"""Version 1.11.3 (Stufe P1b): Link, Code und Sitzung im Portal-Dienst -- die Wege über den Funktionen der Datenbank (app/portal/routen.py).

    Ohne Datenbank  Begrüßung je Anrede; jedes Ergebniswort jeder Funktion ist behandelt (BEHANDELT = Text der Funktionen); kein Weg nimmt eine ID; Cookies
                    nur über eine Stelle; Eingaben (Link fehlt, Code nicht 6 Ziffern, ueberall kein Wahrheitswert) 422 und ohne Cookie 401, bevor die
                    Datenbank gefragt wird; ein unbekanntes Ergebniswort 500; Prüfskript E4 nennt nur Zahlen
    PostgreSQL      (ein Wegwerf-Schema je Datei, der Dienst als Testrolle dkportal_test -- jeder Zugriff außerhalb der Rechte wäre ein Fehler):
                    ganzer Ablauf Link -> Code -> Willkommen -> abmelden mit Protokoll; Cookies __Host- mit Secure, HttpOnly, SameSite=Strict, ohne Domain;
                    jeder ungültige Link außen gleich; ohne gültige Sitzung 401 auf jedem Weg der Vorstufe und der Sitzung (zehn Zustände); Code einer
                    anderen Sitzung; fünf Versuche; verbrauchter Code; frühere Sitzung des Browsers endet; auf allen Geräten abmelden; Verlängern höchstens
                    stündlich mit Cookie; kein GET schreibt; Bremsen 429 mit Retry-After; Positivliste je Weg und Status (jede Antwort jedes Tests);
                    Link, Code und Cookie nie in Protokoll oder Antwort; Anschluss hinter nginx (echter uvicorn, X-Forwarded-For); Angriffe auf die neuen
                    Wege gegen einen echten uvicorn
"""

import logging
import os
import re
import socket
import sys
import threading
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.database import Base
from app.portal import funktionen, pruefwerte, rechte, routen, werte
from app.portal.begruessung import begruessung
from app.portal.main import erzeugen, kopf_der_migrationen
from app.portal.routen import COOKIE, COOKIE_CODE
from tests.test_v800_portal_funktionen import TESTROLLE, Welt
from tests.test_v801_portal_dienst import EIGEN, HERKUNFT, _einstellungen, _fastapi, _roh, _uvicorn, dienst  # noqa: F401 -- dienst ist eine Fixture

ROOT = Path(__file__).resolve().parent.parent
PG_URL = os.getenv("ERP_TEST_POSTGRES_URL")
CODE = "604213"
SITZUNG_SEKUNDEN = 30 * 24 * 3600

# Positivliste: genau diese Schlüssel je Weg und Status -- geprüft an jeder Antwort jedes Tests dieser Datei (Geraet.anfrage)
ERWARTET = {
    ("/api/link", 200): {"stand", "email_anzeige"}, ("/api/link", 422): {"fehler"}, ("/api/link", 429): {"fehler", "minuten"},
    ("/api/code", 200): {"stand"}, ("/api/code", 401): {"fehler"}, ("/api/code", 429): {"fehler", "minuten"},
    ("/api/code/stand", 200): {"stand"}, ("/api/code/stand", 401): {"fehler"},
    ("/api/code/pruefen", 200): {"stand", "rest"}, ("/api/code/pruefen", 401): {"fehler"}, ("/api/code/pruefen", 422): {"fehler"},
    ("/api/code/pruefen", 429): {"fehler", "minuten"},
    ("/api/sitzung/weiter", 200): {"stand"}, ("/api/sitzung/weiter", 401): {"fehler"},
    ("/api/abmelden", 200): {"stand"}, ("/api/abmelden", 401): {"fehler"}, ("/api/abmelden", 422): {"fehler"},
    ("/api/willkommen", 200): {"begruessung"}, ("/api/willkommen", 401): {"fehler"},
}


class Geraet:
    """Ein Browser: hält seine Cookies selbst (wie ein Browser nach Set-Cookie, Max-Age=0 löscht), schickt sie als Kopfzeile, prüft jede Antwort gegen die
    Positivliste und merkt sich jeden Antworttext."""

    def __init__(self, app, kekse: dict | None = None):
        self.client = TestClient(app, base_url=HERKUNFT, headers=EIGEN)
        self.kekse = dict(kekse or {})
        self.texte: list[str] = []

    def anfrage(self, methode: str, pfad: str, kopf: dict | None = None, **kw):
        kopf = dict(kopf or {})
        if self.kekse:
            kopf["Cookie"] = "; ".join(f"{k}={v}" for k, v in self.kekse.items())
        r = self.client.request(methode, pfad, headers=kopf, **kw)
        self.client.cookies.clear()
        for zeile in r.headers.get_list("set-cookie"):
            name, rest = zeile.split("=", 1)
            if "max-age=0" in zeile.lower():
                self.kekse.pop(name, None)
            else:
                self.kekse[name] = rest.split(";", 1)[0]
        if methode != "HEAD":
            self.texte.append(r.text)
            assert (pfad, r.status_code) in ERWARTET, (pfad, r.status_code, r.text)
            assert set(r.json()) == ERWARTET[(pfad, r.status_code)], (pfad, r.status_code, r.text)
        return r

    def link(self, wert):
        return self.anfrage("POST", "/api/link", {"X-Portal-Link": wert})

    def code(self):
        return self.anfrage("POST", "/api/code")

    def stand(self):
        return self.anfrage("GET", "/api/code/stand")

    def pruefen(self, code):
        return self.anfrage("POST", "/api/code/pruefen", json={"code": code})

    def weiter(self):
        return self.anfrage("POST", "/api/sitzung/weiter")

    def abmelden(self, ueberall=False):
        return self.anfrage("POST", "/api/abmelden", json={"ueberall": ueberall})

    def willkommen(self):
        return self.anfrage("GET", "/api/willkommen")


