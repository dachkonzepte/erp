"""Seit 1.9.10 (Stufe 2 „Rahmen“, Runde 5): Seitenkopf der Gruppe „Datensatz mit Pfad“ (befund-rahmen.md, K3) -- Objekt, Dachfläche,
Betriebsmittel, Wartungsvertrag, Checklisten-Vorlage, Prüfvorlage, Einsatzbericht.

    Pfad-Links     jedes Ziel im Pfad -- fest im call-Block der Seite oder im Skript (seitenkopf({pfad: […]})) -- ist eine Seitenroute
                   und öffnet sich (200) für die schwächste Rolle, die die Seite sieht (Büro – Auftrag; „/mobil“ für die Monteurin)
    Rückwege       der Pfad schließt die fehlenden Rückwege aus bildgrundlage/pruefung/ablaeufe.md, soweit sie diese Seiten betreffen:
                   Wartungsvertrag -> Wartungen, Einsatzbericht -> Projektmappe und Wartungsvertrag, Einsatzbericht (Monteurin) ->
                   /mobil, Prüfvorlage -> Einstellungen; bestehende Rückwege bleiben (Kunde, Objekt, Auftrag, Vorlagenliste)
    Löschen        nur im Menü „⋮“ (Eintrag in der Fehlerfarbe), mit derselben Rückfrage wie bisher (confirm in der Funktion, die
                   der Eintrag aufruft)
    verborgen      ds.css hält einen verborgenen Knopf oder Menüeintrag verborgen ([hidden] gegen das display der Klasse)

Im Browser prüft das scripts/klicktest_rahmen.py, Teil „datensatzkopf“ (jeder Link im Pfad je Rolle mit echten Daten geöffnet).
"""

import re

import pytest

from app.design_dateien import STATIC_DIR
from app.routers.pages import router as pages_router
from tests import vorlagen_js as vj
from tests.test_v441_rahmen_baustein import DATENSATZ_MIT_PFAD

# je Seite: was der Pfad mindestens enthält (Muster wie die Routen, {x} = eingesetzte ID)
RUECKWEGE = {
    "property.html": {"/master-data", "/customers/{x}"},
    "roof_area.html": {"/master-data", "/customers/{x}", "/properties/{x}"},
    "operational_asset.html": {"/master-data", "/master-data#assets"},
    "maintenance_contract.html": {"/maintenance-contracts", "/customers/{x}", "/properties/{x}"},
    "checklist_template.html": {"/checklisten", "/checklisten/vorlagen"},
    "inspection_template.html": {"/settings", "/inspection-templates"},
    "service_reports.html": {"/projects", "/customers/{x}", "/projects/{x}", "/maintenance-contracts/{x}", "/orders/{x}", "/mobil"},
    # seit 1.9.67 der Bericht: bis zur Seite des Auftrags (Einsatzberichte), für die Monteurin Heute / Auftrag
    "service_report.html": {"/projects", "/customers/{x}", "/projects/{x}", "/maintenance-contracts/{x}", "/orders/{x}",
                            "/orders/{x}/service-reports", "/mobil"},
    # seit 1.9.13 die Rechnung (ersetzt „← Auftrag“)
    "invoice_detail.html": {"/projects", "/customers/{x}", "/projects/{x}", "/orders/{x}"},
    # seit 1.9.18 das Angebot (ersetzt die Brotkrume Kunde · Projekt · Nummer)
    "quote_editor.html": {"/projects", "/customers/{x}", "/projects/{x}"},
    # seit 1.9.24 die Arbeitsvorbereitung (ersetzt „← Auftrag“ und „Projektmappe“)
    "work_preparation.html": {"/projects", "/customers/{x}", "/projects/{x}", "/orders/{x}"},
}
MIT_LOESCHEN = {"roof_area.html", "operational_asset.html", "maintenance_contract.html", "checklist_template.html",
                "service_report.html"}  # seit 1.9.67, Rückfrage auf der Seite (48-px-Knöpfe) statt confirm()


def _call_block(name: str) -> str:
    text = (vj.TEMPLATES / name).read_text(encoding="utf-8")
    bloecke = re.findall(r"\{%\s*call\(teil\)\s*seitenkopf\(.*?\{%\s*endcall\s*%\}", text, flags=re.S)
    assert len(bloecke) == 1, name
    return bloecke[0]


