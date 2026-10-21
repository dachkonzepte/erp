"""Seit 1.9.12 (Stufe 2, Runde 6, Punkt 1): Auswahlfelder mit gespeichertem Text -- ein Wert außerhalb der Liste bleibt vorgewählt und
erhalten, wie beim Dachtyp (1.9.6) und den Auswahllisten aus Stammdaten (1.8.30, Regel 22).

Je Feld ein Test (alle bis 1.9.11 rot): das Seitenskript läuft in node (tests/test_v334_auswahl_restfaelle.py: seite(), im_browser()), der
gespeicherte Wert steht nicht in der Liste (umbenannt, gelöscht, andere Schreibweise oder aus einem zweiten Schreibweg) -- danach ist genau
er gewählt, beschriftet „<wert> (nicht mehr verfügbar)“ (bzw. „(inaktiv)“ für einen abgeschalteten Eintrag einer Optionsgruppe), und das
Feld liefert ihn beim Speichern unverändert. Feste Listen im Markup liest der Test aus der Vorlage selbst (statische Optionen)."""

import json
import re
from pathlib import Path

import pytest

from tests.test_v334_auswahl_restfaelle import im_browser, nur_mit_node, seite

TEMPLATES = Path(__file__).resolve().parent.parent / "app" / "templates"

# Wirksame Auswahl in einem HTML-Stück (die als selected markierte Option, sonst die erste -- wie der Browser), je <select>, das zum
# regulären Ausdruck passt
WIRKSAM = r"""
function _wirksam(html, kopf) {
  const m = new RegExp('<select[^>]*' + kopf + '[^>]*>([\\s\\S]*?)</select>').exec(String(html));
  if (!m) return null;
  const opt = _optionen(m[1]);
  const o = opt.find(x => x.selected) || opt[0];
  return o ? [o.value, o.text] : null;
}
function _feld(id) { const o = _gewaehlt(id); return o ? [o.value, o.text] : null; }
"""


def statisch(vorlage: str, feld_id: str) -> str:
    """JS-Anweisung: die Optionen des <select id=feld_id> aus dem Markup der Vorlage in die Attrappe setzen."""
    text = (TEMPLATES / vorlage).read_text(encoding="utf-8")
    m = re.search(r'<select[^>]*\bid="' + re.escape(feld_id) + r'"[^>]*>(.*?)</select>', text, flags=re.S)
    assert m, (vorlage, feld_id)
    return f"_element({json.dumps(feld_id)}).innerHTML = {json.dumps(m.group(1))};"


def lauf(vorlage: str, start: str, ablauf: str):
    return im_browser(seite(vorlage, start) + WIRKSAM, ablauf)["ergebnis"]


GRUPPE = [{"value": "Fahrzeug", "label": "Fahrzeug", "active": True}, {"value": "Anhänger", "label": "Anhänger", "active": True},
          {"value": "Kran", "label": "Kran", "active": False}]


# --- A: echte Fehler ---------------------------------------------------------------------------------------------------------------

@nur_mit_node
@pytest.mark.parametrize("gespeichert,soll", [("Leiter", ["Leiter", "Leiter (nicht mehr verfügbar)"]),
                                              ("Kran", ["Kran", "Kran (inaktiv)"]), ("Anhänger", ["Anhänger", "Anhänger"])])
def test_betriebsmittel_typ(gespeichert, soll):
    asset = {"id": 1, "resource_id": None, "asset_type": gespeichert, "name": "Anlegeleiter", "active": True, "inspections": [],
             "documents": []}
    ablauf = f"assetTypes = {json.dumps(GRUPPE)}; resources = []; asset = {json.dumps(asset)}; fillEditor(); return _feld('editType');"
    assert lauf("operational_asset.html", "\ninit();", ablauf) == soll


@nur_mit_node
def test_betriebsmittel_typ_leer_bleibt_leer():
    asset = {"id": 1, "resource_id": None, "asset_type": None, "name": "x", "active": True, "inspections": [], "documents": []}
    ablauf = f"assetTypes = {json.dumps(GRUPPE)}; resources = []; asset = {json.dumps(asset)}; fillEditor(); return _feld('editType');"
    assert lauf("operational_asset.html", "\ninit();", ablauf)[0] == ""


@nur_mit_node
def test_betriebsmittel_pruefungsart_auch_nach_neu_laden_beim_bearbeiten():
    insp = {"id": 5, "inspection_type": "TÜV alt", "interval_months": 12, "last_inspection_date": None, "next_due_date": None,
            "inspector": None, "notes": None}
    asset = {"id": 1, "resource_id": None, "asset_type": "Fahrzeug", "name": "x", "active": True, "inspections": [insp], "documents": []}
    ablauf = (f"assetInspectionTypes = {json.dumps(GRUPPE)}; asset = {json.dumps(asset)}; renderInspections();"
              "editingInspectionId = 5; fillInspectionForm(asset.inspections[0]); const nach_dem_oeffnen = _feld('inspType');"
              "renderInspections(); return [nach_dem_oeffnen, _feld('inspType')];")
    assert lauf("operational_asset.html", "\ninit();", ablauf) == [["TÜV alt", "TÜV alt (nicht mehr verfügbar)"]] * 2


