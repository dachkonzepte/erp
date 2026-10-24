"""Seit 1.9.75 (Stufe 4, R4 Nachtrag, Punkt 1): auf „Heute“ einen Bericht anlegen -- auch ohne Einsatz.

    Daten      GET /api/field-view/today liefert unter "heute" die Auftragsliste "auftraege" -- genau list_field_bookable_orders(), dieselbe
               Liste wie „Zeit nachtragen“ in „Meine Zeiten“ und dieselbe, für die das Anlegen gilt (field_order_in_list(), seit 1.9.74);
               mit und ohne Einsatz, auch wenn eine Zeit läuft
    Seite      ohne Einsatz in der Karte „Heute ist nichts eingeplant.“ der Knopf „Bericht anlegen“ (grün, 56 px), mit Einsatz unter den
               Karten „Bericht für einen anderen Auftrag“ (neutral, 48 px) -- beide öffnen „Für welchen Auftrag?“ mit den Zeilen aus
               H.auftraege, jede zur Seite des Auftrags mit ?neu=1; dort öffnet ?neu=1 nach dem Laden gleich „Bericht anlegen“
Die Bedienung im Browser prüft scripts/klicktest_bericht_ohne_einsatz.py.
"""

import re
from datetime import datetime, time, timedelta

import pytest

from app import berlin_time
from app.planning import list_field_bookable_orders
from app.routers import field_view as field_view_router
from app.time_tracking import start_timer
from tests import vorlagen_js as vj
from tests.test_v224_field_view import make_employee, make_team
from tests.test_v325_contract_basis import beauftragen, make_quote
from tests.test_v471_heute_server import _einsatz


@pytest.fixture
def welt(threaded_db_session, router_test_client, feste_uhr):
    db = threaded_db_session
    heute = berlin_time.berlin_today()
    w = {"db": db, "heute": heute, "team": make_team(db, "K-498", "Kolonne 498"), "client": router_test_client,
         "mia": make_employee(db, "M-498", "Mia", "Monteurin"), "tom": make_employee(db, "T-498", "Tom", "Monteur")}
    w["gestern"] = beauftragen(db, make_quote(db, is_consumer=False, number="04981"))
    w["heute_auftrag"] = beauftragen(db, make_quote(db, is_consumer=False, number="04982"))
    _einsatz(w, w["gestern"], [(heute - timedelta(days=1), heute - timedelta(days=1))], [w["mia"], w["tom"]])
    _einsatz(w, w["heute_auftrag"], [(heute, heute)], [w["tom"]])
    return w


def _heute(w, emp):
    antwort = w["client"](w["db"], field_view_router.router, role="field", employee_id=emp.id).get("/api/field-view/today")
    assert antwort.status_code == 200, antwort.text
    return antwort.json()["heute"]


def test_ohne_einsatz_liefert_heute_die_liste(welt):
    h = _heute(welt, welt["mia"])
    assert h["einsaetze"] == []
    assert h["auftraege"] == [{**o} for o in list_field_bookable_orders(welt["db"], welt["mia"].id)]
    assert [o["id"] for o in h["auftraege"]] == [welt["gestern"].id]


def test_mit_einsatz_und_laufender_zeit_ebenso(welt):
    """Mit Einsatz (Tom) und während seine Zeit läuft -- die Liste steht trotzdem da (bis 1.9.74 nur in der Arbeitszeit, wenn nichts lief)."""
    start_timer(welt["db"], employee_id=welt["tom"].id, order_id=welt["heute_auftrag"].id,
                started_at=datetime.combine(welt["heute"], time(7)))
    h = _heute(welt, welt["tom"])
    assert h["arbeitszeit"]["zustand"] == "laeuft" and len(h["einsaetze"]) == 1
    assert sorted(o["id"] for o in h["auftraege"]) == sorted([welt["gestern"].id, welt["heute_auftrag"].id])
    assert h["auftraege"] == list_field_bookable_orders(welt["db"], welt["tom"].id)


def _skript(name):
    return vj.seitentext(name)[0]


def test_heute_knoepfe_und_dialog():
    text = _skript("mobil.html")
    assert re.search(r"Heute ist nichts eingeplant\.</p>'\s*\+'<div class=\"einsatz-wege\"><button type=\"button\" "
                     r"class=\"knopf knopf-aktion knopf-56\" id=\"berichtOhneEinsatz\">Bericht anlegen</button>", text)
    assert ("<div class=\"weitere-wege\"><button type=\"button\" class=\"knopf knopf-neutral knopf-klein\" id=\"berichtAndererAuftrag\">"
            "Bericht für einen anderen Auftrag</button></div>") in text
    assert ".knopf-56{height:56px;" in text and ".knopf-klein{height:48px;" in text
    assert "el('berichtOhneEinsatz').addEventListener('click',berichtDialogOeffnen)" in text
    assert "el('berichtAndererAuftrag').addEventListener('click',berichtDialogOeffnen)" in text
    dialog = re.search(r'<dialog id="berichtDialog" class="dialog-karte".*?</dialog>', text, flags=re.S)[0]
    assert '<h2 id="berichtDialogTitel">Für welchen Auftrag?</h2>' in dialog
    oeffnen = re.search(r"function berichtDialogOeffnen\(\)\{.*?\n  \}\n", text, flags=re.S)[0]
    assert "var liste=(H&&H.auftraege)||[];" in oeffnen  # die Liste vom Server, keine zweite
    assert "href=\"/orders/'+o.id+'/service-reports?neu=1\"" in oeffnen


def test_seite_des_auftrags_oeffnet_mit_neu_gleich_den_editor():
    text = _skript("service_reports.html")
    init = re.search(r"async function init\(\)\{.*?\n\}\ninit\(\);", text, flags=re.S)[0]
    stelle = init.index("new URLSearchParams(location.search).get('neu')==='1'")
    assert init.index("await loadReports();") < stelle < init.index("openCreateEditor();")
