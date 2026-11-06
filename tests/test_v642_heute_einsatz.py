"""Version 1.9.242 (Stufe 6, R3b, Punkt 4): „Heute“ der Monteurin nach bildgrundlage/entwurf-stufe6/heute-einsatz.html.

    Karte        vorläufig/fest; „Mit dir“ = die Besetzung ohne sie selbst; wer heute abwesend ist, steht nur als „ist nicht da“ dabei, nie mit der Art;
                 Geräte nur an ihren Tagen („nur heute“, „auch …“); Notiz des Einsatzes; Baustellenhinweise der Arbeitsvorbereitung
    Wann         nur an einem Arbeitstag (nicht Wochenende, Feiertag, betriebsfreier Tag) und nicht bei eigener Abwesenheit -- heute_frei sagt, warum
    Nächste      je Einsatz die Arbeitstage in einer Zeile (Wochenende und Feiertag trennen), „weiter“ / „mit …“ / „vorläufig“; eigener Urlaub als
                 eigene Zeile („genehmigt“, ein offener Antrag „beantragt“)
    Test-Uhr     tests/uhr.py::arbeitstag_ab(): eine laufende Uhr ab heute beginnt an einem Tag ohne Arbeit am nächsten Arbeitstag (pytest und Klicktest)
"""

import json
import os
from datetime import date, datetime, time, timedelta
from decimal import Decimal

import pytest

from app import berlin_time
from app.heute import Tage, heute_fuer
from app.main import create_resource
from app.models import EmployeeAbsence, EmployeeAbsenceRequest, PlanningHoliday, WorkPreparation
from app.planning import create_slot
from app.schemas import OperationalResourceCreate
from tests.test_v090_planning_board import setup_order
from tests.test_v633_besetzung_je_einsatz import _kolonne, _person
from tests.uhr import arbeitstag_ab, uhr_festhalten

DI = date(2026, 11, 10)  # FESTER_TAG: Dienstag


@pytest.fixture()
def welt(threaded_db_session, fester_tag):
    db = threaded_db_session
    mia, ole, tom = _person(db, "M-1", "Mia"), _person(db, "M-2", "Ole"), _person(db, "M-3", "Tom")
    kran = create_resource(OperationalResourceCreate(resource_number="K-1", resource_type="Maschine", name="Kran 30 m", identifier="K1"), db)
    pritsche = create_resource(OperationalResourceCreate(resource_number="F-1", resource_type="Fahrzeug", name="Pritsche", identifier="HS 1"), db)
    return {"db": db, "mia": mia, "ole": ole, "tom": tom, "kran": kran.id, "pritsche": pritsche.id, "order": setup_order(db, "1"),
            "nord": _kolonne(db, "N", [mia, ole, tom])}


def _heute(w, wer="mia", tag=DI):
    return heute_fuer(w["db"], w[wer].id, heute=tag, jetzt=datetime.combine(tag, time(10)), ist_monteur=True)


def _einsatz(w, von=DI, bis=DI + timedelta(days=3), **mehr):
    werte = {"order_id": w["order"].id, "team_id": w["nord"].id, "start_date": von, "end_date": bis, "planned_hours": Decimal("1"),
             "trotzdem_planen": True, **mehr}
    return create_slot(w["db"], **werte)


def test_karte_mit_besetzung_geraeten_notiz_baustelle(welt):
    db = welt["db"]
    _einsatz(welt, status="fest", notes="Kran heute ab 8 Uhr", geraete=[{"resource_id": welt["pritsche"]},
                                                                         {"resource_id": welt["kran"], "tage": [DI]}])
    prep = db.query(WorkPreparation).filter_by(order_id=welt["order"].id).one()
    prep.site_notes = "Zufahrt über den Hof"
    db.commit()
    [k] = _heute(welt)["einsaetze"]
    assert k["angaben"] == {"status": "fest", "status_label": "fest", "mit_dir": ["Ole Test", "Tom Test"], "nicht_da": [],
                            "geraete": [{"name": "Pritsche", "zusatz": None}, {"name": "Kran 30 m", "zusatz": "nur heute"}],
                            "notiz": "Kran heute ab 8 Uhr", "baustelle": "Zufahrt über den Hof"}


