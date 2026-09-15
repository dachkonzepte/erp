"""Wartungsverträge (seit 1.2.0, Modul "wartungen").

Bewusst kein Scheduler: check_due_contracts_and_create_reminders() wird beim Aufruf der
Wartungsverträge-Seite ausgelöst (gleiches On-Demand-Muster wie
auto_create_due_reminder_drafts() in app/reminders.py) und erinnert per Aufgabe an einen
zuständigen Mitarbeiter -- ein neuer Vorgang wird nie selbständig erzeugt, das bleibt ein
bewusster Klick (create_project_from_contract()).

Positionen je Dachfläche (MaintenanceContractItem) und saisonale Wartungsfenster
(MaintenanceWindow), seit 1.2.15: hat ein Vertrag mindestens eine aktive (nicht archivierte)
Position UND ist MaintenanceSettings.use_roof_area_items an (seit 1.2.19, Default aus -- vorher
war das Verhalten unbedingt), löst die Positionsebene die Vertragsebene VOLLSTÄNDIG ab -- nicht
nur für Erinnerungen, auch für is_due und für create_project_from_contract() ohne item_id (siehe
_is_due() unten). Ist der Schalter aus, zählt IMMER next_due_date/interval_months, auch wenn
noch Altbestand-Positionen aus einer Zeit existieren, in der der Schalter an war -- diese Zeilen
bleiben in der DB, werden nur nicht mehr ausgewertet. In der Oberfläche heißen Positionen "Zu
wartende Dachflächen" (das Wort "Position" wurde seit 1.2.19 bewusst aus der Oberfläche
entfernt, die Modell-/Funktionsnamen im Code bleiben unverändert)."""

import calendar
from datetime import date, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, selectinload

from .date_utils import add_months
from .models import (
    MaintenanceContract, MaintenanceContractItem, MaintenanceSettings, MaintenanceWindow,
    Project, RoofArea, ServiceReport, Task,
)
from .modules import is_module_enabled
from .projects import duplicate_project, get_or_create_project_profile
from .quick_service_orders import create_quick_service_order
from .roof_areas import list_roof_areas
from .service_reports import create_report
from .tasks import create_task

STATUSES = ("aktiv", "pausiert", "beendet")
MODULE_KEY = "wartungen"


def _next_window_opening(window: MaintenanceWindow, after: date) -> date:
    """Nächster Beginn des saisonalen Fensters ab (exklusive) after -- month_from ist der
    Ankermonat für die jährliche Wiederkehr, unabhängig davon, ob das Fenster über den
    Jahreswechsel reicht (month_to < month_from). Der 1. des Ankermonats gilt als Öffnung."""
    candidate = date(after.year, window.month_from, 1)
    if candidate <= after:
        candidate = date(after.year + 1, window.month_from, 1)
    return candidate


def _window_close_date(window: MaintenanceWindow, opening: date) -> date:
    """opening ist immer der 1. des Ankermonats (month_from) in einem bestimmten Jahr (siehe
    _next_window_opening()). Bei month_to < month_from reicht das Fenster über den
    Jahreswechsel, das Monatsende von month_to liegt dann im Folgejahr."""
    year = opening.year if window.month_to >= window.month_from else opening.year + 1
    last_day = calendar.monthrange(year, window.month_to)[1]
    return date(year, window.month_to, last_day)


def _employee_name(e) -> str | None:
    return f"{e.first_name} {e.last_name}".strip() if e else None


def _address(*parts) -> str | None:
    values = [str(x).strip() for x in parts if x and str(x).strip()]
    return ", ".join(values) if values else None


def get_or_create_maintenance_settings(db: Session) -> MaintenanceSettings:
    settings = db.get(MaintenanceSettings, 1)
    if settings is None:
        settings = MaintenanceSettings(id=1)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


def maintenance_settings_to_dict(settings: MaintenanceSettings) -> dict:
    return {
        "reminder_lead_days": settings.reminder_lead_days,
        "use_roof_area_items": settings.use_roof_area_items,
        "default_responsible_employee_id": settings.default_responsible_employee_id,
        "default_responsible_employee_name": _employee_name(settings.default_responsible_employee),
    }


def update_maintenance_settings(db: Session, reminder_lead_days: int, use_roof_area_items: bool,
                                 default_responsible_employee_id: int | None) -> dict:
    if reminder_lead_days < 0:
        raise ValueError("Die Vorlaufzeit darf nicht negativ sein.")
    settings = get_or_create_maintenance_settings(db)
    settings.reminder_lead_days = reminder_lead_days
    settings.use_roof_area_items = use_roof_area_items
    settings.default_responsible_employee_id = default_responsible_employee_id
    db.commit()
    db.refresh(settings)
    return maintenance_settings_to_dict(settings)


