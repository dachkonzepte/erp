# KI-Fundament

Ausgelagert aus CLAUDE.md am 2026-09-28 im Zuge der Aufteilung in eine schlanke
CLAUDE.md plus themensortiertes Archiv (siehe CLAUDE.md, Abschnitt "Modulübersicht",
und `docs/archiv/regel-abgleich.md` für die vollständige Zuordnung). Der Inhalt ist
wortgetreu (per Skript, zeilenweise) aus der vorherigen CLAUDE.md übernommen, keine
Umformulierung. Versionsangaben ("seit 1.x.y") beziehen sich auf den Stand zum
jeweiligen Zeitpunkt der ursprünglichen Aufzeichnung.

---

## KI-Fundament (seit 1.6.2)

Fundament für künftige KI-Funktionen im ERP (Belegauswertung, Angebotstexte,
Berichtszusammenfassung) -- eine zentrale, anbieter-unabhängige Schnittstelle. **In dieser
Version wird keine konkrete KI-Funktion gebaut und kein Anbieter festgelegt** -- ausschließlich
die Schnittstelle, an die sich künftige Funktionen anhängen. Erst ein vollständiger Befund
(Zugangsdaten-Verschlüsselung, bestehendes HTTP+Schlüssel-Muster, Modul-/Einstellungssystem),
dann nach Bestätigung des Adapter-Zuschnitts gebaut, mit drei vom Betreiber vorgegebenen
Entscheidungen (Mock-Adapter statt echtem Anbieter, synchron mit hartem Zeitlimit für den
Anfang, Kostenprotokoll ohne Inhalt).

### Befund

- **Zugangsdaten-Verschlüsselung**: `app/crypto.py::encrypt_secret()`/`decrypt_secret()`
  (Fernet, Schlüssel abgeleitet von `secret_key()` aus `app/auth.py`) ist bereits generisch --
  bisher genutzt für SMTP-Passwort und Microsoft-Graph-Client-Secret, beide als
  `*_encrypted`-Spalten auf `SmtpSettings`. `AISettings.api_key_encrypted` nutzt denselben
  Mechanismus unverändert, keine Erweiterung nötig.
- **Übertragbares HTTP+Schlüssel-Muster**: `app/email_sending.py` (Microsoft Graph) ist die
  einzige bestehende externe-HTTP-Dienst-mit-Schlüssel-Anbindung -- nutzt bewusst reines
  `urllib` (Stdlib), nicht `httpx` (obwohl in `requirements.txt`), mit festen, im Code
  verankerten Timeout-Konstanten (`GRAPH_TOKEN_TIMEOUT=15`, `GRAPH_SEND_TIMEOUT=30`) und
  einheitlicher Übersetzung jeder technischen Ausnahme in eine klare `ValueError`. Genau dieses
  Muster ist auf das KI-Fundament übertragen (siehe `AI_CALL_TIMEOUT_SECONDS`,
  `AIProviderError`-Hierarchie unten).
- **Modul-/Einstellungssystem**: `OPTIONAL_MODULES` (`app/modules.py`) ist für abschaltbare
  FACHFUNKTIONEN gedacht, nicht für reine Systemkonfiguration ohne eigene Funktion --
  **bewusst KEIN Eintrag dort für "KI"**, analog zu den E-Mail-Einstellungen, die ebenfalls
  keinen Modul-Eintrag haben. Stattdessen `require_admin()` an jedem Endpunkt (Muster
  `app/routers/email_settings.py`), und `AISettings.enabled` als der eigentliche
  Gesamtschalter für KI-Funktionen (nicht der Modul-Umschalter).

### Die zentrale Schnittstelle

Fünf neue, flache Module (Projektkonvention: `app/*.py`, keine Unterpakete):

