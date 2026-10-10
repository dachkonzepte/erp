"""Klicktest: Versandverlauf, Zustellung nachtragen, Checkliste per E-Mail (1.8.20, Stufe 2, Runde 2a-3b).

Sendet über die echten Seiten an einen kleinen SMTP-Empfänger im Skript (aus
klicktest_versandprotokoll.py, nichts verlässt den Rechner) und prüft:

- Rechnung: Versandverlauf statt "zuletzt versendet" (leer, dann nach dem Versand eine Zeile mit
  PDF und dem Hinweis auf die abgelegte Fassung); "Zustellung nachtragen" ohne Notiz → Hinweis, mit
  Weg, Notiz, Empfänger und Beleg-Foto (Datei-Upload über CDP) → zweite Zeile mit Beleg, der Beleg
  kommt als Bild zurück.
- Auftrag und Angebot: Verlauf da, nach dem Versand eine Zeile.
- Mahnwesen: "Verlauf" klappt die Zeile auf.
- Checkliste mit 20 Fotos (Büro): Versandbereich mit vorbelegtem Kunden, Versand, der Anhang in der
  Mail ist ein PDF unter 3.000.000 Bytes, der PDF-Knopf liefert weiter volle Auflösung (über 3 MB);
  Monteur: kein Versandbereich, keine JS-Fehler; 412 px ohne seitliches Scrollen.
- /versandprotokoll: Filter Checkliste, nachgetragene Zustellung mit "Zugestellt am" und Beleg.
- Hell und dunkel auf der Rechnung.

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_versandverlauf.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die
eigene PID beenden): siehe scripts/cdp_klicktest.py.
"""

import socket
import sys
import tempfile
from io import BytesIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402
from klicktest_versandprotokoll import POSTFACH, _smtp_starten  # noqa: E402

GRENZE = 3_000_000


def _foto(seed: int) -> bytes:
    import random

    from PIL import Image
    rng = random.Random(seed)
    klein = Image.frombytes("RGB", (200, 150), rng.randbytes(200 * 150 * 3))
    buf = BytesIO()
    klein.resize((2000, 1500), Image.BILINEAR).save(buf, format="JPEG", quality=92)
    return buf.getvalue()


def _beleg() -> bytes:
    from PIL import Image
    buf = BytesIO()
    Image.new("RGB", (600, 400), (235, 235, 225)).save(buf, format="JPEG")
    return buf.getvalue()


