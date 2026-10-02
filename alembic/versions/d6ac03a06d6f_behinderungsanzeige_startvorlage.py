"""behinderungsanzeige_startvorlage -- Startvorlage "Behinderungsanzeige", Link-Zweck an Regeln,
Tagesbericht-Regel "Behinderung = ja" (seit 1.8.38, Stufe 2b, Runde 2b-3 Teil 1)

- Spalte checklist_template_rules.link_purpose (nullable): leer = die Aufgabe einer Regel verlinkt
  auf die Checkliste; sonst ein Zweck -- die Aufgabe verlinkt aufs Anlegen einer Checkliste dieses
  Zwecks am selben Auftrag (app/checklist_rules.py).
- Startvorlage "Behinderungsanzeige" als ENTWURF (Zweck behinderungsanzeige, nur Auftrag) mit den
  Systemfeldern aus app/checklist_purposes.py in drei Abschnitten: Meldung → Unterschrift des
  Meldenden, Anzeige (Büro) → Unterschrift Büro, Wegfall → Unterschrift. Daten-Migration wie
  349704eab07d, kein Self-Seeding; eine gleichnamige Vorlage bleibt unangetastet. Die
  Systemfelder stehen hier als eigene Kopie (eine Migration verlässt sich nie auf den aktuellen
  Code); tests/test_v341_behinderungsanzeige.py prüft sie gegen die Registry über die echte
  Veröffentlichungsprüfung.
- Startvorlage "Tagesbericht": die Regel "Behinderung aufgetreten = ja" legt statt der bisherigen
  Aufgabe eine mit Link zum Anlegen der Behinderungsanzeige an. Umgestellt NUR, wenn die Vorlage
  noch eine einzige Fassung im Entwurf hat und die Regel genau so ist, wie 349704eab07d sie
  angelegt hat -- eine veröffentlichte Fassung ist eingefroren (dann im Editor einen neuen Entwurf
  anlegen und an der Regel "Aufgabe verlinkt auf" wählen).

downgrade(): stellt die Tagesbericht-Regel zurück, wenn sie noch genau so ist wie hier gesetzt;
bricht ab, wenn danach noch irgendeine Regel einen Link-Zweck trägt (er ginge mit der Spalte
verloren); entfernt die Startvorlage nur, solange sie nie veröffentlicht und nie verwendet wurde.

Revision ID: d6ac03a06d6f
Revises: d99494185ce7
Create Date: 2026-10-02 09:25:07.827486

"""
from datetime import datetime

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd6ac03a06d6f'
down_revision = 'd99494185ce7'
branch_labels = None
depends_on = None

PURPOSE = "behinderungsanzeige"
LABEL = "Behinderungsanzeige"
DESCRIPTION = ("Meldung einer Behinderung von der Baustelle, Anzeige an den Auftraggeber durch das Büro, Wegfall der "
               "Behinderung. Startvorlage (Entwurf) – vor Veröffentlichung Beschriftungen, Hilfetexte und Abschnitte "
               "prüfen.")
_B = PURPOSE + "."


def _f(key, field_type, label, group=None, **extra) -> dict:
    return {"key": key, "type": field_type, "label": label, "group": group, **extra}


