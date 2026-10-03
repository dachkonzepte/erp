"""Version 1.8.46 -- Stufe 2c-1: Fundament Abnahme und Gewährleistung (docs/archiv/abnahme-und-gewaehrleistung.md).

Punkte der Vorgabe, je mit Gegenprobe im Scratchpad-Skript der Runde:
3. Leistungsart und Gewährleistungsdauer am Auftrag: Vorschlag je Vertragsgrundlage mit Fundstelle, Übernahme nur
   bewusst, Abweichung nur mit Begründung, sonst "nicht festgelegt"; Historie.
4. Abnahme: Art, Datum ohne Vorgabe, Umfang mit Dachflächen nur aus dem Objekt des Projekts, Ergebnis mit zwei
   Pflichtfragen, Einwendungen, Erklärende mit Vollmacht-Warnung, Beleg oder Begründung; unveränderlich, Verwerfen mit
   Begründung, Historie; ab buero_auftrag, Monteure nichts.
5. Gewährleistungsende nur abgeleitet (§ 187 Abs. 1, § 188 Abs. 2 und 3 BGB), an Auftrag, Objekt und Dachfläche,
   nicht bei "verweigert".
7. Abgleich mit dem Angebot gesperrt, solange eine nicht verworfene Abnahme besteht.

Angriffstests: Dachfläche eines fremden Objekts, Monteur liest Abnahmen, Ändern nach dem Speichern. Gegen PostgreSQL
(opt-in über ERP_TEST_POSTGRES_URL, Wegwerf-Schema, Regel 16): Sperre zwischen Erfassen und Abgleich, Bestandteile wie
SQLite über das Plugin der Runde."""

import hashlib
import importlib.util
import json
import os
import stat
import threading
import time
import uuid
from datetime import date, datetime, timedelta
from io import BytesIO
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from PIL import Image
from sqlalchemy import create_engine, inspect, select, text, update
from sqlalchemy.orm import close_all_sessions, sessionmaker

from app import acceptances as acceptances_module
from app import project_participants as participants_module
from app.acceptances import AcceptanceExistsError, ensure_no_active_acceptance
from app.audit import record_audit_entry  # noqa: F401  (Historie wird über die Tabelle geprüft)
from app.berlin_time import berlin_today
from app.contacts import create_contact
from app.contract_basis import change_order_contract_basis
from app.database import Base
from app.models import (
    ArchiveImmutableError, AuditLog, Order, OrderAcceptance, OrderAcceptanceFile, OrderAcceptanceRoofArea,
    OrderWarrantyChange, Project, Property, RoofArea,
)
from app.orders import load_order, order_to_dict, sync_order_from_source_quote
from app.project_participants import add_participant, store_power_of_attorney
from app.routers import acceptances as acceptances_router
from app.routers import orders as orders_router
from app.routers import project_participants as participants_router
from app.routers import roof_areas as roof_areas_router
from app.warranty import PROPOSALS, duration_text, warranty_end, warranty_proposal
from tests.test_v325_contract_basis import make_quote
from tests.test_v335_vertragsvorlagen import beauftragen

ROOT = Path(__file__).resolve().parent.parent
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
SVG = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
HTML_ALS_PDF = b"<html><body>kein PDF</body></html>"
PG_TEST_DATABASE_URL = os.getenv("ERP_TEST_POSTGRES_URL")


def _png(farbe="white") -> bytes:
    buf = BytesIO()
    Image.new("RGB", (6, 4), farbe).save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture(autouse=True)
def ablage(tmp_path, monkeypatch):
    monkeypatch.setattr(acceptances_module, "ACCEPTANCE_FILE_ROOT", tmp_path / "abnahmen")
    monkeypatch.setattr(participants_module, "POWER_OF_ATTORNEY_ROOT", tmp_path / "vollmachten")
    return tmp_path / "abnahmen"


def _objekt(db, customer_id, name, flaechen):
    prop = Property(customer_id=customer_id, name=name, street="Hallenweg 1", postal_code="52531", city="Uebach")
    db.add(prop)
    db.flush()
    areas = {}
    for flaeche in flaechen:
        area = RoofArea(property_id=prop.id, name=flaeche, archived=flaeche.endswith("(alt)"))
        db.add(area)
        db.flush()
        areas[flaeche] = area.id
    return prop, areas


def _welt(db) -> dict:
    """Gewerbekunde (VOB/B), Projekt mit Objekt "Halle" (Nord, Süd, Anbau (alt)), ein fremdes Objekt mit "Fremd",
    Auftrag; Beteiligte: Architektin ohne Vollmacht, Hausverwaltung mit Vollmacht samt Beleg, dazu ein Beteiligter
    eines anderen Projekts."""
    quote = make_quote(db, is_consumer=False, number="0349")
    order = beauftragen(db, quote)
    project = db.get(Project, order.project_id)
    prop, areas = _objekt(db, project.customer_id, "Halle", ["Nord", "Süd", "Anbau (alt)"])
    project.property_id = prop.id
    fremd, fremd_areas = _objekt(db, project.customer_id, "Nachbarhaus", ["Fremd"])
    db.commit()
    architektin = add_participant(db, project, create_contact(db, {"kind": "person", "first_name": "Petra",
                                                                    "last_name": "Plan"}), role="architekt_planer")
    verwaltung = add_participant(db, project, create_contact(db, {"kind": "firma", "company_name": "HV Muster"}),
                                 role="hausverwaltung", authorized_recipient=True)
    store_power_of_attorney(db, verwaltung, filename="vollmacht.pdf", data=PDF + b"vollmacht", user_name="Büro")
    other_quote = make_quote(db, is_consumer=False, number="0350")
    other_order = beauftragen(db, other_quote)
    fremd_beteiligt = add_participant(db, db.get(Project, other_order.project_id),
                                      create_contact(db, {"kind": "person", "last_name": "Fremd"}), role="sonstiges")
    return {"order_id": order.id, "project_id": project.id, "property_id": prop.id, "areas": areas,
            "fremd_property_id": fremd.id, "fremd_area": fremd_areas["Fremd"], "architektin": architektin.id,
            "verwaltung": verwaltung.id, "fremd_beteiligt": fremd_beteiligt.id, "other_order_id": other_order.id}


