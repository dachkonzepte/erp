"""Zahlen der Akte je Auftrag (seit 1.9.126, Stufe 5, R2, Punkt 1; Befund F18, F19, F21; app/akte.py, Vorlage
bildgrundlage/entwurf_stufe5/akte-uebersicht.html und akte-leistungen.html).

- Leistung netto: Auftragssumme mit Nachträgen (nur „in Summe“), abgerechnet = Summe der festgeschriebenen Rechnungen ohne Stornos und
  stornierte, noch nicht abgerechnet; nach der abschließenden Rechnung nichts mehr „noch nicht abgerechnet“.
- Zahlung brutto: in Rechnung gestellt, bezahlt, unbezahlt, überfällig -- je Rechnung derselbe Stand wie in Finanzen.
- Stunden: Soll nur aus Positionen „in Summe“ (F18), gebucht (alle Zeitarten, ein laufender Timer nicht), Fahrzeit, Baustelle & Werkstatt;
  dieselben Zahlen in der Arbeitsvorbereitung (F19) und in GET /api/orders (F21).
- Je Position: abgerechnete Menge aus der zuletzt festgeschriebenen Rechnung (ein Storno nimmt den Stand zurück), Std. Ist/Soll.
Jede Zahl wird im Test aus den Rechnungen bzw. Buchungen nachgerechnet, nicht nur gegen eine feste Zahl geprüft."""

from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.akte import soll_stunden, zahlen
from app.berlin_time import berlin_today
from app.invoices import (
    create_abschlag_leistungsstand, create_schlussrechnung, create_storno_draft, invoice_to_dict, list_invoices_for_order,
    update_invoice_item,
)
from app.models import Employee, Invoice, Order, OrderItem, OrderItemCalculationSnapshot, TimeEntry
from app.routers import orders as orders_router
from app.routers import projects as projects_router
from app.routers import work_preparation as work_preparation_router
from app.time_tracking import create_manual_entry, start_timer
from app.work_preparation import planned_hours
from tests.leistungszeitraum import festschreiben
from tests.test_v381_zahlungen import _auftrag, _buchen, _db

D = Decimal
HEUTE = berlin_today()


def _mitarbeiter(db, nummer, vorname, nachname):
    e = Employee(employee_number=nummer, first_name=vorname, last_name=nachname, employee_group="gewerblich", hourly_wage=D("20"),
                 weekly_hours=D("40"), active=True)
    db.add(e)
    db.flush()
    return e


def _position(db, order, nummer, menge, preis, *, in_summe=True, nachtrag=False, minuten=None):
    item = OrderItem(order_id=order.id, sort_order=10 + 10 * len(order.items), position_number=nummer, short_text=f"Position {nummer}",
                     quantity=D(menge), unit="m²", unit_price=D(preis), include_in_total=in_summe, is_addendum=nachtrag)
    db.add(item)
    db.flush()
    if minuten is not None:
        db.add(OrderItemCalculationSnapshot(order_item_id=item.id, site_time_minutes=D(minuten[0]), workshop_time_minutes=D(minuten[1])))
    return item


def _ist(db, invoice, mengen):
    for inv_item in list(invoice.items):
        if inv_item.source_order_item_id in mengen:
            update_invoice_item(db, invoice, inv_item, ist_quantity=D(mengen[inv_item.source_order_item_id]))
    return invoice


