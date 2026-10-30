"""abwesenheiten_als_antraege -- jede Abwesenheit hat einen Antrag (seit 1.9.146, Stufe 6, R1, Punkt 4)

„Abwesenheit eintragen“ auf der Plantafel legt seit 1.9.146 einen Antrag an wie unter „Zeiten“. Abwesenheiten, die bis dahin direkt auf der Tafel entstanden, haben keinen
Antrag und fehlten unter „Zeiten → Abwesenheiten“ (Befund Stufe 6, D2). upgrade() legt je solcher Abwesenheit einen genehmigten Antrag an, mit dem Vermerk MERKER, ohne
Antragsteller und ohne Entscheider (nicht bekannt), Zeitpunkt = Anlegen der Abwesenheit.

downgrade(): entfernt genau die Anträge mit dem Vermerk, die noch genehmigt sind und niemand angefasst hat -- der Vorzustand. Keine Spalte ändert sich.

Revision ID: b2c7f4e19a06
Revises: 8d3f6a2c91e7
Create Date: 2026-10-30

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b2c7f4e19a06'
down_revision = '8d3f6a2c91e7'
branch_labels = None
depends_on = None

MERKER = "Auf der Plantafel eingetragen (vor 1.9.146)"


def uebernehmen(bind) -> None:
    bind.execute(sa.text(
        "INSERT INTO employee_absence_requests (employee_id, absence_type, absence_category, start_date, end_date, notes, status, reviewed_at, review_notes, "
        "approved_absence_id, created_at, updated_at) "
        "SELECT a.employee_id, a.absence_type, a.absence_category, a.start_date, a.end_date, a.notes, 'approved', a.created_at, :merker, a.id, a.created_at, a.updated_at "
        "FROM employee_absences a WHERE NOT EXISTS (SELECT 1 FROM employee_absence_requests r WHERE r.approved_absence_id = a.id)"), {"merker": MERKER})


def zuruecknehmen(bind) -> None:
    bind.execute(sa.text("DELETE FROM employee_absence_requests WHERE review_notes = :merker AND status = 'approved' AND requested_by_user_id IS NULL "
                         "AND reviewed_by_user_id IS NULL"), {"merker": MERKER})


def upgrade() -> None:
    uebernehmen(op.get_bind())


def downgrade() -> None:
    zuruecknehmen(op.get_bind())