@pytest.fixture
def welt(threaded_db_session):
    return {"db": threaded_db_session, **_welt(threaded_db_session)}


def _client(welt, router_test_client, role="buero_auftrag"):
    return router_test_client(welt["db"], acceptances_router.router, orders_router.router, roof_areas_router.router,
                              participants_router.router, role=role)


@pytest.fixture
def buero(welt, router_test_client):
    return _client(welt, router_test_client)


GUELTIG = {"kind": "foermlich", "accepted_on": "2026-09-15", "scope": "gesamt", "result": "abgenommen",
           "reservation_defects": False, "reservation_penalty": False, "declared_by": "auftraggeber"}


def _erfassen(client, order_id, files=(("beleg.pdf", PDF, "application/pdf"),), **werte):
    data = {**GUELTIG, **werte}
    data = {k: v for k, v in data.items() if v is not ...}
    return client.post(f"/api/orders/{order_id}/acceptances", data={"data": json.dumps(data)},
                       files=[("files", f) for f in files])


def _anzahl(db, model=OrderAcceptance):
    db.expire_all()
    return len(db.scalars(select(model)).all())


# ---------------------------------------------------------------------------
# Punkt 5: Fristende nach § 187 Abs. 1, § 188 Abs. 2 und 3 BGB
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("abnahme,monate,tage,ende", [
    (date(2026, 3, 15), 60, 0, date(2031, 3, 15)),   # § 188 Abs. 2: Tag mit derselben Zahl
    (date(2024, 2, 29), 60, 0, date(2029, 2, 28)),   # § 188 Abs. 3: den 29.02.2029 gibt es nicht -> Monatsletzter
    (date(2024, 2, 29), 48, 0, date(2028, 2, 29)),   # Schaltjahr: den 29.02.2028 gibt es
    (date(2024, 2, 29), 12, 0, date(2025, 2, 28)),
    (date(2026, 8, 31), 24, 0, date(2028, 8, 31)),
    (date(2026, 8, 31), 1, 0, date(2026, 9, 30)),    # September hat keinen 31.
    (date(2025, 8, 31), 18, 0, date(2027, 2, 28)),
    (date(2026, 8, 31), 18, 0, date(2028, 2, 29)),   # 2028 ist Schaltjahr
    (date(2026, 1, 30), 1, 2, date(2026, 3, 2)),     # Monate zuerst (28.02.), dann Tage (Festlegung)
    (date(2026, 3, 15), 0, 10, date(2026, 3, 25)),   # § 187 Abs. 1: der Abnahmetag zählt nicht mit
    (date(2026, 12, 31), 0, 1, date(2027, 1, 1)),
])
def test_warranty_end_follows_bgb_188(abnahme, monate, tage, ende):
    assert warranty_end(abnahme, monate, tage) == ende


def test_duration_text_and_proposals_per_basis():
    assert duration_text(60, 0) == "60 Monate (5 Jahre)"
    assert duration_text(1, 0) == "1 Monat"
    assert duration_text(24, 10) == "24 Monate und 10 Tage"
    assert duration_text(0, 1) == "1 Tag"
    assert duration_text(None, None) == "nicht festgelegt"
    erwartet = {("vob_b", "bauwerk"): 48, ("vob_b", "sonstige"): 24, ("bgb", "bauwerk"): 60, ("bgb", "sonstige"): 24,
                ("bgb_vob_c_4_5", "bauwerk"): 60, ("bgb_vob_c_4_5", "sonstige"): 24}
    assert {k: v[0] for k, v in PROPOSALS.items()} == erwartet
    assert all(v[1] == 0 for v in PROPOSALS.values())
    assert "§ 13 Abs. 4 Nr. 1 VOB/B" in warranty_proposal("vob_b", "bauwerk")["citation"]
    assert "§ 634a Abs. 1 Nr. 2 BGB" in warranty_proposal("bgb", "bauwerk")["citation"]
    assert "§ 634a Abs. 1 Nr. 1 BGB" in warranty_proposal("bgb_vob_c_4_5", "sonstige")["citation"]
    assert warranty_proposal("vob_b", None) is None


# ---------------------------------------------------------------------------
# Punkt 3: Leistungsart und Gewährleistungsdauer
# ---------------------------------------------------------------------------

def test_new_order_has_no_warranty_until_set_consciously(welt, buero):
    order = buero.get(f"/api/orders/{welt['order_id']}").json()
    assert order["contract_basis"] == "vob_b"
    assert order["work_kind"] is None and order["warranty_months"] is None and order["warranty_set"] is False
    assert order["warranty_text"] == "nicht festgelegt"
    assert order["warranty_proposals"]["bauwerk"]["months"] == 48
    assert order["warranty_proposals"]["sonstige"]["months"] == 24
    assert "VOB/B" in order["warranty_proposals"]["bauwerk"]["citation"]


def test_adopting_the_proposal_needs_no_reason_and_is_recorded(welt, buero):
    r = buero.put(f"/api/orders/{welt['order_id']}/warranty",
                  json={"work_kind": "bauwerk", "warranty_months": 48, "warranty_days": 0, "reason": None})
    assert r.status_code == 200, r.text
    assert r.json()["warranty_text"] == "48 Monate (4 Jahre)" and r.json()["warranty_follows_proposal"] is True
    assert r.json()["work_kind_label"] == "Bauwerk"
    history = buero.get(f"/api/orders/{welt['order_id']}/warranty-changes").json()
    assert len(history) == 1 and history[0]["follows_proposal"] is True and history[0]["contract_basis"] == "vob_b"
    assert history[0]["proposal_text"] == "48 Monate (4 Jahre)" and history[0]["reason"] is None