@nur_mit_node
def test_betriebskosten_kategorie():
    cost = {"id": 3, "label": "Versicherung", "category": "Versicherung alt", "overhead_classification": "keine", "tax_rate_pct": "19.00",
            "billing_interval": "monatlich", "active": True, "net_amount": "10.00", "documents": []}
    ablauf = (f"categories = {json.dumps(GRUPPE)}; costs = [{json.dumps(cost)}]; assets = []; openEditEditor(3);"
              "return _feld('editCategory');")
    assert lauf("recurring_costs.html", "\ninit();", ablauf) == ["Versicherung alt", "Versicherung alt (nicht mehr verfügbar)"]


ORDER = {"id": 1, "order_number": "AUF-1", "title": "T", "status": "beauftragt", "order_date": "2026-10-01", "items": [], "sections": [],
         "payment_terms": None, "intro_text": "", "outro_text": "", "vat_rate": "19", "tax_key_id": None}


@nur_mit_node
@pytest.mark.parametrize("gespeichert,soll", [("alternativ", ["alternativ", "Alternative"]),  # so legt der Angebots-Editor sie an
                                              ("alternative", ["alternative", "alternative (nicht mehr verfügbar)"])])
def test_auftrag_positionsart(gespeichert, soll):
    item = {"id": 7, "short_text": "Pos", "long_text": "", "quantity": "1", "unit": "Stk", "unit_price": "1.00", "position_type": gespeichert,
            "gaeb_oz": None, "include_in_total": True, "is_addendum": False, "position_number": "1"}
    order = dict(ORDER, items=[item])
    ablauf = (statisch("order.html", "iType") + f"order = {json.dumps(order)}; units = []; openItem(7); return _feld('iType');")
    assert lauf("order.html", "load().catch(e=>document.querySelector('main')", ablauf) == soll


@nur_mit_node
def test_auftrag_status():
    ablauf = (statisch("order.html", "status") + f"order = {json.dumps(dict(ORDER, status='unterbrochen'))};"
              "try { fill(); } catch (e) { if (!_gewaehlt('status')) throw e; } return _feld('status');")
    assert lauf("order.html", "load().catch(e=>document.querySelector('main')", ablauf) == ["unterbrochen",
                                                                                           "unterbrochen (nicht mehr verfügbar)"]


@nur_mit_node
@pytest.mark.parametrize("gespeichert,soll", [("Telefon", ["Telefon", "Telefon (nicht mehr verfügbar)"]),  # aus dem Stammdatenformular
                                              ("email", ["email", "E-Mail"])])
def test_kunde_zusatzinfo_art(gespeichert, soll):
    ablauf = (f"customer = {{extra_infos: [{{id: 1, info_type: {json.dumps(gespeichert)}, label: null, value: '0241 1'}}]}};"
              "renderExtras(); return _wirksam(_element('extras').innerHTML, 'class=\"xt\"');")
    assert lauf("customer.html", "load().catch(", ablauf) == soll


def test_stammdatenformular_legt_zusatzinfos_mit_den_schluesseln_der_kundenakte_an():
    """Der zweite Schreibweg: das Formular „Kunde anlegen“ schrieb die Bezeichnungen (Telefon, E-Mail …) statt der Schlüssel, die die
    Kundenakte anbietet (phone, email …)."""
    text = (TEMPLATES / "master_data_form.html").read_text(encoding="utf-8")
    auswahl = re.search(r'<select class="etype">(.*?)</select>', text).group(1)
    assert re.findall(r'value="([^"]*)"', auswahl) == ["phone", "email", "birthday", "info"]


@nur_mit_node
@pytest.mark.parametrize("gespeichert,soll", [("angebot", ["angebot", "Angebot"]),  # schreibt die Umwandlung einer Anfrage
                                              ("ruht", ["ruht", "ruht (nicht mehr verfügbar)"])])
def test_projekt_status(gespeichert, soll):
    project = {"id": 2, "project_number": "P-1", "name": "N", "status": gespeichert, "description": "", "customer_id": None,
               "property_id": None, "category": None}
    ablauf = (statisch("project_folder.html", "editProjectStatus") + f"project = {json.dumps(project)};"
              "try { await openProjectEdit(); } catch (e) {} return _feld('editProjectStatus');")
    assert lauf("project_folder.html", "load().catch(e=>document.querySelector('main')", ablauf) == soll


VERSION = {"fields": [{"field_key": "farbe", "field_type": "auswahl", "label": "Farbe", "options": [{"option_key": "rot", "label": "Rot"}]}]}


@nur_mit_node
def test_checklisten_regel_operand():
    r = {"id": 1, "operator": "enthaelt", "field_key": "farbe", "operand": "blau", "task_title": "", "task_priority": "normal",
         "assignee_mode": "rolle", "min_visible_role": "buero_auftrag"}
    ablauf = f"version = {json.dumps(VERSION)}; return _wirksam(ruleForm({json.dumps(r)}), 'data-r=\"operand\"');"
    assert lauf("checklist_template.html", "\ninit();", ablauf) == ["blau", "blau (nicht mehr verfügbar)"]


