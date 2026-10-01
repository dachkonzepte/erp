"""Version 1.8.34 -- Stufe 2b, Runde 2b-1b Teil 2b: Unterschrift unter dem Vertrag.

Punkt 1: gemeinsame Unterschriftsvorlage (_unterschrift.html) für Checkliste, Einsatzbericht und Vertrag.
Punkt 2: Unterschrift auf dem Gerät (Kunde und Betrieb, gebunden an Fassung und PDF-Prüfsumme, Ankreuzfelder
im unterschriebenen Inhalt, Unterschriftsblatt in der Ablage) oder Papier-Scan mit Datum und übertragenen
Ankreuzfeldern. Punkt 3: danach Vertragsgrundlage und Abgleich gesperrt, spätere Änderungen am Auftrag nur
als Hinweis. Punkt 4: Widerrufsfrist bei Verbrauchern mit Vermerk zum vorzeitigen Beginn. Punkt 5: Tests mit
Gegenprobe (Gegenproben-Skript im Scratchpad), Monteur 403, gleichzeitige Anfragen gegen PostgreSQL
(opt-in über ERP_TEST_POSTGRES_URL, Wegwerf-Schema, Regel 16).
"""

import base64
import hashlib
import importlib.util
import json
import os
import stat
import threading
import uuid
from datetime import date, timedelta
from io import BytesIO
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import close_all_sessions, sessionmaker

from app import contract_basis as contract_basis_module
from app import contract_versions as contract_versions_module
from app.berlin_time import berlin_today
from app.contract_signatures import withdrawal_info
from app.contract_templates import get_order_contract, save_template
from app.contract_versions import freeze_contract
from app.database import Base, get_db
from app.models import (
    AppUser, ArchiveImmutableError, AuditLog, OrderContract, OrderContractSignature, OrderContractVersion, QuoteItem,
    SentDocument,
)
from app.orders import load_order
from app.projects import load_quote
from app.routers import contract_templates as contract_router
from app.routers import orders as orders_router_module
from app.sent_documents import read_sent_document
from tests.test_v325_contract_basis import make_quote, pdf_text
from tests.test_v335_vertragsvorlagen import SECTIONS, beauftragen, save
from tests.test_v336_vertrag_festschreiben import (  # noqa: F401  (world ist eine Fixture)
    CUSTOMER_EMAIL, FakeSMTP, _archive_path, _freeze, _quote, _versions, world,
)

PG_TEST_DATABASE_URL = os.getenv("ERP_TEST_POSTGRES_URL")
CHECKBOX = "abschnitt-6"  # "Ich verlange den vorzeitigen Beginn." (nur Verbraucher, letzter Abschnitt)


def _png(*, ink=True, opaque=False) -> bytes:
    image = Image.new("RGBA", (300, 100), (255, 255, 255, 255 if opaque else 0))
    if ink:
        ImageDraw.Draw(image).line([(20, 70), (90, 20), (160, 75), (280, 30)], fill=(17, 17, 17, 255), width=4)
    buf = BytesIO()
    image.save(buf, "PNG")
    return buf.getvalue()


SIGNATURE = _png()
SIGNATURE_B64 = "data:image/png;base64," + base64.b64encode(SIGNATURE).decode()


def _client(db, router_test_client, role="buero_auftrag"):
    from app.routers import email_dispatches
    return router_test_client(db, contract_router.router, orders_router_module.router, email_dispatches.router, role=role)


def _frozen_order(db, client, *, number="0001", is_consumer=True):
    order = beauftragen(db, _quote(db, number, is_consumer=is_consumer))
    assert _freeze(client, order, attachment="aktuell").status_code == 200
    return order, _versions(db, order)[-1]


def _sign_payload(version, **overrides):
    payload = {
        "version_id": version.id, "pdf_sha256": version.sent_document.sha256, "checkboxes": {CHECKBOX: True},
        "customer_name": "Klara Kundin", "customer_signature_png_base64": SIGNATURE_B64,
        "company_name": "Bernd Büro", "company_signature_png_base64": SIGNATURE_B64,
    }
    payload.update(overrides)
    return payload


def _sign(client, order, version, **overrides):
    return client.post(f"/api/orders/{order.id}/contract/sign", json=_sign_payload(version, **overrides))


