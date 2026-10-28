"""Kontext der Akte (seit 1.9.128, Stufe 5, R2, Punkt 2; GET /api/projects/{id}/akte, app/akte.py::akte_kontext()).

- Auftragswahl: alle Aufträge des Projekts, gewählt der aus ?auftrag=, sonst der älteste laufende oder pausierte; ein Auftrag eines anderen
  Projekts 404; ohne Auftrag die Phase des Angebots.
- Hauptaktion je Phase und Rolle (darf_geld()): ohne Angebot „Angebot“, mit Angebot „Beauftragen“, Auftrag „Einsatz planen“, Ausführung
  „Rechnung erstellen“ bzw. für Büro – Auftrag „Einsatz planen“, nach verweigerter Abnahme „Abnahme erfassen“, Abnahme „Schlussrechnung
  erstellen“ bzw. „Abnahme & Mängel“, Schlussrechnung „Auftrag abschließen“, geschlossen keine.
- Was ansteht (überfällige Rechnung, offener Befund, Checkliste im Entwurf), Termine (ab heute, private fremde als „Belegt“), Zähler.
- F2: nach der Schlussrechnung 409 für alles, was aufs Dokument geht; Sachbearbeiter und Bemerkungen bleiben frei.
- Summen je LV-Titel und der Nachträge (nur Büro), die eine Rechnungsliste (Art, Zeitraum, Netto); die Monteurin bekommt keine Akte (403)."""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from app import berlin_time
from app.auftragsstatus import status_aendern
from app.invoices import create_abschlag_leistungsstand, create_schlussrechnung, update_invoice_item
from app.models import AppUser, CalendarEvent, Finding, Invoice, OrderItem, OrderSection, ServiceReport
from app.routers import invoices as invoices_router
from app.routers import orders as orders_router
from app.routers import projects as projects_router
from tests.leistungszeitraum import festschreiben
from tests.test_v325_contract_basis import beauftragen, make_quote
from tests.test_v545_phase_projektstatus import _abnahme, _buchung, _projekt, welt  # noqa: F401  (Fixture)

ROUTER = (projects_router.router, orders_router.router, invoices_router.router)


def _zweites_angebot(db, project_id, number):
    """Ein weiteres Angebot im selben Projekt (für einen zweiten Auftrag)."""
    from app.models import Quote, QuoteItem
    from app.projects import load_quote
    q = Quote(quote_number=f"A-{number}", project_id=project_id, title="PV-Anlage", vat_rate=Decimal("19"))
    db.add(q); db.flush()
    db.add(QuoteItem(quote_id=q.id, position_number="1", short_text="Modul", quantity=Decimal("1"), unit="Stk", unit_price=Decimal("100")))
    db.commit()
    return load_quote(db, q.id)


def _akte(w, rolle="admin", **abfrage):
    antwort = w["client"](w["db"], *ROUTER, role=rolle).get(f"/api/projects/{w['order'].project_id}/akte", params=abfrage)
    assert antwort.status_code == 200, antwort.text
    return antwort.json()


def _haupt(w, rolle="admin"):
    h = _akte(w, rolle)["hauptaktion"]
    return h["art"] if h else None


def test_hauptaktion_je_phase_und_rolle(welt):  # noqa: F811
    w = welt
    assert (_haupt(w), _haupt(w, "buero_auftrag")) == ("einsatz", "einsatz")  # Phase Auftrag
    _buchung(w, w["heute"] - timedelta(days=2))
    assert (_haupt(w), _haupt(w, "buero_finanzen"), _haupt(w, "buero_auftrag")) == ("rechnung", "rechnung", "einsatz")  # Ausführung
    _abnahme(w, w["heute"] - timedelta(days=1), result="verweigert")
    assert _haupt(w, "buero_auftrag") == "abnahme"
    _abnahme(w, w["heute"])
    assert (_haupt(w), _haupt(w, "buero_auftrag")) == ("schlussrechnung", "maengel")  # Abnahme
    festschreiben(w["db"], create_schlussrechnung(w["db"], w["order"]))
    assert _haupt(w) == "abschliessen"  # Schlussrechnung
    status_aendern(w["db"], w["order"].id, "abgeschlossen", None)
    assert _haupt(w) is None


