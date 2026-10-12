"""nummern_eindeutig -- jede vergebene Nummer eindeutig in der Datenbank, alle sieben Nummernkreise (seit 1.8.77)

- invoices.invoice_number: UNIQUE (uq_invoice_number), neu. Stornorechnungen ziehen aus demselben Nummernkreis.
- reminders.reminder_number: UNIQUE (uq_reminder_number), neu.
- Rechnungen und Mahnungen im Entwurf haben keine Nummer (NULL) und bleiben beliebig viele erlaubt: NULL ist in einer
  UNIQUE-Bedingung unter PostgreSQL und SQLite nie gleich.
- Kunde, Anfrage, Projekt, Angebot und Auftrag sind seit der Baseline (2befd7907eef) eindeutig (uq_customer_number,
  uq_inquiry_number, uq_project_number, uq_quote_number, uq_order_number) -- hier nur geprüft, dass es so ist.

Vorher, ohne etwas zu ändern: sucht jede Nummer, die in ihrem Nummernkreis mehr als einmal vergeben ist (alle sieben, dieselbe
Frage wie Ergebnis 1 von scripts/pruefabfrage_nummernkreise.sql), und jede der fünf bestehenden Bedingungen, die fehlt -- und
bricht mit einer Liste ab (Nummernkreis, Nummer, Anzahl, IDs) statt mit einem Datenbankfehler mitten im Anlegen.

downgrade(): entfernt die beiden neuen Bedingungen; keine Nummer geht verloren.

Revision ID: f3a8c2d6b190
Revises: 9b4e2c7a1d58
Create Date: 2026-10-12

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f3a8c2d6b190'
down_revision = '9b4e2c7a1d58'
branch_labels = None
depends_on = None

# (Bezeichnung, Tabelle, Spalte, Bedingung, in dieser Migration angelegt) -- die Zuordnung wie
# app/settings.py::_existing_column(), hier fest, damit die Migration nicht vom späteren App-Code abhängt.
NUMMERNKREISE = (
    ("Kunde", "customer_profiles", "customer_number", "uq_customer_number", False),
    ("Anfrage", "inquiries", "inquiry_number", "uq_inquiry_number", False),
    ("Projekt", "projects", "project_number", "uq_project_number", False),
    ("Angebot", "quotes", "quote_number", "uq_quote_number", False),
    ("Auftrag", "orders", "order_number", "uq_order_number", False),
    ("Rechnung", "invoices", "invoice_number", "uq_invoice_number", True),
    ("Mahnung", "reminders", "reminder_number", "uq_reminder_number", True),
)


def _dubletten(bind) -> list[tuple[str, str, str, list[int]]]:
    """(Nummernkreis, Tabelle, Nummer, IDs) je Nummer, die in ihrem Nummernkreis mehr als einmal vergeben ist; NULL (Entwurf)
    zählt nicht."""
    found = []
    for label, table, column, _uq, _neu in NUMMERNKREISE:
        rows = bind.execute(sa.text(
            f"SELECT {column}, id FROM {table} WHERE {column} IN "
            f"(SELECT {column} FROM {table} WHERE {column} IS NOT NULL GROUP BY {column} HAVING COUNT(*) > 1) "
            f"ORDER BY {column}, id")).all()
        groups: dict[str, list[int]] = {}
        for number, row_id in rows:
            groups.setdefault(number, []).append(row_id)
        found.extend((label, table, number, ids) for number, ids in groups.items())
    return found


def _fehlende_bedingungen(bind) -> list[str]:
    """Die schon bestehenden Bedingungen (Baseline), die in dieser Datenbank fehlen -- als Text."""
    inspector = sa.inspect(bind)
    missing = []
    for label, table, column, uq, neu in NUMMERNKREISE:
        if neu:
            continue
        unique = [c["column_names"] for c in inspector.get_unique_constraints(table)]
        unique += [i["column_names"] for i in inspector.get_indexes(table) if i.get("unique")]
        if [column] not in unique:
            missing.append(f"{label}: {table}.{column} ohne Bedingung „eindeutig“ ({uq})")
    return missing


def pruefen(bind) -> None:
    """Bricht ab, bevor etwas geändert ist: mit der Liste der mehrfach vergebenen Nummern und der fehlenden Bedingungen."""
    lines = [f"  - {label} {number}: {len(ids)}-mal vergeben ({table}.id {', '.join(str(i) for i in ids)})"
             for label, table, number, ids in _dubletten(bind)]
    lines += [f"  - {text}" for text in _fehlende_bedingungen(bind)]
    if lines:
        raise RuntimeError(
            "Migration abgebrochen, nichts geändert: jede vergebene Nummer soll in ihrem Nummernkreis eindeutig sein, "
            "aber in dieser Datenbank\n" + "\n".join(lines) + "\n"
            "Bitte zuerst klären (Dubletten und Lücken zeigt scripts/pruefabfrage_nummernkreise.sql), dann erneut einspielen.")


def upgrade() -> None:
    pruefen(op.get_bind())
    for _label, table, column, uq, neu in NUMMERNKREISE:
        if neu:
            with op.batch_alter_table(table, schema=None) as batch_op:
                batch_op.create_unique_constraint(uq, [column])


def downgrade() -> None:
    for _label, table, _column, uq, neu in reversed(NUMMERNKREISE):
        if neu:
            with op.batch_alter_table(table, schema=None) as batch_op:
                batch_op.drop_constraint(uq, type_='unique')
