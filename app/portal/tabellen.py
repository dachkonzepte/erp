"""Die Tabellen, die der Portal-Dienst selbst liest (seit 1.11.2) -- als Core-Tabellen mit NUR den Spalten aus app/portal/rechte.py::LESEN.

Eine Spalte, die hier fehlt, kann der Dienst gar nicht abfragen (und hätte unter seiner Rolle auch kein Recht darauf). Typen und Längen wie im Modell des
ERP; tests/test_v801_portal_dienst.py vergleicht beides. Alles andere (Link, Sitzung, Begrüßung) läuft über die Funktionen der Datenbank (funktionen.py).
"""

from sqlalchemy import Column, Integer, MetaData, String, Table

metadata = MetaData()

general_settings = Table(
    "general_settings", metadata,
    Column("id", Integer, primary_key=True),
    Column("company_name", String(255)),
    Column("street", String(255)),
    Column("postal_code", String(20)),
    Column("city", String(120)),
    Column("phone", String(80)),
    Column("email", String(255)),
    Column("website", String(255)),
)

alembic_version = Table(
    "alembic_version", metadata,
    Column("version_num", String(32), primary_key=True),
)