def test_ohne_auftrag_angebot_oder_beauftragen(welt):  # noqa: F811
    w = welt
    ohne = _projekt(w["db"], "548a")
    mit = _projekt(w["db"], "548b", angebot=True)
    client = w["client"](w["db"], *ROUTER)
    a = client.get(f"/api/projects/{ohne.id}/akte").json()
    assert (a["auftrag_id"], a["hauptaktion"]["art"], a["phasen"]["phase"], a["auftraege"]) == (None, "angebot", None, [])
    b = client.get(f"/api/projects/{mit.id}/akte").json()
    assert (b["hauptaktion"]["art"], b["phasen"]["phase"]) == ("beauftragen", "angebot") and b["angebot_id"]


def test_auftragswahl_mit_zwei_auftraegen(welt):  # noqa: F811
    w = welt
    db, erster = w["db"], w["order"]
    zweiter = beauftragen(db, _zweites_angebot(db, erster.project_id, "0548c"))
    a = _akte(w)
    assert [x["id"] for x in a["auftraege"]] == [erster.id, zweiter.id] and a["auftrag_id"] == erster.id  # der älteste laufende
    status_aendern(db, erster.id, "storniert", "doppelt")
    assert _akte(w)["auftrag_id"] == zweiter.id  # der storniert zählt für die Vorwahl nicht
    assert _akte(w, auftrag=erster.id)["auftrag_id"] == erster.id  # gewählt bleibt gewählt
    fremd = beauftragen(db, make_quote(db, is_consumer=False, number="0548d"))
    antwort = w["client"](db, *ROUTER).get(f"/api/projects/{erster.project_id}/akte", params={"auftrag": fremd.id})
    assert antwort.status_code == 404


def test_was_ansteht_termine_und_zaehler(welt):  # noqa: F811
    w = welt
    db, order = w["db"], w["order"]
    rechnung = create_abschlag_leistungsstand(db, order, due_date=w["heute"] - timedelta(days=20))
    update_invoice_item(db, rechnung, rechnung.items[0], ist_quantity=Decimal("1"))
    festschreiben(db, rechnung)
    bericht = ServiceReport(order_id=order.id, report_type="rapport", performed_at=w["heute"] - timedelta(days=3))
    db.add(bericht); db.flush()
    db.add(Finding(service_report_id=bericht.id, description="Kehle undicht\nmehr Text", severity="mittel", action="reparatur", status="offen",
                   created_by_name="Tom Monteur"))
    besitzer = AppUser(username="olga548", display_name="Olga", role="buero_auftrag", password_hash="x")
    db.add(besitzer); db.flush()
    morgen = datetime.combine(w["heute"] + timedelta(days=1), datetime.min.time())
    db.add_all([CalendarEvent(title="Lieferung Klempnermaterial", start_at=morgen.replace(hour=7, minute=30), end_at=morgen.replace(hour=8),
                              owner_user_id=besitzer.id, project_id=order.project_id, location="an der Baustelle"),
                CalendarEvent(title="Arzt", start_at=morgen.replace(hour=9), end_at=morgen.replace(hour=10), owner_user_id=besitzer.id,
                              project_id=order.project_id, is_private=True),
                CalendarEvent(title="Vorbei", start_at=morgen - timedelta(days=5), end_at=morgen - timedelta(days=5) + timedelta(hours=1),
                              owner_user_id=besitzer.id, project_id=order.project_id)])
    db.commit()
    a = _akte(w)
    arten = [x["art"] for x in a["ansteht"]]
    assert "ueberfaellig" in arten and "befund" in arten
    ueber = next(x for x in a["ansteht"] if x["art"] == "ueberfaellig")
    assert ueber["geld"] is True and ueber["href"] == "/mahnwesen" and rechnung.invoice_number in ueber["unter"]
    befund = next(x for x in a["ansteht"] if x["art"] == "befund")
    assert befund["titel"] == "Befund prüfen: Kehle undicht" and befund["href"] == f"/service-reports/{bericht.id}"
    titel = [t["titel"] for t in a["termine"]]
    assert titel[:2] == ["Lieferung Klempnermaterial", "Belegt"] and "Vorbei" not in titel  # fremder privater Termin nur „Belegt“
    assert a["termine"][0]["unter"] == "07:30 · an der Baustelle · Termin"
    assert a["zaehler"]["rechnungen"] == 1 and a["zaehler"]["leistungen"] == len(order.items) and a["zaehler"]["angebote"] == 1
    assert a["befunde"][0]["service_report_id"] == bericht.id
    assert a["ausfuehrung"]["berichte"][0]["id"] == bericht.id


