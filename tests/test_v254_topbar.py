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
from app import seitendaten
from app.routers import pages as pages_router_module
from tests import vorlagen_js


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


def test_resolve_account_display_falls_back_to_display_name_without_employee_link(db_session):
    """Seit 1.8.168 der Anzeigename des Kontos (bis 1.8.167 der Benutzername "admin")."""
    user = AppUser(username="admin", display_name="Ada Admin", role="admin", active=True,
                    password_hash="x")
    db_session.add(user); db_session.commit()

    result = resolve_account_display(db_session, user)
    assert result == {"full_name": "Ada Admin", "initials": "AA"}


def test_resolve_account_display_falls_back_to_username_without_display_name(db_session):
    """Erst ohne Anzeigenamen (leer oder nur Leerzeichen) der Benutzername."""
    user = AppUser(username="admin", display_name="  ", role="admin", active=True, password_hash="x")
    db_session.add(user); db_session.commit()

    assert resolve_account_display(db_session, user) == {"full_name": "admin", "initials": "AD"}


def test_resolve_account_display_falls_back_to_display_name_when_employee_id_points_nowhere(db_session):
    """Verteidigung in der Tiefe: employee_id gesetzt, aber der Mitarbeiter existiert nicht
    (mehr) -- fällt auf den Anzeigenamen zurück (seit 1.8.168, bis dahin den Benutzernamen) statt eines Fehlers."""
    user = AppUser(username="geist", display_name="Geist", role="user", active=True,
                    password_hash="x", employee_id=999999)
    db_session.add(user); db_session.commit()

    result = resolve_account_display(db_session, user)
    assert result == {"full_name": "Geist", "initials": "GE"}


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
# app/routers/pages.py::account_display() -- Jinja-Global, muss wie die anderen vier nie werfen.
# Seit 1.8.114 mit dem Kontext der Vorlage als erstem Argument (pass_context; None: lädt selbst), gelesen über app/seitendaten.py.
# ---------------------------------------------------------------------------

def test_account_display_global_returns_empty_for_anonymous_user():
    assert pages_router_module._account_display(None, None) == {"full_name": "", "initials": ""}


def test_account_display_global_falls_back_to_display_name_on_error(monkeypatch):
    """Seit 1.8.168 auch hier der Anzeigename vor dem Benutzernamen (bis dahin nur der Benutzername)."""
    class _MitAnzeigename:
        username = "admin"
        display_name = "Ada Admin"

    def _kaputt(db, user):
        raise RuntimeError("simulierter DB-Fehler")

    monkeypatch.setattr(seitendaten, "resolve_account_display", _kaputt)
    assert pages_router_module._account_display(None, _MitAnzeigename()) == {"full_name": "Ada Admin", "initials": "AA"}


def test_account_display_global_falls_back_to_username_on_error(monkeypatch):
    class _FakeUser:
        username = "admin"

    def _boom(db, user):
        raise RuntimeError("simulierter DB-Fehler")

    monkeypatch.setattr(seitendaten, "resolve_account_display", _boom)
    result = pages_router_module._account_display(None, _FakeUser())
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
    env.globals["can"] = lambda current_user, *roles: current_user is not None and current_user.role in roles
    tmpl = env.get_template("project_folder.html")  # eine beliebige Seite, die beide Includes einbindet
    return tmpl.render(request=_FakeRequest("/x", user), app_version="1.0.0", project_id=1)


def test_topbar_appears_right_after_app_content_before_main():
    html = _render()
    content_idx = html.index('<div class="app-content">')
    topbar_idx = html.index('<div class="app-topbar">')
    main_idx = html.index("<main>")
    assert content_idx < topbar_idx < main_idx


def test_search_slot_carries_the_office_search_for_admin_and_office():
    """Schritt 3 (Suche) ist seit 1.3.67 gebaut (siehe CLAUDE.md "Büro-Suche") -- der seit 1.3.45
    reservierte Platz ist jetzt gefüllt, für admin/office."""
    for role in ("admin", "buero_auftrag"):
        class _RoleUser:
            pass
        user = _RoleUser()
        user.role = role
        user.display_name = "Test Nutzer"
        user.username = "test.nutzer"
        html = _render(user=user)
        start = html.index('<div class="app-topbar-search-slot">')
        end = html.index('<div class="app-konto">', start)  # seit 1.8.163 (bis dahin app-topbar-account)
        slot = html[start:end]
        assert 'id="appTopbarSearchInput"' in slot, role
        assert 'id="appTopbarSearchResults"' in slot, role


