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
    # "Rechnungen" bewusst nicht mehr in dieser Liste: der Platzhalter-Tab wurde in
    # 1.0.42 entfernt, Rechnungen haben seither ihren eigenen Platz (Finanzen,
    # Rechnungen-Reiter je Projektmappe), nicht mehr in dieser projektübergreifenden Liste.
    for label in ["Projekte", "Angebote", "Auftragsbestätigungen", "Anfragen"]:
        assert label in html
    assert "/projects/new" in html
    assert "/quotes/new" in html
