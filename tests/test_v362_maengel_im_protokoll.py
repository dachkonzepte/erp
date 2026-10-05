"""Version 1.8.60 -- Stufe 2c-2d, Punkt 1 (docs/archiv/abnahme-und-gewaehrleistung.md, "Umsetzung 1.8.60").

Feldtyp "Mängel" (nur als Systemfeld eines Zwecks): Mängel entstehen im Entwurf des Protokolls mit Herkunft "protokoll"
(Defect.checklist_id, im gebundenen Inhalt statt der Abnahme), ohne Aufgabe und ohne Abnahme. In die feste Kopie jeder
Unterschrift darunter (und des Abschlusses) je Mangel Kennung und Prüfsumme seines Inhalts. Sobald eine gültige Unterschrift
das Feld versiegelt, entstehen an diesem Protokoll keine neuen Mängel. Vorher verworfene fehlen in der Kopie, danach
verworfene bleiben drin und werden als verworfen angezeigt. Bis die Abnahme aus dem Protokoll entsteht (1.8.62), keine
Haltung, Freigabe, Status oder Nachträge -- Verwerfen geht.

Gegen PostgreSQL (opt-in über ERP_TEST_POSTGRES_URL): ein Mangel, der während der Unterschrift erfasst wird, wartet auf die
Sperre der Checkliste und wird danach abgelehnt; umgekehrt wartet die Unterschrift und versiegelt den Mangel mit."""

import importlib.util
import json
import os
import threading
import time
import uuid
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import close_all_sessions, sessionmaker

import app.checklists as checklists_module
from app import acceptances as acceptances_module
from app.acceptances import content_sha256
from app.berlin_time import berlin_today
from app.checklist_purposes import PURPOSES, ChecklistPurpose, SystemField
from app.checklist_templates import add_field, create_template, publish_draft, update_field
from app.database import Base
from app.defects import PROTOCOL_PENDING_TEXT, create_protocol_defect, defect_content
from app.models import ChecklistAttachment, ChecklistTemplateField, Defect, DefectFile, Task
from app.routers import defects as defects_router
from app.routers.checklists import router as checklists_router
from tests.test_v349_abnahme_und_gewaehrleistung import PDF, _png, _welt, ablage, welt  # noqa: F401  (Fixtures)
from tests.test_v358_unterschrift_pruefung import SIGNATUR

ROOT = Path(__file__).resolve().parent.parent
PG_TEST_DATABASE_URL = os.getenv("ERP_TEST_POSTGRES_URL")
HEUTE = berlin_today()
KEY = "test_protokoll"
P = KEY + "."


def _zweck():
    return ChecklistPurpose(KEY, "Test Protokoll", ("auftrag",), (
        SystemField(P + "befund", "text", "Befund", required=True, section="Befund"),
        SystemField(P + "maengel", "maengel", "Mängel", section="Befund"),
        SystemField(P + "ag", "unterschrift", "Unterschrift Auftraggeber", required=True, section="Erklärung"),
        SystemField(P + "notiz", "text", "Notiz", section="Schluss"),
        SystemField(P + "an", "unterschrift", "Unterschrift Auftragnehmer", section="Schluss"),
    ))


@pytest.fixture
def protokoll(welt, ablage, tmp_path, monkeypatch, router_test_client):  # noqa: F811
    monkeypatch.setitem(PURPOSES, KEY, _zweck())
    monkeypatch.setattr(checklists_module, "CHECKLIST_ROOT", tmp_path / "checklisten")
    db = welt["db"]
    t = create_template(db, label="Abnahmeprotokoll (Test)", contexts=["auftrag"], purpose=KEY)
    tpl = publish_draft(db, t["id"])
    client = router_test_client(db, checklists_router, defects_router.router, role="buero_auftrag")
    r = client.post("/api/checklists", json={"template_id": tpl["id"], "context_type": "auftrag",
                                             "order_id": welt["order_id"]})
    assert r.status_code == 200, r.text
    c = r.json()
    f = {x["field_key"].split(".")[-1]: x["id"] for x in c["fields"]}
    assert client.put(f"/api/checklists/{c['id']}/answers/{f['befund']}", json={"value": "Dach dicht"}).status_code == 200
    return {**welt, "client": client, "c": c, "f": f, "tpl": tpl, "router_test_client": router_test_client}


