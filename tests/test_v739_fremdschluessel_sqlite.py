"""Version 1.9.339 (Runde V1, Punkt 2): jede SQLite-Verbindung der Tests prüft Fremdschlüssel (PRAGMA foreign_keys=ON).

Bis 1.9.338 prüfte die Suite keinen Fremdschlüssel -- SQLite tut das nur mit dem PRAGMA, und app/database.py setzt es bewusst nicht. Fünf Fehler,
die live (PostgreSQL) mit 500 abgingen, blieben so unsichtbar (Befund SQLite/PostgreSQL, E1–E5). tests/conftest.py schaltet das PRAGMA seither
für jede neue SQLite-Verbindung des Testprozesses ein (ein Ereignis „connect“ an jeder Engine). Dieser Wächter hält fest:

- jede Art, wie ein Test eine SQLite-Datenbank öffnet, hat die Prüfung an (Fixtures, wegwerf_engine(), create_engine(), Datei, die Engine der
  App aus app.database), und ein Verstoß scheitert sofort;
- kein Test schaltet sie wieder ab (AUSNAHMEN, darf nur kürzer werden) und kein Test schaltet sie selbst ein (das macht conftest für alle).
"""

import ast
import re
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Quote
from tests.aufraeumen import wegwerf_engine

ROOT = Path(__file__).resolve().parents[1]
AUS = re.compile(r"foreign_keys\s*=\s*(off|0|false|no)\b", re.IGNORECASE)
EIN = re.compile(r"PRAGMA\s+foreign_keys\s*=\s*(on|1|true|yes)\b", re.IGNORECASE)
# Datei -> Grund. Darf nur kürzer werden.
AUSNAHMEN: dict[str, str] = {
    "tests/test_v325_contract_basis.py": "Migration im Batch-Modus: SQLite baut customers neu und verweigert das Löschen der alten Tabelle, solange "
                                         "Projekte darauf zeigen; PostgreSQL ändert die Spalte ohne Neuaufbau. Nur für die Dauer der Migration.",
}
EINSCHALTEN_ERLAUBT = {"tests/conftest.py", "tests/test_v739_fremdschluessel_sqlite.py"}


def _an(conn) -> int:
    return conn.execute(text("PRAGMA foreign_keys")).scalar()


def test_db_session_prueft_fremdschluessel(db_session):
    assert _an(db_session) == 1


def test_threaded_db_session_prueft_fremdschluessel(threaded_db_session):
    assert _an(threaded_db_session) == 1


@pytest.mark.parametrize("url", ["sqlite://", "sqlite:///:memory:"])
def test_wegwerf_engine_und_create_engine_pruefen_fremdschluessel(url):
    for engine in (wegwerf_engine(url), create_engine(url)):
        try:
            with engine.connect() as conn:
                assert _an(conn) == 1
        finally:
            engine.dispose()


def test_datei_und_engine_der_app_pruefen_fremdschluessel(tmp_path):
    from app.database import engine as app_engine
    datei = create_engine(f"sqlite:///{(tmp_path / 'probe.db').as_posix()}")
    try:
        for engine in (datei, app_engine):
            with engine.connect() as conn:
                assert _an(conn) == 1
    finally:
        datei.dispose()


def test_ein_verstoss_scheitert_sofort(db_session):
    """Ein Angebot zu einem Projekt, das es nicht gibt -- bis 1.9.338 nahm die Suite es still an."""
    db_session.add(Quote(quote_number="Q-GEIST", project_id=999999, title="Geist"))
    with pytest.raises(IntegrityError, match="FOREIGN KEY constraint failed"):
        db_session.flush()
    db_session.rollback()


def _sql_texte(quelle: str):
    """Jeder Text im Code (auch Teile eines f-Strings), ohne Kommentare und Docstrings -- dort darf „PRAGMA foreign_keys=…“ erklärt werden."""
    baum = ast.parse(quelle)
    doc = {id(k.value) for k in ast.walk(baum) if isinstance(k, ast.Expr) and isinstance(k.value, ast.Constant)}
    for k in ast.walk(baum):
        if isinstance(k, ast.Constant) and isinstance(k.value, str) and id(k) not in doc:
            yield k.lineno, k.value


def test_kein_test_schaltet_die_pruefung_ab_oder_selbst_ein():
    abschalten, einschalten = [], []
    for datei in sorted((ROOT / "tests").rglob("*.py")):
        rel = datei.relative_to(ROOT).as_posix()
        if rel == "tests/test_v739_fremdschluessel_sqlite.py":
            continue
        for nr, wert in _sql_texte(datei.read_text(encoding="utf-8")):
            if AUS.search(wert) and rel not in AUSNAHMEN:
                abschalten.append(f"{rel}:{nr}")
            if EIN.search(wert) and rel not in EINSCHALTEN_ERLAUBT:
                einschalten.append(f"{rel}:{nr}")
    assert abschalten == [], "Schaltet die Prüfung der Fremdschlüssel ab (Eltern echt anlegen, tests/migrationsbestand.py): " + ", ".join(abschalten)
    assert einschalten == [], "Schaltet die Prüfung selbst ein (das macht tests/conftest.py für jede Verbindung): " + ", ".join(einschalten)


def test_ausnahmen_gibt_es_noch():
    for rel in AUSNAHMEN:
        assert any(AUS.search(w) for _, w in _sql_texte((ROOT / rel).read_text(encoding="utf-8"))),             f"{rel} steht in AUSNAHMEN, schaltet aber nichts mehr ab -- streichen"
