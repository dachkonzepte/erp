"""Version 1.8.57 -- Stufe 2c-2c, Punkt 3 (docs/archiv/abnahme-und-gewaehrleistung.md, "Umsetzung 1.8.57").

Unterzeichner je Unterschriftsfeld (ChecklistTemplateField.signer_mode): "frei" wie bisher (Name eintippen), "konto"
(das angemeldete Konto, Name vom Server), "auftraggeber" (Kunde laut Auftrag) oder "beteiligter" (ein Beteiligter des
Projekts, Name und Rolle als Schnappschuss, Vollmacht zur Abnahme als Kopie eingefroren, ohne sie mit Warnung). Name, Art,
Konto, Beteiligter, Rolle und Vollmacht kommen beim Unterschreiben ins Siegel (seal_format 3, "v": 3, dazu Zeitpunkt und
Prüfsumme des Bilds); vorhandene Siegel (Format 2 und älter) bleiben gültig. Eine Unterschrift ist bis auf das Verwerfen
unveränderlich (ORM-Sperre). Angriffe: Unterzeichner über die API ändern (gleiche Kennung, zweite Unterschrift, falscher
Modus), am ORM vorbei und direkt in der Datenbank. Wichtige Tests auch gegen PostgreSQL (Plugin im Scratchpad)."""

import hashlib
import json

import pytest
from sqlalchemy import select, text, update

import app.checklists as checklists_module
from app.checklist_templates import add_field, create_template, publish_draft, update_field
from app.checklists import check_signature, get_checklist_row
from app.contacts import create_contact
from app.models import ArchiveImmutableError, ChecklistAttachment, ChecklistTemplateField, Order
from app.project_participants import add_participant, remove_participant, store_power_of_attorney
from app.routers.checklists import router as checklists_router
from tests.test_v305_checklist_filling import _fields, world  # noqa: F401
from tests.test_v349_abnahme_und_gewaehrleistung import PDF
from tests.test_v358_unterschrift_pruefung import SIGNATUR, _bild


@pytest.fixture
def abnahme(world):
    """Vorlage am Auftrag: Feststellung (Pflicht) -> Unterschrift Auftraggeber -> Unterschrift Beteiligter (mehrfach) ->
    Unterschrift Betrieb (Konto) -> Bemerkung -> freie Unterschrift. Beteiligte: Bauleitung mit Vollmacht zur Abnahme,
    Architektin ohne."""
    db = world["db"]
    t = create_template(db, label="Abnahmeprotokoll (Test)", contexts=["auftrag"])
    v = t["draft_version_id"]
    for werte in (
        {"field_type": "text", "label": "Feststellung", "field_key": "feststellung", "required": True},
        {"field_type": "unterschrift", "label": "Unterschrift Auftraggeber", "field_key": "ag", "signer_mode": "auftraggeber"},
        {"field_type": "unterschrift", "label": "Unterschrift Beteiligte", "field_key": "bet", "signer_mode": "beteiligter",
         "multiple": True, "max_count": 3},
        {"field_type": "unterschrift", "label": "Unterschrift Betrieb", "field_key": "betrieb", "signer_mode": "konto"},
        {"field_type": "text", "label": "Bemerkung", "field_key": "bem"},
        {"field_type": "unterschrift", "label": "Unterschrift Zeuge", "field_key": "frei"},
    ):
        add_field(db, v, werte)
    tpl = publish_draft(db, t["id"])
    order = db.get(Order, world["orders"]["mine"].id)
    from app.models import Project
    project = db.get(Project, order.project_id)
    bau = add_participant(db, project, create_contact(db, {"kind": "person", "first_name": "Bernd", "last_name": "Bau"}),
                          role="bauleitung_ag", acceptance_authorized=True)
    store_power_of_attorney(db, bau, filename="vollmacht.pdf", data=PDF, user_name="Olga Office", kind="abnahme")
    arch = add_participant(db, project, create_contact(db, {"kind": "person", "first_name": "Petra", "last_name": "Plan"}),
                           role="architekt_planer")
    fremdes_projekt = db.get(Project, db.get(Order, world["orders"]["foreign"].id).project_id)
    fremd = add_participant(db, fremdes_projekt, create_contact(db, {"kind": "person", "first_name": "Fritz",
                                                                     "last_name": "Fremd"}), role="architekt_planer")
    world.update(abn_tpl=tpl, bau=bau, arch=arch, order=order, fremd=fremd)
    return world


