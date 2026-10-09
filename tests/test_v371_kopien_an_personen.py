"""Version 1.8.69 -- Nacharbeit zu Stufe 2c-2 (docs/archiv/abnahme-und-gewaehrleistung.md, "Umsetzung 1.8.69").

1. Kopien an die im Dokument eingefrorenen Personen, an ihre Adresse von heute (app/frozen_copies.py) -- Abnahmeprotokoll und
   Briefe der Behinderungs- und Bedenkenanzeige; der Hinweis vor dem Versand nennt alte und neue Adresse; das Versandprotokoll hält
   je Person die tatsächlich genutzte Adresse fest (DispatchCopy).
2. Wer laut Dokument eine Kopie bekommen sollte, aber keine Mail bekam (keine oder ungültige Adresse, nicht mehr im Adressbuch),
   steht im Versandverlauf.
3. Die Briefe haben kein freies CC mehr. Strukturtest: wo ein PDF "Kopie an:" zeigt, gehen die Mails genau an diese Empfänger --
   jeder Renderer mit "Kopie an:" ist eingetragen, seine Dokumente gehen nur über dispatch_to_client(), das CC nur aus den
   eingefrorenen Personen bildet; dazu je Dokumentart der Vergleich "Kopie an:" im versendeten PDF gegen Cc der Mail.

Angriffe: CC und An über die API, Person aus dem Projekt entfernt bzw. Kontakt gelöscht, ungültige Adresse, Adresse des
Auftraggebers unter den Kopien, festgehaltene Kopie am ORM vorbei ändern, Downgrade mit Bestand. Mails gehen nur an die
Test-Attrappe (FakeSMTP), Adressen der eigenen Domain bzw. example.com."""

import ast
import importlib.util
import inspect as pyinspect
import json
import re
from pathlib import Path

import pytest
from sqlalchemy import inspect, select, text


import app.notice_letters as notice_module
from app.contacts import delete_contact
from app.frozen_copies import NO_ADDRESS, NOT_IN_ADDRESS_BOOK
from app.models import ArchiveImmutableError, Contact, DispatchCopy, EmailDispatch, ProjectParticipant
from app.project_participants import remove_participant
from app.schemas import NoticeLetterSend, ProtocolSend
from app.sent_documents import read_sent_document
from tests.test_v321_email_dispatch import FakeSMTP, _attachment
from tests.test_v343_behinderungsanzeige_versand import (  # noqa: F401  (Fixtures)
    AG_EMAIL as N_AG, _letters, _office as _n_office, _participant, _send as _n_send, _signed as _n_signed, _state as _n_state,
    _wegfall, nworld,
)
from tests.test_v305_checklist_filling import world  # noqa: F401  (Fixture)
from tests.test_v341_behinderungsanzeige import bworld  # noqa: F401  (Fixture)
from tests.test_v346_bedenkenanzeige import kworld  # noqa: F401  (Fixture)
from tests.test_v347_bedenkenanzeige_versand import (  # noqa: F401  (Fixtures)
    _office as _m_office, _send as _m_send, _signed as _m_signed, mworld,
)
from tests.test_v349_abnahme_und_gewaehrleistung import ablage, welt  # noqa: F401  (Fixtures)
from tests.test_v363_zweck_abnahme import _sign_ag
from tests.test_v365_abnahme_aus_protokoll import protokoll  # noqa: F401  (Fixture)
from tests.test_v366_protokoll_seite_und_pdf import _pdf_text
from tests.test_v368_feste_fassung import _versions
from tests.test_v369_protokoll_versand import AG_EMAIL, ARCH_EMAIL, HV_EMAIL, _send, _state, versand  # noqa: F401

ROOT = Path(__file__).resolve().parent.parent
NEU_EMAIL = "architektin.neu@dachkonzepte.example"
BAU_EMAIL = "bauleitung@dachkonzepte.example"


def _cc(mail) -> list[str]:
    return [a.strip() for a in (mail["message"]["Cc"] or "").split(",") if a.strip()]


def _rows(db, dispatch_id=None) -> list[tuple]:
    db.expire_all()
    query = select(DispatchCopy).order_by(DispatchCopy.id)
    if dispatch_id is not None:
        query = query.where(DispatchCopy.dispatch_id == dispatch_id)
    return [(r.contact_name, r.email, r.note) for r in db.scalars(query)]


