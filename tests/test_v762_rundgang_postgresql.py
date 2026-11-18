"""Version 1.9.362 -- Rundgang gegen PostgreSQL (Runde V3, Punkt 2; Vorschlag V3 aus dem Befund SQLite gegen PostgreSQL, 13.11.2026).

Die Suite läuft unter SQLite (mit Fremdschlüsseln seit 1.9.339), live läuft PostgreSQL. Der Befund fand Fehler, die nur PostgreSQL zeigt -- zu langer Text,
Löschen in falscher Reihenfolge, Sortierung nach seiner Kollation. V1 und V2 fangen sie statisch und in der Test-SQLite. Dieser Rundgang fängt, was beide nicht
sehen: Wege ohne eigenen Test. Er läuft gegen ein Wegwerf-Schema der Spielwiese (Regel 27) auf Daten, die in die Tabellen der Abläufe etwas legen (die Welt
des Rundgangs der Datengrenze, tests/test_v326_monteur_datengrenze.py::_buero_welt()), als Admin, jede Anfrage in einer eigenen Transaktion, danach
zurückgerollt -- jede Route sieht dieselbe Welt.

    Löschen      jede DELETE-Route unter /api/: kein 500
    Schreiben    jede schreibende Route mit JSON-Körper: jedes Textfeld mit Grenze an der Grenze (max_length Zeichen) -- kein 500; jedes Textfeld ein Zeichen
                 darüber -- 422 an diesem Feld; jede Route mit Formular: jedes Textfeld mit 300 und 5000 Zeichen -- kein 500
    Listen       die Listen der Stammdaten mit Umlauten, Groß- und Kleinschreibung und leeren Namen: in der Reihenfolge des Telefonbuchs, leere am Ende

Ohne ERP_TEST_POSTGRES_URL übersprungen (wie jeder PostgreSQL-Test). Teil des Endlaufs; die Zählung (wie viele Routen bis zur Datenbank kamen) schreibt der
Lauf nach .pytest_cache/rundgang_postgresql.txt, der Bericht nennt sie.
"""

import os
import re
import time
import typing
import uuid
from collections import Counter
from contextlib import contextmanager
from datetime import date, datetime
from datetime import time as uhrzeit
from decimal import Decimal
from enum import Enum
from pathlib import Path
from types import UnionType

import pytest
from annotated_types import Ge, Gt, Le, Lt, MaxLen, MinLen
from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, close_all_sessions

ROOT = Path(__file__).resolve().parents[1]
ZAEHLUNG = ROOT / ".pytest_cache" / "rundgang_postgresql.txt"
TAG = "2027-01-04"


# --- die Welt im Wegwerf-Schema ----------------------------------------------------------------------------------------------------------------------

class Rundgang:
    """Alle Router, angemeldet als Admin; jede Anfrage in einer eigenen Transaktion (Sitzung mit SAVEPOINT), danach zurückgerollt."""

    def __init__(self, engine, welt: dict, routers):
        from app.database import get_db
        self.engine, self.welt, self.halter = engine, welt, {}
        app = FastAPI()
        for router in routers:
            app.include_router(router)

        @app.middleware("http")
        async def _admin(request, call_next):
            request.state.erp_user = self.halter["admin"]
            return await call_next(request)

        @app.exception_handler(Exception)
        async def _fehler(request, exc):  # die Ursache in die 500, damit der Rundgang sie nennt
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=500, content={"fehler": f"{type(exc).__name__}: {str(exc).splitlines()[0][:300] if str(exc) else ''}"})

        app.dependency_overrides[get_db] = lambda: self.halter["db"]
        self.client = TestClient(app, raise_server_exceptions=False)
        self.routen = [r for router in routers for r in router.routes if isinstance(r, APIRoute) and r.path.startswith("/api/")]

    @contextmanager
    def isoliert(self):
        from app.models import AppUser
        conn = self.engine.connect()
        trans = conn.begin()
        db = Session(bind=conn, join_transaction_mode="create_savepoint")
        self.halter.update(db=db, admin=db.get(AppUser, self.welt["admin_id"]))
        try:
            yield db
        finally:
            db.close()
            trans.rollback()
            conn.close()

    def aufruf(self, methode: str, url: str, **kw):
        with self.isoliert():
            return self.client.request(methode, url, **kw)

    def pfad(self, route: APIRoute) -> str:
        from tests.test_v326_monteur_datengrenze import PFAD_WERTE
        eigene = self.welt["routen"].get(route.path, {})
        werte = {p.name: eigene.get(p.name, self.welt.get(p.name, PFAD_WERTE.get(p.name, 1))) for p in route.dependant.path_params}
        return route.path.format(**werte)


