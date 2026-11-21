"""Version 1.10.14 (Antwort F1 vom 21.11.2026): „Aufbewahrung“ in der Leiste unter Verwaltung.

    Eintrag      zwischen Stammdaten und Einstellungen, für jedes Büro (wer die Seite liest); die Monteurin hat keine Leiste und keinen Weg dorthin
    aktiv        die Seite „Aufbewahrung“ markiert ihren eigenen Eintrag (bereich „aufbewahrung“, bis 1.10.13 „anfragen“)
    Kachel       die Kachel auf „Start“ bleibt -- ohne sie (abwählbar) führt die Leiste auf die Seite
"""

import re

import pytest

from app.permissions import ROLE_ADMIN, ROLE_FIELD, ROLE_OFFICE_AUFTRAG, ROLE_OFFICE_FINANZEN
from app.routers.pages import router as pages_router
from app.routers.pages import templates

BUERO = (ROLE_ADMIN, ROLE_OFFICE_FINANZEN, ROLE_OFFICE_AUFTRAG)


@pytest.fixture
def seite(threaded_db_session, router_test_client, monkeypatch):
    monkeypatch.setitem(templates.env.globals, "is_module_enabled", lambda key: True)

    def _seite(pfad: str, rolle: str):
        return router_test_client(threaded_db_session, pages_router, role=rolle).get(pfad, follow_redirects=False)
    return _seite


def _leiste(html: str) -> str:
    return html[html.index('<nav class="app-sidebar-nav">'):html.index("</nav>")]


def _verwaltung(nav: str) -> list[str]:
    teil = nav[nav.index('<div class="app-sidebar-group">Verwaltung</div>'):]
    return re.findall(r'data-bereich="([a-z]+)"', teil)


@pytest.mark.parametrize("rolle", BUERO)
def test_eintrag_unter_verwaltung_fuer_jedes_buero(seite, rolle):
    antwort = seite("/account", rolle)
    assert antwort.status_code == 200
    nav = _leiste(antwort.text)
    assert _verwaltung(nav) == ["stammdaten", "aufbewahrung", "einstellungen"]
    eintrag = re.search(r'<a [^>]*data-bereich="aufbewahrung"[^>]*>', nav).group(0)
    assert 'href="/aufbewahrung"' in eintrag and " active" not in eintrag
    assert seite("/aufbewahrung", rolle).status_code == 200  # wer den Eintrag sieht, öffnet die Seite


def test_monteurin_ohne_eintrag_und_ohne_seite(seite):
    html = seite("/account", ROLE_FIELD).text
    assert 'data-bereich="aufbewahrung"' not in html and 'href="/aufbewahrung"' not in html
    assert seite("/aufbewahrung", ROLE_FIELD).status_code in (302, 303, 307, 403)


@pytest.mark.parametrize("rolle", BUERO)
def test_seite_markiert_ihren_eintrag(seite, rolle):
    nav = _leiste(seite("/aufbewahrung", rolle).text)
    assert nav.count(" active") == 1 and nav.count('aria-current="page"') == 1
    aktiv = re.search(r'<a [^>]*class="app-sidebar-link active"[^>]*>', nav).group(0)
    assert 'data-bereich="aufbewahrung"' in aktiv and 'aria-current="page"' in aktiv


def test_kachel_auf_start_bleibt():
    from app.dashboard import DEFAULT_WIDGETS
    assert any("aufbewahrung" in str(w) for w in DEFAULT_WIDGETS)
