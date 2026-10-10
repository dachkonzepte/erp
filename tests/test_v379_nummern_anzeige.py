"""Nummernkreise: keine Anzeige verbraucht oder schreibt eine Nummer, Überspringen nicht still, Format ohne Jahr nicht mit
Jahreswechsel (seit 1.8.76; Vorgabe 1.8.75 Punkte 3 und 4 und Festlegung 1.8.74 Nr. 2, docs/archiv/befund-vor-echtbetrieb.md
"Umsetzung 1.8.76").

- preview_number() rechnet Jahreswechsel und Abgleich mit den vergebenen Nummern nur aus, schreibt sie nicht in den Nummernkreis
  (bis 1.8.75 setzte sie beides ohne Sperre, die GET-Routen der Einstellungen committeten es -- mit einem veralteten Stand konnte
  das die nächste Nummer unter eine gelöschte zurücksetzen).
- GET /api/customers und /api/customers/{id} legen ein fehlendes Kundenprofil nicht mehr an und ziehen keine Kundennummer.
- Kein GET-Endpunkt erreicht issue_number() (AST, über die Funktionen von app/).
- issue_number() springt weiter über vergebene Nummern, protokolliert das aber (logger.warning, nur Nummernkreis und Nummern).
- Einstellungen: ein Format ohne Jahr mit "Jahreswechsel: auf Startnummer zurück" wird abgelehnt (409)."""

import ast
import logging
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.berlin_time import berlin_now
from app.models import Customer, CustomerProfile, NumberSequence
from app.routers.customers import router as customers_router
from app.routers.settings import router as settings_router
from app.settings import (
    DEFAULT_SEQUENCES,
    NumberBelowExisting,
    YearlyResetWithoutYear,
    issue_number,
    load_sequence,
    preview_number,
    update_sequence,
)
from tests.test_v377_leistungszeitraum import _db, _vergeben

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"


def _stand(db, key):
    db.expire_all()
    seq = load_sequence(db, key)
    return seq.next_value, seq.last_year


# ---------------------------------------------------------------------------
# 3: Anzeige schreibt nichts
# ---------------------------------------------------------------------------

def test_preview_after_new_year_shows_the_start_number_and_writes_nothing():
    db = _db()
    jahr = berlin_now().year
    seq = load_sequence(db, "invoice")
    seq.next_value, seq.last_year = 50, jahr - 1
    db.commit()
    assert preview_number(db, "invoice") == f"R-{jahr}-0001"
    assert (list(db.new), list(db.dirty)) == ([], [])
    assert _stand(db, "invoice") == (50, jahr - 1)
    assert issue_number(db, "invoice") == f"R-{jahr}-0001"  # erst die Vergabe setzt zurück
    db.commit()
    assert _stand(db, "invoice") == (2, jahr)


def test_preview_above_an_issued_number_writes_nothing():
    db = _db()
    jahr = berlin_now().year
    for _ in range(3):
        _vergeben(db, "project")
    load_sequence(db, "project").next_value = 2  # an den Einstellungen vorbei
    db.commit()
    assert preview_number(db, "project") == f"P-{jahr}-0004"
    assert (list(db.new), list(db.dirty)) == ([], [])
    assert _stand(db, "project")[0] == 2


def test_settings_get_routes_write_nothing(threaded_db_session, router_test_client):
    db = threaded_db_session
    jahr = berlin_now().year
    seq = load_sequence(db, "quote")
    seq.next_value, seq.last_year = 7, jahr - 1
    db.commit()
    client = router_test_client(db, settings_router)
    liste = client.get("/api/settings/number-sequences").json()
    zeile = next(s for s in liste if s["sequence_key"] == "quote")
    assert (zeile["preview"], zeile["next_value"]) == (f"A-{jahr}-0001", 1)  # "Nächste Nr." = was die Vergabe zöge
    assert client.get("/api/settings/number-sequences/quote/preview").json()["preview"] == f"A-{jahr}-0001"
    assert _stand(db, "quote") == (7, jahr - 1)


def test_saving_the_row_unchanged_after_new_year_keeps_the_reset(threaded_db_session, router_test_client):
    """Die Einstellungen zeigen nach dem Jahreswechsel die Startnummer als "Nächste Nr." -- wer die Zeile unverändert speichert,
    überschreibt den Jahreswechsel nicht mit der Nummer des alten Jahres."""
    db = threaded_db_session
    jahr = berlin_now().year
    seq = load_sequence(db, "invoice")
    seq.next_value, seq.last_year = 50, jahr - 1
    db.commit()
    client = router_test_client(db, settings_router)
    zeile = next(s for s in client.get("/api/settings/number-sequences").json() if s["sequence_key"] == "invoice")
    gespeichert = client.put("/api/settings/number-sequences/invoice", json={
        k: zeile[k] for k in ("format_pattern", "start_value", "next_value", "reset_yearly")})
    assert gespeichert.status_code == 200 and gespeichert.json()["preview"] == f"R-{jahr}-0001"
    assert issue_number(db, "invoice") == f"R-{jahr}-0001"


