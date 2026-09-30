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
  "in_arbeit" im SAVEPOINT anlegen (Unique `dispatch_key`, seit 1.8.19 auch Unique `lock_key`), commit. (4) PDF in die Ablage, Verweis,
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

(Die Punkte "Hängende Einträge lassen sich nicht klären" und "Parallelversand über zwei Tabs" sind mit
1.8.19 erledigt, siehe unten.)

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

## Umsetzung 1.8.19 (30.09.2026) -- Runde 2a-3b, Teil 1 (Punkte 1–4)

Betreibervorgabe Runde 2a-3b ("Versand fertigstellen"), neun Punkte; bei zu großem Umfang nach Punkt 4
committen. 1.8.19 = Punkte 1–4, der Rest folgt als eigene Version.

- **1. Sperre "läuft gerade" in der Datenbank**: neue Spalte `email_dispatches.lock_key` (Unique,
  leer erlaubt), beim Anlegen `"<art>:<id>"`, beim Abschluss (`_finish()`) und beim Klären wieder leer.
  Die Vorabprüfung `_running_dispatch()` bleibt für die Meldung im Normalfall; entscheidend ist der
  Unique-Schlüssel im SAVEPOINT. Nach einer `IntegrityError` wird unterschieden: derselbe
  `dispatch_key` → wie bisher `_existing()`, sonst → 409 `RUNNING_TEXT`, nichts geschrieben. Ein
  hängender Eintrag (älter als 10 Minuten) gibt seine Sperre beim nächsten Versand ab
  (`_release_stale_lock()`, bedingtes UPDATE in derselben Transaktion) und bleibt "in Arbeit" sichtbar --
  dasselbe Verhalten wie seit 1.8.17. Aufgaben-Mails (`block_parallel=False`) tragen keine Sperre.
  Einträge von vor der Migration haben keine Sperre; ein beim Einspielen laufender Versand ist über die
  Vorabprüfung geschützt.
- **2. Adressen**: `address_problem()`/`parse_recipients()` -- dot-atom vor dem @, Labels aus
  Buchstaben/Ziffern/Bindestrich (nicht am Rand), Endung aus Buchstaben oder `xn--`, Länge 254/64,
  "Name <adresse>" wird gekürzt, Grund in der Meldung. Umlaute bleiben erlaubt (IDN, internationale
  Postfächer). Dieselben Regeln im Browser (`_email_dispatch.html`, `checkEmailAddresses()` vor der
  Anfrage, der Schlüssel bleibt dann unverbraucht). Felder An/CC: `type="text" inputmode="email"`.
  Graph: `graph_send_error_text()` (sendMail) und `graph_token_error_text()` (Token-Endpunkt,
  AADSTS-Codes) in `app/email_sending.py`; unbekannte Codes mit Microsofts Meldung, 5xx als Störung.
  SMTP: `SMTPRecipientsRefused`/`SMTPSenderRefused` mit eigener Meldung. Im Protokoll unverändert nur
  Klasse und HTTP-Status/SMTP-Code (Regel 18); die Übersetzung geht nur an den Menschen.
