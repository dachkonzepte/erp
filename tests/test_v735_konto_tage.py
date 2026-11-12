"""Version 1.9.335 (Lohn L2c-3, Punkt 2): je Person „Tage ansehen“ im Arbeitszeitkonto.

    Dialog     „Tage im Konto · <Name>“ aus der schon geladenen Antwort (keine Anfrage): je Tag mit Sollzeit, Ist oder Posten Soll, Ist, Gutschrift, Saldo und
               Vermerk; darunter der Monat; im Kopf der Stand (ohne Startwert „Startwert folgt“) und „vorläufig – maßgeblich ist die Lohnabrechnung“
    Vermerk    je Posten „<Bezeichnung> <Stunden> gutgeschrieben“ bzw. „– zählt nicht“, dazu der Vermerk des Servers (Schlechtwetter Winter); ein Tag mit
               Sollzeit ohne Arbeit und ohne Posten „kein Eintrag – zählt als Minus“
"""

import json

from app.arbeitszeitkonto import WINTER_VERMERK
from tests.node_lauf import node_ausfuehren
from tests.test_v734_konto_monat import _funktion, _text

VORWEG = ("function esc(s){return String(s??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/\"/g,'&quot;')}"
          "function zahlText(w,s){return Number(w).toFixed(s).replace('.',',')}function stunden(w){return zahlText(w,2)+' h'}"
          "function tagKurz(i){return 'T'+i.slice(8,10)+'.'+i.slice(5,7)+'.'}function kontoStunden(w){return (w>0?'+':'')+zahlText(w,2)+' h'}")


def _node(ablauf: str):
    text = _text()
    js = VORWEG + "\n" + "\n".join(_funktion(text, f) for f in ("kontoVermerk", "kontoTageZeilen")) + \
        f"\nconst ergebnis=(()=>{{{ablauf}}})();process.stdout.write(JSON.stringify(ergebnis));"
    return node_ausfuehren(js)


TAGE = [
    {"tag": "2027-01-01", "soll": 7.5, "arbeit": 0, "gutschrift": 7.5, "ist": 7.5, "saldo": 0,
     "posten": [{"bezeichnung": "Neujahr", "stunden": 7.5, "gutgeschrieben": True, "vermerk": None}]},
    {"tag": "2027-01-02", "soll": 0, "arbeit": 0, "gutschrift": 0, "ist": 0, "saldo": 0, "posten": []},
    {"tag": "2027-01-04", "soll": 7.5, "arbeit": 8, "gutschrift": 0, "ist": 8, "saldo": 0.5, "posten": []},
    {"tag": "2027-01-20", "soll": 7.5, "arbeit": 0, "gutschrift": 0, "ist": 0, "saldo": -7.5,
     "posten": [{"bezeichnung": "Freizeitausgleich", "stunden": 7.5, "gutgeschrieben": False, "vermerk": None}]},
    {"tag": "2027-01-25", "soll": 7.5, "arbeit": 0, "gutschrift": 0, "ist": 0, "saldo": -7.5, "posten": []},
    {"tag": "2027-01-26", "soll": 7.5, "arbeit": 2, "gutschrift": 5.5, "ist": 7.5, "saldo": 0,
     "posten": [{"bezeichnung": "Schlechtwetter Winter", "stunden": 5.5, "gutgeschrieben": True, "vermerk": WINTER_VERMERK}]},
]


def test_vermerk_je_tag():
    r = _node("return " + json.dumps(TAGE) + ".map(kontoVermerk)")
    assert r == ["Neujahr 7,50 h gutgeschrieben", "", "", "Freizeitausgleich 7,50 h – zählt nicht", "kein Eintrag – zählt als Minus",
                 f"Schlechtwetter Winter 5,50 h gutgeschrieben ({WINTER_VERMERK})"]


def test_zeilen_ohne_leere_tage():
    html = _node("return kontoTageZeilen({tage:" + json.dumps(TAGE) + "})")
    assert html.count("<tr>") == 5 and "T02.01." not in html  # der Samstag ohne Sollzeit und ohne Stunden fehlt
    assert ('<tr><td class="nv-tag">T04.01.</td><td class="r num">7,50 h</td><td class="r num">8,00 h</td><td class="r num">0,00 h</td>'
            '<td class="r num">+0,50 h</td><td class="kt-vermerk"></td></tr>') in html
    assert '<td class="r num">-7,50 h</td><td class="kt-vermerk">kein Eintrag – zählt als Minus</td>' in html


def test_seite():
    text = _text()
    oeffnen = _funktion(text, "kontoTageOeffnen")
    assert "el('kontoTageDialog').showModal();" in oeffnen and "api(" not in oeffnen  # aus der geladenen Antwort
    assert "el('ktUnter').textContent=M.titel+' · '+el('kontoStandKopf').textContent+': '+(ohne?'Startwert folgt':kontoStunden(m.stand));" in oeffnen
    assert "el('ktVorlaeufig').textContent=KONTO.hinweis;" in oeffnen
    assert "data-aktion=\"konto-tage\" data-id=\"'+k.employee_id+'\">Tage ansehen</button>" in text
    assert "var b=ev.target.closest&&ev.target.closest('[data-aktion=\"konto-tage\"]');if(b)kontoTageOeffnen(b.dataset.id);" in text
    assert '<th>Tag</th><th class="r">Soll</th><th class="r">Ist</th><th class="r">Gutschrift</th><th class="r">Saldo</th><th>Vermerk</th>' in text
