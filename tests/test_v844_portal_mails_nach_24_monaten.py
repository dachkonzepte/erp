"""Version 1.11.53 (W1c Stufe 2, S2-0 e; Antwort W2-4 vom 28.11.2026) -- die Mails des Portals im Versandprotokoll nach 24 Monaten löschen.

Bis 1.11.52 blieb jede Mail des Portals (Link, Anmeldecode) als Zeile im Versandprotokoll für immer (Regel 21) -- jede Code-Anforderung eine Zeile mit Adresse
(Befund B3 des Bauplans W1c Stufe 2). Jetzt löscht der Postbote sie 24 Monate nach dem Versand, von selbst, wie das Zugriffsprotokoll.

    Frist     älter als 24 Monate (Zeit der Datenbank): weg; jünger: bleibt
    nur sie   nur die Arten aus PORTAL_TYPES -- jede andere Mail (Angebot, Rechnung, Aufgabe …) bleibt, auch älter
    gebunden  bleibt, solange etwas auf die Zeile zeigt (Auftrag des Postboten, Versandergebnis, Kopie an, Vollmacht) oder sie eine Ablage hat
    Wächter   kein anderer Code unter app/ oder scripts/ löscht aus dem Versandprotokoll oder der Ablage (Regel 21); der eine Weg steht in app/portal_postbote.py
"""

import re
import uuid
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app import portal_postbote as postbote
from app.models import DispatchAuthorization, DispatchCopy, DispatchOutcome
from tests.test_v805_portal_postbote import _db, graph, pg_modul, welt  # noqa: F401  (Fixtures)

ROOT = Path(__file__).resolve().parent.parent
JETZT = "(now() AT TIME ZONE 'utc')"


def _versand(w, art: str, alter: str, *, ablage: bool = False) -> int:
    ablage_id = None
    if ablage:
        ablage_id = w.erp("INSERT INTO sent_documents (document_type, document_id, filename, stored_filename, size_bytes, sha256, created_at) VALUES "
                          f"('angebot', 1, 'probe.pdf', :n, 1, :s, {JETZT}) RETURNING id", n=f"{uuid.uuid4().hex}.pdf", s="a" * 64)[0][0]
    return w.erp(f"INSERT INTO email_dispatches (dispatch_key, message_ref, status, channel, document_type, to_recipients, subject, created_at, "
                 f"created_by_name, sent_document_id) VALUES (:k, :m, 'gesendet', 'graph', :a, 'kunde@example.invalid', 'Betreff', {JETZT} - interval '{alter}', "
                 "'System', :d) RETURNING id", k=f"probe-{uuid.uuid4().hex}", m=str(uuid.uuid4()), a=art, d=ablage_id)[0][0]


def _da(w, i) -> bool:
    return w.erp("SELECT count(*) FROM email_dispatches WHERE id = :i", i=i)[0][0] == 1


def test_pg_portal_mails_nach_24_monaten(welt):  # noqa: F811
    w = welt
    alt_code = _versand(w, "portal_code", "25 months")
    alt_link = _versand(w, "portal_link", "25 months")
    jung_code = _versand(w, "portal_code", "23 months")
    alt_angebot = _versand(w, "angebot", "25 months")
    alt_aufgabe = _versand(w, "aufgabe", "30 months")
    with _db(w) as db:
        zahlen = postbote.aufraeumen(db)
    assert zahlen["versand"] == 2
    assert (_da(w, alt_code), _da(w, alt_link), _da(w, jung_code), _da(w, alt_angebot), _da(w, alt_aufgabe)) == (False, False, True, True, True)
    with _db(w) as db:
        assert postbote.aufraeumen(db)["versand"] == 0  # ein zweiter Lauf: nichts mehr


def test_pg_gebundene_zeilen_bleiben(welt):  # noqa: F811
    w = welt
    kid, zid, _link = w.kunde()
    frei = _versand(w, "portal_code", "25 months")
    mit_auftrag = _versand(w, "portal_code", "25 months")
    sitzung = w.erp(f"INSERT INTO portal_sitzungen (zugang_id, wert_sha256, angelegt_am, laeuft_ab) VALUES (:z, :w, {JETZT}, {JETZT} + interval '30 days') "
                    "RETURNING id", z=zid, w="f" * 64)[0][0]
    w.erp(f"INSERT INTO portal_post (art, zugang_id, sitzung_id, angefordert_am, status, email_dispatch_id) VALUES ('code', :z, :s, {JETZT}, 'gesendet', :d)",
          z=zid, s=sitzung, d=mit_auftrag)
    mit_ergebnis, mit_kopie, mit_vollmacht = (_versand(w, "portal_link", "25 months") for _ in range(3))
    mit_ablage = _versand(w, "portal_link", "25 months", ablage=True)
    with Session(w.engine) as db:
        db.add(DispatchOutcome(dispatch_id=mit_ergebnis, outcome="empfangen", outcome_on=date(2024, 10, 1)))
        db.add(DispatchCopy(dispatch_id=mit_kopie, participant_id=1, contact_name="Erfunden", role_label="Architekt"))
        db.add(DispatchAuthorization(dispatch_id=mit_vollmacht, participant_id=1, contact_name="Erfunden", role="architekt"))
        db.commit()
    with _db(w) as db:
        assert postbote.aufraeumen(db)["versand"] == 1
    assert [_da(w, i) for i in (frei, mit_auftrag, mit_ergebnis, mit_kopie, mit_vollmacht, mit_ablage)] == [False, True, True, True, True, True]
    for tabelle in ("dispatch_outcomes", "dispatch_copies", "dispatch_authorizations"):  # aufräumen für die übrigen Tests des Moduls
        w.erp(f"DELETE FROM {tabelle}")


# --- Wächter: kein anderer Weg löscht aus dem Versandprotokoll oder der Ablage ------------------------------------------------------------------

MODELLE = r"(EmailDispatch|SentDocument|DispatchOutcome|DispatchCopy|DispatchAuthorization)"
TABELLEN = r"(email_dispatches|sent_documents|dispatch_outcomes|dispatch_copies|dispatch_authorizations)"
MUSTER = [re.compile(rf"\bdelete\(\s*{MODELLE}\b"), re.compile(rf"DELETE\s+FROM\s+{TABELLEN}\b", re.IGNORECASE),
          re.compile(rf"query\(\s*{MODELLE}\b[^\n]*\.delete\("), re.compile(r"\.delete\(\s*(dispatch|eintrag|ablage|sent_document|outcome)\w*\s*\)")]


def test_waechter_nur_der_postbote_loescht_aus_dem_versandprotokoll():
    funde = []
    for ordner in ("app", "scripts"):
        for pfad in sorted((ROOT / ordner).rglob("*.py")):
            if "__pycache__" in pfad.parts:
                continue
            for nr, zeile in enumerate(pfad.read_text(encoding="utf-8").splitlines(), start=1):
                if any(m.search(zeile) for m in MUSTER):
                    funde.append(f"{pfad.relative_to(ROOT).as_posix()}:{zeile.strip()[:80]}")
    assert funde == ["app/portal_postbote.py:return delete(EmailDispatch).where("], funde


@pytest.mark.parametrize("art", ["portal_link", "portal_code"])
def test_nur_die_arten_des_portals(art):
    from app.email_dispatch import PORTAL_TYPES

    assert set(PORTAL_TYPES) == {"portal_link", "portal_code"} and art in PORTAL_TYPES
    assert postbote.VERSAND_FRIST == "24 months"