@pytest.fixture(scope="module")
def rundgang():
    url = os.getenv("ERP_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    import app.models  # noqa: F401
    from app.database import Base
    from app.grunddaten import anlegen
    from tests.test_v326_monteur_datengrenze import _buero_welt, _routers_in_betriebsreihenfolge
    from tests.uhr import uhr_festhalten

    schema = f"pgtest_rundgang_{uuid.uuid4().hex[:8]}"
    verwaltung = create_engine(url)
    with verwaltung.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}", "application_name": schema})
    start = time.monotonic()
    try:
        with uhr_festhalten():
            Base.metadata.create_all(engine)
            with Session(engine) as db:
                anlegen(db)
                db.commit()
                welt = _buero_welt(db)
                welt.update(_stammdaten(db))
                db.commit()
                welt["routen"], nicht_angelegt = _mehr_daten(db, welt)
            r = Rundgang(engine, welt, _routers_in_betriebsreihenfolge())
            r.zaehlung = {"Aufbau (s)": round(time.monotonic() - start, 1), "nicht angelegt": nicht_angelegt or "nichts"}
            yield r
            _zaehlung_schreiben(r.zaehlung, time.monotonic() - start)
    finally:
        close_all_sessions()
        engine.dispose()
        with verwaltung.begin() as conn:
            conn.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE application_name = :n"), {"n": schema})
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        verwaltung.dispose()


def _zaehlung_schreiben(zaehlung: dict, sekunden: float) -> None:
    zaehlung["gesamt (s)"] = round(sekunden, 1)
    ZAEHLUNG.parent.mkdir(exist_ok=True)
    ZAEHLUNG.write_text("".join(f"{k}: {v}\n" for k, v in zaehlung.items()), encoding="utf-8")


# --- Löschen -------------------------------------------------------------------------------------------------------------------------------------

def test_jede_delete_route_ohne_500(rundgang):
    routen = [r for r in rundgang.routen if "DELETE" in r.methods]
    assert len(routen) > 60
    assert set(rundgang.welt["routen"]) <= {r.path for r in rundgang.routen}, "ein Ziel für eine Route, die es nicht gibt"
    status, rot = Counter(), []
    for route in routen:
        antwort = rundgang.aufruf("DELETE", rundgang.pfad(route))
        status[antwort.status_code] += 1
        if antwort.status_code >= 500:
            rot.append(f"DELETE {route.path}: {antwort.status_code} {antwort.text[:200]}")
    rundgang.zaehlung["DELETE"] = f"{len(routen)} Routen, Status {dict(sorted(status.items()))}"
    assert not rot, rot


# --- Schreiben: Text an der Grenze und ein Zeichen darüber -----------------------------------------------------------------------------------------

def _ohne_none(t):
    o, args = typing.get_origin(t), typing.get_args(t)
    if o is typing.Annotated:
        return _ohne_none(args[0])
    if o in (typing.Union, UnionType):
        rest = [a for a in args if a is not type(None)]
        return _ohne_none(rest[0]) if len(rest) == 1 else t
    return t


def _grenze(feld, art):
    werte = [m for m in feld.metadata if isinstance(m, art)]
    return werte[0] if werte else None


def _zahl(feld, name: str, welt: dict):
    if name.endswith("_id"):
        return welt.get(name, 1)
    unten = _grenze(feld, Ge)
    oben = _grenze(feld, Le)
    wert = 1
    if unten is not None and wert < unten.ge:
        wert = unten.ge
    if oben is not None and wert > oben.le:
        wert = oben.le
    return wert


