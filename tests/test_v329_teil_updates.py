"""Version 1.8.25 -- Datenverlust beim Speichern: sechs Update-Endpunkte übernahmen Felder, die ihr
Aufrufer gar nicht schickte (Pydantic setzt dann den Vorgabewert ein, der Handler speicherte ihn).

    PUT /api/properties/{id}            Kundenseite: Zugangshinweise, Ansprechpartner vor Ort geleert
    PUT /api/tasks/{id}                 Aufgaben-Editor: min_visible_role auf None (Finanz-Aufgabe für alle)
    PUT /api/time-entries/{id}          mobile Zeiterfassung: Pause durch Standard ersetzt, LV-Position geleert
    PUT /api/time-entry-groups/{id}     mobile Kolonnenbuchung: dasselbe
    PUT /api/settings/general           Stammdaten speichern: Logohöhe zurückgesetzt; Logohöhe speichern:
                                        veralteter Stand aller Stammdaten vom Laden der Seite
    PUT /api/invoices/{id}              Pauschale speichern: Schlusstext 2 geleert
    PUT /api/services/{id}/calculation  Leistungsformular: interne Notiz geleert

Beide Hälften sind behoben: der Server übernimmt nur gesendete Felder (PartialUpdate in
app/schemas.py, model_dump(exclude_unset=True)), die Oberfläche schickt nur, was sie bearbeitet.

Jeder Test liest die Schlüssel, die die Oberfläche wirklich schickt, aus der Vorlage (ui_keys()) und
schickt genau diese an den Endpunkt -- ein Schlüssel ohne Testwert ist rot (KeyError), damit ein neues
Feld in der Oberfläche hier auffällt. Zusätzlich steht je Oberfläche die genaue Schlüsselmenge fest:
schickt sie wieder ein Feld mit, das sie nicht bearbeitet, wird der Test rot."""

import re
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from app.models import (
    Customer, Invoice, OrderItem, Property, ServiceCalculation, Task, TimeEntry, TimeEntryGroup,
)
from app.routers.invoices import router as invoices_router
from app.routers.properties import router as properties_router
from app.routers.services import router as services_router
from app.routers.settings import router as settings_router
from app.routers.tasks import router as tasks_router
from app.routers.time_tracking import router as time_router
from app.invoices import create_abschlag_pauschal
from app.tasks import create_task
from app.time_tracking import create_group_manual_entry, create_manual_entry
from tests.test_v123_manual_services import make_service
from tests.test_v133_invoices import make_order_with_item
from tests.test_v264_field_time_tracking import _order
from tests.test_v302_crew_leader import _as, world  # noqa: F401 -- world ist eine Fixture

TEMPLATES = Path(__file__).resolve().parent.parent / "app" / "templates"
HEUTE = date.today()


# ---------------------------------------------------------------------------
# Schlüssel eines JS-Objektliterals aus der Vorlage lesen
# ---------------------------------------------------------------------------

_PAARE = {"{": "}", "(": ")", "[": "]"}


def _ende_der_zeichenkette(text: str, i: int) -> int:
    """Index hinter der bei text[i] beginnenden JS-Zeichenkette ('...', "...", `...${...}...`)."""
    quote, i = text[i], i + 1
    while text[i] != quote:
        if text[i] == "\\":
            i += 2
            continue
        if quote == "`" and text.startswith("${", i):
            i += 1 + len(klammer(text, i + 1))
            continue
        i += 1
    return i + 1


def _ende_des_kommentars(text: str, i: int) -> int | None:
    """Index hinter einem bei text[i] beginnenden JS-Kommentar, sonst None."""
    if text.startswith("//", i):
        ende = text.find("\n", i)
        return len(text) if ende < 0 else ende
    if text.startswith("/*", i):
        return text.index("*/", i) + 2
    return None


