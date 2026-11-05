"""Version 1.9.213 (L1a Stufe 6, Punkt 2): vergebene Personalnummern aus einer Datei in die Sperrliste einlesen.

    Skript        scripts/personalnummern_einlesen.py DATEI [--probe] -- je Nummer ein Eintrag in personalnummern_vergeben: mit der Person, die
                  sie heute trägt, sonst ohne Person (Spalte employee_id seit Migration 8b4c2f9e1d07 leer erlaubt); mehrfach ausführbar, meldet
                  neu und schon gemerkt; eine Datei im Projektordner lehnt es ab
    Sperre        eine eingelesene Nummer bekommt danach keine Person im ERP (die sie tragende behält sie); freigeben wie jede gemerkte

Alle Nummern hier sind erfunden.
"""

import importlib.util
import os
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from app.models import EmployeePayrollSettings, PersonalnummerVergabe
from app.routers import time_backoffice as time_backoffice_router
from tests.test_v224_field_view import make_employee
from tests.test_v380_nummern_eindeutig import _alembic, _ok

MIGRATION = "8b4c2f9e1d07"
VORHER = "5d2e8a71c4f3"
PG_URL = os.getenv("ERP_TEST_POSTGRES_URL")
ROOT = Path(__file__).resolve().parent.parent


