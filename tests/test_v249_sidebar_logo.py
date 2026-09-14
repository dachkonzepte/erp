"""Version 1.3.38 -- Firmenlogo in der Sidebar statt des Schriftzugs "DACHKONZEPTE".

Kein zweiter, eigener Sidebar-Logo-Upload (siehe CLAUDE.md "Firmenlogo in der Sidebar") --
_sidebar.html zeigt heute dasselbe Firmenlogo, das bereits für PDF-Dokumente/das PWA-Icon
existiert (app/company_logo.py). Ist keins hinterlegt, bleibt der Schriftzug.

app/company_logo.py::sidebar_logo_filename() wird hier isoliert getestet (die eigentliche
"welches Logo"-Entscheidung); die Template-Logik (img vs. span) wird über eine bare
jinja2.Environment mit gestubbtem sidebar_logo_url() geprüft, exakt das bereits etablierte
Muster aus tests/test_v163_sidebar_login_status.py. Bewusst KEIN Ende-zu-Ende-Test über eine
echte Seite (router_test_client()): die REALE app/routers/pages.py-Fassung von
sidebar_logo_url() öffnet wie get_theme()/is_module_enabled() eine eigene SessionLocal()
gegen die echte Datenbankdatei (siehe CLAUDE.md, "Bekannte, bewusst offene Punkte") und lässt
sich deshalb nicht per Test-Session umstellen -- ein solcher Test würde nur zufällig den
aktuellen Inhalt der echten dachkonzepte_erp.db spiegeln und bei einem später tatsächlich
hochgeladenen Logo ohne jede Codeänderung fehlschlagen.
"""

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
# _sidebar.html -- img statt Schriftzug, je nach sidebar_logo_url()
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


def _render(logo_url):
    root = Path(__file__).parents[1]
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(root / "app" / "templates")))
    env.globals["get_theme"] = lambda: {"accent_color": "#0d9488"}
    env.globals["is_module_enabled"] = lambda key: True
    env.globals["sidebar_logo_url"] = lambda: logo_url
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
