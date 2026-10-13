"""Version 1.8.96 -- Teil-Update statt gemerkter Werte, zuerst Geld (Nebenbefund 3 der Durchsicht 1.8.25,
docs/archiv/teil-updates.md).

Diese Oberflächen schickten beim Speichern Werte nicht bearbeiteter Felder mit, die die Seite beim Laden gemerkt hatte, und der
Server übernahm jedes Feld. Wurde ein solcher Wert nach dem Laden der Seite anderswo geändert, schrieb das Speichern den alten
Wert zurück:

    Angebots-Editor  saveInlineField   Menge/Einheit inline: Kurztext, Preis, Langtext … aus quote.items (zwei schnelle
                                       Änderungen derselben Position: die zweite schrieb den alten Wert der ersten zurück)
    Angebots-Editor  saveCalc          Preiseinheit je Material aus currentCalc (nicht im Formular)
    Angebots-Editor  Drag-and-drop     "in Summe" aus quote.items
    Auftragsseite    quickItem         Menge/Einheit/EP inline: Preis, Texte, "in Summe" aus order.items
    Eingangsrechn.   markPaidNow       die ganze Rechnung samt Positionen aus der Liste

Jetzt schickt jede Stelle nur, was sie bearbeitet, und die Endpunkte sind Teil-Updates (PartialUpdate, Regel 22). Die Tests
führen die echte Funktion der Vorlage in node aus (mit _speichern.html, api() über fetch), lesen den geschickten Body ab und
schicken ihn an den echten Server -- nach einem Wert, der NACH dem Laden der Seite anderswo geändert wurde.

Angriffe: ausdrückliches null in Pflichtfeldern 422, ein Teil-Update, das mit dem gespeicherten Stand ungültig wird, 422 ohne
etwas zu speichern, gesperrte Felder am Auftrag auch per Teil-Update 409, fremde IDs wie bisher abgelehnt.

Gleichzeitig (PostgreSQL, opt-in über ERP_TEST_POSTGRES_URL, Wegwerf-Schema): zwei Teil-Updates verschiedener Felder derselben
Zeile, die erste hält ihre Transaktion offen -- am Ende stehen beide, abgeleitete Werte passen. Kalkulation und Eingangsrechnung
lesen-ändern-schreiben (Einheitspreis aus der Kalkulation; Prüfungen über mehrere Felder) und laufen deshalb unter einer
Zeilensperre."""

import json
import re
import shutil
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from app.incoming_invoices import create_invoice
from app.invoices import create_schlussrechnung
from app.models import (
    IncomingInvoice, IncomingInvoiceItem, Order, OrderItem, QuoteItem, QuoteItemCalculation, QuoteItemLayout,
    QuoteItemMaterialCalculation, QuoteSection, Supplier,
)
from app.orders import load_order, order_to_dict
from app.projects import build_quote_item_calculation, load_quote, quote_to_dict
from app.recurring_costs import create_cost
from app.routers.incoming_invoices import put_incoming_invoice, router as incoming_router
from app.routers.orders import put_order_item, router as orders_router
from app.routers.quotes import router as quotes_router, update_quote_item, update_quote_item_calculation
from app.schemas import IncomingInvoiceUpdate, OrderItemUpdate, QuoteItemCalculationUpdate, QuoteItemUpdate
from tests.leistungszeitraum import festschreiben
from tests.test_v133_invoices import make_order_with_item
from tests.test_v167_pagination import make_quote_with_items
from tests.test_v325_contract_basis import beauftragen, make_quote
from tests.test_v329_teil_updates import klammer
from tests.test_v375_rechnungen_sperren import _run, _vorbereiten, pg  # noqa: F401  (pg ist eine Fixture)
from tests.test_v385_auftrag_sperren import _leistungsstand

TEMPLATES = Path(__file__).resolve().parent.parent / "app" / "templates"
NODE = shutil.which("node")
nur_mit_node = pytest.mark.skipif(NODE is None, reason="node nicht installiert -- die Tests führen die Vorlage aus.")
D = Decimal


# ---------------------------------------------------------------------------
# Die Funktion der Vorlage in node ausführen
# ---------------------------------------------------------------------------

HARNESS = r"""
var window = globalThis;
var AUFRUFE = [];
var ANTWORT = () => ({});
globalThis.fetch = async (url, opt = {}) => {
  const methode = opt.method || 'GET';
  AUFRUFE.push({url, methode, body: opt.body ? JSON.parse(opt.body) : null});
  const daten = ANTWORT(url, methode);
  return {ok: true, status: 200, statusText: 'OK', headers: {get: () => 'application/json'}, json: async () => daten};
};
async function api(url, opt = {}) { const r = await fetch(url, opt); return r.json(); }
const _el = {};
var document = {
  getElementById: id => _el[id] || (_el[id] = {id, value: '', textContent: '', className: '', style: {}, dataset: {},
    classList: {add() {}, remove() {}, toggle() {}}}),
  querySelectorAll: () => [], querySelector: () => null,
};
var alert = m => AUFRUFE.push({alert: String(m)});
var confirm = () => true;
"""


def js_funktion(vorlage: str, name: str) -> str:
    """Die ganze Funktion `name` aus dem Seitenskript der Vorlage (Kopf und Rumpf, wörtlich)."""
    html = (TEMPLATES / vorlage).read_text(encoding="utf-8")
    treffer = re.search(rf"(?:async\s+)?function {re.escape(name)}\s*\(", html)
    assert treffer, f"{vorlage}: function {name}() nicht gefunden -- Test anpassen"
    rumpf = html.index("{", html.index(")", treffer.end()))
    return html[treffer.start():rumpf] + klammer(html, rumpf)


def _speichern_js() -> str:
    html = (TEMPLATES / "_speichern.html").read_text(encoding="utf-8")
    return "\n".join(re.findall(r"<script>(.*?)</script>", html, flags=re.S))


