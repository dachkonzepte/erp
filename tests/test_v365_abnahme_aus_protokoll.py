"""Version 1.8.63 -- Stufe 2c-2d Teil 2, Punkt 3 (docs/archiv/abnahme-und-gewaehrleistung.md, "Umsetzung 1.8.63").

Nach der Unterschrift des Auftraggebers im Abnahmeprotokoll legt die Folge "Abnahme am Auftrag anlegen" die Abnahme an -- über
dieselbe Prüf- und Anlegefunktion wie das Erfassen von Hand (create_acceptance() mit dem Nachweis "Protokoll"): förmlich, Datum
der Unterschrift in Europe/Berlin, Umfang/Ergebnis/Vorbehalte/Einwendungen/Dachflächen aus der versiegelten Kopie, der
Erklärende aus der Unterschrift samt eingefrorener Vollmacht; im selben Commit die Mängel der Kopie mit ihren Aufgaben. Je
Unterschrift höchstens eine Abnahme; eine neue aus demselben Protokoll nur über eine neue Unterschrift, nachdem Abnahme und
alte Unterschrift verworfen sind. Die Unterschrift lässt sich nicht verwerfen, solange die Abnahme aus ihr gilt.

Angriffe: doppelte Folge (auch gleichzeitig gegen PostgreSQL), Verwerfen der Unterschrift bei gültiger Abnahme (auch
gleichzeitig), am ORM vorbei geänderter Verweis, Mangel an einer Abnahme aus dem Protokoll."""

import importlib.util
import json
import os
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import close_all_sessions, sessionmaker

import app.acceptance_protocol as protocol_module
import app.acceptances as acceptances_module
import app.checklist_follow_ups as follow_ups_module
import app.checklists as checklists_module
from app import berlin_time
from app.acceptance_protocol import SignatureNotValid, acceptance_from_protocol, protocol_acceptance_input
from app.berlin_time import berlin_today, to_berlin
from app.checklist_follow_ups import list_follow_ups, run_checklist_follow_ups
from app.database import Base
from app.defects import PROTOCOL_PENDING_TEXT, create_protocol_defect
from app.models import (
    AuditLog, ChecklistAttachment, ChecklistFollowUp, ChecklistVersion, Defect, Order, OrderAcceptance, RoofArea, Task,
)
from app.routers import acceptances as acceptances_router
from app.routers import defects as defects_router
from app.routers.checklists import router as checklists_router
from tests.test_v349_abnahme_und_gewaehrleistung import _welt, ablage, welt  # noqa: F401  (Fixtures)
from tests.test_v358_unterschrift_pruefung import SIGNATUR
from tests.test_v363_zweck_abnahme import A, AG, _answer, _konten, _mangel, _sig, _sign_ag, _vorlage

ROOT = Path(__file__).resolve().parent.parent
PG_TEST_DATABASE_URL = os.getenv("ERP_TEST_POSTGRES_URL")
AN = "unterschrift_auftragnehmer"
FOLGE = "abnahme.abnahme_anlegen"


@pytest.fixture
def protokoll(welt, ablage, tmp_path, monkeypatch, router_test_client):  # noqa: F811
    """Abnahmeprotokoll aus der Startvorlage (wie test_v363), dazu der Abnahme-Router: Teilnehmer, Gesamtabnahme, abgenommen,
    Vorbehalt Mängel "ja", Vertragsstrafe "nein", ein Mangel -- stimmig."""
    monkeypatch.setattr(checklists_module, "CHECKLIST_ROOT", tmp_path / "checklisten")
    db = welt["db"]
    office, monteur = _konten(db, welt["order_id"])
    tpl = _vorlage(db)
    routers = (checklists_router, defects_router.router, acceptances_router.router)
    client = router_test_client(db, *routers, role="buero_auftrag", employee_id=office.employee_id, user_id=office.id,
                                display_name="Olga Office")
    field = router_test_client(db, *routers, role="field", employee_id=monteur.employee_id, user_id=monteur.id,
                               display_name="Mia Monteurin")
    r = client.post("/api/checklists", json={"template_id": tpl["id"], "context_type": "auftrag",
                                             "order_id": welt["order_id"]})
    assert r.status_code == 200, r.text
    c = r.json()
    p = {**welt, "client": client, "field": field, "c": c, "tpl": tpl, "office": office,
         "f": {x["field_key"].removeprefix(A): x["id"] for x in c["fields"]}}
    for key, value in (("teilnehmer", "Herbert Halle, Olga Office"), ("umfang", "gesamt"), ("ergebnis", "abgenommen"),
                       ("vorbehalt_maengel", "ja"), ("vorbehalt_vertragsstrafe", "nein")):
        _answer(p, key, value)
    p["mangel"] = _mangel(p, "Attika undicht")
    return p


