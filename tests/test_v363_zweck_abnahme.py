"""Version 1.8.61 -- Stufe 2c-2d, Punkt 2 (docs/archiv/abnahme-und-gewaehrleistung.md, "Umsetzung 1.8.61").

Zweck "abnahme": nur am Auftrag, nur Büro (Monteur sieht und startet nichts, auch nicht in /mobil), Systemfelder ohne Vorgabe
der Antworten in drei Abschnitten -- Befund (Teilnehmer, Umfang, abgenommener Teil, Dachflächen aus dem Objekt, Mängel,
Einwendungen), Erklärungen des Auftraggebers (Ergebnis, Vorbehalt Mängel, Vorbehalt Vertragsstrafe, Unterschrift Auftraggeber
laut Auftrag oder Beteiligter), Schluss (Unterschrift Auftragnehmer, Konto); Startvorlage per Migration. Bei der Unterschrift
des Auftraggebers lehnt der Server ab: Mängel ohne Vorbehalt, Vorbehalt ohne Mangel, "verweigert" ohne Mangel -- dazu, was die
Abnahme aus dem Protokoll (1.8.62) nicht annähme, und jeden anderen Unterzeichner.

Gegen PostgreSQL (opt-in über ERP_TEST_POSTGRES_URL): das Verwerfen des einzigen Mangels und die Unterschrift mit Vorbehalt
laufen nacheinander -- wer zuerst die Sperre hat, bestimmt das Ergebnis, nie ein halber Stand."""

import importlib.util
import json
import os
import threading
import time
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import close_all_sessions, sessionmaker

import app.checklists as checklists_module
from app import acceptances as acceptances_module
from app.checklist_purposes import ACCEPTANCE_SYSTEM_FIELDS, PURPOSES
from app.checklist_templates import (
    _normalize_field, get_version, publish_draft, start_draft, sync_system_fields, system_field_problems, update_field,
    validate_version_for_publish,
)
from app.checklists import signer_text
from app.database import Base
from app.defects import create_protocol_defect, discard_defect
from app.models import (
    AppUser, ChecklistAttachment, ChecklistTemplate, ChecklistTemplateField, ChecklistTemplateVersion, Defect, Employee,
    RoofArea, WorkPreparationEmployee,
)
from app.routers import defects as defects_router
from app.routers.checklists import router as checklists_router
from app.work_preparation import ensure_preparation
from tests.grunddaten_schalter import ohne_grunddaten
from tests.test_v349_abnahme_und_gewaehrleistung import PDF, _welt, ablage, welt  # noqa: F401  (Fixtures)
from tests.test_v358_unterschrift_pruefung import SIGNATUR

ROOT = Path(__file__).resolve().parent.parent
VERSIONS = ROOT / "alembic" / "versions"
PG_TEST_DATABASE_URL = os.getenv("ERP_TEST_POSTGRES_URL")
A = "abnahme."
AG = "unterschrift_auftraggeber"


def _load(name: str):
    path = next(VERSIONS.glob(f"*_{name}.py"))
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MIG = _load("abnahmeprotokoll_startvorlage")


def _konten(db, order_id: int) -> tuple[AppUser, AppUser]:
    """Büro und Monteurin als echte Konten (PostgreSQL verlangt sie), die Monteurin dem Auftrag zugeordnet."""
    olga = Employee(first_name="Olga", last_name="Office", employee_group="angestellt", active=True)
    mia = Employee(first_name="Mia", last_name="Monteurin", employee_group="gewerblich", active=True)
    db.add_all([olga, mia])
    db.flush()
    office = AppUser(username="olga", display_name="Olga Office", role="buero_auftrag", employee_id=olga.id, active=True,
                     password_hash="x")
    monteur = AppUser(username="mia", display_name="Mia Monteurin", role="field", employee_id=mia.id, active=True,
                      password_hash="x")
    db.add_all([office, monteur])
    db.commit()
    prep = ensure_preparation(db, order_id)
    db.add(WorkPreparationEmployee(preparation_id=prep.id, employee_id=mia.id))
    db.commit()
    return office, monteur


