"""Seit 1.9.14 (Runde 7, Punkt 2): die Zeitregeln lassen sich speichern, auch wenn das Standard-Arbeitszeitmodell inzwischen
abgeschaltet ist (Nebenbefund 1.9.12, bis 1.9.13 422 „existiert nicht oder ist inaktiv“ bei jedem Speichern -- auch wenn nur die
Rundung geändert wurde). Regel 22: der Server prüft „aktiv“ nur bei einem neu gewählten Wert; der gespeicherte bleibt.

    unverändert     das abgeschaltete Standardmodell bleibt gewählt, andere Felder werden gespeichert (200)
    neu gewählt     ein anderes abgeschaltetes Modell -> 422, nichts gespeichert; ein unbekanntes -> 422
    Oberfläche      die Einstellungen bauen die Auswahl über auswahlOptionen(): das abgeschaltete Modell bleibt gewählt und geht
                    unverändert hinaus
"""

import re

from app.models import WorkTimeModel
from app.routers.time_backoffice import router as time_backoffice_router
from app.work_time_models import load_advanced_settings
from tests import vorlagen_js as vj


def _client(db, router_test_client):
    return router_test_client(db, time_backoffice_router, role="buero_auftrag")


def _abschalten(db, model_id):
    db.get(WorkTimeModel, model_id).active = False
    db.commit()


def test_speichern_mit_abgeschaltetem_standardmodell(threaded_db_session, router_test_client):
    db = threaded_db_session
    client = _client(db, router_test_client)
    stand = client.get("/api/time-backoffice/settings").json()
    standard = stand["default_work_time_model_id"]
    assert standard is not None
    _abschalten(db, standard)

    r = client.put("/api/time-backoffice/settings", json={**stand, "rounding_minutes": 15})
    assert r.status_code == 200, r.text
    assert r.json()["rounding_minutes"] == 15
    assert r.json()["default_work_time_model_id"] == standard
    db.expire_all()
    assert load_advanced_settings(db).default_work_time_model_id == standard


def test_neu_gewaehltes_abgeschaltetes_modell_abgelehnt(threaded_db_session, router_test_client):
    db = threaded_db_session
    client = _client(db, router_test_client)
    stand = client.get("/api/time-backoffice/settings").json()
    standard = stand["default_work_time_model_id"]
    anderes = db.query(WorkTimeModel).filter(WorkTimeModel.id != standard).first()
    assert anderes is not None
    _abschalten(db, anderes.id)

    r = client.put("/api/time-backoffice/settings", json={**stand, "rounding_minutes": 15, "default_work_time_model_id": anderes.id})
    assert r.status_code == 422 and "inaktiv" in r.json()["detail"]
    r = client.put("/api/time-backoffice/settings", json={**stand, "default_work_time_model_id": 999999})
    assert r.status_code == 422
    db.expire_all()
    assert load_advanced_settings(db).default_work_time_model_id == standard
    assert client.get("/api/time-backoffice/settings").json()["rounding_minutes"] == stand["rounding_minutes"]


def test_oberflaeche_behaelt_das_abgeschaltete_modell():
    """Die Auswahl entsteht über auswahlOptionen() mit dem gespeicherten Wert, gespeichert wird ihr Wert -- ein abgeschaltetes Modell
    bleibt als „(inaktiv)“ gewählt und geht unverändert hinaus."""
    text = (vj.TEMPLATES / "settings.html").read_text(encoding="utf-8")
    assert re.search(r"getElementById\('defaultWorkModel'\)\.innerHTML=auswahlOptionen\(workModels,timeRules\.default_work_time_model_id,", text)
    assert "default_work_time_model_id:v('defaultWorkModel')?Number(v('defaultWorkModel')):null" in text
