"""Version 1.9.353 -- Listen nach Namen wie im Telefonbuch (F6, Runde V2b Punkt 1; Entscheidung Tobias 14.11.2026, Runde 17.11.2026).

Ohne Groß- und Kleinschreibung, Umlaute und Akzente beim Grundbuchstaben (Ä wie A, ß wie ss), leere Namen ans Ende -- unter SQLite und PostgreSQL
gleich, unabhängig von der Kollation des Servers. Der Weg: app/telefonbuch.py (Sortierschlüssel telefonbuch() in der Datenbank, schluessel() und
sortierwert() in Python).

    Regeln       schluessel() je Fall
    gleich       SQLite, PostgreSQL (Funktion aus create_all() und aus der Migration) und Python rechnen denselben Schlüssel und dieselbe Reihenfolge
    Kollation    unter PostgreSQL mit COLLATE "C": die lokale Instanz (German_Germany.1252) ordnete „Müller Bau“ und „Müller-Bau“ sonst umgekehrt
    Liste        GET /api/customers in der Reihenfolge des Telefonbuchs, leere Namen zuletzt (SQLite und PostgreSQL)
    Wächter      keine Sortierung nach einer Namensspalte in der Datenbank an nach_namen() vorbei (order_by, Beziehungen, Suche), danach die ID als
                 letzter Schlüssel, kein lower() zum Sortieren, kein casefold()/lower() und kein roher Name als Sortierschlüssel in Python --
                 AUSNAHMEN darf nur kürzer werden
"""

import ast
import importlib.util
import os
import uuid
from pathlib import Path

import pytest
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, event, insert, select, text

from app import telefonbuch as tb

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
MIGRATION = "9e4b2c7d1a35"

# Namen für die Reihenfolge: Groß/klein, Umlaute, ß, Akzente, Leerzeichen am Rand, leer, kein Name, und ein Paar, das eine deutsche Kollation
# anders ordnet als die Bytes („Müller Bau“ / „Müller-Bau“: German_Germany.1252 übergeht den Bindestrich).
NAMEN = ["Zebra GmbH", "apfel", "Äpfel", "bach", "Bach", "MÜLLER", "Müller-Bau", "Müller Bau", "Muller", "Straße", "Strasse", "",
         "Ökonom", "Oeko", "Łukasz", "Lukas", "Émile", "emil", "  Anton", "ẞ-Werk", "Ærø", "aero"]
REIHENFOLGE = ["Ærø", "aero", "  Anton", "apfel", "Äpfel", "bach", "Bach", "emil", "Émile", "Lukas", "Łukasz", "MÜLLER", "Muller",
               "Müller Bau", "Müller-Bau", "Oeko", "Ökonom", "ẞ-Werk", "Straße", "Strasse", "Zebra GmbH", ""]  # gleicher Schlüssel: wie angelegt


@pytest.mark.parametrize("name, erwartet", [
    ("Äpfel", "apfel"), ("MÜLLER", "muller"), ("Straße", "strasse"), ("STRASSE", "strasse"), ("ẞ", "ss"), ("Ærø", "aero"),
    ("Œuvre", "oeuvre"), ("Łukasz Wójcik", "lukasz wojcik"), ("Émile Çelik", "emile celik"), ("  Anton ", "anton"),
    ("", None), ("   ", None), (None, None), ("Müller-Bau 2", "muller-bau 2"),
])
def test_schluessel(name, erwartet):
    assert tb.schluessel(name) == erwartet


def test_jedes_zeichen_der_tabelle_auf_seinen_grundbuchstaben():
    for grund, zeichen in tb.GRUNDBUCHSTABEN.items():
        assert [tb.schluessel(z) for z in zeichen] == [grund] * len(zeichen)
    assert tb.sortierwert("") == tb.sortierwert(None) == (True, "")
    assert sorted(NAMEN, key=tb.sortierwert) == REIHENFOLGE


