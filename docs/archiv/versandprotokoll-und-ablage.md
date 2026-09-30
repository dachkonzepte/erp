# Versandprotokoll und Ablage versendeter Dokumente (seit 1.8.17)

Stufe 2, Runde 2a-3a (Zählung aus dem Checklisten-Vorhaben, siehe `docs/archiv/modul-checklisten.md`,
Etappenplan). Vor jeder Änderung am E-Mail-Versand diese Datei lesen (Regel 14).

## Betreibervorgabe (30.09.2026)

1. Ablage: jedes versendete PDF genau so, wie es verschickt wurde, mit SHA-256, Dokumentart,
   Dokument-ID, Zeitpunkt und Benutzer. Nie überschreiben, nie löschen.
2. Versandprotokoll je Versand: An, CC, Betreff, Zeitpunkt, Kanal, Benutzer, Verweis auf die Ablage,
   eigene Kennung als X-Kopfzeile. Inhalte nur so weit Regel 18 erlaubt.
3. Eintrag vor dem Senden (in Arbeit), danach gesendet oder fehlgeschlagen. Hängengebliebene werden
   angezeigt, nie automatisch erneut gesendet.
4. Jeder Versandauftrag trägt einen Schlüssel, derselbe Schlüssel wird nie zweimal verschickt.
5. Graph und SMTP: mehrere Empfänger und CC, weiterhin nur Mail.Send (Regel 17), Größenprüfung gegen
   3 MB vor dem Senden mit klarer Meldung.
6. Alle bestehenden Versender (Angebot, Auftrag, Rechnung, Mahnung, Aufgaben-Mail) schreiben ins
   Protokoll, ihre PDFs landen in der Ablage.
7. Regel 18 in `checklist_rules.py` und im Folgen-Code: nur Klassenname, mit Test.
8. Tests mit Gegenprobe; die Graph-Attrappe verhält sich wie der echte Dienst.

## Aufbau

- **`app/email_dispatch.py::dispatch_email()`** ist der einzige Weg, eine Mail zu versenden.
  `app/email_sending.py::send_message()` ist nur noch der Transport (SMTP oder Graph) und hat keinen
  anderen Aufrufer; `send_email_with_attachment()`/`send_plain_email()` sind entfallen.
  `test_no_mail_leaves_the_system_past_the_dispatch_log` durchsucht `app/` per AST nach Aufrufen und
  Importen des Transports außerhalb dieser beiden Module.
- **Ablauf je Versandauftrag**: (1) Schlüssel schon bekannt? "gesendet" → vorhandener Eintrag zurück,
  nichts gesendet; "in_arbeit"/"fehlgeschlagen" → `DispatchConflict` (Router 409); ein Schlüssel eines
  anderen Dokuments → 400. (2) Vorab ohne Schreiben: Adressen (Komma, Semikolon, Zeilenumbruch;
  doppelte fallen weg, CC ohne die An-Adressen; höchstens 20), Konfiguration, Anhanggröße, läuft für
  dasselbe Dokument gerade ein anderer Versand (in Arbeit, jünger als 10 Minuten) → 409. (3) Eintrag
  "in_arbeit" im SAVEPOINT anlegen (Unique `dispatch_key`), commit. (4) PDF in die Ablage, Verweis,
  commit; scheitert das, wird nicht gesendet. (5) Senden mit `X-DK-Versand-ID: <message_ref>`, dann
  bedingtes UPDATE (nur aus "in_arbeit") auf "gesendet" bzw. "fehlgeschlagen".
- **Schlüssel**: die Seite erzeugt ihn je Klick (`_email_dispatch.html`, `postEmailDispatch()`); nach
  einer Antwort 2xx/4xx gibt es für den nächsten Klick einen neuen, bei keiner Antwort oder 5xx bleibt
  er -- ein erneuter Klick fragt dann mit demselben Schlüssel nach und sendet nicht doppelt. Die API
  verlangt ihn (`dispatch_key` Pflicht in den vier `*EmailSend`-Schemas, sonst 422). Direkte Aufrufe
  der Geschäftsfunktionen ohne Schlüssel bekommen einen einmaligen (Aufgaben-Mail, Tests).
- **Kennung**: `message_ref` (UUID) als `X-DK-Versand-ID`, bei Graph über `internetMessageHeaders`
  (Graph verlangt das Präfix "X-"). Damit lässt sich eine Mail im Postausgang eindeutig zuordnen --
  der Weg, einen hängengebliebenen Eintrag zu klären.