def _welt(db=None):
    """Auftrag 1 (100 m² × 50 €, Kalkulation 30 + 15 min), 2 (10 × 200 €, 60 min), Bedarfsposition außerhalb der Summe (5 × 100 €, 60 min),
    Nachtrag N1 (2 × 150 €, ohne Kalkulation). Zwei Abschläge festgeschrieben (der erste bezahlt, der zweite teilweise und überfällig), ein
    dritter festgeschrieben und storniert, ein vierter im Entwurf. Buchungen beider Mitarbeiter in allen Zeitarten, ein laufender Timer."""
    if db is None:
        db = _db()
    else:  # threaded_db_session (TestClient): Grunddaten wie in _db()
        from app.grunddaten import anlegen
        anlegen(db)
        db.commit()
    order = _auftrag(db, quantity="100", price="50")
    p1 = order.items[0]
    db.add(OrderItemCalculationSnapshot(order_item_id=p1.id, site_time_minutes=D("30"), workshop_time_minutes=D("15")))
    p2 = _position(db, order, "2", "10", "200", minuten=("60", "0"))
    bedarf = _position(db, order, "3", "5", "100", in_summe=False, minuten=("60", "0"))
    n1 = _position(db, order, "N1", "2", "150", nachtrag=True)
    db.commit()
    order = db.get(Order, order.id)
    db.refresh(order)

    a1 = festschreiben(db, _ist(db, create_abschlag_leistungsstand(db, order), {p1.id: "40", p2.id: "5"}))
    _buchen(db, a1, str(invoice_to_dict(a1)["gross_total"]))
    a2 = festschreiben(db, _ist(db, create_abschlag_leistungsstand(db, db.get(Order, order.id), due_date=HEUTE - timedelta(days=20)),
                                {p1.id: "70", p2.id: "5", n1.id: "2"}))
    _buchen(db, a2, "500")
    a3 = festschreiben(db, _ist(db, create_abschlag_leistungsstand(db, db.get(Order, order.id)), {p1.id: "90", p2.id: "5", n1.id: "2"}))
    festschreiben(db, create_storno_draft(db, db.get(Invoice, a3.id)))
    _ist(db, create_abschlag_leistungsstand(db, db.get(Order, order.id)), {p1.id: "100", p2.id: "10", n1.id: "2"})  # Entwurf zählt nicht

    mia = _mitarbeiter(db, "MA-A1", "Mia", "Monteurin")
    tom = _mitarbeiter(db, "MA-A2", "Tom", "Monteur")
    tag1, tag2, tag3 = date(2026, 9, 7), date(2026, 9, 8), date(2026, 9, 9)
    for emp, tag_, h, art, pos in [(mia, tag1, "8", "site", p1), (mia, tag1, "1", "travel", None), (mia, tag2, "2", "workshop", p2),
                                   (tom, tag1, "6.5", "site", None), (tom, tag2, "1", "other", p1), (tom, tag3, "2", "weather_winter", None),
                                   (tom, tag3, "0.75", "travel", None)]:
        create_manual_entry(db, employee_id=emp.id, order_id=order.id, order_item_id=pos.id if pos else None, work_date=tag_, hours=D(h),
                            entry_type=art)
    start_timer(db, employee_id=mia.id, order_id=order.id, entry_type="site", started_at=datetime(2026, 9, 10, 7, 0))
    return {"db": db, "order": db.get(Order, order.id), "p1": p1, "p2": p2, "bedarf": bedarf, "n1": n1, "a1": a1, "a2": a2, "a3": a3,
            "mia": mia, "tom": tom}


def _gueltig(db, order):
    return [i for i in list_invoices_for_order(db, order.id) if i.status == "versendet" and i.invoice_type != "storno"]


def test_leistung_ist_die_summe_der_rechnungen():
    w = _welt()
    db, order = w["db"], w["order"]
    z = zahlen(db, order)["leistung"]
    # nachgerechnet: Auftragssumme aus den Positionen in der Summe, abgerechnet aus den Rechnungen selbst
    summe = sum((i.quantity * i.unit_price for i in order.items if i.include_in_total), D("0"))
    abgerechnet = sum((D(str(invoice_to_dict(i)["net_total"])) for i in _gueltig(db, order)), D("0"))
    assert z["auftragssumme"] == summe == D("7300.00")  # 5.000 + 2.000 + Nachtrag 300, die Bedarfsposition nicht
    assert z["nachtraege"] == D("300.00")
    assert z["abgerechnet"] == abgerechnet == D("4800.00")  # 3.000 + 1.800; storniert, Storno und Entwurf nicht
    assert z["noch_nicht_abgerechnet"] == summe - abgerechnet == D("2500.00")
    assert z["abgerechnet_prozent"] == 66
    assert (z["vollstaendig"], z["unter_auftragssumme"], z["ueber_auftragssumme"]) == (False, D("0"), D("0"))