def test_customer_get_routes_create_no_profile_and_draw_no_number(threaded_db_session, router_test_client):
    db = threaded_db_session
    alt = Customer(name="Altkunde ohne Profil", last_name="Altkunde ohne Profil")
    db.add(alt)
    db.commit()
    vorher = _stand(db, "customer")
    client = router_test_client(db, customers_router)
    liste = client.get("/api/customers")
    einzeln = client.get(f"/api/customers/{alt.id}")
    assert (liste.status_code, einzeln.status_code) == (200, 200)
    assert next(c for c in liste.json() if c["id"] == alt.id)["customer_number"] is None
    assert einzeln.json()["customer_number"] is None
    assert db.scalar(select(func.count()).select_from(CustomerProfile)) == 0
    assert _stand(db, "customer") == vorher
    # Speichern legt das Profil an und zieht die Nummer -- ein schreibender Weg.
    gespeichert = client.put(f"/api/customers/{alt.id}", json={"last_name": "Altkunde ohne Profil", "category": "Privatkunde"})
    assert gespeichert.status_code == 200 and gespeichert.json()["customer_number"] == f"K-{berlin_now().year}-0001"


def _routen_funktionen(decorator: str) -> list[tuple[str, ast.FunctionDef, str]]:
    found = []
    for path in sorted((APP / "routers").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for fn in tree.body:
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for dec in fn.decorator_list:
                if (isinstance(dec, ast.Call) and getattr(dec.func, "attr", None) == decorator and dec.args
                        and isinstance(dec.args[0], ast.Constant)):
                    found.append((path.name, fn, dec.args[0].value))
    return found


def _aufrufe_je_funktion() -> dict[str, set[str]]:
    """Name -> aufgerufene Namen, über alle Funktionen in app/ (gleichnamige zusammengefasst -- eher zu viel als zu wenig)."""
    calls: dict[str, set[str]] = {}
    for path in APP.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for fn in ast.walk(tree):
            if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                target = calls.setdefault(fn.name, set())
                for node in ast.walk(fn):
                    if isinstance(node, ast.Call):
                        name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
                        if name:
                            target.add(name)
    return calls


def _erreicht(start: str, ziel: str, calls: dict[str, set[str]]) -> list[str] | None:
    """Ein Aufrufweg von start nach ziel, sonst None."""
    weg, gesehen = {start: [start]}, {start}
    offen = [start]
    while offen:
        name = offen.pop()
        for callee in calls.get(name, ()):
            if callee == ziel:
                return weg[name] + [ziel]
            if callee in calls and callee not in gesehen:
                gesehen.add(callee)
                weg[callee] = weg[name] + [callee]
                offen.append(callee)
    return None


# GET-Endpunkte, die eine Nummer ziehen dürfen -- mit Grund; darf nur kürzer werden.
GET_MIT_NUMMER: dict[str, str] = {}


def test_no_get_route_reaches_issue_number():
    calls = _aufrufe_je_funktion()
    assert _erreicht("post_send_invoice", "issue_number", calls), "Suche läuft ins Leere"
    gets = _routen_funktionen("get")
    assert len(gets) > 150
    funde = sorted(f"{datei}::{fn.name} ({pfad}): {' -> '.join(weg)}" for datei, fn, pfad in gets
                   if (weg := _erreicht(fn.name, "issue_number", calls)) and pfad not in GET_MIT_NUMMER)
    assert funde == [], "Eine Anzeige darf nie eine Nummer verbrauchen:\n" + "\n".join(funde)


# ---------------------------------------------------------------------------
# Festlegung 1.8.74 Nr. 2, geändert: Überspringen nicht still
# ---------------------------------------------------------------------------

def test_skipping_issued_numbers_is_logged_with_sequence_and_numbers(caplog):
    db = _db()
    jahr = berlin_now().year
    for _ in range(3):
        _vergeben(db, "invoice")
    load_sequence(db, "invoice").next_value = 2  # an den Einstellungen vorbei
    db.commit()
    with caplog.at_level(logging.WARNING, logger="app.settings"):
        nummer = issue_number(db, "invoice")
    assert nummer == f"R-{jahr}-0004"
    assert [r.getMessage() for r in caplog.records if r.name == "app.settings"] == [
        f"Nummernkreis invoice: nächste Nummer R-{jahr}-0002 lag auf oder unter einer vergebenen -- übersprungen: "
        f"R-{jahr}-0002 bis R-{jahr}-0003, vergeben wird R-{jahr}-0004."]


def test_skipping_one_number_names_it_once(caplog):
    db = _db()
    jahr = berlin_now().year
    _vergeben(db, "order")
    _vergeben(db, "order")
    load_sequence(db, "order").next_value = 2
    db.commit()
    with caplog.at_level(logging.WARNING, logger="app.settings"):
        assert issue_number(db, "order") == f"AUF-{jahr}-0003"
    assert [r.getMessage() for r in caplog.records if r.name == "app.settings"] == [
        f"Nummernkreis order: nächste Nummer AUF-{jahr}-0002 lag auf oder unter einer vergebenen -- übersprungen: "
        f"AUF-{jahr}-0002, vergeben wird AUF-{jahr}-0003."]


@pytest.mark.parametrize("key", sorted(DEFAULT_SEQUENCES))
def test_normal_issuing_logs_nothing(key, caplog):
    db = _db()
    with caplog.at_level(logging.WARNING, logger="app.settings"):
        _vergeben(db, key)
        _vergeben(db, key)
    assert [r for r in caplog.records if r.name == "app.settings"] == []


# ---------------------------------------------------------------------------
# 4: Format ohne Jahr nicht mit "Jahreswechsel: auf Startnummer zurück"
# ---------------------------------------------------------------------------

GRUND = ("Ein Format ohne Jahr ({YYYY} oder {YY}) kann zum Jahreswechsel nicht auf die Startnummer zurückgehen -- die Nummern des "
         "neuen Jahres wären dieselben wie die des alten. Bitte das Jahr ins Format aufnehmen oder „fortlaufend“ wählen.")


@pytest.mark.parametrize("key", sorted(DEFAULT_SEQUENCES))
def test_format_without_year_and_yearly_reset_is_rejected(key):
    db = _db()
    vorher = load_sequence(db, key)
    stand = (vorher.format_pattern, vorher.next_value, vorher.reset_yearly)
    with pytest.raises(YearlyResetWithoutYear) as exc:
        update_sequence(db, key, format_pattern="X-{NNNN}", start_value=1, next_value=5, reset_yearly=True)
    assert str(exc.value) == GRUND
    db.rollback()
    db.expire_all()
    seq = load_sequence(db, key)
    assert (seq.format_pattern, seq.next_value, seq.reset_yearly) == stand


def test_format_without_year_continuing_or_with_short_year_is_fine():
    db = _db()
    assert update_sequence(db, "inquiry", format_pattern="ANF-{NNNN}", start_value=1, next_value=1,
                           reset_yearly=False).format_pattern == "ANF-{NNNN}"
    assert update_sequence(db, "inquiry", format_pattern="ANF-{YY}-{NNNN}", start_value=1, next_value=1,
                           reset_yearly=True).format_pattern == "ANF-{YY}-{NNNN}"


def test_invalid_format_is_still_422_before_the_year_check(threaded_db_session, router_test_client):
    client = router_test_client(threaded_db_session, settings_router)
    kaputt = client.put("/api/settings/number-sequences/invoice", json={
        "format_pattern": "R-ohne-Nummer", "start_value": 1, "next_value": 1, "reset_yearly": True})
    assert kaputt.status_code == 422


def test_settings_route_answers_409_with_the_reason(threaded_db_session, router_test_client):
    client = router_test_client(threaded_db_session, settings_router)
    antwort = client.put("/api/settings/number-sequences/invoice", json={
        "format_pattern": "R-{NNNN}", "start_value": 1, "next_value": 1, "reset_yearly": True})
    assert (antwort.status_code, antwort.json()["detail"]) == (409, GRUND)
    assert issubclass(YearlyResetWithoutYear, ValueError) and issubclass(NumberBelowExisting, ValueError)
    assert threaded_db_session.scalar(select(NumberSequence.format_pattern)
                                      .where(NumberSequence.sequence_key == "invoice")) == "R-{YYYY}-{NNNN}"


def test_outdated_sentence_is_gone_from_the_settings_page():
    text = (APP / "templates" / "settings.html").read_text(encoding="utf-8")
    assert "werden bereits gespeichert und später vom jeweiligen Modul verwendet" not in text
