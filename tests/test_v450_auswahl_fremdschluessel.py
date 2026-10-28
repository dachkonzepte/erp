"""Seit 1.9.16 (Runde 7, Punkt 1): Auswahlfelder für Fremdschlüssel -- ein gespeichertes Ziel, das inzwischen archiviert, inaktiv, nicht
mehr in der Auswahl oder (bei abgeschaltetem Modul) gar nicht in der Liste steht, bleibt vorgewählt und gespeichert, mit Kennzeichen
(„(abgeschlossen)“, „(inaktiv)“, „(archiviert)“, „(nicht mehr in der Auswahl)“ …) -- nie still umgestellt (Befund 1.9.12 B).

Je Feld ein Test, alle bis 1.9.15 rot (falsche oder keine Auswahl); das Seitenskript läuft in node (tests/test_v334_auswahl_restfaelle.py:
seite(), im_browser(); Antworten des Servers als ANTWORTEN):

    Büro-Zeiterfassung      Auftrag der Buchung abgeschlossen bzw. nicht zugeordnet: nachgeladen, gewählt mit Stand, samt LV-Position;
                            Ausweichweg ohne Kontext: die Positionen des Auftrags werden nachgeladen, die LV-Position bleibt
    Meine Zeiten            Einzelbuchung und Kolonnenbuchung: Auftrag außerhalb der Auswahl (±14 Tage) bleibt gewählt (bis 1.9.58 die
                            Zeiterfassung der Monteurin)
    Projektmappe            Objekt eines anderen Kunden (bestätigt) und „kein Objekt“ bleiben beim Öffnen; die Hauptadresse nur beim
                            Kundenwechsel
    Wartungsvertrag         gespeichertes Objekt mit Hauptadresse bleibt gewählt
    Anfrage                 Objekt, das inzwischen einem anderen Kunden gehört, bleibt gewählt (der Server lehnt es sichtbar ab)
    Einsatzbericht          inaktiver Ersteller „(inaktiv)“
    Prüfvorlagen            archivierte Standardvorlage „(archiviert)“
    Eingangsrechnung        Betriebsmittel und Kostenposten: inaktiv gekennzeichnet; bei abgeschaltetem Modul mit dem Namen aus der Rechnung
    Kostenposten            Betriebsmittel bei abgeschaltetem Modul mit dem Namen aus dem Kostenposten (asset_name, Server)
"""

import json

import pytest

from tests.test_v334_auswahl_restfaelle import im_browser, nur_mit_node, seite
from tests.test_v447_auswahl_altwerte import WIRKSAM


def _lauf(vorlage: str, start: str, ablauf: str, antworten: dict | None = None):
    return im_browser(seite(vorlage, start) + WIRKSAM, ablauf, antworten)


def _in_select(ausdruck: str) -> str:
    """JS: wirksame Auswahl eines Options-HTML (wie der Browser)."""
    return f"_wirksam('<select id=\"t\">' + {ausdruck} + '</select>', 'id=\"t\"')"


# --- Seite „Zeiten“, Dialog „Buchung ändern“ (seit 1.9.98; bis 1.9.97 die Büro-Zeiterfassung mit openManual()) ----------------------

ZEITEN_KONTEXT = ("KONTEXT = {orders: ORDERS, employees: [{id: 5, name: 'Max', employee_number: null}], teams: []}; TAETIGKEITEN = []; B = null;")
OFFEN = {"id": 1, "order_number": "AUF-1", "title": "Halle", "geschlossen": None, "items": []}
BUCHUNG = {"id": 9, "employee_id": 5, "employee_name": "Max", "work_date": "2026-10-20", "order_id": 2, "order_number": "AUF-2",
           "order_title": "Lager", "order_item_id": 7, "order_item_oz": "01.01", "entry_type": "site", "zeitart": "Baustelle",
           "activity": None, "hours": "2.00", "break_minutes": 0, "min_break_minutes": 0, "notes": "", "started_at": None, "ended_at": None,
           "booked_by_name": None, "created_at": None}


def _zeiten(auftraege: list, ablauf: str):
    return _lauf("zeiten.html", "binden();", ZEITEN_KONTEXT.replace("ORDERS", json.dumps(auftraege)) + ablauf)


@nur_mit_node
def test_buero_zeiterfassung_auftrag_ausserhalb_der_auswahl():
    """Auftrag der Buchung nicht im Kontext (bis 1.9.15 im Büro: leere Auswahl, Speichern 422 oder Umbuchen): gewählt und gekennzeichnet,
    die LV-Position mit ihrer Ordnungszahl."""
    lauf = _zeiten([OFFEN], f"await buchungDialogOeffnen({json.dumps(BUCHUNG)}); return [_feld('bdAuftrag'), _feld('bdPosition')];")
    assert lauf["ergebnis"] == [["2", "AUF-2 · Lager (nicht mehr in der Auswahl)"], ["7", "01.01 (nicht mehr in der Auswahl)"]]


