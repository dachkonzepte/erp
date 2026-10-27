"""Version 1.9.107 (Stufe 4, R5b Nachrunde 2, Punkt 1, Entscheidung Tobias: die Pause einer Dauer gibt man an).

    GET /api/time-entries/dauer-vorschau       was eine Dauer (Stunden netto, „Pause an diesem Tag“) am Tag bewirkt: anwesend, „Tag zusammen“,
                                               ob die Pause des Tags danach passt -- dieselbe Prüfung wie „Prüfen“ und der Abschluss
    GET /api/time-entry-groups/dauer-vorschau  dasselbe je Mitglied für „Kolonne buchen“ mit Dauer
    pausen_vorschau()                          hat der Tag eine Dauer und bringt die Regel die Pflichtpause nicht unter, fehlt der Rest
                                               („fehlt“) -- der Tag passt nicht, „Prüfen“ zeigt statt „So buchen“ den Weg zu „Ändern“

Bestehende Dauern bleiben, wie sie sind (kein Lesen schreibt, keine Migration).
"""

import json
import re
from datetime import datetime, time
from decimal import Decimal

from app.meldungen import NUR_VON_BIS
from app.models import TimeEntry, TimeTrackingSettings
from app.time_tracking import NICHTS_NEU_ZU_RECHNEN, create_manual_entry, dauer_vorschau, pausen_vorschau
from tests import vorlagen_js as vj
from tests.node_lauf import node_ausfuehren
from tests.test_v471_heute_server import welt  # noqa: F401  (Fixture)
from tests.test_v517_zeiten_server import D, _als, _get, _zeit
from tests.test_v518_zeiten_seite import _funktion, _node, _text


def _buchung(w, emp, von=None, bis=None, *, stunden=None, pause=0, art="site", tag=None):
    """Eine gebuchte Zeit wie ein Nachtrag: mit Von/Bis (Stunden = Anwesenheit − Pause) oder als Dauer."""
    tag = tag or w["heute"]
    if von is not None:
        beginn, ende = datetime.combine(tag, von), datetime.combine(tag, bis)
        stunden = Decimal(str((ende - beginn).total_seconds() / 3600)) - Decimal(pause) / 60
        return create_manual_entry(w["db"], employee_id=emp.id, order_id=w["order"].id, work_date=tag, hours=stunden, entry_type=art,
                                   started_at=beginn, ended_at=ende, break_minutes=pause)
    return create_manual_entry(w["db"], employee_id=emp.id, order_id=w["order"].id, work_date=tag, hours=Decimal(str(stunden)),
                               entry_type=art, break_minutes=pause)


def _tom_15_10(w):
    """Toms Tag wie in klicktest_zeiten: Fahrzeit 06:15–07:00, Baustelle 07:00–16:30 mit 0:45."""
    fahrt = _buchung(w, w["tom"], time(6, 15), time(7), art="travel")
    bau = _buchung(w, w["tom"], time(7), time(16, 30), pause=45)
    return fahrt, bau


def _vorschau(w, rolle="buero_finanzen", employee_id=None, **params):
    return _als(w, rolle, employee_id).get("/api/time-entries/dauer-vorschau", params=params)


def _tag(w, emp):
    return [t for t in _get(w, "/api/zeiten/pruefen")["pausen"] if t["employee_id"] == emp.id and t["tag"] == w["heute"].isoformat()]


# --- Vorschau „Dauer“ beim Server --------------------------------------------------------------------------------------------------------