def _kopie_an(pdf: bytes) -> list[str]:
    """Die Namen unter "Kopie an:" im PDF -- "Name (Rolle); Name (Rolle)" bis zum nächsten Abschnitt."""
    flat = " ".join(_pdf_text(pdf).split())
    if "Kopie an:" not in flat:
        return []
    part = re.split(r"Anlage:|Erstellt aus|Abschluss", flat.split("Kopie an:", 1)[1])[0]
    return [m.group(1).strip() for m in re.finditer(r"\s*([^;]+?)\s*\(([^()]*)\)\s*(?:;|$)", part.strip())]


def _beteiligt(db, project_id, name, email, role, copy=True) -> ProjectParticipant:
    """Firma als Beteiligter des Projekts -- die Adresse am Adressbuch vorbei gesetzt (es prüft sie nicht)."""
    from app.contacts import create_contact
    from app.models import Project
    from app.project_participants import add_participant

    contact = create_contact(db, {"kind": "firma", "company_name": name})
    contact.email = email
    db.commit()
    return add_participant(db, db.get(Project, project_id), contact, role=role, copy_on_notices=copy)


def _heute(db, participant: ProjectParticipant) -> tuple[str, str | None]:
    from app.project_participants import participant_info

    db.expire_all()
    info = participant_info(db.get(ProjectParticipant, participant.id)) if db.get(ProjectParticipant, participant.id) else None
    return info["name"], info["email"]


# ---------------------------------------------------------------------------
# Punkt 1 und 2: Abnahmeprotokoll
# ---------------------------------------------------------------------------

def test_protocol_copy_goes_to_the_persons_address_of_today(versand):
    """Nach der Unterschrift ändert die Architektin ihre Adresse: die Karte nennt alte und neue, die Kopie geht an die neue; das
    Versandprotokoll hält die genutzte Adresse je Person fest. An und CC über die API werden nicht beachtet."""
    p, db = versand, versand["db"]
    assert _sign_ag(p).status_code == 200
    [version] = _versions(db, p["c"]["id"])
    frozen = json.loads(version.copy_to)
    assert [(c["name"], c["email"], c["contact_id"] is not None) for c in frozen] == [
        ("Petra Plan", ARCH_EMAIL, True), ("HV Muster", HV_EMAIL, True)]
    db.get(ProjectParticipant, p["architektin"]).contact.email = NEU_EMAIL
    db.commit()
    s = _state(p)
    assert [(c["name"], c["email"], c["email_then"]) for c in s["version"]["copy_to"]] == [
        ("Petra Plan", NEU_EMAIL, ARCH_EMAIL), ("HV Muster", HV_EMAIL, HV_EMAIL)]
    assert s["cc"] == [NEU_EMAIL, HV_EMAIL]
    assert s["copy_changes"] == [f"Petra Plan (Architekt/Planer): E-Mail-Adresse heute {NEU_EMAIL} statt {ARCH_EMAIL} – die Kopie "
                                 f"geht an {NEU_EMAIL}."]
    r = _send(p, cc_email="angriff@dachkonzepte.example", to_email="angriff2@dachkonzepte.example",
              cc="angriff3@dachkonzepte.example")
    assert r.status_code == 200, r.text
    [mail] = FakeSMTP.sent
    assert mail["recipients"] == [AG_EMAIL, NEU_EMAIL, HV_EMAIL] and _cc(mail) == [NEU_EMAIL, HV_EMAIL]
    assert [(c["contact_name"], c["email"]) for c in r.json()["copies"]] == [("Petra Plan", NEU_EMAIL), ("HV Muster", HV_EMAIL)]
    row = db.scalar(select(EmailDispatch))
    assert row.cc_recipients == f"{NEU_EMAIL}, {HV_EMAIL}" and "angriff" not in f"{row.to_recipients} {row.cc_recipients}"
    assert _rows(db) == [("Petra Plan", NEU_EMAIL, None), ("HV Muster", HV_EMAIL, None)]
    assert _kopie_an(read_sent_document(version.sent_document)) == ["Petra Plan", "HV Muster"]


