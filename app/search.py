"""Geteilte Suchkernfunktion (siehe CLAUDE.md "Dateiablage je Objekt" -> "Suche als Einstieg" UND
"Büro-Suche"). Zwei Suchen leben hier nebeneinander, wie beim Anlegen der Datei versprochen (siehe
1.3.64-Moduldocstring, unten unverändert erhalten): die Monteurs-Suche (nur Objekte,
search_properties_for_field()) UND, seit 1.3.66, die Büro-Suche (Etappe 1: Registry, Kern,
Rollensicherheit -- die Oberfläche folgt erst in Etappe 2).

=== Monteurs-Suche (seit 1.3.64, unverändert) ===

Zwei Schichten, bewusst getrennt:

1. search_properties() -- reine Datenbeschaffung, KEINE Rollenprüfung/-reduktion. Sucht Property
   nach Name/Straße/PLZ/Ort sowie dem Namen des zugehörigen Kunden (Join), unabhängig davon, wer
   aufruft. Gibt volle Property-ORM-Objekte zurück -- eine künftige, reichhaltigere Büro-Suche
   liest daraus, welche Felder sie zusätzlich zeigen will, ohne diese Funktion anzufassen.
2. field_safe_property_search_results() -- reduziert JEDES Ergebnis auf die für `field`
   zulässigen, harmlosen Felder (id, name, city, customer_name -- seit 1.3.65 mit Kundenname,
   siehe dort: ein Monteur, der zum Objekt fährt, kennt den Kunden ohnehin, das Feld ist nicht
   sensibel; weiterhin NICHT enthalten: Kundennummer, interne Notizen, volle Adresse über den
   Ort hinaus, alles Finanzielle).

search_properties_for_field() kombiniert beide zu der EINEN Funktion, die ein Monteurs-Endpunkt
aufrufen darf. WICHTIG für jeden künftigen, auch für `field` erreichbaren Such-Endpunkt (auch
einen gemeinsamen Büro+Monteur-Endpunkt): bei role==ROLE_FIELD MUSS er
search_properties_for_field() aufrufen, NIE search_properties() direkt zurückgeben -- die
Feldbegrenzung sitzt serverseitig, an der Rolle, nicht an der URL/dem Aufrufer.

=== Büro-Suche, Etappe 1 (seit 1.3.66) ===

Der KERN aus 1.3.64 wird um 16 weitere Gruppe-A-Datensatzarten ERWEITERT, nicht ersetzt --
search_properties() bleibt unverändert die EINE Objektsuche, die "properties"-Quelle unten ruft
sie direkt auf. Architektur, entlang der vier Entscheidungen aus dem Befund:

- **Rollen (Entscheidung 1)**: JEDE der (seit 1.4.2: 18) Quellen trägt allowed_roles={ROLE_ADMIN, ROLE_OFFICE}
  -- die Grenze verläuft zwischen Büro und Monteur, nicht zwischen Admin und Büro. Kalkulations-
  grundlagen sind keine Gruppe-A-Entität (Singleton-Settings-Zeile, nicht durchsuchbar);
  Einkaufspreise/Vergütung sind bereits an anderer Stelle Büro+Admin-sichtbar (Material-/
  Mitarbeiter-Stammdaten, 1.3.52), eine Einschränkung nur hier würde nichts schützen. Der
  eigentliche Schutz: KEIN row_fn liefert je ein Preis-/Lohn-/Einkaufsfeld, unabhängig von der
  Rolle -- reine Suchtreffer-Kurzform (id/title/subtitle/url), keine Kalkulationsdaten.
- **ILIKE statt Volltextsuche (Entscheidung 2)**: empirisch geprüft (siehe CLAUDE.md
  "Büro-Suche" für die Zahlen) -- bei 472 Zeilen über alle 17 Tabellen liegt jede der
  repräsentativen, gejointen ILIKE-Abfragen bei ~0.03ms. Schwelle für einen Wechsel zu
  PostgreSQL pg_trgm/tsvector bzw. SQLite FTS5: siehe CLAUDE.md, dort konkret benannt, damit ein
  künftiger Durchgang es nicht neu herleiten muss.
- **Snapshot UND live (Entscheidung 3)**: "orders"/"invoices" durchsuchen IMMER beide -- die
  eingefrorene Schnappschuss-Spalte (Order.customer_name/Invoice.customer_name) UND die live
  Customer.name über den Projekt-Join. Wer nach der alten Schreibweise sucht, findet die alte
  Rechnung; wer nach der neuen sucht, findet den heutigen Kunden -- beide unabhängig voneinander,
  nie nur einer der beiden Wege (siehe tests/test_v270_office_search.py für den Belegtest).
- **Ergebnisseite-Begrenzung (Entscheidung 4)**: jede Quelle liefert ihre REALE Trefferzahl
  (total) UND eine auf limit_per_type (Standard 20) gekappte Liste -- die Oberfläche (Etappe 2)
  zeigt daraus "weitere anzeigen" statt Seitenzahlen.

**Dritte, unabhängige Achse: der Modul-Umschalter (app/modules.py).** Vier Quellen
(tasks/service_reports/findings/maintenance_contracts) hängen an einem abschaltbaren Modul --
SearchSource.module_key trägt dafür den jeweiligen module_key, search_office() prüft
is_module_enabled() für jede Quelle mit gesetztem module_key zusätzlich zur Rolle. Das ist KEINE
vom Nutzer ausdrücklich verlangte Prüfung, sondern folgt aus der bereits bestehenden Regel
("API-Endpunkte müssen den Zustand selbst prüfen, sonst bleibt die Funktion über die API
erreichbar, obwohl die Oberfläche sie versteckt", siehe CLAUDE.md "Modul-Umschalter").

**search_office() prüft MIN_QUERY_LENGTH ZENTRAL, EINMAL, bevor irgendeine der (seit 1.4.2: 18)
Quellfunktionen aufgerufen wird** -- keine der Funktionen prüft es erneut, das ist
beabsichtigt, kein Versehen.

**Registry-Vollständigkeit ist mechanisch erzwungen** (Muster: Regel 11/require_role() -- eine
Registry ohne erzwungene Vollständigkeit ist nur ein Vorschlag, keine Absicherung):
tests/test_v270_office_search.py::EXPECTED_OFFICE_SEARCH_KEYS vergleicht die tatsächlich
registrierten Schlüssel gegen die erwarteten -- eine vergessene oder falsch deklarierte
Datensatzart fällt beim nächsten Testlauf auf, nicht erst durch Zufall.

=== Nachtrag (seit 1.4.2, Punkt 3): Betriebsmittel ===

Achtzehnte Quelle -- "operational_assets", dieselben drei Achsen wie jede andere: Rolle
(OFFICE_ROLES), Modul (module_key="betriebsmittel", eine vierte, unabhängige Achse, die dieses
Feature ohnehin schon kennt), keine Preis-/Kostenfelder im row_fn (`article_number` fließt nur
als Suchkriterium ein, nie in die Antwort). Sucht Bezeichnung/Art/Hersteller/Modell/
Kennzeichen/Artikelnummer -- bei einem ressourcenverknüpften Asset (resource_id gesetzt) sind
die eigenen Identitätsfelder auf OperationalAsset selbst NULL (siehe app/operational_assets.py-
Moduldocstring), deshalb outerjoin auf OperationalResource UND row_fn über
resolve_asset_identity() -- derselbe Helfer, den auch die Betriebsmittelseite selbst nutzt,
kann also nie einen anderen Namen zeigen.

=== Nachtrag (seit 1.4.4): Aufgaben-Sichtbarkeit in der Büro-Suche ===

Gemeldete Lücke aus 1.4.3: _search_tasks() hatte keine Mitarbeiterfilterung -- ein Büro-Konto
fand darüber auch die persönlich zugewiesene Aufgabe eines Kollegen, genau die Grenze, die
list_tasks_for_user() (GET /api/tasks, Dashboard) seit 1.4.3 zieht. Behoben durch tatsächliche
Wiederverwendung von list_tasks_for_user() (app/tasks.py) statt einer zweiten, hier nachgebauten
Kopie der Regel -- search_office() bekommt dafür einen neuen, optionalen `employee_id`-Parameter
(nur für die "tasks"-Quelle relevant) und dispatcht "tasks" als einzigen Sonderfall mit
zusätzlichem role/employee_id-Argument, siehe _search_tasks()/search_office() für die Details."""

