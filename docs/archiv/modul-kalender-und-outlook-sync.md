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

#### Nachtrag (seit 1.7.8): Serientermine aus Outlook, schreibgeschützt

Betreibervorgaben: nur Outlook -> ERP, Serien im ERP weder anlegen noch bearbeiten noch löschen;
Fenster 30 Tage zurück, 12 Monate voraus; einzelne Vorkommen inklusive Ausnahmen (verschobene
oder abgesagte Einzeltermine); Privat/"Belegt" wie bei Einzelterminen. Pflichtpunkte: nie ein
Push (strukturell), Schaukel-Test weiter bei 0, Befund zum wandernden Fenster, Attrappe wie echtes
Graph, Diagnosezeile auch für Serien.

**Graph-Verhalten, anhand der Microsoft-Doku geprüft (nicht aus dem Gedächtnis):** `calendarView`
(v1.0) liefert `singleInstance`, `occurrence` und `exception`, nie den `seriesMaster`; jedes
Vorkommen trägt eigene `id`, `seriesMasterId`, `originalStart`, `@odata.etag`. Aus der Serie
gelöschte Vorkommen fehlen ("instances ... doesn't include occurrences canceled from the
series"); eine vom Organisator abgesagte Besprechung kann mit `isCancelled=true` erscheinen. Ohne
`Prefer: outlook.body-content-type="text"` kommt der Body als HTML.

**Wanderndes Fenster und Delta (Pflicht 3) -- deshalb kein Delta für Serien:** bei
`calendarView/delta` werden `startDateTime`/`endDateTime` in den Token kodiert und sind danach
eingefroren. Ein mitwanderndes Fenster erzwingt regelmäßig eine neue Runde (voller Neuabzug), und
für Vorkommen, die nur durch das Vorrücken der Zeit aus dem Fenster fallen, liefert Delta kein
`@removed` (das gibt es nur für Änderungen) -- sie blieben verwaist, neue am vorderen Rand kämen
nie. Stattdessen holt jeder Lauf den VOLLSTÄNDIGEN `calendarView`-Schnappschuss des aktuellen
Fensters (verankert an Mitternacht Europe/Berlin, innerhalb eines Tages stabil) und gleicht
`OutlookSeriesOccurrence` exakt ab: anlegen/ändern/entfernen in EINER Transaktion, erst nachdem
alle Seiten (`@odata.nextLink`, `$top=100`) geholt sind -- ein Abruffehler ändert lokal nichts
(`series_failed=1`, der Einzeltermin-Sync davor bleibt unberührt). Schlüssel (Besitzer,
Outlook-ID) mit UNIQUE-Constraint: nichts doppelt, nichts fehlt. Aufwand je Lauf und Postfach:
ein vollständiger Abruf über 13 Monate, bei `$select` auf die nötigen Felder und wenigen Serien
unkritisch fürs 4-GB-Budget.

**Strukturelle Push-Sperre (Pflicht 1):** eigene Tabelle `outlook_series_occurrences`
(`OutlookSeriesOccurrence`, Migration `ea1034dc38e7`, reine `CREATE TABLE`) ohne Push-,
Projekt- oder Angebotsfelder. Push-Schleife, `push_event_best_effort()` und PUT/DELETE
`/api/calendar-events/{id}` arbeiten ausschließlich auf `CalendarEvent` -- ein Vorkommen ist dort
nicht adressierbar. Lesen über den neuen `GET /api/calendar-series-occurrences` (kein PUT/DELETE,
dieselbe Redaktion über `is_redacted_for_viewer()`/`redact_for_busy()`, rollen- und
modulgesperrt wie alle Kalender-Endpunkte). Jede Outlook-ID gehört genau einem Weg:
`_apply_delta_change()` lehnt Master, Vorkommen und Ausnahmen ab; der Serien-Abgleich ignoriert
Einzeltermine. Wird ein bekannter Einzeltermin in Outlook zur Serie, entfernt der Delta-Weg die
lokale Kopie (sonst könnte eine ERP-Bearbeitung per PATCH die ganze Serie ändern).

**Oberfläche:** `calendar.html` lädt beide Endpunkte, zeigt Vorkommen mit ↻ und gestrichelter
Kante; ein Klick öffnet eine reine Leseansicht (kein Formular, kein Löschen), getrennt nach
`series`-Merker -- ein Einzeltermin und ein Vorkommen mit derselben numerischen ID werden nicht
verwechselt (per CDP-Klicktest gegen eine isolierte Instanz belegt).

**Diagnose (Pflicht 5):** eigene Zeile `serie occurrence_id=… typ=… etag_gespeichert=…
etag_eingehend=… entscheidung=…` für "neu übernommen", "unverändert", "aktualisiert (in Outlook
geändert)", "abgesagt (isCancelled) -> nicht geführt", "ungültig", "nicht mehr im Fenster oder in
Outlook entfernt/abgesagt -> entfernt" und "Serien-Abgleich fehlgeschlagen"; nie Titel/Ort/Notiz.

**Tests:** `FakeGraphServer` bildet Serien wie dokumentiert ab (Master nur im Delta, Vorkommen/
Ausnahmen nur in `calendarView`, gelöschte fehlen, abgesagte mit `isCancelled`, sieben
Nachkommastellen, Paging) und protokolliert jeden Schreibzugriff. 13 neue Tests, u. a.: sieben
Läufe mit Serie ohne einen einzigen Schreibzugriff am Server; der Schaukel-Test aus 1.7.6 mit
Serie (SQLite und opt-in PostgreSQL gegen `spielwiese`, beide grün); wanderndes Fenster
(t0 -> t0+45 Tage, lokale Menge exakt gleich der unabhängig berechneten Erwartung, über
Seitengrenzen); Abbruch auf Seite 2 ändert nichts. Gegenproben: mit abgeschaltetem Entfernen bzw.
mit fälschlich gezählten Änderungen werden die jeweiligen Tests rot.

#### Bekannte, bewusst offene Punkte

- *(Seit 1.9.160 erledigt, Löschauftrag `OutlookDeleteOrder`.)* **Resurrection-Risiko bei fehlgeschlagener Fernlöschung.** `try_delete_remote_event()` löscht
  IMMER lokal, auch wenn die Graph-Löschung fehlschlägt (z. B. kurzzeitige Netzwerkstörung) --
  Nutzerabsicht hat Vorrang vor einem perfekt konsistenten Zustand. Bleibt der Outlook-Termin
  dadurch bestehen, erkennt ihn der NÄCHSTE Delta-Lauf als unbekannten `outlook_event_id` und
  legt ihn lokal NEU an (er "kommt zurück"). Bewusst akzeptiert, kein Tombstone-Mechanismus
  gebaut -- ein seltener, durch erneutes Löschen leicht behebbarer Fall, kein Datenverlust.
- ~~Serientermine bleiben ausgeklammert~~ -- seit 1.7.8 schreibgeschützt übernommen, siehe
  "Nachtrag (seit 1.7.8)" unten (umgesetzt mit eigener Tabelle statt des hier ursprünglich
  skizzierten `external_source`-Werts).
- **Der Einzeltermin-Sync nutzt `/users/{x}/events/delta`, laut Microsoft-Doku nur in Beta
  dokumentiert** (gefunden 28.09.2026 bei der Serien-Recherche): v1.0 dokumentiert Delta nur auf
  `calendarView/delta` (mit festem Fenster). In Beta liefert `events/delta` Einzeltermine und
  Serien-Master, "Each event in the response contains only the id, type, start, and end
  properties". Auf dem Produktivserver funktioniert der Sync nachweislich (Diagnosezeilen aus
  1.7.4–1.7.6 zeigen `lastModifiedDateTime`/`@odata.etag`), das Verhalten ist aber
  undokumentiert und könnte sich ändern. Bewusst nicht angefasst -- ein Wechsel auf
  `calendarView/delta` wäre eine eigene, sorgfältig zu planende Runde (festes Fenster, Neuabzug).
- **Ein Einzeltermin, der in Outlook zur Serie wird, verliert im ERP seine Projekt-/
  Angebotszuordnung** (seit 1.7.8): die lokale `CalendarEvent`-Zeile wird entfernt, damit eine
  ERP-Bearbeitung nie per PATCH die ganze Serie ändert; die Vorkommen erscheinen danach
  schreibgeschützt ohne Zuordnung. Selten, bewusst in Kauf genommen.
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

## Umsetzung 1.9.142: Stand des Abgleichs prüfen (Stufe 6, R1, Punkt 0)

Befund Stufe 6 (5.2, L9): keine Oberfläche zeigt Stand oder Fehler des Abgleichs. Solange es keine gibt, liest `scripts/pruefe_outlook.py` den Stand auf dem Server (Aufruf im Kopf der Datei): je Postfach letzter Lauf, letzter Fehler, Alter des Delta-Links, Pfad des Links ohne Token; Termine, die auf Senden warten (`_needs_push()`, nur Konten mit Postfach), doppelte Outlook-Kennungen, ganztägige Termine aus dem ERP. Das Alter des Delta-Links ist die Zeit seit dem letzten erfolgreichen Lauf, denn nur der schreibt den Link. Nennt der Pfad das Postfach nicht, sagt das Skript das nur als Achtung: Microsoft kann die Adresse durch eine Kennung ersetzen. Test: `tests/test_v562_pruefe_outlook.py`.

## Umsetzung 1.9.143: Konflikte beim Speichern eines Einsatzes (Stufe 6, R1, Punkt 1)

Die Plantafel gehört seit dem Befund Stufe 6 mit dem Kalender zu einer Planung; ihre Regeln stehen deshalb ab hier mit in dieser Datei. Entscheidung Tobias: Konflikte warnen, trotzdem planbar.

- `einsatz_konflikte()` rechnet den einen Einsatz gegen die Einsätze, die seinen Zeitraum berühren, mit `_conflicts()` -- dieselbe Rechnung wie die Tafel, deshalb können Speichern und Tafel nicht auseinanderlaufen. Die Stufe steht an jedem Konflikt (`stufe`: `warnung` oder `hinweis`).
- Gerechnet wird nach dem Flush und vor dem Commit; mit Warnungen rollt `_warnungen_pruefen()` alles zurück. `ensure_preparation(..., festschreiben=False)`, sonst bliebe nach einem 409 eine neue Arbeitsvorbereitung samt Materialbedarf zurück, und die sperrt den Abgleich mit dem Angebot.
- Der Hinweis „Wochenende“ steht nur in der Antwort auf das Speichern, nicht in den Konflikten der Tafel: ein Einsatz über ein Wochenende ist der Normalfall, sein Balken bleibt, wie er war.
- Einsätze stornierter Aufträge fallen ganz aus der Rechnung, auch aus der Kapazität. Abgeschlossene Aufträge und Einsätze auf „abgeschlossen“ zählen weiter; vorgegeben war nur „storniert“.

### Festlegungen 1.9.143 (Bitte bestätigen)

1. Nur Notiz, Status oder Stunden ändern fragt nicht erneut; die Konflikte stehen in der Antwort. Die Rückfrage kommt, wenn sich Kolonne oder Zeitraum ändern.
2. „Wochenende“ färbt den Balken nicht (nur Hinweis beim Speichern); Feiertag und Kapazität färben ihn weiter rot wie bisher -- die Abstufung auf der Tafel kommt mit der Zeichnung.
3. Der Balken eines stornierten Auftrags bleibt auf der Tafel und sagt „Auftrag storniert“.

## Umsetzung 1.9.144: die Plantafel lädt, was sie zeigt (Stufe 6, R1, Punkt 2)

Woher die Zeit kam, steht im Befund Stufe 6, 7.3. Geändert:

- Die Seite lädt `GET /api/planning`, die Auswahl im Dialog erst beim Öffnen über `GET /api/planning/auftraege` (`offene_auftraege()`: eine Abfrage, Nummer und Projekt, nur offene über `auftragsstatus.offen_bedingung()`).
- `planning_board()`: Einsätze nur, die den Zeitraum berühren; läuft einer über den Rand, zusätzlich alle, die in die Spanne dieser Einsätze fallen -- ein Einsatz am Rand meldet seinen Konflikt weiter. `_conflicts()` bekommt nur noch diese, nach Beginn sortiert, und bricht je Einsatz beim ersten ab, der später beginnt.
- `rueckstand()`: offene Aufträge ohne Einsatz im SQL gefiltert, Positionen und Kalkulation auf einmal (`selectinload`), Begründungen der Pause in einer Abfrage (`pause_begruendungen()`).
- `slot_to_dict(tafel=…)`: Einstellungen, sichtbare Mitarbeiter und Pausen einmal für die ganze Tafel; das Objekt über `_einsatz_abfrage()`.

### Messung (wie Befund 7.1: echte Router, lokale PostgreSQL 17 im Wegwerf-Schema, dieser Entwicklungsrechner, Median aus 3 Läufen, dieselbe Welt; bis die Tafel steht = die längere Anfrage)

Vorher (d9d7d06), GET /api/planning und GET /api/orders zugleich:

    Aufträge  Einsätze  Rückstand | GET /api/planning 14 T        | GET /api/orders                | bis die Tafel steht
         200       380         11 |  0,25 s     294 SQL   167 KB  |  2,67 s    8.000 SQL    91 KB  |   2,7 s
        1000     1.900         51 |  1,49 s     665 SQL   180 KB  | 13,39 s   39.284 SQL   458 KB  |  13,4 s
        4000     7.600        201 | 15,35 s   2.069 SQL   228 KB  | 53,47 s  156.596 SQL 1.849 KB  |  53,5 s

Nachher, nur GET /api/planning; die Auswahl erst beim Öffnen des Dialogs:

    Aufträge  Einsätze  Rückstand | GET /api/planning 14 T        | Auswahl im Dialog              | bis die Tafel steht
         200       380         11 |  0,07 s      51 SQL   171 KB  | 0,004 s  1 SQL    7,5 KB       |   0,07 s
        1000     1.900         51 |  0,08 s      51 SQL   184 KB  | 0,004 s  1 SQL   11,3 KB       |   0,08 s
        4000     7.600        201 |  0,13 s      54 SQL   233 KB  | 0,007 s  1 SQL   25,6 KB       |   0,13 s

Speicherspitze eines Aufrufs bei 4000 Aufträgen (Python-Objekte): /api/planning 10 MB statt 124 MB, Auswahl 0,3 MB statt /api/orders 263 MB. Ziel „1000 Aufträge unter 1 s“ erreicht. Der VPS ist langsamer, den Faktor habe ich weiter nicht gemessen. Die Mengenannahmen stehen im Befund (10 Aufträge je Woche, 5 % offen ohne Einsatz).

`GET /api/orders` selbst blieb, wie es war: die Projektliste nutzt es weiter (`projects.html`). Einen Umbau dort hat dieser Punkt nicht verlangt.

### Festlegungen 1.9.144 (Bitte bestätigen)

1. Die Auswahl im Dialog wird bei jedem Öffnen neu geladen (eine Abfrage), kein Zwischenspeichern in der Seite: ein gerade abgeschlossener Auftrag steht sonst noch drin.
2. Die Konflikte eines Einsatzes am Rand des Zeitraums rechnen auch gegen Einsätze außerhalb, solange sie in die Spanne der sichtbaren fallen; ein sehr langer Einsatz weitet die Spanne entsprechend.

## Umsetzung 1.9.145: F12, der geplante Zeitraum der Arbeitsvorbereitung (Stufe 6, R1, Punkt 3)

Beleg im Befund Stufe 6, 3.4 (V1–V7). `sync_preparation_dates()` ist weg. `planned_start`/`planned_end` sind nur noch, was jemand von Hand eingegeben hat (oder beim Anlegen aus dem Auftrag kam).

- Lesen: `preparation_to_dict()` und `app/akte.py::ausfuehrung()` liefern mit Einsätzen deren Zeitraum (`einsatz_zeitraum()`: Minimum, Maximum, eine Abfrage); ohne Einsatz die Eingabe.
- Schreiben: mit Einsätzen lehnt `zeitraum_ohne_einsatz_pruefen()` einen anderen Zeitraum ab (409), derselbe stört nicht; alles andere geht weiter. Die Seite sperrt die Felder und schickt sie nicht mit.
- Einsatz löschen: die Eingabe gilt wieder (bis 1.9.144 stand die Arbeitsvorbereitung leer da).
- Nicht angefasst: wer die Spalten ohne Einsatz liest (`_relevant_preparation_ids_for_employee()`, Rückstand) -- dort gab es keinen Einsatz, die Eingabe ist richtig.

### Festlegungen 1.9.145 (Bitte bestätigen)

1. Stand von vor 1.9.145: was ein Einsatz in die Spalten geschrieben hat, bleibt dort stehen und gilt als Eingabe, sobald der letzte Einsatz weg ist. Keine Migration, die alte Eingabe ist nicht mehr bekannt.
2. Derselbe Zeitraum von Hand gesendet (mit Einsätzen) ergibt 200, ein anderer 409.
3. Der Hinweis auf der Seite verlinkt die Plantafel ohne Datum; dass sie auf den Zeitraum springt, gehört zum Bruch B1 und kommt mit der Zeichnung.

### Tests und Prüfung

Angepasste Erwartungen (Regel 28): `test_v090::test_planning_slot_updates_work_preparation_dates_and_can_switch_team` und `::test_multiple_slots_define_overall_work_preparation_period`, altes Soll: die Spalten der Arbeitsvorbereitung folgen dem Einsatz, neues Soll: `einsatz_zeitraum()` folgt ihm. `test_v329`: Eintrag `PUT /api/orders/{order_id}/work-preparation` aus `BEKANNT` gestrichen. `test_v399::test_postgresql_planeinsatz_beginn_und_ende_gleichzeitig`, altes Soll: die Spalten folgen dem Einsatz, neues Soll: `einsatz_zeitraum()`. `test_v399::test_postgresql_planeinsatz_entfernen_und_verschieben_ohne_deadlock`, Aufbau: angehalten wird nach dem Flush des DELETE statt in `sync_preparation_dates()`, die Erwartung (404, kein Deadlock) bleibt.

Nachtrag 1.9.147: `tests/test_v563_konflikte_pg.py` prüft die Warnliste unter PostgreSQL im Wegwerf-Schema: nichts bleibt zurück, die Sperre der Arbeitsvorbereitung ist nach dem Ablehnen frei, Tafel und Auswahl laufen.

## Umsetzung 1.9.148: P3, P4, P6, P13 (Stufe 6, R1, Punkt 6)

- P6: `calendar.html::loadEvents()` schickt die Tage als Wandzeit (`toLocalIso(toDateStr(…))`). `app/calendar_events.py::zeitraum_berlin()`: eine Grenze ohne Zeitzone gilt schon als Wandzeit, eine mit Zeitzone wird umgerechnet -- so entscheidet nicht mehr die Zeitzone der Datenbanksitzung. Dieselbe Funktion in `list_series_occurrences()`. Geprüft in Tag, Woche und Monat, Winter und Sommer, im Browser in Berlin und in UTC.
- P4: `saveNew()` schickt leer als null, der Server rechnet die Reststunden (`_remaining_order_hours()`); der Dialog nennt das im Feld. `saveEdit()` schickt leer gar nicht.
- P3: `a.type?a.name+' ('+a.type+')':a.name`.
- P13: `stunden_text()` aus `app/akte.py` in Kapazitätsmeldung und Formel.

### Festlegungen 1.9.148 (Bitte bestätigen)

1. Beim Bearbeiten eines Einsatzes heißt leeres Stundenfeld „unverändert“, nicht „Reststunden“ (bis 1.9.147: 0 h). Der Server bleibt dabei: `planned_hours: null` beim PUT ist 422.
2. Die Formel zeigt Stunden mit zwei Stellen wie „Zeiten“: „24,00 h / (4 MA × (8,00 h − 0,00 h)) = 0,75 Teamtage“.

### Tests und Prüfung

Angepasste Erwartung (Regel 28): `test_v390`, Eintrag `calendar.html` „start:start.toISOString(),end:end.toISOString()“ aus `ERLAUBT` gestrichen: die Stelle gibt es nicht mehr.

## Umsetzung 1.9.150: das Wochenende ist kein Hinweis (Stufe 6, R1 Nachrunde, Punkt 1)

Vorgabe Tobias: ein Einsatz über ein Wochenende meldet nichts, das Wochenende ist nur kein Arbeitstag (Zeichnung `bildgrundlage/entwurf-stufe6/plantafel-regeln.html`, „Zeitraum“). `_wochenend_hinweise()` ist weg, `HINWEIS_ARTEN` kennt nur noch Feiertag/betriebsfreien Tag und Kapazität. Damit ist die Festlegung 1.9.143 Nr. 2 in ihrem ersten Halbsatz überholt („Wochenende“ gibt es nicht mehr); dass Feiertag und Kapazität den Balken rot färben, bleibt bis zur Zeichnung.

### Festlegungen 1.9.150 (bestätigt am 31.10.2026)

1. Auch „Kein Arbeitstag“ für einen Wochentag, an dem der Betrieb laut Einstellungen nicht arbeitet, meldet nichts: dieselbe Regel, dieselbe Funktion war weg.
2. Ein Feiertag oder betriebsfreier Tag an einem Tag, der ohnehin kein Arbeitstag ist, meldet nichts (weder beim Speichern noch auf der Tafel). Sonst meldete ein Einsatz über ein Wochenende doch etwas, sobald ein Feiertag darauf fällt.

### Tests und Prüfung

Angepasste Erwartungen (Regel 28): `test_v563::test_wochenende_200_mit_hinweis_und_faerbt_die_tafel_nicht` hieß so und erwartete zwei Hinweise „Wochenende“; neu `test_wochenende_meldet_nichts`, keine Hinweise. `klicktest_plantafel_konflikte`: „Hinweis: steht über der Tafel“ prüfte „Wochenende · 24.10.“; neu ein eigener Einsatz über einen betriebsfreien Tag („Feiertag: Betriebsausflug · 28.10.“), Bild `hinweis_betriebsfrei` statt `hinweis_wochenende`, dazu vier Prüfungen „Wochenende: …“ (gespeichert, kein Dialog, kein Hinweis, nicht rot); Büro – Auftrag sieht vier statt drei Einsätze, weil einer dazukam. Neu: `test_kein_arbeitstag_unter_der_woche_meldet_nichts`, `test_feiertag_am_wochenende_meldet_nichts`.

## Umsetzung 1.9.151: Einsätze abgeschlossener Aufträge zählen nicht (Stufe 6, R1 Nachrunde, Punkt 2)

Entscheidung Tobias, löst den zweiten Satz der Festlegung 1.9.143 Nr. 3 ab („Abgeschlossene Aufträge zählen weiter als Konflikt“). `_conflicts()`, `einsatz_konflikte()` und die Belegung der Geräte fragen `auftragsstatus.geschlossen()` statt `storniert()`. Weil `_conflicts()` die Einsätze vorne filtert, fehlen sie auch in den Verteilungen -- damit in den Stunden von Kolonne und Person. `create_slot()` lehnt einen neuen Einsatz an einem geschlossenen Auftrag weiter ab (409), ein bestehender lässt sich weiter verschieben und fragt dabei nichts.

### Festlegungen 1.9.151 (bestätigt am 31.10.2026)

1. Der Balken bleibt auf der Tafel und sagt „Auftrag abgeschlossen“, wie der stornierte „Auftrag storniert“. Keine eigene Farbe: das Aussehen kommt mit der Zeichnung.
2. Wird der Auftrag fortgesetzt („Fortsetzen“, mit Begründung), zählen seine Einsätze sofort wieder, auch rückwirkend für Einsätze, die inzwischen daneben geplant wurden: dann steht beides rot auf der Tafel, ohne Rückfrage.

### Tests und Prüfung

Angepasste Erwartung (Regel 28): `test_v563::test_abgeschlossener_auftrag_zaehlt_weiter` erwartete 409 beim zweiten Einsatz neben einem abgeschlossenen; der Test ist weg, neu `test_einsatz_eines_geschlossenen_auftrags_zaehlt_nicht` (bisher nur storniert, jetzt beide Status, Soll 200 ohne Warnung und null Stunden). Neu: `test_geraet_eines_geschlossenen_auftrags_zaehlt_nicht`, `test_einsatz_eines_abgeschlossenen_auftrags_verschieben_fragt_nicht`, `test_fortgesetzter_auftrag_zaehlt_wieder`. `klicktest_plantafel_konflikte`: vier Prüfungen „Abgeschlossen: …“, Bild `abgeschlossen_zaehlt_nicht`.

## Umsetzung 1.9.155: L6, kein „Einsatz planen“ ins Leere (Stufe 6, R1 Nachrunde, Punkt 6)

Befund Stufe 6, L6. `app/akte.py::ausfuehrung()` liefert `einsatz_gesperrt` (`auftragsstatus.einsatz_gesperrt()`, derselbe Text wie die 409 beim Speichern); die Akte versteckt danach den Link und nennt den Grund. `GET /api/planning/auftraege/{id}` sagt für `?auftrag=<id>`, warum ein Auftrag nicht in der Auswahl steht; `openCreate()` fragt ihn nur, wenn der Auftrag dort fehlt.

### Festlegungen 1.9.155 (bestätigt am 31.10.2026)

1. Ein pausierter Auftrag behält „Einsatz planen“: „pausiert“ sperrt nichts (seit 1.9.124).
2. Die Karte „Einsätze“ eines geschlossenen Auftrags zeigt seine Einsätze weiter, darunter den Grund.
3. Der Grund über der Tafel bleibt stehen, bis der nächste Dialog „Einsatz planen“ öffnet oder der nächste Einsatz gespeichert wird.

### Tests und Prüfung

`tests/test_v573_einsatz_planen_geschlossen.py`; `klicktest_plantafel_konflikte`: Prüfungen „L6 …“. Angepasste Erwartungen: keine.

## Stand der Festlegungen von Stufe 6, R1 (Tobias, 31.10.2026)

Bestätigt: alle Festlegungen 1.9.143 bis 1.9.149, ausdrücklich 1.9.146 Nr. 1 (eine genehmigte Abwesenheit löscht nur der Admin) und Nr. 6 („Zeiten → Abwesenheiten“ öffnet mit „Alle“). Anders entschieden, in der Nachrunde umgesetzt: 1.9.143 Nr. 3 in ihrem Zusatz (abgeschlossene zählen nicht, 1.9.151), 1.9.146 Nr. 5 (offener Antrag als Hinweis, 1.9.152), 1.9.146 Nr. 7 („Vermerk:“ statt „Freigabe:“, 1.9.154). Die Zeichnung `bildgrundlage/entwurf-stufe6/` ist freigegeben, gebaut wird sie in einer eigenen Runde.

## Umsetzung 1.9.156: was der Balken sagt, passt hinein (Stufe 6, R1 Nachrunde, Nachtrag)

`.slot` ist 56 px hoch mit `overflow:hidden`, es passen drei Zeilen. Status des Auftrags und offene Anträge standen als vierte. `slotHinweis()` fasst sie in einer Zeile zusammen, die an die Stelle der Adresse tritt; `title` trägt sie vollständig. Klicktests dürfen bei abschneidenden Flächen nicht nur `textContent` lesen: `klicktest_plantafel_konflikte::_zeile_im_balken()` vergleicht die Lage der Zeile mit der des Balkens.

### Festlegungen 1.9.156 (bestätigt am 31.10.2026)

1. Hat ein Balken einen Status oder einen offenen Antrag, steht das statt der Adresse in der dritten Zeile; die Adresse steht weiter im Dialog des Einsatzes. Ein höherer Balken hätte die ganze Tafel verschoben, das Maß kommt mit der Zeichnung.
2. Alles in einer Zeile, getrennt mit „ · “, gekürzt mit „…“, vollständig im Tooltip.

### Tests und Prüfung

`tests/test_v574_balken_lesbar.py`; `klicktest_plantafel_konflikte`: drei Prüfungen „… Zeile im Balken zu sehen“. Angepasste Erwartungen: keine.

## Umsetzung 1.9.157: ganztägige Termine (Stufe 6, R2, Punkt 1)

Quellen: Microsoft, „event resource type“: „isAllDay … start, and endtime must be set to midnight and be in the same time zone“; „dateTimeTimeZone“ führt Europe/Berlin unter den zusätzlichen Zeitzonen. Dass Graph einen ganztägigen Termin als Mitternacht mit „UTC“ zurückgibt, auch mit „Prefer: outlook.timezone“, steht nicht in der Doku, nur in Berichten auf Microsoft Q&A; `_ganztag_tag()` nimmt deshalb den Datumsteil und fängt die andere denkbare Form (23:00 des Vortags) mit ab. Am echten Mandanten nicht geprüft.

Im ERP steht ein ganztägiger Termin auf Mitternacht, `end_at` ist der letzte Tag selbst (so schickt ihn der Dialog, so liest ihn `eventsForDay()`). Das Ende bei Microsoft ist der Tag danach: die Umrechnung sitzt nur in `_zeiten_an_graph()` und `_zeiten_aus_graph()`.

### Festlegungen 1.9.157 (bestätigt am 31.10.2026)

1. Zeitzone ganztägiger Termine nach Outlook ist fest Europe/Berlin, unabhängig von der Einstellung des Postfachs.
2. Die Migration ändert nur Zeilen mit einer Uhrzeit. Ein ganztägiger Termin auf Mitternacht bleibt, auch wenn er aus Outlook stammt; einen, den jemand vor 1.9.157 im Dialog auf zwei Tage gespeichert hat, erkennt sie nicht.
3. `downgrade()` stellt die falsche Form nicht wieder her: der Vorzustand war der Fehler, die alte Fassung liest die neue Form.

### Tests und Prüfung

Angepasste Erwartungen (Regel 28): `test_v562::test_ganztaegige_termine_aus_dem_erp_nicht_aus_outlook` hieß so und erwartete jeden ganztägigen Termin aus dem ERP als Fund; neu `test_ganztaegige_termine_mit_uhrzeit_nicht_auf_mitternacht`, Fund ist die Uhrzeit, unabhängig von der Herkunft. `FakeGraphServer` (test_v297): `_fields_from_payload()` lehnt einen ganztägigen Termin ohne Mitternacht mit 400 ab und liefert ihn als Mitternacht „UTC“ zurück.

## Umsetzung 1.9.158: abgelaufener Delta-Link (Stufe 6, R2, Punkt 2)

