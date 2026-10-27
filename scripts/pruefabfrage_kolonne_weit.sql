-- Prüfabfrage Kolonnenbuchungen, weit gefasst (seit 1.9.100, Stufe 4, R5b Nachrunde, Punkt 0). NUR LESEN -- läuft in einer
-- schreibgeschützten Transaktion und endet mit ROLLBACK, ändert nichts.
--
-- Anlass: scripts/pruefabfrage_kolonne_mittel.sql (1.9.94) fand auf dem Server nichts. Sie suchte eng: seit dem 23.10.2026, mindestens zwei
-- Mitglieder, alle nachher gleich, vorher verschieden, eine Anfrage = dieselbe Minute. Der Fehler (bis 1.9.89, behoben mit 1.9.90):
-- PUT /api/time-entry-groups/{id} ohne Von/Bis -- auch nur Notiz, Tätigkeit oder Zeitart -- gab jedem nicht einzeln geänderten Mitglied
-- die Stunden und die Pause des Kopfs. Probe auf dem Code von 1.9.89 (Bericht der Nachrunde): dabei schreibt der Verlauf (audit_logs) je
-- Mitglied, dessen Stunden sich ändern, eine Zeile „hours“ mit dem Pfad der Kolonne; der Kopf behält seine Stunden und bekommt keine.
--
-- Aufruf auf dem Server (als Benutzer tobias): die Verbindung aus /home/tobias/erp/.env, ohne den Treiberzusatz "+psycopg", den psql nicht
-- kennt; PGOPTIONS macht jede Transaktion der Sitzung schreibgeschützt (doppelt zum BEGIN TRANSACTION READ ONLY unten):
--
--     cd /home/tobias/erp
--     set -a; source .env; set +a
--     PGOPTIONS='-c default_transaction_read_only=on' psql "${DATABASE_URL/postgresql+psycopg:/postgresql:}" -v ON_ERROR_STOP=1 -f scripts/pruefabfrage_kolonne_weit.sql
--
-- Drei Teile, je mit Überschrift; ein Teil ohne Treffer zeigt "(0 Zeilen)" bzw. "(0 rows)".
--
--   a) Jede Änderung der Stunden eines Mitglieds über PUT /api/time-entry-groups/{id}, bei der sich die Stunden des Kopfs (Gruppen-Zeitbuchung)
--      in derselben Anfrage NICHT änderten -- ohne Datumsgrenze, auch wenn nur ein Mitglied betroffen ist oder die alten Werte gleich waren.
--      Eine Anfrage: die Einträge desselben Pfads, zwischen denen höchstens 5 Sekunden liegen (der Verlauf trägt keine Kennung der Anfrage;
--      alle Einträge einer Anfrage entstehen in Millisekunden, über eine Minutengrenze hinweg). "uhrzeiten_geaendert" = in derselben Anfrage
--      änderten sich auch Beginn oder Ende des Mitglieds -- ein Ändern mit Von/Bis (seit 1.9.63), bei dem das Mittel des Kopfs zufällig
--      gleich blieb; dann ist die Zeile kein Fehler. Ohne Uhrzeiten (nein) ist es der Fehler bis 1.9.89 oder eine bewusst eingetragene Dauer,
--      die genau die alten Stunden des Kopfs traf -- im Zweifel am Verlauf der Gruppe prüfen.
--   b) Ohne Verlauf: jedes Mitglied einer Kolonnenbuchung mit Beginn und Ende, dessen gebuchte Stunden nicht zu Von/Bis minus seiner Pause
--      passen -- gerechnet wie der Server (app/time_tracking.py::nachtrag_nach_zeitregel()/ende_rechnen(): Anwesenheit auf vier Stellen,
--      minus Pause, mit der Rundung der Zeitregeln, rounding_minutes, sonst auf vier Stellen). Abweichungen unter 0,005 h (18 Sekunden)
--      zählen nicht (die Rechnungen von Stopp und Nachtrag runden an der vierten Stelle verschieden). Findet auch, was der Verlauf nicht hat
--      (vor der Einführung des Verlaufs, Änderungen ohne Pfad); gerechnet wird mit der Rundung von HEUTE -- wurde sie geändert, erscheinen
--      ältere Buchungen hier, ohne falsch zu sein (dann steht in "rundung_min" die heutige).
--   c) Kontrollzahlen: Änderungen von Kolonnenbuchungen im Verlauf je Monat (Europe/Berlin) -- Anfragen, Kolonnen, Einträge, Stundenänderungen
--      der Mitglieder und des Kopfs, davon in a) gefunden.

