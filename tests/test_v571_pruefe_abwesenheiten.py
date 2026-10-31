"""Version 1.9.153 (Stufe 6, R1 Nachrunde, Punkt 4): scripts/pruefe_abwesenheiten.py -- passen Kategorie und Art im Bestand zusammen?

    Zählen       Anzahl je Kategorie × Art, getrennt nach Abwesenheiten und Anträgen; Anträge aus der Migration, auch wenn die Abwesenheit inzwischen gelöscht ist
    Widersprüche Abwesenheiten und offene Anträge, mit ID und Zeitraum; Rückgabe 1. Sonst Rückgabe 0
    Datenschutz  kein Name, keine Notiz in der Ausgabe
    nur lesen    die eigene Sitzung schreibt nicht; ohne DATABASE_URL Rückgabe 2
"""

import importlib.util
import os
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Employee, EmployeeAbsence, EmployeeAbsenceRequest
from tests.befund_vor_echtbetrieb import pg_sitzung
from tests.pg_schutz import pg_url_pruefen
from tests.test_v133_invoices import db_session

ROOT = Path(__file__).resolve().parent.parent
NAME = "Geheimnachname"
NOTIZ = "Attest vom Hausarzt"


def _skript():
    spec = importlib.util.spec_from_file_location("pruefe_abwesenheiten", ROOT / "scripts" / "pruefe_abwesenheiten.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def _lauf(db):
    zeilen = []
    rc = _skript().main([], sitzung=db, ausgabe=zeilen.append)
    return rc, zeilen


def _person(db):
    emp = Employee(employee_number="M-1", first_name="Mia", last_name=NAME, employee_group="gewerblich", weekly_hours=Decimal("40"), active=True)
    db.add(emp)
    db.commit()
    return emp


def _abwesenheit(db, emp, kategorie, art, von=date(2026, 3, 2), bis=date(2026, 3, 4)):
    row = EmployeeAbsence(employee_id=emp.id, absence_category=kategorie, absence_type=art, start_date=von, end_date=bis, notes=NOTIZ)
    db.add(row)
    db.commit()
    return row


def _antrag(db, emp, kategorie, art, status="pending", vermerk=None, von=date(2026, 3, 2), bis=date(2026, 3, 4)):
    row = EmployeeAbsenceRequest(employee_id=emp.id, absence_category=kategorie, absence_type=art, start_date=von, end_date=bis, status=status, review_notes=vermerk, notes=NOTIZ)
    db.add(row)
    db.commit()
    return row


def test_leerer_bestand_rueckgabe_0():
    db = db_session()
    assert _lauf(db) == (0, ["Abwesenheiten: 0", "Anträge: 0", "Anträge aus der Migration (vor 1.9.146 auf der Plantafel eingetragen): 0", "Keine Widersprüche."])


def test_zaehlt_je_kategorie_und_art_ohne_widerspruch_rueckgabe_0():
    db = db_session()
    emp = _person(db)
    _abwesenheit(db, emp, "krankheit", "Krankheit")
    _abwesenheit(db, emp, "krankheit", "Krankheit")
    _abwesenheit(db, emp, "fortbildung", "Berufsschule")
    _antrag(db, emp, "urlaub", "Urlaub")
    rc, zeilen = _lauf(db)
    assert rc == 0
    assert zeilen == ["Abwesenheiten: 3", "  Fortbildung × Berufsschule: 1", "  Krankheit × Krankheit: 2", "Anträge: 1", "  Urlaub × Urlaub: 1",
                      "Anträge aus der Migration (vor 1.9.146 auf der Plantafel eingetragen): 0", "Keine Widersprüche."]


def test_widersprueche_mit_id_und_zeitraum_rueckgabe_1():
    db = db_session()
    emp = _person(db)
    abw = _abwesenheit(db, emp, "krankheit", "Urlaub")
    antrag = _antrag(db, emp, "urlaub", "Krankheit", von=date(2026, 4, 1), bis=date(2026, 4, 1))
    rc, zeilen = _lauf(db)
    assert rc == 1
    assert f"  Abwesenheit {abw.id}: 02.03.2026–04.03.2026, Kategorie Krankheit, Art Urlaub" in zeilen
    assert f"  Offener Antrag {antrag.id}: 01.04.2026–01.04.2026, Kategorie Urlaub, Art Krankheit" in zeilen
    assert "Widersprüche: 2" in zeilen


@pytest.mark.parametrize("status", ["approved", "rejected", "cancelled"])
def test_erledigter_antrag_ist_kein_widerspruch_wird_aber_gezaehlt(status):
    db = db_session()
    _antrag(db, _person(db), "krankheit", "Urlaub", status=status)
    rc, zeilen = _lauf(db)
    assert rc == 0
    assert "  Krankheit × Urlaub: 1" in zeilen


def test_altbestand_ohne_kategorie_und_eigene_art_sind_kein_widerspruch():
    db = db_session()
    emp = _person(db)
    _abwesenheit(db, emp, "unbekannt", "Urlaub")
    _abwesenheit(db, emp, "krankheit", "Kur")
    _abwesenheit(db, emp, "krankheit", "Sonstiges")
    rc, zeilen = _lauf(db)
    assert rc == 0
    assert "  Unbekannt (Altbestand) × Urlaub: 1" in zeilen


def test_anzahl_der_antraege_aus_der_migration_auch_nach_dem_loeschen():
    """Der Vermerk der Migration bleibt am Anfang stehen, wenn die Abwesenheit gelöscht wird (1.9.154); ein Antrag des Admins mit eigener Notiz zählt nicht."""
    from app.absence_requests import MIGRATION_VERMERK

    db = db_session()
    emp = _person(db)
    _antrag(db, emp, "urlaub", "Urlaub", status="approved", vermerk=MIGRATION_VERMERK)
    _antrag(db, emp, "urlaub", "Urlaub", status="cancelled", vermerk=MIGRATION_VERMERK + ". Die genehmigte Abwesenheit wurde gelöscht.")
    _antrag(db, emp, "urlaub", "Urlaub", status="approved", vermerk="Bitte Vertretung klären")
    _, zeilen = _lauf(db)
    assert "Anträge aus der Migration (vor 1.9.146 auf der Plantafel eingetragen): 2" in zeilen


def test_vermerk_stimmt_mit_der_migration_ueberein():
    from app.absence_requests import MIGRATION_VERMERK

    pfad = next((ROOT / "alembic" / "versions").glob("*_abwesenheiten_als_antraege.py"))
    assert f'MERKER = "{MIGRATION_VERMERK}"' in pfad.read_text(encoding="utf-8")


def test_kein_name_und_keine_notiz_in_der_ausgabe():
    db = db_session()
    emp = _person(db)
    _abwesenheit(db, emp, "krankheit", "Urlaub")
    _antrag(db, emp, "urlaub", "Krankheit")
    _, zeilen = _lauf(db)
    ausgabe = "\n".join(zeilen)
    assert NAME not in ausgabe and "Mia" not in ausgabe and NOTIZ not in ausgabe


def test_ohne_database_url_rueckgabe_2():
    zeilen = []
    assert _skript().main([], umgebung={}, ausgabe=zeilen.append) == 2
    assert zeilen == ["DATABASE_URL ist nicht gesetzt -- auf dem Server zuerst: set -a; source .env; set +a"]


def test_aufruf_steht_im_kopf_der_datei():
    kopf = _skript().__doc__
    assert ".venv/bin/python scripts/pruefe_abwesenheiten.py" in kopf and "Rückgabe: 0 keine Widersprüche, 1 Widersprüche, 2 Umgebung fehlt" in kopf


def test_die_eigene_sitzung_schreibt_nicht(tmp_path):
    url = pg_url_pruefen(f"sqlite:///{(tmp_path / 'bestand.db').as_posix()}")  # Regel 27: wer DATABASE_URL weitergibt, prüft sie
    engine = create_engine(url)
    try:
        Base.metadata.create_all(engine)
        db = sessionmaker(bind=engine)()
        _abwesenheit(db, _person(db), "krankheit", "Urlaub")
        db.close()
        zeilen = []
        assert _skript().main([], umgebung={"DATABASE_URL": url}, ausgabe=zeilen.append) == 1
        sitzung = _skript().nur_lesende_sitzung(url)
        try:
            with pytest.raises(DBAPIError):
                sitzung.execute(text("UPDATE employee_absences SET absence_type = 'x'"))
                sitzung.commit()
            sitzung.rollback()
        finally:
            bind = sitzung.get_bind()
            sitzung.close()
            bind.dispose()
    finally:
        engine.dispose()

@pytest.fixture
def pg():
    with pg_sitzung("pruefe_abw") as db:
        yield db


def test_unter_postgresql_lesen_und_nicht_schreiben(pg):
    """Regel 27: im Wegwerf-Schema, über die eigene Sitzung des Skripts wie auf dem Server."""
    _abwesenheit(pg, _person(pg), "krankheit", "Urlaub")
    schema = pg.scalar(text("SELECT current_schema()"))
    url = pg_url_pruefen(f"{os.environ['ERP_TEST_POSTGRES_URL']}?options=-csearch_path={schema}")
    zeilen = []
    assert _skript().main([], umgebung={"DATABASE_URL": url}, ausgabe=zeilen.append) == 1
    assert any("Kategorie Krankheit, Art Urlaub" in z for z in zeilen)
    sitzung = _skript().nur_lesende_sitzung(url)
    try:
        with pytest.raises(DBAPIError):
            sitzung.execute(text("UPDATE employee_absences SET absence_type = 'x'"))
        sitzung.rollback()
    finally:
        bind = sitzung.get_bind()
        sitzung.close()
        bind.dispose()
