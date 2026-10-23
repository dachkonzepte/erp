"""Version 1.8.119 -- Zahleneingaben: die Grenzen im Browser sind nicht strenger als die des Servers (Vorgabe vom 16.10.2026, Punkt 6).

Ein Zahlenfeld (Regel 34) hat Grenzen im Markup (data-min, data-max, data-stellen, data-zahl="ganz", required) oder in den Optionen des
Aufrufs, der es liest (zahlFeld()/zahlLesen()). Lehnt der Browser etwas ab, das der Server annimmt, kann man einen gültigen Wert gar nicht
eingeben. Dieser Test gleicht jedes Feld mit Grenzen mit dem Feld des Schemas ab, in das sein Wert geht (Pydantic, live gelesen), und mit
Grenzen im Code, die das Schema nicht zeigt (mit Beleg: die Textstelle muss dort stehen).

ABGLEICH nennt je Feld: Vorlage, Schlüssel im Markup (tests/zahlgrenzen.py::schluessel()), die Leseaufrufe mit Optionen, die Schemafelder,
Grenzen im Code samt Beleg -- oder einen Grund, warum Browser und Server dieselbe Quelle haben. Jedes Feld mit Grenzen und jeder
Leseaufruf mit Grenzen muss genau einmal vorkommen; ein neues Feld gehört in die Tabelle.

Bis 1.8.118 war der Browser an 30 Feldern strenger (Erhebung 16.10.2026, docs/archiv/befund-vor-echtbetrieb.md, "Umsetzung 1.8.119"):
negative Flächen, Mengen und Dauern nahm nur der Server, Geldbeträge mit drei Nachkommastellen ebenso, Obergrenzen (Intervall,
Kündigungsfrist, Baujahr, Jahr des Basiszinssatzes) kannte nur der Browser; jetzt gilt dieselbe Grenze auf beiden Seiten."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

import pytest

from tests import vorlagen_js
from tests.zahlgrenzen import (Grenzen, TEMPLATES, felder_mit_grenzen, grenzen_im_markup, grenzen_im_schema, leseaufrufe_mit_grenzen,
                               optionen_anwenden, strenger)

ROOT = Path(__file__).resolve().parent.parent


def _g(wert, inklusive=True):
    return (Decimal(str(wert)), inklusive)


@dataclass(frozen=True)
class Z:
    vorlage: str
    markup: str | None                 # Schlüssel des Felds im Markup, None: Grenzen nur aus dem Leseaufruf
    schemas: tuple[str, ...] = ()      # "Klasse.feld" in app/schemas.py
    lesen: tuple[str, ...] = ()        # Leseaufrufe mit Optionen, z. B. "zahlFeld('ptDays')"
    code: dict = field(default_factory=dict)       # Grenzen im Code (min/max als (Wert, inklusive), stellen, ganz, pflicht)
    beleg: tuple[str, str] | None = None           # (Datei, Textstelle) für code
    gleich: str | None = None          # Grund, warum Browser und Server dieselbe Quelle haben (kein Vergleich)


ABGLEICH = [
    # -- Abnahme und Gewährleistung
    Z("_abnahme.html", "id=warrantyMonths", ("OrderWarrantyUpdate.warranty_months",)),
    Z("_abnahme.html", "id=warrantyDays", ("OrderWarrantyUpdate.warranty_days",)),
    # -- Checklisten
    Z("checklist.html", "data-feld=${esc(f.label)}", ("ChecklistAnswerWrite.value",),
      gleich="Nachkommastellen, Mindest- und Höchstwert stehen am Feld der Vorlage (decimals, min_value, max_value); Browser und Server "
             "lesen dieselben Werte (app/checklists.py prüft die Antwort gegen das Feld)"),
    Z("checklist_template.html", "data-k=decimals", ("ChecklistTemplateFieldWrite.decimals",),
      code={"min": _g(0), "max": _g(4)}, beleg=("app/checklist_templates.py", "0 <= field.decimals <= 4")),
    Z("checklist_template.html", "data-k=min_count", ("ChecklistTemplateFieldWrite.min_count",),
      code={"min": _g(0)}, beleg=("app/checklist_templates.py", "min_count < 0")),
    Z("checklist_template.html", "data-k=max_count", ("ChecklistTemplateFieldWrite.max_count",),
      code={"min": _g(1), "max": _g(20)}, beleg=("app/checklist_templates.py", "MAX_ATTACHMENTS_PER_FIELD = 20")),
    Z("checklist_template.html", "data-r=due_in_days", ("ChecklistTemplateRuleWrite.due_in_days",),
      code={"min": _g(0), "max": _g(365)}, beleg=("app/checklist_templates.py", "0 <= due_in_days <= 365")),
    # -- Kundenakte
    Z("customer.html", "id=refundLine-${i}", ("CustomerRefundLineIn.amount",)),
    Z("customer.html", "id=restAmount-${p.id}", ("PaymentLineIn.zahlung",)),
    # -- Eingangsrechnungen
    Z("incoming_invoices.html", "id=editNetAmount", ("IncomingInvoiceCreate.net_amount", "IncomingInvoiceUpdate.net_amount"),
      lesen=("zahlFeld('editNetAmount')",)),
    Z("incoming_invoices.html", "id=editSkontoPercent", ("IncomingInvoiceCreate.skonto_percent", "IncomingInvoiceUpdate.skonto_percent")),
    Z("incoming_invoices.html", "data-feld=Netto der Position", ("IncomingInvoiceItemIn.net_amount",)),
    # -- Prüfvorlagen
    Z("inspection_template.html", "data-field=sort_order", ("InspectionTemplateItemUpdate.sort_order",)),
    # -- Rechnung
    Z("invoice_detail.html", "id=reminderEditorPaymentDays", ("ReminderUpdate.payment_days",), lesen=("zahlFeld('reminderEditorPaymentDays')",)),
    Z("invoice_detail.html", "id=${prefix}FeeAmount", ("ReminderChargesUpdate.fee_amount",)),
    Z("invoice_detail.html", "id=pyAmount", ("PaymentCreate.amount",)),
    Z("invoice_detail.html", "id=refundAmount", ("RefundCreate.amount",)),
    Z("invoice_detail.html", None, ("InvoiceHeaderUpdate.lump_sum_net",), lesen=("zahlFeld('pAmount')",)),
    Z("invoice_detail.html", None, ("InvoiceItemCreate.ist_quantity", "InvoiceItemUpdate.ist_quantity"), lesen=("zahlFeld('itIst')",),
      code={"pflicht": True}, beleg=("app/invoices.py", "def update_invoice_item(")),  # null heißt beim Ändern "unverändert"
    Z("invoice_detail.html", None, ("InvoiceItemUpdate.ist_quantity",), lesen=("zahlLesen(value)", "zahlFeld(value)"),
      code={"pflicht": True}, beleg=("app/invoices.py", "def update_invoice_item(")),
    Z("invoice_detail.html", None, ("PaymentLineIn.zahlung", "PaymentLineIn.skonto", "PaymentLineIn.einbehalt", "PaymentChargeLineIn.amount"),
      lesen=("zahlLesen(text)",), code={"pflicht": True}, beleg=("app/templates/invoice_detail.html", "{leer:0,stellen:2,min:0,feld}")),
    # -- Mahnwesen
    Z("mahnwesen.html", "id=editorPaymentDays", ("ReminderUpdate.payment_days",), lesen=("zahlFeld('editorPaymentDays')",)),
    Z("mahnwesen.html", "id=${prefix}FeeAmount", ("ReminderChargesUpdate.fee_amount",)),
    # -- Wartungen
    Z("maintenance_contract.html", "id=editInterval", ("MaintenanceContractUpdate.interval_months",)),
    Z("maintenance_contract.html", "id=itemDuration", ("MaintenanceContractItemCreate.duration_minutes",)),
    Z("maintenance_contracts.html", "id=editInterval", ("MaintenanceContractCreate.interval_months",)),
    Z("project_folder.html", "id=mcIntervalMonths", ("MaintenanceContractFromProjectCreate.interval_months",)),
    # -- Stammdaten
    Z("master_data_form.html", None, ("EmployeeCreate.weekly_hours", "EmployeeUpdate.weekly_hours"), lesen=("zahlFeld('weeklyHours')",)),
    Z("master_data_form.html", None, ("MaterialCatalogCreate.purchase_price", "MaterialCatalogUpdate.purchase_price"),
      lesen=("zahlFeld('purchasePrice')",)),
    # -- Betriebsmittel
    Z("operational_asset.html", "id=editAcqCost", ("OperationalAssetCreate.acquisition_cost", "OperationalAssetUpdate.acquisition_cost")),
    Z("operational_asset.html", "id=editRecurringCost", ("OperationalAssetRecurringCostUpdate.net_amount",)),
    Z("operational_asset.html", "id=inspInterval", ("OperationalAssetInspectionCreate.interval_months", "OperationalAssetInspectionUpdate.interval_months")),
    # -- Auftrag
    Z("order.html", None, ("OrderAddendumCreate.quantity", "OrderItemUpdate.quantity"), lesen=("zahlFeld('iQty')",)),
    Z("order.html", None, ("OrderAddendumCreate.unit_price", "OrderItemUpdate.unit_price"), lesen=("zahlFeld('iPrice')",)),
    Z("order.html", None, ("OrderItemUpdate.quantity", "OrderItemUpdate.unit_price"), lesen=("zahlLesen(value)", "zahlFeld(value)")),
    # -- Plantafel
    Z("planning.html", "id=newPlannedHours", ("PlanningSlotCreate.planned_hours",)),
    Z("planning.html", "id=newTravelHours", ("PlanningSuggestionRequest.travel_hours_per_employee_day", "PlanningSlotCreate.travel_hours_per_employee_day")),
    Z("planning.html", "id=editPlannedHours", ("PlanningSlotUpdate.planned_hours",)),
    Z("planning.html", "id=editTravelHours", ("PlanningSlotUpdate.travel_hours_per_employee_day",)),
    # -- Angebot
    Z("quote_editor.html", "class=inline-input", ("QuoteItemUpdate.quantity",)),
    Z("quote_editor.html", None, ("QuoteFreeItemCreate.quantity", "QuoteItemUpdate.quantity"), lesen=("zahlFeld('iQty')",)),
    Z("quote_editor.html", None, ("QuoteFreeItemCreate.unit_price", "QuoteItemUpdate.unit_price"), lesen=("zahlFeld('iPrice')",)),
    # -- Betriebskosten
    Z("recurring_costs.html", "id=editNetAmount", ("RecurringCostCreate.net_amount", "RecurringCostUpdate.net_amount")),
    Z("recurring_costs.html", "id=editNoticePeriod", ("RecurringCostCreate.notice_period_months", "RecurringCostUpdate.notice_period_months")),
    # -- Dachfläche
    Z("roof_area.html", "id=editPitch", ("RoofAreaUpdate.pitch_degrees",)),
    Z("roof_area.html", "id=editArea", ("RoofAreaUpdate.area_sqm",)),
    Z("roof_area.html", "id=editComponentQuantity", ("RoofComponentCreate.quantity", "RoofComponentUpdate.quantity")),
    Z("roof_area.html", "id=editComponentYear", ("RoofComponentCreate.year_built", "RoofComponentUpdate.year_built")),
    Z("roof_area.html", "id=editComponentSort", ("RoofComponentCreate.sort_order", "RoofComponentUpdate.sort_order")),
    Z("roof_area.html", "data-feld=${esc(type.label)} – Dicke (mm)", ("RoofLayerUpsert.thickness_mm",)),
    # -- Einsatzbericht
    Z("service_reports.html", "id=teHours", ("TimeEntryManualCreate.hours",)),
    Z("service_reports.html", "data-feld=Menge", ("ServiceReportMaterialUpdate.quantity",),
      code={"pflicht": True}, beleg=("app/service_reports.py", "Bitte eine Menge größer als 0 angeben.")),
    Z("service_reports.html", "id=matQuantity-${r.id}", ("ServiceReportMaterialCreate.quantity",)),
    Z("service_reports.html", "data-field=duration_minutes", ("InspectionItemResultUpdate.duration_minutes",)),
    # -- Einstellungen
    Z("settings.html", "id=sidebarLogoHeight", ("GeneralSettingsUpdate.sidebar_logo_height_px",), lesen=("zahlFeld(input)",)),
    Z("settings.html", "id=ptDays", ("PaymentTermCreate.days", "PaymentTermUpdate.days"), lesen=("zahlFeld('ptDays')",)),
    Z("settings.html", "id=ptSkontoPercent", ("PaymentTermCreate.skonto_percent", "PaymentTermUpdate.skonto_percent")),
    Z("settings.html", "id=ptSkontoDays", ("PaymentTermCreate.skonto_days", "PaymentTermUpdate.skonto_days")),
    Z("settings.html", "id=tkVatRate", ("TaxKeyCreate.vat_rate", "TaxKeyUpdate.vat_rate"), lesen=("zahlFeld('tkVatRate')",)),
    *[Z("settings.html", None, (f"DocumentPageMarginsUpdate.{seite}_mm",), lesen=(f"zahlFeld('documentLayoutMargin{art}{name}')",))
      for art in ("First", "Continuation") for name, seite in (("Top", "top"), ("Bottom", "bottom"), ("Left", "left"), ("Right", "right"))],
    Z("settings.html", "id=documentLayoutContinuationY", ("DocumentLayoutBlockUpdate.y_mm",), lesen=("zahlFeld(feld)",)),
    Z("settings.html", "id=smtpPort", ("SmtpSettingsUpdate.port",), lesen=("zahlFeld('smtpPort')",)),
    Z("settings.html", "id=optionSort", ("SettingOptionCreate.sort_order", "SettingOptionUpdate.sort_order")),
    Z("settings.html", "id=timeListSort", ("SettingOptionCreate.sort_order",)),
    Z("settings.html", "id=functionSort", ("EmployeeFunctionCreate.sort_order", "EmployeeFunctionUpdate.sort_order")),
    Z("settings.html", "id=defaultBreak", ("TimeTrackingSettingsUpdate.default_break_minutes",),
      code={"min": _g(0), "max": _g(240)}, beleg=("app/schemas.py", "self.default_break_minutes > 240")),
    Z("settings.html", "id=fixedOverheadValue", ("LaborRateSettingsUpdate.fixed_overhead_value",)),
    Z("settings.html", "id=variableOverheadValue", ("LaborRateSettingsUpdate.variable_overhead_value",)),
    Z("settings.html", "id=planningDailyHours", ("PlanningSettingsUpdate.daily_work_hours",)),
    Z("settings.html", "id=planningTravelHours", ("PlanningSettingsUpdate.default_travel_hours_per_employee_day",)),
    Z("settings.html", "id=maintenanceLeadDays", ("MaintenanceSettingsUpdate.reminder_lead_days",),
      code={"min": _g(0)}, beleg=("app/maintenance_contracts.py", "reminder_lead_days < 0")),
    Z("settings.html", "id=operationalAssetLeadDays", ("OperationalAssetSettingsUpdate.reminder_lead_days",)),
    Z("settings.html", "id=recurringCostLeadDays", ("RecurringCostSettingsUpdate.reminder_lead_days",)),
    Z("settings.html", "id=incomingInvoiceLeadDays", ("IncomingInvoiceSettingsUpdate.skonto_reminder_lead_days",)),
    Z("settings.html", "id=newMaintenanceWindowFrom", ("MaintenanceWindowCreate.month_from",),
      code={"min": _g(1), "max": _g(12)}, beleg=("app/maintenance_contracts.py", "def _validate_window_months(")),
    Z("settings.html", "id=newMaintenanceWindowTo", ("MaintenanceWindowCreate.month_to",),
      code={"min": _g(1), "max": _g(12)}, beleg=("app/maintenance_contracts.py", "def _validate_window_months(")),
    Z("settings.html", "data-feld=Startmonat", ("MaintenanceWindowUpdate.month_from",), lesen=("zahlFeld(monthFrom)",),
      code={"min": _g(1), "max": _g(12)}, beleg=("app/maintenance_contracts.py", "def _validate_window_months(")),
    Z("settings.html", "data-feld=Endmonat", ("MaintenanceWindowUpdate.month_to",), lesen=("zahlFeld(monthTo)",),
      code={"min": _g(1), "max": _g(12)}, beleg=("app/maintenance_contracts.py", "def _validate_window_months(")),
    Z("settings.html", "id=modelDailyHours", ("WorkTimeModelUpsert.daily_target_hours",), lesen=("zahlFeld('modelDailyHours')",)),
    Z("settings.html", "id=modelSort", ("WorkTimeModelUpsert.sort_order",)),
    Z("settings.html", "id=modelValidFrom", ("WorkTimeModelUpsert.valid_from_week",)),
    Z("settings.html", "id=modelValidTo", ("WorkTimeModelUpsert.valid_to_week",)),
    Z("settings.html", "data-feld=Pausenregel – über Brutto-Stunden", ("WorkTimeBreakRuleInput.threshold_hours",),
      lesen=("zahlFeld(r.querySelector('.rule-threshold'))",)),
    Z("settings.html", "data-feld=Pausenregel – Pause Minuten", ("WorkTimeBreakRuleInput.break_minutes",),
      lesen=("zahlFeld(r.querySelector('.rule-minutes'))",)),
    Z("settings.html", "id=brNewYear", (), code={"min": _g(2000), "max": _g(2100), "ganz": True, "pflicht": True},
      beleg=("app/schemas.py", "BASISZINS_JAHRE = (2000, 2100)")),
    Z("settings.html", "id=brNewRate", ("BaseInterestRateCreate.rate_percent",), lesen=("zahlFeld('brNewRate')",)),
    Z("settings.html", "data-feld=Basiszinssatz", ("BaseInterestRateUpdate.rate_percent",), lesen=("zahlFeld(row.querySelector('.brRate'))",)),
    Z("settings.html", "id=rl${x.id}Days", ("ReminderLevelUpdate.days_after_previous_step",), lesen=("zahlFeld('rl'+id+'Days')",)),
    Z("settings.html", "id=rl${x.id}Fee", ("ReminderLevelUpdate.fee_amount",)),
    Z("settings.html", "class=start", ("NumberSequenceUpdate.start_value",), lesen=("zahlFeld(row.querySelector('.start'))",)),
    Z("settings.html", "data-feld=Nächste Nummer", ("NumberSequenceUpdate.next_value",), lesen=("zahlFeld(row.querySelector('.next'))",)),
    # -- Zeiterfassung
    Z("time_backoffice.html", None, ("TimeEntryUpdate.hours",), lesen=("zahlFeld('editHours')",)),
    Z("time_tracking.html", "id=stopBreak", ("TimeTimerStop.break_minutes", "TimeGroupTimerStop.break_minutes")),
    # seit 1.9.34 sind die Stunden im Schema optional (ein Nachtrag mit Von/Bis braucht keine) -- ohne Von/Bis verlangt sie der Validator
    Z("time_tracking.html", "id=manualHours", ("TimeEntryManualCreate.hours", "TimeEntryUpdate.hours"), lesen=("zahlFeld('manualHours')",),
      code={"pflicht": True}, beleg=("app/schemas.py", "Bitte die Dauer oder Von und Bis angeben.")),
    Z("time_tracking.html", "id=manualBreak", ("TimeEntryManualCreate.break_minutes", "TimeEntryUpdate.break_minutes")),
    Z("time_tracking.html", "id=groupHours", ("TimeGroupManualCreate.hours", "TimeGroupUpdate.hours"), lesen=("zahlFeld('groupHours')",)),
    Z("time_tracking.html", "id=groupBreak", ("TimeGroupManualCreate.break_minutes", "TimeGroupUpdate.break_minutes")),
    Z("time_tracking_field.html", "id=stopBreak", ("TimeTimerStop.break_minutes",)),
    Z("time_tracking_field.html", "id=manualDuration", ("TimeEntryManualCreate.hours", "TimeEntryUpdate.hours")),
    Z("time_tracking_field.html", "id=crewDialogHours", ("TimeGroupManualCreate.hours", "TimeGroupUpdate.hours")),
    # -- Arbeitsvorbereitung
    Z("work_preparation.html", "id=mqty-${x.id}", ("WorkPreparationMaterialUpdateV082.planned_quantity",)),
]


def _browser(z: Z) -> Grenzen:
    g = Grenzen()
    if z.markup is not None:
        g = grenzen_im_markup(dict(felder_mit_grenzen(z.vorlage))[z.markup])
    aufrufe = dict(leseaufrufe_mit_grenzen(z.vorlage))
    for aufruf in z.lesen:
        g = optionen_anwenden(g, aufrufe[aufruf])
    return g


def _server(z: Z, ref: str | None) -> Grenzen:
    g = grenzen_im_schema(ref) if ref else Grenzen()
    for name, wert in z.code.items():
        if name == "min":
            g.min = wert if g.min is None or wert[0] > g.min[0] else g.min
        elif name == "max":
            g.max = wert if g.max is None or wert[0] < g.max[0] else g.max
        else:
            setattr(g, name, wert or getattr(g, name))
    return g


def _name(z: Z) -> str:
    return f"{z.vorlage} {z.markup or ' '.join(z.lesen)}"


@pytest.mark.parametrize("z", ABGLEICH, ids=_name)
def test_der_browser_ist_nicht_strenger_als_der_server(z):
    if z.gleich:
        assert len(z.gleich) > 40
        return
    browser = _browser(z)
    gruende = {ref: strenger(browser, _server(z, ref)) for ref in (z.schemas or (None,))}
    assert all(not g for g in gruende.values()), f"{_name(z)}: {gruende}"


def _vorhanden() -> tuple[list, set]:
    """(Vorlage, Feld) je Zahlenfeld mit Grenzen und (Vorlage, Aufruf) je Leseaufruf mit Grenzen -- seit 1.8.124 (Stufe 0b) auch in
    Unterordnern (tests/vorlagen_js.py::alle_vorlagen())."""
    namen = vorlagen_js.alle_vorlagen(TEMPLATES)
    markup = [(name, s) for name in namen for s, _ in felder_mit_grenzen(name)]
    lesen = {(name, a) for name in namen if name != "_zahl.html" for a, _ in leseaufrufe_mit_grenzen(name)}
    return markup, lesen


def test_jedes_feld_und_jeder_leseaufruf_mit_grenzen_steht_genau_einmal_im_abgleich():
    markup = [(z.vorlage, z.markup) for z in ABGLEICH if z.markup]
    gelesen = [(z.vorlage, a) for z in ABGLEICH for a in z.lesen]
    vorhanden_markup, vorhanden_lesen = _vorhanden()
    assert len(vorhanden_markup) >= 88 and len(vorhanden_lesen) >= 35
    assert sorted(set(vorhanden_markup) - set(markup)) == [], "Zahlenfeld mit Grenzen fehlt im Abgleich"
    assert sorted(set(markup) - set(vorhanden_markup)) == [], "Abgleich nennt ein Feld, das es nicht (mehr) gibt"
    assert len(markup) == len(set(markup))
    assert sorted(vorhanden_lesen - set(gelesen)) == [], "Leseaufruf mit Grenzen fehlt im Abgleich"
    assert sorted(set(gelesen) - vorhanden_lesen) == [], "Abgleich nennt einen Leseaufruf, den es nicht (mehr) gibt"


def test_jede_grenze_im_code_hat_ihren_beleg():
    for z in ABGLEICH:
        assert bool(z.code) == bool(z.beleg), _name(z)
        if z.beleg:
            datei, stelle = z.beleg
            assert stelle in (ROOT / datei).read_text(encoding="utf-8"), f"{_name(z)}: Beleg fehlt in {datei}: {stelle!r}"
        for ref in z.schemas:
            grenzen_im_schema(ref)  # das Schemafeld gibt es


@pytest.mark.parametrize("browser, server, erwartet", [
    (Grenzen(min=_g(0)), Grenzen(), ["Mindestwert 0 nur im Browser"]),
    (Grenzen(min=_g(0.001)), Grenzen(min=_g(0, False)), ["Mindestwert 0.001 im Browser, Server ab über 0"]),
    (Grenzen(min=_g(0)), Grenzen(min=_g(0, False)), []),
    (Grenzen(max=_g(24)), Grenzen(max=_g(24, False)), []),
    (Grenzen(max=_g(23.75)), Grenzen(max=_g(24, False)), ["Höchstwert 23.75 im Browser, Server bis unter 24"]),
    (Grenzen(stellen=2), Grenzen(), ["höchstens 2 Nachkommastellen im Browser, Server beliebig"]),
    (Grenzen(stellen=3), Grenzen(stellen=2), []),
    (Grenzen(ganz=True), Grenzen(), ["ganze Zahl im Browser, Server nimmt Dezimalzahlen"]),
    (Grenzen(pflicht=True), Grenzen(), ["Pflicht im Browser, Server nimmt leer (null) an"]),
])
def test_der_vergleich(browser, server, erwartet):
    assert strenger(browser, server) == erwartet


# ---------------------------------------------------------------------------
# Verhalten an den geänderten Stellen
# ---------------------------------------------------------------------------

def test_das_jahr_des_basiszinssatzes_hat_die_grenzen_des_browsers():
    from datetime import date

    from pydantic import ValidationError

    from app.schemas import BaseInterestRateCreate

    werte = {"rate_percent": "1.27", "reviewed_on": None, "reviewed_by": None}
    assert BaseInterestRateCreate(half_year_start=date(2026, 7, 1), **werte).half_year_start.year == 2026
    for jahr in (1999, 2101):
        with pytest.raises(ValidationError, match="Jahr 2000 bis 2100"):
            BaseInterestRateCreate(half_year_start=date(jahr, 1, 1), **werte)


def test_eine_eingangsrechnung_ueber_0_euro_netto_laesst_der_browser_zu():
    """Bis 1.8.118 las die Seite das Netto mit {leer: 0} und lehnte danach jeden Betrag ab, der 0 war ("Bitte … Netto-Betrag angeben") --
    der Server nimmt 0 an (ge=0). Jetzt ist das Feld Pflicht, 0 € geht."""
    from tests.test_v314_dashboard_month_berlin import NODE
    from tests.test_v334_auswahl_restfaelle import im_browser, seite

    if NODE is None:
        pytest.skip("node nicht installiert")
    felder = ("_element('editSupplier').value='3'; _element('editInvoiceDate').value='2026-10-16'; _element('editTaxRate').value='19';")
    lauf = im_browser(seite("incoming_invoices.html", "\ninit();"), felder + """
      _element('editNetAmount').value='0'; const mitNull=buildPayload().net_amount;
      _element('editNetAmount').value=''; let leer=null; try{buildPayload()}catch(e){leer=e.message}
      return {mitNull, leer};""")
    # die Attrappe kennt data-feld nicht ("Die Zahl fehlt."), im Browser heißt es "Netto-Betrag fehlt."
    assert lauf["ergebnis"]["mitNull"] == 0 and lauf["ergebnis"]["leer"].endswith(" fehlt.")
    quelle = (TEMPLATES / "incoming_invoices.html").read_text(encoding="utf-8")
    assert "if(!payload.supplier_id||!payload.invoice_date){" in quelle and "!payload.net_amount" not in quelle
