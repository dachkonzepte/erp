"""Version 1.9.112 (Stufe 5, R1, Punkt 2, Befund F1): Befund im Bericht einer anderen Person, „erfasst von“, „Durchgeführt von“.

    Befund   Jedes Konto, das den Bericht bearbeiten darf, legt dort einen Befund an -- auch das Büro im Bericht der Monteurin (bis 1.9.111 403
             „Du darfst nur dich selbst als Mitarbeiter angeben.“, weil die Seite den Ersteller des Berichts mitschickte). „Erfasst von“ ist das
             anlegende Konto (created_by_user_id, created_by_name) und dessen Mitarbeiter -- nie still die Monteurin (der Admin schrieb den Befund
             bis 1.9.111 ihr zu). Wer „erfasst von“ mitschickt, bekommt 422, auch der Admin.
    Altbestand  Ein Befund von vor 1.9.112 (ohne Konto) nennt seinen Mitarbeiter.
    „Durchgeführt von“  bietet nur an, was der Server annimmt: seit 1.9.121 Admin und Büro – Finanzen jede Person, jedes andere Konto sich
             selbst oder niemanden (app/permissions.py::darf_zeit_fuer_andere_buchen(); 1.9.112–1.9.120 nur der Admin, darf_fuer_andere_erfassen()).
"""

import re

import pytest
from sqlalchemy import select

from app.models import AppUser, Finding, ServiceReport
from app.permissions import darf_zeit_fuer_andere_buchen
from app.routers.findings import router as findings_router
from app.routers.service_reports import router as reports_router
from app.service_reports import create_report
from tests.test_v334_auswahl_restfaelle import nur_mit_node
from tests.test_v264_field_time_tracking import _assign_via_team, _employee, _order


def _welt(db):
    order, _ = _order(db, "AUF-532-0001", "P-532-0001")
    mia = _employee(db, "E-532-1", "Mia", "Monteurin")
    bea = _employee(db, "E-532-2", "Bea", "Büro")
    _assign_via_team(db, order, mia)
    bericht = create_report(db, order.id, report_type="rapport", description="Dach geprüft", created_by_employee_id=mia.id)
    return order, mia, bea, bericht["id"]


BEFUND = {"description": "Ziegel gebrochen", "severity": "mittel", "action": "buero_pruefen"}


@pytest.mark.parametrize("rolle", ["buero_finanzen", "buero_auftrag"])
def test_buero_legt_befund_im_bericht_der_monteurin_an(threaded_db_session, router_test_client, rolle):
    db = threaded_db_session
    _, mia, bea, bericht = _welt(db)
    client = router_test_client(db, findings_router, role=rolle, employee_id=bea.id, user_id=7, display_name="Bea Büro")
    antwort = client.post(f"/api/service-reports/{bericht}/findings", json=BEFUND)
    assert antwort.status_code == 200, antwort.text
    assert (antwort.json()["created_by_name"], antwort.json()["created_by_employee_id"]) == ("Bea Büro", bea.id)
    befund = db.scalar(select(Finding))
    assert (befund.created_by_user_id, befund.created_by_name, befund.created_by_employee_id) == (7, "Bea Büro", bea.id)
    assert befund.created_by_employee_id != mia.id
    assert [f["created_by_name"] for f in client.get(f"/api/service-reports/{bericht}/findings").json()] == ["Bea Büro"]


def test_admin_ohne_mitarbeiter_schreibt_nicht_der_monteurin_zu(threaded_db_session, router_test_client):
    db = threaded_db_session
    _, mia, _, bericht = _welt(db)
    client = router_test_client(db, findings_router, role="admin", user_id=1, display_name="Ada Admin")
    antwort = client.post(f"/api/service-reports/{bericht}/findings", json=BEFUND)
    assert antwort.status_code == 200, antwort.text
    befund = db.scalar(select(Finding))
    assert (befund.created_by_name, befund.created_by_employee_id) == ("Ada Admin", None)


def test_monteurin_im_eigenen_bericht_bleibt_sie_selbst(threaded_db_session, router_test_client):
    db = threaded_db_session
    _, mia, _, bericht = _welt(db)
    client = router_test_client(db, findings_router, role="field", employee_id=mia.id, user_id=3, display_name="Mia Monteurin")
    antwort = client.post(f"/api/service-reports/{bericht}/findings", json={**BEFUND, "action": "sofort_behoben"})
    assert antwort.status_code == 200, antwort.text
    assert (antwort.json()["created_by_name"], antwort.json()["created_by_employee_id"], antwort.json()["closed_by_employee_id"]) == (
        "Mia Monteurin", mia.id, mia.id)