def _is_item_due(item: "MaintenanceContractItem", lead_days: int) -> bool:
    return not item.archived and item.next_due_date <= date.today() + timedelta(days=lead_days)


def _is_item_overdue(item: "MaintenanceContractItem") -> bool:
    return not item.archived and date.today() > _window_close_date(item.maintenance_window, item.next_due_date)


def _is_due(contract: MaintenanceContract, lead_days: int, use_roof_area_items: bool) -> bool:
    """Hat der Vertrag mindestens eine aktive (nicht archivierte) Position UND ist der Schalter
    MaintenanceSettings.use_roof_area_items an, entscheiden ausschließlich die Positionen --
    contract.next_due_date wird dann nicht mehr ausgewertet (siehe Moduldocstring). Ist der
    Schalter aus, zählt IMMER next_due_date/interval_months, auch wenn der Vertrag noch
    Altbestand-Positionen aus einer Zeit trägt, in der der Schalter an war (seit 1.2.19)."""
    if not (contract.status == "aktiv" and not contract.archived):
        return False
    if use_roof_area_items:
        active_items = [i for i in contract.items if not i.archived]
        if active_items:
            return any(_is_item_due(i, lead_days) for i in active_items)
    return contract.next_due_date <= date.today() + timedelta(days=lead_days)


def item_to_dict(item: "MaintenanceContractItem", lead_days: int) -> dict:
    template_id = item.template_project_id or item.contract.template_project_id
    template = item.template_project or item.contract.template_project
    return {
        "id": item.id,
        "contract_id": item.contract_id,
        "roof_area_id": item.roof_area_id,
        "roof_area_name": item.roof_area.name if item.roof_area else None,
        "maintenance_window_id": item.maintenance_window_id,
        "maintenance_window_label": item.maintenance_window.label if item.maintenance_window else None,
        "template_project_id": template_id,
        "template_project_number": template.project_number if template else None,
        "inspection_template_id": item.inspection_template_id,
        "inspection_template_label": item.inspection_template.label if item.inspection_template else None,
        "description": item.description,
        "duration_minutes": item.duration_minutes,
        "next_due_date": item.next_due_date,
        "archived": item.archived,
        "is_due": _is_item_due(item, lead_days),
        "is_overdue": _is_item_overdue(item),
    }


def contract_to_dict(contract: MaintenanceContract, lead_days: int, use_roof_area_items: bool) -> dict:
    # Ohne ausgewähltes Objekt gilt die Hauptadresse des Kunden selbst als Einsatzort --
    # Property ("Objekt" in den Stammdaten) ist seit 1.2.9 optional, ein Wartungsvertrag
    # betrifft nicht automatisch ein zusätzliches Objekt.
    if contract.property:
        prop = contract.property
        city_line = " ".join(x for x in [prop.postal_code, prop.city] if x)
        property_name = prop.name
        property_address = _address(prop.street, city_line)
        property_postal_code = prop.postal_code
        property_city = prop.city
    else:
        property_name = "Hauptadresse"
        customer = contract.customer
        city_line = " ".join(x for x in [customer.postal_code, customer.city] if x) if customer else ""
        property_address = _address(customer.street, city_line) if customer else None
        property_postal_code = customer.postal_code if customer else None
        property_city = customer.city if customer else None
    return {
        "id": contract.id,
        "customer_id": contract.customer_id,
        "customer_name": contract.customer.name if contract.customer else None,
        "property_id": contract.property_id,
        "property_name": property_name,
        "property_address": property_address,
        "property_postal_code": property_postal_code,
        "property_city": property_city,
        "title": contract.title,
        "interval_months": contract.interval_months,
        "next_due_date": contract.next_due_date,
        "template_project_id": contract.template_project_id,
        "template_project_number": contract.template_project.project_number if contract.template_project else None,
        "responsible_employee_id": contract.responsible_employee_id,
        "responsible_employee_name": _employee_name(contract.responsible_employee),
        "status": contract.status,
        "archived": contract.archived,
        "notes": contract.notes,
        "is_due": _is_due(contract, lead_days, use_roof_area_items),
        "items": [item_to_dict(i, lead_days) for i in contract.items],
        "created_at": contract.created_at,
        "updated_at": contract.updated_at,
    }


def _contract_item_options():
    return (
        selectinload(MaintenanceContract.items).selectinload(MaintenanceContractItem.roof_area),
        selectinload(MaintenanceContract.items).selectinload(MaintenanceContractItem.maintenance_window),
        selectinload(MaintenanceContract.items).selectinload(MaintenanceContractItem.template_project),
        selectinload(MaintenanceContract.items).selectinload(MaintenanceContractItem.inspection_template),
    )


def _load(db: Session, contract_id: int) -> MaintenanceContract | None:
    return db.scalar(
        select(MaintenanceContract)
        .options(
            selectinload(MaintenanceContract.customer), selectinload(MaintenanceContract.property),
            selectinload(MaintenanceContract.template_project), selectinload(MaintenanceContract.responsible_employee),
            *_contract_item_options(),
        )
        .where(MaintenanceContract.id == contract_id)
    )


