"""Version 1.8.30 -- Auswahllisten behalten einen inaktiven gespeicherten Wert.

Nebenbefund 2 aus 1.8.25 (docs/archiv/teil-updates.md): viele Auswahllisten boten nur aktive Einträge an.
War der gespeicherte Eintrag inzwischen inaktiv (Mitarbeiter ausgeschieden, Auswahl-Eintrag abgeschaltet,
Zahlungsbedingung archiviert), fehlte er in der Liste: das Feld stand leer oder auf dem ersten Eintrag,
und das nächste Speichern schrieb das. Beim Sachbearbeiter des Auftrags lehnte der Server einen
inaktiven Mitarbeiter außerdem mit 422 ab, auch unverändert.

Jetzt baut auswahlOptionen() (app/templates/_auswahl.html) diese Listen: der gespeicherte Wert bleibt
vorgewählt, ein inaktiver mit " (inaktiv)". Die Server-Prüfungen auf "aktiv" gelten nur noch für einen
neu gewählten Wert. Die Tests führen den echten JavaScript-Code der Vorlagen in node aus; fehlt node,
werden sie übersprungen. Die Liste aller umgestellten Felder steht in docs/archiv/teil-updates.md."""

import json
import re
from decimal import Decimal
from html.parser import HTMLParser

import pytest

from app.models import Employee, EmployeeRoleSettings, Order
from app.routers.orders import router as orders_router
from tests.test_v133_invoices import make_order_with_item
from tests.test_v153_mahnwesen import db_session
from tests.test_v314_dashboard_month_berlin import NODE, TEMPLATES, _node
from tests.test_v329_teil_updates import klammer, payload, ui_keys

nur_mit_node = pytest.mark.skipif(NODE is None, reason="node nicht installiert")


def _skripte(vorlage: str) -> str:
    return "\n".join(re.findall(r"<script>(.*?)</script>", (TEMPLATES / vorlage).read_text(encoding="utf-8"), flags=re.S))


def seitenskript(vorlage: str, bis: str, ersetzen: dict[str, str] | None = None) -> str:
    """Der Hilfsskript-Teil einer Seite für node: _auswahl.html (in der Seite per Jinja eingebunden)
    plus das Seitenskript bis vor `bis` (dort beginnt der Seitenstart mit fetch() und DOM)."""
    html = (TEMPLATES / vorlage).read_text(encoding="utf-8")
    haupt = re.findall(r"<script>(.*?)</script>", html, flags=re.S)[-1]
    assert bis in haupt, f"{vorlage}: {bis!r} nicht gefunden -- Test anpassen"
    haupt = haupt.split(bis)[0]
    for alt, neu in (ersetzen or {}).items():
        assert alt in haupt, f"{vorlage}: {alt!r} nicht gefunden -- Test anpassen"
        haupt = haupt.replace(alt, neu)
    return _skripte("_auswahl.html") + "\n" + haupt


def js_funktion(vorlage: str, name: str) -> str:
    """Quelltext von "function name(...){...}" aus der Vorlage."""
    html = (TEMPLATES / vorlage).read_text(encoding="utf-8")
    start = re.search(rf"function {re.escape(name)}\s*\(", html).start()
    return html[start:html.index(")", start)] + ")" + klammer(html, html.index("{", html.index(")", start)))


class _Optionen(HTMLParser):
    def __init__(self):
        super().__init__()
        self.optionen, self._offen = [], None

    def handle_starttag(self, tag, attrs):
        if tag == "option":
            a = dict(attrs)
            self._offen = {"wert": a.get("value"), "gewaehlt": "selected" in a, "text": ""}
            self.optionen.append(self._offen)

    def handle_data(self, data):
        if self._offen is not None:
            self._offen["text"] += data

    def handle_endtag(self, tag):
        if tag == "option":
            self._offen = None


def optionen(html: str) -> list[dict]:
    parser = _Optionen()
    parser.feed(html)
    return parser.optionen


def gewaehlt(html: str) -> dict | None:
    """Was der Browser vorwählt: die letzte Option mit selected, sonst die erste."""
    liste = optionen(html)
    markiert = [o for o in liste if o["gewaehlt"]]
    return markiert[-1] if markiert else (liste[0] if liste else None)


def _js(skript: str, ausdruck: str):
    return _node(skript + f"\nprocess.stdout.write(JSON.stringify({ausdruck}));", "Europe/Berlin")


