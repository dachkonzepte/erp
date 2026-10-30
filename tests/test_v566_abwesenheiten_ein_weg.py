"""Version 1.9.146 (Stufe 6, R1, Punkt 4): Abwesenheiten, ein Weg wie unter „Zeiten“.

    Eintragen    „Abwesenheit eintragen“ auf der Tafel legt einen Antrag an: Admin gleich genehmigt (Abwesenheit da), Büro – Finanzen auch für andere (offen), Büro – Auftrag nur für
                 sich (für andere 403), Monteur 403; ohne Mitarbeiter 403 mit dem Hinweis
    Atomar       scheitert das Genehmigen (schon eine Abwesenheit im Zeitraum), bleibt auch kein Antrag zurück -- 422 mit Text
    „Zeiten“     zeigt alle Anträge, auch die aus der Migration (direkt eingetragene); „Löschen“ nur für den Admin an einem genehmigten
    P1           genehmigte Abwesenheit löschen: 200 oder Meldung, nie 500 (auch unter PostgreSQL), der Antrag folgt; nur der Admin; unbekannt 404
    P2           Art, Kategorie und Notiz in der Tafel für Admin und Büro – Finanzen, für Büro – Auftrag nicht
    PUT          entfällt (keine Oberfläche, ändert am Antrag vorbei) -- 405
    Migration    legt je Abwesenheit ohne Antrag einen genehmigten an, zweimal laufen ändert nichts, Rückweg entfernt genau diese; gegen SQLite und PostgreSQL
    Wächter      eine EmployeeAbsence entsteht nur in app/absence_requests.py
"""

import ast
import importlib.util
import os
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import AppUser, Employee, EmployeeAbsence, EmployeeAbsenceRequest
from app.routers.absence_requests import router as antrag_router
from app.routers.planning import router as planning_router
from app.routers.zeiten import router as zeiten_router
from tests.pg_schutz import pg_url_pruefen

ROOT = Path(__file__).resolve().parent.parent
MONTAG = date(2026, 11, 2)


def _person(db, nummer="M-1", name="Mia"):
    emp = Employee(employee_number=nummer, first_name=name, last_name="Test", employee_group="gewerblich", hourly_wage=Decimal("20"), weekly_hours=Decimal("40"), active=True)
    db.add(emp)
    db.commit()
    return emp


def _body(emp, von=MONTAG, bis=None, **mehr):
    return {"employee_id": emp.id, "absence_type": "Krankheit", "absence_category": "krankheit", "start_date": von.isoformat(), "end_date": (bis or von).isoformat(),
            "notes": "Attest liegt vor", **mehr}


@pytest.fixture()
def welt(threaded_db_session, router_test_client):
    db = threaded_db_session
    mia, ole = _person(db), _person(db, "M-2", "Ole")

    def client(rolle="admin", employee_id=None, user_id=None):
        return router_test_client(db, planning_router, antrag_router, zeiten_router, role=rolle, employee_id=employee_id, user_id=user_id)

    return {"db": db, "mia": mia, "ole": ole, "client": client}


def _anzahl(db, modell):
    db.expire_all()
    return db.scalar(select(func.count()).select_from(modell))


def test_admin_gleich_genehmigt(welt):
    db, mia = welt["db"], welt["mia"]
    antwort = welt["client"]("admin").post("/api/planning/absences", json=_body(mia))
    assert antwort.status_code == 200, antwort.text
    daten = antwort.json()
    assert daten["status"] == "approved" and daten["id"] is not None and daten["antrag_id"] is not None
    antrag = db.get(EmployeeAbsenceRequest, daten["antrag_id"])
    assert (antrag.status, antrag.approved_absence_id) == ("approved", daten["id"])
    assert db.get(EmployeeAbsence, daten["id"]).absence_category == "krankheit"


def test_buero_finanzen_auch_fuer_andere_als_offener_antrag(welt):
    db, mia = welt["db"], welt["mia"]
    antwort = welt["client"]("buero_finanzen").post("/api/planning/absences", json=_body(mia))
    assert antwort.status_code == 200, antwort.text
    daten = antwort.json()
    assert (daten["status"], daten["id"]) == ("pending", None)
    assert _anzahl(db, EmployeeAbsence) == 0  # zählt noch nicht auf der Tafel
    assert db.get(EmployeeAbsenceRequest, daten["antrag_id"]).status == "pending"


