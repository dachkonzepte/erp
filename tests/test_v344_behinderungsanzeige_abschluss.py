"""Version 1.8.41 -- Stufe 2b, Runde 2b-3 Teil 3: Behinderungsanzeige abschließen (app/email_dispatch.py,
app/notice_letters.py, app/notice_letter_pdf.py, app/checklists.py, app/checklist_follow_ups.py,
app/project_participants.py, Migration *_versandergebnis_empfaenger_gegenstandslos.py;
docs/archiv/vertragsgrundlage-und-vertrag.md, "Umsetzung 1.8.41").

Geprüft:
1. Versandprotokoll für jedes Dokument: "Empfang bestätigt am" (Datum, Notiz, optional Beleg) und "unzustellbar"
   (Datum, Pflicht-Notiz) -- einmal je gesendetem Eintrag, nie für Aufgaben-Mails, Datum weder in der Zukunft noch vor
   dem Versand, unveränderlich, gleichzeitig genau einer; eine unzustellbare Behinderungsanzeige öffnet die Aufgabe
   "versenden" wieder, solange sie auf keinem anderen Weg ankam.
2. "Zustellung nachtragen" mit Empfängerauswahl (Auftraggeber, Beteiligte auch ohne E-Mail); die Vollmacht eines
   gewählten Empfangsbevollmächtigten wird eingefroren; eine Kopie nur an Beteiligte erledigt nichts.
3. Anzeige der Wiederaufnahme: "i. A." und das Büro-Konto, kein Unterschriftsbild, nicht die Monteurin.
4. Zeitstrahl: bekannt seit → Meldung unterschrieben → versendet, mit Abstand.
5. "Als gegenstandslos abschließen": nur Büro, Begründung Pflicht, Beleg mit Prüfsumme, fort aus offenen Listen,
   Folge-Aufgabe erledigt, keine Folgen und keine Briefe mehr.
6. Kundenwechsel: ist der neue Kunde schon Beteiligter, 409.
Monteur 403 an jedem neuen Endpunkt; Migration."""

import hashlib
import importlib.util
import json
import uuid
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, select, text, update

from app.berlin_time import BERLIN, berlin_today
from app.checklist_follow_ups import list_checklists_with_open_follow_ups, run_checklist_follow_ups
from app.contacts import linked_contact
from app.database import Base
from app.email_dispatch import record_dispatch_outcome
from app.models import (
    ArchiveImmutableError, AuditLog, Checklist, ChecklistAttachment, Customer, DispatchAuthorization,
    DispatchOutcome, EmailDispatch, EnabledModule, Project, SentDocument, Task,
)
from app.notice_letters import gap_text, letter_was_sent
from app.project_participants import add_participant, store_power_of_attorney
from app.routers.checklists import router as checklists_router
from app.routers.email_dispatches import router as dispatches_router
from app.routers.notice_letters import router as notice_router
from app.routers.projects import router as projects_router
from tests.test_v305_checklist_filling import _client, world  # noqa: F401 -- Fixture
from tests.test_v321_email_dispatch import FakeSMTP
from tests.test_v325_contract_basis import pdf_text
from tests.test_v341_behinderungsanzeige import B, _answer, _notice, _report, _send_tasks, _sign, _start, bworld  # noqa: F401
from tests.test_v343_behinderungsanzeige_versand import (  # noqa: F401 -- Fixture
    NOTICE, RESUME, _archive_bytes, _kind, _letters, _office, _participant, _pdf_bytes, _send, _signed,
    _state, _wegfall, nworld,
)

VERSIONS = Path(__file__).resolve().parent.parent.joinpath("alembic", "versions")


def _outcome(client, dispatch_id, outcome, *, on=None, note="", receipt=None):
    files = {"receipt": receipt} if receipt else None
    return client.post(f"/api/email-dispatches/{dispatch_id}/outcome",
                       data={"outcome": outcome, "outcome_on": str(on or berlin_today()), "note": note}, files=files)


def _manual(client, kind, document_id, *, to_client=False, participant_ids=(), recipient="", note="Einschreiben RR 1",
            on=None):
    data = {"document_type": kind, "document_id": document_id, "channel": "einschreiben",
            "delivered_on": str(on or berlin_today()), "note": note, "recipient": recipient,
            "to_client": "true" if to_client else "false", "dispatch_key": f"manuell-{uuid.uuid4().hex}"}
    if participant_ids:
        data["participant_ids"] = [str(p) for p in participant_ids]
    return client.post("/api/email-dispatches/manual", data=data)


def _items(client, kind, document_id) -> list[dict]:
    res = client.get(f"/api/email-dispatches?document_type={kind}&document_id={document_id}")
    assert res.status_code == 200, res.text
    return res.json()["items"]