def test_deviation_needs_a_reason(welt, buero):
    url = f"/api/orders/{welt['order_id']}/warranty"
    r = buero.put(url, json={"work_kind": "bauwerk", "warranty_months": 60, "warranty_days": 0, "reason": "  "})
    assert r.status_code == 422 and "Begründung" in r.json()["detail"]
    assert buero.get(f"/api/orders/{welt['order_id']}").json()["warranty_set"] is False
    r = buero.put(url, json={"work_kind": "bauwerk", "warranty_months": 60, "warranty_days": 0,
                             "reason": "5 Jahre im Vertrag vereinbart (§ 4 Abs. 2)"})
    assert r.status_code == 200 and r.json()["warranty_follows_proposal"] is False
    history = buero.get(f"/api/orders/{welt['order_id']}/warranty-changes").json()
    assert history[0]["reason"] == "5 Jahre im Vertrag vereinbart (§ 4 Abs. 2)"
    assert history[0]["follows_proposal"] is False


@pytest.mark.parametrize("payload,teil", [
    ({"work_kind": "dach", "warranty_months": 48, "warranty_days": 0, "reason": None}, "Leistungsart"),
    ({"work_kind": "bauwerk", "warranty_months": 0, "warranty_days": 0, "reason": "x"}, "0 Monaten"),
])
def test_invalid_warranty_is_rejected(welt, buero, payload, teil):
    r = buero.put(f"/api/orders/{welt['order_id']}/warranty", json=payload)
    assert r.status_code == 422 and teil in r.json()["detail"]


def test_warranty_fields_are_required_and_same_setting_twice_is_rejected(welt, buero):
    url = f"/api/orders/{welt['order_id']}/warranty"
    assert buero.put(url, json={"work_kind": "bauwerk", "warranty_months": 48, "warranty_days": 0}).status_code == 422
    ok = {"work_kind": "sonstige", "warranty_months": 24, "warranty_days": 0, "reason": None}
    assert buero.put(url, json=ok).status_code == 200
    r = buero.put(url, json=ok)
    assert r.status_code == 422 and "bereits so festgelegt" in r.json()["detail"]


def test_changed_contract_basis_keeps_duration_and_shows_deviation(welt, buero):
    db = welt["db"]
    buero.put(f"/api/orders/{welt['order_id']}/warranty",
              json={"work_kind": "bauwerk", "warranty_months": 48, "warranty_days": 0, "reason": None})
    change_order_contract_basis(db, db.get(Order, welt["order_id"]), contract_basis="bgb", reason="BGB vereinbart")
    order = buero.get(f"/api/orders/{welt['order_id']}").json()
    assert order["warranty_months"] == 48 and order["warranty_follows_proposal"] is False
    assert order["warranty_proposals"]["bauwerk"]["months"] == 60


# ---------------------------------------------------------------------------
# Punkt 4: Abnahme erfassen
# ---------------------------------------------------------------------------

def test_formal_acceptance_with_receipt_is_stored_with_checksum(welt, buero, ablage):
    r = _erfassen(buero, welt["order_id"], roof_area_ids=[welt["areas"]["Nord"]],
                  contractor_objections="Restarbeiten Attika sind keine Mängel.")
    assert r.status_code == 200, r.text
    a = r.json()
    assert a["kind_label"] == "förmlich" and a["scope_label"] == "Gesamtabnahme" and a["accepted_on"] == "2026-09-15"
    assert a["result_text"] == "abgenommen ohne Vorbehalte"
    assert a["roof_areas"] == [{"id": welt["areas"]["Nord"], "name": "Nord"}]
    assert a["declared_by_label"] == "Auftraggeber" and a["declared_by_name"] == "Kunde 0349"
    assert a["contractor_objections"] == "Restarbeiten Attika sind keine Mängel."
    assert a["property_id"] == welt["property_id"]
    assert a["content_ok"] is True and a["intact"] is True
    [beleg] = a["files"]
    assert beleg["kind"] == "nachweis" and beleg["sha256"] == hashlib.sha256(PDF).hexdigest()
    assert beleg["status"] == "unveraendert"
    datei = buero.get(f"/api/order-acceptances/{a['id']}/files/{beleg['id']}")
    assert datei.status_code == 200 and datei.content == PDF
    assert datei.headers["content-type"] == "application/pdf" and datei.headers["x-content-type-options"] == "nosniff"
    gespeichert = next(ablage.rglob("*.pdf"))
    assert gespeichert.read_bytes() == PDF and not os.access(gespeichert, os.W_OK)  # schreibgeschützt


@pytest.mark.parametrize("maengel,strafe,text_", [
    (True, False, "abgenommen mit Vorbehalten (Mängel)"),
    (False, True, "abgenommen mit Vorbehalten (Vertragsstrafe)"),
    (True, True, "abgenommen mit Vorbehalten (Mängel, Vertragsstrafe)"),
])
def test_with_reservations_is_only_derived(welt, buero, maengel, strafe, text_):
    a = _erfassen(buero, welt["order_id"], reservation_defects=maengel, reservation_penalty=strafe).json()
    assert a["result_text"] == text_
    assert set(OrderAcceptance.__table__.c.keys()).isdisjoint({"with_reservations", "result_text"})


@pytest.mark.parametrize("werte,status,teil", [
    ({"reservation_defects": ...}, 400, "Mängel"),
    ({"reservation_penalty": ...}, 400, "Vertragsstrafe"),
    ({"reservation_defects": "false"}, 422, None),          # kein Wahrheitswert -- keine stille Umdeutung
    ({"accepted_on": ...}, 422, None),                       # Datum Pflicht, ohne Vorgabe
    ({"kind": ...}, 422, None),
    ({"scope": "teil"}, 400, "Teil"),
    ({"scope_description": "Nordseite"}, 400, "nur zur Teilabnahme"),
    ({"result": "verweigert"}, 400, "keine Vorbehalte"),
    ({"declared_by": "beteiligter"}, 400, "Beteiligten"),
    ({"participant_id": 1}, 400, "Beteiligter gehört nur"),
    ({"conduct_reason": "Ingebrauchnahme"}, 400, "nur zur schlüssigen"),
    ({"unbekannt": 1}, 422, None),
])
def test_invalid_input_is_rejected_and_nothing_is_stored(welt, buero, ablage, werte, status, teil):
    r = _erfassen(buero, welt["order_id"], **werte)
    assert r.status_code == status, r.text
    if teil:
        assert teil in r.json()["detail"]
    assert _anzahl(welt["db"]) == 0 and not list(ablage.rglob("*.*"))