def test_buero_auftrag_fuer_andere_403_fuer_sich_ein_antrag(welt):
    db, mia, ole = welt["db"], welt["mia"], welt["ole"]
    client = welt["client"]("buero_auftrag", employee_id=mia.id)
    antwort = client.post("/api/planning/absences", json=_body(ole))
    assert antwort.status_code == 403
    assert antwort.json()["detail"] == "Du darfst nur eigene Abwesenheiten beantragen."
    assert _anzahl(db, EmployeeAbsenceRequest) == 0
    antwort = client.post("/api/planning/absences", json=_body(mia))
    assert antwort.status_code == 200, antwort.text
    assert antwort.json()["status"] == "pending"
    assert "absence_type" not in antwort.json()  # „Einmal eintragen, nie wieder lesen“


def test_buero_auftrag_ohne_mitarbeiter_403(welt):
    antwort = welt["client"]("buero_auftrag").post("/api/planning/absences", json=_body(welt["mia"]))
    assert antwort.status_code == 403
    assert "Mitarbeiter" in antwort.json()["detail"]


def test_monteur_403(welt):
    assert welt["client"]("field", employee_id=welt["mia"].id).post("/api/planning/absences", json=_body(welt["mia"])).status_code == 403


def test_ueberlappung_beim_admin_422_und_kein_antrag_bleibt(welt):
    db, mia = welt["db"], welt["mia"]
    client = welt["client"]("admin")
    assert client.post("/api/planning/absences", json=_body(mia)).status_code == 200
    antwort = client.post("/api/planning/absences", json=_body(mia, bis=MONTAG + timedelta(days=2)))
    assert antwort.status_code == 422
    assert "bereits eine genehmigte Abwesenheit" in antwort.json()["detail"]
    assert (_anzahl(db, EmployeeAbsenceRequest), _anzahl(db, EmployeeAbsence)) == (1, 1)


def test_unbekannter_mitarbeiter_422(welt):
    antwort = welt["client"]("admin").post("/api/planning/absences", json={**_body(welt["mia"]), "employee_id": 999999})
    assert antwort.status_code == 422


def test_genehmigte_loeschen_der_antrag_folgt(welt):
    db, mia = welt["db"], welt["mia"]
    client = welt["client"]("admin")
    daten = client.post("/api/planning/absences", json=_body(mia)).json()
    antwort = client.delete(f"/api/planning/absences/{daten['id']}")
    assert antwort.status_code == 200, antwort.text
    assert _anzahl(db, EmployeeAbsence) == 0
    antrag = db.get(EmployeeAbsenceRequest, daten["antrag_id"])
    assert (antrag.status, antrag.approved_absence_id, antrag.review_notes) == ("cancelled", None, "Die genehmigte Abwesenheit wurde gelöscht.")


def test_loeschen_nur_der_admin_und_unbekannt_404(welt):
    db, mia = welt["db"], welt["mia"]
    daten = welt["client"]("admin").post("/api/planning/absences", json=_body(mia)).json()
    for rolle, employee_id in (("buero_finanzen", None), ("buero_auftrag", mia.id)):
        antwort = welt["client"](rolle, employee_id=employee_id).delete(f"/api/planning/absences/{daten['id']}")
        assert antwort.status_code == 403, rolle
        assert antwort.json()["detail"] == "Eine genehmigte Abwesenheit löscht nur der Admin."
    assert _anzahl(db, EmployeeAbsence) == 1
    assert welt["client"]("admin").delete("/api/planning/absences/999999").status_code == 404


def test_abwesenheit_ohne_antrag_laesst_sich_loeschen(welt):
    db, mia = welt["db"], welt["mia"]
    alt = EmployeeAbsence(employee_id=mia.id, absence_type="Urlaub", absence_category="urlaub", start_date=MONTAG, end_date=MONTAG)
    db.add(alt)
    db.commit()
    assert welt["client"]("admin").delete(f"/api/planning/absences/{alt.id}").status_code == 200


def test_put_entfaellt(welt):
    db, mia = welt["db"], welt["mia"]
    daten = welt["client"]("admin").post("/api/planning/absences", json=_body(mia)).json()
    assert welt["client"]("admin").put(f"/api/planning/absences/{daten['id']}", json={"end_date": "2026-11-05"}).status_code == 405


def test_tafel_zeigt_art_und_notiz_nur_finanzen_und_admin(welt):
    """P2: bis 1.9.145 fehlte absence_category in der Antwort -- die Seite zeigte jeder Rolle „Abwesend“."""
    db, mia = welt["db"], welt["mia"]
    welt["client"]("admin").post("/api/planning/absences", json=_body(mia))
    params = {"start": MONTAG.isoformat(), "end": (MONTAG + timedelta(days=13)).isoformat()}
    for rolle in ("admin", "buero_finanzen"):
        zeile = welt["client"](rolle).get("/api/planning", params=params).json()["absences"][0]
        assert (zeile["absence_category"], zeile["absence_type"], zeile["notes"]) == ("krankheit", "Krankheit", "Attest liegt vor"), rolle
    zeile = welt["client"]("buero_auftrag", employee_id=mia.id).get("/api/planning", params=params).json()["absences"][0]
    assert not {"absence_category", "absence_type", "notes"} & set(zeile)


