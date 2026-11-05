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

## Liste, Gesamtzahl und Summen (seit 1.8.9)

Abschluss der Runden 1.8.6–1.8.9 gegen stilles Abschneiden von Zeitbuchungen:

- `GET /api/time-entries` liefert höchstens `limit` Buchungen (Vorgabe 500, neueste zuerst) und
  meldet die Gesamtzahl in der Kopfzeile `X-Total-Count`. Ein `limit` außerhalb von 1–2000 ergibt
  422, `list_entries()` wirft dann `ValueError` (vorher still auf 2000 gekappt).
- **Jede Seite, die diese Liste lädt, nimmt `fetchTimeEntries()` und zeigt
  `timeEntriesTruncatedNotice()` ("Liste gekürzt")** -- beide aus
  `app/templates/_time_entries_list.html`. Ein Strukturtest in
  `tests/test_v313_time_entries_total_count_and_sums.py` schlägt fehl, sobald eine Vorlage
  `/api/time-entries?` an diesem Helfer vorbei abruft.
- **Summen nie aus der Liste bilden**, sondern über `GET /api/time-entries/summary`
  (`summarize_entries()`, dieselben Filter über `_entry_filters()`): `entry_count`,
  `booked_count`, `total_hours`, `productive_hours`, `travel_hours`, `employee_count`, Stunden nur
  aus gebuchten Zeiten. Genutzt von Einsatzbericht-Seite, Projektmappe, Auftragsseite und Dashboard.
- Liste, Gesamtzahl und Summen teilen eine Sichtbarkeitsregel, `_visible_employee_id()`: ein
  Monteur sieht und summiert nur eigene Buchungen.
- Bewusst noch aus der angezeigten Liste gerechnet: die Tagessummen von `time_tracking.html` und
  `time_tracking_field.html` sowie Tages- und Monatssumme von `field_timesheet.html` (ein
  Mitarbeiter, Grenze praktisch nicht erreichbar, bei Kürzung steht der Hinweis darüber). Das
  Stundenzettel-PDF des Monteurs (`app/field_timesheet_pdf.py`) kappt weiterhin bei 2000.
- **Nachtrag (1.8.10): Abgleich mit den alten Oberflächensummen.** Unterhalb der Grenzen liefern
  die Serversummen dieselben Werte wie die bis 1.8.8 in der Oberfläche gebildeten, auch mit
  Schlechtwetter, frei gepflegten Zeitarten und laufenden Timern (die tragen immer 0 Std.:
  `start_timer()`/`start_group_timer()` setzen 0, `update_entry()` lehnt laufende ab). Einmal per
  Wegwerfprüfung verglichen (alte und neue Formeln in node), kein Dauertest. Zwei Abweichungen:
  "Mitarbeiter mit Buchung" zählt nach `employee_id` statt nach Namen (zwei gleichnamige
  Mitarbeiter zählen jetzt zweifach), und `quantize()` ohne Rundungsart rundet `ROUND_HALF_EVEN`
  (wie `order_actual_hours()` und die Backoffice-Summen), die alte Oberfläche per `toLocaleString`
  kaufmännisch -- sichtbar nur bei exakt halben Hundertstel (1,1250 Std.: alt 1,13, neu 1,12).
  Nicht geändert. **Behoben seit 1.8.11:** Alle Stundensummen runden kaufmännisch über
  `app/rounding.py`, 1,1250 Std. ergibt wieder 1,13 -- siehe `docs/archiv/kaufmaennisches-runden.md`.

## Kalenderdatum in Europe/Berlin statt UTC (seit 1.8.10)

`toISOString().slice(0, 10)` liefert das Datum in UTC: für Mitternacht Ortszeit
(`new Date(jahr, monat, 1)`) immer den Vortag, für "jetzt" zwischen 0 und 1 Uhr (Winterzeit) bzw.
2 Uhr (Sommerzeit) ebenfalls. Das Dashboard ("Meine Stunden (Monat)") zählte dadurch jeden Tag den
letzten Tag des Vormonats mit und den letzten Tag des Monats nicht. Seit 1.8.10 nimmt es
`berlinMonthRange()` aus dem geteilten Helfer `app/templates/_berlin_date.html`
(`Intl.DateTimeFormat` mit `timeZone: 'Europe/Berlin'`, unabhängig von der Zeitzone des
Browsers). `tests/test_v314_dashboard_month_berlin.py` führt Helfer und Dashboard-Funktion in node
aus, an Monats- und Jahreswechseln, mit vier Zeitzonen des Prozesses (übersprungen ohne node).

**Offen, nur aufgelistet (Suche vom 29.09.2026) -- dasselbe Muster an weiteren Stellen:**

- *Im Browser, aus UTC abgeleitet (unabhängig vom Server):* `time_tracking.html` `today()` (Z. 29:
  "Heute"-Liste und -Summen, Vorgabedatum Nachtrag und Auswertung); `time_tracking_field.html`
  `today()` (Z. 223: "Heute"-Summen, Liste endet bei `end_date=today()`, Vorgabedatum Nachtrag),
  dort auch Z. 393 (Beginn 14-Tage-Fenster, harmlos); `service_reports.html` Z. 1386 (Datum der
  Zeitbuchung am Einsatzbericht) und Z. 331 (Ausführungsdatum); `incoming_invoices.html` Z. 549
  (Bezahltdatum beim Markieren als bezahlt); `project_folder.html` Z. 151 (nächste Fälligkeit beim
  Wartungsvertrag aus dem Projekt); `planning.html` Z. 41 (`today=iso(new Date())`,
  Heute-Markierung der Plantafel; `iso()` sonst nur mit 12-Uhr-Daten, korrekt).
  Geprüft, korrekt: `time_backoffice.html` `dateISO()` (Ortsdatum, auch Monatsgrenzen und
  Export-Zeiträume), `quote_editor.html` `localToday()`, `time_tracking_field.html` Z. 493.
- *Auf dem Server, `utcnow()`-Zeitstempel als Ortszeit gedruckt (unabhängig von der
  Serverzeitzone):* `app/service_report_pdf.py` Z. 387/395/407 (Unterschriftszeitpunkt Monteur
  und Kunde), `app/checklist_pdf.py` Z. 130/143/201 (`completed_at`) und Z. 188 (Unterschrift),
  `app/projects.py` Z. 64 (Angebotsdatum und Bindefrist neuer Angebote aus `created_at`).
- *Auf dem Server über `date.today()`/`datetime.now()` -- nur falsch, wenn der VPS in UTC läuft
  (nicht dokumentiert, `timedatectl` klärt es):* Zeiterfassung `app/time_tracking.py`
  Z. 124/142/453/465 (Buchungsdatum von Timer und Gruppen-Timer), `app/routers/time_tracking.py`
  Z. 190/326 (Sperrprüfung beim Timerstart mit dem Datum des Vortags), Z. 213,
  `app/work_time_models.py` Z. 36/202/243/250 (Arbeitszeitmodell, automatische Pause),
  `app/mobile_settings.py` Z. 38 mit `app/routers/field_view.py` Z. 87 (Feierabend-Abmeldung 1–2
  Std. zu spät), `app/routers/field_view.py` Z. 195 (Vorgabemonat Monteur-Stundenzettel),
  `app/planning.py` Z. 651/681/776/837
  (Einsätze heute, buchbare Aufträge), `app/productive_hours.py` Z. 124/286; Fristen
  `app/invoices.py` Z. 126/529/736/831, `app/reminders.py` Z. 126/176/392,
  `app/incoming_invoices.py` Z. 80/87/94/418 (Skonto), `app/maintenance_contracts.py`
  Z. 104/108/123/468/730 (Texte 562/580/663), `app/operational_assets.py` Z. 95/102/658,
  `app/recurring_costs.py` Z. 129/136/380, `app/findings.py` Z. 142/247,
  `app/service_reports.py` Z. 511, `app/quick_service_orders.py` Z. 58, `app/projects.py` Z. 653;
  Nummernkreise `app/settings.py` Z. 53/84/108/135/171 (Jahr in der Silvesternacht).

**Nachtrag (1.8.12): Server-Teil behoben.** Der VPS läuft tatsächlich in UTC (`timedatectl`:
Etc/UTC). `app/berlin_time.py` ist seither die eine Stelle für "jetzt" und "heute":
`berlin_now()` (naive Ortszeit), `berlin_today()` (Geschäftsdatum), `to_berlin()` (gespeicherten
Zeitstempel für die Anzeige umrechnen, naive Werte gelten als UTC). Die Uhr steckt in
`_utc_now()`, Tests setzen dort eine feste Zeit ein. Alle Stellen der beiden Server-Absätze oben
sind umgestellt, dazu zwei weitere: `app/checklist_rules.py::_task_values()` (Text "abgeschlossen
am" und Fälligkeit der Aufgabe aus `completed_at`) und `app/routers/planning.py` (Vorgabejahr beim
Abruf der Schulferien). `tests/test_v316_berlin_time.py` sucht `app/` nach `date.today()`,
`datetime.today()` und `datetime.now()` ohne Zeitzone ab.

Zwei Arten gespeicherter Zeit, nicht verwechseln: Zeitstempel aus `datetime.utcnow()` sind naive
UTC und bleiben es (`utcnow()` und die Kalender-Synchronisation bewusst unangetastet); Beginn und
Ende einer Zeitbuchung sind naive Ortszeit, weil man sie von Hand so eintippt und
`time_backoffice.py` sie so druckt. Der Timer schreibt deshalb `berlin_now()`, nicht UTC.

Weiter offen, alle im Browser (unabhängig von der Serverzeitzone):
- die `today()`-Stellen aus dem ersten Absatz oben;
- naive UTC-Zeitstempel ohne `'Z'` an `new Date()` übergeben, der Browser liest sie als Ortszeit
  (Anzeige 1–2 Std. zu früh): `invoice_detail.html` Z. 159, `order.html` Z. 58 (E-Mail-Versandzeit)
  und Z. 77, `quote_editor.html` Z. 260, `customer.html` Z. 207 und `project_folder.html` Z. 180
  (Hochladezeit), `mahnwesen.html` Z. 127 (Datum per `slice(0,10)`, 0–2 Uhr Vortag). Richtig mit
  `+'Z'`: `address_import.html` Z. 208, `operational_asset_field.html` Z. 75. Suche vom 29.09.2026
  nur über diese Muster, nicht vollständig.

**Nachtrag (1.8.87): "heute" im Browser behoben** (Vorgabe R4c "Vorweg" 1, Anlass `klicktest_teil_updates` um
Mitternacht). Jede Vorlage bildet das heutige Datum über `_berlin_date.html` (`berlinToday()`, `berlinMonth()`,
`berlinTime()`, `berlinAddDays()`, `localDateIso()`, `berlinTodayDate()`) -- die `today()`-Stellen aus dem ersten
Absatz oben, dazu die Stellen, die die Zeitzone des Geräts nahmen (Kalender, Aufgaben, Befunde, Stundenzettel,
Checkliste "mit jetzt vorbelegen", Angebot `localToday()`, Dashboard, Einstellungen). `tests/test_v390_browser_datum.py`
lässt in den Vorlagen `toISOString()`, `new Date()` und `Date.now()` ohne Argument nur als begründeten Zeitpunkt zu
(`ERLAUBT`), dazu kein `getTimezoneOffset()`/`toDateString()`; Klicktest `scripts/klicktest_browser_datum.py` (Instanz
und Browser um 00:30 Uhr, Browser in UTC und New York). Weiter offen: die naiven UTC-Zeitstempel aus dem Absatz direkt
darüber (Anzeige und `slice(0, 10)` eines Zeitstempels) -- `docs/archiv/befund-vor-echtbetrieb.md`, "Umsetzung 1.8.87",
Festlegung 2. Details dort.

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

## Ändern einer Buchung ist ein Teil-Update (seit 1.8.25)

`PUT /api/time-entries/{id}` und `PUT /api/time-entry-groups/{id}` übernehmen nur gesendete Felder
(`_merge_time_changes()` in `app/routers/time_tracking.py`). Die mobile Zeiterfassung schickte beim
Ändern die Standardpause und keine LV-Position mit -- jede Korrektur ersetzte die gebuchte Pause und
leerte die LV-Position, bei Kolonnenbuchungen für alle nicht einzeln geänderten Mitglieder. Jetzt
schickt sie beim Ändern nur, was der Dialog zeigt (Auftrag, Datum, Zeitart, Tätigkeit, Stunden, Notiz),
beim Anlegen weiter die Standardpause. Die Backoffice-Korrektur schickt weder Pause noch Mitarbeiter.
Wechselt der Auftrag ohne neue LV-Position, entfällt die alte. Fehlt `employee_id`, bleibt der
Mitarbeiter der Buchung. Details und Tests: `docs/archiv/teil-updates.md`.

## Buchen nach der Schlussrechnung; Gewährleistungs- und Kulanzstunden (festgehalten 13.10.2026, nicht gebaut)

Befund (Stand 1.8.95): nach der Schlussrechnung bzw. der abschließenden Rechnung aus Aufwand buchen
Monteur und Büro weiter auf den Auftrag, die Stunde wird nie abgerechnet (Rechnung aus Aufwand danach
409), ohne Hinweis beim Buchen; beim Status "abgeschlossen" fehlt der Auftrag nur in den Auswahllisten.
Festgehalten für Stufe 2d und die Rüge: Gewährleistungs- und Kulanzstunden auf den ursprünglichen
Auftrag, Zeitbuchung einem Mangel zugeordnet oder als Kulanz gekennzeichnet, nie abrechenbar, in der
Nachkalkulation getrennt als "davon Mängelbeseitigung / Kulanz"; dazu "Abschließen ohne Rechnung" als
Parkplatz vor dem Echtbetrieb. Wortlaut und Befund: `docs/archiv/befund-vor-echtbetrieb.md`,
"Entscheidungen Rechnungen" (Ergänzung nach Nachfrage 10 zu 1.8.95) und "Parkplatz vor dem Echtbetrieb".

## Zeitregeln mit abgeschaltetem Standardmodell (seit 1.9.14)

`update_time_settings()` prüft „aktiv“ nur bei einem neu gewählten Standard-Arbeitszeitmodell (Regel 22); bis 1.9.13 ließen sich die
Zeitregeln nach dem Abschalten des Standardmodells nicht mehr speichern. Herleitung und Test: `docs/archiv/redesign.md`, „Runde 7“,
„Punkt 2 (1.9.14)“; `tests/test_v448_zeitregeln_standardmodell.py`.

## „Ändern“ bei anderem Auswertungsdatum (seit 1.9.15)

In der Büro-Zeiterfassung sucht „Ändern“ die Buchung in der Liste „Heutige Buchungen“ und in der Auswertung; bis 1.9.14 nur in der
Auswertung -- bei einem anderen Datum tat der Knopf still nichts. Steht sie in keiner, sagt die Seite das. Herleitung:
`docs/archiv/redesign.md`, „Runde 7“, „Punkt 3 (1.9.15)“; `tests/test_v449_zeiterfassung_aendern.py`.

## „Heute“: Zeitart wechseln und Vorschau „Ende nachtragen“ (seit 1.9.44)

Für „Heute“ auf /mobil (Stufe 4, R2, `docs/archiv/redesign.md`, „R2 Punkte 2–5 (1.9.44)“) zwei neue Wege und eine gemeinsame Rechnung:
`ende_rechnen(db, employee_id, beginn, ende, mindestpause)` liefert anwesend, Pause (`pause_nach_zeitregel()`) und gebuchte Stunden
(`gebucht_nach_zeitregel()`); Stopp, Gruppen-Stopp (je Mitglied), Zeitart wechseln und `ende_vorschau()` nehmen sie, Ende nachtragen über
Stopp bzw. Gruppen-Stopp. `GET /api/time-entries/{id}/ende-vorschau?ende=…` prüft wie das Nachtragen (Rechte, Monat abgeschlossen,
Kolonnenführer) und bucht nichts. `POST /api/time-entries/{id}/zeitart-wechseln` beendet die laufende Zeit jetzt und beginnt im selben
Augenblick eine neue (LV-Position und Tätigkeit wie bisher) -- nicht für eine Zeit von früher und nicht für eine laufende Gruppenzeit (409).

**Befund (nur berichtet, R2 Punkt 8): die Pausenregel rechnet je Buchung, nicht je Tag.** `pause_nach_zeitregel()` bekommt die
Anwesenheit genau der Buchung, die gerade endet (Stopp, Gruppen-Stopp, Ende nachtragen, Nachtrag mit Von/Bis); frühere Buchungen desselben
Tages zählen nicht mit. Vorgabe der Grunddaten: ab 6 h Anwesenheit 30 min, ab 9 h 45 min.
- Fahrzeit 06:15–07:00 (0:45 h, keine Pause) + Baustelle 07:00–16:00 (9:00 h, 45 min): zusammen 45 min, gebucht 0,75 + 8,25 = 9,00 h -- je
  Tag (9:45 h) wären es auch 45 min, hier zufällig gleich. Mit Baustelle bis 15:45 (8:45 h, 30 min) wären es je Buchung 30 min, je Tag
  (9:30 h) 45 min.
- Zwei Buchungen à 5 h am selben Tag: je Buchung unter 6 h, keine Pause, gebucht 10,00 h; je Tag (10 h) wären es 45 min, gebucht 9,25 h.
- „Zeitart wechseln“ (seit 1.9.44) teilt einen Tag in Buchungen und macht das häufiger: Baustelle 07:00–12:00, dann Werkstatt bis 16:00 --
  5 h + 4 h, keine Pause; je Tag (9 h) 45 min.
- § 4 ArbZG rechnet je Arbeitstag („mehr als sechs bis zu neun Stunden“ 30 min, „mehr als neun Stunden“ 45 min); die Regeln im Code gelten
  „ab“ der Schwelle (≥), das Gesetz „mehr als“.

## Angezeigte Zeitpunkte in Europe/Berlin (seit 1.9.46)

Stufe 4, R2, Punkt 7 (Befund der Monteurin: Unterschrift auf der Berichtsseite 15:33, im PDF 17:33). Der offene Punkt „Zeitstempel im Browser
noch aus UTC gelesen“ (oben, „Weiter offen“; die dortige Liste vom 29.09.2026 war veraltet -- die Versandzeiten zeigen die Seiten seit 1.8.17
über `_email_dispatch.html` mit den `*_local`-Feldern) ist damit erledigt:

- **Helfer** `berlinZeitpunkt(wert, art)` in `_berlin_date.html`: naives UTC (wie die API es liefert, ohne 'Z'; mit 'Z' oder Versatz
  ebenso) -> Europe/Berlin über `Intl.DateTimeFormat(…, {timeZone: 'Europe/Berlin'})`; `'zeit'` „TT.MM.JJJJ HH:MM“ wie die PDFs, `'datum'`
  „TT.MM.JJJJ“, `'tag'` „JJJJ-MM-TT“. Nicht für naive Ortszeit (Beginn/Ende einer Zeitbuchung, Termine, Wiedervorlage, `datum_uhrzeit` einer
  Checkliste) und nicht für `*_local` (kommt in Berlin vom Server).
- **Umgestellt, vorher falsch** (UTC-Uhr bzw. UTC-Datum): `service_reports.html` Unterschrift „Kunde: … (… Uhr)“; `customer.html` und
  `project_folder.html` Hochladezeit; `order.html` Revisionen; `_abnahme.html` „abweichend festgelegt am“ und Historie der Gewährleistung;
  `inquiries.html` „angelegt“; `users.html` letzte Anmeldung; `invoice_detail.html` Nebenforderung „gebucht“; `mahnwesen.html` „versendet“;
  `mobil_objekt.html` und `property.html` Dokumente; `operational_asset.html` Dokumente, „gemeldet“ (2) und „als repariert markiert“;
  `recurring_costs.html` Dokumente; `roof_area.html` Mängelhistorie.
- **Umgestellt, vorher nur im Berliner Browser richtig** (`+'Z'`, `toLocale…` ohne Zeitzone): `checklist.html` (über `fmtDateTime`:
  angelegt/abgeschlossen, Fassung im Versand, Fassungen und „verworfen am“, Folgen, ausgelöste Aufgaben, Stand der Unterschrift des
  Auftraggebers), `_checklists_section.html` (2), `checklists.html`, `history.html` und `project_folder.html` Änderungsprotokoll,
  `address_import.html` Läufe, `checklist_template.html` Veröffentlichung, `operational_asset_field.html` Bereitschaft, `order.html`
  Vertragsgrundlage geändert, `project_folder.html` Vollmachten (2), `time_backoffice.html` Abschluss.
- **Unverändert, schon richtig**: `*_local` aus dem Server (Versandverlauf, Abnahmen, Mängel, Vertragsfassungen, Anhänge der Checkliste);
  naive Ortszeit (Kalender, Termine in Projektmappe und Angebot, Anfragen, Dashboard, Zeiterfassung, „Heute“).
- ~~**Offen (nicht geändert)**: im Änderungsprotokoll (`history.html`, Projektmappe) stehen alter und neuer Wert als roher ISO-Text aus
  `app/audit.py::_text()` -- je nach Spalte UTC oder Ortszeit, im Browser nicht unterscheidbar; das bräuchte die Spalte auf dem Server.~~ Seit 1.9.123
  erledigt: `app/verlauf_namen.py` kennt beim Lesen die Spalte -- naive UTC in Europe/Berlin, naive Ortszeit (`ORTSZEIT`: Beginn/Ende einer
  Zeitbuchung und eines Termins, Besuch und Wiedervorlage einer Anfrage) unverändert, beides „TT.MM.JJJJ HH:MM“ (`docs/archiv/redesign.md`,
  „Nachrunde, Punkt 5“).
  ~~Ebenso auf dem Server: `app/findings.py` filtert `Finding.created_at` (UTC) mit Mitternacht eines Kalendertags (Grenzen um 1–2 Std.
  verschoben)~~ -- seit 1.9.52 behoben: `app/berlin_time.py::berlin_tag_beginn_utc()` (Mitternacht in Europe/Berlin als naive UTC), siehe
  „Tagesgrenzen gespeicherter Zeitstempel (seit 1.9.52)“.

## Pausenregel je Tag (seit 1.9.48)

Entscheidung Tobias vom 23.10.2026 (Stufe 4, R2 Nachrunde, Punkt 1), nur für neue Buchungen. Befund aus R2: die Pause hing an der einzelnen
Buchung -- zwei Buchungen à 5 h am selben Tag (z. B. Baustelle, dann Werkstatt nach „Zeitart wechseln“) bekamen keine Pause, eine Buchung
über 9 h am Stück 45 min.

- **Schwellen „mehr als“**: über 6:00 h Anwesenheit 30 min, über 9:00 h 45 min -- die Werte bleiben in den Grunddaten bzw. den Zeitregeln,
  nur der Vergleich in `app/work_time_models.py::automatic_break_minutes_for_duration()` ist seit 1.9.48 `>` (bis 1.9.46 `>=`). Die Funktion
  hat nur einen Aufrufer (`pause_nach_zeitregel()`), alte Buchungen werden nicht umgerechnet.
- **Der Tag**: maßgeblich ist die Anwesenheit der Person am Starttag (`work_date`) über alle gebuchten Zeiten (`booked`) samt der neuen:
  Ende − Beginn, bei einer reinen Dauer Stunden + Pause (`buchungen_am_tag()`, `_anwesend_der_buchung()`).
- **Was abgezogen wird**: Pflichtpause des Tages − schon abgezogene Pausen des Tages, mindestens die eingegebene Pause, höchstens die
  Anwesenheit der neuen Buchung (`pause_nach_zeitregel()`). Frisst die fehlende Pause die ganze Buchung, wird sie mit 0 h geschlossen (Stopp,
  Gruppen-Stopp, Ende nachtragen, Wechsel); ein Nachtrag mit Von/Bis wird dann abgelehnt wie bisher („Nach Abzug der Pause bleibt keine
  Arbeitszeit.“).
- **Überall eine Funktion**: Stopp, Gruppen-Stopp (je Mitglied seine eigene Tagesrechnung), Ende nachtragen, Nachtrag mit Von/Bis, Zeitart
  wechseln (die abgeschlossene erste Buchung zählt für die zweite) und die Vorschau von „Ende nachtragen“ -- über `ende_rechnen()` bzw.
  `nachtrag_nach_zeitregel()`.
- **Tag zusammen**: `tag_stand()` -- gebuchte Stunden des Tages und Zahl der Buchungen; in der Antwort jeder Buchung (`TimeEntryOut`,
  beim Gruppen-Stopp für den, der stoppt) und in der Vorschau (`TimeEndeVorschauOut`). Angezeigt als h:mm, nur bei mehr als einer Buchung.
- Festlegungen und Tests: `docs/archiv/redesign.md`, „R2 Nachrunde, Punkt 1 (1.9.48)“.

## Tagesgrenzen gespeicherter Zeitstempel (seit 1.9.52)

Wer gespeicherte Zeitstempel (naive UTC aus `datetime.utcnow()`) nach Kalendertagen filtert, nimmt `app/berlin_time.py::berlin_tag_beginn_utc(d)`
als Grenze: „am Tag d“ heißt `berlin_tag_beginn_utc(d) <= t < berlin_tag_beginn_utc(d + 1 Tag)`. `datetime.combine(d, datetime.min.time())`
wäre UTC-Mitternacht, 1 Std. (Winter) bzw. 2 Std. (Sommer) zu spät. Erste Stelle: der Datumsfilter der Befundliste
(`app/findings.py::list_findings()`, bis 1.9.51 mit UTC-Mitternacht). Durchgesehen (`datetime.combine(…, datetime.min.time())` unter `app/`):
`app/notice_letters.py` (Zustelldatum als Anzeige, kein Filter) und `app/outlook_calendar_sync.py` (eigene Umrechnung, bewusst unangetastet)
-- keine weitere Stelle dieser Art. Test `tests/test_v479_befunde_tage_berlin.py`.

## „Tag zusammen“ = Anwesenheit des Tages (seit 1.9.53)

Entscheidung Tobias (23.10.2026, ersetzt Festlegung 1.9.48 Nr. 4): „Tag zusammen“ ist die Anwesenheit der Person am Starttag über alle
gebuchten Zeiten samt der neuen, vor der Pause -- die Zahl, nach der die Pause bemessen wird (`app/time_tracking.py::_anwesend_summe()`, von
`pause_nach_zeitregel()`, `ende_rechnen()` und `tag_stand()` gemeinsam genutzt). 1.9.48–1.9.52 war es die Summe der gebuchten Stunden: bei
„Anwesend 9:00 h · Pause − 0:45 h“ stand „Tag zusammen 9:00 h“ (0,75 + 8,25 gebucht) da und erklärte die 45 min nicht. Die gebuchten Stunden
bleiben dezimal. Anzeige: Vorschau „Anwesend 9:00 h · Tag zusammen 9:45 h · Pause nach Zeitregel − 0:45 h“ / „Gebucht werden 8,25 h“; Ergebnis
auf „Heute“ „Feierabend gebucht: anwesend 4:15 h · Tag zusammen 9:15 h · Pause nach Zeitregel − 0:45 h · gebucht 3,50 h“; Zeiterfassung der
Monteurin „Gestoppt/Ende nachgetragen/Nachgetragen: anwesend … · Tag zusammen … · Pause … · gebucht … h“. „Tag zusammen“ nur, wenn der Tag
schon Buchungen hat. Festlegungen: `docs/archiv/redesign.md`, „R2 Nachrunde 2, Punkt 1 (1.9.53)“.

## Ändern nach der Tagesregel, Pausen je Tag (seit 1.9.57)

Ändern mit Von/Bis (`PUT /api/time-entries/{id}`) rechnet wie ein Nachtrag: `nachtrag_nach_zeitregel(…, ohne_id=<Buchung>)` -- der Tag ohne die
alte Fassung, Rundung der Zeitregeln, Beginn und Ende neu; andere Buchungen nie angefasst. Nach Ändern oder Löschen kann die abgezogene Pause
eines Tags nicht mehr zur Zeitregel passen: `pausen_vorschau()` sagt das (Summe abgezogen gegen die Summe, die die Regel den Buchungen in der
Reihenfolge des Tags gäbe) und zeigt je Buchung alt -> neu; `pausen_neu_rechnen()` bucht genau diese Vorschau (sonst 409), nur auf Klick, mit
einer Zeile „Pausen neu gerechnet“ im Verlauf. Festlegungen: `docs/archiv/redesign.md`, „R3, Server (1.9.57)“.

## Umsetzung 1.9.146: Abwesenheiten, ein Weg (Stufe 6, R1, Punkt 4)

Befund Stufe 6: D2 (zwei Wege), P1 (genehmigte löschen: PostgreSQL 500, keine Meldung), P2 (Dialog zeigt allen „Abwesend“), P9 (Büro – Auftrag trägt für jede Person jede Art ein), L3 (PUT ohne Oberfläche).

- `POST /api/planning/absences` ruft `eintragen()`: Antrag über `_antrag_anlegen()`, beim Admin gleich `_entscheiden()`, ein Commit. Scheitert das Genehmigen (schon eine Abwesenheit im Zeitraum, 422), bleibt auch kein Antrag.
- Rechte aus `routers/absence_requests.py::antrag_fuer()`, wie `POST /api/absence-requests`. `GET /api/planning` nennt sie der Seite (`rechte`), die Vorlage fragt keine Rolle ab.
- `DELETE /api/planning/absences/{id}`: `abwesenheit_loeschen()` löst zuerst den Verweis im Antrag (`approved_absence_id` hat kein ON DELETE). Status „cancelled“, Vermerk `ABWESENHEIT_GELOESCHT`.
- Die Antwort bleibt für Büro – Auftrag ohne Art und Notiz („Einmal eintragen, nie wieder lesen“, Abschnitt unten), dazu `antrag_id` und `status`.
- Migration `b2c7f4e19a06`: `INSERT … SELECT` je Abwesenheit ohne Antrag, Vermerk `MERKER`, ohne Antragsteller und Entscheider, Zeitpunkt = Anlegen der Abwesenheit. Zweimal laufen ändert nichts; `downgrade()` entfernt genau diese Zeilen. Geprobt auf einem Bestand gegen SQLite und PostgreSQL im Wegwerf-Schema.

