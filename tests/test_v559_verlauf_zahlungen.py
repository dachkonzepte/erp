"""Version 1.9.139 (Stufe 5, R4, Punkt 2) -- Verlaufstexte der Zahlungen: ein Satzbau für Akte und Kunde (app/akte_verlauf.py::zahlung_text()).

„Zahlungseingang 3.000,00 € vom 18.08.2025“, „144,00 € auf R-… zugeordnet“, „Erstattung 144,00 € gebucht“, „Zuordnung zurückgenommen – Begründung: …“. Die
Einzelheiten bleiben aufklappbar, tragen denselben Satz und nirgends mehr „Zahlung … Zahlung“. Im Protokoll selbst bleibt die Bezeichnung wie bisher."""

import re
from decimal import Decimal as D
from pathlib import Path

import pytest
from sqlalchemy import select

from app.grunddaten import anlegen
from app.models import AuditLog, PaymentAllocation
from app.payments import Line, RefundLine, allocate_rest, book_customer_refund, reverse_allocation, reverse_payment
from app.routers import customers as customers_router
from app.routers import projects as projects_router
from tests.node_lauf import node_ausfuehren
from tests.test_v381_zahlungen import HEUTE, _abschlag, _auftrag, _buchen, _kunde, _pauschal
from tests.test_v547_akte_verlauf import _Anfrage

VORLAGEN = Path(__file__).resolve().parents[1] / "app/templates"

GRUND = "falsch erfasst"
TAG = HEUTE.strftime("%d.%m.%Y")


@pytest.fixture
def welt(threaded_db_session, router_test_client):
    db = threaded_db_session
    anlegen(db)
    db.commit()
    kunde = _kunde(db, "Kessler")
    order = _auftrag(db, kunde)
    rechnung = _abschlag(db, order)
    client = router_test_client(db, customers_router.router, projects_router.router)
    return {"db": db, "kunde": kunde, "order": order, "rechnung": rechnung, "client": client}


def _kunde_strom(w, **abfrage):
    a = w["client"].get(f"/api/customers/{w['kunde'].id}/verlauf", params=abfrage)
    assert a.status_code == 200, a.text
    return a.json()["eintraege"]


def _akte_strom(w, **abfrage):
    a = w["client"].get(f"/api/projects/{w['order'].project_id}/verlauf", params=abfrage)
    assert a.status_code == 200, a.text
    return a.json()["eintraege"]


def _eingang(w, betrag="3000", zuordnen="2380"):
    with _Anfrage(8, "Fin Finanzen", "POST", "/api/payments"):
        return _buchen(w["db"], w["rechnung"], betrag, lines=[Line(w["rechnung"].id, zahlung=D(zuordnen))] if zuordnen else [])


def _zahlungen(strom):
    return [e for e in strom if e["art"] == "zahlung"]


def test_zahlungseingang_mit_zuordnung(welt):
    _eingang(welt)
    nummer = welt["rechnung"].invoice_number
    e = _zahlungen(_kunde_strom(welt))[0]
    assert e["titel"] == f"Zahlungseingang 3.000,00 € vom {TAG}"
    assert e["unterzeile"] == f"2.380,00 € auf {nummer} zugeordnet"
    assert [z["kurz"] for z in sorted(e["einzelheiten"], key=lambda z: z["id"])] == [e["titel"], e["unterzeile"]]


def test_zuordnung_aus_dem_rest(welt):
    p = _eingang(welt)
    zweite = _pauschal(welt["db"], welt["order"], "1000")
    with _Anfrage(8, "Fin Finanzen", "POST", f"/api/payments/{p.id}/allocations"):
        allocate_rest(welt["db"], p, [Line(zweite.id, zahlung=D("144"))], user_name="Fin Finanzen")
    for strom in (_kunde_strom(welt), _akte_strom(welt)):
        e = _zahlungen(strom)[0]
        assert e["titel"] == f"144,00 € auf {zweite.invoice_number} zugeordnet"
        assert e["unterzeile"] == ""


