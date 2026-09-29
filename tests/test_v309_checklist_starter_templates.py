"""Version 1.8.5 -- die 13 Startvorlagen (Daten-Migration). Die Migrationsdatei wird direkt geladen
(Muster CLAUDE.md "Eine Migrationsdatei selbst testen", über einen beschreibenden Namensteil statt
des Alembic-Hashs) und gegen eine frische Datenbank ausgeführt.

Geprüft: alle 13 als Entwurf, erster Hinweis + Beschreibung mit dem FaSi-Satz, jede Vorlage
besteht die ECHTE Veröffentlichungsprüfung und jedes Feld die echte Feldnormalisierung (sonst
könnte das Büro sie nach der Prüfung nicht veröffentlichen bzw. würde beim ersten Bearbeiten
still verändert), Einsatzbereitschafts-Schlüssel, field_readable, Regeln an Büro-Rollen,
keine Dublette bei vorhandener gleichnamiger Vorlage, Downgrade nur für Unberührtes."""

import copy
import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.checklist_templates import (
    _normalize_field, create_template, list_templates, publish_draft, validate_version_for_publish,
)
from app.checklists import create_checklist
from app.database import Base
from app.models import ChecklistTemplate, ChecklistTemplateVersion, OperationalAsset

MIGRATION = next(Path(__file__).resolve().parent.parent.joinpath("alembic", "versions").glob("*_checklisten_startvorlagen.py"))


def _load_migration():
    spec = importlib.util.spec_from_file_location("startvorlagen_migration", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def seeded():
    mig = _load_migration()
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        created = mig.insert_starter_templates(conn)
    db = sessionmaker(bind=engine)()
    try:
        yield mig, engine, db, created
    finally:
        db.close()


def _templates(db):
    return {t.label: t for t in db.scalars(select(ChecklistTemplate)).all()}


def _only_version(db, template):
    return db.scalars(select(ChecklistTemplateVersion).where(ChecklistTemplateVersion.template_id == template.id)).one()


def test_thirteen_drafts_with_safety_notice(seeded):
    mig, _engine, db, created = seeded
    assert len(created) == 13 == len(mig.STARTER_TEMPLATES)
    templates = _templates(db)
    assert set(templates) == set(created)
    for template in templates.values():
        version = _only_version(db, template)
        assert version.status == "entwurf" and version.version_no == 1 and version.published_at is None
        first = version.fields[0]
        assert first.field_type == "hinweis" and first.label == mig.FASI_SENTENCE
        assert mig.FASI_SENTENCE in template.description
        assert not template.archived and template.purpose == "allgemein"
    # Keine Monteurs-Sicht: nichts ist veröffentlicht, also startet niemand eine Startvorlage.
    assert all(t["published_version_no"] is None for t in list_templates(db))


def test_every_template_passes_the_real_publish_check_and_field_normalisation(seeded):
    _mig, _engine, db, _created = seeded
    for template in _templates(db).values():
        version = _only_version(db, template)
        assert validate_version_for_publish(template, version) == [], template.label
        for field in version.fields:
            probe = copy.copy(field)
            before = {k: getattr(field, k) for k in ("required", "allow_na", "multiline", "multiple", "unit",
                                                      "min_value", "max_value", "decimals", "min_count", "max_count",
                                                      "prefill_now", "signer_label")}
            _normalize_field(probe)  # wirft bei ungültigen Werten
            after = {k: getattr(probe, k) for k in before}
            assert before == after, (template.label, field.field_key, before, after)
        db.expire_all()


def test_published_starter_template_works_end_to_end(seeded):
    """Nach der Prüfung veröffentlichen und anlegen -- die Vorlage ist tatsächlich benutzbar."""
    _mig, _engine, db, _created = seeded
    template = _templates(db)["Geräte-Sichtprüfung"]
    publish_draft(db, template.id)
    asset = OperationalAsset(name="Hubsteiger")
    db.add(asset)
    db.commit()
    checklist = create_checklist(db, template_id=template.id, context_type="betriebsmittel", asset_id=asset.id)
    assert "einsatzbereit" in {f["field_key"] for f in checklist["fields"]}


def test_contexts_readability_readiness_keys_and_rule_roles(seeded):
    _mig, _engine, db, _created = seeded
    templates = _templates(db)
    readable = {label for label, t in templates.items() if t.field_readable}
    assert readable == {"Geräte-Sichtprüfung", "Schadensmeldung Gerät"}
    for label in readable:
        keys = {f.field_key: f for f in _only_version(db, templates[label]).fields}
        assert keys["einsatzbereit"].field_type == "ja_nein" and keys["einsatzbereit"].required
    unterweisung = templates["Sicherheitsunterweisung"]
    assert unterweisung.context_company and unterweisung.context_order and not unterweisung.context_asset
    signatures = {f.field_key: f for f in _only_version(db, unterweisung).fields}["teilnehmer"]
    assert signatures.multiple and signatures.required and signatures.min_count == 1
    for template in templates.values():
        for rule in _only_version(db, template).rules:
            assert rule.min_visible_role in ("buero_auftrag", "buero_finanzen", "admin")
    rules = {r.task_title: r for r in _only_version(db, templates["Sicherheitscheck vor Arbeitsbeginn"]).rules}
    rule = rules["Arbeitsbeginn nicht freigegeben: {kontext}"]
    assert (rule.operator, rule.field_key, rule.task_priority, rule.assignee_mode) == ("ist_nein", "freigabe", "hoch", "sachbearbeiter")


def test_existing_label_is_not_duplicated_and_rerun_adds_nothing():
    mig = _load_migration()
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    create_template(db, label="Tagesbericht", contexts=["auftrag"])  # vom Büro selbst angelegt
    db.close()
    with engine.begin() as conn:
        created = mig.insert_starter_templates(conn)
        assert "Tagesbericht" not in created and len(created) == 12
        assert mig.insert_starter_templates(conn) == []
    db = sessionmaker(bind=engine)()
    assert db.query(ChecklistTemplate).filter_by(label="Tagesbericht").count() == 1
    db.close()


def test_downgrade_removes_only_untouched_templates(seeded):
    mig, engine, db, _created = seeded
    templates = _templates(db)
    published = templates["Tagesbericht"]
    publish_draft(db, published.id)
    used = templates["Geräte-Sichtprüfung"]
    publish_draft(db, used.id)
    asset = OperationalAsset(name="Leiter")
    db.add(asset)
    db.commit()
    create_checklist(db, template_id=used.id, context_type="betriebsmittel", asset_id=asset.id)
    db.close()
    with engine.begin() as conn:
        removed = mig.remove_starter_templates(conn)
    assert len(removed) == 11 and "Tagesbericht" not in removed and "Geräte-Sichtprüfung" not in removed
    db = sessionmaker(bind=engine)()
    assert set(_templates(db)) == {"Tagesbericht", "Geräte-Sichtprüfung"}
    db.close()