@pytest.fixture
def ohne_folge(monkeypatch):
    """Die Folge läuft beim Unterschreiben nicht (Abbruch nach dem Commit der Unterschrift) -- zum Nachholen."""
    monkeypatch.setattr(follow_ups_module, "run_follow_ups_after_signature", lambda *a, **k: None)


def _acceptances(db) -> list[OrderAcceptance]:
    db.expire_all()
    return db.scalars(select(OrderAcceptance).order_by(OrderAcceptance.id)).all()


def _defect(db, defect_id) -> Defect:
    db.expire_all()
    return db.get(Defect, defect_id)


def _liste(p) -> dict:
    return {a["id"]: a for a in p["client"].get(f"/api/orders/{p['order_id']}/acceptances").json()}


def _discard_acceptance(p, acceptance_id):
    return p["client"].post(f"/api/order-acceptances/{acceptance_id}/discard", json={"reason": "falsche Person erfasst"})


def _discard_signature(p, sig_id):
    return p["client"].post(f"/api/checklists/{p['c']['id']}/discard-signatures",
                            json={"signature_id": sig_id, "reason": "neu unterschreiben"})


def _rows(db, checklist_id) -> dict:
    db.expire_all()
    return {r.follow_up_key: r for r in db.scalars(select(ChecklistFollowUp)
                                                    .where(ChecklistFollowUp.checklist_id == checklist_id))}


def _nachholen(p):
    return p["client"].post(f"/api/checklists/{p['c']['id']}/acceptance-from-protocol")


# ---------------------------------------------------------------------------
# Die Abnahme aus dem Protokoll
# ---------------------------------------------------------------------------

def test_customer_signature_creates_the_acceptance_from_the_sealed_copy(protokoll):
    p, db = protokoll, protokoll["db"]
    nord = p["areas"]["Nord"]
    _answer(p, "umfang", "teil")
    _answer(p, "umfang_beschreibung", "Dachfläche Nord samt Attika")
    _answer(p, "dachflaechen", [nord])
    _answer(p, "einwendungen", "Attika ist kein Mangel, sondern Restarbeit")
    r = _sign_ag(p, signer_person="Herbert Halle", signer_function="Geschäftsführer")
    assert r.status_code == 200, r.text
    sig = _sig(p)
    [a] = _acceptances(db)
    order = db.get(Order, p["order_id"])
    assert (a.kind, a.accepted_on, a.scope, a.scope_description, a.result, a.reservation_defects,
            a.reservation_penalty, a.contractor_objections) == (
        "foermlich", to_berlin(sig.created_at).date(), "teil", "Dachfläche Nord samt Attika", "abgenommen", True, False,
        "Attika ist kein Mangel, sondern Restarbeit")
    assert (a.declared_by, a.declared_by_name, a.declared_by_person, a.declared_by_function, a.participant_id) == (
        "auftraggeber", order.customer_name, "Herbert Halle", "Geschäftsführer", None)
    # seit 1.8.67 (Fassung 4) dazu die feste Fassung der Unterschrift und die Prüfsumme ihres PDFs
    version = db.scalar(select(ChecklistVersion).where(ChecklistVersion.signature_id == sig.id))
    assert (a.checklist_id, a.checklist_attachment_id, a.protocol_seal_sha256, a.checksum_format, a.protocol_version_id,
            a.protocol_pdf_sha256) == (p["c"]["id"], sig.id, sig.content_sha256, 4, version.id, version.sent_document.sha256)
    assert [(x.roof_area_id, x.roof_area_name) for x in a.roof_areas] == [(nord, "Nord")]
    assert a.files == [] and a.conduct_reason is None and a.created_by_name == "Olga Office"
    content = acceptances_module.acceptance_content(a)
    assert content["protocol"] == {"checklist_id": p["c"]["id"], "signature_id": sig.id, "seal_sha256": sig.content_sha256,
                                   "version_id": version.id, "pdf_sha256": version.sent_document.sha256}
    assert (content["declared_by_person"], content["checksum_format"]) == ("Herbert Halle", 4)
    eintrag = _liste(p)[a.id]
    assert eintrag["intact"] and eintrag["from_protocol"] and eintrag["protocol"]["check"] == "unveraendert"
    assert eintrag["protocol"]["url"] == f"/checklisten/{p['c']['id']}"  # die Seite (1.8.63 fälschlich /checklists/…)
    assert eintrag["defects"]["can_add"] is False and "Abnahmeprotokoll" in eintrag["defects"]["protocol_text"]
    # Mangel: an der Abnahme, mit Aufgabe -- erst jetzt Haltung, Freigabe, Status
    d = _defect(db, p["mangel"])
    assert d.acceptance_id == a.id and d.task_id is not None
    task = db.get(Task, d.task_id)
    assert (task.source_module, task.source_url) == ("maengel", f"/orders/{p['order_id']}#mangel-{d.id}")
    assert p["client"].post(f"/api/defects/{d.id}/stance", json={"stance": "anerkannt"}).status_code == 200
    # Folge: je Unterschrift, erledigt, Ziel die Abnahme
    [row] = _rows(db, p["c"]["id"]).values()
    assert (row.follow_up_key, row.status, row.target_type, row.target_id) == (f"{FOLGE}#{sig.id}", "erledigt", "abnahme", a.id)
    [folge] = list_follow_ups(db, p["c"]["id"])
    assert folge["target_url"] == f"/orders/{p['order_id']}#acceptanceCard" and f"Unterschrift Nr. {sig.id}" in folge["trigger_label"]


