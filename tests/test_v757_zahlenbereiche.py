"""Version 1.9.357 -- jedes Eingabefeld, das in Numeric(p,s) oder Integer geht, hat Grenzen bis zur Spalte (Runde V2c, Punkt 2; Befund Abschnitt 3 G).

SQLite speichert jede Zahl, PostgreSQL lehnt einen Wert ab, der nicht in die Spalte passt (Befund P6: Wochenstunden 100000 in Numeric(9,4) ->
NumericValueOutOfRange, live 500). Zuordnung wie bei den Längen (tests/test_v750_laengen.py): ein Eingabeschema gehört zum Modell, mit dessen Namen es
beginnt, ein Feld zur Spalte gleichen Namens. Die Grenzen stehen in app/schemas.py:

    Numeric(p,s)  höchstens der größte Wert der Spalte (NUMERIC_p_s, z. B. 999,99 für Numeric(5,2)), mindestens sein Negativ -- bei mehr als 15 Stellen
                  (Numeric(18,…)) 999.999.999.999 (ZAHL_12): so steht die Grenze in der Antwort (JSON-Zahl) und in der Meldung genau
    Integer       INT4_MIN bis INT4_MAX (int4 unter PostgreSQL)

Eine engere Grenze, die schon da war (ge=0, le=80 …), bleibt. Zu groß heißt 422 mit Feld (loc) und Grenze (ctx.le/ge), nie 500. OFFEN darf nur kürzer
werden; seit 1.9.357 leer (98 Numeric- und 150 Integer-Felder des Befunds)."""

import json
import re
from decimal import Decimal

import pydantic
import pytest
from sqlalchemy import Integer, Numeric

import app.schemas as schemas
from app.routers.projects import router as projekte_router
from app.routers.roof_areas import router as dachflaechen_router
from tests.test_v202_maintenance_contracts import make_customer_and_property
from tests.test_v314_dashboard_month_berlin import TEMPLATES, _node
from tests.test_v333_auswahl_inaktiv import nur_mit_node
from tests.test_v750_laengen import _eingabeschemas, _modell_zu

OFFEN: set[str] = set()  # „Schema.feld“; darf nur kürzer werden


def spaltengrenze(t) -> Decimal:
    if isinstance(t, Integer):
        return Decimal(schemas.INT4_MAX)
    return Decimal(10) ** (t.precision - t.scale) - Decimal(10) ** (-t.scale)


def _grenze(f, *arten):
    return next((Decimal(str(getattr(x, a))) for x in f.metadata for a in arten if getattr(x, a, None) is not None), None)


def zahlenfelder():
    """(Schema, Feld, Tabelle.Spalte, Spaltengrenze, oben, unten, ganzzahlig) je Zahlenfeld eines Eingabeschemas, das in eine Spalte Numeric/Integer geht."""
    out = []
    for s in _eingabeschemas():
        cls = _modell_zu(s.__name__)
        if cls is None:
            continue
        for c in cls.__table__.columns:
            if c.name not in s.model_fields or not isinstance(c.type, (Numeric, Integer)):
                continue
            f = s.model_fields[c.name]
            if not any(x in str(f.annotation) for x in ("int", "Decimal", "float")):
                continue
            out.append((s, c.name, f"{cls.__tablename__}.{c.name}", spaltengrenze(c.type), _grenze(f, "le", "lt"), _grenze(f, "ge", "gt"),
                        isinstance(c.type, Integer)))
    return out


FELDER = zahlenfelder()