@nur_mit_node
def test_checklisten_regel_feld():
    r = {"id": 1, "operator": "enthaelt", "field_key": "groesse", "operand": None, "task_title": "", "task_priority": "normal",
         "assignee_mode": "rolle", "min_visible_role": "buero_auftrag"}
    ablauf = f"version = {json.dumps(VERSION)}; return _wirksam(ruleForm({json.dumps(r)}), 'data-r=\"field_key\"');"
    assert lauf("checklist_template.html", "\ninit();", ablauf) == ["groesse", "groesse (nicht mehr verfügbar)"]


# --- A: feste Listen, die der Server nicht erzwingt -------------------------------------------------------------------------------

@nur_mit_node
def test_einstellungen_schichttyp_auswahlliste():
    t = {"id": 4, "key": "daemmung", "label": "Dämmung", "roof_type": None, "option_group": "layer_alt", "has_execution": True,
         "has_thickness": False, "has_notes": True, "active": True}
    ablauf = (f"optionGroups = [{{group_key: 'layer_daemmung', label: 'Dachaufbau – Dämmung'}}]; roofTypeGroup = {{options: []}};"
              f"roofLayerTypes = [{json.dumps(t)}]; populateRoofLayerTypeSelects(); editRoofLayerType(4);"
              "return _feld('roofLayerTypeOptionGroup');")
    assert lauf("settings.html", "load().catch(e=>alert(", ablauf) == ["layer_alt", "layer_alt (nicht mehr verfügbar)"]


@nur_mit_node
def test_plantafel_status():
    slot = {"id": 1, "status": "unterbrochen", "project_number": "P-1", "order_number": "A-1", "team_id": None, "start_date": "2026-10-01",
            "end_date": "2026-10-02", "planned_hours": "8", "travel_hours_per_employee_day": "0", "notes": "", "project_name": "N",
            "customer_name": "K", "conflicts": []}
    ablauf = (statisch("planning.html", "editStatus") + f"board = {{slots: [{json.dumps(slot)}], teams: [], employees: []}};"
              "globalThis.editDialog = _element('editDialog');"  # im Browser über die id als Name erreichbar
              "openEdit(1); return _feld('editStatus');")
    assert lauf("planning.html", "\nloadBoard();", ablauf) == ["unterbrochen", "unterbrochen (nicht mehr verfügbar)"]


PREP = {"id": 1, "order_id": 1, "status": "storniert", "materials": [], "tasks": [], "delivery_notes": [], "teams": [], "employees": []}


@nur_mit_node
def test_arbeitsvorbereitung_status():
    ablauf = (statisch("work_preparation.html", "prepStatus") + f"prep = {json.dumps(PREP)};"
              "try { render(); } catch (e) { if (!_gewaehlt('prepStatus')) throw e; } return _feld('prepStatus');")
    assert lauf("work_preparation.html", "async function load(){", ablauf) == ["storniert", "storniert (nicht mehr verfügbar)"]


@nur_mit_node
def test_arbeitsvorbereitung_material_status():
    material = {"id": 9, "status": "zurueckgestellt", "article_number": "", "name": "Bahn", "source_position": "", "source_short_text": "",
                "quantity": "1", "unit": "m", "supplier_id": None, "supplier_name": None, "delivery_note_id": None, "notes": ""}
    ablauf = (f"prep = {json.dumps(dict(PREP, materials=[material]))}; renderMaterials();"
              "return _wirksam(_element('materialRows').innerHTML, 'id=\"mstatus-9\"');")
    assert lauf("work_preparation.html", "async function load(){", ablauf) == ["zurueckgestellt", "zurueckgestellt (nicht mehr verfügbar)"]


@nur_mit_node
@pytest.mark.parametrize("kopf,soll", [('id="tstatus-3"', ["wartet", "wartet (nicht mehr verfügbar)"]),
                                       ('id="tprio-3"', ["mittel", "mittel (nicht mehr verfügbar)"])])
def test_arbeitsvorbereitung_aufgabe(kopf, soll):
    aufgabe = {"id": 3, "status": "wartet", "priority": "mittel", "title": "T", "due_date": None, "employee_id": None}
    ablauf = (f"prep = {json.dumps(dict(PREP, tasks=[aufgabe]))}; renderTasks();"
              f"return _wirksam(_element('taskRows').innerHTML, {json.dumps(kopf)});")
    assert lauf("work_preparation.html", "async function load(){", ablauf) == soll


@nur_mit_node
def test_aufgabe_prioritaet():
    task = {"id": 4, "title": "T", "description": "", "status": "offen", "priority": "mittel", "due_date": None,
            "assigned_employee_id": None, "project_id": None}
    ablauf = (statisch("tasks.html", "editPriority") + f"tasks = [{json.dumps(task)}]; employees = []; projects = [];"
              "try { openEditor(4); } catch (e) { if (!_gewaehlt('editPriority')) throw e; } return _feld('editPriority');")
    assert lauf("tasks.html", "\ninit();", ablauf) == ["mittel", "mittel (nicht mehr verfügbar)"]


