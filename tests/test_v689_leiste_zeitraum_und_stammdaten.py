"""Version 1.9.289 (Stufe 6, R5d, Punkt 7): die Leiste nennt den neuen Zeitraum, „40 h/Woche“ ohne Umbruch, das Untermenü der Stammdaten in Zeilen.

    Leiste     nach dem Ziehen einer Person oder eines Geräts in „Personen“ bzw. „Geräte“ (umsetzenZiehen()) nennt die Leiste den alten und den neuen Zeitraum
               („Lia Lang · Sturmschaden: 10.–11.11. → 11.–12.11.“), bis 1.9.288 nur den ersten neuen Tag („→ ab Mi 11.11.“); in eine andere Zeile gezogen
               steht der neue Zeitraum hinter dem alten, nur wenn er sich ändert. Der neue Zeitraum kommt vom Server (`ziel_tage` in der Antwort von
               umsetzen(), in Arbeitstagen -- Do–Fr um einen Tag weiter heißt Fr und der nächste Mo), die Seite rechnet ihn nicht nach
    Stunden    „40 h/Woche“ in der Spalte Funktion der Mitarbeiter bricht nicht um (`<span class="nw">`, `.nw{white-space:nowrap}`)
    Untermenü  unter 1400 px oben über der Karte (seit 1.9.278) -- seit 1.9.289 in Zeilen (flex-wrap) statt seitlich rollend; unter 850 px eine Zeile, die
               im Rahmen rollt
Die Abläufe mit echter Maus prüft scripts/klicktest_plantafel_rueckgaengig.py, Untermenü und Stunden bei 1400, 1280 und 412 px
scripts/klicktest_stammdaten_breite.py.
"""

import re

from app.tag_aktionen import tag_setzen, umsetzen
from tests.test_v399_teil_updates_geld import nur_mit_node
from tests.test_v660_besetzung_je_tag import _tag, welt  # noqa: F401 -- welt ist eine Fixture
from tests.test_v667_tag_setzen import _einsatz, _iso
from tests.test_v671_inaktive_mitarbeiter_ausblenden import ROOT
from tests.test_v682_leiste_rueckgaengig import UMKEHRUNG, _lauf

STAMMDATEN = ROOT / "app/templates/master_data.html"


# --- Server: ziel_tage ---------------------------------------------------------------------------------------------------------------

def test_umsetzen_nennt_die_zieltage_in_arbeitstagen(welt):
    db = welt["db"]
    slot = _einsatz(welt, "a", 0, 4, team=welt["nord"].id)
    tag_setzen(db, order_id=welt["a"].id, tag=_tag(3), employee_id=welt["kai"])
    tag_setzen(db, order_id=welt["a"].id, tag=_tag(4), employee_id=welt["kai"])
    e = umsetzen(db, slot_id=slot.id, employee_id=welt["kai"], tage=[_tag(3), _tag(4)], ziel_tag=_tag(4))
    assert e["ziel_tage"] == [_iso(4), _iso(7)]  # Do–Fr um einen Tag weiter: Fr und der nächste Mo
    # auch beim Prüfen (schreibt nichts) und über die API
    p = umsetzen(db, slot_id=slot.id, employee_id=welt["kai"], tage=[_tag(4)], ziel_tag=_tag(1), pruefen=True)
    assert p["ziel_tage"] == [_iso(1)]
    r = welt["client"].post(f"/api/planning/slots/{slot.id}/umsetzen", json={"employee_id": welt["kai"], "tage": [_iso(4), _iso(7)], "ziel_tag": _iso(1)})
    assert r.status_code == 200, r.text
    assert r.json()["ziel_tage"] == [_iso(1), _iso(2)]


# --- Seite: Text der Leiste ------------------------------------------------------------------------------------------------------------

