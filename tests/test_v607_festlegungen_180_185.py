"""Seit 1.9.200: Gegenproben zu den Festlegungen 1.9.180–1.9.185 (Regel 24) -- die Tests, die dabei fehlten.

    1.9.180 Nr. 2  ein halber Urlaubstag an einem Kalendertag ohne Sollzeit wird angenommen und zählt 0
    1.9.181 Nr. 1  ohne „DATEV-Nr. = ERP-Nr.“ trägt eine Mitarbeiternummer keine Personalnummer -- freigeben geht
    1.9.181 Nr. 2  der Eintrag im Änderungsprotokoll nennt, wer frei gab und wann
    1.9.181 Nr. 3  der Dialog fragt keine Begründung ab; die Warnung nennt beide Fälle (nie abgerechnet, Tippfehler)
    1.9.183 Nr. 3  nachgestellt werden alle Arbeitsprozesse zugleich, je einer mit genau seinen Dateien in seiner Reihenfolge
    1.9.184 Nr. 1  das Prüfskript zählt auch abgelehnte Anträge, je Status genannt
    1.9.184 Nr. 2  gezählt wird nur, wo heute gefragt würde -- nicht ohne Sollzeit am Wochentag, nicht am Sonntag mit Sollzeit
    1.9.185 Nr. 1  ohne ERP_KLICKTEST_ORDNER liegt der Ordner unter %TEMP%\\erp-klicktests
    1.9.185 Nr. 2  ein tieferer Ordner außerhalb von %TEMP% bleibt erlaubt
    1.9.185 Nr. 3  kein Werkzeug löscht seinen Ordner nach dem Lauf

Feste Tage: Heiligabend Mo 24.12.2029, Silvester Do 31.12.2026, Fr 31.12.2027, So 31.12.2028, Mo 31.12.2029.
"""

import ast
import importlib.util
import re
import subprocess
import tempfile
import types
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select

from app.audit import reset_audit_context, set_audit_context
from app.auth import hash_password
from app.models import AppUser, AuditLog, Employee, EmployeeAbsenceRequest, TimeBackofficeAdvancedSettings
from app.routers import absence_requests as absence_router
from app.sollzeit import abwesenheit_tage, zeile_anlegen
from app.time_backoffice import personalnummer_freigeben
from tests import reihenfolge
from tests.test_v224_field_view import make_employee
from tests.test_v590_pruefe_zeitregeln import _skript
from tests.test_v593_personalnummer_gesperrt import _client, _gemerkt, _put

D = Decimal
ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
FREIGEBEN = "/api/time-backoffice/personalnummern/freigeben"
TEILZEIT = {"dienstag": D("3"), "mittwoch": D("3"), "donnerstag": D("3")}
ZEILE_184 = "Urlaubsanträge über 31.12. ohne Antwort (vor 1.9.176 angelegt, zählen als ganzer Urlaubstag): "


@pytest.fixture
def welt(threaded_db_session, router_test_client, fester_tag):
    db = threaded_db_session
    mia, tom = make_employee(db, "M-1", "Mia", "Monteurin"), make_employee(db, "M-2", "Tom", "Monteur")
    kim = Employee(employee_number="K-1", first_name="Kim", last_name="Kauffrau", employee_group="kaufmaennisch", active=True)
    db.add(kim)
    db.commit()
    return {"db": db, "mia": mia, "tom": tom, "kim": kim, "client": router_test_client}


# --- 1.9.180 ---------------------------------------------------------------------------------------------------------------------------------

def test_halber_urlaubstag_an_einem_kalendertag_ohne_sollzeit(welt):
    """Seit 1.9.200 (Gegenprobe zu Festlegung 1.9.180 Nr. 2): Tom Di–Do 3,00 h hat am Mo 24.12.2029 keine Sollzeit -- dort gilt kein
    Heiligabend, ein halber Urlaubstag wird angenommen (nicht „gilt Heiligabend …“, 422) und zählt 0 Tage und 0 Stunden, wie an jedem anderen
    Tag ohne Sollzeit."""
    db, tom = welt["db"], welt["tom"]
    zeile_anlegen(db, tom.id, date(2026, 12, 1), TEILZEIT)
    client = welt["client"](db, absence_router.router, role="admin", user_id=9)
    r = client.post("/api/absence-requests", json={"employee_id": tom.id, "absence_category": "urlaub", "start_date": "2029-12-24",
                                                   "end_date": "2029-12-24", "halber_tag": True})
    assert r.status_code == 200, r.text
    db.expire_all()
    assert db.scalars(select(EmployeeAbsenceRequest.halber_tag).where(EmployeeAbsenceRequest.employee_id == tom.id)).all() == [True]
    t = abwesenheit_tage(db, tom.id, date(2029, 12, 24), date(2029, 12, 24), kategorie="urlaub", halber_tag=True)
    assert (t["tage"], t["stunden"], t["je_tag"]) == (D("0"), D("0"), [])