def _probe_reihenfolge(engine, anlegen: bool) -> tuple[list, list]:
    m = MetaData()
    t = Table("tb_probe", m, Column("id", Integer, primary_key=True), Column("name", String(80)))
    if anlegen:
        event.listen(m, "after_create", tb.pg_anlegen)
    m.create_all(engine)
    with engine.begin() as c:
        c.execute(insert(t), [{"name": n} for n in NAMEN])
        reihe = [r.name for r in c.execute(select(t).order_by(*tb.nach_namen(t.c.name), t.c.id))]
        schluessel = [r[0] for r in c.execute(select(tb.telefonbuch(t.c.name)).order_by(t.c.id))]
    return reihe, schluessel


def test_sqlite_rechnet_wie_python():
    engine = create_engine("sqlite://")
    try:
        reihe, schluessel = _probe_reihenfolge(engine, anlegen=False)
    finally:
        engine.dispose()
    assert reihe == REIHENFOLGE
    assert schluessel == [tb.schluessel(n) for n in NAMEN]


def _migration():
    pfad = next((ROOT / "alembic" / "versions").glob(f"{MIGRATION}_*.py"))
    spec = importlib.util.spec_from_file_location("migration_telefonbuch", pfad)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def test_migration_traegt_dieselbe_funktion():
    """Die Migration trägt den Text wörtlich (sie darf sich nicht mit dem Code ändern) -- eine geänderte Tabelle braucht eine neue Migration."""
    assert _migration().FUNKTION == tb.pg_sql()


def test_create_all_legt_die_funktion_an():
    import app.models  # noqa: F401
    from app.database import Base
    assert event.contains(Base.metadata, "after_create", tb.pg_anlegen)


