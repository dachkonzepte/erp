"""Version 1.9.216 (L1a Stufe 6, Punkt 5): Schlechtwetter bekommt Stunden -- abgeleitet, nie gespeichert.

    Stunden     Sollzeit des Tags (app/sollzeit.py) minus die gebuchte Arbeitszeit der Person an dem Tag (alle Zeitarten, nur gebuchte, dieselbe
                Summe wie die Arbeit im Lohn: tagessumme()), nie unter 0 -- app/schlechtwetter.py::ausfall()
    Eintrag     bleibt ein ganzer Ausfalltag ohne Stundenfeld; wird danach gebucht, stimmt die Zahl von selbst
    sichtbar    „Zeiten → Monat & Lohn“ (Spalte Schlechtwetter, auch wer nichts gebucht hat) und die Listen unter „Zeiten“ (Prüfen: offene
                Anträge, Abwesenheiten)

Fester Tag: Mo 07.12.2026 (KW 50, Tarif 7,50 h).
"""

from datetime import date, datetime, time
from decimal import Decimal

import pytest

from app.models import EmployeeAbsence, EmployeeAbsenceRequest, TimeEntry
from app.routers import absence_requests as absence_router
from app.routers import schlechtwetter as schlechtwetter_router
from app.routers import zeiten as zeiten_router
from app.schlechtwetter import ausfall
from app.zeiten import monat
from tests.test_v224_field_view import make_employee
from tests.test_v325_contract_basis import beauftragen, make_quote

MO, DI = date(2026, 12, 7), date(2026, 12, 8)
D = Decimal


@pytest.fixture
def welt(threaded_db_session, router_test_client, fester_tag):
    db = threaded_db_session
    mia, tom = make_employee(db, "M-1", "Mia", "Monteurin"), make_employee(db, "M-2", "Tom", "Monteur")
    order = beauftragen(db, make_quote(db, is_consumer=False, number="0621"))
    db.commit()
    return {"db": db, "mia": mia, "tom": tom, "order": order, "client": router_test_client}


def _ausfalltag(w, emp, tag=MO):
    w["db"].add(EmployeeAbsence(employee_id=emp.id, absence_type="Schlechtwetter", absence_category="schlechtwetter", start_date=tag, end_date=tag))
    w["db"].commit()


def _buchen(w, emp, stunden, tag=MO, art="site", status="booked"):
    o = w["order"]
    w["db"].add(TimeEntry(employee_id=emp.id, project_id=o.project_id, order_id=o.id, work_date=tag, entry_type=art, hours=D(stunden),
                          break_minutes=0, status=status, started_at=datetime.combine(tag, time(7)),
                          ended_at=None if status == "running" else datetime.combine(tag, time(8))))
    w["db"].commit()


def _stunden(w, emp, tag=MO):
    return ausfall(w["db"], [(emp.id, tag)])[(emp.id, tag)]


def test_reiner_ausfalltag_volle_sollzeit(welt):
    a = _stunden(welt, welt["mia"])
    assert (a["soll"], a["gebucht"], a["stunden"], a["text"]) == (D("7.50"), D("0"), D("7.50"), "Ausfall 7,50 h")


def test_gebuchte_arbeit_wird_abgezogen(welt):
    """Baustelle und Werkstatt zusammen (alle Zeitarten, wie die Arbeit im Lohn)."""
    _buchen(welt, welt["mia"], "1.25")
    _buchen(welt, welt["mia"], "0.75", art="workshop")
    a = _stunden(welt, welt["mia"])
    assert (a["gebucht"], a["stunden"], a["text"]) == (D("2.00"), D("5.50"), "Ausfall 5,50 h (Sollzeit 7,50 h − gebucht 2,00 h)")


def test_nie_unter_null(welt):
    _buchen(welt, welt["mia"], "9.25")
    a = _stunden(welt, welt["mia"])
    assert (a["stunden"], a["text"]) == (D("0"), "Ausfall 0,00 h (Sollzeit 7,50 h − gebucht 9,25 h)")


