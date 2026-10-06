"""Version 1.8.64 -- Stufe 2c-2d Teil 2, Punkt 4 (docs/archiv/abnahme-und-gewaehrleistung.md, "Umsetzung 1.8.64").

Mängel und Erklärungen des Abnahmeprotokolls gebündelt -- auf der Protokollseite (Karte "Erklärungen und Mängel",
GET /api/checklists/{id}/protocol-summary, nur Büro) und im PDF (oben die Erklärungen, am Feld "Mängel" jeder Mangel im
Protokoll statt "—"). Nach der Unterschrift des Auftraggebers aus ihrer versiegelten Kopie; ob ein verworfener Mangel im
Protokoll bleibt, sagt die Kopie. Dazu die Korrektur aus 1.8.63: die Links aufs Protokoll zeigen auf die Seite /checklisten/…"""

from pathlib import Path

from sqlalchemy import text
from starlette.routing import Match

import app.checklists as checklists_module
from app.checklist_pdf import build_checklist_pdf
from app.routers.pages import router as pages_router
from tests.test_v349_abnahme_und_gewaehrleistung import _welt, ablage, welt  # noqa: F401  (Fixtures)
from tests.test_v358_unterschrift_pruefung import SIGNATUR
from tests.test_v363_zweck_abnahme import A, _answer, _mangel, _sig, _sign_ag
from tests.test_v365_abnahme_aus_protokoll import AN, _nachholen, ohne_folge, protokoll  # noqa: F401  (Fixtures)

ROOT = Path(__file__).resolve().parent.parent


def _summary(p):
    r = p["client"].get(f"/api/checklists/{p['c']['id']}/protocol-summary")
    assert r.status_code == 200, r.text
    return r.json()


def _rows(s) -> dict:
    return {r["label"]: r["value"] for r in s["declarations"]}


def _discard_defect(p, defect_id, reason="doch keiner"):
    assert p["client"].post(f"/api/defects/{defect_id}/discard", json={"reason": reason}).status_code == 200


def _pdf_text(pdf: bytes) -> str:
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(pdf)
    try:
        parts = []
        for page in doc:
            textpage = page.get_textpage()
            parts.append(textpage.get_text_range(0, textpage.count_chars()))
            textpage.close()
        return "\n".join(parts)
    finally:
        doc.close()


def _abschliessen(p):
    r = p["client"].post(f"/api/checklists/{p['c']['id']}/attachments", data={"field_id": p["f"][AN]},
                         files={"file": ("s.png", SIGNATUR, "image/png")})
    assert r.status_code == 200, r.text
    r = p["client"].post(f"/api/checklists/{p['c']['id']}/complete")
    assert r.status_code == 200, r.text


# ---------------------------------------------------------------------------
# Seite: Erklärungen und Mängel gebündelt
# ---------------------------------------------------------------------------

def test_summary_before_the_signature_shows_the_current_answers(protokoll):
    p = protokoll
    _answer(p, "dachflaechen", [p["areas"]["Nord"]])
    s = _summary(p)
    assert (s["signed"], s["signature"], s["acceptance"], s["pending"], s["source"]) == (
        False, None, None, False, "aktuelle Angaben")
    assert _rows(s) == {"Ergebnis": "Abnahme erklärt", "Umfang": "Gesamtabnahme", "Dachflächen": "Nord",
                        "Vorbehalt wegen bekannter Mängel": "ja", "Vorbehalt der Vertragsstrafe": "nein",
                        "Mängel im Protokoll": "1"}
    [d] = s["defects"]
    assert (d["id"], d["status_label"], d["in_protocol"]) == (p["mangel"], "erfasst", True)


def test_summary_after_the_signature_comes_from_the_sealed_copy(protokoll):
    """Was der Auftraggeber unterschrieben hat: auch wenn eine Antwort danach am ORM vorbei geändert wird, zeigt die Karte
    die Kopie; Mängel vorher verworfen -> nicht im Protokoll, danach verworfen -> bleibt drin; die Abnahme mit Link."""
    p, db = protokoll, protokoll["db"]
    vorher = _mangel(p, "vorher verworfen")
    danach = _mangel(p, "danach verworfen")
    _discard_defect(p, vorher)
    _answer(p, "einwendungen", "Attika ist Restarbeit")
    assert _sign_ag(p, signer_person="Herbert Halle", signer_function="Geschäftsführer").status_code == 200
    _discard_defect(p, danach)
    db.execute(text("UPDATE checklist_answers SET value_text = 'teil' WHERE field_key = :k"), {"k": A + "umfang"})
    db.commit()
    s = _summary(p)
    assert s["signed"] and s["source"] == "Kopie der Unterschrift des Auftraggebers"
    assert "unterschrieben von Herbert Halle (Geschäftsführer)" in s["signature"]["text"]
    rows = _rows(s)
    assert (rows["Umfang"], rows["Mängel im Protokoll"], rows["Einwendungen des Auftragnehmers"]) == (
        "Gesamtabnahme", "2", "Attika ist Restarbeit")
    stand = {d["id"]: d["status_label"] for d in s["defects"]}
    assert stand == {p["mangel"]: "im Protokoll", vorher: "verworfen – nicht im Protokoll",
                     danach: "nach der Unterschrift verworfen – bleibt im Protokoll"}
    assert (s["defects_in_protocol"], s["defects_left_out"]) == (2, 1)
    acceptance = s["acceptance"]
    assert acceptance["url"] == f"/orders/{p['order_id']}#acceptanceCard" and not acceptance["discarded"]
    assert s["pending"] is False and s["problem"] is None