def test_tom_dauer_mit_pause_passt_ohne_pause_nicht(welt):  # noqa: F811
    """Toms 15.10.: 07:00–16:30 wird „Dauer“ 8,00 mit 0:45 neben der Fahrzeit 06:15–07:00 -> „Anwesend 8:45 h · Tag zusammen 9:30 h · Pause des
    Tags passt“. Angriff: mit Pause 0 -> passt danach nicht; gespeichert erscheint der Tag unter „Prüfen“ (dort mit „So buchen“: die Fahrzeit
    bekommt die 30 min)."""
    fahrt, bau = _tom_15_10(welt)
    tag = welt["heute"].isoformat()
    mit = _vorschau(welt, work_date=tag, hours="8", break_minutes=45, entry_id=bau.id, employee_id=welt["tom"].id)
    assert mit.status_code == 200, mit.text
    v = mit.json()
    assert (D(v["anwesend"]), D(v["tag_zusammen"]), v["tag_buchungen"], v["passt"], D(v["gebucht"])) == (
        Decimal("8.75"), Decimal("9.5"), 2, True, Decimal("8"))
    ohne = _vorschau(welt, work_date=tag, hours="8", break_minutes=0, entry_id=bau.id, employee_id=welt["tom"].id).json()
    assert (D(ohne["anwesend"]), D(ohne["tag_zusammen"]), ohne["passt"], ohne["noetig"]) == (Decimal("8"), Decimal("8.75"), False, 30)
    assert _tag(welt, welt["tom"]) == []  # die Vorschau bucht nichts
    client = _als(welt)
    assert client.put(f"/api/time-entries/{bau.id}", json={"hours": 8, "break_minutes": 0}).status_code == 200
    [t] = _tag(welt, welt["tom"])
    assert (t["abgezogen"], t["noetig"], t["fehlt"], t["dauern"]) == (0, 30, 0, [])
    assert [(b["id"], b["pause_alt"], b["pause_neu"]) for b in t["buchungen"]] == [(fahrt.id, 0, 30)]


def test_tom_dauer_mit_pause_gespeichert_tag_passt(welt):  # noqa: F811
    """Gegenprobe: mit 0:45 gespeichert -- „Tag zusammen“ 9:30 h, kein Eintrag unter „Prüfen“; die Antwort nennt denselben Tag."""
    fahrt, bau = _tom_15_10(welt)
    r = _als(welt).put(f"/api/time-entries/{bau.id}", json={"hours": 8, "break_minutes": 45})
    assert r.status_code == 200, r.text
    assert (r.json()["started_at"], D(r.json()["hours"]), r.json()["break_minutes"], D(r.json()["tag_zusammen"])) == (None, Decimal("8"), 45,
                                                                                                                       Decimal("9.5"))
    assert _tag(welt, welt["tom"]) == [] and pausen_vorschau(welt["db"], welt["tom"].id, welt["heute"])["passt"]


def test_neue_dauer_rundet_wie_das_speichern(welt):  # noqa: F811
    """Eine neue Dauer rundet die Vorschau wie das Speichern (Zeitregeln: 15 min), eine geänderte bleibt, wie eingetragen (update_entry())."""
    welt["db"].get(TimeTrackingSettings, 1).rounding_minutes = 15
    welt["db"].commit()
    neu = dauer_vorschau(welt["db"], employee_id=welt["mia"].id, work_date=welt["heute"], hours=Decimal("7.9"), break_minutes=30)
    geaendert = dauer_vorschau(welt["db"], employee_id=welt["mia"].id, work_date=welt["heute"], hours=Decimal("7.9"), break_minutes=30,
                               ohne_id=999, runden=False)
    gespeichert = _als(welt).post("/api/time-entries", json={"employee_id": welt["mia"].id, "order_id": welt["order"].id,
                                                             "work_date": welt["heute"].isoformat(), "hours": "7.9", "break_minutes": 30})
    assert (neu["gebucht"], geaendert["gebucht"], D(gespeichert.json()["hours"])) == (Decimal("8.00"), Decimal("7.9"), Decimal("8"))


