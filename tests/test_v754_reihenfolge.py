"""Version 1.9.354 -- jede Liste mit fester Reihenfolge, leere Werte ausdrücklich am Ende (Runde V2b, Punkt 2; Befund SQLite/PostgreSQL, Abschnitt 3 E).

Ohne ORDER BY liefert PostgreSQL nach einer Änderung eine andere Reihenfolge (Befund P2b: die Angebote eines Projekts tauschten nach einer Änderung des
Status die Plätze), und leere Werte stehen unter SQLite vorn, unter PostgreSQL hinten (P5). Der Wächter hier:

    Beziehungen   jede Listen-Beziehung (Mapped[list[…]]) hat ein order_by -- ohne eigene Ordnung die des Anlegens (ID), mit sort_order danach
    Abfragen      jede Abfrage, deren Ergebnis eine Folge ist (.all(), for … in db.scalars/execute(select …), list(…)), hat ein order_by -- ohne nur,
                  wo OHNE_REIHENFOLGE sie mit Grund nennt (Zuordnung, Menge, Summe, Prüfung, danach vollständig sortiert); die Liste stimmt genau
    leer          jedes order_by auf einer Spalte, die leer sein darf, sagt nulls_last() (oder nulls_first() mit Grund in NULLS_FIRST) -- in
                  Abfragen und Beziehungen
"""

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
MENGE = {"set", "frozenset", "len", "sum", "any", "all", "min", "max", "sorted", "dict", "Counter"}

Z = "Zuordnung (dict je Schlüssel)"
M = "Menge (set / in_())"
S = "Summe, Anzahl, min oder max"
SORT = "danach vollständig sortiert"
EIN = "höchstens eine Zeile je Schlüssel"
PRUEF = "nur Prüfung (gibt es eine)"
LADEN = "lädt nur neu, Ergebnis unbenutzt"

# datei::funktion -> (Zahl der Abfragen ohne order_by, Grund). Eine neue Abfrage ohne order_by kommt nur mit Grund hierher.
OHNE_REIHENFOLGE = {
    "app/acceptances.py::_defect_counts": (1, Z),
    "app/address_import.py::_run_is_untouched": (2, PRUEF),
    "app/akte.py::signale": (5, f"{Z}; {S}; {EIN}"),
    "app/akte.py::stunden": (1, S),
    "app/akte_verlauf.py::auftraege_je_zeile": (1, M),
    "app/auftragsliste.py::auftragsliste": (1, SORT),
    "app/calendar_events.py::unlink_calendar_events_for_project": (1, M),
    "app/checklist_follow_ups.py::list_follow_ups": (1, SORT),
    "app/defects.py::discard_defect": (1, SORT),
    "app/email_dispatch.py::dispatch_outcomes": (1, EIN),
    "app/email_dispatch.py::document_reached_on": (1, S),
    "app/final_dunning.py::settling_finals": (1, EIN),
    "app/invoices.py::_deducted": (1, SORT),
    "app/invoices.py::_lock_draft": (1, LADEN),
    "app/invoices.py::finalize_and_send_invoice": (1, LADEN),
    "app/kunde_verlauf.py::_aus_schnappschuss": (1, S),
    "app/kundenakte.py::angebot_summen": (1, S),
    "app/lohndatei_abgleich.py::gruende": (1, Z),
    "app/lohndatei_abgleich.py::nach_dem_versand": (1, Z),
    "app/maintenance_contracts.py::list_relevant_contracts_for_employee": (1, M),
    "app/maintenance_contracts.py::vertrag_verwendungen": (1, M),
    "app/meine_zeiten.py::_gruppen": (1, Z),
    "app/orders.py::add_order_addendum": (1, S),
    "app/orders.py::field_accessible_property_ids": (1, M),
    "app/payments.py::_allocation_rows": (1, Z),
    "app/payments.py::customer_balances": (1, S),
    "app/payments.py::refunded_from_rest": (1, Z),
    "app/payments.py::unallocated_by_customer": (1, SORT),
    "app/planning.py::_infer_slot_hours": (1, S),
    "app/planning.py::_kapazitaet_rechnung": (1, S),
    "app/planning.py::_relevant_preparation_ids_for_employee": (2, f"{Z}; {M}"),
    "app/planning.py::_remaining_order_hours": (1, S),
    "app/planning.py::_undatiert_zugeordnete_order_ids": (1, M),
    "app/planning.py::list_field_relevant_property_ids": (2, M),
    "app/planning.py::planning_visible_employee_ids": (1, M),
    "app/productive_hours.py::sick_days_actual": (2, f"{S}; {M}"),
    "app/productive_hours.py::weather_days_actual": (2, f"{S}; {M}"),
    "app/project_participants.py::participant_rows": (1, SORT),
    "app/projects.py::_copy_quote_into_project": (1, SORT),
    "app/projects.py::create_quote_section": (1, S),
    "app/projects.py::update_quote_section": (1, PRUEF),
    "app/routers/users.py::deactivate_app_user": (1, S),
    "app/routers/users.py::delete_app_user": (1, S),
    "app/routers/users.py::update_app_user": (1, S),
    "app/schlechtwetter.py::ausfall": (1, S),
    "app/schlechtwetter.py::ausfalltage": (1, SORT),
    "app/schlechtwetter.py::warnungen": (1, S),
    "app/service_reports.py::_resolve_inspection_template": (1, PRUEF),
    "app/two_factor.py::_consume_recovery_code": (1, PRUEF),
    "app/verlauf_namen.py::kontext_laden": (2, Z),
    "app/zeiten.py::umfang_hinweise": (1, M),
}
NULLS_FIRST: dict[str, str] = {}  # "datei:zeile": Grund -- leer