def test_search_slot_is_empty_for_field():
    """Die Büro-Suche rendert nicht für `field` -- kein nie funktionierendes Eingabefeld."""
    class _FieldUser:
        role = "field"
        display_name = "Monteur"
        username = "monteur"
    html = _render(user=_FieldUser())
    start = html.index('<div class="app-topbar-search-slot">')
    end = html.index('<div class="app-konto">', start)  # seit 1.8.163 (bis dahin app-topbar-account)
    slot = html[start:end]
    assert "appTopbarSearchInput" not in slot


def test_account_button_shows_initials_and_full_name_since_1_8_163():
    """Bis 1.8.162 ein runder Knopf nur mit den Initialen (Name erst im Menü). Seit 1.8.163 (Stufe 2 „Rahmen“, Teil 3): Initialen im
    Kreis und daneben der volle Name, im Knopf selbst; aria-label und title nennen den Namen auch, wo er schmal ausgeblendet ist."""
    html = _render(account={"full_name": "Tobias Rödchen", "initials": "TR"})
    start = html.rindex("<button", 0, html.index('id="appTopbarAccountBtn"'))
    knopf = html[start:html.index("</button>", start)]
    assert 'class="app-konto-knopf"' in knopf
    assert 'aria-label="Konto: Tobias Rödchen"' in knopf and 'title="Tobias Rödchen"' in knopf
    assert '<span class="app-konto-initialen" aria-hidden="true">TR</span>' in knopf
    assert '<span class="app-konto-name">Tobias Rödchen</span>' in knopf
    assert 'aria-haspopup="menu"' in knopf and 'aria-expanded="false"' in knopf and 'aria-controls="appTopbarAccountMenu"' in knopf


def test_account_menu_has_account_theme_and_logout_since_1_8_163():
    """Bis 1.8.162: Name als Überschrift, Mein Konto, Hell/Dunkel, Abmelden. Seit 1.8.163 steht der Name im Knopf; das Menü hat genau
    Mein Konto · Hell/Dunkel · Abmelden als Einträge des Bausteins (dsMenue(), Tastatur und aria -- in node geprüft in
    tests/test_v441_rahmen_baustein.py::test_dsmenue_tastatur_aria_und_schliessen)."""
    import re as _re
    html = _render(account={"full_name": "Tobias Rödchen", "initials": "TR"})
    start = html.rindex("<div", 0, html.index('id="appTopbarAccountMenu"'))
    kopf = html[start:html.index(">", start)]
    assert 'class="ds-menue"' in kopf and 'role="menu"' in kopf and " hidden" in kopf
    menu = html[start:html.index("</div>", html.index('id="appTopbarLogout"', start))]  # seit 1.8.167 mit dem Kopf (eigenes div) davor
    eintraege = _re.findall(r'<(a|button) [^>]*class="ds-menue-eintrag"[^>]*>(.*?)</\1>', menu, flags=_re.S)
    texte = [_re.sub(r"<[^>]+>", "", inhalt).strip() for _, inhalt in eintraege]
    assert texte == ["Mein Konto", "Hell/Dunkel", "Abmelden"]
    assert 'href="/account"' in menu and 'id="appThemeToggle"' in menu and 'id="appTopbarLogout"' in menu
    # seit 1.8.167 steht der Name im Menü nur im verborgenen Kopf, der erscheint, wenn der Knopf ihn kürzt (kein Menüeintrag)
    kopf = '<div class="ds-menue-kopf app-konto-vollname" id="appKontoVollname" role="presentation" hidden>Tobias Rödchen</div>'
    assert menu.count("Tobias Rödchen") == 1 and kopf in menu


def test_account_menu_is_wired_through_the_menu_baustein():
    """Das Kontomenü nutzt dsMenue() aus _menue.html (eine Umsetzung für Tastatur und aria), keine eigene Klick-Logik mehr."""
    vorlagen = Path(__file__).parents[1] / "app" / "templates"
    assert vorlagen_js.bindet_ein("_topbar.html", "_kontomenue.html", vorlagen, nur_selbst=True)
    assert vorlagen_js.bindet_ein("_kontomenue.html", "_menue.html", vorlagen, nur_selbst=True)
    konto = (vorlagen / "_kontomenue.html").read_text(encoding="utf-8")
    assert "dsMenue(knopf,menue)" in konto
    assert "localStorage.setItem('erp_theme'" in konto
    assert "speichern('abmelden',()=>fetch('/api/auth/logout',{method:'POST'}))" in konto


