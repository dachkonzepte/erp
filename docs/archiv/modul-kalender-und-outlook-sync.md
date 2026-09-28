# Kalender-Modul und Outlook-Kalendersynchronisation

Ausgelagert aus CLAUDE.md am 2026-09-28 im Zuge der Aufteilung in eine schlanke
CLAUDE.md plus themensortiertes Archiv (siehe CLAUDE.md, Abschnitt "Modulübersicht",
und `docs/archiv/regel-abgleich.md` für die vollständige Zuordnung). Der Inhalt ist
wortgetreu (per Skript, zeilenweise) aus der vorherigen CLAUDE.md übernommen, keine
Umformulierung. Versionsangaben ("seit 1.x.y") beziehen sich auf den Stand zum
jeweiligen Zeitpunkt der ursprünglichen Aufzeichnung.

---

## Kalender-Modul (seit 1.7.0, Modul "kalender")

Büro-Termine (Besichtigung/Aufmaß/Besprechung u. Ä.), erstes neues Modul seit dem KI-Fundament.
**Bewusst GETRENNT von der Plantafel** -- `PlanningSlot` bleibt ausschließlich für Einsatz-/
Feldplanung (Team × Auftrag × Zeitfenster), der Kalender ist ein reines Büro-Terminbuch ohne
jeden Bezug zu Team/Ressource/Auftrag. Zugriff nur `buero_auftrag`/`buero_finanzen`/`admin`
(`require_min_role(ROLE_OFFICE_AUFTRAG)`) -- Monteure sehen den Sidebar-Eintrag nicht und
bekommen 403 auf Seite und API. Auftrag: erst ein Befund zu beiden angefragten Stufen berichten,
dann ausschließlich Stufe 1 bauen -- Stufe 2 (Outlook-Synchronisation) ist bewusst reiner Befund
geblieben, siehe eigener Unterabschnitt unten.

### Datenmodell

Neue Tabelle `CalendarEvent` (`app/models.py`): `title`/`start_at`/`end_at`/`all_day`/`location`/
`notes`, `owner_user_id` (FK auf `app_users.id`, NOT NULL -- bewusst `AppUser`, nicht `Employee`,
weil auch ein reines Systemkonto ohne Mitarbeiterverknüpfung Besitzer sein kann), `project_id`/
`quote_id` (beide optional, **höchstens einer** gesetzt -- `app/calendar_events.py::
_validate_single_assignment()`, Muster `IncomingInvoice`, bewusst kein `CheckConstraint`),
`is_private`. Bereits jetzt zwei Felder für die spätere, NICHT gebaute Stufe 2:
`outlook_event_id` (String, nullable) und `external_source` (fester Code-Wert "erp"/"outlook",
`CALENDAR_EVENT_SOURCES` -- keine Optionsgruppe, da er eine künftige Verarbeitungsregel trägt,
nicht frei erweiterbar sein soll). Für den späteren "letzte Änderung gewinnt"-Konfliktabgleich
ist bewusst KEIN drittes Feld nötig -- das bereits vorhandene `updated_at`
(`onupdate=datetime.utcnow`) ist exakt der Vergleichswert, den ein künftiger Sync gegen Graphs
`lastModifiedDateTime` braucht. Migration `7974647223ea`, reine `CREATE TABLE` (kein `ALTER
TABLE` auf einer bestehenden Tabelle, deshalb kein Regel-1-Fall).

### Privatsphäre serverseitig, nicht nur in der Anzeige

