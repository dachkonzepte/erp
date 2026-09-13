from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy import inspect as sa_inspect
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .models import (
    CalculationSettings,
    MaterialCalculationOverride,
    Service,
    ServiceCalculation,
)

ZERO = Decimal("0")
HUNDRED = Decimal("100")
SIXTY = Decimal("60")
CENT = Decimal("0.01")


def q(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def effective_material_sale_price(purchase_price: Decimal, price_basis: Decimal, material_markup_pct: Decimal) -> Decimal:
    """Einkaufspreis (bezogen auf price_basis Einheiten) zu einem Verkaufspreis pro Einheit
    veredelt -- dieselbe Formel wie der Material-Abschnitt von build_calculation() weiter unten
    (base_cost = qty/basis*price, dann * (1 + markup/100)), hier als eigene Funktion, damit
    create_invoice_from_time_entries() (app/invoices.py, Rechnung aus Aufwand) für
    Katalogmaterial denselben Verkaufspreis bildet wie ein Angebot -- ohne die Formel dorthin zu
    duplizieren oder das bestehende build_calculation() dafür umzubauen. price_basis == 0 wird
    wie dort auf 1 normalisiert, statt eine Division durch Null auszulösen."""
    basis = price_basis if price_basis else Decimal("1")
    base_price = purchase_price / basis
    return base_price * (Decimal("1") + material_markup_pct / HUNDRED)


def _calculation_settings_has_catalog_column(db: Session) -> bool:
    """Analog zu _services_table_has_catalog_column in catalogs.py: true,
    sobald die 1.0.14-Migration angewendet wurde. Vorher existiert
    calculation_settings.catalog_id in der echten Datenbank noch nicht --
    genau das hat "Einstellungen konnten nicht geladen werden" in 1.0.18
    ausgelöst, weil get_or_create_settings() seit dem catalog_id-IS-NULL-Fix
    ungeprüft auf diese Spalte zugegriffen hat."""
    inspector = sa_inspect(db.get_bind())
    columns = {col["name"] for col in inspector.get_columns("calculation_settings")}
    return "catalog_id" in columns


def get_or_create_settings(db: Session) -> CalculationSettings:
    if not _calculation_settings_has_catalog_column(db):
        # Anders als backfill_existing_services() kann diese Funktion nicht
        # einfach überspringen -- sie muss etwas zurückgeben, das alle
        # Aufrufer (Kalkulation, Einstellungsseite, ...) tatsächlich nutzen
        # können. Ein "Fallback" über db.get(CalculationSettings, 1) wäre
        # keiner: das ORM-Modell kennt catalog_id, jede darüber laufende
        # Abfrage würde also ebenfalls an der fehlenden Spalte scheitern.
        # Deshalb hier bewusst klar und verständlich fehlschlagen, statt
        # einen Fallback vorzutäuschen, der es nicht ist -- die Meldung
        # landet dank der Fehler-Middleware aus 1.0.8 vollständig in
        # data/erp.log.
        raise RuntimeError(
            "calculation_settings.catalog_id fehlt in der Datenbank -- die 1.0.14-Migration "
            "wurde noch nicht angewendet. Bitte 'alembic revision --autogenerate' und "
            "'alembic upgrade head' ausführen, danach die App neu starten."
        )

    # Der globale Datensatz wird über catalog_id IS NULL gefunden, nicht über
    # id=1 (seit 1.0.17 kein verlässliches Kennzeichen mehr: mit mehreren
    # möglichen Datensätzen könnte irgendeine Zeile durch reine
    # Erzeugungsreihenfolge zufällig id=1 bekommen, nicht zwingend die
    # global gemeinte). Für eine bestehende Installation, die diese Spalte
    # gerade erst per Migration bekommen hat, ist ihr vorhandener Datensatz
    # automatisch catalog_id=NULL -- wird also unverändert gefunden.
    settings = db.scalar(select(CalculationSettings).where(CalculationSettings.catalog_id.is_(None)))
    if settings is None:
        settings = CalculationSettings(catalog_id=None)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


def get_settings_for_catalog(
    db: Session, catalog_id: int | None, cache: dict[int | None, CalculationSettings] | None = None
) -> CalculationSettings:
    """Kalkulationsgrundlagen für einen Katalog auflösen (seit 1.0.14).

    Hat der Katalog eigene Kalkulationsgrundlagen (CalculationSettings mit
    passender catalog_id), gelten die. Sonst gilt weiterhin der globale
    Datensatz (get_or_create_settings) -- bestehendes Verhalten bleibt damit
    für alle Katalog ohne eigene Grundlagen unverändert.

    cache ist optional: bei Listen mit vielen Leistungen aus wenigen
    Katalogen vermeidet er, dieselbe Abfrage pro Leistung zu wiederholen.
    """
    if cache is not None and catalog_id in cache:
        return cache[catalog_id]
    settings = None
    if catalog_id is not None:
        settings = db.scalar(select(CalculationSettings).where(CalculationSettings.catalog_id == catalog_id))
    if settings is None:
        settings = get_or_create_settings(db)
    if cache is not None:
        cache[catalog_id] = settings
    return settings


def get_service_for_calculation(db: Session, service_id: int) -> Service | None:
    return db.scalar(
        select(Service)
        .options(
            selectinload(Service.materials),
            selectinload(Service.calculation),
            selectinload(Service.material_overrides),
        )
        .where(Service.id == service_id)
    )


def _override_map(service: Service) -> dict[tuple[str, str], MaterialCalculationOverride]:
    return {
        (item.article_number_key or "", item.material_name_key): item
        for item in service.material_overrides
    }


def build_calculation(service: Service, settings: CalculationSettings) -> dict:
    calc = service.calculation

    use_source = bool(settings.use_source_time_as_minutes)
    source_site = Decimal(service.site_time_raw or ZERO)
    source_workshop = Decimal(service.workshop_time_raw or ZERO)

    site_time = (
        Decimal(calc.site_time_minutes)
        if calc is not None and calc.site_time_minutes is not None
        else (source_site if use_source else ZERO)
    )
    workshop_time = (
        Decimal(calc.workshop_time_minutes)
        if calc is not None and calc.workshop_time_minutes is not None
        else (source_workshop if use_source else ZERO)
    )

    labor_rate = Decimal(
        calc.labor_rate_override
        if calc is not None and calc.labor_rate_override is not None
        else settings.labor_rate
    )
    material_markup_pct = Decimal(
        calc.material_markup_pct_override
        if calc is not None and calc.material_markup_pct_override is not None
        else settings.material_markup_pct
    )
    overhead_pct = Decimal(
        calc.overhead_pct_override
        if calc is not None and calc.overhead_pct_override is not None
        else settings.overhead_pct
    )
    risk_profit_pct = Decimal(
        calc.risk_profit_pct_override
        if calc is not None and calc.risk_profit_pct_override is not None
        else settings.risk_profit_pct
    )

    labor_amount = (site_time + workshop_time) / SIXTY * labor_rate

    overrides = _override_map(service)
    material_rows = []
    material_base_cost = ZERO
    for material in service.materials:
        key = (material.article_number or "", material.name)
        override = overrides.get(key)

        source_qty = Decimal(material.quantity or ZERO)
        source_price = Decimal(material.purchase_price or ZERO)
        source_basis = Decimal(material.price_basis or Decimal("1"))
        if source_basis == ZERO:
            source_basis = Decimal("1")

        quantity_override = Decimal(override.quantity_override) if override and override.quantity_override is not None else None
        price_override = Decimal(override.purchase_price_override) if override and override.purchase_price_override is not None else None
        basis_override = Decimal(override.price_basis_override) if override and override.price_basis_override is not None else None
        waste_pct = Decimal(override.waste_pct or ZERO) if override else ZERO

        effective_qty = quantity_override if quantity_override is not None else source_qty
        effective_qty = effective_qty * (Decimal("1") + waste_pct / HUNDRED)
        effective_price = price_override if price_override is not None else source_price
        effective_basis = basis_override if basis_override is not None else source_basis
        if effective_basis == ZERO:
            effective_basis = Decimal("1")

        base_cost = effective_qty / effective_basis * effective_price
        material_base_cost += base_cost
        material_rows.append(
            {
                "material_id": material.id,
                "name": material.name,
                "article_number": material.article_number,
                "unit": material.unit,
                "source_quantity": source_qty,
                "effective_quantity": effective_qty,
                "source_purchase_price": source_price,
                "effective_purchase_price": effective_price,
                "source_price_basis": source_basis,
                "effective_price_basis": effective_basis,
                "waste_pct": waste_pct,
                "base_cost": q(base_cost),
                "quantity_override": quantity_override,
                "purchase_price_override": price_override,
                "price_basis_override": basis_override,
            }
        )

    material_markup_amount = material_base_cost * material_markup_pct / HUNDRED
    material_amount = material_base_cost + material_markup_amount
    equipment = Decimal(calc.equipment_cost or ZERO) if calc else ZERO
    subcontract = Decimal(calc.subcontractor_cost or ZERO) if calc else ZERO
    other = Decimal(calc.other_cost or ZERO) if calc else ZERO

    subtotal_before_overhead = labor_amount + material_amount + equipment + subcontract + other
    overhead_amount = subtotal_before_overhead * overhead_pct / HUNDRED
    subtotal_before_risk_profit = subtotal_before_overhead + overhead_amount
    risk_profit_amount = subtotal_before_risk_profit * risk_profit_pct / HUNDRED
    calculated_sale_price = subtotal_before_risk_profit + risk_profit_amount
    manual_sale_price = Decimal(calc.manual_sale_price) if calc and calc.manual_sale_price is not None else None
    effective_sale_price = manual_sale_price if manual_sale_price is not None else calculated_sale_price
    source_sale = Decimal(service.sale_price or ZERO)
    delta = effective_sale_price - source_sale
    delta_pct = (delta / source_sale * HUNDRED) if source_sale != ZERO else None

    return {
        "service_id": service.id,
        "external_id": service.external_id,
        "service_name": service.short_text.splitlines()[0] if service.short_text else "",
        "unit": service.unit,
        "source_site_time_raw": source_site,
        "source_workshop_time_raw": source_workshop,
        "source_sale_price": q(source_sale),
        "site_time_minutes": site_time,
        "workshop_time_minutes": workshop_time,
        "uses_source_site_time": calc is None or calc.site_time_minutes is None,
        "uses_source_workshop_time": calc is None or calc.workshop_time_minutes is None,
        "labor_rate": labor_rate,
        "material_markup_pct": material_markup_pct,
        "overhead_pct": overhead_pct,
        "risk_profit_pct": risk_profit_pct,
        "labor_amount": q(labor_amount),
        "material_base_cost": q(material_base_cost),
        "material_markup_amount": q(material_markup_amount),
        "material_amount": q(material_amount),
        "equipment_cost": q(equipment),
        "subcontractor_cost": q(subcontract),
        "other_cost": q(other),
        "subtotal_before_overhead": q(subtotal_before_overhead),
        "overhead_amount": q(overhead_amount),
        "subtotal_before_risk_profit": q(subtotal_before_risk_profit),
        "risk_profit_amount": q(risk_profit_amount),
        "calculated_sale_price": q(calculated_sale_price),
        "effective_sale_price": q(effective_sale_price),
        "manual_sale_price": q(manual_sale_price) if manual_sale_price is not None else None,
        "delta_to_source": q(delta),
        "delta_to_source_pct": q(delta_pct) if delta_pct is not None else None,
        "notes": calc.notes if calc else None,
        "labor_rate_override": Decimal(calc.labor_rate_override) if calc and calc.labor_rate_override is not None else None,
        "material_markup_pct_override": Decimal(calc.material_markup_pct_override) if calc and calc.material_markup_pct_override is not None else None,
        "overhead_pct_override": Decimal(calc.overhead_pct_override) if calc and calc.overhead_pct_override is not None else None,
        "risk_profit_pct_override": Decimal(calc.risk_profit_pct_override) if calc and calc.risk_profit_pct_override is not None else None,
        "materials": material_rows,
    }
