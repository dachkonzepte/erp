"""Version 1.9.214 (L1a Stufe 6, Punkt 3): die Zuordnung für den DATEV-Export mit den Werten des Lohnbüros.

    Heiligabend             FR / 1080
    Silvester               UU / ohne Lohnart
    Schlechtwetter Winter   WA / 8195, je Tag -- keine Monatszeile (bis 1.9.213: Monatszeile 8110)
    Berufsschule            FE / ohne Lohnart (vorbelegte Zeile wie Weiterbildung)
    Schlechtwetter Sommer   bleibt leer

Neue Installationen über app/grunddaten.py (app/lohnarten.py::START); eine bestehende stellt die Migration a3f61c8d2b95 um, nur wo noch genau
der bisherige Vorgabewert steht.
"""

import os
import uuid
from datetime import date

import pytest
from sqlalchemy import create_engine, text

from app.grunddaten import anlegen
from app.lohnarten import kalender, speichern, zuordnung
from app.models import LohnartZuordnung
from tests.test_v380_nummern_eindeutig import _alembic, _ok

MIGRATION = "a3f61c8d2b95"
VORHER = "8b4c2f9e1d07"
PG_URL = os.getenv("ERP_TEST_POSTGRES_URL")


def _wert(db, schluessel):
    z = db.query(LohnartZuordnung).filter_by(schluessel=schluessel).one()
    return z.kennzeichen, z.lohnart, bool(z.monatszeile)


def test_vorbelegung_mit_den_werten_des_lohnbueros(db_session):
    db = db_session
    assert _wert(db, "kalender:heiligabend") == ("FR", "1080", False)
    assert _wert(db, "kalender:silvester") == ("UU", None, False)
    assert _wert(db, "schlechtwetter:winter") == ("WA", "8195", False)
    assert _wert(db, "schlechtwetter:sommer") == (None, None, False)
    assert _wert(db, "art:berufsschule") == ("FE", None, False)


def test_schlechtwetter_winter_je_tag(db_session):
    w = zuordnung(db_session, "schlechtwetter", None, date(2026, 12, 7))
    assert (w["kennzeichen"], w["lohnart"], w["monatszeile"]) == ("WA", "8195", False)
    assert zuordnung(db_session, "schlechtwetter", None, date(2026, 6, 15)) is None
    assert kalender(db_session, "heiligabend")["lohnart"] == "1080"


def test_ein_neustart_laesst_geaendertes_und_geleertes_stehen(db_session):
    db = db_session
    speichern(db, "kalender:heiligabend", "XY", "1234", False)
    speichern(db, "art:berufsschule", None, None, False)
    anlegen(db)
    assert _wert(db, "kalender:heiligabend") == ("XY", "1234", False)
    assert _wert(db, "art:berufsschule") == (None, None, False)


# --- Migration a3f61c8d2b95 -----------------------------------------------------------------------------------------------------------------

def _zeilen(engine) -> dict:
    with engine.connect() as c:
        return {s: (k, l, bool(m)) for s, k, l, m in c.execute(text("SELECT schluessel, kennzeichen, lohnart, monatszeile FROM lohnart_zuordnungen"))}


def _bestand(engine, zeilen: dict) -> None:
    with engine.begin() as c:
        for schluessel, (k, l, m) in zeilen.items():
            c.execute(text("INSERT INTO lohnart_zuordnungen (schluessel, kennzeichen, lohnart, monatszeile, updated_at) VALUES (:s, :k, :l, :m, '2026-11-01')"),
                      {"s": schluessel, "k": k, "l": l, "m": m})


BISHER = {"arbeit": ("1", "1000", False), "kalender:heiligabend": ("BF", None, False), "schlechtwetter:winter": (None, "8110", True),
          "schlechtwetter:sommer": (None, None, False), "kalender:silvester": ("XY", None, False)}  # Silvester von Hand geändert


def _probe(url: str, engine) -> None:
    _ok(_alembic(url, "upgrade", VORHER))
    _bestand(engine, BISHER)
    r = _ok(_alembic(url, "upgrade", MIGRATION))
    assert "Zuordnung kalender:silvester: von Hand geändert, nicht umgestellt" in r.stdout + r.stderr
    nach = _zeilen(engine)
    assert nach == {**BISHER, "kalender:heiligabend": ("FR", "1080", False), "schlechtwetter:winter": ("WA", "8195", False)}
    assert "art:berufsschule" not in nach  # fehlt sie, legt sie der Start an
    _ok(_alembic(url, "downgrade", VORHER))
    assert _zeilen(engine) == BISHER
    with engine.begin() as c:  # eine leere Zeile Berufsschule (wie die Kategorie) wird FE, zurück wieder leer
        c.execute(text("INSERT INTO lohnart_zuordnungen (schluessel, monatszeile, updated_at) VALUES ('art:berufsschule', :m, '2026-11-01')"), {"m": False})
    _ok(_alembic(url, "upgrade", MIGRATION))
    assert _zeilen(engine)["art:berufsschule"] == ("FE", None, False)
    _ok(_alembic(url, "downgrade", VORHER))
    assert _zeilen(engine)["art:berufsschule"] == (None, None, False)
    _ok(_alembic(url, "upgrade", "head"))


def test_migration_auf_einem_bestand_sqlite(tmp_path):
    url = f"sqlite:///{(tmp_path / 'zuordnung.db').as_posix()}"
    engine = create_engine(url)
    try:
        _probe(url, engine)
    finally:
        engine.dispose()


def test_migration_auf_einem_bestand_postgresql():
    if not PG_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    schema = f"pgtest_mig_lohnbuero_{uuid.uuid4().hex[:8]}"
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
