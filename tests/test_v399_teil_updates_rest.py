"""Version 1.8.96 -- Teil-Update statt gemerkter Werte, die übrigen Stellen (Nebenbefund 3 der Durchsicht 1.8.25,
docs/archiv/teil-updates.md; Vorgehen wie tests/test_v399_teil_updates_geld.py):

    Einstellungen   toggleDocumentLayoutBlock        "anzeigen": alle Felder des Bausteins aus dem Stand beim Laden
    Einstellungen   saveContinuationHeaderPosition   Position des Folgeseiten-Kopfs: ebenso
    Einstellungen   saveEmailTemplate (Mahnstufe)    schon seit 1.8.80 nur Betreff und Text -- hier nur abgesichert
    Plantafel       dropSlot                         Verschieben: Status, Notiz, Planstunden, Anfahrt aus der Tafel
    Kostenposten    toggleActive                     aktivieren/deaktivieren: der ganze Kostenposten aus der Liste

Gleichzeitig (PostgreSQL, opt-in): der Jahresbetrag eines Kostenpostens wird aus Betrag und Rhythmus abgeleitet, Ende vor Beginn
eines Planeinsatzes auf dem zusammengeführten Stand geprüft -- beide unter einer Zeilensperre."""

from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.document_layout import load_layout, update_layout_block
from app.models import DocumentLayoutBlock, Order, PlanningSlot, PlanningSlotCapacity, RecurringCost, ReminderLevel, Team
from app.planning import create_slot
from app.recurring_costs import create_cost
from app.routers.document_layout import router as layout_router
from app.routers.planning import put_planning_slot, router as planning_router
from app.routers.recurring_costs import put_recurring_cost, router as costs_router
from app.routers.reminders import router as reminders_router
from app.schemas import PlanningSlotUpdate, RecurringCostUpdate
from tests.test_v133_invoices import make_order_with_item
from tests.test_v375_rechnungen_sperren import _run, _vorbereiten, pg  # noqa: F401  (pg ist eine Fixture)
from tests.test_v399_teil_updates_geld import _zeile, im_browser, js, nur_mit_node, schreibende, senden

D = Decimal


# ---------------------------------------------------------------------------
# Einstellungen: Bausteine des Dokumentlayouts
# ---------------------------------------------------------------------------

@pytest.fixture
def bausteine(threaded_db_session, router_test_client):
    db = threaded_db_session
    ids = {b.block_type: b.id for b in load_layout(db, "default")}
    return {"db": db, "client": router_test_client(db, layout_router), "ids": ids}


def _bausteine_beim_laden(bausteine) -> dict:
    return {b["block_type"]: b for b in bausteine["client"].get("/api/document-layout/default").json()}


@nur_mit_node
def test_baustein_anzeigen_schickt_nur_visible(bausteine):
    """Nach dem Laden der Einstellungen wurde die Fußzeile verschoben -- bis 1.8.95 schob "anzeigen" sie zurück."""
    db, client, fid = bausteine["db"], bausteine["client"], bausteine["ids"]["footer_text"]
    beim_laden = _bausteine_beim_laden(bausteine)
    assert client.put(f"/api/document-layout/blocks/{fid}", json={"x_mm": "25", "font_size": "9"}).status_code == 200
    aufrufe = im_browser("settings.html", ["toggleDocumentLayoutBlock"], f"var documentLayoutBlocks = {js(beim_laden)};",
                         "await toggleDocumentLayoutBlock('footer_text', true);")
    assert schreibende(aufrufe) == [("PUT", f"/api/document-layout/blocks/{fid}", {"visible": True})]
    senden(client, aufrufe)
    gespeichert = _zeile(db, DocumentLayoutBlock, fid)
    assert (gespeichert["visible"], gespeichert["x_mm"], gespeichert["font_size"]) == (True, D("25"), D("9"))


@nur_mit_node
def test_folgeseiten_kopf_position_schickt_nur_y(bausteine):
    db, client, cid = bausteine["db"], bausteine["client"], bausteine["ids"]["continuation_header"]
    beim_laden = _bausteine_beim_laden(bausteine)
    assert client.put(f"/api/document-layout/blocks/{cid}", json={"visible": False, "text_align": "right"}).status_code == 200
    vorher = _zeile(db, DocumentLayoutBlock, cid)
    aufrufe = im_browser("settings.html", ["saveContinuationHeaderPosition"],
                         f"var documentLayoutBlocks = {js(beim_laden)};", "await saveContinuationHeaderPosition(40);")
    assert schreibende(aufrufe) == [("PUT", f"/api/document-layout/blocks/{cid}", {"y_mm": 40})]
    senden(client, aufrufe)
    assert _zeile(db, DocumentLayoutBlock, cid) == vorher | {"y_mm": D("40")}


