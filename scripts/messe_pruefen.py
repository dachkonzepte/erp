"""Messung: wie lange GET /api/zeiten/pruefen mit vielen gesendeten Lohndateien braucht (seit 1.9.332, Lohn L2c-3, Punkt 0).

„Prüfen“ rechnet seit 1.9.331 für jeden Monat mit gesendeter Lohndatei im Fenster (app/lohndatei_abgleich.py::MONATE_ZURUECK) die Liste „Nach dem
Versand geändert“ -- je Monat eine volle Rechnung der Lohndatei. Dieses Skript baut einen Testbestand und misst den Aufruf über die echte Anmeldeschranke.

Testbestand (nur erfunden, Wegwerf-Datenbank -- nie die echte, Regel 16): 15 gewerbliche Personen (Personalnummern aus dem erfundenen Kreis), je Arbeitstag
von Januar bis Dezember 2027 eine Buchung von 8,00 h, je Person und Monat ein Urlaubstag (genehmigt); je Monat die Lohndatei erzeugt und als gesendet
vermerkt, danach je Monat zwei geänderte Buchungen (von Anna Admin, in der Änderungshistorie). „Abgeschlossen bis“ 31.12.2027. Seit 1.9.336 mit Grenzen des
Arbeitszeitkontos (Plus 40, Minus 20 h) -- „Prüfen“ rechnet dann auch das Konto über das ganze Jahr.

Zwei Tage:
    31.12.2027  alle zwölf gesendeten Monate liegen im Fenster (der Dezember am letzten Tag gesendet -- der ungünstigste Fall)
    17.01.2028  das Fenster reicht von Februar 2027 bis heute: elf gesendete Monate (der laufende Monat ist nie gesendet)
Je Tag und Fenster (12 und 3 Monate): ein Aufruf zum Aufwärmen, dann --aufrufe Aufrufe als Admin; Median und größter Wert. Dazu einzeln
aenderungen_je_monat() -- der Teil, den das Fenster bestimmt.

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\messe_pruefen.py [--aufrufe 5] [--pg URL]

--pg: zusätzlich gegen PostgreSQL (z. B. die lokale Spielwiese aus ERP_TEST_POSTGRES_URL) -- in einem Wegwerf-Schema, nie in public (Regel 27);
das Schema wird am Ende gelöscht. Ohne --pg nur SQLite (eine Datei im Temp-Ordner). Gemessen wird auf diesem Rechner; der Server (2 Kerne) ist langsamer.
"""

from __future__ import annotations

import argparse
import os
import shutil
import statistics
import sys
import tempfile
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

WURZEL = Path(__file__).resolve().parent.parent
NUMMERN = ["00090", "00091", "00092", "00093", "00094", "00095", "00096", "00097", "00098", "00099", "00190", "00191", "00192", "00193", "00194"]
TAGE = (date(2027, 12, 31), date(2028, 1, 17))


def _uhr(tag: date):
    import app.berlin_time as bt
    bt._utc_now = lambda: datetime(tag.year, tag.month, tag.day, 9, 0, tzinfo=timezone.utc)


