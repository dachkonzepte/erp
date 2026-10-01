"""Version 1.8.31 -- Restfälle des Auswahl-Musters aus 1.8.30 (docs/archiv/teil-updates.md).

1. Backoffice-Korrektur: eine Buchung auf einem abgeschlossenen Auftrag behält ihn (bis 1.8.30 wählte der Dialog
   still den ersten offenen Auftrag des Projekts, Speichern buchte um).
2. Die Zeitbuchung einer inaktiven Person bleibt änderbar, solange die Person nicht wechselt.
3. Archivierter Steuerschlüssel in Angebot, Auftrag und Rechnung, inaktive Schichttypen an der Dachfläche: sichtbar.
4. Angebots-Editor (Texte, Einheit) und Kunden-Kategorie wählen bei leerem Wert nicht still die Vorgabe vor.
5. GET /api/tasks/{id}/finding prüft auch das Modul Aufgabenmanagement.

Die Oberflächen-Tests führen das echte Seitenskript in node aus, mit einer kleinen Attrappe für DOM und fetch
(FAKE_DOM): eine Auswahl wählt wie der Browser die letzte Option mit selected, sonst die erste, und ein value ohne
passende Option leert sie. Die Antworten auf fetch kommen vom echten Server (router_test_client)."""

import json
import re
from datetime import date
from decimal import Decimal

import pytest

from app.models import (
    Employee, EnabledModule, Order, OrderItem, Property, Quote, QuoteItem, RoofArea, RoofLayer, RoofLayerType, TaxKey,
    TimeEntry,
)
from tests.test_v133_invoices import make_order_with_item
from tests.test_v314_dashboard_month_berlin import NODE, TEMPLATES, _node
from tests.test_v329_teil_updates import payload, ui_keys

nur_mit_node = pytest.mark.skipif(NODE is None, reason="node nicht installiert")

FAKE_DOM = r"""
var ANTWORTEN = {}, AUFRUFE = [];
const _entitaeten = s => String(s).replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&amp;/g, '&');
function _optionen(html) {
  return [...String(html).matchAll(/<option\b([^>]*)>([\s\S]*?)<\/option>/g)].map(m => {
    const wert = /\bvalue="([^"]*)"/.exec(m[1]), text = _entitaeten(m[2].replace(/<[^>]*>/g, ''));
    return {value: wert ? _entitaeten(wert[1]) : text, selected: /\sselected\b/.test(m[1]), text};
  });
}
const _elemente = {};
function _element(id) {
  if (_elemente[id]) return _elemente[id];
  const z = {html: '', optionen: null, index: -1, wert: ''};
  const ziel = {id, style: {}, dataset: {}, classList: {add() {}, remove() {}, toggle() {}, contains() { return false; }},
    showModal() {}, close() {}, focus() {}, addEventListener() {}, setAttribute() {}, removeAttribute() {},
    querySelectorAll: () => [], querySelector: () => null};
  return _elemente[id] = new Proxy(ziel, {
    get(t, k) {
      if (k === 'innerHTML') return z.html;
      if (k === 'value') return z.optionen ? (z.index >= 0 ? z.optionen[z.index].value : '') : z.wert;
      if (k === 'options') return z.optionen || [];
      if (k === 'selectedIndex') return z.index;
      return t[k];
    },
    set(t, k, v) {
      if (k === 'innerHTML') {
        z.html = String(v);
        if (z.optionen || z.html.includes('<option')) {
          z.optionen = _optionen(z.html);
          const s = z.optionen.map(o => o.selected).lastIndexOf(true);
          z.index = s >= 0 ? s : (z.optionen.length ? 0 : -1);
        }
        return true;
      }
      if (k === 'value') {
        if (z.optionen) z.index = z.optionen.findIndex(o => o.value === String(v ?? ''));
        else z.wert = String(v ?? '');
        return true;
      }
      t[k] = v;
      return true;
    },
  });
}
function _gewaehlt(id) { const e = _element(id); return e.selectedIndex >= 0 ? e.options[e.selectedIndex] : null; }
var document = {getElementById: _element, querySelector: () => _element('__query'), querySelectorAll: () => [],
  documentElement: _element('__html'), body: _element('__body'), addEventListener() {}};
var window = globalThis;
window.matchMedia = () => ({matches: false, addEventListener() {}});
var location = {hash: '', href: '', search: '', pathname: '/'};
var localStorage = {getItem: () => null, setItem() {}, removeItem() {}};
var confirm = () => true, alert = () => {};
globalThis.fetch = async (url, opt = {}) => {
  const methode = opt.method || 'GET';
  AUFRUFE.push({url, methode, body: opt.body ? JSON.parse(opt.body) : null});
  const antwort = methode === 'GET' ? ANTWORTEN[url] : {};
  const kopf = {get: () => 'application/json'};
  if (antwort === undefined) return {ok: false, status: 404, statusText: 'Not Found', headers: kopf, json: async () => ({detail: 'unbekannt: ' + url})};
  return {ok: true, status: 200, statusText: 'OK', headers: kopf, json: async () => antwort, text: async () => JSON.stringify(antwort)};
};
"""


