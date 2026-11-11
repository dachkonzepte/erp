"""Seit 1.9.198 (Gegenproben zu den Festlegungen 1.9.170–1.9.173, Regel 24): was eine Gegenprobe grün ließ, prüft jetzt ein Test.

    1.9.170 Nr. 1   weder die Funktion „Dachdecker Vorarbeiter“ noch die Rolle „Vorarbeiter“ in einer Kolonne machen jemanden zum Vorarbeiter
    1.9.170 Nr. 3   der Admin entscheidet einen Schlechtwetter-Antrag auch unter „Zeiten“ (POST /api/absence-requests/{id}/review)
    1.9.170 Nr. 4   Schlechtwetter auch für Azubis (Funktion „Dachdecker Auszubildende/r“, Gruppe gewerblich)
    1.9.170 Nr. 5   alles oder nichts auch, wenn erst das Genehmigen einer späteren Person scheitert (schon abwesend)
    1.9.170 Nr. 6   laufende Zeit warnt wie gebuchte; „trotzdem“ lässt die Buchungen stehen
    1.9.170 Nr. 8   auch die Plantafel lässt Schlechtwetter nicht zu; die allgemeinen Abwesenheitsdialoge bieten es nicht an
    1.9.170 Nr. 9   eine wieder eingeschaltete Zeitart Schlechtwetter bekommt ihre Kachel zurück
    1.9.171 Nr. 1   kein halber Tag bei Freizeitausgleich, Fortbildung und Unbezahlt
    1.9.171 Nr. 3   die Plantafel rechnet einen halben Urlaubstag als ganzen Tag
    1.9.171 Nr. 5   der Sammeleintrag nennt jede Person; wer schon abwesend ist, wird nicht übergangen
    1.9.171 Nr. 6   „Alle“ heißt alle aktiven Mitarbeiter, auch kaufmännische; Schlechtwetter im Sammeleintrag auch für einen einzelnen Tag 422
    1.9.172 Nr. 1   ganz ohne Arbeitszeitmodell ist „zu klären“
    1.9.173 Nr. 1   klicktest_monteurin_regeln läuft an einem festen Tag, in Instanz und Browser

Feste Tage: Dezember 2026 (Mo 07.12.2026, wie tests/test_v588_schlechtwetter.py), fester Tag der Uhr 10.11.2026.
"""

import ast
import re
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select

from app.absence_requests import create_request, review_request
from app.models import (EmployeeAbsence, EmployeeAbsenceRequest, EmployeeFunction, EmployeeProfile, EmployeeWorkTimeModel, SettingOption,
                        SettingOptionGroup, TeamEmployee, TimeBackofficeAdvancedSettings, TimeEntry, WorkTimeBreakRule, WorkTimeModel,
                        WorkTimeModelValidity)
from app.routers import absence_requests as absence_router
from app.routers import schlechtwetter as schlechtwetter_router
from app.routers import zeiten as zeiten_router
from app.routers.planning import router as planning_router
from tests.test_v133_invoices import db_session as neue_db
from tests.test_v224_field_view import make_employee
from tests.test_v325_contract_basis import beauftragen, make_quote
from tests.test_v588_schlechtwetter import MO, _abwesenheiten, _als, _eintragen, welt  # noqa: F401  (Fixture)
from tests.test_v590_pruefe_zeitregeln import _lauf

ROOT = Path(__file__).resolve().parent.parent


def _client(w, *router, rolle="admin", wer=None):
    w["db"].commit()
    return w["client"](w["db"], *router, role=rolle, employee_id=w[wer].id if wer else None, user_id=7)


def _funktion(db, name):
    f = db.scalar(select(EmployeeFunction).where(EmployeeFunction.name == name))
    if f is None:
        f = EmployeeFunction(name=name, employee_group="gewerblich", active=True)
        db.add(f)
        db.flush()
    return f


def _zaehlen(w):
    w["db"].expire_all()
    return w["db"].query(EmployeeAbsenceRequest).count(), w["db"].query(EmployeeAbsence).count()


def _buchung(w, emp, status="booked", hours=Decimal("3.5")):
    db = w["db"]
    order = beauftragen(db, make_quote(db, is_consumer=False, number=f"0605-{emp.id}-{status}"))
    eintrag = TimeEntry(employee_id=emp.id, project_id=order.project_id, order_id=order.id, work_date=MO, entry_type="site", hours=hours,
                        break_minutes=0, status=status, started_at=datetime.combine(MO, time(7)),
                        ended_at=datetime.combine(MO, time(10, 30)) if status == "booked" else None)
    db.add(eintrag)
    db.commit()
    return eintrag.id


