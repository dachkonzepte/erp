"""Seit 1.9.63 (Stufe 4, R3 Nachrunde, Punkt 1, Entscheidung Tobias): die Kolonne mit Von/Bis.

    Nachtrag       POST /api/time-entry-groups mit von/bis: eine Angabe für die angehakten Mitglieder, Pause und Rundung je Mitglied nach
                   seinem Tag (kolonne_rechnen(), dieselbe Rechnung wie sein eigener Nachtrag); break_minutes = Mindestpause
    Ändern         PUT /api/time-entry-groups/{id} mit von/bis: je Mitglied sein Tag ohne die alte Fassung; selbst geänderte bleiben;
                   ohne pause_minuten die gemerkte Mindestpause je Mitglied
    Vorschau       GET /api/time-entry-groups/nachtrag-vorschau: dieselben Zahlen je Mitglied, Rechte wie beim Buchen
    Dauer          für die Kolonne nur noch das Büro -- der Kolonnenführer 422 (nach den Rechteprüfungen)
"""

from datetime import datetime, time, timedelta
from decimal import Decimal

from app.meldungen import NUR_VON_BIS
from app.models import TimeEntry, TimeEntryGroup, TimeEntryGroupMember
from app.routers import time_tracking as time_tracking_router
from app.time_tracking import create_group_manual_entry, start_timer, stop_timer
from tests.test_v471_heute_server import _als, _einsatz, welt  # noqa: F401  (Fixture)


def _kolonne(w):
    _einsatz(w, w["order"], [(w["heute"] - timedelta(days=7), w["heute"])], [w["mia"], w["tom"]])
    return _als(w, w["mia"])


def _zeit(w, emp, von, bis, tag, art="site"):
    row = start_timer(w["db"], employee_id=emp.id, order_id=w["order"].id, entry_type=art, started_at=datetime.combine(tag, von))
    return stop_timer(w["db"], row.id, ended_at=datetime.combine(tag, bis))


def _koerper(w, tag, **mehr):
    return {"employee_ids": [w["mia"].id, w["tom"].id], "team_id": w["team"].id, "order_id": w["order"].id, "work_date": tag.isoformat(),
            **mehr}


def _mitglieder(w, gruppe_id):
    w["db"].expire_all()
    ids = {m.employee_id: m.time_entry_id for m in w["db"].query(TimeEntryGroupMember).filter_by(group_id=gruppe_id).all()}
    out = {}
    for emp, eid in ids.items():
        e = w["db"].get(TimeEntry, eid)
        out[emp] = (e.started_at.strftime("%H:%M") if e.started_at else None, e.ended_at.strftime("%H:%M") if e.ended_at else None,
                    e.break_minutes, e.hours, e.min_break_minutes)
    return out


def test_kolonne_0700_1230_je_mitglied_nach_seinem_tag(welt):  # noqa: F811
    """Angriff (Auftrag): 07:00–12:30 für Mia (ohne Vorbuchung) und Tom (Fahrzeit 06:15–07:00 am Morgen) -> Mia 5,50 h ohne Pause, Tom
    5,00 h mit 30 min (Tag zusammen 6:15 h). Vorschau = Buchung, die Antwort nennt die Stunden je Person."""
    client = _kolonne(welt)
    g = welt["gestern"]
    _zeit(welt, welt["tom"], time(6, 15), time(7), g, art="travel")
    v = client.get("/api/time-entry-groups/nachtrag-vorschau",
                   params={"work_date": g.isoformat(), "von": "07:00", "bis": "12:30", "team_id": welt["team"].id,
                           "employee_ids": [welt["mia"].id, welt["tom"].id]})
    assert v.status_code == 200, v.text
    assert [(m["name"], m["pause"], Decimal(str(m["gebucht"])), Decimal(str(m["tag_zusammen"])), m["tag_buchungen"])
            for m in v.json()["mitglieder"]] == [("Mia Monteurin", 0, Decimal("5.5"), Decimal("5.5"), 1),
                                                 ("Tom Monteur", 30, Decimal("5"), Decimal("6.25"), 2)]
    antwort = client.post("/api/time-entry-groups", json=_koerper(welt, g, von="07:00", bis="12:30"))
    assert antwort.status_code == 200, antwort.text
    assert sorted((m["employee_name"], Decimal(str(m["hours"]))) for m in antwort.json()["member_entries"]) == \
        [("Mia Monteurin", Decimal("5.5")), ("Tom Monteur", Decimal("5"))]
    assert _mitglieder(welt, antwort.json()["id"]) == {
        welt["mia"].id: ("07:00", "12:30", 0, Decimal("5.5"), 0), welt["tom"].id: ("07:00", "12:30", 30, Decimal("5"), 0)}
    kopf = welt["db"].get(TimeEntryGroup, antwort.json()["id"])
    assert (kopf.started_at.strftime("%H:%M"), kopf.ended_at.strftime("%H:%M"), kopf.break_minutes, kopf.hours) == \
        ("07:00", "12:30", 30, Decimal("5.25"))


