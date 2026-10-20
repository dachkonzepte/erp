"""Seit 1.8.162 die neue Leiste (Stufe 2 „Rahmen“, Tests unten); ursprünglich Version 1.3.44 -- Umgestaltung der Sidebar, erster von vier Schritten (Topbar, Suche und
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
    env.globals["can"] = lambda current_user, *roles: current_user is not None and current_user.role in roles
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

# ---------------------------------------------------------------------------
# Seit 1.8.162 (Stufe 2 „Rahmen“, Runde 1, Teil 2): Logo-Zeile 52 px mit Kachel 36 px und Schriftzug, Fuß nur „Version …“, Hell/Dunkel
# im Kontomenü, Einklappen am Menüknopf der Kopfzeile, vier Gruppen, aktiv über `bereich`. Die Tests bis 1.8.161 prüften das Logo mit
# einstellbarer Höhe im Kopf und die beiden Knöpfe unten in der Leiste.
# ---------------------------------------------------------------------------

def test_kopf_kachel_mit_logo_und_schriftzug_ohne_knoepfe():
    head = _head_markup(_render("/api/settings/general/logo?v=abc123.png"))
    assert '<span class="app-sidebar-kachel mit-logo"><img class="app-sidebar-logo" src="/api/settings/general/logo?v=abc123.png" alt=""></span>' in head
    html = _render("/api/settings/general/logo?v=abc123.png")
    kopf = html[html.index('<div class="app-sidebar-head"'):html.index('<nav class="app-sidebar-nav">')]
    assert "DACHKONZEPTE" in kopf and "Rödchen GmbH · ERP" in kopf
    assert 'id="appThemeToggle"' not in kopf and 'id="appSidebarToggle"' not in kopf


def test_kopf_ohne_logo_zeigt_ein_dach_auf_der_kachel():
    html = _render(None)
    kopf = html[html.index('<div class="app-sidebar-head"'):html.index('<nav class="app-sidebar-nav">')]
    assert '<span class="app-sidebar-kachel" aria-hidden="true"><svg' in kopf and "<img" not in kopf
    assert "DACHKONZEPTE" in kopf and "Rödchen GmbH · ERP" in kopf


def test_kopf_52px_kachel_36px_breite_232px():
    html = _render(None)
    assert ".app-sidebar{width:232px;flex:0 0 232px;box-sizing:border-box;" in html
    assert ".app-sidebar-head{display:flex;align-items:center;gap:10px;box-sizing:border-box;height:52px;flex:0 0 52px;" in html
    assert "width:36px;height:36px;flex:0 0 36px;" in html.split(".app-sidebar-kachel{", 1)[1].split("}", 1)[0]


def test_logo_hoehe_der_einstellung_wirkt_nicht_mehr():
    """Die Kachel ist fest 36 px -- die einstellbare Höhe (24–120 px, sidebar_logo_height_px) setzt kein Inline-Maß mehr."""
    html = _render("/api/settings/general/logo?v=abc123.png", height=120)
    assert 'style="height:120px"' not in html and "sidebar_logo_height_px" not in html


def test_eingeklappt_60px_nur_kachel_und_symbole():
    html = _render(None)
    assert ".app-sidebar.collapsed{width:60px;flex-basis:60px}" in html
    regel = html.split(".app-sidebar.collapsed .app-sidebar-marke,", 1)[1].split("}", 1)[0]
    assert ".app-sidebar.collapsed .app-sidebar-label" in regel and ".app-sidebar.collapsed .app-sidebar-version" in regel
    assert "display:none" in regel


def test_fuss_nur_version_und_das_feld_fuer_eine_abgelaufene_sitzung():
    bottom = _bottom_markup(_render(None))
    assert 'id="appSidebarFoot"' in bottom and "Version 1.0.0" in bottom
    assert "<button" not in bottom and "appThemeToggle" not in bottom and "appSidebarToggle" not in bottom


def test_hell_dunkel_im_kontomenue_und_einklappen_am_menueknopf_der_kopfzeile():
    """Was die Leiste abgibt, bleibt erreichbar: Hell/Dunkel im Kontomenü (seit 1.8.163 _kontomenue.html, von der Kopfzeile eingebunden),
    Einklappen am Menüknopf der Kopfzeile -- der steht außerhalb der Leiste und ist auch am Desktop sichtbar, also nie in der
    eingeklappten Leiste verschwunden."""
    from tests import vorlagen_js
    root = Path(__file__).parents[1]
    topbar = (root / "app" / "templates" / "_topbar.html").read_text(encoding="utf-8")
    konto = (root / "app" / "templates" / "_kontomenue.html").read_text(encoding="utf-8")
    assert vorlagen_js.bindet_ein("_topbar.html", "_kontomenue.html", root / "app" / "templates", nur_selbst=True)
    assert 'id="appThemeToggle"' in konto and "localStorage.setItem('erp_theme'" in konto
    assert "localStorage.setItem('erp_sidebar_collapsed'" in topbar
    regeln = [r for r in topbar.split("}") if ".app-topbar-menu-btn{" in r]
    assert regeln and all("display:none" not in r for r in regeln)
    html = _render(None)
    aside = html[html.index('<aside class="app-sidebar"'):html.index("</aside>")]
    assert "appTopbarMenuBtn" not in aside


def test_account_link_removed_since_1_3_49():
    """"Mein Konto" (und Benutzername/Abmelden) wanderten mit der Topbar (Schritt 2, 1.3.45)
    dorthin -- seit 1.3.49 ist die Sidebar-eigene Kopie davon vollständig entfernt, siehe
    tests/test_v163_sidebar_login_status.py für den zugehörigen Regressionstest."""
    html = _render("/api/settings/general/logo?v=abc123.png")
    assert "app-sidebar-account-link" not in html


def test_vier_gruppen_in_reihenfolge():
    html = _render(None)
    nav = html[html.index('<nav class="app-sidebar-nav">'):html.index("</nav>")]
    import re as _re
    folge = _re.findall(r'<div class="app-sidebar-group">([^<]+)</div>|data-bereich="([a-z]+)"', nav)
    assert [g or b for g, b in folge] == [
        "Übersicht", "start", "aufgaben", "kalender",
        "Aufträge", "anfragen", "projekte", "plantafel", "checklisten", "wartungen", "befunde",
        "Kaufmännisch", "finanzen", "mahnwesen", "eingangsrechnungen", "betriebskosten", "zeiterfassung", "backoffice",
        "Verwaltung", "stammdaten", "einstellungen"]
    befunde = nav[nav.rindex("<a ", 0, nav.index('data-bereich="befunde"')):nav.index('data-bereich="befunde"')]
    assert "app-sidebar-sub" in befunde


def test_aktiv_ist_der_bereich_der_seite():
    """project_folder.html nennt bereich "projekte" -- genau dieser Eintrag ist aktiv, mit aria-current."""
    html = _render(None)
    nav = html[html.index('<nav class="app-sidebar-nav">'):html.index("</nav>")]
    assert nav.count(" active") == 1 and nav.count('aria-current="page"') == 1
    projekte = nav[nav.index('data-bereich="projekte"') - 60:nav.index('data-bereich="projekte"') + 80]
    assert "app-sidebar-link active" in projekte and 'aria-current="page"' in projekte


def test_mobile_header_include_untouched():
    """_mobile_header.html hat seit 1.3.0 einen eigenen Aufbau und ist von diesem Umbau nicht
    betroffen -- geprueft, dass es keine der hier verschobenen Klassen kennt."""
    root = Path(__file__).parents[1]
    mobile_header = (root / "app" / "templates" / "_mobile_header.html").read_text(encoding="utf-8")
    for cls in ("app-sidebar-head", "app-sidebar-utilities", "app-theme-toggle", "app-sidebar-toggle"):
        assert cls not in mobile_header