def _konto(w, who: str) -> int:
    """Ein echtes Konto (unter PostgreSQL verlangt checklists.created_by_user_id eines) -- einmal je Person."""
    from app.models import AppUser

    db = w["db"]
    name = {"office": "Olga Office", "a": "Anna Alpha"}[who]
    user = db.scalar(select(AppUser).where(AppUser.username == f"konto-{who}"))
    if user is None:
        user = AppUser(username=f"konto-{who}", display_name=name, role="buero_auftrag" if who == "office" else "field",
                       employee_id=w["emps"][who].id, active=True, password_hash="x")
        db.add(user)
        db.commit()
    return user.id


def _client(w, router_test_client, who):
    """Wie test_v305._client, aber mit einem echten Konto mit ID und Namen (Unterzeichner "angemeldetes Konto")."""
    if who == "office":
        return router_test_client(w["db"], checklists_router, role="buero_auftrag", employee_id=w["emps"]["office"].id,
                                  user_id=_konto(w, "office"), display_name="Olga Office")
    return router_test_client(w["db"], checklists_router, role="field", employee_id=w["emps"][who].id,
                              user_id=_konto(w, who), display_name="Anna Alpha")


def _start(w, client):
    r = client.post("/api/checklists", json={"template_id": w["abn_tpl"]["id"], "context_type": "auftrag",
                                             "order_id": w["order"].id})
    assert r.status_code == 200, r.text
    c = r.json()
    assert client.put(f"/api/checklists/{c['id']}/answers/{_fields(c)['feststellung']}",
                      json={"value": "ohne Mängel"}).status_code == 200
    return c


def _sign(client, c, key, **data):
    return client.post(f"/api/checklists/{c['id']}/attachments", data={"field_id": _fields(c)[key], **data},
                       files={"file": ("s.png", SIGNATUR, "image/png")})


def _sig(w, body, key):
    field_id = _fields(body)[key]
    a = [x for x in body["attachments"] if x["field_id"] == field_id and x["kind"] == "unterschrift"][-1]
    w["db"].expire_all()
    return a, w["db"].get(ChecklistAttachment, a["id"])


# ---------------------------------------------------------------------------
# Unterzeichner je Art
# ---------------------------------------------------------------------------

def test_account_signer_takes_name_from_the_logged_in_account(abnahme, router_test_client):
    office = _client(abnahme, router_test_client, "office")
    c = _start(abnahme, office)
    r = _sign(office, c, "betrieb")
    assert r.status_code == 200, r.text
    a, row = _sig(abnahme, r.json(), "betrieb")
    assert (row.signer_kind, row.seal_format, row.signer_participant_id) == ("konto", 3, None)
    assert (row.signer_user_id, row.signer_name, a["signer_name"]) == (_konto(abnahme, "office"), "Olga Office",
                                                                        "Olga Office")
    assert (a["signer_kind"], a["signer_kind_label"]) == ("konto", "angemeldetes Konto")
    seal = json.loads(row.sealed_content)
    assert seal["v"] == 3 and seal["signer"]["kind"] == "konto" and seal["signer"]["user_id"] == row.signer_user_id
    assert seal["signer"]["image_sha256"] == hashlib.sha256(checklists_module.attachment_path(row).read_bytes()).hexdigest()
    assert a["seal"]["status"] == "unveraendert"