### Festlegungen 1.9.146 (Bitte bestätigen)

1. Eine genehmigte Abwesenheit löscht nur der Admin, er entscheidet auch die Anträge; Büro – Finanzen und Büro – Auftrag sehen den Knopf nicht (403).
2. Der Antrag folgt mit dem vorhandenen Status „zurückgezogen“ und dem Vermerk „Die genehmigte Abwesenheit wurde gelöscht.“; kein neuer Status.
3. `PUT /api/planning/absences/{id}` entfällt (405), `EmployeeAbsenceUpdate` ist weg. `GET` bleibt.
4. Der Admin bekommt beim Überlappen 422 statt einer zweiten Abwesenheit (bis 1.9.145 ging das direkt, die zuletzt gelesene galt).
5. Ein offener Antrag zählt auf der Tafel weiter nicht: keine Warnung, keine Kapazität. Zu sehen ist er unter „Zeiten“.
6. „Zeiten → Abwesenheiten“ öffnet mit „Alle“ statt „Offen“; was wartet, steht weiter unter „Prüfen“ und in der Zahl am Reiter.
7. Der Antrag aus der Migration trägt den Vermerk „Auf der Plantafel eingetragen (vor 1.9.146)“; „Zeiten“ zeigt ihn wie jeden Vermerk als „Freigabe: …“.

### Tests und Prüfung

Angepasste Erwartungen (Regel 28): `test_v287::test_buero_auftrag_create_response_hides_category_type_and_notes`, Aufbau: Büro – Auftrag trägt für sich ein. `test_v287` (fünf weitere Tests) und `test_v286::test_planning_absences_list_returns_category_and_supports_filter`, Aufbau: die Abwesenheit legt der Admin an, von Büro – Finanzen wäre sie ein offener Antrag. `test_v287::test_partial_update_by_buero_auftrag_leaves_category_and_notes_untouched` und `::test_partial_update_rejects_end_before_start_against_stored_value` entfallen, altes Soll: PUT ändert, neues Soll: 405 (`test_v566::test_put_entfaellt`). Migrationsprobe: `test_v566::test_migration_sqlite`, `::test_migration_und_loeschen_unter_postgresql`. `klicktest_zeiten`, Prüfung „Bea: zurückgezogen“, altes Soll: keine Zeile mehr (Filter „Offen“), neues Soll: die Zeile bleibt als „zurückgezogen“ ohne Knopf (Filter „Alle“). `test_v447`: `planning.html` `absenceEmployee` neu in `KLASSEN` als „neu“.

Nachtrag 1.9.147: `tests/test_v566_abwesenheiten_migration.py` probt die Migration `b2c7f4e19a06` über die ganze Kette mit alembic auf einem Bestand (hoch, runter, wieder hoch), gegen SQLite und PostgreSQL im Wegwerf-Schema.

## Umsetzung 1.9.152: ein offener Antrag ist ein Hinweis (Stufe 6, R1 Nachrunde, Punkt 3)

Entscheidung Tobias, löst die Festlegung 1.9.146 Nr. 5 ab („zählt auf der Tafel nicht: keine Warnung, keine Kapazität, zu sehen unter ‚Zeiten‘“). `app/planning.py::_conflicts()` hängt je Person der Kolonne mit offenem Antrag im Zeitraum des Einsatzes einen Hinweis `antrag_offen` an (`_offene_antraege()`: eine Abfrage). Die Kapazität liest weiter nur `EmployeeAbsence`, also nur Genehmigtes. `_konflikte_fuer_rolle()` wählt die Fassung ohne Art für alles, was `label_redacted` trägt, nicht mehr nach der Art des Konflikts: ein neuer Konflikt mit Art kann das Schwärzen so nicht vergessen.

### Festlegungen 1.9.152 (bestätigt am 31.10.2026)

1. „Antrag offen“ färbt den Balken nicht und zählt nicht in `conflict_count` (`FAERBT_NICHT`); Feiertag und Kapazität färben weiter rot, bis die Zeichnung kommt (dort grauer Punkt für alle Hinweise). Sonst stünde die halbe Tafel rot, sobald viele Urlaub beantragen.
2. Der Hinweis nennt den ersten Tag des Antrags im Einsatz, nicht den ganzen Zeitraum des Antrags.
3. Der Balken zeigt eine eigene Zeile „Antrag offen: <Person>“, im Vorgriff auf die Zeichnung; ohne sie sähe man den Antrag nur, wenn man den Einsatz öffnet.

### Tests und Prüfung

`tests/test_v570_antrag_offen_hinweis.py`; `klicktest_plantafel_konflikte`: sechs Prüfungen „Antrag offen: …“ als Admin, zwei als Büro – Auftrag, Bilder `antrag_offen_admin`, `antrag_offen_buero_auftrag`. Angepasste Erwartungen: keine.

## Befund und Umsetzung 1.9.153: Kategorie und Art (Stufe 6, R1 Nachrunde, Punkt 4, Befund D2)

### Befund

Welches Feld zählen „Monat & Lohn“ und der Lohnexport? **Keines.** `app/zeiten.py::monat()`, `build_datev_export()`, `build_time_csv()`, `build_timesheet_pdf()` und `backoffice_summary()` lesen nur `TimeEntry`; `monat()` zählt dazu nur die offenen Anträge (`antraege_offen`). `EmployeeAbsence` kommt in keiner dieser Funktionen vor, und `TimeEntry.entry_type` kennt weder Urlaub noch Krankheit (site, travel, workshop, other, weather_winter, weather_summer). Urlaub und Krankheit stehen also in keiner Lohndatei; `tests/test_v571_kategorie_und_art.py` belegt das (dieselbe Datei und dieselben Zeilen mit und ohne Abwesenheit).

Wer liest was: die **Kategorie** zählt nur `app/productive_hours.py::sick_days_actual()` (`== "krankheit"`, Ist-Wert Krankheitstage, rein zur Orientierung), dazu der Filter von `GET /api/planning/absences`. Die **Art** ist nur Anzeige: Text der Warnung „Person abwesend“, Zelle der Tafel, Planungsvorschlag. Die Kapazität zählt jede Abwesenheit gleich, ohne auf eines der Felder zu sehen. Ein Widerspruch wirkte also so: „Krankheit“ + „Urlaub“ zählt als Krankheitstag und steht auf der Tafel als Urlaub; „Urlaub“ + „Krankheit“ umgekehrt.

Gehört jede Art zu einer Kategorie? **Nicht jede.** Grundeinstellung: Urlaub -> Urlaub; Krankheit -> Krankheit; Weiterbildung und Berufsschule -> Fortbildung. Freizeitausgleich hat keine passende Kategorie (bezahlte Freistellung, weder Urlaub noch unbezahlt). Sonstiges passt zu allen. Die Kategorie „Unbezahlt“ hat keine eigene Art. Die Liste lässt sich unter Einstellungen frei erweitern, dort angelegte Arten kennt das Programm nicht.

### Umsetzung

`ART_KATEGORIEN`, `art_kategorien()`, `ist_widerspruch()`, `arten_fuer_auswahl()` in `app/absence_requests.py`; `_antrag_anlegen()` -- der eine Weg, Regel „Ein Weg für Abwesenheiten“ -- lehnt ab (422) und trägt ohne Art den Namen der Kategorie ein. `_abwesenheit.html` füllt die Auswahl auf allen drei Seiten aus der Liste vom Server (`GET /api/absence-requests/arten`, `arten` von „Zeiten“, `abwesenheitsarten` von „Meine Zeiten“). Keine Migration, kein Bestand geändert. `scripts/pruefe_abwesenheiten.py` nur lesend.

### Festlegungen 1.9.153 (Nr. 2–7 bestätigt am 31.10.2026; Nr. 1 entfällt: Freizeitausgleich wird eine eigene Kategorie, siehe „Lohn L0“)

1. Freizeitausgleich gehört zu „Urlaub“ (bezahlte Freistellung). Eine eigene Kategorie wäre eine eigene Entscheidung, zählen tut sie heute nirgends.
2. „Sonstiges“ und jede selbst angelegte Art passen zu jeder Kategorie: das Programm kennt ihre Bedeutung nicht. Eine selbst angelegte Art einer Kategorie zuordnen ginge nur mit einem neuen Feld an der Auswahlliste.
3. Die Art bleibt optional: ohne genauere Angabe trägt der Server den Namen der Kategorie ein („Fortbildung“, „Unbezahlt“), kein Pflichtfeld. Nur so lässt sich „Unbezahlt“ ohne „Sonstiges“ eintragen.
4. Was vor 1.9.153 da war, bleibt: der Admin kann einen älteren offenen Antrag mit Widerspruch genehmigen, auch die daraus entstehende Abwesenheit trägt ihn. `scripts/pruefe_abwesenheiten.py` nennt solche Einträge.
5. Das Skript nennt als Widerspruch Abwesenheiten und offene Anträge. Genehmigte Anträge tragen dieselben Werte wie ihre Abwesenheit, abgelehnte und zurückgezogene wirken nicht; gezählt werden sie.
6. „unbekannt“ (Altbestand ohne Kategorie) ist kein Widerspruch, sondern wird nur gezählt.
7. Im Dialog der Plantafel steht wie unter „Zeiten“ „Krankheit“ oder „Fortbildung (Berufsschule)“ statt „Krankheit · Krankheit“ (`abwArtText()`).

### Tests und Prüfung

Angepasste Erwartungen (Regel 28): `klicktest_abwesenheit_ein_weg` „P2: Art und Notiz sichtbar“, altes Soll „Urlaub · Urlaub“, neues Soll „Urlaub“ (dieselbe Prüfung, die Zeile heißt jetzt anders). `test_v102::test_rejected_absence_request_creates_no_absence`: legte „Freizeitausgleich“ in der Kategorie „Unbezahlt“ an, das ist jetzt ein Widerspruch; neue Daten „Urlaub“, geprüft wird weiter das Ablehnen. Nur der Aufbau: `test_v518::_node` und `test_v519::_abwesenheit` binden `_abwesenheit.html` ein. Neu: `tests/test_v571_kategorie_und_art.py`, `tests/test_v571_pruefe_abwesenheiten.py`.

## Umsetzung 1.9.154: „Zeiten → Abwesenheiten“ (Stufe 6, R1 Nachrunde, Punkt 5)

Entscheidung Tobias, löst den zweiten Halbsatz der Festlegung 1.9.146 Nr. 7 ab („zeigt ihn wie jeden Vermerk als ‚Freigabe: …‘“). `request_to_dict()` liefert `aus_migration` und `vom_programm`; die Seiten entscheiden danach nur über die Beschriftung.

Das Datum: die Migration `b2c7f4e19a06` schreibt `created_at` des Antrags aus `employee_absences.created_at`, also den Tag, an dem die Abwesenheit eingetragen wurde -- ein Datum der Migration steht nirgends. In den Bildern der vorigen Runde sah es danach aus, weil die Testdaten am selben Tag entstanden (`created_at` ist die echte Uhr, die Seite stand auf dem 14.10.); der Klicktest legt Kais Abwesenheit jetzt ausdrücklich am 02.09.2026 an. `employee_absences.created_at` ist seit dem Baseline-Schema Pflicht und beim Umzug auf PostgreSQL mitgekommen (`scripts/migrate_sqlite_to_postgres.py` kopiert jede Spalte); die Regel „sonst weglassen“ greift also nur, falls es doch einmal fehlte.

### Festlegungen 1.9.154 (bestätigt am 31.10.2026)

1. Der Antrag aus der Migration heißt „eingetragen am <Tag>“, nicht nur „am <Tag>“ und nicht ohne Datum: das Wort „beantragt“ stimmte nie.
2. Wird die Abwesenheit gelöscht, steht im Antrag „Auf der Plantafel eingetragen (vor 1.9.146). Die genehmigte Abwesenheit wurde gelöscht.“ -- die Herkunft bleibt lesbar, und `scripts/pruefe_abwesenheiten.py` zählt ihn weiter. `downgrade()` lässt so einen Antrag stehen, wie bisher alles, was jemand angefasst hat.
3. „Vermerk:“ gilt ebenso in „Meine Zeiten“, und `abwZeitraum()` auch dort und im Dialog der Plantafel: dieselben Daten, sonst stünde dort weiter „Freigabe: Die genehmigte Abwesenheit wurde gelöscht.“ und „21.10.–21.10.“.
4. Über den Jahreswechsel tragen beide Tage ihr Jahr („Mo 28.12.2026–Mo 04.01.2027“); bisher stand das erste ohne.

### Tests und Prüfung

`tests/test_v572_abwesenheiten_anzeige.py`; `test_v571_pruefe_abwesenheiten::test_unter_postgresql_lesen_und_nicht_schreiben`; `klicktest_abwesenheit_ein_weg`: acht Prüfungen zu Kai, Zeitraum, Vermerk und Freigabe.

Angepasste Erwartungen (Regel 28): `test_v519::test_antrag_knoepfe_nach_dem_server` und `test_v518` altes Soll „beantragt am 20.10.“, neues Soll „beantragt am 20.10.2026“. `test_v523::test_beantragt_von_in_der_zeile` altes Soll „Mo 02.11.–Mo 02.11.2026 · 1 Arbeitstag · beantragt von Fin Finanzen am 20.10.“, neues Soll „Mo 02.11.2026 · 1 Arbeitstag · beantragt von Fin Finanzen am 20.10.2026“. `klicktest_zeiten` „Admin: Anträge mit Genehmigen und Ablehnen“ und „Fin: „Krank“ für Tom gestellt …“: das Datum mit Jahr. Nur der Aufbau: `test_v523::test_meine_zeiten_zurueckziehen_nur_mit_darf_zurueckziehen` bindet `_abwesenheit.html` ein.

## Umsetzung 1.9.165: Vermerk neben der Freigabe (Stufe 6, R2, Punkt 7)

`review_notes` ist nur noch die Notiz des Admins, `vermerk` das, was das Programm schreibt (`MIGRATION_VERMERK`, `ABWESENHEIT_GELOESCHT`). `vom_programm` ist damit weg.

### Festlegungen 1.9.165 (bestätigt am 31.10.2026)

1. Eine Notiz, die das Löschen vor 1.9.165 schon überschrieben hat, kommt nicht von selbst zurück; sie steht im Änderungsprotokoll.
2. `reviewed_by_user_id` und `reviewed_at` zeigen nach dem Löschen weiter, wer gelöscht hat (seit 1.9.146); keine Seite zeigt sie an. Wer freigegeben hat, steht im Änderungsprotokoll.

### Tests und Prüfung

Angepasste Erwartungen (Regel 28): `test_v566::test_…` (Vermerk statt `review_notes`), `test_v571::_antrag` (Aufbau: `vermerk`), `test_v572` (`vom_programm` -> `vermerk`, die Seiten zeigen beides nebeneinander, Testaufbau `_aus_migration()` wendet die neue Migration an), `test_v326::ERLAUBT_JE_ROUTE` um `$[].vermerk` an `/api/absence-requests`.

## Lohn L0: Befund zur Ablösung von Time 4 (Stand 01.11.2026, nichts gebaut)

Vollständiger Bericht: `bildgrundlage/bericht_lohn_l0_*.txt`. Die Muster von Time 4 (erfundene Nummern) liegen nur lokal unter `bildgrundlage/lohn/`, nicht in Git. Berater- und Mandantennummer nie in Code oder Tests mit echten Werten.

### Ziel und Entscheidungen Tobias (31.10.2026)

Das ERP löst Time 4 ab, voraussichtlich ab dem Lohn Januar 2027; Dezember 2026 Probemonat mit beiden Systemen. Der DATEV-Export liefert genau das Format, das das Lohnbüro aus Time 4 importiert.

- Pause: gesetzliche Pause immer abziehen, auch ohne eingetragene Pause, höchstens bis auf 6,00 bzw. 9,00 h (07:15–13:30 ohne Pause = 6,00). Ersetzt „mehr als 6 h = 30 min“. (Berichtigt 1.9.179: „bis auf 9,00 h“ stimmt nicht -- zwischen 9:00 und 9:30 h Anwesenheit liegt die Arbeitszeit darunter, siehe Festlegung 1.9.166 Nr. 1.)
- Sollzeit Mo–Fr: KW 18–48 8,00 h, KW 49–17 7,50 h (Tarif Dachdecker, ISO-Kalenderwoche); Sa/So 0; Teilzeit je Person eigene Werte.
- Alle mit Stunden in den Export, auch Azubis (Arbeit und Feiertage). DATEV-Personalnummer je Person.
- Zuordnung Art -> Kennzeichen und Lohnart in den Einstellungen (Admin, Büro – Finanzen); leer = nicht exportieren.
- Urlaubskonto im ERP (Anspruch, Übertrag, Stand), Start 01.01.2027.
- Arbeitszeitkonto: maßgeblich bleibt DATEV; im ERP eine Übersicht, Startwert vom Lohnbüro.
- Freizeitausgleich baut das Arbeitszeitkonto ab, keine Urlaubskategorie (1.9.153 Nr. 1 entfällt).
- Schlechtwetter muss erfassbar sein (Ausfalltag für Person oder Kolonne).
- `test_v419` vorerst so lassen, bei erneutem Rot melden.

### Format laut den vier Mustern (per Skript geprüft, 535 Zeilen)

ASCII, CRLF auch in der letzten Zeile. Kopf `Berater;Mandant;MM/JJJJ`. Jede Zeile 11 Felder. Tageszeile `Personalnummer;Tag;Kennzeichen;Lohnart;Stunden;;;;;;` (Tag ohne führende Null, Komma, zwei Stellen). Paare: 1/1000 Arbeit (alle Zeitarten, auch Samstag), U/8000, K/1650, F/1012; U, K, F tragen die Sollzeit. Saison-Kurzarbeitergeld: `Personalnummer;;;8110;;;Stunden;;;;` als letzte Zeile der Person, Stunden = Soll × volle Ausfalltage, an diesen Tagen keine Tageszeile (5 von 5 Personen im Januar; ein Teilausfall zählt nicht). Eigenheit von Time 4: Samstage ohne eingetragene Pause ohne Abzug.

Offen laut Muster: F bekommt nicht jede Person (91012, 91013 nur U und K; 91011 ohne; 9005 keins vor der ersten Zeile; 91006 nur am Donnerstag, sieht nach Soll an Di–Do aus). Nie zwei Arten an einem Tag, also unbekannt: Arbeit und Krank, Arbeit am Feiertag. 2 von 426 Arbeitswerten nicht auf der Viertelstunde (9,10 und 0,15). Reihenfolge der Personen nur teils nach Nummer. Der Wechsel der Sollzeit an KW 17/18 und 48/49 ist durch die Muster nicht belegt. Eine DATEV-Satzbeschreibung liegt nicht vor (Community-Seite 403), das Muster ist die einzige Quelle.

### Befund

- Export (`app/time_backoffice.py::build_datev_export()`): passt in keinem Punkt, neu bauen. Keine Abwesenheit, kein Feiertag, keine Sollzeit, kein Kennzeichen, keine Monatszeile; `datev_fehlt()` prüft nur Personen mit Buchungen. „Leer = nicht exportieren“ dreht Festlegung 1.9.92 Nr. 1 um; „Monat & Lohn“ soll zeigen, was nicht in der Datei steht.
- Pause: eine Stelle, `app/work_time_models.py::automatic_break_minutes_for_duration()`. Vorschlag Lesart A: je Regel `min(Pause, Minuten über der Schwelle)`, davon das Maximum (6:15 -> 15 min, 6:30 -> 30, 9:15 -> 30 = 8,75 h, 9:30 -> 30 = 9,00 h, 9:45 -> 45). Wörtliche Lesart B gäbe zwischen 9:01 und 9:29 immer 9,00 h: eine Minute mehr bringt eine halbe Stunde mehr, und das Ergebnis hängt an der Aufteilung des Tages. Noch nicht entschieden (E1).
- Letzte Buchung kürzer als die fehlende Pause: heute unbemerkt (6:00 + 0:10: 10 statt 30 min, „passt“). Unter A unmöglich, solange alle Buchungen des Tags nach der neuen Regel laufen, die Pflichtpause wächst nie schneller als die Anwesenheit; die letzte Buchung kann mit 0,00 h stehen bleiben. Bleibt: eine Dauer davor (meldet „Prüfen“, seit 1.9.107) und Buchungen nach der alten Regel.
- Alte Buchungen: 6:15 mit 30 min (seit 1.9.62, Mindestpause 0) heißt unter der neuen Regel „passt nicht“ und sperrt den Abschluss. Vorschlag Stichtag 01.12.2026 (E2). Viele Tests rechnen relativ zu heute und kippten am Stichtag von selbst: feste Tage auf beiden Seiten nehmen.
- Falle Dauer: 6,25 h ohne Pause sagt „nach Zeitregel 15 min“, mit 15 eingetragen „30 min“. Richtig sind 30.
- Sollzeit: `WorkTimeModel.daily_target_hours` rechnet niemand; Grundwerte KW 13–43 und 44–12, beide 8,00. Keine Wochentage, kein Eintritt und Austritt (nirgends ein Datum). `Employee.weekly_hours` nur Kapazität und Kalkulation.
- Feiertage: `automatic_public_holidays("NW")` stimmt mit den Mustern. `_combined_holiday_map()` mischt von Hand eingetragene betriebsfreie Tage dazu, ohne Art: für F zählt nur der gesetzliche.
- Schlechtwetter: nur Zeitarten `weather_*` als Buchung auf einen Auftrag. Kein Ausfalltag. Muss in L1, sonst keine Zeile 8110 im Dezember.
- Nicht vorhanden: Urlaubsanspruch je Person (nur `ProductiveHoursSettings.vacation_days`), Arbeitszeitkonto. Stundenzettel-PDFs (Büro, Monteurin) nur Buchungen. Arbeit an einem Abwesenheitstag wird nicht geprüft.
- Rechte: Lohnarten, Personalnummern, Modelle und Pausenregeln ändert heute jedes Büro ab Büro – Auftrag.

Probelauf nur mit der Formel A (Wegwerf-Arbeitskopie auf d0ca6d5, nicht committet): 27 von 8225 Tests rot in 14 Dateien, 4 von 106 Klicktests mit 20 roten Prüfungen; bis auf eine alle mit den alten Zahlen. Die eine: `klicktest_monteurin_regeln` ist am 1. eines Monats auch ohne Änderung rot (am 01.11.2026 auf d0ca6d5 nachgestellt): die Zeit von gestern liegt im Vormonat, `/mobil/zeiten` zeigt den neuen Monat ohne Tage. Nicht behoben.

### Vorschlag

L1, je Punkt eine Version: 1 Pause (keine Migration), 2 Sollzeit (Modelle umstellen, nur wenn noch Grundwerte; Tabelle eigene Werte je Person mit „gültig ab“; Eintritt und Austritt), 3 Personalnummer (UNIQUE, nur Ziffern) und Export-Umfang je Person (alles, nur Abwesenheiten, nichts), 4 Zuordnung (Tabelle, vorbelegt über `app/grunddaten.py`; Art vor Kategorie) und Kategorie Freizeitausgleich mit Migration, 5 Ausfalltag (Kategorie schlechtwetter über `app/absence_requests.py`, gleich genehmigt, Person oder Kolonne, `weather_*` aus der Auswahl), 6 Export (ein Monat, ablegen, „Nicht im Export“, offene Anträge als Hindernis), 7 Prüfskript `scripts/pruefe_lohndatei.py ERP.txt TIME4.txt` (Form, Kopf, über Person und Tag, 8110, Summen; erklärt: Samstag, Deckel, nur im ERP; zu klären: alles andere). Vor dem 01.12.2026 unbedingt: was beim Buchen wirkt (1, 5, Freizeitausgleich) und die Stammdaten (2, 3); Export und Skript möglichst Mitte November für eine Vorprobe mit einer echten Time-4-Datei.

L2, kein harter Termin (leitet sich aus Buchungen und Abwesenheiten ab, es braucht nur Startwerte): Urlaubskonto, Arbeitszeitkonto als Übersicht, Stundenzettel mit U, K, F und Soll.

Zur Entscheidung vorgelegt (E1–E10 im Bericht): Lesart der Pause, Stichtag, wer F bekommt, Soll je Wochentag, Ausfalltag und wer ihn einträgt, Rundung 15 Minuten, Zuordnung vorbelegen, alte Formate entfallen, Sammeleintrag für Betriebsruhe, Rechte. Fragen ans Lohnbüro (LB1–LB10 im Bericht): Berufsschule, unbezahlt, Freizeitausgleich; Reihenfolge und Programm; mehrere Arten an einem Tag; F für wen und am Samstag; 8110 bei Teilausfall und im Sommer; Azubis; Startwerte; Viertelstunde; Korrekturen; Testimport.

### Entscheidungen Tobias zu L0 (02.11.2026, bestätigt)

- E1 Pause nach Lesart A.
- E2 Kein Stichtag: auf dem Server sind keine echten Daten, echte Buchungen beginnen voraussichtlich im Januar 2027. Die neue Pause gilt für alle Buchungen. Tests mit festen Tagen, nicht relativ zu heute.
- E3 Export-Umfang je Person: alles, nur Abwesenheiten oder nichts. F nur bei „alles“ und Soll > 0, nur gesetzliche Feiertage. Vor Eintritt und nach Austritt nichts.
- E4 Sollzeit je Wochentag.
- E5 Schlechtwetter als Abwesenheit (Kategorie schlechtwetter); Winter (01.12.–31.03.) und Sommer getrennt zuordenbar, ob mit gleichem Schlüssel, klärt das Lohnbüro. Die Zeitarten `weather_*` kommen aus der Auswahl, Altes bleibt lesbar.
- E6 Rundung unverändert, bis das Lohnbüro antwortet.
- E7 Zuordnung vorbelegt: 1/1000, U/8000, K/1650, F/1012, Schlechtwetter Winter 8110 als Monatszeile; dazu (Nachtrag 02.11.2026) Art Weiterbildung 1/1000 mit Sollzeit wie Fortbildung in Time 4. Schlechtwetter Sommer leer, bis der Juni-Export da ist; Berufsschule offen beim Lohnbüro. Alles andere leer = nicht exportiert, sichtbar gelistet.
- E8 Die alten Exportformate entfallen (in L1b).
- E9 Sammeleintrag einer Abwesenheit für mehrere Personen (alle, eine Kolonne, Auswahl).
- E10 Personalnummern, Arbeitszeitmodelle, Pausenregeln, Sollzeiten und Zuordnung nur Admin und Büro – Finanzen.
- Schlechtwetter eintragen: Kolonnenführer und Vorarbeiter für jeden gewerblichen Mitarbeiter, dazu Admin und Büro – Finanzen, gilt sofort. Jeder Mitarbeiter für sich selbst als Antrag, den Kolonnenführer, Vorarbeiter oder Admin bestätigt.
- Halbe Tage: Urlaub auch als halber Tag (Stunden = halbe Sollzeit, zählt 0,5 Tag). Der 24.12. und der 31.12. an Wochentagen sind je 0,5 Tag Urlaub; was mit der anderen Hälfte ist, klärt Tobias noch. Keine Betriebsruhe.

Neue Muster (Nachtrag 02.11.2026, `bildgrundlage/lohn/LIESMICH.txt`, für L1b): 12/2025 bis 10/2026 und Einzelbuchungen 09 und 10/2026. Time 4 zieht als Pause die Überschneidung mit festen Pausen des Zeitmodells ab (12:00–12:30, 16:30–16:45), ohne Zeitmodell keine. Azubis standen nur mit U und K im Export (Einstellung in Time 4). Der Wechsel der Sollzeit liegt zwischen Fr 24.04. und Mo 27.04.2026 (KW 17/18), wie angenommen. 31.12.2025 stand als ganzer Urlaubstag mit 7,50 h in Time 4, 24.12.2025 als Arbeitstag -- abweichend von der Vorgabe für L1a (je 0,5 Tag), im Bericht L1a genannt. Eine Person kann die DATEV-Nummer wechseln (91008 -> 91016 ab 10/2026).

## Lohn L1a: was beim Buchen wirkt (ab 1.9.166)

### Umsetzung 1.9.166: Pause nach Lesart A (Punkt 1)

Eine Stelle: `app/work_time_models.py::pflichtpause()` -- je Pausenregel höchstens die ganzen Minuten über ihrer Schwelle (abgerundet; die Anwesenheit kommt mit vier Stellen, deshalb zuerst auf Hundertstel Minuten), davon das Maximum. `automatic_break_minutes_for_duration()` ruft sie mit den Regeln des Modells, das an dem Tag für die Person gilt; darüber laufen wie bisher Stopp, Gruppen-Stopp, Ende nachtragen, Nachtrag, Kolonne, Ändern, Zeitart wechseln, alle Vorschauen, „Prüfen“, „Pausen neu rechnen“ und der Abschluss.

Was einem Tag mit Dauer fehlt, rechnet `fehlende_pause()`: jede Minute Pause verlängert die Anwesenheit einer Dauer, gesucht ist die kleinste Ergänzung, nach der die Pause passt -- eine Regel verlangt ihre volle Pause, sobald die Arbeitszeit über ihrer Schwelle liegt. `_pausen_stand()` nimmt sie statt `pause_nach_zeitregel(deckel=False)` (der Parameter ist weg). Die Vorschau „Dauer“ in „Zeiten“ nennt bei „passt danach nicht“ die Pause nach Zeitregel, auch je Person in „Kolonne buchen“.

