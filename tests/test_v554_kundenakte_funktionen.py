"""Version 1.9.134 (Stufe 5, R3, Punkt 0) -- jede Funktion der heutigen Kundenakte (customer.html) als Liste: Knopf bzw. Link, Endpunkt, Rolle.

Die Tabelle FUNKTIONEN ist die Liste, an der der Umbau zur Kundenakte nach den Vorlagen (bildgrundlage/entwurf_stufe5_kunde/kunde-*.html) gemessen
wird -- wie FUNKTIONEN in tests/test_v549_akte_seite.py für die Akte je Projekt: je Funktion die Art (Knopf, Link, Feld, Anzeige, Anker), die
Endpunkte mit Methode, die Rolle der Funktion laut Route (Au = ab Büro – Auftrag, Geld = darf_geld(): Admin und Büro – Finanzen; sie gilt für die
schreibenden Endpunkte, ein lesender muss für Büro – Auftrag offen sein -- Au oder auch für die Monteurin), der
Reiter der neuen Kundenakte (laut kunde-zuordnung.html) und die Belege im gezeichneten HTML der heutigen Seite.

Geprüft wird: jeder Beleg steht in der Seite; jeder Endpunkt ist eine Route mit genau der genannten Rolle; jeder Pfad unter /api/, den die Seite
aufruft, steht in der Tabelle (keine Funktion fehlt); die Monteurin bekommt die Seite nicht (403).
"""

import re
from pathlib import Path

import pytest

from app.routers.pages import router as pages_router
from tests import vorlagen_js as vj
from tests.test_v260_role_audit import _discover_routes, _iter_role_marked_dependants

AU = frozenset({"buero_auftrag", "buero_finanzen", "admin"})
GELD = frozenset({"buero_finanzen", "admin"})
MO = frozenset({"field", "buero_auftrag", "buero_finanzen", "admin"})
ROLLEN = {"Au": AU, "Geld": GELD, "Mo": MO}
REITER = ("kopf", "uebersicht", "projekte", "objekte", "anfragen", "zahlungen", "dokumente", "kontakte", "verlauf")

