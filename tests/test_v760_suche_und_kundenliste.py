"""Version 1.9.360 -- Aufgaben, Material und Änderungshistorie suchen wie die Büro-Suche; die Kundenliste zeigt „Nachname, Vorname“ (Runde V3, Punkt 0).

F3 (Antwort Tobias 18.11.2026): die Filter von Aufgaben (Titel), Material (Name, Artikelnummer) und Änderungshistorie („Wer“) vergleichen wie die
Büro-Suche seit 1.9.359 über telefonbuch() (app/suchmuster.py::passt()) -- „muller“ findet „MÜLLER“, unter SQLite und PostgreSQL gleich.

Die Kundenliste sortiert seit 1.9.355 nach Nachname, dann Vorname; sie zeigte aber den ganzen Namen samt Anrede und Titel („Herr Bernd Abel“ unter A).
Jetzt zeigt sie Personen als „Nachname, Vorname“ (app/telefonbuch.py::listen_name(), in der Antwort als listen_name); Anrede und Titel nur in der Akte.
Eine Firma (Name im Nachnamen, ohne Vorname) steht unverändert da.

    Wächter    jedes like/ilike unter app/ steht in passt() -- außer INTERN (Muster ohne Text vom Benutzer, die genau vergleichen müssen)
    Verhalten  Aufgaben, Material, Historie: „muller“, „Müller“, „MÜLLER“ finden dasselbe -- unter SQLite und PostgreSQL
    Liste      listen_name je Fall; die Kundenliste zeigt listen_name in der Reihenfolge der Sortierung; die Seite zeigt listen_name
"""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
LIKE = {"like", "ilike", "notlike", "notilike"}

# datei::funktion -> Grund. Muster ohne Text vom Benutzer, die genau vergleichen müssen (Groß- und Kleinschreibung, Umlaute zählen).
INTERN = {
    "app/checklist_follow_ups.py::_close_lapsed_rows": "Schlüssel einer Folge als Präfix -- ein interner Schlüssel, genau",
    "app/kunde_verlauf.py::_aus_schnappschuss": "Kennung im JSON-Schnappschuss des Protokolls -- genau, kein Text vom Benutzer",
}


def _funktion(eltern, node):
    while node in eltern:
        node = eltern[node]
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return node
    return None


def like_ausser_passt(rel: str, quelle: str) -> list[str]:
    """datei::funktion je like/ilike außerhalb von passt()."""
    baum = ast.parse(quelle)
    eltern = {k: n for n in ast.walk(baum) for k in ast.iter_child_nodes(n)}
    out = []
    for n in ast.walk(baum):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in LIKE:
            fn = _funktion(eltern, n)
            if not (rel == "app/suchmuster.py" and fn is not None and fn.name == "passt"):
                out.append(f"{rel}::{fn.name if fn else '<modul>'}")
    return out


def _alle() -> list[str]:
    return [s for p in sorted(APP.rglob("*.py")) for s in like_ausser_passt(p.relative_to(ROOT).as_posix(), p.read_text(encoding="utf-8"))]


def test_jede_suche_ueber_passt():
    assert [s for s in _alle() if s not in INTERN] == [], "Text vom Benutzer über passt(spalte, text) (app/suchmuster.py) vergleichen"


def test_intern_stimmt_genau():
    assert sorted(set(_alle())) == sorted(INTERN), "INTERN nennt genau die Muster ohne Text vom Benutzer"


def test_der_waechter_erkennt_jede_form():
    assert like_ausser_passt("app/x.py", "def f(t): return X.a.ilike(enthaelt(t), escape=ESCAPE)") == ["app/x.py::f"]
    assert like_ausser_passt("app/x.py", "def f(t): return passt(X.a, t)") == []
    assert like_ausser_passt("app/suchmuster.py", "def passt(s, t): return telefonbuch(s).like(enthaelt(t), escape=ESCAPE)") == []
    assert like_ausser_passt("app/x.py", "def passt(s, t): return s.like(t)") == ["app/x.py::passt"]  # nur der Baustein selbst


# --- Verhalten: Aufgaben, Material, Änderungshistorie wie die Büro-Suche -------------------------------------------------------------------------

