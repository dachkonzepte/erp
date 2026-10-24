"""Seit 1.9.36 (Stufe 4, R1, Punkt 4): Einsatzbericht -- die Pflichten vor jeder Unterschrift, Pflichtpunkte bleiben.

    Noch offen     app/service_reports.py::noch_offen(): genau die Pflichten, die sign_report() seit 1.2.16/1.2.17 prüft (Pflichtpunkt
                   beantwortet, Mangel zu negativem Ergebnis, Foto je Mangel, Wiedervorlage bei zurückgestellt) -- je Eintrag mit Namen;
                   GET /api/service-reports/{id}/noch-offen liefert die Liste (die Seite fragt vor jeder Unterschrift), die Unterschrift
                   lehnt mit 409 „Noch offen: …“ ab, vor jeder Prüfung der Bilder (bis 1.9.35 400 mit Zahlen, nach der Bildprüfung)
    Pflichtpunkt   lässt sich nicht löschen (409); seit 1.9.41 gilt das für jeden Punkt aus der Vorlage, löschbar ist nur ein von Hand
                   ergänzter (tests/test_v469_vorlagenpunkte.py)
    Rapport        ein Rapportbericht mit Prüfvorlage trägt seine Vorlage an der Dachfläche (roof_areas[].inspection_template_id) -- die
                   Seite zeigt daran seine Prüfpunkte (bis 1.9.35 nur Wartung oder die alte Spalte inspection_template_id)
"""

import base64

import pytest

from app.routers.inspection_templates import router as inspection_templates_router
from app.routers.service_reports import router as service_reports_router
from app.roof_areas import create_roof_area, create_roof_component
from app.service_reports import (
    NochOffen, add_inspection_item, create_report, list_inspection_items, noch_offen, sign_report, update_inspection_item,
)
from tests.test_v213_inspection_items import TINY_PNG, _make_order_for_report, _seed_test_template
from tests.test_v202_maintenance_contracts import make_customer_and_property
from tests.vorlagen_js import seitentext

PNG = base64.b64encode(TINY_PNG).decode()
UNTERSCHRIFT = {"installer_signature_png_base64": PNG, "installer_signature_name": "Mia Monteurin",
                "customer_signature_png_base64": PNG, "customer_signature_name": "Bernd Bauherr"}


@pytest.fixture
def bericht(threaded_db_session, router_test_client):
    """Rapportbericht mit ausdrücklich gewählter Prüfvorlage (Flachdach, ein Gully)."""
    db = threaded_db_session
    vorlage = _seed_test_template(db)
    _, prop = make_customer_and_property(db)
    area = create_roof_area(db, prop.id, "Hauptdach", roof_type="Flachdach")
    create_roof_component(db, area["id"], "Gully 1", component_type="Gully", sort_order=10)
    order = _make_order_for_report(db, prop)
    client = router_test_client(db, service_reports_router, inspection_templates_router)
    antwort = client.post(f"/api/orders/{order.id}/service-reports",
                          json={"report_type": "rapport", "roof_area_ids": [area["id"]], "inspection_template_id": vorlage["id"]})
    assert antwort.status_code == 200, antwort.text
    return db, client, antwort.json()


def _beantworten(db, report_id, ausser=()):
    for item in list_inspection_items(db, report_id):
        if item["required"] and item["text"] not in ausser:
            update_inspection_item(db, item["id"], {"result": "ok", "condition_grade": 1})


def test_rapport_mit_vorlage_traegt_sie_an_der_dachflaeche(bericht):
    db, client, r = bericht
    assert r["report_type"] == "rapport" and r["inspection_template_id"] is None  # die alte Spalte bleibt leer (seit 1.2.22)
    assert [a["inspection_template_id"] is not None for a in r["roof_areas"]] == [True]
    pflicht = [i["text"] for i in list_inspection_items(db, r["id"]) if i["required"]]
    assert "Zugang und Absturzsicherung geprüft" in pflicht and len(pflicht) == 4


