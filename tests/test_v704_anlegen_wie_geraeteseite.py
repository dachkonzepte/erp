"""Version 1.9.304 (Nachrunde der Geräte-Runde, Punkt 4): „Betriebsmittel anlegen“ sieht aus wie die Seite des Geräts.

    Aufbau          Beschriftung über dem Feld, zwei Spalten (unter 900 px eine) -- bis 1.9.303 links beschriftet wie die übrigen Stammdaten
    Reihenfolge     wie auf der Seite des Geräts (Karte „Stammdaten“): Bezeichnung, Typ, Hersteller, Modell, Kennzeichen / Seriennummer, Betriebsmittelnummer
                    (optional), Status, Im Einsatzbericht auswählbar, Notizen, Bedienungshinweise, Haken „Auf der Plantafel einplanbar“; darunter der Abschnitt
                    „Plantafel“ mit Überschrift und Linie, dann die Dokumente
    neu im Anlegen  „Im Einsatzbericht auswählbar“ (Vorgabe Nein) und „Bedienungshinweise“, gespeichert mit dem Gerät
    nur hier        die übrigen Formulare der Stammdaten bleiben links beschriftet
Im Browser: scripts/klicktest_geraete.py (Beschriftungen beider Seiten verglichen, über dem Feld, Spalten bei 1440, 1280 und 412 px, gespeichert).
"""

import re
from pathlib import Path

from app.routers.operational_assets import router as asset_router

ROOT = Path(__file__).resolve().parent.parent
FORM = ROOT / "app/templates/master_data_form.html"
GERAET = ROOT / "app/templates/operational_asset.html"


def _beschriftungen(markup: str) -> list[str]:
    """Die Texte der Beschriftungen in ihrer Reihenfolge -- ohne Tags, ohne Eingabefelder im Label, Leerraum zusammengefasst."""
    texte = []
    for inhalt in re.findall(r"<label\b[^>]*>(.*?)</label>", markup, flags=re.S):
        text = re.sub(r"<[^>]+>", "", inhalt)
        texte.append(" ".join(text.split()))
    return texte


def _anlegen() -> str:
    form = FORM.read_text(encoding="utf-8")
    start = form.index("function assetForm(){")
    return form[start:form.index("\n", start)]


def test_reihenfolge_und_beschriftungen_wie_die_seite_des_geraets():
    geraet = GERAET.read_text(encoding="utf-8")
    stammdaten = geraet[geraet.index("<h2>Stammdaten</h2>"):geraet.index('<section class="plantafel-abschnitt"')]
    anlegen = _anlegen()
    angaben = anlegen[anlegen.index("el('form').innerHTML=`"):anlegen.index('<section class="plantafel-abschnitt"')]
    erwartet = ["Bezeichnung *", "Typ *", "Hersteller", "Modell", "Kennzeichen / Seriennummer", "Betriebsmittelnummer (optional)", "Status",
                "Im Einsatzbericht auswählbar", "Notizen", "Bedienungshinweise (für Monteure sichtbar, z. B. Kurzanleitung, Sicherheitshinweise)",
                "Auf der Plantafel einplanbar"]
    assert _beschriftungen(stammdaten) == erwartet
    assert _beschriftungen(angaben) == erwartet


def test_abschnitt_plantafel_und_dokumente_darunter():
    anlegen = _anlegen()
    abschnitt = ('<section class="plantafel-abschnitt" id="assetPlantafel" aria-labelledby="assetPlantafelTitel" hidden><h3 id="assetPlantafelTitel">Plantafel</h3>'
                 '<div class="felder-oben"><div class="field full" id="assetVerknuepfenWrap">')
    assert abschnitt in anlegen
    assert anlegen.index(abschnitt) < anlegen.index('<div class="felder-oben dokumente"><div class="field full"><label>Dokumente')


def test_beschriftung_oben_zwei_spalten_nur_im_anlegen():
    form = FORM.read_text(encoding="utf-8")
    for regel in (".felder-oben{display:grid;grid-template-columns:1fr 1fr;gap:10px}",
                  ".felder-oben .field{display:block;padding:0;border-bottom:none}",
                  ".felder-oben .field>label{padding-top:0;font-size:12.5px;font-weight:650;margin-bottom:5px}",
                  ".felder-oben .check{display:flex;",  # das Häkchen neben seiner Beschriftung (sonst überstimmt display:block der Felder)
                  ".plantafel-abschnitt{margin-top:14px;padding-top:12px;border-top:1px solid var(--line)}.plantafel-abschnitt h3{margin:0 0 10px;font-size:14px}",
                  "@media(max-width:900px){.felder-oben{grid-template-columns:1fr}}"):
        assert regel in form, regel
    # die übrigen Formulare der Stammdaten bleiben links beschriftet
    assert ".field{display:grid;grid-template-columns:170px minmax(0,1fr);" in form
    ausserhalb = form.replace(_anlegen(), "")
    assert 'class="felder-oben' not in ausserhalb.split("</style>", 1)[1]
    assert "plantafel-anlegen" not in form and "abschnitt-titel" not in form  # die Klassen von 1.9.298 sind weg


def test_speichern_mit_den_beiden_neuen_feldern():
    form = FORM.read_text(encoding="utf-8")
    assert ("notes:n(v('assetNotes')),usage_notes:n(v('assetUsageNotes')),selectable_in_reports:v('assetSelectable')==='1',"
            "active:v('assetActiveSelect')==='1'}") in form
    assert '<select id="assetSelectable"><option value="0">Nein</option><option value="1">Ja</option></select>' in _anlegen()  # Vorgabe Nein


def test_die_schnittstelle_speichert_beide(threaded_db_session, router_test_client):
    c = router_test_client(threaded_db_session, asset_router)
    r = c.post("/api/operational-assets", json={"name": "Minibagger", "asset_type": "Maschine", "usage_notes": "Nur mit Einweisung",
                                                "selectable_in_reports": True, "active": True})
    assert r.status_code == 200, r.text
    gespeichert = c.get(f"/api/operational-assets/{r.json()['id']}").json()
    assert (gespeichert["usage_notes"], gespeichert["selectable_in_reports"]) == ("Nur mit Einweisung", True)
