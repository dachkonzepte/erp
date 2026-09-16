"""Version "Dateiablage je Objekt", Schritt 3, Nachtrag (nach 1.3.64) -- zwei Anpassungen an der
Monteurs-Suche (siehe CLAUDE.md "Suche als Einstieg"). Punkt 1 (Kundenname in den Vorschlägen)
ist in tests/test_v268_property_search.py abgedeckt. Diese Datei deckt Punkt 2 ab: die Suche
wandert von mobil.html in die gemeinsame Kopfzeile (_mobile_header.html), damit sie von jeder
Seite der Monteursansicht aus erreichbar ist -- rein strukturelle Prüfungen an den
Template-Quellen, da JS-Interaktion/CSS-Layout ohne echten Browser nicht ausführbar ist
(dieselbe, wiederholt dokumentierte Werkzeug-Einschränkung dieser Umgebung, siehe CLAUDE.md)."""

from pathlib import Path

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
    header = _read("_mobile_header.html")
    assert '{% include "_debounce.html" %}' in header
    # Keines der vier Templates, die _mobile_header.html einbinden, darf den Helfer zusätzlich
    # selbst einbinden -- sonst wäre `debounce` doppelt definiert (harmlos in JS, aber ein Zeichen
    # für auseinanderlaufende Konventionen).
    for name in ("mobil.html", "mobil_objekt.html", "field_timesheet.html", "time_tracking_field.html"):
        content = _read(name)
        assert '{% include "_mobile_header.html" %}' in content, f"{name} bindet die Kopfzeile nicht ein"
        assert '{% include "_debounce.html" %}' not in content, f"{name} bindet den Debounce-Helfer doppelt ein"


def test_every_mobile_page_gets_the_search_bar_for_free():
    """Punkt 2 der Anfrage: die Suche muss von JEDER Seite der Monteursansicht aus erreichbar
    sein, nicht nur von /mobil -- da alle vier Seiten _mobile_header.html einbinden, erreicht sie
    das automatisch, ohne dass jede Seite das Suchfeld einzeln nachbauen müsste."""
    for name in ("mobil.html", "mobil_objekt.html", "field_timesheet.html", "time_tracking_field.html"):
        assert '{% include "_mobile_header.html" %}' in _read(name)


def test_search_results_dropdown_is_anchored_below_the_whole_header_not_below_the_input():
    """Die Vorschlagsliste darf die Reiter nicht überlagern (sonst würde ein Tipp auf einen
    Reiter bei offener Liste zuerst die Liste treffen, nicht den Reiter -- ein zweiter Tipp wäre
    nötig). Dafür muss sie strukturell NACH <nav> als Kind des GESAMTEN sticky-Wrappers stehen,
    nicht direkt unter dem Suchfeld -- ihr `top:100%` bezieht sich dann auf die Unterkante des
    ganzen Kopfblocks (Kopf+Suche+Reiter), nicht auf die Unterkante des Eingabefelds."""
    header = _read("_mobile_header.html")
    wrap_start = header.index('id="mobileHeaderWrap"')
    search_bar_pos = header.index('class="mobile-search-bar"', wrap_start)
    nav_pos = header.index("<nav", wrap_start)
    results_pos = header.index('id="mobileObjectSearchResults"', wrap_start)
    wrap_end = header.index("</div>\n<script>", wrap_start)
    assert search_bar_pos < nav_pos < results_pos < wrap_end
    # Die Vorschlagsliste ist absolut positioniert relativ zum sticky-Wrapper (ihrem nächsten
    # positionierten Vorfahren) -- kein zweiter, innerer positionierter Container dazwischen, der
    # sie stattdessen unter das Suchfeld ziehen würde.
    assert "position:relative" not in header.split('class="mobile-search-bar"')[1].split("<nav")[0]


def test_search_bar_has_a_max_width_for_tablets_but_stays_full_width_on_phones():
    """Punkt 2: auf einem Tablet soll das Suchfeld nicht unnötig breit wirken -- eine
    Maximalbreite mit zentrierender Randauflösung (margin:auto) erreicht das, ohne auf einem
    schmalen Smartphone-Bildschirm etwas zu ändern (dort ist die volle Breite ohnehin kleiner
    als die Maximalbreite, die Regel bleibt dort wirkungslos)."""
    header = _read("_mobile_header.html")
    assert "max-width:640px" in header
    assert ".mobile-search-bar input{" in header
    input_rule = header.split(".mobile-search-bar input{")[1].split("}")[0]
    assert "width:100%" in input_rule
    assert "max-width:640px" in input_rule


def test_search_bar_and_tabs_are_stacked_in_normal_flow_never_overlapping():
    """Kopf/Suche/Reiter liegen als normale Blockzeilen in EINEM sticky-Wrapper -- keine
    einzelnen, mit hart codierten top-Pixelwerten aufeinander gestapelten sticky-Elemente mehr
    (das ursprüngliche 1.3.45-Muster, das bei einer neuen Zeile hätte neu vermessen werden
    müssen). Ohne Restüberlappungsrisiko auf jeder Bildschirmgröße, da normale Blockelemente sich
    nie überlappen können, unabhängig von der Fensterbreite."""
    header = _read("_mobile_header.html")
    assert ".mobile-header-wrap{position:sticky" in header
    # .mobile-header und .mobile-nav selbst duerfen NICHT mehr einzeln sticky sein -- das war das
    # alte, fragile Stapel-Muster.
    header_rule = header.split(".mobile-header{")[1].split("}")[0]
    nav_rule = header.split(".mobile-nav{")[1].split("}")[0]
    assert "position:sticky" not in header_rule
    assert "position:sticky" not in nav_rule
    assert "top:45px" not in header


def test_search_results_layer_above_page_content_but_the_wrapper_itself_carries_the_z_index():
    header = _read("_mobile_header.html")
    wrap_rule = header.split(".mobile-header-wrap{")[1].split("}")[0]
    results_rule = header.split(".mobile-search-results{")[1].split("}")[0]
    assert "z-index:30" in wrap_rule
    assert "position:absolute" in results_rule
    assert "z-index:20" in results_rule


def test_customer_name_shown_in_suggestion_subline():
    """Punkt 1 der Anfrage (Kundenname in den Vorschlägen) -- die JS-Rendering-Seite der Änderung,
    die reine Datenprüfung steht in test_v268_property_search.py."""
    header = _read("_mobile_header.html")
    assert "h.customer_name" in header
