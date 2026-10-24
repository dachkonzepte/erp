"""Seit 1.9.66 (Stufe 4, R4 Fortsetzung): die Regeln des Berichts für die Seite in fünf Schritten (Server).

    Beschreibung  Rapportbericht ohne Prüfvorlage (Schritt 1 „Arbeiten“): „Durchgeführte Arbeiten beschreiben“ steht unter „Noch offen“ und
                  sperrt die Unterschrift, solange die Beschreibung leer ist (Entscheidung B); Wartung und Rapport mit Vorlage brauchen sie
                  nicht (app/service_reports.py::hat_pruefpunkte())
    Art           änderbar nur, solange der Bericht leer ist -- keine Antwort, kein Befund, kein Material, kein Betriebsmittel, keine
                  Beschreibung, kein Foto (bericht_leer()); danach 409 „… Entwurf löschen und neu anlegen.“ (Entscheidung C)
    Teil-Update   PUT /api/service-reports/{id} übernimmt nur die gesendeten Felder (Beschreibung allein, Datum allein), Regel 22
    Ein Bericht   GET /api/service-reports/{id} für die Berichtsseite: die Monteurin nur ihren eigenen, das Büro mit office_hint
    Noch offen    je Schritt (arbeiten, pruefpunkte, befunde); „Befund“ statt „Mangel“ (Entscheidung E)
"""

from datetime import timedelta

import pytest

from app.findings import create_finding
from app.operational_assets import create_asset
from app.routers.service_reports import router as service_reports_router
from app.service_reports import (
    ART_FEST, add_asset_usage, add_material, add_photo, create_report, get_report_row, list_inspection_items, update_inspection_item,
)
from tests.test_v213_inspection_items import TINY_PNG
from tests.test_v464_noch_offen import UNTERSCHRIFT, bericht  # noqa: F401  (Fixture: Rapport mit Vorlage)
from tests.test_v471_heute_server import _einsatz, welt  # noqa: F401  (Fixture)


def _rapport_ohne_vorlage(client, order_id, **mehr):
    antwort = client.post(f"/api/orders/{order_id}/service-reports", json={"report_type": "rapport", **mehr})
    assert antwort.status_code == 200, antwort.text
    return antwort.json()


def _buero(w):
    return w["client"](w["db"], service_reports_router, role="admin")


# --- B: Beschreibung beim Rapport ohne Vorlage ------------------------------------------------------------------------------------------

def test_rapport_ohne_vorlage_ohne_beschreibung_gesperrt_mit_beschreibung_frei(welt):  # noqa: F811
    """Angriff: Rapport ohne Vorlage und ohne Beschreibung -> „Noch offen“ nennt sie (Schritt arbeiten), die Unterschrift 409; nur Leerzeichen
    zählen nicht. Gegenprobe: mit Beschreibung nichts offen, die Unterschrift geht durch."""
    client = _buero(welt)
    r = _rapport_ohne_vorlage(client, welt["order"].id)
    assert (r["hat_pruefpunkte"], r["noch_offen"]) == (False, ["Durchgeführte Arbeiten beschreiben"])
    assert r["noch_offen_je_schritt"] == [{"text": "Durchgeführte Arbeiten beschreiben", "schritt": "arbeiten"}]
    assert client.get(f"/api/service-reports/{r['id']}/noch-offen").json() == {
        "offen": ["Durchgeführte Arbeiten beschreiben"], "eintraege": [{"text": "Durchgeführte Arbeiten beschreiben", "schritt": "arbeiten"}]}
    gesperrt = client.post(f"/api/service-reports/{r['id']}/sign", json=UNTERSCHRIFT)
    assert (gesperrt.status_code, gesperrt.json()["offen"]) == (409, ["Durchgeführte Arbeiten beschreiben"])
    assert client.put(f"/api/service-reports/{r['id']}", json={"description": "   "}).json()["noch_offen"] == ["Durchgeführte Arbeiten beschreiben"]
    ausgefuellt = client.put(f"/api/service-reports/{r['id']}", json={"description": "Rinne gereinigt, Ablauf frei"})
    assert (ausgefuellt.status_code, ausgefuellt.json()["noch_offen"]) == (200, [])
    frei = client.post(f"/api/service-reports/{r['id']}/sign", json=UNTERSCHRIFT)
    assert (frei.status_code, frei.json()["status"]) == (200, "unterschrieben")