def seite(vorlage: str, start: str) -> str:
    """Attrappe + _auswahl.html + das Seitenskript bis vor den Start-Aufruf (load()/init(), der fetch und DOM braucht).
    Jinja-Ausdrücke im Skript werden zu 1."""
    hilfe = re.findall(r"<script>(.*?)</script>", (TEMPLATES / "_auswahl.html").read_text(encoding="utf-8"), flags=re.S)
    haupt = re.findall(r"<script>(.*?)</script>", (TEMPLATES / vorlage).read_text(encoding="utf-8"), flags=re.S)[-1]
    assert start in haupt, f"{vorlage}: {start!r} nicht gefunden -- Test anpassen"
    haupt = re.sub(r"\{\{.*?\}\}", "1", haupt.rsplit(start, 1)[0])
    return FAKE_DOM + "\n".join(hilfe) + "\n" + haupt


def im_browser(skript: str, ablauf: str, antworten: dict | None = None):
    """Führt `ablauf` (Rumpf einer async-Funktion, gibt ein Ergebnis zurück) nach dem Seitenskript aus."""
    js = (skript + f"\nANTWORTEN = {json.dumps(antworten or {}, default=str)};\n"
          f"(async () => {{ const ergebnis = await (async () => {{ {ablauf} }})();\n"
          "process.stdout.write(JSON.stringify({ergebnis, aufrufe: AUFRUFE})); })()"
          ".catch(e => { console.error(e && e.stack || e); process.exit(1); });")
    return _node(js, "Europe/Berlin")


def _mitarbeiter(db, nummer, vorname, aktiv=True):
    person = Employee(employee_number=nummer, first_name=vorname, last_name="Test", employee_group="gewerblich",
                      weekly_hours=Decimal("40"), active=aktiv)
    db.add(person)
    db.flush()
    return person


def _buchung(db, person, order, item, stunden="4"):
    entry = TimeEntry(employee_id=person.id, project_id=order.project_id, order_id=order.id,
                      order_item_id=item.id if item else None, work_date=date(2026, 9, 15), entry_type="site",
                      hours=Decimal(stunden), break_minutes=30, source="manual", status="booked")
    db.add(entry)
    db.flush()
    return entry


# ---------------------------------------------------------------------------
# 1. Backoffice-Korrektur: Buchung auf einem abgeschlossenen Auftrag
# ---------------------------------------------------------------------------

