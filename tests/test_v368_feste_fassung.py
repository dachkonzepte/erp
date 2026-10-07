"""Version 1.8.66 -- Stufe 2c-2e, Punkt 1 (docs/archiv/abnahme-und-gewaehrleistung.md, "Umsetzung 1.8.66").

Feste Fassung für alle Checklisten: jede Unterschrift legt das PDF des Stands genau dieses Moments mit Prüfsumme in die Ablage --
im selben Commit, unter der Zeilensperre --, ebenso der Abschluss und "als gegenstandslos abschließen". Danach wird es nie neu
erzeugt: Download, Versand und nachgetragene Zustellung verwenden die abgelegten Bytes. Wird eine Unterschrift verworfen, die
eine Fassung zeigt, ist diese überholt und nicht mehr versendbar. Die Fassungen sieht nur das Büro.

Angriffe: PDF nach der Unterschrift verändert (Prüfsumme), Monteur ruft eine Fassung ab, Fassung am ORM vorbei ändern oder
löschen, Unterschrift ohne Fassung (PDF scheitert), zwei Unterschriften gleichzeitig (PostgreSQL)."""

import hashlib
import importlib.util
import json
import os
import random
import stat
import uuid
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import close_all_sessions, sessionmaker

import app.checklist_follow_ups as follow_ups_module
import app.checklists as checklists_module
from app.checklist_pdf import build_checklist_pdf
from app.checklist_templates import add_field, create_template, publish_draft
from app.checklist_versions import completion_version, latest_valid_version, versions_of
from app.database import Base
from app.models import (
    ArchiveImmutableError, Checklist, ChecklistAttachment, ChecklistVersion, GeneralSettings, SentDocument,
)
from app.routers import acceptances as acceptances_router
from app.routers import defects as defects_router
from app.routers.checklists import router as checklists_router
from app.routers.email_dispatches import router as dispatches_router
from app.sent_documents import SENT_DOCUMENT_ROOT, read_sent_document
from tests.test_v305_checklist_filling import _jpeg, _png, world  # noqa: F401  (Fixture)
from tests.test_v349_abnahme_und_gewaehrleistung import _welt, ablage, welt  # noqa: F401  (Fixtures)
from tests.test_v358_unterschrift_pruefung import SIGNATUR
from tests.test_v363_zweck_abnahme import _sig, _sign_ag, _vorlage
from tests.test_v365_abnahme_aus_protokoll import AN, ohne_folge, protokoll  # noqa: F401  (Fixtures)
from tests.test_v366_protokoll_seite_und_pdf import _pdf_text

ROOT = Path(__file__).resolve().parent.parent
PG_TEST_DATABASE_URL = os.getenv("ERP_TEST_POSTGRES_URL")


def _versions(db, checklist_id) -> list[ChecklistVersion]:
    db.expire_all()
    return versions_of(db, checklist_id)


def _sign_an(p):
    return p["client"].post(f"/api/checklists/{p['c']['id']}/attachments", data={"field_id": p["f"][AN]},
                            files={"file": ("s.png", SIGNATUR, "image/png")})


def _text(version) -> str:
    return " ".join(_pdf_text(read_sent_document(version.sent_document)).split())


def _archivpfad(document: SentDocument) -> Path:
    return SENT_DOCUMENT_ROOT / document.stored_filename


def _verfaelschen(document: SentDocument) -> None:
    """Die abgelegte Datei nach dem Speichern verändern (am System vorbei)."""
    path = _archivpfad(document)
    os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
    data = path.read_bytes()
    path.write_bytes(data.replace(b"ReportLab", b"ReportLaX", 1))


@pytest.fixture
def fassung(protokoll, router_test_client):
    """Abnahmeprotokoll aus test_v365 (Teilnehmer, Gesamtabnahme, abgenommen, Vorbehalt Mängel ja, ein Mangel), dazu das Büro
    mit dem Router der Ablage."""
    p = protokoll
    p["buero"] = router_test_client(p["db"], checklists_router, dispatches_router, defects_router.router,
                                    acceptances_router.router, role="buero_auftrag", employee_id=p["office"].employee_id,
                                    user_id=p["office"].id, display_name="Olga Office")
    return p


