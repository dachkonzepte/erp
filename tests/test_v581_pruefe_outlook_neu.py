"""Version 1.9.163 (Stufe 6, R2, Punkt 7): scripts/pruefe_outlook.py ohne utcnow-Warnung und mit den neuen Fällen.

    Warnung        die Ausgabe des Skripts trägt keine DeprecationWarning (echter Prozess)
    Gerät          steht mit Namen und „(Gerät)“ unter den Postfächern, inaktive gekennzeichnet
    Sperre         läuft (kein Fund) oder hängt (Fund)
    Wechsel        Termin im alten Postfach wartet; Termin in einem Postfach ohne Besitzer; offener Löschauftrag
    Gerät doppelt  Termin und Serienvorkommen am Kran neben einem Einsatz, nicht vergangene, nicht bei geschlossenem Auftrag
    Datenschutz    kein Titel in der Ausgabe (Regel 18)
"""

import importlib.util
import os
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.auftragsstatus import status_aendern
from app.database import Base
from app.main import create_resource, create_team
from app.models import AppUser, CalendarEvent, OperationalResource, OutlookCalendarSyncState, OutlookDeleteOrder, OutlookSeriesOccurrence
from app.planning import create_slot
from app.schemas import OperationalResourceCreate, TeamCreate, TeamResourceInput
from tests.grunddaten_schalter import ohne_grunddaten
from tests.pg_schutz import pg_url_pruefen
from tests.test_v090_planning_board import setup_order
from tests.test_v133_invoices import db_session

ROOT = Path(__file__).resolve().parent.parent
JETZT = datetime(2026, 10, 30, 12, 0)
GEHEIM = "Vermietung Geheim"
KRAN = "kran@x.de"


