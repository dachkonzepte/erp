"""Version 1.9.129 (Stufe 5, R2, Punkte 2, 3 und 5) -- /projects/{id} ist die Akte, /orders/{id} leitet dorthin.

Projektmappe (project_folder.html) und Auftragsseite (order.html) sind in akte.html aufgegangen. Jede Funktion der beiden Seiten (Liste aus
dem Befund Stufe 5, bildgrundlage/bericht_stufe5_befund_auftragsakte_47e3d17.txt, Abschnitte „Projektmappe“ und „Auftrag“) steht in der
Akte -- oder entfällt mit der Entscheidung, die sie ersetzt. Büro – Auftrag sieht Geld ohne Knöpfe, die Monteurin bekommt keine Akte (403).
Arbeitsvorbereitung, Einsatzberichte, Bericht, Rechnung und Checklisten führen in die Akte zurück (Reiter über den Anker).
"""

import re
from pathlib import Path

import pytest

from app.routers.pages import router as pages_router
from tests import vorlagen_js as vj
from tests.test_v325_contract_basis import beauftragen, make_quote

VORLAGEN = Path(__file__).resolve().parents[1] / "app" / "templates"


def _akte(client, url="/projects/1"):
    antwort = client.get(url)
    assert antwort.status_code == 200, antwort.text[:300]
    return antwort.text


def _ohne_skript(text):
    return re.sub(r"<script.*?</script>", "", text, flags=re.S | re.I)


# --- /orders/{id} -> Akte --------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("rolle", ("buero_auftrag", "buero_finanzen", "admin"))
def test_auftragsseite_leitet_in_die_akte(rolle, threaded_db_session, router_test_client):
    db = threaded_db_session
    order = beauftragen(db, make_quote(db, is_consumer=False, number="0549a"))
    client = router_test_client(db, pages_router, role=rolle)
    antwort = client.get(f"/orders/{order.id}", follow_redirects=False)
    assert (antwort.status_code, antwort.headers["location"]) == (302, f"/projects/{order.project_id}?auftrag={order.id}")
    antwort = client.get("/orders/987654", follow_redirects=False)  # unbekannt: die Projektliste, kein 500
    assert (antwort.status_code, antwort.headers["location"]) == (302, "/projects")
    assert client.get(f"/projects/{order.project_id}?auftrag={order.id}").status_code == 200


def test_monteurin_bekommt_keine_akte(threaded_db_session, router_test_client):
    db = threaded_db_session
    order = beauftragen(db, make_quote(db, is_consumer=False, number="0549b"))
    client = router_test_client(db, pages_router, role="field")
    assert client.get(f"/projects/{order.project_id}").status_code == 403
    assert client.get(f"/orders/{order.id}", follow_redirects=False).status_code == 403


@pytest.mark.parametrize("wert", ["²", "5x", "-1", "//evil.example", "1" * 5000])
def test_auftrag_aus_der_adresse_nur_als_zahl(wert, threaded_db_session, router_test_client):
    text = _akte(router_test_client(threaded_db_session, pages_router, role="admin"), f"/projects/1?auftrag={wert}")
    assert "const AUFTRAG_WUNSCH=null;" in text


def test_auftrag_aus_der_adresse(threaded_db_session, router_test_client):
    text = _akte(router_test_client(threaded_db_session, pages_router, role="admin"), "/projects/1?auftrag=42")
    assert "const AUFTRAG_WUNSCH=42;" in text


# --- jede Funktion der beiden Seiten ---------------------------------------------------------------------------------------------------
# (alte Seite, Funktion laut Befund, Reiter der Akte oder "kopf", Belege im gezeichneten HTML); Reiter None = entfällt, Belege = Grund

