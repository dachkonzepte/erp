"""Version 1.3.49 -- Aufräumen im unteren Bereich der Sidebar.

Benutzername, "Mein Konto" und "Abmelden" standen dort noch, obwohl alle drei bereits seit
Schritt 2 (1.3.45) über den Kontoknopf der Topbar erreichbar sind -- zwei Stellen für
dasselbe verwirren. Entfernt: der untere Bereich zeigt jetzt nur noch die beiden
Schaltflächen (Hell/Dunkel, Ein-/Ausklappen) und die Versionsnummer. #appSidebarFoot bleibt
als Element bestehen (für das clientseitige Wiederanmelde-Formular bei einer während des
Browsens ablaufenden Sitzung), rendert serverseitig aber für jeden Anmeldestatus leer;
.app-sidebar-foot:empty{padding:0} verhindert dabei eine unnötig gepolsterte Leerstelle.

Geprüft (siehe Auftrag): /vor-ort nutzt _mobile_header.html mit einem eigenen, komplett
unabhängigen Abmelden-Weg -- unangetastet. Unterhalb des mobilen Umbruchpunkts (seit 1.3.46
blendet sich dort #appSidebarToggle aus) enthält der untere Bereich dann nur noch die
Hell/Dunkel-Schaltfläche und die Version -- geprüft per Struktur, kein Absturz/keine
kaputte Verschachtelung, siehe test_v163_sidebar_login_status.py für die
HTML-Balance-Prüfung, die weiterhin über beide Anmeldezustände läuft.

Nebenbefund aus dem Auftrag: der jetzt entfernte "Mein Konto"-Link (.app-sidebar-account-link)
hatte keine eigene CSS-Regel und wäre als blau unterstrichener Browser-Standardlink erschienen
-- erledigt sich durch die Entfernung selbst, kein separater Fix nötig."""

from pathlib import Path

import jinja2


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
    username = "test.nutzer"


def _render(user=_FakeUser()):
    root = Path(__file__).parents[1]
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(root / "app" / "templates")))
    env.globals["get_theme"] = lambda: {"accent_color": "#0d9488"}
    env.globals["is_module_enabled"] = lambda key: True
    env.globals["sidebar_logo_url"] = lambda: None
    env.globals["sidebar_logo_height_px"] = lambda: 64
    env.globals["account_display"] = lambda current_user: {"full_name": "Tobias Rödchen", "initials": "TR"}
    env.globals["can"] = lambda current_user, *roles: current_user is not None and current_user.role in roles
    tmpl = env.get_template("project_folder.html")  # eine beliebige Seite, die beide Includes einbindet
    return tmpl.render(request=_FakeRequest("/x", user), app_version="1.0.0", project_id=1)


def _bottom_markup(html):
    start = html.index('<div class="app-sidebar-bottom"')
    end = html.index('<div class="app-sidebar-scrim"')
    return html[start:end]


# ---------------------------------------------------------------------------
# Der untere Bereich zeigt nur noch die beiden Schaltflächen und die Version.
# ---------------------------------------------------------------------------

def test_bottom_area_no_longer_shows_username_account_link_or_logout():
    html = _render()
    bottom = _bottom_markup(html)
    assert 'id="appSidebarLogout"' not in bottom
    assert "app-sidebar-account-link" not in bottom
    assert "app-sidebar-user" not in bottom
    assert "Test Nutzer" not in bottom


def test_bottom_area_still_shows_both_buttons_and_the_version():
    html = _render()
    bottom = _bottom_markup(html)
    assert 'id="appThemeToggle"' in bottom
    assert 'id="appSidebarToggle"' in bottom
    assert "Version 1.0.0" in bottom


def test_app_sidebar_foot_element_still_exists_but_renders_empty():
    """Bleibt als Zielelement für das clientseitige Wiederanmelde-Formular bestehen (siehe
    renderAuthFoot() in _sidebar.html) -- rendert serverseitig aber leer, unabhängig vom
    Anmeldestatus (anders als vor 1.3.49, wo der authentifizierte Fall Inhalt zeigte)."""
    for user in (_FakeUser(), None):
        html = _render(user)
        foot_start = html.index('id="appSidebarFoot"')
        foot_tag_end = html.index(">", foot_start)
        assert html[foot_tag_end:foot_tag_end + len("></div>")] == "></div>"


def test_empty_foot_has_no_padding_to_avoid_a_pointless_gap():
    html = _render()
    assert ".app-sidebar-foot:empty{padding:0}" in html


# ---------------------------------------------------------------------------
# Toter Code entfernt -- keine Aufrufer mehr seit dem Wegfall von Benutzername/
# Abmelden-Button in der Sidebar.
# ---------------------------------------------------------------------------

def test_dead_logout_and_escaping_helpers_are_gone():
    """Nur das <script> selbst geprüft, nicht die ganze Datei -- der erklärende Jinja-
    Kommentar am Dateianfang nennt bindLogout()/escHtml() beim Namen (dokumentiert, warum sie
    entfernt wurden), ein naiver Volltext-Scan würde das fälschlich als Treffer zählen (das
    exakte, bereits an anderer Stelle dokumentierte Muster, siehe CLAUDE.md zu
    _topbar.html/_debounce.html)."""
    html = (Path(__file__).parents[1] / "app" / "templates" / "_sidebar.html").read_text(encoding="utf-8")
    script = html[html.index("<script>"):]
    assert "bindLogout" not in script
    assert "escHtml" not in script
    assert "LOGOUT_ICON" not in script
    style = html[html.index("<style>"):html.index("</style>")]
    assert ".app-sidebar-logout" not in style
    assert ".app-sidebar-user" not in style


# ---------------------------------------------------------------------------
# Trotzdem erhalten: der Zwei-Faktor-Pending-Check läuft unabhängig davon, ob im
# Fußbereich etwas angezeigt wird.
# ---------------------------------------------------------------------------

def test_two_factor_pending_redirect_check_is_preserved():
    html = (Path(__file__).parents[1] / "app" / "templates" / "_sidebar.html").read_text(encoding="utf-8")
    assert "status.two_factor_required && !status.otp_ok" in html
    assert "location.href='/account'" in html


# ---------------------------------------------------------------------------
# Geprüft: /vor-ort bleibt unangetastet, eigener, unabhängiger Abmelde-Weg.
# ---------------------------------------------------------------------------

def test_mobile_header_keeps_its_own_independent_logout():
    root = Path(__file__).parents[1] / "app" / "templates"
    mobile_header = (root / "_mobile_header.html").read_text(encoding="utf-8")
    assert 'id="mobileHeaderLogout"' in mobile_header
    for cls in ("app-sidebar-foot", "app-sidebar-user", "app-sidebar-logout", "app-sidebar-account-link"):
        assert cls not in mobile_header
