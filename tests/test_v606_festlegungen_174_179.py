"""Seit 1.9.199 (Gegenproben zu den Festlegungen 1.9.175–1.9.178, L1a-Nachtrag): Tests für Festlegungen, deren Gegenprobe grün blieb.

    1.9.175 Nr. 1   „nur Montag bis Freitag“ wirkt auch bei eigener Sollzeit am Wochenende
    1.9.175 Nr. 2   die Abwesenheit des Kalenders wird nicht gespeichert (die Gegenprobe war rot, aber nur mittelbar über
                    test_v599 -- hier direkt)
    1.9.175 Nr. 6   eine Änderung am Kalender gilt auch für zurückliegende Jahre, die Seite sagt das
    1.9.175 Nr. 7   „Zeiten → Abwesenheiten“: ab heute, dieses und das nächste Jahr, ohne Samstag und Sonntag bei „nur Mo–Fr“, nur aktive Tage
    1.9.176 Nr. 1   Sammeleintrag: eine Antwort gilt für alle, für die der Tag gilt
    1.9.176 Nr. 6   gebuchte Arbeit an Silvester kommt zur Freistellung dazu
    1.9.176 Nr. 7   „Zeiten“ nennt die Antwort auch in der Liste „Prüfen“
    1.9.176 Nr. 8   jeder weitere Kalendertag kann „Rückfrage“ bekommen
    1.9.177 Nr. 1   Anlegen merkt die Mitarbeiternummer bei „DATEV-Nr. = ERP-Nr.“, das Einschalten der Gleichsetzung merkt nichts
    1.9.178 Nr. 3   beim Bestätigen eines Antrags fragt der Server nicht noch einmal nach dem betriebsfreien Tag

Feste Tage: Uhr 10.11.2026 (Fixture fester_tag); Dezember 2025–2028, Mo 07.12.2026.
"""

import json
from datetime import date, datetime
from decimal import Decimal

import pytest

from app.arbeitszeitkalender import abwesenheiten, kalendertag, naechste
from app.models import (ArbeitszeitKalendertag, Employee, EmployeeAbsence, EmployeeAbsenceRequest, PlanningHoliday, TimeBackofficeAdvancedSettings,
                        TimeEntry)
from app.routers import absence_requests as absence_router
from app.routers import schlechtwetter as schlechtwetter_router
from app.routers import time_backoffice as time_backoffice_router
from app.routers import zeiten as zeiten_router
from app.sollzeit import soll, zeile_anlegen
from tests.test_v224_field_view import make_employee
from tests.test_v325_contract_basis import beauftragen, make_quote
from tests.test_v518_zeiten_seite import _node, _text
from tests.test_v593_personalnummer_gesperrt import _client as pnr_client, _gemerkt

D = Decimal
KALENDER = "/api/time-backoffice/arbeitszeitkalender"
URLAUB = {"absence_category": "urlaub", "start_date": "2026-12-28", "end_date": "2027-01-08"}
MO = date(2026, 12, 7)


@pytest.fixture
def welt(threaded_db_session, router_test_client, fester_tag):
    db = threaded_db_session
    mia, tom = make_employee(db, "M-1", "Mia", "Monteurin"), make_employee(db, "M-2", "Tom", "Monteur")
    kim = Employee(employee_number="K-1", first_name="Kim", last_name="Kauffrau", employee_group="kaufmaennisch", active=True)
    db.add(kim)
    db.commit()
    return {"db": db, "mia": mia, "tom": tom, "kim": kim, "client": router_test_client}


def _als(w, rolle="admin", wer=None):
    w["db"].commit()
    return w["client"](w["db"], time_backoffice_router.router, absence_router.router, zeiten_router.router, schlechtwetter_router.router,
                       role=rolle, employee_id=w[wer].id if wer else None, user_id=9)


def _eintrag(**mehr):
    return {"name": "Rosenmontag", "monat": 2, "tag": 15, "sollzeit": None, "abwesenheit": "Rosenmontag – frei", "bezahlt": True,
            "im_urlaub": "kein_urlaubstag", "nur_gewerblich": True, "nur_mo_fr": True, "aktiv": True, **mehr}


