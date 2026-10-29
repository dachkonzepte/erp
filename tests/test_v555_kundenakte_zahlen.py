"""Version 1.9.135 (Stufe 5, R3, Punkt 1) -- die Zahlen der Kundenakte (app/kundenakte.py, GET /api/customers/{id}/akte).

Je Projekt Status und Zahlen mit den Rechnungen der Akte; Geld des Kunden: unbezahlt, überfällig, Guthaben, je Jahr abgerechnet und bezahlt;
Vorschläge für das Guthaben. Jede Zahl ist im Test nachgerechnet -- aus den Akten (app/akte.py::leistung()/zahlung() je Auftrag) bzw. aus den
Rechnungen und Zahlungen des Kunden.

Welt: Kunde Kessler mit
    Projekt A   Auftrag 100 m² × 50 € (5.000 € netto); Abschlag 40 m² im Vorjahr festgeschrieben und im Vorjahr bezahlt (2.380 €), Schlussrechnung
                vor 60 Tagen festgeschrieben -- Zahlbetrag 3.570 € unbezahlt und überfällig
    Projekt B   Auftrag 10 × 200 € (2.000 € netto); pauschaler Abschlag 1.000 € netto heute festgeschrieben, Zahlung 1.500 € -- 1.190 € zugeordnet,
                Rest 310 € am Kunden
    dazu        eine Zahlung 200 € ohne Zuordnung, als Zahlungsausgang erstattet (bezahlt +200 −200), eine Zahlung 99 € zurückgenommen (zählt nicht)
    Projekt C   nur ein Angebot (10 m² × 50 €, dazu eine Bedarfsposition außerhalb der Summe)
    Projekt D   Auftrag storniert
    Muster      Mustervorgang des Kunden (zählt nirgends)
dazu Kunde Lorenz mit einer eigenen Rechnung und Zahlung (zählt bei Kessler nicht) und Kunde Maus mit einem Rest ohne unbezahlte Rechnung.
"""

from contextlib import contextmanager
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal as D

import pytest
from sqlalchemy import select

from app import berlin_time
from app.akte import leistung, projekt_status, zahlung
from app.auftragsstatus import status_aendern
from app.berlin_time import berlin_today
from app.grunddaten import anlegen
from app.invoices import compute_invoice_totals
from app.kundenakte import angebot_summen, geld, kunde_kontext, projekte
from app.models import Invoice, Order, Payment, Project, Quote, QuoteItem, QuoteItemLayout
from app.payments import Line, RefundLine, book_customer_refund, book_payment, customer_payments, reverse_payment
from app.project_pipeline_columns import default_pipeline_column_id
from app.projects import quote_to_dict
from app.routers import customers as customers_router
from tests.test_v381_zahlungen import _abschlag, _auftrag, _kunde, _pauschal
from tests.test_v394_finanzen_zahlbetrag import _schluss


@contextmanager
def _am(tag):
    """Die Uhr der App auf 10:00 Uhr Berliner Zeit am `tag` -- Festschreiben setzt Rechnungsdatum und Fälligkeit danach."""
    vorher = berlin_time._utc_now
    start = datetime.combine(tag, time(10, 0), tzinfo=berlin_time.BERLIN).astimezone(timezone.utc)
    berlin_time._utc_now = lambda: start
    try:
        yield
    finally:
        berlin_time._utc_now = vorher


def _zahlen(db, kunde, tag, betrag, zeilen=()):
    with _am(tag):
        return book_payment(db, customer_id=kunde.id, received_on=tag, amount=D(betrag), note=None,
                            lines=[Line(invoice_id=i.id, zahlung=D(z)) for i, z in zeilen], user_name="Test")


def _projekt_ohne_auftrag(db, kunde, nummer, *, muster=False):
    p = Project(project_number=nummer, name="Garage", customer_id=kunde.id, is_template=muster, pipeline_column_id=default_pipeline_column_id(db))
    db.add(p)
    db.flush()
    q = Quote(quote_number=f"A-{nummer}", project_id=p.id, title="Flachdach", vat_rate=D("19"))
    db.add(q)
    db.flush()
    db.add(QuoteItem(quote_id=q.id, position_number="1", short_text="Abdichten", quantity=D("10"), unit="m²", unit_price=D("50")))
    bedarf = QuoteItem(quote_id=q.id, position_number="2", short_text="Bedarf", quantity=D("1"), unit="Stk", unit_price=D("99"))
    db.add(bedarf)
    db.flush()
    db.add(QuoteItemLayout(quote_item_id=bedarf.id, include_in_total=False))
    db.commit()
    return p, q