# --- 1.9.170 Nr. 1: Vorarbeiter nur über das Kennzeichen ---------------------------------------------------------------------------------

def test_funktion_dachdecker_vorarbeiter_macht_keinen_vorarbeiter(welt):  # noqa: F811
    """Tom trägt die Funktion „Dachdecker Vorarbeiter“, aber nicht das Kennzeichen: für Mia 403, kein Dialog für andere."""
    db = welt["db"]
    db.add(EmployeeProfile(employee_id=welt["tom"].id, function_id=_funktion(db, "Dachdecker Vorarbeiter").id))
    db.commit()
    client = _als(welt, "field", "tom")
    assert client.get("/api/schlechtwetter/kontext").json()["fuer_andere"] is False
    assert _eintragen(client, welt["mia"]).status_code == 403


def test_rolle_vorarbeiter_in_der_kolonne_macht_keinen_vorarbeiter(welt):  # noqa: F811
    """Tom steht in Kolonne 1 mit der Rolle „Vorarbeiter“ (Text, kein Kolonnenführer): für Mia 403."""
    db = welt["db"]
    db.scalar(select(TeamEmployee).where(TeamEmployee.employee_id == welt["tom"].id)).role = "Vorarbeiter"
    db.commit()
    client = _als(welt, "field", "tom")
    assert client.get("/api/schlechtwetter/kontext").json()["fuer_andere"] is False
    assert _eintragen(client, welt["mia"]).status_code == 403


# --- 1.9.170 Nr. 3: der Admin entscheidet auch unter „Zeiten“ ----------------------------------------------------------------------------