def test_dauer_vorschau_rechte(welt):  # noqa: F811
    """Angriff: Büro – Auftrag liest nur (403), die Monteurin bucht nur mit Von und Bis (422 wie beim Speichern), eine Buchung einer anderen
    Person als entry_id 404. Gegenprobe: Büro – Finanzen und Admin für Tom."""
    _, bau = _tom_15_10(welt)
    tag = welt["heute"].isoformat()
    assert _vorschau(welt, "buero_auftrag", work_date=tag, hours="8", employee_id=welt["tom"].id).status_code == 403
    monteurin = _vorschau(welt, "field", employee_id=welt["mia"].id, work_date=tag, hours="8")
    assert (monteurin.status_code, monteurin.json().get("detail")) == (422, NUR_VON_BIS)
    assert _vorschau(welt, work_date=tag, hours="8", entry_id=bau.id, employee_id=welt["mia"].id).status_code == 404
    assert _vorschau(welt, work_date=tag, hours="0", employee_id=welt["tom"].id).status_code == 422
    for rolle in ("buero_finanzen", "admin"):
        assert _vorschau(welt, rolle, work_date=tag, hours="8", employee_id=welt["tom"].id).status_code == 200


# --- Ein Tag nur aus Dauern ---------------------------------------------------------------------------------------------------------------

def test_tag_nur_aus_dauern_zu_wenig_pause_weg_zu_aendern(welt):  # noqa: F811
    """Angriff: Mia 8,00 h als Dauer ohne Pause -- „Prüfen“ kann nichts abziehen: der Tag erscheint mit „fehlt 30 min“, ohne Vorschlag (kein
    „So buchen“) und mit der Dauer als Zeile für „Ändern“; neu rechnen lehnt ab (409). Gegenprobe: über „Ändern“ 0:30 eingetragen -> passt."""
    dauer = _buchung(welt, welt["mia"], stunden=8)
    [t] = _tag(welt, welt["mia"])
    assert (t["abgezogen"], t["nach_zeitregel"], t["fehlt"], t["noetig"], t["buchungen"]) == (0, 0, 30, 30, [])
    assert [(e["id"], e["zeitart"], D(e["hours"]), e["break_minutes"], e["started_at"]) for e in t["dauern"]] == [
        (dauer.id, "Baustellenzeit", Decimal("8"), 0, None)]
    assert {"gebucht_von", "geaendert_von", "employee_name", "order_number"} <= set(t["dauern"][0])  # wie eine Zeile in „Buchungen“
    client = _als(welt)
    abgelehnt = client.post("/api/time-entries/pausen-neu-rechnen", json={"work_date": welt["heute"].isoformat(), "employee_id": welt["mia"].id,
                                                                          "buchungen": [{"id": dauer.id, "pause": 30}]})
    assert (abgelehnt.status_code, abgelehnt.json().get("detail")) == (409, NICHTS_NEU_ZU_RECHNEN)
    v = _vorschau(welt, work_date=welt["heute"].isoformat(), hours="8", break_minutes=30, entry_id=dauer.id, employee_id=welt["mia"].id).json()
    assert (D(v["anwesend"]), v["passt"]) == (Decimal("8.5"), True)
    assert client.put(f"/api/time-entries/{dauer.id}", json={"hours": 8, "break_minutes": 30}).status_code == 200
    assert _tag(welt, welt["mia"]) == []


def test_tag_nur_aus_dauern_sperrt_den_abschluss(welt):  # noqa: F811
    """Ein Tag, dem die Pause einer Dauer fehlt, ist ein Tag mit unpassender Pause -- auch für „Vor dem Abschluss“ und den Abschluss (409)."""
    _buchung(welt, welt["mia"], stunden=8)
    p = _get(welt, "/api/zeiten/pruefen")
    assert {"art": "pause", "text": "1 Tag mit unpassender Pause"} in p["vor_dem_abschluss"] and p["zahlen"]["pruefen"] == 1
    r = _als(welt, "admin").put("/api/time-backoffice/lock", json={"locked_until": welt["heute"].isoformat()})
    assert r.status_code == 409 and "Pause abgezogen 0 min, nach Zeitregel 30 min" in r.json()["detail"]


