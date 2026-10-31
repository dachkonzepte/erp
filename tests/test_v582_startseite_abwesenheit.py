"""Version 1.9.164 (Stufe 6, R2, Punkt 7): die Startseite zeigt einen Abwesenheitsantrag von einem Tag als einen Tag, wie „Zeiten → Abwesenheiten“ (abwZeitraum(), seit 1.9.154)."""

import re
from pathlib import Path

import pytest

from tests.node_lauf import node_ausfuehren
from tests.vorlagen_js import bindet_ein

TEMPLATES = Path(__file__).resolve().parent.parent / "app" / "templates"


def _abw_zeitraum() -> str:
    text = (TEMPLATES / "_abwesenheit.html").read_text(encoding="utf-8")
    return text[text.index("function abwZeitraum("):text.index("function abwArtText(")]


@pytest.mark.parametrize("von, bis, erwartet", [
    ("2026-10-21", "2026-10-21", "Mi 21.10.2026"),
    ("2026-10-19", "2026-10-21", "Mo 19.10.–Mi 21.10.2026"),
    ("2026-12-30", "2027-01-02", "Mi 30.12.2026–Sa 02.01.2027"),
])
def test_der_zeitraum(von, bis, erwartet):
    assert node_ausfuehren(_abw_zeitraum() + f"\nconsole.log(JSON.stringify(abwZeitraum('{von}','{bis}')));") == erwartet


def test_die_startseite_nimmt_ihn():
    seite = (TEMPLATES / "dashboard.html").read_text(encoding="utf-8")
    assert "abwZeitraum(a.start_date,a.end_date)" in seite
    assert not re.search(r"fmtDate\(a\.start_date\)", seite)
    assert bindet_ein("dashboard.html", "_abwesenheit.html")
