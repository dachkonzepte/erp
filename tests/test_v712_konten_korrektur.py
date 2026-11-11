"""Version 1.9.312 (Lohn L2b, Punkt 0: Korrektur aus L2a): „Urlaub und Startwerte“ und Lohnstammdaten.

    Inaktive      „Inaktive ausblenden“ über den Lohnstammdaten und über „Urlaub und Startwerte“ -- ein Stand für beide Kästchen, Vorgabe an, gemerkt im
                  Browser (erp_lohnstammdaten_inaktive), nur Anzeige (bleibt ohne Recht zum Ändern bedienbar); die Lohnstammdaten nennen „active“
    Übertrag      2027 (erstes Jahr der Konten) ist er der Startwert „Resturlaub“ -- kein zweites Feld, am Anspruch 2027 abgelehnt (422); ab 2028 nach der
                  Vorgabe: „von Hand“ das Feld, „automatisch“ der Rest des Vorjahres (am Anspruch abgelehnt). Server und Seite rechnen dieselbe Regel.
    doppelt       ein Übertrag am Anspruch, wo er nicht gilt (Bestand vor 1.9.312), bleibt stehen: „Übertrag doppelt – prüfen“; ein Lesen und ein Speichern
                  anderer Werte löschen ihn nicht, nur „Diesen Übertrag entfernen“ (null)
    geprüft       der Haken zeigt den Stand; ein geänderter Wert nimmt ihn sichtbar heraus („Wert geändert – neu prüfen“); gesendet wird „geprüft“ nur,
                  wenn sich etwas tut
    412 px        die Werte der Konten ohne Umbruch; die erste Spalte zieht die Trennlinie zwischen den Personen selbst (außer in der letzten Zeile)
Stehende Uhr 10.11.2026 (fester_tag).
"""

import json
import re
from decimal import Decimal

import pytest

from app.lohnkonten import ERSTES_JAHR, uebertrag_quelle
from app.models import TimeTrackingSettings, Urlaubsanspruch
from app.routers import time_backoffice as backoffice_router
from tests import vorlagen_js as vj
from tests.node_lauf import node_ausfuehren
from tests.test_v224_field_view import make_employee

K = "/api/time-backoffice/konten"
MELDUNG_2027 = "Für 2027 ist der Übertrag der Startwert „Resturlaub“ – bitte dort eintragen."


@pytest.fixture
def w(threaded_db_session, router_test_client, fester_tag):
    db = threaded_db_session
    ada, ute = make_employee(db, "M-1", "Ada", "Monteurin"), make_employee(db, "M-9", "Ute", "Ehemalig")
    ute.active = False
    db.commit()
    return {"db": db, "ada": ada, "ute": ute, "client": router_test_client}


def _als(w, rolle="buero_finanzen"):
    w["db"].commit()
    return w["client"](w["db"], backoffice_router.router, role=rolle, user_id=9, display_name="Fin Finanzen")


def _anspruch(c, emp, jahr) -> dict | None:
    p = next(x for x in c.get(K).json()["personen"] if x["employee_id"] == emp.id)
    return next((a for a in p["ansprueche"] if a["jahr"] == jahr), None)


def _modus(w, modus: str) -> None:
    w["db"].get(TimeTrackingSettings, 1).urlaub_uebertrag = modus
    w["db"].commit()


# --- Server ---------------------------------------------------------------------------------------------------------------------------------

def test_quelle_je_jahr():
    assert ERSTES_JAHR == 2027
    assert [uebertrag_quelle(j, "von_hand") for j in (2026, 2027, 2028, 2030)] == ["von_hand", "startwert", "von_hand", "von_hand"]
    assert [uebertrag_quelle(j, "automatisch") for j in (2026, 2027, 2028, 2030)] == ["von_hand", "startwert", "automatisch", "automatisch"]