def test_fahrzeit_zu_kurz_erst_so_buchen_dann_aendern(welt):  # noqa: F811
    """Fahrzeit 06:40–07:00 (20 min) und eine Dauer 8,00 ohne Pause: neu rechnen gibt der Fahrzeit ihre 20 min, es fehlen danach noch 10 --
    beides steht unter „Prüfen“ (Vorschlag und die Dauer für „Ändern“). Nach „So buchen“ bleibt nur der Weg zu „Ändern“."""
    fahrt = _buchung(welt, welt["mia"], time(6, 40), time(7), art="travel")
    _buchung(welt, welt["mia"], stunden=8)
    [t] = _tag(welt, welt["mia"])
    assert (t["nach_zeitregel"], t["fehlt"], t["noetig"], [b["pause_neu"] for b in t["buchungen"]], len(t["dauern"])) == (20, 10, 30, [20], 1)
    r = _als(welt).post("/api/time-entries/pausen-neu-rechnen", json={"work_date": welt["heute"].isoformat(), "employee_id": welt["mia"].id,
                                                                    "buchungen": [{"id": fahrt.id, "pause": 20}]})
    assert r.status_code == 200, r.text
    [t] = _tag(welt, welt["mia"])
    assert (t["abgezogen"], t["fehlt"], t["buchungen"], len(t["dauern"])) == (20, 10, [], 1)


def test_tag_nur_mit_uhrzeiten_bleibt_wie_bisher(welt):  # noqa: F811
    """Festlegung 1.9.107 Nr. 4: ein Tag nur mit Uhrzeiten -- auch wenn die Regel der letzten, kurzen Zeit nicht die ganze Pflichtpause geben
    kann (06:00–12:00 ohne Pause, dann 12:00–12:10 gestoppt: 10 min Pause, 0 h) -- passt wie bisher, wenn die Pausen der Regel entsprechen."""
    _zeit(welt, welt["mia"], time(6), time(12), welt["gestern"])
    kurz = _zeit(welt, welt["mia"], time(12), time(12, 10), welt["gestern"])
    assert (kurz.break_minutes, kurz.hours) == (10, Decimal("0"))
    stand = pausen_vorschau(welt["db"], welt["mia"].id, welt["gestern"])
    assert (stand["passt"], stand["fehlt"], stand["noetig"]) == (True, 0, 10)


# --- Kolonne buchen mit Dauer -------------------------------------------------------------------------------------------------------------

def _kolonne(w, rolle="buero_finanzen", employee_id=None, **params):
    return _als(w, rolle, employee_id).get("/api/time-entry-groups/dauer-vorschau", params=params)


def test_kolonne_dauer_je_person(welt):  # noqa: F811
    """„Kolonne buchen“ mit Dauer 8,00: Mia (sonst nichts am Tag) und Tom (Fahrzeit 06:15–07:00) -- ohne Pause passt keiner (Mia fehlt die Pause,
    Toms Fahrzeit bekäme 30 min); mit 0:30 nur Mia (Tom ist dann über 9 h anwesend, er braucht 45 min); mit 0:45 beide, Tom mit „Tag zusammen“
    9:30 h. Gebucht wie die Vorschau, die Pause je Person."""
    _buchung(welt, welt["tom"], time(6, 15), time(7), art="travel")
    params = {"work_date": welt["heute"].isoformat(), "hours": "8", "team_id": welt["team"].id, "employee_ids": [welt["mia"].id, welt["tom"].id]}
    ohne = _kolonne(welt, **params, break_minutes=0)
    assert ohne.status_code == 200, ohne.text
    assert [(m["name"], m["passt"], m["tag_buchungen"]) for m in ohne.json()["mitglieder"]] == [("Mia Monteurin", False, 1), ("Tom Monteur", False, 2)]
    halb = _kolonne(welt, **params, break_minutes=30).json()["mitglieder"]
    assert [(m["passt"], D(m["tag_zusammen"])) for m in halb] == [(True, Decimal("8.5")), (False, Decimal("9.25"))]
    mit = _kolonne(welt, **params, break_minutes=45).json()["mitglieder"]
    assert [(m["name"], m["passt"], D(m["anwesend"]), D(m["tag_zusammen"])) for m in mit] == [
        ("Mia Monteurin", True, Decimal("8.75"), Decimal("8.75")), ("Tom Monteur", True, Decimal("8.75"), Decimal("9.5"))]
    r = _als(welt).post("/api/time-entry-groups", json={"team_id": welt["team"].id, "employee_ids": [welt["mia"].id, welt["tom"].id],
                                                        "order_id": welt["order"].id, "work_date": welt["heute"].isoformat(), "hours": "8",
                                                        "break_minutes": 45})
    assert r.status_code == 200, r.text
    assert [t for t in _get(welt, "/api/zeiten/pruefen")["pausen"] if t["tag"] == welt["heute"].isoformat()] == []


