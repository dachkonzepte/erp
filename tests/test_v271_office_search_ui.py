"""Büro-Suche, Etappe 2 (seit 1.3.67) -- siehe CLAUDE.md "Büro-Suche" für Etappe 1. Deckt die
Oberfläche ab:

1. Die Ergebnisseite `/suche` liegt HINTER `require_role(ROLE_ADMIN, ROLE_OFFICE_FINANZEN,
   ROLE_OFFICE_AUFTRAG)` als eigene Seiten-Absicherung -- nicht nur der API-Endpunkt
   (`GET /api/search`) dahinter. Ein Monteur, der die Seite über die Adresse aufruft, bekommt
   403, bevor irgendetwas gerendert wird.
2. Die (seit 1.4.2: 18) im Client (`search_results.html`) hartcodierten Filter-Schlüssel bleiben synchron mit
   der Registry (`app/search.py::OFFICE_SEARCH_SOURCES`) -- ein Regressionstest, der bei einer
   künftigen Registry-Änderung auffällt, wenn die Kopie im Template nicht mitgezogen wurde.
3. Die Suchleiste in der Topbar ruft ausschließlich `GET /api/search`, nie den Monteurs-Endpunkt
   (Separate-Endpunkt-Prinzip), und erscheint im Markup nur für `admin`/`office`."""

import re
from pathlib import Path

from app.permissions import PAGE_AUDIT_EXEMPT
from app.search import OFFICE_SEARCH_SOURCES
from tests.test_v260_role_audit import _iter_role_marked_dependants
from tests.test_v270_office_search import EXPECTED_OFFICE_SEARCH_KEYS

TEMPLATES = Path(__file__).parents[1] / "app" / "templates"


def _read(name):
    return (TEMPLATES / name).read_text(encoding="utf-8")


# --- 1.: Seiten-Absicherung ---

def test_search_results_page_requires_office_or_admin_role(router_test_client, threaded_db_session):
    from app.routers import pages
    db = threaded_db_session
    field = router_test_client(db, pages.router, role="field", employee_id=None)
    resp = field.get("/suche")
    assert resp.status_code == 403, resp.text


def test_search_results_page_reachable_for_office_and_admin(router_test_client, threaded_db_session):
    from app.routers import pages
    db = threaded_db_session
    for role in ("buero_finanzen", "buero_auftrag", "admin"):
        client = router_test_client(db, pages.router, role=role, employee_id=None)
        resp = client.get("/suche")
        assert resp.status_code == 200, resp.text
        assert "Suche" in resp.text
        assert 'id="searchInput"' in resp.text


def test_search_results_route_carries_require_role_marker_no_new_exemption_needed():
    """Dieselbe mechanische Prüfung wie tests/test_v260_role_audit.py -- hier zusätzlich direkt
    an der neuen Route belegt, damit ein Rückfall (require_role() vergessen) nicht erst beim
    nächsten vollständigen Testlauf über den generischen Audit-Test auffällt."""
    from app.routers import pages
    matched = [r for r in pages.router.routes if getattr(r, "path", None) == "/suche"]
    assert matched, "Route /suche nicht gefunden"
    route = matched[0]
    assert any(True for _ in _iter_role_marked_dependants(route.dependant)), (
        "GET /suche trägt keine require_role()-Markierung"
    )
    assert ("GET", "/suche") not in PAGE_AUDIT_EXEMPT


# --- 2.: Client-seitige Typenliste bleibt synchron mit der Registry ---

def test_search_results_page_type_filter_keys_match_the_registry():
    html = _read("search_results.html")
    match = re.search(r"var TYPE_LABELS=\[(.*?)\];", html, re.DOTALL)
    assert match, "TYPE_LABELS-Array nicht gefunden"
    keys = re.findall(r"\['([a-z_]+)','", match.group(1))
    assert set(keys) == EXPECTED_OFFICE_SEARCH_KEYS
    assert len(keys) == len(OFFICE_SEARCH_SOURCES) == 18
    # Reihenfolge muss ebenfalls übereinstimmen -- eine abweichende Reihenfolge waere zwar
    # funktional harmlos (Filter wirken unabhaengig von der Anzeigereihenfolge), aber ein
    # stilles Auseinanderlaufen der beiden Listen ist genau das, was dieser Test verhindern soll.
    assert keys == [s.key for s in OFFICE_SEARCH_SOURCES]


def test_search_results_page_has_load_more_and_type_filter_logic():
    html = _read("search_results.html")
    assert "/api/search" in html
    assert "weitere anzeigen" in html
    assert "loadMore" in html
    assert "toggleType" in html


# --- 3.: Topbar-Suchleiste ---

def test_topbar_search_calls_the_office_endpoint_never_the_field_endpoint():
    html = _read("_topbar.html")
    assert "/api/search" in html
    assert "/api/field-view/properties/search" not in html


def test_topbar_search_uses_the_same_debounce_and_min_length_as_the_field_search():
    """Punkt: "Vorschläge beim Tippen mit demselben Debounce und derselben Mindestlänge wie die
    Monteurs-Suche" -- 300ms, Mindestlänge 2 Zeichen."""
    topbar = _read("_topbar.html")
    mobile = _read("_mobile_header.html")
    assert "setTimeout(runTopbarSearch,300)" in topbar
    assert "debounce(runObjectSearch,300)" in mobile
    assert "q.length<2" in topbar
    assert "q.length<2" in mobile


def test_topbar_search_closes_on_outside_click_and_escape():
    topbar = _read("_topbar.html")
    assert "'Escape'" in topbar
    assert "searchResults.hidden=true" in topbar
    # Klick daneben -- derselbe Ausschluss-Check wie beim Kontomenü direkt darüber in dieser Datei.
    assert "!searchResults.contains(e.target)" in topbar


def test_field_search_also_closes_on_escape_now():
    """Nachtrag (siehe Docstring dort): die Monteurs-Suche hatte bisher NUR den Klick-daneben-
    Schluss, keine Escape-Behandlung -- beim Bauen der Büro-Suche als Lücke aufgefallen und für
    beide nachgezogen, nicht nur für die neue."""
    mobile = _read("_mobile_header.html")
    assert "e.key==='Escape'" in mobile


def test_topbar_search_input_hidden_from_markup_when_role_is_field():
    """Die Suchleiste selbst rendert für `field` nicht (Jinja-Bedingung), unabhängig davon, ob
    _topbar.html überhaupt auf einer für field erreichbaren Seite eingebunden wird -- kein
    kaputtes, nie funktionierendes Eingabefeld."""
    topbar = _read("_topbar.html")
    assert 'current_user.role in ("admin", "buero_finanzen", "buero_auftrag")' in topbar
