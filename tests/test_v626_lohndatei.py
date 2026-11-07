"""Version 1.9.224 (Lohn L1b, Punkt 1): die Lohndatei für DATEV Lohn und Gehalt im Format der Time-4-Muster (app/lohndatei.py).

    Format      ASCII, CRLF auch nach der letzten Zeile, 11 Felder; Kopf Berater;Mandant;MM/JJJJ; Tageszeile Pnr;Tag;Kennzeichen;Lohnart;Stunden;;;;;;
                (ohne Lohnart leer, Tag ohne führende Null); Monatszeile Pnr;;;Lohnart;;;Stunden;;;; zuletzt
    Reihenfolge Personen nach Personalnummer, Tage aufsteigend, im Tag Arbeit, Mehrarbeit, Feiertag, Kalendertag, Abwesenheit, Schlechtwetter
    Inhalt      Zuordnung, Sollzeit, Abwesenheiten, gesetzliche Feiertage, Kalendertage, Ausfalltage, Umfang, Eintritt und Austritt; Mehrarbeit nur
                Azubis (AA / 1900)

Dezember 2026: Tarif 7,50 h (KW 49–53), Fr 25.12. Feiertag, Sa 26.12. Feiertag ohne Sollzeit, Do 24.12. Heiligabend (FR / 1080, 7,00 h), Do 31.12.
Silvester (UU ohne Lohnart). Berater- und Mandantennummer wie in den Mustern erfunden (1234567;12345).
"""

from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
import os
import uuid

import pytest
from sqlalchemy import create_engine, inspect as sa_inspect, text

from app.lohnarten import liste
from app.lohndatei import berechnen
from app.models import EmployeeAbsence, EmployeePayrollSettings, LohnartZuordnung, TimeEntry, TimeTrackingSettings
from app.routers import time_backoffice as backoffice_router
from app.time_backoffice import DatevExportGesperrt, build_datev_export
from tests.test_v224_field_view import make_employee
from tests.test_v325_contract_basis import beauftragen, make_quote
from tests.test_v380_nummern_eindeutig import _alembic, _ok

MIGRATION, VORHER = "c7e2b94a1f60", "a3f61c8d2b95"
PG_URL = os.getenv("ERP_TEST_POSTGRES_URL")

D = Decimal
ERSTER, LETZTER = date(2026, 12, 1), date(2026, 12, 31)


def tag(t: int) -> date:
    return date(2026, 12, t)


@pytest.fixture
def w(threaded_db_session, fester_tag):
    db = threaded_db_session
    order = beauftragen(db, make_quote(db, is_consumer=False, number="0626"))
    s = db.get(TimeTrackingSettings, 1)
    s.datev_beraternummer, s.datev_mandantennummer, s.locked_until = "1234567", "12345", LETZTER
    db.commit()
    return {"db": db, "order": order}


def person(w, nummer, vorname, pnr, *, umfang="alles", azubi=False, eintritt=None, gruppe="gewerblich"):
    e = make_employee(w["db"], nummer, vorname, "Test")
    e.employee_group = gruppe
    w["db"].add(EmployeePayrollSettings(employee_id=e.id, datev_personnel_number=pnr, export_umfang=umfang, payroll_export_enabled=umfang != "nichts",
                                        azubi=azubi, eintritt=eintritt))
    w["db"].commit()
    return e


def buchen(w, e, stunden, t, art="site", ab=7):
    o = w["order"]
    w["db"].add(TimeEntry(employee_id=e.id, project_id=o.project_id, order_id=o.id, work_date=t, entry_type=art, hours=D(stunden), break_minutes=0,
                          status="booked", started_at=datetime.combine(t, time(ab)), ended_at=datetime.combine(t, time(ab + 1))))
    w["db"].commit()


def abwesend(w, e, von, bis=None, kategorie="urlaub", art="Urlaub"):
    w["db"].add(EmployeeAbsence(employee_id=e.id, absence_type=art, absence_category=kategorie, start_date=von, end_date=bis or von))
    w["db"].commit()


def datei(w) -> bytes:
    return build_datev_export(w["db"], ERSTER, LETZTER)[0]


def zeilen(w) -> list[str]:
    roh = datei(w)
    assert roh.endswith(b"\r\n")
    return roh.decode("ascii").split("\r\n")[:-1]