def _wert(name: str, feld, welt: dict, tiefe: int = 0):
    t = _ohne_none(feld.annotation)
    o, args = typing.get_origin(t), typing.get_args(t)
    if o is typing.Literal:
        return args[0]
    if isinstance(t, type) and issubclass(t, Enum):
        return next(iter(t)).value
    if t is str:
        ml = _grenze(feld, MaxLen)
        if name.endswith(("_date", "_on")) or name in ("datum", "von", "bis", "tag"):
            return TAG
        return "x" * ml.max_length if ml else "x" * max(1, getattr(_grenze(feld, MinLen), "min_length", 1))
    if t is bool:
        return False
    if t is int:
        return _zahl(feld, name, welt)
    if t in (Decimal, float):
        return "1"
    if t is date:
        return TAG
    if t is datetime:
        return f"{TAG}T08:00:00"
    if t is uhrzeit:
        return "08:00:00"
    if o in (list, set, tuple):
        return []
    if o is dict or t is dict:
        return {}
    if isinstance(t, type) and issubclass(t, BaseModel):
        return _koerper(t, welt, tiefe + 1) if tiefe < 3 else {}
    return None


def _koerper(modell, welt: dict, tiefe: int = 0) -> dict:
    """Ein Körper mit jedem Pflichtfeld und jedem Textfeld mit Grenze (an der Grenze)."""
    koerper = {}
    for name, feld in modell.model_fields.items():
        pflicht = feld.is_required()
        mit_grenze = _ohne_none(feld.annotation) is str and _grenze(feld, MaxLen) is not None
        if pflicht or mit_grenze:
            koerper[feld.alias or name] = _wert(name, feld, welt, tiefe)
    return koerper


def _textfelder(modell) -> list[tuple[str, int]]:
    return [(feld.alias or name, _grenze(feld, MaxLen).max_length) for name, feld in modell.model_fields.items()
            if _ohne_none(feld.annotation) is str and _grenze(feld, MaxLen) is not None]


def _json_modell(route: APIRoute):
    koerper = [b for b in route.dependant.body_params if type(b.field_info).__name__ not in ("Form", "File")]
    if len(koerper) != 1:
        return None, False
    t = _ohne_none(koerper[0].field_info.annotation)
    if typing.get_origin(t) is list:
        inner = _ohne_none(typing.get_args(t)[0])
        return (inner, True) if isinstance(inner, type) and issubclass(inner, BaseModel) else (None, False)
    return (t, False) if isinstance(t, type) and issubclass(t, BaseModel) else (None, False)


def _query(route: APIRoute, welt: dict) -> dict:
    from tests.test_v326_monteur_datengrenze import QUERY_WERTE
    q = {}
    for p in route.dependant.query_params:
        if p.field_info.is_required():
            wert = QUERY_WERTE.get(p.name, welt.get(p.name, TAG if "date" in p.name or p.name in ("von", "bis", "tag") else "1"))
            q[p.name] = welt[wert[1:]] if isinstance(wert, str) and wert.startswith("@") else wert
    return q


def _methode(route: APIRoute) -> str:
    return sorted(route.methods & {"POST", "PUT", "PATCH"})[0]


def test_jede_schreibende_route_mit_text_an_der_grenze_ohne_500(rundgang):
    routen = [r for r in rundgang.routen if r.methods & {"POST", "PUT", "PATCH"}]
    status, rot, mit_json = Counter(), [], 0
    for route in routen:
        modell, als_liste = _json_modell(route)
        if modell is None:
            continue
        mit_json += 1
        koerper = _koerper(modell, rundgang.welt)
        antwort = rundgang.aufruf(_methode(route), rundgang.pfad(route), params=_query(route, rundgang.welt),
                                  json=[koerper] if als_liste else koerper)
        status[antwort.status_code] += 1
        if antwort.status_code >= 500:
            rot.append(f"{_methode(route)} {route.path}: {antwort.status_code} {antwort.text[:200]}")
    rundgang.zaehlung["Schreiben an der Grenze"] = f"{mit_json} Routen mit JSON-Körper, Status {dict(sorted(status.items()))}"
    assert mit_json > 250
    assert not rot, rot