def _scan_pdf(text_line="Unterschriebener Vertrag (Scan)") -> bytes:
    """Ein echtes, einseitiges PDF als Scan (seit 1.8.35: der Scan muss sich öffnen lassen, er wird Teil der
    unterschriebenen Abschrift)."""
    from reportlab.pdfgen import canvas

    buf = BytesIO()
    pdf = canvas.Canvas(buf)
    pdf.drawString(72, 720, text_line)
    pdf.showPage()
    pdf.save()
    return buf.getvalue()


SCAN = _scan_pdf()


def _paper(client, order, version, *, signed_on=None, checkboxes=None, scan=SCAN, sha=None):
    data = {"version_id": str(version.id), "pdf_sha256": sha or version.sent_document.sha256,
            "signed_on": (signed_on or berlin_today()).isoformat(),
            "checkboxes": json.dumps({CHECKBOX: False} if checkboxes is None else checkboxes)}
    return client.post(f"/api/orders/{order.id}/contract/sign-paper", data=data,
                       files={"scan": ("scan.pdf", scan, "application/pdf")})


def _signature(db, order):
    db.expire_all()
    return get_order_contract(db, order.id).signature


def _status(db, order):
    db.expire_all()
    return get_order_contract(db, order.id).status


# --- Punkt 2: Unterschrift auf dem Gerät ---------------------------------------------------------

def test_device_signature_binds_version_pdf_and_checkboxes(world, router_test_client):
    db = world
    client = _client(db, router_test_client)
    order, version = _frozen_order(db, client)
    res = _sign(client, order, version)
    assert res.status_code == 200, res.text
    state = res.json()["contract"]
    assert state["status"] == "unterschrieben"
    shown = state["signature"]
    assert (shown["method"], shown["version_no"], shown["customer_signer_name"], shown["company_signer_name"]) == (
        "geraet", 1, "Klara Kundin", "Bernd Büro")
    assert shown["content_intact"] is True and shown["document_check"]["status"] == "unveraendert"
    signature = _signature(db, order)
    signed = json.loads(signature.signed_content)
    assert signature.content_sha256 == hashlib.sha256(signature.signed_content.encode("utf-8")).hexdigest()
    assert signed["pdf_sha256"] == version.sent_document.sha256 and signed["version_id"] == version.id
    assert signed["version_content_sha256"] == version.content_sha256 and signed["method"] == "geraet"
    assert [(b["key"], b["checked"]) for b in signed["checkboxes"]] == [(CHECKBOX, True)]
    # Unterschriftsblatt und beide Bilder in der Ablage; die Bilder sind genau die übergebenen Bytes.
    sheet = read_sent_document(signature.document)
    assert signature.document.document_type == "vertrag" and signature.document.document_id == version.contract_id
    texts = pdf_text(sheet)
    for expected in ("Unterschriftsblatt", "Klara Kundin", "Bernd Büro", "(angekreuzt)", version.sent_document.sha256,
                     signature.content_sha256, "Fassung 1"):
        assert expected in texts, expected
    assert read_sent_document(signature.customer_image_document) == SIGNATURE
    assert signed["customer"]["image_sha256"] == hashlib.sha256(SIGNATURE).hexdigest() == signature.company_image_document.sha256
    assert db.scalar(select(AuditLog).where(AuditLog.entity_type == "Vertrag", AuditLog.field_label == "Vertrag unterschrieben"))


def test_checkbox_state_is_part_of_the_signed_content(world, router_test_client):
    db = world
    client = _client(db, router_test_client)
    order, version = _frozen_order(db, client)
    archived = db.query(SentDocument).count()
    # Jedes Ankreuzfeld ausdrücklich: fehlend, unbekannt oder kein Wahrheitswert -> abgelehnt, nichts abgelegt.
    res = _sign(client, order, version, checkboxes={})
    assert res.status_code == 400 and "ausdrücklich" in res.json()["detail"]
    assert _sign(client, order, version, checkboxes={CHECKBOX: True, "abschnitt-99": False}).status_code == 400
    assert _sign(client, order, version, checkboxes={CHECKBOX: "ja"}).status_code == 422
    assert _status(db, order) == "festgeschrieben" and db.query(SentDocument).count() == archived
    # Nicht angekreuzt: steht so im unterschriebenen Inhalt und auf dem Blatt.
    assert _sign(client, order, version, checkboxes={CHECKBOX: False}).status_code == 200
    signature = _signature(db, order)
    unchecked = json.loads(signature.signed_content)
    assert unchecked["checkboxes"][0]["checked"] is False
    assert "(nicht angekreuzt)" in pdf_text(read_sent_document(signature.document))
    # Gegenprobe: derselbe Inhalt mit angekreuztem Feld hätte eine andere Prüfsumme.
    checked = json.loads(signature.signed_content)
    checked["checkboxes"][0]["checked"] = True
    assert contract_versions_module.sha256_text(contract_versions_module.canonical_json(checked)) != signature.content_sha256


