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

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import hash_password
from app.database import Base, get_db
from app.models import AppUser


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
    threaded_db_session-Fixture erzeugt worden sein."""
    def _make(db, *routers):
        app = FastAPI()
        for router in routers:
            app.include_router(router)

        @app.middleware("http")
        async def _fake_admin_identity(request, call_next):
            request.state.erp_user = AppUser(
                username="admin-test", display_name="Admin", role="admin", active=True,
                password_hash=hash_password("Passwort123"),
            )
            return await call_next(request)

        app.dependency_overrides[get_db] = lambda: db
        return TestClient(app)
    return _make
