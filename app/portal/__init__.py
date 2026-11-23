"""Kundenportal (Stufe P1, seit 1.11.0; docs/archiv/webseite-und-kundenportal.md, „Bauplan P1“).

Der Dienst des Portals (ab P1b) läuft als eigener Prozess unter einem eigenen Systembenutzer und mit einem eigenen PostgreSQL-Benutzer (dkportal). Dieses
Paket importiert nichts aus dem ERP außer einer Positivliste (Wächter tests/test_v799_portal_rechte.py): kein app.models, kein app.database. Was der
Benutzer des Portals in der Datenbank darf, steht in rechte.py; alles an Link und Sitzung läuft über Funktionen der Datenbank (ab 1.11.1).
"""
