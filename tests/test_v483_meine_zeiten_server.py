"""Seit 1.9.57 (Stufe 4, R3 „Meine Zeiten“, Server): Nachtrag-Vorschau, Ändern über Von/Bis nach der Tagesregel, Pausen je Tag prüfen und
neu rechnen, die Daten der Seite.

    Nachtrag       GET /api/time-entries/nachtrag-vorschau rechnet wie POST /api/time-entries mit Von/Bis (nachtrag_nach_zeitregel(): Pause
                   aus dem Tag, Rundung der Zeitregeln, „Tag zusammen“) -- Vorschau = Buchung
    Ändern         PUT /api/time-entries/{id} mit von/bis: dieselbe Rechnung, der Tag ohne die alte Fassung dieser Buchung; andere Buchungen
                   nie angefasst; im abgeschlossenen Monat 403 (Monteurin), eine fremde Buchung 403
    Pausen je Tag  GET /api/time-entries/tagespause: passt die abgezogene Pause noch zur Zeitregel (nach Ändern oder Löschen oft nicht) --
                   nichts rechnet von selbst neu; POST …/pausen-neu-rechnen bucht genau die gezeigte Vorschau, sonst 409; Eintrag im Verlauf
    Seite          GET /api/field-view/meine-zeiten: Kacheln ohne laufende Zeit, Tage neueste zuerst mit Summe (dieselbe Funktion wie der
                   Stundenzettel als PDF) und Pausenprüfung
"""

import ast
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select

from app.models import AuditLog, TimeEntry
from app.time_backoffice import load_time_settings
from app.time_tracking import create_manual_entry, start_timer, stop_timer
from tests.test_v471_heute_server import _als, _einsatz, welt  # noqa: F401  (Fixture)


def _zeit(w, emp, von, bis, tag=None):
    """Eine Zeit mit Beginn und Ende (Timer gestartet und gestoppt) an tag (Vorgabe heute)."""
    tag = tag or w["heute"]
    row = start_timer(w["db"], employee_id=emp.id, order_id=w["order"].id, started_at=datetime.combine(tag, von))
    return stop_timer(w["db"], row.id, ended_at=datetime.combine(tag, bis))


def _monteurin(w):
    """Mia mit Einsatz am Auftrag (heute und die Woche davor) -- sonst bucht sie dort nicht (Planungsbezug)."""
    _einsatz(w, w["order"], [(w["heute"] - timedelta(days=7), w["heute"])], [w["mia"]])
    return _als(w, w["mia"])


def _nachtrag(client, w, von, bis, tag=None):
    return client.post("/api/time-entries", json={"employee_id": w["mia"].id, "order_id": w["order"].id,
                                                  "work_date": (tag or w["heute"]).isoformat(), "von": von, "bis": bis})


def _vorschau(client, w, von, bis, tag=None, **mehr):
    return client.get("/api/time-entries/nachtrag-vorschau",
                      params={"work_date": (tag or w["heute"]).isoformat(), "von": von, "bis": bis, **mehr})


def _zahlen(d, stunden="gebucht"):
    return (Decimal(str(d["anwesend"])), d["pause"], Decimal(str(d[stunden])), Decimal(str(d["tag_zusammen"])), d["tag_buchungen"])


# --- Nachtrag: Vorschau = Buchung ---------------------------------------------------------------------------------------------------

def test_nachtrag_mit_vorbuchung_pause_aus_dem_tag(welt):  # noqa: F811
    """Angriff: Baustelle 07:00–12:00 gebucht, Nachtrag 12:00–16:15 -> der Tag hat 9:15 h, 45 min bei der Nachtragung; Vorschau = Buchung."""
    client = _monteurin(welt)
    _zeit(welt, welt["mia"], time(7), time(12))
    v = _vorschau(client, welt, "12:00", "16:15")
    assert v.status_code == 200, v.text
    b = _nachtrag(client, welt, "12:00", "16:15")
    assert b.status_code == 200, b.text
    assert _zahlen(v.json()) == (Decimal("4.25"), 45, Decimal("3.5"), Decimal("9.25"), 2)
    assert _zahlen(b.json(), "hours") == _zahlen(v.json())


