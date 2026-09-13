"""Version 1.3.27 -- letzter Schritt des Sidebar-Aufräumens: die Lücke aus 1.3.25/1.3.26
schließen, damit "Leistungskatalog" aus der Sidebar entfallen kann.

Vor dem Bauen geprüft (siehe Chatverlauf): eine neue, eigene Ansicht in den Stammdaten war NICHT
nötig -- `/leistungskatalog` (`app/templates/index.html`) funktioniert bereits ohne `catalog_id`
sinnvoll (XML-Import, Kalkulationsvorgaben-Verweis, katalogübergreifende Leistungsliste inkl.
Suche/Verschieben/Kopieren laufen alle unabhängig vom Parameter). "Leistungen ansehen" verlinkte
bereits seit 1.3.25 korrekt auf `/leistungskatalog?catalog_id=<id>`.

Umgesetzt stattdessen: (1) der Sidebar-Eintrag "Leistungskatalog" entfällt, (2) die
Stammdaten-Katalogliste bekommt einen zusätzlichen Link für den parameterlosen Einstieg (Suche,
XML-Import), nach demselben Muster, das die Materialkataloge-Ansicht für "alle Materialien
anzeigen" bereits nutzt, (3) `/leistungskatalog` bekommt eine Rückwärtsnavigation zu den
Stammdaten (Muster `/employees` aus 1.3.26), da die Seite jetzt nur noch von dort aus erreichbar
ist.

Zusätzlich ein bei der Prüfung gemeldeter Randbefund behoben (auf Nutzerwunsch im selben Zug):
sowohl die Leistungsliste (`index.html`) als auch die Materialliste (`master_data.html`) hatten
eine mit "Katalog" beschriftete Tabellenspalte, die tatsächlich Aktionen (Bearbeiten/Verschieben/
Kopieren) zeigte, nicht den Herkunftskatalog der Zeile -- beim jetzt neu hinzukommenden,
katalogübergreifenden Durchsuchen ohne `catalog_id` fehlte dadurch eine sichtbare Zuordnung.
`ServiceListOut.catalog_name` existierte bereits seit 1.3.24; für Materialien wird der Name
client-seitig aus dem ohnehin bereits geladenen `materialGroups`-Array aufgelöst (Muster
`customerName()`)."""

from pathlib import Path

TEMPLATES = Path(__file__).parents[1] / "app" / "templates"


def test_sidebar_no_longer_lists_leistungskatalog_separately():
    html = (TEMPLATES / "_sidebar.html").read_text(encoding="utf-8")
    assert 'href="/leistungskatalog"' not in html
    assert ">Leistungskatalog<" not in html


def test_master_data_catalog_list_links_to_the_parameterless_entry_point():
    html = (TEMPLATES / "master_data.html").read_text(encoding="utf-8")
    assert 'href="/leistungskatalog">Leistungen durchsuchen' in html
    # bereits seit 1.3.25 korrekt -- hier nur als Regression mitgeprüft.
    assert "/leistungskatalog?catalog_id=${x.id}" in html


def test_leistungskatalog_page_has_back_link_to_master_data():
    html = (TEMPLATES / "index.html").read_text(encoding="utf-8")
    assert "← Stammdaten" in html
    assert "history.back()" in html


def test_service_list_shows_real_catalog_name_and_relabels_the_action_column():
    html = (TEMPLATES / "index.html").read_text(encoding="utf-8")
    assert "<th>Katalog</th><th>Verschieben / Kopieren</th>" in html
    assert "esc(s.catalog_name||'—')" in html


def test_material_list_shows_real_catalog_name_and_relabels_the_action_column():
    html = (TEMPLATES / "master_data.html").read_text(encoding="utf-8")
    assert "function materialGroupName(id)" in html
    assert "esc(materialGroupName(x.catalog_id))" in html
    assert "'Herkunft','Katalog','','Verschieben / Kopieren'" in html
