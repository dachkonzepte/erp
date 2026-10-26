"""Version 1.9.90 (Stufe 4, R5a, Punkte 2 und 3): das Büro auf abgeschlossenen Aufträgen, Von/Bis wie die Monteurin, eine Dauer ohne Uhrzeiten.

    geschlossen   Büro – Finanzen (wer für andere bucht) bucht, ändert und löscht auch auf abgeschlossenen und stornierten Aufträgen; der
                  Kontext bietet sie nach den offenen an, gekennzeichnet (geschlossen, status), jede Buchung trägt auftrag_geschlossen; die
                  Monteurin bleibt gesperrt (403, seit 1.9.81)
    Von/Bis       Nachtrag und Ändern des Büros mit Von/Bis über dieselbe Rechnung wie bei der Monteurin (Pause je Tag, Rundung, Vorschau =
                  Buchung); „Dauer“ bleibt dem Büro (netto, ohne Pausenregel)
    Dauer         wird eine Von/Bis-Buchung als Dauer gespeichert (Stunden, Pause oder ein anderer Tag ohne Von/Bis), sind Beginn und Ende leer
                  -- auch an jedem Mitglied und am Kopf einer Kolonnenbuchung; Auftrag, Zeitart, Tätigkeit oder Notiz allein lassen sie stehen.
                  Eine Kolonnenbuchung ohne Von/Bis und ohne Dauer behält die Stunden jedes Mitglieds (bis 1.9.89 bekam jedes die Stunden
                  des Kopfs, nach einem Nachtrag mit Von/Bis deren Mittel). Die Monteurin ändert Stunden, Pause oder Tag nur mit Von/Bis (422)
"""

from datetime import datetime, time, timedelta
from decimal import Decimal

import pytest

from app.meldungen import AUFTRAG_ABGESCHLOSSEN_ZEITEN, AUFTRAG_STORNIERT_ZEITEN, NUR_VON_BIS
from app.models import TimeEntry, TimeEntryGroup
from app.routers import time_tracking as time_tracking_router
from app.time_tracking import create_group_manual_entry, group_member_ids, start_timer, stop_timer
from tests.test_v471_heute_server import _als, _einsatz, _zweiter_auftrag, welt  # noqa: F401  (Fixture)

MELDUNG = {"abgeschlossen": AUFTRAG_ABGESCHLOSSEN_ZEITEN, "storniert": AUFTRAG_STORNIERT_ZEITEN}


def _buero(w, rolle="buero_finanzen"):
    return w["client"](w["db"], time_tracking_router.router, role=rolle)


def _zeit(w, emp, von, bis, tag=None, order=None):
    row = start_timer(w["db"], employee_id=emp.id, order_id=(order or w["order"]).id, started_at=datetime.combine(tag or w["heute"], von))
    return stop_timer(w["db"], row.id, ended_at=datetime.combine(tag or w["heute"], bis))


def _frisch(w, entry_id):
    w["db"].expire_all()
    return w["db"].get(TimeEntry, entry_id)


def _zahlen(d):
    return Decimal(str(d["anwesend"])), d["pause"], Decimal(str(d["gebucht"]))


# --- Punkt 2: abgeschlossene und stornierte Aufträge -------------------------------------------------------------------------------

@pytest.mark.parametrize("status", ["abgeschlossen", "storniert"])
def test_buero_bucht_auf_geschlossenem_auftrag_monteurin_nicht(welt, status):  # noqa: F811
    """Angriff Monteurin (eingeplant): Nachtrag auf den geschlossenen Auftrag 403. Gegenprobe Büro – Finanzen: Nachtrag als Dauer und mit
    Von/Bis für Tom, Ändern, Löschen -- 200, die Buchung gekennzeichnet."""
    _einsatz(welt, welt["order"], [(welt["heute"] - timedelta(days=7), welt["heute"])], [welt["mia"]])
    welt["order"].status = status
    welt["db"].commit()
    monteurin = _als(welt, welt["mia"]).post("/api/time-entries", json={"employee_id": welt["mia"].id, "order_id": welt["order"].id,
                                                                        "work_date": welt["heute"].isoformat(), "von": "07:00", "bis": "09:00"})
    assert (monteurin.status_code, monteurin.json()["detail"]) == (403, MELDUNG[status])
    buero = _buero(welt)
    dauer = buero.post("/api/time-entries", json={"employee_id": welt["tom"].id, "order_id": welt["order"].id,
                                                  "work_date": welt["heute"].isoformat(), "hours": "2"})
    von_bis = buero.post("/api/time-entries", json={"employee_id": welt["tom"].id, "order_id": welt["order"].id,
                                                    "work_date": welt["heute"].isoformat(), "von": "07:00", "bis": "09:00"})
    assert [(a.status_code, a.json().get("auftrag_geschlossen")) for a in (dauer, von_bis)] == [(200, status)] * 2, (dauer.text, von_bis.text)
    assert buero.put(f"/api/time-entries/{dauer.json()['id']}", json={"hours": "3"}).status_code == 200
    assert buero.delete(f"/api/time-entries/{dauer.json()['id']}").status_code == 200


