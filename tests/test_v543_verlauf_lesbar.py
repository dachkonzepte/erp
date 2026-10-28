"""Version 1.9.123 (Stufe 5, R1 Nachrunde, Punkt 5, Merkliste 7b): der Verlauf lesbar -- /history und Projektmappe (GET /api/audit-logs).

    Zahlen      deutsch mit Einheit: Menge einer Auftragsposition „850 → 851“ mit „m²“ aus der Position, MwSt. „19“ mit „%“, Einheitspreis
                „50,00“ mit „€“, Stunden „7,5“ mit „h“ -- kein „.000000“
    Zeitpunkte  gespeichertes UTC in Europe/Berlin („01.07.2026 12:00“ aus 10:00 UTC), naive Ortszeit unverändert (Beginn einer Zeitbuchung),
                ein Tag deutsch
    Codes       Zeitart nach der Auswahlliste („Baustellenzeit“), auch im Namen des Datensatzes („· 14.10.2026 · Baustellenzeit · 3,25 h“);
                „value“ nur am Mangel übersetzt
    IDs         als Name: Sachbearbeiter, Kunde, Spalte der Pipeline; ein gelöschtes Ziel „Nr. n (nicht mehr vorhanden)“; eine Aufgabe nie
    JSON        „Daten (n Angaben)“
    Anzeige     verlaufAenderung() hängt die Einheit an den neuen Wert: „850 → 851 m²“
"""

import json
import re
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from app.audit import reset_audit_context, set_audit_context
from app.models import AuditLog, Employee, TimeEntry
from app.orders import update_order_item
from app.routers.audit import router as audit_router
from tests.test_v133_invoices import make_order_with_item
from tests.test_v334_auswahl_restfaelle import nur_mit_node

VORLAGEN = Path(__file__).resolve().parent.parent / "app" / "templates"


class Konto:
    id = 1
    display_name = "Ada Admin"
    username = "ada"


def _zeilen(db, router_test_client, rolle="admin", **filter):
    antwort = router_test_client(db, audit_router, role=rolle).get("/api/audit-logs", params={"limit": 1000})
    assert antwort.status_code == 200, antwort.text
    return [z for z in antwort.json() if all(z.get(k) == v for k, v in filter.items())]


def _eintrag(db, **werte):
    db.add(AuditLog(actor_name="Ada Admin", action=werte.pop("action", "geändert"), **werte))
    db.commit()


@pytest.fixture
def db(threaded_db_session):
    token = set_audit_context(Konto(), None)
    try:
        yield threaded_db_session
    finally:
        reset_audit_context(token)


def test_menge_einer_auftragsposition_mit_einheit(db, router_test_client):
    order, item = make_order_with_item(db, quantity=Decimal("850"))
    update_order_item(db, order.id, item.id, quantity=Decimal("851.00"))
    [z] = _zeilen(db, router_test_client, entity_type="Auftragsposition", field_name="quantity")
    assert (z["old_value"], z["new_value"], z["einheit"]) == ("850", "851", "m²")


def test_zahlen_deutsch_ohne_nullen_geld_mit_zwei_stellen(db, router_test_client):
    _eintrag(db, entity_type="Auftrag", entity_id="1", entity_label="AUF-1 · Dach", field_name="vat_rate", old_value="19.0000",
             new_value="7.0000")
    _eintrag(db, entity_type="Auftragsposition", entity_id="9", entity_label="1 Dach", field_name="unit_price", old_value="50.000000",
             new_value="1250.5")
    _eintrag(db, entity_type="Zeitbuchung", entity_id="3", entity_label="x", field_name="hours", old_value="7.5000", new_value="8.0000")
    werte = {z["field_name"]: (z["old_value"], z["new_value"], z["einheit"]) for z in _zeilen(db, router_test_client)
             if z["field_name"] in ("vat_rate", "unit_price", "hours")}
    assert werte == {"vat_rate": ("19", "7", "%"), "unit_price": ("50,00", "1.250,50", "€"), "hours": ("7,5", "8", "h")}


def test_zeitpunkte_in_berlin_ortszeit_bleibt(db, router_test_client):
    _eintrag(db, entity_type="Rechnung", entity_id="1", entity_label="R-1", field_name="finalized_at", old_value=None,
             new_value="2026-07-01T10:00:00.123456")
    _eintrag(db, entity_type="Zeitbuchung", entity_id="2", entity_label="x", field_name="started_at", old_value="2026-07-01T07:00:00",
             new_value="2026-07-01T07:15:00")
    _eintrag(db, entity_type="Auftrag", entity_id="1", entity_label="AUF-1", field_name="order_date", old_value="2026-10-01",
             new_value="2026-10-02")
    werte = {z["field_name"]: (z["old_value"], z["new_value"]) for z in _zeilen(db, router_test_client)}
    assert werte["finalized_at"] == (None, "01.07.2026 12:00")      # UTC 10:00 -> Sommerzeit 12:00
    assert werte["started_at"] == ("01.07.2026 07:00", "01.07.2026 07:15")  # naive Ortszeit
    assert werte["order_date"] == ("01.10.2026", "02.10.2026")


def test_zeitbuchung_im_namen_ohne_code(db, router_test_client):
    order, _ = make_order_with_item(db)
    mia = Employee(employee_number="E-1", first_name="Mia", last_name="Monteurin", employee_group="gewerblich", active=True)
    db.add(mia)
    db.commit()
    db.add(TimeEntry(order_id=order.id, project_id=order.project_id, employee_id=mia.id, work_date=date(2026, 10, 14), entry_type="site",
                     hours=Decimal("3.25"), status="booked"))
    db.commit()
    [z] = _zeilen(db, router_test_client, entity_type="Zeitbuchung", action="angelegt")
    assert z["entity_label"] == "E-1 Mia Monteurin · 14.10.2026 · Baustellenzeit · 3,25 h"
    _eintrag(db, entity_type="Zeitbuchung", entity_id="5", entity_label="x", field_name="entry_type", old_value="site", new_value="travel")
    [w] = _zeilen(db, router_test_client, entity_type="Zeitbuchung", field_name="entry_type")
    assert (w["old_value"], w["new_value"]) == ("Baustellenzeit", "Fahrzeit")


