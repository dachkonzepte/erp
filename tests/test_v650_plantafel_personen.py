"""Version 1.9.250 (Stufe 6, R4, Punkt 3): die Ansicht „Personen“ nach bildgrundlage/entwurf-stufe6/plantafel-personen.html.

    Daten        GET /api/planning: je Person das Kennzeichen „plantafel“ (seit 1.9.253, bis 1.9.252 „konto“); die Termine aus dem Kalender der Personen mit Konto
                 („personen_termine“, auch Serienvorkommen) -- privat „Belegt“, außer für den Besitzer (der Router gibt den Betrachter mit); ohne Modul
                 „Kalender“ keine Termine
    Seite        Gruppen je Kolonne (Kolonnenführer zuerst), „Ohne Kolonne“, „Bauleitung · Termine aus dem Kalender“ (Kennzeichen, seit 1.9.253); jede
                 Person einmal; „doppelt …“ (Einsätze geschlossener Aufträge zählen nicht), „Antrag …“; „mit <Kolonne>“ an einem Einsatz einer anderen
                 Kolonne; eine Kranvermietung nach dem Gerät
Im Browser misst scripts/klicktest_plantafel_personen.py (Zeichnung nachgestellt, Überdeckung, 1440/1280, hell/dunkel, Büro – Auftrag).
"""

import json
from datetime import date, datetime, timedelta

from app.models import AppUser, CalendarEvent, EnabledModule, OutlookSeriesOccurrence
from app.planning import personen_termine, planning_board
from app.routers.planning import router as planning_router
from tests.test_v399_teil_updates_geld import im_browser, nur_mit_node
from tests.test_v600_plantafel_kalender import tafel  # noqa: F401  (Fixture)
from tests.test_v633_besetzung_je_einsatz import _person

MO = date(2026, 11, 2)


def _welt(db):
    bea, tom = _person(db, "M-1", "Bea"), _person(db, "M-2", "Tom")
    konto = AppUser(username="bea", display_name="Bea", role="buero_auftrag", employee_id=bea.id, password_hash="x", active=True)
    alt = AppUser(username="tom-alt", display_name="Tom", role="buero_auftrag", employee_id=tom.id, password_hash="x", active=False)
    db.add_all([konto, alt]); db.flush()
    db.add_all([
        CalendarEvent(title="Aufmaß", start_at=datetime(2026, 11, 3, 10), end_at=datetime(2026, 11, 3, 11), owner_user_id=konto.id),
        CalendarEvent(title="Zahnarzt", start_at=datetime(2026, 11, 6, 9), end_at=datetime(2026, 11, 6, 10), owner_user_id=konto.id, is_private=True),
        CalendarEvent(title="Messe", start_at=datetime(2026, 11, 9), end_at=datetime(2026, 11, 11), all_day=True, owner_user_id=konto.id),
        CalendarEvent(title="vorher", start_at=datetime(2026, 10, 30, 9), end_at=datetime(2026, 10, 30, 10), owner_user_id=konto.id),
        CalendarEvent(title="Tom alt", start_at=datetime(2026, 11, 4, 9), end_at=datetime(2026, 11, 4, 10), owner_user_id=alt.id),
        OutlookSeriesOccurrence(owner_user_id=konto.id, outlook_postfach="bea@example.invalid", outlook_event_id="s-1", occurrence_type="occurrence",
                                title="Jour fixe", start_at=datetime(2026, 11, 4, 8), end_at=datetime(2026, 11, 4, 9)),
    ])
    db.commit()
    return {"bea": bea, "tom": tom, "konto": konto}


def _kurz(termine):
    return [(t["titel"], t["von"], t["bis"], t["zeit"], t["serie"]) for t in termine]


def test_personen_mit_konto_und_ihre_termine(threaded_db_session):
    db = threaded_db_session
    w = _welt(db)
    tafel = planning_board(db, MO, MO + timedelta(days=13))
    # seit 1.9.253 kein „konto“ mehr an der Person (die Gruppe folgt dem Kennzeichen „Plantafel“); Toms Konto ist nicht aktiv -- keine Termine
    assert {e["id"]: e["plantafel"] for e in tafel["employees"]} == {w["bea"].id: "einplanbar", w["tom"].id: "einplanbar"}
    assert _kurz(tafel["personen_termine"]) == [
        ("Aufmaß", date(2026, 11, 3), date(2026, 11, 3), "10:00", False),
        ("Belegt", date(2026, 11, 6), date(2026, 11, 6), "09:00", False),  # privat, kein Betrachter
        ("Messe", date(2026, 11, 9), date(2026, 11, 11), None, False),     # ganztägig: erster bis letzter Tag (termin_tage(), wie am Gerät)
        ("Jour fixe", date(2026, 11, 4), date(2026, 11, 4), "08:00", True),
    ]
    assert {t["employee_id"] for t in tafel["personen_termine"]} == {w["bea"].id}