# --- Abfragen ----------------------------------------------------------------------------------------------------------------------------------

def _hat_order_by(node) -> bool:
    return any(isinstance(x, ast.Attribute) and x.attr == "order_by" for x in ast.walk(node))


def _ist_abfrage(node) -> bool:
    if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in ("scalars", "execute") and node.args):
        return False
    a = node.args[0]
    return any(isinstance(x, ast.Call) and isinstance(x.func, ast.Name) and x.func.id == "select" for x in ast.walk(a)) and not _hat_order_by(a)


def _funktion(eltern, node) -> str:
    while node in eltern:
        node = eltern[node]
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return node.name
    return "<modul>"


def _als_menge(eltern, node) -> bool:
    p = eltern.get(node)
    if isinstance(p, ast.Call) and isinstance(p.func, ast.Name) and p.func.id in MENGE:
        return True
    if isinstance(p, ast.Call) and isinstance(p.func, ast.Attribute) and p.func.attr in ("update", "difference_update", "intersection_update"):
        return True
    return isinstance(p, ast.comprehension) and isinstance(eltern.get(p), (ast.SetComp, ast.DictComp))


def folgen_ohne_order_by(rel: str, quelle: str) -> list[str]:
    """datei::funktion je Abfrage, deren Ergebnis eine Folge ist, ohne order_by."""
    baum = ast.parse(quelle)
    eltern = {k: n for n in ast.walk(baum) for k in ast.iter_child_nodes(n)}
    out = []
    for n in ast.walk(baum):
        kandidat = None
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "all" and not n.args and _ist_abfrage(n.func.value):
            kandidat = n
        elif _ist_abfrage(n):
            p = eltern.get(n)
            if isinstance(p, (ast.For, ast.comprehension)) and p.iter is n:
                kandidat = n
            elif isinstance(p, ast.Call) and isinstance(p.func, ast.Name) and p.func.id == "list":
                kandidat = p
        if kandidat is not None and not _als_menge(eltern, kandidat):
            out.append(f"{rel}::{_funktion(eltern, kandidat)}")
    return out


def _alle_folgen() -> dict[str, int]:
    zahl: dict[str, int] = {}
    for pfad in sorted(APP.rglob("*.py")):
        for s in folgen_ohne_order_by(pfad.relative_to(ROOT).as_posix(), pfad.read_text(encoding="utf-8")):
            zahl[s] = zahl.get(s, 0) + 1
    return zahl


