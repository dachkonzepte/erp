"""Version 1.9.137 (Stufe 5, R3, Punkte 2, 3 und 5) -- /customers/{id} ist die Kundenakte nach den Vorlagen kunde-*.html.

Das Skript der Seite läuft in node mit den Antworten der echten Endpunkte (router_test_client, Welt aus tests/test_v555_kundenakte_zahlen.py):
der Anker #zahlungen öffnet den Reiter Zahlungen; die Zahlen kommen vom Server und stehen so auf der Seite; Büro – Auftrag sieht Zahlungen und
Vorschläge ohne Knöpfe, der Server lehnt das Zuordnen ab (403), Büro – Finanzen ordnet den Rest zu (danach 0); der Dialog „Stammdaten bearbeiten“
behält Eingaben beim Neuzeichnen und schickt nur Geändertes. Dazu die Bausteine: Trennlinien im Menü (_menue.html), Untertitel mit Links
(_seitenkopf.html), die Spalte „Projekt“ der Rechnungsliste, das „⋮“ der Akte in drei Gruppen, die Zeilen der unbezahlten Rechnungen vom Server.
"""

import json
import re

import pytest

from app.models import Invoice
from app.routers import customers as customers_router
from app.routers import inquiries as inquiries_router
from app.routers import payment_terms as payment_terms_router
from app.routers import payments as payments_router
from app.routers import properties as properties_router
from app.routers import roof_areas as roof_areas_router
from app.routers import settings as settings_router
from app.routers.pages import router as pages_router
from tests.node_lauf import node_ausfuehren
from tests.test_v334_auswahl_restfaelle import im_browser, nur_mit_node, seite
from tests.test_v555_kundenakte_zahlen import welt  # noqa: F401  (Fixture)
from tests.test_v314_dashboard_month_berlin import TEMPLATES

ROUTER = (customers_router.router, inquiries_router.router, payment_terms_router.router, payments_router.router, properties_router.router,
          roof_areas_router.router, settings_router.router)
# Bausteine der Seite, die die Attrappe aus test_v334 nicht kennt
WEITERE = ("_zahlung_gruppen.html", "_rechnungsliste.html", "_email_dispatch.html")
ZUSATZ = """
var history = {replaceState(a, b, u) { location.hash = u.slice(u.indexOf('#')); }};
document.createTextNode = t => ({textContent: String(t)});
"""


def _antworten(client, kid):
    urls = [f"/api/customers/{kid}", f"/api/properties?customer_id={kid}", f"/api/inquiries?customer_id={kid}",
            "/api/settings/option-groups/customer_categories", "/api/settings/option-groups/customer_salutations",
            "/api/payment-terms?include_archived=true", "/api/settings/option-groups/project_document_categories",
            f"/api/customers/{kid}/akte", f"/api/customers/{kid}/documents", f"/api/customers/{kid}/payments",
            f"/api/customers/{kid}/open-invoices", f"/api/customers/{kid}/verlauf", f"/api/customers/{kid}/verlauf?art=versand"]
    out = {}
    for u in urls:
        r = client.get(u)
        assert r.status_code == 200, (u, r.text[:300])
        out[u] = r.json()
    for p in out[f"/api/properties?customer_id={kid}"]:
        out[f"/api/roof-areas?property_id={p['id']}"] = client.get(f"/api/roof-areas?property_id={p['id']}").json()
    return out


def _skript(kid, *, geld=True, anker=""):
    s = seite("customer.html", "kundenakteStarten().catch(")
    weitere = "\n".join(t for n in WEITERE for t in re.findall(r"<script>(.*?)</script>", (TEMPLATES / n).read_text(encoding="utf-8"), flags=re.S))
    i = s.index("const customerId=1;")
    s = s[:i] + ZUSATZ + weitere + "\n" + s[i:]
    s = s.replace("const customerId=1;", f"const customerId={int(kid)};", 1)
    if not geld:
        s = s.replace('const GELD="1"!=="nein";', "const GELD=false;", 1)
    return s + f"\nlocation.hash = {json.dumps(anker)};\n"


