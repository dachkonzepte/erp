-- Prüfabfrage Auftrag und Kunde (seit 1.8.80, Vorgabe Z2b "Vorweg" 1). NUR LESEN -- ändert nichts.
--
-- Aufruf auf dem Server (PostgreSQL) nach dem Einspielen von 1.8.80, z. B.:
--     psql -d dachkonzepte -f scripts/pruefabfrage_auftrag_kunde.sql
--
-- Die Migration 8e2f4b6d1c97 gibt jedem Auftrag den Kunden seines Projekts am Tag der Migration (orders.customer_id). Wurde der
-- Kunde am Projekt nach dem Beauftragen gewechselt (bis 1.8.79 ohne Rechnung und Vertrag möglich), trägt der Auftrag danach den
-- neuen Kunden, im Schnappschuss aber noch den Namen des alten -- und jede künftige Rechnung übernimmt Name und Anschrift vom
-- Auftrag. Zwei Ergebnisse:
--   1. Aufträge, deren Kundenname im Schnappschuss nicht der Name ihres Kunden ist. Kann auch harmlos sein (Kunde nach dem
--      Beauftragen im Kundenstamm umbenannt). Bei einem echten Wechsel: in der Projektmappe den Kunden einmal auf den richtigen
--      stellen (mit Begründung) -- das schreibt Kunde, Name und Anschrift in Auftrag und Rechnungsentwürfe.
--   2. Festgeschriebene Rechnungen, deren festgehaltener Kunde nicht der Kunde ihres Auftrags ist (sollte leer sein).

SELECT o.order_number AS auftrag, o.customer_name AS name_im_auftrag, c.name AS kunde_des_auftrags,
       p.project_number AS projekt, o.order_date AS auftragsdatum
FROM orders o
JOIN customers c ON c.id = o.customer_id
JOIN projects p ON p.id = o.project_id
WHERE o.customer_name <> c.name
ORDER BY o.order_number;

SELECT i.invoice_number AS rechnung, i.customer_name AS name_in_rechnung, ci.name AS kunde_der_rechnung,
       o.order_number AS auftrag, co.name AS kunde_des_auftrags
FROM invoices i
JOIN orders o ON o.id = i.order_id
JOIN customers ci ON ci.id = i.customer_id
JOIN customers co ON co.id = o.customer_id
WHERE i.status <> 'entwurf' AND i.customer_id <> o.customer_id
ORDER BY i.invoice_number;