# (Funktion, Art, Endpunkte [(Methode, Pfad)], Rolle, Reiter der Kundenakte, Belege in customer.html)
FUNKTIONEN = [
    # Kopf und Kennzahlen
    ("Kopf: Name, Kundennummer, Kategorie, Ansprechpartner, Ort", "Anzeige", [("GET", "/api/customers/{customer_id}")], "Au", "kopf",
     ['id="pageTitle"', 'id="pageSub"', 'id="customerIdBadge"']),
    ("Kennzahlen Objekte, Anfragen, Projekte, Angebote, Angebotssumme netto", "Anzeige",
     [("GET", "/api/properties"), ("GET", "/api/inquiries"), ("GET", "/api/projects"), ("GET", "/api/projects/{project_id}/quotes")], "Au",
     "kopf", ['id="metricProperties"', 'id="metricInquiries"', 'id="metricProjects"', 'id="metricQuotes"', 'id="metricNet"']),
    # Stammdaten
    ("Stammdaten: Kundennummer, Kategorie, Verbraucher, Zahlungsbedingung, Anrede, Titel, Name, Ansprechpartner, Anschrift, E-Mails, "
     "Telefon, Mobil, Fax, interne Notizen", "Feld",
     [("GET", "/api/settings/option-groups/{group_key}"), ("GET", "/api/payment-terms")], "Au", "uebersicht",
     ['id="customerNumber"', 'id="category"', 'id="isConsumer"', 'id="defaultPaymentTerm"', 'id="salutation"', 'id="title"', 'id="firstName"',
      'id="lastName"', 'id="contact"', 'id="street"', 'id="country"', 'id="zip"', 'id="city"', 'id="email"', 'id="email2"', 'id="phone"',
      'id="mobile"', 'id="fax"', 'id="notes"', "/api/settings/option-groups/customer_categories",
      "/api/settings/option-groups/customer_salutations", "/api/payment-terms?include_archived=true"]),
    ("„Stammdaten speichern“", "Knopf", [("PUT", "/api/customers/{customer_id}")], "Au", "uebersicht",
     ['onclick="saveCustomer()"', "api(`/api/customers/${customerId}`,{method:'PUT'"]),
    # Kontakte & Kundenwissen
    ("Kundenwissen: Einträge (Telefon, E-Mail, Geburtstag, Information) anzeigen", "Anzeige", [("GET", "/api/customers/{customer_id}")], "Au",
     "kontakte", ['id="extras"', "renderExtras()"]),
    ("„+“ Eintrag anlegen", "Knopf", [("POST", "/api/customers/{customer_id}/extra-infos")], "Au", "kontakte",
     ['onclick="newExtra()"', "/extra-infos`,{method:'POST'"]),
    ("Eintrag „Speichern“", "Knopf", [("PUT", "/api/customers/{customer_id}/extra-infos/{info_id}")], "Au", "kontakte",
     ['onclick="saveExtra(', "/extra-infos/${id}`,{method:'PUT'"]),
    ("Eintrag löschen („×“)", "Knopf", [("DELETE", "/api/customers/{customer_id}/extra-infos/{info_id}")], "Au", "kontakte",
     ['onclick="deleteExtra(', "/extra-infos/${id}`,{method:'DELETE'"]),
    # Objekte
    ("Objekte mit Hauptadresse und Notiz, „Öffnen“", "Link", [("GET", "/api/properties")], "Au", "objekte",
     ['id="properties"', 'href="/properties/${p.id}"', "/api/properties?customer_id=${customerId}"]),
    ("„+“ Objekt anlegen", "Knopf", [("POST", "/api/properties")], "Au", "objekte",
     ['onclick="newProperty()"', "api('/api/properties',{method:'POST'"]),
    ("Objekt „Bearbeiten“ (nicht die Hauptadresse)", "Knopf", [("PUT", "/api/properties/{property_id}")], "Au", "objekte",
     ['onclick="editProperty(', "api(`/api/properties/${id}`,{method:'PUT'"]),
    ("Dachflächen je Objekt, „Öffnen“", "Link", [("GET", "/api/roof-areas")], "Au", "objekte",
     ["/api/roof-areas?property_id=${p.id}", 'href="/roof-areas/${r.id}"']),
    ("„+ Dachfläche“ anlegen, danach zur Dachfläche", "Knopf", [("POST", "/api/roof-areas")], "Au", "objekte",
     ['onclick="toggleNewRoofArea(', "api('/api/roof-areas',{method:'POST'", "location.href='/roof-areas/'+result.id"]),
    # Anfragen
    ("Anfragen mit Objekt, Status, Wiedervorlage; „Pipeline öffnen“", "Link", [("GET", "/api/inquiries")], "Au", "anfragen",
     ['id="inquiries"', "/api/inquiries?customer_id=${customerId}", 'href="/inquiries"']),
    ("„Neue Anfrage“", "Link", [], "Au", "anfragen", ['id="newInquiryLink"', "`/inquiries?customer_id=${customerId}`"]),
    # Dokumente
    ("Dokumente hochladen: Kategorie, Unterordner, Datum, Notiz, Dateien wählen oder hineinziehen", "Knopf",
     [("POST", "/api/customers/{customer_id}/documents")], "Au", "dokumente",
     ['id="docUploadZone"', 'id="docCategory"', 'id="docSubfolder"', 'id="docDate"', 'id="docDescription"', 'onclick="uploadDocuments()"',
      "/documents`,{method:'POST',body:fd}", "/api/settings/option-groups/project_document_categories"]),
    ("Dokumente: Kacheln je Kategorie und Unterordner, Suche", "Anzeige", [("GET", "/api/customers/{customer_id}/documents")], "Au",
     "dokumente", ['id="docCategoryCards"', 'id="docSubfolderCards"', 'id="docSearch"', "api(`/api/customers/${customerId}/documents`)"]),
    ("Dokument „Öffnen“ (Vorschau)", "Link", [("GET", "/api/customer-documents/{document_id}/view")], "Au", "dokumente",
     ["/api/customer-documents/${d.id}/view"]),
    ("Dokument „Download“", "Link", [("GET", "/api/customer-documents/{document_id}/download")], "Au", "dokumente",
     ["/api/customer-documents/${d.id}/download"]),
    ("Dokument „Bearbeiten“: Kategorie, Unterordner, Datum, Notiz", "Knopf", [("PUT", "/api/customer-documents/{document_id}")], "Au",
     "dokumente", ['onclick="editDocRow(', 'id="docEditor"', "`/api/customer-documents/${editingDocId}`"]),
    ("Dokument „Löschen“", "Knopf", [("DELETE", "/api/customer-documents/{document_id}")], "Au", "dokumente",
     ['onclick="removeDocRow(', "api(`/api/customer-documents/${id}`,{method:'DELETE'})"]),
    # Projekte & Angebote
    ("Projekte mit Objekt und Status, je Projekt die Angebote (Nummer, Titel, Status, netto, brutto); „Projekt öffnen“", "Link",
     [("GET", "/api/projects"), ("GET", "/api/projects/{project_id}/quotes")], "Au", "projekte",
     ['id="projects"', "api(`/api/projects/${p.id}/quotes`)", 'href="/projects?project_id=${p.id}"']),
    ("„Projekt anlegen“", "Link", [], "Au", "kopf", ['id="newProjectLink"', "`/projects/new?customer_id=${customerId}`"]),
    # Zahlungen
    ("Guthaben des Kunden: Rest je Zahlung, Überzahlung je Schlussrechnung", "Anzeige", [("GET", "/api/customers/{customer_id}/payments")],
     "Au", "zahlungen", ['id="customerCredits"', 'id="paymentRestBadge"', "data-guthaben-zeile"]),
    ("„Erstattung buchen“: Beträge je Zeile, ausgezahlt am, Notiz", "Knopf", [("POST", "/api/customers/{customer_id}/refunds")], "Geld",
     "zahlungen", ['onclick="bookCustomerRefund()"', "/refunds`,{method:'POST'"]),
    ("Zahlungen mit Zuordnungen (Link zur Rechnung), Rest, Zahlungsausgänge", "Anzeige",
     [("GET", "/api/customers/{customer_id}/payments")], "Au", "zahlungen",
     ['id="customerPayments"', 'href="/invoices/${a.invoice_id}"', "data-zahlungsausgang"]),
    ("Rest zuordnen: Rechnung wählen, Betrag, „Zuordnen“", "Knopf",
     [("GET", "/api/customers/{customer_id}/open-invoices"), ("POST", "/api/payments/{payment_id}/allocations")], "Geld", "zahlungen",
     ['onclick="allocateRest(', "/open-invoices`", "/allocations`,{method:'POST'"]),
    ("„Zahlung zurücknehmen“ mit Begründung (oder der Grund, warum nicht)", "Knopf", [("POST", "/api/payments/{payment_id}/reverse")], "Geld",
     "zahlungen", ['onclick="showPaymentReverse(', 'onclick="reversePayment(', "data-zuruecknehmen-gesperrt"]),
    ("Hinweis „nur lesen“ für Büro – Auftrag", "Anzeige", [], "Au", "zahlungen", ["{{ geld_nur_lesen }}"]),
    ("Anker #zahlungen (aus Rechnung und Finanzen)", "Anker", [], "Au", "zahlungen",
     ['id="zahlungen"', "location.hash==='#zahlungen'"]),
    # Versand
    ("Versand des Kunden: Einträge aus seinen Projekten und Objekten, Empfang bestätigt / unzustellbar, „Im Versandprotokoll öffnen“",
     "Anzeige", [("GET", "/api/email-dispatches")], "Au", "verlauf",
     ['id="customerDispatches"', "renderDispatchList('customerDispatches',{customer_id:customerId})"]),
]


