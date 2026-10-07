"""Version 1.8.67 -- Stufe 2c-2e, Punkte 2 und 3 (docs/archiv/abnahme-und-gewaehrleistung.md, "Umsetzung 1.8.67").

2. Versand des Abnahmeprotokolls über den Weg der Anzeigen (app/notice_letters.py, dieselben Funktionen): An fest der
   Auftraggeber, Prüfung auf abweichenden Kunden, CC vorbelegt mit "Kopie bei Anzeigen", Vollmacht eines empfangsbevollmächtigten
   Empfängers festgehalten, "Kopie an:" im PDF, versendet nur die jüngste gültige feste Fassung aus der Ablage, Zustellung
   nachtragen mit Empfängerauswahl.
3. Die Abnahme aus dem Protokoll verweist zusätzlich auf die feste Fassung ihrer Unterschrift (Prüfsummenformat 4).

Angriffe: Versand einer überholten Fassung (auch wenn das Verwerfen zwischen Prüfung und Versand fällt, auch gleichzeitig gegen
PostgreSQL), Empfänger über die API mitschicken, PDF nach der Unterschrift verändert, Monteur ruft Stand oder Versand ab, Verweis
der Abnahme am ORM vorbei geändert. Mails gehen nur an die Test-Attrappe (FakeSMTP), Adressen der eigenen Domain."""

import importlib.util
import json
import os
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import close_all_sessions, sessionmaker

import app.acceptance_protocol as protocol_module
import app.acceptances as acceptances_module
import app.checklist_follow_ups as follow_ups_module
import app.checklists as checklists_module
import app.protocol_dispatch as dispatch_module
from app.checklist_versions import versions_of
from app.database import Base
from app.models import (
    AuditLog, ChecklistVersion, Customer, DispatchAuthorization, EmailDispatch, OrderAcceptance, Project,
    ProjectParticipant, SentDocument,
)
from app.routers import acceptances as acceptances_router
from app.routers import defects as defects_router
from app.routers import notice_letters as notice_router
from app.routers.checklists import router as checklists_router
from app.routers.email_dispatches import router as dispatches_router
from app.sent_documents import read_sent_document
from tests.test_v321_email_dispatch import FakeSMTP, _attachment, _configure_smtp
from tests.test_v349_abnahme_und_gewaehrleistung import _welt, ablage, welt  # noqa: F401  (Fixtures)
from tests.test_v358_unterschrift_pruefung import SIGNATUR
from tests.test_v363_zweck_abnahme import _sig, _sign_ag, _vorlage
from tests.test_v365_abnahme_aus_protokoll import AN, _acceptances, _nachholen, _run, ohne_folge, protokoll  # noqa: F401
from tests.test_v366_protokoll_seite_und_pdf import _pdf_text
from tests.test_v368_feste_fassung import _sign_an, _verfaelschen, _versions

ROOT = Path(__file__).resolve().parent.parent
PG_TEST_DATABASE_URL = os.getenv("ERP_TEST_POSTGRES_URL")
AG_EMAIL = "auftraggeber@dachkonzepte.example"
ARCH_EMAIL = "architektin@dachkonzepte.example"
HV_EMAIL = "hausverwaltung@dachkonzepte.example"


@pytest.fixture
def versand(protokoll, router_test_client, monkeypatch):
    """Abnahmeprotokoll aus test_v365 (ein Mangel, Vorbehalt Mängel ja), Auftraggeber mit E-Mail, die Architektin mit "Kopie
    bei Anzeigen", die Hausverwaltung empfangsbevollmächtigt mit Vollmacht und ebenfalls "Kopie bei Anzeigen"; SMTP über die
    Attrappe."""
    p, db = protokoll, protokoll["db"]
    FakeSMTP.sent, FakeSMTP.fail, FakeSMTP.during_send = [], None, None
    monkeypatch.setattr("app.email_sending.smtplib.SMTP", FakeSMTP)
    _configure_smtp(db)
    project = db.get(Project, db.get(acceptances_module.Order, p["order_id"]).project_id)
    db.get(Customer, project.customer_id).email = AG_EMAIL
    for key, mail in (("architektin", ARCH_EMAIL), ("verwaltung", HV_EMAIL)):
        participant = db.get(ProjectParticipant, p[key])
        participant.copy_on_notices = True
        participant.contact.email = mail
    db.commit()
    routers = (checklists_router, notice_router.router, dispatches_router, defects_router.router, acceptances_router.router)
    p["buero"] = router_test_client(db, *routers, role="buero_auftrag", employee_id=p["office"].employee_id,
                                    user_id=p["office"].id, display_name="Olga Office")
    p["monteur"] = router_test_client(db, *routers, role="field")
    return p


