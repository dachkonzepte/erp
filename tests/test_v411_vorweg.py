"""Version 1.8.106 -- Vorweg der zweiten Vorgabe vom 14.10.2026 (Korrekturen zu den Festlegungen 1.8.101–1.8.103).

    101-4  Auch das SVG-Logo kommt mit Sandbox, wenn man seine Adresse direkt öffnet -- so seit 1.8.101 (app/dateiauslieferung.py),
           hier über die echte Route und die echte Anmeldeschranke festgehalten.
    102-2  Jedes Feld "id"/"…_id" mit Text steht in TEXT_IDS (tests/vorlagen_html.py): statisch über alle Spalten und alle
           Pydantic-Modelle in app/ (tests/test_v407_daten_im_html.py), hier zur Laufzeit über die JSON-Antworten aller GET-Routen.
    103-2  Beendet ein Administrator die Sitzungen eines Benutzers, meldet das auch alle seine vertrauten Geräte ab.
    103-3  Feierabend als POST (POST /api/field-view/feierabend); GET /api/field-view/today schreibt nichts mehr -- die Ausnahme von
           Regel 23 entfällt.

Sitzungstests über die echte Anmeldeschranke (tests/anmeldung.py, Welt aus tests/test_v402_sitzungen.py). Gegenproben:
docs/archiv/befund-vor-echtbetrieb.md, "Umsetzung 1.8.106"."""

from __future__ import annotations

import re
from datetime import datetime, timedelta

import pytest
from sqlalchemy import event, select

from app import device_trust
from app.auth import COOKIE_NAME
from app.models import AppUser, TrustedDevice
from app.routers import account as account_router
from app.routers import auth as auth_router
from app.routers import field_view as field_view_router
from app.routers import settings as settings_router
from app.routers import users as users_router
from tests.anmeldung import app_mit_schranke, neue_datenbank
from tests.test_v326_monteur_datengrenze import durchlauf, durchlauf_admin, durchlauf_luecken  # noqa: F401 -- Fixtures
from tests.test_v314_dashboard_month_berlin import NODE, _node
from tests.test_v402_sitzungen import PASSWORT, Welt, _status, _wert
from tests.test_v406_dateien_nie_aktiv import SVG
from tests.test_v408_vorweg import _probe
from tests.vorlagen_html import TEXT_IDS

nur_mit_node = pytest.mark.skipif(NODE is None, reason="node nicht gefunden")
FEIERABEND = datetime.combine(datetime.today(), datetime.min.time()) + timedelta(hours=20)
MITTAG = datetime.combine(datetime.today(), datetime.min.time()) + timedelta(hours=12)


class WeltMitLogo(Welt):
    def __init__(self, engine, make_session):
        super().__init__(make_session)
        self.engine = engine
        self.app = app_mit_schranke(make_session, auth_router.router, account_router.router, users_router.router,
                                    field_view_router.router, settings_router.router, _probe)

    def vertrauen(self, user: AppUser) -> str:
        """Ein vertrautes Gerät für user (wie "Diesem Gerät 30 Tage vertrauen") -- der Wert des Cookies."""
        with self.make_session() as db:
            return device_trust.create_trust(db, db.get(AppUser, user.id))

    def vertraute_geraete(self, user: AppUser) -> int:
        with self.make_session() as db:
            return len(db.scalars(select(TrustedDevice).where(TrustedDevice.user_id == user.id)).all())

    def anmelden_mit_vertrauen(self, name: str, vertrauen: str) -> dict:
        """Anmelden auf einem Gerät mit dem Cookie "vertrautes Gerät" -- die Antwort sagt, ob der zweite Faktor erspart bleibt."""
        c = self.client()
        c.cookies.set(device_trust.TRUST_COOKIE_NAME, vertrauen, domain="testserver.local")
        antwort = c.post("/api/auth/login", json={"username": name, "password": PASSWORT})
        assert antwort.status_code == 200, antwort.text
        return antwort.json()


@pytest.fixture
def welt():
    engine, make_session = neue_datenbank()
    yield WeltMitLogo(engine, make_session)
    engine.dispose()


def _direktiven(csp: str) -> dict:
    return {teile[0].lower(): teile[1:] for teile in (d.split() for d in csp.split(";")) if teile}