def test_format_kopf_und_reihenfolge(w):
    """Kopf aus den Einstellungen, Personen nach Nummer (nicht nach Anlage), Tage aufsteigend, jede Zeile 11 Felder, ASCII mit CRLF."""
    b = person(w, "M-2", "Ben", "00102")
    a = person(w, "M-1", "Ada", "00101")
    buchen(w, b, "8.00", tag(3))
    buchen(w, a, "7.50", tag(8))
    buchen(w, a, "8.20", tag(7))
    z = zeilen(w)
    assert z[0] == "1234567;12345;12/2026"
    assert z[1:4] == ["00101;7;1;1000;8,25;;;;;;", "00101;8;1;1000;7,50;;;;;;", "00101;24;FR;1080;7,00;;;;;;"]
    assert all(len(x.split(";")) == 11 for x in z[1:])
    assert z.index("00102;3;1;1000;8,00;;;;;;") > z.index("00101;31;UU;;7,50;;;;;;")
    assert b"\n" not in datei(w).replace(b"\r\n", b"")


def test_ein_monat_einer_person(w):
    """Arbeit, Urlaub, Krankheit, Schlechtwetter (Sollzeit − Arbeit), Samstag, Heiligabend mit Arbeit (zwei Zeilen), Feiertag, Feiertag am
    Samstag ohne Zeile, Silvester ohne Lohnart."""
    a = person(w, "M-1", "Ada", "00101")
    buchen(w, a, "8.20", tag(7))
    abwesend(w, a, tag(8), tag(9))
    abwesend(w, a, tag(10), kategorie="krankheit", art="Krankheit")
    abwesend(w, a, tag(11), kategorie="schlechtwetter", art="Schlechtwetter")
    buchen(w, a, "2.10", tag(11))
    buchen(w, a, "4.00", tag(12))
    buchen(w, a, "3.00", tag(24))
    assert zeilen(w) == ["1234567;12345;12/2026",
                         "00101;7;1;1000;8,25;;;;;;", "00101;8;U;8000;7,50;;;;;;", "00101;9;U;8000;7,50;;;;;;", "00101;10;K;1650;7,50;;;;;;",
                         "00101;11;1;1000;2,00;;;;;;", "00101;11;WA;8195;5,50;;;;;;", "00101;12;1;1000;4,00;;;;;;",
                         "00101;24;1;1000;3,00;;;;;;", "00101;24;FR;1080;7,00;;;;;;", "00101;25;F;1012;7,50;;;;;;", "00101;31;UU;;7,50;;;;;;"]


def test_azubi_mehrarbeit(w):
    """Über der Sollzeit Mehrarbeit statt Arbeit; am Berufsschultag zählt die Schule mit (2,00 h nach der Schule ganz Mehrarbeit), am Samstag
    alles; ohne Merkmal bleibt alles Arbeit."""
    b = person(w, "M-2", "Ben", "00291", azubi=True)
    buchen(w, b, "9.00", tag(7))
    abwesend(w, b, tag(8), kategorie="fortbildung", art="Berufsschule")
    buchen(w, b, "2.00", tag(8), ab=16)
    buchen(w, b, "3.00", tag(12))
    buchen(w, b, "7.00", tag(14))
    z = [x for x in zeilen(w)[1:] if not x.startswith(("00291;24;", "00291;25;", "00291;31;"))]
    assert z == ["00291;7;1;1000;7,50;;;;;;", "00291;7;AA;1900;1,50;;;;;;", "00291;8;AA;1900;2,00;;;;;;", "00291;8;FE;;7,50;;;;;;",
                 "00291;12;AA;1900;3,00;;;;;;", "00291;14;1;1000;7,00;;;;;;"]
    w["db"].query(EmployeePayrollSettings).update({"azubi": False})
    w["db"].commit()
    assert [x for x in zeilen(w)[1:] if x.startswith(("00291;7;", "00291;8;", "00291;12;"))] == [
        "00291;7;1;1000;9,00;;;;;;", "00291;8;1;1000;2,00;;;;;;", "00291;8;FE;;7,50;;;;;;", "00291;12;1;1000;3,00;;;;;;"]


def test_mehrarbeit_ohne_kennzeichen_bleibt_arbeit(w):
    b = person(w, "M-2", "Ben", "00291", azubi=True)
    buchen(w, b, "9.00", tag(7))
    z = w["db"].query(LohnartZuordnung).filter_by(schluessel="mehrarbeit_azubi").one()
    z.kennzeichen, z.lohnart = None, None
    w["db"].commit()
    assert "00291;7;1;1000;9,00;;;;;;" in zeilen(w)