def test_refused_acceptance_has_no_reservations_in_the_summary(protokoll):
    p = protokoll
    _answer(p, "ergebnis", "verweigert")
    p["client"].put(f"/api/checklists/{p['c']['id']}/answers/{p['f']['vorbehalt_maengel']}", json={"value": None})
    p["client"].put(f"/api/checklists/{p['c']['id']}/answers/{p['f']['vorbehalt_vertragsstrafe']}", json={"value": None})
    rows = _rows(_summary(p))
    assert rows["Ergebnis"] == "Abnahme verweigert" and "Vorbehalt wegen bekannter Mängel" not in rows


def test_summary_shows_a_pending_acceptance_with_its_reason(protokoll, ohne_folge):
    p, db = protokoll, protokoll["db"]
    _answer(p, "dachflaechen", [p["areas"]["Nord"]])
    assert _sign_ag(p).status_code == 200
    from app.models import RoofArea

    db.get(RoofArea, p["areas"]["Nord"]).archived = True
    db.commit()
    s = _summary(p)
    assert s["pending"] and s["acceptance"] is None and "„Nord“ ist archiviert" in s["problem"]


def test_summary_is_office_only_and_null_for_other_checklists(protokoll, router_test_client):
    p = protokoll
    assert p["field"].get(f"/api/checklists/{p['c']['id']}/protocol-summary").status_code == 403
    from app.checklist_templates import add_field, create_template, publish_draft

    db = p["db"]
    t = create_template(db, label="Allgemein", contexts=["auftrag"])
    add_field(db, t["draft_version_id"], {"field_type": "text", "label": "Notiz"})
    tpl = publish_draft(db, t["id"])
    r = p["client"].post("/api/checklists", json={"template_id": tpl["id"], "context_type": "auftrag",
                                                  "order_id": p["order_id"]})
    assert p["client"].get(f"/api/checklists/{r.json()['id']}/protocol-summary").json() is None


def test_page_shows_the_summary_card():
    page = (ROOT / "app" / "templates" / "checklist.html").read_text(encoding="utf-8")
    assert "protocolSummaryCard" in page and "/protocol-summary" in page and "Erklärungen und Mängel" in page
    assert "runSummaryAcceptance" in page and "fmtDateTime(s.signature.signed_at)" in page


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------

def test_pdf_shows_the_declarations_and_the_defects_of_the_protocol(protokoll):
    p, db = protokoll, protokoll["db"]
    vorher = _mangel(p, "Rinne vorher verworfen")
    danach = _mangel(p, "Kehle danach verworfen")
    _discard_defect(p, vorher)
    assert _sign_ag(p, signer_person="Herbert Halle").status_code == 200
    _discard_defect(p, danach)
    _abschliessen(p)
    text_ = _pdf_text(build_checklist_pdf(db, checklists_module.get_checklist_row(db, p["c"]["id"])))
    assert "Erklärungen des Auftraggebers – Zusammenfassung" in text_
    assert "Mängel im Protokoll" in text_ and "Stand der Unterschrift des Auftraggebers vom" in text_
    assert f"Mangel Nr. {p['mangel']}" in text_ and "Attika undicht" in text_
    assert f"Mangel Nr. {danach}" in text_ and "bleibt im Protokoll" in text_
    assert f"Mangel Nr. {vorher}" not in text_ and "Rinne vorher verworfen" not in text_
    assert "doch keiner" not in text_  # Begründungen bleiben im ERP


def test_pdf_of_other_checklists_is_unchanged(protokoll):
    """Ohne Zweck "abnahme" keine Zusammenfassung."""
    from app.checklist_templates import add_field, create_template, publish_draft

    p, db = protokoll, protokoll["db"]
    t = create_template(db, label="Kurz", contexts=["auftrag"])
    add_field(db, t["draft_version_id"], {"field_type": "text", "label": "Notiz"})
    tpl = publish_draft(db, t["id"])
    c = p["client"].post("/api/checklists", json={"template_id": tpl["id"], "context_type": "auftrag",
                                                  "order_id": p["order_id"]}).json()
    assert p["client"].post(f"/api/checklists/{c['id']}/complete").status_code == 200
    text_ = _pdf_text(build_checklist_pdf(db, checklists_module.get_checklist_row(db, c["id"])))
    assert "Zusammenfassung" not in text_


# ---------------------------------------------------------------------------
# Korrektur 1.8.63: Links aufs Protokoll zeigen auf eine echte Seite
# ---------------------------------------------------------------------------

def _is_page(url: str) -> bool:
    scope = {"type": "http", "path": url.split("#")[0], "method": "GET"}
    return any(route.matches(scope)[0] == Match.FULL for route in pages_router.routes)


def test_links_to_the_protocol_point_to_the_page(protokoll, ohne_folge):
    p = protokoll
    assert _sign_ag(p).status_code == 200
    [pending] = p["client"].get(f"/api/orders/{p['order_id']}/pending-protocol-acceptances").json()
    a = _nachholen(p).json()
    for url in (pending["url"], a["protocol"]["url"], _summary(p)["acceptance"]["url"]):
        assert _is_page(url), url
    assert not _is_page(f"/checklists/{p['c']['id']}")  # der Pfad aus 1.8.63 war keine Seite
