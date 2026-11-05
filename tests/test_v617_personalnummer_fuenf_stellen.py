"""Version 1.9.212 (L1a Stufe 6, Punkt 1, Antwort des Lohnbüros): eine DATEV-Personalnummer hat genau 5 Ziffern, führende Nullen gehören dazu.

    Format        genau 5 Ziffern (00001, 00101, 00204) -- sonst 422; kein Auffüllen beim Speichern (1.9.168–1.9.211: 1 bis 5 Ziffern ohne
                  führende Null)
    Kreise        00000–00099 sv-pflichtig Beschäftigte, 00100–00199 Minijobber, ab 00200 Azubis -- ein Hinweis in der Antwort aufs Speichern,
                  keine Sperre (gespeichert wird jede gültige Nummer, gleich welche Funktion die Person hat)
    Migration     5d2e8a71c4f3 füllt Nummern aus 1 bis 4 Ziffern links mit Nullen auf -- Lohnstammdaten und gemerkte Nummern, nicht die
                  ERP-Mitarbeiternummer; bricht ab, wenn danach zwei Zeilen dieselbe Nummer trügen; downgrade() nimmt die Nullen wieder weg
"""

import os
import uuid

import pytest
from sqlalchemy import create_engine, text

from app.models import EmployeePayrollSettings, TimeBackofficeAdvancedSettings
from app.routers import time_backoffice as time_backoffice_router
from app.time_backoffice import nummernkreis
from tests.test_v224_field_view import make_employee
from tests.test_v380_nummern_eindeutig import _alembic, _ok

MIGRATION = "5d2e8a71c4f3"
VORHER = "1e425fe7faa6"
PG_URL = os.getenv("ERP_TEST_POSTGRES_URL")
FALSCH = "Die DATEV-Personalnummer hat genau 5 Ziffern, führende Nullen gehören dazu (z. B. 00101)."


@pytest.fixture
def welt(threaded_db_session, router_test_client, fester_tag):
    db = threaded_db_session
    mia, tom = make_employee(db, "M-1", "Mia", "Monteurin"), make_employee(db, "M-2", "Tom", "Monteur")
    db.commit()
    return {"db": db, "mia": mia, "tom": tom, "client": router_test_client}


def _put(w, emp, **koerper):
    w["db"].commit()
    return w["client"](w["db"], time_backoffice_router.router, role="buero_finanzen").put(
        f"/api/time-backoffice/payroll-employees/{emp.id}", json=koerper)


@pytest.mark.parametrize("nummer", ["1", "101", "9005", "000001", "0010", "00 101", "0010A"])
def test_nicht_fuenf_ziffern_abgelehnt(welt, nummer):
    """Auch „101“ wird nicht aufgefüllt: die Meldung, nichts gespeichert."""
    r = _put(welt, welt["mia"], datev_personnel_number=nummer)
    assert (r.status_code, r.json()["detail"]) == (422, FALSCH), r.text
    assert welt["db"].query(EmployeePayrollSettings).filter_by(employee_id=welt["mia"].id).count() == 0


@pytest.mark.parametrize("nummer, kreis", [
    ("00000", "sv-pflichtig Beschäftigte (00000–00099)"), ("00099", "sv-pflichtig Beschäftigte (00000–00099)"),
    ("00100", "Minijobber (00100–00199)"), ("00199", "Minijobber (00100–00199)"),
    ("00200", "Azubis (ab 00200)"), ("00204", "Azubis (ab 00200)"), ("00299", "Azubis (ab 00200)"),  # seit 1.9.219 bis 00299 (bis 1.9.218 auch 91001)
])
def test_fuenf_ziffern_mit_hinweis_zum_kreis(welt, nummer, kreis):
    r = _put(welt, welt["mia"], datev_personnel_number=nummer)
    assert r.status_code == 200, r.text
    assert (r.json()["datev_personnel_number"], r.json()["nummernkreis"]) == (nummer, f"Die Personalnummer {nummer} liegt im Kreis {kreis}.")


def test_kreis_ist_keine_sperre(welt):
    """Mia ist Monteurin (keine Azubi, kein Minijob) -- 00150 und 00250 werden trotzdem gespeichert, der Hinweis nennt nur den Kreis."""
    for nummer in ("00150", "00250", "00010"):
        r = _put(welt, welt["mia"], datev_personnel_number=nummer)
        assert (r.status_code, r.json()["datev_personnel_number"]) == (200, nummer)
    welt["db"].expire_all()
    assert welt["db"].query(EmployeePayrollSettings).filter_by(employee_id=welt["mia"].id).one().datev_personnel_number == "00010"