def test_kolonne_dauer_vorschau_rechte(welt):  # noqa: F811
    """Angriff: Büro – Auftrag 403; Mia als Kolonnenführerin bucht nur mit Von und Bis (422); Tom ist keiner (403)."""
    params = {"work_date": welt["heute"].isoformat(), "hours": "8", "team_id": welt["team"].id, "employee_ids": [welt["mia"].id]}
    assert _kolonne(welt, "buero_auftrag", **params).status_code == 403
    mia = _kolonne(welt, "field", employee_id=welt["mia"].id, **params)
    assert (mia.status_code, mia.json().get("detail")) == (422, NUR_VON_BIS)
    assert _kolonne(welt, "field", employee_id=welt["tom"].id, **params).status_code == 403


# --- Bestand ------------------------------------------------------------------------------------------------------------------------------

def test_bestehende_dauern_bleiben_unveraendert(welt):  # noqa: F811
    """Nach dem Einspielen: bestehende Dauern (8,00 h mit 0:45, 8,00 h ohne Pause, eine Kolonnen-Dauer) behalten Stunden, Pause und
    Mindestpause -- Prüfen, Buchungen, Monat & Lohn, beide Vorschauen und ein abgelehnter Abschluss lesen nur."""
    def stand():
        welt["db"].expire_all()
        return [(r.id, r.hours, r.break_minutes, r.min_break_minutes, r.started_at, r.ended_at)
                for r in welt["db"].query(TimeEntry).order_by(TimeEntry.id)]

    a = _buchung(welt, welt["tom"], stunden=8, pause=45)
    b = _buchung(welt, welt["mia"], stunden=8)
    _als(welt).post("/api/time-entry-groups", json={"team_id": welt["team"].id, "employee_ids": [welt["mia"].id, welt["tom"].id],
                                                    "order_id": welt["order"].id, "work_date": welt["gestern"].isoformat(), "hours": "7.5"})
    vorher = stand()
    tag, monat = welt["heute"].isoformat(), f"{welt['heute']:%Y-%m}"
    _get(welt, "/api/zeiten/pruefen")
    _get(welt, "/api/zeiten/buchungen", monat=monat)
    _get(welt, "/api/zeiten/monat", monat=monat)
    _vorschau(welt, work_date=tag, hours="8", break_minutes=0, entry_id=a.id, employee_id=welt["tom"].id)
    _kolonne(welt, work_date=tag, hours="8", team_id=welt["team"].id, employee_ids=[welt["mia"].id, welt["tom"].id])
    _als(welt).get("/api/time-entries/tagespause", params={"work_date": tag, "employee_id": welt["mia"].id})
    assert _als(welt, "admin").put("/api/time-backoffice/lock", json={"locked_until": tag}).status_code == 409
    assert stand() == vorher
    assert [(x[2], x[3]) for x in vorher if x[0] in (a.id, b.id)] == [(45, 45), (0, 0)]


# --- Seite (node) -------------------------------------------------------------------------------------------------------------------------