@pytest.fixture
def welt(threaded_db_session):
    db = threaded_db_session
    anlegen(db)
    db.commit()
    heute = berlin_today()
    vorjahr = heute.replace(year=heute.year - 1, month=12, day=1)
    kessler = _kunde(db, "Kessler")
    a = _auftrag(db, kessler, quantity="100", price="50")
    with _am(vorjahr):
        abschlag = _abschlag(db, a, "40")
    _zahlen(db, kessler, vorjahr + timedelta(days=10), "2380", [(abschlag, "2380")])
    with _am(heute - timedelta(days=60)):
        schluss = _schluss(db, db.get(Order, a.id))
    b = _auftrag(db, kessler, quantity="10", price="200")
    pauschal = _pauschal(db, b, "1000")
    zahlung_b = _zahlen(db, kessler, heute, "1500", [(pauschal, "1190")])
    zuviel = _zahlen(db, kessler, heute, "200")
    with _am(heute):
        book_customer_refund(db, kessler.id, paid_on=heute, note=None, lines=[RefundLine(amount=D("200"), payment_id=zuviel.id)], user_name="Test")
        reverse_payment(db, _zahlen(db, kessler, heute, "99"), reason="falsch erfasst", user_name="Test")
    c, angebot = _projekt_ohne_auftrag(db, kessler, "P-C")
    d = _auftrag(db, kessler, quantity="1", price="100")
    status_aendern(db, d.id, "storniert", "Kunde hat abgesagt", user_name="Test")
    muster, _ = _projekt_ohne_auftrag(db, kessler, "P-M", muster=True)
    lorenz = _kunde(db, "Lorenz")
    l_auftrag = _auftrag(db, lorenz, quantity="10", price="50")
    l_abschlag = _abschlag(db, l_auftrag, "10")
    _zahlen(db, lorenz, heute, "100", [(l_abschlag, "100")])
    maus = _kunde(db, "Maus")
    _zahlen(db, maus, heute, "50")
    return {"db": db, "heute": heute, "vorjahr": vorjahr, "kessler": kessler, "a": a, "b": b, "c": c, "d": d, "muster": muster,
            "abschlag": abschlag, "schluss": schluss, "pauschal": pauschal, "zahlung_b": zahlung_b, "angebot": angebot, "maus": maus}


def _je_projekt(daten):
    return {p["project_number"]: p for p in daten}


def test_je_projekt_status_und_zahlen_wie_die_akten(welt):
    """Je Projekt: der Status aus app/akte.py, die Zahlen = Summe von leistung()/zahlung() seiner Aufträge; Muster fehlen; laufende zuerst."""
    db = welt["db"]
    daten = projekte(db, welt["kessler"].id, welt["heute"])
    je = _je_projekt(daten)
    projekte_db = db.scalars(select(Project).where(Project.customer_id == welt["kessler"].id, Project.is_template.is_(False))).all()
    assert set(je) == {p.project_number for p in projekte_db} and "P-M" not in je
    for p in projekte_db:
        eintrag = je[p.project_number]
        assert eintrag["status"] == projekt_status(db, p)
        orders = db.scalars(select(Order).where(Order.project_id == p.id)).all()
        nachgerechnet = {
            "auftragssumme": sum((leistung(db, o)["auftragssumme"] for o in orders), D("0")),
            "abgerechnet": sum((leistung(db, o)["abgerechnet"] for o in orders), D("0")),
            "noch_nicht_abgerechnet": sum((leistung(db, o)["noch_nicht_abgerechnet"] for o in orders), D("0")),
            "unbezahlt": sum((zahlung(db, o)["unbezahlt"] for o in orders), D("0")),
        }
        assert eintrag["zahlen"] == nachgerechnet, p.project_number
        assert len(eintrag["auftraege"]) == len(orders)
    a, b, d = (je[welt[k].project.project_number] for k in ("a", "b", "d"))
    # Abschlag 2.000 € + Schlussrechnung 3.000 € (Gesamtleistung 5.000 € minus Abzug) = 5.000 € abgerechnet; Zahlbetrag 3.570 € unbezahlt
    assert a["zahlen"] == {"auftragssumme": D("5000.00"), "abgerechnet": D("5000.00"), "noch_nicht_abgerechnet": D("0"),
                           "unbezahlt": D("3570.00")}
    assert (a["status"], a["laufend"]) == ("schlussrechnung", True)
    assert b["zahlen"]["unbezahlt"] == D("0") and b["zahlen"]["noch_nicht_abgerechnet"] == D("1000.00")
    assert (d["status"], d["laufend"]) == ("storniert", False)
    assert [x["laufend"] for x in daten] == sorted((x["laufend"] for x in daten), reverse=True)


def test_angebot_ohne_auftrag_und_summen_wie_der_editor(welt):
    db = welt["db"]
    c = _je_projekt(projekte(db, welt["kessler"].id, welt["heute"]))["P-C"]
    q = db.get(Quote, welt["angebot"].id)
    editor = quote_to_dict(q)
    assert (c["status"], c["laufend"], c["auftraege"]) == ("angebot", True, [])
    assert c["angebot"]["quote_number"] == "A-P-C" and c["angebot"]["net_total"] == editor["net_total"] == D("500.00")
    assert c["angebote"][0]["gross_total"] == editor["gross_total"] == D("595.00")
    assert angebot_summen(db, [q]) == {q.id: (editor["net_total"], editor["gross_total"])}


