"""Seit 1.9.201 (Gegenproben zu den Festlegungen 1.9.186–1.9.191, Lohn L1a, Stufe 2): Tests für Aussagen der Festlegungen, deren Gegenprobe
ohne sie grün blieb.

    1.9.186 Nr. 2      in einem Monat vor dem Start ist eine laufende Zeit weder angeheftet noch eine Zeile -- nur im Monat nach dem Start angeheftet
    1.9.187 Nr. 2      Kacheln und „Monat“ zählen nur Buchungen: ein Monat mit Freistellungen und ohne Buchung bleibt bei 0 h und 0 Tagen
    1.9.188 Nr. 4      Büro – Auftrag sieht an der Freistellung am Mitarbeiter „abwesend“, in der Kolonne keine Art; der Hinweis am Einsatz nennt
                       den Tag auch ihm
    1.9.189 Nr. 1      in der Tabelle der Personalnummern steht nur die Spalte Mitarbeiter (links), die Kopfzeile ist nicht oben angeheftet
    1.9.191 Nr. 1      „(trägt heute …)“ bekommt jede Rolle, die die Liste liest -- auch Büro – Auftrag
    1.9.191 Nr. 2      getragen <=> 409 beim Freigeben: die eigene frühere Nummer in den Lohnstammdaten (bei „DATEV-Nr. = ERP-Nr.“) nennt die Person
                       selbst; ohne Gleichsetzung zählt eine Mitarbeiternummer nicht
"""

import re
from datetime import date, datetime, time, timedelta
from decimal import Decimal

import pytest

from app.models import EmployeePayrollSettings, TeamEmployee, TimeBackofficeAdvancedSettings
from app.routers import field_view as field_view_router
from app.routers import time_tracking as time_tracking_router
from app.routers.planning import router as planning_router
from app.sollzeit import zeile_anlegen
from app.time_tracking import start_timer
from tests import vorlagen_js as vj
from tests.test_v090_planning_board import setup_order
from tests.test_v224_field_view import make_employee, make_team
from tests.test_v325_contract_basis import beauftragen, make_quote
from tests.test_v563_konflikte_beim_speichern import _kolonne, _person
from tests.test_v593_personalnummer_gesperrt import _client, _put
from tests.uhr import uhr_festhalten

D = Decimal
FREIGEBEN = "/api/time-backoffice/personalnummern/freigeben"


# --- 1.9.186 Nr. 2 und 1.9.187 Nr. 2: „Meine Zeiten“ ------------------------------------------------------------------------------

def _zeiten_welt(db, router_test_client):
    order = beauftragen(db, make_quote(db, is_consumer=False, number="0608a"))
    team = make_team(db, "K-1", "Kolonne 1")
    mia = make_employee(db, "M-1", "Mia", "Monteurin")
    db.add(TeamEmployee(team_id=team.id, employee_id=mia.id, is_crew_leader=False))
    db.commit()
    return {"db": db, "order": order, "mia": mia, "client": router_test_client}


def _meine_zeiten(w, monat):
    client = w["client"](w["db"], time_tracking_router.router, field_view_router.router, role="field", employee_id=w["mia"].id)
    antwort = client.get("/api/field-view/meine-zeiten", params={"monat": monat})
    assert antwort.status_code == 200, antwort.text
    return antwort.json()


def test_186_2_im_monat_vor_dem_start_weder_angeheftet_noch_zeile(threaded_db_session, router_test_client):
    """Uhr Di 01.12.2026: Mia startete am Mo 30.11. um 07:00 (Feierabend vergessen). Oktober: nichts; November: an ihrem Tag; Dezember: angeheftet."""
    with uhr_festhalten(tag=date(2026, 12, 1)):
        w = _zeiten_welt(threaded_db_session, router_test_client)
        row = start_timer(w["db"], employee_id=w["mia"].id, order_id=w["order"].id, started_at=datetime.combine(date(2026, 11, 30), time(7)))
        ergebnis = {}
        for monat in ("2026-10", "2026-11", "2026-12"):
            d = _meine_zeiten(w, monat)
            ergebnis[monat] = (d["angeheftet"]["id"] if d["angeheftet"] else None, [z["id"] for t in d["tage"] for z in t["zeilen"]])
        assert ergebnis == {"2026-10": (None, []), "2026-11": (None, [row.id]), "2026-12": (row.id, [])}


