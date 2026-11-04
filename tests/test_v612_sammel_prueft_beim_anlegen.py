"""Version 1.9.205 (Lohn L1a, Stufe 4, Punkt 4; Festlegung 1.9.171 Nr. 5): der Sammeleintrag prüft schon beim Anlegen, wer im Zeitraum abwesend
ist oder einen offenen Antrag hat -- alles oder nichts, jede Person genannt, auch bei Büro – Finanzen.

    vorher    beim Admin fiel „schon abwesend“ beim Genehmigen auf (mit Namen), bei Büro – Finanzen entstanden offene Anträge (200), „schon
              abwesend“ scheiterte erst bei der Entscheidung des Admins
    jetzt     app/absence_requests.py::sammel_eintragen() fragt je Person zuerst belegt() -- 422 mit Liste, nichts angelegt; die Prüfung beim
              Entscheiden bleibt (zeitgleiche Einträge von anderer Seite); seit 1.9.208 prüft der Einzelantrag ebenso (1.9.205–1.9.207 blieb er,
              wie er seit vor 1.3.32 war)
    Silvester die Rückfrage (1.9.176) kommt erst, wenn für keine Person etwas dagegen spricht -- vorher die Liste

Feste Tage: 28.–30.12.2026 (Urlaub, wie tests/test_v589_sammel_und_halber_tag.py).
"""

from datetime import date

import pytest

from app import absence_requests
from app.absence_requests import create_request, review_request
from app.models import EmployeeAbsence, EmployeeAbsenceRequest
from tests.test_v589_sammel_und_halber_tag import _als, _sammel, welt  # noqa: F401  (Fixture)

TAG = date(2026, 12, 29)


def _zaehlen(w):
    w["db"].expire_all()
    return w["db"].query(EmployeeAbsenceRequest).count(), w["db"].query(EmployeeAbsence).count()


def _mia_abwesend_tom_offen(w):
    """Mia hat am 29.12. Urlaub (genehmigt), Tom dort einen offenen Antrag (Krankheit), Kai ist frei."""
    db = w["db"]
    review_request(db, create_request(db, employee_id=w["mia"].id, absence_category="urlaub", start_date=TAG, end_date=TAG).id,
                   decision="approved", reviewed_by_user_id=None)
    create_request(db, employee_id=w["tom"].id, absence_category="krankheit", start_date=TAG, end_date=TAG)


@pytest.mark.parametrize("rolle", ["buero_finanzen", "admin"])
def test_jede_person_schon_beim_anlegen(welt, rolle):  # noqa: F811
    _mia_abwesend_tom_offen(welt)
    vorher = _zaehlen(welt)
    r = _sammel(_als(welt, rolle), welt["kai"], welt["mia"], welt["tom"])
    assert r.status_code == 422, r.text
    assert r.json()["liste"] == [{"employee_id": welt["mia"].id, "text": "Mia Monteurin: am 29.12.2026 bereits abwesend"},
                                 {"employee_id": welt["tom"].id, "text": "Tom Monteur: am 29.12.2026 bereits ein offener Antrag"}]
    assert r.json()["detail"] == ("Nicht eingetragen: Mia Monteurin: am 29.12.2026 bereits abwesend; Tom Monteur: am 29.12.2026 bereits ein "
                                  "offener Antrag.")
    assert _zaehlen(welt) == vorher  # auch für Kai kein Antrag


def test_ohne_kategorie_in_der_meldung(welt):  # noqa: F811
    """Toms offener Antrag ist eine Krankheit -- die Meldung sagt nur „offener Antrag“."""
    _mia_abwesend_tom_offen(welt)
    r = _sammel(_als(welt, "buero_finanzen"), welt["tom"])
    assert r.status_code == 422 and "rank" not in r.text, r.text


