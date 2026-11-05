"""personalnummer_fuenf_stellen -- jede DATEV-Personalnummer hat genau 5 Ziffern (seit 1.9.212, L1a Stufe 6, Punkt 1, Antwort des Lohnbüros)

Füllt vorhandene Nummern links mit Nullen auf 5 Stellen auf („9005“ -> „09005“, „101“ -> „00101“):
- employee_payroll_settings.datev_personnel_number
- personalnummern_vergeben.nummer (die gemerkten, dauerhaft gesperrten Nummern, seit 1.9.177)
Aufgefüllt wird nur eine Nummer aus 1 bis 4 Ziffern; eine mit Buchstaben, Leerzeichen oder mehr als 5 Ziffern bleibt, wie sie ist
(scripts/pruefe_zeitregeln.py nennt sie). Die ERP-Mitarbeiternummer (employees.employee_number) bleibt unberührt, auch bei „DATEV-Nr. = ERP-Nr.“:
sie gehört den Stammdaten des Mitarbeiters, das Büro ändert sie im Mitarbeiterformular (Festlegung 1.9.212 Nr. 4).

Vorher, ohne etwas zu ändern: pruefen() rechnet die neuen Werte und bricht ab, wenn danach zwei Zeilen derselben Tabelle dieselbe Nummer trügen
(„101“ und „0101“) -- welche Person die Nummer behält, entscheidet das Büro (wie Festlegung 1.9.168 Nr. 5).

downgrade(): nimmt die führenden Nullen einer 5-stelligen Nummer wieder weg („09005“ -> „9005“; „00000“ bleibt) -- auch bei einer Nummer, die
nach dem Einspielen neu so eingetragen wurde; die alte Fassung erlaubt keine führende Null. Eine Nummer, die schon vor dem Einspielen mit
führender Null gespeichert war (seit 1.9.168 vom Speichern abgelehnt), kommt ohne Nullen zurück.

Revision ID: 5d2e8a71c4f3
Revises: 1e425fe7faa6
Create Date: 2026-11-05

"""
import re

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5d2e8a71c4f3'
down_revision = '1e425fe7faa6'
branch_labels = None
depends_on = None

TABELLEN = (("employee_payroll_settings", "datev_personnel_number"), ("personalnummern_vergeben", "nummer"))
KURZ = re.compile(r"^[0-9]{1,4}$")
MIT_NULL = re.compile(r"^0[0-9]{4}$")


def aufgefuellt(nummer: str | None) -> str | None:
    """Der neue Wert einer Nummer -- None: bleibt."""
    return nummer.zfill(5) if nummer is not None and KURZ.match(nummer) else None


def ohne_nullen(nummer: str | None) -> str | None:
    """Für downgrade(): „09005“ -> „9005“; None: bleibt („00000“ und alles andere)."""
    if nummer is None or not MIT_NULL.match(nummer) or nummer == "00000":
        return None
    return nummer.lstrip("0")


def aenderungen(bind, umrechnen) -> dict[str, list[tuple[int, str, str]]]:
    """Je Tabelle (id, alt, neu) für jede Zeile, die sich ändert."""
    je = {}
    for tabelle, spalte in TABELLEN:
        je[tabelle] = [(i, alt, umrechnen(alt)) for i, alt in bind.execute(sa.text(f"SELECT id, {spalte} FROM {tabelle} ORDER BY id"))
                       if umrechnen(alt) is not None]
    return je


def kollisionen(bind, umrechnen) -> list[str]:
    """Nummern, die nach dem Umrechnen zwei Zeilen derselben Tabelle trügen -- je eine Zeile Text (ohne Namen)."""
    liste = []
    for tabelle, spalte in TABELLEN:
        je: dict[str, list[str]] = {}
        for i, alt in bind.execute(sa.text(f"SELECT id, {spalte} FROM {tabelle} WHERE {spalte} IS NOT NULL ORDER BY id")):
            je.setdefault(umrechnen(alt) or alt, []).append(alt)
        liste += [f"  - {tabelle}: {', '.join(alte)} -> {neu}" for neu, alte in je.items() if len(alte) > 1]
    return liste


def pruefen(bind, umrechnen=aufgefuellt) -> None:
    """Bricht ab, bevor etwas geändert ist."""
    liste = kollisionen(bind, umrechnen)
    if liste:
        raise RuntimeError(
            "Migration abgebrochen, nichts geändert: nach dem Auffüllen auf 5 Ziffern trügen zwei Zeilen dieselbe Personalnummer:\n"
            + "\n".join(liste) + "\nBitte zuerst klären (welche Person die Nummer behält), dann erneut einspielen.")


def anwenden(bind, umrechnen) -> int:
    n = 0
    for tabelle, zeilen in aenderungen(bind, umrechnen).items():
        spalte = dict(TABELLEN)[tabelle]
        for i, _alt, neu in zeilen:
            bind.execute(sa.text(f"UPDATE {tabelle} SET {spalte} = :neu WHERE id = :id"), {"neu": neu, "id": i})
            n += 1
    return n


def upgrade() -> None:
    bind = op.get_bind()
    pruefen(bind)
    anwenden(bind, aufgefuellt)


def downgrade() -> None:
    bind = op.get_bind()
    pruefen(bind, ohne_nullen)
    anwenden(bind, ohne_nullen)
