"""Version 1.9.134 (Stufe 5, R3, Punkt 0) -- jede Funktion der Kundenakte (customer.html) als Liste: Knopf bzw. Link, Endpunkt, Rolle; seit
1.9.137 (Punkt 2) gemessen an der neuen Kundenakte nach den Vorlagen (bildgrundlage/entwurf_stufe5_kunde/kunde-*.html).

Die Tabelle FUNKTIONEN ist die Liste, an der der Umbau gemessen wird -- wie FUNKTIONEN in tests/test_v549_akte_seite.py für die Akte je Projekt:
je Funktion die Art (Knopf, Link, Feld, Anzeige, Anker), die Endpunkte mit Methode, die Rolle der Funktion laut Route (Au = ab Büro – Auftrag,
Geld = darf_geld(): Admin und Büro – Finanzen; sie gilt für die schreibenden Endpunkte, ein lesender muss für Büro – Auftrag offen sein -- Au oder
auch für die Monteurin), der Reiter der Kundenakte (laut kunde-zuordnung.html) und die Belege im gezeichneten HTML bzw. in der Vorlage. Bis 1.9.136
standen hier die Belege der früheren Seite (Formular immer offen, Karten untereinander); jede Funktion von damals steht hier wieder -- die Kennzahlen
als Zähler an den Reitern und Karte „Geld“, die Karte „Versand“ als Verlauf mit „Versand“ und „Zustellung nachtragen“ im Dialog.

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
AKTE = ("GET", "/api/customers/{customer_id}/akte")

# (Funktion, Art, Endpunkte [(Methode, Pfad)], Rolle, Reiter der Kundenakte, Belege in customer.html)
FUNKTIONEN = [
    # Kopf
    ("Kopf: Name, Kundennummer, Kategorie, Anschrift, Telefon und E-Mail als Link; Pfad Stammdaten / Kunden", "Anzeige",
     [("GET", "/api/customers/{customer_id}")], "Au", "kopf",
     ["seitenkopf({titel:customer.name,kennung:customer.customer_number", "statusKennzeichen('kundenkategorie',customer.category)",
      "href:'tel:'", "href:'mailto:'", "{text:'Kunden',href:'/master-data#customers'}"]),
    ("Zähler an den Reitern (bis 1.9.136 Kennzahlen Objekte, Anfragen, Projekte, Angebote, Angebotssumme)", "Anzeige",
     [AKTE, ("GET", "/api/properties"), ("GET", "/api/inquiries")], "Au", "kopf",
     ['id="zahlProjekte"', 'id="zahlObjekte"', 'id="zahlAnfragen"', 'id="zahlDokumente"', 'id="zahlKontakte"',
      "api(`/api/customers/${customerId}/akte`)"]),
    ("„+ Projekt“ als Hauptaktion (bis 1.9.136 „Projekt anlegen“)", "Link", [], "Au", "kopf",
     ['id="newProjectLink"', "`/projects/new?customer_id=${customerId}`"]),
    ("„⋮“ in zwei Gruppen: Stammdaten bearbeiten, + Objekt, + Eintrag, Neue Anfrage · Versandprotokoll des Kunden, Ganze Änderungshistorie",
     "Knopf", [], "Au", "kopf",
     ['class="ds-menue-trenner"', "'/versandprotokoll?kunde='+customerId", 'href="/history"', 'id="newInquiryLink"']),
    # Übersicht
    ("Laufende Projekte mit Phase und Zahlen, „Abgeschlossen: …“, „Alle … Projekte“", "Anzeige", [AKTE], "Au", "uebersicht",
     ['id="uProjekteListe"', 'id="uAbgeschlossen"', 'id="uAlleProjekte"']),
    ("Geld: unbezahlt, Guthaben, abgerechnet und bezahlt im Jahr, Vorschlag zum Guthaben", "Anzeige", [AKTE], "Au", "uebersicht",
     ['id="uGeldZahlen"', 'id="uGeldHinweis"', "vorschlagHtml(akte.vorschlaege[0],true)"]),
    ("Verlauf: die letzten vier Einträge, „Ganzer Verlauf“", "Anzeige", [("GET", "/api/customers/{customer_id}/verlauf")], "Au", "uebersicht",
     ['id="uVerlaufListe"', 'href="#verlauf"']),
    ("Stammdaten lesend: Kundennummer, Kategorie, Verbraucher, Zahlungsbedingung, Rechnungen an, Interne Notiz", "Anzeige",
     [("GET", "/api/customers/{customer_id}"), ("GET", "/api/payment-terms")], "Au", "uebersicht",
     ['id="stammdatenListe"', "'Rechnungen an'", "'Verbraucher'"]),
    ("Dialog „Stammdaten bearbeiten“: Kundennummer, Kategorie, Verbraucher, Zahlungsbedingung, Anrede, Titel, Name, Ansprechpartner, Anschrift, "
     "E-Mails, Telefon, Mobil, Fax, interne Notizen", "Feld",
     [("GET", "/api/settings/option-groups/{group_key}"), ("GET", "/api/payment-terms")], "Au", "uebersicht",
     ['id="stammdatenDialog"', 'data-klick="stammdaten-bearbeiten"', 'id="customerNumber"', 'id="category"', 'id="isConsumer"',
      'id="defaultPaymentTerm"', 'id="salutation"', 'id="title"', 'id="firstName"', 'id="lastName"', 'id="contact"', 'id="street"',
      'id="country"', 'id="zip"', 'id="city"', 'id="email"', 'id="email2"', 'id="phone"', 'id="mobile"', 'id="fax"', 'id="notes"',
      "/api/settings/option-groups/customer_categories", "/api/settings/option-groups/customer_salutations",
      "/api/payment-terms?include_archived=true"]),
    ("„Stammdaten speichern“ -- nur, was im Dialog geändert ist", "Knopf", [("PUT", "/api/customers/{customer_id}")], "Au", "uebersicht",
     ['data-klick="stammdaten-speichern"', "api(`/api/customers/${customerId}`,{method:'PUT'",
      "if(jetzt[k]!==stand[k])geaendert[k]=jetzt[k]"]),
    # Kontakte & Kundenwissen
    ("Kundenwissen: Einträge (Telefon, E-Mail, Geburtstag, Information) anzeigen, Telefon und E-Mail als Link", "Anzeige",
     [("GET", "/api/customers/{customer_id}")], "Au", "kontakte", ['id="extras"', 'id="uKontakteListe"', "renderExtras()"]),
    ("„+ Eintrag“ im Dialog", "Knopf", [("POST", "/api/customers/{customer_id}/extra-infos")], "Au", "kontakte",
     ['data-klick="eintrag-neu"', 'id="extraDialog"', "/extra-infos`,{method:'POST'"]),
    ("Eintrag „Bearbeiten“ im Dialog, „Speichern“", "Knopf", [("PUT", "/api/customers/{customer_id}/extra-infos/{info_id}")], "Au", "kontakte",
     ['data-klick="eintrag-bearbeiten"', 'data-klick="eintrag-speichern"', "/extra-infos/${id}`,{method:'PUT'"]),
    ("Eintrag „Löschen“", "Knopf", [("DELETE", "/api/customers/{customer_id}/extra-infos/{info_id}")], "Au", "kontakte",
     ['data-klick="eintrag-loeschen"', "/extra-infos/${id}`,{method:'DELETE'"]),
    # Objekte
    ("Objekte mit Hauptadresse, Notiz, Projekten, „Öffnen“; Kurzliste in der Übersicht", "Link", [("GET", "/api/properties")], "Au", "objekte",
     ['id="properties"', 'id="uObjekteListe"', 'href="/properties/${p.id}"', "/api/properties?customer_id=${customerId}"]),
    ("„+ Objekt“ im Dialog", "Knopf", [("POST", "/api/properties")], "Au", "objekte",
     ['data-klick="objekt-neu"', 'id="propertyDialog"', "api('/api/properties',{method:'POST'"]),
    ("Objekt „Bearbeiten“ im Dialog (nicht die Hauptadresse)", "Knopf", [("PUT", "/api/properties/{property_id}")], "Au", "objekte",
     ['data-klick="objekt-bearbeiten"', "api(`/api/properties/${id}`,{method:'PUT'"]),
    ("Dachflächen je Objekt, „Öffnen“", "Link", [("GET", "/api/roof-areas")], "Au", "objekte",
     ["/api/roof-areas?property_id=${p.id}", 'href="/roof-areas/${r.id}"']),
    ("„+ Dachfläche“ im Dialog, danach zur Dachfläche", "Knopf", [("POST", "/api/roof-areas")], "Au", "objekte",
     ['data-klick="dachflaeche-neu"', "api('/api/roof-areas',{method:'POST'", "location.href='/roof-areas/'+result.id"]),
    # Anfragen
    ("Anfragen mit Objekt, Status, Wiedervorlage; „Pipeline öffnen“", "Link", [("GET", "/api/inquiries")], "Au", "anfragen",
     ['id="inquiries"', "/api/inquiries?customer_id=${customerId}", 'href="/inquiries"']),
    ("„Neue Anfrage“", "Link", [], "Au", "anfragen", ['id="newInquiryLink2"', "`/inquiries?customer_id=${customerId}`"]),
    # Dokumente
    ("Dokumente hochladen: Kategorie, Unterordner, Datum, Notiz, Dateien wählen oder hineinziehen", "Knopf",
     [("POST", "/api/customers/{customer_id}/documents")], "Au", "dokumente",
     ['id="docUploadZone"', 'id="docCategory"', 'id="docSubfolder"', 'id="docDate"', 'id="docDescription"', 'data-klick="hochladen"',
      "/documents`,{method:'POST',body:fd}", "/api/settings/option-groups/project_document_categories"]),
    ("Dokumente: Kacheln je Kategorie und Unterordner, Suche", "Anzeige", [("GET", "/api/customers/{customer_id}/documents")], "Au",
     "dokumente", ['id="docCategoryCards"', 'id="docSubfolderCards"', 'id="docSearch"', "api(`/api/customers/${customerId}/documents`)"]),
    ("Dokument „Öffnen“ (Vorschau)", "Link", [("GET", "/api/customer-documents/{document_id}/view")], "Au", "dokumente",
     ["/api/customer-documents/${d.id}/view"]),
    ("Dokument „Download“", "Link", [("GET", "/api/customer-documents/{document_id}/download")], "Au", "dokumente",
     ["/api/customer-documents/${d.id}/download"]),
    ("Dokument „Bearbeiten“ im Dialog: Kategorie, Unterordner, Datum, Notiz", "Knopf", [("PUT", "/api/customer-documents/{document_id}")], "Au",
     "dokumente", ['data-klick="dokument-bearbeiten"', 'id="docEditor"', "`/api/customer-documents/${editingDocId}`"]),
    ("Dokument „Löschen“", "Knopf", [("DELETE", "/api/customer-documents/{document_id}")], "Au", "dokumente",
     ['data-klick="dokument-loeschen"', "api(`/api/customer-documents/${id}`,{method:'DELETE'})"]),
    # Projekte & Angebote
    ("Projekte mit Phase und Zahlen, je Projekt Aufträge und Angebote (Nummer, Titel, Stand, netto, brutto); Link in die Akte (bis 1.9.136 "
     "/projects?project_id=, das die Liste nicht auswertete)", "Link", [AKTE], "Au", "projekte",
     ['id="projects"', 'href="/projects/${p.id}"', 'href="/quotes/${q.id}/edit"', 'href="/projects/${p.id}?auftrag=${o.id}"']),
    # Zahlungen
    ("Kennzahlen unbezahlt, Guthaben, bezahlt in diesem und im vorigen Jahr; unbezahlte Rechnungen", "Anzeige", [AKTE], "Au", "zahlungen",
     ['id="zKacheln"', 'id="zUnbezahlt"', "rechnungsTabelleHtml(g.unbezahlte"]),
    ("Guthaben des Kunden: Rest je Zahlung, Überzahlung je Schlussrechnung; Vorschlag „Auf RE-… zuordnen“ bzw. „Erstattung buchen“", "Anzeige",
     [("GET", "/api/customers/{customer_id}/payments"), AKTE], "Au", "zahlungen",
     ['id="zVorschlaege"', "data-vorschlag=", "data-guthaben-zeile", 'data-klick="vorschlag-zuordnen"', 'data-klick="vorschlag-erstatten"']),
    ("„Erstattung buchen“ im Dialog: Beträge je Zeile, ausgezahlt am, Notiz", "Knopf", [("POST", "/api/customers/{customer_id}/refunds")], "Geld",
     "zahlungen", ['data-klick="zahlung-erstatten"', 'data-klick="erstatten"', "/refunds`,{method:'POST'"]),
    ("Zahlungseingänge mit Zuordnung (Link zur Rechnung), Rest, Zahlungsausgänge", "Anzeige",
     [("GET", "/api/customers/{customer_id}/payments")], "Au", "zahlungen",
     ['id="customerPayments"', 'href="/invoices/${a.invoice_id}"', "data-zahlungsausgang", "data-rest"]),
    ("Rest zuordnen im Dialog: Rechnung wählen, Betrag, „Zuordnen“", "Knopf",
     [("GET", "/api/customers/{customer_id}/open-invoices"), ("POST", "/api/payments/{payment_id}/allocations")], "Geld", "zahlungen",
     ['data-klick="zahlung-zuordnen"', 'data-klick="zuordnen"', "/open-invoices`", "/allocations`,{method:'POST'"]),
    ("„Zurücknehmen“ mit Begründung (oder der Grund, warum nicht)", "Knopf", [("POST", "/api/payments/{payment_id}/reverse")], "Geld",
     "zahlungen", ['data-klick="zahlung-zuruecknehmen"', 'data-klick="zuruecknehmen"', "data-zuruecknehmen-gesperrt"]),
    ("Hinweis „nur lesen“ für Büro – Auftrag", "Anzeige", [], "Au", "zahlungen", ["{{ geld_nur_lesen }}"]),
    ("Anker #zahlungen (aus Rechnung und Finanzen) öffnet den Reiter", "Anker", [], "Au", "zahlungen",
     ['href="#zahlungen" data-reiter="zahlungen"', "reiterZeigen(reiterAusAnker()"]),
    # Verlauf
    ("Verlauf des Kunden: Filter nach Art, „Ältere laden“, Ziel je Zeile", "Anzeige", [("GET", "/api/customers/{customer_id}/verlauf")], "Au",
     "verlauf", ['id="verlaufListe"', 'data-klick="verlauf-art"', 'data-klick="verlauf-weiter"', "`/api/customers/${customerId}/verlauf`"]),
    ("Versand des Kunden (bis 1.9.136 Karte „Versand“): Filter „Versand“, „Zustellung nachtragen“ samt Empfang bestätigt / unzustellbar im "
     "Dialog, „Versandprotokoll des Kunden“, Anker #versand", "Anzeige", [("GET", "/api/email-dispatches")], "Au", "verlauf",
     ['data-art="versand"', "renderDispatchHistory('zustellungVerlauf'", 'id="versandprotokollLink"', "ALTE_ANKER={versand:'verlauf'}"]),
]


def _seite(client):
    antwort = client.get("/customers/1")
    assert antwort.status_code == 200, antwort.text[:300]
    return antwort.text


def test_liste_vollstaendig_und_reiter_bekannt():
    assert len(FUNKTIONEN) >= 31  # bis 1.9.136 die 31 der früheren Seite
    assert {f[4] for f in FUNKTIONEN} <= set(REITER)
    assert {f[3] for f in FUNKTIONEN} <= set(ROLLEN)
    # jede Seite der Vorlage hat Funktionen: alle Reiter außer der Übersicht (dort lesend die Stammdaten) bekommen etwas
    assert {f[4] for f in FUNKTIONEN} == set(REITER)


def test_jede_funktion_steht_auf_der_kundenakte(threaded_db_session, router_test_client):
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
    # der Versandverlauf eines Dokuments kommt aus dem Baustein _email_dispatch.html (renderDispatchHistory, seit 1.9.137; bis 1.9.136 die
    # Versandliste renderDispatchList)
    assert "renderDispatchHistory(" in seite
    aufrufe.add("/api/email-dispatches")
    gelistet = {_normal(p) for f in FUNKTIONEN for _, p in f[2]}
    # feste Pfade mit Schlüssel in der Seite (Optionsgruppen) gelten als der Pfad mit Platzhalter
    aufrufe = {re.sub(r"^/api/settings/option-groups/[a-z_]+$", "/api/settings/option-groups/{}", p) for p in aufrufe}
    aufrufe = {_normal(p) for p in aufrufe}  # seit 1.9.137: auch Pfade aus Kommentaren („GET /api/customers/{id}/akte“)
    assert sorted(a for a in aufrufe if a not in gelistet) == []


def test_monteurin_bekommt_keine_kundenakte(threaded_db_session, router_test_client):
    client = router_test_client(threaded_db_session, pages_router, role="field")
    assert client.get("/customers/1").status_code == 403


@pytest.mark.parametrize("rolle", ["buero_auftrag", "buero_finanzen", "admin"])
def test_buero_bekommt_die_seite(threaded_db_session, router_test_client, rolle):
    _seite(router_test_client(threaded_db_session, pages_router, role=rolle))