FUNKTIONEN = [
    # Projektmappe
    ("Projektmappe", "Kopf: „Projektmappe bearbeiten“ mit Dialog", "kopf",
     ['data-klick="projekt-bearbeiten"', 'id="projectModal"', "api(`/api/projects/${projectId}`,{method:'PUT'"]),
    ("Projektmappe", "Menü: Kopieren, Als Mustervorgang speichern", "kopf",
     ['data-klick="projekt-kopieren"', 'data-klick="als-muster"', "/duplicate`"]),
    ("Projektmappe", "Menü: Wartungsvertrag erstellen", "kopf",
     ['id="maintenanceContractMenuItem"', 'id="maintenanceContractModal"', "/api/maintenance-contracts/from-project/"]),
    ("Projektmappe", "Menü: Archivieren / Entarchivieren", "kopf", ['id="archiveMenuItem"', "'unarchive':'archive'"]),
    ("Projektmappe", "Menü: Löschen (nur ohne Auftrag)", "kopf", ['id="deleteMenuItem"', "(project.order_count||0)>0"]),
    ("Projektmappe", "Kennzahlen Projektwert, Abgerechnet, Noch offen, Soll-/Ist-Stunden", "uebersicht",
     ['id="uAbrechnung"', 'id="uStunden"', 'id="auftraegeSumme"', "/zahlen`"]),
    ("Projektmappe", "Übersicht: Kunde, Objekt, Beschreibung", "uebersicht", ['id="uBeteiligteListe"', "project.description"]),
    ("Projektmappe", "„+ Angebot“", "angebote", ['id="newQuote"', "'/quotes/new?project_id='+projectId"]),
    ("Projektmappe", "Dateien: hochladen mit Kategorie, Unterordner, Datum, Notiz; Ziehen in die Zone", "dateien",
     ['id="uploadZone"', 'id="category"', 'id="subfolder"', 'id="documentDate"', 'id="fileDescription"', "/documents`,{method:'POST',body:fd}"]),
    ("Projektmappe", "Dateien: Kacheln, Unterordner, Suche, Kategorie-Filter", "dateien",
     ['id="categoryCards"', 'id="subfolderCards"', 'id="fileSearch"', 'id="categoryFilter"']),
    ("Projektmappe", "Datei: Öffnen, Download, Bearbeiten, Löschen", "dateien",
     ["/api/project-documents/${d.id}/view", "/api/project-documents/${d.id}/download", 'id="documentModal"',
      "api('/api/project-documents/'+id,{method:'DELETE'})"]),
    ("Projektmappe", "Angebote: Tabelle mit Stand und „Öffnen“", "angebote", ['id="quotes"', "/quotes/${Number(q.id)}/edit"]),
    ("Projektmappe", "Aufträge: Liste, „Öffnen“", "kopf", ['id="auftragswahl"', "?auftrag=${Number(a.id)}"]),
    ("Projektmappe", "Rechnungen: Liste, „Alle Rechnungen (Finanzen)“", "rechnungen", ['id="invoicesList"', 'href="/finanzen"', "rechnungsTabelleHtml("]),
    ("Projektmappe", "Arbeitsvorbereitung je Auftrag öffnen", "ausfuehrung", ['id="avLink"', 'id="avStand"', "/work-preparation'"]),
    ("Projektmappe", "Zeiten: Kennzahlen, Mitarbeiter, „Zeiten öffnen“", "ausfuehrung",
     ['id="zeitenStand"', 'id="zeitenLink"', 'id="uMitarbeiter"', "&zeitraum=alle#buchungen"]),
    ("Projektmappe", "Termine des Projekts, „+ Neuer Termin“", "uebersicht", ['id="uTermineListe"', 'id="newCalendarEvent"', "/kalender?new_project="]),
    ("Projektmappe", "Beteiligte: hinzufügen (Suche, neuer Kontakt), Rolle, Häkchen", "kopf",
     ['id="beteiligteModal"', 'id="participantModal"', "/participant-candidates", "/master-data/contacts/new?projekt=",
      "/participants`,{method:'POST'", "changeParticipantRole(", "setParticipantFlag("]),
    ("Projektmappe", "Beteiligte: Vollmachten als Beleg, Kontakt bearbeiten, entfernen", "kopf",
     ["uploadPowerOfAttorney(", "acceptance-power-of-attorney", "/master-data/contacts/${c.id}/edit", "removeParticipant("]),
    ("Projektmappe", "Versand: Einträge des Projekts, Empfang bestätigt / unzustellbar, Versandprotokoll", "verlauf",
     ['data-art="versand"', 'id="zustellungDialog"', "renderDispatchHistory('zustellungVerlauf'", 'id="versandprotokollLink"']),
    ("Projektmappe", "Historie mit „Gesamte Historie“", "verlauf", ['id="verlaufListe"', 'href="/history"', "/verlauf${s?'?'+s:''}"]),
    # Auftragsseite
    ("Auftrag", "Pfad Kunde · Projekt · Auftrag", "kopf", ["'/customers/'+project.customer_id", 'id="auftragswahl"']),
    ("Auftrag", "„Quellangebot“, Übernehmen ins Auftrag", "leistungen", ['id="syncCard"', "/sync-source-quote`"]),
    ("Auftrag", "„Arbeitsvorbereitung“", "kopf", ['id="menueAv"', 'id="avLink"']),
    ("Auftrag", "„Einsatzberichte (n)“ / „Einsatzbericht anlegen“", "ausfuehrung",
     ['id="menueBerichte"', 'id="serviceReportsLink"', 'id="berichtAnlegen"', "/service-reports?neu=1"]),
    ("Auftrag", "„PDF-Auftragsbestätigung“", "vertrag", ['data-klick="ab-pdf"', "'/api/orders/'+orderId+'/pdf'"]),
    ("Auftrag", "Status mit Übergängen (seit 1.9.124)", "kopf", ['id="auftragsstatus"', "auftragsstatusZeigen(order)"]),
    ("Auftrag", "Offene Bedenken (seit 1.9.129 über den Baustein, D17)", "kopf", ['id="concernAlert"', "offeneBedenkenZeigen('concernAlert',orderId)"]),
    ("Auftrag", "E-Mail Auftragsbestätigung: An, CC, Senden, Versandverlauf, Zustellung nachtragen", "vertrag",
     ['id="orderEmailInput"', 'id="orderCcInput"', "/send-email`", "renderDispatchHistory('orderDispatchHistory','auftrag'"]),
    ("Auftrag", "LV: Menge, Einheit, EP je Position (seit 1.9.129 im Dialog)", "leistungen",
     ['id="itemDialog"', 'data-klick="position-bearbeiten"', "/items/${editItemId}`,{method:'PUT'"]),
    ("Auftrag", "LV-Titel bearbeiten", "leistungen", ['id="sectionDialog"', 'data-klick="titel-bearbeiten"', "/sections/${editSectionId}`"]),
    ("Auftrag", "„+ Nachtrag“, Nachtrag entfernen", "leistungen", ["openAddendum()", "/items`,{method:'POST'", "removeAddendum()"]),
    ("Auftrag", "Sperrhinweis des LV", "leistungen", ['id="lvLock"', "order.order_lock"]),
    ("Auftrag", "Auftragsdaten: alle Felder mit Vorlagen, speichern", "vertrag",
     ['id="auftragsdatenDialog"', 'id="orderIntroTemplate"', 'id="orderOutroTemplate"', 'id="orderOutro2Template"',
      "api('/api/orders/'+orderId,{method:'PUT'"]),
    ("Auftrag", "Steuerschlüssel", "vertrag", ['id="taxKey"', "/tax-key`"]),
    ("Auftrag", "Vertragsgrundlage ändern, Historie", "vertrag", ['id="contractBasisSelect"', "changeContractBasis()", "/contract-basis-changes`"]),
    ("Auftrag", "Vertrag: Entwurf, Festschreiben, Fassungen, Versand, Papier, neue Fassung", "vertrag",
     ['id="contractBody"', "/contract/freeze`", "/contract/send-email`", "/contract/sign-paper`", "/contract/new-version`"]),
    ("Auftrag", "Vertrag auf dem Gerät unterschreiben", "vertrag", ['id="signDialog"', "/contract/sign`"]),
    ("Auftrag", "Gewährleistung: Vorschlag, abweichend", "vertrag", ['id="warrantyCard"', "/warranty-preview"]),
    ("Auftrag", "Abnahme: erfassen, verwerfen, aus dem Protokoll", "abnahme",
     ['id="acceptanceCard"', 'id="acceptanceDialog"', "/acceptance-from-protocol", "/api/order-acceptances/${id}/discard"]),
    ("Auftrag", "Mängel: erfassen, Haltung, Freigabe, Status, Fotos, Belege, verwerfen", "abnahme",
     ['id="defectCard"', 'id="defectDialog"', "/stance", "/release", "/api/defects/${id}/status", "/photos", "/receipts"]),
    ("Auftrag", "Checklisten starten und öffnen", "ausfuehrung", ['id="checklistSection"', "renderChecklistSection('checklistSection','auftrag'"]),
    ("Auftrag", "Auftragsstände: Revision sichern, Liste", "leistungen", ['id="revisionReason"', "saveRevision()", 'id="revisions"']),
    ("Auftrag", "Auftragssumme", "leistungen", ["Auftragssumme netto", "order.net_total"]),
    ("Auftrag", "Abrechnungsstand netto/brutto", "uebersicht", ['id="uLeistung"', 'id="uZahlung"']),
    ("Auftrag", "Rechnungen: Liste, „Neue Rechnung“ je Art", "rechnungen",
     ['id="newInvoiceType"', "/invoices/abschlag-pauschal", "/invoices/abschlag-leistungsstand", "/invoices/schlussrechnung",
      "/invoices/aus-zeitbuchungen"]),
    ("Auftrag", "Entwurf einer Rechnung löschen", None,
     ["D17: gelöscht wird ein Entwurf auf seiner Rechnungsseite (DELETE /api/invoices/{id}), nicht mehr aus der Liste"]),
]


