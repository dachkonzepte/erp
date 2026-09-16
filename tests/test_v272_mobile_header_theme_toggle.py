"""Version 1.3.68 -- Hell/Dunkel-Umschalter in der Monteurs-Kopfzeile (_mobile_header.html).

Die Büro-Sidebar hat den Umschalter seit 1.3.44 im Fußbereich, die Monteurs-Kopfzeile hatte
bislang keinen -- ergänzt nach demselben Mechanismus (data-theme-Attribut auf <html>,
localStorage-Schlüssel 'erp_theme'), damit ein Monteur, der auf dem Tablet umschaltet, seine
Wahl beim nächsten Öffnen wiederfindet (siehe CLAUDE.md "Monteursansicht").

Drei Teile:
1. Struktur/Platzierung von _mobile_header.html, über eine bare jinja2.Environment mit
   gestubbten Globals geprüft (Muster tests/test_v254_topbar.py::_render -- kein echtes
   Rendering über eine Seite, da die vier Jinja-Globals mit Datenbankzugriff nicht per
   Test-Session umstellbar sind, siehe CLAUDE.md "Bekannte, bewusst offene Punkte").
2. Derselbe Mechanismus wie _sidebar.html (data-theme/'erp_theme'), nicht nur ein Knopf ohne
   Funktion -- per Quelltextvergleich der beiden IIFEs geprüft.
3. Regressionsschutz für die Vorgabe "get_theme() greift auch auf den Monteursseiten": alle vier
   Templates, die _mobile_header.html einbinden, rufen get_theme().accent_color im eigenen
   :root-Block auf -- war bereits vor dieser Version so, wird hier nur als Test festgehalten.
"""

from pathlib import Path

import jinja2

TEMPLATES_DIR = Path(__file__).parents[1] / "app" / "templates"


def _render_mobile_header(user=None):
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(TEMPLATES_DIR)))

    class _FakeURL:
        path = "/mobil"

    class _FakeState:
        def __init__(self, u):
            self.erp_user = u

    class _FakeRequest:
        def __init__(self, u):
            self.url = _FakeURL()
            self.state = _FakeState(u)

    class _FakeUser:
        display_name = "Max Mustermann"

    tmpl = env.get_template("_mobile_header.html")
    return tmpl.render(request=_FakeRequest(user if user is not None else _FakeUser()))


# ---------------------------------------------------------------------------
# Struktur/Platzierung
# ---------------------------------------------------------------------------

def test_theme_toggle_button_exists_inside_mobile_header_row():
    html = _render_mobile_header()
    header_start = html.index('<div class="mobile-header">')
    header_end = html.index('<div class="mobile-search-bar">')
    header_row = html[header_start:header_end]
    assert 'id="mobileThemeToggle"' in header_row
    assert 'class="mobile-theme-toggle"' in header_row


def test_theme_toggle_sits_next_to_username_not_in_search_or_nav():
    """Kollisionsfreiheit mit Suchfeld (1.3.65) und den vier Reitern -- der Umschalter steckt
    ausschliesslich im Kopf-Block, strukturell getrennt von .mobile-search-bar/.mobile-nav."""
    html = _render_mobile_header()
    search_start = html.index('<div class="mobile-search-bar">')
    nav_start = html.index('<nav class="mobile-nav">')
    nav_end = html.index('</nav>')
    search_bar = html[search_start:nav_start]
    nav = html[nav_start:nav_end]
    assert "mobileThemeToggle" not in search_bar
    assert "mobileThemeToggle" not in nav
    # Gruppiert mit dem Benutzernamen in einem gemeinsamen Rechts-Wrapper, wie vorgegeben
    # ("vermutlich oben rechts neben dem Benutzernamen").
    right_start = html.index('<div class="mobile-header-right">')
    right_end = html.index('</div>', html.index('id="mobileThemeToggle"'))
    right_block = html[right_start:right_end]
    assert "mobile-header-user" in right_block
    assert "mobileThemeToggle" in right_block


