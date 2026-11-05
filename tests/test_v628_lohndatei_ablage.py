"""Version 1.9.226 (Lohn L1b, Punkt 3): jede erzeugte Lohndatei bleibt auf dem Server.

    erzeugen     POST /api/time-backoffice/lohndateien {monat} -- dieselben Prüfungen wie der Export (abgeschlossen, vollständig, ganzer Monat),
                 legt die Bytes mit SHA-256, Zeitpunkt und Konto ab (Tabelle lohndateien, Migration d5a8e3c71b42); jede erzeugte Datei, auch eine
                 zweite für denselben Monat. Der GET-Export entfällt (kein GET schreibt, Regel 23).
    lesen        GET …/lohndateien?monat=JJJJ-MM (ohne die Bytes), GET …/lohndateien/{id}/datei (genau die abgelegten Bytes, nur mit stimmender
                 Prüfsumme, sonst 409; Download über datei_antwort(), Regel 31)
    Rechte       nur Admin und Büro – Finanzen (require_lohndaten)
    unveränderlich   kein Ändern, kein Löschen (ORM-Sperre)
    Personalnummer   eine Nummer, die in einer abgelegten Datei steht, lässt sich nicht freigeben (Notiz zu 1.9.181); die Listen zeigen statt des
                 Knopfs „in der Lohndatei MM/JJJJ“

Dezember 2026, Berater- und Mandantennummer wie in den Mustern erfunden.
"""

import hashlib
import os
import uuid
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect as sa_inspect, text

from app.models import ArchiveImmutableError, EmployeePayrollSettings, Lohndatei, PersonalnummerVergabe, TimeEntry, TimeTrackingSettings
from app.routers import time_backoffice as backoffice_router
from app.routers import zeiten as zeiten_router
from app.time_backoffice import PersonalnummerGehalten, eingelesene_personalnummern, payroll_rows, personalnummer_freigeben
from tests.test_v224_field_view import make_employee
from tests.test_v325_contract_basis import beauftragen, make_quote
from tests.test_v380_nummern_eindeutig import _alembic, _ok

MIGRATION, VORHER = "d5a8e3c71b42", "c7e2b94a1f60"
PG_URL = os.getenv("ERP_TEST_POSTGRES_URL")
URL = "/api/time-backoffice/lohndateien"


@pytest.fixture
def w(threaded_db_session, router_test_client, fester_tag):
    db = threaded_db_session
    order = beauftragen(db, make_quote(db, is_consumer=False, number="0628"))
    s = db.get(TimeTrackingSettings, 1)
    s.datev_beraternummer, s.datev_mandantennummer, s.locked_until = "1234567", "12345", date(2026, 12, 31)
    ada = make_employee(db, "M-1", "Ada", "Test")
    db.add(EmployeePayrollSettings(employee_id=ada.id, datev_personnel_number="00101", export_umfang="alles", payroll_export_enabled=True))
    db.add(TimeEntry(employee_id=ada.id, project_id=order.project_id, order_id=order.id, work_date=date(2026, 12, 7), entry_type="site",
                     hours=Decimal("8"), break_minutes=0, status="booked", started_at=datetime(2026, 12, 7, 7), ended_at=datetime(2026, 12, 7, 15)))
    db.commit()
    return {"db": db, "ada": ada, "client": lambda rolle="buero_finanzen": router_test_client(db, backoffice_router.router, zeiten_router.router,
                                                                                               role=rolle, user_id=7, display_name="Fin Finanzen")}


def test_erzeugen_legt_ab_und_liefert_dieselben_bytes(w):
    c = w["client"]()
    r = c.post(URL, json={"monat": "2026-12"})
    assert r.status_code == 201, r.text
    f = r.json()
    row = w["db"].get(Lohndatei, f["id"])
    assert (f["monat"], f["dateiname"], f["erzeugt_von_name"], f["groesse"]) == ("2026-12-01", "DATEV_Lohndaten_2026-12.txt", "Fin Finanzen",
                                                                              len(row.inhalt))
    assert f["sha256"] == hashlib.sha256(row.inhalt).hexdigest() == row.sha256 and row.erzeugt_von_user_id == 7
    assert row.inhalt.startswith(b"1234567;12345;12/2026\r\n00101;7;1;1000;8,00;;;;;;\r\n")
    d = c.get(f"{URL}/{f['id']}/datei")
    assert d.status_code == 200 and d.content == row.inhalt
    assert 'attachment; filename="DATEV_Lohndaten_2026-12.txt"' in d.headers["content-disposition"] and d.headers["x-content-type-options"] == "nosniff"


