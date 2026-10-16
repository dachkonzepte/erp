-- Prüfabfrage zu 1.8.119 (Zahleneingaben: Browser und Server mit denselben Grenzen, tests/test_v424_zahlgrenzen.py).
-- Seit 1.8.119 lehnt der Server Werte ab, die bis dahin nur der Browser ablehnte. Ein gespeicherter Wert außerhalb der neuen Grenzen
-- bleibt stehen und wird weiter angezeigt -- aber ein Speichern, das ihn wieder mitschickt (z. B. "Wartungsvertrag bearbeiten" schickt
-- immer das Intervall), scheitert dann mit 422, bis der Wert berichtigt ist. Diese Abfrage nennt solche Zeilen; leer heißt: nichts zu tun.
-- Nur lesend, für PostgreSQL und SQLite. Aufruf z. B. psql "$DATABASE_URL_OHNE_TREIBER" -f scripts/pruefabfrage_zahlgrenzen.sql
SELECT 'Wartungsvertrag: Intervall (Monate, 1-24)' AS was, id, CAST(interval_months AS TEXT) AS wert
  FROM maintenance_contracts WHERE interval_months NOT BETWEEN 1 AND 24
UNION ALL SELECT 'Wartungsposition: Dauer (Minuten, ab 0)', id, CAST(duration_minutes AS TEXT)
  FROM maintenance_contract_items WHERE duration_minutes < 0
UNION ALL SELECT 'Prüfpunkt: Dauer (Minuten, ab 0)', id, CAST(duration_minutes AS TEXT)
  FROM inspection_items WHERE duration_minutes < 0
UNION ALL SELECT 'Dachfläche: Neigung (Grad, ab 0)', id, CAST(pitch_degrees AS TEXT)
  FROM roof_areas WHERE pitch_degrees < 0
UNION ALL SELECT 'Dachfläche: Fläche (m², ab 0)', id, CAST(area_sqm AS TEXT)
  FROM roof_areas WHERE area_sqm < 0
UNION ALL SELECT 'Bauteil: Menge (ab 0)', id, CAST(quantity AS TEXT)
  FROM roof_components WHERE quantity < 0
UNION ALL SELECT 'Bauteil: Baujahr (1900-2100)', id, CAST(year_built AS TEXT)
  FROM roof_components WHERE year_built NOT BETWEEN 1900 AND 2100
UNION ALL SELECT 'Schicht: Dicke (mm, ab 0)', id, CAST(thickness_mm AS TEXT)
  FROM roof_layers WHERE thickness_mm < 0
UNION ALL SELECT 'Betriebsmittel: Anschaffungskosten (ab 0)', id, CAST(acquisition_cost AS TEXT)
  FROM operational_assets WHERE acquisition_cost < 0
UNION ALL SELECT 'Betriebskosten: Kündigungsfrist (Monate, bis 24)', id, CAST(notice_period_months AS TEXT)
  FROM recurring_costs WHERE notice_period_months > 24
UNION ALL SELECT 'Plantafel: Standard-Anfahrt (h, bis 23,75)', id, CAST(default_travel_hours_per_employee_day AS TEXT)
  FROM planning_settings WHERE default_travel_hours_per_employee_day > 23.75
ORDER BY was, id;
