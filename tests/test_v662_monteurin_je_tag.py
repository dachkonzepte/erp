"""Version 1.9.262 (Stufe 6, R5a, Punkt 3): was die Monteurin von der Besetzung je Tag merkt -- „Heute“, „Nächste Tage“, Vorwahl, Kran-Termine.

    Heute         eine Karte nur an ihren Tagen; „Heutiger Einsatz · von–bis“ = ihre Folge von Tagen um heute (Antwort 11: ein Tag, der kein Arbeitstag ist,
                  unterbricht sie nicht, ein Arbeitstag ohne sie schon); „Mit dir“ nur, wer heute am Einsatz steht
    Nächste Tage  nur ihre Tage; „mit …“ je Tag nur, wer an dem Tag dran ist; „weiter“ nur, wenn sie heute dran ist
    Vorwahl       die Zeiterfassung wählt den Auftrag nur vor, wenn sie heute dran ist (folgt der Karte)
    /mobil        GET /api/field-view/today (assignments) und /upcoming nur mit Einsätzen, an denen sie (im Fenster) einen Tag hat
    Kran          jeder Termin im Kalender des Geräts nennt als Besetzung nur, wer an seinen Tagen dran ist
Der Bestand (alle an allen Tagen) zeigt alles wie bisher.
"""

from datetime import date, datetime, time, timedelta
from decimal import Decimal

import pytest

from app.heute import heute_fuer
from app.kran_kalender import soll
from app.main import create_resource
from app.models import OperationalResource
from app.planning import _load_slot, create_slot, list_todays_assignments_for_employee, list_upcoming_assignments_for_employee
from app.schemas import OperationalResourceCreate
from tests.test_v090_planning_board import setup_order
from tests.test_v633_besetzung_je_einsatz import _person

DI = date(2026, 11, 10)  # FESTER_TAG (Dienstag); KW 46
MO, MI, DO, FR = DI - timedelta(days=1), DI + timedelta(days=1), DI + timedelta(days=2), DI + timedelta(days=3)


@pytest.fixture()
def welt(threaded_db_session, fester_tag):
    db = threaded_db_session
    tom, mia, kai = _person(db, "M-1", "Tom"), _person(db, "M-2", "Mia"), _person(db, "M-3", "Kai")
    return {"db": db, "tom": tom.id, "mia": mia.id, "kai": kai.id, "a": setup_order(db, "662a"), "b": setup_order(db, "662b")}


def _einsatz(w, personen, von, bis, auftrag="a", **mehr):
    return create_slot(w["db"], order_id=w[auftrag].id, team_id=None, start_date=von, end_date=bis, planned_hours=Decimal("1"), trotzdem_planen=True,
                       besetzung=[{"employee_id": w[n], "tage": t} for n, t in personen.items()], **mehr)


def _heute(w, wer, tag=DI):
    return heute_fuer(w["db"], w[wer], heute=tag, jetzt=datetime.combine(tag, time(10)), ist_monteur=True)


def _naechste(h):
    return [(z["von"], z["bis"], z["nebentext"]) for z in h["naechste_tage"] if z["art"] == "einsatz"]


def test_karte_nur_an_ihren_tagen(welt):
    _einsatz(welt, {"tom": None, "mia": [MI, DO]}, MO, FR)
    assert [k["order_id"] for k in _heute(welt, "tom")["einsaetze"]] == [welt["a"].id]
    assert _heute(welt, "mia")["einsaetze"] == []  # heute (Di) steht Mia nicht am Einsatz
    assert [k["order_id"] for k in _heute(welt, "mia", MI)["einsaetze"]] == [welt["a"].id]


def test_von_bis_ist_ihre_folge_um_heute(welt):
    _einsatz(welt, {"tom": None, "mia": [MO, DI, DO]}, MO, FR)
    [tom] = _heute(welt, "tom")["einsaetze"]
    assert (tom["von"], tom["bis"]) == (MO, FR)  # alle Tage: wie bisher der Zeitraum
    [mia] = _heute(welt, "mia")["einsaetze"]
    assert (mia["von"], mia["bis"]) == (MO, DI)  # Mi ist ein Arbeitstag ohne sie -- die Folge endet am Di


def test_folge_ueber_das_wochenende(welt):
    fr_vorher = MO - timedelta(days=3)
    _einsatz(welt, {"mia": [fr_vorher, MO, DI]}, fr_vorher, DI)
    [k] = _heute(welt, "mia")["einsaetze"]
    assert (k["von"], k["bis"]) == (fr_vorher, DI)  # Sa und So sind keine Arbeitstage und unterbrechen nicht