def _state(p):
    r = p["buero"].get(f"/api/checklists/{p['c']['id']}/protocol-dispatch")
    assert r.status_code == 200, r.text
    return r.json()


def _send(p, key="protokoll-versand-0001", **payload):
    return p["buero"].post(f"/api/checklists/{p['c']['id']}/protocol-dispatch/send-email",
                           json={"dispatch_key": key, **payload})


def _manual(p, key="protokoll-zustellung-01", **extra):
    data = {"document_type": "checkliste", "document_id": str(p["c"]["id"]), "channel": "persoenlich",
            "delivered_on": "2026-10-01", "note": "bei der Abnahme übergeben", "dispatch_key": key, **extra}
    return p["buero"].post("/api/email-dispatches/manual", data=data)


def _dispatches(db):
    db.expire_all()
    return db.scalars(select(EmailDispatch).order_by(EmailDispatch.id)).all()


# ---------------------------------------------------------------------------
# Punkt 2: Versand über den Weg der Anzeigen
# ---------------------------------------------------------------------------

def test_protocol_waits_for_the_customer_signature(versand):
    p = versand
    s = _state(p)
    assert (s["ready"], s["status"], s["version"]) == (False, "wartet", None) and "Auftraggebers" in s["waiting_text"]
    r = _send(p, cc_email=None)
    assert r.status_code == 409, r.text
    r = _manual(p)
    assert r.status_code == 400 and "Abnahmeprotokoll" in r.json()["detail"], r.text
    assert FakeSMTP.sent == [] and _dispatches(p["db"]) == []


def test_send_goes_to_the_client_with_copies_and_the_archived_version(versand):
    """An der Auftraggeber, CC die Vorbelegung (beide "Kopie bei Anzeigen"), Anhang = die Fassung aus der Ablage (keine zweite
    Datei), die Vollmacht der Hausverwaltung festgehalten, "Kopie an:" im PDF, danach "versendet"."""
    p, db = versand, versand["db"]
    assert _sign_ag(p).status_code == 200
    [version] = _versions(db, p["c"]["id"])
    s = _state(p)
    assert (s["ready"], s["status"], s["version"]["version_no"], s["recipient"]["email"]) == (True, "bereit", 1, AG_EMAIL)
    assert s["cc_prefill"] == f"{ARCH_EMAIL}, {HV_EMAIL}"
    assert {c["name"] for c in s["version"]["copy_to"]} == {"Petra Plan", "HV Muster"}
    vorher = db.scalar(select(SentDocument.id).order_by(SentDocument.id.desc()))
    r = _send(p, cc_email=s["cc_prefill"])
    assert r.status_code == 200, r.text
    [mail] = FakeSMTP.sent
    assert mail["recipients"] == [AG_EMAIL, ARCH_EMAIL, HV_EMAIL]
    pdf = read_sent_document(version.sent_document)
    assert _attachment(mail["message"]) == pdf
    [row] = _dispatches(db)
    assert (row.document_type, row.document_id, row.sent_document_id, row.to_recipients) == (
        "checkliste", p["c"]["id"], version.sent_document_id, AG_EMAIL)
    assert row.subject == f"Abnahmeprotokoll – Auftrag {db.get(acceptances_module.Order, p['order_id']).order_number}"
    [vollmacht] = db.scalars(select(DispatchAuthorization).where(DispatchAuthorization.dispatch_id == row.id)).all()
    assert vollmacht.recipient_email == HV_EMAIL
    neu = db.scalars(select(SentDocument).where(SentDocument.id > vorher)).all()
    assert [d.sha256 for d in neu] == [vollmacht.sent_document.sha256]  # nur die Kopie der Vollmacht, kein zweites PDF
    text_ = " ".join(_pdf_text(pdf).split())
    assert "Kopie an: " in text_ and "Petra Plan" in text_ and "HV Muster" in text_
    assert _state(p)["status"] == "versendet"


