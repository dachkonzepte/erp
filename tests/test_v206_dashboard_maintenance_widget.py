from pathlib import Path


def _dashboard_html() -> str:
    return (Path(__file__).parents[1] / "app/templates/dashboard.html").read_text(encoding="utf-8")


def test_due_maintenance_widget_registered():
    html = _dashboard_html()
    assert "due_maintenance:{label:'Fällige Wartungen',render:renderDueMaintenanceWidget}" in html


def test_due_maintenance_widget_checks_module_and_due_flag():
    html = _dashboard_html()
    assert "isModuleEnabled('wartungen')" in html
    assert "/api/maintenance-contracts" in html
    # Seit 1.2.15: Verträge mit aktiven Positionen zeigen ihre einzelnen fälligen/überfälligen
    # Positionen statt einer einzigen Vertrags-Zeile -- Verträge ohne Positionen unverändert
    # über c.is_due wie zuvor.
    assert "c.is_due" in html
    assert "i.is_due||i.is_overdue" in html


def test_due_maintenance_widget_not_forced_into_default_layout():
    """Wie bei anderen optionalen Modulen: neu in der Registry, aber nicht automatisch in
    jedem bestehenden Dashboard sichtbar -- ein Nutzer fügt es bewusst über
    '+ Widget hinzufügen' hinzu."""
    html = _dashboard_html()
    default_layout = html.split("const DEFAULT_LAYOUT=", 1)[1].split(";", 1)[0]
    assert "due_maintenance" not in default_layout