def test_protocol_person_removed_or_unchecked_still_gets_the_copy(versand):
    """Die Architektin wird aus dem Projekt entfernt, die Hausverwaltung hat keine "Kopie bei Anzeigen" mehr: beide stehen im PDF
    und bekommen die Kopie weiter (über ihren Kontakt); die Karte nennt beide Änderungen."""
    p, db = versand, versand["db"]
    assert _sign_ag(p).status_code == 200
    remove_participant(db, db.get(ProjectParticipant, p["architektin"]))
    db.get(ProjectParticipant, p["verwaltung"]).copy_on_notices = False
    db.commit()
    s = _state(p)
    assert s["cc"] == [ARCH_EMAIL, HV_EMAIL]
    assert [line.split(" hat heute")[0] for line in s["copy_changes"]] == ["Petra Plan (Architekt/Planer)",
                                                                         "HV Muster (Hausverwaltung)"]
    assert _send(p).status_code == 200
    assert FakeSMTP.sent[0]["recipients"] == [AG_EMAIL, ARCH_EMAIL, HV_EMAIL]


def test_protocol_copies_without_mail_are_recorded_in_the_history(versand):
    """Unter "Kopie an:" stehen auch: eine Sachverständige ohne Adresse, ein Gutachter mit ungültiger Adresse und eine Eigentümerin,
    die danach aus dem Projekt entfernt und aus dem Adressbuch gelöscht wird. Der Versand geht an die übrigen; Versandverlauf und
    Versandprotokoll nennen die drei mit Grund; die Karte zeigt sie vorher als "keine Mail"."""
    p, db = versand, versand["db"]
    pid = db.get(ProjectParticipant, p["architektin"]).project_id
    _beteiligt(db, pid, "SV Ohne", None, "sachverstaendiger")
    _beteiligt(db, pid, "Gutachter Kaputt", "kaputt@beispiel..de", "sonstiges")
    eigentuemerin = _beteiligt(db, pid, "Eigentum GmbH", "eigentum@dachkonzepte.example", "eigentuemer")
    assert _sign_ag(p).status_code == 200
    contact = eigentuemerin.contact
    remove_participant(db, db.get(ProjectParticipant, eigentuemerin.id))
    delete_contact(db, db.get(Contact, contact.id))
    s = _state(p)
    nomail = {c["name"]: c["no_mail"] for c in s["version"]["copy_to"] if not c["email"]}
    assert nomail == {"SV Ohne": NO_ADDRESS, "Gutachter Kaputt": "E-Mail-Adresse „kaputt@beispiel..de“ ungültig",
                      "Eigentum GmbH": NOT_IN_ADDRESS_BOOK}
    assert any("Eigentum GmbH (Eigentümer) steht nicht mehr im Adressbuch" in line for line in s["copy_changes"])
    r = _send(p)
    assert r.status_code == 200, r.text
    assert FakeSMTP.sent[0]["recipients"] == [AG_EMAIL, ARCH_EMAIL, HV_EMAIL]
    missed = {(c["contact_name"], c["note"]) for c in r.json()["copies"] if c["email"] is None}
    assert missed == {("SV Ohne", NO_ADDRESS), ("Gutachter Kaputt", "E-Mail-Adresse „kaputt@beispiel..de“ ungültig"),
                      ("Eigentum GmbH", NOT_IN_ADDRESS_BOOK)}
    items = p["buero"].get(f"/api/email-dispatches?document_type=checkliste&document_id={p['c']['id']}").json()["items"]
    assert {(c["contact_name"], c["note"]) for c in items[0]["copies"] if c["email"] is None} == missed
    assert "data-copy-missed" in (ROOT / "app" / "templates" / "_email_dispatch.html").read_text(encoding="utf-8")


def test_protocol_client_address_among_the_copies(versand):
    p, db = versand, versand["db"]
    assert _sign_ag(p).status_code == 200
    db.get(ProjectParticipant, p["architektin"]).contact.email = AG_EMAIL.upper()
    db.commit()
    assert _send(p).status_code == 200
    [mail] = FakeSMTP.sent
    assert mail["recipients"] == [AG_EMAIL, HV_EMAIL] and _cc(mail) == [HV_EMAIL]
    assert _rows(db)[0] == ("Petra Plan", AG_EMAIL.upper(), "dieselbe Adresse wie der Auftraggeber (An)")