def test_jedes_textfeld_ein_zeichen_darueber_422(rundgang):
    rot, felder = [], 0
    for route in rundgang.routen:
        if not route.methods & {"POST", "PUT", "PATCH"}:
            continue
        modell, als_liste = _json_modell(route)
        if modell is None:
            continue
        basis = _koerper(modell, rundgang.welt)
        for feld, grenze in _textfelder(modell):
            felder += 1
            koerper = {**basis, feld: "x" * (grenze + 1)}
            antwort = rundgang.aufruf(_methode(route), rundgang.pfad(route), params=_query(route, rundgang.welt),
                                      json=[koerper] if als_liste else koerper)
            fehler = antwort.json().get("detail") if antwort.status_code == 422 else None
            if not (isinstance(fehler, list) and any(e.get("loc", [None])[-1] == feld and e.get("type") == "string_too_long" for e in fehler)):
                rot.append(f"{_methode(route)} {route.path} {feld} ({grenze} + 1): {antwort.status_code} {antwort.text[:160]}")
    rundgang.zaehlung["ein Zeichen darüber"] = f"{felder} Textfelder"
    assert felder > 400
    assert not rot, rot[:30]


def test_jedes_textfeld_im_formular_ohne_500(rundgang):
    """Formulare (Hochladen, Unterschrift auf Papier, Zustellung nachtragen) haben keine Schemas -- jedes Textfeld mit 300 und 5000 Zeichen."""
    rot, felder = [], 0
    png = _png()
    for route in rundgang.routen:
        form = [b for b in route.dependant.body_params if type(b.field_info).__name__ in ("Form", "File")]
        texte = [b for b in form if type(b.field_info).__name__ == "Form" and _ohne_none(b.field_info.annotation) is str]
        if not texte:
            continue
        for b in texte:
            for laenge in (300, 5000):
                felder += 1
                daten, dateien = {}, []
                for x in form:
                    art = type(x.field_info).__name__
                    t = _ohne_none(x.field_info.annotation)
                    if art == "File":
                        dateien.append((x.name, ("probe.png", png, "image/png")))
                    elif x is b:
                        daten[x.name] = "x" * laenge
                    elif x.field_info.is_required():
                        daten[x.name] = (TAG if t is date else str(rundgang.welt.get(x.name, 1)) if t is int else "{}" if x.name == "data"
                                         else "x")
                antwort = rundgang.aufruf(_methode(route), rundgang.pfad(route), data=daten, files=dateien or None)
                if antwort.status_code >= 500:
                    rot.append(f"{_methode(route)} {route.path} {b.name} ({laenge}): {antwort.status_code} {antwort.text[:160]}")
    rundgang.zaehlung["Formular"] = f"{felder} Proben"
    assert felder > 50
    assert not rot, rot


def _png() -> bytes:
    from io import BytesIO

    from PIL import Image
    puffer = BytesIO()
    Image.new("RGB", (4, 4), "white").save(puffer, format="PNG")
    return puffer.getvalue()


# --- Listen der Stammdaten ------------------------------------------------------------------------------------------------------------------------

NAMEN = ["Zander Probe", "ähre Probe", "Abel Probe", "ÖLBERG Probe", "abel Probe", "Straße Probe", "Strasse Probe", "Émile Probe"]


def _stammdaten(db) -> dict:
    """Je Liste die Namen oben, dazu ein leerer Name (Altbestand) -- in einer Reihenfolge angelegt, die weder binär noch nach dem Telefonbuch sortiert ist."""
    from app.models import Catalog, Customer, Employee, MaterialGroup, OperationalResource, Property, Supplier, Team
    angelegt = {}
    kunde = None
    for n in NAMEN + [""]:
        k = Customer(name=n, last_name=n)
        db.add(k)
        db.flush()
        kunde = kunde or k
        angelegt.setdefault("/api/customers", []).append(k.id)
    for modell, pfad, extra in ((Property, "/api/properties", lambda: {"customer_id": kunde.id}), (Supplier, "/api/suppliers", dict),
                                (Team, "/api/teams", dict), (Catalog, "/api/catalogs", dict), (MaterialGroup, "/api/material-groups", dict),
                                (OperationalResource, "/api/resources", lambda: {"resource_type": "fahrzeug"})):
        for n in NAMEN + [""]:
            x = modell(name=n, **extra())
            db.add(x)
            db.flush()
            angelegt.setdefault(pfad, []).append(x.id)
    for n in NAMEN + [""]:
        e = Employee(first_name="", last_name=n, active=True)
        db.add(e)
        db.flush()
        angelegt.setdefault("/api/employees", []).append(e.id)
    from app.models import Contact, Material
    for n in NAMEN + [""]:
        c = Contact(kind="person", last_name=n)
        mat = Material(name=n, unit="Stk", purchase_price=1)
        db.add_all([c, mat])
        db.flush()
        angelegt.setdefault("/api/contacts", []).append(c.id)
        angelegt.setdefault("/api/materials", []).append(mat.id)
    return {"stammdaten": angelegt}