def test_baustein_null_ist_422_content_bleibt_ungeschrieben(bausteine):
    """content nimmt der Server an und schreibt ihn wie bisher nicht (Nebenbefund 4 aus 1.8.25, nur gemeldet)."""
    db, client, fid = bausteine["db"], bausteine["client"], bausteine["ids"]["footer_text"]
    vorher = _zeile(db, DocumentLayoutBlock, fid)
    for feld in ("x_mm", "y_mm", "width_mm", "height_mm", "font_size", "font_weight", "text_align", "visible"):
        assert client.put(f"/api/document-layout/blocks/{fid}", json={feld: None, "y_mm": "100"}
                          if feld != "y_mm" else {feld: None}).status_code == 422, feld
    assert _zeile(db, DocumentLayoutBlock, fid) == vorher
    assert client.put(f"/api/document-layout/blocks/{fid}", json={"content": "Text"}).status_code == 200
    assert _zeile(db, DocumentLayoutBlock, fid) == vorher
    with pytest.raises(TypeError):
        update_layout_block(db, db.get(DocumentLayoutBlock, fid), farbe="rot")


# ---------------------------------------------------------------------------
# Einstellungen: E-Mail-Vorlage einer Mahnstufe (seit 1.8.80 Teil-Update -- nur abgesichert)
# ---------------------------------------------------------------------------

@nur_mit_node
def test_mahnstufe_email_vorlage_schickt_nur_betreff_und_text(threaded_db_session, router_test_client):
    db = threaded_db_session
    client = router_test_client(db, reminders_router)
    beim_laden = client.get("/api/reminder-levels").json()
    stufe = next(s for s in beim_laden if s["level"] == 1)
    assert client.put(f"/api/reminder-levels/{stufe['id']}",
                      json={"label": "Zahlungserinnerung neu", "days_after_previous_step": 9,
                            "text_template": "neu"}).status_code == 200
    vorher = _zeile(db, ReminderLevel, stufe["id"])
    formular = {"emailTemplateType": "reminder:1", "emailTemplateSubject": "Erinnerung {rechnungsnummer}",
                "emailTemplateBody": "Guten Tag"}
    aufrufe = im_browser("settings.html", ["saveEmailTemplate"],
                         f"var FORM = {js(formular)}; function v(id) {{ return FORM[id] ?? ''; }} "
                         "document.getElementById('emailTemplateType').value = FORM.emailTemplateType; "
                         f"var reminderLevels = {js(beim_laden)}; async function ladeMahnstufen() {{}}",
                         "await saveEmailTemplate();")
    body = {"email_subject_template": "Erinnerung {rechnungsnummer}", "email_body_template": "Guten Tag"}
    assert schreibende(aufrufe) == [("PUT", f"/api/reminder-levels/{stufe['id']}", body)]
    senden(client, aufrufe)
    assert _zeile(db, ReminderLevel, stufe["id"]) == vorher | body


# ---------------------------------------------------------------------------
# Plantafel
# ---------------------------------------------------------------------------

def _einsatz(db, order_id, **werte):
    teams = [Team(name="Kolonne A", active=True), Team(name="Kolonne B", active=True)]
    db.add_all(teams)
    db.commit()
    slot = create_slot(db, order_id=order_id, team_id=teams[0].id, start_date=date(2026, 10, 12),
                       end_date=date(2026, 10, 16), notes="alt", planned_hours=D("20"), **werte)
    return slot.id, teams[0].id, teams[1].id


@pytest.fixture
def tafel(threaded_db_session, router_test_client):
    db = threaded_db_session
    order, _ = make_order_with_item(db)
    slot_id, team_a, team_b = _einsatz(db, order.id)
    return {"db": db, "client": router_test_client(db, planning_router), "id": slot_id, "url": f"/api/planning/slots/{slot_id}",
            "team_a": team_a, "team_b": team_b}