# Reihenfolge = sort_order. "system" = Systemfeld des Zwecks (feste Eigenschaften wie in der Registry).
FIELDS = [
    _f("hinweis_pruefung", "hinweis", "Vor Veröffentlichung prüfen: Beschriftungen, Hilfetexte und Abschnitte.",
       help_text="Diesen Hinweis nach der Prüfung löschen, dann veröffentlichen."),
    _f("hinweis_meldung", "hinweis", "Behinderung sofort melden", "Meldung",
       help_text="Was hindert die Arbeit, und seit wann? Fotos helfen. Das Büro zeigt die Behinderung dem "
                 "Auftraggeber schriftlich an."),
    _f(_B + "bekannt_seit", "datum_uhrzeit", "Bekannt seit", "Meldung", system=True, required=True,
       help_text="Wann die Behinderung bekannt wurde – nicht, wann sie gemeldet wird."),
    _f(_B + "beschreibung", "text", "Beschreibung", "Meldung", system=True, required=True, multiline=True),
    _f(_B + "fotos", "foto", "Fotos", "Meldung", system=True, max_count=10),
    _f(_B + "unterschrift_meldung", "unterschrift", "Unterschrift des Meldenden", "Meldung", system=True,
       required=True, signer_label="Meldender",
       help_text="Unterschreibt, wer die Behinderung meldet. Die Unterschrift sperrt die Meldung; das Büro bekommt "
                 "danach die Aufgabe „Behinderungsanzeige versenden“."),
    _f(_B + "ursache", "auswahl", "Ursache", "Anzeige", system=True, required=True, options=[
        ("vorleistung", "fehlende Vorleistung eines anderen Gewerks"),
        ("plaene_freigaben", "fehlende Pläne oder Freigaben"),
        ("zugang_geruest", "Zugang oder Gerüst"),
        ("material_ag", "vom Auftraggeber zu lieferndes Material"),
        ("witterung", "außergewöhnliche Witterung"),
        ("sonstiges", "Sonstiges"),
    ]),
    _f(_B + "ursache_beschreibung", "text", "Beschreibung der Ursache", "Anzeige", system=True, required=True,
       multiline=True),
    _f(_B + "betroffene_leistungen", "text", "Betroffene Leistungen", "Anzeige", system=True, required=True,
       multiline=True),
    _f(_B + "beginn", "datum", "Beginn der Behinderung", "Anzeige", system=True, required=True),
    _f(_B + "dauer", "text", "Voraussichtliche Dauer", "Anzeige", system=True),
    _f(_B + "unterschrift_buero", "unterschrift", "Unterschrift Büro", "Anzeige", system=True, required=True,
       signer_label="Büro",
       help_text="Unterschreibt das Büro, bevor die Anzeige an den Auftraggeber geht. Sperrt Meldung und Anzeige."),
    _f(_B + "beendet_am", "datum", "Behinderung beendet am", "Wegfall", system=True, required=True),
    _f(_B + "wieder_aufgenommen_am", "datum", "Arbeit wieder aufgenommen am", "Wegfall", system=True, required=True),
    _f(_B + "unterschrift_wegfall", "unterschrift", "Unterschrift", "Wegfall", system=True, required=True,
       signer_label="Monteur/Büro",
       help_text="Unterschreibt, wer den Wegfall der Behinderung feststellt (Monteur oder Büro)."),
]

# Tagesbericht-Regel: Stand aus 349704eab07d → neuer Stand.
DAILY_REPORT = "Tagesbericht"
RULE_BEFORE = {"field_key": "behinderung", "operator": "ist_ja", "task_title": "Behinderung gemeldet: {kontext}",
               "task_description": "Laut Tagesbericht von {ersteller} ist eine Behinderung aufgetreten. "
                                   "Behinderungsanzeige prüfen.",
               "link_purpose": None}
RULE_AFTER = {"field_key": "behinderung", "operator": "ist_ja", "task_title": "Behinderungsanzeige anlegen: {kontext}",
              "task_description": "Laut Tagesbericht von {ersteller} ist eine Behinderung aufgetreten. Über den Link "
                                  "die Behinderungsanzeige am Auftrag anlegen.",
              "link_purpose": PURPOSE}

