"""kalendertag_im_urlaub -- Silvester: ganzer Urlaubstag oder frei (seit 1.9.176, L1a-Nachtrag, Punkt 3)

employee_absences.kalendertag_urlaub und employee_absence_requests.kalendertag_urlaub (Boolean, leer erlaubt): liegt ein Tag des
Arbeitszeitkalenders mit Rückfrage (Silvester, „Silvester – unbezahlte Freistellung“) in einem Urlaub, hält die Spalte die Antwort fest --
True ganzer Urlaubstag (ersetzt die Freistellung), False unbezahlt frei (kein Urlaubstag). Der Bestand bleibt leer: leer gilt wie der Vorschlag
(ganzer Urlaubstag), app/sollzeit.py und app/arbeitszeitkalender.py rechnen danach. Silvester selbst legt beim Start app.grunddaten.anlegen() an.

downgrade(): beide Spalten weg; dazu die Kalendertage mit Rückfrage (im_urlaub „fragen“, Silvester) samt ihrer Zeile der Zuordnung -- der Stand
davor kennt „fragen“ nicht und konnte solche Tage nicht anlegen, sie stammen alle aus 1.9.176.

Revision ID: 2474667579d8
Revises: fcbfd2cea2da
Create Date: 2026-11-03

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2474667579d8'
down_revision = 'fcbfd2cea2da'
branch_labels = None
depends_on = None

TABELLEN = ("employee_absences", "employee_absence_requests")


def upgrade() -> None:
    for tabelle in TABELLEN:
        with op.batch_alter_table(tabelle, schema=None) as batch_op:
            batch_op.add_column(sa.Column("kalendertag_urlaub", sa.Boolean(), nullable=True))


def kalendertage_mit_rueckfrage_entfernen(bind) -> int:
    schluessel = [r[0] for r in bind.execute(sa.text("SELECT schluessel FROM arbeitszeit_kalendertage WHERE im_urlaub = 'fragen'"))]
    for s in schluessel:
        bind.execute(sa.text("DELETE FROM lohnart_zuordnungen WHERE schluessel = :s"), {"s": "kalender:" + s})
    bind.execute(sa.text("DELETE FROM arbeitszeit_kalendertage WHERE im_urlaub = 'fragen'"))
    return len(schluessel)


def downgrade() -> None:
    kalendertage_mit_rueckfrage_entfernen(op.get_bind())
    for tabelle in reversed(TABELLEN):
        with op.batch_alter_table(tabelle, schema=None) as batch_op:
            batch_op.drop_column("kalendertag_urlaub")
