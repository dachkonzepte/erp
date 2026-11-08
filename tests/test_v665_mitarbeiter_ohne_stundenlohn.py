"""1.9.265 (Stufe 6, R5b, Punkt 0a, Nebenbefund R5a): GET /api/employees scheitert nicht an einem Mitarbeiter ohne Stundenlohn.

Bis 1.9.264 erbte EmployeeOut von EmployeeCreate die Prüfung des Formulars (validate_commercial_wage, Grenzen der Felder): ein gewerblicher Mitarbeiter
ohne Stundenlohn -- über das Formular nicht anzulegen, die Spalte erlaubt es aber -- brachte die ganze Liste für Admin und Büro – Finanzen auf 500.
Die Prüfung gilt nur beim Speichern."""

from decimal import Decimal

from pydantic import BaseModel

from app.models import Employee
from app.routers.employees import router as employees_router
from app.schemas import EmployeeCreate, EmployeeOut


def _ohne_lohn(db) -> Employee:
    e = Employee(first_name="Olaf", last_name="Ohnelohn", employee_group="gewerblich", hourly_wage=None, weekly_hours=Decimal("40"))
    mit = Employee(first_name="Mia", last_name="Mitlohn", employee_group="gewerblich", hourly_wage=Decimal("21.50"), weekly_hours=Decimal("40"))
    db.add_all([e, mit])
    db.commit()
    return e


def test_liste_und_einzeln_mit_einem_mitarbeiter_ohne_stundenlohn(threaded_db_session, router_test_client):
    db = threaded_db_session
    e = _ohne_lohn(db)
    for rolle in ("admin", "buero_finanzen", "buero_auftrag"):
        client = router_test_client(db, employees_router, role=rolle)
        r = client.get("/api/employees")
        assert r.status_code == 200, (rolle, r.text)
        zeilen = {x["last_name"]: x for x in r.json()}
        assert {"Ohnelohn", "Mitlohn"} <= set(zeilen), rolle
        if rolle != "buero_auftrag":  # die Vergütung nur ab Büro – Finanzen (EmployeeOut)
            assert zeilen["Ohnelohn"]["hourly_wage"] is None
            assert Decimal(str(zeilen["Mitlohn"]["hourly_wage"])) == Decimal("21.50")
        einzeln = client.get(f"/api/employees/{e.id}")
        assert einzeln.status_code == 200, (rolle, einzeln.text)


def test_beim_speichern_bleibt_die_pruefung(threaded_db_session, router_test_client):
    db = threaded_db_session
    e = _ohne_lohn(db)
    client = router_test_client(db, employees_router)
    neu = client.post("/api/employees", json={"first_name": "Nina", "last_name": "Neu", "employee_group": "gewerblich", "compensation_type": "hourly"})
    assert neu.status_code == 422
    assert "Stundenlohn" in neu.text
    aendern = client.put(f"/api/employees/{e.id}", json={"first_name": "Olaf", "last_name": "Ohnelohn", "employee_group": "gewerblich",
                                                           "compensation_type": "hourly"})
    assert aendern.status_code == 422
    assert "Stundenlohn" in aendern.text
    assert client.get("/api/employees").status_code == 200  # die abgelehnte Änderung lässt die Liste lesbar


def test_antwort_ohne_pruefung_mit_allen_feldern():
    """Die Antwort hat jedes Feld des Formulars, aber keine Validatoren und keine Grenzen -- so kommt eine neue Prüfung im Formular nicht in die Antwort."""
    assert not issubclass(EmployeeOut, EmployeeCreate)
    assert set(EmployeeCreate.model_fields) <= set(EmployeeOut.model_fields)
    deko = EmployeeOut.__pydantic_decorators__
    assert not deko.model_validators and not deko.field_validators
    for name, feld in EmployeeOut.model_fields.items():
        assert not feld.metadata, (name, feld.metadata)
    assert issubclass(EmployeeOut, BaseModel)
