"""Version 1.9.241 (Stufe 6, R3b, Punkt 3): Plantafel -> Kran-Kalender. Gegen die Graph-Attrappe (tests/outlook_attrappe.py), das Kran-Postfach ist am
echten Mandanten noch nicht eingerichtet.

    Termine      ein Einsatz mit einem Gerät mit Postfach (Baustelle und Kranvermietung) steht an den Tagen des Geräts in dessen Kalender: je Folge von Tagen
                 ein ganztägiger Termin, geht sofort hinaus; Ändern verschiebt ihn, Löschen nimmt ihn heraus, ein geschlossener Auftrag hat keinen
    führend      in Outlook geändert -> der nächste Abgleich überschreibt; in Outlook gelöscht -> der nächste Abgleich legt ihn neu an
    Büro         der Büro-Kalender ändert und löscht ihn nicht (409); als Belegung zählt er nicht gegen den eigenen Einsatz
    Übernehmen   ein Termin direkt in Outlook bleibt Termin am Kran (warnt weiter) und lässt sich als Kranvermietung übernehmen -- er wird der Termin des
                 Einsatzes
    Nachziehen   bekommt ein Gerät sein Postfach erst nach der Planung, legt der Abgleich seines Postfachs die Termine an
    Migration    c9d2e6a3f417
"""

import os
import uuid
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import create_engine, func, select, text

from app.auftragsstatus import status_aendern, storno_zuruecknehmen
from app.kran_kalender import _laeufe
from app.main import create_customer, create_resource
from app.models import CalendarEvent, OutlookDeleteOrder, PlanningSlot
from app.outlook_calendar_sync import postfach_des_geraets, sync_postfach
from app.schemas import CustomerCreate, OperationalResourceCreate
from tests.test_v090_planning_board import setup_order
from tests.test_v380_nummern_eindeutig import _alembic, _ok
from tests.test_v563_konflikte_beim_speichern import MONTAG, _kolonne, _person
from tests.test_v579_geraete_postfach import KRAN, _geraet, _lauf, welt  # noqa: F401  (welt ist eine Fixture)

MIGRATION = "c9d2e6a3f417"
VORHER = "b5f1c7e2a948"
PG_URL = os.getenv("ERP_TEST_POSTGRES_URL")


def _tag(n):
    return (MONTAG + timedelta(days=n)).isoformat()