def test_wrong_or_superseded_version_is_rejected(world, router_test_client):
    db = world
    client = _client(db, router_test_client)
    order, first = _frozen_order(db, client)
    res = _sign(client, order, first, pdf_sha256="0" * 64)
    assert res.status_code == 409 and "Prüfsumme passt nicht" in res.json()["detail"]
    # Neue Fassung im Entwurf: nichts zu unterschreiben.
    assert client.post(f"/api/orders/{order.id}/contract/new-version").status_code == 200
    res = _sign(client, order, first)
    assert res.status_code == 409 and "festgeschriebener Vertrag" in res.json()["detail"]
    assert _freeze(client, order, attachment="aktuell").status_code == 200
    first, second = _versions(db, order)
    # Abgelöste Fassung mit ihrer eigenen, richtigen Prüfsumme -> abgelehnt; gültige ID mit alter Prüfsumme auch.
    res = _sign(client, order, first)
    assert res.status_code == 409 and "nicht die gültige" in res.json()["detail"]
    assert _sign(client, order, second, pdf_sha256=first.sent_document.sha256).status_code == 409
    # Fassung passt nicht mehr zum Auftrag (Auftragssumme geändert) -> abgelehnt.
    item = load_order(db, order.id).items[0]
    original_price = item.unit_price
    item.unit_price = original_price * 2
    db.commit()
    res = _sign(client, order, second)
    assert res.status_code == 409 and "passt nicht mehr zum Auftrag" in res.json()["detail"]
    item = load_order(db, order.id).items[0]
    item.unit_price = original_price
    db.commit()
    # PDF in der Ablage verändert -> abgelehnt.
    path = _archive_path(second.sent_document)
    original = path.read_bytes()
    os.chmod(path, stat.S_IREAD | stat.S_IWRITE)
    path.write_bytes(original + b"%x")
    assert _sign(client, order, second).status_code == 409
    path.write_bytes(original)
    assert _status(db, order) == "festgeschrieben" and _signature(db, order) is None
    assert _sign(client, order, second).status_code == 200


def test_blank_or_invalid_signatures_and_missing_names_are_rejected(world, router_test_client):
    db = world
    client = _client(db, router_test_client)
    order, version = _frozen_order(db, client)
    blank = "data:image/png;base64," + base64.b64encode(_png(ink=False)).decode()
    res = _sign(client, order, version, customer_signature_png_base64=blank)
    assert res.status_code == 400 and "leer" in res.json()["detail"]
    buf = BytesIO()
    Image.new("RGB", (50, 20), "black").save(buf, "JPEG")
    jpeg = base64.b64encode(buf.getvalue()).decode()
    assert _sign(client, order, version, company_signature_png_base64=jpeg).status_code == 400
    assert _sign(client, order, version, customer_signature_png_base64="kein base64!").status_code == 400
    assert _sign(client, order, version, customer_name="  ").status_code == 400
    assert _status(db, order) == "festgeschrieben"
    # Deckender weißer Hintergrund mit Strich zählt als Unterschrift.
    opaque = "data:image/png;base64," + base64.b64encode(_png(opaque=True)).decode()
    assert _sign(client, order, version, customer_signature_png_base64=opaque).status_code == 200


# --- Punkt 2: Papier ------------------------------------------------------------------------------

