-- Prüfabfrage Dachtypen (Befund 20.10.2026, Stufe 2 Redesign, Nachtrag zu Runde 2): welche Dachtypen stehen in der Datenbank?
-- NUR LESEN -- läuft in einer schreibgeschützten Transaktion und endet mit ROLLBACK, ändert nichts.
--
-- Aufruf auf dem Server (PostgreSQL), z. B.:
--     psql -d dachkonzepte -f scripts/pruefabfrage_dachtypen.sql
--
-- Zwei Ergebnisse:
--   1. Jeder Wert je Ort mit Anzahl: die Auswahlliste "Dachtypen" (roof_types, mit aktiv ja/nein) und die vier Spalten, die einen
--      Dachtyp als freien Text speichern -- Prüfvorlagen, Standardvorlage je Dachtyp, Dachflächen, Schichttypen des Dachaufbaus.
--   2. Werte, die kein Eintrag der Auswahlliste genau so trägt (Groß-/Kleinschreibung zählt, wie überall im Programm), mit dem
--      Eintrag, der nur in der Schreibweise abweicht, falls es einen gibt (z. B. "flachdach" -> "Flachdach").
--
-- Hintergrund: docs/archiv/redesign.md, "Punkt 2: Befund Dachtyp".

BEGIN TRANSACTION READ ONLY;

SELECT 'Auswahlliste roof_types' AS ort, o.value AS dachtyp, count(*) AS anzahl, bool_or(o.active) AS aktiv
  FROM setting_options o JOIN setting_option_groups g ON g.id = o.group_id
 WHERE g.group_key = 'roof_types'
 GROUP BY o.value
UNION ALL
SELECT 'Prüfvorlagen', coalesce(roof_type, '(jeder Dachtyp)'), count(*), NULL::boolean FROM inspection_templates GROUP BY roof_type
UNION ALL
SELECT 'Standardvorlage je Dachtyp', roof_type, count(*), NULL::boolean FROM roof_type_inspection_template_defaults GROUP BY roof_type
UNION ALL
SELECT 'Dachflächen', coalesce(roof_type, '(leer)'), count(*), NULL::boolean FROM roof_areas GROUP BY roof_type
UNION ALL
SELECT 'Schichttypen (Dachaufbau)', coalesce(roof_type, '(jeder Dachtyp)'), count(*), NULL::boolean FROM roof_layer_types GROUP BY roof_type
ORDER BY 1, 2;

SELECT t.ort, t.dachtyp, t.anzahl,
       (SELECT o.value FROM setting_options o JOIN setting_option_groups g ON g.id = o.group_id
         WHERE g.group_key = 'roof_types' AND lower(o.value) = lower(t.dachtyp) LIMIT 1) AS gleich_bis_auf_schreibweise
  FROM (
        SELECT 'Prüfvorlagen' AS ort, roof_type AS dachtyp, count(*) AS anzahl FROM inspection_templates WHERE roof_type IS NOT NULL GROUP BY roof_type
        UNION ALL SELECT 'Standardvorlage je Dachtyp', roof_type, count(*) FROM roof_type_inspection_template_defaults GROUP BY roof_type
        UNION ALL SELECT 'Dachflächen', roof_type, count(*) FROM roof_areas WHERE roof_type IS NOT NULL GROUP BY roof_type
        UNION ALL SELECT 'Schichttypen (Dachaufbau)', roof_type, count(*) FROM roof_layer_types WHERE roof_type IS NOT NULL GROUP BY roof_type
       ) t
 WHERE t.dachtyp NOT IN (SELECT o.value FROM setting_options o JOIN setting_option_groups g ON g.id = o.group_id
                          WHERE g.group_key = 'roof_types')
 ORDER BY 1, 2;

ROLLBACK;
