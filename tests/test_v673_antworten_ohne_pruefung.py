"""1.9.273 (Nachrunde R5b, Punkt 2; Nebenbefund R5b, Abschnitt 9): vier weitere Antwortschemata prüfen nicht mehr wie ihr Formular -- wie EmployeeOut seit 1.9.265.

Bis 1.9.272 erbten EmployeeFunctionOut (validate_group), EmployeeAbsenceOut (Kategorie, validate_dates), AccountOut (validate_default_tax_rate) und
IncomingInvoiceItemOut (validate_tax_rate) die Prüfung ihres Eingabeschemas: stand ein Wert in der Datenbank, den das Formular heute ablehnt, antwortete die
Liste mit 500. Ein echter Fall: ein Ausfalltag Schlechtwetter (Kategorie schlechtwetter, seit 1.9.170) in GET /api/planning/absences für Admin und Büro –
Finanzen. Die Prüfung gilt nur beim Speichern.

Wächter: kein Antwortschema (…Out in app/schemas.py) hat einen Validator; geerbte Grenzen (min_length, max_length, ge …) nur noch bei den acht in BEKANNT
-- die Liste darf nur kürzer werden."""

import inspect
from datetime import date
from decimal import Decimal

import pytest
from pydantic import BaseModel, ValidationError

import app.schemas as schemas
from app.models import Account, EmployeeAbsence, EmployeeFunction, EnabledModule, IncomingInvoiceItem, Supplier
from app.routers.accounts import router as accounts_router
from app.routers.incoming_invoices import router as incoming_invoices_router
from app.routers.planning import router as planning_router
from app.routers.settings import router as settings_router
from app.schemas import (AccountCreate, AccountOut, EmployeeAbsenceCreate, EmployeeAbsenceOut, EmployeeFunctionCreate, EmployeeFunctionOut,
                         IncomingInvoiceItemIn, IncomingInvoiceItemOut)
from tests.test_v633_besetzung_je_einsatz import _person

PAARE = [(EmployeeFunctionOut, EmployeeFunctionCreate), (EmployeeAbsenceOut, EmployeeAbsenceCreate), (AccountOut, AccountCreate),
         (IncomingInvoiceItemOut, IncomingInvoiceItemIn)]

# Antwortschemata, die Grenzen ihres Eingabeschemas noch erben (keine Validatoren) -- Nebenbefund 1.9.273, darf nur kürzer werden
BEKANNT = {"CustomerExtraInfoOut", "CustomerOut", "OperationalResourceOut", "PlanningHolidayOut", "PropertyOut", "QuoteDocumentMetaOut",
           "SettingOptionOut", "SupplierOut"}


def _antwortschemata():
    return sorted((n, c) for n, c in vars(schemas).items()
                  if inspect.isclass(c) and issubclass(c, BaseModel) and c.__module__ == "app.schemas" and n.endswith("Out"))


@pytest.mark.parametrize("aus, ein", PAARE, ids=[a.__name__ for a, _ in PAARE])
def test_antwort_ohne_pruefung_mit_allen_feldern(aus, ein):
    assert not issubclass(aus, ein)
    assert list(aus.model_fields)[:len(ein.model_fields)] == list(ein.model_fields)  # dieselben Felder in derselben Reihenfolge
    deko = aus.__pydantic_decorators__
    assert not deko.model_validators and not deko.field_validators
    for name, feld in aus.model_fields.items():
        assert not feld.metadata, (aus.__name__, name, feld.metadata)
    assert aus.model_config.get("from_attributes") is True


def test_kein_antwortschema_hat_einen_validator():
    mit = [n for n, c in _antwortschemata() if c.__pydantic_decorators__.model_validators or c.__pydantic_decorators__.field_validators]
    assert mit == []


def test_geerbte_grenzen_nur_bei_den_bekannten():
    mit = {n for n, c in _antwortschemata() if any(f.metadata for f in c.model_fields.values())}
    assert mit <= BEKANNT, sorted(mit - BEKANNT)
    assert BEKANNT <= mit, f"behoben -- aus BEKANNT streichen: {sorted(BEKANNT - mit)}"


# --- je Endpunkt: ein gespeicherter Wert, den das Formular ablehnt ----------------------------------------------------------------------

def test_funktion_mit_anderer_gruppe(threaded_db_session, router_test_client):
    db = threaded_db_session
    db.add(EmployeeFunction(name="Hofdienst", employee_group="lager", sort_order=100, active=True))
    db.commit()
    client = router_test_client(db, settings_router)
    r = client.get("/api/settings/employee-functions")
    assert r.status_code == 200, r.text
    assert [f["employee_group"] for f in r.json() if f["name"] == "Hofdienst"] == ["lager"]
    neu = client.post("/api/settings/employee-functions", json={"name": "Fahrer", "employee_group": "lager"})
    assert neu.status_code == 422 and "Mitarbeitergruppe" in neu.text