def _einsatz_stand(db, slot_id) -> dict:
    zeile = _zeile(db, PlanningSlot, slot_id)
    kapazitaet = db.query(PlanningSlotCapacity).filter_by(slot_id=slot_id).one()
    return zeile | {"planned_hours": kapazitaet.planned_hours, "travel": kapazitaet.travel_hours_per_employee_day}


@nur_mit_node
def test_plantafel_verschieben_schickt_nur_team_und_zeitraum(tafel):
    """Nach dem Laden der Tafel hat jemand den Einsatz bestätigt, die Notiz und die Planstunden geändert. Bis 1.8.95 setzte das
    Verschieben alles auf den Stand beim Laden zurück."""
    db, client = tafel["db"], tafel["client"]
    beim_laden = client.get("/api/planning", params={"start": "2026-10-12", "end": "2026-10-25"}).json()
    neu = {"status": "bestaetigt", "notes": "Gerüst steht", "planned_hours": "30", "travel_hours_per_employee_day": "1"}
    assert client.put(tafel["url"], json=neu).status_code == 200
    aufrufe = im_browser(
        "planning.html", ["dropSlot", "findSlot", "iso", "addDays"],
        f"var board = {js(beim_laden)}; var dragData = {{id: {tafel['id']}, days: 5}}; var view = 'teams'; const DAY_W = 120; "
        "var periodStart = new Date('2026-10-12T12:00:00'); async function loadBoard() {} "
        "function localDateIso(d) { const p = n => String(n).padStart(2, '0'); "
        "return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`; } "
        "document.getElementById('rangeDays').value = '14';",
        f"await dropSlot({{preventDefault() {{}}, clientX: 245, currentTarget: {{classList: {{remove() {{}}}}, "
        f"getBoundingClientRect: () => ({{left: 0}})}}}}, {tafel['team_b']});")
    body = {"team_id": tafel["team_b"], "start_date": "2026-10-14", "end_date": "2026-10-18"}
    assert schreibende(aufrufe) == [("PUT", tafel["url"], body)]
    senden(client, aufrufe)
    stand = _einsatz_stand(db, tafel["id"])
    assert (stand["start_date"], stand["end_date"]) == (date(2026, 10, 14), date(2026, 10, 18))
    assert (stand["status"], stand["notes"], stand["planned_hours"], stand["travel"]) == ("bestaetigt", "Gerüst steht", D("30"),
                                                                                        D("1"))
    assert client.get("/api/planning", params={"start": "2026-10-12", "end": "2026-10-25"}).json()["slots"][0]["team_id"] == \
        tafel["team_b"]


def test_plantafel_pruefungen_auf_dem_zusammengefuehrten_stand(tafel):
    """Ende vor Beginn mit nur einem gesendeten Datum, Anfahrt über der Tagesarbeitszeit: 422; unbekanntes Team: 404 (wie
    bisher, der Router macht aus "nicht gefunden" 404) -- nichts gespeichert, auch nicht die mitgeschickte Notiz."""
    db, client, url = tafel["db"], tafel["client"], tafel["url"]
    vorher = _einsatz_stand(db, tafel["id"])
    for body, status in (({"end_date": "2026-10-11", "notes": "x"}, 422), ({"start_date": "2026-10-17", "notes": "x"}, 422),
                         ({"travel_hours_per_employee_day": "20", "notes": "x"}, 422), ({"team_id": 999999, "notes": "x"}, 404),
                         ({"start_date": "2026-10-20", "end_date": "2026-10-19"}, 422)):
        antwort = client.put(url, json=body)
        assert antwort.status_code == status, (body, antwort.text)
    assert _einsatz_stand(db, tafel["id"]) == vorher
    assert client.put(url, json={"start_date": "2026-10-17", "end_date": "2026-10-20"}).status_code == 200
    assert client.put(url, json={"notes": None}).status_code == 200  # nullbar: leert
    stand = _einsatz_stand(db, tafel["id"])
    assert stand == vorher | {"start_date": date(2026, 10, 17), "end_date": date(2026, 10, 20), "notes": None}


def test_plantafel_null_in_pflichtfeldern_ist_422(tafel):
    db, client, url = tafel["db"], tafel["client"], tafel["url"]
    vorher = _einsatz_stand(db, tafel["id"])
    for feld in ("team_id", "start_date", "end_date", "status", "planned_hours", "travel_hours_per_employee_day"):
        assert client.put(url, json={feld: None, "notes": "x"}).status_code == 422, feld
    assert _einsatz_stand(db, tafel["id"]) == vorher


