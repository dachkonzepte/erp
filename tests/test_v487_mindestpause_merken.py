"""Seit 1.9.62 (Stufe 4, R3 Nachrunde, Punkt 3): die eingetragene Mindestpause wird gemerkt (time_entries.min_break_minutes).

    Gesetzt        Nachtrag („Pause mindestens“, eine Dauer: die Pause), Ändern (pause_minuten -- ohne Angabe bleibt sie, Regel 22), Kolonne
                   (die Pause der Gruppe), Feierabend (die eingegebene Pause, ohne Eingabe 0), Ende nachtragen, Zeitart wechseln (0)
    Neu rechnen    nie unter die Mindestpause; eine Buchung ohne Wert (von vor 1.9.62): die abgezogene Pause gilt als Mindestpause -- neu
                   rechnen kann dort nur mehr Pause ergeben, danach steht die bisherige Pause als Mindestpause fest
    Tag            „passt nicht“ nur, wenn neu rechnen etwas ändern würde
    Ändern         „Pause mindestens“ ist mit der Mindestpause vorbelegt (Meine Zeiten liefert sie je Zeile; die Vorschau beim Ändern ohne
                   Angabe rechnet mit ihr)
"""

from datetime import datetime, time, timedelta
from decimal import Decimal

from app.models import TimeEntry, TimeEntryGroupMember
from app.routers import time_tracking as time_tracking_router
from app.time_tracking import start_timer, stop_timer
from tests import vorlagen_js as vj
from tests.test_v471_heute_server import _als, _einsatz, welt  # noqa: F401  (Fixture)


def _monteurin(w):
    _einsatz(w, w["order"], [(w["heute"] - timedelta(days=7), w["heute"])], [w["mia"], w["tom"]])
    return _als(w, w["mia"])


def _buero(w):
    return w["client"](w["db"], time_tracking_router.router, role="admin")


def _zeit(w, emp, von, bis, tag, pause=0):
    row = start_timer(w["db"], employee_id=emp.id, order_id=w["order"].id, started_at=datetime.combine(tag, von))
    return stop_timer(w["db"], row.id, ended_at=datetime.combine(tag, bis), break_minutes=pause)


def _nachtrag(client, w, von, bis, tag, **mehr):
    antwort = client.post("/api/time-entries", json={"employee_id": w["mia"].id, "order_id": w["order"].id, "work_date": tag.isoformat(),
                                                     "von": von, "bis": bis, **mehr})
    assert antwort.status_code == 200, antwort.text
    return antwort.json()


def _eintrag(w, entry_id):
    w["db"].expire_all()
    e = w["db"].get(TimeEntry, entry_id)
    return e.min_break_minutes, e.break_minutes, e.hours


def _tag(client, tag):
    t = client.get("/api/time-entries/tagespause", params={"work_date": tag.isoformat()}).json()
    return t["abgezogen"], t["nach_zeitregel"], t["passt"], [(b["id"], b["pause_alt"], b["pause_neu"]) for b in t["buchungen"]]


# --- gesetzt bei Nachtrag, Feierabend, Ende nachtragen, Zeitart wechseln ----------------------------------------------------------------

def test_nachtrag_merkt_die_eingetragene_mindestpause(welt):  # noqa: F811
    """Nachtrag 07:00–11:00 mit „Pause mindestens“ 45 -> gemerkt 45 (Pause 45); ohne Angabe -> 0. Die Antwort nennt sie."""
    client = _monteurin(welt)
    mit = _nachtrag(client, welt, "07:00", "11:00", welt["gestern"], break_minutes=45)
    ohne = _nachtrag(client, welt, "12:00", "14:00", welt["gestern"])
    assert (mit["min_break_minutes"], mit["pause"]) == (45, 45)
    assert _eintrag(welt, mit["id"]) == (45, 45, Decimal("3.25"))
    assert _eintrag(welt, ohne["id"]) == (0, 0, Decimal("2"))


def test_feierabend_ende_nachtragen_und_zeitart_wechseln(welt):  # noqa: F811
    """Feierabend ohne Eingabe -> 0, mit Pause 15 -> 15; Ende nachtragen mit 20 -> 20; Zeitart wechseln -> 0 an der geschlossenen Zeit."""
    client = _monteurin(welt)
    h, mia = welt["heute"], welt["mia"]
    vortag = start_timer(welt["db"], employee_id=mia.id, order_id=welt["order"].id, started_at=datetime.combine(welt["gestern"], time(7)))
    ende = client.post(f"/api/time-entries/{vortag.id}/ende-nachtragen", json={"ende": f"{welt['gestern'].isoformat()}T11:00", "pause_minuten": 20})
    assert ende.status_code == 200, ende.text
    assert _eintrag(welt, vortag.id)[:2] == (20, 20)
    a = start_timer(welt["db"], employee_id=mia.id, order_id=welt["order"].id, started_at=datetime.combine(h, time(6)))
    assert client.post(f"/api/time-entries/{a.id}/stop", json={"ended_at": f"{h.isoformat()}T07:00"}).status_code == 200
    assert _eintrag(welt, a.id)[:2] == (0, 0)
    b = start_timer(welt["db"], employee_id=mia.id, order_id=welt["order"].id, started_at=datetime.combine(h, time(7)))
    assert client.post(f"/api/time-entries/{b.id}/stop", json={"ended_at": f"{h.isoformat()}T08:00", "break_minutes": 15}).status_code == 200
    assert _eintrag(welt, b.id)[:2] == (15, 15)
    c = start_timer(welt["db"], employee_id=mia.id, order_id=welt["order"].id, started_at=datetime.combine(h, time(8)))
    wechsel = client.post(f"/api/time-entries/{c.id}/zeitart-wechseln", json={"entry_type": "travel"})
    assert wechsel.status_code == 200, wechsel.text
    assert _eintrag(welt, c.id)[0] == 0


