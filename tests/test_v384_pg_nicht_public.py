"""Kein Test gegen PostgreSQL läuft im Schema public der Spielwiese (seit 1.8.81, Vorgabe Z2b "Vorweg" 3, CLAUDE.md Regel 27).

- Der Wächter (tests/pg_schutz.py) ist für den ganzen Testprozess eingerichtet (tests/conftest.py).
- Gegen PostgreSQL (opt-in, ERP_TEST_POSTGRES_URL): eine Verbindung ohne eigenes Schema darf Schemas anlegen und löschen, sonst
  nichts -- weder Tabellen anlegen noch lesen oder schreiben; in einem Wegwerf-Schema geht alles.
- Kindprozesse (alembic, Start von app.main) sieht der Wächter nicht: jede Funktion unter tests/, die DATABASE_URL an einen
  Kindprozess gibt, prüft die URL mit pg_url_pruefen() (AST); die Prüfung lehnt PostgreSQL ohne bzw. mit public als search_path ab.
- Jede Engine auf ERP_TEST_POSTGRES_URL unter tests/ hat ein eigenes search_path oder dient nur der Verwaltung (AST)."""

import ast
import os
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from tests.pg_schutz import SchemaPublicVerboten, pg_url_pruefen, waechter_aktiv

ROOT = Path(__file__).resolve().parent.parent
TESTS = ROOT / "tests"
PG_URL = os.getenv("ERP_TEST_POSTGRES_URL")


def test_the_guard_is_set_for_the_whole_test_process():
    assert waechter_aktiv()


def test_child_process_urls_need_their_own_schema():
    assert pg_url_pruefen("sqlite:///x.db") == "sqlite:///x.db"
    ok = "postgresql+psycopg://erp@127.0.0.1:5433/spielwiese?options=-csearch_path=pgtest_x&application_name=pgtest_x"
    assert pg_url_pruefen(ok) == ok
    for url in ("postgresql+psycopg://erp@127.0.0.1:5433/spielwiese",
                "postgresql+psycopg://erp@127.0.0.1:5433/spielwiese?application_name=x",
                "postgresql+psycopg://erp@127.0.0.1:5433/spielwiese?options=-csearch_path=public",
                "postgresql+psycopg://erp@127.0.0.1:5433/spielwiese?options=-csearch_path%3D%22%24user%22,public"):
        with pytest.raises(SchemaPublicVerboten):
            pg_url_pruefen(url)


def _gibt_database_url_weiter(node: ast.AST) -> bool:
    """dict(..., DATABASE_URL=…), {"DATABASE_URL": …} oder env["DATABASE_URL"] = …"""
    if isinstance(node, ast.Call) and any(k.arg == "DATABASE_URL" for k in node.keywords):
        return True
    if isinstance(node, ast.Dict) and any(isinstance(k, ast.Constant) and k.value == "DATABASE_URL" for k in node.keys):
        return True
    if isinstance(node, ast.Assign):
        return any(isinstance(t, ast.Subscript) and isinstance(t.slice, ast.Constant) and t.slice.value == "DATABASE_URL"
                   for t in node.targets)
    return False


def _ruft(fn: ast.AST, name: str) -> bool:
    return any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == name for n in ast.walk(fn))


def test_every_function_handing_database_url_to_a_child_checks_it():
    funde, gesehen = [], 0
    for path in sorted(TESTS.glob("*.py")):
        if path.name in ("conftest.py", "pg_schutz.py"):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if any(_gibt_database_url_weiter(n) for n in ast.walk(fn)):
                gesehen += 1
                if not _ruft(fn, "pg_url_pruefen"):
                    funde.append(f"{path.name}:{fn.lineno} {fn.name}")
    assert gesehen >= 3, gesehen  # _alembic (test_v380), _start (test_v345), test_v252
    assert funde == [], "DATABASE_URL an einen Kindprozess ohne pg_url_pruefen(): " + ", ".join(funde)


def _pg_url_name(node: ast.AST, names: set[str]) -> bool:
    if isinstance(node, ast.Name) and node.id in names:
        return True
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "getenv" and \
        node.args and isinstance(node.args[0], ast.Constant) and node.args[0].value == "ERP_TEST_POSTGRES_URL"


def _hat_search_path(call: ast.Call) -> bool:
    return any("search_path" in ast.unparse(k.value) for k in call.keywords)


VERWALTUNG_SQL = ("CREATE SCHEMA", "DROP SCHEMA", "pg_terminate_backend")


