"""Klicktest: unterschriebene Abschrift und lesbare Fehlermeldungen der Auftragsseite (1.8.35).

    Klara Kundin  auf dem Gerät unterschrieben: Karte zeigt "Unterschriebene Abschrift" mit eigener Prüfsumme
                  (anders als die der Fassung), "Abschrift öffnen" liefert genau das PDF aus der Ablage; Versand
                  an einen SMTP-Empfänger im Skript: Knopf "Abschrift senden", Anhang = Abschrift
                  (…_unterschrieben.pdf), Verlauf nennt "Fassung 1 · unterschrieben". Hell, 1280 px.
    Lena Altbestand  Unterschrift wie vor 1.8.35 (ohne Abschrift): Karte sagt "noch nicht erzeugt"; der erste
                  Versand holt sie nach, danach "Abschrift öffnen", Anhang = die nachgeholte Abschrift.
    Paul Papier   Foto des unterschriebenen Papiers: Karte mit "Scan öffnen" und Abschrift (PDF); dunkel, 412 px
                  ohne seitliches Scrollen.
    Fehler        Auftragsdatum geleert und gespeichert (422), Abschlag mit "1.234,56" (422): lesbare Meldung mit
                  Feldname statt "[object Object]". Otto: Seite offen, Vertrag inzwischen anderswo unterschrieben,
                  dann "Neue Fassung anlegen" (409): die Meldung des Servers.
    Monteur       Abschrift aus der Ablage: 403.

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_vertrag_abschrift.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID
beenden): siehe scripts/cdp_klicktest.py.
"""

import base64
import hashlib
import socket
import sys
from io import BytesIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402
from klicktest_versandprotokoll import POSTFACH, _smtp_starten  # noqa: E402


def _png() -> bytes:
    from PIL import Image, ImageDraw

    image = Image.new("RGBA", (300, 100), (255, 255, 255, 0))
    ImageDraw.Draw(image).line([(20, 70), (90, 20), (160, 75), (280, 30)], fill=(17, 17, 17, 255), width=4)
    buf = BytesIO()
    image.save(buf, "PNG")
    return buf.getvalue()


def _foto() -> bytes:
    """Foto des unterschriebenen Papiers (hochkant, JPEG)."""
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (600, 850), "white")
    draw = ImageDraw.Draw(image)
    for y in range(80, 700, 40):
        draw.line([(60, y), (540, y)], fill=(120, 120, 120), width=2)
    draw.line([(80, 780), (200, 740), (320, 790)], fill=(10, 10, 10), width=4)
    buf = BytesIO()
    image.save(buf, "JPEG", quality=85)
    return buf.getvalue()


