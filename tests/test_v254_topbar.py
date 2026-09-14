"""Version 1.3.45 -- Umgestaltung der Sidebar, Schritt 2 von vier: eine Topbar über dem
Inhaltsbereich (siehe CLAUDE.md "Umgestaltung der Sidebar"). Grundlage für Suche (Schritt 3)
und Schnellzugriff (Schritt 4) -- in diesem Schritt entsteht nur die Leiste selbst und der
Kontobereich rechts.

Drei Teile:
1. app/auth.py::resolve_account_display() -- woher der volle Name/die Initialen für den
   Kontoknopf kommen (Employee.first_name/last_name über AppUser.employee_id, sonst der
   Benutzername). Direkt gegen eine echte DB-Session getestet.
2. app/routers/pages.py::account_display() -- der Jinja-Global, der resolve_account_display()
   umhüllt und (wie die vier bestehenden Globals seit 1.3.42) jede Ausnahme abfängt.
3. app/templates/_topbar.html -- Struktur/Platzierung, über eine bare jinja2.Environment mit
   gestubbten Globals geprüft (Muster tests/test_v249_sidebar_logo.py/test_v253_sidebar_layout.py
   -- aus demselben, dort bereits begründeten Grund kein Ende-zu-Ende-Test über eine echte Seite:
   die REALEN Jinja-Globals öffnen eine eigene SessionLocal(), nicht per Test-Session umstellbar).

Zusätzlich ein projektweiter Konsistenz-Test: jede der 31 Vorlagen, die _sidebar.html einbindet,
muss auch _topbar.html einbinden (bzw. genau die eine, bewusst ausgenommene Monteursansicht
NICHT) -- ein Regressionsschutz dafür, dass eine künftige neue Seite nicht vergisst, die Topbar
einzubinden."""

from pathlib import Path

import jinja2
import pytest

from app.auth import resolve_account_display
from app.models import AppUser, Employee
from app.routers import pages as pages_router_module


# ---------------------------------------------------------------------------
# app/auth.py::resolve_account_display() -- woher der Name/die Initialen kommen
# ---------------------------------------------------------------------------

def test_resolve_account_display_prefers_linked_employee(db_session):
    employee = Employee(first_name="Tobias", last_name="Rödchen")
    db_session.add(employee); db_session.commit()
    user = AppUser(username="tobias", display_name="Chef", role="admin", active=True,
                    password_hash="x", employee_id=employee.id)
    db_session.add(user); db_session.commit()

    result = resolve_account_display(db_session, user)
    assert result == {"full_name": "Tobias Rödchen", "initials": "TR"}


def test_resolve_account_display_falls_back_to_username_without_employee_link(db_session):
    user = AppUser(username="admin", display_name="Administrator", role="admin", active=True,
                    password_hash="x")
    db_session.add(user); db_session.commit()

    result = resolve_account_display(db_session, user)
    assert result == {"full_name": "admin", "initials": "AD"}


def test_resolve_account_display_falls_back_to_username_when_employee_id_points_nowhere(db_session):
    """Verteidigung in der Tiefe: employee_id gesetzt, aber der Mitarbeiter existiert nicht
    (mehr) -- fällt auf den Benutzernamen zurück statt eines Fehlers."""
    user = AppUser(username="geist", display_name="Geist", role="user", active=True,
                    password_hash="x", employee_id=999999)
    db_session.add(user); db_session.commit()

    result = resolve_account_display(db_session, user)
    assert result == {"full_name": "geist", "initials": "GE"}


def test_resolve_account_display_single_character_username_does_not_crash():
    """Randfall: ein einbuchstabiger Benutzername liefert genau diesen einen Buchstaben als
    Initiale, statt z. B. an einer IndexError-Annahme ('es gibt garantiert zwei Zeichen')
    zu scheitern."""
    class _FakeUser:
        employee_id = None
        username = "a"
    result = resolve_account_display(None, _FakeUser())
    assert result == {"full_name": "a", "initials": "A"}


# ---------------------------------------------------------------------------
# app/routers/pages.py::account_display() -- Jinja-Global, muss wie die anderen vier nie werfen
# ---------------------------------------------------------------------------

def test_account_display_global_returns_empty_for_anonymous_user():
    assert pages_router_module._account_display(None) == {"full_name": "", "initials": ""}


def test_account_display_global_falls_back_to_username_on_error(monkeypatch):
    class _FakeUser:
        username = "admin"

    def _boom(db, user):
        raise RuntimeError("simulierter DB-Fehler")

    monkeypatch.setattr(pages_router_module, "resolve_account_display", _boom)
    result = pages_router_module._account_display(_FakeUser())
    assert result == {"full_name": "admin", "initials": "AD"}


# ---------------------------------------------------------------------------
# _topbar.html -- Struktur, Platzierung, Kontoknopf/-menü
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
    username = "test.nutzer"


def _render(user=_FakeUser(), account=None):
    root = Path(__file__).parents[1]
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(root / "app" / "templates")))
    env.globals["get_theme"] = lambda: {"accent_color": "#0d9488"}
    env.globals["is_module_enabled"] = lambda key: True
    env.globals["sidebar_logo_url"] = lambda: None
    env.globals["sidebar_logo_height_px"] = lambda: 64
    env.globals["account_display"] = lambda current_user: (
        account if account is not None else {"full_name": "Tobias Rödchen", "initials": "TR"}
    )
    tmpl = env.get_template("project_folder.html")  # eine beliebige Seite, die beide Includes einbindet
    return tmpl.render(request=_FakeRequest("/x", user), app_version="1.0.0", project_id=1)