def test_customer_signer_is_the_customer_of_the_order(abnahme, router_test_client):
    office = _client(abnahme, router_test_client, "office")
    c = _start(abnahme, office)
    assert c["signer_choices"][str(_fields(c)["ag"])] == {"mode": "auftraggeber", "name": "Kunde Nord"}
    a, row = _sig(abnahme, _sign(office, c, "ag", signer_person="Klara Kundin").json(), "ag")
    assert (row.signer_kind, row.signer_name, a["signer_kind_label"]) == ("auftraggeber", "Kunde Nord",
                                                                           "Auftraggeber laut Auftrag")
    # Ein späterer Kundenname am Auftrag ändert die Unterschrift nicht (Schnappschuss im Siegel).
    abnahme["db"].execute(update(Order).where(Order.id == abnahme["order"].id).values(customer_name="Neu GmbH"))
    abnahme["db"].commit()
    body = office.get(f"/api/checklists/{c['id']}").json()
    a, _ = _sig(abnahme, body, "ag")
    assert a["signer_name"] == "Kunde Nord" and a["seal"]["status"] == "unveraendert"


def test_participant_signer_with_frozen_power_of_attorney(abnahme, router_test_client):
    office = _client(abnahme, router_test_client, "office")
    c = _start(abnahme, office)
    choices = c["signer_choices"][str(_fields(c)["bet"])]
    assert choices["mode"] == "beteiligter"
    assert [(p["name"], p["role_label"], p["poa_on_record"]) for p in choices["participants"]] == [
        ("Bernd Bau", "Bauleitung des Auftraggebers", True), ("Petra Plan", "Architekt/Planer", False)]
    a, row = _sig(abnahme, _sign(office, c, "bet", participant_id=abnahme["bau"].id).json(), "bet")
    assert (row.signer_kind, row.signer_name, row.signer_role) == ("beteiligter", "Bernd Bau", "Bauleitung des Auftraggebers")
    assert row.signer_poa_sha256 == hashlib.sha256(PDF).hexdigest() and row.signer_poa_content_type == "application/pdf"
    copy = checklists_module.CHECKLIST_ROOT / str(c["id"]) / row.signer_poa_stored_filename
    assert copy.read_bytes() == PDF
    assert a["signer_poa"] is True and a["signer_without_poa"] is False
    seal = json.loads(row.sealed_content)["signer"]
    assert seal["participant_id"] == abnahme["bau"].id and seal["poa"]["sha256"] == row.signer_poa_sha256
    # Ohne Vollmacht: erfasst, gekennzeichnet.
    a2, row2 = _sig(abnahme, _sign(office, c, "bet", participant_id=abnahme["arch"].id).json(), "bet")
    assert row2.signer_poa_sha256 is None and a2["signer_without_poa"] is True
    # Der Beteiligte ersetzt seine Vollmacht später: die eingefrorene Kopie und das Siegel bleiben.
    store_power_of_attorney(abnahme["db"], abnahme["bau"], filename="neu.pdf", data=PDF + b"%neu", user_name="O",
                            kind="abnahme")
    a, _ = _sig(abnahme, office.get(f"/api/checklists/{c['id']}").json(), "bet")
    body = office.get(f"/api/checklists/{c['id']}").json()
    bernd = next(x for x in body["attachments"] if x["signer_name"] == "Bernd Bau")
    assert bernd["seal"]["status"] == "unveraendert" and copy.read_bytes() == PDF
    # Vollmacht-Kopie abrufbar fürs Büro, nicht für den Monteur.
    assert office.get(f"/api/checklist-attachments/{bernd['id']}/power-of-attorney").content == PDF


def test_free_signer_works_like_before(abnahme, router_test_client):
    office = _client(abnahme, router_test_client, "office")
    c = _start(abnahme, office)
    r = _sign(office, c, "frei", signer_name="Zeugin Zora")
    a, row = _sig(abnahme, r.json(), "frei")
    assert (row.signer_kind, row.signer_name, row.seal_format) == ("frei", "Zeugin Zora", 3)
    assert json.loads(row.sealed_content)["signer"] == {
        "kind": "frei", "name": "Zeugin Zora", "user_id": None, "participant_id": None, "role": None, "poa": None,
        "signed_at": row.created_at.isoformat(), "image_sha256": json.loads(row.sealed_content)["signer"]["image_sha256"]}