def test_dialog_dauer_vorschau_text():
    """Die Vorschau des Dialogs in „Dauer“ wie die Vorgabe: „Anwesend 8:45 h · Tag zusammen 9:30 h · Pause des Tags passt“ bzw. „… passt danach
    nicht – der Tag erscheint unter „Prüfen““; „Tag zusammen“ nur bei mehr als einer Buchung."""
    passt = {"anwesend": 8.75, "tag_zusammen": 9.5, "tag_buchungen": 2, "passt": True, "gebucht": 8}
    html = _node(("teileHtml", "dauerVorschauHtml"), f"return [dauerVorschauHtml({json.dumps(passt)}),"
                 f"dauerVorschauHtml({json.dumps({**passt, 'passt': False, 'anwesend': 8, 'tag_zusammen': 8.75})}),"
                 f"dauerVorschauHtml({json.dumps({**passt, 'tag_buchungen': 1})})]")
    assert [_text(h) for h in html] == ["Anwesend 8:45 h · Tag zusammen 9:30 h · Pause des Tags passt",
                                        "Anwesend 8:00 h · Tag zusammen 8:45 h · Pause des Tags passt danach nicht – der Tag erscheint unter „Prüfen“",
                                        "Anwesend 8:45 h · Pause des Tags passt"]
    assert 'class="vorschau-warn"' in html[1] and "vorschau-warn" not in html[0]


def test_dialog_feld_und_saetze():
    """„Pause an diesem Tag (Min.)“ sichtbar in „Dauer“ (nicht unter „Weitere Angaben“) mit „zählt zur Pause des Tags“, in beiden Dialogen; der
    Satz „„Dauer“ bucht die Stunden netto; die Pause gibst du an.“; die Vorschau fragt den Server, auch bei jeder Eingabe in die Pause."""
    html = (vj.TEMPLATES / "zeiten.html").read_text(encoding="utf-8")
    for p in ("bd", "kd"):
        feld = re.search(rf'<label class="feld" for="{p}PauseDauer"[^>]*>(.*?)</label>', html, flags=re.S)[1]
        assert feld.startswith("Pause an diesem Tag (Min.)<input") and '<span class="feld-hinweis">zählt zur Pause des Tags</span>' in feld
        weitere = re.search(rf'<div class="dialog-felder" id="{p}WeitereFelder" hidden>(.*?)</div>', html, flags=re.S)[1]
        assert f"{p}PauseDauer" not in weitere
    assert "„Dauer“ bucht die Stunden netto; die Pause gibst du an." in html and "ohne Pausenregel" not in html
    text = vj.eigene_skripte("zeiten.html").text
    assert "api('/api/time-entries/dauer-vorschau" not in text  # die Adresse steht in einer Variablen …
    assert "'/api/time-entries/dauer-vorschau?work_date='" in _funktion(text, "vorschauLaden") and "api(adresse)" in _funktion(text, "vorschauLaden")
    assert "'/api/time-entry-groups/dauer-vorschau?work_date='" in _funktion(text, "kdVorschauLaden")
    assert "'bdStunden','bdPauseDauer'].forEach" in text and "'kdStunden','kdPauseDauer'].forEach" in text


def test_pruefen_tag_nur_aus_dauern_ohne_so_buchen():
    """„Prüfen“: ein Tag nur aus Dauern zeigt „nach Zeitregel“ mit der nötigen Pause, kein „So buchen“, je Dauer „Ändern“ (nur wer buchen
    darf); mit Vorschlag zuerst „So buchen“ und „Danach fehlen noch …“."""
    dauer = {"id": 7, "zeitart": "Baustellenzeit", "hours": 8, "break_minutes": 0}
    tag = {"employee_id": 3, "name": "Mia Monteurin", "tag": "2026-10-20", "abgezogen": 0, "nach_zeitregel": 0, "fehlt": 30, "noetig": 30,
           "buchungen": [], "dauern": [dauer], "darf_buchen": True}
    html = _node(("pauseHtml", "fehltHtml"), f"return pauseHtml({json.dumps(tag)},0)", vorweg="var ZU={};")
    assert "Pause abgezogen 0:00 h · nach Zeitregel 0:30 h" in _text(html)
    assert "Pause angeben: Hier lässt sich nichts abziehen – die Pause steht in der Dauer, trag sie unter „Ändern“ ein." in _text(html)
    assert "Baustellenzeit · Dauer 8,00 h · Pause 0:00" in _text(html) and 'data-aktion="pause-aendern" data-i="0" data-id="7">Ändern<' in html
    assert "So buchen" not in html and "Neu rechnen" not in html
    ohne = _node(("pauseHtml", "fehltHtml"), f"return pauseHtml({json.dumps({**tag, 'darf_buchen': False})},0)", vorweg="var ZU={};")
    assert "Baustellenzeit · Dauer 8,00 h" in _text(ohne) and "data-aktion" not in ohne
    teil = {**tag, "nach_zeitregel": 20, "fehlt": 10, "buchungen": [{"id": 6, "zeitart": "Fahrzeit", "von": "2026-10-20T06:40:00",
                                                                     "bis": "2026-10-20T07:00:00", "pause_alt": 0, "pause_neu": 20,
                                                                     "gebucht_alt": 0.33, "gebucht_neu": 0}]}
    beides = _node(("pauseHtml", "fehltHtml"), f"return pauseHtml({json.dumps(teil)},0)", vorweg="var ZU={};")
    assert "So buchen" in beides and "Danach fehlen noch 0:10 h – die Pause steht in der Dauer" in _text(beides)
    assert beides.index("So buchen") < beides.index("Pause angeben")


