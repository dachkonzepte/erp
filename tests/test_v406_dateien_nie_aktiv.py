"""Version 1.8.101 -- hochgeladene Dateien nie als aktiver Inhalt (Vorgabe vom 14.10.2026, Punkt 1; Befund 1.8.100 Nr. 4).

Jede Stelle, die eine abgelegte Datei ausliefert, geht über app/dateiauslieferung.py::datei_antwort(): den Typ bestimmt der Server am
Inhalt, im Browser angezeigt werden nur Rasterbilder (JPEG, PNG, GIF, WebP) und PDF, alles andere kommt als Download
(application/octet-stream, attachment, CSP sandbox), immer mit nosniff. Hier:
- die Erkennung am Inhalt und die Antwort selbst,
- Angriffe über die Ablagen, in die jemand eine beliebige Datei legen kann (Kundenakte, Projektmappe, Objekt im Büro und in /mobil,
  Lieferschein, Skizze, Hintergrund, Logo, Eingangsrechnung, Betriebsmittel, Betriebskosten) -- SVG und HTML mit Skript, auch mit
  falscher Angabe des Browsers, laufen nie; Foto und PDF erscheinen weiter,
- der Strukturtest: FileResponse nur im Modul, jede andere Antwort mit Inhalt hat einen festen Typ.
Gegenproben (Regel 24): docs/archiv/befund-vor-echtbetrieb.md, "Umsetzung 1.8.101"."""

from __future__ import annotations

import ast
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from app.dateiauslieferung import ANZEIGBAR, datei_antwort, gespeicherter_typ, typ_aus_inhalt
from app.models import (Customer, DocumentCategory, Employee, IncomingInvoice, OperationalAsset, OperationalAssetInspection, Project,
                        Property, RecurringCost, RoofArea, Supplier)
from app.routers import customer_documents as customer_documents_router
from app.routers import customers as customers_router
from app.routers import document_layout as document_layout_router
from app.routers import field_view as field_view_router
from app.routers import incoming_invoices as incoming_invoices_router
from app.routers import operational_assets as operational_assets_router
from app.routers import project_documents as project_documents_router
from app.routers import projects as projects_router
from app.routers import property_documents as property_documents_router
from app.routers import recurring_costs as recurring_costs_router
from app.routers import roof_areas as roof_areas_router
from app.routers import settings as settings_router

ROOT = Path(__file__).resolve().parent.parent


def _bild(fmt: str) -> bytes:
    puffer = BytesIO()
    Image.new("RGB", (8, 6), (200, 40, 40)).save(puffer, format=fmt)
    return puffer.getvalue()


JPEG, PNG, GIF, WEBP = _bild("JPEG"), _bild("PNG"), _bild("GIF"), _bild("WEBP")
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
SVG = b'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"><script>alert(document.domain)</script></svg>'
SVG_MIT_KOPF = (b'\xef\xbb\xbf<?xml version="1.0" encoding="UTF-8"?>\n<!-- Logo -->\n<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" '
                b'"x">\n<svg xmlns="http://www.w3.org/2000/svg"><rect width="4" height="4"/></svg>')
HTML = b"<html><body><script>alert(document.domain)</script></body></html>"
XHTML = b'<?xml version="1.0"?><html xmlns="http://www.w3.org/1999/xhtml"><script>alert(1)</script></html>'
XML = b'<?xml version="1.0"?><a:script xmlns:a="http://www.w3.org/1999/xhtml">alert(1)</a:script>'
TEXT = b"Hallo <script>alert(1)</script>"


# ---------------------------------------------------------------------------
# Erkennung am Inhalt und Antwort
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("daten, typ", [
    (JPEG, "image/jpeg"), (PNG, "image/png"), (GIF, "image/gif"), (WEBP, "image/webp"), (PDF, "application/pdf"),
    (SVG, None), (SVG_MIT_KOPF, None), (HTML, None), (XHTML, None), (XML, None), (TEXT, None), (b"", None),
    (b"PK\x03\x04docx", None), (b" %PDF-1.4", None), (b"RIFF\x00\x00\x00\x00WAVE", None),
])
def test_der_typ_kommt_aus_den_ersten_bytes(daten, typ):
    assert typ_aus_inhalt(daten) == typ
    assert gespeicherter_typ(daten) == (typ or "application/octet-stream")


