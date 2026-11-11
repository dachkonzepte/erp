"""Version 1.9.305 (L2a, Vorweg -- Frage 1 der Nachrunde der Geräte-Runde): ein Rest wieder verknüpfen, einen Rest ohne alles löschen.

    verknüpfen   die Auswahl „Vorhandenes Plantafel-Gerät verknüpfen“ (Seite des Geräts und „Betriebsmittel anlegen“) bietet jedes freie Gerät an, auch ein
                 inaktives -- mit „(inaktiv)“; so kommt der Rest vom Entfernen des Hakens wieder an sein Betriebsmittel. Gespeichert gilt der Status des
                 Betriebsmittels für beides (Antwort 3 der Geräte-Runde). Bis 1.9.304 nur aktive.
    löschbar     GET /api/resources (und jede Antwort mit einem Gerät) sagt je Gerät „loeschbar“: kein Betriebsmittel, kein Postfach und nichts, was
                 ressource_in_gebrauch() prüft (Kolonne, AV, Einsatz, Termin) -- eine Abfrage je Tabelle, nicht je Gerät
    Löschen      die Liste der Betriebsmittel zeigt an einer Zeile „nur Plantafel“ nur dann „Löschen“; nach Rückfrage DELETE /api/resources/{id}
Im Browser: scripts/klicktest_geraete.py (der Rest des Krans wieder am Kran, „Löschen“ der Hebebühne).
"""

import ast
import json
import re
from pathlib import Path

import pytest
from sqlalchemy import event, select

from app.models import OperationalResource, Team, TeamResource
from app.routers.operational_assets import router as asset_router
from app.routers.resource_planning import router as resource_router
from tests.test_v399_teil_updates_geld import im_browser, nur_mit_node
from tests.test_v696_ein_speicherweg import _einsatz
from tests.test_v697_ein_formular import FREI, OHNE, _zustand

ROOT = Path(__file__).resolve().parent.parent
LISTE = ROOT / "app/templates/master_data.html"
FORM = ROOT / "app/templates/master_data_form.html"


@pytest.fixture()
def welt(threaded_db_session, router_test_client):
    db = threaded_db_session
    return {"db": db, "c": router_test_client(db, asset_router, resource_router)}


def _geraet(c, name: str, **werte) -> int:
    r = c.post("/api/resources", json={"name": name, "resource_type": "Maschine", **werte})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _loeschbar(c) -> dict:
    return {g["name"]: g["loeschbar"] for g in c.get("/api/resources").json()}


# --- Server: löschbar ---------------------------------------------------------------------------------------------------------------------

def test_loeschbar_nur_ohne_alles(welt):
    db, c = welt["db"], welt["c"]
    nichts = _geraet(c, "Nichts")
    _geraet(c, "Inaktiv", active=False)
    kolonne, postfach, einsatz = _geraet(c, "Kolonne"), _geraet(c, "Postfach"), _geraet(c, "Einsatz")
    bm = c.post("/api/operational-assets", json={"einplanbar": True, "name": "Betriebsmittel", "asset_type": "Maschine"}).json()
    team = Team(name="Nord")
    db.add(team)
    db.flush()
    db.add(TeamResource(team_id=team.id, resource_id=kolonne))
    db.get(OperationalResource, postfach).outlook_mailbox = "geraet@example.test"
    db.commit()
    _einsatz(db, einsatz, -10)  # auch ein vergangener Einsatz hängt am Gerät
    assert _loeschbar(c) == {"Nichts": True, "Inaktiv": True, "Kolonne": False, "Postfach": False, "Einsatz": False, "Betriebsmittel": False}
    # dieselbe Angabe in der Antwort eines einzelnen Geräts, beim Anlegen und Ändern
    assert c.get(f"/api/resources/{nichts}").json()["loeschbar"] is True
    assert c.get(f"/api/resources/{bm['resource_id']}").json()["loeschbar"] is False
    assert c.put(f"/api/resources/{postfach}", json={"kurzname": "PF"}).json()["loeschbar"] is False
    # gelöscht wird, was löschbar ist; was in Gebrauch ist, nur deaktiviert (wie bisher)
    assert c.delete(f"/api/resources/{nichts}").json() == {"deleted": True}
    assert c.delete(f"/api/resources/{einsatz}").json() == {"deleted": False, "deactivated": True}


def test_eine_abfrage_je_tabelle_nicht_je_geraet(welt):
    db, c = welt["db"], welt["c"]

    def abfragen() -> int:
        zaehler = []
        bind = db.get_bind()
        hoeren = lambda *a, **k: zaehler.append(1)  # noqa: E731
        event.listen(bind, "before_cursor_execute", hoeren)
        try:
            assert c.get("/api/resources").status_code == 200
        finally:
            event.remove(bind, "before_cursor_execute", hoeren)
        return len(zaehler)

    for i in range(2):
        _geraet(c, f"G{i}")
    zwei = abfragen()
    for i in range(2, 8):
        _geraet(c, f"G{i}")
    assert abfragen() == zwei


def test_dieselben_tabellen_wie_in_gebrauch_und_das_betriebsmittel():
    baum = ast.parse((ROOT / "app/operational_assets.py").read_text(encoding="utf-8"))
    tabellen = {}
    for f in baum.body:
        if isinstance(f, ast.FunctionDef) and f.name in ("ressource_in_gebrauch", "loeschbare_ressourcen"):
            tupel = [n for n in ast.walk(f) if isinstance(n, ast.Tuple) and all(isinstance(e, ast.Name) for e in n.elts) and len(n.elts) >= 5]
            assert len(tupel) == 1, f.name
            tabellen[f.name] = {e.id for e in tupel[0].elts}
    assert tabellen["loeschbare_ressourcen"] == tabellen["ressource_in_gebrauch"] | {"OperationalAsset"}
    quelltext = (ROOT / "app/operational_assets.py").read_text(encoding="utf-8")
    assert 'frei = {rid for rid, postfach in db.execute(abfrage) if not (postfach or "").strip()}' in quelltext  # ohne Postfach


