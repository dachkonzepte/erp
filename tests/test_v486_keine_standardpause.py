"""Seit 1.9.61 (Stufe 4, R3 Nachrunde, Punkt 2): die Standardpause entfällt -- überall gilt nur die Pause nach Zeitregel je Tag und die
selbst eingetragene Mindestpause (Feierabend, Nachtrag, Kolonne, Büro).

    Wächter        `default_break_minutes` steht unter app/ nur noch an der Spalte (app/models.py) und als Beschriftung alter Verlaufseinträge
                   (app/audit.py, liest die Einstellung nicht) -- keine Vorlage, kein Schema, keine Geschäftslogik liest sie
    Zeitregeln     GET/PUT der Zeitregeln ohne das Feld; eine mitgeschickte Standardpause wird nicht übernommen; die Einstellungsseite hat
                   kein Feld mehr dafür
    5:00 h         über Feierabend, Nachtrag (Monteurin, Von/Bis) und Gruppenbuchung (Büro, Dauer) je 0 min Pause -- auch wenn in der alten
                   Spalte 30 steht
"""

import re
from datetime import datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

from app.models import TimeEntry, TimeEntryGroupMember
from app.routers import pages as pages_router
from app.routers import time_backoffice as time_backoffice_router
from app.routers import time_tracking as time_tracking_router
from app.time_backoffice import load_time_settings
from app.time_tracking import start_timer
from tests.test_v471_heute_server import _als, _einsatz, welt  # noqa: F401  (Fixture)
from tests import vorlagen_js as vj

ROOT = Path(__file__).resolve().parents[1]
ERLAUBT = {"app/models.py": "die Spalte bleibt in der Datenbank", "app/audit.py": "Beschriftung alter Verlaufseinträge (liest nicht)"}


def test_waechter_niemand_liest_die_standardpause():
    funde = {}
    for pfad in sorted((ROOT / "app").rglob("*")):
        if pfad.suffix not in (".py", ".html", ".js", ".css") or "__pycache__" in pfad.parts:
            continue
        # die Bezeichner im Code (klein geschrieben) -- die Erklärung „Standardpause“ in Kommentaren zählt nicht
        if re.search(r"default_break_minutes|defaultBreak|standardpause", pfad.read_text(encoding="utf-8")):
            funde[pfad.relative_to(ROOT).as_posix()] = True
    assert sorted(funde) == sorted(ERLAUBT), "Standardpause gelesen außerhalb der erlaubten Stellen"
    modell = (ROOT / "app" / "models.py").read_text(encoding="utf-8")
    assert len(re.findall(r"default_break_minutes", modell)) == 1  # nur die Spalte


def test_waechter_findet_einen_leser(tmp_path, monkeypatch):
    """Gegenprobe des Wächters: eine Datei, die die Standardpause liest, fällt auf."""
    (tmp_path / "app").mkdir()
    for name in ERLAUBT:
        (tmp_path / name).write_text("default_break_minutes = 0\n", encoding="utf-8")
    (tmp_path / "app" / "x.py").write_text("p = regeln.default_break_minutes\n", encoding="utf-8")
    monkeypatch.setitem(globals(), "ROOT", tmp_path)
    try:
        test_waechter_niemand_liest_die_standardpause()
    except AssertionError:
        return
    raise AssertionError("Wächter hat den Leser nicht gefunden")


def test_zeitregeln_ohne_standardpause(welt):  # noqa: F811
    client = welt["client"](welt["db"], time_backoffice_router.router)
    stand = client.get("/api/time-backoffice/settings").json()
    assert "default_break_minutes" not in stand
    r = client.put("/api/time-backoffice/settings", json={**stand, "default_break_minutes": 45})
    assert r.status_code == 200, r.text
    assert "default_break_minutes" not in r.json()
    welt["db"].expire_all()
    assert load_time_settings(welt["db"]).default_break_minutes == 0  # nicht übernommen
    seite = welt["client"](welt["db"], pages_router.router).get("/settings").text
    assert 'id="defaultBreak"' not in seite and "Standardpause" not in seite


def _alte_standardpause(w, minuten=30):
    load_time_settings(w["db"]).default_break_minutes = minuten
    w["db"].commit()


def test_fuenf_stunden_ohne_pause_ueber_feierabend_nachtrag_und_gruppe(welt):  # noqa: F811
    """Angriff: in der alten Spalte steht 30 -- 5:00 h bekommen über jeden Weg 0 min Pause (Feierabend, Nachtrag, Gruppenbuchung des Büros)."""
    _alte_standardpause(welt)
    gestern, vorgestern = welt["heute"] - timedelta(days=1), welt["heute"] - timedelta(days=2)
    _einsatz(welt, welt["order"], [(welt["heute"] - timedelta(days=7), welt["heute"])], [welt["mia"], welt["tom"]])
    mia = _als(welt, welt["mia"])
    # Feierabend
    row = start_timer(welt["db"], employee_id=welt["mia"].id, order_id=welt["order"].id, started_at=datetime.combine(gestern, time(7)))
    stopp = mia.post(f"/api/time-entries/{row.id}/ende-nachtragen", json={"ende": f"{gestern.isoformat()}T12:00"})
    assert stopp.status_code == 200, stopp.text
    assert (stopp.json()["pause"], Decimal(str(stopp.json()["hours"]))) == (0, Decimal("5"))
    # Nachtrag mit Von/Bis
    nachtrag = mia.post("/api/time-entries", json={"employee_id": welt["mia"].id, "order_id": welt["order"].id,
                                                   "work_date": vorgestern.isoformat(), "von": "07:00", "bis": "12:00"})
    assert nachtrag.status_code == 200, nachtrag.text
    assert (nachtrag.json()["pause"], Decimal(str(nachtrag.json()["hours"]))) == (0, Decimal("5"))
    # Gruppenbuchung des Büros (Dauer)
    buero = welt["client"](welt["db"], time_tracking_router.router, role="admin")
    gruppe = buero.post("/api/time-entry-groups", json={"employee_ids": [welt["mia"].id, welt["tom"].id], "team_id": welt["team"].id,
                                                        "order_id": welt["order"].id, "work_date": welt["heute"].isoformat(), "hours": "5"})
    assert gruppe.status_code == 200, gruppe.text
    welt["db"].expire_all()
    ids = [m.time_entry_id for m in welt["db"].query(TimeEntryGroupMember).filter_by(group_id=gruppe.json()["id"]).all()]
    assert sorted((e.break_minutes, e.hours) for e in welt["db"].query(TimeEntry).filter(TimeEntry.id.in_(ids)).all()) == \
        [(0, Decimal("5")), (0, Decimal("5"))]


def test_buero_seite_belegt_keine_standardpause_vor():
    text, _ = vj.seitentext("time_tracking.html")
    assert "$('manualBreak').value=zahlText(row?.break_minutes??0);" in text and "$('groupBreak').value=zahlText(0);" in text
