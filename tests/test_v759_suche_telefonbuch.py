"""Version 1.9.359 -- die Büro-Suche vergleicht wie die Sortierung (Runde V2c, Punkt 4; Befund Abschnitt 3 D, P3/P3b).

ilike behandelt unter SQLite nur ASCII ohne Groß- und Kleinschreibung: „müller“ fand „MÜLLER Bau“ nicht, unter PostgreSQL schon (P3). Und „muller“ fand
„Müller“ nirgends. Jetzt vergleicht die Büro-Suche über telefonbuch() (app/suchmuster.py::passt()): der Schlüssel der Spalte enthält den Schlüssel des
Suchtexts -- ohne Groß- und Kleinschreibung, Umlaute und Akzente beim Grundbuchstaben, ß wie ss; jedes Zeichen sonst wörtlich (1.9.358).

    Wächter    app/search.py vergleicht nur über passt() (kein like/ilike daneben), ebenso der Filter des Adressbuchs (contact_search_filter(), den die
               Büro-Suche teilt)
    Verhalten  „muller“, „Müller“, „MÜLLER“ finden dieselben Kunden, Objekte, Projekte, Kontakte; „strasse“ findet „Straße“ -- unter SQLite und PostgreSQL
"""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIKE = {"like", "ilike", "notlike", "notilike"}


def like_ausser_passt(quelle: str, nur_funktion: str | None = None) -> list[int]:
    baum = ast.parse(quelle)
    zeilen = []
    for fn in ast.walk(baum):
        if not isinstance(fn, ast.FunctionDef) or (nur_funktion and fn.name != nur_funktion) or fn.name == "passt":
            continue
        zeilen += [n.lineno for n in ast.walk(fn) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in LIKE]
    return sorted(set(zeilen))


def test_buero_suche_nur_ueber_passt():
    assert like_ausser_passt((ROOT / "app/search.py").read_text(encoding="utf-8")) == []
    assert like_ausser_passt((ROOT / "app/contacts.py").read_text(encoding="utf-8"), "contact_search_filter") == []
    quelle = (ROOT / "app/search.py").read_text(encoding="utf-8")
    assert quelle.count("passt(") >= 59  # jede Spalte der Suche (1.9.359: 59 -- 58 Spalten der Büro- und Objektsuche, die Auftragssuche der Monteurin)


def test_der_waechter_erkennt_like():
    assert like_ausser_passt("def f(t): return X.a.ilike(t)") == [1]
    assert like_ausser_passt("def f(t): return passt(X.a, t)") == []


def _pruefen(db):
    from app.contacts import list_contacts
    from app.models import Contact, Customer, Project, Property
    from app.search import _search_customers, _search_projects, search_properties
    kunden = [Customer(name=n, last_name=n) for n in ("Müller Bau", "MÜLLER Probe", "Muller GmbH", "Straßenbau Ost", "Mahler")]
    db.add_all(kunden)
    db.flush()
    db.add(Property(customer_id=kunden[0].id, name="Halle Müllerstraße"))
    from sqlalchemy import select
    from app.models import ProjectPipelineColumn
    spalte = db.scalars(select(ProjectPipelineColumn).order_by(ProjectPipelineColumn.id)).first()
    db.add(Project(customer_id=kunden[1].id, name="Dach Ölberg", project_number="P-9001", pipeline_column_id=spalte.id))
    db.add_all([Contact(kind="person", last_name="Müllner"), Contact(kind="firma", company_name="ÖKO Dach")])
    db.commit()
    for suche in ("muller", "Müller", "MÜLLER", "MULLER"):
        assert sorted(c.name for c in _search_customers(db, suche, 10)[1]) == sorted(["Müller Bau", "MÜLLER Probe", "Muller GmbH"]), suche
    assert [c.name for c in _search_customers(db, "strasse", 10)[1]] == ["Straßenbau Ost"]
    assert [c.name for c in _search_customers(db, "STRASSE", 10)[1]] == ["Straßenbau Ost"]
    assert [p.name for p in search_properties(db, "mullerstrasse")] == ["Halle Müllerstraße"]
    assert [p.name for p in _search_projects(db, "olberg", 10)[1]] == ["Dach Ölberg"]
    assert [c["last_name"] for c in list_contacts(db, search="mullner")] == ["Müllner"]
    assert [c["company_name"] for c in list_contacts(db, search="oko")] == ["ÖKO Dach"]
    assert _search_customers(db, "a\\b", 10)[1] == []  # Zeichen weiter wörtlich


def test_suche_wie_die_sortierung_unter_sqlite(db_session):
    _pruefen(db_session)


def test_suche_wie_die_sortierung_unter_postgresql():
    from tests.befund_vor_echtbetrieb import pg_sitzung
    with pg_sitzung("suche_telefonbuch") as db:
        _pruefen(db)