def test_ids_als_namen(db, router_test_client):
    order, _ = make_order_with_item(db)
    bea = Employee(employee_number="E-2", first_name="Bea", last_name="Büro", employee_group="kaufmaennisch", active=True)
    db.add(bea)
    db.commit()
    order.caseworker_employee_id = bea.id
    db.commit()
    [z] = _zeilen(db, router_test_client, entity_type="Auftrag", field_name="caseworker_employee_id")
    assert (z["old_value"], z["new_value"]) == (None, "E-2 Bea Büro")
    _eintrag(db, entity_type="Auftrag", entity_id=str(order.id), entity_label="x", field_name="customer_id", old_value="999",
             new_value=str(order.project.customer_id))
    [k] = _zeilen(db, router_test_client, entity_type="Auftrag", field_name="customer_id")
    assert (k["old_value"], k["new_value"]) == ("Nr. 999 (nicht mehr vorhanden)", "Test Kunde")
    _eintrag(db, entity_type="Mangel", entity_id="1", entity_label="x", field_name="task_id", old_value=None, new_value="4")
    [a] = _zeilen(db, router_test_client, entity_type="Mangel", field_name="task_id")
    assert a["new_value"] == "4"  # den Titel einer Aufgabe sehen nur Admin und Zuständige


def test_spalte_der_pipeline_als_name(db, router_test_client):
    from app.models import ProjectPipelineColumn
    order, _ = make_order_with_item(db)
    spalten = db.query(ProjectPipelineColumn).order_by(ProjectPipelineColumn.id).limit(2).all()
    order.project.pipeline_column_id = spalten[1].id
    db.commit()
    [z] = _zeilen(db, router_test_client, entity_type="Projekt", field_name="pipeline_column_id")
    assert not z["old_value"].isdigit() and not z["new_value"].isdigit()
    assert z["new_value"] in (spalten[1].label, getattr(spalten[1], "name", None))


def test_json_als_daten_und_value_nur_am_mangel(db, router_test_client):
    _eintrag(db, entity_type="Nebenforderung", entity_id="1", entity_label="x", field_name="calculation_json", old_value=None,
             new_value=json.dumps({"tage": 10, "satz": "9.27"}))
    _eintrag(db, entity_type="Kundenwissen", entity_id="1", entity_label="x", field_name="value", old_value="offen", new_value="zu")
    _eintrag(db, entity_type="Mangel", entity_id="2", entity_label="x", field_name="value", old_value=None, new_value="offen")
    zeilen = {(z["entity_type"], z["field_name"]): (z["old_value"], z["new_value"]) for z in _zeilen(db, router_test_client)}
    assert zeilen[("Nebenforderung", "calculation_json")] == (None, "Daten (2 Angaben)")
    assert zeilen[("Kundenwissen", "value")] == ("offen", "zu")  # bis 1.9.122 „Offen“ über die Tabelle des Mangels
    assert zeilen[("Mangel", "value")] == (None, "Offen")


def test_keine_rohwerte_in_einer_ganzen_antwort(db, router_test_client):
    """Über eine ganze Antwort mit Auftrag, Position, Zeitbuchung: kein „.000000“, kein ISO-Tag, kein Zeitartcode, keine ID als Wert."""
    order, item = make_order_with_item(db, quantity=Decimal("850"))
    update_order_item(db, order.id, item.id, quantity=Decimal("851"), unit_price=Decimal("52.5"))
    mia = Employee(employee_number="E-1", first_name="Mia", last_name="Monteurin", employee_group="gewerblich", active=True)
    db.add(mia)
    db.commit()
    db.add(TimeEntry(order_id=order.id, project_id=order.project_id, employee_id=mia.id, work_date=date(2026, 10, 14), entry_type="site",
                     hours=Decimal("7.5"), status="booked"))
    db.commit()
    text = json.dumps([{k: z[k] for k in ("entity_label", "old_value", "new_value")} for z in _zeilen(db, router_test_client)],
                      ensure_ascii=False)
    assert ".000000" not in text and not re.search(r"\b\d{4}-\d{2}-\d{2}\b", text)
    assert not re.search(r"\bsite\b", text)


@nur_mit_node
def test_verlauf_aenderung_haengt_die_einheit_an():
    from tests.test_v314_dashboard_month_berlin import _node
    skript = "\n".join(re.findall(r"<script>(.*?)</script>", (VORLAGEN / "_verlauf.html").read_text(encoding="utf-8"), re.S))
    faelle = [{"action": "geändert", "old_value": "850", "new_value": "851", "einheit": "m²"},
              {"action": "geändert", "old_value": "a", "new_value": "b", "einheit": None},
              {"action": "geändert", "old_value": "1", "new_value": "2", "einheit": "<b>"}]
    ergebnis = _node(skript + f"\nprocess.stdout.write(JSON.stringify({json.dumps(faelle)}.map(verlaufAenderung)));", "Europe/Berlin")
    assert ergebnis == ['<span class="old">850</span> → <span class="new">851</span> m²',
                        '<span class="old">a</span> → <span class="new">b</span>',
                        '<span class="old">1</span> → <span class="new">2</span> &lt;b&gt;']
