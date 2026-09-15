"""app user role office field

Revision ID: 7a2b4e9f1c3d
Revises: 1ccb91b19e8a
Create Date: 2026-09-15 10:35:00.000000

Reine Daten-Migration, kein Schema-Umbau -- app_users.role war immer schon eine unbeschränkte
String(30)-Spalte ohne CHECK-Constraint (siehe CLAUDE.md "Rechtekonzept"), die einzige
Einschränkung auf zwei Werte saß in Pydantic (app/schemas.py). Mit der dritten Rolle "office"
(Büro) neben "admin" und dem neuen "field" (Monteur) wird der bisherige generische Wert "user"
zu "office" -- fachlich unverändert: ein "user"-Konto hatte bereits vollen, nur nicht-admin
Zugriff auf alles außer den zwölf admin-gateten Verwaltungsbereichen (siehe CLAUDE.md), exakt
das, was "office" jetzt weiterhin bedeutet. Auf der echten, lokalen dachkonzepte_erp.db betrifft
das 0 Zeilen (beide bestehenden Konten sind bereits "admin", siehe CLAUDE.md "Rechtekonzept" --
Bestandsschutz) -- die Migration existiert trotzdem für jede andere Installation/Testdatenbank,
die schon eine "user"-Zeile tragen könnte.

downgrade() kann "field" nicht verlustfrei zurückführen (dieser Wert existierte im Zwei-Rollen-
Modell schlicht nicht) -- die nächstliegende, am wenigsten überraschende Entsprechung ist "user"
(dieselbe Nicht-Admin-Zugriffsbreite wie das alte "user", nicht die engere von "field"). Beide
neuen Werte ("office" UND "field") werden beim Zurückrollen deshalb gleich behandelt.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7a2b4e9f1c3d'
down_revision = '1ccb91b19e8a'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE app_users SET role = 'office' WHERE role = 'user'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE app_users SET role = 'user' WHERE role IN ('office', 'field')"))