def test_attack_recipient_sent_through_the_api_is_ignored(versand):
    """Eine mitgeschickte An-Adresse (in jeder Schreibweise) wird nicht beachtet -- die Mail geht nur an den Auftraggeber."""
    p = versand
    assert _sign_ag(p).status_code == 200
    r = _send(p, to_email="fremd@angreifer.example", to="fremd@angreifer.example", recipient="fremd@angreifer.example")
    assert r.status_code == 200, r.text
    [mail] = FakeSMTP.sent
    assert mail["recipients"] == [AG_EMAIL] and r.json()["to_recipients"] == AG_EMAIL


def test_attack_general_send_with_free_recipient_is_blocked_for_the_protocol(versand):
    p = versand
    assert _sign_ag(p).status_code == 200 and _sign_an(p).status_code == 200
    assert p["client"].post(f"/api/checklists/{p['c']['id']}/complete").status_code == 200
    r = p["buero"].post(f"/api/checklists/{p['c']['id']}/send-email",
                        json={"to_email": "fremd@angreifer.example", "dispatch_key": "checkliste-frei-0001"})
    assert r.status_code == 400 and "Protokoll an den Auftraggeber" in r.json()["detail"], r.text
    assert FakeSMTP.sent == []


def test_attack_superseded_version_is_never_sent(versand):
    """Auftraggeber (Fassung 1), Auftragnehmer (Fassung 2); die Unterschrift des Auftragnehmers verworfen -> versendet wird
    Fassung 1, nie die überholte 2. Umgekehrt (Auftragnehmer zuerst): nach dem Verwerfen gibt es keine gültige Fassung mit der
    Unterschrift des Auftraggebers -- Versand und Zustellung abgelehnt, bis eine neue Unterschrift Fassung 3 anlegt."""
    p, db = versand, versand["db"]
    assert _sign_ag(p).status_code == 200 and _sign_an(p).status_code == 200
    v1, v2 = _versions(db, p["c"]["id"])
    assert _state(p)["version"]["version_no"] == 2
    r = p["client"].post(f"/api/checklists/{p['c']['id']}/discard-signatures",
                         json={"signature_id": _sig(p, AN).id, "reason": "falsches Konto"})
    assert r.status_code == 200, r.text
    assert _state(p)["version"]["version_no"] == 1
    assert _send(p, cc_email=None).status_code == 200
    [mail] = FakeSMTP.sent
    assert _attachment(mail["message"]) == read_sent_document(v1.sent_document) != read_sent_document(v2.sent_document)


def test_attack_no_valid_version_with_the_customer_signature(versand):
    p, db = versand, versand["db"]
    assert _sign_an(p).status_code == 200 and _sign_ag(p).status_code == 200
    r = p["client"].post(f"/api/checklists/{p['c']['id']}/discard-signatures",
                         json={"signature_id": _sig(p, AN).id, "reason": "falsches Konto"})
    assert r.status_code == 200, r.text
    s = _state(p)
    assert (s["ready"], s["version"]) == (False, None) and "keine gültige feste Fassung" in s["waiting_text"]
    r = _send(p, cc_email=None)
    assert r.status_code == 409 and "keine gültige feste Fassung" in r.json()["detail"], r.text
    assert _manual(p).status_code == 400
    assert _sign_an(p).status_code == 200
    assert _state(p)["version"]["version_no"] == 3 and _send(p, key="protokoll-versand-0002").status_code == 200
    assert len(FakeSMTP.sent) == 1


