"""Version 1.9.334 (Lohn L2c-3, Punkt 1): das Arbeitszeitkonto in „Monat & Lohn“.

    Karte      „Arbeitszeitkonto“ unter „Stunden je Mitarbeiter“, darüber „vorläufig – maßgeblich ist die Lohnabrechnung“ (vom Server); je gewerblicher Person
               Soll im Monat, Saldo des Monats, Stand am Monatsende (laufender Monat: „Stand bis <gestern>“) -- aus GET /api/zeiten/arbeitszeitkonto, die Seite
               rechnet nichts nach
    Startwert  ohne Startwert (am Stichtag beschäftigt) „Startwert folgt“ statt des Stands
    ab 2027    vor Januar 2027 keine Karte und keine Anfrage (KONTO_AB = KONTOBEGINN)
    Spalten    „Konto · 0,25 je Tag“ unter Soll und Saldo, dazu der Satz, dass die Zeitarten darüber minutengenau sind (Befund L2c, 10.6)
"""

import json
import re

from app.arbeitszeitkonto import KONTOBEGINN, OHNE_STARTWERT, VORLAEUFIG
from tests import vorlagen_js as vj
from tests.node_lauf import node_ausfuehren


def _text():
    return vj.seitentext("zeiten.html")[0]


def _funktion(text: str, name: str) -> str:
    i = text.index("function " + name + "(")
    tiefe, j = 0, text.index("{", text.index(")", i))
    while True:
        tiefe += {"{": 1, "}": -1}.get(text[j], 0)
        j += 1
        if tiefe == 0:
            return text[i:j]


def _node(ablauf: str, vorweg: str = ""):
    text = _text()
    js = ("function esc(s){return String(s??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/\"/g,'&quot;')}"
          "function zahlText(w,s){return Number(w).toFixed(s).replace('.',',')}function stunden(w){return zahlText(w,2)+' h'}"
          "function tagLang(i){return 'Mo '+i.slice(8,10)+'.'+i.slice(5,7)+'.'+i.slice(0,4)}"
          "var EL={};function el(id){return EL[id]||(EL[id]={id:id,hidden:false,textContent:'',innerHTML:''})}\n"
          + vorweg + "\n" + re.search(r"var KONTO_AB='[^']+',KONTO=null;", text)[0] + "\n"
          + "\n".join(_funktion(text, f) for f in ("kontoStunden", "kontoZeile", "kontoZeichnen"))
          + f"\nconst ergebnis=(()=>{{{ablauf}}})();process.stdout.write(JSON.stringify(ergebnis));")
    return node_ausfuehren(js)


ANTWORT = {"monat": "2027-01", "gezaehlt_bis": "2027-01-31", "hinweis": VORLAEUFIG, "konten": [
    {"employee_id": 1, "name": "Ada <A>", "hinweise": [], "monate": [{"soll": 157.5, "saldo": 1.5, "stand": 14}]},
    {"employee_id": 2, "name": "Bo", "hinweise": [OHNE_STARTWERT], "monate": [{"soll": 157.5, "saldo": -7.5, "stand": -7.5}]}]}


def test_kontobeginn_und_startwert_wie_der_server():
    text = _text()
    assert f"var KONTO_AB='{KONTOBEGINN:%Y-%m}',KONTO=null;" in text
    assert f"k.hinweise.indexOf('{OHNE_STARTWERT}')>=0" in text


def test_zeilen_und_stand():
    r = _node("globalThis.M={ende:'2027-01-31'};kontoZeichnen(" + json.dumps(ANTWORT) + ");return [EL.kontoKarte.hidden,EL.kontoVorlaeufig.textContent,"
              "EL.kontoStandKopf.textContent,EL.kontoGezaehlt.textContent,EL.kontoZeilen.innerHTML,EL.kontoLeer.hidden]")
    assert r[:4] == [False, VORLAEUFIG, "Stand am Monatsende", ""] and r[5] is True
    assert ('<tr data-konto="1"><td>Ada &lt;A></td><td class="r num">157,50 h</td><td class="r num">+1,50 h</td><td class="r num">+14,00 h</td>') in r[4]
    assert ('<td class="r num">-7,50 h</td><td class="r num"><span class="chip chip-warn">Startwert folgt</span>') in r[4]


def test_laufender_monat_bis_gestern_und_vor_2027_nichts():
    r = _node("globalThis.M={ende:'2027-02-28'};kontoZeichnen(" + json.dumps({**ANTWORT, "monat": "2027-02", "gezaehlt_bis": "2027-02-02"})
              + ");var a=[EL.kontoStandKopf.textContent,EL.kontoGezaehlt.textContent];kontoZeichnen(null);return a.concat([EL.kontoKarte.hidden])")
    assert r == ["Stand bis 02.02.2027", "gezählt bis gestern, 02.02.2027", True]


def test_seite():
    text = _text()
    laden = _funktion(text, "monatLaden")
    assert ".then(function(){return lesen('konto',()=>LOHN_MONAT<KONTO_AB?null:api('/api/zeiten/arbeitszeitkonto?monat='+encodeURIComponent(LOHN_MONAT)),kontoZeichnen)})" in laden
    karte = text[text.index('<section class="tabelle-karte" id="kontoKarte"'):]
    karte = karte[:karte.index("</section>")]
    assert karte.count('<span class="konto-kopf-einheit">Konto · 0,25 je Tag</span>') == 2
    assert "Die Zeitarten in „Stunden je\n      Mitarbeiter“ sind minutengenau." in karte.replace("\r\n", "\n")
    # die Karte steht unter „Stunden je Mitarbeiter“
    assert text.index('aria-labelledby="lohnTabelleTitel"') < text.index('id="kontoKarte"')