@nur_mit_node
def test_angebot_positionsart():
    ablauf = (statisch("quote_editor.html", "iType") + "currentItem = {id: 5, position_type: 'pauschal', short_text: 'x', quantity: 1,"
              " unit: 'Stk', unit_price: 1}; try { fillItemEditor(); } catch (e) { if (!_gewaehlt('iType')) throw e; }"
              " return _feld('iType');")
    assert lauf("quote_editor.html", "load().catch(", ablauf) == ["pauschal", "pauschal (nicht mehr verfügbar)"]


@nur_mit_node
def test_angebot_status():
    quote = {"id": 1, "status": "zurueckgestellt", "title": "x", "vat_rate": 19, "items": [], "sections": [], "project_id": 1,
             "quote_number": "A-1", "customer_name": "K", "payment_terms": "", "intro_text": "", "outro_text": "", "outro_text_2": "",
             "contract_basis": "bgb"}
    ablauf = (statisch("quote_editor.html", "hStatus") + "globalThis._dhOpts = {}; globalThis.renderDispatchHistory = () => {};"
              f"quote = {json.dumps(quote)}; existingOrder = null; renderAll(); return _feld('hStatus');")
    assert lauf("quote_editor.html", "load().catch(", ablauf) == ["zurueckgestellt", "zurueckgestellt (nicht mehr verfügbar)"]