# ---------------------------------------------------------------------------
# Je Unterschrift und beim Abschluss eine Fassung
# ---------------------------------------------------------------------------

def test_each_signature_and_the_completion_store_a_fixed_version(fassung):
    p, db = fassung, fassung["db"]
    cid = p["c"]["id"]
    assert _versions(db, cid) == []
    assert _sign_ag(p).status_code == 200
    ag = _sig(p)
    [v1] = _versions(db, cid)
    doc = v1.sent_document
    assert (v1.version_no, v1.kind, v1.signature_id, json.loads(v1.signature_ids), v1.seal_sha256) == (
        1, "unterschrift", ag.id, [ag.id], ag.content_sha256)
    assert (doc.document_type, doc.document_id, doc.document_number) == ("checkliste", cid, f"Nr. {cid} · Fassung 1")
    assert hashlib.sha256(_archivpfad(doc).read_bytes()).hexdigest() == doc.sha256 and v1.created_by_name == "Olga Office"
    text1 = _text(v1)
    assert "Feste Fassung 1 – Stand bei der Unterschrift „Unterschrift Auftraggeber“" in text1
    # darunter steht nur noch eine Unterschrift -- also kein Hinweis auf offene Angaben unterhalb
    assert "Angaben unterhalb dieser Unterschrift" not in text1
    assert "Noch nicht abgeschlossen." in text1 and "Nicht unterschrieben." in text1  # die Unterschrift des Auftragnehmers fehlt
    assert _sign_an(p).status_code == 200
    an = _sig(p, AN)
    v2 = _versions(db, cid)[1]
    assert (v2.version_no, v2.signature_id, json.loads(v2.signature_ids)) == (2, an.id, sorted([ag.id, an.id]))
    r = p["client"].post(f"/api/checklists/{cid}/complete")
    assert r.status_code == 200, r.text
    v3 = _versions(db, cid)[2]
    checklist = db.get(Checklist, cid)
    assert (v3.version_no, v3.kind, v3.signature_id, v3.seal_sha256) == (3, "abschluss", None, checklist.content_sha256)
    text3 = _text(v3)
    assert "Feste Fassung 3 – Stand beim Abschluss" in text3 and "Noch nicht abgeschlossen." not in text3
    liste = p["buero"].get(f"/api/checklists/{cid}/versions").json()
    assert [(v["version_no"], v["kind"], v["valid"]) for v in liste] == [
        (1, "unterschrift", True), (2, "unterschrift", True), (3, "abschluss", True)]
    assert liste[0]["signature"]["field_label"] == "Unterschrift Auftraggeber"


def test_pdf_of_a_closed_checklist_comes_from_the_archive_never_regenerated(fassung):
    """Nach dem Abschluss den Firmennamen geändert: der PDF-Knopf liefert weiter die abgelegte Fassung (byte-gleich), ein neues
    Rendern sähe anders aus."""
    p, db = fassung, fassung["db"]
    cid = p["c"]["id"]
    assert _sign_ag(p).status_code == 200 and _sign_an(p).status_code == 200
    assert p["client"].post(f"/api/checklists/{cid}/complete").status_code == 200
    version = completion_version(db, db.get(Checklist, cid))
    archived = read_sent_document(version.sent_document)
    settings = db.get(GeneralSettings, 1)
    settings.company_name = "Ganz Andere Dächer GmbH"
    db.commit()
    r = p["buero"].get(f"/api/checklists/{cid}/pdf")
    assert r.status_code == 200 and r.content == archived and r.headers["X-DK-Ablage"] == str(version.sent_document_id)
    frisch = build_checklist_pdf(db, checklists_module.get_checklist_row(db, cid))
    assert "Ganz Andere Dächer GmbH" in _pdf_text(frisch) and "Ganz Andere Dächer GmbH" not in _pdf_text(r.content)


