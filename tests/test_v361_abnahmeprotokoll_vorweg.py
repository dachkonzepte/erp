"""Version 1.8.59 -- Stufe 2c-2d, Punkt 0 (docs/archiv/abnahme-und-gewaehrleistung.md, "Umsetzung 1.8.59").

- Unterzeichner "Auftraggeber laut Auftrag": Pflichtangabe "Name der unterschreibenden Person", optional Funktion, ohne
  Vorbelegung, im Siegel (nur wenn gesetzt -- Siegel von 1.8.57/1.8.58 bleiben gültig).
- Die Vollmacht-Kennzeichnung nennt immer die Art ("Vollmacht zur Abnahme: ja/nein"), als Warnung nur beim Zweck "abnahme".
- Veröffentlichen lehnt ab, wenn über einer Unterschrift, die auch der Monteur leisten kann, ein Pflichtfeld steht, das nur
  das Büro ausfüllt. Start- und Zweckvorlagen geprüft: nur die Behinderungsanzeige (Wegfall) -- bekannte Ausnahme."""

import importlib.util
import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

from app.checklist_purposes import PURPOSES, ChecklistPurpose, SystemField
from app.checklist_templates import (
    SIGNER_FILL_EXCEPTIONS, add_field, create_template, publish_draft, signer_fill_findings, signer_fill_problems,
    template_to_dict, validate_version_for_publish,
)
from app.checklists import signer_text
from app.database import Base
from app.models import ChecklistAttachment, ChecklistTemplate
from tests.test_v305_checklist_filling import _fields, world  # noqa: F401
from tests.test_v358_unterschrift_pruefung import SIGNATUR
from tests.test_v359_unterzeichner import _client, _sig, _sign, abnahme  # noqa: F401  (Fixtures)

ROOT = Path(__file__).resolve().parent.parent
VERSIONS = ROOT / "alembic" / "versions"


def _start_ohne_pflicht(w, client, tpl):
    r = client.post("/api/checklists", json={"template_id": tpl["id"], "context_type": "auftrag", "order_id": w["order"].id})
    assert r.status_code == 200, r.text
    c = r.json()
    if "feststellung" in _fields(c):
        assert client.put(f"/api/checklists/{c['id']}/answers/{_fields(c)['feststellung']}",
                          json={"value": "ohne Mängel"}).status_code == 200
    return c


# ---------------------------------------------------------------------------
# 0a: Person und Funktion beim Auftraggeber laut Auftrag
# ---------------------------------------------------------------------------

def test_customer_signer_needs_the_signing_person(abnahme, router_test_client):
    office = _client(abnahme, router_test_client, "office")
    c = _start_ohne_pflicht(abnahme, office, abnahme["abn_tpl"])
    r = _sign(office, c, "ag")
    assert r.status_code == 400 and r.json()["detail"] == (
        "Bitte den Namen der Person angeben, die für den Auftraggeber unterschreibt."), r.text
    assert abnahme["db"].scalar(select(ChecklistAttachment.id).where(ChecklistAttachment.kind == "unterschrift")) is None
    r = _sign(office, c, "ag", signer_person="  Klara   Kundin ", signer_function="Geschäftsführerin")
    a, row = _sig(abnahme, r.json(), "ag")
    assert (row.signer_name, row.signer_person, row.signer_function) == ("Kunde Nord", "Klara Kundin", "Geschäftsführerin")
    assert (a["signer_person"], a["signer_function"], a["seal"]["status"]) == ("Klara Kundin", "Geschäftsführerin",
                                                                            "unveraendert")
    signer = json.loads(row.sealed_content)["signer"]
    assert (signer["name"], signer["person"], signer["function"]) == ("Kunde Nord", "Klara Kundin", "Geschäftsführerin")
    assert signer_text(row) == ("Unterzeichner: Auftraggeber laut Auftrag, unterschrieben von Klara Kundin "
                                "(Geschäftsführerin)")


def test_function_is_optional(abnahme, router_test_client):
    office = _client(abnahme, router_test_client, "office")
    c = _start_ohne_pflicht(abnahme, office, abnahme["abn_tpl"])
    _, row = _sig(abnahme, _sign(office, c, "ag", signer_person="Klara Kundin").json(), "ag")
    signer = json.loads(row.sealed_content)["signer"]
    assert row.signer_function is None and "function" not in signer and signer["person"] == "Klara Kundin"