LISTEN = {
    "/api/customers": "last_name", "/api/properties": "name", "/api/suppliers": "name", "/api/teams": "name", "/api/catalogs": "name",
    "/api/material-groups": "name", "/api/resources": "name", "/api/employees": "last_name", "/api/contacts": "last_name", "/api/materials": "name",
}


def test_listen_der_stammdaten_wie_im_telefonbuch(rundgang):
    from app.telefonbuch import sortierwert
    rot = []
    for pfad, feld in LISTEN.items():
        ids = rundgang.welt["stammdaten"][pfad]
        antwort = rundgang.aufruf("GET", pfad, params={"include_archived": "true"} if pfad in ("/api/catalogs", "/api/material-groups") else None)
        if antwort.status_code != 200:
            rot.append(f"{pfad}: {antwort.status_code} {antwort.text[:160]}")
            continue
        namen = [x[feld] for x in antwort.json() if x["id"] in ids]
        erwartet = sorted(NAMEN + [""], key=sortierwert)
        if namen != erwartet:
            rot.append(f"{pfad}: {namen} statt {erwartet}")
    rundgang.zaehlung["Listen"] = f"{len(LISTEN)} Listen"
    assert not rot, rot


# --- mehr Welt: je DELETE-Route ein Ziel, das es gibt ----------------------------------------------------------------------------------------------

