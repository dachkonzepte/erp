"""Version 1.3.46 -- Nebenbefund aus 1.3.45 (Umgestaltung der Sidebar, Schritt 2) behoben, VOR
Schritt 3 (Suche): auf einem schmalen Bildschirm gab es keinen erreichbaren Weg, die Off-Canvas-
Sidebar zu öffnen -- ihr einziger Umschalter (#appSidebarToggle) steckte selbst innerhalb von
<aside class="app-sidebar">, die im geschlossenen Zustand per transform:translateX(-100%)
komplett unsichtbar ist. Genau die Art Fehler, die eine reine Struktur-/CSS-Prüfung ohne echten
Browser leicht übersieht, weil sie nichts über Bildschirmbreiten weiß -- dieser Test prüft deshalb
gezielt die Invariante, die den Fehler verursacht hat (Auslöser außerhalb des unsichtbaren
Elements), statt nur "der Knopf existiert irgendwo".

Neu: #appTopbarMenuBtn in _topbar.html -- außerhalb von <aside id="appSidebar">, erscheint nur
unterhalb des Umbruchpunkts (max-width:1000px, derselbe Wert wie _sidebar.html), steht links vor
dem für Schritt 3 reservierten Suchen-Platzhalter. Öffnet/schließt dasselbe Zustandspaar
(.app-sidebar.mobile-open / #appSidebarScrim.visible) wie zuvor #appSidebarToggle -- das blendet
sich seither unterhalb des Umbruchpunkts komplett aus (kein Kollabieren im Desktop-Sinn auf
Mobilgeräten, nur Auf/Zu, keine zwei Bedienungen für dieselbe Aktion nebeneinander)."""

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


def _render():
    root = Path(__file__).parents[1]
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(root / "app" / "templates")))
    env.globals["get_theme"] = lambda: {"accent_color": "#0d9488"}
    env.globals["is_module_enabled"] = lambda key: True
    env.globals["sidebar_logo_url"] = lambda: None
    env.globals["sidebar_logo_height_px"] = lambda: 64
    env.globals["account_display"] = lambda current_user: {"full_name": "Tobias Rödchen", "initials": "TR"}
    env.globals["can"] = lambda current_user, *roles: current_user is not None and current_user.role in roles
    tmpl = env.get_template("project_folder.html")  # eine beliebige Seite, die beide Includes einbindet
    return tmpl.render(request=_FakeRequest("/x", _FakeUser()), app_version="1.0.0", project_id=1)


# ---------------------------------------------------------------------------
# Die eigentliche Invariante: der Öffnen-Auslöser darf nicht innerhalb des
# Elements liegen, das er öffnen soll -- sonst ist er bei geschlossener
# Sidebar unerreichbar, genau der 1.3.45-Fund.
# ---------------------------------------------------------------------------

def test_mobile_menu_button_lives_outside_the_aside_it_controls():
    html = _render()
    aside_start = html.index('<aside class="app-sidebar" id="appSidebar"')
    aside_end = html.index("</aside>", aside_start)
    btn_idx = html.index('id="appTopbarMenuBtn"')
    assert not (aside_start < btn_idx < aside_end), (
        "Der Öffnen-Umschalter darf nicht innerhalb von <aside id=\"appSidebar\"> stehen -- "
        "genau das machte #appSidebarToggle auf schmalen Bildschirmen unerreichbar."
    )


def test_mobile_menu_button_appears_before_search_slot_and_hidden_on_desktop():
    html = _render()
    btn_idx = html.index('id="appTopbarMenuBtn"')
    slot_idx = html.index('<div class="app-topbar-search-slot">')
    assert btn_idx < slot_idx  # steht links davor, wie verlangt
    # Standardmäßig (Desktop) unsichtbar -- braucht dort keinen Platz vor der künftigen Suche.
    assert ".app-topbar-menu-btn{display:none" in html