def _teil(block: str, teil: str) -> str:
    m = re.search(r'teil == "' + teil + r'" %\}(.*?)(?=\{%\s*(?:elif|endif) teil|\{%\s*elif|\{%\s*endcall)', block, flags=re.S)
    return m.group(1) if m else ""


def pfad_ziele(name: str) -> set[str]:
    """Ziele der Pfad-Links: fest im call-Block (vor dem Laden) und im Skript (nach dem Laden)."""
    return feste_pfad_ziele(name) | skript_pfad_ziele(name)


def feste_pfad_ziele(name: str) -> set[str]:
    """Ziele der Links, die fest im call-Block stehen (href="…") -- der Pfad vor dem Laden."""
    return set(re.findall(r'href="([^"]+)"', _teil(_call_block(name), "pfad")))


def skript_pfad_ziele(name: str) -> set[str]:
    """Ziele der Glieder {text: …, href: …} im Skript (href '…', '…'+id oder `…${id}`) -- im Aufruf von seitenkopf() oder vorher gebaut
    (Einsatzbericht: je nach Rolle). seitenkopf({pfad}) ersetzt den ganzen Pfad: was nach dem Laden gilt, steht hier."""
    ziele = set()
    a = vj.analysieren(vj.eigene_skripte(name))
    schluessel = lambda k: a.t[k].art == "name" and a.t[k + 1].wert == ":" and a.t[k + 1].art == "punct"  # noqa: E731
    for k in range(len(a.t) - 3):
        if schluessel(k) and a.t[k].wert == "href" and a.eltern[k] >= 0 and a.t[a.eltern[k]].wert == "{":
            obj = a.eltern[k]
            if not any(schluessel(j) and a.t[j].wert == "text" and a.eltern[j] == obj for j in range(obj + 1, a.partner[obj])):
                continue
            wert = a.t[k + 2]
            if wert.art == "str":
                ziel = wert.wert + ("{x}" if a.t[k + 3].wert == "+" else "")
            elif wert.art == "tpl":
                # der Tokenizer zerlegt `/a/${x}/b` in tpl '/a/', ( x ), tpl '/b' -- jedem ${…} folgt ein Stück, auch ein leeres
                ziel, j = wert.wert, k + 2
                while a.t[j + 1].wert == "(" and a.t[j + 1].art == "punct" and a.t[a.partner[j + 1] + 1].art == "tpl":
                    j = a.partner[j + 1] + 1
                    ziel += "{x}" + a.t[j].wert
            else:
                ziel = "?"
            ziele.add(ziel)
    return ziele


def _seitenrouten() -> list[re.Pattern]:
    return [re.compile("^" + re.sub(r"\{[^}]+\}", "[^/]+", r.path) + "$") for r in pages_router.routes if "GET" in getattr(r, "methods", ())]


@pytest.mark.parametrize("name", sorted(RUECKWEGE))
def test_pfad_schliesst_die_rueckwege(name):
    """Der Pfad nach dem Laden (seitenkopf() ersetzt den festen ganz) enthält die Rückwege; was vor dem Laden fest dasteht, gehört dazu."""
    nach_dem_laden = skript_pfad_ziele(name)
    assert RUECKWEGE[name] <= nach_dem_laden, sorted(RUECKWEGE[name] - nach_dem_laden)
    assert feste_pfad_ziele(name) <= nach_dem_laden, sorted(feste_pfad_ziele(name) - nach_dem_laden)


@pytest.mark.parametrize("name", sorted(DATENSATZ_MIT_PFAD))
def test_menueeintraege_verborgen_ueber_hidden(name):
    """Ein Eintrag im Menü „⋮“, der nicht gilt, trägt hidden (dsMenue() überspringt ihn auch per Tastatur) -- nie die Klasse .hidden,
    die ihn nur unsichtbar machte."""
    text = (vj.TEMPLATES / name).read_text(encoding="utf-8")
    ids = re.findall(r'class="ds-menue-eintrag[^"]*"[^>]*\bid="([^"]+)"|\bid="([^"]+)"[^>]*class="ds-menue-eintrag', _teil(_call_block(name), "menue"))
    falsch = [i for paar in ids for i in paar if i and re.search(
        r"getElementById\('" + re.escape(i) + r"'\)\.classList\.(?:add|remove|toggle)\('hidden'", text)]
    assert falsch == [], (name, falsch)