def test_umfang_nur_abwesenheiten_und_nichts(w):
    """„nur Abwesenheiten“: Urlaub und Kalendertage, keine Arbeit, kein Feiertag; „nichts“: keine Zeile, auch ohne Personalnummer."""
    c = person(w, "M-3", "Cleo", "00193", umfang="abwesenheiten")
    d = person(w, "M-4", "Dora", None, umfang="nichts")
    buchen(w, c, "8.00", tag(7))
    abwesend(w, c, tag(9))
    buchen(w, d, "8.00", tag(7))
    assert zeilen(w) == ["1234567;12345;12/2026", "00193;9;U;8000;7,50;;;;;;", "00193;24;FR;1080;7,00;;;;;;", "00193;31;UU;;7,50;;;;;;"]


def test_eintritt_und_kaufmaennisch(w):
    """Vor dem Eintritt nichts, auch keine gebuchte Arbeit; kaufmännisch kein Kalendertag, aber der Feiertag."""
    e = person(w, "M-5", "Emil", "00194", eintritt=tag(15))
    f = person(w, "B-1", "Fritz", "00001", gruppe="kaufmännisch")
    buchen(w, e, "8.00", tag(14))
    buchen(w, e, "7.50", tag(15))
    assert zeilen(w) == ["1234567;12345;12/2026", "00001;25;F;1012;7,50;;;;;;",
                         "00194;15;1;1000;7,50;;;;;;", "00194;24;FR;1080;7,00;;;;;;", "00194;25;F;1012;7,50;;;;;;", "00194;31;UU;;7,50;;;;;;"]


def test_silvester_als_urlaubstag_und_halber_tag(w):
    """Ein Urlaub über Silvester mit „ganzer Urlaubstag“ (leer gilt wie der Vorschlag) ersetzt UU durch U; ein halber Urlaubstag halbe Sollzeit."""
    a = person(w, "M-1", "Ada", "00101")
    abwesend(w, a, tag(30), tag(31))
    w["db"].add(EmployeeAbsence(employee_id=a.id, absence_type="Urlaub", absence_category="urlaub", start_date=tag(2), end_date=tag(2), halber_tag=True))
    w["db"].commit()
    z = zeilen(w)
    assert "00101;2;U;8000;3,75;;;;;;" in z and "00101;31;U;8000;7,50;;;;;;" in z and not any(";31;UU;" in x for x in z)


def test_leere_zuordnung_keine_zeile_und_null_stunden(w):
    """Kategorie Unbezahlt ist leer: keine Zeile; Schlechtwetter mit Arbeit über der Sollzeit (Ausfall 0,00): keine Zeile."""
    a = person(w, "M-1", "Ada", "00101")
    abwesend(w, a, tag(2), kategorie="unbezahlt", art="Unbezahlt")
    abwesend(w, a, tag(3), kategorie="schlechtwetter", art="Schlechtwetter")
    buchen(w, a, "8.00", tag(3))
    z = zeilen(w)
    assert not any(x.startswith("00101;2;") for x in z)
    assert [x for x in z if x.startswith("00101;3;")] == ["00101;3;1;1000;8,00;;;;;;"]


def test_monatszeile_zuletzt(w):
    """Eine Zeile der Zuordnung mit Monatszeile (heute keine vorbelegt): je Person eine Zeile Pnr;;;Lohnart;;;Stunden;;;; nach den Tagen."""
    a = person(w, "M-1", "Ada", "00101")
    abwesend(w, a, tag(3), kategorie="schlechtwetter", art="Schlechtwetter")
    abwesend(w, a, tag(4), kategorie="schlechtwetter", art="Schlechtwetter")
    buchen(w, a, "1.00", tag(4))
    z = w["db"].query(LohnartZuordnung).filter_by(schluessel="schlechtwetter:winter").one()
    z.kennzeichen, z.lohnart, z.monatszeile = None, "8110", True
    w["db"].commit()
    assert zeilen(w)[-2:] == ["00101;31;UU;;7,50;;;;;;", "00101;;;8110;;;14,00;;;;"]


def test_nur_ganzer_monat_und_abgeschlossen(w):
    person(w, "M-1", "Ada", "00101")
    with pytest.raises(ValueError):
        build_datev_export(w["db"], tag(1), tag(15))
    w["db"].get(TimeTrackingSettings, 1).locked_until = date(2026, 11, 30)
    w["db"].commit()
    with pytest.raises(DatevExportGesperrt):
        datei(w)