def test_mobile_menu_button_becomes_visible_at_the_same_breakpoint_as_the_sidebar():
    html = _render()
    # Derselbe Umbruchpunkt wie _sidebar.html's Off-Canvas-Umschaltung (max-width:1000px) --
    # ein abweichender Wert würde ein Fenster öffnen, in dem der Knopf entweder sichtbar ist,
    # aber nichts Erreichbares steuert, oder unsichtbar bleibt, während die Sidebar bereits
    # off-canvas ist. Die Regel schließt mit zwei aufeinanderfolgenden "}" (Regel + @media-Block),
    # das grenzt den ganzen Block sauber ein, ohne von einzelnen "}" innerhalb verwirrt zu werden.
    media_start = html.index("@media(max-width:1000px){.app-topbar{")
    media_block_end = html.index("}}", media_start) + 2
    media_block = html[media_start:media_block_end]
    assert ".app-topbar-menu-btn{display:flex}" in media_block


def test_mobile_menu_button_toggles_the_same_state_as_the_scrim_and_drawer():
    # Bewusst nicht auf ein einzelnes <script>-Element eingegrenzt (die Seite hat mehrere,
    # project_folder.html bringt ein eigenes, deutlich späteres mit) -- die Bezeichner sind
    # eindeutig genug, um allein per Volltextsuche zuverlässig zu sein.
    html = _render()
    assert "getElementById('appTopbarMenuBtn')" in html
    assert "classList.toggle('mobile-open')" in html
    assert "classList.toggle('visible',open)" in html


def test_mobile_menu_button_has_accessible_attributes():
    html = _render()
    btn_start = html.index('id="appTopbarMenuBtn"')
    btn_tag_end = html.index(">", btn_start)
    btn_tag = html[html.rindex("<button", 0, btn_start):btn_tag_end]
    assert 'aria-label="Navigation öffnen"' in btn_tag
    assert 'aria-controls="appSidebar"' in btn_tag
    assert 'aria-expanded="false"' in btn_tag


# ---------------------------------------------------------------------------
# Die alte Bedienung (#appSidebarToggle) blendet sich unterhalb des
# Umbruchpunkts aus -- kein Kollabieren im Desktop-Sinn auf Mobilgeräten,
# nur Auf/Zu, keine zwei Bedienungen für dieselbe Aktion nebeneinander.
# ---------------------------------------------------------------------------

def test_old_sidebar_toggle_is_hidden_below_the_breakpoint():
    html = _render()
    mobile_media_start = html.index("@media(max-width:1000px){\n  .app-sidebar{position:fixed")
    mobile_media_end = html.index("</style>", mobile_media_start)
    mobile_media = html[mobile_media_start:mobile_media_end]
    assert ".app-sidebar-toggle{display:none}" in mobile_media
    # Bewusst NICHT dieselbe Regel wie die 1.3.44-Desktop-Prüfung (die bleibt unverändert
    # gültig -- dort geht es um das Kollabieren, hier um Mobilgeräte).
    assert ".app-sidebar.collapsed .app-sidebar-toggle{display:none}" not in html


def test_old_sidebar_toggle_click_handler_no_longer_touches_mobile_open():
    """Der jetzt tote isMobile()-Zweig in #appSidebarToggle's Klick-Handler wurde entfernt --
    unerreichbar, da das Element selbst display:none ist (siehe Test oben)."""
    html = _render()
    handler_start = html.index("toggle.addEventListener('click',function(){")
    handler_end = html.index("});", handler_start)
    handler = html[handler_start:handler_end]
    assert "mobile-open" not in handler
    assert "collapsed" in handler  # das Desktop-Kollabieren bleibt


# ---------------------------------------------------------------------------
# Schließen per Klick auf den Hintergrund bleibt bei _sidebar.html -- der
# neue Knopf synchronisiert dabei nur sein eigenes aria-expanded.
# ---------------------------------------------------------------------------

def test_menu_button_aria_expanded_resyncs_on_scrim_click():
    html = _render()
    assert "mobileScrim.addEventListener('click'" in html
    assert "menuBtn.setAttribute('aria-expanded','false')" in html


# ---------------------------------------------------------------------------
# Nicht Teil dieser Version: /mobil (bis 1.3.60 /vor-ort) bleibt unverändert ohne
# Topbar/Menü-Knopf.
# ---------------------------------------------------------------------------

def test_mobile_field_view_still_has_no_topbar_menu_button():
    root = Path(__file__).parents[1]
    mobil = (root / "app" / "templates" / "mobil.html").read_text(encoding="utf-8")
    assert "appTopbarMenuBtn" not in mobil
