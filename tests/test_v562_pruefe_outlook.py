"""Version 1.9.142 (Stufe 6, R1, Punkt 0): scripts/pruefe_outlook.py -- wie steht der Outlook-Abgleich?

    Stand        je Postfach letzter Lauf, letzter Fehler (nur die Art), Alter des Delta-Links, Pfad ohne Token; ohne Fund Rückgabe 0
    Funde        Termin wartet auf Senden (wie _needs_push()), doppelte Kennung, ganztägig aus dem ERP -- je Rückgabe 1
    Datenschutz  kein Titel, kein Ort, keine Notiz, kein Token in der Ausgabe (Regel 18)
    nur lesen    die eigene Sitzung schreibt nicht; ohne DATABASE_URL Rückgabe 2
"""

import importlib.util
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import AppUser, CalendarEvent, OutlookCalendarSyncState, OutlookSyncSettings
from tests.pg_schutz import pg_url_pruefen
from tests.test_v133_invoices import db_session

ROOT = Path(__file__).resolve().parent.parent
JETZT = datetime(2026, 10, 30, 12, 0)
TOKEN = "GEHEIMES_TOKEN_xyz"
GEHEIM = "Besprechung Geheimprojekt"


def _skript():
    spec = importlib.util.spec_from_file_location("pruefe_outlook", ROOT / "scripts" / "pruefe_outlook.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def _lauf(db):
    zeilen = []
    rc = _skript().main([], sitzung=db, ausgabe=zeilen.append, jetzt=JETZT)
    return rc, zeilen


def _konto(db, name="tobias", postfach="tobias@dachkonzepte.gmbh"):
    user = AppUser(username=name, display_name=name, password_hash="x", role="admin", outlook_mailbox=postfach)
    db.add(user)
    db.flush()
    return user


def _termin(db, user, **werte):
    start = werte.pop("start_at", datetime(2026, 11, 2, 9, 0))
    zeile = CalendarEvent(title=GEHEIM, location="Werkstor 2", notes="Vertraulich", owner_user_id=user.id, start_at=start,
                          end_at=werte.pop("end_at", start + timedelta(hours=1)), **werte)
    db.add(zeile)
    db.flush()
    return zeile


def _gesendet(db, user, kennung="AAA", **werte):
    """Ein Termin, wie ihn ein erfolgreicher Abgleich hinterlässt -- keine Änderung seit dem Senden."""
    zeile = _termin(db, user, outlook_event_id=kennung, **werte)
    db.commit()
    db.execute(text("UPDATE calendar_events SET outlook_synced_at = updated_at WHERE id = :i"), {"i": zeile.id})
    db.commit()
    db.expire_all()
    return zeile


def test_ohne_postfach_und_termin_nichts_gefunden():
    db = db_session()
    rc, zeilen = _lauf(db)
    assert rc == 0
    assert "Postfächer: keins hinterlegt." in zeilen
    assert "Warten auf Senden: 0" in zeilen


def test_stand_je_postfach_mit_alter_und_pfad_ohne_token():
    db = db_session()
    user = _konto(db)
    db.add(OutlookCalendarSyncState(app_user_id=user.id, last_synced_at=JETZT - timedelta(days=9),
                                    delta_link=f"https://graph.microsoft.com/v1.0/users/{user.outlook_mailbox}/events/delta?$deltatoken={TOKEN}"))
    db.commit()
    rc, zeilen = _lauf(db)
    text_ = "\n".join(zeilen)
    assert rc == 0, text_
    assert "tobias · tobias@dachkonzepte.gmbh" in text_
    assert "letzter Lauf: 21.10.2026 14:00" in text_  # UTC 12:00 -> Berlin 14:00
    assert "letzter Fehler: keiner" in text_
    assert "Delta-Link: 9 Tage alt, Pfad /v1.0/users/tobias@dachkonzepte.gmbh/events/delta" in text_
    assert TOKEN not in text_


def test_delta_link_eines_anderen_postfachs_faellt_auf():
    db = db_session()
    user = _konto(db, postfach="neu@dachkonzepte.gmbh")
    db.add(OutlookCalendarSyncState(app_user_id=user.id, last_synced_at=JETZT,
                                    delta_link="https://graph.microsoft.com/v1.0/users/alt@dachkonzepte.gmbh/events/delta?$deltatoken=x"))
    db.commit()
    stand = _skript().pruefen(db, jetzt=JETZT)
    assert stand["postfaecher"][0]["pfad_nennt_postfach"] is False
    _, zeilen = _lauf(db)
    assert any(z.strip().startswith("Achtung: der Pfad nennt das Postfach nicht") for z in zeilen)


def test_letzter_fehler_ist_ein_fund_und_nennt_nur_die_art():
    db = db_session()
    user = _konto(db)
    db.add(OutlookCalendarSyncState(app_user_id=user.id, last_error_type="OutlookSyncError", last_error_at=JETZT - timedelta(hours=3)))
    db.commit()
    rc, zeilen = _lauf(db)
    assert rc == 1
    assert "    letzter Fehler: OutlookSyncError am 30.10.2026 10:00" in zeilen
    assert "    Delta-Link: keiner (der nächste Lauf fragt den ganzen Kalender ab)" in zeilen


def test_termine_die_auf_senden_warten_wie_needs_push():
    db = db_session()
    user = _konto(db)
    neu = _termin(db, user)
    ruhig = _gesendet(db, user, kennung="RUHIG")
    geaendert = _gesendet(db, user, kennung="GEAENDERT")
    geaendert.title = "Anders"
    db.commit()
    stand = _skript().pruefen(db, jetzt=JETZT)
    assert {w["id"]: w["grund"] for w in stand["warten"]} == {neu.id: "noch nie gesendet", geaendert.id: "im ERP geändert"}
    assert ruhig.id not in {w["id"] for w in stand["warten"]}
    assert _lauf(db)[0] == 1


def test_termin_eines_kontos_ohne_postfach_wartet_nicht():
    db = db_session()
    _termin(db, _konto(db, postfach=None))
    db.commit()
    assert _skript().pruefen(db, jetzt=JETZT)["warten"] == []


def test_doppelte_outlook_kennung():
    db = db_session()
    a, b = _konto(db, "a", "a@x.de"), _konto(db, "b", "b@x.de")
    eins, zwei = _gesendet(db, a, kennung="DOPPELT"), _gesendet(db, b, kennung="DOPPELT")
    _gesendet(db, a, kennung="EINMAL")
    stand = _skript().pruefen(db, jetzt=JETZT)
    assert [d["termine"] for d in stand["doppelt"]] == [[eins.id, zwei.id]]
    assert _lauf(db)[0] == 1


def test_ganztaegige_termine_aus_dem_erp_nicht_aus_outlook():
    db = db_session()
    user = _konto(db)
    erp = _gesendet(db, user, kennung="G1", all_day=True, external_source="erp")
    _gesendet(db, user, kennung="G2", all_day=True, external_source="outlook")
    _gesendet(db, user, kennung="G3", all_day=False, external_source="erp")
    stand = _skript().pruefen(db, jetzt=JETZT)
    assert [g["id"] for g in stand["ganztaegig"]] == [erp.id]
    assert stand["ganztaegig"][0]["gesendet"] is True
    assert _lauf(db)[0] == 1


def test_kein_inhalt_der_termine_in_der_ausgabe():
    db = db_session()
    user = _konto(db)
    _termin(db, user, all_day=True, outlook_event_id="X")
    _termin(db, user, outlook_event_id="X")
    db.commit()
    rc, zeilen = _lauf(db)
    text_ = "\n".join(zeilen)
    assert rc == 1
    for geheim in (GEHEIM, "Werkstor 2", "Vertraulich"):
        assert geheim not in text_


def test_ohne_database_url_rueckgabe_2():
    zeilen = []
    assert _skript().main([], umgebung={}, ausgabe=zeilen.append) == 2
    assert zeilen == ["DATABASE_URL ist nicht gesetzt -- auf dem Server zuerst: set -a; source .env; set +a"]


def test_die_eigene_sitzung_schreibt_nicht(tmp_path):
    url = pg_url_pruefen(f"sqlite:///{(tmp_path / 'bestand.db').as_posix()}")  # Regel 27: wer DATABASE_URL weitergibt, prüft sie
    engine = create_engine(url)
    try:
        Base.metadata.create_all(engine)
        db = sessionmaker(bind=engine)()
        user = _konto(db)
        _gesendet(db, user)
        db.merge(OutlookSyncSettings(id=1, enabled=True))
        db.commit()
        db.close()
        zeilen = []
        assert _skript().main([], umgebung={"DATABASE_URL": url}, ausgabe=zeilen.append) == 0
        assert zeilen[0] == "Abgleich: eingeschaltet"
        sitzung = _skript().nur_lesende_sitzung(url)
        try:
            with pytest.raises(DBAPIError):
                sitzung.execute(text("UPDATE calendar_events SET title = 'x'"))
                sitzung.commit()
            sitzung.rollback()
        finally:
            bind = sitzung.get_bind()
            sitzung.close()
            bind.dispose()
    finally:
        engine.dispose()