from dataclasses import dataclass
from typing import Callable

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from .materials import list_materials
from .modules import is_module_enabled
from .models import (
    AppUser, Customer, CustomerProfile, Employee, Finding, Inquiry, Invoice, MaintenanceContract,
    Material, OperationalAsset, OperationalResource, Order, Project, Property, Quote, Reminder,
    RoofArea, Service, ServiceReport, Supplier,
)
from .operational_assets import resolve_asset_identity
from .permissions import ROLE_ADMIN, ROLE_OFFICE
from .tasks import list_tasks_for_user

MIN_QUERY_LENGTH = 2
SEARCH_RESULT_LIMIT = 10
OFFICE_SEARCH_RESULT_LIMIT = 20

OFFICE_ROLES = frozenset({ROLE_ADMIN, ROLE_OFFICE})


def _property_search_base_stmt(term: str):
    """Reiner WHERE-/JOIN-Aufbau, geteilt von search_properties() (Monteurs-Suche) und
    _search_properties_office() (Büro-Suche, Quelle "properties") -- EIN Filter, zwei Aufrufer,
    kann nicht auseinanderlaufen (Muster: die Lehre aus build_customer_and_meta_block(), siehe
    CLAUDE.md "Kopfbereich"). Trägt bewusst KEINE .options()/.order_by()/.limit() -- die setzt
    jeder Aufrufer selbst (search_properties() für sich, _count_and_fetch() für die Büro-Suche)."""
    pattern = f"%{term}%"
    return (
        select(Property)
        .join(Customer, Property.customer_id == Customer.id)
        .where(or_(
            Property.name.ilike(pattern),
            Property.street.ilike(pattern),
            Property.postal_code.ilike(pattern),
            Property.city.ilike(pattern),
            Customer.name.ilike(pattern),
        ))
    )


