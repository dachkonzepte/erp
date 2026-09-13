"""Mängel aus Einsatzberichten (seit 1.2.17, Modul "wartungen") -- macht aus einem negativen
Prüfergebnis eine Handlung: sofort behoben, Büro prüfen lassen oder zurückgestellt, und liefert
damit erstmals eine echte Mängelhistorie je Bauteil.

_execute_finding_action() führt die jeweilige Maßnahme aus, setzt dabei aber NIE finding.action
selbst -- das erledigen create_finding()/update_finding_followup() vorher/nachher, damit beide
Aufrufer sichtbar bleiben, wer die Zuweisung tatsächlich vornimmt. Die Idempotenz einer bereits
ausgeführten Maßnahme hängt (seit einer Planänderung vor dem Bau, siehe update_finding_followup())
NICHT an "war die Maßnahme vorher 'zurueckgestellt'", sondern an ihrem eigenen, einmaligen
Ausführungs-Artefakt -- das erlaubt sowohl das Nachholen einer bei deaktiviertem Aufgabenmodul
ausgefallenen Aufgabe als auch einen jederzeitigen Wechsel weg von "sofort_behoben".

Seit 1.2.21: die früheren, getrennten Maßnahmen "folgeauftrag" (erzeugte sofort einen echten
Auftrag samt Projekt über create_quick_service_order(), mitten im noch nicht unterschriebenen
Bericht) und "angebot_erforderlich" (erzeugte nur eine Aufgabe) sind zu einer einzigen Maßnahme
"buero_pruefen" zusammengeführt -- beide waren fachlich dieselbe Entscheidung ("das muss vom
Büro aus weiterbearbeitet werden"), nur der Monteur auf dem Dach musste vorher raten, ob daraus
ein Angebot oder ein Auftrag wird. "buero_pruefen" erzeugt IMMER nur eine Aufgabe (nie einen
Auftrag/Projekt, kein Navigieren mitten im Bericht) -- der eigentliche Vorgang entsteht erst,
wenn der Sachbearbeiter aus dieser Aufgabe heraus bewusst auf "Vorgang erstellen" klickt (siehe
create_follow_up_project_for_task() unten). Migration ... schreibt bestehende Findings mit den
beiden alten Maßnahmen auf "buero_pruefen" um, OHNE follow_up_order_id/follow_up_project_id/
follow_up_task_id anzufassen -- ein migrierter, ehemals "folgeauftrag"-Mangel trägt daher
weiterhin follow_up_order_id, aber (er hat nie eine Aufgabe erzeugt) kein follow_up_task_id;
_action_already_executed() muss deshalb BEIDE Artefakte prüfen, nicht nur das neue."""

from datetime import date, datetime, timedelta

from sqlalchemy import case, select
from sqlalchemy.orm import Session, selectinload

from .models import Employee, Finding, InspectionItem, Order, Project, RoofComponent, ServiceReport
from .modules import is_module_enabled
from .quick_service_orders import create_quick_service_order
from .tasks import create_task

SEVERITIES = ("gering", "mittel", "dringend", "akute_gefahr")
ACTIONS = ("sofort_behoben", "buero_pruefen", "zurueckgestellt")
STATUSES = ("offen", "in_bearbeitung", "erledigt", "zurueckgestellt")

SEVERITY_RANK = {"akute_gefahr": 4, "dringend": 3, "mittel": 2, "gering": 1}
SEVERITY_LABELS = {"gering": "Gering", "mittel": "Mittel", "dringend": "Dringend", "akute_gefahr": "Akute Gefahr"}
ACTION_LABELS = {
    "sofort_behoben": "Sofort behoben", "buero_pruefen": "Büro prüfen lassen",
    "zurueckgestellt": "Zurückgestellt",
}
STATUS_LABELS = {"offen": "Offen", "in_bearbeitung": "In Bearbeitung", "erledigt": "Erledigt", "zurueckgestellt": "Zurückgestellt"}


def _employee_name(e: Employee | None) -> str | None:
    return f"{e.first_name} {e.last_name}".strip() if e else None