def test_liste_vollstaendig():
    seiten = {s: [f for f in FUNKTIONEN if f[0] == s] for s in ("Projektmappe", "Auftrag")}
    assert len(seiten["Projektmappe"]) >= 20 and len(seiten["Auftrag"]) >= 24
    assert [f[1] for f in FUNKTIONEN if f[2] is None] == ["Entwurf einer Rechnung löschen"]


@pytest.mark.parametrize("rolle", ("buero_finanzen", "admin"))
def test_jede_funktion_der_alten_seiten_erreichbar(rolle, threaded_db_session, router_test_client):
    text = _akte(router_test_client(threaded_db_session, pages_router, role=rolle))
    fehlt = [(alt, funktion, beleg) for alt, funktion, reiter, belege in FUNKTIONEN if reiter for beleg in belege if beleg not in text]
    assert fehlt == []
    reiter = set(re.findall(r'data-reiter="([a-z]+)"', text))
    assert reiter == {"uebersicht", "angebote", "vertrag", "leistungen", "ausfuehrung", "abnahme", "rechnungen", "dateien", "verlauf"}
    assert {f[2] for f in FUNKTIONEN if f[2]} - {"kopf"} <= reiter


def test_buero_auftrag_sieht_geld_ohne_knoepfe(threaded_db_session, router_test_client):
    """Ausblenden statt ausgrauen: ohne darf_geld() kein „Rechnung anlegen“ und kein „Entwurf anlegen“, dafür der Hinweis."""
    text = _akte(router_test_client(threaded_db_session, pages_router, role="buero_auftrag"))
    markup = _ohne_skript(text)
    assert [x for x in ('id="neueRechnung"', 'id="newInvoiceType"', 'id="uNaechste"', 'data-klick="naechste-rechnung"') if x in markup] == []
    assert "data-geld-nur-lesen" in markup and 'id="uAbrechnung"' in markup and 'id="invoicesList"' in markup
    assert 'const GELD="nein"!=="nein";' in text
    voll = _ohne_skript(_akte(router_test_client(threaded_db_session, pages_router, role="buero_finanzen")))
    assert 'id="neueRechnung"' in voll and "data-geld-nur-lesen" not in voll


