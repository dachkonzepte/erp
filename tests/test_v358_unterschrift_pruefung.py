"""Version 1.8.56 -- Stufe 2c-2c, Punkte 1 und 2 (docs/archiv/abnahme-und-gewaehrleistung.md, "Umsetzung 1.8.56").

Punkt 1: eine Abschnittsunterschrift in einer Checkliste verlangt alle Pflichtangaben oberhalb von ihr (Antworten, Fotos,
Belege samt Mindestanzahl) -- sonst 400, nichts gespeichert. Pflicht-Unterschriften oberhalb zählen nicht (eine obere
Unterschrift bleibt nach einer unteren möglich, seit 1.8.14).

Punkt 2: eine gemeinsame Prüfung des gezeichneten Bilds (app/signature_image.py::check_signature_png()) für Checkliste,
Einsatzbericht und Vertrag auf dem Gerät: PNG, höchstens 2 MB und 5000 Pixel je Seite, nicht leer. Strukturtest: jede Spalte,
deren Name nach Unterschrift klingt, ist eingeordnet; jede Funktion unter app/, die ein Unterschriftsbild speichert, ruft die
Prüfung auf (oder alle ihre Aufrufer im Modul tun es). Angriff je Weg über die API: leeres Bild -> 400, nichts gespeichert."""

import ast
import base64
import re
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image, ImageDraw
from sqlalchemy import select

import app.checklists as checklists_module
from app.checklist_templates import add_field, create_template, publish_draft
from app.database import Base
from app.models import ChecklistAttachment, OrderContractSignature, ServiceReport
from app.signature_image import MAX_SIGNATURE_PNG_BYTES, check_signature_png
from tests.test_v305_checklist_filling import _client, _fields, _jpeg, _start_order, world  # noqa: F401
from tests.test_v336_vertrag_festschreiben import world as vertrag_welt  # noqa: F401  (Fixture unter eigenem Namen)

ROOT = Path(__file__).resolve().parent.parent