def _pruefen(db):
    from app.audit import audit_rows
    from app.materials import list_materials
    from app.models import AuditLog, Material, Task
    from app.tasks import list_tasks
    db.add_all([Task(title="Müller anrufen"), Task(title="MÜLLER Probe Ziegel"), Task(title="Muller Rinne"), Task(title="Straße sperren"),
                Task(title="Mahler")])
    db.add_all([Material(name="Rinnenhaken Müller", unit="Stk", purchase_price=1), Material(name="Schraube", article_number="MÜLLER-7", unit="Stk",
                purchase_price=1), Material(name="Ölbinder", unit="kg", purchase_price=1), Material(name="Mahler Kleber", unit="Stk", purchase_price=1)])
    db.add_all([AuditLog(actor_name="Erika Müller", action="geändert", entity_type="Probe"), AuditLog(actor_name="MÜLLER Probe", action="geändert",
                entity_type="Probe"), AuditLog(actor_name="Bernd Mahler", action="geändert", entity_type="Probe")])
    db.commit()
    for suche in ("muller", "Müller", "MÜLLER", "MULLER"):
        assert sorted(t["title"] for t in list_tasks(db, search=suche)) == sorted(["MÜLLER Probe Ziegel", "Muller Rinne", "Müller anrufen"]), suche
        assert sorted(m.name for m in list_materials(db, search=suche)) == sorted(["Rinnenhaken Müller", "Schraube"]), suche
        assert sorted(a.actor_name for a in audit_rows(db, actor=suche)) == sorted(["Erika Müller", "MÜLLER Probe"]), suche
    assert [t["title"] for t in list_tasks(db, search="STRASSE")] == ["Straße sperren"]
    assert [m.name for m in list_materials(db, search="olbinder")] == ["Ölbinder"]
    assert list_tasks(db, search="a\\b") == [] and list_materials(db, search="50%") == []  # Zeichen weiter wörtlich (1.9.358)


def test_aufgaben_material_historie_wie_die_buero_suche_unter_sqlite(db_session):
    _pruefen(db_session)


def test_aufgaben_material_historie_wie_die_buero_suche_unter_postgresql():
    from tests.befund_vor_echtbetrieb import pg_sitzung
    with pg_sitzung("suche_f3") as db:
        _pruefen(db)


# --- Kundenliste: „Nachname, Vorname“ ------------------------------------------------------------------------------------------------------------

def test_listen_name_je_fall():
    from app.telefonbuch import listen_name
    assert listen_name("Abel", "Bernd") == "Abel, Bernd"           # Person: Nachname, Vorname
    assert listen_name("Zimmerei Zander GmbH", None) == "Zimmerei Zander GmbH"  # Firma: unverändert
    assert listen_name("Müller", "") == "Müller"                   # ohne Vorname nur der Nachname (auch „Herr Müller“, „Firma Müller“)
    assert listen_name("  Probe ", "  Erika ") == "Probe, Erika"   # Rand weg
    assert listen_name(" ", None) == "" and listen_name("", "  ") == ""  # Altbestand ohne Namen: leer wie bisher
    assert listen_name("", "Bernd") == "Bernd"


# (Anrede, Titel, Vorname, Nachname) -- angelegt in dieser Reihenfolge
KUNDEN = [("Herr", "Dr.", "Bernd", "Zander"), ("Frau", None, "Anna", "Müller"), (None, None, None, "Bauhof GmbH"), ("Herr", None, "bernd", "müller"),
          ("Frau", None, "Erika", "Abel"), ("Firma", None, None, "Müller Dach"), ("Prof.", "Dr.", None, "Ölberg"), (None, None, None, "Müller GmbH")]
# nach Nachname, dann Vorname (1.9.355) -- und jetzt auch so angezeigt; Anrede und Titel nur in der Akte (name)
LISTE = [("Abel, Erika", "Frau Erika Abel"), ("Bauhof GmbH", "Bauhof GmbH"), ("Müller, Anna", "Frau Anna Müller"),
         ("müller, bernd", "Herr bernd müller"), ("Müller Dach", "Firma Müller Dach"), ("Müller GmbH", "Müller GmbH"), ("Ölberg", "Prof. Dr. Ölberg"),
         ("Zander, Bernd", "Herr Dr. Bernd Zander")]


def _kunden(db):
    from app.crm import compose_customer_name
    from app.models import Customer
    for anrede, titel, vorname, nachname in KUNDEN:
        db.add(Customer(name=compose_customer_name(anrede, titel, vorname, nachname), salutation=anrede, title=titel, first_name=vorname,
                        last_name=nachname))
        db.flush()
    db.commit()


def test_kundenliste_zeigt_nachname_vorname(threaded_db_session, router_test_client):
    from app.routers.customers import router
    db = threaded_db_session
    _kunden(db)
    client = router_test_client(db, router)
    liste = client.get("/api/customers").json()
    assert [(c["listen_name"], c["name"]) for c in liste] == LISTE
    einzeln = client.get(f"/api/customers/{liste[0]['id']}").json()
    assert einzeln["name"] == "Frau Erika Abel" and einzeln["salutation"] == "Frau"  # die Akte behält Anrede und Titel


def test_kundenliste_unter_postgresql():
    from app.routers.customers import list_customers
    from app.schemas import CustomerOut
    from tests.befund_vor_echtbetrieb import pg_sitzung
    with pg_sitzung("kundenliste_anzeige") as db:
        _kunden(db)
        assert [(CustomerOut.model_validate(c).listen_name, c.name) for c in list_customers(db=db, _role=None)] == LISTE


def test_die_seite_zeigt_den_listennamen():
    """Die Zeile der Kundenliste zeigt listen_name (nicht name) und findet beides."""
    from tests.vorlagen_js import seitentext
    text = seitentext("master_data.html")[0]
    zeile = next(z for z in text.splitlines() if "if(current==='customers')" in z)
    assert 'href="/customers/${x.id}">${esc(x.listen_name)}</a>' in zeile
    assert "textMatch(x.customer_number,x.listen_name,x.name," in zeile
