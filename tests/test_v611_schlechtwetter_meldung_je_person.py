"""Version 1.9.204 (Lohn L1a, Stufe 4, Punkt 3; Festlegung 1.9.170 Nr. 5): ist jemand am Tag schon abwesend oder hat er dort einen offenen
Antrag, nennt die Meldung des Schlechtwetter-Dialogs jede betroffene Person mit Grund -- wie bei den übrigen Gründen (kein Arbeitstag, keine
Sollzeit, nicht gewerblich).

    vorher    „Nicht eingetragen: Für diesen Mitarbeiter besteht im beantragten Zeitraum bereits eine genehmigte Abwesenheit.“ -- ohne Namen,
              nur der erste (der zweite Schritt warf beim Anlegen)
    jetzt     app/absence_requests.py::belegt() vor dem Anlegen, je Person „Name: am 07.12.2026 bereits abwesend“ bzw. „… bereits ein offener
              Antrag“ -- ohne Kategorie und Art (die Meldung sehen auch Kolonnenführer und Vorarbeiter); alles oder nichts bleibt

Feste Tage wie tests/test_v588_schlechtwetter.py: Mo 07.12.2026, fester Tag der Uhr 10.11.2026.
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app import absence_requests
from app.absence_requests import belegt, create_request, review_request, zeitraum_text
from app.models import EmployeeAbsence, EmployeeAbsenceRequest
from app.sollzeit import zeile_anlegen
from tests.test_v588_schlechtwetter import MO, _abwesenheiten, _als, _eintragen, welt  # noqa: F401  (Fixture)


def _zaehlen(w):
    w["db"].expire_all()
    return w["db"].query(EmployeeAbsenceRequest).count(), w["db"].query(EmployeeAbsence).count()


def _genehmigt(db, emp, kategorie, start, ende, **mehr):
    review_request(db, create_request(db, employee_id=emp.id, absence_category=kategorie, start_date=start, end_date=ende, **mehr).id,
                   decision="approved", reviewed_by_user_id=None)


def test_zeitraum_text():
    assert zeitraum_text(MO, MO) == "am 07.12.2026"
    assert zeitraum_text(date(2026, 12, 28), date(2026, 12, 30)) == "vom 28.12. bis 30.12.2026"
    assert zeitraum_text(date(2026, 12, 30), date(2027, 1, 2)) == "vom 30.12.2026 bis 02.01.2027"


def test_jede_abwesende_person_mit_namen(welt):  # noqa: F811
    """Mia und Tom haben am Montag schon Schlechtwetter; Kai, Mia, Tom zusammen: 422, beide genannt, für Kai nichts eingetragen."""
    client = _als(welt)
    assert _eintragen(client, welt["mia"], welt["tom"]).status_code == 200
    vorher = _zaehlen(welt)
    r = _eintragen(client, welt["kai"], welt["mia"], welt["tom"])
    assert r.status_code == 422, r.text
    assert r.json()["liste"] == [{"text": "Mia Monteurin: am 07.12.2026 bereits abwesend"}, {"text": "Tom Monteur: am 07.12.2026 bereits abwesend"}]
    assert r.json()["detail"] == "Nicht eingetragen: Mia Monteurin: am 07.12.2026 bereits abwesend; Tom Monteur: am 07.12.2026 bereits abwesend."
    assert _zaehlen(welt) == vorher
    assert welt["kai"].id not in {a[0] for a in _abwesenheiten(welt)}


def test_nur_der_tag_keine_kategorie(welt):  # noqa: F811
    """Mia ist vom 01. bis 11.12. krank; der Kolonnenführer Kai sieht nur „am 07.12.2026 bereits abwesend“ -- nicht die Krankheit, nicht den
    Zeitraum ihrer Abwesenheit."""
    _genehmigt(welt["db"], welt["mia"], "krankheit", date(2026, 12, 1), date(2026, 12, 11))
    r = _eintragen(_als(welt, "field", "kai"), welt["kai"], welt["mia"])
    assert r.status_code == 422, r.text
    assert [x["text"] for x in r.json()["liste"]] == ["Mia Monteurin: am 07.12.2026 bereits abwesend"]
    assert "rank" not in r.text and "01.12." not in r.text and "11.12." not in r.text


def test_offener_antrag_mit_namen(welt):  # noqa: F811
    """Tom hat für Montag einen offenen Antrag (Urlaub); Kai trägt für die Kolonne ein: Tom genannt, nichts eingetragen."""
    create_request(welt["db"], employee_id=welt["tom"].id, absence_category="urlaub", start_date=MO, end_date=MO)
    vorher = _zaehlen(welt)
    r = _eintragen(_als(welt, "field", "kai"), welt["kai"], welt["mia"], welt["tom"])
    assert r.status_code == 422, r.text
    assert r.json()["liste"] == [{"text": "Tom Monteur: am 07.12.2026 bereits ein offener Antrag"}]
    assert _zaehlen(welt) == vorher


def test_fuer_sich_mit_offenem_antrag(welt):  # noqa: F811
    """Tom beantragt Schlechtwetter für sich, hat aber schon einen offenen Antrag: sein Name und der Grund (bis 1.9.203 ohne Namen)."""
    client = _als(welt, "field", "tom")
    assert _eintragen(client, welt["tom"]).status_code == 200
    r = _eintragen(client, welt["tom"])
    assert (r.status_code, r.json()["detail"]) == (422, "Nicht eingetragen: Tom Monteur: am 07.12.2026 bereits ein offener Antrag."), r.text


def test_zusammen_mit_den_uebrigen_gruenden(welt):  # noqa: F811
    """Mia ohne Sollzeit am Montag, Tom schon abwesend, Bea kaufmännisch, Uwe frei: drei genannt, in der Reihenfolge der Auswahl."""
    zeile_anlegen(welt["db"], welt["mia"].id, date(2026, 12, 1), {"dienstag": Decimal("4")})
    _genehmigt(welt["db"], welt["tom"], "urlaub", MO, MO)
    r = _eintragen(_als(welt), welt["uwe"], welt["tom"], welt["mia"], welt["bea"])
    assert r.status_code == 422, r.text
    assert [x["text"] for x in r.json()["liste"]] == ["Tom Monteur: am 07.12.2026 bereits abwesend", "Mia Monteurin: am 07.12.2026 keine Sollzeit",
                                                      "Bea Buero: Schlechtwetter nur für gewerbliche Mitarbeiter"]
    assert _zaehlen(welt) == (1, 1)


def test_zweiter_schritt_bleibt(welt, monkeypatch):  # noqa: F811
    """Kommt ein Eintrag zeitgleich von anderer Seite (hier: belegt() sieht ihn nicht), fängt ihn weiter das Anlegen bzw. Genehmigen ab --
    alles oder nichts, 422."""
    client = _als(welt)
    assert _eintragen(client, welt["mia"]).status_code == 200
    monkeypatch.setattr(absence_requests, "belegt", lambda *a, **k: None)
    vorher = _zaehlen(welt)
    r = _eintragen(client, welt["tom"], welt["mia"])
    assert r.status_code == 422 and "bereits eine genehmigte Abwesenheit" in r.json()["detail"], r.text
    assert _zaehlen(welt) == vorher


def test_belegt_tage_der_ueberschneidung(welt):  # noqa: F811
    """Die Tage, an denen beides zusammenfällt -- nicht der ganze Zeitraum der vorhandenen Abwesenheit."""
    db = welt["db"]
    _genehmigt(db, welt["mia"], "urlaub", date(2026, 12, 21), date(2027, 1, 8), kalendertag_urlaub=True)  # über Silvester (1.9.176)
    create_request(db, employee_id=welt["tom"].id, absence_category="urlaub", start_date=date(2026, 12, 29), end_date=date(2026, 12, 29))
    assert belegt(db, welt["mia"].id, date(2026, 12, 28), date(2026, 12, 30)) == "vom 28.12. bis 30.12.2026 bereits abwesend"
    assert belegt(db, welt["mia"].id, date(2027, 1, 7), date(2027, 1, 12)) == "vom 07.01. bis 08.01.2027 bereits abwesend"
    assert belegt(db, welt["tom"].id, date(2026, 12, 28), date(2026, 12, 30)) == "am 29.12.2026 bereits ein offener Antrag"
    assert belegt(db, welt["kai"].id, date(2026, 12, 28), date(2026, 12, 30)) is None
    abgelehnt = create_request(db, employee_id=welt["kai"].id, absence_category="urlaub", start_date=MO, end_date=MO)
    review_request(db, abgelehnt.id, decision="rejected", reviewed_by_user_id=None)
    assert belegt(db, welt["kai"].id, MO, MO) is None
    assert db.scalar(select(EmployeeAbsenceRequest.status).where(EmployeeAbsenceRequest.id == abgelehnt.id)) == "rejected"
