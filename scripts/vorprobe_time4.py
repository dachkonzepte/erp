"""Vorprobe: Einzelbuchungen aus Time 4 durch den echten Nachtragsweg, die Lohndatei erzeugen und mit der Datei aus Time 4 vergleichen (seit 1.9.228,
Lohn L1b, Punkt 5).

    .venv\\Scripts\\python.exe scripts\\vorprobe_time4.py BUCHUNGEN.csv TIME4.txt [--azubis 91010,91012] [--teilzeit 91006=0,3,3,3,0]
                                                      [--gleich 91008=91016] [--ausgabe ERP.txt]

Die Buchungen (Spalten personalnummer;datum;art;von;bis;stunden, wie bildgrundlage/lohn/time4_buchungen_JJJJ_MM.csv) gehen in eine Wegwerf-
Datenbank (SQLite in einem Temp-Ordner, danach gelöscht -- nie die echte, Regel 16) mit den Grunddaten des Starts:

    V          Nachtrag mit Von/Bis ohne eingetragene Pause, in der Reihenfolge des Tags -- dieselben Funktionen wie POST /api/time-entries
               (nachtrag_nach_zeitregel(), create_manual_entry()); ohne Uhrzeit als Dauer
    P          nicht gebucht: die feste Pause von Time 4 gibt es im ERP nicht (es zieht die gesetzliche nach Lesart A ab)
    U, K       Abwesenheit Urlaub, Krankheit (je Tag ein Antrag, gleich genehmigt -- app/absence_requests.py::eintragen()); Urlaub am 31.12. als
               ganzer Urlaubstag
    BS, FB, UU Fortbildung (Art Berufsschule bzw. Weiterbildung), Unbezahlt
    SWW, SWS   Ausfalltag Schlechtwetter (app/schlechtwetter.py::eintragen(), „trotzdem“)
    F          nicht eingetragen: den Feiertag kennt das ERP selbst
    AT         nicht übernommen: eine Abwesenheit für einen Teil des Tags gibt es im ERP nicht (genannt)
    0,00 h     ohne Eintrag (Time 4 führt U und K am Wochenende mit 0,00)

Je Personalnummer eine gewerbliche Person mit Export-Umfang „alles“ und dieser Nummer (auf 5 Stellen), Tarif-Sollzeit; --teilzeit setzt eigene
Werte Mo–Fr, --azubis das Merkmal Azubi. Berater und Mandant kommen aus dem Kopf der Time-4-Datei, der Monat ist abgeschlossen. Danach vergleicht
scripts/pruefe_lohndatei.py die erzeugte Datei mit der Time-4-Datei (dieselben Optionen); seine Ausgabe und Rückgabe sind die dieses Skripts.
"""

from __future__ import annotations

import argparse
import csv
import os
import shutil
import sys
import tempfile
from datetime import date, time
from decimal import Decimal
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
ARTEN = {"U": ("urlaub", "Urlaub"), "K": ("krankheit", "Krankheit"), "BS": ("fortbildung", "Berufsschule"), "FB": ("fortbildung", "Weiterbildung"),
         "UU": ("unbezahlt", "Unbezahlt")}