@pytest.mark.parametrize("wer, vollmacht", [("bauleitung", True), ("architektin", False)])
def test_participant_signature_with_its_frozen_power_of_attorney(protokoll, wer, vollmacht):
    p, db = protokoll, protokoll["db"]
    assert _sign_ag(p, participant_id=p[wer]).status_code == 200
    sig = _sig(p)
    [a] = _acceptances(db)
    assert (a.declared_by, a.participant_id, a.declared_by_name, a.declared_by_role, a.poa_on_record) == (
        "beteiligter", p[wer], sig.signer_name, sig.signer_role, vollmacht)
    files = [(f.kind, f.sha256) for f in a.files]
    assert files == ([("abnahmevollmacht", sig.signer_poa_sha256)] if vollmacht else [])
    assert _liste(p)[a.id]["without_power_of_attorney"] is (not vollmacht)


def test_power_of_attorney_comes_from_the_signature_not_from_todays_participant(protokoll, ohne_folge):
    """Zwischen Unterschrift und Nachholen nimmt das Büro die Vollmacht am Beteiligten zurück -- die Abnahme hält die beim
    Unterschreiben eingefrorene fest."""
    p, db = protokoll, protokoll["db"]
    assert _sign_ag(p, participant_id=p["bauleitung"]).status_code == 200
    sig = _sig(p)
    db.execute(text("UPDATE project_participants SET acceptance_authorized = :f, acceptance_poa_stored_filename = NULL, "
                    "acceptance_poa_sha256 = NULL WHERE id = :i"), {"f": False, "i": p["bauleitung"]})
    db.commit()
    assert _nachholen(p).status_code == 200
    [a] = _acceptances(db)
    assert a.poa_on_record is True and [(f.kind, f.sha256) for f in a.files] == [("abnahmevollmacht", sig.signer_poa_sha256)]


def test_the_follow_up_goes_through_create_acceptance(protokoll, monkeypatch):
    """Nichts nachgebaut: die Folge ruft genau die Anlegefunktion des Erfassens von Hand, mit dem Nachweis "Protokoll"."""
    p = protokoll
    calls = []
    real = acceptances_module.create_acceptance

    def spy(*args, **kwargs):
        calls.append(kwargs.get("protocol"))
        return real(*args, **kwargs)
    monkeypatch.setattr(acceptances_module, "create_acceptance", spy)
    assert _sign_ag(p).status_code == 200
    assert len(calls) == 1 and calls[0].signature_id == _sig(p).id and calls[0].checklist_id == p["c"]["id"]


def test_date_is_the_day_of_the_signature_in_berlin_not_of_the_follow_up(protokoll, ohne_folge, monkeypatch):
    """Unterschrift um 22:30 UTC = 00:30 in Berlin am nächsten Tag; die Folge wird drei Tage später nachgeholt."""
    p, db = protokoll, protokoll["db"]
    spaet = datetime.combine(berlin_today() - timedelta(days=2), datetime.min.time()) + timedelta(hours=22, minutes=30)

    class Uhr(datetime):
        @classmethod
        def utcnow(cls):
            return spaet
    monkeypatch.setattr(checklists_module, "datetime", Uhr)
    assert _sign_ag(p).status_code == 200
    monkeypatch.setattr(checklists_module, "datetime", datetime)
    sig = _sig(p)
    assert sig.created_at == spaet and to_berlin(spaet).date() == spaet.date() + timedelta(days=1)
    jetzt = berlin_time._utc_now()
    monkeypatch.setattr(berlin_time, "_utc_now", lambda: jetzt + timedelta(days=3))
    r = _nachholen(p)
    assert r.status_code == 200, r.text
    [a] = _acceptances(db)
    assert a.accepted_on == spaet.date() + timedelta(days=1) != berlin_today()