def _skript():
    spec = importlib.util.spec_from_file_location("pruefe_outlook", ROOT / "scripts" / "pruefe_outlook.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def _lauf(db):
    zeilen = []
    rc = _skript().main([], sitzung=db, ausgabe=zeilen.append, jetzt=JETZT)
    return rc, "\n".join(zeilen)


def _kran(db, postfach=KRAN, aktiv=True):
    zeile = OperationalResource(resource_type="Maschine", name="Kran", outlook_mailbox=postfach, active=aktiv)
    db.add(zeile)
    db.commit()
    return zeile


def _ruhig(db, zeile):
    db.commit()
    db.execute(CalendarEvent.__table__.update().where(CalendarEvent.id == zeile.id).values(outlook_synced_at=datetime(2030, 1, 1)))
    db.commit()
    db.expire_all()
    return zeile


def test_keine_warnung_in_der_ausgabe(tmp_path):
    url = pg_url_pruefen(f"sqlite:///{(tmp_path / 'p.db').as_posix()}")
    engine = create_engine(url)
    with ohne_grunddaten():
        Base.metadata.create_all(engine)
    engine.dispose()
    lauf = subprocess.run([sys.executable, str(ROOT / "scripts" / "pruefe_outlook.py")], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
                          env={**os.environ, "DATABASE_URL": url, "ERP_DATA_DIR": str(tmp_path / "data"), "ERP_SECRET_KEY": "test-" + "x" * 40, "PYTHONIOENCODING": "utf-8"})
    assert lauf.returncode == 0, lauf.stdout + lauf.stderr
    assert "Warning" not in lauf.stderr and "utcnow" not in lauf.stderr, lauf.stderr
    assert "Postfächer: keins hinterlegt." in lauf.stdout


def test_das_skript_ruft_utcnow_nicht_auf():
    assert "utcnow" not in (ROOT / "scripts" / "pruefe_outlook.py").read_text(encoding="utf-8").replace("nicht datetime.utcnow()", "")


def test_geraet_unter_den_postfaechern():
    db = db_session()
    _kran(db)
    db.add(OutlookCalendarSyncState(postfach=KRAN, last_synced_at=JETZT, delta_link=f"https://graph.microsoft.com/v1.0/users/{KRAN}/events/delta?$deltatoken=x"))
    db.commit()
    rc, text = _lauf(db)
    assert rc == 0, text
    assert "Kran (Gerät) · kran@x.de" in text
    assert "der Pfad nennt das Postfach nicht" not in text


def test_inaktives_geraet_gekennzeichnet():
    db = db_session()
    _kran(db, aktiv=False)
    assert "Kran (Gerät) · kran@x.de · Konto inaktiv" in _lauf(db)[1]


def test_sperre_laeuft_ist_kein_fund_haengt_ist_einer():
    db = db_session()
    _kran(db)
    stand = OutlookCalendarSyncState(postfach=KRAN, last_synced_at=JETZT, lauf_seit=JETZT - timedelta(minutes=2), lauf_kennung="a")
    db.add(stand)
    db.commit()
    rc, text = _lauf(db)
    assert rc == 0 and "ein Lauf ist gerade dran" in text
    stand.lauf_seit = JETZT - timedelta(minutes=11)
    db.commit()
    rc, text = _lauf(db)
    assert rc == 1 and "der nächste Lauf übernimmt sie" in text


def test_termin_im_alten_postfach_wartet():
    db = db_session()
    konto = AppUser(username="anna", display_name="Anna", password_hash="x", role="admin", outlook_mailbox="neu@x.de")
    db.add(konto)
    db.flush()
    _ruhig(db, _termin(db, owner_user_id=konto.id, outlook_postfach="alt@x.de", outlook_event_id="K"))
    rc, text = _lauf(db)
    assert rc == 1 and "liegt noch im alten Postfach" in text


def _termin(db, *, tag=date(2026, 11, 3), **werte):
    zeile = CalendarEvent(title=GEHEIM, start_at=datetime.combine(tag, datetime.min.time()).replace(hour=8), end_at=datetime.combine(tag, datetime.min.time()).replace(hour=12), **werte)
    db.add(zeile)
    db.flush()
    return zeile


def test_termin_in_einem_postfach_ohne_besitzer():
    db = db_session()
    konto = AppUser(username="anna", display_name="Anna", password_hash="x", role="admin", outlook_mailbox=None)
    db.add(konto)
    db.flush()
    zeile = _ruhig(db, _termin(db, owner_user_id=konto.id, outlook_postfach="frei@x.de", outlook_event_id="K"))
    stand = _skript().pruefen(db, jetzt=JETZT)
    assert [o["id"] for o in stand["ohne_besitzer"]] == [zeile.id] and stand["warten"] == []
    rc, text = _lauf(db)
    assert rc == 1 and "liegt in frei@x.de" in text


def test_offener_loeschauftrag():
    db = db_session()
    db.add(OutlookDeleteOrder(postfach="a@x.de", outlook_event_id="K" * 40, last_error_type="OutlookSyncError", created_at=JETZT))
    db.commit()
    rc, text = _lauf(db)
    assert rc == 1 and "a@x.de · " + "K" * 24 + "…" in text and "letzter Fehler OutlookSyncError" in text
    assert "K" * 25 not in text


def _einsatz(db, von=date(2026, 11, 2), bis=date(2026, 11, 4)):
    kran = create_resource(OperationalResourceCreate(resource_number="K-1", resource_type="Maschine", name="Kran", identifier="K1"), db)
    team = create_team(TeamCreate(team_number="A", name="Kolonne A", employees=[], resources=[TeamResourceInput(resource_id=kran.id, role="Standard")]), db)
    order = setup_order(db, "1")
    return kran, order, create_slot(db, order_id=order.id, team_id=team.id, start_date=von, end_date=bis)


def test_geraet_doppelt_termin_und_serie_ohne_titel():
    db = db_session()
    kran, _, einsatz = _einsatz(db)
    _ruhig(db, _termin(db, resource_id=kran.id, outlook_postfach=KRAN, outlook_event_id="K"))
    db.add(OutlookSeriesOccurrence(resource_id=kran.id, outlook_postfach=KRAN, outlook_event_id="S", occurrence_type="occurrence", title=GEHEIM, start_at=datetime(2026, 11, 4, 8), end_at=datetime(2026, 11, 4, 9)))
    db.commit()
    stand = _skript().pruefen(db, jetzt=JETZT)
    assert [(g["einsatz"], g["geraet"], g["serie"], g["tag"]) for g in stand["geraet_doppelt"]] == [(einsatz.id, "Kran", False, date(2026, 11, 3)), (einsatz.id, "Kran", True, date(2026, 11, 4))]
    rc, text = _lauf(db)
    assert rc == 1 and f"Einsatz {einsatz.id} · Kran · 03.11.2026 · Termin" in text and "Serienvorkommen" in text
    assert GEHEIM not in text


def test_vergangener_einsatz_zaehlt_nicht():
    db = db_session()
    kran, _, _ = _einsatz(db, date(2026, 9, 1), date(2026, 9, 2))
    _ruhig(db, _termin(db, tag=date(2026, 9, 1), resource_id=kran.id, outlook_postfach=KRAN, outlook_event_id="K"))
    assert _skript().pruefen(db, jetzt=JETZT)["geraet_doppelt"] == []


def test_geschlossener_auftrag_zaehlt_nicht():
    db = db_session()
    kran, order, _ = _einsatz(db)
    _ruhig(db, _termin(db, resource_id=kran.id, outlook_postfach=KRAN, outlook_event_id="K"))
    status_aendern(db, order.id, "storniert", "abgesagt")
    db.commit()
    assert _skript().pruefen(db, jetzt=JETZT)["geraet_doppelt"] == []


def test_die_sitzung_schreibt_nichts(tmp_path):
    url = pg_url_pruefen(f"sqlite:///{(tmp_path / 'q.db').as_posix()}")
    engine = create_engine(url)
    with ohne_grunddaten():
        Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    _kran(db)
    db.close()
    engine.dispose()
    zeilen = []
    assert _skript().main([], umgebung={"DATABASE_URL": url}, ausgabe=zeilen.append) == 0