def klammer(text: str, start: int) -> str:
    """Der Text von der öffnenden Klammer text[start] bis zur passenden schließenden."""
    offen, i = [], start
    while i < len(text):
        c = text[i]
        if c in "'\"`":
            i = _ende_der_zeichenkette(text, i)
            continue
        if (ende := _ende_des_kommentars(text, i)) is not None:
            i = ende
            continue
        if c in _PAARE:
            offen.append(_PAARE[c])
        elif c in ")]}":
            assert offen and offen.pop() == c, f"Klammern passen nicht bei {text[max(0, i - 40):i + 1]!r}"
            if not offen:
                return text[start:i + 1]
        i += 1
    raise AssertionError("Klammer nicht geschlossen")


def _oberste_teile(innen: str) -> list[str]:
    """An Kommas der obersten Ebene getrennt."""
    teile, tiefe, anfang, i = [], 0, 0, 0
    while i < len(innen):
        c = innen[i]
        if c in "'\"`":
            i = _ende_der_zeichenkette(innen, i)
            continue
        if (ende := _ende_des_kommentars(innen, i)) is not None:
            innen = innen[:i] + " " * (ende - i) + innen[ende:]
            i = ende
            continue
        if c in _PAARE:
            tiefe += 1
        elif c in ")]}":
            tiefe -= 1
        elif c == "," and tiefe == 0:
            teile.append(innen[anfang:i])
            anfang = i + 1
        i += 1
    teile.append(innen[anfang:])
    return [t.strip() for t in teile if t.strip()]


def objekt_schluessel(objekt: str) -> list[str]:
    """Schlüssel der obersten Ebene eines Objektliterals "{a:1,b,...c}" -> ["a", "b", "...c"]."""
    schluessel = []
    for teil in _oberste_teile(objekt[1:-1]):
        if teil.startswith("..."):
            schluessel.append(teil)
            continue
        treffer = re.match(r"([A-Za-z_$][\w$]*)\s*(?::|$)", teil)
        assert treffer, f"Unbekannte Form im Objekt: {teil!r}"
        schluessel.append(treffer.group(1))
    return schluessel


def funktion(vorlage: str, name: str) -> str:
    html = (TEMPLATES / vorlage).read_text(encoding="utf-8")
    treffer = re.search(rf"function {re.escape(name)}\s*\(", html)
    assert treffer, f"{vorlage}: function {name}() nicht gefunden -- Test anpassen"
    return klammer(html, html.index("{", html.index(")", treffer.end())))


def ui_keys(vorlage: str, name: str, marke: str) -> list[str]:
    """Schlüssel des ersten Objektliterals nach `marke` in der Funktion `name` der Vorlage."""
    rumpf = funktion(vorlage, name)
    assert marke in rumpf, f"{vorlage}::{name}(): {marke!r} nicht gefunden -- Test anpassen"
    return objekt_schluessel(klammer(rumpf, rumpf.index("{", rumpf.index(marke) + len(marke) - 1)))


def payload(keys: list[str], werte: dict, gemerkt: dict | None = None) -> dict:
    """Payload mit genau den Schlüsseln der Oberfläche; "...x" setzt den beim Laden gemerkten Stand ein."""
    daten = {}
    for key in keys:
        if key.startswith("..."):
            daten.update(gemerkt or {})
        else:
            daten[key] = werte[key]
    return daten


def test_selbsttest_schluessel_lesen():
    js = """async function speichern(){const x=1; // Hinweis: don't {
      const payload={
      title, a:fn('x,y'), /* b' */ b:{c:1,d:[1,2]}, 'e':2, f:`t${g({h:1})}`, ...alt, i:(j,k)=>j};
      await api('/u',{method:'PUT',body:JSON.stringify({z:1,...payload})})}"""
    rumpf = klammer(js, js.index("{"))
    obj = klammer(rumpf, rumpf.index("{", rumpf.index("const payload=")))
    with pytest.raises(AssertionError):
        objekt_schluessel(obj)  # 'e' in Anführungszeichen kennt die Oberfläche nicht -- soll auffallen
    obj = obj.replace("'e':2, ", "")
    assert objekt_schluessel(obj) == ["title", "a", "b", "f", "...alt", "i"]
    aufruf = klammer(rumpf, rumpf.index("{", rumpf.index("JSON.stringify(")))
    assert objekt_schluessel(aufruf) == ["z", "...payload"]