@pytest.fixture
def pg_schema():
    url = os.getenv("ERP_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    schema = f"pgtest_tb_{uuid.uuid4().hex[:8]}"
    admin = create_engine(url)
    with admin.begin() as c:
        c.execute(text(f"CREATE SCHEMA {schema}"))
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    try:
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as c:
            c.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin.dispose()


def test_postgresql_rechnet_wie_python(pg_schema):
    reihe, schluessel = _probe_reihenfolge(pg_schema, anlegen=True)
    assert schluessel == [tb.schluessel(n) for n in NAMEN]
    assert reihe == REIHENFOLGE


def test_postgresql_unabhaengig_von_der_kollation(pg_schema):
    """Die Kollation der lokalen Instanz ordnet die Schlüssel anders als die Bytes -- erst COLLATE "C" macht sie gleich (live: C.UTF-8)."""
    _probe_reihenfolge(pg_schema, anlegen=True)
    with pg_schema.connect() as c:
        kollation = c.execute(text("SELECT datcollate FROM pg_database WHERE datname = current_database()")).scalar()
        ohne_c = [r[0] for r in c.execute(text("SELECT name FROM tb_probe ORDER BY telefonbuch(name) NULLS LAST, id"))]
    if kollation in ("C", "POSIX", "C.UTF-8", "C.utf8"):
        pytest.skip(f"Kollation {kollation} sortiert ohnehin binär -- der Unterschied ist hier nicht zu sehen")
    assert ohne_c != REIHENFOLGE, "die Probe zeigt den Unterschied der Kollation nicht mehr -- NAMEN um ein Paar ergänzen"


def test_migration_legt_die_funktion_an(pg_schema):
    from alembic.operations import Operations
    from alembic.runtime.migration import MigrationContext
    modul = _migration()
    with pg_schema.begin() as c:
        with Operations.context(MigrationContext.configure(c)):
            modul.upgrade()
        werte = [c.execute(text("SELECT telefonbuch(:n)"), {"n": n}).scalar() for n in NAMEN]
        assert werte == [tb.schluessel(n) for n in NAMEN]
        with Operations.context(MigrationContext.configure(c)):
            modul.downgrade()
        assert c.execute(text("SELECT count(*) FROM pg_proc p JOIN pg_namespace s ON s.oid = p.pronamespace "
                              "WHERE p.proname = 'telefonbuch' AND s.nspname = current_schema()")).scalar() == 0


def test_kundenliste_in_der_reihenfolge_des_telefonbuchs(threaded_db_session, router_test_client):
    from app.models import Customer
    from app.routers.customers import router
    db = threaded_db_session
    for n in NAMEN:
        db.add(Customer(name=n, last_name=n or "-"))
    db.commit()
    client = router_test_client(db, router)
    assert [c["name"] for c in client.get("/api/customers").json()] == REIHENFOLGE


def test_kundenliste_unter_postgresql():
    from tests.befund_vor_echtbetrieb import pg_sitzung
    from app.models import Customer
    from app.routers.customers import list_customers
    with pg_sitzung("telefonbuch") as db:
        for n in NAMEN:
            db.add(Customer(name=n, last_name=n or "-"))
        db.commit()
        assert [c.name for c in list_customers(db=db, _role=None)] == REIHENFOLGE


# --- Wächter ---------------------------------------------------------------------------------------------------------------------------------

NAMENSSPALTEN = {"name", "display_name", "first_name", "last_name", "label", "title", "company_name", "kurzname", "username"}
NAMENSFELDER = NAMENSSPALTEN | {"nachname", "vorname", "employee_name", "mitarbeiter_name"}
SORTIER_AUFRUFE = {"order_by": None, "_count_and_fetch": 2}  # Funktion -> Stelle des Arguments, das sortiert (None = jedes)
UMWANDELN = {"lower", "upper", "casefold"}
VERGLEICH = {"in_", "not_in", "notin_", "like", "ilike", "startswith", "endswith", "contains", "is_", "isnot", "is_not"}
AUSNAHMEN: dict[str, str] = {
    # "datei.py:zeile": Grund -- darf nur kürzer werden
}


def _dateien():
    for pfad in sorted(APP.rglob("*.py")):
        quelle = pfad.read_text(encoding="utf-8")
        yield pfad.relative_to(ROOT).as_posix(), quelle, ast.parse(quelle)


def _ohne_richtung(node):
    while isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in {"asc", "desc", "nulls_last", "nulls_first"}:
        node = node.func.value
    return node


def _roh_nach_namen(node) -> bool:
    """Sortiert dieser Ausdruck nach einer Namensspalte ohne telefonbuch()?"""
    node = _ohne_richtung(node)
    if isinstance(node, ast.Lambda):
        node = node.body
    if isinstance(node, (ast.Tuple, ast.List)):
        return any(_roh_nach_namen(e) for e in node.elts)
    if isinstance(node, ast.Attribute):
        return node.attr in NAMENSSPALTEN
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return any(t.strip().rsplit(".", 1)[-1] in NAMENSSPALTEN for t in node.value.split(","))
    return False


def verstoesse_datenbank(rel: str, baum) -> list[str]:
    out = []
    for n in ast.walk(baum):
        if not isinstance(n, ast.Call):
            continue
        name = n.func.attr if isinstance(n.func, ast.Attribute) else n.func.id if isinstance(n.func, ast.Name) else None
        if name in SORTIER_AUFRUFE:
            stelle = SORTIER_AUFRUFE[name]
            args = n.args if stelle is None else n.args[stelle:stelle + 1]
            if any(_roh_nach_namen(a) for a in args):
                out.append(f"{rel}:{n.lineno}")
        if name == "relationship":
            for kw in n.keywords:
                if kw.arg == "order_by" and _roh_nach_namen(kw.value):
                    out.append(f"{rel}:{n.lineno}")
    return out


def _sortiert_nach_namen(a) -> bool:
    while isinstance(a, (ast.Starred, ast.Subscript)):
        a = a.value
    return isinstance(a, ast.Call) and isinstance(a.func, ast.Name) and a.func.id in ("nach_namen", "contact_sort_columns")


def _ist_id(a) -> bool:
    a = _ohne_richtung(a)
    return isinstance(a, ast.Attribute) and a.attr == "id"


def verstoesse_id(rel: str, baum) -> list[str]:
    """Wer nach Namen sortiert, nimmt die ID als letzten Schlüssel -- gleiche Namen sonst in beliebiger Reihenfolge."""
    out = []
    for n in ast.walk(baum):
        if not isinstance(n, ast.Call):
            continue
        name = n.func.attr if isinstance(n.func, ast.Attribute) else n.func.id if isinstance(n.func, ast.Name) else None
        gruppen = []
        if name == "order_by":
            gruppen.append(n.args)
        elif name == "_count_and_fetch" and len(n.args) > 2 and isinstance(n.args[2], ast.Tuple):
            gruppen.append(n.args[2].elts)
        elif name == "relationship":
            gruppen += [kw.value.body.elts for kw in n.keywords
                        if kw.arg == "order_by" and isinstance(kw.value, ast.Lambda) and isinstance(kw.value.body, ast.Tuple)]
        for args in gruppen:
            if any(_sortiert_nach_namen(a) for a in args) and not (args and _ist_id(args[-1])):
                out.append(f"{rel}:{n.lineno}")
        if name == "_count_and_fetch" and len(n.args) > 2 and _sortiert_nach_namen(n.args[2]):
            out.append(f"{rel}:{n.lineno}")
    return out


def verstoesse_lower(rel: str, baum) -> list[str]:
    """func.lower()/upper() nur in einem Vergleich (where), nie zum Sortieren."""
    eltern = {}
    for n in ast.walk(baum):
        for k in ast.iter_child_nodes(n):
            eltern[k] = n
    out = []
    for n in ast.walk(baum):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in UMWANDELN
                and isinstance(n.func.value, ast.Name) and n.func.value.id == "func"):
            x, im_vergleich = n, False
            while x in eltern and not isinstance(x, ast.stmt):
                p = eltern[x]
                if isinstance(p, ast.Compare) or (isinstance(p, ast.Attribute) and p.attr in VERGLEICH):
                    im_vergleich = True
                    break
                x = p
            if not im_vergleich:
                out.append(f"{rel}:{n.lineno}")
    return out