def test_privat_nur_fuer_den_besitzer_mit_titel(threaded_db_session, router_test_client):
    db = threaded_db_session
    w = _welt(db)
    titel = lambda **kw: [t["titel"] for t in personen_termine(db, {w["bea"].id}, MO, MO + timedelta(days=13), **kw)[1]]  # noqa: E731
    assert "Zahnarzt" in titel(betrachter_user_id=w["konto"].id) and "Belegt" not in titel(betrachter_user_id=w["konto"].id)
    assert "Belegt" in titel(betrachter_user_id=w["konto"].id + 99) and "Zahnarzt" not in titel(betrachter_user_id=w["konto"].id + 99)
    # über die Schnittstelle: der Router gibt den Betrachter mit
    ueber = lambda uid: [t["titel"] for t in router_test_client(db, planning_router, role="buero_auftrag", user_id=uid)  # noqa: E731
                         .get("/api/planning", params={"start": MO.isoformat(), "end": (MO + timedelta(days=13)).isoformat()}).json()["personen_termine"]]
    assert "Zahnarzt" in ueber(w["konto"].id) and "Zahnarzt" not in ueber(w["konto"].id + 99)


def test_ohne_modul_kalender_keine_termine(threaded_db_session):
    db = threaded_db_session
    w = _welt(db)
    db.add(EnabledModule(module_key="kalender", enabled=False))
    db.commit()
    tafel = planning_board(db, MO, MO + timedelta(days=13))
    assert tafel["personen_termine"] == [] and {e["id"] for e in tafel["employees"]} == {w["bea"].id, w["tom"].id}


def test_konflikte_nennen_die_person(threaded_db_session):
    """Seit 1.9.250: Person doppelt, abwesend und Antrag offen nennen die betroffene Person (employee_id) -- „Personen“ zeigt sie nur bei ihr."""
    from decimal import Decimal

    from app.models import EmployeeAbsence, EmployeeAbsenceRequest
    from app.planning import create_slot
    from tests.test_v090_planning_board import setup_order

    db = threaded_db_session
    kai, nele, tom = _person(db, "M-1", "Kai"), _person(db, "M-2", "Nele"), _person(db, "M-3", "Tom")
    db.add(EmployeeAbsence(employee_id=tom.id, absence_type="Urlaub", absence_category="urlaub", start_date=MO, end_date=MO))
    db.add(EmployeeAbsenceRequest(employee_id=nele.id, absence_type="Urlaub", absence_category="urlaub", start_date=MO, end_date=MO, status="pending"))
    db.commit()
    a = create_slot(db, order_id=setup_order(db, "A").id, team_id=None, employee_ids=[kai.id, nele.id, tom.id], start_date=MO, end_date=MO,
                    planned_hours=Decimal("1"), trotzdem_planen=True)
    create_slot(db, order_id=setup_order(db, "B").id, team_id=None, employee_ids=[kai.id], start_date=MO, end_date=MO, planned_hours=Decimal("1"),
                trotzdem_planen=True)
    [s] = [x for x in planning_board(db, MO, MO + timedelta(days=6))["slots"] if x["id"] == a.id]
    assert sorted((c["type"], c.get("employee_id")) for c in s["conflicts"] if c["type"] in ("employee", "absence", "antrag_offen")) == sorted(
        [("employee", kai.id), ("absence", tom.id), ("antrag_offen", nele.id)])


def test_freistellung_nennt_die_personen(tafel):  # noqa: F811  (Fixture aus test_v600: Heiligabend für Mia und Tom, nicht für Ben)
    from tests.test_v090_planning_board import setup_order
    from tests.test_v600_plantafel_kalender import HEILIGABEND, MONTAG as WEIHNACHTEN, _body

    db = tafel["db"]
    assert tafel["client"].post("/api/planning/slots", json=_body(setup_order(db, "1"), tafel["team"], WEIHNACHTEN, HEILIGABEND)).status_code == 200
    [k] = planning_board(db, WEIHNACHTEN, WEIHNACHTEN + timedelta(days=6))["slots"][0]["conflicts"]
    assert (k["type"], sorted(k["employee_ids"])) == ("kalendertag", sorted([tafel["mia"].id, tafel["tom"].id]))


# --- Seite (node) -------------------------------------------------------------------------------------------------------------------------------

