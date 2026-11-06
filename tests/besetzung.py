"""Seit 1.9.233 (Stufe 6, R3a, Punkt 2): die Personen eines Einsatzes stehen am Einsatz (PlanningSlotEmployee), seit 1.9.234 auch seine Geräte
(PlanningSlotResource). Ein Test, der einen Einsatz direkt anlegt wie ein Bestand von vor 1.9.233 (Kolonnen-Zuweisung mit Schnappschuss,
Einzelzuweisung an der AV), gibt ihm mit wie_migration() die Besetzung und die Geräte, die die Migrationen e4b1c9d27a35 und f2c8d4a61e93 ihm gäben:
erst die Personen des Schnappschusses, dann die Einzelzuweisungen der Arbeitsvorbereitung, jede einmal; die Geräte des Schnappschusses, alle Tage."""

from sqlalchemy import select

from app.models import (PlanningSlot, PlanningSlotEmployee, PlanningSlotResource, WorkPreparationEmployee, WorkPreparationTeamEmployee,
                        WorkPreparationTeamResource)


def wie_migration(db, *slots: PlanningSlot) -> None:
    """Für jeden Einsatz ohne Besetzung (flusht vorher, committet nicht)."""
    db.flush()
    for slot in slots:
        if db.scalar(select(PlanningSlotEmployee.id).where(PlanningSlotEmployee.slot_id == slot.id).limit(1)) is not None:
            continue
        ids: list[int] = []
        if slot.team_assignment_id is not None:
            ids += list(db.scalars(select(WorkPreparationTeamEmployee.employee_id)
                                   .where(WorkPreparationTeamEmployee.assignment_id == slot.team_assignment_id).order_by(WorkPreparationTeamEmployee.id)))
        ids += list(db.scalars(select(WorkPreparationEmployee.employee_id)
                               .where(WorkPreparationEmployee.preparation_id == slot.preparation_id).order_by(WorkPreparationEmployee.id)))
        gesehen: list[int] = []
        for eid in ids:
            if eid not in gesehen:
                gesehen.append(eid)
                db.add(PlanningSlotEmployee(slot_id=slot.id, employee_id=eid))
        if slot.team_assignment_id is not None and db.scalar(select(PlanningSlotResource.id).where(PlanningSlotResource.slot_id == slot.id).limit(1)) is None:
            geraete: list[int] = []
            for rid in db.scalars(select(WorkPreparationTeamResource.resource_id)
                                  .where(WorkPreparationTeamResource.assignment_id == slot.team_assignment_id).order_by(WorkPreparationTeamResource.id)):
                if rid is not None and rid not in geraete:
                    geraete.append(rid)
                    db.add(PlanningSlotResource(slot_id=slot.id, resource_id=rid))
    db.flush()


def alle_wie_migration(db) -> None:
    """Jeder Einsatz der Datenbank ohne Besetzung bekommt sie wie nach der Migration."""
    wie_migration(db, *db.scalars(select(PlanningSlot)).all())
