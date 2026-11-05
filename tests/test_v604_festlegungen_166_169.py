"""Seit 1.9.197 (Gegenproben zu den Festlegungen 1.9.166–1.9.169, Lohn L1a): was eine Gegenprobe ausheben konnte, ohne dass ein Test rot wurde.

    1.9.166 Nr. 3   Lesart A gilt für jede Pausenregel eines Modells, auch für selbst angelegte; Schwellen und Pausen je Modell
    1.9.167 Nr. 1   ohne eigene Werte gilt der Tarif auch für Azubis und Aushilfen
    1.9.167 Nr. 3   Eintritt und Austritt prüfen „Abgeschlossen bis“ nicht (nur die eigene Sollzeit)
    1.9.167 Nr. 4   eine Änderung am Modell gilt auch rückwirkend; die Seite sagt, sie erst nach dem Abschluss der Monate davor zu ändern
    1.9.168 Nr. 2   bei „DATEV-Nr. = ERP-Nr.“ gilt das Format auch beim Umfang „nur Abwesenheiten“ -- von der Person geht etwas in die Datei
    1.9.169 Nr. 5   eine Zeile je Art entsteht erst beim ersten Speichern (außer Weiterbildung)

Feste Tage (Fixture fester_tag, Dienstag 10.11.2026), nicht relativ zu heute.
"""

from datetime import date, datetime, time
from decimal import Decimal

import pytest

from app.models import EmployeeFunction, EmployeeProfile, LohnartZuordnung, TimeBackofficeAdvancedSettings, TimeTrackingSettings, WorkTimeModel
from app.routers import time_backoffice as time_backoffice_router
from app.sollzeit import soll
from app.time_tracking import start_timer, stop_timer
from app.work_time_models import automatic_break_minutes_for_duration, fehlende_pause_am_tag, save_model, set_employee_model
from tests.test_v224_field_view import make_employee
from tests.test_v325_contract_basis import beauftragen, make_quote

D = Decimal
TAG = date(2026, 11, 9)  # Montag vor dem festen Tag
ABGESCHLOSSEN = date(2026, 10, 31)


@pytest.fixture
def welt(threaded_db_session, router_test_client, fester_tag):
    db = threaded_db_session
    mia = make_employee(db, "M-1", "Mia", "Monteurin")
    db.commit()
    return {"db": db, "mia": mia, "client": router_test_client}


def _als(w, rolle="buero_finanzen"):
    w["db"].commit()
    return w["client"](w["db"], time_backoffice_router.router, role=rolle)


def _h(hm: str) -> Decimal:
    s, m = hm.split(":")
    return (D(int(s)) + D(int(m)) / 60).quantize(D("0.0001"))


# --- 1.9.166 Nr. 3: Lesart A für selbst angelegte Pausenregeln -------------------------------------------------------------------------

def test_selbst_angelegte_pausenregeln_nach_lesart_a(welt):
    """Ein eigenes Modell mit 5 h -> 20 min und 8 h -> 40 min: je Regel höchstens die Minuten über ihrer Schwelle (wie bei den Grundregeln
    6 h und 9 h). Bucht man 07:00–12:15, bleiben 15 min Pause und 5,00 h; eine Dauer von 5,25 h braucht ihre volle Pause von 20 min."""
    db, mia = welt["db"], welt["mia"]
    modell = save_model(db, model_id=None, name="Eigenes Modell", code=None, daily_target_hours=D("8"), valid_from_week=1, valid_to_week=53,
                        description=None, active=True, sort_order=30,
                        break_rules=[{"threshold_hours": "5", "break_minutes": 20}, {"threshold_hours": "8", "break_minutes": 40}])
    set_employee_model(db, mia.id, modell.id)
    pausen = {hm: automatic_break_minutes_for_duration(db, mia.id, _h(hm), TAG)
              for hm in ("5:00", "5:10", "5:30", "6:15", "8:15", "8:30", "8:45", "9:30")}
    assert pausen == {"5:00": 0, "5:10": 10, "5:30": 20, "6:15": 20, "8:15": 20, "8:30": 30, "8:45": 40, "9:30": 40}
    assert fehlende_pause_am_tag(db, mia.id, D("5.25"), 0, TAG) == 20
    order = beauftragen(db, make_quote(db, is_consumer=False, number="0604"))
    row = start_timer(db, employee_id=mia.id, order_id=order.id, started_at=datetime.combine(TAG, time(7)))
    row = stop_timer(db, row.id, ended_at=datetime.combine(TAG, time(12, 15)))
    assert (row.break_minutes, row.hours) == (15, D("5.0000"))


# --- 1.9.167 Nr. 1: Tarif auch für Azubis und Aushilfen ----------------------------------------------------------------------------------

def test_tarif_auch_fuer_azubis_und_aushilfen(welt):
    """Ohne eigene Werte zählen weder die Funktion (Auszubildende/r) noch die Wochenstunden am Mitarbeiter (Aushilfe mit 10 h): beide haben
    die Sollzeit des Tarifs -- wer anders arbeitet, bekommt eigene Werte."""
    db = welt["db"]
    azubi, aushilfe = make_employee(db, "A-1", "Ali", "Azubi"), make_employee(db, "H-1", "Hanna", "Aushilfe")
    funktion = db.query(EmployeeFunction).filter_by(name="Dachdecker Auszubildende/r").one()
    db.add(EmployeeProfile(employee_id=azubi.id, function_id=funktion.id))
    aushilfe.weekly_hours = D("10")
    db.commit()
    for tag, stunden in ((date(2026, 11, 27), "8.00"), (date(2026, 11, 30), "7.50"), (date(2026, 11, 28), "0")):  # Fr KW 48, Mo KW 49, Sa
        assert (soll(db, azubi.id, tag), soll(db, aushilfe.id, tag)) == (D(stunden), D(stunden)), tag