# ---------------------------------------------------------------------------
# 101-4: das SVG-Logo direkt geöffnet -- Download mit Sandbox
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("pfad", ["/api/settings/general/logo", "/api/settings/general/sidebar-logo"])
def test_svg_logo_direkt_geoeffnet_kommt_mit_sandbox(welt, pfad):
    anna = welt.benutzer("anna", "admin", zweiter_faktor=True)
    c = welt.als(anna)
    assert c.post(pfad, files={"file": ("logo.svg", SVG, "image/svg+xml")}).status_code == 200
    antwort = c.get(pfad)
    assert antwort.headers["content-type"].startswith("image/svg+xml")
    assert antwort.headers["content-disposition"].startswith("attachment")
    assert antwort.headers["x-content-type-options"] == "nosniff"
    d = _direktiven(antwort.headers["content-security-policy"])
    # sandbox ohne allow-…: kein Skript, kein Formular, eigener (undurchsichtiger) Ursprung statt dem des ERP
    assert d.get("sandbox") == [] and not any(k.startswith("allow-") for k in d)
    assert d["default-src"] == ["'none'"] and "script-src" not in d
    assert d["frame-ancestors"] == ["'none'"]  # von der Anmeldeschranke angehängt, nicht ersetzt


# ---------------------------------------------------------------------------
# 102-2: zur Laufzeit -- jede Antwort aller GET-Routen
# ---------------------------------------------------------------------------

def _text_ids(wert, out: dict, route: str) -> None:
    if isinstance(wert, dict):
        for k, v in wert.items():
            if (k == "id" or k.endswith("_id")) and isinstance(v, str):
                out.setdefault(k, set()).add(route)
            _text_ids(v, out, route)
    elif isinstance(wert, list):
        for x in wert:
            _text_ids(x, out, route)


def test_jedes_id_feld_mit_text_in_den_antworten_steht_in_text_ids(durchlauf, durchlauf_admin, durchlauf_luecken):  # noqa: F811
    """Die drei Rundgänge aus test_v326 (Monteurin, Administratorin, Daten mit Lücken): jeder Schlüssel "id"/"…_id", dessen Wert in
    einer JSON-Antwort Text ist, steht in TEXT_IDS -- auch wo die Antwort ein dict ist, kein Antwortschema."""
    gefunden, routen = {}, set()
    for d in (durchlauf, durchlauf_admin, durchlauf_luecken):
        for a in d["antworten"]:
            if a["body"] is not None:
                routen.add(a["route"])
                _text_ids(a["body"], gefunden, a["route"])
    assert len(routen) > 150  # der Rundgang trifft die Routen mit Inhalt
    assert {"entity_id", "external_id"} <= set(gefunden)  # Text-IDs, die die Testdaten füllen
    fehlen = {k: sorted(v)[:3] for k, v in gefunden.items() if k not in TEXT_IDS}
    assert fehlen == {}, f"Feld mit Text unter dem Namen einer ID, nicht in TEXT_IDS: {fehlen}"


# ---------------------------------------------------------------------------
# 103-2: "Alle Sitzungen beenden" meldet auch die vertrauten Geräte ab
# ---------------------------------------------------------------------------

def test_admin_beendet_sitzungen_und_vertraute_geraete_eines_benutzers(welt):
    anna = welt.benutzer("anna", "admin", zweiter_faktor=True)
    bert = welt.benutzer("bert", "admin", zweiter_faktor=True)
    vertrauen = welt.vertrauen(bert)
    assert welt.anmelden_mit_vertrauen("bert", vertrauen)["otp_ok"] is True  # vorher erspart das Gerät den zweiten Faktor
    tablet = welt.als(bert)
    admin = welt.als(anna)
    liste = {u["username"]: u for u in admin.get("/api/users").json()}
    assert liste["bert"]["trusted_device_count"] == 1 and liste["anna"]["trusted_device_count"] == 0

    antwort = admin.post(f"/api/users/{bert.id}/end-sessions")
    assert antwort.status_code == 200
    assert antwort.json()["geraete_abgemeldet"] == 1 and antwort.json()["sitzungen_beendet"] == 2
    assert welt.vertraute_geraete(bert) == 0 and welt.sitzungen_von(bert) == 0
    assert _status(welt, _wert(tablet)) == 401
    # Angriffstest: das Cookie des vertrauten Geräts erspart den zweiten Faktor nicht mehr
    assert welt.anmelden_mit_vertrauen("bert", vertrauen)["otp_ok"] is False
    assert admin.get("/api/users").json()[0]["trusted_device_count"] == 0


