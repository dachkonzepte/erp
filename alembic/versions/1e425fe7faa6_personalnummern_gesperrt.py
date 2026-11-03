"""personalnummern_gesperrt -- eine Personalnummer bleibt der Person, der sie einmal gehörte (seit 1.9.177, L1a-Nachtrag, Punkt 4)

Neu: Tabelle personalnummern_vergeben (Nummer eindeutig, Person, vergeben am). Eine Nummer, die einer Person einmal gehört hat, bleibt dauerhaft
gesperrt -- auch nach Austritt und nach einem Nummernwechsel; nur dieselbe Person bekommt sie wieder (app/time_backoffice.py).

Bestand: übernommen werden die heutigen DATEV-Personalnummern der Lohnstammdaten (ohne Leerzeichen außen, leere nicht) -- sie sind seit 1.9.168
eindeutig. Steht „DATEV-Nr. = ERP-Nr.“ an, dazu die Mitarbeiternummern, soweit die Nummer nicht schon einer anderen Person gemerkt ist. Frühere
Nummern kennt der Bestand nicht (bis 1.9.176 gab es keine Liste).

downgrade(): Tabelle weg.

Revision ID: 1e425fe7faa6
Revises: 2474667579d8
Create Date: 2026-11-03

"""
from datetime import datetime

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1e425fe7faa6'
down_revision = '2474667579d8'
branch_labels = None
depends_on = None


def nummern_uebernehmen(bind) -> int:
    jetzt = datetime.utcnow()
    gemerkt: dict[str, int] = {}
    for nummer, eid in bind.execute(sa.text("SELECT datev_personnel_number, employee_id FROM employee_payroll_settings ORDER BY id")):
        nummer = (nummer or "").strip()
        if nummer and nummer not in gemerkt:
            gemerkt[nummer] = eid
    gleich = bind.execute(sa.text("SELECT datev_personnel_equals_erp_number FROM time_backoffice_advanced_settings WHERE id = 1")).scalar()
    if gleich:
        for nummer, eid in bind.execute(sa.text("SELECT employee_number, id FROM employees ORDER BY id")):
            nummer = (nummer or "").strip()
            if nummer and nummer not in gemerkt:
                gemerkt[nummer] = eid
    for nummer, eid in gemerkt.items():
        bind.execute(sa.text("INSERT INTO personalnummern_vergeben (nummer, employee_id, vergeben_am) VALUES (:n, :e, :j)"),
                     {"n": nummer, "e": eid, "j": jetzt})
    return len(gemerkt)


def upgrade() -> None:
    op.create_table(
        "personalnummern_vergeben",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nummer", sa.String(length=50), nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("vergeben_am", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("nummer", name="uq_personalnummer_vergeben_nummer"),
    )
    op.create_index(op.f("ix_personalnummern_vergeben_employee_id"), "personalnummern_vergeben", ["employee_id"], unique=False)
    nummern_uebernehmen(op.get_bind())


def downgrade() -> None:
    op.drop_index(op.f("ix_personalnummern_vergeben_employee_id"), table_name="personalnummern_vergeben")
    op.drop_table("personalnummern_vergeben")