def finding_to_dict(finding: Finding) -> dict:
    report = finding.service_report
    order = report.order if report else None
    project = order.project if order else None
    return {
        "id": finding.id,
        "service_report_id": finding.service_report_id,
        "order_id": order.id if order else None,
        "order_number": order.order_number if order else None,
        "property_id": project.property_id if project else None,
        "property_name": project.property.name if project and project.property else None,
        "customer_name": project.customer.name if project and project.customer else None,
        "inspection_item_id": finding.inspection_item_id,
        "roof_component_id": finding.roof_component_id,
        # Schnappschuss bevorzugt (seit 1.3.12) -- Rückfall auf den aktuellen Namen nur für
        # Bestandszeilen ohne Schnappschuss (siehe Migration).
        "roof_component_name": finding.roof_component_name_snapshot or (finding.roof_component.name if finding.roof_component else None),
        "description": finding.description,
        "severity": finding.severity,
        "severity_label": SEVERITY_LABELS.get(finding.severity, finding.severity),
        "action": finding.action,
        "action_label": ACTION_LABELS.get(finding.action, finding.action),
        "follow_up_order_id": finding.follow_up_order_id,
        "follow_up_project_id": finding.follow_up_project_id,
        "follow_up_task_id": finding.follow_up_task_id,
        "resubmission_date": finding.resubmission_date,
        "status": finding.status,
        "status_label": STATUS_LABELS.get(finding.status, finding.status),
        "closed_at": finding.closed_at,
        "closed_by_employee_id": finding.closed_by_employee_id,
        "closed_by_employee_name": _employee_name(finding.closed_by_employee),
        "created_at": finding.created_at,
        "updated_at": finding.updated_at,
        "created_by_employee_id": finding.created_by_employee_id,
        "client_uuid": finding.client_uuid,
        "photo_count": len(finding.photos),
    }


_LOAD_OPTIONS = (
    selectinload(Finding.roof_component),
    selectinload(Finding.closed_by_employee),
    selectinload(Finding.created_by_employee),
    selectinload(Finding.photos),
    selectinload(Finding.service_report).selectinload(ServiceReport.order),
)


def _load_finding(db: Session, finding_id: int) -> Finding | None:
    return db.scalar(select(Finding).options(*_LOAD_OPTIONS).where(Finding.id == finding_id))


def list_findings_for_report(db: Session, service_report_id: int) -> list[dict]:
    query = (
        select(Finding).options(*_LOAD_OPTIONS)
        .where(Finding.service_report_id == service_report_id)
        .order_by(Finding.id)
    )
    return [finding_to_dict(f) for f in db.scalars(query).all()]


def list_findings(
    db: Session, status: str | None = None, severity: str | None = None, property_id: int | None = None,
    overdue_only: bool = False, date_from: date | None = None, date_to: date | None = None,
) -> list[dict]:
    """Mängelliste über alle Objekte -- sortiert nach Schweregrad absteigend, dann
    Wiedervorlage aufsteigend (ohne Wiedervorlagedatum zuletzt). property_id löst über
    service_report -> order -> project auf (Order/ServiceReport selbst tragen kein
    property_id), gleiches Auflösungsprinzip wie list_property_history()."""
    query = select(Finding).options(*_LOAD_OPTIONS)
    if property_id is not None:
        query = (
            query.join(ServiceReport, Finding.service_report_id == ServiceReport.id)
            .join(Order, ServiceReport.order_id == Order.id)
            .join(Project, Order.project_id == Project.id)
            .where(Project.property_id == property_id)
        )
    if status is not None:
        query = query.where(Finding.status == status)
    if severity is not None:
        query = query.where(Finding.severity == severity)
    if date_from is not None:
        query = query.where(Finding.created_at >= datetime.combine(date_from, datetime.min.time()))
    if date_to is not None:
        query = query.where(Finding.created_at < datetime.combine(date_to + timedelta(days=1), datetime.min.time()))
    if overdue_only:
        query = query.where(
            Finding.action == "zurueckgestellt", Finding.resubmission_date.is_not(None),
            Finding.resubmission_date <= date.today(), Finding.status != "erledigt",
        )
    severity_rank = case(
        (Finding.severity == "akute_gefahr", 4), (Finding.severity == "dringend", 3),
        (Finding.severity == "mittel", 2), (Finding.severity == "gering", 1), else_=0,
    )
    query = query.order_by(severity_rank.desc(), Finding.resubmission_date.is_(None), Finding.resubmission_date)
    return [finding_to_dict(f) for f in db.scalars(query).all()]