# ---------------------------------------------------------------------------
# Angriffe: Unterzeichner nachträglich ändern oder unterschieben
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("key, data, text", [
    ("betrieb", {"signer_name": "Jemand Anderes"}, "Den Namen setzt hier der Server"),
    ("ag", {"signer_name": "Jemand Anderes"}, "Den Namen setzt hier der Server"),
    ("bet", {}, "Bitte den Beteiligten wählen"),
    ("bet", {"participant_id": 999_999}, "Bitte einen Beteiligten dieses Projekts wählen"),
    ("bet", {"participant_id": "FREMD"}, "Bitte einen Beteiligten dieses Projekts wählen"),
    ("ag", {"participant_id": "PARTICIPANT"}, "Ein Beteiligter gehört nur"),
    ("frei", {}, "Bitte den Namen der unterschreibenden Person angeben"),
], ids=["konto_mit_name", "auftraggeber_mit_name", "beteiligter_ohne_wahl", "unbekannter_beteiligter",
        "beteiligter_anderes_projekt",
        "beteiligter_am_auftraggeber", "frei_ohne_name"])
def test_attack_wrong_signer_data_is_rejected(abnahme, router_test_client, key, data, text):
    office = _client(abnahme, router_test_client, "office")
    c = _start(abnahme, office)
    data = {k: {"PARTICIPANT": abnahme["bau"].id, "FREMD": abnahme["fremd"].id}.get(v, v) if isinstance(v, str) else v
            for k, v in data.items()}
    r = _sign(office, c, key, **data)
    assert r.status_code == 400 and text in r.json()["detail"], r.text
    abnahme["db"].expire_all()
    assert abnahme["db"].scalar(select(ChecklistAttachment.id).where(ChecklistAttachment.kind == "unterschrift")) is None


def test_attack_replay_with_same_key_cannot_change_the_signer(abnahme, router_test_client):
    office = _client(abnahme, router_test_client, "office")
    c = _start(abnahme, office)
    erste = _sign(office, c, "frei", signer_name="Zeugin Zora", client_uuid="k-1").json()
    zweite = _sign(office, c, "frei", signer_name="Mallory", client_uuid="k-1")
    assert zweite.status_code == 200 and zweite.json()["attachments"] == erste["attachments"]
    # Derselbe Beteiligte zweimal im selben Feld: abgelehnt.
    assert _sign(office, c, "bet", participant_id=abnahme["bau"].id).status_code == 200
    r = _sign(office, c, "bet", participant_id=abnahme["bau"].id)
    assert r.status_code == 409 and "schon unterschrieben" in r.json()["detail"]


def test_attack_signer_changed_at_the_orm_is_refused(abnahme, router_test_client):
    office = _client(abnahme, router_test_client, "office")
    c = _start(abnahme, office)
    _, row = _sig(abnahme, _sign(office, c, "ag", signer_person="Klara Kundin").json(), "ag")
    db = abnahme["db"]
    for feld, wert in (("signer_name", "Mallory"), ("signer_kind", "frei"), ("seal_format", 2),
                       ("signer_participant_id", abnahme["bau"].id), ("stored_filename", "anderes.png")):
        setattr(row, feld, wert)
        with pytest.raises(ArchiveImmutableError):
            db.flush()
        db.rollback()
        row = db.get(ChecklistAttachment, row.id)
    with pytest.raises(ArchiveImmutableError):
        db.delete(row)
        db.flush()
    db.rollback()


@pytest.mark.parametrize("spalte, wert", [
    ("signer_name", "Mallory"), ("signer_kind", "frei"), ("signer_role", "Bauherr"), ("signer_user_id", 4711),
    ("signer_poa_sha256", "0" * 64), ("signer_participant_id", None), ("seal_format", 2), ("seal_format", None),
], ids=["name", "art", "rolle", "konto", "vollmacht", "beteiligter", "format_2", "format_leer"])
def test_attack_signer_changed_in_the_database_is_detected(abnahme, router_test_client, spalte, wert):
    """Am ORM vorbei (rohes SQL): jede Änderung am Unterzeichner -- auch ein zurückgesetztes Siegelformat -- erscheint
    als "weicht ab: Unterzeichner" bzw. "Kopfangaben"."""
    office = _client(abnahme, router_test_client, "office")
    c = _start(abnahme, office)
    _, row = _sig(abnahme, _sign(office, c, "bet", participant_id=abnahme["bau"].id).json(), "bet")
    db = abnahme["db"]
    db.execute(text(f"UPDATE checklist_attachments SET {spalte} = :w WHERE id = :i"), {"w": wert, "i": row.id})
    db.commit()
    body = office.get(f"/api/checklists/{c['id']}").json()
    seal = next(x for x in body["attachments"] if x["id"] == row.id)["seal"]
    assert seal["status"] == "abweichend", seal
    assert "Unterzeichner" in seal["changed_fields"] or "Kopfangaben (Vorlage, Bezug)" in seal["changed_fields"], seal