Jede Büro-/Admin-Person sieht grundsätzlich ALLE Termine (eigene + Kollegen) im angefragten
Zeitraum. Ein Termin wird beim Lesen auf eine reine "Belegt"-Zusammenfassung reduziert, wenn
`is_private=True` **und** der Betrachter nicht der Besitzer ist (`app/calendar_events.py::
is_redacted_for_viewer()`) -- `redact_for_busy()` liefert dann `CalendarEventBusyOut` statt
`CalendarEventOut`: `title` ist der feste Platzhalter `"Belegt"`, `location`/`notes`/`project_id`/
`project_name`/`quote_id`/`quote_number` fehlen STRUKTURELL in der Antwort, nicht nur leer.
`GET /api/calendar-events`/`GET /api/calendar-events/{id}` tragen deshalb bewusst KEIN
`response_model` -- jede Zeile wird einzeln validiert (Muster `app/service_reports.py::
list_reports_for_field()`: "ein `response_model=list[A] | list[B]` würde nicht zeilenweise,
sondern nur für die GESAMTE Liste greifen").

**Bewusst KEINE Eigentümerschafts-Prüfung beim Ändern/Löschen** -- jede Büro-/Admin-Rolle darf
jeden Termin bearbeiten, unabhängig davon, wer ihn angelegt hat. Diese Entscheidung wurde
transparent getroffen (nicht explizit angefragt): dasselbe, bereits im Projekt etablierte Muster
wie bei `PUT`/`DELETE /api/tasks/{id}` ("keine isolierte Verschärfung nur hier", siehe CLAUDE.md
"Aufgabe"). Privatsphäre wirkt ausschließlich beim LESEN fremder Termine, nicht als Schreibschranke
-- ein Termin, der versehentlich mit `is_private=False` gespeichert wird, ist für Kollegen offen
lesbar, das ist eine bewusste Policy-Frage eines geteilten Büro-Kalenders, keine technische Lücke.

**Testbarkeit dieser Eigentümerschaftsfrage**: die gemeinsame `router_test_client`-Fixture
(`tests/conftest.py`) baut einen NUR TRANSIENTEN `AppUser` (nie committet), dessen `.id` deshalb
immer `None` bleibt -- für Rollen-Gates ausreichend, aber nicht für die "eigener vs. fremder
Termin"-Prüfung, die eine echte `request.state.erp_user.id` braucht. `tests/
test_v296_calendar_events.py` baut dafür lokal einen eigenen, kleinen Test-Client mit einer ECHTEN,
committeten Identität (`_client_for_real_user()`) -- keine Änderung an der geteilten Fixture.

### Oberfläche

`app/templates/calendar.html` -- Tag-/Wochen-/Monatsansicht als framework-loses JavaScript (kein
externes Kalender-Widget, konsistent mit dem Rest des Projekts), Anlegen/Bearbeiten über ein
Modal (Muster `project_folder.html`), Projekt-/Angebot-Verknüpfung über eine debounced Suche
gegen den bereits bestehenden, geteilten Endpunkt `GET /api/search?types=projects,quotes` (Büro-
Suche, seit 1.3.66) statt einer eigenen, neuen Such-Implementierung. Besitzer-Dropdown über den
neuen, literal VOR `/{event_id}` registrierten Endpunkt `GET /api/calendar-events/owners`
(sonst Literal-vs-Platzhalter-Kollision, wie an mehreren Stellen dieses Projekts bereits
dokumentiert) -- liefert nur aktive Konten der drei Rollen mit Zugriff auf dieses Modul.

Sidebar-Eintrag direkt nach "Planung" (nicht in der strenger gegateten Finanzen-Achse von
Betriebskosten/Eingangsrechnungen) -- `is_module_enabled('kalender') and can(current_user,
'admin', 'buero_finanzen', 'buero_auftrag')`. Auf der Projektmappe (neuer Reiter "Termine",
Jinja-gated) und im Angebotseditor (neuer Abschnitt unter "Angebot") werden die zugeordneten
Termine angezeigt, mit einem Deep-Link `/kalender?new_project=<id>&new_project_label=<name>`
bzw. `?new_quote=`, der beim Laden von `calendar.html` automatisch das Anlegen-Formular öffnet
und die Zuordnung vorbefüllt (Muster: die bereits bestehenden `?task=`/`?report=`-Deep-Links des
Dashboards).

### Löschen eines Projekts entkoppelt, statt zu löschen

`delete_project()` (`app/projects.py`) löscht per Kaskade auch die zugehörigen `Quote`-Zeilen.
Ein Termin (Besichtigung/Aufmaß) bleibt aber auch nach Löschen des Projekts als eigenständige
Historie sinnvoll -- `unlink_calendar_events_for_project()` (`app/calendar_events.py`) hängt
referenzierende `CalendarEvent`-Zeilen deshalb VOR dem eigentlichen Löschen aus (`project_id`/
`quote_id` -> `NULL`, nie ein `db.delete()` auf den Termin selbst), inklusive aller per Kaskade
mitgelöschten Angebote dieses Projekts. Ohne diesen Schritt hätte PostgreSQL (anders als die
lokale, ungeprüfte SQLite-Entwicklungsdatenbank) die Fremdschlüssel-Bedingung verletzt.

### Befund Stufe 2 (beidseitige Outlook-Synchronisation über Microsoft Graph) -- Ausgangslage vor
dem Bau (1.7.0), inzwischen umgesetzt

Reine Zukunftsplanung zum Zeitpunkt von 1.7.0, damals bewusst kein Code -- seit 1.7.1 gebaut,
siehe Abschnitt "Stufe 2 (seit 1.7.1)" weiter unten für den tatsächlichen Stand. Dieser
Unterabschnitt bleibt unverändert stehen (Entscheidungsgeschichte, nicht rückwirkend
überschrieben, Muster CLAUDE.md "Krankheitssichtbarkeit"):

- *(Überholt: umgesetzt wurde nicht die hier skizzierte Application Access Policy, sondern
  Exchange "RBAC for Applications", siehe "Einrichtung" unten.)*
  **App-Berechtigung auf alle Postfächer einschränken**: Microsofts `Calendars.ReadWrite`
  (App-Berechtigung) gilt tenant-weit, sofern keine **Application Access Policy** eingerichtet
  ist (`New-ApplicationAccessPolicy`, Exchange Online PowerShell) -- eine Postfach-
  Sicherheitsgruppe wird angelegt, die App-ID wird per Policy exakt auf diese Gruppe beschränkt.
  Das ist eine Microsoft-365-Admin-Aufgabe außerhalb des ERP-Codes, das ERP kann das nicht
  erzwingen.
- **Verknüpfung ERP-Nutzer ↔ Outlook-Postfach**: ein neues Feld `AppUser.outlook_mailbox`
  (E-Mail-Adresse) wäre der naheliegende Ort, analog zu `AppUser.employee_id`.
- **Delta-Query statt Webhooks, ohne Hintergrunddienst**: Webhook-Abos laufen ab (max. ~4230
  Minuten bei Kalenderereignissen) und bräuchten einen Dauerprozess für die Erneuerung -- passt
  nicht zur bestehenden "kein echter Scheduler"-Philosophie dieses Projekts (siehe die
  `check_due_*_and_create_reminders()`-Funktionen, die alle On-Demand beim Seitenaufruf laufen).
  **Delta-Query** ist dagegen zustandslos zwischen Aufrufen (ein gespeicherter `deltaLink` je
  Postfach) und ließe sich als echter, periodischer Cron-Job fahren -- exakt wie `backup.sh`
  auf dem Produktivserver (siehe "Produktivbetrieb" oben), nicht als In-Process-Scheduler.
- **Konfliktauflösung/Löschungen**: "letzte Änderung gewinnt" über den Vergleich von `updated_at`
  (ERP) gegen `lastModifiedDateTime` (Graph) -- kein neues Feld nötig, siehe Datenmodell oben.
  Löschungen zeigen sich in einer Delta-Query als `@removed`-Einträge; in die andere Richtung
  bräuchte ein gelöschter ERP-Termin ein Soft-Delete-Signal, bis der nächste Sync-Lauf ihn auch
  bei Outlook entfernt hat.
- **Private Outlook-Termine**: Graph liefert `sensitivity: "private"` -- würde 1:1 auf
  `is_private=True` gemappt, dieselbe Redaktion wie bei ERP-eigenen Terminen greift dann
  automatisch mit, ohne dass die Redaktionslogik selbst etwas von Outlook wissen müsste.

### Tests

22 neue Tests (`tests/test_v296_calendar_events.py`) -- reine Geschäftslogik (Anlegen/Teil-
Update/Löschen, Zeitraum-/Zuordnungsvalidierung, Überlappungsfilter, `list_owners()` nur für die
drei Büro-/Admin-Rollen, das Entkoppeln beim Löschen eines Projekts inkl. der per Kaskade
mitgelöschten Angebote), Router-Ebene (Rollen-/Modul-Gate, voller CRUD-Zyklus für alle drei
Büro-/Admin-Rollen, die Seiten-Route), und die Privatsphäre-Redaktion mit einer echten,
committeten Identität (eigener vs. fremder privater Termin, ein nicht-privater Termin bleibt für
jeden voll sichtbar). Volle Suite: 1786 Tests grün. Zusätzlich ein echter, CDP-gesteuerter
Headless-Chrome-Durchlauf gegen eine isolierte Testinstanz (niemals gegen `dachkonzepte_erp.db`):
Seite rendert mit echtem Login-Cookie, Monatsansicht aktiv, "+ Termin" öffnet das Modal, ein
Termin wird über das echte Formular angelegt und erscheint nach dem Speichern im DOM, keine
JavaScript-Konsolenfehler während des gesamten Durchlaufs.

### Stufe 2 (seit 1.7.1): Outlook-Kalendersynchronisation über Microsoft Graph

Fortsetzung des in 1.7.0 dokumentierten Befunds -- kurzer Befund zu sieben vom Betreiber
vorgegebenen Punkten (Prämissen dabei gegen den echten Code geprüft, siehe unten), dann in einer
Runde gebaut. Betrifft ausschließlich das Kalender-Modul selbst; kein anderer Modulteil dieses
Projekts wurde dafür angefasst außer der Umbenennung eines internen Funktionsnamens in
`app/email_sending.py` (siehe unten).

#### Einrichtung: Exchange "RBAC for Applications", KEINE Graph-Berechtigung in Entra ID

**Das ist die wichtigste, dauerhaft zu beachtende Regel dieses Abschnitts, deshalb vorangestellt.**
**Korrigiert am 28.09.2026 (auf dem Server verifizierter Stand, Betreiberangabe)** -- die
ursprüngliche Fassung dieses Abschnitts beschrieb zweierlei falsch: (a) `Mail.Send` sei über die
tenant-weite "Administratorzustimmung erteilen"-Schaltfläche in Entra erteilt und das sei "für
den E-Mail-Versand unproblematisch"; (b) `Calendars.ReadWrite` werde zusätzlich in Entra
hinzugefügt, nur ohne Zustimmung. Tatsächlicher Stand:

- **In Entra ID trägt die App (App-Registrierung UND Unternehmensanwendung) keine einzige
  Graph-Anwendungsberechtigung**, auch nicht "hinzugefügt ohne Zustimmung" -- nur `User.Read`
  (delegiert). `Mail.Send` wurde dort entfernt.
- **`Mail.Send` UND `Calendars.ReadWrite` laufen beide ausschließlich über Exchange "RBAC for
  Applications"**, Scope `ERP-Zugriff` = Mitglieder der E-Mail-aktivierten Sicherheitsgruppe
  `ERP-Zugriff@dachkonzepte.gmbh`.
- Tenant-weites `Mail.Send` war **nicht** unproblematisch: es erlaubte Senden im Namen JEDES
  Postfachs im Mandanten, nicht nur des Firmenpostfachs. Eine Wiedererteilung in Entra ist
  ausschließlich ein Notfall-Rückweg (z. B. wenn RBAC ausfällt), nie der Einrichtungsweg.

Einrichtung (Exchange Online PowerShell):

1. `Enable-OrganizationCustomization` (einmalig je Mandant, Voraussetzung für eigene
   Management-Scopes).
2. `New-ServicePrincipal` -- mit der **ObjectId der Unternehmensanwendung** (nicht der
   App-Registrierung) und der AppId.
3. Die E-Mail-aktivierte Sicherheitsgruppe `ERP-Zugriff@dachkonzepte.gmbh` anlegen;
   `New-ManagementScope -Name "ERP-Zugriff"` mit einem `MemberOfGroup`-Filter
   (`RecipientRestrictionFilter`) auf diese Gruppe.
4. `New-ManagementRoleAssignment` für die App-Rollen `Application Mail.Send` und
   `Application Calendars.ReadWrite` mit `-CustomResourceScope "ERP-Zugriff"`.
5. **Jedes Postfach, das das ERP nutzen soll, kommt in die Gruppe** -- das Absenderpostfach aus
   Einstellungen → E-Mail-Versand (`SmtpSettings.graph_sender_mailbox`) EBENSO wie jedes
   `AppUser.outlook_mailbox` für den Kalender-Sync. Fehlt das Absenderpostfach in der Gruppe,
   lehnt Graph `sendMail` mit `ErrorAccessDenied` ab (real so aufgetreten). Kein erneuter
   Entra-Eingriff nötig, keine Zustimmung.

**Drei Konsequenzen, die dauerhaft zu beachten sind** (die dritte: das Absenderpostfach muss in
der Gruppe sein, siehe Schritt 5 -- `app/email_sending.py::_graph_error_hint()` weist bei
`ErrorAccessDenied` seit 1.7.7 genau darauf hin, statt wie zuvor auf eine Entra-Zustimmung bzw.
`Get-ApplicationAccessPolicy`):

- **Das Zugriffstoken selbst enthält KEINE Information darüber, welche Rollen über RBAC for
  Applications gelten** -- der Client-Credentials-Flow fordert immer denselben Scope
  (`https://graph.microsoft.com/.default`), das Token ist für JEDEN Aufruf identisch, unabhängig
  davon, ob das angefragte Postfach freigegeben ist. **Deshalb darf der Code an keiner Stelle
  versuchen, aus dem Token selbst zu lesen, ob ein Zugriff erlaubt ist** -- die einzige
  verlässliche Prüfung ist der tatsächliche API-Aufruf gegen das jeweilige Postfach.
- **Ein `403 Forbidden` von Graph bedeutet in aller Regel "Postfach nicht freigegeben"**, nicht
  "Zugangsdaten falsch" (das wäre `401`) -- `app/outlook_calendar_sync.py::_graph_call()` hängt
  bei `403` deshalb einen erklärenden Hinweis an die Fehlermeldung an, der genau auf diese
  RBAC-Gruppe verweist, statt den Betreiber bei den Zugangsdaten suchen zu lassen.

#### Die sieben Punkte, mit den dabei geprüften/korrigierten Prämissen

1. **Zuordnung ERP-Nutzer zu Postfach**: `AppUser.outlook_mailbox` (neue, nullable
   `String(255)`-Spalte, `app/models.py`) -- admin-gepflegt über `/users` (neues Feld im
   bestehenden Formular, `users.html`), kein Format-Zwang (Muster `Customer.email`, das ebenfalls
   keine strikte E-Mail-Validierung hat). `NULL` bedeutet "kein Sync für dieses Konto".
2. **Projekt-/Angebotsbezug nie durch Outlook-Änderung überschreiben**: `_apply_delta_change()`
   (`app/outlook_calendar_sync.py`) baut das Update-Dict für eine eingehende Änderung IMMER nur
   aus den syncbaren Feldern (`title`/`start_at`/`end_at`/`all_day`/`location`/`notes`) --
   `project_id`/`quote_id`/`is_private`/`owner_user_id` sind darin strukturell nie enthalten,
   unabhängig davon, was Graph liefert. Mit einem eigenen Test belegt
   (`test_incoming_newer_change_updates_fields_but_never_touches_project_link`): ein Termin mit
   Projektbezug bekommt einen neuen Titel aus Outlook, behält aber `project_id` unverändert.
3. **Zeitzonen**: `CalendarEvent.start_at`/`end_at` sind naive Zeitstempel in **Europe/Berlin-
   Ortszeit** (so, wie sie in `calendar.html` eingegeben werden, `toLocalIso()` -- KEIN UTC,
   anders als `created_at`/`updated_at`). `to_utc()`/`to_berlin()` rechnen per `zoneinfo` um,
   gesendet/erwartet wird gegenüber Graph ausschließlich `"timeZone": "UTC"` -- vermeidet jede
   Mehrdeutigkeit zwischen Windows- und IANA-Zeitzonennamen, die Graphs `timeZone`-Feld sonst
   zulässt. Getestet über beide DST-Übergänge 2026 (29. März, Sprung 02:00→03:00; 25. Oktober,
   Rücksprung 03:00→02:00) -- je ein Zeitpunkt unmittelbar vor und nach der Umstellung, plus
   Rundlauf-Tests (`to_berlin(to_utc(x)) == x`) für beide Jahreszeiten und beide Übergangstage.
   `tzdata` (PyPI) neu in `requirements.txt` -- Windows liefert die IANA-Zeitzonendatenbank
   anders als Linux nicht mit dem Betriebssystem mit, `ZoneInfo("Europe/Berlin")` bräche dort
   sonst mit `ZoneInfoNotFoundError` ab (auf der lokalen Entwicklungsmaschine bereits transitiv
   über `psycopg` vorhanden, jetzt aber eine eigene, bewusste Abhängigkeit statt eines Zufalls).
4. **Serientermine -- nur ein Vorschlag, NICHT implementiert** (wie vorgegeben): `CalendarEvent`
   kennt keine Wiederholungsregel. Ein wiederkehrender Outlook-Termin erscheint in der
   `events/delta`-Antwort als EIN einzelnes `"seriesMaster"`-Objekt (Graph expandiert
   Einzeltermine nur über `calendarView` mit Datumsfenster, nicht über die hier genutzte, DAFÜR
   bewusst gewählte `events/delta` -- ein bewusster Kompromiss: `calendarView/delta` hätte jede
   Instanz einzeln geliefert, aber ein festes Zeitfenster statt eines echten, unbegrenzten
   Fortschritts-Zeigers gebraucht). `_is_recurring()` erkennt `type=="seriesMaster"` ODER ein
   gesetztes `recurrence`-Feld, `_apply_delta_change()` überspringt solche Zeilen vollständig
   (gezählt als `skipped_recurring`, nie angelegt/geändert). Ein künftiger Ausbau müsste auf
   `calendarView/delta` mit festem Zeitfenster wechseln und jede Instanz als eigene, entkoppelte
   `CalendarEvent`-Zeile führen -- eine größere Modelländerung (Recurrence-Feld), hier bewusst
   nicht gebaut.
5. **Delta-Abfrage, Cron plus beim Öffnen, letzte Änderung gewinnt, Löschungen beidseitig**:
   `sync_user_calendar(db, user)` (`app/outlook_calendar_sync.py`) ist der vollständige
   Pull-dann-Push-Zyklus für GENAU EIN Postfach -- aufgerufen sowohl von
   `scripts/sync_outlook_calendars.py` (Cron, alle Postfächer mit hinterlegtem
   `outlook_mailbox`, Muster `scripts/reset_admin_2fa.py`, Beispiel-Crontab-Zeile im
   Skript-Kopfkommentar) als auch von `POST /api/calendar-events/sync-outlook` (beim Öffnen von
   `/kalender`, **nur das eigene Postfach der angemeldeten Person**, nie das eines Kollegen --
   Selbstbedienung, keine Admin-Anforderung). `OutlookCalendarSyncState.delta_link` (neue
   Tabelle, ein Datensatz je `AppUser`) erspart jedem Lauf außer dem ersten die vollständige
   Kalenderabfrage -- mit Pagination-Test belegt (`@odata.nextLink` wird gefolgt, bis
   `@odata.deltaLink` kommt) UND mit einem Zwei-Läufe-Test, dass der zweite Lauf tatsächlich den
   gespeicherten Link wiederverwendet statt erneut die volle `$select`-Abfrage zu stellen.
   "Letzte Änderung gewinnt": Vergleich von Graphs `lastModifiedDateTime` gegen
   `CalendarEvent.updated_at` -- nur wenn Graph NACHWEISLICH neuer ist, werden die lokalen Felder
   überschrieben, sonst gewinnt die lokale Zeile UND wird in derselben Sync-Ausführung an Outlook
   zurückgeschrieben (Push-Phase, mit eigenem Test belegt: lokale Änderung "gewinnt" gegen eine
   ältere Outlook-Änderung, Graph bekommt danach ein PATCH). Löschungen beidseitig: ein
   `"@removed"`-Delta-Eintrag löscht die lokale Zeile hart; eine lokale Löschung
   (`DELETE /api/calendar-events/{id}`) stößt VOR dem eigentlichen `delete_event()` best effort
   eine Graph-Löschung an (`try_delete_remote_event()`, siehe "Bekannte, bewusst offene Punkte"
   unten für das dabei akzeptierte Restrisiko).
6. **Kein Termininhalt in Protokollen**: `logger = logging.getLogger("app.outlook_calendar_sync")`
   protokolliert ausschließlich Zähler (erstellt/aktualisiert/gelöscht/übersprungene
   Serientermine/nach Outlook gepusht) und im Fehlerfall NUR den Exception-Klassennamen, NIE
   `str(exc)` -- exakt dieselbe Zurückhaltung wie `AICallLog.error_type` (siehe CLAUDE.md
   "KI-Fundament"), aus demselben Grund: eine Graph-Fehlermeldung kann Teile der fehlgeschlagenen
   Anfrage (Titel, Ort) im Klartext zurückspiegeln. Mit einem eigenen Test belegt
   (`test_no_event_content_ever_appears_in_a_log_record`, `caplog`-Fixture): ein Termin mit einem
   bewusst markanten Titel/Ort wird gepusht und ein fehlschlagender Sync-Lauf ausgelöst, keine der
   beiden Zeichenketten taucht in irgendeiner protokollierten Zeile auf.
7. **Tests nur gegen Attrappe**: `tests/test_v297_outlook_calendar_sync.py` patcht in jedem Test
   `app.outlook_calendar_sync.urllib.request.urlopen` (Muster der bestehenden Graph-E-Mail-Tests,
   "am Verwendungsort", siehe CLAUDE.md "Testen") -- kein einziger Test ruft einen echten
   Microsoft-Endpunkt auf.

#### Architektur, bewusst getrennt von der reinen Geschäftslogik

`app/outlook_calendar_sync.py` ist ein komplett eigenständiges Modul -- `app/calendar_events.py`
(die Stufe-1-Geschäftslogik: `create_event()`/`update_event()`/`delete_event()`, Privatsphäre-
Redaktion) bleibt UNVERÄNDERT und weiterhin frei von jeder Outlook-Kenntnis. Die Orchestrierung
(nach erfolgreichem Anlegen/Ändern pushen, vor dem Löschen fernlöschen) sitzt in
`app/routers/calendar_events.py` -- derselbe Ort, der auch sonst mehrere Fachmodule
zusammenführt, keine gegenseitige Kopplung der beiden Business-Module (kein
Zirkel-Import-Risiko, Regel 3). `push_event_best_effort()`/`try_delete_remote_event()` sind
beide best effort -- ein Graph-Fehler darf ein bereits erfolgreich lokal gespeichertes Ergebnis
nie rückwirkend als Fehlschlag erscheinen lassen (Muster `app/tasks.py::notify_task_assignment()`).

**Graph-Zugangsdaten wiederverwendet, nicht dupliziert**: `OutlookSyncSettings` (neue
Singleton-Tabelle, Muster `AISettings`) trägt ausschließlich den Gesamtschalter (`enabled`,
Default aus) -- Mandanten-ID/Client-ID/Client-Secret bleiben unter `SmtpSettings` (Einstellungen
→ E-Mail-Versand), dieselbe App-Registrierung bedient beide Zwecke (siehe Einrichtung oben).
`app/email_sending.py::_get_graph_access_token()` wurde dafür in `get_graph_access_token()`
umbenannt (kein führender Unterstrich mehr, zwei interne Aufrufstellen mitgezogen) -- der
Client-Credentials-Flow liefert ohnehin immer dasselbe Token für `.default`, eine zweite
Token-Beschaffung wäre eine überflüssige Kopie.

Neue Endpunkte: `POST /api/calendar-events/sync-outlook` (Selbstbedienung, `require_min_role
(ROLE_OFFICE_AUFTRAG)`, GENAUSO modulgated wie jeder andere Endpunkt dieser Datei -- bewusst
KEINE Ausnahme, siehe Code-Kommentar dort für die kurz erwogene, dann verworfene
Gegenposition), `GET/PUT /api/outlook-sync-settings` (neuer Router
`app/routers/outlook_sync_settings.py`, `require_admin()` -- Systemkonfiguration, nicht einmal
buero_finanzen, Muster KI-Anbieter). Neue Oberflächen: ein Postfach-Feld im
Benutzer-Bearbeiten-Formular (`users.html`), ein neuer, admin-only Einstellungen-Abschnitt
"Outlook-Synchronisation" (`settings.html`, Gruppe "Kalender" neben "KI"), und ein
Fire-and-forget-Aufruf beim Öffnen von `/kalender` (`calendar.html::init()`, Muster der
bestehenden `check-due`-Aufrufe an anderer Stelle im Projekt).

Migration `6573d677bc1d` (neue Tabellen `outlook_sync_settings`/`outlook_calendar_sync_state`,
neue, nullable Spalte `app_users.outlook_mailbox` -- Regel 1 greift bei keinem der drei, da
weder eine NOT-NULL-Spalte auf einer bestehenden Tabelle noch Bestandsdaten für die beiden neuen
Tabellen existieren).

#### Nachtrag (seit 1.7.2): vier Nachfragen zu Stufe 2, zwei davon echte Funde

Vier vom Betreiber gestellte Nachfragen zur 1.7.1-Fassung -- zwei bestätigten echte, in der
1.7.1-Erstfassung offen gebliebene bzw. fehlerhafte Stellen, behoben; die dritte bleibt
ausdrücklich ein Vorschlag (noch nicht gebaut); die vierte ist reine Dokumentation.

**1. Outlook-Vertraulichkeit -> `is_private` -- fehlte, jetzt gebaut.** Die 1.7.1-Fassung fragte
`sensitivity` im `$select` der Delta-Abfrage bereits mit ab, wertete es aber nirgends aus -- ein
aus Outlook gezogener Termin startete immer mit `is_private=False`, unabhängig von seiner
tatsächlichen Vertraulichkeitsstufe in Outlook. Behoben: `_is_private_sensitivity()`/
`_outgoing_sensitivity()` (`app/outlook_calendar_sync.py`) übersetzen bidirektional zwischen
Outlooks `sensitivity` (`"private"`/`"confidential"` -> `is_private=True`; `"personal"` bewusst
NICHT -- eine geringere Vertraulichkeitsstufe, in der Anfrage nicht genannt) und `is_private`.
`is_private` ist damit seit 1.7.2 die EINE bewusste Ausnahme von "project_id/quote_id bleiben bei
einer eingehenden Änderung strukturell außen vor" (Punkt 2) -- anders als project_id/quote_id hat
Outlook mit `sensitivity` ein natives Äquivalent, die Übernahme läuft über `incoming_fields`
genauso wie title/location/etc., inklusive derselben "letzte Änderung gewinnt"-Logik (ändert ein
Kollege die Vertraulichkeit in Outlook später, übernimmt ERP das, sobald diese Änderung neuer
ist). Auf dem Push-Weg wird `is_private` ebenso als `sensitivity` mitgeschickt (`_event_payload()`)
-- ein in ERP als privat markierter Termin erscheint dadurch auch in Outlook selbst als privat,
nicht nur innerhalb des ERP. **Die eigentliche Anforderung ("Kollegen dürfen solche Termine nur
als 'belegt' sehen") brauchte dafür KEINEN Sonderfall** -- die bereits in Stufe 1 gebaute
Privatsphäre-Redaktion (`app/calendar_events.py::is_redacted_for_viewer()`/`redact_for_busy()`,
unverändert) greift automatisch, sobald `is_private` korrekt gesetzt ist, für Outlook-Termine
genau wie für ERP-eigene. Mit einem echten Ende-zu-Ende-Test belegt
(`test_a_private_synced_event_is_shown_as_busy_to_a_colleague_end_to_end`): ein mit
`sensitivity="confidential"` gezogener Termin zeigt sich einem Kollegen nur als "Belegt" ohne
Titel/Ort.

**2. Push-Wiederholung nach einem Fehlschlag -- zwei echte Funde, beide behoben.** Siehe
`app/outlook_calendar_sync.py`-Moduldocstring "Nachtrag (seit 1.7.2)" für die technische
Herleitung im Detail, hier die Kurzfassung:

- **Fund 1**: die Push-Phase von `sync_user_calendar()` committete `outlook_event_id` nach einem
  erfolgreichen POST NICHT sofort, sondern erst am Ende der GESAMTEN Schleife. Schlug ein
  SPÄTERER Termin in derselben Schleife fehl, riss das äußere `except`/`db.rollback()` die
  bereits erfolgreich zugewiesene `outlook_event_id` eines FRÜHEREN Termins wieder ein -- der
  nächste Lauf hätte diesen Termin dadurch ein zweites Mal in Outlook angelegt (Dublette). Behoben:
  jeder Termin committet jetzt EINZELN, in einem eigenen try/except -- ein fehlschlagender Termin
  blockiert die übrigen nicht mehr (Muster "ein Postfach darf den Cron-Lauf für andere nicht
  abbrechen", hier eine Ebene tiefer angewendet, neuer Zähler `push_failed`). Mit einem eigenen
  Test belegt (`test_one_failing_push_does_not_roll_back_a_sibling_rows_successful_push_in_the_same_run`).
- **Fund 2, der eigentliche Kern der Nachfrage**: selbst mit sofortigem Commit hätte der
  ursprüngliche, rein POSTFACHWEITE Vergleich (`CalendarEvent.updated_at >
  OutlookCalendarSyncState.last_synced_at`) einen genau EINEN fehlgeschlagenen Termin beim
  NÄCHSTEN Lauf verloren, sobald dieser Lauf für ALLE ANDEREN Termine erfolgreich war:
  `last_synced_at` rückt dann trotzdem vor, der liegen gebliebene Termin hätte danach
  `updated_at < last_synced_at` gezeigt -- fälschlich "bereits aktuell". Neue Spalte
  `CalendarEvent.outlook_synced_at` (nullable, Migration `c137c16e9a5c`) ersetzt diesen Vergleich
  durch einen PRO-TERMIN-Merker: `_needs_push()` prüft `outlook_event_id fehlt ODER
  outlook_synced_at fehlt ODER updated_at > outlook_synced_at`, unabhängig vom postfachweiten
  `last_synced_at` (das bleibt als reine Diagnoseinformation bestehen). Mit einem gezielten
  Regressionstest belegt, der GENAU dieses Szenario nachstellt
  (`test_a_single_stuck_row_is_still_retried_after_a_later_successful_run_advances_the_mailbox_watermark`)
  -- der Test schlägt nachweislich fehl, wenn man ihn gegen die alte, rein postfachweite Logik
  laufen lässt (so beim Entwickeln verifiziert), und ist grün gegen die neue.

  **Dabei ein drittes, beim Beheben selbst gefundenes Detail**: `_mark_synced()`s erster
  Entwurf setzte `updated_at`/`outlook_synced_at` schlicht per ORM-Attributzuweisung
  (`row.updated_at = at` mit `at == row.updated_at`, scheinbar ein No-op) -- das reichte NICHT.
  SQLAlchemys Dirty-Tracking vergleicht den neuen gegen den bereits geladenen Wert und verwirft
  eine Zuweisung ohne echte Änderung wieder aus dem "dirty"-Zustand; die Spalte landet dann NICHT
  im UPDATE, wodurch `onupdate=datetime.utcnow` trotzdem greift (per Test aufgedeckt: einige
  Millisekunden Drift zwischen beabsichtigtem und tatsächlich gespeichertem Wert -- ohne diesen
  Test wäre das unbemerkt geblieben, da der Effekt zu klein ist, um im Betrieb aufzufallen, aber
  groß genug, um `_needs_push()` gelegentlich falsch zu entscheiden). Behoben durch ein
  explizites Core-Level-`db.execute(update(CalendarEvent).where(...).values(updated_at=at,
  outlook_synced_at=at))` -- eine über `.values()` angegebene Spalte wird IMMER ins UPDATE
  aufgenommen, unabhängig davon, ob sich ihr Wert ändert, und unterdrückt `onupdate` dadurch
  zuverlässig. Mit `test_successful_push_does_not_let_updated_at_drift_and_prevents_a_redundant_second_push`
  belegt.

**3. Serientermine schreibgeschützt ins ERP -- VORSCHLAG, bewusst NICHT gebaut.** Wie
ausdrücklich verlangt nur skizziert:

- **Zweite, separate Abfrage statt eines Ausbaus der bestehenden `events/delta`**: ein neuer,
  eigener Durchlauf ruft `GET /users/{mailbox}/calendarView?startDateTime=...&endDateTime=...`
  auf (NICHT `events/delta`) -- `calendarView` expandiert wiederkehrende Serien automatisch in
  einzelne Vorkommen, jedes mit eigener `id` und `seriesMasterId`, `type` `"occurrence"` bzw.
  `"exception"` für ein individuell verschobenes/verändertes Vorkommen.
- **Festes, bei jedem Lauf neu abgefragtes Zeitfenster statt eines rollierenden Delta-Tokens für
  `calendarView`**: Graphs `calendarView/delta` existiert zwar, aber sein Zeitfenster lässt sich
  nachträglich nicht verschieben, ohne den Delta-Token zu verwerfen -- für ein rollierendes
  Fenster (z. B. "heute − 7 Tage bis heute + 90 Tage") wäre bei jeder Verschiebung ohnehin ein
  Neustart nötig. Einfacher und für schreibgeschützte, nicht editierbare Einträge ausreichend:
  ein normaler, nicht-inkrementeller `calendarView`-Aufruf für das aktuelle Fenster bei JEDEM
  Lauf (ein Kalender über ein paar Monate ist klein genug, um das unbedenklich zu machen),
  gefolgt von einem vollständigen Abgleich (bestehende Vorkommen im Fenster aktualisieren, neue
  anlegen, nicht mehr gelieferte löschen) statt eines Delta-Tokens.
- **Schreibschutz, ohne app/calendar_events.py anzufassen**: ein neuer `external_source`-Wert
  (z. B. `"outlook_occurrence"`, Erweiterung von `CALENDAR_EVENT_SOURCES`) markiert diese Zeilen.
  Die Business-Logik selbst bliebe unverändert (kein neues `if`); der Schreibschutz säße im
  ROUTER (`app/routers/calendar_events.py`), der `PUT`/`DELETE` für diesen `external_source`-Wert
  mit `409` ablehnt, BEVOR `update_event()`/`delete_event()` aufgerufen werden -- dieselbe
  Orchestrierungs-Ebene, die schon jetzt Push/Fernlöschen um die reine Geschäftslogik herum baut.
- **Kein Push, keine Projekt-/Angebot-Zuordnung nötig** -- rein lesende Vorschau der eigenen
  wiederkehrenden Termine (Jour Fixe, wöchentliche Serviceslots) in der ERP-Kalenderansicht, ohne
  Anspruch auf Bearbeitbarkeit.
- Noch NICHT entschieden (Teil des Vorschlags, nicht der Umsetzung): die genaue Fenstergröße,
  ob eine gelöschte/verschobene Instanz beim nächsten vollständigen Abgleich sauber erkannt wird
  (Diff über `outlook_event_id` innerhalb des Fensters, ähnlich `@removed` bei der bestehenden
  Delta-Abfrage, aber selbst gebaut statt von Graph geliefert).

**4. Exakte Cron-Zeile inklusive .env-Laden** -- siehe `scripts/sync_outlook_calendars.py`
(Kopfkommentar) für die vollständige Begründung, hier die Zeile selbst:

    */15 * * * * cd /home/tobias/erp && bash -c 'set -a; source .env; set +a; .venv/bin/python scripts/sync_outlook_calendars.py' >> /home/tobias/erp-data/outlook_sync.log 2>&1

`bash -c '...'` ist nötig, weil Cron Zeilen standardmäßig über `/bin/sh` ausführt, das `source`
(eine Bash-Erweiterung) nicht kennt. Ohne das `.env`-Laden würde dieses Skript denselben Fehler
wiederholen, der beim Ausliefern von 1.3.38–1.3.41 bereits real passiert ist (siehe
"Produktivbetrieb" -> "Zwei Vorfälle..." Vorfall 1): `app/database.py` fällt ohne gesetztes
`DATABASE_URL` STILL auf SQLite zurück (anders als `alembic/env.py`, das seit 1.3.42 hart
abbricht) -- der Kalender-Sync liefe dann lautlos gegen eine falsche/leere Datenbank, ohne dass
irgendetwas im Log darauf hinweist.

#### Nachtrag (seit 1.7.3): schaukelnder Termin -- Echo-Erkennung per changeKey

Gemeldet: ein Termin pendelte über mehrere Sync-Läufe hinweg zwischen "1 geändert" (Pull) und "1
nach Outlook aktualisiert" (Push), ohne dass jemand ihn angefasst hat -- vermutet wurde, dass die
Übernahme aus Outlook `updated_at` neu setzt, ohne `outlook_synced_at` nachzuziehen. Vor jeder
Änderung geprüft, wie verlangt, nicht angenommen:

- **`_mark_synced()` selbst empirisch bestätigt korrekt**, entgegen der ersten Vermutung: ein
  isolierter Test (Attribute per `setattr` ändern, dann `_mark_synced()` aufrufen, DANACH prüfen,
  ob `db.dirty`/die Attribut-History noch eine echte Änderung an `updated_at`/`outlook_synced_at`
  zeigt) UND ein zweiter Test über einen KOMPLETTEN Session-Neustart hinweg (simuliert einen
  neuen Cron-Prozess, der die Zeile frisch aus der DB lädt) bestätigen beide: die im 1.7.2-
  Nachtrag beschriebene Core-Level-UPDATE-Lösung hält, kein erneuter Autoflush-Bump.
- **Ein voller Rundlauf gegen eine Graph-Attrappe MIT ECHTEM ZUSTAND** -- der entscheidende
  Unterschied zu jeder bisherigen Testantwort in dieser Datei, die ausnahmslos einzelne,
  statische Momentaufnahmen waren: `FakeGraphServer` (neu, `tests/test_v297_outlook_calendar_sync.py`)
  führt Buch über jedes Event, vergibt bei JEDEM PATCH/POST einen neuen `lastModifiedDateTime`
  UND einen neuen `changeKey` (wie Microsoft Graph es tatsächlich tut) und liefert über `delta()`
  alles zurück, was sich seit dem zuletzt zurückgegebenen Cursor geändert hat -- ausdrücklich
  AUCH die eigene, gerade erst gepushte Änderung, denn Graph unterscheidet dabei nicht zwischen
  "von uns" und "von jemand anderem". Mit dieser Attrappe über sieben aufeinanderfolgende Läufe
  ohne jede Nutzeränderung getestet: der einfache Fall (ein Termin, ein Push, ein Echo-Pull einen
  Lauf später) wird von der bereits bestehenden Zeitstempel-Logik korrekt EINMALIG absorbiert und
  kommt danach zur Ruhe. **Ein tatsächliches, unbegrenztes Schaukeln ließ sich mit den hier
  verfügbaren Mitteln (kein Zugriff auf echte Graph-Protokolle/den Produktivserver) nicht
  reproduzieren** -- das wird hier transparent so festgehalten, statt einen unbelegten Fund zu
  behaupten.

Die bestehende Zeitstempel-Logik (`graph_modified <= existing.updated_at`) bleibt aber eine reine
"wer ist neuer"-HEURISTIK, keine exakte Identitätsaussage -- sie könnte durch Uhrenabweichung
zwischen dem ERP-Server und Microsofts eigenen Servern oder durch eine beim Roundtrip abweichend
formatierte Graph-Antwort (z. B. für Event-Bodies dokumentiert) getäuscht werden, beides mit den
hier verfügbaren Mitteln weder aus- noch nachweisbar. Deshalb, wie vom Betreiber vorgegeben, eine
ZUSÄTZLICHE, uhrzeitunabhängige Absicherung statt nur eines erneuten Zeitstempel-Tests:

- **`CalendarEvent.outlook_change_key`** (neu, nullable, Migration `3e187156fa80`) speichert
  Graphs eigenen, bei JEDER Schreiboperation neu vergebenen Versionsstempel (funktional ein
  ETag). Neu in `_EVENT_SELECT` abgefragt.
- **Nach jedem erfolgreichen Push** (`push_event_best_effort()` UND die Push-Schleife in
  `sync_user_calendar()`) wird der `changeKey` aus der POST-/PATCH-Antwort direkt übernommen --
  vorher wurde die PATCH-Antwort überhaupt nicht ausgewertet.
- **`_apply_delta_change()`** prüft VOR der Zeitstempel-Heuristik: trägt ein eingehender
  Delta-Eintrag exakt den `changeKey`, den wir zuletzt selbst gespeichert haben, ist das
  zweifelsfrei die eigene, bereits bekannte Version -- unabhängig von jeder Uhr, ohne
  Feldübernahme, ohne `_mark_synced()`-Aufruf (nichts zu synchronisieren).
- **Zusätzliche, keine ersetzende Absicherung**: liefert Graph auf ein PATCH keinen Body mit
  `changeKey` zurück (bewusst offener Randfall, siehe Test
  `test_push_patch_without_response_body_does_not_crash_and_leaves_change_key_unset`), bleibt der
  alte Wert stehen -- die unveränderte Zeitstempel-Logik greift dann unverändert als Rückfall,
  genau wie vor dieser Version.

**Regressionstest, wie ausdrücklich verlangt**:
`test_no_oscillation_all_counters_reach_zero_from_the_second_run_and_stay_zero_for_five_more_runs`
lässt `FakeGraphServer` über sieben Läufe ohne jede Nutzeränderung laufen und verlangt, dass ab
dem ZWEITEN Lauf `created`/`updated`/`deleted`/`pushed_created`/`pushed_updated`/`push_failed`
für JEDEN weiteren Lauf bei null stehen. Ein zweiter, ergänzender Test
(`test_no_oscillation_holds_even_with_a_genuine_later_edit_from_outlook_in_between`) bestätigt,
dass eine ECHTE, spätere Änderung durch jemand anderen direkt in Outlook davon unberührt
weiterhin korrekt als "updated" absorbiert wird und danach erneut zur Ruhe kommt -- die neue
changeKey-Prüfung verschluckt also keine echten externen Änderungen.

#### Nachtrag "Zweite Untersuchungsrunde" (seit 1.7.4): Schaukeln trotz changeKey (1.7.3) weiter
gemeldet -- vier gezielte Prüfungen, kein reproduzierter Fund, dafür Diagnose-Werkzeuge

Der 1.7.3-Nachtrag hat das gemeldete Schaukeln auf dem Produktivserver NICHT beendet -- weiterhin
dasselbe "1 geändert" / "1 nach Outlook aktualisiert"-Wechselmuster, obwohl `changeKey` seither
abgefragt/gespeichert/verglichen wird. Vier vom Betreiber vorgegebene Prüfungen, in dieser
Reihenfolge, jede VOR jeder weiteren Codeänderung durchgeführt:

**1. `updated_at`/`outlook_synced_at`/der Vergleich mit `lastModifiedDateTime` -- Datenbank oder
Python, UTC oder Berlin, welche Genauigkeit ("Hauptverdacht" des Betreibers).** Gegen die echte,
lokale PostgreSQL-Instanz empirisch geprüft (nicht nur SQLite, das bisher einzige in dieser Datei
verwendete Testbackend):

- **Ausschließlich Python-seitig gesetzt** -- `default=datetime.utcnow`/`onupdate=datetime.utcnow`
  auf der ORM-Spalte, KEIN `server_default`/Trigger auf der PostgreSQL-Seite (per `\d
  calendar_events` bestätigt: keine Trigger). `to_utc()`/`to_berlin()` werden nirgends für
  `updated_at`/`outlook_synced_at`/den `lastModifiedDateTime`-Vergleich aufgerufen -- diese beiden
  Funktionen sind ausschließlich für `start_at`/`end_at` reserviert (Punkt 3 des ursprünglichen
  Moduldocstrings), `updated_at`/`outlook_synced_at`/`graph_modified` bleiben durchgängig
  naiv-UTC.
- **Spaltentyp empirisch bestätigt**: `timestamp without time zone` (nicht `timestamptz`) -- diese
  Spaltenart kennt gar keine Zeitzonen-Umwandlung, unabhängig von der PostgreSQL-Sessioneinstellung
  `TimeZone` (die für `timestamptz`-Spalten relevant wäre, hier nicht). Kein Risiko einer
  stillschweigenden Zeitzonen-Reinterpretation beim Lesen/Schreiben.
- **Mikrosekunden-Präzision round-trippt exakt** -- ein per `datetime.utcnow()` erzeugter Wert
  (volle Python-Mikrosekunden-Auflösung) wurde geschrieben, die Session geschlossen, in einer
  KOMPLETT FRISCHEN Session neu geladen: identisch bis zur letzten Mikrosekunde, sowohl direkt
  nach dem Schreiben als auch nach einem zweiten Reload nach `_mark_synced()`. Kein
  Postgres-spezifischer Präzisionsverlust gefunden.
- **`_mark_synced()`s Dirty-Tracking-Verhalten unter PostgreSQL identisch zu SQLite** -- direkt
  geprüft: nach `setattr()` auf mehreren Feldern gefolgt von `_mark_synced()` zeigt
  `sa_inspect(row).attrs[...].history` für `updated_at`/`outlook_synced_at` `unchanged`, nicht
  `added` -- ein nachfolgender `db.commit()` löst deshalb KEINEN zweiten `onupdate`-Bump aus, exakt
  wie unter SQLite bereits in 1.7.3 nachgewiesen.

**Kein Postgres-vs-SQLite-Unterschied gefunden, der den "Hauptverdacht" bestätigen würde.**

**2. Der Schaukel-Test gegen die lokale, portable PostgreSQL-Instanz (`spielwiese`,
`postgresql+psycopg://erp@127.0.0.1:5433/spielwiese`, siehe CLAUDE.md "PostgreSQL-Umstieg").**
Vollständige Migrationskette (bis `3e187156fa80`) lief dort erneut sauber durch -- zusätzlicher
Beleg, dass die Kette insgesamt weiterhin gegen echtes PostgreSQL funktioniert. Zwei Varianten
getestet, beide mit FRISCHEN Sessions je Lauf (simuliert einen neuen Cron-Prozess je Tick, nicht
nur eine lange laufende Session):

- MIT `changeKey` (realistische Attrappe wie in 1.7.3): kommt nach dem einmaligen Echo-Zyklus zur
  Ruhe, kein Unterschied zu SQLite.
- OHNE `changeKey` (simuliert den Fall, dass Graph ihn trotz `$select` nicht liefert -- reiner
  Zeitstempel-Rückfallpfad): ebenfalls stabil nach einem Zyklus, auch unter PostgreSQL.

**Die beiden Schaukel-Tests sind jetzt auch als echte, opt-in pytest-Tests verfügbar** (Punkt 5,
`tests/test_v297_outlook_calendar_sync.py`,
`test_no_oscillation_all_counters_reach_zero_from_the_second_run_and_stay_zero_for_five_more_runs_postgresql`/
`test_no_oscillation_holds_even_with_a_genuine_later_edit_from_outlook_in_between_postgresql`,
`@pytest.mark.skipif` auf die neue Umgebungsvariable `ERP_TEST_POSTGRES_URL`) -- der
Standard-Testlauf bleibt unverändert SQLite-only, kein externer Dienst wird vorausgesetzt. Räumt
vor UND nach jedem Lauf ausschließlich die unter eindeutigen Test-Benutzernamen angelegten Zeilen
auf (`_cleanup_pg_test_data()`), rührt sonst nichts in der (potenziell von manuellen Prüfungen
mitbenutzten) Datenbank an.

**Dabei ein echter Fund -- allerdings im TEST, nicht im Produktcode**: die erste Fassung der
Genuine-Edit-PostgreSQL-Variante schlug fehl, weil eine eigene, ÄLTERE manuelle Testsitzung
(während dieser Untersuchung) Daten in `spielwiese` hinterlassen hatte UND die Test-Verifikationszeile
`db.scalar(select(CalendarEvent).where(CalendarEvent.outlook_event_id == graph_id))` -- anders als
die ECHTE Produktionslogik in `_apply_delta_change()` -- nicht zusätzlich nach `owner_user_id`
filterte. Da `FakeGraphServer` je Testlauf wieder bei `"graph-1"` beginnt UND
`outlook_event_id` bewusst KEINEN Unique-Constraint trägt (siehe Klassendocstring), lieferte die
ungefilterte Testabfrage die falsche, veraltete Zeile eines anderen (Test-)Postfachs zurück.
Behoben: die Testzeile filtert jetzt zusätzlich nach `owner_user_id`, exakt wie die
Produktionslogik es tut; `spielwiese` wurde vollständig bereinigt.

**3. Liefert Graphs Delta-Antwort `changeKey` überhaupt mit? Ohne Zugriff auf den echten Tenant
NICHT verifizierbar.** `_EVENT_SELECT` fragt es seit 1.7.3 ab, aber ob Microsoft Graph es für
`/events/delta` tatsächlich zurückliefert (manche Graph-Endpunkte haben dokumentierte
`$select`-Einschränkungen), lässt sich mit den hier verfügbaren Mitteln nicht klären -- genau
dafür die neue Diagnosezeile (Punkt 4).

**4. Abschaltbare Diagnosezeile** (`ERP_OUTLOOK_SYNC_DIAGNOSTICS=1` in `.env`, vom Cron-Skript bei
JEDEM Lauf neu geladen -- ein Umschalten wirkt bereits beim nächsten Tick, kein Neustart des
Webservers nötig): `app/outlook_calendar_sync.py::diagnostics_enabled()`/`_diag()` protokollieren
je verarbeitetem Delta-Eintrag (`_apply_delta_change()`) UND je Push-Versuch
(`push_event_best_effort()`, die Push-Schleife in `sync_user_calendar()`) eine strukturierte Zeile
mit genau den angeforderten Feldern -- ERP-ID, `updated_at`, `outlook_synced_at`,
`lastModifiedDateTime` ROH (der unveränderte String aus der Graph-Antwort) UND umgerechnet
(`_parse_graph_datetime()`s Ergebnis), `outlook_change_key` gespeichert/eingehend, die getroffene
Entscheidung (`"neu angelegt"`/`"changeKey-Echo (übersprungen)"`/`"Graph nicht neuer
(übersprungen)"`/`"übernommen (Graph war neuer)"`/`"gelöscht (@removed)"`/`"push angestoßen
(...)"`/`"push erfolgreich"`/`"push fehlgeschlagen (...)"` u. a.) -- NIE Titel/Ort/Notiz, Punkt 6
bleibt unverändert in Kraft. Eigener Logger-Name (`app.outlook_calendar_sync.diagnostics`), damit
sie sich unabhängig vom bestehenden Warn-Logger und rein über die Umgebungsvariable schalten
lässt. Dies ist das Werkzeug, mit dem der Betreiber die auf dem Produktivserver tatsächlich
eintreffenden Rohwerte selbst nachvollziehen kann -- ohne es hätte Punkt 3 nie beantwortet werden
können.

**Dabei ein Fallstrick beim Bauen der Diagnosezeile SELBST gefunden und behoben, bevor er
ausgeliefert wurde**: ein naiver Versuch, `row.updated_at`/`row.outlook_synced_at` NACH einem
`db.delete(row)` + `db.commit()` für die "gelöscht (@removed)"-Diagnosezeile zu lesen, hätte
`ObjectDeletedError` ausgelöst (SQLAlchemys `expire_on_commit` markiert alle Session-Objekte nach
jedem Commit als abgelaufen -- ein Zugriff auf ein bereits gelöschtes, abgelaufenes Objekt löst
dann einen Reload-Versuch gegen eine nicht mehr existierende Zeile aus). Behoben: alle für die
Diagnosezeile benötigten Werte werden VOR jeder Mutation in reine Python-Variablen kopiert, `log()`
liest nur noch daraus, nie erneut vom (möglicherweise inzwischen gelöschten) ORM-Objekt. Mit einem
gezielten Regressionstest belegt (`test_diagnostics_do_not_crash_on_removed_delta_entry`).

**Unabhängiger, real gefundener Härtungsbedarf, nicht als bewiesene Ursache behauptet**:
`_parse_graph_datetime()` verließ sich auf `datetime.fromisoformat()`, das SIEBEN-stellige
Bruchteilsekunden (Microsofts übliches "Ticks"-Format, z. B. `"...634.6472860Z"`) erst ab **Python
3.11** akzeptiert -- davor: `ValueError` bei jeder Bruchteilsekundenlänge außer 0/3/6 Ziffern, ein
sehr verbreiteter, dokumentierter Stolperstein beim Arbeiten mit der Graph-API. Welche
Python-Version auf dem Produktivserver tatsächlich läuft, war nicht dokumentiert/geprüft. Eine
solche `ValueError` hätte allerdings den GESAMTEN Lauf mit `error: True` markiert, nicht das
gemeldete, unauffällige 1-zu-1-Wechselmuster -- deshalb vermutlich NICHT die alleinige Ursache des
gemeldeten Schaukelns, aber ein eigenständiger, tatsächlich vorhandener Fehler. Behoben,
UNABHÄNGIG von der jeweiligen Python-Version: Bruchteilsekunden werden jetzt vor dem eigentlichen
Parsen per Regex auf sechs Stellen gekürzt (`_OVERLONG_FRACTION_RE`, dieselbe
Abschneide-statt-Rundungs-Konvention wie Pythons eigener 3.11+-Parser) -- macht das Verhalten
strukturell unabhängig davon, welche Python-Version tatsächlich läuft.

**Ergebnis, ehrlich festgehalten**: die gemeldete, tatsächliche Ursache des Schaukelns auf dem
Produktivserver konnte mit den hier verfügbaren Mitteln (kein Zugriff auf den echten Tenant, echte
Graph-Protokolle oder den Produktivserver selbst) NICHT abschließend bewiesen werden. Punkt 1
(Datenbank/Zeitzone/Präzision) und Punkt 2 (PostgreSQL-Rundlauf) wurden geprüft und ergaben keinen
Fund. Punkt 3 (liefert Graph tatsächlich changeKey mit) bleibt offen -- die neue Diagnosezeile
(Punkt 4) ist das Werkzeug, mit dem der Betreiber das beim nächsten Produktiv-Cron-Lauf selbst
nachvollziehen kann. Ein unabhängiger, real gefundener Präzisions-Fehler (Python-Versions-
Abhängigkeit von `_parse_graph_datetime()`) wurde vorsorglich behoben, ohne als bewiesene Ursache
behauptet zu werden.

7 neue Tests (Zeitstempel-Präzisions-Parsing, drei Diagnosezeilen-Tests inkl. des
Content-Ausschlusses, die @removed-Regression, plus die beiden opt-in PostgreSQL-Varianten der
Schaukel-Tests), volle Suite: 1840 Tests grün, 2 davon opt-in und standardmäßig übersprungen ohne
gesetztes `ERP_TEST_POSTGRES_URL`.

#### Nachtrag (seit 1.7.5): die tatsächliche Ursache -- changeKey kommt im Delta strukturell nie an

Rückmeldung des Betreibers auf 1.7.4: das Schaukeln selbst blieb aus (der einfache Fall wird
einmalig absorbiert und kommt zur Ruhe, wie in 1.7.3 bereits nachgewiesen), aber
`change_key_gespeichert`/`change_key_eingehend` standen in JEDER Diagnosezeile auf `None` --
auch direkt nach einem als "push erfolgreich" protokollierten Push. Drei vorgegebene Prüfungen,
diesmal NICHT aus dem Gedächtnis, sondern direkt anhand der Microsoft-Graph-Dokumentation
(Microsoft Learn, per WebFetch/WebSearch nachgeschlagen -- nicht angenommen):

1. **Fordert der Delta-Aufruf `changeKey` per `$select` an?** Ja (`_EVENT_SELECT`) -- aber
   Microsoft dokumentiert für Kalender-Delta-Abfragen ausdrücklich: *"Expect a delta function
   call on a calendarView to return the same properties you'd normally get from a GET
   /calendarView request. You cannot use $select to get only a subset of those properties."*
   (`event: delta`-Referenzseite, `learn.microsoft.com/en-us/graph/api/event-delta`) --
   **`$select` wird für Kalender-Delta-Abfragen komplett ignoriert**, unabhängig vom Inhalt.
2. **Liefert Graph `changeKey` im Delta überhaupt, oder nur `@odata.etag`?** Jede von Microsoft
   selbst gezeigte Beispiel-Delta-Antwort (mehrere Beispiele auf
   `learn.microsoft.com/en-us/graph/delta-query-events`, sowohl geänderte als auch neu
   hinzugekommene Einträge) zeigt durchgängig `@odata.etag`, aber **niemals** `changeKey` --
   obwohl andere, weniger zentrale Felder (`subject`, `body`, `attendees`, `organizer`) jeweils
   vollständig gezeigt werden. `changeKey` ist damit für Delta-Zeilen strukturell unerreichbar,
   kein Zufall dieser einen Installation, wie der 1.7.4-Nachtrag noch offengelassen hatte.
3. **Wird es aus der Antwort auf POST/PATCH übernommen?** Die Extraktion selbst
   (`response.get("changeKey")`) war korrekt -- aber ein zweiter, unabhängiger, beim Nachprüfen
   gefundener Fund: die "push erfolgreich"-Diagnosezeile protokollierte für
   `change_key_gespeichert` den Wert VOR DEM Push (`old_change_key`), nicht den gerade frisch
   gespeicherten -- ein reiner Diagnose-Anzeigefehler, unabhängig von der eigentlichen Ursache,
   ebenfalls behoben.

**Der komplette Mechanismus wechselt von `changeKey` auf `@odata.etag`.** `@odata.etag` ist eine
protokollweite OData-Annotation, die laut Microsofts eigener Ressourcen-Dokumentation UND allen
gezeigten Beispielantworten JEDE Entitätsdarstellung begleitet -- ein einfaches `GET /events/{id}`
ebenso wie die Antwort auf `POST`/`PATCH` UND jede einzelne Delta-Zeile, unabhängig von `$select`,
weil sie kein regulär selektierbares Entitäts-Property ist. Sie steht deshalb zuverlässig auf
BEIDEN Seiten des Vergleichs zur Verfügung. `CalendarEvent.outlook_change_key` heißt seither
`outlook_etag` (echte Spalten-Umbenennung, Migration `1375eeeea2fa`, `alter_column(...,
new_column_name=...)` -- kein Drop+Add, kein Datenverlust-Risiko: die Spalte trug zu diesem
Zeitpunkt bei keiner einzigen Zeile einen von Graph tatsächlich nutzbaren Wert, bestätigt per
Produktions-Diagnose). `_EVENT_SELECT` verzichtet seither auf `changeKey` -- es kam über diesen
Weg nachweislich nie an, ein Weglassen ändert am Verhalten nichts, macht die Anfrage aber ehrlich.
Die diagnostischen Feldnamen `change_key_gespeichert`/`change_key_eingehend` heißen seither
`etag_gespeichert`/`etag_eingehend` -- bewusst nicht rückwärtskompatibel gehalten: die alten Namen
versprachen einen Wert, den die Delta-Antwort nie geliefert hat.

**`FakeGraphServer` (`tests/test_v297_outlook_calendar_sync.py`) bildete bis dahin selbst den
Fehler ab, den sie eigentlich aufdecken sollte** -- `delta()` lieferte `changeKey` in JEDER Zeile
mit, ein Test dagegen konnte den echten Produktionsfehler dadurch strukturell nie finden,
unabhängig davon, wie viele Läufe er simulierte hätte. `delta()` liefert seither NUR NOCH
`@odata.etag` (kein `changeKey` mehr, genau wie die echten Microsoft-Beispielantworten),
`create()`/`patch()` liefern weiterhin BEIDE Felder (wie ein reales POST/PATCH). Zwei neue Tests
härten die Umkehrung ab: eine Push-Antwort mit `changeKey`, aber ohne `@odata.etag`, darf
`outlook_etag` NICHT verändern (`test_push_response_with_changekey_but_no_etag_does_not_store_anything`);
ein Delta-Eintrag, der -- absichtlich zufällig passend, aber ohne `@odata.etag` -- nur einen
`changeKey` trägt, wird NICHT über einen (nicht existierenden) changeKey-Rückfall als Echo erkannt
(`test_delta_item_carrying_only_changekey_is_not_recognized_as_echo_via_changekey_fallback`); dazu
ein Regressionsschutz, dass die alten Diagnose-Feldnamen nirgends mehr auftauchen. 2 neue Tests
(netto, da drei bestehende nur umbenannt/angepasst wurden -- nicht ersetzt), volle Suite: **1842
Tests grün, 2 davon weiterhin opt-in ohne gesetztes `ERP_TEST_POSTGRES_URL` übersprungen.**

#### Nachtrag (seit 1.7.6): Dauer-Push trotz 1.7.5 -- die reine Sync-Buchhaltung selbst hatte
`updated_at` verschoben, jetzt gefunden und behoben

Eine weitere Produktions-Diagnose zeigte: trotz 1.7.5 (Echo-Erkennung per `@odata.etag`) blieb
der unnötige Push bestehen. Für "etag-Echo (übersprungen)"/"Graph nicht neuer (übersprungen)"
stand `updated_at` bereits VOR der eigentlichen Verarbeitung mehrere Sekunden nach
`outlook_synced_at` (Beispiel: `updated_at=13:01:57.632772` gegen
`outlook_synced_at=13:01:50.714899`, gefolgt von "push angestoßen"); an anderer Stelle lag
`updated_at` 3,7 ms NACH `_mark_synced()` noch von `outlook_synced_at` entfernt. Drei geforderte
Punkte: die Skip-Zweige dürfen die Zeile gar nicht verändern; jeder reine Sync-Buchhaltungs-
Schreibvorgang (Etag, `outlook_synced_at`, der Graph-Zeitpunkt) muss über einen Weg laufen, der
`updated_at` nie berührt; ein Test soll das beweisen.

**Empirisch nachgebaut statt angenommen, mit zwei widerlegten eigenen Zwischenannahmen.** Ein
Nachbau mit `echo=True` gegen SQLite UND eine echte, lokale PostgreSQL-Instanz (dieselbe
portable Instanz aus "PostgreSQL-Umstieg", eigens dafür wieder gestartet) bestätigte zunächst die
erste Vermutung: `session.execute()` autoflusht vor der eigenen Anweisung jede andere, noch
offene Dirty-Markierung -- war die Zeile bereits über `setattr()` dirty (wie
`push_event_best_effort()`/die Push-Schleife es bis dahin mit `outlook_event_id`/`outlook_etag`
VOR dem alten `_mark_synced()`-Aufruf taten), erzeugte dieser Autoflush eine gewöhnliche
ORM-`UPDATE`-Anweisung samt `onupdate=datetime.utcnow`-Bump. Ein erster Fix-Entwurf entfernte
deshalb nur das vorherige `setattr()` (die Felder wandern direkt in `.values()`, `updated_at`
bleibt einfach weg) -- **das reichte NICHT**: der bereits bestehende, seit 1.7.2 grüne Test
`test_successful_push_does_not_let_updated_at_drift_and_prevents_a_redundant_second_push` schlug
mit genau diesem "Fix" weiterhin fehl, per SQL-Mitschnitt bestätigt mit `UPDATE calendar_events
SET outlook_event_id=?, outlook_synced_at=?, updated_at=?` -- `updated_at` erschien in der
SET-Klausel, OBWOHL kein `updated_at`-Parameter in `.values()` übergeben wurde.

**Die tatsächliche Ursache**: `Column(..., onupdate=datetime.utcnow)` ist eine COLUMN-, keine
reine ORM-Mapper-Eigenschaft -- sie greift bei JEDER `UPDATE`-Anweisung gegen diese Tabelle, ob
über die ORM-Klasse (`update(CalendarEvent)`) ODER das rohe Core-`Table`-Objekt
(`update(CalendarEvent.__table__)`) abgesetzt (beides empirisch geprüft, beide Varianten zeigten
denselben, unerwünschten Bump), SOBALD `updated_at` NICHT explizit in `.values()` auftaucht. Ein
bloßes Weglassen der Spalte schützt sie also NICHT vor `onupdate`. **Die tatsächlich wirksame
Lösung**: `updated_at` wird in JEDEM Sync-Buchhaltungs-Schreibvorgang IMMER explizit auf eine
SELBSTREFERENZ gesetzt (`updated_at=CalendarEvent.updated_at`, kompiliert zu `SET updated_at =
calendar_events.updated_at`) -- ein explizit gegebener Wert unterdrückt `onupdate` zuverlässig
(das laut SQLAlchemy nur greift, wenn für die Spalte KEIN Wert übergeben wurde), ohne dass der
aktuelle Wert vorher in Python bekannt sein müsste: die Datenbank liest ihn sich selbst aus
derselben Zeile, atomar. Per direktem Vorher/Nachher-Vergleich bestätigt: `DRIFT = 0:00:00`,
exakt, nicht nur "meist richtig".

**Zweite, unabhängige Absicherung, ebenfalls empirisch gefunden**: die Selbstreferenz schützt nur
VOR der EIGENEN Anweisung -- trägt die Zeile beim Aufruf bereits eine ANDERE, über `setattr()`
erzeugte Dirty-Markierung, autoflusht `db.execute()` diese ZUERST über eine gewöhnliche
ORM-`UPDATE`-Anweisung, die `onupdate` einbezieht, BEVOR die Selbstreferenz greifen kann (ein
`event.title = "..."` unmittelbar vor dem Buchhaltungsaufruf erzeugte trotz Selbstreferenz einen
echten, persistierten Millisekunden-Versatz). Die neue Funktion `_write_sync_bookkeeping()`
(`app/outlook_calendar_sync.py`, löst `_mark_synced()` vollständig ab) prüft deshalb VORAB
`db.is_modified(row)` und bricht mit einer klaren Fehlermeldung ab, statt den Fehler ein drittes
Mal still zu wiederholen -- jeder der drei Aufrufer (`push_event_best_effort()`, die Push-Schleife
in `sync_user_calendar()`, der "übernommen"-Zweig von `_apply_delta_change()`) flusht/committet
eine echte inhaltliche Änderung deshalb IMMER VOR diesem Aufruf, nie danach. `outlook_event_id`/
`outlook_etag` werden seither NICHT MEHR per `setattr()` vor dem Buchhaltungsaufruf gesetzt,
sondern als Teil DERSELBEN Anweisung übergeben. `_apply_delta_change()`s "übernommen"-Zweig
trennt ECHTE inhaltliche Änderungen (title/location/... -- die SOLLEN `updated_at` ganz normal
über `onupdate` bumpen, das ist eine echte Änderung) von der reinen Buchhaltung: erst `db.flush()`
der inhaltlichen Felder, dann wird der TATSÄCHLICH generierte `updated_at`-Wert ausgelesen und
unverändert als `outlook_synced_at` in die separate Buchhaltungsanweisung übergeben -- kein
separat erfasster `datetime.utcnow()` mehr, der vom tatsächlich gespeicherten Wert abweichen
könnte.

**Ehrlich festgehalten**: ein exakter, deterministischer Nachbau der in der Produktions-Diagnose
gezeigten PERSISTIERTEN Zahlenwerte (mit mehreren Sekunden Abstand bzw. dem 3,7-ms-Versatz)
gelang trotz umfangreicher Versuche (Einzelsession, Session-pro-Lauf nach dem Vorbild eines neuen
Cron-Prozesses, SQLite UND PostgreSQL) NICHT -- die genaue Abfolge, die in Produktion zu einem
beobachteten Versatz geführt hat, bleibt damit nicht abschließend bewiesen. Der jetzt gefundene
und behobene `onupdate`-Mechanismus trat ausschließlich in einem ZWISCHENSCHRITT des eigenen
Reparaturversuchs auf (dem ersten, verworfenen "Spalte weglassen"-Fix-Entwurf), nicht nachweisbar
in der ursprünglich ausgelieferten 1.7.1–1.7.5-Fassung, deren `_mark_synced()` `updated_at=at`
bereits explizit mitgab und `onupdate` damit für ihre eine Anweisung korrekt unterdrückte. Der
jetzt gewählte, endgültige Mechanismus (explizite Selbstreferenz plus `is_modified()`-Wächter)
ist unabhängig davon nachweislich korrekt und macht das gesamte Risiko strukturell unmöglich,
statt sich auf eine bestimmte Zwischenzustands-Reihenfolge zu verlassen.

**Tests**: zwei neue, direkt gegen `_write_sync_bookkeeping()` --
`test_write_sync_bookkeeping_never_changes_updated_at` (saubere Zeile, exakte
`updated_at`-Gleichheit) und `test_write_sync_bookkeeping_rejects_a_row_with_unrelated_dirty_state`
(bricht sofort ab, wenn die Zeile noch dirty ist). Der bestehende Sieben-Läufe-Schaukel-Test
(`_check_no_oscillation()`/`_check_no_oscillation_with_genuine_edit()`) läuft seither mit einer
GENUINE NEUEN Session je Lauf (gebunden an dieselbe Engine, `db.get_bind()`) statt der zuvor über
alle sieben Läufe wiederverwendeten -- simuliert einen neuen Cron-Prozess je Tick, wie
ausdrücklich verlangt (`scripts/sync_outlook_calendars.py` startet tatsächlich als eigener
Prozess bei jedem Tick). Volle Suite: **1844 Tests grün, 2 davon weiterhin opt-in ohne gesetztes
`ERP_TEST_POSTGRES_URL` übersprungen** (beide PostgreSQL-Schaukel-Varianten mit gesetzter
Variable zusätzlich verifiziert grün).

#### Bekannte, bewusst offene Punkte

- **Resurrection-Risiko bei fehlgeschlagener Fernlöschung.** `try_delete_remote_event()` löscht
  IMMER lokal, auch wenn die Graph-Löschung fehlschlägt (z. B. kurzzeitige Netzwerkstörung) --
  Nutzerabsicht hat Vorrang vor einem perfekt konsistenten Zustand. Bleibt der Outlook-Termin
  dadurch bestehen, erkennt ihn der NÄCHSTE Delta-Lauf als unbekannten `outlook_event_id` und
  legt ihn lokal NEU an (er "kommt zurück"). Bewusst akzeptiert, kein Tombstone-Mechanismus
  gebaut -- ein seltener, durch erneutes Löschen leicht behebbarer Fall, kein Datenverlust.
- **Serientermine bleiben ausgeklammert** (siehe Punkt 4 des Moduldocstrings sowie den Vorschlag
  im Nachtrag oben) -- eine künftige Erweiterung bräuchte einen zweiten `calendarView`-Durchlauf
  UND einen neuen, schreibgeschützten `external_source`-Wert -- eine größere Erweiterung, hier
  bewusst nur skizziert, nicht gebaut.
- **Kein Reverse-Proxy-Header-Problem hier** (anders als bei `public_base_url`,
  Betriebsmittelverwaltung Stufe 2) -- die Kalender-Sync-URLs zeigen immer auf
  `graph.microsoft.com`, nie auf die eigene ERP-Instanz, es gibt also keine analoge
  Basis-URL-Frage zu lösen.

#### Tests

32 neue Tests seit 1.7.1 (`tests/test_v297_outlook_calendar_sync.py`) -- alle sieben Punkte
einzeln abgedeckt, dazu `is_outlook_sync_available()` (Gesamtschalter/Graph-Zugangsdaten/
Postfach je einzeln geprüft), Push (Anlegen, Ändern, Fehlschlag ohne Exception, No-op ohne
aktivierten Sync), Fernlöschen (Erfolg, Fehlschlag ohne Exception, No-op ohne `outlook_event_id`)
und die Rollen-/Modul-Gates der beiden neuen Endpunkte (field bekommt 403 auf
`sync-outlook`; buero_auftrag darf es aufrufen, bekommt ohne hinterlegtes Postfach `{"skipped":
true}`; `outlook-sync-settings` ist ausnahmslos admin-only). Ein bereits bestehender Test
(`tests/test_v054_settings_sidebar.py::test_every_sidebar_section_is_in_the_settings_sections_whitelist`)
musste um den neuen `outlook-sync`-Menüpunkt in `SETTINGS_SECTIONS` ergänzt werden -- ein
gemeldeter, sofort behobener Fund derselben Testrunde. **Seit 1.7.2 zusätzlich 11 weitere Tests**
für die vier Nachfragen oben (Vertraulichkeits-Abbildung beim Anlegen UND bei einer eingehenden
Änderung, die Ende-zu-Ende-Redaktion für einen Kollegen, die beiden Push-Wiederholungs-Regressionstests,
und der Nachweis, dass ein erfolgreicher Push `updated_at` nicht driften lässt). **Seit 1.7.3
zusätzlich 6 weitere Tests** für den Nachtrag "schaukelnder Termin" oben (`changeKey`-Erfassung
beim Push, inkl. des Randfalls ohne Antwort-Body; exakte Echo-Erkennung trotz einer scheinbar
neueren Zeitstempel-Heuristik; die beiden Sieben-Läufe-Regressionstests gegen `FakeGraphServer`).
Volle Suite: **1835 Tests grün.**
