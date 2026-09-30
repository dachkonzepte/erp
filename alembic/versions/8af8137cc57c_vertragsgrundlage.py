"""vertragsgrundlage -- Verbraucher-Merkmal und Vertragsgrundlage (seit 1.8.21)

- customers.is_consumer (NOT NULL, server_default wahr): Verbraucher nach § 13 BGB. Bestandskunden
  der Kategorien Gewerbekunde, Öffentlicher Auftraggeber, Architekt/Planer und Versicherung werden auf
  falsch gesetzt, alle anderen (auch ohne Profil) bleiben wahr. Die Kategorie wird ohne Leerzeichen
  und Groß-/Kleinschreibung verglichen ("Architekt / Planer" wie "Architekt/Planer").
- quote_document_meta.contract_basis, orders.contract_basis (NOT NULL, server_default "bgb"):
  bestehende Angebote und Aufträge bekommen "bgb". Angebote, die noch keine Kopfzeile haben (die legt
  ensure_quote_structure() sonst erst beim ersten Öffnen an, dann mit der Vorgabe aus dem Kunden),
  bekommen sie hier -- mit denselben Werten, die ensure_quote_structure() setzen würde (Datum aus
  created_at in Europe/Berlin, Bindefrist 30 Tage, Standard-Zahlungsbedingung), und "bgb".
- orders.contract_basis_manual (NOT NULL, server_default falsch): am Auftrag mit Begründung geändert.
- Tabellen contract_basis_clauses (Klauseltext je Vertragsgrundlage) und
  order_contract_basis_changes (Historie der Änderungen am Auftrag).

downgrade(): bricht ab, sobald etwas verloren ginge -- ein Klauseltext oder eine Prüfangabe, eine
Änderung am Auftrag, eine Vertragsgrundlage ungleich "bgb" an Angebot oder Auftrag, oder ein Kunde,
dessen Verbraucher-Merkmal von der Regel oben abweicht (also von Hand geändert wurde). Die hier
angelegten Angebotskopf-Zeilen bleiben stehen: die Anwendung legt sie ohne diese Migration beim ersten
Zugriff mit denselben Werten an.

Revision ID: 8af8137cc57c
Revises: d1c4a7252554
Create Date: 2026-09-30 18:32:27.626626

"""
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8af8137cc57c'
down_revision = 'd1c4a7252554'
branch_labels = None
depends_on = None

# Bewusst eine Kopie, nicht aus app/ importiert: die Migration muss auch dann noch dasselbe tun, wenn
# sich die Anwendung später ändert.
NON_CONSUMER_CATEGORIES = {"gewerbekunde", "öffentlicherauftraggeber", "architekt/planer", "versicherung"}
BERLIN = ZoneInfo("Europe/Berlin")


def _normalize_category(value) -> str:
    return "".join(str(value or "").split()).casefold()


def _non_consumer_customer_ids(bind) -> set[int]:
    rows = bind.execute(sa.text("SELECT customer_id, category FROM customer_profiles")).all()
    return {int(cid) for cid, category in rows if _normalize_category(category) in NON_CONSUMER_CATEGORIES}


def _as_datetime(value):
    if value is None or isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def _berlin_date(created_at) -> date:
    value = _as_datetime(created_at)
    if value is None:
        return datetime.now(BERLIN).date()
    return value.replace(tzinfo=timezone.utc).astimezone(BERLIN).date()