# ---------------------------------------------------------------------------
# PUT /api/properties/{id}
# ---------------------------------------------------------------------------

OBJEKT_WERTE = {"customer_id": None, "name": "Halle Nord", "street": "Hafenweg 2", "postal_code": "20457",
                "city": "Hamburg", "notes": "Büro-Hinweis", "access_notes": "Schlüssel beim Hausmeister",
                "site_contact_name": "Herr Vor-Ort", "site_contact_phone": "0171 1234567"}
OBJEKT_ZUGANG = {"access_notes": "Code 4711, Hund im Hof", "site_contact_name": "Frau Haus",
                 "site_contact_phone": "040 999"}


@pytest.fixture
def objekt(threaded_db_session, router_test_client):
    db = threaded_db_session
    kunde = Customer(name="Kundin", last_name="Kundin")
    db.add(kunde); db.flush()
    halle = Property(customer_id=kunde.id, name="Halle", **OBJEKT_ZUGANG)
    db.add(halle); db.commit()
    return {"db": db, "id": halle.id, "kunde": kunde.id,
            "client": router_test_client(db, properties_router)}


@pytest.mark.parametrize("vorlage,name,marke,erwartet", [
    ("customer.html", "saveProperty", "const payload=", {"name", "street", "postal_code", "city", "notes"}),
    ("master_data_form.html", "save", "type==='properties'){body=",
     {"customer_id", "name", "street", "postal_code", "city", "notes"}),
])
def test_objekt_bearbeiten_ohne_zugangsfelder_laesst_sie_stehen(objekt, vorlage, name, marke, erwartet):
    keys = ui_keys(vorlage, name, marke)
    assert set(keys) == erwartet
    werte = {**OBJEKT_WERTE, "customer_id": objekt["kunde"]}
    response = objekt["client"].put(f"/api/properties/{objekt['id']}", json=payload(keys, werte))
    assert response.status_code == 200, response.text
    gespeichert = objekt["client"].get(f"/api/properties/{objekt['id']}").json()
    assert gespeichert["name"] == "Halle Nord" and gespeichert["city"] == "Hamburg"
    assert {k: gespeichert[k] for k in OBJEKT_ZUGANG} == OBJEKT_ZUGANG


def test_objektseite_schickt_und_aendert_den_zugang(objekt):
    keys = ui_keys("property.html", "saveProperty", "const payload=")
    assert set(keys) == set(OBJEKT_WERTE) - {"customer_id"}
    objekt["client"].put(f"/api/properties/{objekt['id']}", json=payload(keys, OBJEKT_WERTE))
    gespeichert = objekt["client"].get(f"/api/properties/{objekt['id']}").json()
    assert gespeichert["access_notes"] == "Schlüssel beim Hausmeister"


def test_objekt_ausdrueckliches_null_leert_name_nie(objekt):
    client = objekt["client"]
    assert client.put(f"/api/properties/{objekt['id']}", json={"access_notes": None}).status_code == 200
    assert client.get(f"/api/properties/{objekt['id']}").json()["access_notes"] is None
    assert client.put(f"/api/properties/{objekt['id']}", json={"name": None}).status_code == 422
    assert client.put(f"/api/properties/{objekt['id']}", json={"customer_id": None}).status_code == 422


# ---------------------------------------------------------------------------
# PUT /api/tasks/{id}
# ---------------------------------------------------------------------------