def _seite(client):
    antwort = client.get("/customers/1")
    assert antwort.status_code == 200, antwort.text[:300]
    return antwort.text


def test_liste_vollstaendig_und_reiter_bekannt():
    assert len(FUNKTIONEN) >= 30
    assert {f[4] for f in FUNKTIONEN} <= set(REITER)
    assert {f[3] for f in FUNKTIONEN} <= set(ROLLEN)
    # jede Seite der Vorlage hat Funktionen: alle Reiter außer der Übersicht (dort lesend die Stammdaten) bekommen etwas
    assert {f[4] for f in FUNKTIONEN} == set(REITER)


def test_jede_funktion_steht_auf_der_heutigen_seite(threaded_db_session, router_test_client):
    text = _seite(router_test_client(threaded_db_session, pages_router, role="buero_finanzen"))
    vorlage = (vj.TEMPLATES / "customer.html").read_text(encoding="utf-8")
    fehlt = [(f[0], b) for f in FUNKTIONEN for b in f[5] if b not in text and b not in vorlage]
    assert fehlt == []


def _routen():
    out = {}
    for methode, pfad, route in _discover_routes(api=True):
        rollen = list(_iter_role_marked_dependants(route.dependant))
        out[(methode, pfad)] = frozenset.intersection(*rollen) if rollen else None
    return out


