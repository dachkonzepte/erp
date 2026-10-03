"""Version 1.8.25 -- Strukturtest: ein Update-Handler übernimmt keine Felder, die nicht gesendet wurden.

Fehlerklasse (1.8.23, 1.8.25): ein PUT-Schema hat Felder mit Vorgabewert. Schickt ein Aufrufer ein
Feld nicht mit, setzt Pydantic den Vorgabewert ein -- liest der Handler dann payload.feld oder
payload.model_dump(), speichert er None, 0, "site" usw. über den gespeicherten Wert. So gingen
Zugangshinweise, Pause, LV-Position, Schlusstext 2, Kalkulationsnotiz und die Sichtbarkeitsgrenze
einer Aufgabe verloren.

Der Test geht jede PUT/PATCH-Route aus app.main durch (keine Liste im Test) und liest den Quelltext
ihres Handlers (AST, wie die quantize-Suche in test_v315). Hat das Body-Schema Felder mit
Vorgabewert, darf der Handler den Payload nur so lesen:
  - payload.model_dump(exclude_unset=True) oder payload.model_fields_set,
  - payload.<Pflichtfeld> (ohne Vorgabewert -- fehlt es, antwortet FastAPI 422),
  - payload.<Feld> nur unter einer Bedingung, die das Feld selbst prüft
    (if "feld" in ..., if payload.feld is not None, ... if payload.feld else ...).
Alles andere ist ein Fund: payload.<Feld mit Vorgabewert>, model_dump() ohne exclude_unset, und der
Payload als Ganzes an eine andere Funktion (was die damit tut, sieht der Test nicht).

BEKANNT: Handler, die das beim Einführen des Tests schon taten, je mit Grund. Laut Sweep 1.8.25 lässt
heute keine Oberfläche dort ein Feld weg -- kein Datenverlust, aber jeder neue Aufrufer, der ein Feld
nicht kennt, würde es leeren. Die Liste darf nur kürzer werden: ein Eintrag, der nicht mehr gefunden
wird, ist rot (dann streichen). Ein neuer Handler mit Fund ist rot -- Teil-Update bauen (PartialUpdate
in app/schemas.py, model_dump(exclude_unset=True)) oder alle Felder zu Pflichtfeldern machen."""

import ast
import inspect
import textwrap

from fastapi.routing import APIRoute
from pydantic import BaseModel

from tests.test_v326_monteur_datengrenze import _routers_in_betriebsreihenfolge


# ---------------------------------------------------------------------------
# Suche
# ---------------------------------------------------------------------------

def _mit_eltern(baum):
    for knoten in ast.walk(baum):
        for kind in ast.iter_child_nodes(knoten):
            kind._eltern = knoten
    return baum


def _bedingung_prueft(test: ast.AST, name: str, feld: str) -> bool:
    """Nennt die Bedingung das Feld -- als "feld" in ... oder als name.feld?"""
    for knoten in ast.walk(test):
        if isinstance(knoten, ast.Compare) and isinstance(knoten.left, ast.Constant) and knoten.left.value == feld \
                and any(isinstance(op, ast.In) for op in knoten.ops):
            return True
        if isinstance(knoten, ast.Attribute) and knoten.attr == feld and isinstance(knoten.value, ast.Name) \
                and knoten.value.id == name:
            return True
    return False


def _bewacht(knoten: ast.AST, name: str, feld: str) -> bool:
    eltern = getattr(knoten, "_eltern", None)
    while eltern is not None:
        if isinstance(eltern, (ast.If, ast.IfExp, ast.While)) and _bedingung_prueft(eltern.test, name, feld):
            return True
        eltern = getattr(eltern, "_eltern", None)
    return False


def _exclude_unset(aufruf: ast.AST) -> bool:
    return isinstance(aufruf, ast.Call) and any(
        k.arg == "exclude_unset" and isinstance(k.value, ast.Constant) and k.value.value is True
        for k in aufruf.keywords)


def payload_funde(quelle: str, name: str, mit_vorgabe: set[str]) -> list[str]:
    """Jede Stelle, an der der Handler (Quelltext) den Payload `name` so liest, dass ein nicht
    gesendetes Feld (eines aus `mit_vorgabe`) mit seinem Vorgabewert durchkommen kann."""
    funde = []
    for knoten in ast.walk(_mit_eltern(ast.parse(textwrap.dedent(quelle)))):
        if not (isinstance(knoten, ast.Name) and knoten.id == name and isinstance(knoten.ctx, ast.Load)):
            continue
        eltern = knoten._eltern
        if isinstance(eltern, ast.Attribute):
            if eltern.attr == "model_fields_set":
                continue
            if eltern.attr == "model_dump":
                if not _exclude_unset(eltern._eltern):
                    funde.append(f"{name}.model_dump() ohne exclude_unset")
                continue
            if eltern.attr in mit_vorgabe and not _bewacht(eltern, name, eltern.attr):
                funde.append(f"{name}.{eltern.attr}")
            continue
        funde.append(f"{name} als Ganzes weitergegeben")
    return sorted(set(funde))