def test_paper_scan_with_date_and_transferred_checkboxes(world, router_test_client):
    db = world
    client = _client(db, router_test_client)
    order, version = _frozen_order(db, client)
    assert _paper(client, order, version, signed_on=berlin_today() + timedelta(days=1)).status_code == 400
    res = _paper(client, order, version, signed_on=berlin_today() - timedelta(days=1))
    assert res.status_code == 400 and "vor dem Festschreiben" in res.json()["detail"]
    assert _paper(client, order, version, scan=b"<html>kein Scan</html>").status_code == 400
    assert _paper(client, order, version, checkboxes={}).status_code == 400
    assert _paper(client, order, version, sha="f" * 64).status_code == 409
    assert _status(db, order) == "festgeschrieben"
    # Festlegung: eine Abweichung vom Auftrag sperrt das Eintragen des Papiers nicht.
    item = load_order(db, order.id).items[0]
    item.unit_price = item.unit_price + 1
    db.commit()
    res = _paper(client, order, version, checkboxes={CHECKBOX: True})
    assert res.status_code == 200, res.text
    state = res.json()["contract"]
    assert state["status"] == "unterschrieben" and state["differences"]  # nur noch Hinweis
    signature = _signature(db, order)
    signed = json.loads(signature.signed_content)
    assert signed["method"] == "papier" and signed["checkboxes"][0]["checked"] is True
    assert signed["scan"]["sha256"] == signature.document.sha256 == hashlib.sha256(SCAN).hexdigest()
    assert signature.customer_image_document_id is None and signature.signed_on == berlin_today()
    assert read_sent_document(signature.document) == SCAN


# --- Punkt 3: Sperren nach der Unterschrift --------------------------------------------------------

def test_after_signature_basis_sync_and_new_versions_are_locked(world, router_test_client):
    db = world
    client = _client(db, router_test_client)
    order, version = _frozen_order(db, client)
    other, _ = _frozen_order(db, client, number="0002")
    for target in (order, other):  # Angebot nach der Beauftragung geändert: Abgleich wäre möglich
        quote = load_quote(db, target.source_quote_id)
        db.get(QuoteItem, quote.items[0].id).unit_price = 61
    db.commit()
    assert _sign(client, order, version).status_code == 200
    res = client.put(f"/api/orders/{order.id}/contract-basis", json={"contract_basis": "vob_b", "reason": "doch VOB"})
    assert res.status_code == 409 and "unterschrieben" in res.json()["detail"]
    res = client.post(f"/api/orders/{order.id}/sync-source-quote", json={"reason": "Angebot übernehmen"})
    assert res.status_code == 409 and "Abgleich" in res.json()["detail"]
    assert client.post(f"/api/orders/{order.id}/contract/new-version").status_code == 409
    assert _freeze(client, order, attachment="aktuell").status_code == 409
    assert client.put(f"/api/orders/{order.id}/contract", json={"payment_plan": "neu"}).status_code == 422
    assert _sign(client, order, version).status_code == 409
    assert _paper(client, order, version).status_code == 409
    assert load_order(db, order.id).contract_basis == "bgb_vob_c_4_5"
    # Gegenprobe: am nicht unterschriebenen Auftrag geht beides.
    assert client.post(f"/api/orders/{other.id}/sync-source-quote", json={"reason": "x"}).status_code == 200
    assert client.put(f"/api/orders/{other.id}/contract-basis", json={"contract_basis": "vob_b", "reason": "x"}).status_code == 200
    # Spätere Änderung am Auftrag (Nachtrag): erlaubt, der Vertrag bleibt unterschrieben, die Karte zeigt es nur.
    item = load_order(db, order.id).items[0]
    res = client.put(f"/api/orders/{order.id}/items/{item.id}", json={
        "quantity": 12, "unit": item.unit, "unit_price": float(item.unit_price), "short_text": item.short_text,
        "long_text": "", "position_type": item.position_type, "gaeb_oz": None, "include_in_total": True})
    assert res.status_code == 200, res.text
    state = client.get(f"/api/orders/{order.id}/contract").json()["contract"]
    assert state["status"] == "unterschrieben" and any(d.startswith("Auftragssumme") for d in state["differences"])
    # Die unterschriebene Fassung bleibt abrufbar und versendbar (Abschrift für den Kunden).
    assert client.get(f"/api/orders/{order.id}/contract/pdf").content == read_sent_document(version.sent_document)
    res = client.post(f"/api/orders/{order.id}/contract/send-email", json={"to_email": CUSTOMER_EMAIL, "dispatch_key": "vertrag-abschrift-01"})
    assert res.status_code == 200, res.text
    assert len(FakeSMTP.sent) == 1


