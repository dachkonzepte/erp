-- Prüfabfrage Auswahlwerte (seit 1.9.12, Stufe 2 Redesign, Runde 6 Punkt 1): welche gespeicherten Werte stehen in keiner Auswahlliste?
-- NUR LESEN -- läuft in einer schreibgeschützten Transaktion und endet mit ROLLBACK, ändert nichts.
--
-- Aufruf auf dem Server (als Benutzer tobias): die Verbindung aus /home/tobias/erp/.env -- derselbe Datenbank-Benutzer wie die Anwendung
-- (ein eigener steht in der Betriebsdoku nicht) --, ohne den Treiberzusatz "+psycopg", den psql nicht kennt; PGOPTIONS macht jede
-- Transaktion der Sitzung schreibgeschützt (doppelt zum BEGIN TRANSACTION READ ONLY unten):
--
--     cd /home/tobias/erp
--     set -a; source .env; set +a
--     PGOPTIONS='-c default_transaction_read_only=on' psql "${DATABASE_URL/postgresql+psycopg:/postgresql:}" -v ON_ERROR_STOP=1 -f scripts/pruefabfrage_auswahlwerte.sql
--
-- Ein Ergebnis: je Spalte jeder gespeicherte Wert, den die Auswahl auf der Seite nicht anbietet, mit Anzahl und Hinweis --
--   "inaktiv"                 ein abgeschalteter Eintrag der Auswahlliste (Optionsgruppe)
--   "Schreibweise: <Eintrag>" ein Eintrag, der nur in Groß-/Kleinschreibung abweicht (Optionsgruppe)
--   leer                      kein Eintrag (umbenannt, gelöscht, aus einem anderen Schreibweg)
-- Seit 1.9.12 bleibt jeder solche Wert auf der Seite gewählt und erhalten ("… (nicht mehr verfügbar)" bzw. "… (inaktiv)"); die Abfrage
-- zeigt, wie viele es gibt und welche. Bekannte Quellen bis 1.9.11: der Auftragsdialog bot "alternative" statt "alternativ" an, das
-- Formular "Kunde anlegen" schrieb "Telefon", "E-Mail", "Geburtstag", "Information" statt phone/email/birthday/info, die Umwandlung
-- einer Anfrage setzt den Projektstatus "angebot" (seit 1.9.12 in der Auswahl der Projektmappe).
-- Die festen Listen unten sind die Optionen der Seiten (Vorlage, Stand 1.9.12) -- tests/test_v447_auswahl_altwerte.py prüft sie dagegen.
-- Hintergrund: docs/archiv/redesign.md, "Punkt 1 (1.9.12)".

BEGIN TRANSACTION READ ONLY;