Probe mit dem echten Code, Tabelle aus L0 2.2: 6:01 -> 1 min, 6:15 -> 15, 6:30 -> 30, 9:01 -> 30, 9:15 -> 30, 9:30 -> 30, 9:40 -> 40, 9:45 -> 45; die Pflichtpause steigt von Minute zu Minute höchstens um eine Minute (0 bis 12 h geprüft).

### Festlegungen 1.9.166 (Bitte bestätigen)

1. Neu gefasst mit 1.9.179 (Hinweis Tobias 03.11.2026): Minuten über der Schwelle werden abgerundet, nie aufgerundet: 6:00 h und 40 s Anwesenheit ergeben keine Pause. Die Pflichtpause ist der kleinste Wert, der zur Arbeitszeit danach passt; unter 6,00 h fällt die Arbeitszeit nie. Unter 9,00 h dagegen schon: zwischen 9:00 und 9:30 h Anwesenheit verlangt § 4 ArbZG für mehr als 6 h Arbeit 30 Minuten (9:15 h -> 30 min, 8,75 h; 9:30 h -> 30 min, 9,00 h). Bis 1.9.178 hieß es fälschlich: „So liegt die Arbeitszeit nie unter 6,00 bzw. 9,00 h.“
2. Eine Dauer braucht die volle Pause, sobald ihre Arbeitszeit über der Schwelle liegt (6,25 h -> 30 min, 9,25 h -> 45 min). Die Meldung nennt diese Zahl; sie ist dieselbe wie unter „Prüfen“.
3. Lesart A gilt für jede Pausenregel eines Modells, auch für selbst angelegte; Schwellen und Pausen bleiben je Modell einstellbar.
4. Kein Stichtag (E2): Buchungen nach der alten Regel bleiben, wie sie gebucht sind. „Prüfen“ zeigt ihren Tag als „passt nicht“ und sperrt den Abschluss, bis jemand „Pausen neu rechnen“ klickt -- auf dem Server gibt es keine echten Buchungen, die das träfe.

### Tests und Prüfung

Neu: `tests/test_v584_pause_lesart_a.py` (Formel, Wachstum, Fälle aus L0 2.3, Dauer, alte Buchung; fester Tag 09.11.2026). Gegenproben: die alte Formel -> 17 Tests rot; die alte Rechnung der fehlenden Pause einer Dauer -> 2 rot (`test_fehlende_pause_einer_dauer[6.25-0-30]`, `test_dauer_6_25_sagt_gleich_30`).

Angepasste Erwartungen (Regel 28), altes Soll -> neues Soll:
- `test_v104::test_work_time_models_and_automatic_break_on_timer`: 6,0167 h 30 -> 1 min, 9,0167 h 45 -> 30 min; 07:00–16:15 45 min, 8,50 h -> 30 min, 8,75 h (dazu 6,50 -> 30 und 9,75 -> 45 neu).
- `test_v462`: 06:45–16:00 45 min, 8,50 h -> 30 min, 8,75 h (`…zieht_die_pause…`, `…feierabend_bucht…`); `test_zusaetzliche_pause_bleibt_mindestpause[20]` 45 -> 30.
- `test_v463::test_richtiges_ende_gebucht…` und `::test_kolonnenfuehrer_schliesst…`: 45 min, 8,50 h -> 30 min, 8,75 h.
- `test_v471::test_vorschau_und_buchung_dieselben_zahlen[9h15]`: 45 -> 30.
- `test_v474`: Aufbau fester Tag (Fixture `fester_tag` statt `feste_uhr`); `test_schwelle_mehr_als` 6:01 30 -> 1, 9:01 45 -> 30, dazu sechs neue Fälle; `…mittags_pause_bei_der_zweiten[bis_16_15]` 45 min, 8,50 h -> 30 min, 8,75 h; `test_dauer_buchung_zaehlt…` Aufbau bis 14:30 statt 14:00 (6:15 h Tag verlangt nur noch 15 min, die schon abgezogen sind), Soll 15 bleibt; `test_echter_tag…` 45 min, 3,50 h, Tag 8,50 h -> 30 min, 3,75 h, 8,75 h; `test_vorschau_rechnet_wie_die_funktion` 45 -> 30.
- `test_v483`: Nachtrag 12:00–16:15 nach 07:00–12:00 45 min, 3,50 h -> 30 min, 3,75 h; die zweite Buchung beim Ändern, Löschen und neu Rechnen 45 -> 30 min (Vorschau 3,50 -> 3,75), Verlauf „45“ -> „30“; die bewusst falsche Vorschau 30 -> 15 min (30 ist jetzt der gebuchte Wert).
- `test_v489::test_kolonne_0700_1230…`: Aufbau Toms Fahrzeit ab 06:00 statt 06:15 („Tag zusammen“ 6:15 -> 6:30 h); Toms 30 min und 5,00 h bleiben.
- `test_v504::test_pausen_neu_rechnen_an_buchung_dort…`, `test_v510::test_pausen_neu_rechnen_fuer_andere`: 45 -> 30 min.
- `test_v511`: Büro-Nachtrag 45 min, 3,50 h -> 30 min, 3,75 h; Kolonne Mia 3,50 -> 3,75 h.
- `test_v512::test_unpassende_pause_sperrt…`: „abgezogen 45 min“ -> „30 min“.
- `test_v517::test_pruefen_zeiten_von_frueher` 8,50 h, 45 -> 8,75 h, 30; `::test_pruefen_pause_passt_nicht…` abgezogen 45 -> 30, Vorschau 45 -> 0 / 3,50 -> 4,25 jetzt 30 -> 0 / 3,75 -> 4,25.
- `test_v522`: Aufbau Toms Fahrzeit ab 06:00 statt 06:15 (sonst 15 statt 30 min); die nachgestellten Fehlerwerte bleiben.
- `test_v527::test_kolonne_dauer_je_person`: mit 0:30 Tom „passt nicht“ -> „passt“ (8:45 h Arbeit brauchen 30 min); `::test_dialog_dauer_vorschau_text` und `::test_kolonne_vorschau_text`: Text mit „(nach Zeitregel 0:30 h)“, die Attrappe trägt `noetig`.
- `klicktest_echter_tag`: drei Prüfungen 0:45 h, 3,50 h, Tag 8,50 h -> 0:30 h, 3,75 h, 8,75 h.
- `klicktest_meine_zeiten`: sechs Prüfungen -- Nachtrag 0:45 h, 3,50 h -> 0:30 h, 3,75 h, Tag 8,50 -> 8,75 h; Kolonne Tom 5,00 -> 5,25 h (Fahrzeit 06:15, Tag 6:15 h -> 15 min).
- `klicktest_monteurin_regeln`: „Ende nachgetragen“ 0:45 h, 8,50 h -> 0:30 h, 8,75 h.
- `klicktest_zeiten`: zwölf Prüfungen -- Ende 16:00 0:45 h, 8,50 h -> 0:30 h, 8,75 h (Vorschau, API, Meldung); Pause passt nicht 0:45 -> 0:30 h, 3,50 -> 3,75 h; Monat Mia 18,00 -> 18,50, zusammen 35,75 -> 36,25; Buchungen Mia 0:45/3,50 -> 0:30/3,75, Tom 0:45/8,50 -> 0:30/8,75; Summe 45,00 -> 45,50, Tom 26,25 -> 26,50; drei Texte „passt danach nicht“ mit „(nach Zeitregel 0:30 h)“; Lohn Mia 21,75 -> 22,00, Tom 30,50 -> 30,75, zusammen 52,25 -> 52,75.

### Umsetzung 1.9.167: Sollzeit (Punkt 2)

`app/sollzeit.py` ist die eine Rechnung: `soll(db, Person, Tag)` und `soll_zeitraum()` (Stunden mit zwei Stellen). Tarif = Montag bis Freitag `WorkTimeModel.daily_target_hours` des Modells, das `employee_model()` für den Tag liefert (zugeordnetes Modell, sonst das gültige Standardmodell, sonst das erste gültige); Samstag und Sonntag 0. Eigene Werte: `EmployeeTargetHours` (je Person und Tag eindeutig, sieben Spalten `montag` … `sonntag`, alle leer = Tarif), es gilt die jüngste Zeile mit `valid_from <= Tag`. `EmployeePayrollSettings.eintritt/austritt` (beide eingeschlossen, leer = offen): davor und danach 0. Ein Feiertag ändert die Sollzeit nicht.

Migration `b7e3c91d4a52`: Spalten und Tabelle; Startmodelle (Kürzel summer/winter) nur bei genau den Grundwerten auf den Tarif; `downgrade()` stellt nur zurück, was genau dem Tarif entspricht. Neue Installationen bekommen den Tarif aus `ensure_default_work_time_models()`. Ein Fehler, den die Migrationsprobe fand: SQLite bindet in rohem SQL keinen Decimal-Wert, der Parameter hat jetzt einen Typ.

Rechte (E10): `app/permissions.py::darf_lohnregeln()`/`require_lohnregeln` (Admin, Büro – Finanzen) an `PUT /api/time-backoffice/settings`, Modelle (POST, PUT, DELETE), Zuordnung (PUT, bulk), Lohnstammdaten (PUT) und Sollzeiten (POST, DELETE). Lesen bleibt ab Büro – Auftrag. Die Seite bekommt `lohnregeln` von der Seitenroute und sperrt den ganzen Bereich „Zeitregeln und DATEV“ (`lohnregelnNurLesen()` nach jedem Zeichnen).

### Festlegungen 1.9.167 (Bitte bestätigen)

1. Ohne eigene Werte gilt der Tarif auch für Azubis und Aushilfen; wer anders arbeitet, bekommt eigene Werte.
2. Eigene Werte ändern sich nicht mit der Kalenderwoche (E4 sagt nur „je Wochentag“); soll eine Teilzeit im Winter anders laufen, braucht sie eine zweite Zeile ab dem Wechsel.
3. „Gültig ab“ einer eigenen Sollzeit liegt nach „Abgeschlossen bis“, Löschen ebenso -- ein abgerechneter Monat rechnet beim nächsten Export nicht anders. Eintritt und Austritt prüfen das nicht: sie stehen meist weit zurück und ändern sich selten; der abgelegte Export (L1b) hält fest, was abgerechnet ist.
4. Eine Änderung am Modell (Sollzeit, Kalenderwochen) gilt weiter auch rückwirkend; die Seite sagt, sie erst nach dem Abschluss der Monate davor zu ändern.
5. Rundung, Standardmodell, Lohnarten und „DATEV-Nr. = ERP-Nr.“ (das Formular „Zeitregeln“) ändern nur noch Admin und Büro – Finanzen -- alles rechnet in die Lohndatei; E10 nannte Personalnummern, Modelle, Pausenregeln, Sollzeiten und Zuordnung.
6. Die Sollzeit eines Tags hat zwei Nachkommastellen (`round_hours()`), auch wenn das Modell vier speichert.

### Tests und Prüfung

Neu: `tests/test_v585_sollzeit.py` -- Tarif an Fr 24.04./Mo 27.04.2026 (7,50/8,00, wie LIESMICH 7.), Fr 27.11./Mo 30.11.2026, Sa, So, KW 53, KW 1, 01.05.; Teilzeit Di–Do und zurück zum Tarif; Eintritt und Austritt; Anlegen, Lesen, Löschen über die Schnittstelle; falsche Werte 422; abgeschlossener Zeitraum 409; Teil-Update der Lohnstammdaten; Büro – Auftrag 403 an sieben Schreibwegen, liest fünf; Migration auf einem Bestand (geänderter Winter bleibt) unter SQLite und PostgreSQL. Gegenproben: Rechte wie bisher -> `test_buero_auftrag_liest_nur` rot; Sperre aus -> `test_sollzeit_nie_im_abgeschlossenen_zeitraum` rot; Eintritt nicht beachtet -> `test_eintritt_und_austritt` rot. Klicktest neu: `klicktest_sollzeit.py` (16 Prüfungen, vier Bilder).

Angepasste Erwartungen (Regel 28): `test_v109::test_time_backoffice_router_fully_uses_shared_dependency` altes Soll mindestens 11-mal `_role_dep`, neues Soll mindestens 6-mal `_role_dep` und 9-mal `_regeln_dep` (4-mal `_lohn_dep` bleibt). `test_v105::test_summer_winter_model_week_validity…` altes Soll KW 13–43 und 44–12, neues Soll KW 18–48 und 49–17. `test_v448` (beide Tests) Aufbau: Büro – Finanzen statt Büro – Auftrag speichert die Zeitregeln. `test_v513::test_formular_der_zeitregeln_laesst_die_nummern_stehen` Aufbau: Büro – Finanzen speichert das Formular statt Büro – Auftrag (das liest nur noch). `test_v329::BEKANNT` ohne `PUT /api/time-backoffice/payroll-employees/{employee_id}` (jetzt ein Teil-Update). `test_v424::ABGLEICH` um die sieben Felder der Sollzeit (0 bis 24 h, Grenze im Prüfer des Schemas).

### Umsetzung 1.9.168: Personalnummer und Export-Umfang (Punkt 3)

`app/time_backoffice.py`: `PERSONALNUMMER_FORMAT` (`^[1-9][0-9]{0,4}$`), `EXPORT_UMFAENGE` (alles, abwesenheiten, nichts), `exportiert_arbeit()` (nur „alles“ -- liest der heutige Export, `datev_fehlt()` und „Monat & Lohn“). `set_employee_payroll()` prüft erst alles und schreibt dann; `payroll_export_enabled` folgt dem Umfang (= nicht „nichts“), gelesen wird es nicht mehr. Ein gleichzeitiges Speichern derselben Nummer endet an der Bedingung mit „bereits vergeben“ (422), nicht mit 500. Im Änderungsprotokoll heißt das neue Feld „Export-Umfang“ (`app/audit.py`; gefunden im Lauf der Suite, `test_v436`, `test_v438`).

Migration `c5a9e3f71d28`: `pruefen()` (Dubletten auf den getrimmten Nummern) vor jeder Änderung, dann Leerzeichen weg und leere Nummern NULL, Bedingung, Spalte `export_umfang` (server_default „alles“, aus false wird „nichts“). `downgrade()`: Häkchen aus dem Umfang („nur Abwesenheiten“ wird aus), Spalte und Bedingung weg. Das Format prüft die Migration nicht -- eine Nummer mit Buchstaben bleibt, die Prüfabfrage und `scripts/pruefe_zeitregeln.py` nennen sie.

### Festlegungen 1.9.168 (Bitte bestätigen)

1. Neu gefasst mit 1.9.212 (Antwort des Lohnbüros, Vorgabe Tobias 05.11.2026): eine Personalnummer hat genau 5 Ziffern, führende Nullen gehören dazu (00001, 00101, 00204); beim Speichern wird nichts aufgefüllt, „101“ bekommt die Meldung. Die Kreise 00000–00099 sv-pflichtig Beschäftigte, 00100–00199 Minijobber, ab 00200 Azubis sind ein Hinweis, keine Sperre. Bis 1.9.211 hieß es: „Eine Personalnummer hat 1 bis 5 Ziffern ohne führende Null (die Muster haben 4 und 5 Stellen). Falls DATEV längere Nummern nimmt, ist das eine Zeile im Code -- zu klären mit LB2.“
2. Bei „DATEV-Nr. = ERP-Nr.“ gilt das Format für die ERP-Nummer, aber nur, solange von der Person etwas in die Datei geht; mit „nichts“ bleibt sie speicherbar (Eintritt, Sollzeit).
3. Neu gefasst mit 1.9.177 (Vorgabe Tobias 03.11.2026): eine Nummer, die einer Person einmal gehört hat, bleibt dauerhaft gesperrt -- auch nach Austritt und nach einem Nummernwechsel (LIESMICH 8: 91008 -> 91016 bekommt die Person die neue Nummer, die alte bleibt ihr gemerkt); nur dieselbe Person bekommt sie wieder (seit 1.9.181 gibt der Admin eine gemerkte Nummer frei, solange sie niemand trägt -- Festlegung 1.9.177 Nr. 3; vermerkt mit 1.9.197). Bis 1.9.176 hieß es: „die alte ist danach frei. Eine Liste früherer Nummern gibt es nicht.“
4. Der Umfang „nur Abwesenheiten“ wirkt im heutigen Export wie „nichts“ (er kennt noch keine Abwesenheiten); mit L1b stehen dann U, K und die übrigen zugeordneten Abwesenheiten in der Datei.
5. Die Migration bricht bei einer Dublette ab, statt eine Nummer zu leeren: welche Person die Nummer behält, entscheidet das Büro.

### Tests und Prüfung

Neu: `tests/test_v586_personalnummer.py` -- sieben falsche Formate 422 ohne Zeile, vier gültige, dieselbe Nummer für zwei Personen (422 und `IntegrityError` direkt in der Datenbank), leer beliebig oft, die drei Umfänge, falscher Umfang 422, altes Häkchen, Gleichsetzung mit der ERP-Nummer, Büro – Auftrag 403, Migration auf einem Bestand mit Dublette (Abbruch, nichts geändert), danach hoch, runter, hoch unter SQLite und PostgreSQL, Prüfabfrage nur SELECT. Gegenproben: Format nicht geprüft -> 8 rot; Umfang „abwesenheiten“ als Arbeit -> 1 rot; Migration ohne `pruefen()` -> 1 rot. `klicktest_sollzeit.py`: drei Prüfungen mehr (19).

Angepasste Erwartungen (Regel 28): `test_v513::test_ohne_lohnexport_keine_personalnummer_noetig` Aufbau: Tom mit Umfang „nichts“ statt nur `payroll_export_enabled = False`.

### Umsetzung 1.9.169: Zuordnung und Freizeitausgleich (Punkt 4)

`LohnartZuordnung` (Tabelle `lohnart_zuordnungen`, Schlüssel eindeutig): „arbeit“, „feiertag“, „kategorie:<Kategorie>“, „schlechtwetter:winter|sommer“, „art:<Art klein>“; Kennzeichen (1–2 Zeichen, Ziffer oder Großbuchstabe), Lohnart (1–4 Ziffern), Monatszeile (nur Schlechtwetter, dann ohne Kennzeichen). `app/lohnarten.py::zuordnung(kategorie, art, tag)`: die Art, wenn sie eine eigene Lohnart hat, sonst die Kategorie, Schlechtwetter nach Datum (Winter 01.12.–31.03.); `fest()` für Arbeit und Feiertag; `liste()` für die Seite mit „Wirkt“ je Zeile (bei einer Art ohne eigene die ihrer Kategorie). `GET /api/time-backoffice/lohnarten` ab Büro – Auftrag, `PUT` (Schlüssel, Kennzeichen, Lohnart, Monatszeile, alle Pflicht) nur `require_lohnregeln`. Grunddaten: `ensure_default_lohnart_zuordnungen()` legt die festen Zeilen und „art:weiterbildung“ an, wenn sie fehlen. Die bisherigen Lohnarten je Zeitart bleiben bis L1b stehen („Lohnarten des bisherigen Exports“). Jede Änderung der Zuordnung steht im Änderungsprotokoll („Zuordnung DATEV-Export“).

Kategorie „freizeitausgleich“: `ABSENCE_CATEGORIES`, Bezeichnung, `ART_KATEGORIEN` (Art Freizeitausgleich nur noch dazu), Muster in `app/schemas.py`, Auswahl und Bezeichnung in `zeiten.html`, `mobil_zeiten.html`, `planning.html`. Migration `d8f2a6c4e913`: Tabelle; Abwesenheiten und Anträge mit Art Freizeitausgleich (ohne Groß- und Kleinschreibung, Leerzeichen außen) in Kategorie Urlaub -> Freizeitausgleich; `downgrade()` jede Kategorie Freizeitausgleich zurück auf Urlaub.

### Festlegungen 1.9.169 (Bitte bestätigen)

1. Arbeit trägt die gebuchten Stunden, jede andere Zeile die Sollzeit des Tags (auch Weiterbildung 1/1000, wie Fortbildung in Time 4, LIESMICH 3).
2. Neu gefasst mit 1.9.215 (folgt aus Festlegung 1.9.175 Nr. 5 neu): eine Art geht ihrer Kategorie vor, sobald sie ein Kennzeichen hat (mit oder ohne Lohnart); eine leere Art heißt „wie die Kategorie“. Bis 1.9.214 hieß es: „Eine Art geht ihrer Kategorie nur vor, wenn sie eine Lohnart hat; eine leere Art heißt „wie die Kategorie“, nicht „nicht exportiert“. Wer eine Art ausdrücklich nicht exportieren will, leert ihre Kategorie oder legt die Art in einer leeren Kategorie an.“
3. Neu gefasst mit 1.9.214 (Antwort des Lohnbüros, Vorgabe Tobias 05.11.2026): Schlechtwetter ist je Jahreszeit eine Zeile (Winter 01.12.–31.03., Sommer sonst), nicht je Art -- für die Kategorie Schlechtwetter gewinnt immer die Jahreszeit (seit 1.9.203), eine Zuordnung je Art wird abgelehnt, eine gespeicherte übergangen. Winter steht als WA / 8195 je Ausfalltag (eine Zeile je Tag, keine Monatszeile), Sommer bleibt leer (nicht exportiert). Bis 1.9.213 hieß es: „Schlechtwetter ist je Jahreszeit eine Zeile (Winter 01.12.–31.03., Sommer sonst), nicht je Art -- ob beide denselben Schlüssel bekommen, klärt das Lohnbüro (E5). Eine Monatszeile gibt es nur dort. Seit 1.9.203 auch im Code (Vorgabe Tobias, L1a Stufe 4, Punkt 2): für die Kategorie Schlechtwetter gewinnt immer die Jahreszeit, eine Zuordnung je Art wird dort abgelehnt, eine gespeicherte übergangen (bis 1.9.202 ging eine Zeile „art:schlechtwetter“ vor).“ (vorbelegt war Winter 8110 als Monatszeile).
4. Kennzeichen 1 bis 2 Zeichen, Lohnart 1 bis 4 Ziffern (die Muster: 1, U, K, F; 1000, 8000, 1650, 1012, 8110).
5. Die festen Zeilen legt der Start an; eine geleerte bleibt leer. Eine Zeile je Art entsteht erst beim ersten Speichern (außer Weiterbildung; seit 1.9.214 auch außer Berufsschule, FE ohne Lohnart -- Festlegung 1.9.214 Nr. 4).
6. Die bisherigen Lohnarten je Zeitart (sechs Felder im Formular „Zeitregeln“) bleiben stehen, bis der neue Export sie ersetzt (E8, L1b).
7. Freizeitausgleich im Bestand: nur Art Freizeitausgleich in der Kategorie Urlaub wird umgestellt; dieselbe Art in einer anderen Kategorie (Altbestand mit Widerspruch) bleibt und steht in `scripts/pruefe_abwesenheiten.py`.

### Tests und Prüfung

Neu: `tests/test_v587_lohnarten.py` -- Vorbelegung samt leeren Zeilen, Vorrang der Art (7 Fälle), Schlechtwetter nach Datum, eigene Zuordnung einer Art, Leeren übersteht einen Neustart, neun abgelehnte Eingaben, Kennzeichen groß, Schnittstelle und Rechte (Büro – Auftrag 403, PUT ohne Felder 422), Kategorie Freizeitausgleich beim Antrag, die drei Seiten, Migration auf einem Bestand unter SQLite und PostgreSQL. Klicktest neu: `klicktest_lohnarten.py` (8 Prüfungen, zwei Bilder).

Angepasste Erwartungen (Regel 28): `test_v571::test_zuordnung[Freizeitausgleich]` altes Soll Kategorie Urlaub, neues Soll Freizeitausgleich; `test_v571::test_passend_200` (beide Wege) Aufbau: Freizeitausgleich in seiner Kategorie statt in Urlaub; `test_v102::test_rejected_absence_request_creates_no_absence` Aufbau ebenso; `test_v109::test_time_backoffice_router_fully_uses_shared_dependency` altes Soll 6/9, neues Soll 7/10 (`_role_dep`/`_regeln_dep`); `klicktest_abwesenheit_ein_weg` „D2: zu Urlaub nur passende Arten“ altes Soll „— ohne —, Urlaub, Freizeitausgleich, Sonstiges“, neues Soll „— ohne —, Urlaub, Sonstiges“.

### Befund vorab (Punkt 5): Kolonnenführer und Vorarbeiter, wie sie bis 1.9.169 abgebildet sind

- **Kolonnenführer**: `TeamEmployee.is_crew_leader` je Kolonne (seit 1.7.12, Migration `2f5de21f11b8`), mehrere je Kolonne erlaubt, gesetzt in der Maske der Kolonne (Stammdaten). Rechtegrundlage für Kolonnenbuchungen (`_require_crew_leader()`), „Ende nachtragen“ einer Gruppenzeit, Kolonnen-Nachtrag. Gilt nur für das Team, in dem das Kennzeichen steht.
- **Vorarbeiter**: keine Rechtegrundlage. Es gibt nur Text: die Funktion „Dachdecker Vorarbeiter“ (`EmployeeFunction`, frei umbenennbar), die Rolle in einer Kolonne (`TeamEmployee.role`, „z. B. Vorarbeiter“, als Schnappschuss in die Arbeitsvorbereitung kopiert) und „Projektleiter / Vorarbeiter“ am Auftrag (`Order.project_manager_employee_id`, eine Person je Auftrag). 1.7.12 hat bewusst entschieden, Rechte nicht an Schreibweisen zu hängen.
- Entscheidung dieser Runde: ein eigenes Kennzeichen `EmployeeRoleSettings.vorarbeiter` am Mitarbeiter (wie „Als Sachbearbeiter verfügbar“), gesetzt im Mitarbeiterformular von Admin und Büro – Finanzen (wer den Mitarbeiter ändert). Niemand wird automatisch Vorarbeiter.

### Umsetzung 1.9.170: Ausfalltag Schlechtwetter (Punkt 5)

`app/schlechtwetter.py` (Regeln, rollenlos) und `app/routers/schlechtwetter.py` (Rechte): `GET /api/schlechtwetter/kontext` (darf für andere, darf bestätigen, gewerbliche Personen -- für andere alle, sonst nur die eigene --, aktive Kolonnen mit gewerblichen Mitgliedern, offene Anträge nur für die, die bestätigen; nur Namen und Tag), `POST /api/schlechtwetter` (Personen, Tag, Notiz, „trotzdem“; alles oder nichts in einem Commit; 422 mit Liste, 409 mit Warnungen), `POST /api/schlechtwetter/{id}/entscheiden`. Der Ausfalltag entsteht über `app/absence_requests.py::_antrag_anlegen()`/`_entscheiden()` (ein Weg), Kategorie „schlechtwetter“ in `ABSENCE_CATEGORIES`, nur ein Tag; die allgemeinen Wege (`/api/absence-requests`, Plantafel) lassen die Kategorie nicht zu (Muster im Schema). Feiertag = gesetzlicher Feiertag des Bundeslands (`automatic_public_holidays()`, auch wenn die Plantafel ihn nicht anzeigt), betriebsfreie Tage von Hand zählen nicht. Sollzeit aus `app/sollzeit.py`.

Kolonnenführer = `is_crew_leader` in einer aktiven Kolonne; Vorarbeiter = `EmployeeRoleSettings.vorarbeiter` (Migration `e4b7d1a93c56`, server_default false), beide nur für aktive Mitarbeiter. Die Zeitarten `weather_winter`/`weather_summer` werden in der Migration inaktiv, in einer neuen Installation inaktiv angelegt (`app/option_settings.py::NEU_INAKTIV`); die Kacheln in /mobil kommen aus den aktiven Zeitarten und zeigen sie nicht mehr. `app/productive_hours.py::weather_days_actual()` zählt je Ausfalltag die Stunden eines Tags dazu.

Oberfläche: `_schlechtwetter.html` (Dialog und Bestätigen, bindet `_speichern.html`, `_auswahl.html`, `_berlin_date.html` und `_abwesenheit.html` selbst ein; die node-Attrappe der Seiten kennt ihn, `tests/test_v334_auswahl_restfaelle.py::BAUSTEINE`), in „Zeiten → Abwesenheiten“ (Knopf „Schlechtwetter eintragen“, nur wer für andere einträgt) und in „Meine Zeiten“ (Knopf „Schlechtwetter“ für jede gewerbliche Person, darunter „Schlechtwetter bestätigen“). Die Liste unter „Zeiten“ zeigt die Kategorie „Schlechtwetter“, der Admin entscheidet einen Antrag dort wie jeden anderen.

### Festlegungen 1.9.170 (Bitte bestätigen)

1. Vorarbeiter ist ein Kennzeichen am Mitarbeiter, gesetzt im Mitarbeiterformular (Admin, Büro – Finanzen); weder die Funktion „Dachdecker Vorarbeiter“ noch die Rolle in einer Kolonne machen jemanden zum Vorarbeiter.
2. Ein Kolonnenführer trägt für jeden gewerblichen Mitarbeiter ein, nicht nur für seine Kolonne (wie vorgegeben); er muss Kolonnenführer einer aktiven Kolonne sein.
3. Büro – Finanzen trägt sofort ein, bestätigt aber keine Anträge (die Vorgabe nennt Kolonnenführer, Vorarbeiter und Admin); der Admin entscheidet auch unter „Zeiten“ -- seit 1.9.202 mit denselben Prüfungen wie im Dialog (bis 1.9.201 genehmigte er dort auch an einem Tag ohne Sollzeit; Vorgabe Tobias, L1a Stufe 4, Punkt 1).
4. Schlechtwetter nur für gewerbliche Mitarbeiter (Funktion mit Gruppe „gewerblich“), auch für Azubis.
5. Alles oder nichts: ist ein Tag für eine Person nicht möglich, wird für niemanden eingetragen; die Meldung nennt jede Person mit Grund -- seit 1.9.204 auch, wer schon abwesend ist oder einen offenen Antrag hat (bis 1.9.203 kam das erst beim Anlegen, ohne Namen und nur der erste; Vorgabe Tobias, L1a Stufe 4, Punkt 3).
6. Die Warnung betrifft gebuchte und laufende Zeit an dem Tag; „trotzdem“ trägt für alle ein, die Buchungen bleiben (die Datei zeigt dann zwei Arten an einem Tag, LB3).
7. Neu gefasst mit 1.9.178 (Vorgabe Tobias 03.11.2026): nur gesetzliche Feiertage werden abgelehnt; an einem von Hand eingetragenen betriebsfreien Tag fragt der Server wie bei gebuchter Zeit nach (409, „Trotzdem eintragen“). Bis 1.9.177 hieß es: „ein von Hand eingetragener betriebsfreier Tag nicht (keine Betriebsruhe, Vorgabe zu den halben Tagen)“ -- er wurde still angenommen.
8. Die allgemeinen Abwesenheitsdialoge bieten Schlechtwetter nicht an; der Weg ist der eigene Dialog.
9. Die Zeitarten Schlechtwetter bleiben in der Liste (inaktiv): wer sie in den Einstellungen wieder einschaltet, bekommt die Kacheln zurück.