def _load_item(db: Session, item_id: int) -> "MaintenanceContractItem | None":
    return db.scalar(
        select(MaintenanceContractItem)
        .options(
            selectinload(MaintenanceContractItem.roof_area), selectinload(MaintenanceContractItem.maintenance_window),
            selectinload(MaintenanceContractItem.template_project),
            selectinload(MaintenanceContractItem.inspection_template),
            selectinload(MaintenanceContractItem.contract).selectinload(MaintenanceContract.template_project),
        )
        .where(MaintenanceContractItem.id == item_id)
    )


def get_contract(db: Session, contract_id: int) -> dict | None:
    """Einzelabruf für die eigene Vertragsseite (seit 1.2.19, /maintenance-contracts/{id}) --
    vorher gab es nur list_contracts(), die Liste hatte keinen Einzelabruf nötig, da alles
    inline auf derselben Seite aufklappte."""
    contract = _load(db, contract_id)
    if contract is None:
        return None
    settings = get_or_create_maintenance_settings(db)
    return contract_to_dict(contract, settings.reminder_lead_days, settings.use_roof_area_items)


def list_contracts(db: Session, status: str | None = None, include_archived: bool = False) -> list[dict]:
    settings = get_or_create_maintenance_settings(db)
    query = select(MaintenanceContract).options(
        selectinload(MaintenanceContract.customer), selectinload(MaintenanceContract.property),
        selectinload(MaintenanceContract.template_project), selectinload(MaintenanceContract.responsible_employee),
        *_contract_item_options(),
    )
    if status is not None:
        query = query.where(MaintenanceContract.status == status)
    if not include_archived:
        query = query.where(MaintenanceContract.archived == False)  # noqa: E712 -- SQLAlchemy-Vergleich, kein Python-Bool-Vergleich
    query = query.order_by(MaintenanceContract.next_due_date)
    return [
        contract_to_dict(c, settings.reminder_lead_days, settings.use_roof_area_items)
        for c in db.scalars(query).all()
    ]


def list_contracts_for_property(db: Session, property_id: int, include_archived: bool = False) -> list[dict]:
    """Wartungsverträge eines Objekts für die neue Objektseite (seit 1.2.18) -- Property hat
    laut Bestandsaufnahme keine Rückwärts-Relationship zu MaintenanceContract; eine eigene
    select-Abfrage genügt hier, eine Relationship nur für diesen einen Anzeigefall wäre
    Overkill (gleiche Zurückhaltung wie bei der property_id-Auflösung in
    app/service_reports.py::list_property_history())."""
    settings = get_or_create_maintenance_settings(db)
    query = select(MaintenanceContract).options(
        selectinload(MaintenanceContract.customer), selectinload(MaintenanceContract.property),
        selectinload(MaintenanceContract.template_project), selectinload(MaintenanceContract.responsible_employee),
        *_contract_item_options(),
    ).where(MaintenanceContract.property_id == property_id)
    if not include_archived:
        query = query.where(MaintenanceContract.archived == False)  # noqa: E712 -- SQLAlchemy-Vergleich, kein Python-Bool-Vergleich
    query = query.order_by(MaintenanceContract.next_due_date)
    return [
        contract_to_dict(c, settings.reminder_lead_days, settings.use_roof_area_items)
        for c in db.scalars(query).all()
    ]


def create_contract(db: Session, customer_id: int, property_id: int | None, title: str, interval_months: int,
                     next_due_date: date, template_project_id: int | None = None,
                     responsible_employee_id: int | None = None, notes: str | None = None) -> dict:
    if interval_months < 1:
        raise ValueError("Das Intervall muss mindestens 1 Monat betragen.")
    contract = MaintenanceContract(
        customer_id=customer_id, property_id=property_id, title=title.strip(),
        interval_months=interval_months, next_due_date=next_due_date,
        template_project_id=template_project_id, responsible_employee_id=responsible_employee_id,
        notes=(notes or None),
    )
    db.add(contract)
    db.commit()
    settings = get_or_create_maintenance_settings(db)
    return contract_to_dict(_load(db, contract.id), settings.reminder_lead_days, settings.use_roof_area_items)


def update_contract(db: Session, contract_id: int, title: str, interval_months: int, next_due_date: date,
                     template_project_id: int | None, responsible_employee_id: int | None,
                     notes: str | None, property_id: int | None = None) -> dict | None:
    contract = db.get(MaintenanceContract, contract_id)
    if contract is None:
        return None
    if interval_months < 1:
        raise ValueError("Das Intervall muss mindestens 1 Monat betragen.")
    contract.property_id = property_id
    contract.title = title.strip()
    contract.interval_months = interval_months
    contract.next_due_date = next_due_date
    contract.template_project_id = template_project_id
    contract.responsible_employee_id = responsible_employee_id
    contract.notes = notes or None
    db.commit()
    settings = get_or_create_maintenance_settings(db)
    return contract_to_dict(_load(db, contract.id), settings.reminder_lead_days, settings.use_roof_area_items)