def test_defects_of_the_copy_get_the_acceptance_only_open_ones_a_task(protokoll, ohne_folge):
    """Vor der Unterschrift verworfen: nicht im Protokoll, keine Abnahme. Danach verworfen (vor dem Nachholen): im Protokoll,
    an der Abnahme, ohne Aufgabe. Offen: an der Abnahme mit Aufgabe."""
    p, db = protokoll, protokoll["db"]
    vorher = _mangel(p, "vorher verworfen")
    danach = _mangel(p, "danach verworfen")
    assert p["client"].post(f"/api/defects/{vorher}/discard", json={"reason": "doppelt"}).status_code == 200
    assert _sign_ag(p).status_code == 200
    assert p["client"].post(f"/api/defects/{danach}/discard", json={"reason": "doch keiner"}).status_code == 200
    assert _acceptances(db) == []
    assert _defect(db, p["mangel"]).acceptance_id is None  # bis zur Abnahme: noch offen im Protokoll
    assert _nachholen(p).status_code == 200
    [a] = _acceptances(db)
    stand = {i: (_defect(db, i).acceptance_id, _defect(db, i).task_id is not None) for i in (p["mangel"], vorher, danach)}
    assert stand == {p["mangel"]: (a.id, True), vorher: (None, False), danach: (a.id, False)}
    assert _liste(p)[a.id]["defects"]["active"] == 1


def test_signature_check_runs_the_same_acceptance_check(protokoll):
    """Was create_acceptance() ablehnt, lehnt schon die Unterschrift ab -- hier die Länge der Beschreibung des Teils (das
    Protokoll nimmt 10.000 Zeichen, die Abnahme 2.000). Bis 1.8.62 wäre die Unterschrift durchgegangen."""
    p, db = protokoll, protokoll["db"]
    _answer(p, "umfang", "teil")
    _answer(p, "umfang_beschreibung", "x" * 2001)
    r = _sign_ag(p)
    assert r.status_code == 400 and "höchstens 2000 Zeichen" in r.json()["detail"], r.text
    assert _sig(p) is None and _acceptances(db) == []


# ---------------------------------------------------------------------------
# Höchstens eine Abnahme je Unterschrift
# ---------------------------------------------------------------------------

def test_attack_double_follow_up_gives_one_acceptance(protokoll, monkeypatch):
    p, db = protokoll, protokoll["db"]
    assert _sign_ag(p).status_code == 200
    [a] = _acceptances(db)
    sig_id = _sig(p).id
    # Folge noch einmal, Nachholen, Wiederholung derselben Unterschrift (client_uuid fehlt -> zweite Unterschrift 409)
    assert run_checklist_follow_ups(db, p["c"]["id"]) == {"done": 0, "module_off": 0, "failed": 0}
    assert _nachholen(p).json()["id"] == a.id
    # Die Folge selbst: gibt es die Abnahme, ist sie die Antwort -- ohne erneutes Anlegen
    monkeypatch.setattr(acceptances_module, "create_acceptance", lambda *x, **k: pytest.fail("zweites Anlegen"))
    assert acceptance_from_protocol(db, p["c"]["id"], signature_id=sig_id).id == a.id
    assert [x.id for x in _acceptances(db)] == [a.id]


def test_attack_second_acceptance_for_the_same_signature_hits_the_unique_key(protokoll):
    """Der letzte Schutz, wenn alles andere versagt (SQLite sperrt keine Zeilen): der UNIQUE-Schlüssel."""
    p, db = protokoll, protokoll["db"]
    assert _sign_ag(p).status_code == 200
    checklist = checklists_module._load(db, p["c"]["id"])
    data, source = protocol_acceptance_input(db, checklist, _sig(p))
    with pytest.raises(IntegrityError):
        acceptances_module.create_acceptance(db, db.get(Order, p["order_id"]), data, [], user_id=None, user_name="x",
                                             protocol=source)
    assert len(_acceptances(db)) == 1
    assert "uq_order_acceptance_checklist_attachment" in {
        u["name"] for u in inspect(db.get_bind()).get_unique_constraints("order_acceptances")}


def test_attack_discarding_the_customer_signature_while_its_acceptance_is_valid(protokoll):
    p, db = protokoll, protokoll["db"]
    assert _sign_ag(p).status_code == 200
    r = p["client"].post(f"/api/checklists/{p['c']['id']}/attachments", data={"field_id": p["f"][AN]},
                         files={"file": ("s.png", SIGNATUR, "image/png")})
    assert r.status_code == 200, r.text
    [a] = _acceptances(db)
    sig, an = _sig(p), _sig(p, AN)
    r = _discard_signature(p, sig.id)
    assert r.status_code == 409 and "erst die Abnahme" in r.json()["detail"], r.text
    assert _sig(p).id == sig.id and _sig(p, AN).id == an.id  # beide gelten weiter
    with pytest.raises(checklists_module.ChecklistLocked):
        checklists_module.discard_signatures(db, p["c"]["id"], signature_id=sig.id, reason="direkt")
    # Die Unterschrift des Auftragnehmers darunter betrifft die Abnahme nicht
    assert _discard_signature(p, an.id).status_code == 200
    # nach dem Verwerfen der Abnahme geht es
    assert _discard_acceptance(p, a.id).status_code == 200
    assert _discard_signature(p, sig.id).status_code == 200