def test_tage_der_ueberschneidung(welt):  # noqa: F811
    """Kai hat vom 21.12. bis 02.01. Urlaub (über Silvester, beantwortet): genannt werden die Tage des Sammeleintrags, die betroffen sind."""
    db = welt["db"]
    review_request(db, create_request(db, employee_id=welt["kai"].id, absence_category="urlaub", start_date=date(2026, 12, 21),
                                      end_date=date(2027, 1, 2), kalendertag_urlaub=True).id, decision="approved", reviewed_by_user_id=None)
    r = _sammel(_als(welt, "buero_finanzen"), welt["mia"], welt["kai"])
    assert [x["text"] for x in r.json()["liste"]] == ["Kai Kolonne: vom 28.12. bis 30.12.2026 bereits abwesend"], r.text


def test_silvester_erst_nach_der_liste(welt):  # noqa: F811
    """Über Silvester ohne Antwort: ist Mia schon abwesend, kommt zuerst die Liste (422) -- ohne Mia die Rückfrage (409), mit Antwort 200."""
    _mia_abwesend_tom_offen(welt)
    client = _als(welt, "buero_finanzen")
    ueber = {"start_date": "2026-12-28", "end_date": "2027-01-04"}
    r = _sammel(client, welt["kai"], welt["mia"], **ueber)
    assert r.status_code == 422, r.text
    assert [x["employee_id"] for x in r.json()["liste"]] == [welt["mia"].id]
    vorher = _zaehlen(welt)
    r = _sammel(client, welt["kai"], **ueber)
    assert (r.status_code, "rueckfrage" in r.json()) == (409, True), r.text
    assert _zaehlen(welt) == vorher
    r = _sammel(client, welt["kai"], kalendertag_urlaub=True, **ueber)
    assert (r.status_code, [x["status"] for x in r.json()]) == (200, ["pending"]), r.text


def test_entscheiden_prueft_weiter(welt):  # noqa: F811
    """Büro – Finanzen stellt für Kai einen Sammelantrag; danach kommt zeitgleich von anderer Seite eine Abwesenheit dazu -- das Genehmigen des
    Admins lehnt weiter ab (die Prüfung beim Entscheiden bleibt)."""
    r = _sammel(_als(welt, "buero_finanzen"), welt["kai"])
    assert r.status_code == 200, r.text
    antrag = r.json()[0]["id"]
    welt["db"].add(EmployeeAbsence(employee_id=welt["kai"].id, absence_type="Urlaub", absence_category="urlaub", start_date=TAG, end_date=TAG))
    welt["db"].commit()
    r = _als(welt).post(f"/api/absence-requests/{antrag}/review", json={"decision": "approved"})
    assert r.status_code == 422 and "bereits eine genehmigte Abwesenheit" in r.json()["detail"], r.text


def test_zweiter_schritt_beim_admin(welt, monkeypatch):  # noqa: F811
    """Sieht belegt() einen zeitgleichen Eintrag nicht, fängt ihn beim Admin das Genehmigen ab -- alles oder nichts, mit Namen."""
    _mia_abwesend_tom_offen(welt)
    monkeypatch.setattr(absence_requests, "belegt", lambda *a, **k: None)
    vorher = _zaehlen(welt)
    r = _sammel(_als(welt), welt["kai"], welt["mia"])
    assert r.status_code == 422, r.text
    assert r.json()["liste"][0]["text"].startswith("Mia Monteurin: Für diesen Mitarbeiter besteht im beantragten Zeitraum bereits")
    assert _zaehlen(welt) == vorher


def test_einzelantrag_wie_der_sammeleintrag(welt):  # noqa: F811
    """Seit 1.9.208 (L1a Stufe 5, Punkt 1): auch der Einzelantrag von Büro – Finanzen für eine abwesende Person wird beim Anlegen abgelehnt,
    mit Namen und Tag wie im Sammeleintrag (1.9.205: ein offener Antrag, abgelehnt erst bei der Entscheidung des Admins)."""
    _mia_abwesend_tom_offen(welt)
    vorher = _zaehlen(welt)
    r = _als(welt, "buero_finanzen").post("/api/absence-requests", json={"employee_id": welt["mia"].id, "absence_category": "urlaub",
                                                                        "start_date": "2026-12-28", "end_date": "2026-12-30"})
    assert (r.status_code, r.json()["detail"]) == (422, "Mia Monteurin: am 29.12.2026 bereits abwesend."), r.text
    assert _zaehlen(welt) == vorher