def test_topbar_appears_right_after_app_content_before_main():
    html = _render()
    content_idx = html.index('<div class="app-content">')
    topbar_idx = html.index('<div class="app-topbar">')
    main_idx = html.index("<main>")
    assert content_idx < topbar_idx < main_idx


def test_search_slot_is_present_and_empty():
    """Schritt 3 (Suche) folgt später -- der Platz ist bereits reserviert, aber leer."""
    html = _render()
    start = html.index('<div class="app-topbar-search-slot">')
    end = html.index("</div>", start)
    slot = html[start:end]
    assert slot.strip() == '<div class="app-topbar-search-slot">'


def test_account_button_shows_the_resolved_initials():
    html = _render(account={"full_name": "Tobias Rödchen", "initials": "TR"})
    assert '<button type="button" class="app-topbar-account-btn" id="appTopbarAccountBtn"' in html
    btn_start = html.index('id="appTopbarAccountBtn"')
    btn_end = html.index("</button>", btn_start)  # index() zeigt auf das "<" von "</button>"
    assert html[btn_start:btn_end].endswith(">TR")


def test_account_menu_contains_full_name_account_link_and_logout():
    html = _render(account={"full_name": "Tobias Rödchen", "initials": "TR"})
    menu_start = html.index('id="appTopbarAccountMenu"')
    first_inner_div_close = html.index("</div>", menu_start)  # schliesst .app-topbar-account-name
    menu_end = html.index("</div>", first_inner_div_close + 1)  # schliesst .app-topbar-account-menu selbst
    menu = html[menu_start:menu_end]
    assert "Tobias Rödchen" in menu
    assert 'href="/account"' in menu
    assert "Mein Konto" in menu
    assert 'id="appTopbarLogout"' in menu
    assert "Abmelden" in menu


def test_no_account_button_when_not_authenticated():
    html = _render(user=None)
    assert 'id="appTopbarAccountBtn"' not in html
    assert 'id="appTopbarAccountMenu"' not in html
    # Die Leiste selbst bleibt trotzdem bestehen.
    assert '<div class="app-topbar">' in html


def test_topbar_is_sticky_and_uses_design_system_variables_only():
    html = _render()
    assert ".app-topbar{position:sticky;top:0" in html
    assert "background:var(--card)" in html
    assert "border-bottom:1px solid var(--line)" in html
    # Keine im Hex-Code fest eingetragene, projektfremde Farbe im Topbar-Regelsatz -- "#fff" für
    # Text auf Akzentfarbe ist die bereits im ganzen Projekt etablierte Konvention (z. B.
    # settings.html: "button{background:var(--accent);color:#fff;...}"), keine neue Erfindung.
    topbar_css_start = html.index(".app-topbar{")
    topbar_css_end = html.index("</style>", topbar_css_start)
    topbar_css = html[topbar_css_start:topbar_css_end]
    assert topbar_css.count("#") == topbar_css.count("#fff")


# ---------------------------------------------------------------------------
# Kollision mit der Sidebar geprüft: z-index niedriger als die (mobile) Sidebar/der Scrim
# ---------------------------------------------------------------------------

def test_topbar_z_index_is_lower_than_mobile_sidebar_and_scrim():
    """Eine geöffnete Mobil-Sidebar (z-index:40) bzw. der Scrim (z-index:39) sollen sich beim
    Öffnen bewusst ÜBER die Topbar legen, nicht darunter verschwinden."""
    html = _render()
    topbar_z = html[html.index(".app-topbar{"):html.index("}", html.index(".app-topbar{"))]
    assert "z-index:10" in topbar_z


# ---------------------------------------------------------------------------
# Was unverändert bleibt: /vor-ort bekommt keine Topbar
# ---------------------------------------------------------------------------

def test_mobile_header_does_not_include_topbar():
    root = Path(__file__).parents[1]
    mobile_header = (root / "app" / "templates" / "_mobile_header.html").read_text(encoding="utf-8")
    assert "_topbar.html" not in mobile_header
    vor_ort = (root / "app" / "templates" / "vor_ort.html").read_text(encoding="utf-8")
    assert "_topbar.html" not in vor_ort


# ---------------------------------------------------------------------------
# Projektweiter Konsistenz-Test: jede Seite mit _sidebar.html bekommt auch _topbar.html
# ---------------------------------------------------------------------------

def test_every_template_with_sidebar_also_includes_topbar():
    """Nur echte SEITEN geprüft, keine Partials (Dateien mit führendem "_") -- _topbar.html
    selbst erwähnt _sidebar.html im erklärenden Jinja-Kommentar (wo es eingebunden werden muss),
    was als reiner Text-Treffer sonst fälschlich mitgezählt würde, obwohl Jinja-Kommentare beim
    Rendern vollständig entfernt werden (kein Rekursionsrisiko wie beim 1.2.19-Fund in
    _debounce.html, dort ein JS-Kommentar statt eines Jinja-Kommentars -- hier bewusst geprüft,
    nicht nur angenommen)."""
    root = Path(__file__).parents[1] / "app" / "templates"
    missing = []
    for html_file in sorted(root.glob("*.html")):
        if html_file.name.startswith("_"):
            continue
        text = html_file.read_text(encoding="utf-8")
        if '{% include "_sidebar.html" %}' in text and '{% include "_topbar.html" %}' not in text:
            missing.append(html_file.name)
    assert missing == []