def test_new_signature_after_discarded_acceptance_gives_exactly_one_new_acceptance(protokoll):
    p, db = protokoll, protokoll["db"]
    erster = p["mangel"]
    assert _sign_ag(p).status_code == 200
    [a1] = _acceptances(db)
    s1 = _sig(p)
    task1 = _defect(db, erster).task_id
    assert _discard_acceptance(p, a1.id).status_code == 200
    # Nachholen bei verworfener Abnahme und gültiger Unterschrift: keine zweite (die Unterschrift hat ihre Abnahme gehabt)
    assert _nachholen(p).json()["id"] == a1.id
    assert p["client"].get(f"/api/orders/{p['order_id']}/pending-protocol-acceptances").json() == []
    assert len(_acceptances(db)) == 1
    # alte Unterschrift verwerfen -> Protokoll wieder offen, ein Mangel dazu, neu unterschreiben
    assert _discard_signature(p, s1.id).status_code == 200
    zweiter = _mangel(p, "Rinne lose")
    assert _sign_ag(p, signer_person="Hanna Halle").status_code == 200
    s2 = _sig(p)
    alle = _acceptances(db)
    assert len(alle) == 2
    a2 = alle[1]
    assert (a1.discarded_at is not None, a2.discarded_at, a2.checklist_attachment_id, a2.declared_by_person) == (
        True, None, s2.id, "Hanna Halle")
    # beide Mängel an der neuen Abnahme; der erste behält seine Aufgabe, der zweite bekommt eine
    assert (_defect(db, erster).acceptance_id, _defect(db, erster).task_id) == (a2.id, task1)
    assert _defect(db, zweiter).acceptance_id == a2.id and _defect(db, zweiter).task_id is not None
    umgehaengt = db.scalars(select(AuditLog).where(AuditLog.entity_type == "Mangel", AuditLog.entity_id == str(erster),
                                                  AuditLog.field_name == "acceptance_id")).all()
    assert [(x.old_value, x.new_value) for x in umgehaengt] == [(str(a1.id), str(a2.id))]
    # Folgen: je Unterschrift eine Zeile; noch einmal ausführen ändert nichts
    rows = _rows(db, p["c"]["id"])
    assert {k: r.status for k, r in rows.items()} == {f"{FOLGE}#{s1.id}": "erledigt", f"{FOLGE}#{s2.id}": "erledigt"}
    run_checklist_follow_ups(db, p["c"]["id"])
    assert len(_acceptances(db)) == 2


# ---------------------------------------------------------------------------
# Ausstehend, Nachholen, Gründe
# ---------------------------------------------------------------------------

def test_pending_acceptance_is_shown_at_the_order_and_can_be_caught_up(protokoll, ohne_folge):
    p, db = protokoll, protokoll["db"]
    assert _sign_ag(p).status_code == 200
    [eintrag] = p["client"].get(f"/api/orders/{p['order_id']}/pending-protocol-acceptances").json()
    assert (eintrag["checklist_id"], eintrag["signature_id"], eintrag["problem"]) == (p["c"]["id"], _sig(p).id, None)
    # bis dahin: der Mangel wartet
    r = p["client"].post(f"/api/defects/{p['mangel']}/stance", json={"stance": "anerkannt"})
    assert r.status_code == 409 and r.json()["detail"] == PROTOCOL_PENDING_TEXT
    r = _nachholen(p)
    assert r.status_code == 200 and r.json()["from_protocol"], r.text
    assert p["client"].get(f"/api/orders/{p['order_id']}/pending-protocol-acceptances").json() == []


def test_a_follow_up_that_cannot_run_shows_why_and_runs_later(protokoll, ohne_folge):
    """Die gewählte Dachfläche wird nach der Unterschrift archiviert: die Abnahme nähme sie nicht -- der Hinweis nennt den
    Grund, Nachholen antwortet 409; nach dem Zurückholen der Dachfläche klappt es."""
    p, db = protokoll, protokoll["db"]
    _answer(p, "dachflaechen", [p["areas"]["Nord"]])
    assert _sign_ag(p).status_code == 200
    db.get(RoofArea, p["areas"]["Nord"]).archived = True
    db.commit()
    [eintrag] = p["client"].get(f"/api/orders/{p['order_id']}/pending-protocol-acceptances").json()
    assert "„Nord“ ist archiviert" in eintrag["problem"]
    r = _nachholen(p)
    assert r.status_code == 409 and "„Nord“ ist archiviert" in r.json()["detail"]
    assert [r.status for r in _rows(db, p["c"]["id"]).values()] == ["ausstehend"]
    db.get(RoofArea, p["areas"]["Nord"]).archived = False
    db.commit()
    assert _nachholen(p).status_code == 200
    assert [r.status for r in _rows(db, p["c"]["id"]).values()] == ["erledigt"]