def im_browser(vorlage: str, funktionen: list[str], vorbereitung: str, ablauf: str) -> list[dict]:
    """Führt `ablauf` (Rumpf einer async-Funktion) nach Attrappe, _speichern.html, `vorbereitung` (Zustand der Seite) und den
    genannten Funktionen der Vorlage aus; gibt jeden fetch-Aufruf zurück ({url, methode, body}) und jedes alert()."""
    from tests.test_v314_dashboard_month_berlin import _node
    js = (HARNESS + _speichern_js() + "\n" + vorbereitung + "\n"
          + "\n".join(js_funktion(vorlage, name) for name in funktionen)
          + f"\n(async () => {{ {ablauf} }})().then(() => process.stdout.write(JSON.stringify(AUFRUFE)))"
          ".catch(e => { console.error(e && e.stack || e); process.exit(1); });")
    return _node(js, "Europe/Berlin")


def schreibende(aufrufe: list[dict]) -> list[tuple[str, str, dict]]:
    return [(a["methode"], a["url"], a["body"]) for a in aufrufe if a.get("methode") not in (None, "GET")]


def senden(client, aufrufe: list[dict]) -> None:
    """Jede geschriebene Anfrage der Oberfläche, so wie sie ging, an den echten Server -- in derselben Reihenfolge."""
    for methode, adresse, body in schreibende(aufrufe):
        antwort = client.request(methode, adresse, json=body)
        assert antwort.status_code == 200, (adresse, body, antwort.text)


def js(wert) -> str:
    return json.dumps(wert, default=str)


def _zeile(db, model, row_id) -> dict:
    """Gespeicherter Stand der Zeile. Der Test-Client teilt sich die Sitzung mit dem Test; rollback() verwirft, was eine
    abgelehnte Anfrage nicht committet hat -- wie get_db() am Ende jeder echten Anfrage (close())."""
    db.rollback()
    row = db.get(model, row_id)
    return {c.name: getattr(row, c.name) for c in model.__table__.columns if c.name not in ("updated_at",)}


# ---------------------------------------------------------------------------
# Angebots-Editor
# ---------------------------------------------------------------------------

@pytest.fixture
def angebot(threaded_db_session, router_test_client):
    db = threaded_db_session
    quote = make_quote_with_items(db)  # eine Position: 10 m zu 12,50
    item = quote.items[0]
    item.long_text = "Langtext alt"
    titel = QuoteSection(quote_id=quote.id, title="Dach", sort_order=10)
    db.add(titel)
    db.commit()
    return {"db": db, "client": router_test_client(db, quotes_router), "quote_id": quote.id, "item_id": item.id,
            "titel": titel.id}


@nur_mit_node
def test_angebot_inline_schickt_nur_menge_bzw_einheit(angebot):
    """Zwei schnelle Inline-Änderungen derselben Position, beide aus dem Stand beim Laden; dazwischen hat jemand im
    Positions-Editor Preis und Kurztext geändert. Bis 1.8.95 schrieb die zweite Anfrage die alte Menge zurück und beide den alten
    Preis und Kurztext."""
    db, client, qid, iid = angebot["db"], angebot["client"], angebot["quote_id"], angebot["item_id"]
    beim_laden = client.get(f"/api/quotes/{qid}").json()
    item = db.get(QuoteItem, iid)
    item.unit_price, item.short_text = D("15"), "Lattung neu"
    db.commit()
    aufrufe = im_browser("quote_editor.html", ["saveInlineField"],
                         f"var quote = {js(beim_laden)}; var quoteId = {qid}; function renderAll() {{}}; ANTWORT = () => quote;",
                         f"const a = saveInlineField({iid}, 'quantity', '7', null); "
                         f"const b = saveInlineField({iid}, 'unit', 'Stk', null); await a; await b;")
    url = f"/api/quotes/{qid}/items/{iid}"
    assert schreibende(aufrufe) == [("PUT", url, {"quantity": 7}), ("PUT", url, {"unit": "Stk"})]
    senden(client, aufrufe)
    gespeichert = _zeile(db, QuoteItem, iid)
    assert (gespeichert["quantity"], gespeichert["unit"]) == (D("7"), "Stk")
    assert (gespeichert["unit_price"], gespeichert["short_text"], gespeichert["long_text"]) == (D("15"), "Lattung neu",
                                                                                                 "Langtext alt")


@nur_mit_node
def test_angebot_inline_ungueltige_menge_schickt_nichts(angebot):
    beim_laden = angebot["client"].get(f"/api/quotes/{angebot['quote_id']}").json()
    aufrufe = im_browser("quote_editor.html", ["saveInlineField"],
                         f"var quote = {js(beim_laden)}; var quoteId = {angebot['quote_id']}; function renderAll() {{}};",
                         f"await saveInlineField({angebot['item_id']}, 'quantity', '0', null);")
    assert schreibende(aufrufe) == []


@nur_mit_node
@pytest.mark.parametrize("zone,erwartet", [("titel", "titel"), ("", None)])
def test_angebot_drag_and_drop_schickt_nur_den_titel(angebot, zone, erwartet):
    """Nach dem Laden hat jemand "in Summe" abgewählt -- das Verschieben ließ es bis 1.8.95 wieder zu "in Summe" werden."""
    db, client, qid, iid = angebot["db"], angebot["client"], angebot["quote_id"], angebot["item_id"]
    if zone == "":  # Ziel "Positionen ohne Titel": die Position steht vorher unter dem Titel
        assert client.put(f"/api/quotes/{qid}/items/{iid}/layout", json={"section_id": angebot["titel"]}).status_code == 200
    beim_laden = client.get(f"/api/quotes/{qid}").json()
    assert client.put(f"/api/quotes/{qid}/items/{iid}/layout", json={"include_in_total": False}).status_code == 200
    abschnitt = str(angebot["titel"]) if zone == "titel" else ""
    aufrufe = im_browser(
        "quote_editor.html", ["wireDragDrop"],
        f"var quote = {js(beim_laden)}; var quoteId = {qid}; var dragNode = null; async function reloadQuote() {{}}; "
        f"var ZONE = {{dataset: {{section: {js(abschnitt)}}}, classList: {{add() {{}}, remove() {{}}}}}}; "
        "document.querySelectorAll = sel => sel === '.dropzone' ? [ZONE] : [];",
        f"wireDragDrop(); dragNode = {{kind: 'item', id: {iid}}}; await ZONE.ondrop({{preventDefault() {{}}}});")
    ziel = angebot["titel"] if erwartet else None
    assert schreibende(aufrufe) == [("PUT", f"/api/quotes/{qid}/items/{iid}/layout", {"section_id": ziel})]
    senden(client, aufrufe)
    db.expire_all()
    layout = db.scalar(select(QuoteItemLayout).where(QuoteItemLayout.quote_item_id == iid))
    assert (layout.section_id, layout.include_in_total) == (ziel, False)