BEGIN TRANSACTION READ ONLY;

\echo
\echo '== a) Stunden eines Mitglieds über PUT /api/time-entry-groups/{id} geändert, die Stunden des Kopfs in derselben Anfrage nicht'
WITH verlauf AS (
    SELECT a.id, a.action, a.entity_type, a.entity_id, a.field_name, a.old_value, a.new_value, a.occurred_at, a.actor_name, a.request_path,
           CASE WHEN a.occurred_at - lag(a.occurred_at) OVER (PARTITION BY a.request_path ORDER BY a.occurred_at, a.id) <= INTERVAL '5 seconds'
                THEN 0 ELSE 1 END AS neu
    FROM audit_logs a
    WHERE a.request_method = 'PUT' AND a.request_path ~ '^/api/time-entry-groups/[0-9]+$'
),
anfrage AS (
    SELECT v.*, sum(v.neu) OVER (PARTITION BY v.request_path ORDER BY v.occurred_at, v.id) AS nr
    FROM verlauf v
)
SELECT substring(m.request_path FROM '[0-9]+$')::integer AS gruppe,
       COALESCE(g.work_date, te.work_date) AS tag,
       concat_ws(' · ', o.order_number, o.title) AS auftrag,
       concat_ws(' ', e.first_name, e.last_name) AS mitarbeiter,
       m.entity_id AS buchung,
       m.old_value::numeric AS stunden_vorher,
       m.new_value::numeric AS stunden_nachher,
       (m.occurred_at AT TIME ZONE 'UTC') AT TIME ZONE 'Europe/Berlin' AS geaendert_am,
       m.actor_name AS geaendert_von,
       EXISTS (SELECT 1 FROM anfrage u
               WHERE u.request_path = m.request_path AND u.nr = m.nr AND u.entity_type = 'Zeitbuchung' AND u.entity_id = m.entity_id
                 AND u.field_name IN ('started_at', 'ended_at')) AS uhrzeiten_geaendert
FROM anfrage m
LEFT JOIN time_entries te ON te.id::text = m.entity_id
LEFT JOIN employees e ON e.id = te.employee_id
LEFT JOIN time_entry_groups g ON g.id::text = substring(m.request_path FROM '[0-9]+$')
LEFT JOIN orders o ON o.id = COALESCE(g.order_id, te.order_id)
WHERE m.entity_type = 'Zeitbuchung' AND m.action = 'geändert' AND m.field_name = 'hours'
  AND NOT EXISTS (SELECT 1 FROM anfrage k
                  WHERE k.request_path = m.request_path AND k.nr = m.nr
                    AND k.entity_type = 'Gruppen-Zeitbuchung' AND k.action = 'geändert' AND k.field_name = 'hours')
ORDER BY m.occurred_at, gruppe, mitarbeiter, buchung;

