"""nebenforderungen_z2b -- Auftrag hält seinen Kunden, Mahnung ersetzen, Mahngebühren und Pauschale (seit 1.8.80, Zahlungsstufe Z2b)

- orders.customer_id (FK customers, Index, NOT NULL): der Vertragspartner des Auftrags (Vorgabe Z2b "Vorweg" 1). Bestand: der
  Kunde des Projekts am Tag der Migration -- wie 1.8.79 bei invoices.customer_id. Ein Auftrag, dessen Kunde am Projekt nach dem
  Beauftragen gewechselt wurde, trägt danach den neuen Kunden, im Schnappschuss aber noch den alten Namen: dafür
  scripts/pruefabfrage_auftrag_kunde.sql.
- order_customer_changes: Historie eines Kundenwechsels am Auftrag mit Begründung.
- reminders.replaced_by_id/replaced_at: eine nie hinausgegangene Mahnung, ersetzt durch eine neue derselben Stufe ("Vorweg" 2).
- reminders.fee_accepted/flat_fee_accepted: Gebühr bzw. Pauschale im Entwurf bewusst übernommen (Nr. 5 und 6), Bestand: nein.
- general_settings.dunning_charges_enabled: Schalter "Mahngebühren und Verzugszinsen", Vorgabe aus (Nr. 3).
- invoice_charges: Nebenforderungen je Rechnung (Nr. 4), invoice_default_starts: bestätigter Verzugsbeginn (Nr. 6).
- Stufe 1: Gebühr 5,00 € (die alte Vorgabe) -> 0,00 € (Nr. 5); die drei Standard-Mahntexte, wenn sie unverändert sind, ohne
  "zuzüglich einer Mahngebühr" -- sie nennen den Gesamtbetrag, die Aufstellung im PDF zeigt die Teile (bei ausgeschalteten
  Gebühren stünde sonst "Mahngebühr von 0,00 €" im Brief).

downgrade(): verweigert, solange etwas besteht, das der Rückweg verlöre (Nebenforderung, Verzugsbeginn, Kundenwechsel am Auftrag,
ersetzte Mahnung). Gebühr der Stufe 1 und Texte gehen nur zurück, wenn sie noch genau auf dem Stand dieser Migration stehen.

Revision ID: 8e2f4b6d1c97
Revises: 5db1a12b4a66
Create Date: 2026-10-12

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8e2f4b6d1c97'
down_revision = '5db1a12b4a66'
branch_labels = None
depends_on = None

FK_ORDER_CUSTOMER = "fk_orders_customer_id_customers"
FK_REMINDER_REPLACED = "fk_reminders_replaced_by_id_reminders"

# Standard-Mahntexte bis 1.8.79 (app/reminders.py::DEFAULT_REMINDER_LEVELS) und ab 1.8.80 -- feste Kopien, wie sie hier gelten.
OLD_TEXTS = {
    1: ("Trotz Fälligkeit am {faelligkeitsdatum} konnten wir bis heute keinen Zahlungseingang zu "
        "Rechnung {rechnungsnummer} vom {rechnungsdatum} feststellen. Bitte begleichen Sie den "
        "offenen Betrag von {offener_betrag} zuzüglich einer Mahngebühr von {mahngebuehr}, "
        "insgesamt {gesamtbetrag}, bis zum {neue_frist}. Sollte Ihre Zahlung bereits erfolgt sein, "
        "betrachten Sie dieses Schreiben bitte als gegenstandslos."),
    2: ("Leider konnten wir trotz unserer Zahlungserinnerung vom {vorheriges_mahndatum} bis heute "
        "keinen Zahlungseingang zu Rechnung {rechnungsnummer} vom {rechnungsdatum} feststellen. Wir "
        "bitten Sie letztmalig, den offenen Betrag von {offener_betrag} zuzüglich einer Mahngebühr "
        "von {mahngebuehr}, insgesamt {gesamtbetrag}, bis zum {neue_frist} zu begleichen."),
    3: ("Auch nach unserer 2. Mahnung vom {vorheriges_mahndatum} ist Rechnung {rechnungsnummer} vom "
        "{rechnungsdatum} weiterhin nicht ausgeglichen. Wir bitten Sie letztmalig um Zahlung des "
        "offenen Betrags von {offener_betrag} zuzüglich einer Mahngebühr von {mahngebuehr}, "
        "insgesamt {gesamtbetrag}, bis zum {neue_frist}. Nach fruchtlosem Ablauf dieser Frist "
        "behalten wir uns weitere rechtliche Schritte vor."),
}
NEW_TEXTS = {
    1: ("Trotz Fälligkeit am {faelligkeitsdatum} konnten wir bis heute keinen Zahlungseingang zu "
        "Rechnung {rechnungsnummer} vom {rechnungsdatum} feststellen. Bitte begleichen Sie den "
        "Betrag von {gesamtbetrag} (Aufstellung unten) bis zum {neue_frist}. Sollte Ihre Zahlung "
        "bereits erfolgt sein, betrachten Sie dieses Schreiben bitte als gegenstandslos."),
    2: ("Leider konnten wir trotz unserer Zahlungserinnerung vom {vorheriges_mahndatum} bis heute "
        "keinen Zahlungseingang zu Rechnung {rechnungsnummer} vom {rechnungsdatum} feststellen. Wir "
        "bitten Sie letztmalig, den Betrag von {gesamtbetrag} (Aufstellung unten) bis zum "
        "{neue_frist} zu begleichen."),
    3: ("Auch nach unserer 2. Mahnung vom {vorheriges_mahndatum} ist Rechnung {rechnungsnummer} vom "
        "{rechnungsdatum} weiterhin nicht ausgeglichen. Wir bitten Sie letztmalig um Zahlung von "
        "{gesamtbetrag} (Aufstellung unten) bis zum {neue_frist}. Nach fruchtlosem Ablauf dieser "
        "Frist behalten wir uns weitere rechtliche Schritte vor."),
}


def kunden_der_auftraege(bind) -> int:
    """Setzt an jedem Auftrag den Kunden seines Projekts. Gibt die Zahl der Aufträge zurück."""
    return bind.execute(sa.text(
        "UPDATE orders SET customer_id = (SELECT projects.customer_id FROM projects WHERE projects.id = orders.project_id)"
    )).rowcount


def stufen_umstellen(bind, *, von_texte: dict, nach_texte: dict, von_gebuehr: int, nach_gebuehr: int) -> None:
    """Texte der Stufen 1-3, die genau dem alten Standard entsprechen, und die Gebühr der Stufe 1, wenn sie genau dem alten Wert
    entspricht -- anderes bleibt, wie es ist."""
    for level, text in von_texte.items():
        bind.execute(sa.text("UPDATE reminder_levels SET text_template = :neu WHERE level = :level AND text_template = :alt"),
                     {"neu": nach_texte[level], "level": level, "alt": text})
    bind.execute(sa.text("UPDATE reminder_levels SET fee_amount = :neu WHERE level = 1 AND fee_amount = :alt"),
                 {"neu": nach_gebuehr, "alt": von_gebuehr})


def upgrade() -> None:
    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.add_column(sa.Column('customer_id', sa.Integer(), nullable=True))
    kunden_der_auftraege(op.get_bind())
    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.alter_column('customer_id', existing_type=sa.Integer(), nullable=False)
        batch_op.create_index(batch_op.f('ix_orders_customer_id'), ['customer_id'], unique=False)
        batch_op.create_foreign_key(FK_ORDER_CUSTOMER, 'customers', ['customer_id'], ['id'])

    op.create_table(
        'order_customer_changes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=False),
        sa.Column('old_customer_id', sa.Integer(), nullable=False),
        sa.Column('new_customer_id', sa.Integer(), nullable=False),
        sa.Column('old_customer_name', sa.String(length=255), nullable=False),
        sa.Column('new_customer_name', sa.String(length=255), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('changed_at', sa.DateTime(), nullable=False),
        sa.Column('changed_by_user_id', sa.Integer(), nullable=True),
        sa.Column('changed_by_name', sa.String(length=160), nullable=False),
        sa.ForeignKeyConstraint(['new_customer_id'], ['customers.id'], ),
        sa.ForeignKeyConstraint(['old_customer_id'], ['customers.id'], ),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('order_customer_changes', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_order_customer_changes_order_id'), ['order_id'], unique=False)

    with op.batch_alter_table('reminders', schema=None) as batch_op:
        batch_op.add_column(sa.Column('replaced_by_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('replaced_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('fee_accepted', sa.Boolean(), server_default='0', nullable=False))
        batch_op.add_column(sa.Column('flat_fee_accepted', sa.Boolean(), server_default='0', nullable=False))
        batch_op.create_index(batch_op.f('ix_reminders_replaced_by_id'), ['replaced_by_id'], unique=False)
        batch_op.create_foreign_key(FK_REMINDER_REPLACED, 'reminders', ['replaced_by_id'], ['id'])

    with op.batch_alter_table('general_settings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('dunning_charges_enabled', sa.Boolean(), server_default='0', nullable=False))

    op.create_table(
        'invoice_charges',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('invoice_id', sa.Integer(), nullable=False),
        sa.Column('kind', sa.String(length=20), nullable=False),
        sa.Column('amount', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('reminder_id', sa.Integer(), nullable=True),
        sa.Column('reverses_charge_id', sa.Integer(), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('created_by_name', sa.String(length=160), nullable=False),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id'], ),
        sa.ForeignKeyConstraint(['reminder_id'], ['reminders.id'], ),
        sa.ForeignKeyConstraint(['reverses_charge_id'], ['invoice_charges.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('reverses_charge_id', name='uq_invoice_charge_reverses'),
    )
    with op.batch_alter_table('invoice_charges', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_invoice_charges_invoice_id'), ['invoice_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_invoice_charges_reminder_id'), ['reminder_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_invoice_charges_reverses_charge_id'), ['reverses_charge_id'], unique=False)

    op.create_table(
        'invoice_default_starts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('invoice_id', sa.Integer(), nullable=False),
        sa.Column('starts_on', sa.Date(), nullable=False),
        sa.Column('basis', sa.String(length=20), nullable=False),
        sa.Column('source_text', sa.Text(), nullable=True),
        sa.Column('proposal_on', sa.Date(), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('created_by_name', sa.String(length=160), nullable=False),
        sa.Column('discarded_at', sa.DateTime(), nullable=True),
        sa.Column('discarded_by_user_id', sa.Integer(), nullable=True),
        sa.Column('discarded_by_name', sa.String(length=160), nullable=True),
        sa.Column('discard_reason', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('invoice_default_starts', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_invoice_default_starts_invoice_id'), ['invoice_id'], unique=False)

    stufen_umstellen(op.get_bind(), von_texte=OLD_TEXTS, nach_texte=NEW_TEXTS, von_gebuehr=5, nach_gebuehr=0)


def downgrade() -> None:
    bind = op.get_bind()
    blocking = {
        "Nebenforderungen": "SELECT COUNT(*) FROM invoice_charges",
        "bestätigte Verzugsbeginne": "SELECT COUNT(*) FROM invoice_default_starts",
        "Kundenwechsel an Aufträgen": "SELECT COUNT(*) FROM order_customer_changes",
        "ersetzte Mahnungen": "SELECT COUNT(*) FROM reminders WHERE replaced_by_id IS NOT NULL",
    }
    found = {label: bind.execute(sa.text(sql)).scalar() for label, sql in blocking.items()}
    found = {label: n for label, n in found.items() if n}
    if found:
        listed = ", ".join(f"{n} {label}" for label, n in found.items())
        raise RuntimeError(f"Downgrade verweigert: {listed} -- sie gingen verloren.")

    stufen_umstellen(bind, von_texte=NEW_TEXTS, nach_texte=OLD_TEXTS, von_gebuehr=0, nach_gebuehr=5)

    with op.batch_alter_table('invoice_default_starts', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_invoice_default_starts_invoice_id'))
    op.drop_table('invoice_default_starts')
    with op.batch_alter_table('invoice_charges', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_invoice_charges_reverses_charge_id'))
        batch_op.drop_index(batch_op.f('ix_invoice_charges_reminder_id'))
        batch_op.drop_index(batch_op.f('ix_invoice_charges_invoice_id'))
    op.drop_table('invoice_charges')

    with op.batch_alter_table('general_settings', schema=None) as batch_op:
        batch_op.drop_column('dunning_charges_enabled')

    with op.batch_alter_table('reminders', schema=None) as batch_op:
        batch_op.drop_constraint(FK_REMINDER_REPLACED, type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_reminders_replaced_by_id'))
        batch_op.drop_column('flat_fee_accepted')
        batch_op.drop_column('fee_accepted')
        batch_op.drop_column('replaced_at')
        batch_op.drop_column('replaced_by_id')

    with op.batch_alter_table('order_customer_changes', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_order_customer_changes_order_id'))
    op.drop_table('order_customer_changes')

    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.drop_constraint(FK_ORDER_CUSTOMER, type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_orders_customer_id'))
        batch_op.drop_column('customer_id')