def befuellen(db) -> int:
    """Der Testbestand; gibt die ID des Admin-Kontos zurück."""
    from app.absence_requests import eintragen
    from app.audit import reset_audit_context, set_audit_context
    from app.grunddaten import anlegen
    from app.lohndatei import monat_ende, versendet_setzen
    from app.models import AppUser, Customer, Employee, EmployeePayrollSettings, LohnStartwert, Order, Project, Property, Quote, TimeEntry, TimeTrackingSettings
    from app.project_pipeline_columns import default_pipeline_column_id
    from app.time_backoffice import lohndatei_erzeugen

    anlegen(db)
    db.commit()
    kunde = Customer(name="Messung", last_name="Messung", is_consumer=False)
    db.add(kunde); db.flush()
    objekt = Property(customer_id=kunde.id, name="Messung", street="-", postal_code="00000", city="-")
    db.add(objekt); db.flush()
    projekt = Project(project_number="P-MESSUNG", name="Messung", customer_id=kunde.id, property_id=objekt.id,
                      pipeline_column_id=default_pipeline_column_id(db))
    db.add(projekt); db.flush()
    angebot = Quote(project_id=projekt.id, quote_number="A-MESSUNG", title="Messung")  # PostgreSQL prüft den Fremdschlüssel des Auftrags
    db.add(angebot); db.flush()
    auftrag = Order(order_number="AUF-MESSUNG", project_id=projekt.id, source_quote_id=angebot.id, quote_number_snapshot="A-MESSUNG", title="Messung",
                    customer_name="Messung", status="laeuft")
    db.add(auftrag)
    anna = AppUser(username="anna", display_name="Anna Admin", role="admin", password_hash="-")
    db.add(anna)
    s = db.get(TimeTrackingSettings, 1)
    s.datev_beraternummer, s.datev_mandantennummer, s.locked_until = "1234567", "12345", date(2027, 12, 31)
    # seit 1.9.336: mit Grenzen rechnet „Prüfen“ auch das Konto aller gewerblichen Personen über das ganze Jahr (app/arbeitszeitkonto.py::grenzen_hinweise())
    s.konto_hinweis_plus, s.konto_hinweis_minus = Decimal("40"), Decimal("20")
    db.commit()
    personen = []
    for i, nummer in enumerate(NUMMERN):
        e = Employee(employee_number=f"M-{i + 1}", first_name="Person", last_name=f"Messung {i + 1:02d}", employee_group="gewerblich", active=True,
                     hourly_wage=Decimal("20"), weekly_hours=Decimal("40"))
        db.add(e); db.flush()
        db.add(EmployeePayrollSettings(employee_id=e.id, datev_personnel_number=nummer, export_umfang="alles", payroll_export_enabled=True))
        db.add(LohnStartwert(employee_id=e.id, stichtag=date(2026, 12, 31), resturlaub_tage=Decimal("5"), saldo_stunden=Decimal("12.5")))
        personen.append(e.id)
    db.commit()
    for m in range(1, 13):
        erster = date(2027, m, 1)
        urlaub = next(t for t in (erster + timedelta(days=d) for d in range(7, 14)) if t.weekday() == 2)  # der zweite Mittwoch
        for eid in personen:
            eintragen(db, gleich_genehmigt=True, abschluss_erlaubt=True, employee_id=eid, absence_category="urlaub", absence_type="Urlaub",
                      start_date=urlaub, end_date=urlaub)
            t = erster
            while t <= monat_ende(erster):
                if t.weekday() < 5 and t != urlaub:
                    db.add(TimeEntry(employee_id=eid, project_id=projekt.id, order_id=auftrag.id, work_date=t, entry_type="site", hours=Decimal("8"),
                                     break_minutes=0, status="booked", started_at=datetime(t.year, t.month, t.day, 7),
                                     ended_at=datetime(t.year, t.month, t.day, 15)))
                t += timedelta(days=1)
        db.commit()
    for m in range(1, 13):
        row = lohndatei_erzeugen(db, date(2027, m, 1), user_id=anna.id, user_name="Anna Admin")
        versendet_setzen(db, row.id, user_id=anna.id, user_name="Anna Admin")
    token = set_audit_context(SimpleNamespace(id=anna.id, display_name="Anna Admin"), None)
    try:
        for m in range(1, 13):
            for eid in personen[:2]:
                e = (db.query(TimeEntry).filter(TimeEntry.employee_id == eid, TimeEntry.work_date >= date(2027, m, 1),
                                                TimeEntry.work_date <= monat_ende(date(2027, m, 1))).order_by(TimeEntry.work_date).first())
                e.hours = Decimal("6")
        db.commit()
    finally:
        reset_audit_context(token)
    return anna.id


def messen(make_session, admin_id: int, aufrufe: int) -> list[dict]:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    import app.lohndatei_abgleich as abgleich
    from app.anmeldeschranke import einbinden
    from app.auth import COOKIE_NAME
    from app.database import get_db
    from app.models import AppUser
    from app.routers import zeiten as zeiten_router
    from app.sitzungen import neue_sitzung

    anwendung = FastAPI()
    anwendung.include_router(zeiten_router.router)

    def _db():
        db = make_session()
        try:
            yield db
        finally:
            db.close()

    anwendung.dependency_overrides[get_db] = _db
    einbinden(anwendung, make_session)
    ergebnisse = []
    vorher = abgleich.MONATE_ZURUECK
    try:
        for tag in TAGE:
            _uhr(tag)
            db = make_session()
            wert = neue_sitzung(db, db.get(AppUser, admin_id), zweiter_faktor=True)
            db.commit()
            db.close()
            client = TestClient(anwendung, headers={"origin": "http://testserver", "sec-fetch-site": "same-origin"})
            client.cookies.set(COOKIE_NAME, wert, domain="testserver.local")
            for fenster in (12, 3):
                abgleich.MONATE_ZURUECK = fenster
                r = client.get("/api/zeiten/pruefen")
                assert r.status_code == 200, r.text
                monate = len(r.json()["nach_dem_versand"])
                zeiten = []
                for _ in range(aufrufe):
                    t0 = time.perf_counter()
                    r = client.get("/api/zeiten/pruefen")
                    zeiten.append(time.perf_counter() - t0)
                    assert r.status_code == 200
                teil = []
                for _ in range(aufrufe):
                    db = make_session()
                    t0 = time.perf_counter()
                    abgleich.aenderungen_je_monat(db, tag)
                    teil.append(time.perf_counter() - t0)
                    db.close()
                ergebnisse.append({"tag": tag, "fenster": fenster, "monate": monate, "median": statistics.median(zeiten), "max": max(zeiten),
                                   "teil": statistics.median(teil)})
    finally:
        abgleich.MONATE_ZURUECK = vorher
    return ergebnisse


