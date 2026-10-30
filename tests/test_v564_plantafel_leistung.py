"""Version 1.9.144 (Stufe 6, R1, Punkt 2): die Plantafel lädt keine ganze Auftragsliste mehr.

    Auswahl      GET /api/planning/auftraege nur offene Aufträge, nur Nummer und Projekt, eine Abfrage -- beim Öffnen des Dialogs, nicht beim Laden der Tafel
    Abfragen     GET /api/planning: die Zahl der Abfragen hängt nicht an der Zahl der Aufträge im Rückstand, der Einsätze im Bild und der alten Einsätze
    Konflikte    nur für Einsätze, die den Zeitraum berühren -- auch gegen einen, der mit ihnen über den Rand hinaus zusammenfällt
    Rückstand    wie bisher: offene Aufträge ohne Einsatz, Soll aus der Kalkulation, Begründung der Pause, Vorschlag aus AV oder Auftrag
"""

from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import event

from app.auftragsstatus import status_aendern
from app.main import create_team
from app.models import Customer, Employee, Order, OrderItem, OrderItemCalculationSnapshot, Project, WorkPreparation
from app.planning import create_slot, planning_board
from app.project_pipeline_columns import default_pipeline_column_id
from app.routers.planning import router as planning_router
from app.schemas import TeamCreate, TeamEmployeeInput

ROOT = Path(__file__).resolve().parent.parent
MONTAG = date(2026, 11, 2)
ZAEHLER = [0]


def _auftrag(db, minuten="6", menge="10", status="laeuft"):
    ZAEHLER[0] += 1
    n = ZAEHLER[0]
    kunde = Customer(name=f"Kunde {n}", last_name=f"Kunde {n}")
    db.add(kunde)
    db.flush()
    projekt = Project(project_number=f"P-{n}", name=f"Dach {n}", customer_id=kunde.id, pipeline_column_id=default_pipeline_column_id(db), status="angebot")
    db.add(projekt)
    db.flush()
    order = Order(order_number=f"AUF-{n}", project_id=projekt.id, source_quote_id=n, quote_number_snapshot=f"A-{n}", title="Sanierung", vat_rate=Decimal("19"),
                  customer_name=kunde.name, customer_number=f"K-{n}", status=status, property_address="Dachweg 1\n52531 Uebach")
    db.add(order)
    db.flush()
    item = OrderItem(order_id=order.id, sort_order=10, position_number="1", short_text="Eindecken", quantity=Decimal(menge), unit="m²", unit_price=Decimal("50"))
    db.add(item)
    db.flush()
    db.add(OrderItemCalculationSnapshot(order_item_id=item.id, site_time_minutes=Decimal(minuten), workshop_time_minutes=Decimal("0")))
    db.commit()
    return order


def _kolonne(db, name):
    emp = Employee(employee_number=f"M-{name}", first_name=name, last_name="Test", employee_group="gewerblich", weekly_hours=Decimal("40"), active=True)
    db.add(emp)
    db.commit()
    return create_team(TeamCreate(team_number=name, name=f"Kolonne {name}", employees=[TeamEmployeeInput(employee_id=emp.id, role="Monteur")], resources=[]), db)


@pytest.fixture()
def tafel(threaded_db_session, router_test_client):
    db = threaded_db_session
    return db, router_test_client(db, planning_router)


class Zaehler:
    def __init__(self, db):
        self.bind, self.anzahl = db.get_bind(), 0

    def _plus(self, *_args):
        self.anzahl += 1

    def __enter__(self):
        event.listen(self.bind, "before_cursor_execute", self._plus)
        return self

    def __exit__(self, *_args):
        event.remove(self.bind, "before_cursor_execute", self._plus)


def _abfragen(db, client, von=MONTAG):
    db.expire_all()
    with Zaehler(db) as z:
        antwort = client.get("/api/planning", params={"start": von.isoformat(), "end": (von + timedelta(days=13)).isoformat()})
    assert antwort.status_code == 200, antwort.text
    return z.anzahl, antwort.json()