def test_future_date_is_rejected(welt, buero):
    r = _erfassen(buero, welt["order_id"], accepted_on=(berlin_today() + timedelta(days=1)).isoformat())
    assert r.status_code == 400 and "Zukunft" in r.json()["detail"]
    assert _erfassen(buero, welt["order_id"], accepted_on=berlin_today().isoformat()).status_code == 200


def test_receipt_required_except_for_conduct_which_needs_a_reason(welt, buero):
    r = _erfassen(buero, welt["order_id"], files=())
    assert r.status_code == 400 and "Beleg" in r.json()["detail"]
    r = _erfassen(buero, welt["order_id"], files=(), kind="schluessig")
    assert r.status_code == 400 and "schlüssigen Abnahme" in r.json()["detail"]
    r = _erfassen(buero, welt["order_id"], files=(), kind="schluessig",
                  conduct_reason="Halle seit 01.09. ohne Rüge in Gebrauch, Schlussrechnung vorbehaltlos bezahlt.")
    assert r.status_code == 200 and r.json()["files"] == [] and r.json()["kind_label"] == "schlüssig"
    foto = _erfassen(buero, welt["order_id"], files=(("foto.png", _png(), "image/png"),), kind="ausdruecklich")
    assert foto.status_code == 200 and foto.json()["files"][0]["content_type"] == "image/png"


@pytest.mark.parametrize("name,inhalt,art", [
    ("bild.svg", SVG, "image/svg+xml"), ("beleg.pdf", HTML_ALS_PDF, "application/pdf"), ("leer.pdf", b"", "application/pdf"),
])
def test_only_pdf_or_photo_is_accepted_as_receipt(welt, buero, ablage, name, inhalt, art):
    r = _erfassen(buero, welt["order_id"], files=((name, inhalt, art),))
    assert r.status_code == 400
    assert _anzahl(welt["db"]) == 0 and not list(ablage.rglob("*.*"))


def test_receipt_limits(welt, buero, monkeypatch):
    monkeypatch.setattr(acceptances_module, "MAX_FILE_BYTES", len(PDF) + 5)
    r = _erfassen(buero, welt["order_id"], files=(("gross.pdf", PDF + b"x" * 10, "application/pdf"),))
    assert r.status_code == 400 and "größer" in r.json()["detail"]
    sechs = tuple((f"b{i}.pdf", PDF + bytes([i]), "application/pdf") for i in range(6))
    assert _erfassen(buero, welt["order_id"], files=sechs).status_code == 400
    doppelt = (("a.pdf", PDF, "application/pdf"), ("b.pdf", PDF, "application/pdf"))
    r = _erfassen(buero, welt["order_id"], files=doppelt)
    assert r.status_code == 400 and "mehrfach" in r.json()["detail"]


def test_partial_acceptance_needs_description(welt, buero):
    a = _erfassen(buero, welt["order_id"], scope="teil", scope_description="Dachfläche Nord mit Attika",
                  roof_area_ids=[welt["areas"]["Nord"], welt["areas"]["Nord"]]).json()
    assert a["scope_label"] == "Teilabnahme" and a["scope_description"] == "Dachfläche Nord mit Attika"
    assert a["roof_areas"] == [{"id": welt["areas"]["Nord"], "name": "Nord"}]  # doppelt gewählt, einmal gespeichert


def test_attack_roof_area_of_a_foreign_property_is_rejected(welt, buero, ablage):
    """Angriff: die ID einer Dachfläche eines anderen Objekts mitschicken -- abgelehnt, nichts gespeichert."""
    r = _erfassen(buero, welt["order_id"], roof_area_ids=[welt["areas"]["Süd"], welt["fremd_area"]])
    assert r.status_code == 400 and "gehört nicht zum Objekt des Projekts" in r.json()["detail"]
    assert _anzahl(welt["db"]) == 0 and _anzahl(welt["db"], OrderAcceptanceRoofArea) == 0
    assert not list(ablage.rglob("*.*"))
    assert _erfassen(buero, welt["order_id"], roof_area_ids=[999999]).status_code == 400


def test_archived_roof_area_and_project_without_property(welt, buero):
    r = _erfassen(buero, welt["order_id"], roof_area_ids=[welt["areas"]["Anbau (alt)"]])
    assert r.status_code == 400 and "archiviert" in r.json()["detail"]
    db = welt["db"]
    db.get(Project, welt["project_id"]).property_id = None
    db.commit()
    r = _erfassen(buero, welt["order_id"], roof_area_ids=[welt["areas"]["Nord"]])
    assert r.status_code == 400
    a = _erfassen(buero, welt["order_id"]).json()
    assert a["property_id"] is None and a["roof_areas"] == []


def test_options_offer_only_the_projects_roof_areas_and_participants(welt, buero):
    o = buero.get(f"/api/orders/{welt['order_id']}/acceptance-options").json()
    assert o["property"]["name"] == "Halle" and [r["name"] for r in o["roof_areas"]] == ["Nord", "Süd"]
    assert o["client_name"] == "Kunde 0349"
    by_id = {p["participant_id"]: p for p in o["participants"]}
    assert set(by_id) == {welt["architektin"], welt["verwaltung"]}
    assert by_id[welt["architektin"]]["poa_on_record"] is False
    assert by_id[welt["verwaltung"]]["poa_on_record"] is True


def test_participant_without_power_of_attorney_is_saved_with_warning(welt, buero):
    a = _erfassen(buero, welt["order_id"], declared_by="beteiligter", participant_id=welt["architektin"]).json()
    assert a["declared_by_name"] == "Petra Plan" and a["declared_by_role"] == "Architekt/Planer"
    assert a["poa_on_record"] is False and a["without_power_of_attorney"] is True
    assert [f["kind"] for f in a["files"]] == ["nachweis"]