def test_bericht_nennt_was_noch_offen_ist(bericht):
    db, client, r = bericht
    assert r["noch_offen"] == [
        "Pflichtpunkt „Zugang und Absturzsicherung geprüft“ beantworten", "Pflichtpunkt „Gesamtzustand Dachfläche“ beantworten",
        "Pflichtpunkt „Gully 1: Ablauf frei und funktionsfähig“ beantworten",
        "Pflichtpunkt „Abdichtung auf Blasen, Risse, Falten“ beantworten"]
    assert client.get(f"/api/service-reports/{r['id']}/noch-offen").json()["offen"] == r["noch_offen"]  # seit 1.9.66 dazu eintraege


def test_unterschrift_mit_offenem_pflichtpunkt_abgelehnt(bericht):
    """Angriff: ein Pflichtpunkt offen -- 409, der Punkt steht mit Namen in der Liste, der Bericht bleibt Entwurf."""
    db, client, r = bericht
    _beantworten(db, r["id"], ausser=("Gesamtzustand Dachfläche",))
    antwort = client.post(f"/api/service-reports/{r['id']}/sign", json=UNTERSCHRIFT)
    assert antwort.status_code == 409
    assert antwort.json() == {"detail": "Noch offen: Pflichtpunkt „Gesamtzustand Dachfläche“ beantworten",
                              "offen": ["Pflichtpunkt „Gesamtzustand Dachfläche“ beantworten"]}
    assert client.get(f"/api/orders/{r['order_id']}/service-reports").json()[0]["status"] == "entwurf"


def test_unterschrift_erledigt_ok(bericht):
    """Gegenprobe: alle Pflichtpunkte beantwortet -- unterschrieben, nichts mehr offen."""
    db, client, r = bericht
    _beantworten(db, r["id"])
    assert client.get(f"/api/service-reports/{r['id']}/noch-offen").json() == {"offen": [], "eintraege": []}
    antwort = client.post(f"/api/service-reports/{r['id']}/sign", json=UNTERSCHRIFT)
    assert antwort.status_code == 200, antwort.text
    assert (antwort.json()["status"], antwort.json()["noch_offen"]) == ("unterschrieben", [])


def test_pflichten_vor_der_pruefung_der_bilder(bericht):
    """Ein offener Pflichtpunkt geht vor: auch mit unbrauchbaren Unterschriften 409 mit der Liste (bis 1.9.35 zuerst die Bilder)."""
    db, client, r = bericht
    antwort = client.post(f"/api/service-reports/{r['id']}/sign", json={**UNTERSCHRIFT, "customer_signature_png_base64": "kaputt"})
    assert antwort.status_code == 409 and len(antwort.json()["offen"]) == 4


def test_alle_vier_pflichten_mit_namen(bericht):
    """Dieselben vier Pflichten wie bisher, je mit Namen: negatives Ergebnis ohne Mangel, Mangel ohne Foto, zurückgestellt ohne Datum."""
    from app.findings import create_finding
    from app.models import Finding

    db, client, r = bericht
    _beantworten(db, r["id"])
    gully = next(i for i in list_inspection_items(db, r["id"]) if i["text"] == "Gully 1: Ablauf frei und funktionsfähig")
    update_inspection_item(db, gully["id"], {"result": "nok"})
    # seit 1.9.66 „Befund“ statt „Mangel“ (Stufe 4, R4, Entscheidung E)
    assert noch_offen(_bericht(db, r["id"])) == ["Befund zum Prüfpunkt „Gully 1: Ablauf frei und funktionsfähig“ erfassen (negatives Ergebnis)"]
    mangel = create_finding(db, r["id"], "Gully verstopft", "mittel", "sofort_behoben", inspection_item_id=gully["id"])
    assert noch_offen(_bericht(db, r["id"])) == ["Foto zum Befund „Gully verstopft“ aufnehmen"]
    zeile = db.get(Finding, mangel["id"])
    zeile.action = "zurueckgestellt"
    db.commit()
    with pytest.raises(NochOffen) as fehler:
        sign_report(db, r["id"], installer_signature_png_bytes=TINY_PNG, installer_signature_name="Mia",
                    customer_signature_png_bytes=TINY_PNG, customer_signature_name="Bernd")
    assert fehler.value.offen == ["Foto zum Befund „Gully verstopft“ aufnehmen",
                                  "Wiedervorlagedatum zum zurückgestellten Befund „Gully verstopft“ angeben"]


