"""datev_berater_mandant -- Berater- und Mandantennummer für den DATEV-Export (seit 1.9.92)

- time_tracking_settings.datev_beraternummer (String(7), leer erlaubt): DATEV-Beraternummer, 4 bis 7 Ziffern, ab 1001
- time_tracking_settings.datev_mandantennummer (String(5), leer erlaubt): DATEV-Mandantennummer, 1 bis 5 Ziffern, ab 1

Beide stehen im Kopf des LODAS-Exports ([Allgemein] BeraterNr/MandantenNr); ohne sie lehnt der DATEV-Export ab
(app/time_backoffice.py::datev_fehlt()). Eingetragen nur vom Admin (PUT /api/time-backoffice/datev-nummern).

Ändert keine vorhandenen Daten: beide Spalten bleiben leer, bis ein Admin sie einträgt.

downgrade(): verweigert, solange eine Nummer eingetragen ist -- sie ginge verloren; ohne entfernt es die Spalten.

Revision ID: 750d709a4863
Revises: c4f2a8e61d35
Create Date: 2026-10-26

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '750d709a4863'
down_revision = 'c4f2a8e61d35'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('time_tracking_settings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('datev_beraternummer', sa.String(length=7), nullable=True))
        batch_op.add_column(sa.Column('datev_mandantennummer', sa.String(length=5), nullable=True))


def downgrade() -> None:
    anzahl = op.get_bind().execute(sa.text(
        "SELECT count(*) FROM time_tracking_settings WHERE datev_beraternummer IS NOT NULL OR datev_mandantennummer IS NOT NULL")).scalar()
    if anzahl:
        raise RuntimeError("Downgrade verweigert: Berater- oder Mandantennummer ist eingetragen -- sie ginge verloren.")
    with op.batch_alter_table('time_tracking_settings', schema=None) as batch_op:
        batch_op.drop_column('datev_mandantennummer')
        batch_op.drop_column('datev_beraternummer')
