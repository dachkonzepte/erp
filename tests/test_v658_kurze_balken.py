"""Version 1.9.258 (Stufe 6, R4b, Punkt 7): kurze Balken -- zwei Zeilen mit Silbentrennung, die Vornamen ganz weg, erst dann „…“.

    Reihenfolge  eine Zeile mit Vornamen -> zwei Zeilen mit Vornamen -> eine Zeile ohne -> zwei Zeilen ohne -> „…“ (zwei Zeilen; ist ein Wort breiter als
                 der Balken, eine Zeile); ohne Zusatz gleich zwei Zeilen, dann „…“ (balkenEinpassen(), Klassen zweizeilig / ohne-namen / gekuerzt)
    Messen       Breite genau über einen Range (ein Überstand unter 1 px zeigt schon „…“), Höhe mit 1 px Spiel; nach jedem Zeichnen der Tafel
    Aussehen     zwei Zeilen 10,5 px auf 11 px Zeilenhöhe, höchstens zwei (line-clamp), hyphens:auto unter lang="de"; ohne Vornamen fehlt der Zusatz „· …“ ganz
    Termine      einer Person (zweizeilig seit 1.9.250) bleiben, wie sie sind
Im Browser: scripts/klicktest_plantafel_tafel.py (Probebalken je Breite, „Am Was-serturm 4“ am Kran, bei 1280 px ab 2 Arbeitstagen ungekürzt) und
klicktest_plantafel_personen.py (dasselbe in „Personen“ und „Geräte“, „Wartung“ ohne „…“). Headless trennt Chrome nur mit den Trenndaten des installierten
Chrome im Profil (scripts/cdp_klicktest.py::trenndaten_einlegen(), klicktest_main(silbentrennung=True)).
"""

import re
import shutil
from pathlib import Path

import pytest

from tests.test_v399_teil_updates_geld import im_browser, nur_mit_node

ROOT = Path(__file__).resolve().parent.parent
SEITE = (ROOT / "app/templates/planning.html").read_text(encoding="utf-8")

# Ein nachgestellter Balken: passt(klassen) sagt, ob der Text in diesem Zustand in die Breite bzw. Höhe passt
VORBEREITUNG = """
function balken(passt, mitZusatz) {
  const kl = new Set(['slot', 'fest']);
  const s = {classList: {add: (...c) => c.forEach(x => kl.add(x)), remove: (...c) => c.forEach(x => kl.delete(x)), contains: c => kl.has(c)}, kl};
  const t = {querySelector: q => (q === '.leise' && mitZusatz ? {} : null), getBoundingClientRect: () => ({width: 100}), clientHeight: 22,
             get scrollHeight() { return passt(kl).hoch ? 23 : 34; }, breite: () => (passt(kl).breit ? 99.5 : 100.4)};
  s.querySelector = q => (q === '.slot-text' ? t : null);
  return s;
}
var document = {createRange: () => { let n; return {selectNodeContents: x => { n = x; }, getBoundingClientRect: () => ({width: n.breite()})}; }};
const FAELLE = {
  eine_zeile:      kl => ({breit: true, hoch: true}),
  zwei_zeilen:     kl => ({breit: kl.has('zweizeilig'), hoch: true}),
  eine_ohne:       kl => ({breit: kl.has('ohne-namen') && !kl.has('zweizeilig'), hoch: true}),
  zwei_ohne:       kl => ({breit: kl.has('ohne-namen') && kl.has('zweizeilig'), hoch: true}),
  wort_zu_breit:   kl => ({breit: false, hoch: true}),
  zu_hoch:         kl => ({breit: kl.has('zweizeilig'), hoch: false}),
};
"""


def _klassen(fall, mit_zusatz=True):
    ablauf = (f"const s = balken(FAELLE.{fall}, {str(mit_zusatz).lower()}); balkenEinpassen({{querySelectorAll: () => [s]}});"
              "AUFRUFE.push(['zweizeilig', 'ohne-namen', 'gekuerzt'].filter(c => s.kl.has(c)));")
    [erg] = im_browser("planning.html", ["balkenEinpassen", "textPasst"], VORBEREITUNG, ablauf)
    return erg


