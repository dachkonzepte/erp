"""Version 1.9.121 (Stufe 5, R1 Nachrunde, Punkt 3): „Durchgeführt von“ im Einsatzbericht nach der Regel der Zeiten.

Festlegung 1.9.112 Nr. 3 (Büro – Finanzen wählt dort nur sich selbst) nicht bestätigt: seit 1.9.121 gilt app/permissions.py::
darf_zeit_fuer_andere_buchen() -- Admin und Büro – Finanzen wählen auch andere, Büro – Auftrag und die Monteurin nur sich selbst oder niemanden.
Eine Regel: darf_fuer_andere_erfassen() (1.9.112–1.9.120, nur Admin) gibt es nicht mehr.
"""

import ast
import inspect

import pytest

import app.permissions as permissions
from app.routers import service_reports as reports_module
from app.routers.service_reports import router as reports_router
from tests.test_v532_befund_im_fremden_bericht import _welt

NEU = {"report_type": "rapport", "description": "Rinne gereinigt"}


@pytest.mark.parametrize("rolle, status", [("buero_finanzen", 200), ("admin", 200), ("buero_auftrag", 403)])
def test_bericht_durchgefuehrt_von_mia(threaded_db_session, router_test_client, rolle, status):
    db = threaded_db_session
    order, mia, bea, _ = _welt(db)
    client = router_test_client(db, reports_router, role=rolle, employee_id=bea.id)
    antwort = client.post(f"/api/orders/{order.id}/service-reports", json={**NEU, "created_by_employee_id": mia.id})
    assert antwort.status_code == status, antwort.text
    if status == 200:
        assert antwort.json()["created_by_employee_id"] == mia.id
    else:
        assert antwort.json()["detail"] == "Du darfst nur dich selbst als Mitarbeiter angeben."


def test_eine_regel_fuer_zeiten_und_bericht():
    assert not hasattr(permissions, "darf_fuer_andere_erfassen")
    baum = ast.parse(inspect.getsource(reports_module._employee_for_request))
    aufrufe = {n.func.id for n in ast.walk(baum) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "darf_zeit_fuer_andere_buchen" in aufrufe
