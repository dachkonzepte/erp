"""bedenkenanzeige_antwort_als_beleg -- "Antwort als Beleg" der Startvorlage wird ein Belegfeld (seit 1.8.45)

- Seit 1.8.45 gibt es den Feldtyp "beleg" (PDF oder Foto, am Inhalt erkannt), und das Systemfeld
  bedenkenanzeige.antwort_beleg trägt ihn (app/checklist_purposes.py). Die Startvorlage "Bedenkenanzeige" aus
  0816ece7159b legte es als Fotofeld an.
- Umgestellt wird nur eine unveränderte Startvorlage (Muster 803d94127c12): genau eine Vorlage dieses Namens mit Zweck
  bedenkenanzeige, genau eine Fassung, Entwurf, Felder mit Schlüssel, Reihenfolge und Typ wie 0816ece7159b sie angelegt
  hat. Dann Typ "beleg"; den Hilfetext nur, solange er noch der ursprüngliche ist.
- Sonst bleibt alles, wie es ist, und der Editor weist darauf hin: an einem Entwurf "weicht von der Vorgabe ab: Typ"
  mit "Systemfelder angleichen" (stellt das Systemfeld um), an einer veröffentlichten Fassung ohne Entwurf "entspricht
  nicht mehr den Systemfeldern" -- "Neuen Entwurf anlegen" gleicht an. Schon ausgefüllte Checklisten behalten ihre
  Fassung und damit ihr Fotofeld.
- Kein Schema: Belege liegen in checklist_attachments (kind "beleg").

downgrade(): stellt nur eine Startvorlage zurück, die noch genau der umgestellten Form entspricht. Veröffentlichte
Fassungen mit Belegfeld und hochgeladene Belege bleiben -- der Code vor 1.8.45 kennt den Typ nicht.

Revision ID: 2798ba2fb235
Revises: 0816ece7159b
Create Date: 2026-10-02 18:14:08.754703

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2798ba2fb235'
down_revision = '0816ece7159b'
branch_labels = None
depends_on = None

PURPOSE = "bedenkenanzeige"
LABEL = "Bedenkenanzeige"
_K = PURPOSE + "."
FIELD_KEY = _K + "antwort_beleg"
OLD_HELP = "Foto oder Scan der Antwort (Brief, Fax, ausgedruckte E-Mail)."
NEW_HELP = "PDF oder Foto der Antwort (Brief, Fax, E-Mail als PDF)."

# Felder der Startvorlage, wie 0816ece7159b sie anlegt (eigene Kopie, eine Migration verlässt sich nie auf den
# aktuellen Code): Schlüssel und Typ in dieser Reihenfolge, sort_order = Position * 10.
ORIGINAL = [
    ("hinweis_pruefung", "hinweis"), ("hinweis_meldung", "hinweis"),
    (_K + "bekannt_seit", "datum_uhrzeit"), (_K + "beschreibung", "text"), (_K + "fotos", "foto"),
    (_K + "unterschrift_meldung", "unterschrift"),
    (_K + "bedenken_gegen", "auswahl"), (_K + "begruendung", "text"), (_K + "moegliche_folgen", "text"),
    (_K + "vorschlag_abhilfe", "text"), (_K + "entscheidung_bis", "datum"), (_K + "unterschrift_buero", "unterschrift"),
    (_K + "eingegangen_am", "datum"), (_K + "entscheidung", "auswahl"), (FIELD_KEY, "foto"), (_K + "notiz", "text"),
    (_K + "unterschrift_entscheidung", "unterschrift"),
]


def layout(field_type: str) -> list[tuple[str, int, str]]:
    """(Schlüssel, sort_order, Typ) der Startvorlage mit diesem Typ für "Antwort als Beleg"."""
    return [(key, index * 10, field_type if key == FIELD_KEY else t) for index, (key, t) in enumerate(ORIGINAL, start=1)]


_META = sa.MetaData()
templates_t = sa.Table("checklist_templates", _META, sa.Column("id", sa.Integer, primary_key=True),
                       sa.Column("label", sa.String), sa.Column("purpose", sa.String))
versions_t = sa.Table("checklist_template_versions", _META, sa.Column("id", sa.Integer, primary_key=True),
                      sa.Column("template_id", sa.Integer), sa.Column("status", sa.String))
fields_t = sa.Table(
    "checklist_template_fields", _META,
    sa.Column("id", sa.Integer, primary_key=True), sa.Column("version_id", sa.Integer), sa.Column("field_key", sa.String),
    sa.Column("sort_order", sa.Integer), sa.Column("field_type", sa.String), sa.Column("help_text", sa.Text),
)


def _unchanged_draft(bind, expected) -> int | None:
    """ID der einzigen Fassung der Startvorlage, wenn sie ein Entwurf ist und ihre Felder genau dem Layout
    entsprechen -- sonst None."""
    template_ids = list(bind.execute(sa.select(templates_t.c.id).where(
        templates_t.c.label == LABEL, templates_t.c.purpose == PURPOSE)).scalars())
    if len(template_ids) != 1:
        return None
    versions = bind.execute(sa.select(versions_t.c.id, versions_t.c.status)
                            .where(versions_t.c.template_id == template_ids[0])).all()
    if len(versions) != 1 or versions[0].status != "entwurf":
        return None
    version_id = versions[0].id
    current = [tuple(row) for row in bind.execute(
        sa.select(fields_t.c.field_key, fields_t.c.sort_order, fields_t.c.field_type)
        .where(fields_t.c.version_id == version_id).order_by(fields_t.c.sort_order, fields_t.c.id)).all()]
    return version_id if current == expected else None


def _switch(bind, old_type: str, new_type: str, old_help: str, new_help: str) -> bool:
    version_id = _unchanged_draft(bind, layout(old_type))
    if version_id is None:
        return False
    field = (fields_t.c.version_id == version_id) & (fields_t.c.field_key == FIELD_KEY)
    bind.execute(fields_t.update().where(field).values(field_type=new_type))
    bind.execute(fields_t.update().where(field, fields_t.c.help_text == old_help).values(help_text=new_help))
    return True


def answer_as_beleg(bind) -> bool:
    """Stellt "Antwort als Beleg" einer unveränderten Startvorlage auf den Typ "beleg" um. True = umgestellt."""
    return _switch(bind, "foto", "beleg", OLD_HELP, NEW_HELP)


def answer_as_photo(bind) -> bool:
    """Gegenstück für downgrade(). True = zurückgestellt."""
    return _switch(bind, "beleg", "foto", NEW_HELP, OLD_HELP)


def upgrade() -> None:
    answer_as_beleg(op.get_bind())


def downgrade() -> None:
    answer_as_photo(op.get_bind())