def test_follow_up_of_a_discarded_signature_lapses(protokoll, ohne_folge):
    p, db = protokoll, protokoll["db"]
    _answer(p, "dachflaechen", [p["areas"]["Nord"]])
    assert _sign_ag(p).status_code == 200
    s1 = _sig(p)
    db.get(RoofArea, p["areas"]["Nord"]).archived = True
    db.commit()
    assert _nachholen(p).status_code == 409  # Zeile "ausstehend"
    assert _discard_signature(p, s1.id).status_code == 200  # keine Abnahme -> verwerfen geht
    run_checklist_follow_ups(db, p["c"]["id"])
    rows = _rows(db, p["c"]["id"])
    assert {k: r.status for k, r in rows.items()} == {f"{FOLGE}#{s1.id}": "entfallen"}
    [folge] = list_follow_ups(db, p["c"]["id"])
    assert folge["status_label"] == "entfallen (Unterschrift verworfen)"
    with pytest.raises(SignatureNotValid):
        acceptance_from_protocol(db, p["c"]["id"], signature_id=s1.id)
    assert _acceptances(db) == []


def test_changed_protocol_after_the_signature_blocks_the_acceptance(protokoll, ohne_folge):
    p, db = protokoll, protokoll["db"]
    assert _sign_ag(p).status_code == 200
    db.execute(text("UPDATE checklist_answers SET value_text = 'jemand anderes' WHERE field_key = :k"),
               {"k": A + "teilnehmer"})
    db.commit()
    r = _nachholen(p)
    assert r.status_code == 409 and "passt nicht mehr zu ihrer Prüfsumme" in r.json()["detail"], r.text
    assert _acceptances(db) == []


def test_no_new_defects_at_an_acceptance_from_the_protocol(protokoll):
    p, db = protokoll, protokoll["db"]
    assert _sign_ag(p).status_code == 200
    [a] = _acceptances(db)
    r = p["client"].post(f"/api/order-acceptances/{a.id}/defects", data={"data": json.dumps({"description": "neu"})})
    assert r.status_code == 409 and "stammt aus dem Abnahmeprotokoll" in r.json()["detail"], r.text
    options = p["client"].get(f"/api/order-acceptances/{a.id}/defect-options").json()
    assert options["allowed"] is False and "Abnahmeprotokoll" in options["not_allowed_text"]


def test_monteur_has_no_access(protokoll):
    p = protokoll
    assert p["field"].get(f"/api/orders/{p['order_id']}/pending-protocol-acceptances").status_code == 403
    assert p["field"].post(f"/api/checklists/{p['c']['id']}/acceptance-from-protocol").status_code == 403


# ---------------------------------------------------------------------------
# Prüfsumme und Verweis
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("spalte, wert", [
    ("protocol_seal_sha256", "'0000'"), ("checklist_attachment_id", "NULL"), ("declared_by_person", "'Jemand'"),
], ids=["siegel", "unterschrift", "person"])
def test_attack_protocol_reference_changed_past_the_orm(protokoll, spalte, wert):
    p, db = protokoll, protokoll["db"]
    assert _sign_ag(p).status_code == 200
    [a] = _acceptances(db)
    db.execute(text(f"UPDATE order_acceptances SET {spalte} = {wert} WHERE id = :i"), {"i": a.id})
    db.commit()
    eintrag = _liste(p)[a.id]
    assert eintrag["intact"] is False and "Inhalt weicht von seiner Prüfsumme ab" in eintrag["check"]["text"]


def test_attack_signature_checksum_changed_breaks_the_reference(protokoll):
    p, db = protokoll, protokoll["db"]
    assert _sign_ag(p).status_code == 200
    [a] = _acceptances(db)
    db.execute(text("UPDATE checklist_attachments SET content_sha256 = 'anders' WHERE id = :i"), {"i": _sig(p).id})
    db.commit()
    eintrag = _liste(p)[a.id]
    assert eintrag["protocol"]["check"] == "abweichend" and "Verweis auf das Abnahmeprotokoll weicht ab" in eintrag["check"]["text"]


def test_older_formats_keep_their_checksum_and_a_set_reference_changes_them(protokoll, monkeypatch, router_test_client):
    """Fassung 2 (bis 1.8.62): Inhalt ohne Verweis -- gültig; am ORM vorbei ein Verweis gesetzt: weicht ab."""
    from tests.test_v349_abnahme_und_gewaehrleistung import _erfassen

    p, db = protokoll, protokoll["db"]
    buero = router_test_client(db, acceptances_router.router, role="buero_auftrag")
    monkeypatch.setattr(acceptances_module, "CHECKSUM_FORMAT", 2)
    a = _erfassen(buero, p["order_id"]).json()
    monkeypatch.setattr(acceptances_module, "CHECKSUM_FORMAT", 3)
    row = db.get(OrderAcceptance, a["id"])
    assert row.checksum_format == 2 and "protocol" not in acceptances_module.acceptance_content(row)
    assert _liste(p)[a["id"]]["intact"] is True
    db.execute(text("UPDATE order_acceptances SET declared_by_person = 'Jemand' WHERE id = :i"), {"i": a["id"]})
    db.commit()
    assert _liste(p)[a["id"]]["intact"] is False


