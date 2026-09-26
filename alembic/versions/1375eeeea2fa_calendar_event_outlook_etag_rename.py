"""calendar event outlook etag rename

Revision ID: 1375eeeea2fa
Revises: 3e187156fa80
Create Date: 2026-09-26 14:43:52.477110

Reine Spalten-Umbenennung, kein Datenverlust-Risiko (Regel 1 greift nicht -- keine neue NOT-NULL-
Spalte, nur ein bestehendes, bereits nullable Feld wird umbenannt): `calendar_events.
outlook_change_key` -> `outlook_etag`. Siehe app/models.py::CalendarEvent-Klassendocstring
"Korrektur (seit 1.7.5)" für die vollständige Begründung -- kurz: Microsoft Graph liefert
`changeKey` in Delta-Antworten nachweislich nie (auch nicht über `$select`, das für Kalender-
Delta-Abfragen laut Microsoft-Dokumentation ignoriert wird), sondern ausschließlich `@odata.etag`
-- die 1.7.3-Fassung dieser Spalte konnte dadurch für ihren eigentlichen Zweck (Echo-Erkennung
gegen einen eingehenden Delta-Eintrag) niemals einen Treffer liefern. Die Spalte trug zum
Zeitpunkt dieser Migration in der echten, lokalen Datenbank bei keiner einzigen Zeile einen von
Graph tatsächlich verwendbaren Wert (bestätigt per Produktions-Diagnose: `change_key_gespeichert`/
`change_key_eingehend` standen in jeder Zeile auf `None`) -- ein Datenverlust durch die
Umbenennung ist deshalb ausgeschlossen, unabhängig vom aktuellen Inhalt der Spalte.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1375eeeea2fa'
down_revision = '3e187156fa80'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('calendar_events', schema=None) as batch_op:
        batch_op.alter_column('outlook_change_key', new_column_name='outlook_etag',
                               existing_type=sa.String(length=255))


def downgrade() -> None:
    with op.batch_alter_table('calendar_events', schema=None) as batch_op:
        batch_op.alter_column('outlook_etag', new_column_name='outlook_change_key',
                               existing_type=sa.String(length=255))
