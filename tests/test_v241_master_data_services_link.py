"""Version 1.3.25 -- Punkt 1: "Leistungen ansehen" (Stammdaten -> Leistungskataloge) führte auf
die Startseite (`/?catalog_id=<id>`), ein Ziel, das diesen Parameter nirgends auswertet.

Ursprünglich als fehlendes Ziel diagnostiziert und dafür eine neue "Leistungen"-Ansicht in
master_data.html gebaut -- bei der Sidebar-Bestandsaufnahme zu Punkt 2 dann aber festgestellt,
dass unter `/leistungskatalog` (app/templates/index.html, Sidebar-Eintrag "Leistungskatalog")
bereits eine vollständige, deutlich reichhaltigere Leistungsverwaltung existiert (Suche,
Bearbeiten-Link, Verschieben/Kopieren zwischen Katalogen, Kalkulationsdetail, XML-Import) --
inklusive eines bereits funktionierenden `?catalog_id=`-Parameters. Der eigentliche Fehler war
also ein fehlendes Pfadsegment (`/` statt `/leistungskatalog`), keine fehlende Seite. Die zuvor
gebaute, redundante Ansicht wurde deshalb wieder entfernt -- diese Datei prüft die tatsächliche,
minimale Korrektur. Zwei weitere Vorkommen desselben Fehlers in `service_form.html` (Redirect
nach dem Speichern) beim Durchsuchen der Stammdatenverwaltung gefunden und im selben Zug
behoben, da sie auf dasselbe Ziel zeigen sollen."""

from pathlib import Path

TEMPLATES = Path(__file__).parents[1] / "app" / "templates"


def test_master_data_links_services_to_the_existing_leistungskatalog_page():
    html = (TEMPLATES / "master_data.html").read_text(encoding="utf-8")
    assert "/?catalog_id=" not in html
    assert "/leistungskatalog?catalog_id=${x.id}" in html


def test_master_data_did_not_grow_a_redundant_services_view():
    """index.html (/leistungskatalog) deckt das bereits vollständig ab -- eine zweite,
    einfachere Ansicht in master_data.html wäre unnötige Duplikation."""
    html = (TEMPLATES / "master_data.html").read_text(encoding="utf-8")
    assert "current==='services'" not in html
    assert "moveOrCopyService" not in html


def test_service_form_redirects_to_the_existing_leistungskatalog_page():
    html = (TEMPLATES / "service_form.html").read_text(encoding="utf-8")
    assert "/?catalog_id=" not in html
    assert html.count("/leistungskatalog?catalog_id=") == 2


def test_leistungskatalog_page_already_supports_the_catalog_id_parameter():
    """Regression/Beleg: das Ziel existierte bereits und wertet den Parameter tatsächlich aus --
    der Fehler war ein fehlendes Pfadsegment, keine fehlende Seite."""
    html = (TEMPLATES / "index.html").read_text(encoding="utf-8")
    assert "urlParams.get('catalog_id')" in html
