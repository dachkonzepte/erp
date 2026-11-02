"""personalnummer_eindeutig_und_export_umfang -- DATEV-Personalnummer eindeutig, Export-Umfang je Person (seit 1.9.168, Lohn L1a, Punkt 3)

- employee_payroll_settings.datev_personnel_number: UNIQUE (uq_employee_payroll_datev_number). Leer (NULL) bleibt beliebig oft erlaubt.
  Vorher, ohne etwas zu ändern: eine Nummer aus Leerzeichen wird NULL, Leerzeichen um eine Nummer fallen weg (wie das Speichern seit
  jeher); dann sucht pruefen() jede Nummer, die mehr als eine Person trägt, und bricht mit der Liste ab (dieselbe Frage wie Ergebnis 1
  von scripts/pruefabfrage_personalnummern.sql) statt mit einem Datenbankfehler mitten im Anlegen.
- employee_payroll_settings.export_umfang: „alles“, „abwesenheiten“ oder „nichts“ (NOT NULL, server_default „alles“); aus
  payroll_export_enabled = false wird „nichts“.

Das Format (nur Ziffern) prüft das Speichern, nicht die Migration: eine Nummer mit Buchstaben bleibt, scripts/pruefe_zeitregeln.py nennt sie.

downgrade(): payroll_export_enabled aus dem Umfang („nichts“ und „abwesenheiten“ -> false, die alte Fassung kennt keine Abwesenheiten im
Export), Spalte und Bedingung weg. Leerzeichen kommen nicht zurück.

Revision ID: c5a9e3f71d28
Revises: b7e3c91d4a52
Create Date: 2026-11-02

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c5a9e3f71d28'
down_revision = 'b7e3c91d4a52'
branch_labels = None
depends_on = None

UQ = "uq_employee_payroll_datev_number"


def bereinigen(bind) -> None:
    bind.execute(sa.text("UPDATE employee_payroll_settings SET datev_personnel_number = NULL "
                         "WHERE datev_personnel_number IS NOT NULL AND TRIM(datev_personnel_number) = ''"))
    bind.execute(sa.text("UPDATE employee_payroll_settings SET datev_personnel_number = TRIM(datev_personnel_number) "
                         "WHERE datev_personnel_number IS NOT NULL AND datev_personnel_number <> TRIM(datev_personnel_number)"))


def dubletten(bind) -> list[tuple[str, list[int]]]:
    """(Nummer, Mitarbeiter-IDs) je Personalnummer, die mehr als eine Person trägt -- Leerzeichen um die Nummer zählen nicht (so speichert
    das Programm sie), eine leere Nummer ist keine."""
    rows = bind.execute(sa.text(
        "SELECT TRIM(datev_personnel_number) AS nummer, employee_id FROM employee_payroll_settings "
        "WHERE datev_personnel_number IS NOT NULL AND TRIM(datev_personnel_number) <> '' AND TRIM(datev_personnel_number) IN "
        "(SELECT TRIM(datev_personnel_number) FROM employee_payroll_settings WHERE datev_personnel_number IS NOT NULL "
        "GROUP BY TRIM(datev_personnel_number) HAVING COUNT(*) > 1) ORDER BY nummer, employee_id")).all()
    je: dict[str, list[int]] = {}
    for nummer, emp in rows:
        je.setdefault(nummer, []).append(emp)
    return list(je.items())


def pruefen(bind) -> None:
    """Bricht ab, bevor etwas geändert ist."""
    liste = dubletten(bind)
    if liste:
        zeilen = [f"  - Personalnummer {nummer}: {len(ids)} Personen (employees.id {', '.join(str(i) for i in ids)})" for nummer, ids in liste]
        raise RuntimeError(
            "Migration abgebrochen, nichts geändert: jede DATEV-Personalnummer soll genau eine Person tragen, aber in dieser Datenbank\n"
            + "\n".join(zeilen) + "\nBitte zuerst klären (scripts/pruefabfrage_personalnummern.sql), dann erneut einspielen.")


def upgrade() -> None:
    bind = op.get_bind()
    pruefen(bind)
    bereinigen(bind)
    with op.batch_alter_table("employee_payroll_settings", schema=None) as batch_op:
        batch_op.add_column(sa.Column("export_umfang", sa.String(length=20), server_default="alles", nullable=False))
        batch_op.create_unique_constraint(UQ, ["datev_personnel_number"])
    bind.execute(sa.text("UPDATE employee_payroll_settings SET export_umfang = 'nichts' WHERE payroll_export_enabled = :aus"),
                 {"aus": False})


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("UPDATE employee_payroll_settings SET payroll_export_enabled = :an WHERE export_umfang = 'alles'"), {"an": True})
    bind.execute(sa.text("UPDATE employee_payroll_settings SET payroll_export_enabled = :aus WHERE export_umfang <> 'alles'"), {"aus": False})
    with op.batch_alter_table("employee_payroll_settings", schema=None) as batch_op:
        batch_op.drop_constraint(UQ, type_="unique")
        batch_op.drop_column("export_umfang")
