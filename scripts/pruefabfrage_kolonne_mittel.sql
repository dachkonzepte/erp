-- Prüfabfrage Kolonnenbuchungen (seit 1.9.94, Stufe 4, R5b, Punkt 0): welche Kolonnenbuchung bekam durch ein Ändern ohne Von/Bis für alle
-- Mitglieder dieselben Stunden? NUR LESEN -- läuft in einer schreibgeschützten Transaktion und endet mit ROLLBACK, ändert nichts.
--
-- Der Fehler (bis 1.9.89, behoben mit 1.9.90): PUT /api/time-entry-groups/{id} ohne Von/Bis -- auch nur Notiz, Tätigkeit oder Zeitart --
-- gab jedem nicht einzeln geänderten Mitglied die Stunden und die Pause des Kopfs; nach einem Kolonnen-Nachtrag mit Von/Bis (seit 1.9.63)
-- hält der Kopf das Mittel aller Mitglieder (Mia 3,50 h und Tom 4,25 h wurden je 3,875 h).
--
-- Aufruf auf dem Server (als Benutzer tobias): die Verbindung aus /home/tobias/erp/.env, ohne den Treiberzusatz "+psycopg", den psql nicht
-- kennt; PGOPTIONS macht jede Transaktion der Sitzung schreibgeschützt (doppelt zum BEGIN TRANSACTION READ ONLY unten):
--
--     cd /home/tobias/erp
--     set -a; source .env; set +a
--     PGOPTIONS='-c default_transaction_read_only=on' psql "${DATABASE_URL/postgresql+psycopg:/postgresql:}" -v ON_ERROR_STOP=1 -f scripts/pruefabfrage_kolonne_mittel.sql
--
-- Ein Ergebnis, leer, wenn nichts betroffen ist: je betroffener Änderung und Mitglied eine Zeile -- Gruppe, Tag, Auftrag, Mitarbeiter, Stunden
-- vorher und nachher, wann (Europe/Berlin) und von wem geändert.
--
-- Woran die Abfrage den Fehler erkennt (aus dem Änderungsverlauf audit_logs, den jede Änderung schreibt):
--   - Änderungen der Stunden von Zeitbuchungen seit dem 23.10.2026 (00:00 Europe/Berlin = 22.10.2026 22:00 UTC; occurred_at ist UTC) über
--     PUT /api/time-entry-groups/{id} -- also das Ändern einer Kolonnenbuchung, nicht das Ändern eines einzelnen Mitglieds;
--   - je Gruppe und Anfrage (dieselbe Minute) mindestens zwei Mitglieder, nachher alle dieselben Stunden, vorher verschiedene;
--   - und die Stunden des Kopfs (Gruppen-Zeitbuchung) änderten sich in derselben Anfrage NICHT -- bei einer bewusst eingetragenen Dauer
--     ändern sie sich mit (dann ist das gleiche Ergebnis gewollt und keine Zeile erscheint). Eine Dauer, die zufällig genau das alte Mittel
--     trifft, erschiene hier ebenfalls -- im Zweifel am Verlauf der Gruppe prüfen.
-- Was die Abfrage nicht findet: Änderungen ohne Eintrag im Verlauf (vor der Einführung des Verlaufs; der Verlauf ist unveränderlich).

BEGIN TRANSACTION READ ONLY;

WITH aenderung AS (
    SELECT a.entity_id::integer AS buchung_id, a.old_value, a.new_value, a.occurred_at, a.actor_name, a.request_path,
           date_trunc('minute', a.occurred_at) AS minute
    FROM audit_logs a
    WHERE a.entity_type = 'Zeitbuchung' AND a.action = 'geändert' AND a.field_name = 'hours'
      AND a.request_method = 'PUT' AND a.request_path ~ '^/api/time-entry-groups/[0-9]+$'
      AND a.occurred_at >= TIMESTAMP '2026-10-22 22:00:00'
),
je_aenderung AS (
    SELECT g.id AS gruppe, ae.request_path, ae.minute
    FROM aenderung ae
    JOIN time_entry_group_members m ON m.time_entry_id = ae.buchung_id
    JOIN time_entry_groups g ON g.id = m.group_id AND ae.request_path = '/api/time-entry-groups/' || g.id
    GROUP BY g.id, ae.request_path, ae.minute
    HAVING count(*) >= 2 AND count(DISTINCT ae.new_value::numeric) = 1 AND count(DISTINCT ae.old_value::numeric) > 1
)
SELECT g.id AS gruppe,
       g.work_date AS tag,
       concat_ws(' · ', o.order_number, o.title) AS auftrag,
       concat_ws(' ', e.first_name, e.last_name) AS mitarbeiter,
       ae.old_value::numeric AS stunden_vorher,
       ae.new_value::numeric AS stunden_nachher,
       (ae.occurred_at AT TIME ZONE 'UTC') AT TIME ZONE 'Europe/Berlin' AS geaendert_am,
       ae.actor_name AS geaendert_von
FROM je_aenderung j
JOIN time_entry_groups g ON g.id = j.gruppe
JOIN orders o ON o.id = g.order_id
JOIN aenderung ae ON ae.request_path = j.request_path AND ae.minute = j.minute
JOIN time_entry_group_members m ON m.time_entry_id = ae.buchung_id AND m.group_id = g.id
JOIN employees e ON e.id = m.employee_id
WHERE NOT EXISTS (
    SELECT 1 FROM audit_logs k
    WHERE k.entity_type = 'Gruppen-Zeitbuchung' AND k.entity_id = g.id::text AND k.field_name = 'hours'
      AND k.request_path = j.request_path AND date_trunc('minute', k.occurred_at) = j.minute
)
ORDER BY g.work_date, g.id, ae.occurred_at, mitarbeiter;

ROLLBACK;
