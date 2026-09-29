# Schlechtwetter-Zeitarten und Abwesenheitskategorie, Krankheitssichtbarkeit

Ausgelagert aus CLAUDE.md am 2026-09-28 im Zuge der Aufteilung in eine schlanke
CLAUDE.md plus themensortiertes Archiv (siehe CLAUDE.md, Abschnitt "Modulübersicht",
und `docs/archiv/regel-abgleich.md` für die vollständige Zuordnung). Der Inhalt ist
wortgetreu (per Skript, zeilenweise) aus der vorherigen CLAUDE.md übernommen, keine
Umformulierung. Versionsangaben ("seit 1.x.y") beziehen sich auf den Stand zum
jeweiligen Zeitpunkt der ursprünglichen Aufzeichnung.

---

## Schlechtwetter-Zeitarten und Abwesenheitskategorie (seit 1.5.3)

Vorbereitung für die spätere Ist-Wert-Auswertung im Produktivstunden-Rechner ("Grundlage für die
späteren Ist-Werte" -- die Ist-Werte selbst sind eine eigene, noch folgende Runde, diese Version
liefert ausschließlich die saubere Erfassung). Erst zwei Befund-Runden (welche Zeitarten/
Abwesenheitsarten heute existieren, ob Krankheit schon von Urlaub getrennt ist, wie viele
Bestandseinträge zu migrieren wären), dann vier vom Betreiber entschiedene Punkte gebaut.

**Punkt 1 -- Prämisse korrigiert: Krankheit/Urlaub waren schon getrennt.** Der Befund zeigte:
`EmployeeAbsence.absence_type`/`EmployeeAbsenceRequest.absence_type` sind freie `String(80)`-
Spalten, gespeist aus der Optionsgruppe `absence_types`, die bereits sechs unterschiedliche Werte
trägt (Urlaub, **Krankheit**, Weiterbildung, Berufsschule, Freizeitausgleich, Sonstiges) --
durchgängig verdrahtet von `create_request()` über `review_request()` bis zur Plantafel-Anzeige.
Der Betreiber verlangte trotzdem eine ZUSÄTZLICHE, feste Kategorie (Urlaub/Krankheit/Fortbildung/
Unbezahlt) für die spätere Ist-Wert-Zählung -- ein fester Code-Wert wie `RecurringCost.
overhead_classification` (`app/absence_requests.py::ABSENCE_CATEGORIES`), KEINE Optionsgruppe:
eine spätere Auswertung muss wissen, welche Werte existieren, ein Admin dürfte sie nicht frei
erweitern können. Das bestehende freie `absence_type`-Feld bleibt UNVERÄNDERT als Ergänzung
daneben (z. B. "Berufsschule" als Unterfall von "fortbildung") -- keine Ablösung.

**Migration ohne Ratewerte**: 0 Bestandszeilen in `employee_absences` UND
`employee_absence_requests` der echten Datenbank (frisch geprüft, nicht angenommen) -- es gab
nichts zu migrieren. Die neue Spalte `absence_category` bekommt trotzdem
`server_default='unbekannt'` (Regel 1) -- für jede andere Installation und gegen einen zwischen
Migrationserstellung und -ausführung eingefügten Datensatz. `"unbekannt"` ist beim Neu-/
Bearbeiten-Schreiben über die Schemas (`EmployeeAbsenceCreate`/`EmployeeAbsenceRequestCreate`,
`Field(pattern="^(urlaub|krankheit|fortbildung|unbezahlt)$")`) bewusst NICHT erlaubt -- entsteht
ausschließlich als Migrations-Rückfallwert, eine spätere Ist-Wert-Auswertung zählt ihn bewusst
nicht mit (verhindert, dass ein geratener/unbekannter Status den Durchschnitt verfälscht).

