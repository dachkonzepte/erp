"""Gemeinsame pytest-Fixtures (seit 1.0.11).

Viele bestehende Testdateien definieren ihre eigene db_session()- oder
new_db()-Hilfsfunktion für eine frische In-Memory-SQLite-Datenbank -- das
funktioniert und wurde hier bewusst nicht angefasst (Risiko für etwas, das
längst läuft, unnötig). Für NEUE Tests steht ab jetzt dieselbe Datenbank
als reguläre pytest-Fixture zur Verfügung, um die Dopplung nicht weiter
wachsen zu lassen:

    def test_etwas(db_session):
        kunde = Customer(name="Test", last_name="Test")
        db_session.add(kunde); db_session.commit()
        ...

Bestehende Testdateien mit eigener lokaler db_session()-Funktion sind davon
nicht betroffen: ein Name, der in einer Testdatei selbst definiert wird,
hat dort Vorrang vor dieser Fixture.
"""

import os
import tempfile
from pathlib import Path

# Regel 16 (CLAUDE.md): kein Testlauf berührt die echte Datenbank oder den echten Datenordner.
# Ohne diese Zeilen fiele app.database beim Import still auf ./dachkonzepte_erp.db zurück --
# jeder Test, der app.main importiert (create_all()) oder eine Seite rendert (Jinja-Globals mit
# eigener SessionLocal()), schriebe dann in die lokale Arbeitsdatenbank. Gesetzt VOR dem ersten
# Import aus app.*, bewusst unbedingt: auch ein in der Shell gesetztes DATABASE_URL (z. B. die
# lokale Postgres-Instanz) wird für den Testlauf ersetzt. Die Wegwerf-Dateien liegen im
# Temp-Verzeichnis und werden nie wiederverwendet.
_TEST_SCRATCH = Path(tempfile.mkdtemp(prefix="erp_pytest_"))
os.environ["DATABASE_URL"] = f"sqlite:///{(_TEST_SCRATCH / 'wegwerf.db').as_posix()}"
os.environ["ERP_DATA_DIR"] = str(_TEST_SCRATCH / "data")
os.environ.pop("ERP_ENV", None)

import pytest  # noqa: E402 -- erst nach dem Umlenken der Datenbank
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import hash_password
from app.database import Base, get_db
from app.models import AppUser
from tests.uhr import uhr_festhalten


def pytest_addoption(parser):
    parser.addoption(
        "--wanduhr", metavar="HH:MM", default=None,
        help="Suite so laufen lassen, als wäre es heute HH:MM (Europe/Berlin) -- Gegenprobe für Tests, "
             "die von der Tageszeit abhängen (seit 1.8.36, z. B. --wanduhr 19:30 nach der Feierabend-Grenze).",
    )


@pytest.fixture(scope="session", autouse=True)
def _wanduhr(request):
    """Ohne --wanduhr nichts. Mit: die Uhr der App läuft ab HH:MM heute. Sitzungsweit, damit sie auch
    unter Modul-Fixtures liegt; feste_uhr/uhr_festhalten() setzen sich darüber."""
    wert = request.config.getoption("--wanduhr")
    if not wert:
        yield
        return
    from datetime import time
    with uhr_festhalten(time.fromisoformat(wert)):
        yield


@pytest.fixture
def feste_uhr():
    """Uhr der App (app.berlin_time) läuft ab heute 10:00 Europe/Berlin -- für Tests, die sonst von
    der Tageszeit abhingen (Feierabend-Grenze an /api/field-view/today). Siehe tests/uhr.py."""
    with uhr_festhalten() as start:
        yield start


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def threaded_db_session():
    """Wie db_session(), aber mit check_same_thread=False + StaticPool (seit 1.2.15) -- der
    FastAPI-TestClient führt Endpunkte über einen Threadpool aus. Ohne StaticPool würde
    SQLAlchemys SingletonThreadPool dem neuen Thread eine ZWEITE, leere :memory:-Verbindung
    zuteilen ("no such table"); StaticPool erzwingt exakt dieselbe Connection über alle Threads.
    Für echte HTTP-Routen-Tests über router_test_client() -- reine In-Process-Tests bleiben bei
    der einfachen db_session-Fixture bzw. der gleichnamigen lokalen Funktion."""
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def router_test_client():
    """Baut aus ECHTEN Router-Instanzen (nicht kopiert) eine schlanke Test-App -- prüft die
    tatsächliche FastAPI/Starlette-Routenauflösung (z. B. dass "/reorder" nicht von "/{id}"
    verschluckt wird), ohne die produktive identity_and_audit_middleware (echte Datei-DB,
    echter Login) mitzuschleppen. Ersetzt sie durch einen einfachen, fest angemeldeten
    Admin-Kontext -- reine Test-Infrastruktur, betrifft nicht die Auth-Prüfung selbst.

    Verwendung: client = router_test_client(db, some_router, other_router); db muss mit der
    threaded_db_session-Fixture erzeugt worden sein.

    Seit "Rechtekonzept" (siehe CLAUDE.md): optionale Parameter role/employee_id, um dieselbe
    Test-App auch als Büro-/Monteur-Konto statt fest als Administrator zu durchlaufen (z. B. um
    require_role(...)-Ablehnungen zu belegen) -- Vorgabewerte bleiben "admin"/None, kein
    bestehender Aufruf muss sich ändern."""
    def _make(db, *routers, role="admin", employee_id=None):
        app = FastAPI()
        for router in routers:
            app.include_router(router)

        @app.middleware("http")
        async def _fake_identity(request, call_next):
            request.state.erp_user = AppUser(
                username=f"{role}-test", display_name=role.capitalize(), role=role, active=True,
                employee_id=employee_id, password_hash=hash_password("Passwort123"),
            )
            return await call_next(request)

        app.dependency_overrides[get_db] = lambda: db
        return TestClient(app)
    return _make