def test_mehrere_zuordnungen_nennen_zwei_und_zaehlen_den_rest(welt):
    db = welt["db"]
    zweite, dritte, vierte = (_pauschal(db, welt["order"], "100") for _ in range(3))
    with _Anfrage(8, "Fin Finanzen", "POST", "/api/payments"):
        _buchen(db, welt["rechnung"], "280", lines=[Line(zweite.id, zahlung=D("10")), Line(dritte.id, zahlung=D("20")), Line(vierte.id, zahlung=D("30"))])
    e = _zahlungen(_kunde_strom(welt))[0]
    assert e["titel"] == f"Zahlungseingang 280,00 € vom {TAG}"
    assert e["unterzeile"] == f"10,00 € auf {zweite.invoice_number} zugeordnet · 20,00 € auf {dritte.invoice_number} zugeordnet · und 1 weitere Einzelheit"
    assert len(e["einzelheiten"]) == 4


def test_skonto_und_einbehalt_stehen_mit_ihrem_namen(welt):
    with _Anfrage(8, "Fin Finanzen", "POST", "/api/payments"):
        _buchen(welt["db"], welt["rechnung"], "2000", lines=[Line(welt["rechnung"].id, zahlung=D("2000"), skonto=D("5"), einbehalt=D("7"))])
    nummer = welt["rechnung"].invoice_number
    e = _zahlungen(_akte_strom(welt))[0]
    texte = {z["kurz"] for z in e["einzelheiten"]}
    assert texte == {f"2.000,00 € auf {nummer} zugeordnet", f"Skonto 5,00 € auf {nummer}", f"Einbehalt 7,00 € auf {nummer}"}


def test_zuordnung_zurueckgenommen_gleich_in_akte_und_kunde(welt):
    db = welt["db"]
    p = _eingang(welt)
    zuordnung = db.scalar(select(PaymentAllocation).where(PaymentAllocation.payment_id == p.id))
    with _Anfrage(8, "Fin Finanzen", "POST", f"/api/payment-allocations/{zuordnung.id}/reverse"):
        reverse_allocation(db, zuordnung, reason=GRUND, user_name="Fin Finanzen")
    nummer = welt["rechnung"].invoice_number
    for strom in (_kunde_strom(welt), _akte_strom(welt)):
        e = _zahlungen(strom)[0]
        assert e["titel"] == f"Zuordnung zurückgenommen – Begründung: {GRUND}"
        assert e["unterzeile"] == f"2.380,00 € auf {nummer}"


def test_zahlungseingang_zurueckgenommen(welt):
    p = _eingang(welt)
    with _Anfrage(8, "Fin Finanzen", "POST", f"/api/payments/{p.id}/reverse"):
        reverse_payment(welt["db"], p, reason=GRUND, user_name="Fin Finanzen")
    e = _zahlungen(_kunde_strom(welt))[0]
    assert e["titel"] == f"Zahlungseingang zurückgenommen – Begründung: {GRUND}"
    assert e["unterzeile"] == f"3.000,00 € vom {TAG} · und 1 weitere Einzelheit"
    # In der Akte steht nur, was das Projekt betrifft: die Zuordnung
    assert _zahlungen(_akte_strom(welt))[0]["titel"] == f"Zuordnung zurückgenommen – Begründung: {GRUND}"


def _erstattung(w, betrag="144"):
    p = _eingang(w, betrag="3000", zuordnen="2380")
    with _Anfrage(8, "Fin Finanzen", "POST", "/api/payments/refund"):
        return p, book_customer_refund(w["db"], w["kunde"].id, paid_on=HEUTE, note=None, lines=[RefundLine(D(betrag), payment_id=p.id)], user_name="Fin Finanzen")


def test_erstattung_gebucht_und_zurueckgenommen(welt):
    _, ausgang = _erstattung(welt)
    e = _zahlungen(_kunde_strom(welt))[0]
    assert (e["titel"], e["unterzeile"]) == ("Erstattung 144,00 € gebucht", "")
    with _Anfrage(8, "Fin Finanzen", "POST", f"/api/payments/{ausgang.id}/reverse"):
        reverse_payment(welt["db"], ausgang, reason=GRUND, user_name="Fin Finanzen")
    e = _zahlungen(_kunde_strom(welt))[0]
    assert e["titel"] == f"Erstattung zurückgenommen – Begründung: {GRUND}"
    assert e["unterzeile"] == "144,00 €"