def test_kolonnenfuehrer_mit_dauer_422_buero_wie_bisher(welt):  # noqa: F811
    """Angriff: der Kolonnenführer trägt für die Kolonne eine Dauer nach -> 422 mit der Meldung, nichts gebucht; ändert er die Stunden
    einer Kolonnenbuchung -> 422; nur die Notiz -> 200. Gegenprobe: das Büro (Admin) mit Dauer wie bisher."""
    client = _kolonne(welt)
    g = welt["gestern"]
    abgelehnt = client.post("/api/time-entry-groups", json=_koerper(welt, g, hours="5"))
    assert (abgelehnt.status_code, abgelehnt.json()["detail"]) == (422, NUR_VON_BIS)
    assert welt["db"].query(TimeEntryGroup).count() == 0
    buero = welt["client"](welt["db"], time_tracking_router.router, role="admin")
    dauer = buero.post("/api/time-entry-groups", json=_koerper(welt, g, hours="5"))
    assert dauer.status_code == 200, dauer.text
    assert {k: v[3] for k, v in _mitglieder(welt, dauer.json()["id"]).items()} == {welt["mia"].id: Decimal("5"), welt["tom"].id: Decimal("5")}
    kolonne = client.post("/api/time-entry-groups", json=_koerper(welt, welt["heute"], von="06:00", bis="09:00"))
    assert kolonne.status_code == 200, kolonne.text
    stunden = client.put(f"/api/time-entry-groups/{kolonne.json()['id']}", json={"hours": "4"})
    assert (stunden.status_code, stunden.json()["detail"]) == (422, NUR_VON_BIS)
    assert client.put(f"/api/time-entry-groups/{kolonne.json()['id']}", json={"notes": "Rinne"}).status_code == 200


def test_kolonne_fuenf_stunden_ohne_pause(welt):  # noqa: F811
    """5:00 h über die Kolonne (07:00–12:00, ohne weitere Buchungen) -> je 0 min Pause, 5,00 h."""
    client = _kolonne(welt)
    antwort = client.post("/api/time-entry-groups", json=_koerper(welt, welt["gestern"], von="07:00", bis="12:00"))
    assert antwort.status_code == 200, antwort.text
    assert {k: v[2:4] for k, v in _mitglieder(welt, antwort.json()["id"]).items()} == {
        welt["mia"].id: (0, Decimal("5")), welt["tom"].id: (0, Decimal("5"))}


def test_kolonne_aendern_mit_von_bis_je_mitglied(welt):  # noqa: F811
    """Eine Kolonnenbuchung von Mia als Dauer (8 h, von vor 1.9.63); Tom ändert seine Buchung selbst (über das Büro). Mia ändert die
    Kolonne auf 07:00–15:00 -> Mia 7,50 h mit 30 min, Beginn und Ende; Tom bleibt (übersprungen). Die Vorschau mit group_id nennt nur Mia,
    Tom als „bleibt“."""
    client = _kolonne(welt)
    g = welt["gestern"]
    buero = welt["client"](welt["db"], time_tracking_router.router, role="admin")
    gruppe = {"id": create_group_manual_entry(welt["db"], employee_ids=[welt["mia"].id, welt["tom"].id], team_id=welt["team"].id,
                                              actor_employee_id=welt["mia"].id, is_admin=False, order_id=welt["order"].id, work_date=g,
                                              hours=Decimal("8")).id}
    tom_id = welt["db"].query(TimeEntryGroupMember).filter_by(group_id=gruppe["id"], employee_id=welt["tom"].id).one().time_entry_id
    assert buero.put(f"/api/time-entries/{tom_id}", json={"hours": "6"}).status_code == 200
    v = client.get("/api/time-entry-groups/nachtrag-vorschau",
                   params={"work_date": g.isoformat(), "von": "07:00", "bis": "15:00", "group_id": gruppe["id"]}).json()
    assert ([(m["name"], Decimal(str(m["gebucht"]))) for m in v["mitglieder"]], v["uebersprungen"]) == \
        ([("Mia Monteurin", Decimal("7.5"))], ["Tom Monteur"])
    antwort = client.put(f"/api/time-entry-groups/{gruppe['id']}", json={"von": "07:00", "bis": "15:00"})
    assert antwort.status_code == 200, antwort.text
    assert antwort.json()["skipped_members"] == ["Tom Monteur"]
    stand = _mitglieder(welt, gruppe["id"])
    assert stand[welt["mia"].id] == ("07:00", "15:00", 30, Decimal("7.5"), 0)
    assert stand[welt["tom"].id][:4] == (None, None, 0, Decimal("6"))


