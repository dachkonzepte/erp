-- Prüfabfrage DATEV-Personalnummern (seit 1.9.168, Lohn L1a, Punkt 3). NUR LESEN -- ändert nichts. Vor der Migration c5a9e3f71d28
-- (Personalnummer eindeutig) laufen lassen: findet sie eine Dublette, bricht die Migration ab, ohne etwas zu ändern.
--
-- Aufruf auf dem Server (PostgreSQL), z. B.:
--     psql -d dachkonzepte -f scripts/pruefabfrage_personalnummern.sql
--
-- Drei Ergebnisse, ohne Namen (nur die Kennung der Person):
--   1. Dubletten: jede Nummer, die mehr als eine Person trägt (Leerzeichen um die Nummer zählen nicht).
--   2. Format: jede Nummer, die nicht aus 1 bis 5 Ziffern ohne führende Null besteht (seit 1.9.168 lehnt das Speichern sie ab).
--   3. Leer oder nur Leerzeichen gespeichert (die Migration macht daraus NULL).
-- Gilt „DATEV-Nr. = ERP-Nr.“ (Einstellungen -> Zeitregeln und DATEV), nimmt der Export die ERP-Nummer; die prüft scripts/pruefe_zeitregeln.py.

SELECT 'Dublette' AS befund, TRIM(datev_personnel_number) AS nummer, count(*) AS personen,
       string_agg(employee_id::text, ', ' ORDER BY employee_id) AS mitarbeiter_ids
FROM employee_payroll_settings
WHERE datev_personnel_number IS NOT NULL AND TRIM(datev_personnel_number) <> ''
GROUP BY TRIM(datev_personnel_number)
HAVING count(*) > 1
ORDER BY nummer;

SELECT 'Format' AS befund, employee_id AS mitarbeiter_id, datev_personnel_number AS nummer
FROM employee_payroll_settings
WHERE datev_personnel_number IS NOT NULL AND TRIM(datev_personnel_number) <> ''
  AND TRIM(datev_personnel_number) !~ '^[1-9][0-9]{0,4}$'
ORDER BY employee_id;

SELECT 'leer' AS befund, employee_id AS mitarbeiter_id
FROM employee_payroll_settings
WHERE datev_personnel_number IS NOT NULL AND TRIM(datev_personnel_number) = ''
ORDER BY employee_id;
