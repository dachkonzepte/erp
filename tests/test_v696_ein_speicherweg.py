"""Version 1.9.296 (Geräte-Runde, Punkt 1): ein Gerät, ein Speicherweg in einer Transaktion.

    Teil-Update   PUT /api/operational-assets/{id} übernimmt nur die gesendeten Felder (bis 1.9.295 das volle Formular, ein Altfall in BEKANNT)
    Anlegen       mit einplanbar legt POST Gerät und Plantafel-Gerät (Ressource) zusammen an -- die Identität in der Ressource, die Ressourcennummer
                  vergibt der Server („R-<id>“, Antwort 1); ohne Typ oder Bezeichnung nichts (422)
    Identität     Bezeichnung, Typ, Hersteller, Modell, Kennzeichen stehen genau einmal: mit Plantafel in der Ressource, sonst im Betriebsmittel
    Haken         setzen: eine neue Ressource mit den Werten des Geräts (sie wandern); mit resource_id ein freies vorhandenes verknüpfen (dessen Werte gelten);
                  entfernen: die Werte wandern ins Betriebsmittel, die Ressource wird gelöscht, wenn nichts an ihr hängt und sie kein Postfach hat, sonst
                  deaktiviert; steht sie auf künftigen Einsätzen, erst nach Rückfrage (409, trotzdem_entfernen) -- Antwort 4
    Status        ein Schalter für beides (Antwort 3); der Kurzname über den Teil „ressource“
    Transaktion   scheitert etwas, ist nichts gespeichert -- auch keine eben angelegte Ressource
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.berlin_time import berlin_today
from app.models import OperationalAsset, OperationalResource, Order, TeamResource
from app.planning import create_slot
from app.routers.operational_assets import router as asset_router
from tests.test_v090_planning_board import setup_order
from tests.test_v633_besetzung_je_einsatz import _person


@pytest.fixture()
def welt(threaded_db_session, router_test_client):
    db = threaded_db_session
    return {"db": db, "c": router_test_client(db, asset_router)}


def _anlegen(c, **werte):
    r = c.post("/api/operational-assets", json=werte)
    assert r.status_code == 200, r.text
    return r.json()


def _ressourcen(db):
    db.expire_all()
    return db.scalar(select(func.count()).select_from(OperationalResource))


def _einsatz(db, resource_id, tage_ab: int, laenge: int = 2, status: str | None = None, geraet_tage: list[int] | None = None):
    """ein Einsatz mit dem Gerät, tage_ab Tage ab heute (negativ = vergangen); geraet_tage: das Gerät nur an diesen Tagen (ab heute gezählt)"""
    order = setup_order(db, f"E{resource_id}{tage_ab}{status or ''}")
    start = berlin_today() + timedelta(days=tage_ab)
    slot = create_slot(db, order_id=order.id, team_id=None, employee_ids=[_person(db, f"P{resource_id}{tage_ab}{status or ''}", "Ute").id],
                       geraete=[{"resource_id": resource_id, "tage": None if geraet_tage is None else
                                 [(berlin_today() + timedelta(days=n)).isoformat() for n in geraet_tage]}], start_date=start, end_date=start + timedelta(days=laenge - 1),
                       planned_hours=Decimal("1"))
    if status:  # erst danach: an einem stornierten Auftrag legt die Plantafel keinen Einsatz an
        db.get(Order, order.id).status = status
        db.commit()
    return slot


# --- Anlegen ------------------------------------------------------------------------------------------------------------------------------

def test_anlegen_mit_haken_legt_beides_an(welt):
    db, c = welt["db"], welt["c"]
    a = _anlegen(c, einplanbar=True, name=" Pritsche HS-DK 202 ", asset_type="Fahrzeug", manufacturer="MAN", identifier="HS-DK 202",
                 asset_number="BM-7", notes="TÜV im Mai", ressource={"kurzname": " HS-DK 202 "})
    r = db.get(OperationalResource, a["resource_id"])
    assert (r.name, r.resource_type, r.manufacturer, r.identifier, r.kurzname, r.active) == ("Pritsche HS-DK 202", "Fahrzeug", "MAN", "HS-DK 202", "HS-DK 202", True)
    assert r.resource_number == f"R-{r.id}"  # intern, vom Server (Antwort 1)
    row = db.get(OperationalAsset, a["id"])
    assert (row.name, row.asset_type, row.manufacturer, row.identifier) == (None, None, None, None)  # die Identität steht nur in der Ressource
    assert (a["name"], a["einplanbar"], a["kurzname"], a["asset_number"], a["notes"]) == ("Pritsche HS-DK 202", True, "HS-DK 202", "BM-7", "TÜV im Mai")


@pytest.mark.parametrize("werte, meldung", [({"name": "Kran"}, "Typ"), ({"name": "  ", "asset_type": "Kran"}, "Bezeichnung")])
def test_anlegen_mit_haken_ohne_typ_oder_name_legt_nichts_an(welt, werte, meldung):
    db, c = welt["db"], welt["c"]
    r = c.post("/api/operational-assets", json={"einplanbar": True, **werte})
    assert r.status_code == 422 and meldung in r.text
    assert _ressourcen(db) == 0 and db.scalar(select(func.count()).select_from(OperationalAsset)) == 0  # eine Transaktion: nichts


def test_ressourcennummer_mit_zusatz_wenn_vergeben(welt):
    db, c = welt["db"], welt["c"]
    db.add(OperationalResource(name="Alt", resource_type="Kran", resource_number="R-2"))
    db.commit()
    a = _anlegen(c, einplanbar=True, name="Neu", asset_type="Kran")
    assert db.get(OperationalResource, a["resource_id"]).resource_number == "R-2-2"


def test_anlegen_ohne_haken_wie_bisher(welt):
    db, c = welt["db"], welt["c"]
    a = _anlegen(c, name="Leiter", asset_type="Leiter")
    assert a["resource_id"] is None and a["einplanbar"] is False and _ressourcen(db) == 0
    assert c.post("/api/operational-assets", json={"asset_type": "Leiter"}).status_code == 422  # ohne Bezeichnung


# --- Teil-Update, Identität, Status, Kurzname ---------------------------------------------------------------------------------------------

def test_teil_update_laesst_ungesendete_felder_stehen(welt):
    db, c = welt["db"], welt["c"]
    a = _anlegen(c, name="Leiter", usage_notes="Nur zu zweit", selectable_in_reports=True, acquisition_cost="120.00", asset_number="BM-1")
    r = c.put(f"/api/operational-assets/{a['id']}", json={"notes": "geprüft"})
    assert r.status_code == 200, r.text
    b = r.json()
    assert (b["notes"], b["usage_notes"], b["selectable_in_reports"], b["acquisition_cost"], b["asset_number"], b["name"]) == (
        "geprüft", "Nur zu zweit", True, "120.00", "BM-1", "Leiter")


def test_identitaet_mit_haken_in_der_ressource_ohne_im_betriebsmittel(welt):
    db, c = welt["db"], welt["c"]
    mit = _anlegen(c, einplanbar=True, name="Kran", asset_type="Kran")
    ohne = _anlegen(c, name="Leiter")
    assert c.put(f"/api/operational-assets/{mit['id']}", json={"name": "Kran 2", "model": "LTM 1050"}).status_code == 200
    assert c.put(f"/api/operational-assets/{ohne['id']}", json={"name": "Leiter 6 m", "model": "Alu"}).status_code == 200
    db.expire_all()
    r = db.get(OperationalResource, mit["resource_id"])
    assert (r.name, r.model, db.get(OperationalAsset, mit["id"]).name) == ("Kran 2", "LTM 1050", None)
    assert (db.get(OperationalAsset, ohne["id"]).name, db.get(OperationalAsset, ohne["id"]).model) == ("Leiter 6 m", "Alu")
    leer = c.put(f"/api/operational-assets/{mit['id']}", json={"asset_type": None})
    assert leer.status_code == 422 and "Typ" in leer.text  # ein Gerät auf der Plantafel braucht seinen Typ


def test_ein_status_fuer_beides_und_kurzname(welt):
    db, c = welt["db"], welt["c"]
    a = _anlegen(c, einplanbar=True, name="Pritsche", asset_type="Fahrzeug")
    b = c.put(f"/api/operational-assets/{a['id']}", json={"active": False, "ressource": {"kurzname": "P 1"}}).json()
    db.expire_all()
    r = db.get(OperationalResource, a["resource_id"])
    assert (b["active"], r.active, r.kurzname, b["kurzname"]) == (False, False, "P 1", "P 1")
    c.put(f"/api/operational-assets/{a['id']}", json={"active": True, "ressource": {"kurzname": "  "}})
    db.expire_all()
    assert (db.get(OperationalResource, a["resource_id"]).active, db.get(OperationalResource, a["resource_id"]).kurzname) == (True, None)


# --- Haken setzen und verknüpfen ---------------------------------------------------------------------------------------------------------

def test_haken_setzen_laesst_die_werte_wandern(welt):
    db, c = welt["db"], welt["c"]
    a = _anlegen(c, name="Minibagger", asset_type="Maschine", manufacturer="Kubota", model="U17", identifier="SN 4711", active=False)
    b = c.put(f"/api/operational-assets/{a['id']}", json={"einplanbar": True, "ressource": {"kurzname": "Bagger"}})
    assert b.status_code == 200, b.text
    db.expire_all()
    r = db.get(OperationalResource, b.json()["resource_id"])
    assert (r.name, r.resource_type, r.manufacturer, r.model, r.identifier, r.kurzname, r.active) == (
        "Minibagger", "Maschine", "Kubota", "U17", "SN 4711", "Bagger", False)  # der Status geht mit
    row = db.get(OperationalAsset, a["id"])
    assert (row.name, row.asset_type, row.manufacturer, row.model, row.identifier) == (None, None, None, None, None)


def test_haken_setzen_ohne_typ_legt_nichts_an(welt):
    db, c = welt["db"], welt["c"]
    a = _anlegen(c, name="Kleingerät")
    r = c.put(f"/api/operational-assets/{a['id']}", json={"einplanbar": True})
    assert r.status_code == 422 and "Typ" in r.text
    db.expire_all()
    assert _ressourcen(db) == 0 and db.get(OperationalAsset, a["id"]).name == "Kleingerät"  # nichts gespeichert


def test_freies_vorhandenes_geraet_verknuepfen(welt):
    db, c = welt["db"], welt["c"]
    frei = OperationalResource(name="Anhänger", resource_type="Anhänger", identifier="HS-A 1", resource_number="A-1")
    db.add(frei)
    db.commit()
    a = _anlegen(c, name="Mein Anhänger", asset_type="Sonstiges")
    b = c.put(f"/api/operational-assets/{a['id']}", json={"einplanbar": True, "resource_id": frei.id, "name": "überschreibt nichts"}).json()
    assert (b["resource_id"], b["name"], b["identifier"]) == (frei.id, "Anhänger", "HS-A 1")  # verknüpfen übernimmt das vorhandene Gerät
    andere = _anlegen(c, name="Zweites")
    r = c.put(f"/api/operational-assets/{andere['id']}", json={"einplanbar": True, "resource_id": frei.id})
    assert r.status_code == 422 and "bereits einem anderen Betriebsmittel" in r.text and "Ressource" not in r.text


# --- Haken entfernen ----------------------------------------------------------------------------------------------------------------------

def test_haken_entfernen_nirgends_benutzt_loescht_die_ressource(welt):
    db, c = welt["db"], welt["c"]
    a = _anlegen(c, einplanbar=True, name="Rüttelplatte", asset_type="Maschine", manufacturer="Wacker")
    b = c.put(f"/api/operational-assets/{a['id']}", json={"einplanbar": False})
    assert b.status_code == 200, b.text
    assert (b.json()["resource_id"], b.json()["name"], b.json()["manufacturer"]) == (None, "Rüttelplatte", "Wacker")
    assert _ressourcen(db) == 0
    row = db.get(OperationalAsset, a["id"])
    assert (row.name, row.asset_type, row.manufacturer) == ("Rüttelplatte", "Maschine", "Wacker")  # die Werte sind gewandert


@pytest.mark.parametrize("wie", ["kolonne", "postfach", "vergangener_einsatz", "stornierter_einsatz", "nur_vergangene_tage"])
def test_haken_entfernen_benutzt_deaktiviert_ohne_rueckfrage(welt, wie):
    db, c = welt["db"], welt["c"]
    a = _anlegen(c, einplanbar=True, name="Pritsche", asset_type="Fahrzeug")
    rid = a["resource_id"]
    if wie == "kolonne":
        from app.models import Team
        team = Team(name="Nord")
        db.add(team)
        db.flush()
        db.add(TeamResource(team_id=team.id, resource_id=rid))
        db.commit()
    elif wie == "postfach":
        db.get(OperationalResource, rid).outlook_mailbox = "pritsche@example.test"
        db.commit()
    elif wie == "vergangener_einsatz":
        _einsatz(db, rid, -10)
    elif wie == "nur_vergangene_tage":
        _einsatz(db, rid, -2, laenge=5, geraet_tage=[-2, -1])  # der Einsatz läuft weiter, das Gerät stand nur vorgestern und gestern
    else:
        _einsatz(db, rid, 3, status="storniert")
    b = c.put(f"/api/operational-assets/{a['id']}", json={"einplanbar": False})
    assert b.status_code == 200, b.text
    db.expire_all()
    r = db.get(OperationalResource, rid)
    assert r is not None and r.active is False and b.json()["resource_id"] is None


def test_haken_entfernen_mit_kuenftigem_einsatz_fragt_zurueck(welt):
    db, c = welt["db"], welt["c"]
    a = _anlegen(c, einplanbar=True, name="Kran", asset_type="Kran")
    rid = a["resource_id"]
    slot = _einsatz(db, rid, 2)
    r = c.put(f"/api/operational-assets/{a['id']}", json={"einplanbar": False, "notes": "x"})
    assert r.status_code == 409, r.text
    frage = r.json()["rueckfrage"]
    assert frage["art"] == "kuenftige_einsaetze" and [e["id"] for e in frage["einsaetze"]] == [slot.id] and "noch eingeplant" in frage["text"]
    db.expire_all()
    assert db.get(OperationalAsset, a["id"]).resource_id == rid and db.get(OperationalAsset, a["id"]).notes is None  # nichts gespeichert
    ok = c.put(f"/api/operational-assets/{a['id']}", json={"einplanbar": False, "trotzdem_entfernen": True})
    assert ok.status_code == 200, ok.text
    db.expire_all()
    assert db.get(OperationalResource, rid).active is False  # der Einsatz hält die Ressource: deaktiviert, nicht gelöscht


def test_aufbau():
    import inspect

    from app.operational_assets import geraet_speichern
    from tests.test_v671_inaktive_mitarbeiter_ausblenden import ROOT
    assert "commit(" not in inspect.getsource(geraet_speichern)  # eine Transaktion: es committet nur der Aufrufer
    router = (ROOT / "app/routers/operational_assets.py").read_text(encoding="utf-8")
    assert "update_asset(db, asset_id, payload.model_dump(exclude_unset=True))" in router
    assert "create_asset(db, payload.model_dump(exclude_unset=True))" in router
    bekannt = (ROOT / "tests/test_v329_update_handler_struktur.py").read_text(encoding="utf-8")
    assert '"PUT /api/operational-assets/{asset_id}":' not in bekannt