@nur_mit_node
def test_backoffice_korrektur_behaelt_den_abgeschlossenen_auftrag(threaded_db_session, router_test_client):
    from app.routers.orders import router as orders_router
    from app.routers.time_tracking import router as time_router

    db = threaded_db_session
    offen, _ = make_order_with_item(db)                       # derselbe Projekt: der "erste offene"
    erledigt = Order(order_number="AUF-TEST-0002", project_id=offen.project_id, source_quote_id=2,
                     quote_number_snapshot="A-TEST-0002", title="Reparatur Gaube", vat_rate=Decimal("19"),
                     customer_name="Test Kunde", customer_number="K-0001", status="abgeschlossen")
    db.add(erledigt)
    db.flush()
    gaube = OrderItem(order_id=erledigt.id, sort_order=10, position_number="1", short_text="Gaube abdichten",
                      quantity=Decimal("1"), unit="psch", unit_price=Decimal("0"))
    db.add(gaube)
    db.flush()
    entry = _buchung(db, _mitarbeiter(db, "Z-1", "Anna"), erledigt, gaube)
    db.commit()

    client = router_test_client(db, time_router, orders_router)
    kontext = client.get("/api/time-tracking/context").json()
    assert [o["id"] for o in kontext["orders"]] == [offen.id]  # der Kontext liefert nur offene Aufträge
    buchungen = client.get(f"/api/time-entries?employee_id={entry.employee_id}").json()
    antworten = {f"/api/orders/{erledigt.id}": client.get(f"/api/orders/{erledigt.id}").json()}

    ablauf = f"""
      timeContext = {json.dumps(kontext)}; entries = {json.dumps(buchungen)}; groups = []; reloadAll = async () => {{}};
      await openEdit({entry.id});
      const auswahl = {{auftrag: _gewaehlt('editOrder'), position: _gewaehlt('editOrderItem'),
                        auftraege: _element('editOrder').options.map(o => o.value)}};
      await saveEntryEdit();
      return auswahl;"""
    lauf = im_browser(seite("time_backoffice.html", "init().catch("), ablauf, antworten)
    auswahl = lauf["ergebnis"]
    assert auswahl["auftrag"] == {"value": str(erledigt.id), "selected": True,
                                  "text": "AUF-TEST-0002 · Reparatur Gaube (abgeschlossen)"}
    assert sorted(auswahl["auftraege"]) == sorted([str(offen.id), str(erledigt.id)])
    assert auswahl["position"]["value"] == str(gaube.id)

    gesendet = next(a["body"] for a in lauf["aufrufe"] if a["methode"] == "PUT")
    assert (gesendet["order_id"], gesendet["order_item_id"]) == (erledigt.id, gaube.id)
    assert client.put(f"/api/time-entries/{entry.id}", json={**gesendet, "hours": 5}).status_code == 200
    db.expire_all()
    gespeichert = db.get(TimeEntry, entry.id)
    assert (gespeichert.order_id, gespeichert.order_item_id, gespeichert.hours) == (erledigt.id, gaube.id, Decimal("5"))


# ---------------------------------------------------------------------------
# 2. Zeitbuchung einer inaktiven Person
# ---------------------------------------------------------------------------

def test_buchung_einer_inaktiven_person_bleibt_aenderbar(threaded_db_session, router_test_client):
    from app.routers.time_tracking import router as time_router

    db = threaded_db_session
    order, item = make_order_with_item(db)
    bernd = _mitarbeiter(db, "Z-2", "Bernd")
    andere_inaktiv = _mitarbeiter(db, "Z-3", "Clara", aktiv=False)
    aktiv = _mitarbeiter(db, "Z-4", "Dora")
    entry = _buchung(db, bernd, order, item)
    bernd.active = False                                       # nach der Buchung ausgeschieden
    db.commit()
    client = router_test_client(db, time_router)
    url = f"/api/time-entries/{entry.id}"

    keys = ui_keys("time_backoffice.html", "saveEntryEdit", "body:JSON.stringify(")
    assert "employee_id" not in keys
    werte = {"order_id": order.id, "order_item_id": item.id, "work_date": "2026-09-15", "entry_type": "site",
             "activity": None, "hours": 6, "notes": "korrigiert"}
    antwort = client.put(url, json=payload(keys, werte))
    assert antwort.status_code == 200, antwort.text
    assert client.put(url, json={"employee_id": bernd.id, "hours": 7}).status_code == 200   # dieselbe Person, ausdrücklich
    db.expire_all()
    gespeichert = db.get(TimeEntry, entry.id)
    assert (gespeichert.employee_id, gespeichert.hours, gespeichert.notes) == (bernd.id, Decimal("7"), "korrigiert")

    # Wechseln geht nur zu einer aktiven Person
    antwort = client.put(url, json={"employee_id": andere_inaktiv.id})
    assert antwort.status_code == 422 and "inaktiv" in antwort.text
    assert client.put(url, json={"employee_id": aktiv.id}).status_code == 200


