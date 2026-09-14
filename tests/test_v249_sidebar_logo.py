"""Version 1.3.38/1.3.39/1.3.43 -- Firmenlogo in der Sidebar statt des Schriftzugs
"DACHKONZEPTE", Anzeigehöhe einstellbar (24-80px), seit 1.3.43 zusätzlich ein eigener,
dedizierter Sidebar-Logo-Upload.

**Korrektur zu 1.3.39/1.3.40** (siehe CLAUDE.md "Firmenlogo in der Sidebar"): die dort per
Bounding-Box-Auswertung des Alphakanals gestellte Diagnose "kein Schriftzug vorhanden" war
falsch -- die reale Datei zeigt "DACHKONZEPTE GmbH"/"RÖDCHEN" unterhalb des Dachzeichens, nur
räumlich zu nah am Bildzeichen, um automatisiert getrennt zu werden. Deshalb seit 1.3.43:
app/company_logo.py::sidebar_logo_filename() löst jetzt DREI Stufen auf (Sidebar-Logo ->
Firmenlogo -> Schriftzug) statt nur zwei, und liefert dafür ein SidebarLogoReference-NamedTuple
(source + stored_filename) statt eines nackten Strings -- der Aufrufer (sidebar_logo_url() in
app/routers/pages.py) braucht die Quelle, um die richtige Auslieferungsroute zu wählen
(Sidebar-Logo und Firmenlogo liegen in getrennten Ordnern hinter getrennten Endpunkten).

app/company_logo.py::sidebar_logo_filename()/sidebar_logo_height_px() werden hier isoliert
getestet (die eigentlichen "welches Logo"/"wie groß"-Entscheidungen), ebenso die beiden neuen
Router-Endpunkte für den Sidebar-Logo-Upload (POST/GET/DELETE .../sidebar-logo, über
router_test_client() -- das sind normale, per Depends(get_db) injizierte Endpunkte, anders als
die Jinja-Globals unten). Die Template-Logik (img vs. span, Höhe als Inline-Style) wird über
eine bare jinja2.Environment mit gestubbten Globals geprüft, exakt das bereits etablierte
Muster aus tests/test_v163_sidebar_login_status.py. Bewusst KEIN Ende-zu-Ende-Test über eine
echte Seite (router_test_client() für die SEITEN-Router): die REALE app/routers/pages.py-Fassung
der vier Jinja-Globals öffnet wie get_theme()/is_module_enabled() eine eigene SessionLocal()
gegen die echte Datenbankdatei (siehe CLAUDE.md, "Bekannte, bewusst offene Punkte") und lässt
sich deshalb nicht per Test-Session umstellen -- ein solcher Test würde nur zufällig den
aktuellen Inhalt der echten dachkonzepte_erp.db spiegeln. Deren Ausnahmesicherheit (seit 1.3.42)
wird stattdessen in tests/test_v252_deployment_hardening.py direkt gegen die Modulfunktionen
geprüft.

Kein echter Browser-Screenshot möglich (kein Automatisierungswerkzeug in dieser Umgebung) --
dass ein breites Logo bei fester Höhe rechts abgeschnitten wird (.app-sidebar-logo-wrap,
overflow:hidden) statt die Höhe zu verkleinern, ist deshalb nur an der Markup-/CSS-Struktur
geprüft (der Wrapper trägt max-width+overflow:hidden, das <img> selbst KEIN max-width mehr --
genau das war der reale, in 1.3.39 gefundene und behobene Fehler: <img> mit sowohl fester Höhe
als auch max-width verkleinert bei einem breiten Bild die Höhe wieder, weil die
Ersatzelement-Breiten/Höhen-Auflösung die feste Höhe verwirft, sobald max-width eingreift)."""

from pathlib import Path

import jinja2

from app import company_logo
from app.settings import get_or_create_general_settings


# ---------------------------------------------------------------------------
# company_logo.sidebar_logo_filename() -- welches Logo liefert die Funktion, in welcher Stufe
# ---------------------------------------------------------------------------

def test_sidebar_logo_filename_none_when_nothing_set(db_session):
    assert company_logo.sidebar_logo_filename(db_session) is None


def test_sidebar_logo_filename_falls_back_to_company_logo_when_no_sidebar_logo_set(db_session, tmp_path, monkeypatch):
    monkeypatch.setattr(company_logo, "LOGO_ROOT", tmp_path / "company_logo")
    stored = company_logo.replace_logo(None, "logo.png", b"Bildinhalt")
    settings = get_or_create_general_settings(db_session)
    settings.logo_filename = stored
    db_session.commit()

    ref = company_logo.sidebar_logo_filename(db_session)
    assert ref == company_logo.SidebarLogoReference("company", stored)