def test_jede_folge_hat_ein_order_by():
    ist = _alle_folgen()
    ohne_grund = {s: n for s, n in ist.items() if n > OHNE_REIHENFOLGE.get(s, (0, ""))[0]}
    assert ohne_grund == {}, "Abfrage ohne order_by: .order_by(...) ergänzen -- nur mit Grund nach OHNE_REIHENFOLGE"


def test_ohne_reihenfolge_stimmt_genau():
    ist = _alle_folgen()
    assert {s: n for s, (n, _g) in OHNE_REIHENFOLGE.items() if ist.get(s, 0) != n} == {}, "OHNE_REIHENFOLGE an den Bestand anpassen"


# --- Beziehungen und leere Werte ---------------------------------------------------------------------------------------------------------------

def _mapper():
    import app.models  # noqa: F401
    from app.database import Base
    return {m.class_.__name__: m for m in Base.registry.mappers}


def test_jede_listen_beziehung_hat_eine_reihenfolge():
    ohne = [f"{m.class_.__name__}.{r.key}" for m in _mapper().values() for r in m.relationships if r.uselist and not r.order_by
            and r.secondary is None]
    assert ohne == []


def _leer_erlaubt(spalte) -> bool:
    return getattr(spalte, "nullable", False) and not getattr(spalte, "primary_key", False)


def test_leere_werte_in_beziehungen_am_ende():
    from sqlalchemy.sql.elements import UnaryExpression
    from sqlalchemy.sql import operators
    offen = []
    for m in _mapper().values():
        for r in m.relationships:
            for e in r.order_by or ():
                nulls = e.modifier if isinstance(e, UnaryExpression) and e.modifier in (operators.nulls_last_op, operators.nulls_first_op) else None
                kern = e
                while isinstance(kern, UnaryExpression):
                    kern = kern.element
                if _leer_erlaubt(kern) and nulls is None:
                    offen.append(f"{m.class_.__name__}.{r.key}: {e}")
    assert offen == []


def _kern(node):
    nulls = None
    while isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in {"asc", "desc", "nulls_last", "nulls_first"}:
        if node.func.attr in ("nulls_last", "nulls_first"):
            nulls = node.func.attr
        node = node.func.value
    return node, nulls


def leere_werte_ohne_angabe(rel: str, quelle: str, mapper) -> list[str]:
    out = []
    for n in ast.walk(ast.parse(quelle)):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "order_by":
            for a in n.args:
                kern, nulls = _kern(a)
                if nulls == "nulls_first" and f"{rel}:{n.lineno}" in NULLS_FIRST:
                    continue
                if isinstance(kern, ast.Attribute) and isinstance(kern.value, ast.Name) and kern.value.id in mapper:
                    attrs = mapper[kern.value.id].attrs
                    spalte = attrs[kern.attr].columns[0] if kern.attr in attrs and hasattr(attrs[kern.attr], "columns") else None
                    if spalte is not None and _leer_erlaubt(spalte) and nulls != "nulls_last":
                        out.append(f"{rel}:{n.lineno} {kern.value.id}.{kern.attr}")
    return out


def test_leere_werte_in_abfragen_am_ende():
    mapper = _mapper()
    offen = [s for p in sorted(APP.rglob("*.py")) for s in leere_werte_ohne_angabe(p.relative_to(ROOT).as_posix(), p.read_text(encoding="utf-8"), mapper)]
    assert offen == [], "order_by auf einer Spalte, die leer sein darf: .nulls_last() (leere Werte ans Ende)"


