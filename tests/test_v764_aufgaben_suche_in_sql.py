"""Die Aufgaben-Quelle der Büro-Suche zählt und begrenzt in SQL (seit 1.9.364).

Bis 1.9.363 lud `app/search.py::_search_tasks()` über `list_tasks_for_user()` zweimal jeden Treffer (eigene, dann empfängerlose)
samt Mitarbeiter, Projekt und Checkliste, prüfte die Sichtbarkeit je Zeile in Python und zählte die Liste -- bei 20 000 Aufgaben
0,5–0,8 s je Suche (Messung Punkt 4, Runde V3). Seit 1.9.364 baut `app/tasks.py::aufgaben_abfrage()` die Abfrage samt Regel
(`sichtbar_in_sql()`, die SQL-Fassung von `task_visible_for_user()`); `list_tasks_for_user()` führt sie aus, die Suche zählt und
begrenzt sie über `_count_and_fetch()` wie jede andere Quelle.

Geprüft: die Regel in SQL ist dieselbe wie `task_visible_for_user()` für jede Kombination (SQLite und PostgreSQL); die Suche lädt
höchstens so viele Aufgaben, wie sie zeigt, mit gleich vielen Anfragen bei 5 und 50 Treffern, und nennt die ganze Zahl; neueste
zuerst; Mindestrolle und Zuweisung gelten auch dort; die Regel steht nur in app/tasks.py."""

import ast
from pathlib import Path

from sqlalchemy import event, select

from app.models import AppUser, Employee, Task
from app.permissions import ROLES, ROLE_ADMIN, ROLE_OFFICE_AUFTRAG, ROLE_OFFICE_FINANZEN, has_min_role
from app.search import OFFICE_SEARCH_RESULT_LIMIT, search_office
from app.tasks import aufgaben_abfrage, list_tasks_for_user, sichtbar_in_sql, task_visible_for_user

ROOT = Path(__file__).resolve().parent.parent


# --- 1. Die Regel in SQL ist dieselbe wie task_visible_for_user() ---

def _raster(db):
    """Je Zuweisung (keine, Erika, Otto) und Mindestrolle (keine, jede Rolle) eine Aufgabe."""
    erika = Employee(first_name="Erika", last_name="Raster")
    otto = Employee(first_name="Otto", last_name="Raster")
    db.add_all([erika, otto])
    db.flush()
    aufgaben = []
    for zugewiesen in (None, erika.id, otto.id):
        for rolle in (None, *ROLES):
            aufgaben.append(Task(title=f"Raster {zugewiesen} {rolle}", assigned_employee_id=zugewiesen, min_visible_role=rolle))
    db.add_all(aufgaben)
    db.commit()
    return erika, aufgaben


def _regel_gleich(db):
    erika, aufgaben = _raster(db)
    geprueft = 0
    for rolle in ROLES:
        for mitarbeiter in (None, erika.id):
            konto = AppUser(role=rolle, employee_id=mitarbeiter)
            erwartet = {t.id for t in aufgaben if task_visible_for_user(konto, t.assigned_employee_id, t.min_visible_role)}
            abfrage = aufgaben_abfrage(konto, include_archived=True, mit_eingang=True)
            if not has_min_role(konto, ROLE_OFFICE_AUFTRAG):
                assert abfrage is None and erwartet == set(), (rolle, mitarbeiter)
                continue
            in_sql = set(db.scalars(select(Task.id).where(sichtbar_in_sql(konto))))
            assert in_sql == erwartet, (rolle, mitarbeiter, sorted(in_sql ^ erwartet))
            assert set(db.scalars(abfrage.with_only_columns(Task.id))) == erwartet, (rolle, mitarbeiter)
            geprueft += 1
    assert geprueft == 6  # drei Büro-Rollen, je mit und ohne Mitarbeiter


def test_regel_in_sql_wie_task_visible_for_user_unter_sqlite(db_session):
    _regel_gleich(db_session)


def test_regel_in_sql_wie_task_visible_for_user_unter_postgresql():
    from tests.befund_vor_echtbetrieb import pg_sitzung
    with pg_sitzung("aufgaben_regel") as db:
        _regel_gleich(db)


# --- 2. Zählen und begrenzen in SQL ---