# Jede Grenze, die ein Zahlenfeld schon vor 1.9.357 hatte (ge=0, le=80 …), bleibt -- die Grenzen der Spalte kamen nur dazu, wo keine war. Stand 1.9.356,
# aus dem Inventar des Befunds; ein Feld darf hier strenger werden (mit Grund), nie weiter.
VORHER = {
    "ArbeitszeitKalendertagIn.monat": {"ge": "1", "le": "12"},
    "ArbeitszeitKalendertagIn.sollzeit": {"ge": "0", "le": "24"},
    "ArbeitszeitKalendertagIn.tag": {"ge": "1", "le": "31"},
    "CalculationSettingsUpdate.labor_rate": {"ge": "0"},
    "CalculationSettingsUpdate.material_markup_pct": {"ge": "-100"},
    "CalculationSettingsUpdate.overhead_pct": {"ge": "-100"},
    "CalculationSettingsUpdate.risk_profit_pct": {"ge": "-100"},
    "DocumentLayoutBlockUpdate.font_size": {"ge": "5", "le": "36"},
    "DocumentLayoutBlockUpdate.height_mm": {"gt": "0", "le": "297"},
    "DocumentLayoutBlockUpdate.width_mm": {"gt": "0", "le": "210"},
    "DocumentLayoutBlockUpdate.x_mm": {"ge": "0", "le": "210"},
    "DocumentLayoutBlockUpdate.y_mm": {"ge": "0", "le": "297"},
    "DocumentPageMarginsUpdate.bottom_mm": {"ge": "0", "le": "100"},
    "DocumentPageMarginsUpdate.left_mm": {"ge": "0", "le": "100"},
    "DocumentPageMarginsUpdate.right_mm": {"ge": "0", "le": "100"},
    "DocumentPageMarginsUpdate.top_mm": {"ge": "0", "le": "100"},
    "EmployeeCreate.hourly_wage": {"ge": "0"},
    "EmployeeCreate.weekly_hours": {"gt": "0", "le": "80"},
    "EmployeeFunctionCreate.sort_order": {"ge": "0", "le": "9999"},
    "EmployeeFunctionUpdate.sort_order": {"ge": "0", "le": "9999"},
    "EmployeeUpdate.hourly_wage": {"ge": "0"},
    "EmployeeUpdate.weekly_hours": {"gt": "0", "le": "80"},
    "GeneralSettingsUpdate.default_vat_rate": {"ge": "0", "le": "100"},
    "GeneralSettingsUpdate.sidebar_logo_height_px": {"ge": "24", "le": "120"},
    "IncomingInvoiceCreate.net_amount": {"ge": "0"},
    "IncomingInvoiceCreate.skonto_percent": {"ge": "0", "le": "100"},
    "IncomingInvoiceItemIn.net_amount": {"ge": "0"},
    "IncomingInvoiceSettingsUpdate.skonto_reminder_lead_days": {"ge": "0"},
    "IncomingInvoiceUpdate.net_amount": {"ge": "0"},
    "IncomingInvoiceUpdate.skonto_percent": {"ge": "0", "le": "100"},
    "InspectionItemResultUpdate.duration_minutes": {"ge": "0"},
    "InvoiceCreateAbschlagPauschal.lump_sum_net": {"gt": "0"},
    "InvoiceHeaderUpdate.lump_sum_net": {"gt": "0"},
    "InvoiceItemCreate.ist_quantity": {"ge": "0"},
    "InvoiceItemCreate.unit_price": {"ge": "0"},
    "InvoiceItemUpdate.ist_quantity": {"ge": "0"},
    "InvoiceItemUpdate.unit_price": {"ge": "0"},
    "LaborRateSettingsUpdate.annual_overhead": {"ge": "0"},
    "LaborRateSettingsUpdate.employer_cost_pct": {"ge": "0", "le": "200"},
    "LaborRateSettingsUpdate.productive_time_pct": {"gt": "0", "le": "100"},
    "LaborRateSettingsUpdate.target_profit_pct": {"ge": "0", "le": "200"},
    "LaborRateSettingsUpdate.weeks_per_year": {"gt": "0", "le": "53"},
    "MaintenanceContractCreate.interval_months": {"ge": "1", "le": "24"},
    "MaintenanceContractFromProjectCreate.interval_months": {"ge": "1", "le": "24"},
    "MaintenanceContractItemCreate.duration_minutes": {"ge": "0"},
    "MaintenanceContractItemUpdate.duration_minutes": {"ge": "0"},
    "MaintenanceContractUpdate.interval_months": {"ge": "1", "le": "24"},
    "MaterialCatalogCreate.price_basis": {"gt": "0"},
    "MaterialCatalogCreate.purchase_price": {"ge": "0"},
    "MaterialCatalogUpdate.price_basis": {"gt": "0"},
    "MaterialCatalogUpdate.purchase_price": {"ge": "0"},
    "NumberSequenceUpdate.next_value": {"ge": "0"},
    "NumberSequenceUpdate.start_value": {"ge": "0"},
    "OperationalAssetCreate.acquisition_cost": {"ge": "0"},
    "OperationalAssetInspectionCreate.interval_months": {"ge": "1"},
    "OperationalAssetInspectionUpdate.interval_months": {"ge": "1"},
    "OperationalAssetSettingsUpdate.reminder_lead_days": {"ge": "0"},
    "OperationalAssetUpdate.acquisition_cost": {"ge": "0"},
    "OrderItemUpdate.quantity": {"ge": "0"},
    "OrderItemUpdate.unit_price": {"ge": "0"},
    "OrderWarrantyUpdate.warranty_days": {"ge": "0", "le": "366"},
    "OrderWarrantyUpdate.warranty_months": {"ge": "0", "le": "360"},
    "PaymentChargeLineIn.amount": {"gt": "0"},
    "PaymentCreate.amount": {"gt": "0"},
    "PaymentTermCreate.days": {"ge": "0"},
    "PaymentTermCreate.skonto_days": {"ge": "0"},
    "PaymentTermCreate.skonto_percent": {"gt": "0", "le": "100"},
    "PaymentTermUpdate.days": {"ge": "0"},
    "PaymentTermUpdate.skonto_days": {"ge": "0"},
    "PaymentTermUpdate.skonto_percent": {"gt": "0", "le": "100"},
    "PlanningSettingsUpdate.daily_work_hours": {"ge": "0.01", "le": "24"},
    "PlanningSettingsUpdate.default_travel_hours_per_employee_day": {"ge": "0", "le": "23.75"},
    "PlanningSlotCapacityUpdate.planned_hours": {"ge": "0"},
    "PlanningSlotCapacityUpdate.travel_hours_per_employee_day": {"ge": "0", "lt": "24"},
    "ProductiveHoursSettingsUpdate.average_sick_days": {"ge": "0", "le": "366"},
    "ProductiveHoursSettingsUpdate.daily_hours": {"gt": "0", "le": "24"},
    "ProductiveHoursSettingsUpdate.public_holidays": {"ge": "0", "le": "366"},
    "ProductiveHoursSettingsUpdate.unproductive_time_pct": {"ge": "0", "le": "100"},
    "ProductiveHoursSettingsUpdate.vacation_days": {"ge": "0", "le": "366"},
    "ProductiveHoursSettingsUpdate.weather_loss_days": {"ge": "0", "le": "366"},
    "ProductiveHoursSettingsUpdate.weekly_hours": {"gt": "0", "le": "80"},
    "QuoteCreate.vat_rate": {"ge": "0", "le": "100"},
    "QuoteItemCalculationUpdate.equipment_cost": {"ge": "0"},
    "QuoteItemCalculationUpdate.labor_rate": {"ge": "0"},
    "QuoteItemCalculationUpdate.manual_sale_price": {"ge": "0"},
    "QuoteItemCalculationUpdate.material_markup_pct": {"ge": "-100"},
    "QuoteItemCalculationUpdate.other_cost": {"ge": "0"},
    "QuoteItemCalculationUpdate.overhead_pct": {"ge": "-100"},
    "QuoteItemCalculationUpdate.risk_profit_pct": {"ge": "-100"},
    "QuoteItemCalculationUpdate.site_time_minutes": {"ge": "0"},
    "QuoteItemCalculationUpdate.subcontractor_cost": {"ge": "0"},
    "QuoteItemCalculationUpdate.workshop_time_minutes": {"ge": "0"},
    "QuoteItemCreate.quantity": {"gt": "0"},
    "QuoteItemMaterialCalculationUpdate.price_basis": {"gt": "0"},
    "QuoteItemMaterialCalculationUpdate.purchase_price": {"ge": "0"},
    "QuoteItemMaterialCalculationUpdate.quantity": {"ge": "0"},
    "QuoteItemMaterialCalculationUpdate.waste_pct": {"ge": "-100"},
    "QuoteItemUpdate.quantity": {"ge": "0.001"},
    "QuoteItemUpdate.unit_price": {"ge": "0"},
    "QuoteUpdate.vat_rate": {"ge": "0", "le": "100"},
    "RecurringCostCreate.net_amount": {"ge": "0"},
    "RecurringCostCreate.notice_period_months": {"ge": "1", "le": "24"},
    "RecurringCostSettingsUpdate.reminder_lead_days": {"ge": "0"},
    "RecurringCostUpdate.net_amount": {"ge": "0"},
    "RecurringCostUpdate.notice_period_months": {"ge": "1", "le": "24"},
    "ReminderChargesUpdate.fee_amount": {"ge": "0"},
    "ReminderCreate.level": {"ge": "1", "le": "3"},
    "ReminderLevelUpdate.days_after_previous_step": {"ge": "1", "le": "365"},
    "ReminderLevelUpdate.fee_amount": {"ge": "0"},
    "RoofAreaCreate.area_sqm": {"ge": "0"},
    "RoofAreaCreate.pitch_degrees": {"ge": "0"},
    "RoofAreaUpdate.area_sqm": {"ge": "0"},
    "RoofAreaUpdate.pitch_degrees": {"ge": "0"},
    "RoofComponentCreate.quantity": {"ge": "0"},
    "RoofComponentCreate.year_built": {"ge": "1000", "le": "2100"},
    "RoofComponentPositionUpdate.sketch_h": {"ge": "0", "le": "100"},
    "RoofComponentPositionUpdate.sketch_w": {"ge": "0", "le": "100"},
    "RoofComponentPositionUpdate.sketch_x": {"ge": "0", "le": "100"},
    "RoofComponentPositionUpdate.sketch_y": {"ge": "0", "le": "100"},
    "RoofComponentUpdate.quantity": {"ge": "0"},
    "RoofComponentUpdate.year_built": {"ge": "1000", "le": "2100"},
    "RoofLayerUpsert.thickness_mm": {"ge": "0"},
    "ServiceBaseUpdate.quantity": {"gt": "0"},
    "ServiceCalculationUpdate.equipment_cost": {"ge": "0"},
    "ServiceCalculationUpdate.labor_rate_override": {"ge": "0"},
    "ServiceCalculationUpdate.manual_sale_price": {"ge": "0"},
    "ServiceCalculationUpdate.material_markup_pct_override": {"ge": "-100"},
    "ServiceCalculationUpdate.other_cost": {"ge": "0"},
    "ServiceCalculationUpdate.overhead_pct_override": {"ge": "-100"},
    "ServiceCalculationUpdate.risk_profit_pct_override": {"ge": "-100"},
    "ServiceCalculationUpdate.site_time_minutes": {"ge": "0"},
    "ServiceCalculationUpdate.subcontractor_cost": {"ge": "0"},
    "ServiceCalculationUpdate.workshop_time_minutes": {"ge": "0"},
    "ServiceCreate.quantity": {"gt": "0"},
    "ServiceCreate.sale_price": {"ge": "0"},
    "ServiceCreate.site_time_raw": {"ge": "0"},
    "ServiceCreate.workshop_time_raw": {"ge": "0"},
    "ServiceMaterialAdd.quantity": {"gt": "0"},
    "ServiceReportMaterialCreate.quantity": {"ge": "0.001"},
    "ServiceReportMaterialUpdate.quantity": {"ge": "0.001"},
    "SettingOptionCreate.sort_order": {"ge": "0", "le": "99999"},
    "SettingOptionUpdate.sort_order": {"ge": "0", "le": "99999"},
    "SmtpSettingsUpdate.port": {"ge": "1", "le": "65535"},
    "TaxKeyCreate.vat_rate": {"ge": "0", "le": "100"},
    "TaxKeyUpdate.vat_rate": {"ge": "0", "le": "100"},
    "TimeEntryManualCreate.break_minutes": {"ge": "0", "le": "720"},
    "TimeEntryManualCreate.hours": {"ge": "0.01", "le": "24"},
    "TimeEntryUpdate.break_minutes": {"ge": "0", "le": "720"},
    "TimeEntryUpdate.hours": {"ge": "0.01", "le": "24"},
    "WorkPreparationEmployeeCreate.planned_hours": {"ge": "0"},
    "WorkPreparationEmployeeUpdate.planned_hours": {"ge": "0"},
    "WorkPreparationMaterialUpdate.planned_quantity": {"ge": "0"},
    "WorkPreparationMaterialUpdateV082.planned_quantity": {"ge": "0"},
    "WorkTimeBreakRuleInput.break_minutes": {"ge": "0", "le": "720"},
    "WorkTimeBreakRuleInput.threshold_hours": {"ge": "0.01", "le": "24"},
    "WorkTimeModelUpsert.daily_target_hours": {"ge": "0.01", "le": "24"},
}