def test_nachtrag_ohne_vorbuchung_wie_einzelbuchung(welt):  # noqa: F811
    """Gegenprobe: derselbe Nachtrag ohne Vorbuchung -- 4:15 h, keine Pause, eine Buchung."""
    client = _monteurin(welt)
    v = _vorschau(client, welt, "12:00", "16:15").json()
    b = _nachtrag(client, welt, "12:00", "16:15").json()
    assert _zahlen(v) == (Decimal("4.25"), 0, Decimal("4.25"), Decimal("4.25"), 1)
    assert _zahlen(b, "hours") == _zahlen(v)


def test_vorschau_und_buchung_runden_gleich(welt):  # noqa: F811
    """Mit Rundung der Zeitregeln (15 min): Vorschau und Buchung runden mit derselben Funktion."""
    load_time_settings(welt["db"]).rounding_minutes = 15
    welt["db"].commit()
    client = _monteurin(welt)
    v = _vorschau(client, welt, "07:00", "11:10").json()
    b = _nachtrag(client, welt, "07:00", "11:10").json()
    assert Decimal(str(v["gebucht"])) == Decimal(str(b["hours"])) == Decimal("4.25")  # 4:10 h -> auf 15 min gerundet


# --- Ändern über Von/Bis ----------------------------------------------------------------------------------------------------------

def test_aendern_rechnet_den_tag_ohne_die_alte_fassung(welt):  # noqa: F811
    """Angriff: 07:00–12:00 und 12:00–16:15 (45 min); die zweite auf 12:00–15:00 geändert -> der Tag ohne ihre alte Fassung hat 8:00 h,
    30 min; die erste bleibt, wie sie ist. Vorschau mit entry_id = Ergebnis."""
    client = _monteurin(welt)
    erste = _zeit(welt, welt["mia"], time(7), time(12))
    zweite = _zeit(welt, welt["mia"], time(12), time(16, 15))
    assert zweite.break_minutes == 45
    vorher = (erste.hours, erste.break_minutes, erste.started_at, erste.ended_at)
    v = _vorschau(client, welt, "12:00", "15:00", entry_id=zweite.id).json()
    antwort = client.put(f"/api/time-entries/{zweite.id}", json={"von": "12:00", "bis": "15:00", "work_date": welt["heute"].isoformat()})
    assert antwort.status_code == 200, antwort.text
    assert _zahlen(v) == (Decimal("3"), 30, Decimal("2.5"), Decimal("8"), 2)
    d = antwort.json()
    assert (d["break_minutes"], Decimal(str(d["hours"])), d["started_at"][11:16], d["ended_at"][11:16]) == (30, Decimal("2.5"), "12:00", "15:00")
    welt["db"].expire_all()
    e = welt["db"].get(TimeEntry, erste.id)
    assert (e.hours, e.break_minutes, e.started_at, e.ended_at) == vorher


def test_aendern_mit_mindestpause(welt):  # noqa: F811
    """„Pause mindestens“ beim Ändern: 07:00–16:15 mit 60 min statt 45."""
    client = _monteurin(welt)
    row = _zeit(welt, welt["mia"], time(7), time(16, 15))
    d = client.put(f"/api/time-entries/{row.id}", json={"von": "07:00", "bis": "16:15", "pause_minuten": 60}).json()
    assert (d["break_minutes"], Decimal(str(d["hours"]))) == (60, Decimal("8.25"))


def test_aendern_abgelehnt_im_abgeschlossenen_monat_und_fremd(welt):  # noqa: F811
    """Angriff: im abgeschlossenen Zeitraum 403 (Monteurin), eine fremde Buchung 403, Von ohne Bis 422 -- nichts geändert."""
    client = _monteurin(welt)
    gestern = welt["heute"] - timedelta(days=1)
    alt = _zeit(welt, welt["mia"], time(7), time(12), tag=gestern)
    fremd = _zeit(welt, welt["tom"], time(7), time(12))
    load_time_settings(welt["db"]).locked_until = gestern
    welt["db"].commit()
    assert client.put(f"/api/time-entries/{alt.id}", json={"von": "07:00", "bis": "11:00"}).status_code == 403
    assert client.put(f"/api/time-entries/{fremd.id}", json={"von": "07:00", "bis": "11:00"}).status_code == 403
    assert _vorschau(client, welt, "07:00", "11:00", entry_id=fremd.id).status_code == 404
    eigene = _zeit(welt, welt["mia"], time(7), time(12))
    assert client.put(f"/api/time-entries/{eigene.id}", json={"von": "07:00"}).status_code == 422
    welt["db"].expire_all()
    assert welt["db"].get(TimeEntry, alt.id).hours == Decimal("5") and welt["db"].get(TimeEntry, fremd.id).hours == Decimal("5")