def test_protocol_version_before_1_8_69_finds_the_person_through_the_participant(versand):
    """Eine Fassung von 1.8.66/1.8.67 (ohne Kontakt und Adresse): die Person über den Beteiligten desselben Projekts, an ihre
    Adresse von heute, ohne Adress-Hinweis (die alte ist unbekannt); ist der Beteiligte entfernt, gilt sie als nicht mehr im
    Adressbuch."""
    p, db = versand, versand["db"]
    assert _sign_ag(p).status_code == 200
    [version] = _versions(db, p["c"]["id"])
    alt = json.dumps([{k: c[k] for k in ("participant_id", "name", "role_label")} for c in json.loads(version.copy_to)],
                     ensure_ascii=False)
    db.execute(text("UPDATE checklist_versions SET copy_to = :c WHERE id = :id"), {"c": alt, "id": version.id})
    db.get(ProjectParticipant, p["architektin"]).contact.email = NEU_EMAIL
    db.commit()
    remove_participant(db, db.get(ProjectParticipant, p["verwaltung"]))
    db.expire_all()
    s = _state(p)
    assert [(c["email"], c["no_mail"], c["then_known"]) for c in s["version"]["copy_to"]] == [
        (NEU_EMAIL, None, False), (None, NOT_IN_ADDRESS_BOOK, False)]
    assert not any("E-Mail-Adresse heute" in line for line in s["copy_changes"])
    assert _send(p).status_code == 200
    assert FakeSMTP.sent[0]["recipients"] == [AG_EMAIL, NEU_EMAIL]
    assert _rows(db) == [("Petra Plan", NEU_EMAIL, None), ("HV Muster", None, NOT_IN_ADDRESS_BOOK)]


def test_attack_recorded_copy_is_immutable(versand):
    p, db = versand, versand["db"]
    assert _sign_ag(p).status_code == 200
    assert _send(p).status_code == 200
    row = db.scalars(select(DispatchCopy)).first()
    row.email = "angriff@dachkonzepte.example"
    with pytest.raises(ArchiveImmutableError):
        db.commit()
    db.rollback()
    with pytest.raises(ArchiveImmutableError):
        db.delete(db.scalars(select(DispatchCopy)).first())
        db.commit()
    db.rollback()
    assert _rows(db)[0] == ("Petra Plan", ARCH_EMAIL, None)


# ---------------------------------------------------------------------------
# Punkt 3: Briefe der Anzeigen
# ---------------------------------------------------------------------------

def test_letter_copies_are_the_persons_under_kopie_an_at_their_address_of_today(nworld, router_test_client):
    """Vor dem ersten Brief zeigt die Karte, wer beim Erstellen unter "Kopie an:" käme; der erste Versand friert sie ein (Kontakt
    und Adresse im Inhalt). Danach: neue Adresse der Architektin, Hausverwaltung ohne "Kopie bei Anzeigen", Bauleitung neu -- der
    zweite Versand geht an die Personen im Brief, an ihre Adresse von heute; An und CC aus der Anfrage zählen nicht."""
    db = nworld["db"]
    office = _n_office(nworld, router_test_client)
    arch = _participant(db, nworld, name="Architekt", email="arch@example.com")
    hv = _participant(db, nworld, name="Hausverwaltung", email="hv@example.com", role="hausverwaltung")
    bau = _participant(db, nworld, name="Bauleitung", email="bau@example.com", role="bauleitung_ag", copy=False)
    c = _n_signed(nworld, router_test_client)
    kind = next(k for k in _n_state(office, c)["kinds"] if k["kind"] == "behinderungsanzeige")
    assert (kind["copies_frozen"], kind["cc"], kind["copy_changes"]) == (False, ["arch@example.com", "hv@example.com"], [])
    assert "cc_prefill" not in _n_state(office, c)
    r = _n_send(office, c, cc_email="fremd@example.com", to_email="fremd2@example.com")
    assert r.status_code == 200, r.text
    assert FakeSMTP.sent[0]["recipients"] == [N_AG, "arch@example.com", "hv@example.com"]
    [letter] = _letters(db)
    frozen = json.loads(letter.content)["copy_to"]
    assert [(e["name"], e["email"], e["contact_id"]) for e in frozen] == [
        ("Architekt", "arch@example.com", arch.contact_id), ("Hausverwaltung", "hv@example.com", hv.contact_id)]
    db.get(Contact, arch.contact_id).email = "arch.neu@example.com"
    db.get(ProjectParticipant, hv.id).copy_on_notices = False
    db.get(ProjectParticipant, bau.id).copy_on_notices = True
    db.commit()
    kind = next(k for k in _n_state(office, c)["kinds"] if k["kind"] == "behinderungsanzeige")
    assert kind["copies_frozen"] and kind["cc"] == ["arch.neu@example.com", "hv@example.com"]
    changes = " | ".join(kind["copy_changes"])
    assert "heute arch.neu@example.com statt arch@example.com" in changes
    assert "Hausverwaltung (Hausverwaltung) hat heute keine" in changes
    assert "Bauleitung (Bauleitung des Auftraggebers) hat seither" in changes
    r = _n_send(office, c, cc_email="bau@example.com")
    assert r.status_code == 200, r.text
    assert FakeSMTP.sent[1]["recipients"] == [N_AG, "arch.neu@example.com", "hv@example.com"]
    assert _kopie_an(_attachment(FakeSMTP.sent[1]["message"])) == ["Architekt", "Hausverwaltung"]
    second = db.scalars(select(EmailDispatch).order_by(EmailDispatch.id.desc())).first()
    assert _rows(db, second.id) == [("Architekt", "arch.neu@example.com", None), ("Hausverwaltung", "hv@example.com", None)]


