"""Version 1.9.152 (Stufe 6, R1 Nachrunde, Punkt 3): ein offener Antrag ist ein Hinweis „Antrag offen“.

    Hinweis     beim Speichern 200 ohne Rückfrage, in der Antwort und auf der Tafel; auch mit „trotzdem“ nichts anderes
    Kapazität   zählt nicht: dieselben Stunden je Tag wie ohne Antrag, der Balken ist nicht rot, conflict_count bleibt 0
    Art         nur für Admin und Büro – Finanzen (im Text und im ganzen JSON), Büro – Auftrag nur die Person
    Grenzen     zurückgezogen, abgelehnt, außerhalb des Zeitraums: kein Hinweis; genehmigt: Warnung wie jede Abwesenheit
    Abfragen    eine Abfrage für alle Anträge, nicht je Einsatz
"""

from datetime import timedelta

import pytest
from sqlalchemy import event

from app.absence_requests import cancel_request, create_request, review_request
from app.planning import planning_board
from app.routers.planning import router as planning_router
from tests.test_v563_konflikte_beim_speichern import MONTAG, _body, _kolonne, _person, setup_order


@pytest.fixture()
def tafel(threaded_db_session, router_test_client):
    db = threaded_db_session
    return db, router_test_client(db, planning_router)


def _antrag(db, person, von=MONTAG, bis=None, kategorie="krankheit", art="Krankheit"):
    return create_request(db, employee_id=person.id, absence_type=art, absence_category=kategorie, start_date=von, end_date=bis or von)


def _tafel_daten(db):
    return planning_board(db, MONTAG, MONTAG + timedelta(days=13))


def test_offener_antrag_200_mit_hinweis_ohne_rueckfrage(tafel):
    db, client = tafel
    tom = _person(db, "M-1", "Tom")
    _antrag(db, tom)
    antwort = client.post("/api/planning/slots", json=_body(setup_order(db, "1"), _kolonne(db, "A", [tom])))
    assert antwort.status_code == 200, antwort.text
    daten = antwort.json()
    assert daten["warnungen"] == []
    assert [(k["type"], k["stufe"], k["label"], k["date"]) for k in daten["hinweise"]] == [("antrag_offen", "hinweis", "Tom Test · Krankheit", MONTAG.isoformat())]


def test_der_hinweis_nennt_den_ersten_tag_im_einsatz_und_steht_auf_der_tafel(tafel):
    db, client = tafel
    tom = _person(db, "M-1", "Tom")
    _antrag(db, tom, von=MONTAG - timedelta(days=3), bis=MONTAG + timedelta(days=1))
    client.post("/api/planning/slots", json=_body(setup_order(db, "1"), _kolonne(db, "A", [tom])))
    einsatz = _tafel_daten(db)["slots"][0]
    assert [(k["type"], k["date"]) for k in einsatz["conflicts"]] == [("antrag_offen", MONTAG)]


def test_keine_kapazitaet_nicht_rot_nicht_gezaehlt(tafel):
    """Dieselben Stunden je Tag wie ohne Antrag -- genehmigt wäre die Kapazität der Person weg."""
    db, client = tafel
    tom = _person(db, "M-1", "Tom")
    team = _kolonne(db, "A", [tom])
    client.post("/api/planning/slots", json=_body(setup_order(db, "1"), team, planned_hours="16"))
    vorher = _tafel_daten(db)
    antrag = _antrag(db, tom, bis=MONTAG + timedelta(days=2))
    nachher = _tafel_daten(db)
    assert nachher["team_capacity"] == vorher["team_capacity"]
    assert nachher["employee_capacity"] == vorher["employee_capacity"]
    assert nachher["conflict_count"] == 0

    review_request(db, antrag.id, decision="approved", reviewed_by_user_id=None)
    genehmigt = _tafel_daten(db)
    assert genehmigt["conflict_count"] == 1  # Gegenstück: jetzt zählt er
    assert genehmigt["team_capacity"][str(team.id)][MONTAG.isoformat()]["capacity_hours"] == 0


