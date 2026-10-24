"""Seit 1.9.69 (Stufe 4, R4 Nachrunde, Punkt 5): Benennung für die Monteurin.

    Mangel   die freigegebenen Mängel der Abnahme (Defect) heißen auch für die Monteurin „Mangel“: „Mängel zur Beseitigung“ auf „Heute“
             und „Heute / Offen“, „Keine Mängel zur Beseitigung.“, „Mangel als beseitigt gemeldet …“, „Mangel nicht gefunden.“
    Befund   „Befund“ heißen nur die Befunde aus Einsatzberichten (Finding): Schritt „Befunde“ der Berichtsseite, „Noch offen“, „Befund nicht
             gefunden.“
1.9.68 hatte auch die Mängel der Abnahme in den Monteursansichten „Befund“ genannt (Entscheidung E) -- in der Nachrunde korrigiert.
"""

from app import defects
from app.findings import create_finding
from app.routers import field_defects
from app.routers.pages import router as pages_router
from app.service_reports import create_report, list_inspection_items, update_inspection_item
from tests.test_v213_inspection_items import TINY_PNG
from tests.test_v464_noch_offen import bericht  # noqa: F401  (Fixture: Rapport mit Vorlage)
from tests.vorlagen_js import seitentext


def test_heute_zeile_maengel_zur_beseitigung():
    text, _ = seitentext("mobil.html")
    assert "offenZeile('Mängel zur Beseitigung',o.maengel)" in text and "Befunde zur Beseitigung" not in text


def test_offen_ueberschrift_und_meldungen_sagen_mangel(threaded_db_session, router_test_client):
    """Angriff auf die Benennung: „Heute / Offen“ zeigt der Monteurin die Mängel der Abnahme als „Mängel zur Beseitigung“ -- nirgends
    „Befund“ für sie."""
    html = router_test_client(threaded_db_session, pages_router, role="field").get("/mobil/offen").text
    assert '<h2 id="maengelTitel">Mängel zur Beseitigung</h2>' in html
    assert "'Keine Mängel zur Beseitigung.'" in html and "'Mangel als beseitigt gemeldet – das Büro prüft die Abnahme der Beseitigung.'" in html
    assert 'alt="Foto zum Mangel"' in html
    assert "Befunde zur Beseitigung" not in html and "Befund als beseitigt" not in html and "Foto zum Befund" not in html


def test_meldungen_des_monteurswegs_sagen_mangel():
    assert field_defects.NOT_FOUND == "Mangel nicht gefunden."
    quelle = open(defects.__file__, encoding="utf-8").read()
    teil = quelle[quelle.index("def report_remedied("):]
    assert "bei der der Mangel festgehalten wurde" in teil[:teil.index("\ndef ")]


def test_befund_im_einsatzbericht_bleibt_befund(bericht):  # noqa: F811
    """Gegenstück: der Befund eines Einsatzberichts heißt weiter „Befund“ -- in „Noch offen“ und in der Meldung zu einem fremden Befund."""
    db, client, r = bericht
    gully = next(i for i in list_inspection_items(db, r["id"]) if i["text"] == "Gully 1: Ablauf frei und funktionsfähig")
    update_inspection_item(db, gully["id"], {"result": "nok"})
    offen = client.get(f"/api/service-reports/{r['id']}/noch-offen").json()["offen"]
    assert any(t.startswith("Befund zum Prüfpunkt „Gully 1") for t in offen) and not any("Mangel" in t for t in offen)
    anderer = create_report(db, r["order_id"], "rapport", description="anderer Bericht")
    fremd = create_finding(db, anderer["id"], "Riss", "mittel", "sofort_behoben")
    antwort = client.post(f"/api/service-reports/{r['id']}/photos", data={"finding_id": str(fremd["id"]), "kind": "allgemein"},
                          files={"file": ("foto.png", TINY_PNG, "image/png")})
    assert (antwort.status_code, antwort.json()["detail"]) == (400, "Befund nicht gefunden.")
    seite, _ = seitentext("service_report.html")
    assert "{key:'befunde',name:'Befunde'}" in seite and "Mangel" not in seite