- **`app/ai_types.py`**: `AIRequest` (`caller`/`prompt`/`attachments`/`system`),
  `AIResponse` (`text`/`input_tokens`/`output_tokens`/`cost_estimate`), `AIAttachment`
  (`mime_type`/`data`/`filename` -- vorgesehen für eine künftige Belegauswertung, in dieser
  Version von keiner Fachfunktion befüllt), sowie die Fehlerhierarchie `AIProviderError` ->
  `AIProviderNotConfigured`/`AIProviderUnavailable`. `AI_PROVIDERS = ("anthropic", "openai",
  "azure_openai", "google")` -- fester Code-Wert wie `RecurringCost.billing_interval`, keine
  Optionsgruppe (die Auswahl bestimmt, welcher Adapter dispatcht wird, eine Rechenregel).
- **`app/ai_adapters.py`**: `AIProviderAdapter` (Protocol, eine Methode `complete(request, *,
  timeout)`), `MockAIAdapter` (siehe unten), `_ADAPTERS`-Registry (`dict[str, Factory]`).
- **`app/ai_settings.py`**: `get_or_create_ai_settings()`/`update_ai_settings()`/
  `is_ai_available()` -- Muster `app/email_sending.py`, Singleton wie `SmtpSettings`.
- **`app/ai_service.py`**: `call_ai()`/`call_ai_async()` -- die EINEN Stellen, durch die jeder
  künftige KI-Aufruf laufen soll. Liest die Konfiguration, wählt über `_ADAPTERS` den Adapter,
  ruft ihn mit Zeitlimit auf, protokolliert. Kein anderer Code importiert je eine
  Adapter-Klasse direkt.
- **`app/routers/ai_settings.py`**: `GET/PUT /api/ai-settings` + `POST /api/ai-settings/test`,
  ausnahmslos `require_admin()` -- Systemkonfiguration, nicht einmal `buero_finanzen`
  (Betreibervorgabe, anders als z. B. Kalkulationsgrundlagen). Antwortschema liefert nie den
  Schlüssel selbst, nur `has_api_key: bool` (Muster `SmtpSettingsOut`).

Ein Anbieterwechsel ändert dadurch tatsächlich nur eine Datenbankzeile (`AISettings.provider`)
-- kein Code, der einen Anbieter kennt, wird dafür angefasst.

### Mock-Adapter statt echtem Anbieter (Betreiberentscheidung)