**Bedienung**: wer eine Abwesenheit anlegt, wählt auch die Kategorie -- dieselbe Person wie beim
bereits bestehenden freien `absence_type`. Ein Monteur/Büro-Mitarbeiter, der über
`POST /api/absence-requests` (Selbstbedienung) einen eigenen Antrag stellt, wählt beide Felder
selbst; das Büro, das über `POST /api/planning/absences` (Plantafel) direkt eine Abwesenheit für
jemand anderen anlegt, ebenso. Keine neue Zuständigkeit.

**Punkt 3 -- Krankheitssichtbarkeit, Vorschlag geprüft und vom Betreiber abgelehnt.** Vorgelegter
Vorschlag (Muster `app/audit.py::redact_wage_snapshot()`, das Lohnfelder bereits heute für
`buero_auftrag` aus der Änderungshistorie entfernt, siehe "Rechtekonzept" -> "Vier Rollen"):
`buero_auftrag` sieht bei Urlaub/Fortbildung/Unbezahlt weiterhin die echte Kategorie (für die
Plantafel-Kapazitätsplanung nötig), bei Krankheit dagegen nur ein neutrales Label ohne Notiz;
`buero_finanzen`/`admin` sehen alles unverändert. **Der Betreiber hat diesen Vorschlag zunächst
nach Rückfrage ausdrücklich abgelehnt** ("Unverändert lassen") -- `buero_auftrag` sollte demnach
weiterhin JEDE Kategorie inkl. Krankheit ungefiltert sehen, exakt wie vor dieser Version. **Seit
1.5.4 revidiert**: derselbe Vorschlag wurde in der Folgerunde erneut aufgegriffen und diesmal
umgesetzt -- siehe Abschnitt "Krankheitssichtbarkeit: buero_auftrag sieht nur noch 'abwesend'
(seit 1.5.4)" unten für die vollständige Umsetzung inkl. der dabei gelösten Anlegen/Bearbeiten-
Frage. Diese Zeile bleibt bewusst stehen, um die Entscheidungsgeschichte nachvollziehbar zu
halten, statt sie rückwirkend zu überschreiben. Für die spätere Ist-Wert-Runde festgehalten: der
Produktivstunden-Rechner selbst zeigt UNABHÄNGIG von dieser Entscheidung nur einen aggregierten
Zähler/Durchschnitt, nie eine Zeile "Mitarbeiter X war Y Tage krank" -- dieselbe Trennung wie bei
den Löhnen (aggregiert ja, personenbezogen nein), unabhängig von der Rolle, die den Rechner öffnet.

**Punkt 2 -- Schlechtwetter Winter/Sommer, drei bestehende Auswertungen mussten angefasst
werden.** Grenze wie vorgegeben: 1.12.–31.3. Winter (gesetzliche Schlechtwetterzeit im
Dachdeckerhandwerk, Saison-Kurzarbeitergeld), sonst Sommer (tarifliches Ausfallgeld) -- die
feineren Wintergeld-Zeiträume (15.12.–Ende Februar) sind bewusst NICHT in die Zeitart eingebaut,
das ist laut Vorgabe eine Abrechnungsfrage, keine Zeitart-Frage. Zwei neue Werte
`weather_winter`/`weather_summer` in der bereits bestehenden Optionsgruppe `time_entry_types`
(vier bisherige Werte: Baustellenzeit/Fahrzeit/Werkstattzeit/Sonstige Arbeitszeit) --
**Migration ergänzt sie explizit in einer bereits gesäten Installation**
(`ensure_default_option_groups()` füllt eine bereits existierende Gruppe nie nachträglich mit
neuen Defaults auf, "Existierende Gruppen werden nicht wieder mit Defaults aufgefüllt", siehe
`app/option_settings.py` -- Muster `257fb2967c93`, der vierte Rahmen-Baustein für einen bereits
gesäten Satz). `DEFAULT_OPTION_GROUPS` selbst ist ebenfalls erweitert, für jede künftige, frische
Installation ohne vorherigen Zugriff.