# ---------------------------------------------------------------------------
# 3. Archivierter Steuerschlüssel, inaktive Schichttypen
# ---------------------------------------------------------------------------

STEUER_SEITEN = [("quote_editor.html", "quote", "load().catch("), ("order.html", "order", "load().catch("),
                 ("invoice_detail.html", "invoice", "load().catch(")]


@nur_mit_node
@pytest.mark.parametrize("vorlage,variable,start", STEUER_SEITEN)
def test_archivierter_steuerschluessel_bleibt_sichtbar_und_vorgewaehlt(threaded_db_session, router_test_client,
                                                                        vorlage, variable, start):
    from app.routers.tax_keys import router as tax_router
    from app.tax_keys import ensure_default_tax_keys

    db = threaded_db_session
    ensure_default_tax_keys(db)
    alt = TaxKey(label="Alt 16", vat_rate=Decimal("16.00"), archived=False, is_default=False)
    auch_alt = TaxKey(label="Auch archiviert", vat_rate=Decimal("5.00"), archived=True, is_default=False)
    db.add_all([alt, auch_alt])
    db.commit()
    alt.archived = True                                        # nach der Zuordnung archiviert
    db.commit()

    html = (TEMPLATES / vorlage).read_text(encoding="utf-8")
    urls = re.findall(r"api\('(/api/tax-keys[^']*)'\)", html)
    assert len(urls) == 1, urls
    steuerschluessel = router_test_client(db, tax_router).get(urls[0]).json()   # was die Seite beim Laden bekommt

    ablauf = f"""
      taxKeys = {json.dumps(steuerschluessel)}; {variable} = {{tax_key_id: {alt.id}}};
      renderTaxKeySelect();
      const id = {json.dumps({"quote": "hTaxKey", "order": "taxKey", "invoice": "iTaxKeySelect"}[variable])};
      return {{gewaehlt: _gewaehlt(id), werte: _element(id).options.map(o => o.value)}};"""
    ergebnis = im_browser(seite(vorlage, start), ablauf)["ergebnis"]
    assert ergebnis["gewaehlt"]["value"] == str(alt.id)
    assert ergebnis["gewaehlt"]["text"].startswith("Alt 16 (16,") and ergebnis["gewaehlt"]["text"].endswith(" %) (inaktiv)")
    assert str(auch_alt.id) not in ergebnis["werte"]          # neu angeboten nur aktive
    assert len(ergebnis["werte"]) == db.query(TaxKey).filter_by(archived=False).count() + 1