def test_sidebar_logo_filename_prefers_dedicated_sidebar_logo_over_company_logo(db_session, tmp_path, monkeypatch):
    monkeypatch.setattr(company_logo, "LOGO_ROOT", tmp_path / "company_logo")
    monkeypatch.setattr(company_logo, "SIDEBAR_LOGO_ROOT", tmp_path / "sidebar_logo")
    company_stored = company_logo.replace_logo(None, "logo.png", b"Firmenlogo-Bildinhalt")
    sidebar_stored = company_logo.replace_sidebar_logo(None, "sidebar.png", b"Sidebar-Logo-Bildinhalt")
    settings = get_or_create_general_settings(db_session)
    settings.logo_filename = company_stored
    settings.sidebar_logo_filename = sidebar_stored
    db_session.commit()

    ref = company_logo.sidebar_logo_filename(db_session)
    assert ref == company_logo.SidebarLogoReference("sidebar", sidebar_stored)


def test_sidebar_logo_filename_falls_back_to_company_logo_when_sidebar_file_missing(db_session, tmp_path, monkeypatch):
    """Verteidigung in der Tiefe: ein Datenbankeintrag ohne zugehörige Datei (z. B. nach einem
    von Hand gelöschten Ordner) fällt auf die nächste Stufe zurück, statt zu einem defekten
    <img> zu führen."""
    monkeypatch.setattr(company_logo, "LOGO_ROOT", tmp_path / "company_logo")
    monkeypatch.setattr(company_logo, "SIDEBAR_LOGO_ROOT", tmp_path / "sidebar_logo")
    company_stored = company_logo.replace_logo(None, "logo.png", b"Firmenlogo-Bildinhalt")
    settings = get_or_create_general_settings(db_session)
    settings.logo_filename = company_stored
    settings.sidebar_logo_filename = "nie-hochgeladen.png"
    db_session.commit()

    ref = company_logo.sidebar_logo_filename(db_session)
    assert ref == company_logo.SidebarLogoReference("company", company_stored)


def test_sidebar_logo_filename_none_when_file_missing_despite_db_entry(db_session, tmp_path, monkeypatch):
    """Wie oben, aber ohne jede zweite Stufe -- fällt bis auf den Schriftzug (None) zurück."""
    monkeypatch.setattr(company_logo, "LOGO_ROOT", tmp_path / "company_logo")
    settings = get_or_create_general_settings(db_session)
    settings.logo_filename = "nie-hochgeladen.png"
    db_session.commit()

    assert company_logo.sidebar_logo_filename(db_session) is None


# ---------------------------------------------------------------------------
# Router: POST/GET/DELETE /api/settings/general/sidebar-logo -- eigener Upload, eigener Ordner
# ---------------------------------------------------------------------------

def _make_png_bytes(size=(300, 60)):
    from io import BytesIO

    from PIL import Image

    buf = BytesIO()
    Image.new("RGBA", size, (10, 90, 40, 255)).save(buf, format="PNG")
    return buf.getvalue()


def test_upload_view_and_remove_sidebar_logo_over_real_routes(threaded_db_session, router_test_client, tmp_path, monkeypatch):
    monkeypatch.setattr(company_logo, "SIDEBAR_LOGO_ROOT", tmp_path / "sidebar_logo")
    from app.routers.settings import router as settings_router
    client = router_test_client(threaded_db_session, settings_router)

    upload_resp = client.post(
        "/api/settings/general/sidebar-logo",
        files={"file": ("sidebar-logo.png", _make_png_bytes(), "image/png")},
    )
    assert upload_resp.status_code == 200
    stored = upload_resp.json()["sidebar_logo_filename"]
    assert stored

    view_resp = client.get("/api/settings/general/sidebar-logo")
    assert view_resp.status_code == 200
    assert view_resp.headers["cache-control"] == "private, max-age=31536000, immutable"

    remove_resp = client.delete("/api/settings/general/sidebar-logo")
    assert remove_resp.status_code == 200
    assert remove_resp.json()["sidebar_logo_filename"] is None
    assert client.get("/api/settings/general/sidebar-logo").status_code == 404


def test_sidebar_logo_upload_does_not_touch_company_logo_folder(threaded_db_session, router_test_client, tmp_path, monkeypatch):
    """Beide Uploads liegen in eigenen, unabhängigen Ordnern -- ein Sidebar-Logo-Upload darf
    ein bereits hinterlegtes Firmenlogo nicht berühren."""
    monkeypatch.setattr(company_logo, "LOGO_ROOT", tmp_path / "company_logo")
    monkeypatch.setattr(company_logo, "SIDEBAR_LOGO_ROOT", tmp_path / "sidebar_logo")
    from app.routers.settings import router as settings_router
    client = router_test_client(threaded_db_session, settings_router)

    company_resp = client.post(
        "/api/settings/general/logo",
        files={"file": ("logo.png", _make_png_bytes((200, 200)), "image/png")},
    )
    assert company_resp.status_code == 200
    company_filename = company_resp.json()["logo_filename"]

    sidebar_resp = client.post(
        "/api/settings/general/sidebar-logo",
        files={"file": ("sidebar-logo.png", _make_png_bytes(), "image/png")},
    )
    assert sidebar_resp.status_code == 200
    assert sidebar_resp.json()["logo_filename"] == company_filename  # unveraendert
    assert client.get("/api/settings/general/logo").status_code == 200
    assert client.get("/api/settings/general/sidebar-logo").status_code == 200


# ---------------------------------------------------------------------------
# company_logo.sidebar_logo_height_px() -- wie groß liefert die Funktion
# ---------------------------------------------------------------------------

