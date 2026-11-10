"""Version 1.9.298 (Geräte-Runde, Punkt 3): Liste und Anlegen.

    Anlegen     „+ Hinzufügen“ (Stammdaten -> Betriebsmittel) legt mit dem Haken „Auf der Plantafel einplanbar“ auch das Plantafel-Gerät an (POST mit
                einplanbar, 1.9.296); ein freies Plantafel-Gerät lässt sich dort verknüpfen; /master-data/assets/new?ressource=<id> startet damit
    Liste       ein Gerät mit Plantafel trägt „Plantafel“ (bis 1.9.297 „Ressourcenbezug“); ein Plantafel-Gerät ohne Betriebsmittel (nur über Umwege) steht als
                „nur Plantafel“ mit „Betriebsmittel anlegen“ (Antwort 5); der Untertitel zählt es mit
    Suche       findet ein Gerät über seinen Kurznamen (N5)
    Modul aus   das Formular „Fuhrpark & Maschinen“ bleibt (/master-data/resources/…)
Im Browser: scripts/klicktest_geraete.py (Liste, „Betriebsmittel anlegen“, neues planbares Gerät, Suche, Bilder).
"""

from app.models import OperationalAsset, OperationalResource
from app.search import search_office
from tests.test_v276_operational_assets import db_session
from tests.test_v671_inaktive_mitarbeiter_ausblenden import ROOT

FORM = ROOT / "app/templates/master_data_form.html"
LISTE = ROOT / "app/templates/master_data.html"


def _treffer(db, wort: str) -> list[str]:
    gruppen = search_office(db, "admin", wort)
    return [r["title"] for g in gruppen if g["key"] == "operational_assets" for r in g["hits"]]


def test_suche_findet_den_kurznamen():
    db = db_session()
    r = OperationalResource(name="Pritsche MAN TGE", resource_type="Fahrzeug", kurzname="HS-DK 202")
    db.add(r)
    db.flush()
    db.add(OperationalAsset(resource_id=r.id))
    db.add(OperationalAsset(name="Leiter"))
    db.commit()
    assert _treffer(db, "DK 202") == ["Pritsche MAN TGE"]  # nur der Kurzname enthält „DK 202“
    assert _treffer(db, "Leiter") == ["Leiter"]


def test_anlegen_mit_haken_und_verknuepfen():
    form = FORM.read_text(encoding="utf-8")
    assert '<input id="assetEinplanbar" type="checkbox" onchange="assetPlantafelZeigen()"><label for="assetEinplanbar">Auf der Plantafel einplanbar</label>' in form
    assert "body={einplanbar,...(verkn?{resource_id:verkn}:{}),...(einplanbar?{ressource:{kurzname:n(v('assetKurzname'))}}:{})," in form
    assert "new URLSearchParams(location.search).get('ressource')" in form
    assert "function assetVerknuepfenOptionen(gewaehlt){return auswahlOptionen(assetResources,gewaehlt," in form  # die ganze Liste (Regel 22, P3)
    assert "el('assetVerknuepfenWrap').hidden=!frei.length;" in form
    assert "assetHasResource" not in form and "Mit Ressourcenbezug" not in form and "Bitte eine Ressource wählen" not in form


def test_liste_plantafel_und_nur_plantafel():
    liste = LISTE.read_text(encoding="utf-8")
    assert """${x.resource_id?' <span class="pill">Plantafel</span>':''}""" in liste and "Ressourcenbezug" not in liste
    assert "const nurPlantafel=resources.filter(r=>r.active&&!assets.some(a=>a.resource_id===r.id));" in liste
    # die Zeilen kommen in die Liste, mit der Suche der Liste gefiltert (Nachzug nach der Gegenprobe 298_4a, Regel 24)
    assert "rows=rows.concat(nurPlantafel.filter(r=>textMatch(r.name,r.resource_type,r.kurzname,r.identifier)).map(r=>" in liste
    assert '<span class="pill">nur Plantafel</span>' in liste and 'href="/master-data/assets/new?ressource=${r.id}">Betriebsmittel anlegen</a>' in liste


def test_modul_aus_bleibt_das_formular_fuhrpark():
    liste = LISTE.read_text(encoding="utf-8")
    assert "add.href='/master-data/resources/new'" in liste and 'href="/master-data/resources/${x.id}/edit">Bearbeiten</a>' in liste
    assert "function resourceForm(){" in FORM.read_text(encoding="utf-8")