@nur_mit_node
def test_dachflaeche_zeigt_schicht_eines_inaktiven_schichttyps(threaded_db_session, router_test_client):
    from app.main import create_customer
    from app.routers.roof_areas import router as roof_router
    from app.schemas import CustomerCreate

    db = threaded_db_session
    kunde = create_customer(CustomerCreate(last_name="Dachkunde"), db)
    objekt = Property(customer_id=kunde.id, name="Halle", street="Weg 1", postal_code="12345", city="Ort")
    db.add(objekt)
    db.flush()
    flaeche = RoofArea(property_id=objekt.id, name="Hauptdach", roof_type="flachdach_test")
    aktiv = RoofLayerType(key="t_abdichtung", label="Abdichtung", roof_type="flachdach_test", option_group=None, sort_order=10)
    frueher = RoofLayerType(key="t_kies", label="Kiesschüttung", roof_type="flachdach_test", option_group=None, sort_order=20)
    ungenutzt = RoofLayerType(key="t_alt", label="Altschicht", roof_type="flachdach_test", option_group=None,
                              sort_order=30, active=False)
    db.add_all([flaeche, aktiv, frueher, ungenutzt])
    db.flush()
    db.add(RoofLayer(roof_area_id=flaeche.id, layer_type_id=frueher.id, present=True, notes="16/32"))
    db.commit()
    frueher.active = False                                     # Schichttyp nach der Erfassung abgeschaltet
    db.commit()

    client = router_test_client(db, roof_router)
    antworten = {f"/api/roof-layer-types?roof_type=flachdach_test{z}": client.get(f"/api/roof-layer-types?roof_type=flachdach_test{z}").json()
                 for z in ("", "&include_inactive=true")}
    antworten["/api/roof-areas/1/layers"] = client.get(f"/api/roof-areas/{flaeche.id}/layers").json()   # roofAreaId ist im Skript 1

    ablauf = """
      _element('editRoofType').value = 'flachdach_test';
      await loadLayers();
      return {zeilen: _element('layerRows').innerHTML, fremd: _element('layerMismatchRows').innerHTML};"""
    ergebnis = im_browser(seite("roof_area.html", "init();"), ablauf, antworten)["ergebnis"]
    assert "Abdichtung" in ergebnis["zeilen"]
    assert 'Kiesschüttung <span class="muted">(inaktiv)</span>' in ergebnis["zeilen"] and 'value="16/32"' in ergebnis["zeilen"]
    assert "Kiesschüttung" not in ergebnis["fremd"]           # bis 1.8.30: "Passt nicht zum aktuellen Dachtyp"
    assert "Altschicht" not in ergebnis["zeilen"] + ergebnis["fremd"]   # inaktiv ohne Schicht: nicht angeboten


# ---------------------------------------------------------------------------
# 4. Leerer Wert an einem bestehenden Datensatz: keine still vorgewählte Vorgabe
# ---------------------------------------------------------------------------

def _angebote(db, client):
    """Ein neues Angebot (Server setzt die Vorgaben) und ein bestehendes mit leeren Texten, leerer Zahlungsbedingung
    und einer Position ohne Einheit. Die Zahlungsbedingungen hängt der Editor beim Laden als Auswahlliste
    "quote_payment_terms" an (load()), hier ebenso."""
    from app.main import create_customer, create_project
    from app.models import QuoteDocumentMeta
    from app.payment_terms import ensure_default_payment_terms
    from app.schemas import CustomerCreate, ProjectCreate

    ensure_default_payment_terms(db)
    gruppen = client.get("/api/settings/option-groups").json()  # legt die Standard-Auswahllisten an
    bedingungen = client.get("/api/payment-terms").json()
    gruppen = [g for g in gruppen if g["group_key"] != "quote_payment_terms"] + [{
        "group_key": "quote_payment_terms", "label": "Zahlungsbedingungen",
        "options": [{"id": b["id"], "label": f"{b['label']} ({b['days']} Tage)", "value": b["label"], "active": not b["archived"],
                     "is_default": b["is_default"], "sort_order": i * 10} for i, b in enumerate(bedingungen)]}]
    projekt = create_project(ProjectCreate(customer_id=create_customer(CustomerCreate(last_name="K"), db).id, name="P"), db)
    neu = client.post(f"/api/projects/{projekt.id}/quotes", json={"title": "Neu"}).json()
    alt = client.post(f"/api/projects/{projekt.id}/quotes", json={"title": "Bestand"}).json()
    bestand = db.get(Quote, alt["id"])
    bestand.intro_text = bestand.outro_text = None
    db.query(QuoteDocumentMeta).filter_by(quote_id=bestand.id).one().payment_terms = None
    db.add(QuoteItem(quote_id=bestand.id, sort_order=10, position_number="1", short_text="Altposition", long_text="",
                     quantity=Decimal("1"), unit="", unit_price=Decimal("0")))
    db.commit()
    return gruppen, neu, client.get(f"/api/quotes/{alt['id']}").json()