def _vorlage(db) -> dict:
    """Die Startvorlage aus der Migration, veröffentlicht wie sie ist."""
    assert MIG.insert_acceptance_template(db.connection())
    db.commit()
    return publish_draft(db, db.scalar(select(ChecklistTemplate.id).where(ChecklistTemplate.label == "Abnahmeprotokoll")))


def _answer(p, key, value, client=None):
    r = (client or p["client"]).put(f"/api/checklists/{p['c']['id']}/answers/{p['f'][key]}", json={"value": value})
    assert r.status_code == 200, r.text
    return r


def _mangel(p, description="Attika undicht") -> int:
    r = p["client"].post(f"/api/checklists/{p['c']['id']}/defects", data={"data": json.dumps({"description": description})})
    assert r.status_code == 200, r.text
    return max(d["id"] for d in r.json())


def _sign_ag(p, **data):
    data = data or {"signer_person": "Herbert Halle"}
    return p["client"].post(f"/api/checklists/{p['c']['id']}/attachments", data={"field_id": p["f"][AG], **data},
                            files={"file": ("s.png", SIGNATUR, "image/png")})


def _sig(p, key=AG):
    db = p["db"]
    db.expire_all()
    return db.scalar(select(ChecklistAttachment).where(ChecklistAttachment.template_field_id == p["f"][key],
                                                       ChecklistAttachment.discarded_at.is_(None)))


@pytest.fixture
def protokoll(welt, ablage, tmp_path, monkeypatch, router_test_client):  # noqa: F811
    """Abnahmeprotokoll aus der Startvorlage am Auftrag der Welt aus test_v349 (Objekt "Halle": Nord, Süd, Anbau (alt)
    archiviert; Bauleitung mit Vollmacht zur Abnahme, Architektin ohne). Ausgefüllt: Teilnehmer, Gesamtabnahme, abgenommen,
    beide Vorbehalte "nein" -- stimmig, solange kein Mangel dazukommt."""
    monkeypatch.setattr(checklists_module, "CHECKLIST_ROOT", tmp_path / "checklisten")
    db = welt["db"]
    office, monteur = _konten(db, welt["order_id"])
    tpl = _vorlage(db)
    client = router_test_client(db, checklists_router, defects_router.router, role="buero_auftrag",
                                employee_id=office.employee_id, user_id=office.id, display_name="Olga Office")
    field = router_test_client(db, checklists_router, defects_router.router, role="field",
                               employee_id=monteur.employee_id, user_id=monteur.id, display_name="Mia Monteurin")
    r = client.post("/api/checklists", json={"template_id": tpl["id"], "context_type": "auftrag",
                                             "order_id": welt["order_id"]})
    assert r.status_code == 200, r.text
    c = r.json()
    p = {**welt, "client": client, "field": field, "c": c, "tpl": tpl, "monteur": monteur,
         "f": {x["field_key"].removeprefix(A): x["id"] for x in c["fields"]}}
    for key, value in (("teilnehmer", "Herbert Halle (Auftraggeber), Olga Office (Auftragnehmer)"), ("umfang", "gesamt"),
                       ("ergebnis", "abgenommen"), ("vorbehalt_maengel", "nein"), ("vorbehalt_vertragsstrafe", "nein")):
        _answer(p, key, value)
    return p


# ---------------------------------------------------------------------------
# Zweck und Startvorlage
# ---------------------------------------------------------------------------

