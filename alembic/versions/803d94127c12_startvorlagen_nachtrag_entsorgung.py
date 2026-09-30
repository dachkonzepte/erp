"""startvorlagen_nachtrag_entsorgung -- Startvorlagen "Nachtragsmeldung" und
"Entsorgungsnachweis" in je zwei Abschnitte (seit 1.8.15)

Seit 1.8.14 versiegelt eine Unterschrift nur die Felder vor ihr. Beide Startvorlagen hatten eine
Unterschrift am Ende, obwohl ein Teil der Angaben erst später entsteht (Befund 1.8.13). Neu, nach
dem Vorschlag aus 1.8.14 (docs/archiv/modul-checklisten.md):

- Nachtragsmeldung: Abschnitt "Anordnung" (Art, Beschreibung, Menge, Einheit, angeordnet durch)
  → Unterschrift Kunde; Abschnitt "Ausführung" (geschätzter Zeitaufwand, Material, bereits
  ausgeführt, Fotos) → NEUE Unterschrift Monteur. Der Kunde bestätigt nur die Anordnung.
- Entsorgungsnachweis: Abschnitt "Übergabe" (Abfallart, Menge, Einheit, Entsorger, Übergabe)
  → Unterschrift Monteur; Abschnitt "Beleg" (Wiege-/Lieferschein-Nr., Foto des Belegs, Bemerkung)
  → NEUE zweite Unterschrift "Beleg erfasst" (Monteur oder Büro).

Wie bei 05a080705f2c umgestellt NUR, wenn die Vorlage noch genau so ist, wie 349704eab07d sie
angelegt hat: eine einzige Fassung, Entwurf, gleiche Felder in gleicher Reihenfolge. Eine
veröffentlichte oder umsortierte Vorlage gehört dem Betrieb und bleibt unangetastet (dann im
Editor umbauen). Abschnittsnamen und Hilfetexte werden nur gesetzt, wo das Feld noch keinen hat.
Die neuen Unterschriften sind wie alle Startvorlagen-Unterschriften ohne Pflicht (Entscheidung vor
der Veröffentlichung). Daten und Funktionen auf Modulebene, damit
tests/test_v319_checklist_discard_and_completion.py diese Datei direkt laden kann.

downgrade(): nur, solange die Vorlage noch genau der neuen Form entspricht und keine Regel auf die
neue Unterschrift verweist -- entfernt die neue Unterschrift (ein Entwurf, keine Checkliste kann
darauf verweisen), stellt die alte Reihenfolge her und entfernt nur die hier gesetzten
Abschnittsnamen und Hilfetexte.

Revision ID: 803d94127c12
Revises: af9cd6b4e543
Create Date: 2026-09-30 09:01:30.008044

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '803d94127c12'
down_revision = 'af9cd6b4e543'
branch_labels = None
depends_on = None

SPECS = [
    {
        "label": "Nachtragsmeldung",
        "original": ["hinweis_pruefung", "hinweis_keine_zusage", "art", "beschreibung", "menge", "einheit", "zeitaufwand",
                     "material", "angeordnet_durch", "bereits_ausgefuehrt", "fotos", "unterschrift_kunde"],
        "head": ["hinweis_pruefung", "hinweis_keine_zusage"],
        "sections": [
            ("Anordnung", ["art", "beschreibung", "menge", "einheit", "angeordnet_durch", "unterschrift_kunde"]),
            ("Ausführung", ["zeitaufwand", "material", "bereits_ausgefuehrt", "fotos", "unterschrift_monteur"]),
        ],
        "new_field": {"field_key": "unterschrift_monteur", "label": "Unterschrift Monteur", "signer_label": "Monteur"},
        "help": {
            "unterschrift_kunde": "Bei der Anordnung unterschreiben lassen. Die Unterschrift sperrt die Angaben oberhalb; "
                                  "Ausführung und Fotos bleiben bis zur Unterschrift des Monteurs offen.",
            "unterschrift_monteur": "Nach der Ausführung unterschreiben. Die Unterschrift sperrt alle Angaben oberhalb.",
        },
    },
    {
        "label": "Entsorgungsnachweis",
        "original": ["hinweis_pruefung", "abfallart", "menge", "einheit", "entsorger", "uebergabe", "beleg_nr",
                     "beleg_foto", "bemerkung", "unterschrift_monteur"],
        "head": ["hinweis_pruefung"],
        "sections": [
            ("Übergabe", ["abfallart", "menge", "einheit", "entsorger", "uebergabe", "unterschrift_monteur"]),
            ("Beleg", ["beleg_nr", "beleg_foto", "bemerkung", "unterschrift_beleg"]),
        ],
        "new_field": {"field_key": "unterschrift_beleg", "label": "Unterschrift Beleg erfasst",
                      "signer_label": "Monteur/Büro"},
        "help": {
            "unterschrift_monteur": "Bei der Übergabe an den Entsorger unterschreiben. Die Unterschrift sperrt die Angaben "
                                    "oberhalb; Beleg-Nr., Foto des Belegs und Bemerkung bleiben bis zur zweiten "
                                    "Unterschrift offen.",
            "unterschrift_beleg": "Unterschreibt, wer den Beleg der Annahmestelle erfasst hat (Monteur oder Büro). "
                                  "Die Unterschrift sperrt alle Angaben oberhalb.",
        },
    },
]


def new_order(spec: dict) -> list[str]:
    return spec["head"] + [key for _group, keys in spec["sections"] for key in keys]


def layout(keys: list[str]) -> list[tuple[str, int]]:
    """Wie 349704eab07d die Reihenfolge anlegt: sort_order = Position * 10."""
    return [(key, index * 10) for index, key in enumerate(keys, start=1)]


_META = sa.MetaData()
templates_t = sa.Table("checklist_templates", _META, sa.Column("id", sa.Integer, primary_key=True),
                       sa.Column("label", sa.String))
versions_t = sa.Table("checklist_template_versions", _META, sa.Column("id", sa.Integer, primary_key=True),
                      sa.Column("template_id", sa.Integer), sa.Column("status", sa.String))
fields_t = sa.Table(
    "checklist_template_fields", _META,
    sa.Column("id", sa.Integer, primary_key=True), sa.Column("version_id", sa.Integer), sa.Column("field_key", sa.String),
    sa.Column("sort_order", sa.Integer), sa.Column("group_name", sa.String), sa.Column("field_type", sa.String),
    sa.Column("label", sa.String), sa.Column("help_text", sa.Text), sa.Column("required", sa.Boolean),
    sa.Column("allow_na", sa.Boolean), sa.Column("multiline", sa.Boolean), sa.Column("multiple", sa.Boolean),
    sa.Column("unit", sa.String), sa.Column("min_value", sa.Numeric(18, 4)), sa.Column("max_value", sa.Numeric(18, 4)),
    sa.Column("decimals", sa.Integer), sa.Column("min_count", sa.Integer), sa.Column("max_count", sa.Integer),
    sa.Column("prefill_now", sa.Boolean), sa.Column("signer_label", sa.String), sa.Column("is_system", sa.Boolean),
)
options_t = sa.Table("checklist_template_field_options", _META, sa.Column("id", sa.Integer, primary_key=True),
                     sa.Column("field_id", sa.Integer))
rules_t = sa.Table("checklist_template_rules", _META, sa.Column("id", sa.Integer, primary_key=True),
                   sa.Column("version_id", sa.Integer), sa.Column("field_key", sa.String))


def _draft_version_with_layout(bind, label: str, expected) -> int | None:
    """ID der einzigen Fassung der Startvorlage, wenn sie ein Entwurf ist und ihre Felder genau
    dem Layout entsprechen -- sonst None (Muster 05a080705f2c)."""
    template_ids = list(bind.execute(sa.select(templates_t.c.id).where(templates_t.c.label == label)).scalars())
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
    return version_id if current == expected else None


def split_starter_templates(bind) -> list[str]:
    """Stellt jede unveränderte Startvorlage auf zwei Abschnitte um. Liefert die umgestellten
    Bezeichnungen."""
    done = []
    for spec in SPECS:
        version_id = _draft_version_with_layout(bind, spec["label"], layout(spec["original"]))
        if version_id is None:
            continue
        in_version = fields_t.c.version_id == version_id
        positions = dict(layout(new_order(spec)))
        new = spec["new_field"]
        bind.execute(fields_t.insert().values(  # Einzelunterschrift: max_count 1 wie _normalize_field()
            version_id=version_id, field_key=new["field_key"], sort_order=positions[new["field_key"]], group_name=None,
            field_type="unterschrift", label=new["label"], help_text=None, required=False, allow_na=False,
            multiline=False, multiple=False, unit=None, min_value=None, max_value=None, decimals=None, min_count=None,
            max_count=1, prefill_now=False, signer_label=new["signer_label"], is_system=False,
        ))
        for key, sort_order in positions.items():
            bind.execute(fields_t.update().where(in_version, fields_t.c.field_key == key).values(sort_order=sort_order))
        for group, keys in spec["sections"]:
            bind.execute(fields_t.update().where(in_version, fields_t.c.field_key.in_(keys), fields_t.c.group_name.is_(None))
                         .values(group_name=group))
        for key, text in spec["help"].items():
            bind.execute(fields_t.update().where(in_version, fields_t.c.field_key == key, fields_t.c.help_text.is_(None))
                         .values(help_text=text))
        done.append(spec["label"])
    return done


def join_starter_templates(bind) -> list[str]:
    """Gegenstück für downgrade(). Liefert die zurückgestellten Bezeichnungen."""
    done = []
    for spec in SPECS:
        version_id = _draft_version_with_layout(bind, spec["label"], layout(new_order(spec)))
        if version_id is None:
            continue
        in_version = fields_t.c.version_id == version_id
        new_key = spec["new_field"]["field_key"]
        if bind.execute(sa.select(rules_t.c.id).where(rules_t.c.version_id == version_id,
                                                      rules_t.c.field_key == new_key).limit(1)).first() is not None:
            continue  # das Büro hat eine Regel an die neue Unterschrift gehängt
        field_ids = list(bind.execute(sa.select(fields_t.c.id).where(in_version, fields_t.c.field_key == new_key)).scalars())
        bind.execute(options_t.delete().where(options_t.c.field_id.in_(field_ids)))
        bind.execute(fields_t.delete().where(fields_t.c.id.in_(field_ids)))
        for key, sort_order in layout(spec["original"]):
            bind.execute(fields_t.update().where(in_version, fields_t.c.field_key == key).values(sort_order=sort_order))
        bind.execute(fields_t.update().where(in_version, fields_t.c.group_name.in_([g for g, _ in spec["sections"]]))
                     .values(group_name=None))
        for key, text in spec["help"].items():
            bind.execute(fields_t.update().where(in_version, fields_t.c.field_key == key, fields_t.c.help_text == text)
                         .values(help_text=None))
        done.append(spec["label"])
    return done


def upgrade() -> None:
    split_starter_templates(op.get_bind())


def downgrade() -> None:
    join_starter_templates(op.get_bind())