def _band(war: str, zeile_id: str, tag: int, ziel_tage: list[str]) -> str:
    aufrufe = _lauf(f"await umsetzenZiehen({war},{{dataset:{{zeile:'person',id:'{zeile_id}'}}}},{tag});AUFRUFE.push({{band:band()}});",
                    antwort={"slot_id": 1, "ziel_tage": ziel_tage, "umkehrung": UMKEHRUNG})
    return re.match(r'<span class="zug-band-text">(.*?)</span>', aufrufe[-1]["band"]).group(1)


TOM_DO_FR = "{id:1,zeile:'person',wer:1,von:'2026-11-12',bis:'2026-11-13'}"


@nur_mit_node
def test_leiste_mit_dem_neuen_zeitraum_vom_server():
    # eigene Zeile: alter und neuer Zeitraum, der neue aus ziel_tage (Fr und der nächste Mo -- die Seite rechnet keine Arbeitstage nach)
    assert _band(TOM_DO_FR, "1", 4, ["2026-11-13", "2026-11-16"]) == "Tom Monteur · Wasserturm: 12.–13.11. → 13.–16.11."
    # ein Tag
    assert _band("{id:1,zeile:'person',wer:1,von:'2026-11-10',bis:'2026-11-10'}", "1", 2, ["2026-11-11"]) == "Tom Monteur · Wasserturm: 10.11. → 11.11."
    # andere Zeile, anderer Tag: der neue Zeitraum hinter dem alten
    assert _band(TOM_DO_FR, "2", 4, ["2026-11-13", "2026-11-16"]) == "Wasserturm 12.–13.11. → 13.–16.11.: Tom Monteur → Kai Kolb"
    # andere Zeile, dieselben Tage: ohne Pfeil
    assert _band(TOM_DO_FR, "2", 3, ["2026-11-12", "2026-11-13"]) == "Wasserturm 12.–13.11.: Tom Monteur → Kai Kolb"


def test_kein_ab_mehr_in_der_leiste():
    seite = (ROOT / "app/templates/planning.html").read_text(encoding="utf-8")
    assert "→ ab ${tagText(zielTag)}" not in seite and "', ab '+tagText(zielTag)" not in seite
    assert "const text=a=>{const zt=a.ziel_tage||[],neu=zt.length?fmtSpanne(zt[0],zt[zt.length-1]):spanne;" in seite
    assert "a=>bandZeigen(text(a),a.umkehrung))}" in seite


# --- Stammdaten -------------------------------------------------------------------------------------------------------------------------

def _regeln(seite: str, breite: int) -> str:
    """der Inhalt der Regel @media(max-width:<breite>px){…} (bis zur schließenden Klammer auf gleicher Ebene)"""
    start = seite.index(f"@media(max-width:{breite}px){{") + len(f"@media(max-width:{breite}px){{")
    tiefe, i = 1, start
    while tiefe:
        tiefe += {"{": 1, "}": -1}.get(seite[i], 0)
        i += 1
    return seite[start:i - 1]


def test_untermenue_in_zeilen_unter_1400_und_rollend_unter_850():
    seite = STAMMDATEN.read_text(encoding="utf-8")
    breit = _regeln(seite, 1400)
    assert ".side{position:static;display:flex;flex-wrap:wrap}" in breit and "overflow:auto" not in breit.split(".side{", 1)[1].split("}", 1)[0]
    # die Knöpfe so breit wie ihr Text (sonst nähme jeder mit width:100% eine ganze Zeile -- in einer Zeile ohne Umbruch schrumpften sie bis 1.9.288 von
    # selbst), ein Knopf bricht nicht in sich um
    assert ".side button{width:auto;white-space:nowrap}" in breit
    assert ".side{flex-wrap:nowrap;overflow:auto}" in _regeln(seite, 850)
    assert seite.index("@media(max-width:1400px)") < seite.index("@media(max-width:850px)")  # die engere Regel steht danach und gewinnt


def test_stunden_je_woche_ohne_umbruch():
    seite = STAMMDATEN.read_text(encoding="utf-8")
    assert "<span class=\"nw\">${Number(x.weekly_hours).toLocaleString('de-DE')} h/Woche</span>" in seite
    assert ".nw{white-space:nowrap}" in seite