Quelle: Microsoft, „Use delta query“: „Synchronization reset“ (410 Gone mit Location-Kopfzeile), „Token duration“ (bei Outlook „the upper limit isn't fixed“, „a 40X-series error with error codes such as syncStateNotFound“). Am echten Mandanten nicht ausgelöst. Die Location-Kopfzeile wird nicht gebraucht: der Abruf beginnt mit derselben Adresse wie beim ersten Mal.

`_delta_abgelaufen()`: 410 immer; sonst nur 40X mit einem der Codes in `_DELTA_ABGELAUFEN_CODES`, auch verschachtelt (`innerError`). 403, 401, 429, 500 und 404 ohne den Code setzen nichts zurück.

### Festlegungen 1.9.158 (bestätigt am 31.10.2026)

1. Nach jedem Abruf des ganzen Kalenders (Rückstellung oder kein Link) fragt der Lauf jeden lokalen Termin einzeln nach, der im Abruf fehlt; gelöscht wird nur bei 404. Eine andere Antwort lässt ihn stehen, ohne Fehler am Postfach.
2. Die Rückstellung steht nur im Protokoll und in der Antwort (`delta_reset`), nicht als letzter Fehler: der Lauf ist gelungen.

### Tests und Prüfung

Angepasste Erwartungen: keine. `FakeGraphServer` nimmt einen Präfix für die Termin-IDs (Vorgabe wie bisher „graph“).

## Umsetzung 1.9.159: Sperre je Postfach, eindeutige Kennung (Stufe 6, R2, Punkt 3)

Keine Zeilensperre: sie hielte über Minuten eine Datenbankverbindung samt Transaktion (Regel 35), und der Lauf committet je Termin. Kein Advisory-Lock: unter SQLite gibt es keinen. Stattdessen eine Belegung in der Zeile des Postfachs (`lauf_kennung`, `lauf_seit`), gesetzt mit einem bedingten UPDATE: unter PostgreSQL wartet das zweite UPDATE auf die Zeile und prüft die Bedingung danach neu, unter SQLite gibt es nur einen Schreiber.

Das Fernlöschen läuft ohne Sperre: es legt nichts an.

Die Kennung gilt nur in ihrem Postfach, deshalb sucht der Abruf einen Termin über (Postfach, Kennung). Findet er ihn dort nicht, aber am selben Konto unter derselben Kennung, liegt er hier: die Adresse wurde umbenannt oder die Zeile stammt von vor 1.9.159.

### Festlegungen 1.9.159 (bestätigt am 31.10.2026)

1. Die Belegung gilt zehn Minuten (`SPERRE_GILT`), ein lebender Lauf erneuert sie höchstens einmal je Minute. Ein gestorbener Prozess hält das Postfach also bis zu zehn Minuten; in der Zeit meldet der Abgleich „busy“ und Speichern sendet nicht.
2. Speichern während eines Laufs sendet nicht und wartet nicht: der Termin geht mit dem nächsten Lauf (Öffnen von `/kalender` oder Cron).
3. Adressen stehen klein geschrieben in der Datenbank, auch auf der Benutzerseite.
4. Migration, zwei Konten am selben Postfach: das aktive behält es, sonst das ältere; das andere wird leer, ohne Rückfrage.
5. Migration, doppelte Termine: es bleibt die Zeile mit Projekt oder Angebot, sonst die älteste. Eine weitere mit eigenem Bezug bleibt ohne Verbindung und geht beim nächsten Lauf als neuer Termin nach Outlook; eine ohne eigenen Bezug fällt weg.
6. Migration, Delta-Link auf eine andere Adresse: wird geleert, der nächste Lauf liest den ganzen Kalender. Nennt der Pfad keine Adresse, bleibt er.
7. `downgrade()` bringt weder die alte Schreibweise der Adressen noch die als doppelt entfernten Zeilen zurück.

### Tests und Prüfung

Angepasster Aufbau (Regel 28): `test_v297`, `test_v562`, `test_v568`, `test_v576`: `get_or_create_sync_state()` und `OutlookCalendarSyncState` nehmen die Adresse statt des Kontos, `OutlookSeriesOccurrence` braucht `outlook_postfach`; die Erwartungen bleiben.

## Umsetzung 1.9.160: Besitzer- und Postfachwechsel (Stufe 6, R2, Punkt 4)

Beide Wechsel sehen am Termin gleich aus (`outlook_postfach` ungleich dem Postfach des Besitzers) und brauchen doch Verschiedenes: wer im Dialog einen Besitzer wählt, will den Termin dort haben; wer eine Adresse ändert, hat vielleicht nur einen Irrtum berichtigt, und das alte Postfach gehört jemand anderem. Deshalb löst der Besitzerwechsel die Verbindung sofort, im Router, ohne Netz. Was danach noch woanders liegt, kommt aus einem Postfachwechsel.

Der Eintrag „Resurrection-Risiko“ unter „Bekannte, bewusst offene Punkte“ ist damit erledigt.

### Festlegungen 1.9.160 (bestätigt am 31.10.2026)

1. Besitzer wechseln: die Kopie im alten Postfach wird gelöscht, auch wenn der Termin aus Outlook stammt. Der Termin geht als neuer ins neue Postfach (neue Kennung). Teilnehmer und Anhänge des alten Termins kennt das ERP nicht, sie gehen nicht mit.
2. Neuer Besitzer ohne Postfach: der Termin verliert die Verbindung und bleibt nur im ERP.
3. Postfach am Konto wechseln: aus dem alten Postfach löscht das ERP nur, was es selbst dort angelegt hat (`external_source` „erp“). Was aus Outlook stammt, bleibt dort und fällt im ERP weg, außer es hängt an einem Projekt oder Angebot: dann bleibt es, wird Termin des ERP und geht als Kopie ins neue. Dort liegt es dann zweimal, im alten unverändert.
4. Postfach entfernen: Einzeltermine bleiben im ERP mit ihrer Kennung, werden aber nicht mehr abgeglichen; eine Änderung im ERP erreicht das Postfach nicht mehr, Löschen schon. Serienvorkommen fallen weg.
5. Wer ein Postfach neu bekommt, liest es ganz, auch wenn dafür noch ein Stand da ist. Liegt dort schon ein Termin eines anderen Kontos, geht er auf das neue Konto über.
6. Löschauftrag: 404 (schon weg) und 403 (nicht freigegeben) geben auf, 403 steht im Protokoll, die Kopie bleibt dann in dem Postfach. Andere Fehler bleiben offen und werden bei jedem Lauf und jedem Speichern wieder versucht.
7. PATCH mit 404: der Termin wird neu angelegt. Wurde er genau in dem Moment in Outlook gelöscht, zwischen Abruf und Senden, kommt er wieder.
8. Beim Abruf des ganzen Kalenders gilt eine Kennung, die das Postfach einzeln mit 404 beantwortet, als in Outlook gelöscht: der Termin fällt im ERP weg, auch mit Projekt oder Angebot, wie bei einem @removed. Das trifft auch eine Zeile von vor 1.9.159, die in Wahrheit in einem anderen Postfach lag (Befund XB6: Besitzer gewechselt): ihre Kopie dort kommt über das andere Postfach herein, der Bezug zum Projekt geht verloren.

### Tests und Prüfung

Angepasste Erwartungen: keine; das Befundverhalten XB1–XB6, XC1 und XP1 stand in keinem Test. Neue Spalte im Wächter `test_v364::OHNE_FESTE_WERTE`: `outlook_delete_orders.last_error_type`.

## Umsetzung 1.9.161: mehrere Postfächer, Konto oder Gerät (Stufe 6, R2, Punkt 5)

Entscheidung Tobias: Postfächer sind Tobias und neu ein eigenes Kran-Postfach, Kran-Kalender in beiden Richtungen, Termine entstehen dort auch direkt in Outlook. Regel aus der Zeichnung: Einträge im Kran-Kalender belegen den Kran und warnen bei Doppelbelegung; für Einsätze ist später die Plantafel führend.

`Postfach` (Adresse plus Konto oder Gerät) ersetzt im Abgleich den Parameter `user`. `sync_user_calendar()` bleibt für das Öffnen von `/kalender`, `sync_postfach()` ist der Lauf für beides.

### Festlegungen 1.9.161 (bestätigt am 31.10.2026)

1. Das Kran-Postfach läuft nur mit dem Cron (alle 15 Minuten), nicht beim Öffnen des Kalenders: ein Eintrag in Outlook warnt frühestens nach dem nächsten Lauf. Was im ERP entsteht, geht sofort hinaus.
2. Die Warnung steht nur beim Speichern eines Einsatzes. Die Tafel zeichnet Kran-Termine erst mit R4; ein trotzdem geplanter Einsatz ist bis dahin dort nicht rot.
3. Der Einsatz belegt ganze Tage: jeder Termin an einem Arbeitstag des Einsatzes warnt, auch einer von zwei Stunden. Ein Termin nur an einem freien Tag (Einsatz Freitag bis Montag, Termin am Samstag) warnt nicht. Hat der Einsatz gar keinen Arbeitstag, zählen alle seine Tage.
4. Es warnt nur das Speichern eines Einsatzes. Ein Kran-Termin, der im ERP-Kalender oder in Outlook neben einem Einsatz entsteht, warnt nicht; `scripts/pruefe_outlook.py` nennt solche Überschneidungen (1.9.163).
5. Ein privater Termin am Kran ist für alle „Belegt“, auch für die Person, die ihn angelegt hat: ein Gerät hat keinen Besitzer, der ihn lesen dürfte.
6. Im Dialog steht das Gerät in derselben Auswahl wie die Konten („Kran 30 m (Gerät)“), zu sehen sind nur aktive Geräte mit Postfach.
7. Ein Gerät mit Terminen wird beim Löschen nur deaktiviert, wie eines an einer Kolonne. Ein deaktiviertes Gerät gleicht nicht mehr ab.
8. Gesehen wird der Standardkalender des Postfachs. Ein Termin mit „frei“ (`showAs`) belegt den Kran wie jeder andere.

### Tests und Prüfung

Angepasster Aufbau (Regel 28): `test_v577::test_treffen_sich_zwei_laeufe_…` übergibt das Postfach statt des Kontos, die Erwartung bleibt.

## Umsetzung 1.9.162: Stand je Postfach in den Einstellungen (Stufe 6, R2, Punkt 6)

`postfach_uebersicht()` liest nur und fragt Microsoft nicht, sonst dauerte das Öffnen der Einstellungen je Postfach einen Netzaufruf. Einen Knopf „Verbindung testen“ oder „Neu einlesen“ gibt es weiter nicht (Befund L9), verlangt war der Stand.

### Festlegungen 1.9.162 (bestätigt am 31.10.2026)

1. Auch inaktive Konten und Geräte mit Postfach stehen in der Liste, gekennzeichnet; sie gleichen nicht ab.
2. „Wartet auf Senden“ zählt auch Termine, die nach einem Postfachwechsel noch im alten liegen, „wartet auf Löschen“ steht nur da, wenn etwas offen ist.
3. Das Postfach eines Kontos ändert man weiter auf der Benutzerseite, die Zeile verlinkt dorthin; das eines Geräts in diesem Abschnitt, weil es nur der Admin ändert und die Stammdaten der Geräte ab Büro – Auftrag offen sind.
4. Die Auswahl „Gerät“ bietet nur aktive Geräte ohne Postfach an: ein Wechsel geht über Entfernen und neu zuordnen. Entfernen fragt mit `confirm()` nach (Regel 4).
5. Ein Fehler von vor 1.9.162 hat keinen Status und steht als „Microsoft hat nicht geantwortet“, bis der nächste Lauf ihn ersetzt oder löscht.

### Tests und Prüfung

Angepasste Erwartung (Regel 28): `test_v473::UTC_FELDER` um `letzter_lauf`, `fehler_am`, `laeuft_seit` erweitert. Klicktest `klicktest_outlook_postfaecher` neu.

## Umsetzung 1.9.163: `scripts/pruefe_outlook.py` (Stufe 6, R2, Punkt 7)

`app/planning.py::termine_der_geraete()` liefert die Überschneidungen ohne Text; die Warnung beim Speichern und das Skript nehmen dieselbe Rechnung.

### Festlegungen 1.9.163 (bestätigt am 31.10.2026)

1. Eine laufende Sperre ist kein Fund, eine abgelaufene schon (Rückgabe 1), auch wenn der nächste Lauf sie übernimmt: sie zeigt, dass ein Prozess gestorben ist.
2. „Gerät doppelt“ zählt Einsätze, die heute oder später enden, auf offenen Aufträgen; ein Fund ist auch, was jemand mit „Trotzdem planen“ bewusst gespeichert hat.

### Tests und Prüfung

Angepasste Erwartungen: keine. `test_v562::test_ohne_postfach_und_termin_nichts_gefunden` prüft zusätzlich die neuen Zeilen.

## Befund und Einrichtung: ein Postfach, das keinem Konto gehört (Stufe 6, R2, Punkt 0)

Anbindung: eine App-Registrierung für E-Mail und Kalender, Client-Credentials-Flow, Token mit Scope `.default`, dasselbe für jedes Postfach; niemand meldet sich an einem Postfach an. Rechte nur über Exchange „RBAC for Applications“ (Regel 17): Rollen `Application Mail.Send` und `Application Calendars.ReadWrite`, Scope `ERP-Zugriff`. Graph spricht jedes Postfach über `/users/<adresse>` an, ob Person, freigegeben oder Gerät; der Code unterscheidet das nicht.

Einrichtung, Vorschlag freigegebenes Postfach (Quellen: Microsoft, „About shared mailboxes“: bis 50 GB ohne eigene Lizenz, wer zugreift, braucht ein lizenziertes Postfach, höchstens 25 Personen, Anmeldung sperren; „Role Based Access Control for Applications“: nur direkte Gruppenmitgliedschaft zählt, Änderungen wirken nach 30 Minuten bis 2 Stunden, `Test-ServicePrincipalAuthorization` umgeht den Zwischenspeicher):

    New-Mailbox -Shared -Name "Kran" -PrimarySmtpAddress kran@dachkonzepte.gmbh
    Add-MailboxPermission -Identity kran@dachkonzepte.gmbh -User <person> -AccessRights FullAccess
    Add-DistributionGroupMember -Identity ERP-Zugriff@dachkonzepte.gmbh -Member kran@dachkonzepte.gmbh
    Test-ServicePrincipalAuthorization -Identity <AppId> -Resource kran@dachkonzepte.gmbh

Nichts in Entra, kein neues Secret, keine neue Rollenzuweisung. Danach im ERP Einstellungen → Outlook-Kalender → „Postfach für ein Gerät“. Für das Gerät ist der Cron (`scripts/sync_outlook_calendars.py`) der einzige Weg aus Outlook ins ERP.

Stand 31.10.2026: nichts davon am echten Mandanten ausgeführt oder geprüft. Offen, ob ein freigegebenes Postfach ohne Lizenz über Graph mit App-Rechten antwortet (Microsoft nennt keine Pflicht, ein Forenbeitrag das Gegenteil); der erste Lauf zeigt es in den Einstellungen.

## Stufe 6, R3a: Plantafel-Modell -- Besetzung, Geräte, Status (ab 1.9.233)

Vorgabe Tobias (06.11.2026), Zeichnung `bildgrundlage/entwurf-stufe6/` (neue Fassung, freigegeben; neu: Zeile „Ohne Kolonne“, Kran-Kalender), Regeln
`plantafel-regeln.html`. Punkte: 1 Befund zuerst (Modell nach den Stufen 2 bis 7, was die Zeichnung ändert, Plan der Migrationen; widerspricht etwas
der Zeichnung: anhalten und melden); 2 Besetzung je Einsatz; 3 Geräte je Einsatz, alle oder einzelne Tage; 4 Status vorläufig | fest; 5 Konflikte auf
dem neuen Modell; 6 die heutige Oberfläche bleibt bedienbar. Das neue Aussehen kommt mit R4, Kranvermietung, Kran-Kalender und „Heute“ mit R3b.

### Befund (Punkt 1)

**Das Modell bis 1.9.232** (nach Stufe 2 bis 7; Kalender seit R2, Kapazität aus der Sollzeit seit 1.9.211):

    Order 1 ── 0..1 WorkPreparation „AV“
                    ├─ n WorkPreparationEmployee            Einzelzuweisung, ohne Datum
                    ├─ n WorkPreparationTeamAssignment       eine je AV und Kolonne (UNIQUE), Schnappschuss beim ersten Zuweisen
                    │       ├─ n WorkPreparationTeamEmployee     Personen (Name, Rolle)
                    │       └─ n WorkPreparationTeamResource     Geräte = OperationalResource (Name, Typ, Rolle)
                    └─ n PlanningSlot „Einsatz“              team_assignment_id NOT NULL, start/end, status (Freitext), notes
                            └─ 0..1 PlanningSlotCapacity     Stunden, Anfahrt je Person und Tag

- Wer an einem Einsatz arbeitet, steht nirgends am Einsatz: es ist der Schnappschuss der Kolonnen-Zuweisung an der AV (für alle Einsätze dieser
  Kolonne an diesem Auftrag derselbe), dazu für „Heute“ jede Einzelzuweisung an der AV (sieht jeden Einsatz der AV, B5).
- Geräte ebenso nur über die Kolonnen-Zuweisung, für alle Tage. Prüffristen (`OperationalAssetInspection.next_due_date` am Betriebsmittel mit
  `resource_id`) kennt die Plantafel nicht (W7). Termine im Kalender eines Geräts (`CalendarEvent.resource_id`, Kran-Postfach seit 1.9.161) zählen
  beim Speichern als „Gerät doppelt“ (`termine_der_geraete()`).
- Status: Freitext (geplant, bestaetigt, in_ausfuehrung, pausiert, abgeschlossen), ohne Wirkung (Befund Stufe 6, 3.3).
- Kapazität je Person und Tag = Sollzeit des Lohns − Anfahrt (seit 1.9.211, `_soll_je_tag()`), Feiertag 0, Freistellung des Arbeitszeitkalenders 0.
- Konflikte (`_conflicts()`): Warnung Kolonne doppelt, Person doppelt (nur Personen der Kolonnen-Schnappschüsse), Gerät doppelt (Kolonnen-Geräte und
  Kalender des Geräts), Person abwesend; Hinweis Feiertag/betriebsfreier Tag, Freistellung des Kalenders, Kapazität, Antrag offen; Einsätze
  geschlossener Aufträge zählen nicht.
- Leser des Modells: Tafel (`planning_board()`, Zeilen je Kolonne/Person/Gerät), Konflikte und Kapazität, Speichern (`einsatz_konflikte()`),
  „Heute“ und „Nächste Tage“ (`_employee_assignment_slot_condition()`), Zugriff der Monteurin auf den Auftrag (`app/orders.py::
  _assigned_order_id_queries()`: AV-Kolonne, AV-Einzelzuweisung, eigener Bericht), Akte (`app/akte.py::einsaetze()`: Kolonne und Personenzahl), AV-Seite
  (Kolonnen an der AV, Entfernen gesperrt, solange ein Einsatz daran hängt -- L2), Löschschutz einer Ressource (`resource_planning.py`).

**Was die Zeichnung daran ändert:**

| Zeichnung | Modell |
|---|---|
| Besetzung = die Personen dieses Einsatzes; die Kolonne schlägt sie vor; „ohne Kolonne“ wählt Personen einzeln; eine spätere Änderung der Kolonne ändert keinen bestehenden Einsatz | neue Tabelle `planning_slot_employees` (Einsatz, Person); `planning_slots.team_assignment_id` wird optional (leer = ohne Kolonne) |
| Geräte je Einsatz, alle oder einzelne Tage | neue Tabelle `planning_slot_resources` (Einsatz, Gerät, Tage; leer = alle Tage) |
| Status vorläufig (gestrichelt) oder fest; „geplant“ wird vorläufig, alles andere fest; abgeschlossen/storniert kommt vom Auftrag | `planning_slots.status` nur noch `vorlaeufig` / `fest` |
| Warnung: Person doppelt, Person abwesend, Gerät doppelt, Gerät mit abgelaufener Prüffrist; Hinweis: Antrag offen, Feiertag/betriebsfreier Tag, Kapazität | „Kolonne doppelt“ entfällt (die Personen zählen); Prüffrist neu; alles aus Besetzung und Geräten des Einsatzes |
| Kapazität je Einsatz | aus der Besetzung (die Rechnung je Person und Tag bleibt die aus 1.9.211) |

**Kein Widerspruch zur Zeichnung.** Zwei Stellen, bei denen die Vorgabe dieser Runde und die Zeichnung verschieden formuliert sind, beide ohne
Widerspruch im Modell:
1. Die Zeichnung schreibt „Kapazität = Personen × Arbeitstage × (Tagesstunden − Anfahrt)“ (Dialog: „2 Personen × 3 Arbeitstage × 7,50 h“). Sie ist
   älter als 1.9.211 (Sollzeit des Lohns); gerechnet wird nach der Vorgabe dieser Runde aus der Sollzeit der Besetzung an den Arbeitstagen minus Anfahrt
   (je Person und Tag). In der Woche der Zeichnung (KW 45) ergibt das nach dem Tarif 8,00 h je Person und Tag (KW 18–48), die Zeichnung zeigt 7,50 h
   (die Tagesstunden der Planung): 2 Personen × 3 Arbeitstage sind 48,00 h statt 45,00 h. Wie die Formel im Dialog steht, kommt mit R4.
2. „Person doppelt (auch einzeln zugeordnete, Befund B5/B6)“: in der Zeichnung gibt es Einzelne nur am Einsatz („ohne Kolonne“). Die Einzelzuweisung an
   der AV (B5/B6) bleibt eine Zuweisung ohne Datum (Zugriff auf den Auftrag); was heute an Einsätzen aus ihr folgt (die Person sieht jeden Einsatz der AV
   auf „Heute“), übernimmt die Migration als Besetzung -- danach zählt sie wie jede Person am Einsatz (Festlegung 1.9.233 Nr. 6).

**Plan der Migrationen** (je auf einem Bestand unter SQLite und PostgreSQL geprobt, mit downgrade()):
- 1.9.233 (Punkt 2): Tabelle `planning_slot_employees`; `planning_slots.team_assignment_id` NULL erlaubt; je Einsatz die Personen des Schnappschusses
  seiner Kolonnen-Zuweisung und die Einzelzuweisungen seiner AV. downgrade(): bricht ab, solange ein Einsatz ohne Kolonne besteht (die alte Fassung
  kennt keinen), sonst Tabelle weg, Spalte wieder NOT NULL.
- 1.9.234 (Punkt 3): Tabelle `planning_slot_resources`; je Einsatz die Geräte seiner Kolonnen-Zuweisung, alle Tage. downgrade(): Tabelle weg.
- 1.9.235 (Punkt 4): Status „geplant“ -> vorlaeufig, jeder andere (auch leer) -> fest. downgrade(): vorlaeufig -> geplant, fest -> bestaetigt (die
  übrigen Freitexte hatten keine Wirkung, Befund 3.3, und kommen nicht zurück).
- 1.9.236 (Punkt 5) und 1.9.237 (Punkt 6): keine Migration.

Nicht Teil dieser Runde (bleibt, wie es ist): die Kolonnen-Zuweisung an der AV mit Schnappschuss (AV-Seite, Zugriff der Monteurin; B7/B8 -- die alte
Kolonne behält nach dem Umplanen den Zugriff), „Heute“ in neuer Form (R3b), das Aussehen (R4).

### Umsetzung 1.9.233: Besetzung je Einsatz (Punkt 2)

- Modell: `PlanningSlotEmployee` (Tabelle `planning_slot_employees`, je Einsatz eine Person einmal, `PlanningSlot.besetzung`); `PlanningSlot.team_assignment_id`
  darf leer sein (= ohne Kolonne). Migration `e4b1c9d27a35`.
- `app/planning.py`: `create_slot(team_id, employee_ids)` -- mit Kolonne und ohne `employee_ids` schlägt die Kolonne ihre heutigen aktiven Mitglieder vor
  (`_kolonne_schlaegt_vor()`, Stammdaten); mit `employee_ids` genau diese (`_besetzung_pruefen()`: bekannt, aktiv, jede einmal); ohne Kolonne mindestens eine
  Person (`BesetzungUngueltig`, 422). Die Kolonnen-Zuweisung an der AV (`ensure_team_assignment()`) entsteht mit Kolonne weiter wie bisher -- die AV-Seite und
  der Zugriff lesen sie. `update_slot()`: `team_id` null = ohne Kolonne (die Personen bleiben), eine andere Kolonne setzt deren Mitglieder (auch beim Ziehen in
  ihre Zeile), `employee_ids` setzt genau; wer bleibt, behält seinen Platz (`_besetzung_setzen()`); eine geänderte Besetzung fragt wie Kolonne und Zeitraum zurück.
- Leser auf der Besetzung: `_besetzung()` (Kapazität, Verteilung), `_slot_members()` und `_conflicts()` (Person doppelt, abwesend, Freistellung, Antrag offen),
  `slot_to_dict()` (`employees`: Name live, Rolle aus der Kolonne, falls die Person dort steht), `_employee_assignment_slot_condition()` („Heute“ und
  „Nächste Tage“: nur noch die Besetzung), `app/orders.py::_assigned_order_id_queries()` (Zugriff der Monteurin: dazu die Besetzung eines Einsatzes des
  Auftrags), `app/akte.py::einsaetze()` (Kolonne oder „Ohne Kolonne“, Personen = Besetzung), Änderungsprotokoll (je Person „Plantafel-Besetzung“, Kennung =
  Einsatz; im Verlauf der Akte als „Termin“; ein Einsatz ohne Kolonne heißt „Ohne Kolonne · …“).
- Geräte bleiben bis 1.9.234 an der Kolonnen-Zuweisung (ohne Kolonne: keine).
- Oberfläche (bedienbar wie bisher): eine Kolonne wählen setzt ihre Mitglieder; Einsätze ohne Kolonne stehen in „Kolonnen“ in der Zeile „Ohne Kolonne“ und
  in „Mitarbeiter“ bei jeder Person; der Dialog „Einsatz bearbeiten“ bietet „ohne Kolonne – die Personen bleiben“. Personen einzeln wählen kommt mit R4 (heute
  über die Schnittstelle).

### Festlegungen 1.9.233 (bestätigt am 06.11.2026)

1. Die Besetzung am Einsatz ist die eine Quelle für Tafel, Kapazität, Konflikte und die Einsätze der Monteurin („Heute“, „Nächste Tage“).
2. Die Kolonne schlägt ihre heutigen aktiven Mitglieder aus den Stammdaten vor -- beim Anlegen und beim Wechsel der Kolonne (auch Ziehen in ihre Zeile),
   nicht mehr den Schnappschuss an der AV (B1: eine neue Kollegin kommt in den nächsten Einsatz).
3. Eine spätere Änderung der Kolonne ändert keinen bestehenden Einsatz.
4. `employee_ids` setzt die Besetzung genau so, auch mit Personen anderer Kolonnen; unbekannt oder inaktiv 422; doppelt genannt zählt einmal.
5. Ohne Kolonne: mindestens eine Person (422); beim Wechsel auf „ohne Kolonne“ bleiben die Personen; ein Einsatz ohne Kolonne legt keine Kolonnen-Zuweisung an
   der AV an. Mit Kolonne darf die Besetzung leer sein (wie bisher eine Kolonne ohne aktive Mitglieder).
6. Die Migration übernimmt je Einsatz den Schnappschuss seiner Kolonne und danach die Einzelzuweisungen seiner AV (sie sahen den Einsatz bis 1.9.232 auf
   „Heute“, B5) -- über die Vorgabe „aus der Kolonnen-Zuweisung“ hinaus, damit niemand einen Einsatz verliert, den er heute sieht, und „Person doppelt“ auch
   die einzeln Zugeordneten findet (B6). Danach ist eine neue Einzelzuweisung an der AV eine Zuweisung ohne Datum: Zugriff auf den Auftrag, kein Einsatz.
7. Zugriff der Monteurin auf den Auftrag: dazu die Besetzung eines Einsatzes; die Kolonnen-Zuweisung an der AV und die Einzelzuweisung bleiben Wege (B7/B8
   bleibt, wie es ist).
8. Eine geänderte Besetzung fragt beim Speichern zurück wie Kolonne und Zeitraum.
9. Reihenfolge der Besetzung: wer bleibt, behält seinen Platz, neue Personen kommen dahinter.
10. Das Änderungsprotokoll führt jede Person der Besetzung („Plantafel-Besetzung“, im Verlauf der Akte unter „Termin“); ein Einsatz ohne Kolonne heißt dort
    „Ohne Kolonne · …“.
11. downgrade() der Migration bricht ab, solange ein Einsatz ohne Kolonne besteht.

### Tests und Prüfung 1.9.233

Neu: `tests/test_v633_besetzung_je_einsatz.py` (Vorschlag der Kolonne, B1, gewählte Personen, unbekannt/inaktiv, ohne Kolonne, Wechsel, Rückfrage, Person
doppelt ohne Kolonne, Kapazität, Tafel und Dialog, „Heute“/„Nächste Tage“/Zugriff, neue Einzelzuweisung ohne Einsatz, Akte, Änderungsprotokoll, Schema,
Migration auf einem Bestand unter SQLite und PostgreSQL). Testhelfer `tests/besetzung.py::wie_migration()`: ein direkt angelegter Einsatz bekommt die
Besetzung wie nach der Migration. Gegenproben: Archiv `gegenproben-stufe6-r3a.md` (32 rot, eine erst grün -> Test ergänzt).

Angepasste Erwartungen (Regel 28) -- nur Aufbau: die Tests legen Einsätze direkt an wie ein Bestand von vor 1.9.233 und rufen danach
`wie_migration()` bzw. `alle_wie_migration()` (sonst hätten die Einsätze keine Personen): `test_v224` (`make_slot_for_team`, `make_slot_for_individual`),
`test_v260` (Einsatz für den Monteur), `test_v262`, `test_v263`, `test_v264`, `test_v265` (je der Helfer des Einsatzes), `test_v326` (Welt der
Datengrenze), `test_v346` (Hinweis je Einsatz), `test_v471` (Einsätze für „Heute“), `test_v545` (Phase Ausführung). Die Erwartungen dieser Tests bleiben.
- Klicktests, nur Aufbau: die Testdaten von `klicktest_bedenkenanzeige`, `_bericht_ohne_einsatz`, `_bericht_schritte`, `_heute`,
  `_zeiten_abgeschlossen`, `_beleg_und_hinweis`, `_meine_zeiten`, `_meine_zeiten_angeheftet`, `_meine_zeiten_freistellungen`, `_monteurin_regeln` und
  `scripts/bildgrundlage.py` legen Einsätze direkt an; danach ruft jede `besetzung_wie_migration()` (neu in `scripts/cdp_klicktest.py`, dieselbe Regel wie
  die Migration). Ohne sie hatten die Einsätze keine Personen, sechs Klicktests waren im ersten Gesamtlauf rot (fünf davon aus diesem Grund).

### Umsetzung 1.9.234: Geräte je Einsatz, alle oder einzelne Tage (Punkt 3)

- Modell: `PlanningSlotResource` (Tabelle `planning_slot_resources`: Einsatz, Gerät = `OperationalResource`, `tage` als JSON-Liste einzelner Tage, leer = alle
  Tage; je Einsatz ein Gerät einmal; `PlanningSlot.geraete`). Migration `f2c8d4a61e93`.
- `app/planning.py`: ohne `geraete` schlägt die Kolonne ihre aktiven Geräte vor (`_kolonne_schlaegt_geraete_vor()`, jede Rolle, alle Tage), ohne Kolonne
  keine; mit `geraete` genau diese (`_geraete_pruefen()`: bekannt, aktiv, Tage im Einsatz, keine leere Liste -- `GeraeteUngueltig`, 422). Beim Ändern setzt eine
  andere Kolonne ohne `geraete` ihre Geräte, „ohne Kolonne“ lässt sie; ein neuer Zeitraum nimmt einzelne Tage mit (`_tage_mitnehmen()`: gleiche Dauer =
  verschoben, sonst nur die Tage im neuen Zeitraum, ein Gerät ohne Tag fällt weg). Geänderte Geräte fragen zurück wie Besetzung, Kolonne und Zeitraum.
- Leser: „Gerät doppelt“ nur, wenn sich die Tage des Geräts in beiden Einsätzen treffen (`_geraet_tage()`); Termine im Kalender eines Geräts
  (`termine_der_geraete()`) nur an seinen Tagen (an Arbeitstagen, wie bisher); Belegung der Tafel (`resource_load`) nur an seinen Tagen; `slot_to_dict()`
  `resources` mit Name live, Rolle aus der Kolonne und `tage`. Ein Gerät an einem Einsatz wird nicht gelöscht, sondern abgeschaltet
  (`resource_planning.py::delete_resource()`). Änderungsprotokoll: „Plantafel-Gerät“ (Kennung = Einsatz, Feld „Tage“), im Verlauf der Akte unter „Termin“.
- Oberfläche: eine Kolonne wählen setzt auch ihre Geräte; die Ansicht „Fahrzeuge / Maschinen“ liest die Geräte des Einsatzes. Geräte und Tage wählen kommt
  mit R4 (heute über die Schnittstelle).

### Festlegungen 1.9.234 (bestätigt am 06.11.2026)

1. Die Kolonne schlägt ihre aktiven Geräte jeder Rolle vor (auch „bei Bedarf“), für alle Tage -- wie bis 1.9.233 der Schnappschuss; ohne Kolonne keine.
2. `geraete` setzt die Geräte genau so; unbekannt oder inaktiv, ein Tag außerhalb des Einsatzes oder eine leere Tagesliste 422; doppelt genannt zählt das erste.
3. Wechsel der Kolonne ohne `geraete` setzt deren Geräte; „ohne Kolonne“ lässt die Geräte.
4. Neuer Zeitraum: bei gleicher Dauer wandern einzelne Tage mit; sonst bleiben nur die Tage im neuen Zeitraum, ein Gerät ohne verbleibenden Tag fällt weg.
5. „Gerät doppelt“ nur, wenn sich die Tage treffen; der Kalender des Geräts zählt nur an seinen Tagen; die Tafel belegt das Gerät nur an seinen Tagen.
6. Geänderte Geräte fragen beim Speichern zurück.
7. Ein Gerät, das an einem Einsatz steht, wird beim Löschen nur abgeschaltet (wie mit Kolonne oder Kalender).
8. Die Migration übernimmt je Einsatz die Geräte seines Kolonnen-Schnappschusses für alle Tage; downgrade() verwirft die Geräte je Einsatz.

### Tests und Prüfung 1.9.234

Neu: `tests/test_v634_geraete_je_einsatz.py` (Vorschlag der Kolonne, ohne Kolonne, einzelne Tage, ungültige Geräte, Wechsel, Tage beim Verschieben,
Gerät doppelt nach Tagen, Kalender des Geräts nach Tagen, Belegung der Tafel, Löschschutz, Änderungsprotokoll, Migration auf einem Bestand unter SQLite und
PostgreSQL). `tests/besetzung.py::wie_migration()` und `scripts/cdp_klicktest.py::besetzung_wie_migration()` übernehmen dazu die Geräte des Schnappschusses
(wie die Migration). Gegenproben: Archiv `gegenproben-stufe6-r3a.md` (21, alle rot; eine erst aus dem falschen Grund).
Angepasste Erwartungen: keine (die neue Feldbeschriftung „Tage“ in `app/audit.py::FIELD_LABELS` verlangen `test_v436`/`test_v438` ohnehin).

### Umsetzung 1.9.235: Status vorläufig | fest (Punkt 4)

- `app/planning.py::EINSATZ_STATUS` (`vorlaeufig` -> „vorläufig“, `fest` -> „fest“): `create_slot()` (Vorgabe vorläufig) und `update_slot()` nehmen nur diese
  zwei (`ValueError`), die Schemas als `Literal` (422); `slot_to_dict()` dazu `status_label`. Modell-Vorgabe `vorlaeufig`.
- Migration `a7d3e5f9c214`: „geplant“ -> vorläufig, jeder andere Wert (auch leer, Freitext) -> fest; downgrade() vorläufig -> geplant, fest -> bestaetigt.
- Oberfläche: „Einsatz planen“ und „Einsatz bearbeiten“ bieten „vorläufig“ und „fest“ (neu vorläufig). Gestrichelt auf der Tafel und die Anzeige auf
  „Heute“ kommen mit R4 und R3b. Abgeschlossen und storniert kommen vom Auftrag. Im Verlauf heißen die Werte „Vorläufig“/„Fest“; die Prüfabfrage
  `scripts/pruefabfrage_auswahlwerte.sql` kennt die zwei.

### Festlegungen 1.9.235 (bestätigt am 06.11.2026)

1. Ein Einsatz ist „vorläufig“ oder „fest“, neu angelegt vorläufig; jeder andere Wert 422.
2. Die Migration macht „geplant“ zu vorläufig und jeden anderen Wert (auch leer oder Freitext) zu fest; downgrade() macht vorläufig zu „geplant“ und fest zu
   „bestaetigt“, frühere andere Werte kommen nicht zurück (sie hatten keine Wirkung).
3. Der Status hat in R3a keine Wirkung auf Konflikte und Kapazität: ein vorläufiger Einsatz zählt wie ein fester. -- Gilt auch künftig (Vorgabe
   Tobias, 06.11.2026).

### Tests und Prüfung 1.9.235

Neu: `tests/test_v635_einsatz_status.py` (Vorgabe vorläufig, fest, sechs andere Werte 422 beim Anlegen und Ändern, Geschäftsfunktionen prüfen selbst,
vorläufig zählt wie fest, Dialog und Verlauf, Migration auf einem Bestand unter SQLite und PostgreSQL; seit den Gegenproben dazu Schema und Vorgabe
für sich). Gegenproben: Archiv `gegenproben-stufe6-r3a.md` (14 rot, drei erst grün -> Tests ergänzt).

Angepasste Erwartungen (Regel 28):
- `test_v090::test_planning_slot_updates_work_preparation_dates_and_can_switch_team`: Aufbau `status="fest"` statt „bestaetigt“.
- `test_v399_teil_updates_rest::test_plantafel_verschieben_schickt_nur_team_und_zeitraum`: Status „fest“ statt „bestaetigt“ (gesendet und erwartet).
- `test_v563::test_nur_notiz_aendern_fragt_nicht_nach_und_nennt_die_konflikte`: geändert wird `{"status": "fest"}` statt „bestaetigt“.
- `test_v364`: `planning_slots.status` von `FESTE_LITERALE` („geplant“, sonst vom Client) nach `FESTE_WERTE` (`app.planning.EINSATZ_STATUS`).
- `scripts/pruefabfrage_auswahlwerte.sql` (von `test_v447` gegen die Seite geprüft): `planning_slots.status IN ('vorlaeufig', 'fest')` statt der fünf alten Werte.

### Umsetzung 1.9.236: Konflikte auf dem neuen Modell (Punkt 5)

- `WARNUNG_ARTEN` = Person doppelt, Gerät doppelt, Person abwesend, neu **Gerät mit abgelaufener Prüffrist** (`pruefung`); „Kolonne doppelt“ (`team`)
  entfällt -- zwei Einsätze derselben Kolonne melden ihre gemeinsamen Personen, ohne gemeinsame Person nichts. `HINWEIS_ARTEN` unverändert (Antrag offen,
  Feiertag oder betriebsfreier Tag, Freistellung des Arbeitszeitkalenders, Kapazität).
- Prüffrist (`_pruefungen()`, eine Abfrage für alle Geräte der Einsätze): je Gerät die Prüfungen seines Betriebsmittels (`OperationalAsset.resource_id`,
  `OperationalAssetInspection.next_due_date`); ist an einem Arbeitstag des Geräts am Einsatz (hat es keinen, an einem seiner Tage) die Fälligkeit schon
  vorbei (fällig vor dem Tag), eine Warnung „Kran · UVV fällig am 03.11.2026“ mit dem ersten solchen Tag. Nur bei eingeschalteter Betriebsmittelverwaltung.
- Person doppelt aus der Besetzung (seit 1.9.233) -- damit auch einzeln Zugeordnete, aus dem Bestand übernommene Einzelzuweisungen (B5/B6) eingeschlossen;
  Gerät doppelt aus den Geräten an ihren Tagen und den Terminen im Kalender des Geräts (seit 1.9.234); Kapazität aus der Sollzeit der Besetzung an den
  Arbeitstagen minus Anfahrt (seit 1.9.211/1.9.233).
- Tafel: „Prüffrist abgelaufen: …“ in der Liste des Einsatzes und der Rückfrage; „Kolonne doppelt“ steht dort nicht mehr.

### Festlegungen 1.9.236 (bestätigt am 06.11.2026)

1. „Kolonne doppelt“ ist kein Konflikt mehr; es zählen die Personen.
2. Gerät mit abgelaufener Prüffrist ist eine Warnung, sobald an einem Arbeitstag des Geräts am Einsatz die Fälligkeit vorbei ist (der Fälligkeitstag selbst
   gilt noch, wie `is_inspection_overdue()`); eine Warnung je Gerät und Prüfung, mit dem ersten solchen Tag.
3. Ohne Fälligkeit oder ohne Betriebsmittel am Gerät keine Warnung; bei ausgeschalteter Betriebsmittelverwaltung auch keine.
4. Ein Gerät, das nur an einzelnen Tagen am Einsatz ist, wird nur an diesen Tagen geprüft.

### Tests und Prüfung 1.9.236

Neu: `tests/test_v636_konflikte_neues_modell.py` (Arten, Prüffrist als Warnung mit erstem Tag und trotzdem planbar, nur an den Tagen des Geräts, nur mit
Betriebsmittelverwaltung, ohne Fälligkeit nichts, Einzelzuweisung aus dem Bestand als Person doppelt, Kapazität mit Anfahrt, dieselbe Kolonne ohne gemeinsame
Person). Gegenproben: Archiv `gegenproben-stufe6-r3a.md`.

Angepasste Erwartungen (Regel 28):
- `test_v563::test_kolonne_doppelt` heißt `test_kolonne_doppelt_meldet_die_personen`; alt „team“ in den Warnungen; neu genau „employee“, und ohne gemeinsame
  Person 200 ohne Konflikt.
- `test_v563::test_verschieben_auf_eine_belegte_kolonne_fragt_nach_und_laesst_alles_stehen`: alt „team“ in den Warnungen, neu „employee“.
- `test_v564::test_konflikt_ueber_den_rand_des_zeitraums_bleibt`: alt ("team", Einsatz), neu ("employee", Einsatz).
- `test_v090::test_same_team_overlap_is_conflict_and_unplanned_backlog_disappears_after_planning`: alt ein Konflikt „team“, neu „employee“.
- `test_v563_konflikte_pg::test_pg_warnung_laesst_nichts_zurueck_und_trotzdem_planen_speichert`: alt „team“ in den Warnungen, neu „employee“; die
  Kolonne A der PostgreSQL-Fassung bekommt dafür eine Person (Aufbau), `test_pg_verschieben_mit_warnung_gibt_die_sperre_frei` erwartet weiter 409.

### Umsetzung 1.9.237: die heutige Oberfläche bleibt bedienbar (Punkt 6)

Mit 1.9.233–1.9.236 lief die Oberfläche auf dem neuen Modell mit: eine Kolonne wählen (Anlegen, Bearbeiten, Ziehen in ihre Zeile) setzt ihre Mitglieder und
Geräte, Einsätze ohne Kolonne stehen in der Zeile „Ohne Kolonne“, „Mitarbeiter“ liest die Besetzung, „Fahrzeuge / Maschinen“ die Geräte an ihren Tagen,
der Status heißt „vorläufig“/„fest“, die Rückfrage nennt „Prüffrist abgelaufen“. Dazu jetzt:

- „Einsatz bearbeiten“ nennt unter der Kolonne die Besetzung und die Geräte des Einsatzes (`besetzungText()`, einzelne Tage in Klammern) und sagt, dass
  eine andere Kolonne ihre Mitglieder und Geräte setzt -- die Besetzung kann seit 1.9.233 von der Kolonne abweichen. Nur lesend; Personen und Geräte
  einzeln wählen kommt mit R4.
- Klicktest `scripts/klicktest_plantafel_besetzung.py`: Neu mit Nord, Ansichten Kolonnen/Mitarbeiter/Fahrzeuge, Dialog, Wechsel auf Süd mit Rückfrage
  „Prüffrist abgelaufen“, „ohne Kolonne“ (fragt wie jeder Wechsel der Kolonne), Ziehen nach Nord, Status fest.

Unverändert bis R4 (bewusst): die Legende der Tafel („geplant · Konflikt · …“ meint einen eingeplanten Balken, nicht den Status), keine Strichelung für
vorläufig, Kapazität je Tag und Kolonne in den Zellen, Ziehen nur in „Kolonnen“ und mit der Maus.

### Festlegungen 1.9.237 (bestätigt am 06.11.2026)

1. „Einsatz bearbeiten“ zeigt die Besetzung und die Geräte des Einsatzes lesend unter der Kolonne; ändern über die Kolonne (oder die Schnittstelle).
2. Auch der Wechsel auf „ohne Kolonne“ fragt bei Warnungen zurück wie jeder Wechsel der Kolonne.

### Tests und Prüfung 1.9.237

Neu: `tests/test_v637_plantafel_bedienbar.py` (Text der Besetzung im Dialog in node, Dialog füllt die Zeile beim Öffnen, der Klicktest deckt die Abläufe,
„ohne Kolonne“ fragt bei Warnungen zurück) und `scripts/klicktest_plantafel_besetzung.py` (17 Prüfungen). Gegenproben: Archiv `gegenproben-stufe6-r3a.md`.
Angepasste Erwartungen (Regel 28): `test_v447::test_plantafel_status` nur Aufbau -- die Attrappe des Einsatzes bekommt `employees` und `resources`
(leer), wie jede Antwort des Servers (`slot_to_dict`); ohne sie warf der neue `besetzungText()` beim Öffnen des Dialogs (Regel 36). Erwartung bleibt.

## Stufe 6, R3b: Kran und „Heute“ (ab 1.9.240)

Vorgabe Tobias (06.11.2026), Start bcfd155. Zeichnung `bildgrundlage/entwurf-stufe6/` (`plantafel-regeln.html`: „Kranvermietung“, „Kran-Kalender“;
`heute-einsatz.html`). Bestätigt vor der Runde: alle Festlegungen 1.9.230–1.9.237; 1.9.235 Nr. 3 gilt auch künftig (vorläufig zählt wie fest). Vorweg
(0a–0c) im Archiv „Buchhaltung“ und „Zeiterfassung“.

### Befund (Punkt 1): Schnellauftrag, Kran und Kran-Postfach (Stand bcfd155)

- **Schnellauftrag** (`app/quick_service_orders.py`, `POST /api/quick-service-orders`, nur mit Modul „Wartungen“, ab Büro – Auftrag): Kunde, Objekt (ein
  fremdes nur mit Bestätigung), Art Reparatur/Wartung, Bezeichnung. Normale Kette Projekt -> Angebot (eine Position „<Art> nach Aufwand“, 1 pauschal,
  0,00 €) -> Auftrag (läuft, ohne Vertragsentwurf); abgerechnet über „Rechnung aus Aufwand“ (Auftrag nach Aufwand). Er committet unterwegs dreimal
  (Position, Struktur des Angebots, Auftrag) -- seit 1.9.245 einmal am Ende (Stufe 6, R4, Punkt 0c, Archiv `redesign.md`).
- **Kran (Gerät)**: `OperationalResource`, seit 1.9.234 je Einsatz mit Tagen (`PlanningSlotResource`). Es gibt kein Merkmal „Kran“: ein Gerät mit
  eigenem Postfach (`outlook_mailbox`, seit 1.9.161) hat einen Kalender. Prüffrist über das Betriebsmittel (seit 1.9.236).
- **Kran-Postfach**: Termine am Gerät sind `CalendarEvent` mit `resource_id`; Abgleich nur per Cron (Festlegung 1.9.161 Nr. 1), beide Richtungen, „letzte
  Änderung gewinnt“; was im ERP entsteht, geht sofort hinaus. Ein Termin am Gerät warnt beim Speichern eines Einsatzes als „Gerät doppelt“. Am echten
  Mandanten nicht eingerichtet -- getestet gegen die Graph-Attrappe.
- **Zusammenhang heute: keiner.** Einsätze stehen nicht im Kran-Kalender, ein Termin am Kran wird kein Einsatz, ein Schnellauftrag hat keinen Einsatz.

Kein Widerspruch zur Zeichnung. Verschieden formuliert: (a) „Tom hat Urlaub“ in der Zeichnung, Vorgabe Tobias „ist nicht da“, nie die Art -- gebaut
wird die Vorgabe; (b) ob eine Kranvermietung eine Kolonne haben kann, sagt die Zeichnung nicht -- gebaut: ohne Kolonne, Bediener einzeln.

### Umsetzung 1.9.240: Kranvermietung als Art des Einsatzes (Punkt 2)

`PlanningSlot.art` (Migration `b5f1c7e2a948`, NOT NULL, `server_default` „baustelle“), `app/planning.py::EINSATZ_ARTEN`. `create_slot(art=…)`:
- „baustelle“ wie bisher an einem Auftrag (`order_id`); Kunde, Objekt und Titel gehören nur zur Kranvermietung (422).
- „kranvermietung“ an einem bestehenden Auftrag (`order_id`) oder mit Kunde (`customer_id`, wahlweise `property_id` mit `confirm_property_customer`,
  `titel`): `app/quick_service_orders.py::auftrag_nach_aufwand(commit=False)` legt Projekt, Angebot mit der Position „Kranvermietung nach Aufwand“ (1
  pauschal, 0,00 €) und Auftrag an (Titel wahlweise, sonst „Kranvermietung“; Ausführungsbeginn = erster Tag) -- derselbe Weg wie der Schnellauftrag
  (`create_quick_service_order()` nimmt ihn jetzt auch), aber ohne Commit: `create_free_quote_item()`, `ensure_quote_structure()` und
  `create_order_from_quote()` haben dafür `commit=False`. Fragt das Speichern zurück (`PlanungsWarnung`, rollback), bleibt nichts zurück.
- Eine Kranvermietung hat keine Kolonne (422 beim Anlegen und Ändern), mindestens ein Gerät (422, auch wenn beim Kürzen des Zeitraums das letzte Gerät
  wegfiele) und Bediener als Besetzung, auch keine. Nicht an das Modul „Wartungen“ gebunden (die Plantafel ist Kern).
- Die Art steht in `slot_to_dict()` (`art`, `art_label`) und bleibt, wie sie angelegt wurde (kein Feld zum Ändern).
- `create_slot()` und `update_slot()` nehmen bei einer Ablehnung (`ValueError`) alles in der Sitzung zurück (bis 1.9.239 blieb eine halbe Änderung bis
  zum Schließen der Sitzung stehen -- im Betrieb schließt jede Anfrage ihre Sitzung, in Tests mit geteilter Sitzung lief sie in die nächste Anfrage).
- Router: Objekt eines anderen Kunden ohne Bestätigung 409, unbekannter Kunde oder unbekanntes Objekt 404 (Regel 25: `customer_id` als FREI,
  `property_id` als GEPRUEFT in `tests/test_v373_zugehoerigkeit_struktur.py`).

Die Oberfläche bleibt in R3b, wie sie ist: eine Kranvermietung steht auf der Tafel in der Zeile „Ohne Kolonne“, in der Zeile des Geräts und bei jedem
Bediener; anlegen nur über die Schnittstelle (`POST /api/planning/slots` mit `art`), die Knöpfe kommen mit R4.

### Festlegungen 1.9.240 (Bitte bestätigen)

1. Ein Einsatz ist „Baustelle“ oder „Kranvermietung“; ohne Angabe Baustelle; jeder andere Wert 422; die Art bleibt, wie sie angelegt wurde.
2. Kranvermietung mit Kunde: Projekt, Angebot und Auftrag wie der Schnellauftrag, Position „Kranvermietung nach Aufwand“ (1 pauschal, 0,00 €), Titel
   wahlweise, sonst „Kranvermietung“, Ausführungsbeginn der erste Tag; ein fremdes Objekt nur mit Bestätigung (409), unbekannter Kunde 404.
3. Das geschieht in der Transaktion des Einsatzes: eine Warnung oder Ablehnung lässt nichts zurück (kein Projekt, keine Nummer verbraucht).
4. Oder an einem bestehenden Auftrag; Auftrag und Kunde zugleich oder keins von beiden 422.
5. Eine Kranvermietung hat keine Kolonne, mindestens ein Gerät, Bediener als Besetzung -- auch keine.
6. Ein Einsatz auf der Baustelle braucht einen Auftrag; Kunde, Objekt und Titel gehören nur zur Kranvermietung.
7. Abgerechnet wie jeder Auftrag nach Aufwand; die Plantafel schreibt keine Beträge.
8. Wird das Anlegen oder Ändern eines Einsatzes abgelehnt, nimmt die Sitzung alles zurück.
9. Die Kranvermietung hängt nicht am Modul „Wartungen“.
10. Migration: jeder bestehende Einsatz ist „baustelle“; downgrade() lässt die Spalte fallen (eine Kranvermietung bleibt als Einsatz ohne Art).

### Tests und Prüfung 1.9.240

Neu: `tests/test_v640_kranvermietung.py` (mit Kunde, mit Titel und Bediener, an einem Auftrag, Warnung lässt nichts zurück, Regeln 422 über Schnittstelle,
Schema für sich und Geschäftsfunktion, fremdes Objekt und unbekannter Kunde, Ändern, Baustelle ohne Kolonne braucht weiter eine Person, Ablehnung lässt
nichts zurück, ohne Modul „Wartungen“, Migration unter SQLite und PostgreSQL). Gegenproben: Archiv `gegenproben-stufe6-r3b.md`.

Angepasster Aufbau (Regel 28): `tests/test_v373_zugehoerigkeit_struktur.py` -- neu eingeordnet `POST /api/planning/slots customer_id` (FREI) und
`property_id` (GEPRUEFT); der Eintrag `POST /api/planning/slots order_id` nennt `planning._create_slot` statt `planning.create_slot` (die Regeln stehen
seit 1.9.240 dort, `create_slot()` nimmt bei einer Ablehnung zurück). Erwartungen bleiben.
Dazu `tests/test_v364_feste_werte_spaltenlaenge.py`: `planning_slots.art` neu im Katalog (`EINSATZ_ARTEN`). Gefunden im Lauf der vollen Suite: die neue
Spalte hatte im Änderungsprotokoll keinen Namen (`test_v436`, `test_v438` rot) -- jetzt „Art des Einsatzes“, Werte „Baustelle“/„Kranvermietung“
(`app/audit.py`, `app/verlauf_namen.py`).

Nach der Gegenprobe `240_5b` (erst grün) verlangt `test_v640::test_aendern_einer_kranvermietung` zusätzlich: Kolonne setzen mit dem Kran in derselben
Anfrage -> 422 „keine Kolonne“ (ohne Gerät in der Anfrage lehnte die Prüfung „mindestens ein Gerät“ ab, die Kolonne-Prüfung blieb ungesehen).

### Umsetzung 1.9.241: Plantafel -> Kran-Kalender (Punkt 3)

Vorgabe (Zeichnung „Kran-Kalender“): Einsätze mit dem Kran (Baustelle und Vermietung) erscheinen an ihren Tagen im Kran-Postfach, für sie ist die
Plantafel führend, Änderungen in Outlook überschreibt der nächste Abgleich; Termine, die direkt in Outlook entstehen, bleiben Termine am Kran (1.9.161)
und lassen sich als Kranvermietung übernehmen (Schnittstelle, Knopf mit R4). Das Kran-Postfach ist noch nicht eingerichtet: gebaut und geprüft gegen die
Graph-Attrappe (`tests/outlook_attrappe.py`).

`app/kran_kalender.py`, `calendar_events.planning_slot_id` (Migration `c9d2e6a3f417`, Fremdschlüssel mit ON DELETE SET NULL, Index):
- `soll()`: je Gerät des Einsatzes mit Postfach (aktiv) und je Folge zusammenhängender Tage des Geräts (alle Tage des Zeitraums oder seine einzelnen Tage)
  ein ganztägiger Termin; Besitzer das Gerät, Herkunft „erp“; Titel „<Auftrag> · <Projekt>“ bzw. „Kranvermietung · <Kunde>“, „vorläufig:“ davor; Ort die
  Adresse; Text: Hinweis „Aus der Plantafel – bitte dort ändern …“, Besetzung bzw. Bediener, Notiz. Ein Einsatz eines abgeschlossenen oder stornierten
  Auftrags hat keine.
- `abgleichen()` (ohne Commit) aus `create_slot()`/`update_slot()` vor dem Commit, `entfernen()` aus `delete_slot()`, `auftrag_abgleichen()` aus dem
  Statuswechsel (`app/auftragsstatus.py::_wechsel_schreiben()`); was stimmt, bleibt; ein Termin desselben Geräts wandert auf neue Tage, statt gelöscht und neu
  angelegt zu werden; was übrig ist, fällt weg (Löschauftrag, wenn er in Outlook liegt). `senden()` nach dem Commit: `push_event_best_effort()` und die
  Löschaufträge -- wie jeder Termin des ERP; was scheitert, holt der nächste Lauf nach.
- `nachziehen()` vor dem Abgleich eines Geräte-Postfachs (`app/outlook_calendar_sync.py::_postfach_abgleichen()`): die Termine jedes Einsatzes mit diesem
  Gerät, der heute oder später endet.
- Abgleich, Plantafel führend (`_apply_delta_change()`, `_weggefallene_entfernen()`): eine Änderung aus Outlook wird nicht übernommen, der Termin gilt als
  „nicht übertragen“ und die Push-Phase desselben Laufs überschreibt sie; gelöscht (auch beim Abruf des ganzen Kalenders mit 404) oder zur Serie gemacht ->
  er verliert seine Kennung und geht als neuer hinaus. Zähler `plantafel`.
- `termine_der_geraete()` übergeht die Termine der Einsätze (keine Belegung gegen sich selbst); ein Termin direkt in Outlook warnt weiter als „Gerät doppelt“.
- Büro-Kalender: `PUT`/`DELETE /api/calendar-events/{id}` an einem Termin der Plantafel 409 („bitte dort ändern oder löschen“).
- Übernehmen: `app/planning.py::kran_termin_uebernehmen()`, `POST /api/planning/kran-termine/{event_id}/kranvermietung` (Schema `KranTerminUebernahme`: Auftrag
  oder Kunde wie beim Anlegen, Bediener, Status, Notiz, Stunden, `trotzdem_planen`). Nur ein Termin am Gerät, nicht schon übernommen (409), unbekannt 404.
  Zeitraum vom Termin (ganztägig erster bis letzter Tag, sonst Tag des Beginns bis zum Tag vor einem Ende um Mitternacht), das Gerät für alle Tage, ohne
  Notiz der Titel des Termins (außer privat). Der Termin wird vor der Prüfung der Warnungen der Termin des Einsatzes (sonst warnte er gegen sich selbst),
  Herkunft „erp“; der nächste Abgleich überschreibt ihn in Outlook mit dem Stand der Plantafel. Eine Warnung lässt nichts zurück.

### Festlegungen 1.9.241 (Bitte bestätigen)

1. Ein Einsatz mit einem aktiven Gerät mit Postfach steht im Kalender dieses Geräts: je Folge zusammenhängender Tage des Geräts ein ganztägiger Termin
   (ein Gerät für alle Tage: der ganze Zeitraum, auch das Wochenende darin).
2. Besitzer das Gerät, Herkunft „erp“; Titel „<Auftrag> · <Projekt>“ bzw. „Kranvermietung · <Kunde>“, „vorläufig:“ davor; Ort die Adresse; Text Hinweis,
   Besetzung bzw. Bediener, Notiz.
3. Anlegen, Ändern und Löschen gleichen im selben Commit ab und senden sofort; Ändern verschiebt denselben Termin, Löschen geht über einen Löschauftrag.
4. Ein abgeschlossener oder stornierter Auftrag hat keine Termine im Kalender des Geräts; der Statuswechsel nimmt sie heraus und legt sie wieder an.
5. Plantafel führend: eine Änderung in Outlook überschreibt der nächste Abgleich; gelöscht oder zur Serie gemacht, legt er den Termin neu an.
6. Der Büro-Kalender ändert und löscht einen Termin der Plantafel nicht (409).
7. Ein Termin der Plantafel ist keine Belegung gegen Einsätze; ein Termin direkt in Outlook bleibt eine (wie 1.9.161).
8. Übernehmen: nur ein Termin am Gerät, nicht schon übernommen (409), unbekannt 404; Kranvermietung mit dem Gerät an den Tagen des Termins (bis zum Tag vor
   einem Ende um Mitternacht); der Termin wird ihr Termin; Notiz der Titel, außer privat; eine Warnung lässt nichts zurück.
9. Der Abgleich eines Geräte-Postfachs zieht die Termine jedes Einsatzes nach, der heute oder später endet; ein vergangener bekommt keinen.
10. Ein Gerät, das nach der Planung inaktiv wird oder sein Postfach verliert: sein Termin fällt beim nächsten Speichern des Einsatzes weg.
11. Migration `c9d2e6a3f417`: bestehende Termine bleiben ohne Einsatz; downgrade() löscht die Termine der Einsätze im ERP (in Outlook bleiben sie).

### Tests und Prüfung 1.9.241

Neu: `tests/test_v641_kran_kalender.py` (Folgen von Tagen, Termin und Push, einzelne Tage, ohne Postfach und inaktiv, Verschieben, Löschen, Storno und
zurück, Kranvermietung mit Bediener, in Outlook geändert und gelöscht, ganzer Kalender ohne den Termin, Büro-Kalender 409, eigener und fremder Termin,
Übernehmen mit Ablehnungen und bis Mitternacht, Nachziehen, Migration unter SQLite und PostgreSQL) -- gegen die Graph-Attrappe aus `test_v579`.
Gegenproben: Archiv `gegenproben-stufe6-r3b.md` (`241_7c` blieb zuerst grün: der zweite Übernahmeversuch scheiterte an der Warnung „Gerät
doppelt“ -- der Test versucht es jetzt mit „trotzdem planen“ und prüft die Meldung).

Angepasster Aufbau (Regel 28): `tests/test_v373_zugehoerigkeit_struktur.py` -- neu eingeordnet `POST /api/planning/kran-termine/{event_id}/kranvermietung`
mit `order_id` (FREI, `planning._create_slot`), `customer_id` (FREI, `zugehoerigkeit.require_customer`) und `property_id` (GEPRUEFT). Dazu im Änderungsprotokoll
der Name der neuen Spalte („Einsatz der Plantafel“, `app/audit.py`). Erwartungen bleiben.

## Stufe 6, R5: Plantafel nach Aufträgen -- Befund (08.11.2026, nur gelesen)

Vorgabe Tobias (07.11.2026): `bildgrundlage/entwurf-stufe6/plantafel-auftraege.html` und `plantafel-auftraege-regeln.html` (freigegeben). Vorhaben: 1 Fundament
„Besetzung je Tag“ wie die Tage der Geräte, bestehende Einsätze behalten die Besetzung an allen Tagen; 2 vierte Ansicht „Aufträge“ (Personen, Kolonnen, Geräte auf
Auftrag und Tag ziehen, umsetzen, herausnehmen, verlängern); 3 Zeitraum „1 Woche“; 4 Kurzname am Gerät; 5 in „Personen“ verschiebt Ziehen nur die Person, in
„Kolonnen“ weiter den ganzen Einsatz. Befund auf 961ed75, Bericht `bildgrundlage/befund_stufe6_r5_961ed75.txt`.

### Befund

**Speicherung bis 1.9.259.** `planning_slot_employees` (Einsatz, Person, UNIQUE, ON DELETE CASCADE) kennt keine Tage: eine Person gilt an jedem Tag des Einsatzes.
`planning_slot_resources.tage` (TEXT, JSON-Liste ISO-Tage, NULL = alle Tage) trägt die Tage der Geräte (1.9.234): `_geraete_pruefen()`, `_tage_lesen()`/
`_tage_schreiben()`, `_geraet_tage()`, `_tage_mitnehmen()`; „alle Tage gewählt“ speicherte nur die Oberfläche als NULL. Tage werden nur in Python ausgewertet.

**Die Falle.** „Alle Tage“ heißt „alle Tage des Einsatzes“. Verlängert eine Tag-Aktion (Ziehen aus der Liste, ab R5b) einen Einsatz, stünde jeder mit „alle
Tage“ auch am neuen Tag -- die ganze Kolonne statt der gezogenen Person. Eine Tag-Aktion schreibt die anderen deshalb vorher auf ihre bisherigen Tage fest;
nur „Ende ändern“ im Dialog (und Ziehen des ganzen Einsatzes) nimmt „alle Tage“ mit, wie bei den Geräten (Festlegung 1.9.234 Nr. 4). Für den Bestand wird
dabei kein Test rot -- die Falle braucht eigene Tests und Gegenproben.

**Leser der Besetzung** (ändert sich je Tag): Konflikte (`_conflicts()`: „Person doppelt“ bis 1.9.260 bei überschneidendem Zeitraum, ohne Datum; abwesend,
Freistellung, Antrag offen, Feiertag), Verteilung und Kapazität (`_besetzung()`, `_slot_distribution()`, `_day_capacity()`), Rechnung und Zustand im Dialog
(`_kapazitaet_rechnung()`, `_personen_zustand()`), `slot_to_dict()`, „Heute“ (`app/heute.py::_slots()`, `einsaetze()` über
`list_todays_assignments_for_employee()`, `einsatz_details()`, `naechste_tage()`, Vorwahl der Zeit in `arbeitszeit()`), `GET /api/field-view/upcoming`, der Text
der Kran-Termine (`app/kran_kalender.py::_inhalt()`), das Änderungsprotokoll („Tage“). **Bleibt:** Zugriff der Monteurin (`app/orders.py::
_assigned_order_id_queries()` -- ein Tag genügt), Auftragsliste der Zeiterfassung (Fenster ±14 Tage), Kolonne starten (Stammdaten), Einsatzbericht (liest die
Plantafel nicht), Lohn (liest keine Einsätze), Akte (`einsaetze()`: Zahl der Personen; Phase über `start_date`), Zeitraum der AV (`einsatz_zeitraum()`),
Kapazität je Kolonne (Stammdaten), Belegung der Geräte (schon je Tag). 63 Testdateien und 18 Klicktests legen Besetzung ohne Tage an -- mit Variante A bleibt das
„alle Tage“.

**Leerer Tag** (ohne Personen und Geräte): am Rand kürzt er den Einsatz, in der Mitte bleibt der Einsatz einer („niemand“ in „Aufträge“, Lücke in „Kolonnen“);
er zählt nirgends, die Stunden bleiben am Einsatz, der Kran-Termin teilt sich. Er widerspricht „ohne Kolonne mindestens eine Person“ (1.9.233 Nr. 5) und
„Kranvermietung braucht den Kran“.

**Neuer Einsatz durch Ziehen** (ab R5b): `create_slot()` kann es (vorläufig, AV und Kolonnen-Zuweisung, Rest der Stunden, Rückfrage, Kran-Kalender); es fehlen
Ziel (dazu / verlängern / neu), Verlängern ohne Mitnehmen, Sperren beider AVs in fester Reihenfolge beim Umsetzen, Prüfen ohne Schreiben, Zugehörigkeit (Regel 25).

**Schnittstellen** vorhanden: `GET /api/planning` (bis 63 Tage, „1 Woche“ geht), `GET /api/planning/auftraege` (nur Nummer, Projekt, Kunde), Anlegen, Teil-Update,
Löschen, Prüfen ohne Schreiben. Neu nötig (R5b/R5c): Auftragsliste der Woche (Soll, Rest, „nach Aufwand“, nächster Einsatz; feste Zahl Abfragen), Tag setzen,
Umsetzen, Herausnehmen, Verlängern, Kurzname am Gerät (`PUT /api/resources` ist ein Altfall in `BEKANNT`, Regel 22).

### Antworten von Tobias (08.11.2026)

1. Variante A: Spalte `planning_slot_employees.tage` wie bei den Geräten. 2. `downgrade()` bricht ab, solange jemand an einzelnen Tagen steht.
3. Wird der letzte Tag mit jemandem leer: Rückfrage „Der Einsatz hat dann niemanden mehr.“ Löschen | Behalten; Behalten = er bleibt mit dem zuletzt geleerten
Tag („niemand“). 4. Ohne Kolonne beim Anlegen mindestens eine Person oder ein Gerät, danach darf er leer werden; die Kranvermietung braucht ihr Gerät nur beim
Anlegen. 5. „Rückgängig“ nach einem eben angelegten Einsatz löscht ihn, solange er unverändert ist. 6. Zwei Einsätze am Tag: zwei Karten untereinander in der
Zelle; Ziel ist die Karte, auf die gezogen wird; auf freie Fläche der Vorschlag (Kolonne in den Einsatz derselben Kolonne, sonst neu; Person oder Gerät in den
ohne Kolonne, sonst in den frühesten). 7. „Direkt anschließend“ = nächster Arbeitstag (Fr -> Mo verlängert). 8. Kolonne auf den Einsatz einer anderen Kolonne:
eigener Einsatz; Kolonne auf eine Kranvermietung: ablehnen („bitte einzelne Bediener ziehen“); Person allein auf einen Tag ohne Einsatz einer Kranvermietung:
ablehnen („zuerst den Kran ziehen“). 9. Eine gezogene Kolonne bringt ihre Mitglieder ohne „nicht zeigen“. 10. Rest = Soll minus gebuchte Stunden, wie die Akte;
ohne Soll „nach Aufwand“, Herkunft Wartungsvertrag „Wartungsvertrag“, Kranvermietung „Kran mit Bediener“ bzw. „Kran ohne Bediener“; Stunden eines durch Ziehen
neuen Einsatzes wie heute (Rest). 11. „Heute“: von–bis = ihre Folge von Tagen um heute. 12. „Geräte“: Ziehen verschiebt nur das Gerät; in „Personen“ und
„Geräte“ setzt Ziehen in eine andere Zeile auf diese Person bzw. dieses Gerät um (übernimmt die Tage), Rückfrage bei Warnung. 13. Wochenleiste: eigener
Zustand „abwesend“ (schraffiert, ohne Art). 14. Hinweis „Feiertag“ nur an Tagen, an denen jemand steht. 15. Jede Ansicht merkt sich ihren Zeitraum („Aufträge“
Start 1 Woche, sonst 2 Wochen); die gezeigte Woche bleibt beim Wechsel gleich.

Runden: R5a Fundament (dieser Abschnitt), R5b Tag-Aktionen auf dem Server und Punkt 5, R5c Ansicht „Aufträge“ mit „1 Woche“ und Kurzname, R5d Nachrunde.

## Stufe 6, R5a: Fundament -- Besetzung je Tag (ab 1.9.259)

Auftrag vom 08.11.2026, Start 961ed75 (live, Datenbank `e3b7c51a9d26`, R4b eingespielt). Bestätigt: Festlegungen 1.9.253–1.9.258, N1 und W1 der Runde R4b,
außer 1.9.253 Nr. 6 zweiter Teil („die Kolonne schlägt sie weiter vor“) -- dafür Punkt 0 (1.9.259). Frage 1 aus R4b („alle einplanbar“): so eingespielt,
erledigt. Punkte: 0 die Kolonne schlägt „nicht zeigen“ nicht mehr vor; 1–5 nach Befund G (Spalte und Schreibweg, Leser je Tag, Monteurin, leerer Tag,
Oberfläche) mit den Antworten 3, 4, 11 und 14. Je Punkt eine Version.

### Umsetzung 1.9.259 (Punkt 0): die Kolonne schlägt „nicht zeigen“ nicht mehr vor

- `app/planning.py::_kolonne_schlaegt_vor()`: die aktiven Mitglieder ohne Kennzeichen „nicht zeigen“ (`_plantafel_map()`: gespeichert, sonst die Vorgabe aus
  Gruppe und Funktion). Wirkt überall, wo die Kolonne vorschlägt: Anlegen mit Kolonne, Wechsel der Kolonne (auch Ziehen in ihre Zeile), Prüfung des Dialogs
  (`_personen_zustand()`, Spalte „vorschlag“). Einzeln gewählt (`employee_ids`) kommt eine Person „nicht zeigen“ weiter in den Einsatz; bestehende Einsätze
  bleiben, wie sie sind. Die Kolonnen-Zuweisung an der AV (Schnappschuss, Zugriff der Monteurin) nimmt weiter alle aktiven Mitglieder.
- Stammdaten -> Kolonnen: in der Liste `plantafelHinweis()` je Mitglied („Vera Test · nicht zeigen“, title mit dem Grund), im Formular der Kolonne „· nicht
  zeigen“ hinter der Funktion.

#### Festlegungen 1.9.259 (bestätigt am 08.11.2026)

1. Die Kolonne schlägt nur Mitglieder ohne „nicht zeigen“ vor -- beim Anlegen, beim Wechsel der Kolonne (auch Ziehen in ihre Zeile) und in der Prüfung des
   Dialogs; das Kennzeichen wie überall (gespeichert, sonst die Vorgabe aus Gruppe und Funktion). Ersetzt 1.9.253 Nr. 6 zweiter Teil.
2. Einzeln gewählt kommt eine Person „nicht zeigen“ weiter in einen Einsatz; bestehende Einsätze und der Schnappschuss der Kolonne an der AV bleiben.
3. Stammdaten -> Kolonnen: Liste und Formular nennen bei ihr „nicht zeigen“.

#### Tests und Prüfung 1.9.259

Neu: `tests/test_v659_kolonne_ohne_nicht_zeigen.py` (Anlegen, Wechsel, Vorgabe aus der Gruppe, einzeln gewählt, Prüfung des Dialogs, Liste in node, Formular).
`scripts/klicktest_plantafel_besetzung.py`: Vera („nicht zeigen“) in Nord, der Dialog nennt nur Tom und Mia, Stammdaten-Liste und Formular nennen „nicht zeigen“
(20 statt 17 Prüfungen); dafür bekamen die Mitarbeiter einen Stundenlohn (ohne ihn lehnt `GET /api/employees` einen gewerblichen Mitarbeiter in der
Kalkulation ab, die Stammdaten luden nicht). Gegenproben: Archiv `gegenproben-stufe6-r5a.md`.

Angepasste Erwartung (Regel 28): `tests/test_v653_plantafel_kennzeichen.py::test_nicht_zeigen_auch_nicht_im_einsatz_dialog` -- alt: mit Kolonne Nord schlägt die
Prüfung „Tom, Bea, Vera“ vor; neu: „Tom, Bea“.

### Umsetzung 1.9.260 (Punkt 1): Besetzung je Tag -- Spalte und Schreibweg

- Modell: `PlanningSlotEmployee.tage` (TEXT, leer = alle Tage), Migration `b6e4d2a9c731` (hängt an `e3b7c51a9d26`): Spalte dazu, nichts geschrieben;
  `downgrade()` bricht ab, solange eine Zeile Tage trägt („Downgrade abgebrochen, nichts geändert: n Person(en) stehen an einzelnen Tagen …“), sonst fällt die
  Spalte weg. Geprobt auf einem Bestand unter SQLite und PostgreSQL (Wegwerf-Schema): hin, Abbruch mit Tagen, zurück ohne, wieder hin.
- `app/planning.py`: eine Funktion für die Tage einer Zeile, Person oder Gerät (`_tage_lesen()`, `_tage_schreiben()`, `_tage_der_zeile()` -- bis 1.9.259
  `_geraet_tage()`, auch in `app/heute.py` und `app/kran_kalender.py`), eine Prüfung (`_tage_pruefen()`: im Einsatz, keine leere Liste, Normalform).
  `create_slot(besetzung=…)` und `update_slot(besetzung=…)`: [{employee_id, tage}] über `_personen_pruefen()` (bekannt, aktiv, die erste zählt);
  `employee_ids` und der Vorschlag der Kolonne über `_alle_tage()`; beides zugleich `BesetzungUngueltig` (422). `_besetzung_setzen()` setzt mit Tagen, wer
  bleibt, behält seine Zeile; die Rückfrage vergleicht Personen samt Tagen (`_besetzung_stand()`). Ein neuer Zeitraum nimmt die Tage der Personen mit, wenn die
  Besetzung nicht neu gesetzt wird (`_tage_mitnehmen(…, "besetzung")`); die Prüfung „ohne Kolonne mindestens eine Person“ steht danach.
- **Die Falle** (`_alle_tage_festschreiben()`): `update_slot(alle_tage_mitnehmen=False)` schreibt vor einer Änderung des Zeitraums jede Person und jedes Gerät,
  das die Änderung nicht setzt und an allen Tagen stand, auf genau die bisherigen Tage fest. Was die Änderung setzt, gilt so (auch „alle Tage“ = die des neuen
  Zeitraums). Die Schnittstelle (`PUT`) kennt den Schalter nicht -- er ist für die Tag-Aktionen ab R5b; Dialog und Ziehen des ganzen Einsatzes nehmen alle mit.
- Antworten: `slot_to_dict()` nennt je Person `tage`, die Prüfung des Dialogs (`_personen_zustand()`) `tage` und `tage_text` wie bei den Geräten
  (`_tage_text()`, eine Schreibweise für beide). Schemas: `PlanningSlotPerson`, `besetzung` an Anlegen, Ändern (Teil-Update, null 422), Prüfen und der
  Übernahme eines Kran-Termins.
- Dialog (`planning.html`): der Zustand heißt `einsatz.besetzung` [{employee_id, tage}] (bis 1.9.259 `employee_ids`); Öffnen, Prüfung, Häkchen, „+ Person“,
  Wechsel der Art und der Kolonne halten die Tage, gesendet wird `besetzung`. Tage wählen lassen sich ab 1.9.264.

#### Festlegungen 1.9.260 (bestätigt am 08.11.2026)

1. Eine Person am Einsatz hat ihre Tage wie ein Gerät (leer = alle Tage); der Bestand steht an allen Tagen, die Migration schreibt nichts.
2. `downgrade()` bricht ab, solange jemand an einzelnen Tagen steht.
3. `besetzung` [{employee_id, tage}] beim Anlegen, Ändern, Prüfen und Übernehmen eines Kran-Termins; `employee_ids` und der Vorschlag der Kolonne heißen alle
   Tage; beides zugleich 422; Tage nur im Einsatz, keine leere Liste (422); unbekannt oder inaktiv 422; doppelt genannt zählt die erste.
4. Normalform auf dem Server, für Personen und Geräte: alle Tage des Einsatzes einzeln genannt heißt „alle Tage“.
5. Geänderte Tage einer Person fragen beim Speichern zurück wie eine geänderte Besetzung.
6. Ein neuer Zeitraum nimmt die Tage der Personen mit wie die der Geräte (gleiche Dauer verschoben, sonst nur die Tage im neuen Zeitraum, ohne Tag fällt die
   Person weg); wer an allen Tagen steht, steht danach an allen Tagen des neuen Zeitraums (Dialog, Ziehen des ganzen Einsatzes).
7. Die Falle: `update_slot(alle_tage_mitnehmen=False)` schreibt jeden, den die Änderung nicht setzt und der an allen Tagen stand, vorher auf seine bisherigen
   Tage fest (Personen und Geräte); was sie setzt, gilt so. Für die Tag-Aktionen ab R5b, nicht an der Schnittstelle.
8. Der Dialog hält die Besetzung mit den Tagen (aus der Prüfung) und schickt `besetzung`; Antwort und Prüfung nennen die Tage je Person.

#### Tests und Prüfung 1.9.260

Neu: `tests/test_v660_besetzung_je_tag.py` (Bestand und Kolonne alle Tage, Anlegen mit Tagen, Tage außerhalb und leer, unbekannt, inaktiv, beides zugleich,
null, doppelt, Normalform auch bei Geräten, Teil-Update lässt die Tage, Rückfrage bei geänderten Tagen, Prüfung mit Tagen, Mitnehmen beim Verschieben und bei
anderem Zeitraum, die Falle in vier Fällen, Änderungsprotokoll „Tage“, Dialog in node, Migration auf einem Bestand unter SQLite und PostgreSQL). Gegenproben:
Archiv `gegenproben-stufe6-r5a.md`.

Angepasste Erwartung (Regel 28): `tests/test_v637_plantafel_bedienbar.py::test_dialog_fuellt_die_zeile_beim_oeffnen` -- alt: `openEdit()` füllt
`employee_ids:s.employees.map(e=>e.id)`; neu: `besetzung:s.employees.map(e=>({employee_id:e.id,tage:e.tage??null}))`.

### Umsetzung 1.9.261 (Punkt 2): Konflikte, Kapazität und der Zustand im Dialog je Tag

- `app/planning.py::_conflicts()`: „Person doppelt“ nur, wenn sich die Tage der Person in beiden Einsätzen treffen (bis 1.9.260 genügte, dass sich die
  Zeiträume überschneiden); „Person doppelt“ und „Gerät doppelt“ tragen die gemeinsamen Tage (`tage`, sortiert). `tafel_zaehler()` zählt ein Paar weiter
  einmal (die Tage gehen nicht in `date`). Abwesend und Freistellung je Tag nur an den Tagen der Person (`_tage_je_person()`), ein offener Antrag nur, wenn er
  ihre Tage berührt, mit dem ersten betroffenen Tag. Feiertag und betriebsfreier Tag nur an einem Tag, an dem jemand steht -- Person oder Gerät
  (`_jemand_am()`, Antwort 14).
- Kapazität: `_slot_distribution()` gibt `_day_capacity()` je Tag nur die Personen dieses Tages -- damit auch „Kapazität reicht nicht“, die Kapazität je Person
  und je Kolonne der Tafel (aus der Verteilung). `_kapazitaet_rechnung()`: je Person ihre Arbeitstage am Einsatz; die Kurzform „n Personen × m Arbeitstage ×
  h“ nur, wenn alle an allen Arbeitstagen gleich stehen, sonst je Person.
- Dialog (`_personen_zustand()`): „auch bei …“ (gewählt) bzw. „bei …“ (Vorschlag, „+ Person“) mit den gemeinsamen Tagen als Folgen („02.–03.11., 05.11.“) --
  eine gewählte Person an ihren Tagen, sonst gegen alle Tage des Einsatzes; abwesend nur an ihren Tagen; ein Antrag nur, wenn er ihre Tage berührt.
- Der Bestand (alle an allen Tagen) meldet dieselben Konflikte wie bisher, nur mit den Tagen; die Tests bis 1.9.260 laufen ohne Änderung.

#### Festlegungen 1.9.261 (bestätigt am 08.11.2026)

1. „Person doppelt“ nur an gemeinsamen Tagen; Person und Gerät doppelt nennen ihre Tage; der Zähler zählt ein Paar weiter einmal.
2. Abwesend, Freistellung des Arbeitszeitkalenders und Antrag offen nur an den Tagen der Person; der Antrag mit dem ersten betroffenen Tag.
3. Feiertag und betriebsfreier Tag nur, wenn an dem Tag jemand steht -- eine Person oder ein Gerät (Antwort 14).
4. Die Kapazität eines Tages kommt nur aus den Personen an diesem Tag (Verteilung, „Kapazität reicht nicht“, Kapazität der Tafel); die Rechnung im Dialog je
   Person mit ihren Arbeitstagen.
5. Dialog: „auch bei …“/„bei …“ mit den gemeinsamen Tagen (gewählt an ihren Tagen, sonst an allen Tagen des Einsatzes); abwesend nur an ihren Tagen; ein
   Antrag nur, wenn er ihre Tage berührt.

#### Tests und Prüfung 1.9.261

Neu: `tests/test_v661_konflikte_je_tag.py` (doppelt nur an gemeinsamen Tagen, Bestand mit Tagen, Gerät mit Tagen, Zähler, abwesend, Antrag, Feiertag mit
Person und mit Gerät, Verteilung je Tag, Rechnung je Person, Dialog „auch bei“, abwesend und Antrag im Dialog). Gegenproben: Archiv
`gegenproben-stufe6-r5a.md`. Angepasste Erwartungen: keine.

### Umsetzung 1.9.262 (Punkt 3): was die Monteurin merkt

- `app/planning.py::list_todays_assignments_for_employee()`: nur Einsätze, an denen sie an dem Tag steht (ihre Tage, `_tage_der_zeile()`; die Besetzung
  wird mitgeladen); `list_upcoming_assignments_for_employee()`: nur Einsätze, an denen sie im Fenster einen Tag hat. Der Zeitraum in diesen Antworten bleibt
  der des Einsatzes (keine Seite zeigt ihn mehr; `assignments` liest nur noch der Test).
- `app/heute.py`: `_slots()` nur Einsätze mit einem ihrer Tage im Zeitraum (`ihre_tage()`); `einsaetze()`: „Heutiger Einsatz · von–bis“ = ihre Folge von Tagen
  um heute aus den Einsätzen des Auftrags, an denen sie heute steht (`folge_um()`, Antwort 11: ein Tag, der kein Arbeitstag ist -- Wochenende, Feiertag,
  betriebsfreier Tag --, unterbricht nicht, ein Arbeitstag ohne sie schon; Arbeitstage wie `Tage` über `_arbeitstag()`); `einsatz_details()`: „Mit dir“ und
  „ist nicht da“ nur, wer heute am Einsatz steht; `naechste_tage()`: nur ihre Tage, „mit …“ je Tag nur, wer an dem Tag dabei ist, „weiter“ nur, wenn sie heute
  dort steht (bis 1.9.261: der Einsatz läuft heute). Die Vorwahl der Zeiterfassung (`arbeitszeit()`) folgt den Karten.
- `app/kran_kalender.py::_inhalt(slot, von, bis)`: je Termin (Folge von Tagen des Geräts) „Besetzung:“/„Bediener:“ nur mit denen, die an einem dieser Tage am
  Einsatz stehen; der Abgleich vergleicht den Inhalt je Termin und schickt nur geänderte hinaus.
- Bleibt: Zugriff auf den Auftrag (`app/orders.py::_assigned_order_id_queries()` -- ein Tag genügt), Auftragsliste der Zeiterfassung (Fenster ±14 Tage um die
  Einsätze der AV), Kolonne starten (Stammdaten), Einsatzbericht, Lohn.

#### Festlegungen 1.9.262 (bestätigt am 08.11.2026)

1. „Heute“: eine Karte nur an ihren Tagen; „Heutiger Einsatz · von–bis“ = ihre Folge von Tagen um heute -- ein Tag, der kein Arbeitstag ist, unterbricht sie
   nicht, ein Arbeitstag ohne sie schon; aus allen Einsätzen des Auftrags, an denen sie heute steht.
2. „Mit dir“ und „ist nicht da“ nur, wer heute am Einsatz steht; ein zweiter Einsatz desselben Auftrags, an dem sie heute nicht steht, zählt nicht.
3. „Nächste Tage“: nur ihre Tage; „mit …“ je Tag nur, wer an dem Tag dabei ist; „weiter“ nur, wenn sie heute am Einsatz steht.
4. Die Vorwahl der Zeiterfassung folgt den Karten: nur an ihren Tagen.
5. `GET /api/field-view/today` (assignments) und `/upcoming`: nur Einsätze, an denen sie am Tag bzw. im Fenster einen Tag hat; der Zeitraum darin bleibt der des
   Einsatzes.
6. Kran-Kalender: jeder Termin nennt als Besetzung bzw. Bediener nur, wer an einem seiner Tage am Einsatz steht.
7. Unverändert: Zugriff auf den Auftrag (ein Tag genügt), Auftragsliste der Zeiterfassung, Einsatzbericht, Lohn.

#### Tests und Prüfung 1.9.262

Neu: `tests/test_v662_monteurin_je_tag.py` (Karte nur an ihren Tagen, von–bis als Folge, über das Wochenende, „Mit dir“, Nächste Tage mit „mit“ je Tag,
„weiter“, Vorwahl, `/today` und `/upcoming`, Kran-Termine, zwei Einsätze desselben Auftrags). Neu: `scripts/klicktest_heute_tage.py` (Kai am Mittwoch ohne
Einsatz -- „Heute ist nichts eingeplant.“, keine Vorwahl, Nächste Tage Do–Fr mit den anderen dieser Tage und nur Di 17.11. am Dachfenster, quer und hoch, hell
und dunkel; Mia mit der Karte Ortgang und „Mit dir“ Tom; Ole mit der Karte Sturmschaden; Lia mit „mit Kai“ nur am Di). Gegenproben: Archiv `gegenproben-stufe6-r5a.md` -- die Gegenprobe
`262_3d` und `262_3e` blieben im Klicktest zuerst grün (Kais künftige Tage waren genau die restlichen Tage des Einsatzes, und an ihnen standen alle anderen
ohnehin dabei); der Klicktest bekam den Einsatz „Dachfenster Krüger“ (Lia an allen Tagen, Kai nur am Di) und die Sicht von Lia („mit Kai“ nur am Di), dieselben
Gegenproben danach. Angepasste Erwartungen: keine.

### Umsetzung 1.9.263 (Punkt 4): der leere Tag

- Ein Tag ist leer, wenn an ihm keine Person und kein Gerät am Einsatz steht (`_besetzte_tage()`). **Am Rand:** `_raender_kuerzen()` setzt Beginn und Ende auf
  den ersten und letzten Tag mit jemandem -- auch über ein Wochenende --, nach jedem Anlegen (`_create_slot()`) und Ändern (`_update_slot()`); einzelne Tage
  bleiben, in der Normalform (wer danach an allen Tagen steht, heißt „alle Tage“). Die Stunden (`PlanningSlotCapacity`) bleiben. Ein Einsatz, an dem gar niemand
  steht, behält seinen Zeitraum. Wer an allen Tagen steht (NULL), belegt jeden Tag -- der Bestand wird nie gekürzt.
- **In der Mitte:** der Einsatz bleibt einer. `leere_tage()` nennt die Arbeitstage ohne jemanden (ein Tag ohne Arbeit ist nie leer), `abschnitte()` die Stücke des
  Balkens ohne die leeren Tage -- ein Tag ohne Arbeit an einer Lücke gehört nicht dazu, ein Stück nur aus solchen Tagen fällt weg; ein ganz leerer Einsatz ist ein
  Stück (er bleibt sichtbar). `slot_to_dict()` trägt `niemand`, `leere_tage`, `abschnitte`; die Arbeitstage nach den Einstellungen der Planung und den
  Feiertagen (für die Tafel eine Abfrage für alle Einsätze im Bild, `tafel["feiertage"]`). Kein Hinweis, kein Zähler; der Termin im Kalender des Krans teilt sich
  an einem leeren Tag von selbst (Folge der Tage des Geräts).
- **Ganz leer:** nähme eine Änderung dem Einsatz den letzten Tag mit jemandem (vorher jemand, danach niemand), wirft `_update_slot()` `EinsatzWirdLeer`
  (nichts gespeichert); `PUT` antwortet 409 mit `rueckfrage` {art „einsatz_leer“, text „Der Einsatz hat dann niemanden mehr.“, optionen [loeschen, behalten]}.
  Mit `wenn_leer` (Teil-Update, sonst 422): „loeschen“ löscht den Einsatz samt seinen Kran-Terminen (Antwort `{"deleted": true, "id": …}`), „behalten“ lässt ihn
  mit dem zuletzt geleerten Tag stehen -- werden mehrere Tage zugleich leer (Dialog), mit dem ersten davon. Ein schon leerer Einsatz fragt nicht. Die Prüfung des
  Dialogs (`einsatz_pruefen()`) fragt nicht, sie trägt `leer`.
- **Regeln (Antwort 4):** ohne Kolonne beim Anlegen eine Person oder ein Gerät (Schema und `create_slot()`, „Ohne Kolonne bitte mindestens eine Person oder ein
  Gerät wählen.“); beim Ändern keine Mindestbesetzung mehr (bis 1.9.262: ohne Kolonne immer eine Person). Eine Kranvermietung braucht ihr Gerät nur beim Anlegen
  (bis 1.9.262 auch beim Ändern, 422).
- Seite (`planning.html`): Dialog „Der Einsatz hat dann niemanden mehr.“ mit Abbrechen, Löschen, Behalten (`leerFrage()`, `leerEntscheiden()`); die Wahl geht mit
  `wenn_leer` noch einmal hinaus -- beim Speichern im Dialog und beim Ziehen (z. B. in die Zeile einer leeren Kolonne). Der Einsatz-Dialog nennt es schon vorher
  („… beim Speichern: löschen oder behalten“). Die Lücke im Balken kommt mit 1.9.264.

#### Festlegungen 1.9.263 (bestätigt am 08.11.2026 -- Nr. 2: ein ganz leerer Einsatz meldet seit 1.9.266 keine Kapazität (Frage 2))

1. Am Rand fällt jeder Tag ohne Person und Gerät weg (auch ein Wochenende), nach jedem Anlegen und Ändern; einzelne Tage bleiben in der Normalform; die Stunden
   bleiben. Ein Einsatz ohne jemanden behält seinen Zeitraum.
2. In der Mitte bleibt der Einsatz einer; leer ist nur ein Arbeitstag ohne jemanden; die Stücke des Balkens ohne die leeren Tage und ohne die Tage ohne Arbeit an
   einer Lücke; ein ganz leerer Einsatz ist ein Stück. Der leere Tag selbst meldet nichts und zählt nicht; fehlt dadurch Kapazität für die Stunden des Einsatzes,
   sagt das „Kapazität reicht nicht“ wie bisher -- auch an einem behaltenen, ganz leeren Einsatz.
3. Wird ein Einsatz ganz leer: 409 „Der Einsatz hat dann niemanden mehr.“ mit Löschen | Behalten, nichts gespeichert; behalten = mit dem zuletzt geleerten Tag,
   bei mehreren zugleich mit dem ersten; ein schon leerer Einsatz fragt nicht.
4. Die Prüfung des Dialogs fragt nicht, sie sagt „leer“; der Dialog nennt es vorher, die Rückfrage kommt beim Speichern und beim Ziehen.
5. Ohne Kolonne beim Anlegen eine Person oder ein Gerät, danach darf der Einsatz leer werden; eine Kranvermietung braucht ihr Gerät nur beim Anlegen.

#### Tests und Prüfung 1.9.263

Neu: `tests/test_v663_leerer_tag.py` (Rand beim Anlegen samt Stunden, Wochenende am Rand, Rand beim Ändern, Mitte mit Lücke, Lücke am Wochenende, Wochenende in
der Mitte, leerer Tag zählt nirgends, Kran-Termin teilt sich, Rückfrage samt Antwort, behalten mit dem zuletzt geleerten bzw. ersten Tag, löschen, schon leer,
Prüfung des Dialogs, ohne Kolonne nur ein Gerät, Seite in node und im Text, ganz leer mit Stunden meldet die Kapazität). Gegenproben: Archiv `gegenproben-stufe6-r5a.md`.

Angepasste Erwartungen (Regel 28):
- `tests/test_v633_besetzung_je_einsatz.py::test_ohne_kolonne_behaelt_die_personen` -- alt: `employee_ids: []` ohne Kolonne 422 „mindestens eine Person“; neu: 409
  mit der Rückfrage „einsatz_leer“, Besetzung unverändert.
- `tests/test_v633_besetzung_je_einsatz.py::test_update_slot_direkt_ohne_kolonne_ohne_personen` -- alt: `BesetzungUngueltig`; neu: `EinsatzWirdLeer`, mit
  `wenn_leer="behalten"` leer gespeichert.
- `tests/test_v640_kranvermietung.py::test_aendern_einer_kranvermietung` -- alt: `geraete: []` 422 („der Kran bleibt“), ein Kürzen, bei dem der Kran wegfiele, 422;
  neu: mit Bediener darf der Kran weg (200); der Kran nur am zweiten Tag kürzt den Einsatz auf diesen Tag, ihm danach den Kran zu nehmen fragt zurück (409).
- `tests/test_v640_kranvermietung.py::test_baustelle_ohne_kolonne_braucht_weiter_eine_person` -- alt: 422 bzw. `BesetzungUngueltig`; neu: 409 bzw.
  `EinsatzWirdLeer` (beim Anlegen weiter eine Person oder ein Gerät).
- `tests/test_v399_teil_updates_rest.py::test_plantafel_null_in_pflichtfeldern_ist_422` -- alt: auch `team_id: null` 422; neu: ohne `team_id` in der Liste (null
  heißt „ohne Kolonne“, und der leere Einsatz der Attrappe darf seit 1.9.263 ohne Kolonne sein -- die 422 kam bis dahin aus der Mindestbesetzung).
- `tests/test_v648_einsatz_pruefen.py::test_schnittstelle_mit_rolle_und_fehlern` -- alt: ohne Kolonne und ohne Person 422 (mit der Pritsche); neu: mit der Pritsche
  200, ohne Person und Gerät 422 „mindestens eine Person oder ein Gerät“.
- Eigene Tests dieser Runde, nur Aufbau: `test_v660::test_doppelt_genannt_zaehlt_die_erste` (dazu Tom an allen Tagen), `test_v661::test_person_doppelt_nur_an_
  gemeinsamen_tagen` und `::test_dialog_antrag_nur_an_ihren_tagen` (dazu eine Person an allen Tagen), `test_v662::test_mobil_einsaetze_heute_und_kommend` (dazu
  Kai an allen Tagen) -- sonst kürzte der Rand die Einsätze, und die Tests prüften nicht mehr, was sie sollen. Ihre Erwartungen bleiben.

### Umsetzung 1.9.264 (Punkt 5): die Tafel zeigt die Besetzung je Tag

- Dialog (`planning.html`): je gewählter Person neben dem Zustand ein Knopf mit ihren Tagen (`tage_text` vom Server: „alle Tage“ oder „nur …“), aufgeklappt
  Knöpfe je Tag des Einsatzes (`personTageZeigen()`, `personTagUmschalten()` -- wie die Geräte seit 1.9.248: alle gewählt heißt „alle Tage“, der letzte Tag lässt
  sich nicht abwählen, dafür das Häkchen). Ändert sich im Dialog Von oder Bis, behalten Personen und Geräte mit einzelnen Tagen nur die Tage im neuen Zeitraum, wer
  keinen hat, fällt weg (`tageImZeitraum()`, wie das Mitnehmen des Servers) -- sonst schickte der Dialog Tage außerhalb des Einsatzes (422).
- „Kolonnen“ und „Ohne Kolonne“: je Stück des Einsatzes ein Balken (`stueckItems()` aus `abschnitte` vom Server, 1.9.263) -- eine Lücke an jedem leeren Tag; die
  Vornamen je Stück nur, wer an einem seiner Tage dabei ist (`vornamen(s, stueck)`); ein ganz leerer Einsatz zeigt „niemand“. Ziehen eines Stücks verschiebt weiter
  den ganzen Einsatz (Festlegung 1.9.249 Nr. 3, Punkt 5 der Runde kommt mit R5b).
- „Personen“: je Folge ihrer Tage ein Balken (`folgen(personTageIn())`, aufeinander folgende Kalendertage wie bei den Geräten). „Geräte“: je Folge wie bisher,
  seit 1.9.264 mit dem Stück für die Warnungen.
- Warnung und Hinweis am Stück, dessen Tage sie betreffen (`imStueck()`: die Tage von Person/Gerät doppelt, sonst der Tag; ohne Tag an jedem Stück); „Personen“
  zeigt weiter nur die Konflikte der Person (1.9.250). Die Warnzeile (`konfliktZeile()`) nennt die Tage von Person/Gerät doppelt. „doppelt …“ in der Zeile einer
  Person zählt je Tag (`doppeltText()`, bis 1.9.263 die Überschneidung der Zeiträume). Der Titel eines Balkens nennt je Person ihre Tage („Kai Kolb (nur 12.11.,
  13.11.)“).

#### Festlegungen 1.9.264 (bestätigt am 08.11.2026)

1. Dialog: je gewählter Person ihre Tage wie bei den Geräten („alle Tage“ oder „nur …“, Knöpfe je Tag, der letzte Tag nicht abwählbar); ändert sich im Dialog der
   Zeitraum, behalten Personen und Geräte mit einzelnen Tagen nur die Tage darin, wer keinen hat, fällt weg.
2. „Kolonnen“ und „Ohne Kolonne“: je Stück ein Balken, eine Lücke an jedem leeren Tag; die Vornamen je Stück; ein ganz leerer Einsatz zeigt „niemand“. Ziehen eines
   Stücks verschiebt den ganzen Einsatz.
3. „Personen“: je Folge ihrer Tage ein Balken.
4. Warnung und Hinweis am Stück ihrer Tage (ohne Tag an jedem Stück); die Warnzeile nennt die Tage.
5. „doppelt …“ in der Zeile einer Person je Tag.
6. Der Titel eines Balkens nennt je Person ihre Tage.

#### Tests und Prüfung 1.9.264

Neu: `tests/test_v664_plantafel_tage.py` (Kolonne mit Lücke und Namen je Stück, ganz leer „niemand“, Person je Folge, Warnung am Stück, doppelt je Tag, Dialog:
Tage umschalten und Zeitraum, Zeile mit Tagen, Warnzeile mit Tagen, Titel). Neu: `scripts/klicktest_plantafel_tage.py` (18 Prüfungen: Kolonnen mit Lücke und
Warnung am Stück, kein Tom doppelt, „Personen“ je Folge, Kai „doppelt 13.11.“, Dialog mit den Tagen je Person und Knöpfen, Kai am Mi dazu -> ein Balken; leer:
Hinweis vorher, Rückfrage, Behalten -> „niemand“ mit dem Hinweis Kapazität, Löschen -> weg; Bilder Kolonnen, Personen, Dialog bei 1440 und 1280 px, hell und
dunkel, dazu die Rückfrage). Gegenproben: Archiv `gegenproben-stufe6-r5a.md`.

Angepasste Erwartungen (Regel 28), nur Aufbau -- die node-Tests holen die Funktionen der Seite einzeln, die neuen Helfer kamen in ihre Listen:
`tests/test_v647_plantafel_tafel.py::test_zeilen_der_kolonnen` (`einsatzTage`, `personTageIn`, `imStueck`, `stueckItems`),
`tests/test_v650_plantafel_personen.py::test_gruppen_doppelt_und_antrag` (`einsatzTage`, `personTageIn`, `folgen`) und `::test_balken_einer_person_nur_mit_ihren_
konflikten` (`imStueck`), `tests/test_v655_geraetezeilen.py` (`imStueck`), `tests/test_v574_balken_lesbar.py` (`FUNKTIONEN` + `imStueck`; erst die volle
Suite der Arbeitskopie fand ihn, vier Tests mit „imStueck is not defined“). Ihre Erwartungen bleiben.

### Stand nach R5a (1.9.259–1.9.264)

Die Besetzung gilt je Tag, gespeichert wie bei den Geräten; der Bestand steht an allen Tagen und sieht aus wie vorher. Konflikte, Kapazität, „Heute“, „Nächste
Tage“, die Vorwahl der Zeit und die Kran-Termine rechnen je Tag; der leere Tag kürzt am Rand und lässt in der Mitte eine Lücke; die Tafel zeigt und ändert die Tage
im Dialog. Die Falle (Verlängern ohne Mitnehmen) liegt als `update_slot(alle_tage_mitnehmen=False)` bereit -- die Tag-Aktionen nutzen sie mit R5b.

## Stufe 6, R5b: Tag-Aktionen (ab 1.9.265)

Auftrag vom 08.11.2026, Start 55ea3fd (live, Datenbank `b6e4d2a9c731`, R5a eingespielt). Bestätigt: Festlegungen 1.9.259–1.9.264. Fragen aus R5a: 1 ja (werden
mehrere Tage zugleich leer, bleibt der erste); 2 ein Einsatz mit „niemand“ meldet keine Kapazität (Punkt 0b); 3 ja (ein Tag ohne Arbeit unterbricht die Folge
nicht); 4 ja (Normalform auch für Geräte). Punkte: vorweg 0a Nebenbefund `GET /api/employees`, 0b leerer Einsatz ohne Kapazität; dann nach Befund G und D mit
den Antworten 5–8 und 12: 1 Tag setzen (dazu, verlängern, neu) für Person, Kolonne und Gerät mit Prüfen ohne Schreiben, die Falle über
`alle_tage_mitnehmen=False`; 2 Umsetzen, Herausnehmen, Verlängern; 3 Sperren in fester Reihenfolge, Zugehörigkeit, Rolle, Teil-Update, keine Datenbank auf der
Event-Loop, Rückgängig; 4 Ziehen in „Personen“ und „Geräte“ nur für diese Person bzw. dieses Gerät, in eine andere Zeile umsetzen. Je Punkt eine Version.

### Umsetzung 1.9.265 (Punkt 0a): Mitarbeiterliste ohne die Prüfung des Formulars

Befund (R5a, Abschnitt 10 des Berichts): `EmployeeOut` erbte von `EmployeeCreate` die Prüfung des Formulars (`validate_commercial_wage`: gewerblich oder in der
Kalkulation -> positiver Stundenlohn bzw. Monatsgehalt; dazu die Grenzen der Felder). `GET /api/employees` (und `/api/employees/{id}`, `/caseworkers`) baute
die Antwort für Admin und Büro – Finanzen mit `EmployeeOut.model_validate()` -- ein gespeicherter Mitarbeiter, den das Formular heute ablehnen würde, brachte die
ganze Liste auf 500. Büro – Auftrag (`EmployeeRosterOut`) und die Monteurin (`EmployeeNameOut`) waren nicht betroffen.

- `app/schemas.py::_felder_ohne_pruefung(eingabe, name)`: die Felder eines Eingabeschemas mit Name, Typ und Vorgabe, ohne Grenzen und ohne Validatoren
  (`pydantic.create_model`). `EmployeeOut` erbt davon statt von `EmployeeCreate` -- ein neues Feld im Formular kommt von selbst in die Antwort, eine neue Prüfung
  nicht.
- Anlegen und Ändern (`EmployeeCreate`/`EmployeeUpdate`) prüfen unverändert (422).
- Nicht geändert, nur gesehen: vier weitere Antwortschemata erben eine Prüfung ihres Eingabeschemas -- `EmployeeFunctionOut` (`validate_group`),
  `EmployeeAbsenceOut` (`validate_dates`), `AccountOut` (`validate_default_tax_rate`), `IncomingInvoiceItemOut` (`validate_tax_rate`). Ob gespeicherte Werte sie
  verletzen können, ist nicht geprüft.

#### Festlegungen 1.9.265 (bestätigt am 09.11.2026)

1. Die Antwort mit dem Mitarbeiter (`EmployeeOut`) prüft nicht wie das Formular: keine Validatoren, keine Grenzen; sie hat jedes Feld des Formulars und zeigt, was
   gespeichert ist.
2. Geprüft wird nur beim Speichern: Anlegen und Ändern ohne Stundenlohn (gewerblich) weiter 422 -- wie bisher an zwei Stellen, im Schema
   (`EmployeeCreate.validate_commercial_wage`) und in `app/employees.py::apply_employee_payload()`.
3. Die vier anderen Antworten mit geerbter Prüfung bleiben, wie sie sind (oben).

#### Tests und Prüfung 1.9.265

Neu: `tests/test_v665_mitarbeiter_ohne_stundenlohn.py` (Liste und einzeln als Admin, Büro – Finanzen und Büro – Auftrag mit einem gewerblichen Mitarbeiter ohne
Stundenlohn; Anlegen und Ändern ohne Stundenlohn 422, die Liste danach lesbar; die Antwort ohne Validatoren und Grenzen mit allen Feldern des Formulars).
Gegenproben: Archiv `gegenproben-stufe6-r5b.md`. Angepasste Erwartungen: keine.

### Umsetzung 1.9.266 (Punkt 0b): „niemand“ meldet keine Kapazität

Frage 2 aus R5a: ein behaltener, ganz leerer Einsatz meldete für seine Stunden „Kapazität reicht nicht“ (Festlegung 1.9.263 Nr. 2, zweiter Teil). Antwort: ein
Einsatz mit „niemand“ meldet keine Kapazität. `app/planning.py::_conflicts()` legt den Hinweis `capacity` nur noch an, wenn am Einsatz jemand steht
(`_besetzte_tage()`, Person oder Gerät). Damit schweigen Tafel, Zähler („Hinweise“), die Antwort beim Speichern (`einsatz_konflikte()`) und die Prüfung des
Dialogs -- alle rechnen über `_conflicts()`. Ein Einsatz mit nur einem Gerät (keine Person, also keine Kapazität) meldet weiter. Die Rechnung im Dialog
(„niemand eingeplant = 0,00 h“) bleibt.

#### Festlegungen 1.9.266 (bestätigt am 09.11.2026)

1. Ein ganz leerer Einsatz („niemand“: keine Person, kein Gerät) meldet keine Kapazität -- auf der Tafel, im Zähler, beim Speichern und in der Prüfung des Dialogs.
   Ersetzt 1.9.263 Nr. 2, zweiter Teil.
2. Steht jemand am Einsatz, auch nur ein Gerät, meldet er „Kapazität reicht nicht“ wie bisher.

#### Tests und Prüfung 1.9.266

Neu: `tests/test_v666_niemand_ohne_kapazitaet.py` (Tafel und Zähler, Speichern und Prüfung, ein Einsatz mit nur einem Gerät meldet weiter). Gegenproben: Archiv
`gegenproben-stufe6-r5b.md`.

Angepasste Erwartungen (Regel 28): `tests/test_v663_leerer_tag.py::test_ganz_leer_mit_stunden_meldet_die_kapazitaet` heißt jetzt `…_meldet_keine_kapazitaet`
-- alt: Konflikte `[("capacity", "hinweis")]`, neu: keine, „niemand“. `scripts/klicktest_plantafel_tage.py`, Prüfung „Leer: Behalten“ -- alt: Knopf „1 Hinweis“,
Konflikte der Garage `["capacity"]`; neu: „Keine Warnungen“, keine.

### Umsetzung 1.9.267 (Punkt 1): Tag setzen

Neues Modul `app/tag_aktionen.py` (Regeln im Kopf), Endpunkt `POST /api/planning/tag-setzen` {order_id, tag, employee_id | team_id | resource_id, slot_id?,
trotzdem_planen, pruefen} -- ab Büro – Auftrag wie die Tafel, `def`, Sitzung mit `scope="function"`.

- **Ziel** (`ziel_finden()`): auf einer Karte (slot_id, Antwort 6) dieser Einsatz -- er muss zum Auftrag gehören (`_karte()`: fremd wie unbekannt 404, Regel 25)
  und an dem Tag liegen (422); eine Kolonne nur in den Einsatz derselben Kolonne, sonst ein eigener (Antwort 8, auch auf der Karte eines Einsatzes ohne Kolonne).
  Auf freier Fläche: ein Einsatz des Auftrags an dem Tag -> dazu (Person oder Gerät: der ohne Kolonne, sonst der früheste; Kolonne: der derselben Kolonne);
  sonst einer, an den der Tag direkt anschließt (`anschliessend()`: kein Arbeitstag dazwischen, Antwort 7) -> verlängert, der vordere zuerst, nie
  zusammengelegt; sonst neu.
- **Neu** über `_create_slot(…, _offen=True)` (Anlegen ohne Abschluss): vorläufig, die Art des letzten Einsatzes des Auftrags (sonst Baustelle,
  `_art_des_auftrags()`), Stunden = Rest, mit Kolonne nur, wenn eine Kolonne gezogen wurde.
- **Dazu und verlängert** über `_update_slot(…, alle_tage_mitnehmen=False, dazu=[…], _offen=True)` -- die Falle: wer „alle Tage“ hatte, steht danach an genau den
  bisherigen Tagen (`_alle_tage_festschreiben()`, Personen und Geräte); neu in `_update_slot()` die internen Änderungen `dazu`/`weg`
  (`app/planning.py::_tage_aendern()`: einer Person oder einem Gerät Tage geben oder nehmen, die übrigen Zeilen unberührt, Normalform danach) und `_offen`
  (ohne Warnungen, Kran-Kalender und Commit -- die Tag-Aktion schließt selbst ab). `PUT /api/planning/slots/{id}` kennt `dazu`/`weg` nicht (Schema).
- **Kran** (`_kran_pruefen()`, Antwort 8): eine Kolonne nie in eine Kranvermietung -- weder auf ihrer Karte noch an einem Auftrag, dessen letzter Einsatz eine
  ist (422 „bitte einzelne Bediener ziehen“); eine Person nur dazu an einen Tag mit Einsatz, nicht verlängern oder neu (422 „zuerst den Kran ziehen“); ein Gerät
  darf verlängern und neu anlegen.
- **Kolonne** (`_eintraege()`): ihre Mitglieder ohne „nicht zeigen“ (`_kolonne_schlaegt_vor()`, Antwort 9) und ihre aktiven Geräte; schlägt sie niemanden vor,
  422.
- **Fragen** (`neue_warnungen()`, `abschliessen()`): nur bei Warnungen, die die Aktion neu bringt -- verglichen mit den Warnungen aller Einsätze des Auftrags
  vorher, je Warnung mit Art, Wem, anderem Einsatz und ihren Tagen (`_schluessel()`): eine neue Warnung oder ein neuer Tag einer bestehenden fragt, was vorher
  schon da war nicht; eine Rückfrage für alle (ganze Kolonne); Hinweise nie. 409 wie beim Anlegen (`warnungen`, `hinweise`), nichts gespeichert, auch keine neue
  Arbeitsvorbereitung.
- **Prüfen** (`pruefen: true`): derselbe Weg bis zum Flush, dann `pruefung()` (`aktion`, `slot_id` -- leer bei „neu“ --, `warnungen`, `hinweise`, `fragt`) und
  rollback.
- Antwort: `aktion` (dazu | verlaengert | neu), `slot_id`, `tage` (der Person bzw. des Geräts am Einsatz, alle einzeln), `bis` (letzter Tag des Einsatzes, für „bis …
  verlängern“) und `einsatz` wie beim Speichern. Ein geschlossener Auftrag bekommt keinen Tag, auch nicht dazu (409).
- Nebenbei: hält ein Test die Ausnahme einer abgelehnten Aktion fest (`pytest.raises`), hält ihr Traceback die verworfenen Objekte -- SQLAlchemy warnte beim
  nächsten Flush („Identity map already had an identity …“). Im Server verwirft der Router die Ausnahme; der Test gibt sie frei (`del fehler`).

#### Festlegungen 1.9.267 (bestätigt am 09.11.2026)

1. `POST /api/planning/tag-setzen`: genau eine Person, Kolonne oder ein Gerät, ein Tag, ein Auftrag (sonst 422); `pruefen` schreibt nichts.
2. Frei: hat der Auftrag an dem Tag einen Einsatz, kommt sie dazu -- Person oder Gerät in den ohne Kolonne, sonst den frühesten; eine Kolonne nur in den derselben
   Kolonne.
3. Schließt der Tag an einen Einsatz an (kein Arbeitstag dazwischen, Fr -> Mo), wird er verlängert -- der vordere zuerst, nie zusammengelegt; sonst neu.
4. Auf einer Karte: dieser Einsatz (des Auftrags, sonst 404; an dem Tag, sonst 422); eine Kolonne auf der Karte einer anderen Kolonne oder eines Einsatzes ohne
   Kolonne bekommt einen eigenen.
5. Neu: vorläufig, die Art des letzten Einsatzes des Auftrags (sonst Baustelle), Stunden = Rest, mit Kolonne nur, wenn eine Kolonne gezogen wurde.
6. Kranvermietung: eine Kolonne nie (Karte oder Art des Auftrags), 422; eine Person nur dazu an einen Tag mit Einsatz, sonst 422; ein Gerät verlängert oder legt
   neu an.
7. Die Falle: verlängert wird über `update_slot(alle_tage_mitnehmen=False)` -- Personen und Geräte stehen danach an genau ihren bisherigen Tagen.
8. Gesetzt wird nur der Tag der Genannten; ihre übrigen Tage und jede andere Zeile bleiben; wer danach an allen Tagen steht, heißt „alle Tage“.
9. Eine Kolonne bringt ihre Mitglieder ohne „nicht zeigen“ und ihre aktiven Geräte; schlägt sie niemanden vor, 422.
10. Gefragt wird nur bei Warnungen, die die Aktion neu bringt (eine neue oder ein neuer Tag einer bestehenden); was vorher schon da war, fragt nicht; eine
    Rückfrage für alle; Hinweise nie.
11. Ein geschlossener Auftrag bekommt keinen Tag, auch nicht dazu (409).
12. Unter der Sperre der Arbeitsvorbereitung des Auftrags; Sperren, Rolle, Zugehörigkeit und Event-Loop bekommen mit Punkt 3 (1.9.269) eigene Tests und
    Gegenproben.

#### Tests und Prüfung 1.9.267

Neu: `tests/test_v667_tag_setzen.py` (dazu, Normalform, verlängert über das Wochenende mit der Falle, nach vorn, der vordere zuerst, neu ohne Anschluss, Kolonne
neu mit Mitgliedern und Geräten, Gerät setzen; Antwort 6 mit Karte und Vorschlag, Antwort 8 mit Kran -- auch ein gemischter Auftrag --, Kolonne ohne „nicht
zeigen“, Kolonne ohne Vorschlag; neue Warnung fragt und nichts bleibt, Bestehendes fragt nicht, neuer Tag fragt, abwesend fragt und Antrag nicht, eine Rückfrage für
die Kolonne; Prüfen schreibt nichts; API mit 200, 409, 404, 422; geschlossener Auftrag). `tests/test_v373_zugehoerigkeit_struktur.py`: `order_id` (FREI,
`tag_aktionen._auftrag`) und `slot_id` (GEPRUEFT, `tag_aktionen._karte`) eingetragen -- neue Einträge, keine geänderte Erwartung. Gegenproben: Archiv
`gegenproben-stufe6-r5b.md`. Angepasste Erwartungen: keine.

### Umsetzung 1.9.268 (Punkt 2): Umsetzen, Herausnehmen, Verlängern

Drei Endpunkte in `app/routers/planning.py`, je `POST /api/planning/slots/{slot_id}/…`, ab Büro – Auftrag, `def`; gemeinsam über `_tag_aktion()` (409 Warnung,
409 Rückfrage „niemand mehr“ über `_leer_antwort()` -- auch PUT nutzt sie jetzt --, 409 geschlossen, 404, 422) und `_tag_antwort()` (der Einsatz wie beim
Speichern, beim Umsetzen dazu `quelle`). In `app/tag_aktionen.py`:

- **Umsetzen** (`umsetzen()`; Body: `employee_id` | `resource_id`, `tage`, `ziel_tag`, `ziel_order_id`?, `ziel_slot_id`?, `trotzdem_planen`, `wenn_leer`,
  `pruefen`): die Person bzw. das Gerät steht an allen genannten Tagen am Einsatz (`_an_den_tagen()`, sonst 422); die Tage wandern um gleich viele
  Kalendertage, der erste auf `ziel_tag`. Erst setzen am Ziel (`setzen_offen()`, Regeln von Tag setzen, Karte `ziel_slot_id` nach Antwort 6), dann am alten
  Platz herausnehmen (`_update_slot(…, weg=…)`) -- im selben Einsatz nur die Tage, die sie nicht behält (Do–Fr um einen Tag weiter: Fr–Sa, der Freitag
  bleibt). In einer Transaktion; beide Arbeitsvorbereitungen aufsteigend gesperrt (`_sperren()`). Gefragt wird erst danach -- der alte Platz fragt nicht
  (Zeichnung: „aus seiner Zelle … ohne Rückfrage“), eine neue Warnung am Ziel schon. Wird der Einsatz, aus dem sie kommt, leer: Rückfrage (Antwort 3); im
  selben Einsatz nie -- wer allein steht und einen Tag weiter geht, schließt an (verlängert), danach kürzt der Rand: der Einsatz wandert mit.
- **Herausnehmen** (`herausnehmen()`; `tage` oder `alle`, genau eins): am Rand kürzt der Einsatz, in der Mitte bleibt eine Lücke; ganz leer: Rückfrage,
  `wenn_leer`. Fragt sonst nie (eine Warnung kann nur kürzer werden oder einen anderen ersten Tag nennen).
- **Verlängern** (`verlaengern()`; `ab_tag`): jeder Kalendertag nach `ab_tag` bis zum Ende des Einsatzes kommt zu ihren Tagen (danach in der Normalform);
  ab dem letzten Tag 422; prüft wie Planen.
- **Weniger Tage sind nicht neu** (`neue_warnungen()`): die Warnungen vorher je Schlüssel (Art, Text, wen, anderer Einsatz) mit ihren Tagen; neu ist eine
  Warnung ohne Schlüssel vorher oder mit einem Tag, den sie vorher nicht hatte. Bis 1.9.267 gehörten die Tage zum Schlüssel -- beim Hinzufügen gleichwertig,
  beim Herausnehmen und Umsetzen hätte eine kürzere Warnung als neu gefragt (Fund beim Schreiben der Gegenproben dieser Version).
- Prüfen (`pruefen`) wie bei Tag setzen, dazu `leer` (Umsetzen: der Einsatz, aus dem sie kommt; Herausnehmen: dieser).

#### Festlegungen 1.9.268 (bestätigt am 09.11.2026 -- außer Nr. 7: Verlängern nimmt seit 1.9.272 nur Arbeitstage)

1. Umsetzen: eine Person oder ein Gerät (keine Kolonne) für Tage, an denen sie am Einsatz steht (sonst 422), auf einen Tag an einem Auftrag (leer = derselbe)
   oder eine Karte; erst setzen nach den Regeln von Tag setzen, dann herausnehmen, in einer Transaktion.
2. Die Tage wandern um gleich viele Kalendertage; im selben Einsatz bleiben die Tage, die sie behält.
3. Der alte Platz fragt nicht (geprüft wird nach dem Herausnehmen); eine neue Warnung am Ziel fragt.
4. Weniger Tage machen eine Warnung nicht neu -- für alle Tag-Aktionen (statt der Tage im Schlüssel, 1.9.267 Nr. 10).
5. Wird der Einsatz, aus dem sie kommt, leer: Rückfrage „niemand mehr“ (`wenn_leer`); im selben Einsatz nie -- wer allein einen Tag weiter geht, nimmt den Einsatz
   mit.
6. Herausnehmen: Tage oder alle (genau eins, sonst 422), nur ihre Tage; am Rand kürzt der Einsatz, in der Mitte bleibt eine Lücke; ganz leer: Rückfrage; fragt
   sonst nie.
7. Verlängern: ab einem ihrer Tage jeder Kalendertag bis zum Ende des Einsatzes; ab dem letzten Tag 422; prüft wie Planen. *Geändert mit 1.9.272: nur
   Arbeitstage (Festlegungen 1.9.272 Nr. 1–5).*
8. Antworten: der Einsatz am Ziel, beim Umsetzen auch der, aus dem sie kam (wenn es ihn noch gibt); ihre Tage und der letzte Tag; geprüft dazu „leer“; Prüfen
   schreibt nichts.
9. Beide Arbeitsvorbereitungen aufsteigend gesperrt -- der Beweis unter PostgreSQL mit Punkt 3 (1.9.269).

#### Tests und Prüfung 1.9.268

Neu: `tests/test_v668_umsetzen_herausnehmen.py` (auf einen anderen Auftrag ohne Rückfrage nach dem alten Platz, auf einen anderen Tag im Einsatz, mehrere Tage
überlappend mit der Falle, allein wandert der Einsatz, die Quelle wird leer -- Rückfrage, Prüfen, Behalten, Löschen --, auf eine Karte, neue Warnung am Ziel
fragt, weniger Tage sind nicht neu, Gerät; Herausnehmen Lücke und Rand, alle und leer, fragt nie, Gerät und Fehler; Verlängern bis zum letzten Tag, prüft wie
Planen; API; Prüfen schreibt nichts). `tests/test_v373_zugehoerigkeit_struktur.py`: `ziel_order_id` (FREI, `tag_aktionen._auftrag`) und `ziel_slot_id`
(GEPRUEFT, `tag_aktionen._karte`) eingetragen. Gegenproben: Archiv `gegenproben-stufe6-r5b.md`. Angepasste Erwartungen: keine.

### Umsetzung 1.9.269 (Punkt 3): Sperren, Zugehörigkeit, Rolle, Teil-Update, Event-Loop, Rückgängig

- **Sperren** (`app/tag_aktionen.py::_sperren()`): jede Tag-Aktion sperrt die Arbeitsvorbereitungen, die sie berührt, aufsteigend nach ID (Umsetzen: die
  des alten und die des neuen Auftrags; Rückgängig: die aller Schritte); `_update_slot()` sperrt danach dieselbe Zeile noch einmal (in derselben Transaktion
  ohne Wirkung). Belegt unter PostgreSQL: zwei Umsetzen über Kreuz (Tom von Auftrag 1 nach 2, Kai von 2 nach 1), die erste hält nach ihrer ersten Sperre an,
  die zweite startet, länger als `deadlock_timeout` gewartet -- beide gelingen nacheinander; in der Reihenfolge der Anfrage bräche PostgreSQL eine mit einem
  Deadlock ab (Gegenprobe).
- **Zugehörigkeit** (Regel 25, `tests/test_v373_zugehoerigkeit_struktur.py`): Auftrag (`_auftrag()`, FREI) und Karte (`_karte()`, GEPRUEFT: ein Einsatz dieses
  Auftrags) bei Tag setzen und Umsetzen; der Einsatz im Pfad und in jedem Schritt von Rückgängig (`_einsatz()`, unbekannt 404); Person bzw. Gerät muss an
  den genannten Tagen am Einsatz stehen (`_an_den_tagen()`, `_tage_aendern()`: 422). Person, Kolonne und Gerät sind Stammdaten (`STAMMDATEN`).
- **Rolle**: alle fünf Endpunkte ab Büro – Auftrag wie die Tafel (`_role_dep`), die Monteurin 403.
- **Event-Loop** (Regel 35): jeder Endpunkt `def`, Sitzung mit `scope="function"`; die Aktion läuft im Threadpool.
- **Teil-Update**: eine Tag-Aktion schreibt nur die Zeilen der Genannten (`_tage_aendern()`); der Zeitraum ändert sich nur, wo sie ihn braucht (verlängert mit der
  Falle, gekürzt am Rand); Notiz, Status, Stunden, Kolonne und jede andere Zeile bleiben. `dazu`/`weg` gibt es nur intern -- `PUT /api/planning/slots/{id}`
  kennt sie nicht (Schema).
- **Rückgängig** (Befund E: kein Speicher auf dem Server): jede Aktion gibt `umkehrung` zurück -- `{pfad: "/api/planning/rueckgaengig", body: {schritte}}` oder
  leer. Schritte: `weg` (Tage einer Person bzw. eines Geräts heraus; ein dabei leerer Einsatz bleibt „niemand“), `dazu` (Tage zurück in genau diesen Einsatz,
  verlängert mit der Falle), `loeschen` (ein eben angelegter Einsatz mit seinem Stand). Tag setzen: neu -> `loeschen`, sonst je Zeile `weg` der hinzugekommenen
  Tage (eine Kolonne: je Mitglied und Gerät); Umsetzen: erst `dazu` am alten Platz, dann am Ziel `weg` bzw. `loeschen` (neu) -- im selben Einsatz ohne leeren
  Zwischenstand; Herausnehmen: `dazu` der herausgenommenen Tage; Verlängern: `weg` der hinzugekommenen. `rueckgaengig()` führt alle Schritte in einer Transaktion
  aus (geht einer nicht, bleibt keiner) und fragt nie.
- **Antwort 5** (`einsatz_stand()`): eine kurze Prüfsumme aus Zeitraum, Status, Notiz, Art, Kolonne, Personen und Geräten mit Tagen, Stunden und Anfahrt;
  `loeschen` nur bei gleichem Stand, sonst 409 „Der Einsatz wurde seitdem geändert – Rückgängig geht nicht mehr, bitte im Dialog löschen.“ (nichts geändert).
- Kein Rückgängig, wenn die Aktion einen Einsatz gelöscht hat (Löschen in der Rückfrage) oder nichts geändert hat. Eine Arbeitsvorbereitung, die beim Anlegen
  entstand, bleibt nach Rückgängig stehen -- wie nach dem Löschen eines Einsatzes im Dialog.

#### Festlegungen 1.9.269 (bestätigt am 09.11.2026)

1. Jede Tag-Aktion sperrt die Arbeitsvorbereitungen, die sie berührt, aufsteigend nach ID -- zwei Aktionen über Kreuz warten aufeinander (unter PostgreSQL belegt).
2. Rolle: ab Büro – Auftrag wie die Tafel; die Monteurin 403.
3. Zugehörigkeit: Auftrag und Karte wie bei Tag setzen; der Einsatz im Pfad und in den Schritten unbekannt 404; Person bzw. Gerät nur an ihren Tagen (422).
4. Event-Loop: jeder Endpunkt `def`, Sitzung mit `scope="function"`.
5. Teil-Update: eine Tag-Aktion ändert nur die Zeilen der Genannten; Notiz, Status, Stunden, Kolonne und jede andere Zeile bleiben; PUT kennt `dazu`/`weg` nicht.
6. Rückgängig: jede Aktion gibt ihre Umkehrung zurück (Schritte weg | dazu | loeschen), kein Speicher auf dem Server; in einer Transaktion, fragt nie.
7. Ein eben angelegter Einsatz wird beim Rückgängig gelöscht, nur solange er unverändert ist (Stand); sonst 409, nichts geändert (Antwort 5).
8. Kein Rückgängig, wenn die Aktion einen Einsatz gelöscht oder nichts geändert hat.
9. Eine beim Anlegen entstandene Arbeitsvorbereitung bleibt nach Rückgängig.

#### Tests und Prüfung 1.9.269

Neu: `tests/test_v669_sperren_und_rueckgaengig.py` (Rückgängig nach dazu, verlängert -- die Falle wieder „alle Tage“ --, Kolonne, nichts geändert; neu nur
unverändert; Umsetzen in einen bestehenden, im selben Einsatz und in einen neuen; Herausnehmen Mitte, Rand, beides, „niemand“, gelöscht; Verlängern; gelöschte
Quelle; eine Transaktion und fragt nie; Schritte prüfen; Rolle; Event-Loop; Teil-Update; Sperren aufsteigend unter SQLite; über Kreuz unter PostgreSQL).
`tests/test_v373_zugehoerigkeit_struktur.py`: `schritte.slot_id` (FREI, `tag_aktionen._einsatz`) eingetragen. Gegenproben: Archiv `gegenproben-stufe6-r5b.md`.
Angepasste Erwartungen: keine.

### Umsetzung 1.9.270 (Punkt 4): Ziehen in „Personen“ und „Geräte“

- **Seite** (`planning.html`): ein Balken trägt sein Stück (`einsatzBalken()` -> `von`/`bis`, `balkenHtml()` -> `data-von`/`data-bis`). Beim Fassen merkt sich der
  Zug, ob er nur diese Zeile betrifft (`nurDieseZeile()`: Ansicht „Personen“ und Zeile einer Person oder Ansicht „Geräte“ und Zeile eines Geräts -- nie in
  „Kolonnen“, auch nicht in deren Gerätezeilen), die Person bzw. das Gerät der Zeile und das Stück; der Versatz zählt dann vom ersten Tag des Stücks. Beim
  Loslassen `umsetzenZiehen()` statt `verschieben()`: die Tage der Person bzw. des Geräts im Stück (`personTageIn()`/`geraetTageIn()`), der Tag unter dem Anfang
  -> `POST /api/planning/slots/{id}/umsetzen` mit `genau` und `ziel_slot_id` = derselbe Einsatz; in eine andere Zeile derselben Art dazu `auf_employee_id` bzw.
  `auf_resource_id`; eine Zeile anderer Art oder kein Unterschied -> keine Anfrage. Warnungen fragen zurück (`konfliktFrage()`, „Trotzdem planen“), „niemand mehr“
  ebenso (`leerFrage()`). `verschieben()` (Kolonnen) bleibt unverändert.
- **Server** (`app/tag_aktionen.py`): Umsetzen mit `genau` -- genau der Einsatz `ziel_slot_id` (`_karte(…, genau=True)` prüft nur die Zugehörigkeit, nicht den Tag;
  `ziel_finden(…, fest=…)`: dazu, wenn er alle Tage hat, sonst verlängert mit der Falle); danach kürzt der Rand: steht sie allein, wandert der Einsatz mit (gleiche
  ID, Notiz, Status, Stunden). `auf_employee_id`/`auf_resource_id` (`_auf()`): diese Person bzw. dieses Gerät übernimmt die Tage, dieselbe Art (sonst 422); die
  gezogene verliert alle diese Tage. Rückgängig wie bei jedem Umsetzen.
- Ersetzt für „Personen“ und „Geräte“ die Festlegung 1.9.249 Nr. 3 („in der Zeile einer Person oder eines Geräts nur der Zeitraum“) -- dort verschob das Ziehen
  bis 1.9.269 den ganzen Einsatz. In „Kolonnen“ gilt sie weiter. Kein Test und kein Klicktest zog bisher in diesen Ansichten (`test_v649` prüft `verschieben()`
  und bleibt).

#### Festlegungen 1.9.270 (bestätigt am 09.11.2026)

1. In „Personen“ und „Geräte“ verschiebt Ziehen nur diese Person bzw. dieses Gerät: ihre Tage dieses Balkens um gleich viele Tage, im selben Einsatz (verlängert mit
   der Falle, am Rand gekürzt -- auch weit weg, dann mit Lücke); steht sie allein, wandert der Einsatz mit.
2. In eine andere Zeile derselben Ansicht gezogen übernimmt diese Person bzw. dieses Gerät die Tage (schräg gezogen auch um die Tage versetzt); die gezogene verliert
   sie; Person nur auf Person, Gerät nur auf Gerät.
3. Bringt das eine neue Warnung, fragt die Tafel zurück („Trotzdem planen“); „niemand mehr“ wie bisher.
4. In „Kolonnen“ weiter der ganze Einsatz, auch in ihren Gerätezeilen.
5. Server: Umsetzen mit `genau` (genau dieser Einsatz, Tage außerhalb verlängern ihn) und `auf_employee_id`/`auf_resource_id`.
6. Ein Balken trägt sein Stück; gezogen wird das Stück, auf dem gefasst wurde.

#### Tests und Prüfung 1.9.270

Neu: `tests/test_v670_ziehen_einzeln.py` (eigene Zeile mit der Falle und der Lücke, allein wandert der Einsatz, andere Zeile auch schräg, Gerät auf Gerät, Regeln,
Rückfrage und Rückgängig, API; die Seite schickt Umsetzen -- eigene Zeile, andere Zeile, nichts, andere Art, alle Tage, Gerät --, welche Ansicht einzeln zieht,
Balken mit Stück). Neu: `scripts/klicktest_plantafel_ziehen.py` (37 Prüfungen mit echten Mauseingaben, je 1440 und 1280 px, hell und dunkel: Personen eigene
Zeile, andere Zeile, Rückfrage und „Trotzdem planen“; Geräte eigene Zeile, andere Zeile mit Rückfrage; danach jeder Zug über Rückgängig zurück). In
`tests/test_v373_zugehoerigkeit_struktur.py` `auf_employee_id`/`auf_resource_id` unter `STAMMDATEN`. Gegenproben: Archiv `gegenproben-stufe6-r5b.md`.
Angepasste Erwartungen: keine.

### Stand nach R5b (1.9.265–1.9.270)

Vorweg: die Mitarbeiterliste prüft nicht mehr wie das Formular; „niemand“ meldet keine Kapazität. Die Tag-Aktionen stehen auf dem Server -- Tag setzen (dazu,
verlängert, neu), Umsetzen, Herausnehmen, Verlängern, je mit Prüfen ohne Schreiben und Rückgängig, unter Sperren in fester Reihenfolge. Die Tafel nutzt davon bisher
das Umsetzen beim Ziehen in „Personen“ und „Geräte“. Die Ansicht „Aufträge“ mit Liste, Chips, „nur <Tag>“, „bis … verlängern“ und „Rückgängig“ kommt mit R5c.

## Stufe 6, R5b Nachrunde (ab 1.9.272)

Auftrag vom 09.11.2026, Start 1fc155e (live, Datenbank `b6e4d2a9c731`). Bestätigt: Festlegungen 1.9.265–1.9.270 außer 1.9.268 Nr. 7 (siehe Punkt 1) und
1.9.271 Nr. 1–6. Antworten auf die Fragen aus R5b: 1 ja, nur neue Warnungen fragen; 2 ja, eine Kolonne auf der Karte eines Einsatzes ohne Kolonne bekommt einen
eigenen; 3 ja, weit weg in der eigenen Zeile bleibt es derselbe Einsatz mit Lücke; 4 nein -- Verlängern nimmt nur Arbeitstage (Punkt 1); 5 ja: nach jedem Zug in
„Kolonnen“, „Personen“ und „Geräte“ eine schmale Leiste über der Tafel mit dem Zug und „Rückgängig“, bis zur nächsten Aktion -- kommt mit R5c, jetzt nicht
gebaut. Antworten auf die Fragen zu 1.9.271: 1 Untertitel „N aktiv · M inaktiv“ (Punkt 3); 2 je Gerät reicht; 3 ja (Punkt 4); 4 schaut Tobias selbst nach.
Kleine Runde, je Punkt eine Version: 1 Verlängern nimmt nur Arbeitstage -- Samstag, Sonntag, Feiertag und betriebsfreie Tage nur, wenn jemand ausdrücklich auf
diesen Tag zieht; 2 Nebenbefund R5b (Abschnitt 9 des Berichts): die vier Antwortschemata wie in 1.9.265; 3 Mitarbeiter: Untertitel „N aktiv · M inaktiv“;
4 Stammdaten bei 412 px ohne Überlauf, die Mitarbeitertabelle bei 1440 px ohne Rollen. Punkte 3 und 4: Archiv „Stammdaten und Sidebar“.

### Umsetzung 1.9.272 (Punkt 1): Verlängern nur Arbeitstage

- `app/tag_aktionen.py::verlaengern()`: von den Kalendertagen nach `ab_tag` bis zum Ende des Einsatzes nur die, für die `_arbeitstag()` gilt -- dieselbe Prüfung
  wie „direkt anschließend“ (Antwort 7): `_is_workday()` mit den Wochentagen der Planungsgrundlagen und `_combined_holiday_map()` (gesetzliche Feiertage des
  Bundeslands, wenn eingeschaltet, und die eingetragenen Feier- und betriebsfreien Tage). Sie kommen über `dazu` hinzu wie bisher -- wo sie schon steht, auch an
  einem freien Tag, bleibt sie. Der Zeitraum des Einsatzes ändert sich nicht.
- Kein Kalendertag mehr nach `ab_tag`: 422 wie bisher (`NICHTS_ZU_VERLAENGERN`); nur freie Tage: 422 `KEIN_ARBEITSTAG_MEHR`.
- „bis“ in der Antwort ist der letzte Arbeitstag, der dazukommt (bis 1.9.271 das Ende des Einsatzes -- mit einem freien letzten Tag wären beide verschieden).
- Unverändert: Tag setzen, Umsetzen (die Tage wandern um Kalendertage, 1.9.268 Nr. 2) und die Tage im Dialog -- das sind die Wege, auf denen jemand ausdrücklich
  auf einen Tag gezogen wird. Die Tafel hat für Verlängern noch keinen Knopf (R5c).

#### Festlegungen 1.9.272 (bestätigt am 09.11.2026 -- Nr. 2, zweiter Satz: seit 1.9.276 sind Heiligabend und Silvester keine Arbeitstage)

1. Verlängern nimmt ab einem ihrer Tage jeden **Arbeitstag** bis zum Ende des Einsatzes; Samstag, Sonntag, Feiertag und betriebsfreie Tage nicht (statt 1.9.268
   Nr. 7).
2. Arbeitstag wie bei „direkt anschließend“ (`_arbeitstag()`): ein Wochentag der Planungsgrundlagen (ist dort der Samstag ein Arbeitstag, zählt er), kein
   gesetzlicher Feiertag, kein eingetragener Feier- oder betriebsfreier Tag. Freistellungen des Arbeitszeitkalenders (Heiligabend, Silvester) sind dort
   Arbeitstage -- die Tafel zeigt an ihnen weiter den Hinweis.
3. Auf einen freien Tag kommt sie nur ausdrücklich: Tag setzen, Umsetzen und die Tage im Dialog bleiben, wie sie sind; wo sie schon an einem freien Tag steht,
   bleibt sie dort.
4. Bleiben bis zum Ende nur freie Tage: 422 „Bis zum Ende des Einsatzes kommt kein Arbeitstag mehr – Wochenende, Feiertage und betriebsfreie Tage bitte einzeln
   ziehen.“; ab dem letzten Tag wie bisher.
5. „bis“ in der Antwort ist der letzte Arbeitstag, der dazukommt; der Zeitraum des Einsatzes bleibt.

#### Tests und Prüfung 1.9.272

Neu: `tests/test_v672_verlaengern_arbeitstage.py` (über das Wochenende nur Arbeitstage, gesetzlicher Feiertag und betriebsfreier Tag, ausdrücklich gezogener
Samstag bleibt, Tag setzen auf einen Samstag geht weiter, bis zum Ende nur freie Tage, Gerät, Samstag als Arbeitstag der Planung, Prüfen, API und Rückgängig).
Die Tests von 1.9.268 und 1.9.269 bleiben unverändert grün (ihre Einsätze liegen Mo–Fr). Gegenproben: Archiv `gegenproben-stufe6-r5b.md`, „1.9.272“. Kein
Klicktest ruft Verlängern auf (noch kein Knopf). Angepasste Erwartungen: keine.

### Umsetzung 1.9.273 (Punkt 2): vier Antwortschemata ohne die Prüfung des Formulars

Nebenbefund R5b (Bericht, Abschnitt 9): wie `EmployeeOut` bis 1.9.264 erbten vier Antwortschemata die Prüfung ihres Eingabeschemas -- `EmployeeFunctionOut`
(`validate_group`, Grenzen von Name und Reihenfolge), `EmployeeAbsenceOut` (Kategorie nur urlaub … freizeitausgleich, `validate_dates`), `AccountOut`
(`validate_default_tax_rate`: 19, 7 oder 0) und `IncomingInvoiceItemOut` (`validate_tax_rate`). Steht ein Wert in der Datenbank, den das Formular heute ablehnt,
antwortet die ganze Liste mit 500. Ob das im Bestand vorkommt, ist nicht geprüft (nichts gegen den Server); mit normalen Daten möglich ist es bei den
Abwesenheiten: ein Ausfalltag Schlechtwetter hat die Kategorie „schlechtwetter“ (seit 1.9.170), eine aus dem Altbestand übernommene „unbekannt“ -- beide lehnt das
Muster der Kategorie ab, `GET /api/planning/absences` antwortete Admin und Büro – Finanzen dann mit 500 (Büro – Auftrag bekommt `EmployeeAbsencePlanningOut` ohne
Kategorie). Heute ruft keine Seite diese Liste auf (die Plantafel trägt nur ein und löscht).

- `app/schemas.py`: die vier Antwortschemata erben nicht mehr vom Eingabeschema, sondern von `_felder_ohne_pruefung(<Eingabe>, …)` -- dieselben Felder in derselben
  Reihenfolge, ohne Grenzen und Validatoren; `from_attributes` und die eigenen Felder bleiben. `_felder_ohne_pruefung()` steht dafür vor den Funktionen der
  Mitarbeiter.
- Beim Speichern unverändert: `EmployeeFunctionCreate`, `EmployeeAbsenceCreate`, `AccountCreate`, `IncomingInvoiceItemIn` prüfen wie bisher (422).
- Wächter: kein Antwortschema (Name endet auf `Out`, 253 in `app/schemas.py`) hat einen Validator. Grenzen erben noch acht (`CustomerExtraInfoOut`,
  `CustomerOut`, `OperationalResourceOut`, `PlanningHolidayOut`, `PropertyOut`, `QuoteDocumentMetaOut`, `SettingOptionOut`, `SupplierOut` -- nur Längen und bei
  `SettingOptionOut` die Reihenfolge 0–99999, kein Muster, kein Validator); sie stehen in `BEKANNT`, die Liste darf nur kürzer werden.

#### Festlegungen 1.9.273 (bestätigt am 09.11.2026)

1. Funktion, Abwesenheit, Konto und Position einer Eingangsrechnung antworten mit dem, was gespeichert ist, ohne die Prüfung des Formulars (wie die Mitarbeiter
   seit 1.9.265); Felder und Reihenfolge bleiben.
2. Beim Speichern prüft das Formular wie bisher (422).
3. Kein Antwortschema hat einen Validator; ein neues nimmt `_felder_ohne_pruefung()`. Geerbte Grenzen nur noch bei den acht in `BEKANNT` (darf nur kürzer
   werden).

#### Tests und Prüfung 1.9.273

Neu: `tests/test_v673_antworten_ohne_pruefung.py` (je Schema ohne Prüfung mit allen Feldern; Wächter Validatoren und geerbte Grenzen; je Endpunkt ein
gespeicherter Wert, den das Formular ablehnt -- Funktion mit anderer Gruppe, Abwesenheit „schlechtwetter“ und „unbekannt“ für drei Rollen, Konto mit 16 %,
Position einer Eingangsrechnung mit 16 % in Liste und Rechnung --, dazu je, dass Speichern weiter ablehnt). Gegenproben: Archiv `gegenproben-stufe6-r5b.md`,
„1.9.273“. Klicktests der Seiten, die diese Antworten lesen (Abwesenheit, Einstellungen, Rahmen): siehe Bericht. Angepasste Erwartungen: keine.

## Stufe 6, R5c: Ansicht „Aufträge“ (ab 1.9.276)

Auftrag vom 09.11.2026, Start 35034fd (live, Datenbank `b6e4d2a9c731`). Bestätigt: Festlegungen 1.9.272–1.9.275 (Nachrunde R5b). Antworten auf die Fragen der
Nachrunde: 1 Heiligabend und Silvester beim Verlängern auslassen wie betriebsfreie Tage (Punkt 0a); 2 Weg a -- das Untermenü der Stammdaten unter etwa 1400 px
oben, bei 1280 px brach die E-Mail über sechs Zeilen und die Telefonnummer um (gegen 1.9.275 Nr. 3, Punkt 0c); 3 beide Zahlen bleiben (Untertitel und neben dem
Kästchen); 4 nein -- Verschieben zählt Arbeitstage: Mo–Fr einen Tag weiter wird Di–Fr und der nächste Mo, für Umsetzen und für das Ziehen des ganzen Einsatzes in
„Kolonnen“; freie Tage nur ausdrücklich (Punkt 0b). Maßgeblich: `bildgrundlage/entwurf-stufe6/plantafel-auftraege.html` und `plantafel-auftraege-regeln.html`,
Befund G (R5c) mit den Antworten aus R5a. Vorweg je eine Version 0a, 0b, 0c; dann je Punkt eine Version: 1 Auftragsliste der Woche (alle offenen, eingeplante
oben, Rest wie die Akte, feste Zahl Abfragen) und Zeitraum „1 Woche“ (jede Ansicht merkt sich ihren Zeitraum); 2 Ansicht „Aufträge“ (Zellen mit Chips je
Einsatz, zwei Einsätze zwei Karten untereinander, „niemand“, Liste links mit Wochenleiste, Kurzname am Gerät, Kran mit eigenem Zeichen); 3 Ziehen mit Maus und
Finger (Tag setzen, Umsetzen, Herausnehmen, Anzeige vor dem Loslassen, Rückfrage bei neuer Warnung, danach „nur <Tag>“ mit „bis … verlängern“ und
„Rückgängig“); 4 Leiste „Rückgängig“ in „Kolonnen“, „Personen“ und „Geräte“ (Antwort 5 zu R5b), Klick in einen Tag öffnet den Dialog für diesen Tag.

### Umsetzung 1.9.276 (Punkt 0a): Heiligabend und Silvester keine Arbeitstage

- `app/arbeitszeitkalender.py::im_kalender(liste, tag)`: liegt an dem Tag ein aktiver Kalendertag (Datum und Wochentag wie `_datum_passt()`, ohne Gruppe und
  Sollzeit)?
- `app/tag_aktionen.py::_arbeitstag()`: ein Tag ist Arbeitstag der Planung, wenn er ein Wochentag der Planungsgrundlagen ist, kein Feiertag oder betriebsfreier
  Tag (`_combined_holiday_map()`) und -- neu -- kein aktiver Tag des Arbeitszeitkalenders. Eine Funktion für alles, was die Planung in Arbeitstagen zählt:
  Verlängern (1.9.272), „direkt anschließend“ beim Tag setzen (Antwort 7) und ab 1.9.277 das Verschieben.
- Für alle: auf der Plantafel gilt der Kalendertag wie ein betriebsfreier Tag für jede Person und jedes Gerät -- im Lohn gilt er weiter nur, wer an dem Tag
  Sollzeit hat und zur Gruppe gehört (unverändert, `kalendertage_im_zeitraum()`); auch der Hinweis „Freistellung“ der Tafel bleibt, wie er war.

#### Festlegungen 1.9.276 (bestätigt am 09.11.2026)

1. Ein aktiver Tag des Arbeitszeitkalenders (Heiligabend, Silvester) ist auf der Plantafel kein Arbeitstag -- wie ein betriebsfreier Tag, für alle Personen und
   Geräte; Gruppe und Sollzeit spielen dafür keine Rolle (statt 1.9.272 Nr. 2, zweiter Satz).
2. Das gilt überall, wo die Planung Arbeitstage zählt: Verlängern, „direkt anschließend“ beim Tag setzen, ab 1.9.277 Verschieben.
3. Ein abgeschalteter (inaktiver) Kalendertag ist wieder ein Arbeitstag.

#### Tests und Prüfung 1.9.276

Neu: `tests/test_v676_kalendertage_kein_arbeitstag.py` (Verlängern 21.–31.12. ohne 24. und 31.12., Gerät ebenso, Tag setzen am 28.12. verlängert den Einsatz bis
23.12., abgeschaltet wieder Arbeitstag). Gegenproben: Archiv `gegenproben-stufe6-r5c.md`. Angepasste Erwartungen: keine.

### Umsetzung 1.9.277 (Punkt 0b): Verschieben in Arbeitstagen

Antwort 4 zur Nachrunde R5b: „Verschieben zählt Arbeitstage -- Mo–Fr einen Tag weiter wird Di–Fr und der nächste Mo; gilt für Umsetzen und für das Ziehen des
ganzen Einsatzes in „Kolonnen“. Freie Tage nur ausdrücklich.“

- `app/tag_aktionen.py::verschiebung(von, auf, arbeitstag)`: die Abbildung der Tage, wenn `von` auf `auf` gezogen wird -- `von` landet auf `auf` (dort losgelassen,
  auch ein freier Tag), jeder spätere Tag behält seinen Abstand in Arbeitstagen zu `von` (Zahl der Arbeitstage nach `von` bis zu ihm) und landet auf dem
  entsprechenden Arbeitstag nach `auf`. Ein freier Tag, an dem jemand stand, hat denselben Abstand wie der Arbeitstag davor und geht in dessen Abbild auf. Ohne
  Verschiebung (`auf == von`) bleibt alles, auch ein freier Tag. Arbeitstag = `_arbeitstag()` (Planungsgrundlagen, Feiertage, betriebsfreie Tage, seit 1.9.276
  der Arbeitszeitkalender); `_arbeitstag_fuer()` holt die Feiertage weit genug nach beiden Enden.
- Umsetzen (`umsetzen()`): die Zieltage sind die Abbilder (bis 1.9.276 gleich viele Kalendertage weiter) -- in „Personen“ und „Geräte“ beim Ziehen, aus einer Zelle
  der Ansicht „Aufträge“ (Punkt 3).
- Den ganzen Einsatz ziehen (`verschieben()`, `POST /api/planning/slots/{id}/verschieben` mit `auf` und `team_id` nur, wenn gesendet; die Tafel ruft es aus
  `verschieben()` in „Kolonnen“, bis 1.9.276 PUT mit Beginn und Ende): `_update_slot(…, tage_abbild=abbild)` setzt Beginn `auf` und Ende = Abbild des letzten Tags
  und gibt jeder Zeile die Abbilder ihrer bisherigen Tage (`_tage_abbilden()`; wer neu dazukommt, weil die Kolonne wechselt, die Abbilder aller Tage) -- in der
  Normalform: „alle Tage“ nur, wenn sie danach an allen Tagen des Einsatzes stehen; sonst einzelne Tage, ein Wochenende dazwischen bleibt frei („niemand“, in
  „Kolonnen“ eine Lücke). Es fragt wie bisher bei jeder Warnung des Einsatzes (`_warnungen_pruefen()`; die Tag-Aktionen fragen nur bei neuen, 1.9.267 Nr. 10,
  bestätigt mit der Unterscheidung in Frage 1 zu R5b). Rückgängig: Schritt „zurueck“ mit dem Stand danach (`einsatz_stand()`) und Zeitraum, Kolonne, Personen und
  Geräten mit Tagen von vorher (`_zuruecksetzen()`, ohne Prüfung der Personen) -- nur solange der Einsatz unverändert ist, sonst 409.
- Unverändert: Beginn und Ende im Dialog (PUT) in Kalendertagen (`_tage_mitnehmen()`), Tag setzen (ein Tag, ausdrücklich), Verlängern (1.9.272).

#### Festlegungen 1.9.277 (bestätigt am 09.11.2026)

1. Verschieben zählt Arbeitstage: der erste Tag landet auf dem Tag, auf dem losgelassen wird, jeder weitere behält seinen Abstand in Arbeitstagen (Mo–Fr einen Tag
   weiter: Di–Fr und der nächste Mo) -- für Umsetzen und das Ziehen des ganzen Einsatzes.
2. Freie Tage nur ausdrücklich: der Tag, auf dem losgelassen wird, darf frei sein; ein freier Tag, an dem jemand stand, geht im Arbeitstag davor auf.
3. Ganzer Einsatz: jede Person und jedes Gerät bekommt die Abbilder ihrer Tage; „alle Tage“ nur, wenn sie danach an allen Tagen stehen, sonst einzelne Tage; eine
   andere Kolonne bringt ihre Mitglieder an die Abbilder aller Tage.
4. Das Ziehen des ganzen Einsatzes geht über `POST …/verschieben`, fragt wie bisher bei jeder Warnung des Einsatzes, Prüfen schreibt nichts; Rückgängig stellt
   Zeitraum, Kolonne, Personen und Geräte wieder her, nur solange der Einsatz unverändert ist (409).
5. Beginn und Ende im Dialog bleiben Kalendertage.

#### Tests und Prüfung 1.9.277

Neu: `tests/test_v677_verschieben_in_arbeitstagen.py` (die Abbildung vor und zurück, freier Zieltag, freier Tag geht auf; Umsetzen von Person und Gerät; ganzer
Einsatz Mo–Fr, einzelne Tage, Wochenende im Einsatz, freier Zieltag, andere Kolonne, fragt bei jeder Warnung und Prüfen, Rückgängig und 409, Dialog in
Kalendertagen; API mit Prüfen, 404, Kran mit Kolonne 422, Monteurin 403, def und Sitzung). Gegenproben: Archiv `gegenproben-stufe6-r5c.md`.
**Angepasste Erwartungen** (Regel 28):
- `tests/test_v668_umsetzen_herausnehmen.py::test_umsetzen_mehrerer_tage_ueberlappend_mit_der_falle`: alt Do–Fr einen Tag weiter = Fr, Sa (Einsatz bis Sa), neu Fr
  und der nächste Mo (Einsatz bis Mo).
- `tests/test_v670_ziehen_einzeln.py::test_geraet_auf_geraet`: ebenso, alt Fr, Sa, neu Fr, Mo.
- `tests/test_v649_plantafel_bedienen.py::test_ziehen_je_zielzeile`: alt je Zug PUT `/api/planning/slots/{id}` mit Beginn und Ende, neu POST `…/verschieben` mit dem
  neuen ersten Tag (`auf`) und der Kolonne wie bisher.
- `tests/test_v399_teil_updates_rest.py::test_plantafel_verschieben_schickt_nur_team_und_zeitraum`: alt PUT mit Kolonne, Beginn, Ende und danach 14.–18.10., neu
  POST `…/verschieben` mit Kolonne und `auf` und danach 14.–20.10. (Mo–Fr auf Mi: Mi–Fr, Mo, Di); Status, Notiz, Stunden bleiben wie bisher.

### Umsetzung 1.9.279 (Punkt 1): Auftragsliste der Woche und „1 Woche“

- `app/auftragsliste.py::auftragsliste(db, start, ende)` (höchstens 63 Tage), `GET /api/planning/auftragsliste?start&end` (ab Büro – Auftrag wie die Tafel): je
  offenem Auftrag (läuft, pausiert) Nummer, Projekt (Nummer, Name), Kunde, Status, `eingeplant` (ein Einsatz berührt den Zeitraum), `erster_tag` (sein erster Tag im
  Zeitraum), `naechster_einsatz` (der erste Einsatz nach dem Zeitraum), Soll, gebucht, `stunden` (Text) und `zusatz` (Liste). Reihenfolge: eingeplant oben nach
  `erster_tag`, dann Nummer; darunter nach Nummer.
- Stunden (`stunden_zeile()`, Antwort 10, in dieser Reihenfolge): eine Kranvermietung -- ein Einsatz der Art „kranvermietung“ -- „Kran mit Bediener“ (eine Person an
  einem solchen Einsatz) bzw. „Kran ohne Bediener“; aus einem Wartungsvertrag (`ProjectProfile.source_maintenance_contract_id`) „Wartungsvertrag“; ohne Soll „nach
  Aufwand“; nichts gebucht „Soll …“; sonst „Rest …“ (Soll minus gebuchte Baustelle & Werkstatt wie die Akte, `app/akte.py`), darüber „… über Soll“.
- Zusatz: eingeplant und ein Einsatz im Zeitraum vorläufig -> „vorläufig“; nicht eingeplant -> „ab <Tag>“ (nächster Einsatz) oder „ohne Termin“; „pausiert“.
- Abfragen: Aufträge (mit Projekt, Positionen und Kalkulation über selectinload), gebuchte Stunden je Auftrag, Einsätze im Zeitraum, nächster Einsatz je Auftrag,
  Kranvermietungen mit Bedienern, Herkunft Wartungsvertrag -- je eine, die offenen Aufträge als Unterabfrage; die Zahl hängt nicht an Aufträgen und Einsätzen.
- Tafel: „1 Woche“ in der Auswahl; `zeitraumGemerkt(view)`/`zeitraumMerken()` merken den Zeitraum je Ansicht im Browser (`localStorage` `plantafel_zeitraum`, JSON je
  Ansicht; ohne Speicher die Vorgabe: „Aufträge“ 7, sonst 14 Tage, Antwort 15). Wechselt die Ansicht, gilt ihr Zeitraum; die gezeigte Woche (`periodStart`) bleibt;
  ändert sich die Zahl der Tage, lädt die Tafel neu, sonst zeichnet sie nur. Die Auftragsliste lädt nur die Ansicht „Aufträge“ (ab 1.9.280).

#### Festlegungen 1.9.279 (bestätigt am 09.11.2026)

1. Zeilen: alle offenen Aufträge (läuft, pausiert); mit Einsatz im Zeitraum oben nach ihrem ersten Tag im Zeitraum, dann nach Nummer; darunter die übrigen nach
   Nummer; abgeschlossene und stornierte nicht.
2. Stunden wie die Akte: „Soll …“, solange nichts gebucht ist, dann „Rest …“ (Soll minus gebuchte Baustelle & Werkstatt), darüber „… über Soll“; Vorrang
   Kranvermietung („Kran mit/ohne Bediener“), dann Wartungsvertrag, dann „nach Aufwand“ (ohne Soll).
3. Zusatz: „vorläufig“, wenn ein Einsatz im Zeitraum vorläufig ist; ohne Einsatz im Zeitraum „ab <nächster Einsatz>“ oder „ohne Termin“; „pausiert“.
4. Eine feste Zahl Abfragen; eigener Endpunkt, nur die Ansicht „Aufträge“ lädt ihn; ab Büro – Auftrag; höchstens 63 Tage.
5. „1 Woche“ in der Auswahl; jede Ansicht merkt sich ihren Zeitraum im Browser („Aufträge“ 1 Woche, sonst 2 Wochen); die gezeigte Woche bleibt beim Wechsel; ein
   anderer Zeitraum lädt neu.

#### Tests und Prüfung 1.9.279

Neu: `tests/test_v679_auftragsliste.py` (Text der Stunden, Auswahl und Reihenfolge, Stunden wie die Akte mit Fahrzeit und laufender Buchung, vorläufig und pausiert,
Kran und Wartungsvertrag, feste Zahl Abfragen bei 2 und 10 Aufträgen, API mit 63 Tagen und Monteurin 403; in node mit dem Code der Seite: Vorgaben, Merken je
Ansicht, unbekannter Wert und ohne Speicher, Laden nur bei anderer Zahl der Tage; die Auswahl am Text). Gegenproben: Archiv `gegenproben-stufe6-r5c.md`, „1.9.279“.
**Angepasste Erwartungen** (Regel 28): `tests/test_v647_plantafel_tafel.py::test_seitenkopf_mit_einsatz_und_menue`: alt die Auswahl 14/21/28, neu 7/14/21/28. `tests/test_v447_auswahl_altwerte.py`: `KLASSEN` um `('planning.html', 'P2', 'rangeDays')` mit Klasse „neu“ ergänzt
(der Zeitraum der Ansicht kommt jetzt aus dem Browser, nur Werte der Liste über `zeitraumGemerkt()` -- kein gespeicherter Wert); der Wächter fand die Zuweisung im
ersten Lauf vor dem Commit.

### Umsetzung 1.9.280 (Punkt 2): Ansicht „Aufträge“, Kurzname am Gerät

- Reiter „Aufträge“ (`view==='auftraege'`, vierter Knopf der Leiste): die Tafel zeichnet `auftraegeHtml()` -- je Zeile der Auftragsliste (1.9.279, nur diese Ansicht
  lädt sie: `ladeAuftragsliste()` in `loadBoard()` und `setView()`) der Name als Link auf die Akte (`/projects/<Projekt>?auftrag=<Auftrag>`), Nummer und Kunde, Stunden
  und Zusatz; Abschnitte „Eingeplant in <Woche>“ und „Offen, ohne Einsatz in <Woche>“.
- Zelle je Tag (`td.a-tag` mit `data-date`, `data-auftrag`): je Einsatz des Auftrags an dem Tag eine Karte (`karteHtml()`; Klassen `vorlaeufig`, `kran`, `niemand`), zwei
  Einsätze untereinander; Chips der Personen (`personenAm()`) und Geräte (`geraeteAm()`) dieses Tags, am Gerät der Kurzname, am Kran `KRANZEICHEN`; ein Tag ohne Person und
  Gerät „niemand“. ⚠ bzw. Hinweispunkt nur am Chip, dessen Konflikt diesen Tag trifft (`konflikteAm()` über `imStueck()`). Ab 2 Wochen Chips mit zwei Buchstaben, der
  Name im title (`chipName()`). Ein Klick auf die Karte öffnet ihren Einsatz (`aktion('auftragKarte')`).
- Links „Zum Einplanen“ (`zumEinplanenHtml()`): Kolonnen mit Mitgliedern und Geräten, Personen, Geräte, je mit Wochenleiste der Arbeitstage (`personZustand()`,
  `geraetZustand()`: eingeplant, frei, beantragt, abwesend -- ohne Art, Antwort 13 --, doppelt), Legende darunter; die Zahl „Nicht eingeplant“ entfällt dort.
- Filter „Warnungen · Hinweise“: nur Aufträge mit einem Einsatz mit Warnung oder Hinweis im Zeitraum.
- Kurzname: `operational_resources.kurzname` VARCHAR(30), leer = der Name, beim Speichern ohne Leerzeichen am Rand; Stammdaten-Formular „Kurzname auf der Plantafel“;
  `GET /api/planning` liefert je Gerät `kurzname` und `kran` (`app/planning.py::ist_kran()`: der Typ enthält „Kran“, auch „Autokran“); in der Änderungshistorie
  „Kurzname auf der Plantafel“ (`app/audit.py::FIELD_LABELS`).
- Ecken (v460): der Einsatz im Tag (`.a-einsatz`, 8 px wie der Balken der Zeichnung) ist ein Tafelteil, der Chip (`.chip`) ein Kennzeichen -- bis zum ersten
  vollen Lauf hieß die Karte `.a-karte`, und v460 verlangte für einen Namen mit „karte“ die Ecke der Karte (12 px).

#### Festlegungen 1.9.280 (bestätigt am 09.11.2026)

1. Kurzname am Gerät: eigene Spalte, höchstens 30 Zeichen, leer = der Name, Leerzeichen am Rand weg; im Stammdaten-Formular; `PUT /api/resources/{id}` ist ein
   Teil-Update.
2. Kran am Typ erkannt (enthält „Kran“), eigenes Zeichen am Chip -- in der Zelle und in der Liste.
3. „Aufträge“ ist der vierte Reiter; nur diese Ansicht lädt die Auftragsliste; der Name öffnet die Akte; Abschnitte „Eingeplant in …“ und „Offen, ohne Einsatz in …“.
4. Je Einsatz eine Karte (fest, vorläufig, Kran), zwei Einsätze zwei Karten untereinander; Chips nur der Personen und Geräte dieses Tags; ein Tag ohne jemanden
   „niemand“; Klick auf die Karte öffnet den Einsatz.
5. ⚠ und Hinweispunkt nur am betroffenen Chip und Tag.
6. Ab 2 Wochen schmalere Chips (zwei Buchstaben), der Name im title.
7. Links „Zum Einplanen“ mit Wochenleiste: eingeplant, frei, beantragt, abwesend (ohne Art), doppelt.
8. Der Filter „Warnungen · Hinweise“ zeigt nur Aufträge mit Warnung oder Hinweis.
9. Migration `c3e9f1a7b285`: Spalte dazu, bestehende Geräte ohne Kurznamen; downgrade entfernt sie.

#### Tests und Prüfung 1.9.280

Neu: `tests/test_v680_ansicht_auftraege.py` (Kurzname als Teil-Update mit Grenze, Kran am Typ, Tafel mit `kurzname`/`kran`, Formular, Migration unter SQLite und
PostgreSQL mit Bestand; in node mit dem Code der Seite: Karte mit Chips am Tag, vorläufig und Kran mit Hinweis, schmale Chips, Wochenleiste; Reiter, Legende, Laden nur
in „Aufträge“), Klicktest `scripts/klicktest_plantafel_auftraege.py` (Daten wie die Zeichnung, Zeilen, Zellen, Liste, Klick auf die Karte, 2 Wochen, Filter, Bilder
bei 1440 und 1280 px hell und dunkel). Gegenproben: Archiv `gegenproben-stufe6-r5c.md`, „1.9.280“.
**Angepasste Erwartungen** (Regel 28): `tests/test_v647_plantafel_tafel.py::test_seitenkopf_mit_einsatz_und_menue`: alt drei Reiter (Kolonnen, Personen, Geräte), neu
vier (dazu „Aufträge“). `tests/test_v329_update_handler_struktur.py`: `BEKANNT` ohne `PUT /api/resources/{resource_id}` (58 -> 57, darf nur kürzer werden).
`tests/test_v460_ecken_der_karten.py`: `NICHT_KARTEN` um `a-einsatz` (Tafelteil) und `chip` (Kennzeichen) ergänzt -- neue Einträge, keine geänderte Regel.
`scripts/klicktest_plantafel_tafel.py`, Prüfung „Legende: acht Einträge“: alt jedes `.legende > span` ohne `hidden`, neu nur die sichtbaren (die Seite hat seit
1.9.280 eine zweite Legende für „Aufträge“, in den übrigen Ansichten per CSS versteckt) -- nur der Aufbau, die acht Einträge bleiben; rot im ersten Lauf der
Klicktests vor dem Commit.
Gefunden im ersten vollen Lauf vor dem Commit: v460 (siehe oben), v436 und v438 (der Feldname „Kurzname“ fehlte in `FIELD_LABELS`) und v558 (der Klicktest
maß die Breite gegen `innerWidth`, jetzt `tab.ueberlauf()`).

### Umsetzung 1.9.281 (Punkt 3): Ziehen in „Aufträge“ mit Maus und Finger

- Pointer Events am Layout (`chipZiehenEinrichten()`, einmal je Seite): `pointerdown` auf einem Chip mit `data-art` merkt den Zug (`azug`: Art, ID, Einsatz und Tag
  der Zelle, Name), ab 6 px Bewegung schwebt eine Kopie über dem Zeiger (`.zug-geist`), `pointerup` führt aus (`zugAusfuehren()`), ohne Bewegung ist es Antippen
  (`chipMenue()`), `pointercancel` und Escape brechen ab. `chipTipp` hält den Klick, der nach dem Antippen auf der Karte ankommt, vom Öffnen des Einsatzes ab.
- Ziel (`zielAnPunkt()`): die Liste (`#backlog`) oder eine Zelle `td.a-tag` mit Tag, Auftrag und -- wenn der Zeiger auf einer Karte steht -- dem Einsatz.
- Aus der Liste: `POST /api/planning/tag-setzen` mit `order_id`, `tag`, `employee_id` | `team_id` | `resource_id` (`FELD`), auf einer Karte `slot_id` (Antwort 6).
  Aus einer Zelle: `POST /api/planning/slots/{id}/umsetzen` mit `tage` = [Tag der Zelle], `ziel_tag`, `ziel_order_id`, auf einer Karte `ziel_slot_id`; dieselbe Zelle
  und derselbe Einsatz: nichts. Auf die Liste: `POST …/herausnehmen` mit `tage`; angetippt zusätzlich `alle`.
- Anzeige (`zugAnzeige()`, nur aus `board`): Person abwesend (genehmigt) -> „Abwesend – Rückfrage „Trotzdem planen““; an einem anderen Einsatz eines anderen Auftrags an
  dem Tag (`schonWoanders()`, ohne den Einsatz, aus dem sie kommt) -> „Schon woanders: <Projekte> – Rückfrage „Trotzdem planen““, ebenso ein Gerät; Antrag offen ->
  „Antrag offen – plant ohne Rückfrage“; sonst „Frei – <Tag>“. Kolonne: „Ganze Kolonne – <Tag>“ bzw. „Ganze Kolonne – <Vornamen> schon woanders: Rückfrage für
  alle“. Die Zelle trägt `zug-ziel` und `zug-frei` | `zug-woanders` | `zug-antrag`, darunter der Text (`.zug-anzeige`); kommt der Chip aus einer Zelle, ist die Liste als
  Ziel umrandet (`zug-ziel-liste`).
- Senden (`zugSenden(url, body, fertig)`): über `speichern('tafel', …)`; 409 mit Warnungen -> Konflikt-Dialog, „niemand mehr“ -> Löschen | Behalten; jede Antwort
  kommt zu den bisherigen dazu (`versuch({...opt, …})`), sonst die Meldung im Status. Nach dem Erfolg `fertig(Antwort)` -- hier `merkeZug()`, die Antwort bleibt für
  die Leiste --, danach `loadBoard()`.
- Danach (`zugNachZeigen()` nach jedem Zeichnen, `letzterZug`): am Chip „<Name> · nur <Tage>“ bzw. „alle Tage“, je weiterem Tag Mo–Fr des Einsatzes danach der Zustand
  (`personZustand()`/`geraetZustand()`), „bis <Ende> verlängern“ (`POST …/verlaengern` ab dem letzten Tag, nur mit Tagen danach und nicht nach dem Verlängern),
  „Rückgängig“ (`POST` der Umkehrung aus der Antwort, nur mit Umkehrung, danach nichts mehr); herausgenommen „<Tag> herausgenommen“ bzw. „an allen Tagen
  herausgenommen“; Kolonne: Name und Tag. Die Leiste schließt mit dem nächsten Ziehen, dem ×, dem Antippen eines Chips und einer anderen Ansicht.
- Finger: `.ansicht-auftraege .chip[data-art]` mit `touch-action:none` und `user-select:none`, bei `(pointer:coarse)` mindestens 40 px hoch. Der Knopf der Liste heißt
  wie die Liste (`rkKnopfBeschriften()`), unter der Tafel steht je Ansicht ihr Hinweis (`fussTafel`, `fussAuftraege`).
- Bei 1280 px startet die Liste eingeklappt (Regel seit 1.9.257, „solange nichts gemerkt ist“) -- in „Aufträge“ muss sie zum Ziehen erst aufgeklappt werden (Frage im
  Bericht).

#### Festlegungen 1.9.281 (bestätigt am 09.11.2026, außer Nr. 7: Chips 32 statt 40 px, der Treffbereich mit dem Finger größer -- seit 1.9.284)

1. Aus der Liste gezogen: Person, Kolonne oder Gerät für diesen Tag an den Auftrag (`tag-setzen`); auf einer Karte genau dieser Einsatz, an einer freien Stelle entscheidet
   der Server (dazu, verlängert, neu und vorläufig).
2. Aus einer Zelle gezogen: diese Person bzw. dieses Gerät für diesen Tag umsetzen (`umsetzen`) -- auf einen anderen Auftrag oder Tag, auf einer Karte in genau diesen
   Einsatz; an den eigenen Platz zurück: nichts.
3. Herausnehmen: auf die Liste gezogen für diesen Tag; angetippt eine Leiste „Für diesen Tag herausnehmen“, „An allen Tagen herausnehmen“, „Einsatz öffnen“ -- das
   Antippen öffnet den Einsatz nicht, ein Klick neben die Chips weiter.
4. Vor dem Loslassen zeigt die Zelle aus den geladenen Daten, ohne Anfrage: „Frei – <Tag>“, „Schon woanders: … – Rückfrage „Trotzdem planen““ (auch am Gerät),
   „Antrag offen – plant ohne Rückfrage“, „Abwesend – Rückfrage …“, „Ganze Kolonne – <Tag>“ bzw. „… schon woanders: Rückfrage für alle“; der Einsatz, aus dem gezogen
   wird, zählt nicht als „woanders“; die Liste ist als Ziel umrandet, wenn der Chip aus einer Zelle kommt.
5. Beim Loslassen prüft der Server (nur neue Warnungen fragen, „niemand mehr“ fragt Löschen | Behalten); mehrere Rückfragen nacheinander, die Antworten gelten zusammen.
6. Danach am Chip „<Name> · nur <Tage>“ (bzw. „alle Tage“), je weiterem Tag Mo–Fr des Einsatzes danach der Zustand, „bis <Ende> verlängern“ (nur mit Tagen danach,
   nicht nach dem Verlängern) und „Rückgängig“ (nur mit Umkehrung, einmal); nach dem Herausnehmen „<Tag> herausgenommen“ bzw. „an allen Tagen herausgenommen“; nach einer
   Kolonne ihr Name und der Tag; bis zur nächsten Aktion.
7. Maus und Finger über Pointer Events wie R4: Chips mit `touch-action:none`, ohne Textauswahl, bei grobem Zeiger mindestens 40 px hoch; Escape bricht ab; die Kopie des
   Chips schwebt über dem Zeiger.
8. Der Knopf der Liste heißt wie die Liste („Zum Einplanen aufklappen“); unter der Tafel steht in „Aufträge“ ein eigener Hinweis zu Karten und Chips.

#### Tests und Prüfung 1.9.281

Neu: `tests/test_v681_ziehen_auftraege.py` (in node mit dem Code der Seite: die Anzeige für frei, schon woanders -- auch aus der eigenen Zelle mit einem weiteren
Einsatz --, Antrag, abwesend, Gerät, Kolonne; was beim Loslassen hinausgeht für Liste, Zelle, eigenen Platz und Liste als Ziel; Rückfragen nacheinander; danach
verlängern, Rückgängig nur mit Umkehrung und einmal; Aufbau: Finger, Pointer Events, Escape, Knopf und Hinweis je Ansicht), Klicktest
`scripts/klicktest_plantafel_auftraege_ziehen.py` (Daten wie `klicktest_plantafel_auftraege.py` und die Zeichnung: Antippen und herausnehmen, frei mit „nur Do“ und
verlängern, schon woanders mit Rückfrage, umsetzen ohne Rückfrage, Antrag offen, ganze Kolonne, zurück auf die Liste, Escape; mit dem Finger bei 1280 px dunkel; Bilder).
Gegenproben: Archiv `gegenproben-stufe6-r5c.md`, „1.9.281“.
`tests/test_v460_ecken_der_karten.py`: `zug-leiste` als Karte (Aufklappfläche, Ecke der Karte) eingeordnet -- ein neuer Eintrag.
**Angepasste Erwartungen** (Regel 28): `tests/test_v680_ansicht_auftraege.py::test_reiter_legende_und_laden_nur_in_auftraege`: alt `aktion('auftragKarte',el=>openEdit(…))`
und `renderBacklog();renderFilter();return`, neu mit `chipTipp` und `chipZiehenEinrichten();zugNachZeigen();` (nur der Aufbau, die Aussagen bleiben).

### Umsetzung 1.9.282 (Punkt 4): Leiste „Rückgängig“ über der Tafel, Klick in einen freien Tag

- `<div class="zug-band" id="zugBand" role="status" hidden>` über dem Layout der Tafel. `bandZeigen(text, umkehrung)` nach dem Erfolg eines Zugs: `verschieben()`
  („<Projekt>: <alter Zeitraum> → <neuer Zeitraum>“, wechselt die Kolonne „· <Kolonne>“ bzw. „· ohne Kolonne“) und `umsetzenZiehen()` (eigene Zeile „<Name> · <Projekt>:
  <Tage> → ab <Tag>“, andere Zeile „<Projekt> <Tage>: <Name> → <Name>“, dazu „, ab <Tag>“, wenn sich der Tag ändert). „Rückgängig“ nur mit Umkehrung in der Antwort
  (`bandZurueck()`: `POST` der Umkehrung, danach neu laden, einmal).
- Bis zur nächsten Aktion: ein Klick außerhalb der Leiste (`click` mit Capture), `setView()` und `movePeriod()` schließen sie (`bandSchliessen()`). Nicht schon
  `pointerdown`: dann verschwände die Leiste beim Greifen des nächsten Balkens, die Tafel rückte mitten im Ziehen um ihre Höhe nach oben und das Ziel unter dem
  Zeiger wäre eine andere Zeile -- so im ersten Lauf vor dem Commit, gefunden von `klicktest_plantafel_ziehen` (zweiter Zug in „Personen“ und „Geräte“ landete
  in der falschen Zeile). Nach einem Zug kommt der Klick erst nach dem Loslassen. In „Aufträge“ gibt es die Leiste nicht (dort die Leiste am Chip, 1.9.281).
- Beide Züge gehen über `zugSenden(url, body, fertig)` (1.9.281): Warnungen und „niemand mehr“ fragen nacheinander, die Antworten gelten zusammen. Bis 1.9.281 hatte
  `umsetzenZiehen()` (seit 1.9.270) eine eigene Schleife, in der nach „Behalten“/„Löschen“ eine Warnung mit 409 nur im Fehlertext des Dialogs landete.
- „Aufträge“: ein Klick auf `#planner` in einer Zelle `td.a-tag`, nicht auf einer Karte, öffnet `openCreate(Auftrag, Tag, null, {bis: Tag})` -- der Dialog für diesen
  Auftrag, nur dieser Tag, ohne Kolonne; Mauszeiger „copy“ über dem Tag, „pointer“ über der Karte; der Hinweis unter der Tafel nennt es.
- Die Leiste ist eine Karte (Ecke der Karte, v460 „zug-band“); mit der Maus (`pointer:fine`) ist ihr Knopf 32 px hoch, mit dem Finger bleibt er 40 px.

#### Festlegungen 1.9.282 (bestätigt am 09.11.2026, außer Nr. 4: Klick in einen freien Tag schlägt die Kolonne vor, wenn der Auftrag an anderen Tagen genau eine hat -- seit 1.9.285)

1. Nach einem Zug in „Kolonnen“, „Personen“ und „Geräte“ eine schmale Leiste über der Tafel mit dem Zug in Worten (Auftrag, Zeitraum bzw. Tage, Person oder Gerät,
   bei einer anderen Zeile „Name → Name“, bei einer anderen Kolonne ihr Name) und „Rückgängig“ -- nur mit Umkehrung in der Antwort, einmal.
2. Die Leiste bleibt bis zur nächsten Aktion: der nächste Klick außerhalb der Leiste (Maus oder Finger), eine andere Ansicht, ein anderer Zeitraum.
3. Beide Züge fragen wie in „Aufträge“: mehrere Rückfragen nacheinander, die Antworten gelten zusammen.
4. In „Aufträge“ öffnet ein Klick in einen freien Teil eines Tags den Dialog für diesen Auftrag und diesen Tag, ohne Kolonne; eine Karte öffnet ihren Einsatz.
5. In „Aufträge“ keine Leiste über der Tafel -- dort steht sie am Chip.

#### Tests und Prüfung 1.9.282

Neu: `tests/test_v682_leiste_rueckgaengig.py` (in node mit dem Code der Seite: Leiste nach dem Verschieben mit Kolonne, ohne Umkehrung ohne „Rückgängig“, Umsetzen in der
eigenen und in einer anderen Zeile, „Rückgängig“ schickt die Umkehrung einmal und schließt, Rückfragen nacheinander beim Ziehen in „Personen“; Aufbau: Leiste, Schließen
mit der nächsten Aktion, Klick in einen freien Tag), Klicktest `scripts/klicktest_plantafel_rueckgaengig.py` (Daten wie `klicktest_plantafel_ziehen.py`: „Kolonnen“,
„Personen“ eigene und andere Zeile mit Rückfrage, Schließen durch einen Klick auf die Seite und durch eine andere Ansicht, „Geräte“, „Aufträge“ freier Tag eines nicht eingeplanten Auftrags und Karte;
Bilder 1440 px hell und 1280 px dunkel); `klicktest_plantafel_auftraege_ziehen.py` prüft dazu, dass in „Aufträge“ keine Leiste über der Tafel erscheint.
Gegenproben: Archiv `gegenproben-stufe6-r5c.md`, „1.9.282“.
**Angepasste Erwartungen** (Regel 28): `tests/test_v649_plantafel_bedienen.py::test_ziehen_je_zielzeile` und `tests/test_v670_ziehen_einzeln.py::test_seite_schickt_umsetzen` -- alt liefen `verschieben()`
bzw. `umsetzenZiehen()` in node mit ihrer eigenen Sende-Schleife, neu brauchen sie `zugSenden()`, `bandZeigen()` und deren Helfer (Funktionsliste und Tafel der Attrappe ergänzt); die
geprüften Anfragen sind unverändert. Ebenso `tests/test_v399_teil_updates_rest.py::test_plantafel_verschieben_schickt_nur_team_und_zeitraum` (Funktionsliste) und
`tests/test_v679_auftragsliste.py::_seite` (`setView()` schließt die Leiste: `bandSchliessen` in der Funktionsliste) -- die geprüften Anfragen bzw. Zahlen unverändert.
`tests/test_v663_leerer_tag.py::test_dialog_und_ziehen_nehmen_die_rueckfrage`: alt `&&!leerFrage(err,wahl=>senden(false,wahl))` und `...(wahl?{wenn_leer:wahl}:{})` (die
eigene Schleife von `umsetzenZiehen()`), neu `!leerFrage(err,wahl=>versuch({...opt,wenn_leer:wahl}))` in `zugSenden()` und der Aufruf aus `umsetzenZiehen()`.
`tests/test_v460_ecken_der_karten.py`: `zug-band` als Karte (Hinweiskasten) eingeordnet -- ein neuer Eintrag.

## Stufe 6, R5d: Nachrunde (ab 1.9.283)

Auftrag vom 09.11.2026, Start 55be423 (live, Datenbank `c3e9f1a7b285`). Bestätigt: Festlegungen 1.9.276–1.9.282, außer 1.9.281 Nr. 7 (Punkt 2) und 1.9.282
Nr. 4 (Punkt 3). Je Punkt eine Version:
1 Frage 1: in „Aufträge“ startet „Zum Einplanen“ immer offen; die Tagesspalten werden schmaler, damit bei 1280 px mit offener Liste nichts seitlich rollt (bis
  1.9.282 war der Freitag abgeschnitten).
2 Frage 2: Chips 32 px hoch, der Treffbereich mit dem Finger größer.
3 Frage 3: Klick in einen freien Tag schlägt die Kolonne vor, wenn der Auftrag an anderen Tagen genau eine hat; sonst ohne.
4 Frage 4: „Ganze Kolonne“ nennt vor dem Loslassen auch Geräte, die schon woanders sind.
5 Die Anzeige vor dem Loslassen schwebt über der Zelle und macht die Zeile nicht höher (bis 1.9.282 wuchs die Zeile beim Ziehen, alles darunter rutschte weg).
6 „Nicht eingeplant“ und „Aufträge“ zeigen die Stunden beide wie die Akte (Kaminverwahrung Schulz: „Soll 0,00 h“ gegen „Soll 6,00 h“).
7 Leiste: neuer Zeitraum statt „ab“; „40 h/Woche“ ohne Umbruch; Untermenü der Stammdaten bei 1280 px in zwei Zeilen statt seitlich rollend.

### Umsetzung 1.9.283 (Punkt 1): „Zum Einplanen“ immer offen, schmalere Tagesspalten

- `setView()`: wechselt die Ansicht nach „Aufträge“, öffnet sie die Liste (`rueckstandZeigen(true, false, false)` -- ohne zu merken, ohne Neuzeichnen, das folgt
  in `setView()`); zurück in eine der übrigen Ansichten gilt wieder `rueckstandStartZu(innerWidth)` (gemerkt „zu“/„offen“, sonst unter 1440 px zu, 1.9.257).
  Der Knopf merkt in „Aufträge“ nichts (`rueckstandZeigen(…, view!=='auftraege')`) -- dort startet die Liste ohnehin offen; zugeklappt bleibt sie bis zum
  nächsten Wechsel in die Ansicht.
- Spalten: gemessen bei 1280 px mit offener Liste 721 px Platz, die Tabelle verlangte bis 1.9.282 mindestens 230 + 5 × 110 + 2 × 26 = 832 px. Jetzt
  `nameW + Arbeitstage × 84 + Wochenende × 26` (2–4 Wochen wie bisher 56 je Tag), `nameW` = 200 unter 1400 px Fensterbreite, sonst 230 (an der Spalte gesetzt).
  Bei 1280 px: Tabelle 721 px, Tage je 94 px; bei 1440 px wie bisher 881 px, Tage 120 px.
- Chips: die Karte ist ein Container (`container-type:inline-size`); unter 93 px Inhalt (`@container (max-width:92px)`) fällt das Gerätezeichen weg
  (`.geraetzeichen`), das Kranzeichen bleibt. Innenabstand der Zelle 4 statt 5 px, der Karte 3 statt 4 px, des Chips 6 statt 7 px -- bei 1280 px passt
  „HS-DK 202“ ohne Zeichen (74 px) in die Karte (75 px); gemessen kein gekürzter Chip bei 1440 und 1280 px.
- 2–4 Wochen bei 1280 px mit offener Liste: die Tabelle rollt weiter in ihrem Rahmen (2 Wochen mindestens 200 + 10 × 56 + 4 × 26 = 864 px).

#### Festlegungen 1.9.283 (bestätigt am 10.11.2026, außer Nr. 5: mit 2–4 Wochen startet die Liste unter 1440 px eingeklappt -- seit 1.9.290)

1. In „Aufträge“ startet „Zum Einplanen“ immer offen; zurück in den übrigen Ansichten gilt wieder deren Zustand (gemerkt, sonst unter 1440 px zu).
2. Auf- und Zuklappen in „Aufträge“ merkt sich nichts; zugeklappt bleibt die Liste bis zum nächsten Wechsel in die Ansicht.
3. Tage mindestens 84 px (1 Woche, bis 1.9.282 110 px), unter 1400 px Fensterbreite die Namensspalte 200 statt 230 px: bei 1280 px mit offener Liste rollt
   nichts (Tage 94 px); bei 1440 px wie bisher.
4. Ist eine Karte zu schmal für Gerätezeichen und Kurzname, fällt nur das Gerätezeichen weg; das Kranzeichen bleibt immer. Innenabstände je 1 px kleiner
   (Zelle 4, Karte 3, Chip 6 px).
5. 2–4 Wochen: wie bisher mindestens 56 px je Tag -- bei 1280 px mit offener Liste rollt die Tabelle dann in ihrem Rahmen.

#### Tests und Prüfung 1.9.283

Neu: `tests/test_v683_auftraege_liste_offen.py` (in node mit dem Code der Seite: Liste beim Wechsel nach „Aufträge“ offen und zurück wie gemerkt -- vier Fälle aus
Breite und Merken --, zugeklappt in „Aufträge“ bleibt bis zum nächsten Wechsel, nichts gemerkt; die übrigen Ansichten unverändert; Aufbau der Spalten und Chips).
`scripts/klicktest_plantafel_auftraege.py` ergänzt: bei 1440 und 1280 px rollt nichts, kein Chip gekürzt, Liste offen; bei 1280 px der Freitag zu sehen, das
Kranzeichen da, Gerätezeichen weg; „Kolonnen“ zu, „Aufträge“ offen, zugeklappt nichts gemerkt, beim nächsten Wechsel wieder offen. Gegenproben: Archiv
`gegenproben-stufe6-r5d.md`, „1.9.283“.
**Angepasste Erwartungen** (Regel 28): `tests/test_v657_rueckstand_unter_1440.py::test_nur_der_knopf_merkt` -- alt `function rueckstandZeigen(offen,merken=true){`
und der Knopf `rueckstandZeigen(…contains('rk-zu'))`, neu mit `zeichnen=true` und `…contains('rk-zu'),view!=='auftraege')` (in „Aufträge“ merkt der Knopf
nichts). `tests/test_v679_auftragsliste.py::_seite` -- die node-Attrappe bekommt `rueckstandZeigen()` und `rueckstandStartZu()` als Platzhalter (`setView()` ruft
sie seit 1.9.283); die geprüften Zahlen unverändert. `scripts/klicktest_plantafel_auftraege_ziehen.py`, Teil „Finger“ (1280 px): alt „Liste eingeklappt, Knopf
„Zum Einplanen aufklappen““ und ein Klick zum Aufklappen, neu „Liste offen, Knopf „Zum Einplanen einklappen““ ohne Klick.

### Umsetzung 1.9.284 (Punkt 2): Chips mit dem Finger 32 px, der Treffbereich größer

- `@media (pointer:coarse)`: `.ansicht-auftraege .chip[data-art]` 32 px hoch (bis 1.9.283 40 px, 1.9.281 Nr. 7), `position:relative`; `::before` unsichtbar mit
  `inset:-5px -3px` -- vom Innenrand gemessen (der Rand ist 1 px), also 4 px über und unter der Außenkante und 2 px zur Seite: 40 px hoch zum Greifen. Gemessen im
  Klicktest: mit `inset:-4px -2px` reichte er nur 3 px über den Chip (2 px darunter; bei 3 px lag dort schon die Karte).
- Zwischen zwei Chip-Zeilen einer Karte mit dem Finger `row-gap:8px` (sonst 4 px): bei 4 px überdeckte der Treffbereich der unteren Zeile den der oberen, der
  später gezeichnete läge obenauf. Zur Seite 4 px Abstand und je 2 px -- die Bereiche berühren sich.
- Der Chip schneidet nicht mehr ab (ohne `overflow:hidden` und `text-overflow`, sonst schnitte er auch sein `::before` ab); der Name steht in
  `<span class="chip-text">` und kürzt dort mit „…“ (`min-width:0`). Der Klicktest der Ansicht misst gekürzte Namen deshalb am Textteil.

#### Festlegungen 1.9.284 (bestätigt am 10.11.2026)

1. Mit dem Finger sind die Chips 32 px hoch (statt 40 px, 1.9.281 Nr. 7); der Treffbereich reicht 4 px darüber und darunter und 2 px zur Seite hinaus
   (40 px), ohne die Karte höher zu machen.
2. Zwischen zwei Chip-Zeilen einer Karte mit dem Finger 8 px Abstand -- die Treffbereiche überdecken sich nicht.
3. Der Name kürzt in einem eigenen Teil des Chips („…“), der Chip selbst schneidet nicht ab.

#### Tests und Prüfung 1.9.284

Neu: `tests/test_v684_chips_finger.py` (Regel mit dem Finger, der Chip schneidet nicht ab, Textteil im Chip -- in node mit dem Code der Seite).
`scripts/klicktest_plantafel_auftraege_ziehen.py`, Teil „Finger“: grober Zeiger, Chip 32 px hoch, 3 px darüber und darunter trifft noch den Chip, 7 px darüber nicht.
Gegenproben: Archiv `gegenproben-stufe6-r5d.md`, „1.9.284“.
**Angepasste Erwartungen** (Regel 28): `tests/test_v681_ziehen_auftraege.py::test_chips_mit_dem_finger_greifbar_ohne_textauswahl` -- alt `min-height:40px;padding:4px 10px`,
neu `min-height:32px;` (Festlegung 1.9.281 Nr. 7 geändert). `scripts/klicktest_plantafel_auftraege_ziehen.py`, Teil „Finger“ -- alt „Chips greifbar (≥ 40 px bei
grobem Zeiger)“, neu die Höhe 32 px und der Treffbereich (oben). `scripts/klicktest_plantafel_auftraege.py`, `PLATZ` -- alt gekürzte Chips am `.chip`, neu am
`.chip-text` (nur der Aufbau).

### Umsetzung 1.9.285 (Punkt 3): Klick in einen freien Tag schlägt die Kolonne vor

- `kolonneDesAuftrags(auftrag)`: die Kolonnen der Einsätze dieses Auftrags in `board.slots` (der geladene Zeitraum; der freie Tag selbst hat keinen Einsatz des
  Auftrags, also sind es seine Einsätze an anderen Tagen), Einsätze ohne Kolonne zählen nicht -- genau eine: ihre ID, sonst `null`.
- Der Klick in einen freien Teil eines Tags (1.9.282) ruft `openCreate(Auftrag, Tag, kolonneDesAuftrags(Auftrag), {bis: Tag})`; der Dialog schlägt dann wie beim
  Anlegen aus einer Kolonnenzeile deren Mitglieder vor. Der Hinweis unter der Tafel nennt es.

#### Festlegungen 1.9.285 (bestätigt am 10.11.2026)

1. Klick in einen freien Tag: hat der Auftrag an anderen Tagen (seine Einsätze im geladenen Zeitraum) genau eine Kolonne, schlägt der Dialog sie vor; keine oder
   mehrere -- ohne Kolonne (statt 1.9.282 Nr. 4).
2. Einsätze ohne Kolonne zählen nicht (eine Kolonne und ein Einsatz ohne Kolonne: die Kolonne).
3. Weiter nur dieser Tag; eine Karte öffnet ihren Einsatz.

#### Tests und Prüfung 1.9.285

Neu: `tests/test_v685_kolonne_beim_klick.py` (in node mit dem Code der Seite: fünf Aufträge -- dieselbe Kolonne zweimal, zwei verschiedene, nur ohne, eine und ohne,
kein Einsatz --, der Handler wörtlich aus der Seite). `scripts/klicktest_plantafel_rueckgaengig.py` ergänzt: Wasserturm am freien Samstag -- Kolonne Nord, nur
Sa. Gegenproben: Archiv `gegenproben-stufe6-r5d.md`, „1.9.285“.
**Angepasste Erwartungen** (Regel 28): `tests/test_v682_leiste_rueckgaengig.py::test_klick_in_einen_freien_tag_in_auftraege` -- alt `openCreate(…,null,{bis:…})`
und der Hinweis „… plant den Auftrag an diesem Tag.“, neu `openCreate(auftrag,…,kolonneDesAuftrags(auftrag),{bis:…})` und „… an diesem Tag (mit seiner Kolonne,
wenn er genau eine hat).“ (Festlegung 1.9.282 Nr. 4 geändert).

### Umsetzung 1.9.286 (Punkt 4): „Ganze Kolonne“ nennt auch Geräte

- `zugAnzeige()` für eine Kolonne: wer schon woanders ist, sind jetzt die Mitglieder (`team.employees`, Vorname) und danach die Geräte der Kolonne
  (`team.resources`, `geraetName()`: der Kurzname, ohne ihn der Name), je über `schonWoanders()` an dem Tag (ein anderer Auftrag). Bis 1.9.285 nur die Mitglieder --
  ein doppeltes Gerät meldete erst die Rückfrage des Servers.

#### Festlegungen 1.9.286 (bestätigt am 10.11.2026)

1. „Ganze Kolonne“ nennt vor dem Loslassen auch die Geräte der Kolonne, die an dem Tag schon woanders stehen.
2. Erst die Personen (Vorname), dann die Geräte (Kurzname wie am Chip, ohne Kurzname der Name).

#### Tests und Prüfung 1.9.286

Neu: `tests/test_v686_ganze_kolonne_geraete.py` (in node mit dem Code der Seite: Person und Gerät, nur ein Gerät ohne Kurzname, nur das Gerät, frei).
Gegenproben: Archiv `gegenproben-stufe6-r5d.md`, „1.9.286“.
**Angepasste Erwartungen** (Regel 28): `scripts/klicktest_plantafel_auftraege_ziehen.py`, „Kolonne: Anzeige“ -- alt „Ganze Kolonne – Kai, Nele schon woanders: …“,
neu „Ganze Kolonne – Kai, Nele, HS-DK 204 schon woanders: …“ (die Pritsche der Kolonne Süd steht am Mo bei der Garage).

### Umsetzung 1.9.287 (Punkt 5): die Anzeige schwebt über der Zelle

- `.zug-anzeige`: `position:absolute`, oberhalb der Zelle (`bottom:calc(100% + 2px)`), so breit wie sie (`left/right:2px`), wächst nach oben, `z-index:5`, mit
  Hintergrund je Zustand und Schatten, ohne Rand, `pointer-events:none` -- die Zeile wird nicht höher, die Chips des Ziels bleiben zu sehen. Bis 1.9.286 stand sie
  im Fluss der Zelle (`margin-top`): die Zeile wuchs beim Ziehen, alles darunter rutschte weg; mit dem Finger rutschte dabei das Ziel unter dem Finger weg.
- `zugZielZeigen()` setzt sie vorn in die Zelle (`prepend`): hinten angehängt war die letzte Karte nicht mehr `:last-child`, ihr `margin-bottom:4px` machte die
  Zeile trotz absoluter Anzeige 4 px höher (beim Bauen gemessen: 77 -> 81 px).
- Die Kopie des gezogenen Chips steht rechts neben dem Zeiger, auf seiner Höhe (`left = x + 16`, `top = y − Höhe/2`); bis 1.9.286 über dem Zeiger -- sie verdeckte
  dann den oberen Teil der Anzeige.
- Mit dem Finger seitlich 6 px Innenabstand wie mit der Maus (1.9.284: 7 px): im Bild mit dem Finger bei 1280 px war „HS-DK 202“ wieder gekürzt. Ein Chip mit ⚠
  braucht 16 px mehr und darf bei 1280 px kürzen; der volle Name steht im title.

#### Festlegungen 1.9.287 (bestätigt am 10.11.2026, außer Nr. 4 zweiter Satz: kein Chip mit Kurzname wird gekürzt, ⚠ als Abzeichen an der Ecke -- seit 1.9.291)

1. Die Anzeige vor dem Loslassen schwebt oberhalb der Zelle, so breit wie sie, und wächst nach oben; die Zeile wird beim Ziehen nicht höher, die Chips des Ziels
   bleiben zu sehen.
2. Die Anzeige fängt keine Zeigerereignisse ab; sie steht vorn in der Zelle.
3. Die Kopie des gezogenen Chips steht rechts neben dem Zeiger, auf seiner Höhe (statt darüber, 1.9.281 Nr. 7).
4. Mit dem Finger seitlich 6 px Innenabstand wie mit der Maus (statt 7 px, 1.9.284 Nr. 1); ein Chip mit ⚠ darf bei 1280 px kürzen (Name im title).

#### Tests und Prüfung 1.9.287

Neu: `tests/test_v687_anzeige_schwebt.py` (Regel der Anzeige, vorn in der Zelle, Kopie neben dem Zeiger, Finger seitlich wie die Maus).
`scripts/klicktest_plantafel_auftraege_ziehen.py` ergänzt: die Zeile bleibt beim Ziehen gleich hoch (Woanders, Kolonne, mit dem Finger, mit der Maus dunkel), die
Anzeige oberhalb der Zelle und ohne Zeigerereignisse (an ihrer Mitte findet die Seite nie das Ziel), kein Name ohne Warnung gekürzt (Finger, 1280 px); Bilder mit dem Finger hell (1280 px) und mit der Maus dunkel (1440 px).
Gegenproben: Archiv `gegenproben-stufe6-r5d.md`, „1.9.287“.
**Angepasste Erwartungen** (Regel 28): `tests/test_v684_chips_finger.py::test_finger_32_px_mit_groesserem_treffbereich` -- alt `padding:3px 7px`, neu `padding:3px 6px`.
`scripts/klicktest_plantafel_auftraege_ziehen.py`, „Frei: nichts markiert, der Chip über dem Zeiger“ -- alt die Unterkante der Kopie über dem Zeiger, neu „… der Chip
neben dem Zeiger“: links mindestens 12 px rechts vom Zeiger, der Zeiger zwischen Ober- und Unterkante.

### Umsetzung 1.9.288 (Punkt 6): „Nicht eingeplant“ zeigt die Stunden wie die Akte

- Befund: beide Listen rechnen dasselbe Soll (`app/akte.py::soll_stunden()`). „Soll 0,00 h“ in „Nicht eingeplant“ gegen „Soll 6,00 h“ in „Aufträge“ bei
  „Kaminverwahrung Schulz“ kam aus verschiedenen Testdaten: im Klicktest `klicktest_plantafel_rueckgaengig.py` (1.9.282) hatte der Auftrag keine Kalkulation, im
  Klicktest `klicktest_plantafel_auftraege.py` 6 h. Ein echter Unterschied blieb trotzdem: „Nicht eingeplant“ zeigte immer „Soll <Planstunden> h“ -- auch
  „Soll 0,00 h“ statt „nach Aufwand“ und das volle Soll statt „Rest …“, wenn schon gebucht war.
- `app/planning.py::rueckstand()` liefert dazu `stunden` aus `app/auftragsliste.py::stunden_zeile()` (Kranvermietung nie -- sie hat einen Einsatz), gebucht und
  Herkunft Wartungsvertrag über die gemeinsamen Abfragen `gebuchte_stunden()` und `aus_wartungsvertrag()` (die Auftragsliste nutzt sie ebenso) -- zwei Abfragen
  mehr, fest. Die Liste zeigt `stunden` statt „Soll <planned_hours> h“; `planned_hours` bleibt in der Antwort (Dialog, Kapazität).
- Der Klicktest „Rückgängig“ legt „Kaminverwahrung Schulz“ jetzt mit 6 h Soll an -- derselbe Auftrag zeigt in beiden Testdaten dieselben Stunden.

#### Festlegungen 1.9.288 (bestätigt am 10.11.2026)

1. „Nicht eingeplant“ zeigt die Stunden mit derselben Zeile wie „Aufträge“ und die Akte („Soll …“, „Rest …“, „… über Soll“, „nach Aufwand“, „Wartungsvertrag“).
2. Gebucht zählt wie die Akte nur Baustelle & Werkstatt (keine Fahrzeit, keine laufende Zeit).
3. Die Zahl der Abfragen bleibt fest (je eine für gebucht und Herkunft Wartungsvertrag, unabhängig von der Zahl der Aufträge).

#### Tests und Prüfung 1.9.288

Neu: `tests/test_v688_rueckstand_stunden.py` (vier Aufträge -- Soll, Rest mit Fahrzeit und einer laufenden Zeit, nach Aufwand, Wartungsvertrag --, dieselbe Zeile wie die Auftragsliste, die
Planstunden bleiben; die Liste zeigt `stunden`). `scripts/klicktest_plantafel_rueckgaengig.py` ergänzt: „Nicht eingeplant“ und „Aufträge“ zeigen für
„Kaminverwahrung Schulz“ „Soll 6,00 h · ohne Termin“. Die feste Zahl Abfragen prüft weiter `tests/test_v564_plantafel_leistung.py`. Gegenproben: Archiv
`gegenproben-stufe6-r5d.md`, „1.9.288“. Angepasste Erwartungen: keine.

### Umsetzung 1.9.289 (Punkt 7): Leiste mit dem neuen Zeitraum, „40 h/Woche“ ohne Umbruch, Untermenü der Stammdaten in Zeilen

- Leiste: nach dem Ziehen einer Person bzw. eines Geräts in „Personen“ und „Geräte“ (`umsetzenZiehen()`) stand bis 1.9.288 „<Name> · <Projekt>: <alt> → ab
  <erster neuer Tag>“ bzw. in eine andere Zeile „…: <Name> → <Name>, ab <Tag>“. Jetzt der neue Zeitraum: „Lia Lang · Sturmschaden Gartenstraße 2: 10.–11.11. →
  11.–12.11.“, in eine andere Zeile „<Projekt> <alt> → <neu>: <Name> → <Name>“, ohne „→ <neu>“, wenn die Tage bleiben.
- Den neuen Zeitraum rechnet der Server: `app/tag_aktionen.py::umsetzen()` liefert `ziel_tage` (die Tage, auf die die gezogenen gingen, in Arbeitstagen nach
  `verschiebung()`, seit 1.9.277) -- auch beim Prüfen. Die Seite nimmt den ersten und letzten davon (`fmtSpanne()`), sie rechnet keine Arbeitstage nach (Do–Fr um
  einen Tag weiter heißt „13.–16.11.“, Fr und der nächste Mo -- in Kalendertagen hätte die Seite „13.–14.11.“ gezeigt).
- Stammdaten: „40 h/Woche“ steht in `<span class="nw">` mit `white-space:nowrap`; das Untermenü unter 1400 px (seit 1.9.278 oben, eine Zeile, die seitlich rollte)
  bricht jetzt in Zeilen um (`flex-wrap:wrap`, ein Knopf in sich nie) -- bei 1400 px passt es in eine Zeile, bei 1280 px zwei; unter 850 px wieder eine Zeile, die
  im Rahmen rollt (`flex-wrap:nowrap;overflow:auto`), sonst stünden auf dem Telefon vier bis fünf Zeilen Menü über der Liste. Die Knöpfe sind dort so breit wie ihr
  Text (`width:auto`): mit `width:100%` aus der Leiste links nahm beim ersten Versuch jeder Knopf eine ganze Zeile (neun Zeilen, vom Klicktest gefunden) -- in einer
  Zeile ohne Umbruch waren sie bis 1.9.288 von selbst auf ihre Textbreite geschrumpft. Einzelheiten: `stammdaten-und-sidebar.md`,
  „Untermenü in Zeilen, Stunden ohne Umbruch (1.9.289)“.

#### Festlegungen 1.9.289 (bestätigt am 10.11.2026)

1. Nach dem Ziehen einer Person oder eines Geräts nennt die Leiste den alten und den neuen Zeitraum („10.–11.11. → 11.–12.11.“) statt „→ ab <Tag>“.
2. Den neuen Zeitraum liefert der Server (`ziel_tage`, in Arbeitstagen); die Seite rechnet ihn nicht nach.
3. In eine andere Zeile gezogen: „<Projekt> <alt> → <neu>: <Name> → <Name>“; bleiben die Tage, ohne „→ <neu>“.
4. „40 h/Woche“ (Spalte Funktion der Mitarbeiter) bricht nie um, auch in einer eng gezwungenen Spalte.
5. Unter 1400 px steht das Untermenü der Stammdaten in Zeilen über der Karte, ohne seitliches Rollen (bei 1280 px zwei Zeilen), jeder Knopf so breit wie sein
   Text -- ersetzt 1.9.278 Nr. 1 („eine Zeile, rollt waagrecht“).
6. Unter 850 px bleibt das Untermenü eine Zeile, die im Rahmen rollt.

#### Tests und Prüfung 1.9.289

Neu: `tests/test_v689_leiste_zeitraum_und_stammdaten.py` (`ziel_tage` in Arbeitstagen, beim Prüfen und über die API; der Text der Leiste in vier Fällen aus der
Antwort; die Regeln des Untermenüs unter 1400 und 850 px samt Knopfbreite; „h/Woche“ in `.nw`). `scripts/klicktest_stammdaten_breite.py` ergänzt: bei 1400 und 1280 px rollt das
Untermenü nicht seitlich, bei 1280 px zwei Zeilen; „h/Woche“ einzeilig bei 1280 px und mit eng gezwungener Spalte Funktion (40 px); bei 412 px eine Zeile, die rollt.
Gegenproben: Archiv `gegenproben-stufe6-r5d.md`, „1.9.289“.
**Angepasste Erwartungen** (Regel 28):
- `tests/test_v682_leiste_rueckgaengig.py::test_umsetzen_in_der_eigenen_und_einer_anderen_zeile`: alt Antwort ohne `ziel_tage`, Leiste „Tom Monteur · Wasserturm:
  09.–10.11. → ab Mi 11.11.“; neu Antwort mit `ziel_tage` 11.–12.11., Leiste „… 09.–10.11. → 11.–12.11.“ (in die andere Zeile unverändert).
- `tests/test_v678_stammdaten_untermenue_oben.py::test_untermenue_unter_1400_px_oben`: alt `.side{position:static;display:flex;overflow:auto}` und keine Regel
  `.side{` unter 850 px, `.side button{white-space:nowrap}`; neu `.side{position:static;display:flex;flex-wrap:wrap}`, `.side button{width:auto;white-space:nowrap}`
  und unter 850 px `.side{flex-wrap:nowrap;overflow:auto}`.
- `tests/test_v675_stammdaten_breite.py::test_stunden_unter_der_funktion`: alt „… h/Woche“ ohne Hülle, neu in `<span class="nw">` (nur der Aufbau).
- `tests/test_v663_leerer_tag.py::test_dialog_und_ziehen_nehmen_die_rueckfrage`: alt `a=>bandZeigen(text,a.umkehrung)`, neu `a=>bandZeigen(text(a),a.umkehrung)`
  (der Text der Leiste aus der Antwort; nur der Aufbau, die Rückfrage geht weiter über `zugSenden()`) -- gefunden im vollen Lauf vor dem Festhalten.
- `scripts/klicktest_plantafel_rueckgaengig.py`: alt „Lia Lang · Sturmschaden Gartenstraße 2: 10.–11.11. → ab Mi 11.11.“ und „Pritsche HS-DK 202 · Am Wasserturm 4:
  09.–10.11. → ab Di 10.11.“; neu „… → 11.–12.11.“ und „… → 10.–11.11.“.

## Stufe 6, R5e (ab 1.9.290)

Auftrag vom 10.11.2026, Start 256bf96 (live, Datenbank `c3e9f1a7b285`). Bestätigt: Festlegungen 1.9.283–1.9.289, außer 1.9.283 Nr. 5 (Punkt 1) und 1.9.287
Nr. 4 zweiter Satz (Punkt 2). Je Punkt eine Version:
1 „Aufträge“ mit 2–4 Wochen: unter 1440 px startet „Zum Einplanen“ eingeklappt (wie die übrigen Ansichten); mit 1 Woche bleibt es immer offen.
2 Chip mit Warnung oder Hinweis: das Zeichen sitzt als kleines Abzeichen an der Ecke und nimmt dem Namen keinen Platz (bis 1.9.290 „HS-D… ⚠“ bei 1280 px mit
  dem Finger, die Pritschen waren so nicht zu unterscheiden). Kein Chip mit Kurzname wird gekürzt (1440 und 1280 px, Maus und Finger).
3 Anzeige vor dem Loslassen bei schmalen Tagen (unter 110 px) kurz: „Schon woanders · Rückfrage“, „Antrag offen“, „Abwesend · Rückfrage“, „Ganze Kolonne ·
  Rückfrage“; der Auftrag steht dann in der Rückfrage.

### Umsetzung 1.9.290 (Punkt 1): „Zum Einplanen“ startet nach dem Zeitraum

- `auftraegeListeOffen(tage)`: mit 1 Woche offen, sonst `!rueckstandStartZu(innerWidth)` -- dieselbe Regel wie „Nicht eingeplant“ in den übrigen Ansichten
  (gemerkt „zu“/„offen“ gilt bei jeder Breite, sonst unter 1440 px zu, 1.9.257). Gemerkt wird nur in den übrigen Ansichten (der Knopf, 1.9.247); in „Aufträge“
  merkt weder der Start noch der Knopf etwas (1.9.283 Nr. 2).
- `setView()`: beim Wechsel nach „Aufträge“ mit dem gemerkten Zeitraum der Ansicht (`zeitraumGemerkt('auftraege')`, 1.9.279); bis 1.9.289 immer
  `rueckstandZeigen(true, false, false)`.
- `zeitraumGewechselt()` (bis 1.9.289 ein namenloser Pfeil am `change` der Auswahl): merkt den Zeitraum der Ansicht wie bisher und startet in „Aufträge“ die Liste
  neu -- auch, wenn sie dort von Hand auf- oder zugeklappt war. Sonst stünde die Liste nach „1 Woche → 2 Wochen“ bei 1280 px weiter offen und die Tafel rollte
  (der übliche Weg: die Ansicht öffnet mit 1 Woche, dann wird der Zeitraum gewählt). In den übrigen Ansichten ändert ein anderer Zeitraum die Liste nicht.
- Gemessen (Testdaten des Klicktests, Liste offen bzw. zu, `scrollWidth − clientWidth` der Tafel):

  | Fenster | Zeitraum | Liste offen: Platz, Tag, rollt | Liste zu: Platz, Tag, rollt |
  |---|---|---|---|
  | 1440 px | 1 Woche | 881 px, 120 px, nein | 1077 px, 159 px, nein |
  | 1440 px | 2 Wochen | 881 px, 56 px, 13 px | 1077 px, 74 px, nein |
  | 1440 px | 3 Wochen | 881 px, 56 px, 345 px | 1077 px, 56 px, 149 px |
  | 1440 px | 4 Wochen | 881 px, 56 px, 677 px | 1077 px, 56 px, 481 px |
  | 1280 px | 1 Woche | 721 px, 94 px, nein | 917 px, 133 px, nein |
  | 1280 px | 2 Wochen | 721 px, 56 px, 143 px | 917 px, 61 px, nein |
  | 1280 px | 3 Wochen | 721 px, 56 px, 475 px | 917 px, 56 px, 279 px |
  | 1280 px | 4 Wochen | 721 px, 56 px, 807 px | 917 px, 56 px, 611 px |

  Mit der Regel startet die Liste bei 1280 px mit 2 Wochen zu -- die Tafel rollt nicht mehr. Offen bleiben: bei genau 1440 px mit 2 Wochen ist die Liste offen und
  die Tafel rollt 13 px (mindestens 230 + 10 × 56 + 4 × 26 = 894 px bei 881 px Platz); 3 und 4 Wochen rollen bei 1440 und 1280 px auch eingeklappt (mindestens
  56 px je Tag, unverändert) -- als Frage im Bericht.

#### Festlegungen 1.9.290 (bestätigt am 10.11.2026)

1. In „Aufträge“ startet „Zum Einplanen“ mit 1 Woche immer offen, mit 2–4 Wochen wie „Nicht eingeplant“ in den übrigen Ansichten: gemerkt „zu“ bzw. „offen“
   gilt bei jeder Breite, sonst unter 1440 px zu -- ersetzt 1.9.283 Nr. 1 („immer offen“) und Nr. 5.
2. Der Start gilt beim Wechsel in „Aufträge“ (mit dem gemerkten Zeitraum der Ansicht) und bei jedem anderen Zeitraum dort -- auch wenn die Liste vorher von Hand
   auf- oder zugeklappt war (ergänzt 1.9.283 Nr. 2: von Hand zugeklappt bleibt sie bis zum nächsten Wechsel in die Ansicht oder des Zeitraums).
3. Der Start merkt nichts; in den übrigen Ansichten ändert ein anderer Zeitraum die Liste nicht.

#### Tests und Prüfung 1.9.290

Neu: `tests/test_v690_auftraege_liste_nach_zeitraum.py` (in node mit dem Code der Seite: Wechsel nach „Aufträge“ mit 1–4 Wochen, bei 1280 und 1440 px, mit und
ohne Gemerktes -- neun Fälle; ein anderer Zeitraum startet die Liste neu, auch nach Auf- oder Zuklappen von Hand; in den übrigen Ansichten nicht; nichts gemerkt).
`scripts/klicktest_plantafel_auftraege.py` ergänzt: bei 1440 px mit 2 Wochen offen; bei 1280 px mit 2 Wochen zu, die Tafel rollt nicht, nichts gemerkt; beim
Wechsel in die Ansicht mit 2 Wochen zu; zurück auf 1 Woche offen; von Hand zu, dann 3 Wochen: zu; Bilder „2 Wochen bei 1280 px“ hell und dunkel. Gegenproben:
Archiv `gegenproben-stufe6-r5e.md`, „1.9.290“.
**Angepasste Erwartungen** (Regel 28):
- `tests/test_v683_auftraege_liste_offen.py::_lauf`: die node-Attrappe bekommt `auftraegeListeOffen()` dazu (`setView()` ruft sie seit 1.9.290); die geprüften
  Fälle unverändert (ohne gemerkten Zeitraum ist es 1 Woche) -- nur der Aufbau.
- `tests/test_v679_auftragsliste.py::_seite`: `auftraegeListeOffen()` als Platzhalter (nur der Aufbau); `test_auswahl_mit_einer_woche_und_merken`: alt
  `addEventListener('change',()=>{zeitraumMerken(view,tageAnzahl());loadBoard()})`, neu `addEventListener('change',zeitraumGewechselt)` und
  `function zeitraumGewechselt(){zeitraumMerken(view,tageAnzahl());…loadBoard()}` (merkt den Zeitraum und lädt weiter, dazu der Neustart der Liste).

### Umsetzung 1.9.291 (Punkt 2): Warnung und Hinweis als Abzeichen an der Ecke

- `chipHtml()`: statt ⚠ hinter dem Namen (`${c.warn?WARNZEICHEN:''}`) und dem Punkt davor steht hinter dem Namen ein `span.abzeichen` (mit Warnung zusätzlich
  `.warn`, darin `WARNZEICHEN`; sonst mit Hinweis darin `span.hinweis-punkt`) -- Warnung vor Hinweis wie bisher (mit beidem nur ⚠). `aria-hidden`: was die
  Warnung sagt, steht wie bisher im title des Chips. Der Klassenname beginnt bewusst nicht mit „chip“ -- die Zähler der Tests (`class="chip…"`) nähmen ihn sonst als
  eigenen Chip.
- CSS: `.chip` ist `position:relative`; `.chip .abzeichen` absolut, 12 × 12 px rund, `top:-5px; right:-5px` -- 5 px über die Ecke hinaus, in den Abstand zum
  nächsten Chip (4 px) und den Innenabstand der Karte; links reicht es 7 px in den Chip, so weit wie Innenabstand und Rand (6 + 1 px), also nicht in den Namen.
  Mit Warnung Rand `--ds-fehler` auf `--ds-fehler-hell`, ⚠ 8 px; mit Hinweis Rand `--ds-linie-stark` auf `--ds-flaeche`, der Punkt 6 px. Der rote Rand des
  Chips mit Warnung bleibt.
- Gemessen (Klicktests, Testdaten mit „HS-DK 202“, „HS-DK 204“ und dem Kran): kein Chip gekürzt bei 1440 und 1280 px, mit Maus und Finger, auch die Pritsche
  HS-DK 204 mit ⚠ (bis 1.9.290 „HS-D…“) -- mit 1 Woche (Tage 120 bzw. 94 px) und mit 2 Wochen bei eingeklappter Liste (74 bzw. 61 px). Bei 56 px je Tag
  (2 Wochen mit offener Liste, 3 und 4 Wochen -- dort rollt die Tafel ohnehin) bleibt der Kran gekürzt: Kranzeichen und „Kr“ brauchen 45 px, die Karte hat 40
  (der Name steht im title) -- als Frage im Bericht.

#### Festlegungen 1.9.291 (bestätigt am 10.11.2026)

1. ⚠ bzw. der Punkt eines Hinweises sitzt als Abzeichen an der oberen rechten Ecke des Chips (12 px, 5 px über die Ecke hinaus), außerhalb des Namens; der Chip
   mit Warnung behält seinen roten Rand -- ersetzt 1.9.287 Nr. 4 zweiter Satz („ein Chip mit ⚠ darf bei 1280 px kürzen“).
2. Kein Chip ist gekürzt bei 1440 und 1280 px, mit Maus und Finger, auch mit Warnung -- mit 1 Woche und mit 2 Wochen bei eingeklappter Liste.

#### Tests und Prüfung 1.9.291

Neu: `tests/test_v691_abzeichen_an_der_ecke.py` (in node mit dem Code der Seite: Abzeichen mit Warnung bzw. Hinweis hinter dem Namen, kein Zeichen mehr im Fluss,
Warnung vor Hinweis, ohne beides keins; die Regeln für Lage und Größe). `tests/test_v460_ecken_der_karten.py`: `abzeichen` unter „Kennzeichen“ in
`NICHT_KARTEN` (eine neue umrandete Fläche wird dort eingeordnet -- im vollen Lauf vor dem Festhalten gefunden). `scripts/klicktest_plantafel_auftraege.py`
ergänzt: bei 1440 und 1280 px die Abzeichen (⚠ zweimal am Kran, Punkt an Nele) an der Ecke ihres eigenen Chips -- 5 px (±1) über und rechts hinaus --, außerhalb
des Namens; mit 2 Wochen bei 1280 px kein Chip gekürzt (bis 1.9.290 „Kr“).
`scripts/klicktest_plantafel_auftraege_ziehen.py` ergänzt: kein Chip gekürzt, Abzeichen an der Ecke, HS-DK 204 mit ⚠ -- mit der Maus bei 1440 px (hell, dunkel)
und 1280 px, mit dem Finger bei 1280 px (dunkel, hell) und 1440 px; Bilder „Aufträge“ mit dem Finger bei 1280 px, hell und dunkel. Gegenproben: Archiv
`gegenproben-stufe6-r5e.md`, „1.9.291“.
**Angepasste Erwartungen** (Regel 28):
- `scripts/klicktest_plantafel_auftraege_ziehen.py`, Teil „Finger hell“: alt „kein Name ohne Warnung gekürzt“ (nur Chips ohne ⚠), neu „kein Chip gekürzt,
  Abzeichen an der Ecke, HS-DK 204 mit ⚠“ (alle Chips, auch mit Warnung).
- `scripts/klicktest_plantafel_auftraege.py`, Teil „2 Wochen bei 1280 px“ (seit 1.9.290): alt nur „Liste zu, rollt nicht“, neu dazu „kein Chip gekürzt“.

### Umsetzung 1.9.292 (Punkt 3): kurze Anzeige vor dem Loslassen bei schmalen Tagen

- `zugAnzeige(z, ziel, kurz=false)`: mit `kurz` die kurze Fassung ohne Auftrag und Namen -- „Schon woanders · Rückfrage“ (Person oder Gerät), „Abwesend ·
  Rückfrage“, „Antrag offen“, „Ganze Kolonne · Rückfrage“; die Klasse (frei, woanders, antrag) und damit Farbe und Rand der Zelle bleiben dieselben. „Frei –
  <Tag>“ und „Ganze Kolonne – <Tag>“ haben keine kurze Fassung (bei 94 px zwei Zeilen). Ohne den dritten Parameter wie bis 1.9.291 -- die Tests mit der langen
  Fassung (v681, v686) unverändert.
- `zugZielZeigen()`: kurz, wenn die Zelle schmaler als `SCHMALER_TAG` (110 px) ist (`getBoundingClientRect().width` der Zelle). Gemessen (1.9.290): 1 Woche bei
  1440 px 120 px (lang), bei 1280 px mit offener Liste 94 px (kurz), mit eingeklappter Liste 133 bzw. 159 px (lang); ab 2 Wochen 56–74 px (kurz).
- Der Auftrag steht in der Rückfrage: beim Loslassen fragt der Server bei einer neuen Warnung zurück (1.9.281), `konfliktZeile()` nennt je Person bzw. Gerät
  doppelt „gleichzeitig in <Nummer> · <Auftrag>“ (`other_project`, `other_project_name` aus `app/planning.py::_conflicts()`) -- unverändert, jetzt im Klicktest
  geprüft. Abwesend nennt sie mit Art und Tag, ohne Auftrag.
- Bei 94 px steht die kurze Fassung auf drei Zeilen („Schon / woanders · / Rückfrage“), die lange stand auf bis zu sechs.
- Klicktest: dazu „Uwe Urlaub“ ohne Kolonne, die ganze Woche abwesend (`EmployeeAbsence`) -- vorher gab es in den Testdaten niemanden, der abwesend ist.

#### Festlegungen 1.9.292 (bestätigt am 10.11.2026)

1. Ist der Tag schmaler als 110 px, zeigt die Anzeige vor dem Loslassen die kurze Fassung: „Schon woanders · Rückfrage“ (Person oder Gerät), „Abwesend ·
   Rückfrage“, „Antrag offen“, „Ganze Kolonne · Rückfrage“; ab 110 px die lange wie bisher.
2. „Frei – <Tag>“ und „Ganze Kolonne – <Tag>“ bleiben auch bei schmalen Tagen.
3. Wer wo schon steht, nennt dann die Rückfrage beim Loslassen: je Person bzw. Gerät „gleichzeitig in <Nummer> · <Auftrag>“ (wie bisher).

#### Tests und Prüfung 1.9.292

Neu: `tests/test_v692_kurze_anzeige.py` (in node mit dem Code der Seite: die vier kurzen Fassungen samt Klasse, die langen wie bisher, „Frei“ und „Ganze Kolonne –
<Tag>“ gleich; die Grenze 110 px und der Aufruf in `zugZielZeigen()`; die Rückfrage mit dem Auftrag). `scripts/klicktest_plantafel_auftraege_ziehen.py` ergänzt:
bei 1440 px der Tag mindestens 110 px und „Abwesend – Rückfrage …“ (Uwe auf Kaminverwahrung Di, Escape); mit dem Finger bei 1280 px der Tag schmaler als 110 px,
„Schon woanders · Rückfrage“ (Bild dunkel), loslassen -> die Rückfrage nennt Ole, P-2026-0151 und „Sturmschaden Gartenstraße 2“, Abbrechen -> nichts gespeichert;
„Abwesend · Rückfrage“, „Antrag offen“, „Ganze Kolonne · Rückfrage“ (je zurück auf die Liste: nichts); mit dem Finger hell die kurze Fassung (Bild). Gegenproben:
Archiv `gegenproben-stufe6-r5e.md`, „1.9.292“.

## Geräte-Runde: Vorweg zur Plantafel (ab 1.9.293)

Auftrag vom 10.11.2026, Start 3ec14c1 (live, Datenbank `c3e9f1a7b285`). Bestätigt: Festlegungen 1.9.290–1.9.292. Antworten auf die Fragen zu R5e, gebaut als
Vorweg der Geräte-Runde (die Runde selbst: `modul-betriebsmittel-und-betriebskosten.md`, „Geräte-Runde“), je eine Version:
V1 ab 2 Wochen die Namensspalte 200 px, damit bei 1440 px nichts rollt; 3 und 4 Wochen dürfen rollen.
V2 bei 56 px je Tag am Kran nur das Kranzeichen.
V3 die kurze Anzeige passt -- nichts zu bauen, keine Version.
V4 in schmalen Chips hießen beide Pritschen „HS“: endet der Kurzname eines Geräts auf eine Zahl, zeigt der schmale Chip die Zahl („202“), sonst die ersten zwei
   Buchstaben.

### Umsetzung 1.9.293 (V1): Namensspalte ab 2 Wochen 200 px

- `auftraegeHtml()`: `nameW` ist 200 px unter 1400 px Fensterbreite (1.9.283) und jetzt auch ab 2 Wochen (`eng`, schon für die 56 px je Tag da), sonst 230 px.
- Gemessen (1.9.290): bei 1440 px mit offener Liste 881 px Platz; 2 Wochen brauchten mit 230 px mindestens 894 px (rollte 13 px), mit 200 px 864 px -- rollt
  nicht, die Tage 57–58 px. 3 und 4 Wochen rollen weiter (mindestens 56 px je Tag, unverändert).

#### Festlegungen 1.9.293 (Bitte bestätigen)

1. In „Aufträge“ ist die Namensspalte ab 2 Wochen 200 px (wie unter 1400 px Fensterbreite); mit 1 Woche ab 1400 px weiter 230 px -- bei 1440 px mit offener
   Liste rollt 2 Wochen nicht mehr.
2. 3 und 4 Wochen dürfen rollen (mindestens 56 px je Tag, unverändert).

#### Tests und Prüfung 1.9.293

Neu: `tests/test_v693_namensspalte_ab_zwei_wochen.py` (die Zeile der Seite in node, acht Fälle aus Fensterbreite und Zeitraum). `scripts/klicktest_plantafel_auftraege.py`
ergänzt: bei 1440 px mit 1 Woche 230 px, mit 2 Wochen 200 px und die Tafel rollt nicht. Gegenproben: Archiv `gegenproben-geraete.md`, „1.9.293“.
**Angepasste Erwartungen** (Regel 28): `tests/test_v683_auftraege_liste_offen.py::test_spalten_und_chips` -- alt `const nameW=window.innerWidth<1400?200:230;`, neu
`const nameW=window.innerWidth<1400||eng?200:230;`.

### Umsetzung 1.9.294 (V2): der Kran bei schmalen Tagen nur mit seinem Zeichen

- CSS: `@container (max-width:43.9px){.a-einsatz .chip:has(.kranzeichen) .chip-text{display:none}}` -- die Karte ist seit 1.9.283 ein Container; ist ihr
  Inhalt höchstens 43,9 px breit, verschwindet der Name des Krans, das Kranzeichen bleibt (1.9.283 Nr. 4), der Name steht im title des Chips. Ohne neue Klasse
  am Chip (`:has()`), das Markup bleibt.
- Gemessen (Klicktest-Daten): die Zelle hat 4,5 px Innenabstand je Seite, die Karte 3 px und 1 px Rand -- Inhalt der Karte bei 56 px je Tag 39 px, bei 57,7 px
  (1440 px, 2 Wochen, Liste offen) 41 px, bei 61,3 px (1280 px, 2 Wochen, Liste zu) 44,3 px. Der Kran-Chip mit „Kr“ und Warnung ist 43,7 px breit. Die erste
  Grenze (45 px, aus 5 px Innenabstand gerechnet) nahm auch bei 61 px den Namen weg -- der Klicktest fand es, gemessen statt gerechnet.

#### Festlegungen 1.9.294 (Bitte bestätigen)

1. In „Aufträge“ zeigt der Kran nur sein Zeichen, wenn die Karte höchstens 43,9 px Inhalt hat (bei 56–58 px je Tag); der Name steht im title.
2. Darüber bleibt „Kr“ (bei 61 px je Tag: 2 Wochen, 1280 px, Liste zu); das Kranzeichen verschwindet nie.

#### Tests und Prüfung 1.9.294

Neu: `tests/test_v694_kran_nur_zeichen.py` (die Regel, die Karte als Container, kein Ausblenden des Kranzeichens). `scripts/klicktest_plantafel_auftraege.py`
ergänzt: bei 1280 px mit 3 Wochen 56 px je Tag, kein Chip gekürzt, der Kran nur mit Zeichen; ebenso bei 1440 px mit 2 Wochen (58 px); bei 1280 px mit 2 Wochen
(61 px) der Kran mit „Kr“. Gegenproben: Archiv `gegenproben-geraete.md`, „1.9.294“.
