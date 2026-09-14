"""Version 1.3.44 -- Umgestaltung der Sidebar, erster von vier Schritten (Topbar, Suche und
Schnellzugriff folgen einzeln in späteren Schritten, siehe CLAUDE.md "Umgestaltung der
Sidebar").

Zwei Punkte in diesem Schritt:

1. Das Logo steht jetzt allein im Kopfbereich, waagerecht zentriert, mit der vollen verfügbaren
   Breite (vorher: Logo + zwei Schaltflächen nebeneinander, Breitenbegrenzung fest bei 200px).
   Die einstellbare Höhe (seit 1.3.39) reicht seither bis 120px (vorher 80), neuer Standardwert
   64 (vorher 48). Die eingeklappte Sidebar (60px) bekommt eine eigene, feste, kleinere
   Logo-Höhe statt der einstellbaren.
2. Hell/Dunkel- und Ein-/Ausklappen-Schaltfläche sind aus dem Kopfbereich in den unteren
   Bereich gewandert (neben den Benutzer-/Abmelden-Block), "Mein Konto" bleibt vorerst, wo es
   ist.

Wie bei tests/test_v249_sidebar_logo.py über eine bare jinja2.Environment mit gestubbten
Globals geprüft (Muster tests/test_v163_sidebar_login_status.py) -- kein Ende-zu-Ende-Test über
eine echte Seite, aus demselben Grund wie dort (die REALEN Jinja-Globals in app/routers/pages.py
öffnen eine eigene SessionLocal(), nicht per Test-Session umstellbar). Kein echter
Browser-Screenshot möglich (kein Automatisierungswerkzeug in dieser Umgebung) -- die rein
visuelle Zentrierung/Anordnung ist deshalb nur an der Markup-/CSS-Struktur geprüft, nicht an
einem gerenderten Bild."""

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


def _render(logo_url=None, height=64):
    root = Path(__file__).parents[1]
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(root / "app" / "templates")))
    env.globals["get_theme"] = lambda: {"accent_color": "#0d9488"}
    env.globals["is_module_enabled"] = lambda key: True
    env.globals["sidebar_logo_url"] = lambda: logo_url
    env.globals["sidebar_logo_height_px"] = lambda: height
    # Seiten binden seit 1.3.45 zusätzlich _topbar.html ein, das account_display() aufruft --
    # auch das nur ein Stub, echtes Verhalten wird in tests/test_v254_topbar.py getestet.
    env.globals["account_display"] = lambda current_user: {"full_name": "", "initials": ""}
    tmpl = env.get_template("project_folder.html")  # eine beliebige Seite, die _sidebar.html einbindet
    return tmpl.render(request=_FakeRequest("/x", _FakeUser()), app_version="1.0.0", project_id=1)


def _head_markup(html):
    start = html.index('<div class="app-sidebar-head"')
    end = html.index("</div>", start)
    return html[start:end]


def _bottom_markup(html):
    start = html.index('<div class="app-sidebar-bottom"')
    end = html.index('<div class="app-sidebar-scrim"')
    return html[start:end]


# ---------------------------------------------------------------------------
# Punkt 1: Logo allein im Kopfbereich, zentriert, volle Breite
# ---------------------------------------------------------------------------

def test_head_contains_only_the_logo_no_buttons():
    html = _render("/api/settings/general/logo?v=abc123.png")
    head = _head_markup(html)
    assert "app-sidebar-logo-wrap" in head
    assert 'id="appThemeToggle"' not in head
    assert 'id="appSidebarToggle"' not in head


def test_head_still_shows_wordmark_fallback_without_buttons():
    html = _render(None)
    head = _head_markup(html)
    assert "app-sidebar-brand" in head
    assert 'id="appThemeToggle"' not in head
    assert 'id="appSidebarToggle"' not in head


def test_head_is_centered_and_logo_wrap_uses_full_available_width():
    html = _render("/api/settings/general/logo?v=abc123.png")
    assert ".app-sidebar-head{display:flex;align-items:center;justify-content:center" in html
    assert ".app-sidebar-logo-wrap{max-width:100%" in html
    # Die vorherige feste 200px-Breitenbegrenzung darf nicht mehr vorkommen.
    assert "max-width:200px" not in html


def test_configurable_height_range_is_24_to_120():
    html = _render("/api/settings/general/logo?v=abc123.png", height=120)
    assert 'style="height:120px"' in html