def test_187_2_kacheln_und_monat_ohne_freistellungen(threaded_db_session, router_test_client):
    """Uhr Do 24.12.2026 (Heiligabend), keine Buchung: die Freistellungen stehen da (Heiligabend 7,00 h, Silvester 7,50 h), Kacheln und
    „Monat“ bleiben bei 0 h und 0 Tagen, „Buchungen“ ohne Tag."""
    with uhr_festhalten(tag=date(2026, 12, 24)):
        w = _zeiten_welt(threaded_db_session, router_test_client)
        d = _meine_zeiten(w, "2026-12")
        assert [(f["tag"], D(str(f["stunden"]))) for f in d["freistellungen"]] == [("2026-12-24", D("7.00")), ("2026-12-31", D("7.50"))]
        assert {k: D(str(v)) for k, v in d["kacheln"].items()} == {"heute": 0, "woche": 0, "monat": 0}
        assert (d["monat_tage"], D(str(d["monat_fahrzeit"])), D(str(d["monat_produktiv"])), d["tage"]) == (0, 0, 0, [])


# --- 1.9.188 Nr. 4: Plantafel für Büro – Auftrag -----------------------------------------------------------------------------------

def test_188_4_buero_auftrag_sieht_abwesend_und_den_tag_im_hinweis(threaded_db_session, router_test_client, fester_tag):
    """Mia (Tarif), Tom (Teilzeit Di–Do) und Ben (Teilzeit Mo–Di, am Donnerstag keine Sollzeit) in Kolonne A, Einsatz 21.–24.12.2026: Büro –
    Auftrag sieht am 24.12. bei Mia und Tom „abwesend“ wie bei jeder Abwesenheit (eine gespeicherte Krankheit bei Ben am 22.12. zum Vergleich),
    in der Kolonne die Abwesenden ohne Art; der Hinweis am Einsatz nennt den Tag wie für den Admin."""
    from app.models import EmployeeAbsence
    db = threaded_db_session
    mia, tom, ben = _person(db, "M-1", "Mia"), _person(db, "M-2", "Tom"), _person(db, "M-3", "Ben")
    zeile_anlegen(db, tom.id, date(2026, 12, 1), {"dienstag": D("3"), "mittwoch": D("3"), "donnerstag": D("3")})
    zeile_anlegen(db, ben.id, date(2026, 12, 1), {"montag": D("8"), "dienstag": D("8")})
    db.add(EmployeeAbsence(employee_id=ben.id, absence_type="Krankheit", absence_category="krankheit", start_date=date(2026, 12, 22),
                           end_date=date(2026, 12, 22)))
    db.commit()
    team = _kolonne(db, "A", [mia, tom, ben])
    order = setup_order(db, "1")
    admin = router_test_client(db, planning_router)
    angelegt = admin.post("/api/planning/slots", json={"order_id": order.id, "team_id": team.id, "start_date": "2026-12-21", "end_date": "2026-12-24",
                                                       "planned_hours": "1", "trotzdem_planen": True})
    assert angelegt.status_code == 200, angelegt.text
    zeitraum = {"start": "2026-12-21", "end": "2026-12-27"}
    buero = router_test_client(db, planning_router, role="buero_auftrag").get("/api/planning", params=zeitraum)
    assert buero.status_code == 200, buero.text
    b = buero.json()
    leute = b["employee_capacity"]
    assert [leute[str(p.id)]["2026-12-24"]["absence"] for p in (mia, tom, ben)] == ["abwesend", "abwesend", None]
    assert leute[str(ben.id)]["2026-12-22"]["absence"] == "abwesend"  # wie bei jeder Abwesenheit
    kolonne = b["team_capacity"][str(team.id)]["2026-12-24"]["absences"]
    assert sorted(a["name"] for a in kolonne) == ["Mia Test", "Tom Test"] and all("type" not in a for a in kolonne)
    hinweise = {rolle: [(k["type"], k["label"]) for k in antwort["slots"][0]["conflicts"] if k["type"] == "kalendertag"]
                for rolle, antwort in (("admin", admin.get("/api/planning", params=zeitraum).json()), ("buero_auftrag", b))}
    assert hinweise == {"admin": [("kalendertag", "Heiligabend – Mia Test, Tom Test")],
                        "buero_auftrag": [("kalendertag", "Heiligabend – Mia Test, Tom Test")]}


# --- 1.9.189 Nr. 1: Tabelle der Personalnummern ------------------------------------------------------------------------------------

