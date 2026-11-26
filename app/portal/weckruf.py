"""Weckruf für den Postboten, wenn sich Freigaben ändern (seit 1.11.33, Stufe P2b; Bauplan P2, B2.1).

Ein Auslöser auf Anweisungsebene an portal_freigaben: nach jedem INSERT und jedem UPDATE der Spalte zurueckgenommen_am ein NOTIFY auf dem Kanal
portal_freigabe (ohne Inhalt -- der Postbote liest selbst, was zu tun ist, app/portal_kopien.py). Er feuert für jeden Weg, der eine Freigabe anlegt oder
zurücknimmt -- Code des ERP, Skript, SQL --, und erst beim Commit (NOTIFY wartet auf ihn). Das Schreiben der Kopie-Spalten durch den Postboten selbst weckt
nicht. Was eine Freigabe ruhen lässt (Kette, Archiv), weckt nicht: das findet der volle Lauf alle 15 Minuten; das Portal zeigt sie ohnehin sofort nicht mehr.

Gehört dem Benutzer des ERP, für alle entzogen (wie jede Funktion im Schema, app/portal/rechte.py prüft das). Der Text steht wörtlich in der Migration
a7c3e9f1d2b4; tests/test_v823_portal_kopien.py vergleicht. Unter PostgreSQL legt jedes create_all() ihn an (app/database.py), unter SQLite gibt es ihn
nicht.
"""

KANAL = "portal_freigabe"

ANWEISUNGEN = (
    "CREATE OR REPLACE FUNCTION portal_freigabe_geweckt() RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog, @SCHEMA@, pg_temp AS $$\n"
    "BEGIN\n"
    f"  PERFORM pg_notify('{KANAL}', '');\n"
    "  RETURN NULL;\n"
    "END\n"
    "$$",
    "CREATE OR REPLACE TRIGGER portal_freigabe_geweckt AFTER INSERT OR UPDATE OF zurueckgenommen_am ON portal_freigaben\n"
    "FOR EACH STATEMENT EXECUTE FUNCTION portal_freigabe_geweckt()",
    "REVOKE ALL ON FUNCTION portal_freigabe_geweckt() FROM PUBLIC",
)


def anweisungen(schema: str) -> list[str]:
    from .rechte import _name
    schema = _name(schema)
    return [a.replace("@SCHEMA@", schema) for a in ANWEISUNGEN]


def pg_anlegen(target, connection, **kw):
    """Nach jedem create_all() unter PostgreSQL; fehlt portal_freigaben (create_all() nur für einzelne Tabellen), bleibt es bei nichts."""
    if connection.dialect.name != "postgresql":
        return
    if not connection.exec_driver_sql("SELECT to_regclass('portal_freigaben') IS NOT NULL").scalar():
        return
    schema = connection.exec_driver_sql("SELECT current_schema()").scalar()
    for a in anweisungen(schema):
        connection.exec_driver_sql(a)