def search_properties(db: Session, query: str, *, limit: int = SEARCH_RESULT_LIMIT) -> list[Property]:
    """Kernfunktion (siehe Moduldocstring) -- sucht Objekte nach Name, Straße, PLZ, Ort und dem
    Namen des zugehörigen Kunden. Eine zu kurze Anfrage (< MIN_QUERY_LENGTH) liefert bewusst
    keine Treffer statt der ersten N Objekte der Datenbank -- eine Vorschlagsliste ohne
    brauchbaren Suchbegriff wäre irreführend, nicht hilfreich."""
    term = (query or "").strip()
    if len(term) < MIN_QUERY_LENGTH:
        return []
    stmt = (
        _property_search_base_stmt(term)
        .options(selectinload(Property.customer))
        .order_by(Property.name)
        .limit(limit)
    )
    return list(db.scalars(stmt).all())


def field_safe_property_search_results(properties: list[Property]) -> list[dict]:
    """Schicht 2 (siehe Moduldocstring) -- reduziert auf id/name/city/customer_name, die einzigen
    Felder, die die Vorschlagsliste zeigen darf. Kundenname seit 1.3.65 dabei (nicht sensibel --
    ein Monteur, der zum Objekt fährt, kennt den Kunden ohnehin, und mehrere Objekte desselben
    Kunden sind ohne ihn kaum zu unterscheiden) -- weiterhin keine Kundennummer, keine interne
    Notiz, keine volle Adresse über den Ort hinaus, nichts Finanzielles. `selectinload()` in
    search_properties() lädt `Property.customer` bereits mit, dieser Zugriff löst also keine
    zusätzliche Abfrage je Zeile aus."""
    return [
        {"id": p.id, "name": p.name, "city": p.city, "customer_name": p.customer.name}
        for p in properties
    ]


def search_properties_for_field(db: Session, query: str, *, limit: int = SEARCH_RESULT_LIMIT) -> list[dict]:
    """Die EINE Funktion, die ein für `field` erreichbarer Such-Endpunkt aufrufen darf --
    kombiniert Schicht 1 (Objektbegrenzung: ausschließlich Property, nie Kunde/Auftrag/Rechnung/
    Angebot) mit Schicht 2 (Feldbegrenzung). Siehe Moduldocstring, warum künftiger Code diese
    Reduktion nicht selbst nachbauen darf."""
    return field_safe_property_search_results(search_properties(db, query, limit=limit))


# --------------------------------------------------------------------------------------------
# Büro-Suche, Etappe 1: Registry + Dispatcher (siehe Moduldocstring oben)
# --------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class SearchSource:
    """Eine Gruppe-A-Datensatzart der Büro-Suche -- analog im Geist zu require_role() (kein
    Feld mit einem "harmlosen" impliziten Default außer module_key, das für die meisten Quellen
    schlicht nicht gilt): key/label/allowed_roles/query_fn/row_fn müssen für jede Quelle bewusst
    angegeben werden."""

    key: str
    label: str
    allowed_roles: frozenset[str]
    # (Session, str, int) -> (total, rows) für jede Quelle außer "tasks" -- deren query_fn
    # (_search_tasks()) braucht zusätzlich role/employee_id, siehe search_office()s Dispatch-
    # Sonderfall dafür. Kein eigenes Feld dafür in dieser Dataclass, um die 17 übrigen Quellen
    # nicht mit einer ungenutzten Signaturerweiterung zu belasten (siehe _search_tasks()-Docstring).
    query_fn: Callable[..., tuple[int, list]]
    row_fn: Callable[[object], dict]
    module_key: str | None = None