def test_attack_image_replaced_on_disk_is_detected(abnahme, router_test_client):
    office = _client(abnahme, router_test_client, "office")
    c = _start(abnahme, office)
    _, row = _sig(abnahme, _sign(office, c, "ag", signer_person="Klara Kundin").json(), "ag")
    checklists_module.attachment_path(row).write_bytes(_bild(size=(310, 90)))  # ein anderes Bild
    body = office.get(f"/api/checklists/{c['id']}").json()
    seal = next(x for x in body["attachments"] if x["id"] == row.id)["seal"]
    assert seal["status"] == "abweichend" and "Unterzeichner" in seal["changed_fields"]


def test_attack_published_signer_mode_cannot_be_changed(abnahme):
    db = abnahme["db"]
    field = db.scalar(select(ChecklistTemplateField).where(ChecklistTemplateField.field_key == "ag",
                                                           ChecklistTemplateField.version_id == abnahme["abn_tpl"]["published_version_id"]))
    with pytest.raises(ValueError):
        update_field(db, field.id, {"signer_mode": "frei"})


# ---------------------------------------------------------------------------
# Vorlage, Bestand, Beteiligte
# ---------------------------------------------------------------------------

def test_template_rules_for_signer_modes(world):
    db = world["db"]
    t = create_template(db, label="Objekt-Prüfung", contexts=["auftrag", "objekt"])
    v = t["draft_version_id"]
    with pytest.raises(ValueError, match="Unbekannter Unterzeichner"):
        add_field(db, v, {"field_type": "unterschrift", "label": "U", "signer_mode": "jeder"})
    with pytest.raises(ValueError, match="Mehrere Unterschriften"):
        add_field(db, v, {"field_type": "unterschrift", "label": "U", "signer_mode": "konto", "multiple": True})
    body = add_field(db, v, {"field_type": "text", "label": "T", "signer_mode": "konto"})
    assert body["fields"][-1]["signer_mode"] == "frei"  # nur an Unterschriften
    add_field(db, v, {"field_type": "unterschrift", "label": "AG", "field_key": "ag", "signer_mode": "auftraggeber"})
    with pytest.raises(ValueError, match="nur am Auftrag"):
        publish_draft(db, t["id"])


def test_old_signatures_stay_valid(abnahme, router_test_client, monkeypatch):
    """Ein Siegel im Format 2 (vor 1.8.57, ohne Unterzeichner) bleibt "unverändert" -- es wird nach seinem eigenen
    Format geprüft."""
    office = _client(abnahme, router_test_client, "office")
    c = _start(abnahme, office)
    _, row = _sig(abnahme, _sign(office, c, "frei", signer_name="Alt").json(), "frei")
    db = abnahme["db"]
    checklist = get_checklist_row(db, c["id"])
    field = next(f for f in checklist.template_version.fields if f.field_key == "frei")
    alt = checklists_module.seal_content(checklist, field)  # Format 2
    db.execute(text("UPDATE checklist_attachments SET sealed_content = :s, content_sha256 = :h, seal_format = NULL, "
                    "signer_kind = NULL WHERE id = :i"),
               {"s": alt, "h": hashlib.sha256(alt.encode()).hexdigest(), "i": row.id})
    db.commit()
    db.expire_all()
    assert json.loads(alt)["v"] == 2
    assert check_signature(get_checklist_row(db, c["id"]), db.get(ChecklistAttachment, row.id))["status"] == "unveraendert"