def test_letter_before_1_8_69_finds_persons_through_the_participant(nworld, router_test_client, monkeypatch):
    """Ein Brief wie seit 1.8.40 (in "Kopie an:" nur Beteiligter, Name, Rolle): die Kopie geht an die Adresse von heute; ein
    entfernter Beteiligter ist nicht mehr auffindbar -- keine Mail, im Versandverlauf festgehalten."""
    db = nworld["db"]
    office = _n_office(nworld, router_test_client)
    arch = _participant(db, nworld, name="Architekt", email="arch@example.com")
    weg = _participant(db, nworld, name="Weg GmbH", email="weg@example.com", role="eigentuemer")
    real_freeze = notice_module.freeze_copies
    monkeypatch.setattr(notice_module, "freeze_copies", lambda db_, pid: [
        {k: e[k] for k in ("participant_id", "name", "role_label")} for e in real_freeze(db_, pid)])
    c = _n_signed(nworld, router_test_client)
    assert _n_send(office, c).status_code == 200
    monkeypatch.setattr(notice_module, "freeze_copies", real_freeze)
    db.get(Contact, arch.contact_id).email = "arch.neu@example.com"
    db.commit()
    remove_participant(db, db.get(ProjectParticipant, weg.id))
    assert _n_send(office, c).status_code == 200
    assert FakeSMTP.sent[1]["recipients"] == [N_AG, "arch.neu@example.com"]
    second = db.scalars(select(EmailDispatch).order_by(EmailDispatch.id.desc())).first()
    assert _rows(db, second.id) == [("Architekt", "arch.neu@example.com", None), ("Weg GmbH", None, NOT_IN_ADDRESS_BOOK)]


# ---------------------------------------------------------------------------
# Strukturtest: wo ein PDF "Kopie an:" zeigt, gehen die Mails genau an diese Empfänger
# ---------------------------------------------------------------------------

# Renderer mit "Kopie an:" -> die Dokumentarten ihrer Mails. Ein neuer Renderer mit "Kopie an:" gehört hier eingetragen und seine
# Mails über dispatch_to_client() (CC nur aus den eingefrorenen Personen).
KOPIE_AN_PDFS = {
    "app/notice_letter_pdf.py": ("behinderungsanzeige", "wiederaufnahme", "bedenkenanzeige"),
    "app/checklist_pdf.py": ("checkliste",),  # nur das Abnahmeprotokoll zeigt "Kopie an:"
}
# Wer eine dieser Dokumentarten sonst noch mit fester Art versenden darf -- mit Grund.
ANDERE_VERSENDER = {
    ("app/checklist_email.py", "send_checklist_email"): "allgemeiner Versand einer Checkliste: lehnt das Abnahmeprotokoll ab (400, "
                                                        "test_v369), jede andere Checkliste zeigt kein „Kopie an:“",
}


def _app_modules():
    for path in sorted((ROOT / "app").rglob("*.py")):
        yield path.relative_to(ROOT).as_posix(), ast.parse(path.read_text(encoding="utf-8"))


def _docstrings(tree) -> set[int]:
    ids = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                ids.add(id(first.value))
    return ids


