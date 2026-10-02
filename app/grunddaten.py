"""Grunddaten: Einstellungen und Standardsätze, die jede Installation braucht (seit 1.8.42).

Bis 1.8.41 legte jede Lesefunktion ihre Zeile beim ersten Zugriff selbst an (get_or_create_*_settings,
ensure_default_* in den Lesepfaden). Das hatte drei Folgen:
- zwei gleichzeitige erste Zugriffe legten dieselbe Einstellung zweimal an, einer scheiterte am
  Primärschlüssel (Einstellungsseite: labor_rate_settings und Gemeinkosten-Einstellung, 1.8.21/1.8.40);
- Standardsätze ohne UNIQUE-Constraint (Zahlungsbedingungen, Steuerschlüssel, Mahnstufen, Layout)
  konnten still doppelt entstehen;
- das Anlegen committete mitten in einer fremden Transaktion -- beim Festschreiben und Unterschreiben
  des Vertrags gab das die Zeilensperre frei (1.8.40, Nebenbefund 1).

Seither legt anlegen() alles beim Start an (app/main.py, in jeder Umgebung). Die Lesefunktionen
(load_*, list_*, get_margins(), load_layout()) lesen nur noch; fehlt eine Einstellung, melden sie
GrunddatenFehlen statt sie anzulegen. Testdatenbanken bekommen dieselben Grunddaten nach
create_all() (tests/conftest.py), wie eine echte Installation nach dem Start.

anlegen() läuft in EINER Transaktion und committet erst am Ende. Zwei Arbeitsprozesse
(gunicorn -w 2) starten gleichzeitig: der erste Schritt legt die Zeile general_settings id=1 an und
sperrt sie (SELECT ... FOR UPDATE) -- der zweite Prozess wartet dort, bis der erste committet hat,
und findet danach alles vor. Unter SQLite öffnet BEGIN IMMEDIATE die Transaktion mit der Schreibsperre
der Datenbank (siehe _sperren()). Jeder einzelne Anlegeschritt läuft zusätzlich in einem SAVEPOINT
(Muster 1.4.6).
Deshalb dürfen die Schritte (ensure_default_* in den Fachmodulen) nicht selbst committen -- ein
Commit gäbe die Sperre frei.

Neue Einstellung oder neuer Standardsatz: hier eintragen (EINZELZEILEN bzw. anlegen()), nicht in
der Lesefunktion anlegen. tests/test_v326_monteur_datengrenze.py prüft, dass kein GET schreibt."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


class GrunddatenFehlen(RuntimeError):
    """Eine Einstellung fehlt, die anlegen() beim Start angelegt haben müsste."""


def einzelzeile(db: Session, model):
    """Die eine Einstellungszeile (id=1) einer Singleton-Tabelle -- nur lesen."""
    row = db.get(model, 1)
    if row is None:
        raise GrunddatenFehlen(
            f"{model.__tablename__}: Einstellungszeile fehlt -- app.grunddaten.anlegen() ist beim Start "
            "nicht gelaufen oder gescheitert (siehe Log)."
        )
    return row


def _einzelzeilen():
    """(Modell, Startwerte) je Singleton-Einstellung, id=1. Startwerte nur, wo das Modell selbst
    keinen passenden Vorgabewert hat."""
    from .models import (
        AISettings, GeneralSettings, IncomingInvoiceSettings, LaborRateSettings, MaintenanceSettings,
        MobileSettings, OperationalAssetSettings, OutlookSyncSettings, PlanningRegionSettings, PlanningSettings,
        ProductiveHoursSettings, RecurringCostSettings, SmtpSettings, TaskSettings, TimeBackofficeAdvancedSettings,
        TimeTrackingSettings,
    )
    return [
        (GeneralSettings, {}),
        (AISettings, {}),
        (SmtpSettings, {}),
        (IncomingInvoiceSettings, {}),
        (LaborRateSettings, {}),
        (MaintenanceSettings, {}),
        (MobileSettings, {}),
        (OperationalAssetSettings, {}),
        (OutlookSyncSettings, {}),
        (PlanningSettings, {}),
        (PlanningRegionSettings, {"federal_state_code": "NW"}),
        (ProductiveHoursSettings, {}),
        (RecurringCostSettings, {}),
        (TaskSettings, {}),
        (TimeTrackingSettings, {}),
        (TimeBackofficeAdvancedSettings, {"datev_personnel_equals_erp_number": False}),
    ]


def _zeile_anlegen(db: Session, model, werte: dict) -> None:
    if db.get(model, 1) is not None:
        return
    try:
        with db.begin_nested():
            db.add(model(id=1, **werte))
            db.flush()
    except IntegrityError:
        pass  # ein anderer Prozess war schneller


def _sperren(db: Session) -> None:
    """Erster Schritt: general_settings id=1 anlegen oder vorhanden sperren. Ein zweiter, gleichzeitig
    startender Prozess wartet hier (beim Anlegen am Primärschlüssel, sonst an FOR UPDATE).

    SQLite kennt kein FOR UPDATE, und pysqlite beginnt die Transaktion erst vor der ersten Änderung -- ein
    SAVEPOINT davor ist selbst die Transaktion, sein RELEASE committet (so in 1.8.42 beim Test mit zwei
    Prozessen gefunden: Zahlungsbedingungen doppelt). Deshalb dort BEGIN IMMEDIATE: holt die Schreibsperre
    der Datenbank, der zweite Prozess wartet (bis zum busy timeout von pysqlite, 5 Sekunden)."""
    from .models import GeneralSettings
    connection = db.connection()
    if connection.dialect.name == "sqlite" and not connection.connection.dbapi_connection.in_transaction:
        connection.exec_driver_sql("BEGIN IMMEDIATE")
    _zeile_anlegen(db, GeneralSettings, {})
    db.execute(select(GeneralSettings.id).where(GeneralSettings.id == 1).with_for_update())


def _gemeinkosten_anlegen(db: Session) -> None:
    """Gemeinkosten-Einstellung: übernimmt beim Anlegen die alten "jährlichen Gemeinkosten" (<=0.6.8)
    als fixe Gemeinkosten in EUR -- deshalb nach LaborRateSettings."""
    from decimal import Decimal

    from .models import LaborRateOverheadSettings, LaborRateSettings
    if db.get(LaborRateOverheadSettings, 1) is not None:
        return
    base = db.get(LaborRateSettings, 1)
    try:
        with db.begin_nested():
            db.add(LaborRateOverheadSettings(
                id=1, fixed_overhead_mode="eur", fixed_overhead_value=Decimal(base.annual_overhead or 0),
                variable_overhead_mode="eur", variable_overhead_value=Decimal("0"),
            ))
            db.flush()
    except IntegrityError:
        pass


def _kalkulation_anlegen(db: Session) -> None:
    """Globale Kalkulationsgrundlagen (catalog_id IS NULL, ID automatisch -- siehe CalculationSettings).
    Kein UNIQUE greift hier (NULL ist in UNIQUE nie gleich) -- die Sperre in _sperren() verhindert die
    doppelte Zeile."""
    from .models import CalculationSettings
    if db.scalar(select(CalculationSettings.id).where(CalculationSettings.catalog_id.is_(None)).limit(1)) is not None:
        return
    with db.begin_nested():
        db.add(CalculationSettings(catalog_id=None))
        db.flush()


def anlegen(db: Session) -> None:
    """Legt fehlende Grunddaten an, rührt vorhandene nie an. Idempotent; committet einmal am Ende."""
    from .document_categories import ensure_default_categories
    from .document_layout import ensure_default_layout
    from .document_page_margins import ensure_default_margins
    from .employees import ensure_default_employee_functions
    from .option_settings import ensure_default_option_groups
    from .payment_terms import ensure_default_payment_terms
    from .project_pipeline_columns import ensure_default_columns as ensure_default_pipeline_columns
    from .reminders import ensure_default_reminder_levels
    from .settings import ensure_default_sequences
    from .task_columns import ensure_default_columns as ensure_default_task_columns
    from .tax_keys import ensure_default_tax_keys
    from .work_time_models import ensure_default_work_time_models

    _sperren(db)
    for model, werte in _einzelzeilen():
        _zeile_anlegen(db, model, werte)
    _gemeinkosten_anlegen(db)
    _kalkulation_anlegen(db)
    ensure_default_option_groups(db)  # nach general_settings: übernimmt dort gepflegte Angebotstexte
    ensure_default_categories(db)
    ensure_default_employee_functions(db)
    ensure_default_payment_terms(db)
    ensure_default_tax_keys(db)
    ensure_default_reminder_levels(db)
    ensure_default_pipeline_columns(db)
    ensure_default_task_columns(db)
    ensure_default_sequences(db)
    ensure_default_work_time_models(db)  # nach time_backoffice_advanced_settings: setzt das Standardmodell
    ensure_default_layout(db)
    ensure_default_margins(db)
    db.commit()
