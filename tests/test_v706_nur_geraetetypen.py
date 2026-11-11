"""Version 1.9.306 (L2a, Vorweg -- Frage 2 der Nachrunde der Geräte-Runde): die Auswahlliste heißt nur „Gerätetypen“.

    neu         eine neue Installation legt „Gerätetypen“ an (app/option_settings.py, Grunddaten beim Start)
    Bestand     die Migration 84ee228b331e stellt „Gerätetypen · Fuhrpark & Maschinen“ um, nur wo genau diese Bezeichnung steht; zurück ebenso
    Kette       ein Bestand von vor 1.9.301 („Ressourcentypen · Fuhrpark & Maschinen“) heißt nach „upgrade head“ „Gerätetypen“
Kein eigener Klicktest: die Bezeichnung steht nur in den Einstellungen (Auswahllisten), aus der Datenbank.
"""

import os
import uuid

import pytest
from sqlalchemy import create_engine, select, text

from app.models import SettingOptionGroup
from app.option_settings import DEFAULT_OPTION_GROUPS
from tests.test_v380_nummern_eindeutig import _alembic, _ok

MIGRATION = "84ee228b331e"
VORHER = "c990522c34ff"
VOR_1_9_301 = "c3e9f1a7b285"
PG_URL = os.getenv("ERP_TEST_POSTGRES_URL")
ZUSATZ = "Gerätetypen · Fuhrpark & Maschinen"
NUR = "Gerätetypen"


def test_neue_installation(db_session):
    assert DEFAULT_OPTION_GROUPS["resource_types"]["label"] == NUR
    assert db_session.scalar(select(SettingOptionGroup.label).where(SettingOptionGroup.group_key == "resource_types")) == NUR


def _labels(engine) -> dict:
    with engine.connect() as c:
        return dict(c.execute(text("SELECT group_key, label FROM setting_option_groups")).all())


def _einfuegen(engine, label: str) -> None:
    with engine.begin() as c:
        c.execute(text("DELETE FROM setting_option_groups"))
        for key, wert in (("resource_types", label), ("units", "Mengeneinheiten")):
            c.execute(text("INSERT INTO setting_option_groups (group_key, label, sort_order, created_at, updated_at) VALUES (:k, :l, 10, '2026-11-01', '2026-11-01')"),
                      {"k": key, "l": wert})


def _probe(url: str, engine) -> None:
    _ok(_alembic(url, "upgrade", VORHER))
    _einfuegen(engine, ZUSATZ)
    _ok(_alembic(url, "upgrade", MIGRATION))
    assert _labels(engine) == {"resource_types": NUR, "units": "Mengeneinheiten"}
    _ok(_alembic(url, "downgrade", VORHER))
    assert _labels(engine) == {"resource_types": ZUSATZ, "units": "Mengeneinheiten"}
    with engine.begin() as c:  # eine andere Bezeichnung bleibt
        c.execute(text("UPDATE setting_option_groups SET label = 'Fahrzeugarten' WHERE group_key = 'resource_types'"))
    _ok(_alembic(url, "upgrade", MIGRATION))
    assert _labels(engine)["resource_types"] == "Fahrzeugarten"
    # die ganze Kette: ein Bestand von vor 1.9.301 heißt danach nur „Gerätetypen“
    _ok(_alembic(url, "downgrade", VOR_1_9_301))
    _einfuegen(engine, "Ressourcentypen · Fuhrpark & Maschinen")
    _ok(_alembic(url, "upgrade", "head"))
    assert _labels(engine)["resource_types"] == NUR


def test_migration_auf_einem_bestand_sqlite(tmp_path):
    url = f"sqlite:///{(tmp_path / 'nur_geraetetypen.db').as_posix()}"
    engine = create_engine(url)
    try:
        _probe(url, engine)
    finally:
        engine.dispose()


def test_migration_auf_einem_bestand_postgresql():
    if not PG_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    schema = f"pgtest_mig_nurgeraetetypen_{uuid.uuid4().hex[:8]}"
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