def _keks(r, name: str) -> str | None:
    return next((z for z in r.headers.get_list("set-cookie") if z.startswith(name + "=")), None)


def _gesetzt(r, name: str, sekunden: int) -> None:
    zeile = _keks(r, name)
    assert zeile, (name, r.headers.get_list("set-cookie"))
    teile = {t.strip().lower() for t in zeile.split(";")[1:]}
    assert {"httponly", "secure", "path=/", "samesite=strict", f"max-age={sekunden}"} <= teile, zeile
    assert not any(t.startswith("domain") for t in teile), zeile  # __Host-: nur diese Adresse


def _geloescht(r, name: str) -> None:
    zeile = _keks(r, name)
    assert zeile and "max-age=0" in zeile.lower() and "secure" in zeile.lower() and "path=/" in zeile.lower(), (name, zeile)


# --- ohne Datenbank ---------------------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("anrede, titel, vorname, nachname, name, erwartet", [
    ("Herr", "Dr.", "Max", "Muster", "Herr Dr. Max Muster", "Guten Tag, Herr Dr. Muster"),
    ("Frau", None, "Erika", "Muster", "Frau Erika Muster", "Guten Tag, Frau Muster"),
    ("Frau", " Prof. ", " Erika ", " Muster ", "", "Guten Tag, Frau Prof. Muster"),
    ("Firma", "Dr.", None, "Muster Bedachung GmbH", "Firma Muster Bedachung GmbH", "Guten Tag, Muster Bedachung GmbH"),
    ("Divers", "Dr.", "Kim", "Muster", "Divers Dr. Kim Muster", "Guten Tag, Dr. Kim Muster"),
    (None, None, "Max", "Muster", "Max Muster", "Guten Tag, Max Muster"),
    ("", "", "", "Muster", "Muster", "Guten Tag, Muster"),
    ("Herr", None, "Max", "", "Herr Max", "Guten Tag, Max"),
    (None, None, None, None, "Altbestand Muster", "Guten Tag, Altbestand Muster"),
    (None, None, None, None, None, "Guten Tag"),
    ("Herr", None, None, "<b>Muster</b>", "", "Guten Tag, Herr <b>Muster</b>"),  # bleibt Text; die Seite setzt ihn über textContent
])
def test_begruessung(anrede, titel, vorname, nachname, name, erwartet):
    assert begruessung(anrede, titel, vorname, nachname, name) == erwartet


def _woerter(funktion: str) -> set[str]:
    sql = next(s for n, _a, s in funktionen._FUNKTIONEN if n == funktion)
    rumpf = sql.split("$$", 1)[1]
    return set(re.findall(r"RETURN QUERY SELECT '(\w+)'::text", rumpf)) | set(re.findall(r"RETURN '(\w+)';", rumpf))


def test_jedes_ergebniswort_jeder_funktion_ist_behandelt():
    for funktion in ("portal_link_oeffnen", "portal_code_anfordern", "portal_code_pruefen", "portal_sitzung_weiter", "portal_abmelden"):
        assert routen.BEHANDELT[funktion] == _woerter(funktion), funktion
    rumpf = next(s for n, _a, s in funktionen._FUNKTIONEN if n == "portal_post_stand").split("$$", 1)[1]
    assert set(re.findall(r"'(\w+)'", rumpf)) == {"ungueltig", "keiner"} and "p.status" in rumpf
    assert routen.BEHANDELT["portal_post_stand"] == {"ungueltig", "keiner", *werte.POST_STATUS}
    # jede Funktion des Portals hat ihren Weg; portal_sitzung (nur prüfen) braucht heute keiner, portal_willkommen liefert eine Zeile
    assert set(routen.BEHANDELT) | {"portal_sitzung", "portal_willkommen"} == set(funktionen.FUER_DAS_PORTAL)


def test_kein_weg_nimmt_eine_id():
    """Der Kunde kommt nur aus der Sitzung: kein Pfad-, Abfrage-, Kopf- oder Cookie-Parameter; Körper nur Code bzw. ueberall."""
    koerper = {}
    for route in routen.router.routes:
        assert isinstance(route, APIRoute)
        d = route.dependant
        assert not (d.path_params or d.query_params or d.header_params or d.cookie_params), route.path
        koerper[route.path] = {f.name for f in d.body_params}
    assert {p: k for p, k in koerper.items() if k} == {"/api/code/pruefen": {"eingabe"}, "/api/abmelden": {"eingabe"}}
    assert set(routen.CodeIn.model_fields) == {"code"} and set(routen.AbmeldenIn.model_fields) == {"ueberall"}