def test_auftragsdaten_nach_der_schlussrechnung_f2(welt):  # noqa: F811
    w = welt
    db, order = w["db"], w["order"]
    client = w["client"](db, *ROUTER)
    assert client.put(f"/api/orders/{order.id}", json={"title": "Vorher änderbar"}).status_code == 200
    festschreiben(db, create_schlussrechnung(db, order))
    for feld, wert in (("title", "Neu"), ("execution_period", "KW 1"), ("payment_terms", "sofort"), ("intro_text", "x")):
        antwort = client.put(f"/api/orders/{order.id}", json={feld: wert})
        assert antwort.status_code == 409 and "Sachbearbeiter und Bemerkungen bleiben änderbar" in antwort.json()["detail"], feld
    antwort = client.put(f"/api/orders/{order.id}", json={"remarks": "nach der Schlussrechnung", "caseworker_employee_id": None})
    assert antwort.status_code == 200 and antwort.json()["remarks"] == "nach der Schlussrechnung"
    assert antwort.json()["order_lock"]  # die Seite sperrt danach die Felder des Dokuments


def test_summen_je_titel_und_rechnungsliste(welt):  # noqa: F811
    w = welt
    db, order = w["db"], w["order"]
    oben = OrderSection(order_id=order.id, title="Dach", sort_order=1, section_number="1")
    db.add(oben); db.flush()
    unten = OrderSection(order_id=order.id, parent_id=oben.id, title="Rinne", sort_order=1, section_number="1.1")
    db.add(unten); db.flush()
    p1, p2 = OrderItem(order_id=order.id, section_id=oben.id, sort_order=90, position_number="9", short_text="A", quantity=Decimal("2"),
                       unit="m", unit_price=Decimal("10")), OrderItem(order_id=order.id, section_id=unten.id, sort_order=91, position_number="9.1",
                                                                       short_text="B", quantity=Decimal("3"), unit="m", unit_price=Decimal("5"))
    nachtrag = OrderItem(order_id=order.id, sort_order=99, position_number="N1", short_text="N", quantity=Decimal("1"), unit="psch",
                         unit_price=Decimal("7"), is_addendum=True)
    db.add_all([p1, p2, nachtrag]); db.commit()
    daten = w["client"](db, *ROUTER).get(f"/api/orders/{order.id}").json()
    assert {k: Decimal(str(v)) for k, v in daten["section_totals"].items()} == {
        str(oben.id): Decimal("35.00"), str(unten.id): Decimal("15.00"), "nachtraege": Decimal("7.00")}
    monteurin = w["client"](db, *ROUTER, role="field", employee_id=w["mia"].id).get(f"/api/orders/{order.id}")
    assert "section_totals" not in (monteurin.json() if monteurin.status_code == 200 else {})
    rechnung = create_abschlag_leistungsstand(db, order)
    update_invoice_item(db, rechnung, rechnung.items[0], ist_quantity=Decimal("1"))
    festschreiben(db, rechnung)
    zeilen = w["client"](db, *ROUTER).get(f"/api/projects/{order.project_id}/invoices").json()
    assert zeilen[0]["art_text"] == "1. Abschlag nach Leistungsstand" and zeilen[0]["project_id"] == order.project_id
    assert Decimal(str(zeilen[0]["net_total"])) > 0 and zeilen[0]["service_period_start"]
    am_auftrag = w["client"](db, *ROUTER).get(f"/api/orders/{order.id}/invoices").json()
    assert am_auftrag[0]["art_text"] == "1. Abschlag nach Leistungsstand"