def test_manual_acceptance_is_current_format_without_reference(protokoll, router_test_client):
    """Von Hand erfasst: aktuelles Prüfsummenformat (seit 1.8.67: 4), ohne Verweis aufs Protokoll."""
    from tests.test_v349_abnahme_und_gewaehrleistung import _erfassen

    p, db = protokoll, protokoll["db"]
    buero = router_test_client(db, acceptances_router.router, role="buero_auftrag")
    a = _erfassen(buero, p["order_id"]).json()
    row = db.get(OrderAcceptance, a["id"])
    content = acceptances_module.acceptance_content(row)
    assert (row.checksum_format, content["protocol"], content["declared_by_person"], a["from_protocol"], a["protocol"]) == (
        4, None, None, False, None)
    # förmlich ohne Beleg bleibt von Hand abgelehnt -- das Protokoll ist nur über die Folge der Nachweis
    r = buero.post(f"/api/orders/{p['order_id']}/acceptances", data={"data": json.dumps({
        "kind": "foermlich", "accepted_on": berlin_today().isoformat(), "scope": "gesamt", "result": "verweigert",
        "declared_by": "auftraggeber"})})
    assert r.status_code == 400 and "Protokoll der förmlichen Abnahme als Beleg" in r.json()["detail"]


# ---------------------------------------------------------------------------
# Seite, Migration
# ---------------------------------------------------------------------------

def test_order_page_shows_pending_hint_proof_and_no_defect_button():
    page = (ROOT / "app" / "templates" / "_abnahme.html").read_text(encoding="utf-8")
    assert "pending-protocol-acceptances" in page and "acceptance-from-protocol" in page and "Abnahme jetzt anlegen" in page
    assert "data-protocol-proof" in page and "dq.can_add" in page and "declared_by_person" in page
    assert "Eine neue Abnahme aus diesem Protokoll entsteht nur mit einer neuen Unterschrift" in page
    checklist = (ROOT / "app" / "templates" / "checklist.html").read_text(encoding="utf-8")
    assert "r.target_url" in checklist and "r.status==='ausstehend'||r.status==='modul_aus'" in checklist