def test_purpose_has_office_only_system_fields_in_three_sections():
    purpose = PURPOSES["abnahme"]
    assert (purpose.contexts, purpose.office_only, purpose.voidable) == (("auftrag",), True, False)
    # seit 1.8.63 die Folge "Abnahme am Auftrag anlegen" nach der Unterschrift des Auftraggebers, je Unterschrift
    assert [(f.key, f.after_signature, f.per_signature, f.module) for f in purpose.follow_ups] == [
        (A + "abnahme_anlegen", A + AG, True, None)]
    assert [(s.key.removeprefix(A), s.field_type, s.required, s.section) for s in purpose.system_fields] == [
        ("teilnehmer", "text", True, "Befund"), ("umfang", "auswahl", True, "Befund"),
        ("umfang_beschreibung", "text", False, "Befund"), ("dachflaechen", "dachflaechen", False, "Befund"),
        ("maengel", "maengel", False, "Befund"), ("einwendungen", "text", False, "Befund"),
        ("ergebnis", "auswahl", True, "Erklärungen des Auftraggebers"),
        ("vorbehalt_maengel", "ja_nein", False, "Erklärungen des Auftraggebers"),
        ("vorbehalt_vertragsstrafe", "ja_nein", False, "Erklärungen des Auftraggebers"),
        ("unterschrift_auftraggeber", "unterschrift", True, "Erklärungen des Auftraggebers"),
        ("unterschrift_auftragnehmer", "unterschrift", True, "Schluss")]
    assert {s.key.removeprefix(A): s.signer_mode for s in purpose.system_fields if s.signer_mode} == {
        AG: "ag_oder_beteiligter", "unterschrift_auftragnehmer": "konto"}
    assert [key for key, _check in purpose.signature_checks] == [A + AG]
    assert not any(s.office_only for s in purpose.system_fields)  # der ganze Zweck ist Büro, nicht einzelne Felder


def test_signer_modes_and_field_types_fit_their_columns():
    """Unter PostgreSQL lehnt eine zu kurze Spalte den Wert ab, SQLite nimmt ihn still an -- so wäre der zuerst geplante
    Schlüssel "auftraggeber_oder_beteiligter" (29 Zeichen, signer_mode ist String(20)) erst auf dem Server aufgefallen."""
    from app.checklist_templates import FIELD_TYPES, SIGNER_MODES

    columns = ChecklistTemplateField.__table__.c
    assert [k for k in SIGNER_MODES if len(k) > columns.signer_mode.type.length] == []
    assert [k for k in FIELD_TYPES if len(k) > columns.field_type.type.length] == []
    assert [s.key for s in PURPOSES["abnahme"].system_fields if len(s.key) > columns.field_key.type.length] == []


def test_starter_template_passes_the_real_publish_check_and_matches_the_registry():
    engine = create_engine("sqlite:///:memory:")
    with ohne_grunddaten():
        Base.metadata.create_all(engine)
    with engine.begin() as conn:
        assert MIG.insert_acceptance_template(conn)
        assert not MIG.insert_acceptance_template(conn)  # keine Dublette
    db = sessionmaker(bind=engine)()
    template = db.scalar(select(ChecklistTemplate).where(ChecklistTemplate.label == "Abnahmeprotokoll"))
    [version] = template.versions
    assert (version.status, version.purpose, template.purpose, template.field_readable) == (
        "entwurf", "abnahme", "abnahme", False)
    assert (template.context_order, template.context_property, template.context_asset, template.context_company) == (
        True, False, False, False)
    system = [f for f in version.fields if f.is_system]
    assert [f.field_key for f in system] == [s.key for s in ACCEPTANCE_SYSTEM_FIELDS]
    assert [f.group_name for f in system] == [s.section for s in ACCEPTANCE_SYSTEM_FIELDS]
    assert [f.signer_mode for f in system if f.field_type == "unterschrift"] == ["ag_oder_beteiligter", "konto"]
    assert validate_version_for_publish(template, version) == []
    for field in version.fields:  # die echte Normalisierung ändert nichts (sonst still verändert beim Bearbeiten)
        before = {c: getattr(field, c) for c in ("required", "allow_na", "multiline", "multiple", "min_count",
                                                  "max_count", "signer_label", "signer_mode", "group_name", "help_text")}
        _normalize_field(field)
        assert {c: getattr(field, c) for c in before} == before, field.field_key
    db.rollback()
    assert publish_draft(db, template.id)["published_version_no"] == 1
    db.close()


def test_migration_removes_only_an_unused_draft(threaded_db_session):
    db = threaded_db_session
    conn = db.connection()
    assert MIG.insert_acceptance_template(conn) and MIG.remove_acceptance_template(conn)
    assert db.scalar(select(ChecklistTemplate.id).where(ChecklistTemplate.label == "Abnahmeprotokoll")) is None
    assert MIG.insert_acceptance_template(conn)
    db.commit()
    publish_draft(db, db.scalar(select(ChecklistTemplate.id).where(ChecklistTemplate.label == "Abnahmeprotokoll")))
    assert not MIG.remove_acceptance_template(db.connection())  # veröffentlicht: bleibt


