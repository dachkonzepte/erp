from pathlib import Path


def test_master_data_hub_and_forms_exist():
    root = Path(__file__).parents[1]
    main = (root / "app" / "main.py").read_text(encoding="utf-8") + "".join(p.read_text(encoding="utf-8") for p in sorted((root / "app" / "routers").glob("*.py")))
    html = (root / "app" / "templates" / "master_data.html").read_text(encoding="utf-8")
    form = (root / "app" / "templates" / "master_data_form.html").read_text(encoding="utf-8")
    assert '@router.get("/master-data"' in main
    assert '@router.get("/master-data/{data_type}/new"' in main
    for label in ["Kunden", "Objekte", "Mitarbeiter", "Leistungskataloge"]:
        assert label in html
    assert "+ Hinzufügen" in html
    assert "Kundennummer" in form
    # Mitarbeiter ist seit 1.3.30 wieder ein regulärer Stammdatenbereich wie jeder andere
    # (die zwischenzeitliche 1.3.26-Auslagerung auf eine eigene /employees-Seite wurde
    # zurückgenommen, siehe CLAUDE.md "Mitarbeiter-Formular: ein Bereich statt zwei Ähnlicher") --
    # der "Mitarbeiter"-Knopf schaltet wie alle anderen nur die Ansicht innerhalb dieser Seite um,
    # das Formular lebt in master_data_form.html.
    assert "Funktion / Tätigkeit" in form
    assert "data-view=\"employees\" onclick=\"showView('employees')\"" in html


def test_project_document_hub_exists():
    root = Path(__file__).parents[1]
    main = (root / "app" / "main.py").read_text(encoding="utf-8") + "".join(p.read_text(encoding="utf-8") for p in sorted((root / "app" / "routers").glob("*.py")))
    html = (root / "app" / "templates" / "projects.html").read_text(encoding="utf-8")
    assert '@router.get("/api/quotes")' in main
    assert "Projekte" in html
    assert "Angebot" in html
    assert "/projects/new" in html
    assert "/quotes/new" in html


def test_project_hub_dropped_the_left_tab_box_since_1_3_71_rebuild():
    """Seit "Runde 2 der Projektliste" (siehe CLAUDE.md "Umbau der Projektliste") entfällt
    der linke Reiter-Kasten "Projekte & Vorgänge" (Angebote/Aufträge/Anfragen/Mustervorgänge)
    -- die eigenständigen /quotes- und /orders-Listenseiten gab es nie (nur die API-Endpunkte,
    projektübergreifend nur über diese Reiter erreichbar), "Anfragen" hatte mit /inquiries
    bereits eine eigenständige Seite (redundanter Reiter). Die Projektliste nutzt seither die
    volle Breite, mit Liste/Kanban-Umschalter statt der alten Reiter."""
    html = (Path(__file__).parents[1] / "app" / "templates" / "projects.html").read_text(encoding="utf-8")
    assert "showView" not in html
    assert "Projekte &amp; Vorgänge" not in html
    assert "Auftragsbestätigungen" not in html
    assert "Nur Mustervorgänge" in html
    assert "setView('kanban')" in html
    assert "erp_project_view" in html
    assert "categoryFilter" in html
    assert "pipeline-column" in html