def test_nachher_gebucht_stimmt_von_selbst(welt):
    """Der Eintrag bleibt ein ganzer Tag -- eine laufende Zeit zählt nicht, eine gebuchte sofort, nichts wird gespeichert."""
    _ausfalltag(welt, welt["mia"])
    _buchen(welt, welt["mia"], "3", status="running")
    assert _stunden(welt, welt["mia"])["stunden"] == D("7.50")
    welt["db"].query(TimeEntry).update({"status": "booked"})
    welt["db"].commit()
    assert _stunden(welt, welt["mia"])["stunden"] == D("4.50")
    assert not any("stunde" in c.name or "hours" in c.name for c in EmployeeAbsence.__table__.columns)
    assert not any("stunde" in c.name or "hours" in c.name for c in EmployeeAbsenceRequest.__table__.columns)


def test_andere_tage_und_personen_zaehlen_nicht(welt):
    _buchen(welt, welt["mia"], "4", tag=DI)
    _buchen(welt, welt["tom"], "4")
    assert _stunden(welt, welt["mia"])["stunden"] == D("7.50")


def test_monat_und_lohn(welt):
    """Mia: gebucht und ein Ausfalltag; Tom: nur der Ausfalltag (dazu ein offener Antrag, der nicht zählt) -- steht trotzdem in der Liste; die
    Summe; Arbeit „Zusammen“ ohne Ausfall."""
    db = welt["db"]
    _buchen(welt, welt["mia"], "2", tag=DI)
    _buchen(welt, welt["mia"], "1.5")
    _ausfalltag(welt, welt["mia"])
    _ausfalltag(welt, welt["tom"])
    db.add(EmployeeAbsenceRequest(employee_id=welt["tom"].id, absence_type="Schlechtwetter", absence_category="schlechtwetter", start_date=DI,
                                  end_date=DI, status="pending"))  # offen: zählt in „Monat & Lohn“ nicht
    db.commit()
    d = monat(db, date(2026, 12, 1))
    zeilen = {z["name"]: z for z in d["zeilen"]}
    assert d["schlechtwetter"] is True
    assert (zeilen["Mia Monteurin"]["zusammen"], zeilen["Mia Monteurin"]["schlechtwetter"]) == (D("3.50"), {"tage": 1, "stunden": D("6.00")})
    assert (zeilen["Tom Monteur"]["tage"], zeilen["Tom Monteur"]["zusammen"], zeilen["Tom Monteur"]["schlechtwetter"]) == (
        0, D("0"), {"tage": 1, "stunden": D("7.50")})
    assert d["summe"]["schlechtwetter"] == {"tage": 2, "stunden": D("13.50")}
    assert d["summe"]["zusammen"] == D("3.50")
    ohne = monat(db, date(2026, 11, 1))
    # seit 1.9.311 (Lohn L2a, Punkt 4) stehen beide da -- sie haben im November Sollzeit --, ohne Stunden und ohne Ausfall (bis 1.9.310: keine Zeile)
    assert ohne["schlechtwetter"] is False and [(z["tage"], z["zusammen"], z["schlechtwetter"]["tage"]) for z in ohne["zeilen"]] == [(0, D("0"), 0)] * 2


def test_listen_unter_zeiten(welt):
    """Der Admin trägt für Mia ein (genehmigt), Tom beantragt für sich (offen) -- beide mit Stunden in „Abwesenheiten“, Toms auch unter „Prüfen“."""
    db = welt["db"]
    _buchen(welt, welt["mia"], "2")
    db.commit()
    admin = welt["client"](db, schlechtwetter_router.router, absence_router.router, zeiten_router.router, role="admin", user_id=7)
    assert admin.post("/api/schlechtwetter", json={"employee_ids": [welt["mia"].id], "tag": MO.isoformat(), "trotzdem": True}).status_code == 200
    tom = welt["client"](db, schlechtwetter_router.router, role="field", employee_id=welt["tom"].id, user_id=8)
    assert tom.post("/api/schlechtwetter", json={"employee_ids": [welt["tom"].id], "tag": MO.isoformat()}).status_code == 200
    abgelehnt = tom.post("/api/schlechtwetter", json={"employee_ids": [welt["tom"].id], "tag": DI.isoformat()}).json()["antraege"][0]["id"]
    assert admin.post(f"/api/schlechtwetter/{abgelehnt}/entscheiden", json={"decision": "rejected"}).status_code == 200
    urlaub = admin.post("/api/absence-requests", json={"employee_id": welt["mia"].id, "absence_category": "urlaub", "start_date": "2026-12-14",
                                                       "end_date": "2026-12-14"})
    assert urlaub.status_code == 200, urlaub.text
    liste = admin.get("/api/zeiten/abwesenheiten").json()["antraege"]
    je = {(a["employee_id"], a["absence_category"], a["status"]): a["ausfall"] for a in liste}
    assert je[(welt["mia"].id, "schlechtwetter", "approved")] == "Ausfall 5,50 h (Sollzeit 7,50 h − gebucht 2,00 h)"
    assert je[(welt["tom"].id, "schlechtwetter", "pending")] == "Ausfall 7,50 h"
    assert je[(welt["tom"].id, "schlechtwetter", "rejected")] is None  # abgelehnt: keine Stunden
    assert [a["ausfall"] for a in liste if a["absence_category"] != "schlechtwetter"] == [None]
    offen = admin.get("/api/zeiten/pruefen").json()["antraege"]
    assert [a["ausfall"] for a in offen if a["absence_category"] == "schlechtwetter"] == ["Ausfall 7,50 h"]


