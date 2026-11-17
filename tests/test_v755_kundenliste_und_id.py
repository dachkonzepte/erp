"""Version 1.9.355 -- Kundenliste nach Nachname, dann Vorname; jede Sortierung endet auf der ID (Runde V2c, Punkt 0; F1 und F2 aus dem Bericht V2b).

    Kundenliste  GET /api/customers und die Kunden der Büro-Suche nach Nachname, dann Vorname -- ohne Anrede und Titel; eine Firma trägt ihren Namen im
                 Nachnamen und steht dort (SQLite und PostgreSQL)
    ID zuletzt   jedes order_by unter app/ endet auf der ID (Primärschlüssel) -- bei Gleichstand (gleiches Datum, gleicher Status, gleicher Rang) ist die
                 Reihenfolge unter PostgreSQL sonst offen; ebenso jede Listen-Beziehung und jeder Aufruf von _count_and_fetch() (Büro-Suche).
                 Ohne ID nur, wo AUSNAHMEN es mit Grund nennt (GROUP BY je ID, nur ein Wert); die Liste stimmt genau
"""

import ast
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"

# datei::funktion -> (Zahl der order_by, die nicht auf der ID enden, Grund)
AUSNAHMEN = {
    "app/checklist_follow_ups.py::list_checklists_with_open_follow_ups": (1, "GROUP BY je Checkliste: sortiert nach ihrer ID, eine Zeile je ID"),
    "app/checklist_rules.py::list_checklists_with_open_rules": (1, "GROUP BY je Checkliste: sortiert nach ihrer ID, eine Zeile je ID"),
    "app/search.py::_count_and_fetch": (1, "Helfer der Büro-Suche: die Aufrufer geben die Sortierung mit (geprüft in test_jeder_aufruf_der_suche_endet_auf_der_id)"),
    "app/settings.py::highest_existing": (1, "liest nur die Werte einer Nummernspalte; bei Gleichstand derselbe Wert"),
}

# (Anrede, Titel, Vorname, Nachname) -- angelegt in dieser Reihenfolge, weder nach dem ganzen Namen noch nach dem Nachnamen sortiert
KUNDEN = [("Herr", "Dr.", "Bernd", "Zander"), ("Frau", None, "Anna", "Müller"), (None, None, None, "Bauhof GmbH"), ("Herr", None, "bernd", "müller"),
          ("Frau", None, "Erika", "Abel"), (None, None, None, "Müller"), ("Prof.", "Dr.", None, "Ölberg"), (None, None, None, "Müller GmbH"),
          ("Frau", None, "Anna", "Müller")]
# Nachname, dann Vorname wie im Telefonbuch; ohne Vorname nach denen mit (leere Werte ans Ende); gleicher Name: wie angelegt
NACH_NACHNAME = ["Frau Erika Abel", "Bauhof GmbH", "Frau Anna Müller", "Frau Anna Müller", "Herr bernd müller", "Müller", "Müller GmbH",
                 "Prof. Dr. Ölberg", "Herr Dr. Bernd Zander"]


def _kunden(db):
    from app.crm import compose_customer_name
    from app.models import Customer
    for anrede, titel, vorname, nachname in KUNDEN:
        db.add(Customer(name=compose_customer_name(anrede, titel, vorname, nachname), salutation=anrede, title=titel, first_name=vorname,
                        last_name=nachname))
        db.flush()
    db.commit()


def test_kundenliste_nach_nachname_dann_vorname(threaded_db_session, router_test_client):
    from app.routers.customers import router
    db = threaded_db_session
    _kunden(db)
    client = router_test_client(db, router)
    assert [c["name"] for c in client.get("/api/customers").json()] == NACH_NACHNAME


def test_kunden_der_buero_suche_in_derselben_reihenfolge(db_session):
    from app.search import _search_customers
    _kunden(db_session)
    _anzahl, treffer = _search_customers(db_session, "", 50)
    assert [c.name for c in treffer] == NACH_NACHNAME


def test_kundenliste_unter_postgresql():
    from app.routers.customers import list_customers
    from tests.befund_vor_echtbetrieb import pg_sitzung
    with pg_sitzung("kundenliste") as db:
        _kunden(db)
        assert [c.name for c in list_customers(db=db, _role=None)] == NACH_NACHNAME


def test_gleicher_tag_bleibt_in_der_reihenfolge_auch_unter_postgresql():
    """Zwei Wartungsverträge, fällig am selben Tag: unter PostgreSQL ohne ID als letzten Schlüssel tauschten sie nach einer Änderung des ersten die
    Plätze (die geänderte Zeile steht danach hinten in der Tabelle) -- jetzt in der Reihenfolge des Anlegens."""
    from app.maintenance_contracts import list_contracts
    from app.models import Customer, MaintenanceContract
    from tests.befund_vor_echtbetrieb import pg_sitzung
    with pg_sitzung("kundenliste") as db:
        kunde = Customer(name="Probe", last_name="Probe")
        db.add(kunde)
        db.flush()
        for titel in ("Erster Vertrag", "Zweiter Vertrag"):
            db.add(MaintenanceContract(customer_id=kunde.id, title=titel, next_due_date=date(2027, 4, 1)))
            db.flush()
        db.commit()
        vorher = [c["id"] for c in list_contracts(db)]
        erster = db.get(MaintenanceContract, vorher[0])
        erster.title = "Erster Vertrag, geändert"
        db.commit()
        db.expire_all()
        assert [c["id"] for c in list_contracts(db)] == vorher == sorted(vorher)


# --- Wächter: ID als letzter Schlüssel ---------------------------------------------------------------------------------------------------------