def test_uebertrag_2027_nur_aus_dem_startwert(w):
    c, ada = _als(w), w["ada"]
    r = c.put(f"{K}/{ada.id}/anspruch/2027", json={"uebertrag": 3})
    assert (r.status_code, r.json()["detail"]) == (422, MELDUNG_2027)
    assert w["db"].query(Urlaubsanspruch).count() == 0  # erst prüfen, dann schreiben
    assert c.put(f"{K}/{ada.id}/anspruch/2027", json={"uebertrag": None, "urlaubstage": 26}).status_code == 200  # leer geht immer
    assert c.get(K).json()["erstes_jahr"] == 2027
    assert c.put(f"{K}/{ada.id}/anspruch/2028", json={"uebertrag": 2.5}).json()["ansprueche"][1]["uebertrag_quelle"] == "von_hand"
    _modus(w, "automatisch")
    r = c.put(f"{K}/{ada.id}/anspruch/2029", json={"uebertrag": 1})
    assert (r.status_code, r.json()["detail"]) == (422, "Der Übertrag ist automatisch der Rest des Vorjahres (Einstellung „Übertrag ins Folgejahr“).")


def test_doppelt_bleibt_bis_von_hand_entfernt(w):
    db, ada = w["db"], w["ada"]
    db.add(Urlaubsanspruch(employee_id=ada.id, jahr=2027, uebertrag=Decimal("2")))  # Bestand aus der Zeit vor 1.9.312
    db.commit()
    c = _als(w)
    a = _anspruch(c, ada, 2027)
    assert (a["uebertrag"], a["uebertrag_quelle"], a["uebertrag_doppelt"]) == ("2.0", "startwert", True)
    db.expire_all()
    assert db.query(Urlaubsanspruch).one().uebertrag == Decimal("2")  # ein Lesen löscht nichts (Regel 23)
    c.put(f"{K}/{ada.id}/anspruch/2027", json={"urlaubstage": 26, "notiz": "Teilzeit"})  # andere Werte: der Übertrag bleibt
    assert _anspruch(c, ada, 2027)["uebertrag_doppelt"] is True
    a = c.put(f"{K}/{ada.id}/anspruch/2027", json={"uebertrag": None}).json()["ansprueche"][0]
    assert (a["uebertrag"], a["uebertrag_doppelt"], a["urlaubstage"], a["notiz"]) == (None, False, "26.0", "Teilzeit")
    # ab 2028 nur unter „automatisch“ doppelt
    db.add(Urlaubsanspruch(employee_id=ada.id, jahr=2028, uebertrag=Decimal("1")))
    db.commit()
    assert _anspruch(c, ada, 2028)["uebertrag_doppelt"] is False
    _modus(w, "automatisch")
    assert (_anspruch(c, ada, 2028)["uebertrag_quelle"], _anspruch(c, ada, 2028)["uebertrag_doppelt"]) == ("automatisch", True)


def test_lohnstammdaten_nennen_aktiv(w):
    zeilen = {z["employee_name"]: z["active"] for z in _als(w).get("/api/time-backoffice/payroll-employees").json()}
    assert zeilen == {"Ada Monteurin": True, "Ute Ehemalig": False}


# --- Seite in node --------------------------------------------------------------------------------------------------------------------------

def _text():
    return vj.eigene_skripte("settings.html").text


def _funktion(text: str, name: str) -> str:
    i = text.index("function " + name + "(")
    if text[i - 6:i] == "async ":
        i -= 6
    tiefe, j = 0, text.index("{", text.index(")", i))
    while True:
        tiefe += {"{": 1, "}": -1}.get(text[j], 0)
        j += 1
        if tiefe == 0:
            return text[i:j]


def _baustein(name: str) -> str:
    return "\n".join(re.findall(r"<script>(.*?)</script>", (vj.TEMPLATES / name).read_text(encoding="utf-8"), flags=re.S))