@nur_mit_node
@pytest.mark.parametrize("stand", ["abgeschlossen", "storniert"])
def test_buero_zeiterfassung_geschlossener_auftrag_gekennzeichnet(stand):
    """Seit 1.9.90 bekommt, wer für andere bucht, die geschlossenen Aufträge im Kontext -- gewählt, mit Kennzeichen, die Position bleibt."""
    zu = {"id": 2, "order_number": "AUF-2", "title": "Lager", "geschlossen": stand, "items": [{"id": 7, "oz": "01.01", "short_text": "Dach"}]}
    lauf = _zeiten([OFFEN, zu], f"await buchungDialogOeffnen({json.dumps(BUCHUNG)}); return [_feld('bdAuftrag'), _feld('bdPosition')];")
    assert lauf["ergebnis"] == [["2", f"AUF-2 · Lager (Auftrag {stand})"], ["7", "01.01 · Dach"]]


@nur_mit_node
def test_buero_zeiterfassung_speichern_behaelt_auftrag_und_position():
    # Von und Bis eingetragen (die Attrappe merkt sich aria-pressed nicht, der Dialog bleibt bei „Von – Bis“)
    lauf = _zeiten([OFFEN], f"await buchungDialogOeffnen({json.dumps(BUCHUNG)}); _element('bdVon').value='07:00'; _element('bdBis').value='09:00';"
                            "await buchungSpeichern();"
                            "return AUFRUFE.filter(a => a.methode === 'PUT').map(a => [a.url, a.body.order_id, a.body.order_item_id, a.body.von]);")
    assert lauf["ergebnis"] == [["/api/time-entries/9", "2", "7", "07:00"]]


@nur_mit_node
def test_buero_zeiterfassung_neue_buchung_wie_bisher():
    """Vergleichsfall: neue Buchung ohne Vorgabe -- leere Auswahl, nur die Aufträge des Kontexts."""
    lauf = _zeiten([OFFEN], "await buchungDialogOeffnen(null); return [_feld('bdAuftrag'), _element('bdAuftrag').options.map(o => o.value)];")
    assert lauf["ergebnis"] == [["", "— Auftrag wählen —"], ["", "1"]]


# --- Meine Zeiten (seit 1.9.59, bis dahin die Zeiterfassung der Monteurin) -----------------------------------------------------------

FELD_KONTEXT = ("D = {mitarbeiter_id: 5, abgeschlossen_bis: null, taetigkeiten: [], kolonnen_buchungen: [],"
                " auftraege: [{id: 1, order_number: 'AUF-1', customer_name: 'Kunde', property_address: null}],"
                " zeitarten: [{value: 'site', label: 'Baustelle'}], kolonnen: [{team_id: 3, name: 'Kolonne', members: []}]};")
ZEILE = {"id": 9, "work_date": "2026-10-20", "order_id": 2, "order_number": "AUF-2", "project_name": "Lager", "entry_type": "site",
         "zeitart": "Baustelle", "activity": None, "notes": "", "von": None, "bis": None, "gebucht": "5.00", "pause": 0}


@nur_mit_node
def test_monteur_einzelbuchung_auftrag_ausserhalb_der_auswahl():
    """Auftrag der Buchung außerhalb von ±14 Tagen (bis 1.9.15: „— Auftrag wählen —“, Speichern verlangte Umbuchen)."""
    ablauf = FELD_KONTEXT + f"zeitDialogOeffnen({json.dumps(ZEILE)}); return _feld('zdAuftrag');"
    assert _lauf("mobil_zeiten.html", "binden();", ablauf)["ergebnis"] == ["2", "AUF-2 · Lager (nicht mehr in der Auswahl)"]


@nur_mit_node
def test_monteur_kolonnenbuchung_auftrag_ausserhalb_der_auswahl():
    gruppe = {"id": 4, "order_id": 2, "order_number": "AUF-2", "members": [{"name": "Max"}], "work_date": "2026-10-20", "hours": "8",
              "entry_type": "site", "activity": None, "notes": ""}
    ablauf = FELD_KONTEXT + f"kolonneDialogOeffnen({json.dumps(gruppe)}); return _feld('kdAuftrag');"
    assert _lauf("mobil_zeiten.html", "binden();", ablauf)["ergebnis"] == ["2", "AUF-2 (nicht mehr in der Auswahl)"]