def _bericht(db, report_id):
    from app.service_reports import get_report_row
    db.expire_all()
    return get_report_row(db, report_id)


def test_pflichtpunkt_loeschen_abgelehnt(bericht):
    db, client, r = bericht
    pflicht = next(i for i in list_inspection_items(db, r["id"]) if i["required"])
    antwort = client.delete(f"/api/inspection-items/{pflicht['id']}")
    assert (antwort.status_code, antwort.json()["detail"]) == (409, "Ein Prüfpunkt aus der Vorlage lässt sich nicht löschen – trifft er nicht zu, „Entfällt“ wählen.")  # seit 1.9.41 jeder Punkt aus der Vorlage
    assert any(i["id"] == pflicht["id"] for i in list_inspection_items(db, r["id"]))


def test_freier_punkt_loeschen_ok(bericht):
    """Seit 1.9.41: ein freier Punkt aus der Vorlage bleibt (409) / Gegenprobe: ein von Hand ergänzter lässt sich löschen (bis 1.9.40
    ließ sich auch der freie Punkt aus der Vorlage löschen)."""
    db, client, r = bericht
    frei = next(i for i in list_inspection_items(db, r["id"]) if not i["required"])
    assert client.delete(f"/api/inspection-items/{frei['id']}").status_code == 409
    eigener = add_inspection_item(db, r["id"], "Dachluke geprüft", "ja_nein")
    assert client.delete(f"/api/inspection-items/{eigener['id']}").status_code == 200


def test_unterschriebener_bericht_hat_nichts_offen(threaded_db_session, router_test_client):
    db = threaded_db_session
    order = _make_order_for_report(db)
    r = create_report(db, order.id, "rapport", description="Dach kontrolliert")
    sign_report(db, r["id"], installer_signature_png_bytes=TINY_PNG, installer_signature_name="Mia",
                customer_signature_png_bytes=TINY_PNG, customer_signature_name="Bernd")
    client = router_test_client(db, service_reports_router)
    assert client.get(f"/api/service-reports/{r['id']}/noch-offen").json() == {"offen": [], "eintraege": []}


def test_seite_fragt_vor_der_unterschrift_und_loeschen_nur_am_eigenen_punkt():
    """Strukturprüfung der Berichtsseite (seit 1.9.67 service_report.html; bis 1.9.66 je Bericht auf der Seite des Auftrags mit zwei
    Unterschriftsschritten): vor „Bericht abschließen“ wartet sie das Speichern der Seite ab und fragt …/noch-offen frisch -- steht dort
    etwas, geht nichts hinaus; „Prüfpunkt löschen“ nur an einem von Hand ergänzten Punkt; ob es Prüfpunkte gibt, sagt der Server
    (hat_pruefpunkte, auch bei einer Vorlage an der Fläche)."""
    text, _ = seitentext("service_report.html")
    abschluss = text[text.index("async function berichtAbschliessen("):text.index("aktion('abschliessen',berichtAbschliessen)")]
    laden = text[text.index("function nochOffenLaden("):text.index("// --- Inhalt je Schritt")]
    assert "api('/api/service-reports/'+REPORT_ID+'/noch-offen')" in laden
    assert abschluss.index("await nachDemSpeichern();await nochOffenLaden()") < abschluss.index("abschliessen('bericht'")
    assert "if((OFFEN.eintraege||[]).length){abschlussZeichnen();return}" in abschluss
    # seit 1.9.41 nur an einem von Hand ergänzten Punkt (ohne template_item_id), seit 1.9.67 im Menü „⋮“ des Punkts
    assert ("(p.template_item_id==null?'<button type=\"button\" class=\"ds-menue-eintrag ds-menue-eintrag-fehler\" "
            "data-klick=\"punkt-loeschen\"") in text
    assert "key:R.hat_pruefpunkte?'pruefpunkte':'arbeiten'" in text