def _quote_router_client(db, router_test_client):
    from app.routers.projects import router as projects_router
    from app.routers.quotes import router as quotes_router
    from app.routers.settings import router as settings_router
    from app.routers.payment_terms import router as payment_terms_router
    return router_test_client(db, projects_router, quotes_router, settings_router, payment_terms_router)


@nur_mit_node
def test_angebots_editor_texte_ohne_still_vorgewaehlte_vorgabe(threaded_db_session, router_test_client):
    db = threaded_db_session
    gruppen, neu, bestand = _angebote(db, _quote_router_client(db, router_test_client))
    vorgabe = {g["group_key"]: next(o["value"] for o in g["options"] if o["is_default"])
               for g in gruppen if g["group_key"] in ("quote_intro_texts", "quote_outro_texts")}
    assert (neu["intro_text"], neu["outro_text"], neu["outro_text_2"]) == (
        vorgabe["quote_intro_texts"], vorgabe["quote_outro_texts"], None)   # Vorgabe beim Anlegen, vom Server
    assert neu["document_meta"]["payment_terms"]                            # ebenso die Standard-Zahlungsbedingung

    # Die fillTextSelect()-Aufrufe genau so, wie renderAll() sie macht
    html = (TEMPLATES / "quote_editor.html").read_text(encoding="utf-8")
    aufrufe = re.findall(r"fillTextSelect\('\w+','\w+',[^)]*\)", html)
    assert len(aufrufe) == 4, aufrufe

    def felder(angebot):
        ablauf = (f"optionGroups = {json.dumps(gruppen)}; quote = {json.dumps(angebot)}; const m = quote.document_meta || {{}};\n"
                  + ";".join(aufrufe) + ";\nreturn Object.fromEntries(['hIntro','hPayment','hOutro','hOutro2'].map(id => [id, _element(id).value]));")
        return im_browser(seite("quote_editor.html", "load().catch("), ablauf)["ergebnis"]

    assert felder(neu) == {"hIntro": vorgabe["quote_intro_texts"], "hPayment": neu["document_meta"]["payment_terms"],
                           "hOutro": vorgabe["quote_outro_texts"], "hOutro2": ""}
    assert felder(bestand) == {"hIntro": "", "hPayment": "", "hOutro": "", "hOutro2": ""}


@nur_mit_node
def test_angebots_editor_einheit_ohne_still_vorgewaehlte_vorgabe(threaded_db_session, router_test_client):
    db = threaded_db_session
    gruppen, _neu, bestand = _angebote(db, _quote_router_client(db, router_test_client))
    vorgabe = "m²"                # nicht "Stück": sonst unterschiede der Test die Vorgabe nicht vom alten festen Rückfall
    for gruppe in gruppen:
        if gruppe["group_key"] == "units":
            for option in gruppe["options"]:
                option["is_default"] = option["value"] == vorgabe

    ablauf = f"""
      optionGroups = {json.dumps(gruppen)}; quote = {json.dumps(bestand)}; showEditMode = () => {{}};
      currentItem = quote.items[0]; fillItemEditor();
      const bestand = _gewaehlt('iUnit');
      await saveItem();
      const meldung = _element('itemStatus').textContent;
      openFreeItem();
      return {{bestand, meldung, neu: _element('iUnit').value}};"""
    lauf = im_browser(seite("quote_editor.html", "load().catch("), ablauf)
    ergebnis = lauf["ergebnis"]
    assert ergebnis["bestand"] == {"value": "", "selected": True, "text": "— keine Einheit —"}
    assert ergebnis["meldung"] == "Fehler: Bitte eine Einheit wählen."
    assert not [a for a in lauf["aufrufe"] if a["methode"] != "GET"]   # nichts gespeichert
    assert ergebnis["neu"] == vorgabe                                  # neue Position: Vorgabe aus den Einstellungen