def test_alte_anker_oeffnen_den_reiter():
    """Lesezeichen und Links der früheren Seiten (#sec-… der Projektmappe, #mangel-… der Auftragsseite) öffnen den passenden Reiter."""
    text = (VORLAGEN / "akte.html").read_text(encoding="utf-8")
    anker = dict(re.findall(r"'(sec-[a-z]+)':'([a-z]+)'", text))
    assert anker == {"sec-info": "uebersicht", "sec-orders": "uebersicht", "sec-workprep": "ausfuehrung", "sec-times": "ausfuehrung",
                     "sec-quotes": "angebote", "sec-files": "dateien", "sec-invoices": "rechnungen", "sec-calendar": "uebersicht",
                     "sec-participants": "uebersicht", "sec-dispatch": "verlauf", "sec-history": "verlauf"}
    assert "if(/^mangel-\\d+$/.test(h))return 'abnahme';" in text


@pytest.mark.parametrize("datei, link", [
    ("work_preparation.html", "href:'/projects/'+prep.project_id+'?auftrag='+prep.order_id+'#ausfuehrung'"),
    ("service_reports.html", "href:'/projects/'+o.project_id+'?auftrag='+orderId+'#ausfuehrung'"),
    ("service_report.html", "href:'/projects/'+o.project_id+'?auftrag='+R.order_id+'#ausfuehrung'"),
    ("invoice_detail.html", "href:`/projects/${invoice.project_id}?auftrag=${invoice.order_id}#rechnungen`"),
    ("checklist.html", "`/orders/${cl.order_id}#ausfuehrung`"),
    ("checklist_order.html", "href:'/projects/'+o.project_id+'?auftrag='+orderId+'#ausfuehrung'"),
])
def test_rueckwege_fuehren_in_die_akte(datei, link):
    """Die Seiten des Auftrags führen auf den passenden Reiter der Akte zurück -- im Pfad direkt (/projects/<p>?auftrag=<a>#reiter),
    die Checkliste (ohne Projekt in ihren Daten) über /orders/{id}, das weiterleitet."""
    assert link in (VORLAGEN / datei).read_text(encoding="utf-8")


def test_alte_vorlagen_gibt_es_nicht_mehr():
    namen = set(vj.alle_vorlagen())
    assert {"order.html", "project_folder.html"} & namen == set() and "akte.html" in namen