# --- Seite des Geräts: auch ein inaktives freies -------------------------------------------------------------------------------------------

REST = {**FREI, "id": 11, "name": "Autokran", "resource_type": "Kran", "active": False}


@nur_mit_node
def test_seite_des_geraets_bietet_den_rest_an():
    danach = ("_element('editEinplanbar').checked = true; plantafelZeigen();"
              "return [_element('verknuepfenWrap').hidden, _element('editVerknuepfen').innerHTML];")
    # nur der inaktive Rest frei: die Auswahl erscheint, mit „(inaktiv)“
    versteckt, optionen = _zustand(OHNE, [REST], True, danach)
    assert versteckt is False and _texte(optionen) == ["— neues Plantafel-Gerät —", "Kran · Autokran (inaktiv)"]
    # ein vergebenes zählt weiter nicht
    assert _zustand(OHNE, [{**REST, "taken": True}], True, danach)[0] is True
    assert _texte(_zustand(OHNE, [FREI, REST], True, danach)[1]) == ["— neues Plantafel-Gerät —", "Kran · Anhänger Humbaur", "Kran · Autokran (inaktiv)"]


def _texte(html: str) -> list[str]:
    return re.findall(r"<option[^>]*>([^<]*)</option>", html)


# --- Betriebsmittel anlegen: dieselbe Auswahl ----------------------------------------------------------------------------------------------

@nur_mit_node
def test_anlegen_bietet_den_rest_an():
    auswahl = "\n".join(re.findall(r"<script>(.*?)</script>", (ROOT / "app/templates/_auswahl.html").read_text(encoding="utf-8"), flags=re.S))
    vorbereitung = (auswahl + "\n"
                    + f"var assetResources = {json.dumps([FREI, REST, {**REST, 'id': 12, 'name': 'Vergeben', 'taken': True}])};")
    ablauf = "AUFRUFE.push(assetVerknuepfenOptionen(null)); AUFRUFE.push(assetVerknuepfenOptionen(11));"
    leer, gewaehlt = im_browser("master_data_form.html", ["assetVerknuepfenOptionen"], vorbereitung, ablauf)
    assert ">Kran · Autokran (inaktiv)</option>" in leer and "Vergeben" not in leer and ">Kran · Anhänger Humbaur</option>" in leer
    assert '<option value="11" selected>Kran · Autokran (inaktiv)</option>' in gewaehlt
    form = FORM.read_text(encoding="utf-8")
    assert "const frei=assetResources.filter(x=>!x.taken);" in form and "el('assetVerknuepfenWrap').hidden=!frei.length;" in form


# --- Liste: „Löschen“ nur, wenn nichts daran hängt -----------------------------------------------------------------------------------------

def test_liste_loeschen_nur_wenn_loeschbar():
    liste = LISTE.read_text(encoding="utf-8")
    assert ("""Betriebsmittel anlegen</a>${r.loeschbar?`<br><a class="link" href="#" data-klick="geraetLoeschen" data-id="${r.id}" """
            """data-name="${esc(r.name)}">Löschen</a>`:''}</td></tr>`));""") in liste
    start = liste.index("aktion('geraetLoeschen'")
    rumpf = liste[start:liste.index("\n", start)]
    assert "if(!confirm(`Plantafel-Gerät „${el.dataset.name}“ löschen? An ihm hängt nichts mehr.`))return;" in rumpf
    assert "api('/api/resources/'+Number(el.dataset.id),{method:'DELETE'})" in rumpf and "{neuLaden:geraeteNeuLaden}" in rumpf
    assert "if(!r.deleted)alert('Inzwischen hängt etwas an dem Gerät -- es bleibt deaktiviert.')" in rumpf


@nur_mit_node
def test_loeschen_fragt_und_sendet_genau_das_geraet():
    vorbereitung = ("var resources = [], assets = [], GERENDERT = 0; function render(){ GERENDERT++; }\n"
                    "var BESTAETIGT = true; confirm = m => { AUFRUFE.push({frage: m}); return BESTAETIGT; };\n"
                    "ANTWORT = (url, methode) => methode === 'DELETE' ? {deleted: true} : [];\n"
                    "var _AKTIONEN = {}; function aktion(name, fn){ _AKTIONEN[name] = fn; }\n"
                    + LISTE.read_text(encoding="utf-8").split("\n")[[i for i, z in enumerate(LISTE.read_text(encoding='utf-8').split('\n'))
                                                                       if z.startswith("aktion('geraetLoeschen'")][0]])
    el = "{dataset: {id: '7', name: 'Hebebühne JLG'}}"
    ablauf = (f"await _AKTIONEN.geraetLoeschen({el}, {{preventDefault(){{}}}}); BESTAETIGT = false;"
              f"await _AKTIONEN.geraetLoeschen({el}, {{preventDefault(){{}}}});")
    aufrufe = im_browser("master_data.html", ["geraeteNeuLaden"], vorbereitung, ablauf)
    fragen = [a["frage"] for a in aufrufe if "frage" in a]
    assert fragen == ["Plantafel-Gerät „Hebebühne JLG“ löschen? An ihm hängt nichts mehr."] * 2
    assert [(a["methode"], a["url"]) for a in aufrufe if a.get("methode") == "DELETE"] == [("DELETE", "/api/resources/7")]  # abgelehnt: nichts gesendet