Erst beim genauen Hinsehen zeigte sich: `entry_type` ist entgegen einer früheren, zu groben
Beschreibung KEIN hart geschlossener Satz -- `app/time_tracking.py::ENTRY_TYPES` (die vier
bekannten Werte) wird nur weich geprüft (`create_manual_entry()`: ein unbekannter Wert wird nicht
abgelehnt, nur ein leerer auf "other" normalisiert), `start_timer()` prüft gar nicht. Die beiden
neuen Zeitarten funktionieren dadurch strukturell bereits ohne Codeänderung -- **aber drei
bestehende Auswertungen hätten sie falsch behandelt, wenn sie unangetastet geblieben wären**:

1. **Produktivität**: `entry_type_is_productive()` lautete `entry_type != "travel"` -- ein
   Einzeiler, keine Liste (die daneben liegende `PRODUCTIVE_TYPES`-Konstante war tot, nirgends
   referenziert, jetzt entfernt). Ohne Anpassung wären beide neuen Zeitarten fälschlich als
   produktiv gezählt worden. Jetzt `entry_type not in NON_PRODUCTIVE_ENTRY_TYPES`
   (`{"travel", "weather_winter", "weather_summer"}`) -- **eine Quelle für `counts_as_productive`**
   (bei Anlage/Änderung eines `TimeEntry` gesetzt), jede nachgelagerte, bereits bestehende
   Auswertung, die dieses Feld liest (Dashboard, Projektmappe, Backoffice-Summen,
   Produktivstunden-Rechner künftig), funktioniert dadurch korrekt, ohne selbst geändert werden
   zu müssen.
2. **DATEV-Export**: `_wage_type()` (`app/time_backoffice.py`) kannte nur vier feste Lohnarten
   (eigene `TimeTrackingSettings`-Spalten je Zeitart) und wäre für einen unbekannten `entry_type`
   stillschweigend auf die Lohnart "Sonstige Arbeitszeit" zurückgefallen -- tariflich falsch,
   Saison-Kurzarbeitergeld und Ausfallgeld sind eigene Lohnarten. Zwei neue Spalten
   `datev_wage_type_weather_winter`/`_weather_summer` plus zwei neue Felder in der
   Backoffice-Oberfläche (Einstellungen → Zeiterfassungs-Backoffice → DATEV/Lohnarten) --
   **bewusst KEIN Rückfall auf "Sonstige"** für diese beiden Zeitarten: fehlt die Lohnart, bricht
   der Export mit einer Warnung ab ("Zeitart weather_winter: DATEV-Lohnart fehlt"), statt falsch
   zu buchen. Der Stundenzettel-PDF/CSV-Export zeigte bisher ohnehin den rohen `entry_type`-Wert
   statt der Optionsgruppen-Bezeichnung (`_entry_type_label()`, neu) -- sonst stünde dort
   "weather_winter" statt "Schlechtwetter Winter". **Seit 1.8.8** einmal je Lauf geladen
   (`_entry_type_labels()`, vor `list_entries()`), nicht mehr je Zeile, siehe CHANGELOG.md 1.8.8.