def test_signer_of_a_system_signature_is_fixed(protokoll):
    p, db = protokoll, protokoll["db"]
    draft = get_version(db, start_draft(db, p["tpl"]["id"])["draft_version_id"])
    fields = {f["field_key"].removeprefix(A): f["id"] for f in draft["fields"]}
    with pytest.raises(ValueError, match="Den Unterzeichner dieses Systemfelds gibt der Zweck vor"):
        update_field(db, fields[AG], {"signer_mode": "frei"})
    update_field(db, fields[AG], {"signer_mode": "ag_oder_beteiligter", "label": "Unterschrift Bauherr"})  # gleich: geht
    db.execute(text("UPDATE checklist_template_fields SET signer_mode = 'beteiligter' WHERE id = :i"), {"i": fields[AG]})
    db.commit()
    db.expire_all()
    version = db.get(ChecklistTemplateVersion, draft["id"])
    problems = system_field_problems("abnahme", version)
    assert any("Unterschrift Bauherr" in x and "Unterzeichner" in x for x in problems), problems
    sync_system_fields(db, version.id)
    db.expire_all()
    assert db.get(ChecklistTemplateField, fields[AG]).signer_mode == "ag_oder_beteiligter"
    assert system_field_problems("abnahme", db.get(ChecklistTemplateVersion, draft["id"])) == []


def test_editor_and_purpose_list_show_fixed_signer_and_office_only(protokoll, router_test_client):
    """Über HTTP (die Antwortschemata filtern unbekannte Schlüssel): Zweckliste mit "nur Büro" und den festen
    Unterzeichnern, im Editor die beiden Unterschriften als vom Zweck vorgegeben."""
    from app.routers.checklist_templates import router as templates_router

    client = router_test_client(protokoll["db"], templates_router, role="buero_auftrag")
    purposes = {x["key"]: x for x in client.get("/api/checklist-purposes").json()}
    assert (purposes["abnahme"]["office_only"], purposes["allgemein"]["office_only"]) == (True, False)
    assert {s["key"].removeprefix(A): s["signer_mode"] for s in purposes["abnahme"]["system_fields"] if s["signer_mode"]} == {
        AG: "ag_oder_beteiligter", "unterschrift_auftragnehmer": "konto"}
    version_id = client.get(f"/api/checklist-templates/{protokoll['tpl']['id']}").json()["published_version_id"]
    fields = client.get(f"/api/checklist-template-versions/{version_id}").json()["fields"]
    assert {f["field_key"].removeprefix(A): f["signer_mode_locked"] for f in fields if f["field_type"] == "unterschrift"} == {
        AG: True, "unterschrift_auftragnehmer": True}
    assert not any(f["signer_mode_locked"] for f in fields if f["field_type"] != "unterschrift")


# ---------------------------------------------------------------------------
# Nur Büro
# ---------------------------------------------------------------------------

def test_monteur_never_sees_or_starts_an_acceptance_protocol(protokoll):
    p = protokoll
    m, cid, order_id = p["field"], p["c"]["id"], p["order_id"]
    office_start = p["client"].get("/api/checklists/startable-templates?context=auftrag").json()
    assert p["tpl"]["id"] in [t["id"] for t in office_start]
    assert p["tpl"]["id"] not in [t["id"] for t in m.get("/api/checklists/startable-templates?context=auftrag").json()]
    r = m.post("/api/checklists", json={"template_id": p["tpl"]["id"], "context_type": "auftrag", "order_id": order_id})
    assert (r.status_code, r.json()["detail"]) == (403, "Diese Checkliste führt das Büro.")
    assert cid not in [x["id"] for x in m.get(f"/api/checklists?order_id={order_id}").json()]
    for method, url, kwargs in (
        ("get", f"/api/checklists/{cid}", {}),
        ("get", f"/api/checklists/{cid}/pdf", {}),
        ("put", f"/api/checklists/{cid}/answers/{p['f']['teilnehmer']}", {"json": {"value": "x"}}),
        ("post", f"/api/checklists/{cid}/attachments", {"data": {"field_id": p["f"][AG], "signer_person": "X"},
                                                         "files": {"file": ("s.png", SIGNATUR, "image/png")}}),
        ("get", f"/api/checklists/{cid}/defects", {}),
    ):
        assert getattr(m, method)(url, **kwargs).status_code == 403, url
    # Auch eine "eigene" (am Router vorbei angelegt): nicht in "meine", kein Zugriff
    own = checklists_module.create_checklist(p["db"], template_id=p["tpl"]["id"], context_type="auftrag",
                                             order_id=order_id, created_by_employee_id=p["monteur"].employee_id,
                                             created_by_user_id=p["monteur"].id)
    assert own["id"] not in [x["id"] for x in m.get("/api/checklists/mine").json()]
    assert m.get(f"/api/checklists/{own['id']}").status_code == 403


