"""Seit 1.9.27 (Stufe 2, Runde 9, Punkt 4): Anmeldung und Sperrseite auf dem Design-System.

    umgezogen      <body class="ds-seite">, darüber die Bildmarke mit Schriftzug (_marke.html: Kachel mit _bildmarke.html,
                   „DACHKONZEPTE“, „Rödchen GmbH · ERP“), darunter der gemeinsame Seitenkopf (teile/seitenkopf.html)
    Anmeldung      Titel „Anmelden“, Untertitel „Melde dich mit deinem Benutzernamen an.“ (bis dahin die Überschrift „DACHKONZEPTE ERP“ und
                   „Anmeldung für personengenaue Änderungshistorie“)
    Sperrseite     Titel „Kein Zugriff auf diese Seite“; Titel und Text sagen nicht zweimal dasselbe -- bis dahin „Diese Seite ist für deine
                   Rolle nicht verfügbar“ und darunter meist „Für deine Rolle nicht verfügbar.“ (die Vorgabe von require_role() und
                   require_min_role()). Die allgemeine Meldung lässt app/main.py weg, eine genauere (z. B. „nur für Administratoren“)
                   steht einmal da; darunter, was zu tun ist, und „Zur Startseite“ als grüne Hauptaktion

Im Browser prüft das scripts/klicktest_rahmen.py, Teil „anmeldung“ (Kopf, Marke, Kontrast hell und dunkel, Fokus).
"""

import inspect
import re

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.testclient import TestClient

from app.design_dateien import STATIC_DIR
from app.models import AppUser
from tests import vorlagen_js as vj
from tests.test_v441_rahmen_baustein import ANMELDUNG_UND_SPERRSEITE, UMGEZOGEN

UNTERTITEL = "Melde dich mit deinem Benutzernamen an."


def _app() -> TestClient:
    """Eine kleine App mit der Anmeldeseite und gesperrten Seiten hinter dem 403-Handler aus app/main.py (wie
    tests/test_v260_role_audit.py::test_403_on_a_page_route_renders_access_denied_html_not_json)."""
    from app.deps import require_admin
    from app.main import _role_check_403_shows_access_denied_page
    from app.permissions import ROLE_ADMIN, ROLE_OFFICE_AUFTRAG, require_min_role, require_role
    from app.routers.pages import templates

    app = FastAPI()
    app.add_exception_handler(HTTPException, _role_check_403_shows_access_denied_page)

    @app.middleware("http")
    async def _rolle(request: Request, call_next):
        rolle = request.headers.get("x-test-role")
        request.state.erp_user = (AppUser(username="x", display_name="x", role=rolle, active=True, password_hash="x")
                                  if rolle else None)
        return await call_next(request)

    @app.get("/login")
    def anmeldung(request: Request):
        return templates.TemplateResponse(request=request, name="login.html")

    @app.get("/nur-admin-rolle")
    def nur_admin_rolle(request: Request, _r: AppUser = Depends(require_role(ROLE_ADMIN))):
        return {"ok": True}

    @app.get("/ab-buero")
    def ab_buero(request: Request, _r: AppUser = Depends(require_min_role(ROLE_OFFICE_AUFTRAG))):
        return {"ok": True}

    @app.get("/nur-admin")
    def nur_admin(request: Request, _r: AppUser = Depends(require_admin())):
        return {"ok": True}

    return TestClient(app, raise_server_exceptions=False)


def _sichtbar(html: str) -> str:
    """Der sichtbare Text der Karte: ohne <style>, <script>, Jinja-Kommentare und Tags."""
    karte = html.split('<div class="card">', 1)[1].split("</body>", 1)[0]
    karte = re.sub(r"<(style|script)\b.*?</\1>", " ", karte, flags=re.S)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", karte)).strip()


def test_beide_seiten_sind_umgezogen():
    assert ANMELDUNG_UND_SPERRSEITE <= UMGEZOGEN
    for name in ANMELDUNG_UND_SPERRSEITE:
        assert re.search(r'<body class="ds-seite">', (vj.TEMPLATES / name).read_text(encoding="utf-8")), name
        assert vj.bindet_ein(name, "_marke.html", nur_selbst=True), name