def _send_task(db, c):
    return next(t for t in _send_tasks(db) if t.source_url == f"/checklisten/{c['id']}")


def _dispatch_row(db, **values) -> EmailDispatch:
    row = EmailDispatch(dispatch_key=f"test-{uuid.uuid4().hex}", message_ref=str(uuid.uuid4()), channel="smtp",
                        to_recipients="x@example.com", subject="Test", created_at=datetime.utcnow(),
                        created_by_name="Test", **values)
    db.add(row)
    db.commit()
    return row


# --- Punkt 1: Empfang bestätigt / unzustellbar --------------------------------------------------

def test_receipt_confirmed_with_date_note_and_receipt_exactly_once(nworld, router_test_client):
    db = nworld["db"]
    office = _office(nworld, router_test_client)
    c = _signed(nworld, router_test_client)
    sent = _send(office, c)
    assert sent.status_code == 200, sent.text
    dispatch_id = sent.json()["id"]
    assert sent.json()["can_record_outcome"] is True and sent.json()["outcome"] is None
    receipt = _pdf_bytes(b"Rueckschein")
    res = _outcome(office, dispatch_id, "empfangen", note="Lesebestätigung 14:02", receipt=("r.pdf", receipt, "application/pdf"))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["outcome"]["outcome"] == "empfangen" and body["outcome"]["note"] == "Lesebestätigung 14:02"
    assert body["outcome"]["outcome_on"] == str(berlin_today()) and body["can_record_outcome"] is False
    doc = db.get(SentDocument, body["outcome"]["receipt_document"]["id"])
    assert _archive_bytes(doc) == receipt and (doc.document_type, doc.document_id) == (NOTICE, c["id"])
    # Im Versandverlauf und genau einmal: ein zweites Ergebnis -- auch das andere -- wird abgelehnt.
    [item] = _items(office, NOTICE, c["id"])
    assert item["outcome"]["outcome_label"] == "Empfang bestätigt"
    again = _outcome(office, dispatch_id, "unzustellbar", note="doch nicht")
    assert again.status_code == 409 and "bereits vermerkt" in again.json()["detail"]
    assert db.scalars(select(DispatchOutcome)).all()[0].outcome == "empfangen"
    audit = db.scalars(select(AuditLog).where(AuditLog.entity_type == "Versand", AuditLog.field_name == "outcome")).all()
    assert len(audit) == 1 and "Empfang bestätigt am" in audit[0].new_value and "mit Beleg" in audit[0].new_value
    # Empfang ändert an der Aufgabe nichts (sie ist nach dem Versand erledigt und bleibt es).
    assert _send_task(db, c).status == "erledigt"


def test_outcome_rules_date_note_status_and_document_types(nworld, router_test_client):
    db = nworld["db"]
    office = _office(nworld, router_test_client)
    c = _signed(nworld, router_test_client)
    dispatch_id = _send(office, c).json()["id"]
    cases = (
        (dict(outcome="unzustellbar", note=""), 400, "Notiz"),
        (dict(outcome="empfangen", on=berlin_today() + timedelta(days=1)), 400, "Zukunft"),
        (dict(outcome="empfangen", on=berlin_today() - timedelta(days=1)), 400, "vor dem Versand"),
        (dict(outcome="gelesen"), 400, "wählen"),
    )
    for kwargs, status, word in cases:
        res = _outcome(office, dispatch_id, **kwargs)
        assert res.status_code == status and word in res.json()["detail"], (kwargs, res.text)
    html = ("x.pdf", b"<html><script>alert(1)</script></html>", "application/pdf")
    assert _outcome(office, dispatch_id, "empfangen", receipt=html).status_code == 400
    # Nur ein gesendeter Eintrag; Aufgaben-Benachrichtigungen haben kein Ergebnis (auch nicht für Admins).
    failed = _dispatch_row(db, status="fehlgeschlagen", document_type=NOTICE, document_id=c["id"])
    res = _outcome(office, failed.id, "unzustellbar", note="Rückläufer")
    assert res.status_code == 409 and "gesendeten" in res.json()["detail"]
    task_mail = _dispatch_row(db, status="gesendet", document_type="aufgabe", document_id=1)
    admin = _office(nworld, router_test_client, role="admin")
    assert _outcome(admin, task_mail.id, "empfangen").status_code == 404
    assert db.scalars(select(DispatchOutcome)).all() == []
    # Für jedes Dokument: eine nachgetragene Zustellung des Auftrags -- unzustellbar mit Datum ab der Zustellung.
    order = nworld["orders"]["mine"]
    day = berlin_today() - timedelta(days=3)
    manual = _manual(office, "auftrag", order.id, to_client=True, on=day)
    assert manual.status_code == 200, manual.text
    assert _outcome(office, manual.json()["id"], "unzustellbar", on=day - timedelta(days=1), note="zu früh").status_code == 400
    res = _outcome(office, manual.json()["id"], "unzustellbar", on=day, note="Annahme verweigert")
    assert res.status_code == 200 and res.json()["outcome"]["outcome"] == "unzustellbar"


