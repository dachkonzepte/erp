"""Seit 1.9.188 (Lohn L1a, Stufe 2, Punkt 3): die Plantafel kennt den Arbeitszeitkalender.

Feste Tage: Dezember 2026 (Mo 21.12. bis So 27.12.; Do 24.12. Heiligabend, Do 31.12. Silvester, kein Feiertag).

    Abwesend   an einem Kalendertag stehen die betroffenen gewerblichen Mitarbeiter (Sollzeit an dem Tag über 0, app/arbeitszeitkalender.py::
               freistellungen() -- dieselbe Regel wie der Lohn) auf der Tafel abwesend: Kapazität 0, in der Kolonne „abw.“, beim Mitarbeiter die
               Freistellung; die Kapazität des Einsatzes rechnet den Tag ohne sie. Wer an dem Tag keine Sollzeit hat (Teilzeit ohne Donnerstag),
               bleibt wie bisher. Nicht in der Liste der Abwesenheiten (abgeleitet, nicht gespeichert).
    Hinweis    ein Einsatz über den Tag bekommt einen Hinweis „kalendertag“ (Freistellung – wer) -- speichern ohne Rückfrage wie am betriebsfreien
               Tag, kein 409; eine gespeicherte Abwesenheit (Urlaub) geht vor und bleibt eine Warnung wie bisher
    Vorschlag  „Einsatz planen“ rechnet den Tag ebenso (abwesend mit der Freistellung)
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.arbeitszeitkalender import eintraege, freistellungen
from app.models import EmployeeAbsence, EmployeePlanningSettings, PlanningSlot, TeamEmployee
from app.planning import planning_board, planning_suggestion
from app.sollzeit import zeile_anlegen
from tests.test_v090_planning_board import setup_order
from tests.test_v563_konflikte_beim_speichern import _kolonne, _person
from app.routers.planning import router as planning_router

D = Decimal
MONTAG = date(2026, 12, 21)
HEILIGABEND = date(2026, 12, 24)


@pytest.fixture
def tafel(threaded_db_session, router_test_client, fester_tag):
    """Mia (Tarif), Tom (Teilzeit Di–Do 3,00 h -- am Donnerstag Sollzeit) und Ben (Teilzeit Mo–Di -- am Donnerstag keine) in Kolonne A."""
    db = threaded_db_session
    mia, tom, ben = _person(db, "M-1", "Mia"), _person(db, "M-2", "Tom"), _person(db, "M-3", "Ben")
    zeile_anlegen(db, tom.id, date(2026, 12, 1), {"dienstag": D("3"), "mittwoch": D("3"), "donnerstag": D("3")})
    zeile_anlegen(db, ben.id, date(2026, 12, 1), {"montag": D("8"), "dienstag": D("8")})
    team = _kolonne(db, "A", [mia, tom, ben])
    return {"db": db, "client": router_test_client(db, planning_router), "mia": mia, "tom": tom, "ben": ben, "team": team}


def _body(order, team, start, ende, **mehr):
    return {"order_id": order.id, "team_id": team.id, "start_date": start.isoformat(), "end_date": ende.isoformat(), "planned_hours": "1", **mehr}


def test_freistellungen_nur_mit_sollzeit(tafel):
    """Die Regel des Lohns: Mia und Tom am 24.12. und 31.12., Ben nicht (keine Sollzeit am Donnerstag); ein Zeitraum ohne Kalendertag -- leer."""
    db = tafel["db"]
    leute = [tafel["mia"], tafel["tom"], tafel["ben"]]
    f = freistellungen(db, leute, MONTAG, date(2026, 12, 31))
    assert sorted((p_id, tag.isoformat(), e.name) for (p_id, tag), e in f.items()) == sorted([
        (tafel["mia"].id, "2026-12-24", "Heiligabend"), (tafel["tom"].id, "2026-12-24", "Heiligabend"),
        (tafel["mia"].id, "2026-12-31", "Silvester"), (tafel["tom"].id, "2026-12-31", "Silvester")])
    assert freistellungen(db, leute, date(2026, 11, 2), date(2026, 11, 30)) == {}


def test_tafel_zeigt_die_betroffenen_abwesend(tafel):
    db = tafel["db"]
    order = setup_order(db, "1")
    antwort = tafel["client"].post("/api/planning/slots", json=_body(order, tafel["team"], MONTAG, HEILIGABEND))
    assert antwort.status_code == 200, antwort.text
    board = planning_board(db, MONTAG, MONTAG + timedelta(days=6))
    mia, tom, ben = (board["employee_capacity"][str(tafel[n].id)] for n in ("mia", "tom", "ben"))
    # 1.9.188 (Nachtrag): in der schmalen Zelle nur der Tag -- bis dahin die ganze Freistellung, sie überdeckte die Kapazität
    assert (mia["2026-12-24"]["capacity_hours"], mia["2026-12-24"]["absence"]) == (D("0"), "Heiligabend")
    assert mia["2026-12-23"]["capacity_hours"] > 0 and mia["2026-12-23"]["absence"] is None
    assert tom["2026-12-24"]["absence"] == "Heiligabend"
    # seit 1.9.211 (Kapazität aus der Sollzeit): Ben (Mo–Di) hat Mittwoch und Donnerstag keine Sollzeit, also keine Kapazität -- und ist nicht
    # freigestellt (bis 1.9.210 an beiden Tagen dieselbe Kapazität aus den Wochenstunden, Festlegung 1.9.188 Nr. 3 alt)
    assert (ben["2026-12-24"]["absence"], ben["2026-12-24"]["capacity_hours"], ben["2026-12-23"]["capacity_hours"]) == (None, D("0"), D("0"))
    assert ben["2026-12-22"]["capacity_hours"] == D("8")
    team = board["team_capacity"][str(tafel["team"].id)]
    assert sorted((a["name"], a["type"]) for a in team["2026-12-24"]["absences"]) == [
        ("Mia Test", "Heiligabend – bezahlte Freistellung"), ("Tom Test", "Heiligabend – bezahlte Freistellung")]
    # seit 1.9.211 an beiden Tagen ohne Ben (bis 1.9.210: 1 und 3)
    assert team["2026-12-24"]["available_employee_count"] == 0 and team["2026-12-23"]["available_employee_count"] == 2
    assert team["2026-12-24"]["capacity_hours"] < team["2026-12-23"]["capacity_hours"]
    assert board["absences"] == []  # abgeleitet, nicht gespeichert -- nicht in der Liste der Abwesenheiten
    konflikte = board["slots"][0]["conflicts"]
    assert [(k["type"], k["label"], str(k["date"]), k["stufe"]) for k in konflikte] == [
        ("kalendertag", "Heiligabend – Mia Test, Tom Test", "2026-12-24", "hinweis")]
    assert board["conflict_count"] == 1  # wie der betriebsfreie Tag: der Einsatz steht markiert


def test_speichern_ohne_rueckfrage_mit_hinweis(tafel):
    """Wie am betriebsfreien Tag: kein 409, der Hinweis steht in der Antwort; Silvester ebenso."""
    db = tafel["db"]
    order = setup_order(db, "1")
    antwort = tafel["client"].post("/api/planning/slots", json=_body(order, tafel["team"], date(2026, 12, 28), date(2026, 12, 31)))
    assert antwort.status_code == 200, antwort.text
    daten = antwort.json()
    assert daten["warnungen"] == []
    assert [(k["type"], k["label"], k["date"]) for k in daten["hinweise"]] == [("kalendertag", "Silvester – Mia Test, Tom Test", "2026-12-31")]


def test_gespeicherte_abwesenheit_geht_vor(tafel):
    """Mia hat am 24.12. Urlaub (gespeichert): für sie die Warnung wie bisher, der Hinweis nennt nur noch Tom."""
    db = tafel["db"]
    db.add(EmployeeAbsence(employee_id=tafel["mia"].id, absence_type="Urlaub", absence_category="urlaub", start_date=HEILIGABEND, end_date=HEILIGABEND))
    db.commit()
    order = setup_order(db, "1")
    antwort = tafel["client"].post("/api/planning/slots", json=_body(order, tafel["team"], MONTAG, HEILIGABEND))
    assert antwort.status_code == 409, antwort.text
    daten = antwort.json()
    assert [(k["type"], k["label"]) for k in daten["warnungen"]] == [("absence", "Mia Test · Urlaub")]
    assert [(k["type"], k["label"]) for k in daten["hinweise"]] == [("kalendertag", "Heiligabend – Tom Test")]


def test_abgeschalteter_kalendertag_wie_bisher(tafel):
    """Gegenprobe: Heiligabend abgeschaltet -- niemand abwesend, kein Hinweis."""
    db = tafel["db"]
    next(e for e in eintraege(db) if e.schluessel == "heiligabend").aktiv = False
    db.commit()
    order = setup_order(db, "1")
    daten = tafel["client"].post("/api/planning/slots", json=_body(order, tafel["team"], MONTAG, HEILIGABEND)).json()
    assert daten["hinweise"] == [] and daten["warnungen"] == []
    board = planning_board(db, MONTAG, MONTAG + timedelta(days=6))
    assert board["employee_capacity"][str(tafel["mia"].id)]["2026-12-24"]["absence"] is None
    assert db.query(PlanningSlot).count() == 1


def test_vorschlag_rechnet_den_tag_ohne_die_betroffenen(tafel):
    """Seit 1.9.211 mit Uwe (kaufmännisch, Tarif, auf der Tafel eingeschaltet) in der Kolonne: für ihn gilt Heiligabend nicht (nur gewerbliche) --
    er ist an dem Tag der eine Verfügbare (bis 1.9.210 Ben, der jetzt am Donnerstag ohne Sollzeit keine Kapazität hat)."""
    db = tafel["db"]
    uwe = _person(db, "B-1", "Uwe")
    uwe.employee_group = "kaufmaennisch"
    db.add_all([TeamEmployee(team_id=tafel["team"].id, employee_id=uwe.id), EmployeePlanningSettings(employee_id=uwe.id, show_on_planning_board=True)])
    db.commit()
    order = setup_order(db, "1")
    s = planning_suggestion(db, order_id=order.id, team_id=tafel["team"].id, start_date=HEILIGABEND)
    tag = next(d for d in s["days"] if d["date"] == HEILIGABEND)
    assert sorted((a["name"], a["type"]) for a in tag["absent_employees"]) == [
        ("Mia Test", "Heiligabend – bezahlte Freistellung"), ("Tom Test", "Heiligabend – bezahlte Freistellung")]
    assert tag["available_employee_count"] == 1


def test_seite_nennt_die_freistellung():
    from tests import vorlagen_js as vj
    text = vj.seitentext("planning.html")[0]
    assert "kalendertag:'Freistellung: '" in text
    # seit 1.9.193: der Satz über der Tafel nennt Freistellungen -- in der Liste „Abwesenheiten“ der Tafel stehen sie nicht (Festlegung 1.9.188 Nr. 5)
    assert "Berücksichtigt werden Doppelbelegungen, Abwesenheiten, Freistellungen, Feiertage und unzureichende Stundenkapazität." in text


def test_lange_abwesenheit_in_der_zelle_gekuerzt_mit_tooltip():
    """Seit 1.9.194 (Nachtrag zu 1.9.188): eine lange Abwesenheit wird in der Zelle mit „…“ gekürzt und trägt den vollen Text im Tooltip.
    Lage und Kürzung misst scripts/klicktest_plantafel_kalender.py im Browser (Kais lange Art am 22.12.); hier die Regel und das Markup."""
    import re

    from tests import vorlagen_js as vj
    text = vj.seitentext("planning.html")[0]
    [regel] = re.findall(r"\.absence-mark\{([^}]*)\}", text)
    assert {"position:absolute", "right:3px", "bottom:3px", "max-width:calc(100% - 58px)", "overflow:hidden", "text-overflow:ellipsis",
            "white-space:nowrap"} <= set(regel.split(";"))
    assert '<span class="absence-mark" title="${esc(absence)}">${esc(absence)}</span>' in text