def test_cookies_nur_an_einer_stelle():
    quelltext = (ROOT / "app" / "portal" / "routen.py").read_text(encoding="utf-8")
    assert quelltext.count(".set_cookie(") == 1 and quelltext.count(".delete_cookie(") == 1
    assert 'secure=True, httponly=True, samesite="strict"' in quelltext.split("def _setzen", 1)[1].split("def ", 1)[0]
    assert 'secure=True, httponly=True, samesite="strict"' in quelltext.split("def _loeschen", 1)[1].split("def ", 1)[0]
    assert COOKIE.startswith("__Host-") and COOKIE_CODE.startswith("__Host-")


@pytest.mark.parametrize("pfad, koerper", [
    ("/api/link", None),
    ("/api/code/pruefen", {"code": "12345"}), ("/api/code/pruefen", {"code": "1234567"}), ("/api/code/pruefen", {"code": "12a456"}),
    ("/api/code/pruefen", {"code": " 123456"}), ("/api/code/pruefen", {"code": 123456}), ("/api/code/pruefen", {"code": "１２３４５６"}),
    ("/api/code/pruefen", {"code": "123456", "zugang_id": 1}), ("/api/code/pruefen", {}),
    ("/api/abmelden", {"ueberall": "ja"}), ("/api/abmelden", {"ueberall": 1}), ("/api/abmelden", {}), ("/api/abmelden", {"ueberall": False, "x": 1}),
])
def test_eingaben_422_vor_der_datenbank(dienst, pfad, koerper):
    """Über SQLite (dort gibt es die Funktionen nicht): fragte der Weg die Datenbank, käme 500."""
    client, _ = dienst
    r = client.post(pfad, headers={**EIGEN, "X-Portal-Link": "x" * 257} if pfad == "/api/link" else EIGEN, json=koerper)
    assert (r.status_code, r.json()) == (422, {"fehler": "eingabe"})
    assert client.post("/api/link", headers=EIGEN).status_code == 422  # ohne Kopfzeile


def test_ohne_cookie_401_vor_der_datenbank(dienst):
    client, _ = dienst
    for keks in ({}, {COOKIE: "x" * 300, COOKIE_CODE: "y" * 300}, {"dk_erp_auth": pruefwerte.neuer_wert()}):  # zu lang zählt wie keins
        kopf = {**EIGEN, **({"Cookie": "; ".join(f"{k}={v}" for k, v in keks.items())} if keks else {})}
        for methode, pfad, koerper, loescht in (("POST", "/api/code", None, {COOKIE_CODE}), ("GET", "/api/code/stand", None, set()),
                                                ("POST", "/api/code/pruefen", {"code": CODE}, {COOKIE_CODE}),
                                                ("POST", "/api/sitzung/weiter", None, {COOKIE}),
                                                ("POST", "/api/abmelden", {"ueberall": True}, {COOKIE, COOKIE_CODE}), ("GET", "/api/willkommen", None, set())):
            r = client.request(methode, pfad, headers=kopf, json=koerper)
            client.cookies.clear()
            assert (r.status_code, r.json()) == (401, {"fehler": "sitzung"}), (pfad, keks)
            assert {z.split("=", 1)[0] for z in r.headers.get_list("set-cookie")} == loescht, pfad
            for name in loescht:
                _geloescht(r, name)


def test_unbekanntes_ergebniswort_500(dienst, monkeypatch, caplog):
    client, app = dienst
    db = _fastapi(app).state.db
    monkeypatch.setattr(db, "link_oeffnen", lambda *a: ("neu_erfunden", None, None))
    with caplog.at_level(logging.ERROR, logger="dk_portal"):
        r = client.post("/api/link", headers={**EIGEN, "X-Portal-Link": "irgendwas"})
    assert (r.status_code, r.json()) == (500, {"fehler": "technisch"})
    assert "UnbekanntesErgebnis" in caplog.text and "neu_erfunden" not in caplog.text and "irgendwas" not in caplog.text


def _skript():
    sys.path.insert(0, str(ROOT / "scripts"))
    import pruefe_portal_e4
    return pruefe_portal_e4


def test_pruefskript_e4_nennt_nur_zahlen():
    from sqlalchemy.pool import StaticPool
    from app.models import PortalBremse
    skript = _skript()
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    jetzt = datetime(2026, 11, 23, 10, 30)
    try:
        with Session(engine) as s:
            assert skript.main([], sitzung=s, ausgabe=(aus := []).append, jetzt=jetzt) == 1 and "Noch kein Aufruf" in aus[1]
            s.add_all([PortalBremse(schluessel="link:a:" + "a" * 64, fenster_beginn=datetime(2026, 11, 23, 10), zaehler=2),
                       PortalBremse(schluessel="link:a:" + "b" * 64, fenster_beginn=datetime(2026, 11, 23, 9), zaehler=3),
                       PortalBremse(schluessel="link:a:" + "c" * 64, fenster_beginn=datetime(2026, 11, 23, 8), zaehler=5),  # älter als das vorige Fenster
                       PortalBremse(schluessel="code:a:" + "d" * 64, fenster_beginn=datetime(2026, 11, 23, 10), zaehler=1),  # andere Bremse
                       PortalBremse(schluessel="linkXa:" + "e" * 64, fenster_beginn=datetime(2026, 11, 23, 10), zaehler=1)])
            s.commit()
            aus = []
            assert skript.main([], sitzung=s, ausgabe=aus.append, jetzt=jetzt) == 0
            assert aus[0] == "Link geöffnet seit 09:00 Uhr (UTC): 2 Anschlüsse, 5 Aufrufe."
            assert not any(c * 8 in "\n".join(aus) for c in "abcde")  # kein Prüfwert
            s.execute(text("DELETE FROM portal_bremsen WHERE schluessel LIKE 'link:a:b%'"))
            s.commit()
            assert skript.main([], sitzung=s, ausgabe=(aus := []).append, jetzt=jetzt) == 1 and "Nur ein Anschluss" in aus[1]
        assert skript.main([], umgebung={}, ausgabe=(aus := []).append) == 2 and "DATABASE_URL" in aus[0]
    finally:
        engine.dispose()