def _mapper():
    import app.models  # noqa: F401
    from app.database import Base
    return {m.class_.__name__: m for m in Base.registry.mappers}


def _kern(node):
    while isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in {"asc", "desc", "nulls_last", "nulls_first"}:
        node = node.func.value
    return node


def _ist_id(node, mapper) -> bool:
    """X.id (auch modell.id) oder der Primärschlüssel einer Klasse des Modells."""
    node = _kern(node)
    if not isinstance(node, ast.Attribute):
        return False
    if node.attr == "id":
        return True
    return isinstance(node.value, ast.Name) and node.value.id in mapper and any(c.key == node.attr for c in mapper[node.value.id].primary_key)


def _letzter(args):
    """Letzter Sortierschlüssel; *(…) eines Tupels wird aufgelöst, sonst None (unbekannt)."""
    if not args:
        return None
    a = args[-1]
    if isinstance(a, ast.Starred):
        return a.value.elts[-1] if isinstance(a.value, ast.Tuple) and a.value.elts else None
    return a


def _funktion(eltern, node) -> str:
    while node in eltern:
        node = eltern[node]
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return node.name
    return "<modul>"


def ohne_id(rel: str, quelle: str, mapper) -> list[str]:
    """datei::funktion je order_by(...) und _count_and_fetch(...), dessen letzter Schlüssel nicht die ID ist."""
    baum = ast.parse(quelle)
    eltern = {k: n for n in ast.walk(baum) for k in ast.iter_child_nodes(n)}
    out = []
    for n in ast.walk(baum):
        if not isinstance(n, ast.Call):
            continue
        if isinstance(n.func, ast.Attribute) and n.func.attr == "order_by" and n.args:
            letzter = _letzter(n.args)
        elif isinstance(n.func, ast.Name) and n.func.id == "_count_and_fetch" and len(n.args) >= 3:
            a = n.args[2]
            letzter = _letzter(a.elts) if isinstance(a, ast.Tuple) else a
        else:
            continue
        if letzter is None or not _ist_id(letzter, mapper):
            out.append(f"{rel}::{_funktion(eltern, n)}")
    return out


def _alle() -> dict[str, int]:
    mapper = _mapper()
    zahl: dict[str, int] = {}
    for pfad in sorted(APP.rglob("*.py")):
        for s in ohne_id(pfad.relative_to(ROOT).as_posix(), pfad.read_text(encoding="utf-8"), mapper):
            zahl[s] = zahl.get(s, 0) + 1
    return zahl


def test_jede_sortierung_endet_auf_der_id():
    offen = {s: n for s, n in _alle().items() if n > AUSNAHMEN.get(s, (0, ""))[0]}
    assert offen == {}, "order_by ohne ID als letzten Schlüssel: …, X.id (bzw. X.id.desc()) anhängen -- nur mit Grund nach AUSNAHMEN"


def test_ausnahmen_stimmen_genau():
    ist = _alle()
    assert {s: n for s, (n, _g) in AUSNAHMEN.items() if ist.get(s, 0) != n} == {}, "AUSNAHMEN an den Bestand anpassen"


def test_jeder_aufruf_der_suche_endet_auf_der_id():
    """_count_and_fetch() reicht seine Sortierung durch -- jeder Aufruf gibt die ID als letzten Schlüssel mit (sonst stünde er oben in _alle())."""
    quelle = (APP / "search.py").read_text(encoding="utf-8")
    aufrufe = [n for n in ast.walk(ast.parse(quelle)) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "_count_and_fetch"]
    assert len(aufrufe) >= 15
    assert [s for s in _alle() if s.startswith("app/search.py::") and s != "app/search.py::_count_and_fetch"] == []


def test_jede_listen_beziehung_endet_auf_der_id():
    from sqlalchemy.sql.elements import UnaryExpression
    offen = []
    for name, m in _mapper().items():
        for r in m.relationships:
            if not r.uselist or not r.order_by:
                continue
            letzter = r.order_by[-1]
            while isinstance(letzter, UnaryExpression):
                letzter = letzter.element
            if not getattr(letzter, "primary_key", False):
                offen.append(f"{name}.{r.key}: {[str(x) for x in r.order_by]}")
    assert offen == []


def test_der_waechter_erkennt_jede_form():
    mapper = _mapper()
    rot = ["def f(q): return q.order_by(Invoice.created_at)", "def f(q): return q.order_by(Invoice.created_at.desc())",
           "def f(q): return q.order_by(X.id, X.name)", "def f(q): return q.order_by(*nach_namen(X.name))",
           "def f(q): return q.order_by(*spalten)", "def f(db, s): return _count_and_fetch(db, s, (*nach_namen(X.name),), 5)",
           "def f(db, s): return _count_and_fetch(db, s, X.name, 5)", "def f(q): return q.order_by(X.employee_id)"]
    gruen = ["def f(q): return q.order_by(Invoice.created_at, Invoice.id)", "def f(q): return q.order_by(Invoice.created_at.desc(), Invoice.id.desc())",
             "def f(q): return q.order_by(*nach_namen(X.name), X.id)", "def f(q): return q.order_by(modell.start_at, modell.id)",
             "def f(q): return q.order_by(TimeEntry.started_at.desc().nulls_last(), TimeEntry.id.desc())",
             "def f(db, s): return _count_and_fetch(db, s, (*nach_namen(X.name), X.id), 5)", "def f(db, s): return _count_and_fetch(db, s, X.id.desc(), 5)"]
    assert [bool(ohne_id("p.py", q, mapper)) for q in rot] == [True] * len(rot)
    assert [ohne_id("p.py", q, mapper) for q in gruen] == [[]] * len(gruen)