def lauf(name: str, url: str, connect_args: dict, aufrufe: int) -> list[dict]:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    import app.models  # noqa: F401 -- die Tabellen in Base.metadata
    from app.database import Base

    engine = create_engine(url, connect_args=connect_args)
    try:
        Base.metadata.create_all(engine)
        make_session = sessionmaker(bind=engine)
        _uhr(date(2027, 12, 31))
        db = make_session()
        t0 = time.perf_counter()
        admin_id = befuellen(db)
        from sqlalchemy import func, select

        from app.models import AuditLog, EmployeeAbsence, Lohndatei, TimeEntry
        mengen = {was: db.scalar(select(func.count()).select_from(m)) for was, m in (("Buchungen", TimeEntry), ("Abwesenheiten", EmployeeAbsence),
                                                                                  ("Lohndateien", Lohndatei), ("Einträge der Historie", AuditLog))}
        zeilen = sum(r.inhalt.count(b"\r\n") - 1 for r in db.scalars(select(Lohndatei)))
        db.close()
        print(f"{name}: Testbestand in {time.perf_counter() - t0:.1f} s -- " + ", ".join(f"{n} {w}" for w, n in mengen.items())
              + f", {zeilen} Zeilen in den Lohndateien", flush=True)
        return messen(make_session, admin_id, aufrufe)
    finally:
        engine.dispose()


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Dauer von GET /api/zeiten/pruefen mit vielen gesendeten Lohndateien")
    parser.add_argument("--aufrufe", type=int, default=5)
    parser.add_argument("--pg", help="PostgreSQL-URL (ein Wegwerf-Schema darin, nie public)")
    args = parser.parse_args(argv)
    ordner = Path(tempfile.mkdtemp(prefix="erp-messung-"))
    os.environ.update({"DATABASE_URL": f"sqlite:///{(ordner / 'messung.db').as_posix()}", "ERP_DATA_DIR": str(ordner), "ERP_ENV": "test",
                       "ERP_SECRET_KEY": "messung-" + os.urandom(8).hex()})
    sys.path.insert(0, str(WURZEL))
    alle = []
    try:
        alle += [("SQLite", e) for e in lauf("SQLite", os.environ["DATABASE_URL"], {"check_same_thread": False}, args.aufrufe)]
        if args.pg:
            from sqlalchemy import create_engine, text
            schema = f"pgmessung_{uuid.uuid4().hex[:8]}"
            verwaltung = create_engine(args.pg)
            with verwaltung.begin() as c:
                c.execute(text(f"CREATE SCHEMA {schema}"))
            try:
                alle += [("PostgreSQL", e) for e in lauf("PostgreSQL", args.pg, {"options": f"-csearch_path={schema}", "application_name": schema},
                                                          args.aufrufe)]
            finally:
                with verwaltung.begin() as c:
                    c.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE application_name = :n"), {"n": schema})
                    c.execute(text(f"DROP SCHEMA {schema} CASCADE"))
                verwaltung.dispose()
    finally:
        shutil.rmtree(ordner, ignore_errors=True)
    print("\nDatenbank    heute        Fenster  Monate  /api/zeiten/pruefen (Median / größter)  davon „nach dem Versand“ (Median)")
    for name, e in alle:
        print(f"{name:<12} {e['tag']:%d.%m.%Y}   {e['fenster']:>2} Mon.  {e['monate']:>6}  {e['median']:>8.3f} s / {e['max']:.3f} s"
              f"                {e['teil']:.3f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