@pytest.mark.parametrize("rolle", ["admin", "buero_finanzen", "field"])
def test_erfasst_von_mitgeschickt_422(threaded_db_session, router_test_client, rolle):
    db = threaded_db_session
    _, mia, bea, bericht = _welt(db)
    client = router_test_client(db, findings_router, role=rolle, employee_id=mia.id if rolle == "field" else bea.id)
    for wert in (mia.id, bea.id, None):
        antwort = client.post(f"/api/service-reports/{bericht}/findings", json={**BEFUND, "created_by_employee_id": wert})
        assert antwort.status_code == 422, antwort.text
    assert db.scalar(select(Finding)) is None


def test_altbestand_nennt_den_mitarbeiter(threaded_db_session, router_test_client):
    from app.findings import create_finding
    db = threaded_db_session
    _, mia, _, bericht = _welt(db)
    create_finding(db, bericht, "alt", "gering", "buero_pruefen", created_by_employee_id=mia.id)  # wie vor 1.9.112: ohne Konto
    [befund] = router_test_client(db, findings_router).get(f"/api/service-reports/{bericht}/findings").json()
    assert befund["created_by_name"] == "Mia Monteurin"


# seit 1.9.121 Büro – Finanzen True (bis 1.9.120 False: nur der Admin)
@pytest.mark.parametrize("rolle, darf", [("admin", True), ("buero_finanzen", True), ("buero_auftrag", False), ("field", False)])
def test_durchgefuehrt_von_regel_und_server(threaded_db_session, router_test_client, rolle, darf):
    db = threaded_db_session
    order, mia, bea, _ = _welt(db)
    assert darf_zeit_fuer_andere_buchen(AppUser(username="x", role=rolle)) is darf
    eigen = mia if rolle == "field" else bea
    fremd = bea if rolle == "field" else mia
    client = router_test_client(db, reports_router, role=rolle, employee_id=eigen.id)
    neu = {"report_type": "rapport", "description": "Reparatur"}
    fremd_antwort = client.post(f"/api/orders/{order.id}/service-reports", json={**neu, "created_by_employee_id": fremd.id})
    assert fremd_antwort.status_code == (200 if darf else 403), fremd_antwort.text
    eigen_antwort = client.post(f"/api/orders/{order.id}/service-reports", json={**neu, "created_by_employee_id": eigen.id})
    assert eigen_antwort.status_code == 200, eigen_antwort.text


@nur_mit_node
@pytest.mark.parametrize("rolle", ["admin", "buero_finanzen", "buero_auftrag"])
def test_einsatzberichte_seite_bietet_nur_an_was_der_server_annimmt(threaded_db_session, router_test_client, rolle):
    """„Durchgeführt von“ in node auf der vom Server gezeichneten Seite: Admin und (seit 1.9.121) Büro – Finanzen bekommen alle Mitarbeiter
    (eigener vorgewählt), Büro – Auftrag „— nicht zugeordnet —“ und sich selbst (vorgewählt) -- genau das, was der Server annimmt
    (test_durchgefuehrt_von_regel_und_server)."""
    from app.routers.pages import router as pages_router
    from tests.gerenderte_seite import gerenderte_seite
    from tests.test_v334_auswahl_restfaelle import im_browser
    db = threaded_db_session
    order, mia, bea, _ = _welt(db)
    html = router_test_client(db, pages_router, role=rolle, employee_id=bea.id).get(f"/orders/{order.id}/service-reports").text
    ablauf = (f"authStatus={{user:{{employee_id:{bea.id}}}}};employees=[{{id:{mia.id},first_name:'Mia',last_name:'Monteurin',active:true}},"
              f"{{id:{bea.id},first_name:'Bea',last_name:'Büro',active:true}}];"
              r'const h=durchgefuehrtVonOptionen();return [...h.matchAll(/<option value="(\d*)"([^>]*)>([^<]*)</g)].map(m=>[m[1],m[3],/selected/.test(m[2])]);')
    optionen = im_browser(gerenderte_seite(html, "\ninit();"), ablauf)["ergebnis"]
    if rolle in ("admin", "buero_finanzen"):  # seit 1.9.121 auch Büro – Finanzen (bis 1.9.120 nur der Admin)
        assert [o[1] for o in optionen] == ["— nicht zugeordnet —", "Mia Monteurin", "Bea Büro"]
    else:
        assert [o[1] for o in optionen] == ["— nicht zugeordnet —", "Bea Büro"]
    assert [o[1] for o in optionen if o[2]] == ["Bea Büro"]


def test_berichtsseite_schickt_kein_erfasst_von_und_zeigt_es():
    from pathlib import Path
    text = (Path(__file__).resolve().parent.parent / "app" / "templates" / "service_report.html").read_text(encoding="utf-8")
    anlegen = re.search(r"aktion\('befund-anlegen'.*?\n\}\);", text, re.S).group(0)
    assert "created_by_employee_id" not in anlegen
    assert "erfasst von '+esc(f.created_by_name)" in text