def test_der_waechter_erkennt_jede_form():
    rot = ["def f(db): return db.scalars(select(X).where(X.a == 1)).all()",
           "def f(db):\n    for x in db.scalars(select(X)):\n        print(x)",
           "def f(db): return list(db.scalars(select(X)))",
           "def f(db): return [x for x in db.execute(select(X.a, X.b))]"]
    gruen = ["def f(db): return db.scalars(select(X).order_by(X.id)).all()",
             "def f(db): return set(db.scalars(select(X.id)).all())",
             "def f(db): return {x.id: x for x in db.scalars(select(X))}",
             "def f(db): return len(db.scalars(select(X)).all())",
             "def f(db): s.update(db.scalars(select(X.id)).all())",
             "def f(db): return db.scalar(select(X))"]
    assert [bool(folgen_ohne_order_by("p.py", q)) for q in rot] == [True] * len(rot)
    assert [folgen_ohne_order_by("p.py", q) for q in gruen] == [[]] * len(gruen)
    mapper = _mapper()
    assert leere_werte_ohne_angabe("p.py", "q.order_by(Task.due_date)", mapper) == ["p.py:1 Task.due_date"]
    assert leere_werte_ohne_angabe("p.py", "q.order_by(Task.due_date.desc())", mapper) == ["p.py:1 Task.due_date"]
    assert leere_werte_ohne_angabe("p.py", "q.order_by(Task.due_date.nulls_last(), Task.id)", mapper) == []
    assert leere_werte_ohne_angabe("p.py", "q.order_by(Task.id)", mapper) == []


# --- Verhalten ---------------------------------------------------------------------------------------------------------------------------------

def test_angebote_eines_projekts_bleiben_in_ihrer_reihenfolge():
    """Befund P2b: unter PostgreSQL tauschten die Angebote eines Projekts nach einer Änderung des Status die Plätze (die geänderte Zeile kam ans
    Ende der Tabelle) -- jetzt in der Reihenfolge des Anlegens (Project.quotes, order_by ID)."""
    from app.models import Quote
    from app.routers.projects import list_project_quotes
    from tests.befund_vor_echtbetrieb import pg_sitzung
    from tests.test_v192_project_templates import make_full_project
    with pg_sitzung("reihenfolge") as db:
        project = make_full_project(db)
        db.add(Quote(project_id=project.id, quote_number="A-ZWEI", title="Zweites", status="entwurf"))
        db.commit()
        vorher = [q.id for q in list_project_quotes(project.id, db=db, _role=None)]
        erstes = db.get(Quote, vorher[0])
        erstes.status = "beauftragt"
        db.commit()
        db.expire_all()
        nachher = [q.id for q in list_project_quotes(project.id, db=db, _role=None)]
        assert vorher == nachher == sorted(vorher)


def test_dauer_buchung_am_ende_ihres_tags_auch_unter_postgresql():
    """Befund P5: leere Werte stehen unter SQLite bei absteigender Sortierung hinten, unter PostgreSQL vorn. list_entries() sortiert je Tag nach
    Beginn absteigend -- eine Dauer-Buchung (ohne Beginn) steht jetzt überall am Ende ihres Tags (nulls_last)."""
    from datetime import date, datetime
    from decimal import Decimal
    from app.models import Employee, TimeEntry
    from app.time_tracking import list_entries
    from tests.befund_vor_echtbetrieb import pg_sitzung
    from tests.test_v133_invoices import make_order_with_item
    with pg_sitzung("reihenfolge") as db:
        order, _item = make_order_with_item(db)
        e = Employee(first_name="Rita", last_name="Reihe")
        db.add(e)
        db.flush()
        tag = date(2027, 3, 3)
        db.add_all([
            TimeEntry(employee_id=e.id, project_id=order.project_id, order_id=order.id, work_date=tag, entry_type="site", hours=Decimal("2"),
                      status="booked", notes="dauer"),
            TimeEntry(employee_id=e.id, project_id=order.project_id, order_id=order.id, work_date=tag, entry_type="site", hours=Decimal("3"),
                      started_at=datetime(2027, 3, 3, 7, 0), ended_at=datetime(2027, 3, 3, 10, 0), status="booked", notes="früh"),
            TimeEntry(employee_id=e.id, project_id=order.project_id, order_id=order.id, work_date=tag, entry_type="site", hours=Decimal("2"),
                      started_at=datetime(2027, 3, 3, 11, 0), ended_at=datetime(2027, 3, 3, 13, 0), status="booked", notes="spät"),
        ])
        db.commit()
        assert [x.notes for x in list_entries(db, employee_id=e.id, limit=None)] == ["spät", "früh", "dauer"]