def test_jede_erzeugte_datei_bleibt(w):
    c = w["client"]()
    erste, zweite = c.post(URL, json={"monat": "2026-12"}).json(), c.post(URL, json={"monat": "2026-12"}).json()
    assert erste["id"] != zweite["id"] and erste["sha256"] == zweite["sha256"]
    liste = c.get(URL, params={"monat": "2026-12"}).json()
    assert [x["id"] for x in liste] == [zweite["id"], erste["id"]] and "inhalt" not in liste[0]
    assert c.get(URL, params={"monat": "2026-11"}).json() == []
    assert [x["id"] for x in c.get("/api/zeiten/monat", params={"monat": "2026-12"}).json()["lohndateien"]] == [zweite["id"], erste["id"]]


def test_nicht_abgeschlossen_oder_unvollstaendig_nichts_abgelegt(w):
    c = w["client"]()
    w["db"].get(TimeTrackingSettings, 1).locked_until = date(2026, 11, 30)
    w["db"].commit()
    assert c.post(URL, json={"monat": "2026-12"}).status_code == 409
    w["db"].get(TimeTrackingSettings, 1).locked_until = date(2026, 12, 31)
    w["db"].query(EmployeePayrollSettings).update({"datev_personnel_number": None})
    w["db"].commit()
    r = c.post(URL, json={"monat": "2026-12"})
    assert r.status_code == 409 and [x["art"] for x in r.json()["liste"]] == ["personalnummer"]
    assert c.post(URL, json={"monat": "2026-13"}).status_code == 422
    assert w["db"].query(Lohndatei).count() == 0


def test_rechte(w):
    fid = w["client"]().post(URL, json={"monat": "2026-12"}).json()["id"]
    assert w["client"]("admin").get(f"{URL}/{fid}/datei").status_code == 200
    for rolle in ("buero_auftrag", "field"):
        c = w["client"](rolle)
        assert [c.post(URL, json={"monat": "2026-12"}).status_code, c.get(URL).status_code, c.get(f"{URL}/{fid}/datei").status_code] == [403] * 3
    assert w["db"].query(Lohndatei).count() == 1


def test_kein_get_export_mehr(w):
    c = w["client"]()
    assert c.get("/api/time-backoffice/datev-export", params={"start_date": "2026-12-01", "end_date": "2026-12-31"}).status_code in (404, 405)
    assert w["db"].query(Lohndatei).count() == 0


def test_unveraenderlich_und_pruefsumme(w):
    db = w["db"]
    fid = w["client"]().post(URL, json={"monat": "2026-12"}).json()["id"]
    row = db.get(Lohndatei, fid)
    row.inhalt = b"anders"
    with pytest.raises(ArchiveImmutableError):
        db.flush()
    db.rollback()
    db.delete(db.get(Lohndatei, fid))
    with pytest.raises(ArchiveImmutableError):
        db.flush()
    db.rollback()
    db.execute(text("UPDATE lohndateien SET inhalt = :b WHERE id = :i"), {"b": b"1234567;12345;12/2026\r\n", "i": fid})  # an der Sperre vorbei
    db.commit()
    assert w["client"]().get(f"{URL}/{fid}/datei").status_code == 409
    assert w["client"]().get(f"{URL}/999/datei").status_code == 404