# --- Punkt 4: Widerrufsfrist ----------------------------------------------------------------------

def test_withdrawal_deadline_and_early_start_note(world, router_test_client):
    db = world
    sections = [dict(s) for s in SECTIONS]
    sections[-1]["early_start"] = True
    save_template(db, "bgb_vob_c_4_5", title="Bauvertrag", sections=sections, reviewed_on=berlin_today(), reviewed_by="RA")
    client = _client(db, router_test_client)
    order, version = _frozen_order(db, client)
    assert json.loads(version.frozen_content)["sections"][-1]["early_start"] is True
    state = _sign(client, order, version, checkboxes={CHECKBOX: True}).json()["contract"]
    withdrawal = state["signature"]["withdrawal"]
    deadline = date.fromisoformat(withdrawal["deadline"])
    assert deadline - berlin_today() >= timedelta(days=14) and deadline.weekday() < 5
    assert withdrawal["early_start"] is True and "vorzeitigen Beginn" in withdrawal["early_start_label"]
    # Kein Verbraucher: keine Widerrufsfrist (Vorgabe-Grundlage VOB/B, eigene Vorlage ohne Ankreuzfeld).
    save(db, "vob_b", sections=[{"heading": "VOB", "body_text": "Nach VOB/B"}], title="VOB-Vertrag", reviewed=True)
    business, business_version = _frozen_order(db, client, number="0002", is_consumer=False)
    state = _sign(client, business, business_version, checkboxes={}).json()["contract"]
    assert state["signature"]["withdrawal"] is None


def test_withdrawal_info_counts_14_days_and_skips_the_weekend():
    def signed(day, checkboxes=()):
        return {"is_consumer": True, "signed_on": day.isoformat(), "checkboxes": list(checkboxes)}
    thursday = withdrawal_info(signed(date(2026, 10, 1)))
    assert thursday["deadline"] == date(2026, 10, 15) and thursday["shifted_from_weekend"] is False
    saturday = withdrawal_info(signed(date(2026, 10, 3)))  # +14 = Samstag 17.10. -> Montag 19.10.
    assert saturday["deadline"] == date(2026, 10, 19) and saturday["shifted_from_weekend"] is True
    assert thursday["early_start"] is None  # ohne gekennzeichnetes Ankreuzfeld kein Vermerk
    marked = withdrawal_info(signed(date(2026, 10, 1), [{"key": "a", "heading": None, "text": "Beginn", "early_start": True, "checked": False}]))
    assert marked["early_start"] is False
    assert withdrawal_info({"is_consumer": False, "signed_on": "2026-10-01", "checkboxes": []}) is None


def test_early_start_marker_rules(world):
    db = world
    sections = [dict(s) for s in SECTIONS]
    sections[0]["early_start"] = True  # ohne Ankreuzfeld
    with pytest.raises(ValueError, match="vorzeitigen Beginns"):
        save_template(db, "bgb_vob_c_4_5", title="T", sections=sections, reviewed_on=None, reviewed_by=None)
    sections = [dict(s) for s in SECTIONS] + [dict(SECTIONS[-1])]
    sections[-1]["early_start"] = sections[-2]["early_start"] = True
    with pytest.raises(ValueError, match="Nur ein Ankreuzfeld"):
        save_template(db, "bgb_vob_c_4_5", title="T", sections=sections, reviewed_on=None, reviewed_by=None)
    # Das Kennzeichen setzt die Prüfung nicht zurück (kein Text im Vertrag ändert sich), eine Textänderung schon.
    marked = [dict(s) for s in SECTIONS]
    marked[-1]["early_start"] = True
    template, reset = save_template(db, "bgb_vob_c_4_5", title="Bauvertrag {auftragsnummer}", sections=marked,
                                    reviewed_on=berlin_today(), reviewed_by="RA Beispiel")
    assert reset is False and template["reviewed"] is True and template["sections"][-1]["early_start"] is True
    marked[0]["body_text"] = "anders"
    template, reset = save_template(db, "bgb_vob_c_4_5", title="Bauvertrag {auftragsnummer}", sections=marked,
                                    reviewed_on=berlin_today(), reviewed_by="RA Beispiel")
    assert reset is True and template["reviewed"] is False