DOM = ("var EL={};function feld(id){return EL[id]||(EL[id]={id:id,value:'',checked:false,disabled:false,hidden:false,textContent:'',innerHTML:'',"
       "placeholder:'',dataset:{},getAttribute(){return null},setAttribute(){},removeAttribute(){}})}var document={getElementById(id){return feld(id)},querySelectorAll(){return []}};"
       "var SPEICHER={};var localStorage={getItem(k){return k in SPEICHER?SPEICHER[k]:null},setItem(k,w){SPEICHER[k]=String(w)}};"
       "function esc(s){return String(s??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/\"/g,'&quot;')}"
       "const v=id=>document.getElementById(id).value.trim();const setv=(id,x)=>document.getElementById(id).value=x??'';"
       "function auswahlWert(f,g){f.value=g??''}function szDatum(s){return s?s.slice(8,10)+'.'+s.slice(5,7)+'.'+s.slice(0,4):''}")


def _node(funktionen: tuple, ablauf: str, vorweg: str = ""):
    text = _text()
    js = (_baustein("_zahl.html") + "\n" + DOM + "\n" + vorweg + "\n" + "\n".join(_funktion(text, f) for f in funktionen)
          + f"\nconst ergebnis=(()=>{{{ablauf}}})();Promise.resolve(ergebnis).then(e=>process.stdout.write(JSON.stringify(e)));")
    return node_ausfuehren(js)


def test_js_quelle_wie_der_server():
    faelle = [(j, m) for j in (2026, 2027, 2028, 2031) for m in ("von_hand", "automatisch")]
    ablauf = f"return {json.dumps(faelle)}.map(([j,m])=>{{konten.vorgaben.urlaub_uebertrag=m;return kontenQuelle(j)}})"
    assert _node(("kontenQuelle",), ablauf, "var konten={erstes_jahr:2027,vorgaben:{}};") == [uebertrag_quelle(j, m) for j, m in faelle]


def test_js_anspruch_mit_dem_uebertrag():
    vorweg = "var konten={erstes_jahr:2027,jahr:2027,vorgaben:{urlaub_vorgabe_tage:'30.0',urlaub_uebertrag:'von_hand'}};"
    ablauf = ("const sw={resturlaub_tage:'4.5'};const a27={jahr:2027,urlaubstage_wirksam:'24.0',vorgabe:false,uebertrag:null,uebertrag_doppelt:false};"
              "const r=[kontenAnspruchText({ansprueche:[a27],startwert:sw}),kontenAnspruchText({ansprueche:[],startwert:null}),"
              "kontenAnspruchText({ansprueche:[{...a27,uebertrag:'2.0',uebertrag_doppelt:true}],startwert:sw})];"
              "konten.jahr=2028;r.push(kontenAnspruchText({ansprueche:[{jahr:2028,urlaubstage_wirksam:'30.0',vorgabe:true,uebertrag:'-1.5',"
              "uebertrag_doppelt:false}],startwert:sw}));konten.vorgaben.urlaub_uebertrag='automatisch';"
              "r.push(kontenAnspruchText({ansprueche:[],startwert:sw}));return r")
    assert _node(("kontenTage", "kontenAnspruch", "kontenQuelle", "kontenUebertragText", "kontenAnspruchText"), ablauf, vorweg) == [
        "24 Tage · Übertrag 4,5", "30 Tage (Vorgabe)", "24 Tage · Übertrag doppelt – prüfen", "30 Tage (Vorgabe) · Übertrag -1,5",
        "30 Tage (Vorgabe) · Übertrag automatisch"]


