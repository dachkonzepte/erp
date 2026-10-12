"""Test-Helfer seit 1.8.80: Bestand für die Migrationsproben älterer Stände (tests/test_v380_nummern_eindeutig.py,
tests/test_v381_zahlungen_migration.py, tests/test_v382_mahnwesen_migration.py).

Die Proben fahren die Datenbank auf einen Stand vor einer Migration und legen dort einen Bestand an. Mit dem ORM von heute geht
das nicht, sobald eine spätere Migration an denselben Tabellen eine Spalte ergänzt -- das ORM schreibt und liest jede Spalte des
heutigen Modells (1.8.79: invoices.customer_id, seit 1.8.80 orders.customer_id und general_settings.dunning_charges_enabled, die
app.grunddaten.anlegen() liest). Deshalb hier Startspalte, Kunde, Projekt, Angebot und Auftrag als Core-Insert mit genau den
Spalten, die es auf jedem dieser Stände gibt -- und orders.customer_id nur, wenn die Spalte schon da ist."""

from types import SimpleNamespace

from sqlalchemy import inspect, text

_ZEIT = "2026-09-01 08:00:00"  # als Text: SQLite und PostgreSQL nehmen es ohne Adapter


def _spalten(db, table: str) -> set[str]:
    # Über die Verbindung der Sitzung, nicht die Engine: unter SQLite (:memory:) teilten sich beide die Verbindung, und deren
    # Rückgabe an den Pool rollte die laufende Transaktion zurück.
    return {c["name"] for c in inspect(db.connection()).get_columns(table)}


def startspalte(db) -> int:
    """Die Startspalte der Projektliste (sonst von app.grunddaten.anlegen() angelegt)."""
    existing = db.execute(text("SELECT id FROM project_pipeline_columns ORDER BY sort_order, id LIMIT 1")).scalar()
    if existing is not None:
        return existing
    return db.execute(text("INSERT INTO project_pipeline_columns (key, label, sort_order, created_at) "
                           "VALUES ('neu', 'Neu', 10, :t) RETURNING id"), {"t": _ZEIT}).scalar()


def auftrag_zeile(db, *, order_number: str, project_id: int, quote_id: int, quote_number: str, customer_name: str,
                  vat_rate: int = 19) -> int:
    """Eine Auftragszeile wie beim Beauftragen; customer_id (seit 1.8.80) = Kunde des Projekts, wenn es die Spalte gibt."""
    values = {"order_number": order_number, "project_id": project_id, "source_quote_id": quote_id,
              "quote_number_snapshot": quote_number, "title": "Dachsanierung", "status": "beauftragt", "vat_rate": vat_rate,
              "customer_name": customer_name, "order_date": "2026-09-01", "created_at": _ZEIT, "updated_at": _ZEIT}
    if "customer_id" in _spalten(db, "orders"):
        values["customer_id"] = db.execute(text("SELECT customer_id FROM projects WHERE id = :p"), {"p": project_id}).scalar()
    columns = ", ".join(values)
    params = ", ".join(f":{k}" for k in values)
    return db.execute(text(f"INSERT INTO orders ({columns}) VALUES ({params}) RETURNING id"), values).scalar()


def auftrag(db, *, number: str, is_consumer: bool = False) -> SimpleNamespace:
    """Kunde, Projekt, Angebot und Auftrag (wie make_quote() + beauftragen() aus tests/test_v325_contract_basis.py), committet.
    Ergebnis mit id, project_id, customer_id und customer_name."""
    column = startspalte(db)
    name = f"Kunde {number}"
    customer_id = db.execute(text(
        "INSERT INTO customers (name, last_name, country, is_consumer, street, postal_code, city, created_at) "
        "VALUES (:n, :n, 'Deutschland', :c, 'Dachweg 1', '52531', 'Uebach', :t) RETURNING id"),
        {"n": name, "c": is_consumer, "t": _ZEIT}).scalar()
    project_id = db.execute(text(
        "INSERT INTO projects (project_number, name, customer_id, status, pipeline_column_id, is_template, archived, created_at) "
        "VALUES (:no, 'Dach', :c, 'beauftragt', :col, :f, :f, :t) RETURNING id"),
        {"no": f"P-{number}", "c": customer_id, "col": column, "f": False, "t": _ZEIT}).scalar()
    quote_id = db.execute(text(
        "INSERT INTO quotes (quote_number, project_id, title, status, vat_rate, source_format, created_at, updated_at) "
        "VALUES (:no, :p, 'Dachsanierung', 'beauftragt', 19, 'manual', :t, :t) RETURNING id"),
        {"no": f"A-{number}", "p": project_id, "t": _ZEIT}).scalar()
    order_id = auftrag_zeile(db, order_number=f"AU-{number}", project_id=project_id, quote_id=quote_id,
                             quote_number=f"A-{number}", customer_name=name)
    db.commit()
    return SimpleNamespace(id=order_id, project_id=project_id, customer_id=customer_id, customer_name=name)