# --- Ändern: gesetzt mit pause_minuten, ohne Angabe bleibt sie ---------------------------------------------------------------------------

def test_aendern_setzt_die_mindestpause_und_behaelt_sie_ohne_angabe(welt):  # noqa: F811
    """Angriff: 07:00–12:00 mit 45 nachgetragen; auf 07:00–13:00 geändert ohne „pause_minuten“ -> die 45 bleiben (bis 1.9.61: 0, die
    Regel gäbe bei 6 h keine Pause). Mit pause_minuten 0 -> 0. Nur die Notiz geändert -> unverändert. Die Vorschau beim Ändern ohne Angabe
    rechnet mit der gemerkten."""
    client = _monteurin(welt)
    g = welt["gestern"]
    row = _nachtrag(client, welt, "07:00", "12:00", g, break_minutes=45)
    v = client.get("/api/time-entries/nachtrag-vorschau", params={"work_date": g.isoformat(), "von": "07:00", "bis": "13:00",
                                                                   "entry_id": row["id"]}).json()
    assert v["pause"] == 45
    assert client.put(f"/api/time-entries/{row['id']}", json={"von": "07:00", "bis": "13:00"}).status_code == 200
    assert _eintrag(welt, row["id"]) == (45, 45, Decimal("5.25"))
    assert client.put(f"/api/time-entries/{row['id']}", json={"von": "07:00", "bis": "13:00", "pause_minuten": 0}).status_code == 200
    assert _eintrag(welt, row["id"]) == (0, 0, Decimal("6"))
    assert client.put(f"/api/time-entries/{row['id']}", json={"von": "07:00", "bis": "13:00", "pause_minuten": 30}).status_code == 200
    assert client.put(f"/api/time-entries/{row['id']}", json={"notes": "Rinne"}).status_code == 200
    assert _eintrag(welt, row["id"]) == (30, 30, Decimal("5.5"))


def test_buero_dauer_und_kolonne_merken_die_pause(welt):  # noqa: F811
    """Büro: Dauer 4 h mit Pause 30 -> 30; geändert auf 5 h mit 15 -> 15; nur die Notiz -> 15. Kolonne (Dauer) mit Pause 20 -> je Mitglied 20,
    die Kolonne geändert mit 10 -> 10."""
    buero = _buero(welt)
    g = welt["gestern"]
    dauer = buero.post("/api/time-entries", json={"employee_id": welt["tom"].id, "order_id": welt["order"].id, "work_date": g.isoformat(),
                                                  "hours": "4", "break_minutes": 30})
    assert dauer.status_code == 200, dauer.text
    assert _eintrag(welt, dauer.json()["id"]) == (30, 30, Decimal("4"))
    assert buero.put(f"/api/time-entries/{dauer.json()['id']}", json={"hours": "5", "break_minutes": 15}).status_code == 200
    assert buero.put(f"/api/time-entries/{dauer.json()['id']}", json={"notes": "nachgefragt"}).status_code == 200
    assert _eintrag(welt, dauer.json()["id"]) == (15, 15, Decimal("5"))
    gruppe = buero.post("/api/time-entry-groups", json={"employee_ids": [welt["mia"].id, welt["tom"].id], "team_id": welt["team"].id,
                                                        "order_id": welt["order"].id, "work_date": welt["heute"].isoformat(), "hours": "6",
                                                        "break_minutes": 20})
    assert gruppe.status_code == 200, gruppe.text
    ids = [m.time_entry_id for m in welt["db"].query(TimeEntryGroupMember).filter_by(group_id=gruppe.json()["id"]).all()]
    assert sorted(_eintrag(welt, i)[:2] for i in ids) == [(20, 20), (20, 20)]
    assert buero.put(f"/api/time-entry-groups/{gruppe.json()['id']}", json={"break_minutes": 10}).status_code == 200
    assert sorted(_eintrag(welt, i)[:2] for i in ids) == [(10, 10), (10, 10)]


# --- neu rechnen nie unter die Mindestpause --------------------------------------------------------------------------------------------