def test_admin_entscheidet_schlechtwetter_auch_unter_zeiten(welt):  # noqa: F811
    _eintragen(_als(welt, "field", "tom"), welt["tom"])
    antrag = welt["db"].scalar(select(EmployeeAbsenceRequest.id))
    client = _client(welt, absence_router.router, zeiten_router.router)
    zeile = next(a for a in client.get("/api/zeiten/abwesenheiten").json()["antraege"] if a["id"] == antrag)
    assert (zeile["absence_category"], zeile["darf_entscheiden"]) == ("schlechtwetter", True)
    r = client.post(f"/api/absence-requests/{antrag}/review", json={"decision": "approved"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "approved"
    assert _abwesenheiten(welt) == [(welt["tom"].id, MO, MO, "schlechtwetter", "Schlechtwetter")]


# --- 1.9.170 Nr. 4: auch für Azubis ------------------------------------------------------------------------------------------------------

def test_schlechtwetter_auch_fuer_azubis(welt):  # noqa: F811
    db = welt["db"]
    azubi = make_employee(db, "A-1", "Ali", "Azubi")
    db.add(EmployeeProfile(employee_id=azubi.id, function_id=_funktion(db, "Dachdecker Auszubildende/r").id))
    db.commit()
    assert "Ali Azubi" in {p["name"] for p in _als(welt, "field", "kai").get("/api/schlechtwetter/kontext").json()["personen"]}
    r = _eintragen(_als(welt), azubi, welt["mia"])
    assert r.status_code == 200, r.text
    assert r.json()["genehmigt"] is True
    assert sorted(a[0] for a in _abwesenheiten(welt)) == sorted([azubi.id, welt["mia"].id])


# --- 1.9.170 Nr. 5: alles oder nichts, auch im zweiten Schritt ------------------------------------------------------------------------------

def test_alles_oder_nichts_wenn_eine_spaetere_person_schon_abwesend_ist(welt):  # noqa: F811
    """Mia ist schon abwesend; Tom steht vorn in der Auswahl -- auch für ihn wird nichts eingetragen, kein Antrag bleibt zurück."""
    client = _als(welt)
    assert _eintragen(client, welt["mia"]).status_code == 200
    vorher = _zaehlen(welt)
    r = _eintragen(client, welt["tom"], welt["mia"])
    assert r.status_code == 422 and "bereits" in r.json()["detail"], r.text
    assert _zaehlen(welt) == vorher
    assert [a[0] for a in _abwesenheiten(welt)] == [welt["mia"].id]


# --- 1.9.170 Nr. 6: laufende Zeit, Buchungen bleiben -----------------------------------------------------------------------------------------

def test_laufende_zeit_warnt_wie_gebuchte(welt):  # noqa: F811
    _buchung(welt, welt["mia"], status="running", hours=Decimal("0"))
    r = _eintragen(_als(welt), welt["mia"], welt["tom"])
    assert r.status_code == 409, r.text
    assert [(w["employee_id"], w["laeuft"]) for w in r.json()["warnungen"]] == [(welt["mia"].id, True)]
    assert "eine Zeit läuft" in r.json()["detail"]
    assert _zaehlen(welt) == (0, 0)


def test_trotzdem_laesst_die_buchungen_stehen(welt):  # noqa: F811
    eintrag = _buchung(welt, welt["mia"])
    assert _eintragen(_als(welt), welt["mia"], trotzdem=True).status_code == 200
    welt["db"].expire_all()
    zeit = welt["db"].get(TimeEntry, eintrag)
    assert zeit is not None and (zeit.status, Decimal(str(zeit.hours)), zeit.work_date) == ("booked", Decimal("3.5"), MO)
    assert _abwesenheiten(welt) == [(welt["mia"].id, MO, MO, "schlechtwetter", "Schlechtwetter")]


# --- 1.9.170 Nr. 8: nur der eigene Dialog ----------------------------------------------------------------------------------------------------

def test_plantafel_laesst_schlechtwetter_nicht_zu(welt):  # noqa: F811
    r = _client(welt, planning_router).post("/api/planning/absences", json={
        "employee_id": welt["mia"].id, "absence_category": "schlechtwetter", "start_date": MO.isoformat(), "end_date": MO.isoformat()})
    assert r.status_code == 422, r.text
    assert _zaehlen(welt) == (0, 0)


@pytest.mark.parametrize("vorlage, auswahl", [("zeiten.html", "adKategorie"), ("mobil_zeiten.html", "adKategorie"),
                                              ("planning.html", "absenceCategory")])
def test_allgemeine_dialoge_bieten_schlechtwetter_nicht_an(vorlage, auswahl):
    from tests import vorlagen_js as vj
    html = (vj.TEMPLATES / vorlage).read_text(encoding="utf-8")
    treffer = re.search(rf'<select id="{auswahl}"[^>]*>(.*?)</select>', html, re.S)
    assert treffer is not None, vorlage
    werte = re.findall(r'<option value="([^"]*)"', treffer.group(1))
    # seit 1.9.313 mit Sonderurlaub nach Urlaub (Lohn L2b, Punkt 1)
    assert werte == ["urlaub", "sonderurlaub", "krankheit", "fortbildung", "unbezahlt", "freizeitausgleich"], (vorlage, werte)


# --- 1.9.170 Nr. 9: wieder eingeschaltet -> Kachel -----------------------------------------------------------------------------------------

def test_wieder_eingeschaltete_zeitart_bekommt_ihre_kachel_zurueck(welt):  # noqa: F811
    from app.heute import zeitarten
    db = welt["db"]
    gruppe = db.scalar(select(SettingOptionGroup).where(SettingOptionGroup.group_key == "time_entry_types"))
    db.scalar(select(SettingOption).where(SettingOption.group_id == gruppe.id, SettingOption.value == "weather_winter")).active = True
    db.commit()
    werte = {z["value"] for z in zeitarten(db)}
    assert "weather_winter" in werte and "weather_summer" not in werte


# --- 1.9.171 Nr. 1: halber Tag nur bei Urlaub ---------------------------------------------------------------------------------------------

@pytest.mark.parametrize("kategorie", ["freizeitausgleich", "fortbildung", "unbezahlt"])
def test_halber_tag_nicht_bei_anderen_kategorien(welt, kategorie):  # noqa: F811
    r = _client(welt, absence_router.router).post("/api/absence-requests", json={
        "employee_id": welt["mia"].id, "absence_category": kategorie, "start_date": MO.isoformat(), "end_date": MO.isoformat(), "halber_tag": True})
    assert r.status_code == 422 and "halber Tag geht nur bei Urlaub" in r.json()["detail"], r.text
    assert _zaehlen(welt) == (0, 0)


# --- 1.9.171 Nr. 3: Plantafel je ganzem Tag ----------------------------------------------------------------------------------------------

def test_plantafel_rechnet_den_halben_urlaubstag_als_ganzen_tag(welt):  # noqa: F811
    from app.planning import planning_board
    db = welt["db"]
    antrag = create_request(db, employee_id=welt["mia"].id, absence_category="urlaub", start_date=MO, end_date=MO, halber_tag=True)
    review_request(db, antrag.id, decision="approved", reviewed_by_user_id=None)
    board = planning_board(db, MO, MO + timedelta(days=6))
    mia, tom = (board["employee_capacity"][str(welt[n].id)] for n in ("mia", "tom"))
    assert (mia[MO.isoformat()]["capacity_hours"], mia[MO.isoformat()]["absence"]) == (Decimal("0"), "Urlaub")
    assert tom[MO.isoformat()]["capacity_hours"] > 0 and mia[(MO + timedelta(days=1)).isoformat()]["capacity_hours"] > 0


# --- 1.9.171 Nr. 5 und 6: Sammeleintrag -------------------------------------------------------------------------------------------------

def _sammel(client, *leute, **mehr):
    return client.post("/api/absence-requests/sammel", json={"employee_ids": [p.id for p in leute], "absence_category": "urlaub",
                                                             "start_date": "2026-12-28", "end_date": "2026-12-30", **mehr})


def test_sammel_nennt_jede_person_auch_wer_schon_abwesend_ist(welt):  # noqa: F811
    """Mia hat am 29.12. Urlaub (genehmigt), Tom einen offenen Antrag: für niemanden eingetragen, die Meldung nennt beide."""
    db = welt["db"]
    review_request(db, create_request(db, employee_id=welt["mia"].id, absence_category="urlaub", start_date=date(2026, 12, 29),
                                      end_date=date(2026, 12, 29)).id, decision="approved", reviewed_by_user_id=None)
    create_request(db, employee_id=welt["tom"].id, absence_category="krankheit", start_date=date(2026, 12, 29), end_date=date(2026, 12, 29))
    vorher = _zaehlen(welt)
    r = _sammel(_client(welt, absence_router.router), welt["kai"], welt["mia"], welt["tom"])
    assert r.status_code == 422, r.text
    assert [x["employee_id"] for x in r.json()["liste"]] == [welt["mia"].id, welt["tom"].id]
    assert [x["text"].split(":")[0] for x in r.json()["liste"]] == ["Mia Monteurin", "Tom Monteur"]
    assert _zaehlen(welt) == vorher


def test_alle_heisst_alle_aktiven_auch_kaufmaennische(welt):  # noqa: F811
    db = welt["db"]
    weg = make_employee(db, "X-1", "Ina", "Inaktiv")
    weg.active = False
    db.commit()
    namen = {m["name"] for m in _client(welt, zeiten_router.router, rolle="buero_finanzen").get("/api/zeiten/abwesenheiten").json()["mitarbeiter"]}
    assert namen == {"Mia Monteurin", "Tom Monteur", "Kai Kolonne", "Uwe Ohnekolonne", "Vera Vorarbeiterin", "Bea Buero"}
    r = _sammel(_client(welt, absence_router.router), welt["bea"], welt["mia"])
    assert r.status_code == 200, r.text
    assert [x["status"] for x in r.json()] == ["approved", "approved"]


def test_sammel_schlechtwetter_auch_fuer_einen_tag_nicht(welt):  # noqa: F811
    r = _sammel(_client(welt, absence_router.router), welt["mia"], welt["tom"], absence_category="schlechtwetter", start_date=MO.isoformat(),
                end_date=MO.isoformat())
    assert r.status_code == 422, r.text
    assert _zaehlen(welt) == (0, 0)


# --- 1.9.172 Nr. 1: kein Modell -------------------------------------------------------------------------------------------------------------

def test_ohne_arbeitszeitmodell_zu_klaeren():
    db = neue_db()
    try:
        db.get(TimeBackofficeAdvancedSettings, 1).default_work_time_model_id = None
        for tabelle in (WorkTimeBreakRule, WorkTimeModelValidity, EmployeeWorkTimeModel, WorkTimeModel):
            db.query(tabelle).delete()
        db.commit()
        rc, zeilen = _lauf(db)
        assert rc == 1
        assert "Arbeitszeitmodelle: 0" in zeilen
        assert "  ! Kein Arbeitszeitmodell -- ohne Modell gibt es keine Sollzeit." in zeilen
    finally:
        bind = db.get_bind()
        db.close()
        bind.dispose()


# --- 1.9.173 Nr. 1: fester Tag im Klicktest ---------------------------------------------------------------------------------------------

def test_klicktest_monteurin_regeln_an_einem_festen_tag():
    """Instanz: klicktest_main(…, uhr="JJJJ-MM-TT HH:MM") -- ein Tag, nicht der Lauftag; Browser: tab.browser_uhr_fest(…) wird aufgerufen."""
    baum = ast.parse((ROOT / "scripts" / "klicktest_monteurin_regeln.py").read_text(encoding="utf-8"))
    aufrufe = [n for n in ast.walk(baum) if isinstance(n, ast.Call)]
    uhren = [k.value.value for n in aufrufe if isinstance(n.func, ast.Name) and n.func.id == "klicktest_main" for k in n.keywords
             if k.arg == "uhr" and isinstance(k.value, ast.Constant)]
    assert len(uhren) == 1 and re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", uhren[0]), uhren
    date.fromisoformat(uhren[0][:10])
    assert any(isinstance(n.func, ast.Attribute) and n.func.attr == "browser_uhr_fest" for n in aufrufe)
