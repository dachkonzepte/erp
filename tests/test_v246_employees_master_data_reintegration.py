"""Version 1.3.30 -- Mitarbeiter wird ein regulärer Stammdatenbereich, drei gemeldete
Abweichungen vom sonstigen Muster behoben:

1. Die Stammdaten-Navigationsleiste fehlte auf der eigenständigen /employees-Seite (nur ein
   Zurück-Link). Da Mitarbeiter jetzt ein `current`-Bereich in `master_data.html` ist wie jeder
   andere, trägt er automatisch dieselbe `.side`-Navigationsleiste -- kein Sonderfall mehr, kein
   Zurück-Link nötig.
2. Anlegen/Bearbeiten öffneten ein Formular unterhalb der Liste statt einer eigenen Seite.
   Mitarbeiter läuft jetzt über `master_data_form.html`, exakt wie Teams/Lieferanten/Fuhrpark/
   Materialien -- `/master-data/employees/new` bzw. `/master-data/employees/{id}/edit`.
3. Geprüft (vor dem Bauen, siehe Chatverlauf), ob sich /employees ganz in das bestehende Muster
   einfügen lässt (Weg a) oder eigenständig bleiben muss (Weg b): kein Feld, kein Endpunkt und
   keine Interaktion gefunden, die sich in `master_data_form.html` nicht sinnvoll unterbringen
   lässt -- Weg (a) gewählt. Der Vergütungsrechner zerfällt sauber in zwei Teile: die
   aggregierten Kennzahlen (gewichteter Mittellohn, Mitarbeiterzahl je Kosten-Zuordnung) sind
   reine Client-Berechnung aus dem bereits geladenen `employees`-Array und wandern in
   `master_data.html`s Listenansicht; die Live-Vorschau des kalkulatorischen Stundenlohns
   (aktualisiert sich beim Tippen) ist reine Formular-JS-Logik und wandert unverändert in
   `master_data_form.html`s neue `employeeForm()`.

`employees.html` und die eigenständige Route `/employees` entfallen vollständig. Der
Kalkulationsgrundlagen-Link in `settings.html` zeigt bewusst wieder auf `/master-data#employees`
(die 1.3.28-Korrektur auf `/employees` wird zurückgenommen, weil dieses Ziel jetzt wieder
existiert -- keine wiedereingeschleppte Regression, siehe test_v244)."""

from pathlib import Path

ROOT = Path(__file__).parents[1]
TEMPLATES = ROOT / "app" / "templates"


def _master_data() -> str:
    return (TEMPLATES / "master_data.html").read_text(encoding="utf-8")


def _form() -> str:
    return (TEMPLATES / "master_data_form.html").read_text(encoding="utf-8")


def _pages() -> str:
    return (ROOT / "app" / "routers" / "pages.py").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Punkt 1: eigene Seite/Route entfällt, Mitarbeiter ist ein regulärer Bereich
# ---------------------------------------------------------------------------

def test_employees_html_and_its_route_are_gone():
    assert not (TEMPLATES / "employees.html").exists()
    pages = _pages()
    assert '"/employees"' not in pages
    assert "def employees_page" not in pages


def test_master_data_carries_the_standard_side_navigation_for_employees():
    """Mitarbeiter ist ein `current`-Bereich wie jeder andere -- die .side-Navigationsleiste mit
    allen Bereichen ist automatisch vorhanden, kein eigener Zurück-Link nötig oder vorhanden."""
    html = _master_data()
    assert "data-view=\"employees\" onclick=\"showView('employees')\">Mitarbeiter<" in html
    # Dieselbe Navigationsleiste zeigt weiterhin alle uebrigen Bereiche.
    for other in ["Kunden", "Objekte", "Kolonnen / Teams", "Fuhrpark & Maschinen", "Lieferanten"]:
        assert other in html
    assert "class=\"side\"" in html


def test_employees_shows_the_list_first_like_every_other_area():
    html = _master_data()
    branch_start = html.index("current==='employees'")
    branch = html[branch_start:html.index(" else if(current==='teams')")]
    assert "table(" in branch
    assert "employeeForm" not in branch  # kein eingebettetes Formular in der Liste