def test_vorhandene_grenzen_bleiben():
    felder = {f"{s.__name__}.{feld}": s.model_fields[feld] for s, feld, *_ in FELDER}
    geaendert = {}
    for name, grenzen in VORHER.items():
        for art, wert in grenzen.items():
            ist = _grenze(felder[name], art)
            if ist is None or ist != Decimal(wert):
                geaendert[f"{name}.{art}"] = (wert, ist)
    assert geaendert == {}, "eine Grenze von vorher geändert -- Spaltengrenzen nur dort, wo keine war"


def test_jedes_zahlenfeld_hat_grenzen_bis_zur_spalte():
    offen = set()
    for s, feld, _spalte, g, oben, unten, ganz in FELDER:
        untergrenze = -g - 1 if ganz else -g
        if oben is None or oben > g or unten is None or unten < untergrenze:
            offen.add(f"{s.__name__}.{feld}")
    assert offen <= OFFEN, f"ohne passende Grenzen (le/ge bis zur Spalte, app/schemas.py): {sorted(offen - OFFEN)}"
    assert not OFFEN - offen, f"erledigt, aus OFFEN nehmen: {sorted(OFFEN - offen)}"
    # die Zuordnung findet die Felder des Befunds noch: Numeric 141 (43 passten schon), Integer 172 (22 passten schon)
    assert sum(1 for x in FELDER if not x[6]) >= 141 and sum(1 for x in FELDER if x[6]) >= 172