def befuellen(db, k):
    from datetime import date, time as dt_time
    from decimal import Decimal

    from sqlalchemy import update

    from app.mobile_settings import update_mobile_settings

    from app.berlin_time import berlin_today
    from app.contract_signatures import record_paper_signature, sign_contract_on_device
    from app.contract_templates import save_template
    from app.contract_versions import freeze_contract
    from app.email_sending import update_smtp_settings
    from app.models import AppUser, Customer, OrderContractSignature, Project, Quote, QuoteItem
    from app.orders import create_order_from_quote, load_order
    from app.project_pipeline_columns import default_pipeline_column_id

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        smtp_port = s.getsockname()[1]
    update_smtp_settings(db, host="127.0.0.1", port=smtp_port, username="buero", encryption="none",
                         sender_email="buero@klicktest.example", sender_name="Klicktest GmbH", password="pw")
    bert = AppUser(username="bert", display_name="Bert Büro", role="buero_auftrag", password_hash=k.passwort())
    max_ = AppUser(username="max", display_name="Max Monteur", role="field", password_hash=k.passwort())
    db.add_all([bert, max_]); db.flush()
    # /mobil meldet den Monteur nach Feierabend ab (Vorgabe 19:00) -- sonst hinge das Ergebnis von der Uhrzeit ab.
    update_mobile_settings(db, dt_time(23, 59))
    save_template(db, "bgb_vob_c_4_5", title="Bauvertrag {auftragsnummer}", sections=[
        {"heading": "§ 1 Parteien", "body_text": "Zwischen {firmenname} und {kundenname}."},
        {"heading": "§ 2 Vergütung", "body_text": "Auftragssumme {auftragssumme_brutto}."},
        {"heading": "Vorzeitiger Beginn", "body_text": "Ich verlange, dass vor Ende der Widerrufsfrist begonnen wird.",
         "consumer_only": True, "with_checkbox": True, "early_start": True},
    ], reviewed_on=berlin_today(), reviewed_by="RA Beispiel")
    png = _png()

    def auftrag(name, nr):
        kunde = Customer(name=name, last_name=name, is_consumer=True, email=f"{name.split()[0].lower()}@klicktest.example",
                         street="Dachweg 1", postal_code="52531", city="Übach")
        db.add(kunde); db.flush()
        projekt = Project(project_number=f"P-KT-{nr}", name=f"Dach {nr}", customer_id=kunde.id,
                          pipeline_column_id=default_pipeline_column_id(db))
        db.add(projekt); db.flush()
        quote = Quote(quote_number=f"A-KT-{nr}", project_id=projekt.id, title=f"Dachsanierung {nr}",
                      vat_rate=Decimal("19"), status="versendet")
        db.add(quote); db.flush()
        db.add(QuoteItem(quote_id=quote.id, position_number="1", short_text="Eindecken", quantity=Decimal("10"),
                         unit="m²", unit_price=Decimal("50")))
        db.commit()
        order = create_order_from_quote(
            db, quote.id, order_date=date(2026, 10, 1), execution_start=None, execution_end=None,
            caseworker_employee_id=None, project_manager_employee_id=None, payment_terms="14 Tage netto", remarks=None,
        )
        version = freeze_contract(db, load_order(db, order.id), attachment="aktuell", user_name="Bert Büro")
        return order.id, version.id, version.sent_document.sha256

    def geraet(order_id, version_id, sha):
        sign_contract_on_device(db, load_order(db, order_id), version_id=version_id, pdf_sha256=sha,
                                checkboxes={"abschnitt-3": True}, customer_name="Klara Kundin", customer_png=png,
                                company_name="Bert Büro", company_png=png, user_name="Bert Büro")

    klara = auftrag("Klara Kundin", "1")
    geraet(*klara)
    lena = auftrag("Lena Altbestand", "2")
    geraet(*lena)
    # Stand einer Unterschrift von vor 1.8.35: ohne Abschrift (an der ORM-Sperre vorbei, wie die Migration).
    db.execute(update(OrderContractSignature).where(OrderContractSignature.version_id == lena[1]).values(copy_document_id=None))
    db.commit()
    paul = auftrag("Paul Papier", "3")
    record_paper_signature(db, load_order(db, paul[0]), version_id=paul[1], pdf_sha256=paul[2], signed_on=berlin_today(),
                           checkboxes={"abschnitt-3": False}, scan_bytes=_foto(), user_name="Bert Büro")
    otto = auftrag("Otto Offen", "4")
    return {"smtp_port": smtp_port, "klara": klara[0], "lena": lena[0], "paul": paul[0], "otto": otto[0],
            "png": "data:image/png;base64," + base64.b64encode(png).decode(),
            "cookies": {"bert": k.cookies(bert), "max": k.cookies(max_)}}


async def pruefen(tab, seed, p):
    server = _smtp_starten(seed["smtp_port"])
    try:
        await _pruefen(tab, seed, p)
    finally:
        server.shutdown()


KARTE = "document.getElementById('contractCard').textContent"
STATUS = "document.getElementById('contractStatus').textContent"
SENDEN = "document.querySelector('#contractBody .contract-send button')"


def _vertrag(order_id) -> str:
    return f"fetch('/api/orders/{order_id}/contract').then(r=>r.json()).then(d=>d.contract)"


def _sha_js(url: str) -> str:
    return (f"(async()=>{{const r=await fetch('{url}');const h=await crypto.subtle.digest('SHA-256',await r.arrayBuffer());"
            "return [r.status,r.headers.get('content-type'),[...new Uint8Array(h)].map(b=>b.toString(16).padStart(2,'0')).join('')]})()")


def _anhang(mail):
    for part in mail["message"].walk():
        if part.get_content_disposition() == "attachment":
            return part.get_filename(), hashlib.sha256(part.get_payload(decode=True)).hexdigest()
    return None, None