def _art(antwort) -> tuple[str, str]:
    return (antwort.headers.get("content-type", "").split(";")[0].strip().lower(),
            antwort.headers.get("content-disposition", "").split(";")[0].strip().lower())


def _pruefen(antwort, erwartet: str | None, *, herunterladen: bool = False) -> None:
    """erwartet: der Typ einer anzeigbaren Datei, None für alles andere (Download ohne Typ)."""
    assert antwort.status_code == 200, antwort.status_code
    typ, art = _art(antwort)
    assert antwort.headers.get("x-content-type-options") == "nosniff"
    if erwartet is None:
        assert (typ, art) == ("application/octet-stream", "attachment")
        assert antwort.headers.get("content-security-policy") == "sandbox"
    else:
        assert typ == erwartet and art == ("attachment" if herunterladen else "inline")
    if art == "inline":  # was der Browser zeigt, ist ein Rasterbild oder ein PDF -- nie etwas mit Skript
        assert typ in ANZEIGBAR


@pytest.mark.parametrize("daten, typ", [(JPEG, "image/jpeg"), (PNG, "image/png"), (GIF, "image/gif"), (WEBP, "image/webp"),
                                        (PDF, "application/pdf"), (SVG, None), (SVG_MIT_KOPF, None), (HTML, None), (XHTML, None),
                                        (XML, None), (TEXT, None), (b"", None)])
def test_datei_antwort_zeigt_nur_rasterbilder_und_pdf(tmp_path, daten, typ):
    pfad = tmp_path / "datei.svg"  # Endung und Name täuschen nichts vor: der Typ kommt aus dem Inhalt
    pfad.write_bytes(daten)
    from starlette.testclient import TestClient
    from fastapi import FastAPI
    app = FastAPI()
    app.get("/pfad")(lambda: datei_antwort(pfad, "bild.svg"))
    app.get("/bytes")(lambda: datei_antwort(daten, "bild.png"))
    app.get("/laden")(lambda: datei_antwort(pfad, "bild.png", herunterladen=True))
    client = TestClient(app)
    for url in ("/pfad", "/bytes"):
        antwort = client.get(url)
        _pruefen(antwort, typ)
        assert antwort.content == daten
    _pruefen(client.get("/laden"), typ, herunterladen=True)


def test_svg_als_bild_nur_fuer_echtes_svg_mit_csp_und_als_download():
    antwort = datei_antwort(SVG_MIT_KOPF, svg_als_bild=True)
    assert antwort.media_type == "image/svg+xml"
    assert antwort.headers["content-disposition"] == "attachment"
    csp = antwort.headers["content-security-policy"]
    assert csp.startswith("sandbox;") and "default-src 'none'" in csp and "script-src" not in csp
    for falsch in (HTML, XHTML, XML, TEXT, b"<svgx>"):
        assert datei_antwort(falsch, svg_als_bild=True).media_type == "application/octet-stream", falsch
    assert datei_antwort(PNG, svg_als_bild=True).headers["content-disposition"] == "inline"


@pytest.mark.parametrize("name, kopf", [
    ("plan.pdf", 'inline; filename="plan.pdf"'),
    ('a"b.pdf', "inline; filename*=utf-8''a%22b.pdf"),
    ("Größe;x.pdf", "inline; filename*=utf-8''Gr%C3%B6%C3%9Fe%3Bx.pdf"),
    ("a\r\nSet-Cookie: x.pdf", "inline; filename*=utf-8''a%20%20Set-Cookie%3A%20x.pdf"),
    ("../../etc/x.pdf", "inline; filename*=utf-8''..%2F..%2Fetc%2Fx.pdf"),
])
def test_der_dateiname_kann_die_kopfzeile_nicht_aufbrechen(name, kopf):
    assert datei_antwort(PDF, name).headers["content-disposition"] == kopf


