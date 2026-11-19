"""webanfragen_pruefliste_verwerfen -- Prüfliste, Verwerfen und Meldung an den Empfangsdienst (seit 1.10.4, Stufe W1b)

Neue Spalten an webanfragen (alle leer erlaubt): geprueft_am, geprueft_von_user_id (aus der Prüfliste in den Eingang gegeben), erledigt_am,
erledigt_von_user_id, verworfen_grund (fester Schlüssel), melden_soll (erp_id, die der Empfangsdienst bekommen soll; leer = eingang-<ID>),
gemeldet_als (zuletzt bestätigte erp_id). Der Bestand: bestätigt gemeldete Anfragen (gemeldet_am gesetzt) bekommen gemeldet_als = eingang-<ID> --
so hat W1a gemeldet (app/webanfragen.py bis 1.10.3).

downgrade(): bricht ab, solange eine Anfrage verworfen ist (der Stand ginge verloren); sonst fallen die Spalten weg.

Revision ID: a107b86d8e8d
Revises: 994be7557612
Create Date: 2026-11-19

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a107b86d8e8d'
down_revision = '994be7557612'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('webanfragen', schema=None) as batch_op:
        batch_op.add_column(sa.Column('geprueft_am', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('geprueft_von_user_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('erledigt_am', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('erledigt_von_user_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('verworfen_grund', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('melden_soll', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('gemeldet_als', sa.String(length=64), nullable=True))
        batch_op.create_foreign_key('fk_webanfragen_geprueft_von_user_id', 'app_users', ['geprueft_von_user_id'], ['id'])
        batch_op.create_foreign_key('fk_webanfragen_erledigt_von_user_id', 'app_users', ['erledigt_von_user_id'], ['id'])

    bind = op.get_bind()
    tabelle = sa.table('webanfragen', sa.column('id', sa.Integer), sa.column('gemeldet_am', sa.DateTime), sa.column('gemeldet_als', sa.String))
    for (zeile_id,) in bind.execute(sa.select(tabelle.c.id).where(tabelle.c.gemeldet_am.is_not(None)).order_by(tabelle.c.id)).all():
        bind.execute(tabelle.update().where(tabelle.c.id == zeile_id).values(gemeldet_als=f"eingang-{zeile_id}"))


def downgrade() -> None:
    bind = op.get_bind()
    verworfen = bind.execute(sa.text("SELECT COUNT(*) FROM webanfragen WHERE status <> 'neu'")).scalar()
    if verworfen:
        raise RuntimeError(f"webanfragen: {verworfen} Anfragen sind schon erledigt -- ihr Stand ginge mit dem Downgrade verloren.")
    with op.batch_alter_table('webanfragen', schema=None) as batch_op:
        batch_op.drop_constraint('fk_webanfragen_erledigt_von_user_id', type_='foreignkey')
        batch_op.drop_constraint('fk_webanfragen_geprueft_von_user_id', type_='foreignkey')
        batch_op.drop_column('gemeldet_als')
        batch_op.drop_column('melden_soll')
        batch_op.drop_column('verworfen_grund')
        batch_op.drop_column('erledigt_von_user_id')
        batch_op.drop_column('erledigt_am')
        batch_op.drop_column('geprueft_von_user_id')
        batch_op.drop_column('geprueft_am')