_META = sa.MetaData()
templates_t = sa.Table(
    "checklist_templates", _META,
    sa.Column("id", sa.Integer, primary_key=True), sa.Column("label", sa.String), sa.Column("description", sa.Text),
    sa.Column("purpose", sa.String), sa.Column("context_order", sa.Boolean), sa.Column("context_property", sa.Boolean),
    sa.Column("context_asset", sa.Boolean), sa.Column("context_company", sa.Boolean),
    sa.Column("field_readable", sa.Boolean), sa.Column("sort_order", sa.Integer), sa.Column("archived", sa.Boolean),
    sa.Column("created_at", sa.DateTime), sa.Column("updated_at", sa.DateTime),
)
versions_t = sa.Table(
    "checklist_template_versions", _META,
    sa.Column("id", sa.Integer, primary_key=True), sa.Column("template_id", sa.Integer), sa.Column("version_no", sa.Integer),
    sa.Column("status", sa.String), sa.Column("purpose", sa.String), sa.Column("published_at", sa.DateTime),
    sa.Column("published_by_user_id", sa.Integer), sa.Column("created_at", sa.DateTime),
)
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
options_t = sa.Table(
    "checklist_template_field_options", _META,
    sa.Column("id", sa.Integer, primary_key=True), sa.Column("field_id", sa.Integer), sa.Column("option_key", sa.String),
    sa.Column("label", sa.String), sa.Column("sort_order", sa.Integer),
)
rules_t = sa.Table(
    "checklist_template_rules", _META,
    sa.Column("id", sa.Integer, primary_key=True), sa.Column("version_id", sa.Integer), sa.Column("field_key", sa.String),
    sa.Column("operator", sa.String), sa.Column("task_title", sa.String), sa.Column("task_description", sa.Text),
    sa.Column("link_purpose", sa.String),
)
checklists_t = sa.Table("checklists", _META, sa.Column("id", sa.Integer, primary_key=True),
                        sa.Column("template_id", sa.Integer))


def insert_obstruction_template(bind, now: datetime | None = None) -> bool:
    """Legt die Startvorlage als Entwurf an, sofern es keine Vorlage dieses Namens gibt. True =
    angelegt."""
    now = now or datetime.utcnow()
    if bind.execute(sa.select(templates_t.c.id).where(templates_t.c.label == LABEL)).first() is not None:
        return False
    sort_order = (bind.execute(sa.select(sa.func.max(templates_t.c.sort_order))).scalar() or 0) + 10
    template_id = bind.execute(templates_t.insert().values(
        label=LABEL, description=DESCRIPTION, purpose=PURPOSE, context_order=True, context_property=False,
        context_asset=False, context_company=False, field_readable=False, sort_order=sort_order, archived=False,
        created_at=now, updated_at=now,
    )).inserted_primary_key[0]
    version_id = bind.execute(versions_t.insert().values(
        template_id=template_id, version_no=1, status="entwurf", purpose=PURPOSE, published_at=None,
        published_by_user_id=None, created_at=now,
    )).inserted_primary_key[0]
    for index, field in enumerate(FIELDS, start=1):
        field_type = field["type"]
        field_id = bind.execute(fields_t.insert().values(
            version_id=version_id, field_key=field["key"], sort_order=index * 10, group_name=field["group"],
            field_type=field_type, label=field["label"], help_text=field.get("help_text"),
            required=bool(field.get("required")), allow_na=False, multiline=bool(field.get("multiline")),
            multiple=False, unit=None, min_value=None, max_value=None, decimals=None, min_count=None,
            max_count=1 if field_type == "unterschrift" else field.get("max_count"),  # Einzelunterschrift
            prefill_now=False, signer_label=field.get("signer_label"), is_system=bool(field.get("system")),
        )).inserted_primary_key[0]
        for option_index, (option_key, option_label) in enumerate(field.get("options", []), start=1):
            bind.execute(options_t.insert().values(field_id=field_id, option_key=option_key, label=option_label,
                                                   sort_order=option_index * 10))
    return True