# --- Rechte, Unveränderlichkeit, Vorlagen, Migration ----------------------------------------------

def test_monteur_gets_403_on_the_signature_routes(world, router_test_client):
    db = world
    office = _client(db, router_test_client)
    order, version = _frozen_order(db, office)
    field = _client(db, router_test_client, role="field")
    assert _sign(field, order, version).status_code == 403
    assert _paper(field, order, version).status_code == 403
    assert field.get(f"/api/orders/{order.id}/contract").status_code == 403
    assert _status(db, order) == "festgeschrieben" and db.query(OrderContractSignature).count() == 0


def test_signature_is_unchangeable_and_never_deleted(world, router_test_client):
    db = world
    client = _client(db, router_test_client)
    order, version = _frozen_order(db, client)
    assert _sign(client, order, version).status_code == 200
    signature = _signature(db, order)
    signature.customer_signer_name = "Jemand anderes"
    with pytest.raises(ArchiveImmutableError):
        db.commit()
    db.rollback()
    with pytest.raises(ArchiveImmutableError):
        db.delete(_signature(db, order))
        db.commit()
    db.rollback()


def test_checklist_service_report_and_order_pages_use_the_shared_pad(world, router_test_client):
    """Punkt 1: eine Vorlage statt drei Kopien -- Zeichenfläche weiß mit dunklem Strich in beiden Themes."""
    from app.routers import pages
    root = Path(__file__).resolve().parents[1] / "app" / "templates"
    shared = (root / "_unterschrift.html").read_text(encoding="utf-8")
    assert "background:#fff" in shared and "strokeStyle='#111'" in shared and "devicePixelRatio" in shared
    for name in ("checklist.html", "service_reports.html", "order.html"):
        source = (root / name).read_text(encoding="utf-8")
        assert '{% include "_unterschrift.html" %}' in source, name
        assert "getContext('2d')" not in source and "setPointerCapture" not in source, f"{name}: eigene Zeichenlogik"
    client = router_test_client(world, pages.router, role="buero_auftrag")
    for path in ("/orders/1/service-reports", "/checklisten/1", "/orders/1"):
        html = client.get(path).text
        assert "function unterschriftsfeld(" in html and "dk-unterschrift" in html, path