def _einsatz(w, order=None, *, geraete=None, von=0, bis=2, **mehr):
    order = order or setup_order(w.db, uuid.uuid4().hex[:6])
    tom = _person(w.db, f"M-{uuid.uuid4().hex[:4]}", "Tom")
    team = _kolonne(w.db, uuid.uuid4().hex[:4], [tom])
    body = {"order_id": order.id, "team_id": team.id, "start_date": _tag(von), "end_date": _tag(bis), "planned_hours": "1",
            "geraete": geraete if geraete is not None else [{"resource_id": w.kran.id}], **mehr}
    r = w.client.post("/api/planning/slots", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def _termine(w, slot_id):
    w.db.expire_all()
    return list(w.db.scalars(select(CalendarEvent).where(CalendarEvent.planning_slot_id == slot_id).order_by(CalendarEvent.start_at)))


def _outlook(w):
    """Die Termine im Kran-Postfach der Attrappe: (Betreff, ganztägig, erster Tag, Tag nach dem letzten)."""
    return sorted((e["subject"], e.get("isAllDay"), e["start"]["dateTime"][:10], e["end"]["dateTime"][:10]) for e in w.ms.postfach(KRAN).events.values())


def test_folgen_von_tagen():
    d = [date(2026, 11, t) for t in (2, 3, 4, 6, 9, 10)]
    assert _laeufe(d) == [(d[0], d[2]), (d[3], d[3]), (d[4], d[5])]


def test_einsatz_mit_kran_steht_im_kalender_und_geht_hinaus(welt):
    e = _einsatz(welt)
    [t] = _termine(welt, e["id"])
    assert (t.resource_id, t.owner_user_id, t.all_day, t.external_source) == (welt.kran.id, None, True, "erp")
    assert (t.start_at, t.end_at) == (datetime(2026, 11, 2), datetime(2026, 11, 4))
    assert t.title == f"vorläufig: {e['order_number']} · {e['project_name']}" and "Besetzung: Tom Test" in t.notes and "Aus der Plantafel" in t.notes
    assert t.outlook_event_id and t.outlook_postfach == KRAN
    assert _outlook(welt) == [(t.title, True, "2026-11-02", "2026-11-05")]


def test_einzelne_tage_ergeben_einzelne_termine(welt):
    e = _einsatz(welt, geraete=[{"resource_id": welt.kran.id, "tage": [_tag(0), _tag(2)]}])
    assert [(t.start_at.date(), t.end_at.date()) for t in _termine(welt, e["id"])] == [(MONTAG, MONTAG), (MONTAG + timedelta(days=2),) * 2]


def test_ohne_postfach_oder_inaktiv_kein_termin(welt):
    ohne = create_resource(OperationalResourceCreate(resource_number="K-2", resource_type="Maschine", name="Kran ohne Postfach", identifier="K2"), welt.db)
    e = _einsatz(welt, geraete=[{"resource_id": ohne.id}])
    assert _termine(welt, e["id"]) == []
    e = _einsatz(welt)
    assert len(_termine(welt, e["id"])) == 1 and len(_outlook(welt)) == 1
    _geraet(welt).active = False  # nach der Planung abgeschaltet: beim nächsten Speichern fällt der Termin weg, auch in Outlook
    welt.db.commit()
    assert welt.client.put(f"/api/planning/slots/{e['id']}", json={"notes": "Kran in der Werkstatt"}).status_code == 200
    assert _termine(welt, e["id"]) == [] and _outlook(welt) == []


def test_aendern_verschiebt_den_termin(welt):
    e = _einsatz(welt)
    [vorher] = _termine(welt, e["id"])
    kennung, termin_id = vorher.outlook_event_id, vorher.id
    r = welt.client.put(f"/api/planning/slots/{e['id']}", json={"start_date": _tag(7), "end_date": _tag(8), "status": "fest", "trotzdem_planen": True})
    assert r.status_code == 200, r.text
    [t] = _termine(welt, e["id"])
    assert (t.id, t.outlook_event_id, t.start_at.date(), t.end_at.date()) == (termin_id, kennung, MONTAG + timedelta(days=7), MONTAG + timedelta(days=8))
    assert t.title == f"{e['order_number']} · {e['project_name']}"  # fest: ohne „vorläufig:“
    assert _outlook(welt) == [(t.title, True, "2026-11-09", "2026-11-11")]


def test_loeschen_nimmt_den_termin_aus_outlook(welt):
    e = _einsatz(welt)
    assert len(_outlook(welt)) == 1
    assert welt.client.delete(f"/api/planning/slots/{e['id']}").status_code == 200
    assert _termine(welt, e["id"]) == [] and _outlook(welt) == []
    assert welt.db.scalar(select(func.count()).select_from(OutlookDeleteOrder)) == 0  # abgearbeitet


def test_geschlossener_auftrag_hat_keinen_termin(welt):
    order = setup_order(welt.db, "storno")
    e = _einsatz(welt, order)
    status_aendern(welt.db, order.id, "storniert", "Kunde hat abgesagt")
    assert _termine(welt, e["id"]) == [] and _outlook(welt) == []
    storno_zuruecknehmen(welt.db, order.id, "versehentlich")
    assert len(_termine(welt, e["id"])) == 1 and len(_outlook(welt)) == 1


def test_kranvermietung_mit_bediener(welt):
    kunde = create_customer(CustomerCreate(last_name="Kranmieter"), welt.db)
    tom = _person(welt.db, "M-K", "Kai")
    r = welt.client.post("/api/planning/slots", json={"art": "kranvermietung", "customer_id": kunde.id, "employee_ids": [tom.id],
                                                       "geraete": [{"resource_id": welt.kran.id}], "start_date": _tag(1), "end_date": _tag(1),
                                                       "notes": "ab 8 Uhr"})
    assert r.status_code == 200, r.text
    [t] = _termine(welt, r.json()["id"])
    assert t.title == "vorläufig: Kranvermietung · Kranmieter" and "Bediener: Kai Test" in t.notes and "Notiz: ab 8 Uhr" in t.notes


def test_in_outlook_geaendert_ueberschreibt_der_abgleich(welt):
    e = _einsatz(welt)
    [t] = _termine(welt, e["id"])
    welt.ms.postfach(KRAN).aendern(t.outlook_event_id, subject="Kran frei, Meier holt ihn")
    zaehler = _lauf(welt)
    assert zaehler["plantafel"] == 1, zaehler
    [nachher] = _termine(welt, e["id"])
    assert nachher.title == t.title and _outlook(welt) == [(t.title, True, "2026-11-02", "2026-11-05")]
    assert _lauf(welt)["plantafel"] == 0  # danach Ruhe


def test_in_outlook_geloescht_legt_der_abgleich_neu_an(welt):
    e = _einsatz(welt)
    [t] = _termine(welt, e["id"])
    alt, titel, termin_id = t.outlook_event_id, t.title, t.id
    _lauf(welt)  # Delta-Link steht
    welt.ms.postfach(KRAN).loeschen(alt)
    assert _outlook(welt) == []
    zaehler = _lauf(welt)
    assert zaehler["plantafel"] == 1, zaehler
    [neu] = _termine(welt, e["id"])
    assert neu.id == termin_id and neu.outlook_event_id and neu.outlook_event_id != alt
    assert _outlook(welt) == [(titel, True, "2026-11-02", "2026-11-05")]


def test_ganzer_kalender_ohne_den_termin_legt_ihn_neu_an(welt):
    """Abgelaufener Delta-Link: der Abruf des ganzen Kalenders findet den Termin nicht mehr (in Outlook gelöscht), Graph antwortet 404 -- ein Termin
    der Plantafel geht neu hinaus, statt im ERP wegzufallen."""
    e = _einsatz(welt)
    [t] = _termine(welt, e["id"])
    alt, titel = t.outlook_event_id, t.title
    _lauf(welt)
    welt.ms.postfach(KRAN).loeschen(alt)
    welt.ms.ablaufen(KRAN)
    zaehler = _lauf(welt)
    assert zaehler["plantafel"] == 1 and zaehler["deleted"] == 0, zaehler
    [neu] = _termine(welt, e["id"])
    assert neu.outlook_event_id != alt and _outlook(welt) == [(titel, True, "2026-11-02", "2026-11-05")]


def test_buero_kalender_aendert_ihn_nicht(welt):
    e = _einsatz(welt)
    [t] = _termine(welt, e["id"])
    r = welt.client.put(f"/api/calendar-events/{t.id}", json={"title": "anders"})
    assert r.status_code == 409 and "Plantafel" in r.json()["detail"], r.text
    assert welt.client.delete(f"/api/calendar-events/{t.id}").status_code == 409
    assert len(_termine(welt, e["id"])) == 1


def test_der_eigene_termin_warnt_nicht_ein_fremder_schon(welt):
    e = _einsatz(welt)
    r = welt.client.put(f"/api/planning/slots/{e['id']}", json={"start_date": _tag(1)})  # Zeitraum geändert: prüft die Warnungen
    assert r.status_code == 200, r.text
    welt.ms.postfach(KRAN).anlegen("Kran an Meier", datetime(2026, 11, 3, 8), datetime(2026, 11, 3, 12))
    _lauf(welt)
    r = welt.client.put(f"/api/planning/slots/{e['id']}", json={"start_date": _tag(0)})
    assert r.status_code == 409 and [w["label"] for w in r.json()["warnungen"]] == ["Kran 30 m · Termin: Kran an Meier"], r.text


def test_termin_aus_outlook_als_kranvermietung_uebernehmen(welt):
    kennung = welt.ms.postfach(KRAN).anlegen("Kran für Meier, Tel. 0170", datetime(2026, 11, 4, 7), datetime(2026, 11, 4, 11))
    _lauf(welt)
    termin = welt.db.scalar(select(CalendarEvent).where(CalendarEvent.outlook_event_id == kennung))
    assert termin.planning_slot_id is None
    kunde = create_customer(CustomerCreate(last_name="Meier"), welt.db)
    vorher = welt.db.scalar(select(func.count()).select_from(CalendarEvent))
    r = welt.client.post(f"/api/planning/kran-termine/{termin.id}/kranvermietung", json={"customer_id": kunde.id})
    assert r.status_code == 200, r.text
    e = r.json()
    assert (e["art"], e["start_date"], e["end_date"], e["notes"], [g["id"] for g in e["resources"]]) == (
        "kranvermietung", "2026-11-04", "2026-11-04", "Kran für Meier, Tel. 0170", [welt.kran.id])
    [t] = _termine(welt, e["id"])
    assert (t.id, t.outlook_event_id, t.all_day, t.external_source, t.title) == (termin.id, kennung, True, "erp", "vorläufig: Kranvermietung · Meier")
    assert welt.db.scalar(select(func.count()).select_from(CalendarEvent)) == vorher  # derselbe Termin, kein zweiter
    assert _outlook(welt) == [("vorläufig: Kranvermietung · Meier", True, "2026-11-04", "2026-11-05")]
    # schon übernommen -- auch mit „trotzdem planen“ (Gegenprobe 241_7c: ohne trotzdem_planen lehnte die Warnung „Gerät doppelt“ ab, nicht diese Regel)
    r = welt.client.post(f"/api/planning/kran-termine/{termin.id}/kranvermietung", json={"customer_id": kunde.id, "trotzdem_planen": True})
    assert r.status_code == 409 and "schon zu einem Einsatz" in r.json()["detail"], r.text


def test_uebernehmen_bis_mitternacht_ist_ein_tag(welt):
    kunde = create_customer(CustomerCreate(last_name="Meier"), welt.db)
    termin = welt.client.post("/api/calendar-events", json={"title": "Abends", "start_at": "2026-11-04T18:00:00", "end_at": "2026-11-05T00:00:00",
                                                            "resource_id": welt.kran.id}).json()
    r = welt.client.post(f"/api/planning/kran-termine/{termin['id']}/kranvermietung", json={"customer_id": kunde.id})
    assert r.status_code == 200 and (r.json()["start_date"], r.json()["end_date"]) == ("2026-11-04", "2026-11-04"), r.text


def test_uebernehmen_ablehnungen(welt):
    kunde = create_customer(CustomerCreate(last_name="Meier"), welt.db)
    assert welt.client.post("/api/planning/kran-termine/99999/kranvermietung", json={"customer_id": kunde.id}).status_code == 404
    konto = welt.client.post("/api/calendar-events", json={"title": "Besprechung", "start_at": "2026-11-04T09:00:00", "end_at": "2026-11-04T10:00:00",
                                                           "owner_user_id": welt.anna.id}).json()
    assert welt.client.post(f"/api/planning/kran-termine/{konto['id']}/kranvermietung", json={"customer_id": kunde.id}).status_code == 409
    privat = welt.client.post("/api/calendar-events", json={"title": "Geheim", "start_at": "2026-11-05T09:00:00", "end_at": "2026-11-05T10:00:00",
                                                            "resource_id": welt.kran.id, "is_private": True}).json()
    r = welt.client.post(f"/api/planning/kran-termine/{privat['id']}/kranvermietung", json={"customer_id": kunde.id})
    assert r.status_code == 200 and r.json()["notes"] is None, r.text  # privat: der Titel wandert nicht in die Notiz
    # eine Warnung: der Kran ist an dem Tag schon an einer Baustelle -- nichts übernommen
    _einsatz(welt, von=9, bis=9)
    fremd = welt.client.post("/api/calendar-events", json={"title": "Anruf", "start_at": "2026-11-11T09:00:00", "end_at": "2026-11-11T10:00:00",
                                                           "resource_id": welt.kran.id}).json()
    r = welt.client.post(f"/api/planning/kran-termine/{fremd['id']}/kranvermietung", json={"customer_id": kunde.id})
    assert r.status_code == 409 and [w["type"] for w in r.json()["warnungen"]] == ["resource"], r.text
    welt.db.expire_all()
    assert welt.db.get(CalendarEvent, fremd["id"]).planning_slot_id is None


def test_postfach_nach_der_planung_zieht_der_abgleich_nach(welt):
    zweiter = create_resource(OperationalResourceCreate(resource_number="K-3", resource_type="Maschine", name="Kran 2", identifier="K3"), welt.db)
    from app.berlin_time import berlin_today
    tage = (berlin_today() - MONTAG).days + 7  # nachziehen() nimmt Einsätze, die heute oder später enden
    vorbei = _einsatz(welt, geraete=[{"resource_id": zweiter.id}], von=-14, bis=-13)
    e = _einsatz(welt, geraete=[{"resource_id": zweiter.id}], von=tage, bis=tage + 1)
    assert _termine(welt, e["id"]) == []
    welt.ms.postfach("kran2@x.de")
    assert welt.client.put(f"/api/outlook-sync-settings/geraete/{zweiter.id}", json={"outlook_mailbox": "kran2@x.de"}).status_code == 200
    welt.db.expire_all()
    zaehler = sync_postfach(welt.db, postfach_des_geraets(welt.db.get(type(_geraet(welt)), zweiter.id)))
    assert zaehler["pushed_created"] == 1, repr(sorted(zaehler.items()))
    [t] = _termine(welt, e["id"])
    assert t.outlook_postfach == "kran2@x.de" and len(welt.ms.postfach("kran2@x.de").events) == 1
    assert _termine(welt, vorbei["id"]) == []  # ein vergangener Einsatz bekommt keinen Termin mehr


# --- Migration c9d2e6a3f417 ---------------------------------------------------------------------------------------------------------------

def _probe(url, engine):
    from tests.test_v633_besetzung_je_einsatz import _bestand
    _ok(_alembic(url, "upgrade", VORHER))
    b = _bestand(engine)
    with engine.begin() as c:
        geraet = c.execute(text("INSERT INTO operational_resources (resource_number, resource_type, name, active, created_at, updated_at) "
                                "VALUES ('K-1', 'Maschine', 'Kran', :a, '2026-09-01', '2026-09-01') RETURNING id"), {"a": True}).scalar()
        c.execute(text("INSERT INTO calendar_events (title, start_at, end_at, all_day, resource_id, is_private, external_source, created_at, updated_at) "
                       "VALUES ('Anruf', '2026-11-03 08:00:00', '2026-11-03 10:00:00', :f, :g, :f, 'outlook', '2026-09-01', '2026-09-01')"),
                  {"f": False, "g": geraet})
    _ok(_alembic(url, "upgrade", MIGRATION))
    with engine.begin() as c:
        assert c.execute(text("SELECT planning_slot_id FROM calendar_events")).scalars().all() == [None]
        c.execute(text("INSERT INTO calendar_events (title, start_at, end_at, all_day, resource_id, is_private, external_source, planning_slot_id, "
                       "created_at, updated_at) VALUES ('Einsatz', '2026-11-02 00:00:00', '2026-11-04 00:00:00', :t, :g, :f, 'erp', :s, '2026-09-01', "
                       "'2026-09-01')"), {"t": True, "f": False, "g": geraet, "s": b["slots"][0]})
    _ok(_alembic(url, "downgrade", VORHER))
    with engine.connect() as c:
        assert c.execute(text("SELECT title FROM calendar_events")).scalars().all() == ["Anruf"]  # der Termin des Einsatzes fällt weg
    _ok(_alembic(url, "upgrade", "head"))


def test_migration_auf_einem_bestand_sqlite(tmp_path):
    url = f"sqlite:///{(tmp_path / 'kran.db').as_posix()}"
    engine = create_engine(url)
    try:
        _probe(url, engine)
    finally:
        engine.dispose()


def test_migration_auf_einem_bestand_postgresql():
    if not PG_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    schema = f"pgtest_mig_kran_{uuid.uuid4().hex[:8]}"
    admin = create_engine(PG_URL)
    with admin.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
    url = f"{PG_URL}{'&' if '?' in PG_URL else '?'}options=-csearch_path={schema}"
    engine = create_engine(PG_URL, connect_args={"options": f"-csearch_path={schema}", "application_name": schema})
    try:
        _probe(url, engine)
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE application_name = :n"), {"n": schema})
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin.dispose()