def test_participant_with_power_of_attorney_freezes_a_copy(welt, buero):
    db = welt["db"]
    a = _erfassen(buero, welt["order_id"], declared_by="beteiligter", participant_id=welt["verwaltung"]).json()
    assert a["poa_on_record"] is True and a["without_power_of_attorney"] is False
    vollmacht = next(f for f in a["files"] if f["kind"] == "vollmacht")
    assert vollmacht["sha256"] == hashlib.sha256(PDF + b"vollmacht").hexdigest()
    # Der Beteiligte ersetzt seine Vollmacht später -- die Abnahme behält die von damals.
    store_power_of_attorney(db, db.get(participants_module.ProjectParticipant, welt["verwaltung"]),
                            filename="neu.pdf", data=PDF + b"neu", user_name="Büro")
    datei = buero.get(f"/api/order-acceptances/{a['id']}/files/{vollmacht['id']}")
    assert datei.status_code == 200 and datei.content == PDF + b"vollmacht"


def test_participant_of_another_project_is_rejected(welt, buero):
    r = _erfassen(buero, welt["order_id"], declared_by="beteiligter", participant_id=welt["fremd_beteiligt"])
    assert r.status_code == 400 and "Beteiligten dieses Projekts" in r.json()["detail"]
    assert _anzahl(welt["db"]) == 0


def test_refused_acceptance_has_no_reservations_and_no_warranty(welt, buero):
    buero.put(f"/api/orders/{welt['order_id']}/warranty",
              json={"work_kind": "bauwerk", "warranty_months": 48, "warranty_days": 0, "reason": None})
    a = _erfassen(buero, welt["order_id"], result="verweigert", reservation_defects=..., reservation_penalty=...,
                  contractor_objections="Verweigerung unberechtigt, Mängel bestritten.").json()
    assert a["result_text"] == "verweigert" and a["reservation_defects"] is None and a["warranty"] is None


# ---------------------------------------------------------------------------
# Angriff: Ändern nach dem Speichern
# ---------------------------------------------------------------------------

def test_attack_no_route_changes_or_deletes_an_acceptance(welt, buero):
    a = _erfassen(buero, welt["order_id"]).json()
    for method in ("put", "patch", "delete"):
        assert getattr(buero, method)(f"/api/order-acceptances/{a['id']}").status_code in (404, 405)
        assert buero.request(method.upper(), f"/api/order-acceptances/{a['id']}/files/{a['files'][0]['id']}").status_code == 405
    assert buero.post(f"/api/orders/{welt['order_id']}/acceptances/{a['id']}").status_code in (404, 405)


def test_attack_orm_changes_and_deletes_are_refused(welt, buero):
    db = welt["db"]
    a = _erfassen(buero, welt["order_id"], roof_area_ids=[welt["areas"]["Nord"]]).json()
    for change in (
        lambda x: setattr(x, "accepted_on", date(2026, 1, 1)),
        lambda x: setattr(x, "result", "verweigert"),
        lambda x: setattr(x, "discard_reason", "über das ORM"),
        lambda x: setattr(x.files[0], "sha256", "0" * 64),
        lambda x: setattr(x.roof_areas[0], "roof_area_name", "Süd"),
    ):
        row = db.get(OrderAcceptance, a["id"])
        change(row)
        with pytest.raises(ArchiveImmutableError):
            db.commit()
        db.rollback()
    for target in (lambda x: x, lambda x: x.files[0], lambda x: x.roof_areas[0]):
        db.delete(target(db.get(OrderAcceptance, a["id"])))
        with pytest.raises(ArchiveImmutableError):
            db.commit()
        db.rollback()
    assert buero.get(f"/api/orders/{welt['order_id']}/acceptances").json()[0]["intact"] is True


def test_attack_change_past_the_orm_is_detected(welt, buero, ablage):
    db = welt["db"]
    a = _erfassen(buero, welt["order_id"]).json()
    db.execute(update(OrderAcceptance).where(OrderAcceptance.id == a["id"]).values(reservation_penalty=True)
               .execution_options(synchronize_session=False))
    db.commit()
    stand = buero.get(f"/api/orders/{welt['order_id']}/acceptances").json()[0]
    assert stand["content_ok"] is False and stand["intact"] is False
    # Datei in der Ablage verändert bzw. entfernt: nicht ausgeliefert, als abweichend gemeldet.
    pfad = next(ablage.rglob("*.pdf"))
    os.chmod(pfad, stat.S_IWRITE | stat.S_IREAD)
    pfad.write_bytes(PDF + b"manipuliert")
    beleg = buero.get(f"/api/orders/{welt['order_id']}/acceptances").json()[0]["files"][0]
    assert beleg["status"] == "abweichend"
    assert buero.get(f"/api/order-acceptances/{a['id']}/files/{beleg['id']}").status_code == 409
    pfad.unlink()
    assert buero.get(f"/api/order-acceptances/{a['id']}/files/{beleg['id']}").status_code == 410


def test_file_of_another_acceptance_is_not_delivered(welt, buero):
    a = _erfassen(buero, welt["order_id"]).json()
    b = _erfassen(buero, welt["order_id"], files=(("foto.png", _png(), "image/png"),)).json()
    assert buero.get(f"/api/order-acceptances/{a['id']}/files/{b['files'][0]['id']}").status_code == 404


# ---------------------------------------------------------------------------
# Verwerfen und Historie
# ---------------------------------------------------------------------------

