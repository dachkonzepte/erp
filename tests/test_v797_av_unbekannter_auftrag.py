"""Version 1.10.26 (Frage F13, Antwort 23.11.2026): die Schreibwege der Arbeitsvorbereitung antworten bei einem unbekannten Auftrag mit 404, nie mit 500.

Bis 1.10.25 ließen POST /api/orders/{id}/work-preparation/employees, /tasks, /teams und /delivery-notes den ValueError aus ensure_preparation() durch -- 500
statt 404 (gefunden im Rundgang tests/test_v794_archiv_rundgang.py, der seither keine 500 mehr zulässt). Jetzt holt jeder Schreibweg die Arbeitsvorbereitung
über _vorbereitung(): „Auftrag nicht gefunden.“ wird dort 404, nichts wird angelegt, keine Datei geschrieben. Anlegen und Ändern gaben schon 404 und gehen
denselben Weg.
"""

import ast
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.models import (
    Employee, ProjectDocument, Team, WorkPreparation, WorkPreparationDeliveryNote, WorkPreparationEmployee, WorkPreparationTask,
    WorkPreparationTeamAssignment,
)
from app.project_documents import PROJECT_ROOT
from app.routers.work_preparation import router as av_router
from tests.test_v133_invoices import make_order_with_item
from tests.test_v793_archivschutz import PNG

ROOT = Path(__file__).resolve().parent.parent
LEER = 999999
# je Schreibweg mit dem Auftrag im Pfad: Methode, Pfad, Anfrage (aus den Kennungen der Welt) -- dieselbe Anfrage gelingt mit dem echten Auftrag
WEGE = {
    "mitarbeiter": ("POST", "/api/orders/{}/work-preparation/employees", lambda w: {"json": {"employee_id": w["mitarbeiter"]}}),
    "aufgabe": ("POST", "/api/orders/{}/work-preparation/tasks", lambda w: {"json": {"title": "Gerüst bestellen"}}),
    "kolonne": ("POST", "/api/orders/{}/work-preparation/teams", lambda w: {"json": {"team_id": w["team"]}}),
    "lieferschein": ("POST", "/api/orders/{}/work-preparation/delivery-notes", lambda w: {"files": {"file": ("lieferschein.png", PNG, "image/png")}}),
    "anlegen": ("POST", "/api/orders/{}/work-preparation", lambda w: {}),
    "aendern": ("PUT", "/api/orders/{}/work-preparation", lambda w: {"json": {"site_notes": "Zufahrt über den Hof"}}),
}
ZEILEN = (WorkPreparation, WorkPreparationEmployee, WorkPreparationTask, WorkPreparationTeamAssignment, WorkPreparationDeliveryNote, ProjectDocument)


@pytest.fixture
def av(threaded_db_session, router_test_client):
    db = threaded_db_session
    order, _ = make_order_with_item(db)
    mitarbeiter = Employee(employee_number="AV-1", first_name="Mia", last_name="Muster", employee_group="gewerblich", weekly_hours=Decimal("40"), active=True)
    team = Team(name="Kolonne Nord", active=True)
    db.add_all([mitarbeiter, team])
    db.commit()
    return {"db": db, "client": router_test_client(db, av_router), "order": order.id, "mitarbeiter": mitarbeiter.id, "team": team.id}


def _stand(db) -> dict:
    db.expire_all()
    dateien = sorted(str(p) for p in PROJECT_ROOT.rglob("*") if p.is_file()) if PROJECT_ROOT.exists() else []
    return {**{m.__tablename__: db.scalar(select(func.count()).select_from(m)) for m in ZEILEN}, "dateien": dateien}


@pytest.mark.parametrize("weg", sorted(WEGE))
def test_unbekannter_auftrag_404_ohne_spur(av, weg):
    methode, pfad, anfrage = WEGE[weg]
    vorher = _stand(av["db"])
    r = av["client"].request(methode, pfad.format(LEER), **anfrage(av))
    assert (r.status_code, r.json().get("detail")) == (404, "Auftrag nicht gefunden."), r.text
    assert _stand(av["db"]) == vorher


@pytest.mark.parametrize("weg", sorted(WEGE))
def test_dieselbe_anfrage_mit_dem_auftrag_gelingt(av, weg):
    """Gegenstück: die Anfrage selbst ist gültig -- die 404 oben kommt vom unbekannten Auftrag, nicht von der Anfrage."""
    methode, pfad, anfrage = WEGE[weg]
    r = av["client"].request(methode, pfad.format(av["order"]), **anfrage(av))
    assert r.status_code == 200, r.text
    assert r.json()["order_id"] == av["order"]


def test_jeder_schreibweg_holt_die_arbeitsvorbereitung_ueber_vorbereitung():
    """ensure_preparation() steht im Router nur in _vorbereitung(), und dort wird der ValueError 404."""
    baum = ast.parse((ROOT / "app" / "routers" / "work_preparation.py").read_text(encoding="utf-8"))
    aufrufer = []
    for f in (n for n in ast.walk(baum) if isinstance(n, ast.FunctionDef)):
        if any(isinstance(c, ast.Call) and getattr(c.func, "id", None) == "ensure_preparation" for c in ast.walk(f)):
            aufrufer.append(f.name)
    assert aufrufer == ["_vorbereitung"], aufrufer
    vorbereitung = next(f for f in ast.walk(baum) if isinstance(f, ast.FunctionDef) and f.name == "_vorbereitung")
    quelle = ast.unparse(vorbereitung)
    assert "except ValueError" in quelle and "status_code=404" in quelle