def test_js_inaktive_ausblenden():
    text = _text()
    konst = re.search(r"const LOHN_INAKTIVE_SCHLUESSEL='[^']+';", text)[0]
    assert konst == "const LOHN_INAKTIVE_SCHLUESSEL='erp_lohnstammdaten_inaktive';"  # eigener Schlüssel, nicht der der Mitarbeiterliste
    assert "let lohnInaktiveVersteckt=lohnInaktiveGemerkt();" in text  # der Stand beginnt mit dem gemerkten Wert
    vorweg = (konst + "let lohnInaktiveVersteckt=true;var GEZEICHNET=[];function renderPayroll(){GEZEICHNET.push('lohn')}"
              "function renderKonten(){GEZEICHNET.push('konten')}var konten={};")
    ablauf = ("const r=[lohnInaktiveGemerkt()];SPEICHER[LOHN_INAKTIVE_SCHLUESSEL]='zeigen';r.push(lohnInaktiveGemerkt());"
              "const liste=[{n:'a',active:true},{n:'u',active:false},{n:'o'}];r.push(lohnDerListe(liste).map(x=>x.n));"
              "lohnInaktiveMerken(false);r.push(SPEICHER[LOHN_INAKTIVE_SCHLUESSEL],lohnDerListe(liste).map(x=>x.n),GEZEICHNET.slice());"
              "lohnInaktiveMerken(true);r.push(SPEICHER[LOHN_INAKTIVE_SCHLUESSEL]);"
              "lohnKaestchen('kontenInaktivZahl',liste);r.push(EL.kontenInaktivZahl.textContent);return r")
    assert _node(("lohnInaktiveGemerkt", "lohnInaktiveMerken", "lohnDerListe", "lohnKaestchen"), ablauf, vorweg) == [
        True, False, ["a", "o"], "zeigen", ["a", "u", "o"], ["lohn", "konten"], "ausblenden", "1 inaktiv"]


GEPRUEFT = ("var konten={stichtag:'2026-12-31',personen:[]};var kdPerson={employee_id:7,startwert:{stichtag:'2026-12-31',resturlaub_tage:'4.5',saldo_stunden:'-12.25',"
            "herkunft:'steuerbuero',herkunft_notiz:'Liste',geprueft_am:'2026-11-10',geprueft_von:'Fin'}};var GESENDET=[];"
            "async function speichern(b,f){f()}function api(u,o){GESENDET.push(JSON.parse(o.body))}function ladeKonten(){}")


def test_js_geprueft_zeigt_den_stand_und_faellt_bei_aenderung():
    ablauf = ("kontenStartwertFuellen();const r=[[EL.kdGeprueft.checked,EL.kdGeprueftHinweis.hidden,EL.kdGeprueftText.textContent]];"
              "kontenStartwertGeaendert();r.push([EL.kdGeprueft.checked,EL.kdGeprueftHinweis.hidden]);"  # nichts geändert
              "EL.kdSaldo.value='-13';kontenStartwertGeaendert();r.push([EL.kdGeprueft.checked,EL.kdGeprueftHinweis.hidden]);"
              "EL.kdGeprueft.checked=true;EL.kdSaldo.value='-12,25';kontenStartwertGeaendert();r.push([EL.kdGeprueft.checked,EL.kdGeprueftHinweis.hidden]);"
              "kdPerson.startwert.geprueft_am=null;kontenStartwertFuellen();EL.kdSaldo.value='-13';kontenStartwertGeaendert();"
              "r.push([EL.kdGeprueft.checked,EL.kdGeprueftHinweis.hidden]);return r")
    assert _node(("kontenStartwertWerte", "kontenStartwertGeaendert", "kontenStartwertFuellen"), ablauf, GEPRUEFT + "let kdStartwertVorher='',kdGeprueftVorher=false;") == [
        [True, True, "Geprüft am 10.11.2026 durch Fin."], [True, True], [False, False], [True, False], [False, True]]