def test_auswahl_nur_offene_auftraege_nur_was_sie_zeigt_eine_abfrage(tafel):
    db, client = tafel
    laeuft, pausiert = _auftrag(db), _auftrag(db, status="pausiert")
    _auftrag(db, status="abgeschlossen"), _auftrag(db, status="storniert"), _auftrag(db, status=" Storniert ")
    db.expire_all()
    with Zaehler(db) as z:
        antwort = client.get("/api/planning/auftraege")
    assert antwort.status_code == 200
    assert z.anzahl == 1
    daten = antwort.json()
    assert [x["id"] for x in daten] == [pausiert.id, laeuft.id]
    assert set(daten[0]) == {"id", "order_number", "project_number", "project_name"}


def test_auftrag_ohne_status_gilt_als_offen(tafel):
    db, client = tafel
    order = _auftrag(db, status=None)
    assert order.id in {x["id"] for x in client.get("/api/planning/auftraege").json()}


def test_monteur_bekommt_die_auswahl_nicht(threaded_db_session, router_test_client):
    client = router_test_client(threaded_db_session, planning_router, role="field")
    assert client.get("/api/planning/auftraege").status_code == 403


def test_tafel_laedt_keine_auftragsliste_die_auswahl_laedt_der_dialog():
    html = (ROOT / "app/templates/planning.html").read_text(encoding="utf-8")
    lade = html[html.index("async function loadBoard()"):]
    lade = lade[:lade.index("\n")]
    assert "api('/api/orders')" not in html
    assert "/api/planning?start=" in lade and "/api/planning/auftraege" not in lade
    dialog = html[html.index("async function openCreate("):]
    assert "api('/api/planning/auftraege')" in dialog[:dialog.index("\n")]


def test_abfragen_haengen_nicht_am_rueckstand(tafel):
    db, client = tafel
    _kolonne(db, "A")
    _auftrag(db)
    wenige, daten = _abfragen(db, client)
    assert len(daten["backlog"]) == 1
    for _ in range(15):
        _auftrag(db)
    _auftrag(db, status="pausiert")
    viele, daten = _abfragen(db, client)
    assert len(daten["backlog"]) == 17
    assert viele <= wenige + 1, (wenige, viele)  # höchstens die eine Abfrage der Begründungen dazu


def test_abfragen_haengen_nicht_an_den_einsaetzen_im_bild(tafel):
    db, client = tafel
    teams = [_kolonne(db, n) for n in "ABCD"]
    create_slot(db, order_id=_auftrag(db).id, team_id=teams[0].id, start_date=MONTAG, end_date=MONTAG)
    wenige, _ = _abfragen(db, client)
    for tag in range(1, 8):
        for team in teams[1:]:
            create_slot(db, order_id=_auftrag(db).id, team_id=team.id, start_date=MONTAG + timedelta(days=tag), end_date=MONTAG + timedelta(days=tag), trotzdem_planen=True)
    viele, daten = _abfragen(db, client)
    assert len(daten["slots"]) == 22
    assert viele <= wenige + 2, (wenige, viele)


def test_alte_einsaetze_kosten_nichts(tafel):
    db, client = tafel
    a, b = _kolonne(db, "A"), _kolonne(db, "B")
    create_slot(db, order_id=_auftrag(db).id, team_id=a.id, start_date=MONTAG, end_date=MONTAG)
    ohne, _ = _abfragen(db, client)
    for woche in range(1, 11):
        tag = MONTAG - timedelta(weeks=woche)
        create_slot(db, order_id=_auftrag(db).id, team_id=a.id, start_date=tag, end_date=tag)
        create_slot(db, order_id=_auftrag(db).id, team_id=a.id, start_date=tag, end_date=tag, trotzdem_planen=True)
    mit, daten = _abfragen(db, client)
    assert mit == ohne, (ohne, mit)
    assert daten["conflict_count"] == 0