@pytest.mark.parametrize("art,beschreibung,soll", [("abschlag_leistungsstand", "3. Abschlagsrechnung (nach Leistungsstand)", "3. Abschlag nach Leistungsstand"),
                                                   ("abschlag_pauschal", "2. Abschlagsrechnung", "2. Abschlag"),
                                                   ("abschlag_pauschal", "Abschlag gemäß Zahlungsplan", "Abschlag gemäß Zahlungsplan"),
                                                   ("schluss", None, "Schlussrechnung"), ("storno", None, "Storno")])
def test_rechnungsart_in_worten(art, beschreibung, soll):
    from app.invoices import rechnungsart_text
    assert rechnungsart_text(Invoice(invoice_type=art, progress_description=beschreibung, closes_order=False)) == soll


def test_monteurin_bekommt_keine_akte(welt):  # noqa: F811
    w = welt
    antwort = w["client"](w["db"], *ROUTER, role="field", employee_id=w["mia"].id).get(f"/api/projects/{w['order'].project_id}/akte")
    assert antwort.status_code == 403


def test_alle_buchungen_des_auftrags_l3(welt):  # noqa: F811
    """L3: „Alle Buchungen des Auftrags“ (Akte) zeigt in „Zeiten“ jeden Monat, nicht nur den laufenden; nur für einen Auftrag."""
    from app.routers import zeiten as zeiten_router
    w = welt
    _buchung(w, w["heute"] - timedelta(days=70), hours="3")
    _buchung(w, w["heute"], hours="2")
    client = w["client"](w["db"], zeiten_router.router, role="buero_auftrag")
    monat = client.get("/api/zeiten/buchungen", params={"auftrag": w["order"].id}).json()
    alle = client.get("/api/zeiten/buchungen", params={"auftrag": w["order"].id, "zeitraum": "alle"}).json()
    assert (monat["zeitraum"], len(monat["eintraege"])) == ("monat", 1)
    assert (alle["zeitraum"], alle["titel"], len(alle["eintraege"]), Decimal(str(alle["summe"]))) == ("alle", "alle Monate", 2, Decimal("5"))
    assert client.get("/api/zeiten/buchungen", params={"zeitraum": "alle"}).status_code == 422  # ohne Auftrag
    assert client.get("/api/zeiten/buchungen", params={"auftrag": w["order"].id, "zeitraum": "jahr"}).status_code == 422


def test_mustervorgang_ohne_hauptaktion(welt):  # noqa: F811
    """Ein Mustervorgang wird nicht beauftragt (seit 1.9.117) -- die Akte bietet ihm keine Hauptaktion an, auch mit Angebot (Fund der
    Klicktests 1.9.129: bis dahin „Beauftragen“, der Dialog im Angebot öffnete sich und scheiterte erst mit 409)."""
    from app.akte import hauptaktion

    w = welt
    muster = _projekt(w["db"], "548m", angebot=True)
    muster.is_template = True
    w["db"].commit()
    a = w["client"](w["db"], *ROUTER).get(f"/api/projects/{muster.id}/akte").json()
    assert (a["hauptaktion"], a["phasen"]["phase"]) == (None, "angebot")
    assert hauptaktion("auftrag", hat_angebot=True, verweigert=False, geschlossen=False, geld=True, muster=True) is None
