"""findings_folgeauftrag_angebot_zu_buero_pruefen

Revision ID: 9e3bb642c686
Revises: 4609e3fc8976
Create Date: 2026-09-10 07:51:54.459295

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9e3bb642c686'
down_revision = '4609e3fc8976'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Reine Daten-Migration, kein Schema-Change -- Finding.action ist ein einfacher String ohne
    # DB-Enum. Die beiden früheren Maßnahmen "folgeauftrag" und "angebot_erforderlich" sind
    # fachlich zu einer einzigen Maßnahme "buero_pruefen" zusammengeführt (siehe app/findings.py,
    # Moduldocstring). follow_up_order_id/follow_up_project_id/follow_up_task_id bleiben dabei
    # bewusst unverändert -- ein ehemals "folgeauftrag"-Mangel behält seinen bereits erzeugten
    # Auftrag/Projekt, ein ehemals "angebot_erforderlich"-Mangel seine bereits erzeugte Aufgabe.
    op.execute("UPDATE findings SET action = 'buero_pruefen' WHERE action IN ('folgeauftrag', 'angebot_erforderlich')")


def downgrade() -> None:
    # Nicht umkehrbar ohne Informationsverlust -- welche der beiden alten Maßnahmen ein
    # "buero_pruefen"-Mangel ursprünglich war, ist nach dem Upgrade nicht mehr unterscheidbar
    # (außer indirekt über follow_up_order_id vs. follow_up_task_id, was hier bewusst nicht
    # automatisch zurückgerechnet wird, um keine falsche Sicherheit über die historische Wahl
    # vorzutäuschen).
    pass