# ---------------------------------------------------------------------------
# Kostenposten
# ---------------------------------------------------------------------------

@pytest.fixture
def kosten(threaded_db_session, router_test_client):
    db = threaded_db_session
    cost = create_cost(db, {"label": "Bürolokal", "category": "Miete", "net_amount": "100.00", "billing_interval": "monatlich",
                            "vendor": "Vermieter", "notes": "alt"})
    return {"db": db, "client": router_test_client(db, costs_router), "id": cost["id"], "url": f"/api/recurring-costs/{cost['id']}"}


@nur_mit_node
def test_kostenposten_aktivieren_schickt_nur_active(kosten):
    """Nach dem Laden der Liste wurde der Betrag erhöht -- bis 1.8.95 setzte "deaktivieren" ihn samt Jahresbetrag zurück."""
    db, client = kosten["db"], kosten["client"]
    beim_laden = client.get("/api/recurring-costs").json()
    assert client.put(kosten["url"], json={"net_amount": "150.00"}).status_code == 200
    aufrufe = im_browser("recurring_costs.html", ["toggleActive"],
                         f"var costs = {js(beim_laden)}; async function loadAll() {{}}", f"await toggleActive({kosten['id']});")
    assert schreibende(aufrufe) == [("PUT", kosten["url"], {"active": False})]
    senden(client, aufrufe)
    gespeichert = _zeile(db, RecurringCost, kosten["id"])
    assert (gespeichert["active"], gespeichert["net_amount"], gespeichert["annual_amount"]) == (False, D("150.00"), D("1800.00"))
    assert (gespeichert["label"], gespeichert["vendor"], gespeichert["notes"]) == ("Bürolokal", "Vermieter", "alt")


def test_kostenposten_jahresbetrag_aus_gespeichertem_und_gesendetem(kosten):
    db, client, url = kosten["db"], kosten["client"], kosten["url"]
    assert client.put(url, json={"billing_interval": "vierteljaehrlich"}).status_code == 200
    assert _zeile(db, RecurringCost, kosten["id"])["annual_amount"] == D("400.00")  # 100 je Quartal
    assert client.put(url, json={"net_amount": "250.00"}).status_code == 200
    gespeichert = _zeile(db, RecurringCost, kosten["id"])
    assert (gespeichert["billing_interval"], gespeichert["annual_amount"]) == ("vierteljaehrlich", D("1000.00"))
    assert (gespeichert["tax_rate_pct"], gespeichert["overhead_classification"]) == (D("19.00"), "keine")


def test_kostenposten_angriffe(kosten):
    db, client, url = kosten["db"], kosten["client"], kosten["url"]
    vorher = _zeile(db, RecurringCost, kosten["id"])
    for feld in ("label", "overhead_classification", "net_amount", "tax_rate_pct", "billing_interval", "active"):
        assert client.put(url, json={feld: None, "notes": "x"}).status_code == 422, feld
    for body in ({"asset_id": 999999, "notes": "x"}, {"tax_rate_pct": "16.00"}, {"billing_interval": "taeglich"},
                 {"label": ""}):
        assert client.put(url, json=body).status_code == 422, body
    assert _zeile(db, RecurringCost, kosten["id"]) == vorher
    assert client.put(url, json={"notes": None, "category": None}).status_code == 200  # nullbar: leert
    assert _zeile(db, RecurringCost, kosten["id"]) == vorher | {"notes": None, "category": None}


# ---------------------------------------------------------------------------
# Gleichzeitig: PostgreSQL (opt-in)
# ---------------------------------------------------------------------------

def test_postgresql_kostenposten_betrag_und_rhythmus_gleichzeitig(pg):
    """Betrag hier, Rhythmus dort: der Jahresbetrag passt zu beiden -- ohne die Sperre der Zeile rechnete die zweite mit dem
    Betrag von vor der ersten."""
    Session, _ = pg
    cost_id = _vorbereiten(Session, lambda s: create_cost(s, {"label": "Miete", "net_amount": "100.00",
                                                              "billing_interval": "monatlich"})["id"])
    _run(Session, lambda s: put_recurring_cost(cost_id, RecurringCostUpdate(net_amount=D("200")), db=s, _role=None),
         lambda s: put_recurring_cost(cost_id, RecurringCostUpdate(billing_interval="jaehrlich"), db=s, _role=None))
    gespeichert = _vorbereiten(Session, lambda s: (lambda c: (c.net_amount, c.billing_interval, c.annual_amount))(
        s.get(RecurringCost, cost_id)))
    assert gespeichert == (D("200.00"), "jaehrlich", D("200.00"))