def test_eigene_sitzungen_beenden_meldet_auch_dieses_vertraute_geraet_ab(welt):
    anna = welt.benutzer("anna", "admin", zweiter_faktor=True)
    vertrauen = welt.vertrauen(anna)
    hier, dort = welt.als(anna), welt.als(anna)
    hier.cookies.set(device_trust.TRUST_COOKIE_NAME, vertrauen, domain="testserver.local")
    antwort = hier.post(f"/api/users/{anna.id}/end-sessions")
    assert antwort.status_code == 200 and antwort.json()["geraete_abgemeldet"] == 1
    gesetzt = antwort.headers.get_list("set-cookie")
    assert any(z.startswith(device_trust.TRUST_COOKIE_NAME + '=""') or z.startswith(device_trust.TRUST_COOKIE_NAME + "=;")
               for z in gesetzt), gesetzt  # das Cookie dieses Geräts ist gelöscht
    assert hier.get("/api/probe").status_code == 200  # dieses Gerät bleibt angemeldet (neue Sitzung)
    assert _status(welt, _wert(dort)) == 401
    assert welt.vertraute_geraete(anna) == 0
    assert welt.anmelden_mit_vertrauen("anna", vertrauen)["otp_ok"] is False


def test_auch_ohne_sitzungen_meldet_der_admin_die_vertrauten_geraete_ab(welt):
    anna = welt.benutzer("anna", "admin", zweiter_faktor=True)
    bert = welt.benutzer("bert", "admin", zweiter_faktor=True)
    welt.vertrauen(bert)
    admin = welt.als(anna)
    assert admin.post(f"/api/users/{bert.id}/end-sessions").json() == {"ok": True, "sitzungen_beendet": 0, "geraete_abgemeldet": 1}
    assert welt.vertraute_geraete(bert) == 0


# ---------------------------------------------------------------------------
# 103-3: Feierabend als POST, der GET schreibt nichts
# ---------------------------------------------------------------------------

def _schreibt(welt, aufruf) -> list[str]:
    """Die schreibenden SQL-Anweisungen während aufruf()."""
    geschrieben = []

    def merken(conn, cursor, statement, params, context, executemany):
        if re.match(r"\s*(INSERT|UPDATE|DELETE)\b", statement, re.I):
            geschrieben.append(statement.split("\n")[0][:80])

    event.listen(welt.engine, "before_cursor_execute", merken)
    try:
        aufruf()
    finally:
        event.remove(welt.engine, "before_cursor_execute", merken)
    return geschrieben


def test_der_get_nach_feierabend_schreibt_nichts(welt, monkeypatch):
    welt.benutzer("mia", "field")
    geraet = welt.angemeldet("mia")
    monkeypatch.setattr(field_view_router, "_now", lambda: FEIERABEND)
    antworten = []
    assert _schreibt(welt, lambda: antworten.append(geraet.get("/api/field-view/today"))) == []
    antwort = antworten[0]
    assert antwort.status_code == 401 and antwort.json() == {"detail": "Feierabend -- bitte erneut anmelden.", "feierabend": True}
    assert not any(z.startswith(COOKIE_NAME + "=") for z in antwort.headers.get_list("set-cookie"))
    assert _status(welt, _wert(geraet)) == 200  # die Sitzung steht noch -- beenden tut der POST


def test_der_post_nach_feierabend_beendet_nur_diese_sitzung(welt, monkeypatch):
    mia = welt.benutzer("mia", "field")
    geraet, anderes = welt.angemeldet("mia"), welt.angemeldet("mia")
    wert, wert_anderes = _wert(geraet), _wert(anderes)
    monkeypatch.setattr(field_view_router, "_now", lambda: FEIERABEND)
    antwort = geraet.post("/api/field-view/feierabend")
    assert antwort.status_code == 200
    assert any(z.startswith(COOKIE_NAME + "=") for z in antwort.headers.get_list("set-cookie"))  # Cookie gelöscht
    # Angriffstest: der Wert des Tablets von außen -- auf dem Server beendet
    assert _status(welt, wert) == 401
    assert _status(welt, wert_anderes) == 200 and welt.sitzungen_von(mia) == 1