def _bild(*, ink=True, opaque=False, size=(300, 100), fmt="PNG") -> bytes:
    image = Image.new("RGBA", size, (255, 255, 255, 255 if opaque else 0))
    if ink:
        ImageDraw.Draw(image).line([(10, size[1] - 10), (size[0] // 2, 10), (size[0] - 10, size[1] - 20)],
                                   fill=(17, 17, 17, 255), width=4)
    buf = BytesIO()
    (image.convert("RGB") if fmt == "JPEG" else image).save(buf, fmt)
    return buf.getvalue()


SIGNATUR = _bild()
LEER = _bild(ink=False)
WEISS = _bild(ink=False, opaque=True)


def _b64(data: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(data).decode()


# ---------------------------------------------------------------------------
# Punkt 2: die Prüfung selbst
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("data, text", [
    (b"", "Bitte des Kunden unterschreiben."),
    (LEER, "ist leer"),
    (WEISS, "ist leer"),
    (_bild(fmt="JPEG"), "kein gültiges PNG"),
    (b"\x89PNG\r\n\x1a\n" + b"0" * 200, "kein gültiges PNG"),
    (b"<svg xmlns='http://www.w3.org/2000/svg'/>", "kein gültiges PNG"),
    (SIGNATUR + b"\0" * (MAX_SIGNATURE_PNG_BYTES - len(SIGNATUR) + 1), "zu groß (höchstens 2 MB)"),
    (_bild(size=(5001, 20)), "höchstens 5000 Pixel"),
    (_bild(size=(4000, 3001)), "höchstens 5000 Pixel"),  # 12.004.000 Pixel
], ids=["nichts", "leer", "weiss", "jpeg", "kaputt", "svg", "zu_gross", "zu_breit", "zu_viele_pixel"])
def test_check_rejects(data, text):
    with pytest.raises(ValueError, match=re.escape(text)):
        check_signature_png(data, "des Kunden")


def test_check_accepts_drawn_signature_on_transparent_and_white():
    assert check_signature_png(SIGNATUR, "x") == SIGNATUR
    assert check_signature_png(_bild(opaque=True), "x")
    exact = SIGNATUR + b"\0" * (MAX_SIGNATURE_PNG_BYTES - len(SIGNATUR))  # genau an der Grenze, Rest nach IEND
    assert check_signature_png(exact, "x") == exact


# ---------------------------------------------------------------------------
# Punkt 2: Angriff je Weg über die API -- leeres Bild, kein PNG
# ---------------------------------------------------------------------------

def _checklist_files(world):
    root = checklists_module.CHECKLIST_ROOT
    return sorted(p.name for p in root.rglob("*") if p.is_file()) if root.exists() else []


def _filled(world, client):
    c = _start_order(world, client)
    f = _fields(c)
    assert client.put(f"/api/checklists/{c['id']}/answers/{f['frei']}", json={"value": "ja"}).status_code == 200
    assert client.post(f"/api/checklists/{c['id']}/attachments", data={"field_id": f["fotos"]},
                       files={"file": ("f.jpg", _jpeg(), "image/jpeg")}).status_code == 200
    return c


@pytest.mark.parametrize("bild, text", [(LEER, "ist leer"), (WEISS, "ist leer"), (_bild(fmt="JPEG"), "kein gültiges PNG")],
                         ids=["leer", "weiss", "jpeg"])
def test_attack_checklist_empty_or_foreign_image(world, router_test_client, bild, text):
    a = _client(world, router_test_client, "a")
    c = _filled(world, a)
    vorher = _checklist_files(world)
    r = a.post(f"/api/checklists/{c['id']}/attachments", data={"field_id": _fields(c)["sig"], "signer_name": "Anna Alpha"},
               files={"file": ("s.png", bild, "image/png")})
    assert r.status_code == 400 and text in r.json()["detail"] and "„Unterschrift Monteur“" in r.json()["detail"], r.text
    world["db"].expire_all()
    assert world["db"].scalar(select(ChecklistAttachment.id).where(ChecklistAttachment.kind == "unterschrift")) is None
    assert _checklist_files(world) == vorher
    # Gegenstück: mit Strich angenommen.
    assert a.post(f"/api/checklists/{c['id']}/attachments", data={"field_id": _fields(c)["sig"], "signer_name": "Anna Alpha"},
                  files={"file": ("s.png", SIGNATUR, "image/png")}).status_code == 200


@pytest.fixture
def bericht(threaded_db_session, router_test_client, tmp_path, monkeypatch):
    from app import service_reports as service_reports_module
    from app.routers.service_reports import router as sr_router
    from app.service_reports import create_report
    from tests.test_v325_contract_basis import make_quote
    from tests.test_v335_vertragsvorlagen import beauftragen

    db = threaded_db_session
    monkeypatch.setattr(service_reports_module, "SIGNATURE_ROOT", tmp_path / "sigs")
    order = beauftragen(db, make_quote(db))
    report = create_report(db, order.id, "rapport")
    return {"db": db, "client": router_test_client(db, sr_router), "id": report["id"], "root": tmp_path / "sigs"}


def _sign_report(bericht, installer, customer):
    return bericht["client"].post(f"/api/service-reports/{bericht['id']}/sign", json={
        "installer_signature_png_base64": _b64(installer), "installer_signature_name": "Max Monteur",
        "customer_signature_png_base64": _b64(customer), "customer_signature_name": "Klara Kundin"})


@pytest.mark.parametrize("installer, customer, who, text", [
    (LEER, SIGNATUR, "des Monteurs", "ist leer"),
    (SIGNATUR, WEISS, "des Kunden", "ist leer"),
    (_bild(fmt="JPEG"), SIGNATUR, "des Monteurs", "ist kein gültiges PNG"),
    (SIGNATUR, b"kein bild", "des Kunden", "ist kein gültiges PNG"),
], ids=["monteur_leer", "kunde_weiss", "monteur_jpeg", "kunde_kein_bild"])
def test_attack_service_report_empty_or_foreign_image(bericht, installer, customer, who, text):
    r = _sign_report(bericht, installer, customer)
    assert r.status_code == 400 and f"Die Unterschrift {who} {text}" in r.json()["detail"], r.text
    db = bericht["db"]
    db.expire_all()
    report = db.get(ServiceReport, bericht["id"])
    assert report.status == "entwurf" and report.signature_path is None and report.installer_signature_path is None
    assert not bericht["root"].exists() or not any(bericht["root"].iterdir())
    r = _sign_report(bericht, SIGNATUR, SIGNATUR)
    assert r.status_code == 200 and r.json()["status"] == "unterschrieben", r.text


@pytest.mark.parametrize("partei, who", [("customer", "des Kunden"), ("company", "für den Betrieb")])
def test_attack_contract_empty_image(vertrag_welt, router_test_client, partei, who):
    from tests.test_v337_vertrag_unterschrift import _client as contract_client, _frozen_order, _sign

    db = vertrag_welt
    client = contract_client(db, router_test_client)
    order, version = _frozen_order(db, client)
    r = _sign(client, order, version, **{f"{partei}_signature_png_base64": _b64(LEER)})
    assert r.status_code == 400 and f"Die Unterschrift {who} ist leer" in r.json()["detail"], r.text
    db.expire_all()
    assert db.scalar(select(OrderContractSignature.id)) is None


# ---------------------------------------------------------------------------
# Punkt 2: Strukturtest -- jeder Weg, der ein Unterschriftsbild speichert, prüft es
# ---------------------------------------------------------------------------

# Jede Spalte, deren Name nach Unterschrift klingt: "bild" verweist auf ein gezeichnetes Unterschriftsbild, alles andere
# mit Grund. Eine neue Spalte ist rot, bis sie hier steht -- so fällt ein neuer Unterschrift-Weg auf.
SPALTEN = {
    "service_reports.signature_path": "bild",
    "service_reports.installer_signature_path": "bild",
    "order_contract_signatures.customer_image_document_id": "bild",
    "order_contract_signatures.company_image_document_id": "bild",
    "service_reports.signature_name": "Name",
    "service_reports.signed_at": "Zeitpunkt",
    "service_reports.installer_signature_name": "Name",
    "service_reports.installer_signed_at": "Zeitpunkt",
    "checklist_attachments.signer_name": "Name (das Bild ist die Zeile selbst, Art 'unterschrift' -- siehe ZEILEN)",
    "checklist_template_fields.signer_label": "Beschriftung in der Vorlage",
    "notice_letters.signature_id": "Verweis auf eine schon gespeicherte Unterschrift (liest nur)",
    "notice_letters.signature_sha256": "Prüfsumme der Kopie (liest nur)",
    "order_contract_signatures.signed_on": "Datum",
    "order_contract_signatures.customer_signer_name": "Name",
    "order_contract_signatures.company_signer_name": "Name",
    "order_contract_signatures.signed_content": "unterschriebener Inhalt (Text)",
    "services.image_reference": "Leistungsbild, keine Unterschrift",
}
# Modelle, deren Zeile selbst ein Unterschriftsbild sein kann (Feldtyp "unterschrift"): ihr Anlegen ist ein Weg.
ZEILEN = {"ChecklistAttachment"}
# Funktionen, die ein Unterschriftsbild speichern, ohne es zu prüfen -- nur mit Grund.
OHNE_PRUEFUNG = {
    "app/contract_signatures.py::record_paper_signature": "Papier-Scan statt gezeichnetem Bild (Beleg: PDF oder Foto), "
                                                          "übergibt keine Bild-Verweise an _finish()",
}
NAME = re.compile(r"(^|_)(signature|signer|signed)(_|$)|unterschrift|image")


def test_every_signature_like_column_is_classified():
    gefunden = {f"{t.name}.{c.name}" for t in Base.metadata.sorted_tables for c in t.columns if NAME.search(c.name)}
    assert gefunden - set(SPALTEN) == set(), "neue Spalte -- als 'bild' oder mit Grund einordnen"
    assert set(SPALTEN) - gefunden == set(), "Eintrag ohne Spalte -- entfernen"


def _functions():
    for path in sorted((ROOT / "app").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        rel = path.relative_to(ROOT).as_posix()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                yield rel, node


MODELLE = {m.class_.__name__ for m in Base.registry.mappers}


def _writes_signature_image(func) -> bool:
    """Speichert die Funktion ein Unterschriftsbild? Zuweisung an eine "bild"-Spalte, ein Modell-Konstruktor mit so einem
    Schlüsselwort oder das Anlegen einer Zeile aus ZEILEN. Ein Schlüsselwort an einer gewöhnlichen Funktion (z. B. der
    Pfad an einen PDF-Renderer, der das Bild nur liest) zählt nicht."""
    bild = {s.split(".")[1] for s, art in SPALTEN.items() if art == "bild"}
    for node in ast.walk(func):
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Attribute) and t.attr in bild for t in node.targets):
            return True
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in MODELLE:
            if node.func.id in ZEILEN or any(k.arg in bild for k in node.keywords):
                return True
    return False


def _calls(func, name) -> bool:
    return any(isinstance(n, ast.Call) and ((isinstance(n.func, ast.Name) and n.func.id == name)
                                            or (isinstance(n.func, ast.Attribute) and n.func.attr == name))
               for n in ast.walk(func))


def test_every_path_storing_a_signature_image_checks_it():
    funcs = list(_functions())
    writers = [(rel, f) for rel, f in funcs if _writes_signature_image(f)]
    assert {f"{rel}::{f.name}" for rel, f in writers} >= {
        "app/checklists.py::add_attachment", "app/service_reports.py::sign_report", "app/contract_signatures.py::_finish"}
    fehlend = []
    for rel, f in writers:
        if _calls(f, "check_signature_png"):
            continue
        # Speichert eine Hilfsfunktion, muss jeder Aufrufer im selben Modul prüfen (oder begründet ausgenommen sein).
        callers = [(r, g) for r, g in funcs if r == rel and g is not f and _calls(g, f.name)]
        offen = [f"{r}::{g.name}" for r, g in callers
                 if not _calls(g, "check_signature_png") and f"{r}::{g.name}" not in OHNE_PRUEFUNG]
        if not callers or offen:
            fehlend.append(f"{rel}::{f.name} (Aufrufer ohne Prüfung: {offen or 'keine Aufrufer'})")
    assert not fehlend, "Unterschriftsbild ohne check_signature_png():\n" + "\n".join(fehlend)


def test_no_second_ink_check_outside_the_module():
    """Die Prüfung gibt es nur einmal -- keine eigene Leer-/PNG-Prüfung an einem Weg."""
    for rel, f in _functions():
        if rel != "app/signature_image.py":
            assert f.name not in {"_has_ink", "has_ink", "signature_png", "_decode_signature_png", "_png_from_base64"}, \
                f"{rel}::{f.name}"


# ---------------------------------------------------------------------------
# Punkt 1: Pflichtangaben oberhalb einer Abschnittsunterschrift
# ---------------------------------------------------------------------------

@pytest.fixture
def abschnitte(world):
    """Zwei Abschnitte: Freigabe (Pflicht-Text, Pflicht-Unterschrift) und Nachkontrolle (Pflicht ja/nein mit "entfällt",
    Foto mit Mindestanzahl 1, freiwilliger Text, Unterschrift)."""
    db = world["db"]
    t = create_template(db, label="Heißarbeiten (Test)", contexts=["auftrag"])
    v = t["draft_version_id"]
    for werte in (
        {"field_type": "text", "label": "Arbeitsbereich", "field_key": "bereich", "required": True},
        {"field_type": "unterschrift", "label": "Unterschrift Ausführender", "field_key": "sig1", "required": True},
        {"field_type": "ja_nein", "label": "Nachkontrolle ohne Befund", "field_key": "ok", "required": True,
         "allow_na": True},
        {"field_type": "foto", "label": "Fotos Nachkontrolle", "field_key": "fotos", "min_count": 1, "max_count": 3},
        {"field_type": "text", "label": "Bemerkung", "field_key": "bem"},
        {"field_type": "unterschrift", "label": "Unterschrift Brandwache", "field_key": "sig2"},
    ):
        add_field(db, v, werte)
    return publish_draft(db, t["id"])


def _start(world, client, template):
    r = client.post("/api/checklists", json={"template_id": template["id"], "context_type": "auftrag",
                                             "order_id": world["orders"]["mine"].id})
    assert r.status_code == 200, r.text
    return r.json()


def _unterschreiben(client, c, key, name="Anna Alpha"):
    return client.post(f"/api/checklists/{c['id']}/attachments", data={"field_id": _fields(c)[key], "signer_name": name},
                       files={"file": ("s.png", SIGNATUR, "image/png")})


def _antwort(client, c, key, value):
    r = client.put(f"/api/checklists/{c['id']}/answers/{_fields(c)[key]}", json={"value": value})
    assert r.status_code == 200, r.text
    return r.json()


def _signaturen(world):
    world["db"].expire_all()
    return world["db"].scalars(select(ChecklistAttachment).where(ChecklistAttachment.kind == "unterschrift")).all()


def test_signature_requires_required_fields_above(world, router_test_client, abschnitte):
    a = _client(world, router_test_client, "a")
    c = _start(world, a, abschnitte)
    vorher = _checklist_files(world)
    r = _unterschreiben(a, c, "sig1")
    assert r.status_code == 400 and r.json()["detail"] == (
        "Vor der Unterschrift „Unterschrift Ausführender“ fehlen noch Pflichtangaben: Arbeitsbereich."), r.text
    assert _signaturen(world) == [] and _checklist_files(world) == vorher  # kein Bild gespeichert
    _antwort(a, c, "bereich", "Dach Nord")
    assert _unterschreiben(a, c, "sig1").status_code == 200  # Felder darunter zählen nicht


def test_lower_signature_needs_its_section_and_everything_above(world, router_test_client, abschnitte):
    a = _client(world, router_test_client, "a")
    c = _start(world, a, abschnitte)
    _antwort(a, c, "bereich", "Dach Nord")
    r = _unterschreiben(a, c, "sig2")
    # Pflicht-Unterschriften oberhalb zählen nicht (Festlegung), die Mindestanzahl der Fotos schon.
    assert r.status_code == 400 and r.json()["detail"].endswith(
        "fehlen noch Pflichtangaben: Nachkontrolle ohne Befund, Fotos Nachkontrolle."), r.text
    _antwort(a, c, "ok", "entfaellt")  # "entfällt" ist eine Antwort
    r = _unterschreiben(a, c, "sig2")
    assert r.status_code == 400 and r.json()["detail"].endswith("Pflichtangaben: Fotos Nachkontrolle."), r.text
    assert a.post(f"/api/checklists/{c['id']}/attachments", data={"field_id": _fields(c)["fotos"]},
                  files={"file": ("f.jpg", _jpeg(), "image/jpeg")}).status_code == 200
    assert _unterschreiben(a, c, "sig2").status_code == 200
    # Die obere Unterschrift bleibt danach möglich (seit 1.8.14) -- ihre Felder sind ausgefüllt.
    assert _unterschreiben(a, c, "sig1").status_code == 200


def test_missing_fields_are_listed_per_signature_for_the_page(world, router_test_client, abschnitte):
    a = _client(world, router_test_client, "a")
    c = _start(world, a, abschnitte)
    f = _fields(c)
    assert c["missing_before_signature"] == {
        str(f["sig1"]): ["Arbeitsbereich"],
        str(f["sig2"]): ["Arbeitsbereich", "Nachkontrolle ohne Befund", "Fotos Nachkontrolle"]}
    c = _antwort(a, c, "bereich", "Dach Nord")
    assert c["missing_before_signature"][str(f["sig1"])] == []


def test_attack_signature_with_missing_required_field_via_api(world, router_test_client):
    """Die Seite sperrt den Knopf -- die API muss es trotzdem ablehnen, auch fürs Büro und für eine Wiederholung."""
    office = _client(world, router_test_client, "office")
    c = _start_order(world, office)  # Sicherheitscheck: "Freigegeben" Pflicht, Fotos mindestens 1, dann "sig"
    r = _unterschreiben(office, c, "sig", name="Olga Office")
    assert r.status_code == 400 and "Freigegeben, Fotos" in r.json()["detail"]
    r = office.post(f"/api/checklists/{c['id']}/attachments",
                    data={"field_id": _fields(c)["sig"], "signer_name": "Olga Office", "client_uuid": "k-1"},
                    files={"file": ("s.png", SIGNATUR, "image/png")})
    assert r.status_code == 400 and _signaturen(world) == []


def test_checklist_page_blocks_signature_with_missing_fields():
    page = (ROOT / "app/templates/checklist.html").read_text(encoding="utf-8")
    assert "cl.missing_before_signature" in page and "data-missing-before" in page
    assert "Vor der Unterschrift fehlen noch" in page
    # saveSignature bricht vor der Rückfrage ab, und jede gespeicherte Eingabe frischt den Hinweis auf
    assert "if(fehlt){setStatus(fieldId,fehlt,true);updateMissing();return}" in page
    assert page.count("cl.missing_before_signature=data.missing_before_signature") == 3