def set_contract_status(db: Session, contract_id: int, status: str) -> dict | None:
    if status not in STATUSES:
        raise ValueError(f"Unbekannter Status: {status}")
    contract = db.get(MaintenanceContract, contract_id)
    if contract is None:
        return None
    contract.status = status
    db.commit()
    settings = get_or_create_maintenance_settings(db)
    return contract_to_dict(_load(db, contract.id), settings.reminder_lead_days, settings.use_roof_area_items)


def set_contract_archived(db: Session, contract_id: int, archived: bool) -> dict | None:
    """Rein informatives Aus-/Einblenden aus der Standardliste (seit 1.2.10, gleiches Muster
    wie set_project_archived() in app/projects.py) -- jederzeit umkehrbar, unabhängig vom
    Status (aktiv/pausiert/beendet)."""
    contract = db.get(MaintenanceContract, contract_id)
    if contract is None:
        return None
    contract.archived = archived
    db.commit()
    settings = get_or_create_maintenance_settings(db)
    return contract_to_dict(_load(db, contract.id), settings.reminder_lead_days, settings.use_roof_area_items)


def delete_contract(db: Session, contract_id: int) -> bool:
    """Kein GoBD-Dokument wie Invoice/Order/Reminder -- ein Wartungsvertrag ist reine
    Planungsinformation, echtes Löschen ist daher grundsätzlich erlaubt, nicht nur für
    Entwürfe -- AUSSER es existiert bereits ein unterschriebener Einsatzbericht dazu (seit
    1.2.15, vertrags- oder positionsbezogen): dann wird blockiert statt kaskadiert, exakt das
    Muster von delete_project() (siehe app/projects.py) -- Archivieren bleibt davon unberührt.
    MaintenanceContractItem-Zeilen räumt die ORM-Cascade auf MaintenanceContract.items
    automatisch ab. Die von check_due_contracts_and_create_reminders() erzeugten
    Erinnerungs-Aufgaben (Vertrags- UND Positionsebene, beide teilen sich dieselbe source_url)
    hängen nur locker über source_module/source_url an diesem Vertrag (siehe
    Automatisierungs-Anschlussstelle in app/tasks.py, bewusst keine FK-Beziehung). Ohne
    explizites Aufräumen blieben sie als tote Links zurück -- deshalb hier vorab gelöscht,
    unabhängig davon, ob die Aufgabe bereits archiviert oder erledigt ist."""
    contract = db.get(MaintenanceContract, contract_id)
    if contract is None:
        return False
    if db.scalar(
        select(ServiceReport.id).where(
            ServiceReport.maintenance_contract_id == contract_id, ServiceReport.status == "unterschrieben",
        ).limit(1)
    ):
        raise ValueError(
            "Wartungsverträge mit bereits unterschriebenen Einsatzberichten können nicht gelöscht werden, nur archiviert."
        )
    db.execute(
        delete(Task).where(Task.source_module == "wartungsvertrag", Task.source_url == f"/maintenance-contracts/{contract_id}")
    )
    db.delete(contract)
    db.commit()
    return True


