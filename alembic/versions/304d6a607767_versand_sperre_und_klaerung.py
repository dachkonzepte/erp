"""versand_sperre_und_klaerung -- Sperre "läuft gerade" und Klärung hängender Einträge (seit 1.8.19)

email_dispatches bekommt:
- lock_key (unique, leer erlaubt): "<art>:<id>", solange ein Versand des Dokuments in Arbeit ist.
  Zwei gleichzeitige Versände desselben Dokuments -- die Datenbank legt genau einen an.
- resolved_at/resolved_by_user_id/resolved_by_name/resolution_note: das Büro klärt einen
  hängengebliebenen Eintrag als gesendet oder fehlgeschlagen, mit Notiz.

Bestehende Einträge bekommen keinen lock_key: ein Versand, der beim Einspielen gerade läuft, ist
weiter über die Vorabprüfung ("läuft gerade", jünger als 10 Minuten) geschützt.

downgrade(): bricht ab, sobald ein Eintrag geklärt ist -- sonst ginge verloren, wer ihn wann und
warum als gesendet oder fehlgeschlagen bestätigt hat, und das Ergebnis stünde ohne Begründung da.
Ohne Klärungen entfernt er die Spalten; lock_key ist nur eine laufende Sperre, kein Nachweis.

Revision ID: 304d6a607767
Revises: b414df7c7744
Create Date: 2026-09-30 16:56:12.381528

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '304d6a607767'
down_revision = 'b414df7c7744'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('email_dispatches', schema=None) as batch_op:
        batch_op.add_column(sa.Column('lock_key', sa.String(length=60), nullable=True))
        batch_op.add_column(sa.Column('resolved_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('resolved_by_user_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('resolved_by_name', sa.String(length=160), nullable=True))
        batch_op.add_column(sa.Column('resolution_note', sa.Text(), nullable=True))
        batch_op.create_unique_constraint('uq_email_dispatches_lock_key', ['lock_key'])


def downgrade() -> None:
    bind = op.get_bind()
    count = bind.execute(sa.text("SELECT COUNT(*) FROM email_dispatches WHERE resolved_at IS NOT NULL")).scalar()
    if count:
        raise RuntimeError(
            f"Downgrade abgebrochen: {count} geklärte Einträge im Versandprotokoll (wer, wann, Notiz). "
            "Vorher sichern, siehe Docstring dieser Migration."
        )
    with op.batch_alter_table('email_dispatches', schema=None) as batch_op:
        batch_op.drop_constraint('uq_email_dispatches_lock_key', type_='unique')
        batch_op.drop_column('resolution_note')
        batch_op.drop_column('resolved_by_name')
        batch_op.drop_column('resolved_by_user_id')
        batch_op.drop_column('resolved_at')
        batch_op.drop_column('lock_key')