# --- 1.9.175 Nr. 1: nur Montag bis Freitag --------------------------------------------------------------------------------------------------

def test_nur_mo_fr_auch_bei_eigener_sollzeit_am_wochenende(welt):
    """Gegenprobe zu Festlegung 1.9.175 Nr. 1 („nur Montag bis Freitag“ blieb grün, solange niemand am Wochenende Sollzeit hat): Tom mit
    eigener Sollzeit am Sonntag 4,00 h -- So 24.12.2028 bleibt 4,00 h, kein Kalendertag, keine Freistellung. Ohne „nur Mo–Fr“ gilt
    Heiligabend auch dort (7,00 h)."""
    db, tom = welt["db"], welt["tom"]
    zeile_anlegen(db, tom.id, date(2028, 12, 1), {"sonntag": D("4")})
    assert soll(db, tom.id, date(2028, 12, 24)) == D("4.00")
    assert kalendertag(db, tom.id, date(2028, 12, 24)) is None
    assert abwesenheiten(db, tom.id, date(2028, 12, 24), date(2028, 12, 24)) == []
    heiligabend = db.query(ArbeitszeitKalendertag).filter_by(schluessel="heiligabend").one()
    heiligabend.nur_mo_fr = False
    db.commit()
    assert soll(db, tom.id, date(2028, 12, 24)) == D("7.00")
    assert [a["stunden"] for a in abwesenheiten(db, tom.id, date(2028, 12, 24), date(2028, 12, 24))] == [D("7.00")]


# --- 1.9.175 Nr. 2: nicht gespeichert -------------------------------------------------------------------------------------------------------

def test_abwesenheit_des_kalenders_wird_nicht_gespeichert(welt):
    """Gegenprobe zu Festlegung 1.9.175 Nr. 2: abwesenheiten() leitet je Tag ab -- nichts kommt in die Sitzung, keine Abwesenheit, kein Antrag."""
    db, mia = welt["db"], welt["mia"]
    assert [a["tag"] for a in abwesenheiten(db, mia.id, date(2026, 12, 1), date(2027, 12, 31))] == [
        date(2026, 12, 24), date(2026, 12, 31), date(2027, 12, 24), date(2027, 12, 31)]
    assert not db.new and not db.dirty
    assert db.query(EmployeeAbsence).count() == 0 and db.query(EmployeeAbsenceRequest).count() == 0


# --- 1.9.175 Nr. 6: auch für zurückliegende Jahre -------------------------------------------------------------------------------------------

def test_aenderung_gilt_auch_fuer_zurueckliegende_jahre(welt):
    """Gegenprobe zu Festlegung 1.9.175 Nr. 6: Heiligabend am 10.11.2026 auf 6,50 h geändert -- das gilt auch für Mi 24.12.2025."""
    db, mia = welt["db"], welt["mia"]
    client = _als(welt, "buero_finanzen")
    heiligabend = next(e for e in client.get(KALENDER).json()["eintraege"] if e["schluessel"] == "heiligabend")
    r = client.put(f"{KALENDER}/{heiligabend['id']}", json=_eintrag(name="Heiligabend", monat=12, tag=24, sollzeit="6.5",
                                                                   abwesenheit="Heiligabend – bezahlte Freistellung"))
    assert r.status_code == 200, r.text
    db.expire_all()
    assert soll(db, mia.id, date(2025, 12, 24)) == D("6.50")
    assert [(a["tag"], a["stunden"]) for a in abwesenheiten(db, mia.id, date(2025, 12, 1), date(2025, 12, 31)) if a["schluessel"] == "heiligabend"] == [
        (date(2025, 12, 24), D("6.50"))]