def test_attack_discard_between_check_and_send_stops_before_sending(versand, monkeypatch):
    """Die Unterschrift des Auftragnehmers wird verworfen, nachdem der Versand die Fassung gewählt hat: die Prüfung vor dem
    Senden (unter der Zeilensperre) findet die überholte Fassung -- nichts geht hinaus, der Eintrag ist fehlgeschlagen."""
    p, db = versand, versand["db"]
    assert _sign_ag(p).status_code == 200 and _sign_an(p).status_code == 200
    an = _sig(p, AN).id
    original = dispatch_module._document

    def dazwischen(version):
        data = original(version)
        checklists_module.discard_signatures(db, p["c"]["id"], signature_id=an, reason="gleichzeitig verworfen")
        return data
    monkeypatch.setattr(dispatch_module, "_document", dazwischen)
    r = _send(p, cc_email=None)
    assert r.status_code == 400 and "überholt" in r.json()["detail"], r.text
    assert FakeSMTP.sent == [] and [d.status for d in _dispatches(db)] == ["fehlgeschlagen"]


def test_attack_pdf_changed_after_the_signature_is_not_sent(versand):
    p, db = versand, versand["db"]
    assert _sign_ag(p).status_code == 200
    [version] = _versions(db, p["c"]["id"])
    _verfaelschen(version.sent_document)
    r = _send(p, cc_email=None)
    assert r.status_code == 409 and "nicht mehr unversehrt" in r.json()["detail"], r.text
    r = _manual(p)
    assert r.status_code == 400 and "nicht mehr unversehrt" in r.json()["detail"], r.text
    assert FakeSMTP.sent == [] and _dispatches(db) == []


def test_customer_mismatch_needs_confirmation_and_is_recorded(versand):
    p, db = versand, versand["db"]
    assert _sign_ag(p).status_code == 200
    project = db.get(Project, db.get(acceptances_module.Order, p["order_id"]).project_id)
    db.get(Customer, project.customer_id).name = "Ganz Andere GmbH"
    db.commit()
    s = _state(p)
    assert s["customer_mismatch"] is not None
    r = _send(p, cc_email=None)
    assert r.status_code == 409 and "weicht vom Kunden laut Auftrag" in r.json()["detail"], r.text
    assert FakeSMTP.sent == []
    r = _send(p, key="protokoll-versand-0002", cc_email=None, confirm_customer=True)
    assert r.status_code == 200, r.text
    assert db.scalar(select(AuditLog.id).where(AuditLog.field_label == "Abnahmeprotokoll: abweichender Kunde bestätigt"))


def test_manual_delivery_with_recipient_choice_uses_the_version(versand):
    """Zustellung nachtragen: dieselbe Fassung, Empfängerauswahl, Vollmacht des Empfangsbevollmächtigten festgehalten -- danach
    "versendet" (beim Auftraggeber angekommen)."""
    p, db = versand, versand["db"]
    assert _sign_ag(p).status_code == 200
    [version] = _versions(db, p["c"]["id"])
    empf = p["buero"].get("/api/email-dispatches/delivery-recipients",
                          params={"document_type": "checkliste", "document_id": p["c"]["id"]}).json()
    assert empf["client"]["name"] and {x["participant_id"] for x in empf["participants"]} >= {p["verwaltung"]}
    r = _manual(p, to_client="true", participant_ids=str(p["verwaltung"]))
    assert r.status_code == 200, r.text
    [row] = _dispatches(db)
    assert row.sent_document_id == version.sent_document_id and row.delivered_to_client is True
    assert db.scalar(select(DispatchAuthorization.id).where(DispatchAuthorization.dispatch_id == row.id))
    assert _state(p)["status"] == "versendet"


def test_attack_monteur_gets_neither_state_nor_send(versand):
    p = versand
    assert _sign_ag(p).status_code == 200
    assert p["monteur"].get(f"/api/checklists/{p['c']['id']}/protocol-dispatch").status_code == 403
    assert p["monteur"].post(f"/api/checklists/{p['c']['id']}/protocol-dispatch/send-email",
                             json={"dispatch_key": "protokoll-monteur-0001"}).status_code == 403
    assert FakeSMTP.sent == []


def test_email_template_and_placeholders(versand):
    from app.document_email_templates import update_email_template

    p, db = versand, versand["db"]
    update_email_template(db, "abnahmeprotokoll", subject_template="Protokoll {auftragsnummer} – {kundenname}",
                          body_template="{anrede}\n\nProtokoll Nr. {checklistennummer} zum Bauvorhaben {bauvorhaben}.")
    assert _sign_ag(p).status_code == 200
    assert _send(p, cc_email=None).status_code == 200
    [mail] = FakeSMTP.sent
    order = db.get(acceptances_module.Order, p["order_id"])
    from email.header import decode_header, make_header

    assert str(make_header(decode_header(mail["message"]["Subject"]))).startswith(f"Protokoll {order.order_number} – ")
    body = mail["message"].get_payload()[0].get_payload(decode=True).decode("utf-8")
    assert f"Protokoll Nr. {p['c']['id']} zum Bauvorhaben" in body and "{" not in body