def test_simultaneous_outcomes_make_exactly_one(nworld, router_test_client, monkeypatch):
    """Beide Anfragen haben "noch kein Ergebnis" gelesen (Vorabprüfung ausgehebelt): der UNIQUE-Schlüssel lässt genau
    einen Vermerk zu, der zweite bekommt 409."""
    db = nworld["db"]
    office = _office(nworld, router_test_client)
    c = _signed(nworld, router_test_client)
    dispatch_id = _send(office, c).json()["id"]
    record_dispatch_outcome(db, dispatch_id, outcome="empfangen", outcome_on=berlin_today(), note=None,
                            user_id=None, user_name="Erste")
    original = db.scalar

    def stale_read(statement, *args, **kwargs):
        if "dispatch_outcomes" in str(statement):
            return None  # liest wie vor dem ersten Vermerk
        return original(statement, *args, **kwargs)

    monkeypatch.setattr(db, "scalar", stale_read)
    from app.email_dispatch import DispatchConflict
    with pytest.raises(DispatchConflict, match="inzwischen"):
        record_dispatch_outcome(db, dispatch_id, outcome="unzustellbar", outcome_on=berlin_today(), note="Zweite",
                                user_id=None, user_name="Zweite")
    monkeypatch.undo()
    assert [(o.outcome, o.created_by_name) for o in db.scalars(select(DispatchOutcome))] == [("empfangen", "Erste")]


def test_outcome_is_immutable(nworld, router_test_client):
    db = nworld["db"]
    office = _office(nworld, router_test_client)
    c = _signed(nworld, router_test_client)
    dispatch_id = _send(office, c).json()["id"]
    assert _outcome(office, dispatch_id, "unzustellbar", note="Rückläufer").status_code == 200
    row = db.scalars(select(DispatchOutcome)).one()
    row.note = "geändert"
    with pytest.raises(ArchiveImmutableError):
        db.flush()
    db.rollback()
    with pytest.raises(ArchiveImmutableError):
        db.delete(db.get(DispatchOutcome, row.id))
        db.flush()
    db.rollback()


def test_undeliverable_notice_reopens_the_send_task_until_it_arrives(nworld, router_test_client):
    db = nworld["db"]
    office = _office(nworld, router_test_client)
    c = _signed(nworld, router_test_client)
    first = _send(office, c).json()
    task = _send_task(db, c)
    assert task.status == "erledigt" and letter_was_sent(db, NOTICE, c["id"])
    assert _outcome(office, first["id"], "unzustellbar", note="Postfach existiert nicht").status_code == 200
    db.expire_all()
    task = db.get(Task, task.id)
    assert task.status == "offen" and task.completed_at is None
    kind = _kind(_state(office, c))
    assert (kind["status"], kind["sent"]) == ("unzustellbar", False)
    assert not letter_was_sent(db, NOTICE, c["id"])
    # Erneut zugestellt (Einschreiben an den Auftraggeber): wieder erledigt, "versendet".
    assert _manual(office, NOTICE, c["id"], to_client=True).status_code == 200
    db.expire_all()
    assert db.get(Task, task.id).status == "erledigt"
    assert _kind(_state(office, c))["status"] == "versendet"
    # Ein zweiter Eintrag unzustellbar, der andere kam an: die Aufgabe bleibt erledigt.
    second = _send(office, c).json()
    assert _outcome(office, second["id"], "unzustellbar", note="Rückläufer").status_code == 200
    db.expire_all()
    assert db.get(Task, task.id).status == "erledigt"


# --- Punkt 2: Empfängerauswahl beim Nachtragen ---------------------------------------------------

def test_recipient_choice_lists_client_and_participants_even_without_email(nworld, router_test_client):
    db = nworld["db"]
    office = _office(nworld, router_test_client)
    _participant(db, nworld, name="Architekt", email="arch@example.com")
    _participant(db, nworld, name="Gutachter ohne Mail", email=None, role="sachverstaendiger", copy=False, authorized=True)
    c = _signed(nworld, router_test_client)
    res = office.get(f"/api/email-dispatches/delivery-recipients?document_type={NOTICE}&document_id={c['id']}")
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["client"]["name"] == "Herr Dr. Max Muster" and data["client"]["address"] == "Kundenweg 3, 50667 Köln"
    assert [(p["name"], p["role_label"], p["email"], p["authorized"]) for p in data["participants"]] == [
        ("Architekt", "Architekt/Planer", "arch@example.com", False),
        ("Gutachter ohne Mail", "Sachverständiger/Gutachter", None, True)]
    # Auch für andere Dokumentarten (hier: der Auftrag), über das Projekt.
    other = office.get(f"/api/email-dispatches/delivery-recipients?document_type=auftrag&document_id={nworld['orders']['mine'].id}")
    assert [p["name"] for p in other.json()["participants"]] == ["Architekt", "Gutachter ohne Mail"]
    assert office.get("/api/email-dispatches/delivery-recipients?document_type=auftrag&document_id=999").status_code == 404


