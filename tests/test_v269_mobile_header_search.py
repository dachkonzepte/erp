"""Version "Dateiablage je Objekt", Schritt 3, Nachtrag (nach 1.3.64) -- zwei Anpassungen an der
Monteurs-Suche (siehe CLAUDE.md "Suche als Einstieg"). Punkt 1 (Kundenname in den Vorschlägen)
ist in tests/test_v268_property_search.py abgedeckt. Diese Datei deckt Punkt 2 ab: die Suche
wandert von mobil.html in die gemeinsame Kopfzeile (_mobile_header.html), damit sie von jeder
Seite der Monteursansicht aus erreichbar ist -- rein strukturelle Prüfungen an den
Template-Quellen, da JS-Interaktion/CSS-Layout ohne echten Browser nicht ausführbar ist
(dieselbe, wiederholt dokumentierte Werkzeug-Einschränkung dieser Umgebung, siehe CLAUDE.md)."""

from pathlib import Path

from tests import vorlagen_js

TEMPLATES = Path(__file__).parents[1] / "app" / "templates"


def _read(name):
    return (TEMPLATES / name).read_text(encoding="utf-8")


def test_search_lives_in_mobile_header_not_in_mobil_page():
    header = _read("_mobile_header.html")
    mobil = _read("mobil.html")
    assert 'id="mobileObjectSearch"' in header
    assert 'id="mobileObjectSearchResults"' in header
    assert "/api/field-view/properties/search" in header
    # War vorher auf mobil.html gebunden -- muss dort jetzt vollständig fehlen, sonst erschiene
    # das Suchfeld doppelt (einmal aus der Kopfzeile, einmal aus der Seite selbst).
    for token in ("mobileObjectSearch", "objectSearch", "search-wrap", "/api/field-view/properties/search"):
        assert token not in mobil, f"{token!r} sollte nicht mehr in mobil.html stehen"


def test_debounce_helper_included_exactly_once_via_mobile_header():
    assert vorlagen_js.bindet_ein("_mobile_header.html", "_debounce.html", TEMPLATES)  # seit 1.8.125 nicht per Textvergleich
    # Keines der vier Templates, die _mobile_header.html einbinden, darf den Helfer zusätzlich
    # selbst einbinden -- sonst wäre `debounce` doppelt definiert (harmlos in JS, aber ein Zeichen
    # für auseinanderlaufende Konventionen).
    # Seit 1.8.124 (Stufe 0b): eingebunden selbst oder im Basis-Template der Seite (tests/vorlagen_js.py::bindet_ein()).
    for name in ("mobil.html", "mobil_objekt.html", "field_timesheet.html", "time_tracking_field.html"):
        assert vorlagen_js.bindet_ein(name, "_mobile_header.html", TEMPLATES), f"{name} bindet die Kopfzeile nicht ein"
        assert not vorlagen_js.bindet_ein(name, "_debounce.html", TEMPLATES), f"{name} bindet den Debounce-Helfer doppelt ein"


def test_every_mobile_page_gets_the_search_bar_for_free():
    """Punkt 2 der Anfrage: die Suche muss von JEDER Seite der Monteursansicht aus erreichbar
    sein, nicht nur von /mobil -- da alle vier Seiten _mobile_header.html einbinden, erreicht sie
    das automatisch, ohne dass jede Seite das Suchfeld einzeln nachbauen müsste."""
    for name in ("mobil.html", "mobil_objekt.html", "field_timesheet.html", "time_tracking_field.html"):
        assert vorlagen_js.bindet_ein(name, "_mobile_header.html", TEMPLATES), name


