"""Nachrunde zur Fehlerrunde (1.8.143 ff., Vorgabe vom 19.10.2026): je Punkt ein Test, der vor der Behebung scheiterte.

Die Punkte 1–3 (Zeit buchen, Gruppenzeit stoppen, Kennzeichen entziehen) stehen in tests/test_v437_befund_zeit_fuer_andere.py.

    4  users.html: Zurück-Link mit echtem Ziel statt history.back() (1.8.146)
"""

import html
import re


# ---------------------------------------------------------------------------
# 4. users.html: Zurück-Link mit echtem Ziel
# ---------------------------------------------------------------------------

def test_benutzerseite_zurueck_in_die_einstellungen(threaded_db_session, router_test_client):
    """Bis 1.8.145 ging „← Einstellungen“ per history.back() zurück -- nach direktem Aufruf ins Leere."""
    from app.routers.pages import router as pages_router

    antwort = router_test_client(threaded_db_session, pages_router, role="admin").get("/users")
    assert antwort.status_code == 200
    markup = re.sub(r"<script.*?</script>", "", antwort.text, flags=re.S | re.I)
    links = re.findall(r'<a[^>]*class="back"[^>]*>.*?</a>', markup, flags=re.S)
    assert len(links) == 1, links
    assert re.search(r'href="([^"]*)"', links[0]).group(1) == "/settings"
    assert "onclick" not in links[0] and "history.back" not in antwort.text
    assert html.unescape(re.sub(r"<[^>]+>", "", links[0])).strip() == "← Einstellungen"
    assert router_test_client(threaded_db_session, pages_router, role="admin").get("/settings").status_code == 200