def test_discard_with_reason_once_and_history(welt, buero):
    db = welt["db"]
    a = _erfassen(buero, welt["order_id"]).json()
    url = f"/api/order-acceptances/{a['id']}/discard"
    assert buero.post(url, json={"reason": ""}).status_code == 422
    assert buero.post(url, json={"reason": "   "}).status_code == 400
    r = buero.post(url, json={"reason": "Falsches Datum erfasst (richtig: 16.09.)"})
    assert r.status_code == 200
    v = r.json()
    assert v["discarded"] is True and v["discard_reason"] == "Falsches Datum erfasst (richtig: 16.09.)"
    assert v["discarded_by_name"] == "Buero_auftrag" and v["content_ok"] is True and v["warranty"] is None
    assert v["accepted_on"] == a["accepted_on"] and v["files"] == a["files"]  # sonst nichts geändert
    r = buero.post(url, json={"reason": "noch einmal"})
    assert r.status_code == 409
    assert db.get(OrderAcceptance, a["id"]).discard_reason == "Falsches Datum erfasst (richtig: 16.09.)"
    eintraege = db.scalars(select(AuditLog).where(AuditLog.entity_type == "Abnahme")
                           .order_by(AuditLog.id)).all()
    assert [e.action for e in eintraege] == ["angelegt", "verworfen"]
    assert all(e.project_id == welt["project_id"] for e in eintraege)
    assert eintraege[1].new_value == "Falsches Datum erfasst (richtig: 16.09.)"
    assert json.loads(eintraege[0].details)["kind"] == "foermlich"
    # Korrektur: neuer Eintrag; beide stehen in der Liste, der verworfene gekennzeichnet.
    _erfassen(buero, welt["order_id"], accepted_on="2026-09-16")
    liste = buero.get(f"/api/orders/{welt['order_id']}/acceptances").json()
    assert [(x["accepted_on"], x["discarded"]) for x in liste] == [("2026-09-16", False), ("2026-09-15", True)]


def test_named_roof_area_and_declaring_participant_cannot_be_removed(welt, buero):
    _erfassen(buero, welt["order_id"], roof_area_ids=[welt["areas"]["Süd"]], declared_by="beteiligter",
              participant_id=welt["architektin"])
    r = buero.delete(f"/api/roof-areas/{welt['areas']['Süd']}")
    assert r.status_code == 400 and "Abnahme" in r.json()["detail"]
    r = buero.delete(f"/api/project-participants/{welt['architektin']}")
    assert r.status_code == 409 and "Abnahme" in r.json()["detail"]
    assert buero.delete(f"/api/project-participants/{welt['verwaltung']}").status_code == 200  # Gegenprobe


# ---------------------------------------------------------------------------
# Angriff: Monteur liest Abnahmen
# ---------------------------------------------------------------------------

def test_attack_field_worker_sees_nothing(welt, buero, router_test_client):
    a = _erfassen(buero, welt["order_id"], roof_area_ids=[welt["areas"]["Nord"]]).json()
    monteur = _client(welt, router_test_client, role="field")
    for url in (f"/api/orders/{welt['order_id']}/acceptances", f"/api/orders/{welt['order_id']}/acceptance-options",
                f"/api/order-acceptances/{a['id']}/files/{a['files'][0]['id']}",
                f"/api/orders/{welt['order_id']}/warranty-changes",
                f"/api/properties/{welt['property_id']}/acceptance-warranties",
                f"/api/roof-areas/{welt['areas']['Nord']}/acceptance-warranties"):
        assert monteur.get(url).status_code == 403, url
    assert _erfassen(monteur, welt["order_id"]).status_code == 403
    assert monteur.post(f"/api/order-acceptances/{a['id']}/discard", json={"reason": "x"}).status_code == 403
    assert monteur.put(f"/api/orders/{welt['order_id']}/warranty", json={
        "work_kind": "bauwerk", "warranty_months": 48, "warranty_days": 0, "reason": None}).status_code == 403
    assert _anzahl(welt["db"]) == 1 and welt["db"].get(OrderAcceptance, a["id"]).discarded_at is None


# ---------------------------------------------------------------------------
# Punkt 5: Gewährleistungsende an Auftrag, Objekt und Dachfläche
# ---------------------------------------------------------------------------

def _dauer(buero, welt, monate, grund=None):
    r = buero.put(f"/api/orders/{welt['order_id']}/warranty",
                  json={"work_kind": "bauwerk", "warranty_months": monate, "warranty_days": 0, "reason": grund})
    assert r.status_code == 200, r.text


def test_warranty_end_at_order_property_and_roof_area(welt, buero):
    teil = _erfassen(buero, welt["order_id"], accepted_on="2024-02-29", scope="teil", scope_description="Nord",
                     roof_area_ids=[welt["areas"]["Nord"]]).json()
    assert teil["warranty"]["end"] is None and "nicht festgelegt" in teil["warranty"]["text"]
    _dauer(buero, welt, 48)
    gesamt = _erfassen(buero, welt["order_id"], accepted_on="2025-08-31").json()
    verweigert = _erfassen(buero, welt["order_id"], accepted_on="2024-01-10", result="verweigert",
                           reservation_defects=..., reservation_penalty=..., roof_area_ids=[welt["areas"]["Süd"]]).json()
    liste = {x["id"]: x for x in buero.get(f"/api/orders/{welt['order_id']}/acceptances").json()}
    assert liste[teil["id"]]["warranty"]["end"] == "2028-02-29"   # 48 Monate ab 29.02.2024
    assert liste[gesamt["id"]]["warranty"]["end"] == "2029-08-31"
    assert liste[verweigert["id"]]["warranty"] is None
    _dauer(buero, welt, 60, grund="5 Jahre vereinbart")
    liste = {x["id"]: x for x in buero.get(f"/api/orders/{welt['order_id']}/acceptances").json()}
    assert liste[teil["id"]]["warranty"]["end"] == "2029-02-28"   # § 188 Abs. 3
    assert liste[teil["id"]]["warranty"]["text"] == "Gewährleistung bis 28.02.2029 (60 Monate (5 Jahre) ab Abnahme)"

    objekt = buero.get(f"/api/properties/{welt['property_id']}/acceptance-warranties").json()
    assert {x["id"] for x in objekt["acceptances"]} == {teil["id"], gesamt["id"]}  # nicht die verweigerte
    assert objekt["roof_areas"] == {str(welt["areas"]["Nord"]): {"end": "2029-02-28", "order_number": teil["order_number"]}}
    nord = buero.get(f"/api/roof-areas/{welt['areas']['Nord']}/acceptance-warranties").json()
    assert [x["id"] for x in nord["acceptances"]] == [teil["id"]] and nord["property_without_roof_areas"] == 1
    sued = buero.get(f"/api/roof-areas/{welt['areas']['Süd']}/acceptance-warranties").json()
    assert sued["acceptances"] == [] and sued["property_without_roof_areas"] == 1
    assert buero.get(f"/api/properties/{welt['fremd_property_id']}/acceptance-warranties").json()["acceptances"] == []

    buero.post(f"/api/order-acceptances/{teil['id']}/discard", json={"reason": "Doppelt erfasst"})
    nord = buero.get(f"/api/roof-areas/{welt['areas']['Nord']}/acceptance-warranties").json()
    assert nord["acceptances"] == []
    assert buero.get(f"/api/properties/{welt['property_id']}/acceptance-warranties").json()["roof_areas"] == {}


