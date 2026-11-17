"""Version 1.9.358 -- ein Baustein für LIKE: Zeichen geschützt, Fluchtzeichen ausdrücklich (Runde V2c, Punkt 3; Befund Abschnitt 3 F, P8).

Bis 1.9.357 setzten 18 Suchmuster (17 in app/search.py, eins in app/contacts.py) und vier weitere (Aufgaben, Material, Änderungshistorie, Verlauf des
Kunden) den Text roh ein: „%“ und „_“ wirkten auf beiden Datenbanken als Platzhalter, der Backslash unter PostgreSQL als Fluchtzeichen -- die Büro-Suche
„a\\b“ fand dort „ab“ (P8). Jetzt über app/suchmuster.py (enthaelt(), beginnt_mit(), ESCAPE), Vorbild app/search.py::search_orders_for_field().

    Baustein   jedes Zeichen gilt wörtlich
    Wächter    jedes like/ilike unter app/ nimmt sein Muster aus dem Baustein und trägt escape=ESCAPE -- AUSNAHMEN leer
    Verhalten  Büro-Suche, Aufgaben, Material, Adressbuch: „a\\b“, „50%“ und „A_1“ finden nur sich selbst -- unter SQLite und PostgreSQL
"""

import ast
from pathlib import Path

import pytest

from app.suchmuster import ESCAPE, beginnt_mit, enthaelt

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
LIKE = {"like", "ilike", "notlike", "notilike"}
BAUSTEIN = {"enthaelt", "beginnt_mit"}
AUSNAHMEN: set[str] = set()  # „datei::funktion“; leer


def test_baustein_schuetzt_jedes_zeichen():
    assert ESCAPE == "\\"
    assert enthaelt("a\\b%c_d") == "%a\\\\b\\%c\\_d%"
    assert beginnt_mit("x_y#") == "x\\_y#%"
    assert enthaelt("") == "%%" and enthaelt(5) == "%5%"


def _vom_baustein(node) -> bool:
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in BAUSTEIN


def _funktion(eltern, node):
    while node in eltern:
        node = eltern[node]
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return node
    return None


def ohne_baustein(rel: str, quelle: str) -> list[str]:
    """datei::funktion je like/ilike, dessen Muster nicht aus dem Baustein kommt oder das kein escape=ESCAPE trägt."""
    baum = ast.parse(quelle)
    eltern = {k: n for n in ast.walk(baum) for k in ast.iter_child_nodes(n)}
    out = []
    for n in ast.walk(baum):
        if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in LIKE):
            continue
        fn = _funktion(eltern, n)
        escape = [k.value for k in n.keywords if k.arg == "escape"]
        ok_escape = len(escape) == 1 and isinstance(escape[0], ast.Name) and escape[0].id == "ESCAPE"
        muster = n.args[0] if n.args else None
        ok_muster = _vom_baustein(muster)
        if isinstance(muster, ast.Name) and fn is not None:
            zuweisungen = [z.value for z in ast.walk(fn) if isinstance(z, ast.Assign) and any(isinstance(t, ast.Name) and t.id == muster.id for t in z.targets)]
            parameter = {a.arg for a in fn.args.args + fn.args.kwonlyargs}
            ok_muster = bool(zuweisungen) and all(_vom_baustein(z) for z in zuweisungen) and muster.id not in parameter
        if not (ok_escape and ok_muster):
            out.append(f"{rel}::{fn.name if fn else '<modul>'}")
    return out


def _alle() -> list[str]:
    return [s for p in sorted(APP.rglob("*.py")) for s in ohne_baustein(p.relative_to(ROOT).as_posix(), p.read_text(encoding="utf-8"))]


def test_jedes_suchmuster_aus_dem_baustein():
    assert [s for s in _alle() if s not in AUSNAHMEN] == [], "LIKE-Muster über app/suchmuster.py: x.ilike(enthaelt(text), escape=ESCAPE)"


def test_der_waechter_erkennt_jede_form():
    rot = ['def f(t): return X.a.ilike(f"%{t}%")', "def f(t): return X.a.ilike(enthaelt(t))", 'def f(t): return X.a.ilike(enthaelt(t), escape="#")',
           'def f(t):\n    p = f"%{t}%"\n    return X.a.ilike(p, escape=ESCAPE)', "def f(p): return X.a.ilike(p, escape=ESCAPE)",
           'def f(k): return X.a.like(k + "%", escape=ESCAPE)']
    gruen = ["def f(t): return X.a.ilike(enthaelt(t), escape=ESCAPE)", "def f(k): return X.a.like(beginnt_mit(k), escape=ESCAPE)",
             "def f(t):\n    p = enthaelt(t)\n    return X.a.ilike(p, escape=ESCAPE) | X.b.ilike(p, escape=ESCAPE)", "def f(s): return s.startswith('x')"]
    assert [bool(ohne_baustein("p.py", q)) for q in rot] == [True] * len(rot)
    assert [ohne_baustein("p.py", q) for q in gruen] == [[]] * len(gruen)


# --- Verhalten: jedes Zeichen gilt wörtlich, unter SQLite und PostgreSQL ------------------------------------------------------------------------

def _pruefen(db):
    from app.contacts import list_contacts
    from app.materials import list_materials
    from app.models import Contact, Customer, Material, Task
    from app.search import _search_customers
    from app.tasks import list_tasks
    db.add_all([Customer(name="Probe a\\b", last_name="Probe a\\b"), Customer(name="Probe ab", last_name="Probe ab"),
                Customer(name="Probe 50% Rabatt", last_name="Probe 50% Rabatt"), Customer(name="Probe 500", last_name="Probe 500")])
    db.add_all([Task(title="50% Anzahlung prüfen"), Task(title="500 Ziegel bestellen")])
    db.add_all([Material(name="Schraube A_1", unit="Stk", purchase_price=1), Material(name="Schraube AB1", unit="Stk", purchase_price=1)])
    db.add_all([Contact(kind="person", last_name="Probe_Bau"), Contact(kind="person", last_name="ProbeXBau")])
    db.commit()
    assert [c.name for c in _search_customers(db, "a\\b", 10)[1]] == ["Probe a\\b"]
    assert [c.name for c in _search_customers(db, "50%", 10)[1]] == ["Probe 50% Rabatt"]
    assert [t["title"] for t in list_tasks(db, search="50%")] == ["50% Anzahlung prüfen"]
    assert [m.name for m in list_materials(db, search="A_1")] == ["Schraube A_1"]
    assert [c["last_name"] for c in list_contacts(db, search="Probe_")] == ["Probe_Bau"]


def test_jedes_zeichen_woertlich_unter_sqlite(db_session):
    _pruefen(db_session)


def test_jedes_zeichen_woertlich_unter_postgresql():
    from tests.befund_vor_echtbetrieb import pg_sitzung
    with pg_sitzung("suchmuster") as db:
        _pruefen(db)