def _kalkulation(db, item_id, labor_rate="60"):
    calc = QuoteItemCalculation(quote_item_id=item_id, site_time_minutes=D("30"), workshop_time_minutes=D("0"),
                                labor_rate=D(labor_rate), material_markup_pct=D("10"), equipment_cost=D("0"),
                                subcontractor_cost=D("0"), other_cost=D("0"), overhead_pct=D("10"), risk_profit_pct=D("5"),
                                notes="intern")
    db.add(calc)
    db.flush()
    material = QuoteItemMaterialCalculation(calculation_id=calc.id, name="Bitumenbahn", unit="Rolle", source_quantity=D("2"),
                                            quantity=D("2"), waste_pct=D("5"), source_purchase_price=D("40"),
                                            purchase_price=D("40"), price_basis=D("1"))
    db.add(material)
    db.commit()
    return calc.id, material.id


CALC_FORMULAR = {"site_time_minutes", "workshop_time_minutes", "labor_rate", "material_markup_pct", "equipment_cost",
                 "subcontractor_cost", "other_cost", "overhead_pct", "risk_profit_pct", "manual_sale_price", "notes", "materials"}
FORMULAR_IDS = {"site_time_minutes": "cSite", "workshop_time_minutes": "cWork", "labor_rate": "cLabor",
                "material_markup_pct": "cMatMarkup", "equipment_cost": "cEquip", "subcontractor_cost": "cSub",
                "other_cost": "cOther", "overhead_pct": "cOH", "risk_profit_pct": "cRisk"}


@nur_mit_node
def test_kalkulation_schickt_keine_preiseinheit(angebot):
    """Die Preiseinheit steht nicht im Formular; nach dem Laden wurde sie anderswo auf 10 gesetzt (Rolle zu 10 m). Bis 1.8.95
    schrieb das Speichern die gemerkte 1 zurück -- der Einheitspreis verzehnfachte den Materialanteil."""
    db, client, qid, iid = angebot["db"], angebot["client"], angebot["quote_id"], angebot["item_id"]
    _, mid = _kalkulation(db, iid)
    url = f"/api/quotes/{qid}/items/{iid}/calculation"
    beim_laden = client.get(url).json()
    db.get(QuoteItemMaterialCalculation, mid).price_basis = D("10")
    db.commit()
    formular = {FORMULAR_IDS[k]: beim_laden[k] for k in FORMULAR_IDS} | {"cLabor": "65", "cManual": "", "cNotes": "intern"}
    zeilen = [{"mid": m["id"], "mqty": m["quantity"], "mwaste": m["waste_pct"], "mprice": m["purchase_price"]}
              for m in beim_laden["materials"]]
    quote = client.get(f"/api/quotes/{qid}").json()
    aufrufe = im_browser(
        "quote_editor.html", ["saveCalc", "cn"],
        f"var FORM = {js(formular)}; function v(id) {{ return FORM[id] ?? ''; }} "
        f"var currentCalc = {js(beim_laden)}; var currentItem = {{id: {iid}}}; var quote = {js(quote)}; var quoteId = {qid}; "
        "function fillItemEditor() {} function fillCalc() {} function renderAll() {} "
        f"var ZEILEN = {js(zeilen)}; "
        "document.querySelectorAll = sel => sel === '#calcMaterials tr' ? ZEILEN.map(z => ({dataset: {mid: String(z.mid)}, "
        "querySelector: c => ({value: String(z[c.slice(1)])})})) : []; "
        "ANTWORT = (u, m) => m === 'GET' ? quote : currentCalc;",
        "await saveCalc();")
    [(methode, adresse, body)] = schreibende(aufrufe)
    assert (methode, adresse) == ("PUT", url)
    assert set(body) == CALC_FORMULAR and body["labor_rate"] == 65
    assert [set(m) for m in body["materials"]] == [{"id", "quantity", "waste_pct", "purchase_price"}]
    senden(client, aufrufe)
    material = _zeile(db, QuoteItemMaterialCalculation, mid)
    assert (material["price_basis"], material["quantity"]) == (D("10"), D("2"))
    item = db.get(QuoteItem, iid)
    ergebnis = build_quote_item_calculation(item)
    assert ergebnis["labor_rate"] == D("65") and item.unit_price == ergebnis["effective_sale_price"]


def test_kalkulation_teil_update_aendert_nur_gesendetes_und_den_preis(angebot):
    db, client, qid, iid = angebot["db"], angebot["client"], angebot["quote_id"], angebot["item_id"]
    calc_id, mid = _kalkulation(db, iid)
    url = f"/api/quotes/{qid}/items/{iid}/calculation"
    vorher = _zeile(db, QuoteItemCalculation, calc_id)
    assert client.put(url, json={"other_cost": "25"}).status_code == 200
    assert _zeile(db, QuoteItemCalculation, calc_id) == vorher | {"other_cost": D("25")}
    material = _zeile(db, QuoteItemMaterialCalculation, mid)
    assert client.put(url, json={"materials": [{"id": mid, "purchase_price": "44"}]}).status_code == 200
    assert _zeile(db, QuoteItemMaterialCalculation, mid) == material | {"purchase_price": D("44")}
    item = db.get(QuoteItem, iid)
    assert item.unit_price == build_quote_item_calculation(item)["effective_sale_price"]
    assert client.put(url, json={"manual_sale_price": "99", "notes": None}).status_code == 200
    db.expire_all()
    assert db.get(QuoteItem, iid).unit_price == D("99.00") and db.get(QuoteItemCalculation, calc_id).notes is None
    assert client.put(url, json={"manual_sale_price": None}).status_code == 200  # null: wieder der berechnete VK
    item = db.get(QuoteItem, iid)
    db.refresh(item)
    assert item.unit_price == build_quote_item_calculation(item)["calculated_sale_price"]