def test_discarded_signature_makes_every_version_showing_it_superseded(fassung):
    """Der Auftragnehmer unterschreibt zuerst (Fassung 1), dann der Auftraggeber (Fassung 2 zeigt beide). Wird nur die
    Unterschrift des Auftragnehmers verworfen, sind beide Fassungen überholt -- auch Fassung 2, deren eigene Unterschrift gilt.
    Eine neue Unterschrift ergibt Fassung 3, die jüngste gültige."""
    p, db = fassung, fassung["db"]
    cid = p["c"]["id"]
    assert _sign_an(p).status_code == 200
    an = _sig(p, AN)
    assert _sign_ag(p).status_code == 200
    r = p["client"].post(f"/api/checklists/{cid}/discard-signatures", json={"signature_id": an.id, "reason": "falsches Konto"})
    assert r.status_code == 200, r.text
    liste = p["buero"].get(f"/api/checklists/{cid}/versions").json()
    assert [v["valid"] for v in liste] == [False, False]
    assert liste[1]["superseded"]["field_label"] == "Unterschrift Auftragnehmer"
    assert latest_valid_version(db, db.get(Checklist, cid)) is None
    assert _sign_an(p).status_code == 200
    db.expire_all()
    latest = latest_valid_version(db, db.get(Checklist, cid))
    assert latest.version_no == 3 and [v["valid"] for v in p["buero"].get(f"/api/checklists/{cid}/versions").json()] == [
        False, False, True]


# ---------------------------------------------------------------------------
# Angriffe
# ---------------------------------------------------------------------------

def test_attack_failed_pdf_leaves_no_signature_and_no_file(fassung, monkeypatch):
    """Scheitert das PDF der Fassung, gibt es auch keine Unterschrift -- und keine liegengebliebene Datei."""
    import app.checklist_pdf as pdf_module

    p, db = fassung, fassung["db"]
    cid = p["c"]["id"]
    ordner = checklists_module.CHECKLIST_ROOT / str(cid)
    vorher = set(ordner.iterdir()) if ordner.exists() else set()

    def kaputt(*a, **k):
        raise RuntimeError("Renderer kaputt")
    monkeypatch.setattr(pdf_module, "build_checklist_version_pdf", kaputt)
    r = _sign_ag(p)
    assert r.status_code == 400 and "feste Fassung" in r.json()["detail"], r.text
    db.expire_all()
    assert db.scalars(select(ChecklistAttachment).where(ChecklistAttachment.kind == "unterschrift")).all() == []
    assert _versions(db, cid) == [] and (set(ordner.iterdir()) if ordner.exists() else set()) == vorher


def test_attack_failed_pdf_at_completion_leaves_the_draft(fassung, monkeypatch):
    """Dasselbe beim Abschluss: ohne PDF bleibt die Checkliste Entwurf, ohne Kopie des Abschlusses."""
    import app.checklist_pdf as pdf_module

    p, db = fassung, fassung["db"]
    cid = p["c"]["id"]
    assert _sign_ag(p).status_code == 200 and _sign_an(p).status_code == 200

    def kaputt(*a, **k):
        raise RuntimeError("Renderer kaputt")
    monkeypatch.setattr(pdf_module, "build_checklist_version_pdf", kaputt)
    r = p["client"].post(f"/api/checklists/{cid}/complete")
    assert r.status_code == 400 and "feste Fassung" in r.json()["detail"], r.text
    db.expire_all()
    checklist = db.get(Checklist, cid)
    assert (checklist.status, checklist.content_sha256, len(_versions(db, cid))) == ("entwurf", None, 2)


def test_attack_version_rows_are_immutable(fassung):
    p, db = fassung, fassung["db"]
    assert _sign_ag(p).status_code == 200
    [version] = _versions(db, p["c"]["id"])
    version.kind = "abschluss"
    with pytest.raises(ArchiveImmutableError):
        db.commit()
    db.rollback()
    [version] = _versions(db, p["c"]["id"])
    db.delete(version)
    with pytest.raises(ArchiveImmutableError):
        db.commit()
    db.rollback()


