"""Version 1.9.314 (Lohn L2b, Punkt 2; Antwort 7 des Befunds L2): der Hinweis Rückfahrt in „Zeiten → Prüfen“.

    Regel        eine gebuchte Fahrzeit, die nach der letzten Arbeit ihres Tags beginnt (Beginn nicht vor dem Ende der letzten Buchung einer anderen
                 Zeitart), ergibt „Fahrzeit nach Arbeitsende – Rückfahrt? Feierabend ist auf der Baustelle.“ -- nicht die Hinfahrt, nicht die Fahrt
                 zwischen zwei Baustellen, nicht ein Tag nur mit Fahrzeit, nicht wenn eine Buchung des Tags keine Uhrzeiten hat (Reihenfolge unbekannt)
    Zeitraum     wie die Pausen: ab dem Tag nach „Abgeschlossen bis“ (sonst Monatsanfang) bis heute
    Wirkung      nichts abgezogen (Buchung und Tagesbilanz unverändert), weder Abschluss noch Lohndatei gesperrt, keine Zahl am Reiter
    Seite        Karte „Fahrzeit nach Arbeitsende“ (zur Info) mit Name, Tag, Fahrzeit mit Uhrzeiten, Arbeitsende und dem Hinweis; „Ändern“ nur, wer die
                 Buchung ändern darf (öffnet den Dialog wie in „Buchungen“)
Stehende Uhr 10.11.2026 (fester_tag): geprüft wird der 01.–10.11.2026.
"""

from datetime import date, datetime, time
from decimal import Decimal

import pytest

from app.models import TimeEntry, TimeTrackingSettings
from app.routers import zeiten as zeiten_router
from app.tagesbilanz import bilanz
from app.time_backoffice import abschluss_hindernisse, datev_fehlt
from app.zeiten import RUECKFAHRT, rueckfahrten, vor_dem_abschluss
from tests.test_v224_field_view import make_employee
from tests.test_v325_contract_basis import beauftragen, make_quote
from tests.test_v518_zeiten_seite import _node

D = Decimal


@pytest.fixture
def w(threaded_db_session, router_test_client, fester_tag):
    db = threaded_db_session
    order = beauftragen(db, make_quote(db, is_consumer=False, number="0714"))
    mia = make_employee(db, "M-1", "Mia", "Monteurin")
    db.commit()
    return {"db": db, "order": order, "mia": mia, "client": router_test_client}


def buchen(w, tag, art, von=None, bis=None, stunden=None):
    o = w["order"]
    beginn = datetime.combine(tag, time(*von)) if von else None
    ende = datetime.combine(tag, time(*bis)) if bis else None
    h = D(stunden) if stunden is not None else D((ende - beginn).seconds) / 3600
    r = TimeEntry(employee_id=w["mia"].id, project_id=o.project_id, order_id=o.id, work_date=tag, entry_type=art, hours=h.quantize(D("0.01")),
                  break_minutes=0, status="booked", started_at=beginn, ended_at=ende)
    w["db"].add(r)
    w["db"].commit()
    return r


@pytest.fixture
def tage(w):
    """Mo 02.11. Rückfahrt; Di 03.11. Hinfahrt; Mi 04.11. Fahrt zwischen zwei Baustellen; Do 05.11. nur Fahrzeit; Fr 06.11. dazu eine Dauer ohne Uhrzeit;
    Mo 09.11. Werkstatt und Fahrt genau ab ihrem Ende."""
    t = {}
    buchen(w, date(2026, 11, 2), "site", (7, 0), (11, 0))
    t["rueck"] = buchen(w, date(2026, 11, 2), "travel", (11, 30), (12, 15))
    buchen(w, date(2026, 11, 3), "travel", (6, 30), (7, 0))
    buchen(w, date(2026, 11, 3), "site", (7, 0), (11, 0))
    buchen(w, date(2026, 11, 4), "site", (7, 0), (9, 0))
    buchen(w, date(2026, 11, 4), "travel", (9, 0), (9, 30))
    buchen(w, date(2026, 11, 4), "site", (9, 30), (11, 0))
    buchen(w, date(2026, 11, 5), "travel", (7, 0), (8, 0))
    buchen(w, date(2026, 11, 6), "site", stunden="4")  # eine Dauer ohne Uhrzeit: die Reihenfolge des Tags ist unbekannt
    buchen(w, date(2026, 11, 6), "site", (7, 0), (8, 0))
    buchen(w, date(2026, 11, 6), "travel", (16, 0), (16, 30))
    buchen(w, date(2026, 11, 9), "workshop", (7, 0), (11, 0))
    t["genau"] = buchen(w, date(2026, 11, 9), "travel", (11, 0), (11, 20))
    return t