def test_seite_sagt_zurueckliegende_jahre():
    """Gegenprobe zu Festlegung 1.9.175 Nr. 6 („die Seite sagt das“): der Block „Arbeitszeitkalender“ in den Einstellungen."""
    from tests import vorlagen_js as vj
    einstellungen = (vj.TEMPLATES / "settings.html").read_text(encoding="utf-8")
    block = einstellungen[einstellungen.index('id="kalenderBlock"'):]
    block = block[:block.index("</h3>") + 600]
    assert "Eine Änderung gilt auch für zurückliegende Jahre" in block


# --- 1.9.175 Nr. 7: „Zeiten → Abwesenheiten“ -----------------------------------------------------------------------------------------------

@pytest.fixture
def mehr_tage(welt):
    """Dazu Rosenmontag (15.02., aktiv) und ein abgeschaltetes Betriebsfest (01.06.) -- beide nur gewerbliche, nur Mo–Fr."""
    db = welt["db"]
    db.add_all([
        ArbeitszeitKalendertag(schluessel="rosenmontag", name="Rosenmontag", monat=2, tag=15, abwesenheit="Rosenmontag – frei", bezahlt=True,
                               im_urlaub="kein_urlaubstag", nur_gewerblich=True, nur_mo_fr=True, aktiv=True),
        ArbeitszeitKalendertag(schluessel="betriebsfest", name="Betriebsfest", monat=6, tag=1, abwesenheit="Betriebsfest – frei", bezahlt=True,
                               im_urlaub="kein_urlaubstag", nur_gewerblich=True, nur_mo_fr=True, aktiv=False)])
    db.commit()
    return welt


def _naechste(w):
    """Heute Mo 01.03.2027: dieses und das nächste Jahr."""
    return [(z["tag"], z["name"]) for z in naechste(w["db"], date(2027, 3, 1))]


def test_naechste_ab_heute(mehr_tage):
    """Rosenmontag Mo 15.02.2027 liegt vor heute -- nicht in der Liste; Di 15.02.2028 schon."""
    tage = [t for t, _n in _naechste(mehr_tage)]
    assert date(2027, 2, 15) not in tage and date(2028, 2, 15) in tage


def test_naechste_ohne_samstag_und_sonntag(mehr_tage):
    """Heiligabend und Silvester 2028 sind Sonntage -- bei „nur Mo–Fr“ nicht in der Liste."""
    tage = [t for t, _n in _naechste(mehr_tage)]
    assert date(2028, 12, 24) not in tage and date(2028, 12, 31) not in tage and date(2027, 12, 24) in tage


def test_naechste_nur_aktive_tage(mehr_tage):
    assert "Betriebsfest" not in {n for _t, n in _naechste(mehr_tage)}


def test_naechste_ganz(mehr_tage):
    assert _naechste(mehr_tage) == [(date(2027, 12, 24), "Heiligabend"), (date(2027, 12, 31), "Silvester"), (date(2028, 2, 15), "Rosenmontag")]


# --- 1.9.176 Nr. 1, 6, 7, 8 -----------------------------------------------------------------------------------------------------------------

def test_sammeleintrag_eine_antwort_fuer_alle(welt):
    """Gegenprobe zu Festlegung 1.9.176 Nr. 1: Mia, Tom (gewerblich) und Kim (kaufmännisch) über Silvester mit „frei“ -- die Antwort steht an
    Mias und Toms Antrag, an Kims keine (für sie gilt der Tag nicht)."""
    r = _als(welt).post("/api/absence-requests/sammel", json={"employee_ids": [welt["mia"].id, welt["tom"].id, welt["kim"].id], **URLAUB,
                                                               "kalendertag_urlaub": False})
    assert r.status_code == 200, r.text
    assert {x["employee_name"]: x["kalendertag_urlaub"] for x in r.json()} == {"Mia Monteurin": False, "Tom Monteur": False, "Kim Kauffrau": None}