def test_angebotsposition_teil_update_laesst_den_rest_stehen(angebot):
    db, client, qid, iid = angebot["db"], angebot["client"], angebot["quote_id"], angebot["item_id"]
    vorher = _zeile(db, QuoteItem, iid)
    assert client.put(f"/api/quotes/{qid}/items/{iid}", json={"long_text": "Neu"}).status_code == 200
    assert _zeile(db, QuoteItem, iid) == vorher | {"long_text": "Neu"}
    assert client.put(f"/api/quotes/{qid}/items/{iid}", json={"gaeb_oz": "01.02"}).status_code == 200
    assert client.put(f"/api/quotes/{qid}/items/{iid}", json={"gaeb_oz": None}).status_code == 200  # nullbar: leert
    assert _zeile(db, QuoteItem, iid) == vorher | {"long_text": "Neu"}


# ---------------------------------------------------------------------------
# Auftragsseite
# ---------------------------------------------------------------------------

@pytest.fixture
def auftrag(threaded_db_session, router_test_client):
    db = threaded_db_session
    order, item = make_order_with_item(db)  # 100 Einheiten zu 50
    return {"db": db, "client": router_test_client(db, orders_router, role="buero_auftrag"), "order": order,
            "order_id": order.id, "item_id": item.id}


@nur_mit_node
def test_auftrag_inline_schickt_nur_das_bearbeitete_feld(auftrag):
    """Menge und Einheitspreis kurz nacheinander geändert, beide aus dem Stand beim Laden; dazwischen hat jemand im Dialog Texte
    und "in Summe" geändert. Bis 1.8.95 schrieb jede Anfrage den gemerkten Stand aller Felder zurück."""
    db, client, oid, iid = auftrag["db"], auftrag["client"], auftrag["order_id"], auftrag["item_id"]
    beim_laden = client.get(f"/api/orders/{oid}").json()
    item = db.get(OrderItem, iid)
    item.short_text, item.long_text, item.include_in_total = "Dacheindeckung neu", "mit Lattung", False
    db.commit()
    aufrufe = im_browser("order.html", ["quickItem"],
                         f"var order = {js(beim_laden)}; var orderId = {oid}; function zeigeAuftragMitLv(d) {{}} "
                         "async function reload() {} ANTWORT = () => order;",
                         f"const a = quickItem({iid}, 'quantity', '120'); const b = quickItem({iid}, 'unit_price', '55'); "
                         "await a; await b;")
    url = f"/api/orders/{oid}/items/{iid}"
    assert schreibende(aufrufe) == [("PUT", url, {"quantity": 120}), ("PUT", url, {"unit_price": 55})]
    senden(client, aufrufe)
    gespeichert = _zeile(db, OrderItem, iid)
    assert (gespeichert["quantity"], gespeichert["unit_price"]) == (D("120"), D("55"))
    assert (gespeichert["short_text"], gespeichert["long_text"], gespeichert["include_in_total"]) == (
        "Dacheindeckung neu", "mit Lattung", False)


@nur_mit_node
def test_auftrag_inline_einheit(auftrag):
    beim_laden = auftrag["client"].get(f"/api/orders/{auftrag['order_id']}").json()
    aufrufe = im_browser("order.html", ["quickItem"],
                         f"var order = {js(beim_laden)}; var orderId = {auftrag['order_id']}; "
                         "function zeigeAuftragMitLv(d) {} async function reload() {}",
                         f"await quickItem({auftrag['item_id']}, 'unit', 'm²');")
    assert schreibende(aufrufe) == [("PUT", f"/api/orders/{auftrag['order_id']}/items/{auftrag['item_id']}", {"unit": "m²"})]


def test_auftrag_abgerechnete_position_bleibt_per_teil_update_gesperrt(auftrag):
    """Einheitspreis, Einheit und "in Summe" einer abgerechneten Position: 409 auch, wenn nur das eine Feld kommt; Menge und
    Texte gehen; derselbe Wert ist keine Änderung."""
    db, client, order, iid = auftrag["db"], auftrag["client"], auftrag["order"], auftrag["item_id"]
    abschlag = festschreiben(db, _leistungsstand(db, order))
    url = f"/api/orders/{order.id}/items/{iid}"
    for body in ({"unit_price": "60"}, {"unit": "Stk."}, {"include_in_total": False}):
        antwort = client.put(url, json=body)
        assert antwort.status_code == 409 and abschlag.invoice_number in antwort.json()["detail"], body
    assert client.put(url, json={"unit_price": "50"}).status_code == 200  # unverändert
    assert client.put(url, json={"quantity": "120"}).status_code == 200
    assert client.put(url, json={"short_text": "Dacheindeckung neu"}).status_code == 200
    gespeichert = _zeile(db, OrderItem, iid)
    assert (gespeichert["quantity"], gespeichert["unit_price"], gespeichert["short_text"]) == (
        D("120"), D("50"), "Dacheindeckung neu")
    festschreiben(db, create_schlussrechnung(db, db.get(Order, order.id)))
    for body in ({"quantity": "90"}, {"long_text": "x"}, {"gaeb_oz": "01"}):
        antwort = client.put(url, json=body)
        assert antwort.status_code == 409 and "Nach der Schlussrechnung" in antwort.json()["detail"], body
    assert client.put(url, json={}).status_code == 200  # nichts geändert, nichts gesperrt
    assert _zeile(db, OrderItem, iid) == gespeichert


# ---------------------------------------------------------------------------
# Eingangsrechnungen
# ---------------------------------------------------------------------------