# --- Wächter ------------------------------------------------------------------------------------------------------------------------
# Jede Fundstelle des Scanners (tests/vorlagen_auswahl.py: Optionen von Hand mit bedingtem selected, P1; Wertzuweisung an ein <select>,
# P2) mit Klasse und Grund. Ein gespeicherter Text oder eine Zahl, die der Server auch außerhalb der Liste annimmt, gehört NICHT hierher,
# sondern über auswahlOptionen() bzw. auswahlWert() (_auswahl.html). Klassen:
#   server_fest      der Server nimmt nur die Werte der Liste an (Fundstelle der Liste im Grund)
#   ja_nein          Ja/Nein-Auswahl
#   neu              zeigt keinen gespeicherten Wert: Vorgabe für einen neuen Datensatz, Filter, Ziel einer Aktion
#   eigen            eigene, geprüfte Altwert-Behandlung (der gespeicherte Wert bleibt gewählt)
#   fremdschluessel  ID eines Datensatzes -- nicht „gespeicherter Freitext“; bekannte Fehler als „Befund 1.9.12 (B)“ (Archiv)
KLASSEN = {
    ('_abnahme.html', 'P2', 'workKindSelect'): ('server_fest', 'WORK_KINDS'),
    ('_objekt_anderer_kunde.html', 'P1', 'g===p.id'): ('fremdschluessel', 'ID eines Datensatzes; Befund 1.9.12 (B): Objekt mit Hauptadresse fehlt in der Liste des Wartungsvertrags'),
    ('checklist_template.html', 'P1', "(f.signer_mode||'frei')===k"): ('server_fest', 'SIGNER_MODES'),
    ('checklist_template.html', 'P1', 'p.key===r.link_purpose'): ('server_fest', 'PURPOSES, ein unbekannter Zweck wird als „(unbekannt)“ ergänzt'),
    ('checklist_template.html', 'P1', 'p.key===template.purpose'): ('server_fest', 'PURPOSES, ein unbekannter Zweck wird als „(unbekannt)“ ergänzt'),
    ('checklist_template.html', 'P1', "r.assignee_mode==='rolle'"): ('server_fest', 'ASSIGNEE_MODES'),
    ('checklist_template.html', 'P1', "r.assignee_mode==='sachbearbeiter'"): ('server_fest', 'ASSIGNEE_MODES'),
    ('checklist_template.html', 'P1', 'v===r.min_visible_role'): ('server_fest', 'permissions.ROLES'),
    ('checklist_template.html', 'P1', 'v===r.operator'): ('server_fest', 'RULE_OPERATORS'),
    ('checklist_template.html', 'P1', 'v===r.task_priority'): ('server_fest', 'tasks.PRIORITIES'),
    ('checklist_template.html', 'P1', 'v===selected'): ('server_fest', 'FIELD_TYPES, gespeicherte Systemtypen werden ergänzt'),
    ('customer.html', 'P1', 'x.is_default'): ('neu', 'Kategorie eines neuen Dokuments (Vorgabe)'),
    ('customer.html', 'P2', 'docEditCategory'): ('eigen', 'Optionen vorher über auswahlOptionen() mit demselben Wert gebaut'),
    ('dashboard.html', 'P1', 'String(e.id)===selectedTaskEmployeeId'): ('neu', 'Filter'),
    ('email_dispatches.html', 'P2', 'filterType'): ('neu', 'Filter aus der Adresse'),
    ('incoming_invoices.html', 'P1', 'Number(item.tax_rate_pct)===0'): ('server_fest', 'Steuersatz 19/7/0'),
    ('incoming_invoices.html', 'P1', 'Number(item.tax_rate_pct)===19'): ('server_fest', 'Steuersatz 19/7/0'),
    ('incoming_invoices.html', 'P1', 'Number(item.tax_rate_pct)===7'): ('server_fest', 'Steuersatz 19/7/0'),
    ('incoming_invoices.html', 'P1', 'Number(selected)===a.id'): ('fremdschluessel', 'ID eines Datensatzes'),
    ('incoming_invoices.html', 'P1', 'Number(selected)===c.id'): ('fremdschluessel', 'ID eines Datensatzes'),
    ('incoming_invoices.html', 'P2', 'editPaymentStatus'): ('server_fest', 'Zahlstatus der Eingangsrechnung'),
    ('incoming_invoices.html', 'P2', 'editTaxRate'): ('server_fest', 'Steuersatz 19/7/0'),
    ('inquiries.html', 'P1', 'p.id===Number(selected)'): ('fremdschluessel', 'ID eines Datensatzes'),
    ('inquiries.html', 'P2', 'editCustomer'): ('fremdschluessel', 'ID eines Datensatzes'),
    ('inquiries.html', 'P2', 'editPriority'): ('server_fest', 'PRIORITIES der Anfrage'),
    ('inquiries.html', 'P2', 'editProperty'): ('fremdschluessel', 'ID eines Datensatzes'),
    ('inquiries.html', 'P2', 'editStatus'): ('server_fest', 'STATUSES der Anfrage'),
    ('inquiries.html', 'P2', 'newCustomer'): ('neu', 'neue Anfrage'),
    ('inquiries.html', 'P2', 'newProperty'): ('neu', 'neue Anfrage'),
    ('inspection_template.html', 'P1', 'selected===v'): ('server_fest', 'ITEM_TYPES'),
    ('inspection_templates.html', 'P1', 'Number(selected)===t.id'): ('fremdschluessel', 'ID eines Datensatzes'),
    ('inspection_templates.html', 'P1', 'selected===o.value'): ('neu', 'Dachtyp einer neuen Prüfvorlage'),
    ('maintenance_contracts.html', 'P1', 'Number(selected)===c.id'): ('fremdschluessel', 'ID eines Datensatzes'),
    ('maintenance_contracts.html', 'P1', 'Number(selected)===e.id'): ('fremdschluessel', 'ID eines Datensatzes'),
    ('maintenance_contracts.html', 'P1', 'Number(selected)===t.id'): ('fremdschluessel', 'ID eines Datensatzes'),
    ('master_data_form.html', 'P1', 'Number(selected)===f.id'): ('fremdschluessel', 'ID eines Datensatzes'),
    ('master_data_form.html', 'P1', 'x.is_default'): ('neu', 'Kategorie eines neuen Kunden (Vorgabe)'),
    ('master_data_form.html', 'P2', 'compensationType'): ('server_fest', 'hourly/fixed_salary'),
    ('master_data_form.html', 'P2', 'costAllocation'): ('server_fest', 'labor_rate/variable_overhead/excluded'),
    ('master_data_form.html', 'P2', 'customer'): ('fremdschluessel', 'ID eines Datensatzes'),
    ('master_data_form.html', 'P2', 'resourceType'): ('eigen', 'Optionen vorher über auswahlOptionen() mit demselben Wert gebaut'),
    ('order.html', 'P2', 'payment'): ('eigen', 'Zahlungsbedingung: ein gespeicherter Text außerhalb der Liste erscheint als „· bisher“'),
    ('planning.html', 'P1', 'x.id===selected'): ('fremdschluessel', 'ID eines Datensatzes'),
    ('planning.html', 'P2', 'newOrder'): ('neu', 'neuer Einsatz'),
    ('planning.html', 'P2', 'newTeam'): ('neu', 'neuer Einsatz'),
    ('project_folder.html', 'P1', 'r.key===p.role'): ('server_fest', 'project_participants.ROLES, eine fehlende Rolle wird ergänzt'),
    ('project_folder.html', 'P1', 'x.is_default'): ('neu', 'Kategorie eines neuen Dokuments (Vorgabe)'),
    ('project_folder.html', 'P2', 'categoryFilter'): ('neu', 'Filter'),
    ('project_folder.html', 'P2', 'editCustomer'): ('fremdschluessel', 'ID eines Datensatzes'),
    ('project_folder.html', 'P2', 'editProperty'): ('fremdschluessel', 'ID eines Datensatzes; Befund 1.9.12 (B): ohne Objekt still die Hauptadresse, bestätigtes Objekt eines anderen Kunden überschrieben'),
    ('project_form.html', 'P1', 'x.is_default'): ('neu', 'Kategorie eines neuen Projekts (Vorgabe)'),
    ('project_form.html', 'P2', 'customer'): ('neu', 'neues Projekt'),
    ('project_form.html', 'P2', 'property'): ('neu', 'neues Projekt'),
    ('property.html', 'P1', 'o.value===selected'): ('neu', 'Dachtyp beim Anlegen mehrerer Dachflächen'),
    ('quote_editor.html', 'P1', 'Number(selected)===e.id'): ('fremdschluessel', 'ID eines Datensatzes'),
    ('quote_editor.html', 'P1', 'u===current'): ('eigen', 'Einheit: unitOptionsHtml() setzt den gespeicherten Wert vorn in die Liste'),
    ('quote_editor.html', 'P2', 'hContractBasis'): ('server_fest', 'Vertragsgrundlagen'),
    ('quote_editor.html', 'P2', 'iSection'): ('fremdschluessel', 'ID eines Datensatzes'),
    ('quote_editor.html', 'P2', 'oPayment'): ('neu', 'Zahlungsbedingung beim Beauftragen (Vorschlag)'),
    ('quote_editor.html', 'P2', 'sParent'): ('fremdschluessel', 'ID eines Datensatzes'),
    ('quote_form.html', 'P2', 'project'): ('neu', 'neues Angebot'),
    ('recurring_costs.html', 'P1', 'Number(selected)===a.id'): ('fremdschluessel', 'ID eines Datensatzes'),
    ('recurring_costs.html', 'P2', 'editClassification'): ('server_fest', 'Gemeinkosten-Einordnung'),
    ('recurring_costs.html', 'P2', 'editInterval'): ('server_fest', 'Abrechnungsintervall'),
    ('recurring_costs.html', 'P2', 'editTaxRate'): ('server_fest', 'Steuersatz 19/7/0'),
    ('service_reports.html', 'P1', 'Number(selected)===e.id'): ('fremdschluessel', 'ID eines Datensatzes'),
    ('service_reports.html', 'P1', 'Number(selected)===t.id'): ('fremdschluessel', 'ID eines Datensatzes'),
    ('service_reports.html', 'P1', 'draft.roofAreaId===String(a.roof_area_id)'): ('fremdschluessel', 'ID eines Datensatzes'),
    ('service_reports.html', 'P1', 'f.action===k'): ('server_fest', 'findings.ACTIONS'),
    ('service_reports.html', 'P1', 'f.status===k'): ('server_fest', 'findings.STATUSES'),
    ('service_reports.html', 'P1', 'o.value===selected'): ('neu', 'Zeitart und Tätigkeit einer neuen Buchung'),
    ('service_reports.html', 'P2', 'editType'): ('server_fest', 'REPORT_TYPES'),
    ('settings.html', 'P1', '!s.reset_yearly'): ('ja_nein', 'Ja/Nein'),
    ('settings.html', 'P1', 's.reset_yearly'): ('ja_nein', 'Ja/Nein'),
    ('settings.html', 'P2', 'acTaxRate'): ('server_fest', 'Steuersatz des Kontos'),
    ('settings.html', 'P2', 'aiProvider'): ('server_fest', 'AI_PROVIDERS'),
    ('settings.html', 'P2', 'datevTarget'): ('server_fest', 'DATEV-Ziele'),
    ('settings.html', 'P2', 'emailSendMethod'): ('server_fest', 'smtp/graph'),
    ('settings.html', 'P2', 'fixedOverheadMode'): ('server_fest', 'eur/pct'),
    ('settings.html', 'P2', 'functionActive'): ('ja_nein', 'Ja/Nein'),
    ('settings.html', 'P2', 'functionGroup'): ('server_fest', 'gewerblich/kaufmaennisch'),
    ('settings.html', 'P2', 'holidayActive'): ('ja_nein', 'Ja/Nein'),
    ('settings.html', 'P2', 'optionActive'): ('ja_nein', 'Ja/Nein'),
    ('settings.html', 'P2', 'optionDefault'): ('ja_nein', 'Ja/Nein'),
    ('settings.html', 'P2', 'planningState'): ('server_fest', 'Bundesländer'),
    ('settings.html', 'P2', 'rounding'): ('server_fest', 'Rundung der Zeiterfassung'),
    ('settings.html', 'P2', 'smtpEncryption'): ('server_fest', 'Verschlüsselung'),
    ('settings.html', 'P2', 'variableOverheadMode'): ('server_fest', 'eur/pct'),
    ('tasks.html', 'P1', 'String(e.id)===selectedEmployeeId'): ('neu', 'Filter'),
    ('tasks.html', 'P2', 'editStatus'): ('server_fest', 'Spalten der Aufgaben (eine benutzte Spalte lässt sich nicht löschen)'),
    ('time_backoffice.html', 'P2', 'editOrderItem'): ('fremdschluessel', 'ID eines Datensatzes'),
    ('time_backoffice.html', 'P2', 'editProject'): ('fremdschluessel', 'ID eines Datensatzes'),
    ('time_tracking.html', 'P1', 'String(e.id)===String(selected)'): ('fremdschluessel', 'ID eines Datensatzes'),
    ('time_tracking.html', 'P1', 'String(i.id)===String(selected)'): ('fremdschluessel', 'ID eines Datensatzes; Befund 1.9.12 (B): LV-Position im Ausweichweg still auf null'),
    ('time_tracking.html', 'P1', 'String(o.id)===String(selected)'): ('fremdschluessel', 'ID eines Datensatzes; Befund 1.9.12 (B): ein Auftrag außerhalb der Liste erzwingt Umbuchen'),
    ('time_tracking.html', 'P2', 'absenceEmployee'): ('neu', 'neuer Antrag'),
    ('time_tracking.html', 'P2', 'groupOrder'): ('neu', 'Vorgabe aus der Adresse'),
    ('time_tracking.html', 'P2', 'manualEmployee'): ('fremdschluessel', 'ID eines Datensatzes'),
    ('time_tracking.html', 'P2', 'manualOrder'): ('fremdschluessel', 'ID eines Datensatzes; Befund 1.9.12 (B): ein Auftrag außerhalb der Liste erzwingt Umbuchen'),
    ('time_tracking.html', 'P2', 'quickOrder'): ('neu', 'Vorgabe aus der Adresse'),
    ('time_tracking_field.html', 'P1', 'String(o.id)===String(selected)'): ('fremdschluessel', 'ID eines Datensatzes; Befund 1.9.12 (B): ein Auftrag außerhalb der Liste (±14 Tage, offen) erzwingt Umbuchen'),
    ('users.html', 'P2', 'active'): ('ja_nein', 'Ja/Nein'),
    ('users.html', 'P2', 'employee'): ('fremdschluessel', 'ID eines Datensatzes'),
    ('users.html', 'P2', 'role'): ('server_fest', 'permissions.ROLES'),
    ('work_preparation.html', 'P1', 'Number(selected)===x.id'): ('fremdschluessel', 'ID eines Datensatzes'),
}
ERLAUBTE_KLASSEN = {"server_fest", "ja_nein", "neu", "eigen", "fremdschluessel"}