# ---------------------------------------------------------------------------
# Unterzeichner Auftraggeber laut Auftrag oder Beteiligter
# ---------------------------------------------------------------------------

def test_customer_signs_as_customer_with_person_or_as_participant(protokoll):
    p = protokoll
    r = _sign_ag(p, signer_person="Herbert Halle", signer_function="Geschäftsführer")
    assert r.status_code == 200, r.text
    sig = _sig(p)
    assert (sig.signer_kind, sig.signer_person, sig.signer_function) == ("auftraggeber", "Herbert Halle", "Geschäftsführer")
    assert sig.signer_name == p["db"].get(checklists_module.Order, p["order_id"]).customer_name


@pytest.mark.parametrize("wer, vollmacht", [("bauleitung", True), ("architektin", False)])
def test_customer_field_takes_a_participant_with_or_without_power_of_attorney(protokoll, wer, vollmacht):
    p = protokoll
    r = _sign_ag(p, participant_id=p[wer])
    assert r.status_code == 200, r.text
    sig = _sig(p)
    assert (sig.signer_kind, sig.signer_participant_id, sig.signer_poa_sha256 is not None) == ("beteiligter", p[wer], vollmacht)
    zeile = signer_text(sig, "abnahme")
    assert ("Vollmacht zur Abnahme: ja (SHA-256" in zeile) if vollmacht else zeile.endswith(
        ", Achtung: Vollmacht zur Abnahme: nein"), zeile


@pytest.mark.parametrize("data, text_", [
    ({}, "Bitte den Namen der Person angeben"),
    ({"signer_name": "Irgendwer"}, "Den Namen setzt hier der Server"),
    ({"signer_person": "Herbert Halle", "participant_id": "BAU"}, "gehören nur zum Unterzeichner"),
], ids=["ohne_person", "freier_name", "person_und_beteiligter"])
def test_customer_field_rejects_incomplete_or_mixed_signers(protokoll, data, text_):
    p = protokoll
    data = {k: (p["bauleitung"] if v == "BAU" else v) for k, v in data.items()}
    r = p["client"].post(f"/api/checklists/{p['c']['id']}/attachments", data={"field_id": p["f"][AG], **data},
                         files={"file": ("s.png", SIGNATUR, "image/png")})
    assert r.status_code == 400 and text_ in r.json()["detail"], r.text
    assert _sig(p) is None


@pytest.mark.parametrize("mode, data", [("frei", {"signer_name": "Irgendwer"}), ("konto", {})], ids=["frei", "konto"])
def test_attack_wrong_signer_kind_at_the_customer_field(protokoll, mode, data):
    """Die Fassung trägt am ORM vorbei einen anderen Unterzeichner -- die Prüfung des Zwecks lehnt trotzdem ab."""
    p, db = protokoll, protokoll["db"]
    db.execute(text("UPDATE checklist_template_fields SET signer_mode = :m WHERE id = :i"), {"m": mode, "i": p["f"][AG]})
    db.commit()
    db.expire_all()
    r = p["client"].post(f"/api/checklists/{p['c']['id']}/attachments", data={"field_id": p["f"][AG], **data},
                         files={"file": ("s.png", SIGNATUR, "image/png")})
    assert r.status_code == 400, r.text
    assert "leistet der Auftraggeber laut Auftrag oder ein Beteiligter" in r.json()["detail"]
    assert _sig(p) is None


