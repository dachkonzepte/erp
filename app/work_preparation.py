from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy import select, case
from sqlalchemy.orm import Session, selectinload

from .models import (
    Employee, Order, OrderItem, OrderItemCalculationSnapshot, WorkPreparation,
    WorkPreparationEmployee, WorkPreparationTask, WorkPreparationMaterial,
    WorkPreparationMaterialSupplier, WorkPreparationTeamAssignment,
    WorkPreparationTeamEmployee, WorkPreparationTeamResource, WorkPreparationDeliveryNote,
    WorkPreparationMaterialDeliveryNote,
)
from .time_tracking import order_actual_hours, order_item_actual_hours

QTY = Decimal("0.001")
HOUR = Decimal("0.01")


def _d(v):
    return Decimal(v or 0)


def employee_name(e: Employee | None):
    return f"{e.first_name} {e.last_name}".strip() if e else None


def load_preparation(db: Session, order_id: int) -> WorkPreparation | None:
    return db.scalar(
        select(WorkPreparation)
        .options(
            selectinload(WorkPreparation.order).selectinload(Order.project),
            selectinload(WorkPreparation.employees).selectinload(WorkPreparationEmployee.employee),
            selectinload(WorkPreparation.tasks).selectinload(WorkPreparationTask.assigned_employee),
            selectinload(WorkPreparation.materials),
        )
        .where(WorkPreparation.order_id == order_id)
    )


def _load_order_full(db: Session, order_id: int) -> Order | None:
    return db.scalar(
        select(Order)
        .options(
            selectinload(Order.project),
            selectinload(Order.items)
              .selectinload(OrderItem.calculation_snapshot)
              .selectinload(OrderItemCalculationSnapshot.materials),
        )
        .where(Order.id == order_id)
    )


def ensure_preparation(db: Session, order_id: int) -> WorkPreparation:
    prep = load_preparation(db, order_id)
    if prep is not None:
        return prep
    order = _load_order_full(db, order_id)
    if order is None:
        raise ValueError("Auftrag nicht gefunden.")
    prep = WorkPreparation(
        order_id=order.id,
        status="offen",
        planned_start=order.execution_start,
        planned_end=order.execution_end,
    )
    db.add(prep)
    db.flush()
    for item in order.items:
        calc = item.calculation_snapshot
        if calc is None:
            continue
        for m in calc.materials:
            effective_per_unit = _d(m.quantity) * (Decimal("1") + _d(m.waste_pct) / Decimal("100"))
            total = (effective_per_unit * _d(item.quantity)).quantize(QTY, rounding=ROUND_HALF_UP)
            db.add(WorkPreparationMaterial(
                preparation_id=prep.id,
                source_material_snapshot_id=m.id,
                source_order_item_id=item.id,
                article_number=m.article_number,
                name=m.name,
                unit=m.unit,
                calculated_quantity=total,
                planned_quantity=total,
                status="bedarf",
            ))
    db.commit()
    return load_preparation(db, order_id)


def planned_hours(order: Order) -> Decimal:
    total = Decimal("0")
    for item in order.items:
        calc = item.calculation_snapshot
        if calc:
            total += ((_d(calc.site_time_minutes) + _d(calc.workshop_time_minutes)) / Decimal("60")) * _d(item.quantity)
    return total.quantize(HOUR, rounding=ROUND_HALF_UP)


