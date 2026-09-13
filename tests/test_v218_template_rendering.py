"""Version 1.2.20 -- Jinja-Vorlagen-Rendertest.

Rendert jede Seiten-Route aus app/routers/pages.py einmal über den TestClient und prüft auf
Status 200. Hätte den _debounce.html-Rekursionsfehler aus 1.2.19 gefangen: der trat beim
Rendern selbst auf, unabhängig davon, ob die übergebene ID real existiert, da alle echten Daten
in diesem Projekt clientseitig per fetch() nachgeladen werden (siehe CLAUDE.md, Stack &
Struktur) -- der Server rendert nur das statische Gerüst.

WICHTIG, bevor an diesem Test etwas nach demselben Muster ergänzt wird: die Jinja-Globals
get_theme()/is_module_enabled() (app/routers/pages.py) öffnen bei JEDEM Rendern eine eigene
SessionLocal()-Verbindung zur ECHTEN Datenbankdatei (dachkonzepte_erp.db), nicht zur hier per
router_test_client()/threaded_db_session übergebenen Test-Session -- sie umgehen die
get_db()-Injektion und sind damit nicht per app.dependency_overrides austauschbar (siehe
CLAUDE.md, "Bekannte, bewusst offene Punkte"; geprüft, eine kleine Behebung existiert nicht,
siehe dort). Für DIESEN Test unschädlich, weil ausschließlich gelesen wird (Akzentfarbe,
Modul-Status) -- ein künftiger Test nach diesem Vorbild darf darüber aber NICHT schreibend
gegen die echte Datenbankdatei laufen."""

import re

from app.routers.pages import router as pages_router

_PARAM_PATTERN = re.compile(r"\{[^}]+\}")

_SPECIAL_PATH_OVERRIDES = {
    "/master-data/{data_type}/new": "/master-data/customers/new",
    "/master-data/{data_type}/{record_id}/edit": "/master-data/properties/1/edit",
}


def _dummy_path(path: str) -> str:
    return _SPECIAL_PATH_OVERRIDES.get(path) or _PARAM_PATTERN.sub("1", path)


def test_every_page_route_renders_without_error(threaded_db_session, router_test_client):
    client = router_test_client(threaded_db_session, pages_router)
    failures = []
    for route in pages_router.routes:
        if "GET" not in getattr(route, "methods", set()) or route.path == "/health":
            continue
        path = _dummy_path(route.path)
        resp = client.get(path)
        if resp.status_code != 200:
            failures.append((path, resp.status_code))
    assert not failures, failures