def test_kein_auswahlfeld_fuer_gespeicherte_werte_ohne_auswahloptionen():
    """Jede Fundstelle steht in KLASSEN -- ein neues Auswahlfeld für einen gespeicherten Wert nimmt auswahlOptionen() oder auswahlWert()."""
    from tests.vorlagen_auswahl import alle_fundstellen

    funde = alle_fundstellen()
    neu = [f"{name}:{zeilen[0]} {art} {kennung}" for (name, art, kennung), zeilen in sorted(funde.items())
           if (name, art, kennung) not in KLASSEN]
    assert neu == [], "Auswahlfeld ohne auswahlOptionen()/auswahlWert() (oder in KLASSEN mit Grund einordnen): " + "; ".join(neu)


def test_klassen_ohne_veraltete_eintraege():
    from tests.vorlagen_auswahl import alle_fundstellen

    funde = alle_fundstellen()
    assert sorted(k for k in KLASSEN if k not in funde) == []
    assert {klasse for klasse, _ in KLASSEN.values()} <= ERLAUBTE_KLASSEN
    assert all(grund for _, grund in KLASSEN.values())


def test_eine_auswahlliste_aus_einer_optionsgruppe_zeigt_keinen_gespeicherten_wert_von_hand():
    """Optionen aus einer Optionsgruppe (Einträge mit value/label: o.value, x.is_default) von Hand nur für Neues (Vorgabe) -- ein
    gespeicherter Wert aus einer Optionsgruppe kann umbenannt, abgeschaltet oder gelöscht sein und geht immer über auswahlOptionen()."""
    gruppe = {k: v for k, v in KLASSEN.items() if k[1] == "P1" and (".value" in k[2] or "is_default" in k[2])}
    assert gruppe and all(klasse == "neu" for klasse, _ in gruppe.values()), gruppe