def _skript():
    spec = importlib.util.spec_from_file_location("personalnummern_einlesen", ROOT / "scripts" / "personalnummern_einlesen.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


@pytest.fixture
def welt(threaded_db_session, router_test_client, fester_tag, tmp_path):
    db = threaded_db_session
    mia, tom = make_employee(db, "M-1", "Mia", "Monteurin"), make_employee(db, "M-2", "Tom", "Monteur")
    db.commit()
    return {"db": db, "mia": mia, "tom": tom, "client": router_test_client, "ordner": tmp_path}


def _datei(w, inhalt: str, name="vergeben.txt") -> str:
    pfad = w["ordner"] / name
    pfad.write_bytes(inhalt.encode("utf-8"))
    return str(pfad)


def _lauf(w, *argv):
    zeilen = []
    rc = _skript().main(list(argv), sitzung=w["db"], ausgabe=zeilen.append)
    return rc, zeilen


def _gemerkt(w):
    w["db"].expire_all()
    return sorted((v.nummer, v.employee_id) for v in w["db"].query(PersonalnummerVergabe))


def _put(w, emp, **koerper):
    w["db"].commit()
    return w["client"](w["db"], time_backoffice_router.router, role="buero_finanzen").put(
        f"/api/time-backoffice/payroll-employees/{emp.id}", json=koerper)


def test_einlesen_und_zweiter_lauf(welt):
    """Erster Lauf: drei neu (eine davon trägt Mia heute -- sie wird ihr gemerkt); zweiter Lauf mit einer weiteren: eine neu, drei schon gemerkt."""
    db = welt["db"]
    db.add(EmployeePayrollSettings(employee_id=welt["mia"].id, datev_personnel_number="00123", export_umfang="alles"))
    db.commit()
    rc, zeilen = _lauf(welt, _datei(welt, "00011\n00123\n00204\n"))
    assert rc == 0, zeilen
    assert zeilen == ["Nummern in der Datei: 3", "Neu gemerkt: 3 -- 00123 (Person %d), 00011, 00204" % welt["mia"].id,
                      "  davon einer Person im ERP gemerkt, die sie heute trägt: 1", "Schon gemerkt: 0"]
    assert _gemerkt(welt) == [("00011", None), ("00123", welt["mia"].id), ("00204", None)]
    rc, zeilen = _lauf(welt, _datei(welt, "00011\n00123\n00204\n00205\n"))
    assert rc == 0
    assert zeilen == ["Nummern in der Datei: 4", "Neu gemerkt: 1 -- 00205", "Schon gemerkt: 3 -- 00011, 00123, 00204"]
    assert len(_gemerkt(welt)) == 4


def test_danach_gesperrt_und_die_traegerin_behaelt_ihre(welt):
    db = welt["db"]
    db.add(EmployeePayrollSettings(employee_id=welt["mia"].id, datev_personnel_number="00123", export_umfang="alles"))
    db.commit()
    assert _lauf(welt, _datei(welt, "00011\n00123\n"))[0] == 0
    r = _put(welt, welt["tom"], datev_personnel_number="00011")
    assert (r.status_code, r.json()["detail"]) == (
        422, "Die Personalnummer 00011 ist schon vergeben (eingelesene Liste vergebener Nummern) – eine Personalnummer bleibt dauerhaft gesperrt.")
    r = _put(welt, welt["tom"], datev_personnel_number="00123")
    assert r.status_code == 422 and "Diese DATEV-Personalnummer ist bereits vergeben." == r.json()["detail"]
    assert _put(welt, welt["mia"], datev_personnel_number="00123").status_code == 200
    zeilen = welt["client"](db, time_backoffice_router.router, role="buero_finanzen").get("/api/time-backoffice/payroll-employees").json()
    assert {z["employee_name"]: z["fruehere_personalnummern"] for z in zeilen} == {"Mia Monteurin": [], "Tom Monteur": []}


def test_freigeben_einer_eingelesenen(welt):
    """Der Admin gibt eine eingelesene Nummer frei wie jede gemerkte -- im Änderungsprotokoll „gesperrt, eingelesen ohne Person“."""
    from app.models import AuditLog
    assert _lauf(welt, _datei(welt, "00011\n"))[0] == 0
    client = welt["client"](welt["db"], time_backoffice_router.router, role="admin")
    r = client.post("/api/time-backoffice/personalnummern/freigeben", json={"nummer": "00011"})
    assert r.status_code == 200, r.text
    assert _gemerkt(welt) == []
    eintrag = welt["db"].query(AuditLog).filter_by(entity_type="Personalnummer", entity_id="00011").one()
    assert (eintrag.old_value, eintrag.new_value) == ("gesperrt, eingelesen ohne Person", "frei")


def test_probe_schreibt_nichts(welt):
    rc, zeilen = _lauf(welt, _datei(welt, "00011\n00012\n"), "--probe")
    assert rc == 0
    assert zeilen[:2] == ["Probe, nichts geschrieben -- Nummern in der Datei: 2", "Würde neu gemerkt: 2 -- 00011, 00012"]
    assert _gemerkt(welt) == []


def test_aufbau_der_datei(welt):
    """Überschrift und Kommentar übersprungen (nur die Zeilennummer, nie der Inhalt), CSV: das erste Feld, „101“ aufgefüllt, doppelt einmal."""
    inhalt = "Personalnummer;Name\n# Liste vom Lohnbüro\n\n00011;Erika Beispiel\n101;Max Muster\n﻿00011\n\"00204\",x\n"
    rc, zeilen = _lauf(welt, _datei(welt, inhalt))
    assert rc == 0
    assert zeilen[0] == "Übersprungen (erstes Feld keine Zahl), Zeile: 1"
    assert zeilen[1] == "Nummern in der Datei: 3 (davon auf 5 Ziffern aufgefüllt: 1)"
    assert "Erika" not in "\n".join(zeilen) and "Max" not in "\n".join(zeilen)
    assert [n for n, _ in _gemerkt(welt)] == ["00011", "00101", "00204"]


def test_mehr_als_fuenf_ziffern_nichts_gemerkt(welt):
    rc, zeilen = _lauf(welt, _datei(welt, "00011\n123456\n00012\n"))
    assert (rc, zeilen) == (1, ["Mehr als 5 Ziffern, Zeile: 2 -- nichts gemerkt. Eine Personalnummer hat genau 5 Ziffern."])
    assert _gemerkt(welt) == []


def test_datei_im_projektordner_abgelehnt(welt):
    """Die Datei gehört nicht ins Repository -- abgelehnt, bevor sie gelesen wird (die Datei muss dafür nicht existieren)."""
    rc, zeilen = _lauf(welt, str(ROOT / "tests" / "vergeben_gibt_es_nicht.txt"))
    assert rc == 2 and zeilen[0].startswith("Die Datei liegt im Projektordner")
    assert not (ROOT / "tests" / "vergeben_gibt_es_nicht.txt").exists()


def test_ohne_database_url_und_ohne_datei(tmp_path):
    zeilen = []
    assert _skript().main([str(tmp_path / "x.txt")], umgebung={}, ausgabe=zeilen.append) == 2
    assert zeilen[0].startswith("DATABASE_URL ist nicht gesetzt")


def test_pruefskript_zaehlt_die_eingelesenen(welt):
    from datetime import date
    from tests.test_v590_pruefe_zeitregeln import _skript as pruefskript
    db = welt["db"]
    assert _lauf(welt, _datei(welt, "00011\n00012\n"))[0] == 0
    db.add(EmployeePayrollSettings(employee_id=welt["tom"].id, datev_personnel_number="00012", export_umfang="alles"))  # an der Sperre vorbei
    db.commit()
    zeilen = []
    assert pruefskript().main([], sitzung=db, ausgabe=zeilen.append, heute=date(2026, 11, 10)) == 1
    assert "    davon eingelesen ohne Person: 2" in zeilen
    assert f"  ! Personalnummer 00012 steht in der eingelesenen Liste (ohne Person), heute trägt sie Person {welt['tom'].id}." in zeilen


def test_keine_echten_nummern_im_repository():
    """Keine Datei mit Personalnummern im Projektordner: außer Code und Tests keine .txt/.csv mit einer Zeile aus genau 5 Ziffern."""
    import re
    import subprocess
    dateien = subprocess.run(["git", "ls-files", "*.txt", "*.csv"], cwd=ROOT, capture_output=True, text=True).stdout.split()
    treffer = [d for d in dateien if any(re.fullmatch(r"\s*\d{5}\s*(;.*)?", z) for z in (ROOT / d).read_text(encoding="utf-8", errors="replace").splitlines())]
    assert treffer == []


# --- Migration 8b4c2f9e1d07 -----------------------------------------------------------------------------------------------------------------

def _probe(url: str, engine) -> None:
    _ok(_alembic(url, "upgrade", VORHER))
    with engine.begin() as c:
        c.execute(text("INSERT INTO employees (employee_number, first_name, last_name, employee_group, weekly_hours, active, created_at, updated_at) "
                       "VALUES ('E-1', 'P', 'Test', 'gewerblich', 40, :a, '2026-09-01', '2026-09-01')"), {"a": True})
        c.execute(text("INSERT INTO personalnummern_vergeben (nummer, employee_id, vergeben_am) VALUES "
                       "('00123', (SELECT id FROM employees WHERE employee_number = 'E-1'), '2026-11-01')"))
    _ok(_alembic(url, "upgrade", MIGRATION))
    with engine.begin() as c:
        c.execute(text("INSERT INTO personalnummern_vergeben (nummer, employee_id, vergeben_am) VALUES ('00011', NULL, '2026-11-05')"))
        with pytest.raises(Exception):  # die Nummer bleibt eindeutig
            with c.begin_nested():
                c.execute(text("INSERT INTO personalnummern_vergeben (nummer, employee_id, vergeben_am) VALUES ('00011', NULL, '2026-11-05')"))
    _ok(_alembic(url, "downgrade", VORHER))
    with engine.connect() as c:
        assert [tuple(z) for z in c.execute(text("SELECT nummer FROM personalnummern_vergeben ORDER BY nummer"))] == [("00123",)]
    _ok(_alembic(url, "upgrade", "head"))


def test_migration_auf_einem_bestand_sqlite(tmp_path):
    url = f"sqlite:///{(tmp_path / 'ohne_person.db').as_posix()}"
    engine = create_engine(url)
    try:
        _probe(url, engine)
    finally:
        engine.dispose()


def test_migration_auf_einem_bestand_postgresql():
    if not PG_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    schema = f"pgtest_mig_pnr_ohne_{uuid.uuid4().hex[:8]}"
    admin = create_engine(PG_URL)
    with admin.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
    url = f"{PG_URL}{'&' if '?' in PG_URL else '?'}options=-csearch_path={schema}"  # ohne Prozentkodierung (configparser)
    engine = create_engine(PG_URL, connect_args={"options": f"-csearch_path={schema}", "application_name": schema})
    try:
        _probe(url, engine)
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE application_name = :n"), {"n": schema})
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin.dispose()
