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

def test_sidebar_has_labeled_stammdaten_and_system_groups_in_order():
    html = (TEMPLATES / "_sidebar.html").read_text(encoding="utf-8")
    stammdaten_group = html.index('class="app-sidebar-group">Stammdaten<')
    system_group = html.index('class="app-sidebar-group">System<')
    master_data_link = html.index('href="/master-data"')
    settings_link = html.index('href="/settings"')
    assert stammdaten_group < master_data_link < system_group < settings_link


# ---------------------------------------------------------------------------
# Punkt 4: Backoffice bleibt bei Zeiterfassung
# ---------------------------------------------------------------------------

def test_backoffice_stays_directly_after_time_tracking_as_a_sub_item():
    html = (TEMPLATES / "_sidebar.html").read_text(encoding="utf-8")
    time_tracking = html.index('href="/time-tracking"')
    backoffice = html.index('href="/time-backoffice"')
    stammdaten_group = html.index('class="app-sidebar-group">Stammdaten<')
    assert time_tracking < backoffice < stammdaten_group
    # Bleibt ein sichtbar eingerueckter Unterpunkt, kein gleichrangiger Haupteintrag.
    body = html[max(0, backoffice - 200):backoffice]
    assert "app-sidebar-sub" in body