@nur_mit_node
def test_monteur_neue_buchung_ohne_vorgabe_ausserhalb():
    """Vergleichsfall: eine neue Buchung schlägt keinen Auftrag außerhalb der Auswahl vor."""
    ablauf = FELD_KONTEXT + "zeitDialogOeffnen(null); return _feld('zdAuftrag');"
    assert _lauf("mobil_zeiten.html", "binden();", ablauf)["ergebnis"] == ["", "— Auftrag wählen —"]


# --- Projektmappe --------------------------------------------------------------------------------------------------------------------

def _projekt(property_id, property_name):
    projekt = {"id": 1, "project_number": "P-1", "name": "Halle", "status": "anfrage", "category": None, "description": "",
               "customer_id": 1, "property_id": property_id, "property_name": property_name}
    antworten = {"/api/properties?customer_id=1": [{"id": 3, "name": "Hauptadresse", "postal_code": "52531", "city": "Übach",
                                                     "customer_id": 1}]}
    ablauf = (f"project = {json.dumps(projekt)}; customers = [{{id: 1, customer_number: 'K-1', name: 'Kunde'}}]; projectCategories = [];"
              "try { await openProjectEdit(); } catch (e) { if (!_gewaehlt('editProperty')) throw e; } return _feld('editProperty');")
    return _lauf("akte.html", "akteStarten().catch(", ablauf, antworten)["ergebnis"]


@nur_mit_node
def test_projektmappe_objekt_eines_anderen_kunden_bleibt():
    """Bestätigtes Objekt eines anderen Kunden (bis 1.9.15: still die Hauptadresse, das nächste Speichern schrieb sie)."""
    assert _projekt(5, "Halle Süd") == ["5", "Halle Süd (Objekt eines anderen Kunden)"]


@nur_mit_node
def test_projektmappe_kein_objekt_bleibt():
    assert _projekt(None, None) == ["", "— kein Objekt —"]


@nur_mit_node
def test_projektmappe_hauptadresse_nur_beim_kundenwechsel():
    """Vergleichsfall: wechselt der Kunde im Dialog, schlägt die Liste dessen Hauptadresse vor (wie bisher)."""
    antworten = {"/api/properties?customer_id=2": [{"id": 8, "name": "Hauptadresse", "postal_code": "1", "city": "X", "customer_id": 2}]}
    ablauf = ("project = {property_name: null}; _element('editCustomer').value = '2'; await loadEditProperties();"
              "return _feld('editProperty');")
    assert _lauf("akte.html", "akteStarten().catch(", ablauf, antworten)["ergebnis"] == ["8", "Hauptadresse · 1 X"]


# --- Wartungsvertrag -----------------------------------------------------------------------------------------------------------------

@nur_mit_node
def test_wartungsvertrag_objekt_mit_hauptadresse_bleibt():
    """Gespeichertes Objekt mit Hauptadresse (bis 1.9.15: fehlte in der Liste -- „Hauptadresse verwenden“, Speichern null oder 422)."""
    ablauf = ("properties = [{id: 3, customer_id: 1, is_primary_address: true, name: 'Hauptadresse'},"
              " {id: 4, customer_id: 1, is_primary_address: false, name: 'Halle'}]; customers = [{id: 1, name: 'Kunde'}];"
              f"return [{_in_select('propertyOptionsHtml(1, 3, false)')}, {_in_select('propertyOptionsHtml(1, null, false)')}];")
    assert _lauf("maintenance_contract.html", "\ninit();", ablauf)["ergebnis"] == [["3", "Hauptadresse"],
                                                                                   ["", "— Hauptadresse verwenden —"]]


# --- Anfrage ---------------------------------------------------------------------------------------------------------------------------

@nur_mit_node
def test_anfrage_objekt_eines_anderen_kunden_bleibt():
    """Objekt nachträglich einem anderen Kunden zugeordnet (bis 1.9.15: still „Kein Objekt“); nach einem Kundenwechsel im Dialog die
    Liste des neuen Kunden ohne Auswahl (Vergleich)."""
    ablauf = ("properties = [{id: 3, customer_id: 1, name: 'Hauptadresse', street: 'Weg 1', postal_code: '1', city: 'X'},"
              " {id: 5, customer_id: 2, name: 'Halle Süd', street: '', postal_code: '', city: ''}];"
              "currentInquiry = {customer_id: 1, property_id: 5, property_name: 'Halle Süd'};"
              "_element('editCustomer').value = '1'; loadEditProperties(); const vorher = _feld('editProperty');"
              "_element('editCustomer').value = '2'; loadEditProperties(); return [vorher, _feld('editProperty')];")
    assert _lauf("inquiries.html", "\ninit();", ablauf)["ergebnis"] == [["5", "Halle Süd (gehört nicht mehr zum Kunden)"],
                                                                        ["", "Kein Objekt"]]