@pytest.mark.parametrize("key, extra", [
    ("frei", {"signer_name": "Zeugin Zora", "signer_person": "X"}),
    ("betrieb", {"signer_function": "Bauleiter"}),
    ("bet", {"participant_id": "BAU", "signer_person": "X"}),
], ids=["frei", "konto", "beteiligter"])
def test_attack_person_or_function_at_other_signers(abnahme, router_test_client, key, extra):
    office = _client(abnahme, router_test_client, "office")
    c = _start_ohne_pflicht(abnahme, office, abnahme["abn_tpl"])
    extra = {k: (abnahme["bau"].id if v == "BAU" else v) for k, v in extra.items()}
    r = _sign(office, c, key, **extra)
    assert r.status_code == 400 and "gehören nur zum Unterzeichner „Auftraggeber laut Auftrag“" in r.json()["detail"]


def test_older_seals_stay_valid_and_the_person_is_bound(abnahme, router_test_client):
    """Ohne Person (Konto, wie jede Unterschrift von 1.8.57/1.8.58) stehen die Schlüssel nicht im Siegel -- so rechnen
    ältere Siegel unverändert nach. Eine am ORM vorbei gesetzte oder entfernte Person ändert den Inhalt."""
    office = _client(abnahme, router_test_client, "office")
    c = _start_ohne_pflicht(abnahme, office, abnahme["abn_tpl"])
    _, konto = _sig(abnahme, _sign(office, c, "betrieb").json(), "betrieb")
    assert not {"person", "function"} & set(json.loads(konto.sealed_content)["signer"])
    _, ag = _sig(abnahme, _sign(office, c, "ag", signer_person="Klara Kundin").json(), "ag")
    db = abnahme["db"]
    for row_id, spalte, wert in ((konto.id, "signer_person", "Mallory"), (ag.id, "signer_person", None),
                                 (ag.id, "signer_function", "Prokurist")):
        alt = db.execute(text(f"SELECT {spalte} FROM checklist_attachments WHERE id = :i"), {"i": row_id}).scalar()
        db.execute(text(f"UPDATE checklist_attachments SET {spalte} = :w WHERE id = :i"), {"w": wert, "i": row_id})
        db.commit()
        seal = next(x for x in office.get(f"/api/checklists/{c['id']}").json()["attachments"] if x["id"] == row_id)["seal"]
        assert seal["status"] == "abweichend" and "Unterzeichner" in seal["changed_fields"], (spalte, seal)
        db.execute(text(f"UPDATE checklist_attachments SET {spalte} = :w WHERE id = :i"), {"w": alt, "i": row_id})
        db.commit()


def test_page_asks_for_person_without_prefill():
    page = (ROOT / "app" / "templates" / "checklist.html").read_text(encoding="utf-8")
    eingabe = next(z for z in page.splitlines() if 'id="padPerson_${f.id}"' in z)
    assert 'placeholder="Name der unterschreibenden Person"' in eingabe and "value=" not in eingabe.split("padPerson_")[1].split(">")[0]
    assert 'placeholder="Funktion (optional)"' in eingabe
    assert "extra.signer_person=per.value.trim()" in page and "Bitte den Namen der Person eintragen" in page


# ---------------------------------------------------------------------------
# 0b: Vollmacht immer mit Art, Warnung nur beim Zweck "abnahme"
# ---------------------------------------------------------------------------

def _beteiligter_ohne_vollmacht(w, client, purpose):
    db = w["db"]
    t = create_template(db, label=f"Protokoll {purpose}", contexts=["auftrag"], purpose=purpose)
    # Ganz oben: seit 1.8.61 trägt der Zweck "abnahme" Pflicht-Systemfelder -- über dieser Unterschrift steht keins davon
    add_field(db, t["draft_version_id"], {"field_type": "unterschrift", "label": "Beteiligter", "field_key": "bet",
                                          "signer_mode": "beteiligter", "sort_order": 1})
    tpl = publish_draft(db, t["id"])
    c = _start_ohne_pflicht(w, client, tpl)
    r = _sign(client, c, "bet", participant_id=w["arch"].id)
    assert r.status_code == 200, r.text
    return _sig(w, r.json(), "bet")