def list_findings_for_component(db: Session, roof_component_id: int) -> list[dict]:
    """Mängelhistorie eines Bauteils, chronologisch nach Einsatzdatum des jeweiligen
    Berichts (nicht nach Finding.created_at, das nur den Erfassungszeitpunkt trägt)."""
    query = (
        select(Finding).options(*_LOAD_OPTIONS)
        .join(ServiceReport, Finding.service_report_id == ServiceReport.id)
        .where(Finding.roof_component_id == roof_component_id)
        .order_by(ServiceReport.performed_at, Finding.id)
    )
    return [finding_to_dict(f) for f in db.scalars(query).all()]


def _action_already_executed(finding: Finding, action: str) -> bool:
    """Die Idempotenzsperre einer Maßnahme hängt an IHREM EIGENEN Ausführungs-Artefakt, nicht
    an finding.action selbst -- siehe Moduldocstring. sofort_behoben/zurueckgestellt haben kein
    einmaliges externes Artefakt und sind daher nie gesperrt.

    buero_pruefen prüft BEIDE Artefakte (follow_up_task_id UND follow_up_order_id), nicht nur
    das neue -- ein per Migration auf buero_pruefen umgeschriebener, ehemals "folgeauftrag"-
    Mangel trägt nur follow_up_order_id (er hat nie eine Aufgabe erzeugt); ohne diese zweite
    Prüfung wäre er fälschlich nicht gesperrt und ein erneuter Klick würde eine überflüssige
    zweite Aufgabe für einen Mangel erzeugen, der bereits einen Auftrag hat."""
    if action == "buero_pruefen":
        return finding.follow_up_task_id is not None or finding.follow_up_order_id is not None
    return False


def _execute_finding_action(
    db: Session, finding: Finding, action: str, resubmission_date: date | None = None,
    employee_id: int | None = None,
) -> None:
    """Führt eine Mangel-Maßnahme aus (kein eigenständiger Commit). Setzt finding.action nicht
    selbst -- siehe Moduldocstring."""
    if action == "sofort_behoben":
        finding.status = "erledigt"
        finding.closed_at = datetime.utcnow()
        finding.closed_by_employee_id = employee_id
    elif action == "buero_pruefen":
        # Erzeugt bewusst NUR eine Aufgabe, nie einen Auftrag/Projekt -- der eigentliche Vorgang
        # entsteht erst durch einen bewussten Klick des Sachbearbeiters aus dieser Aufgabe
        # heraus (create_follow_up_project_for_task() unten), nicht mehr automatisch beim
        # Anlegen des Mangels mitten im noch nicht unterschriebenen Bericht. Bei deaktiviertem
        # Aufgabenmodul entfällt die Aufgabe ersatzlos -- der Mangel bleibt gültig und behält
        # seinen aktuellen Status (bei Neuanlage "offen"). Das fehlende follow_up_task_id ist
        # zugleich das Signal, die Maßnahme später nachzuholen (siehe _action_already_executed()).
        if is_module_enabled(db, "aufgabenmanagement"):
            report = finding.service_report
            order = report.order
            title = (finding.description.strip().splitlines()[0] or "Mangel")[:200]
            task = create_task(
                db, title=f"Büro prüfen lassen: {title}",
                description=f"Mangel im Einsatzbericht zu Auftrag {order.order_number}:\n\n{finding.description}",
                assigned_employee_id=order.caseworker_employee_id, project_id=order.project_id,
                source_module="wartungsbericht", source_label=f"Mangel Auftrag {order.order_number}",
                source_url=f"/orders/{order.id}/service-reports",
            )
            finding.follow_up_task_id = task["id"]
            finding.status = "in_bearbeitung"
    elif action == "zurueckgestellt":
        if resubmission_date is None:
            raise ValueError("Bitte ein Wiedervorlagedatum angeben.")
        finding.resubmission_date = resubmission_date
        finding.status = "offen"
    else:
        raise ValueError(f"Unbekannte Maßnahme: {action}")