def _eingangsrechnung(db, **werte):
    lieferant = Supplier(supplier_number="L-399", name="Dachbaustoffe Nord", active=True)
    db.add(lieferant)
    db.commit()
    payload = {"supplier_id": lieferant.id, "supplier_invoice_number": "RE-1", "invoice_date": date(2026, 9, 1),
               "net_amount": "500.00", "tax_rate_pct": "19.00", "payment_status": "offen", "notes": "alt",
               "items": [{"description": "Bahnen", "net_amount": "500.00", "tax_rate_pct": "19.00"}]}
    payload.update(werte)
    return create_invoice(db, payload)["id"], lieferant.id


@pytest.fixture
def eingang(threaded_db_session, router_test_client):
    db = threaded_db_session
    invoice_id, supplier_id = _eingangsrechnung(db)
    order, _ = make_order_with_item(db)
    kosten = create_cost(db, {"label": "Miete", "net_amount": "100.00", "billing_interval": "monatlich"})
    return {"db": db, "client": router_test_client(db, incoming_router), "id": invoice_id, "url": f"/api/incoming-invoices/{invoice_id}",
            "project_id": order.project_id, "cost_id": kosten["id"]}


def _positionen(db, invoice_id):
    db.rollback()  # siehe _zeile()
    return [(i.description, i.net_amount) for i in sorted(db.get(IncomingInvoice, invoice_id).items, key=lambda i: i.id)]


@nur_mit_node
def test_als_bezahlt_markieren_schickt_nur_status_und_datum(eingang):
    """Nach dem Laden der Liste hat jemand die Rechnung bearbeitet (Positionen, Notiz, Projekt). Bis 1.8.95 schrieb "als bezahlt
    markieren" die ganze Rechnung samt Positionen aus dem Stand beim Laden zurück."""
    db, client = eingang["db"], eingang["client"]
    beim_laden = client.get("/api/incoming-invoices").json()
    neu = {"net_amount": "600.00", "notes": "Skonto geprüft", "project_id": eingang["project_id"],
           "items": [{"description": "Bahnen", "net_amount": "450.00"}, {"description": "Fracht", "net_amount": "150.00"}]}
    assert client.put(eingang["url"], json=neu).status_code == 200
    aufrufe = im_browser("incoming_invoices.html", ["markPaidNow"],
                         f"var invoices = {js(beim_laden)}; function berlinToday() {{ return '2026-10-13'; }} "
                         "async function loadAll() {}",
                         f"await markPaidNow({eingang['id']});")
    assert schreibende(aufrufe) == [("PUT", eingang["url"], {"payment_status": "bezahlt", "payment_date": "2026-10-13"})]
    senden(client, aufrufe)
    gespeichert = _zeile(db, IncomingInvoice, eingang["id"])
    assert (gespeichert["payment_status"], gespeichert["payment_date"]) == ("bezahlt", date(2026, 10, 13))
    assert (gespeichert["net_amount"], gespeichert["notes"], gespeichert["project_id"]) == (
        D("600.00"), "Skonto geprüft", eingang["project_id"])
    assert _positionen(db, eingang["id"]) == [("Bahnen", D("450.00")), ("Fracht", D("150.00"))]


def test_eingangsrechnung_pruefungen_auf_dem_zusammengefuehrten_stand(eingang):
    """Zuordnung, Summe der Positionen und Zahlungsdatum prüfen gespeicherten Stand + gesendete Werte; abgelehnt wird nichts
    gespeichert."""
    db, client, url = eingang["db"], eingang["client"], eingang["url"]
    assert client.put(url, json={"project_id": eingang["project_id"]}).status_code == 200
    vorher = _zeile(db, IncomingInvoice, eingang["id"])
    antwort = client.put(url, json={"recurring_cost_id": eingang["cost_id"], "notes": "x"})
    assert antwort.status_code == 422 and "nur einem Projekt" in antwort.json()["detail"]
    antwort = client.put(url, json={"net_amount": "600.00", "notes": "x"})  # Positionen ergeben 500
    assert antwort.status_code == 422 and "Summe der Positionen" in antwort.json()["detail"]
    antwort = client.put(url, json={"items": [{"description": "Bahnen", "net_amount": "400.00"}]})
    assert antwort.status_code == 422 and "Summe der Positionen" in antwort.json()["detail"]
    assert _zeile(db, IncomingInvoice, eingang["id"]) == vorher
    assert _positionen(db, eingang["id"]) == [("Bahnen", D("500.00"))]
    # mit dem Wechsel der Zuordnung bzw. passenden Positionen geht es
    assert client.put(url, json={"recurring_cost_id": eingang["cost_id"], "project_id": None}).status_code == 200
    assert client.put(url, json={"net_amount": "600.00", "items": []}).status_code == 200
    gespeichert = _zeile(db, IncomingInvoice, eingang["id"])
    assert (gespeichert["project_id"], gespeichert["recurring_cost_id"], gespeichert["net_amount"]) == (
        None, eingang["cost_id"], D("600.00"))
    assert _positionen(db, eingang["id"]) == []
    # Zahlungsdatum nur bei "bezahlt" -- auch wenn der Status nicht mitkommt
    assert client.put(url, json={"payment_date": "2026-10-01"}).status_code == 200
    assert _zeile(db, IncomingInvoice, eingang["id"])["payment_date"] is None


def test_eingangsrechnung_ohne_items_behaelt_die_positionen(eingang):
    db, client, url = eingang["db"], eingang["client"], eingang["url"]
    vorher = _zeile(db, IncomingInvoice, eingang["id"])
    assert client.put(url, json={"notes": None}).status_code == 200  # nullbar: leert
    assert _zeile(db, IncomingInvoice, eingang["id"]) == vorher | {"notes": None}
    assert _positionen(db, eingang["id"]) == [("Bahnen", D("500.00"))]


# ---------------------------------------------------------------------------
# Angriffe: null in Pflichtfeldern, fremde IDs
# ---------------------------------------------------------------------------

NULL_ANGEBOT = ["quantity", "short_text", "long_text", "unit", "unit_price", "position_type"]
NULL_KALKULATION = ["site_time_minutes", "workshop_time_minutes", "labor_rate", "material_markup_pct", "equipment_cost",
                    "subcontractor_cost", "other_cost", "overhead_pct", "risk_profit_pct", "materials"]