@pytest.mark.parametrize("purpose, warnung", [("allgemein", False), ("abnahme", True)])
def test_power_of_attorney_named_always_warning_only_for_acceptance(abnahme, router_test_client, purpose, warnung):
    office = _client(abnahme, router_test_client, "office")
    a, row = _beteiligter_ohne_vollmacht(abnahme, office, purpose)
    assert (a["signer_without_poa"], a["signer_poa_warning"]) == (True, warnung)
    assert signer_text(row, purpose).endswith(", Achtung: Vollmacht zur Abnahme: nein" if warnung
                                              else "(Architekt/Planer), Vollmacht zur Abnahme: nein")


def test_power_of_attorney_yes_names_the_type(abnahme, router_test_client):
    office = _client(abnahme, router_test_client, "office")
    c = _start_ohne_pflicht(abnahme, office, abnahme["abn_tpl"])
    _, row = _sig(abnahme, _sign(office, c, "bet", participant_id=abnahme["bau"].id).json(), "bet")
    assert f", Vollmacht zur Abnahme: ja (SHA-256 {row.signer_poa_sha256})" in signer_text(row, "abnahme")


def test_page_names_the_type_and_warns_only_for_acceptance():
    page = (ROOT / "app" / "templates" / "checklist.html").read_text(encoding="utf-8")
    assert "· Vollmacht zur Abnahme: ${p.poa_on_record?'ja':'nein'}" in page  # Auswahl
    assert "hint.hidden=!(p&&!p.poa_on_record&&cl.purpose==='abnahme')" in page  # Hinweis nur beim Zweck
    assert "a.signer_poa_warning?' · <span class=\"no-poa\">⚠ Vollmacht zur Abnahme: nein</span>':' · Vollmacht zur Abnahme: nein'" in page
    assert "ohne Vollmacht zur Abnahme" not in page.split("const poaText")[1].split("\n")[0]


# ---------------------------------------------------------------------------
# 0c: Pflichtfelder nur fürs Büro über einer Unterschrift, die auch der Monteur leistet
# ---------------------------------------------------------------------------

TEST_KEY = "test_buero_felder"


@pytest.fixture
def buerozweck(monkeypatch):
    monkeypatch.setitem(PURPOSES, TEST_KEY, ChecklistPurpose(TEST_KEY, "Test Büro-Felder", ("auftrag",), (
        SystemField(TEST_KEY + ".meldung", "text", "Meldung", required=True, section="Meldung"),
        SystemField(TEST_KEY + ".sig_meldung", "unterschrift", "Unterschrift Meldung", section="Meldung"),
        SystemField(TEST_KEY + ".anzeige", "text", "Anzeige", required=True, section="Anzeige", office_only=True),
        SystemField(TEST_KEY + ".notiz", "text", "Notiz Büro", section="Anzeige", office_only=True),
        SystemField(TEST_KEY + ".sig_buero", "unterschrift", "Unterschrift Büro", section="Anzeige", office_only=True),
        SystemField(TEST_KEY + ".sig_schluss", "unterschrift", "Unterschrift Schluss", section="Schluss"),
    )))


def test_publish_rejects_monteur_signature_below_office_only_required_field(world, buerozweck):
    db = world["db"]
    t = create_template(db, label="Zwei Abschnitte", contexts=["auftrag"], purpose=TEST_KEY)
    template = db.get(ChecklistTemplate, t["id"])
    version = template.versions[0]
    problems = validate_version_for_publish(template, version)
    assert problems == ["„Unterschrift Schluss“ kann auch der Monteur unterschreiben, darüber stehen Pflichtfelder, die nur "
                        "das Büro ausfüllt: Anzeige."]  # Meldung: nichts nur fürs Büro darüber; Büro: unterschreibt das Büro
    with pytest.raises(ValueError, match="Unterschrift Schluss"):
        publish_draft(db, t["id"])
    detail = template_to_dict(db.get(ChecklistTemplate, t["id"]), with_editable_version=True)
    assert detail["signer_fill_findings"] == [{"text": problems[0], "known_exception": False}]


