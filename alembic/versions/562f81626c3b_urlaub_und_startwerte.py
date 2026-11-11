"""urlaub_und_startwerte -- Urlaubsanspruch je Person und Jahr, Startwert der Konten je Person, Vorgaben des Urlaubskontos (seit 1.9.310)

Lohn L2a, Punkt 3. Neue Tabellen urlaubsansprueche (je Person und Jahr: urlaubstage, uebertrag, verfall_am, notiz) und lohn_startwerte (je Person: stichtag,
resturlaub_tage, saldo_stunden, herkunft, herkunft_notiz, geprueft_am, geprueft_von); in time_tracking_settings die Vorgaben urlaub_vorgabe_tage (NOT
NULL, server_default 30), urlaub_uebertrag (NOT NULL, server_default „von_hand“) und urlaub_verfall (leer). Keine Datenübernahme -- die Tabellen sind
leer, die Vorgaben stehen auf ihrem Vorgabewert.

downgrade(): bricht ab, solange ein Anspruch oder ein Startwert eingetragen ist oder eine Vorgabe vom Vorgabewert abweicht -- die Fassung davor
kennt sie nicht, sie gingen verloren. Sonst fallen Tabellen und Spalten weg.

Revision ID: 562f81626c3b
Revises: 84ee228b331e
Create Date: 2026-11-11

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '562f81626c3b'
down_revision = '84ee228b331e'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "urlaubsansprueche",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("jahr", sa.Integer(), nullable=False),
        sa.Column("urlaubstage", sa.Numeric(4, 1), nullable=True),
        sa.Column("uebertrag", sa.Numeric(4, 1), nullable=True),
        sa.Column("verfall_am", sa.Date(), nullable=True),
        sa.Column("notiz", sa.String(255), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("employee_id", "jahr", name="uq_urlaubsanspruch_person_jahr"),
    )
    op.create_index("ix_urlaubsansprueche_employee_id", "urlaubsansprueche", ["employee_id"])
    op.create_table(
        "lohn_startwerte",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("stichtag", sa.Date(), nullable=False),
        sa.Column("resturlaub_tage", sa.Numeric(4, 1), nullable=True),
        sa.Column("saldo_stunden", sa.Numeric(7, 2), nullable=True),
        sa.Column("herkunft", sa.String(20), server_default="steuerbuero", nullable=False),
        sa.Column("herkunft_notiz", sa.String(255), nullable=True),
        sa.Column("geprueft_am", sa.Date(), nullable=True),
        sa.Column("geprueft_von", sa.String(160), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("employee_id", name="uq_lohn_startwert_person"),
    )
    op.create_index("ix_lohn_startwerte_employee_id", "lohn_startwerte", ["employee_id"])
    with op.batch_alter_table("time_tracking_settings") as batch:
        batch.add_column(sa.Column("urlaub_vorgabe_tage", sa.Numeric(4, 1), server_default="30", nullable=False))
        batch.add_column(sa.Column("urlaub_uebertrag", sa.String(20), server_default="von_hand", nullable=False))
        batch.add_column(sa.Column("urlaub_verfall", sa.String(6), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    ansprueche = bind.execute(sa.text("SELECT count(*) FROM urlaubsansprueche")).scalar()
    startwerte = bind.execute(sa.text("SELECT count(*) FROM lohn_startwerte")).scalar()
    vorgaben = bind.execute(sa.text("SELECT count(*) FROM time_tracking_settings WHERE urlaub_vorgabe_tage <> 30 OR urlaub_uebertrag <> 'von_hand' "
                                    "OR urlaub_verfall IS NOT NULL")).scalar()
    if ansprueche or startwerte or vorgaben:
        raise RuntimeError(f"Downgrade abgebrochen, nichts geändert: {ansprueche} Urlaubsanspruch/-ansprüche, {startwerte} Startwert(e) und "
                           f"{vorgaben} geänderte Vorgabe(n) des Urlaubskontos sind eingetragen -- die Fassung davor kennt sie nicht, sie gingen verloren.")
    with op.batch_alter_table("time_tracking_settings") as batch:
        batch.drop_column("urlaub_verfall")
        batch.drop_column("urlaub_uebertrag")
        batch.drop_column("urlaub_vorgabe_tage")
    op.drop_index("ix_lohn_startwerte_employee_id", table_name="lohn_startwerte")
    op.drop_table("lohn_startwerte")
    op.drop_index("ix_urlaubsansprueche_employee_id", table_name="urlaubsansprueche")
    op.drop_table("urlaubsansprueche")