def test_wer_auswahlwert_nutzt_bindet_auswahl_ein():
    from tests import vorlagen_js as vj

    fehlt = [name for name in vj.alle_vorlagen() if name != "_auswahl.html"
             and re.search(r"\bauswahl(Wert|Optionen)\(", (vj.TEMPLATES / name).read_text(encoding="utf-8"))
             and not vj.bindet_ein(name, "_auswahl.html")]
    assert fehlt == []


def test_waechter_findet_beide_bauweisen():
    """Gegenprobe des Scanners an erfundenen Stücken."""
    from tests.vorlagen_auswahl import fundstellen

    text = ("<select id=\"a\"></select><script>const setv=(id,x)=>document.getElementById(id).value=x??'';"
            "x.innerHTML=list.map(o=>`<option value=\"${esc(o.value)}\" ${o.value===sel?'selected':''}>`);"
            "y.innerHTML=`<option value=\"fest\" ${r.s==='fest'?'selected':''}>`;"
            "document.getElementById('a').value=rec.typ; setv('a',rec.art); document.getElementById('a').value='normal';"
            "document.getElementById('a').value=rec.aktiv?'1':'0'; auswahlWert(document.getElementById('a'),rec.typ);</script>")
    assert [(art, k) for art, k, _ in fundstellen("x.html", text)] == [
        ("P1", "o.value===sel"), ("P1", "r.s==='fest'"), ("P2", "a"), ("P2", "a")]


# --- Prüfabfrage für den Server (scripts/pruefabfrage_auswahlwerte.sql) -------------------------------------------------------------

SQL = Path(__file__).resolve().parent.parent / "scripts" / "pruefabfrage_auswahlwerte.sql"


def _liste_im_sql(spalte_anfang: str) -> list[str]:
    """Die feste Liste der Spalte im SQL (IN (...) hinter dem Namen der Spalte)."""
    text = SQL.read_text(encoding="utf-8")
    m = re.search(re.escape(spalte_anfang) + r"[^\n]*\n?[^\n]*?IN \(([^)]*)\)", text)
    assert m, spalte_anfang
    return re.findall(r"'([^']*)'", m.group(1))


