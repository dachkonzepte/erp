"""Klicktest: Finanzen und Dashboard zählen nach der Schlussrechnung je Auftrag ihren Zahlbetrag (1.8.91, Nacharbeit R4c Punkt 1).

Zwei Aufträge zu je 10 m² × 50 € (595 € brutto):
    A  Abschlag 4 m² (238 €), davon 100 € bezahlt (offen 138 €); Schlussrechnung 10 m² über 357 € -> Zahlbetrag 495 €
    B  Abschlag 10 m² (595 €), davon 500 € bezahlt (offen 95 €); Schlussrechnung 8 m² über −119 € -> Guthaben 24 €

    Finanzen         Unbezahlte Rechnungen 1, Unbezahlt 495 €, Guthaben 24 €; Abschläge "Enthalten in Schlussrechnung …" ohne
                     unbezahlten Betrag, A "Zahlbetrag unbezahlt 495 €", B "Guthaben 24 €"; Filter "In Schlussrechnung", "Guthaben"
                     und "Unbezahlt" (seit 1.9.129 dieselbe Rechnungsliste wie die Akte, _rechnungsliste.html: Zeilen
                     `#rows tbody tr`, „Unbezahlt“ statt „Offen“)
    Dashboard        Kennzahlen wie Finanzen
    Akte             Reiter Rechnungen der Akte (seit 1.9.129 statt Auftragsseite und Projektmappe): Zahlstand nach demselben Stand
    Rechnungsseite   Abschlag A: Kennzeichen "Enthalten in Schlussrechnung …", Karte Zahlungen weiter "teilweise bezahlt"
    412 px dunkel    Finanzen
    Monteurin        /api/invoices 403

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_finanzen_zahlbetrag.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe
scripts/cdp_klicktest.py. Feste Uhr 10:00.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402


def befuellen(db, k):
    from datetime import date
    from decimal import Decimal

    from app.berlin_time import berlin_today
    from app.invoices import (
        create_abschlag_leistungsstand, create_schlussrechnung, finalize_and_send_invoice, update_invoice_header,
        update_invoice_item,
    )
    from app.models import AppUser, Customer, Project, Quote, QuoteItem
    from app.orders import create_order_from_quote, load_order
    from app.payments import Line, book_payment
    from app.project_pipeline_columns import default_pipeline_column_id

    buero = AppUser(username="buero", display_name="Bea Büro", role="buero_auftrag", password_hash=k.passwort())
    monteurin = AppUser(username="monteurin", display_name="Mia Monteurin", role="field", password_hash=k.passwort())
    kunde = Customer(name="Bauherr Zahl", last_name="Zahl", street="Dachweg 1", postal_code="52531", city="Uebach")
    db.add_all([buero, monteurin, kunde]); db.flush()

    def festschreiben(invoice, bis):
        update_invoice_header(db, invoice, service_period_start=date(2026, 9, 1), service_period_end=bis)
        return finalize_and_send_invoice(db, invoice)

    def auftrag(nr, abschlag_ist, gezahlt, schluss_ist):
        projekt = Project(project_number=f"P-KT-{nr}", name=f"Dach {nr}", customer_id=kunde.id, status="angebot",
                          pipeline_column_id=default_pipeline_column_id(db))
        db.add(projekt); db.flush()
        quote = Quote(quote_number=f"A-KT-{nr}", project_id=projekt.id, title="Dachsanierung", vat_rate=Decimal("19"))
        db.add(quote); db.flush()
        db.add(QuoteItem(quote_id=quote.id, position_number="1", short_text="Eindecken", quantity=Decimal("10"), unit="m2",
                         unit_price=Decimal("50")))
        db.commit()
        order = create_order_from_quote(db, quote.id, order_date=date(2026, 9, 1), execution_start=None, execution_end=None,
                                        caseworker_employee_id=None, project_manager_employee_id=None, payment_terms=None,
                                        remarks=None)
        abschlag = create_abschlag_leistungsstand(db, load_order(db, order.id))
        update_invoice_item(db, abschlag, abschlag.items[0], ist_quantity=Decimal(abschlag_ist))
        abschlag = festschreiben(abschlag, date(2026, 9, 30))
        book_payment(db, customer_id=kunde.id, received_on=berlin_today(), amount=Decimal(gezahlt), note=None,
                     lines=[Line(abschlag.id, zahlung=Decimal(gezahlt))], user_name="Bea Büro")
        schluss = create_schlussrechnung(db, load_order(db, order.id))
        update_invoice_item(db, schluss, schluss.items[0], ist_quantity=Decimal(schluss_ist))
        schluss = festschreiben(schluss, date(2026, 10, 10))
        return {"order": order.id, "project": projekt.id, "abschlag": abschlag.id, "abschlag_nr": abschlag.invoice_number,
                "schluss": schluss.id, "schluss_nr": schluss.invoice_number}

    a = auftrag("1", "4", "100", "10")
    b = auftrag("2", "10", "500", "8")
    return {"a": a, "b": b, "cookies": {"buero": k.cookies(buero), "monteurin": k.cookies(monteurin)}}


def _passt(p, name, ist, bedingung):
    """Prüfung über eine Bedingung -- bei Abweichung steht der gelesene Wert in der Ausgabe."""
    p.pruefe(name, "passt" if bedingung(ist) else ist, "passt")


FINANZEN_READY = "allInvoices.length>0&&document.getElementById('metrics').innerHTML"


def _zeile(nr: str) -> str:
    """Text der Zeile mit dieser Rechnungsnummer in der Tabelle von Finanzen (seit 1.9.129 `#rows tbody tr`, die Kopfzeile in thead)."""
    return (f"(()=>{{const r=[...document.querySelectorAll('#rows tbody tr')].find(x=>x.cells[0]&&x.cells[0].textContent==={nr!r});"
            "return r?[r.querySelector('[data-zahlstand]').textContent,r.querySelector('[data-offen-zeile]').textContent]:null})()")


# Rechnungsnummern der sichtbaren Zeilen von Finanzen (seit 1.9.129 ohne die Kopfzeile, die in thead steht)
FINANZEN_NUMMERN = "[...document.querySelectorAll('#rows tbody tr')].map(r=>r.cells[0].textContent)"


async def _js(tab, expr):
    """tab.js() mit normalem statt geschütztem Leerzeichen (Beträge aus toLocaleString)."""
    def norm(v):
        if isinstance(v, str):
            return v.replace(chr(160), " ")
        if isinstance(v, list):
            return [norm(x) for x in v]
        return v
    return norm(await tab.js(expr))


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument",
                  source="window.alert=m=>console.error('alert(): '+m);window.confirm=()=>true")
    await tab.anmelden(seed["cookies"]["buero"])
    await tab.fenster(1400, 1100)
    a, b = seed["a"], seed["b"]
    abschlag_a, abschlag_b = a["abschlag_nr"], b["abschlag_nr"]

    # --- Finanzen ---
    await tab.oeffnen("/finanzen", FINANZEN_READY)
    p.pruefe("Finanzen: offene Rechnungen 1, offener Betrag 495 €, Guthaben 24 €", await _js(tab,
        "[document.querySelector('[data-offen-anzahl]').textContent,document.querySelector('[data-offen-betrag]').textContent,"
        "document.querySelector('#metrics [data-guthaben]')?.textContent]"), ["1", "495,00 €", "24,00 €"])
    # seit 1.9.129 heißen die Kacheln „Unbezahlte Rechnungen“ und „Unbezahlt“ statt „Offene Rechnungen“ und „Offener Betrag“
    p.pruefe("Finanzen: Kacheln „Unbezahlte Rechnungen“ und „Unbezahlt“", await _js(tab,
        "['[data-offen-anzahl]','[data-offen-betrag]'].map(s=>document.querySelector(s).parentElement.querySelector('small').textContent)"),
        ["Unbezahlte Rechnungen", "Unbezahlt"])
    p.pruefe("Finanzen: Abschlag A enthalten, ohne offenen Betrag", await _js(tab, _zeile(abschlag_a)),
             [f"Enthalten in Schlussrechnung {a['schluss_nr']}", "—"])
    p.pruefe("Finanzen: Abschlag B enthalten", await _js(tab, _zeile(abschlag_b)),
             [f"Enthalten in Schlussrechnung {b['schluss_nr']}", "—"])
    # seit 1.9.129 Zahlstand aus der einen Rechnungsliste (_rechnungsliste.html): „Zahlbetrag unbezahlt <Betrag>“ statt „Zahlbetrag
    # offen“, das Guthaben mit Betrag
    p.pruefe("Finanzen: Schlussrechnung A Zahlbetrag unbezahlt 495 €", await _js(tab, _zeile(a["schluss_nr"])),
             ["Zahlbetrag unbezahlt 495,00 €", "495,00 €"])
    p.pruefe("Finanzen: Schlussrechnung B Guthaben 24 €", await _js(tab, _zeile(b["schluss_nr"])),
             ["Guthaben 24,00 €", "Guthaben 24,00 €"])
    await _js(tab, "setFilter('enthalten')")
    p.pruefe("Filter „In Schlussrechnung“: die beiden Abschläge", await _js(tab, FINANZEN_NUMMERN + ".sort()"),
             sorted([abschlag_a, abschlag_b]))
    await _js(tab, "setFilter('guthaben')")
    p.pruefe("Filter „Guthaben“: Schlussrechnung B", await _js(tab, FINANZEN_NUMMERN), [b["schluss_nr"]])
    # seit 1.9.129 heißt der Filter „Unbezahlt“ statt „Offen“ (Wert weiter 'offen')
    p.pruefe("Filter „Unbezahlt“: Beschriftung", await _js(tab,
        "document.querySelector('#filters [data-wert=\"offen\"]').textContent"), "Unbezahlt")
    await _js(tab, "setFilter('offen')")
    p.pruefe("Filter „Unbezahlt“: Schlussrechnung A", await _js(tab, FINANZEN_NUMMERN), [a["schluss_nr"]])
    await _js(tab, "setFilter('')")
    await tab.bild("finanzen_zahlbetrag")

    # --- Dashboard ---
    await tab.oeffnen("/", "document.querySelector('#widget-body-kpis [data-offen-betrag]')")
    p.pruefe("Dashboard: offene Rechnungen 1, 495 €, Guthaben 24 €", await _js(tab, 
        "(()=>{const w=document.getElementById('widget-body-kpis');return [w.querySelector('.metric b').textContent,"
        "w.querySelector('[data-offen-betrag]').textContent,w.querySelector('[data-guthaben]')?.textContent]})()"),
        ["1", "495,00 €", "24,00 €"])
    await tab.bild("dashboard_zahlbetrag")

    # --- Akte (seit 1.9.129 statt Auftragsseite und Projektmappe): Reiter Rechnungen, dieselbe Rechnungsliste ---
    # /orders/<id> leitet in die Akte des Projekts mit diesem Auftrag; Zahlstand „Zahlbetrag unbezahlt <Betrag>“ statt „Zahlbetrag offen
    # (offen …)“, „teilweise bezahlt“ klein geschrieben
    akte_bereit = "order&&order.id&&invoices.length>0&&document.querySelector('#invoicesList tbody tr[data-rechnung]')"
    await tab.oeffnen(f"/orders/{a['order']}#rechnungen", akte_bereit)
    _passt(p, "Akte A: Abschlag enthalten, Schlussrechnung Zahlbetrag unbezahlt", await _js(tab,
        "document.getElementById('invoicesList').textContent"),
        lambda v: v and f"Enthalten in Schlussrechnung {a['schluss_nr']}" in v and "Zahlbetrag unbezahlt 495,00" in v
        and "teilweise bezahlt" not in v.lower())
    await tab.oeffnen(f"/projects/{b['project']}#rechnungen", akte_bereit)
    _passt(p, "Akte B: Abschlag enthalten, Schlussrechnung Guthaben", await _js(tab,
        "document.getElementById('invoicesList').textContent"),
        lambda v: v and f"Enthalten in Schlussrechnung {b['schluss_nr']}" in v and "Guthaben 24,00" in v)

    # --- Rechnungsseite ---
    await tab.oeffnen(f"/invoices/{a['abschlag']}", "invoice&&invoice.id&&document.getElementById('seitenkopfStatus').textContent")
    p.pruefe("Rechnungsseite Abschlag A: Kennzeichen enthalten, Zahlstand teilweise bezahlt", await _js(tab, 
        "[document.getElementById('seitenkopfStatus').textContent,document.querySelector('[data-zahlstand]')?.textContent||'']"),
        [f"Enthalten in Schlussrechnung {a['schluss_nr']}", "Zahlstand: teilweise bezahlt"])
    await tab.oeffnen(f"/invoices/{a['schluss']}", "invoice&&invoice.id&&document.getElementById('seitenkopfStatus').textContent")
    p.pruefe("Rechnungsseite Schlussrechnung A: Zahlbetrag offen 495 €",
             await _js(tab, "document.getElementById('seitenkopfStatus').textContent"), "Zahlbetrag offen 495,00 €")
    p.pruefe("JS-Fehler Büro", tab.fehler, [])

    # --- 412 px dunkel ---
    await tab.fenster(412, 900, mobil=True)
    await tab.oeffnen("/finanzen", FINANZEN_READY)
    await _js(tab, "document.documentElement.setAttribute('data-theme','dark')")
    await tab.bild("finanzen_412_dunkel")
    await tab.fenster(1400, 1100)

    # --- Monteurin ---
    await tab.anmelden(seed["cookies"]["monteurin"])
    p.pruefe("Monteurin: /api/invoices 403", await _js(tab, "fetch('/api/invoices').then(r=>r.status)"), 403)


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="10:00"))
