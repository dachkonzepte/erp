"""Nachrunde zur Fehlerrunde (1.8.143 ff., Vorgabe vom 19.10.2026): je Punkt ein Test, der vor der Behebung scheiterte.

Die Punkte 1–3 (Zeit buchen, Gruppenzeit stoppen, Kennzeichen entziehen) stehen in tests/test_v437_befund_zeit_fuer_andere.py.

    4  users.html: Zurück-Link mit echtem Ziel statt history.back() (1.8.146)
    5  Stammdaten-Formular: nach dem Speichern in den Bereich der Liste, auch für Ressourcen (1.8.147)
    6  Auftrag: Menge und Einheitspreis mit Tausenderpunkt über zahlText() (1.8.148)
"""

import html
import json
import re

import pytest

from tests.test_v334_auswahl_restfaelle import TEMPLATES, im_browser, nur_mit_node, seite
from tests.test_v414_zahleneingaben import _js


# ---------------------------------------------------------------------------
# 4. users.html: Zurück-Link mit echtem Ziel
# ---------------------------------------------------------------------------

def test_benutzerseite_zurueck_in_die_einstellungen(threaded_db_session, router_test_client):
    """Bis 1.8.145 ging „← Einstellungen“ per history.back() zurück -- nach direktem Aufruf ins Leere."""
    from app.routers.pages import router as pages_router

    antwort = router_test_client(threaded_db_session, pages_router, role="admin").get("/users")
    assert antwort.status_code == 200
    markup = re.sub(r"<script.*?</script>", "", antwort.text, flags=re.S | re.I)
    links = re.findall(r'<a[^>]*class="back"[^>]*>.*?</a>', markup, flags=re.S)
    assert len(links) == 1, links
    assert re.search(r'href="([^"]*)"', links[0]).group(1) == "/settings"
    assert "onclick" not in links[0] and "history.back" not in antwort.text
    assert html.unescape(re.sub(r"<[^>]+>", "", links[0])).strip() == "← Einstellungen"
    assert router_test_client(threaded_db_session, pages_router, role="admin").get("/settings").status_code == 200


# ---------------------------------------------------------------------------
# 5. Stammdaten-Formular: nach dem Speichern in den richtigen Bereich
# ---------------------------------------------------------------------------

SPEICHERN_FETCH = r"""
  globalThis.fetch = async (url, opt = {}) => ({ok: true, status: 200, statusText: 'OK', headers: {get: () => 'application/json'},
                                                json: async () => ({id: 7})});
  _element('name').value = 'Kran';
  await save();
  return {ziel: location.href, meldung: _element('msg').textContent || ''};
"""


@nur_mit_node
@pytest.mark.parametrize("adresse,ziel", [
    ("/master-data/resources/new", "/master-data#assets"),
    ("/master-data/resources/3/edit", "/master-data#assets"),
    ("/master-data/teams/5/edit", "/master-data#teams"),
])
def test_stammdaten_formular_springt_in_den_bereich_der_liste(threaded_db_session, router_test_client, adresse, ziel):
    """Bis 1.8.146 sprang das Formular nach dem Speichern auf '/master-data#'+Art -- für Ressourcen „#resources“, den Bereich gibt es
    nicht, die Liste zeigte Kunden. Das Skript der vom Server gezeichneten Seite in node."""
    from app.routers.pages import router as pages_router
    from tests.gerenderte_seite import gerenderte_seite

    html_text = router_test_client(threaded_db_session, pages_router, role="buero_finanzen").get(adresse).text
    ergebnis = im_browser(gerenderte_seite(html_text, "init()"), SPEICHERN_FETCH)["ergebnis"]
    assert ergebnis == {"ziel": ziel, "meldung": ""}


def test_jeder_stammdatenbereich_hat_einen_bereich_der_liste():
    """Jedes Ziel nach dem Speichern (und jeder Zurück-Link) ist ein Bereich, den die Liste kennt (viewFromHash in master_data.html)."""
    from app.routers.pages import STAMMDATEN_BEREICHE

    quelle = (TEMPLATES / "master_data.html").read_text(encoding="utf-8")
    bekannt = set(re.findall(r"'(\w+)'", re.search(r"function viewFromHash\(\)\{.*?\[(.*?)\]", quelle, flags=re.S).group(1)))
    assert {bereich for bereich, _ in STAMMDATEN_BEREICHE.values()} <= bekannt
    assert "resources" not in bekannt  # der Bereich, auf den das Formular bis 1.8.146 sprang


# ---------------------------------------------------------------------------
# 6. Auftrag: Menge und Einheitspreis mit Tausenderpunkt
# ---------------------------------------------------------------------------

@nur_mit_node
def test_zahltext_mit_tausenderpunkt_und_zurueck():
    """Seit 1.8.148 setzt zahlText(wert, stellen, {tausender: true}) den Tausenderpunkt; zahlLesen() liest ihn unverändert zurück.
    Ohne die Option wie bisher ohne Punkt (tests/test_v414_zahleneingaben.py)."""
    faelle = [[12345.678, None], [1234.56, None], [-1234.5, 2], [999, None], [1250, None], [1234567.891, None], [0.5, None],
              ["12345.678", None], [None, None]]
    ergebnis = _js(f"process.stdout.write(JSON.stringify({json.dumps(faelle)}.map(([w,s])=>zahlText(w,s===null?undefined:s,{{tausender:true}}))));")
    assert ergebnis == ["12.345,678", "1.234,56", "-1.234,50", "999", "1.250", "1.234.567,891", "0,5", "12.345,678", ""]
    werte = [0, 7.5, 1250, 1250.5, 999999.99, -3.75, 1234567.891, 12345.678, 100000]
    assert _js(f"process.stdout.write(JSON.stringify({json.dumps(werte)}.map(w=>zahlLesen(zahlText(w,undefined,{{tausender:true}})))));") == werte
    assert _js("process.stdout.write(JSON.stringify(zahlText(12345.678)));") == "12345,678"


@nur_mit_node
def test_auftrag_zeigt_menge_und_ep_mit_tausenderpunkt():
    """Bis 1.8.147 standen Menge und Einheitspreis im LV des Auftrags ohne Tausenderpunkt („12345,678“, „1234,56“)."""
    position = {"id": 4, "position_number": "1", "short_text": "Dach", "quantity": "12345.678", "unit": "m²", "unit_price": "1234.56",
                "line_total": "15241480.23", "include_in_total": True}
    lauf = im_browser(seite("order.html", "load().catch(e=>document.querySelector('main')"), f"""
      order = {{order_lock: null, items: [{json.dumps(position)}]}}; units = [];
      const zeile = rowHtml({json.dumps(position)});
      openItem(4);
      return {{menge: /data-feld="Menge" value="([^"]*)"/.exec(zeile)[1], ep: /data-feld="Einheitspreis" value="([^"]*)"/.exec(zeile)[1],
               dialogMenge: _element('iQty').value, dialogEp: _element('iPrice').value}};""")
    assert lauf["ergebnis"] == {"menge": "12.345,678", "ep": "1.234,56", "dialogMenge": "12.345,678", "dialogEp": "1.234,56"}