@pytest.mark.parametrize("kategorie", ["schlechtwetter", "unbekannt"])
def test_abwesenheit_schlechtwetter_und_unbekannt(threaded_db_session, router_test_client, kategorie):
    db = threaded_db_session
    tom = _person(db, "M-1", "Tom")
    db.add(EmployeeAbsence(employee_id=tom.id, absence_type="Schlechtwetter", absence_category=kategorie, start_date=date(2026, 11, 3),
                           end_date=date(2026, 11, 3)))
    db.commit()
    for rolle in ("admin", "buero_finanzen", "buero_auftrag"):
        client = router_test_client(db, planning_router, role=rolle)
        r = client.get("/api/planning/absences", params={"start": "2026-11-01", "end": "2026-11-30"})
        assert r.status_code == 200, (rolle, r.text)
        assert len(r.json()) == 1, rolle
        if rolle != "buero_auftrag":  # die Art nur ab Büro – Finanzen (Krankheitssichtbarkeit)
            assert r.json()[0]["absence_category"] == kategorie
    neu = router_test_client(db, planning_router).post("/api/planning/absences", json={"employee_id": tom.id, "absence_category": kategorie,
                                                                                      "start_date": "2026-11-10", "end_date": "2026-11-10"})
    assert neu.status_code == 422


def test_konto_mit_anderem_steuersatz(threaded_db_session, router_test_client):
    db = threaded_db_session
    db.add(EnabledModule(module_key="buchhaltung", enabled=True))
    konto = Account(account_number="3300", label="Wareneingang 16 %", default_tax_rate_pct=Decimal("16.00"), active=True)
    db.add(konto)
    db.commit()
    client = router_test_client(db, accounts_router)
    liste = client.get("/api/accounts")
    assert liste.status_code == 200, liste.text
    assert [Decimal(str(k["default_tax_rate_pct"])) for k in liste.json() if k["account_number"] == "3300"] == [Decimal("16.00")]
    assert client.get(f"/api/accounts/{konto.id}").status_code == 200
    neu = client.post("/api/accounts", json={"account_number": "3301", "label": "Neu", "default_tax_rate_pct": "16.00", "active": True})
    assert neu.status_code == 422 and "Steuersatz" in neu.text
    # das Eingabeschema selbst prüft weiter -- nicht nur app/accounts.py::_validate_tax_rate() dahinter (Gegenprobe 273_2b blieb sonst grün)
    with pytest.raises(ValidationError, match="Steuersatz muss 19, 7 oder 0 Prozent sein"):
        AccountCreate(account_number="3301", label="Neu", default_tax_rate_pct=Decimal("16.00"))


def test_position_einer_eingangsrechnung_mit_anderem_steuersatz(threaded_db_session, router_test_client):
    db = threaded_db_session
    db.add(EnabledModule(module_key="buchhaltung", enabled=True))
    lieferant = Supplier(name="Musterbaustoffe GmbH")
    db.add(lieferant)
    db.commit()
    client = router_test_client(db, incoming_invoices_router)
    angelegt = client.post("/api/incoming-invoices", json={
        "supplier_id": lieferant.id, "supplier_invoice_number": "RE-2020-016", "invoice_date": "2020-09-01", "net_amount": "500.00", "tax_rate_pct": "19.00",
        "payment_status": "offen", "items": [{"description": "Ziegel", "net_amount": "500.00", "tax_rate_pct": "19.00"}]})
    assert angelegt.status_code == 200, angelegt.text
    rechnung_id = angelegt.json()["id"]
    position = db.query(IncomingInvoiceItem).filter_by(incoming_invoice_id=rechnung_id).one()
    position.tax_rate_pct = Decimal("16.00")  # zweites Halbjahr 2020 -- über das Formular nicht mehr einzutragen
    db.commit()
    for pfad in ("/api/incoming-invoices", f"/api/incoming-invoices/{rechnung_id}"):
        r = client.get(pfad)
        assert r.status_code == 200, (pfad, r.text)
    einzeln = client.get(f"/api/incoming-invoices/{rechnung_id}").json()
    assert [Decimal(str(p["tax_rate_pct"])) for p in einzeln["items"]] == [Decimal("16.00")]
    falsch = client.put(f"/api/incoming-invoices/{rechnung_id}", json={
        "supplier_id": lieferant.id, "supplier_invoice_number": "RE-2020-016", "invoice_date": "2020-09-01", "net_amount": "500.00", "tax_rate_pct": "19.00",
        "payment_status": "offen", "items": [{"description": "Ziegel", "net_amount": "500.00", "tax_rate_pct": "16.00"}]})
    assert falsch.status_code == 422 and "Steuersatz" in falsch.text