def get_finding_for_task(db: Session, task_id: int) -> dict | None:
    """Rückrichtung von einer Aufgabe zum Mangel, der sie erzeugt hat (seit 1.2.21) -- über die
    bereits bestehende Finding.follow_up_task_id, keine neue Spalte an Task. Liefert None, wenn
    die Aufgabe nicht aus einem Mangel entstanden ist (z. B. manuell angelegt oder aus einem
    anderen Modul)."""
    finding = db.scalar(select(Finding).options(*_LOAD_OPTIONS).where(Finding.follow_up_task_id == task_id))
    return finding_to_dict(finding) if finding else None


def create_follow_up_project_for_task(db: Session, task_id: int) -> dict:
    """Erzeugt den eigentlichen Vorgang (Projekt+Auftrag über create_quick_service_order()) aus
    der Aufgabe heraus (seit 1.2.21) -- das, was die Maßnahme "folgeauftrag" früher sofort beim
    Anlegen des Mangels getan hat, jetzt ein bewusster Klick des Sachbearbeiters, der am
    Schreibtisch sitzt und entscheidet, nicht mehr der Monteur mitten in der Erfassung."""
    finding = db.scalar(select(Finding).options(*_LOAD_OPTIONS).where(Finding.follow_up_task_id == task_id))
    if finding is None:
        raise ValueError("Zu dieser Aufgabe wurde kein Mangel gefunden.")
    if finding.follow_up_order_id is not None:
        raise ValueError("Für diesen Mangel wurde bereits ein Vorgang erstellt.")
    report = finding.service_report
    order = report.order
    project = order.project
    title = (finding.description.strip().splitlines()[0] or "Mangel")[:200]
    result = create_quick_service_order(
        db, customer_id=project.customer_id, property_id=project.property_id, order_type="reparatur",
        title=f"Folgeauftrag: {title}",
        description=(
            f"{finding.description}\n\nErstellt aus Mangel im Einsatzbericht {report.id} "
            f"(Auftrag {order.order_number}) am {date.today():%d.%m.%Y}."
        ),
        caseworker_employee_id=order.caseworker_employee_id,
    )
    finding.follow_up_project_id = result["project_id"]
    finding.follow_up_order_id = result["order_id"]
    finding.status = "in_bearbeitung"
    db.commit()
    return result


def create_finding(
    db: Session, service_report_id: int, description: str, severity: str, action: str,
    inspection_item_id: int | None = None, roof_component_id: int | None = None,
    resubmission_date: date | None = None, created_by_employee_id: int | None = None,
) -> dict:
    report = db.get(ServiceReport, service_report_id)
    if report is None:
        raise ValueError("Bericht nicht gefunden.")
    if report.status == "unterschrieben":
        raise ValueError("Zu einem bereits unterschriebenen Bericht können keine neuen Mängel angelegt werden.")
    description = description.strip()
    if not description:
        raise ValueError("Bitte eine Beschreibung angeben.")
    if severity not in SEVERITIES:
        raise ValueError(f"Unbekannter Schweregrad: {severity}")
    if action not in ACTIONS:
        raise ValueError(f"Unbekannte Maßnahme: {action}")
    if inspection_item_id is not None:
        item = db.get(InspectionItem, inspection_item_id)
        if item is None or item.service_report_id != service_report_id:
            raise ValueError("Prüfpunkt nicht gefunden.")
        # roof_component_id wird aus dem Prüfpunkt übernommen, falls der Mangel aus ihm
        # entsteht -- ein ggf. mitgegebener Wert wird dabei bewusst überschrieben.
        roof_component_id = item.roof_component_id

    # Physischer Namens-Schnappschuss (seit 1.3.12, CLAUDE.md "Eingefrorene Bauteil-/
    # Dachflächennamen") -- dasselbe Prinzip wie InspectionItem.text seit 1.2.16: ein Mangel ist
    # nach der Unterschrift des Berichts unveränderlich, durfte aber bisher über
    # finding.roof_component.name den AKTUELLEN (ggf. seither umbenannten) Namen zeigen.
    roof_component_name_snapshot = None
    if roof_component_id is not None:
        component = db.get(RoofComponent, roof_component_id)
        roof_component_name_snapshot = component.name if component else None

    finding = Finding(
        service_report_id=service_report_id, inspection_item_id=inspection_item_id,
        roof_component_id=roof_component_id, roof_component_name_snapshot=roof_component_name_snapshot,
        description=description, severity=severity,
        action=action, created_by_employee_id=created_by_employee_id,
    )
    db.add(finding)
    db.flush()
    try:
        _execute_finding_action(db, finding, action, resubmission_date=resubmission_date, employee_id=created_by_employee_id)
    except ValueError:
        # Ohne Rollback bliebe die bereits geflushte (aber nie committete) Finding-Zeile im
        # offenen Transaktionszustand der Session hängen und würde beim nächsten -- völlig
        # unabhängigen -- erfolgreichen db.commit() dieser Session stillschweigend mit
        # übernommen, obwohl diese Anlage fehlgeschlagen ist.
        db.rollback()
        raise
    db.commit()
    return finding_to_dict(_load_finding(db, finding.id))