def _zu_gross(schema, feld, wert):
    with pytest.raises(pydantic.ValidationError) as fehler:
        schema.model_validate({feld: wert})
    return [e for e in fehler.value.errors() if e["loc"][-1] == feld]


@pytest.mark.parametrize("schema, feld, spalte, g, oben, ganz", [(s, f, sp, g, o, ga) for s, f, sp, g, o, _u, ga in FELDER],
                         ids=lambda x: getattr(x, "__name__", str(x)))
def test_ueber_der_spalte_wird_mit_feld_und_grenze_abgelehnt(schema, feld, spalte, g, oben, ganz):
    wert = int(g) + 1 if ganz else str(g + 1)
    treffer = _zu_gross(schema, feld, wert)
    # zu groß: die Grenze (le/lt) -- oder eine Stellenzahl, die das Feld schon vorher hatte (max_digits, z. B. Basiszinssatz, Zahlung, Mahngebühr)
    assert [e["type"] for e in treffer] in (["less_than_equal"], ["less_than"], ["decimal_max_digits"], ["decimal_whole_digits"]), (spalte, treffer)
    if treffer[0]["type"] in ("less_than_equal", "less_than"):
        assert Decimal(str(treffer[0]["ctx"].get("le", treffer[0]["ctx"].get("lt")))) <= g
    unter = _zu_gross(schema, feld, -int(g) - 2 if ganz else str(-g - 1))
    assert [e["type"] for e in unter] in (["greater_than_equal"], ["greater_than"], ["decimal_max_digits"], ["decimal_whole_digits"]), (spalte, unter)