def check_due_contracts_and_create_reminders(db: Session) -> list[dict]:
    """Erinnert per Aufgabe an jeden fälligen (oder innerhalb der Vorlaufzeit
    MaintenanceSettings.reminder_lead_days bald fälligen), aktiven und nicht archivierten
    Vertrag -- last_reminder_due_date verhindert, dass ein erneuter Seitenaufruf für denselben
    Fälligkeitszyklus doppelt erinnert. Ohne eigenen responsible_employee_id greift der
    globale default_responsible_employee_id als Rückfall. Ohne aktives Aufgabenmanagement
    entfällt die Erinnerung ersatzlos (eine Aufgabe wäre dort sowieso nirgends sichtbar).

    Positionen (MaintenanceContractItem, seit 1.2.15): hat ein Vertrag mindestens eine aktive
    Position, übernimmt AUSSCHLIESSLICH die Positionsebene die Erinnerung -- die
    Vertragsschleife unten überspringt solche Verträge, um keine doppelte Aufgabe zu erzeugen.
    reminded enthält jede Vertrags-ID höchstens einmal, auch wenn mehrere Positionen desselben
    Vertrags in diesem Lauf erinnert wurden. Eine bereits überfällige Position (is_overdue,
    siehe contract_to_dict()) wird dabei NICHT erneut erinnert, solange last_reminder_due_date
    == next_due_date bleibt -- das ändert sich erst, wenn tatsächlich ein Vorgang angelegt
    wird (create_project_from_contract() rückt next_due_date weiter). Dasselbe Verhalten wie
    auf Vertragsebene seit 1.2.0; den laufenden Überblick über offene/überfällige Positionen
    liefert list_due_items_grouped() ("Fällige Wartungen im Fenster"), nicht wiederholte
    Aufgaben."""
    if not is_module_enabled(db, "aufgabenmanagement"):
        return []
    settings = get_or_create_maintenance_settings(db)
    threshold = date.today() + timedelta(days=settings.reminder_lead_days)
    due = db.scalars(
        select(MaintenanceContract)
        .options(selectinload(MaintenanceContract.items))
        .where(
            MaintenanceContract.status == "aktiv",
            MaintenanceContract.archived == False,  # noqa: E712 -- SQLAlchemy-Vergleich, kein Python-Bool-Vergleich
            MaintenanceContract.next_due_date <= threshold,
        )
    ).all()
    reminded = []
    for contract in due:
        if settings.use_roof_area_items and any(not i.archived for i in contract.items):
            continue  # Positionsebene übernimmt vollständig, siehe Funktions-Docstring
        if contract.last_reminder_due_date == contract.next_due_date:
            continue
        create_task(
            db, title=f"Wartung fällig: {contract.title}",
            description=f"Wartungsvertrag \"{contract.title}\" ist am {contract.next_due_date.strftime('%d.%m.%Y')} fällig.",
            assigned_employee_id=contract.responsible_employee_id or settings.default_responsible_employee_id,
            source_module="wartungsvertrag", source_label=f"Wartungsvertrag {contract.title}",
            source_url=f"/maintenance-contracts/{contract.id}",
        )
        contract.last_reminder_due_date = contract.next_due_date
        reminded.append(contract.id)

    if settings.use_roof_area_items:
        items_due = db.scalars(
            select(MaintenanceContractItem)
            .join(MaintenanceContract, MaintenanceContractItem.contract_id == MaintenanceContract.id)
            .options(
                selectinload(MaintenanceContractItem.roof_area), selectinload(MaintenanceContractItem.contract),
            )
            .where(
                MaintenanceContract.status == "aktiv",
                MaintenanceContract.archived == False,  # noqa: E712
                MaintenanceContractItem.archived == False,  # noqa: E712
                MaintenanceContractItem.next_due_date <= threshold,
            )
        ).all()
        for item in items_due:
            if item.last_reminder_due_date == item.next_due_date:
                continue
            create_task(
                db, title=f"Wartung fällig: {item.contract.title} -- {item.roof_area.name}",
                description=(
                    f"Position \"{item.roof_area.name}\" von Wartungsvertrag \"{item.contract.title}\" "
                    f"ist am {item.next_due_date.strftime('%d.%m.%Y')} fällig."
                ),
                assigned_employee_id=item.contract.responsible_employee_id or settings.default_responsible_employee_id,
                source_module="wartungsvertrag", source_label=f"Wartungsvertrag {item.contract.title}",
                # Bewusst dieselbe URL wie der Vertrag selbst -- delete_contract()s bestehendes
                # Task-Aufräumen (Filter auf source_module + source_url) greift dadurch
                # unverändert auch für Positions-Aufgaben, ohne dass delete_contract() etwas über
                # Positionen wissen müsste.
                source_url=f"/maintenance-contracts/{item.contract_id}",
            )
            item.last_reminder_due_date = item.next_due_date
            if item.contract_id not in reminded:
                reminded.append(item.contract_id)

    if reminded:
        db.commit()
    return reminded