def test_aufgaben_editor_laesst_die_sichtbarkeitsgrenze_stehen(threaded_db_session, router_test_client):
    db = threaded_db_session
    aufgabe = create_task(db, title="Skonto Lieferant X", min_visible_role="buero_finanzen")
    keys = ui_keys("tasks.html", "saveTask", "const payload=")
    assert set(keys) == {"title", "description", "status", "priority", "due_date", "assigned_employee_id",
                         "project_id"}
    werte = {"title": "Skonto Lieferant X ziehen", "description": "bis Freitag", "status": aufgabe["status"],
             "priority": "hoch", "due_date": (HEUTE + timedelta(days=3)).isoformat(),
             "assigned_employee_id": None, "project_id": None}
    client = router_test_client(db, tasks_router)
    response = client.put(f"/api/tasks/{aufgabe['id']}", json=payload(keys, werte))
    assert response.status_code == 200, response.text
    db.expire_all()
    task = db.get(Task, aufgabe["id"])
    assert task.min_visible_role == "buero_finanzen"
    assert (task.title, task.priority, task.description) == ("Skonto Lieferant X ziehen", "hoch", "bis Freitag")


def test_aufgabe_teil_update_aendert_nur_gesendetes(threaded_db_session, router_test_client):
    db = threaded_db_session
    aufgabe = create_task(db, title="Angebot nachfassen", description="Kunde ruft zurück", priority="hoch")
    client = router_test_client(db, tasks_router)
    assert client.put(f"/api/tasks/{aufgabe['id']}", json={"priority": "niedrig"}).status_code == 200
    db.expire_all()
    task = db.get(Task, aufgabe["id"])
    assert (task.title, task.description, task.priority) == ("Angebot nachfassen", "Kunde ruft zurück", "niedrig")
    assert client.put(f"/api/tasks/{aufgabe['id']}", json={"title": None}).status_code == 422


# ---------------------------------------------------------------------------
# PUT /api/time-entries/{id} und /api/time-entry-groups/{id} (mobile Zeiterfassung)
# ---------------------------------------------------------------------------

ZEIT_WERTE = {"order_id": None, "work_date": HEUTE.isoformat(), "entry_type": "site", "activity": None,
              "hours": 6, "notes": "Rinne gereinigt", "order_item_id": None,
              # nur noch von der alten Oberfläche geschickt (Gegenprobe): Standardpause, eigene Nummer
              "break_minutes": 30, "employee_id": None}


def _position(db, order_id):
    return db.query(OrderItem).filter_by(order_id=order_id).first().id


@pytest.fixture
def lea_buchung(world):  # noqa: F811
    db, lea, order = world["db"], world["emp"]["lea"], world["order"]
    entry = create_manual_entry(db, employee_id=lea.id, order_id=order.id, work_date=HEUTE, hours=Decimal("4"),
                                order_item_id=_position(db, order.id), break_minutes=45, notes="alt")
    return {**world, "entry_id": entry.id}


def test_mobile_zeitbuchung_aendern_laesst_pause_und_lv_position(lea_buchung):
    db, order = lea_buchung["db"], lea_buchung["order"]
    keys = ui_keys("time_tracking_field.html", "saveManual", "const body=")
    assert set(keys) == {"order_id", "work_date", "entry_type", "activity", "hours", "notes"}
    assert ("`/api/time-entries/${editingId}`,{method:'PUT',headers:{'Content-Type':'application/json'},"
            "body:JSON.stringify(body)}") in funktion("time_tracking_field.html", "saveManual")
    werte = {**ZEIT_WERTE, "order_id": order.id, "employee_id": lea_buchung["emp"]["lea"].id}
    response = _as(lea_buchung, "lea").put(f"/api/time-entries/{lea_buchung['entry_id']}", json=payload(keys, werte))
    assert response.status_code == 200, response.text
    db.expire_all()
    entry = db.get(TimeEntry, lea_buchung["entry_id"])
    assert (entry.break_minutes, entry.order_item_id) == (45, _position(db, order.id))
    assert (entry.hours, entry.notes) == (Decimal("6"), "Rinne gereinigt")