def test_sidebar_logo_height_px_default_is_64(db_session):
    """Seit 1.3.44 (siehe CLAUDE.md "Umgestaltung der Sidebar") -- der Kopfbereich teilt sich
    nicht mehr mit den beiden Kopfzeilen-Schaltflächen, ein größerer Standardwert wirkt dadurch
    nicht mehr gedrängt."""
    assert company_logo.sidebar_logo_height_px(db_session) == 64


def test_sidebar_logo_height_px_returns_configured_value(db_session):
    settings = get_or_create_general_settings(db_session)
    settings.sidebar_logo_height_px = 90
    db_session.commit()

    assert company_logo.sidebar_logo_height_px(db_session) == 90


def test_sidebar_logo_height_px_clamps_out_of_range_value(db_session):
    """Verteidigung in der Tiefe: ein Wert außerhalb 24-120 (z. B. durch einen direkten
    Datenbankzugriff, das Feld selbst hat keine DB-seitige Prüfung) darf die Sidebar nicht
    absurd groß/klein machen."""
    settings = get_or_create_general_settings(db_session)
    settings.sidebar_logo_height_px = 500
    db_session.commit()
    assert company_logo.sidebar_logo_height_px(db_session) == company_logo.MAX_SIDEBAR_LOGO_HEIGHT_PX

    settings.sidebar_logo_height_px = 1
    db_session.commit()
    assert company_logo.sidebar_logo_height_px(db_session) == company_logo.MIN_SIDEBAR_LOGO_HEIGHT_PX


def test_sidebar_logo_height_px_bounds_are_24_to_120():
    """Seit 1.3.44 auf 120px angehoben (vorher 80), siehe CLAUDE.md "Umgestaltung der
    Sidebar" -- ein Logo mit Schriftzug soll bei ausreichender Höhe lesbar sein."""
    assert company_logo.MIN_SIDEBAR_LOGO_HEIGHT_PX == 24
    assert company_logo.MAX_SIDEBAR_LOGO_HEIGHT_PX == 120


# ---------------------------------------------------------------------------
# _sidebar.html -- img statt Schriftzug, je nach sidebar_logo_url(); Höhe als Inline-Style
# ---------------------------------------------------------------------------

class _FakeURL:
    def __init__(self, path):
        self.path = path


class _FakeState:
    def __init__(self, user):
        self.erp_user = user


class _FakeRequest:
    def __init__(self, path, user=None):
        self.url = _FakeURL(path)
        self.state = _FakeState(user)


class _FakeUser:
    role = "admin"
    display_name = "Test Nutzer"


def _render(logo_url, height=48):
    root = Path(__file__).parents[1]
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(root / "app" / "templates")))
    env.globals["get_theme"] = lambda: {"accent_color": "#0d9488"}
    env.globals["is_module_enabled"] = lambda key: True
    env.globals["sidebar_logo_url"] = lambda: logo_url
    env.globals["sidebar_logo_height_px"] = lambda: height
    tmpl = env.get_template("project_folder.html")  # eine beliebige Seite, die _sidebar.html einbindet
    return tmpl.render(request=_FakeRequest("/x", _FakeUser()), app_version="1.0.0", project_id=1)


def test_sidebar_shows_wordmark_when_no_logo():
    html = _render(None)
    assert '<span class="app-sidebar-brand">DACHKONZEPTE</span>' in html
    # Nicht auf "app-sidebar-logo" insgesamt prüfen -- die CSS-Regel dafür steht immer im
    # <style>-Block, unabhängig davon, ob das <img> tatsächlich gerendert wird.
    assert '<img class="app-sidebar-logo"' not in html


def test_sidebar_shows_logo_image_when_present():
    html = _render("/api/settings/general/logo?v=abc123.png")
    assert 'class="app-sidebar-logo"' in html
    assert 'src="/api/settings/general/logo?v=abc123.png"' in html
    assert '<span class="app-sidebar-brand">DACHKONZEPTE</span>' not in html


def test_sidebar_logo_uses_configured_height_as_inline_style():
    html = _render("/api/settings/general/logo?v=abc123.png", height=64)
    assert 'style="height:64px"' in html


def test_sidebar_logo_wrapped_in_width_limiting_clip_container_not_on_img_itself():
    """Der reale, in 1.3.39 gefundene Fehler: ein <img> mit sowohl fester Höhe ALS AUCH
    max-width verkleinert bei einem breiten Logo die Höhe wieder (die
    Ersatzelement-Breiten/Höhen-Auflösung verwirft die feste Höhe, sobald max-width
    eingreift). Die Breitenbegrenzung muss deshalb auf einem umschließenden Element sitzen,
    das <img> selbst darf kein max-width/max-height tragen."""
    html = _render("/api/settings/general/logo?v=abc123.png")
    assert '<span class="app-sidebar-logo-wrap"><img class="app-sidebar-logo"' in html
    img_tag = html[html.index('<img class="app-sidebar-logo"'):]
    img_tag = img_tag[:img_tag.index(">") + 1]
    assert "max-width" not in img_tag
    assert "max-height" not in img_tag