def _body(route: APIRoute) -> tuple[str | None, type | None]:
    for parameter in inspect.signature(route.endpoint).parameters.values():
        if isinstance(parameter.annotation, type) and issubclass(parameter.annotation, BaseModel):
            return parameter.name, parameter.annotation
    return None, None


def update_handler_funde() -> tuple[dict[str, list[str]], int]:
    """({"PUT /pfad": [Funde]} für jede PUT/PATCH-Route mit Fund, Zahl der geprüften Routen)."""
    funde, geprueft = {}, 0
    for router in _routers_in_betriebsreihenfolge():
        for route in router.routes:
            if not isinstance(route, APIRoute) or not route.methods & {"PUT", "PATCH"}:
                continue
            name, schema = _body(route)
            if schema is None:
                continue
            geprueft += 1
            mit_vorgabe = {feld for feld, info in schema.model_fields.items() if not info.is_required()}
            if not mit_vorgabe:
                continue
            gefunden = payload_funde(inspect.getsource(route.endpoint), name, mit_vorgabe)
            if gefunden:
                for methode in sorted(route.methods & {"PUT", "PATCH"}):
                    funde[f"{methode} {route.path}"] = gefunden
    return funde, geprueft


# ---------------------------------------------------------------------------
# Selbsttest der Suche
# ---------------------------------------------------------------------------

ALTER_OBJEKT_HANDLER = '''
def update_property(property_id: int, payload: PropertyUpdate, db: Session = Depends(get_db)):
    property_obj = db.get(Property, property_id)
    values = payload.model_dump()
    customer_id = values.pop("customer_id", None)
    for key, value in values.items():
        setattr(property_obj, key, value)
'''

ALTER_KALKULATIONS_HANDLER = '''
def update_service_calculation(service_id, payload: ServiceCalculationUpdate, db=None):
    calc.site_time_minutes = payload.site_time_minutes
    calc.notes = payload.notes
    for item in payload.material_overrides:
        pass
'''

NEUER_HANDLER = '''
def put_x(x_id, payload: XUpdate, db=None):
    changes = payload.model_dump(exclude_unset=True)
    if "notes" in payload.model_fields_set:
        row.notes = payload.notes
    if payload.password:
        row.password = encrypt(payload.password)
    if payload.color is not None:
        row.color = payload.color
    items = payload.items if "items" in changes else []
    row.title = payload.title
'''


def test_selbsttest_alte_handler_fallen_auf():
    assert payload_funde(ALTER_OBJEKT_HANDLER, "payload", {"notes", "access_notes"}) == [
        "payload.model_dump() ohne exclude_unset"]
    assert payload_funde(ALTER_KALKULATIONS_HANDLER, "payload", {"site_time_minutes", "notes", "material_overrides"}) == [
        "payload.material_overrides", "payload.notes", "payload.site_time_minutes"]


def test_selbsttest_teil_update_und_waechter_sind_erlaubt():
    mit_vorgabe = {"notes", "password", "color", "items"}
    assert payload_funde(NEUER_HANDLER, "payload", mit_vorgabe) == []          # title ist Pflichtfeld
    assert payload_funde(NEUER_HANDLER, "payload", mit_vorgabe | {"title"}) == ["payload.title"]


def test_selbsttest_weitergeben_und_andere_namen():
    quelle = '''
def put_y(y_id, body: YUpdate, payload: str = ""):
    update_y(db, y_id, body)
    other = payload.notes
    update_z(**body.model_dump(exclude_unset=True), notes=body.notes)
'''
    assert payload_funde(quelle, "body", {"notes"}) == ["body als Ganzes weitergegeben", "body.notes"]


# ---------------------------------------------------------------------------
# Durchlauf
# ---------------------------------------------------------------------------

_VOLLES_FORMULAR = ("übernimmt jedes Feld; jede Oberfläche schickt heute alle (Sweep 1.8.25) -- "
                    "ein neuer Aufrufer, der eins weglässt, würde es leeren")
_LEEREN_GEWOLLT = "Weglassen heißt hier leeren bzw. entfernen, so gebaut; die Oberfläche schickt das Feld immer"
_NONE_UNVERAENDERT = ("kein Verstoß, für den Test nicht erkennbar: die Geschäftsfunktion behandelt None als "
                      "unverändert")