def befuellen(db, k):
    from datetime import date, timedelta
    from decimal import Decimal

    from PIL import Image

    from app.checklist_templates import add_field, create_template, publish_draft
    from app.checklists import add_attachment, complete_checklist, create_checklist
    from app.email_sending import update_smtp_settings
    from app.invoices import create_schlussrechnung, finalize_and_send_invoice
    from app.models import AppUser, Customer, Employee, Order, OrderItem, Project, Quote, QuoteItem
    from app.project_pipeline_columns import default_pipeline_column_id
    from app.reminders import compute_reminder_status, create_reminder, ensure_default_reminder_levels, finalize_and_send_reminder

    def festschreiben(inv):  # seit 1.8.74: Leistungszeitraum Pflicht beim Festschreiben
        from app.invoices import update_invoice_header
        if inv.service_period_start is None:
            update_invoice_header(db, inv, service_period_start=date(2026, 9, 1), service_period_end=date(2026, 9, 30))
        return finalize_and_send_invoice(db, inv)

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        smtp_port = s.getsockname()[1]
    update_smtp_settings(db, host="127.0.0.1", port=smtp_port, username="buero", encryption="none",
                         sender_email="buero@klicktest.example", sender_name="Klicktest GmbH", password="pw")

    kunde = Customer(name="Verlauf Kunde", last_name="Verlauf Kunde", email="kunde@klicktest.example")
    db.add(kunde); db.flush()
    projekt = Project(project_number="P-VL-1", name="Verlauf", customer_id=kunde.id, pipeline_column_id=default_pipeline_column_id(db))
    db.add(projekt); db.flush()
    angebot = Quote(quote_number="A-VL-1", project_id=projekt.id, title="Dachsanierung", vat_rate=Decimal("19.00"), status="versendet")
    db.add(angebot); db.flush()
    db.add(QuoteItem(quote_id=angebot.id, sort_order=10, position_number="1", short_text="Dacheindeckung",
                     quantity=Decimal("10"), unit="m²", unit_price=Decimal("50")))
    auftrag = Order(order_number="AUF-VL-1", project_id=projekt.id, source_quote_id=angebot.id, quote_number_snapshot="A-VL-1",
                    title="Dachsanierung", vat_rate=Decimal("19.00"), customer_name="Verlauf Kunde", customer_number="K-VL-1")
    db.add(auftrag); db.flush()
    db.add(OrderItem(order_id=auftrag.id, sort_order=10, position_number="1", short_text="Dacheindeckung",
                     quantity=Decimal("10"), unit="m²", unit_price=Decimal("50")))
    db.commit()
    rechnung = festschreiben(create_schlussrechnung(db, auftrag, due_date=date.today() - timedelta(days=20)))
    ensure_default_reminder_levels(db)
    mahnung = finalize_and_send_reminder(db, create_reminder(db, rechnung, compute_reminder_status(db, rechnung)["next_level"]))

    max_ma = Employee(first_name="Max", last_name="Monteur", employee_group="angestellt", hourly_wage="30", weekly_hours="40", active=True)
    db.add(max_ma); db.flush()
    buero = AppUser(username="bea", display_name="Bea Büro", role="buero_auftrag", password_hash=k.passwort())
    monteur = AppUser(username="max", display_name="Max Monteur", role="field", employee_id=max_ma.id, password_hash=k.passwort())
    db.add_all([buero, monteur]); db.commit()

    t = create_template(db, label="Fotodokumentation", contexts=["auftrag"])
    add_field(db, t["draft_version_id"], {"field_type": "foto", "label": "Fotos", "field_key": "fotos",
                                          "multiple": True, "min_count": 1, "max_count": 20})
    add_field(db, t["draft_version_id"], {"field_type": "unterschrift", "label": "Unterschrift Monteur", "field_key": "sig",
                                          "required": True})
    tpl = publish_draft(db, t["id"])
    c = create_checklist(db, template_id=tpl["id"], context_type="auftrag", order_id=auftrag.id,
                         created_by_employee_id=max_ma.id)
    felder = {f["field_key"]: f["id"] for f in c["fields"]}
    for n in range(20):
        add_attachment(db, c["id"], felder["fotos"], _foto(n), created_by_employee_id=max_ma.id)
    sig = BytesIO()
    Image.new("RGB", (300, 120), (20, 20, 20)).save(sig, format="PNG")
    add_attachment(db, c["id"], felder["sig"], sig.getvalue(), signer_name="Max Monteur", created_by_employee_id=max_ma.id)
    complete_checklist(db, c["id"], completed_by_employee_id=max_ma.id)

    return {"smtp_port": smtp_port, "rechnung": rechnung.id, "auftrag": auftrag.id, "angebot": angebot.id, "mahnung": mahnung.id,
            "checkliste": c["id"], "cookies": {"buero": k.cookies(buero), "monteur": k.cookies(monteur)}}


def _anhang(mail):
    for part in mail["message"].walk():
        if part.get_content_disposition() == "attachment":
            return part.get_payload(decode=True)
    return None


async def pruefen(tab, seed, p):
    server = _smtp_starten(seed["smtp_port"])
    try:
        await _pruefen(tab, seed, p)
    finally:
        server.shutdown()


async def _datei_setzen(tab, selector: str, pfad: Path) -> None:
    doc = await tab.cmd("DOM.getDocument", depth=1)
    node = await tab.cmd("DOM.querySelector", nodeId=doc["root"]["nodeId"], selector=selector)
    await tab.cmd("DOM.setFileInputFiles", files=[str(pfad)], nodeId=node["nodeId"])