def test_geraet_an_einzelnen_tagen(welt):
    _einsatz(welt, geraete=[{"resource_id": welt["kran"], "tage": [DI, DI + timedelta(days=2)]},
                            {"resource_id": welt["pritsche"], "tage": [DI + timedelta(days=1)]}])
    [k] = _heute(welt)["einsaetze"]
    assert k["angaben"]["geraete"] == [{"name": "Kran 30 m", "zusatz": "auch Do 12.11."}]  # die Pritsche ist heute nicht da
    assert k["angaben"]["status"] == "vorlaeufig"


def test_wer_fehlt_ist_nicht_da_nie_die_art(welt):
    db = welt["db"]
    _einsatz(welt)
    db.add(EmployeeAbsence(employee_id=welt["tom"].id, absence_type="Krankheit", absence_category="krankheit", start_date=DI, end_date=DI))
    db.commit()
    h = _heute(welt)
    [k] = h["einsaetze"]
    assert (k["angaben"]["mit_dir"], k["angaben"]["nicht_da"]) == (["Ole Test"], ["Tom Test"])
    assert "Krankheit" not in json.dumps(h, default=str)  # die Art einer anderen Person steht nirgends in der Antwort


def test_kein_arbeitstag_keine_karte(welt):
    _einsatz(welt, bis=DI + timedelta(days=6))
    samstag = DI + timedelta(days=4)
    h = _heute(welt, tag=samstag)
    assert (h["einsaetze"], h["heute_frei"]) == ([], "Heute ist kein Arbeitstag.")
    welt["db"].add(PlanningHoliday(holiday_date=DI + timedelta(days=1), name="Betriebsausflug"))
    welt["db"].commit()
    h = _heute(welt, tag=DI + timedelta(days=1))
    assert (h["einsaetze"], h["heute_frei"]) == ([], "Heute ist kein Arbeitstag.")
    assert _heute(welt)["heute_frei"] is None and len(_heute(welt)["einsaetze"]) == 1


def test_eigene_abwesenheit_keine_karte(welt):
    db = welt["db"]
    _einsatz(welt)
    db.add(EmployeeAbsence(employee_id=welt["mia"].id, absence_type="Urlaub", absence_category="urlaub", start_date=DI, end_date=DI))
    db.commit()
    h = _heute(welt)
    assert (h["einsaetze"], h["heute_frei"]) == ([], "Heute bist du nicht eingeplant: Urlaub.")
    assert [k["angaben"]["nicht_da"] for k in _heute(welt, "ole")["einsaetze"]] == [["Mia Test"]]


def test_naechste_tage_je_einsatz_ohne_wochenende_mit_urlaub(welt):
    db = welt["db"]
    _einsatz(welt, bis=DI + timedelta(days=7))  # Di 10. bis Di 17.: weiter Mi–Fr, Mo–Di
    order2 = setup_order(db, "2")
    _einsatz(welt, order_id=order2.id, team_id=None, employee_ids=[welt["mia"].id, welt["ole"].id], von=DI + timedelta(days=8),
             bis=DI + timedelta(days=8), status="vorlaeufig")
    db.add(EmployeeAbsence(employee_id=welt["mia"].id, absence_type="Urlaub", absence_category="urlaub", start_date=DI + timedelta(days=13),
                           end_date=DI + timedelta(days=19)))
    db.add(EmployeeAbsenceRequest(employee_id=welt["mia"].id, absence_type="Urlaub", absence_category="urlaub", start_date=DI + timedelta(days=9),
                                  end_date=DI + timedelta(days=9), status="pending"))
    db.commit()
    zeilen = [(z["art"], z["von"], z["bis"], z["objekt"] if z["art"] == "abwesenheit" else z["order_id"], z["nebentext"])
              for z in _heute(welt)["naechste_tage"]]
    tag = lambda n: DI + timedelta(days=n)  # noqa: E731
    assert zeilen == [
        ("einsatz", tag(1), tag(3), welt["order"].id, "weiter"),
        ("einsatz", tag(6), tag(7), welt["order"].id, "weiter"),
        ("einsatz", tag(8), tag(8), order2.id, "mit Ole · vorläufig"),
        ("abwesenheit", tag(9), tag(9), "Urlaub", "beantragt"),
        ("abwesenheit", tag(13), tag(14), "Urlaub", "genehmigt"),  # bis zum Ende des Fensters (14 Tage), am Wochenende nichts
    ]