def _lauf(welt, ablauf, *, rolle="buero_finanzen", kunde="kessler", anker=""):
    db, kid = welt["db"], welt[kunde].id
    antworten = _antworten(welt["client"](db, *ROUTER, role=rolle), kid)
    return {**im_browser(_skript(kid, geld=rolle != "buero_auftrag", anker=anker), ablauf, antworten), "antworten": antworten}


@pytest.fixture
def akte_welt(welt, router_test_client):
    return {**welt, "client": router_test_client}


ZEICHNEN = ("await kundenakteStarten(); return {sichtbar: REITER.filter(r => _element('reiter-' + r).hidden === false),"
            "anker: location.hash, art: verlaufArt, unbezahlt: _element('zUnbezahlt').innerHTML, zahlungen: _element('customerPayments').innerHTML,"
            "vorschlaege: _element('zVorschlaege').innerHTML, hinweis: _element('uGeldHinweis').innerHTML, kacheln: _element('zKacheln').innerHTML,"
            "geld: _element('uGeldZahlen').innerHTML, projekte: _element('uProjekteListe').innerHTML,"
            "zahlProjekte: [_element('zahlProjekte').hidden, _element('zahlProjekte').textContent],"
            "titel: _element('seitenkopfTitel').textContent, status: [_element('seitenkopfStatus').className, _element('seitenkopfStatus').textContent],"
            "kennung: _element('seitenkopfKennung').textContent};")


@nur_mit_node
def test_anker_zahlungen_oeffnet_den_reiter_mit_den_zahlen_des_servers(akte_welt):
    db = akte_welt["db"]
    lauf = _lauf(akte_welt, ZEICHNEN, anker="#zahlungen")
    e, kunde = lauf["ergebnis"], lauf["antworten"][f"/api/customers/{akte_welt['kessler'].id}"]
    schluss = db.get(Invoice, akte_welt["schluss"].id)
    assert e["sichtbar"] == ["zahlungen"] and e["anker"] == "#zahlungen"
    # unbezahlt ist nur die Schlussrechnung von A (Zahlbetrag 3.570 €), mit Projekt und Art, Fälligkeit mit Jahr
    assert schluss.invoice_number in e["unbezahlt"] and "3.570,00" in e["unbezahlt"] and "Schlussrechnung" in e["unbezahlt"]
    assert schluss.due_date.strftime("%d.%m.%Y") in e["unbezahlt"]
    # Kennzahlen: unbezahlt 3.570 € als Signalkarte; Guthaben 310 € (Rest von B); bezahlt dieses Jahr 1.500 € (+200 −200), Vorjahr 2.380 €
    assert e["kacheln"].count("karte-signal") == 1 and "3.570,00" in e["kacheln"] and "310,00" in e["kacheln"]
    assert "1.500,00" in e["kacheln"] and "2.380,00" in e["kacheln"] and "überfällig seit " + schluss.due_date.strftime("%d.%m.%Y") in e["kacheln"]
    # Vorschlag: Rest 310 € auf die älteste unbezahlte Rechnung -- Knöpfe mit Geld
    assert f"Auf {schluss.invoice_number} zuordnen …" in e["vorschlaege"] and 'data-klick="vorschlag-erstatten"' in e["vorschlaege"]
    assert 'data-klick="zahlung-zuordnen"' in e["zahlungen"] and 'data-klick="zahlung-zuruecknehmen"' in e["zahlungen"]
    assert "Rest 310,00" in e["zahlungen"] and "data-zahlungsausgang" in e["zahlungen"]
    # Kopf: Name, Kennung, Kategorie blau (freie Gruppe kundenkategorie)
    assert e["titel"] == kunde["name"] and e["kennung"] == (kunde["customer_number"] or "")
    assert e["status"] == ["ds-status ds-status-info", kunde["category"]]
    assert e["zahlProjekte"] == [False, "4"]  # A, B, C, D -- ohne Mustervorgang