# ---------------------------------------------------------------------------
# Der Helfer selbst
# ---------------------------------------------------------------------------

LEUTE = [{"id": 1, "name": "Anna", "active": True}, {"id": 2, "name": "Bernd <B>", "active": False},
         {"id": 3, "name": "Carla", "active": True}]


def _helfer(gespeichert, **opt) -> str:
    opt_js = "{" + ",".join(f"{k}:{v}" for k, v in opt.items()) + "}"
    return _js(_skripte("_auswahl.html"),
               f"auswahlOptionen({json.dumps(LEUTE)},{json.dumps(gespeichert)},x=>x.name,{opt_js})")


@nur_mit_node
def test_helfer_inaktiver_gespeicherter_wert_bleibt_gewaehlt_und_gekennzeichnet():
    html = _helfer(2, leer="'— keiner —'")
    assert [o["wert"] for o in optionen(html)] == ["", "1", "2", "3"]
    assert gewaehlt(html) == {"wert": "2", "gewaehlt": True, "text": "Bernd <B> (inaktiv)"}
    assert "<B>" not in html  # maskiert


@nur_mit_node
def test_helfer_bietet_inaktive_sonst_nicht_an():
    for gespeichert in (None, 1, ""):
        html = _helfer(gespeichert, leer="'— keiner —'")
        assert [o["wert"] for o in optionen(html)] == ["", "1", "3"]
    assert gewaehlt(_helfer(None, leer="'— keiner —'"))["wert"] == ""
    assert gewaehlt(_helfer(3))["wert"] == "3"


@nur_mit_node
def test_helfer_wert_nicht_in_der_quelle():
    html = _helfer(9, leer="'—'")
    assert gewaehlt(html) == {"wert": "9", "gewaehlt": True, "text": "9 (nicht mehr verfügbar)"}
    html = _helfer(9, fehlt="w=>'Dora ('+w+')'")
    assert gewaehlt(html)["text"] == "Dora (9)"


@nur_mit_node
def test_helfer_mit_eigenem_wert_und_aktiv():
    werte = [{"value": "flach", "label": "Flachdach", "archived": True}, {"value": "steil", "label": "Steildach"}]
    html = _js(_skripte("_auswahl.html"),
               f"auswahlOptionen({json.dumps(werte)},'flach',x=>x.label,{{wert:x=>x.value,aktiv:x=>!x.archived}})")
    assert [(o["wert"], o["text"]) for o in optionen(html)] == [("flach", "Flachdach (inaktiv)"), ("steil", "Steildach")]


# ---------------------------------------------------------------------------
# Gegenprobe am Sachbearbeiter des Auftrags: Oberfläche und Server
# ---------------------------------------------------------------------------

def _auftrag_mit_inaktivem_sachbearbeiter(db):
    erika = Employee(employee_number="S-1", first_name="Erika", last_name="Ehemalig", employee_group="angestellt",
                     weekly_hours=Decimal("40"), active=True)
    otto = Employee(employee_number="S-2", first_name="Otto", last_name="Offen", employee_group="angestellt",
                    weekly_hours=Decimal("40"), active=True)
    ina = Employee(employee_number="S-3", first_name="Ina", last_name="Inaktiv", employee_group="angestellt",
                   weekly_hours=Decimal("40"), active=False)
    db.add_all([erika, otto, ina]); db.flush()
    db.add_all([EmployeeRoleSettings(employee_id=erika.id, available_as_caseworker=True),
                EmployeeRoleSettings(employee_id=otto.id, available_as_caseworker=True)])
    order, _ = make_order_with_item(db, caseworker_employee_id=erika.id, project_manager_employee_id=erika.id)
    erika.active = False       # nach der Zuordnung ausgeschieden
    db.commit()
    return order, erika, otto, ina


def _personen(*leute) -> list[dict]:
    return [{"id": e.id, "first_name": e.first_name, "last_name": e.last_name, "active": e.active,
             "function_name": None} for e in leute]