def test_der_post_vor_dem_feierabend_aendert_nichts(welt, monkeypatch):
    welt.benutzer("mia", "field")
    geraet = welt.angemeldet("mia")
    monkeypatch.setattr(field_view_router, "_now", lambda: MITTAG)
    antwort = geraet.post("/api/field-view/feierabend")
    assert antwort.status_code == 409 and "Noch kein Feierabend" in antwort.json()["detail"]
    assert _status(welt, _wert(geraet)) == 200


def test_feierabend_von_einer_fremden_seite_abgelehnt(welt, monkeypatch):
    """Der POST ist eine schreibende Anfrage wie jede andere (Regel 33): von einer fremden Seite 403, die Sitzung bleibt."""
    welt.benutzer("mia", "field")
    geraet = welt.angemeldet("mia")
    monkeypatch.setattr(field_view_router, "_now", lambda: FEIERABEND)
    antwort = geraet.post("/api/field-view/feierabend", headers={"Sec-Fetch-Site": "cross-site", "Origin": "https://boese.example"})
    assert antwort.status_code == 403
    assert _status(welt, _wert(geraet)) == 200


def _mobil() -> str:
    from tests.vorlagen_js import TEMPLATES
    return (TEMPLATES / "mobil.html").read_text(encoding="utf-8")


def test_mobil_meldet_nach_feierabend_per_post_ab():
    """mobil.html: auf "feierabend" aus dem GET folgt der POST über speichern() (Regel 29)."""
    text = _mobil()
    assert "if(d&&d.feierabend)return feierabend();" in text
    assert "return speichern('feierabend',()=>fetch('/api/field-view/feierabend',{method:'POST'}))" in text


@nur_mit_node
@pytest.mark.parametrize("antwort, navigiert, meldung", [
    ("{ok:true,status:200,json:async()=>({ok:true})}", True, None),
    ("{ok:false,status:401,json:async()=>({detail:'Anmeldung abgelaufen'})}", True, None),  # Sitzung schon weg -- keine Schleife
    ("{ok:false,status:403,json:async()=>({detail:'Anfrage von einer fremden Seite abgelehnt.'})}", False,
     "Anfrage von einer fremden Seite abgelehnt."),
    ("{ok:false,status:409,json:async()=>({detail:'Noch kein Feierabend -- die Anmeldung bleibt bestehen.'})}", False, "Noch kein Feierabend"),
    ("{ok:false,status:502,json:async()=>{throw new Error('kein JSON')}}", False, "HTTP 502."),
    ("Promise.reject(new Error('Failed to fetch'))", False, "Failed to fetch"),
])
def test_mobil_geht_nur_mit_beendeter_sitzung_zur_anmeldung(antwort, navigiert, meldung):
    """Angriffs-/Ausfalltest in node: scheitert der POST (403 von einem alten Tablet ohne Sec-Fetch-Site, Netz weg, Server), bleibt
    /mobil mit der Meldung stehen -- mit der noch gültigen Sitzung schickte /login sonst sofort zurück nach /mobil, die Seite liefe im
    Kreis (so in der Gegenprobe ohne POST beobachtet)."""
    text = _mobil()
    # seit 1.9.45 („Heute“) folgt auf feierabend() das Laden über lesen() (ladeHeute()), bis dahin der direkte fetch()
    js = text[text.index("  function feierabendFehler(text){"):text.index("  // Seit 1.9.45 über lesen()")]
    script = ("const location={pathname:'/mobil',href:''};const fehler=[];function showError(m){fehler.push(m)}\n"
              "const gesendet=[];function fetch(u,o){gesendet.push([u,(o||{}).method]);return Promise.resolve(" + antwort + ")}\n"
              "async function speichern(b,f){return await f()}\n" + js
              + "\nfeierabend().then(()=>process.stdout.write(JSON.stringify({href:location.href,fehler,gesendet})))")
    ergebnis = _node(script, "Europe/Berlin")
    assert ergebnis["gesendet"] == [["/api/field-view/feierabend", "POST"]]
    assert ergebnis["href"] == ("/login?next=%2Fmobil" if navigiert else "")
    if meldung is None:
        assert ergebnis["fehler"] == []
    else:
        assert len(ergebnis["fehler"]) == 1 and meldung in ergebnis["fehler"][0] and "Abmelden fehlgeschlagen" in ergebnis["fehler"][0]


