"""Version 1.9.104 (Stufe 4, R5b Nachrunde, Punkte 5 und 6): was die Liste „Buchungen“ aus dem Verlauf liest.

    Unterzeile    „Tom Monteur · gebucht von … am …“ wie die Vorlage zeiten-aendern.html -- gebucht hat, wer die Zeit beendet hat (eine gestoppte
                  Zeit) bzw. wer sie angelegt hat; nach einer Änderung dazu „· geändert von … am …“ (nicht die Anfrage, die gebucht hat)
    Dauer         „Dauer · vom Büro“, wenn ein Konto außerhalb der Monteursansicht die Zeit zuletzt gesetzt hat (Stunden, Uhrzeiten, Tag, Pause) --
                  auch beim Ändern einer Buchung der Monteurin (bis 1.9.103 nur, wenn das Büro sie angelegt hatte; Festlegung 1.9.95 Nr. 9
                  ersetzt); eine Notiz der Monteurin danach ändert daran nichts
Der Verlauf schreibt jede Änderung samt Konto und Pfad (app/audit.py; in der Anwendung setzt die Anmeldeschranke Konto und Pfad, hier
_als_konto()).
"""

import json
from contextlib import contextmanager
from datetime import datetime, time, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.audit import reset_audit_context, set_audit_context
from app.models import AppUser, AuditLog
from app.routers import zeiten as zeiten_router
from app.time_tracking import create_manual_entry, start_timer, stop_timer, update_entry
from tests.test_v471_heute_server import welt  # noqa: F401  (Fixture)
from tests.test_v518_zeiten_seite import _node


@contextmanager
def _als_konto(konto, pfad, methode="PUT"):
    """Konto, Pfad und Methode für den Verlauf -- wie die Anmeldeschranke sie je Anfrage setzt."""
    tokens = set_audit_context(user=konto, request=SimpleNamespace(url=SimpleNamespace(path=pfad), method=methode))
    try:
        yield
    finally:
        reset_audit_context(tokens)


@pytest.fixture
def konten(welt):  # noqa: F811
    db = welt["db"]
    k = {"tom": AppUser(username="tom", display_name="Tom Monteur", role="field", employee_id=welt["tom"].id, active=True, password_hash="x"),
         "fin": AppUser(username="fin", display_name="Fin Finanzen", role="buero_finanzen", active=True, password_hash="x")}
    db.add_all(k.values()); db.commit()
    return k


def _zeile(w, entry_id):
    client = w["client"](w["db"], zeiten_router.router, role="buero_finanzen")
    tag = w["gestern"]
    d = client.get("/api/zeiten/buchungen", params={"monat": f"{tag:%Y-%m}"}).json()
    return next(e for e in d["eintraege"] if e["id"] == entry_id)


def _toms_zeit(w, k):
    """Tom startet und stoppt in der Monteursansicht: gestern 07:00–16:30."""
    db, tag = w["db"], w["gestern"]
    with _als_konto(k["tom"], "/api/time-entries/start", "POST"):
        row = start_timer(db, employee_id=w["tom"].id, order_id=w["order"].id, started_at=datetime.combine(tag, time(7)), created_by_user_id=k["tom"].id)
    with _als_konto(k["tom"], f"/api/time-entries/{row.id}/stop", "POST"):
        stop_timer(db, row.id, ended_at=datetime.combine(tag, time(16, 30)))
    return row.id


def _als_dauer(w, k, entry_id, wer="fin", stunden="8"):
    with _als_konto(k[wer], f"/api/time-entries/{entry_id}"):
        update_entry(w["db"], entry_id, employee_id=w["tom"].id, order_id=w["order"].id, work_date=w["gestern"], hours=Decimal(stunden),
                     entry_type="site", break_minutes=45, min_break_minutes=45, als_dauer=True)


def test_gebucht_von_wer_beendet_dann_geaendert_vom_buero(welt, konten):  # noqa: F811
    """Angriff: Büro – Finanzen setzt Toms Buchung (07:00–16:30) auf Dauer -> „Dauer · vom Büro“ und „geändert von Fin Finanzen“ (bis 1.9.103
    nur „Dauer“, Tom hatte sie angelegt). Gegenprobe: vorher gebucht von Tom (beim Stoppen), keine Änderung -- das Stoppen selbst ist das Buchen."""
    eid = _toms_zeit(welt, konten)
    vorher = _zeile(welt, eid)
    stopp = welt["db"].query(AuditLog).filter_by(entity_type="Zeitbuchung", entity_id=str(eid), field_name="status").one()
    assert (vorher["gebucht_von"], vorher["gebucht_am"], vorher["geaendert_von"], vorher["geaendert_am"], vorher["vom_buero"]) == \
        ("Tom Monteur", stopp.occurred_at.isoformat(), None, None, False)
    _als_dauer(welt, konten, eid)
    nachher = _zeile(welt, eid)
    assert (nachher["started_at"], nachher["gebucht_von"], nachher["geaendert_von"], nachher["vom_buero"]) == (None, "Tom Monteur", "Fin Finanzen", True)
    assert nachher["geaendert_am"] is not None and nachher["geaendert_am"] >= nachher["gebucht_am"]


