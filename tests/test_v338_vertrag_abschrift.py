"""Version 1.8.35 -- Vertrag abrunden.

Punkt 1: unterschriebene Abschrift. Mit der Unterschrift entsteht ein PDF aus Fassung und Unterschriftsblatt bzw.
Papier-Scan, mit eigener Prüfsumme in der Ablage; Versand und Zustellung nach der Unterschrift verwenden sie
(§ 312f BGB: Abschrift des unterzeichneten Vertrags). Eine Unterschrift von vor 1.8.35 bekommt sie beim ersten
Versand, genau einmal (auch bei gleichzeitigen Anfragen gegen PostgreSQL, opt-in über ERP_TEST_POSTGRES_URL).
Punkt 2: Unterschrift im Einsatzbericht höchstens 2 MB, wie Checkliste und Vertrag.
Punkt 3: Fehlermeldungen der Auftragsseite lesbar statt "[object Object]" -- api() aus order.html läuft in node
mit echten 422-/409-Antworten der App.
Gegenproben (Schutz im Code ausgehebelt, Test rot, Datei byte-genau zurück): Skript im Scratchpad.
"""

import base64
import importlib.util
import json
import os
import re
import shutil
import stat
import subprocess
import threading
from io import BytesIO
from pathlib import Path

import pypdfium2 as pdfium
import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from PIL import Image, ImageDraw
from sqlalchemy import create_engine, inspect, select, text, update

from app import contract_versions as contract_versions_module
from app.berlin_time import berlin_today
from app.contract_signatures import ensure_signed_copy
from app.contract_templates import get_order_contract
from app.contract_versions import pdf_plain_text
from app.database import Base
from app.models import ArchiveImmutableError, AuditLog, EmailDispatch, OrderContractSignature, SentDocument
from app.orders import load_order
from app.sent_documents import read_sent_document
from tests.test_v321_email_dispatch import FakeSMTP, _attachment
from tests.test_v325_contract_basis import make_quote
from tests.test_v335_vertragsvorlagen import beauftragen
from tests.test_v336_vertrag_festschreiben import (  # noqa: F401  (world ist eine Fixture)
    CUSTOMER_EMAIL, _archive_path, _quote, world,
)
from tests.test_v337_vertrag_unterschrift import (  # noqa: F401  (pg ist eine Fixture)
    _client, _frozen_order, _paper, _pg_app, _pg_frozen_order, _pg_sign, _scan_pdf, _sign, _signature, _status, _together, pg,
)

TEMPLATES = Path(__file__).resolve().parents[1] / "app" / "templates"
NODE = shutil.which("node")


def _pages(pdf: bytes) -> list[tuple[float, float]]:
    doc = pdfium.PdfDocument(pdf)
    try:
        return [doc[i].get_size() for i in range(len(doc))]
    finally:
        doc.close()


def _send(client, order, key):
    return client.post(f"/api/orders/{order.id}/contract/send-email", json={"to_email": CUSTOMER_EMAIL, "dispatch_key": key})


def _deliver(client, contract_id, key):
    data = {"document_type": "vertrag", "document_id": str(contract_id), "channel": "persoenlich",
            "delivered_on": berlin_today().isoformat(), "note": "Beim Termin übergeben", "recipient": "", "dispatch_key": key}
    return client.post("/api/email-dispatches/manual", data=data)


def _attachment_name(message):
    return next(p.get_filename() for p in message.walk() if p.get_content_disposition() == "attachment")


def _last_dispatch(db):
    db.expire_all()
    return db.scalars(select(EmailDispatch).order_by(EmailDispatch.id.desc()).limit(1)).one()


def _forget_copy(db, order):
    """Stand einer Unterschrift von vor 1.8.35: ohne Abschrift (an der ORM-Sperre vorbei, wie die Migration)."""
    db.execute(update(OrderContractSignature).where(OrderContractSignature.id == _signature(db, order).id)
               .values(copy_document_id=None))
    db.commit()


