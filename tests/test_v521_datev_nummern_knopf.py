"""Version 1.9.99 (Stufe 4, R5b, Punkt 8) -- „Berater- und Mandantennummer speichern“ ist ein grüner Hauptknopf wie die übrigen
Speichern-Knöpfe der Einstellungen (Wunsch Tobias; 1.9.92–1.9.98 mit der Klasse „secondary“, ohne Fläche)."""

import re

from app.routers.pages import router as pages_router


def _klasse(attribute: str) -> str:
    treffer = re.search(r'class="([^"]*)"', attribute)
    return treffer.group(1) if treffer else ""


def test_datev_nummern_speichern_wie_zeitregeln_speichern(threaded_db_session, router_test_client):
    text = router_test_client(threaded_db_session, pages_router, role="admin").get("/settings").text
    zeitregeln = re.search(r"<button([^>]*)>Zeitregeln und Lohnarten speichern</button>", text).group(1)
    datev = re.search(r"<button([^>]*)>Berater- und Mandantennummer speichern</button>", text).group(1)
    assert 'id="datevNummernSpeichern"' in datev
    assert _klasse(datev) == _klasse(zeitregeln) == ""


def test_kein_speichern_knopf_einer_karte_ohne_flaeche(threaded_db_session, router_test_client):
    """Jeder Speichern-Knopf einer Karte (im Markup, onclick="save…()") ist der grüne Hauptknopf -- „secondary“ tragen nur die Knöpfe je
    Zeile einer Liste, die das Skript zeichnet."""
    text = router_test_client(threaded_db_session, pages_router, role="admin").get("/settings").text
    markup = re.sub(r"<script.*?</script>", "", text, flags=re.S | re.I)
    knoepfe = [(m.group(2), _klasse(m.group(1))) for m in re.finditer(r"<button([^>]*)>([^<]*)</button>", markup)
               if "speichern" in m.group(2).lower() and re.search(r'onclick="save\w+\(', m.group(1))]
    assert len(knoepfe) >= 20
    assert [k for k in knoepfe if "secondary" in k[1].split()] == []