def test_mit_dir_nur_wer_heute_dran_ist(welt):
    _einsatz(welt, {"tom": None, "mia": [MI], "kai": [DI]}, MO, FR)
    [k] = _heute(welt, "tom")["einsaetze"]
    assert k["angaben"]["mit_dir"] == ["Kai Test"]


def test_naechste_tage_nur_ihre_tage_und_mit_je_tag(welt):
    naechste_woche = MO + timedelta(days=7)
    _einsatz(welt, {"tom": None, "mia": [naechste_woche + timedelta(days=2), naechste_woche + timedelta(days=3)]}, naechste_woche,
             naechste_woche + timedelta(days=4), status="fest")
    titel = welt["a"].title or welt["a"].order_number
    mi, do, fr = (naechste_woche + timedelta(days=n) for n in (2, 3, 4))
    assert _naechste(_heute(welt, "tom")) == [(naechste_woche, naechste_woche + timedelta(days=1), titel), (mi, do, "mit Mia"), (fr, fr, titel)]
    assert _naechste(_heute(welt, "mia")) == [(mi, do, "mit Tom")]


def test_weiter_nur_wenn_sie_heute_dran_ist(welt):
    _einsatz(welt, {"tom": None, "mia": [MI, DO]}, MO, FR, status="fest")
    assert _naechste(_heute(welt, "tom")) == [(MI, FR, "weiter")]
    assert _naechste(_heute(welt, "mia")) == [(MI, DO, "mit Tom")]  # sie steht heute nicht am Einsatz -- kein „weiter“


def test_vorwahl_der_zeit_nur_an_ihren_tagen(welt):
    _einsatz(welt, {"tom": None, "mia": [MI]}, MO, FR)
    assert _heute(welt, "tom")["arbeitszeit"]["vorbelegt"] == welt["a"].id
    assert _heute(welt, "mia")["arbeitszeit"]["vorbelegt"] is None
    assert _heute(welt, "mia", MI)["arbeitszeit"]["vorbelegt"] == welt["a"].id


def test_mobil_einsaetze_heute_und_kommend(welt):
    db = welt["db"]
    _einsatz(welt, {"tom": None, "mia": [FR]}, MO, FR)
    _einsatz(welt, {"mia": [MO + timedelta(days=50)]}, MO, MO + timedelta(days=50), auftrag="b")
    assert [a["order_id"] for a in list_todays_assignments_for_employee(db, welt["mia"], DI)] == []
    assert [a["order_id"] for a in list_todays_assignments_for_employee(db, welt["mia"], FR)] == [welt["a"].id]
    assert [a["order_id"] for a in list_upcoming_assignments_for_employee(db, welt["mia"], today=DI)] == [welt["a"].id]  # B erst in 49 Tagen


def test_kran_termin_nennt_wer_an_seinen_tagen_dran_ist(welt):
    db = welt["db"]
    kran = create_resource(OperationalResourceCreate(resource_number="K-1", resource_type="Kran", name="Kran 30 m", identifier="K1"), db)
    db.get(OperationalResource, kran.id).outlook_mailbox = "kran@dachkonzepte.example"
    db.commit()
    slot = _einsatz(welt, {"tom": None, "kai": [DO, FR]}, MO, FR, geraete=[{"resource_id": kran.id, "tage": [MO, DI, DO, FR]}])
    termine = soll(_load_slot(db, slot.id))
    assert sorted((von, bis) for _, von, bis in termine) == [(MO, DI), (DO, FR)]
    besetzung = {von: [z for z in t["notes"].splitlines() if z.startswith("Besetzung")] for (_, von, _b), t in termine.items()}
    assert besetzung == {MO: ["Besetzung: Tom Test"], DO: ["Besetzung: Tom Test, Kai Test"]}


def test_zwei_einsaetze_desselben_auftrags_nur_der_ihrer_tage(welt):
    """Zwei Einsätze desselben Auftrags heute: die Karte nimmt nur den, an dem sie heute steht -- „Mit dir“ und von–bis kommen nicht aus dem anderen."""
    _einsatz(welt, {"tom": None, "mia": [DI]}, MO, FR)
    _einsatz(welt, {"kai": None, "mia": [MI]}, MO, FR)
    [k] = _heute(welt, "mia")["einsaetze"]
    assert (k["von"], k["bis"], k["angaben"]["mit_dir"]) == (DI, DI, ["Tom Test"])
