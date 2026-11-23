"""kundenportal_fundament -- Tabellen des Kundenportals (seit 1.11.0, Stufe P1a; docs/archiv/webseite-und-kundenportal.md, „Bauplan P1“)

Neue Spalte customers.portal_aktiv (Pflicht, Vorgabe aus -- Regel 1, server_default) und sechs neue Tabellen ohne Bestand: portal_zugaenge (einer je
Kunde, Link nur als Prüfwert), portal_sitzungen, portal_codes (nur Prüfwerte), portal_post (Aufträge an den Postboten), portal_zugriffe (Protokoll, nur feste
Wörter) und portal_bremsen. Die festen Werte stehen als CHECK hier wörtlich (CHECKS) -- tests/test_v799_portal_rechte.py vergleicht sie mit
app/portal/werte.py; eine Änderung dort braucht eine neue Migration.

Keine Rechte: die setzt scripts/portal_rechte.py nach der Migration (update.sh) -- eine Migration hängt nie vom heutigen Stand von app/portal/rechte.py ab.
Das Modul „Kundenportal“ ist ab Werk aus, ohne Zeile (app/modules.py::AB_WERK_AUS).

downgrade(): bricht ab, solange ein Zugang besteht oder ein Kunde das Portal an hat (beides ginge verloren); sonst fallen Tabellen und Spalte weg.

Revision ID: 4f8a2c6e1b97
Revises: 9a4c2e7b1d56
Create Date: 2026-11-23

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4f8a2c6e1b97'
down_revision = '9a4c2e7b1d56'
branch_labels = None
depends_on = None

CHECKS = {
    "ck_portal_sitzung_ende": "beendet_grund IS NULL OR beendet_grund IN ('abgemeldet', 'ueberall', 'gesperrt', 'neu_erzeugt', 'portal_aus')",
    "ck_portal_post_art": "art IN ('code')",
    "ck_portal_post_status": "status IN ('wartet', 'gesendet', 'fehler', 'verworfen')",
    "ck_portal_zugriff_aktion": ("aktion IN ('link_geoeffnet', 'code_angefordert', 'code_gesendet', 'code_fehler', 'code_falsch', 'code_abgelaufen', "
                                 "'angemeldet', 'verlaengert', 'abgemeldet', 'ueberall_abgemeldet')"),
    "ck_portal_zugriff_ergebnis": ("ergebnis IN ('ok', 'unbekannt', 'gesperrt', 'abgelaufen', 'portal_aus', 'archiv', 'modul_aus', 'bremse', "
                                   "'code_noetig', 'angemeldet', 'ungueltig')"),
}


def upgrade() -> None:
    with op.batch_alter_table('customers', schema=None) as batch_op:
        batch_op.add_column(sa.Column('portal_aktiv', sa.Boolean(), nullable=False, server_default='0'))

    op.create_table(
        'portal_zugaenge',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('email_anzeige', sa.String(length=255), nullable=False),
        sa.Column('link_sha256', sa.String(length=64), nullable=True),
        sa.Column('link_erzeugt_am', sa.DateTime(), nullable=True),
        sa.Column('gueltig_bis', sa.DateTime(), nullable=True),
        sa.Column('gesperrt_am', sa.DateTime(), nullable=True),
        sa.Column('gesperrt_grund', sa.Text(), nullable=True),
        sa.Column('gesperrt_von_user_id', sa.Integer(), nullable=True),
        sa.Column('gesperrt_von_name', sa.String(length=160), nullable=True),
        sa.Column('angelegt_am', sa.DateTime(), nullable=False),
        sa.Column('angelegt_von_user_id', sa.Integer(), nullable=True),
        sa.Column('angelegt_von_name', sa.String(length=160), server_default='System', nullable=False),
        sa.Column('zuletzt_genutzt_am', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], name='fk_portal_zugaenge_customer_id'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('customer_id', name='uq_portal_zugang_kunde'),
        sa.UniqueConstraint('link_sha256', name='uq_portal_zugang_link'),
    )
    op.create_index('ix_portal_zugaenge_customer_id', 'portal_zugaenge', ['customer_id'], unique=False)

    op.create_table(
        'portal_sitzungen',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('zugang_id', sa.Integer(), nullable=False),
        sa.Column('wert_sha256', sa.String(length=64), nullable=False),
        sa.Column('angelegt_am', sa.DateTime(), nullable=False),
        sa.Column('bestaetigt_am', sa.DateTime(), nullable=True),
        sa.Column('zuletzt_am', sa.DateTime(), nullable=True),
        sa.Column('laeuft_ab', sa.DateTime(), nullable=False),
        sa.Column('beendet_am', sa.DateTime(), nullable=True),
        sa.Column('beendet_grund', sa.String(length=20), nullable=True),
        sa.CheckConstraint(CHECKS['ck_portal_sitzung_ende'], name='ck_portal_sitzung_ende'),
        sa.ForeignKeyConstraint(['zugang_id'], ['portal_zugaenge.id'], name='fk_portal_sitzungen_zugang_id'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('wert_sha256', name='uq_portal_sitzung_wert'),
    )
    op.create_index('ix_portal_sitzungen_zugang_id', 'portal_sitzungen', ['zugang_id'], unique=False)

    op.create_table(
        'portal_codes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('sitzung_id', sa.Integer(), nullable=False),
        sa.Column('pruefwert', sa.String(length=64), nullable=False),
        sa.Column('angelegt_am', sa.DateTime(), nullable=False),
        sa.Column('gueltig_bis', sa.DateTime(), nullable=False),
        sa.Column('versuche', sa.Integer(), server_default='0', nullable=False),
        sa.Column('verbraucht_am', sa.DateTime(), nullable=True),
        sa.Column('ersetzt_am', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['sitzung_id'], ['portal_sitzungen.id'], name='fk_portal_codes_sitzung_id', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_portal_codes_sitzung_id', 'portal_codes', ['sitzung_id'], unique=False)

    op.create_table(
        'portal_post',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('art', sa.String(length=20), nullable=False),
        sa.Column('zugang_id', sa.Integer(), nullable=False),
        sa.Column('sitzung_id', sa.Integer(), nullable=False),
        sa.Column('angefordert_am', sa.DateTime(), nullable=False),
        sa.Column('status', sa.String(length=20), server_default='wartet', nullable=False),
        sa.Column('erledigt_am', sa.DateTime(), nullable=True),
        sa.Column('email_dispatch_id', sa.Integer(), nullable=True),
        sa.Column('fehler', sa.String(length=60), nullable=True),
        sa.CheckConstraint(CHECKS['ck_portal_post_art'], name='ck_portal_post_art'),
        sa.CheckConstraint(CHECKS['ck_portal_post_status'], name='ck_portal_post_status'),
        sa.ForeignKeyConstraint(['zugang_id'], ['portal_zugaenge.id'], name='fk_portal_post_zugang_id'),
        sa.ForeignKeyConstraint(['sitzung_id'], ['portal_sitzungen.id'], name='fk_portal_post_sitzung_id', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['email_dispatch_id'], ['email_dispatches.id'], name='fk_portal_post_email_dispatch_id'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_portal_post_zugang_id', 'portal_post', ['zugang_id'], unique=False)
    op.create_index('ix_portal_post_sitzung_id', 'portal_post', ['sitzung_id'], unique=False)
    op.create_index('ix_portal_post_status', 'portal_post', ['status'], unique=False)

    op.create_table(
        'portal_zugriffe',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('zeitpunkt', sa.DateTime(), nullable=False),
        sa.Column('zugang_id', sa.Integer(), nullable=True),
        sa.Column('sitzung_id', sa.Integer(), nullable=True),
        sa.Column('aktion', sa.String(length=30), nullable=False),
        sa.Column('ergebnis', sa.String(length=20), nullable=False),
        sa.Column('objekt_art', sa.String(length=30), nullable=True),
        sa.Column('objekt_id', sa.Integer(), nullable=True),
        sa.CheckConstraint(CHECKS['ck_portal_zugriff_aktion'], name='ck_portal_zugriff_aktion'),
        sa.CheckConstraint(CHECKS['ck_portal_zugriff_ergebnis'], name='ck_portal_zugriff_ergebnis'),
        sa.ForeignKeyConstraint(['zugang_id'], ['portal_zugaenge.id'], name='fk_portal_zugriffe_zugang_id'),
        sa.ForeignKeyConstraint(['sitzung_id'], ['portal_sitzungen.id'], name='fk_portal_zugriffe_sitzung_id', ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_portal_zugriffe_zeitpunkt', 'portal_zugriffe', ['zeitpunkt'], unique=False)
    op.create_index('ix_portal_zugriffe_zugang_id', 'portal_zugriffe', ['zugang_id'], unique=False)

    op.create_table(
        'portal_bremsen',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('schluessel', sa.String(length=100), nullable=False),
        sa.Column('fenster_beginn', sa.DateTime(), nullable=False),
        sa.Column('zaehler', sa.Integer(), server_default='0', nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('schluessel', 'fenster_beginn', name='uq_portal_bremse'),
    )


def downgrade() -> None:
    bind = op.get_bind()
    zugaenge = bind.execute(sa.text("SELECT COUNT(*) FROM portal_zugaenge")).scalar()
    an = bind.execute(sa.text("SELECT COUNT(*) FROM customers WHERE portal_aktiv")).scalar()
    if zugaenge or an:
        raise RuntimeError(f"Kundenportal: {zugaenge} Zugänge, {an} Kunden mit Portal an -- sie gingen mit dem Downgrade verloren.")
    op.drop_table('portal_bremsen')
    op.drop_index('ix_portal_zugriffe_zugang_id', table_name='portal_zugriffe')
    op.drop_index('ix_portal_zugriffe_zeitpunkt', table_name='portal_zugriffe')
    op.drop_table('portal_zugriffe')
    op.drop_index('ix_portal_post_status', table_name='portal_post')
    op.drop_index('ix_portal_post_sitzung_id', table_name='portal_post')
    op.drop_index('ix_portal_post_zugang_id', table_name='portal_post')
    op.drop_table('portal_post')
    op.drop_index('ix_portal_codes_sitzung_id', table_name='portal_codes')
    op.drop_table('portal_codes')
    op.drop_index('ix_portal_sitzungen_zugang_id', table_name='portal_sitzungen')
    op.drop_table('portal_sitzungen')
    op.drop_index('ix_portal_zugaenge_customer_id', table_name='portal_zugaenge')
    op.drop_table('portal_zugaenge')
    with op.batch_alter_table('customers', schema=None) as batch_op:
        batch_op.drop_column('portal_aktiv')
