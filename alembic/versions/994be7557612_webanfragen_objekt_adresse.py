"""webanfragen_objekt_adresse -- Adresse des Objekts am Eingang der Anfragen der Webseite (seit 1.10.3, Stufe W1b)

Neue Spalten webanfragen.objekt_strasse, objekt_plz, objekt_ort (alle leer erlaubt). Der Bestand bekommt sie aus seinem gespeicherten Umschlag -- nur
aus den strukturierten Angaben, wie app/webanfrage_angaben.py::objekt_adresse() (hier eingefroren, damit die Migration nicht vom Code von heute
abhängt): Reparatur und Wartung daten.objekt (dk-reparatur/1), Dach und PV daten.strasse/plz/ort, sonst keine. Ein unlesbarer Umschlag oder ein Wert
außerhalb der Grenzen bleibt leer.

downgrade(): die drei Spalten fallen weg (aus dem Umschlag jederzeit neu ableitbar).

Revision ID: 994be7557612
Revises: 2394d984cea8
Create Date: 2026-11-19

"""
import json
import re

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '994be7557612'
down_revision = '2394d984cea8'
branch_labels = None
depends_on = None

_STEUERZEICHEN = re.compile(r"[\x00-\x1f\x7f]")
_LEERRAUM = re.compile(r"\s+")


def _einzeilig(wert, hoechstens):
    if not isinstance(wert, str) or _STEUERZEICHEN.search(wert):
        return None
    text = _LEERRAUM.sub(" ", wert).strip()
    return text if text and len(text) <= hoechstens else None


def adresse_aus_umschlag(art, umschlag_text):
    """{strasse, plz, ort} oder None -- Stand 1.10.3 von app/webanfrage_angaben.py::objekt_adresse()."""
    try:
        umschlag = json.loads(umschlag_text) if umschlag_text else None
    except (ValueError, RecursionError):
        return None
    daten = umschlag.get("daten") if isinstance(umschlag, dict) else None
    if not isinstance(daten, dict):
        return None
    if art in ("reparatur", "wartung"):
        quelle = daten.get("objekt") if daten.get("schema") == "dk-reparatur/1" else None
    elif art in ("dach", "pv"):
        quelle = daten
    else:
        return None
    if not isinstance(quelle, dict):
        return None
    adresse = {"strasse": _einzeilig(quelle.get("strasse"), 100), "plz": _einzeilig(quelle.get("plz"), 10), "ort": _einzeilig(quelle.get("ort"), 60)}
    return adresse if any(adresse.values()) else None


def upgrade() -> None:
    with op.batch_alter_table('webanfragen', schema=None) as batch_op:
        batch_op.add_column(sa.Column('objekt_strasse', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('objekt_plz', sa.String(length=10), nullable=True))
        batch_op.add_column(sa.Column('objekt_ort', sa.String(length=60), nullable=True))

    bind = op.get_bind()
    tabelle = sa.table('webanfragen', sa.column('id', sa.Integer), sa.column('art', sa.String), sa.column('umschlag', sa.Text),
                       sa.column('objekt_strasse', sa.String), sa.column('objekt_plz', sa.String), sa.column('objekt_ort', sa.String))
    for zeile in bind.execute(sa.select(tabelle.c.id, tabelle.c.art, tabelle.c.umschlag).order_by(tabelle.c.id)).all():
        adresse = adresse_aus_umschlag(zeile.art, zeile.umschlag)
        if adresse:
            bind.execute(tabelle.update().where(tabelle.c.id == zeile.id).values(
                objekt_strasse=adresse["strasse"], objekt_plz=adresse["plz"], objekt_ort=adresse["ort"]))


def downgrade() -> None:
    with op.batch_alter_table('webanfragen', schema=None) as batch_op:
        batch_op.drop_column('objekt_ort')
        batch_op.drop_column('objekt_plz')
        batch_op.drop_column('objekt_strasse')