# --- 1.9.181 ---------------------------------------------------------------------------------------------------------------------------------

def _wechsel(w):
    """Mia 91008 -> 91016: 91008 ist ihr gemerkt (wie tests/test_v595_personalnummer_freigeben.py)."""
    assert _put(w, w["mia"], datev_personnel_number="91008").status_code == 200
    assert _put(w, w["mia"], datev_personnel_number="91016").status_code == 200


def test_ohne_gleichsetzung_traegt_eine_mitarbeiternummer_keine_personalnummer(welt):
    """Seit 1.9.200 (Gegenprobe zu Festlegung 1.9.181 Nr. 1): „niemand trägt sie“ heißt keine Lohnstammdaten mit der Nummer und NUR bei
    „DATEV-Nr. = ERP-Nr.“ keine Mitarbeiternummer -- ohne Gleichsetzung hält Toms Mitarbeiternummer 91008 die Nummer nicht, freigeben geht."""
    db, mia, tom = welt["db"], welt["mia"], welt["tom"]
    _wechsel(welt)
    assert not db.get(TimeBackofficeAdvancedSettings, 1).datev_personnel_equals_erp_number
    tom.employee_number = "91008"
    db.commit()
    r = _client(welt, "admin").post(FREIGEBEN, json={"nummer": "91008"})
    assert r.status_code == 200, r.text
    assert _gemerkt(welt) == [("91016", mia.id)]


def test_die_freigabe_nennt_wer_und_wann(welt):
    """Seit 1.9.200 (Gegenprobe zu Festlegung 1.9.181 Nr. 2): der Eintrag im Änderungsprotokoll nennt das Konto, das frei gab (aus der
    Anfrage, wie jeder Eintrag), und den Zeitpunkt."""
    db = welt["db"]
    _wechsel(welt)
    konto = AppUser(username="anna", display_name="Admin Anna", role="admin", active=True, password_hash=hash_password("Passwort123"))
    db.add(konto)
    db.commit()
    marken = set_audit_context(konto)
    try:
        personalnummer_freigeben(db, "91008")
    finally:
        reset_audit_context(marken)
    eintrag = db.scalars(select(AuditLog).where(AuditLog.action == "Personalnummer freigegeben")).one()
    assert (eintrag.actor_user_id, eintrag.actor_name, eintrag.entity_id) == (konto.id, "Admin Anna", "91008")
    assert eintrag.occurred_at is not None


def test_dialog_ohne_begruendung_die_warnung_nennt_den_fall():
    """Seit 1.9.200 (Gegenprobe zu Festlegung 1.9.181 Nr. 3): im Dialog „Personalnummer freigeben“ kein Eingabefeld (keine Begründung), gesendet
    wird nur die Nummer; die Warnung nennt den Fall, für den es gedacht ist -- nie abgerechnet und Tippfehler (bis 1.9.198 prüfte die Suite nur
    den ersten, den vollen Text nur klicktest_personalnummer_freigeben)."""
    from tests import vorlagen_js as vj
    html = (vj.TEMPLATES / "settings.html").read_text(encoding="utf-8")
    dialog = html[html.index('<dialog id="pnrFreigabeDialog"'):]
    dialog = dialog[:dialog.index("</dialog>")]
    assert not re.search(r"<(textarea|input|select)\b", dialog), dialog
    oeffnen = html[html.index("function pnrFreigabeOeffnen("):]
    oeffnen = oeffnen[:oeffnen.index("\n")]
    assert "gib sie nur frei, wenn sie nie abgerechnet wurde (z. B. nach einem Tippfehler)." in oeffnen
    senden = html[html.index("async function pnrFreigeben("):]
    senden = senden[:senden.index("\n")]
    assert "body:JSON.stringify({nummer})" in senden