- **Größe**: `MAX_ATTACHMENT_BYTES = 3_000_000`. Graph nimmt mit sendMail höchstens 4 MB je Anfrage an
  (413 darüber); Base64 macht aus 3.000.000 Bytes 4.000.000, mit Text und JSON-Hülle bleibt die
  Anfrage unter 4 MiB. 3 MiB (3.145.728) ergäben in Base64 schon exakt 4 MiB -- beim Durchrechnen
  aufgefallen, deshalb die dezimale Grenze. Gilt für beide Wege gleich. Größere Anhänge bräuchten eine
  Upload-Sitzung an einem Entwurf, also Mail.ReadWrite -- ausgeschlossen (Regel 17).
- **Regel 18**: im Protokoll stehen Empfänger und Betreff, weil der Betreiber sie für den Nachweis
  verlangt; kein Mailtext, kein Anhang (der liegt in der Ablage), vom Fehler nur Klassenname der
  innersten Ursache und ihr Code (HTTP-Status, SMTP-Antwortcode). Der Fehlertext geht wie bisher nur an
  den Menschen, der gerade sendet.
- **Unveränderlich**: `SentDocument` ohne Änderung und Löschen, `EmailDispatch` ohne Löschen und nur
  der Abschluss aus "in_arbeit" (ORM-Ereignisse in `app/models.py`, `ArchiveImmutableError`; der
  gespeicherte Status wird dafür aus der Datenbank gelesen, weil die Attribut-Historie den alten Wert
  nur kennt, wenn er vorher geladen war -- im ersten Testlauf aufgefallen). Beide Tabellen ohne
  Fremdschlüssel auf Dokument und Benutzer (Muster `AuditLog`): die Ablage überdauert ein gelöschtes
  Angebot und einen gelöschten Benutzer, und die bekannte PostgreSQL-Falle beim Benutzer-Löschen
  (FKs auf `app_users` ohne `ON DELETE`) wächst nicht weiter. Die Datei wird mit `open(..., "xb")`
  angelegt, danach schreibgeschützt; `test_archive_code_has_no_way_to_delete_or_overwrite` prüft per
  AST, dass Ablage- und Versandcode weder löschen noch umbenennen noch überschreiben.
- **Prüfen**: `verify_sent_document()` rechnet die Prüfsumme neu (unverändert/abweichend/fehlt), nur
  auf Anfrage (liest die ganze Datei). `GET /api/sent-documents/{id}/file` liefert nur eine Datei mit
  stimmender Prüfsumme, sonst 409 (abweichend) bzw. 410 (fehlt).
- **Migration `b414df7c7744`**: zwei neue Tabellen. `downgrade()` bricht ab, sobald eine davon Einträge
  hat (sonst gingen Prüfsummen und Nachweis verloren); leer läuft er normal.

## Oberfläche und Rechte

- Rechnung, Auftrag, Angebot, Mahnung: Felder "An" (vorbelegt, mehrere mit Komma) und "CC",
  `type="email" multiple`; Knopf während der Anfrage gesperrt; Link "Versandprotokoll" auf das Dokument
  gefiltert (Mahnwesen: im Kopf).
- `/versandprotokoll` (Sidebar unter Finanzen): Liste neueste zuerst, Filter Status (inkl.
  "Hängengeblieben") und Art, `?typ=…&id=…` für ein Dokument, Warnkarte bei hängenden Einträgen, je
  Zeile Kennung, An/CC, Betreff, Weg und Benutzer, Status mit Fehlerklasse, Ablage mit Größe, gekürzter
  Prüfsumme, "PDF" und "Prüfen".
- Rechte: Lesen ab `buero_auftrag` (wer versendet, muss sehen, ob es hinausging), Monteure 403 an
  Seite und API. **Aufgaben-Benachrichtigungen nur für Admins**: ihr Betreff nennt den Aufgabentitel,
  und eine zugewiesene Aufgabe sieht außer dem Empfänger nur Admin (`list_tasks_for_user()`).
  Schreibende Endpunkte gibt es nicht.

## Umsetzung 1.8.17 (30.09.2026)

- **Dateien**: `app/email_dispatch.py`, `app/sent_documents.py` (neu), `app/email_sending.py`
  (`send_message()`, `check_attachment_size()`, `ensure_configured()`, mehrere Empfänger/CC/Kopfzeilen),
  Modelle und ORM-Sperren am Ende von `app/models.py`, `app/audit.py::current_actor()` (Benutzer der
  Anfrage für die Aufgaben-Mail), Versender in `invoices.py`/`orders.py`/`projects.py`/`reminders.py`/
  `tasks.py`, Router `app/routers/email_dispatches.py`, Seite `email_dispatches.html`, Include
  `_email_dispatch.html`, `.env.example` (`DACHKONZEPTE_SENT_DOCUMENT_ROOT`).