def test_mobile_header_has_exactly_two_direct_children_preserving_space_between():
    """.mobile-header nutzt justify-content:space-between -- ein dritter direkter Kindknoten
    wuerde die Zeile verschieben statt Benutzer+Umschalter zusammen rechts zu halten. Der neue
    Umschalter muss deshalb INNERHALB des rechten Wrappers stecken, nicht als eigenes,
    drittes Geschwisterelement von .mobile-header-brand."""
    html = _render_mobile_header()
    start = html.index('<div class="mobile-header">')
    end = html.index("</div>", html.rindex('id="mobileThemeToggle"'))
    end = html.index("</div>", end)  # schliesst .mobile-header-right
    end = html.index("</div>", end + 1)  # schliesst .mobile-header selbst
    block = html[start:end]
    assert block.count('<span class="mobile-header-brand"') == 1
    assert block.count('<div class="mobile-header-right"') == 1


def test_toggle_is_fixed_size_and_does_not_shrink_or_wrap():
    """Strukturelle Absicherung gegen Umbruch/Verdraengung auf schmalen Bildschirmen: der
    Rechts-Wrapper ist flex:0 0 auto (schrumpft nie), der Umschalter selbst hat eine feste
    30x30px-Groesse -- nur .mobile-header-brand (bereits mit overflow:hidden) darf schrumpfen."""
    html = _render_mobile_header()
    style_start = html.index("<style>")
    style_end = html.index("</style>")
    css = html[style_start:style_end]
    assert ".mobile-header-right{display:flex;align-items:center;gap:8px;flex:0 0 auto" in css
    assert ".mobile-theme-toggle{background:none;border:1px solid var(--line);color:var(--ink);width:30px;height:30px;flex:0 0 30px" in css
    assert "overflow:hidden" in css.split(".mobile-header-brand{", 1)[1].split("}", 1)[0]


# ---------------------------------------------------------------------------
# Derselbe Mechanismus wie _sidebar.html
# ---------------------------------------------------------------------------

def test_toggle_uses_the_same_storage_key_and_attribute_as_the_sidebar():
    mobile_js = (TEMPLATES_DIR / "_mobile_header.html").read_text(encoding="utf-8")
    sidebar_js = (TEMPLATES_DIR / "_sidebar.html").read_text(encoding="utf-8")
    for needle in (
        "document.documentElement.getAttribute('data-theme')",
        "document.documentElement.setAttribute('data-theme'",
        "localStorage.setItem('erp_theme'",
    ):
        assert needle in mobile_js, needle
        assert needle in sidebar_js, needle


def test_toggle_swaps_sun_and_moon_icon_like_the_sidebar():
    mobile_js = (TEMPLATES_DIR / "_mobile_header.html").read_text(encoding="utf-8")
    sidebar_js = (TEMPLATES_DIR / "_sidebar.html").read_text(encoding="utf-8")
    # Dieselben SVG-Icon-Strings, keine eigene, abweichende Ikonografie.
    sun_icon = sidebar_js[sidebar_js.index("var SUN_ICON="):sidebar_js.index(";", sidebar_js.index("var SUN_ICON="))]
    moon_icon = sidebar_js[sidebar_js.index("var MOON_ICON="):sidebar_js.index(";", sidebar_js.index("var MOON_ICON="))]
    assert sun_icon in mobile_js
    assert moon_icon in mobile_js


def test_toggle_click_handler_writes_to_localstorage_and_updates_the_dom():
    mobile_js = (TEMPLATES_DIR / "_mobile_header.html").read_text(encoding="utf-8")
    handler_start = mobile_js.index("themeToggle.addEventListener('click'")
    handler_end = mobile_js.index("});", handler_start)
    handler = mobile_js[handler_start:handler_end]
    assert "document.documentElement.setAttribute('data-theme',next)" in handler
    assert "localStorage.setItem('erp_theme',next)" in handler


# ---------------------------------------------------------------------------
# get_theme() greift auch auf den Monteursseiten (Regressionsschutz, war bereits so)
# ---------------------------------------------------------------------------

def test_get_theme_is_used_in_root_block_of_every_page_including_mobile_header():
    for page in ("mobil.html", "mobil_objekt.html", "field_timesheet.html", "time_tracking_field.html"):
        text = (TEMPLATES_DIR / page).read_text(encoding="utf-8")
        assert "{% include \"_mobile_header.html\" %}" in text, page
        assert "get_theme().accent_color" in text, page
        # Steht tatsaechlich im :root-Block, nicht nur irgendwo auf der Seite.
        root_start = text.index(":root{")
        root_end = text.index("}", root_start)
        assert "get_theme().accent_color" in text[root_start:root_end], page