@nur_mit_node
def test_auftragsseite_zeigt_den_inaktiven_sachbearbeiter_vorgewaehlt():
    db = db_session()
    _order, erika, otto, ina = _auftrag_mit_inaktivem_sachbearbeiter(db)
    alle = _personen(erika, otto, ina)
    skript = seitenskript("order.html", "async function load(", {"const orderId={{ order_id }};": "const orderId=1;"})
    skript += f"\nemployees={json.dumps(alle)};caseworkers={json.dumps(_personen(otto))};"
    # caseworkers liefert der Server nur aktive, freigegebene -- Erika fehlt dort
    sachbearbeiter = _js(skript, f"employeeOptions(caseworkers,{erika.id})")
    projektleiter = _js(skript, f"employeeOptions(employees,{erika.id})")
    for html in (sachbearbeiter, projektleiter):
        auswahl = gewaehlt(html)
        assert auswahl["wert"] == str(erika.id)
        assert auswahl["text"].startswith("Erika Ehemalig") and "(inaktiv)" in auswahl["text"]
        assert str(ina.id) not in [o["wert"] for o in optionen(html)]   # inaktiv und nicht gespeichert
    assert gewaehlt(_js(skript, "employeeOptions(caseworkers,null)"))["text"] == "— nicht zugeordnet —"


def test_auftrag_speichern_mit_unveraendertem_inaktivem_sachbearbeiter(threaded_db_session, router_test_client):
    db = threaded_db_session
    order, erika, otto, ina = _auftrag_mit_inaktivem_sachbearbeiter(db)
    keys = ui_keys("order.html", "saveOrder", "body:JSON.stringify(")
    assert {"caseworker_employee_id", "project_manager_employee_id"} <= set(keys)
    werte = {"title": "Dach neu", "status": order.status, "order_date": order.order_date.isoformat(),
             "execution_start": None, "execution_end": None, "caseworker_employee_id": erika.id,
             "project_manager_employee_id": erika.id, "payment_terms": None, "remarks": "geprüft",
             "intro_text": None, "outro_text": None, "outro_text_2": None}
    client = router_test_client(db, orders_router)
    response = client.put(f"/api/orders/{order.id}", json=payload(keys, werte))
    assert response.status_code == 200, response.text
    db.expire_all()
    gespeichert = db.get(Order, order.id)
    assert (gespeichert.title, gespeichert.caseworker_employee_id, gespeichert.project_manager_employee_id) == (
        "Dach neu", erika.id, erika.id)

    # Neu wählen darf man weiterhin nur aktive
    for feld in ("caseworker_employee_id", "project_manager_employee_id"):
        response = client.put(f"/api/orders/{order.id}", json=payload(keys, {**werte, feld: ina.id}))
        assert response.status_code == 422 and "inaktiv" in response.text
    assert client.put(f"/api/orders/{order.id}", json=payload(keys, {**werte, "caseworker_employee_id": otto.id})
                      ).status_code == 200


# ---------------------------------------------------------------------------
# Server: ein unverändert gespeicherter inaktiver Wert wird angenommen, ein neu gewählter nicht
# ---------------------------------------------------------------------------

def test_arbeitsvorbereitung_unveraenderter_inaktiver_zustaendiger_und_lieferant(threaded_db_session, router_test_client):
    from app.models import Supplier, WorkPreparationMaterial, WorkPreparationMaterialSupplier, WorkPreparationTask
    from app.routers.work_preparation import router as av_router
    from app.work_preparation import ensure_preparation

    db = threaded_db_session
    order, erika, _otto, ina = _auftrag_mit_inaktivem_sachbearbeiter(db)
    prep = ensure_preparation(db, order.id)
    alt, neu_inaktiv = Supplier(name="Alt GmbH", active=True), Supplier(name="Auch inaktiv", active=False)
    db.add_all([alt, neu_inaktiv]); db.flush()
    aufgabe = WorkPreparationTask(preparation_id=prep.id, title="Kran", assigned_employee_id=erika.id)
    material = WorkPreparationMaterial(preparation_id=prep.id, name="Blech", unit="m", status="bedarf",
                                       planned_quantity=Decimal("1"), supplier="Alt GmbH")
    db.add_all([aufgabe, material]); db.flush()
    db.add(WorkPreparationMaterialSupplier(material_id=material.id, supplier_id=alt.id))
    alt.active = False
    db.commit()
    client = router_test_client(db, av_router)

    keys = ui_keys("work_preparation.html", "saveTask", "body:JSON.stringify(")
    werte = {"title": "Kran bestellen", "status": "offen", "priority": "normal", "due_date": None,
             "assigned_employee_id": erika.id, "notes": None}
    assert client.put(f"/api/work-preparation/tasks/{aufgabe.id}", json=payload(keys, werte)).status_code == 200
    assert client.put(f"/api/work-preparation/tasks/{aufgabe.id}",
                      json={"assigned_employee_id": ina.id}).status_code == 422

    url = f"/api/work-preparation/materials/{material.id}"
    assert client.put(url, json={"planned_quantity": 5, "status": "bestellt", "notes": None,
                                 "supplier_id": alt.id}).status_code == 200
    assert client.put(url, json={"supplier_id": neu_inaktiv.id}).status_code == 422
    db.expire_all()
    assert db.get(WorkPreparationTask, aufgabe.id).assigned_employee_id == erika.id
    gespeichert = db.get(WorkPreparationMaterial, material.id)
    assert (gespeichert.planned_quantity, gespeichert.supplier) == (Decimal("5"), "Alt GmbH")