def test_search_opens_from_the_magnifier_below_the_header_since_1_8_164():
    """Bis 1.8.163 eine eigene Zeile unter dem Kopf (Kopf 173 px). Seit 1.8.164 öffnet die Lupe (48 px) im einzeiligen Kopf das Feld als
    Fläche unter dem Kopf: Feld und Vorschläge in EINER Fläche, absolut am sticky-Wrapper (top:100%) -- sie liegt unter der ganzen
    Kopfzeile samt Reitern, überlagert die Reiter also nie."""
    header = _read("_mobile_header.html")
    wrap_start = header.index('id="mobileHeaderWrap"')
    lupe = header[header.rindex("<button", 0, header.index('id="mobileSearchToggle"')):]
    lupe = lupe[:lupe.index(">")]
    assert 'aria-controls="mobileSearchPanel"' in lupe and 'aria-expanded="false"' in lupe and 'aria-label="Objekt suchen"' in lupe
    nav_end = header.index("</nav>", wrap_start)
    panel_pos = header.index('id="mobileSearchPanel"', wrap_start)
    input_pos = header.index('id="mobileObjectSearch"', wrap_start)
    results_pos = header.index('id="mobileObjectSearchResults"', wrap_start)
    wrap_end = header.index("</div>\n<script>", wrap_start)
    assert nav_end < panel_pos < input_pos < results_pos < wrap_end
    panel_tag = header[header.rindex("<div", 0, panel_pos):header.index(">", panel_pos)]
    assert " hidden" in panel_tag
    regel = header.split(".mobile-header-wrap .mobile-suche{")[1].split("}")[0]
    assert "position:absolute" in regel and "top:100%" in regel
    assert "lupe.focus()" in header and "searchInput.focus()" in header  # Fokus ins Feld, Escape zurück an die Lupe


def test_search_bar_has_a_max_width_for_tablets_but_stays_full_width_on_phones():
    """Punkt 2: auf einem Tablet soll das Suchfeld nicht unnötig breit wirken -- eine Maximalbreite mit zentrierender Randauflösung
    (margin:auto). Seit 1.8.164 am Feld der Fläche unter der Lupe (bis dahin .mobile-search-bar input)."""
    header = _read("_mobile_header.html")
    input_rule = header.split(".mobile-header-wrap .mobile-suche-feld{")[1].split("}")[0]
    assert "width:100%" in input_rule and "max-width:640px" in input_rule and "margin:0 auto" in input_rule


def test_search_bar_and_tabs_are_stacked_in_normal_flow_never_overlapping():
    """Kopf und Reiter liegen in EINEM sticky-Wrapper -- keine einzelnen, mit hart codierten top-Pixelwerten aufeinander gestapelten
    sticky-Elemente (das ursprüngliche 1.3.45-Muster). Seit 1.8.164 stehen die Reiter in der Kopfzeile selbst (unter 600 px in deren
    zweiter Zeile)."""
    header = _read("_mobile_header.html")
    assert ".mobile-header-wrap{position:sticky" in header
    header_rule = header.split(".mobile-header-wrap .mobile-header{")[1].split("}")[0]
    nav_rule = header.split(".mobile-header-wrap .mobile-nav{")[1].split("}")[0]
    assert "position:sticky" not in header_rule
    assert "position:sticky" not in nav_rule
    assert "top:45px" not in header


def test_search_results_layer_above_page_content_but_the_wrapper_itself_carries_the_z_index():
    """Seit 1.8.164 liegen die Vorschläge in der Fläche unter der Lupe (absolut, bis dahin die Liste selbst mit z-index:20)."""
    header = _read("_mobile_header.html")
    wrap_rule = header.split(".mobile-header-wrap{")[1].split("}")[0]
    panel_rule = header.split(".mobile-header-wrap .mobile-suche{")[1].split("}")[0]
    assert "z-index:30" in wrap_rule
    assert "position:absolute" in panel_rule


def test_customer_name_shown_in_suggestion_subline():
    """Punkt 1 der Anfrage (Kundenname in den Vorschlägen) -- die JS-Rendering-Seite der Änderung,
    die reine Datenprüfung steht in test_v268_property_search.py."""
    header = _read("_mobile_header.html")
    assert "h.customer_name" in header