def test_auftragswechsel_ohne_neue_position_laesst_die_alte_fallen(lea_buchung):
    """Die alte LV-Position gehört zum alten Auftrag -- bleibt sie stehen, lehnt der Server ab."""
    from tests.test_v264_field_time_tracking import _assign_via_team
    db, lea = lea_buchung["db"], lea_buchung["emp"]["lea"]
    neu, _ = _order(db, "AUF-329-0002", "P-329-0002")
    _assign_via_team(db, neu, lea)
    response = _as(lea_buchung, "lea").put(f"/api/time-entries/{lea_buchung['entry_id']}",
                                           json={"order_id": neu.id, "hours": 2})
    assert response.status_code == 200, response.text
    db.expire_all()
    entry = db.get(TimeEntry, lea_buchung["entry_id"])
    assert (entry.order_id, entry.order_item_id, entry.break_minutes) == (neu.id, None, 45)


def test_backoffice_korrektur_schickt_weder_pause_noch_mitarbeiter(lea_buchung, router_test_client):
    db, order = lea_buchung["db"], lea_buchung["order"]
    keys = ui_keys("time_backoffice.html", "saveEntryEdit", "body:JSON.stringify(")
    assert set(keys) == {"order_id", "order_item_id", "work_date", "entry_type", "activity", "hours", "notes"}
    werte = {**ZEIT_WERTE, "order_id": order.id, "order_item_id": _position(db, order.id)}
    client = router_test_client(db, time_router)
    response = client.put(f"/api/time-entries/{lea_buchung['entry_id']}", json=payload(keys, werte))
    assert response.status_code == 200, response.text
    db.expire_all()
    entry = db.get(TimeEntry, lea_buchung["entry_id"])
    assert (entry.employee_id, entry.break_minutes) == (lea_buchung["emp"]["lea"].id, 45)


def test_zeitbuchung_null_in_pflichtfeld_ist_422(lea_buchung):
    client = _as(lea_buchung, "lea")
    for feld in ("hours", "work_date", "order_id", "break_minutes"):
        assert client.put(f"/api/time-entries/{lea_buchung['entry_id']}", json={feld: None}).status_code == 422


def test_mobile_kolonnenbuchung_aendern_laesst_pause_und_lv_position(world):  # noqa: F811
    db, e, crew, order = world["db"], world["emp"], world["crew"], world["order"]
    position = _position(db, order.id)
    gruppe = create_group_manual_entry(
        db, employee_ids=[e["lea"].id, e["max"].id], team_id=crew.id, actor_employee_id=e["lea"].id,
        is_admin=False, order_id=order.id, work_date=HEUTE, hours=Decimal("8"), order_item_id=position,
        break_minutes=45)
    keys = ui_keys("time_tracking_field.html", "saveCrewDialog", "const body=")
    assert set(keys) == {"order_id", "work_date", "entry_type", "activity", "hours", "notes"}
    assert ("`/api/time-entry-groups/${crewEditingId}`,{method:'PUT',headers:{'Content-Type':'application/json'},"
            "body:JSON.stringify(body)}") in funktion("time_tracking_field.html", "saveCrewDialog")
    response = _as(world, "lea").put(f"/api/time-entry-groups/{gruppe.id}",
                                     json=payload(keys, {**ZEIT_WERTE, "order_id": order.id}))
    assert response.status_code == 200, response.text
    db.expire_all()
    gruppe = db.get(TimeEntryGroup, gruppe.id)
    assert (gruppe.break_minutes, gruppe.order_item_id, gruppe.hours) == (45, position, Decimal("6"))
    for entry in db.query(TimeEntry).filter_by(order_id=order.id).all():
        assert (entry.break_minutes, entry.order_item_id) == (45, position)


# ---------------------------------------------------------------------------
# PUT /api/settings/general
# ---------------------------------------------------------------------------