def test_genehmigt_ist_eine_warnung(tafel):
    db, client = tafel
    tom = _person(db, "M-1", "Tom")
    review_request(db, _antrag(db, tom).id, decision="approved", reviewed_by_user_id=None)
    antwort = client.post("/api/planning/slots", json=_body(setup_order(db, "1"), _kolonne(db, "A", [tom])))
    assert antwort.status_code == 409
    assert [k["type"] for k in antwort.json()["warnungen"]] == ["absence"]


@pytest.mark.parametrize("status", ["zurueckgezogen", "abgelehnt", "ausserhalb"])
def test_kein_hinweis(tafel, status):
    db, client = tafel
    tom = _person(db, "M-1", "Tom")
    if status == "zurueckgezogen":
        cancel_request(db, _antrag(db, tom).id)
    elif status == "abgelehnt":
        review_request(db, _antrag(db, tom).id, decision="rejected", reviewed_by_user_id=None)
    else:
        _antrag(db, tom, von=MONTAG + timedelta(days=30))
    antwort = client.post("/api/planning/slots", json=_body(setup_order(db, "1"), _kolonne(db, "A", [tom])))
    assert antwort.status_code == 200 and antwort.json()["hinweise"] == []


def test_nur_die_personen_der_kolonne(tafel):
    db, client = tafel
    tom, mia = _person(db, "M-1", "Tom"), _person(db, "M-2", "Mia")
    _antrag(db, mia)
    antwort = client.post("/api/planning/slots", json=_body(setup_order(db, "1"), _kolonne(db, "A", [tom])))
    assert antwort.json()["hinweise"] == []


@pytest.mark.parametrize("rolle, sichtbar", [("admin", True), ("buero_finanzen", True), ("buero_auftrag", False)])
def test_art_nur_fuer_admin_und_finanzen(threaded_db_session, router_test_client, rolle, sichtbar):
    db = threaded_db_session
    tom = _person(db, "M-1", "Tom")
    _antrag(db, tom, kategorie="krankheit", art="Krankheit")
    client = router_test_client(db, planning_router, role=rolle)
    antwort = client.post("/api/planning/slots", json=_body(setup_order(db, "1"), _kolonne(db, "A", [tom])))
    assert antwort.status_code == 200, antwort.text
    tafel_antwort = client.get("/api/planning", params={"start": MONTAG.isoformat(), "end": (MONTAG + timedelta(days=13)).isoformat()})
    assert tafel_antwort.status_code == 200, tafel_antwort.text
    assert antwort.json()["hinweise"][0]["label"] == ("Tom Test · Krankheit" if sichtbar else "Tom Test")
    assert tafel_antwort.json()["slots"][0]["conflicts"][0]["label"] == ("Tom Test · Krankheit" if sichtbar else "Tom Test")
    # nirgends sonst in der Antwort: weder die Art noch das interne Hilfsfeld
    for text in (antwort.text, tafel_antwort.text):
        assert "label_redacted" not in text
        assert ("Krankheit" in text) is sichtbar


def test_eine_abfrage_fuer_alle_antraege(tafel):
    """Mehr Einsätze und Anträge, gleich viele Abfragen der Antragstabelle."""
    db, client = tafel

    def _zaehlen():
        zahl = []
        def _anweisung(conn, cursor, statement, parameters, context, executemany):
            if "employee_absence_requests" in statement:
                zahl.append(statement)
        event.listen(db.get_bind(), "before_cursor_execute", _anweisung)
        try:
            _tafel_daten(db)
        finally:
            event.remove(db.get_bind(), "before_cursor_execute", _anweisung)
        return len(zahl)

    for i in range(4):
        person = _person(db, f"M-{i}", f"P{i}")
        _antrag(db, person)
        assert client.post("/api/planning/slots", json=_body(setup_order(db, str(i)), _kolonne(db, f"K{i}", [person]))).status_code == 200
    assert _zaehlen() == 1


def test_seite_zeigt_den_hinweis_ohne_rot():
    from pathlib import Path
    seite = (Path(__file__).resolve().parent.parent / "app" / "templates" / "planning.html").read_text(encoding="utf-8")
    assert "antrag_offen:'Antrag offen: '" in seite
    assert "filter(c=>c.type==='antrag_offen')" in seite