def test_no_account_button_when_not_authenticated():
    html = _render(user=None)
    assert 'id="appTopbarAccountBtn"' not in html
    assert 'id="appTopbarAccountMenu"' not in html
    # Die Leiste selbst bleibt trotzdem bestehen.
    assert '<div class="app-topbar">' in html


def test_topbar_is_sticky_and_uses_design_system_variables_only():
    """Seit 1.8.163 aus den --ds-*-Werten (bis dahin --card/--line der Seite) und ohne die Akzentfarbe -- die färbt die Oberfläche
    nicht mehr (Entscheidung Stufe 2)."""
    html = _render()
    assert ".app-topbar{position:sticky;top:0" in html
    assert "background:var(--ds-flaeche)" in html
    assert "border-bottom:1px solid var(--ds-linie)" in html
    for datei in ("_topbar.html", "_kontomenue.html"):
        text = (Path(__file__).parents[1] / "app" / "templates" / datei).read_text(encoding="utf-8")
        css = text[text.index("<style>"):text.index("</style>")]
        assert "--accent" not in css and "var(--card)" not in css and "var(--line)" not in css, datei
    # Keine im Hex-Code fest eingetragene, projektfremde Farbe im Topbar-Regelsatz -- "#fff" für
    # Text auf Akzentfarbe ist die bereits im ganzen Projekt etablierte Konvention (z. B.
    # settings.html: "button{background:var(--accent);color:#fff;...}"), keine neue Erfindung.
    topbar_css_start = html.index(".app-topbar{")
    topbar_css_end = html.index("</style>", topbar_css_start)
    topbar_css = html[topbar_css_start:topbar_css_end]
    assert topbar_css.count("#") == topbar_css.count("#fff")


def test_topbar_is_64px_with_a_480px_search_and_the_initials_in_aktion():
    """Vorgabe Stufe 2, Runde 1, Teil 3: Kopfzeile 64 px, Suche 480 px breit, Initialen im Kreis in --ds-aktion."""
    html = _render()
    regel = html[html.index(".app-topbar{"):html.index("}", html.index(".app-topbar{"))]
    assert "box-sizing:border-box" in regel and "height:64px" in regel
    assert ".app-topbar-search{position:relative;width:100%;max-width:480px}" in html
    kreis = html[html.index(".app-konto .app-konto-initialen{"):]
    kreis = kreis[:kreis.index("}")]
    assert "border-radius:50%" in kreis and "background:var(--ds-aktion)" in kreis and "color:var(--ds-auf-aktion)" in kreis


def test_page_button_rules_do_not_reach_the_head():
    """34 Seiten haben button:hover, eine button:active (Spezifität 0,1,1) -- eine Regel mit nur einer Klasse (0,1,0) verlöre gegen sie,
    der Kontoknopf färbte sich dann in der Akzentfarbe. Darum trägt jede Regel an einem Knopf oder Feld des Kopfs zwei Klassen, und
    ds.css hat :active für Knopf und Menüeintrag."""
    import re as _re
    vorlagen = Path(__file__).parents[1] / "app" / "templates"
    for datei in ("_topbar.html", "_kontomenue.html"):
        text = (vorlagen / datei).read_text(encoding="utf-8")
        css = _re.sub(r"/\*.*?\*/", "", text[text.index("<style>") + 7:text.index("</style>")], flags=_re.S)
        css = _re.sub(r"@media[^{]*\{", "", css)
        for selektoren in _re.findall(r"([^{}]+)\{", css):
            for sel in selektoren.split(","):
                if any(k in sel for k in ("app-konto-knopf", "app-topbar-menu-btn", "app-topbar-search input", "app-topbar-search-hit")):
                    assert len(_re.findall(r"\.[\w-]+", sel)) >= 2, (datei, sel.strip())
    ds = (Path(__file__).parents[1] / "app" / "static" / "ds" / "ds.css").read_text(encoding="utf-8")
    assert ".ds-menue-eintrag:active" in ds and ".ds-knopf:active" in ds and ".ds-knopf-aktion:active" in ds


