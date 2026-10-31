"""Version 1.9.154 (Stufe 6, R1 Nachrunde, Punkt 5): „Zeiten -> Abwesenheiten“.

    Migration  ein Antrag aus der Migration heißt nie „beantragt am“: „eingetragen am <Tag der Abwesenheit>“, sonst nichts; sein Datum ist nie das der Migration
    Vermerk    vom Programm geschrieben „Vermerk:“, „Freigabe:“ nur bei einer Notiz des Admins zur Entscheidung; beim Löschen bleibt die Herkunft
    Datum      ein Tag „Mi 21.10.2026“, mehrere „Mo 19.10.–Mi 21.10.2026“, alleinstehende Daten mit Jahr
"""

import importlib.util
import json
import re
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select

from app.absence_requests import ABWESENHEIT_GELOESCHT, MIGRATION_VERMERK, abwesenheit_loeschen, create_request, request_to_dict, review_request
from app.models import Employee, EmployeeAbsence, EmployeeAbsenceRequest
from app.routers.absence_requests import router as antraege_router
from tests.node_lauf import node_lauf
from tests.test_v133_invoices import db_session
from tests.vorlagen_js import TEMPLATES

ROOT = Path(__file__).resolve().parent.parent
TAG = date(2026, 10, 21)


def _person(db):
    emp = Employee(employee_number="M-1", first_name="Mia", last_name="Test", employee_group="gewerblich", weekly_hours=Decimal("40"), active=True)
    db.add(emp)
    db.commit()
    return emp


def _migration():
    pfad = next((ROOT / "alembic" / "versions").glob("*_abwesenheiten_als_antraege.py"))
    spec = importlib.util.spec_from_file_location("migration_abwesenheiten", pfad)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def _aus_migration(db, angelegt=datetime(2026, 9, 2, 8, 0)):
    db.add(EmployeeAbsence(employee_id=_person(db).id, absence_type="Urlaub", absence_category="urlaub", start_date=TAG, end_date=TAG, created_at=angelegt, updated_at=angelegt))
    db.commit()
    _migration().uebernehmen(db.connection())
    db.commit()
    return db.scalar(select(EmployeeAbsenceRequest))


def _antrag(db):
    return create_request(db, employee_id=_person(db).id, absence_type="Urlaub", absence_category="urlaub", start_date=TAG, end_date=TAG)


# --- Migration -------------------------------------------------------------------------------------------------------------------

def test_antrag_aus_der_migration_traegt_den_tag_der_abwesenheit():
    """Nicht den Tag der Migration: die Abwesenheit wurde am 02.09. eingetragen, gelaufen ist die Migration später."""
    db = db_session()
    antrag = _aus_migration(db)
    daten = request_to_dict(db, antrag)
    assert daten["aus_migration"] is True
    assert daten["created_at"] == datetime(2026, 9, 2, 8, 0)
    assert daten["vom_programm"] is True


def test_vermerk_der_migration_stimmt():
    assert _migration().MERKER == MIGRATION_VERMERK


def test_geloeschte_abwesenheit_aus_der_migration_bleibt_erkennbar():
    db = db_session()
    antrag = _aus_migration(db)
    abwesenheit_loeschen(db, antrag.approved_absence_id)
    db.refresh(antrag)
    daten = request_to_dict(db, antrag)
    assert daten["status"] == "cancelled"
    assert daten["aus_migration"] is True and daten["vom_programm"] is True
    assert daten["review_notes"] == f"{MIGRATION_VERMERK}. {ABWESENHEIT_GELOESCHT}"


def test_rueckweg_der_migration_laesst_den_geloeschten_stehen():
    """downgrade() nimmt nur, was niemand angefasst hat -- der Antrag einer gelöschten Abwesenheit bleibt, wie er ist."""
    db = db_session()
    antrag = _aus_migration(db)
    abwesenheit_loeschen(db, antrag.approved_absence_id)
    _migration().zuruecknehmen(db.connection())
    db.commit()
    assert db.scalar(select(EmployeeAbsenceRequest.id)) == antrag.id


# --- Vermerk ---------------------------------------------------------------------------------------------------------------------