def test_employees_list_is_loaded_like_every_other_area():
    html = _master_data()
    assert "api('/api/employees')" in html
    assert "let customers=[],properties=[],employees=[]," in html


# ---------------------------------------------------------------------------
# Punkt 2: Anlegen/Bearbeiten öffnen eine eigene Formularseite
# ---------------------------------------------------------------------------

def test_add_button_and_edit_links_point_to_the_dedicated_form_page():
    html = _master_data()
    assert "add.href='/master-data/employees/new'" in html
    assert "/master-data/employees/${x.id}/edit" in html


def test_page_routes_accept_employees_for_create_and_edit():
    pages = _pages()
    create_fn = pages[pages.index("def master_data_create_page"):]
    create_fn = create_fn[:create_fn.index("\n\n")]
    edit_fn = pages[pages.index("def master_data_edit_page"):]
    edit_fn = edit_fn[:edit_fn.index("\n\n")]
    assert '"employees"' in create_fn
    assert '"employees"' in edit_fn


def test_form_page_renders_the_employee_form():
    form = _form()
    assert "function employeeForm()" in form
    assert "type==='employees'" in form
    assert "el('heading').textContent=editing?'Mitarbeiter bearbeiten':'Mitarbeiter anlegen'" in form


# ---------------------------------------------------------------------------
# Punkt 3: nichts verloren beim Umzug in master_data_form.html
# ---------------------------------------------------------------------------

def test_compensation_calculator_moved_into_the_form_page():
    form = _form()
    assert "function syncCompensation()" in form
    assert 'id="effectiveWage"' in form and 'id="wageFormula"' in form
    assert "laborRateSettings" in form
    assert "/api/labor-rate-settings" in form


def test_aggregate_wage_metrics_moved_into_the_list_page():
    """Der andere Teil des Vergütungsrechners -- die Kennzahlen ueber ALLE Mitarbeiter -- ist
    reine Client-Berechnung aus der Liste, kein Formular-Feature, und gehoert deshalb in
    master_data.html, nicht in master_data_form.html."""
    html = _master_data()
    assert "MA im Verrechnungssatz" in html
    assert "Gewichteter Mittellohn" in html
    assert "MA in variablen GK" in html


def test_show_on_planning_board_preserved():
    form = _form()
    assert 'id="showOnPlanningBoard"' in form
    assert "show_on_planning_board:el('showOnPlanningBoard').checked" in form
    html = _master_data()
    assert "show_on_planning_board" in html


def test_all_other_employee_fields_preserved_in_the_form():
    form = _form()
    for field_id in [
        "employeeNumber", "activeSelect", "availableAsCaseworker", "firstName", "lastName",
        "functionId", "weeklyHours", "compensationType", "costAllocation", "hourlyWage",
        "monthlySalary", "street", "postalCode", "city", "country", "phone", "mobile",
        "email", "birthday", "importantInfo",
    ]:
        assert f'id="{field_id}"' in form, field_id


def test_save_builds_a_valid_employee_payload_and_the_generic_name_check_does_not_block_it():
    """save()'s allgemeine Pflichtfeldpruefung haengt an body.name -- Mitarbeiter hat kein
    `name`-Feld (nur first_name/last_name), muss deshalb explizit ausgenommen werden. Seit dem
    Adressimport (CLAUDE.md "Adressimport aus dem Altsystem") gilt dieselbe Ausnahme auch für
    Kunden (last_name statt name); seit der Betriebsmittelverwaltung (1.4.0) ebenso für
    Assets (name bleibt NULL, wenn ein Ressourcenbezug gewählt ist -- geprüft ist das bereits
    serverseitig über den Pydantic-Validator)."""
    form = _form()
    assert "if(!body.name&&type!=='employees'&&type!=='customers'&&type!=='assets')throw Error" in form
    assert "type==='employees'&&(!body.first_name||!body.last_name)" in form
    assert "url=editing?`/api/employees/${recordId}`:'/api/employees'" in form


def test_settings_link_points_back_to_master_data_hash_employees():
    settings = (TEMPLATES / "settings.html").read_text(encoding="utf-8")
    assert 'href="/master-data#employees"' in settings
