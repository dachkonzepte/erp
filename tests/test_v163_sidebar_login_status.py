from pathlib import Path

import jinja2
from html.parser import HTMLParser


class BalanceChecker(HTMLParser):
    VOID = {"meta", "link", "br", "img", "input", "hr", "source", "area", "base", "col", "embed", "track", "wbr"}

    def __init__(self):
        super().__init__()
        self.stack = []
        self.errors = []

    def handle_starttag(self, tag, attrs):
        if tag not in self.VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag in self.VOID:
            return
        if not self.stack:
            self.errors.append(f"</{tag}> ohne offen")
            return
        if self.stack[-1] == tag:
            self.stack.pop()
        elif tag in self.stack:
            self.errors.append(f"</{tag}> falsch verschachtelt")
            while self.stack and self.stack[-1] != tag:
                self.stack.pop()
            if self.stack:
                self.stack.pop()
        else:
            self.errors.append(f"</{tag}> kein passendes")


class FakeURL:
    def __init__(self, path):
        self.path = path


class FakeState:
    def __init__(self, user):
        self.erp_user = user


class FakeRequest:
    def __init__(self, path, user=None):
        self.url = FakeURL(path)
        self.state = FakeState(user)


class FakeUser:
    def __init__(self, role="admin"):
        self.role = role
        self.display_name = "Test Nutzer"


def _render(user):
    root = Path(__file__).parents[1]
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(root / "app" / "templates")))
    # Seiten rufen inzwischen alle {{ get_theme().accent_color }} für das
    # anpassbare Design auf -- in der echten App liefert app/routers/pages.py
    # dieses Jinja-Global live aus general_settings, hier reicht ein Stub.
    env.globals["get_theme"] = lambda: {"accent_color": "#0d9488"}
    # _sidebar.html prüft seit 1.0.103 zusätzlich is_module_enabled() für optionale
    # Module (siehe app/modules.py) -- ebenfalls nur ein Stub, echtes Verhalten wird
    # in tests/test_v197_module_toggle.py getestet.
    env.globals["is_module_enabled"] = lambda key: True
    # _sidebar.html zeigt seit 1.3.38 statt des Schriftzugs ein Logo, falls eines hinterlegt
    # ist (app/company_logo.py::sidebar_logo_filename()) -- auch das nur ein Stub, echtes
    # Verhalten (Fallback auf den Schriftzug ohne Logo) wird in
    # tests/test_v249_sidebar_logo.py getestet.
    env.globals["sidebar_logo_url"] = lambda: None
    # Seiten binden seit 1.3.45 zusätzlich _topbar.html ein, das account_display() aufruft
    # (app/routers/pages.py) -- auch das nur ein Stub, echtes Verhalten wird in
    # tests/test_v254_topbar.py getestet.
    env.globals["account_display"] = lambda current_user: {"full_name": "", "initials": ""}
    tmpl = env.get_template("project_folder.html")  # eine beliebige Seite, die _sidebar.html einbindet
    return tmpl.render(request=FakeRequest("/x", user), app_version="1.0.63", project_id=1)


# ---------------------------------------------------------------------------
# Kernproblem: vorher gab es im nicht angemeldeten Zustand überhaupt keine
# sichtbare Anzeige im Fuß-Bereich der Sidebar -- weder Hinweis noch Login.
# ---------------------------------------------------------------------------

def test_sidebar_foot_element_always_present_regardless_of_login_state():
    for user in [FakeUser("admin"), None]:
        html = _render(user)
        assert 'id="appSidebarFoot"' in html, f"appSidebarFoot fehlt bei user={user}"


def test_sidebar_html_balanced_in_both_login_states():
    for user in [FakeUser("admin"), None]:
        html = _render(user)
        checker = BalanceChecker()
        checker.feed(html)
        assert not checker.errors and not checker.stack, f"HTML unausgeglichen bei user={user}: {checker.errors}"


def test_sidebar_uses_existing_auth_status_endpoint():
    """Bewusst der bereits bestehende, leichte /api/auth/status-Endpunkt
    (liefert authenticated/user) statt eines neuen -- kein zusätzlicher
    Backend-Code für die reine Statusanzeige nötig."""
    html = (Path(__file__).parents[1] / "app" / "templates" / "_sidebar.html").read_text(encoding="utf-8")
    assert "/api/auth/status" in html


def test_sidebar_shows_login_form_when_not_authenticated():
    html = (Path(__file__).parents[1] / "app" / "templates" / "_sidebar.html").read_text(encoding="utf-8")
    assert "appSidebarLoginForm" in html
    assert "appSidebarUsername" in html
    assert "appSidebarPassword" in html
    assert "/api/auth/login" in html
    assert "Nicht angemeldet" in html


def test_sidebar_login_reloads_page_on_success_instead_of_redirect():
    """Login direkt in der Sidebar soll auf der aktuellen Seite bleiben
    (location.reload()), nicht wegnavigieren -- anders als der bestehende
    Abmelden-Button, der bewusst zur /login-Seite weiterleitet."""
    html = (Path(__file__).parents[1] / "app" / "templates" / "_sidebar.html").read_text(encoding="utf-8")
    assert "location.reload()" in html


def test_sidebar_escapes_display_name_to_prevent_xss():
    """display_name kommt aus der Datenbank (Benutzerverwaltung) -- beim
    dynamischen Aufbau per JS muss das escaped werden, sonst wäre ein
    bösartiger Anzeigename ein gespeichertes XSS."""
    html = (Path(__file__).parents[1] / "app" / "templates" / "_sidebar.html").read_text(encoding="utf-8")
    assert "escHtml" in html


def test_sidebar_collapsed_state_hides_login_form_but_shows_icon_link():
    """Ein Login-Formular mit Texteingaben passt nicht in die eingeklappte,
    60px schmale Sidebar -- dort stattdessen nur ein kompakter Icon-Link."""
    html = (Path(__file__).parents[1] / "app" / "templates" / "_sidebar.html").read_text(encoding="utf-8")
    assert ".app-sidebar.collapsed .app-sidebar-login-form" in html
    assert "app-sidebar-login-link" in html


def test_sidebar_logout_button_still_works_for_already_logged_in_render():
    """Regressionstest: der bestehende, serverseitig vorgerenderte
    'eingeloggt'-Fall darf durch die neue, dynamische Logik nicht kaputt
    gegangen sein."""
    html = _render(FakeUser("admin"))
    assert 'id="appSidebarLogout"' in html
    assert "Test Nutzer" in html  # display_name des serverseitig übergebenen Nutzers
