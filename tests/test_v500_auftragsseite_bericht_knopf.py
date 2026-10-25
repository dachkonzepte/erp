"""Seit 1.9.77 (Stufe 4, R4 Nachtrag 2, Punkt 2): „+ Bericht“ auf der Seite des Auftrags nur, wenn die Monteurin dort anlegen darf --
1.9.77–1.9.78 bei Aufträgen ihrer Liste, seit 1.9.79 (Nachtrag 3, A) bei jedem nicht stornierten Auftrag.

    Server     GET /api/orders/{id} meldet der Monteurin bericht_anlegen -- aus derselben Regel wie POST …/service-reports
               (seit 1.9.79 bericht_zum_auftrag_moeglich())
    Seite      service_reports.html zeichnet „+ Bericht“ für die Monteurin erst danach (vorher hidden) und zeigt sonst an seiner Stelle „Für diesen
               Auftrag legt das Büro Berichte an.“; ?neu=1 öffnet „Bericht anlegen“ nur, wenn sie darf (wartet dafür auf den Auftrag)
Zugänglich: ohne Datum zugeordnet, eigener Bericht, außerhalb der 14 Tage datiert, abgeschlossen mit eigenem Bericht -- seit 1.9.79 alle mit
„+ Bericht“; storniert mit eigenem Bericht ohne. Die Seite im Browser prüft scripts/klicktest_bericht_ohne_einsatz.py.
"""

import re
from datetime import timedelta

import pytest

from app import berlin_time
from app.models import WorkPreparation, WorkPreparationEmployee
from app.routers import orders as orders_router
from app.routers import service_reports as service_reports_router
from app.service_reports import create_report
from tests import vorlagen_js as vj
from tests.test_v224_field_view import make_employee, make_team
from tests.test_v325_contract_basis import beauftragen, make_quote
from tests.test_v471_heute_server import _einsatz


@pytest.fixture
def welt(threaded_db_session, router_test_client, feste_uhr):
    db = threaded_db_session
    heute = berlin_time.berlin_today()
    mia = make_employee(db, "M-500", "Mia", "Monteurin")
    namen = ("ohne_datum", "eigen", "alt", "abgeschlossen_eigen", "storniert_eigen")
    auftraege = {n: beauftragen(db, make_quote(db, is_consumer=False, number=f"0500{i}")) for i, n in enumerate(namen)}
    w = {"db": db, "mia": mia, "team": make_team(db, "K-500", "Kolonne 500"), "auftraege": auftraege}
    prep = WorkPreparation(order_id=auftraege["ohne_datum"].id, status="offen")
    db.add(prep); db.flush()
    db.add(WorkPreparationEmployee(preparation_id=prep.id, employee_id=mia.id))
    _einsatz(w, auftraege["alt"], [(heute - timedelta(days=40), heute - timedelta(days=40))], [mia])
    for n in ("eigen", "abgeschlossen_eigen", "storniert_eigen"):
        create_report(db, auftraege[n].id, "rapport", "Notdienst", created_by_employee_id=mia.id)
    auftraege["abgeschlossen_eigen"].status = "abgeschlossen"
    auftraege["storniert_eigen"].status = "storniert"
    db.commit()
    w["als_mia"] = router_test_client(db, orders_router.router, service_reports_router.router, role="field", employee_id=mia.id)
    w["buero"] = router_test_client(db, orders_router.router, service_reports_router.router)
    return w


def test_bericht_anlegen_folgt_dem_anlegen(welt):
    """Angriff: für jeden zugänglichen Auftrag meldet GET bericht_anlegen genau dann, wenn das Anlegen gelingt -- seit 1.9.79 bei jedem
    nicht stornierten (1.9.77–1.9.78: „alt“ und „abgeschlossen_eigen“ nein), beim stornierten nein."""
    client = welt["als_mia"]
    gemeldet, angelegt = {}, {}
    for name, order in welt["auftraege"].items():
        antwort = client.get(f"/api/orders/{order.id}")
        assert antwort.status_code == 200, (name, antwort.text)  # zugänglich (Zuordnung oder eigener Bericht)
        gemeldet[name] = antwort.json()["bericht_anlegen"]
        angelegt[name] = client.post(f"/api/orders/{order.id}/service-reports", json={"report_type": "rapport"}).status_code == 200
    assert gemeldet == angelegt == {"ohne_datum": True, "eigen": True, "alt": True, "abgeschlossen_eigen": True, "storniert_eigen": False}


def test_buero_legt_weiter_an(welt):
    order = welt["auftraege"]["alt"]
    assert welt["buero"].post(f"/api/orders/{order.id}/service-reports", json={"report_type": "rapport"}).status_code == 200


def test_seite_zeigt_knopf_nur_mit_bericht_anlegen():
    text = vj.seitentext("service_reports.html")[0]
    assert ('<button type="button" id="neuerBericht" data-klick="editor-auf"{% if monteursrahmen %} hidden{% endif %}>+ Bericht</button>'
            in text)
    assert '<span id="berichtNurBuero" class="muted" hidden>Für diesen Auftrag legt das Büro Berichte an.</span>' in text
    assert "function berichtAnlegenErlaubt(){return !monteursrahmen||!!(orderData&&orderData.bericht_anlegen)}" in text
    zeichnen = re.search(r"function berichtKnopfZeichnen\(\)\{.*?\n\}\n", text, flags=re.S)[0]
    assert "document.getElementById('neuerBericht').hidden=!darf;" in zeichnen
    assert "document.getElementById('berichtNurBuero').hidden=darf||!orderData;" in zeichnen
    init = re.search(r"async function init\(\)\{.*?\n\}\ninit\(\);", text, flags=re.S)[0]
    assert "berichtKnopfZeichnen();" in init
    neu = init[init.index("get('neu')==='1'"):]
    assert neu.index("await auftragGeladen;") < neu.index("if(berichtAnlegenErlaubt())openCreateEditor();")