def test_kolonne_vorschau_text():
    v = {"mitglieder": [{"name": "Mia Monteurin", "gebucht": 8, "tag_buchungen": 1, "tag_zusammen": 8, "passt": False},
                        {"name": "Tom Monteur", "gebucht": 8, "tag_buchungen": 2, "tag_zusammen": 9.25, "passt": True}]}
    html = _node(("kdDauerHtml",), f"return kdDauerHtml({json.dumps(v)})")
    assert _text(html) == ("Mia Monteurin 8,00 h – Pause passt danach nicht · Tom Monteur 8,00 h (Tag zusammen 9:15 h) – Pause passt "
                           "Passt die Pause eines Tags danach nicht, erscheint er unter „Prüfen“.")
    beide = _node(("kdDauerHtml",), f"return kdDauerHtml({json.dumps({'mitglieder': [{**m, 'passt': True} for m in v['mitglieder']]})})")
    assert "Prüfen" not in beide


def test_meine_zeiten_kein_neu_rechnen_ohne_vorschlag():
    """„Meine Zeiten“: fehlt nur die Pause einer Buchung ohne Uhrzeiten, kein „Pausen neu rechnen“ (es änderte nichts), ein Satz, wie sie
    hineinkommt; mit Vorschlag wie bisher der Knopf."""
    text = vj.eigene_skripte("mobil_zeiten.html").text
    rumpf = re.search(r"function tagHtml\(t\)\{.*?\n\}\n", text, flags=re.S)[0]
    vorweg = ("function esc(s){return String(s==null?'':s)}function tagKurz(t){return t}function stunden(x){return x+' h'}"
              "function zeileHtml(){return ''}function pad2(n){return (n<10?'0':'')+n}"
              + re.search(r"function stundenUhr\(minuten\)\{[^\n]*\}", text)[0] + "\nvar D={nachtragen_erlaubt:true};")
    def tag(pause):
        return {"tag": "2026-10-20", "summe": 8, "abgeschlossen": False, "zeilen": [], "pause": pause}
    nur = {"abgezogen": 0, "nach_zeitregel": 0, "fehlt": 30, "noetig": 30, "passt": False, "buchungen": []}
    vorschlag = {**nur, "nach_zeitregel": 20, "fehlt": 10, "buchungen": [{"id": 1, "pause_alt": 0, "pause_neu": 20}]}
    html = node_ausfuehren(vorweg + rumpf + f"\nprocess.stdout.write(JSON.stringify([tagHtml({json.dumps(tag(nur))}),"
                                              f"tagHtml({json.dumps(tag(vorschlag))})]));")
    assert "Pausen neu rechnen" not in html[0] and "nach Zeitregel 0:30 h" in html[0]
    assert "eine Buchung ohne Uhrzeiten: über „⋮ Ändern“ Von und Bis eintragen." in html[0]
    assert "Pausen neu rechnen" in html[1] and "Danach fehlen noch 0:10 h – eine Buchung ohne Uhrzeiten" in html[1]