def _photo(width, height, *, orientation=1, fmt="JPEG", transparent=False) -> bytes:
    image = Image.new("RGBA" if transparent else "RGB", (width, height), (0, 0, 0, 0) if transparent else "white")
    ImageDraw.Draw(image).line([(10, height - 10), (width - 10, 10)], fill=(20, 20, 20, 255), width=3)
    exif = Image.Exif()
    exif[0x0112] = orientation
    buf = BytesIO()
    image.save(buf, fmt, **({"exif": exif} if fmt == "JPEG" else {}))
    return buf.getvalue()


# --- Punkt 1: Abschrift entsteht mit der Unterschrift ----------------------------------------------

def test_device_signature_stores_a_signed_copy_of_version_and_sheet(world, router_test_client, monkeypatch):
    db = world
    client = _client(db, router_test_client)
    order, version = _frozen_order(db, client)
    res = _sign(client, order, version)
    assert res.status_code == 200, res.text
    signature = _signature(db, order)
    copy = signature.copy_document
    assert copy is not None and copy.id not in (version.sent_document_id, signature.document_id)
    assert (copy.document_type, copy.document_id, copy.content_type) == ("vertrag", version.contract_id, "application/pdf")
    assert copy.document_number == f"{order.order_number} · Fassung 1 · unterschrieben"
    assert copy.filename == f"Vertrag_{order.order_number}_Fassung_1_unterschrieben.pdf"
    fassung, sheet = read_sent_document(version.sent_document), read_sent_document(signature.document)
    copy_bytes = read_sent_document(copy)  # nur mit stimmender eigener Prüfsumme
    assert copy_bytes not in (fassung, sheet)
    # Erst alle Seiten der Fassung (mit Anlage), dann das Unterschriftsblatt.
    assert len(_pages(copy_bytes)) == len(_pages(fassung)) + len(_pages(sheet))
    assert pdf_plain_text(copy_bytes) == pdf_plain_text(fassung) + "\f" + pdf_plain_text(sheet)
    shown = res.json()["contract"]["signature"]
    assert shown["copy_document"]["id"] == copy.id and shown["copy_document"]["sha256"] == copy.sha256
    assert shown["copy_check"]["status"] == "unveraendert" and shown["copy_too_large"] is False
    audit = db.scalars(select(AuditLog).where(AuditLog.field_label == "Vertrag unterschrieben")).one()
    assert f"Abschrift {copy.sha256}" in audit.new_value
    # Über der Versandgrenze sagt die Karte es (dann auf anderem Weg zustellen).
    monkeypatch.setattr("app.email_sending.MAX_ATTACHMENT_BYTES", copy.size_bytes - 1)
    assert client.get(f"/api/orders/{order.id}/contract").json()["contract"]["signature"]["copy_too_large"] is True


def test_send_and_delivery_after_signature_use_the_signed_copy(world, router_test_client):
    db = world
    client = _client(db, router_test_client)
    order, version = _frozen_order(db, client)
    # Gegenprobe vor der Unterschrift: die Fassung selbst.
    assert _send(client, order, "vertrag-vorher-0001").status_code == 200
    assert _attachment(FakeSMTP.sent[-1]["message"]) == read_sent_document(version.sent_document)
    assert _sign(client, order, version).status_code == 200
    copy = _signature(db, order).copy_document
    documents = db.query(SentDocument).count()
    res = _send(client, order, "vertrag-abschrift-0001")
    assert res.status_code == 200, res.text
    message = FakeSMTP.sent[-1]["message"]
    assert _attachment(message) == read_sent_document(copy)
    assert _attachment_name(message) == copy.filename
    dispatch = _last_dispatch(db)
    assert dispatch.sent_document_id == copy.id and dispatch.document_number == copy.document_number
    assert db.query(SentDocument).count() == documents  # verwiesen, nicht noch einmal abgelegt
    # Zustellung nachtragen: dieselbe Abschrift.
    res = _deliver(client, version.contract_id, "vertrag-hand-abschrift-0001")
    assert res.status_code == 200, res.text
    assert res.json()["sent_document"]["id"] == copy.id
    assert _last_dispatch(db).subject.endswith(f"Vertrag zu Auftrag {order.order_number}, Fassung 1, unterschrieben")
    assert db.query(SentDocument).count() == documents