# --- 1.9.183 ---------------------------------------------------------------------------------------------------------------------------------

def test_nachstellen_startet_alle_zugleich_je_mit_seinen_dateien(tmp_path, monkeypatch, capsys):
    """Seit 1.9.200 (Gegenprobe zu Festlegung 1.9.183 Nr. 3): ohne --arbeitsprozess startet tests.reihenfolge alle Prozesse, bevor es auf den
    ersten wartet (die Last der übrigen kommt nur so mit), je einer mit genau seinen Dateien in seiner Reihenfolge und eigenem Ordner."""
    (tmp_path / "gw0.txt").write_text("10:00:00.000\tpassed\ttests/test_b.py::test_1\n10:00:01.000\tpassed\ttests/test_a.py::test_1\n"
                                      "10:00:02.000\tpassed\ttests/test_b.py::test_2\n", encoding="utf-8")
    (tmp_path / "gw1.txt").write_text("10:00:00.500\tfailed\ttests/test_c.py::test_1\n", encoding="utf-8")
    ereignisse = []

    class Prozess:
        def __init__(self, befehl, cwd, env, stdout, stderr):
            self.name = Path(env["ERP_TEST_REIHENFOLGE"]).name
            ereignisse.append(("start", self.name, befehl[befehl.index("no:cacheprovider") + 1:]))

        def wait(self):
            ereignisse.append(("warten", self.name, None))
            return 0

    monkeypatch.setattr(reihenfolge, "subprocess", types.SimpleNamespace(Popen=Prozess, STDOUT=subprocess.STDOUT))
    assert reihenfolge.main([str(tmp_path)]) == 0
    capsys.readouterr()
    assert [e[0] for e in ereignisse] == ["start", "start", "warten", "warten"], ereignisse
    assert {e[1]: e[2] for e in ereignisse if e[0] == "start"} == {"gw0": ["tests/test_b.py", "tests/test_a.py"], "gw1": ["tests/test_c.py"]}


# --- 1.9.184 ---------------------------------------------------------------------------------------------------------------------------------

def _antrag(db, emp, von, bis, status="approved"):
    db.add(EmployeeAbsenceRequest(employee_id=emp.id, absence_type="Urlaub", absence_category="urlaub", start_date=von, end_date=bis,
                                  status=status, kalendertag_urlaub=None))


def test_pruefskript_zaehlt_auch_abgelehnte(welt):
    """Seit 1.9.200 (Gegenprobe zu Festlegung 1.9.184 Nr. 1): gezählt werden alle Status, auch abgelehnte, je für sich genannt (bis 1.9.198
    hatte der Test keinen abgelehnten Antrag)."""
    db, mia, tom = welt["db"], welt["mia"], welt["tom"]
    _antrag(db, mia, date(2026, 12, 28), date(2027, 1, 8))
    _antrag(db, tom, date(2026, 12, 28), date(2027, 1, 8), status="pending")
    _antrag(db, mia, date(2027, 12, 27), date(2028, 1, 7), status="rejected")  # Fr 31.12.2027
    _antrag(db, tom, date(2029, 12, 27), date(2030, 1, 4), status="cancelled")
    db.commit()
    stand = _skript().pruefen(db, date(2026, 11, 10))
    assert ZEILE_184 + "4 (genehmigt 1, offen 1, abgelehnt 1, zurückgezogen 1)" in stand.zeilen


def test_pruefskript_nur_wo_heute_gefragt_wuerde(welt):
    """Seit 1.9.200 (Gegenprobe zu Festlegung 1.9.184 Nr. 2): nicht gezählt, wo heute nicht gefragt würde -- Tom (Di–Do 3,00 h) hat am
    Mo 31.12.2029 keine Sollzeit; Ole hat eigene Werte auch am Sonntag, am So 31.12.2028 fragt Silvester trotzdem nicht (nur Mo–Fr).
    Bis 1.9.198 schloss der Sonntag im Test schon die Sollzeit aus, und eine Person ohne Sollzeit am Wochentag gab es nicht."""
    db, mia, tom = welt["db"], welt["mia"], welt["tom"]
    ole = make_employee(db, "M-3", "Ole", "Sonntag")
    zeile_anlegen(db, tom.id, date(2026, 12, 1), TEILZEIT)
    zeile_anlegen(db, ole.id, date(2026, 12, 1), {w: D("8") for w in ("montag", "dienstag", "mittwoch", "donnerstag", "freitag", "samstag",
                                                                      "sonntag")})
    _antrag(db, mia, date(2026, 12, 28), date(2027, 1, 8))  # gezählt
    _antrag(db, tom, date(2029, 12, 27), date(2030, 1, 4))  # Mo 31.12.2029 ohne Sollzeit
    _antrag(db, ole, date(2028, 12, 27), date(2029, 1, 5))  # So 31.12.2028 mit Sollzeit
    db.commit()
    stand = _skript().pruefen(db, date(2026, 11, 10))
    assert ZEILE_184 + "1 (genehmigt 1)" in stand.zeilen