def test_zahlung_ist_die_summe_der_rechnungen_wie_in_finanzen():
    w = _welt()
    db, order = w["db"], w["order"]
    z = zahlen(db, order)["zahlung"]
    gueltig = [invoice_to_dict(i) for i in _gueltig(db, order)]
    assert z["rechnungen"] == len(gueltig) == 2
    assert z["in_rechnung"] == sum((D(str(r["gross_total"])) for r in gueltig), D("0")) == D("5712.00")  # 3.570 + 2.142
    assert z["bezahlt"] == sum((D(str(r["payment"]["paid"])) for r in gueltig), D("0")) == D("4070.00")
    assert z["unbezahlt"] == sum((D(str(r["overview"]["open"])) for r in gueltig), D("0")) == D("1642.00")
    assert z["in_rechnung"] == z["bezahlt"] + z["skonto"] + z["unbezahlt"]
    a2 = next(r for r in gueltig if r["id"] == w["a2"].id)
    assert a2["is_overdue"]
    assert (z["ueberfaellig"], z["ueberfaellig_seit"]) == (D("1642.00"), a2["due_date"])
    assert z["bezahlt_prozent"] == 71


def test_stunden_sind_die_summe_der_buchungen():
    w = _welt()
    db, order = w["db"], w["order"]
    z = zahlen(db, order)["stunden"]
    gebucht = db.scalars(select(TimeEntry).where(TimeEntry.order_id == order.id, TimeEntry.status == "booked")).all()
    assert z["gebucht"] == sum((e.hours for e in gebucht), D("0")) == D("21.25")  # der laufende Timer trägt nichts
    assert z["fahrzeit"] == sum((e.hours for e in gebucht if e.entry_type == "travel"), D("0")) == D("1.75")
    assert z["baustelle_werkstatt"] == sum((e.hours for e in gebucht if e.entry_type in ("site", "workshop")), D("0")) == D("16.50")
    assert z["ohne_position"] == D("6.50")
    # Soll nur aus den Positionen in der Summe: (30 + 15) / 60 × 100 + 60 / 60 × 10 -- die Bedarfsposition (5 h) zählt nicht (F18)
    assert z["soll"] == D("85.00")
    assert (z["abweichung"], z["prozent_vom_soll"]) == (D("-68.50"), 19)
    mia, tom = w["mia"], w["tom"]
    assert z["mitarbeiter"] == [
        {"employee_id": mia.id, "name": "Mia Monteurin", "tage": 2, "fahrzeit": D("1.00"), "stunden": D("11.00")},
        {"employee_id": tom.id, "name": "Tom Monteur", "tage": 3, "fahrzeit": D("0.75"), "stunden": D("10.25")},
    ]
    assert sum((m["stunden"] for m in z["mitarbeiter"]), D("0")) == z["gebucht"]


def test_je_position_stand_der_letzten_rechnung_und_stunden():
    w = _welt()
    db, order = w["db"], w["order"]
    z = zahlen(db, order)["positionen"]
    zeilen = {x["item_id"]: x for x in z["zeilen"]}
    # Stand aus dem 2. Abschlag: der dritte ist storniert (sein Stand gilt nicht), der vierte ein Entwurf
    assert z["quelle"]["invoice_id"] == w["a2"].id
    assert (zeilen[w["p1"].id]["abgerechnet_menge"], zeilen[w["p1"].id]["abgerechnet_prozent"]) == (D("70"), 70)
    assert (zeilen[w["p2"].id]["abgerechnet_menge"], zeilen[w["p2"].id]["abgerechnet_prozent"]) == (D("5"), 50)
    assert (zeilen[w["n1"].id]["abgerechnet_menge"], zeilen[w["n1"].id]["abgerechnet_prozent"]) == (D("2"), 100)
    assert zeilen[w["bedarf"].id]["abgerechnet_menge"] == D("0")
    # Std. Ist: Baustelle und Werkstatt mit Bezug auf die Position; „Sonstige“ auf Position 1 zählt nicht
    assert (zeilen[w["p1"].id]["stunden_ist"], zeilen[w["p1"].id]["stunden_soll"]) == (D("8.00"), D("75.00"))
    assert (zeilen[w["p2"].id]["stunden_ist"], zeilen[w["p2"].id]["stunden_soll"]) == (D("2.00"), D("10.00"))
    assert zeilen[w["n1"].id]["stunden_soll"] is None  # ohne Kalkulation: „–“
    st = zahlen(db, order)["stunden"]
    assert sum((x["stunden_ist"] for x in z["zeilen"]), D("0")) + st["ohne_position"] == st["baustelle_werkstatt"]