def test_weitere_kopfzeilen_ersetzen_nie_typ_disposition_nosniff_oder_csp():
    antwort = datei_antwort(HTML, "x.html", kopfzeilen={"Content-Type": "text/html", "Content-Disposition": "inline",
                                                        "X-Content-Type-Options": "", "Content-Security-Policy": "",
                                                        "Cache-Control": "private, max-age=60"})
    assert antwort.media_type == "application/octet-stream"
    assert antwort.headers["content-disposition"].startswith("attachment")
    assert antwort.headers["x-content-type-options"] == "nosniff" and antwort.headers["content-security-policy"] == "sandbox"
    assert antwort.headers["cache-control"] == "private, max-age=60"


# ---------------------------------------------------------------------------
# Angriffe über die Ablagen
# ---------------------------------------------------------------------------

# (Name, Inhalt, Angabe des Browsers, erwarteter Typ beim Anzeigen -- None = Download)
UPLOADS = [
    ("bild.svg", SVG, "image/svg+xml", None),
    ("plan.html", HTML, "text/html", None),
    ("foto.png", HTML, "image/png", None),  # HTML, das sich als Foto ausgibt
    ("seite.xhtml", XHTML, "application/xhtml+xml", None),
    ("daten.xml", XML, "text/xml", None),
    ("foto.jpg", JPEG, "text/html", "image/jpeg"),  # ein echtes Foto mit falscher Angabe bleibt ein Foto
    ("scan.pdf", PDF, "application/octet-stream", "application/pdf"),
    ("animation.gif", GIF, "image/gif", "image/gif"),
]


@pytest.fixture
def ablage(threaded_db_session, router_test_client):
    db = threaded_db_session
    kunde = Customer(name="Kunde", last_name="Kunde")
    db.add(kunde); db.flush()
    from app.project_pipeline_columns import default_pipeline_column_id
    projekt = Project(project_number="P-1", name="Dach", customer_id=kunde.id, pipeline_column_id=default_pipeline_column_id(db))
    objekt = Property(customer_id=kunde.id, name="Halle")
    monteur = Employee(first_name="Mia", last_name="Monteur")
    db.add_all([projekt, objekt, monteur]); db.flush()
    flaeche = RoofArea(property_id=objekt.id, name="Nord")
    lieferant = Supplier(name="Lieferant")
    db.add_all([flaeche, lieferant]); db.commit()
    routers = (customers_router.router, customer_documents_router.router, projects_router.router, project_documents_router.router,
               property_documents_router.router, field_view_router.router, roof_areas_router.router, document_layout_router.router,
               settings_router.router, incoming_invoices_router.router, operational_assets_router.router, recurring_costs_router.router)
    return {"db": db, "client": router_test_client(db, *routers), "monteur": router_test_client(db, *routers, employee_id=monteur.id),
            "kunde": kunde.id, "projekt": projekt.id, "objekt": objekt.id, "flaeche": flaeche.id, "lieferant": lieferant.id}


def _kategorie(db, nur_monteur: bool = False) -> int:
    from app.document_categories import field_may_see_category
    for kategorie in db.query(DocumentCategory).order_by(DocumentCategory.id):
        if not nur_monteur or field_may_see_category(kategorie):
            return kategorie.id
    raise AssertionError("keine Kategorie")


@pytest.mark.parametrize("name, daten, angabe, erwartet", UPLOADS)
def test_kundenakte(ablage, name, daten, angabe, erwartet):
    c = ablage["client"]
    doc = c.post(f"/api/customers/{ablage['kunde']}/documents", files={"file": (name, daten, angabe)}).json()
    assert doc["content_type"] == (erwartet or "application/octet-stream")  # den Typ bestimmt der Server
    assert doc["can_preview"] is (erwartet is not None)
    assert doc["is_image"] is (erwartet or "").startswith("image/")
    _pruefen(c.get(f"/api/customer-documents/{doc['id']}/view"), erwartet)
    _pruefen(c.get(f"/api/customer-documents/{doc['id']}/download"), erwartet, herunterladen=True)