def upgrade() -> None:
    op.create_table('contract_basis_clauses',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('basis_key', sa.String(length=30), nullable=False),
    sa.Column('clause_text', sa.Text(), nullable=True),
    sa.Column('reviewed_on', sa.Date(), nullable=True),
    sa.Column('reviewed_by', sa.String(length=160), nullable=True),
    sa.Column('updated_by_name', sa.String(length=160), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('basis_key', name='uq_contract_basis_clause_key')
    )
    op.create_table('order_contract_basis_changes',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('order_id', sa.Integer(), nullable=False),
    sa.Column('old_basis', sa.String(length=30), nullable=False),
    sa.Column('new_basis', sa.String(length=30), nullable=False),
    sa.Column('reason', sa.Text(), nullable=False),
    sa.Column('changed_by_name', sa.String(length=160), nullable=False),
    sa.Column('changed_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('order_contract_basis_changes', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_order_contract_basis_changes_order_id'), ['order_id'], unique=False)

    with op.batch_alter_table('customers', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_consumer', sa.Boolean(), server_default='1', nullable=False))

    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.add_column(sa.Column('contract_basis', sa.String(length=30), server_default='bgb', nullable=False))
        batch_op.add_column(sa.Column('contract_basis_manual', sa.Boolean(), server_default='0', nullable=False))

    with op.batch_alter_table('quote_document_meta', schema=None) as batch_op:
        batch_op.add_column(sa.Column('contract_basis', sa.String(length=30), server_default='bgb', nullable=False))

    bind = op.get_bind()

    # Verbraucher-Merkmal aus der Kategorie ableiten (gebundene Parameter statt 0/1-Literalen,
    # siehe CLAUDE.md "PostgreSQL-Umstieg").
    ids = sorted(_non_consumer_customer_ids(bind))
    update = sa.text("UPDATE customers SET is_consumer = :flag WHERE id IN :ids").bindparams(
        sa.bindparam("ids", expanding=True)
    )
    for start in range(0, len(ids), 500):
        bind.execute(update, {"flag": False, "ids": ids[start:start + 500]})

    # Fehlende Angebotskopf-Zeilen mit "bgb" anlegen (sonst bekäme ein altes Angebot beim ersten
    # Öffnen die Vorgabe für neue Angebote).
    default_term = bind.execute(
        sa.text("SELECT label FROM payment_terms WHERE is_default = :yes AND archived = :no ORDER BY id"),
        {"yes": True, "no": False},
    ).scalar()
    missing = bind.execute(sa.text(
        "SELECT q.id, q.created_at FROM quotes q "
        "LEFT JOIN quote_document_meta m ON m.quote_id = q.id WHERE m.id IS NULL ORDER BY q.id"
    )).all()
    if missing:
        meta = sa.table(
            'quote_document_meta',
            sa.column('quote_id', sa.Integer), sa.column('quote_date', sa.Date),
            sa.column('valid_until', sa.Date), sa.column('payment_terms', sa.Text),
            sa.column('contract_basis', sa.String), sa.column('updated_at', sa.DateTime),
        )
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        rows = []
        for quote_id, created_at in missing:
            qdate = _berlin_date(created_at)
            rows.append({
                "quote_id": int(quote_id), "quote_date": qdate, "valid_until": qdate + timedelta(days=30),
                "payment_terms": default_term, "contract_basis": "bgb", "updated_at": now,
            })
        op.bulk_insert(meta, rows)


def downgrade() -> None:
    bind = op.get_bind()
    clauses = bind.execute(sa.text(
        "SELECT COUNT(*) FROM contract_basis_clauses "
        "WHERE COALESCE(clause_text, '') <> '' OR reviewed_on IS NOT NULL OR COALESCE(reviewed_by, '') <> ''"
    )).scalar()
    changes = bind.execute(sa.text("SELECT COUNT(*) FROM order_contract_basis_changes")).scalar()
    quotes = bind.execute(sa.text("SELECT COUNT(*) FROM quote_document_meta WHERE contract_basis <> 'bgb'")).scalar()
    orders = bind.execute(sa.text("SELECT COUNT(*) FROM orders WHERE contract_basis <> 'bgb'")).scalar()
    non_consumer = _non_consumer_customer_ids(bind)
    edited = sum(
        1 for cid, flag in bind.execute(sa.text("SELECT id, is_consumer FROM customers")).all()
        if bool(flag) != (int(cid) not in non_consumer)
    )
    if clauses or changes or quotes or orders or edited:
        raise RuntimeError(
            f"Downgrade abgebrochen: {clauses} Klauseltexte, {changes} Änderungen am Auftrag, "
            f"{quotes} Angebote und {orders} Aufträge mit anderer Vertragsgrundlage als bgb, "
            f"{edited} Kunden mit von Hand geändertem Verbraucher-Merkmal. "
            "Vorher sichern, siehe Docstring dieser Migration."
        )

    with op.batch_alter_table('quote_document_meta', schema=None) as batch_op:
        batch_op.drop_column('contract_basis')

    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.drop_column('contract_basis_manual')
        batch_op.drop_column('contract_basis')

    with op.batch_alter_table('customers', schema=None) as batch_op:
        batch_op.drop_column('is_consumer')

    with op.batch_alter_table('order_contract_basis_changes', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_order_contract_basis_changes_order_id'))

    op.drop_table('order_contract_basis_changes')
    op.drop_table('contract_basis_clauses')