def test_collapsed_sidebar_uses_its_own_fixed_smaller_logo_height():
    """60px Breite -- die für die volle Breite gedachte, einstellbare Höhe passt dort nicht,
    deshalb eine eigene, feste Höhe statt der konfigurierten (per !important, da die
    konfigurierte Höhe sonst als Inline-Style Vorrang hätte)."""
    html = _render("/api/settings/general/logo?v=abc123.png", height=120)
    assert ".app-sidebar.collapsed .app-sidebar-logo{height:32px!important}" in html
    # Nur auf Desktop-Breite wirksam -- auf Mobilgeräten bedeutet "collapsed" (durch einen
    # Resize ohne Neuladen) weiterhin die volle, unveränderte Darstellung.
    idx = html.index(".app-sidebar.collapsed .app-sidebar-logo{height:32px!important}")
    media_start = html.rindex("@media(min-width:1001px)", 0, idx)
    media_open_brace = html.index("{", media_start)
    assert media_start < idx  # liegt tatsächlich innerhalb dieses Blocks
    assert media_open_brace < idx


def test_wordmark_fallback_stays_fully_hidden_when_collapsed_not_shrunk():
    """Für "DACHKONZEPTE" gibt es bei 60px keinen sinnvollen Platz -- anders als beim Logo
    (das schrumpft) bleibt der reine Textschriftzug beim bisherigen Verhalten: ausgeblendet."""
    html = _render(None)
    assert ".app-sidebar.collapsed .app-sidebar-brand{display:none}" in html


# ---------------------------------------------------------------------------
# Punkt 2: Hell/Dunkel + Einklappen in den unteren Bereich, neben Abmelden
# ---------------------------------------------------------------------------

def test_theme_and_collapse_buttons_are_in_the_bottom_area():
    html = _render("/api/settings/general/logo?v=abc123.png")
    bottom = _bottom_markup(html)
    assert 'id="appThemeToggle"' in bottom
    assert 'id="appSidebarToggle"' in bottom
    # Beide Schaltflaechen erscheinen bereits VOR (oberhalb von) dem Benutzer-/Abmelden-Block --
    # "neben Abmelden" im Sinne von: im selben unteren Bereich, direkt angrenzend.
    assert bottom.index('id="appThemeToggle"') < bottom.index('id="appSidebarFoot"')
    assert bottom.index('id="appSidebarToggle"') < bottom.index('id="appSidebarFoot"')


def test_collapse_toggle_is_never_hidden_when_collapsed_but_theme_toggle_is():
    """Kritisch fuers Bedienbar-Bleiben: die Schaltflaeche, mit der man die eingeklappte
    Sidebar wieder ausklappt, darf im eingeklappten Zustand selbst nicht verschwinden --
    anders als der (dort ohnehin bereits vorher ausgeblendete) Hell/Dunkel-Umschalter."""
    html = _render("/api/settings/general/logo?v=abc123.png")
    assert ".app-sidebar.collapsed .app-sidebar-toggle{display:none}" not in html
    assert ".app-sidebar.collapsed .app-theme-toggle{display:none}" in html


def test_account_link_position_unchanged_for_this_step():
    """"Mein Konto" wandert laut Auftrag erst mit der Topbar in einem spaeteren Schritt --
    dieser Schritt fasst die Jinja-Vorlage dafuer nicht an (das Auth-Fuss-Markup wird ohnehin
    zur Laufzeit per renderAuthFoot() im Skript neu aufgebaut, nicht hier serverseitig)."""
    html = _render("/api/settings/general/logo?v=abc123.png")
    assert "app-sidebar-account-link" in html  # Teil des unveraendert belassenen JS-Templates


# ---------------------------------------------------------------------------
# "Was unveraendert bleibt": Navigationseintraege, Reihenfolge, Gruppen
# ---------------------------------------------------------------------------

def test_navigation_groups_and_order_unchanged():
    html = _render("/api/settings/general/logo?v=abc123.png")
    stammdaten_idx = html.index('<div class="app-sidebar-group">Stammdaten</div>')
    system_idx = html.index('<div class="app-sidebar-group">System</div>')
    master_data_idx = html.index('href="/master-data"')
    settings_idx = html.index('href="/settings"')
    assert stammdaten_idx < master_data_idx < system_idx < settings_idx


def test_mobile_header_include_untouched():
    """_mobile_header.html hat seit 1.3.0 einen eigenen Aufbau und ist von diesem Umbau nicht
    betroffen -- geprueft, dass es keine der hier verschobenen Klassen kennt."""
    root = Path(__file__).parents[1]
    mobile_header = (root / "app" / "templates" / "_mobile_header.html").read_text(encoding="utf-8")
    for cls in ("app-sidebar-head", "app-sidebar-utilities", "app-theme-toggle", "app-sidebar-toggle"):
        assert cls not in mobile_header