@pytest.mark.parametrize("name", sorted(RUECKWEGE))
def test_jedes_pfad_ziel_ist_eine_seitenroute(name):
    routen = _seitenrouten()
    falsch = [z for z in pfad_ziele(name) if not any(r.match(z.replace("{x}", "1").split("#")[0].split("?")[0]) for r in routen)]
    assert falsch == []


@pytest.fixture
def seiten_mit_modulen(monkeypatch):
    from app.routers.pages import templates
    monkeypatch.setitem(templates.env.globals, "is_module_enabled", lambda key: True)


@pytest.mark.parametrize("name", sorted(RUECKWEGE))
def test_jeder_pfad_link_oeffnet_eine_seite(name, threaded_db_session, router_test_client, seiten_mit_modulen):
    """Büro – Auftrag (die schwächste Rolle, die diese Seiten sieht) öffnet jedes Ziel; „/mobil“ öffnet die Monteurin (nur ihr Pfad)."""
    buero = router_test_client(threaded_db_session, pages_router, role="buero_auftrag")
    monteur = router_test_client(threaded_db_session, pages_router, role="field")
    for ziel in sorted(pfad_ziele(name)):
        adresse = ziel.replace("{x}", "1").split("#")[0]
        r = (monteur if adresse == "/mobil" else buero).get(adresse, follow_redirects=False)
        assert r.status_code == 200 and r.headers["content-type"].startswith("text/html"), (name, ziel, r.status_code)


@pytest.mark.parametrize("name", sorted(RUECKWEGE))
def test_loeschen_nur_im_menue_mit_rueckfrage(name):
    block = _call_block(name)
    text = (vj.TEMPLATES / name).read_text(encoding="utf-8")
    ausserhalb = text.replace(block, "")
    assert not re.search(r">\s*Löschen\s*</button>", _teil(block, "aktion") + _teil(block, "pfad")), name
    if name not in MIT_LOESCHEN:
        assert "Löschen" not in block, name
        return
    eintrag = re.search(r'<button type="button" class="ds-menue-eintrag ds-menue-eintrag-fehler"[^>]*data-klick="loeschen"[^>]*>Löschen</button>',
                        _teil(block, "menue"))
    assert eintrag, name
    # die Aktion ruft die bisherige Löschfunktion, die vor dem Löschen fragt -- mit confirm() oder (seit 1.9.67, Monteursrahmen) der
    # Rückfrage auf der Seite
    funktion = re.search(r"aktion\('loeschen',\(\)=>(\w+)\(\)\)", ausserhalb).group(1)
    rumpf = re.search(r"async function " + funktion + r"\(\)\{(.*?)\n\}", ausserhalb, flags=re.S).group(1)
    assert re.match(r"\s*if\(!(?:confirm\('[^']+'\)|await rueckfrage\([^\n]*\))\)return;", rumpf), (name, funktion)


def test_ds_css_haelt_verborgene_knoepfe_und_eintraege_verborgen():
    css = (STATIC_DIR / "ds" / "ds.css").read_text(encoding="utf-8")
    assert re.search(r"\.ds-knopf\[hidden\],\s*\.ds-menue-eintrag\[hidden\]\s*\{\s*display:\s*none;\s*\}", css)


def test_scanner_liest_template_literale_ganz(tmp_path, monkeypatch):
    """Seit 1.9.13: ein Ziel als Template-Literal zählt ganz (bis 1.9.12 las der Scanner nur das Stück vor dem ersten ${…})."""
    (tmp_path / "a.html").write_text(
        "<script>seitenkopf({pfad:[{text:'A',href:`/a/${x.id}/b`},{text:'B',href:`/c/${y}`},{text:'C',href:'/d/'+z},"
        "{text:'D',href:`/e`}]});</script>", encoding="utf-8")
    monkeypatch.setattr(vj, "TEMPLATES", tmp_path)
    assert skript_pfad_ziele("a.html") == {"/a/{x}/b", "/c/{x}", "/d/{x}", "/e"}
