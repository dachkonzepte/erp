"""Klicktest: Rechnungsseite rundet kaufmännisch (1.8.11, Runde 0e).

Öffnet /invoices/<id> für drei Rechnungsentwürfe mit Halbcent-Fällen und liest die angezeigten
Beträge aus der Seite:

    A  1 x 1,50 EUR, 19 % USt       USt 0,285  -> 0,29 EUR, Brutto 1,79 EUR
    B  2,5 x 0,85 EUR, 19 % USt     Position 2,125 -> 2,13 EUR, Netto 2,13, USt 0,40, Brutto 2,53
    C  1 x 10,25 EUR, 0 % USt,      Skonto 0,205 -> "... das entspricht 0,21 €."
       2 % Skonto in 10 Tagen

Dazu eine vor 1.8.11 versendete Rechnung D (1 x 1,50 EUR, rounding_rule leer): Ihr PDF zeigt
unverändert 0,28 EUR USt (geprüft in tests/test_v315_commercial_rounding.py). Was die Seite für D
anzeigt, gibt das Skript nur aus: Die Oberfläche formatiert den ungerundeten Wert 0,285 selbst
per toLocaleString und zeigt 0,29 EUR, das PDF 0,28 EUR -- so war es schon vor 1.8.11. Aus
demselben Grund prüft das Skript bei A und B zusätzlich die vom Server gelieferten Beträge: Die
Anzeige allein sähe auch mit dem alten Code richtig aus.

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_rechnung_rundung.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die
eigene PID beenden): siehe scripts/cdp_klicktest.py. Dauer etwa 20 Sekunden. Zugleich die kurze
Vorlage für ein neues Klicktest-Skript.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402


def befuellen(db, k):
    from datetime import date, timedelta
    from decimal import Decimal

    from app.invoices import create_schlussrechnung, finalize_and_send_invoice
    from app.models import AppUser, Customer, Order, OrderItem, Project
    from app.project_pipeline_columns import default_pipeline_column_id

    def festschreiben(inv):  # seit 1.8.74: Leistungszeitraum Pflicht beim Festschreiben
        from app.invoices import update_invoice_header
        if inv.service_period_start is None:
            update_invoice_header(db, inv, service_period_start=date(2026, 9, 1), service_period_end=date(2026, 9, 30))
        return finalize_and_send_invoice(db, inv)

    kunde = Customer(name="Klicktest Kunde", last_name="Klicktest Kunde")
    db.add(kunde); db.flush()
    admin = AppUser(username="anna", display_name="Anna Admin", role="admin", password_hash=k.passwort())
    db.add(admin); db.flush()

    def rechnung(nr, menge, preis, ust):
        projekt = Project(project_number=f"P-KT-{nr}", name=f"Rundung {nr}", customer_id=kunde.id, pipeline_column_id=default_pipeline_column_id(db))
        db.add(projekt); db.flush()
        auftrag = Order(order_number=f"AUF-KT-{nr}", project_id=projekt.id, source_quote_id=int(nr), quote_number_snapshot=f"A-KT-{nr}",
                        title="Rundung", vat_rate=Decimal(ust), customer_name="Klicktest Kunde")
        db.add(auftrag); db.flush()
        db.add(OrderItem(order_id=auftrag.id, sort_order=10, position_number="1", short_text="Dacheindeckung",
                         quantity=Decimal(menge), unit="m²", unit_price=Decimal(preis)))
        db.commit()
        return create_schlussrechnung(db, auftrag, due_date=date.today() + timedelta(days=14))

    a, b, c = rechnung("1", "1", "1.50", "19.00"), rechnung("2", "2.5", "0.85", "19.00"), rechnung("3", "1", "10.25", "0")
    c.skonto_percent, c.skonto_days = Decimal("2.00"), 10
    d = festschreiben(rechnung("4", "1", "1.50", "19.00"))
    d.rounding_rule = None   # so steht eine vor 1.8.11 versendete Rechnung nach der Migration da
    db.commit()
    return {"rechnungen": {"A": a.id, "B": b.id, "C": c.id, "D": d.id}, "cookies": {"anna": k.cookies(admin)}}


BETRAEGE = ("[...['mNet','mVat','mGross']].map(id=>(document.getElementById(id)?.textContent||'').replace(/\\u00a0/g,' '))")
POSITION = ("[...document.querySelectorAll('.inv-row')].map(r=>[...r.children].map(c=>c.textContent.replace(/\\u00a0/g,' ').trim()))"
            ".find(r=>r[1]&&r[1].startsWith('Dacheindeckung'))?.[6]")
BEREIT = "document.getElementById('mGross')?.textContent.includes('€')"
# Die Seite formatiert per toLocaleString, das rundete 0,285 schon vor 1.8.11 auf 0,29 -- nur das
# PDF rundete halb-gerade. Deshalb zusätzlich die Werte, die der Server liefert (alt: 0.285/1.785).
SERVER = "fetch('/api/invoices/{id}').then(r=>r.json()).then(j=>[j.net_total,j.vat_total,j.gross_total].map(Number))"


async def pruefen(tab, seed, p):
    r = seed["rechnungen"]
    await tab.anmelden(seed["cookies"]["anna"])

    await tab.oeffnen(f"/invoices/{r['A']}", BEREIT)
    p.pruefe("A: Netto, USt, Brutto", await tab.js(BETRAEGE), ["1,50 €", "0,29 €", "1,79 €"])
    p.pruefe("A: vom Server geliefert", await tab.js(SERVER.format(id=r["A"])), [1.5, 0.29, 1.79])
    p.pruefe("A: JS-Fehler", tab.fehler, [])
    await tab.bild("rechnung_a_ust")

    await tab.oeffnen(f"/invoices/{r['B']}", BEREIT)
    p.pruefe("B: Positionsbetrag", await tab.js(POSITION), "2,13 €")
    p.pruefe("B: Netto, USt, Brutto", await tab.js(BETRAEGE), ["2,13 €", "0,40 €", "2,53 €"])
    p.pruefe("B: vom Server geliefert", await tab.js(SERVER.format(id=r["B"])), [2.13, 0.4, 2.53])
    p.pruefe("B: JS-Fehler", tab.fehler, [])
    await tab.bild("rechnung_b_position")

    await tab.oeffnen(f"/invoices/{r['C']}", BEREIT)
    satz = await tab.js("document.getElementById('paymentTermsSentence')?.textContent||''")
    p.pruefe("C: Skontobetrag im Zahlungssatz", "das entspricht 0,21 €." in (satz or ""), True)
    p.pruefe("C: JS-Fehler", tab.fehler, [])
    await tab.bild("rechnung_c_skonto")

    await tab.oeffnen(f"/invoices/{r['D']}", BEREIT)
    print(f"    D (vor 1.8.11, nur zur Info): Seite zeigt {await tab.js(BETRAEGE)}, Server liefert {await tab.js(SERVER.format(id=r['D']))}")
    p.pruefe("D: JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__))