# --- PostgreSQL -------------------------------------------------------------------------------------------------------------------------------------

LEEREN = ("portal_zugriffe", "portal_codes", "portal_post", "portal_sitzungen", "portal_zugaenge", "portal_bremsen", "customers")


@pytest.fixture(scope="module")
def pg_modul():
    """Ein Schema für die ganze Datei (die Instanz trägt kein Schema je Test, Befund 13.11.), zwischen den Tests geleert."""
    if not PG_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    schema = f"pgtest_ps_{uuid.uuid4().hex[:8]}"
    admin = create_engine(PG_URL)
    with admin.begin() as c:
        c.execute(text(f"CREATE SCHEMA {schema}"))
    erp = create_engine(PG_URL, connect_args={"options": f"-csearch_path={schema}", "application_name": schema})
    portal = None
    try:
        with erp.connect() as c:
            if c.execute(text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": TESTROLLE}).first() is None:
                pytest.skip(f"Testrolle {TESTROLLE} fehlt (siehe tests/test_v799_portal_rechte.py)")
        Base.metadata.create_all(erp)  # legt die Funktionen an (app/database.py)
        with erp.begin() as c:
            c.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)"))
            c.execute(text("INSERT INTO alembic_version VALUES (:k)"), {"k": kopf_der_migrationen()})
            rechte.setzen(c, rolle=TESTROLLE, schema=schema)
        # der Dienst wie auf dem Server: eigene Engine, jede Verbindung als Rolle des Portals
        portal = create_engine(PG_URL, connect_args={"options": f"-csearch_path={schema} -crole={TESTROLLE}", "application_name": schema},
                               pool_size=3, max_overflow=3, pool_timeout=10)
        yield erp, portal, schema
    finally:
        if portal is not None:
            portal.dispose()
        erp.dispose()
        with admin.begin() as c:
            c.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE application_name = :n"), {"n": schema})
            c.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin.dispose()


@pytest.fixture
def welt(pg_modul):
    erp, portal, schema = pg_modul
    with erp.begin() as c:
        for tabelle in LEEREN:
            c.execute(text(f"DELETE FROM {tabelle}"))
        c.execute(text("DELETE FROM enabled_modules WHERE module_key = 'kundenportal'"))
        c.execute(text("INSERT INTO enabled_modules (module_key, enabled, updated_at) VALUES ('kundenportal', true, now())"))
    app = erzeugen(_einstellungen(), engine=portal, pruefen=False)
    return SimpleNamespace(w=Welt(erp, schema), app=app, erp=erp, portal=portal, schema=schema)


def _anmelden(welt, geraet: Geraet, link: str, code: str = CODE) -> str:
    """Ein Gerät durch Link, Code anfordern, Postbote (nachgespielt), Code richtig -- gibt den Wert des Cookies der bestätigten Sitzung zurück."""
    assert geraet.link(link).json()["stand"] == "code_noetig"
    assert geraet.code().json() == {"stand": "angefordert"}
    welt.w.code_anlegen(geraet.kekse[COOKIE_CODE], code)
    assert geraet.pruefen(code).json() == {"stand": "angemeldet", "rest": None}
    return geraet.kekse[COOKIE]


def test_pg_ganzer_ablauf(welt):
    w = welt.w
    kid, _zid, link = w.kunde()
    w.erp("UPDATE customers SET title = 'Dr.' WHERE id = :k", k=kid)
    g = Geraet(welt.app)
    r = g.link(link)
    assert r.json() == {"stand": "code_noetig", "email_anzeige": "m***@example.invalid"}
    _gesetzt(r, COOKIE_CODE, 15 * 60)
    vorlaeufig = g.kekse[COOKIE_CODE]
    assert COOKIE not in g.kekse
    assert g.stand().json() == {"stand": "keiner"}
    assert g.code().json() == {"stand": "angefordert"}
    assert g.stand().json() == {"stand": "wartet"}
    w.code_anlegen(vorlaeufig, CODE)
    w.erp("UPDATE portal_post SET status = 'gesendet', erledigt_am = now() AT TIME ZONE 'utc'")
    assert g.stand().json() == {"stand": "gesendet"}
    assert g.pruefen("111111").json() == {"stand": "falsch", "rest": 4}
    r = g.pruefen(CODE)
    assert r.json() == {"stand": "angemeldet", "rest": None}
    _gesetzt(r, COOKIE, SITZUNG_SEKUNDEN)
    _geloescht(r, COOKIE_CODE)
    wert = g.kekse[COOKIE]
    assert wert != vorlaeufig and COOKIE_CODE not in g.kekse  # neuer Wert nach dem Code
    assert g.willkommen().json() == {"begruessung": "Guten Tag, Herr Dr. Muster"}
    r = g.weiter()
    assert r.json() == {"stand": "angemeldet"} and not r.headers.get_list("set-cookie")  # eben bestätigt: noch nicht verlängert
    assert g.link(link).json() == {"stand": "angemeldet", "email_anzeige": None}
    r = g.abmelden()
    assert r.json() == {"stand": "abgemeldet"}
    _geloescht(r, COOKIE)
    assert g.weiter().status_code == 401
    assert Geraet(welt.app, {COOKIE: wert}).willkommen().status_code == 401  # der alte Wert gilt nicht mehr
    assert Geraet(welt.app, {COOKIE_CODE: vorlaeufig}).code().status_code == 401
    assert w.protokoll() == [("link_geoeffnet", "code_noetig"), ("code_angefordert", "ok"), ("code_falsch", "ungueltig"), ("angemeldet", "ok"),
                             ("link_geoeffnet", "angemeldet"), ("abgemeldet", "ok")]