async def _pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument",
                  source="window.confirm=()=>true;window.alert=m=>console.error('alert(): '+m)")
    await tab.anmelden(seed["cookies"]["bert"])
    await tab.fenster(1280, 960)
    klara, lena, paul, otto = seed["klara"], seed["lena"], seed["paul"], seed["otto"]

    # --- Klara: Abschrift aus Fassung und Unterschriftsblatt --------------------------------------------
    await tab.oeffnen(f"/orders/{klara}", "document.readyState==='complete'")
    await tab.js("localStorage.setItem('erp_theme','light'); true")
    await tab.oeffnen(f"/orders/{klara}", f"({KARTE}||'').includes('Unterschriebene Abschrift:')")
    vertrag = await tab.js(_vertrag(klara))
    kopie, fassung = vertrag["signature"]["copy_document"], vertrag["versions"][0]["document"]
    karte = await tab.js(KARTE) or ""
    p.pruefe("Klara: Karte zeigt Abschrift mit eigener Prüfsumme",
             [f"Prüfsumme {kopie['sha256'][:12]}…" in karte, "Abschrift öffnen" in karte, kopie["sha256"] != fassung["sha256"]],
             [True, True, True])
    p.pruefe("Klara: 'Abschrift öffnen' zeigt auf die Ablage",
             await tab.js(f"!!document.querySelector('#contractCard a[href=\"/api/sent-documents/{kopie['id']}/file\"]')"), True)
    p.pruefe("Klara: Abschrift ist PDF, SHA-256 wie in der Ablage",
             await tab.js(_sha_js(f"/api/sent-documents/{kopie['id']}/file")), [200, "application/pdf", kopie["sha256"]])
    p.pruefe("Klara: Versand-Überschrift und Knopf",
             ["Unterschriebene Abschrift (Fassung 1) per E-Mail senden" in karte, await tab.js(f"{SENDEN}.textContent")],
             [True, "✉️ Abschrift senden"])
    await tab.js(f"{SENDEN}.click(); true")
    await tab.warten(f"{STATUS}==='Versendet.'", timeout=30)
    p.pruefe("Klara: versendet", await tab.js(STATUS), "Versendet.")
    p.pruefe("Klara: eine Mail", len(POSTFACH), 1)
    p.pruefe("Klara: Anhang = Abschrift", _anhang(POSTFACH[0]) if POSTFACH else None,
             (kopie["filename"], kopie["sha256"]))
    p.pruefe("Klara: Dateiname der Abschrift", kopie["filename"].endswith("_Fassung_1_unterschrieben.pdf"), True)
    await tab.warten("document.querySelectorAll('#contractDispatchHistory .dh-row').length===1")
    p.pruefe("Klara: Verlauf nennt 'Fassung 1 · unterschrieben'",
             "· Fassung 1 · unterschrieben" in (await tab.js("document.querySelector('#contractDispatchHistory .dh-row').textContent") or ""), True)
    await tab.js("document.getElementById('contractCard').scrollIntoView(); true")
    await tab.bild("klara_abschrift_hell")
    p.pruefe("Klara: JS-Fehler", tab.fehler, [])

    # --- Lena: Unterschrift von vor 1.8.35 ------------------------------------------------------------
    await tab.oeffnen(f"/orders/{lena}", f"({KARTE}||'').includes('Unterschriebene Abschrift:')")
    p.pruefe("Lena: Abschrift noch nicht erzeugt", "noch nicht erzeugt" in (await tab.js(KARTE) or ""), True)
    await tab.js(f"{SENDEN}.click(); true")
    await tab.warten(f"{STATUS}==='Versendet.'", timeout=30)
    vertrag = await tab.js(_vertrag(lena))
    kopie = vertrag["signature"]["copy_document"]
    p.pruefe("Lena: erster Versand holt die Abschrift nach", kopie is not None and "Abschrift öffnen" in (await tab.js(KARTE) or ""), True)
    p.pruefe("Lena: Anhang = nachgeholte Abschrift", _anhang(POSTFACH[1]) if len(POSTFACH) > 1 else None,
             (kopie["filename"], kopie["sha256"]) if kopie else None)
    p.pruefe("Lena: JS-Fehler", tab.fehler, [])

    # --- Paul: Foto des Papiers, dunkel, 412 px --------------------------------------------------------
    await tab.js("localStorage.setItem('erp_theme','dark'); true")
    await tab.fenster(412, 900, mobil=True)
    await tab.oeffnen(f"/orders/{paul}", f"({KARTE}||'').includes('Unterschriebene Abschrift:')")
    p.pruefe("Paul: dunkel", await tab.js("document.documentElement.getAttribute('data-theme')"), "dark")
    vertrag = await tab.js(_vertrag(paul))
    kopie = vertrag["signature"]["copy_document"]
    karte = await tab.js(KARTE) or ""
    p.pruefe("Paul: Scan und Abschrift auf der Karte", ["Scan öffnen" in karte, "Abschrift öffnen" in karte], [True, True])
    p.pruefe("Paul: Abschrift ist PDF", await tab.js(_sha_js(f"/api/sent-documents/{kopie['id']}/file")),
             [200, "application/pdf", kopie["sha256"]])
    p.pruefe("Paul: 412 px ohne seitliches Scrollen",
             await tab.js("document.documentElement.scrollWidth<=document.documentElement.clientWidth+1"), True)
    await tab.js("document.getElementById('contractCard').scrollIntoView(); true")
    await tab.bild("paul_abschrift_dunkel_412")
    p.pruefe("Paul: JS-Fehler", tab.fehler, [])
    await tab.fenster(1280, 960)
    await tab.js("localStorage.setItem('erp_theme','light'); true")

    # --- Fehlermeldungen: 422 -------------------------------------------------------------------------
    await tab.oeffnen(f"/orders/{klara}", "!!document.getElementById('orderDate').value")
    await tab.js("document.getElementById('orderDate').value=''; document.querySelector('[onclick=\"saveOrder()\"]').click(); true")
    await tab.warten("document.getElementById('saveStatus').textContent.startsWith('Fehler')")
    p.pruefe("422 Auftragsdatum: lesbar", await tab.js("document.getElementById('saveStatus').textContent"),
             "Fehler: Bitte die Eingabe prüfen – Auftragsdatum ist kein gültiges Datum.")
    await tab.js("document.getElementById('newInvoiceType').value='abschlag_pauschal';toggleNewInvoiceFields();"
                 "document.getElementById('newLumpSum').value='1.234,56';"
                 "document.querySelector('[onclick=\"createNewInvoice()\"]').click(); true")
    await tab.warten("document.getElementById('newInvoiceStatus').textContent.startsWith('Fehler')")
    p.pruefe("422 Abschlag: lesbar", await tab.js("document.getElementById('newInvoiceStatus').textContent"),
             "Fehler: Bitte die Eingabe prüfen – Betrag netto muss eine Zahl sein (ohne Tausenderpunkt).")
    await tab.js("document.getElementById('saveStatus').scrollIntoView({block:'center'}); true")
    await tab.bild("fehler_422")
    p.pruefe("422: JS-Fehler", tab.fehler, [])

    # --- Fehlermeldungen: 409 (Seite veraltet) ----------------------------------------------------------
    await tab.oeffnen(f"/orders/{otto}", "!!document.querySelector('[onclick^=\"startNewContractVersion\"]')")
    unterschrieben = await tab.js(
        f"(async()=>{{const c=await {_vertrag(otto)};const v=c.versions[0];"
        f"const r=await fetch('/api/orders/{otto}/contract/sign',{{method:'POST',headers:{{'Content-Type':'application/json'}},"
        "body:JSON.stringify({version_id:v.id,pdf_sha256:v.document.sha256,checkboxes:{'abschnitt-3':false},"
        f"customer_name:'Otto Offen',customer_signature_png_base64:'{seed['png']}',company_name:'Bert Büro',"
        f"company_signature_png_base64:'{seed['png']}'}})}});return r.status}})()")
    p.pruefe("409: anderswo unterschrieben", unterschrieben, 200)
    await tab.js("document.querySelector('[onclick^=\"startNewContractVersion\"]').click(); true")
    await tab.warten(f"{STATUS}.startsWith('Fehler')")
    meldung = await tab.js(STATUS) or ""
    p.pruefe("409 Neue Fassung: Meldung des Servers",
             [meldung.startswith("Fehler: Der Vertrag ist unterschrieben – eine neue Fassung gibt es danach nicht."), "[object Object]" in meldung],
             [True, False])
    p.pruefe("409: JS-Fehler", tab.fehler, [])

    # --- Monteur ---------------------------------------------------------------------------------------
    await tab.anmelden(seed["cookies"]["max"])
    await tab.oeffnen("/mobil", "document.readyState==='complete'")
    p.pruefe("Monteur: Abschrift 403", await tab.js(f"fetch('/api/sent-documents/{kopie['id']}/file').then(r=>r.status)"), 403)


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung="Unterschriebene Abschrift und Fehlermeldungen (1.8.35)"))
