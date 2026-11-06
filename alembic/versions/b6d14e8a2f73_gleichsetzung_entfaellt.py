"""gleichsetzung_entfaellt -- „DATEV-Nr. = ERP-Nr.“ entfällt (seit 1.9.230, Stufe 6, R3a, Punkt 0a)

Bis 1.9.229 nahm die Lohndatei bei eingeschaltetem Schalter (time_backoffice_advanced_settings.datev_personnel_equals_erp_number) die
ERP-Mitarbeiternummer als Personalnummer -- ungeprüft, „MA-0042“ ging so in die Datei. Seit 1.9.230 liest niemand den Schalter mehr; es gilt nur
die DATEV-Personalnummer der Lohnstammdaten. Die Spalte bleibt ungenutzt stehen (wie Zielsystem und Lohnarten seit 1.9.224).

Daten: nur wenn der Schalter an war, übernimmt die Migration je Person die Mitarbeiternummer (ohne Leerzeichen am Rand) als DATEV-Personalnummer --
nur eine Nummer aus genau 5 Ziffern, und nur, wenn keine andere Person sie in den Lohnstammdaten trägt und sie für keine andere Person (oder aus der
eingelesenen Liste ohne Person) gemerkt ist. Eine abweichende gespeicherte Nummer wird ersetzt: mit dem Schalter nahm die Lohndatei die
Mitarbeiternummer. Ohne Zeile der Lohnstammdaten entsteht eine mit der Vorgabe (Umfang „alles“, wie load_employee_payroll() sie liest). Die Nummer wird
für die Person gemerkt (personalnummern_vergeben), falls noch nicht. Alles andere bleibt -- eine Person ohne gültige Nummer nennt danach „Prüfen“
(„Personalnummer fehlt“ bzw. „hat nicht genau 5 Ziffern“), die Lohndatei entsteht dann nicht.

downgrade(): ändert keine Daten. Mit eingeschaltetem Schalter liest der Stand davor ohnehin die Mitarbeiternummer, die übernommene Nummer ist
dieselbe; eine neu angelegte Zeile der Lohnstammdaten trägt die Vorgabe, die der Stand davor ohne Zeile las.

Revision ID: b6d14e8a2f73
Revises: d5a8e3c71b42
Create Date: 2026-11-06

"""
import re
from datetime import datetime

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b6d14e8a2f73'
down_revision = 'd5a8e3c71b42'
branch_labels = None
depends_on = None

FUENF = re.compile(r"^[0-9]{5}$")


def uebernahmen(bind) -> list[tuple[int, int | None, str | None, str]]:
    """Je Person, deren Mitarbeiternummer übernommen wird: (employee_id, id der Lohnstammdaten oder None, bisherige DATEV-Nummer, neue)."""
    gleich = bind.execute(sa.text("SELECT datev_personnel_equals_erp_number FROM time_backoffice_advanced_settings WHERE id = 1")).scalar()
    if not gleich:
        return []
    zeilen = bind.execute(sa.text(
        "SELECT e.id, e.employee_number, p.id, p.datev_personnel_number FROM employees e "
        "LEFT JOIN employee_payroll_settings p ON p.employee_id = e.id ORDER BY e.id, p.id")).all()
    getragen: dict[str, int] = {}
    for eid, _erp, _pid, datev in zeilen:
        if datev:
            getragen.setdefault(datev.strip(), eid)
    gemerkt = {n: eid for n, eid in bind.execute(sa.text("SELECT nummer, employee_id FROM personalnummern_vergeben"))}
    ergebnis, gesehen = [], set()
    for eid, erp, pid, datev in zeilen:
        if eid in gesehen:
            continue  # je Person die erste Zeile der Lohnstammdaten (so liest sie auch die App)
        gesehen.add(eid)
        nummer = (erp or "").strip()
        if not FUENF.match(nummer) or (datev or "").strip() == nummer:
            continue
        if getragen.get(nummer, eid) != eid or (nummer in gemerkt and gemerkt[nummer] != eid):
            continue
        ergebnis.append((eid, pid, datev, nummer))
        getragen[nummer] = eid
    return ergebnis


def anwenden(bind) -> int:
    jetzt = datetime.utcnow()
    liste = uebernahmen(bind)
    for eid, pid, _alt, nummer in liste:
        if pid is None:
            bind.execute(sa.text("INSERT INTO employee_payroll_settings (employee_id, datev_personnel_number, payroll_export_enabled, export_umfang, "
                                 "azubi, updated_at) VALUES (:e, :n, :t, 'alles', :f, :jetzt)"), {"e": eid, "n": nummer, "t": True, "f": False,
                                                                                                 "jetzt": jetzt})
        else:
            bind.execute(sa.text("UPDATE employee_payroll_settings SET datev_personnel_number = :n, updated_at = :jetzt WHERE id = :id"),
                         {"n": nummer, "id": pid, "jetzt": jetzt})
        vorhanden = bind.execute(sa.text("SELECT id FROM personalnummern_vergeben WHERE nummer = :n"), {"n": nummer}).first()
        if vorhanden is None:
            bind.execute(sa.text("INSERT INTO personalnummern_vergeben (nummer, employee_id, vergeben_am) VALUES (:n, :e, :jetzt)"),
                         {"n": nummer, "e": eid, "jetzt": jetzt})
    return len(liste)


def upgrade() -> None:
    anwenden(op.get_bind())


def downgrade() -> None:
    pass  # keine Daten zurück, siehe oben