def test_pg_jeder_ungueltige_link_ist_aussen_gleich(welt):
    w = welt.w
    antworten = []
    for grund in ("unbekannt", "gesperrt", "abgelaufen", "portal_aus", "archiv", "modul_aus"):
        kid, zid, link = w.kunde(portal=grund != "portal_aus", gueltig_tage=-1 if grund == "abgelaufen" else 365)
        if grund == "unbekannt":
            link = pruefwerte.neuer_wert()
        elif grund == "gesperrt":
            w.erp("UPDATE portal_zugaenge SET gesperrt_am = now(), gesperrt_grund = 'Test' WHERE id = :z", z=zid)
        elif grund == "archiv":
            w.erp("UPDATE customers SET archiviert_am = now() WHERE id = :k", k=kid)
        elif grund == "modul_aus":
            w.erp("UPDATE enabled_modules SET enabled = false WHERE module_key = 'kundenportal'")
        r = Geraet(welt.app).link(link)
        antworten.append((r.status_code, r.content, tuple(r.headers.get_list("set-cookie"))))
        w.erp("UPDATE enabled_modules SET enabled = true WHERE module_key = 'kundenportal'")
    assert set(antworten) == {(200, b'{"stand":"ungueltig","email_anzeige":null}', ())}
    assert [e for _a, e in w.protokoll()] == ["unbekannt", "gesperrt", "abgelaufen", "portal_aus", "archiv", "modul_aus"]
    assert w.erp("SELECT count(*) FROM portal_sitzungen")[0][0] == 0


def _zustand_sitzung(welt, zustand: str) -> dict:
    """Cookies eines Browsers, dessen bestätigte Sitzung im genannten Zustand ist."""
    w = welt.w
    kid, zid, link = w.kunde()
    wert = _anmelden(welt, Geraet(welt.app), link)
    if zustand == "ohne":
        return {}
    if zustand == "erfunden":
        return {COOKIE: pruefwerte.neuer_wert()}
    if zustand == "unbestaetigt":  # der Wert einer unbestätigten Sitzung im Cookie der bestätigten
        anderes = Geraet(welt.app)
        anderes.link(link)
        return {COOKIE: anderes.kekse[COOKIE_CODE]}
    if zustand == "erp":
        return {"dk_erp_auth": wert}
    sql = {"gesperrt": "UPDATE portal_zugaenge SET gesperrt_am = now() WHERE id = :z",
           "portal_aus": "UPDATE customers SET portal_aktiv = false WHERE id = :k",
           "archiv": "UPDATE customers SET archiviert_am = now() WHERE id = :k",
           "modul_aus": "UPDATE enabled_modules SET enabled = false WHERE module_key = 'kundenportal'",
           "zugang_abgelaufen": "UPDATE portal_zugaenge SET gueltig_bis = (now() AT TIME ZONE 'utc') - interval '1 minute' WHERE id = :z",
           "abgelaufen": "UPDATE portal_sitzungen SET laeuft_ab = (now() AT TIME ZONE 'utc') - interval '1 minute' WHERE wert_sha256 = :s",
           "beendet": "UPDATE portal_sitzungen SET beendet_am = now(), beendet_grund = 'gesperrt' WHERE wert_sha256 = :s"}[zustand]
    w.erp(sql, **{k: v for k, v in {"z": zid, "k": kid, "s": pruefwerte.sitzung(wert)}.items() if f":{k}" in sql})
    return {COOKIE: wert}


@pytest.mark.parametrize("zustand", ["ohne", "erfunden", "unbestaetigt", "erp", "gesperrt", "portal_aus", "archiv", "modul_aus", "zugang_abgelaufen",
                                     "abgelaufen", "beendet"])
def test_pg_ohne_gueltige_sitzung_401_auf_jedem_weg_der_sitzung(welt, zustand):
    kekse = _zustand_sitzung(welt, zustand)
    vorher = welt.w.protokoll()
    g = Geraet(welt.app, kekse)
    for anfrage in (g.weiter, g.willkommen, lambda: g.abmelden(True)):
        g.kekse = dict(kekse)
        r = anfrage()
        assert (r.status_code, r.json()) == (401, {"fehler": "sitzung"}), (zustand, r.request.url.path)
        if r.request.method == "GET":
            assert not r.headers.get_list("set-cookie")
        else:
            _geloescht(r, COOKIE)
    assert welt.w.protokoll() == vorher  # nichts verlängert, niemand abgemeldet