def create_project_from_contract(db: Session, contract_id: int, item_id: int | None = None) -> dict:
    """Erzeugt einen neuen Vorgang aus dem Mustervorgang des Vertrags (item_id=None, heutiges
    Verhalten) oder einer einzelnen Position (item_id gesetzt, seit 1.2.15) -- eine Position
    kann ihren eigenen template_project_id tragen, der dann dem Vertrags-Mustervorgang vorgeht.
    Ohne item_id wird abgelehnt, solange der Vertrag noch aktive Positionen hat UND
    MaintenanceSettings.use_roof_area_items an ist (seit 1.2.19) -- ist der Schalter aus, zählt
    ausschließlich die Vertragsebene, auch wenn noch Altbestand-Positionen existieren. Prüft
    bewusst NICHT die Fälligkeit (is_due/is_overdue) -- das bleibt Sache der Oberfläche
    (Rückfrage vor dem Anlegen, wenn der Vertrag noch nicht fällig ist, seit 1.2.19)."""
    contract = db.get(MaintenanceContract, contract_id)
    if contract is None:
        raise ValueError("Wartungsvertrag nicht gefunden.")
    use_roof_area_items = get_or_create_maintenance_settings(db).use_roof_area_items
    active_items = [i for i in contract.items if not i.archived]

    if item_id is None:
        if use_roof_area_items and active_items:
            raise ValueError(
                "Dieser Wartungsvertrag hat aktive Positionen -- bitte den Vorgang je Position anlegen."
            )
        if contract.template_project_id is None:
            raise ValueError("Für diesen Vertrag ist kein Mustervorgang hinterlegt.")
        template = db.get(Project, contract.template_project_id)
        if template is None:
            raise ValueError("Der hinterlegte Mustervorgang wurde nicht gefunden.")
        new_project = duplicate_project(db, template, as_template=False)
        new_project.description = (
            f"{new_project.description}\n\n" if new_project.description else ""
        ) + f"Erstellt aus Wartungsvertrag \"{contract.title}\" am {date.today().strftime('%d.%m.%Y')}."
        contract.next_due_date = add_months(contract.next_due_date, contract.interval_months)
        contract.last_reminder_due_date = None
    else:
        item = db.get(MaintenanceContractItem, item_id)
        if item is None or item.contract_id != contract_id:
            raise ValueError("Position nicht gefunden.")
        template_id = item.template_project_id or contract.template_project_id
        if template_id is None:
            raise ValueError("Für diese Position (und den Vertrag) ist kein Mustervorgang hinterlegt.")
        template = db.get(Project, template_id)
        if template is None:
            raise ValueError("Der hinterlegte Mustervorgang wurde nicht gefunden.")
        new_project = duplicate_project(db, template, as_template=False)
        new_project.description = (
            f"{new_project.description}\n\n" if new_project.description else ""
        ) + (
            f"Erstellt aus Wartungsvertrag \"{contract.title}\", Position \"{item.roof_area.name}\" "
            f"am {date.today().strftime('%d.%m.%Y')}."
        )
        item.next_due_date = _next_window_opening(item.maintenance_window, after=item.next_due_date)
        item.last_reminder_due_date = None

    profile = get_or_create_project_profile(db, new_project.id)
    profile.source_maintenance_contract_id = contract.id
    profile.source_maintenance_contract_item_id = item_id
    db.commit()
    db.refresh(new_project)
    return {"project_id": new_project.id, "project_number": new_project.project_number}


def create_maintenance_visit(db: Session, contract_id: int, created_by_employee_id: int | None = None) -> dict:
    """"Wartung durchführen" (seit 1.2.22): fasst Anlegen des Auftrags UND eines vorbereiteten
    Wartungsberichts über ALLE nicht archivierten Dachflächen des Objekts in einem Schritt
    zusammen -- bewusst ohne den Mustervorgang (Wartung wird über die Vertragspauschale oder
    nach Aufwand abgerechnet, nicht über LV-Positionen, siehe create_quick_service_order()).

    Reine Vertragsebene, unabhängig von MaintenanceContractItem/use_roof_area_items: hat der
    Vertrag aktive Positionen unter dem Schalter, bleibt dafür ausschließlich der bestehende Weg
    je Position (create_project_from_contract() mit item_id) zuständig -- dieselbe Sperre wie
    dort, da eine einzelne, objektweite Wartung sonst mit der positionsweisen
    Fälligkeitssteuerung kollidieren würde.

    Die Fälligkeit wird hier bewusst NICHT fortgeschrieben (anders als
    create_project_from_contract()) -- das übernimmt sign_report() über
    ServiceReport.advance_due_date_on_sign, siehe dort. Ein angelegter, aber nie unterschriebener
    Bericht soll den Turnus nicht verschieben.

    created_by_employee_id (seit 1.3.56, Rechtekonzept): der Ersteller des vorbereiteten
    Berichts -- für einen Monteur, der vor Ort eine ungeplante Wartung startet, ist das sein
    einziger Zugriffsweg auf den neuen Auftrag (field_may_access_order(), Weg "eigener
    Bericht"): eine Plantafel-Zuordnung existiert für diesen Auftrag noch nicht. Der Router
    setzt den Wert wie bei POST /api/orders/{id}/service-reports über _employee_for_request()."""
    contract = db.get(MaintenanceContract, contract_id)
    if contract is None:
        raise ValueError("Wartungsvertrag nicht gefunden.")
    use_roof_area_items = get_or_create_maintenance_settings(db).use_roof_area_items
    if use_roof_area_items and any(not i.archived for i in contract.items):
        raise ValueError("Dieser Wartungsvertrag hat aktive Positionen -- bitte den Vorgang je Position anlegen.")

    title = f"Wartung {contract.title} vom {date.today().strftime('%d.%m.%Y')}"
    result = create_quick_service_order(
        db, customer_id=contract.customer_id, property_id=contract.property_id,
        order_type="wartung", title=title, caseworker_employee_id=contract.responsible_employee_id,
    )
    profile = get_or_create_project_profile(db, result["project_id"])
    profile.source_maintenance_contract_id = contract.id
    db.commit()

    roof_area_ids = None
    if contract.property_id is not None:
        roof_area_ids = [a["id"] for a in list_roof_areas(db, contract.property_id)] or None

    report = create_report(
        db, order_id=result["order_id"], report_type="wartung", roof_area_ids=roof_area_ids,
        advance_due_date_on_sign=True, created_by_employee_id=created_by_employee_id,
    )
    return {**result, "report_id": report["id"]}