def test_aendern_ohne_pause_behaelt_die_mindestpause_je_mitglied(welt):  # noqa: F811
    """Kolonne 07:00–11:00 mit „Pause mindestens“ 45 -> je 45; geändert auf 07:00–12:00 ohne pause_minuten -> je 45 (gemerkt), mit 0 -> 0."""
    client = _kolonne(welt)
    g = welt["gestern"]
    gruppe = client.post("/api/time-entry-groups", json=_koerper(welt, g, von="07:00", bis="11:00", break_minutes=45)).json()
    assert {k: v[2:] for k, v in _mitglieder(welt, gruppe["id"]).items()} == {
        welt["mia"].id: (45, Decimal("3.25"), 45), welt["tom"].id: (45, Decimal("3.25"), 45)}
    mine = client.get("/api/time-entry-groups/mine").json()
    assert [(x["von"], x["bis"], x["mindestpause"]) for x in mine] == [("07:00", "11:00", 45)]
    assert client.put(f"/api/time-entry-groups/{gruppe['id']}", json={"von": "07:00", "bis": "12:00"}).status_code == 200
    assert {k: v[2:] for k, v in _mitglieder(welt, gruppe["id"]).items()} == {
        welt["mia"].id: (45, Decimal("4.25"), 45), welt["tom"].id: (45, Decimal("4.25"), 45)}
    assert client.put(f"/api/time-entry-groups/{gruppe['id']}", json={"von": "07:00", "bis": "12:00", "pause_minuten": 0}).status_code == 200
    assert {k: v[2:] for k, v in _mitglieder(welt, gruppe["id"]).items()} == {
        welt["mia"].id: (0, Decimal("5"), 0), welt["tom"].id: (0, Decimal("5"), 0)}


def test_vorschau_rechte_und_fehler(welt):  # noqa: F811
    """Angriff: Tom (kein Kolonnenführer) fragt die Vorschau der Kolonne -> 403; Mia die Vorschau einer fremden Kolonnenbuchung -> 403;
    Bis vor Von -> 422 (Vorschau und Buchung), nichts gebucht."""
    client = _kolonne(welt)
    tom = _als(welt, welt["tom"])
    g = welt["gestern"].isoformat()
    params = {"work_date": g, "von": "07:00", "bis": "12:00", "team_id": welt["team"].id, "employee_ids": [welt["mia"].id, welt["tom"].id]}
    assert tom.get("/api/time-entry-groups/nachtrag-vorschau", params=params).status_code == 403
    buero = welt["client"](welt["db"], time_tracking_router.router, role="admin")
    fremd = buero.post("/api/time-entry-groups", json=_koerper(welt, welt["gestern"], hours="4")).json()
    assert client.get("/api/time-entry-groups/nachtrag-vorschau",
                      params={"work_date": g, "von": "07:00", "bis": "12:00", "group_id": fremd["id"]}).status_code == 403
    falsch = client.get("/api/time-entry-groups/nachtrag-vorschau", params={**params, "von": "12:00", "bis": "07:00"})
    assert (falsch.status_code, falsch.json()["detail"]) == (422, "Bis muss nach Von liegen.")
    anzahl = welt["db"].query(TimeEntryGroup).count()
    assert client.post("/api/time-entry-groups", json=_koerper(welt, welt["gestern"], von="12:00", bis="07:00")).status_code == 422
    assert welt["db"].query(TimeEntryGroup).count() == anzahl