def _zustand_vorstufe(welt, zustand: str) -> dict:
    w = welt.w
    kid, zid, link = w.kunde()
    g = Geraet(welt.app)
    g.link(link)
    wert = g.kekse[COOKIE_CODE]
    if zustand == "ohne":
        return {}
    if zustand == "erfunden":
        return {COOKIE_CODE: pruefwerte.neuer_wert()}
    if zustand == "bestaetigt":  # der Wert einer bestätigten Sitzung im Cookie der Vorstufe
        return {COOKIE_CODE: _anmelden(welt, Geraet(welt.app), w.kunde()[2])}
    if zustand == "verbraucht":  # nach dem richtigen Code hat die Sitzung einen neuen Wert
        g.code()
        w.code_anlegen(wert, CODE)
        assert g.pruefen(CODE).json()["stand"] == "angemeldet"
        return {COOKIE_CODE: wert}
    sql = {"gesperrt": "UPDATE portal_zugaenge SET gesperrt_am = now() WHERE id = :z",
           "portal_aus": "UPDATE customers SET portal_aktiv = false WHERE id = :k",
           "archiv": "UPDATE customers SET archiviert_am = now() WHERE id = :k",
           "modul_aus": "UPDATE enabled_modules SET enabled = false WHERE module_key = 'kundenportal'",
           "abgelaufen": "UPDATE portal_sitzungen SET laeuft_ab = (now() AT TIME ZONE 'utc') - interval '1 minute' WHERE wert_sha256 = :s"}[zustand]
    w.erp(sql, **{k: v for k, v in {"z": zid, "k": kid, "s": pruefwerte.sitzung(wert)}.items() if f":{k}" in sql})
    return {COOKIE_CODE: wert}


@pytest.mark.parametrize("zustand", ["ohne", "erfunden", "bestaetigt", "verbraucht", "gesperrt", "portal_aus", "archiv", "modul_aus", "abgelaufen"])
def test_pg_ohne_gueltige_vorstufe_401_auf_jedem_weg_der_vorstufe(welt, zustand):
    kekse = _zustand_vorstufe(welt, zustand)
    post_vorher = welt.w.erp("SELECT count(*) FROM portal_post")[0][0]
    g = Geraet(welt.app, kekse)
    for anfrage in (g.code, g.stand, lambda: g.pruefen(CODE)):
        g.kekse = dict(kekse)
        r = anfrage()
        assert (r.status_code, r.json()) == (401, {"fehler": "sitzung"}), (zustand, r.request.url.path)
        if r.request.method == "GET":
            assert not r.headers.get_list("set-cookie")
        else:
            _geloescht(r, COOKIE_CODE)
    assert welt.w.erp("SELECT count(*) FROM portal_post")[0][0] == post_vorher  # kein Auftrag an den Postboten


def test_pg_code_einer_anderen_sitzung_passt_nicht(welt):
    _k, _z, link = welt.w.kunde()
    a, b = Geraet(welt.app), Geraet(welt.app)
    a.link(link)
    b.link(link)
    a.code()
    welt.w.code_anlegen(a.kekse[COOKIE_CODE], CODE)
    assert b.pruefen(CODE).json() == {"stand": "neu_anfordern", "rest": None}  # b hat noch keinen Code
    b.code()
    welt.w.code_anlegen(b.kekse[COOKIE_CODE], "111222")
    assert b.pruefen(CODE).json() == {"stand": "falsch", "rest": 4}  # der Code von a passt nicht zur Sitzung von b
    assert a.pruefen(CODE).json()["stand"] == "angemeldet"


def test_pg_fuenf_versuche_dann_neu_anfordern(welt):
    _k, _z, link = welt.w.kunde()
    g = Geraet(welt.app)
    g.link(link)
    g.code()
    welt.w.code_anlegen(g.kekse[COOKIE_CODE], CODE)
    assert [g.pruefen("000000").json()["rest"] for _ in range(5)] == [4, 3, 2, 1, 0]
    assert g.pruefen(CODE).json() == {"stand": "neu_anfordern", "rest": None}  # auch der richtige nicht mehr
    assert COOKIE not in g.kekse


def test_pg_eine_sitzung_je_browser(welt):
    """Meldet sich ein Browser bei einem anderen Zugang an, endet seine frühere Sitzung (abgemeldet); der andere Zugang braucht den Code."""
    w = welt.w
    _k1, _z1, link1 = w.kunde(nachname="Erste")
    _k2, _z2, link2 = w.kunde(anrede="Frau", nachname="Zweite")
    g = Geraet(welt.app)
    wert1 = _anmelden(welt, g, link1)
    assert g.link(link2).json()["stand"] == "code_noetig"  # die Sitzung von 1 gilt nicht für 2
    assert g.willkommen().json() == {"begruessung": "Guten Tag, Herr Erste"}  # bis zum Code bleibt 1
    g.code()
    w.code_anlegen(g.kekse[COOKIE_CODE], CODE)
    assert g.pruefen(CODE).json()["stand"] == "angemeldet"
    assert g.willkommen().json() == {"begruessung": "Guten Tag, Frau Zweite"}
    assert Geraet(welt.app, {COOKIE: wert1}).weiter().status_code == 401
    assert w.erp("SELECT beendet_grund FROM portal_sitzungen WHERE wert_sha256 = :s", s=pruefwerte.sitzung(wert1)) == [("abgemeldet",)]


