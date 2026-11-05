"""zuordnung_lohnbuero -- die Zuordnung für den DATEV-Export mit den Werten des Lohnbüros (seit 1.9.214, L1a Stufe 6, Punkt 3)

Stellt in lohnart_zuordnungen vier Zeilen um, aber nur, wo noch genau der bisherige Vorgabewert steht (Kennzeichen, Lohnart, Monatszeile):

    kalender:heiligabend     BF / ohne Lohnart          -> FR / 1080
    kalender:silvester       AF / ohne Lohnart          -> UU / ohne Lohnart
    schlechtwetter:winter    Monatszeile 8110           -> WA / 8195, je Tag (keine Monatszeile)
    art:berufsschule         leer (wie die Kategorie)   -> FE / ohne Lohnart

Eine Zeile, die jemand in den Einstellungen geändert hat, bleibt, wie sie ist -- die Migration nennt sie in der Ausgabe von update.sh.
Fehlt eine Zeile, legt sie der Start an (app/grunddaten.py, app/lohnarten.py::START, schon mit den neuen Werten). Schlechtwetter Sommer
bleibt leer.

downgrade(): dieselben vier Zeilen zurück, nur wo genau der neue Wert steht; art:berufsschule wird leer (vor 1.9.214 hieß eine leere Zeile
dasselbe wie keine).

Revision ID: a3f61c8d2b95
Revises: 8b4c2f9e1d07
Create Date: 2026-11-05

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a3f61c8d2b95'
down_revision = '8b4c2f9e1d07'
branch_labels = None
depends_on = None

BISHER = {"kalender:heiligabend": ("BF", None, False), "kalender:silvester": ("AF", None, False),
          "schlechtwetter:winter": (None, "8110", True), "art:berufsschule": (None, None, False)}
NEU = {"kalender:heiligabend": ("FR", "1080", False), "kalender:silvester": ("UU", None, False),
       "schlechtwetter:winter": ("WA", "8195", False), "art:berufsschule": ("FE", None, False)}


def umstellen(bind, von: dict, nach: dict) -> tuple[list[str], list[str]]:
    """(umgestellt, gelassen) -- gelassen: die Zeile steht, trägt aber nicht genau den Wert von „von“."""
    umgestellt, gelassen = [], []
    for schluessel, (kennzeichen, lohnart, monatszeile) in nach.items():
        zeile = bind.execute(sa.text("SELECT id, kennzeichen, lohnart, monatszeile FROM lohnart_zuordnungen WHERE schluessel = :s"),
                             {"s": schluessel}).first()
        if zeile is None:
            continue
        if (zeile.kennzeichen or None, zeile.lohnart or None, bool(zeile.monatszeile)) != von[schluessel]:
            gelassen.append(schluessel)
            continue
        bind.execute(sa.text("UPDATE lohnart_zuordnungen SET kennzeichen = :k, lohnart = :l, monatszeile = :m WHERE id = :id"),
                     {"k": kennzeichen, "l": lohnart, "m": monatszeile, "id": zeile.id})
        umgestellt.append(schluessel)
    return umgestellt, gelassen


def upgrade() -> None:
    _umgestellt, gelassen = umstellen(op.get_bind(), BISHER, NEU)
    for schluessel in gelassen:
        print(f"Zuordnung {schluessel}: von Hand geändert, nicht umgestellt -- bitte in den Einstellungen prüfen (Wert des Lohnbüros: "
              f"{NEU[schluessel][0] or '–'} / {NEU[schluessel][1] or 'ohne Lohnart'}).")


def downgrade() -> None:
    umstellen(op.get_bind(), NEU, BISHER)