### Tests und Prüfung

Neu: `tests/test_v588_schlechtwetter.py` -- gilt sofort für Admin, Büro – Finanzen, Kolonnenführer, Vorarbeiterin (auch außerhalb der Kolonne); Monteurin beantragt für sich, für andere 403; bestätigen durch Kolonnenführer, Vorarbeiterin, Admin, nicht Büro – Finanzen und Monteurin; ablehnen; Sa, So, Feiertag; Tag ohne Sollzeit und kaufmännisch zusammen -- nichts gespeichert; schon abwesend; Warnung und „trotzdem“; allgemeiner Weg 422; Kontext je Rolle; Kolonnenführer einer abgeschalteten Kolonne; Vorarbeiter im Mitarbeiterformular (weggelassen = unverändert); Zeitarten inaktiv in einer neuen Installation; Ist-Wert; Baustein in beiden Seiten; Migration auf einem Bestand unter SQLite und PostgreSQL. Gegenproben: Rechte für alle -> 4 rot; Feiertag nicht geprüft -> 1 rot; Warnung übergangen -> 1 rot. Klicktest neu: `klicktest_schlechtwetter.py` (20 Prüfungen, vier Bilder).

Angepasste Erwartungen (Regel 28): `test_v286::test_create_request_accepts_each_real_category[schlechtwetter]` Aufbau: ein Tag statt zwei (neue Kategorie in der Liste). `klicktest_heute` „Lea: Auftrag A vorbelegt, Kacheln mit Vorschlag“ altes Soll eine Kachel mit „Vorschlag“ (Schlechtwetter), neues Soll keine und keine Kachel `weather_*`. `test_v334::BAUSTEINE` Aufbau: um `_schlechtwetter.html` (die Attrappe von „Zeiten“ in `test_v520` brauchte `swBinden()`).

### Umsetzung 1.9.171: Sammeleintrag und halbe Urlaubstage (Punkt 6)

`EmployeeAbsence.halber_tag` und `EmployeeAbsenceRequest.halber_tag` (Migration `f6c3a8e25b19`, server_default false). `_antrag_anlegen()` lässt ihn nur bei Urlaub an einem Tag zu (422), `_entscheiden()` übernimmt ihn. `app/sollzeit.py`: `anteil()` (halber Tag, Urlaub am 24.12./31.12. je 0,5), `abwesenheit_tage()` (Tage und Stunden einer Abwesenheit nach der Sollzeit, ohne Tage ohne Soll und ohne gesetzliche Feiertage); `soll_zeitraum()` merkt sich das Modell je Kalenderwoche. „Zeiten“ zeigt `arbeitstage` daraus (auch 0,5) und „halber Tag“.

Sammeleintrag: `app/absence_requests.py::sammel_eintragen()` (je Person `_antrag_anlegen()`, beim Admin `_entscheiden()`; alles oder nichts, `SammelAbgelehnt` mit Liste), `POST /api/absence-requests/sammel` (nur `darf_abwesenheiten_aller()`, Admin gleich genehmigt, Büro – Finanzen Anträge), `GET /api/zeiten/abwesenheiten` liefert dazu die aktiven Kolonnen mit ihren aktiven Mitgliedern. Ohne SAVEPOINT je Person: unter SQLite ist ein SAVEPOINT vor der ersten Änderung selbst die Transaktion, sein RELEASE committet -- der Test „alles oder nichts“ fand das.

### Festlegungen 1.9.171 (Bitte bestätigen)

1. Ein halber Tag geht nur bei Urlaub und für einen einzelnen Tag (Vorgabe „Urlaub auch als halber Tag“); Krankheit und Freizeitausgleich bleiben ganze Tage.
2. ~~Der 24.12. und der 31.12. zählen je 0,5 Tag Urlaub, wenn sie in einem Urlaub liegen; ein Häkchen braucht es dafür nicht. Die andere Hälfte rechnet das ERP nicht (weder Arbeit noch frei), bis Tobias sie klärt. Time 4 hatte den 31.12.2025 als ganzen Tag (LIESMICH 5), den 24.12.2025 als Arbeitstag.~~ Zurückgezogen von Tobias (03.11.2026), entfällt ersatzlos seit 1.9.174; die beiden Tage regelt der Arbeitszeitkalender (1.9.175, 1.9.176).
3. Arbeitstage am Antrag nach der Sollzeit der Person (bis 1.9.170 Montag bis Freitag für jeden); die Plantafel rechnet ihre Kapazität weiter je ganzem Tag.
4. Sammeleintrag: beim Admin gleich genehmigt (wie „Abwesenheit eintragen“ auf der Plantafel), bei Büro – Finanzen offene Anträge, die der Admin entscheidet. Einzeln bleibt es wie bisher ein Antrag.
5. Alles oder nichts, wie bei Schlechtwetter: wer schon abwesend ist oder einen offenen Antrag hat, muss abgewählt werden; die Meldung nennt jede Person. Seit 1.9.205 geprüft schon beim Anlegen, auch bei Büro – Finanzen (bis 1.9.204 entstanden dort offene Anträge, „schon abwesend“ scheiterte erst bei der Entscheidung; Vorgabe Tobias, L1a Stufe 4, Punkt 4); die Prüfung beim Entscheiden bleibt.
6. „Alle“ heißt alle aktiven Mitarbeiter der Auswahl, auch kaufmännische; Schlechtwetter geht weiter nur über den eigenen Dialog.

### Tests und Prüfung

Neu: `tests/test_v589_sammel_und_halber_tag.py` -- halber Urlaubstag (0,5 Tag, 3,75 h), halber Tag nur Urlaub an einem Tag, 21.–31.12.2026 = 7 Tage und 52,50 h, 24.12. halb, 31.12.2027 (Freitag) halb, Krankheit am 24.12. ganz, Teilzeit Di–Do = 3 Tage, „Zeiten“ zeigt 0,5; Sammeleintrag Admin genehmigt, Büro – Finanzen Anträge, Büro – Auftrag und Monteurin 403, alles oder nichts, halber Tag und Schlechtwetter im Sammeleintrag, Kolonnen nur für Admin und Büro – Finanzen, die Seiten; Migration auf einem Bestand unter SQLite und PostgreSQL. Gegenproben: halber Tag ungeprüft -> 2 rot; 24.12./31.12. ganz -> 2 rot; Commit statt Rollback -> 1 rot. Klicktest neu: `klicktest_sammeleintrag.py` (20 Prüfungen, drei Bilder); er fand die zwei Punkte am Ende der Meldung.

Angepasste Erwartungen (Regel 28): `test_v525::test_antrag_ueber_weihnachten_acht_arbeitstage` altes Soll 8 Arbeitstage, neues Soll 7 (24.12. und 31.12. je 0,5). `test_v519::_abwesenheit` Aufbau: die Attrappe bindet `_zahl.html` ein (die Zeile zeigt die Arbeitstage über `zahlText()`).

### Umsetzung 1.9.172: Prüfskript `scripts/pruefe_zeitregeln.py` (Punkt 7)

Nur lesend, Muster `scripts/pruefe_abwesenheiten.py` (`nur_lesende_sitzung()`: PostgreSQL `READ ONLY`, SQLite `query_only`; `main(argv, sitzung=, umgebung=, ausgabe=, heute=)`; ohne `DATABASE_URL` Rückgabe 2). Abschnitte: Rundung und „abgeschlossen bis“; Arbeitszeitmodelle (Kürzel, Kalenderwochen, Soll Mo–Fr, Pausenregeln, aktiv, Standardmodell, zugeordnete Personen), alte Grundwerte, Kalenderwochen ohne bzw. mit mehreren aktiven Modellen; Personen (aktiv) mit Gleichsetzung, Personalnummer fehlend/falsch/doppelt nach `PERSONALNUMMER_FORMAT`, Export-Umfang, Eintritt, „aktiv, aber ausgetreten“, eigene Sollzeiten; Bundesland, „Feiertage automatisch“, gesetzliche Feiertage dieses und des nächsten Jahres (`automatic_public_holidays()`), von Hand eingetragene Tage (`PlanningHoliday`, zählen nicht als F und nicht in der Sollzeit); Zuordnung für den Export je Schlüssel. Heute aus `berlin_today()`.

### Festlegungen 1.9.172 (Bitte bestätigen)

1. „Zu klären“ (Rückgabe 1) ist nur, was Sollzeit oder Export falsch machte: Personalnummer fehlt bei Export ungleich „nichts“, ist nicht 1 bis 5 Ziffern ohne führende Null (seit 1.9.212: hat nicht genau 5 Ziffern) oder doppelt; Startmodell mit den alten Grundwerten; Kalenderwochen ohne aktives Modell; kein Modell. Abweichende Pausenregeln, mehrere Modelle in einer Woche und kein Standardmodell sind Hinweise ohne Einfluss auf die Rückgabe.
2. Bei „DATEV-Nr. = ERP-Nr.“ prüft das Skript die ERP-Mitarbeiternummer, wie der Export sie nimmt.
3. Geprüft werden nur aktive Mitarbeiter; „aktiv, aber ausgetreten“ wird genannt, ist aber kein Befund (nach dem Austritt geht ohnehin nichts in den Export).
4. Personen nur mit Kennung; Modelle, Feiertage und von Hand eingetragene Tage mit ihrem Namen (keine Personendaten).

### Tests und Prüfung

Neu: `tests/test_v590_pruefe_zeitregeln.py` (16 Tests) -- Grunddaten ohne Befund, Rundung und Abschluss, Feiertage NW 2026/2027, Berlin ohne Allerheiligen, von Hand eingetragene Tage, alte Grundwerte, Kalenderwochen 1–17 und 49–53 ohne Modell, Hinweise ohne Einfluss, Personalnummern (fehlend, nur Abwesenheiten, führende Null, doppelt mit Leerzeichen, „nichts“ und inaktiv ohne Befund), Gleichsetzung, Eintritt/Austritt/eigene Sollzeit/Zuordnung der Modelle, Zuordnung für den Export, kein Name, ohne `DATABASE_URL`, Aufruf im Kopf, Schreibschutz unter SQLite und PostgreSQL. Gegenproben: Personalnummer auch bei „nichts“ verlangt -> 1 rot; `query_only` weg -> 1 rot; alte Grundwerte nicht erkannt -> 1 rot. Angepasste Erwartungen: keine.

### Nachtrag 1.9.173: Gegenproben zu 1.9.169

Bei 1.9.169 nicht gefahren, mit 1.9.173 nachgeholt (`tests/test_v587_lohnarten.py`): `schlechtwetter_schluessel()` immer Winter ->
`test_schlechtwetter_nach_datum` rot; `PUT /api/time-backoffice/lohnarten` mit der Rolle zum Lesen -> `test_schnittstelle_und_rechte` rot;
`zuordnung()` nimmt eine vorhandene, aber leere Zeile der Art statt der Kategorie -> blieb grün. Festlegung 1.9.169 Nr. 2 („eine leere Art
heißt wie die Kategorie“) war ungeprüft. Neu `test_geleerte_art_heisst_wie_die_kategorie` (Sonderurlaub gesetzt, dann geleert -> U/8000);
die Gegenprobe ist damit rot.

## Lohn L1a-Nachtrag (ab 1.9.174)

Vorgabe Tobias (03.11.2026), je Punkt eine Version: 1 Festlegung 1.9.171 Nr. 2 zurückgezogen (keine automatische Halbierung von 24.12. und 31.12.), 2 Heiligabend und 3 Silvester im Arbeitszeitkalender (nicht im Code), 4 Personalnummern dauerhaft gesperrt (Festlegung 1.9.168 Nr. 3 neu), 5 Schlechtwetter an einem von Hand eingetragenen betriebsfreien Tag mit Rückfrage (Festlegung 1.9.170 Nr. 7 neu), 6 Festlegung 1.9.166 Nr. 1 neu gefasst (nur Doku).

### Umsetzung 1.9.174: Urlaub am 24.12. und 31.12. wieder ganze Tage (Punkt 1)

`app/sollzeit.py::anteil(halber_tag)` -- 0,5 nur für den ausdrücklich gewählten halben Urlaubstag; `URLAUB_HALBE_TAGE` entfällt. `abwesenheit_tage()` rechnet sonst unverändert (Tage mit Sollzeit, ohne gesetzliche Feiertage). Die Spalte `halber_tag` und die Migration `f6c3a8e25b19` bleiben.

### Tests und Prüfung 1.9.174

Gegenprobe: die Halbierung von Urlaub am 24.12./31.12. wieder in `abwesenheit_tage()` -> 3 rot (`test_v589::test_weihnachten_und_silvester_ganze_tage`, `::test_zeiten_zeigt_halbe_tage`, `test_v525::test_antrag_ueber_weihnachten_acht_arbeitstage`).

Angepasste Erwartungen (Regel 28), altes Soll -> neues Soll:
- `test_v589::test_weihnachten_und_silvester_je_halb`, jetzt `…_ganze_tage`: 21.–31.12.2026 7 Tage, 52,50 h -> 8 Tage, 60,00 h; 24.12.2026 und 31.12.2027 je 0,5 Tag, 3,75 h -> 1 Tag, 7,50 h; neu: ein halber Tag am 24.12. bleibt 0,5.
- `test_v589::test_zeiten_zeigt_halbe_tage`: Urlaub 21.–31.12.2026 7 -> 8 Arbeitstage.
- `test_v525::test_antrag_ueber_weihnachten_acht_arbeitstage`: 7 -> 8 Arbeitstage (wie bis 1.9.170).
- `klicktest_sammeleintrag` „Ada: halber Tag und … Arbeitstage in der Liste“: Tom 21.–24.12. 3,5 -> 4 Arbeitstage.

### Umsetzung 1.9.175: Arbeitszeitkalender und Heiligabend (Punkt 2)

`ArbeitszeitKalendertag` (Tabelle `arbeitszeit_kalendertage`, Migration `fcbfd2cea2da`, nur die Tabelle): Schlüssel (für die Zuordnung, aus dem Namen, bleibt), Name, Monat und Tag (eindeutig), Sollzeit (leer = Modellwert), Abwesenheit (Text), bezahlt, „Im Urlaub“ (`IM_URLAUB`: `kein_urlaubstag`), nur gewerbliche, nur Montag bis Freitag, aktiv. `app/arbeitszeitkalender.py`: `gilt()`/`fuer_tag()`/`kalendertag()` (aktiv, Datum, Wochentag, Gruppe), `abwesenheiten()` (je Tag mit Sollzeit: Name, Abwesenheit, Stunden = Sollzeit des Tags, bezahlt -- nicht gespeichert), `naechste()` (für „Zeiten“), `anlegen()`/`aendern()` (Prüfung: Name, Abwesenheit, Tag, „Im Urlaub“, 0–24 h, ein Tag je Datum; gleichzeitig angelegt endet an der Bedingung mit 422). Grunddaten: `ensure_default_kalendertage()` legt Heiligabend an, wenn der Schlüssel fehlt; `ensure_default_lohnart_zuordnungen()` danach die Zeile „kalender:heiligabend“ mit BF ohne Lohnart.

`app/sollzeit.py::soll_zeitraum()`: ein Kalendertag mit Sollzeit geht Tarif und eigenen Werten vor (nur, wenn beschäftigt). `abwesenheit_tage()`: Kalendertage zählen nicht (es gilt deren Abwesenheit). `app/absence_requests.py::_antrag_anlegen()`: halber Urlaubstag an einem Kalendertag 422. `app/schlechtwetter.py::grund_gegen()`: Kalendertag 422 („gilt …“). `app/lohnarten.py`: Zeilen „kalender:<Schlüssel>“ in `liste()`, `kalender()` für den Export, Kennzeichen ohne Lohnart nur dort, `_text()` „BF / Lohnart offen – nicht exportiert“. Schnittstelle: `GET /api/time-backoffice/arbeitszeitkalender` (ab Büro – Auftrag), `POST` und `PUT …/{id}` (alle Felder Pflicht, `require_lohnregeln`). Änderungsprotokoll „Arbeitszeitkalender“ mit lesbaren Feldnamen. Seiten: Block „Arbeitszeitkalender“ mit Dialog in den Einstellungen (vor der Zuordnung, gesperrt wie der ganze Bereich ohne `darf_lohnregeln()`), Karte „Arbeitszeitkalender“ unter „Zeiten → Abwesenheiten“ (`GET /api/zeiten/abwesenheiten` liefert `kalender`).

### Festlegungen 1.9.175 (Bitte bestätigen)

1. Der Arbeitszeitkalender ist eine eigene Liste in Einstellungen → „Zeitregeln und DATEV“: je Tag Monat und Tag (gilt jedes Jahr), Sollzeit, Abwesenheit, bezahlt, „Im Urlaub“, nur gewerbliche, nur Montag bis Freitag, aktiv; ein Eintrag je Datum. Weitere Tage lassen sich anlegen. Ändern dürfen Admin und Büro – Finanzen (wie die Sollzeit, E10), Büro – Auftrag liest. Abschalten statt löschen.
2. Die Abwesenheit des Kalenders wird nicht gespeichert, sondern je Tag abgeleitet: sie steht nicht unter den Anträgen, sondern in einer eigenen Karte „Arbeitszeitkalender“ unter „Zeiten → Abwesenheiten“, und lässt sich nicht einzeln löschen. Ändern sich Kalender, Funktion (gewerblich) oder Eintritt und Austritt, stimmt sie sofort.
3. Neu gefasst mit 1.9.180 (Vorgabe Tobias 03.11.2026): die 7,00 h gelten nur für gewerbliche Mitarbeiter mit einer Sollzeit über 0 an diesem Tag (Tarif oder eigene Werte) -- dann voll, nicht anteilig (Di–Do 3,00 h: Do 24.12.2026 Soll 7,00 h, Freistellung 7,00 h). Wer an dem Wochentag keine Sollzeit hat, bekommt weder Sollzeit noch Freistellung (Mo 24.12.2029 bei Di–Do 3,00 h: Soll 0) -- dieselbe Bedingung wie an Silvester (Festlegung 1.9.176 Nr. 2). Vor dem Eintritt und nach dem Austritt gilt der Tag nicht. Bis 1.9.179 hieß es: „Die 7,00 h gelten wörtlich für alle gewerblichen Mitarbeiter, auch an einem Wochentag, an dem die eigene Sollzeit einer Teilzeitkraft 0 ist (z. B. Mo 24.12.2029 bei Di–Do 3,00 h): Soll 7,00 h, Freistellung 7,00 h.“
4. An einem Kalendertag zählt keine andere Abwesenheit: nicht nur Urlaub (Vorgabe), auch Krankheit, Fortbildung und die übrigen zählen ihn mit 0 -- es gilt die Freistellung. Ein halber Urlaubstag und Schlechtwetter werden dort abgelehnt (422).
5. Neu gefasst mit 1.9.215 (Vorgabe Tobias 05.11.2026, L1a Stufe 6, Punkt 4): je Kalendertag eine Zeile der Zuordnung „kalender:<Schlüssel>“. Für jede Zeile der Zuordnung gilt: Kennzeichen leer -> nicht exportiert; Kennzeichen gesetzt, Lohnart leer -> exportiert, Stunden ohne Lohnart (UU, FE); beides gesetzt -> exportiert mit Lohnart. Die Regel „Zum Kennzeichen gehört eine Lohnart“ entfällt; „Wirkt“ sagt je Zeile den Fall. Bis 1.9.214 hieß es: „Je Kalendertag eine Zeile der Zuordnung „kalender:<Schlüssel>“; nur dort darf ein Kennzeichen ohne Lohnart stehen („BF / Lohnart offen – nicht exportiert“). Exportiert wird die Zeile erst mit Lohnart (L1b); sonst gilt weiter „Zum Kennzeichen gehört eine Lohnart“.“
6. Eine Änderung am Kalender gilt wie eine am Arbeitszeitmodell auch für zurückliegende Jahre (Festlegung 1.9.167 Nr. 4); die Seite sagt das.
7. „Zeiten → Abwesenheiten“ zeigt die aktiven Kalendertage ab heute für dieses und das nächste Jahr, ohne Samstag und Sonntag bei „nur Mo–Fr“.

Offen, nicht gebaut: die Plantafel kennt den Kalender noch nicht -- am 24.12. geplante gewerbliche Mitarbeiter stehen dort nicht als abwesend, die Kapazität rechnet den Tag wie bisher; „Meine Zeiten“ nennt die Freistellung nicht.

### Tests und Prüfung 1.9.175

Neu: `tests/test_v591_arbeitszeitkalender.py` (28 Tests) -- Vorbelegung samt Zuordnung, der Start legt nichts doppelt an und lässt Geändertes stehen, Sollzeit 2026 (Do), 2027 (Fr), 2028 (So), kaufmännisch, Teilzeit Di–Do am Do und am Mo 24.12.2029, vor dem Eintritt, Abwesenheit von selbst (nichts gespeichert), gebuchte Arbeit mindert sie nicht, Urlaub über Heiligabend (gewerblich 7, kaufmännisch 8 Tage), Krankheit 0, „Zeiten“ mit Arbeitstagen und Kalender, halber Urlaubstag nur kaufmännisch, kein Schlechtwetter, Rechte, anlegen/ändern/abschalten, fünf abgelehnte Eingaben, Pflichtfelder, 0–24 h, Zuordnung ohne Lohnart nur am Kalendertag, Prüfskript, Seiten, Migration auf einem Bestand unter SQLite und PostgreSQL. Gegenproben: Kalender-Sollzeit aus -> 5 rot; Kalendertage in `abwesenheit_tage()` mitgezählt -> 5 rot; „nur gewerbliche“ übergangen -> 4 rot; Anlegen mit der Rolle zum Lesen -> 1 rot; Schlechtwetter ohne Kalenderprüfung -> 1 rot. Klicktest neu: `klicktest_arbeitszeitkalender.py` (18 Prüfungen, drei Bilder).

Angepasste Erwartungen (Regel 28), altes Soll -> neues Soll:
- `test_v589::test_weihnachten_und_silvester_ganze_tage` (Mia gewerblich): 21.–31.12.2026 8 Tage, 60,00 h -> 7 Tage, 52,50 h; 24.12. 1 Tag, 7,50 h -> 0; Krankheit am 24.12. 1 Tag, 7,50 h -> 0; Aufbau: der halbe Tag am 23.12. statt 24.12. (0,5 Tag, 3,75 h bleibt).
- `test_v589::test_zeiten_zeigt_halbe_tage`: Urlaub 21.–31.12.2026 8 -> 7 Arbeitstage.
- `test_v525::test_antrag_ueber_weihnachten_acht_arbeitstage` (Tom gewerblich): 8 -> 7 Arbeitstage.
- `test_v424::ABGLEICH`: Aufbau um das Feld `kdSoll` (Schema `ArbeitszeitKalendertagIn.sollzeit`, 0 bis 24 h).
- `test_v109::test_time_backoffice_router_fully_uses_shared_dependency`: altes Soll mindestens 7-mal `_role_dep` und 10-mal `_regeln_dep`, neues Soll mindestens 8 und 12 (der Kalender liest mit `_role_dep`, legt an und ändert mit `_regeln_dep`; gefunden im Lauf der Suite).
- `klicktest_sammeleintrag` „Ada: halber Tag und … Arbeitstage in der Liste“: Tom 21.–24.12. 4 -> 3 Arbeitstage.

### Umsetzung 1.9.176: Silvester, Rückfrage im Urlaub (Punkt 3)

`app/arbeitszeitkalender.py`: `IM_URLAUB` um „fragen“, Vorgabe Silvester (31.12., ohne eigene Sollzeit, „Silvester – unbezahlte Freistellung“, nicht bezahlt, „fragen“); `rueckfrage_tage()` (Tage mit Rückfrage, die für die Person in einem Zeitraum lägen, nur mit Sollzeit), `urlaub_ersetzt()` (Tage, die eine genehmigte Abwesenheit der Kategorie Urlaub mit „ganzer Urlaubstag“ nimmt), `als_urlaubstag()` (leer gilt wie der Vorschlag); `abwesenheiten()` lässt ersetzte Tage weg. `app/sollzeit.py::abwesenheit_tage(…, kalendertag_urlaub)`: ein Tag mit Rückfrage zählt im Urlaub mit seiner Sollzeit, außer bei „frei“. `EmployeeAbsenceRequest.kalendertag_urlaub` und `EmployeeAbsence.kalendertag_urlaub` (Migration `2474667579d8`, leer erlaubt; `downgrade()` entfernt auch die Kalendertage mit Rückfrage samt Zuordnung -- der Stand davor kennt sie nicht). `app/absence_requests.py`: `KalendertagFrage` (bewusst kein ValueError, der Sammeleintrag sammelt ValueError als Ablehnung je Person), `_antrag_anlegen(…, kalendertag_urlaub)` fragt nach der Prüfung auf offene Anträge und speichert die Antwort nur, wenn ein solcher Tag im Urlaub liegt; `_entscheiden()` übernimmt sie; `eintragen()` und `sammel_eintragen()` rollen bei der Rückfrage zurück. Schnittstelle: `kalendertag_urlaub` in `POST /api/absence-requests`, `/sammel` und `POST /api/planning/absences`, ohne Antwort 409 mit `rueckfrage` (`kalendertag_frage_antwort()`); `EmployeeAbsenceRequestOut.kalendertag_urlaub`. Zuordnung „kalender:silvester“ mit AF ohne Lohnart. Seiten: Baustein `_kalendertag_frage.html` (`ktFrageZeigen()`, `ktWahl()`, `ktZuruecksetzen()`) in „Zeiten“, „Meine Zeiten“ und auf der Plantafel; die Listen nennen „Kalendertag als Urlaubstag“ bzw. „Kalendertag frei, kein Urlaubstag“.

### Festlegungen 1.9.176 (Bitte bestätigen)

1. Die Frage stellt der Server: ein Urlaub über Silvester ohne Antwort wird mit 409 abgelehnt, nichts ist gespeichert -- auf allen Wegen (Zeiten einzeln und für mehrere, Meine Zeiten, Plantafel), auch für eine Schnittstelle ohne Dialog. Beim Sammeleintrag gilt eine Antwort für alle, für die der Tag gilt.
2. Gefragt wird nur bei der Kategorie Urlaub und nur, wenn Silvester für die Person gilt (gewerblich, Montag bis Freitag, beschäftigt, Sollzeit über 0). Krankheit und die übrigen Kategorien über Silvester zählen den Tag nicht -- es gilt die Freistellung (wie an Heiligabend, Festlegung 1.9.175 Nr. 4).
3. Die Antwort steht an Antrag und Abwesenheit. „Ganzer Urlaubstag“ zählt den Tag mit der Sollzeit des Modells und ersetzt die Freistellung, sobald der Urlaub genehmigt ist -- bis dahin gilt die Freistellung.
4. Ein Urlaub ohne Antwort (vor 1.9.176 angelegt) gilt wie der Vorschlag: ganzer Urlaubstag, die Freistellung entfällt. Seit 1.9.184 zählt `scripts/pruefe_zeitregeln.py` solche Anträge.
5. Ein halber Urlaubstag an Silvester wird abgelehnt (422, Vorgabe „Halbe Tage gibt es hier nicht“).
6. Gebuchte Arbeit an Silvester kommt wie an Heiligabend zur Freistellung dazu (die Vorgabe nennt das nur für Heiligabend).
7. Die Listen unter „Zeiten“ und „Meine Zeiten“ nennen die Antwort („Kalendertag als Urlaubstag“, „Kalendertag frei, kein Urlaubstag“).
8. „Im Urlaub“ hat im Kalender jetzt zwei Werte („kein Urlaubstag“, „Rückfrage“); jeder weitere Kalendertag kann beides bekommen.

### Tests und Prüfung 1.9.176

Neu: `tests/test_v592_silvester.py` (15 Tests) -- Vorbelegung samt Zuordnung, Sollzeit und Freistellung (kaufmännisch und Sonntag ohne), ohne Antwort 409 auf allen drei Wegen (nichts gespeichert), Antwort „Urlaubstag“ 9 bzw. „frei“ 8 Arbeitstage, die Freistellung entfällt nur bei „Urlaubstag“, keine Frage für kaufmännisch, für einen Urlaub ohne den 31.12. und für Krankheit, kein halber Tag, alter Urlaub ohne Antwort wie der Vorschlag, die Monteurin wird gefragt, kein Schlechtwetter, Seiten, Migration auf einem Bestand unter SQLite und PostgreSQL. Gegenproben: keine Rückfrage -> 4 rot; Antwort nicht gezählt -> 6 rot; Urlaub ersetzt die Freistellung nicht -> 2 rot. Klicktest neu: `klicktest_silvester.py` (20 Prüfungen, zwei Bilder); er fand, dass die Frage auf dem Tablet nur eine halbe Spalte breit war.