def _count_and_fetch(db: Session, stmt, order_by, limit: int, *, options: tuple = ()) -> tuple[int, list]:
    """Gemeinsamer Helfer für (fast) jede Büro-Suchquelle -- EIN gefilterter Basis-`stmt`
    (JOIN+WHERE, ohne .options()/.order_by()/.limit()), zwei Verwendungen: eine echte
    COUNT(*)-Abfrage für die Gesamttrefferzahl (Entscheidung 4) und eine gekappte, geordnete
    Liste für die Anzeige -- beide aus demselben Filter, können dadurch nie auseinanderlaufen
    (Muster: die Lehre aus build_customer_and_meta_block()s historischer Divergenz, siehe
    CLAUDE.md "Kopfbereich"). `options` wird bewusst NUR auf die Fetch-Abfrage angewendet --
    Eager-Load-Strategien sind für eine reine Zählung irrelevant und unnötig."""
    count = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    fetch_stmt = stmt
    for option in options:
        fetch_stmt = fetch_stmt.options(option)
    rows = db.scalars(fetch_stmt.order_by(order_by).limit(limit)).all()
    return count, rows


# --- Kunden ---

def _search_customers(db: Session, term: str, limit: int) -> tuple[int, list]:
    pattern = f"%{term}%"
    stmt = (
        select(Customer)
        .outerjoin(CustomerProfile, Customer.id == CustomerProfile.customer_id)
        .where(or_(Customer.name.ilike(pattern), CustomerProfile.customer_number.ilike(pattern)))
    )
    return _count_and_fetch(db, stmt, Customer.name, limit)


def _customer_row(c: Customer) -> dict:
    return {"id": c.id, "title": c.name, "subtitle": c.city, "url": f"/customers/{c.id}"}


# --- Objekte (nutzt denselben Filter wie die Monteurs-Suche) ---

def _search_properties_office(db: Session, term: str, limit: int) -> tuple[int, list]:
    return _count_and_fetch(
        db, _property_search_base_stmt(term), Property.name, limit,
        options=(selectinload(Property.customer),),
    )


def _property_office_row(p: Property) -> dict:
    sub = " · ".join(x for x in [p.customer.name, p.city] if x)
    return {"id": p.id, "title": p.name, "subtitle": sub or None, "url": f"/properties/{p.id}"}


# --- Dachflächen ---

def _search_roof_areas(db: Session, term: str, limit: int) -> tuple[int, list]:
    pattern = f"%{term}%"
    stmt = select(RoofArea).where(RoofArea.name.ilike(pattern))
    return _count_and_fetch(db, stmt, RoofArea.name, limit, options=(selectinload(RoofArea.property),))


def _roof_area_row(r: RoofArea) -> dict:
    return {"id": r.id, "title": r.name, "subtitle": r.property.name if r.property else None, "url": f"/roof-areas/{r.id}"}


# --- Projekte ---

def _search_projects(db: Session, term: str, limit: int) -> tuple[int, list]:
    pattern = f"%{term}%"
    stmt = (
        select(Project)
        .join(Customer, Project.customer_id == Customer.id)
        .where(or_(
            Project.project_number.ilike(pattern),
            Project.name.ilike(pattern),
            Customer.name.ilike(pattern),
        ))
    )
    return _count_and_fetch(db, stmt, Project.id.desc(), limit, options=(selectinload(Project.customer),))


def _project_row(p: Project) -> dict:
    return {"id": p.id, "title": f"{p.project_number} · {p.name}", "subtitle": p.customer.name, "url": f"/projects/{p.id}"}


# --- Angebote ---

def _search_quotes(db: Session, term: str, limit: int) -> tuple[int, list]:
    pattern = f"%{term}%"
    stmt = (
        select(Quote)
        .join(Project, Quote.project_id == Project.id)
        .join(Customer, Project.customer_id == Customer.id)
        .where(or_(
            Quote.quote_number.ilike(pattern),
            Quote.title.ilike(pattern),
            Customer.name.ilike(pattern),
        ))
    )
    return _count_and_fetch(
        db, stmt, Quote.id.desc(), limit,
        options=(selectinload(Quote.project).selectinload(Project.customer),),
    )


def _quote_row(q: Quote) -> dict:
    return {"id": q.id, "title": f"{q.quote_number} · {q.title}", "subtitle": q.project.customer.name, "url": f"/quotes/{q.id}/edit"}


# --- Aufträge (Entscheidung 3: Snapshot UND live durchsucht) ---

def _search_orders(db: Session, term: str, limit: int) -> tuple[int, list]:
    pattern = f"%{term}%"
    stmt = (
        select(Order)
        .join(Project, Order.project_id == Project.id)
        .join(Customer, Project.customer_id == Customer.id)
        .where(or_(
            Order.order_number.ilike(pattern),
            Order.title.ilike(pattern),
            Order.customer_name.ilike(pattern),  # eingefroren
            Customer.name.ilike(pattern),  # live
        ))
    )
    return _count_and_fetch(db, stmt, Order.id.desc(), limit)


