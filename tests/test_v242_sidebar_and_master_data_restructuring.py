"""Version 1.3.26 -- Sidebar aufräumen, nach dem in 1.3.25 vorgelegten und vom Nutzer
bestätigten Befund (vier Anmerkungen):

1. Mitarbeiter: Stammdaten -> Mitarbeiter zeigte auf /employees (die damals reichhaltigere
   Oberfläche) statt auf ein eigenes, schlankeres Formular in master_data_form.html; der
   Sidebar-Eintrag "Mitarbeiter" entfiel. **Seit 1.3.30 bewusst wieder zurückgenommen** --
   /employees zeigte beim Einstieg direkt das Anlegeformular statt der Liste (1.3.29-Befund);
   die anschließende Prüfung (CLAUDE.md "Mitarbeiter-Formular: ein Bereich statt zwei
   Ähnlicher") ergab, dass sich der Vergütungsrechner vollständig in master_data_form.html
   unterbringen lässt -- Mitarbeiter ist seither ein regulärer master_data.html-Bereich wie
   jeder andere, /employees und die eigene employees.html existieren nicht mehr. Die
   zugehörigen Tests dieses Punktes stehen jetzt in
   tests/test_v246_employees_master_data_reintegration.py, nicht mehr hier.
2. Leistungskatalog bleibt vorerst in der Sidebar (Lücke -- Leistungen-Ansicht + XML-Import --
   wird in einem eigenen, spaeteren Schritt geschlossen, siehe CLAUDE.md). Die dabei zunächst
   vermutete zweite Lücke (globale Kalkulationsvorgaben) stellte sich als echtes Duplikat
   heraus, nicht als getrennter Datensatz -- die Kalkulationsvorgaben-Karte in /leistungskatalog
   entfällt deshalb bereits jetzt zugunsten eines Verweises auf Einstellungen.
3. Die beiden Gruppen am Ende der Sidebar ("Stammdaten"/"System") bekommen sichtbare
   Überschriften nach dem Muster von settings.html.
4. Backoffice bleibt bei Zeiterfassung (taeglich) -- admin-only ist eine Sichtbarkeits-, keine
   Haeufigkeitsfrage, und es sitzt bereits als Unterpunkt dort."""

from pathlib import Path

TEMPLATES = Path(__file__).parents[1] / "app" / "templates"


# ---------------------------------------------------------------------------
# Punkt 2: Kalkulationsvorgaben-Duplikat in /leistungskatalog entfaellt
# ---------------------------------------------------------------------------

def test_leistungskatalog_no_longer_has_its_own_calculation_settings_editor():
    html = (TEMPLATES / "index.html").read_text(encoding="utf-8")
    assert "saveSettings" not in html
    assert 'id="setLabor"' not in html
    assert "/settings#calculation" in html


def test_settings_still_has_the_one_true_calculation_settings_editor():
    html = (TEMPLATES / "settings.html").read_text(encoding="utf-8")
    assert "saveCalculation" in html
    assert "data-settings-section=\"calculation\"" in html


# ---------------------------------------------------------------------------
# Punkt 3: sichtbare Gruppenueberschriften
# ---------------------------------------------------------------------------

def test_sidebar_has_labeled_verwaltung_group_with_stammdaten_and_settings():
    """Bis 1.8.161 je eine Gruppe "Stammdaten" und "System"; seit 1.8.162 (vier Gruppen) beide in "Verwaltung"."""
    html = (TEMPLATES / "_sidebar.html").read_text(encoding="utf-8")
    verwaltung_group = html.index('class="app-sidebar-group">Verwaltung<')
    master_data_link = html.index('href="/master-data"')
    settings_link = html.index('href="/settings"')
    assert verwaltung_group < master_data_link < settings_link
    assert 'class="app-sidebar-group">Stammdaten<' not in html and 'class="app-sidebar-group">System<' not in html


# ---------------------------------------------------------------------------
# Punkt 4: Backoffice bleibt bei Zeiterfassung
# ---------------------------------------------------------------------------

def test_zeiten_am_ende_der_gruppe_kaufmaennisch():
    """Bis 1.8.111 ein eingerückter Unterpunkt der Zeiterfassung. Seit 1.8.112 (neue Ordnung, Gruppen mit Überschrift): Zeiterfassung und Backoffice bilden die Gruppe "Personal" --
    Backoffice steht direkt nach der Zeiterfassung, als gleichrangiger Eintrag der Gruppe statt eingerückt. Seit 1.8.162 (vier Gruppen)
    stehen beide am Ende der Gruppe "Kaufmännisch", vor "Verwaltung". Seit 1.9.98 ersetzt sie ein Eintrag „Zeiten“, an derselben Stelle."""
    html = (TEMPLATES / "_sidebar.html").read_text(encoding="utf-8")
    kaufmaennisch_group = html.index('class="app-sidebar-group">Kaufmännisch<')
    zeiten = html.index('href="/zeiten"')
    verwaltung_group = html.index('class="app-sidebar-group">Verwaltung<')
    assert kaufmaennisch_group < zeiten < verwaltung_group
    assert 'href="/' not in html[zeiten + 1:verwaltung_group]  # der letzte Eintrag der Gruppe
    assert 'href="/time-tracking"' not in html and 'href="/time-backoffice"' not in html
    body = html[max(0, zeiten - 200):zeiten]
    assert "app-sidebar-sub" not in body
