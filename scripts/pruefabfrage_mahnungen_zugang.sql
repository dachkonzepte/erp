-- Prüfabfrage Mahnungen ohne Zugang (seit 1.8.80, Vorgabe Z2b "Vorweg" 2). NUR LESEN -- ändert nichts.
--
-- Aufruf auf dem Server (PostgreSQL) nach dem Einspielen von 1.8.80, z. B.:
--     psql -d dachkonzepte -f scripts/pruefabfrage_mahnungen_zugang.sql
--
-- Seit 1.8.80 ist eine Mahnstufe erst erreicht, wenn ihre Mahnung hinausging: per E-Mail gesendet oder als Zustellung
-- nachgetragen (Einschreiben, Übergabe, Bote, Fax), nicht als unzustellbar vermerkt (app/email_dispatch.py::document_reached_on()).
-- Bis 1.8.79 zählte schon das Festschreiben. Eine Mahnung, die ausgedruckt und per Post verschickt wurde, ohne dass jemand die
-- Zustellung nachgetragen hat, zählt deshalb jetzt nicht -- die Rechnung zeigt dann "… ging noch nicht hinaus", und als Nächstes
-- käme wieder dieselbe Stufe (als Ersatz). Ausweg: im Mahnwesen bzw. auf der Rechnungsseite die Zustellung nachtragen (mit dem
-- tatsächlichen Datum).
--
-- Ergebnis: festgeschriebene, nicht ersetzte Mahnungen ohne gesendeten Eintrag im Versandprotokoll und ohne E-Mail-Versand von
-- vor dem Versandprotokoll (email_sent_at). Unzustellbare und reine Kopien an Beteiligte prüft die App genauer -- diese Liste
-- zeigt nur die, bei denen gar nichts vermerkt ist.

SELECT r.reminder_number AS mahnung, r.level AS stufe, r.reminder_date AS mahndatum, i.invoice_number AS rechnung,
       i.customer_name AS kunde
FROM reminders r
JOIN invoices i ON i.id = r.invoice_id
WHERE r.status = 'versendet'
  AND r.replaced_by_id IS NULL
  AND r.email_sent_at IS NULL
  AND NOT EXISTS (SELECT 1 FROM email_dispatches d
                  WHERE d.document_type = 'mahnung' AND d.document_id = r.id AND d.status = 'gesendet')
ORDER BY r.reminder_date, r.reminder_number;