def test_personalnummer_fehlt_kein_stilles_weglassen(w):
    """Bekäme eine Person ohne Personalnummer eine Zeile (hier nur Urlaub), lehnt der Export ab."""
    a = person(w, "M-1", "Ada", None, umfang="abwesenheiten")
    abwesend(w, a, tag(9))
    with pytest.raises(DatevExportGesperrt) as fehler:
        datei(w)
    assert [x["art"] for x in fehler.value.liste] == ["personalnummer"]


def test_schnittstelle(w, router_test_client):
    a = person(w, "M-1", "Ada", "00101")
    buchen(w, a, "8.00", tag(7))
    client = router_test_client(w["db"], backoffice_router.router)
    # seit 1.9.226 erzeugen und ablegen (POST), herunterladen aus der Ablage über datei_antwort() (Regel 31: unbekannter Typ als Download) --
    # 1.9.224/1.9.225 GET /api/time-backoffice/datev-export mit text/plain; charset=us-ascii
    f = client.post("/api/time-backoffice/lohndateien", json={"monat": "2026-12"})
    assert f.status_code == 201
    r = client.get(f"/api/time-backoffice/lohndateien/{f.json()['id']}/datei")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/octet-stream"
    assert 'filename="DATEV_Lohndaten_2026-12.txt"' in r.headers["content-disposition"]
    assert r.content.startswith(b"1234567;12345;12/2026\r\n00101;7;1;1000;8,00;;;;;;\r\n")
    assert client.post("/api/time-backoffice/lohndateien", json={"monat": "2026-12-02"}).status_code == 422


def test_berechnen_ohne_einstellungen_der_alten_formate(w):
    """Zielsystem und Lohnarten je Zeitart lesen nichts mehr (E8): ein gesetztes LODAS ändert die Datei nicht."""
    a = person(w, "M-1", "Ada", "00101")
    buchen(w, a, "8.00", tag(7))
    vorher = datei(w)
    s = w["db"].get(TimeTrackingSettings, 1)
    s.datev_target, s.datev_wage_type_site = "lodas", None
    w["db"].commit()
    assert datei(w) == vorher
    assert [p.personalnummer for p in berechnen(w["db"], ERSTER)] == ["00101"]


# --- Merkmal „Azubi“ an den Lohnstammdaten, Zeile „Mehrarbeit Azubis“ der Zuordnung -------------------------------------------------------

def test_azubi_in_den_lohnstammdaten(w, router_test_client):
    """Ein Teil-Update: nur gesendet ändert es sich; die Liste nennt es; vorbelegt nein."""
    a = person(w, "M-1", "Ada", "00101")
    client = router_test_client(w["db"], backoffice_router.router)
    assert client.get("/api/time-backoffice/payroll-employees").json()[0]["azubi"] is False
    r = client.put(f"/api/time-backoffice/payroll-employees/{a.id}", json={"azubi": True})
    assert (r.status_code, r.json()["azubi"], r.json()["datev_personnel_number"]) == (200, True, "00101")
    assert client.put(f"/api/time-backoffice/payroll-employees/{a.id}", json={"eintritt": "2026-01-01"}).json()["azubi"] is True
    assert client.put(f"/api/time-backoffice/payroll-employees/{a.id}", json={"azubi": None}).status_code == 422


def test_zuordnung_mehrarbeit_vorbelegt(w):
    z = next(x for x in liste(w["db"]) if x["schluessel"] == "mehrarbeit_azubi")
    assert (z["kennzeichen"], z["lohnart"], z["wirkt"], z["stunden"]) == ("AA", "1900", "AA / 1900 – exportiert mit Lohnart", "Arbeit über der Sollzeit")


def test_seite_azubi_und_ohne_alte_lohnarten():
    text = (Path(__file__).resolve().parent.parent / "app" / "templates" / "settings.html").read_text(encoding="utf-8")
    assert "azubi:document.getElementById('pazubi-'+id).checked" in text and "<th>Azubi</th>" in text
    assert 'id="datevTarget"' not in text and 'id="wageSite"' not in text and "'datevTarget'" not in text and ">Lohnarten des bisherigen" not in text


# --- Migration c7e2b94a1f60 ------------------------------------------------------------------------------------------------------------------

