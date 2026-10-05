"""abnahmeprotokoll_startvorlage -- Startvorlage "Abnahmeprotokoll" (seit 1.8.61, Stufe 2c-2d, Punkt 2)

- Startvorlage "Abnahmeprotokoll" als ENTWURF (Zweck abnahme, nur Auftrag, field_readable aus -- der Zweck ist nur fürs
  Büro) mit den Systemfeldern aus app/checklist_purposes.py in drei Abschnitten: Befund (Teilnehmer, Umfang, abgenommener
  Teil, Dachflächen, Mängel, Einwendungen des Auftragnehmers), Erklärungen des Auftraggebers (Ergebnis, Vorbehalt wegen
  bekannter Mängel, Vorbehalt der Vertragsstrafe, Unterschrift Auftraggeber -- laut Auftrag oder Beteiligter), Schluss
  (Unterschrift Auftragnehmer -- angemeldetes Konto). Daten-Migration wie 0816ece7159b (Bedenkenanzeige), kein
  Self-Seeding; eine gleichnamige Vorlage bleibt unangetastet. Die Systemfelder stehen hier als eigene Kopie (eine
  Migration verlässt sich nie auf den aktuellen Code); tests/test_v363_zweck_abnahme.py prüft sie gegen die Registry über
  die echte Veröffentlichungsprüfung.
- Kein Schema: neuer Feldtyp "dachflaechen" und Unterzeichner "ag_oder_beteiligter" sind Werte in vorhandenen Spalten
  (field_type String 30, signer_mode String 20 -- deshalb der kurze Schlüssel).

downgrade(): entfernt die Startvorlage nur, solange sie nie veröffentlicht und nie verwendet wurde.

Revision ID: 65c57e30d0f3
Revises: 82e4382b0c9f
Create Date: 2026-10-05

"""
from datetime import datetime

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '65c57e30d0f3'
down_revision = '82e4382b0c9f'
branch_labels = None
depends_on = None


PURPOSE = "abnahme"
LABEL = "Abnahmeprotokoll"
DESCRIPTION = ("Förmliche Abnahme mit dem Auftraggeber: Befund mit Mängeln, Erklärungen und Unterschrift des Auftraggebers, "
               "Unterschrift des Auftragnehmers. Nur Büro. Startvorlage (Entwurf) – vor Veröffentlichung Beschriftungen, "
               "Hilfetexte und Abschnitte prüfen.")
_A = PURPOSE + "."
BEFUND, ERKLAERUNG, SCHLUSS = "Befund", "Erklärungen des Auftraggebers", "Schluss"


def _f(key, field_type, label, group=None, **extra) -> dict:
    return {"key": key, "type": field_type, "label": label, "group": group, **extra}


# Reihenfolge = sort_order. "system" = Systemfeld des Zwecks (feste Eigenschaften wie in der Registry).
FIELDS = [
    _f("hinweis_pruefung", "hinweis", "Vor Veröffentlichung prüfen: Beschriftungen, Hilfetexte und Abschnitte.",
       help_text="Diesen Hinweis nach der Prüfung löschen, dann veröffentlichen."),
    _f(_A + "teilnehmer", "text", "Teilnehmer", BEFUND, system=True, required=True, multiline=True,
       help_text="Wer bei der Abnahme anwesend ist – für Auftraggeber und Auftragnehmer, mit Funktion."),
    _f(_A + "umfang", "auswahl", "Umfang", BEFUND, system=True, required=True, options=[
        ("gesamt", "Gesamtabnahme"),
        ("teil", "Teilabnahme"),
    ]),
    _f(_A + "umfang_beschreibung", "text", "Abgenommener Teil", BEFUND, system=True, multiline=True,
       help_text="Nur bei einer Teilabnahme: welcher in sich abgeschlossene Teil abgenommen wird."),
    _f(_A + "dachflaechen", "dachflaechen", "Dachflächen", BEFUND, system=True,
       help_text="Die abgenommenen Dachflächen aus dem Objekt des Auftrags."),
    _f(_A + "maengel", "maengel", "Mängel", BEFUND, system=True,
       help_text="Jeden bei der Begehung festgestellten Mangel einzeln erfassen. Nach der Unterschrift des Auftraggebers "
                 "kommen keine neuen Mängel mehr dazu."),
    _f(_A + "einwendungen", "text", "Einwendungen des Auftragnehmers", BEFUND, system=True, multiline=True,
       help_text="Was der Betrieb zu den gerügten Mängeln einwendet."),
    _f(_A + "ergebnis", "auswahl", "Ergebnis", ERKLAERUNG, system=True, required=True, options=[
        ("abgenommen", "Abnahme erklärt"),
        ("verweigert", "Abnahme verweigert"),
    ]),
    _f(_A + "vorbehalt_maengel", "ja_nein", "Vorbehalt wegen bekannter Mängel", ERKLAERUNG, system=True,
       help_text="Nur bei „Abnahme erklärt“: behält sich der Auftraggeber seine Rechte wegen der im Protokoll stehenden "
                 "Mängel vor?"),
    _f(_A + "vorbehalt_vertragsstrafe", "ja_nein", "Vorbehalt der Vertragsstrafe", ERKLAERUNG, system=True,
       help_text="Nur bei „Abnahme erklärt“: behält sich der Auftraggeber eine Vertragsstrafe vor?"),
    _f(_A + "unterschrift_auftraggeber", "unterschrift", "Unterschrift Auftraggeber", ERKLAERUNG, system=True,
       required=True, signer_label="Auftraggeber", signer_mode="ag_oder_beteiligter",
       help_text="Unterschreibt der Auftraggeber laut Auftrag (Name der Person eintragen) oder ein Beteiligter, am "
                 "besten mit Vollmacht zur Abnahme. Die Unterschrift sperrt Befund und Erklärungen."),
    _f(_A + "unterschrift_auftragnehmer", "unterschrift", "Unterschrift Auftragnehmer", SCHLUSS, system=True,
       required=True, signer_label="Auftragnehmer", signer_mode="konto",
       help_text="Unterschreibt, wer für den Betrieb angemeldet ist."),
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
    sa.Column("prefill_now", sa.Boolean), sa.Column("signer_label", sa.String), sa.Column("signer_mode", sa.String),
    sa.Column("is_system", sa.Boolean),
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


def insert_acceptance_template(bind, now: datetime | None = None) -> bool:
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
            multiple=False, unit=None, min_value=None, max_value=None, decimals=None,
            min_count=None, max_count=1 if field_type == "unterschrift" else None,  # Einzelunterschrift
            prefill_now=False, signer_label=field.get("signer_label"), signer_mode=field.get("signer_mode", "frei"),
            is_system=bool(field.get("system")),
        )).inserted_primary_key[0]
        for option_index, (option_key, option_label) in enumerate(field.get("options", []), start=1):
            bind.execute(options_t.insert().values(field_id=field_id, option_key=option_key, label=option_label,
                                                   sort_order=option_index * 10))
    return True


def remove_acceptance_template(bind) -> bool:
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
    insert_acceptance_template(op.get_bind())


def downgrade() -> None:
    remove_acceptance_template(op.get_bind())