def _order_row(o: Order) -> dict:
    return {"id": o.id, "title": f"{o.order_number} · {o.title}", "subtitle": o.customer_name, "url": f"/orders/{o.id}"}


# --- Rechnungen (Entscheidung 3: Snapshot UND live durchsucht, DER konkrete Fund) ---

def _search_invoices(db: Session, term: str, limit: int) -> tuple[int, list]:
    pattern = f"%{term}%"
    stmt = (
        select(Invoice)
        .join(Order, Invoice.order_id == Order.id)
        .join(Project, Order.project_id == Project.id)
        .join(Customer, Project.customer_id == Customer.id)
        .where(or_(
            Invoice.invoice_number.ilike(pattern),
            Invoice.customer_name.ilike(pattern),  # eingefroren -- findet die alte Rechnung
            Customer.name.ilike(pattern),  # live -- findet den heutigen Kunden
        ))
    )
    return _count_and_fetch(db, stmt, Invoice.id.desc(), limit)


def _invoice_row(i: Invoice) -> dict:
    return {"id": i.id, "title": i.invoice_number or "Entwurf", "subtitle": i.customer_name, "url": f"/invoices/{i.id}"}


# --- Mahnungen ---

def _search_reminders(db: Session, term: str, limit: int) -> tuple[int, list]:
    pattern = f"%{term}%"
    stmt = (
        select(Reminder)
        .join(Invoice, Reminder.invoice_id == Invoice.id)
        .where(or_(
            Reminder.reminder_number.ilike(pattern),
            Invoice.customer_name.ilike(pattern),
        ))
    )
    return _count_and_fetch(db, stmt, Reminder.id.desc(), limit, options=(selectinload(Reminder.invoice),))


def _reminder_row(r: Reminder) -> dict:
    return {
        "id": r.id, "title": r.reminder_number or f"Mahnung Stufe {r.level}",
        "subtitle": r.invoice.customer_name, "url": f"/invoices/{r.invoice_id}",
    }


# --- Anfragen ---

def _search_inquiries(db: Session, term: str, limit: int) -> tuple[int, list]:
    pattern = f"%{term}%"
    stmt = (
        select(Inquiry)
        .join(Customer, Inquiry.customer_id == Customer.id)
        .where(or_(
            Inquiry.inquiry_number.ilike(pattern),
            Inquiry.title.ilike(pattern),
            Customer.name.ilike(pattern),
        ))
    )
    return _count_and_fetch(db, stmt, Inquiry.id.desc(), limit, options=(selectinload(Inquiry.customer),))


def _inquiry_row(i: Inquiry) -> dict:
    return {"id": i.id, "title": f"{i.inquiry_number} · {i.title}", "subtitle": i.customer.name, "url": f"/inquiries?inquiry={i.id}"}


# --- Aufgaben (Modul "aufgabenmanagement") -- EINZIGE Quelle, deren Sichtbarkeit vom Aufrufer
# selbst abhängt (Büro sieht nur die eigenen UND die empfängerlosen Aufgaben, nie die eines
# Kollegen -- exakt die Regel, die list_tasks_for_user()/GET /api/tasks seit 1.4.3 durchsetzt,
# siehe CLAUDE.md "Änderung am Aufgabenmodul"). Der ursprüngliche Fund, der zu dieser Ergänzung
# führte: _search_tasks() hatte KEINE Mitarbeiterfilterung, ein Büro-Konto fand darüber auch die
# persönlich zugewiesene Aufgabe eines Kollegen -- genau die Grenze, die 1.4.3 in der Aufgaben-
# liste gezogen hatte, stand in der Suche wieder offen. ---

