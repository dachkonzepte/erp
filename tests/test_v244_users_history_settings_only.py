"""Version 1.3.28 -- vierter Fall derselben Aufräumreihe (nach Leistungskatalog, Mitarbeitern,
Kalkulationsvorgaben): "Benutzer" und "Änderungshistorie" verschwinden aus der Sidebar.

Anders als bei Mitarbeitern/Kalkulationsvorgaben gab es hier keine zwei konkurrierenden
Bearbeitungsoberflächen zum Vergleichen -- `settings.html` hatte für beide nie einen eigenen
Datenbereich, nur einen reinen Navigationslink (`<a href="/users">`/`<a href="/history">`) zu den
bereits bestehenden, alleinigen Seiten `users.html`/`history.html`. Die "vollständigere
Oberfläche" ist deshalb trivial die jeweils einzige echte Seite -- sie bleibt bestehen und wird
(wie schon vorher) von den Einstellungen aus verlinkt; neu ist nur die Rückwärtsnavigation
("← Einstellungen", Muster `/employees`/1.3.26 und `/leistungskatalog`/1.3.27) und der Wegfall
des Sidebar-Direktlinks.

Dabei zwei Nebenbefunde: (1) ein bei der 1.3.26-Mitarbeiter-Migration liegen gebliebener toter
Link in `settings.html` (`/master-data#employees` -- der Hash-View existiert seit 1.3.26 nicht
mehr) wurde auf `/employees` korrigiert -- seit 1.3.30 bewusst wieder zurückgedreht, weil
Mitarbeiter seither wieder ein regulärer master_data.html-Bereich ist und `#employees` damit
wieder existiert (siehe test_v246). (2) `/time-backoffice` ist ebenfalls doppelt verlinkt
(Sidebar + Einstellungen), bleibt aber bewusst unverändert -- es sitzt in der TÄGLICHEN
Sidebar-Gruppe (1.3.26-Entscheidung: fachlich Tagesgeschäft), nicht wie Benutzer/Historie in der
System-Gruppe, passt also nicht zu diesem Muster."""

from pathlib import Path

TEMPLATES = Path(__file__).parents[1] / "app" / "templates"


def test_sidebar_no_longer_links_users_or_history_directly():
    html = (TEMPLATES / "_sidebar.html").read_text(encoding="utf-8")
    assert 'href="/users"' not in html
    assert 'href="/history"' not in html
    assert ">Benutzer<" not in html
    assert ">Änderungshistorie<" not in html


def test_settings_still_links_to_both_dedicated_pages():
    html = (TEMPLATES / "settings.html").read_text(encoding="utf-8")
    assert 'href="/users"' in html
    assert 'href="/history"' in html


def test_users_and_history_pages_have_back_link_to_settings():
    users = (TEMPLATES / "users.html").read_text(encoding="utf-8")
    history = (TEMPLATES / "history.html").read_text(encoding="utf-8")
    assert "← Einstellungen" in users and "history.back()" in users
    assert "← Einstellungen" in history and "history.back()" in history


def test_master_data_employees_hash_link_restored_since_1_3_30():
    """Seit 1.3.26 existierte die Ansicht '#employees' in master_data.html nicht mehr (Mitarbeiter
    lebten auf /employees) -- dieser Link in den Kalkulationsgrundlagen wurde damals hier auf
    /employees korrigiert. Seit 1.3.30 ist Mitarbeiter wieder ein regulärer master_data.html-
    Bereich (siehe CLAUDE.md "Mitarbeiter-Formular: ein Bereich statt zwei Ähnlicher") --
    '#employees' existiert damit wieder, der Link zeigt bewusst erneut dorthin. Keine
    wiedereingeschleppte Regression, sondern dieselbe Korrektur, nur mit umgekehrtem Zielzustand."""
    html = (TEMPLATES / "settings.html").read_text(encoding="utf-8")
    assert 'href="/master-data#employees"' in html
    assert 'href="/employees"' not in html


def test_time_backoffice_double_link_stays_untouched():
    """Bewusst nicht angefasst: /time-backoffice sitzt in der täglichen Sidebar-Gruppe
    (1.3.26), nicht in der System-Gruppe wie Benutzer/Historie -- kein Fall desselben Musters."""
    sidebar = (TEMPLATES / "_sidebar.html").read_text(encoding="utf-8")
    settings = (TEMPLATES / "settings.html").read_text(encoding="utf-8")
    assert 'href="/time-backoffice"' in sidebar
    assert 'href="/time-backoffice"' in settings