@pytest.mark.parametrize("name, daten, angabe, erwartet", UPLOADS)
def test_projektmappe(ablage, name, daten, angabe, erwartet):
    c = ablage["client"]
    doc = c.post(f"/api/projects/{ablage['projekt']}/documents", files={"file": (name, daten, angabe)}).json()
    assert doc["content_type"] == (erwartet or "application/octet-stream")
    assert doc["can_preview"] is (erwartet is not None)
    _pruefen(c.get(f"/api/project-documents/{doc['id']}/view"), erwartet)
    _pruefen(c.get(f"/api/project-documents/{doc['id']}/download"), erwartet, herunterladen=True)


@pytest.mark.parametrize("name, daten, angabe, erwartet", UPLOADS)
@pytest.mark.parametrize("wer", ["buero", "monteur"])
def test_objekt_im_buero_und_in_mobil(ablage, wer, name, daten, angabe, erwartet):
    """Bilder legt das Objekt als JPEG ab (verkleinert) -- auch ein GIF, und auch dann, wenn der Browser etwas anderes angab; SVG und
    HTML scheitern nicht mehr an Pillow und bleiben unverändert als Download liegen."""
    db = ablage["db"]
    erwartet = "image/jpeg" if (erwartet or "").startswith("image/") else erwartet
    if wer == "buero":
        doc = ablage["client"].post(f"/api/properties/{ablage['objekt']}/documents", data={"category_id": str(_kategorie(db))},
                                    files={"file": (name, daten, angabe)}).json()
    else:
        doc = ablage["monteur"].post(f"/api/field-view/properties/{ablage['objekt']}/documents",
                                     data={"category_id": str(_kategorie(db, nur_monteur=True))}, files={"file": (name, daten, angabe)}).json()
    assert doc["content_type"] == (erwartet or "application/octet-stream")
    assert doc["can_preview"] is (erwartet is not None)
    c = ablage["client"]
    _pruefen(c.get(f"/api/property-documents/{doc['id']}/view"), erwartet)
    _pruefen(c.get(f"/api/property-documents/{doc['id']}/download"), erwartet, herunterladen=True)
    basis = f"/api/field-view/properties/{ablage['objekt']}/documents/property/{doc['id']}"
    _pruefen(ablage["monteur"].get(f"{basis}/view"), erwartet)
    _pruefen(ablage["monteur"].get(f"{basis}/download"), erwartet, herunterladen=True)


def test_eintraege_von_vor_1_8_101_mit_dem_typ_des_browsers(ablage):
    """Bis 1.8.100 speicherten Kundenakte und Projektmappe die Angabe des Browsers (image/svg+xml, text/html). Solche Einträge zeigen
    keine Vorschau und kein "Öffnen" mehr und kommen als Download -- der Typ kommt beim Ausliefern aus dem Inhalt."""
    from app.customer_documents import customer_directory
    from app.document_categories import resolve_category_id
    from app.models import CustomerDocument
    db, c = ablage["db"], ablage["client"]
    ids = {}
    for name, daten, typ in (("alt.svg", SVG, "image/svg+xml"), ("alt.html", HTML, "text/html"), ("alt.png", HTML, "image/png")):
        (customer_directory(ablage["kunde"]) / name).write_bytes(daten)
        doc = CustomerDocument(customer_id=ablage["kunde"], category="Sonstiges", category_id=resolve_category_id(db, "Sonstiges"),
                               original_filename=name, stored_filename=name, content_type=typ, file_size=len(daten))
        db.add(doc); db.commit()
        ids[name] = doc.id
    liste = {d["original_filename"]: [d["is_image"], d["can_preview"]] for d in c.get(f"/api/customers/{ablage['kunde']}/documents").json()}
    assert liste == {"alt.svg": [False, False], "alt.html": [False, False], "alt.png": [True, True]}  # PNG laut Eintrag: Vorschau
    for doc_id in ids.values():
        _pruefen(c.get(f"/api/customer-documents/{doc_id}/view"), None)  # ... aber am Inhalt HTML: Download