def test_paper_copy_appends_the_scan_pdf_or_the_photo_as_a_page(world, router_test_client):
    db = world
    client = _client(db, router_test_client)
    # Scan als PDF mit zwei Seiten: beide hinter der Fassung.
    order, version = _frozen_order(db, client, number="0001")
    scan = pdfium.PdfDocument(_scan_pdf("Seite eins des Scans"))
    scan.import_pages(pdfium.PdfDocument(_scan_pdf("Seite zwei des Scans")))
    buf = BytesIO()
    scan.save(buf)
    two_pages = buf.getvalue()
    assert _paper(client, order, version, scan=two_pages).status_code == 200
    copy = read_sent_document(_signature(db, order).copy_document)
    fassung = read_sent_document(version.sent_document)
    assert pdf_plain_text(copy) == pdf_plain_text(fassung) + "\f" + pdf_plain_text(two_pages)
    # Foto, quer gespeichert mit EXIF "um 90° drehen": eine Seite, hochkant wie das fotografierte Papier.
    order, version = _frozen_order(db, client, number="0002")
    assert _paper(client, order, version, scan=_photo(400, 300, orientation=6)).status_code == 200
    pages = _pages(read_sent_document(_signature(db, order).copy_document))
    assert len(pages) == len(_pages(read_sent_document(version.sent_document))) + 1
    width, height = pages[-1]
    assert width < height
    # Durchsichtiges PNG: auf Weiß, nicht auf Schwarz.
    order, version = _frozen_order(db, client, number="0003")
    assert _paper(client, order, version, scan=_photo(300, 400, fmt="PNG", transparent=True)).status_code == 200
    doc = pdfium.PdfDocument(read_sent_document(_signature(db, order).copy_document))
    try:
        page = doc[len(doc) - 1]
        image = page.render(scale=0.5).to_pil().convert("RGB")
        page.close()
    finally:
        doc.close()
    corner = image.getpixel((image.width // 2 - image.width // 4, image.height // 2 - image.height // 4))
    assert min(corner) > 200, corner
    # Ein "PDF", das sich nicht öffnen lässt, wird nicht angenommen -- nichts abgelegt, nichts unterschrieben.
    order, version = _frozen_order(db, client, number="0004")
    documents = db.query(SentDocument).count()
    res = _paper(client, order, version, scan=b"%PDF-1.4 kein echtes PDF")
    assert res.status_code == 400 and "nicht als PDF öffnen" in res.json()["detail"]
    assert db.query(SentDocument).count() == documents and _status(db, order) == "festgeschrieben"


# --- Punkt 1: Unterschrift von vor 1.8.35 ------------------------------------------------------------

def test_signature_from_before_1835_gets_its_copy_once_on_first_send(world, router_test_client):
    db = world
    client = _client(db, router_test_client)
    order, version = _frozen_order(db, client)
    assert _sign(client, order, version).status_code == 200
    _forget_copy(db, order)
    shown = client.get(f"/api/orders/{order.id}/contract").json()["contract"]["signature"]
    assert shown["copy_document"] is None and shown["copy_check"] is None
    documents = db.query(SentDocument).count()
    assert _send(client, order, "vertrag-alt-0001").status_code == 200
    signature = _signature(db, order)
    copy = signature.copy_document
    assert copy is not None and db.query(SentDocument).count() == documents + 1
    copy_bytes = read_sent_document(copy)
    assert _attachment(FakeSMTP.sent[-1]["message"]) == copy_bytes
    assert pdf_plain_text(copy_bytes) == (
        pdf_plain_text(read_sent_document(version.sent_document)) + "\f" + pdf_plain_text(read_sent_document(signature.document))
    )
    audit = db.scalars(select(AuditLog).where(AuditLog.field_label == "Unterschriebene Abschrift nachgeholt")).one()
    assert copy.sha256 in audit.new_value and audit.actor_name
    # Zweiter Versand und Zustellung: dieselbe Abschrift, keine weitere Datei.
    assert _send(client, order, "vertrag-alt-0002").status_code == 200
    assert _attachment(FakeSMTP.sent[-1]["message"]) == copy_bytes
    assert _deliver(client, version.contract_id, "vertrag-alt-hand-0001").json()["sent_document"]["id"] == copy.id
    assert db.query(SentDocument).count() == documents + 1
    # Über das ORM bleibt die Unterschrift gesperrt, auch dieses Feld.
    signature = _signature(db, order)
    signature.copy_document_id = signature.document_id
    with pytest.raises(ArchiveImmutableError):
        db.commit()
    db.rollback()


def test_missing_copy_is_not_built_from_a_damaged_archive(world, router_test_client):
    db = world
    client = _client(db, router_test_client)
    order, version = _frozen_order(db, client)
    assert _sign(client, order, version).status_code == 200
    _forget_copy(db, order)
    sheet = _archive_path(_signature(db, order).document)
    os.chmod(sheet, stat.S_IWRITE | stat.S_IREAD)
    sheet.write_bytes(sheet.read_bytes() + b"\n% veraendert")
    documents = db.query(SentDocument).count()
    res = _send(client, order, "vertrag-kaputt-0001")
    assert res.status_code == 409 and "nicht mehr unversehrt" in res.json()["detail"]
    res = _deliver(client, version.contract_id, "vertrag-kaputt-hand-0001")
    assert res.status_code == 400 and "nicht mehr unversehrt" in res.json()["detail"]
    assert FakeSMTP.sent == [] and _signature(db, order).copy_document_id is None
    assert db.query(SentDocument).count() == documents


# --- Migration ---------------------------------------------------------------------------------------

def _migration():
    path = next(Path(__file__).resolve().parents[1].glob("alembic/versions/*_vertrag_abschrift.py"))
    spec = importlib.util.spec_from_file_location("migration_1835_vertrag_abschrift", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(engine, fn_name):
    with engine.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            getattr(_migration(), fn_name)()


def test_migration_downgrade_refuses_while_copies_exist_and_upgrade_restores():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO order_contract_signatures (contract_id, version_id, method, signed_on, signed_content, "
                          "content_sha256, document_id, recorded_at, copy_document_id) "
                          "VALUES (1, 1, 'papier', '2026-10-01', '{}', 'x', 1, '2026-10-01 00:00:00', 2)"))
    with pytest.raises(RuntimeError, match="1 Unterschriften haben eine unterschriebene Abschrift"):
        _run(engine, "downgrade")
    with engine.begin() as conn:
        conn.execute(text("UPDATE order_contract_signatures SET copy_document_id = NULL"))
    _run(engine, "downgrade")
    assert "copy_document_id" not in {c["name"] for c in inspect(engine).get_columns("order_contract_signatures")}
    assert inspect(engine).get_table_names().count("order_contract_signatures") == 1
    _run(engine, "upgrade")
    assert "copy_document_id" in {c["name"] for c in inspect(engine).get_columns("order_contract_signatures")}
    fks = inspect(engine).get_foreign_keys("order_contract_signatures")
    assert any(fk["constrained_columns"] == ["copy_document_id"] and fk["referred_table"] == "sent_documents" for fk in fks)
    with engine.begin() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM order_contract_signatures WHERE copy_document_id IS NULL")).scalar() == 1


# --- Punkt 1: gleichzeitig gegen PostgreSQL -----------------------------------------------------------

def test_parallel_catch_up_of_a_missing_copy_on_postgresql_stores_exactly_one(pg, monkeypatch):
    """Zwei gleichzeitige Versände einer Unterschrift von vor 1.8.35 (hier direkt ensure_signed_copy(), je eine
    eigene Verbindung; die Sperren der Vertragszeile warten aufeinander): genau eine Abschrift, beide bekommen sie."""
    from fastapi.testclient import TestClient

    order_id, version_id, sha = _pg_frozen_order(pg, "A1")
    with TestClient(_pg_app(pg)) as client:
        assert _pg_sign(order_id, version_id, sha)(client) == 200
    db = pg()
    db.execute(update(OrderContractSignature).values(copy_document_id=None))
    db.commit()
    documents = db.query(SentDocument).count()
    db.close()
    _together(monkeypatch, 2)
    results, errors = [None, None], []

    def run(i):
        session = pg()
        try:
            order = load_order(session, order_id)
            results[i] = ensure_signed_copy(session, order, get_order_contract(session, order_id)).id
        except Exception as e:  # noqa: BLE001 -- im Ergebnis sichtbar machen, nicht den Thread beenden
            errors.append(repr(e))
        finally:
            session.close()
    threads = [threading.Thread(target=run, args=(i,)) for i in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    assert errors == [] and results[0] == results[1] is not None
    db = pg()
    assert db.query(SentDocument).count() == documents + 1
    assert db.scalar(select(OrderContractSignature.copy_document_id)) == results[0]
    db.close()


# --- Punkt 2: Unterschrift im Einsatzbericht höchstens 2 MB ------------------------------------------

def test_service_report_signature_is_limited_to_2_mb(router_test_client, threaded_db_session):
    from app import service_reports as service_reports_module
    from app.routers.service_reports import router as sr_router
    from app.service_reports import MAX_SIGNATURE_PNG_BYTES, create_report

    db = threaded_db_session
    order = beauftragen(db, make_quote(db))  # echte Beauftragung (läuft so auch gegen PostgreSQL)
    client = router_test_client(db, sr_router)
    assert MAX_SIGNATURE_PNG_BYTES == 2 * 1024 * 1024

    def png(size):
        return base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"0" * (size - 8)).decode()

    def sign(report_id, installer, customer):
        return client.post(f"/api/service-reports/{report_id}/sign", json={
            "installer_signature_png_base64": installer, "installer_signature_name": "Max Monteur",
            "customer_signature_png_base64": customer, "customer_signature_name": "Klara Kundin"})

    root = service_reports_module.SIGNATURE_ROOT
    files = lambda: len(list(root.glob("*"))) if root.exists() else 0  # noqa: E731
    report = create_report(db, order.id, "rapport")
    before = files()
    for installer, customer, who in ((MAX_SIGNATURE_PNG_BYTES + 1, 100, "des Monteurs"),
                                     (100, MAX_SIGNATURE_PNG_BYTES + 1, "des Kunden")):
        res = sign(report["id"], png(installer), png(customer))
        assert res.status_code == 400 and f"Die Unterschrift {who} ist zu groß" in res.json()["detail"], res.text
    assert files() == before  # nichts auf die Festplatte geschrieben
    db.expire_all()
    assert service_reports_module.get_report_row(db, report["id"]).status != "unterschrieben"
    # Genau an der Grenze: angenommen.
    res = sign(report["id"], png(MAX_SIGNATURE_PNG_BYTES), png(MAX_SIGNATURE_PNG_BYTES))
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "unterschrieben" and files() == before + 2


# --- Punkt 3: Fehlermeldungen der Auftragsseite -------------------------------------------------------

def _order_page_api_script() -> str:
    """fehlerText() aus _fehlertext.html und FELDNAMEN/api() genau so, wie sie in order.html stehen."""
    helper = "\n".join(re.findall(r"<script>(.*?)</script>", (TEMPLATES / "_fehlertext.html").read_text(encoding="utf-8"), flags=re.S))
    page = (TEMPLATES / "order.html").read_text(encoding="utf-8")
    lines = [re.search(rf"^{re.escape(start)}.*$", page, flags=re.M).group(0)
             for start in ("const FELDNAMEN=", "async function api(")]
    return helper + "\n" + "\n".join(lines)


def _messages(cases: list[tuple[int, object]]) -> list[str]:
    """api('/x') der Auftragsseite gegen eine abgelehnte Antwort je Fall (body None: kein JSON)."""
    script = _order_page_api_script() + f"""
const faelle = {json.dumps([{"status": s, "body": b} for s, b in cases])};
(async () => {{
  const out = [];
  for (const f of faelle) {{
    globalThis.fetch = async () => ({{ok: false, status: f.status, statusText: 'Status', json: async () => {{
      if (f.body === null) throw new SyntaxError('kein JSON'); return f.body; }}}});
    try {{ await api('/x'); out.push(null); }} catch (e) {{ out.push(e.message); }}
  }}
  process.stdout.write(JSON.stringify(out));
}})();
"""
    result = subprocess.run([NODE], input=script, capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


@pytest.mark.skipif(NODE is None, reason="node nicht installiert -- der Test führt JavaScript aus order.html aus.")
def test_order_page_shows_422_and_409_readably(world, router_test_client):
    from app.routers import invoices as invoices_router
    from app.routers import orders as orders_router

    db = world
    order = beauftragen(db, _quote(db))
    client = router_test_client(db, orders_router.router, invoices_router.router)
    office = _client(db, router_test_client)
    # Echte Antworten der App: Auftragsdatum geleert, Bezeichnung geleert, Betrag mit Tausenderpunkt (422);
    # Festschreiben ohne gewählte Anlage (409, Text).
    empty_date = client.put(f"/api/orders/{order.id}", json={"order_date": ""})
    empty_title = client.put(f"/api/orders/{order.id}", json={"title": ""})
    lump = client.post(f"/api/orders/{order.id}/invoices/abschlag-pauschal", json={"lump_sum_net": "1.234.56"})
    conflict = office.post(f"/api/orders/{order.id}/contract/freeze", json={})
    assert [r.status_code for r in (empty_date, empty_title, lump, conflict)] == [422, 422, 422, 409]
    messages = _messages([
        (422, empty_date.json()), (422, empty_title.json()), (422, lump.json()), (409, conflict.json()),
        (409, {"detail": {"message": "Der verknüpfte Kostenposten trägt weitere Angaben."}}),
        (409, None), (502, None), (422, {"detail": [{"type": "neu_unbekannt", "loc": ["body", "remarks"], "msg": "Something odd"}]}),
    ])
    assert not any("[object Object]" in m for m in messages), messages
    assert messages[0] == "Bitte die Eingabe prüfen – Auftragsdatum ist kein gültiges Datum."
    assert messages[1] == "Bitte die Eingabe prüfen – Bezeichnung ist zu kurz."
    assert messages[2] == "Bitte die Eingabe prüfen – Betrag netto muss eine Zahl sein (ohne Tausenderpunkt)."
    assert messages[3] == conflict.json()["detail"] and "bewusst wählen" in messages[3]
    assert messages[4] == "Der verknüpfte Kostenposten trägt weitere Angaben."
    assert messages[5].startswith("Der Stand hat sich inzwischen geändert") and messages[6].startswith("Serverfehler (502)")
    assert messages[7] == "Bitte die Eingabe prüfen – Bemerkungen: Something odd."


def test_order_page_includes_the_shared_error_helper(world, router_test_client):
    from app.routers import pages

    source = (TEMPLATES / "order.html").read_text(encoding="utf-8")
    assert '{% include "_fehlertext.html" %}' in source
    assert re.search(r"^async function api\(.*fehlerText\(", source, flags=re.M)
    html = router_test_client(world, pages.router, role="buero_auftrag").get("/orders/1").text
    assert "function fehlerText(" in html and "const FELDNAMEN=" in html