def test_konflikte_nur_fuer_einsaetze_im_zeitraum(tafel, monkeypatch):
    """Die Rechnung bekommt die alten Einsätze gar nicht."""
    import app.planning as planung

    db, _ = tafel
    a = _kolonne(db, "A")
    im_bild = create_slot(db, order_id=_auftrag(db).id, team_id=a.id, start_date=MONTAG, end_date=MONTAG)
    alt = create_slot(db, order_id=_auftrag(db).id, team_id=a.id, start_date=MONTAG - timedelta(days=30), end_date=MONTAG - timedelta(days=30))
    gesehen = []
    echt = planung._conflicts

    def _mitschreiben(db_, slots, *args, **kwargs):
        gesehen.append({s.id for s in slots})
        return echt(db_, slots, *args, **kwargs)

    monkeypatch.setattr(planung, "_conflicts", _mitschreiben)
    planning_board(db, MONTAG, MONTAG + timedelta(days=13))
    assert gesehen == [{im_bild.id}]
    assert alt.id not in gesehen[0]


def test_konflikt_ueber_den_rand_des_zeitraums_bleibt(tafel):
    """Einsatz A läuft über das Ende des Zeitraums hinaus, Einsatz B beginnt erst danach: A meldet ihn trotzdem."""
    db, client = tafel
    a = _kolonne(db, "A")
    ende = MONTAG + timedelta(days=13)
    lang = create_slot(db, order_id=_auftrag(db).id, team_id=a.id, start_date=ende - timedelta(days=1), end_date=ende + timedelta(days=5))
    danach = create_slot(db, order_id=_auftrag(db).id, team_id=a.id, start_date=ende + timedelta(days=3), end_date=ende + timedelta(days=4), trotzdem_planen=True)
    _, daten = _abfragen(db, client)
    assert [s["id"] for s in daten["slots"]] == [lang.id]
    assert ("team", danach.id) in [(k["type"], k["other_slot_id"]) for k in daten["slots"][0]["conflicts"]]


def test_rueckstand_wie_bisher(tafel):
    db, client = tafel
    a = _kolonne(db, "A")
    frei = _auftrag(db, minuten="90", menge="10")  # 15 h Soll
    mit_av = _auftrag(db)
    db.add(WorkPreparation(order_id=mit_av.id, status="offen", planned_start=date(2026, 12, 1), planned_end=date(2026, 12, 3)))
    db.commit()
    pause = _auftrag(db)
    status_aendern(db, pause.id, "pausiert", "Gerüst fehlt")
    eingeplant = _auftrag(db)
    create_slot(db, order_id=eingeplant.id, team_id=a.id, start_date=MONTAG, end_date=MONTAG)
    schon_alt = _auftrag(db)
    create_slot(db, order_id=schon_alt.id, team_id=a.id, start_date=MONTAG - timedelta(days=90), end_date=MONTAG - timedelta(days=90))
    _auftrag(db, status="abgeschlossen"), _auftrag(db, status="storniert")
    _, daten = _abfragen(db, client)
    je_id = {z["order_id"]: z for z in daten["backlog"]}
    assert set(je_id) == {frei.id, mit_av.id, pause.id}
    assert Decimal(str(je_id[frei.id]["planned_hours"])) == Decimal("15")
    assert je_id[frei.id]["property_address"] == "Dachweg 1, 52531 Uebach"
    assert (je_id[mit_av.id]["suggested_start"], je_id[mit_av.id]["suggested_end"]) == ("2026-12-01", "2026-12-03")
    assert (je_id[pause.id]["order_status"], je_id[pause.id]["order_status_reason"]) == ("pausiert", "Gerüst fehlt")
    assert je_id[frei.id]["order_status_reason"] is None


def test_pausierter_einsatz_nennt_seine_begruendung_ohne_eigene_abfrage(tafel):
    db, client = tafel
    a = _kolonne(db, "A")
    pause = _auftrag(db)
    create_slot(db, order_id=pause.id, team_id=a.id, start_date=MONTAG, end_date=MONTAG)
    status_aendern(db, pause.id, "pausiert", "Gerüst fehlt")
    status_aendern(db, pause.id, "laeuft", None)
    status_aendern(db, pause.id, "pausiert", "Regen")
    _, daten = _abfragen(db, client)
    assert (daten["slots"][0]["order_status"], daten["slots"][0]["order_status_reason"]) == ("pausiert", "Regen")
    status_aendern(db, pause.id, "laeuft", None)
    _, daten = _abfragen(db, client)
    assert daten["slots"][0]["order_status_reason"] is None