def test_pg_abmelden_dieses_geraet_und_ueberall(welt):
    w = welt.w
    _k, _z, link = w.kunde()
    _k2, _z2, link2 = w.kunde(nachname="Zweite")
    a, b, c = Geraet(welt.app), Geraet(welt.app), Geraet(welt.app)
    for g in (a, b, c):
        _anmelden(welt, g, link)
    assert a.abmelden(False).json() == {"stand": "abgemeldet"}
    assert (b.weiter().status_code, c.weiter().status_code) == (200, 200)
    assert c.link(link).json()["stand"] == "angemeldet" and COOKIE_CODE not in c.kekse  # angemeldet: kein Code-Cookie
    assert c.link(link2).json()["stand"] == "code_noetig"  # dazu eine unbestätigte Sitzung bei einem anderen Zugang -- sie endet mit
    vorlaeufig = c.kekse[COOKIE_CODE]
    d = c
    r = d.abmelden(True)
    assert r.json() == {"stand": "abgemeldet"}
    _geloescht(r, COOKIE)
    _geloescht(r, COOKIE_CODE)
    assert b.weiter().status_code == 401  # auf allen Geräten
    assert w.erp("SELECT beendet_grund FROM portal_sitzungen WHERE wert_sha256 = :s", s=pruefwerte.sitzung(vorlaeufig)) == [("abgemeldet",)]
    assert [a for a, _e in w.protokoll() if a.endswith("abgemeldet")] == ["abgemeldet", "ueberall_abgemeldet", "abgemeldet"]


def test_pg_abmelden_beendet_die_eigene_sitzung_auch_wenn_sie_nicht_mehr_gilt(welt):
    """Dieses Gerät abmelden geht mit jeder nicht beendeten Sitzung des Browsers (sie endet nur); „auf allen Geräten“ nur mit gültiger."""
    w = welt.w
    kid, _z, link = w.kunde()
    wert = _anmelden(welt, Geraet(welt.app), link)
    w.erp("UPDATE customers SET portal_aktiv = false WHERE id = :k", k=kid)
    assert Geraet(welt.app, {COOKIE: wert}).abmelden(True).status_code == 401
    assert Geraet(welt.app, {COOKIE: wert}).abmelden(False).json() == {"stand": "abgemeldet"}
    assert Geraet(welt.app, {COOKIE: wert}).abmelden(False).status_code == 401  # schon beendet


def test_pg_weiter_verlaengert_hoechstens_stuendlich_und_setzt_dann_das_cookie(welt):
    w = welt.w
    _k, _z, link = w.kunde()
    g = Geraet(welt.app)
    wert = _anmelden(welt, g, link)
    s = pruefwerte.sitzung(wert)
    w.erp("UPDATE portal_sitzungen SET zuletzt_am = zuletzt_am - interval '2 hours', laeuft_ab = laeuft_ab - interval '2 hours' WHERE wert_sha256 = :s", s=s)
    ab_vorher = w.erp("SELECT laeuft_ab FROM portal_sitzungen WHERE wert_sha256 = :s", s=s)[0][0]
    r = g.weiter()
    assert r.json() == {"stand": "angemeldet"}
    _gesetzt(r, COOKIE, SITZUNG_SEKUNDEN)
    assert g.kekse[COOKIE] == wert  # derselbe Wert, nur länger
    ab_nachher = w.erp("SELECT laeuft_ab FROM portal_sitzungen WHERE wert_sha256 = :s", s=s)[0][0]
    assert timedelta(hours=1) < ab_nachher - ab_vorher < timedelta(hours=3)
    assert not g.weiter().headers.get_list("set-cookie")  # in derselben Stunde nicht noch einmal
    assert [a for a, _e in w.protokoll()].count("verlaengert") == 1


def test_pg_kein_get_schreibt(welt):
    w = welt.w
    _k, _z, link = w.kunde()
    g = Geraet(welt.app)
    _anmelden(welt, g, link)
    v = Geraet(welt.app)
    v.link(link)
    v.code()

    def stand():
        return (w.erp("SELECT count(*) FROM portal_zugriffe")[0][0], w.erp("SELECT coalesce(sum(zaehler), 0) FROM portal_bremsen")[0][0],
                [tuple(x) for x in w.erp("SELECT id, zuletzt_am, laeuft_ab, beendet_am, bestaetigt_am FROM portal_sitzungen ORDER BY id")],
                [tuple(x) for x in w.erp("SELECT id, zuletzt_genutzt_am FROM portal_zugaenge ORDER BY id")],
                w.erp("SELECT count(*) FROM portal_post")[0][0])
    vorher = stand()
    for _ in range(3):
        for r in (g.willkommen(), g.anfrage("HEAD", "/api/willkommen"), v.stand(), v.anfrage("HEAD", "/api/code/stand")):
            assert r.status_code == 200 and not r.headers.get_list("set-cookie")
    assert stand() == vorher