@nur_mit_node
def test_kunden_kategorie_ohne_still_vorgewaehlte_vorgabe(threaded_db_session, router_test_client):
    """Ein leerer Wert erreicht die Seite heute nicht: der Server setzt "Privatkunde" (app/crm.py), lehnt "" ab, und ein
    direkt in der Datenbank geleerter Wert lässt GET /api/customers/{id} scheitern (CustomerOut, min_length=1). Die
    Seite wählt trotzdem nicht mehr selbst eine Vorgabe vor (bis 1.8.30: customer.category||'Privatkunde', dann die
    Standard-Kategorie) -- geprüft mit einem leeren Wert in der Antwort. Ein abgeschalteter gespeicherter Wert bleibt
    vorgewählt und heißt jetzt "(inaktiv)" wie überall (bis 1.8.30 "· bisher")."""
    from app.main import create_customer
    from app.routers.customers import router as customers_router
    from app.routers.settings import router as settings_router
    from app.schemas import CustomerCreate

    db = threaded_db_session
    client = router_test_client(db, customers_router, settings_router)
    gruppe = client.get("/api/settings/option-groups/customer_categories").json()
    gewerbe = next(o for o in gruppe["options"] if o["value"] == "Gewerbekunde")
    felder = {k: gewerbe[k] for k in ("label", "value", "sort_order", "is_default")}
    assert client.put(f"/api/settings/option-groups/customer_categories/options/{gewerbe['id']}",
                      json={**felder, "active": False}).status_code == 200
    gruppe = client.get("/api/settings/option-groups/customer_categories").json()
    kunde = create_customer(CustomerCreate(last_name="Alt", category="Gewerbekunde"), db)
    gespeichert = client.get(f"/api/customers/{kunde.id}").json()
    assert client.put(f"/api/customers/{kunde.id}", json={"last_name": "Alt", "category": ""}).status_code == 422

    # Der Aufruf so, wie die Seite ihn beim Laden macht
    html = (TEMPLATES / "customer.html").read_text(encoding="utf-8")
    aufruf = re.search(r"renderCategorySelect\(customer[^;]*\);", html).group(0)

    def seite_laden(kunde_json):
        ablauf = (f"customerCategoryGroup = {json.dumps(gruppe)}; customer = {json.dumps(kunde_json)};"
                  f"{aufruf} const auswahl = _gewaehlt('category'); await saveCustomer();"
                  "return {auswahl, meldung: _element('customerStatus').textContent};")
        return im_browser(seite("customer.html", "load().catch("), ablauf)

    assert seite_laden(gespeichert)["ergebnis"]["auswahl"] == {"value": "Gewerbekunde", "selected": True,
                                                               "text": "Gewerbekunde (inaktiv)"}
    lauf = seite_laden({**gespeichert, "category": ""})
    assert lauf["ergebnis"]["auswahl"] == {"value": "", "selected": True, "text": "— keine Kategorie —"}
    assert lauf["ergebnis"]["meldung"] == "Fehler: Bitte eine Kundenkategorie wählen."
    assert not [a for a in lauf["aufrufe"] if a["methode"] == "PUT"]


# ---------------------------------------------------------------------------
# 5. Mangel zur Aufgabe: Modul Aufgabenmanagement
# ---------------------------------------------------------------------------

def test_mangel_zur_aufgabe_prueft_das_modul_aufgabenmanagement(threaded_db_session, router_test_client):
    from app.findings import create_finding
    from app.routers.findings import router as findings_router
    from app.service_reports import create_report
    from tests.test_v214_findings_and_photos import _build_extra_order

    db = threaded_db_session
    order, _kunde, _projekt = _build_extra_order(db, "9334", source_quote_id=9334)
    mangel = create_finding(db, create_report(db, order.id, "rapport")["id"], "Kehle undicht", "dringend", "buero_pruefen")
    db.commit()
    client = router_test_client(db, findings_router)
    url = f"/api/tasks/{mangel['follow_up_task_id']}/finding"

    antwort = client.get(url)
    assert antwort.status_code == 200 and antwort.json()["id"] == mangel["id"]
    db.add(EnabledModule(module_key="aufgabenmanagement", enabled=False))
    db.commit()
    antwort = client.get(url)
    assert antwort.status_code == 403 and "Aufgabenmanagement" in antwort.text and "Kehle" not in antwort.text