@nur_mit_node
@pytest.mark.parametrize("fall, mit_zusatz, klassen", [
    ("eine_zeile", True, []),
    ("zwei_zeilen", True, ["zweizeilig"]),                       # erst zwei Zeilen -- mit den Vornamen
    ("eine_ohne", True, ["ohne-namen"]),                         # dann ohne Vornamen auf einer Zeile
    ("zwei_ohne", True, ["zweizeilig", "ohne-namen"]),           # dann ohne Vornamen auf zwei
    ("zu_hoch", True, ["zweizeilig", "ohne-namen", "gekuerzt"]),  # erst danach „…“ (am Ende der zweiten Zeile)
    ("wort_zu_breit", True, ["ohne-namen", "gekuerzt"]),         # ein Wort breiter als der Balken: „…“ auf einer Zeile
    ("zu_hoch", False, ["zweizeilig", "gekuerzt"]),              # ohne Zusatz gleich „…“ nach zwei Zeilen
])
def test_reihenfolge(fall, mit_zusatz, klassen):
    assert _klassen(fall, mit_zusatz) == klassen


def test_aussehen_und_aufruf():
    stil = SEITE[SEITE.index("<style>"):SEITE.index("</style>")]
    assert '<html lang="de">' in SEITE  # Silbentrennung braucht die Sprache
    assert "  .slot.zweizeilig{white-space:normal;padding:0 5px}" in stil
    zwei = re.search(r"\.slot\.zweizeilig \.slot-text\{([^}]*)\}", stil).group(1)
    for teil in ("-webkit-line-clamp:2", "max-height:22px", "font-size:10.5px", "line-height:11px", "hyphens:auto"):
        assert teil in zwei, teil
    assert "  .slot.ohne-namen .slot-text .leise{display:none}" in stil
    assert "querySelectorAll('.slot:not(.zwei)')" in SEITE  # die Termine einer Person bleiben
    rb = SEITE[SEITE.index("function renderBoard(){"):]
    assert rb.index("balkenEinpassen(document.getElementById('planner'))") < rb.index("ziehenEinrichten()")  # nach dem Zeichnen jeder Ansicht
    assert "r.getBoundingClientRect().width<=t.getBoundingClientRect().width" in SEITE  # Breite genau, nicht scrollWidth


def test_werkzeug_legt_trenndaten_ins_profil(tmp_path):
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    from cdp_klicktest import trenndaten_einlegen
    quelle = tmp_path / "hyphen-data" / "120.0"
    quelle.mkdir(parents=True)
    (quelle / "hyph-de-1996.hyb").write_bytes(b"x")
    profil = tmp_path / "profil"
    profil.mkdir()
    assert trenndaten_einlegen(profil, tmp_path / "hyphen-data") is True
    assert (profil / "hyphen-data" / "120.0" / "hyph-de-1996.hyb").read_bytes() == b"x"
    shutil.rmtree(profil / "hyphen-data")
    assert trenndaten_einlegen(profil, tmp_path / "fehlt") is False and not (profil / "hyphen-data").exists()


def test_neu_zeichnen_wenn_die_tafel_schmaler_wird():
    """1.9.258 (Nachtrag): erscheint der Bildlauf der Seite (sie wird durch die Zeilen höher als das Fenster), ist die Tafel rund 15 px schmaler -- ohne
    resize des Fensters. Bis zum Nachtrag rechnete sie mit der alten Breite und rollte bei 1440 px waagrecht (Bild „Personen“ im Endlauf von R4b)."""
    assert "geoBreite=box?box.clientWidth:null;" in SEITE[SEITE.index("function geometrie(dates){"):]
    beobachter = re.search(r"if\(window\.ResizeObserver\)new ResizeObserver\(\(\)=>\{(.*?)\}\)\.observe\(document\.getElementById\('planner'\)\);", SEITE)
    assert beobachter and "b!==geoBreite" in beobachter.group(1) and "renderBoard()" in beobachter.group(1)