def test_pg_bremsen_429_mit_retry_after(welt):
    w = welt.w
    _k, _z, link = w.kunde()
    g = Geraet(welt.app)
    g.link(link)
    assert g.code().json() == {"stand": "angefordert"}
    r = g.code()  # innerhalb von 60 Sekunden
    assert (r.status_code, r.json(), r.headers["retry-after"]) == (429, {"fehler": "bremse", "minuten": 1}, "60")
    for _ in range(29):
        assert Geraet(welt.app).link(pruefwerte.neuer_wert()).status_code == 200  # dazu der erste: 30 je Stunde und Anschluss
    r = Geraet(welt.app).link(link)
    assert r.status_code == 429 and r.json()["fehler"] == "bremse" and 1 <= r.json()["minuten"] <= 60
    assert int(r.headers["retry-after"]) == r.json()["minuten"] * 60 and not r.headers.get_list("set-cookie")
    for _ in range(30):
        g.pruefen("000000")
    r = g.pruefen(CODE)
    assert r.status_code == 429 and int(r.headers["retry-after"]) == r.json()["minuten"] * 60


def test_pg_link_code_und_cookie_nie_in_protokoll_oder_antwort(welt, caplog):
    caplog.set_level(logging.DEBUG)
    caplog.set_level(logging.INFO, logger="sqlalchemy.engine")  # jede Anweisung mit ihren Parametern -- dort stehen nur Prüfwerte
    w = welt.w
    _k, _z, link = w.kunde(link=pruefwerte.neuer_wert())
    g = Geraet(welt.app)
    g.link(link)
    vorlaeufig = g.kekse[COOKIE_CODE]
    g.code()
    w.code_anlegen(vorlaeufig, CODE)
    g.pruefen("999999")
    g.pruefen(CODE)
    wert = g.kekse[COOKIE]
    g.willkommen()
    g.weiter()
    g.link(link)
    g.abmelden(True)
    Geraet(welt.app).link(link + "x")
    geheim = {"Link": link, "Code": CODE, "falscher Code": "999999", "Cookie vorläufig": vorlaeufig, "Cookie": wert}
    for name, wert_ in geheim.items():
        assert wert_ not in caplog.text, name
        assert not any(wert_ in t for t in g.texte), name
    assert pruefwerte.sitzung(wert) in caplog.text and "portal_code_pruefen" in caplog.text  # die Ausgabe von SQLAlchemy lief wirklich


def _hinter_nginx(app):
    """uvicorn wie unter gunicorn mit UvicornWorker: X-Forwarded-For nur von 127.0.0.1 (Vorgabe von gunicorn, die Einheit setzt nichts anderes)."""
    import uvicorn
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    server = uvicorn.Server(uvicorn.Config(app, http="h11", log_level="warning", lifespan="on", proxy_headers=True, forwarded_allow_ips="127.0.0.1"))
    faden = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    faden.start()
    ende = time.monotonic() + 15
    while not server.started:
        assert time.monotonic() < ende, "uvicorn startet nicht"
        time.sleep(0.05)
    return server, faden, sock.getsockname()[1]


def test_pg_anschluss_hinter_nginx(welt):
    """E4: der Anschluss ist die Adresse, die nginx anhängt (rechts in X-Forwarded-For) -- eine vom Besucher vorangestellte ändert nichts."""
    skript = _skript()
    server, faden, port = _hinter_nginx(welt.app)
    try:
        kopf = {"Host": "kunde.test", **EIGEN, "X-Portal-Link": "erfunden"}
        for i in range(30):
            assert _roh(port, "POST", "/api/link", {**kopf, "X-Forwarded-For": f"203.0.113.{i}, 198.51.100.7"}) == 200
        assert _roh(port, "POST", "/api/link", {**kopf, "X-Forwarded-For": "203.0.113.200, 198.51.100.7"}) == 429
        assert _roh(port, "POST", "/api/link", {**kopf, "X-Forwarded-For": "198.51.100.8"}) == 200
        assert _roh(port, "POST", "/api/link", kopf) == 200  # ohne Kopfzeile: die Adresse der Verbindung, ein eigener Anschluss
    finally:
        server.should_exit = True
        faden.join(15)
    with Session(welt.erp) as s:
        from app.berlin_time import utc_jetzt
        assert skript.zaehlen(s, skript.fenster_seit(utc_jetzt())) == (3, 33)


@pytest.mark.parametrize("http_art", ["h11", "httptools"])
def test_pg_angriffe_auf_die_neuen_wege(welt, http_art):
    pytest.importorskip(http_art)
    server, faden, port = _uvicorn(welt.app, http_art)
    try:
        erreicht = []
        for methode in ("GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "TRACE", "ERFUNDEN"):
            for pfad in sorted(routen.VORSTUFE | routen.SITZUNG | {"/api/link"}):
                for kopf in ({"Host": "kunde.test"}, {"Host": "kunde.test", **EIGEN}, {"Host": "app.dachkonzepte.gmbh", **EIGEN}, {},
                             {"Host": "kunde.test", **EIGEN, "Cookie": f"dk_erp_auth={pruefwerte.neuer_wert()}"},
                             {"Host": "kunde.test", "Origin": "https://app.dachkonzepte.gmbh", "Sec-Fetch-Site": "same-site",
                              "X-Portal-Link": "erfunden"}):
                    status = _roh(port, methode, pfad, kopf)
                    if status < 400:
                        erreicht.append((methode, pfad, kopf.get("Host"), status))
        assert erreicht == []  # ohne Link und ohne Sitzung erreicht nichts etwas
        assert welt.w.erp("SELECT count(*) FROM portal_zugriffe")[0][0] == 0
    finally:
        server.should_exit = True
        faden.join(15)