def _probe(url: str, engine) -> None:
    _ok(_alembic(url, "upgrade", VORHER))
    with engine.begin() as c:
        c.execute(text("INSERT INTO employees (employee_number, first_name, last_name, employee_group, weekly_hours, active, created_at, updated_at) "
                       "VALUES ('M-1', 'Mia', 'Test', 'gewerblich', 40, :a, '2026-09-01', '2026-09-01')"), {"a": True})
        mia = c.execute(text("SELECT id FROM employees")).scalar()
        c.execute(text("INSERT INTO employee_payroll_settings (employee_id, datev_personnel_number, payroll_export_enabled, export_umfang, updated_at) "
                       "VALUES (:e, '00291', :a, 'alles', '2026-11-02')"), {"e": mia, "a": True})
    _ok(_alembic(url, "upgrade", MIGRATION))
    with engine.begin() as c:
        assert c.execute(text("SELECT datev_personnel_number, azubi FROM employee_payroll_settings")).one() == ("00291", False)
        c.execute(text("UPDATE employee_payroll_settings SET azubi = :a"), {"a": True})
    _ok(_alembic(url, "downgrade", VORHER))
    assert "azubi" not in {s["name"] for s in sa_inspect(engine).get_columns("employee_payroll_settings")}
    with engine.connect() as c:
        assert c.execute(text("SELECT datev_personnel_number FROM employee_payroll_settings")).scalar() == "00291"
    _ok(_alembic(url, "upgrade", "head"))


def test_migration_auf_einem_bestand_sqlite(tmp_path):
    url = f"sqlite:///{(tmp_path / 'azubi.db').as_posix()}"
    engine = create_engine(url)
    try:
        _probe(url, engine)
    finally:
        engine.dispose()


def test_migration_auf_einem_bestand_postgresql():
    if not PG_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    schema = f"pgtest_mig_azubi_{uuid.uuid4().hex[:8]}"
    admin = create_engine(PG_URL)
    with admin.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
    url = f"{PG_URL}{'&' if '?' in PG_URL else '?'}options=-csearch_path={schema}"  # ohne Prozentkodierung (configparser)
    engine = create_engine(PG_URL, connect_args={"options": f"-csearch_path={schema}", "application_name": schema})
    try:
        _probe(url, engine)
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE application_name = :n"), {"n": schema})
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin.dispose()


def test_feiertag_geht_dem_kalendertag_vor(w):
    """Ein Tag des Arbeitszeitkalenders auf einem gesetzlichen Feiertag: nur die Zeile F."""
    from app.arbeitszeitkalender import anlegen as kalendertag_anlegen
    from app.lohnarten import speichern
    a = person(w, "M-1", "Ada", "00101")
    k = kalendertag_anlegen(w["db"], {"name": "Testtag", "monat": 12, "tag": 25, "sollzeit": None, "abwesenheit": "Testtag – frei", "bezahlt": True,
                                      "im_urlaub": "kein_urlaubstag", "nur_gewerblich": True, "nur_mo_fr": True, "aktiv": True})
    speichern(w["db"], f"kalender:{k.schluessel}", "XX", "1111", False)
    assert [x for x in zeilen(w) if x.startswith("00101;25;")] == ["00101;25;F;1012;7,50;;;;;;"]
    assert a.id


def test_mehrarbeit_hoechstens_die_arbeit(w):
    """Mehr übrige Stunden als Sollzeit (zwei Abwesenheiten am selben Tag, direkt eingetragen): Mehrarbeit höchstens die gebuchte Arbeit."""
    b = person(w, "M-2", "Ben", "00291", azubi=True)
    abwesend(w, b, tag(7))
    abwesend(w, b, tag(7), kategorie="krankheit", art="Krankheit")
    buchen(w, b, "1.00", tag(7))
    assert [x for x in zeilen(w) if x.startswith("00291;7;")] == ["00291;7;AA;1900;1,00;;;;;;", "00291;7;U;8000;7,50;;;;;;",
                                                                  "00291;7;K;1650;7,50;;;;;;"]


def test_einstellungen_ohne_alte_felder(w, router_test_client):
    client = router_test_client(w["db"], backoffice_router.router)
    s = client.get("/api/time-backoffice/settings").json()
    assert not {"datev_target", "datev_wage_type_site", "datev_wage_type_weather_winter"} & set(s)
    assert client.put("/api/time-backoffice/settings", json={**s, "require_activity": True, "datev_target": "lodas"}).status_code == 200  # seit 1.9.231 ohne Rundung
    assert w["db"].get(TimeTrackingSettings, 1).datev_target == "lohn_gehalt"  # nichts liest oder schreibt es mehr