def _nur_verwaltung(fn: ast.AST, var: str) -> bool:
    """Die Engine var (ohne eigenes Schema) dient im Rumpf nur der Verwaltung: benutzt nur über begin()/connect()/dispose(),
    nirgends weitergegeben, und in jedem "with var.begin()/connect() as c:" führt c nur CREATE/DROP SCHEMA bzw.
    pg_terminate_backend aus."""
    for n in ast.walk(fn):
        if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == var \
                and n.attr not in ("begin", "connect", "dispose"):
            return False
        if isinstance(n, ast.Call) and (any(isinstance(a, ast.Name) and a.id == var for a in n.args)
                                        or any(isinstance(k.value, ast.Name) and k.value.id == var for k in n.keywords)):
            return False  # z. B. sessionmaker(bind=admin) oder Base.metadata.create_all(admin)
        if not isinstance(n, ast.With):
            continue
        for item in n.items:
            c = item.context_expr
            if not (isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute) and isinstance(c.func.value, ast.Name)
                    and c.func.value.id == var and isinstance(item.optional_vars, ast.Name)):
                continue
            conn = item.optional_vars.id
            for stmt in n.body:
                for m in ast.walk(stmt):
                    if isinstance(m, ast.Call) and isinstance(m.func, ast.Attribute) and isinstance(m.func.value, ast.Name) \
                            and m.func.value.id == conn and m.func.attr == "execute":
                        sql = ast.unparse(m.args[0]) if m.args else ""
                        if not any(w in sql for w in VERWALTUNG_SQL):
                            return False
    return True


def test_every_pg_engine_in_tests_has_its_own_schema_or_only_administers():
    funde, gesehen = [], 0
    for path in sorted(TESTS.glob("*.py")):
        if path.name in ("pg_schutz.py", Path(__file__).name):  # dieser Test benutzt public absichtlich (Gegenprobe des Wächters)
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        names = {t.id for n in ast.walk(tree) if isinstance(n, ast.Assign) for t in n.targets
                 if isinstance(t, ast.Name) and _pg_url_name(n.value, set())}
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            local = names | {t.id for n in ast.walk(fn) if isinstance(n, ast.Assign) for t in n.targets
                             if isinstance(t, ast.Name) and _pg_url_name(n.value, names)}
            for n in ast.walk(fn):
                if not (isinstance(n, ast.Assign) and isinstance(n.value, ast.Call) and isinstance(n.value.func, ast.Name)
                        and n.value.func.id == "create_engine" and n.value.args and _pg_url_name(n.value.args[0], local)):
                    continue
                gesehen += 1
                var = n.targets[0].id if isinstance(n.targets[0], ast.Name) else None
                if _hat_search_path(n.value) or (var and _nur_verwaltung(fn, var)):
                    continue
                funde.append(f"{path.name}:{n.lineno} {fn.name}")
    assert gesehen >= 20, gesehen
    assert funde == [], "Engine auf ERP_TEST_POSTGRES_URL ohne eigenes Schema: " + ", ".join(funde)


@pytest.fixture
def pg_url():
    if not PG_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    return PG_URL


def test_pg_public_allows_only_schema_administration(pg_url):
    schema = f"pgtest_public_{uuid.uuid4().hex[:8]}"
    admin = create_engine(pg_url)
    try:
        with admin.begin() as conn:
            conn.execute(text(f"CREATE SCHEMA {schema}"))  # Verwaltung: erlaubt
        for sql in (f"CREATE TABLE erp_waechter_{schema} (id integer)", "SELECT count(*) FROM pg_class",
                    "SELECT * FROM general_settings"):
            with admin.connect() as conn:
                with pytest.raises(Exception) as caught:
                    conn.execute(text(sql))
            assert isinstance(caught.value, SchemaPublicVerboten) or isinstance(
                getattr(caught.value, "orig", None), SchemaPublicVerboten), caught.value
        engine = create_engine(pg_url, connect_args={"options": f"-csearch_path={schema}"})
        try:
            with engine.begin() as conn:  # im Wegwerf-Schema geht alles
                conn.execute(text("CREATE TABLE probe (id integer)"))
                conn.execute(text("INSERT INTO probe VALUES (1)"))
                assert conn.execute(text("SELECT count(*) FROM probe")).scalar() == 1
        finally:
            engine.dispose()
    finally:
        with admin.begin() as conn:
            conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        admin.dispose()
    katalog = create_engine(pg_url, connect_args={"options": "-csearch_path=pg_catalog"})
    try:  # nichts in public hinterlassen
        with katalog.connect() as conn:
            left = conn.execute(text("SELECT count(*) FROM pg_tables WHERE schemaname = 'public' AND tablename = :t"),
                                {"t": f"erp_waechter_{schema}"}).scalar()
    finally:
        katalog.dispose()
    assert left == 0