def test_normaler_antrag_ohne_notiz():
    db = db_session()
    daten = request_to_dict(db, _antrag(db))
    assert daten["aus_migration"] is False and daten["vom_programm"] is False


def test_notiz_des_admins_ist_freigabe():
    db = db_session()
    antrag = review_request(db, _antrag(db).id, decision="approved", reviewed_by_user_id=None, review_notes="Vertretung geklärt")
    daten = request_to_dict(db, antrag)
    assert (daten["vom_programm"], daten["review_notes"]) == (False, "Vertretung geklärt")


def test_geloeschte_abwesenheit_ist_vermerk():
    db = db_session()
    antrag = review_request(db, _antrag(db).id, decision="approved", reviewed_by_user_id=None)
    abwesenheit_loeschen(db, antrag.approved_absence_id)
    db.refresh(antrag)
    daten = request_to_dict(db, antrag)
    assert (daten["vom_programm"], daten["review_notes"], daten["aus_migration"]) == (True, ABWESENHEIT_GELOESCHT, False)


def test_die_felder_kommen_auch_ueber_die_liste_der_antraege(threaded_db_session, router_test_client):
    """„Meine Zeiten“ liest GET /api/absence-requests (Schema mit Positivliste)."""
    db = threaded_db_session
    emp = _person(db)
    create_request(db, employee_id=emp.id, absence_type="Urlaub", absence_category="urlaub", start_date=TAG, end_date=TAG)
    daten = router_test_client(db, antraege_router).get("/api/absence-requests").json()
    assert daten[0]["vom_programm"] is False and daten[0]["aus_migration"] is False


@pytest.mark.parametrize("seite", ["zeiten.html", "mobil_zeiten.html"])
def test_seiten_unterscheiden_vermerk_und_freigabe(seite):
    text = (TEMPLATES / seite).read_text(encoding="utf-8")
    assert "vom_programm?'Vermerk: ':'Freigabe: ')" in text
    assert "Freigabe: '+esc(" not in text


# --- Datum ------------------------------------------------------------------------------------------------------------------------

def _baustein():
    text = (TEMPLATES / "_abwesenheit.html").read_text(encoding="utf-8")
    return text.split("<script>", 1)[1].rsplit("</script>", 1)[0]


@pytest.mark.parametrize("von, bis, text", [
    ("2026-10-21", "2026-10-21", "Mi 21.10.2026"),
    ("2026-10-19", "2026-10-21", "Mo 19.10.–Mi 21.10.2026"),
    ("2026-12-28", "2027-01-04", "Mo 28.12.2026–Mo 04.01.2027"),
    ("2026-10-21T00:00:00", "2026-10-21T00:00:00", "Mi 21.10.2026"),
])
def test_zeitraum(von, bis, text):
    assert node_lauf(_baustein() + f"\nconsole.log(abwZeitraum({json.dumps(von)},{json.dumps(bis)}));", tz="America/New_York").stdout.strip() == text


def _beantragt():
    text = (TEMPLATES / "zeiten.html").read_text(encoding="utf-8")
    funktion = re.search(r"function beantragtText\(a\)\{.*?\n\}\n", text, re.S).group(0)
    datum = (TEMPLATES / "_berlin_date.html").read_text(encoding="utf-8")
    return datum.split("<script>", 1)[1].rsplit("</script>", 1)[0] + "\n" + funktion


@pytest.mark.parametrize("a, text", [
    ({"aus_migration": True, "created_at": "2026-09-02T08:00:00"}, " · eingetragen am 02.09.2026"),
    ({"aus_migration": True, "created_at": None}, ""),
    ({"aus_migration": False, "created_at": "2026-10-20T08:00:00"}, " · beantragt am 20.10.2026"),
    ({"aus_migration": False, "created_at": "2026-10-20T08:00:00", "beantragt_von": "Finn"}, " · beantragt von Finn am 20.10.2026"),
    ({"aus_migration": False, "created_at": "2026-12-31T23:30:00"}, " · beantragt am 01.01.2027"),  # gespeichert in UTC, angezeigt in Berlin
])
def test_beantragt_text(a, text):
    assert json.loads(node_lauf(_beantragt() + f"\nconsole.log(JSON.stringify(beantragtText({json.dumps(a)})));").stdout.strip()) == text
