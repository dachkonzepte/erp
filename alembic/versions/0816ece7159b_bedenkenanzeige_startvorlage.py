"""bedenkenanzeige_startvorlage -- Startvorlage "Bedenkenanzeige" (seit 1.8.43, Stufe 2b, Runde 2b-4)

- Startvorlage "Bedenkenanzeige" als ENTWURF (Zweck bedenkenanzeige, nur Auftrag) mit den Systemfeldern aus
  app/checklist_purposes.py in drei Abschnitten: Meldung → Unterschrift des Meldenden, Anzeige (Büro) →
  Unterschrift Büro, Entscheidung des Auftraggebers (Büro) → Unterschrift. Daten-Migration wie d6ac03a06d6f
  (Behinderungsanzeige), kein Self-Seeding; eine gleichnamige Vorlage bleibt unangetastet. Die Systemfelder
  stehen hier als eigene Kopie (eine Migration verlässt sich nie auf den aktuellen Code);
  tests/test_v346_bedenkenanzeige.py prüft sie gegen die Registry über die echte Veröffentlichungsprüfung.
- Kein Schema: die Bedenkenanzeige nutzt die Tabellen der Checklisten und Folgen.

downgrade(): entfernt die Startvorlage nur, solange sie nie veröffentlicht und nie verwendet wurde.

Revision ID: 0816ece7159b
Revises: 0181f8f79a6b
Create Date: 2026-10-02 16:13:35.669113

"""
from datetime import datetime

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0816ece7159b'
down_revision = '0181f8f79a6b'
branch_labels = None
depends_on = None

PURPOSE = "bedenkenanzeige"
LABEL = "Bedenkenanzeige"
DESCRIPTION = ("Bedenken von der Baustelle melden, Anzeige an den Auftraggeber durch das Büro, Entscheidung des "
               "Auftraggebers festhalten. Startvorlage (Entwurf) – vor Veröffentlichung Beschriftungen, Hilfetexte "
               "und Abschnitte prüfen.")
_K = PURPOSE + "."


def _f(key, field_type, label, group=None, **extra) -> dict:
    return {"key": key, "type": field_type, "label": label, "group": group, **extra}


# Reihenfolge = sort_order. "system" = Systemfeld des Zwecks (feste Eigenschaften wie in der Registry).
FIELDS = [
    _f("hinweis_pruefung", "hinweis", "Vor Veröffentlichung prüfen: Beschriftungen, Hilfetexte und Abschnitte.",
       help_text="Diesen Hinweis nach der Prüfung löschen, dann veröffentlichen."),
    _f("hinweis_meldung", "hinweis", "Bedenken sofort melden", "Meldung",
       help_text="Was spricht gegen die vorgesehene Ausführung, das gelieferte Material oder die Vorleistung? Fotos "
                 "helfen. Bis zur Entscheidung des Auftraggebers die betroffene Leistung nicht ausführen – im "
                 "Zweifel mit dem Büro klären."),
    _f(_K + "bekannt_seit", "datum_uhrzeit", "Bekannt seit", "Meldung", system=True, required=True,
       help_text="Wann die Bedenken aufkamen – nicht, wann sie gemeldet werden."),
    _f(_K + "beschreibung", "text", "Beschreibung", "Meldung", system=True, required=True, multiline=True),
    _f(_K + "fotos", "foto", "Fotos", "Meldung", system=True, max_count=10),
    _f(_K + "unterschrift_meldung", "unterschrift", "Unterschrift des Meldenden", "Meldung", system=True,
       required=True, signer_label="Meldender",
       help_text="Unterschreibt, wer die Bedenken meldet. Die Unterschrift sperrt die Meldung; das Büro bekommt "
                 "danach die Aufgabe „Bedenkenanzeige versenden“."),
    _f(_K + "bedenken_gegen", "auswahl", "Bedenken gegen", "Anzeige", system=True, required=True, multiple=True,
       options=[
           ("art_der_ausfuehrung", "vorgesehene Art der Ausführung"),
           ("stoffe_bauteile", "vom Auftraggeber gelieferte Stoffe oder Bauteile"),
           ("leistungen_anderer", "Leistungen anderer Unternehmer"),
       ]),
    _f(_K + "begruendung", "text", "Begründung", "Anzeige", system=True, required=True, multiline=True),
    _f(_K + "moegliche_folgen", "text", "Mögliche Folgen", "Anzeige", system=True, required=True, multiline=True),
    _f(_K + "vorschlag_abhilfe", "text", "Vorschlag zur Abhilfe", "Anzeige", system=True, multiline=True),
    _f(_K + "entscheidung_bis", "datum", "Entscheidung erbeten bis", "Anzeige", system=True, required=True),
    _f(_K + "unterschrift_buero", "unterschrift", "Unterschrift Büro", "Anzeige", system=True, required=True,
       signer_label="Büro",
       help_text="Unterschreibt das Büro, bevor die Anzeige an den Auftraggeber geht. Sperrt Meldung und Anzeige."),
    _f(_K + "eingegangen_am", "datum", "Eingegangen am", "Entscheidung", system=True,
       help_text="Wann die Antwort des Auftraggebers einging – leer bei „keine Antwort“."),
    _f(_K + "entscheidung", "auswahl", "Entscheidung", "Entscheidung", system=True, required=True, options=[
        ("bedenken_gefolgt", "Bedenken gefolgt"),
        ("trotz_bedenken", "Ausführung trotz Bedenken angeordnet"),
        ("keine_antwort", "keine Antwort"),
        ("sonstiges", "Sonstiges"),
    ]),
    _f(_K + "antwort_beleg", "foto", "Antwort als Beleg", "Entscheidung", system=True, max_count=10,
       help_text="Foto oder Scan der Antwort (Brief, Fax, ausgedruckte E-Mail)."),
    _f(_K + "notiz", "text", "Notiz", "Entscheidung", system=True, multiline=True),
    _f(_K + "unterschrift_entscheidung", "unterschrift", "Unterschrift", "Entscheidung", system=True, required=True,
       signer_label="Büro",
       help_text="Unterschreibt das Büro, wenn die Entscheidung feststeht. Danach verschwindet der Hinweis „Offene "
                 "Bedenken“ am Auftrag und in /mobil."),
]

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
rules_t = sa.Table("checklist_template_rules", _META, sa.Column("id", sa.Integer, primary_key=True),
                   sa.Column("version_id", sa.Integer))
checklists_t = sa.Table("checklists", _META, sa.Column("id", sa.Integer, primary_key=True),
                        sa.Column("template_id", sa.Integer))


def insert_concern_template(bind, now: datetime | None = None) -> bool:
    """Legt die Startvorlage als Entwurf an, sofern es keine Vorlage dieses Namens gibt. True = angelegt."""
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
            multiple=bool(field.get("multiple")), unit=None, min_value=None, max_value=None, decimals=None,
            min_count=None, max_count=1 if field_type == "unterschrift" else field.get("max_count"),  # Einzelunterschrift
            prefill_now=False, signer_label=field.get("signer_label"), is_system=bool(field.get("system")),
        )).inserted_primary_key[0]
        for option_index, (option_key, option_label) in enumerate(field.get("options", []), start=1):
            bind.execute(options_t.insert().values(field_id=field_id, option_key=option_key, label=option_label,
                                                   sort_order=option_index * 10))
    return True


def remove_concern_template(bind) -> bool:
    """Entfernt die Startvorlage, solange sie nie veröffentlicht und nie verwendet wurde. True = entfernt."""
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


def upgrade() -> None:
    insert_concern_template(op.get_bind())


def downgrade() -> None:
    remove_concern_template(op.get_bind())