_OHNE_AUFRUFER = "übernimmt jedes Feld; keine Oberfläche ruft den Endpunkt auf"

BEKANNT = {
    "PUT /api/accounts/{account_id}": _VOLLES_FORMULAR,
    "PUT /api/ai-settings": _VOLLES_FORMULAR,
    "PUT /api/calculation-settings": _VOLLES_FORMULAR,
    "PUT /api/checklist-template-field-options/{option_id}": _NONE_UNVERAENDERT,
    "PUT /api/checklist-templates/{template_id}": _VOLLES_FORMULAR,
    "PUT /api/checklists/{checklist_id}/answers/{field_id}": _LEEREN_GEWOLLT,
    "PUT /api/customer-documents/{document_id}": _VOLLES_FORMULAR,
    "PUT /api/customers/{customer_id}": _VOLLES_FORMULAR,
    "PUT /api/customers/{customer_id}/extra-infos/{info_id}": _VOLLES_FORMULAR,
    "PUT /api/dashboard/widgets": _LEEREN_GEWOLLT,
    "PUT /api/document-categories/{category_id}": _VOLLES_FORMULAR,
    "PUT /api/document-email-templates/{document_type}": _VOLLES_FORMULAR,
    "PUT /api/document-layout/blocks/{block_id}": _VOLLES_FORMULAR,
    "PUT /api/email-settings": _VOLLES_FORMULAR,
    "PUT /api/email-settings/graph": _NONE_UNVERAENDERT,
    "PUT /api/employees/{employee_id}": _VOLLES_FORMULAR,
    "PUT /api/findings/{finding_id}/followup": _NONE_UNVERAENDERT,
    "PUT /api/incoming-invoices/{invoice_id}": _VOLLES_FORMULAR,
    "PUT /api/inquiries/{inquiry_id}": _VOLLES_FORMULAR,
    "PUT /api/inspection-template-items/{item_id}": _VOLLES_FORMULAR,
    "PUT /api/inspection-templates/{template_id}": _VOLLES_FORMULAR,
    "PUT /api/invoices/{invoice_id}/items/{item_id}": _NONE_UNVERAENDERT,
    "PUT /api/labor-rate-settings": _VOLLES_FORMULAR,
    "PUT /api/maintenance-contract-items/{item_id}": _OHNE_AUFRUFER,
    "PUT /api/maintenance-contracts/{contract_id}": _VOLLES_FORMULAR,
    "PUT /api/maintenance-settings": _VOLLES_FORMULAR,
    "PUT /api/materials/{material_id}": _VOLLES_FORMULAR,
    "PUT /api/operational-asset-inspections/{inspection_id}": _VOLLES_FORMULAR,
    "PUT /api/operational-assets/{asset_id}": _VOLLES_FORMULAR,
    "PUT /api/operational-assets/{asset_id}/recurring-cost": _LEEREN_GEWOLLT,
    "PUT /api/orders/{order_id}/items/{item_id}": _VOLLES_FORMULAR,
    "PUT /api/orders/{order_id}/sections/{section_id}": _VOLLES_FORMULAR,
    "PUT /api/orders/{order_id}/work-preparation": _VOLLES_FORMULAR,
    "PUT /api/payment-terms/{term_id}": _VOLLES_FORMULAR,
    "PUT /api/planning/holidays/{holiday_id}": _VOLLES_FORMULAR,
    "PUT /api/planning/settings": _VOLLES_FORMULAR,
    "PUT /api/planning/slots/{slot_id}": _VOLLES_FORMULAR,
    "PUT /api/project-documents/{document_id}": _VOLLES_FORMULAR,
    "PUT /api/project-pipeline-columns/{column_id}": _NONE_UNVERAENDERT,
    "PUT /api/projects/{project_id}": _VOLLES_FORMULAR,
    "PUT /api/quotes/{quote_id}": _VOLLES_FORMULAR,
    "PUT /api/quotes/{quote_id}/document-meta": _VOLLES_FORMULAR,
    "PUT /api/quotes/{quote_id}/items/{item_id}": _VOLLES_FORMULAR,
    "PUT /api/quotes/{quote_id}/items/{item_id}/calculation": _VOLLES_FORMULAR,
    "PUT /api/quotes/{quote_id}/items/{item_id}/layout": _VOLLES_FORMULAR,
    "PUT /api/quotes/{quote_id}/sections/{section_id}": _VOLLES_FORMULAR,
    "PUT /api/recurring-costs/{cost_id}": _VOLLES_FORMULAR,
    "PUT /api/reminder-levels/{level_id}": _VOLLES_FORMULAR,
    "PUT /api/reminders/{reminder_id}": _VOLLES_FORMULAR,
    "PUT /api/resources/{resource_id}": _VOLLES_FORMULAR,
    "PUT /api/roof-component-types/{component_type_id}": _VOLLES_FORMULAR,
    "PUT /api/roof-components/{component_id}": _VOLLES_FORMULAR,
    "PUT /api/roof-components/{component_id}/position": _LEEREN_GEWOLLT,
    "PUT /api/roof-layer-types/reorder": _NONE_UNVERAENDERT,
    "PUT /api/roof-layer-types/{layer_type_id}": _VOLLES_FORMULAR,
    "PUT /api/roof-type-template-defaults/{roof_type}": _LEEREN_GEWOLLT,
    "PUT /api/service-reports/{report_id}": _VOLLES_FORMULAR,
    "PUT /api/services/{service_id}": _VOLLES_FORMULAR,
    "PUT /api/settings/contract-basis-clauses/{basis_key}": _VOLLES_FORMULAR,
    "PUT /api/settings/employee-functions/{function_id}": _VOLLES_FORMULAR,
    "PUT /api/settings/number-sequences/{sequence_key}": _VOLLES_FORMULAR,
    "PUT /api/settings/option-groups/{group_key}/options/{option_id}": _VOLLES_FORMULAR,
    "PUT /api/suppliers/{supplier_id}": _VOLLES_FORMULAR,
    "PUT /api/task-columns/{column_id}": _NONE_UNVERAENDERT,
    "PUT /api/tasks/{task_id}/checklist-items/{item_id}": _NONE_UNVERAENDERT,
    "PUT /api/tax-keys/{key_id}": _VOLLES_FORMULAR,
    "PUT /api/teams/{team_id}": _VOLLES_FORMULAR,
    "PUT /api/time-backoffice/lock": _LEEREN_GEWOLLT,
    "PUT /api/time-backoffice/payroll-employees/{employee_id}": _VOLLES_FORMULAR,
    "PUT /api/time-backoffice/settings": _VOLLES_FORMULAR,
    "PUT /api/time-backoffice/work-time-models/{model_id}": _VOLLES_FORMULAR,
    "PUT /api/users/{user_id}": _VOLLES_FORMULAR,
}