def _mangel(p, description="Attika undicht", photos=(), receipts=(), **werte):
    data = {"description": description, **werte}
    files = [("photos", x) for x in photos] + [("receipts", x) for x in receipts]
    return p["client"].post(f"/api/checklists/{p['c']['id']}/defects", data={"data": json.dumps(data)}, files=files)


def _sign(p, key, name="Klara Kundin"):
    return p["client"].post(f"/api/checklists/{p['c']['id']}/attachments",
                            data={"field_id": p["f"][key], "signer_name": name},
                            files={"file": ("s.png", SIGNATUR, "image/png")})


def _sig(p, key):
    db = p["db"]
    db.expire_all()
    return db.scalar(select(ChecklistAttachment).where(ChecklistAttachment.template_field_id == p["f"][key],
                                                       ChecklistAttachment.discarded_at.is_(None)))


def _defects(db):
    db.expire_all()
    return db.scalars(select(Defect).order_by(Defect.id)).all()


def _view(p):
    return {x["id"]: x for x in p["client"].get(f"/api/checklists/{p['c']['id']}").json()["attachments"]}


def _discard(p, defect_id, reason="doppelt"):
    return p["client"].post(f"/api/defects/{defect_id}/discard", json={"reason": reason})


# ---------------------------------------------------------------------------
# Erfassen im Entwurf
# ---------------------------------------------------------------------------

def test_defect_from_protocol_has_protocol_origin_and_no_task_or_acceptance(protokoll):
    p, db = protokoll, protokoll["db"]
    r = _mangel(p, photos=[("vorher.png", _png("red"), "image/png")], receipts=[("ruege.pdf", PDF, "application/pdf")],
                roof_area_id=p["areas"]["Nord"], location="Attika West", remedy_due_on=(HEUTE + timedelta(days=7)).isoformat())
    assert r.status_code == 200, r.text
    [d] = _defects(db)
    assert (d.source, d.checklist_id, d.acceptance_id, d.task_id, d.roof_area_name) == (
        "protokoll", p["c"]["id"], None, None, "Nord")
    content = defect_content(d)
    assert content["checklist_id"] == p["c"]["id"] and "acceptance_id" not in content
    assert content_sha256(content) == d.content_sha256
    assert db.scalars(select(Task).where(Task.source_module == "maengel")).all() == []
    [eintrag] = r.json()
    assert (eintrag["in_protocol"], eintrag["sealed"], len(eintrag["files"]), eintrag["intact"]) == (True, False, 2, True)
    # Auftragsseite: aus dem Protokoll, noch ohne Abnahme, keine Aufgabe
    [v] = p["client"].get(f"/api/orders/{p['order_id']}/defects").json()
    assert (v["protocol_pending"], v["checklist_id"], v["source_label"], v["acceptance"]) == (
        True, p["c"]["id"], "Abnahmeprotokoll", None)
    assert v["task"] == {"exists": False, "text": "entsteht mit der Abnahme aus dem Abnahmeprotokoll"}


@pytest.mark.parametrize("werte, text", [
    ({"description": " "}, "Bitte den Mangel beschreiben."),
    ({"roof_area_id": "FREMD"}, "gehört nicht zum Objekt des Projekts"),
    ({"roof_area_id": "ALT"}, "ist archiviert"),
    ({"remedy_due_on": "GESTERN"}, "liegt in der Vergangenheit"),
], ids=["ohne_beschreibung", "fremde_dachflaeche", "archivierte_dachflaeche", "frist_vorbei"])
def test_invalid_protocol_defect_is_rejected(protokoll, werte, text):
    p = protokoll
    ersetzt = {"FREMD": p["fremd_area"], "ALT": p["areas"]["Anbau (alt)"],
               "GESTERN": (HEUTE - timedelta(days=1)).isoformat()}
    werte = {k: ersetzt.get(v, v) if isinstance(v, str) else v for k, v in werte.items()}
    r = _mangel(p, **werte)
    assert r.status_code == 400 and text in r.json()["detail"], r.text
    assert _defects(p["db"]) == []


