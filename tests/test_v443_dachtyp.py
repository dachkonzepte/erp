"""Stufe 2, Runde 4, Punkt 1 (1.9.6): Dachtyp -- Altwerte bleiben sichtbar und erhalten (Befund in docs/archiv/redesign.md, "Punkt 2:
Befund Dachtyp").

    a) Editor einer Prüfvorlage: ein Wert außerhalb der Auswahlliste bleibt vorgewählt ("… (nicht mehr verfügbar)", wie die Dachfläche)
       und geht beim Speichern des Kopfs unverändert zurück -- bis 1.9.5 stand die Auswahl auf "— jeder Dachtyp —", das Speichern löschte
       den Wert still.
    b) Liste der Prüfvorlagen: der gespeicherte Wert, wie er steht; ein Wert, den kein aktiver Eintrag der Auswahlliste genau so trägt,
       mit Marke "nicht mehr verfügbar" (deaktivierter Eintrag: "inaktiv", wie im Editor) -- 1.9.3 bis 1.9.5 schrieb die Liste ihn in die
       Bezeichnung um (auch bei anderer Schreibweise).
    c) Testdaten der Bildgrundlage: Dachtypen nur aus der Auswahlliste, ein Altwert als eigener, erklärter Fall (DACHTYP_ALTWERT).
Die Seiten laufen in node mit den Antworten des echten Dienstes (tests/test_v334_auswahl_restfaelle.py: seite(), im_browser())."""

import ast
import json
from pathlib import Path

import pytest

from tests.test_v334_auswahl_restfaelle import im_browser, nur_mit_node, seite

ROOT = Path(__file__).resolve().parent.parent


def _antworten(db, router_test_client, *vorlagen):
    """Auswahlliste "Dachtypen" (Grunddaten; "Terrasse" deaktiviert) und die Prüfvorlagen, wie der Dienst sie liefert."""
    from app.inspection_templates import create_template
    from app.models import SettingOption, SettingOptionGroup
    from app.routers.inspection_templates import router as vorlagen_router
    from app.routers.settings import router as settings_router

    gruppe = db.query(SettingOptionGroup).filter_by(group_key="roof_types").one()
    db.query(SettingOption).filter_by(group_id=gruppe.id, value="Terrasse").one().active = False
    db.commit()
    ids = [create_template(db, label, roof_type=dachtyp)["id"] for label, dachtyp in vorlagen]
    client = router_test_client(db, settings_router, vorlagen_router)
    return (client.get("/api/settings/option-groups/roof_types").json(), client.get("/api/inspection-templates").json(),
            [client.get(f"/api/inspection-templates/{i}").json() for i in ids])


@nur_mit_node
@pytest.mark.parametrize("gespeichert,soll_text", [
    ("flachdach", "flachdach (nicht mehr verfügbar)"),   # andere Schreibweise
    ("Pultdach", "Pultdach (nicht mehr verfügbar)"),     # kein Eintrag (umbenannt oder gelöscht)
    ("Terrasse", "Terrasse (inaktiv)"),                  # Eintrag deaktiviert
    ("Flachdach", "Flachdach"),
])
def test_editor_behaelt_den_gespeicherten_dachtyp(threaded_db_session, router_test_client, gespeichert, soll_text):
    gruppe, _, (vorlage,) = _antworten(threaded_db_session, router_test_client, ("Wartung", gespeichert))
    ablauf = f"""
      roofTypes = {json.dumps(gruppe["options"])};
      template = {json.dumps(vorlage)};
      fillMetaForm();
      const gewaehlt = _gewaehlt('editRoofType');
      _element('editLabel').value = 'Wartung neu';
      await saveTemplateMeta();
      const put = AUFRUFE.find(a => a.methode === 'PUT');
      return {{gewaehlt: gewaehlt && [gewaehlt.value, gewaehlt.text], gesendet: put && put.body.roof_type,
               leer: _element('editRoofType').options[0].text}};"""
    ergebnis = im_browser(seite("inspection_template.html", "init();"), ablauf)["ergebnis"]
    assert ergebnis == {"gewaehlt": [gespeichert, soll_text], "gesendet": gespeichert, "leer": "— jeder Dachtyp —"}