Angepasste Erwartungen (Regel 28), altes Soll -> neues Soll (Silvester ist jetzt vorbelegt):
- `test_v591::test_heiligabend_ist_vorbelegt`: Aufbau -- der erste Eintrag statt genau eines.
- `test_v591::test_der_start_legt_nichts_doppelt_an_und_laesst_geaendertes_stehen`: nur Heiligabend -> dazu Silvester (leer, aktiv).
- `test_v591::test_abwesenheit_von_selbst`: Aufbau -- verglichen werden nur die Tage von Heiligabend; Kalendertage in der Datenbank 1 -> 2.
- `test_v591::test_zeiten_zeigt_die_arbeitstage_und_den_kalender`: Aufbau -- der Antrag mit `kalendertag_urlaub` True (7 Arbeitstage bleiben); Kalender 2 -> 4 Tage (dazu Silvester 2026 und 2027).
- `test_v591::test_buero_auftrag_liest_nur`: Einträge „Heiligabend“ -> „Heiligabend, Silvester“, „Im Urlaub“ „kein_urlaubstag“ -> „kein_urlaubstag, fragen“.
- `test_v591::test_anlegen_aendern_abschalten`: Liste rosenmontag, heiligabend -> dazu silvester.
- `test_v591::test_abgelehnte_eingaben`: 1 -> 2 Einträge nach der Ablehnung.
- `test_v591::test_pruefskript_nennt_den_kalender`: „Arbeitszeitkalender: 1 Tage“ -> „2 Tage“.
- `test_v589::test_zeiten_zeigt_halbe_tage`: Aufbau -- der Antrag 21.–31.12. mit `kalendertag_urlaub` True (7 Arbeitstage bleiben).
- `klicktest_arbeitszeitkalender`: Aufbau -- Mias Antrag mit Antwort; „Rosenmontag in Kalender und Zuordnung“ dazu silvester; „nichts gespeichert“ 2 -> 3 Einträge; Karte 3 -> 5 Zeilen (Silvester 2026 und 2027); Bea 2 -> 3 Zeilen; Mias Zeile „· 7 Arbeitstage“ -> „· Kalendertag als Urlaubstag · 7 Arbeitstage“.

### Umsetzung 1.9.177: Personalnummern dauerhaft gesperrt (Punkt 4)

`PersonalnummerVergabe` (Tabelle `personalnummern_vergeben`: Nummer eindeutig, Person, vergeben am; Migration `1e425fe7faa6`). `app/time_backoffice.py`: `personalnummer_gesperrt()` (Meldung mit dem Namen der Person, der die Nummer gehörte; die eigene ist frei), `personalnummer_merken()` (ohne Commit, einmal je Nummer), `fruehere_personalnummern()`. `set_employee_payroll()` prüft die Sperre nach der Prüfung auf eine heute vergebene Nummer und merkt die neue Nummer im selben Commit (zwei gleichzeitige enden an der Bedingung mit 422). `app/routers/employees.py`: bei „DATEV-Nr. = ERP-Nr.“ prüfen Anlegen und Ändern die Mitarbeiternummer (409) und merken die bisherige und die neue. Die Lohnstammdaten liefern `fruehere_personalnummern` (ohne die heutige), die Einstellungen zeigen „früher: …“ unter der Nummer. Migration: die heutigen DATEV-Nummern (ohne Leerzeichen außen, leere nicht), bei Gleichsetzung dazu die Mitarbeiternummern, soweit nicht schon gemerkt; `downgrade()` Tabelle weg. `scripts/pruefe_zeitregeln.py`: Zahl der gemerkten Nummern, Befund, wenn eine aktive Person die Nummer einer anderen trägt.

### Festlegungen 1.9.177 (Bitte bestätigen)

1. Gemerkt wird jede Nummer, die beim Speichern der Lohnstammdaten eingetragen wird; bei „DATEV-Nr. = ERP-Nr.“ auch die Mitarbeiternummer beim Anlegen und Ändern im Mitarbeiterformular (die bisherige und die neue). Das Einschalten der Gleichsetzung selbst merkt nichts.
2. Die Sperre gilt nur gegenüber anderen Personen: dieselbe Person bekommt eine frühere Nummer wieder.
3. Neu gefasst mit 1.9.181 (Vorgabe Tobias 03.11.2026): auch ein Tippfehler bleibt gemerkt (wer 91061 statt 91016 einträgt und danach korrigiert, sperrt 91061 für alle anderen) -- aber der Admin kann eine gemerkte Nummer wieder freigeben, solange sie niemand trägt, mit Warnung im Dialog und Eintrag in der Änderungshistorie; Büro – Finanzen darf das nicht. Notiz für L1b, noch nicht gebaut: sobald L1b Exporte ablegt, bleibt eine Nummer, die in einem abgelegten Export stand, dauerhaft gesperrt und lässt sich nicht mehr freigeben. Bis 1.9.180 hieß es: „Einen Weg, eine Nummer wieder freizugeben, gibt es nicht.“
4. Die Liste der Personalnummern zeigt je Person „früher: …“; die Meldung nennt, wem die Nummer gehörte (die Seite ist nur Admin und Büro – Finanzen zum Ändern offen, die Namen stehen dort ohnehin).
5. Die Migration übernimmt die heutigen DATEV-Nummern und, bei Gleichsetzung, die Mitarbeiternummern; frühere Nummern kennt der Bestand nicht.
6. `scripts/pruefe_zeitregeln.py` zählt die gemerkten Nummern; trägt eine aktive Person die gemerkte Nummer einer anderen (nur an der Sperre vorbei möglich), ist das ein Befund (Rückgabe 1).

### Tests und Prüfung 1.9.177

Neu: `tests/test_v593_personalnummer_gesperrt.py` (8 Tests) -- Nummernwechsel 91008 -> 91016 (Tom bekommt 91008 nicht, Mia wieder), nach Austritt und geleerter Nummer gesperrt, „früher“ in der Liste, eine Nummer einmal in der Datenbank, Gleichsetzung über das Mitarbeiterformular (Ändern und Anlegen 409, die eigene frühere Nummer geht), ohne Gleichsetzung nichts gemerkt, Prüfskript, Migration auf einem Bestand unter SQLite und PostgreSQL. Gegenproben: Sperre übergangen -> 3 rot; beim Speichern nicht gemerkt -> 3 rot; die bisherige Mitarbeiternummer nicht gemerkt -> 1 rot. Angepasste Erwartungen: keine.

### Umsetzung 1.9.178: Schlechtwetter an einem betriebsfreien Tag (Punkt 5)

`app/schlechtwetter.py::betriebsfrei()` (aktiver `PlanningHoliday` an dem Tag), `warnungen()` setzt ihn als erste Warnung (`art` „betriebsfrei“, `employee_id` leer) vor die gebuchten Zeiten (`art` „gebucht“); `SchlechtwetterWarnung` baut eine Meldung: der Tag, dann „Außerdem ist schon Zeit gebucht: …“ (nur gebuchte Zeit: die Meldung wie bisher). Der Weg bleibt derselbe: 409, „trotzdem“ trägt ein. Dialog unverändert (`_schlechtwetter.html` zeigt die Meldung und „Trotzdem eintragen“ bei jeder 409).

### Festlegungen 1.9.178 (Bitte bestätigen)

1. Die Rückfrage gilt für jeden aktiven, von Hand eingetragenen betriebsfreien Tag (`PlanningHoliday`, Einstellungen → Planungsgrundlagen); ein abgeschalteter fragt nicht.
2. Eine Meldung für beides: zuerst der betriebsfreie Tag, dann die gebuchte Zeit; „Trotzdem eintragen“ gilt für alles.
3. Beim Bestätigen eines Antrags (Kolonnenführer, Vorarbeiter, Admin) fragt der Server nicht noch einmal -- wie bei gebuchter Zeit; wer beantragt, sah die Rückfrage schon.

### Tests und Prüfung 1.9.178

Neu: `tests/test_v594_schlechtwetter_betriebsfrei.py` (5 Tests) -- Rückfrage und „trotzdem“, abgeschalteter Tag ohne Rückfrage, betriebsfrei und gebucht in einer Meldung, die Monteurin wird gefragt (Antrag), gesetzlicher Feiertag weiter 422 auch mit „trotzdem“. Gegenproben: betriebsfreier Tag nicht geprüft -> 3 rot; auch abgeschaltete Tage -> 1 rot. `klicktest_schlechtwetter`: Aufbau um einen betriebsfreien Tag (Do 10.12.2026, „Betriebsausflug“), zwei Prüfungen mehr (20 -> 22) und ein Bild; die übrigen Erwartungen unverändert. Angepasste Erwartungen: keine.

### Umsetzung 1.9.179: Festlegung 1.9.166 Nr. 1 neu gefasst (Punkt 6, nur Doku)

Der Satz „So liegt die Arbeitszeit nie unter 6,00 bzw. 9,00 h“ war falsch. Richtig: die Pflichtpause ist der kleinste Wert, der zur Arbeitszeit danach passt; unter 6,00 h fällt die Arbeitszeit nie, unter 9,00 h schon (zwischen 9:00 und 9:30 h Anwesenheit verlangt § 4 ArbZG 30 Minuten). Geprüft mit dem echten Code, je Minute Anwesenheit von 0 bis 12 h mit den Grundregeln (6 h -> 30 min, 9 h -> 45 min): `pflichtpause()` ist an jeder Stelle der kleinste Wert p mit p ≥ gesetzliche Pause der Arbeitszeit (Anwesenheit − p); die Arbeitszeit fällt nie unter 6,00 h; unter 9,00 h liegt sie genau bei 9:01 bis 9:29 h Anwesenheit (29 Fälle), 9:30 h ergibt 9,00 h, ab 9:31 h wächst die Pause bis 45 min.

Berichtigt: Festlegung 1.9.166 Nr. 1 (oben, mit dem alten Wortlaut), die Beschreibung von Lesart A in L0 (Vermerk), CLAUDE.md („Eine Pausenregel“), die Docstrings von `app/work_time_models.py::pflichtpause()` und `tests/test_v584_pause_lesart_a.py` -- nur Text, kein ausführbarer Code; die Überschrift von 1.9.166 im CHANGELOG bleibt als Stand von damals, der Eintrag 1.9.179 nennt die Berichtigung. Tests: keine neuen, angepasste Erwartungen keine.

## Lohn L1a-Korrekturen (ab 1.9.180)

Vorgabe Tobias (03.11.2026), je Punkt eine Version, vorab zwei Prüfungen ohne Commit: A die drei Migrationen des Nachtrags auf einem Bestand proben, B das Bild von Heiligabend mit 6,50 h klären; dann 1 Heiligabend nur bei Sollzeit (Festlegung 1.9.175 Nr. 3 neu), 2 eine gemerkte Personalnummer freigeben (Festlegung 1.9.177 Nr. 3 neu), 3 Text der Rückfrage zu Silvester, 4 test_v564 mit Leeraufruf und Reihenfolge je Testprozess, 5 Prüfskript zählt Urlaub über den 31.12. ohne Antwort, 6 Klicktest-Ordner nicht mehr direkt unter C:\ und eine laufende Liste der Wackler.

### Prüfung A: die Migrationen des Nachtrags auf einem Bestand

Nachgeholt (im Bericht des Nachtrags fehlte der Abschnitt; die Suite enthielt je Migration eine kleine Probe in `tests/test_v591`, `v592`, `v593`, aber ohne Abgleich mit den Modellen). `fcbfd2cea2da`, `2474667579d8` und `1e425fe7faa6` je unter SQLite und PostgreSQL (Schema `pgtest_migprobe_*` der Spielwiese), `1e425fe7faa6` mit und ohne „DATEV-Nr. = ERP-Nr.“ -- acht Läufe, alle wie erwartet. Je Lauf: Bestand mit dem Code des Stands davor (Arbeitskopie `62183a9`, `c0245dd` bzw. `8b09efd`: Grunddaten wie beim Start, sechs Personen mit Mitarbeiter- und DATEV-Nummern -- darunter „ 91008 “ mit Leerzeichen, eine leere, eine ausgetretene Person, deren Mitarbeiternummer 91008 die DATEV-Nummer einer anderen ist --, Urlaub und Krankheit über 24.12. und 31.12., ein halber Tag, ein offener Antrag, eine eigene Sollzeit, ab 1.9.175 ein eigener Kalendertag, ab 1.9.176 eine Antwort zu Silvester), hoch auf die Migration (Bestand unverändert, nur die neue Tabelle bzw. Spalte; bei `1e425fe7faa6` die gemerkten Nummern wie erwartet: DATEV-Nummern ohne Leerzeichen, leere nicht, bei Gleichsetzung die Mitarbeiternummern, 91008 bleibt bei der Person mit dieser DATEV-Nummer), Start des Stands der Migration (legt Heiligabend bzw. Silvester samt Zuordnung an), runter (Tabellen, Spalten, Indizes und alle Zeilen wie der Bestand -- bis auf die Zeilen des Änderungsprotokolls, die der Start geschrieben hat; sie bleiben als Verlauf), Start des Stands davor auf dem zurückgesetzten Bestand, wieder hoch auf head, Start von heute, `alembic compare_metadata` gegen die Modelle: kein Unterschied.

### Prüfung B: Heiligabend mit 6,50 h im Bild

Das Bild 01 des Berichts zum Nachtrag stammte aus `klicktest_arbeitszeitkalender.py` nach dem Schritt „Heiligabend mit 6,5 h“: der Test ändert die Sollzeit, um den Dialog zu prüfen, und nahm das Bild erst danach auf. Ausgeliefert wird 7,00 h (`app/arbeitszeitkalender.py::VORGABEN`). Belegt auf 71d7f52 mit einer frischen Instanz ohne jede Änderung: Datenbank nach dem Start, `GET /api/time-backoffice/arbeitszeitkalender`, die Zeile in den Einstellungen und die Karte unter „Zeiten → Abwesenheiten“ zeigen 7,00 h (zwei Bilder im Bericht). Seit 1.9.180 nimmt der Klicktest zuerst den ausgelieferten Zustand auf (`kalender_fin_ausgeliefert`), das Bild nach der Änderung heißt `kalender_fin_geaendert`.

### Umsetzung 1.9.180: Heiligabend nur an einem Tag mit Sollzeit (Punkt 1)

`app/sollzeit.py::soll_zeitraum()`: zuerst die Sollzeit aus Tarif bzw. eigenen Werten; ein Kalendertag mit eigener Sollzeit ersetzt sie nur, wenn sie über 0 liegt (bis 1.9.179 stets). `app/arbeitszeitkalender.py::kalendertage_im_zeitraum()` nennt nur Tage, an denen die Person Sollzeit hat (optional mit der Sollzeit des Aufrufers, `abwesenheit_tage()` reicht sie durch); daraus folgen `kalendertag()` (halber Urlaubstag, Schlechtwetter), `abwesenheiten()`, `rueckfrage_tage()` und `urlaub_ersetzt()`. Einstellungen: der Block und der Dialog „Kalendertag“ sagen, dass nur betroffen ist, wer an dem Tag Sollzeit hat.

### Festlegungen 1.9.180 (Bitte bestätigen)

1. Die Bedingung gilt für jeden Kalendertag, nicht nur für Heiligabend: ein Kalendertag gilt für eine Person nur an einem Tag, an dem Tarif oder eigene Werte Sollzeit über 0 ergeben; ein Kalendertag mit eigener Sollzeit setzt sie dann voll.
2. An einem solchen Tag ohne Sollzeit nennt Schlechtwetter „keine Sollzeit“ (bis 1.9.179 „gilt Heiligabend …“), und ein halber Urlaubstag wird dort angenommen und zählt 0 -- wie an jedem anderen Tag ohne Sollzeit.

### Tests und Prüfung 1.9.180

Neu in `tests/test_v591_arbeitszeitkalender.py`: `test_ohne_sollzeit_am_wochentag_weder_sollzeit_noch_freistellung` (Teilzeit Di–Do am Mo 24.12. und 31.12.2029: keine Freistellung, kein Kalendertag, keine Rückfrage, Schlechtwetter „keine Sollzeit“). Gegenproben: Sollzeit des Kalenders ohne Bedingung -> 2 rot; Kalendertage ohne die Bedingung Sollzeit -> 2 rot (auch `test_vor_dem_eintritt_kein_heiligabend`). `klicktest_arbeitszeitkalender.py`: Aufbau -- ein Bild vor der ersten Änderung, das spätere Bild umbenannt; Prüfungen unverändert.

Angepasste Erwartungen (Regel 28), altes Soll -> neues Soll:
- `test_v591::test_sollzeit_auch_fuer_teilzeit_mit_eigener_sollzeit`, jetzt `…::test_teilzeit_an_einem_tag_mit_sollzeit_voll`: Mo 24.12.2029 bei Di–Do 3,00 h Soll 7,00 h -> 0,00 h; Aufbau: dazu die Freistellung am Do 24.12.2026 mit 7,00 h.

### Umsetzung 1.9.181: eine gemerkte Personalnummer freigeben (Punkt 2)

`app/permissions.py`: `darf_personalnummer_freigeben()` (nur Admin), `require_personalnummer_freigeben`. `app/time_backoffice.py`: `personalnummer_halter()` (wer die Nummer heute trägt: Lohnstammdaten mit dieser DATEV-Nummer, bei „DATEV-Nr. = ERP-Nr.“ eine Mitarbeiternummer), `personalnummer_freigeben()` (gemerkte Zeile unter Sperre, getragen -> `PersonalnummerGehalten` 409, nicht gemerkt -> 404; Eintrag im Änderungsprotokoll über `record_audit_entry()`: Aktion „Personalnummer freigegeben“, Art „Personalnummer“, alt „gesperrt, gehörte <Name>“, neu „frei“; Zeile gelöscht, ein Commit). `POST /api/time-backoffice/personalnummern/freigeben` (Körper `nummer`, Antwort: die Lohnstammdaten aller). Einstellungen: die Seitenroute gibt `personalnummer_freigeben`; beim Admin steht hinter jeder früheren Nummer „freigeben“, der Dialog `pnrFreigabeDialog` warnt und sendet über `speichern('lohn', …)`; der Text über der Liste nennt die Freigabe.

Notiz für L1b (Vorgabe Tobias, noch nicht gebaut): sobald L1b Exporte ablegt, bleibt eine Nummer, die in einem abgelegten Export stand, dauerhaft gesperrt und lässt sich nicht mehr freigeben -- `personalnummer_freigeben()` prüft dann zusätzlich die Ablage.

### Festlegungen 1.9.181 (Bitte bestätigen)

1. „Niemand trägt sie“: keine Lohnstammdaten mit dieser DATEV-Nummer -- auch nicht die der Person, der sie gemerkt ist -- und bei „DATEV-Nr. = ERP-Nr.“ keine Mitarbeiternummer; sonst lehnt der Server mit dem Namen ab (409). Die heutige Nummer einer Person lässt sich also nicht freigeben, nur eine frühere.
2. Freigeben löscht den Eintrag der Sperre; was frei gegeben wurde, steht nur in der Änderungshistorie (welche Nummer, wem sie gehörte, wer und wann), nicht mehr unter „früher“.
3. Keine Begründung im Dialog: die Warnung nennt den Fall, für den es gedacht ist (Tippfehler, nie abgerechnet).

### Tests und Prüfung 1.9.181

Neu: `tests/test_v595_personalnummer_freigeben.py` (6 Tests) -- der Admin gibt eine frühere Nummer frei (danach frei für Tom, Eintrag im Änderungsprotokoll), Büro – Finanzen, Büro – Auftrag und Monteurin 403 (nichts geändert), eine getragene Nummer 409, eine Mitarbeiternummer bei Gleichsetzung 409 (danach frei), nicht gemerkt 404, leer 422, Seite und Regel. Gegenproben: Prüfung „trägt sie jemand“ übergangen -> 2 rot; Recht der Lohnregeln statt nur Admin -> 1 rot; kein Eintrag im Änderungsprotokoll -> 1 rot. Klicktest neu: `klicktest_personalnummer_freigeben.py` (15 Prüfungen, drei Bilder). Angepasste Erwartungen: keine.

### Umsetzung 1.9.182: Text der Rückfrage zu Silvester (Punkt 3)

„Bitte wählen und noch einmal senden.“ -> „Bitte prüfen und noch einmal senden.“ in `zeiten.html` und `mobil_zeiten.html`, „Bitte wählen und noch einmal eintragen.“ -> „Bitte prüfen und noch einmal eintragen.“ in `planning.html` (dort heißt der Knopf „Eintragen“). Die Vorauswahl „Ganzer Urlaubstag (Vorschlag)“ in `_kalendertag_frage.html` bleibt.

### Tests und Prüfung 1.9.182

`tests/test_v592_silvester.py::test_seiten`: dazu je Seite „Bitte prüfen und noch einmal“ und kein „Bitte wählen und noch einmal“. Gegenprobe: der alte Text in `zeiten.html` zurück -> 1 rot.

Angepasste Erwartungen (Regel 28), altes Soll -> neues Soll:
- `klicktest_silvester` „Ada: der Server fragt“, „Ada: Sammeleintrag -- der Server fragt“, „Mia: der Server fragt“: „Bitte wählen und noch einmal senden.“ -> „Bitte prüfen und noch einmal senden.“; „Plantafel: Frage im Dialog“: „Bitte wählen und noch einmal eintragen.“ -> „Bitte prüfen und noch einmal eintragen.“

### Umsetzung 1.9.183: Wackler test_v564 und Reihenfolge je Testprozess (Punkt 4)

Nur Tests und Testablauf -- beschrieben im Archiv „Testablauf und Klicktest-Werkzeug“, Abschnitt „Wackler test_v564 geklärt, Reihenfolge je Testprozess“ (dort auch die Festlegungen 1.9.183).

### Umsetzung 1.9.184: Prüfskript zählt Urlaub über Silvester ohne Antwort (Punkt 5)

`scripts/pruefe_zeitregeln.py::_urlaub_ohne_antwort()` (aus `_kalender()`): je aktivem Kalendertag mit Rückfrage die Urlaubsanträge (Kategorie Urlaub, `kalendertag_urlaub` leer), deren Zeitraum den Tag enthält und für die `app/arbeitszeitkalender.py::rueckfrage_tage()` heute fragen würde; Zeile „Urlaubsanträge über 31.12. ohne Antwort (vor 1.9.176 angelegt, zählen als ganzer Urlaubstag): N (genehmigt …, offen …, abgelehnt …, zurückgezogen …)“, nur Status mit Anträgen. Kein Befund, keine Personen. Seit 1.9.176 trägt jeder neue Antrag über einen solchen Tag die Antwort -- ein Antrag ohne Antwort stammt von davor.

### Festlegungen 1.9.184 (Bitte bestätigen)

1. Gezählt werden alle Status, auch abgelehnte und zurückgezogene (je für sich genannt) -- für den Lohn zählen nur die genehmigten, die übrigen zeigen, wie viele es vor 1.9.176 gab.
2. Gezählt wird nur, wo die Frage heute gestellt würde (gewerblich, Montag bis Freitag, Sollzeit über 0 an dem Tag); ein Antrag einer kaufmännischen Kraft oder über einen 31.12. am Wochenende hat keine Antwort, weil es nichts zu fragen gibt.

### Tests und Prüfung 1.9.184

Neu in `tests/test_v592_silvester.py`: `test_pruefskript_zaehlt_urlaub_ueber_silvester_ohne_antwort` (drei gezählt: genehmigt, offen, zurückgezogen; nicht gezählt: mit Antwort, ohne den 31.12., kaufmännisch, Krankheit, 31.12. am Sonntag; kein Befund), `test_pruefskript_ohne_solche_antraege` (0). Gegenprobe: die Prüfung „würde heute gefragt“ übergangen -> 1 rot. Angepasste Erwartungen: keine.

### Umsetzung 1.9.185: Klicktest-Ordner und Liste der Wackler (Punkt 6)

Nur Werkzeug und Testablauf -- beschrieben im Archiv „Testablauf und Klicktest-Werkzeug“, Abschnitte „Ordner der Klicktests unter %TEMP%\erp-klicktests“ und „Laufende Liste der Wackler“ (dort auch die Festlegungen 1.9.185).

## Lohn L1a, Stufe 2 (ab 1.9.186)

Vorgabe Tobias (03.11.2026), je Punkt eine Version: 1 „Meine Zeiten“ heftet eine laufende Zeit an, die vor dem Monatsanfang begann (Startdatum, „Beenden“, Test mit stehender Uhr am 01.12.2026); 2 „Meine Zeiten“ zeigt die Freistellungen des Arbeitszeitkalenders mit Stunden und „bezahlt“/„unbezahlt“; 3 die Plantafel kennt den Arbeitszeitkalender (betroffene gewerbliche Mitarbeiter abwesend, Kapazität, Einplanen nach Hinweis wie am betriebsfreien Tag); 4 in Einstellungen → „Zeitregeln und DATEV“ bleibt in der Tabelle der Personalnummern die Spalte Mitarbeiter beim waagrechten Rollen stehen; 5 `Zaehler` in `test_v564`: Speicherbereinigung auch nach einem Fehler beim Zählen wieder an; 6 „freigeben“ nur, wo die Freigabe möglich ist, sonst wer die Nummer trägt.

### Umsetzung 1.9.186: laufende Zeit aus dem Vormonat angeheftet (Punkt 1)

`app/meine_zeiten.py::angeheftet()`: die laufende Zeit (`active_entry()`), wenn ihr Tag vor dem ersten Tag des angezeigten Monats liegt -- Startdatum, Beginn, Zeitart, Auftrag, Kennzeichen „Auftrag abgeschlossen/storniert“; `meine_zeiten()` liefert sie als `angeheftet`. `GET /api/field-view/meine-zeiten` setzt `beenden` und `grund`: „Beenden“ nur, wer Zeiten bucht (`darf_zeit_buchen()`, sonst `ZEITEN_NUR_LESEN`) und wen `app/routers/time_tracking.py::ende_nachtragen_pruefen()` durchlässt (bis 1.9.185 `_ende_nachtragen_pruefen`, jetzt öffentlich) -- sonst steht dessen Meldung als `grund` da. Seite `mobil_zeiten.html`: Zeile `#angeheftet` zwischen Kopf und Liste der Buchungen (Signalfarbe wie „Wartet auf dich“), Dialog „Laufende Zeit beenden“ mit „Feierabend am <Starttag> um“, Vorschau über `GET /api/time-entries/{id}/ende-vorschau` (`lesen()`), Buchung über `POST …/ende-nachtragen` (`speichern()`, danach neu geladen), Ergebnis „Feierabend am Mo 30.11. eingetragen: anwesend … · Pause nach Zeitregel … · gebucht …“. In ihrem eigenen Monat steht die Zeit wie bisher an ihrem Tag mit „Feierabend auf „Heute“ eintragen“.

### Festlegungen 1.9.186 (Bitte bestätigen)

1. „Beenden“ trägt das Ende am Starttag ein, im Dialog auf „Meine Zeiten“, mit denselben Endpunkten und Regeln wie „Feierabend eintragen“ auf „Heute“ -- kein Wechsel auf „Heute“, auch für das Büro, das „Heute“ nicht hat.
2. Angeheftet wird nur in einem Monat nach dem Start; im Monat des Starts steht die Zeit an ihrem Tag, in einem Monat davor gar nicht.
3. Wer die Zeit nicht beenden darf (Mitglied einer Gruppenzeit, Monteurin im abgeschlossenen Monat, Büro – Auftrag), sieht sie angeheftet ohne „Beenden“, mit der Meldung, mit der der Server das Nachtragen ablehnen würde.

### Tests und Prüfung 1.9.186

Neu: `tests/test_v598_meine_zeiten_angeheftet.py` (9 Tests, stehende Uhr Di 01.12.2026 10:00) -- angeheftet am 01.12. mit Startdatum und „Beenden“, im November an ihrem Tag, eine heute begonnene nie angeheftet, „Beenden“ über Vorschau und Nachtragen (danach nichts angeheftet, die Buchung im November), Gruppenzeit nur der Kolonnenführer, abgeschlossener Monat und Büro – Auftrag ohne „Beenden“ mit Meldung, Seite in node (Text, Knopf, Grund, leer), Dialog über die Endpunkte. Gegenproben: nie anheften -> 3 rot; immer anheften -> 2 rot; Regeln von „Ende nachtragen“ übergangen -> 2 rot. Klicktest neu: `scripts/klicktest_meine_zeiten_angeheftet.py` (16 Prüfungen, fünf Bilder: 412 px dunkel, 1280 × 620 hell, Dialog, danach, Gruppenzeit). Beim Ansehen der Bilder gefunden und vor dem Commit behoben: die Meldung „Bitte die Uhrzeit des Feierabends angeben.“ blieb nach der Eingabe einer Uhrzeit neben der Vorschau stehen -- sie verschwindet jetzt mit jeder Eingabe (im Klicktest geprüft).

### Umsetzung 1.9.187: Freistellungen in „Meine Zeiten“ (Punkt 2)

`app/meine_zeiten.py::meine_zeiten()` liefert `freistellungen`: `app/arbeitszeitkalender.py::abwesenheiten()` für den angezeigten Monat (je Tag Abwesenheit, Name, Stunden = Sollzeit des Tags, bezahlt) -- dieselbe Rechnung wie der Lohn, abgeleitet, nichts gespeichert. Seite `mobil_zeiten.html`: `#abwFrei` in der Karte „Abwesenheit“ unter dem Text, je Tag eine Zeile in der Form der Anträge (`.antrag`): Abwesenheit fett, darunter Wochentag und Datum, Stunden, „bezahlt“/„unbezahlt“, rechts „gilt ohne Antrag“ (`freistellungenZeichnen()`); ohne Freistellung im Monat ausgeblendet.

### Festlegungen 1.9.187 (Bitte bestätigen)