def test_optional_office_field_or_office_signature_is_fine(world, buerozweck, monkeypatch):
    db = world["db"]
    spec = PURPOSES[TEST_KEY]
    ohne_pflicht = tuple(SystemField(s.key, s.field_type, s.label, required=False if s.key.endswith(".anzeige") else
                                     s.required, section=s.section, office_only=s.office_only) for s in spec.system_fields)
    monkeypatch.setitem(PURPOSES, TEST_KEY, ChecklistPurpose(TEST_KEY, spec.label, spec.contexts, ohne_pflicht))
    t = create_template(db, label="Ohne Pflicht", contexts=["auftrag"], purpose=TEST_KEY)
    template = db.get(ChecklistTemplate, t["id"])
    assert signer_fill_problems(TEST_KEY, template.versions[0]) == []


def _load(name: str):
    path = next(VERSIONS.glob(f"*_{name}.py"))
    spec = importlib.util.spec_from_file_location(f"mig_{name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_starter_and_purpose_templates_checked_only_the_known_exception():
    """Alle Startvorlagen (13 allgemeine, Behinderungs- und Bedenkenanzeige) über ihre Migrationen: Befund nur an der
    Behinderungsanzeige (Wegfall, Monteur oder Büro, unter den Pflichtfeldern der Anzeige) -- die bekannte Ausnahme. Jede
    Ausnahme muss einem echten Befund entsprechen (die Liste darf nur kürzer werden)."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        _load("checklisten_startvorlagen").insert_starter_templates(conn)
        _load("behinderungsanzeige_startvorlage").insert_obstruction_template(conn)
        _load("bedenkenanzeige_startvorlage").insert_concern_template(conn)
    db = sessionmaker(bind=engine)()
    befunde = {}
    for template in db.scalars(select(ChecklistTemplate)).all():
        for version in template.versions:
            for key, text_ in signer_fill_findings(template.purpose, version):
                befunde[(template.purpose, key)] = (template.label, text_)
    assert set(befunde) == set(SIGNER_FILL_EXCEPTIONS) == {("behinderungsanzeige", "behinderungsanzeige.unterschrift_wegfall")}
    assert "Ursache" in befunde[("behinderungsanzeige", "behinderungsanzeige.unterschrift_wegfall")][1]
    # die Ausnahme hindert das Veröffentlichen nicht
    template = db.scalar(select(ChecklistTemplate).where(ChecklistTemplate.label == "Behinderungsanzeige"))
    assert validate_version_for_publish(template, template.versions[0]) == []
    db.close()


def test_editor_shows_the_findings():
    page = (ROOT / "app" / "templates" / "checklist_template.html").read_text(encoding="utf-8")
    assert "template.signer_fill_findings" in page and "bekannte Ausnahme des Zwecks" in page
    assert "Veröffentlichen ist so nicht möglich." in page


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------

def test_migration_adds_person_columns_and_refuses_downgrade():
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import inspect

    module = _load("unterzeichner_person")
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    def run(name):
        with engine.begin() as conn:
            with Operations.context(MigrationContext.configure(conn)):
                getattr(module, name)()

    def spalten():
        return {c["name"] for c in inspect(engine).get_columns("checklist_attachments")}

    if engine.dialect.name != "sqlite":
        pytest.skip("Bestand mit rohem SQL ohne Fremdschlüssel nur unter SQLite (PostgreSQL: Migrationsprobe)")
    with engine.begin() as conn:
        conn.execute(text("PRAGMA foreign_keys=OFF"))
        conn.execute(text("INSERT INTO checklist_attachments (checklist_id, template_field_id, kind, stored_filename, "
                          "sort_order, created_at, signer_person) VALUES (1, 1, 'unterschrift', 'x.png', 10, "
                          "'2026-10-05 10:00:00', 'Klara')"))
    with pytest.raises(RuntimeError, match="Downgrade verweigert: 1 Unterschriften"):
        run("downgrade")
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM checklist_attachments"))
    run("downgrade")
    assert not {"signer_person", "signer_function"} & spalten()
    run("upgrade")
    assert {"signer_person", "signer_function"} <= spalten()