def _zeit(text: str) -> time:
    h, m = text.split(":")
    return time(int(h), int(m))


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Time-4-Buchungen durch den Nachtragsweg, Lohndatei erzeugen und vergleichen")
    parser.add_argument("buchungen", type=Path)
    parser.add_argument("time4", type=Path)
    parser.add_argument("--azubis", default="")
    parser.add_argument("--teilzeit", action="append", default=[], help="Nummer=Mo,Di,Mi,Do,Fr in Stunden, z. B. 91006=0,3,3,3,0")
    parser.add_argument("--gleich", action="append", default=[])
    parser.add_argument("--ausgabe", type=Path)
    args = parser.parse_args(argv)
    kopf = args.time4.read_bytes().decode("ascii").split("\r\n")[0].split(";")
    berater, mandant, (mm, jjjj) = kopf[0], kopf[1], kopf[2].split("/")
    erster = date(int(jjjj), int(mm), 1)
    with open(args.buchungen, encoding="ascii", newline="") as f:
        zeilen = sorted(csv.DictReader(f, delimiter=";"), key=lambda z: (z["personalnummer"], z["datum"], z["von"] or "99:99"))

    ordner = Path(tempfile.mkdtemp(prefix="erp-vorprobe-"))
    os.environ.update({"DATABASE_URL": f"sqlite:///{(ordner / 'vorprobe.db').as_posix()}", "ERP_DATA_DIR": str(ordner), "ERP_ENV": "test",
                       "ERP_SECRET_KEY": "vorprobe-" + os.urandom(8).hex()})
    sys.path.insert(0, str(WURZEL))
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.absence_requests import eintragen
    from app.database import Base
    from app.grunddaten import anlegen
    from app.lohndatei import monat_ende
    from app.models import Customer, Employee, EmployeePayrollSettings, Order, Project, Property, TimeTrackingSettings
    from app.project_pipeline_columns import default_pipeline_column_id
    from app.schlechtwetter import eintragen as schlechtwetter_eintragen
    from app.sollzeit import WOCHENTAGE, zeile_anlegen
    from app.time_backoffice import build_datev_export
    from app.time_tracking import create_manual_entry, nachtrag_nach_zeitregel

    engine = create_engine(os.environ["DATABASE_URL"])
    try:
        Base.metadata.create_all(engine)
        db = sessionmaker(bind=engine)()
        anlegen(db)
        db.commit()
        kunde = Customer(name="Vorprobe", last_name="Vorprobe", is_consumer=False)
        db.add(kunde); db.flush()
        objekt = Property(customer_id=kunde.id, name="Vorprobe", street="-", postal_code="00000", city="-")
        db.add(objekt); db.flush()
        projekt = Project(project_number="P-VORPROBE", name="Vorprobe", customer_id=kunde.id, property_id=objekt.id, pipeline_column_id=default_pipeline_column_id(db))
        db.add(projekt); db.flush()
        auftrag = Order(order_number="AUF-VORPROBE", project_id=projekt.id, source_quote_id=1, quote_number_snapshot="A-VORPROBE", title="Vorprobe",
                        customer_name="Vorprobe", status="laeuft")
        db.add(auftrag); db.commit()
        azubis = {n.strip() for n in args.azubis.split(",") if n.strip()}
        teilzeit = dict(t.split("=", 1) for t in args.teilzeit)
        personen = {}
        for nummer in sorted({z["personalnummer"] for z in zeilen}):
            e = Employee(employee_number=nummer, first_name="Person", last_name=nummer, employee_group="gewerblich", active=True)
            db.add(e); db.flush()
            db.add(EmployeePayrollSettings(employee_id=e.id, datev_personnel_number=nummer.zfill(5), export_umfang="alles", payroll_export_enabled=True,
                                           azubi=nummer in azubis))
            db.commit()
            if nummer in teilzeit:
                werte = [Decimal(w.replace(",", ".")) for w in teilzeit[nummer].split(",")] + [Decimal("0")] * 2
                zeile_anlegen(db, e.id, date(erster.year - 1, 1, 1), dict(zip(WOCHENTAGE, werte)))
            personen[nummer] = e.id
        nicht_uebernommen = []
        for z in zeilen:
            eid, tag, art = personen[z["personalnummer"]], date.fromisoformat(z["datum"]), z["art"]
            stunden = Decimal(z["stunden"].replace(",", ".")) if z["stunden"] else Decimal("0")
            if art == "V":
                if z["von"]:
                    w = nachtrag_nach_zeitregel(db, employee_id=eid, work_date=tag, von=_zeit(z["von"]), bis=_zeit(z["bis"]), mindestpause=0)
                    create_manual_entry(db, employee_id=eid, order_id=auftrag.id, work_date=tag, entry_type="site", hours=w["netto"], break_minutes=w["pause"],
                                        min_break_minutes=0, started_at=w["beginn"], ended_at=w["ende"])
                else:
                    create_manual_entry(db, employee_id=eid, order_id=auftrag.id, work_date=tag, entry_type="site", hours=stunden, break_minutes=0,
                                        min_break_minutes=0)
            elif art in ARTEN and stunden > 0:
                kategorie, typ = ARTEN[art]
                eintragen(db, gleich_genehmigt=True, employee_id=eid, absence_category=kategorie, absence_type=typ, start_date=tag, end_date=tag,
                          kalendertag_urlaub=True if (tag.month, tag.day) == (12, 31) and art == "U" else None)
            elif art in ("SWW", "SWS") and stunden > 0:
                schlechtwetter_eintragen(db, employee_ids=[eid], tag=tag, notes=None, gleich_genehmigt=True, user_id=None, trotzdem=True)
            elif art in ("AT",) and stunden > 0:
                nicht_uebernommen.append(f"{z['personalnummer']} {tag:%d.%m.} AT {z['stunden']} h")
        s = db.get(TimeTrackingSettings, 1)
        s.datev_beraternummer, s.datev_mandantennummer, s.locked_until = berater, mandant, monat_ende(erster)
        db.commit()
        inhalt, _ext = build_datev_export(db, erster, monat_ende(erster))
        db.close()
    finally:
        engine.dispose()
    ausgabe = args.ausgabe or (ordner / f"ERP_{erster:%Y_%m}.txt")
    ausgabe.write_bytes(inhalt)
    print(f"Vorprobe {erster:%m/%Y}: {len(personen)} Personen, {sum(1 for z in zeilen if z['art'] == 'V')} Buchungen über den Nachtragsweg, "
          f"ERP-Datei {ausgabe if args.ausgabe else '(im Temp-Ordner, danach gelöscht)'}")
    if nicht_uebernommen:
        print("Nicht übernommen (eine Abwesenheit für einen Teil des Tags gibt es im ERP nicht): " + "; ".join(nicht_uebernommen))
    sys.path.insert(0, str(WURZEL / "scripts"))
    import pruefe_lohndatei
    weiter = (["--azubis", args.azubis] if args.azubis else []) + [x for g in args.gleich for x in ("--gleich", g)]
    try:
        return pruefe_lohndatei.main([str(ausgabe), str(args.time4), *weiter])
    finally:
        shutil.rmtree(ordner, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