def test_ohne_nummer_kein_hinweis(welt):
    r = _put(welt, welt["mia"], export_umfang="nichts", datev_personnel_number=None)
    assert (r.status_code, r.json()["nummernkreis"]) == (200, None)
    assert nummernkreis("101") is None and nummernkreis(None) is None


def test_gleichsetzung_braucht_fuenf_ziffern(welt):
    """„DATEV-Nr. = ERP-Nr.“: die ERP-Nummer „M-1“ bzw. „101“ taugt nicht (mit Export), „00101“ geht und bekommt den Hinweis."""
    db, mia = welt["db"], welt["mia"]
    db.get(TimeBackofficeAdvancedSettings, 1).datev_personnel_equals_erp_number = True
    mia.employee_number = "101"
    r = _put(welt, mia, export_umfang="alles")
    assert (r.status_code, r.json()["detail"]) == (
        422, "Die ERP-Mitarbeiternummer „101“ taugt nicht als DATEV-Personalnummer: genau 5 Ziffern, führende Nullen gehören dazu.")
    mia.employee_number = "00101"
    r = _put(welt, mia, export_umfang="alles")
    assert (r.status_code, r.json()["nummernkreis"]) == (200, "Die Personalnummer 00101 liegt im Kreis Minijobber (00100–00199).")


def test_pruefskript_format_und_kreise():
    from tests.test_v590_pruefe_zeitregeln import _lauf, _person, db_session
    db = db_session()
    a = _person(db, "E-1", datev="00042")
    _person(db, "E-2", datev="00150")
    _person(db, "E-3", datev="00204")
    kurz = _person(db, "E-4", datev="9005")
    rc, zeilen = _lauf(db)
    assert rc == 1
    assert [z for z in zeilen if z.startswith("  ! ")] == [f"  ! Person {kurz.id}: Personalnummer „9005“ hat nicht genau 5 Ziffern."]
    assert "  Personalnummern je Kreis: sv-pflichtig Beschäftigte 1, Minijobber 1, Azubis 1, außerhalb 0" in zeilen  # seit 1.9.219 mit „außerhalb“
    assert not any(f"Person {a.id}:" in z for z in zeilen)


# --- Migration 5d2e8a71c4f3 -----------------------------------------------------------------------------------------------------------------

def _bestand(engine, payroll: list[tuple[str, str | None]], gemerkt: list[tuple[str, str]], gleich: bool = True) -> None:
    """Personen mit ERP-Nummer und DATEV-Nummer, gemerkte Nummern (Nummer, ERP-Nummer der Person) -- auf dem Stand VORHER."""
    with engine.begin() as c:
        for erp, datev in payroll:
            c.execute(text("INSERT INTO employees (employee_number, first_name, last_name, employee_group, weekly_hours, active, created_at, "
                           "updated_at) VALUES (:e, 'P', 'Test', 'gewerblich', 40, :a, '2026-09-01', '2026-09-01')"), {"e": erp, "a": True})
            c.execute(text("INSERT INTO employee_payroll_settings (employee_id, datev_personnel_number, payroll_export_enabled, export_umfang, updated_at) "
                           "VALUES ((SELECT id FROM employees WHERE employee_number = :e), :d, :a, 'alles', '2026-09-01')"), {"e": erp, "d": datev, "a": True})
        for nummer, erp in gemerkt:
            c.execute(text("INSERT INTO personalnummern_vergeben (nummer, employee_id, vergeben_am) VALUES "
                           "(:n, (SELECT id FROM employees WHERE employee_number = :e), '2026-11-01')"), {"n": nummer, "e": erp})
        c.execute(text("INSERT INTO time_backoffice_advanced_settings (id, datev_personnel_equals_erp_number, updated_at) VALUES (1, :g, '2026-09-01')"),
                  {"g": gleich})


def _stand(engine) -> tuple[list, list, list]:
    with engine.connect() as c:
        return ([tuple(z) for z in c.execute(text("SELECT e.employee_number, p.datev_personnel_number FROM employee_payroll_settings p "
                                                  "JOIN employees e ON e.id = p.employee_id ORDER BY e.employee_number"))],
                [z[0] for z in c.execute(text("SELECT nummer FROM personalnummern_vergeben ORDER BY id"))],
                [z[0] for z in c.execute(text("SELECT employee_number FROM employees ORDER BY id"))])