def test_nur_die_fahrzeit_nach_der_letzten_arbeit(w, tage):
    r = rueckfahrten(w["db"], date(2026, 11, 1), date(2026, 11, 10))
    assert [(x["id"], x["tag"], x["arbeitsende"], x["text"], x["name"], x["zeitart"]) for x in r] == [
        (tage["rueck"].id, date(2026, 11, 2), datetime(2026, 11, 2, 11, 0), RUECKFAHRT, "Mia Monteurin", "Fahrzeit"),
        (tage["genau"].id, date(2026, 11, 9), datetime(2026, 11, 9, 11, 0), RUECKFAHRT, "Mia Monteurin", "Fahrzeit")]
    assert RUECKFAHRT == "Fahrzeit nach Arbeitsende – Rückfahrt? Feierabend ist auf der Baustelle."
    assert rueckfahrten(w["db"], date(2026, 11, 3), date(2026, 11, 8)) == []  # außerhalb des Zeitraums nichts


def test_nichts_abgezogen_nichts_gesperrt(w, tage):
    db = w["db"]
    db.refresh(tage["rueck"])
    assert tage["rueck"].hours == D("0.75")
    b = bilanz(db, date(2026, 11, 2), date(2026, 11, 2), [w["mia"].id])
    assert (b.tage[w["mia"].id][date(2026, 11, 2)].fahrzeit, b.tage[w["mia"].id][date(2026, 11, 2)].arbeit) == (D("0.75"), D("4.75"))
    assert not [x for x in abschluss_hindernisse(db, date(2026, 11, 10)) if "Fahrzeit" in str(x)]
    assert not [x for x in datev_fehlt(db, date(2026, 11, 1), date(2026, 11, 30)) if "Fahrzeit" in x["text"]]
    assert not [x for x in vor_dem_abschluss(db, date(2026, 11, 1)) if "Fahrzeit" in x["text"]]


def test_pruefen_mit_rechten_und_ohne_zahl(w, tage):
    db = w["db"]
    admin = w["client"](db, zeiten_router.router, role="admin").get("/api/zeiten/pruefen").json()
    assert [(x["id"], x["darf_aendern"]) for x in admin["rueckfahrten"]] == [(tage["rueck"].id, True), (tage["genau"].id, True)]
    assert admin["zahlen"]["pruefen"] == sum(1 for t in admin["pausen"] if t["darf_buchen"])  # die Fahrzeiten zählen nicht
    ba = w["client"](db, zeiten_router.router, role="buero_auftrag").get("/api/zeiten/pruefen").json()
    assert [x["darf_aendern"] for x in ba["rueckfahrten"]] == [False, False]
    # nach dem Abschluss bis 05.11. beginnt der Zeitraum am 06.11.
    db.get(TimeTrackingSettings, 1).locked_until = date(2026, 11, 5)
    db.commit()
    admin = w["client"](db, zeiten_router.router, role="admin").get("/api/zeiten/pruefen").json()
    assert [x["id"] for x in admin["rueckfahrten"]] == [tage["genau"].id]


def test_seite_zeichnet_den_hinweis():
    zeile = {"id": 7, "name": "Mia Monteurin", "tag": "2026-11-02", "zeitart": "Fahrzeit", "started_at": "2026-11-02T11:30:00",
             "ended_at": "2026-11-02T12:15:00", "hours": "0.75", "arbeitsende": "2026-11-02T11:00:00", "order_number": "AUF-2026-0714",
             "order_title": "Halle", "text": "Fahrzeit nach Arbeitsende – Rückfahrt? Feierabend ist auf der Baustelle."}
    import json
    html = _node(("rueckfahrtHtml",), f"var z={json.dumps(zeile)};return [rueckfahrtHtml(z,0),rueckfahrtHtml(Object.assign({{}},z,{{darf_aendern:true}}),0)]")
    ohne, mit = html
    assert "Mia Monteurin · Mo 02.11." in ohne and "Fahrzeit 11:30–12:15 · 0,75 h · nach Arbeitsende 11:00 · AUF-2026-0714" in ohne
    assert "Fahrzeit nach Arbeitsende – Rückfahrt? Feierabend ist auf der Baustelle." in ohne and "Ändern" not in ohne
    assert 'data-aktion="rueckfahrt-aendern" data-i="0">Ändern</button>' in mit


def test_seite_aufbau():
    from tests import vorlagen_js as vj
    text = vj.seitentext("zeiten.html")[0]
    assert '<section class="karte" id="rueckfahrtKarte" aria-labelledby="rueckfahrtTitel" hidden>' in text
    assert "el('allesGut').hidden=!!(d.offene_zeiten.length||d.pausen.length||d.rueckfahrten.length||d.antraege.length);" in text
    assert "else if(a==='rueckfahrt-aendern'){var r=P.rueckfahrten[Number(b.dataset.i)];if(r)buchungDialogOeffnen(r)}" in text
