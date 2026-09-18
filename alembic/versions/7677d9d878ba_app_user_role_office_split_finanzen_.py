"""app user role office split finanzen auftrag

Revision ID: 7677d9d878ba
Revises: b2226e22b9f0
Create Date: 2026-09-18 00:00:00.000000

Reine Daten-Migration, kein Schema-Umbau -- app_users.role war immer schon eine unbeschränkte
String(30)-Spalte ohne CHECK-Constraint (siehe CLAUDE.md "Rechtekonzept" -> "Vier Rollen"), die
einzige Einschränkung saß in Pydantic (app/schemas.py). Etappe 1 der Rollen-Erweiterung: die
bisherige, einzelne Rolle "office" wird in zwei getrennte Rollen aufgeteilt -- "buero_finanzen"
(alles Fachliche/Kaufmännische PLUS Kalkulationsgrundlagen/Betriebskosten-Übersicht/
Mitarbeitervergütung, Schnittstelle zum Steuerberater) und "buero_auftrag" (derselbe fachliche/
kaufmännische Kern OHNE diese drei Bereiche). "field" und "admin" bleiben unverändert.

Betreiber-Vorgabe für die Migration (nicht geraten, siehe CLAUDE.md "Rechtekonzept" ->
"Bestandskonten"): ein bestehendes, reines Büro-Konto ("office") wird "buero_finanzen" -- die
umfassendere der beiden neuen Rollen, damit ein bereits eingerichtetes Büro-Konto durch diese
Migration NIE Zugriff verliert (Standardschutz gegen versehentlichen Funktionsverlust bei einem
Rollen-Split, exakt umgekehrt zur "sicherste Rolle zuerst"-Regel bei NEUEN Konten -- dort gilt
seit dieser Version "buero_auftrag" als restriktiverer Standardwert, siehe app/schemas.py).

Auf der echten, lokalen dachkonzepte_erp.db betrifft das 0 Zeilen -- vor dieser Migration direkt
geprüft (siehe CLAUDE.md "Rechtekonzept"): beide bestehenden Konten (Tobias, Admin) sind bereits
"admin", kein einziges "office"-Konto existiert. Die Migration existiert trotzdem für jede andere
Installation/Testdatenbank, die noch eine "office"-Zeile tragen könnte.

downgrade() kann buero_finanzen/buero_auftrag nicht verlustfrei unterscheiden zurückführen (die
Aufteilung existierte im Drei-Rollen-Modell schlicht nicht) -- beide werden beim Zurückrollen
gleich auf "office" abgebildet, exakt dasselbe Prinzip wie beim vorherigen Rollen-Split
(7a2b4e9f1c3d, dort office/field -> user).
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7677d9d878ba'
down_revision = 'b2226e22b9f0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE app_users SET role = 'buero_finanzen' WHERE role = 'office'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE app_users SET role = 'office' WHERE role IN ('buero_finanzen', 'buero_auftrag')"))