def test_nach_der_schlussrechnung_nichts_mehr_noch_nicht_abgerechnet():
    db = _db()
    order = _auftrag(db, quantity="100", price="50")
    schluss = create_schlussrechnung(db, order)
    update_invoice_item(db, schluss, schluss.items[0], ist_quantity=D("90"))
    festschreiben(db, schluss)
    z = zahlen(db, db.get(Order, order.id))["leistung"]
    assert (z["vollstaendig"], z["abgerechnet"], z["noch_nicht_abgerechnet"], z["unter_auftragssumme"]) == (
        True, D("4500.00"), D("0"), D("500.00"))


def test_ohne_rechnung_und_buchung_alles_null():
    db = _db()
    order = _auftrag(db)
    z = zahlen(db, order)
    assert z["leistung"]["abgerechnet"] == 0 and z["leistung"]["noch_nicht_abgerechnet"] == D("5000.00")
    assert (z["zahlung"]["rechnungen"], z["zahlung"]["in_rechnung"], z["zahlung"]["bezahlt_prozent"]) == (0, 0, None)
    assert (z["stunden"]["gebucht"], z["stunden"]["soll"], z["stunden"]["prozent_vom_soll"], z["stunden"]["mitarbeiter"]) == (0, 0, None, [])
    assert z["positionen"]["quelle"] is None


def test_arbeitsvorbereitung_plantafel_und_listen_dieselben_zahlen(router_test_client, threaded_db_session):
    """F18, F19, F21: die Arbeitsvorbereitung, GET /api/orders und die Aufträge des Projekts zeigen dieselben Stunden und Beträge."""
    w = _welt(threaded_db_session)
    db, order = w["db"], w["order"]
    z = zahlen(db, order)
    assert planned_hours(order) == soll_stunden(order) == z["stunden"]["soll"]
    client = router_test_client(db, orders_router.router, projects_router.router, work_preparation_router.router)
    av = client.get(f"/api/orders/{order.id}/work-preparation").json()
    assert D(str(av["planned_total_hours"])) == z["stunden"]["soll"]
    assert D(str(av["actual_total_hours"])) == z["stunden"]["baustelle_werkstatt"]
    assert D(str(av["actual_all_hours"])) == z["stunden"]["gebucht"]
    assert D(str(av["actual_travel_hours"])) == z["stunden"]["fahrzeit"]
    assert D(str(av["hours_variance"])) == z["stunden"]["abweichung"]
    assert {int(k): D(str(v)) for k, v in av["order_item_actual_hours"].items() if D(str(v))} == {
        x["item_id"]: x["stunden_ist"] for x in z["positionen"]["zeilen"] if x["stunden_ist"]}
    for liste in (client.get("/api/orders").json(), client.get(f"/api/projects/{order.project_id}/orders").json()):
        zeile = next(x for x in liste if x["id"] == order.id)
        assert D(str(zeile["invoiced_net"])) == z["leistung"]["abgerechnet"]
        assert D(str(zeile["invoiced_gross"])) == z["zahlung"]["in_rechnung"]
        assert D(str(zeile["planned_hours"])) == z["stunden"]["soll"]


def test_endpunkt_zahlen_buero_200_monteurin_403(router_test_client, threaded_db_session):
    w = _welt(threaded_db_session)
    db, order = w["db"], w["order"]
    for rolle in ("buero_auftrag", "buero_finanzen", "admin"):
        antwort = router_test_client(db, orders_router.router, role=rolle).get(f"/api/orders/{order.id}/zahlen")
        assert antwort.status_code == 200, rolle
        body = antwort.json()
        assert D(str(body["leistung"]["abgerechnet"])) == D("4800.00")
        assert D(str(body["zahlung"]["unbezahlt"])) == D("1642.00")
        assert D(str(body["stunden"]["soll"])) == D("85.00")
    monteurin = router_test_client(db, orders_router.router, role="field", employee_id=w["mia"].id)
    assert monteurin.get(f"/api/orders/{order.id}/zahlen").status_code == 403
    assert router_test_client(db, orders_router.router).get("/api/orders/999999/zahlen").status_code == 404