def test_neue_texte_gleich_in_akte_und_kunde(welt):
    """Jede Zeile, die in beiden Strömen steht, trägt denselben Satz."""
    db = welt["db"]
    p = _eingang(welt)
    zuordnung = db.scalar(select(PaymentAllocation).where(PaymentAllocation.payment_id == p.id))
    with _Anfrage(8, "Fin Finanzen", "POST", f"/api/payment-allocations/{zuordnung.id}/reverse"):
        reverse_allocation(db, zuordnung, reason=GRUND, user_name="Fin Finanzen")

    def saetze(strom):
        return {z["id"]: z["kurz"] for e in _zahlungen(strom) for z in e["einzelheiten"]}

    kunde, akte = saetze(_kunde_strom(welt)), saetze(_akte_strom(welt))
    gemeinsam = set(kunde) & set(akte)
    assert len(gemeinsam) == 2  # Zuordnung und Gegenbuchung (die Zahlung selbst steht nur im Kunden)
    assert {i: kunde[i] for i in gemeinsam} == {i: akte[i] for i in gemeinsam}


def test_kein_doppeltes_wort(welt):
    db = welt["db"]
    p = _eingang(welt)
    zweite = _pauschal(db, welt["order"], "1000")
    with _Anfrage(8, "Fin Finanzen", "POST", f"/api/payments/{p.id}/allocations"):
        allocate_rest(db, p, [Line(zweite.id, zahlung=D("144"))], user_name="Fin Finanzen")
    zuordnung = db.scalar(select(PaymentAllocation).where(PaymentAllocation.invoice_id == zweite.id))
    with _Anfrage(8, "Fin Finanzen", "POST", f"/api/payment-allocations/{zuordnung.id}/reverse"):
        reverse_allocation(db, zuordnung, reason=GRUND, user_name="Fin Finanzen")
    doppelt = re.compile(r"Zahlung.*Zahlung")
    gesehen = 0
    for strom in (_kunde_strom(welt), _akte_strom(welt)):
        for e in _zahlungen(strom):
            gesehen += 1
            assert not doppelt.search(e["titel"]), e["titel"]
            assert not doppelt.search(e["unterzeile"]), e["unterzeile"]
            for z in e["einzelheiten"]:
                assert not doppelt.search(z["kurz"]), z["kurz"]
                assert z["entity_label"] is None  # die lange Bezeichnung steht nicht in der Antwort
    assert gesehen >= 4


def test_protokoll_selbst_bleibt_wie_bisher(welt):
    _eingang(welt)
    bezeichnung = welt["db"].scalar(select(AuditLog.entity_label).where(AuditLog.entity_type == "Zahlungseingang").order_by(AuditLog.id))
    assert bezeichnung.startswith("Zahlung 3.000,00 €") and "Kessler" in bezeichnung


def test_zeile_ohne_schnappschuss_faellt_auf_den_allgemeinen_satz_zurueck(welt):
    """Unlesbarer Schnappschuss: kein Fehler, der allgemeine Satz ohne die Art davor."""
    p = _eingang(welt)
    zeilen = welt["db"].scalars(select(AuditLog).where(AuditLog.entity_type == "Zahlungseingang", AuditLog.entity_id == str(p.id))).all()
    assert len(zeilen) == 2
    for zeile in zeilen:
        zeile.details = "kein json"
    welt["db"].commit()
    e = _zahlungen(_kunde_strom(welt))[0]
    assert e["titel"].startswith("Zahlung 3.000,00 €") and e["titel"].endswith("angelegt")
    assert all("kurz" not in z for z in e["einzelheiten"])


def test_seite_zeichnet_den_kurzen_satz():
    baustein = (VORLAGEN / "_verlauf.html").read_text(encoding="utf-8").replace("<script>", "").replace("</script>", "")
    aus = node_ausfuehren(baustein + """
console.log(JSON.stringify([
  verlaufEinzelheit({kurz: '144,00 € auf R-1 <b>zugeordnet</b>', entity_label: 'x', entity_type: 'Zahlungseingang', action: 'angelegt'}),
  verlaufEinzelheit({entity_type: 'Objekt', entity_type_label: 'Objekt', entity_label: 'Am Turm', action: 'gelöscht'}),
]));""")
    assert aus[0] == "144,00 € auf R-1 &lt;b&gt;zugeordnet&lt;/b&gt;"
    assert aus[1] == "<b>Objekt</b> Am Turm: Datensatz gelöscht"


@pytest.mark.parametrize("vorlage", ["akte.html", "customer.html"])
def test_beide_seiten_nehmen_denselben_baustein(vorlage):
    text = (VORLAGEN / vorlage).read_text(encoding="utf-8")
    assert "verlaufEinzelheit(z)" in text
    assert "z.entity_type_label||z.entity_type" not in text