@nur_mit_node
def test_anker_versand_oeffnet_den_verlauf_mit_versand(akte_welt):
    e = _lauf(akte_welt, ZEICHNEN, anker="#versand")["ergebnis"]
    assert e["sichtbar"] == ["verlauf"] and e["anker"] == "#verlauf" and e["art"] == "versand"


@nur_mit_node
def test_ohne_anker_die_uebersicht(akte_welt):
    e = _lauf(akte_welt, ZEICHNEN)["ergebnis"]
    assert e["sichtbar"] == ["uebersicht"] and e["anker"] == ""
    # Übersicht: laufende Projekte A und B mit Phase und Zahlen, Geld mit Vorschlag „Zuordnen …“
    assert "Unbezahlt · brutto" in e["geld"] and "3.570,00" in e["geld"] and "Zuordnen …" in e["hinweis"]


@nur_mit_node
def test_buero_auftrag_liest_ohne_knoepfe_und_der_server_lehnt_ab(akte_welt):
    e = _lauf(akte_welt, ZEICHNEN, rolle="buero_auftrag", anker="#zahlungen")["ergebnis"]
    assert e["sichtbar"] == ["zahlungen"]
    assert "Rest 310,00" in e["zahlungen"] and "data-klick=" not in e["zahlungen"] and "ds-menue" not in e["zahlungen"]
    assert "Auf die unbezahlte" in e["vorschlaege"] and "data-klick=" not in e["vorschlaege"] and "data-klick=" not in e["hinweis"]
    db = akte_welt["db"]
    schluss = db.get(Invoice, akte_welt["schluss"].id)
    pid = akte_welt["zahlung_b"].id
    koerper = {"lines": [{"invoice_id": schluss.id, "zahlung": "310.00"}]}
    auftrag = akte_welt["client"](db, payments_router.router, role="buero_auftrag")
    assert auftrag.post(f"/api/payments/{pid}/allocations", json=koerper).status_code == 403
    finanzen = akte_welt["client"](db, *ROUTER, role="buero_finanzen")
    assert finanzen.post(f"/api/payments/{pid}/allocations", json=koerper).status_code == 200
    zahlungen = finanzen.get(f"/api/customers/{akte_welt['kessler'].id}/payments").json()["payments"]
    assert float(next(p for p in zahlungen if p["id"] == pid)["rest"]) == 0
    akte = finanzen.get(f"/api/customers/{akte_welt['kessler'].id}/akte").json()
    assert akte["vorschlaege"] == [] and float(akte["geld"]["unbezahlt"]) == 3260.0


def test_seite_fuer_buero_auftrag_ohne_dialoge_des_gelds(threaded_db_session, router_test_client):
    def markup(rolle):
        text = router_test_client(threaded_db_session, pages_router, role=rolle).get("/customers/1").text
        return re.sub(r"<script.*?</script>", "", text, flags=re.S | re.I)

    auftrag, finanzen = markup("buero_auftrag"), markup("buero_finanzen")
    for dialog in ('id="zuordnenDialog"', 'id="erstattenDialog"', 'id="zuruecknehmenDialog"'):
        assert dialog not in auftrag and dialog in finanzen
    assert "data-geld-nur-lesen" in auftrag and "data-geld-nur-lesen" not in finanzen
    assert 'id="stammdatenDialog"' in auftrag  # Stammdaten pflegt jedes Büro (Festlegung 1.9.120 Nr. 4)


@nur_mit_node
def test_stammdaten_eingaben_bleiben_und_nur_geaendertes_geht_hinaus(akte_welt):
    ablauf = ("await kundenakteStarten(); stammdatenOeffnen(); _element('phone').value = '0241 99 88'; _element('category').value = 'Hausverwaltung';"
              "render(); const nachRender = [_element('phone').value, _element('category').value];"
              "await load(); const nachLaden = [_element('phone').value, _element('category').value];"
              "AUFRUFE.length = 0; await saveCustomer();"
              "return {nachRender, nachLaden, put: AUFRUFE.filter(a => a.methode === 'PUT'), meldung: _element('customerStatus').textContent};")
    e = _lauf(akte_welt, ablauf)["ergebnis"]
    assert e["nachRender"] == ["0241 99 88", "Hausverwaltung"] and e["nachLaden"] == e["nachRender"]
    assert [a["body"] for a in e["put"]] == [{"phone": "0241 99 88", "category": "Hausverwaltung"}]
    assert e["meldung"] == ""