NULL_MATERIAL = ["quantity", "waste_pct", "purchase_price", "price_basis"]
NULL_AUFTRAG = ["quantity", "unit", "unit_price", "short_text", "long_text", "position_type", "include_in_total"]
NULL_EINGANG = ["supplier_id", "invoice_date", "net_amount", "tax_rate_pct", "payment_status", "items"]


def test_null_in_pflichtfeldern_ist_422_und_aendert_nichts(angebot):
    db, client, qid, iid = angebot["db"], angebot["client"], angebot["quote_id"], angebot["item_id"]
    calc_id, mid = _kalkulation(db, iid)
    position, kalkulation, material = (_zeile(db, QuoteItem, iid), _zeile(db, QuoteItemCalculation, calc_id),
                                       _zeile(db, QuoteItemMaterialCalculation, mid))
    for feld in NULL_ANGEBOT:
        assert client.put(f"/api/quotes/{qid}/items/{iid}", json={feld: None, "long_text": "x"}
                          if feld != "long_text" else {feld: None}).status_code == 422, feld
    for feld in NULL_KALKULATION:
        assert client.put(f"/api/quotes/{qid}/items/{iid}/calculation", json={feld: None}).status_code == 422, feld
    for feld in NULL_MATERIAL:
        body = {"materials": [{"id": mid, feld: None}]}
        assert client.put(f"/api/quotes/{qid}/items/{iid}/calculation", json=body).status_code == 422, feld
    assert client.put(f"/api/quotes/{qid}/items/{iid}/layout", json={"include_in_total": None}).status_code == 422
    assert (_zeile(db, QuoteItem, iid), _zeile(db, QuoteItemCalculation, calc_id),
            _zeile(db, QuoteItemMaterialCalculation, mid)) == (position, kalkulation, material)


def test_null_in_pflichtfeldern_auftrag_und_eingangsrechnung(auftrag, router_test_client):
    db, client = auftrag["db"], auftrag["client"]
    url = f"/api/orders/{auftrag['order_id']}/items/{auftrag['item_id']}"
    vorher = _zeile(db, OrderItem, auftrag["item_id"])
    for feld in NULL_AUFTRAG:
        assert client.put(url, json={feld: None}).status_code == 422, feld
    assert _zeile(db, OrderItem, auftrag["item_id"]) == vorher
    invoice_id, _ = _eingangsrechnung(db)
    eingang = router_test_client(db, incoming_router)
    vorher = _zeile(db, IncomingInvoice, invoice_id)
    for feld in NULL_EINGANG:
        assert eingang.put(f"/api/incoming-invoices/{invoice_id}", json={feld: None}).status_code == 422, feld
    assert _zeile(db, IncomingInvoice, invoice_id) == vorher


def test_fremde_ids_bleiben_abgelehnt(angebot, router_test_client):
    db, client, qid, iid = angebot["db"], angebot["client"], angebot["quote_id"], angebot["item_id"]
    _, mid = _kalkulation(db, iid)
    fremd = make_quote(db, number="0399")
    fremde_position = fremd.items[0].id
    _, fremdes_material = _kalkulation(db, fremde_position)
    fremder_titel = QuoteSection(quote_id=fremd.id, title="Fremd", sort_order=10)
    db.add(fremder_titel)
    db.commit()
    vorher = (_zeile(db, QuoteItem, iid), _zeile(db, QuoteItem, fremde_position))
    assert client.put(f"/api/quotes/{qid}/items/{fremde_position}", json={"quantity": "3"}).status_code == 404
    assert client.put(f"/api/quotes/{qid}/items/{fremde_position}/calculation", json={"labor_rate": "1"}).status_code == 404
    assert client.put(f"/api/quotes/{qid}/items/{fremde_position}/layout", json={"section_id": None}).status_code == 422
    antwort = client.put(f"/api/quotes/{qid}/items/{iid}/layout", json={"section_id": fremder_titel.id})
    assert antwort.status_code == 422 and "gehört nicht zu diesem Angebot" in antwort.json()["detail"]
    antwort = client.put(f"/api/quotes/{qid}/items/{iid}/calculation",
                         json={"labor_rate": "1", "materials": [{"id": fremdes_material, "quantity": "9"}]})
    assert antwort.status_code == 422 and "gehört nicht zu dieser Angebotsposition" in antwort.json()["detail"]
    assert (_zeile(db, QuoteItem, iid), _zeile(db, QuoteItem, fremde_position)) == vorher
    assert db.get(QuoteItemCalculation, db.get(QuoteItemMaterialCalculation, mid).calculation_id).labor_rate == D("60")
    assert db.get(QuoteItemMaterialCalculation, fremdes_material).quantity == D("2")
    # Auftrag: Position eines anderen Auftrags
    orders = router_test_client(db, orders_router)
    fremde_auftragsposition = beauftragen(db, fremd).items[0].id
    eigener = beauftragen(db, make_quote(db, number="0398"))
    antwort = orders.put(f"/api/orders/{eigener.id}/items/{fremde_auftragsposition}", json={"quantity": "1"})
    assert antwort.status_code == 404
    assert _zeile(db, OrderItem, fremde_auftragsposition)["quantity"] == D("10")


def test_eingangsrechnung_unbekannte_zuordnung_ist_422(eingang):
    db, client, url = eingang["db"], eingang["client"], eingang["url"]
    vorher = _zeile(db, IncomingInvoice, eingang["id"])
    for body in ({"project_id": 999999}, {"recurring_cost_id": 999999}, {"supplier_id": 999999}, {"account_id": 999999}):
        assert client.put(url, json=body).status_code == 422, body
    assert _zeile(db, IncomingInvoice, eingang["id"]) == vorher


