"""Version 1.9.332 (Vorweg zu L2c-3): „An das Steuerbüro gesendet“ unter PostgreSQL.

Befund (12.11.2026, bei der Messung für L2c-3 gegen PostgreSQL): 1.9.328 schrieb in die Änderungshistorie die Aktion „Lohndatei an das Steuerbüro gesendet“
(36 Zeichen) bzw. „Vermerk „gesendet“ zurückgenommen“ (33) -- audit_logs.action ist String(30). PostgreSQL lehnte ab, Setzen und Zurücknehmen endeten mit
500 und speicherten nichts; SQLite nimmt einen zu langen Wert still an, deshalb blieb es in den Tests unsichtbar (Architektur „Feste Werte passen in ihre
Spalte“ prüfte die Aufrufe von record_audit_entry() bis dahin nicht).

    Länge     jede feste Aktion in einem Aufruf von record_audit_entry() unter app/ passt in audit_logs.action (Länge aus dem Modell); eine nicht feste wird
              genannt (es gibt keine)
    Postgres  versendet_setzen() und versendet_zuruecknehmen() gegen PostgreSQL in einem Wegwerf-Schema (opt-in über ERP_TEST_POSTGRES_URL, wie alle
              PostgreSQL-Tests): beide gespeichert, je ein Eintrag in der Historie
"""

import ast
import os
import uuid
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.grunddaten import anlegen
from app.lohndatei import ablegen, versendet_setzen, versendet_zuruecknehmen
from app.models import AuditLog, Lohndatei

PG_URL = os.getenv("ERP_TEST_POSTGRES_URL")
APP = Path(__file__).resolve().parents[1] / "app"


def _aktionen():
    """(Datei, Zeile, Ausdruck) je Aufruf von record_audit_entry() mit action=."""
    for pfad in sorted(APP.rglob("*.py")):
        for knoten in ast.walk(ast.parse(pfad.read_text(encoding="utf-8"))):
            if isinstance(knoten, ast.Call) and getattr(knoten.func, "id", getattr(knoten.func, "attr", None)) == "record_audit_entry":
                for kw in knoten.keywords:
                    if kw.arg == "action":
                        yield pfad.relative_to(APP.parent).as_posix(), knoten.lineno, kw.value


def test_jede_aktion_passt_in_ihre_spalte():
    laenge = AuditLog.__table__.c.action.type.length
    zu_lang, nicht_fest, gefunden = [], [], 0
    for datei, zeile, wert in _aktionen():
        gefunden += 1
        if isinstance(wert, ast.Constant) and isinstance(wert.value, str):
            if len(wert.value) > laenge:
                zu_lang.append(f"{datei}:{zeile} „{wert.value}“ ({len(wert.value)} > {laenge})")
        else:
            nicht_fest.append(f"{datei}:{zeile} {ast.unparse(wert)}")
    assert gefunden >= 16  # der Scanner findet die Aufrufe
    assert zu_lang == [] and nicht_fest == []


def test_gesendet_und_zuruecknehmen_unter_postgresql():
    if not PG_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    schema = f"pgtest_lohnvermerk_{uuid.uuid4().hex[:8]}"
    admin = create_engine(PG_URL)
    with admin.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
    engine = create_engine(PG_URL, connect_args={"options": f"-csearch_path={schema}", "application_name": schema})
    try:
        Base.metadata.create_all(engine)
        db = sessionmaker(bind=engine)()
        try:
            anlegen(db)
            db.commit()
            row = ablegen(db, date(2026, 12, 1), b"1234567;12345;12/2026\r\n", "DATEV_Lohndaten_2026-12.txt", user_id=None, user_name="Fin")
            db.commit()
            versendet_setzen(db, row.id, user_id=7, user_name="Fin Finanzen")
            assert db.get(Lohndatei, row.id).versendet_von_name == "Fin Finanzen"
            versendet_zuruecknehmen(db, row.id, user_id=1, user_name="Ada Admin")
            db.expire_all()
            assert db.get(Lohndatei, row.id).versendet_am is None
            assert [a.action for a in db.scalars(select(AuditLog).where(AuditLog.entity_type == "Lohndatei").order_by(AuditLog.id))] == [
                "als gesendet vermerkt", "Vermerk zurückgenommen"]
        finally:
            db.close()
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE application_name = :n"), {"n": schema})
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin.dispose()