def test_delivery_to_authorized_participant_without_email_freezes_the_power_of_attorney(nworld, router_test_client):
    db = nworld["db"]
    office = _office(nworld, router_test_client)
    poa = _pdf_bytes(b"Vollmacht Gutachter")
    expert = _participant(db, nworld, name="Gutachter", email=None, role="sachverstaendiger", copy=False, authorized=True)
    store_power_of_attorney(db, expert, filename="vollmacht.pdf", data=poa, user_name="Olga")
    copy = _participant(db, nworld, name="Architekt", email="arch@example.com")
    c = _signed(nworld, router_test_client)
    res = _manual(office, NOTICE, c["id"], participant_ids=[expert.id, copy.id], recipient="Büro Süd")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["to_recipients"] == "Gutachter (Sachverständiger/Gutachter); Architekt (Architekt/Planer); Büro Süd"
    assert body["delivered_to_client"] is False
    [auth] = body["authorizations"]
    assert (auth["contact_name"], auth["recipient_email"]) == ("Gutachter", None)
    row = db.scalars(select(DispatchAuthorization)).one()
    assert _archive_bytes(row.sent_document) == poa and row.poa_sha256 == hashlib.sha256(poa).hexdigest()
    assert (row.sent_document.document_type, row.sent_document.document_id) == (NOTICE, c["id"])
    # An einen Empfangsbevollmächtigten zugestellt: das gilt als Anzeige an den Auftraggeber.
    assert _send_task(db, c).status == "erledigt" and letter_was_sent(db, NOTICE, c["id"])
    # Ersetzen der Vollmacht ändert die eingefrorene Kopie nicht.
    store_power_of_attorney(db, db.get(type(expert), expert.id), filename="neu.pdf", data=_pdf_bytes(b"neu"), user_name="Olga")
    assert _archive_bytes(row.sent_document) == poa
    # Für jede Dokumentart: der Auftrag per Bote an den Bevollmächtigten.
    res = _manual(office, "auftrag", nworld["orders"]["mine"].id, participant_ids=[expert.id])
    assert res.status_code == 200 and res.json()["authorizations"][0]["sent_document"]["filename"].startswith("Vollmacht")


def test_copy_only_to_participants_does_not_count_as_notice_to_the_client(nworld, router_test_client):
    db = nworld["db"]
    office = _office(nworld, router_test_client)
    arch = _participant(db, nworld, name="Architekt ohne Mail", email=None)
    c = _signed(nworld, router_test_client)
    res = _manual(office, NOTICE, c["id"], participant_ids=[arch.id], note="Kopie per Post")
    assert res.status_code == 200 and res.json()["delivered_to_client"] is False
    assert _send_task(db, c).status == "offen" and not letter_was_sent(db, NOTICE, c["id"])
    assert _kind(_state(office, c))["status"] == "bereit"
    res = _manual(office, NOTICE, c["id"], to_client=True, participant_ids=[arch.id])
    assert res.status_code == 200 and res.json()["to_recipients"] == "Herr Dr. Max Muster (Auftraggeber); Architekt ohne Mail (Architekt/Planer)"
    assert _send_task(db, c).status == "erledigt"


def test_recipient_choice_only_participants_of_this_project(nworld, router_test_client):
    db = nworld["db"]
    office = _office(nworld, router_test_client)
    c = _signed(nworld, router_test_client)
    other_project = db.get(Project, nworld["orders"]["foreign"].project_id)
    foreign = add_participant(db, other_project, linked_contact(db, customer=db.get(Customer, _new_customer(db).id)),
                              role="eigentuemer")
    res = _manual(office, NOTICE, c["id"], participant_ids=[foreign.id])
    assert res.status_code == 400 and "gehört nicht zu diesem Projekt" in res.json()["detail"]
    assert db.scalars(select(EmailDispatch)).all() == []


# --- Punkt 3: Wiederaufnahme "i. A." --------------------------------------------------------------