# ---------------------------------------------------------------------------
# Punkt 3: die Abnahme verweist auf die feste Fassung ihrer Unterschrift
# ---------------------------------------------------------------------------

def test_acceptance_refers_to_the_fixed_version_and_shows_it(versand):
    p, db = versand, versand["db"]
    assert _sign_ag(p).status_code == 200
    [version] = _versions(db, p["c"]["id"])
    [a] = _acceptances(db)
    assert (a.checksum_format, a.protocol_version_id, a.protocol_pdf_sha256) == (4, version.id, version.sent_document.sha256)
    [eintrag] = p["buero"].get(f"/api/orders/{p['order_id']}/acceptances").json()
    assert (eintrag["protocol"]["version_no"], eintrag["protocol"]["pdf_document_id"], eintrag["protocol"]["check"]) == (
        1, version.sent_document_id, "unveraendert")
    assert eintrag["intact"]


@pytest.mark.parametrize("spalte", ["protocol_version_id", "protocol_pdf_sha256"])
def test_attack_reference_to_the_version_changed_past_the_orm(versand, spalte):
    """Verweis auf eine andere Fassung bzw. andere Prüfsumme am ORM vorbei: Inhalt und Verweis weichen ab."""
    p, db = versand, versand["db"]
    assert _sign_ag(p).status_code == 200 and _sign_an(p).status_code == 200
    v1, v2 = _versions(db, p["c"]["id"])
    [a] = _acceptances(db)
    wert = v2.id if spalte == "protocol_version_id" else v2.sent_document.sha256
    db.execute(text(f"UPDATE order_acceptances SET {spalte} = :w WHERE id = :i"), {"w": wert, "i": a.id})
    db.commit()
    [eintrag] = p["buero"].get(f"/api/orders/{p['order_id']}/acceptances").json()
    assert eintrag["protocol"]["check"] == "abweichend" and not eintrag["intact"]


def test_attack_changed_pdf_of_the_signature_gives_no_acceptance(versand, ohne_folge):
    p, db = versand, versand["db"]
    assert _sign_ag(p).status_code == 200
    [version] = _versions(db, p["c"]["id"])
    _verfaelschen(version.sent_document)
    r = _nachholen(p)
    assert r.status_code == 409 and "nicht mehr unversehrt" in r.json()["detail"], r.text
    assert _acceptances(db) == []


def test_format_3_acceptance_without_version_stays_valid(versand, ohne_folge, monkeypatch):
    """Eine Abnahme aus 1.8.63–1.8.66 (Format 3, ohne Verweis auf eine Fassung) rechnet unverändert -- "Prüfsumme stimmt"."""
    p, db = versand, versand["db"]
    assert _sign_ag(p).status_code == 200
    with monkeypatch.context() as m:
        m.setattr(acceptances_module, "CHECKSUM_FORMAT", 3)
        m.setattr(protocol_module, "_signature_version", lambda db_, signature: (None, None))
        assert _nachholen(p).status_code == 200
    [a] = _acceptances(db)
    assert (a.checksum_format, a.protocol_version_id) == (3, None)
    assert "version_id" not in acceptances_module.acceptance_content(a)["protocol"]
    check = acceptances_module.verify_acceptance(a)
    assert check["ok"] and check["protocol"] == "unveraendert"