def test_every_pdf_with_kopie_an_is_registered():
    """Jedes Modul, das mit reportlab ein PDF baut und dabei "Kopie an" schreibt, steht in KOPIE_AN_PDFS."""
    found = set()
    for rel, tree in _app_modules():
        uses_reportlab = any(isinstance(n, (ast.Import, ast.ImportFrom)) and "reportlab" in ast.unparse(n) for n in ast.walk(tree))
        docs = _docstrings(tree)
        texts = [n for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docs]
        if uses_reportlab and any("Kopie an" in n.value for n in texts):
            found.add(rel)
    assert found == set(KOPIE_AN_PDFS)


def _enclosing_functions(tree):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for inner in ast.walk(node):
                yield node.name, inner


def test_documents_with_kopie_an_are_mailed_only_through_dispatch_to_client():
    """Jeder Aufruf von dispatch_email() mit einer Dokumentart aus KOPIE_AN_PDFS (oder mit veränderlicher Art) liegt in
    dispatch_to_client() -- sonst nur die begründeten ANDERE_VERSENDER."""
    kinds = {k for ks in KOPIE_AN_PDFS.values() for k in ks}
    found, variable = [], []
    for rel, tree in _app_modules():
        for function, node in _enclosing_functions(tree):
            if not (isinstance(node, ast.Call) and getattr(node.func, "id", getattr(node.func, "attr", None)) == "dispatch_email"):
                continue
            kind = next((k.value for k in node.keywords if k.arg == "document_type"), None)
            if isinstance(kind, ast.Constant):
                if kind.value in kinds:
                    found.append((rel, function))
            else:
                variable.append((rel, function))
    assert sorted(set(variable)) == [("app/notice_letters.py", "dispatch_to_client")]
    assert sorted(set(found)) == sorted(ANDERE_VERSENDER)


def test_dispatch_to_client_builds_cc_only_from_the_frozen_copies():
    """dispatch_to_client() nimmt kein CC von außen (kein Parameter dafür), bildet es aus cc_of(copies, to); seine Aufrufer geben
    die Personen aus dem Dokument (frozen_copies() bzw. letter_copies()); die Schemas der beiden Versand-Routen haben kein Feld für
    An oder CC."""
    params = set(pyinspect.signature(notice_module.dispatch_to_client).parameters)
    assert not {p for p in params if "cc" in p or p.endswith("_email") or p == "recipients"}
    assert "copies" in params
    tree = ast.parse((ROOT / "app" / "notice_letters.py").read_text(encoding="utf-8"))
    fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "dispatch_to_client")
    assigns = {t.id: n.value for n in ast.walk(fn) if isinstance(n, ast.Assign) for t in n.targets if isinstance(t, ast.Name)}
    assert ast.unparse(assigns["cc"]) == "cc_of(copies, to)"
    [call] = [n for n in ast.walk(fn) if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "dispatch_email"]
    assert ast.unparse(next(k.value for k in call.keywords if k.arg == "cc")) == "', '.join(cc) or None"
    callers = []
    for rel, tree in _app_modules():
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "dispatch_to_client":
                copies = next(k.value for k in node.keywords if k.arg == "copies")
                callers.append((rel, copies.func.id if isinstance(copies, ast.Call) else ast.unparse(copies)))
    assert sorted(callers) == [("app/notice_letters.py", "letter_copies"), ("app/protocol_dispatch.py", "frozen_copies")]
    for schema in (NoticeLetterSend, ProtocolSend):
        assert not [f for f in schema.model_fields if "cc" in f or "to" in f.split("_") or "email" in f]


def _letter_case(request, kind):
    w = request.getfixturevalue("mworld" if kind == "bedenkenanzeige" else "nworld")
    rtc = request.getfixturevalue("router_test_client")
    db = w["db"]
    pid = w["orders"]["mine"].project_id
    office = (_m_office if kind == "bedenkenanzeige" else _n_office)(w, rtc)
    people = [_beteiligt(db, pid, "Architekt", "arch@example.com", "architekt_planer"),
              _beteiligt(db, pid, "Hausverwaltung", "hv@example.com", "hausverwaltung"),
              _beteiligt(db, pid, "Ohne Mail", None, "sachverstaendiger")]
    c = (_m_signed if kind == "bedenkenanzeige" else _n_signed)(w, rtc)
    if kind == "wiederaufnahme":
        _wegfall(w, rtc, c)
    send = _m_send if kind == "bedenkenanzeige" else _n_send
    r = office.post(f"/api/checklists/{c['id']}/notice-letters/{kind}/freeze", json={})
    assert r.status_code == 200, r.text
    return {"db": db, "project_id": pid, "people": people, "ag": N_AG,
            "send": lambda: send(office, c, kind=kind, cc_email="fremd@example.com", to_email="fremd2@example.com")}