# ---------------------------------------------------------------------------
# Widersprüche bei der Unterschrift des Auftraggebers
# ---------------------------------------------------------------------------

def _verweigert(p):
    _answer(p, "ergebnis", "verweigert")
    _answer(p, "vorbehalt_maengel", None)
    _answer(p, "vorbehalt_vertragsstrafe", None)


@pytest.mark.parametrize("fall, text_", [
    ("maengel_ohne_vorbehalt", "aber kein Vorbehalt wegen Mängeln"),
    ("vorbehalt_ohne_mangel", "Vorbehalt wegen Mängeln, aber im Protokoll steht kein Mangel"),
    ("verweigert_ohne_mangel", "verweigert, aber im Protokoll steht kein Mangel"),
    ("vorbehalt_nur_verworfener_mangel", "Vorbehalt wegen Mängeln, aber im Protokoll steht kein Mangel"),
])
def test_attack_three_contradictions_are_rejected(protokoll, fall, text_):
    p = protokoll
    if fall == "maengel_ohne_vorbehalt":
        _mangel(p)
    elif fall == "vorbehalt_ohne_mangel":
        _answer(p, "vorbehalt_maengel", "ja")
    elif fall == "verweigert_ohne_mangel":
        _verweigert(p)
    else:
        assert p["client"].post(f"/api/defects/{_mangel(p)}/discard", json={"reason": "doppelt"}).status_code == 200
        _answer(p, "vorbehalt_maengel", "ja")
    r = _sign_ag(p)
    assert r.status_code == 400 and text_ in r.json()["detail"], r.text
    assert _sig(p) is None


@pytest.mark.parametrize("fall", ["ohne_maengel", "maengel_mit_vorbehalt", "verweigert_mit_mangel"])
def test_consistent_protocols_are_signed(protokoll, fall):
    p = protokoll
    if fall != "ohne_maengel":
        _mangel(p)
    if fall == "maengel_mit_vorbehalt":
        _answer(p, "vorbehalt_maengel", "ja")
    elif fall == "verweigert_mit_mangel":
        _verweigert(p)
    r = _sign_ag(p)
    assert r.status_code == 200, r.text
    assert _sig(p).seal_format == 3


@pytest.mark.parametrize("fall, text_", [
    ("teil_ohne_beschreibung", "Bei einer Teilabnahme bitte beschreiben"),
    ("gesamt_mit_beschreibung", "gehört nur zur Teilabnahme"),
    ("abgenommen_ohne_vorbehalt_maengel", "Rechte wegen bekannter Mängel vor?"),
    ("abgenommen_ohne_vorbehalt_vertragsstrafe", "die Vertragsstrafe vor?"),
    ("verweigert_mit_vorbehalt", "Bei einer verweigerten Abnahme gibt es keine Vorbehalte"),
])
def test_what_the_acceptance_would_reject_is_rejected_at_the_signature(protokoll, fall, text_):
    p = protokoll
    if fall == "teil_ohne_beschreibung":
        _answer(p, "umfang", "teil")
    elif fall == "gesamt_mit_beschreibung":
        _answer(p, "umfang_beschreibung", "nur Nord")
    elif fall == "abgenommen_ohne_vorbehalt_maengel":
        _answer(p, "vorbehalt_maengel", None)
    elif fall == "abgenommen_ohne_vorbehalt_vertragsstrafe":
        _answer(p, "vorbehalt_vertragsstrafe", None)
    else:
        _mangel(p)
        _answer(p, "ergebnis", "verweigert")
    r = _sign_ag(p)
    assert r.status_code == 400 and text_ in r.json()["detail"], r.text


def test_partial_acceptance_with_description_is_signed(protokoll):
    p = protokoll
    _answer(p, "umfang", "teil")
    _answer(p, "umfang_beschreibung", "Dachfläche Nord")
    assert _sign_ag(p).status_code == 200


# ---------------------------------------------------------------------------
# Dachflächen aus dem Objekt
# ---------------------------------------------------------------------------