def create_maintenance_contract_from_project(db: Session, project_id: int, *, interval_months: int,
                                              next_due_date: date, responsible_employee_id: int | None = None) -> dict:
    """Rückweg zu create_project_from_contract(): aus einem bestehenden (auch einmalig per
    create_quick_service_order() angelegten) Projekt einen Wartungsvertrag machen, seit 1.2.12.
    Nutzt duplicate_project(as_template=True) -- exakt derselbe Mechanismus, den auch "Als
    Mustervorgang speichern" auf der Projektseite verwendet -- statt das Kopieren erneut
    nachzubauen. Der ursprüngliche Auftrag bleibt unverändert; der neue Mustervorgang ist ein
    separates Projekt."""
    project = db.get(Project, project_id)
    if project is None:
        raise ValueError("Projekt nicht gefunden.")
    if project.is_template:
        raise ValueError(
            "Aus einem Mustervorgang kann kein weiterer Wartungsvertrag erzeugt werden -- bitte "
            "den bestehenden Mustervorgang direkt beim Anlegen eines Wartungsvertrags auswählen."
        )
    template = duplicate_project(db, project, as_template=True)
    return create_contract(
        db, project.customer_id, project.property_id, project.name, interval_months, next_due_date,
        template_project_id=template.id, responsible_employee_id=responsible_employee_id,
    )


# --- Positionen je Dachfläche (MaintenanceContractItem, seit 1.2.15) ---

def create_contract_item(db: Session, contract_id: int, roof_area_id: int, maintenance_window_id: int,
                          description: str | None = None, template_project_id: int | None = None,
                          inspection_template_id: int | None = None, duration_minutes: int | None = None) -> dict:
    if not get_or_create_maintenance_settings(db).use_roof_area_items:
        raise ValueError("Zu wartende Dachflächen sind in den Einstellungen deaktiviert.")
    contract = db.get(MaintenanceContract, contract_id)
    if contract is None:
        raise ValueError("Wartungsvertrag nicht gefunden.")
    if contract.property_id is None:
        raise ValueError("Für Positionen muss dem Wartungsvertrag ein Objekt zugeordnet sein.")
    roof_area = db.get(RoofArea, roof_area_id)
    if roof_area is None:
        raise ValueError("Dachfläche nicht gefunden.")
    if roof_area.property_id != contract.property_id:
        raise ValueError("Diese Dachfläche gehört nicht zum Objekt des Wartungsvertrags.")
    window = db.get(MaintenanceWindow, maintenance_window_id)
    if window is None:
        raise ValueError("Wartungsfenster nicht gefunden.")
    item = MaintenanceContractItem(
        contract_id=contract_id, roof_area_id=roof_area_id, maintenance_window_id=maintenance_window_id,
        template_project_id=template_project_id, inspection_template_id=inspection_template_id,
        description=(description or None), duration_minutes=duration_minutes,
        next_due_date=_next_window_opening(window, after=date.today()),
    )
    db.add(item)
    db.commit()
    lead_days = get_or_create_maintenance_settings(db).reminder_lead_days
    return item_to_dict(_load_item(db, item.id), lead_days)


def update_contract_item(db: Session, item_id: int, roof_area_id: int, maintenance_window_id: int,
                          description: str | None, template_project_id: int | None,
                          inspection_template_id: int | None, duration_minutes: int | None) -> dict | None:
    """Ändert nur die Positions-Metadaten -- next_due_date/last_reminder_due_date bleiben
    unangetastet (das Bearbeiten einer Position darf ihre Fälligkeit nicht zurücksetzen)."""
    item = db.get(MaintenanceContractItem, item_id)
    if item is None:
        return None
    contract = item.contract
    roof_area = db.get(RoofArea, roof_area_id)
    if roof_area is None:
        raise ValueError("Dachfläche nicht gefunden.")
    if roof_area.property_id != contract.property_id:
        raise ValueError("Diese Dachfläche gehört nicht zum Objekt des Wartungsvertrags.")
    window = db.get(MaintenanceWindow, maintenance_window_id)
    if window is None:
        raise ValueError("Wartungsfenster nicht gefunden.")
    item.roof_area_id = roof_area_id
    item.maintenance_window_id = maintenance_window_id
    item.description = description or None
    item.template_project_id = template_project_id
    item.inspection_template_id = inspection_template_id
    item.duration_minutes = duration_minutes
    db.commit()
    lead_days = get_or_create_maintenance_settings(db).reminder_lead_days
    return item_to_dict(_load_item(db, item.id), lead_days)