def _migration():
    path = next(Path(__file__).resolve().parents[1].glob("alembic/versions/*_vertrag_unterschrift.py"))
    spec = importlib.util.spec_from_file_location("migration_1834_vertrag_unterschrift", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(engine, fn_name):
    module = _migration()
    with engine.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            getattr(module, fn_name)()


def test_migration_downgrade_refuses_while_signatures_exist_and_upgrade_restores():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO contract_templates (basis_key, updated_by_name, updated_at) VALUES ('bgb', 'X', '2026-10-01 00:00:00')"))
        conn.execute(text("INSERT INTO contract_template_sections (template_id, sort_order, body_text, consumer_only, with_checkbox, early_start) "
                          "VALUES (1, 10, 'Beginn', true, true, true)"))
    with pytest.raises(RuntimeError, match="1 als „vorzeitiger Beginn“"):
        _run(engine, "downgrade")
    with engine.begin() as conn:
        conn.execute(text("UPDATE contract_template_sections SET early_start = false"))
        conn.execute(text("INSERT INTO order_contracts (order_id, status, created_by_name, created_at, updated_at) "
                          "VALUES (1, 'unterschrieben', 'X', '2026-10-01 00:00:00', '2026-10-01 00:00:00')"))
    with pytest.raises(RuntimeError, match="1 unterschriebene Verträge"):
        _run(engine, "downgrade")
    with engine.begin() as conn:
        conn.execute(text("UPDATE order_contracts SET status = 'festgeschrieben'"))
    _run(engine, "downgrade")
    assert "order_contract_signatures" not in inspect(engine).get_table_names()
    assert "early_start" not in {c["name"] for c in inspect(engine).get_columns("contract_template_sections")}
    _run(engine, "upgrade")
    with engine.begin() as conn:
        assert conn.execute(text("SELECT early_start FROM contract_template_sections")).scalar() in (False, 0)
        conn.execute(text("INSERT INTO order_contract_signatures (contract_id, version_id, method, signed_on, signed_content, "
                          "content_sha256, document_id, recorded_at) VALUES (1, 1, 'papier', '2026-10-01', '{}', 'x', 1, '2026-10-01 00:00:00')"))
    with pytest.raises(RuntimeError, match="1 Unterschriften"):
        _run(engine, "downgrade")


# --- Punkt 5: gleichzeitige Anfragen gegen PostgreSQL ----------------------------------------------

@pytest.fixture
def pg():
    """Wegwerf-Schema in der PostgreSQL-Testdatenbank, eine echte Verbindung je Anfrage (Regel 16)."""
    if not PG_TEST_DATABASE_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    schema = f"pgtest_vertrag_{uuid.uuid4().hex[:8]}"
    admin = create_engine(PG_TEST_DATABASE_URL)
    with admin.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
    engine = create_engine(PG_TEST_DATABASE_URL, pool_size=10,
                           connect_args={"options": f"-csearch_path={schema}", "application_name": schema})
    try:
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        setup = Session()
        save(setup, reviewed=True)
        setup.close()
        yield Session
    finally:
        # Schlägt eine Prüfung fehl, bleibt eine Sitzung offen ("idle in transaction") und DROP SCHEMA
        # wartete ewig auf ihre Sperren -- deshalb alle Sitzungen schließen und die eigenen Verbindungen
        # (erkannt am application_name) beenden.
        close_all_sessions()
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE application_name = :n"), {"n": schema})
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin.dispose()


def _pg_app(Session):
    app = FastAPI()
    app.include_router(contract_router.router)
    app.include_router(orders_router_module.router)

    @app.middleware("http")
    async def _identity(request, call_next):
        request.state.erp_user = AppUser(username="buero", display_name="Büro", role="buero_auftrag", active=True, password_hash="x")
        return await call_next(request)

    def _session():
        session = Session()
        try:
            yield session
        finally:
            session.close()
    app.dependency_overrides[get_db] = _session
    return app


def _pg_frozen_order(Session, number):
    db = Session()
    try:
        order = beauftragen(db, make_quote(db, number=number))
        freeze_contract(db, load_order(db, order.id), attachment="aktuell")
        version = db.scalars(select(OrderContractVersion).join(OrderContract).where(OrderContract.order_id == order.id)).one()
        return order.id, version.id, version.sent_document.sha256
    finally:
        db.close()


_ORIGINAL_LOCK = contract_versions_module._locked_contract
_ORIGINAL_ENSURE = contract_basis_module.ensure_contract_not_signed


def _together(monkeypatch, parties):
    """Die ersten `parties` Sperren der Vertragszeile warten aufeinander -- alle Anfragen haben ihre
    Vorabprüfungen hinter sich, die Datenbank entscheidet. Gezählt wird über alle Threads (eine Anfrage läuft
    in einem Worker-Thread des Testclients, zwei Anfragen desselben Clients womöglich in verschiedenen)."""
    barrier = threading.Barrier(parties)
    count, lock = [0], threading.Lock()

    def gate(original):
        def wrapper(*args, **kwargs):
            with lock:
                count[0] += 1
                mine = count[0]
            if mine <= parties:
                barrier.wait(timeout=20)
            return original(*args, **kwargs)
        return wrapper
    monkeypatch.setattr(contract_versions_module, "_locked_contract", gate(_ORIGINAL_LOCK))
    monkeypatch.setattr(contract_basis_module, "ensure_contract_not_signed", gate(_ORIGINAL_ENSURE))


def _parallel(app, calls):
    results = [None] * len(calls)

    def run(i, call):
        # Ein Serverfehler soll als 500 im Ergebnis stehen, nicht den Thread beenden.
        with TestClient(app, raise_server_exceptions=False) as client:
            results[i] = call(client)
    threads = [threading.Thread(target=run, args=(i, c)) for i, c in enumerate(calls)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    return results


def _pg_sign(order_id, version_id, sha):
    payload = {"version_id": version_id, "pdf_sha256": sha, "checkboxes": {CHECKBOX: True}, "customer_name": "K",
               "customer_signature_png_base64": SIGNATURE_B64, "company_name": "B", "company_signature_png_base64": SIGNATURE_B64}
    return lambda c: c.post(f"/api/orders/{order_id}/contract/sign", json=payload).status_code


def test_parallel_freeze_requests_on_postgresql_write_exactly_one_version(pg, monkeypatch):
    app = _pg_app(pg)
    for round_no in range(3):
        db = pg()
        order = beauftragen(db, make_quote(db, number=f"F{round_no}"))
        order_id = order.id
        db.close()
        _together(monkeypatch, 2)
        freeze = lambda c: c.post(f"/api/orders/{order_id}/contract/freeze", json={"attachment": "aktuell"}).status_code  # noqa: E731
        assert sorted(_parallel(app, [freeze, freeze])) == [200, 409]
        db = pg()
        assert db.scalar(select(OrderContract.status).where(OrderContract.order_id == order_id)) == "festgeschrieben"
        assert db.query(OrderContractVersion).join(OrderContract).filter(OrderContract.order_id == order_id).count() == 1
        db.close()


def test_parallel_signatures_on_postgresql_exactly_one_wins(pg, monkeypatch):
    app = _pg_app(pg)
    order_id, version_id, sha = _pg_frozen_order(pg, "S1")
    _together(monkeypatch, 3)
    sign = _pg_sign(order_id, version_id, sha)
    assert sorted(_parallel(app, [sign, sign, sign])) == [200, 409, 409]
    db = pg()
    assert db.query(OrderContractSignature).count() == 1
    assert db.scalar(select(OrderContract.status).where(OrderContract.order_id == order_id)) == "unterschrieben"
    db.close()


def test_parallel_freeze_and_sign_on_postgresql_never_both(pg, monkeypatch):
    """Gleichzeitig: Unterschrift unter Fassung 1 und "Neue Fassung" + Festschreiben von Fassung 2. Entweder
    die Unterschrift gewinnt (dann keine neue Fassung) oder die neue Fassung (dann keine Unterschrift unter
    der abgelösten) -- nie beides."""
    app = _pg_app(pg)
    outcomes = []
    for round_no in range(5):
        order_id, version_id, sha = _pg_frozen_order(pg, f"N{round_no}")
        _together(monkeypatch, 2)

        def new_version_then_freeze(c, order_id=order_id):
            first = c.post(f"/api/orders/{order_id}/contract/new-version").status_code
            second = c.post(f"/api/orders/{order_id}/contract/freeze", json={"attachment": "aktuell"}).status_code if first == 200 else None
            return first, second
        signed, (new_version, frozen) = _parallel(app, [_pg_sign(order_id, version_id, sha), new_version_then_freeze])
        db = pg()
        contract = db.scalars(select(OrderContract).where(OrderContract.order_id == order_id)).one()
        versions = sorted(contract.versions, key=lambda v: v.version_no)
        if signed == 200:
            assert new_version == 409 and frozen is None
            assert contract.status == "unterschrieben" and len(versions) == 1
            assert contract.signature.version_id == versions[-1].id and versions[-1].superseded_at is None
        else:
            assert signed == 409 and (new_version, frozen) == (200, 200)
            assert contract.status == "festgeschrieben" and contract.signature is None and len(versions) == 2
        outcomes.append("Unterschrift" if signed == 200 else "neue Fassung")
        db.close()
    assert set(outcomes) <= {"Unterschrift", "neue Fassung"}, outcomes


def test_parallel_sign_and_basis_change_on_postgresql_never_both(pg, monkeypatch):
    app = _pg_app(pg)
    for round_no in range(3):
        order_id, version_id, sha = _pg_frozen_order(pg, f"B{round_no}")
        _together(monkeypatch, 2)
        change = lambda c, o=order_id: c.put(f"/api/orders/{o}/contract-basis", json={"contract_basis": "vob_b", "reason": "x"}).status_code  # noqa: E731
        signed, changed = _parallel(app, [_pg_sign(order_id, version_id, sha), change])
        assert sorted([signed, changed]) == [200, 409], (signed, changed)
        db = pg()
        basis = db.scalar(select(OrderContract.status).where(OrderContract.order_id == order_id))
        assert basis == ("unterschrieben" if signed == 200 else "festgeschrieben")
        db.close()