@pytest.mark.parametrize("geprueft_am, schritte, erwartet", [
    ("2026-11-10", "", None),                                                      # geprüft, nichts geändert, Haken an: nichts senden, die Prüfung bleibt
    ("2026-11-10", "EL.kdSaldo.value='-13';kontenStartwertGeaendert();", False),    # geändert, der Haken ging heraus: die Prüfung ist weg
    ("2026-11-10", "EL.kdSaldo.value='-13';kontenStartwertGeaendert();EL.kdGeprueft.checked=true;", True),  # geändert und neu angehakt
    ("2026-11-10", "EL.kdGeprueft.checked=false;", False),                          # nur abgehakt: Prüfung weg
    ("2026-11-10", "EL.kdSaldo.value='-13';", False),                               # geändert ohne Eingabe-Ereignis: beim Speichern heraus
    (None, "EL.kdGeprueft.checked=true;", True),                                    # erstmals angehakt
    (None, "", None),
])
def test_js_geprueft_gesendet_nur_wenn_sich_etwas_tut(geprueft_am, schritte, erwartet):
    vorweg = GEPRUEFT.replace("geprueft_am:'2026-11-10'", f"geprueft_am:{json.dumps(geprueft_am)}") + "let kdStartwertVorher='',kdGeprueftVorher=false;"
    ablauf = f"kontenStartwertFuellen();{schritte}return kontenStartwertSpeichern().then(()=>GESENDET[0].geprueft??null)"
    assert _node(("kontenStartwertWerte", "kontenStartwertGeaendert", "kontenStartwertFuellen", "kontenStartwertSpeichern"), ablauf, vorweg) == erwartet


# --- Seite: Aufbau ------------------------------------------------------------------------------------------------------------------------

def test_seite_aufbau():
    text = vj.seitentext("settings.html")[0]
    kaestchen = re.findall(r'<input type="checkbox" id="(\w+)" data-lohn-inaktive data-nur-anzeige data-aenderung="lohn-inaktive" checked>', text)
    assert kaestchen == ["lohnInaktiveAusblenden", "kontenInaktiveAusblenden"]  # über den Lohnstammdaten und über den Konten, Vorgabe an
    assert text.index('id="lohnInaktiveAusblenden"') < text.index('id="payrollRollen"') < text.index('id="kontenInaktiveAusblenden"') < text.index('id="kontenTabelle"')
    # nur Anzeige: ohne Recht zum Ändern bleibt das Kästchen bedienbar
    assert "box.querySelectorAll('input:not([data-nur-anzeige]),textarea,select').forEach(f=>{f.disabled=true});" in text
    # der Übertrag ist nicht mehr fest an „darf“ gebunden -- kontenJahrFuellen() sperrt ihn je Jahr
    assert "['kdTage','kdVerfall','kdNotiz'].forEach(i=>{document.getElementById(i).disabled=!darf});" in text
    assert "ue.disabled=!konten.darf_aendern||q!=='von_hand';" in text
    assert "if(kontenQuelle(jahr)==='von_hand')werte.uebertrag=zahlFeld('kdUebertrag');" in text
    # 412 px: Werte ohne Umbruch, Trennlinie der ersten Spalte (außer in der letzten Zeile)
    assert ".lohn-tabelle td:first-child{box-shadow:inset -1px 0 0 var(--line),inset 0 -1px 0 var(--line)}" in text
    assert ".lohn-tabelle tbody tr:last-child td:first-child{box-shadow:inset -1px 0 0 var(--line)}" in text
    assert ".lohn-tabelle td.nw{white-space:nowrap}" in text
    assert ('<td class="nw">${esc(kontenAnspruchText(p))}</td><td class="nw">${esc(kontenTage(p.startwert?p.startwert.resturlaub_tage:null))}</td>'
            '<td class="nw">${esc(kontenSaldoText(p.startwert))}</td>') in text
    # die Felder des Startwerts melden jede Eingabe
    for feld in ("kdRest", "kdSaldo", "kdHerkunftNotiz"):
        assert re.search(rf'<input id="{feld}"[^>]*data-eingabe="konten-startwert-geaendert"', text), feld
    assert '<select id="kdHerkunft" data-aenderung="konten-startwert-geaendert">' in text
    assert '<div id="kdGeprueftHinweis" class="hint" style="border-left-color:var(--ds-warn-text)" hidden>Wert geändert – neu prüfen</div>' in text