def test_roof_areas_are_stored_with_name_and_sealed(protokoll):
    p, db = protokoll, protokoll["db"]
    body = _answer(p, "dachflaechen", [p["areas"]["Süd"], p["areas"]["Nord"], p["areas"]["Nord"]]).json()
    value = body["answers"][str(p["f"]["dachflaechen"])]["value"]
    assert value == sorted([{"id": p["areas"]["Nord"], "name": "Nord"}, {"id": p["areas"]["Süd"], "name": "Süd"}],
                           key=lambda a: a["id"])
    db.get(RoofArea, p["areas"]["Nord"]).name = "Nordseite"  # Umbenennen ändert die Antwort nicht
    db.commit()
    assert _sign_ag(p).status_code == 200
    entry = next(e for e in json.loads(_sig(p).sealed_content)["fields"] if e["field_key"] == A + "dachflaechen")
    assert entry["value"] == value
    _answer_cleared = p["client"].put(f"/api/checklists/{p['c']['id']}/answers/{p['f']['dachflaechen']}",
                                      json={"value": None})
    assert _answer_cleared.status_code == 409  # versiegelt


@pytest.mark.parametrize("wert, text_", [
    ("FREMD", "gehört nicht zum Objekt des Projekts"),
    ("ALT", "ist archiviert"),
    ("TEXT", "Liste von Kennungen"),
], ids=["fremd", "archiviert", "kein_liste"])
def test_invalid_roof_areas_are_rejected(protokoll, wert, text_):
    p = protokoll
    value = {"FREMD": [p["fremd_area"]], "ALT": [p["areas"]["Anbau (alt)"]], "TEXT": "Nord"}[wert]
    r = p["client"].put(f"/api/checklists/{p['c']['id']}/answers/{p['f']['dachflaechen']}", json={"value": value})
    assert r.status_code == 400 and text_ in r.json()["detail"], r.text


def test_roof_area_archived_after_the_answer_blocks_the_customer_signature(protokoll):
    p, db = protokoll, protokoll["db"]
    _answer(p, "dachflaechen", [p["areas"]["Süd"]])
    db.get(RoofArea, p["areas"]["Süd"]).archived = True
    db.commit()
    r = _sign_ag(p)
    assert r.status_code == 400 and "inzwischen archiviert" in r.json()["detail"], r.text


# ---------------------------------------------------------------------------
# Seiten
# ---------------------------------------------------------------------------

def test_pages_offer_roof_areas_and_the_customer_signer_choice():
    page = (ROOT / "app" / "templates" / "checklist.html").read_text(encoding="utf-8")
    assert "if(t==='dachflaechen'){" in page and "toggleRoofArea(" in page and "loadProtocolOptions()" in page
    assert "if(mode==='ag_oder_beteiligter'){" in page and "signerWhoChange(" in page
    assert "Bitte wählen, wer für den Auftraggeber unterschreibt." in page
    editor = (ROOT / "app" / "templates" / "checklist_template.html").read_text(encoding="utf-8")
    assert "['ag_oder_beteiligter','Auftraggeber laut Auftrag oder Beteiligter" in editor
    assert "f.signer_mode_locked?'disabled':d" in editor and "p.office_only" in editor


# ---------------------------------------------------------------------------
# PostgreSQL: Verwerfen des einzigen Mangels und Unterschrift mit Vorbehalt gleichzeitig
# ---------------------------------------------------------------------------

