"""Version 1.9.208 (Lohn L1a, Stufe 5, Punkt 1): jeder Abwesenheitsantrag prüft beim Anlegen, ob die Person im Zeitraum schon abwesend ist oder
einen offenen Antrag hat -- auch der Einzelantrag unter „Zeiten“ und „Meine Zeiten“ und „Abwesenheit eintragen“ auf der Plantafel, wie der
Sammeleintrag (1.9.205). Die Prüfung sitzt in app/absence_requests.py::_antrag_anlegen() (belegt(), Ausnahme Belegt).

    Befund   bis 1.9.207 prüfte das Anlegen nur offene Anträge („Für diesen Zeitraum existiert bereits ein offener Abwesenheitsantrag.“), „schon
             abwesend“ erst das Entscheiden -- so seit vor 1.3.32 (erster Commit), ohne festgehaltenen Grund; 1.9.101 änderte nur, wer für wen
             beantragt. Der einzige denkbare Grund (Krankheit während eines genehmigten Urlaubs als offener Antrag) trägt nicht: genehmigen ließ
             er sich erst, nachdem der Admin den Urlaub gelöscht hatte -- danach geht der Antrag auch jetzt
    Meldung  „Mia Monteurin: am 29.12.2026 bereits abwesend.“ bzw. „… bereits ein offener Antrag.“ -- nur die Tage, keine Kategorie
    bleibt   das Entscheiden prüft weiter selbst (tests/test_v612_sammel_prueft_beim_anlegen.py::test_entscheiden_prueft_weiter)

Feste Tage: Dezember 2026 (wie tests/test_v589_sammel_und_halber_tag.py).
"""

from datetime import date

import pytest

from app.absence_requests import create_request, review_request
from app.models import EmployeeAbsence, EmployeeAbsenceRequest
from app.routers import absence_requests as absence_router
from app.routers.planning import router as planning_router
from tests.test_v589_sammel_und_halber_tag import _als, welt  # noqa: F401  (Fixture)

TAG = date(2026, 12, 29)


def _zaehlen(w):
    w["db"].expire_all()
    return w["db"].query(EmployeeAbsenceRequest).count(), w["db"].query(EmployeeAbsence).count()


def _genehmigt(w, emp, start=TAG, ende=TAG, kategorie="urlaub"):
    db = w["db"]
    return review_request(db, create_request(db, employee_id=emp.id, absence_category=kategorie, start_date=start, end_date=ende).id,
                          decision="approved", reviewed_by_user_id=None)


def _antrag(client, emp, start="2026-12-28", ende="2026-12-30", kategorie="krankheit", pfad="/api/absence-requests"):
    return client.post(pfad, json={"employee_id": emp.id, "absence_category": kategorie, "start_date": start, "end_date": ende})


@pytest.mark.parametrize("rolle, wer", [("field", "mia"), ("buero_finanzen", None), ("admin", None)], ids=["monteurin_fuer_sich", "buero_finanzen",
                                                                                                              "admin"])
def test_einzelantrag_schon_abwesend(welt, rolle, wer):  # noqa: F811
    _genehmigt(welt, welt["mia"])
    vorher = _zaehlen(welt)
    r = _antrag(_als(welt, rolle, wer), welt["mia"])
    assert (r.status_code, r.json()["detail"]) == (422, "Mia Monteurin: am 29.12.2026 bereits abwesend."), r.text
    assert _zaehlen(welt) == vorher


def test_einzelantrag_offener_antrag(welt):  # noqa: F811
    """Neuer Wortlaut für den offenen Antrag (bis 1.9.207 „Für diesen Zeitraum existiert bereits ein offener Abwesenheitsantrag.“)."""
    client = _als(welt, "field", "mia")
    assert _antrag(client, welt["mia"], start="2026-12-29", ende="2026-12-29").status_code == 200
    r = _antrag(client, welt["mia"], kategorie="urlaub")
    assert (r.status_code, r.json()["detail"]) == (422, "Mia Monteurin: am 29.12.2026 bereits ein offener Antrag."), r.text


def test_tage_der_ueberschneidung_ohne_kategorie(welt):  # noqa: F811
    """Mia ist vom 21. bis 23.12. krank; ihr Antrag 22.–28.12. nennt nur die Tage, die zusammenfallen, nicht die Krankheit."""
    _genehmigt(welt, welt["mia"], date(2026, 12, 21), date(2026, 12, 23), kategorie="krankheit")
    r = _antrag(_als(welt, "field", "mia"), welt["mia"], start="2026-12-22", ende="2026-12-28", kategorie="urlaub")
    assert (r.status_code, r.json()["detail"]) == (422, "Mia Monteurin: vom 22.12. bis 23.12.2026 bereits abwesend."), r.text
    assert "rank" not in r.text


@pytest.mark.parametrize("rolle", ["buero_finanzen", "admin"])
def test_plantafel_ebenso(welt, rolle):  # noqa: F811
    """„Abwesenheit eintragen“ auf der Plantafel ist derselbe Weg (1.9.146): Büro – Finanzen legte bis 1.9.207 einen offenen Antrag an, der Admin
    scheiterte beim gleich Genehmigen ohne Namen -- jetzt beide beim Anlegen, mit Namen und Tag."""
    _genehmigt(welt, welt["mia"])
    vorher = _zaehlen(welt)
    client = welt["client"](welt["db"], planning_router, role=rolle, user_id=9)
    r = _antrag(client, welt["mia"], pfad="/api/planning/absences")
    assert (r.status_code, r.json()["detail"]) == (422, "Mia Monteurin: am 29.12.2026 bereits abwesend."), r.text
    assert _zaehlen(welt) == vorher


def test_krankheit_im_urlaub_ueber_den_admin(welt):  # noqa: F811
    """Der einzige denkbare Grund für die frühere Lücke: Krankheit während eines genehmigten Urlaubs. Der Antrag ließ sich auch früher erst
    genehmigen, nachdem der Admin den Urlaub gelöscht hatte -- danach geht er jetzt wie früher."""
    db = welt["db"]
    _genehmigt(welt, welt["mia"], date(2026, 12, 28), date(2026, 12, 30))
    client = _als(welt, "field", "mia")
    assert _antrag(client, welt["mia"], start="2026-12-29").status_code == 422
    urlaub = db.query(EmployeeAbsence).one()
    admin = welt["client"](db, planning_router, absence_router.router, role="admin", user_id=9)
    assert admin.delete(f"/api/planning/absences/{urlaub.id}").status_code == 200
    r = _antrag(client, welt["mia"], start="2026-12-29")
    assert (r.status_code, r.json()["status"]) == (200, "pending"), r.text
    assert admin.post(f"/api/absence-requests/{r.json()['id']}/review", json={"decision": "approved"}).status_code == 200


def test_abgelehnte_und_zurueckgezogene_zaehlen_nicht(welt):  # noqa: F811
    db = welt["db"]
    abgelehnt = create_request(db, employee_id=welt["mia"].id, absence_category="urlaub", start_date=TAG, end_date=TAG)
    review_request(db, abgelehnt.id, decision="rejected", reviewed_by_user_id=None)
    r = _antrag(_als(welt, "field", "mia"), welt["mia"])
    assert r.status_code == 200, r.text