def test_resumption_letter_is_signed_i_a_by_the_office_account_not_by_the_wegfall_signer(nworld, router_test_client):
    db = nworld["db"]
    office = _office(nworld, router_test_client)
    c = _signed(nworld, router_test_client)
    assert _send(office, c).status_code == 200
    _wegfall(nworld, router_test_client, c)
    assert "i. A." in _kind(_state(office, c), RESUME)["signoff_text"]
    preview = office.get(f"/api/checklists/{c['id']}/notice-letters/{RESUME}/preview")
    assert preview.status_code == 200 and "i. A. Buero_auftrag" in pdf_text(preview.content)
    assert _send(office, c, RESUME).status_code == 200
    [letter] = _letters(db, RESUME)
    content = json.loads(letter.content)
    assert content["signoff"] == {"mode": "i_a", "name": "Buero_auftrag"}
    assert content["signature"]["signer_name"] == "Anna Alpha"  # interner Bezug bleibt im eingefrorenen Inhalt
    pdf = _archive_bytes(letter.sent_document)
    text_ = pdf_text(pdf)
    assert "i. A. Buero_auftrag" in text_ and "Anna Alpha" not in text_
    assert b"/Subtype /Image" not in pdf  # kein Unterschriftsbild (und keine Fotos in diesem Brief)
    # Die Behinderungsanzeige selbst trägt weiter die Unterschrift Büro.
    [notice] = _letters(db, NOTICE)
    assert json.loads(notice.content)["signoff"] is None
    notice_pdf = _archive_bytes(notice.sent_document)
    assert "Olga Office" in pdf_text(notice_pdf) and b"/Subtype /Image" in notice_pdf


# --- Punkt 4: Zeitstrahl -------------------------------------------------------------------------

def test_gap_text_in_hours_or_days():
    t = datetime(2026, 10, 2, 7, 45)
    cases = ((timedelta(minutes=20), "unter 1 Std."), (timedelta(hours=2, minutes=30), "2 Std."),
             (timedelta(hours=23, minutes=59), "23 Std."), (timedelta(hours=28), "1 Tag 4 Std."),
             (timedelta(days=2), "2 Tage"), (timedelta(hours=-3), "3 Std. vorher"))
    for delta, expected in cases:
        assert gap_text(t, t + delta)["text"] == expected, delta
    assert gap_text(t, t + timedelta(hours=20), date_only=True)["text"] == "1 Tag"
    assert gap_text(t, t + timedelta(hours=2), date_only=True)["text"] == "am selben Tag"
    assert gap_text(t, t - timedelta(days=3), date_only=True) == {"text": "3 Tage vorher", "minutes": None, "days": -3,
                                                                 "negative": True}


def _utc(local: datetime) -> datetime:
    """Ortszeit Europe/Berlin -> naive UTC, wie die Zeitstempel gespeichert werden (unabhängig von Sommer-/Winterzeit)."""
    return local.replace(tzinfo=BERLIN).astimezone(timezone.utc).replace(tzinfo=None)


def test_timeline_known_reported_sent_with_gaps(nworld, router_test_client):
    db = nworld["db"]
    office = _office(nworld, router_test_client)
    field, office_c = _client(nworld, router_test_client, "a"), _client(nworld, router_test_client, "office")
    # Vorgestern 07:45 bekannt, 10:15 Ortszeit gemeldet (2 Std. 30 Min.), gestern 14:15 versendet (1 Tag 4 Std.).
    day = berlin_today() - timedelta(days=2)
    reported = datetime.combine(day, time(10, 15))
    sent = datetime.combine(day + timedelta(days=1), time(14, 15))
    c = _start(nworld, field)
    for key, value in ((B + "bekannt_seit", f"{day}T07:45"), (B + "beschreibung", "Gerüst fehlt")):
        assert _answer(field, c, key, value).status_code == 200
    assert _sign(field, c, B + "unterschrift_meldung", "Anna Alpha").status_code == 200
    _notice(office_c, c)
    report_id = db.scalar(select(ChecklistAttachment.id).where(
        ChecklistAttachment.checklist_id == c["id"], ChecklistAttachment.kind == "unterschrift").order_by(ChecklistAttachment.id))
    # Nur der Zeitpunkt der Unterschrift wird zurückgedreht -- er gehört nicht zum versiegelten Inhalt.
    db.execute(text("UPDATE checklist_attachments SET created_at = :t WHERE id = :id"), {"t": _utc(reported), "id": report_id})
    db.commit()
    steps = _state(office, c)["timeline"]
    assert [(s["key"], s["at_local"]) for s in steps] == [
        ("bekannt_seit", f"{day}T07:45"), ("meldung", f"{day}T10:15"), ("versendet", None)]
    assert steps[1]["gap"]["text"] == "2 Std." and steps[2]["gap"] is None and "waiting" in steps[2]
    dispatch_id = _send(office, c).json()["id"]
    db.execute(text("UPDATE email_dispatches SET finished_at = :t WHERE id = :id"), {"t": _utc(sent), "id": dispatch_id})
    db.commit()
    steps = _state(office, c)["timeline"]
    assert (steps[2]["at_local"], steps[2]["gap"]["text"], steps[2]["channel"]) == (
        f"{day + timedelta(days=1)}T14:15", "1 Tag 4 Std.", "SMTP")
    assert "waiting" not in steps[2]
    # Unzustellbar: nicht mehr "versendet" -- der Zeitstrahl wartet wieder.
    assert _outcome(office, dispatch_id, "unzustellbar", note="Rückläufer", on=berlin_today()).status_code == 200
    steps = _state(office, c)["timeline"]
    assert steps[2]["at_local"] is None and "waiting" in steps[2]
    # Nachgetragen: nur der Tag zählt, Abstand in Kalendertagen.
    assert _manual(office, NOTICE, c["id"], to_client=True, on=day).status_code == 200
    steps = _state(office, c)["timeline"]
    assert (steps[2]["label"], steps[2]["at_local"], steps[2]["date_only"]) == ("Zugestellt", str(day), True)
    assert steps[2]["gap"]["text"] == "am selben Tag" and steps[2]["channel"] == "Einschreiben"