def test_kalkulation_aus_der_vorschau_bleibt_bei_ablehnung_weg(threaded_db_session, router_test_client):
    """Seit 1.8.96 legt das Speichern die Projektkalkulation ohne eigenen Commit an (die Sperre der Position bleibt bis zum
    Schluss). Lehnt es danach ab (Material einer anderen Position), bleibt auch die angelegte Kalkulation weg -- bis 1.8.95 stand
    sie schon."""
    from tests.test_v387_lesepfade_ohne_anlegen import _routers, _welt_mit_luecken
    db = threaded_db_session
    welt = _welt_mit_luecken(db)
    client = router_test_client(db, *_routers())
    pfad = "/api/quotes/{quote_id}/items/{item_id}/calculation".format(**welt)
    fremd = make_quote(db, number="0397")
    _, fremdes_material = _kalkulation(db, fremd.items[0].id)
    antwort = client.put(pfad, json={"labor_rate": "70", "materials": [{"id": fremdes_material, "quantity": "1"}]})
    assert antwort.status_code == 422
    db.rollback()  # wie get_db() am Ende der Anfrage: nicht Committetes ist weg (siehe _zeile())
    assert db.scalar(select(func.count()).select_from(QuoteItemCalculation)
                     .where(QuoteItemCalculation.quote_item_id == welt["item_id"])) == 0
    assert client.put(pfad, json={"labor_rate": "70"}).status_code == 200  # ohne Materialzeilen: angelegt, Material aus dem Katalog
    calc = db.scalar(select(QuoteItemCalculation).where(QuoteItemCalculation.quote_item_id == welt["item_id"]))
    assert calc.labor_rate == D("70") and len(calc.materials) > 0


# ---------------------------------------------------------------------------
# Gleichzeitig: PostgreSQL (opt-in)
# ---------------------------------------------------------------------------

def _pg_angebot(Session, order_id):
    return _vorbereiten(Session, lambda s: (lambda o: (o.source_quote_id, load_quote(s, o.source_quote_id).items[0].id))(
        s.get(Order, order_id)))


def test_postgresql_angebotsposition_zwei_felder_gleichzeitig(pg):
    """Menge hier, Einheit dort -- beide stehen, der Positionsbetrag passt."""
    Session, order_id = pg
    qid, iid = _pg_angebot(Session, order_id)
    _run(Session, lambda s: update_quote_item(qid, iid, QuoteItemUpdate(quantity=D("7")), db=s, _role=None),
         lambda s: update_quote_item(qid, iid, QuoteItemUpdate(unit="Stk"), db=s, _role=None))
    item = _vorbereiten(Session, lambda s: next(i for i in quote_to_dict(load_quote(s, qid))["items"] if i["id"] == iid))
    assert (item["quantity"], item["unit"], item["unit_price"], item["line_total"]) == (D("7"), "Stk", D("50"), D("350.00"))


def test_postgresql_kalkulation_zwei_felder_gleichzeitig_preis_passt(pg):
    """Stundensatz hier, sonstige Kosten dort. Der Einheitspreis wird aus der ganzen Kalkulation abgeleitet -- ohne die Sperre
    der Position rechnete die zweite mit dem Stundensatz von vor der ersten."""
    Session, order_id = pg
    qid, iid = _pg_angebot(Session, order_id)
    _vorbereiten(Session, lambda s: _kalkulation(s, iid))
    erste, zweite = _run(
        Session,
        lambda s: update_quote_item_calculation(qid, iid, QuoteItemCalculationUpdate(labor_rate=D("80")), db=s, _role=None),
        lambda s: update_quote_item_calculation(qid, iid, QuoteItemCalculationUpdate(other_cost=D("50")), db=s, _role=None))
    assert not isinstance(zweite, Exception), zweite

    def pruefen(s):
        item = s.scalar(select(QuoteItem).where(QuoteItem.id == iid))
        ergebnis = build_quote_item_calculation(item)
        return ergebnis["labor_rate"], ergebnis["other_cost"], ergebnis["effective_sale_price"], item.unit_price
    labor, other, effektiv, preis = _vorbereiten(Session, pruefen)
    assert (labor, other) == (D("80"), D("50.00"))
    assert preis == effektiv == zweite.effective_sale_price


def test_postgresql_kalkulation_speichern_und_position_loeschen_ohne_deadlock(pg, monkeypatch):
    """Seit 1.8.96 sperrt das Speichern der Kalkulation zuerst die Position, dann ändert es Kalkulation, Material und Preis. Das
    Löschen der Position löscht Material, Kalkulation, Position -- in umgekehrter Reihenfolge. Hier deterministisch: das
    Speichern hält nach der Sperre an, das Löschen startet. Seit delete_quote_item() die Position zuerst sperrt, wartet das
    Löschen und löscht danach; ohne diese Sperre warteten beide aufeinander (Deadlock)."""
    import threading
    import time

    import app.routers.quotes as quotes

    Session, order_id = pg
    qid, iid = _pg_angebot(Session, order_id)
    _vorbereiten(Session, lambda s: _kalkulation(s, iid))
    echt = quotes.ensure_quote_item_calculation
    gesperrt, weiter = threading.Event(), threading.Event()

    def angehalten(db, item):
        if threading.current_thread().name == "kalkulation":
            gesperrt.set()
            weiter.wait(timeout=30)
        return echt(db, item)
    monkeypatch.setattr(quotes, "ensure_quote_item_calculation", angehalten)
    ergebnis = {}

    def laufen(name, aktion):
        s = Session()
        try:
            ergebnis[name] = aktion(s)
        except Exception as exc:  # noqa: BLE001
            ergebnis[name] = exc
        finally:
            s.close()
    speichern = threading.Thread(name="kalkulation", target=laufen, args=("kalkulation", lambda s: update_quote_item_calculation(
        qid, iid, QuoteItemCalculationUpdate(labor_rate=D("80")), db=s, _role=None)))
    loeschen = threading.Thread(target=laufen, args=("loeschen", lambda s: quotes.delete_quote_item(qid, iid, db=s, _role=None)))
    speichern.start()
    assert gesperrt.wait(timeout=10)
    loeschen.start()
    time.sleep(1.5)  # länger als deadlock_timeout (1 s)
    weiter.set()
    speichern.join(timeout=30)
    loeschen.join(timeout=30)
    assert not isinstance(ergebnis["kalkulation"], Exception), ergebnis
    assert not isinstance(ergebnis["loeschen"], Exception), ergebnis
    assert iid not in [i.id for i in ergebnis["loeschen"].items]
    assert _vorbereiten(Session, lambda s: (s.get(QuoteItem, iid), s.scalar(
        select(func.count()).select_from(QuoteItemCalculation).where(QuoteItemCalculation.quote_item_id == iid)))) == (None, 0)