@pytest.fixture
def eigene(world, router_test_client, tmp_path, monkeypatch):  # noqa: F811
    """Checkliste der Monteurin am zugeordneten Auftrag (test_v305): ja/nein, Fotos, Unterschrift -- unterschrieben und
    abgeschlossen; dazu Büro und Monteurin mit dem Router der Ablage."""
    db = world["db"]
    monteurin = router_test_client(db, checklists_router, dispatches_router, role="field",
                                   employee_id=world["emps"]["a"].id)
    buero = router_test_client(db, checklists_router, dispatches_router, role="buero_auftrag",
                               employee_id=world["emps"]["office"].id)
    c = monteurin.post("/api/checklists", json={"template_id": world["order_tpl"]["id"], "context_type": "auftrag",
                                                "order_id": world["orders"]["mine"].id}).json()
    f = {x["field_key"]: x["id"] for x in c["fields"]}
    assert monteurin.put(f"/api/checklists/{c['id']}/answers/{f['frei']}", json={"value": "ja"}).status_code == 200
    assert monteurin.post(f"/api/checklists/{c['id']}/attachments", data={"field_id": f["fotos"]},
                          files={"file": ("f.jpg", _jpeg(), "image/jpeg")}).status_code == 200
    assert monteurin.post(f"/api/checklists/{c['id']}/attachments", data={"field_id": f["sig"], "signer_name": "Anna Alpha"},
                          files={"file": ("s.png", _png(), "image/png")}).status_code == 200
    r = monteurin.post(f"/api/checklists/{c['id']}/complete")
    assert r.status_code == 200, r.text
    return {"db": db, "monteurin": monteurin, "buero": buero, "c": c}


def test_attack_monteur_cannot_fetch_versions(eigene):
    """Die Monteurin hat die Checkliste selbst angelegt und unterschrieben: die Liste der Fassungen und die Dateien in der
    Ablage bleiben ihr verschlossen (403); den PDF-Knopf ihrer abgeschlossenen Checkliste behält sie -- er liefert dasselbe
    Dokument wie bisher, jetzt aus der Ablage. Das Büro sieht beide Fassungen."""
    db, c = eigene["db"], eigene["c"]
    versions = _versions(db, c["id"])
    assert [v.kind for v in versions] == ["unterschrift", "abschluss"]
    assert eigene["monteurin"].get(f"/api/checklists/{c['id']}/versions").status_code == 403
    for v in versions:
        assert eigene["monteurin"].get(f"/api/sent-documents/{v.sent_document_id}/file").status_code == 403
        assert eigene["monteurin"].get(f"/api/sent-documents/{v.sent_document_id}/check").status_code == 403
        assert eigene["buero"].get(f"/api/sent-documents/{v.sent_document_id}/file").status_code == 200
    assert len(eigene["buero"].get(f"/api/checklists/{c['id']}/versions").json()) == 2
    pdf = eigene["monteurin"].get(f"/api/checklists/{c['id']}/pdf")
    assert pdf.status_code == 200 and pdf.content == read_sent_document(versions[1].sent_document)


def test_attack_pdf_changed_after_the_signature_is_never_delivered(eigene, monkeypatch):
    """Die abgelegte Fassung nach dem Abschluss verändert: Download 409, Prüfen "weicht ab", Versand per E-Mail und
    nachgetragene Zustellung verweigert -- nichts geht hinaus, nichts wird still neu erzeugt."""
    from tests.test_v321_email_dispatch import FakeSMTP, _configure_smtp

    FakeSMTP.sent, FakeSMTP.fail, FakeSMTP.during_send = [], None, None
    monkeypatch.setattr("app.email_sending.smtplib.SMTP", FakeSMTP)
    db, c, buero = eigene["db"], eigene["c"], eigene["buero"]
    _configure_smtp(db)
    version = _versions(db, c["id"])[-1]
    _verfaelschen(version.sent_document)
    assert buero.get(f"/api/checklists/{c['id']}/pdf").status_code == 409
    assert buero.get(f"/api/sent-documents/{version.sent_document_id}/file").status_code == 409
    assert buero.get(f"/api/sent-documents/{version.sent_document_id}/check").json()["check"]["status"] == "abweichend"
    r = buero.post(f"/api/checklists/{c['id']}/send-email", json={"to_email": "buero@dachkonzepte.example",
                                                                  "dispatch_key": "checkliste-verfaelscht-01"})
    assert r.status_code == 400 and "nicht mehr unversehrt" in r.json()["detail"], r.text
    r = buero.post("/api/email-dispatches/manual", data={
        "document_type": "checkliste", "document_id": str(c["id"]), "channel": "persoenlich",
        "delivered_on": "2026-10-01", "note": "vor Ort übergeben", "dispatch_key": "checkliste-verfaelscht-02"})
    assert r.status_code == 400 and "nicht mehr unversehrt" in r.json()["detail"], r.text
    assert FakeSMTP.sent == [] and db.scalar(select(SentDocument.id).where(SentDocument.id > version.sent_document_id)) is None