def test_wartung_braucht_keine_beschreibung(welt):  # noqa: F811
    client = _buero(welt)
    wartung = client.post(f"/api/orders/{welt['order'].id}/service-reports", json={"report_type": "wartung"}).json()
    assert (wartung["hat_pruefpunkte"], wartung["noch_offen"]) == (True, [])


def test_rapport_mit_vorlage_braucht_keine_beschreibung(bericht):  # noqa: F811
    _, _, mit_vorlage = bericht
    assert mit_vorlage["hat_pruefpunkte"] is True and "Durchgeführte Arbeiten beschreiben" not in mit_vorlage["noch_offen"]


# --- C: Art nur, solange der Bericht leer ist --------------------------------------------------------------------------------------------

def test_art_aendern_leer_geht(bericht):  # noqa: F811
    _, client, r = bericht
    assert r["art_aenderbar"] is True
    antwort = client.put(f"/api/service-reports/{r['id']}", json={"report_type": "wartung"})
    assert (antwort.status_code, antwort.json()["report_type"]) == (200, "wartung")


@pytest.mark.parametrize("eingabe", ["antwort", "beschreibung", "befund", "material", "betriebsmittel", "foto"])
def test_art_aendern_nicht_leer_abgelehnt(bericht, eingabe):  # noqa: F811
    """Angriff: nach je einer Eingabe (Antwort, Beschreibung, Befund, Material, Betriebsmittel, Foto) die Art ändern -> 409 mit dem Hinweis,
    nichts geändert; dieselbe Art noch einmal geschickt geht durch."""
    db, client, r = bericht
    punkt = list_inspection_items(db, r["id"])[0]
    if eingabe == "antwort":
        update_inspection_item(db, punkt["id"], {"result": "ok"})
    elif eingabe == "beschreibung":
        client.put(f"/api/service-reports/{r['id']}", json={"description": "Dach begangen"})
    elif eingabe == "befund":
        create_finding(db, r["id"], "Riss an der Attika", "mittel", "sofort_behoben")
    elif eingabe == "material":
        add_material(db, r["id"], description="Dichtband", quantity=2, unit="m")
    elif eingabe == "betriebsmittel":
        add_asset_usage(db, r["id"], asset_id=create_asset(db, {"name": "Kran", "selectable_in_reports": True})["id"])
    else:
        add_photo(db, r["id"], TINY_PNG, "foto.png", inspection_item_id=punkt["id"])
    db.expire_all()
    assert client.get(f"/api/service-reports/{r['id']}").json()["art_aenderbar"] is False
    abgelehnt = client.put(f"/api/service-reports/{r['id']}", json={"report_type": "wartung"})
    assert (abgelehnt.status_code, abgelehnt.json()["detail"]) == (409, ART_FEST)
    assert "Entwurf löschen und neu anlegen" in ART_FEST
    db.expire_all()
    assert get_report_row(db, r["id"]).report_type == "rapport"
    assert client.put(f"/api/service-reports/{r['id']}", json={"report_type": "rapport"}).status_code == 200


