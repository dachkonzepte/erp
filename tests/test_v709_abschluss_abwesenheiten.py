"""Version 1.9.309 (Lohn L2a, Punkt 2; Antwort 10 des Befunds L2): Abwesenheiten und Ausfalltage nach dem Abschluss gesperrt wie die Zeitbuchungen.

    gesperrt    berührt eine Abwesenheit einen Tag bis „Abgeschlossen bis“, legt sie nur der Admin an, genehmigt und löscht sie -- jeder Weg: Antrag unter
                „Zeiten“ und „Meine Zeiten“, Sammeleintrag, „Abwesenheit eintragen“ auf der Plantafel, Ausfalltag Schlechtwetter und sein Bestätigen;
                403 mit „Die Zeiterfassung ist bis TT.MM.JJJJ abgeschlossen. Abwesenheiten in diesem Zeitraum nur durch einen Administrator.“, nichts
                gespeichert (bis 1.9.308 ging das alles auch im abgeschlossenen Monat -- Befund L2, 7.1)
    frei        ein offener Antrag zählt nirgends: ihn abzulehnen oder zurückzuziehen bleibt frei; nach dem Abschluss alles wie bisher
    eine Regel  app/permissions.py::darf_im_abschluss_aendern() -- dieselbe für die Zeitbuchungen; die Geschäftslogik sperrt ohne Angabe (Vorgabe)
Stehende Uhr 10.11.2026 (fester_tag), abgeschlossen bis 31.10.2026; Mo 26.10.2026 liegt im abgeschlossenen Zeitraum, Mo 16.11.2026 nicht.
"""

import ast
from datetime import date
from pathlib import Path

import pytest

from app.absence_requests import AbschlussGesperrt, create_request, eintragen, review_request
from app.models import EmployeeAbsence, EmployeeAbsenceRequest, TeamEmployee, TimeTrackingSettings
from app.permissions import darf_im_abschluss_aendern
from app.routers import absence_requests as absence_router
from app.routers.planning import router as planning_router
from app.routers.schlechtwetter import router as schlechtwetter_router
from tests.test_v589_sammel_und_halber_tag import welt  # noqa: F401  (Fixture)

ROOT = Path(__file__).resolve().parent.parent
ZU, OFFEN = date(2026, 10, 26), date(2026, 11, 16)
MELDUNG = "Die Zeiterfassung ist bis 31.10.2026 abgeschlossen. Abwesenheiten in diesem Zeitraum nur durch einen Administrator."


@pytest.fixture
def w(welt):  # noqa: F811
    db = welt["db"]
    db.get(TimeTrackingSettings, 1).locked_until = date(2026, 10, 31)
    db.add(TeamEmployee(team_id=welt["team"].id, employee_id=welt["kai"].id, is_crew_leader=True))
    db.commit()
    return welt


def _als(w, rolle, wer=None):
    w["db"].commit()
    return w["client"](w["db"], absence_router.router, planning_router, schlechtwetter_router, role=rolle, employee_id=w[wer].id if wer else None,
                       user_id=9)


def _zaehlen(w):
    w["db"].expire_all()
    return w["db"].query(EmployeeAbsenceRequest).count(), w["db"].query(EmployeeAbsence).count()


def _wege(w, tag):
    t, mia = tag.isoformat(), w["mia"].id
    return {
        "antrag": ("/api/absence-requests", {"employee_id": mia, "absence_category": "urlaub", "start_date": t, "end_date": t}),
        "sammel": ("/api/absence-requests/sammel", {"employee_ids": [mia, w["tom"].id], "absence_category": "urlaub", "start_date": t, "end_date": t}),
        "plantafel": ("/api/planning/absences", {"employee_id": mia, "absence_category": "urlaub", "start_date": t, "end_date": t}),
        "schlechtwetter": ("/api/schlechtwetter", {"employee_ids": [mia], "tag": t, "trotzdem": True}),
    }


@pytest.mark.parametrize("weg", ["antrag", "sammel", "plantafel", "schlechtwetter"])
def test_buero_finanzen_im_abschluss_gesperrt(w, weg):
    vorher = _zaehlen(w)
    pfad, body = _wege(w, ZU)[weg]
    r = _als(w, "buero_finanzen").post(pfad, json=body)
    assert (r.status_code, r.json()["detail"]) == (403, MELDUNG), r.text
    assert _zaehlen(w) == vorher
    pfad, body = _wege(w, OFFEN)[weg]  # nach dem Abschluss wie bisher
    assert _als(w, "buero_finanzen").post(pfad, json=body).status_code == 200


@pytest.mark.parametrize("weg", ["antrag", "sammel", "plantafel", "schlechtwetter"])
def test_admin_auch_im_abschluss(w, weg):
    vorher = _zaehlen(w)
    pfad, body = _wege(w, ZU)[weg]
    r = _als(w, "admin").post(pfad, json=body)
    assert r.status_code == 200, r.text
    antraege, abwesenheiten = _zaehlen(w)
    assert antraege > vorher[0] and abwesenheiten == vorher[1] + (0 if weg == "antrag" else len(body.get("employee_ids", [0])))  # unter „Zeiten“ ein Antrag


def test_monteurin_und_buero_auftrag_fuer_sich(w):
    for rolle in ("field", "buero_auftrag"):
        r = _als(w, rolle, "mia").post("/api/absence-requests", json={"employee_id": w["mia"].id, "absence_category": "krankheit",
                                                                      "start_date": "2026-10-30", "end_date": "2026-11-02"})
        assert (r.status_code, r.json()["detail"]) == (403, MELDUNG), (rolle, r.text)  # ein Tag im abgeschlossenen Zeitraum genügt