@nur_mit_node
def test_stammdaten_ohne_aenderung_schicken_nichts(akte_welt):
    ablauf = ("await kundenakteStarten(); stammdatenOeffnen(); AUFRUFE.length = 0; await saveCustomer();"
              "return AUFRUFE.filter(a => a.methode !== 'GET');")
    assert _lauf(akte_welt, ablauf)["ergebnis"] == []


@nur_mit_node
def test_kunde_ohne_projekt(akte_welt):
    """Kunde Maus: kein Projekt, ein Rest von 50 € ohne unbezahlte Rechnung -- Vorschlag „Erstattung buchen“."""
    e = _lauf(akte_welt, ZEICHNEN, kunde="maus")["ergebnis"]
    assert "Noch kein Projekt" in e["projekte"] and e["zahlProjekte"] == [True, ""]
    assert "Erstattung buchen …" in e["hinweis"] and "50,00" in e["geld"]


def test_unbezahlte_rechnungen_vom_server(welt):
    from app.kundenakte import geld

    db = welt["db"]
    g = geld(db, welt["kessler"].id, welt["heute"])
    schluss = db.get(Invoice, welt["schluss"].id)
    assert [z["id"] for z in g["unbezahlte"]] == [schluss.id] and g["unbezahlte_rechnungen"] == 1
    z = g["unbezahlte"][0]
    assert z["project_number"] and z["art_text"] and float(z["overview"]["open"]) == 3570.0 and z["is_overdue"]


def test_projekte_nennen_ihr_objekt(welt):
    from app.kundenakte import projekte

    db = welt["db"]
    for p in projekte(db, welt["kessler"].id, welt["heute"]):
        assert "property_id" in p


MENUE = r"""
const _el = (klasse, versteckt) => ({classList: {contains: k => k === klasse}, hidden: !!versteckt});
const E = v => _el('ds-menue-eintrag', v), T = () => _el('ds-menue-trenner');
function lauf(kinder) { dsMenueTrennerOrdnen({children: kinder}); return kinder.filter(k => k.classList.contains('ds-menue-trenner')).map(k => !k.hidden); }
console.log(JSON.stringify([
  lauf([E(), T(), E()]),                      // zwei Gruppen: Linie sichtbar
  lauf([E(true), T(), E()]),                  // erste Gruppe leer: keine Linie
  lauf([E(), T(), E(true), T(), E()]),        // mittlere Gruppe leer: eine Linie
  lauf([T(), E(), T()]),                      // Linie am Anfang und am Ende: keine
  lauf([E(), T(), E(true)]),                  // letzte Gruppe leer: keine
]));
"""


def test_trennlinien_im_menue():
    baustein = "\n".join(re.findall(r"<script>(.*?)</script>", (TEMPLATES / "_menue.html").read_text(encoding="utf-8"), flags=re.S))
    assert node_ausfuehren(baustein + MENUE) == [[True], [False], [True, False], [False, False], [False]]
    assert "dsMenueTrennerOrdnen(liste);\n    liste.hidden = false;" in baustein


UNTERTITEL_DOM = r"""
const _knoten = {};
var document = {readyState: 'complete', addEventListener() {},
  getElementById: id => _knoten[id] || (_knoten[id] = {id, kinder: [], textContent: '', setAttribute() {}, getAttribute: () => null,
    addEventListener() {}, querySelectorAll: () => [], replaceChildren(...k) { this.kinder = k; }}),
  createElement: tag => ({tag, attrs: {}, textContent: '', setAttribute(k, v) { this.attrs[k] = v; }}),
  createTextNode: t => ({tag: '#text', textContent: String(t)})};
"""
UNTERTITEL = r"""
seitenkopf({untertitel: ['Bahnhofstraße 12, 52511 Geilenkirchen', {text: '02451 550120', href: 'tel:02451550120'}, null,
  {text: 'böse', href: 'javascript:alert(1)'}, {text: 'info@example.org', href: 'mailto:info@example.org'}]});
console.log(JSON.stringify(document.getElementById('seitenkopfUntertitel').kinder.map(k => [k.tag, k.textContent, k.attrs ? k.attrs.href : null])));
"""


