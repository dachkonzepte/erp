"""Version 1.9.132 (Stufe 5, R2 Nachrunde, Punkte 3–5) -- Stunden mit zwei Stellen, „Entwurf öffnen“, Daten mit Jahr.

3. Stunden in der Akte mit zwei Stellen wie in „Zeiten“ (10,75 h statt 10,8 h): Übersicht, Phase (Text vom Server, app/akte.py::stunden_text()),
   Leistungen (Std. Ist/Soll je Position), Ausführung -- die Vorlage zeigte eine Stelle, das war falsch.
4. „Nächste Rechnung“: liegt schon ein Entwurf vor, führt „Entwurf öffnen“ auf ihn statt „Entwurf anlegen“ (ein Entwurf sperrt keinen neuen
   Abschlag -- bis 1.9.131 bot die Karte einen zweiten an).
5. Ein Datum, das für sich steht (Auftragsdaten: Auftragsdatum, Ausführung; geplanter Zeitraum, Stand des LV, überfällig seit), mit Jahr; kurz nur
   in Phasen und Listen.
"""

import json
import re
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from app.akte import stunden_text
from app.routers import orders as orders_router
from app.routers import zeiten as zeiten_router
from tests.node_lauf import node_ausfuehren
from tests.test_v314_dashboard_month_berlin import NODE
from tests.test_v545_phase_projektstatus import _buchung, _schritte, welt  # noqa: F401  (Fixture)

VORLAGEN = Path(__file__).resolve().parents[1] / "app" / "templates"
AKTE = (VORLAGEN / "akte.html").read_text(encoding="utf-8")


def _skripte(name):
    return "\n".join(re.findall(r"<script>(.*?)</script>", (VORLAGEN / name).read_text(encoding="utf-8"), flags=re.S))


def _funktion(text, kopf):
    """Eine Funktion der Seite wörtlich (vom Kopf bis zur schließenden Klammer am Zeilenanfang)."""
    start = text.index(kopf)
    return text[start:text.index("\n}\n", start) + 3]


def _zeile(text, kopf):
    start = text.index(kopf)
    return text[start:text.index("\n", start)]


# --- Punkt 3: Stunden ---------------------------------------------------------------------------------------------------------------------

def test_dieselben_stunden_in_akte_und_zeiten(welt):  # noqa: F811
    """10,75 h gebucht (8 + 2,75): die Zahlen der Akte, „Zeiten“ (alle Monate des Auftrags) und der Text der Phase nennen dieselbe Summe mit zwei
    Stellen."""
    _buchung(welt, welt["heute"] - timedelta(days=3), "8")
    _buchung(welt, welt["heute"] - timedelta(days=1), "2.75")
    client = welt["client"](welt["db"], orders_router.router, zeiten_router.router, role="buero_finanzen")
    order_id = welt["order"].id
    stunden = client.get(f"/api/orders/{order_id}/zahlen").json()["stunden"]
    assert Decimal(str(stunden["gebucht"])) == Decimal(str(stunden["baustelle_werkstatt"])) == Decimal("10.75")
    zeiten = client.get("/api/zeiten/buchungen", params={"auftrag": order_id, "zeitraum": "alle"})
    assert zeiten.status_code == 200, zeiten.text
    assert Decimal(str(zeiten.json()["summe"])) == Decimal("10.75")
    _, schritte = _schritte(welt)
    assert schritte["ausfuehrung"][2].endswith("· 10,75 h gebucht")


@pytest.mark.parametrize("wert,text", [(Decimal("10.75"), "10,75 h"), (Decimal("9.5"), "9,50 h"), (None, "0,00 h"), (Decimal("0.125"), "0,13 h")])
def test_stunden_text_zwei_stellen(wert, text):
    assert stunden_text(wert) == text


@pytest.mark.skipif(NODE is None, reason="node nicht installiert")
def test_anzeige_wie_zeiten():
    """Die Helfer der Akte (Übersicht, Ausführung, Leistungen) und von „Zeiten“ zeichnen 10,75 h gleich."""
    akte = _zeile(AKTE, "const stunden=h=>") + "\nconst _lvPosition=i=>i;\n" + _zeile(AKTE, "function lvStd(i)")
    zeiten = _zeile((VORLAGEN / "zeiten.html").read_text(encoding="utf-8"), "function stunden(wert)").replace("function stunden(", "function stundenZeiten(")
    ablauf = _skripte("_zahl.html") + "\n" + akte + "\n" + zeiten + """
      console.log(JSON.stringify([stunden('10.75'), stundenZeiten('10.75'), stunden(9.5), lvStd({stunden_ist: '10.75', stunden_soll: '12'}),
                                  lvStd({stunden_ist: '1', stunden_soll: null})]));
    """
    assert node_ausfuehren(ablauf, "Europe/Berlin") == ["10,75 h", "10,75 h", "9,50 h", "10,75 / 12,00 h", "–"]


# --- Punkt 4: „Entwurf öffnen“ ------------------------------------------------------------------------------------------------------------