1. Die Freistellungen stehen in der Karte „Abwesenheit“ für den angezeigten Monat, je Tag eine Zeile wie ein Antrag, mit „gilt ohne Antrag“ statt eines Status -- nicht unter „Meine Anträge“ (sie sind kein Antrag, Festlegung 1.9.175 Nr. 2) und nicht unter den Buchungen (sie sind keine Buchung).
2. Die Stunden sind die Sollzeit des Tags (Heiligabend 7,00 h, Silvester die des Modells, bei Teilzeit die eigene) -- dieselbe Zahl wie für den Lohn; Kacheln und „Monat“ zählen nur Buchungen und bleiben ohne sie.
3. Neu gefasst mit 1.9.206 (Vorgabe Tobias, L1a Stufe 4, Punkt 5; am Code nichts): Sie erscheinen nur im Monat des Kalendertags. Die Seite „Meine Zeiten“ öffnet keine künftigen Monate (‹ › nur bis zum laufenden Monat, keinen Monat aus der Adresse) -- dort steht Heiligabend also ab dem 1. Dezember da. Die Schnittstelle `GET /api/field-view/meine-zeiten?monat=JJJJ-MM` liefert dagegen auch einen künftigen Monat samt Freistellungen. Bis 1.9.205 hieß es: „künftige Monate öffnet „Meine Zeiten“ nicht (‹ › nur bis zum laufenden Monat) -- Heiligabend steht also ab dem 1. Dezember da.“ -- das galt nur für die Seite (gemeldet in den Gegenproben 1.9.201).

### Tests und Prüfung 1.9.187

Neu: `tests/test_v599_meine_zeiten_freistellungen.py` (7 Tests) -- Dezember 2026 mit Heiligabend (7,00 h, bezahlt) und Silvester (7,50 h, unbezahlt), andere Monate leer, Teilzeit Di–Do am Donnerstag voll und Silvester mit 3,00 h, im Dezember 2029 (Montag) keine, kaufmännisch keine, Silvester fehlt nach genehmigtem Urlaub mit „ganzer Urlaubstag“ (offen noch nicht), Seite in node (Zeilen, Maskierung, leer). Gegenproben: keine Freistellungen geliefert -> 3 rot; „bezahlt“/„unbezahlt“ vertauscht -> 1 rot. Klicktest neu: `scripts/klicktest_meine_zeiten_freistellungen.py` (11 Prüfungen, drei Bilder: Mia 1280 × 620 hell und 412 px dunkel, Tom mit Urlaub über Silvester; Kim kaufmännisch ohne).

### Umsetzung 1.9.188: die Plantafel kennt den Arbeitszeitkalender (Punkt 3)

`app/arbeitszeitkalender.py::freistellungen(db, personen, start, ende)`: {(Person, Tag): Kalendertag} für viele Personen auf einmal -- dieselbe Regel wie `kalendertage_im_zeitraum()` (aktiv, Datum, Wochentag, Gruppe, Sollzeit über 0); liegt kein aktiver Kalendertag im Zeitraum, bleibt es bei einer Abfrage, sonst die Sollzeit nur an den Kalendertagen (`app/sollzeit.py::soll_an_tagen()`: je Gruppe naher Tage ein `soll_zeitraum()`, nicht über bis zu zwei Jahre des Vorschlags). `app/planning.py`: `Freistellung` (abgeleitete Abwesenheit mit den Feldern, die Kapazität und Tafel lesen), `_abwesend_map()` (Abwesenheiten je Person und Tag samt Freistellungen, eine gespeicherte geht vor) in `_conflicts()`, `planning_board()` und `planning_suggestion()`; in `_conflicts()` je Einsatz und Tag ein Hinweis `kalendertag` („Heiligabend – Mia Test, Tom Test“) statt der Warnung `absence`, `HINWEIS_ARTEN` um `kalendertag`. Seite `planning.html`: `KONFLIKT_ART.kalendertag` = „Freistellung: “. Die Liste „Abwesenheiten“ der Tafel bleibt ohne sie.

### Festlegungen 1.9.188 (Bitte bestätigen)

1. Auf der Tafel ist die Freistellung eine Abwesenheit des Tages: die Betroffenen haben dort keine Kapazität, wie bei Urlaub. Der Einsatz bekommt aber einen Hinweis (wie am betriebsfreien Tag), keine Warnung wie bei einer Abwesenheit: gespeichert wird ohne Rückfrage, der Hinweis steht in der Antwort und über der Tafel, der Einsatz ist markiert und zählt unter „Konflikte“ -- wie der betriebsfreie Tag.
2. Ein Hinweis je Einsatz und Tag mit allen Betroffenen („Freistellung: Heiligabend – Mia Test, Tom Test · 24.12.“).
3. Neu gefasst mit 1.9.211 (Vorgabe Tobias, L1a Stufe 5, Punkt 4): Wer betroffen ist und wie viel Kapazität jemand an einem Tag hat, entscheidet die Sollzeit des Lohns (Tarif bzw. eigene Werte) -- Ben (Teilzeit ohne Donnerstag) hat am 24.12. keine Kapazität, ist aber nicht freigestellt. Bis 1.9.210 hieß es: „die Kapazität der Tafel rechnet für alle anderen weiter mit Wochenstunden und den Arbeitstagen der Planung -- Ben (Teilzeit ohne Donnerstag) steht am 24.12. wie bisher mit Kapazität.“
4. Eine gespeicherte Abwesenheit am selben Tag geht vor (Warnung wie bisher). Büro – Auftrag sieht am Mitarbeiter „abwesend“ wie bei jeder Abwesenheit; der Hinweis am Einsatz nennt den Tag für alle Rollen (keine Krankheit).
5. Die Freistellung steht nicht in der Liste „Abwesenheiten“ der Tafel und lässt sich dort nicht löschen -- sie wird abgeleitet (Festlegung 1.9.175 Nr. 2).

### Tests und Prüfung 1.9.188

Neu: `tests/test_v600_plantafel_kalender.py` (7 Tests) -- `freistellungen()` nur mit Sollzeit (Ben nicht) und ohne Kalendertag leer, Tafel (Mitarbeiter, Kolonne, Kapazität, Liste der Abwesenheiten, Hinweis, Konfliktzahl), Speichern über Silvester ohne Rückfrage mit Hinweis, gespeicherter Urlaub geht vor (Warnung für Mia, Hinweis nur Tom), abgeschalteter Kalendertag wie bisher, Planungsvorschlag, Seite. Gegenproben: Konflikte ohne Freistellungen -> 3 rot; Tafel ohne Freistellungen -> 1 rot; Bedingung Sollzeit übergangen -> 5 rot. Klicktest neu: `scripts/klicktest_plantafel_kalender.py` (11 Prüfungen, vier Bilder: Kolonnen, Dialog des Einsatzes, Mitarbeiter, Hinweis nach dem Speichern; Büro – Auftrag).

Angepasste Erwartungen (Regel 28), altes Soll -> neues Soll:
- `test_v563::test_feiertag_200_mit_hinweis` (Tom gewerblich, Einsatz 24.–25.12.2026): Hinweise [Feiertag 25.12.] -> [Freistellung „Heiligabend – Tom Test“ 24.12., Feiertag 25.12., „Kapazität reicht um 1,00 h nicht aus“] -- an beiden Tagen arbeitet Tom nicht mehr; gefunden im Lauf vor dem Commit.

Nachtrag 1.9.188 (nach dem Endlauf auf 0af82d2, eigener Commit ohne neue Versionsnummer, Festlegung 1.8.100 Nr. 5): im Bild „Mitarbeiter“ des Endlaufs stand am 24.12. die ganze Freistellung in der 120 px schmalen Tageszelle (`.absence-mark`, rechts unten) über der Kapazität (`.capacity-label`, links unten) -- beide unleserlich. Suite und Klicktests waren grün, weil der Klicktest nur den Text las. Behoben: `planning_board()` gibt beim Mitarbeiter für eine Freistellung den Namen des Tags (`Freistellung.kalendertag`, „Heiligabend“) statt der Abwesenheit; `planning.html` kürzt `.absence-mark` auf die Zelle abzüglich 58 px mit „…“ und trägt den vollen Text als Tooltip (Absicherung für lange Arten auch anderer Abwesenheiten, ohne eigenen Test -- seit 1.9.194 mit Test, siehe „Lohn L1a, Stufe 3“). Die Kolonne und die Hinweise nennen weiter die ganze Freistellung. `klicktest_plantafel_kalender` misst jetzt in Mias Zelle die Lage beider Angaben (nebeneinander, in der Zelle) und dass nichts abgeschnitten ist (11 -> 12 Prüfungen). Gegenproben: der lange Text zurück -> Klicktest 2 rot (Text, abgeschnitten), `test_v600` 1 rot.

Angepasste Erwartungen des Nachtrags (Regel 28), altes Soll -> neues Soll:
- `test_v600::test_tafel_zeigt_die_betroffenen_abwesend`: Mia und Tom am 24.12. „Heiligabend – bezahlte Freistellung“ -> „Heiligabend“; dazu geprüft, dass die Kolonne die ganze Freistellung nennt.
- `klicktest_plantafel_kalender` „Mitarbeiter am 24.12.: Mia und Tom freigestellt, Ben wie bisher“: [„Heiligabend – bezahlte Freistellung“ ×2, „“] -> [„Heiligabend“ ×2, „“].

### Umsetzung 1.9.189: Spalte Mitarbeiter bleibt stehen (Punkt 4)

`settings.html`: die Tabelle trägt die Klasse `lohn-tabelle`, ihr Rollbereich die ID `payrollRollen`; `.lohn-tabelle th:first-child, td:first-child` mit `position:sticky; left:0`, deckend (`--card`), rechts eine Linie (`box-shadow`), 150–220 px breit, lange Namen brechen um. Sonst nichts geändert (die Kopfzeile rollt senkrecht wie bisher mit).

### Festlegung 1.9.189 (Bitte bestätigen)

1. Stehen bleibt nur die Spalte Mitarbeiter, beim waagrechten Rollen; die Kopfzeile rollt beim senkrechten Rollen weiter mit (die Tabelle hat höchstens 60 % der Fensterhöhe).

### Tests und Prüfung 1.9.189

`scripts/klicktest_personalnummer_freigeben.py` um zwei Prüfungen (15 -> 17): bei 1440 px rollt die Tabelle waagrecht; ganz nach rechts gerollt stehen Kopf- und Zeilenzelle „Mitarbeiter“ am linken Rand (Abstand 0), obenauf (`elementFromPoint`), alle vier Namen lesbar, die Spalte ERP-Nr. darunter verschwunden; Bild `lohn_tabelle_gerollt_1440`. Keine neue Prüfung in pytest: die Regel ist reines CSS, gemessen wird im Browser.

### Umsetzung 1.9.190: Zähler in test_v564 (Punkt 5)

Nur Tests -- beschrieben im Archiv „Testablauf und Klicktest-Werkzeug“, Abschnitt „Zähler in test_v564: Speicherbereinigung in jedem Fall zurück“ (dort auch die Festlegung 1.9.190).

### Umsetzung 1.9.191: „freigeben“ nur, wo es geht (Punkt 6)

`app/time_backoffice.py::personalnummern_traeger(db, nummern)`: {Nummer: Name} der heutigen Träger -- dieselbe Regel wie `personalnummer_halter()` (Lohnstammdaten mit dieser DATEV-Nummer, bei „DATEV-Nr. = ERP-Nr.“ die getrimmte Mitarbeiternummer), für alle gemerkten Nummern in einem Zug; `payroll_rows()` gibt jeder Zeile `fruehere_traeger` (nur getragene früheren Nummern), `EmployeePayrollSettingsOut.fruehere_traeger`. Seite `settings.html`: `fruehereNummer(p, n)` -- an einer getragenen Nummer „(trägt heute <Name>)“, sonst für den Admin „freigeben“, sonst die Nummer. Der Server prüft bei der Freigabe weiter selbst (409).

### Festlegungen 1.9.191 (Bitte bestätigen)

1. „(trägt heute <Name>)“ steht an einer getragenen Nummer für jede Rolle, die die Liste sieht (Admin, Büro – Finanzen, lesend Büro – Auftrag) -- nicht nur statt des Knopfs beim Admin.
2. Ob eine Nummer getragen ist, entscheidet dieselbe Regel wie die Freigabe; trägt die Person ihre frühere Nummer noch in den Lohnstammdaten (bei „DATEV-Nr. = ERP-Nr.“), steht dort ihr eigener Name -- freigeben geht dann nicht, wie bisher (Festlegung 1.9.181 Nr. 1).

### Tests und Prüfung 1.9.191

Neu: `tests/test_v601_freigeben_nur_wo_moeglich.py` (4 Tests) -- die Liste nennt den Träger (und nach seiner Änderung nicht mehr; getragen <=> 409 beim Freigeben), bei Gleichsetzung auch die Mitarbeiternummer (mit Leerzeichen, getrimmt), Seite in node mit und ohne Recht zum Freigeben (Maskierung). Gegenproben: keine Träger geliefert -> 2 rot; Seite übergeht den Träger -> 2 rot.

Angepasste Erwartungen (Regel 28), altes Soll -> neues Soll:
- `test_v595::test_seite`, nur der Aufbau: statt `${PNR_FREIGEBEN?p.fruehere_personalnummern.map(` jetzt `früher: ${p.fruehere_personalnummern.map(n=>fruehereNummer(p,n)).join(', ')}` (der Knopf entsteht in `fruehereNummer()`).
- `klicktest_personalnummer_freigeben` „Ada: frühere Nummern mit „freigeben““: Pia „früher: 91030 freigeben“ -> „früher: 91030 (trägt heute Kai Monteur)“.
- dort „Ada: Dialog zu 91030 mit Warnung“ und „Ada: 91030 trägt Kai -- Meldung, nichts geändert“ (Klick auf „freigeben“, Fehler im Dialog) -> „Ada: an 91030 kein „freigeben“, dafür wer sie trägt“ und „Ada: 91030 trägt Kai -- der Server lehnt ab, nichts geändert“ (derselbe POST, 409 mit derselben Meldung).
- dort „Ada: Pia weiter „früher: 91030““: „früher: 91030 freigeben“ -> „früher: 91030 (trägt heute Kai Monteur)“ (nach neuem Laden der Seite).
- dort „Fin: „früher: 91030“ ohne Knopf“: „früher: 91030“ -> „früher: 91030 (trägt heute Kai Monteur)“.

## Lohn L1a, Stufe 3 (ab 1.9.192)

Vorgabe Tobias (04.11.2026), zuerst vier kleinere Punkte je eine Version: 1 „Meine Zeiten“, Monat des Starts -- eine laufende Zeit von einem früheren Tag desselben Monats bekommt denselben Dialog „Beenden“ wie die angeheftete Zeit, der Link nach /mobil entfällt; 2 Plantafel -- der Satz über der Tafel nennt auch Freistellungen; 3 ein Test für die Kürzung mit „…“ in der schmalen Zelle der Plantafel (Nachtrag zu 1.9.188); 4 die Testaufbauten schließen ihre Engine selbst, die Fehler beim Abräumen je vollem Lauf gehen auf 0. Danach 5: für jede Festlegung von 1.9.166 bis 1.9.191 eine Gegenprobe nach Regel 24, in Blöcken je Versionsbereich -- bleibt eine grün, fehlenden Test nachziehen und dieselbe Gegenprobe noch einmal.

### Umsetzung 1.9.192: „Beenden“ im Monat des Starts (Punkt 1)

`app/meine_zeiten.py::_zeile()` gibt einer laufenden Zeit ihren Starttag (`start_tag`). `GET /api/field-view/meine-zeiten` setzt „beenden“ und „grund“ jetzt an der angehefteten Zeit und an jeder Zeile mit `laeuft_seit_frueher` -- dieselbe Prüfung wie seit 1.9.186 (`darf_zeit_buchen()`, sonst `ZEITEN_NUR_LESEN`; dann `ende_nachtragen_pruefen()`, sonst dessen Meldung). Seite `mobil_zeiten.html`: an der Zeile statt des Links `<a href="/mobil">Feierabend auf „Heute“ eintragen</a>` der Knopf „Beenden“ (`data-aktion="beenden"`, `data-id`) bzw. die Meldung (`.zeile-zu`, `data-grund`); `laufendeZeit(z)` gibt dem Dialog dieselben Felder wie die angeheftete Zeit (id, Starttag, Beginn, Zeitart, Auftrag), `beendenOeffnen(a)` nimmt sie als Argument (bis 1.9.191 las er nur `D.angeheftet`).

### Festlegungen 1.9.192 (Bitte bestätigen)

1. „Beenden“ steht an jeder laufenden Zeit, die an einem früheren Tag begann -- im Monat des Starts an der Zeile, in einem späteren Monat angeheftet; eine heute begonnene Zeit bekommt es nicht (sie stoppt auf „Heute“ normal, das Büro unter „Zeiten“).
2. Der Link nach /mobil entfällt für alle Rollen, auch für die Monteurin: der Dialog liegt auf der Seite, „Heute“ bleibt im Reiter.
3. Wer nicht beenden darf, sieht an der Zeile die Meldung, mit der der Server das Nachtragen ablehnen würde -- wie an der angehefteten Zeit (Festlegung 1.9.186 Nr. 3).

### Tests und Prüfung 1.9.192

Neu: `tests/test_v602_meine_zeiten_beenden_im_monat.py` (8 Tests, stehende Uhr Mi 18.11.2026 10:00) -- die Zeile vom 16.11. mit Starttag und „Beenden“ (nichts angeheftet), eine heute begonnene ohne, Beenden über Vorschau und Nachtragen am Starttag, Büro – Finanzen: „Heute“ 403, „Beenden“ gilt und bucht, ohne „Beenden“ die Meldung (Gruppenzeit, Monat abgeschlossen, Büro – Auftrag), Seite in node (Knopf statt Link, Meldung maskiert, `laufendeZeit()` und der Klick in „Buchungen“). Gegenproben: der Router setzt „beenden“ nur an der angehefteten Zeit -> 3 rot; kein Starttag -> 2 rot; der alte Link an der Zeile -> 2 rot, `klicktest_meine_zeiten` 53 von 59.

Angepasste Erwartungen (Regel 28), altes Soll -> neues Soll:
- `klicktest_meine_zeiten` „Ole: läuft seit gestern, Weg zu „Heute““, jetzt „Ole: läuft seit gestern, „Beenden“ statt des Wegs zu „Heute““: [„… läuft seit 06:45“, „Feierabend auf „Heute“ eintragen“, „/mobil“] -> [„… läuft seit 06:45“, „Beenden“, kein Link, nichts angeheftet]; dazu fünf Prüfungen (Ole: Dialog, Vorschau, gebucht; Fin aus Büro – Finanzen: „Heute“ 403 und „Beenden“, gebucht), 54 -> 59, ein Bild mehr (`meine_zeiten_beenden_im_monat_hell`); Aufbau um das Konto Fin mit eigener Zeit seit Mo 12.10. 07:30.
- `klicktest_monteurin_regeln` „Meine Zeiten: die offene Zeit „läuft seit 06:45“ ohne Stunden, Weg zu „Heute““: [„…“, „“, „Feierabend auf „Heute“ eintragen“, „/mobil“] -> [„…“, „“, „Beenden“, kein Link]; Mia beendet die Zeit danach wie bisher auf „Heute“ (31 Prüfungen).

### Umsetzung 1.9.193: Freistellungen im Satz über der Tafel (Punkt 2)

`planning.html`, Hinweis bei Konflikten (`#conflictBanner`): „Berücksichtigt werden Doppelbelegungen, Abwesenheiten, Freistellungen, Feiertage und unzureichende Stundenkapazität.“ (bis 1.9.192 ohne „Freistellungen“). Sonst nichts geändert -- die Liste „Abwesenheiten“ der Tafel bleibt ohne Freistellungen (Festlegung 1.9.188 Nr. 5).

### Tests und Prüfung 1.9.193

`tests/test_v600_plantafel_kalender.py::test_seite_nennt_die_freistellung` prüft dazu den Satz; `klicktest_plantafel_kalender` liest den Hinweis über der Tafel in der Woche von Heiligabend (12 -> 13 Prüfungen). Gegenprobe: der alte Satz zurück -> `test_v600` 1 rot, der Klicktest 12 von 13. Angepasste Erwartungen: keine; keine neue Festlegung.

### Umsetzung 1.9.194: Test der Kürzung in der Zelle (Punkt 3)

Nur Tests, am Programm nichts geändert. `scripts/klicktest_plantafel_kalender.py`: Kai (gewerblich, in keiner Kolonne -- Einsatz A und die Kolonne Nord bleiben, wie sie sind) bekommt über `app/absence_requests.py::eintragen()` eine genehmigte Fortbildung am Di 22.12.2026 mit der Art „Fortbildung Abdichtungstechnik Flachdach mit Herstellerschulung (Teil 2)“. In der Ansicht „Mitarbeiter“ misst `GEKUERZT` in Kais Zelle am 22.12.: Kapazität links, die Art rechts daneben ohne Überlappung; die Art ganz in der Zelle; gekürzt (`scrollWidth` über `clientWidth`), `text-overflow: ellipsis`, `white-space: nowrap`; Text und `title` = die volle Art. Im Bild `3_mitarbeiter_heiligabend` steht „Fortbildun…“ neben „0/0 h · 0%“. `tests/test_v600_plantafel_kalender.py::test_lange_abwesenheit_in_der_zelle_gekuerzt_mit_tooltip`: die Regel `.absence-mark` enthält Lage, Höchstbreite, `overflow:hidden`, `text-overflow:ellipsis` und `white-space:nowrap`, das Markup setzt `title="${esc(absence)}"`.

### Tests und Prüfung 1.9.194

Klicktest 13 -> 14 Prüfungen, pytest ein Test mehr. Gegenproben: die Regel `.absence-mark` wie vor dem Nachtrag (ohne Höchstbreite und Kürzung) -> Klicktest 13 von 14 (Art über der Kapazität, nicht gekürzt, „clip“, „normal“), `test_v600` 1 rot; ohne `title` -> Klicktest 12 von 14 (auch Mias Tooltip „Heiligabend“), `test_v600` 1 rot. Angepasste Erwartungen: keine (Aufbau: Kai mit seiner Fortbildung dazu; die übrigen Prüfungen betreffen Kolonne Nord, Mia, Tom und Ben). Keine neue Festlegung.

### Umsetzung 1.9.197: Gegenproben zu 1.9.166–1.9.169 (Punkt 5, Block 1)

Tabelle, Befunde und Bemerkungen: `docs/archiv/gegenproben-lohn-l1a.md`, Abschnitt „1.9.197“. 48 Gegenproben zu 23 Festlegungen; 9 blieben grün
(Befunde an 1.9.166 Nr. 3, 1.9.167 Nr. 1, 3, 4, 1.9.168 Nr. 2, 1.9.169 Nr. 5), 7 neue Tests in `tests/test_v604_festlegungen_166_169.py`, danach
alle rot. Zwei Abweichungen von Wortlaut und Code gemeldet, nicht geändert: 1.9.169 Nr. 3 („nicht je Art“) -- `zuordnung()` prüft die Art auch bei
Schlechtwetter vor der Jahreszeit, eine gespeicherte Zeile „art:schlechtwetter“ ginge Winter und Sommer vor (zu entscheiden: Code oder Wortlaut);
1.9.168 Nr. 3 nannte die Freigabe von 1.9.181 nicht (oben vermerkt). Angepasste Erwartungen: keine.

### Umsetzung 1.9.198: Gegenproben zu 1.9.170–1.9.173 (Punkt 5, Block 2)

Tabelle, Befunde und Bemerkungen: `docs/archiv/gegenproben-lohn-l1a.md`, Abschnitt „1.9.198“. 67 Gegenproben zu 20 Festlegungen; 22 blieben grün
(17 Befunde), neue Tests in `tests/test_v605_festlegungen_170_173.py`, danach alle rot. Gemeldet, nicht geändert, zu entscheiden:
- 1.9.170 Nr. 5 („die Meldung nennt jede Person mit Grund“): ist jemand am Tag schon abwesend, lautet die Meldung des Schlechtwetter-Dialogs „Nicht
  eingetragen: Für diesen Mitarbeiter besteht im beantragten Zeitraum bereits eine genehmigte Abwesenheit.“ -- ohne Namen, nur ein Grund
  (`app/schlechtwetter.py::eintragen()` sammelt nur die Gründe aus `grund_gegen()`; „schon abwesend“ wirft erst `_antrag_anlegen()`/`_entscheiden()`).
- 1.9.171 Nr. 5 („wer schon abwesend ist, muss abgewählt werden“): gilt nur beim Admin; trägt Büro – Finanzen ein, entstehen offene Anträge (200),
  „schon abwesend“ scheitert erst bei der Entscheidung (wie beim Einzelantrag seit 1.9.101).
- 1.9.170 Nr. 3 (der Admin entscheidet auch unter „Zeiten“): `POST /api/absence-requests/{id}/review` prüft `grund_gegen()` nicht -- ein
  Schlechtwetter-Antrag an einem Tag ohne Sollzeit wird dort genehmigt, der Schlechtwetter-Dialog lehnt denselben ab (422).
Angepasste Erwartungen: keine.

### Umsetzung 1.9.199: Gegenproben zu 1.9.174–1.9.179 (Punkt 5, Block 3)

Tabelle, Befunde und Bemerkungen: `docs/archiv/gegenproben-lohn-l1a.md`, Abschnitt „1.9.199“. 77 Gegenproben zu 24 Festlegungen; 15 blieben grün
(14 Befunde an 1.9.175 Nr. 1, 6, 7, 1.9.176 Nr. 1, 6, 7, 8, 1.9.177 Nr. 1, 1.9.178 Nr. 3), 15 neue Tests in `tests/test_v606_festlegungen_174_179.py`,
danach alle rot. Wortlaut und Code passen. Angepasste Erwartungen: keine.

### Umsetzung 1.9.200: Gegenproben zu 1.9.180–1.9.185 (Punkt 5, Block 4)

Tabelle, Befunde und Bemerkungen: `docs/archiv/gegenproben-lohn-l1a.md`, Abschnitt „1.9.200“ (die Werkzeug-Festlegungen 1.9.183 und 1.9.185 stehen
dort mit). 42 Gegenproben zu 13 Festlegungen; 13 blieben grün (Befunde an 10 Aussagen), 10 neue Tests in `tests/test_v607_festlegungen_180_185.py`,
danach alle rot. Wortlaut und Code passen. Angepasste Erwartungen: keine.

### Umsetzung 1.9.201: Gegenproben zu 1.9.186–1.9.191 (Punkt 5, Block 5)

Tabelle, Befunde und Bemerkungen: `docs/archiv/gegenproben-lohn-l1a.md`, Abschnitt „1.9.201“. 43 Gegenproben zu 15 Festlegungen; 8 blieben grün
(7 Befunde), 7 neue Tests in `tests/test_v608_festlegungen_186_191.py`, danach alle rot. Gemeldet: Festlegung 1.9.187 Nr. 3 gilt für die Seite; die
Schnittstelle liefert mit `?monat=` auch einen künftigen Monat samt Freistellungen. Angepasste Erwartungen: keine.

Zusammen (1.9.197–1.9.201): 95 Festlegungen, 277 Gegenproben (und eine Nullprobe), 67 zuerst grün -> 56 neue Testfunktionen in fünf Dateien
(test_v604 … test_v608), danach jede Gegenprobe rot. Ohne Gegenprobe: die Werkzeug-Festlegung 1.9.166 Nr. 1 und 19 Teilaussagen, je mit Grund.

## Lohn L1a, Stufe 4 (ab 1.9.202)

Vorgabe Tobias (04.11.2026): die fünf Abweichungen von Wortlaut und Code aus Stufe 3 -- vier am Code, eine nur am Wortlaut -- je eine Version: 1 der Admin genehmigt einen Ausfalltag unter „Zeiten“ nur mit den Prüfungen des Dialogs (1.9.170 Nr. 3); 2 für die Kategorie Schlechtwetter gewinnt immer die Jahreszeit, eine Zuordnung je Art wird dort abgelehnt, eine gespeicherte übergangen und vom Prüfskript genannt (1.9.169 Nr. 3); 3 die Meldung des Schlechtwetter-Dialogs nennt auch, wer schon abwesend ist, je Person mit Grund (1.9.170 Nr. 5); 4 der Sammeleintrag prüft schon beim Anlegen, wer abwesend ist oder einen offenen Antrag hat, auch bei Büro – Finanzen (1.9.171 Nr. 5); 5 Wortlaut von 1.9.187 Nr. 3 (Seite und Schnittstelle). Dazu 6 (Werkzeug): Klicktests, die einen vom Server gefüllten Wert lesen, ohne auf die Antwort zu warten.

### Umsetzung 1.9.202: Genehmigen unter „Zeiten“ wie im Dialog (Punkt 1)

`app/absence_requests.py::_entscheiden()` prüft beim Genehmigen eines Antrags der Kategorie Schlechtwetter `app/schlechtwetter.py::grund_gegen()` (kein Arbeitstag, Feiertag, Tag des Arbeitszeitkalenders, keine Sollzeit, nicht gewerblich, inaktiv) und lehnt mit dem Grund ab (`ValueError`, 422 aus `POST /api/absence-requests/{id}/review` wie aus `POST /api/schlechtwetter/{id}/entscheiden`); der Antrag bleibt offen, keine Abwesenheit. Die eigene Prüfung in `app/schlechtwetter.py::entscheiden()` entfällt -- eine Stelle für jeden Weg (Dialog, „Zeiten“, Eintragen mit sofortiger Genehmigung). Ablehnen bleibt ohne Prüfung. Die Seite „Zeiten“ zeigt die Meldung wie jede abgelehnte Entscheidung in der Statuszeile.

### Festlegungen 1.9.202 (Bitte bestätigen)