STAMMDATEN = {"company_name": "DACHKONZEPTE GmbH", "managing_director": "T. R.", "street": "Dachweg 1",
              "postal_code": "20095", "city": "Hamburg", "country": "Deutschland", "phone": "040 1",
              "email": "info@example.org", "website": "https://example.org",
              "public_base_url": "https://app.example.org", "tax_number": "12/345", "vat_id": "DE123",
              "register_court": "AG Hamburg", "register_number": "HRB 1", "iban": "DE00 1234",
              "bic": "HASPDEHH", "default_vat_rate": 19, "default_quote_intro": "Guten Tag",
              "default_quote_outro": "Mit freundlichen Grüßen", "sidebar_logo_height_px": 80}


def test_stammdaten_und_logohoehe_speichern_ueberschreiben_sich_nicht(threaded_db_session, router_test_client):
    client = router_test_client(threaded_db_session, settings_router)
    beim_laden = client.get("/api/settings/general").json()   # generalSettings beim Öffnen der Seite

    stammdaten = ui_keys("settings.html", "saveGeneral", "body:JSON.stringify(")
    assert "sidebar_logo_height_px" not in stammdaten
    hoehe = ui_keys("settings.html", "saveLogoHeight", "body:JSON.stringify(")
    assert hoehe == ["sidebar_logo_height_px"]

    assert client.put("/api/settings/general", json={"sidebar_logo_height_px": 56}).status_code == 200
    assert client.put("/api/settings/general", json=payload(stammdaten, STAMMDATEN)).status_code == 200
    assert client.get("/api/settings/general").json()["sidebar_logo_height_px"] == 56

    response = client.put("/api/settings/general", json=payload(hoehe, STAMMDATEN, gemerkt=beim_laden))
    assert response.status_code == 200, response.text
    gespeichert = client.get("/api/settings/general").json()
    assert gespeichert["sidebar_logo_height_px"] == 80
    assert {k: gespeichert[k] for k in ("company_name", "city", "phone", "iban")} == {
        "company_name": "DACHKONZEPTE GmbH", "city": "Hamburg", "phone": "040 1", "iban": "DE00 1234"}


def test_firmenname_darf_nicht_null_sein(threaded_db_session, router_test_client):
    client = router_test_client(threaded_db_session, settings_router)
    assert client.put("/api/settings/general", json={"company_name": None}).status_code == 422


# ---------------------------------------------------------------------------
# PUT /api/invoices/{id}
# ---------------------------------------------------------------------------

RECHNUNG_WERTE = {"progress_description": "2. Abschlag Dach", "lump_sum_net": "4500.00",
                  "intro_text": "Einleitung neu", "outro_text": "Schluss neu", "outro_text_2": "Schluss 2 neu",
                  # nur noch von der alten Oberfläche geschickt (Gegenprobe): Stand vom Laden
                  "due_date": None, "payment_terms": None}


@pytest.fixture
def pauschale(threaded_db_session, router_test_client):
    db = threaded_db_session
    order, _ = make_order_with_item(db)
    invoice = create_abschlag_pauschal(db, order, lump_sum_net=Decimal("3000"), progress_description="1. Abschlag")
    invoice.intro_text, invoice.outro_text, invoice.outro_text_2 = "Einleitung", "Schluss", "Bankverbindung beachten"
    invoice.payment_terms, invoice.due_date = "14 Tage netto", HEUTE + timedelta(days=14)
    db.commit()
    return {"db": db, "id": invoice.id, "client": router_test_client(db, invoices_router)}


def _rechnung(pauschale) -> Invoice:
    pauschale["db"].expire_all()
    return pauschale["db"].get(Invoice, pauschale["id"])