def _naechste(invoices, blocks=None):
    dom = """
      const esc = s => String(s ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
      const money = x => Number(x || 0).toLocaleString('de-DE', {style: 'currency', currency: 'EUR'});
      const elemente = {uNaechste: {hidden: true, dataset: {}}, uNaechsteText: {innerHTML: ''}, uNaechsteKnopf: {hidden: false},
                        uNaechsteLink: {hidden: true, href: '/projects'}};
      const el = id => elemente[id];
    """
    daten = f"let invoices = {json.dumps(invoices)}; const order = {{invoice_create_blocks: {json.dumps(blocks or {})}}};\n"
    ablauf = dom + daten + _funktion(AKTE, "function naechsteRechnungZeichnen(){") + """
      naechsteRechnungZeichnen();
      const e = elemente;
      console.log(JSON.stringify([e.uNaechste.hidden, e.uNaechsteKnopf.hidden, e.uNaechsteLink.hidden, e.uNaechsteLink.href, e.uNaechsteText.innerHTML]));
    """
    return node_ausfuehren(ablauf, "Europe/Berlin")


@pytest.mark.skipif(NODE is None, reason="node nicht installiert")
def test_mit_entwurf_entwurf_oeffnen():
    """Ein Entwurf (Storno-Entwürfe zählen nicht): „Entwurf öffnen“ auf ihn, kein „Entwurf anlegen“; bei zwei der älteste, mit Hinweis."""
    versendet = {"id": 3, "status": "versendet", "invoice_type": "abschlag_leistungsstand", "art_text": "1. Abschlag nach Leistungsstand",
                 "net_total": "1000"}
    entwurf = {"id": 9, "status": "entwurf", "invoice_type": "abschlag_leistungsstand", "art_text": "2. Abschlag nach Leistungsstand",
               "net_total": "1250.5"}
    storno = {"id": 5, "status": "entwurf", "invoice_type": "storno", "art_text": "Storno", "net_total": "-1000"}
    sichtbar, knopf_weg, link_weg, href, text = _naechste([versendet, storno, entwurf])
    assert (sichtbar, knopf_weg, link_weg, href) == (False, True, False, "/invoices/9")
    assert text.startswith("<b>Nächste Rechnung:</b> 2. Abschlag nach Leistungsstand liegt als Entwurf vor (netto 1.250,50") and "weitere" not in text
    zweiter = dict(entwurf, id=12, invoice_type="schluss", art_text="Schlussrechnung")
    _, _, _, href, text = _naechste([zweiter, versendet, entwurf])
    assert href == "/invoices/9" and "dazu 1 weiterer Entwurf" in text
    _, _, _, _, text = _naechste([dict(entwurf, net_total="0")])  # ein frischer Entwurf: ohne „netto 0,00 €“
    assert "liegt als Entwurf vor. Festgeschrieben wird erst auf der Rechnung." in text and "netto" not in text


@pytest.mark.skipif(NODE is None, reason="node nicht installiert")
def test_ohne_entwurf_entwurf_anlegen():
    """Ohne Entwurf wie bisher: „Entwurf anlegen“ für den nächsten Abschlag, kein „Entwurf öffnen“."""
    versendet = {"id": 3, "status": "versendet", "invoice_type": "abschlag_leistungsstand", "art_text": "1. Abschlag", "net_total": "1000"}
    sichtbar, knopf_weg, link_weg, _, text = _naechste([versendet])
    assert (sichtbar, knopf_weg, link_weg) == (False, False, True)
    assert "2. Abschlag nach Leistungsstand" in text
    assert _naechste([versendet], {"abschlag_leistungsstand": "gesperrt", "schluss": "gesperrt"})[0] is True  # nichts anzulegen: keine Karte


def test_markup_knopf_und_link():
    assert ('<button type="button" class="secondary" id="uNaechsteKnopf" data-klick="naechste-rechnung">Entwurf anlegen</button>'
            '<a class="btn secondary" id="uNaechsteLink" href="/projects" hidden>Entwurf öffnen</a>') in AKTE


# --- Punkt 5: Daten mit Jahr ----------------------------------------------------------------------------------------------------------------

@pytest.mark.skipif(NODE is None, reason="node nicht installiert")
def test_tag_lang_und_kurz():
    ablauf = "const berlinToday = () => '2026-10-29';\n" + _zeile(AKTE, "function tagKurz(d)") + "\n" + _zeile(AKTE, "function tagLang(d)") + """
      console.log(JSON.stringify([tagLang('2026-10-01'), tagKurz('2026-10-01'), tagLang('2025-12-31'), tagKurz('2025-12-31'), tagLang(null)]));
    """
    assert node_ausfuehren(ablauf, "Europe/Berlin") == ["01.10.2026", "01.10.", "31.12.2025", "31.12.2025", ""]


def test_daten_die_fuer_sich_stehen_mit_jahr():
    """Auftragsdaten (Auftragsdatum, Ausführung), geplanter Zeitraum der Arbeitsvorbereitung, Stand des LV und „überfällig seit“ über tagLang();
    die Phasen kommen vom Server, Listen (Einsätze, Berichte, Verlauf) bleiben kurz."""
    daten = _funktion(AKTE, "function auftragsdatenAnzeigen(){")
    assert "tagLang(order.execution_start)" in daten and "tagLang(order.execution_end)" in daten and "tagLang(order.order_date)" in daten
    assert "tagKurz" not in daten
    for stelle in ("'geplant '+esc(tagLang(av.planned_start))", "(${tagLang(q.invoice_date)})", "'überfällig seit '+tagLang(p.ueberfaellig_seit)"):
        assert stelle in AKTE, stelle
    assert "tagKurz(s." in AKTE and "tagKurz(b." in AKTE  # Einsätze und Berichte: Listen, kurz