async def _pruefen(tab, seed, p):
    await tab.anmelden(seed["cookies"]["buero"])
    H = "invoiceDispatchHistory"

    # --- Rechnung: Verlauf, Versand, Zustellung nachtragen (Theme erst auf der App-Seite setzbar)
    await tab.oeffnen(f"/invoices/{seed['rechnung']}", f"!!document.querySelector('#{H} .dh-head')")
    await tab.js("localStorage.setItem('erp_theme','light'); true")
    await tab.oeffnen(f"/invoices/{seed['rechnung']}", f"!!document.querySelector('#{H} .dh-head')")
    p.pruefe("Rechnung: Verlauf leer", "Noch nicht versendet oder zugestellt." in (await tab.js(f"document.getElementById('{H}').textContent") or ""), True)
    p.pruefe("Rechnung: kein 'Zuletzt per E-Mail'", "Zuletzt per E-Mail" in (await tab.js("document.body.textContent") or ""), False)
    await tab.js("document.querySelector('button[onclick^=\"sendInvoiceEmail\"]').click(); true")
    await tab.warten(f"document.querySelectorAll('#{H} .dh-row').length===1")
    zeile = await tab.js(f"document.querySelector('#{H} .dh-row').textContent") or ""
    p.pruefe("Rechnung: Verlaufszeile SMTP, gesendet, An", all(x in zeile for x in ("SMTP", "Gesendet", "kunde@klicktest.example", "Bea Büro")), True)
    p.pruefe("Rechnung: Hinweis auf die abgelegte Fassung", "verwenden die abgelegte Fassung vom" in (await tab.js(f"document.getElementById('{H}').textContent") or ""), True)
    p.pruefe("Rechnung: eine Mail", len(POSTFACH), 1)

    await tab.js(f"document.getElementById('{H}-toggle').click(); true")
    p.pruefe("Nachtragen: Formular sichtbar", await tab.js(f"getComputedStyle(document.getElementById('{H}-form')).display"), "grid")
    await tab.js(f"document.getElementById('{H}-save').click(); true")
    p.pruefe("Nachtragen ohne Notiz: Hinweis", await tab.js(f"document.getElementById('{H}-msg').textContent"),
             "Bitte in der Notiz festhalten, wie zugestellt wurde.")
    belegdatei = Path(tempfile.mkdtemp(prefix="klicktest-beleg-")) / "Einlieferungsbeleg.jpg"
    belegdatei.write_bytes(_beleg())
    await _datei_setzen(tab, f"#{H}-file", belegdatei)
    await tab.js(f"document.getElementById('{H}-channel').value='einschreiben';"
                 f"document.getElementById('{H}-recipient').value='Verlauf Kunde, Dachstr. 1';"
                 f"document.getElementById('{H}-note').value='Sendungsnummer RR 1234 5678 9DE';"
                 f"document.getElementById('{H}-save').click(); true")
    await tab.warten(f"document.querySelectorAll('#{H} .dh-row').length===2")
    oben = await tab.js(f"document.querySelector('#{H} .dh-row').textContent") or ""
    p.pruefe("Nachtragen: Zeile mit Weg, Datum, Notiz, Beleg",
             all(x in oben for x in ("Einschreiben", "Zugestellt am", "Sendungsnummer RR 1234 5678 9DE", "Beleg", "PDF")), True)
    beleg = await tab.js(f"(async()=>{{const a=[...document.querySelectorAll('#{H} .dh-links a')].find(x=>x.textContent==='Beleg');"
                         "const r=await fetch(a.href);return [r.status,r.headers.get('content-type'),(await r.arrayBuffer()).byteLength]})()")
    p.pruefe("Nachtragen: Beleg kommt als Bild zurück", beleg, [200, "image/jpeg", len(belegdatei.read_bytes())])
    p.pruefe("Nachtragen: keine Mail", len(POSTFACH), 1)
    p.pruefe("Rechnung: JS-Fehler", tab.fehler, [])
    p.pruefe("Hell: Pille 'Gesendet'", await tab.js(f"getComputedStyle(document.querySelector('#{H} .dh-pill.gesendet')).backgroundColor"), "rgb(234, 245, 239)")
    await tab.js(f"document.getElementById('{H}').scrollIntoView({{block:'start'}}); true")
    await tab.bild("rechnung_verlauf_hell")

    await tab.js("localStorage.setItem('erp_theme','dark'); true")
    await tab.oeffnen(f"/invoices/{seed['rechnung']}", f"document.querySelectorAll('#{H} .dh-row').length===2")
    p.pruefe("Dunkel: Pille 'Gesendet' nicht hell", await tab.js(f"getComputedStyle(document.querySelector('#{H} .dh-pill.gesendet')).backgroundColor"), "rgb(23, 50, 38)")
    await tab.js(f"document.getElementById('{H}').scrollIntoView({{block:'start'}}); true")
    await tab.bild("rechnung_verlauf_dunkel")
    await tab.js("localStorage.setItem('erp_theme','light'); true")

    # --- Auftrag, Angebot
    await tab.oeffnen(f"/orders/{seed['auftrag']}", "!!document.querySelector('#orderDispatchHistory .dh-head')")
    p.pruefe("Auftrag: Verlauf leer", "Noch nicht versendet" in (await tab.js("document.getElementById('orderDispatchHistory').textContent") or ""), True)
    await tab.js("document.querySelector('button[onclick^=\"sendOrderEmail\"]').click(); true")
    await tab.warten("document.querySelectorAll('#orderDispatchHistory .dh-row').length===1")
    p.pruefe("Auftrag: eine Verlaufszeile", await tab.js("document.querySelectorAll('#orderDispatchHistory .dh-row').length"), 1)
    p.pruefe("Auftrag: JS-Fehler", tab.fehler, [])
    await tab.oeffnen(f"/quotes/{seed['angebot']}/edit", "!!document.querySelector('#quoteDispatchHistory .dh-head')")
    await tab.js("document.querySelector('button[onclick^=\"sendQuoteEmail\"]').click(); true")
    await tab.warten("document.querySelectorAll('#quoteDispatchHistory .dh-row').length===1")
    p.pruefe("Angebot: eine Verlaufszeile", await tab.js("document.querySelectorAll('#quoteDispatchHistory .dh-row').length"), 1)
    p.pruefe("Angebot: JS-Fehler", tab.fehler, [])

    # --- Mahnwesen
    mid = seed["mahnung"]
    await tab.oeffnen("/mahnwesen", f"!!document.querySelector('button[onclick=\"toggleReminderHistory({mid})\"]')")
    await tab.js(f"document.querySelector('button[onclick=\"toggleReminderHistory({mid})\"]').click(); true")
    await tab.warten(f"!!document.querySelector('#dh{mid} .dh-head')")
    p.pruefe("Mahnwesen: Verlauf aufgeklappt", "Noch nicht versendet" in (await tab.js(f"document.getElementById('dh{mid}').textContent") or ""), True)
    p.pruefe("Mahnwesen: JS-Fehler", tab.fehler, [])

    # --- Checkliste (Büro)
    cid = seed["checkliste"]
    await tab.oeffnen(f"/checklisten/{cid}", "!!document.querySelector('#clDispatchHistory .dh-head') && document.getElementById('clEmailTo').value!==''")
    p.pruefe("Checkliste: An vorbelegt", await tab.js("document.getElementById('clEmailTo').value"), "kunde@klicktest.example")
    await tab.js("document.getElementById('clSendBtn').click(); true")
    await tab.warten("document.getElementById('clSendStatus').textContent==='Versendet.' || document.getElementById('clSendStatus').textContent.startsWith('Fehler')", timeout=90)
    p.pruefe("Checkliste: versendet", await tab.js("document.getElementById('clSendStatus').textContent"), "Versendet.")
    await tab.warten("document.querySelectorAll('#clDispatchHistory .dh-row').length===1")
    p.pruefe("Checkliste: eine Verlaufszeile", await tab.js("document.querySelectorAll('#clDispatchHistory .dh-row').length"), 1)
    anhang = _anhang(POSTFACH[-1]) if POSTFACH else None
    p.pruefe("Checkliste: Anhang ist ein PDF unter 3.000.000 Bytes", bool(anhang and anhang.startswith(b"%PDF") and len(anhang) <= GRENZE), True)
    voll = await tab.js(f"fetch('/api/checklists/{cid}/pdf').then(r=>r.arrayBuffer()).then(b=>b.byteLength)")
    p.pruefe("Checkliste: PDF-Knopf weiter in voller Auflösung (über 3 MB)", (voll or 0) > GRENZE, True)
    p.pruefe("Checkliste: JS-Fehler", tab.fehler, [])
    await tab.bild("checkliste_versand")

    # --- Versandprotokoll
    await tab.oeffnen("/versandprotokoll?typ=checkliste", "!!document.querySelector('#rows tr td') && !document.querySelector('#rows td.empty')")
    p.pruefe("Protokoll: Filter Checkliste", await tab.js("document.querySelectorAll('#rows tr').length"), 1)
    await tab.oeffnen(f"/versandprotokoll?typ=rechnung&id={seed['rechnung']}", "!!document.querySelector('#rows tr td') && !document.querySelector('#rows td.empty')")
    zeilen = await tab.js("document.getElementById('rows').textContent") or ""
    p.pruefe("Protokoll: Zustellung mit Datum und Beleg", all(x in zeilen for x in ("Einschreiben", "Zugestellt am", "Beleg:", "Einlieferungsbeleg.jpg")), True)
    p.pruefe("Protokoll: JS-Fehler", tab.fehler, [])

    # --- Checkliste als Monteur, 412 px
    await tab.anmelden(seed["cookies"]["monteur"])
    await tab.fenster(412, 900, mobil=True)
    await tab.oeffnen(f"/checklisten/{cid}", "!!document.querySelector('.card h1')")
    p.pruefe("Monteur: kein Versandbereich", await tab.js("!!document.getElementById('sendCard')"), False)
    p.pruefe("Monteur: JS-Fehler", tab.fehler, [])
    await tab.anmelden(seed["cookies"]["buero"])
    await tab.oeffnen(f"/checklisten/{cid}", "!!document.querySelector('#clDispatchHistory .dh-head')")
    p.pruefe("412 px: kein seitliches Scrollen (Checkliste, Büro)", await tab.js("document.documentElement.scrollWidth<=window.innerWidth"), True)
    await tab.js("document.getElementById('sendCard').scrollIntoView({block:'start'}); true")
    await tab.bild("checkliste_412")
    await tab.fenster(1280, 900)


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__))