def _mehr_daten(db, welt: dict) -> tuple[dict, list[str]]:
    """Datensätze, die die Welt der Datengrenze nicht hat -- je DELETE-Route, die sonst nur 404 sähe, ein Ziel. Jeder in einem eigenen SAVEPOINT; was
    nicht angelegt werden kann, steht in der Zählung (nicht still). Rückgabe: (Werte je Route und Pfadparameter, nicht angelegt)."""
    from datetime import date, datetime
    from decimal import Decimal

    from sqlalchemy import select

    import app.models as m
    werte, fehlt = {}, []

    def anlegen(name: str, bauen):
        try:
            with db.begin_nested():
                obj = bauen()
                db.add(obj)
                db.flush()
                return obj.id
        except Exception as exc:  # noqa: BLE001 -- genannt in der Zählung
            fehlt.append(f"{name}: {type(exc).__name__}")
            return None

    def ziel(route: str, **param):
        if all(v is not None for v in param.values()):
            werte[route] = param

    erstes = lambda modell, *bed: db.scalars(select(modell).where(*bed).order_by(modell.id)).first()  # noqa: E731
    kategorie = erstes(m.DocumentCategory)
    lieferant = erstes(m.Supplier)
    aufgabe = erstes(m.Task)
    ziel("/api/quotes/{quote_id}/items/{item_id}", quote_id=1,
         item_id=anlegen("Angebotsposition", lambda: m.QuoteItem(quote_id=1, sort_order=20, position_number="2", short_text="Rinne", unit="m",
                                                                  quantity=Decimal("1"), unit_price=Decimal("1"))))
    ziel("/api/quotes/{quote_id}/sections/{section_id}", quote_id=1,
         section_id=anlegen("LV-Titel", lambda: m.QuoteSection(quote_id=1, title="Dach", sort_order=10)))
    pos = erstes(m.OrderItem, m.OrderItem.order_id == welt["order_id"])
    ziel("/api/orders/{order_id}/items/{item_id}", order_id=welt["order_id"], item_id=pos.id if pos else None)
    rechnung = erstes(m.Invoice, m.Invoice.status == "entwurf")
    rpos = erstes(m.InvoiceItem, m.InvoiceItem.invoice_id == rechnung.id) if rechnung else None
    ziel("/api/invoices/{invoice_id}/items/{item_id}", invoice_id=rechnung.id if rechnung else None, item_id=rpos.id if rpos else None)
    ziel("/api/project-documents/{document_id}", document_id=anlegen("Projektdokument", lambda: m.ProjectDocument(
        project_id=welt["project_id"], category_id=kategorie.id, original_filename="probe.pdf", stored_filename="probe-projekt.pdf")))
    ziel("/api/customer-documents/{document_id}", document_id=anlegen("Kundendokument", lambda: m.CustomerDocument(
        customer_id=welt["customer_id"], category_id=kategorie.id, original_filename="probe.pdf", stored_filename="probe-kunde.pdf")))
    ziel("/api/planning/absences/{absence_id}", absence_id=anlegen("Abwesenheit", lambda: m.EmployeeAbsence(
        employee_id=welt["employee_id"], start_date=date(2027, 2, 1), end_date=date(2027, 2, 2))))
    ziel("/api/planning/holidays/{holiday_id}", holiday_id=anlegen("Feiertag", lambda: m.PlanningHoliday(holiday_date=date(2027, 3, 3), name="Probe")))
    ziel("/api/calendar-events/{event_id}", event_id=anlegen("Termin", lambda: m.CalendarEvent(
        title="Probe", start_at=datetime(2027, 1, 5, 9), end_at=datetime(2027, 1, 5, 10), owner_user_id=welt["admin_id"])))
    if aufgabe:
        ziel("/api/tasks/{task_id}/checklist-items/{item_id}", task_id=aufgabe.id,
             item_id=anlegen("Punkt einer Aufgabe", lambda: m.TaskChecklistItem(task_id=aufgabe.id, title="Leiter holen")))
    ziel("/api/customers/{customer_id}/extra-infos/{info_id}", customer_id=welt["customer_id"],
         info_id=anlegen("Zusatzinfo", lambda: m.CustomerExtraInfo(customer_id=welt["customer_id"], info_type="Hinweis", value="Hund im Hof")))
    ziel("/api/maintenance-windows/{window_id}", window_id=anlegen("Wartungsfenster", lambda: m.MaintenanceWindow(label="Frühjahr", month_from=3,
                                                                                                              month_to=5)))
    if lieferant:
        rechnung_ein = anlegen("Eingangsrechnung", lambda: m.IncomingInvoice(supplier_id=lieferant.id, invoice_date=date(2027, 1, 4),
                                                                              net_amount=Decimal("10")))
        ziel("/api/incoming-invoices/{invoice_id}", invoice_id=rechnung_ein)
        ziel("/api/incoming-invoices/{invoice_id}/document", invoice_id=rechnung_ein)
    kosten = anlegen("Betriebskosten", lambda: m.RecurringCost(label="Versicherung", net_amount=Decimal("10"), billing_interval="monatlich",
                                                              annual_amount=Decimal("120")))
    ziel("/api/recurring-costs/{cost_id}", cost_id=kosten)
    if kosten:
        ziel("/api/recurring-cost-documents/{document_id}", document_id=anlegen("Beleg der Betriebskosten", lambda: m.RecurringCostDocument(
            recurring_cost_id=kosten, document_type="Vertrag", stored_filename="probe-kosten.pdf", original_filename="probe.pdf")))
    ziel("/api/base-interest-rates/{rate_id}", rate_id=anlegen("Basiszinssatz", lambda: m.BaseInterestRate(half_year_start=date(2030, 1, 1),
                                                                                                         rate_percent=Decimal("1.27"))))
    ziel("/api/roof-component-types/{component_type_id}", component_type_id=anlegen("Bauteilart", lambda: m.RoofComponentType(key="probe_bauteil",
                                                                                                                           label="Probe")))
    ziel("/api/roof-layer-types/{layer_type_id}", layer_type_id=anlegen("Schichtart", lambda: m.RoofLayerType(key="probe_schicht", label="Probe")))
    gruppe = erstes(m.SettingOptionGroup, m.SettingOptionGroup.group_key == "time_entry_types")
    option = erstes(m.SettingOption, m.SettingOption.group_id == gruppe.id) if gruppe else None
    ziel("/api/settings/option-groups/{group_key}/options/{option_id}", group_key="time_entry_types", option_id=option.id if option else None)
    pruefung = anlegen("Prüffrist", lambda: m.OperationalAssetInspection(asset_id=welt["asset_id"], inspection_type="UVV"))
    ziel("/api/operational-asset-inspections/{inspection_id}", inspection_id=pruefung)
    ziel("/api/operational-asset-inspections/{inspection_id}/document", inspection_id=pruefung)
    ziel("/api/operational-asset-documents/{document_id}", document_id=anlegen("Dokument eines Betriebsmittels", lambda: m.OperationalAssetDocument(
        asset_id=welt["asset_id"], document_type="Handbuch", stored_filename="probe-geraet.pdf", original_filename="probe.pdf")))
    ziel("/api/time-backoffice/sollzeiten/zeile/{zeile_id}", zeile_id=anlegen("eigene Sollzeit", lambda: m.EmployeeTargetHours(
        employee_id=welt["employee_id"], valid_from=date(2027, 6, 1))))
    db.commit()
    return werte, fehlt