def _rechnungen(db, kunde):
    return [i for i in db.scalars(select(Invoice).where(Invoice.customer_id == kunde.id))
            if i.status == "versendet" and i.invoice_type != "storno"]


def test_geld_nachgerechnet(welt):
    """Unbezahlt = Summe der Akten (unbezahlt je Auftrag), Guthaben = Rest der Zahlungen, je Jahr abgerechnet = Netto seiner Rechnungen nach
    Rechnungsdatum, bezahlt = seine Zahlungen nach Eingangstag; nichts von Lorenz."""
    db, heute = welt["db"], welt["heute"]
    g = geld(db, welt["kessler"].id, heute)
    orders = db.scalars(select(Order).join(Project).where(Project.customer_id == welt["kessler"].id)).all()
    assert g["unbezahlt"] == sum((zahlung(db, o)["unbezahlt"] for o in orders), D("0")) == D("3570.00")
    assert g["unbezahlte_rechnungen"] == 1
    assert g["ueberfaellig_seit"] == db.get(Invoice, welt["schluss"].id).due_date and g["ueberfaellig"] > 0
    assert g["guthaben"]["total"] == customer_payments(db, welt["kessler"].id)["balance"]["total"] == D("310.00")
    je_jahr = {w["jahr"]: w for w in g["je_jahr"]}
    for jahr in (heute.year, heute.year - 1):
        rechnungen = [i for i in _rechnungen(db, welt["kessler"]) if i.invoice_date.year == jahr]
        assert je_jahr[jahr]["abgerechnet"] == sum((compute_invoice_totals(i)["net_total"] for i in rechnungen), D("0"))
        alle = db.scalars(select(Payment).where(Payment.customer_id == welt["kessler"].id)).all()
        zurueck = {p.reverses_payment_id for p in alle if p.reverses_payment_id is not None}
        zahlungen = [p for p in alle if p.received_on.year == jahr and p.reverses_payment_id is None and p.id not in zurueck]
        assert je_jahr[jahr]["bezahlt"] == sum((p.amount for p in zahlungen), D("0"))
        assert je_jahr[jahr]["zahlungen"] == len([p for p in zahlungen if p.amount > 0])
        assert je_jahr[jahr]["erstattet"] == -sum((p.amount for p in zahlungen if p.amount < 0), D("0"))
    assert (je_jahr[heute.year]["bezahlt"], je_jahr[heute.year]["zahlungen"], je_jahr[heute.year]["erstattet"]) == (D("1500.00"), 2, D("200.00"))
    assert je_jahr[heute.year - 1]["abgerechnet"] == D("2000.00") and je_jahr[heute.year - 1]["bezahlt"] == D("2380.00")
    assert g["jahr"] == heute.year and [w["jahr"] for w in g["je_jahr"]] == sorted(je_jahr, reverse=True)


def test_vorschlag_rest_auf_die_aelteste_unbezahlte_sonst_erstatten(welt):
    db = welt["db"]
    kontext = kunde_kontext(db, welt["kessler"], welt["heute"])
    assert kontext["vorschlaege"] == [{"art": "zuordnen", "payment_id": welt["zahlung_b"].id, "eingang": welt["heute"], "rest": D("310.00"),
                                      "invoice_id": welt["schluss"].id, "invoice_number": db.get(Invoice, welt["schluss"].id).invoice_number,
                                      "betrag": D("310.00")}]
    maus = kunde_kontext(db, welt["maus"], welt["heute"])
    assert [(v["art"], v["betrag"], v["invoice_id"]) for v in maus["vorschlaege"]] == [("erstatten", D("50.00"), None)]


def test_zaehler(welt):
    z = kunde_kontext(welt["db"], welt["kessler"], welt["heute"])["zaehler"]
    assert z["projekte"] == 4  # A, B, C, D -- ohne den Mustervorgang
    assert set(z) == {"projekte", "objekte", "anfragen", "dokumente", "kontakte"}


@pytest.mark.parametrize("rolle,status", [("buero_auftrag", 200), ("buero_finanzen", 200), ("admin", 200), ("field", 403)])
def test_endpunkt_rollen(welt, router_test_client, rolle, status):
    client = router_test_client(welt["db"], customers_router.router, role=rolle)
    antwort = client.get(f"/api/customers/{welt['kessler'].id}/akte")
    assert antwort.status_code == status, antwort.text
    if status == 200:
        daten = antwort.json()
        assert D(str(daten["geld"]["unbezahlt"])) == D("3570.00") and len(daten["projekte"]) == 4
    assert client.get("/api/customers/987654/akte").status_code == (404 if status == 200 else 403)
