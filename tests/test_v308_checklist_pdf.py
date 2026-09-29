"""Version 1.8.4 -- PDF einer abgeschlossenen Checkliste über den gemeinsamen Rahmen
(app/checklist_pdf.py, document_type="checklist"). Inhalt, Schnappschuss-Treue, Rechte (dieselbe
Leseprüfung wie der Einzelabruf) und dass nur abgeschlossene Checklisten ein PDF bekommen.

Textprüfung nur mit ASCII-Teilstrings (_extract_pdf_text, siehe test_v213)."""

import pytest

from app.checklist_pdf import build_checklist_pdf, format_answer
from app.document_frame import RENDERERS_USING_SHARED_FRAME
from app.document_layout import DOCUMENT_TYPES
from app.models import Checklist, OperationalAsset
from tests.test_v213_inspection_items import _extract_pdf_text
from tests.test_v305_checklist_filling import _client, _fields, _fill_order_checklist, _png, _start_order, world  # noqa: F401


def _completed_order_checklist(world, client):
    c = _start_order(world, client)
    f = _fields(c)
    client.put(f"/api/checklists/{c['id']}/answers/{f['bem']}", json={"value": "Dachrand Nord gesichert"})
    client.put(f"/api/checklists/{c['id']}/answers/{f['wind']}", json={"value": "12,5"})
    client.put(f"/api/checklists/{c['id']}/answers/{f['sich']}", json={"value": ["fangnetz"]})
    _fill_order_checklist(client, c)
    assert client.post(f"/api/checklists/{c['id']}/complete").status_code == 200
    return c


def _asset_checklist(world, client, value="nein"):
    c = client.post("/api/checklists", json={"template_id": world["asset_tpl"]["id"], "context_type": "betriebsmittel",
                                             "operational_asset_id": world["asset"].id}).json()
    client.put(f"/api/checklists/{c['id']}/answers/{_fields(c)['einsatzbereit']}", json={"value": value})
    assert client.post(f"/api/checklists/{c['id']}/complete").status_code == 200
    return c


def test_document_type_is_registered_for_the_shared_frame():
    assert "checklist" in RENDERERS_USING_SHARED_FRAME and "checklist" in DOCUMENT_TYPES


def test_order_checklist_pdf_contains_header_answers_photo_and_signature(world, router_test_client):
    a = _client(world, router_test_client, "a")
    c = _completed_order_checklist(world, a)
    resp = a.get(f"/api/checklists/{c['id']}/pdf")
    assert resp.status_code == 200 and resp.headers["content-type"] == "application/pdf"
    assert resp.content.startswith(b"%PDF")
    text = _extract_pdf_text(resp.content)
    for expected in (b"Sicherheitscheck", b"AU-2026-0001", b"Kunde Nord", b"Halle Nord", b"Freigegeben",
                     b"Dachrand Nord gesichert", b"12,5", b"Fangnetz", b"Anna Alpha", b"Vor Beginn lesen",
                     b"Unterschrift Monteur"):
        assert expected in text, expected
    # Foto und Unterschrift sind als Bilder eingebettet (JPEG bzw. PNG → zwei Bild-XObjects).
    assert resp.content.count(b"/Subtype /Image") >= 2


def test_asset_checklist_pdf_uses_snapshot_and_no_address(world, router_test_client):
    field = _client(world, router_test_client, "c")
    c = _asset_checklist(world, field)
    asset = world["db"].get(OperationalAsset, world["asset"].id)
    asset.name = "Umbenannt nach Abschluss"
    world["db"].commit()
    text = _extract_pdf_text(_client(world, router_test_client, "office").get(f"/api/checklists/{c['id']}/pdf").content)
    assert b"Hubsteiger" in text and b"BM-7" in text and b"Umbenannt" not in text  # eingefrorener Kontext (Klammern sind im PDF escaped)
    assert b"Einsatzbereit" in text and b"Nein" in text and b"Carla Gamma" in text
    assert b"Kunde Nord" not in text  # kein Anschriftenfeld im Kontext Betriebsmittel


def test_draft_has_no_pdf(world, router_test_client):
    a = _client(world, router_test_client, "a")
    c = _start_order(world, a)
    assert a.get(f"/api/checklists/{c['id']}/pdf").status_code == 400
    with pytest.raises(ValueError):
        build_checklist_pdf(world["db"], world["db"].get(Checklist, c["id"]))


def test_pdf_follows_read_rights(world, router_test_client):
    """Eigene: ja. Fremde, nicht lesbare Vorlage (Kollege am selben Auftrag): nein. Fremde,
    lesbare Vorlage (Gerät): ja. Betrieb: Monteur nie. Büro: alles."""
    a, b, c_field = (_client(world, router_test_client, k) for k in ("a", "b", "c"))
    office = _client(world, router_test_client, "office")
    order_c = _completed_order_checklist(world, a)
    asset_c = _asset_checklist(world, a, "ja")
    company = office.post("/api/checklists", json={"template_id": world["company_tpl"]["id"], "context_type": "betrieb"}).json()
    for name in ("Olga Office", "Anna Alpha"):
        office.post(f"/api/checklists/{company['id']}/attachments", data={"field_id": _fields(company)["tn"], "signer_name": name},
                    files={"file": ("s.png", _png(), "image/png")})
    assert office.post(f"/api/checklists/{company['id']}/complete").status_code == 200

    assert a.get(f"/api/checklists/{order_c['id']}/pdf").status_code == 200
    assert b.get(f"/api/checklists/{order_c['id']}/pdf").status_code == 403
    assert c_field.get(f"/api/checklists/{order_c['id']}/pdf").status_code == 403
    assert c_field.get(f"/api/checklists/{asset_c['id']}/pdf").status_code == 200
    assert a.get(f"/api/checklists/{company['id']}/pdf").status_code == 403
    for cid in (order_c["id"], asset_c["id"], company["id"]):
        assert office.get(f"/api/checklists/{cid}/pdf").status_code == 200
    assert office.get("/api/checklists/9999/pdf").status_code == 404
    text = _extract_pdf_text(office.get(f"/api/checklists/{company['id']}/pdf").content)
    assert b"Olga Office" in text and b"Anna Alpha" in text  # mehrere Unterschriften


def test_format_answer_variants(world):
    """Zahl ohne überflüssige Nullen mit Komma und Einheit, Auswahl über Beschriftungen."""
    from decimal import Decimal
    from types import SimpleNamespace

    number_field = SimpleNamespace(field_type="zahl", unit="km/h", options=[], multiple=False)
    answer = SimpleNamespace(value_number=Decimal("12.5000"), value_text=None, selections=[])
    assert format_answer(number_field, answer) == "12,5 km/h"
    answer.value_number = Decimal("100.0000")
    assert format_answer(number_field, answer) == "100 km/h"
    assert format_answer(number_field, None) == "—"