def test_events_wait_for_the_acceptance_discard_works(protokoll):
    p = protokoll
    _mangel(p)
    [d] = _defects(p["db"])
    c = p["client"]
    for url, kwargs in ((f"/api/defects/{d.id}/stance", {"json": {"stance": "anerkannt"}}),
                        (f"/api/defects/{d.id}/release", {"json": {"released": True}}),
                        (f"/api/defects/{d.id}/status", {"data": {"data": json.dumps({"status": "erledigt_ohne",
                                                                                      "reason": "x"})}}),
                        (f"/api/defects/{d.id}/photos", {"files": [("photos", ("a.png", _png("red"), "image/png"))]}),
                        (f"/api/defects/{d.id}/receipts", {"files": [("receipts", ("a.pdf", PDF, "application/pdf"))]})):
        r = c.post(url, **kwargs)
        assert r.status_code == 409 and r.json()["detail"] == PROTOCOL_PENDING_TEXT, (url, r.text)
    assert _discard(p, d.id).status_code == 200


def test_maengel_field_takes_no_answer_and_is_system_only(protokoll):
    p, db = protokoll, protokoll["db"]
    r = p["client"].put(f"/api/checklists/{p['c']['id']}/answers/{p['f']['maengel']}", json={"value": "x"})
    assert r.status_code == 400 and "Mängel über „Mangel erfassen“" in r.json()["detail"]
    t = create_template(db, label="Von Hand", contexts=["auftrag"])
    with pytest.raises(ValueError, match="Feldtyp „Mängel“ gibt ein Zweck als Systemfeld vor"):
        add_field(db, t["draft_version_id"], {"field_type": "maengel", "label": "Mängel"})
    body = add_field(db, t["draft_version_id"], {"field_type": "text", "label": "Text"})
    with pytest.raises(ValueError, match="Feldtyp „Mängel“"):
        update_field(db, body["fields"][-1]["id"], {"field_type": "maengel"})


def test_monteur_cannot_read_or_create_protocol_defects(protokoll):
    p = protokoll
    monteur = p["router_test_client"](p["db"], checklists_router, defects_router.router, role="field")
    assert monteur.get(f"/api/checklists/{p['c']['id']}/defects").status_code == 403
    assert monteur.get(f"/api/checklists/{p['c']['id']}/protocol-options").status_code == 403
    r = monteur.post(f"/api/checklists/{p['c']['id']}/defects", data={"data": json.dumps({"description": "x"})})
    assert r.status_code == 403 and _defects(p["db"]) == []


# ---------------------------------------------------------------------------
# Kopie: je Mangel Kennung und Prüfsumme
# ---------------------------------------------------------------------------

def _entry(signature, key):
    return next(e for e in json.loads(signature.sealed_content)["fields"] if e["field_key"] == P + key)


def test_signature_seals_id_and_checksum_per_defect(protokoll):
    p, db = protokoll, protokoll["db"]
    _mangel(p, description="Attika undicht")
    _mangel(p, description="Rinne lose")
    assert _sign(p, "ag").status_code == 200
    sig = _sig(p, "ag")
    defects = _defects(db)
    assert _entry(sig, "maengel") == {"field_key": P + "maengel", "defects": [
        {"id": d.id, "sha256": content_sha256(defect_content(d))} for d in defects]}
    assert _view(p)[sig.id]["seal"]["status"] == "unveraendert"
    # Auftragnehmer darunter: dieselben Mängel in seiner Kopie
    assert _sign(p, "an", name="Olga Office").status_code == 200
    assert _entry(_sig(p, "an"), "maengel")["defects"] == _entry(sig, "maengel")["defects"]


def test_attack_defect_after_the_signature_is_rejected(protokoll):
    p, db = protokoll, protokoll["db"]
    _mangel(p)
    assert _sign(p, "ag").status_code == 200
    root = acceptances_module.ACCEPTANCE_FILE_ROOT
    dateien = sorted(x.name for x in root.rglob("*") if x.is_file()) if root.exists() else []
    r = _mangel(p, description="nachträglich", photos=[("x.png", _png("blue"), "image/png")])
    assert r.status_code == 409 and "keine neuen Mängel" in r.json()["detail"], r.text
    assert len(_defects(db)) == 1 and db.scalars(select(DefectFile)).all() == []  # der erste Mangel hatte keine Dateien
    assert (sorted(x.name for x in root.rglob("*") if x.is_file()) if root.exists() else []) == dateien
    # auch direkt über die Geschäftsfunktion
    with pytest.raises(checklists_module.ChecklistLocked):
        create_protocol_defect(db, p["c"]["id"], {"description": "direkt"}, [], user_id=None, user_name="x")
    assert len(_defects(db)) == 1
    # Seite: kein Formular mehr
    page = (ROOT / "app" / "templates" / "checklist.html").read_text(encoding="utf-8")
    assert "const offen=cl.status==='entwurf'&&!isSealed(f);" in page