def test_ein_kaputtes_rasterbild_am_objekt_bleibt_als_download(ablage):
    """Erkennt der Server ein Rasterbild, das Pillow nicht lesen kann, bleibt es unverändert liegen (bis 1.8.100 ein 500)."""
    kaputt = b"\x89PNG\r\n\x1a\n" + b"<script>alert(1)</script>"
    c = ablage["client"]
    doc = c.post(f"/api/properties/{ablage['objekt']}/documents", data={"category_id": str(_kategorie(ablage["db"]))},
                 files={"file": ("foto.png", kaputt, "image/png")}).json()
    assert doc["content_type"] == "application/octet-stream" and doc["can_preview"] is False
    antwort = c.get(f"/api/property-documents/{doc['id']}/view")
    assert _art(antwort) == ("image/png", "inline")  # am Inhalt erkannt: der Browser zeigt es als (kaputtes) Bild, nie als Skript
    assert antwort.headers["x-content-type-options"] == "nosniff"


def test_skizze_der_dachflaeche(ablage):
    """Die Skizze lag bis 1.8.100 mit der Endung des Browsers und ging ohne Typ hinaus: "plan.html" mit Angabe image/png lief als
    HTML."""
    c = ablage["client"]
    for name, daten, angabe, erwartet in (("plan.html", HTML, "image/png", None), ("skizze.jpg", JPEG, "image/jpeg", "image/jpeg")):
        assert c.post(f"/api/roof-areas/{ablage['flaeche']}/sketch", files={"file": (name, daten, angabe)}).status_code == 200
        _pruefen(c.get(f"/api/roof-areas/{ablage['flaeche']}/sketch"), erwartet)


def test_hintergrund_der_dokumente(ablage):
    c = ablage["client"]
    for name, daten, erwartet in (("hg.html", HTML, None), ("hg.png", PNG, "image/png")):
        assert c.post("/api/document-layout/default/background", files={"file": (name, daten, "image/png")}).status_code == 200
        _pruefen(c.get("/api/document-layout/default/background/file"), erwartet)


@pytest.mark.parametrize("pfad", ["/api/settings/general/logo", "/api/settings/general/sidebar-logo"])
def test_logo_svg_nur_als_bild(ablage, pfad):
    """Ein SVG-Logo erscheint in der Seitenleiste (<img>), direkt geöffnet kommt es als Download und ohne Skript; HTML, das sich als SVG
    ausgibt, kommt als Download ohne Typ; ein Rasterbild wie bisher inline."""
    c = ablage["client"]
    assert c.post(pfad, files={"file": ("logo.svg", SVG, "image/svg+xml")}).status_code == 200
    antwort = c.get(pfad)
    assert _art(antwort) == ("image/svg+xml", "attachment")
    assert antwort.headers["content-security-policy"].startswith("sandbox;") and antwort.headers["x-content-type-options"] == "nosniff"
    assert c.post(pfad, files={"file": ("logo.svg", HTML, "image/svg+xml")}).status_code == 200
    _pruefen(c.get(pfad), None)
    assert c.post(pfad, files={"file": ("logo.png", PNG, "image/png")}).status_code == 200
    _pruefen(c.get(pfad), "image/png")