def test_art_wechsel_legt_pruefpunkte_wie_beim_anlegen(bericht):  # noqa: F811
    """Rapport ohne Vorlage -> Wartung: die Vorlage des Dachtyps an der Fläche, ihre Punkte da, Schritt 1 „Prüfpunkte“; zurück zum Rapport:
    ohne Vorlage und ohne Punkte, die Beschreibung wieder Pflicht (wie beim Anlegen mit dieser Art)."""
    db, client, mit_vorlage = bericht
    flaeche = mit_vorlage["roof_areas"][0]["roof_area_id"]
    r = client.post(f"/api/orders/{mit_vorlage['order_id']}/service-reports", json={"report_type": "rapport", "roof_area_ids": [flaeche]}).json()
    assert (r["hat_pruefpunkte"], list_inspection_items(db, r["id"])) == (False, [])
    wartung = client.put(f"/api/service-reports/{r['id']}", json={"report_type": "wartung"}).json()
    assert wartung["hat_pruefpunkte"] is True and wartung["roof_areas"][0]["inspection_template_label"] == "Testvorlage"
    assert "Ablauf frei und funktionsfähig" in " ".join(i["text"] for i in list_inspection_items(db, r["id"]))
    rapport = client.put(f"/api/service-reports/{r['id']}", json={"report_type": "rapport"}).json()
    assert (rapport["hat_pruefpunkte"], rapport["roof_areas"][0]["inspection_template_id"], list_inspection_items(db, r["id"])) == (False, None, [])
    assert rapport["noch_offen"] == ["Durchgeführte Arbeiten beschreiben"]


# --- Teil-Update -------------------------------------------------------------------------------------------------------------------------

def test_datum_allein_laesst_art_und_beschreibung(welt):  # noqa: F811
    client = _buero(welt)
    r = _rapport_ohne_vorlage(client, welt["order"].id, description="Rinne gereinigt")
    neu = (welt["heute"] - timedelta(days=1)).isoformat()
    antwort = client.put(f"/api/service-reports/{r['id']}", json={"performed_at": neu}).json()
    assert (antwort["performed_at"], antwort["description"], antwort["report_type"]) == (neu, "Rinne gereinigt", "rapport")
    assert client.put(f"/api/service-reports/{r['id']}", json={"performed_at": None}).status_code == 422
    assert client.put(f"/api/service-reports/{r['id']}", json={"report_type": None}).status_code == 422


# --- Ein Bericht für die Berichtsseite ----------------------------------------------------------------------------------------------------

def test_ein_bericht_monteurin_nur_der_eigene_buero_mit_hinweis(welt):  # noqa: F811
    _einsatz(welt, welt["order"], [(welt["heute"] - timedelta(days=7), welt["heute"])], [welt["mia"], welt["tom"]])
    mia, tom = (welt["client"](welt["db"], service_reports_router, role="field", employee_id=e.id) for e in (welt["mia"], welt["tom"]))
    eigener = mia.post(f"/api/orders/{welt['order'].id}/service-reports", json={"report_type": "wartung"}).json()
    antwort = mia.get(f"/api/service-reports/{eigener['id']}")
    assert antwort.status_code == 200 and antwort.json()["id"] == eigener["id"] and "office_hint" not in antwort.json()
    assert tom.get(f"/api/service-reports/{eigener['id']}").status_code == 403
    buero = _buero(welt).get(f"/api/service-reports/{eigener['id']}")
    assert buero.status_code == 200 and "office_hint" in buero.json()
    assert _buero(welt).get("/api/service-reports/999999").status_code == 404


# --- E: „Befund“ statt „Mangel“ ----------------------------------------------------------------------------------------------------------

def test_noch_offen_je_schritt_mit_befund(bericht):  # noqa: F811
    db, client, r = bericht
    for item in list_inspection_items(db, r["id"]):
        if item["required"]:
            update_inspection_item(db, item["id"], {"result": "ok", "condition_grade": 1})
    gully = next(i for i in list_inspection_items(db, r["id"]) if i["text"] == "Gully 1: Ablauf frei und funktionsfähig")
    update_inspection_item(db, gully["id"], {"result": "nok"})
    assert client.get(f"/api/service-reports/{r['id']}/noch-offen").json()["eintraege"] == [
        {"text": "Befund zum Prüfpunkt „Gully 1: Ablauf frei und funktionsfähig“ erfassen (negatives Ergebnis)", "schritt": "pruefpunkte"}]
    create_finding(db, r["id"], "Gully verstopft", "mittel", "sofort_behoben", inspection_item_id=gully["id"])
    assert client.get(f"/api/service-reports/{r['id']}/noch-offen").json()["eintraege"] == [
        {"text": "Foto zum Befund „Gully verstopft“ aufnehmen", "schritt": "befunde"}]
