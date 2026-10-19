"""Nachrunde 2 zur Fehlerrunde (1.8.151 ff., Vorgabe vom 19.10.2026): erst prüfen, dann je Punkt ein Test, der vor der Behebung scheiterte.

    1  Prüfung: zahlLesen() seit 1.8.148 (Tabelle) und Rundweg Menge/EP im Auftrag -- angezeigt mit Tausenderpunkt, unverändert
       gespeichert, derselbe Betrag in der Datenbank (1.8.151)
"""

import json
from decimal import Decimal

import pytest

from tests.test_v334_auswahl_restfaelle import im_browser, nur_mit_node, seite
from tests.test_v414_zahleneingaben import _lesen


# ---------------------------------------------------------------------------
# 1. Prüfung: zahlLesen() und der Rundweg im Auftrag
# ---------------------------------------------------------------------------

def test_zahllesen_tabelle_seit_1_8_148():
    """Die verlangte Tabelle Eingabe → Ergebnis (Regel 34: Komma dezimal, Punkt nur als Tausender vor je drei Ziffern)."""
    tabelle = {"1.234,50": 1234.5, "1.234": 1234, "1,5": 1.5, "1.5": "nicht eindeutig", "1234.5": "nicht eindeutig",
               "12.345.678,9": 12345678.9}
    ergebnis = _lesen([[t, {"feld": "Menge"}] for t in tabelle])
    gelesen = {t: (e["wert"] if "wert" in e else ("nicht eindeutig" if "nicht eindeutig" in e["fehler"] else e["fehler"]))
               for t, e in zip(tabelle, ergebnis)}
    assert gelesen == tabelle


RUNDWEG = r"""
  renderOrderEmailSection = () => {};  // Versand-Karte (_email_dispatch.html, nicht in der Attrappe) -- hier ohne Belang
  const puts = [];
  globalThis.fetch = async (url, opt = {}) => {
    if ((opt.method || 'GET') !== 'GET') puts.push({url, body: JSON.parse(opt.body)});
    const antwort = /^\/api\/orders\/\d+(\/items\/\d+)?$/.test(url) ? ORDER : [];  // Auftrag; sonst (Module u. a. beim Neuzeichnen) leer
    return {ok: true, status: 200, statusText: 'OK', headers: {get: () => 'application/json'}, json: async () => antwort};
  };
  order = JSON.parse(JSON.stringify(ORDER)); units = [];
  const i = order.items[0];
  const zeile = rowHtml(i);
  const angezeigt = {menge: /data-feld="Menge" value="([^"]*)"/.exec(zeile)[1], ep: /data-feld="Einheitspreis" value="([^"]*)"/.exec(zeile)[1]};
  // LV-Zeile: das Feld mit dem angezeigten Text, unverändert verlassen (onchange)
  for (const [feld, wert] of [['quantity', angezeigt.menge], ['unit_price', angezeigt.ep]]) {
    const el = _element('lv_' + feld); el.value = wert;
    await quickItem(i.id, feld, el);
  }
  // Dialog der Position: geöffnet, unverändert gespeichert
  openItem(i.id);
  const dialog = {menge: _element('iQty').value, ep: _element('iPrice').value};
  await saveItemDialog();
  return {angezeigt, dialog, puts};
"""


@nur_mit_node
@pytest.mark.parametrize("menge,ep", [("12345.678", "1234.56"), ("1234.5", "1000"), ("1000000", "0.5"), ("0.125", "12345678.9")])
def test_auftrag_rundweg_menge_und_ep_mit_tausenderpunkt(threaded_db_session, router_test_client, menge, ep):
    """Angezeigt mit Tausenderpunkt (1.8.148), unverändert gespeichert -- aus der LV-Zeile und aus dem Dialog -- ergibt in der Datenbank
    denselben Betrag. Die Anfragen baut das echte Seitenskript (node), gesendet werden sie an den echten Dienst."""
    from app.models import OrderItem
    from app.routers.orders import router as orders_router
    from tests.test_v133_invoices import make_order_with_item

    db = threaded_db_session
    order, item = make_order_with_item(db, quantity=Decimal(menge), unit_price=Decimal(ep))
    client = router_test_client(db, orders_router, role="buero_finanzen")
    auftrag = client.get(f"/api/orders/{order.id}").json()
    lauf = im_browser(seite("order.html", "load().catch(e=>document.querySelector('main')"),
                      f"const ORDER = {json.dumps(auftrag)};" + RUNDWEG)["ergebnis"]
    assert len(lauf["puts"]) == 3, lauf["puts"]  # Menge, EP aus der Zeile, dann der Dialog
    for put in lauf["puts"]:
        antwort = client.put(f"/api/orders/{order.id}/items/{item.id}", json=put["body"])
        assert antwort.status_code == 200, antwort.text
        db.expire_all()
        gespeichert = db.get(OrderItem, item.id)
        assert (gespeichert.quantity, gespeichert.unit_price) == (Decimal(menge), Decimal(ep)), (put["body"], lauf["angezeigt"])
    assert lauf["dialog"] == lauf["angezeigt"]
    if Decimal(menge) >= 1000:
        assert "." in lauf["angezeigt"]["menge"]  # wirklich mit Tausenderpunkt angezeigt
