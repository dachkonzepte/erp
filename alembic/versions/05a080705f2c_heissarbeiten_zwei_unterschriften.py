"""heissarbeiten_zwei_unterschriften -- Startvorlage "Heißarbeiten mit Brandwache" in zwei
Abschnitte (seit 1.8.14)

Seit 1.8.14 versiegelt eine Unterschrift nur die Felder, die in der Vorlage vor ihr stehen. Die
Startvorlage hatte beide Unterschriften am Ende -- wer den Erlaubnisschein wie üblich vor
Arbeitsbeginn unterschrieb, sperrte damit auch Ende und Nachkontrolle (Befund 1.8.13). Neu:

- Abschnitt "Freigabe vor Arbeitsbeginn": Freigabe … Beginn, danach Unterschrift Ausführender.
- Abschnitt "Nachkontrolle": Ende, Nachkontrolle bis, Nachkontrolle ohne Befund, Fotos, danach
  Unterschrift Brandwache.

Umgestellt wird NUR eine Startvorlage, die noch genau so ist, wie 349704eab07d sie angelegt hat:
eine einzige Fassung, Entwurf, gleiche Felder in gleicher Reihenfolge. Eine veröffentlichte oder
umsortierte Vorlage gehört dem Betrieb und bleibt unangetastet (dann im Editor umsortieren).
Abschnittsnamen und Hilfetexte der Unterschriften werden nur gesetzt, wo das Feld noch keinen
hat. Die Daten und die beiden Funktionen stehen auf Modulebene, damit
tests/test_v318_checklist_signature_sections.py diese Datei direkt laden kann.

downgrade(): stellt die alte Reihenfolge nur zurück, solange die Vorlage noch genau der neuen
entspricht, und entfernt nur die hier gesetzten Abschnittsnamen und Hilfetexte.

Revision ID: 05a080705f2c
Revises: 8f73789cdd66
Create Date: 2026-09-30 14:12:40.118904

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '05a080705f2c'
down_revision = '8f73789cdd66'
branch_labels = None
depends_on = None

TEMPLATE_LABEL = "Heißarbeiten mit Brandwache"
FIRST_SIGNATURE = "unterschrift_ausfuehrender"
ORIGINAL_ORDER = [
    "hinweis_pruefung", "freigabe_auftraggeber", "arbeitsbereich", "geraete_ok", "brennbares", "loeschmittel",
    "brandwache_name", "beginn", "ende", "nachkontrolle_bis", "nachkontrolle_ohne_befund", "fotos",
    "unterschrift_ausfuehrender", "unterschrift_brandwache",
]
ORIGINAL_LAYOUT = [(key, index * 10) for index, key in enumerate(ORIGINAL_ORDER, start=1)]
NEW_SORT_ORDER = 85  # zwischen "beginn" (80) und "ende" (90)
NEW_LAYOUT = sorted([(k, NEW_SORT_ORDER if k == FIRST_SIGNATURE else s) for k, s in ORIGINAL_LAYOUT], key=lambda x: x[1])
GROUP_FREIGABE = "Freigabe vor Arbeitsbeginn"
GROUP_NACHKONTROLLE = "Nachkontrolle"
SIGNATURE_HELP = {
    "unterschrift_ausfuehrender": "Vor Arbeitsbeginn unterschreiben. Die Unterschrift sperrt die Angaben oberhalb; "
                                  "Ende und Nachkontrolle bleiben bis zur Unterschrift der Brandwache offen.",
    "unterschrift_brandwache": "Nach der Nachkontrolle unterschreiben. Die Unterschrift sperrt alle Angaben oberhalb.",
}

_META = sa.MetaData()
templates_t = sa.Table("checklist_templates", _META, sa.Column("id", sa.Integer, primary_key=True),
                       sa.Column("label", sa.String))
versions_t = sa.Table("checklist_template_versions", _META, sa.Column("id", sa.Integer, primary_key=True),
                      sa.Column("template_id", sa.Integer), sa.Column("status", sa.String))
fields_t = sa.Table(
    "checklist_template_fields", _META,
    sa.Column("id", sa.Integer, primary_key=True), sa.Column("version_id", sa.Integer), sa.Column("field_key", sa.String),
    sa.Column("sort_order", sa.Integer), sa.Column("group_name", sa.String), sa.Column("help_text", sa.Text),
)


def _draft_version_with_layout(bind, layout) -> int | None:
    """ID der einzigen Fassung der Startvorlage, wenn sie ein Entwurf ist und ihre Felder genau
    dem Layout entsprechen -- sonst None."""
    template_ids = list(bind.execute(sa.select(templates_t.c.id).where(templates_t.c.label == TEMPLATE_LABEL)).scalars())
    if len(template_ids) != 1:
        return None
    versions = bind.execute(sa.select(versions_t.c.id, versions_t.c.status)
                            .where(versions_t.c.template_id == template_ids[0])).all()
    if len(versions) != 1 or versions[0].status != "entwurf":
        return None
    version_id = versions[0].id
    current = [tuple(row) for row in bind.execute(
        sa.select(fields_t.c.field_key, fields_t.c.sort_order).where(fields_t.c.version_id == version_id)
        .order_by(fields_t.c.sort_order, fields_t.c.id)).all()]
    return version_id if current == layout else None


def split_hot_work_template(bind) -> bool:
    """Stellt die unveränderte Startvorlage auf zwei Abschnitte um. True, wenn umgestellt."""
    version_id = _draft_version_with_layout(bind, ORIGINAL_LAYOUT)
    if version_id is None:
        return False
    in_version = fields_t.c.version_id == version_id
    bind.execute(fields_t.update().where(in_version, fields_t.c.field_key == FIRST_SIGNATURE)
                 .values(sort_order=NEW_SORT_ORDER))
    bind.execute(fields_t.update().where(in_version, fields_t.c.group_name.is_(None),
                                         fields_t.c.sort_order.between(20, NEW_SORT_ORDER))
                 .values(group_name=GROUP_FREIGABE))
    bind.execute(fields_t.update().where(in_version, fields_t.c.group_name.is_(None), fields_t.c.sort_order > NEW_SORT_ORDER)
                 .values(group_name=GROUP_NACHKONTROLLE))
    for key, text in SIGNATURE_HELP.items():
        bind.execute(fields_t.update().where(in_version, fields_t.c.field_key == key, fields_t.c.help_text.is_(None))
                     .values(help_text=text))
    return True


def join_hot_work_template(bind) -> bool:
    """Gegenstück für downgrade(): nur, solange die Vorlage noch genau der neuen entspricht."""
    version_id = _draft_version_with_layout(bind, NEW_LAYOUT)
    if version_id is None:
        return False
    in_version = fields_t.c.version_id == version_id
    bind.execute(fields_t.update().where(in_version, fields_t.c.field_key == FIRST_SIGNATURE)
                 .values(sort_order=dict(ORIGINAL_LAYOUT)[FIRST_SIGNATURE]))
    bind.execute(fields_t.update().where(in_version, fields_t.c.group_name.in_((GROUP_FREIGABE, GROUP_NACHKONTROLLE)))
                 .values(group_name=None))
    for key, text in SIGNATURE_HELP.items():
        bind.execute(fields_t.update().where(in_version, fields_t.c.field_key == key, fields_t.c.help_text == text)
                     .values(help_text=None))
    return True


def upgrade() -> None:
    split_hot_work_template(op.get_bind())


def downgrade() -> None:
    join_hot_work_template(op.get_bind())