def _nennt_namen(node) -> bool:
    for x in ast.walk(node):
        if isinstance(x, ast.Attribute) and x.attr in NAMENSFELDER:
            return True
        if isinstance(x, ast.Subscript) and isinstance(x.slice, ast.Constant) and x.slice.value in NAMENSFELDER:
            return True
        if isinstance(x, ast.Call) and isinstance(x.func, ast.Name) and "name" in x.func.id and x.func.id not in ("sortierwert", "schluessel"):
            return True
    return False


def _nimmt_telefonbuch(node) -> bool:
    return any(isinstance(x, ast.Call) and isinstance(x.func, (ast.Name, ast.Attribute))
               and (x.func.id if isinstance(x.func, ast.Name) else x.func.attr) in ("sortierwert", "schluessel") for x in ast.walk(node))


def verstoesse_python(rel: str, baum) -> list[str]:
    out = []
    for n in ast.walk(baum):
        if not (isinstance(n, ast.Call) and ((isinstance(n.func, ast.Attribute) and n.func.attr == "sort")
                                              or (isinstance(n.func, ast.Name) and n.func.id == "sorted"))):
            continue
        for kw in n.keywords:
            if kw.arg != "key":
                continue
            umgewandelt = any(isinstance(x, ast.Call) and isinstance(x.func, ast.Attribute) and x.func.attr in UMWANDELN for x in ast.walk(kw.value))
            if umgewandelt or (_nennt_namen(kw.value) and not _nimmt_telefonbuch(kw.value)):
                out.append(f"{rel}:{n.lineno}")
    return out


def _alle(pruefung) -> list[str]:
    return [s for rel, _q, baum in _dateien() for s in pruefung(rel, baum)]


@pytest.mark.parametrize("pruefung", [verstoesse_datenbank, verstoesse_id, verstoesse_lower, verstoesse_python], ids=["datenbank", "id", "lower", "python"])
def test_jede_sortierung_nach_namen_wie_im_telefonbuch(pruefung):
    offen = [s for s in _alle(pruefung) if s not in AUSNAHMEN]
    assert offen == [], "nach Namen sortieren über nach_namen() (Datenbank) bzw. sortierwert() (Python), app/telefonbuch.py"


def test_ausnahmen_gibt_es_noch():
    alle = {s for p in (verstoesse_datenbank, verstoesse_id, verstoesse_lower, verstoesse_python) for s in _alle(p)}
    assert [s for s in AUSNAHMEN if s not in alle] == []


