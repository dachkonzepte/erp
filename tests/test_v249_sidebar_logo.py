"""Version 1.3.38/1.3.39 -- Firmenlogo in der Sidebar statt des Schriftzugs "DACHKONZEPTE",
Anzeigehöhe einstellbar (24-80px).

Kein zweiter, eigener Sidebar-Logo-Upload (siehe CLAUDE.md "Firmenlogo in der Sidebar") --
_sidebar.html zeigt heute dasselbe Firmenlogo, das bereits für PDF-Dokumente/das PWA-Icon
existiert (app/company_logo.py). Ist keins hinterlegt, bleibt der Schriftzug.

app/company_logo.py::sidebar_logo_filename()/sidebar_logo_height_px() werden hier isoliert
getestet (die eigentlichen "welches Logo"/"wie groß"-Entscheidungen); die Template-Logik
(img vs. span, Höhe als Inline-Style) wird über eine bare jinja2.Environment mit gestubbten
Globals geprüft, exakt das bereits etablierte Muster aus tests/test_v163_sidebar_login_status.py.
Bewusst KEIN Ende-zu-Ende-Test über eine echte Seite (router_test_client()): die REALE
app/routers/pages.py-Fassung dieser Globals öffnet wie get_theme()/is_module_enabled() eine
eigene SessionLocal() gegen die echte Datenbankdatei (siehe CLAUDE.md, "Bekannte, bewusst offene
Punkte") und lässt sich deshalb nicht per Test-Session umstellen -- ein solcher Test würde nur
zufällig den aktuellen Inhalt der echten dachkonzepte_erp.db spiegeln und bei einem später
tatsächlich hochgeladenen Logo ohne jede Codeänderung fehlschlagen.

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
# company_logo.sidebar_logo_filename() -- welches Logo liefert die Funktion
# ---------------------------------------------------------------------------

def test_sidebar_logo_filename_none_when_no_logo_set(db_session):
    assert company_logo.sidebar_logo_filename(db_session) is None


def test_sidebar_logo_filename_returns_filename_when_file_exists(db_session, tmp_path, monkeypatch):
    monkeypatch.setattr(company_logo, "LOGO_ROOT", tmp_path / "company_logo")
    stored = company_logo.replace_logo(None, "logo.png", b"Bildinhalt")
    settings = get_or_create_general_settings(db_session)
    settings.logo_filename = stored
    db_session.commit()

    assert company_logo.sidebar_logo_filename(db_session) == stored


def test_sidebar_logo_filename_none_when_file_missing_despite_db_entry(db_session, tmp_path, monkeypatch):
    """Verteidigung in der Tiefe: ein Datenbankeintrag ohne zugehörige Datei (z. B. nach
    einem von Hand gelöschten Ordner) soll zum Schriftzug zurückfallen, nicht zu einem
    defekten <img>."""
    monkeypatch.setattr(company_logo, "LOGO_ROOT", tmp_path / "company_logo")
    settings = get_or_create_general_settings(db_session)
    settings.logo_filename = "nie-hochgeladen.png"
    db_session.commit()

    assert company_logo.sidebar_logo_filename(db_session) is None


# ---------------------------------------------------------------------------
# company_logo.sidebar_logo_height_px() -- wie groß liefert die Funktion
# ---------------------------------------------------------------------------

def test_sidebar_logo_height_px_default_is_48(db_session):
    assert company_logo.sidebar_logo_height_px(db_session) == 48


def test_sidebar_logo_height_px_returns_configured_value(db_session):
    settings = get_or_create_general_settings(db_session)
    settings.sidebar_logo_height_px = 64
    db_session.commit()

    assert company_logo.sidebar_logo_height_px(db_session) == 64


def test_sidebar_logo_height_px_clamps_out_of_range_value(db_session):
    """Verteidigung in der Tiefe: ein Wert außerhalb 24-80 (z. B. durch einen direkten
    Datenbankzugriff, das Feld selbst hat keine DB-seitige Prüfung) darf die Sidebar nicht
    absurd groß/klein machen."""
    settings = get_or_create_general_settings(db_session)
    settings.sidebar_logo_height_px = 500
    db_session.commit()
    assert company_logo.sidebar_logo_height_px(db_session) == company_logo.MAX_SIDEBAR_LOGO_HEIGHT_PX

    settings.sidebar_logo_height_px = 1
    db_session.commit()
    assert company_logo.sidebar_logo_height_px(db_session) == company_logo.MIN_SIDEBAR_LOGO_HEIGHT_PX


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