def test_bewusst_laengere_pause_bleibt_nach_dem_loeschen(welt):  # noqa: F811
    """Angriff (Auftrag): 08:00–12:00 und 12:30–16:30 mit „Pause mindestens“ 60; die Buchung davor gelöscht -> kein Hinweis am Tag, die
    Pause bleibt 60 (bis 1.9.61: „passt nicht“, neu rechnen hätte 0 gebucht). Gegenprobe am Vortag: dieselben Zeiten ohne Mindestpause
    (die 30 min kamen aus der Regel) -> nach dem Löschen „passt nicht“ mit 30 -> 0."""
    client = _monteurin(welt)
    g, vortag = welt["gestern"], welt["gestern"] - timedelta(days=1)
    erste = _zeit(welt, welt["mia"], time(8), time(12), g)
    zweite = _nachtrag(client, welt, "12:30", "16:30", g, break_minutes=60)
    assert zweite["pause"] == 60
    assert client.delete(f"/api/time-entries/{erste.id}").status_code == 200
    assert _tag(client, g) == (60, 60, True, [])
    assert _eintrag(welt, zweite["id"])[:2] == (60, 60)
    # Gegenprobe
    frueh = _zeit(welt, welt["mia"], time(8), time(12), vortag)
    spaet = _nachtrag(client, welt, "12:30", "16:30", vortag)
    assert spaet["pause"] == 30
    assert client.delete(f"/api/time-entries/{frueh.id}").status_code == 200
    assert _tag(client, vortag) == (30, 0, False, [(spaet["id"], 30, 0)])


def test_mindestpause_ueber_der_regel_passt(welt):  # noqa: F811
    """Eine Buchung mit Mindestpause 60 allein (5 h) -- die Regel gäbe 0: der Tag passt (bis 1.9.61: „passt nicht“, 60 -> 0)."""
    client = _monteurin(welt)
    _nachtrag(client, welt, "07:00", "12:00", welt["gestern"], break_minutes=60)
    assert _tag(client, welt["gestern"]) == (60, 60, True, [])


def test_alte_buchung_ohne_wert_neu_rechnen_nur_nach_oben(welt):  # noqa: F811
    """Buchungen von vor 1.9.62 (ohne gemerkten Wert): die abgezogene Pause gilt als Mindestpause.
    Angriff 1: 06:00–13:00 (30 min) und 13:00–16:00 (15 min), die erste gelöscht -> die zweite behält 15 (nach unten nicht), der Tag passt.
    Angriff 2: 07:00–15:00 mit 0 min (die Regel will 30) -> „passt nicht“ 0 -> 30, gebucht wie gezeigt; danach steht die bisherige Pause 0
    als Mindestpause fest."""
    client = _monteurin(welt)
    g, vortag = welt["gestern"], welt["gestern"] - timedelta(days=1)
    a = _zeit(welt, welt["mia"], time(6), time(13), g)
    b = _zeit(welt, welt["mia"], time(13), time(16), g)
    c = _zeit(welt, welt["mia"], time(7), time(15), vortag)
    for row in (a, b, c):
        row.min_break_minutes = None
    c.break_minutes, c.hours = 0, Decimal("8")
    welt["db"].commit()
    assert (a.break_minutes, b.break_minutes) == (30, 15)
    assert client.delete(f"/api/time-entries/{a.id}").status_code == 200
    assert _tag(client, g) == (15, 15, True, [])
    assert _tag(client, vortag) == (0, 30, False, [(c.id, 0, 30)])
    gebucht = client.post("/api/time-entries/pausen-neu-rechnen", json={"work_date": vortag.isoformat(), "buchungen": [{"id": c.id, "pause": 30}]})
    assert gebucht.status_code == 200, gebucht.text
    assert _eintrag(welt, c.id) == (0, 30, Decimal("7.5"))
    assert _tag(client, vortag) == (30, 30, True, [])


# --- „Ändern“ vorbelegt ----------------------------------------------------------------------------------------------------------------

def test_meine_zeiten_liefert_die_mindestpause_fuer_aendern(welt):  # noqa: F811
    """Meine Zeiten nennt je Zeile die Mindestpause: gemerkt 45 -> 45; eine Buchung von vor 1.9.62 mit 30 min abgezogen -> 30; eine laufende
    Zeit -> keine. Der Dialog „Zeit ändern“ belegt „Pause mindestens“ damit vor und nennt sie im Knopf „Weitere Angaben“."""
    client = _monteurin(welt)
    h = welt["heute"]
    gemerkt = _nachtrag(client, welt, "06:00", "07:00", h, break_minutes=45)
    alt = _zeit(welt, welt["mia"], time(7), time(9), h, pause=30)
    alt.min_break_minutes = None
    welt["db"].commit()
    laeuft = start_timer(welt["db"], employee_id=welt["mia"].id, order_id=welt["order"].id, started_at=datetime.combine(h, time(9)))
    zeilen = {z["id"]: z for t in client.get("/api/field-view/meine-zeiten").json()["tage"] for z in t["zeilen"]}
    assert (zeilen[gemerkt["id"]]["mindestpause"], zeilen[alt.id]["mindestpause"], zeilen[laeuft.id]["mindestpause"]) == (45, 30, None)
    text, _ = vj.seitentext("mobil_zeiten.html")
    assert "el('zdPause').value=aendern?zahlText(z.mindestpause||0):'';" in text
    assert "z.mindestpause?'Pause mindestens '+stundenUhr(z.mindestpause):null" in text