@pytest.fixture
def pg(monkeypatch, tmp_path):
    if not PG_TEST_DATABASE_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    monkeypatch.setattr(acceptances_module, "ACCEPTANCE_FILE_ROOT", tmp_path / "abnahmen")
    monkeypatch.setattr(checklists_module, "CHECKLIST_ROOT", tmp_path / "checklisten")
    schema = f"pgtest_abnahme_{uuid.uuid4().hex[:8]}"
    admin = create_engine(PG_TEST_DATABASE_URL)
    with admin.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
    engine = create_engine(PG_TEST_DATABASE_URL, pool_size=5,
                           connect_args={"options": f"-csearch_path={schema}", "application_name": schema})
    try:
        Base.metadata.create_all(engine)
        from app.grunddaten import anlegen

        Session = sessionmaker(bind=engine)
        setup = Session()
        try:
            anlegen(setup)
            setup.commit()
            w = _welt(setup)
            tpl = _vorlage(setup)
            c = checklists_module.create_checklist(setup, template_id=tpl["id"], context_type="auftrag",
                                                   order_id=w["order_id"])
            f = {x["field_key"].removeprefix(A): x["id"] for x in c["fields"]}
            for key, value in (("teilnehmer", "alle"), ("umfang", "gesamt"), ("ergebnis", "abgenommen"),
                               ("vorbehalt_maengel", "ja"), ("vorbehalt_vertragsstrafe", "nein")):
                checklists_module.save_answer(setup, c["id"], f[key], value)
            defect = create_protocol_defect(setup, c["id"], {"description": "Attika undicht"}, [], user_id=None,
                                            user_name="x")
        finally:
            setup.close()
        yield Session, {"checklist_id": c["id"], "f": f, "defect_id": defect.id}
    finally:
        close_all_sessions()
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE application_name = :n"),
                         {"n": schema})
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin.dispose()


def _held(Session, action, ready):
    """Führt action(session) aus, hält aber den Commit an, bis release gesetzt ist -- die Zeilensperre bleibt so lange."""
    holder = Session()
    commit = holder.commit
    release = threading.Event()

    def angehalten():
        holder.flush()
        ready.set()
        release.wait(timeout=30)
        commit()
    holder.commit = angehalten
    thread = threading.Thread(target=lambda: _swallow(lambda: action(holder)))
    thread.start()
    return holder, release, thread


def _swallow(fn):
    try:
        fn()
    except Exception:  # noqa: BLE001 -- die Folgen nach dem Commit sind hier nicht Gegenstand
        pass


def _timed(fn) -> dict:
    start, done = time.monotonic(), {}
    try:
        done["result"] = fn()
    except Exception as exc:  # noqa: BLE001
        done["result"] = exc
    done["seconds"] = time.monotonic() - start
    return done


def _sign(session, w):
    return checklists_module.add_attachment(session, w["checklist_id"], w["f"][AG], SIGNATUR, signer_person="Herbert Halle")


def _discard(session, w):
    return discard_defect(session, session.get(Defect, w["defect_id"]), reason="doppelt", user_id=None, user_name="x")


def _run(Session, first, second):
    ready = threading.Event()
    holder, release, thread = _held(Session, first, ready)
    assert ready.wait(timeout=10)
    result = {}
    other = threading.Thread(target=lambda: result.update(_timed(lambda: second(Session()))))
    other.start()
    time.sleep(1.0)
    release.set()
    other.join(timeout=30)
    thread.join(timeout=30)
    holder.close()
    return result


def test_postgresql_signature_waits_for_the_discard_and_is_rejected(pg):
    Session, w = pg
    result = _run(Session, lambda s: _discard(s, w), lambda s: _sign(s, w))
    assert isinstance(result["result"], ValueError) and result["seconds"] >= 0.9, result
    assert "Vorbehalt wegen Mängeln, aber im Protokoll steht kein Mangel" in str(result["result"])
    check = Session()
    try:
        assert check.scalar(select(ChecklistAttachment).where(ChecklistAttachment.kind == "unterschrift")) is None
    finally:
        check.close()


def test_postgresql_discard_waits_for_the_signature_and_stays_in_the_copy(pg):
    Session, w = pg
    result = _run(Session, lambda s: _sign(s, w), lambda s: _discard(s, w))
    assert not isinstance(result["result"], Exception) and result["seconds"] >= 0.9, result
    check = Session()
    try:
        sig = check.scalar(select(ChecklistAttachment).where(ChecklistAttachment.kind == "unterschrift"))
        entry = next(e for e in json.loads(sig.sealed_content)["fields"] if e["field_key"] == A + "maengel")
        assert [x["id"] for x in entry["defects"]] == [w["defect_id"]]
        assert checklists_module.check_signature(checklists_module.get_checklist_row(check, w["checklist_id"]),
                                                 sig)["status"] == "unveraendert"
    finally:
        check.close()
