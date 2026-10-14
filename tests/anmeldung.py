"""Testanwendungen mit der echten Anmeldeschranke (seit 1.8.98).

Bis 1.8.97 bauten tests/test_v250_two_factor_auth.py, test_v256, test_v257 und test_v292 die Middleware von app/main.py je nach --
seit den Sitzungen auf dem Server (app/sitzungen.py) bindet jede dieselbe Funktion ein: app/anmeldeschranke.py::middleware(), mit der
Sitzungsfabrik des Tests. Middleware und Endpunkte bekommen dabei je eine eigene Sitzung, wie in der echten Anwendung (siehe den
Kommentar in test_v250 zum Fund mit request.state.erp_user)."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.anmeldeschranke import middleware
from app.database import Base, get_db


def neue_datenbank():
    """Eine leere In-Memory-Datenbank für mehrere Threads (TestClient) und ihre Sitzungsfabrik."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine)


def client_mit_schranke(make_session, *routers, raise_server_exceptions: bool = True) -> TestClient:
    """TestClient auf app_mit_schranke()."""
    return TestClient(app_mit_schranke(make_session, *routers), raise_server_exceptions=raise_server_exceptions)


def app_mit_schranke(make_session, *routers) -> FastAPI:
    """FastAPI mit den Routern, get_db auf make_session und der echten Anmeldeschranke."""
    app = FastAPI()
    for router in routers:
        app.include_router(router)

    def _db():
        db = make_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _db
    app.middleware("http")(middleware(make_session))
    return app