class _Zaehler:
    """Anweisungen an die Datenbank und geladene Aufgaben während einer Suche."""

    def __init__(self, db):
        self.db, self.anweisungen, self.aufgaben = db, 0, 0

    def _anweisung(self, *args):
        self.anweisungen += 1

    def _geladen(self, session, objekt):
        if isinstance(objekt, Task):
            self.aufgaben += 1

    def suchen(self, wort):
        self.db.expunge_all()  # sonst liegen die Aufgaben schon in der Sitzung und zählen nicht als geladen
        self.anweisungen = self.aufgaben = 0
        engine = self.db.get_bind()
        event.listen(engine, "before_cursor_execute", self._anweisung)
        event.listen(self.db, "loaded_as_persistent", self._geladen)
        try:
            return search_office(self.db, ROLE_ADMIN, wort, types=frozenset({"tasks"}))
        finally:
            event.remove(engine, "before_cursor_execute", self._anweisung)
            event.remove(self.db, "loaded_as_persistent", self._geladen)


def test_suche_zaehlt_und_begrenzt_in_sql(db_session):
    db = db_session
    viele = [Task(title=f"Zaehlprobe Viele {i}") for i in range(50)]
    wenige = [Task(title=f"Zaehlprobe Wenige {i}") for i in range(5)]
    db.add_all(viele + wenige + [Task(title="Etwas anderes")])
    db.commit()
    neueste = sorted((t.id for t in viele), reverse=True)[:20]
    zaehler = _Zaehler(db)

    gruppen = zaehler.suchen("Zaehlprobe Viele")
    anweisungen_viele, geladen_viele = zaehler.anweisungen, zaehler.aufgaben
    assert len(gruppen) == 1
    assert gruppen[0]["total"] == 50, "die Zahl nennt jeden Treffer, nicht nur die gezeigten"
    treffer = [h["id"] for h in gruppen[0]["hits"]]
    assert len(treffer) == OFFICE_SEARCH_RESULT_LIMIT == 20
    assert treffer == neueste, "neueste zuerst"
    assert geladen_viele <= OFFICE_SEARCH_RESULT_LIMIT, f"{geladen_viele} Aufgaben geladen, gezeigt werden höchstens 20"

    gruppen = zaehler.suchen("Zaehlprobe Wenige")
    assert gruppen[0]["total"] == 5 and len(gruppen[0]["hits"]) == 5
    assert zaehler.anweisungen == anweisungen_viele, (
        f"5 Treffer: {zaehler.anweisungen} Anweisungen, 50 Treffer: {anweisungen_viele} -- die Zahl hängt an den Treffern"
    )


# --- 3. Zuweisung und Mindestrolle gelten auch in der Suche ---

def _sichtbarkeit_in_der_suche(db):
    erika = Employee(first_name="Erika", last_name="Suche")
    otto = Employee(first_name="Otto", last_name="Suche")
    db.add_all([erika, otto])
    db.flush()
    eigene = Task(title="Sichtprobe eigene", assigned_employee_id=erika.id)
    fremde = Task(title="Sichtprobe fremde", assigned_employee_id=otto.id)
    eingang = Task(title="Sichtprobe Eingang")
    eingang_finanzen = Task(title="Sichtprobe Eingang Finanzen", min_visible_role=ROLE_OFFICE_FINANZEN)
    eigene_finanzen = Task(title="Sichtprobe eigene Finanzen", assigned_employee_id=erika.id, min_visible_role=ROLE_OFFICE_FINANZEN)
    db.add_all([eigene, fremde, eingang, eingang_finanzen, eigene_finanzen])
    db.commit()

    def gefunden(rolle, mitarbeiter):
        gruppen = search_office(db, rolle, "Sichtprobe", types=frozenset({"tasks"}), employee_id=mitarbeiter)
        if not gruppen:
            return 0, set()
        return gruppen[0]["total"], {h["id"] for h in gruppen[0]["hits"]}

    assert gefunden(ROLE_OFFICE_AUFTRAG, erika.id) == (2, {eigene.id, eingang.id})
    assert gefunden(ROLE_OFFICE_FINANZEN, erika.id) == (4, {eigene.id, eingang.id, eingang_finanzen.id, eigene_finanzen.id})
    assert gefunden(ROLE_OFFICE_AUFTRAG, None) == (1, {eingang.id})
    assert gefunden(ROLE_ADMIN, None) == (5, {eigene.id, fremde.id, eingang.id, eingang_finanzen.id, eigene_finanzen.id})
    # dieselbe Menge wie die Liste (zwei Reiter: eigene, Eingang)
    konto = AppUser(role=ROLE_OFFICE_AUFTRAG, employee_id=erika.id)
    liste = {t["id"] for t in list_tasks_for_user(db, konto, search="Sichtprobe")}
    liste |= {t["id"] for t in list_tasks_for_user(db, konto, unassigned_only=True, search="Sichtprobe")}
    assert liste == {eigene.id, eingang.id}


