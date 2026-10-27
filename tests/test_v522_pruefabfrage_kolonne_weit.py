"""Version 1.9.100 (Stufe 4, R5b Nachrunde, Punkt 0): scripts/pruefabfrage_kolonne_weit.sql -- die weit gefasste Prüfabfrage der
Kolonnenbuchungen (die enge von 1.9.94 fand auf dem Server nichts).

    a) jede Stundenänderung eines Mitglieds über PUT /api/time-entry-groups/{id}, bei der sich die Stunden des Kopfs in derselben Anfrage
       nicht änderten -- ohne Datumsgrenze, auch nur ein Mitglied, auch gleiche alte Werte; eine Anfrage = Einträge desselben Pfads mit
       höchstens 5 Sekunden Abstand (über eine Minutengrenze hinweg)
    b) ohne Verlauf: Mitglieder mit Von/Bis, deren Stunden nicht zu Von/Bis minus Pause passen (Rechnung wie der Server, Rundung der
       Zeitregeln)
    c) Kontrollzahlen je Monat

Nur lesende Anweisungen; unter PostgreSQL (Wegwerf-Schema, Regel 27) ein Bestand mit gefundenen und unbeteiligten Fällen. Der Verlauf ist
nachgestellt wie in tests/test_v516_pruefabfrage_kolonne_mittel.py -- dass der fehlerhafte Weg (Code von 1.9.89) für die Mitglieder genau
solche Zeilen schrieb, belegt die Probe im Bericht der Nachrunde."""

import re
from datetime import date, datetime, time, timezone
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from app.models import AuditLog, Employee, Team, TeamEmployee, TimeEntry, TimeEntryGroupMember, TimeTrackingSettings

SQL = Path(__file__).resolve().parent.parent / "scripts" / "pruefabfrage_kolonne_weit.sql"


def _anweisungen() -> list[str]:
    """Die SQL-Anweisungen ohne Kommentare und ohne die Zeilen für psql (\\echo der Überschriften)."""
    roh = re.sub(r"--[^\n]*", "", SQL.read_text(encoding="utf-8"))
    roh = "\n".join(z for z in roh.splitlines() if not z.lstrip().startswith("\\"))
    return [a.strip() for a in roh.split(";") if a.strip()]


def test_pruefabfrage_nur_lesend_mit_drei_teilen():
    anweisungen = _anweisungen()
    assert anweisungen[0] == "BEGIN TRANSACTION READ ONLY" and anweisungen[-1] == "ROLLBACK"
    assert len(anweisungen) == 5 and all(a.startswith("WITH") for a in anweisungen[1:-1])
    assert not re.search(r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|GRANT|COPY)\b", " ".join(anweisungen[1:-1]), flags=re.I)
    ueberschriften = re.findall(r"^\\echo '== (\w)\)", SQL.read_text(encoding="utf-8"), flags=re.M)
    assert ueberschriften == ["a", "b", "c"]


def _verlauf(db, *, art, kennung, alt, neu, um, pfad, feld="hours"):
    db.add(AuditLog(occurred_at=um, actor_name="Anna Admin", action="geändert", entity_type=art, entity_id=str(kennung),
                    field_name=feld, old_value=alt, new_value=neu, request_method="PUT", request_path=pfad))


def _berlin(utc: datetime) -> datetime:
    return utc.replace(tzinfo=timezone.utc).astimezone(ZoneInfo("Europe/Berlin")).replace(tzinfo=None)