def test_eingangsrechnung_betriebsmittel_betriebskosten_kommen_als_download(ablage):
    """Diese Ablagen prüfen nur die Angabe des Browsers (PDF/Bild) und lieferten mit dem Typ der Endung als Download aus -- jetzt am
    Inhalt: HTML ohne Typ, PDF als PDF, beides als Download (wie bisher)."""
    db, c = ablage["db"], ablage["client"]
    from datetime import date
    rechnung = IncomingInvoice(supplier_id=ablage["lieferant"], invoice_date=date(2026, 10, 1), net_amount=10)
    geraet = OperationalAsset(name="Leiter")
    kosten = RecurringCost(label="Miete", net_amount=10, billing_interval="monthly", annual_amount=120)
    db.add_all([rechnung, geraet, kosten]); db.flush()
    pruefung = OperationalAssetInspection(asset_id=geraet.id, inspection_type="UVV")
    db.add(pruefung); db.commit()
    for name, daten, erwartet in (("r.html", HTML, None), ("r.pdf", PDF, "application/pdf")):
        datei = {"file": (name, daten, "application/pdf")}
        assert c.post(f"/api/incoming-invoices/{rechnung.id}/document", files=datei).status_code == 200
        _pruefen(c.get(f"/api/incoming-invoices/{rechnung.id}/document/file"), erwartet, herunterladen=True)
        assert c.post(f"/api/operational-asset-inspections/{pruefung.id}/document", files=datei).status_code == 200
        _pruefen(c.get(f"/api/operational-asset-inspections/{pruefung.id}/document"), erwartet, herunterladen=True)
        doc = c.post(f"/api/operational-assets/{geraet.id}/documents", data={"document_type": "Rechnung"}, files=datei).json()
        _pruefen(c.get(f"/api/operational-asset-documents/{doc['id']}/file"), erwartet, herunterladen=True)
        doc = c.post(f"/api/recurring-costs/{kosten.id}/documents", data={"document_type": "Vertrag"}, files=datei).json()
        _pruefen(c.get(f"/api/recurring-cost-documents/{doc['id']}/file"), erwartet, herunterladen=True)


# ---------------------------------------------------------------------------
# Strukturtest: jede Auslieferung abgelegter Dateien über datei_antwort()
# ---------------------------------------------------------------------------

MODUL = ROOT / "app" / "dateiauslieferung.py"
ANTWORTEN = {"Response", "StreamingResponse"}


def _name(knoten) -> str | None:
    if isinstance(knoten, ast.Name):
        return knoten.id
    if isinstance(knoten, ast.Attribute):
        return knoten.attr
    return None


def _fest(ausdruck, funktion) -> bool:
    """Ein fester Typ: Text, a if b else c mit festen Zweigen, oder ein Name, dem in der Funktion nur Festes zugewiesen wird."""
    if isinstance(ausdruck, ast.Constant):
        return isinstance(ausdruck.value, str)
    if isinstance(ausdruck, ast.IfExp):
        return _fest(ausdruck.body, funktion) and _fest(ausdruck.orelse, funktion)
    if isinstance(ausdruck, ast.Name) and funktion is not None:
        werte = [k.value for k in ast.walk(funktion) if isinstance(k, ast.Assign)
                 and any(isinstance(z, ast.Name) and z.id == ausdruck.id for z in k.targets)]
        return bool(werte) and all(_fest(w, None) for w in werte)
    return False