def test_der_waechter_erkennt_jede_form():
    rot_db = ["q.order_by(Customer.name)", "q.order_by(Employee.active.desc(), Employee.last_name)", "q.order_by(Team.name.asc(), Team.id)",
              "relationship(order_by='RoofArea.name')", "relationship(order_by=lambda: (RoofArea.name, RoofArea.id))",
              "_count_and_fetch(db, stmt, Supplier.name, limit)"]
    gruen_db = ["q.order_by(*nach_namen(Customer.name), Customer.id)", "q.order_by(Order.id.desc())", "_count_and_fetch(db, stmt, Project.id.desc(), 5)",
                "relationship(order_by=lambda: (*nach_namen(RoofArea.name), RoofArea.id))", "q.order_by(X.sort_order, X.id)"]
    rot_id = ["q.order_by(*nach_namen(Customer.name))", "q.order_by(*nach_namen(Team.name), Team.id, Team.active)",
              "_count_and_fetch(db, stmt, (*nach_namen(Supplier.name),), limit)", "_count_and_fetch(db, stmt, nach_namen(Supplier.name)[0], limit)",
              "relationship(order_by=lambda: (*nach_namen(RoofArea.name),))", "q.order_by(*contact_sort_columns())"]
    gruen_id = ["q.order_by(*nach_namen(Customer.name), Customer.id)", "q.order_by(X.active.desc(), *nach_namen(X.a, X.b), X.id)",
                "_count_and_fetch(db, stmt, (*contact_sort_columns(), Contact.id), limit)", "q.order_by(Order.id.desc())",
                "relationship(order_by=lambda: (*nach_namen(RoofArea.name), RoofArea.id))"]
    rot_lower = ["def s(): return (func.lower(Contact.last_name),)", "q.order_by(func.lower(Customer.name))"]
    gruen_lower = ["q.where(func.lower(Order.status) != 'x')", "q.where(func.lower(Order.status).not_in(['a']))"]
    rot_py = ["xs.sort(key=lambda x: x.name.casefold())", "sorted(xs, key=lambda x: (x['name'] or '').lower())", "sorted(xs, key=lambda x: x.last_name)",
              "xs.sort(key=lambda b: (_employee_name(b), b.activity))", "xs.sort(key=lambda x: (-x['stunden'], x['name']))"]
    gruen_py = ["xs.sort(key=lambda x: sortierwert(x.name))", "sorted(xs, key=lambda x: (x.sort_order, x.id))",
                "xs.sort(key=lambda p: (sortierwert(p.nachname), p.employee_id))", "sorted(xs, key=lambda r: r['id'])"]
    for quelle, pruefung, rot in ([(q, verstoesse_datenbank, True) for q in rot_db] + [(q, verstoesse_datenbank, False) for q in gruen_db]
                                  + [(q, verstoesse_id, True) for q in rot_id] + [(q, verstoesse_id, False) for q in gruen_id]
                                  + [(q, verstoesse_lower, True) for q in rot_lower] + [(q, verstoesse_lower, False) for q in gruen_lower]
                                  + [(q, verstoesse_python, True) for q in rot_py] + [(q, verstoesse_python, False) for q in gruen_py]):
        assert bool(pruefung("probe.py", ast.parse(quelle))) is rot, quelle


def test_betriebsmittel_nach_dem_aufgeloesten_namen(db_session):
    """Bei einem Betriebsmittel mit Gerät bleibt OperationalAsset.name leer, der Name kommt aus dem Gerät -- bis 1.9.352 sortierte die Datenbank
    nach der leeren Spalte (unter SQLite vorn, unter PostgreSQL hinten). Seit 1.9.353 nach dem aufgelösten Namen wie im Telefonbuch."""
    from app.models import OperationalAsset, OperationalResource
    from app.operational_assets import list_assets
    db = db_session
    pritsche = OperationalResource(name="Pritsche", resource_type="Fahrzeug")
    anhaenger = OperationalResource(name="ähnlicher Anhänger", resource_type="Anhänger")
    db.add_all([pritsche, anhaenger])
    db.flush()
    db.add_all([OperationalAsset(resource_id=pritsche.id), OperationalAsset(name="Rüttelplatte"), OperationalAsset(resource_id=anhaenger.id),
                OperationalAsset(name="Leiter")])
    db.commit()
    assert [a["name"] for a in list_assets(db)] == ["ähnlicher Anhänger", "Leiter", "Pritsche", "Rüttelplatte"]
