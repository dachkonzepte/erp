"""Version 1.9.288 (Stufe 6, R5d, Punkt 6): „Nicht eingeplant“ zeigt die Stunden wie „Aufträge“ und die Akte.

    Stunden   app/planning.py::rueckstand() liefert `stunden` aus app/auftragsliste.py::stunden_zeile() -- „Soll …“, solange nichts gebucht ist, dann „Rest …“
              (Soll minus gebuchte Baustelle & Werkstatt), „nach Aufwand“ ohne Soll, „Wartungsvertrag“; bis 1.9.287 zeigte die Liste immer „Soll <Planstunden>
              h“ (auch „Soll 0,00 h“ für einen Auftrag nach Aufwand, „Soll 8,00 h“ für einen mit 3,5 h gebucht). Gebucht und Herkunft Wartungsvertrag über
              dieselben Abfragen wie die Auftragsliste (gebuchte_stunden(), aus_wartungsvertrag()) -- je eine, fest
Der Klicktest scripts/klicktest_plantafel_rueckgaengig.py zeigt „Nicht eingeplant“ mit „Soll 6,00 h“ wie „Aufträge“.
"""

from datetime import timedelta
from decimal import Decimal

from app.auftragsliste import auftragsliste
from app.models import Employee, ProjectProfile, TimeEntry
from app.planning import rueckstand
from tests.test_v564_plantafel_leistung import MONTAG, _auftrag
from tests.test_v671_inaktive_mitarbeiter_ausblenden import ROOT

D = Decimal


def test_rueckstand_wie_die_auftragsliste(threaded_db_session):
    db = threaded_db_session
    soll = _auftrag(db, minuten="60", menge="8")  # Soll 8 h, nichts gebucht
    rest = _auftrag(db, minuten="60", menge="8")
    aufwand = _auftrag(db, minuten="0")
    wartung = _auftrag(db, minuten="60", menge="2")
    db.add(ProjectProfile(project_id=wartung.project_id, source_maintenance_contract_id=1))
    emp = Employee(first_name="Tom", last_name="Test", employee_group="gewerblich", weekly_hours=D("40"), active=True)
    db.add(emp)
    db.flush()
    for art, h in (("site", "2.5"), ("workshop", "1"), ("travel", "3")):  # Fahrzeit zählt nicht (wie die Akte)
        db.add(TimeEntry(employee_id=emp.id, project_id=rest.project_id, order_id=rest.id, work_date=MONTAG, entry_type=art, hours=D(h), status="booked"))
    # eine laufende Zeit zählt nicht (nur gebuchte, wie die Akte) -- mit Stunden, damit ein fehlender Filter auffiele (Gegenprobe 288_2b)
    db.add(TimeEntry(employee_id=emp.id, project_id=rest.project_id, order_id=rest.id, work_date=MONTAG, entry_type="site", hours=D("2"), status="running"))
    db.commit()
    db.expire_all()
    zeilen = {z["order_id"]: z for z in rueckstand(db)}
    assert {o.id: zeilen[o.id]["stunden"] for o in (soll, rest, aufwand, wartung)} == {
        soll.id: "Soll 8,00 h", rest.id: "Rest 4,50 h", aufwand.id: "nach Aufwand", wartung.id: "Wartungsvertrag"}
    liste = {z["order_id"]: z["stunden"] for z in auftragsliste(db, MONTAG, MONTAG + timedelta(days=6))}
    assert all(zeilen[i]["stunden"] == liste[i] for i in zeilen)  # dieselbe Zeile in beiden Ansichten
    assert zeilen[rest.id]["planned_hours"] == D("8.00")  # die Planstunden bleiben (Dialog, Kapazität)


def test_die_liste_zeigt_die_zeile():
    seite = (ROOT / "app/templates/planning.html").read_text(encoding="utf-8")
    assert "<span class=\"klein\">${esc(x.stunden)} · ${x.suggested_start?" in seite
    assert "Soll ${esc(zahlText(x.planned_hours,2))} h" not in seite
