"""Seit 1.9.23 (Stufe 2, Runde 9, Punkt 1; ersetzt Festlegung 1.9.22 Nr. 5): „Abbrechen“ auf den Formularseiten (Stammdaten-Formular,
Leistung) fragt „Änderungen verwerfen?“, aber nur, wenn es ungespeicherte Änderungen gibt.

    Seitenskript   die vom Server gezeichnete Seite läuft in node (tests/gerenderte_seite.py) mit init() bis zum Ende; danach wird der
                   Klick auf „Abbrechen“ (data-klick="abbrechen", _aktionen.html) ausgelöst -- ohne Änderung keine Frage und der Link
                   folgt seinem Ziel, nach einer Änderung die Frage: abgelehnt bleibt die Seite (preventDefault), bestätigt geht sie
                   weiter; mit Strg/Cmd (neuer Tab) keine Frage
    zählt mit      vorgemerkte Zeilen, die erst das Speichern schickt (Material einer neuen Leistung, Dokumente eines neuen
                   Betriebsmittels); nicht: die Felder, über die man eine Zeile erst hinzufügt (data-ohne-stand)
    vor dem Laden  vor dem Ende von init() fragt „Abbrechen“ nie (kein Stand zum Vergleichen)

Bis 1.9.22 gab es keine Frage (Festlegung 1.9.22 Nr. 5): dort scheitert dieser Test (keine Aktion „abbrechen“). Im Browser prüft das
scripts/klicktest_rahmen.py, Teil „formularseiten“.
"""

import re

import pytest

from tests import vorlagen_js as vj
from tests.gerenderte_seite import gerenderte_seite
from tests.test_v334_auswahl_restfaelle import im_browser, nur_mit_node

# Klick auf „Abbrechen“ nachstellen: das Element mit data-klick="abbrechen" und ein Ereignis, das preventDefault mitzählt
KLICK = """
const _rueckfragen = [];
let _antwort = false;
confirm = t => { _rueckfragen.push(t); return _antwort; };
function abbrechenKlicken(tasten = {}) {
  const ev = {...tasten, verhindert: false, preventDefault() { this.verhindert = true; }};
  window._dkAktionen.click.abbrechen(_element('abbrechenLink'), ev);
  return {verhindert: ev.verhindert, fragen: _rueckfragen.splice(0)};
}
"""


def _seite(router_test_client, threaded_db_session, adresse):
    from app.routers.pages import router as pages_router

    antwort = router_test_client(threaded_db_session, pages_router, role="buero_finanzen").get(adresse)
    assert antwort.status_code == 200
    assert 'data-klick="abbrechen"' in antwort.text, "„Abbrechen“ ohne Aktion -- es fragt nie"
    return gerenderte_seite(antwort.text, "init().catch(")


@nur_mit_node
def test_stammdaten_formular_fragt_nur_bei_aenderungen(router_test_client, threaded_db_session):
    skript = _seite(router_test_client, threaded_db_session, "/master-data/suppliers/new")
    ablauf = KLICK + """
      // die Felder unter #form (die Attrappe kennt kein HTML-Gerüst): zwei Felder des Formulars
      _element('form').querySelectorAll = () => [_element('supplierNumber'), _element('name')];
      const vor_dem_laden = (_element('name').value = 'x', abbrechenKlicken());
      _element('name').value = '';
      await init();
      const ohne = abbrechenKlicken();
      _element('name').value = 'Dachbaustoffe Nord';
      const abgelehnt = abbrechenKlicken();
      _antwort = true;
      const bestaetigt = abbrechenKlicken();
      _antwort = false;
      const neuer_tab = abbrechenKlicken({ctrlKey: true});
      _element('name').value = '';
      const zurueck = abbrechenKlicken();
      return {vor_dem_laden, ohne, abgelehnt, bestaetigt, neuer_tab, zurueck};
    """
    r = im_browser(skript, ablauf)["ergebnis"]
    assert r["vor_dem_laden"] == {"verhindert": False, "fragen": []}
    assert r["ohne"] == {"verhindert": False, "fragen": []}
    assert r["abgelehnt"] == {"verhindert": True, "fragen": ["Änderungen verwerfen?"]}
    assert r["bestaetigt"] == {"verhindert": False, "fragen": ["Änderungen verwerfen?"]}
    assert r["neuer_tab"] == {"verhindert": False, "fragen": []}
    assert r["zurueck"] == {"verhindert": False, "fragen": []}  # zurückgeändert = wie geladen


@nur_mit_node
def test_neue_leistung_material_zaehlt_die_suche_nicht(router_test_client, threaded_db_session):
    skript = _seite(router_test_client, threaded_db_session, "/services/new")
    ablauf = KLICK + """
      ANTWORTEN['/api/calculation-settings'] = {labor_rate: '82.00', material_markup_pct: '0', overhead_pct: '0', risk_profit_pct: '0'};
      ANTWORTEN['/api/settings/option-groups/service_types'] = {options: []};
      _element('materialSearch').dataset.ohneStand = '';
      _element('editableArea').querySelectorAll = () => [_element('shortText'), _element('unit'), _element('materialSearch')];
      await init();
      const ohne = abbrechenKlicken();
      _element('materialSearch').value = 'Bahn';
      const suche = abbrechenKlicken();
      materialRows.push({materialId: 7, quantity: 2, wastePct: 0});
      const material = abbrechenKlicken();
      materialRows.pop();
      _element('shortText').value = 'Rinne reinigen';
      const feld = abbrechenKlicken();
      return {ohne, suche, material, feld};
    """
    r = im_browser(skript, ablauf)["ergebnis"]
    assert r["ohne"] == {"verhindert": False, "fragen": []}
    assert r["suche"] == {"verhindert": False, "fragen": []}
    assert r["material"] == {"verhindert": True, "fragen": ["Änderungen verwerfen?"]}
    assert r["feld"] == {"verhindert": True, "fragen": ["Änderungen verwerfen?"]}


@pytest.mark.parametrize("name,wurzel", [("master_data_form.html", "el('form')"), ("service_form.html", "el('editableArea')")])
def test_stand_nach_dem_laden_der_felder_des_formulars(name, wurzel):
    """Der Stand wird am Ende von init() gemerkt -- über die Felder des Formulars, nicht über die ganze Seite (dort stünde auch die Suche
    der Kopfzeile); die Hilfsfelder zum Hinzufügen tragen data-ohne-stand."""
    text = (vj.TEMPLATES / name).read_text(encoding="utf-8")
    assert vj.bindet_ein(name, "_abbrechen.html") and vj.bindet_ein(name, "_aktionen.html")
    skript = vj.eigene_skripte(name).text
    rumpf = skript[skript.index("async function init()"):]
    rumpf = rumpf[:rumpf.index("\n}\n") if name == "service_form.html" else rumpf.index("}\nasync function save(")]
    assert re.search(r"abbrechenEinrichten\(" + re.escape(wurzel) + r",", rumpf.splitlines()[-1]), "nicht am Ende von init()"
    hilfen = {"master_data_form.html": ("assetDocType", "assetDocFile", "assetDocNotes"),
              "service_form.html": ("materialSearch", "materialPick", "materialQty", "materialWaste")}[name]
    for feld in hilfen:
        assert re.search(r'id="' + feld + r'"[^>]*\bdata-ohne-stand\b', text), feld
