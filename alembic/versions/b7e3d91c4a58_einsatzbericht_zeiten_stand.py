"""einsatzbericht_zeiten_stand -- die Zeiten eines Einsatzberichts mit der Unterschrift gespeichert (seit 1.9.42)

- service_reports.time_rows_json (Text, leer erlaubt): die Zeilen „Tag, Person, von–bis, Stunden“ des Berichtstags, wie sie bei der
  Unterschrift angezeigt waren (app/service_reports.py::zeiten_des_berichts()).

Ändert keine vorhandenen Daten: jeder schon unterschriebene Bericht bleibt ohne gespeicherten Stand und zeigt seine Zeiten wie vor 1.9.37
(alle Zeiten des Auftrags).

downgrade(): verweigert, solange ein Bericht einen gespeicherten Stand hat -- er ginge verloren; ohne entfernt es die Spalte.

Revision ID: b7e3d91c4a58
Revises: 8c86e12540cf
Create Date: 2026-10-22

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b7e3d91c4a58'
down_revision = '8c86e12540cf'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('service_reports', schema=None) as batch_op:
        batch_op.add_column(sa.Column('time_rows_json', sa.Text(), nullable=True))


def downgrade() -> None:
    anzahl = op.get_bind().execute(sa.text("SELECT count(*) FROM service_reports WHERE time_rows_json IS NOT NULL")).scalar()
    if anzahl:
        raise RuntimeError(f"Downgrade verweigert: {anzahl} Einsatzberichte mit gespeicherten Zeiten -- sie gingen verloren.")
    with op.batch_alter_table('service_reports', schema=None) as batch_op:
        batch_op.drop_column('time_rows_json')