def test_zuweisung_und_mindestrolle_in_der_suche_unter_sqlite(db_session):
    _sichtbarkeit_in_der_suche(db_session)


def test_zuweisung_und_mindestrolle_in_der_suche_unter_postgresql():
    from tests.befund_vor_echtbetrieb import pg_sitzung
    with pg_sitzung("aufgaben_suche") as db:
        _sichtbarkeit_in_der_suche(db)


# --- 4. Die Regel steht nur in app/tasks.py ---

def _funktion(baum, name):
    return next(n for n in ast.walk(baum) if isinstance(n, ast.FunctionDef) and n.name == name)


def _aufrufe(knoten) -> set[str]:
    namen = set()
    for n in ast.walk(knoten):
        if isinstance(n, ast.Call):
            f = n.func
            namen.add(f.id if isinstance(f, ast.Name) else getattr(f, "attr", ""))
    return namen


def regel_ausserhalb(quelle_suche: str, quelle_aufgaben: str) -> list[str]:
    """Was die Regel an der Abfrage vorbei prüft: die Suche nimmt aufgaben_abfrage() und fasst Zuweisung, Mindestrolle und
    die Einzelprüfung nicht selbst an; list_tasks_for_user() nimmt aufgaben_abfrage(), diese sichtbar_in_sql()."""
    funde = []
    suche = ast.parse(quelle_suche)
    if "aufgaben_abfrage" not in _aufrufe(_funktion(suche, "_search_tasks")):
        funde.append("search.py::_search_tasks ohne aufgaben_abfrage()")
    for n in ast.walk(suche):
        if isinstance(n, ast.Attribute) and n.attr in ("assigned_employee_id", "min_visible_role"):
            funde.append(f"search.py:{n.lineno} {n.attr}")
        if isinstance(n, ast.Name) and n.id in ("task_visible_for_user", "sichtbar_in_sql", "list_tasks_for_user", "has_min_role"):
            funde.append(f"search.py:{n.lineno} {n.id}")
    aufgaben = ast.parse(quelle_aufgaben)
    liste = _aufrufe(_funktion(aufgaben, "list_tasks_for_user"))
    if "aufgaben_abfrage" not in liste or {"task_visible_for_user", "list_tasks"} & liste:
        funde.append("tasks.py::list_tasks_for_user nicht über aufgaben_abfrage()")
    if "sichtbar_in_sql" not in _aufrufe(_funktion(aufgaben, "aufgaben_abfrage")):
        funde.append("tasks.py::aufgaben_abfrage ohne sichtbar_in_sql()")
    return funde


def test_die_regel_steht_nur_in_app_tasks():
    funde = regel_ausserhalb((ROOT / "app" / "search.py").read_text(encoding="utf-8"),
                             (ROOT / "app" / "tasks.py").read_text(encoding="utf-8"))
    assert funde == []


def test_der_waechter_erkennt_jede_form():
    gut_suche = "def _search_tasks(db, t, n, r, e):\n    return _count_and_fetch(db, aufgaben_abfrage(AppUser(role=r)), Task.id.desc(), n)\n"
    gut_aufgaben = ("def aufgaben_abfrage(u):\n    return select(Task).where(sichtbar_in_sql(u))\n"
                    "def list_tasks_for_user(db, u):\n    return _als_liste(db, aufgaben_abfrage(u))\n")
    assert regel_ausserhalb(gut_suche, gut_aufgaben) == []
    assert regel_ausserhalb(gut_suche.replace("Task.id.desc()", "Task.assigned_employee_id"), gut_aufgaben)
    assert regel_ausserhalb("def _search_tasks(db, t, n, r, e):\n    return list_tasks_for_user(db, AppUser(role=r))\n", gut_aufgaben)
    assert regel_ausserhalb(gut_suche, gut_aufgaben.replace("_als_liste(db, aufgaben_abfrage(u))",
                                                            "[r for r in list_tasks(db) if task_visible_for_user(u, 1, 2)]"))
    assert regel_ausserhalb(gut_suche, gut_aufgaben.replace("sichtbar_in_sql(u)", "Task.id > 0"))