def test_personalnummer_aus_der_ablage_bleibt_gesperrt(w):
    """Ada wechselt nach der abgelegten Dezember-Datei auf 00105: 00101 lässt sich nicht freigeben (409), die Liste nennt die Datei statt des Knopfs.
    Eine gemerkte, nie abgelegte Nummer geht weiter frei."""
    db = w["db"]
    ben = make_employee(db, "M-2", "Ben", "Test")
    db.add(EmployeePayrollSettings(employee_id=ben.id, datev_personnel_number="00102", export_umfang="alles", payroll_export_enabled=True))
    db.commit()
    w["client"]().post(URL, json={"monat": "2026-12"})  # Ben steht mit 00102 darin (Feiertag, Heiligabend, Silvester)
    db.add_all([PersonalnummerVergabe(nummer="00101", employee_id=w["ada"].id), PersonalnummerVergabe(nummer="00777", employee_id=None),
                PersonalnummerVergabe(nummer="00102", employee_id=None)])  # 00102 wie eingelesen, ohne Person
    db.query(EmployeePayrollSettings).filter_by(employee_id=w["ada"].id).update({"datev_personnel_number": "00105"})
    db.query(EmployeePayrollSettings).filter_by(employee_id=ben.id).update({"datev_personnel_number": None, "export_umfang": "nichts"})
    db.commit()
    with pytest.raises(PersonalnummerGehalten, match="steht in der abgelegten Lohndatei 12/2026"):
        personalnummer_freigeben(db, "00101")
    zeile = next(x for x in payroll_rows(db) if x["employee_id"] == w["ada"].id)
    assert (zeile["fruehere_personalnummern"], zeile["fruehere_in_lohndatei"]) == (["00101"], {"00101": "12/2026"})
    assert [(x["nummer"], x["lohndatei"]) for x in eingelesene_personalnummern(db)] == [("00102", "12/2026"), ("00777", None)]
    personalnummer_freigeben(db, "00777")
    r = w["client"]("admin").post("/api/time-backoffice/personalnummern/freigeben", json={"nummer": "00101"})
    assert r.status_code == 409 and "abgelegten Lohndatei 12/2026" in r.json()["detail"]


def test_seiten():
    root = Path(__file__).resolve().parent.parent / "app" / "templates"
    zeiten = (root / "zeiten.html").read_text(encoding="utf-8")
    assert '<button type="button" class="knopf knopf-neutral links-buendig" id="lohnDatev" hidden>DATEV-Export</button>' in zeiten
    assert "abschliessen('monat',()=>api('/api/time-backoffice/lohndateien',{method:'POST'" in zeiten
    assert "location.href='/api/time-backoffice/lohndateien/'+Number(f.id)+'/datei'" in zeiten
    assert "esc(berlinZeitpunkt(f.erzeugt_am))" in zeiten and "datev-export" not in zeiten
    settings = (root / "settings.html").read_text(encoding="utf-8")
    assert "(p.fruehere_in_lohndatei||{})[n]" in settings and "z.lohndatei?" in settings


# --- Migration d5a8e3c71b42 ------------------------------------------------------------------------------------------------------------------

def _probe(url: str, engine) -> None:
    _ok(_alembic(url, "upgrade", VORHER))
    assert "lohndateien" not in sa_inspect(engine).get_table_names()
    _ok(_alembic(url, "upgrade", MIGRATION))
    with engine.begin() as c:
        c.execute(text("INSERT INTO lohndateien (monat, dateiname, inhalt, sha256, groesse, erzeugt_am) VALUES ('2026-12-01', 'x.txt', :b, :s, 3, "
                       "'2027-01-05 10:00:00')"), {"b": b"abc", "s": hashlib.sha256(b"abc").hexdigest()})
        assert c.execute(text("SELECT inhalt, erzeugt_von_name FROM lohndateien")).one() == (b"abc", "System")
    _ok(_alembic(url, "downgrade", VORHER))
    assert "lohndateien" not in sa_inspect(engine).get_table_names()
    _ok(_alembic(url, "upgrade", "head"))


def test_migration_sqlite(tmp_path):
    url = f"sqlite:///{(tmp_path / 'ablage.db').as_posix()}"
    engine = create_engine(url)
    try:
        _probe(url, engine)
    finally:
        engine.dispose()


def test_migration_postgresql():
    if not PG_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    schema = f"pgtest_mig_ablage_{uuid.uuid4().hex[:8]}"
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