1. Geprüft wird beim Genehmigen nur, was der Dialog ablehnt (`grund_gegen()`); die Rückfragen (gebuchte Zeit, betriebsfreier Tag) gelten beim Genehmigen nicht -- wie beim Bestätigen im Dialog (Festlegung 1.9.178 Nr. 3).
2. Die Meldung ist der Grund selbst, ohne Vorsatz („Tom Monteur: am 07.12.2026 keine Sollzeit“) -- dieselbe wie im Dialog.
3. Die Prüfung sitzt in `_entscheiden()`: jeder Weg, der einen Ausfalltag genehmigt, prüft dort; andere Kategorien nicht (Urlaub an einem Tag ohne Sollzeit genehmigt der Admin wie bisher, er zählt 0).

### Tests und Prüfung 1.9.202

Neu: `tests/test_v609_schlechtwetter_unter_zeiten.py` (7 Tests) -- Tom beantragt Mo 07.12.2026, danach keine Sollzeit am Montag bzw. kaufmännisch: unter „Zeiten“ 422 mit dem Grund des Dialogs, Antrag offen, keine Abwesenheit; im Dialog dieselbe Meldung; ablehnen geht; ohne Änderung genehmigt; Urlaub an einem Tag ohne Sollzeit wie bisher genehmigt. Gegenprobe: die Prüfung in `_entscheiden()` abgeschaltet -> 4 rot (beide Wege, beide Gründe). Angepasste Erwartungen: keine (`test_v605::test_admin_entscheidet_schlechtwetter_auch_unter_zeiten` bleibt -- ein gültiger Tag).

### Umsetzung 1.9.203: für Schlechtwetter gewinnt die Jahreszeit (Punkt 2)

`app/lohnarten.py`: `zuordnung()` nimmt für die Kategorie Schlechtwetter immer die Zeile der Jahreszeit (`schlechtwetter_schluessel()`), ohne Blick auf die Art -- auch nicht auf „Sonstiges“ oder eine selbst angelegte Art, die zu jeder Kategorie passt. `nur_jahreszeit(schluessel)`: eine Zeile „art:<Art>“ für eine Art, die nur zu Schlechtwetter passt (`art_kategorien()` = nur Schlechtwetter; heute nur „Schlechtwetter“). `speichern()` lehnt dort einen Wert ab (`NUR_JAHRESZEIT`, 422 aus `PUT /api/time-backoffice/lohnarten`, die Seite zeigt „Fehler: …“ unter der Tabelle); leeren geht. Eine schon gespeicherte Zeile bleibt stehen und wirkt nie, auch außerhalb der Kategorie Schlechtwetter nicht (Altbestand ohne Kategorie). `liste()` sagt in „Wirkt“ „nach der Jahreszeit (Schlechtwetter Winter bzw. Sommer)“ bzw. „gespeichert S / 8111 – wird übergangen, es gilt die Jahreszeit …“ (bis 1.9.202 stand dort „wie die Kategorie – “ ohne Kategorie). Der Satz über der Tabelle (`settings.html`): „Eine Art mit eigener Zuordnung geht ihrer Kategorie vor – außer bei Schlechtwetter: dort gilt immer die Jahreszeit.“ `scripts/pruefe_zeitregeln.py` nennt eine übergangene Zeile mit Wert als Befund (Rückgabe 1).

### Festlegungen 1.9.203 (Bitte bestätigen)

1. Übergangen wird bei Schlechtwetter jede Zuordnung je Art, nicht nur „art:schlechtwetter“ -- auch die einer Art, die zu jeder Kategorie passt („Sonstiges“, selbst angelegte); für die übrigen Kategorien gilt sie weiter.
2. Abgelehnt wird nur eine Zuordnung für eine Art, die ausschließlich zu Schlechtwetter passt; Kennzeichen, Lohnart oder Monatszeile allein genügen dafür.
3. Leeren der übergangenen Zeile geht und beendet den Befund; gelöscht wird sie nicht -- die Liste zeigt sie, solange es sie gibt.
4. Die übergangene Zeile wirkt nirgends, auch nicht bei einer Abwesenheit ohne Kategorie (Altbestand „unbekannt“) mit der Art „Schlechtwetter“.
5. Das Prüfskript zählt eine übergangene Zeile mit Wert zu „zu klären“ (Rückgabe 1) -- Ergänzung zu Festlegung 1.9.172 Nr. 1; eine leere nicht.

### Tests und Prüfung 1.9.203

Neu: `tests/test_v610_lohnart_schlechtwetter_jahreszeit.py` (12 Tests) -- welche Schlüssel nur zur Jahreszeit gehören; gespeicherte „art:schlechtwetter“ S / 8111 übergangen (Winter Monatszeile 8110, Sommer nicht exportiert, die Zeile bleibt); „Sonstiges“ X / 9999 gilt für Urlaub, nicht für Schlechtwetter; Altbestand ohne Kategorie; vier abgelehnte Eingaben (Wert, groß geschrieben, Monatszeile, nur Kennzeichen), nichts gespeichert; Schnittstelle 422 mit Meldung, leeren 200; Liste mit der Art „Schlechtwetter“; Prüfskript Befund und nach dem Leeren keiner; Satz auf der Seite. Klicktest `klicktest_lohnarten` 8 -> 13 Prüfungen (Satz, „wird übergangen“, Meldung auf der Seite, nichts gespeichert, geleert), ein Bild mehr. Gegenproben: Art vor der Jahreszeit wie bis 1.9.202 -> 3 rot; `speichern()` ohne Ablehnung -> 5 rot, Klicktest 11 von 13; Liste ohne Hinweis -> 2 rot, Klicktest 10 von 13; Altbestand wirkt außerhalb -> 1 rot; Prüfskript ohne Befund -> 1 rot; alter Satz -> 1 rot, Klicktest 12 von 13.

Angepasste Erwartungen (Regel 28): `klicktest_lohnarten` -- fünf Prüfungen dazu (8 -> 13), Aufbau: eine Zeile „art:schlechtwetter“ S / 8111 im Bestand; die übrigen Soll unverändert (auch „Bea: Felder gesperrt“, das jetzt die Zeile mitzählt).

### Umsetzung 1.9.204: die Schlechtwetter-Meldung nennt jede Person (Punkt 3)

`app/absence_requests.py::belegt(db, employee_id, start, ende)`: ist die Person im Zeitraum schon abwesend (genehmigte Abwesenheit, jede Kategorie) oder hat sie dort einen offenen Antrag (jede Kategorie)? Der Grund nennt die Tage, an denen beides zusammenfällt (`zeitraum_text()`: „am 07.12.2026“, „vom 28.12. bis 30.12.2026“), ohne Kategorie, Art oder den Zeitraum der vorhandenen Abwesenheit -- „am 07.12.2026 bereits abwesend“, „am 08.12.2026 bereits ein offener Antrag“. `app/schlechtwetter.py::eintragen()` prüft je Person zuerst `grund_gegen()`, sonst `belegt()`; jede betroffene Person steht mit Namen in `SchlechtwetterAbgelehnt` (422, die Liste in derselben Form wie bisher, je Eintrag `text`), nichts gespeichert. Das Anlegen und Genehmigen prüfen dahinter weiter selbst (zeitgleiche Einträge von anderer Seite) -- dann wie bisher die Meldung ohne Namen.

### Festlegungen 1.9.204 (Bitte bestätigen)

1. „Schon abwesend“ und „offener Antrag“ gehören zu den abgelehnten Tagen (422) und kommen vor der Rückfrage zu gebuchter Zeit und zum betriebsfreien Tag (409).
2. Die Meldung nennt nur die Tage der Überschneidung, nie Kategorie, Art oder den Zeitraum der vorhandenen Abwesenheit -- sie sehen auch Kolonnenführer und Vorarbeiter (Krankheit nur für wen sie bestimmt ist, seit 1.5.4).
3. Je Person ein Grund, in dieser Reihenfolge: die Gründe des Tags (`grund_gegen()`), schon abwesend, offener Antrag; die Personen in der Reihenfolge der Auswahl.
4. Auch wer für sich beantragt und schon einen offenen Antrag hat, bekommt seinen Namen und den Tag (bis 1.9.203 „Für diesen Zeitraum existiert bereits ein offener Abwesenheitsantrag.“).

### Tests und Prüfung 1.9.204

Neu: `tests/test_v611_schlechtwetter_meldung_je_person.py` (8 Tests) -- `zeitraum_text()`; Mia und Tom schon eingetragen, Kai frei: beide mit Namen, für Kai nichts; Krankheit 01.–11.12.: der Kolonnenführer sieht nur den Tag; offener Antrag; für sich mit offenem Antrag; zusammen mit „keine Sollzeit“ und „nicht gewerblich“ in der Reihenfolge der Auswahl; zweiter Schritt bleibt (belegt() ausgeschaltet: 422, nichts gespeichert); Tage der Überschneidung, abgelehnte Anträge zählen nicht. Klicktest `klicktest_schlechtwetter` 22 -> 24 Prüfungen (Kai: Kolonne am Montag noch einmal -- alle drei genannt, ein Bild; am Dienstag nur Tom mit offenem Antrag). Gegenproben: ohne `belegt()` (wie bis 1.9.203) -> 5 rot, Klicktest 22 von 24; ohne Namen -> 5 rot; offene Anträge nicht gesehen -> 3 rot; der ganze Zeitraum der Abwesenheit -> 2 rot; mit Art -> 4 rot. Im Lauf vor dem Commit war `test_v591::test_kein_schlechtwetter_an_heiligabend` rot: er erwartet die Liste der Meldung in der bisherigen Form, eine zuerst mitgegebene `employee_id` je Eintrag (nicht verlangt) kam wieder heraus -- die Antwort behält ihre Form.

Angepasste Erwartungen (Regel 28): `klicktest_schlechtwetter` zwei Prüfungen dazu (22 -> 24), sonst unverändert. `test_v588::test_schon_abwesend` und `test_v605::test_alles_oder_nichts_wenn_eine_spaetere_person_schon_abwesend_ist` prüfen „bereits“ in der Meldung -- unverändert grün, nicht angepasst.

### Umsetzung 1.9.205: der Sammeleintrag prüft schon beim Anlegen (Punkt 4)

`app/absence_requests.py::sammel_eintragen()` fragt je Person zuerst `belegt()` (1.9.204) für den ganzen Zeitraum: wer schon abwesend ist oder einen offenen Antrag hat, steht mit Namen und den Tagen der Überschneidung in `SammelAbgelehnt` (422), für niemanden wird etwas angelegt -- beim Admin wie bei Büro – Finanzen. Danach wie bisher `_antrag_anlegen()` und beim Admin `_entscheiden()`; deren Prüfungen bleiben als zweiter Schritt (zeitgleiche Einträge von anderer Seite), ebenso die Prüfung, wenn der Admin einen offenen Antrag später entscheidet. Die Rückfrage zu Silvester (1.9.176) wird jetzt gesammelt: sie kommt (409) erst, wenn für keine Person etwas dagegen spricht -- sonst zuerst die Liste. Der Einzelantrag bleibt, wie er seit 1.9.101 ist.

### Festlegungen 1.9.205 (Bitte bestätigen)

1. Geprüft wird der ganze Zeitraum des Sammeleintrags; die Meldung nennt je Person die Tage der Überschneidung, ohne Kategorie und Art (wie 1.9.204 Nr. 2) -- der Wortlaut für einen offenen Antrag ist jetzt „am 29.12.2026 bereits ein offener Antrag“ statt „Für diesen Zeitraum existiert bereits ein offener Abwesenheitsantrag.“
2. Spricht gegen eine Person etwas und liegt Silvester im Zeitraum, kommt zuerst die Liste, die Rückfrage danach (bis 1.9.204 umgekehrt, wenn die Person mit der Rückfrage vor der abgelehnten stand).
3. Neu gefasst mit 1.9.208 (Vorgabe Tobias, L1a Stufe 5, Punkt 1): Auch der Einzelantrag prüft beim Anlegen, ob die Person schon abwesend ist oder einen offenen Antrag hat (`belegt()`), mit Namen und Tagen wie der Sammeleintrag; ebenso „Abwesenheit eintragen“ auf der Plantafel. Die Prüfung beim Entscheiden bleibt. Bis 1.9.207 hieß es: „Der Einzelantrag (`POST /api/absence-requests`) prüft weiter nur offene Anträge beim Anlegen; „schon abwesend“ fällt dort wie seit 1.9.101 bei der Entscheidung auf -- die Vorgabe betrifft den Sammeleintrag.“ -- „seit 1.9.101“ war ungenau, die Lücke ist älter (Befund 1.9.208).

### Tests und Prüfung 1.9.205

Neu: `tests/test_v612_sammel_prueft_beim_anlegen.py` (8 Tests) -- Büro – Finanzen und Admin: Mia am 29.12. schon abwesend, Tom mit offenem Antrag (Krankheit), Kai frei -> 422, beide genannt, nichts angelegt; die Meldung ohne Kategorie; Tage der Überschneidung (Kai 21.12.–02.01.); Silvester erst nach der Liste (422, ohne Mia 409, mit Antwort 200); das Entscheiden prüft weiter (zeitgleiche Abwesenheit -> 422); zweiter Schritt beim Admin (belegt() ausgeschaltet -> 422 mit Namen); Einzelantrag bleibt. Klicktest `klicktest_sammeleintrag` 20 -> 21 Prüfungen (Fin: Kai und Tom 28.–30.12. -> beide genannt, keine Anträge, ein Bild). Gegenproben: ohne `belegt()` (wie bis 1.9.204) -> 5 rot, Klicktest 19 von 21; die Rückfrage vor der Liste -> 1 rot; beim Entscheiden nicht mehr geprüft -> 4 rot (davon 3 neu, dazu `test_v566::test_ueberlappung_beim_admin_422_und_kein_antrag_bleibt`).

Angepasste Erwartungen (Regel 28): `test_v589::test_alles_oder_nichts` altes Soll „Tom Monteur: Für diesen Zeitraum existiert bereits ein offener Abwesenheitsantrag.“, neues Soll „Tom Monteur: am 29.12.2026 bereits ein offener Antrag“. `klicktest_sammeleintrag` „Ada: Kai schon im Urlaub -- nichts eingetragen“ altes Soll „Nicht eingetragen: Kai Kolonne: Für diesen Mitarbeiter besteht im beantragten Zeitraum bereits eine genehmigte Abwesenheit.“, neues Soll „Nicht eingetragen: Kai Kolonne: am 29.12.2026 bereits abwesend.“; dazu eine Prüfung (20 -> 21).

### Umsetzung 1.9.206: Wortlaut von 1.9.187 Nr. 3 (Punkt 5, nur Doku)

Festlegung 1.9.187 Nr. 3 oben neu gefasst: die Seite öffnet keine künftigen Monate, die Schnittstelle liefert mit `?monat=` auch einen künftigen Monat samt Freistellungen. Am Code nichts. Beide Teile sind geprüft: die Seite in `klicktest_meine_zeiten` („zurück im Oktober, › gesperrt“; Gegenprobe 187_3b in 1.9.201: 58 von 59), die Schnittstelle in `tests/test_v599_meine_zeiten_freistellungen.py` (am festen Tag 10.11.2026 mit `monat=2026-12`). Gegenprobe zur neuen Fassung: `GET …/meine-zeiten` nimmt höchstens den laufenden Monat (`app/routers/field_view.py`) -> 3 rot (`test_v599::test_dezember_mit_heiligabend_und_silvester`, `::test_teilzeit_nur_an_tagen_mit_sollzeit_und_voll`, `::test_silvester_als_ganzer_urlaubstag_fehlt`). Keine neue Festlegung, keine angepasste Erwartung.

### Umsetzung 1.9.207: Klicktests lesen erst nach der Antwort (Punkt 6, Werkzeug)

Steht im Archiv „Testablauf und Klicktests“, Abschnitt „Klicktests lesen erst nach der Antwort (1.9.207)“: alle Klicktests mit verzögerten Antworten gemessen, 6 Stellen in 6 Klicktests umgestellt (5 lesen nach `oeffnen()`, 1 navigiert nach dem Neuladen), drei Festlegungen zum Werkzeug. Am Programm nichts geändert.

## Lohn L1a, Stufe 5 (ab 1.9.208)

Vorgabe Tobias (04.11.2026), je Punkt eine Version: 1 Befund, warum der Einzelantrag beim Anlegen nur offene Anträge prüft -- ohne tragenden Grund an den Sammeleintrag angleichen, die Prüfung beim Entscheiden bleibt, Festlegung 1.9.205 Nr. 3 neu fassen; 2 `klicktest_heute` mit stehender Uhr, „Tag zusammen 3:15 h“ auf genau einem Wert; 3 (Werkzeug) jede neue Festlegung bekommt in derselben Runde ihre Gegenprobe, die Lücke 1.9.202 Nr. 2 und 3 schließen; 4 Plantafel: Kapazität aus der Sollzeit des Lohns statt aus Wochenstunden und Arbeitstagen der Planung.

### Befund und Umsetzung 1.9.208: der Einzelantrag prüft wie der Sammeleintrag (Punkt 1)

**Befund.** `_antrag_anlegen()` prüfte beim Anlegen nur offene Anträge („Für diesen Zeitraum existiert bereits ein offener Abwesenheitsantrag.“), eine genehmigte Abwesenheit im Zeitraum erst `_entscheiden()`. Das stammt nicht aus 1.9.101 -- 1.9.101 legte nur fest, wer für wen beantragt und entscheidet --, sondern steht so schon im ersten Commit des Repos (13.09.2026, Version 1.3.32, `create_request()`); Changelog, Archiv und Code nennen keinen Grund. Der einzige denkbare: eine Krankheit während eines genehmigten Urlaubs als offener Antrag melden. Er trägt nicht -- genehmigen ließ sich ein solcher Antrag auch bisher erst, nachdem der Admin den Urlaub gelöscht hatte (eine genehmigte Abwesenheit lässt sich nicht ändern, 1.9.146), und nichts auf den Seiten führte dorthin; bis dahin stand ein Antrag, der nicht genehmigt werden konnte und weitere Anträge im Zeitraum sperrte. Also angeglichen.

**Umsetzung.** `_antrag_anlegen()` fragt statt der offenen Anträge `belegt()` (1.9.204) und wirft `Belegt` (Name und Grund getrennt, Unterklasse von `ValueError`): der Einzelantrag meldet „Mia Monteurin: am 29.12.2026 bereits abwesend.“ bzw. „… bereits ein offener Antrag.“ (422), nur mit den Tagen der Überschneidung, ohne Kategorie. Das gilt für jeden Antrag: „Zeiten“ und „Meine Zeiten“ (`POST /api/absence-requests`), „Abwesenheit eintragen“ auf der Plantafel (`POST /api/planning/absences`, ein Weg seit 1.9.146), Sammeleintrag und Schlechtwetter. Der Sammeleintrag braucht seine eigene Prüfung vorweg (1.9.205) nicht mehr und bildet seine Zeile je Person aus `Belegt`; der Schlechtwetter-Dialog behält seine (er sammelt erst alle Gründe des Tags). `_entscheiden()` prüft weiter selbst.

### Festlegungen 1.9.208 (Bitte bestätigen)

1. Die Prüfung „schon abwesend oder offener Antrag“ sitzt in `_antrag_anlegen()` -- jeder Weg, der einen Antrag anlegt, prüft dort; der Sammeleintrag hat keine eigene Prüfung vorweg mehr.
2. Die Meldung des Einzelantrags und der Plantafel nennt Person und Tage mit Punkt („Mia Monteurin: am 29.12.2026 bereits abwesend.“), ohne Kategorie; sie ersetzt „Für diesen Zeitraum existiert bereits ein offener Abwesenheitsantrag.“ und auf der Plantafel beim Admin „Für diesen Mitarbeiter besteht im beantragten Zeitraum bereits eine genehmigte Abwesenheit.“
3. = Festlegung 1.9.205 Nr. 3, neu gefasst (oben): der Einzelantrag prüft wie der Sammeleintrag, das Entscheiden zusätzlich.
4. Eine Krankheit während eines genehmigten Urlaubs meldet die Monteurin nicht mehr als Antrag: der Admin löscht den Urlaub (dessen Antrag ist danach zurückgezogen und zählt nicht) und trägt neu ein; danach geht auch der Antrag der Monteurin.

### Tests und Prüfung 1.9.208

Neu: `tests/test_v613_einzelantrag_belegt.py` (9 Tests) -- Einzelantrag schon abwesend (Monteurin für sich, Büro – Finanzen, Admin): 422 mit Namen und Tag, nichts angelegt; offener Antrag mit neuem Wortlaut; Tage der Überschneidung ohne Kategorie; Plantafel für Büro – Finanzen und Admin; Krankheit im Urlaub über den Admin; abgelehnte Anträge zählen nicht. `klicktest_sammeleintrag` 21 -> 22 Prüfungen (Fin: Einzelantrag für Kai, ein Bild). Gegenproben je Festlegung: Nr. 1 ohne Prüfung beim Anlegen -> 16 rot, Klicktests 19 von 22 und 48 von 49; Nr. 2 Meldung ohne Namen -> 9 rot; Nr. 3 nur offene Anträge wie bis 1.9.207 -> 13 rot; Nr. 4 zurückgezogene Anträge zählen -> 1 rot.

Angepasste Erwartungen (Regel 28) zu 1.9.208: `test_v612::test_einzelantrag_bleibt` (200, offener Antrag) -> `test_einzelantrag_wie_der_sammeleintrag` (422 „Mia Monteurin: am 29.12.2026 bereits abwesend.“); `test_v566::test_ueberlappung_beim_admin_422_und_kein_antrag_bleibt` altes Soll „bereits eine genehmigte Abwesenheit“ in der Meldung, neues Soll genau „Mia Test: am 02.11.2026 bereits abwesend.“; `klicktest_abwesenheit_ein_weg` „Überlappend: Meldung“ ebenso (neu „Mia Test: vom 19.10. bis 20.10.2026 bereits abwesend.“); `klicktest_sammeleintrag` eine Prüfung mehr.

### Umsetzung 1.9.209: `klicktest_heute` mit stehender Uhr (Punkt 2, Werkzeug)

Steht im Archiv „Testablauf und Klicktests“, Abschnitt „Stehende Uhr, vom Klicktest weitergestellt (1.9.209)“: eine ganz stehende Uhr reicht nicht (Wechsel und Feierabend in derselben Sekunde lehnt der Server ab); `tab.uhr_stellen()` stellt sie in Instanz und Browser genau um 10 s weiter, „Tag zusammen 3:15 h“ und „gebucht 0,00 h“ sind genau ein Wert. Am Programm nichts geändert.

### Umsetzung 1.9.210: Gegenprobe zu jeder neuen Festlegung (Punkt 3, Werkzeug)

Die stehende Regel steht im Archiv „Testablauf und Klicktests“, Abschnitt „Gegenprobe zu jeder neuen Festlegung in derselben Runde“, und kurz in Regel 24. Für Stufe 4 nachgeholt: genannt waren 1.9.202 Nr. 2 und Nr. 3 (beide sofort rot -- die Tests gab es, die Gegenprobe nicht); die Durchsicht aller Festlegungen von Stufe 4 fand dazu 1.9.202 Nr. 1b, 1.9.203 Nr. 3a/3b und 1.9.204 Nr. 3c (sofort rot) und drei Befunde: 1.9.204 Nr. 1b (abgelehnt vor der Rückfrage), Nr. 3a (erst die Gründe des Tags), Nr. 3b (abwesend vor offenem Antrag) -- neue Tests in `tests/test_v615_gegenproben_stufe4.py`, danach rot. Die Tabelle aller Gegenproben von Stufe 4 und 5: `docs/archiv/gegenproben-lohn-l1a.md`, „Stufe 4 und 5“. Am Programm nichts geändert.

### Umsetzung 1.9.211: die Plantafel rechnet mit der Sollzeit (Punkt 4)

Bis 1.9.210 hatte jede Person an jedem Arbeitstag der Planung (Einstellungen „Reguläre Arbeitstage“) dieselbe Kapazität: Wochenstunden durch die Zahl dieser Tage, höchstens „Arbeitsstunden je Tag“ (`_employee_daily_gross_hours()`), abzüglich der Anfahrt -- Mia im Winter 8,00 h statt 7,50 h, Tom (Teilzeit Di–Do 3,00 h, aber 40 Wochenstunden) jeden Tag 8,00 h, Ben (Mo–Di) auch Mittwoch bis Freitag. Jetzt kommt die Kapazität je Person und Tag aus der Sollzeit des Lohns: `app/planning.py::_soll_je_tag()` über `app/sollzeit.py::soll_fuer_personen()` (neu: dieselbe Rechnung wie `soll_zeitraum()` für viele Personen, je eine Abfrage für Lohnstammdaten, eigene Werte, Gruppen und Zuordnung der Modelle, das Modell je Zuordnung und Kalenderwoche einmal über `app/work_time_models.py::modell_fuer_zuordnung()`, aus `employee_model()` herausgelöst; `soll_zeitraum()` geht seitdem darüber). `_day_capacity()`: an einem Feiertag oder betriebsfreien Tag niemand; sonst je Person ohne Sollzeit an dem Tag weder verfügbar noch abwesend, mit Sollzeit abwesend oder verfügbar mit `_netto()` = Sollzeit − Anfahrt, nie unter 0. Das wirkt auf die Kapazität und Auslastung der Tafel (Kolonnen und Mitarbeiter), die Verteilung der Stunden eines Einsatzes und damit den Hinweis „Kapazität reicht um … nicht aus“ (Speichern und Tafel) und den Planungsvorschlag: volle Tageskapazität ist die der Kolonne am ersten Tag ab dem Start, an dem sie ohne Abwesenheiten und Feiertage Sollzeit hat (`_SollAbschnitte` lädt die Sollzeit in Abschnitten von 62 Tagen nach), die Formel nennt diesen Tag und die Zahl der Personen („24,00 h / 15,50 h (Sollzeit von 2 MA am 21.12.2026 − je 0,00 h Anfahrt) = 1,55 Teamtage“), die Seite „… MA · Sollzeit am 21.12.2026 − je 0,00 h Anfahrt = 15,50 Team-h/Tag“. Die Tafel rechnet die Sollzeit einmal für Tafel und Konflikte (über ihren Zeitraum samt dem der Einsätze, die über den Rand reichen) -- sonst hingen die Abfragen an den Einsätzen im Bild (`test_v564`). Die Einstellungsseite sagt bei „Tägliche geplante Arbeitszeit“ und „Reguläre Arbeitstage“, wofür sie noch gelten.

**Wo Wochenstunden, Arbeitstage der Planung und „Arbeitsstunden je Tag“ noch gebraucht werden** (nichts gelöscht):
- Wochenstunden des Mitarbeiters (`Employee.weekly_hours`): Lohnkosten und Jahresstunden (`app/employees.py`), Verrechnungssatz (`app/labor_rate.py`), Mitarbeiterformular, Änderungsprotokoll. In der Plantafel nirgends mehr. Teilzeit für die Planung heißt jetzt eigene Sollzeit.
- Arbeitstage der Planung (`PlanningSettings.monday` … `sunday`, `_working_weekdays()`): Hinweis „Feiertag“ an einem Einsatz nur an einem Arbeitstag (`_conflicts()`, seit 1.9.150), Termine an Geräten nur an Arbeitstagen (`termine_der_geraete()`, `_is_workday()`), Feiertage im Produktivstunden-Rechner (`count_workday_holidays()`), Prüfung beim Speichern der Einstellungen (mindestens ein Tag).
- „Arbeitsstunden je Tag“ (`PlanningSettings.daily_work_hours`): nur noch Obergrenze der Anfahrt -- beim Speichern der Einstellungen, eines Einsatzes mit eigener Anfahrt und im Planungsvorschlag (dort weiter in der Antwort, die Seite zeigt es nicht mehr).

### Festlegungen 1.9.211 (Bitte bestätigen)

1. Die Kapazität einer Person an einem Tag ist ihre Sollzeit (Tarif oder eigene Werte, Eintritt und Austritt, Arbeitszeitkalender) abzüglich der Anfahrt, nie unter 0; ohne Sollzeit 0, auch ohne Anfahrt.
2. An einem Tag ohne Sollzeit ist die Person in der Kolonne weder verfügbar noch abwesend: keine „abw.“-Markierung, kein Anteil an der Verteilung -- auch wenn an dem Tag eine Abwesenheit eingetragen ist; in ihrer eigenen Zeile (Ansicht „Mitarbeiter“) steht eine eingetragene Abwesenheit weiter da, mit Kapazität 0.
3. An einem gesetzlichen Feiertag und einem betriebsfreien Tag hat niemand Kapazität, auch wer Sollzeit hätte (wie bisher).
4. Die Arbeitstage der Planung und „Arbeitsstunden je Tag“ zählen für die Kapazität nicht mehr (ein Samstag als Arbeitstag gibt ohne Sollzeit keine Kapazität, „Arbeitsstunden je Tag“ begrenzt nicht); sie bleiben für die oben genannten Zwecke.
5. Planungsvorschlag: die volle Tageskapazität ist die des ersten Tags ab dem Start, an dem die Kolonne ohne Abwesenheiten und Feiertage Sollzeit hat; die Formel nennt Tag und Zahl der Personen.
6. Eine Rechnung der Sollzeit für eine wie für viele Personen; die Zahl der Abfragen hängt nicht an der Zahl der Personen und nicht an den Einsätzen im Bild.
7. = Festlegung 1.9.188 Nr. 3, neu gefasst (oben).

### Tests und Prüfung 1.9.211

