"""Version 1.9.94 (Stufe 4, R5b, Punkt 0): scripts/pruefabfrage_kolonne_mittel.sql -- Kolonnenbuchungen, deren Mitglieder durch ein Ändern
ohne Von/Bis dieselben Stunden bekamen (Fehler bis 1.9.89, behoben mit 1.9.90).

Die Abfrage liest nur (schreibgeschützte Transaktion, ROLLBACK) und erkennt den Fehler im Änderungsverlauf: Stunden der Mitglieder über
PUT /api/time-entry-groups/{id} seit dem 23.10.2026 (Berlin), in einer Anfrage alle gleich, vorher verschieden, der Kopf unverändert. Unter
PostgreSQL (Wegwerf-Schema, Regel 27) mit einem Bestand: eine betroffene Gruppe und vier, die nicht erscheinen dürfen (bewusste Dauer mit
geändertem Kopf, Änderung vor dem 23.10., nur ein Mitglied, vorher schon gleich)."""

import re
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from app.models import AuditLog, Employee, Team, TeamEmployee

SQL = Path(__file__).resolve().parent.parent / "scripts" / "pruefabfrage_kolonne_mittel.sql"


def _anweisungen() -> list[str]:
    roh = re.sub(r"--[^\n]*", "", SQL.read_text(encoding="utf-8"))
    return [a.strip() for a in roh.split(";") if a.strip()]


def test_pruefabfrage_nur_lesend():
    anweisungen = _anweisungen()
    assert anweisungen[0] == "BEGIN TRANSACTION READ ONLY" and anweisungen[-1] == "ROLLBACK"
    assert not re.search(r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|GRANT)\b", " ".join(anweisungen[1:-1]), flags=re.I)


def _verlauf(db, *, art, kennung, alt, neu, um, pfad, feld="hours"):
    db.add(AuditLog(occurred_at=um, actor_name="Anna Admin", action="geändert", entity_type=art, entity_id=str(kennung),
                    field_name=feld, old_value=alt, new_value=neu, request_method="PUT", request_path=pfad))


def test_pruefabfrage_findet_die_kolonne_mit_dem_mittel_unter_postgresql():
    from sqlalchemy import text

    from app.time_tracking import create_group_manual_entry, group_member_ids
    from app.models import TimeEntryGroupMember
    from tests.befund_vor_echtbetrieb import pg_sitzung
    from tests.test_v325_contract_basis import beauftragen, make_quote

    with pg_sitzung("kolonne_mittel") as db:
        order = beauftragen(db, make_quote(db, is_consumer=False, number="0516a"))  # Angebot -> Auftrag (Fremdschlüssel unter PostgreSQL)
        mia = Employee(employee_number="M-1", first_name="Mia", last_name="Monteurin", employee_group="gewerblich", active=True)
        tom = Employee(employee_number="M-2", first_name="Tom", last_name="Monteur", employee_group="gewerblich", active=True)
        db.add_all([mia, tom])
        db.flush()
        team = Team(name="Kolonne 1", team_number="K-1", active=True)
        db.add(team)
        db.flush()
        db.add_all([TeamEmployee(team_id=team.id, employee_id=mia.id), TeamEmployee(team_id=team.id, employee_id=tom.id)])
        db.commit()

        def gruppe(tag):
            g = create_group_manual_entry(db, employee_ids=[mia.id, tom.id], team_id=team.id, actor_employee_id=None, is_admin=True,
                                          order_id=order.id, work_date=tag, hours=Decimal("4"))
            buchung = {m.employee_id: m.time_entry_id for m in db.query(TimeEntryGroupMember).filter_by(group_id=g.id)}
            assert sorted(group_member_ids(db, g.id)) == sorted([mia.id, tom.id])
            return g.id, buchung[mia.id], buchung[tom.id]

        betroffen, b_mia, b_tom = gruppe(date(2026, 10, 24))
        pfad = f"/api/time-entry-groups/{betroffen}"
        um = datetime(2026, 10, 24, 8, 0, 5)  # UTC -> 10:00:05 in Berlin
        _verlauf(db, art="Zeitbuchung", kennung=b_mia, alt="3.5000", neu="3.8750", um=um, pfad=pfad)
        _verlauf(db, art="Zeitbuchung", kennung=b_tom, alt="4.2500", neu="3.8750", um=um, pfad=pfad)
        _verlauf(db, art="Zeitbuchung", kennung=b_mia, alt="x", neu="Rinne", um=um, pfad=pfad, feld="notes")  # andere Felder zählen nicht

        dauer, d_mia, d_tom = gruppe(date(2026, 10, 25))  # bewusste Dauer: der Kopf änderte sich mit
        pfad = f"/api/time-entry-groups/{dauer}"
        _verlauf(db, art="Zeitbuchung", kennung=d_mia, alt="3.5000", neu="8.0000", um=um, pfad=pfad)
        _verlauf(db, art="Zeitbuchung", kennung=d_tom, alt="4.2500", neu="8.0000", um=um, pfad=pfad)
        _verlauf(db, art="Gruppen-Zeitbuchung", kennung=dauer, alt="3.8750", neu="8.0000", um=um, pfad=pfad)

        frueh, f_mia, f_tom = gruppe(date(2026, 10, 22))  # 22.10.2026 21:59 UTC = 23:59 in Berlin, vor dem 23.10.
        pfad = f"/api/time-entry-groups/{frueh}"
        for b, alt in ((f_mia, "3.5000"), (f_tom, "4.2500")):
            _verlauf(db, art="Zeitbuchung", kennung=b, alt=alt, neu="3.8750", um=datetime(2026, 10, 22, 21, 59), pfad=pfad)

        einzeln, e_mia, _ = gruppe(date(2026, 10, 26))  # nur ein Mitglied geändert
        _verlauf(db, art="Zeitbuchung", kennung=e_mia, alt="3.5000", neu="3.8750", um=um, pfad=f"/api/time-entry-groups/{einzeln}")

        gleich, g_mia, g_tom = gruppe(date(2026, 10, 27))  # vorher schon gleich
        pfad = f"/api/time-entry-groups/{gleich}"
        for b in (g_mia, g_tom):
            _verlauf(db, art="Zeitbuchung", kennung=b, alt="4.0000", neu="3.8750", um=um, pfad=pfad)
        db.commit()

        conn = db.connection()
        conn.execute(text("SET TRANSACTION READ ONLY"))
        zeilen = [tuple(r) for r in conn.execute(text(_anweisungen()[1])).all()]
        auftrag = " · ".join(x for x in (order.order_number, order.title) if x)
        db.rollback()

    assert zeilen == [
        (betroffen, date(2026, 10, 24), auftrag, "Mia Monteurin", Decimal("3.5000"), Decimal("3.8750"), datetime(2026, 10, 24, 10, 0, 5),
         "Anna Admin"),
        (betroffen, date(2026, 10, 24), auftrag, "Tom Monteur", Decimal("4.2500"), Decimal("3.8750"), datetime(2026, 10, 24, 10, 0, 5),
         "Anna Admin"),
    ]
