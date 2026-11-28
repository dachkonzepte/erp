"""portal_aus_seit -- wann das Kundenportal am Kunden ausgeschaltet wurde (seit 1.11.51, W1c Stufe 2, S2-0 c; Antwort W2-3 vom 28.11.2026)

customers.portal_aus_seit (naiv UTC, leer erlaubt): 6 Monate danach geht der Zugang (Stufe 2, nach Vorschau und Bestätigung). Bestand: für jeden Kunden mit
ausgeschaltetem Portal der jüngste Eintrag der Änderungshistorie „Kundenportal an: Nein“ (audit_logs, Art „Kunde“, Feld portal_aktiv, neuer Wert „Nein“) --
war das Portal nie an, bleibt die Spalte leer. Schreibt mit Core (Archivschutz, app/archivschutz.py: Migrationen schreiben mit Core).

downgrade(): nur die Spalte weg.

Revision ID: f6b1d8e3a925
Revises: d4a8c2f61b07
Create Date: 2026-11-28

"""
import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = 'f6b1d8e3a925'
down_revision = 'd4a8c2f61b07'
branch_labels = None
depends_on = None


def bestand_fuellen(bind) -> int:
    """Der jüngste Zeitpunkt „Kundenportal an: Nein“ je Kunde mit ausgeschaltetem Portal; Rückgabe: wie viele Kunden ihn bekamen."""
    return bind.execute(sa.text(
        "UPDATE customers SET portal_aus_seit = (SELECT max(a.occurred_at) FROM audit_logs a WHERE a.entity_type = 'Kunde' "
        "AND a.entity_id = CAST(customers.id AS VARCHAR(40)) AND a.field_name = 'portal_aktiv' AND a.new_value = 'Nein') "
        "WHERE portal_aktiv = :aus AND EXISTS (SELECT 1 FROM audit_logs a WHERE a.entity_type = 'Kunde' "
        "AND a.entity_id = CAST(customers.id AS VARCHAR(40)) AND a.field_name = 'portal_aktiv' AND a.new_value = 'Nein')"),
        {"aus": False}).rowcount


def upgrade() -> None:
    op.add_column('customers', sa.Column('portal_aus_seit', sa.DateTime(), nullable=True))
    bestand_fuellen(op.get_bind())


def downgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":  # ohne Neuaufbau von customers (auf sie zeigen viele Tabellen, vgl. tests/test_v325_contract_basis.py)
        op.execute("ALTER TABLE customers DROP COLUMN portal_aus_seit")
    else:
        op.drop_column('customers', 'portal_aus_seit')