def _search_tasks(db: Session, term: str, limit: int, role: str, employee_id: int | None) -> tuple[int, list]:
    """Nutzt list_tasks_for_user() (app/tasks.py) -- DIESELBE Filterfunktion wie GET /api/tasks/
    das Dashboard, keine zweite, hier nachgebaute Kopie der Regel (genau das war die Ursache der
    ursprünglichen Lücke: zwei Stellen, eine Regel, nur an einer gepflegt). Ein transientes,
    nie persistiertes AppUser-Objekt trägt Rolle/employee_id in list_tasks_for_user() hinein --
    dieselbe Technik wie router_test_client()s Test-Identität, kein neuer Mechanismus.

    Zwei Aufrufe statt einem: list_tasks_for_user() liefert für die getrennten Board-Tabs
    ("Meine Aufgaben"/"Offene Büro-Aufgaben") bewusst ENTWEDER die eigenen ODER die
    empfängerlosen Aufgaben (unassigned_only ist ein Entweder-Oder-Schalter) -- die Suche
    braucht dagegen beide KOMBINIERT in einer einzigen Trefferliste. Ein Büro-Konto ohne
    Mitarbeiterverknüpfung kann "eigene" nicht bestimmen (ValueError, siehe dort) -- das wird
    hier abgefangen, damit wenigstens die empfängerlosen weiterhin gefunden werden, statt die
    ganze Suche für dieses Konto leer zu lassen (dieselbe Großzügigkeit wie beim direkten Sehen
    des gemeinsamen Eingangs). Ein Monteur erreicht diese Funktion ohnehin nie -- search_office()
    filtert "tasks" bereits über allowed_roles aus, list_tasks_for_user() verweigert zusätzlich
    (leere Liste) als zweite, unabhängige Absicherung."""
    user = AppUser(role=role, employee_id=employee_id)
    try:
        own = list_tasks_for_user(db, user, include_archived=True, search=term)
    except ValueError:
        own = []
    unassigned = list_tasks_for_user(db, user, include_archived=True, unassigned_only=True, search=term)
    seen_ids = {t["id"] for t in own}
    combined = own + [t for t in unassigned if t["id"] not in seen_ids]
    combined.sort(key=lambda t: t["id"], reverse=True)
    return len(combined), combined[:limit]


def _task_row(t: dict) -> dict:
    return {"id": t["id"], "title": t["title"], "subtitle": t["project_name"], "url": f"/tasks?task={t['id']}"}


# --- Mitarbeiter ---

def _search_employees(db: Session, term: str, limit: int) -> tuple[int, list]:
    pattern = f"%{term}%"
    stmt = select(Employee).where(or_(
        Employee.first_name.ilike(pattern),
        Employee.last_name.ilike(pattern),
        Employee.employee_number.ilike(pattern),
    ))
    return _count_and_fetch(db, stmt, Employee.last_name, limit)


def _employee_row(e: Employee) -> dict:
    return {"id": e.id, "title": f"{e.first_name} {e.last_name}", "subtitle": e.employee_number, "url": f"/master-data/employees/{e.id}/edit"}


# --- Einsatzberichte (Modul "wartungen") ---

def _search_service_reports(db: Session, term: str, limit: int) -> tuple[int, list]:
    pattern = f"%{term}%"
    stmt = (
        select(ServiceReport)
        .join(Order, ServiceReport.order_id == Order.id)
        .where(or_(
            Order.order_number.ilike(pattern),
            Order.customer_name.ilike(pattern),
            ServiceReport.description.ilike(pattern),
        ))
    )
    return _count_and_fetch(db, stmt, ServiceReport.id.desc(), limit, options=(selectinload(ServiceReport.order),))


def _service_report_row(r: ServiceReport) -> dict:
    return {
        "id": r.id, "title": f"Bericht zu Auftrag {r.order.order_number}",
        "subtitle": r.order.customer_name, "url": f"/orders/{r.order_id}/service-reports?report={r.id}",
    }


# --- Mängel (Modul "wartungen") ---

def _search_findings(db: Session, term: str, limit: int) -> tuple[int, list]:
    pattern = f"%{term}%"
    stmt = (
        select(Finding)
        .join(ServiceReport, Finding.service_report_id == ServiceReport.id)
        .join(Order, ServiceReport.order_id == Order.id)
        .where(or_(
            Finding.description.ilike(pattern),
            Order.order_number.ilike(pattern),
        ))
    )
    return _count_and_fetch(
        db, stmt, Finding.id.desc(), limit,
        options=(selectinload(Finding.service_report).selectinload(ServiceReport.order),),
    )


def _finding_row(f: Finding) -> dict:
    order = f.service_report.order
    return {
        "id": f.id, "title": f.description[:80],
        "subtitle": f"Auftrag {order.order_number}",
        "url": f"/orders/{order.id}/service-reports?report={f.service_report_id}",
    }


# --- Wartungsverträge (Modul "wartungen") ---

def _search_maintenance_contracts(db: Session, term: str, limit: int) -> tuple[int, list]:
    pattern = f"%{term}%"
    stmt = (
        select(MaintenanceContract)
        .join(Customer, MaintenanceContract.customer_id == Customer.id)
        .where(or_(
            MaintenanceContract.title.ilike(pattern),
            Customer.name.ilike(pattern),
        ))
    )
    return _count_and_fetch(db, stmt, MaintenanceContract.id.desc(), limit, options=(selectinload(MaintenanceContract.customer),))


def _maintenance_contract_row(m: MaintenanceContract) -> dict:
    return {"id": m.id, "title": m.title, "subtitle": m.customer.name, "url": f"/maintenance-contracts/{m.id}"}


# --- Leistungen ---