- **Regel 18 im Checklisten-Code**: `run_rules_after_completion()` protokolliert statt
  `logger.exception()` nur ID und Klassenname (bei einer SQLAlchemy-Ausnahme stand sonst die SQL mit
  Aufgabentitel und -beschreibung im Log). Der Folgen-Code tat das schon; beide jetzt mit Test (auch
  kein `exc_info`, kein Traceback).
- **Verifikation**: `tests/test_v321_email_dispatch.py` (35 Tests), zusätzlich gegen PostgreSQL
  (Wegwerf-Schema je Test in `spielwiese`), ebenso die angepassten alten Mail-Tests. Graph-Attrappe:
  Token als JSON mit Prüfung von grant_type/scope, sendMail 202 mit leerem Körper, 413 über 4 MiB,
  404 für jeden anderen Pfad, prüft Empfänger, X-Kopfzeilen und Base64 des Anhangs. Gegenproben (Schutz
  im Code ausgehebelt, Test rot, Datei byte-genau zurück): 25 rot -- Überschreiben, Prüfung ohne
  Nachrechnen, Auslieferung ohne Prüfsumme, löschbare Ablage, änderbarer Abschluss, Ablage nach dem
  Senden, Fehlertext im Protokoll, Hängende nicht erkannt, fehlender Unique-Schutz, fehlgeschlagener
  Schlüssel wiederholt, Parallelversand, Graph-Antwort als JSON gelesen, CC bei Graph, Kopfzeile, CC im
  SMTP-Umschlag, keine Größenprüfung, Grenze 3 MiB, Adressprüfung, Versand am Protokoll vorbei, Monteur
  liest, Aufgaben-Mails für jedes Büro, Versanddaten im Monteur-Auftrag, Regeln mit Traceback, Folge
  mit Meldung, Vorabprüfung UND Unique-Schutz zusammen. Nur die Vorabprüfung allein auszuhebeln blieb
  grün -- richtig so, der Unique-Schlüssel fängt den Doppelversand dann trotzdem ab. Migration SQLite
  und PostgreSQL hin/zurück/hin, `alembic check` sauber, Downgrade mit Bestand verweigert. Klicktest
  `scripts/klicktest_versandprotokoll.py` 33/33 (kleiner SMTP-Empfänger im Skript, Doppelklick = eine
  Mail, abgelehnter Empfänger, alle vier Seiten, Protokoll hell/dunkel/412 px, Monteur gesperrt).

### Nebenbefunde (nur gemeldet)

- **`logger.exception()` außerhalb des Checklisten-Codes**: `app/main.py` (unbehandelter Fehler je
  Anfrage) und fünf Jinja-Globals in `app/routers/pages.py` protokollieren mit Traceback. Bei einer
  SQLAlchemy-Ausnahme steht darin die SQL samt Parametern, also Inhalte (Regel 18). Nicht geändert.
- **Hängende Einträge lassen sich nicht klären**: sie bleiben "in Arbeit", bis jemand den Postausgang
  prüft -- eine Büro-Aktion "als gesendet/fehlgeschlagen bestätigen" mit Notiz fehlt. Nach 10 Minuten
  blockieren sie einen neuen Versand des Dokuments nicht mehr.
- **Parallelversand über zwei Tabs**: die Sperre "läuft gerade ein Versand dieses Dokuments" ist eine
  Vorabprüfung ohne Constraint; zwei Klicks mit verschiedenen Schlüsseln in derselben Sekunde kommen
  beide durch. Selten, nicht abgesichert.
- **Server-Sicherung**: die Ablage liegt unter `ERP_DATA_DIR/sent_documents`. Ob `/home/tobias/backup.sh`
  den ganzen Datenordner sichert, ist hier nicht prüfbar -- vor dem Einspielen nachsehen.
- **Echter Graph-Fehlercode bei zu großer Anfrage** nicht ohne Mandanten prüfbar; dokumentiert ist
  HTTP 413 ("Request entity too large"), die Attrappe antwortet so. Das Protokoll hält nur Klasse und
  Status fest, hängt also nicht am genauen Code.
- **PDF-Größen im Bestand unbekannt**: ob eine echte Rechnung mit Briefpapier-Hintergrund in die
  Nähe von 3 MB kommt, lässt sich nur auf dem Server sehen (`ls -l` der ersten abgelegten Dateien).