def _optionen_der_vorlage(vorlage: str, feld_id: str) -> list[str]:
    text = (TEMPLATES / vorlage).read_text(encoding="utf-8")
    return re.findall(r'value="([^"]*)"', re.search(r'<select[^>]*\bid="' + re.escape(feld_id) + r'"[^>]*>(.*?)</select>', text,
                                                     flags=re.S).group(1))


def _konstante(vorlage: str, name: str) -> list[str]:
    text = (TEMPLATES / vorlage).read_text(encoding="utf-8")
    return re.findall(r"\['([^']*)',", re.search(r"const " + name + r"=\[(.*?)\];", text).group(1))


@pytest.mark.parametrize("spalte,quelle", [
    ("'order_items.position_type", lambda: _optionen_der_vorlage("order.html", "iType")),
    ("'quote_items.position_type", lambda: _optionen_der_vorlage("quote_editor.html", "iType")),
    ("'customer_extra_infos.info_type", lambda: _konstante("customer.html", "ZUSATZINFO_ARTEN")),
    ("'projects.status", lambda: _optionen_der_vorlage("project_folder.html", "editProjectStatus")),
    ("'orders.status", lambda: _optionen_der_vorlage("order.html", "status")),
    ("'quotes.status", lambda: _optionen_der_vorlage("quote_editor.html", "hStatus")),
    ("'planning_slots.status", lambda: _optionen_der_vorlage("planning.html", "editStatus")),
    ("'work_preparations.status", lambda: _optionen_der_vorlage("work_preparation.html", "prepStatus")),
    ("'work_preparation_materials.status", lambda: _konstante("work_preparation.html", "MATERIAL_STATUS")),
    ("'work_preparation_tasks.status", lambda: _konstante("work_preparation.html", "AUFGABE_STATUS")),
    ("'work_preparation_tasks.priority", lambda: _konstante("work_preparation.html", "AUFGABE_PRIO")),
    ("'tasks.priority", lambda: _optionen_der_vorlage("tasks.html", "editPriority")),
])
def test_feste_listen_der_pruefabfrage_wie_auf_den_seiten(spalte, quelle):
    assert _liste_im_sql(spalte) == quelle()


def test_pruefabfrage_nur_lesend():
    text = re.sub(r"--[^\n]*", "", SQL.read_text(encoding="utf-8"))
    anweisungen = [a.strip() for a in text.split(";") if a.strip()]
    assert anweisungen[0] == "BEGIN TRANSACTION READ ONLY" and anweisungen[-1] == "ROLLBACK"
    assert not re.search(r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|GRANT)\b", " ".join(anweisungen[1:-1]), flags=re.I)


def test_pruefabfrage_findet_die_altwerte_unter_postgresql():
    """Die Abfrage läuft unter PostgreSQL (Wegwerf-Schema, Regel 27) über alle Spalten und nennt genau die Werte außerhalb der Listen."""
    from sqlalchemy import text

    from app.models import (Customer, CustomerExtraInfo, OperationalAsset, OperationalAssetInspection, SettingOption, SettingOptionGroup,
                            Task)
    from tests.befund_vor_echtbetrieb import pg_sitzung

    with pg_sitzung("auswahlwerte") as db:
        gruppe = db.query(SettingOptionGroup).filter_by(group_key="resource_types").one()
        optionen = sorted(db.query(SettingOption).filter_by(group_id=gruppe.id), key=lambda o: o.value)
        aktiv, abgeschaltet = optionen[0].value, optionen[1]
        abgeschaltet.active = False
        kunde = Customer(name="K", last_name="K")
        db.add(kunde)
        db.flush()
        geraete = [OperationalAsset(name=n, asset_type=t) for n, t in
                   (("a", aktiv), ("b", "Leiter"), ("c", "Leiter"), ("d", abgeschaltet.value), ("e", aktiv.lower()))]
        db.add_all(geraete)
        db.flush()
        db.add_all([CustomerExtraInfo(customer_id=kunde.id, info_type=t, value="x") for t in ("phone", "Telefon", "Telefon")]
                   + [Task(title="t1", priority="normal"), Task(title="t2", priority="mittel"),
                      OperationalAssetInspection(asset_id=geraete[0].id, inspection_type="TÜV alt")])
        db.commit()
        roh = re.sub(r"--[^\n]*", "", SQL.read_text(encoding="utf-8"))
        anweisungen = [a.strip() for a in roh.split(";") if a.strip()][1:-1]  # ohne BEGIN/ROLLBACK
        conn = db.connection()
        conn.execute(text("SET TRANSACTION READ ONLY"))
        zeilen = [tuple(r) for r in conn.execute(text(anweisungen[0])).all()]
        abgeschaltet_wert = abgeschaltet.value
        db.rollback()
    ergebnis = {(s.split(" ")[0], w, n, h) for s, w, n, h in zeilen}
    assert ergebnis == {
        ("operational_assets.asset_type", abgeschaltet_wert, 1, "inaktiv"),
        ("operational_assets.asset_type", "Leiter", 2, None),
        ("operational_assets.asset_type", aktiv.lower(), 1, f"Schreibweise: {aktiv}"),
        ("operational_asset_inspections.inspection_type", "TÜV alt", 1, None),
        ("customer_extra_infos.info_type", "Telefon", 2, None),
        ("tasks.priority", "mittel", 1, None),
    }