def test_pauschale_speichern_laesst_texte_und_frist_stehen(pauschale):
    keys = ui_keys("invoice_detail.html", "savePauschal", "body:JSON.stringify(")
    assert set(keys) == {"progress_description", "lump_sum_net"}
    response = pauschale["client"].put(f"/api/invoices/{pauschale['id']}", json=payload(keys, RECHNUNG_WERTE))
    assert response.status_code == 200, response.text
    inv = _rechnung(pauschale)
    assert (inv.lump_sum_net, inv.progress_description) == (Decimal("4500.00"), "2. Abschlag Dach")
    assert (inv.intro_text, inv.outro_text, inv.outro_text_2) == ("Einleitung", "Schluss", "Bankverbindung beachten")
    assert (inv.payment_terms, inv.due_date) == ("14 Tage netto", HEUTE + timedelta(days=14))
    assert [(i.short_text, i.unit_price) for i in inv.items] == [("2. Abschlag Dach", Decimal("4500.00"))]


def test_texte_speichern_laesst_pauschale_und_frist_stehen(pauschale):
    keys = ui_keys("invoice_detail.html", "saveHeader", "body:JSON.stringify(")
    assert set(keys) == {"intro_text", "outro_text", "outro_text_2"}
    response = pauschale["client"].put(f"/api/invoices/{pauschale['id']}", json=payload(keys, RECHNUNG_WERTE))
    assert response.status_code == 200, response.text
    inv = _rechnung(pauschale)
    assert inv.outro_text_2 == "Schluss 2 neu"
    assert (inv.lump_sum_net, inv.progress_description) == (Decimal("3000"), "1. Abschlag")
    assert (inv.payment_terms, inv.due_date) == ("14 Tage netto", HEUTE + timedelta(days=14))


# ---------------------------------------------------------------------------
# PUT /api/services/{id}/calculation
# ---------------------------------------------------------------------------

KALKULATION_WERTE = {"site_time_minutes": "30", "workshop_time_minutes": "0", "labor_rate_override": None,
                     "material_markup_pct_override": None, "equipment_cost": "5", "subcontractor_cost": "0",
                     "other_cost": "0", "overhead_pct_override": None, "risk_profit_pct_override": None,
                     "manual_sale_price": None, "notes": "Nur mit Gerüst kalkuliert", "material_overrides": []}


def _service_form_keys() -> list[str]:
    rumpf = funktion("service_form.html", "save")
    aufruf = rumpf.index("/calculation`")
    return objekt_schluessel(klammer(rumpf, rumpf.index("{", rumpf.index("JSON.stringify(", aufruf))))


def test_leistungsformular_laesst_die_kalkulationsnotiz_stehen(threaded_db_session, router_test_client):
    db = threaded_db_session
    service = make_service(db)
    db.add(ServiceCalculation(service_id=service.id, notes="Nur mit Gerüst kalkuliert", equipment_cost=Decimal("7")))
    db.commit()
    keys = _service_form_keys()
    assert "notes" not in keys and "material_overrides" not in keys
    client = router_test_client(db, services_router)
    response = client.put(f"/api/services/{service.id}/calculation", json=payload(keys, {**KALKULATION_WERTE,
                                                                                       "notes": "FALSCH"}))
    assert response.status_code == 200, response.text
    db.expire_all()
    calc = db.query(ServiceCalculation).filter_by(service_id=service.id).one()
    assert calc.notes == "Nur mit Gerüst kalkuliert"
    assert calc.equipment_cost == Decimal("5")


def test_kalkulationsdetail_schickt_die_notiz_und_darf_sie_leeren(threaded_db_session, router_test_client):
    db = threaded_db_session
    service = make_service(db)
    db.add(ServiceCalculation(service_id=service.id, notes="alt"))
    db.commit()
    keys = ui_keys("index.html", "saveCalculation", "const payload=")
    assert "notes" in keys
    client = router_test_client(db, services_router)
    response = client.put(f"/api/services/{service.id}/calculation",
                          json=payload(keys, {**KALKULATION_WERTE, "notes": None}))
    assert response.status_code == 200, response.text
    db.expire_all()
    assert db.query(ServiceCalculation).filter_by(service_id=service.id).one().notes is None
