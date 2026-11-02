"""sollzeit_tarif_und_eigene_werte -- Sollzeit je Person (seit 1.9.167, Lohn L1a, Punkt 2)

Neu: employee_payroll_settings.eintritt und .austritt (leer = offen); Tabelle employee_target_hours (eigene Werte je Person ab einem Tag,
Montag bis Sonntag, eine Zeile ohne Werte = wieder Tarif).

Tarif Dachdecker (Entscheidung Tobias): Montag bis Freitag KW 18–48 8,00 h, KW 49–17 7,50 h. upgrade() stellt die beiden Startmodelle um,
aber nur, solange sie noch genau den Grundwerten entsprechen (Kürzel summer: KW 13–43, 8,00 h; Kürzel winter: KW 44–12, 8,00 h) -- ein
Modell, das jemand geändert hat, bleibt, wie es ist; scripts/pruefe_zeitregeln.py nennt es.

downgrade(): stellt nur zurück, was noch genau dem Tarif entspricht, und entfernt Tabelle und Spalten.

Revision ID: b7e3c91d4a52
Revises: f1b9d2c6a470
Create Date: 2026-11-02

"""
from decimal import Decimal

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b7e3c91d4a52'
down_revision = 'f1b9d2c6a470'
branch_labels = None
depends_on = None

# (Kürzel, KW von, KW bis, Stunden) vorher -> nachher
GRUNDWERTE = {"summer": (13, 43, Decimal("8.00")), "winter": (44, 12, Decimal("8.00"))}
TARIF = {"summer": (18, 48, Decimal("8.00")), "winter": (49, 17, Decimal("7.50"))}


def _umstellen(bind, von: dict, nach: dict) -> list[int]:
    """Stellt je Kürzel das Modell von `von` auf `nach` um, nur wenn es genau `von` entspricht; gibt die umgestellten Modelle zurück."""
    geaendert = []
    zeilen = bind.execute(sa.text(
        "SELECT m.id, m.code, m.daily_target_hours, v.id AS vid, v.valid_from_week, v.valid_to_week FROM work_time_models m "
        "JOIN work_time_model_validities v ON v.model_id = m.id")).mappings().all()
    for z in zeilen:
        code = (z["code"] or "").strip().lower()
        if code not in von:
            continue
        kw_von, kw_bis, stunden = von[code]
        if (int(z["valid_from_week"]), int(z["valid_to_week"])) != (kw_von, kw_bis) or Decimal(str(z["daily_target_hours"])) != stunden:
            continue
        neu_von, neu_bis, neu_stunden = nach[code]
        bind.execute(sa.text("UPDATE work_time_model_validities SET valid_from_week = :a, valid_to_week = :b WHERE id = :i"),
                     {"a": neu_von, "b": neu_bis, "i": z["vid"]})
        # mit Typ: SQLite bindet keinen Decimal-Wert in rohem SQL (gefunden in der Migrationsprobe)
        bind.execute(sa.text("UPDATE work_time_models SET daily_target_hours = :h WHERE id = :i").bindparams(sa.bindparam("h", type_=sa.Numeric(9, 4))),
                     {"h": neu_stunden, "i": z["id"]})
        geaendert.append(int(z["id"]))
    return geaendert


def tarif_umstellen(bind) -> list[int]:
    return _umstellen(bind, GRUNDWERTE, TARIF)


def tarif_zurueck(bind) -> list[int]:
    return _umstellen(bind, TARIF, GRUNDWERTE)


def upgrade() -> None:
    op.add_column("employee_payroll_settings", sa.Column("eintritt", sa.Date(), nullable=True))
    op.add_column("employee_payroll_settings", sa.Column("austritt", sa.Date(), nullable=True))
    op.create_table(
        "employee_target_hours",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        *[sa.Column(tag, sa.Numeric(5, 2), nullable=True) for tag in ("montag", "dienstag", "mittwoch", "donnerstag", "freitag", "samstag", "sonntag")],
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("employee_id", "valid_from", name="uq_employee_target_hours_tag"),
    )
    op.create_index(op.f("ix_employee_target_hours_employee_id"), "employee_target_hours", ["employee_id"], unique=False)
    op.create_index(op.f("ix_employee_target_hours_valid_from"), "employee_target_hours", ["valid_from"], unique=False)
    tarif_umstellen(op.get_bind())


def downgrade() -> None:
    tarif_zurueck(op.get_bind())
    op.drop_index(op.f("ix_employee_target_hours_valid_from"), table_name="employee_target_hours")
    op.drop_index(op.f("ix_employee_target_hours_employee_id"), table_name="employee_target_hours")
    op.drop_table("employee_target_hours")
    with op.batch_alter_table("employee_payroll_settings") as batch_op:
        batch_op.drop_column("austritt")
        batch_op.drop_column("eintritt")
