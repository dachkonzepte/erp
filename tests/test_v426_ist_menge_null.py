"""Version 1.8.121 -- Ist-Menge 0 (Korrektur 119-4 vom 16.10.2026).

Ist-Mengen dürfen 0 sein: im Abschlag nach Leistungsstand eine Position, an der noch nichts gemacht ist, in der Schlussrechnung eine
nicht ausgeführte Position. „Menge ab 0,001“ (Festlegung 1.8.119-4) betrifft nur die Menge einer Angebotsposition und die Materialmenge
im Einsatzbericht -- die Ist-Menge einer Rechnung (InvoiceItemCreate/InvoiceItemUpdate.ist_quantity) steht auf dem Server auf „ab 0“, im
Browser ohne Untergrenze. Dieser Test sichert es ab: über die echten Routen festgeschrieben, die Seite schickt „0“ als 0, und keine
Ist-Menge bekommt eine Untergrenze über 0 (Server und Browser)."""

from __future__ import annotations

import json
import re
from decimal import Decimal

import pytest
from pydantic import BaseModel

from app import schemas
from app.invoices import compute_invoice_totals
from app.models import Invoice
from app.routers.invoices import router as invoices_router
from tests.leistungszeitraum import ZEITRAUM_JSON, festschreiben
from tests.test_v133_invoices import make_order_with_item
from tests.test_v314_dashboard_month_berlin import NODE
from tests.test_v334_auswahl_restfaelle import im_browser, seite
from tests.test_v385_auftrag_sperren import _leistungsstand, _zweite_position
from tests.test_v424_zahlgrenzen import ABGLEICH, _browser
from tests.zahlgrenzen import TEMPLATES, attribut, grenzen_im_markup, grenzen_im_schema, zahl_tags


def _positionen(antwort) -> list[dict]:
    assert antwort.status_code == 200, antwort.text
    return sorted(antwort.json()["items"], key=lambda i: (i["sort_order"], i["id"]))


def _ist(client, invoice_id, item_id, wert):
    return client.put(f"/api/invoices/{invoice_id}/items/{item_id}", json={"ist_quantity": wert})


def test_abschlag_nach_leistungsstand_mit_einer_position_ohne_leistung(threaded_db_session, router_test_client):
    db = threaded_db_session
    order, _ = make_order_with_item(db)                       # 100 m² zu 50 €
    _zweite_position(db, order)                               # 20 m zu 30 €, noch nicht begonnen
    client = router_test_client(db, invoices_router, role="buero_finanzen")
    antwort = client.post(f"/api/orders/{order.id}/invoices/abschlag-leistungsstand", json={})
    invoice_id = antwort.json()["id"]
    dach, rinne = _positionen(antwort)
    assert Decimal(rinne["ist_quantity"]) == 0                # Vorschlag: nie abgerechnet = 0
    _positionen(_ist(client, invoice_id, dach["id"], "40"))
    _positionen(_ist(client, invoice_id, rinne["id"], "5"))
    assert Decimal(_positionen(_ist(client, invoice_id, rinne["id"], "0"))[1]["ist_quantity"]) == 0   # bewusst zurück auf 0
    assert client.put(f"/api/invoices/{invoice_id}", json=ZEITRAUM_JSON).status_code == 200
    gesendet = client.post(f"/api/invoices/{invoice_id}/send")
    assert gesendet.status_code == 200, gesendet.text
    assert gesendet.json()["status"] == "versendet"
    assert [Decimal(p["ist_quantity"]) for p in _positionen(gesendet)] == [Decimal("40"), Decimal("0")]
    db.expire_all()
    assert compute_invoice_totals(db.get(Invoice, invoice_id))["net_total"] == Decimal("2000.00")   # nur die Dachfläche


def test_schlussrechnung_mit_einer_nicht_ausgefuehrten_position(threaded_db_session, router_test_client):
    db = threaded_db_session
    order, _ = make_order_with_item(db)
    _zweite_position(db, order)
    festschreiben(db, _leistungsstand(db, order, "40"))       # ein Abschlag auf die Dachfläche
    client = router_test_client(db, invoices_router, role="buero_finanzen")
    antwort = client.post(f"/api/orders/{order.id}/invoices/schlussrechnung", json={})
    invoice_id = antwort.json()["id"]
    dach, rinne = _positionen(antwort)
    assert Decimal(rinne["ist_quantity"]) == 20               # Vorschlag: Menge des Auftrags
    dach, rinne = _positionen(_ist(client, invoice_id, rinne["id"], "0"))   # die Rinne wurde nicht ausgeführt
    assert Decimal(rinne["ist_quantity"]) == 0 and "auftrag" in rinne["quantity_check"]["deviations"]  # markiert, nicht gesperrt
    assert client.put(f"/api/invoices/{invoice_id}", json=ZEITRAUM_JSON).status_code == 200
    gesendet = client.post(f"/api/invoices/{invoice_id}/send")
    assert gesendet.status_code == 200, gesendet.text
    body = gesendet.json()
    assert body["status"] == "versendet" and Decimal(_positionen(gesendet)[1]["ist_quantity"]) == 0
    aufstellung = body["final_breakdown"]
    assert Decimal(str(aufstellung["positions_net"])) == Decimal("5000.00")       # 100 × 50 €, ohne die Rinne
    assert Decimal(str(aufstellung["amount_net"])) == Decimal("3000.00")          # abzüglich des Abschlags (40 × 50 €)