def test_name_hidden_only_on_phones_and_only_in_the_office_topbar():
    """Unter 600 px nur die Initialen (Festlegung 1.8.163) -- in der Kopfzeile der Büroseiten; der Monteurskopf (Teil 4) bindet dasselbe
    Kontomenü ein und zeigt den Namen immer, darum steht die Regel in _topbar.html, nicht im Kontomenü."""
    vorlagen = Path(__file__).parents[1] / "app" / "templates"
    topbar = (vorlagen / "_topbar.html").read_text(encoding="utf-8")
    assert "@media(max-width:599px){.app-topbar .app-konto-name,.app-topbar .app-konto-pfeil{display:none}" in topbar
    assert "display:none" not in (vorlagen / "_kontomenue.html").read_text(encoding="utf-8").split("</style>")[0]


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
# Was unverändert bleibt: /mobil (bis 1.3.60 /vor-ort) bekommt keine Topbar
# ---------------------------------------------------------------------------

def test_mobile_header_does_not_include_topbar():
    """Seit 1.8.125 über bindet_ein() (auch nicht über ein Basis-Template), nicht per Textvergleich."""
    vorlagen = Path(__file__).parents[1] / "app" / "templates"
    assert not vorlagen_js.bindet_ein("_mobile_header.html", "_topbar.html", vorlagen)
    assert not vorlagen_js.bindet_ein("mobil.html", "_topbar.html", vorlagen)


# ---------------------------------------------------------------------------
# Projektweiter Konsistenz-Test: jede Seite mit _sidebar.html bekommt auch _topbar.html
# ---------------------------------------------------------------------------

def _seitenleiste_ohne_topbar() -> tuple[list[str], list[str]]:
    """(Seiten mit _sidebar.html, davon ohne _topbar.html) -- in der zusammengesetzten Seite: seit 1.8.124 (Stufe 0b) auch über ihr
    Basis-Template, auch in Unterordnern (tests/vorlagen_js.py::seiten(), zusammensetzen())."""
    vorlagen = Path(__file__).parents[1] / "app" / "templates"
    mit, ohne = [], []
    for seite in vorlagen_js.seiten(vorlagen):
        dateien = {d for _, _, d, _ in vorlagen_js.zusammensetzen(seite, wurzel=vorlagen)[1]}
        if "_sidebar.html" in dateien:
            mit.append(seite)
            if "_topbar.html" not in dateien:
                ohne.append(seite)
    return mit, ohne


def test_every_template_with_sidebar_also_includes_topbar():
    """Nur echte SEITEN geprüft, keine Partials (Dateien mit führendem "_") -- _topbar.html
    selbst erwähnt _sidebar.html im erklärenden Jinja-Kommentar (wo es eingebunden werden muss),
    was als reiner Text-Treffer sonst fälschlich mitgezählt würde, obwohl Jinja-Kommentare beim
    Rendern vollständig entfernt werden (kein Rekursionsrisiko wie beim 1.2.19-Fund in
    _debounce.html, dort ein JS-Kommentar statt eines Jinja-Kommentars -- hier bewusst geprüft,
    nicht nur angenommen). Seit 1.8.124 die zusammengesetzte Seite (zusammensetzen() liest keine Kommentare)."""
    assert _seitenleiste_ohne_topbar()[1] == []


def test_full_name_in_the_menu_when_the_button_shortens_it_since_1_8_167():
    """Nachrunde Punkt 3: ist der Name im Kontoknopf gekürzt („…“) oder ausgeblendet (Kopfzeile unter 600 px), steht er vollständig im
    Kontomenü -- in Kopfzeile und Monteurskopf, weil beide _kontomenue.html einbinden. Der Kopf darf umbrechen (kein „…“ im Menü) und ist
    kein Menüeintrag. Im Browser prüft das scripts/klicktest_rahmen.py (Teil „vollname“)."""
    konto = (Path(__file__).parents[1] / "app" / "templates" / "_kontomenue.html").read_text(encoding="utf-8")
    assert "nameImKnopf.offsetWidth===0||nameImKnopf.scrollWidth>nameImKnopf.clientWidth" in konto
    assert "vollname.hidden=!gekuerzt()" in konto and "window.addEventListener('resize',vollnameZeigen)" in konto
    assert ".app-konto .app-konto-vollname{white-space:normal;" in konto
    kopf = konto[konto.index('id="appKontoVollname"') - 60:konto.index('id="appKontoVollname"')]
    assert "ds-menue-eintrag" not in kopf

