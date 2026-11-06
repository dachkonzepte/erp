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


# --- 1.9.242 (Nachtrag): der Browser im Klicktest geht um dieselben ganzen Tage mit ------------------------------------------------------

def _klicktest_modul(name):
    import importlib.util
    from pathlib import Path
    pfad = Path(__file__).resolve().parents[1] / "scripts" / "cdp_klicktest.py"
    spec = importlib.util.spec_from_file_location(name, pfad)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def test_klicktest_browser_geht_um_ganze_tage_mit():
    """1.9.242 (Nachtrag): an einem Tag ohne Arbeit liegt die laufende Uhr der Instanz Tage voraus -- der Browser um dieselben ganzen Tage."""
    from datetime import timezone
    modul = _klicktest_modul("cdp_klicktest_v642_tage")
    montag_10_uhr = datetime(2026, 11, 9, 10, 0, tzinfo=berlin_time.BERLIN).astimezone(timezone.utc).isoformat()
    freitag_10_uhr = datetime(2026, 11, 6, 10, 0, tzinfo=berlin_time.BERLIN).astimezone(timezone.utc).isoformat()
    samstag_15_uhr = datetime(2026, 11, 7, 15, 0, tzinfo=berlin_time.BERLIN).timestamp()
    freitag_23_30 = datetime(2026, 11, 6, 23, 30, tzinfo=berlin_time.BERLIN).timestamp()
    assert modul._tage_versatz_ms(f"{montag_10_uhr}|{samstag_15_uhr}") == 2 * 86_400_000
    assert modul._tage_versatz_ms(f"{freitag_10_uhr}|{freitag_23_30}") == 0  # Arbeitstag: der Browser bleibt, wie er war
    assert modul._tage_versatz_ms(f"{montag_10_uhr}|fest") == 0  # stehende Uhr: der Klicktest hält den Browser selbst an


def test_klicktest_tab_bekommt_den_tagesversatz(monkeypatch):
    """1.9.242 (Nachtrag): _browser_tage() setzt den Tagesversatz am Tab -- an einem Arbeitstag (0) nichts."""
    import asyncio
    modul = _klicktest_modul("cdp_klicktest_v642_tab")

    class Attrappe:
        def __init__(self):
            self.versatz = []

        async def browser_uhr(self, ms):
            self.versatz.append(ms)

    tab = Attrappe()
    monkeypatch.setattr(modul, "_BROWSER_TAGE_MS", 0)
    asyncio.run(modul._browser_tage(tab))
    monkeypatch.setattr(modul, "_BROWSER_TAGE_MS", 2 * 86_400_000)
    asyncio.run(modul._browser_tage(tab))
    assert tab.versatz == [2 * 86_400_000]


def test_klicktest_jeder_tab_bekommt_den_tagesversatz():
    """1.9.242 (Nachtrag): jede Funktion in cdp_klicktest.py, die einen Tab anlegt, ruft _browser_tage() auf."""
    import ast
    from pathlib import Path
    baum = ast.parse((Path(__file__).resolve().parents[1] / "scripts" / "cdp_klicktest.py").read_text(encoding="utf-8"))
    anlegen = 0
    for f in ast.walk(baum):
        if not isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        aufrufe = [n.func.id for n in ast.walk(f) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)]
        if "Tab" in aufrufe:
            anlegen += 1
            assert "_browser_tage" in aufrufe, f"{f.name}() legt einen Tab an, ohne _browser_tage()"
    assert anlegen == 2


@nur_mit_node
def test_browser_uhr_das_letzte_skript_gilt():
    """1.9.242 (Nachtrag): zwei Skripte BROWSER_UHR in einem Dokument -- der Versatz des zweiten gilt (erst der Tagesversatz des Werkzeugs,
    dann der volle Versatz eines Klicktests über Tab.browser_uhr())."""
    from tests.node_lauf import node_ausfuehren
    modul = _klicktest_modul("cdp_klicktest_v642_skript")
    erst, dann = 2 * 86_400_000, 2 * 86_400_000 + 3_600_000
    ergebnis = node_ausfuehren("globalThis.window=globalThis;const echt=Date.now();" + modul.BROWSER_UHR % erst + modul.BROWSER_UHR % dann
                               + "console.log(JSON.stringify({now: Date.now() - echt, neu: new Date().getTime() - echt, fest: new Date(5).getTime()}));")
    assert dann <= ergebnis["now"] < dann + 5_000 and dann <= ergebnis["neu"] < dann + 5_000
    assert ergebnis["fest"] == 5