def test_kontext_bietet_geschlossene_auftraege_gekennzeichnet_an(welt):  # noqa: F811
    """Büro – Finanzen: offene zuerst, danach der abgeschlossene mit Kennzeichen. Gegenprobe Büro – Auftrag (bucht nicht): nur offene."""
    offen = _zweiter_auftrag(welt)
    welt["order"].status = "abgeschlossen"
    welt["db"].commit()
    finanzen = _buero(welt).get("/api/time-tracking/context").json()["orders"]
    assert [(o["id"], o["geschlossen"]) for o in finanzen] == [(offen.id, None), (welt["order"].id, "abgeschlossen")]
    auftrag = _buero(welt, "buero_auftrag").get("/api/time-tracking/context").json()["orders"]
    assert [o["id"] for o in auftrag] == [offen.id]


def test_liste_kennzeichnet_buchungen_auf_geschlossenen_auftraegen(welt):  # noqa: F811
    zu = _zeit(welt, welt["tom"], time(7), time(9))
    welt["order"].status = "storniert"
    welt["db"].commit()
    liste = _buero(welt, "buero_auftrag").get("/api/time-entries", params={"employee_id": welt["tom"].id}).json()
    assert [(e["id"], e["auftrag_geschlossen"]) for e in liste] == [(zu.id, "storniert")]


# --- Punkt 3: Von/Bis wie die Monteurin -------------------------------------------------------------------------------------------

def test_buero_nachtrag_von_bis_pause_aus_dem_tag_vorschau_gleich_buchung(welt):  # noqa: F811
    """Tom hat 07:00–12:00 gebucht; das Büro trägt für ihn 12:00–16:15 nach -- der Tag hat 9:15 h, 45 min bei der Nachtragung (dieselbe
    Rechnung wie bei der Monteurin, test_v483); Vorschau = Buchung."""
    _zeit(welt, welt["tom"], time(7), time(12))
    buero = _buero(welt)
    vorschau = buero.get("/api/time-entries/nachtrag-vorschau", params={"work_date": welt["heute"].isoformat(), "von": "12:00",
                                                                        "bis": "16:15", "employee_id": welt["tom"].id}).json()
    neu = buero.post("/api/time-entries", json={"employee_id": welt["tom"].id, "order_id": welt["order"].id,
                                                "work_date": welt["heute"].isoformat(), "von": "12:00", "bis": "16:15"}).json()
    assert _zahlen(vorschau) == _zahlen(neu) == (Decimal("4.25"), 45, Decimal("3.5"))
    assert (neu["started_at"], neu["ended_at"]) == (f"{welt['heute'].isoformat()}T12:00:00", f"{welt['heute'].isoformat()}T16:15:00")


def test_buero_dauer_bleibt_netto_ohne_pausenregel(welt):  # noqa: F811
    """Gegenprobe: dieselben 4,25 h als Dauer -- gebucht, wie eingegeben, ohne Abzug, ohne Uhrzeiten."""
    _zeit(welt, welt["tom"], time(7), time(12))
    neu = _buero(welt).post("/api/time-entries", json={"employee_id": welt["tom"].id, "order_id": welt["order"].id,
                                                       "work_date": welt["heute"].isoformat(), "hours": "4.25"}).json()
    assert (Decimal(str(neu["gebucht"])), neu["pause"], neu["started_at"], neu["ended_at"]) == (Decimal("4.25"), 0, None, None)


def test_buero_aendert_mit_von_bis(welt):  # noqa: F811
    row = _zeit(welt, welt["tom"], time(7), time(12))
    d = _buero(welt).put(f"/api/time-entries/{row.id}", json={"von": "07:00", "bis": "13:30"}).json()
    assert (d["started_at"], d["ended_at"]) == (f"{welt['heute'].isoformat()}T07:00:00", f"{welt['heute'].isoformat()}T13:30:00")
    assert _zahlen(d) == (Decimal("6.5"), 30, Decimal("6"))


# --- Punkt 3: eine Dauer hat keine Uhrzeiten ---------------------------------------------------------------------------------------

@pytest.mark.parametrize("aenderung", [{"hours": "4"}, {"break_minutes": 15}, {"work_date": "@gestern"}],
                         ids=["stunden", "pause", "tag"])
def test_als_dauer_gespeichert_leert_von_und_bis(welt, aenderung):  # noqa: F811
    """Angriff: eine Von/Bis-Buchung (07:00–12:00) ohne Von/Bis mit Stunden, Pause oder anderem Tag gespeichert -- Beginn und Ende leer (bis
    1.9.89 blieben sie stehen und passten nicht mehr)."""
    row = _zeit(welt, welt["tom"], time(7), time(12))
    werte = {k: (welt["gestern"].isoformat() if v == "@gestern" else v) for k, v in aenderung.items()}
    antwort = _buero(welt).put(f"/api/time-entries/{row.id}", json=werte)
    assert antwort.status_code == 200, antwort.text
    assert (antwort.json()["started_at"], antwort.json()["ended_at"]) == (None, None)
    gespeichert = _frisch(welt, row.id)
    assert (gespeichert.started_at, gespeichert.ended_at) == (None, None)


