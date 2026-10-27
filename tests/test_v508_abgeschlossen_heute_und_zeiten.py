"""Seit 1.9.87 (Stufe 4, R5, Teil 1 Punkt 3): ein abgeschlossener oder stornierter Auftrag auf „Heute“ und in „Meine Zeiten“.

    Heute        nicht vorbelegt; ein offener Einsatz daneben ist vorbelegt (bis 1.9.86 zählte der abgeschlossene mit, dann keiner);
                 die Einsatzkarte trägt "auftrag_geschlossen" (Kennzeichen „Auftrag abgeschlossen“, beim stornierten kein „Bericht
                 anlegen“); läuft die Zeit auf einem solchen Auftrag, nur „Feierabend“ (kein „Zeitart wechseln“)
    Meine Zeiten an einer Buchung dort kein „⋮“, das Kennzeichen „Auftrag abgeschlossen“; „Pausen neu rechnen“ weicht dem Hinweis, wenn es
                 eine solche Buchung ändern würde
Die Bedienung prüft scripts/klicktest_zeiten_abgeschlossen.py (Bild „Heute mit abgeschlossenem Auftrag“).
"""

import re
from datetime import datetime, time, timedelta

from app.time_tracking import start_timer, stop_timer
from tests import vorlagen_js as vj
from tests.test_v325_contract_basis import beauftragen, make_quote
from tests.test_v471_heute_server import _als, _einsatz, _heute, welt  # noqa: F401  (Fixture)


def _zweiter(w, nummer, status=None):
    order = beauftragen(w["db"], make_quote(w["db"], is_consumer=False, number=nummer))
    order.title = f"Auftrag {nummer}"
    if status:
        order.status = status
    w["db"].commit()
    return order


def test_heute_vorbelegt_nur_den_offenen_und_kennzeichnet_den_geschlossenen(welt):  # noqa: F811
    """Angriff: heute zwei Einsätze, einer abgeschlossen -> vorbelegt der offene, die Karte des abgeschlossenen mit Kennzeichen.
    Gegenprobe: beide offen -> keiner vorbelegt (wie bisher), keine Kennzeichen."""
    zu = _zweiter(welt, "0508a")
    for order in (welt["order"], zu):
        _einsatz(welt, order, [(welt["heute"], welt["heute"])], [welt["mia"]])
    h = _heute(welt, welt["mia"])
    assert h["arbeitszeit"]["vorbelegt"] is None
    assert {k["order_id"]: k["auftrag_geschlossen"] for k in h["einsaetze"]} == {welt["order"].id: None, zu.id: None}
    zu.status = "abgeschlossen"
    welt["db"].commit()
    h = _heute(welt, welt["mia"])
    assert h["arbeitszeit"]["vorbelegt"] == welt["order"].id
    assert zu.id not in [a["id"] for a in h["arbeitszeit"]["auftraege"]]
    assert {k["order_id"]: k["auftrag_geschlossen"] for k in h["einsaetze"]} == {welt["order"].id: None, zu.id: "abgeschlossen"}


def test_heute_nur_ein_geschlossener_einsatz_nichts_vorbelegt(welt):  # noqa: F811
    _einsatz(welt, welt["order"], [(welt["heute"], welt["heute"])], [welt["mia"]])
    welt["order"].status = "storniert"
    welt["db"].commit()
    h = _heute(welt, welt["mia"])
    assert h["arbeitszeit"]["vorbelegt"] is None
    assert [k["auftrag_geschlossen"] for k in h["einsaetze"]] == ["storniert"]


def test_laufende_zeit_auf_geschlossenem_auftrag(welt):  # noqa: F811
    _einsatz(welt, welt["order"], [(welt["heute"], welt["heute"])], [welt["mia"]])
    start_timer(welt["db"], employee_id=welt["mia"].id, order_id=welt["order"].id, started_at=datetime.combine(welt["heute"], time(7)))
    assert _heute(welt, welt["mia"])["arbeitszeit"]["auftrag_geschlossen"] is None
    welt["order"].status = "abgeschlossen"
    welt["db"].commit()
    z = _heute(welt, welt["mia"])["arbeitszeit"]
    assert (z["zustand"], z["auftrag_geschlossen"]) == ("laeuft", "abgeschlossen")


def test_meine_zeiten_kennzeichnet_die_buchung(welt):  # noqa: F811
    _einsatz(welt, welt["order"], [(welt["heute"] - timedelta(days=7), welt["heute"])], [welt["mia"]])
    offen = _zweiter(welt, "0508b")
    _einsatz(welt, offen, [(welt["heute"], welt["heute"])], [welt["mia"]])
    for order, von, bis in ((welt["order"], time(7), time(9)), (offen, time(9), time(11))):
        row = start_timer(welt["db"], employee_id=welt["mia"].id, order_id=order.id, started_at=datetime.combine(welt["heute"], von))
        stop_timer(welt["db"], row.id, ended_at=datetime.combine(welt["heute"], bis))
    welt["order"].status = "abgeschlossen"
    welt["db"].commit()
    d = _als(welt, welt["mia"]).get("/api/field-view/meine-zeiten").json()
    zeilen = {z["order_id"]: z["auftrag_geschlossen"] for t in d["tage"] for z in t["zeilen"]}
    assert zeilen == {welt["order"].id: "abgeschlossen", offen.id: None}


def _funktion(text, name):
    m = re.search(r"function " + name + r"\([^)]*\)\{.*?\n  ?\}\n", text, flags=re.S)
    assert m, name
    return m[0]


def test_heute_seite():
    text = vj.seitentext("mobil.html")[0]
    karte = _funktion(text, "einsatzKarte")
    assert "+(k.auftrag_geschlossen?'<span class=\"einsatz-zu\" data-geschlossen=\"'+esc(k.auftrag_geschlossen)+'\">Auftrag '+esc(k.auftrag_geschlossen)+'</span>':'')" in karte
    assert "(k.auftrag_geschlossen==='storniert'?'':'<a class=\"knopf knopf-neutral knopf-klein\" href=\"/orders/'+k.order_id+'/service-reports\">Bericht anlegen</a>')" in karte
    laeuft = _funktion(text, "laeuftKarte")
    zweig = re.search(r"else if\(z\.auftrag_geschlossen\)knoepfe='[^;]*;", laeuft)[0]
    assert "feierabendKnopf" in zweig and "wechselKnopf" not in zweig
    assert laeuft.index("else if(z.auftrag_geschlossen)") < laeuft.index("id=\"wechselKnopf\"")


def test_meine_zeiten_seite():
    text = vj.seitentext("mobil_zeiten.html")[0]
    assert "if(z.laeuft||z.abgeschlossen||z.auftrag_geschlossen)return '<span class=\"platz\"></span>';" in _funktion(text, "menueHtml")
    zeile = _funktion(text, "zeileHtml")
    assert "'<span class=\"zeile-zu\" data-geschlossen=\"'+esc(z.auftrag_geschlossen)+'\">Auftrag '+esc(z.auftrag_geschlossen)+'</span>'" in zeile
    assert "+zu+weg+'</span>'" in zeile
    # seit 1.9.107 auch ohne Vorschlag kein Knopf (es fehlt nur die Pause einer Buchung ohne Uhrzeiten, test_v527)
    assert "(t.abgeschlossen||zu||!plan?'':'<button type=\"button\" class=\"knopf knopf-neutral knopf-klein\" data-aktion=\"pausen\"" in text
    assert "return t.zeilen.some(function(r){return r.id===b.id&&r.auftrag_geschlossen})" in text