def preparation_to_dict(db: Session, prep: WorkPreparation) -> dict:
    order = _load_order_full(db, prep.order_id)
    hours = planned_hours(order)
    employee_hours = sum((_d(x.planned_hours) for x in prep.employees), Decimal("0")).quantize(HOUR)
    open_tasks = sum(1 for t in prep.tasks if t.status != "erledigt")
    supplier_links = {x.material_id: x for x in db.scalars(
        select(WorkPreparationMaterialSupplier).options(selectinload(WorkPreparationMaterialSupplier.supplier))
        .join(WorkPreparationMaterial, WorkPreparationMaterial.id == WorkPreparationMaterialSupplier.material_id)
        .where(WorkPreparationMaterial.preparation_id == prep.id)
    ).all()}
    material_delivery_links = {}
    for link in db.scalars(
        select(WorkPreparationMaterialDeliveryNote)
        .options(
            selectinload(WorkPreparationMaterialDeliveryNote.delivery_note).selectinload(WorkPreparationDeliveryNote.document),
            selectinload(WorkPreparationMaterialDeliveryNote.delivery_note).selectinload(WorkPreparationDeliveryNote.supplier),
        )
        .join(WorkPreparationMaterial, WorkPreparationMaterial.id == WorkPreparationMaterialDeliveryNote.material_id)
        .where(WorkPreparationMaterial.preparation_id == prep.id)
    ).all():
        note=link.delivery_note
        material_delivery_links.setdefault(link.material_id,[]).append({
            "id": note.id,
            "delivery_note_number": note.delivery_note_number,
            "supplier_id": note.supplier_id,
            "supplier_name": note.supplier.name if note.supplier else None,
            "filename": note.document.original_filename if note.document else None,
            "project_document_id": note.project_document_id,
            "document_date": note.document_date,
        })
    material_rows = []
    for m in prep.materials:
        source_item = db.get(OrderItem, m.source_order_item_id) if m.source_order_item_id else None
        sl = supplier_links.get(m.id)
        material_rows.append({
            "id": m.id,
            "article_number": m.article_number,
            "name": m.name,
            "unit": m.unit,
            "calculated_quantity": m.calculated_quantity,
            "planned_quantity": m.planned_quantity,
            "status": m.status,
            "supplier_id": sl.supplier_id if sl else None,
            "supplier": sl.supplier.name if sl and sl.supplier else m.supplier,
            "notes": m.notes,
            "source_order_item_id": m.source_order_item_id,
            "source_position": (source_item.gaeb_oz or source_item.position_number) if source_item else None,
            "source_short_text": source_item.short_text if source_item else None,
            "delivery_notes": material_delivery_links.get(m.id, []),
        })
    team_rows = []
    assignments = db.scalars(
        select(WorkPreparationTeamAssignment)
        .options(
            selectinload(WorkPreparationTeamAssignment.employees).selectinload(WorkPreparationTeamEmployee.employee),
            selectinload(WorkPreparationTeamAssignment.resources).selectinload(WorkPreparationTeamResource.resource),
        )
        .where(WorkPreparationTeamAssignment.preparation_id == prep.id)
        .order_by(WorkPreparationTeamAssignment.id)
    ).all()
    for a in assignments:
        team_rows.append({
            "id": a.id, "team_id": a.team_id, "team_name": a.team_name_snapshot, "notes": a.notes,
            "employees": [{
                "employee_id": x.employee_id, "employee_name": x.employee_name_snapshot, "role": x.role_snapshot
            } for x in a.employees],
            "resources": [{
                "resource_id": x.resource_id, "resource_name": x.resource_name_snapshot,
                "resource_type": x.resource_type_snapshot, "role": x.role_snapshot
            } for x in a.resources],
        })
    delivery_rows = []
    notes = db.scalars(
        select(WorkPreparationDeliveryNote)
        .options(selectinload(WorkPreparationDeliveryNote.document), selectinload(WorkPreparationDeliveryNote.supplier))
        .where(WorkPreparationDeliveryNote.preparation_id == prep.id)
        .order_by(WorkPreparationDeliveryNote.created_at.desc(), WorkPreparationDeliveryNote.id.desc())
    ).all()
    for x in notes:
        delivery_rows.append({
            "id": x.id, "project_document_id": x.project_document_id,
            "filename": x.document.original_filename if x.document else None,
            "content_type": x.document.content_type if x.document else None,
            "supplier_id": x.supplier_id, "supplier_name": x.supplier.name if x.supplier else None,
            "delivery_note_number": x.delivery_note_number,
            "document_date": x.document_date, "notes": x.notes, "created_at": x.created_at,
        })
    actual = order_actual_hours(db, order.id)
    item_actual = order_item_actual_hours(db, order.id)
    planned = hours
    productive_actual = actual["productive_hours"]
    return {
        "id": prep.id,
        "order_id": order.id,
        "order_number": order.order_number,
        "project_id": order.project_id,
        "project_number": order.project.project_number,
        "project_name": order.project.name,
        "status": prep.status,
        "planned_start": prep.planned_start,
        "planned_end": prep.planned_end,
        "site_notes": prep.site_notes,
        "material_notes": prep.material_notes,
        "planned_total_hours": planned,
        "actual_total_hours": productive_actual,
        "actual_travel_hours": actual["travel_hours"],
        "actual_all_hours": actual["total_hours"],
        "hours_variance": (productive_actual - planned).quantize(HOUR),
        "time_by_type": actual["by_type"],
        "order_item_actual_hours": {str(k): v for k, v in item_actual.items()},
        "assigned_planned_hours": employee_hours,
        "open_task_count": open_tasks,
        "material_count": len(material_rows),
        "employees": [{
            "id": x.id, "employee_id": x.employee_id, "employee_name": employee_name(x.employee),
            "role": x.role, "planned_hours": x.planned_hours, "notes": x.notes,
        } for x in prep.employees],
        "teams": team_rows,
        "tasks": [{
            "id": x.id, "title": x.title, "status": x.status, "priority": x.priority,
            "due_date": x.due_date, "assigned_employee_id": x.assigned_employee_id,
            "assigned_employee_name": employee_name(x.assigned_employee), "notes": x.notes,
            "sort_order": x.sort_order,
        } for x in sorted(prep.tasks, key=lambda r:(r.sort_order,r.id))],
        "materials": material_rows,
        "delivery_notes": delivery_rows,
    }