def test_acceptance_keeps_its_property_when_the_project_moves(welt, buero):
    a = _erfassen(buero, welt["order_id"], roof_area_ids=[welt["areas"]["Nord"]]).json()
    db = welt["db"]
    db.get(Project, welt["project_id"]).property_id = welt["fremd_property_id"]
    db.commit()
    assert [x["id"] for x in buero.get(f"/api/properties/{welt['property_id']}/acceptance-warranties").json()
            ["acceptances"]] == [a["id"]]
    assert buero.get(f"/api/properties/{welt['fremd_property_id']}/acceptance-warranties").json()["acceptances"] == []


# ---------------------------------------------------------------------------
# Punkt 7: Abgleich mit dem Angebot gesperrt
# ---------------------------------------------------------------------------

def _angebot_aendern(db, order_id):
    from app.models import QuoteItem
    order = db.get(Order, order_id)
    item = db.scalars(select(QuoteItem).where(QuoteItem.quote_id == order.source_quote_id)).first()
    item.quantity = item.quantity + 5
    db.commit()


@pytest.mark.parametrize("ergebnis", ["abgenommen", "verweigert"])
def test_sync_is_locked_while_an_acceptance_exists(welt, buero, ergebnis):
    db = welt["db"]
    _angebot_aendern(db, welt["order_id"])
    werte = {} if ergebnis == "abgenommen" else {"result": "verweigert", "reservation_defects": ...,
                                                 "reservation_penalty": ...}
    a = _erfassen(buero, welt["order_id"], **werte).json()
    order = buero.get(f"/api/orders/{welt['order_id']}").json()
    assert order["has_active_acceptance"] is True and order["source_quote_in_sync"] is False
    r = buero.post(f"/api/orders/{welt['order_id']}/sync-source-quote", json={"reason": None})
    assert r.status_code == 409 and "Abnahme" in r.json()["detail"]
    assert buero.get(f"/api/orders/{welt['order_id']}").json()["source_quote_in_sync"] is False
    buero.post(f"/api/order-acceptances/{a['id']}/discard", json={"reason": "falsch erfasst"})
    assert buero.get(f"/api/orders/{welt['order_id']}").json()["has_active_acceptance"] is False
    r = buero.post(f"/api/orders/{welt['order_id']}/sync-source-quote", json={"reason": None})
    assert r.status_code == 200 and r.json()["source_quote_in_sync"] is True


def test_sync_lock_in_business_function(welt, buero):
    db = welt["db"]
    _angebot_aendern(db, welt["order_id"])
    _erfassen(buero, welt["order_id"])
    with pytest.raises(AcceptanceExistsError):
        sync_order_from_source_quote(db, load_order(db, welt["order_id"]))
    db.rollback()
    assert order_to_dict(load_order(db, welt["order_id"]), db)["source_quote_in_sync"] is False


# ---------------------------------------------------------------------------
# Oberfläche: Karten an Auftrag, Objekt und Dachfläche
# ---------------------------------------------------------------------------

def test_pages_carry_the_cards(welt, router_test_client):
    from app.routers import pages
    client = router_test_client(welt["db"], pages.router, role="buero_auftrag")
    order_html = client.get(f"/orders/{welt['order_id']}").text
    assert 'id="warrantyCard"' in order_html and 'id="acceptanceCard"' in order_html
    assert 'id="acceptanceDialog"' in order_html and "function loadAcceptanceSection(" in order_html
    assert "prompt(" not in order_html.split('id="warrantyCard"')[1]  # Regel 4
    assert "acceptance-warranties" in client.get(f"/properties/{welt['property_id']}").text
    assert "acceptance-warranties" in client.get(f"/roof-areas/{welt['areas']['Nord']}").text


def test_dialog_has_no_preselected_choices():
    """Datum und die beiden Pflichtfragen ohne Vorgabe -- auch Art, Umfang, Ergebnis und Erklärende."""
    source = (ROOT / "app" / "templates" / "_abnahme.html").read_text(encoding="utf-8")
    dialog = source.split('id="acceptanceDialog"')[1].split("</dialog>")[0]
    assert " checked" not in dialog and 'type="date"' in dialog and "value=\"20" not in dialog
    for name in ("accKind", "accScope", "accResult", "accDefects", "accPenalty", "accDeclarer"):
        assert f'name="{name}"' in dialog, name


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------

