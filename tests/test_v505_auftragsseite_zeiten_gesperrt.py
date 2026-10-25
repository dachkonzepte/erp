"""Seit 1.9.82 (Stufe 4, R4 Nachtrag 3, B): auf der Seite eines abgeschlossenen oder stornierten Auftrags weicht „Zeit nachtragen“ dem
Hinweis.

    Server     GET /api/orders/{id} meldet der Monteurin zeiten_gesperrt -- die Meldung, mit der das Buchen abgelehnt wird
               (app/time_tracking.py::auftrag_zeiten_gesperrt(), dieselbe Regel), sonst null
    Seite      service_reports.html: zeitenKarteZeichnen() blendet Text und „Zeit nachtragen“ aus und zeigt die Meldung (#zeitenGesperrt);
               das Büro hat diese Karte nicht
Die Bedienung im Browser prüft scripts/klicktest_zeiten_abgeschlossen.py (Bilder 1 und 2).
"""

import re
from datetime import timedelta

from app.routers import orders as orders_router
from app.routers import time_tracking as time_tracking_router
from tests import vorlagen_js as vj
from tests.test_v325_contract_basis import beauftragen, make_quote
from tests.test_v471_heute_server import _einsatz, welt  # noqa: F401  (Fixture)


def test_zeiten_gesperrt_folgt_dem_buchen(welt):  # noqa: F811
    """Angriff: je Status meldet GET zeiten_gesperrt genau dann (mit genau der Meldung), wenn der Nachtrag der Monteurin abgelehnt wird."""
    auftraege = {"beauftragt": welt["order"],
                 "abgeschlossen": beauftragen(welt["db"], make_quote(welt["db"], is_consumer=False, number="0505a")),
                 "storniert": beauftragen(welt["db"], make_quote(welt["db"], is_consumer=False, number="0505b"))}
    for order in auftraege.values():
        _einsatz(welt, order, [(welt["heute"] - timedelta(days=3), welt["heute"])], [welt["mia"]])
    for status, order in auftraege.items():
        order.status = status
    welt["db"].commit()
    client = welt["client"](welt["db"], orders_router.router, time_tracking_router.router, role="field", employee_id=welt["mia"].id)
    for nr, (status, order) in enumerate(auftraege.items()):
        gemeldet = client.get(f"/api/orders/{order.id}").json()["zeiten_gesperrt"]
        nachtrag = client.post("/api/time-entries", json={"employee_id": welt["mia"].id, "order_id": order.id,
                                                          "work_date": (welt["heute"] - timedelta(days=nr + 1)).isoformat(),
                                                          "von": "07:00", "bis": "09:00"})
        if gemeldet is None:
            assert nachtrag.status_code == 200, (status, nachtrag.text)
        else:
            assert (nachtrag.status_code, nachtrag.json()["detail"]) == (403, gemeldet), status
    assert client.get(f"/api/orders/{welt['order'].id}").json()["zeiten_gesperrt"] is None


def _text():
    return vj.seitentext("service_reports.html")[0]


def test_seite_zeigt_den_hinweis_statt_zeit_nachtragen():
    text = _text()
    karte = re.search(r'<div class="card" id="zeitenKarte">.*?\n</div>', text, flags=re.S)[0]
    assert '<p class="muted" id="zeitenText"' in karte
    assert '<a class="zeit-nachtragen" id="zeitNachtragen" href="/mobil/zeiten">Zeit nachtragen</a>' in karte
    assert '<p class="muted" id="zeitenGesperrt" style="margin:0" hidden></p>' in karte
    assert ".zeit-nachtragen[hidden]{display:none}" in text  # sonst gewinnt display:inline-flex über hidden
    zeichnen = re.search(r"function zeitenKarteZeichnen\(\)\{.*?\n\}\n", text, flags=re.S)[0]
    assert "if(!monteursrahmen||!orderData)return;" in zeichnen
    assert "const gesperrt=orderData.zeiten_gesperrt||'';" in zeichnen
    for teil in ("document.getElementById('zeitenText').hidden=!!gesperrt;", "document.getElementById('zeitNachtragen').hidden=!!gesperrt;",
                 "hinweis.textContent=gesperrt;", "hinweis.hidden=!gesperrt;"):
        assert teil in zeichnen, teil
    assert "    berichtKnopfZeichnen();\n    zeitenKarteZeichnen();\n" in text  # nach dem Laden des Auftrags