def test_tafel_nennt_die_rechte_der_rolle(welt):
    mia = welt["mia"]
    params = {"start": MONTAG.isoformat(), "end": (MONTAG + timedelta(days=13)).isoformat()}
    rechte = welt["client"]("admin").get("/api/planning", params=params).json()["rechte"]
    assert (rechte["abwesenheit_fuer_andere"], rechte["abwesenheit_loeschen"], rechte["hinweis"]) == (True, True, None)
    rechte = welt["client"]("buero_finanzen").get("/api/planning", params=params).json()["rechte"]
    assert (rechte["abwesenheit_fuer_andere"], rechte["abwesenheit_loeschen"]) == (True, False)
    rechte = welt["client"]("buero_auftrag", employee_id=mia.id).get("/api/planning", params=params).json()["rechte"]
    assert (rechte["abwesenheit_fuer_andere"], rechte["abwesenheit_loeschen"], rechte["eigener_mitarbeiter"]) == (False, False, {"id": mia.id, "name": "Mia Test"})
    rechte = welt["client"]("buero_auftrag").get("/api/planning", params=params).json()["rechte"]
    assert rechte["eigener_mitarbeiter"] is None and "Mitarbeiter" in rechte["hinweis"]


def test_zeiten_zeigt_den_antrag_und_loeschen_nur_dem_admin(welt):
    mia = welt["mia"]
    welt["client"]("admin").post("/api/planning/absences", json=_body(mia))
    offen = welt["client"]("buero_finanzen").post("/api/planning/absences", json=_body(welt["ole"])).json()
    antraege = welt["client"]("admin").get("/api/zeiten/abwesenheiten").json()["antraege"]
    je_status = {a["status"]: a for a in antraege}
    assert set(je_status) == {"approved", "pending"}
    assert je_status["approved"]["darf_loeschen"] is True
    assert je_status["pending"]["darf_loeschen"] is False and je_status["pending"]["id"] == offen["antrag_id"]
    assert all(a["darf_loeschen"] is False for a in welt["client"]("buero_finanzen").get("/api/zeiten/abwesenheiten").json()["antraege"])


def test_offener_antrag_von_der_tafel_laesst_sich_entscheiden(welt):
    db, mia = welt["db"], welt["mia"]
    offen = welt["client"]("buero_finanzen").post("/api/planning/absences", json=_body(mia)).json()
    antwort = welt["client"]("admin").post(f"/api/absence-requests/{offen['antrag_id']}/review", json={"decision": "approved"})
    assert antwort.status_code == 200, antwort.text
    assert _anzahl(db, EmployeeAbsence) == 1


def test_seite_bietet_loeschen_nur_nach_dem_recht_an_und_faengt_jeden_fehler():
    html = (ROOT / "app/templates/planning.html").read_text(encoding="utf-8")
    assert "board.rechte&&board.rechte.abwesenheit_loeschen?" in html
    loeschen = html[html.index("async function deleteAbsence("):]
    assert "catch(e){st.textContent='Fehler: '+e.message}" in loeschen[:loeschen.index("\n")]
    einsatz = html[html.index("async function deleteCurrent("):]
    assert "catch(e)" in einsatz[:einsatz.index("\n")]


def test_eine_abwesenheit_entsteht_nur_ueber_den_antrag():
    """Wächter: nur app/absence_requests.py konstruiert eine EmployeeAbsence."""
    fundstellen = []
    for datei in sorted((ROOT / "app").rglob("*.py")):
        baum = ast.parse(datei.read_text(encoding="utf-8"))
        for knoten in ast.walk(baum):
            if isinstance(knoten, ast.Call) and getattr(knoten.func, "id", None) == "EmployeeAbsence":
                fundstellen.append(datei.relative_to(ROOT).as_posix())
    assert fundstellen == ["app/absence_requests.py"]


# --- Migration ------------------------------------------------------------------------------------------------------------------------------------------------------------

