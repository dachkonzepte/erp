"""Version 1.8.98 -- Cache-Control: no-store für jede Antwort an eine angemeldete Sitzung (Vorgabe vom 14.10.2026, Punkt 3).

Bis 1.8.97 zeigte "Zurück" nach dem Abmelden die Seite samt Daten (Back-Forward-Cache, ohne ihn der HTTP-Cache: Seite und 9
API-Antworten) -- auf dem Fahrzeug-Tablet mit mehreren Monteuren (Nebenbefund 4 aus 1.8.97). Jetzt setzt die Anmeldeschranke
(app/anmeldeschranke.py) "Cache-Control: no-store" an jede Antwort an eine angemeldete Sitzung, auch an PDFs und Dateien, und ersetzt
dabei eine eigene Angabe des Endpunkts (Logo: ein Jahr "immutable").

Dauertest: jeder GET-Endpunkt (API und Seiten) aller Router, in der Reihenfolge von app/main.py, über die echte Anmeldeschranke -- als
Administrator auf den Testdaten von tests/test_v326_monteur_datengrenze.py (mit Logo) und als Monteurin. Jede Antwort, gleich welcher
Status, trägt no-store; ein neuer Endpunkt ist ohne Zutun dabei. Die Klicktests scripts/klicktest_anmelden.py prüfen "Zurück" nach
dem Abmelden im echten Browser."""

from __future__ import annotations

import re
from io import BytesIO

import pytest
from fastapi.routing import APIRoute
from PIL import Image
from sqlalchemy import select

from app import sitzungen
from app.auth import COOKIE_NAME
from app.models import AppUser, GeneralSettings
from tests.anmeldung import client_mit_schranke, neue_datenbank
from tests.test_v326_monteur_datengrenze import (
    PFAD_WERTE, QUERY_JE_ROUTE, QUERY_WERTE, _buero_welt, _routers_in_betriebsreihenfolge, _wert,
)
from tests.uhr import uhr_festhalten


# Pfadwerte der Seiten, die test_v326 (nur /api/) nicht kennt.
SEITEN_WERTE = {"data_type": "customers", "record_id": "@customer_id"}


def _logo(db) -> None:
    from app.company_logo import replace_logo
    buf = BytesIO()
    Image.new("RGB", (8, 8), "white").save(buf, format="PNG")
    settings = db.get(GeneralSettings, 1)
    settings.logo_filename = replace_logo(None, "logo.png", buf.getvalue())
    db.commit()


def _rundgang(client, welt: dict, routers) -> list[dict]:
    """Jeder GET-Endpunkt jedes Routers einmal, mit den Werten der Welt (wie test_v326, dazu die Seiten)."""
    antworten = []
    for router in routers:
        for route in router.routes:
            if not isinstance(route, APIRoute) or "GET" not in route.methods:
                continue
            werte = {p.name: _wert(welt, welt.get(p.name, PFAD_WERTE.get(p.name, SEITEN_WERTE.get(p.name)))) for p in route.dependant.path_params}
            if any(v is None for v in werte.values()):
                antworten.append({"route": route.path, "status": None, "cache": None})
                continue
            query = {k: _wert(welt, v) for k, v in QUERY_JE_ROUTE.get(route.path, {}).items()}
            for param in route.dependant.query_params:
                if param.field_info.is_required() and param.name not in query and param.name in QUERY_WERTE:
                    query[param.name] = _wert(welt, QUERY_WERTE[param.name])
            pfad = re.sub(r"\{(\w+):\w+\}", r"{\1}", route.path)  # {id:int} der Seiten
            antwort = client.get(pfad.format(**werte), params=query, follow_redirects=False)
            antworten.append({"route": route.path, "status": antwort.status_code, "cache": antwort.headers.get("cache-control"),
                              "art": antwort.headers.get("content-type", ""),
                              # seit 1.8.104 auch der Schutz gegen Einrahmen (geprüft in test_v409), seit 1.8.107 HSTS (test_v412)
                              "xfo": antwort.headers.get("x-frame-options"), "csp": antwort.headers.get("content-security-policy"),
                              "hsts": antwort.headers.get("strict-transport-security")})
    return antworten