def test_tage_kennt_freistellung_und_feiertag(welt):
    db = welt["db"]
    db.add(PlanningHoliday(holiday_date=DI + timedelta(days=2), name="Betriebsversammlung"))
    db.commit()
    t = Tage(db, welt["mia"].id, DI, DI + timedelta(days=6))
    assert sorted(t.arbeitstage) == [DI, DI + timedelta(days=1), DI + timedelta(days=3), DI + timedelta(days=6)]
    assert t.arbeitet(DI) and not t.arbeitet(DI + timedelta(days=2)) and not t.arbeitet(DI + timedelta(days=4))


# --- laufende Test-Uhr an einem Arbeitstag ----------------------------------------------------------------------------------------------

def test_arbeitstag_ab():
    assert arbeitstag_ab(date(2026, 11, 10)) == date(2026, 11, 10)  # Dienstag
    assert arbeitstag_ab(date(2026, 11, 7)) == date(2026, 11, 9)    # Samstag -> Montag
    assert arbeitstag_ab(date(2026, 12, 25)) == date(2026, 12, 28)  # 1. Weihnachtstag (Fr), Wochenende -> Montag
    assert arbeitstag_ab(date(2027, 1, 1)) == date(2027, 1, 4)      # Neujahr (Fr) -> Montag


def test_feste_uhr_beginnt_an_einem_arbeitstag():
    with uhr_festhalten(time(10), tag=date(2026, 11, 7)):  # „heute“ ist ein Samstag
        with uhr_festhalten():
            assert berlin_time.berlin_today() == date(2026, 11, 9)


def test_klicktest_uhr_beginnt_an_einem_arbeitstag(monkeypatch):
    import importlib.util
    from pathlib import Path
    pfad = Path(__file__).resolve().parents[1] / "scripts" / "cdp_klicktest.py"
    spec = importlib.util.spec_from_file_location("cdp_klicktest_v642", pfad)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    monkeypatch.setitem(os.environ, "ERP_KLICKTEST_HEUTE", "2026-11-07")
    start = datetime.fromisoformat(modul._uhr_marke("10:00").split("|")[0])
    assert start.astimezone(berlin_time.BERLIN).date() == date(2026, 11, 9)
    monkeypatch.setitem(os.environ, "ERP_KLICKTEST_HEUTE", "2026-11-10")
    start = datetime.fromisoformat(modul._uhr_marke("10:00").split("|")[0])
    assert start.astimezone(berlin_time.BERLIN).date() == date(2026, 11, 10)


# --- die Seite zeichnet die Angaben (in node, tests/node_lauf.py) -----------------------------------------------------------------------

from tests.test_v399_teil_updates_geld import im_browser, nur_mit_node  # noqa: E402


@nur_mit_node
def test_seite_zeichnet_die_angaben():
    angaben = {"status": "fest", "status_label": "fest", "mit_dir": ["Ole Offen", "Kai Kolb"], "nicht_da": ["Tom Test"],
               "geraete": [{"name": "Pritsche", "zusatz": None}, {"name": "Kran", "zusatz": "nur heute"}], "notiz": "ab 8 Uhr",
               "baustelle": "Zufahrt <Hof>"}
    # esc() der Seite liest der Ausleser nicht (Anführungszeichen im regulären Ausdruck) -- dieselbe Funktion hier
    esc = ("function esc(s){return String(s==null?'':s).replace(/[&<>'\"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;',"
           "\"'\":'&#39;','\"':'&quot;'}[c]})}")
    aufrufe = im_browser("mobil.html", ["angabeZeile", "einsatzAngaben"], esc,
                         f"AUFRUFE.push({{t: einsatzAngaben({json.dumps(angaben)})}});"
                         f"AUFRUFE.push({{t: einsatzAngaben({json.dumps({**angaben, 'mit_dir': [], 'nicht_da': ['Tom Test', 'Mia Test'], 'geraete': [], 'notiz': None, 'baustelle': None})})}});"
                         "AUFRUFE.push({t: einsatzAngaben(null)});")
    erste, zweite, keine = (a["t"] for a in aufrufe)
    assert ('data-angabe="mit"' in erste and "Ole Offen, Kai Kolb<span class=\"leise\"> · Tom Test ist nicht da</span>" in erste
            and "Pritsche · Kran <span class=\"leise\">nur heute</span>" in erste and ">ab 8 Uhr<" in erste and "Zufahrt &lt;Hof&gt;" in erste)
    assert zweite == ('<div class="einsatz-info" data-angabe="mit"><span class="was">Mit dir</span><span class="text">'
                      '<span class="leise">Tom Test, Mia Test sind nicht da</span></span></div>')
    assert keine == ""