def _material_match_key(item: OrderItem | None, article_number, name, unit):
    position_key = ""
    if item is not None:
        position_key = (item.source_external_id or item.gaeb_oz or item.position_number or item.short_text or "").strip()
    return (position_key, (article_number or "").strip(), (name or "").strip(), (unit or "").strip())



def capture_preparation_material_state(db: Session, order_id: int) -> dict:
    prep = load_preparation(db, order_id)
    if prep is None:
        return {}
    preserved = {}
    links = {x.material_id:x for x in db.scalars(
        select(WorkPreparationMaterialSupplier)
        .join(WorkPreparationMaterial, WorkPreparationMaterial.id==WorkPreparationMaterialSupplier.material_id)
        .where(WorkPreparationMaterial.preparation_id==prep.id)
    ).all()}
    delivery_links = {}
    for x in db.scalars(
        select(WorkPreparationMaterialDeliveryNote)
        .join(WorkPreparationMaterial, WorkPreparationMaterial.id==WorkPreparationMaterialDeliveryNote.material_id)
        .where(WorkPreparationMaterial.preparation_id==prep.id)
    ).all():
        delivery_links.setdefault(x.material_id,[]).append(x.delivery_note_id)
    for row in prep.materials:
        old_item = db.get(OrderItem, row.source_order_item_id) if row.source_order_item_id else None
        key = _material_match_key(old_item, row.article_number, row.name, row.unit)
        custom_plan = _d(row.planned_quantity) != _d(row.calculated_quantity)
        preserved[key] = {
            "planned_quantity": row.planned_quantity,
            "custom_plan": custom_plan,
            "status": row.status,
            "supplier": row.supplier,
            "supplier_id": links.get(row.id).supplier_id if links.get(row.id) else None,
            "notes": row.notes,
            "delivery_note_ids": delivery_links.get(row.id, []),
        }
    return preserved