WITH gruppe AS (
  SELECT g.group_key, o.value, o.active FROM setting_options o JOIN setting_option_groups g ON g.id = o.group_id
), gruppenwerte AS (
  SELECT 'operational_assets.asset_type (Betriebsmittel, Typ)' AS spalte, 'resource_types' AS group_key, asset_type AS wert
    FROM operational_assets WHERE asset_type IS NOT NULL AND resource_id IS NULL
  UNION ALL
  SELECT 'operational_asset_inspections.inspection_type (Betriebsmittel, Prüfungsart)', 'operational_asset_inspection_types', inspection_type
    FROM operational_asset_inspections WHERE inspection_type IS NOT NULL
  UNION ALL
  SELECT 'recurring_costs.category (Betriebskosten, Kategorie)', 'recurring_cost_categories', category
    FROM recurring_costs WHERE category IS NOT NULL
), feste_werte AS (
  SELECT 'order_items.position_type (Auftrag, Positionsart)' AS spalte, position_type AS wert,
         position_type IN ('normal', 'zulage', 'bedarf', 'alternativ') AS in_liste FROM order_items
  UNION ALL SELECT 'quote_items.position_type (Angebot, Positionsart)', position_type,
         position_type IN ('normal', 'zulage', 'bedarf', 'alternativ') FROM quote_items
  UNION ALL SELECT 'customer_extra_infos.info_type (Kunde, Zusatzinfo)', info_type,
         info_type IN ('phone', 'email', 'birthday', 'info') FROM customer_extra_infos
  UNION ALL SELECT 'projects.status (Projektmappe)', status,
         status IN ('anfrage', 'angebot', 'planung', 'beauftragt', 'ausfuehrung', 'abgeschlossen') FROM projects
  UNION ALL SELECT 'orders.status (Auftrag)', status,
         status IN ('beauftragt', 'arbeitsvorbereitung', 'in_ausfuehrung', 'pausiert', 'abgeschlossen', 'storniert') FROM orders
  UNION ALL SELECT 'quotes.status (Angebot)', status,
         status IN ('entwurf', 'versendet', 'in_pruefung', 'beauftragt', 'abgelehnt') FROM quotes
  UNION ALL SELECT 'planning_slots.status (Plantafel)', status,
         status IN ('geplant', 'bestaetigt', 'in_ausfuehrung', 'pausiert', 'abgeschlossen') FROM planning_slots
  UNION ALL SELECT 'work_preparations.status (Arbeitsvorbereitung)', status,
         status IN ('offen', 'in_planung', 'bereit', 'in_ausfuehrung', 'abgeschlossen') FROM work_preparations
  UNION ALL SELECT 'work_preparation_materials.status (Arbeitsvorbereitung, Material)', status,
         status IN ('bedarf', 'bestellt', 'teilgeliefert', 'geliefert', 'entfaellt') FROM work_preparation_materials
  UNION ALL SELECT 'work_preparation_tasks.status (Arbeitsvorbereitung, Aufgabe)', status,
         status IN ('offen', 'in_arbeit', 'erledigt') FROM work_preparation_tasks
  UNION ALL SELECT 'work_preparation_tasks.priority (Arbeitsvorbereitung, Aufgabe)', priority,
         priority IN ('niedrig', 'normal', 'hoch', 'dringend') FROM work_preparation_tasks
  UNION ALL SELECT 'tasks.priority (Aufgaben)', priority, priority IN ('niedrig', 'normal', 'hoch', 'dringend') FROM tasks
  UNION ALL SELECT 'roof_layer_types.option_group (Einstellungen, Schichttyp)', option_group,
         option_group IN (SELECT group_key FROM setting_option_groups WHERE group_key LIKE 'layer\_%') FROM roof_layer_types
   WHERE option_group IS NOT NULL AND option_group <> ''
  UNION ALL SELECT 'checklist_template_rules.field_key (Checklisten-Vorlage, Regel)', r.field_key,
         EXISTS (SELECT 1 FROM checklist_template_fields f WHERE f.version_id = r.version_id AND f.field_key = r.field_key)
    FROM checklist_template_rules r WHERE r.field_key IS NOT NULL AND r.field_key <> ''
  UNION ALL SELECT 'checklist_template_rules.operand (Checklisten-Vorlage, Regel „enthält Option“)', r.operand,
         EXISTS (SELECT 1 FROM checklist_template_fields f JOIN checklist_template_field_options fo ON fo.field_id = f.id
                  WHERE f.version_id = r.version_id AND f.field_key = r.field_key AND fo.option_key = r.operand)
    FROM checklist_template_rules r WHERE r.operator = 'enthaelt'
)
SELECT spalte, wert, anzahl, hinweis FROM (
  SELECT w.spalte, w.wert, count(*) AS anzahl,
         CASE WHEN bool_or(g.active IS NOT NULL) THEN 'inaktiv'
              ELSE (SELECT 'Schreibweise: ' || min(g2.value) FROM gruppe g2 WHERE g2.group_key = w.group_key AND lower(g2.value) = lower(w.wert))
         END AS hinweis
    FROM gruppenwerte w LEFT JOIN gruppe g ON g.group_key = w.group_key AND g.value = w.wert
   GROUP BY w.spalte, w.group_key, w.wert
  HAVING NOT bool_or(coalesce(g.active, false))
  UNION ALL
  SELECT spalte, coalesce(wert, '(leer)'), count(*), NULL FROM feste_werte WHERE NOT coalesce(in_liste, false) GROUP BY spalte, wert
) t
ORDER BY 1, 2;

ROLLBACK;