# ---------------------------------------------------------------------------
# Größe: Fotos verkleinert, Originale unverändert
# ---------------------------------------------------------------------------

def _foto(seed: int) -> bytes:
    rng = random.Random(seed)
    small = Image.frombytes("RGB", (160, 120), rng.randbytes(160 * 120 * 3))
    buf = BytesIO()
    small.resize((1600, 1200), Image.BILINEAR).save(buf, format="JPEG", quality=92)
    return buf.getvalue()


def test_version_with_photos_is_reduced_and_originals_stay(world, router_test_client, monkeypatch):  # noqa: F811
    """Mit enger Grenze: die Fassung verkleinert die Fotos stufenweise, sagt es im PDF, die Originale bleiben byte-gleich."""
    import app.email_sending as email_sending_module

    monkeypatch.setattr(email_sending_module, "MAX_ATTACHMENT_BYTES", 250_000)
    db = world["db"]
    t = create_template(db, label="Fotos (Test)", contexts=["auftrag"])
    add_field(db, t["draft_version_id"], {"field_type": "foto", "label": "Fotos", "field_key": "fotos", "multiple": True,
                                          "max_count": 5})
    add_field(db, t["draft_version_id"], {"field_type": "unterschrift", "label": "Unterschrift", "field_key": "sig"})
    tpl = publish_draft(db, t["id"])
    field = router_test_client(db, checklists_router, role="field", employee_id=world["emps"]["a"].id)
    c = field.post("/api/checklists", json={"template_id": tpl["id"], "context_type": "auftrag",
                                            "order_id": world["orders"]["mine"].id}).json()
    f = {x["field_key"]: x["id"] for x in c["fields"]}
    for n in range(3):
        assert field.post(f"/api/checklists/{c['id']}/attachments", data={"field_id": f["fotos"]},
                          files={"file": (f"f{n}.jpg", _foto(n), "image/jpeg")}).status_code == 200
    db.expire_all()
    fotos = [a for a in db.get(Checklist, c["id"]).attachments if a.kind == "foto"]
    vorher = {a.id: hashlib.sha256(checklists_module.attachment_path(a).read_bytes()).hexdigest() for a in fotos}
    assert field.post(f"/api/checklists/{c['id']}/attachments", data={"field_id": f["sig"], "signer_name": "Anna Alpha"},
                      files={"file": ("s.png", _png(), "image/png")}).status_code == 200
    [version] = _versions(db, c["id"])
    text = _text(version)
    assert "Fotos in dieser Fassung auf höchstens" in text and "Pixel verkleinert" in text
    assert version.sent_document.size_bytes <= 250_000 or "360 Pixel" in text
    assert {a.id: hashlib.sha256(checklists_module.attachment_path(a).read_bytes()).hexdigest() for a in fotos} == vorher


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------