def test_gebuchte_arbeit_an_silvester_kommt_dazu(welt):
    """Gegenprobe zu Festlegung 1.9.176 Nr. 6: 4,00 h gebucht an Do 31.12.2026 -- die Freistellung bleibt mit der Sollzeit 7,50 h."""
    db, mia = welt["db"], welt["mia"]
    order = beauftragen(db, make_quote(db, is_consumer=False, number="0606"))
    db.add(TimeEntry(employee_id=mia.id, project_id=order.project_id, order_id=order.id, work_date=date(2026, 12, 31), entry_type="site",
                     hours=D("4.00"), break_minutes=0, status="booked", started_at=datetime(2026, 12, 31, 7), ended_at=datetime(2026, 12, 31, 11)))
    db.commit()
    assert [(a["schluessel"], a["stunden"]) for a in abwesenheiten(db, mia.id, date(2026, 12, 31), date(2026, 12, 31))] == [("silvester", D("7.50"))]


def test_beide_listen_unter_zeiten_nennen_die_antwort():
    """Gegenprobe zu Festlegung 1.9.176 Nr. 7: „Zeiten“ nennt die Antwort zu Silvester in beiden Listen -- „Prüfen“ (antragHtml, offene
    Anträge; bis hierher von keinem Test gelesen) und „Abwesenheiten“ (abwesenheitHtml, dort prüft es auch klicktest_silvester)."""
    vorweg = ("var KATEGORIE={urlaub:'Urlaub'};var STATUS={pending:['offen','chip-info']};function berlinZeitpunkt(w,a){return '10.11.2026'};"
              "var ZURUECK=null;var RECHTE={admin:false};var P=null;")
    antrag = {"id": 4, "employee_name": "Mia Monteurin", "absence_type": "Urlaub", "absence_category": "urlaub", "start_date": "2026-12-28",
              "end_date": "2027-01-08", "arbeitstage": 8, "created_at": "2026-11-10T08:00:00", "notes": None, "review_notes": None,
              "status": "pending", "darf_entscheiden": False, "darf_zurueckziehen": False, "beantragt_von": None, "halber_tag": False}
    for antwort, text in ((True, "Kalendertag als Urlaubstag"), (False, "Kalendertag frei, kein Urlaubstag"), (None, None)):
        a = {**antrag, "kalendertag_urlaub": antwort}
        zeilen = [_text(h) for h in _node(("beantragtText", "kontoDanachZeile", "abwesenheitHtml", "antragHtml"),
                                          f"return [abwesenheitHtml({json.dumps(a)}),antragHtml({json.dumps(a)})]", vorweg=vorweg)]
        if text is None:
            assert not any("Kalendertag" in z for z in zeilen), zeilen
        else:
            assert all(f"Mo 28.12.2026–Fr 08.01.2027 · {text} · 8 Arbeitstage" in z for z in zeilen), zeilen


def test_ein_weiterer_kalendertag_mit_rueckfrage(welt):
    """Gegenprobe zu Festlegung 1.9.176 Nr. 8: ein neuer Kalendertag „Brückentag“ (07.12.) mit „Rückfrage“ -- angelegt von Büro – Finanzen; ein
    Urlaub darüber fragt wie an Silvester, die Antwort steht am Antrag."""
    r = _als(welt, "buero_finanzen").post(KALENDER, json=_eintrag(name="Brückentag", monat=12, tag=7, abwesenheit="Brückentag – unbezahlt frei",
                                                                  bezahlt=False, im_urlaub="fragen"))
    assert r.status_code == 200, r.text
    client = _als(welt)
    body = {"employee_id": welt["mia"].id, "absence_category": "urlaub", "start_date": "2026-12-07", "end_date": "2026-12-11"}
    r = client.post("/api/absence-requests", json=body)
    assert r.status_code == 409, r.text
    assert r.json()["rueckfrage"] == {"tage": [{"tag": "2026-12-07", "name": "Brückentag", "abwesenheit": "Brückentag – unbezahlt frei"}]}
    r = client.post("/api/absence-requests", json={**body, "kalendertag_urlaub": False})
    assert (r.status_code, r.json()["kalendertag_urlaub"]) == (200, False)


# --- 1.9.177 Nr. 1: gemerkt beim Anlegen, nicht beim Einschalten ----------------------------------------------------------------------------