def _protocol_case(request):
    p = request.getfixturevalue("versand")
    db = p["db"]
    pid = db.get(ProjectParticipant, p["architektin"]).project_id
    ohne = _beteiligt(db, pid, "Ohne Mail", None, "sachverstaendiger")
    assert _sign_ag(p).status_code == 200
    people = [db.get(ProjectParticipant, p["architektin"]), db.get(ProjectParticipant, p["verwaltung"]), ohne]
    return {"db": db, "project_id": pid, "people": people, "ag": AG_EMAIL,
            "send": lambda: _send(p, cc_email="fremd@dachkonzepte.example", to_email="fremd2@dachkonzepte.example")}


@pytest.mark.parametrize("kind", ["behinderungsanzeige", "wiederaufnahme", "bedenkenanzeige", "abnahmeprotokoll"])
def test_kopie_an_in_the_sent_pdf_and_the_mail_recipients_agree(kind, request):
    """Für jede Dokumentart mit "Kopie an:": Dokument erstellt, danach neue Adresse, "Kopie bei Anzeigen" entzogen, ein neuer
    Beteiligter mit Kopie -- versendet. Die Namen unter "Kopie an:" im angehängten PDF sind genau die festgehaltenen Kopien des
    Versands, je mit ihrer Adresse von heute; Cc ist genau diese Adressen (ohne die des Auftraggebers); wer keine hat, steht ohne
    Mail mit Grund da; An und CC aus der Anfrage zählen nicht."""
    case = _protocol_case(request) if kind == "abnahmeprotokoll" else _letter_case(request, kind)
    db, (arch, hv, ohne) = case["db"], case["people"]
    db.get(Contact, arch.contact_id).email = "arch.heute@example.com"
    db.get(ProjectParticipant, hv.id).copy_on_notices = False
    db.commit()
    spaet = _beteiligt(db, case["project_id"], "Spät GmbH", "spaet@example.com", "anderes_gewerk")
    r = case["send"]()
    assert r.status_code == 200, r.text
    mail = FakeSMTP.sent[-1]
    names = _kopie_an(_attachment(mail["message"]))
    copies = r.json()["copies"]
    assert names == [c["contact_name"] for c in copies] == [_heute(db, x)[0] for x in (arch, hv, ohne)]
    emails = [c["email"] for c in copies]
    assert emails == [_heute(db, x)[1] for x in (arch, hv, ohne)] and emails[0] == "arch.heute@example.com"
    assert emails[1] and emails[2] is None
    assert _cc(mail) == [c["email"] for c in copies if c["email"]]
    assert mail["recipients"] == [case["ag"], *_cc(mail)]
    assert [(c["contact_name"], c["note"]) for c in copies if not c["email"]] == [("Ohne Mail", NO_ADDRESS)]
    assert spaet.id not in {c["participant_id"] for c in copies} and "spaet@example.com" not in mail["recipients"]


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------

def test_migration_creates_the_table_and_refuses_a_lossy_downgrade(versand):
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    path = next((ROOT / "alembic" / "versions").glob("*_kopie_an_personen.py"))
    spec = importlib.util.spec_from_file_location("mig_kopie_an_personen", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.down_revision == "7c1e5a9d3f20"
    p = versand
    assert _sign_ag(p).status_code == 200
    engine = p["db"].get_bind()
    with engine.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            module.downgrade()  # leer: geht
            assert "dispatch_copies" not in inspect(conn).get_table_names()
            module.upgrade()
    cols = {c["name"] for c in inspect(engine).get_columns("dispatch_copies")}
    assert cols == {"id", "dispatch_id", "participant_id", "contact_id", "contact_name", "role_label", "email", "note",
                    "created_at"}
    assert _send(p).status_code == 200
    with engine.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            with pytest.raises(RuntimeError, match="Downgrade verweigert: 2 beim Versand festgehaltene Kopien"):
                module.downgrade()
    assert len(_rows(p["db"])) == 2