def test_migration_creates_the_table_and_refuses_downgrade_with_versions(fassung):
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    path = next((ROOT / "alembic" / "versions").glob("*_feste_fassung_checkliste.py"))
    spec = importlib.util.spec_from_file_location("mig_feste_fassung", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    p = fassung
    assert _sign_ag(p).status_code == 200
    engine = p["db"].get_bind()
    with engine.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            with pytest.raises(RuntimeError, match="Downgrade verweigert: 1 feste Fassungen"):
                module.downgrade()
    assert {"version_no", "signature_id", "signature_ids", "sent_document_id"} <= {
        c["name"] for c in inspect(engine).get_columns("checklist_versions")}
    assert module.down_revision == "4b9e2c7d1a63"


# ---------------------------------------------------------------------------
# PostgreSQL: zwei Unterschriften gleichzeitig
# ---------------------------------------------------------------------------

@pytest.fixture
def pg(monkeypatch, tmp_path):
    if not PG_TEST_DATABASE_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    import app.acceptances as acceptances_module
    import app.project_participants as participants_module
    from app.grunddaten import anlegen

    monkeypatch.setattr(acceptances_module, "ACCEPTANCE_FILE_ROOT", tmp_path / "abnahmen")
    monkeypatch.setattr(participants_module, "POWER_OF_ATTORNEY_ROOT", tmp_path / "vollmachten")
    monkeypatch.setattr(checklists_module, "CHECKLIST_ROOT", tmp_path / "checklisten")
    monkeypatch.setattr(follow_ups_module, "run_follow_ups_after_signature", lambda *a, **k: None)
    schema = f"pgtest_fassung_{uuid.uuid4().hex[:8]}"
    admin = create_engine(PG_TEST_DATABASE_URL)
    with admin.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
    engine = create_engine(PG_TEST_DATABASE_URL, pool_size=6,
                           connect_args={"options": f"-csearch_path={schema}", "application_name": schema})
    try:
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        setup = Session()
        try:
            anlegen(setup)
            setup.commit()
            w = _welt(setup)
            tpl = _vorlage(setup)
            c = checklists_module.create_checklist(setup, template_id=tpl["id"], context_type="auftrag",
                                                   order_id=w["order_id"])
            f = {x["field_key"].removeprefix("abnahme."): x["id"] for x in c["fields"]}
            for key, value in (("teilnehmer", "alle"), ("umfang", "gesamt"), ("ergebnis", "abgenommen"),
                               ("vorbehalt_maengel", "nein"), ("vorbehalt_vertragsstrafe", "nein")):
                checklists_module.save_answer(setup, c["id"], f[key], value)
        finally:
            setup.close()
        yield Session, {"checklist_id": c["id"], "f": f}
    finally:
        close_all_sessions()
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE application_name = :n"),
                         {"n": schema})
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin.dispose()


def test_postgresql_two_signatures_at_once_give_two_numbered_versions(pg):
    """Die erste Unterschrift hält ihren Commit an (Zeilensperre bleibt), die zweite wartet und bekommt danach Fassung 2, die
    beide Unterschriften zeigt -- keine doppelte Nummer, keine Fassung ohne die andere Unterschrift."""
    from tests.test_v365_abnahme_aus_protokoll import _run

    Session, w = pg

    def unterschreibe(key, **extra):
        return lambda s: checklists_module.add_attachment(s, w["checklist_id"], w["f"][key], SIGNATUR, **extra)["id"]

    first, second = _run(Session, unterschreibe("unterschrift_auftragnehmer", account_user_id=1, account_name="Olga"),
                         unterschreibe("unterschrift_auftraggeber", signer_person="Herbert Halle"))
    assert not isinstance(first, Exception) and not isinstance(second["result"], Exception), (first, second)
    assert second["seconds"] >= 0.9, second
    s = Session()
    try:
        versions = versions_of(s, w["checklist_id"])
        signatures = {a.template_field_id: a.id for a in s.scalars(select(ChecklistAttachment)
                                                                    .where(ChecklistAttachment.kind == "unterschrift"))}
        assert [v.version_no for v in versions] == [1, 2]
        assert versions[0].signature_id == signatures[w["f"]["unterschrift_auftragnehmer"]]
        assert json.loads(versions[1].signature_ids) == sorted(signatures.values())
        assert len({v.sent_document_id for v in versions}) == 2
    finally:
        s.close()