def test_pruefabfrage_weit_unter_postgresql():
    from sqlalchemy import text

    from app.time_tracking import create_group_manual_entry, start_timer, stop_timer
    from tests.befund_vor_echtbetrieb import pg_sitzung
    from tests.test_v325_contract_basis import beauftragen, make_quote

    with pg_sitzung("kolonne_weit") as db:
        order = beauftragen(db, make_quote(db, is_consumer=False, number="0522a"))
        auftrag = " · ".join(x for x in (order.order_number, order.title) if x)
        mia = Employee(employee_number="M-1", first_name="Mia", last_name="Monteurin", employee_group="gewerblich", active=True)
        tom = Employee(employee_number="M-2", first_name="Tom", last_name="Monteur", employee_group="gewerblich", active=True)
        db.add_all([mia, tom])
        db.flush()
        team = Team(name="Kolonne 1", team_number="K-1", active=True)
        db.add(team)
        db.flush()
        db.add_all([TeamEmployee(team_id=team.id, employee_id=mia.id), TeamEmployee(team_id=team.id, employee_id=tom.id)])
        db.commit()

        def gruppe(tag, **von_bis):
            g = create_group_manual_entry(db, employee_ids=[mia.id, tom.id], team_id=team.id, actor_employee_id=None, is_admin=True,
                                          order_id=order.id, work_date=tag, **(von_bis or {"hours": Decimal("4")}))
            buchung = {m.employee_id: m.time_entry_id for m in db.query(TimeEntryGroupMember).filter_by(group_id=g.id)}
            return g.id, buchung[mia.id], buchung[tom.id], f"/api/time-entry-groups/{g.id}"

        gefunden = []  # (Zeitpunkt UTC, Gruppe, Tag, Name, Buchung, vorher, nachher, Uhrzeiten geändert)

        def fehler(g, tag, wer, buchung, alt, neu, um, uhrzeiten=False):
            _verlauf(db, art="Zeitbuchung", kennung=buchung, alt=alt, neu=neu, um=um, pfad=f"/api/time-entry-groups/{g}")
            gefunden.append((um, g, tag, wer, str(buchung), Decimal(alt), Decimal(neu), uhrzeiten))

        # a) gefunden: klassisch (vorher verschieden), nur ein Mitglied, alte Werte gleich, über die Minutengrenze, vor dem 23.10.2026
        tag = date(2026, 10, 24); g1, m1, t1, p1 = gruppe(tag)
        fehler(g1, tag, "Mia Monteurin", m1, "3.5000", "3.8750", datetime(2026, 10, 24, 8, 0, 5))
        fehler(g1, tag, "Tom Monteur", t1, "4.2500", "3.8750", datetime(2026, 10, 24, 8, 0, 5))
        _verlauf(db, art="Zeitbuchung", kennung=m1, alt="x", neu="Rinne", um=datetime(2026, 10, 24, 8, 0, 5), pfad=p1, feld="notes")
        tag = date(2026, 10, 25); g2, m2, _t2, _p2 = gruppe(tag)
        fehler(g2, tag, "Mia Monteurin", m2, "3.5000", "3.8750", datetime(2026, 10, 25, 8, 0, 5))
        tag = date(2026, 10, 26); g3, m3, t3, _p3 = gruppe(tag)
        fehler(g3, tag, "Mia Monteurin", m3, "4.0000", "3.8750", datetime(2026, 10, 26, 8, 0, 5))
        fehler(g3, tag, "Tom Monteur", t3, "4.0000", "3.8750", datetime(2026, 10, 26, 8, 0, 5))
        tag = date(2026, 10, 27); g4, m4, t4, _p4 = gruppe(tag)
        fehler(g4, tag, "Mia Monteurin", m4, "3.5000", "3.8750", datetime(2026, 10, 27, 8, 0, 59, 800000))
        fehler(g4, tag, "Tom Monteur", t4, "4.2500", "3.8750", datetime(2026, 10, 27, 8, 1, 0, 300000))
        tag = date(2026, 9, 15); g5, m5, t5, _p5 = gruppe(tag)
        fehler(g5, tag, "Mia Monteurin", m5, "3.5000", "3.8750", datetime(2026, 9, 15, 8, 0, 5))
        fehler(g5, tag, "Tom Monteur", t5, "4.2500", "3.8750", datetime(2026, 9, 15, 8, 0, 5))
        # unbeteiligt: bewusste Dauer, der Kopf änderte sich mit -- über die Minutengrenze (die Abfrage von 1.9.94 hätte das gezeigt)
        tag = date(2026, 10, 28); u1, um1, ut1, pu1 = gruppe(tag)
        _verlauf(db, art="Zeitbuchung", kennung=um1, alt="3.5000", neu="8.0000", um=datetime(2026, 10, 28, 8, 0, 59, 900000), pfad=pu1)
        _verlauf(db, art="Zeitbuchung", kennung=ut1, alt="4.2500", neu="8.0000", um=datetime(2026, 10, 28, 8, 0, 59, 950000), pfad=pu1)
        _verlauf(db, art="Gruppen-Zeitbuchung", kennung=u1, alt="3.8750", neu="8.0000", um=datetime(2026, 10, 28, 8, 1, 0, 200000), pfad=pu1)
        # unbeteiligt: ein einzelnes Mitglied über PUT /api/time-entries/{id}
        _verlauf(db, art="Zeitbuchung", kennung=um1, alt="8.0000", neu="7.0000", um=datetime(2026, 10, 28, 9, 0), pfad=f"/api/time-entries/{um1}")
        # gefunden mit „Uhrzeiten geändert“: Ändern mit Von/Bis, das Mittel des Kopfs blieb gleich (kein Fehler, die Spalte sagt es)
        tag = date(2026, 10, 29); g6, m6, _t6, p6 = gruppe(tag)
        fehler(g6, tag, "Mia Monteurin", m6, "5.5000", "5.0000", datetime(2026, 10, 29, 8, 0, 5), uhrzeiten=True)
        _verlauf(db, art="Zeitbuchung", kennung=m6, alt="2026-10-29T07:00:00", neu="2026-10-29T07:30:00", um=datetime(2026, 10, 29, 8, 0, 5),
                 pfad=p6, feld="started_at")
        _verlauf(db, art="Gruppen-Zeitbuchung", kennung=g6, alt="2026-10-29T07:00:00", neu="2026-10-29T07:30:00",
                 um=datetime(2026, 10, 29, 8, 0, 5), pfad=p6, feld="started_at")
        # gefunden: der Fehler, 25 Sekunden später eine bewusste Dauer mit Kopf -- die spätere Anfrage verdeckt die frühere nicht
        tag = date(2026, 10, 30); g7, m7, t7, p7 = gruppe(tag)
        fehler(g7, tag, "Mia Monteurin", m7, "3.5000", "3.8750", datetime(2026, 10, 30, 8, 0, 5))
        fehler(g7, tag, "Tom Monteur", t7, "4.2500", "3.8750", datetime(2026, 10, 30, 8, 0, 5))
        for kennung, art in ((m7, "Zeitbuchung"), (t7, "Zeitbuchung"), (g7, "Gruppen-Zeitbuchung")):
            _verlauf(db, art=art, kennung=kennung, alt="3.8750", neu="8.0000", um=datetime(2026, 10, 30, 8, 0, 30), pfad=p7)

        # b) Kolonnen mit Von/Bis: Tom mit Fahrzeit am Morgen (30 min Pause), danach die Stunden wie der Fehler bis 1.9.89 (Mittel und
        # Pause des Kopfs) -- beide gefunden; eine richtige Kolonne und eine mit Rundung auf 15 min nicht; ein Einzelner nicht
        tag_b = date(2026, 10, 19)
        fahrt = start_timer(db, employee_id=tom.id, order_id=order.id, entry_type="travel", started_at=datetime.combine(tag_b, time(6, 15)))
        stop_timer(db, fahrt.id, ended_at=datetime.combine(tag_b, time(7)))
        gb1, bm1, bt1, _pb1 = gruppe(tag_b, von=time(7), bis=time(12, 30))
        assert [(db.get(TimeEntry, b).hours, db.get(TimeEntry, b).break_minutes) for b in (bm1, bt1)] == [(Decimal("5.5"), 0), (Decimal("5"), 30)]
        for b in (bm1, bt1):
            db.get(TimeEntry, b).hours, db.get(TimeEntry, b).break_minutes = Decimal("5.25"), 30
        gruppe(date(2026, 10, 20), von=time(7), bis=time(11))
        einzeln = start_timer(db, employee_id=mia.id, order_id=order.id, started_at=datetime.combine(date(2026, 10, 21), time(7)))
        stop_timer(db, einzeln.id, ended_at=datetime.combine(date(2026, 10, 21), time(9)))
        db.get(TimeEntry, einzeln.id).hours = Decimal("1.5")
        db.get(TimeTrackingSettings, 1).rounding_minutes = 15
        db.commit()
        _gb3, bm3, _bt3, _pb3 = gruppe(date(2026, 10, 22), von=time(7), bis=time(12, 10))
        assert db.get(TimeEntry, bm3).hours == Decimal("5.25")  # 5,1667 h auf die Viertelstunde
        db.commit()

        conn = db.connection()
        conn.execute(text("SET TRANSACTION READ ONLY"))
        teil_a, teil_b, teil_c = ([tuple(r) for r in conn.execute(text(a)).all()] for a in _anweisungen()[1:4])
        db.rollback()

    assert teil_a == [(g, tag, auftrag, wer, buchung, alt, neu, _berlin(um), "Anna Admin", uhrzeiten)
                      for um, g, tag, wer, buchung, alt, neu, uhrzeiten in sorted(gefunden, key=lambda x: (x[0], x[1], x[3], x[4]))]
    assert len(teil_a) == 12
    assert teil_b == [
        (gb1, tag_b, auftrag, "Mia Monteurin", bm1, "07:00–12:30", 30, Decimal("5.2500"), Decimal("5.00"), Decimal("0.2500"), 15),
        (gb1, tag_b, auftrag, "Tom Monteur", bt1, "07:00–12:30", 30, Decimal("5.2500"), Decimal("5.00"), Decimal("0.2500"), 15),
    ]
    assert teil_c == [("2026-09", 1, 1, 2, 2, 0, 2), ("2026-10", 8, 7, 19, 14, 2, 10)]
