"""Version 1.9.327 (Lohn L2c-2, Punkt 0): an der Ablage der Lohndatei „art“ (datei | abgleich), „versendet am / von“ und „Notiz“.

    Bestand     jede abgelegte Datei ist „datei“, nicht versendet, ohne Notiz (Migration 517c94f6dbcf, auf einem Bestand unter SQLite und PostgreSQL)
    Sperre      seit 1.9.226 unveränderlich -- seit 1.9.327 (Entscheidung 12.11.2026) dürfen sich genau „versendet am / von“ ändern (setzen, zurücknehmen);
                Bytes, Prüfsumme, Monat, Art, Notiz und „erzeugt“ bleiben fest; gelöscht wird nie
    je Monat    höchstens eine versendete Zeile, auch in der Datenbank (eindeutiger Index nur über versendete Zeilen)
    downgrade   bricht ab, solange eine Abgleich-Zeile, eine versendete Datei oder eine Notiz da ist
"""

import os
import uuid
from datetime import date, datetime

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from app.lohndatei import ARTEN, abgelegt_dict, ablegen
from app.models import ArchiveImmutableError, Lohndatei
from tests.test_v380_nummern_eindeutig import _alembic, _ok

MIGRATION, VORHER = "517c94f6dbcf", "562f81626c3b"
PG_URL = os.getenv("ERP_TEST_POSTGRES_URL")
DEZ, JAN = date(2026, 12, 1), date(2027, 1, 1)


def datei(db, monat=DEZ, **k):
    row = ablegen(db, monat, b"1234567;12345;12/2026\r\n", f"DATEV_Lohndaten_{monat:%Y-%m}.txt", user_id=None, user_name="Fin", **k)
    db.commit()
    return row


def test_neue_zeile(db_session):
    row = datei(db_session)
    assert (row.art, row.versendet_am, row.versendet_von_name, row.notiz) == ("datei", None, None, None)
    a = datei(db_session, art="abgleich", notiz="Telefonat 05.02.")
    d = abgelegt_dict(a)
    assert (d["art"], d["notiz"], d["versendet_am"]) == ("abgleich", "Telefonat 05.02.", None)
    assert ARTEN == ("datei", "abgleich")
    with pytest.raises(ValueError):
        ablegen(db_session, DEZ, b"x", "x.txt", user_id=None, user_name=None, art="anders")


def test_nur_versendet_laesst_sich_aendern(db_session):
    db = db_session
    row = datei(db)
    row.versendet_am, row.versendet_von_user_id, row.versendet_von_name = datetime(2027, 1, 5, 9), 3, "Fin"
    db.commit()  # setzen geht
    row.versendet_am = row.versendet_von_user_id = row.versendet_von_name = None
    db.commit()  # zurücknehmen geht
    for feld, wert in (("inhalt", b"anders"), ("sha256", "0" * 64), ("monat", JAN), ("art", "abgleich"), ("notiz", "x"), ("erzeugt_von_name", "Anna"),
                       ("dateiname", "y.txt"), ("groesse", 1), ("erzeugt_am", datetime(2027, 1, 1))):
        setattr(row, feld, wert)
        with pytest.raises(ArchiveImmutableError):
            db.flush()
        db.rollback()
        row = db.get(Lohndatei, row.id)
    db.delete(row)
    with pytest.raises(ArchiveImmutableError):
        db.flush()
    db.rollback()


def test_je_monat_hoechstens_eine_versendete(db_session):
    db = db_session
    a, b, c = datei(db), datei(db), datei(db, monat=JAN)
    datei(db, art="abgleich", notiz="Telefonat")
    for r in (a, c):
        r.versendet_am, r.versendet_von_name = datetime(2027, 1, 5, 9), "Fin"
    db.commit()  # je ein Monat
    b.versendet_am, b.versendet_von_name = datetime(2027, 1, 6, 9), "Fin"
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def _probe(url: str, engine) -> None:
    _ok(_alembic(url, "upgrade", VORHER))
    with engine.begin() as c:
        c.execute(text("INSERT INTO lohndateien (monat, dateiname, inhalt, sha256, groesse, erzeugt_am, erzeugt_von_name) VALUES "
                       "('2026-12-01', 'DATEV_Lohndaten_2026-12.txt', :b, :s, 3, '2027-01-04 10:00:00', 'Fin')"), {"b": b"abc", "s": "a" * 64})
    _ok(_alembic(url, "upgrade", MIGRATION))
    with engine.connect() as c:
        assert tuple(c.execute(text("SELECT art, versendet_am, versendet_von_user_id, versendet_von_name, notiz FROM lohndateien")).one()) == (
            "datei", None, None, None, None)  # der Bestand: Datei, nicht versendet
    with engine.begin() as c:
        c.execute(text("INSERT INTO lohndateien (monat, dateiname, inhalt, sha256, groesse, erzeugt_am, erzeugt_von_name, versendet_am) VALUES "
                       "('2026-12-01', 'b.txt', :b, :s, 3, '2027-01-05 10:00:00', 'Fin', '2027-01-05 11:00:00')"), {"b": b"abc", "s": "b" * 64})
    with pytest.raises(Exception):
        with engine.begin() as c:  # eine zweite versendete im selben Monat
            c.execute(text("UPDATE lohndateien SET versendet_am = '2027-01-06 10:00:00' WHERE dateiname = 'DATEV_Lohndaten_2026-12.txt'"))
    nein = _alembic(url, "downgrade", VORHER)
    assert nein.returncode != 0 and "Downgrade abgebrochen" in (nein.stdout + nein.stderr)
    with engine.begin() as c:
        c.execute(text("UPDATE lohndateien SET versendet_am = NULL"))
    _ok(_alembic(url, "downgrade", VORHER))
    _ok(_alembic(url, "upgrade", "head"))


def test_migration_auf_einem_bestand_sqlite(tmp_path):
    url = f"sqlite:///{(tmp_path / 'lohndatei_versand.db').as_posix()}"
    engine = create_engine(url)
    try:
        _probe(url, engine)
    finally:
        engine.dispose()


def test_migration_auf_einem_bestand_postgresql():
    if not PG_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    schema = f"pgtest_mig_lohnversand_{uuid.uuid4().hex[:8]}"
    admin = create_engine(PG_URL)
    with admin.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
    url = f"{PG_URL}{'&' if '?' in PG_URL else '?'}options=-csearch_path={schema}"
    engine = create_engine(PG_URL, connect_args={"options": f"-csearch_path={schema}", "application_name": schema})
    try:
        _probe(url, engine)
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE application_name = :n"), {"n": schema})
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin.dispose()
