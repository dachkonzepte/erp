"""Version 1.8.36 -- Tests und Klicktests unabhängig von der Tageszeit.

Ab MobileSettings.shift_end_time (Vorgabe 19:00) meldet GET /api/field-view/today den Monteur ab.
test_v321 und test_v326 riefen den Endpunkt als Monteur auf und waren abends rot, Klicktests mit
Monteur auf /mobil ebenso (1.8.35, Nebenbefund 3). Jetzt hält eine feste Uhr (tests/uhr.py,
Fixture feste_uhr; im Klicktest klicktest_main(..., uhr="10:00")) die Zeit auf heute 10:00.

Gegenprobe für die ganze Suite: `pytest --wanduhr 19:30` (tests/conftest.py) -- als liefe sie um
19:30.
"""

import importlib.util
import re
from datetime import time
from pathlib import Path

from app import berlin_time
from app.models import Employee
from tests.uhr import uhr_festhalten

ROOT = Path(__file__).resolve().parent.parent


def _cdp_klicktest():
    pfad = ROOT / "scripts" / "cdp_klicktest.py"
    spec = importlib.util.spec_from_file_location("cdp_klicktest_test_v339", pfad)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def test_feste_uhr_laeuft_heute_ab_zehn(feste_uhr):
    jetzt = berlin_time.berlin_now()
    assert time(10, 0) <= jetzt.time() < time(10, 5)
    assert feste_uhr.tzinfo is not None


def test_gegenprobe_abends_meldet_today_ab_mit_fester_uhr_nicht(threaded_db_session, router_test_client):
    """Abends (vorgetäuscht 19:30) antwortet /api/field-view/today dem Monteur 401 "Feierabend" --
    mit fester Uhr darüber 200. Ohne Uhr wäre das Ergebnis die echte Tageszeit."""
    from app.routers.field_view import router as field_view_router

    db = threaded_db_session
    monteur = Employee(first_name="Max", last_name="Monteur")
    db.add(monteur); db.commit()
    client = router_test_client(db, field_view_router, role="field", employee_id=monteur.id)
    with uhr_festhalten(time(19, 30)):
        abends = client.get("/api/field-view/today")
        with uhr_festhalten():
            fest = client.get("/api/field-view/today")
        wieder_abends = client.get("/api/field-view/today")
    assert abends.status_code == 401 and "Feierabend" in abends.text
    assert fest.status_code == 200, fest.text
    assert wieder_abends.status_code == 401


def test_feste_uhr_nimmt_das_datum_der_vorherigen_uhr():
    with uhr_festhalten(time(23, 50)) as spaet:
        with uhr_festhalten() as fest:
            assert fest.astimezone(berlin_time.BERLIN).date() == spaet.astimezone(berlin_time.BERLIN).date()
            assert berlin_time.berlin_now().time() < time(10, 5)


def test_klicktest_uhr_marke_setzt_die_uhr_der_app(monkeypatch):
    """Was der Befüllen-Prozess und der Server einer Instanz mit uhr="10:00" tun: die Marke aus der
    Umgebung lesen und app.berlin_time._utc_now ersetzen."""
    werkzeug = _cdp_klicktest()
    monkeypatch.setattr(berlin_time, "_utc_now", berlin_time._utc_now)  # nach dem Test zurück
    monkeypatch.setenv(werkzeug.UHR_ENV, werkzeug._uhr_marke("10:00"))
    werkzeug._uhr_einsetzen()
    jetzt = berlin_time.berlin_now()
    assert time(10, 0) <= jetzt.time() < time(10, 5)


def test_klicktest_ohne_uhr_laesst_die_echte_uhr(monkeypatch):
    werkzeug = _cdp_klicktest()
    echte = berlin_time._utc_now
    monkeypatch.delenv(werkzeug.UHR_ENV, raising=False)
    werkzeug._uhr_einsetzen()
    assert berlin_time._utc_now is echte


def test_klicktests_mit_monteur_auf_mobil_halten_die_uhr_fest():
    """Ein Klicktest, der /mobil öffnet, braucht klicktest_main(..., uhr=...) -- und setzt die
    Feierabend-Grenze nicht mehr im Bestand hoch (das war 1.8.34/1.8.35 der Notbehelf)."""
    ohne_uhr, mit_grenze = [], []
    for skript in sorted((ROOT / "scripts").glob("klicktest_*.py")):
        text = skript.read_text(encoding="utf-8")
        if re.search(r"oeffnen\(\s*f?[\"']/mobil[\"'?]", text) and not re.search(r"klicktest_main\(.*\buhr=\"", text):
            ohne_uhr.append(skript.name)
        if "update_mobile_settings" in text:
            mit_grenze.append(skript.name)
    assert ohne_uhr == []
    assert mit_grenze == []
