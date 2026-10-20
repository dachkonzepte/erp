"""Runde „Du“ (1.8.157 ff., Vorgabe vom 20.10.2026).

    3  „… keinem Mitarbeiter zugeordnet“: eine gemeinsame Meldung (app/meldungen.py::KEIN_MITARBEITER) statt neun Fassungen (1.8.159)
"""

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MELDUNG_MUSTER = re.compile(r"(keinem|mit keinem) Mitarbeiter (zugeordnet|verknüpft)")


# ---------------------------------------------------------------------------
# 3. Eine Meldung „… keinem Mitarbeiter zugeordnet“
# ---------------------------------------------------------------------------

def _zeichenketten(pfad: Path):
    baum = ast.parse(pfad.read_text(encoding="utf-8"))
    docstrings = {id(k.body[0].value) for k in ast.walk(baum)
                  if isinstance(k, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and k.body
                  and isinstance(k.body[0], ast.Expr) and isinstance(k.body[0].value, ast.Constant)}
    for k in ast.walk(baum):
        if isinstance(k, ast.Constant) and isinstance(k.value, str) and id(k) not in docstrings:
            yield k.lineno, k.value


def test_keine_eigene_fassung_der_meldung():
    """Bis 1.8.158 stand die Meldung in neun Fassungen an 20 Stellen (14 im Server, 6 in Vorlagen). Seit 1.8.159 nur noch als
    KEIN_MITARBEITER in app/meldungen.py; die Vorlagen nehmen den Jinja-Global kein_mitarbeiter."""
    from app.meldungen import KEIN_MITARBEITER
    from tests.test_v334_auswahl_restfaelle import TEMPLATES
    from tests.vorlagen_js import alle_vorlagen

    funde = [f"{p.relative_to(ROOT)}:{nr}" for p in sorted((ROOT / "app").rglob("*.py")) if p.name != "meldungen.py"
             for nr, s in _zeichenketten(p) if MELDUNG_MUSTER.search(s)]
    for name in alle_vorlagen():
        text = re.sub(r"\{#.*?#\}", "", (TEMPLATES / name).read_text(encoding="utf-8"), flags=re.S)
        funde += [f"app/templates/{name}" for _ in MELDUNG_MUSTER.finditer(text)]
    assert funde == []
    assert KEIN_MITARBEITER == ("Dein Konto ist keinem Mitarbeiter zugeordnet. Ein Administrator kann das unter Einstellungen → "
                                "Benutzer und Zugriff ändern.")
    nutzer = {name for name in alle_vorlagen() if "{{ kein_mitarbeiter|tojson }}" in (TEMPLATES / name).read_text(encoding="utf-8")}
    assert nutzer == {"dashboard.html", "field_timesheet.html", "service_reports.html", "time_backoffice.html", "time_tracking.html",
                      "time_tracking_field.html"}


@pytest.mark.parametrize("adresse,rolle", [("/time-tracking", "buero_finanzen"), ("/time-tracking", "field"), ("/", "buero_auftrag"),
                                           ("/mobil/stundenzettel", "field"), ("/time-backoffice", "buero_finanzen")])
def test_seiten_zeigen_die_gemeinsame_meldung(threaded_db_session, router_test_client, adresse, rolle):
    """Die gezeichnete Seite trägt genau die Meldung aus app/meldungen.py (als JSON-Zeichenkette im Skript)."""
    from jinja2.utils import htmlsafe_json_dumps

    from app.meldungen import KEIN_MITARBEITER
    from app.routers.pages import router as pages_router

    antwort = router_test_client(threaded_db_session, pages_router, role=rolle).get(adresse, follow_redirects=False)
    assert antwort.status_code == 200, (adresse, antwort.status_code)
    assert str(htmlsafe_json_dumps(KEIN_MITARBEITER)) in antwort.text


def test_server_meldet_die_gemeinsame_meldung(threaded_db_session, router_test_client, feste_uhr):
    """Ein Konto ohne Mitarbeiter bekommt aus Zeiterfassung und Monteursansicht dieselbe Meldung (feste Uhr: /today meldet ab dem
    Feierabend 401)."""
    from app.meldungen import KEIN_MITARBEITER
    from app.routers.field_view import router as field_router
    from app.routers.time_tracking import router as time_router

    db = threaded_db_session
    monteur = router_test_client(db, time_router, field_router, role="field")
    for antwort in (monteur.post("/api/time-entries", json={"employee_id": 1, "order_id": 1, "work_date": "2026-10-20", "hours": "1"}),
                    monteur.get("/api/time-entries/active"),
                    monteur.get("/api/field-view/today"),
                    monteur.get("/api/field-view/timesheet.pdf")):
        assert antwort.status_code in (403, 422), antwort.text
        assert antwort.json()["detail"] == KEIN_MITARBEITER