def test_after_discarding_the_signature_defects_can_be_added_again(protokoll):
    """Festlegung: "nach der Unterschrift" heißt "solange eine gültige Unterschrift das Feld versiegelt"."""
    p = protokoll
    assert _sign(p, "ag").status_code == 200
    assert _mangel(p).status_code == 409
    r = p["client"].post(f"/api/checklists/{p['c']['id']}/discard-signatures",
                         json={"signature_id": _sig(p, "ag").id, "reason": "Mangel vergessen"})
    assert r.status_code == 200, r.text
    assert _mangel(p, description="nachgetragen").status_code == 200


def test_discarded_before_missing_discarded_after_kept(protokoll):
    p, db = protokoll, protokoll["db"]
    _mangel(p, description="vorher verworfen")
    _mangel(p, description="danach verworfen")
    vorher, danach = _defects(db)
    assert _discard(p, vorher.id).status_code == 200
    liste = {x["id"]: x for x in p["client"].get(f"/api/checklists/{p['c']['id']}/defects").json()}
    assert [(liste[d.id]["discarded"], liste[d.id]["in_protocol"]) for d in (vorher, danach)] == [(True, False), (False, True)]
    assert _sign(p, "ag").status_code == 200
    sig = _sig(p, "ag")
    assert [e["id"] for e in _entry(sig, "maengel")["defects"]] == [danach.id]
    assert _discard(p, danach.id).status_code == 200  # nach der Unterschrift verworfen: bleibt in der Kopie
    assert _view(p)[sig.id]["seal"]["status"] == "unveraendert"
    liste = {x["id"]: x for x in p["client"].get(f"/api/checklists/{p['c']['id']}/defects").json()}
    assert (liste[vorher.id]["discarded"], liste[vorher.id]["in_protocol"]) == (True, False)
    assert (liste[danach.id]["discarded"], liste[danach.id]["in_protocol"]) == (True, True)


def test_completion_seals_defects_too(protokoll):
    p, db = protokoll, protokoll["db"]
    _mangel(p)
    assert _sign(p, "ag").status_code == 200
    done = p["client"].post(f"/api/checklists/{p['c']['id']}/complete")
    assert done.status_code == 200 and done.json()["completion_seal"]["status"] == "unveraendert", done.text
    [d] = _defects(db)
    content = json.loads(db.get(checklists_module.Checklist, p["c"]["id"]).sealed_content)
    assert next(e for e in content["fields"] if e["field_key"] == P + "maengel")["defects"][0]["id"] == d.id
    assert _discard(p, d.id).status_code == 200  # nach dem Abschluss verworfen: Abschluss bleibt unverändert
    assert p["client"].get(f"/api/checklists/{p['c']['id']}").json()["completion_seal"]["status"] == "unveraendert"


def test_attack_defect_changed_in_the_database_shows_at_the_signature(protokoll):
    p, db = protokoll, protokoll["db"]
    _mangel(p)
    assert _sign(p, "ag").status_code == 200
    [d] = _defects(db)
    db.execute(text("UPDATE defects SET description = 'anders' WHERE id = :i"), {"i": d.id})
    db.commit()
    seal = _view(p)[_sig(p, "ag").id]["seal"]
    assert seal["status"] == "abweichend" and seal["changed_fields"] == ["Mängel"], seal


def test_page_lists_defects_and_offers_the_form_only_while_open():
    page = (ROOT / "app" / "templates" / "checklist.html").read_text(encoding="utf-8")
    assert "if(t==='maengel'){" in page and "loadProtocolDefects(f)" in page
    assert "`/api/checklists/${checklistId}/defects`" in page and "Mangel erfassen" in page
    assert "bleibt im Protokoll (erst nach der Unterschrift verworfen)" in page and "nicht im Protokoll" in page
    order = (ROOT / "app" / "templates" / "_maengel.html").read_text(encoding="utf-8")
    assert "const acts=d.protocol_pending?[['verwerfen','Verwerfen …']]" in order and "data-protokoll" in order


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------