# Die sieben Routen der Runde 1.8.25 -- hier darf nie wieder ein Fund stehen.
REPARIERT_1_8_25 = {
    "PUT /api/properties/{property_id}", "PUT /api/tasks/{task_id}", "PUT /api/time-entries/{entry_id}",
    "PUT /api/time-entry-groups/{group_id}", "PUT /api/settings/general", "PUT /api/invoices/{invoice_id}",
    "PUT /api/services/{service_id}/calculation",
}
# Seither einzeln zum Teil-Update umgebaut und aus BEKANNT gestrichen -- ebenso nie wieder ein Fund.
REPARIERT_SPAETER = {
    "PUT /api/orders/{order_id}",  # 1.8.32: neues Feld execution_period, ein Aufrufer ohne es hätte es geleert
    "PUT /api/roof-areas/{roof_area_id}",  # 1.8.46: Garantie Dritter umbenannt, Speicherweg auf Teil-Update
}


def test_kein_update_handler_uebernimmt_nicht_gesendete_felder():
    funde, geprueft = update_handler_funde()
    assert geprueft > 100, "Suche läuft ins Leere: PUT-Routen aus app.main nicht gefunden"
    neu = {route: gefunden for route, gefunden in funde.items() if route not in BEKANNT}
    assert not neu, ("Update-Handler übernehmen Felder, die der Aufrufer nicht geschickt hat (Vorgabewert "
                     "überschreibt den gespeicherten Wert). Teil-Update bauen (PartialUpdate in app/schemas.py, "
                     "model_dump(exclude_unset=True)) oder die Felder zu Pflichtfeldern machen:\n"
                     + "\n".join(f"  {route}: {', '.join(gefunden)}" for route, gefunden in sorted(neu.items())))
    veraltet = sorted(set(BEKANNT) - set(funde))
    assert not veraltet, "BEKANNT-Einträge ohne Fund -- streichen: " + ", ".join(veraltet)


def test_die_reparierten_routen_bleiben_ohne_fund():
    funde, _ = update_handler_funde()
    repariert = REPARIERT_1_8_25 | REPARIERT_SPAETER
    assert repariert.isdisjoint(funde), {r: funde[r] for r in repariert & set(funde)}
    assert repariert.isdisjoint(BEKANNT)