def test_unter_0_bleibt_abgelehnt(threaded_db_session, router_test_client):
    db = threaded_db_session
    order, _ = make_order_with_item(db)
    client = router_test_client(db, invoices_router, role="buero_finanzen")
    antwort = client.post(f"/api/orders/{order.id}/invoices/abschlag-leistungsstand", json={})
    (dach,) = _positionen(antwort)
    assert _ist(client, antwort.json()["id"], dach["id"], "-0.001").status_code == 422
    assert schemas.InvoiceItemCreate(short_text="Rinne", unit="m", unit_price=Decimal("30"), ist_quantity=Decimal("0")).ist_quantity == 0


def _ist_felder_im_schema() -> list[str]:
    return sorted(f"{name}.{feld}" for name, klasse in vars(schemas).items()
                  if isinstance(klasse, type) and issubclass(klasse, BaseModel) and klasse.__module__ == schemas.__name__
                  for feld in klasse.model_fields if feld.startswith("ist_") and "quantity" in feld and not name.endswith("Out"))


def test_keine_ist_menge_hat_eine_untergrenze_ueber_0():
    """Server: jede Ist-Menge eines Eingabeschemas nimmt 0 an (ge=0, inklusive). Browser: jedes Feld „Ist-Menge“ und jeder Leseaufruf
    für eine Ist-Menge (aus dem Abgleich von 1.8.119) hat keine Untergrenze oder eine bis 0."""
    felder = _ist_felder_im_schema()
    assert felder == ["InvoiceItemCreate.ist_quantity", "InvoiceItemUpdate.ist_quantity"], felder
    for ref in felder:
        assert grenzen_im_schema(ref).min == (Decimal("0"), True), ref
    eintraege = [z for z in ABGLEICH if any(ref.split(".")[1].startswith("ist_") for ref in z.schemas)]
    assert len(eintraege) == 2
    for z in eintraege:
        untergrenze = _browser(z).min
        assert untergrenze is None or untergrenze[0] < 0 or untergrenze == (Decimal("0"), True), (z, untergrenze)
    markup = [tag for vorlage in sorted(TEMPLATES.glob("*.html")) for _, tag in zahl_tags(vorlage.read_text(encoding="utf-8"))
              if re.search(r"\bIst\b", attribut(tag, "data-feld") or attribut(tag, "aria-label") or "")]
    assert len(markup) == 3, markup                            # Dialog „Position“, Ist-Spalte der Rechnung und der Schlussrechnung
    for tag in markup:
        untergrenze = grenzen_im_markup(tag).min
        assert untergrenze is None or untergrenze[0] <= 0, tag


def _dataset(tag: str) -> dict:
    """Die data-Attribute eines Felds wie im Browser (dataset): data-zahl → zahl, ohne Wert ''."""
    return {re.sub(r"-(\w)", lambda m: m.group(1).upper(), name): wert
            for name, wert in re.findall(r'\sdata-([a-z][a-z-]*)(?:="([^"]*)")?', tag)}


@pytest.mark.skipif(NODE is None, reason="node nicht installiert")
def test_die_rechnungsseite_schickt_0_als_ist_menge():
    """Ist-Spalte (Text und jedes Feld mit den data-Attributen aus der Vorlage) und Dialog „Position“ (Ändern und Neu, ebenso mit den
    data-Attributen aus der Vorlage) schicken „0“ als 0 -- keine Meldung, keine Untergrenze."""
    tags = [tag for _, tag in zahl_tags((TEMPLATES / "invoice_detail.html").read_text(encoding="utf-8")) if "Ist-Menge" in tag]
    dialog = next(tag for tag in tags if 'id="itIst"' in tag)
    spalten = [_dataset(tag) for tag in tags if tag != dialog]
    assert len(spalten) == 2
    lauf = im_browser(seite("invoice_detail.html", "\nload()"), f"""
      zeigeRechnung = () => {{}};
      Object.assign(_element('itIst').dataset, {json.dumps(_dataset(dialog))});
      await quickIst(7, '0');
      for (const [nr, dataset] of {json.dumps(spalten)}.entries()) {{
        const feld = _element('istFeld' + nr); Object.assign(feld.dataset, dataset); feld.value = '0';
        await quickIst(8 + nr, feld);
      }}
      for (const [id, wert] of [['itShort', 'Rinne'], ['itLong', ''], ['itUnit', 'm'], ['itPrice', '30'], ['itIst', '0']])
        _element(id).value = wert;
      editItemId = 10; await saveItemDialog();
      editItemId = null; await saveItemDialog();
      return {{status: _element('itemStatus').textContent || ''}};""")
    aufrufe = [(a["methode"], a["url"], a["body"]["ist_quantity"]) for a in lauf["aufrufe"] if a["methode"] != "GET"]
    assert aufrufe == [("PUT", "/api/invoices/1/items/7", 0), ("PUT", "/api/invoices/1/items/8", 0), ("PUT", "/api/invoices/1/items/9", 0),
                       ("PUT", "/api/invoices/1/items/10", 0), ("POST", "/api/invoices/1/items", 0)], aufrufe
    assert lauf["ergebnis"]["status"] == ""