def _tafel():
    s = lambda i, team, leute, von, bis, **kw: {"id": i, "team_id": team, "employees": [{"id": x} for x in leute], "start_date": von, "end_date": bis,  # noqa: E731
                                                "order_status": "laeuft", "art": "baustelle", **kw}
    return {
        "teams": [{"id": 1, "name": "Kolonne Nord", "employees": [{"id": 11, "name": "Ole", "kf": False}, {"id": 10, "name": "Tom", "kf": True}]},
                  {"id": 2, "name": "Kolonne Süd", "employees": [{"id": 20, "name": "Kai", "kf": True}, {"id": 11, "name": "Ole", "kf": False},
                                                                 {"id": 99, "name": "Unsichtbar", "kf": False}]},
                  {"id": 3, "name": "Kolonne leer", "employees": []}],
        "employees": [{"id": 10, "name": "Tom"}, {"id": 11, "name": "Ole"}, {"id": 20, "name": "Kai"}, {"id": 30, "name": "Ulf", "plantafel": "einplanbar"},
                      {"id": 31, "name": "Bea", "plantafel": "bauleitung"}],
        "slots": [s(1, 1, [20], "2026-11-02", "2026-11-06"), s(2, 2, [20], "2026-11-04", "2026-11-05"), s(3, 2, [20], "2026-11-05", "2026-11-09"),
                  s(4, 2, [20], "2026-11-12", "2026-11-12"), s(5, 2, [20], "2026-11-12", "2026-11-13", order_status="storniert"),
                  s(6, 1, [10], "2026-10-26", "2026-11-03"), s(7, 1, [10], "2026-10-27", "2026-11-04")],
        "abwesenheiten": [{"employee_id": 31, "stand": "beantragt", "von": "2026-11-05", "bis": "2026-11-06", "art": None},
                          {"employee_id": 31, "stand": "genehmigt", "von": "2026-11-09", "bis": "2026-11-09", "art": None}],
    }


@nur_mit_node
def test_gruppen_doppelt_und_antrag():
    vorbereitung = (f"var board = {json.dumps(_tafel())}; "
                    "var geo = {spalten: Array.from({length: 14}, (_, i) => ({d: addDays('2026-11-02', i)}))}; "
                    "function localDateIso(d) { const p = n => String(n).padStart(2, '0'); return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`; }")
    ablauf = ("AUFRUFE.push({gruppen: personenGruppen().map(g => [g.titel, g.team, g.personen.map(p => p.name)]), "
              "doppelt: [doppeltText(20), doppeltText(10), doppeltText(31)], antrag: antragText(31)});")
    [erg] = im_browser("planning.html", ["personenGruppen", "doppeltText", "antragText", "fmtSpanne", "fmt", "addDays", "iso"], vorbereitung, ablauf)
    assert erg["gruppen"] == [["Kolonne Nord", 1, ["Tom", "Ole"]],   # Kolonnenführer zuerst, Ole nur in seiner ersten Kolonne
                              ["Kolonne Süd", 2, ["Kai"]],          # wer nicht sichtbar ist, fehlt; eine leere Kolonne ohne Abschnitt
                              ["Ohne Kolonne", None, ["Ulf"]], ["Bauleitung · Termine aus dem Kalender", None, ["Bea"]]]
    # Kai: 04.–05. (1+2), 05.–06. (1+3) -> 04.–06.; 12. nicht (5 ist storniert); Tom: im Bild ab 02.11. (6+7 bis 03.)
    assert erg["doppelt"] == ["doppelt 04.–06.11.", "doppelt 02.–03.11.", ""]
    assert erg["antrag"] == "Antrag 05.–06.11."


@nur_mit_node
def test_balken_einer_person_nur_mit_ihren_konflikten():
    s = {"id": 1, "art": "baustelle", "team_id": 1, "project_name": "Garage", "status": "fest", "order_status": "laeuft", "employees": [], "resources": [],
         "conflicts": [{"type": "employee", "stufe": "warnung", "employee_id": 20}, {"type": "antrag_offen", "stufe": "hinweis", "employee_id": 21},
                       {"type": "kalendertag", "stufe": "hinweis", "employee_ids": [22]}, {"type": "holiday", "stufe": "hinweis"}]}
    vorbereitung = (f"var board = {{teams: [{{id: 1, name: 'Kolonne Süd'}}]}}; var s = {json.dumps(s)}; "
                    "function vornamen() { return ''; } function einsatzTitel() { return ''; }")
    ablauf = ("AUFRUFE.push({p: [20, 21, 22, 23].map(p => { const b = einsatzBalken(s, 'person', 1, p); return [b.warn, b.hint]; }), "
              "k: (b => [b.warn, b.hint])(einsatzBalken(s, 'kolonne'))});")
    [erg] = [x for x in im_browser("planning.html", ["einsatzBalken"], vorbereitung, ablauf) if "p" in x]
    assert erg["p"] == [[True, False], [False, True], [False, True], [False, False]]  # Kai, Nele, Freistellung, jemand ohne -- der Feiertag nicht
    assert erg["k"] == [True, True]  # in „Kolonnen“ alle
