"""Version 1.9.303 (Nachrunde der Geräte-Runde, Punkt 3): die Büro-Suche findet auch Plantafel-Geräte ohne Betriebsmittel („nur Plantafel“).

    Gruppe   „Betriebsmittel“, hinter den Betriebsmitteln; Ziel „Betriebsmittel anlegen“ mit dem Gerät (/master-data/assets/new?ressource=<id>)
    Felder   Bezeichnung, Typ, Hersteller, Modell, Kennzeichen, Kurzname -- wie bei den Betriebsmitteln
    Zeile    Untertitel „nur Plantafel“ bzw. „nur Plantafel · inaktiv“, dann Typ, Hersteller, Modell, Kennzeichen
    Zahl     die Gesamtzahl der Gruppe zählt beide; ein Gerät mit Betriebsmittel steht nur einmal da (als Betriebsmittel)
    Modul    bei ausgeschaltetem Modul keine Gruppe (wie bisher)
Im Browser: scripts/klicktest_geraete.py (Seite „Suche“, Klick führt ins Anlegen).
"""

from app.models import EnabledModule, OperationalAsset, OperationalResource
from app.search import search_office
from tests.test_v276_operational_assets import db_session


def _gruppe(db, wort: str, *, limit: int | None = None) -> dict | None:
    gruppen = search_office(db, "admin", wort, **({"limit_per_type": limit} if limit else {}))
    return next((g for g in gruppen if g["key"] == "operational_assets"), None)


def _bestand(db):
    kran = OperationalResource(name="Autokran", resource_type="Kran", manufacturer="Liebherr", kurzname="Kran", active=False)  # Rest: Haken entfernt
    hub = OperationalResource(name="Hubsteiger Genie", resource_type="Maschine", identifier="Z-45", kurzname="Hub", active=True)
    pritsche = OperationalResource(name="Pritsche", resource_type="Fahrzeug", kurzname="HS 202", active=True)
    db.add_all([kran, hub, pritsche])
    db.flush()
    db.add_all([OperationalAsset(resource_id=pritsche.id), OperationalAsset(name="Autokran", asset_type="Kran", manufacturer="Liebherr")])
    db.commit()
    return kran, hub, pritsche


def test_findet_nur_plantafel_mit_ziel_anlegen():
    db = db_session()
    kran, hub, _ = _bestand(db)
    g = _gruppe(db, "Autokran")
    assert g["label"] == "Betriebsmittel" and g["total"] == 2
    assert [(h["title"], h["subtitle"], h["url"].split("/")[1]) for h in g["hits"]] == [
        ("Autokran", "Kran · Liebherr", "betriebsmittel"),  # das Betriebsmittel zuerst
        ("Autokran", "nur Plantafel · inaktiv · Kran · Liebherr", "master-data"),
    ]
    assert g["hits"][1]["url"] == f"/master-data/assets/new?ressource={kran.id}"
    hub_g = _gruppe(db, "Z-45")
    assert [(h["title"], h["subtitle"], h["url"]) for h in hub_g["hits"]] == [
        ("Hubsteiger Genie", "nur Plantafel · Maschine · Z-45", f"/master-data/assets/new?ressource={hub.id}")]


def test_dieselben_felder_wie_bei_den_betriebsmitteln():
    db = db_session()
    _, hub, _ = _bestand(db)
    for wort in ("Hubsteiger", "Maschine", "Z-45", "Hub"):
        assert [h["url"] for h in _gruppe(db, wort)["hits"]] == [f"/master-data/assets/new?ressource={hub.id}"], wort


def test_geraet_mit_betriebsmittel_nur_einmal():
    db = db_session()
    _bestand(db)
    g = _gruppe(db, "HS 202")
    assert g["total"] == 1 and [h["url"].split("/")[1] for h in g["hits"]] == ["betriebsmittel"]


def test_grenze_je_gruppe_zaehlt_beide():
    db = db_session()
    for i in range(3):
        db.add(OperationalAsset(name=f"Leiter {i}"))
        db.add(OperationalResource(name=f"Leiterwagen {i}", resource_type="Anhänger"))
    db.commit()
    g = _gruppe(db, "Leiter", limit=4)
    assert g["total"] == 6 and len(g["hits"]) == 4
    assert [h["url"].split("/")[1] for h in g["hits"]] == ["betriebsmittel"] * 3 + ["master-data"]


def test_modul_aus_keine_gruppe():
    db = db_session()
    _bestand(db)
    db.add(EnabledModule(module_key="betriebsmittel", enabled=False))
    db.commit()
    assert _gruppe(db, "Hubsteiger") is None