- **3. Hängende Einträge klären**: `resolve_stuck_dispatch()` + `POST /api/email-dispatches/{id}/resolve`
  (ab `buero_auftrag`; Aufgaben-Benachrichtigung nur Admin, sonst 404). Nur "in_arbeit" und älter als
  10 Minuten (409 "läuft womöglich noch"), Notiz 3–1000 Zeichen, bedingtes UPDATE (409 "inzwischen
  geklärt"). Neue Spalten `resolved_at`, `resolved_by_user_id`, `resolved_by_name`, `resolution_note`;
  `finished_at` bleibt leer (wann die Mail tatsächlich hinausging, weiß nur der Postausgang). Historie:
  `record_audit_entry()` mit Art "Versand" (Bezeichnung: Dokument + Kennung, nie Betreff/Empfänger),
  `project_id` des Dokuments; bei einer Aufgaben-Benachrichtigung an der Aufgabe (nur Admin sieht sie,
  Muster 1.8.18). Oberfläche: in der Zeile eines hängenden Eintrags Notizfeld und zwei Knöpfe, danach
  "Von Hand geklärt · Name, Zeit" mit Notiz. Die ORM-Sperre bleibt: ein geklärter Eintrag ist
  abgeschlossen und unveränderlich.
- **4. Aus der Ablage**: `frozen_version()`/`frozen_or_fresh_pdf()` in `app/sent_documents.py`,
  `FROZEN_AFTER_FIRST_DISPATCH = {"rechnung", "mahnung"}` (Storno = Rechnung). Maßgeblich ist die zuerst
  abgelegte Fassung, deren Versand nicht "fehlgeschlagen" ist -- ein hängender zählt (womöglich beim
  Kunden), bis das Büro ihn als fehlgeschlagen klärt. Nachdruck/Download (`GET /api/invoices/{id}/pdf`,
  `GET /api/reminders/{id}/pdf`, gemeinsam `document_pdf_response()` im Router des Protokolls) liefern
  sie mit Kopfzeile `X-DK-Ablage`; der erneute Versand hängt sie an und verweist per
  `archived_document` auf denselben Ablage-Eintrag (keine zweite Datei; `dispatch_email()` prüft, dass
  die Bytes zur Prüfsumme passen). Datei verändert/fehlt: Download 409/410, Versand verweigert, nie
  still neu erzeugt. Rechnungen ohne E-Mail-Versand (vor 1.8.17, nur gedruckt) werden weiter neu erzeugt.
- **Migration `304d6a607767`**: fünf Spalten, Unique-Constraint `uq_email_dispatches_lock_key`.
  `downgrade()` verweigert, sobald ein Eintrag geklärt ist (Wer/Wann/Notiz gingen verloren). SQLite und
  PostgreSQL hin/zurück/hin, `alembic check` sauber, doppelte Sperre von beiden Datenbanken abgelehnt,
  mehrere leere erlaubt, Downgrade mit geklärtem Eintrag verweigert.
- **Graph-Attrappe** (`tests/test_v321_email_dispatch.py`): lehnt formal ungültige Empfänger wie Exchange
  mit 400 `ErrorInvalidRecipients` ab (eigene Prüfung im Test, nicht aus `app/` übernommen), Fehlercode
  und Anmeldefehler einstellbar.
- **Verifikation**: `tests/test_v323_dispatch_completion.py` (49 Tests, darunter zwei Tabs in derselben
  Sekunde mit zwei SQLite-Verbindungen, zwei Threads gegen PostgreSQL im Wegwerf-Schema, neun Adressen,
  die 1.8.18 durchließ und Exchange ablehnt, Nachdruck byte-gleich nach geändertem Briefkopf für
  Rechnung, Storno und Mahnung). Gegenproben (Schutz ausgehebelt, Test rot, Datei byte-genau zurück):
  16 rot -- Sperre nie gesetzt, Sperre bleibt nach Abschluss, hängender hält Sperre, alte Adressprüfung,
  Graph-Fehler roh, Anmeldefehler roh, SMTP-Ablehnung ohne Meldung, Klärung ohne Bedingung, Klärung für
  laufenden Versand, Klärung ohne Historie, Aufgaben-Mail vom Büro klärbar, Nachdruck neu erzeugt,
  fehlgeschlagener friert ein, beschädigte Ablage still neu erzeugt, erneuter Versand legt noch einmal
  ab, Anhang nicht gegen Ablage geprüft. Dabei im eigenen Test gefunden: die Gegenprobe "Klärung ohne
  Bedingung" blieb zuerst grün, weil der Test das in Session B geladene Objekt nicht festhielt -- die
  Identity-Map hält nur schwach, `get()` las danach frisch und die Vorabprüfung fing es ab; der Test
  prüfte das Fenster also gar nicht. Behoben (Referenz halten, Zustand vor dem Aufruf prüfen), danach
  rot. Zwei alte Strukturtests erwarteten `type="email"` und wurden angepasst. Volle Suite grün.
  Klicktest `scripts/klicktest_versandprotokoll.py` 45/45 (Textfeld, ungültige Adresse mit Grund ohne
  Anfrage, deutsche SMTP-Ablehnung, Nachdruck per SHA-256 gleich dem Anhang, Klären ohne und mit Notiz).

### Nebenbefunde 1.8.19 (nur gemeldet)

- **Teilweise abgelehnte Empfänger bei SMTP**: `smtplib.sendmail()` wirft nur, wenn der Server ALLE
  Empfänger ablehnt; lehnt er einige ab, geht die Mail an die übrigen, der Eintrag steht auf "gesendet"
  und niemand erfährt, wer fehlte (`sendmail()` gibt die Abgelehnten nur zurück). Nicht geändert.
- **Graph meldet unbekannte externe Empfänger nicht beim Senden**: `ErrorInvalidRecipients` kommt nur
  bei formal ungültigen Adressen; ein nicht existierendes Postfach bei einem fremden Anbieter ergibt
  später eine Unzustellbarkeitsnachricht im Absender-Postfach, das Protokoll bleibt "gesendet". Das ERP
  liest den Posteingang nicht (nur Mail.Send, Regel 17).