# --- 1.9.167 Nr. 3: Eintritt und Austritt prüfen den Abschluss nicht ---------------------------------------------------------------------

def test_eintritt_und_austritt_auch_im_abgeschlossenen_zeitraum(welt):
    """Anders als die eigene Sollzeit (409) speichert der Server Eintritt und Austritt auch vor „Abgeschlossen bis“; die Sollzeit folgt."""
    db, mia = welt["db"], welt["mia"]
    db.get(TimeTrackingSettings, 1).locked_until = ABGESCHLOSSEN
    r = _als(welt).put(f"/api/time-backoffice/payroll-employees/{mia.id}", json={"eintritt": "2026-10-05", "austritt": "2026-10-30"})
    assert r.status_code == 200, r.text
    assert (r.json()["eintritt"], r.json()["austritt"]) == ("2026-10-05", "2026-10-30")
    assert [soll(db, mia.id, t) for t in (date(2026, 10, 2), date(2026, 10, 5), date(2026, 10, 30), date(2026, 11, 2))] == [
        D("0"), D("8.00"), D("8.00"), D("0")]


# --- 1.9.167 Nr. 4: eine Änderung am Modell gilt rückwirkend -----------------------------------------------------------------------------

def test_modellaenderung_gilt_auch_im_abgeschlossenen_zeitraum(welt):
    """Das Wintermodell auf 7,00 h: gespeichert, obwohl bis 31.10.2026 abgeschlossen ist, und die Sollzeit eines abgeschlossenen Wintertags
    (Mo 02.03.2026, KW 10) ändert sich mit -- es gibt keine Fassungen je Zeitraum."""
    db, mia = welt["db"], welt["mia"]
    db.get(TimeTrackingSettings, 1).locked_until = ABGESCHLOSSEN
    assert soll(db, mia.id, date(2026, 3, 2)) == D("7.50")
    winter = db.query(WorkTimeModel).filter_by(code="winter").one()
    koerper = {"name": winter.name, "code": "winter", "daily_target_hours": "7", "valid_from_week": 49, "valid_to_week": 17, "active": True,
               "sort_order": winter.sort_order,
               "break_rules": [{"id": r.id, "threshold_hours": str(r.threshold_hours), "break_minutes": r.break_minutes} for r in winter.break_rules]}
    r = _als(welt).put(f"/api/time-backoffice/work-time-models/{winter.id}", json=koerper)
    assert r.status_code == 200, r.text
    db.expire_all()
    assert soll(db, mia.id, date(2026, 3, 2)) == D("7.00")


def test_seite_sagt_modell_erst_nach_dem_abschluss_aendern():
    """Den Rückweg gibt es nur als Hinweis über den Arbeitszeitmodellen (Einstellungen → Zeitregeln und DATEV)."""
    from tests import vorlagen_js as vj
    html = (vj.TEMPLATES / "settings.html").read_text(encoding="utf-8")
    kopf = html[html.index("Arbeitszeitmodelle</h3>"):html.index('id="workModelCards"')]
    assert ("Eine Änderung gilt auch für zurückliegende Tage – ändere Sollzeit und Kalenderwochen erst, wenn die Monate davor abgeschlossen "
            "sind.") in kopf


# --- 1.9.168 Nr. 2: Gleichsetzung auch bei „nur Abwesenheiten“ ---------------------------------------------------------------------------

def test_gleichsetzung_nur_abwesenheiten_verlangt_das_format(welt):
    """„Nur Abwesenheiten“ schreibt etwas von der Person in die Datei (mit L1b U, K …) -- die ERP-Nummer „M-1“ taugt dann so wenig wie bei
    „alles“; speicherbar bleibt sie nur bei „nichts“."""
    db, mia = welt["db"], welt["mia"]
    db.get(TimeBackofficeAdvancedSettings, 1).datev_personnel_equals_erp_number = True
    r = _als(welt).put(f"/api/time-backoffice/payroll-employees/{mia.id}", json={"export_umfang": "abwesenheiten", "eintritt": "2026-11-05"})
    assert r.status_code == 422 and "„M-1“ taugt nicht als DATEV-Personalnummer" in r.json()["detail"], r.text


# --- 1.9.169 Nr. 5: eine Zeile je Art erst beim Speichern --------------------------------------------------------------------------------

def test_zeile_je_art_erst_beim_ersten_speichern(db_session):
    """Nach dem Start (Grunddaten) gibt es unter „art:“ nur Weiterbildung und (seit 1.9.214) Berufsschule; Freizeitausgleich und die übrigen
    Arten zeigt die Liste ohne eigene Zeile („wie die Kategorie“). Erst Speichern legt die Zeile einer Art an."""
    from app.grunddaten import anlegen
    from app.lohnarten import speichern

    def arten():
        return sorted(s for (s,) in db_session.query(LohnartZuordnung.schluessel) if s.startswith("art:"))

    anlegen(db_session)  # ein zweiter Start legt ebenso keine an
    assert arten() == ["art:berufsschule", "art:weiterbildung"]  # seit 1.9.214 mit Berufsschule
    speichern(db_session, "art:sonderurlaub", "S", "8100", False)
    assert arten() == ["art:berufsschule", "art:sonderurlaub", "art:weiterbildung"]