def test_migration_adds_columns_and_refuses_downgrade_with_protocol_acceptances(protokoll):
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    path = next((ROOT / "alembic" / "versions").glob("*_abnahme_aus_protokoll.py"))
    spec = importlib.util.spec_from_file_location("mig_abnahme_aus_protokoll", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    p = protokoll
    assert _sign_ag(p).status_code == 200
    engine = p["db"].get_bind()
    with engine.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            with pytest.raises(RuntimeError, match="Downgrade verweigert: 1 Abnahmen stammen aus einem Abnahmeprotokoll"):
                module.downgrade()
    columns = {c["name"] for c in inspect(engine).get_columns("order_acceptances")}
    assert {"checklist_id", "checklist_attachment_id", "protocol_seal_sha256", "declared_by_person",
            "declared_by_function"} <= columns


# ---------------------------------------------------------------------------
# PostgreSQL: gleichzeitig
# ---------------------------------------------------------------------------

@pytest.fixture
def pg(monkeypatch, tmp_path):
    if not PG_TEST_DATABASE_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    from tests.test_v349_abnahme_und_gewaehrleistung import _welt as welt_bauen
    import app.project_participants as participants_module

    monkeypatch.setattr(acceptances_module, "ACCEPTANCE_FILE_ROOT", tmp_path / "abnahmen")
    monkeypatch.setattr(participants_module, "POWER_OF_ATTORNEY_ROOT", tmp_path / "vollmachten")
    monkeypatch.setattr(checklists_module, "CHECKLIST_ROOT", tmp_path / "checklisten")
    monkeypatch.setattr(follow_ups_module, "run_follow_ups_after_signature", lambda *a, **k: None)
    schema = f"pgtest_aus_protokoll_{uuid.uuid4().hex[:8]}"
    admin = create_engine(PG_TEST_DATABASE_URL)
    with admin.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
    engine = create_engine(PG_TEST_DATABASE_URL, pool_size=6,
                           connect_args={"options": f"-csearch_path={schema}", "application_name": schema})
    try:
        Base.metadata.create_all(engine)
        from app.grunddaten import anlegen

        Session = sessionmaker(bind=engine)
        setup = Session()
        try:
            anlegen(setup)
            setup.commit()
            w = welt_bauen(setup)
            tpl = _vorlage(setup)
            c = checklists_module.create_checklist(setup, template_id=tpl["id"], context_type="auftrag",
                                                   order_id=w["order_id"])
            f = {x["field_key"].removeprefix(A): x["id"] for x in c["fields"]}
            for key, value in (("teilnehmer", "alle"), ("umfang", "gesamt"), ("ergebnis", "abgenommen"),
                               ("vorbehalt_maengel", "ja"), ("vorbehalt_vertragsstrafe", "nein")):
                checklists_module.save_answer(setup, c["id"], f[key], value)
            defect = create_protocol_defect(setup, c["id"], {"description": "Attika undicht"}, [], user_id=None,
                                            user_name="x")
            checklists_module.add_attachment(setup, c["id"], f[AG], SIGNATUR, signer_person="Herbert Halle")
            sig_id = setup.scalar(select(ChecklistAttachment.id).where(ChecklistAttachment.kind == "unterschrift"))
        finally:
            setup.close()
        yield Session, {"checklist_id": c["id"], "f": f, "defect_id": defect.id, "signature_id": sig_id}
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
    result = {}

    def run():
        try:
            result["result"] = action(holder)
        except Exception as exc:  # noqa: BLE001
            result["result"] = exc
    thread = threading.Thread(target=run)
    thread.start()
    return holder, release, thread, result


def _timed(fn) -> dict:
    start, done = time.monotonic(), {}
    try:
        done["result"] = fn()
    except Exception as exc:  # noqa: BLE001
        done["result"] = exc
    done["seconds"] = time.monotonic() - start
    return done


def _run(Session, first, second):
    ready = threading.Event()
    holder, release, thread, first_result = _held(Session, first, ready)
    assert ready.wait(timeout=10)
    result = {}
    other = threading.Thread(target=lambda: result.update(_timed(lambda: second(Session()))))
    other.start()
    time.sleep(1.0)
    release.set()
    other.join(timeout=30)
    thread.join(timeout=30)
    holder.close()
    return first_result.get("result"), result


def _anlegen(session, w):
    return acceptance_from_protocol(session, w["checklist_id"], signature_id=w["signature_id"], user_name="Olga")


def _verwerfen_unterschrift(session, w):
    return checklists_module.discard_signatures(session, w["checklist_id"], signature_id=w["signature_id"],
                                                reason="neu unterschreiben")


def _count(Session):
    s = Session()
    try:
        return s.scalars(select(OrderAcceptance)).all(), s.scalar(select(Defect.acceptance_id))
    finally:
        s.close()


def test_postgresql_concurrent_follow_ups_give_one_acceptance(pg):
    Session, w = pg
    first, second = _run(Session, lambda s: _anlegen(s, w).id, lambda s: _anlegen(s, w).id)
    assert not isinstance(first, Exception) and second["seconds"] >= 0.9, (first, second)
    assert second["result"] == first
    acceptances, defect_acceptance = _count(Session)
    assert [a.id for a in acceptances] == [first] and defect_acceptance == first


def test_postgresql_discard_waits_for_the_follow_up_and_is_rejected(pg):
    Session, w = pg
    first, second = _run(Session, lambda s: _anlegen(s, w).id, lambda s: _verwerfen_unterschrift(s, w))
    assert not isinstance(first, Exception), first
    assert isinstance(second["result"], checklists_module.ChecklistLocked) and second["seconds"] >= 0.9, second
    s = Session()
    try:
        assert s.get(ChecklistAttachment, w["signature_id"]).discarded_at is None
    finally:
        s.close()


def test_postgresql_follow_up_waits_for_the_discard_and_creates_nothing(pg):
    Session, w = pg
    first, second = _run(Session, lambda s: _verwerfen_unterschrift(s, w), lambda s: _anlegen(s, w))
    assert not isinstance(first, Exception), first
    assert isinstance(second["result"], SignatureNotValid) and second["seconds"] >= 0.9, second
    acceptances, defect_acceptance = _count(Session)
    assert acceptances == [] and defect_acceptance is None


def test_postgresql_new_signature_after_discarded_acceptance(pg):
    Session, w = pg
    s = Session()
    try:
        a1 = _anlegen(s, w).id
        acceptances_module.discard_acceptance(s, s.get(OrderAcceptance, a1), reason="falsch", user_id=None,
                                              user_name="x")
        _verwerfen_unterschrift(s, w)
        checklists_module.add_attachment(s, w["checklist_id"], w["f"][AG], SIGNATUR, signer_person="Hanna Halle")
        s2 = s.scalar(select(ChecklistAttachment.id).where(ChecklistAttachment.kind == "unterschrift",
                                                          ChecklistAttachment.discarded_at.is_(None)))
        a2 = acceptance_from_protocol(s, w["checklist_id"], signature_id=s2, user_name="Olga").id
        assert acceptance_from_protocol(s, w["checklist_id"], signature_id=s2).id == a2
    finally:
        s.close()
    acceptances, defect_acceptance = _count(Session)
    assert [a.id for a in acceptances] == [a1, a2] and defect_acceptance == a2