Neu: `tests/test_v616_plantafel_sollzeit.py` (14 Tests) -- Kapazität je Person und Kolonne in der Woche ab 21.12.2026 (Mia 7,50, Tom Di–Do 3,00, Ben Mo–Di 8,00; Kolonne 15,50 / 18,50 / 10,50 / 0, verfügbar 2 / 3 / 2 / 0; Samstag und Feiertag 0); ohne Sollzeit nicht abwesend; Anfahrt nie unter 0; Arbeitstage der Planung zählen nicht; Arbeitsstunden je Tag begrenzen nicht; Feiertag und betriebsfreier Tag 0 (Person und Kolonne); Austritt; „Kapazität reicht um 5,00 h nicht aus“ und Auslastung mit 15,00 h; Vorschlag ab Samstag mit voller Kapazität des Montags und Formel; Sollzeit für viele wie für eine; Abfragen unabhängig von der Zahl der Personen; Sätze auf beiden Seiten; Tarif Sommer 8,00 und Winter 7,50. `klicktest_plantafel_kalender` 14 -> 16 Prüfungen (Kapazität der Kolonne Nord und je Person in der Woche ab 21.12.). Gegenproben je Festlegung (16, alle rot, die Kapazität aus Wochenstunden auch im Klicktest: 15 von 16): Tabelle in `docs/archiv/gegenproben-lohn-l1a.md`, „Stufe 4 und 5“. Befund dabei: „Arbeitstage zählen nicht“ blieb für die Kolonne zuerst grün -- die Kolonne rechnet auf eigenem Weg (`_day_capacity()`), der Test prüfte nur die Person; nachgezogen (auch „Arbeitsstunden je Tag“ und die Zeile der Person ohne Sollzeit), danach rot.

Bilder derselben Woche vorher und nachher (Kolonne Nord und Mitarbeiter, Woche ab 21.12.2026, `klicktest_plantafel_kalender`): vorher Nord Mo–Mi je 0/24 h und Do 0/8 h, je Person 8 h an jedem Werktag; nachher Nord 0/15,5 · 0/18,5 · 0/10,5 · 0/0 h, Ben 8 · 8 · 0 · 0, Mia 7,5 · 7,5 · 7,5 · 0, Tom 0 · 3 · 3 · 0.

**Fund unterwegs (Muster von 1.9.207):** Das erste Vorher-Bild der Kolonnen zeigte die Woche ab 14.12. und „Lädt …“. Nach `movePeriod(7)` wartete `klicktest_plantafel_kalender` auf `board.slots.length===1` -- das galt schon für die alte Tafel (zwei Wochen ab 14.12. mit demselben Einsatz); Prüfungen und Bild liefen, bevor die neue Woche da war. Die Prüfungen blieben grün, weil die alte Tafel an diesen Tagen dieselben Werte zeigte -- deshalb fand die Messung mit verzögerten Antworten (1.9.207) die Stelle nicht. Jetzt `warte_auf_neu_geladene_liste("movePeriod(7)", "#planner")` und `board.start_date` in der Bedingung; dieselbe schwache Bedingung an fünf Stellen in `klicktest_plantafel_konflikte` ebenso umgestellt (Archiv „Testablauf“, Nachtrag zu 1.9.207).

Angepasste Erwartungen (Regel 28) -- 3 in pytest, 0 in Klicktests: `test_v568::test_kapazitaet_und_formel_deutsch` altes Soll „24,00 h / (4 MA × (8,00 h − 0,00 h)) = 0,75 Teamtage“, neues Soll „24,00 h / 32,00 h (Sollzeit von 4 MA am 02.11.2026 − je 0,00 h Anfahrt) = 0,75 Teamtage“; `test_v600::test_tafel_zeigt_die_betroffenen_abwesend` altes Soll Ben am 24.12. mit derselben Kapazität wie am 23.12. („wie bisher“), verfügbar am 24.12./23.12. 1 und 3, neues Soll Ben am 23.12. und 24.12. 0 h (am 22.12. 8 h), verfügbar 0 und 2; `test_v600::test_vorschlag_rechnet_den_tag_ohne_die_betroffenen` nur Aufbau (Uwe, kaufmännisch und auf der Tafel, statt Ben als der eine Verfügbare an Heiligabend), Soll gleich. Klicktests: `klicktest_plantafel_kalender` zwei Prüfungen dazu und Aufbau (warten auf die neue Woche), `klicktest_plantafel_konflikte` nur Aufbau (fünf Stellen) -- kein Soll eines Klicktests geändert.

## Lohn L1a, Stufe 6 (ab 1.9.212)

Vorgabe Tobias (05.11.2026): Antworten des Lohnbüros einarbeiten, je Punkt eine Version, jede neue Festlegung mit eigener Gegenprobe: 1 Personalnummer genau 5 Ziffern, führende Nullen erlaubt und erwartet, Festlegung 1.9.168 Nr. 1 neu, Migration füllt auf (auch die gemerkten), Nummernkreise als Hinweis beim Speichern; 2 Skript, das vergebene Personalnummern aus einer Datei auf dem Server in die Sperrliste einliest (keine echten Nummern in Code, Tests, Beispielen; mehrfach ausführbar, meldet neu und schon gemerkt); 3 Zuordnung neue Werte (Heiligabend FR/1080, Silvester UU ohne Lohnart, Schlechtwetter Winter WA/8195 je Tag ohne Monatszeile, Berufsschule FE ohne Lohnart, Schlechtwetter Sommer leer), Festlegung 1.9.169 Nr. 3 neu, Notiz für L1b: Mehrarbeit von Azubis AA/1900 je Tag; 4 Festlegung 1.9.175 Nr. 5 neu: Kennzeichen leer -> nicht exportiert, Kennzeichen ohne Lohnart -> exportiert ohne Lohnart, beides -> mit Lohnart, „Wirkt“ sagt den Fall; 5 Schlechtwetter bekommt Stunden, abgeleitet: Sollzeit des Tags minus gebuchte Arbeitszeit, nie unter 0, sichtbar unter „Monat & Lohn“ und in den Listen; 6 Befund, nichts ändern: wo wirkt die Monatszeile noch.

### Umsetzung 1.9.212: Personalnummer genau 5 Ziffern (Punkt 1)

`app/time_backoffice.py`: `PERSONALNUMMER_FORMAT` `^[0-9]{5}$` (bis 1.9.211 `^[1-9][0-9]{0,4}$`), Meldung „Die DATEV-Personalnummer hat genau 5 Ziffern, führende Nullen gehören dazu (z. B. 00101).“, bei Gleichsetzung „Die ERP-Mitarbeiternummer „…“ taugt nicht als DATEV-Personalnummer: genau 5 Ziffern, führende Nullen gehören dazu.“ `NUMMERNKREISE` und `nummernkreis()`: der Hinweis „Die Personalnummer 00150 liegt im Kreis Minijobber (00100–00199).“, in der Antwort aufs Speichern der Lohnstammdaten (`nummernkreis`, `EmployeePayrollSettingsOut`); die Seite hängt ihn an „Gespeichert.“ (Text vom Server). Der Hilfetext unter „DATEV-Personalnummern, Eintritt und Sollzeit“ nennt Format und Kreise. Migration `5d2e8a71c4f3` (siehe Festlegungen). `scripts/pruefe_zeitregeln.py`: Befund „hat nicht genau 5 Ziffern“, neue Zeile „Personalnummern je Kreis: …“; `scripts/pruefabfrage_personalnummern.sql` mit dem neuen Format.

### Festlegungen 1.9.212 (Bitte bestätigen)

1. = Festlegung 1.9.168 Nr. 1, neu gefasst (oben): genau 5 Ziffern, führende Nullen gehören dazu; beim Speichern wird nichts aufgefüllt („101“ -> Meldung).
2. Die Kreise sind nur ein Hinweis in der Antwort aufs Speichern der Lohnstammdaten („Gespeichert. Die Personalnummer … liegt im Kreis …“) -- keine Sperre und keine Rückfrage. Er nennt nur den Kreis der Nummer: das ERP kennt weder Minijob noch Azubi als Merkmal einer Person (die Funktion ist frei benennbar). 00200 bis 99999 heißt „Azubis“, auch 91001 aus den alten Mustern.
3. Bei „DATEV-Nr. = ERP-Nr.“ verlangt das Speichern der Lohnstammdaten die 5 Ziffern von der ERP-Mitarbeiternummer (mit Export, wie Festlegung 1.9.168 Nr. 2), der Hinweis nennt dann deren Kreis. Das Mitarbeiterformular prüft das Format weiter nicht und zeigt keinen Hinweis.
4. Die Migration füllt die Lohnstammdaten und die gemerkten Nummern auf, nicht die ERP-Mitarbeiternummer -- auch nicht bei Gleichsetzung: sie gehört den Stammdaten, das Büro ändert sie im Mitarbeiterformular; bis dahin nennt das Prüfskript sie, und das Speichern der Lohnstammdaten mit Export lehnt ab. Eine gemerkte frühere ERP-Nummer („12“ -> „00012“) passt danach zur neuen ERP-Nummer „00012“ derselben Person.
5. Aufgefüllt wird nur eine Nummer aus 1 bis 4 Ziffern; eine mit Buchstaben, Leerzeichen oder mehr Ziffern bleibt. Trügen danach zwei Zeilen derselben Tabelle dieselbe Nummer, bricht die Migration ab, ohne etwas zu ändern (wie Festlegung 1.9.168 Nr. 5).
6. `scripts/pruefe_zeitregeln.py` zählt die gültigen Nummern aktiver Personen je Kreis, ohne Befund; ein Befund ist nur, was nicht genau 5 Ziffern hat.
7. `downgrade()` nimmt die führenden Nullen jeder 5-stelligen Nummer wieder weg, auch einer nach dem Einspielen neu eingetragenen („00001“ -> „1“; die alte Fassung kennt keine führende Null); „00000“ bleibt.

### Tests und Prüfung 1.9.212

Neu: `tests/test_v617_personalnummer_fuenf_stellen.py` (23 Tests) -- sieben Formate abgelehnt ohne Zeile (auch „101“ und „9005“), die Kreise an ihren Grenzen (00000, 00099, 00100, 00199, 00200, 00204, 91001), keine Sperre (Monteurin mit 00150, 00250, 00010), ohne Nummer kein Hinweis, Gleichsetzung („101“ abgelehnt, „00101“ mit Hinweis), Prüfskript (Befund und Kreise), Migration auf einem Bestand unter SQLite und PostgreSQL (aufgefüllt, ERP-Nummer bleibt, hoch, runter, hoch), Abbruch bei einer Kollision unter SQLite und PostgreSQL (nichts geändert), die Umrechnung für sich. `klicktest_sollzeit`: eine Prüfung mehr („Gespeichert. Die Personalnummer 91001 liegt im Kreis Azubis (ab 00200).“). Gegenproben je Festlegung: Archiv „Gegenproben Lohn L1a“, Abschnitt „Stufe 6“.

Angepasste Erwartungen (Regel 28) zu 1.9.212:
- `test_v586::test_personalnummer_nur_ziffern`: dazu „1“ und „9005“ (abgelehnt); Meldung altes Soll „1 bis 5 Ziffern ohne führende Null“, neues Soll „genau 5 Ziffern, führende Nullen gehören dazu“.
- `test_v586::test_gueltige_personalnummer`: altes Soll „1“, „9005“, „91001“, „ 91001 “ gültig, neues Soll „00001“, „09005“, „91001“, „ 91001 “.
- `test_v586::test_pruefabfrage_nur_lesen`: altes Soll Format `^[1-9][0-9]{0,4}$`, neues Soll `^[0-9]{5}$`.
- `test_v590::test_personalnummern_fehlend_falsch_doppelt` und `::test_gleichsetzung_prueft_die_erp_nummer`: Befund altes Soll „ist nicht 1 bis 5 Ziffern ohne führende Null.“, neues Soll „hat nicht genau 5 Ziffern.“; Aufbau „9005“ -> „09005“.
- `test_v590::test_eintritt_austritt_eigene_sollzeit_und_zuordnung_der_modelle`: Aufbau Personalnummern „1“, „2“, „3“ -> „00001“, „00002“, „00003“ (Soll gleich).
- `klicktest_sollzeit` „Fin: Personalnummer „9100A“ abgelehnt“: altes Soll „Fehler: Die DATEV-Personalnummer besteht aus 1 bis 5 Ziffern ohne führende Null (z. B. 91001).“, neues Soll „Fehler: Die DATEV-Personalnummer hat genau 5 Ziffern, führende Nullen gehören dazu (z. B. 00101).“
- `klicktest_zeiten` „Fin: Lohnart Werkstatt und Oles Personalnummer gespeichert“: nur Aufbau, Oles Nummer „1003“ -> „01003“ (Soll 200 bleibt).
- `test_v387::test_lohnstammdaten_entstehen_erst_beim_speichern`: nur Aufbau, gespeicherte Nummer „77“ -> „00077“ (gefunden im ersten Lauf der Kette: 422 statt 200).
- `klicktest_personalnummer_freigeben` „Ada: Tom bekommt 91008“: altes Soll [„Gespeichert.“, 91008], neues Soll [„Gespeichert. Die Personalnummer 91008 liegt im Kreis Azubis (ab 00200).“, 91008] (gefunden im zweiten Lauf der Kette).

### Umsetzung 1.9.213: vergebene Personalnummern einlesen (Punkt 2)

`scripts/personalnummern_einlesen.py` (Muster `scripts/erstes_konto.py`: `DATABASE_URL` Pflicht, `main(argv, sitzung=, umgebung=, ausgabe=)`): `lesen()` zerlegt die Datei (UTF-8, Byte-Order-Mark erlaubt), `einlesen()` merkt je Nummer, die noch nicht gemerkt ist, einen Eintrag -- mit der Person, die sie heute trägt (`app/time_backoffice.py::personalnummer_halter()`, dieselbe Regel wie beim Freigeben), sonst ohne Person; ein Commit am Ende, bei `--probe` keiner. Migration `8b4c2f9e1d07`: `personalnummern_vergeben.employee_id` leer erlaubt (`downgrade()` löscht die Nummern ohne Person und verlangt die Person wieder). `app/time_backoffice.py`: `personalnummer_gesperrt()` nennt bei einer Nummer ohne Person „eingelesene Liste vergebener Nummern“ (`EINGELESEN`), `fruehere_personalnummern()` nur Nummern mit Person, `personalnummer_freigeben()` schreibt „gesperrt, eingelesen ohne Person“. `scripts/pruefe_zeitregeln.py`: Zeile „davon eingelesen ohne Person“ (nur wenn es welche gibt), Befund, wenn eine aktive Person eine solche Nummer trägt.

Aufruf auf dem Server: `set -a; source .env; set +a` und `.venv/bin/python scripts/personalnummern_einlesen.py /home/tobias/erp-data/<datei> --probe`, danach ohne `--probe`. Die Datei gehört nach `erp-data` (außerhalb von Git, von `backup.sh` gesichert) oder wird nach dem Einlesen gelöscht -- beides entscheidet der Betreiber.

### Festlegungen 1.9.213 (Bitte bestätigen)

1. Die Datei liegt auf dem Server, ihr Pfad ist das Argument; eine Datei unter dem Projektordner lehnt das Skript ab, bevor es sie liest (Rückgabe 2).
2. Trägt eine Person im ERP eine eingelesene Nummer heute (Lohnstammdaten, bei „DATEV-Nr. = ERP-Nr.“ die Mitarbeiternummer), wird sie ihr gemerkt und sie behält sie; sonst steht die Nummer ohne Person und bekommt keine Person im ERP. Die Meldung beim Speichern nennt dann keinen Namen, sondern „eingelesene Liste vergebener Nummern“.
3. Mehrfach ausführbar: eine schon gemerkte Nummer bleibt, wie sie ist (auch, wem sie gemerkt ist). Gemeldet werden die neuen Nummern (eine Person nur mit ihrer Kennung) und die schon gemerkten, jeweils mit der Nummer.
4. Aufbau der Datei: je Zeile eine Nummer, bei CSV das erste Feld vor „;“, „,“ oder Tabulator; leere Zeilen und Zeilen mit „#“ zählen nicht; eine Zeile, deren erstes Feld keine Zahl ist, wird übersprungen und nur mit ihrer Zeilennummer genannt (dort kann ein Name stehen); 1 bis 4 Ziffern werden links auf 5 aufgefüllt (wie die Migration 5d2e8a71c4f3 -- eine Tabellenkalkulation lässt führende Nullen weg); mehr als 5 Ziffern: Abbruch, nichts gemerkt (Rückgabe 1); doppelte zählen einmal.
5. `--probe` meldet dasselbe, schreibt nichts; ohne `--probe` ein Commit für alle Nummern.
6. Nummern ohne Person stehen auf der Seite nirgends (die Liste „früher“ ist je Person). Freigeben kann der Admin sie wie jede gemerkte, aber nur über die Schnittstelle (`POST /api/time-backoffice/personalnummern/freigeben`) -- eine Liste der eingelesenen Nummern auf der Seite ist nicht gebaut.
7. `scripts/pruefe_zeitregeln.py` zählt die Nummern ohne Person; trägt eine aktive Person eine davon (nur an der Sperre vorbei möglich), ist das ein Befund.
8. `downgrade()` löscht die Nummern ohne Person; nach einem erneuten Einspielen das Skript noch einmal laufen lassen.

### Tests und Prüfung 1.9.213

Neu: `tests/test_v618_personalnummern_einlesen.py` (12 Tests, alle Nummern erfunden) -- zwei Läufe (neu, schon gemerkt, die Trägerin behält ihre), danach gesperrt für eine andere Person, freigeben einer eingelesenen, `--probe`, Aufbau der Datei (Überschrift, Kommentar, CSV, Auffüllen, doppelt, kein Name in der Ausgabe), mehr als 5 Ziffern, Datei im Projektordner, ohne `DATABASE_URL`, Prüfskript, keine Datei mit Personalnummern im Repository, Migration auf einem Bestand unter SQLite und PostgreSQL. Gegenproben je Festlegung: Archiv „Gegenproben Lohn L1a“, Abschnitt „Stufe 6“. Angepasste Erwartungen: keine.

### Umsetzung 1.9.214: Zuordnung mit den Werten des Lohnbüros (Punkt 3)

`app/lohnarten.py::START`: `kalender:heiligabend` FR / 1080, `kalender:silvester` UU ohne Lohnart, `schlechtwetter:winter` WA / 8195 ohne Monatszeile, neu `art:berufsschule` FE ohne Lohnart (legt `ensure_default_lohnart_zuordnungen()` an, wenn sie fehlt); `schlechtwetter:sommer` bleibt leer. Migration `a3f61c8d2b95`: dieselben vier Zeilen, nur wo genau der bisherige Vorgabewert steht (Heiligabend BF ohne Lohnart, Silvester AF ohne Lohnart, Winter Monatszeile 8110, Berufsschule leer); eine andere bleibt und die Migration schreibt „Zuordnung …: von Hand geändert, nicht umgestellt“ in ihre Ausgabe (also in die von `update.sh`); eine fehlende legt der Start an. `downgrade()` stellt nur zurück, was genau den neuen Wert trägt. Der Satz über der Tabelle der Einstellungen sagt jetzt, dass Schlechtwetter je Ausfalltag in der Datei steht und die Monatszeile nirgends vorbelegt ist.

Bis 1.9.215 gilt die alte Regel „zum Kennzeichen gehört eine Lohnart“ (Festlegung 1.9.175 Nr. 5): Silvester und Berufsschule wirken in 1.9.214 wie eine Zeile ohne Lohnart -- Silvester „UU / Lohnart offen – nicht exportiert“, Berufsschule „wie die Kategorie – Fortbildung: nicht exportiert“; in 1.9.214 lässt sich die Zeile Berufsschule mit FE ohne Lohnart nicht speichern (das kann erst 1.9.215).

### Festlegungen 1.9.214 (Bitte bestätigen)

1. = Festlegung 1.9.169 Nr. 3, neu gefasst (oben): Schlechtwetter Winter WA / 8195 je Ausfalltag, keine Monatszeile; Sommer leer.
2. Die Werte des Lohnbüros sind die Vorbelegung einer neuen Installation: Heiligabend FR / 1080, Silvester UU ohne Lohnart, Schlechtwetter Winter WA / 8195, Berufsschule FE ohne Lohnart, Schlechtwetter Sommer leer.
3. Eine bestehende Installation stellt die Migration nur dort um, wo noch genau der bisherige Vorgabewert steht (wie die Sollzeit in `b7e3c91d4a52`); eine von Hand geänderte Zeile bleibt und wird in der Ausgabe genannt -- das Büro entscheidet. `downgrade()` ebenso nur bei genau dem neuen Wert.
4. Berufsschule bekommt als zweite Art (nach Weiterbildung) eine vorbelegte Zeile (Festlegung 1.9.169 Nr. 5 ergänzt); eine leere Zeile Berufsschule (wie die Kategorie) zählt für die Migration als bisheriger Vorgabewert.

### Notiz für L1b (nicht gebaut)

- Mehrarbeit von Azubis: AA / 1900, je Tag (Antwort des Lohnbüros, Vorgabe Tobias 05.11.2026). Was „Mehrarbeit“ eines Azubis an einem Tag ist (Arbeit über der Sollzeit?) und ob die Stunden dann nicht unter 1 / 1000 stehen, ist mit dem Export zu klären.

### Tests und Prüfung 1.9.214

Neu: `tests/test_v619_zuordnung_lohnbuero.py` (5 Tests) -- Vorbelegung, Schlechtwetter Winter je Tag ohne Monatszeile (Sommer nicht exportiert), ein Neustart lässt Geändertes und Geleertes stehen, Migration auf einem Bestand unter SQLite und PostgreSQL (Heiligabend und Winter umgestellt, Silvester von Hand geändert bleibt und steht in der Ausgabe, Berufsschule fehlt -> bleibt dem Start; leer -> FE, zurück leer; hoch, runter, hoch). Gegenproben je Festlegung: Archiv „Gegenproben Lohn L1a“, Abschnitt „Stufe 6“.

Angepasste Erwartungen (Regel 28) zu 1.9.214:
- `test_v587::test_vorbelegt_nach_e7`: Schlechtwetter Winter altes Soll (–, 8110, Monatszeile, „Monatszeile 8110“), neues Soll (WA, 8195, ohne, „WA / 8195“); Berufsschule altes Soll (–, –, ohne), neues Soll (FE, –, ohne), „Wirkt“ unverändert „wie die Kategorie – Fortbildung: nicht exportiert“.
- `test_v587::test_schlechtwetter_nach_datum`: Lohnart im Winter altes Soll 8110, neues Soll 8195.
- `test_v590::test_zuordnung_fuer_den_export`: altes Soll „schlechtwetter:winter: Monatszeile 8110“, neues Soll „schlechtwetter:winter: WA / 8195“.
- `test_v591::test_heiligabend_ist_vorbelegt`: Zuordnung altes Soll BF ohne Lohnart, nicht exportiert, „BF / Lohnart offen – nicht exportiert“, neues Soll FR / 1080, exportiert, „FR / 1080“.
- `test_v591::test_pruefskript_nennt_den_kalender`: altes Soll „kalender:heiligabend: BF / Lohnart offen“, neues Soll „kalender:heiligabend: FR / 1080“.
- `test_v592::test_silvester_ist_vorbelegt`: Kennzeichen altes Soll AF, neues Soll UU (ohne Lohnart, nicht exportiert bleibt).
- `test_v610::test_gespeicherte_art_wird_uebergangen` und `::test_auch_eine_art_fuer_jede_kategorie_nicht`: Winter altes Soll (–, 8110, Monatszeile), neues Soll (WA, 8195, ohne).
- `test_v604::test_zeile_je_art_erst_beim_ersten_speichern`: nach dem Start altes Soll nur `art:weiterbildung`, neues Soll dazu `art:berufsschule`.
- `klicktest_lohnarten` „Fin: vorbelegt nach E7, Leeres sichtbar“: Winter altes Soll „Monatszeile 8110“, neues Soll „WA / 8195“.
- `klicktest_arbeitszeitkalender` „Fin: Zuordnung BF ohne Lohnart“, jetzt „Fin: Zuordnung FR / 1080“: altes Soll „BF / Lohnart offen – nicht exportiert“, neues Soll „FR / 1080“.

### Umsetzung 1.9.215: drei Fälle je Zeile der Zuordnung (Punkt 4)

`app/lohnarten.py`: `_gesetzt()` (wird exportiert) heißt jetzt „Kennzeichen gesetzt“ -- oder eine Monatszeile mit Lohnart; bis 1.9.214 „Lohnart gesetzt“. Daraus folgen `zuordnung()` (die Art geht vor, sobald sie ein Kennzeichen hat; die Lohnart im Ergebnis kann leer sein), `fest()` und `kalender()` (`exportiert` auch ohne Lohnart). `speichern()` ohne „Zum Kennzeichen gehört eine Lohnart.“; „Zur Lohnart gehört ein Kennzeichen (oder bei Schlechtwetter die Monatszeile).“ bleibt. Neu `wirkt()` (der Fall: „nicht exportiert“, „UU – exportiert, Stunden ohne Lohnart“, „FR / 1080 – exportiert mit Lohnart“, „Monatszeile 8110 – exportiert als eine Zeile je Monat“) und `kurz()` (der gespeicherte Wert, für eine übergangene Zeile je Art bei Schlechtwetter). `scripts/pruefe_zeitregeln.py` nennt je Zeile `wirkt()`, eine übergangene Zeile „gespeichert S / 8111 – wird übergangen“. Der Satz über der Tabelle der Einstellungen nennt die drei Fälle.

### Festlegungen 1.9.215 (Bitte bestätigen)

1. = Festlegung 1.9.175 Nr. 5, neu gefasst (oben): für jede Zeile Kennzeichen leer -> nicht exportiert, Kennzeichen ohne Lohnart -> exportiert ohne Lohnart, beides -> mit Lohnart; „Wirkt“ sagt den Fall.
2. = Festlegung 1.9.169 Nr. 2, neu gefasst (oben): eine Art geht ihrer Kategorie vor, sobald sie ein Kennzeichen hat.
3. Eine Lohnart ohne Kennzeichen lehnt das Speichern weiter ab (außer als Monatszeile): nach der Regel hieße sie „nicht exportiert“ und ist fast sicher ein Versehen.
4. Die Monatszeile bleibt bis L1b ein vierter Fall neben den dreien (nur Schlechtwetter, Lohnart ohne Kennzeichen, „Monatszeile 8110 – exportiert als eine Zeile je Monat“) -- keine Zeile nutzt sie seit 1.9.214; geändert wird daran nichts (Befund 1.9.217).
5. Das Prüfskript nennt je Zeile denselben Fall wie „Wirkt“; eine übergangene Zeile je Art bei Schlechtwetter nur mit ihrem gespeicherten Wert („gespeichert S / 8111 – wird übergangen“), weil sie nie wirkt.

### Tests und Prüfung 1.9.215

Neu: `tests/test_v620_zuordnung_drei_faelle.py` (12 Tests) -- die drei Fälle in „Wirkt“ an einer Kategorie, einer Art, einem Kalendertag und einer festen Zeile; ohne Kennzeichen nicht exportiert; Kennzeichen ohne Lohnart exportiert (Kategorie, Arbeit, Silvester); Berufsschule FE geht Fortbildung vor; eine Art mit Kennzeichen geht vor, geleert wieder die Kategorie; Lohnart ohne Kennzeichen abgelehnt; die Monatszeile als eigener Fall; die Schnittstelle; der Satz auf der Seite. `klicktest_lohnarten`: eine Prüfung mehr (Unbezahlt UB ohne Lohnart -> „UB – exportiert, Stunden ohne Lohnart“). Gegenproben je Festlegung: Archiv „Gegenproben Lohn L1a“, Abschnitt „Stufe 6“.

Angepasste Erwartungen (Regel 28) zu 1.9.215 -- überall „Wirkt“ mit dem Fall:
- `test_v587::test_vorbelegt_nach_e7`: altes Soll „1 / 1000“, „F / 1012“, „U / 8000“, „K / 1650“, „WA / 8195“, „1 / 1000“ (Weiterbildung), Berufsschule „wie die Kategorie – Fortbildung: nicht exportiert“; neues Soll je „… – exportiert mit Lohnart“, Berufsschule „FE – exportiert, Stunden ohne Lohnart“.
- `test_v587::test_art_vor_kategorie[Berufsschule]`: altes Soll keine Zuordnung, neues Soll FE ohne Lohnart.
- `test_v587::test_pruefungen`: der Fall „feiertag F ohne Lohnart -> „gehört eine Lohnart““ entfällt (wird jetzt gespeichert).
- `test_v587::test_schnittstelle_und_rechte`: „Z / 1500“ -> „Z / 1500 – exportiert mit Lohnart“.
- `test_v590::test_zuordnung_fuer_den_export`: „arbeit: 1 / 1000“, „kategorie:urlaub: U / 8000“, „schlechtwetter:winter: WA / 8195“, „art:weiterbildung: 1 / 1000“ -> je mit „ – exportiert mit Lohnart“.
- `test_v591::test_heiligabend_ist_vorbelegt` und `::test_pruefskript_nennt_den_kalender`: „FR / 1080“ -> „FR / 1080 – exportiert mit Lohnart“.
- `test_v591::test_zuordnung_des_kalendertags`: BF ohne Lohnart altes Soll nicht exportiert, neues Soll exportiert; Arbeit „1“ ohne Lohnart altes Soll abgelehnt („Zum Kennzeichen gehört eine Lohnart“), neues Soll gespeichert.
- `test_v592::test_silvester_ist_vorbelegt`: UU ohne Lohnart altes Soll nicht exportiert, neues Soll exportiert.
- `test_v610::test_pruefskript_nennt_die_uebergangene_zeile`: „art:schlechtwetter: S / 8111“ -> „art:schlechtwetter: gespeichert S / 8111 – wird übergangen“.
- `klicktest_lohnarten` „Fin: vorbelegt nach E7, Leeres sichtbar“, „Fin: Freizeitausgleich Z / 1500, die Art folgt der Kategorie“, „Bea: Felder gesperrt …“: je mit „ – exportiert mit Lohnart“, Berufsschule „FE – exportiert, Stunden ohne Lohnart“.
- `klicktest_arbeitszeitkalender` „Fin: Zuordnung FR / 1080“: „FR / 1080“ -> „FR / 1080 – exportiert mit Lohnart“.
