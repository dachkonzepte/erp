"""Version 1.10.25 (Frage F12, Antwort 23.11.2026): jede Tabelle der Akte rollt in ihrem Rahmen.

Bis 1.10.24 stand die Tabelle „Angebote“ der Übersicht (Projekt ohne Auftrag) in einem Element ohne Rahmen -- bei 412 px lief die ganze Akte 60 px über.
Jedes Element, in das die Akte eine Tabelle zeichnet (el('…').innerHTML = …, der Ausdruck enthält <table oder einen Wert „…tabelle…“), trägt jetzt
`tabelle-wrap` (rollt waagrecht in sich). Gemessen im Browser: scripts/klicktest_nur_lesen.py (Akte eines Projekts ohne Auftrag bei 412 px, im Archiv und
zurückgeholt).
"""

import re
from pathlib import Path

from tests.vorlagen_js import _ausdruck_ende, analysieren, eigene_skripte

ROOT = Path(__file__).resolve().parent.parent
AKTE = ROOT / "app" / "templates" / "akte.html"
TABELLE = re.compile(r"<table|tabelle|Tabelle")


def _tabellen_ziele() -> set[str]:
    """Die IDs der Elemente, in die das Skript der Akte eine Tabelle zeichnet: el('ID').innerHTML = <Ausdruck mit einer Tabelle>."""
    a = analysieren(eigene_skripte("akte.html"))
    t, ziele = a.t, set()
    for k in range(5, len(t) - 2):
        if (t[k].wert == "innerHTML" and t[k - 1].wert == "." and t[k + 1].wert == "=" and t[k - 2].wert == ")" and t[k - 3].art == "str"
                and t[k - 4].wert == "(" and t[k - 5].wert == "el"):
            e = _ausdruck_ende(a, k + 2)
            if TABELLE.search(a.quelle.text[t[k + 2].pos:t[e].pos + len(t[e].wert)]):
                ziele.add(t[k - 3].wert)
    return ziele


def _klassen(text: str, kennung: str) -> list[str]:
    m = re.search(r"<[a-z]+\b([^>]*)\bid=\"" + re.escape(kennung) + r"\"([^>]*)>", text)
    assert m is not None, f"Element #{kennung} nicht im Markup"
    k = re.search(r"class=\"([^\"]*)\"", m.group(1) + m.group(2))
    return k.group(1).split() if k else []


def test_jede_tabelle_der_akte_steht_in_einem_rahmen_der_rollt():
    text = AKTE.read_text(encoding="utf-8")
    ziele = _tabellen_ziele()
    # die Ziele von heute: Stunden je Mitarbeiter, Angebote (Reiter und Übersicht), Rechnungen (Reiter und Übersicht) -- ein neues kommt von selbst dazu
    assert {"uMitarbeiter", "quotes", "uAngeboteListe", "invoicesList", "uRechnungen"} <= ziele, sorted(ziele)
    ohne = sorted(z for z in ziele if "tabelle-wrap" not in _klassen(text, z))
    assert ohne == [], f"Tabelle ohne Rahmen, der rollt: {ohne}"
    assert re.search(r"\.tabelle-wrap\{[^}]*overflow-x:auto", text)


def test_angebote_der_uebersicht_im_rahmen():
    """Der Befund selbst: die Tabelle „Angebote“ der Übersicht (nur ohne Auftrag) steht im selben Rahmen wie die im Reiter."""
    text = AKTE.read_text(encoding="utf-8")
    assert "tabelle-wrap" in _klassen(text, "uAngeboteListe")
    assert "tabelle-wrap" in _klassen(text, "quotes")


def test_nummer_des_angebots_bricht_nicht_um():
    """Im Rahmen, der rollt, bleibt die Nummer in einer Zeile (bis 1.10.24 bei 412 px „A- / 2026- / 0903“) -- wie die Nummer der Rechnungsliste."""
    text = AKTE.read_text(encoding="utf-8")
    assert re.search(r"(?m)^td\.nw\{white-space:nowrap\}", text)
    assert '<tr><td class="nw"><a href="/quotes/${Number(q.id)}/edit"><b>${esc(q.quote_number)}</b></a></td>' in text