@nur_mit_node
def test_editor_ohne_dachtyp_bleibt_jeder_dachtyp(threaded_db_session, router_test_client):
    gruppe, _, (vorlage,) = _antworten(threaded_db_session, router_test_client, ("Allgemein", None))
    ablauf = f"""
      roofTypes = {json.dumps(gruppe["options"])}; template = {json.dumps(vorlage)}; fillMetaForm();
      await saveTemplateMeta();
      return [_gewaehlt('editRoofType').value, AUFRUFE.find(a => a.methode === 'PUT').body.roof_type];"""
    ergebnis = im_browser(seite("inspection_template.html", "init();"),
                          ablauf)["ergebnis"]
    assert ergebnis == ["", None]


@nur_mit_node
def test_liste_zeigt_den_gespeicherten_wert_und_markiert_altwerte(threaded_db_session, router_test_client):
    gruppe, vorlagen, _ = _antworten(threaded_db_session, router_test_client, ("A Flachdach", "Flachdach"), ("B klein", "flachdach"),
                                     ("C Pult", "Pultdach"), ("D Terrasse", "Terrasse"), ("E ohne", None))
    ablauf = f"""
      roofTypes = {json.dumps(gruppe["options"])}; templates = {json.dumps(vorlagen)};
      renderRows();
      return _element('templateRows').innerHTML;"""
    html = im_browser(seite("inspection_templates.html", "init();"),
                      ablauf)["ergebnis"]
    zeilen = {z.split("</b>")[0].rsplit(">", 1)[-1]: z for z in html.split("<tr")[1:]}
    marke = "nicht mehr verfügbar"
    zelle = {name: z.split("<td>")[2].split("</td>")[0] for name, z in zeilen.items()}
    assert zelle["A Flachdach"] == "Flachdach"
    assert zelle["B klein"].startswith("flachdach ") and marke in zelle["B klein"]      # nicht in "Flachdach" umgeschrieben
    assert zelle["C Pult"].startswith("Pultdach ") and marke in zelle["C Pult"]
    assert zelle["D Terrasse"].startswith("Terrasse ") and ">inaktiv<" in zelle["D Terrasse"]  # deaktiviert: wie im Editor „inaktiv“
    assert zelle["E ohne"] == "jeder Dachtyp"


def _dachtypen_der_auswahlliste() -> set[str]:
    from app.option_settings import DEFAULT_OPTION_GROUPS
    return {wert for _, _, wert, _ in DEFAULT_OPTION_GROUPS["roof_types"]["options"]}


def test_testdaten_der_bildgrundlage_nur_mit_gueltigen_dachtypen():
    """Jeder roof_type in den Testdaten der Bildgrundlage (Prüfvorlagen, Dachflächen) ist ein Wert der Auswahlliste -- außer genau einem
    erklärten Altwert (DACHTYP_ALTWERT, einer, der nicht in der Liste steht), an genau einer eigenen Prüfvorlage."""
    baum = ast.parse((ROOT / "scripts" / "bildgrundlage.py").read_text(encoding="utf-8"))
    gueltig = _dachtypen_der_auswahlliste()
    altwert = next((k.value.value for k in ast.walk(baum) if isinstance(k, ast.Assign) and len(k.targets) == 1
                    and isinstance(k.targets[0], ast.Name) and k.targets[0].id == "DACHTYP_ALTWERT"), None)
    assert isinstance(altwert, str) and altwert not in gueltig, altwert
    werte = [kw.value for k in ast.walk(baum) if isinstance(k, ast.Call) for kw in k.keywords if kw.arg == "roof_type"]
    assert werte, "keine Dachtypen in den Testdaten gefunden"
    literale = [w.value for w in werte if isinstance(w, ast.Constant)]
    namen = [w.id for w in werte if isinstance(w, ast.Name)]
    assert len(literale) + len(namen) == len(werte), "roof_type nur als Text oder DACHTYP_ALTWERT"
    assert [w for w in literale if w not in gueltig] == []
    assert namen == ["DACHTYP_ALTWERT"]
