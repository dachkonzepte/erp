"""Version 1.8.23 -- Speichern des Angebotskopfs leerte die interne Notiz.

quote_editor.html::saveHeader() schickte internal_note:null fest mit (der Editor hat kein Feld
dafür), und PUT /api/quotes/{id}/document-meta übernahm jedes Feld des Payloads -- auch ein
weggelassenes, das Pydantic mit None füllt. Beide Hälften sind behoben: der Editor schickt die
Notiz nicht mehr, der Server lässt eine nicht mitgeschickte Notiz stehen.

Der Test schickt genau die Schlüssel, die saveHeader() im Template an /document-meta übergibt
(aus dem Quelltext gelesen) -- schickt der Editor die Notiz wieder als null mit, oder leert der
Server ein fehlendes Feld wieder, wird er rot."""

import re
from pathlib import Path

from app.routers.quotes import router as quotes_router
from tests.test_v167_pagination import make_quote_with_items

EDITOR = Path(__file__).resolve().parent.parent / "app" / "templates" / "quote_editor.html"


def _editor_meta_keys() -> list[str]:
    """Die Schlüssel des Objekts, das saveHeader() an PUT .../document-meta schickt."""
    html = EDITOR.read_text(encoding="utf-8")
    match = re.search(r"/document-meta`,\{method:'PUT'.*?body:JSON\.stringify\(\{(.*?)\}\)\}\)", html, re.S)
    assert match, "saveHeader() ruft /document-meta nicht mehr wie erwartet auf -- Test anpassen"
    return re.findall(r"(?:^|,)([a-z_]+):", match.group(1))


def _editor_payload() -> dict:
    """Werte wie aus einem ausgefüllten Angebotskopf, nur für die Schlüssel, die der Editor schickt."""
    values = {"quote_date": "2026-10-01", "valid_until": "2026-10-31", "payment_terms": "14 Tage netto",
              "execution_period": "KW 44", "contract_basis": "bgb"}
    return {key: values.get(key) for key in _editor_meta_keys()}


def _meta(client, quote_id) -> dict:
    response = client.get(f"/api/quotes/{quote_id}")
    assert response.status_code == 200, response.text
    return response.json()["document_meta"]


def test_editor_schickt_die_kopfdaten(threaded_db_session):
    """Plausibilität des Auslesens: die sichtbaren Felder des Angebotskopfs sind dabei."""
    keys = _editor_meta_keys()
    assert {"quote_date", "valid_until", "payment_terms", "execution_period", "contract_basis"} <= set(keys)


def test_speichern_im_editor_laesst_die_interne_notiz_stehen(threaded_db_session, router_test_client):
    db = threaded_db_session
    quote = make_quote_with_items(db)
    client = router_test_client(db, quotes_router)
    base = {"quote_date": "2026-10-01"}
    assert client.put(f"/api/quotes/{quote.id}/document-meta",
                      json={**base, "internal_note": "Kunde will Skonto, nicht zusagen"}).status_code == 200

    response = client.put(f"/api/quotes/{quote.id}/document-meta", json=_editor_payload())
    assert response.status_code == 200, response.text

    meta = _meta(client, quote.id)
    assert meta["internal_note"] == "Kunde will Skonto, nicht zusagen"
    assert meta["payment_terms"] == "14 Tage netto"
    assert meta["execution_period"] == "KW 44"


def test_ausdrueckliches_null_leert_die_notiz_weiterhin(threaded_db_session, router_test_client):
    """Wer die Notiz über die API mitschickt, kann sie auch leeren -- nur das Weglassen ändert nichts."""
    db = threaded_db_session
    quote = make_quote_with_items(db)
    client = router_test_client(db, quotes_router)
    base = {"quote_date": "2026-10-01"}
    client.put(f"/api/quotes/{quote.id}/document-meta", json={**base, "internal_note": "alt"})
    assert client.put(f"/api/quotes/{quote.id}/document-meta",
                      json={**base, "internal_note": None}).status_code == 200
    assert _meta(client, quote.id)["internal_note"] is None