# --- Pausen je Tag: Hinweis nach dem Löschen, neu rechnen nur auf Klick -------------------------------------------------------------

def test_loeschen_hinweis_am_tag_nichts_automatisch(welt):  # noqa: F811
    """Angriff: 07:00–12:00 und 12:00–16:15 (45 min); die erste gelöscht -> die zweite behält 45 min (nichts von selbst), der Tag meldet
    „abgezogen 45, nach Zeitregel 0“ mit der Vorschau 45 -> 0, gebucht 3,50 -> 4,25."""
    client = _monteurin(welt)
    erste = _zeit(welt, welt["mia"], time(7), time(12))
    zweite = _zeit(welt, welt["mia"], time(12), time(16, 15))
    assert client.delete(f"/api/time-entries/{erste.id}").status_code == 200
    welt["db"].expire_all()
    assert welt["db"].get(TimeEntry, zweite.id).break_minutes == 45
    t = client.get("/api/time-entries/tagespause", params={"work_date": welt["heute"].isoformat()}).json()
    assert (t["abgezogen"], t["nach_zeitregel"], t["passt"]) == (45, 0, False)
    assert [(b["id"], b["pause_alt"], b["pause_neu"], Decimal(str(b["gebucht_alt"])), Decimal(str(b["gebucht_neu"]))) for b in t["buchungen"]] == \
        [(zweite.id, 45, 0, Decimal("3.5"), Decimal("4.25"))]


def test_pausen_neu_rechnen_bucht_genau_die_vorschau(welt):  # noqa: F811
    """Gegenprobe zum Löschen: „Pausen neu rechnen“ mit der gezeigten Vorschau -> die zweite 0 min, 4,25 h, der Tag passt, Eintrag im Verlauf;
    eine andere Vorschau (veraltet) -> 409, nichts geändert."""
    client = _monteurin(welt)
    erste = _zeit(welt, welt["mia"], time(7), time(12))
    zweite = _zeit(welt, welt["mia"], time(12), time(16, 15))
    client.delete(f"/api/time-entries/{erste.id}")
    tag = welt["heute"].isoformat()
    falsch = client.post("/api/time-entries/pausen-neu-rechnen", json={"work_date": tag, "buchungen": [{"id": zweite.id, "pause": 30}]})
    assert falsch.status_code == 409, falsch.text
    welt["db"].expire_all()
    assert welt["db"].get(TimeEntry, zweite.id).break_minutes == 45
    richtig = client.post("/api/time-entries/pausen-neu-rechnen", json={"work_date": tag, "buchungen": [{"id": zweite.id, "pause": 0}]})
    assert richtig.status_code == 200, richtig.text
    assert richtig.json()["passt"] is True
    welt["db"].expire_all()
    z = welt["db"].get(TimeEntry, zweite.id)
    assert (z.break_minutes, z.hours) == (0, Decimal("4.25"))
    verlauf = welt["db"].scalars(select(AuditLog).where(AuditLog.action == "Pausen neu gerechnet")).all()
    assert [(v.old_value, v.new_value) for v in verlauf] == [("45", "0")]
    assert client.post("/api/time-entries/pausen-neu-rechnen", json={"work_date": tag, "buchungen": [{"id": zweite.id, "pause": 0}]}).status_code == 409


def test_pausen_passen_bei_gleicher_summe(welt):  # noqa: F811
    """Gegenprobe: Nachmittag zuerst gebucht, der Vormittag nachgetragen (30 min dort) -- in der Reihenfolge des Tags fiele die Pause auf den
    Nachmittag, die Summe ist dieselbe: der Tag passt, kein Hinweis."""
    client = _monteurin(welt)
    _zeit(welt, welt["mia"], time(12, 30), time(16))
    assert _nachtrag(client, welt, "07:00", "12:00").json()["pause"] == 30
    t = client.get("/api/time-entries/tagespause", params={"work_date": welt["heute"].isoformat()}).json()
    assert (t["abgezogen"], t["nach_zeitregel"], t["passt"], t["buchungen"]) == (30, 30, True, [])