def update_finding_followup(
    db: Session, finding_id: int, *, status: str | None = None, action: str | None = None,
    resubmission_date: date | None = None, closed_by_employee_id: int | None = None,
) -> dict | None:
    """Die einzige Stelle, die einen Finding auch nach der Unterschrift des zugehörigen
    Berichts noch ändern darf (Muster: sign_report()/update_report() -- eine schmale, eigene
    Funktion neben dem allgemeinen, nach der Unterschrift blockierten Bearbeitungspfad).
    Eingefroren bleibt die FESTSTELLUNG (description, severity, Bauteilbezug, Fotos) -- lebendig
    bleibt ausschließlich ihre NACHVERFOLGUNG: status, ein Wechsel der Maßnahme, resubmission_date,
    closed_at/closed_by_employee_id. Ein Wechsel der Maßnahme ist erlaubt, sofern ihr eigenes
    Ausführungs-Artefakt noch fehlt (siehe _action_already_executed()); ein Wechsel WEG von
    "sofort_behoben" setzt closed_at/closed_by_employee_id zurück, bevor die neue Maßnahme
    ausgeführt wird."""
    finding = db.get(Finding, finding_id)
    if finding is None:
        return None
    if status is not None and status not in STATUSES:
        raise ValueError(f"Unbekannter Status: {status}")
    if action is not None and action not in ACTIONS:
        raise ValueError(f"Unbekannte Maßnahme: {action}")

    if action is not None:
        # Bewusst NICHT auf "action != finding.action" geprüft: das "Nachholen" einer bei
        # deaktiviertem Aufgabenmodul ausgefallenen Aufgabe wählt exakt dieselbe Maßnahme
        # ("angebot_erforderlich") erneut aus -- die Sperre hängt ausschließlich am Artefakt.
        if _action_already_executed(finding, action):
            raise ValueError("Diese Maßnahme wurde für diesen Mangel bereits ausgeführt.")
        if finding.action == "sofort_behoben" and action != "sofort_behoben":
            finding.closed_at = None
            finding.closed_by_employee_id = None
        finding.action = action
        try:
            _execute_finding_action(db, finding, action, resubmission_date=resubmission_date, employee_id=closed_by_employee_id)
        except ValueError:
            # Ohne Rollback blieben die eben vorgenommenen, noch nicht committeten
            # Änderungen (action, ggf. zurückgesetztes closed_at) als Karteileiche in der
            # Session hängen und würden vom nächsten -- völlig unabhängigen -- erfolgreichen
            # db.commit() dieser Session mit übernommen, obwohl dieser Wechsel fehlgeschlagen ist.
            db.rollback()
            raise

    if status is not None:
        finding.status = status
        if status == "erledigt":
            finding.closed_at = datetime.utcnow()
            finding.closed_by_employee_id = closed_by_employee_id
    if resubmission_date is not None:
        finding.resubmission_date = resubmission_date

    db.commit()
    return finding_to_dict(_load_finding(db, finding.id))