# --- Einsatzbericht, Prüfvorlagen, Eingangsrechnung, Kostenposten -----------------------------------------------------------------

@nur_mit_node
def test_einsatzbericht_inaktiver_ersteller():
    """Inaktiver Ersteller (bis 1.9.15: „— nicht zugeordnet —“); neu angeboten nur aktive."""
    ablauf = ("employees = [{id: 1, first_name: 'Max', last_name: 'Alt', active: false}, {id: 2, first_name: 'Eva', last_name: 'Neu',"
              " active: true}];"
              f"return [{_in_select('employeeOptionsHtml(1, \"Max Alt\")')}, employeeOptionsHtml(null).includes('value=\"1\"')];")
    assert _lauf("service_reports.html", "\ninit();", ablauf)["ergebnis"] == [["1", "Max Alt (inaktiv)"], False]


@nur_mit_node
def test_pruefvorlagen_archivierte_standardvorlage():
    """Archivierte Standardvorlage eines Dachtyps (bis 1.9.15: „— keine —“); neu angeboten nur aktive."""
    ablauf = ("templates = [{id: 4, label: 'Flachdach alt', archived: true}, {id: 5, label: 'Flachdach', archived: false}];"
              f"return [{_in_select('defaultTemplateOptionsHtml(4, \"Flachdach alt\")')}, defaultTemplateOptionsHtml(null).includes('value=\"4\"')];")
    assert _lauf("inspection_templates.html", "\ninit();", ablauf)["ergebnis"] == [["4", "Flachdach alt (archiviert)"], False]


@nur_mit_node
@pytest.mark.parametrize("liste,soll", [("[]", ["8", "Kran (nicht in der Auswahl)"]),
                                        ("[{id: 8, name: 'Kran', active: false}]", ["8", "Kran (inaktiv)"])])
def test_eingangsrechnung_betriebsmittel(liste, soll):
    """Modul abgeschaltet (Liste leer; bis 1.9.15: „— kein Betriebsmittel —“, Speichern null) und inaktiv (bis 1.9.15 ohne Kennzeichen)."""
    ablauf = f"assets = {liste}; return {_in_select('assetOptionsHtml(8, \"Kran\")')};"
    assert _lauf("incoming_invoices.html", "\ninit();", ablauf)["ergebnis"] == soll


@nur_mit_node
@pytest.mark.parametrize("liste,soll", [("[]", ["3", "Wartung Kran (nicht in der Auswahl)"]),
                                        ("[{id: 3, label: 'Wartung Kran', active: false}]", ["3", "Wartung Kran (inaktiv)"])])
def test_eingangsrechnung_kostenposten(liste, soll):
    ablauf = f"recurringCosts = {liste}; return {_in_select('recurringCostOptionsHtml(3, \"Wartung Kran\")')};"
    assert _lauf("incoming_invoices.html", "\ninit();", ablauf)["ergebnis"] == soll


@nur_mit_node
def test_kostenposten_betriebsmittel_bei_abgeschaltetem_modul():
    ablauf = f"assets = []; return {_in_select('assetOptionsHtml(8, \"Kran\")')};"
    assert _lauf("recurring_costs.html", "\ninit();", ablauf)["ergebnis"] == ["8", "Kran (nicht in der Auswahl)"]


def test_kostenposten_liefert_den_namen_des_betriebsmittels(db_session):
    """Server: cost_to_dict() nennt das Betriebsmittel (asset_name) -- die Auswahl braucht ihn bei abgeschaltetem Modul."""
    from decimal import Decimal

    from app.models import OperationalAsset, RecurringCost
    from app.recurring_costs import cost_to_dict

    asset = OperationalAsset(name="Kran 25 t", asset_type="Kran", active=False)
    db_session.add(asset)
    db_session.flush()
    kosten = RecurringCost(label="Wartung Kran", category="Wartung", net_amount=Decimal("100.00"), tax_rate_pct=Decimal("19.00"),
                           billing_interval="monatlich", annual_amount=Decimal("1200.00"), asset_id=asset.id)
    db_session.add(kosten)
    db_session.commit()
    db_session.refresh(kosten)
    zeile = cost_to_dict(kosten, 30)
    assert zeile["asset_id"] == asset.id and zeile["asset_name"] == "Kran 25 t"
    assert cost_to_dict(RecurringCost(label="x", net_amount=Decimal("1"), tax_rate_pct=Decimal("19")), 30)["asset_name"] is None
