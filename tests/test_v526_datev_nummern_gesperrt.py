"""Version 1.9.106 (Stufe 4, R5b Nachrunde, Punkt 7): Berater- und Mandantennummer in Einstellungen → Zeitregeln und DATEV sind für Büro – Finanzen
erkennbar nur lesbar -- gesperrt (disabled) und grau wie jedes gesperrte Feld der Einstellungen (bis 1.9.105 readonly: sie sahen bearbeitbar aus,
die Einstellungen hatten keine eigene Darstellung gesperrter Felder). Im Browser: scripts/klicktest_datev_nummern.py."""

import re

import pytest

from app.routers.pages import router as pages_router


def _feld(html: str, feld_id: str) -> str:
    return re.search(rf'<input id="{feld_id}"[^>]*>', html).group(0)


@pytest.mark.parametrize("rolle, gesperrt", [("buero_finanzen", True), ("admin", False)])
def test_nummern_fuer_das_buero_gesperrt(threaded_db_session, router_test_client, rolle, gesperrt):
    html = router_test_client(threaded_db_session, pages_router, role=rolle).get("/settings").text
    for feld_id in ("datevBerater", "datevMandant"):
        feld = _feld(html, feld_id)
        assert (" disabled" in feld, "readonly" in feld) == (gesperrt, False), feld


def test_gesperrte_felder_der_einstellungen_grau(threaded_db_session, router_test_client):
    html = router_test_client(threaded_db_session, pages_router, role="admin").get("/settings").text
    assert "input:disabled,select:disabled,textarea:disabled{background:var(--soft);color:var(--muted);cursor:not-allowed}" in html