# --- 1.9.185 ---------------------------------------------------------------------------------------------------------------------------------

def _werkzeug(monkeypatch, wurzel: Path | None):
    if wurzel is None:
        monkeypatch.delenv("ERP_KLICKTEST_ORDNER", raising=False)
    else:
        monkeypatch.setenv("ERP_KLICKTEST_ORDNER", str(wurzel))
    spec = importlib.util.spec_from_file_location("cdp_klicktest_v607", SCRIPTS / "cdp_klicktest.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def test_ohne_umgebung_unter_temp_erp_klicktests(monkeypatch):
    """Seit 1.9.200 (Gegenprobe zu Festlegung 1.9.185 Nr. 1): ohne ERP_KLICKTEST_ORDNER ist der Ordner %TEMP%\\erp-klicktests, ein Name ohne
    Pfad landet dort (die übrigen Tests setzen die Umgebung immer). Es entsteht nichts."""
    k = _werkzeug(monkeypatch, None)
    temp = Path(tempfile.gettempdir())
    assert k.KLICKTEST_ORDNER == temp / "erp-klicktests"
    assert k.klicktest_ordner(Path("end_607_gibt_es_nicht"), "lauf-") == (temp / "erp-klicktests" / "end_607_gibt_es_nicht").resolve()
    assert not (temp / "erp-klicktests" / "end_607_gibt_es_nicht").exists()


def test_ein_tieferer_ordner_ausserhalb_von_temp_bleibt(tmp_path, monkeypatch):
    """Seit 1.9.200 (Gegenprobe zu Festlegung 1.9.185 Nr. 2): jeder tiefere Ordner bleibt erlaubt, auch außerhalb von %TEMP% (der Pfad im
    Test von 1.9.185 lag unter tmp_path, also unter %TEMP%). klicktest_ordner() legt für einen vollen Pfad nichts an."""
    k = _werkzeug(monkeypatch, tmp_path / "erp-klicktests")
    temp = str(Path(tempfile.gettempdir()).resolve()).lower()
    ausserhalb = Path(Path(tempfile.gettempdir()).anchor) / "erp_v607_gibt_es_nicht" / "lauf"
    assert not str(ausserhalb.resolve()).lower().startswith(temp) and not ausserhalb.parent.exists()
    assert k.klicktest_ordner(ausserhalb, "lauf-") == ausserhalb.resolve()
    assert not ausserhalb.parent.exists()


def test_kein_werkzeug_loescht_seinen_ordner():
    """Seit 1.9.200 (Gegenprobe zu Festlegung 1.9.185 Nr. 3): die Ordner bleiben nach dem Lauf liegen, aufgeräumt wird von Hand -- weder
    cdp_klicktest.py noch klicktest_alle.py löscht einen Ordner oder eine Datei (kein rmtree, rmdir, unlink, removedirs, os.remove)."""
    verboten = {"rmtree", "rmdir", "unlink", "removedirs"}
    for name in ("cdp_klicktest.py", "klicktest_alle.py"):
        funde = []
        for knoten in ast.walk(ast.parse((SCRIPTS / name).read_text(encoding="utf-8"))):
            if isinstance(knoten, ast.Attribute) and (knoten.attr in verboten or (
                    knoten.attr == "remove" and isinstance(knoten.value, ast.Name) and knoten.value.id == "os")):
                funde.append(f"{name}:{knoten.lineno} {knoten.attr}")
            if isinstance(knoten, ast.ImportFrom) and knoten.module in ("shutil", "os") and {a.name for a in knoten.names} & (verboten | {"remove"}):
                funde.append(f"{name}:{knoten.lineno} import")
        assert not funde, funde