def _search_services(db: Session, term: str, limit: int) -> tuple[int, list]:
    pattern = f"%{term}%"
    stmt = select(Service).where(or_(
        Service.short_text.ilike(pattern),
        Service.external_id.ilike(pattern),
    ))
    return _count_and_fetch(db, stmt, Service.id.desc(), limit)


def _service_row(s: Service) -> dict:
    return {"id": s.id, "title": (s.short_text or "").split("\n")[0][:120], "subtitle": s.external_id, "url": f"/services/{s.id}/edit"}


# --- Materialien (reines "fetch all, cap in Python" -- bewusste Tradeoff-Entscheidung bei
# aktueller Größenordnung, siehe CLAUDE.md; list_materials() ist die bereits bestehende,
# etablierte Suchfunktion, keine Zweitimplementierung derselben Sache) ---

def _search_materials(db: Session, term: str, limit: int) -> tuple[int, list]:
    rows_all = list_materials(db, search=term)
    return len(rows_all), rows_all[:limit]


def _material_row(m) -> dict:
    return {"id": m.id, "title": m.name, "subtitle": m.article_number, "url": f"/master-data/materials/{m.id}/edit"}


# --- Betriebsmittel (Modul "betriebsmittel", seit 1.4.2 Punkt 3) -- Live-Auflösung beachten:
# ein Asset MIT resource_id trägt seine eigenen Identitätsfelder (name/asset_type/manufacturer/
# model/identifier) als NULL (siehe app/operational_assets.py-Moduldocstring, "Live-Auflösung
# statt Kopie") -- ein Suchfilter, der nur OperationalAsset selbst prüft, würde jedes
# ressourcenverknüpfte Betriebsmittel (Kran, Fahrzeug, Anhänger) unauffindbar machen. Der
# outerjoin auf OperationalResource UND resolve_asset_identity() im row_fn (derselbe Helfer wie
# asset_to_dict()/asset_field_dict(), siehe dort) stellen sicher, dass beide Fälle -- mit und
# ohne Ressourcenbezug -- gefunden werden und niemals einen anderen Namen zeigen als die
# Betriebsmittelseite selbst. ---

def _search_operational_assets(db: Session, term: str, limit: int) -> tuple[int, list]:
    pattern = f"%{term}%"
    stmt = (
        select(OperationalAsset)
        .outerjoin(OperationalResource, OperationalAsset.resource_id == OperationalResource.id)
        .where(or_(
            OperationalAsset.name.ilike(pattern),
            OperationalAsset.asset_type.ilike(pattern),
            OperationalAsset.manufacturer.ilike(pattern),
            OperationalAsset.model.ilike(pattern),
            OperationalAsset.identifier.ilike(pattern),
            OperationalAsset.article_number.ilike(pattern),
            OperationalResource.name.ilike(pattern),
            OperationalResource.resource_type.ilike(pattern),
            OperationalResource.manufacturer.ilike(pattern),
            OperationalResource.model.ilike(pattern),
            OperationalResource.identifier.ilike(pattern),
        ))
    )
    return _count_and_fetch(db, stmt, OperationalAsset.id.desc(), limit, options=(selectinload(OperationalAsset.resource),))


def _operational_asset_row(a: OperationalAsset) -> dict:
    name, asset_type, manufacturer, model, identifier, _resource_number = resolve_asset_identity(a)
    sub = " · ".join(x for x in [asset_type, manufacturer, model, identifier] if x)
    return {"id": a.id, "title": name or f"Betriebsmittel #{a.id}", "subtitle": sub or None, "url": f"/betriebsmittel/{a.id}"}


# --- Lieferanten ---

def _search_suppliers(db: Session, term: str, limit: int) -> tuple[int, list]:
    pattern = f"%{term}%"
    stmt = select(Supplier).where(or_(
        Supplier.name.ilike(pattern),
        Supplier.supplier_number.ilike(pattern),
    ))
    return _count_and_fetch(db, stmt, Supplier.name, limit)


def _supplier_row(s: Supplier) -> dict:
    return {"id": s.id, "title": s.name, "subtitle": s.city, "url": f"/master-data/suppliers/{s.id}/edit"}


# --- Die Registry selbst -- siehe tests/test_v270_office_search.py für die erzwungene
# Vollständigkeitsprüfung (EXPECTED_OFFICE_SEARCH_KEYS), gebaut ZUSAMMEN mit dieser Liste, nicht
# danach (ausdrückliche Vorgabe, siehe CLAUDE.md "Büro-Suche"). ---