def test_migration_adds_checklist_reference_and_refuses_downgrade(protokoll):
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import inspect

    path = next((ROOT / "alembic" / "versions").glob("*_maengel_aus_protokoll.py"))
    spec = importlib.util.spec_from_file_location("mig_maengel_aus_protokoll", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    p = protokoll
    _mangel(p)
    engine = p["db"].get_bind()

    def run(name):
        with engine.begin() as conn:
            with Operations.context(MigrationContext.configure(conn)):
                getattr(module, name)()

    with pytest.raises(RuntimeError, match="Downgrade verweigert: 1 Mängel stammen aus einem Abnahmeprotokoll"):
        run("downgrade")
    assert "checklist_id" in {c["name"] for c in inspect(engine).get_columns("defects")}


# ---------------------------------------------------------------------------
# PostgreSQL: Mangel und Unterschrift gleichzeitig
# ---------------------------------------------------------------------------

@pytest.fixture
def pg(monkeypatch, tmp_path):
    if not PG_TEST_DATABASE_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    monkeypatch.setitem(PURPOSES, KEY, _zweck())
    monkeypatch.setattr(acceptances_module, "ACCEPTANCE_FILE_ROOT", tmp_path / "abnahmen")
    monkeypatch.setattr(checklists_module, "CHECKLIST_ROOT", tmp_path / "checklisten")
    schema = f"pgtest_protokoll_{uuid.uuid4().hex[:8]}"
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
            t = create_template(setup, label="Protokoll (PG)", contexts=["auftrag"], purpose=KEY)
            tpl = publish_draft(setup, t["id"])
            c = checklists_module.create_checklist(setup, template_id=tpl["id"], context_type="auftrag",
                                                   order_id=w["order_id"])
            f = {x["field_key"].split(".")[-1]: x["id"] for x in c["fields"]}
            checklists_module.save_answer(setup, c["id"], f["befund"], "Dach dicht")
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


def test_postgresql_defect_during_signature_waits_and_is_rejected(pg):
    Session, w = pg
    ready = threading.Event()
    holder, release, thread = _held(Session, lambda s: checklists_module.add_attachment(
        s, w["checklist_id"], w["f"]["ag"], SIGNATUR, signer_name="Klara Kundin"), ready)
    assert ready.wait(timeout=10)
    result = {}
    other = threading.Thread(target=lambda: result.update(_timed(lambda: create_protocol_defect(
        Session(), w["checklist_id"], {"description": "während der Unterschrift"}, [], user_id=None, user_name="x"))))
    other.start()
    time.sleep(1.0)
    release.set()
    other.join(timeout=30)
    thread.join(timeout=30)
    holder.close()
    assert isinstance(result["result"], checklists_module.ChecklistLocked) and result["seconds"] >= 0.9, result
    check = Session()
    try:
        assert check.scalars(select(Defect)).all() == []
    finally:
        check.close()


def test_postgresql_signature_waits_for_the_defect_and_seals_it(pg):
    Session, w = pg
    ready = threading.Event()
    holder, release, thread = _held(Session, lambda s: create_protocol_defect(
        s, w["checklist_id"], {"description": "vor der Unterschrift"}, [], user_id=None, user_name="x"), ready)
    assert ready.wait(timeout=10)
    result = {}
    other = threading.Thread(target=lambda: result.update(_timed(lambda: checklists_module.add_attachment(
        Session(), w["checklist_id"], w["f"]["ag"], SIGNATUR, signer_name="Klara Kundin"))))
    other.start()
    time.sleep(1.0)
    release.set()
    other.join(timeout=30)
    thread.join(timeout=30)
    holder.close()
    assert isinstance(result["result"], dict) and result["seconds"] >= 0.9, result
    check = Session()
    try:
        [d] = check.scalars(select(Defect)).all()
        sig = check.scalar(select(ChecklistAttachment).where(ChecklistAttachment.kind == "unterschrift"))
        entry = next(e for e in json.loads(sig.sealed_content)["fields"] if e["field_key"] == P + "maengel")
        assert [x["id"] for x in entry["defects"]] == [d.id]
    finally:
        check.close()
