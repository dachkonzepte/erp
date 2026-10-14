"""Klicktest: hochgeladene Dateien nie als aktiver Inhalt (1.8.101, Vorgabe vom 14.10.2026 Punkt 1; Befund 1.8.100 Nr. 4).

Bis 1.8.100 gingen Dokumente inline mit dem Typ hinaus, den der Browser beim Hochladen nannte: eine SVG- oder HTML-Datei mit Skript lief
beim Öffnen auf dem Ursprung des ERP. Seit 1.8.101 bestimmt der Server den Typ am Inhalt; angezeigt werden nur Rasterbilder und PDF, alles
andere kommt als Download (app/dateiauslieferung.py). Jedes Skript in den Testdateien schreibt in den localStorage des ERP -- liefe es,
stünde danach dort ein Eintrag.

    Kundenakte      SVG und HTML (neu hochgeladen und als Eintrag von vor 1.8.101 mit dem Typ des Browsers), Foto und PDF:
                    Vorschaubild nur beim Foto (geladen), "Öffnen" nur bei Foto und PDF; jede view-Adresse direkt geöffnet --
                    Foto als Bild, PDF als PDF, SVG und HTML als Download im Download-Ordner, kein Skript gelaufen
    Projektmappe    dasselbe
    Objekt          dasselbe (Bilder als JPEG abgelegt); /mobil/objekt als Monteurin: "Ansehen" nur bei Foto und PDF, view direkt
                    geöffnet wie oben
    Logo            SVG-Logo mit Skript in der Seitenleiste als Bild sichtbar, direkt geöffnet ein Download, kein Skript

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_dateien_nie_aktiv.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe
scripts/cdp_klicktest.py. Dauer rund eine Minute.
"""

import asyncio
import json
import sys
from io import BytesIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402

SVG = (b'<svg xmlns="http://www.w3.org/2000/svg" width="120" height="40" onload="localStorage.setItem(\'dkXss\',\'svg-onload\')">'
       b'<rect width="120" height="40" fill="#0d9488"/><script>localStorage.setItem("dkXss","svg")</script></svg>')