def test_grenzen_passen_unter_postgresql_in_ihre_spalte():
    """Jede Grenze aus app/schemas.py passt in ihre Spalte -- und ein Schritt darüber nicht (unter PostgreSQL; SQLite nähme beides)."""
    from sqlalchemy import text
    from sqlalchemy.exc import DataError
    from tests.befund_vor_echtbetrieb import pg_sitzung
    faelle = [(f"numeric({p},{s})", getattr(schemas, f"NUMERIC_{p}_{s}"), Decimal(10) ** -s)
              for p, s in ((4, 1), (5, 1), (5, 2), (6, 2), (6, 3), (9, 4), (12, 2))]
    faelle += [(f"numeric(18,{s})", Decimal(schemas.ZAHL_12), None) for s in (2, 3, 4, 6)]
    faelle += [("integer", Decimal(schemas.INT4_MAX), Decimal(1)), ("integer", Decimal(schemas.INT4_MIN), Decimal(-1))]
    with pg_sitzung("zahlenbereiche") as db:
        for typ, grenze, schritt in faelle:
            assert db.execute(text(f"SELECT CAST(:w AS {typ})"), {"w": str(grenze)}).scalar() == grenze, typ
            assert db.execute(text(f"SELECT CAST(:w AS {typ})"), {"w": str(-grenze if typ != "integer" else grenze)}).scalar() is not None
            if schritt is not None:
                with pytest.raises(DataError):
                    db.execute(text(f"SELECT CAST(:w AS {typ})"), {"w": str(grenze + schritt)})
                db.rollback()