def test_pausen_neu_rechnen_im_abgeschlossenen_monat_abgelehnt(welt):  # noqa: F811
    client = _monteurin(welt)
    gestern = welt["heute"] - timedelta(days=1)
    row = _zeit(welt, welt["mia"], time(12), time(16, 15), tag=gestern)
    row.break_minutes = 45
    welt["db"].commit()
    load_time_settings(welt["db"]).locked_until = gestern
    welt["db"].commit()
    antwort = client.post("/api/time-entries/pausen-neu-rechnen", json={"work_date": gestern.isoformat(), "buchungen": [{"id": row.id, "pause": 0}]})
    assert antwort.status_code == 403


# --- die Daten der Seite ------------------------------------------------------------------------------------------------------------

def test_meine_zeiten_kacheln_ohne_laufende_zeit(welt):  # noqa: F811
    """Angriff: heute 06:00–07:00 gebucht, seit 07:00 läuft eine Zeit -- die Kachel „Heute“ zählt nur die gebuchte Stunde; die laufende Zeile
    steht ohne Stunden mit „läuft seit 07:00“; der Tag summiert ohne sie."""
    client = _monteurin(welt)
    _zeit(welt, welt["mia"], time(6), time(7))
    start_timer(welt["db"], employee_id=welt["mia"].id, order_id=welt["order"].id, started_at=datetime.combine(welt["heute"], time(7)))
    d = client.get("/api/field-view/meine-zeiten").json()
    assert Decimal(str(d["kacheln"]["heute"])) == Decimal("1")
    tag = d["tage"][0]
    assert (tag["tag"], Decimal(str(tag["summe"]))) == (welt["heute"].isoformat(), Decimal("1"))
    laufend = [z for z in tag["zeilen"] if z["laeuft"]]
    assert [(z["von"], z["gebucht"]) for z in laufend] == [("07:00", None)]


def test_meine_zeiten_monat_und_tage(welt):  # noqa: F811
    """Tage neueste zuerst, Monat (Summe, Tage, Fahrzeit), eine Dauer-Buchung zählt; ein anderer Monat über ?monat=, falscher Wert 422."""
    client = _monteurin(welt)
    h = welt["heute"]
    erster = h.replace(day=1)
    if h == erster:
        pytest.skip("braucht zwei Tage im laufenden Monat")
    _zeit(welt, welt["mia"], time(7), time(12), tag=erster)
    create_manual_entry(welt["db"], employee_id=welt["mia"].id, order_id=welt["order"].id, work_date=h, hours=Decimal("2.5"), entry_type="travel")
    d = client.get("/api/field-view/meine-zeiten").json()
    assert [t["tag"] for t in d["tage"]] == [h.isoformat(), erster.isoformat()]
    assert (Decimal(str(d["kacheln"]["monat"])), d["monat_tage"], Decimal(str(d["monat_fahrzeit"]))) == (Decimal("7.5"), 2, Decimal("2.5"))
    vormonat = (erster - timedelta(days=1)).strftime("%Y-%m")
    assert client.get("/api/field-view/meine-zeiten", params={"monat": vormonat}).json()["tage"] == []
    assert client.get("/api/field-view/meine-zeiten", params={"monat": "2026-13"}).status_code == 422


def test_stundenzettel_und_seite_summieren_mit_derselben_funktion():
    """Kacheln, Tagessummen und der Stundenzettel als PDF rechnen mit app/meine_zeiten.py::tagessumme() (AST)."""
    pdf = ast.parse(Path("app/field_timesheet_pdf.py").read_text(encoding="utf-8"))
    aufrufe = {n.func.id for n in ast.walk(pdf) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "tagessumme" in aufrufe
    seite = ast.parse(Path("app/meine_zeiten.py").read_text(encoding="utf-8"))
    assert sum(1 for n in ast.walk(seite) if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "tagessumme") >= 5
