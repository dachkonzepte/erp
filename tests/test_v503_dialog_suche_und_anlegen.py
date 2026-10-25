"""Seit 1.9.80 (Stufe 4, R4 Nachtrag 3, A): der Dialog „Für welchen Auftrag?“ auf „Heute“ sucht über alle nicht stornierten Aufträge und legt den
Bericht selbst an.

    Wahl       oben „Auftrag suchen“ (ab 2 Zeichen, GET /api/field-view/auftraege-suche, eine Antwort zu einem überholten Suchbegriff zeichnet
               nichts), darunter „Deine Aufträge“ (H.auftraege) bzw. „Treffer“; jede Zeile ein Knopf
    Anlegen    zweiter Schritt im Dialog: GET /api/field-view/auftraege/{id}/bericht-anlegen, Art, Datum, Dachflächen, Vorlage (bei genau einer
               Fläche), Beschreibung; „Anlegen“ über speichern() an POST /api/orders/{id}/service-reports, danach /service-reports/{id}
Die Bedienung im Browser prüft scripts/klicktest_bericht_ohne_einsatz.py (Bilder 3a und 8).
"""

import re

from tests import vorlagen_js as vj


def _text():
    return vj.seitentext("mobil.html")[0]


def _funktion(text, name):
    m = re.search(r"(?:async )?function " + name + r"\([^)]*\)\{.*?\n  \}\n", text, flags=re.S)
    assert m, name
    return m[0]


def test_dialog_hat_suche_liste_und_zweiten_schritt():
    dialog = re.search(r'<dialog id="berichtDialog" class="dialog-karte".*?</dialog>', _text(), flags=re.S)[0]
    for teil in ('<input id="auftragSuche" type="search"', 'id="berichtListeTitel">Deine Aufträge</span>', 'id="berichtAuftraege"',
                 'id="berichtNeu" hidden', 'id="neuArt"', 'id="neuDatum" type="date"', 'id="neuFlaechen"', 'id="neuVorlage"',
                 'id="neuBeschreibung"', 'id="berichtZurueck" hidden>Anderer Auftrag</button>', 'id="berichtAnlegen" hidden>Anlegen</button>'):
        assert teil in dialog, teil
    assert dialog.rstrip().endswith("</div>\n</dialog>") or dialog.rstrip().endswith("</div></dialog>")  # endet mit der Knopfleiste


def test_suche_ab_zwei_zeichen_ueber_den_server_ohne_ueberholte_antworten():
    suche = _funktion(_text(), "sucheGeaendert")
    assert "if(q.length<2){eigeneAuftraegeZeigen();return}" in suche
    assert "lesen('auftragssuche',()=>api('/api/field-view/auftraege-suche?q='+encodeURIComponent(q))" in suche
    assert "if(el('auftragSuche').value.trim()!==q)return;" in suche


def test_zweiter_schritt_und_anlegen():
    text = _text()
    neu = _funktion(text, "berichtNeuOeffnen")
    assert "api('/api/field-view/auftraege/'+orderId+'/bericht-anlegen')" in neu
    anlegen = _funktion(text, "berichtAnlegen")
    assert "speichern('bericht-neu',()=>api('/api/orders/'+NEU.auftrag.id+'/service-reports',{method:'POST'" in anlegen
    assert anlegen.index("speichern(") < anlegen.index("location.href='/service-reports/'+neu.id;")
    assert "inspection_template_id:flaechen.length===1&&vorlage?Number(vorlage):null" in anlegen  # Vorlage nur bei genau einer Fläche
    assert "el('berichtAuftraege').addEventListener('click',function(e){var z=e.target.closest('[data-auftrag]');" in text