def test_angebot_unveraenderter_ausgeschiedener_sachbearbeiter():
    from fastapi import HTTPException

    from app.main import create_customer, create_project, create_quote, update_quote_document_meta
    from app.schemas import CustomerCreate, ProjectCreate, QuoteCreate, QuoteDocumentMetaUpdate

    db = db_session()
    erika = Employee(employee_number="Q-1", first_name="Erika", last_name="Ehemalig", employee_group="angestellt",
                     weekly_hours=Decimal("40"), active=True)
    ina = Employee(employee_number="Q-2", first_name="Ina", last_name="Inaktiv", employee_group="angestellt",
                   weekly_hours=Decimal("40"), active=False)
    db.add_all([erika, ina]); db.flush()
    db.add_all([EmployeeRoleSettings(employee_id=erika.id, available_as_caseworker=True),
                EmployeeRoleSettings(employee_id=ina.id, available_as_caseworker=True)])
    db.commit()
    kunde = create_customer(CustomerCreate(last_name="Kunde"), db)
    quote = create_quote(create_project(ProjectCreate(customer_id=kunde.id, name="P"), db).id, QuoteCreate(title="A"), db)

    def kopf(mitarbeiter):
        return update_quote_document_meta(quote.id, QuoteDocumentMetaUpdate(
            quote_date="2026-10-01", contact_person_employee_id=mitarbeiter, payment_terms="14 Tage",
            execution_period=None), db)

    kopf(erika.id)
    erika.active = False
    db.commit()
    assert kopf(erika.id).document_meta.contact_person_employee_id == erika.id   # unverändert: angenommen
    with pytest.raises(HTTPException) as fehler:
        kopf(ina.id)                                                              # neu gewählt: abgelehnt
    assert fehler.value.status_code == 422


def test_mitarbeiter_mit_inzwischen_inaktiver_funktion_laesst_sich_speichern():
    from app.employees import apply_employee_payload, ensure_default_employee_functions
    from app.models import EmployeeFunction
    from app.schemas import EmployeeCreate

    db = db_session()
    ensure_default_employee_functions(db)
    funktion, andere = db.query(EmployeeFunction).filter_by(employee_group="kaufmaennisch").limit(2).all()

    def daten(funktion_id, nachname="Büro"):
        return EmployeeCreate(employee_number="B-1", first_name="Bea", last_name=nachname, function_id=funktion_id,
                              employee_group="kaufmaennisch", weekly_hours=Decimal("40"), active=True)

    mitarbeiter = Employee(first_name="Bea", last_name="Büro", employee_group="kaufmaennisch", weekly_hours=Decimal("40"))
    apply_employee_payload(db, mitarbeiter, daten(funktion.id))   # Funktion steht in EmployeeProfile
    db.add(mitarbeiter); db.commit()
    assert mitarbeiter.profile.function_id == funktion.id
    funktion.active = andere.active = False
    db.commit()

    apply_employee_payload(db, mitarbeiter, daten(funktion.id, "Büro-Neu"))
    assert mitarbeiter.last_name == "Büro-Neu"
    with pytest.raises(ValueError, match="inaktiv"):
        apply_employee_payload(db, mitarbeiter, daten(andere.id))


def test_jede_seite_mit_auswahloptionen_bindet_den_helfer_ein():
    """Ohne {% include "_auswahl.html" %} bricht die Seite erst im Browser mit ReferenceError ab."""
    nutzer = []
    for vorlage in sorted(TEMPLATES.glob("*.html")):
        text = vorlage.read_text(encoding="utf-8")
        if vorlage.name != "_auswahl.html" and "auswahlOptionen(" in text:
            nutzer.append(vorlage.name)
            assert '{% include "_auswahl.html" %}' in text, vorlage.name
    assert len(nutzer) >= 18