def _probe(url: str, engine) -> None:
    _ok(_alembic(url, "upgrade", VORHER))
    _bestand(engine, [("12", "9005"), ("E-2", "91001"), ("E-3", "M-17"), ("E-4", "101"), ("E-5", None), ("E-6", "123456")],
             [("9005", "12"), ("91001", "E-2"), ("101", "E-4"), ("77", "E-4"), ("12", "12"), ("M-1", "E-2")])
    vorher = _stand(engine)
    _ok(_alembic(url, "upgrade", MIGRATION))
    assert _stand(engine) == (
        [("12", "09005"), ("E-2", "91001"), ("E-3", "M-17"), ("E-4", "00101"), ("E-5", None), ("E-6", "123456")],
        ["09005", "91001", "00101", "00077", "00012", "M-1"],
        ["12", "E-2", "E-3", "E-4", "E-5", "E-6"])  # die ERP-Nummer „12“ bleibt, auch bei Gleichsetzung (Festlegung 1.9.212 Nr. 4)
    with engine.begin() as c:  # nach dem Einspielen neu eingetragen: 00001 -- downgrade() nimmt auch hier die Nullen weg
        c.execute(text("UPDATE employee_payroll_settings SET datev_personnel_number = '00001' WHERE datev_personnel_number IS NULL"))
    _ok(_alembic(url, "downgrade", VORHER))
    zurueck = _stand(engine)
    assert zurueck[0] == [(erp, "1" if erp == "E-5" else datev) for erp, datev in vorher[0]]
    assert zurueck[1:] == vorher[1:]
    _ok(_alembic(url, "upgrade", "head"))


def _abbruch(url: str, engine) -> None:
    """„101“ und „0101“ trügen nach dem Auffüllen beide 00101 -- Abbruch mit Liste, nichts geändert."""
    _ok(_alembic(url, "upgrade", VORHER))
    _bestand(engine, [("E-1", "101"), ("E-2", "0101"), ("E-3", "9005")], [], gleich=False)
    vorher = _stand(engine)
    r = _alembic(url, "upgrade", MIGRATION)
    assert r.returncode != 0
    assert "employee_payroll_settings: 101, 0101 -> 00101" in r.stdout + r.stderr
    assert _stand(engine) == vorher


def _sqlite(tmp_path, name, ablauf):
    url = f"sqlite:///{(tmp_path / name).as_posix()}"
    engine = create_engine(url)
    try:
        ablauf(url, engine)
    finally:
        engine.dispose()


def _postgresql(ablauf):
    if not PG_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    schema = f"pgtest_mig_pnr5_{uuid.uuid4().hex[:8]}"
    admin = create_engine(PG_URL)
    with admin.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
    url = f"{PG_URL}{'&' if '?' in PG_URL else '?'}options=-csearch_path={schema}"  # ohne Prozentkodierung (configparser)
    engine = create_engine(PG_URL, connect_args={"options": f"-csearch_path={schema}", "application_name": schema})
    try:
        ablauf(url, engine)
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE application_name = :n"), {"n": schema})
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin.dispose()


def test_migration_auf_einem_bestand_sqlite(tmp_path):
    _sqlite(tmp_path, "pnr5.db", _probe)


def test_migration_bricht_bei_einer_kollision_ab_sqlite(tmp_path):
    _sqlite(tmp_path, "pnr5_abbruch.db", _abbruch)


def test_migration_auf_einem_bestand_postgresql():
    _postgresql(_probe)


def test_migration_bricht_bei_einer_kollision_ab_postgresql():
    _postgresql(_abbruch)


def test_aufgefuellt_und_zurueck():
    """Die Umrechnung der Migration für sich: nur 1 bis 4 Ziffern, zurück nur 5 Ziffern mit führender Null (außer 00000)."""
    import importlib.util
    from pathlib import Path
    datei = next((Path(__file__).resolve().parent.parent / "alembic" / "versions").glob("*_personalnummer_fuenf_stellen.py"))
    spec = importlib.util.spec_from_file_location("mig_pnr5", datei)
    mig = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mig)
    assert [mig.aufgefuellt(n) for n in ("1", "9005", "0101", "91001", "123456", "M-17", " 101", None)] == \
        ["00001", "09005", "00101", None, None, None, None, None]
    assert [mig.ohne_nullen(n) for n in ("00001", "09005", "91001", "00000", "0101", None)] == ["1", "9005", None, None, None, None]
