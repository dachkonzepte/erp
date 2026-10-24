"""Seit 1.9.74 (Stufe 4, R4 Nachtrag): einen Auftrag für heute einplanen, damit er in der Auftragsliste der Monteurin steht.

Einen Bericht legt die Monteurin seit 1.9.74 nur für einen Auftrag ihrer Liste an (app/planning.py::field_order_in_list(), dieselbe Liste wie
„Zeit nachtragen“ in „Meine Zeiten“). Eine Zuordnung über die Arbeitsvorbereitung ohne Datum reicht dafür nicht mehr (bis 1.9.73 schon) --
Tests, die über eine solche Zuordnung einen Bericht anlegen, aber etwas anderes prüfen (Zugehörigkeit, Eigentum, Datengrenze), datieren die
Arbeitsvorbereitung mit heute(), wie ein Eintrag der Plantafel ohne Abschnitt (planned_start/planned_end, der Rückfall des Zeitfensters).
"""

from app.berlin_time import berlin_today
from app.work_preparation import ensure_preparation


def heute(db, order_id: int) -> None:
    prep = ensure_preparation(db, order_id)
    prep.planned_start = prep.planned_end = berlin_today()
    db.commit()