# --- Punkt 5: als gegenstandslos abschließen ---------------------------------------------------

def test_void_only_office_with_reason_sealed_and_out_of_open_lists(nworld, router_test_client):
    db = nworld["db"]
    field = _client(nworld, router_test_client, "a")
    office_c = _client(nworld, router_test_client, "office")
    c = _start(nworld, field)
    _report(field, c)  # nur die Meldung: Anzeige und Wegfall fehlen
    task = _send_task(db, c)
    assert task.status == "offen"
    assert field.post(f"/api/checklists/{c['id']}/void", json={"reason": "übliche Witterung"}).status_code == 403
    assert office_c.post(f"/api/checklists/{c['id']}/void", json={"reason": "  "}).status_code == 400
    assert c["id"] in [x["id"] for x in field.get("/api/checklists/mine").json()]
    res = office_c.post(f"/api/checklists/{c['id']}/void", json={"reason": "Übliche Witterung – keine Behinderung"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert (body["status"], body["void_reason"], body["voided_by_name"]) == (
        "gegenstandslos", "Übliche Witterung – keine Behinderung", "Buero_auftrag")
    assert body["completion_seal"]["status"] == "unveraendert" and body["missing_required"]
    assert body["can_void"] is False and body["can_sign"] is False and body["can_edit"] is False
    row = db.get(Checklist, c["id"])
    sealed = json.loads(row.sealed_content)
    assert (sealed["sealed_by"], sealed["void_reason"]) == ("gegenstandslos", "Übliche Witterung – keine Behinderung")
    assert row.content_sha256 == hashlib.sha256(row.sealed_content.encode("utf-8")).hexdigest()
    # Fort aus den offenen Listen (Monteur /mobil, Entwürfe), die offene Aufgabe erledigt.
    assert c["id"] not in [x["id"] for x in field.get("/api/checklists/mine").json()]
    assert c["id"] not in [x["id"] for x in office_c.get("/api/checklists?status=entwurf").json()]
    assert c["id"] in [x["id"] for x in office_c.get("/api/checklists?status=gegenstandslos").json()]
    db.expire_all()
    assert db.get(Task, task.id).status == "erledigt"
    # Bleibt als Beleg: PDF mit Begründung, Monteur sieht Status und Begründung an seiner Checkliste.
    pdf = office_c.get(f"/api/checklists/{c['id']}/pdf")
    assert pdf.status_code == 200 and "Übliche Witterung – keine Behinderung" in pdf_text(pdf.content)
    mine = field.get(f"/api/checklists/{c['id']}").json()
    assert (mine["status"], mine["void_reason"]) == ("gegenstandslos", "Übliche Witterung – keine Behinderung")
    # Unveränderlich danach; wiederholt (Doppelklick) ändert nichts.
    assert _answer(field, c, B + "beschreibung", "anders").status_code == 409
    assert office_c.post(f"/api/checklists/{c['id']}/complete").status_code == 409
    again = office_c.post(f"/api/checklists/{c['id']}/void", json={"reason": "andere Begründung"})
    assert again.status_code == 200 and again.json()["void_reason"] == "Übliche Witterung – keine Behinderung"
    assert db.scalars(select(AuditLog).where(AuditLog.entity_type == "Checkliste",
                                            AuditLog.field_name == "void_reason")).all()


def test_void_stops_follow_ups_letters_and_sending(nworld, router_test_client):
    db = nworld["db"]
    db.add(EnabledModule(module_key="aufgabenmanagement", enabled=False))
    db.commit()
    office = _office(nworld, router_test_client)
    office_c = _client(nworld, router_test_client, "office")
    c = _signed(nworld, router_test_client)  # Folge "versenden" bleibt "modul_aus"
    assert c["id"] in list_checklists_with_open_follow_ups(db)
    assert office_c.post(f"/api/checklists/{c['id']}/void", json={"reason": "keine Behinderung"}).status_code == 200
    db.execute(update(EnabledModule).where(EnabledModule.module_key == "aufgabenmanagement").values(enabled=True))
    db.commit()
    assert c["id"] not in list_checklists_with_open_follow_ups(db)
    assert run_checklist_follow_ups(db, c["id"]) == {"done": 0, "module_off": 0, "failed": 0}
    assert _send_tasks(db) == []
    base = f"/api/checklists/{c['id']}/notice-letters/{NOTICE}"
    for res in (_send(office, c), office.post(f"{base}/freeze"), office.get(f"{base}/preview")):
        assert res.status_code == 409 and "gegenstandslos" in res.json()["detail"], res.text
    assert FakeSMTP.sent == [] and _letters(db) == [] and _state(office, c)["voided"] is True
    # Ohne erstellten Brief lässt sich auch keine Zustellung nachtragen.
    assert _manual(office, NOTICE, c["id"], to_client=True).status_code == 400


def test_void_keeps_an_already_created_letter_deliverable(nworld, router_test_client):
    db = nworld["db"]
    office = _office(nworld, router_test_client)
    office_c = _client(nworld, router_test_client, "office")
    c = _signed(nworld, router_test_client)
    assert office.post(f"/api/checklists/{c['id']}/notice-letters/{NOTICE}/freeze").status_code == 200
    assert office_c.post(f"/api/checklists/{c['id']}/void", json={"reason": "Gerüst stand doch"}).status_code == 200
    assert _send(office, c).status_code == 409
    res = _manual(office, NOTICE, c["id"], to_client=True, note="vor dem Abschluss per Post")
    assert res.status_code == 200, res.text
    assert res.json()["sent_document"]["id"] == _letters(db)[0].sent_document_id


def test_void_only_for_obstruction_and_concern_notices_and_only_drafts(nworld, router_test_client):
    db = nworld["db"]
    office_c = _client(nworld, router_test_client, "office")
    general = office_c.post("/api/checklists", json={"template_id": nworld["order_tpl"]["id"], "context_type": "auftrag",
                                                     "order_id": nworld["orders"]["mine"].id}).json()
    res = office_c.post(f"/api/checklists/{general['id']}/void", json={"reason": "egal"})
    assert res.status_code == 400 and "Behinderungs- und Bedenkenanzeigen" in res.json()["detail"]
    # Bedenkenanzeige: die Fassung trägt den Zweck (hier gesetzt, die Startvorlage folgt in 2b-4).
    db.execute(text("UPDATE checklist_template_versions SET purpose = 'bedenkenanzeige' WHERE id = :v"),
               {"v": general["template_version_id"]})
    db.commit()
    concern = office_c.get(f"/api/checklists/{general['id']}").json()
    assert concern["voidable"] and concern["can_void"]
    assert office_c.post(f"/api/checklists/{general['id']}/void", json={"reason": "Bedenken ausgeräumt"}).status_code == 200
    # Ein schon abgeschlossener: 409 (Status hier direkt gesetzt -- die Vorlage hat Pflichtfelder).
    done = office_c.post("/api/checklists", json={"template_id": nworld["order_tpl"]["id"], "context_type": "auftrag",
                                                  "order_id": nworld["orders"]["mine"].id}).json()
    db.execute(text("UPDATE checklists SET status = 'abgeschlossen' WHERE id = :id"), {"id": done["id"]})
    db.commit()
    res = office_c.post(f"/api/checklists/{done['id']}/void", json={"reason": "zu spät"})
    assert res.status_code == 409 and "abgeschlossen" in res.json()["detail"]


def test_changed_void_reason_shows_in_the_completion_check(nworld, router_test_client):
    db = nworld["db"]
    office_c = _client(nworld, router_test_client, "office")
    c = _start(nworld, _client(nworld, router_test_client, "a"))
    assert office_c.post(f"/api/checklists/{c['id']}/void", json={"reason": "Witterung"}).status_code == 200
    db.execute(text("UPDATE checklists SET void_reason = 'Behinderung lag nie vor' WHERE id = :id"), {"id": c["id"]})
    db.commit()
    seal = office_c.get(f"/api/checklists/{c['id']}").json()["completion_seal"]
    assert seal["status"] == "abweichend" and "Begründung (gegenstandslos)" in seal["changed_fields"]


# --- Punkt 6: Kundenwechsel ----------------------------------------------------------------------

def _new_customer(db, name="Hausverwaltung Süd") -> Customer:
    customer = Customer(name=name, last_name=name)
    db.add(customer)
    db.commit()
    return customer


def test_client_change_refused_while_the_new_client_is_a_participant(nworld, router_test_client):
    db = nworld["db"]
    project = db.get(Project, nworld["orders"]["mine"].project_id)
    old_customer_id = project.customer_id
    manager = _new_customer(db)
    participant = add_participant(db, project, linked_contact(db, customer=manager), role="hausverwaltung")
    client = router_test_client(db, projects_router, role="buero_auftrag")
    body = {"customer_id": manager.id, "property_id": None, "name": project.name, "status": project.status,
            "description": project.description}
    res = client.put(f"/api/projects/{project.id}", json=body)
    assert res.status_code == 409, res.text
    assert "Hausverwaltung Süd" in res.json()["detail"] and "Hausverwaltung" in res.json()["detail"]
    db.expire_all()
    assert db.get(Project, project.id).customer_id == old_customer_id
    # Ein anderer neuer Kunde geht; nach dem Entfernen des Beteiligten auch dieser.
    other = _new_customer(db, "Neuer Bauherr")
    assert client.put(f"/api/projects/{project.id}", json={**body, "customer_id": other.id}).status_code == 200
    db.delete(db.get(type(participant), participant.id))
    db.commit()
    assert client.put(f"/api/projects/{project.id}", json=body).status_code == 200
    db.expire_all()
    assert db.get(Project, project.id).customer_id == manager.id
    # Derselbe Kunde (z. B. nur der Name geändert) prüft nichts.
    assert client.put(f"/api/projects/{project.id}", json={**body, "name": "Neu"}).status_code == 200


# --- Rechte -------------------------------------------------------------------------------------

def test_monteur_gets_403_at_every_new_endpoint(nworld, router_test_client):
    db = nworld["db"]
    office = _office(nworld, router_test_client)
    c = _signed(nworld, router_test_client)
    dispatch_id = _send(office, c).json()["id"]
    field = router_test_client(db, checklists_router, notice_router, dispatches_router, role="field",
                               employee_id=nworld["emps"]["a"].id)
    for res in (
        field.get(f"/api/email-dispatches/delivery-recipients?document_type={NOTICE}&document_id={c['id']}"),
        _outcome(field, dispatch_id, "empfangen"),
        _manual(field, NOTICE, c["id"], to_client=True),
        field.post(f"/api/checklists/{c['id']}/void", json={"reason": "keine Behinderung"}),
    ):
        assert res.status_code == 403, res.request.url
    assert db.scalars(select(DispatchOutcome)).all() == [] and db.get(Checklist, c["id"]).status == "entwurf"
    assert len(db.scalars(select(EmailDispatch)).all()) == 1


# --- Migration ----------------------------------------------------------------------------------

def _migration():
    path = next(VERSIONS.glob("*_versandergebnis_empfaenger_gegenstandslos.py"))
    spec = importlib.util.spec_from_file_location("migration_1841", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(engine, fn_name):
    module = _migration()
    with engine.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            getattr(module, fn_name)()


def test_migration_adds_the_columns_and_refuses_a_lossy_downgrade():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    _run(engine, "downgrade")  # leer: läuft
    columns = lambda table: {c["name"] for c in inspect(engine).get_columns(table)}  # noqa: E731
    assert "dispatch_outcomes" not in inspect(engine).get_table_names()
    assert "void_reason" not in columns("checklists") and "delivered_to_client" not in columns("email_dispatches")
    _run(engine, "upgrade")
    assert {"voided_at", "voided_by_user_id", "voided_by_name", "void_reason"} <= columns("checklists")
    assert "delivered_to_client" in columns("email_dispatches") and "dispatch_outcomes" in inspect(engine).get_table_names()
    nullable = {c["name"]: c["nullable"] for c in inspect(engine).get_columns("dispatch_authorizations")}
    assert nullable["recipient_email"] is True
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO email_dispatches (dispatch_key, message_ref, status, channel, document_type, "
                          "to_recipients, subject, created_at, created_by_name, delivered_to_client) VALUES "
                          "('k-12345678', 'r1', 'gesendet', 'einschreiben', 'auftrag', 'x', 'y', '2026-10-02 10:00:00', "
                          "'Test', TRUE)"))
    with pytest.raises(RuntimeError, match="Empfängerauswahl"):
        _run(engine, "downgrade")
    with engine.begin() as conn:
        conn.execute(text("UPDATE email_dispatches SET delivered_to_client = NULL"))
    _run(engine, "downgrade")
    _run(engine, "upgrade")
    assert "dispatch_outcomes" in inspect(engine).get_table_names()