def test_participant_who_signed_stays_in_the_project(abnahme, router_test_client):
    from app.project_participants import ParticipantInUseError

    office = _client(abnahme, router_test_client, "office")
    c = _start(abnahme, office)
    assert _sign(office, c, "bet", participant_id=abnahme["arch"].id).status_code == 200
    with pytest.raises(ParticipantInUseError, match="Checkliste unterschrieben"):
        remove_participant(abnahme["db"], abnahme["arch"])


def test_monteur_sees_choices_but_not_the_power_of_attorney(abnahme, router_test_client):
    a = _client(abnahme, router_test_client, "a")
    c = _start(abnahme, a)
    names = [p["name"] for p in c["signer_choices"][str(_fields(c)["bet"])]["participants"]]
    assert names == ["Bernd Bau", "Petra Plan"]
    r = _sign(a, c, "bet", participant_id=abnahme["bau"].id)
    assert r.status_code == 200
    bernd = next(x for x in r.json()["attachments"] if x["signer_name"] == "Bernd Bau")
    assert a.get(f"/api/checklist-attachments/{bernd['id']}/power-of-attorney").status_code == 403
    # Konto-Unterschrift der Monteurin: ihr Konto.
    r = _sign(a, c, "betrieb")
    assert r.status_code == 200
    assert next(x for x in r.json()["attachments"] if x["signer_kind"] == "konto")["signer_name"] == "Anna Alpha"


def test_pages_show_the_signer_by_mode():
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent / "app" / "templates"
    page = (root / "checklist.html").read_text(encoding="utf-8")
    assert "function signerInput(f,prefill)" in page and 'data-signer="${f.id}"' in page and "padPart_" in page
    assert "extra.participant_id=sel.value" in page and "extra.signer_name=name" in page
    assert "power-of-attorney" in page and "Vollmacht zur Abnahme: ja${IS_FIELD?" in page  # seit 1.8.59 mit Art
    editor = (root / "checklist_template.html").read_text(encoding="utf-8")
    assert 'data-k="signer_mode"' in editor and "['beteiligter','Beteiligter des Projekts" in editor


def _migration():
    import importlib.util
    from pathlib import Path

    path = next((Path(__file__).resolve().parent.parent / "alembic" / "versions").glob("*_checklisten_unterzeichner.py"))
    spec = importlib.util.spec_from_file_location("migration_1857_unterzeichner", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_adds_columns_and_refuses_downgrade_with_signers():
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import create_engine, inspect

    from app.database import Base

    module = _migration()
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    def run(name):
        with engine.begin() as conn:
            with Operations.context(MigrationContext.configure(conn)):
                getattr(module, name)()

    def spalten(table):
        return {c["name"] for c in inspect(engine).get_columns(table)}

    from sqlalchemy.orm import Session

    with Session(engine) as db:  # Bestand über die App-Funktionen -- unter SQLite wie unter PostgreSQL (Plugin-Lauf)
        tpl = create_template(db, label="Vorlage", contexts=["auftrag"])
        add_field(db, tpl["draft_version_id"], {"field_type": "unterschrift", "label": "AG", "signer_mode": "auftraggeber"})
    with pytest.raises(RuntimeError, match="1 Unterschriftsfelder mit festem Unterzeichner"):
        run("downgrade")
    with engine.begin() as conn:
        conn.execute(text("UPDATE checklist_template_fields SET signer_mode = 'frei'"))
    run("downgrade")
    assert "signer_mode" not in spalten("checklist_template_fields")
    assert not {"signer_kind", "seal_format", "signer_participant_id"} & spalten("checklist_attachments")
    run("upgrade")
    assert {"signer_kind", "signer_user_id", "signer_participant_id", "signer_role", "signer_poa_stored_filename",
            "signer_poa_content_type", "signer_poa_sha256", "seal_format"} <= spalten("checklist_attachments")
    with engine.connect() as conn:  # server_default: vorhandene Felder bleiben "frei"
        assert conn.execute(text("SELECT signer_mode FROM checklist_template_fields")).scalar() == "frei"