def set_item_archived(db: Session, item_id: int, archived: bool) -> dict | None:
    item = db.get(MaintenanceContractItem, item_id)
    if item is None:
        return None
    item.archived = archived
    db.commit()
    lead_days = get_or_create_maintenance_settings(db).reminder_lead_days
    return item_to_dict(_load_item(db, item.id), lead_days)


def delete_contract_item(db: Session, item_id: int) -> bool:
    item = db.get(MaintenanceContractItem, item_id)
    if item is None:
        return False
    if db.scalar(
        select(ServiceReport.id).where(
            ServiceReport.maintenance_contract_item_id == item_id, ServiceReport.status == "unterschrieben",
        ).limit(1)
    ):
        raise ValueError(
            "Diese Position hat bereits unterschriebene Einsatzberichte und kann nicht gelöscht werden."
        )
    db.delete(item)
    db.commit()
    return True


# --- Saisonale Wartungsfenster (MaintenanceWindow, seit 1.2.15) ---

def window_to_dict(window: MaintenanceWindow) -> dict:
    return {
        "id": window.id, "label": window.label, "month_from": window.month_from,
        "month_to": window.month_to, "sort_order": window.sort_order,
    }


def list_windows(db: Session) -> list[dict]:
    windows = db.scalars(select(MaintenanceWindow).order_by(MaintenanceWindow.sort_order, MaintenanceWindow.id)).all()
    return [window_to_dict(w) for w in windows]


def _validate_window_months(month_from: int, month_to: int) -> None:
    if not (1 <= month_from <= 12) or not (1 <= month_to <= 12):
        raise ValueError("Start- und Endmonat müssen zwischen 1 und 12 liegen.")


def create_window(db: Session, label: str, month_from: int, month_to: int) -> dict:
    label = label.strip()
    if not label:
        raise ValueError("Bitte eine Bezeichnung angeben.")
    _validate_window_months(month_from, month_to)
    max_sort = db.scalar(select(func.max(MaintenanceWindow.sort_order))) or 0
    window = MaintenanceWindow(label=label, month_from=month_from, month_to=month_to, sort_order=max_sort + 10)
    db.add(window)
    db.commit()
    return window_to_dict(window)


def update_window(db: Session, window_id: int, label: str, month_from: int, month_to: int) -> dict | None:
    window = db.get(MaintenanceWindow, window_id)
    if window is None:
        return None
    label = label.strip()
    if not label:
        raise ValueError("Bitte eine Bezeichnung angeben.")
    _validate_window_months(month_from, month_to)
    window.label = label
    window.month_from = month_from
    window.month_to = month_to
    db.commit()
    return window_to_dict(window)


def reorder_windows(db: Session, ordered_ids: list[int]) -> list[dict]:
    windows_by_id = {w.id: w for w in db.scalars(select(MaintenanceWindow)).all()}
    if set(ordered_ids) != set(windows_by_id.keys()):
        raise ValueError("Die Reihenfolge muss alle vorhandenen Wartungsfenster enthalten.")
    for index, window_id in enumerate(ordered_ids):
        windows_by_id[window_id].sort_order = index * 10
    db.commit()
    return list_windows(db)


def delete_window(db: Session, window_id: int) -> bool:
    """Blockiert (seit 1.2.15), solange eine MaintenanceContractItem noch auf dieses Fenster
    verweist -- SQLite erzwingt Fremdschlüssel in diesem Projekt nicht selbst, siehe
    delete_roof_area() in app/roof_areas.py für dieselbe Begründung."""
    window = db.get(MaintenanceWindow, window_id)
    if window is None:
        return False
    if db.scalar(select(MaintenanceContractItem.id).where(MaintenanceContractItem.maintenance_window_id == window_id).limit(1)):
        raise ValueError("Dieses Wartungsfenster wird noch von mindestens einer Position verwendet.")
    db.delete(window)
    db.commit()
    return True


# --- Übersicht "Fällige Wartungen im Fenster" (seit 1.2.15) ---

def list_due_items_grouped(db: Session) -> list[dict]:
    """Alle fälligen ODER überfälligen Positionen aktiver, nicht archivierter Verträge,
    angereichert mit Objektadresse -- das Frontend gruppiert clientseitig nach PLZ/Ort und
    stellt is_overdue optisch abgesetzt von is_due dar."""
    contracts = list_contracts(db, status="aktiv")
    rows = []
    for contract in contracts:
        for item in contract["items"]:
            if not (item["is_due"] or item["is_overdue"]):
                continue
            rows.append({
                **item,
                "contract_title": contract["title"],
                "customer_name": contract["customer_name"],
                "property_postal_code": contract["property_postal_code"],
                "property_city": contract["property_city"],
            })
    return rows