@pytest.mark.parametrize("aenderung", [{"notes": "Dachrinne"}, {"activity": "Abdichten"}, {"entry_type": "workshop"}, {"order_id": "@offen"}],
                         ids=["notiz", "taetigkeit", "zeitart", "auftrag"])
def test_ohne_zeit_aenderung_bleiben_von_und_bis(welt, aenderung):  # noqa: F811
    """Gegenprobe: Notiz, Tätigkeit, Zeitart oder Auftrag allein -- Beginn, Ende und Stunden bleiben."""
    offen = _zweiter_auftrag(welt)
    row = _zeit(welt, welt["tom"], time(7), time(12))
    werte = {k: (offen.id if v == "@offen" else v) for k, v in aenderung.items()}
    antwort = _buero(welt).put(f"/api/time-entries/{row.id}", json=werte)
    assert antwort.status_code == 200, antwort.text
    gespeichert = _frisch(welt, row.id)
    assert (gespeichert.started_at.time(), gespeichert.ended_at.time(), gespeichert.hours) == (time(7), time(12), Decimal("5"))


def _kolonne_von_bis(w):
    """Mia hat 07:00–12:00 gebucht; Kolonnen-Nachtrag 12:00–16:15 für Mia und Tom -- Mia 45 min Pause (3,50 h), Tom ohne (4,25 h)."""
    _zeit(w, w["mia"], time(7), time(12))
    gruppe = create_group_manual_entry(w["db"], employee_ids=[w["mia"].id, w["tom"].id], team_id=w["team"].id, actor_employee_id=None,
                                       is_admin=True, order_id=w["order"].id, work_date=w["heute"], von=time(12), bis=time(16, 15))
    return gruppe.id


def _mitglieder(w, group_id):
    w["db"].expire_all()
    eintraege = w["db"].query(TimeEntry).filter(TimeEntry.source == "group_manual").all()
    return {e.employee_id: (e.hours, e.started_at is not None, e.ended_at is not None) for e in eintraege}


def test_kolonne_nur_notiz_behaelt_die_stunden_jedes_mitglieds(welt):  # noqa: F811
    """Angriff (Befund 1.9.90): bis 1.9.89 bekam jedes Mitglied beim Ändern nur der Notiz die Stunden des Kopfs (das Mittel 3,875 h)."""
    group_id = _kolonne_von_bis(welt)
    vorher = _mitglieder(welt, group_id)
    assert vorher == {welt["mia"].id: (Decimal("3.5"), True, True), welt["tom"].id: (Decimal("4.25"), True, True)}
    antwort = _buero(welt).put(f"/api/time-entry-groups/{group_id}", json={"notes": "Material nachgeholt"})
    assert antwort.status_code == 200, antwort.text
    assert _mitglieder(welt, group_id) == vorher


def test_kolonne_als_dauer_leert_von_und_bis(welt):  # noqa: F811
    group_id = _kolonne_von_bis(welt)
    antwort = _buero(welt).put(f"/api/time-entry-groups/{group_id}", json={"hours": "4"})
    assert antwort.status_code == 200, antwort.text
    assert _mitglieder(welt, group_id) == {welt["mia"].id: (Decimal("4"), False, False), welt["tom"].id: (Decimal("4"), False, False)}
    gruppe = welt["db"].get(TimeEntryGroup, group_id)
    assert (gruppe.started_at, gruppe.ended_at) == (None, None)
    assert sorted(group_member_ids(welt["db"], group_id)) == sorted([welt["mia"].id, welt["tom"].id])


@pytest.mark.parametrize("aenderung", [{"break_minutes": 15}, {"work_date": "@gestern"}], ids=["pause", "tag"])
def test_monteurin_aendert_pause_oder_tag_nur_mit_von_bis(welt, aenderung):  # noqa: F811
    """Seit 1.9.90: Pause oder Tag ohne Von/Bis wäre eine Dauer -- die Monteurin bekommt 422 (bis dahin nur bei den Stunden), nichts geändert."""
    _einsatz(welt, welt["order"], [(welt["heute"] - timedelta(days=7), welt["heute"])], [welt["mia"]])
    row = _zeit(welt, welt["mia"], time(7), time(12))
    werte = {k: (welt["gestern"].isoformat() if v == "@gestern" else v) for k, v in aenderung.items()}
    antwort = _als(welt, welt["mia"]).put(f"/api/time-entries/{row.id}", json=werte)
    assert (antwort.status_code, antwort.json()["detail"]) == (422, NUR_VON_BIS)
    gespeichert = _frisch(welt, row.id)
    assert (gespeichert.started_at.time(), gespeichert.work_date, gespeichert.break_minutes) == (time(7), welt["heute"], 0)