# Über echte Routen: bis 1.9.356 unter SQLite 200 (live unter PostgreSQL 500), jetzt 422 mit Feld und Grenze.
def test_route_dachneigung(threaded_db_session, router_test_client):
    db = threaded_db_session
    _kunde, objekt = make_customer_and_property(db)
    client = router_test_client(db, dachflaechen_router)
    r = client.post("/api/roof-areas", json={"property_id": objekt.id, "name": "Süd", "pitch_degrees": "1000"})
    assert r.status_code == 422, r.text
    assert [(e["loc"][-1], e["type"], e["ctx"]["le"]) for e in r.json()["detail"]] == [("pitch_degrees", "less_than_equal", 999.99)]


def test_route_kunde_des_projekts(threaded_db_session, router_test_client):
    client = router_test_client(threaded_db_session, projekte_router)
    r = client.post("/api/projects", json={"customer_id": 3_000_000_000, "name": "Probe"})
    assert r.status_code == 422, r.text
    assert [(e["loc"][-1], e["type"], e["ctx"]["le"]) for e in r.json()["detail"]] == [("customer_id", "less_than_equal", 2147483647)]


@nur_mit_node
def test_meldung_nennt_die_grenze():
    """fehlerText() (_fehlertext.html) hängt seit 1.9.357 die Grenze an „ist zu groß“ / „ist zu klein“, deutsch formatiert."""
    skript = "\n".join(re.findall(r"<script>(.*?)</script>", (TEMPLATES / "_fehlertext.html").read_text(encoding="utf-8"), re.S))
    faelle = [
        {"detail": [{"type": "less_than_equal", "loc": ["body", "pitch_degrees"], "msg": "x", "ctx": {"le": 999.99}}]},
        {"detail": [{"type": "greater_than_equal", "loc": ["body", "pitch_degrees"], "msg": "x", "ctx": {"ge": -999.99}}]},
        {"detail": [{"type": "less_than_equal", "loc": ["body", "customer_id"], "msg": "x", "ctx": {"le": 2147483647}}]},
        {"detail": [{"type": "less_than", "loc": ["body", "pitch_degrees"], "msg": "x", "ctx": {"lt": 90}}]},
        {"detail": [{"type": "less_than_equal", "loc": ["body", "pitch_degrees"], "msg": "x"}]},
        {"detail": [{"type": "decimal_max_digits", "loc": ["body", "pitch_degrees"], "msg": "Decimal input should have …", "ctx": {"max_digits": 6}}]},
    ]
    ergebnis = _node(skript + f"\nprocess.stdout.write(JSON.stringify({json.dumps(faelle)}.map(b=>fehlerText(b,422,"
                     "{pitch_degrees:'Dachneigung',customer_id:'Kunde'}))));", "Europe/Berlin")
    assert ergebnis == ["Bitte die Eingabe prüfen – Dachneigung ist zu groß (höchstens 999,99).",
                        "Bitte die Eingabe prüfen – Dachneigung ist zu klein (mindestens -999,99).",
                        "Bitte die Eingabe prüfen – Kunde ist zu groß (höchstens 2.147.483.647).",
                        "Bitte die Eingabe prüfen – Dachneigung ist zu groß (muss kleiner als 90 sein).",
                        "Bitte die Eingabe prüfen – Dachneigung ist zu groß.",
                        "Bitte die Eingabe prüfen – Dachneigung hat zu viele Stellen (höchstens 6)."]