def test_notiz_der_monteurin_laesst_die_dauer_vom_buero(welt, konten):  # noqa: F811
    """Nach der Dauer des Büros ändert Tom nur die Notiz: „geändert von Tom Monteur“, die Dauer bleibt „vom Büro“ (gesetzt hat sie das Büro)."""
    eid = _toms_zeit(welt, konten)
    _als_dauer(welt, konten, eid)
    with _als_konto(konten["tom"], f"/api/time-entries/{eid}"):
        update_entry(welt["db"], eid, employee_id=welt["tom"].id, order_id=welt["order"].id, work_date=welt["gestern"], hours=Decimal("8"),
                     entry_type="site", notes="Rinne", break_minutes=45)
    z = _zeile(welt, eid)
    assert (z["geaendert_von"], z["vom_buero"], z["notes"]) == ("Tom Monteur", True, "Rinne")


@pytest.mark.parametrize("wer, vom_buero", [("tom", False), ("fin", True)])
def test_angelegte_dauer_nach_dem_konto(welt, konten, wer, vom_buero):  # noqa: F811
    """Eine angelegte Dauer: vom Büro nur, wenn ein Büro-Konto sie angelegt hat (die Monteurin trug bis 1.9.59 Dauern ein)."""
    with _als_konto(konten[wer], "/api/time-entries", "POST"):
        row = create_manual_entry(welt["db"], employee_id=welt["tom"].id, order_id=welt["order"].id, work_date=welt["gestern"],
                                  hours=Decimal("6"), created_by_user_id=konten[wer].id)
    z = _zeile(welt, row.id)
    assert (z["vom_buero"], z["gebucht_von"], z["geaendert_von"]) == (vom_buero, konten[wer].display_name, None)


def test_ohne_konto_im_verlauf_der_anleger(welt, konten):  # noqa: F811
    """Testdaten und Skripte schreiben den Verlauf ohne Konto („System“): dann zählt der Anleger der Buchung, ohne ihn kein Name."""
    tag = welt["gestern"]
    row = start_timer(welt["db"], employee_id=welt["tom"].id, order_id=welt["order"].id, started_at=datetime.combine(tag, time(7)))
    stop_timer(welt["db"], row.id, ended_at=datetime.combine(tag, time(9)))
    dauer = create_manual_entry(welt["db"], employee_id=welt["tom"].id, order_id=welt["order"].id, work_date=tag, hours=Decimal("2"),
                                created_by_user_id=konten["fin"].id)
    ohne, mit = _zeile(welt, row.id), _zeile(welt, dauer.id)
    assert (ohne["gebucht_von"], ohne["vom_buero"]) == (None, False)
    assert (mit["gebucht_von"], mit["vom_buero"]) == ("Fin Finanzen", True)


def test_unterzeile_wie_die_vorlage():
    vorweg = "function berlinZeitpunkt(w){return {'2026-10-15T14:31:00':'15.10.2026 16:31','2026-10-26T08:12:00':'26.10.2026 09:12'}[w]||''};"
    js = "return [unterzeile(%s),unterzeile(%s),unterzeile(%s)]"
    gebucht = {"employee_name": "Tom Monteur", "gebucht_von": "Tom Monteur", "gebucht_am": "2026-10-15T14:31:00"}
    geaendert = {**gebucht, "geaendert_von": "Fin Finanzen", "geaendert_am": "2026-10-26T08:12:00"}
    ohne = {"employee_name": "Tom Monteur", "gebucht_von": None, "gebucht_am": "2026-10-15T14:31:00"}
    assert _node(("amText", "unterzeile"), js % (json.dumps(gebucht), json.dumps(geaendert), json.dumps(ohne)), vorweg=vorweg) == [
        "Tom Monteur · gebucht von Tom Monteur am 15.10., 16:31",
        "Tom Monteur · gebucht von Tom Monteur am 15.10., 16:31 · geändert von Fin Finanzen am 26.10., 09:12",
        "Tom Monteur · gebucht am 15.10., 16:31"]