def test_marke_ist_die_bildmarke_mit_schriftzug():
    marke = (vj.TEMPLATES / "_marke.html").read_text(encoding="utf-8")
    assert vj.bindet_ein("_marke.html", "_bildmarke.html", nur_selbst=True)
    assert '<span class="marke-name">DACHKONZEPTE</span><span class="marke-zusatz">Rödchen GmbH · ERP</span>' in marke
    # die Kachel weiß wie in Leiste und Monteurskopf, die Bildmarke darin; Regeln mit svg stehen im Baustein (ds.css nur .ds-…, Regel 37)
    assert re.search(r"\.marke-kachel\{[^}]*background:#FFFFFF", marke)
    assert ".marke" not in (STATIC_DIR / "ds" / "ds.css").read_text(encoding="utf-8")


def test_anmeldung_titel_und_untertitel():
    html = _app().get("/login").text
    assert html.index('class="marke"') < html.index('id="seitenkopf"') < html.index('id="u"')
    assert re.findall(r"<h1\b[^>]*>(.*?)</h1>", html) == ["Anmelden"]
    assert re.search(rf'<p class="ds-kopf-untertitel" id="seitenkopfUntertitel">{re.escape(UNTERTITEL)}</p>', html)
    assert "personengenaue" not in html
    assert "<svg" in html.split('class="marke"', 1)[1].split("</div>", 1)[0]
    # Benutzername, Passwort und der Knopf „Anmelden“ bleiben, wie sie waren
    for teil in ('<input id="u" autofocus>', '<input id="p" type="password"', '<button onclick="login()">Anmelden</button>'):
        assert teil in html, teil


def test_sperrseite_sagt_nichts_zweimal():
    client = _app()
    for adresse in ("/nur-admin-rolle", "/ab-buero"):
        r = client.get(adresse, headers={"x-test-role": "field"})
        assert r.status_code == 403, adresse
        assert re.findall(r"<h1\b[^>]*>(.*?)</h1>", r.text) == ["Kein Zugriff auf diese Seite"], adresse
        text = _sichtbar(r.text)
        # die allgemeine Meldung der Rollenprüfung sagte dasselbe wie der Titel -- sie fehlt, nichts steht doppelt
        assert "nicht verfügbar" not in text, (adresse, text)
        assert text.count("Zugriff") == 1, (adresse, text)
        assert text == ("DACHKONZEPTE Rödchen GmbH · ERP Kein Zugriff auf diese Seite Brauchst du sie, wende dich an eine Person mit "
                        "den passenden Rechten. Zur Startseite"), (adresse, text)


def test_sperrseite_zeigt_eine_genauere_meldung_einmal():
    r = _app().get("/nur-admin", headers={"x-test-role": "buero_auftrag"})
    assert r.status_code == 403
    text = _sichtbar(r.text)
    assert text.count("Diese Aktion ist nur für Administratoren verfügbar.") == 1, text
    assert text.index("Kein Zugriff auf diese Seite") < text.index("nur für Administratoren") < text.index("Brauchst du sie")


def test_zur_startseite_ist_die_gruene_hauptaktion():
    client = _app()
    r = client.get("/ab-buero", headers={"x-test-role": "field"})
    assert '<a class="ds-knopf ds-knopf-aktion" href="/mobil">Zur Startseite</a>' in r.text
    assert '<a class="ds-knopf ds-knopf-aktion" href="/">Zur Startseite</a>' in client.get("/ab-buero").text


def test_die_weggelassene_meldung_ist_die_vorgabe_der_rollenpruefung():
    """Die Sperrseite erkennt die allgemeine Meldung an ROLLE_NICHT_VERFUEGBAR -- genau der Vorgabe beider Rollenprüfungen; ändert sich
    der Wortlaut dort, wandert der Vergleich mit."""
    from app.permissions import ROLLE_NICHT_VERFUEGBAR, require_min_role, require_role
    assert inspect.signature(require_role).parameters["message"].default == ROLLE_NICHT_VERFUEGBAR
    assert inspect.signature(require_min_role).parameters["message"].default == ROLLE_NICHT_VERFUEGBAR