Kein einziger echter Anbieter-Adapter in dieser Version -- auch kein "minimaler, aber
austauschbarer" für einen bestimmten Anbieter, wie ursprünglich als Option vorgeschlagen.
Stattdessen `MockAIAdapter` (`app/ai_adapters.py`): liefert eine feste Testantwort ohne jeden
Netzwerkzugriff, optional mit `raise_error=...` für gezielte Fehlerpfad-Tests. Macht die
gesamte Testsuite unabhängig von externen Diensten (Betreibervorgabe: "eine Testsuite darf nie
einen echten KI-Aufruf machen") -- alle 24 neuen Tests (`tests/test_v295_ai_fundament.py`)
laufen ohne jede Netzwerkverbindung.

**"mock" ist bewusst NICHT in `AI_PROVIDERS` enthalten** und kann über `update_ai_settings()`
(den einzigen Schreibweg der Admin-Oberfläche) nie persistiert werden -- geprüft per
`ValueError`. Erreichbar ist der Mock ausschließlich über `call_ai(..., adapter_override=...)`,
ein Parameter, der ausdrücklich für Tests gedacht ist. Damit kann ein Admin "mock" niemals
versehentlich als echten Anbieter wählen, aber die Testsuite deckt trotzdem die VOLLE
Dispatch-/Zeitlimit-/Protokoll-Logik von `call_ai()` ab, nicht nur eine isolierte Attrappe.

Ein künftiger, echter Anbieter ist ein neuer Eintrag in `_ADAPTERS` unter dem jeweiligen
`AI_PROVIDERS`-Wert -- `call_ai()` selbst muss dafür nicht angefasst werden. Bis dahin liefert
ein bereits eingetragener Anbieter (z. B. `provider="anthropic"`, `enabled=True`) bei jedem
Aufruf weiterhin `AIProviderNotConfigured` ("kein Adapter hinterlegt") -- derselbe
Normalzustand wie "gar kein Anbieter gewählt", nur mit spezifischerer Meldung.

### Synchron mit hartem Zeitlimit -- die bewusste Wahl für den Anfang, und wo ein Hintergrund-Ablauf andocken würde

**Betreibervorgabe**: für die künftige Belegauswertung ist ein wartender Nutzer beim Anlegen
einer Rechnung vertretbar (wie bei einem Upload) -- deshalb synchron, mit
`AI_CALL_TIMEOUT_SECONDS = 45.0` (fest im Code, NICHT in den Einstellungen editierbar, Muster
`GRAPH_SEND_TIMEOUT`) als hartes Zeitlimit.

**Wo ein späterer Hintergrund-Ablauf andocken würde, ohne die Schnittstelle umzubauen**: die
Signatur `AIRequest` rein / `AIResponse` raus (oder eine der beiden `AIProviderError`-Klassen)
bliebe unverändert. Eine künftige, lange laufende KI-Funktion (Minuten statt Sekunden, z. B.
ein langer Bericht) würde `call_ai()` nicht anders aufrufen, sondern von einem ANDEREN
Ausführungskontext aus (ein Hintergrund-Task/Worker statt direkt im Request-Response-Zyklus) --
die aufrufende Fachfunktion würde sofort mit einem "wird verarbeitet"-Status antworten und der
Hintergrund-Task würde `call_ai()` normal aufrufen, das Ergebnis in einer neuen, eigenen
Job-Tabelle ablegen (NUR Status + `AIResponse`, niemals die Anfrage selbst -- die
Datenschutz-Zusage unten gilt unverändert). `call_ai()`/`call_ai_async()` selbst bräuchten dafür
keine Änderung, nur einen zweiten, später hinzukommenden Aufrufer.

**Sicherheitsnetz-Timeout, unabhängig vom Adapter-Verhalten**: `_run_with_timeout()`
(`app/ai_service.py`) führt `adapter.complete()` in einem eigenen `ThreadPoolExecutor`-Thread
aus und erzwingt `AI_CALL_TIMEOUT_SECONDS` über `future.result(timeout=...)` -- unabhängig
davon, ob der Adapter sein eigenes `timeout`-Argument tatsächlich beachtet. **Fallstrick, der
beim Bauen gefunden und behoben wurde**: ein `with ThreadPoolExecutor(...) as executor:` ruft
bei `__exit__` IMMER `shutdown(wait=True)` auf -- das hätte den rufenden Thread bei einer
Zeitüberschreitung erneut blockiert, bis der (hängende) Hintergrund-Thread fertig ist, und den
Zweck des Zeitlimits genau dann zunichtegemacht, wenn er am nötigsten ist. Behoben durch
explizites `executor.shutdown(wait=False)` im `finally`-Block -- der rufende Thread kehrt
garantiert spätestens nach 45s zurück, der verwaiste Hintergrund-Thread darf unabhängig davon
zu Ende laufen. Als Regressionstest festgehalten
(`test_call_ai_never_blocks_beyond_the_timeout_even_if_the_adapter_ignores_it`, misst die
tatsächliche Rückkehrzeit gegen einen absichtlich hängenden Test-Adapter).

**Aus async-Code ausschließlich `call_ai_async()` verwenden, nie `call_ai()` direkt** --
`call_ai()` selbst blockiert den rufenden Thread bis zu 45s; direkt aus einer `async def`-Route
aufgerufen würde das die Event-Loop blockieren (derselbe Fehlertyp, der in dieser Datei bereits
für `post_service_report_photo()`/Bildverkleinerung dokumentiert ist). `call_ai_async()` reicht
über `starlette.concurrency.run_in_threadpool()` an Starlettes Threadpool weiter. Aus einer
gewöhnlichen `def`-Route (von Starlette automatisch threadgepoolt) `call_ai()` direkt
verwenden.

### Untersuchung: trägt synchron auf dem Produktivserver?

**Korrektur (nach Server-Verifikation durch den Betreiber, direkt im Anschluss an diese
Version)**: die vorherige Fassung dieses Abschnitts ging von "ein Arbeitsprozess" aus -- eine
zu diesem Zeitpunkt bereits an anderer Stelle in dieser Datei falsch dokumentierte Prämisse
(siehe die Korrektur unter "Produktivbetrieb" oben). Der Betreiber hat den tatsächlichen
`ExecStart` der systemd-Unit auf dem VPS eingesehen: `gunicorn -w 2 --timeout 120` -- **zwei**
Arbeitsprozesse, `--timeout` tatsächlich explizit gesetzt (nicht der gunicorn-Standardwert).
Diese eigene Einschätzung stand ausschließlich auf der Ein-Prozess-Annahme, wo es um die
KONSEQUENZ eines Fehlers ging (siehe unten) -- der Timeout-Mechanismus selbst, die
`call_ai_async()`-Regel und das gesamte übrige Fundament (Mock-Adapter, Protokoll,
Einstellungen) hängen an keiner Stelle von der Prozesszahl ab, siehe die Prüfung am Ende dieses
Abschnitts.

**Zwei Prozesse bedeuten zwei unabhängige asyncio-Event-Loops mit je eigenem
Starlette-Threadpool** -- kein gemeinsamer Speicher, keine gemeinsame Warteschlange zwischen
beiden gunicorn-Arbeitsprozessen. Das ändert die Einschätzung an genau einer Stelle:

- **Gesamtkapazität**: GRÖSSER als mit einem Prozess, nicht kleiner -- wie vom Betreiber
  richtig eingeschätzt, unkritisch. Zwei Threadpools statt einem, mehr gleichzeitig lauffähige
  KI-Aufrufe, bevor irgendein Engpass entsteht.
- **Die `call_ai_async()`-Regel bleibt GENAUSO wichtig, nicht weniger** -- nur ihre Konsequenz
  bei Verstoß ist jetzt genauer zu benennen: eine `async def`-Route, die `call_ai()` DIREKT
  (ohne `run_in_threadpool`) aufruft, blockiert die Event-Loop GENAU DES EINEN
  Arbeitsprozesses, der diese Anfrage bearbeitet -- also die Hälfte der Gesamtkapazität, nicht
  alles und nicht nichts. Das ist exakt die ursprünglich (vor der fälschlichen "ein
  Prozess"-Korrektur der letzten Runde) vom Betreiber selbst benannte Formulierung
  ("die Hälfte der Kapazität") -- sie war die ganze Zeit richtig, die Korrektur der letzten
  Runde war es nicht. Der andere Arbeitsprozess bleibt von einer blockierten Event-Loop des
  ersten vollständig unberührt (kein gemeinsamer Zustand) und bedient währenddessen weiterhin
  jede Anfrage, die gunicorn ihm zuteilt -- "die Hälfte der Kapazität" ist damit trotzdem ein
  ernstzunehmender, kein vernachlässigbarer Ausfall: für die Dauer der Blockade (bis zu
  `AI_CALL_TIMEOUT_SECONDS`) bekommt etwa jede zweite neue Anfrage keine Bearbeitung, real
  spürbar für alle gerade angemeldeten Personen, nicht nur ein theoretisches Risiko.
- **`--timeout 120` jetzt bestätigt statt nur vermutet**: mit `AI_CALL_TIMEOUT_SECONDS = 45`
  deutlich darunter -- ein korrekt thread-abgekoppelter KI-Aufruf lässt die Event-Loop des
  bearbeitenden Prozesses währenddessen frei, der gunicorn-Heartbeat bleibt unabhängig von der
  Aufrufdauer unberührt. Selbst im Fehlerfall (Event-Loop direkt blockiert) würde ein einzelner
  45s-Aufruf `--timeout 120` nicht auslösen -- ein Prozess-Neustart durch gunicorn selbst
  bräuchte entweder einen deutlich längeren Hänger oder mehrere sich überlappende Blockaden. Das
  ändert an der Schwere des "die Hälfte blockiert"-Falls nichts (der tritt schon bei einer
  einzelnen falsch aufgerufenen Route ein), macht aber einen zusätzlichen, durch gunicorn selbst
  ausgelösten Prozess-Abbruch mitten im Request unwahrscheinlich.

**Was sich NICHT ändert, ausdrücklich geprüft**: der Sicherheitsnetz-Timeout in
`_run_with_timeout()` (`ThreadPoolExecutor` + `future.result(timeout=...)` +
`shutdown(wait=False)`) operiert vollständig INNERHALB des einen Prozesses, der ihn ausführt --
er kennt und braucht die Gesamtzahl der gunicorn-Arbeitsprozesse an keiner Stelle. Genauso
unabhängig von der Prozesszahl: die `call_ai_async()`/`run_in_threadpool()`-Empfehlung selbst
(korrektes Thread-Abkoppeln ist innerhalb JEDES einzelnen Prozesses nötig, unabhängig davon, wie
viele es insgesamt gibt), das Mock-Adapter-Fundament, `AISettings`/`AICallLog` und die
Datenschutz-Zusage (keine Inhalte im Protokoll). Kein Teil des tatsächlich gebauten Codes
(`app/ai_service.py` u. a.) musste wegen dieser Korrektur geändert werden -- ausschließlich die
Prosa-Einschätzung der Konsequenz in diesem Abschnitt war betroffen.

**Schlussfolgerung zur gestellten Frage, unverändert**: synchron reicht für den Anfang, kein
sofortiger Hintergrund-Ablauf nötig -- unter der Bedingung, dass jede künftige Fachfunktion
`call_ai_async()` (nie `call_ai()` direkt) aus einer `async def`-Route aufruft, bzw. `call_ai()`
direkt nur aus einer gewöhnlichen `def`-Route. Diese Bedingung ist -- jetzt nachweislich, nicht
nur vermutet -- wichtiger als die gewählte Zeitlimit-Zahl: sie entscheidet, ob ein KI-Aufruf
eine Handvoll Threads bindet (unkritisch, siehe oben) oder die Hälfte des gesamten ERP für
jeden anderen Nutzer für bis zu 45 Sekunden lahmlegt.

### Kostenprotokoll -- niemals Inhalt

`AICallLog` (`app/models.py`): `occurred_at`/`caller`/`success`/`error_type`/`input_tokens`/
`output_tokens`/`cost_estimate`/`duration_ms` -- **strukturell** kein Feld, das Prompt, Anhang
oder Antworttext aufnehmen könnte (nicht nur eine Verhaltenszusage, siehe
`test_ai_call_log_table_has_no_column_that_could_hold_request_or_response_content()`, die
exakt die Spaltenmenge prüft). `error_type` ist der reine Exception-Klassenname, nie dessen
Text -- der könnte bei einem echten Anbieter-Adapter Teile der Anfrage enthalten.

**Geprüft wie ausdrücklich verlangt**: die Anfrage selbst (Prompt, Bild/Dokument) wird an
KEINER Stelle gespeichert -- nicht in `AICallLog`, nicht in einem Cache (es gibt keinen),
nicht in einem Debug-Log (`_log_call()` protokolliert ausschließlich die oben genannten
Metadaten-Parameter, niemals `request.prompt`/`request.attachments`). Ein eigener Test
(`test_a_long_prompt_and_attachment_never_end_up_anywhere_in_the_logged_row`) ruft `call_ai()`
mit einem bewusst vertraulich klingenden Prompt und Anhang auf und bestätigt, dass keine
gespeicherte Spalte diesen Inhalt enthält.

**Anders als `FailedLoginAttempt` bewusst OHNE automatische Bereinigung** -- der Zweck ist hier
nicht kurzlebige Sicherheits-Buchhaltung, sondern dass der Betreiber über die Zeit sieht, was
die KI kostet und ob sie funktioniert. Die Tabelle bleibt wie `AuditLog` dauerhaft bestehen.

### Datenschutz-Rahmen

- **Sichtbarkeit**: `provider`/`api_base_url`/`model` stehen als Klartext-Anzeigefelder in
  Einstellungen → KI → KI-Anbieter (admin-only) -- der Schlüssel selbst bleibt wie beim
  SMTP-Muster ausschließlich als `has_api_key`-Boolean sichtbar, nie im Klartext, auch nicht
  beim Bearbeiten.
- **Gesamtschalter**: `AISettings.enabled`, Default AUS (`server_default='0'`). `call_ai()`
  prüft ihn als Erstes, vor jeder Netzwerkaktivität -- ist er aus, verhält es sich identisch zu
  "kein Anbieter konfiguriert", unabhängig davon, ob bereits ein Anbieter/Schlüssel eingetragen
  ist. Ein Anbieter lässt sich dadurch bereits vorbereiten, ohne dass Daten fließen, solange
  kein AV-Vertrag steht.
- **Hinweistext**: ein statischer Absatz direkt über dem Gesamtschalter in der Oberfläche, der
  auf die Datenübermittlung bei aktiver externer KI und die AV-Vertrags-Pflicht hinweist.

**Nur Administratoren** sehen/konfigurieren die KI-Einstellungen -- `require_admin()` an jedem
Endpunkt, der Menüeintrag selbst ist serverseitig hinter `{% if can(current_user, 'admin') %}`
verborgen (ausblenden, nicht ausgrauen, Muster der übrigen admin-only-Bereiche). Weder
`buero_finanzen` noch `buero_auftrag` sehen den Menüpunkt oder erreichen die Endpunkte --
Systemkonfiguration, keine Finanzfrage (Betreibervorgabe, abweichend von z. B.
Kalkulationsgrundlagen).

### Bewusst NICHT Teil dieser Version

Kein `OPTIONAL_MODULES`-Eintrag (siehe Befund). Kein echter Anbieter-Adapter. Keine
Fachfunktion nutzt `call_ai()`/`call_ai_async()` -- Belegauswertung/Angebotstexte/
Berichtszusammenfassung bleiben eigene, spätere Runden. Kein Hintergrund-Ablauf (siehe oben,
nur die Docking-Stelle ist vorbereitet).

**Tests/Verifikation**: 24 neue Tests (`tests/test_v295_ai_fundament.py`) -- Typen, Mock-Adapter,
Einstellungsverwaltung (inkl. "mock" nie persistierbar), `call_ai()`/`call_ai_async()` (Normalzustand,
Dispatch ohne Adapter, Fehlerübersetzung, das Zeitlimit-Sicherheitsnetz mit Regressionstest gegen
den `shutdown(wait=False)`-Fallstrick, Async-Offloading über die `threaded_db_session`-Fixture,
da `call_ai_async()` tatsächlich in einem anderen Thread läuft), die strukturelle
Kein-Inhalt-Garantie des Protokolls, und der abschließend verlangte Angriffstest
(`buero_finanzen`/`buero_auftrag`/`field` kommen an keinen Teil der KI-Einstellungen, inkl. des
Test-Endpunkts und ohne dass der Schlüssel je in einer 403-/200-Antwort auftaucht). Migration
`d87d5bc04b69` (zwei neue Tabellen, keine Änderung an bestehenden), volle Suite: 1764 Tests grün.