@pytest.fixture(scope="module")
def durchlauf():
    engine, make_session = neue_datenbank()
    try:
        with uhr_festhalten():
            with make_session() as db:
                welt = _buero_welt(db)
                _logo(db)
                admin = db.get(AppUser, welt["admin_id"])
                monteurin = db.get(AppUser, welt["user_id"])
                admin_wert = sitzungen.neue_sitzung(db, admin, zweiter_faktor=True)
                monteur_wert = sitzungen.neue_sitzung(db, monteurin)
                db.commit()
            routers = _routers_in_betriebsreihenfolge()
            ergebnis = {}
            for name, wert in (("admin", admin_wert), ("monteurin", monteur_wert)):
                client = client_mit_schranke(make_session, *routers, raise_server_exceptions=False)
                client.cookies.set(COOKIE_NAME, wert, domain="testserver.local")
                ergebnis[name] = _rundgang(client, welt, routers)
            yield ergebnis
    finally:
        engine.dispose()


@pytest.mark.parametrize("wer", ["admin", "monteurin"])
def test_jede_antwort_an_eine_angemeldete_sitzung_ist_no_store(durchlauf, wer):
    antworten = [a for a in durchlauf[wer] if a["status"] is not None]
    ohne = [f"{a['route']} ({a['status']}): {a['cache']!r}" for a in antworten if a["cache"] != "no-store"]
    assert ohne == [], "Antwort an eine angemeldete Sitzung ohne Cache-Control: no-store: " + "; ".join(ohne)


def test_der_rundgang_trifft_die_endpunkte_mit_inhalt(durchlauf):
    """Sonst prüfte der Dauertest nur Fehlerseiten: als Administrator die allermeisten mit 200, darunter Seiten, PDFs und das Logo
    (dessen eigene Angabe -- ein Jahr "immutable" -- ersetzt wird)."""
    admin = durchlauf["admin"]
    ohne_wert = [a["route"] for a in admin if a["status"] is None]
    assert ohne_wert == [], "GET-Endpunkt ohne Testwert -- in PFAD_WERTE (test_v326) oder SEITEN_WERTE ergänzen: " + ", ".join(ohne_wert)
    ok = [a for a in admin if a["status"] == 200]
    assert len(ok) >= 0.8 * len(admin), f"nur {len(ok)} von {len(admin)} mit 200"
    assert any(a["art"].startswith("text/html") and not a["route"].startswith("/api/") for a in ok)
    assert any(a["art"].startswith("application/pdf") for a in ok)
    assert [a["status"] for a in admin if a["route"] == "/api/settings/general/logo"] == [200]
    assert len(admin) > 300  # 310 GET-Routen am 14.10.2026


def test_auch_ohne_sitzung_bleibt_die_anmeldung_erreichbar_und_setzt_no_store():
    """Die Antwort, die eine Sitzung setzt (Anmeldung) oder löscht (Abmelden), trägt no-store; Anmeldeseite und /health ohne Sitzung
    bleiben, wie sie sind."""
    from app.auth import hash_password
    from app.routers import auth as auth_router
    from app.routers import pages as pages_router
    engine, make_session = neue_datenbank()
    with make_session() as db:
        db.add(AppUser(username="bea", display_name="Bea", role="buero_auftrag", active=True, password_hash=hash_password("Passwort-123")))
        db.commit()
    client = client_mit_schranke(make_session, pages_router.router, auth_router.router)
    assert client.get("/login").status_code == 200
    antwort = client.post("/api/auth/login", json={"username": "bea", "password": "Passwort-123"})
    assert (antwort.status_code, antwort.headers.get("cache-control")) == (200, "no-store")
    assert client.get("/login", follow_redirects=False).headers.get("cache-control") == "no-store"  # angemeldet
    abmelden = client.post("/api/auth/logout")
    assert abmelden.headers.get("cache-control") == "no-store"
    with make_session() as db:
        assert db.scalars(select(AppUser)).first() is not None
    engine.dispose()
