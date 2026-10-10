-- Prüfabfrage Nummernkreise (seit 1.8.73): Dubletten und Lücken je Nummernkreis. NUR LESEN -- ändert nichts.
--
-- Aufruf auf dem Server (PostgreSQL), z. B.:
--     psql -d dachkonzepte -f scripts/pruefabfrage_nummernkreise.sql
--
-- Drei Ergebnisse:
--   1. Dubletten: jede Nummer, die in ihrem Nummernkreis mehr als einmal vergeben ist (unabhängig vom Format).
--   2. Lücken: je Nummernkreis und Gruppe (alles außer der laufenden Nummer, also z. B. "R-2026-") erste und letzte Nummer,
--      Anzahl, fehlende dazwischen (bis zu 50 aufgelistet) und wie viele vor der ersten fehlen, gemessen am Startwert.
--      Gezählt werden nur Nummern im aktuellen Format des Nummernkreises (Einstellungen -> Nummernkreise).
--   3. Nummern, die nicht zum aktuellen Format passen (Altsystem, früheres Format, von Hand) -- für Lücken nicht gezählt.
--
-- Rechnungen und Mahnungen im Entwurf haben keine Nummer und zählen nicht. Stornorechnungen gehören zum Kreis "invoice".
-- Eine Lücke bei Kunde, Anfrage, Projekt, Angebot oder Auftrag kann vom Löschen kommen, bei Rechnung und Mahnung ist sie
-- erklärungsbedürftig (GoBD) -- seit 1.8.73 reißt weder das Löschen eines Entwurfs noch ein Wettlauf eine.

WITH nummern AS (
    SELECT 'customer' AS kreis, customer_number AS nummer FROM customer_profiles
    UNION ALL SELECT 'inquiry', inquiry_number FROM inquiries
    UNION ALL SELECT 'project', project_number FROM projects
    UNION ALL SELECT 'quote', quote_number FROM quotes
    UNION ALL SELECT 'order', order_number FROM orders
    UNION ALL SELECT 'invoice', invoice_number FROM invoices
    UNION ALL SELECT 'reminder', reminder_number FROM reminders
)
SELECT kreis AS nummernkreis, nummer, count(*) AS anzahl
FROM nummern
WHERE nummer IS NOT NULL
GROUP BY kreis, nummer
HAVING count(*) > 1
ORDER BY kreis, nummer;

WITH nummern AS (
    SELECT 'customer' AS kreis, customer_number AS nummer FROM customer_profiles
    UNION ALL SELECT 'inquiry', inquiry_number FROM inquiries
    UNION ALL SELECT 'project', project_number FROM projects
    UNION ALL SELECT 'quote', quote_number FROM quotes
    UNION ALL SELECT 'order', order_number FROM orders
    UNION ALL SELECT 'invoice', invoice_number FROM invoices
    UNION ALL SELECT 'reminder', reminder_number FROM reminders
),
-- Format "R-{YYYY}-{NNNN}" -> regulärer Ausdruck ^(R-[0-9]{4}-)([0-9]+)()$: Gruppe 1 vor, 2 die laufende Nummer, 3 nach ihr.
teile AS (
    SELECT sequence_key AS kreis, start_value,
           substring(format_pattern FROM '^(.*?)\{N+\}') AS vor,
           substring(format_pattern FROM '\{N+\}(.*)$') AS nach
    FROM number_sequences
),
muster AS (
    SELECT kreis, start_value,
           '^(' || replace(replace(regexp_replace(vor, '([.^$*+?()\[\]\\|{}])', '\\\1', 'g'),
                                   '\{YYYY\}', '[0-9]{4}'), '\{YY\}', '[0-9]{2}')
           || ')([0-9]+)('
           || replace(replace(regexp_replace(nach, '([.^$*+?()\[\]\\|{}])', '\\\1', 'g'),
                              '\{YYYY\}', '[0-9]{4}'), '\{YY\}', '[0-9]{2}')
           || ')$' AS regex
    FROM teile
),
zerlegt AS (
    SELECT n.kreis, m.start_value, t[1] || '…' || t[3] AS gruppe, t[2]::bigint AS lauf
    FROM nummern n
    JOIN muster m ON m.kreis = n.kreis
    CROSS JOIN LATERAL regexp_match(n.nummer, m.regex) AS t
    WHERE n.nummer IS NOT NULL AND t IS NOT NULL  -- anderes Format: Ergebnis 3
),
gruppen AS (
    SELECT kreis, gruppe, min(start_value) AS start_value, min(lauf) AS erste, max(lauf) AS letzte,
           count(DISTINCT lauf) AS vergeben
    FROM zerlegt
    GROUP BY kreis, gruppe
)
SELECT g.kreis AS nummernkreis, g.gruppe, g.erste, g.letzte, g.vergeben,
       (g.letzte - g.erste + 1) - g.vergeben AS fehlend_dazwischen,
       (SELECT string_agg(f::text, ', ' ORDER BY f)
          FROM (SELECT f FROM generate_series(g.erste, g.letzte) AS f
                WHERE NOT EXISTS (SELECT 1 FROM zerlegt z WHERE z.kreis = g.kreis AND z.gruppe = g.gruppe AND z.lauf = f)
                ORDER BY f LIMIT 50) AS fehlt) AS fehlende_nummern,
       greatest(g.erste - g.start_value, 0) AS fehlend_vor_der_ersten
FROM gruppen g
ORDER BY g.kreis, g.gruppe;

WITH nummern AS (
    SELECT 'customer' AS kreis, customer_number AS nummer FROM customer_profiles
    UNION ALL SELECT 'inquiry', inquiry_number FROM inquiries
    UNION ALL SELECT 'project', project_number FROM projects
    UNION ALL SELECT 'quote', quote_number FROM quotes
    UNION ALL SELECT 'order', order_number FROM orders
    UNION ALL SELECT 'invoice', invoice_number FROM invoices
    UNION ALL SELECT 'reminder', reminder_number FROM reminders
),
teile AS (
    SELECT sequence_key AS kreis,
           substring(format_pattern FROM '^(.*?)\{N+\}') AS vor,
           substring(format_pattern FROM '\{N+\}(.*)$') AS nach
    FROM number_sequences
),
muster AS (
    SELECT kreis,
           '^' || replace(replace(regexp_replace(vor, '([.^$*+?()\[\]\\|{}])', '\\\1', 'g'),
                                  '\{YYYY\}', '[0-9]{4}'), '\{YY\}', '[0-9]{2}')
           || '[0-9]+'
           || replace(replace(regexp_replace(nach, '([.^$*+?()\[\]\\|{}])', '\\\1', 'g'),
                              '\{YYYY\}', '[0-9]{4}'), '\{YY\}', '[0-9]{2}')
           || '$' AS regex
    FROM teile
)
SELECT n.kreis AS nummernkreis, count(*) AS anzahl_anderes_format,
       array_to_string((array_agg(n.nummer ORDER BY n.nummer))[1:20], ', ') AS beispiele
FROM nummern n
JOIN muster m ON m.kreis = n.kreis
WHERE n.nummer IS NOT NULL AND n.nummer !~ m.regex
GROUP BY n.kreis
ORDER BY n.kreis;