def test_migration_adds_columns_and_refuses_downgrade(versand):
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    path = next((ROOT / "alembic" / "versions").glob("*_protokoll_versand.py"))
    spec = importlib.util.spec_from_file_location("mig_protokoll_versand", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    p = versand
    assert _sign_ag(p).status_code == 200
    engine = p["db"].get_bind()
    with engine.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            with pytest.raises(RuntimeError, match="Downgrade verweigert: 1 Abnahmen verweisen auf eine feste Fassung, 1 "):
                module.downgrade()
    assert {"protocol_version_id", "protocol_pdf_sha256"} <= {c["name"] for c in inspect(engine).get_columns("order_acceptances")}
    assert "copy_to" in {c["name"] for c in inspect(engine).get_columns("checklist_versions")}
    assert module.down_revision == "28dde84825c8"


# ---------------------------------------------------------------------------
# PostgreSQL: Verwerfen und Versand gleichzeitig
# ---------------------------------------------------------------------------

@pytest.fixture
def pg(monkeypatch, tmp_path):
    if not PG_TEST_DATABASE_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    import app.project_participants as participants_module
    from app.grunddaten import anlegen

    FakeSMTP.sent, FakeSMTP.fail, FakeSMTP.during_send = [], None, None
    monkeypatch.setattr("app.email_sending.smtplib.SMTP", FakeSMTP)
    monkeypatch.setattr(acceptances_module, "ACCEPTANCE_FILE_ROOT", tmp_path / "abnahmen")
    monkeypatch.setattr(participants_module, "POWER_OF_ATTORNEY_ROOT", tmp_path / "vollmachten")
    monkeypatch.setattr(checklists_module, "CHECKLIST_ROOT", tmp_path / "checklisten")
    monkeypatch.setattr(follow_ups_module, "run_follow_ups_after_signature", lambda *a, **k: None)
    schema = f"pgtest_versand_{uuid.uuid4().hex[:8]}"
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
            _configure_smtp(setup)
            w = _welt(setup)
            project = setup.get(Project, setup.get(acceptances_module.Order, w["order_id"]).project_id)
            setup.get(Customer, project.customer_id).email = AG_EMAIL
            setup.commit()
            tpl = _vorlage(setup)
            c = checklists_module.create_checklist(setup, template_id=tpl["id"], context_type="auftrag",
                                                   order_id=w["order_id"])
            f = {x["field_key"].removeprefix("abnahme."): x["id"] for x in c["fields"]}
            for key, value in (("teilnehmer", "alle"), ("umfang", "gesamt"), ("ergebnis", "abgenommen"),
                               ("vorbehalt_maengel", "nein"), ("vorbehalt_vertragsstrafe", "nein")):
                checklists_module.save_answer(setup, c["id"], f[key], value)
            checklists_module.add_attachment(setup, c["id"], f["unterschrift_auftraggeber"], SIGNATUR,
                                             signer_person="Herbert Halle", account_user_id=1, account_name="Olga")
            an = checklists_module.add_attachment(setup, c["id"], f["unterschrift_auftragnehmer"], SIGNATUR,
                                                  account_user_id=1, account_name="Olga")
            an_id = next(a["id"] for a in an["attachments"] if a["field_id"] == f["unterschrift_auftragnehmer"])
        finally:
            setup.close()
        yield Session, {"checklist_id": c["id"], "an": an_id}
    finally:
        close_all_sessions()
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE application_name = :n"),
                         {"n": schema})
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin.dispose()


def test_postgresql_send_waits_for_a_running_discard_and_sends_nothing(pg):
    """Das Verwerfen der Unterschrift des Auftragnehmers hält seinen Commit an; der Versand wählt Fassung 2, wartet vor dem
    Senden auf die Zeilensperre und findet sie danach überholt -- keine Mail, der Eintrag ist fehlgeschlagen."""
    Session, w = pg

    def verwerfen(s):
        return checklists_module.discard_signatures(s, w["checklist_id"], signature_id=w["an"], reason="gleichzeitig")

    def senden(s):
        return dispatch_module.send_protocol(s, w["checklist_id"], dispatch_key="protokoll-pg-000001")

    first, second = _run(Session, verwerfen, senden)
    assert not isinstance(first, Exception), first
    assert isinstance(second["result"], ValueError) and "überholt" in str(second["result"]), second
    assert second["seconds"] >= 0.9 and FakeSMTP.sent == []
    s = Session()
    try:
        assert [d.status for d in s.scalars(select(EmailDispatch))] == ["fehlgeschlagen"]
        assert [v.version_no for v in versions_of(s, w["checklist_id"])] == [1, 2]
    finally:
        s.close()