def remove_obstruction_template(bind) -> bool:
    """Entfernt die Startvorlage, solange sie nie veröffentlicht und nie verwendet wurde. True =
    entfernt."""
    row = bind.execute(sa.select(templates_t.c.id).where(templates_t.c.label == LABEL,
                                                         templates_t.c.purpose == PURPOSE)).first()
    if row is None:
        return False
    template_id = row.id
    statuses = set(bind.execute(sa.select(versions_t.c.status).where(versions_t.c.template_id == template_id)).scalars())
    used = bind.execute(sa.select(checklists_t.c.id).where(checklists_t.c.template_id == template_id).limit(1)).first()
    if statuses != {"entwurf"} or used is not None:
        return False
    version_ids = list(bind.execute(sa.select(versions_t.c.id).where(versions_t.c.template_id == template_id)).scalars())
    field_ids = list(bind.execute(sa.select(fields_t.c.id).where(fields_t.c.version_id.in_(version_ids))).scalars())
    if field_ids:
        bind.execute(options_t.delete().where(options_t.c.field_id.in_(field_ids)))
    bind.execute(rules_t.delete().where(rules_t.c.version_id.in_(version_ids)))
    bind.execute(fields_t.delete().where(fields_t.c.version_id.in_(version_ids)))
    bind.execute(versions_t.delete().where(versions_t.c.template_id == template_id))
    bind.execute(templates_t.delete().where(templates_t.c.id == template_id))
    return True


def _daily_report_rule_id(bind, expected: dict) -> int | None:
    """ID der Behinderungs-Regel des Tagesberichts, wenn die Vorlage eine einzige Fassung im Entwurf
    hat und die Regel genau `expected` entspricht -- sonst None."""
    template_ids = list(bind.execute(sa.select(templates_t.c.id).where(templates_t.c.label == DAILY_REPORT)).scalars())
    if len(template_ids) != 1:
        return None
    versions = bind.execute(sa.select(versions_t.c.id, versions_t.c.status)
                            .where(versions_t.c.template_id == template_ids[0])).all()
    if len(versions) != 1 or versions[0].status != "entwurf":
        return None
    rows = bind.execute(sa.select(rules_t).where(rules_t.c.version_id == versions[0].id,
                                                 rules_t.c.field_key == expected["field_key"],
                                                 rules_t.c.operator == expected["operator"])).all()
    matching = [r.id for r in rows if all(getattr(r, k) == v for k, v in expected.items())]
    return matching[0] if len(matching) == 1 else None


def link_daily_report_rule(bind) -> bool:
    rule_id = _daily_report_rule_id(bind, RULE_BEFORE)
    if rule_id is None:
        return False
    bind.execute(rules_t.update().where(rules_t.c.id == rule_id).values(
        task_title=RULE_AFTER["task_title"], task_description=RULE_AFTER["task_description"],
        link_purpose=RULE_AFTER["link_purpose"]))
    return True


def unlink_daily_report_rule(bind) -> bool:
    rule_id = _daily_report_rule_id(bind, RULE_AFTER)
    if rule_id is None:
        return False
    bind.execute(rules_t.update().where(rules_t.c.id == rule_id).values(
        task_title=RULE_BEFORE["task_title"], task_description=RULE_BEFORE["task_description"], link_purpose=None))
    return True


def upgrade() -> None:
    with op.batch_alter_table('checklist_template_rules', schema=None) as batch_op:
        batch_op.add_column(sa.Column('link_purpose', sa.String(length=40), nullable=True))
    bind = op.get_bind()
    insert_obstruction_template(bind)
    link_daily_report_rule(bind)


def downgrade() -> None:
    bind = op.get_bind()
    unlink_daily_report_rule(bind)
    left = bind.execute(sa.select(sa.func.count()).select_from(rules_t)
                        .where(rules_t.c.link_purpose.is_not(None))).scalar()
    if left:
        raise RuntimeError(
            f"{left} Regel(n) tragen einen Link-Zweck (Aufgabe verlinkt aufs Anlegen einer Checkliste) -- er ginge mit "
            f"der Spalte link_purpose verloren. Downgrade abgebrochen.")
    remove_obstruction_template(bind)
    with op.batch_alter_table('checklist_template_rules', schema=None) as batch_op:
        batch_op.drop_column('link_purpose')