@pytest.fixture
def pnr(threaded_db_session, router_test_client, fester_tag):
    db = threaded_db_session
    mia, tom = make_employee(db, "M-1", "Mia", "Monteurin"), make_employee(db, "M-2", "Tom", "Monteur")
    return {"db": db, "mia": mia, "tom": tom, "client": router_test_client}


def test_anlegen_merkt_keine_mitarbeiternummer(pnr):
    """Seit 1.9.230 (Stufe 6, R3a, Punkt 0a): „DATEV-Nr. = ERP-Nr.“ ist entfallen (bis 1.9.229
    test_anlegen_merkt_die_mitarbeiternummer_bei_gleichsetzung: das Anlegen merkte 91005). Auch mit der alten Spalte auf „an“ merkt es nichts."""
    pnr["db"].get(TimeBackofficeAdvancedSettings, 1).datev_personnel_equals_erp_number = True
    client = pnr_client(pnr)
    neu = {k: v for k, v in client.get(f"/api/employees/{pnr['tom'].id}").json().items()
           if k not in ("id", "function_name", "effective_hourly_wage", "annual_gross_wage")}
    r = client.post("/api/employees", json={**neu, "employee_number": "91005", "first_name": "Lea"})
    assert r.status_code == 200, r.text
    assert _gemerkt(pnr) == []


def test_den_schalter_gibt_es_nicht_mehr(pnr):
    """Seit 1.9.230 (Stufe 6, R3a, Punkt 0a): „DATEV-Nr. = ERP-Nr.“ ist entfallen (bis 1.9.229 test_einschalten_der_gleichsetzung_merkt_nichts:
    einschalten ging und merkte nichts). Die Zeitregeln nennen ihn nicht, ein mitgeschickter Wert wird nicht übernommen, nichts gemerkt."""
    client = pnr_client(pnr)
    stand = client.get("/api/time-backoffice/settings").json()
    assert "datev_personnel_equals_erp_number" not in stand
    r = client.put("/api/time-backoffice/settings", json={**stand, "datev_personnel_equals_erp_number": True})
    assert r.status_code == 200, r.text
    assert "datev_personnel_equals_erp_number" not in r.json()
    pnr["db"].expire_all()
    assert not pnr["db"].get(TimeBackofficeAdvancedSettings, 1).datev_personnel_equals_erp_number
    assert _gemerkt(pnr) == []


# --- 1.9.178 Nr. 3: Bestätigen fragt nicht noch einmal --------------------------------------------------------------------------------------

def test_bestaetigen_fragt_nicht_noch_einmal(threaded_db_session, router_test_client, fester_tag):
    """Gegenprobe zu Festlegung 1.9.178 Nr. 3: Uwe (Monteur, ohne Kolonne) beantragt Schlechtwetter am betriebsfreien Mo 07.12.2026 -- er sah die
    Rückfrage und bestätigte „trotzdem“; der Admin bestätigt den Antrag ohne neue Rückfrage."""
    db = threaded_db_session
    uwe = make_employee(db, "M-4", "Uwe", "Ohnekolonne")
    db.add(PlanningHoliday(holiday_date=MO, name="Betriebsausflug", active=True))
    db.commit()

    def als(rolle, employee_id=None):
        db.commit()
        return router_test_client(db, schlechtwetter_router.router, absence_router.router, role=rolle, employee_id=employee_id, user_id=7)

    monteur = als("field", uwe.id)
    body = {"employee_ids": [uwe.id], "tag": MO.isoformat(), "trotzdem": False}
    assert monteur.post("/api/schlechtwetter", json=body).status_code == 409
    r = monteur.post("/api/schlechtwetter", json={**body, "trotzdem": True})
    assert (r.status_code, r.json()["genehmigt"]) == (200, False)
    r = als("admin").post(f"/api/schlechtwetter/{r.json()['antraege'][0]['id']}/entscheiden", json={"decision": "approved"})
    assert (r.status_code, r.json()["status"]) == (200, "approved"), r.text
    db.expire_all()
    assert db.query(EmployeeAbsence).filter_by(employee_id=uwe.id, absence_category="schlechtwetter").count() == 1