OFFICE_SEARCH_SOURCES: tuple[SearchSource, ...] = (
    SearchSource("customers", "Kunden", OFFICE_ROLES, _search_customers, _customer_row),
    SearchSource("properties", "Objekte", OFFICE_ROLES, _search_properties_office, _property_office_row),
    SearchSource("roof_areas", "Dachflächen", OFFICE_ROLES, _search_roof_areas, _roof_area_row),
    SearchSource("projects", "Projekte", OFFICE_ROLES, _search_projects, _project_row),
    SearchSource("quotes", "Angebote", OFFICE_ROLES, _search_quotes, _quote_row),
    SearchSource("orders", "Aufträge", OFFICE_ROLES, _search_orders, _order_row),
    SearchSource("invoices", "Rechnungen", OFFICE_ROLES, _search_invoices, _invoice_row),
    SearchSource("reminders", "Mahnungen", OFFICE_ROLES, _search_reminders, _reminder_row),
    SearchSource("inquiries", "Anfragen", OFFICE_ROLES, _search_inquiries, _inquiry_row),
    SearchSource("tasks", "Aufgaben", OFFICE_ROLES, _search_tasks, _task_row, module_key="aufgabenmanagement"),
    SearchSource("employees", "Mitarbeiter", OFFICE_ROLES, _search_employees, _employee_row),
    SearchSource("service_reports", "Einsatzberichte", OFFICE_ROLES, _search_service_reports, _service_report_row, module_key="wartungen"),
    SearchSource("findings", "Mängel", OFFICE_ROLES, _search_findings, _finding_row, module_key="wartungen"),
    SearchSource("maintenance_contracts", "Wartungsverträge", OFFICE_ROLES, _search_maintenance_contracts, _maintenance_contract_row, module_key="wartungen"),
    SearchSource("services", "Leistungen", OFFICE_ROLES, _search_services, _service_row),
    SearchSource("materials", "Materialien", OFFICE_ROLES, _search_materials, _material_row),
    SearchSource("suppliers", "Lieferanten", OFFICE_ROLES, _search_suppliers, _supplier_row),
    SearchSource(
        "operational_assets", "Betriebsmittel", OFFICE_ROLES, _search_operational_assets, _operational_asset_row,
        module_key="betriebsmittel",
    ),
)


def search_office(
    db: Session, role: str, query: str, *,
    limit_per_type: int = OFFICE_SEARCH_RESULT_LIMIT, types: frozenset[str] | None = None,
    employee_id: int | None = None,
) -> list[dict]:
    """Der EINE Dispatcher der Büro-Suche (siehe Moduldocstring) -- geht OFFICE_SEARCH_SOURCES
    durch und filtert dreifach: Rolle (source.allowed_roles -- ein Monteur bekommt aus JEDER
    Quelle nichts, da role==ROLE_FIELD in keiner allowed_roles-Menge steckt; die eigentliche,
    primäre Sicherung ist trotzdem der Router selbst, siehe app/routers/search.py), optionaler
    `types`-Filter (Client-Parameter, welche Datensatzarten überhaupt durchsucht werden sollen),
    Modul-Zustand (source.module_key, falls gesetzt -- dritte, von der Rolle unabhängige Achse).

    `employee_id` (seit 1.4.4, siehe CLAUDE.md "Änderung am Aufgabenmodul") ist ausschließlich
    für die "tasks"-Quelle relevant -- jede andere Quelle ignoriert ihn, unverändert. Optional
    mit Default None, damit kein bestehender Aufrufer sich ändern muss (ein Admin-Aufruf ohne
    employee_id sieht über _search_tasks() weiterhin alles, exakt wie vorher).

    Liefert nur Gruppen mit mindestens einem Treffer (total > 0) -- eine leere Gruppe wäre auf
    der Ergebnisseite nur Rauschen. Prüft MIN_QUERY_LENGTH EINMAL zentral, bevor irgendeine der
    Quellfunktionen aufgerufen wird -- diese selbst prüfen es nicht erneut (siehe
    Moduldocstring)."""
    term = (query or "").strip()
    if len(term) < MIN_QUERY_LENGTH:
        return []
    groups = []
    for source in OFFICE_SEARCH_SOURCES:
        if role not in source.allowed_roles:
            continue
        if types is not None and source.key not in types:
            continue
        if source.module_key is not None and not is_module_enabled(db, source.module_key):
            continue
        if source.key == "tasks":
            # Einzige Quelle, die pro Aufrufer scopen muss (siehe _search_tasks()-Docstring) --
            # bekommt deshalb zusätzlich role/employee_id, jede andere Quelle bleibt beim
            # einheitlichen 3-Parameter-Aufruf.
            total, rows = source.query_fn(db, term, limit_per_type, role, employee_id)
        else:
            total, rows = source.query_fn(db, term, limit_per_type)
        if total == 0:
            continue
        groups.append({
            "key": source.key,
            "label": source.label,
            "total": total,
            "hits": [source.row_fn(row) for row in rows],
        })
    return groups