def test_postgresql_auftragsposition_zwei_felder_gleichzeitig(pg):
    Session, order_id = pg
    iid = _vorbereiten(Session, lambda s: s.scalar(select(OrderItem.id).where(OrderItem.order_id == order_id)))
    _run(Session, lambda s: put_order_item(order_id, iid, OrderItemUpdate(quantity=D("7")), db=s, _role=None),
         lambda s: put_order_item(order_id, iid, OrderItemUpdate(short_text="Eindecken neu"), db=s, _role=None))
    item, netto = _vorbereiten(Session, lambda s: (lambda o: ((o["items"][0]["quantity"], o["items"][0]["short_text"]),
                                                              o["net_total"]))(order_to_dict(load_order(s, order_id), s)))
    assert item == (D("7"), "Eindecken neu") and netto == D("350.00")


def _pg_eingangsrechnung(Session, order_id):
    def anlegen(s):
        invoice_id, _ = _eingangsrechnung(s)
        kosten = create_cost(s, {"label": "Miete", "net_amount": "100.00", "billing_interval": "monatlich"})
        return invoice_id, s.get(Order, order_id).project_id, kosten["id"]
    return _vorbereiten(Session, anlegen)


def test_postgresql_eingangsrechnung_zwei_zuordnungen_gleichzeitig(pg):
    """Projekt hier, Kostenposten dort: jede für sich gültig, zusammen zwei Zuordnungen. Unter der Sperre der Zeile prüft die
    zweite auf dem Stand nach der ersten und lehnt ab."""
    Session, order_id = pg
    invoice_id, project_id, cost_id = _pg_eingangsrechnung(Session, order_id)
    _, zweite = _run(Session,
                     lambda s: put_incoming_invoice(invoice_id, IncomingInvoiceUpdate(project_id=project_id), db=s, _role=None),
                     lambda s: put_incoming_invoice(invoice_id, IncomingInvoiceUpdate(recurring_cost_id=cost_id), db=s,
                                                    _role=None))
    assert isinstance(zweite, HTTPException) and zweite.status_code == 422, zweite
    gespeichert = _vorbereiten(Session, lambda s: (s.get(IncomingInvoice, invoice_id).project_id,
                                                   s.get(IncomingInvoice, invoice_id).recurring_cost_id))
    assert gespeichert == (project_id, None)


def test_postgresql_eingangsrechnung_speichern_und_loeschen_ohne_deadlock(pg, monkeypatch):
    """Speichern mit Positionen sperrt seit 1.8.96 zuerst die Rechnung, dann ersetzt es die Positionen; Löschen löscht Positionen,
    dann Rechnung. Hier deterministisch: das Speichern hält nach der Sperre an, das Löschen startet. Seit delete_invoice() die
    Rechnung zuerst sperrt, wartet das Löschen; ohne diese Sperre warteten beide aufeinander (Deadlock)."""
    import threading
    import time

    import app.incoming_invoices as eingang
    from app.routers.incoming_invoices import delete_incoming_invoice

    Session, order_id = pg
    invoice_id, _, _ = _pg_eingangsrechnung(Session, order_id)
    echt = eingang._validate_items_payload
    gesperrt, weiter = threading.Event(), threading.Event()

    def angehalten(db, items):
        if threading.current_thread().name == "speichern":
            gesperrt.set()
            weiter.wait(timeout=30)
        return echt(db, items)
    monkeypatch.setattr(eingang, "_validate_items_payload", angehalten)
    ergebnis = {}

    def laufen(name, aktion):
        s = Session()
        try:
            ergebnis[name] = aktion(s)
        except Exception as exc:  # noqa: BLE001
            ergebnis[name] = exc
        finally:
            s.close()
    neu = IncomingInvoiceUpdate(net_amount=D("600.00"), items=[{"description": "Bahnen", "net_amount": D("600.00")}])
    speichern = threading.Thread(name="speichern", target=laufen,
                                 args=("speichern", lambda s: put_incoming_invoice(invoice_id, neu, db=s, _role=None)))
    loeschen = threading.Thread(target=laufen, args=("loeschen", lambda s: delete_incoming_invoice(invoice_id, db=s, _role=None)))
    speichern.start()
    assert gesperrt.wait(timeout=10)
    loeschen.start()
    time.sleep(1.5)  # länger als deadlock_timeout (1 s)
    weiter.set()
    speichern.join(timeout=30)
    loeschen.join(timeout=30)
    assert not isinstance(ergebnis["speichern"], Exception), ergebnis
    assert ergebnis["loeschen"] == {"deleted": True}, ergebnis
    assert _vorbereiten(Session, lambda s: (s.get(IncomingInvoice, invoice_id),
                                            s.scalar(select(func.count()).select_from(IncomingInvoiceItem)))) == (None, 0)


def test_postgresql_eingangsrechnung_notiz_und_bezahlt_gleichzeitig(pg):
    Session, order_id = pg
    invoice_id, _, _ = _pg_eingangsrechnung(Session, order_id)
    _run(Session,
         lambda s: put_incoming_invoice(invoice_id, IncomingInvoiceUpdate(notes="Skonto geprüft"), db=s, _role=None),
         lambda s: put_incoming_invoice(invoice_id, IncomingInvoiceUpdate(payment_status="bezahlt",
                                                                          payment_date=date(2026, 10, 13)), db=s, _role=None))
    gespeichert = _vorbereiten(Session, lambda s: (lambda i: (i.notes, i.payment_status, i.payment_date, len(i.items)))(
        s.get(IncomingInvoice, invoice_id)))
    assert gespeichert == ("Skonto geprüft", "bezahlt", date(2026, 10, 13), 1)
    assert _vorbereiten(Session, lambda s: s.scalar(select(func.count()).select_from(IncomingInvoiceItem))) == 1