def _migration():
    path = next(ROOT.glob("alembic/versions/*_abnahme_und_gewaehrleistung.py"))
    spec = importlib.util.spec_from_file_location("migration_1846_abnahme", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(engine, fn_name):
    module = _migration()
    with engine.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            getattr(module, fn_name)()


def _guarantee(engine, column):
    with engine.begin() as conn:
        return conn.execute(text(f"SELECT {column} FROM roof_areas WHERE name = 'Probe'")).scalar()


def test_migration_down_refuses_while_data_exists_and_up_restores():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with engine.begin() as conn:  # Punkt 6: der Wert überlebt die Umbenennung in beide Richtungen
        conn.execute(text("INSERT INTO customers (name, last_name, created_at) VALUES ('K', 'K', '2026-10-03')"))
        conn.execute(text("INSERT INTO properties (customer_id, name, created_at) "
                          "SELECT id, 'Halle', '2026-10-03' FROM customers"))
        conn.execute(text("INSERT INTO roof_areas (property_id, name, third_party_guarantee_until, archived, created_at, "
                          "updated_at) SELECT id, 'Probe', '2031-05-01', false, '2026-10-03', '2026-10-03' FROM properties"))
    _run(engine, "downgrade")
    assert str(_guarantee(engine, "warranty_until")) == "2031-05-01"
    names = set(inspect(engine).get_table_names())
    assert not names & {"order_acceptances", "order_acceptance_files", "order_acceptance_roof_areas",
                        "order_warranty_changes"}
    assert not {"work_kind", "warranty_months", "warranty_days"} & {c["name"] for c in inspect(engine).get_columns("orders")}
    _run(engine, "upgrade")
    assert {"order_acceptances", "order_warranty_changes"} <= set(inspect(engine).get_table_names())
    assert str(_guarantee(engine, "third_party_guarantee_until")) == "2031-05-01"
    assert "warranty_until" not in {c["name"] for c in inspect(engine).get_columns("roof_areas")}
    with engine.begin() as conn:
        conn.execute(text("UPDATE orders SET work_kind = 'bauwerk'"))  # keine Zeile: kein Abbruch
        conn.execute(text("INSERT INTO order_warranty_changes (order_id, work_kind, warranty_months, warranty_days, "
                          "contract_basis, proposal_months, proposal_days, follows_proposal, changed_by_name, "
                          "changed_at) VALUES (1, 'bauwerk', 48, 0, 'vob_b', 48, 0, true, 'X', '2026-10-03 00:00:00')"))
    with pytest.raises(RuntimeError, match="1 Festlegungen der Gewährleistung"):
        _run(engine, "downgrade")
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM order_warranty_changes"))
        conn.execute(text("INSERT INTO order_acceptances (order_id, kind, accepted_on, scope, result, declared_by, "
                          "declared_by_name, content_sha256, created_at, created_by_name) VALUES (1, 'foermlich', "
                          "'2026-09-15', 'gesamt', 'verweigert', 'auftraggeber', 'K', 'x', '2026-10-03 00:00:00', 'X')"))
    with pytest.raises(RuntimeError, match="1 Abnahmen"):
        _run(engine, "downgrade")


# ---------------------------------------------------------------------------
# PostgreSQL: Erfassen und Abgleich warten aufeinander (Sperre der Auftragszeile)
# ---------------------------------------------------------------------------

@pytest.fixture
def pg():
    if not PG_TEST_DATABASE_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    schema = f"pgtest_abnahme_{uuid.uuid4().hex[:8]}"
    admin = create_engine(PG_TEST_DATABASE_URL)
    with admin.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
    engine = create_engine(PG_TEST_DATABASE_URL, pool_size=5,
                           connect_args={"options": f"-csearch_path={schema}", "application_name": schema})
    try:
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        setup = Session()
        try:
            welt = _welt(setup)
        finally:
            setup.close()
        yield Session, welt
    finally:
        close_all_sessions()
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE application_name = :n"),
                         {"n": schema})
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin.dispose()


def _waits_for(first_holds_lock, second_action) -> dict:
    """first_holds_lock() hält die Sperre, bis das Ereignis gesetzt ist; second_action() läuft in einem Thread.
    Rückgabe: {"result": Ergebnis oder Ausnahme, "seconds": wie lange die zweite Aktion gebraucht hat}."""
    release, done = threading.Event(), {}

    def second():
        start = time.monotonic()
        try:
            done["result"] = second_action()
        except Exception as exc:  # noqa: BLE001 -- das Ergebnis prüft der Test
            done["result"] = exc
        done["seconds"] = time.monotonic() - start
    first_holds_lock(release)
    thread = threading.Thread(target=second)
    thread.start()
    time.sleep(1.0)
    assert "seconds" not in done, "die zweite Aktion wartete nicht auf die Sperre"
    release.set()
    thread.join(timeout=30)
    return done


def test_postgresql_acceptance_waits_for_a_running_sync_and_vice_versa(pg):
    Session, welt = pg
    holder = Session()
    holder_ready = threading.Event()

    def hold(release):
        def run():
            ensure_no_active_acceptance(holder, welt["order_id"], "der Abgleich")  # sperrt den Auftrag
            holder_ready.set()
            release.wait(timeout=30)
            holder.commit()
        threading.Thread(target=run).start()
        holder_ready.wait(timeout=10)

    def create():
        db = Session()
        try:
            order = db.get(Order, welt["order_id"])
            return acceptances_module.create_acceptance(
                db, order, {**GUELTIG, "accepted_on": date(2026, 9, 15), "roof_area_ids": []},
                [("beleg.pdf", PDF)], user_id=None, user_name="PG").id
        finally:
            db.close()
    done = _waits_for(hold, create)
    assert isinstance(done["result"], int) and done["seconds"] >= 0.9
    holder.close()

    # Umgekehrt: eine Abnahme wird gerade erfasst (Sperre gehalten, Zeile noch nicht committet) -- der Abgleich
    # wartet und sieht sie danach. Ohne Sperre sähe er nichts und liefe durch.
    db = Session()
    acceptances_module.discard_acceptance(db, db.get(OrderAcceptance, done["result"]), reason="Probe",
                                          user_id=None, user_name="PG")
    db.close()
    holder2 = Session()
    ready2 = threading.Event()

    def hold2(release):
        def run():
            acceptances_module.lock_order(holder2, welt["order_id"])
            holder2.add(OrderAcceptance(order_id=welt["order_id"], kind="foermlich", accepted_on=date(2026, 9, 20),
                                        scope="gesamt", result="verweigert", declared_by="auftraggeber",
                                        declared_by_name="K", content_sha256="probe", created_by_name="PG"))
            holder2.flush()
            ready2.set()
            release.wait(timeout=30)
            holder2.commit()
        threading.Thread(target=run).start()
        ready2.wait(timeout=10)

    def check():
        db = Session()
        try:
            ensure_no_active_acceptance(db, welt["order_id"], "der Abgleich")
            return "frei"
        finally:
            db.close()
    done = _waits_for(hold2, check)
    assert isinstance(done["result"], AcceptanceExistsError) and done["seconds"] >= 0.9
    holder2.close()