# --- die Funde des Rundgangs, je ein Test unter SQLite (seit 1.9.362) ------------------------------------------------------------------------------

def test_bezeichnung_im_protokoll_hoechstens_so_lang_wie_die_spalte(db_session):
    """write_audit(): „Nummer Name“ eines Lieferanten (50 + 1 + 255 Zeichen) -- bis 1.9.361 ungekürzt in audit_logs.entity_label (255), unter PostgreSQL
    500 bei jedem Anlegen und Ändern."""
    from sqlalchemy import select

    from app.models import AuditLog, Supplier
    from app.spaltenlaenge import laenge
    db_session.add(Supplier(supplier_number="L" * 50, name="N" * 255))
    db_session.commit()
    labels = db_session.scalars(select(AuditLog.entity_label).where(AuditLog.entity_type == "Lieferant").order_by(AuditLog.id)).all()
    assert labels and all(len(x) == laenge(AuditLog.entity_label) for x in labels)


def test_kundenname_zusammen_zu_lang_422(threaded_db_session, router_test_client):
    from app.routers import customers
    client = router_test_client(threaded_db_session, customers.router)
    lang = {"salutation": "H" * 50, "title": "T" * 80, "first_name": "V" * 120, "last_name": "N" * 255}
    antwort = client.post("/api/customers", json=lang)
    assert antwort.status_code == 422 and antwort.json()["detail"] == ("Anrede, Titel, Vorname und Nachname sind zusammen zu lang (508 Zeichen, "
                                                                       "höchstens 255).")
    kunde = client.post("/api/customers", json={"last_name": "N" * 255}).json()  # 255 genau: geht
    assert kunde["name"] == "N" * 255
    antwort = client.put(f"/api/customers/{kunde['id']}", json={"first_name": "Erika"})  # Teil-Update: mit dem gespeicherten Nachnamen zu lang
    assert antwort.status_code == 422 and "zusammen zu lang (261 Zeichen" in antwort.json()["detail"]
    assert client.get(f"/api/customers/{kunde['id']}").json()["first_name"] is None  # nichts gespeichert


FORMULARE = [  # (Router, Pfad, Feld, Grenze, weitere Felder)
    ("customers", "/api/customers/1/documents", "category", 100, {}),
    ("customers", "/api/customers/1/documents", "subfolder", 150, {}),
    ("projects", "/api/projects/1/documents", "category", 100, {}),
    ("projects", "/api/projects/1/documents", "subfolder", 150, {}),
    ("work_preparation", "/api/orders/1/work-preparation/delivery-notes", "delivery_note_number", 120, {}),
    ("operational_assets", "/api/operational-assets/1/documents", "document_type", 80, {}),
    ("recurring_costs", "/api/recurring-costs/1/documents", "document_type", 80, {}),
    ("service_reports", "/api/service-reports/1/photos", "caption", 255, {}),
]