def test_seite_zeigt_die_spalte():
    from pathlib import Path
    text = (Path(__file__).resolve().parent.parent / "app" / "templates" / "zeiten.html").read_text(encoding="utf-8")
    assert ">Ausfall Schlechtwetter</th>':'')" in text
    assert text.count("+(a.ausfall?' · '+a.ausfall:'')") == 2


def test_beide_listen_zeichnen_die_stunden():
    """Die Seite zeichnet den Text vom Server in beiden Listen -- offene Anträge auf „Prüfen“ (antragHtml) und „Abwesenheiten“
    (abwesenheitHtml); ohne ausfall steht nichts da (nachgezogen nach der Gegenprobe 1.9.216 Nr. 4c, die mit dem Textvergleich grün blieb)."""
    import json
    from tests.test_v523_abwesenheiten_rechte import _node, _text
    vorweg = ("var KATEGORIE={schlechtwetter:'Schlechtwetter'};var STATUS={pending:['offen','chip-info']};"
              "function berlinZeitpunkt(w,a){return '01.12.2026'};var ZURUECK=null;var RECHTE={admin:false};var P=null;")
    antrag = {"id": 4, "employee_name": "Mia Monteurin", "absence_type": "Schlechtwetter", "absence_category": "schlechtwetter",
              "start_date": "2026-12-07", "end_date": "2026-12-07", "arbeitstage": 1, "created_at": "2026-12-01T08:00:00", "notes": None,
              "review_notes": None, "status": "pending", "darf_entscheiden": False, "darf_zurueckziehen": False, "beantragt_von": None,
              "ausfall": "Ausfall 5,50 h (Sollzeit 7,50 h − gebucht 2,00 h)"}
    html = _node(("beantragtText", "abwesenheitHtml", "antragHtml"),
                 f"return [abwesenheitHtml({json.dumps(antrag)}),antragHtml({json.dumps(antrag)})]", vorweg=vorweg)
    assert all("Mo 07.12.2026 · 1 Arbeitstag · Ausfall 5,50 h (Sollzeit 7,50 h − gebucht 2,00 h) · beantragt am 01.12.2026" in _text(h)
               for h in html), [_text(h) for h in html]
    ohne = _node(("beantragtText", "abwesenheitHtml", "antragHtml"),
                 f"return [abwesenheitHtml({json.dumps({**antrag, 'ausfall': None})}),antragHtml({json.dumps({**antrag, 'ausfall': None})})]",
                 vorweg=vorweg)
    assert all("Ausfall" not in _text(h) for h in ohne)


def test_zuordnung_nennt_die_stunden(db_session):
    """1.9.216 (Nachtrag): in der Zuordnung steht bei Schlechtwetter „Sollzeit − gebuchte Arbeit“ (bis dahin „Sollzeit“), der Satz über der
    Tabelle sagt dasselbe."""
    from pathlib import Path
    from app.lohnarten import liste
    stunden = {z["schluessel"]: z["stunden"] for z in liste(db_session)}
    assert (stunden["schlechtwetter:winter"], stunden["schlechtwetter:sommer"]) == ("Sollzeit − gebuchte Arbeit", "Sollzeit − gebuchte Arbeit")
    assert stunden["kategorie:urlaub"] == "Sollzeit" and stunden["arbeit"] == "gebuchte Stunden"
    text = (Path(__file__).resolve().parent.parent / "app" / "templates" / "settings.html").read_text(encoding="utf-8")
    assert "Arbeit trägt die gebuchten Stunden, Schlechtwetter die Sollzeit minus die gebuchte Arbeit des Tags, alles andere die Sollzeit" in text
