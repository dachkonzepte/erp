"""Version 1.9.220 (L1a Stufe 7, Punkt 3): das Häkchen „Monatszeile“ ist gesperrt, solange ein Kennzeichen steht.

    Zeichnen    mit gespeichertem Kennzeichen (Schlechtwetter Winter WA) gesperrt, darunter „Für die Monatszeile zuerst das Kennzeichen leeren.“;
                ohne Kennzeichen frei, ohne Hinweis
    Tippen      Kennzeichen geleert -> frei, Hinweis weg; Kennzeichen getippt -> gesperrt und abgehakt, Hinweis da
    Server      lehnt eine Monatszeile mit Kennzeichen weiter ab (Festlegung 1.9.169, test_v587)

Die Monatszeile bleibt als Möglichkeit (Befund 1.9.217); bis 1.9.219 brach das Häkchen bei Winter mit „Eine Monatszeile hat kein Kennzeichen“ ab.
"""

import pytest

from app.lohnarten import speichern
from tests.node_lauf import node_ausfuehren
from tests.test_v518_zeiten_seite import _funktion
from tests.vorlagen_js import eigene_skripte

HINWEIS = "Für die Monatszeile zuerst das Kennzeichen leeren."
DOM = ("var EL={};function feld(id){return EL[id]||(EL[id]={id:id,value:'',checked:false,disabled:false,hidden:false,innerHTML:''})}"
       "var document={getElementById(id){return feld(id)}};"
       "function esc(s){return String(s??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/\"/g,'&quot;')}function lohnregelnNurLesen(){}")


def _skript(*rest: str) -> str:
    text = eigene_skripte("settings.html").text
    return DOM + _funktion(text, "monatszeileSperren") + "\n" + _funktion(text, "renderLohnarten") + "\n" + "\n".join(rest)


def test_gezeichnet_gesperrt_mit_kennzeichen():
    zeilen = ("var lohnarten=[{schluessel:'schlechtwetter:winter',bezeichnung:'Winter',kennzeichen:'WA',lohnart:'8195',monatszeile:false,"
              "monatszeile_moeglich:true,stunden:'',wirkt:''},{schluessel:'schlechtwetter:sommer',bezeichnung:'Sommer',kennzeichen:null,lohnart:null,"
              "monatszeile:false,monatszeile_moeglich:true,stunden:'',wirkt:''}];renderLohnarten();"
              "process.stdout.write(JSON.stringify(EL.lohnartZeilen.innerHTML));")
    html = node_ausfuehren(_skript(zeilen))
    winter, sommer = html.split('data-lohnart="schlechtwetter:sommer"')
    assert '<input id="lzM-0" type="checkbox" style="width:auto"  disabled>' in winter
    assert f'<div class="small muted" id="lzMH-0" >{HINWEIS}</div>' in winter
    assert '<input id="lzM-1" type="checkbox" style="width:auto"  >' in sommer and 'id="lzMH-1" hidden>' in sommer
    assert 'data-eingabe="lohnart-kennzeichen" data-i="0"' in winter


def test_beim_tippen():
    """Leeren gibt frei, Hinweis weg; ein Kennzeichen sperrt und hakt ab, Hinweis da."""
    ablauf = ("feld('lzK-0').value='';feld('lzM-0').disabled=true;feld('lzMH-0').hidden=false;monatszeileSperren(0);var aus=[[EL['lzM-0'].disabled,EL['lzMH-0'].hidden]];"
              "feld('lzM-0').checked=true;feld('lzK-0').value='WA';monatszeileSperren(0);aus.push([EL['lzM-0'].disabled,EL['lzM-0'].checked,EL['lzMH-0'].hidden]);"
              "feld('lzK-0').value='  ';monatszeileSperren(0);aus.push([EL['lzM-0'].disabled,EL['lzMH-0'].hidden]);"
              "monatszeileSperren(5);process.stdout.write(JSON.stringify(aus));")
    assert node_ausfuehren(_skript(ablauf)) == [[False, True], [True, False, False], [False, True]]


def test_server_lehnt_weiter_ab(db_session):
    with pytest.raises(ValueError, match="Eine Monatszeile hat kein Kennzeichen."):
        speichern(db_session, "schlechtwetter:winter", "WA", "8195", True)
    assert speichern(db_session, "schlechtwetter:winter", None, "8195", True).monatszeile is True