3. **Abrechnungsschutz**: `create_invoice_from_time_entries()` (`app/invoices.py`, "Rechnung aus
   Zeitbuchungen") holt alle gebuchten Zeiten eines Auftrags ungefiltert nach Zeitart. Da
   `TimeEntry.order_id` NOT NULL ist, muss ein Monteur auch witterungsbedingten Ausfall
   zwangsläufig einem Kundenauftrag zuordnen (Schlechtwetter hat keinen natürlichen "eigenen"
   Auftrag) -- ohne Ausschluss hätte die Funktion diese Stunden als Position "Ausgeführt von …"
   dem Kunden in Rechnung gestellt. Die beiden neuen Zeitarten sind jetzt explizit ausgeschlossen
   (`booked = [... if e.entry_type not in ("weather_winter", "weather_summer")]`). **Fahrzeit
   bleibt davon bewusst unberührt** (bereits bestehendes, nicht Teil dieser Anfrage geändertes
   Verhalten -- Fahrzeit wird heute schon ungefiltert mit abgerechnet, wenn sie über diesen Weg
   läuft).

**Vorschlag statt Zwang beim Buchen**: die Grenze ist eine reine Kalenderregel, deshalb wird beim
Öffnen der mobilen Zeiterfassung (Schnellstart UND Nachtrag) die zum Buchungsdatum passende der
beiden Kacheln optisch hervorgehoben (`weatherSeasonFor(dateStr)`, `time_tracking_field.html`,
CSS-Klasse `.suggested`) -- **übersteuerbar**, keine der beiden Kacheln ist gesperrt oder
automatisch vorausgewählt; bei Nachtrag aktualisiert sich die Hervorhebung, wenn das Datum
geändert wird. Auf der Desktop-Seite (`time_tracking.html`) bleiben Quick-Start-Kacheln bewusst
hart codiert (4 feste Buttons, unverändert seit jeher, keine Weiche für die beiden neuen Werte) --
die beiden neuen Zeitarten sind dort trotzdem sofort über die bereits bestehenden, dynamisch aus
der Optionsgruppe befüllten Dropdown-Felder ("Manuell buchen"/"Gruppenbuchung") erreichbar, ohne
Codeänderung nötig; die Season-Hervorhebung wurde für Desktop bewusst nicht gebaut (primäres Ziel
laut Auftrag: die mobile Ansicht des Monteurs).

**Angriffstest/Regressionstest**: 20 neue Tests
(`tests/test_v286_schlechtwetter_und_abwesenheitskategorie.py`) -- Produktivitäts-Klassifikation
pur und über eine echte `TimeEntry`-Anlage, Abrechnungsschutz (Schlechtwetter wird nie zur
Rechnungsposition, eine Rechnung aus nur Schlechtwetter-Zeit schlägt fehl statt eine leere
Rechnung zu erzeugen), DATEV-Lohnart ohne Rückfall für die beiden neuen Zeitarten, Kategorie-
Validierung (jede der vier echten Kategorien wird akzeptiert, ein unbekannter Wert UND
"unbekannt" selbst werden beim Neuanlegen abgelehnt), Genehmigung kopiert die Kategorie korrekt
auf die entstehende `EmployeeAbsence`, Router-Ebene (`POST /api/absence-requests` verlangt das
neue Pflichtfeld, 422 ohne/mit ungültigem Wert), `GET /api/planning/absences` liefert das neue
Feld und unterstützt einen Filter darauf, sowie die Migrations-Seed-Funktion isoliert
(idempotent, No-op ohne bereits existierende Gruppe). Ein bestehender Test
(`test_v260_role_audit.py::test_absence_requests_stay_open_to_field_as_self_service`) musste um
das neue Pflichtfeld ergänzt werden. Volle Suite: 1602 Tests grün.

## Abschluss der Zeiterfassung / Sperrdatum (seit 1.7.10)

Befund aus der Kolonnenführer-Runde: Es gab keinerlei Abschluss. `TimeEntry.status` kennt nur
`running`/`booked`, `build_datev_export()` liest nur und setzt keinen Stempel -- jeder Monteur
konnte eigene, bereits in die Lohnabrechnung eingegangene Zeiten jederzeit ändern oder löschen.
Betreiberentscheidung: ein Sperrdatum statt eines Status je Buchung.

- **Datenmodell:** `TimeTrackingSettings.locked_until` (Date) plus `locked_at`/`locked_by_user_id`
  (Wer/Wann), Migration `fa2105afb89a`, alle drei nullable (kein Regel-1-Fall). Fremdschlüssel mit
  festem Namen `fk_time_tracking_settings_locked_by_user_id` -- Autogenerate hatte ihn namenlos
  erzeugt, `downgrade()` hätte dann nicht funktioniert.
- **Eigener Endpunkt statt Formularfeld:** `PUT /api/time-backoffice/lock`. Das allgemeine
  Einstellungsformular (`PUT /api/time-backoffice/settings`) überschreibt alle Felder auf einmal --
  läge das Sperrdatum darin, würde jedes normale Speichern es zurücksetzen.
  `update_time_settings()` übernimmt die drei Felder deshalb bewusst nicht; in
  `TimeTrackingSettingsOut` stehen sie nur lesend (Monteur-Ansicht braucht sie). Mit Test belegt.
- **Wer darf was:** vorrücken das Backoffice (`buero_auftrag`+); zurücknehmen oder aufheben öffnet
  bereits abgerechnete Zeiträume wieder und bleibt dem Admin vorbehalten (403 sonst). Die
  Backoffice-Seite selbst lässt ohnehin nur Admins hinein (`init()`), die API ab `buero_auftrag`.
- **Wirkung:** `app/routers/time_tracking.py::_require_open_period()` -- jeder Nicht-Admin bekommt
  403 für Anlegen, Ändern (alter UND neuer `work_date`), Löschen, Stoppen, Timer-Start und
  Gruppenbuchung/-stopp mit `work_date <= locked_until` (einschließlich). Gilt auch für die
  eigenen Buchungen eines Monteurs und für Büro-Konten auf ihren eigenen Zeiten. Ein über den
  Abschluss hinweg laufender Timer lässt sich danach nur vom Admin stoppen -- bewusst, denn Stoppen
  schreibt Stunden in einen abgerechneten Zeitraum.
- **Oberfläche:** Karte "Abschluss der Zeiterfassung" im DATEV-Reiter des Backoffice (Stand mit
  Wer/Wann, Rückfrage beim Wiederöffnen). `time_tracking_field.html` zeigt gesperrte Buchungen
  mit "abgeschlossen" statt Ändern/Löschen und setzt das Mindestdatum des Nachtrags. Die volle
  `time_tracking.html` (Büro) blendet die Knöpfe NICHT aus -- dort meldet der Server den Abschluss
  als verständlichen Fehler.
- **Nebenbefund, nicht geändert:** `build_datev_export()` holt die Buchungen über
  `list_entries(..., limit=2000)` -- ein Zeitraum mit mehr als 2000 Buchungen würde still
  abgeschnitten. Bei der heutigen Größe (wenige Monteure) nicht erreichbar, für später notiert.
  **Behoben seit 1.8.7:** DATEV-Export, Stundenübersicht, Stundenzettel und CSV-Export holen mit
  `limit=None` alle Buchungen des Zeitraums; `limit` ist in `list_entries()` jetzt Pflicht.

`tests/test_v300_time_tracking_lock.py` (7 Tests, Gegenprobe mit abgeschalteter Prüfung rot).

## Krankheitssichtbarkeit: buero_auftrag sieht nur noch "abwesend" (seit 1.5.4)

Kurskorrektur zu 1.5.3, wo der Betreiber einen ersten Redaktions-Vorschlag noch abgelehnt hatte
("Unverändert lassen") -- in dieser Runde ausdrücklich erneut aufgegriffen: personenbezogene
Krankheit soll für `buero_auftrag` nicht mehr sichtbar sein, weder Art (Urlaub/Krankheit/
Fortbildung/Unbezahlt) noch der Freitext-Grund. Für die Kapazitätsplanung reicht "abwesend" mit
Zeitraum. `buero_finanzen`/`admin` sehen unverändert alles. Erst ein vollständiger Befund über
jede Stelle, an der Abwesenheiten erscheinen, dann die Klärung der Anlegen/Bearbeiten-Frage
("Backoffice liegt bei buero_auftrag -- wie geht das zusammen, wenn es die Art nicht mehr sehen
darf?"), dann gebaut -- exakt das erst-Befund-dann-Vorschlag-Vorgehen dieses Projekts.

### Sechs Fundstellen

1. **Plantafel-Konflikte** (`_conflicts()`, `app/planning.py`): das Konflikt-Label je Slot
   embeddete `f"{Name} · {absence_type}"` als fertigen Text.
2. **Planungsvorschlag** (`planning_suggestion()`): `absent_employees: [{name, type}]` je Tag.
3. **Team-Tageskapazität** (`planning_board()`, `team_capacity`): `absences: [{employee_id,
   name, type}]` je Team/Tag.
4. **Mitarbeiter-Tageskapazität** (`planning_board()`, `employee_capacity`): `absence:
   absence_type` je Mitarbeiter/Tag.
5. **Die Backoffice-Abwesenheitsliste selbst** -- der eigentliche Fund: **nicht** der separate
   `GET /api/planning/absences`-Endpunkt (den liest aktuell kein Template, nur `POST`/`DELETE`
   werden von `planning.html` genutzt), sondern `GET /api/planning`s Top-Level-Feld `absences`
   -- das ist die tatsächliche Datenquelle von `planning.html::renderAbsences()`. Der separate
   Endpunkt wurde trotzdem mitkorrigiert, für den Fall, dass er künftig doch gelesen wird.
6. **Änderungshistorie** (`GET /api/audit-logs`): doppelter Fund. Die GESPEICHERTE
   `entity_label`-Zeile ("Mitarbeiter-Abwesenheit") trug `absence_type` fest im Text -- anders
   als der `details`-Schnappschuss (JSON, redigierbar) ist ein Label bereits beim Schreiben in
   die Datenbank "gebrannt", eine nachträgliche Redaktion könnte den Text nicht zuverlässig
   wieder in Name/Typ zerlegen. UND der `details`-Schnappschuss selbst enthielt
   `absence_type`/`absence_category`/`notes` wie jedes andere Feld -- `redact_wage_snapshot()`
   (Rechtekonzept "Vier Rollen" Etappe 2) kennt nur Lohnfelder, keine Abwesenheitsfelder.

**Kein Fund**: Dashboard (das "Freigabe"-Widget ruft `GET /api/absence-requests?status=pending`
ohnehin nur für `admin` ab, `isAdmin?...:Promise.resolve([])` -- `buero_auftrag`/`buero_finanzen`
bekommen dort heute schon ein leeres Array, unabhängig von dieser Änderung) und Mitarbeiterseite
(`master_data.html`/`master_data_form.html` zeigen aktuell überhaupt keine Abwesenheiten, nichts
zu redigieren). Monteur (`field`) war bereits vor dieser Version durchgängig sicher: alle sechs
Fundstellen hängen an Endpunkten mit `require_min_role(ROLE_OFFICE_AUFTRAG)`, ein Monteur bekommt
403, bevor irgendeine Geschäftslogik läuft -- geprüft, nicht nur angenommen.

### Die Anlegen/Bearbeiten-Frage: "einmal eintragen, nie wieder lesen"

Drei Varianten wurden dem Betreiber vorgelegt, bevor gebaut wurde:
- **(A) Immer "unbekannt"**: `buero_auftrag` kann beim Anlegen nichts an Art eintragen, der Wert
  wird serverseitig immer auf den Migrations-Rückfallwert "unbekannt" gezwungen, `buero_finanzen`
  muss die echte Art in einem zweiten Schritt nachtragen.
- **(B) Einmal eintragen, nie wieder lesen** -- **gewählt**: `buero_auftrag` darf beim Anlegen
  weiterhin die echte Art eintippen (z. B. nach einem Telefonanruf "Mitarbeiter X ist krank"),
  sieht sie danach aber bei JEDEM Lesen -- auch der eigenen, soeben abgeschickten Anfrage -- nur
  noch als "abwesend". Kein Zusatzschritt für `buero_finanzen`, keine Warteschlange
  unzugeordneter Einträge.
- **(C) Anlegen/Bearbeiten komplett zu `buero_finanzen`**: wie beim Mitarbeiter-Bestand ohne
  Vergütung (Rechtekonzept Etappe 2) -- `buero_auftrag` verliert die Schreibrechte vollständig.

**Der Betreiber wählte (B)** -- keine Ausnahme "aber ich habe es doch gerade selbst getippt": die
Antwort auf den eigenen `POST`/`PUT` ist für `buero_auftrag` ebenso redigiert wie jede spätere
`GET`-Abfrage, konsequent durchgezogen in `_absence_out_for_role()`
(`app/routers/planning.py`).

**Nebenbefund, unabhängig vom eigentlichen Auftrag, aber notwendig für (B)**: `PUT
/api/planning/absences/{id}` überschrieb bisher jedes Feld blind
(`for k,v in payload.model_dump().items(): setattr(row,k,v)`). Ein Formular, das Art/Kategorie/
Notiz gar nicht mehr anzeigt (weil `buero_auftrag` sie nicht lesen kann), hätte sie beim
Speichern stillschweigend auf einen Leerwert zurückgesetzt -- dieselbe Gefahrenklasse wie bei
`upsert_roof_layer()` vor 1.2.19, dort behoben durch `exclude_unset`. Neues
`EmployeeAbsenceUpdate`-Schema (alle Felder optional, kein erzwungener Wert wie bei
`EmployeeAbsenceCreate`) + `payload.model_dump(exclude_unset=True)` -- ein Feld, das der Aufrufer
nicht mitsendet, bleibt unangetastet, unabhängig von der Rolle. Die Datums-Reihenfolge-Prüfung
(`end_date >= start_date`) läuft deshalb NICHT mehr im Pydantic-Validator (der kennt bei einem
Teil-Update nur die gesendeten Felder, nicht den gespeicherten Bestand), sondern im Router NACH
dem Zusammenführen mit den bereits gespeicherten Werten. `planning.html` selbst bietet aktuell
gar keine Bearbeiten-Funktion für Abwesenheiten an (nur Anlegen/Löschen) -- der Fund betraf also
noch keine akute Regression, war aber eine Falle für die nächste UI-Erweiterung.

### Umsetzung: rollenblinde Business-Logik, Redaktion im Router

Durchgängiges Prinzip, wie beim Rechtekonzept schon etabliert: `app/planning.py` kennt keine
Rollen, `app/routers/planning.py` entscheidet.

- **`EmployeeAbsencePlanningOut`** (neues Schema, Muster `EmployeeRosterOut`/`PropertyAccessOut`):
  `id`/`employee_id`/`employee_name`/`start_date`/`end_date` -- fehlt bewusst: `absence_type`,
  `absence_category`, `notes`. `_absence_out_for_role(role, data)` ist die EINE Stelle, die
  entscheidet (`has_min_role(role, ROLE_OFFICE_FINANZEN)` → `EmployeeAbsenceOut`, sonst
  `EmployeeAbsencePlanningOut`) -- verwendet von `list_employee_absences()`,
  `create_employee_absence()` UND `update_employee_absence()` gleichermaßen, Union-Response-Model
  auf allen drei Endpunkten.
- **`_conflicts()`** (`app/planning.py`) liefert für jede Abwesenheits-Konfliktzeile zusätzlich
  ein `label_redacted`-Feld ("… · abwesend" statt "… · Krankheit") -- **bewusst KEINE
  Zeichenketten-Zerlegung** eines bereits zusammengesetzten `"{Name} · {Art}"`-Textstrings im
  Router (fragil, falls ein Name selbst " · " enthält); die Funktion liefert beide fertigen
  Varianten, der Router (`_redact_board_absences()`) wählt nur noch aus.
- **`_redact_board_absences(board, role)`**/**`_redact_suggestion_absences(suggestion, role)`**
  (`app/routers/planning.py`, neu): reine Nachbearbeitung des von `planning_board()`/
  `planning_suggestion()` zurückgegebenen Dicts -- entfernt `"type"` aus `team_capacity`-
  Einträgen, ersetzt `employee_capacity`-Einträge durch die feste Zeichenkette `"abwesend"`,
  reduziert die Top-Level-`absences`-Liste auf die fünf feldsicheren Schlüssel, wählt je Slot das
  passende Konflikt-Label. Für `buero_finanzen`/`admin` unverändert (nur die internen
  `label_redacted`-Hilfsfelder werden aufgeräumt, damit sie nicht versehentlich mit ausgeliefert
  werden).
- **`planning.html::renderAbsences()`**: prüft `'absence_category' in x`, um zwischen dem vollen
  und dem reduzierten Schema zu unterscheiden -- zeigt "Abwesend" statt einer leeren
  " · "-Lücke, wenn die Felder fehlen. Kein Eingriff in die Kachel-/Konflikt-/Kapazitäts-Anzeige
  nötig: `renderBoard()`/`cellHtml()` lesen `c.absences.length` (unverändert korrekt, da nur die
  Länge zählt) bzw. `c.absence` (zeigt jetzt "abwesend" statt der echten Art, ohne Codeänderung,
  da der Router bereits die passende Zeichenkette einsetzt) bzw. `s.conflicts[].label`
  (unverändert korrekt, da der Router bereits das passende Label auswählt).
- **Änderungshistorie**: `app/audit.py::_normalize()`s `EmployeeAbsence`/
  `EmployeeAbsenceRequest`-Zweige nennen im gespeicherten Label künftig nur noch Name + Zeitraum,
  nie die Art -- 0 Bestandszeilen in der echten Datenbank (erneut frisch geprüft), also kein
  historischer Datenverlust durch diese Änderung. Neues
  `ABSENCE_ENTITY_TYPES`/`ABSENCE_FIELD_NAMES`/`redact_absence_snapshot()` (Gegenstück zu
  `WAGE_FIELD_NAMES`/`redact_wage_snapshot()`, aber entitätstyp-GEBUNDEN statt global -- `notes`
  ist nur bei diesen beiden Entitätstypen sensibel, bei jeder anderen Entität bleibt eine Notiz
  für `buero_auftrag` unverändert sichtbar). `app/routers/audit.py` überspringt zusätzlich
  Feldänderungs-Zeilen, deren `field_name` eines dieser drei Felder ist -- exakt das bereits für
  `WAGE_FIELD_NAMES` etablierte Muster, nur um eine zweite Feldmenge ergänzt.

### Angriffstest

`tests/test_v287_absence_visibility.py` (18 Tests) -- rekursiver Schlüssel-Scan (Fehlerklasse
`purchase_price`) über `GET/POST/PUT /api/planning/absences`, `GET /api/planning`,
`POST /api/planning/suggestion` und `GET /api/audit-logs`: `buero_auftrag` bekommt in KEINER
Antwort `absence_type`/`absence_category`/`notes`, auch nicht im Ergebnis der eigenen, soeben
abgeschickten Anfrage; `buero_finanzen`/`admin` sehen alles unverändert; `field` bekommt
durchgängig 403. Zusätzlich: das Teil-Update lässt Kategorie/Notiz tatsächlich unverändert, wenn
`buero_auftrag` sie nicht mitsendet (verifiziert über einen anschließenden `buero_finanzen`-Read);
die Datums-Validierung greift auch bei einem Teil-Update korrekt gegen den gespeicherten
Bestand. Ein bestehender Test aus 1.5.3
(`test_v286_schlechtwetter_und_abwesenheitskategorie.py::test_planning_absences_list_returns_category_and_supports_filter`)
wurde auf `buero_finanzen` umgestellt -- er prüft das Kategorie-Feld/den Filter selbst, nicht die
Rollenreduktion, die jetzt separat und ausführlicher in der neuen Testdatei steht. Volle Suite:
1620 Tests grün.