def list_open_tasks(db: Session, employee_id: int | None = None) -> list[dict]:
    """Offene Arbeitsvorbereitungs-Aufgaben über alle Aufträge hinweg, fürs
    Dashboard-Widget "Meine Aufgaben" (seit 1.0.102). employee_id=None liefert
    alle offenen Aufgaben -- die Rechteprüfung (nur Admins dürfen das) liegt
    beim aufrufenden Router, siehe get_absence_requests() als Vorbild."""
    query = (
        select(WorkPreparationTask)
        .options(
            selectinload(WorkPreparationTask.preparation)
              .selectinload(WorkPreparation.order)
              .selectinload(Order.project),
        )
        .where(WorkPreparationTask.status != "erledigt")
    )
    if employee_id is not None:
        query = query.where(WorkPreparationTask.assigned_employee_id == employee_id)
    query = query.order_by(
        case((WorkPreparationTask.due_date.is_(None), 1), else_=0),
        WorkPreparationTask.due_date,
    )
    result = []
    for t in db.scalars(query).all():
        order = t.preparation.order
        result.append({
            "id": t.id,
            "title": t.title,
            "status": t.status,
            "priority": t.priority,
            "due_date": t.due_date,
            "assigned_employee_id": t.assigned_employee_id,
            "order_id": order.id,
            "order_number": order.order_number,
            "project_id": order.project_id,
            "project_number": order.project.project_number,
            "project_name": order.project.name,
        })
    return result


def refresh_preparation_materials(db: Session, order_id: int, preserved: dict | None = None) -> WorkPreparation | None:
    """Synchronisiert den AV-Materialbedarf mit dem aktuellen Auftragsstand.

    Manuelle Dispositionsdaten (Lieferant, Status, Notiz sowie bewusst geänderte
    Planmenge) werden für fachlich wiedererkennbare Materialpositionen erhalten.
    """
    prep = load_preparation(db, order_id)
    if prep is None:
        return None
    if preserved is None:
        preserved = capture_preparation_material_state(db, order_id)
    order = _load_order_full(db, order_id)
    if order is None:
        return prep

    previous_audit_flag = db.info.get("audit_disabled", False)
    db.info["audit_disabled"] = True
    try:
        old_material_ids=[row.id for row in prep.materials]
        if old_material_ids:
            for link in db.scalars(select(WorkPreparationMaterialSupplier).where(WorkPreparationMaterialSupplier.material_id.in_(old_material_ids))).all():
                db.delete(link)
            for link in db.scalars(select(WorkPreparationMaterialDeliveryNote).where(WorkPreparationMaterialDeliveryNote.material_id.in_(old_material_ids))).all():
                db.delete(link)
        for row in list(prep.materials):
            db.delete(row)
        db.flush()

        for item in order.items:
            calc = item.calculation_snapshot
            if calc is None:
                continue
            for m in calc.materials:
                effective_per_unit = _d(m.quantity) * (Decimal("1") + _d(m.waste_pct) / Decimal("100"))
                total = (effective_per_unit * _d(item.quantity)).quantize(QTY, rounding=ROUND_HALF_UP)
                key = _material_match_key(item, m.article_number, m.name, m.unit)
                old = preserved.get(key)
                planned = old["planned_quantity"] if old and old["custom_plan"] else total
                new_row=WorkPreparationMaterial(
                    preparation_id=prep.id,
                    source_material_snapshot_id=m.id,
                    source_order_item_id=item.id,
                    article_number=m.article_number,
                    name=m.name,
                    unit=m.unit,
                    calculated_quantity=total,
                    planned_quantity=planned,
                    status=(old["status"] if old else "bedarf"),
                    supplier=(old["supplier"] if old else None),
                    notes=(old["notes"] if old else None),
                )
                db.add(new_row); db.flush()
                if old and old.get("supplier_id"):
                    db.add(WorkPreparationMaterialSupplier(material_id=new_row.id,supplier_id=old["supplier_id"]))
                if old:
                    for delivery_note_id in old.get("delivery_note_ids",[]):
                        if db.get(WorkPreparationDeliveryNote,delivery_note_id):
                            db.add(WorkPreparationMaterialDeliveryNote(material_id=new_row.id,delivery_note_id=delivery_note_id))
        db.commit()
    finally:
        db.info["audit_disabled"] = previous_audit_flag
    return load_preparation(db, order_id)