def test_postgresql_planeinsatz_beginn_und_ende_gleichzeitig(pg):
    """Beginn hier auf den 15., Ende dort auf den 13.: jedes für sich gültig, zusammen Ende vor Beginn. Unter der Sperre der
    Arbeitsvorbereitung prüft die zweite auf dem Stand nach der ersten und lehnt ab."""
    Session, order_id = pg
    slot_id, _, _ = _vorbereiten(Session, lambda s: _einsatz(s, order_id))
    _, zweite = _run(Session,
                     lambda s: put_planning_slot(slot_id, PlanningSlotUpdate(start_date=date(2026, 10, 15)), db=s, _role=None),
                     lambda s: put_planning_slot(slot_id, PlanningSlotUpdate(end_date=date(2026, 10, 13)), db=s, _role=None))
    assert isinstance(zweite, HTTPException) and zweite.status_code == 422, zweite
    gespeichert = _vorbereiten(Session, lambda s: (lambda x: (x.start_date, x.end_date))(s.get(PlanningSlot, slot_id)))
    assert gespeichert == (date(2026, 10, 15), date(2026, 10, 16))
    vorbereitung = _vorbereiten(Session, lambda s: (lambda o: (o.planned_start, o.planned_end))(
        s.get(PlanningSlot, slot_id).preparation))
    assert vorbereitung == (date(2026, 10, 15), date(2026, 10, 16))


def test_postgresql_planeinsatz_entfernen_und_verschieben_ohne_deadlock(pg, monkeypatch):
    """Seit 1.8.96 sperrt update_slot() zuerst die Arbeitsvorbereitung, dann den Einsatz; delete_slot() sperrte (implizit) erst
    den Einsatz (DELETE), dann die Vorbereitung (Beginn/Ende abgleichen). Läuft das Verschieben genau zwischen diese beiden
    Schritte, warteten beide aufeinander. Hier deterministisch: das Entfernen hält nach dem DELETE an, das Verschieben startet --
    seit delete_slot() die Vorbereitung zuerst sperrt, wartet das Verschieben und findet den Einsatz danach nicht mehr (404)."""
    import threading
    import time

    import app.planning as planning

    Session, order_id = pg
    slot_id, _, _ = _vorbereiten(Session, lambda s: _einsatz(s, order_id))
    prep_id = _vorbereiten(Session, lambda s: s.get(PlanningSlot, slot_id).preparation_id)
    echt = planning.sync_preparation_dates
    geloescht, weiter = threading.Event(), threading.Event()

    def angehalten(db, preparation_id):
        if threading.current_thread().name == "entfernen":
            geloescht.set()
            weiter.wait(timeout=30)
        return echt(db, preparation_id)
    monkeypatch.setattr(planning, "sync_preparation_dates", angehalten)
    ergebnis = {}

    def laufen(name, aktion):
        s = Session()
        try:
            ergebnis[name] = aktion(s)
        except Exception as exc:  # noqa: BLE001
            ergebnis[name] = exc
        finally:
            s.close()
    entfernen = threading.Thread(name="entfernen", target=laufen,
                                 args=("entfernen", lambda s: planning.delete_slot(s, slot_id)))
    verschieben = threading.Thread(target=laufen, args=("verschieben", lambda s: put_planning_slot(
        slot_id, PlanningSlotUpdate(start_date=date(2026, 10, 13)), db=s, _role=None)))
    entfernen.start()
    assert geloescht.wait(timeout=10)
    verschieben.start()
    time.sleep(1.5)  # länger als deadlock_timeout (1 s): ein Deadlock wäre jetzt erkannt
    weiter.set()
    entfernen.join(timeout=30)
    verschieben.join(timeout=30)
    assert ergebnis["entfernen"] == prep_id, ergebnis
    assert isinstance(ergebnis["verschieben"], HTTPException) and ergebnis["verschieben"].status_code == 404, ergebnis
    assert _vorbereiten(Session, lambda s: s.get(PlanningSlot, slot_id)) is None