\echo
\echo '== b) Ohne Verlauf: Mitglieder einer Kolonnenbuchung mit Von/Bis, deren Stunden nicht zu Von/Bis minus Pause passen'
WITH regel AS (
    SELECT COALESCE(max(s.rounding_minutes), 0) AS minuten FROM time_tracking_settings s
),
mitglied AS (
    SELECT gm.group_id, te.id AS buchung, te.work_date, te.order_id, te.employee_id, te.started_at, te.ended_at, te.break_minutes, te.hours,
           round(extract(epoch FROM (te.ended_at - te.started_at))::numeric / 3600, 4) AS anwesend
    FROM time_entry_group_members gm
    JOIN time_entries te ON te.id = gm.time_entry_id
    WHERE te.status = 'booked' AND te.started_at IS NOT NULL AND te.ended_at IS NOT NULL AND te.ended_at > te.started_at
),
rechnung AS (
    SELECT m.*, r.minuten,
           CASE WHEN r.minuten > 0
                THEN round(round(greatest(m.anwesend - m.break_minutes::numeric / 60, 0) / (r.minuten::numeric / 60)) * (r.minuten::numeric / 60), 2)
                ELSE round(greatest(m.anwesend - m.break_minutes::numeric / 60, 0), 4) END AS erwartet
    FROM mitglied m CROSS JOIN regel r
)
SELECT x.group_id AS gruppe,
       x.work_date AS tag,
       concat_ws(' · ', o.order_number, o.title) AS auftrag,
       concat_ws(' ', e.first_name, e.last_name) AS mitarbeiter,
       x.buchung,
       to_char(x.started_at, 'HH24:MI') || '–' || to_char(x.ended_at, 'HH24:MI') AS von_bis,
       x.break_minutes AS pause_min,
       x.hours::numeric AS stunden,
       x.erwartet AS stunden_nach_von_bis,
       x.hours::numeric - x.erwartet AS abweichung,
       x.minuten AS rundung_min
FROM rechnung x
LEFT JOIN orders o ON o.id = x.order_id
LEFT JOIN employees e ON e.id = x.employee_id
WHERE abs(x.hours::numeric - x.erwartet) >= 0.005
ORDER BY x.work_date, x.group_id, mitarbeiter, x.buchung;

\echo
\echo '== c) Kontrollzahlen: Änderungen von Kolonnenbuchungen im Verlauf je Monat (Europe/Berlin)'
WITH verlauf AS (
    SELECT a.id, a.action, a.entity_type, a.entity_id, a.field_name, a.occurred_at, a.request_path,
           CASE WHEN a.occurred_at - lag(a.occurred_at) OVER (PARTITION BY a.request_path ORDER BY a.occurred_at, a.id) <= INTERVAL '5 seconds'
                THEN 0 ELSE 1 END AS neu
    FROM audit_logs a
    WHERE a.request_method = 'PUT' AND a.request_path ~ '^/api/time-entry-groups/[0-9]+$'
),
anfrage AS (
    SELECT v.*, sum(v.neu) OVER (PARTITION BY v.request_path ORDER BY v.occurred_at, v.id) AS nr
    FROM verlauf v
),
markiert AS (
    SELECT m.*,
           (m.entity_type = 'Zeitbuchung' AND m.action = 'geändert' AND m.field_name = 'hours') AS stunden_mitglied,
           (m.entity_type = 'Gruppen-Zeitbuchung' AND m.action = 'geändert' AND m.field_name = 'hours') AS stunden_kopf,
           NOT EXISTS (SELECT 1 FROM anfrage k
                       WHERE k.request_path = m.request_path AND k.nr = m.nr
                         AND k.entity_type = 'Gruppen-Zeitbuchung' AND k.action = 'geändert' AND k.field_name = 'hours') AS kopf_unveraendert
    FROM anfrage m
)
SELECT to_char((occurred_at AT TIME ZONE 'UTC') AT TIME ZONE 'Europe/Berlin', 'YYYY-MM') AS monat,
       count(DISTINCT request_path || '#' || nr) AS anfragen,
       count(DISTINCT request_path) AS kolonnen,
       count(*) AS eintraege,
       count(*) FILTER (WHERE stunden_mitglied) AS stunden_mitglieder,
       count(*) FILTER (WHERE stunden_kopf) AS stunden_kopf,
       count(*) FILTER (WHERE stunden_mitglied AND kopf_unveraendert) AS davon_in_a
FROM markiert
GROUP BY 1
ORDER BY 1;

ROLLBACK;