def test_untertitel_mit_links():
    from tests.test_v445_statuskennzeichen import _baustein_js

    kinder = node_ausfuehren(UNTERTITEL_DOM + _baustein_js("_seitenkopf.html") + UNTERTITEL)
    assert kinder == [["#text", "Bahnhofstraße 12, 52511 Geilenkirchen", None], ["#text", " · ", None], ["a", "02451 550120", "tel:02451550120"],
                      ["#text", " · ", None], ["a", "böse", "#"], ["#text", " · ", None], ["a", "info@example.org", "mailto:info@example.org"]]


def _menue_gruppen(datei):
    text = (TEMPLATES / datei).read_text(encoding="utf-8")
    teil = text.split('{% elif teil == "menue" %}', 1)[1].split("{% endcall %}", 1)[0]
    gruppen = [[]]
    for m in re.finditer(r'class="ds-menue-trenner"|data-klick="([A-Za-z-]+)"(?: data-ziel="([a-z]+)")?|id="(menue[A-Za-z]+)"', teil):
        if m.group(0).startswith('class="ds-menue-trenner"'):
            gruppen.append([])
        else:
            gruppen[-1].append(m.group(2) or m.group(1) or m.group(3))
    return gruppen


def test_menue_der_akte_in_drei_gruppen():
    status, projekt, wege = _menue_gruppen("akte.html")
    assert status == ["laeuft", "pausiert", "abgeschlossen", "stornoZuruecknehmen", "storniert"]
    assert projekt == ["projekt-bearbeiten", "beteiligte-oeffnen", "projekt-kopieren", "als-muster", "wartungsvertrag", "archivieren",
                       "projekt-loeschen"]
    assert wege == ["menueAbPdf", "ab-pdf", "menueAv", "menueBerichte"]


def test_menue_der_kundenakte_in_zwei_gruppen_ohne_archivieren():
    kunde, wege = _menue_gruppen("customer.html")
    assert kunde == ["stammdaten-bearbeiten", "objekt-neu", "eintrag-neu"] and wege == ["menueVersandprotokoll"]
    text = (TEMPLATES / "customer.html").read_text(encoding="utf-8")
    assert "archivieren" not in text.split('{% elif teil == "menue" %}', 1)[1].split("{% endcall %}", 1)[0]  # Punkt 4: gibt es nicht


def test_rechnungsliste_spalte_projekt_und_daten_mit_jahr():
    baustein = "\n".join(re.findall(r"<script>(.*?)</script>", (TEMPLATES / "_rechnungsliste.html").read_text(encoding="utf-8"), flags=re.S))
    zeile = {"id": 7, "invoice_number": "RE-2026-0094", "project_id": 3, "project_number": "P-2026-0118", "order_id": 5, "art_text": "2. Abschlag",
             "due_date": "2026-10-24", "gross_total": "14481.11", "overview": {"state": "offen", "open": "14481.11"}, "status": "versendet"}
    skript = ("function berlinToday() { return '2026-10-29'; }\n" + baustein
              + f"\nconst r = {json.dumps(zeile)};\n"
              "console.log(JSON.stringify([rechnungsTabelleHtml([r], {spalten: ['projekt', 'faellig'], kopf: {faellig: 'Fällig am'}, mitJahr: true}),"
              "rechnungsTabelleHtml([r], {spalten: ['faellig']})]));")
    mit, ohne = node_ausfuehren(skript)
    assert '<a href="/projects/3?auftrag=5">P-2026-0118</a> · 2. Abschlag' in mit and "24.10.2026" in mit and ">Fällig am</th>" in mit
    assert "24.10.<" in ohne and "24.10.2026" not in ohne