HTML = b'<html><body><h1>Plan</h1><script>localStorage.setItem("dkXss","html")</script></body></html>'
PDF = (b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
       b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n")


def _foto() -> bytes:
    from PIL import Image
    puffer = BytesIO()
    Image.new("RGB", (60, 40), (13, 148, 136)).save(puffer, format="JPEG")
    return puffer.getvalue()


def befuellen(db, k):
    """Je Ablage ein Eintrag "von vor 1.8.101": gespeicherter Typ = Angabe des Browsers (image/svg+xml, text/html)."""
    from app.customer_documents import customer_directory
    from app.document_categories import field_may_see_category, resolve_category_id
    from app.models import (AppUser, Customer, CustomerDocument, DocumentCategory, Employee, Project, ProjectDocument, Property,
                            PropertyDocument)
    from app.project_documents import project_directory
    from app.project_pipeline_columns import default_pipeline_column_id
    from app.property_documents import property_directory

    mia = Employee(first_name="Mia", last_name="Monteurin")
    db.add(mia); db.flush()
    bea = AppUser(username="bea", display_name="Bea Büro", role="buero_auftrag", password_hash=k.passwort())
    monteurin = AppUser(username="mia", display_name="Mia", role="field", employee_id=mia.id, password_hash=k.passwort())
    kunde = Customer(name="Kunde Dateien", last_name="Dateien", city="Uebach")
    db.add_all([bea, monteurin, kunde]); db.flush()
    projekt = Project(project_number="P-DAT", name="Dach Dateien", customer_id=kunde.id, pipeline_column_id=default_pipeline_column_id(db))
    objekt = Property(customer_id=kunde.id, name="Halle Dateien", city="Uebach")
    db.add_all([projekt, objekt]); db.flush()
    kategorie = next(c for c in db.query(DocumentCategory).order_by(DocumentCategory.id) if field_may_see_category(c))
    alt = {}
    for art, daten, typ in (("svg", SVG, "image/svg+xml"), ("html", HTML, "text/html")):
        for ordner in (customer_directory(kunde.id), project_directory(projekt.id), property_directory(objekt.id)):
            (ordner / f"alt.{art}").write_bytes(daten)
        sonstiges = resolve_category_id(db, "Sonstiges")
        c = CustomerDocument(customer_id=kunde.id, category="Sonstiges", category_id=sonstiges, original_filename=f"alt-kunde.{art}",
                             stored_filename=f"alt.{art}", content_type=typ, file_size=len(daten))
        p = ProjectDocument(project_id=projekt.id, category="Sonstiges", category_id=sonstiges, original_filename=f"alt-projekt.{art}",
                            stored_filename=f"alt.{art}", content_type=typ, file_size=len(daten))
        o = PropertyDocument(property_id=objekt.id, category_id=kategorie.id, original_filename=f"alt-objekt.{art}",
                             stored_filename=f"alt.{art}", content_type=typ, file_size=len(daten))
        db.add_all([c, p, o]); db.flush()
        alt[art] = {"kunde": c.id, "projekt": p.id, "objekt": o.id}
    return {"kunde": kunde.id, "projekt": projekt.id, "objekt": objekt.id, "kategorie": kategorie.id, "alt": alt,
            "buero": k.cookies(bea), "monteurin": k.cookies(monteurin)}


DATEIEN = [("plan.svg", SVG, "image/svg+xml"), ("plan.html", HTML, "text/html"), ("foto.jpg", None, "image/jpeg"),
           ("scan.pdf", PDF, "application/pdf")]


async def _hochladen(tab, url: str, extra: dict, zusatz: str) -> dict:
    """Lädt die vier Dateien wie der Browser hoch (FormData mit der Angabe des Browsers); Rückgabe: Name -> Antwort. Der Dateiname
    trägt die Ablage (plan-kunde.svg), damit jeder Download eine eigene Datei ergibt."""
    ergebnis = {}
    for name, daten, typ in DATEIEN:
        daten = daten if daten is not None else _foto()
        datei = name.replace(".", f"-{zusatz}.")
        felder = "".join(f"fd.append({json.dumps(k)},{json.dumps(v)});" for k, v in extra.items())
        ergebnis[name] = await tab.js(
            f"(async()=>{{const fd=new FormData();{felder}"
            f"fd.append('file',new Blob([new Uint8Array({json.dumps(list(daten))})],{{type:{json.dumps(typ)}}}),{json.dumps(datei)});"
            f"const r=await fetch({json.dumps(url)},{{method:'POST',body:fd}});return r.json()}})()")
    return ergebnis


async def _xss(tab) -> str | None:
    return await tab.js("localStorage.getItem('dkXss')")


async def _direkt(tab, pfad: str, download: Path, datei: str | None = None) -> dict:
    """Öffnet pfad direkt im Tab (wie "Öffnen" in einem neuen Tab) und meldet, was der Browser daraus machte: download = die Namen der
    Downloads, die der Tab dabei begann (Page.downloadWillBegin), datei_da = ob datei danach im Download-Ordner geschrieben ist. Mit
    datei wird darauf gewartet (Chrome prüft HTML-Downloads und benennt erst danach um), ohne eine Sekunde."""
    def stand():
        # Chrome legt Zwischendateien an (.crdownload, downloads.htm) und entfernt sie gleich wieder -- eine, die zwischen dem
        # Auflisten und dem Lesen verschwindet, zählt nicht (Nachtrag 1.8.101: daran brach der Lauf nach Regel 26 zu 1.8.104 ab).
        out = {}
        for d in download.iterdir():
            try:
                out[d.name] = d.stat().st_mtime_ns
            except FileNotFoundError:
                pass
        return out

    vorher, marke = stand(), len(tab.downloads)
    antwort = await tab.cmd("Page.navigate", url=tab.base + pfad)
    for runde in range(50):
        await asyncio.sleep(0.2)
        await tab.cmd("Runtime.evaluate", expression="0")  # liest die Ereignisse ab
        jetzt = stand()
        if datei is None and runde >= 4:
            break
        if datei is not None and jetzt.get(datei) not in (None, vorher.get(datei)):
            break
    await asyncio.sleep(0.3)
    seite = await tab.js("({typ:document.contentType,pfad:location.pathname,"
                         "bild:document.images.length===1&&document.images[0].naturalWidth>0})") or {}
    return {"abgebrochen": antwort.get("errorText") == "net::ERR_ABORTED", "typ": seite.get("typ"),
            "hier": seite.get("pfad") == pfad.split("?")[0], "bild": seite.get("bild"),
            "download": [d["name"] for d in tab.downloads[marke:]],
            "datei_da": datei is not None and stand().get(datei) not in (None, vorher.get(datei))}


async def _download_pruefen(tab, p, titel: str, pfad: str, download: Path, datei: str) -> None:
    e = await _direkt(tab, pfad, download, datei)
    p.pruefe(f"{titel}: Download, nicht angezeigt", [e["abgebrochen"], e["hier"], e["download"], e["datei_da"]],
             [True, False, [datei], True])


async def _ablage_pruefen(tab, p, titel: str, ansicht: str, bereit: str, eintraege: dict, zusatz: str, view, download: Path, *,
                          vorschau: bool) -> None:
    """eintraege: Name -> ID; view(id) -> Adresse. Prüft die Liste (Öffnen, Vorschaubild) und jede Adresse direkt."""
    await tab.oeffnen(ansicht, bereit)
    await tab.warte_auf_neu_geladene_liste()
    links = await tab.js("[...document.querySelectorAll('a')].map(a=>a.getAttribute('href')).filter(h=>h&&h.includes('/view'))")
    p.pruefe(f"{titel}: 'Öffnen' nur bei Foto und PDF",
             sorted(n for n, i in eintraege.items() if view(i) in (links or [])), ["foto.jpg", "scan.pdf"])
    bilder = await tab.js("[...document.querySelectorAll('img')].filter(i=>(i.getAttribute('src')||'').includes('/view'))"
                          ".map(i=>[i.getAttribute('src'),i.complete&&i.naturalWidth>0])")
    p.pruefe(f"{titel}: Vorschaubild nur beim Foto, geladen" if vorschau else f"{titel}: keine Vorschaubilder", bilder,
             [[view(eintraege["foto.jpg"]), True]] if vorschau else [])
    for name, i in eintraege.items():
        if name in ("plan.svg", "plan.html"):
            await _download_pruefen(tab, p, f"{titel}: {name} direkt geöffnet", view(i), download, name.replace(".", f"-{zusatz}."))
            continue
        soll = {"abgebrochen": False, "typ": "image/jpeg" if name == "foto.jpg" else "application/pdf", "hier": True,
                "bild": name == "foto.jpg", "download": [], "datei_da": False}
        p.pruefe(f"{titel}: {name} direkt geöffnet: angezeigt", await _direkt(tab, view(i), download), soll)
    await tab.oeffnen(ansicht, bereit)
    p.pruefe(f"{titel}: kein Skript aus einer Datei gelaufen", await _xss(tab), None)


async def pruefen(tab, seed, p):
    download = tab.shots.parent / "downloads"
    download.mkdir(exist_ok=True)
    await tab.cmd("Page.setDownloadBehavior", behavior="allow", downloadPath=str(download))
    await tab.anmelden(seed["buero"])
    alt = seed["alt"]

    # --- Kundenakte ---------------------------------------------------------------------------------------------------
    kid = seed["kunde"]
    bereit_kunde = "document.getElementById('lastName')?.value==='Dateien'"
    await tab.oeffnen(f"/customers/{kid}", bereit_kunde)
    await tab.js("localStorage.removeItem('dkXss'); true")
    neu = await _hochladen(tab, f"/api/customers/{kid}/documents", {"category": "Sonstiges"}, "kunde")
    p.pruefe("Kundenakte: Typ vom Server bestimmt", {n: [d.get("content_type"), d.get("can_preview")] for n, d in neu.items()},
             {"plan.svg": ["application/octet-stream", False], "plan.html": ["application/octet-stream", False],
              "foto.jpg": ["image/jpeg", True], "scan.pdf": ["application/pdf", True]})
    eintraege = {n: d["id"] for n, d in neu.items()}
    await _ablage_pruefen(tab, p, "Kundenakte", f"/customers/{kid}",
                          bereit_kunde + "&&document.querySelectorAll('#customerDocuments .doc').length===6", eintraege, "kunde",
                          lambda i: f"/api/customer-documents/{i}/view", download, vorschau=True)
    await tab.bild("kundenakte")
    for art in ("svg", "html"):
        await _download_pruefen(tab, p, f"Kundenakte: Eintrag von vor 1.8.101 ({art}, Typ des Browsers gespeichert) direkt geöffnet",
                                f"/api/customer-documents/{alt[art]['kunde']}/view", download, f"alt-kunde.{art}")

    # --- Projektmappe -------------------------------------------------------------------------------------------------
    pid = seed["projekt"]
    neu = await _hochladen(tab, f"/api/projects/{pid}/documents", {"category": "Sonstiges"}, "projekt")
    eintraege = {n: d["id"] for n, d in neu.items()}
    await _ablage_pruefen(tab, p, "Projektmappe", f"/projects/{pid}#sec-files",
                          "document.querySelectorAll('#documents .doc').length===6", eintraege, "projekt",
                          lambda i: f"/api/project-documents/{i}/view", download, vorschau=True)
    await tab.bild("projektmappe")
    for art in ("svg", "html"):
        await _download_pruefen(tab, p, f"Projektmappe: Eintrag von vor 1.8.101 ({art}) direkt geöffnet",
                                f"/api/project-documents/{alt[art]['projekt']}/view", download, f"alt-projekt.{art}")

    # --- Objekt (Büro) ---------------------------------------------------------------------------------------------------
    oid = seed["objekt"]
    neu = await _hochladen(tab, f"/api/properties/{oid}/documents", {"category_id": str(seed["kategorie"])}, "objekt")
    eintraege = {n: d["id"] for n, d in neu.items()}
    p.pruefe("Objekt: Foto als JPEG abgelegt, SVG/HTML ohne Typ",
             {n: d.get("content_type") for n, d in neu.items()},
             {"plan.svg": "application/octet-stream", "plan.html": "application/octet-stream", "foto.jpg": "image/jpeg",
              "scan.pdf": "application/pdf"})
    await _ablage_pruefen(tab, p, "Objekt", f"/properties/{oid}", "document.querySelectorAll('#propertyDocRows tr').length===6",
                          eintraege, "objekt", lambda i: f"/api/property-documents/{i}/view", download, vorschau=False)
    await tab.bild("objekt")
    for art in ("svg", "html"):
        await _download_pruefen(tab, p, f"Objekt: Eintrag von vor 1.8.101 ({art}) direkt geöffnet",
                                f"/api/property-documents/{alt[art]['objekt']}/view", download, f"alt-objekt.{art}")

    # --- Logo -----------------------------------------------------------------------------------------------------------
    logo = await tab.js("(async()=>{const fd=new FormData();"
                        f"fd.append('file',new Blob([new Uint8Array({json.dumps(list(SVG))})],{{type:'image/svg+xml'}}),'logo.svg');"
                        "const r=await fetch('/api/settings/general/sidebar-logo',{method:'POST',body:fd});return r.status})()")
    p.pruefe("Logo: SVG hochgeladen", logo, 200)
    await tab.oeffnen(f"/customers/{kid}", bereit_kunde)
    sichtbar = await tab.warten("(()=>{const i=document.querySelector('.app-sidebar-logo');"
                                "return !!i&&i.complete&&i.naturalWidth>0})()", 10)
    p.pruefe("Logo: SVG in der Seitenleiste als Bild sichtbar", sichtbar, True)
    await tab.bild("logo_seitenleiste")
    src = await tab.js("document.querySelector('.app-sidebar-logo')?.getAttribute('src')")
    await _download_pruefen(tab, p, "Logo: direkt geöffnet", src or "/api/settings/general/sidebar-logo", download, "sidebar-logo.svg")
    await tab.oeffnen(f"/customers/{kid}", bereit_kunde)
    p.pruefe("Logo: kein Skript gelaufen", await _xss(tab), None)
    p.pruefe("JS-Fehler (Büro)", tab.fehler, [])

    # --- /mobil/objekt als Monteurin ----------------------------------------------------------------------------------
    await tab.anmelden(seed["monteurin"])
    await tab.fenster(412, 900, mobil=True)
    basis = f"/api/field-view/properties/{oid}/documents/property"
    bereit_mobil = "document.querySelectorAll('#documentsList .doc-row').length===6"
    await tab.oeffnen(f"/mobil/objekt/{oid}", bereit_mobil)
    ansehen = await tab.js("[...document.querySelectorAll('#documentsList a')].filter(a=>a.textContent==='Ansehen')"
                           ".map(a=>a.getAttribute('href'))")
    p.pruefe("/mobil/objekt: 'Ansehen' nur bei Foto und PDF", sorted(ansehen or []),
             sorted(f"{basis}/{eintraege[n]}/view" for n in ("foto.jpg", "scan.pdf")))
    await tab.bild("mobil_objekt")
    for name in ("plan.svg", "plan.html"):
        await _download_pruefen(tab, p, f"/mobil/objekt: {name} direkt geöffnet", f"{basis}/{eintraege[name]}/view", download,
                                name.replace(".", "-objekt."))
    p.pruefe("/mobil/objekt: foto.jpg direkt geöffnet: angezeigt", await _direkt(tab, f"{basis}/{eintraege['foto.jpg']}/view", download),
             {"abgebrochen": False, "typ": "image/jpeg", "hier": True, "bild": True, "download": [], "datei_da": False})
    for art in ("svg", "html"):
        await _download_pruefen(tab, p, f"/mobil/objekt: Eintrag von vor 1.8.101 ({art}) direkt geöffnet",
                                f"{basis}/{alt[art]['objekt']}/view", download, f"alt-objekt.{art}")
    await tab.oeffnen(f"/mobil/objekt/{oid}", bereit_mobil)
    p.pruefe("/mobil/objekt: kein Skript gelaufen", await _xss(tab), None)
    p.pruefe("JS-Fehler (Monteurin)", tab.fehler, [])
    print("Downloads:", sorted(x.name for x in download.iterdir()), flush=True)


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="10:00"))