def _migration():
    pfad = next((ROOT / "alembic" / "versions").glob("*_abwesenheiten_als_antraege.py"))
    spec = importlib.util.spec_from_file_location("migration_abwesenheiten", pfad)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def _bestand(engine):
    db = sessionmaker(bind=engine)()
    mia = Employee(employee_number="M-1", first_name="Mia", last_name="Test", employee_group="gewerblich", active=True)
    db.add(mia)
    db.flush()
    direkt = EmployeeAbsence(employee_id=mia.id, absence_type="Urlaub", absence_category="urlaub", start_date=MONTAG, end_date=MONTAG + timedelta(days=4), notes="Sommer",
                             created_at=datetime(2026, 9, 1, 8, 0))
    genehmigt = EmployeeAbsence(employee_id=mia.id, absence_type="Krankheit", absence_category="krankheit", start_date=MONTAG + timedelta(days=30), end_date=MONTAG + timedelta(days=30))
    db.add_all([direkt, genehmigt])
    db.flush()
    db.add(EmployeeAbsenceRequest(employee_id=mia.id, absence_type="Krankheit", absence_category="krankheit", start_date=genehmigt.start_date, end_date=genehmigt.end_date,
                                  status="approved", approved_absence_id=genehmigt.id))
    db.add(EmployeeAbsenceRequest(employee_id=mia.id, absence_type="Urlaub", absence_category="urlaub", start_date=MONTAG + timedelta(days=60), end_date=MONTAG + timedelta(days=61),
                                  status="pending"))
    db.commit()
    ids = (direkt.id, genehmigt.id)
    db.close()
    return ids


def _probe(engine):
    direkt_id, genehmigt_id = _bestand(engine)
    m = _migration()
    with engine.begin() as c:
        m.uebernehmen(c)
    db = sessionmaker(bind=engine)()
    zeilen = db.scalars(select(EmployeeAbsenceRequest).order_by(EmployeeAbsenceRequest.id)).all()
    assert len(zeilen) == 3  # genau einer dazu
    neu = next(z for z in zeilen if z.approved_absence_id == direkt_id)
    assert (neu.status, neu.absence_type, neu.absence_category, neu.start_date, neu.end_date, neu.notes, neu.review_notes, neu.requested_by_user_id, neu.reviewed_by_user_id) == (
        "approved", "Urlaub", "urlaub", MONTAG, MONTAG + timedelta(days=4), "Sommer", m.MERKER, None, None)
    assert neu.created_at == datetime(2026, 9, 1, 8, 0)
    assert sum(1 for z in zeilen if z.approved_absence_id == genehmigt_id) == 1
    db.close()
    with engine.begin() as c:
        m.uebernehmen(c)  # noch einmal: nichts dazu
    db = sessionmaker(bind=engine)()
    assert db.scalar(select(func.count()).select_from(EmployeeAbsenceRequest)) == 3
    db.close()
    with engine.begin() as c:
        m.zuruecknehmen(c)
    db = sessionmaker(bind=engine)()
    rest = db.scalars(select(EmployeeAbsenceRequest)).all()
    assert len(rest) == 2 and all(z.review_notes != m.MERKER for z in rest)
    assert db.scalar(select(func.count()).select_from(EmployeeAbsence)) == 2
    db.close()


def test_migration_sqlite(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'bestand.db').as_posix()}")
    try:
        Base.metadata.create_all(engine)
        _probe(engine)
    finally:
        engine.dispose()


def _pg_url():
    return os.environ.get("ERP_TEST_POSTGRES_URL")


@pytest.mark.skipif(not _pg_url(), reason="ERP_TEST_POSTGRES_URL fehlt")
def test_migration_und_loeschen_unter_postgresql(router_test_client):
    """Regel 27: Wegwerf-Schema. Der Beleg aus dem Befund (A8): genehmigte Abwesenheit löschen ergab unter PostgreSQL 500 -- SQLite prüft den Fremdschlüssel nicht."""
    basis = _pg_url()
    schema = f"pgtest_abw_{uuid.uuid4().hex[:8]}"
    verwaltung = create_engine(basis)
    with verwaltung.begin() as c:
        c.execute(text(f"CREATE SCHEMA {schema}"))
    engine = create_engine(basis, connect_args={"options": f"-csearch_path={schema}"}, pool_pre_ping=True)
    try:
        Base.metadata.create_all(engine)
        _probe(engine)
        db = sessionmaker(bind=engine)()
        mia = db.scalar(select(Employee))
        client = router_test_client(db, planning_router)
        daten = client.post("/api/planning/absences", json=_body(mia, von=MONTAG + timedelta(days=100))).json()
        assert daten["status"] == "approved", daten
        antwort = client.delete(f"/api/planning/absences/{daten['id']}")
        assert antwort.status_code == 200, antwort.text
        db.expire_all()
        assert db.get(EmployeeAbsenceRequest, daten["antrag_id"]).status == "cancelled"
        assert db.get(EmployeeAbsence, daten["id"]) is None
        db.close()
    finally:
        engine.dispose()
        with verwaltung.begin() as c:
            c.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        verwaltung.dispose()