def test_kolonnenfuehrer_schlechtwetter_eintragen_und_bestaetigen(w):
    db = w["db"]
    kai = _als(w, "field", "kai")
    r = kai.post("/api/schlechtwetter", json={"employee_ids": [w["mia"].id], "tag": ZU.isoformat(), "trotzdem": True})
    assert (r.status_code, r.json()["detail"]) == (403, MELDUNG), r.text
    # ein Antrag, gestellt vor dem Abschluss: bestätigen gesperrt, ablehnen frei
    db.get(TimeTrackingSettings, 1).locked_until = None
    db.commit()
    tom = _als(w, "field", "tom")
    antraege = [tom.post("/api/schlechtwetter", json={"employee_ids": [w["tom"].id], "tag": t}).json()["antraege"][0]["id"]
                for t in ("2026-10-26", "2026-10-27")]
    db.get(TimeTrackingSettings, 1).locked_until = date(2026, 10, 31)
    db.commit()
    r = kai.post(f"/api/schlechtwetter/{antraege[0]}/entscheiden", json={"decision": "approved"})
    assert (r.status_code, r.json()["detail"]) == (403, MELDUNG), r.text
    assert kai.post(f"/api/schlechtwetter/{antraege[1]}/entscheiden", json={"decision": "rejected"}).status_code == 200
    assert _als(w, "admin").post(f"/api/schlechtwetter/{antraege[0]}/entscheiden", json={"decision": "approved"}).status_code == 200


def test_offenen_antrag_zurueckziehen_frei_genehmigen_nur_admin(w):
    db = w["db"]
    db.get(TimeTrackingSettings, 1).locked_until = None
    db.commit()
    mia = _als(w, "field", "mia")
    antraege = [mia.post("/api/absence-requests", json={"employee_id": w["mia"].id, "absence_category": "urlaub", "start_date": t,
                                                       "end_date": t}).json()["id"] for t in ("2026-10-26", "2026-10-27")]
    db.get(TimeTrackingSettings, 1).locked_until = date(2026, 10, 31)
    db.commit()
    assert mia.delete(f"/api/absence-requests/{antraege[0]}").status_code == 200  # zurückziehen
    assert _als(w, "admin").post(f"/api/absence-requests/{antraege[1]}/review", json={"decision": "approved"}).status_code == 200
    # löschen: nur der Admin (ohnehin), auch im abgeschlossenen Zeitraum
    abwesenheit = db.query(EmployeeAbsence).one()
    assert _als(w, "admin").delete(f"/api/planning/absences/{abwesenheit.id}").status_code == 200


def test_geschaeftslogik_sperrt_ohne_angabe(w):
    """Die Vorgabe sperrt: wer abschluss_erlaubt nicht setzt, bekommt AbschlussGesperrt -- auch beim Genehmigen und Löschen."""
    db, mia = w["db"], w["mia"]
    with pytest.raises(AbschlussGesperrt):
        create_request(db, employee_id=mia.id, absence_category="urlaub", start_date=ZU, end_date=ZU)
    with pytest.raises(AbschlussGesperrt):
        eintragen(db, gleich_genehmigt=True, employee_id=mia.id, absence_category="urlaub", start_date=ZU, end_date=ZU)
    antrag = create_request(db, employee_id=mia.id, absence_category="urlaub", start_date=ZU, end_date=ZU, abschluss_erlaubt=True)
    with pytest.raises(AbschlussGesperrt):
        review_request(db, antrag.id, decision="approved", reviewed_by_user_id=None)
    db.rollback()
    review_request(db, antrag.id, decision="approved", reviewed_by_user_id=None, abschluss_erlaubt=True)
    from app.absence_requests import abwesenheit_loeschen
    with pytest.raises(AbschlussGesperrt):
        abwesenheit_loeschen(db, db.query(EmployeeAbsence).one().id)


def test_eine_regel_fuer_zeiten_und_abwesenheiten():
    class Konto:
        def __init__(self, rolle):
            self.role = rolle
    assert [darf_im_abschluss_aendern(Konto(r)) for r in ("admin", "buero_finanzen", "buero_auftrag", "field")] == [True, False, False, False]
    assert darf_im_abschluss_aendern(None) is True
    zeiten = (ROOT / "app/routers/time_tracking.py").read_text(encoding="utf-8")
    assert "    if darf_im_abschluss_aendern(user):\n        return" in zeiten


AUFRUFE = {"create_absence_request_row", "sammel_eintragen", "review_absence_request_row", "eintragen", "abwesenheit_loeschen", "entscheiden"}


def test_jeder_router_gibt_die_rolle_mit():
    """Jeder Aufruf eines anlegenden, genehmigenden oder löschenden Wegs in den Routern setzt abschluss_erlaubt aus darf_im_abschluss_aendern()."""
    gefunden = []
    for name in ("absence_requests.py", "planning.py", "schlechtwetter.py"):
        baum = ast.parse((ROOT / "app/routers" / name).read_text(encoding="utf-8"))
        for knoten in ast.walk(baum):
            if isinstance(knoten, ast.Call) and isinstance(knoten.func, ast.Name) and knoten.func.id in AUFRUFE:
                wert = next((k.value for k in knoten.keywords if k.arg == "abschluss_erlaubt"), None)
                assert isinstance(wert, ast.Call) and getattr(wert.func, "id", None) == "darf_im_abschluss_aendern", (name, knoten.func.id, knoten.lineno)
                gefunden.append((name, knoten.func.id))
    assert sorted(gefunden) == sorted([("absence_requests.py", "create_absence_request_row"), ("absence_requests.py", "sammel_eintragen"),
                                       ("absence_requests.py", "review_absence_request_row"), ("planning.py", "eintragen"),
                                       ("planning.py", "abwesenheit_loeschen"), ("schlechtwetter.py", "eintragen"), ("schlechtwetter.py", "entscheiden")])