def test_189_1_nur_die_spalte_mitarbeiter_steht_die_kopfzeile_rollt_mit():
    """Die Lage misst scripts/klicktest_personalnummer_freigeben.py beim waagrechten Rollen; hier die Regel: angeheftet (sticky) ist in der Tabelle
    nur die erste Spalte („Mitarbeiter“), links -- keine Regel heftet Zellen oben an (die Kopfzeile rollt senkrecht mit)."""
    text = vj.seitentext("settings.html")[0]
    assert '<table class="lohn-tabelle"><thead><tr><th>Mitarbeiter</th>' in text
    regeln = [(re.sub(r"/\*.*?\*/", "", sel, flags=re.S).strip(), dekl) for sel, dekl in re.findall(r"([^{}]*\.lohn-tabelle[^{}]*)\{([^}]*)\}", text)]
    angeheftet = [(sel, dekl) for sel, dekl in regeln if "sticky" in dekl]
    assert [sel for sel, _ in angeheftet] == [".lohn-tabelle th:first-child,.lohn-tabelle td:first-child"]
    for _sel, dekl in angeheftet:
        teile = set(dekl.split(";"))
        assert {"position:sticky", "left:0"} <= teile and not any(t.startswith(("top:", "bottom:")) for t in teile)
    assert not any("top:" in dekl or "bottom:" in dekl for _sel, dekl in regeln)


# --- 1.9.191: Träger früherer Personalnummern --------------------------------------------------------------------------------------

@pytest.fixture
def nummern(threaded_db_session, router_test_client, fester_tag):
    db = threaded_db_session
    mia, tom = make_employee(db, "M-1", "Mia", "Monteurin"), make_employee(db, "M-2", "Tom", "Monteur")
    return {"db": db, "mia": mia, "tom": tom, "client": router_test_client}


def _zeile(w, name, rolle="buero_finanzen"):
    r = _client(w, rolle).get("/api/time-backoffice/payroll-employees")
    assert r.status_code == 200, r.text
    z = next(z for z in r.json() if z["employee_name"] == name)
    return z["fruehere_personalnummern"], z["fruehere_traeger"]


def test_191_1_jede_rolle_der_liste_sieht_den_traeger(nummern):
    """Mia 91008 -> 91016, Tom trägt 91008 (an der Sperre vorbei): Admin, Büro – Finanzen und lesend Büro – Auftrag sehen Tom als Träger."""
    w = nummern
    assert _put(w, w["mia"], datev_personnel_number="91008").status_code == 200
    assert _put(w, w["mia"], datev_personnel_number="91016").status_code == 200
    w["db"].add(EmployeePayrollSettings(employee_id=w["tom"].id, datev_personnel_number="91008", payroll_export_enabled=True))
    w["db"].commit()
    assert {rolle: _zeile(w, "Mia Monteurin", rolle) for rolle in ("admin", "buero_finanzen", "buero_auftrag")} == {
        rolle: (["91008"], {"91008": "Tom Monteur"}) for rolle in ("admin", "buero_finanzen", "buero_auftrag")}


def test_191_2_alte_gleichsetzung_aendert_die_heutige_nummer_nicht(nummern):
    """Seit 1.9.230 (Stufe 6, R3a, Punkt 0a): „DATEV-Nr. = ERP-Nr.“ ist entfallen (bis 1.9.229
    test_191_2_eigene_fruehere_nummer_in_den_lohnstammdaten_nennt_die_person_selbst: mit dem Schalter war M-1 ihre Nummer, 91008 „früher“). Auch mit
    der alten Spalte auf „an“ bleibt 91008 ihre heutige Nummer -- keine „frühere“, die Freigabe lehnt ab (409, sie trägt sie)."""
    w = nummern
    assert _put(w, w["mia"], datev_personnel_number="91008").status_code == 200
    w["db"].get(TimeBackofficeAdvancedSettings, 1).datev_personnel_equals_erp_number = True
    assert _zeile(w, "Mia Monteurin") == ([], {})
    assert _client(w, "admin").post(FREIGEBEN, json={"nummer": "91008"}).status_code == 409


def test_191_2_ohne_gleichsetzung_zaehlt_die_mitarbeiternummer_nicht(nummern):
    """Ohne „DATEV-Nr. = ERP-Nr.“: Tom hat die Mitarbeiternummer 91008, Mias frühere DATEV-Nummer -- er trägt sie nicht (dieselbe Regel wie die
    Freigabe: niemand genannt, die Freigabe geht)."""
    w = nummern
    assert _put(w, w["mia"], datev_personnel_number="91008").status_code == 200
    assert _put(w, w["mia"], datev_personnel_number="91016").status_code == 200
    w["tom"].employee_number = "91008"
    w["db"].commit()
    assert _zeile(w, "Mia Monteurin") == (["91008"], {})
    assert _client(w, "admin").post(FREIGEBEN, json={"nummer": "91008"}).status_code == 200