@pytest.mark.parametrize("router,pfad,feld,grenze,weitere", FORMULARE)
def test_textfeld_im_formular_ueber_der_spalte_422(threaded_db_session, router_test_client, router, pfad, feld, grenze, weitere):
    """Seit 1.9.362: die Felder eines Formulars, die ohne Prüfung in eine Spalte String(n) gehen, haben max_length -- bis dahin unter PostgreSQL 500."""
    import importlib
    client = router_test_client(threaded_db_session, importlib.import_module(f"app.routers.{router}").router)
    antwort = client.post(pfad, data={feld: "x" * (grenze + 1), **weitere}, files={"file": ("probe.png", _png(), "image/png")})
    assert antwort.status_code == 422
    assert any(e["loc"][-1] == feld and e["type"] == "string_too_long" and e["ctx"]["max_length"] == grenze for e in antwort.json()["detail"])


def test_lieferant_mit_eingangsrechnung_oder_aus_dem_import_wird_deaktiviert(threaded_db_session, router_test_client):
    """Bis 1.9.361 löschte DELETE /api/suppliers/{id} einen Lieferanten mit Eingangsrechnung oder aus dem Adressimport -- am Fremdschlüssel 500."""
    from datetime import date
    from decimal import Decimal

    from app.models import ImportedAddress, ImportRun, IncomingInvoice, Supplier
    from app.routers import resource_planning
    db = threaded_db_session
    mit_rechnung, aus_import, frei = Supplier(name="Rechnung Probe"), Supplier(name="Import Probe"), Supplier(name="Frei Probe")
    db.add_all([mit_rechnung, aus_import, frei])
    db.flush()
    lauf = ImportRun(source_filename="probe.xlsx")
    db.add(lauf)
    db.flush()
    db.add_all([IncomingInvoice(supplier_id=mit_rechnung.id, invoice_date=date(2027, 1, 4), net_amount=Decimal("10")),
                ImportedAddress(import_run_id=lauf.id, row_number=1, classification="lieferant", created_supplier_id=aus_import.id)])
    db.commit()
    client = router_test_client(db, resource_planning.router)
    for lieferant in (mit_rechnung, aus_import):
        assert client.delete(f"/api/suppliers/{lieferant.id}").json() == {"deleted": False, "deactivated": True}
        db.refresh(lieferant)
        assert lieferant.active is False
    assert client.delete(f"/api/suppliers/{frei.id}").json() == {"deleted": True}


def test_betriebsmittel_im_unterschriebenen_bericht_400(threaded_db_session, router_test_client):
    """Bis 1.9.361 endeten PUT und DELETE eines Betriebsmittels im unterschriebenen Einsatzbericht mit 500 (ValueError ungefangen); Material 400."""
    from sqlalchemy import select

    from app.models import Customer, OperationalAsset, Order, Project, ProjectPipelineColumn, ServiceReport, ServiceReportAsset
    from app.routers import service_reports
    from tests.quellangebot import quell_angebot
    db = threaded_db_session
    kunde = Customer(name="Probe", last_name="Probe")
    db.add(kunde)
    db.flush()
    spalte = db.scalars(select(ProjectPipelineColumn).order_by(ProjectPipelineColumn.id)).first()
    projekt = Project(project_number="P-RG-1", customer_id=kunde.id, name="Probe", pipeline_column_id=spalte.id)
    db.add(projekt)
    db.flush()
    auftrag = Order(order_number="AUF-RG-1", project_id=projekt.id, source_quote_id=quell_angebot(db, projekt.id, "AUF-RG-1"),
                    quote_number_snapshot="Q-AUF-RG-1", title="Probe", customer_name="Probe", customer_id=kunde.id)
    geraet = OperationalAsset(name="Leiter")
    db.add_all([auftrag, geraet])
    db.flush()
    bericht = ServiceReport(order_id=auftrag.id, report_type="rapport", status="unterschrieben")
    db.add(bericht)
    db.flush()
    zeile = ServiceReportAsset(service_report_id=bericht.id, asset_id=geraet.id, asset_name_snapshot="Leiter")
    db.add(zeile)
    db.commit()
    client = router_test_client(db, service_reports.router)
    for antwort in (client.put(f"/api/service-report-assets/{zeile.id}", json={"notes": "x"}), client.delete(f"/api/service-report-assets/{zeile.id}")):
        assert antwort.status_code == 400 and "unterschriebenen" in antwort.json()["detail"]