def test_endpunkte_mit_ihrer_rolle():
    routen = _routen()
    falsch = []
    for funktion, _, endpunkte, rolle, _, _ in FUNKTIONEN:
        for ep in endpunkte:
            erwartet = ROLLEN[rolle] if ep[0] != "GET" else None
            if ep not in routen:
                falsch.append((funktion, ep, "keine Route"))
            elif erwartet is not None and routen[ep] != erwartet:
                falsch.append((funktion, ep, sorted(routen[ep] or [])))
            elif erwartet is None and routen[ep] not in (AU, MO):  # lesend: Büro – Auftrag liest alles
                falsch.append((funktion, ep, sorted(routen[ep] or [])))
    assert falsch == []


def _api_pfade(text):
    """Jeder Pfad unter /api/, den das Skript der Seite aufruft -- ${…} wird {}, die Abfrage fällt weg."""
    pfade = set()
    for m in re.finditer(r"/api/[A-Za-z0-9_\-/${}.]+", text):
        pfad = re.sub(r"\$\{[^}]*\}", "{}", m.group(0)).rstrip("/")
        pfade.add(pfad)
    return pfade


def _normal(pfad):
    return re.sub(r"\{[^}]*\}", "{}", pfad)


def test_jeder_api_aufruf_der_seite_steht_in_der_liste():
    seite = vj.zusammensetzen("customer.html")[0]
    aufrufe = _api_pfade(vj.TEMPLATES.joinpath("customer.html").read_text(encoding="utf-8"))
    # die Versandliste kommt aus dem Baustein _email_dispatch.html (renderDispatchList)
    assert "renderDispatchList(" in seite
    aufrufe.add("/api/email-dispatches")
    gelistet = {_normal(p) for f in FUNKTIONEN for _, p in f[2]}
    # feste Pfade mit Schlüssel in der Seite (Optionsgruppen) gelten als der Pfad mit Platzhalter
    aufrufe = {re.sub(r"^/api/settings/option-groups/[a-z_]+$", "/api/settings/option-groups/{}", p) for p in aufrufe}
    assert sorted(a for a in aufrufe if a not in gelistet) == []


def test_monteurin_bekommt_keine_kundenakte(threaded_db_session, router_test_client):
    client = router_test_client(threaded_db_session, pages_router, role="field")
    assert client.get("/customers/1").status_code == 403


@pytest.mark.parametrize("rolle", ["buero_auftrag", "buero_finanzen", "admin"])
def test_buero_bekommt_die_seite(threaded_db_session, router_test_client, rolle):
    _seite(router_test_client(threaded_db_session, pages_router, role=rolle))