def funde_ausserhalb(quellen: dict[str, str]) -> list[str]:
    """Jede Stelle außerhalb von app/dateiauslieferung.py, die eine Datei an datei_antwort() vorbei ausliefern könnte: FileResponse
    überhaupt, oder Response/StreamingResponse mit Inhalt, deren Typ nicht fest im Code steht (z. B. der gespeicherte Typ)."""
    funde = []
    for pfad, text in quellen.items():
        baum = ast.parse(text)
        eltern = {}
        for knoten in ast.walk(baum):
            for kind in ast.iter_child_nodes(knoten):
                eltern[kind] = knoten
        for knoten in ast.walk(baum):
            if isinstance(knoten, ast.alias) and knoten.name.split(".")[-1] == "FileResponse":
                funde.append(f"{pfad}:{getattr(knoten, 'lineno', '?')}: FileResponse importiert")
            elif _name(knoten) == "FileResponse" and isinstance(knoten, (ast.Name, ast.Attribute)):
                funde.append(f"{pfad}:{knoten.lineno}: FileResponse")
            elif isinstance(knoten, ast.Call) and _name(knoten.func) in ANTWORTEN:
                funktion = knoten
                while funktion is not None and not isinstance(funktion, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    funktion = eltern.get(funktion)
                kw = {k.arg: k.value for k in knoten.keywords}
                inhalt = knoten.args or "content" in kw
                typ = kw.get("media_type", knoten.args[3] if len(knoten.args) > 3 else None)
                if inhalt and (typ is None or not _fest(typ, funktion)):
                    funde.append(f"{pfad}:{knoten.lineno}: {_name(knoten.func)} ohne festen Typ")
    return funde


def _app_quellen() -> dict[str, str]:
    return {str(p.relative_to(ROOT)).replace("\\", "/"): p.read_text(encoding="utf-8")
            for p in sorted((ROOT / "app").rglob("*.py")) if p != MODUL}


def test_jede_abgelegte_datei_geht_ueber_datei_antwort():
    assert funde_ausserhalb(_app_quellen()) == []


def test_die_auslieferungsstellen_rufen_datei_antwort_auf():
    """Gegenstück: der Strukturtest sieht die Stellen überhaupt -- jede bekannte Auslieferung ruft datei_antwort() auf."""
    aufrufe = {}
    for pfad, text in _app_quellen().items():
        n = sum(1 for k in ast.walk(ast.parse(text)) if isinstance(k, ast.Call) and _name(k.func) == "datei_antwort")
        if n:
            aufrufe[pfad] = n
    assert aufrufe == {
        "app/routers/acceptances.py": 1, "app/routers/checklists.py": 2, "app/routers/customer_documents.py": 2,
        "app/routers/defects.py": 1, "app/routers/document_layout.py": 2, "app/routers/email_dispatches.py": 1,
        "app/routers/field_defects.py": 1, "app/routers/field_view.py": 2, "app/routers/incoming_invoices.py": 1,
        "app/routers/operational_assets.py": 2, "app/routers/project_documents.py": 2, "app/routers/project_participants.py": 1,
        "app/routers/property_documents.py": 2, "app/routers/recurring_costs.py": 1, "app/routers/roof_areas.py": 1,
        "app/routers/service_reports.py": 1, "app/routers/settings.py": 4,
    }


@pytest.mark.parametrize("code, fund", [
    ("from fastapi.responses import FileResponse\n", "FileResponse importiert"),
    ("import starlette.responses as r\ndef f(p):\n    return r.FileResponse(p)\n", "FileResponse"),
    ("def f(doc, data):\n    return Response(content=data, media_type=doc.content_type)\n", "Response ohne festen Typ"),
    ("def f(data):\n    return Response(data)\n", "Response ohne festen Typ"),
    ("def f(data, t):\n    typ = t\n    return Response(content=data, media_type=typ)\n", "Response ohne festen Typ"),
    ("def f(data):\n    return StreamingResponse(iter([data]), media_type=data.typ)\n", "StreamingResponse ohne festen Typ"),
    ("def f(data, x):\n    return Response(content=data, media_type='text/csv' if x else x)\n", "Response ohne festen Typ"),
])
def test_strukturtest_findet_umgehungen(code, fund):
    assert [f.split(": ", 1)[1] for f in funde_ausserhalb({"app/x.py": code})] == [fund]


@pytest.mark.parametrize("code", [
    "def f(pdf):\n    return Response(content=pdf, media_type='application/pdf')\n",
    "def f(d, x):\n    media = 'text/plain' if x else 'text/csv'\n    return Response(content=d, media_type=media)\n",
    "def f():\n    return Response(status_code=204)\n",
    "def f(p):\n    return datei_antwort(p, 'a.pdf')\n",
])
def test_strukturtest_laesst_feste_typen_durch(code):
    assert funde_ausserhalb({"app/x.py": code}) == []
