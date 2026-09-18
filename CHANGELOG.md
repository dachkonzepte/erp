# Changelog – DACHKONZEPTE ERP

Rückwirkend rekonstruiert aus den Entwicklungssitzungen seit Version 1.0.6 (die erste Version, ab der ein durchgehendes README pro Version vorliegt). Neueste Version zuerst. Ab 1.0.52 wird diese Datei laufend mit jeder neuen Version fortgeschrieben.

Die Versionen 1.0.57–1.0.101 wurden nachträglich aus `seit 1.0.NN`-Vermerken im Code sowie aus dem Gesprächsverlauf der jeweiligen Entwicklungssitzung rekonstruiert, nachdem diese Datei über einen langen Zeitraum nicht mitgepflegt wurde. Für folgende Versionsnummern ließ sich im Code kein zuordenbarer Vermerk mehr finden; damit hier nichts erfunden wird, bleiben sie bewusst ohne eigenen Eintrag: 1.0.60, 1.0.62, 1.0.63, 1.0.72, 1.0.73, 1.0.75–1.0.78, 1.0.80, 1.0.81, 1.0.83, 1.0.85, 1.0.86, 1.0.88, 1.0.89, 1.0.91, 1.0.93, 1.0.95, 1.0.96.

## 1.4.8 – Rechtekonzept: vier Rollen statt zwei, Etappe 2 (die Verengungen)

Zweite und letzte Etappe des vom Betreiber beauftragten Rollen-Umbaus (siehe CLAUDE.md
"Rechtekonzept" -> "Vier Rollen" für die vollständige Herleitung). Diese Version setzt die drei
in 1.4.7 angekündigten Verengungen und die eine Erweiterung tatsächlich um -- ab jetzt sieht
`buero_auftrag` nicht mehr dasselbe wie `buero_finanzen`.

**Verengt auf `require_min_role(buero_finanzen)`**: `GET/PUT /api/calculation-settings`
(`app/routers/settings.py`) und die komplette `app/routers/labor_rate.py` (alle 4 Endpunkte,
ein einziger Modul-`_role_dep`) -- die Pflege der Kalkulationsgrundlagen und der Herleitung des
Stundenverrechnungssatzes aus den Mitarbeiter-Stundenlöhnen. Geprüft, was der fertige Satz für
`buero_auftrag` bedeutet: `CalculationSettings.labor_rate` ist ein eigenständig gespeicherter
Wert, keine aus den drei Kalkulationsfaktoren berechnete Größe -- `buero_auftrag` sieht ihn
weiterhin dort, wo er ANGEWENDET wird (Angebotskalkulation/Leistungskatalog, beide bereits
unverengt), nur nicht mehr, wo er GEPFLEGT wird.

**Mitarbeitervergütung verengt, der Bestand bleibt**: `app/routers/employees.py` bekommt eine
dritte, rollenabhängige Antwortform. Neues `EmployeeRosterOut`-Schema (`app/schemas.py`) --
Name, Funktion, Kontakt, Planung, Kosten-Zuordnung (eine reine Kategorie, kein Betrag), aber
ohne `compensation_type`/`hourly_wage`/`monthly_salary`/`effective_hourly_wage`/
`annual_gross_wage`. `_employee_out_for_role()` ist die eine Stelle, die je Rolle zwischen
`EmployeeOut` (buero_finanzen/admin), `EmployeeRosterOut` (buero_auftrag) und `EmployeeNameOut`
(field, unverändert seit 1.3.53) wählt -- angewendet auf alle drei Lese-Endpunkte (Liste,
Sachbearbeiter, Einzelabruf). **Anlegen/Bearbeiten dagegen komplett auf `buero_finanzen`**,
nicht nur die Vergütungsfelder: das Formular (`master_data_form.html::employeeForm()`) ist ein
einziges, kombiniertes Formular mit den Lohnfeldern direkt darin (Regel 10 -- kein zweites,
vergütungsfreies Formular für einen einzelnen Bereich). Eine Aufteilung der Schreibrechte hätte
ein zweites Formular oder eine partielle PUT-Semantik gebraucht, UND ein echtes Risiko
eingeführt: ein für `buero_auftrag` unsichtbares Lohnfeld würde beim Speichern sonst den
bestehenden Wert eines Kollegen stillschweigend auf 0/`None` überschreiben. Diese Erweiterung
über eine wörtliche Lesart der Anfrage hinaus wird hier transparent festgehalten, wie in diesem
Projekt üblich. `app/routers/pages.py::_require_finanzen_for_employees()` sperrt zusätzlich die
beiden Formular-SEITEN (`/master-data/employees/new|{id}/edit`) selbst für `buero_auftrag` --
sonst hätte diese Rolle ein Formular gesehen, dessen Speichern die API ohnehin abgelehnt hätte.
`master_data.html` blendet Vergütungsspalte, "Gewichteter Mittellohn"-Kachel, "+ Hinzufügen" und
"Bearbeiten" für `buero_auftrag` aus (ausblenden, nicht ausgrauen) -- die zählenden Kennzahlen
("MA im Verrechnungssatz"/"MA in variablen GK") bleiben sichtbar, da sie keinen Betrag zeigen.

**Zeiterfassungs-Backoffice angehoben** (`app/routers/time_backoffice.py`, 15 Endpunkte): von
`require_admin()` auf `require_min_role(buero_auftrag)` -- Betreiberbegründung: Zeiten der
Kolonnen korrigieren/Abwesenheiten verwalten gehört zum laufenden, von `buero_auftrag`
geführten Betrieb. Vor der Anhebung wie verlangt geprüft, ob dabei Vergütung mitsichtbar wird --
kein Fund: `EmployeePayrollSettingsOut` trägt nur `datev_personnel_number`/
`payroll_export_enabled` (eine Personalnummer-Zuordnung, kein Betrag), `backoffice_summary()`/
`build_timesheet_pdf()`/`build_time_csv()` zeigen ausschließlich Stunden, `build_datev_export()`s
"Lohnart" ist eine DATEV-Buchungskategorie (Zeitart-zu-Buchungscode), kein €-Betrag. Kein
einziges €-Vergütungsfeld in der ganzen Datei -- die gesamte Datei hebt sich deshalb einheitlich
an, ohne dass innerhalb von ihr etwas verengt werden musste.

**Eigener Fund dieser Etappe, nicht in der ursprünglichen Anfrage benannt: die
Änderungshistorie.** `GET /api/audit-logs` (`app/routers/audit.py`) zeigt Vorher-/Nachher-Werte
und angelegt/gelöscht-Schnappschüsse über ALLE Entitäten hinweg, auch Mitarbeiter --
`AuditLog.old_value`/`new_value` einer `hourly_wage`-Änderung enthält den Betrag im Klartext,
der JSON-Schnappschuss eines neu angelegten Mitarbeiters ebenso. Das ist wörtlich "jede
Auswertung, die Löhne zeigt". Neue `app/audit.py::WAGE_FIELD_NAMES`/`redact_wage_snapshot()`:
für `buero_auftrag` entfallen "geändert"-Zeilen mit einem Lohnfeld vollständig (nie old/new_value
zeigen), "angelegt"/"gelöscht"-Schnappschüsse werden um die drei Lohnschlüssel bereinigt, ohne
die zugrunde liegende `AuditLog`-Zeile zu mutieren (ein neues `AuditLogOut`, nicht das
ORM-Objekt selbst, damit nichts versehentlich in einer späteren Session-Aktion committet wird).
`buero_finanzen`/`admin` sehen die Historie unverändert vollständig. Andere Entitäten (Projekte,
Angebote, Kunden ...) bleiben für `buero_auftrag` vollständig einsehbar -- nur Lohnfelder
entfallen, nicht die Historie als Ganzes.

**Beim Bauen gefundener und behobener Jinja-Fehler**: die neuen Sichtbarkeits-Bedingungen in
`settings.html`/`master_data.html` (`{% if can(current_user, 'admin', 'buero_finanzen') %}`)
verließen sich auf `{% set current_user = request.state.erp_user %}` aus dem eingebundenen
`_sidebar.html` -- ein `{% set %}` innerhalb eines `{% include %}` wirkt in Jinja aber NICHT in
der einbindenden Vorlage nach, unabhängig von der Rolle. Beide Dateien setzen `current_user`
seither selbst, direkt nach `<body>`. Ohne diesen Fund hätte jeder Aufruf von `/settings` und
`/master-data` -- für JEDE Rolle, nicht nur `buero_auftrag` -- mit `UndefinedError` abgebrochen;
gefangen durch den bereits bestehenden `test_v218_template_rendering.py` (der jede Seiten-Route
einmal rendert), nicht durch manuelles Ausprobieren.

**Angriffstest zum Abschluss** (`tests/test_v282_role_narrowing_etappe2.py`, 18 Tests, je ein
Testkonto pro Rolle): `buero_auftrag` bekommt 403 auf Kalkulationsgrundlagen/
Stundenverrechnungssatz-Herleitung/Mitarbeiter-Schreiben, ohne dass in irgendeiner Antwort ein
Lohnfeld auftaucht (rekursiver Schlüssel-Scan, auch durch als JSON-String codierte
`AuditLogOut.details`-Werte hindurch); `buero_auftrag` erreicht das Zeiterfassungs-Backoffice
(200), aber ohne jedes Lohnfeld; `buero_finanzen` sieht alles davon (200, inkl. Lohnfeldern wo
vorgesehen); `field` bleibt überall gesperrt, wie zuvor. Zusätzlich zwei ältere Tests korrigiert,
die durch diese Etappe echt veraltet waren: `test_v109_unified_admin_dependency.py` prüfte
bisher "alle 15 time-backoffice-Routen nutzen `require_admin()`" -- jetzt auf die neue, ebenso
geteilte `_role_dep`-Variable umgestellt; `test_v067_admin_and_masterdata_edit.py` rief
`get_employee()` bisher ohne Rollen-Argument direkt auf (unproblematisch, solange die Funktion
`_role` nie inhaltlich auswertete) -- seit `_employee_out_for_role()` braucht der direkte Aufruf
jetzt eine echte Rolle. Volle Suite: 1532 Tests grün.

## 1.4.7 – Rechtekonzept: vier Rollen statt zwei, Etappe 1 (reine Rollen-Erweiterung)

Erste von zwei Etappen des vom Betreiber beauftragten Rollen-Umbaus (Befund + Vorschlag zuvor
separat berichtet, keine Codeänderung -- siehe CLAUDE.md "Rechtekonzept" -> "Vier Rollen" für die
vollständige Herleitung). Diese Version liefert AUSSCHLIESSLICH die Rollen-Erweiterung selbst --
Rollenmodell, Hierarchie, Migration, Benutzerverwaltung mit vier wählbaren Rollen -- bewusst OHNE
jede der drei angekündigten Verengungen (Kalkulationsgrundlagen, Betriebskosten-Übersicht,
Mitarbeitervergütung) oder die eine angekündigte Erweiterung (Zeiterfassungs-Backoffice). Bis zum
Abschluss von Etappe 2 sieht buero_auftrag deshalb weiterhin exakt dasselbe wie buero_finanzen --
kein Endpunkt ist bereits enger geschnitten, kein Endpunkt bereits weiter geöffnet.

**Die bisherige, einzelne Rolle "office" wird in zwei Rollen aufgeteilt**: `buero_finanzen`
(alles Fachliche/Kaufmännische PLUS Betriebskosten-Übersicht/Kalkulationsgrundlagen/
Stundenverrechnungssatz-Herleitung/Mitarbeitervergütung, Schnittstelle zum Steuerberater, keine
Systemverwaltung) und `buero_auftrag` (der komplette produktive und kaufmännische Betrieb --
Projekte, Angebote mit voller Kalkulation, Aufträge, Rechnungen, Mahnwesen, Planung, Wartung,
Anfragen, Aufgaben, Betriebsmittel-Bestand -- ohne die vier finanzspezifischen Bereiche oben).
`admin`/`field` bleiben unverändert.

**Hierarchie statt vier unabhängiger Rollenmengen** (`app/permissions.py::ROLE_RANK`,
`has_min_role()`, `require_min_role()`) -- die zentrale Frage vor dem Bau: admin ⊇ buero_finanzen
⊇ buero_auftrag ⊇ field, kann buero_finanzen alles, was buero_auftrag kann, plus mehr? Ja --
`ROLE_RANK` ist eine reine Ganzzahl-Kette (0=field, 1=buero_auftrag, 2=buero_finanzen, 3=admin),
`require_min_role(min_role)` lässt jede Rolle AB diesem Rang durch, ohne sie einzeln aufzuzählen.
Das bestätigt sich exakt an der real vorgefundenen Codestruktur: im gesamten Projekt kamen bislang
nur zwei Rollenkombinationen vor (`require_role(ROLE_ADMIN, ROLE_OFFICE)` in ~40 Dateien,
`require_role(ROLE_ADMIN, ROLE_OFFICE, ROLE_FIELD)` in ~15 Dateien) -- beide übersetzen sich
mechanisch, ohne Einzelentscheidung, in `require_min_role(ROLE_OFFICE_AUFTRAG)` bzw.
`require_min_role(ROLE_FIELD)`. Die Migration ist dadurch deutlich weniger invasiv, als eine vier
unabhängige Mengen verwaltende Alternative gewesen wäre. `require_role()`/`has_role()` (die
flache Mengenprüfung) bleiben unverändert bestehen -- für admin-only und echte "für jede Rolle
offen"-Fälle, kein Ersatz für die Hierarchie, sondern eine zweite, weiterhin gültige Prüfart
daneben. `require_admin()` (`app/deps.py`) bleibt unverändert (deckt sich mit
`require_min_role(ROLE_ADMIN)`), an den Dateien, die es nutzt, wurde in dieser Etappe nichts
geändert -- die Verschiebung von `time_backoffice.py`/`address-import` ist Teil von Etappe 2.

**Mechanische Umstellung, keine Einzelentscheidung** -- ~55 Endpunkt-Dependencies in ~45
Router-Dateien (`app/routers/*.py`) sowie zwei App-Kernmodule (`app/tasks.py::list_tasks_for_user()`,
`app/search.py::OFFICE_ROLES`) wurden von `require_role(ROLE_ADMIN, ROLE_OFFICE[, ROLE_FIELD])`
auf `require_min_role(...)` umgestellt -- ein Skript hat die reine Textersetzung vorgenommen,
anschließend wurden Importzeilen bereinigt (ungenutzte Symbole entfernt, `require_min_role`
ergänzt) und jedes Router-Modul einzeln importiert, um fehlende/falsche Importe sofort als
`ImportError` statt erst als Testfehler zu finden. Ein einziger, vom Skript nicht erfasster
manueller Vergleich (`app/routers/pages.py::_require_users_page_access()`, `user.role not in
(ROLE_ADMIN, ROLE_OFFICE)`) wurde dabei gefunden und auf `has_min_role(user, ROLE_OFFICE_AUFTRAG)`
umgestellt. `app/search.py::OFFICE_ROLES` (die einzige, zentrale Konstante, die alle 18
Suchquellen-Einträge referenzieren) wurde auf `{ROLE_ADMIN, ROLE_OFFICE_FINANZEN,
ROLE_OFFICE_AUFTRAG}` erweitert -- eine einzige Konstantenänderung genügt für die gesamte
Büro-Suche, keine 18 Einzelentscheidungen (bereits in der vorangegangenen Bestandsaufnahme so
vorhergesagt und hier bestätigt). Drei literale `can(current_user, 'admin', 'office')`-Aufrufe in
`_sidebar.html`/`_topbar.html` (Jinja-Templates kennen keine Rollenkonstanten, nur die
String-Literale) wurden auf beide neuen Rollennamen erweitert.

**Migration `7677d9d878ba`** (reine Daten-Migration, kein Schema-Umbau -- `app_users.role` war
immer schon eine unbeschränkte `String(30)`-Spalte ohne Constraint): ein bestehendes
`role="office"`-Konto wird `buero_finanzen` -- die umfassendere der beiden neuen Rollen, wie vom
Betreiber vorgegeben (Bestandsschutz: ein bereits eingerichtetes Büro-Konto darf durch den Split
nie Zugriff verlieren). **Vor der Migration geprüft, nicht geraten** (wie ausdrücklich verlangt):
die echte, lokale `dachkonzepte_erp.db` trägt genau zwei Konten (Tobias, Admin), beide bereits
`admin` -- 0 Zeilen betroffen. Migration trotzdem angewendet (Kettenanschluss), Bestand danach
erneut verifiziert: beide Konten unverändert `admin`. `AppUserCreate`/`-Update` (`app/schemas.py`):
Pattern erweitert auf alle vier Rollen, Vorgabewert (greift nur, wenn ein Aufruf `role` ganz
weglässt) von `"field"` auf `"buero_auftrag"` geändert -- die restriktivere der beiden Bürorollen,
damit niemand allein durch Weglassen des Feldes Zugriff auf Kalkulationsgrundlagen/
Mitarbeitervergütung erben kann. Die Sidebar-Voreinstellung in `users.html` bleibt bewusst
unabhängig davon `field` (Monteur) -- die am wenigsten privilegierte Rolle über alle vier hinweg,
unverändert seit 1.3.51.

**Benutzerverwaltung** (`users.html`): Rollen-Dropdown zeigt jetzt vier Optionen ("Monteur"/"Büro
– Auftrag"/"Büro – Finanzen"/"Administrator", in dieser, der Rangfolge entsprechenden
Reihenfolge) statt drei, die bereits bestehende Bestätigungsabfrage beim Anlegen ohne
ausdrücklich gewählte Rolle bleibt unverändert erhalten.

**Testfolgen**: ~140 Vorkommen von `role="office"`/`ROLE_OFFICE` über ~35 Testdateien wurden
durchgesehen und einzeln eingeordnet -- reine Testaufbau-Stellen (der weit überwiegende Teil)
mechanisch auf `buero_auftrag` umbenannt; eine kleine Zahl von Stellen, die ausdrücklich "office
UND admin dürfen beide" belegen sollten, auf alle drei nicht-Monteur-Rollen erweitert statt nur
umbenannt (stärkerer Nachweis der Hierarchie an genau den Stellen, die das schon vorher zeigen
wollten); `tests/test_v261_permissions_foundation.py`s Migrationstest für die HISTORISCHE
Migration `7a2b4e9f1c3d` (role='user' -> 'office') bewusst unverändert gelassen -- der testet
eine bereits abgeschlossene, andere Migration, kein Teil dieser Version.
`tests/test_v260_role_audit.py` (der Standardverweigerungs-Audit) bekommt zusätzlich einen neuen
Test, der die `_dk_roles`-Markierung von `require_min_role()` selbst prüft (Pendant zum
bestehenden Test für `require_role()`/`require_admin()`). Neue, dedizierte Datei
`tests/test_v281_role_hierarchy.py` -- end-to-end-Nachweis der Hierarchie über eine echte
FastAPI-Testroute (nicht nur die Funktion isoliert): `require_min_role(ROLE_OFFICE_AUFTRAG)`
lässt buero_auftrag, buero_finanzen UND admin durch, ohne dass Letztere einzeln genannt werden
mussten; ein liegen gebliebener Altwert ("office") fällt an jeder Schwelle sicher durch. Volle
Suite: 1514 Tests grün.

**Bewusst NICHT Teil dieser Version** (Etappe 2, folgt nach Rückmeldung zu dieser Etappe, siehe
CLAUDE.md "Rechtekonzept" -> "Vier Rollen"): die drei Verengungen auf `buero_finanzen`
(Kalkulationsgrundlagen/Stundenverrechnungssatz-Herleitung, künftige Betriebskosten-Übersicht,
Mitarbeitervergütung), die eine Erweiterung (`time_backoffice.py`/`address-import` von admin-only
auf `buero_auftrag`), und die noch offene, vom Betreiber selbst nachgeschärfte Detailfrage, wie
der fertige Stundenverrechnungssatz (als Zahl, wo angewendet) von seiner Herleitung (Lohnansatz/
Gemeinkosten/Materialaufschlag/Wagnis & Gewinn) technisch sauber getrennt wird.

## 1.4.6 – Self-Seeding gegen gleichzeitigen ersten Zugriff abgesichert

Nachgezogener Fund aus der 1.4.5-Verifikation (Betriebsmittelverwaltung Stufe 3): ein
CDP-gesteuerter Browsertest hatte transparent, als unabhängigen Nebenbefund, eine Race Condition
in `app/option_settings.py::ensure_default_option_groups()` gemeldet -- zwei gleichzeitige erste
Zugriffe auf eine frische, noch nie geseedete Datenbank (zwei Arbeitsprozesse, oder -- realistischer
für diese Installation, die produktiv mit einem einzigen `gunicorn`-Worker läuft, siehe CLAUDE.md
"Produktivbetrieb" -- zwei von Starlettes Threadpool gleichzeitig bediente Requests innerhalb
desselben Prozesses) konnten beide "keine Gruppen vorhanden" lesen und beide dieselben
Standardzeilen einzufügen versuchen -- der zweite Versuch kollidierte mit einer unabgefangenen
`sqlalchemy.exc.IntegrityError` (UNIQUE-Verletzung auf `group_key`, real beobachtet bei
`group_key='units'`, dem ersten Eintrag in `DEFAULT_OPTION_GROUPS`), die als 500 durchschlug.

**Abwägung, wie verlangt, vor dem Bauen**: Locking (z. B. ein PostgreSQL-Advisory-Lock) versus
Abfangen der UNIQUE-Kollision und Behandeln als "schon gesät". Für Letzteres entschieden --
weniger fragil, da (a) kein neues, plattformabhängiges Locking-Primitiv nötig ist (ein
Advisory-Lock hat unter SQLite, dem zweiten von diesem Projekt gleichberechtigt unterstützten
Dialekt, siehe CLAUDE.md "PostgreSQL-Umstieg", keine Entsprechung), (b) die Absicherung nur im
tatsächlichen Kollisionsfall aktiv wird, der Erfolgspfad bleibt unverändert, (c) keine neue
Infrastruktur/Abhängigkeit eingeführt wird. Jeder Anlegeversuch läuft seither in einem eigenen
SAVEPOINT (`db.begin_nested()`) -- eine dabei auftretende `IntegrityError` wird abgefangen und als
"ein anderer Prozess war schneller" behandelt, nicht als Fehler weitergereicht; ein `db.rollback()`
auf der GANZEN Session hätte dagegen auch bereits erfolgreich vorher angelegte, aber noch nicht
committete Zeilen derselben Schleife mit verworfen -- das SAVEPOINT begrenzt den Rollback exakt
auf den einen kollidierenden Versuch.

**Sweep**: dasselbe Self-Seeding-Muster (`ensure_default_*()`, "leg beim ersten Lesezugriff die
Standardwerte an") existiert an zwölf weiteren Stellen im Projekt -- geprüft, ob deren jeweilige
Tabelle einen UNIQUE-Constraint trägt (dann dieselbe Race-Condition-Klasse, sonst nur eine andere,
leisere Fehlerklasse: stille doppelte Zeilen statt eines Crashes). Acht Fundstellen betroffen und
nach demselben Muster abgesichert: `app/document_categories.py::ensure_default_categories()`
("Dokumentkategorien", vom Nutzer benannt), `app/project_pipeline_columns.py::ensure_default_columns()`
("Pipeline-Spalten", vom Nutzer benannt -- "Betriebsmittel-Dokumenttypen" ist bereits über
`option_settings.py` mit abgedeckt, da `operational_asset_document_types` nur ein weiterer Eintrag
in `DEFAULT_OPTION_GROUPS` ist, kein eigener Code-Pfad), `app/task_columns.py::ensure_default_columns()`
(das Vorbild, nach dem die Pipeline-Spalten gebaut wurden), `app/employees.py::ensure_default_employee_functions()`,
`app/document_page_margins.py::ensure_default_margins()` (Einzelzeilen-Variante -- kollidierte
Zeile wird nach dem Abfangen erneut gelesen und die des anderen Prozesses zurückgegeben, statt nur
übersprungen), `app/settings.py::get_or_create_sequence()` (dieselbe Einzelzeilen-Behandlung, höhere
Tragweite, da jede Dokumentnummer-Vergabe darüber läuft, aber nur der allererste Aufruf je
`sequence_key` betroffen ist), `app/work_time_models.py::ensure_default_work_time_models()` (die
komplexeste Fundstelle -- zwei Modelle samt Gültigkeits-/Pausenregeln laufen als eine Einheit in
einem einzigen SAVEPOINT). Vier weitere `ensure_default_*()`-Funktionen (`document_layout.py`,
`payment_terms.py`, `tax_keys.py`, `reminders.py`) folgen demselben Muster, ihre Tabellen tragen
aber keinen UNIQUE-Constraint -- ein Wettlauf würde dort nicht crashen, sondern nur stille doppelte
Zeilen anlegen; das Abfangen einer nie geworfenen `IntegrityError` würde dort nichts bewirken. Eine
Behebung bräuchte zuerst eine eigene Migration (fehlende Constraints ergänzen) und ist damit ein
größerer, separat zu entscheidender Schritt -- gemeldet, nicht Teil dieser Runde. Ebenfalls bewusst
außerhalb: das strukturell verwandte, aber deutlich umfangreichere "get_or_create_settings(id=1)"-
Singleton-Muster (`GeneralSettings`, `TaskSettings`, `MaintenanceSettings` u. v. a., über zehn
Tabellen) -- dort kollidiert ein PRIMARY KEY statt eines Business-Keys, ein eigener, größerer Sweep.

**Test, wie gefordert, mit vorhandenen Mitteln erreichbar**: `tests/test_v281_self_seeding_race_safety.py`
simuliert den gleichzeitigen ersten Zugriff deterministisch statt zeitbasiert -- zwei unabhängige
`Session`-Objekte auf dieselbe echte, temporäre SQLite-DATEI (nicht `:memory:`, das wäre pro
Connection isoliert), ein `event.listens_for(session1, "before_flush")`-Hook lässt beim ersten
eigenen Flush-Versuch eine zweite Session denselben Aufruf vollständig (inklusive Commit)
durchlaufen, bevor die erste fortfährt -- garantiert kollidierend, ganz ohne echtes
Threading/Timing. Gegen den unveränderten Code (`git stash` auf `option_settings.py`) verifiziert,
dass der Test die real gemeldete `IntegrityError` bei `group_key='units'` tatsächlich reproduziert,
bevor er gegen den Fix grün lief -- kein vorschnell grüner Test. Acht Tests (einer je Fundstelle),
zusätzlich ein Regressionstest für den unkollidierten Normalfall. `pytest` vollständig grün
(1501/1501).

## 1.4.5 – Betriebsmittelverwaltung, Stufe 3: eingesetzte Betriebsmittel im Einsatzbericht

Reine Dokumentation -- kein Preis, keine Menge, keine Betriebsstunden in dieser Version. Erst
Befund (Aufbau des Einsatzberichts, Vorbild `ServiceReportMaterial`, wo im PDF), dann drei
Entscheidungen des Betreibers, dann in einer Runde gebaut.

**`ServiceReportAsset`, so geschnitten, dass die Kostenerweiterung später sauber andockt.**
`service_report_id` + `asset_id` (Pflicht -- ein Betriebsmittel wird immer aus dem Katalog
gewählt, nie frei eingetippt, anders als `ServiceReportMaterial.material_id`) +
`asset_name_snapshot` (Pflicht, physisch eingefroren bei der Erfassung -- dasselbe Muster wie die
Bauteil-/Dachflächennamen seit 1.3.12) + `notes` (das einzige Zusatzfeld dieser Stufe, bleibt
intern) + `sort_order`/`created_by_employee_id`/`client_uuid`. Beides wie verlangt: `asset_id` als
echter Verweis für eine spätere Kostenauswertung, UND der eingefrorene Name für die Anzeige --
wird das Betriebsmittel später umbenannt oder gelöscht, zeigt ein unterschriebener Bericht
weiterhin, was damals eingesetzt wurde. Bewusst KEIN `roof_area_id` (anders als Material) -- ein
Kran/Hubsteiger gehört üblicherweise zum ganzen Einsatz. Diese Tabelle ist die vorgesehene Stelle
für die spätere Kosten-/Abrechnungserweiterung (Betriebsstunden, Mietdauer, abrechenbare Menge) --
nullable `ALTER TABLE ADD COLUMN`-Ergänzungen auf genau dieser Zeile, keine Strukturänderung.

**Das Flag "im Bericht auswählbar"** (`OperationalAsset.selectable_in_reports`, Standard AUS,
Muster `DocumentCategory.is_field_visible`): das Büro gibt bewusst frei, was in einen Bericht
darf, sonst wächst die Auswahlliste mit jedem Kleingerät zu. Gilt für JEDEN Aufrufer gleich, auch
Büro/Admin -- keine Rollenausnahme, zugleich die serverseitige Absicherung gegen eine geratene
`asset_id`. Die 5 Bestandsressourcen wurden bei der Migration auf "nicht auswählbar" gesetzt,
ohne zu raten, welche gemeint sein könnten -- das Büro gibt sie gezielt frei.

**Bedienung wie Material, ein vierter Panel-Umschalter** "Betriebsmittel" auf der Berichtskarte,
aber ein einfaches `<select>` statt einer Debounce-Suche (die freigegebene Liste bleibt in der
Praxis kurz). Neuer, für jede Rolle erreichbarer Endpunkt `GET /api/operational-assets/
selectable-for-report` liefert immer das bereits aus Stufe 2 bekannte, feldsichere
`OperationalAssetFieldOut`-Schema, gefiltert auf freigegeben+aktiv. Einfrieren nach der
Unterschrift wie Material/Fotos/Prüfpunkte, keine neue Pflichtprüfung in `sign_report()`.

**`delete_asset()` blockiert jetzt**, solange ein Bericht (Entwurf ODER unterschrieben) das Asset
referenziert -- strenger als `delete_roof_component()` (das nur bei unterschriebenen Berichten
blockiert), weil `ServiceReportAsset.asset_id` NICHT NULL ist und ein Löschen die
Fremdschlüsselbeziehung sonst immer verletzen würde. Archivieren (`active=False`) bleibt frei.

**QR-Scan im Bericht geprüft, nicht gebaut.** Der bestehende QR-Code öffnet beim Scannen eine neue
Seite und verlässt damit den gerade bearbeiteten Bericht -- kein natürlicher Andock-Punkt. Ein
echter In-Bericht-Scanner bräuchte Kamera-Zugriff im Browser plus eine neue Dekodier-Bibliothek,
mit Cross-Browser-Risiko. Zurückgestellt, bis sich im Betrieb zeigt, dass die Auswahlliste zu
umständlich ist -- für jetzt: Auswahl aus der Liste.

**Im Kundenbericht**: neuer Abschnitt "Eingesetzte Betriebsmittel", direkt nach "Verbrauchtes
Material", nur wenn tatsächlich welche erfasst wurden -- eine schlichte, komma-getrennte
Namensliste aus den eingefrorenen Namen, über den gemeinsamen Rahmen mit `KeepTogether`. `notes`
erscheint nie im PDF. Auch im reduzierten Feld-PDF vorhanden -- keine fremden Personendaten.

**Angriffstest**: die neue Auswahlliste liefert für jede Rolle (Monteur, Büro, Admin) ausschließlich
die fünf feldsicheren Felder, nie Kosten/Fristen/Artikelnummer (rekursiver Schlüssel-Scan). Ein
Monteur kann über eine nicht freigegebene oder geratene `asset_id` kein Betriebsmittel in einen
Bericht zwingen (400, keine stille Erfolgsmeldung) und keinem fremden Bericht ein Betriebsmittel
hinzufügen. Migration `b2226e22b9f0` (neue Tabelle `service_report_assets`, neue Spalte
`operational_assets.selectable_in_reports`), 26 neue Tests
(`tests/test_v280_operational_assets_stufe3.py`), volle Suite: 1492 Tests grün.

## 1.4.4 – Nachtrag zu 1.4.3: Büro-Suche findet Aufgaben über dieselbe Sichtbarkeitsregel

Der bei 1.4.3 transparent gemeldete, offene Punkt wurde behoben, solange der Zusammenhang noch
frisch war: die Büro-Suche (`app/search.py::_search_tasks()`) hatte keine Mitarbeiter-Filterung
-- ein Büro-Konto fand darüber auch die persönlich zugewiesene Aufgabe eines Kollegen, genau die
Grenze, die 1.4.3 für `GET /api/tasks`/das Dashboard gezogen hatte.

**Keine zweite Kopie der Regel, wie ausdrücklich verlangt.** `app/tasks.py::list_tasks()`/
`list_tasks_for_user()` bekommen einen neuen, optionalen `search: str | None`-Parameter
(Titel-ILIKE). `_search_tasks()` ruft `list_tasks_for_user()` seither ZWEIMAL auf -- einmal ohne
`unassigned_only` (eigene Aufgaben), einmal mit (empfängerlose) -- und vereinigt beide Listen
(Duplikate über die `id` entfernt), statt eine eigene, dritte Filterlogik nachzubauen:
`list_tasks_for_user()` liefert für die getrennten Board-Tabs bewusst ENTWEDER eigene ODER
empfängerlose Aufgaben, die Suche braucht dagegen beide kombiniert. Ein Büro-Konto ohne
Mitarbeiterverknüpfung kann "eigene" nicht bestimmen (`ValueError`, abgefangen) -- findet aber
weiterhin die empfängerlosen, statt komplett leer zu bleiben.

`search_office()` bekommt einen neuen, optionalen `employee_id`-Parameter (nur für die
"tasks"-Quelle relevant, Default `None` -- kein bestehender Aufrufer musste sich ändern). Ein
transientes, nie persistiertes `AppUser(role=role, employee_id=employee_id)`-Objekt trägt beide
Werte in `list_tasks_for_user()` hinein. Bewusst KEIN einheitlicher 4-Parameter-`query_fn` für
alle 18 Quellen (hätte 17 unbeteiligte Funktionssignaturen um einen ungenutzten Parameter
erweitert) -- die Dispatch-Schleife behandelt "tasks" stattdessen als einzigen, klar
kommentierten Sonderfall. `_task_row()` liest seither ein Dict (`task_to_dict()`-Schema) statt
eines ORM-`Task`-Objekts.

**Der verlangte Angriffstest** (vier neue Tests in `tests/test_v270_office_search.py`, Kernfunktions-
UND echter Router-Test): ein Büro-Konto findet über die Suche die eigenen und die empfängerlosen
Aufgaben, nie die eines Kollegen -- auch nicht ohne eigene Mitarbeiterverknüpfung (dann nur die
empfängerlosen). Admin findet alle. Ein Monteur findet über die Büro-Suche weiterhin gar
nichts -- unverändert bereits über die Registry-Rollenprüfung/`require_role()` am Router
abgedeckt, kein neuer Test dafür nötig. Volle Suite: 1466 Tests grün.

## 1.4.3 – Änderung am Aufgabenmodul: empfängerlose Aufgaben für ganz Büro sichtbar, Übernehmen/Zurückgeben

Bug-Meldung aus 1.4.2 ("eine unassigned Aufgabe ist für Nicht-Admin-Büro-Konten unsichtbar") war
Anlass für eine erst per Befund, dann per bestätigtem Bauauftrag umgesetzte Änderung am
Aufgabenmodul selbst -- nicht nur an der Betriebsmittelverwaltung.

**Zentrale Rollenbestimmung, wie ausdrücklich verlangt.** Neues `has_role(user, *roles) -> bool`
(`app/permissions.py`) ist jetzt die EINE Quelle für "hat diese Person eine dieser Rollen" --
`require_role()`s interne Prüfung UND der Jinja-Global `can()` (`app/routers/pages.py`) delegieren
beide daran, statt je einen eigenen `user.role in (...)`-Vergleich zu tragen. Bewusst vermieden:
genau das Muster, das bei `build_din5008_header_block()`s Vorgängern zu drei divergierenden
Varianten geführt hat (siehe CLAUDE.md "Kopfbereich").

**Neue Sichtbarkeitsregel, eine einzige Stelle.** `app/tasks.py::list_tasks_for_user(db, user, ...)`
ist jetzt der ausschließliche Einstiegspunkt für jede Task-Sichtbarkeitsentscheidung -- ersetzt die
bisherige, inline im Router sitzende `user.role != "admin"`-Prüfung. `list_tasks()` bekommt dafür
einen neuen `unassigned_only: bool`-Parameter (Vorrang vor `employee_id`, filtert
`Task.assigned_employee_id.is_(None)`). Admin bleibt frei wählbar; ein Büro-Konto ist ohne
`unassigned_only` weiterhin zwingend auf die eigene `employee_id` festgelegt (Kollegen-Aufgaben
bleiben unsichtbar, unverändert); mit `unassigned_only=True` sieht JEDES Büro-/Admin-Konto den
gemeinsamen Eingang, unabhängig von der eigenen `employee_id` -- das Sehen selbst braucht dafür
keine Mitarbeiter-Verknüpfung (die braucht erst das Übernehmen, siehe unten). `GET /api/tasks`
bekommt einen neuen Query-Parameter `unassigned_only` und delegiert vollständig an
`list_tasks_for_user()` -- geprüft und bestätigt: Liste (`/tasks`), Dashboard-Widget und jede
Zählung laufen ausschließlich über diesen einen Endpunkt, es gibt keine zweite SQL-Filterstelle.

**"Übernehmen" weist fest zu, kein dritter Zustand.** Neue Funktionen `claim_task()`/
`release_task()` (`app/tasks.py`) und Endpunkte `POST /api/tasks/{id}/claim`/`.../release` (beide
hinter dem bestehenden `require_role(ROLE_ADMIN, ROLE_OFFICE)`-Gate). Übernehmen setzt
`assigned_employee_id` auf die eigene, verknüpfte `employee_id` -- exakt dasselbe Feld wie jede
andere Zuweisung, keine zweite Zuweisungsart. Fehlt die Mitarbeiter-Verknüpfung, eine klare
Meldung (400), kein stiller Fehler -- derselbe Fall wie beim Monteur ohne `employee_id` an anderer
Stelle. Eine bereits vergebene Aufgabe lässt sich nicht "übernehmen" (400, verhindert ein
versehentliches Stehlen einer Kollegen-Aufgabe) -- eine neue, bewusste Sperre, die die bestehende
PUT-Zuweisung nicht kennt. "Zurück in den Büro-Eingang" (`release_task()`) setzt
`assigned_employee_id` zurück auf `NULL`, bewusst OHNE Eigentümerschafts-Prüfung -- konsistent mit
der bereits bestehenden, dokumentierten Lücke bei PUT/DELETE/archive/unarchive auf Aufgaben (siehe
CLAUDE.md "Aufgabe"), keine isolierte, inkonsistente Verschärfung nur hier.

**Dashboard und Board.** Neues, opt-in Dashboard-Widget "Offene Büro-Aufgaben"
(`open_office_tasks`, `app/templates/dashboard.html`, Muster `due_maintenance`/`due_assets` --
NICHT im Standard-Layout) zeigt `GET /api/tasks?unassigned_only=true` mit einem
"Übernehmen"-Button je Zeile, der nach Erfolg gezielt nur diesen einen Widget-Container neu
rendert. "Meine Aufgaben" bleibt unverändert (zeigt weiterhin ausschließlich die eigenen
zugewiesenen Aufgaben, niemals unassigned). `/tasks` bekommt einen neuen Button "Zurück in den
Büro-Eingang" im Editor, sichtbar nur bei bereits zugewiesener Aufgabe -- der Board-Fetch selbst
(`loadTasks()`) bleibt unverändert "nur eigene" für Nicht-Admin; ein Monteur sieht weiterhin
ausschließlich seine eigenen Aufgaben -- die gesamte `/api/tasks*`-Familie bleibt Büro/Admin-only,
unverändert seit "Rechtekonzept".

**Der verlangte Angriffstest, bestätigt (`tests/test_v279_task_visibility.py`, 21 neue Tests).**
Ein Monteur bekommt über `GET /api/tasks?unassigned_only=true` UND über `POST .../claim`/`.../release`
-- auch mit einer geratenen, nicht existierenden Aufgaben-ID -- durchgängig 403, bevor irgendeine
Geschäftslogik läuft (die primäre Absicherung ist bereits `require_role()`). Ein Büro-Konto sieht
über `unassigned_only=true` die empfängerlosen Aufgaben, aber nicht die persönlich zugewiesene
Aufgabe eines Kollegen -- weder im Standardfall noch mit manipuliertem `employee_id`-Parameter.
Volle Suite: 1462 Tests grün.

**Bewusst unadressiert, transparent vermerkt:** die in derselben Untersuchung gefundene,
unabhängige Lücke in der Büro-Suche (`app/search.py::_search_tasks()` hat keine
Mitarbeiter-Filterung -- jedes Büro-/Admin-Konto findet über `/suche` jede Aufgabe per Titel,
unabhängig von der Zuweisung) ist NICHT Teil dieser Änderung -- der aktuelle Auftrag betraf
ausdrücklich nur `GET /api/tasks`/Dashboard/Übernehmen-Zurückgeben. Bleibt als offener Punkt
vermerkt, bis explizit angefragt.

## 1.4.2 – Betriebsmittelverwaltung: Fälligkeitsberechnung, Erinnerung, Büro-Suche, Dokumentenablage

Vier reine Bürofunktions-Ergänzungen zur Betriebsmittelverwaltung (1.4.0/1.4.1) -- kein Monteur
betroffen, siehe die beiden abschließenden Angriffstests unten.

**Punkt 1 -- automatische Fälligkeitsberechnung, mit der entscheidenden Feinheit.**
`OperationalAssetInspection.next_due_date` wird bei jedem Anlegen/Bearbeiten automatisch berechnet
(`_compute_next_due_date()`, `app/operational_assets.py`), sobald `interval_months` gesetzt ist --
`Anschaffungsdatum (bzw. das zuletzt tatsächliche Prüfdatum) + Intervall − 1 Tag`. Die erste
Fälligkeit beim Anlegen mit Anschaffungsdatum ist deshalb `Anschaffungsdatum + Intervall − 1 Tag`,
nie das Anschaffungsdatum selbst. **Entscheidend**: die Basis ist immer `last_inspection_date`,
falls vorhanden, sonst das Anschaffungsdatum -- NIE kumulativ vom Anschaffungsdatum fortgeschrieben.
Verspätet sich eine Prüfung, verschiebt sich der gesamte Rhythmus mit, statt auseinanderzudriften
-- mit einem eigenen Test belegt, der eine deutlich verspätete Prüfung gegen die (falsche)
kumulative Berechnung abgrenzt. Eine Prüffrist ohne Intervall (einmalige Prüfung) bleibt
vollständig manuell, unverändert.

**Punkt 2 -- Meldung und Aufgabe vier Wochen vorher, On-Demand wie bei den Wartungsverträgen.**
Neue `check_due_asset_inspections_and_create_reminders()`, ausgelöst per Fire-and-Forget-Aufruf
(`POST /api/operational-assets/check-due`) beim Laden der Stammdaten-Betriebsmittelliste -- kein
Hintergrundjob, derselbe Auslöser-Mechanismus wie `check_due_contracts_and_create_reminders()`.
Erinnert per `create_task()` (Aufgabe **unassigned**, "allgemein ans Büro" -- es gibt kein Feld für
einen Zuständigen je Betriebsmittel), idempotent über einen neuen Stempel
`OperationalAssetInspection.last_reminder_due_date` (dasselbe Muster wie bei `MaintenanceContract`,
ohne expliziten Reset nötig, da eine Neuberechnung von `next_due_date` den Stempel automatisch
veralten lässt). Erscheint ausschließlich im bestehenden "Fällige Prüffristen"-Panel und im
Aufgabenbereich -- kein zweites Dashboard-Widget. **Transparent festgehalten**: eine unassigned
Aufgabe ist für Nicht-Admin-Büro-Konten nach dem heutigen Task-System nicht sichtbar (`GET
/api/tasks` filtert für jeden Nicht-Admin auf die eigene `employee_id`) -- eine bereits bestehende,
allgemeine Einschränkung des Aufgabenmoduls, keine für dieses Feature neu eingeführte Lücke.

**Punkt 3 -- Betriebsmittel in der Büro-Suche**, 18. Registry-Eintrag (`app/search.py`,
Mindestrolle Büro, gated auf das Modul "betriebsmittel"). Durchsucht Bezeichnung/Art/Hersteller/
Modell/Kennzeichen/Artikelnummer, führt auf `/betriebsmittel/{id}`. Ein ressourcenverknüpftes Asset
(Kran, Fahrzeug, Anhänger) trägt seine eigenen Identitätsfelder als `NULL` (Live-Auflösung, siehe
1.4.0) -- die neue Quelle joint deshalb zusätzlich `OperationalResource` und nutzt denselben
`resolve_asset_identity()`-Helfer wie die Betriebsmittelseite selbst, sonst wäre jedes
ressourcenverknüpfte Asset unauffindbar gewesen. Der Registry-Vollständigkeitstest
(`EXPECTED_OFFICE_SEARCH_KEYS`) deckt den neuen Eintrag ab.

**Punkt 4 -- Dokumentenablage am Betriebsmittel**, für Anschaffungsrechnung, Leasingvertrag u. Ä.
Neue Tabelle `OperationalAssetDocument` (mehrere unabhängige Dateien je Betriebsmittel, anders als
die bestehende 1:1-Ablage je Prüffrist) plus `save_document()` in `app/operational_asset_documents.py`
-- gleicher Speicherordner/`ERP_DATA_DIR`-Anbindung wie die bestehende Prüffristen-Ablage, kein
zweiter Ordner. `document_type` läuft über eine neue, schlanke, self-seedende Optionsgruppe
(`operational_asset_document_types`: Anschaffungsrechnung, Leasingvertrag, Sonstiges) -- bewusst
NICHT die schwergewichtige `DocumentCategory`-Stammdatentabelle aus 1.3.62: deren gesamter Zweck
(`is_sensitive`/`is_field_visible`, zwei Schlösser gegen "sensible Kategorie für Monteure sichtbar")
ist hier gegenstandslos, da Betriebsmittel-Dokumente ausnahmslos Büro/Admin-only sind, ohne jede
Monteur-sichtbare Stufe. Löschen räumt die Datei über ein `before_delete`-Event von der Platte auf
(Muster `app/roof_areas.py`), feuert für jeden ORM-Löschweg, auch kaskadiert beim Löschen des
ganzen Betriebsmittels. Drei neue, ausnahmslos Büro/Admin-only-Endpunkte (Upload/Ansehen/Löschen).

**Abschließender Angriffstest, wie verlangt**: ein Monteur (`field`) erreicht keinen der drei
Dokumentenablage-Endpunkte -- auch nicht über eine geratene, fortlaufende Datei-ID (`require_role()`
schließt die Rolle strukturell aus, unabhängig davon, ob die ID existiert). Die Büro-Suche liefert
einem Monteur über den echten Router (`GET /api/search`) durchgängig 403, nie ein Betriebsmittel.
Beide Fälle in `tests/test_v278_operational_assets_erweiterungen.py` belegt, 0 "durchgelassen".

Migration `ed896599a211` (neue Tabelle `operational_asset_documents`, neue, nullable Spalte
`operational_asset_inspections.last_reminder_due_date`) gegen die echte, lokale Datenbank
angewendet. Volle Suite: 1441 Tests grün.

## 1.4.1 – Betriebsmittelverwaltung, Stufe 2 (QR-Code-Etikett, rollenabhängige Ansicht)

Zweite Etappe des dreistufigen Betriebsmittel-Umbaus (siehe 1.4.0) -- Stufe 3 (Betriebsmittel im
Bericht) folgt weiterhin erst nach Rückmeldung. Vier Teile, wie vorgegeben umgesetzt.

**Zwei neue Felder, Büro/Admin-only**: `article_number`/`product_url` auf `OperationalAsset`
(neue, nullable Spalten -- Beschaffung, kein Monteur sieht sie an irgendeiner Stelle).
`product_url` wird per Pydantic-`field_validator` geprüft -- nur `http`/`https` mit gültigem
Host, alles andere (`javascript:`, bloßer Text, `ftp://`) wird mit 422 abgelehnt, bevor es je als
anklickbarer Link ausgegeben werden könnte. Auf der Betriebsmittelseite als Link mit
`target="_blank" rel="noopener"` dargestellt.

**Bewusste Prämissen-Korrektur, transparent gemeldet**: Punkt 3 der Anfrage nennt
"Bedienungshinweise" als Bestandteil der reduzierten Monteursansicht, ohne das explizit als
neues Feld in Punkt 1 aufzuführen. Da das bestehende `notes`-Feld beliebige interne/
Beschaffungsvermerke tragen kann (in der echten Nutzung z. B. Einkaufsdetails, Rabatte), wäre es
falsch gewesen, es einfach für Monteure freizugeben. Stattdessen ein drittes, neues Feld
`usage_notes` ("Bedienungshinweise") -- das EINZIGE Freitextfeld, das die reduzierte Ansicht
zeigt, unabhängig davon, was in `notes` steht.

**QR-Code, wiederverwendete Bibliothek statt neuer Abhängigkeit**: `qrcode[pil]` ist bereits seit
1.3.34 Projektabhängigkeit (Zwei-Faktor-Setup, `app/two_factor.py`) -- BSD-3-Clause, siehe dort für
die Lizenzprüfung. Neues, eigenständiges `app/qr_codes.py::qr_code_png_bytes()` statt einer
Erweiterung von `two_factor.py`: derselbe fünfzeilige Erzeugungscode wäre trivial zu duplizieren
gewesen, aber ein sicherheitskritisches Modul für einen zweiten, fachlich unabhängigen
Anwendungsfall anzufassen wäre unnötiges Risiko gewesen. Neuer Endpunkt
`GET /api/operational-assets/{id}/qr-code.png` (Büro/Admin-only -- Drucken ist ein Büro-Vorgang,
das Scannen des fertigen Etiketts dagegen nicht) liefert den Code als PNG, kodiert die
VOLLSTÄNDIGE URL inklusive Domain.

**Domain nie hartkodiert**: neues, optionales Feld `GeneralSettings.public_base_url`
(Einstellungen → Unternehmensstammdaten, "Öffentliche Adresse") -- wenn gesetzt, wird es
verwendet, sonst fällt der Endpunkt auf `request.base_url` zurück (die tatsächliche
Aufrufadresse). Kein hartkodierter Wert, der sonst auf `localhost`/`127.0.0.1` zeigen würde,
sobald die Installation nicht lokal aufgerufen wird -- und ein Override für den Fall, dass ein
künftiger Reverse-Proxy Schema/Host nicht korrekt durchreicht. Ebenfalls per `field_validator`
auf http(s) beschränkt.

**Rollenabhängige Seite, dasselbe Muster wie `time_tracking_page()`**: der QR-Code führt jeden --
Büro wie Monteur -- auf `/betriebsmittel/{id}`, aber die Seite rendert für `field` die neue,
reduzierte `operational_asset_field.html` (Bezeichnung/Art/Hersteller/Modell/Bedienungshinweise)
statt der vollen `operational_asset.html` -- die Weiche hängt an der Rolle, nicht am Weg
(QR-Code oder von Hand eingetippte Büro-URL liefern serverseitig identisch dasselbe). Neues
`OperationalAssetFieldOut`-Schema für `GET /api/operational-assets/{id}` (Union-Response-Model,
Muster `OrderOut | OrderFieldAccessOut`) -- die Antwort wird im Router explizit als validiertes
Pydantic-Modell zurückgegeben, damit die Union-Deklaration nie versehentlich das jeweils andere
Schema für die Serialisierung wählt. Per echtem, CDP-gesteuertem Headless-Chrome-Test gegen eine
isolierte Testinstanz verifiziert (zwei echte Testkonten, Rolle Büro und Monteur): die
Monteursansicht zeigt nachweislich weder Kosten noch Artikelnummer/Produktlink noch die interne
`notes`-Notiz, die API-Antwort enthält exakt die sechs erlaubten Schlüssel, der QR-Endpunkt
liefert für `field` 403. Zusätzlich per `Page.printToPDF` geprüft: das gedruckte Etikett zeigt
ausschließlich QR-Code und Bezeichnung, keine Sidebar/Navigation (dabei ein eigener CSS-Fehler
im ersten Entwurf gefunden und behoben -- `body>*:not(#printLabel)` griff nicht, weil
`#printLabel` kein direktes Kind von `<body>` war, sondern tief in `.app-layout` verschachtelt;
korrigiert durch `.app-layout{display:none!important}` plus einen Sibling-`<div>` außerhalb
davon).

14 neue Tests (`tests/test_v277_operational_assets_stufe2.py`), volle Suite weiterhin grün
(1424/1424). Migration `ccb5c4c0915b` (vier neue, nullable Spalten -- `article_number`/
`product_url`/`usage_notes` auf `operational_assets`, `public_base_url` auf `general_settings`).

## 1.4.0 – Betriebsmittelverwaltung, Stufe 1 (neues Modul "betriebsmittel")

Erstes echtes neues Modul seit Version 1.3.0 (daher der Minor-Sprung, Regel 8) -- Befund zuvor
separat berichtet (kein Code), dann fünf vom Nutzer bestätigte Bau-Entscheidungen umgesetzt.
Dreistufig angelegt: diese Version liefert ausschließlich **Stufe 1** (Datenmodell mit
Ressourcenbezug, Prüffristen, Kosten, Stammdatenpflege, Modulschalter) -- QR-Code/rollenabhängige
Ansicht (Stufe 2) und Betriebsmittel im Bericht (Stufe 3) folgen erst nach Rückmeldung.

**Modulschalter zuerst, wie ausdrücklich verlangt** ("bevor irgendein Endpunkt gebaut wird"):
`OPTIONAL_MODULES["betriebsmittel"] = "Betriebsmittelverwaltung"` (`app/modules.py`) war der
erste Codeschritt dieser Version, jeder Endpunkt in `app/routers/operational_assets.py` prüft
`is_module_enabled()` von Anfang an (403, Muster `maintenance_contracts.py`).

**Eigene Inventarschicht statt Erweiterung von `OperationalResource`** -- die zentrale
Bau-Entscheidung: `OperationalAsset` trägt ein optionales `resource_id` (unique -- höchstens
ein Betriebsmittel je Ressource, verhindert Doppelerfassung auf Datenbankebene). Ein Kran ist
ein Betriebsmittel MIT Ressourcenbezug (bleibt über den unveränderten `Team`/`TeamResource`/
`PlanningSlot`-Weg in der Plantafel disponierbar), eine Leiter eins OHNE. Ist ein Asset
verknüpft, werden Name/Typ/Hersteller/Modell/Kennzeichen bei JEDEM Lesezugriff LIVE von der
Ressource aufgelöst (`app/operational_assets.py::asset_to_dict()`) -- niemals als eigene Kopie
gespeichert, das ist der eigentliche Schutz gegen Namensdivergenz zwischen beiden Tabellen. Ist
kein Ressourcenbezug gewählt, ist die Bezeichnung Pflicht (Pydantic-Validator in
`OperationalAssetCreate`, nicht per DB-Constraint, da das Feld im verknüpften Fall NULL bleiben
muss). **Ausdrückliche Warnung in `app/models.py`s Klassendocstring** (auf Wunsch des Nutzers
festgehalten): `OperationalResource` und `OperationalAsset` dürfen künftig NICHT zu einer
einzigen Tabelle zusammengeführt werden -- die Plantafel-Disposition referenziert ausschließlich
`operational_resources.id` und kennt `OperationalAsset` überhaupt nicht, eine Zusammenführung
würde diese Fremdschlüssel brechen.

**Fälligkeitslogik: Muster übernommen, Code bewusst nicht wiederverwendet.** Geprüft, ob
`MaintenanceContractItem`s `_is_item_due()`/`_is_item_overdue()` (`app/maintenance_contracts.py`)
direkt nutzbar sind -- nein: `_is_item_overdue()` ist an die saisonalen `MaintenanceWindow`-Fenster
der Wartungsverträge gekoppelt, was für eine turnusmäßige Geräteprüfung (z. B. "TÜV alle 12
Monate") fachlich nicht passt. Neue, eigene Funktionen `is_inspection_due()`/
`is_inspection_overdue()` (`app/operational_assets.py`) übernehmen nur das PATTERN (Vorlaufzeit-
gesteuertes `is_due`, eigenständiges `is_overdue` für bereits verstrichene Fristen) --
dieselbe "gleiches Muster, dokumentierte Trennung"-Vorgabe wie bei den Projekt-Pipeline-Spalten
(CLAUDE.md). Eigene Singleton-Einstellung `OperationalAssetSettings.reminder_lead_days`
(Default 30, unabhängig von `MaintenanceSettings`).

**Datenmodell**: `OperationalAsset` (Identität bei fehlendem Ressourcenbezug, Notizen,
Anschaffungsdatum/-kosten, `recurring_cost_per_month`, Status), `OperationalAssetInspection`
(Art/Intervall/letzte Prüfung/nächste Fälligkeit/Prüfer/Dokument/Notizen, cascade beim Löschen
des Assets), `OperationalAssetSettings` (Singleton). Neue, self-seedende Optionsgruppe
`operational_asset_inspection_types` (TÜV/HU, Leiterprüfung, UVV-Prüfung, Wartung, Sonstige
Prüfung) -- `asset_type` selbst nutzt bewusst dieselbe, bereits bestehende Gruppe
`resource_types` wie `OperationalResource`, keine doppelte Typliste. Migration `5917bb099776`
legt alle drei Tabellen an UND backfillt für jede der 5 real bestehenden `OperationalResource`-
Zeilen ein verknüpftes `OperationalAsset` (nur `resource_id` gesetzt) -- ohne diesen Schritt
wären die 5 Bestandsressourcen aus der Stammdaten-Übersicht verschwunden, sobald diese auf die
Asset-Ansicht umgestellt wird. Gegen die echte, migrierte Datenbank verifiziert: alle 5 Zeilen
korrekt verknüpft.

**Dokument-Ablage für Prüffristen** (`app/operational_asset_documents.py`, Muster
`app/roof_area_sketches.py`): eigener `data/operational_asset_documents/`-Ordner (neue
Umgebungsvariable `DACHKONZEPTE_OPERATIONAL_ASSET_FILE_ROOT`, in `.env.example` ergänzt), PDF
zusätzlich zu Bildern erlaubt (Prüfprotokolle), 10 MB-Grenze.

**Kosten monatsnormalisiert statt Intervall+Betrag** (`recurring_cost_per_month`) -- bewusste
Vorentscheidung für die vom Nutzer bereits angekündigte künftige Gesamtkostenübersicht: eine
solche Auswertung kann dadurch trivial über alle Assets summieren, ohne zuvor unterschiedliche
Intervalle umrechnen zu müssen. In CLAUDE.md als Merkposten für diese künftige Auswertung
festgehalten.

**"Fuhrpark & Maschinen" wird zur Weiche, nicht zu zwei Parallelpflegen** -- dieselbe Weiche wie
bei Mitarbeitern in 1.3.26: EIN Stammdaten-Navigationsknopf (`master_data.html`, umbenannt auf
"Betriebsmittel"), dessen Inhalt live nach Modulzustand umschaltet. Modul an: die reiche
Asset-Liste (`GET /api/operational-assets`, eigener `.catch(()=>[])`-abgesicherter Fetch-Zweig
in `load()`, da dieser Endpunkt modulgated ist -- der einzige unter den vielen unbedingten
Fetches dieser Datei, der 403 liefern könnte). Modul aus: unverändert die alte, rohe
Ressourcenliste (`GET /api/resources`, weiterhin ungegatet, Kern-ERP) -- die 5 Bestandsressourcen
bleiben dadurch auch bei deaktiviertem Modul erreichbar. Anlegen führt über
`master_data_form.html`s neue `assetForm()` (Ressourcenbezug-Umschalter, bereits verknüpfte
Ressourcen werden aus der Auswahl ausgeschlossen), Bearbeiten bewusst NICHT über dasselbe
Formular, sondern direkt über die neue, eigene, reichere Detailseite `GET /betriebsmittel/{id}`
(`app/templates/operational_asset.html`, Muster `maintenance_contract.html`) -- Regel-10-
Präzedenzfall "eigene Detailseite statt generischem Formular, wenn ein Bereich das
rechtfertigt" (wie Property/Wartungsvertrag), Anlegen bounct nach dem Speichern sofort dorthin.
Die Detailseite verlinkt bei verknüpfter Ressource zusätzlich auf deren eigene Stammdatenseite
(`/master-data/resources/{id}/edit`), damit auch die reinen Ressourcenfelder (Kennzeichen,
Hersteller bei Fuhrpark) erreichbar bleiben.

**Dashboard-Widget "Fällige Betriebsmittelfristen"** (`due_assets`, Muster `due_maintenance`,
`app/templates/dashboard.html`) und ein "Fällige Prüffristen"-Panel oben auf der Stammdaten-
Betriebsmittelliste (nur bei aktivem Modul) decken die verlangte Sichtbarkeit auf einer
Übersicht UND im Dashboard ab, ohne eine dritte, eigene Seite dafür zu bauen.

**Einstellungen** → System → "Betriebsmittel" (neuer Abschnitt, `settings.html`, Muster
"Wartungen"): einziges konfigurierbares Feld ist die Vorlaufzeit, mit Deaktiviert-Hinweis wie
beim Wartungsmodul.

**Transparenz-Hinweis zum Opt-out-Standard, wie bereits im Befund angekündigt**: ohne die
`EnabledModule`-Zeile gilt ein neuer Registry-Eintrag sofort als aktiv (`is_module_enabled()`s
Opt-out-Philosophie, `app/modules.py`) -- das neue Modul war ab dem Moment der Migration auf
jeder Installation ohne explizite Zeile live, bis ein Admin es unter Einstellungen → Module
bewusst abschaltet. Kein Sonderfall für diese Version, aber wie beim allerersten Modul (1.1.0)
explizit erwähnt, damit es niemanden überrascht.

Per echtem, CDP-gesteuertem Headless-Chrome gegen eine isolierte, temporäre SQLite-Instanz
verifiziert (Muster 1.3.73/1.3.74): Stammdatenliste, Anlegen → Bounce zur Detailseite, Prüffrist
mit überfälligem Datum anlegen → Badges/"Fällige Prüffristen"-Panel erscheinen korrekt,
Einstellungen-Abschnitt zeigt den geladenen Wert, und -- direkt in der Datenbank deaktiviert --
der vollständige Rückfall auf die alte Fuhrpark-Ansicht samt funktionierendem 403 auf der API.
1410 Tests grün (17 neu, `tests/test_v276_operational_assets.py`: Doppelerfassungs-Schutz,
Live-Auflösung, Name-Pflicht-Validator, Fälligkeits-Aggregation über mehrere Prüffristen,
Migrations-Backfill isoliert, Rollen- und Modul-Gate über echte Router).

## 1.3.74 – Umbau der Projekt-Detailseite (die Projektmappe)

Zweiter Teil des vom Nutzer angefragten Umbaus (Befund zuvor separat berichtet, keine
Codeänderung) -- `app/templates/project_folder.html` vollständig neu gebaut. Ziel: die linke,
sprungmarken-basierte Bereichsnavigation wird zu einer echten, waagerechten Reiterleiste, das
Hauptfeld nutzt die volle Breite, Vorbild war das vom Nutzer gezeigte LB.tec-Layout.

Fünf vorab bestätigte Entscheidungen, jede umgesetzt:

1. **Acht echte Reiter** statt neun Sprungmarken (Kennzahlen entfällt als Reiter, siehe Punkt 2):
   Übersicht (frühere "Projektinformationen"), Dateien, Angebote, Aufträge, Rechnungen,
   Arbeitsvorbereitung, Zeiten, Historie -- mit denselben Zählungen wie bisher an der linken
   Navigation (Dateien/Angebote/Aufträge/Rechnungen/Zeiten), jetzt am jeweiligen Reiter. Die
   Reiter-Schlüssel sind bewusst identisch mit den bisherigen Sprungmarken-IDs (`sec-info`,
   `sec-files`, `sec-quotes`, `sec-orders`, `sec-invoices`, `sec-workprep`, `sec-times`,
   `sec-history`) -- die drei bestehenden externen Tiefenverweise (`projects.html`s
   Kontextmenü-Link auf `#sec-quotes`, `order.html`/`work_preparation.html`s Breadcrumb-Link auf
   `#sec-orders`) mussten dadurch nicht geändert werden, sie aktivieren jetzt automatisch den
   richtigen Reiter statt zu einer Sprungmarke zu scrollen.
2. **Kennzahlen als fester, immer sichtbarer Block über den Reitern**, kein eigener Reiter --
   entgegen dem eigenen Befund-Vorschlag (Zusammenlegung mit "Übersicht"), auf ausdrücklichen
   Nutzerwunsch. Schlank gehalten: die frühere dritte KPI-Gruppe "Dokumente" (Angebote/Aufträge/
   Rechnungen-Zählung) entfällt, weil dieselben Zahlen jetzt an den Reitern stehen -- keine
   dritte, redundante Stelle für dieselbe Zahl (vorher: Kopf-Badges UND Kennzahlen-Dashboard UND
   Seitenleiste zeigten dieselben vier Zahlen dreifach). Übrig bleiben sechs kompakte Kacheln
   (Finanzen: Projektwert/Abgerechnet/Noch offen; Stunden: Soll/Ist/Abweichung), wiederverwendet
   über die bereits bestehenden `.metric`/`.grid`-Klassen (dieselben, die auch die
   Zeiterfassungs-Sektion nutzt) statt einer dritten, eigenen Kachel-Optik -- die alte
   `.kpi-groups`/`.kpi-group`-CSS (nur für diese eine Stelle gebaut) entfällt vollständig. Per
   echtem Browser-Test (siehe unten) nachgemessen: Kopf + Kennzahlen-Streifen + Reiterleiste
   zusammen 309px bei 855px Ansichtsfensterhöhe (~36 %) -- deutlich unter der Hälfte.
3. **"Übersicht" ist der Reiter beim Öffnen**, der aktive Reiter steht im URL-Hash
   (`#sec-quotes` usw.) -- adaptiert aus dem bereits etablierten Muster in `settings.html`
   (`showSettingsSection()`/`history.replaceState`/`hashchange`-Listener mit einer validierten
   Schlüsselliste), nicht neu erfunden, wie ausdrücklich verlangt geprüft. `master_data.html`s
   älteres, einfacheres `viewFromHash()` wurde ebenfalls geprüft, `settings.html`s Fassung passt
   aber besser (Bookmark-/Reload-Fähigkeit war dort von Anfang an mitgedacht).
4. **Ein einziger permanenter Kopf-Button: "Projektmappe bearbeiten"**, nicht "+ Angebot" wie in
   der eigenen Befund-Vermutung. Gegen die echte, lokale Datenbank geprüft statt nur vermutet: 6
   von 8 Projekten tragen bereits den Status "beauftragt" (die Angebotsphase ist für die meiste
   Projektlaufzeit bereits abgeschlossen), 6 von 8 haben genau ein Angebot -- die Projektmappe
   wird also überwiegend zum Nachsehen (Dateien, Aufträge, Rechnungen, Zeiten) statt zum Anlegen
   eines weiteren Angebots geöffnet. "+ Angebot" verschwindet dabei nicht (bleibt unverändert in
   den Reitern Übersicht UND Angebote erhalten, wie zuvor doppelt vorhanden) -- nur die
   permanente Kopf-Position wechselt. Der Rest (Kopieren, Als Mustervorgang speichern,
   Wartungsvertrag erstellen, Archivieren/Entarchivieren, Löschen) wandert ins Drei-Punkte-Menü,
   exakt nach dem in `projects.html` etablierten Muster (1.3.72/1.3.73: `.menu`/`.menu-btn`/
   `toggleMenu()`/`positionMenu()`/`closeAllMenus()`, `position:fixed`, Escape/Scroll/Resize
   schließen das Menü) -- keine zweite, eigene Menü-Implementierung.
5. **Bereichsinhalte unverändert, nur ihre Erreichbarkeit ändert sich**: Upload-Zone mit
   Drag&Drop, Kategorie-/Unterordner-Filterkarten, Suche, alle Tabellen, alle Modals (Projekt
   bearbeiten, Dateimetadaten bearbeiten, Wartungsvertrag erstellen) sind eins zu eins aus dem
   bisherigen Template übernommen, nur die Collapse-Buttons (▾/▸) und ihr `localStorage`-Zustand
   (`dachkonzepte_project_folder_collapsed_sections`) entfallen -- bei genau einem sichtbaren
   Bereich zur selben Zeit ist ein Ein-/Ausklappen wirkungslos geworden, keine Funktion, die noch
   etwas leistet. **Eager statt lazy Laden**: der bestehende einzelne `Promise.all(...)`-Aufruf in
   `load()` bleibt unverändert -- bei 8 Bestandsprojekten mit insgesamt einstelligen bis
   niedrigen zweistelligen Zeilenzahlen (Dateien/Angebote/Aufträge/Rechnungen/Zeiteinträge/
   Historie je Projekt) gäbe es keinen messbaren Ladezeitgewinn durch Reiterwechsel-Nachladen,
   nur zusätzliche Komplexität (Ladezustand je Reiter, doppelte Fehlerbehandlung) ohne fachlichen
   Nutzen -- Reiterwechsel schaltet ausschließlich `display:none`/`display:block` um.

**Rollen-Check bestätigt, nicht nur angenommen**: `/projects/{project_id}` (Seitenroute,
`app/routers/pages.py`) UND der komplette `app/routers/projects.py`-Router (`_role_dep`) tragen
unverändert `require_role(ROLE_ADMIN, ROLE_OFFICE)` -- dieser Umbau rührt daran nichts an, ein
Monteur bleibt vollständig ausgesperrt (Seite UND API). Per echtem, gegen eine isolierte,
temporäre Testinstanz gesteuertem Headless-Chrome (CDP, Muster 1.3.73) verifiziert, nicht nur
behauptet: Standardansicht zeigt "Übersicht" aktiv, Kennzahlen-Streifen kompakt (105px) und
Kopfbereich (141px) und Reiterleiste (39px) zusammen weit unter der halben Bildschirmhöhe;
Klick auf "Dateien" schaltet den Reiter tatsächlich um und setzt den URL-Hash; ein Neuladen mit
`#sec-quotes` in der Adresse aktiviert direkt den Angebote-Reiter (Tiefenverweis-Fähigkeit
bestätigt); das Drei-Punkte-Menü öffnet vollständig innerhalb des Ansichtsfensters mit allen
fünf Einträgen; keine JavaScript-Fehler beim Laden oder bei den Interaktionen.

## 1.3.73 – Kontextmenü der Projektliste: Beschneidung durch overflow:auto behoben

Gemeldeter Fehler an 1.3.72: das Drei-Punkte-Kontextmenü klappte innerhalb des seit 1.3.9
seitlich scrollbaren `.wrap`-Tabellencontainers (`overflow:auto`) auf -- dessen `overflow`
beschneidet nicht nur horizontal, sondern auch vertikal, was das Menü am unteren Rand abschnitt.

Geprüft, ob sich dasselbe Muster anderswo im Projekt schon findet, statt eine zweite Lösung zu
erfinden: der einzige bestehende "Klick-öffnet-ein-Menü"-Baustein ist der Kontoknopf in
`_topbar.html` -- der sitzt aber nicht in einem overflow-Container, sein einfaches
`position:absolute` war für dieses Problem nie geprüft und taugt hier nicht als Vorbild.

Gewählte Lösung: `.menu` wechselt von `position:absolute` (relativ zur Zelle) auf
`position:fixed` (relativ zum Ansichtsfenster) -- ohne das Element im DOM zu verschieben. Das
funktioniert, weil ein `position:fixed`-Element sein Containing Block beim Ansichtsfenster hat
und dadurch NICHT vom `overflow` eines Vorfahren beschnitten wird, solange kein Vorfahre
`transform`/`filter`/`contain` trägt -- geprüft: `.app-content`/`main`/`.card` tun das nicht,
nur die (unbeteiligte) Off-Canvas-Sidebar hat ein `transform`, aber als Geschwister-Element,
nicht als Vorfahre der Tabelle. Position wird jetzt per JS (`positionMenu()`) aus
`getBoundingClientRect()` des Drei-Punkte-Knopfs berechnet: rechtsbündig zum Knopf (mit
Rand-Klemmung), unterhalb des Knopfs -- klappt aber nach OBEN, wenn darunter nicht genug Platz im
Ansichtsfenster ist. Ein neuer, globaler Scroll-Listener (Capture-Phase, da Scroll-Events nicht
bubbeln) schließt ein offenes Menü, sobald irgendetwas gescrollt wird (die Liste selbst oder die
Seite) -- ein fixed-positioniertes Menü folgt dem Knopf sonst nicht mit und stünde an der
falschen Stelle.

**Per echtem, per Chrome-DevTools-Protocol gesteuertem Headless-Browser verifiziert** (kein
Test-Framework wie Playwright im Projekt vorhanden, deshalb ein eigener, kleiner
PowerShell/CDP-Treiber gegen eine isolierte Testinstanz mit 25 Testprojekten): Menü an der
letzten Zeile klappt nachweislich nach oben und liegt vollständig innerhalb des
Ansichtsfensters (vorher: unten abgeschnitten, `bottom` 11px über die Fensterhöhe hinaus); Menü
an der ersten Zeile klappt weiterhin normal nach unten; Scrollen der Liste bei offenem Menü
schließt es. Screenshots beider Fälle optisch bestätigt.

## 1.3.72 – Umbau der Projektliste, Runde 2: die Oberfläche

Baut auf dem 1.3.70-Fundament auf (`pipeline_column_id`, Spalten-Stammdaten, Verwaltung in den
Einstellungen). `app/templates/projects.html` wurde vollständig neu gebaut.

**Linker Reiter-Kasten entfällt, vorab geprüft statt einfach entfernt.** `app/routers/pages.py`
kennt bis heute keine eigenständige `/quotes`- oder `/orders`-Seite -- die beiden Reiter waren
die einzige Möglichkeit, alle Angebote/Aufträge projektübergreifend in einer Liste zu sehen,
Suche und Kategoriefilter (Projekt-Kategorie) ersetzen das nicht vollständig. Vor dem Entfernen
gemeldet, auf Rückmeldung gelöst über einen **zusätzlichen Status-Filter in der neuen Liste**
("Angebot: Entwurf"/"Angebot: Versendet"/"Auftrag vorhanden"/"Ohne Angebot") statt eines neuen
Reiters oder eigener `/quotes`-/`/orders`-Seiten -- rein client-seitig aus den bereits
bestehenden, weiterhin unveränderten `GET /api/quotes`/`GET /api/orders` berechnet (beide
liefern `project_id`), keine Backend-Erweiterung nötig. Der "Anfragen"-Reiter war dagegen
redundant (`/inquiries` existiert bereits als eigenständige Seite) und entfällt ersatzlos.
Mustervorgänge bleiben über eine Kontrollkästchen "Nur Mustervorgänge" in derselben Liste
erreichbar (schaltet die Datenquelle auf `GET /api/project-templates` um) statt eines eigenen
Zugangs.

**Tasks-Prämisse erneut geprüft, nicht nur erinnert:** `tasks.html` hat weiterhin kein
`draggable`/`dragover`/`drop` und keinen Listen/Kanban-Umschalter -- nur ein einzelnes Board,
Spaltenwechsel über ein `<select>` im Bearbeiten-Formular. Umschalter und Drag-and-drop für die
neue Kanban-Ansicht sind deshalb ein eigenständiger, neuer Entwurf, kein Kopieren eines
bestehenden Musters -- die bereits in Runde 1 vereinbarte Absicherung ("nur die Pipeline-Spalte
ändert sich, kein fachlicher Status, kein Bestätigungsdialog nötig") gilt unverändert.

**Listenansicht** (volle Breite, kein `.layout`-Grid mit linker Spalte mehr): Spalten
Projektnummer/Bezeichnung/Kunde/Objekt/Kategorie/Status/Angebote/Dateien wie bisher. Die sechs
Zeilenaktionen (Projektmappe/+Angebot/Angebote/Kopieren/Als Mustervorgang speichern/
Archivieren/Löschen) wandern in ein Drei-Punkte-Kontextmenü je Zeile -- die Zeile selbst führt
per Klick in die Projektmappe. "Angebote" führt jetzt auf `/projects/{id}#sec-quotes` (die
bereits bestehende Angebote-Sektion der Projektmappe) statt auf den entfallenen Reiter.

**Kanban-Ansicht**: Spalten aus `GET /api/project-pipeline-columns` in `sort_order`, eine Karte
je Projekt (Projektnummer, Bezeichnung, Kunde/Objekt, Status als Kennzeichen). Verschieben per
nativem HTML5-Drag-and-drop (wie die Plantafel -- Projekte sind Büro/Admin-only, also
Desktop-orientiert, das bekannte Nicht-Funktionieren auf Touch-Geräten ist hier unproblematisch)
ruft den neuen Endpunkt `PUT /api/projects/{id}/pipeline-column` auf (`ProjectPipelineColumnMove`-
Schema) -- ändert ausschließlich `pipeline_column_id`, fasst `Project.status` nie an, kein
Bestätigungsdialog. Optimistisches UI-Update mit Rückrollen bei Fehler. Suche, Kategoriefilter
und der neue Status-Filter wirken identisch in beiden Ansichten (dieselbe `filteredRows()`).

**Umschalter und Kopfzeile**: Suche, Kategoriefilter, Status-Filter, "Nur Mustervorgänge",
"Archivierte anzeigen" und der Liste/Kanban-Umschalter sitzen in einer gemeinsamen Kopfzeile
über dem Inhalt. Die Wahl (`erp_project_view`, `localStorage`, Muster `erp_theme`) bleibt beim
nächsten Öffnen erhalten.

**Schema-Erweiterung**: `ProjectListOut`/`ProjectDetailOut` bekommen `pipeline_column_id`
(Pflichtfeld) -- an allen vier Stellen ergänzt, die das Schema manuell befüllen
(`routers/projects.py` dreimal, `routers/inquiries.py` einmal), sonst hätte ein bestehender
Aufrufer mit einem Pydantic-Validierungsfehler abgebrochen.

**Rollen geprüft, keine Änderung nötig**: `/projects` und `/api/projects*` tragen unverändert
`require_role(ROLE_ADMIN, ROLE_OFFICE)` -- ein Monteur erreicht die Projektliste weiterhin nicht
(Seite UND API 403, per echtem HTTP-Smoke-Test gegen eine isolierte Testinstanz bestätigt, nicht
nur angenommen), `/mobil` bleibt für ihn unverändert erreichbar.

**Smoke-Test gegen eine isolierte, echte Serverinstanz** (eigene, temporäre SQLite-Datei, nie die
echte `dachkonzepte_erp.db`): Projekt anlegen, im Kanban zwischen Spalten verschieben (Status
blieb dabei nachweislich unverändert), Büro-Rolle sieht die Liste (200), Monteur-Rolle bekommt
403 auf Seite und API. JS-Syntax mit `node --check` geprüft. Kein echter Browser-Klicktest
(dieselbe, wiederholt dokumentierte Werkzeug-Einschränkung dieser Umgebung) -- Drag-and-drop,
Kontextmenü-Interaktion und die clientseitige Filterlogik sind dadurch nur über die
JS-Quelltextprüfung und die Backend-Endpunkttests abgesichert, nicht über eine echte
Bildschirminteraktion.

## 1.3.71 – Wanduhrzeit-Flake in `tests/test_v224_field_view.py` behoben

Unabhängig von der Projekt-Pipeline (eigener Commit, wie ausdrücklich verlangt -- "eine eigene
kleine Korrektur, nicht vermischt"). Zwei bereits vor 1.3.70 bestehende Tests
(`test_field_view_today_returns_assignments_and_drafts_for_linked_employee`/
`..._rejects_unlinked_employee`) riefen `get_field_view_today()` (`app/routers/field_view.py`)
direkt auf, ohne die darin geprüfte Feierabend-Grenze (`is_past_shift_end()`, Standard 19:00 Uhr)
über ein festes `now` zu entkoppeln -- sie schlugen deshalb JEDEN Tag nach 19 Uhr fehl,
unabhängig von jeder Codeänderung. Ein Test, der irgendwann garantiert rot wird, ist schlimmer
als keiner: man gewöhnt sich an eine rote Suite und übersieht dabei einen echten Fehler.

Behoben über eine neue, private Bruchstelle `_now()` in `app/routers/field_view.py` -- liefert
`datetime.now()`, wird jetzt von `get_field_view_today()` explizit an `is_past_shift_end()`
durchgereicht, statt sich auf dessen impliziten `datetime.now()`-Rückfall zu verlassen. Bewusst
KEIN Query-/Body-Parameter auf der Route selbst: das hätte einem Monteur erlaubt, die
Feierabend-Abmeldung per `?now=...` zu umgehen, ein echtes Sicherheitsrisiko. Die beiden Tests
monkeypatchen `_now()` jetzt auf einen festen Vormittagswert -- dasselbe Muster, das
`test_is_past_shift_end_before_and_after_configured_time()` in derselben Datei für
`is_past_shift_end()` bereits direkt mit einem festen `now` vormacht, nur über die private
Python-Bruchstelle statt eines HTTP-Parameters. Verifiziert um 20:22 Uhr (nach dem
Standard-Feierabend) -- vollständige Suite grün (1382/1382), keine Regression.

## 1.3.70 – Umbau der Projektliste, Fundament: Projekt-Pipeline

Erster Baustein des vom Nutzer verlangten Umbaus (Befund zuvor separat geliefert, keine
Codeänderung -- siehe CLAUDE.md "Umbau der Projektliste"): die Projektliste soll eine eigene,
frei konfigurierbare Kanban-Ansicht bekommen, analog zu den Aufgaben. Die wichtigste
Entscheidung dabei -- Kanban-Spalte als neues, unabhängiges Feld neben dem bestehenden
`Project.status`, statt den Status durch die Spalten zu ersetzen -- ist getroffen: `status`
bleibt automatisch/kennzahlengesteuert (Beauftragung, Duplizieren, Dashboard-KPIs), die neue
`pipeline_column_id` ist eine rein frei per Ziehen gesetzte Arbeitsansicht ohne jede fachliche
Bedeutung. Diese Version liefert AUSSCHLIESSLICH das Fundament -- Datenmodell, Migration mit
Startspalte für alle Bestandsprojekte, Spaltenverwaltung in den Einstellungen. Die Listen- und
Kanban-Oberfläche selbst folgt erst in der zweiten Runde, nach Bestätigung dieses Schritts.

Neue Stammdatentabelle `ProjectPipelineColumn` (`key`/`label`/`sort_order`, Migration
`da9d9425e257`) -- bewusst nach demselben Muster wie `TaskColumn` aufgebaut (Slug-Erzeugung,
sort_order-Schrittweite 10, Löschschutz bei letzter Spalte/bei Verwendung), aber ohne
`is_done`: die Pipeline-Spalte trägt keine Automatik, ein wirkungsloses "erledigt"-Flag wäre
nur irreführend gewesen. Vier Startspalten ("Neu", "In Bearbeitung", "Wartet",
"Abgeschlossen") -- ein schlanker, allgemeiner Satz statt fein aufgeteilter Phasen, der Betrieb
passt sie in den Einstellungen an. Neue Spalte `Project.pipeline_column_id` (FK, NOT NULL) --
ein Projekt ohne Spalte würde im künftigen Kanban unsichtbar bleiben, deshalb Pflichtfeld statt
optional; die Migration legt sie zunächst nullable an, befüllt ALLE Bestandsprojekte auf die
erste Spalte ("Neu") und setzt danach NOT NULL (Regel 1). Alle vier Stellen, die ein neues
`Project` anlegen (`app/projects.py::duplicate_project()`, `app/quick_service_orders.py`,
`app/routers/inquiries.py::convert_inquiry()`, `app/routers/projects.py::create_project()`)
setzen die Startspalte jetzt explizit über die neue `default_pipeline_column_id()`.

Bewusst KEINE gemeinsame, generische Abstraktion mit `app/task_columns.py` -- Task verweist
über den String-Schlüssel (`Task.status == TaskColumn.key`), Project dagegen über die
numerische ID (`Project.pipeline_column_id == ProjectPipelineColumn.id`), zwei unterschiedliche
Referenzformen, und die Pipeline-Spalte kennt kein `is_done`. Eine Abstraktion für nur diese
zwei, sich in diesem Punkt unterscheidenden Nutzer wäre eine Überabstraktion gewesen -- das
MUSTER (nicht der Code) ist identisch übernommen, damit beide Spaltensysteme nicht
auseinanderdriften. Neuer Router `app/routers/project_pipeline_columns.py`
(`/api/project-pipeline-columns`), dieselbe Büro+Admin-Sperre wie der Rest der
Projektverwaltung, Schreibzugriffe zusätzlich admin-only (Muster `task_columns.py`). Neuer
Einstellungen-Abschnitt "Projekt-Pipeline" (Gruppe "Projekte") mit derselben
Bearbeiten/Verschieben/Löschen-Oberfläche wie bei den Aufgaben-Spalten.

## 1.3.69 – Wartungsbericht-Detailansicht für Monteure, ausschließlich über das Objekt

Anlass: ein Monteur führt dieselbe Wartung erneut durch und will nachvollziehen, was beim
letzten Einsatz gemacht wurde -- auch von einem inzwischen ausgeschiedenen Kollegen. Bisher
zeigte die mobile Objektansicht (`/mobil/objekt/{property_id}`) dafür nur das reduzierte
Wartungshistorie-Schema (Datum, Berichtstyp, Monteur, Prüfergebnisse, Mängel mit Status) -- den
einzelnen Bericht im Detail samt Fotos, oder als PDF, konnte ein Monteur nicht öffnen.

Vorab ein Befund, dann auf Bestätigung gebaut. Vier Punkte:

1. **Der vermutete "internal_note"-Fund existiert nicht.** Ein rekursiver Schlüssel-Scan gegen
   `ServiceReportHistoryOut` und die zugrunde liegenden Modelle (`ServiceReport`, `Finding`,
   `InspectionItem`) findet kein Feld dieses Namens oder mit vergleichbarer Bedeutung -- nichts
   wurde entfernt. Als Regressionstest festgehalten (erweitert den bereits bestehenden
   Exact-Key-Set-Test aus `tests/test_v260_role_audit.py` um zusätzliche Suchbegriffe:
   "internal"/"office_note"/"vermerk"/"betrag"/"summe").
2. **Kein Preis war je im Bericht-PDF enthalten** -- weder Material (`ServiceReportMaterial`
   trägt strukturell keine Preisspalte) noch Zeitbuchungen (`TimeEntry` hat kein Preis-/
   Stundensatzfeld). Das PDF, das ein Monteur ohne die Zeitbuchungen der Kollegen sehen darf,
   entsteht deshalb NICHT über einen eigenen Renderer, sondern über einen einzigen Schalter am
   bestehenden: `build_service_report_pdf(db, report, include_time_entries=False)` lässt den
   Abschnitt "Erfasste Zeiten" komplett weg -- `list_entries()` wird dabei gar nicht erst
   aufgerufen (nicht nur die Tabelle ausgeblendet, per Test mit einem Aufruf-Wächter belegt).
   Alles andere bleibt exakt wie im Kundendokument, inklusive dem "damaliger Monteur"-Meta-Feld
   (per Vorgabe ausdrücklich erlaubt). `build_service_report_pdf_for_field()` ist die dünne,
   dokumentierende Wrapper-Funktion dafür.
3. **Zugang ausschließlich über das Objekt.** Neuer Endpunkt
   `GET /api/field-view/properties/{property_id}/maintenance-history/{report_id}/pdf` --
   `resolve_property_history_report_for_field()` (`app/service_reports.py`) verifiziert am
   Abrufzeitpunkt erneut, dass der Bericht tatsächlich zu GENAU diesem Objekt gehört und bereits
   unterschrieben ist (Muster `resolve_property_document_for_field()`), sonst 404 --
   ununterscheidbar von "existiert nicht", nie ein 403 (kein Bestätigen per URL-Raten). Eine
   geratene `report_id` ohne Objektweg (es gibt keine Route ohne `property_id`) und ein Bericht,
   der zu einem ANDEREN Objekt gehört, wurden im Angriffstest je einzeln geprüft.
4. **Nur Lesen.** Unter diesem Pfad existiert kein PUT/DELETE/sign (405 bei einem Versuch) --
   die bestehenden Berichts-Endpunkte bleiben unverändert über `require_field_report_ownership()`
   (`app/routers/orders.py`) auf den eigenen Bericht beschränkt, unberührt von dieser Änderung.
   Bewusste, dokumentierte Ausnahme zu deren Docstring: die objektbezogene Detailansicht prüft
   keine Ersteller-Zuordnung -- die Wartungshistorie zeigt einem Monteur schon immer fremde
   Berichte desselben Objekts (seit 1.3.56), diese Version ist nur die Detail-Variante derselben
   Ausnahme.

`app/templates/mobil_objekt.html` bekommt dafür einen "Als PDF ansehen"-Link je Historieneintrag
(Muster der bereits bestehenden Dokument-Aktionsknöpfe, `.doc-actions`). 9 neue Tests
(`tests/test_v273_maintenance_report_field_detail.py`): geratene ID, fremdes Objekt, Entwurf
(noch nicht unterschrieben), interne Felder, Preisfelder, fremde Zeit, Schreibversuch über den
alten UND den neuen Weg -- null "durchgelassen".

## 1.3.68 – Hell/Dunkel-Umschalter in der Monteurs-Kopfzeile

Gemeldete Lücke: die Büro-Sidebar hat den Hell/Dunkel-Umschalter seit 1.3.44 im Fußbereich, die
Monteurs-Kopfzeile (`_mobile_header.html`) hatte nie einen -- ein Monteur konnte sein Tablet nicht
auf ein anderes Design umstellen. Ergänzt nach demselben Mechanismus wie die Sidebar (dasselbe
`data-theme`-Attribut auf `<html>`, derselbe `localStorage`-Schlüssel `'erp_theme'`, dieselben
SUN_ICON/MOON_ICON-SVGs) -- dupliziert statt geteilt, wie in diesem Projekt bei kleinen
JS-Schnipseln üblich (kein gemeinsames Modul). Ein Monteur, der auf dem Tablet umschaltet, findet
seine Wahl beim nächsten Öffnen wieder.

Anordnung: der neue, kleine Icon-Knopf (`#mobileThemeToggle`, 30×30px) sitzt in der Kopfzeile
selbst, oben rechts neben dem Benutzernamen -- beide zusammen in einem neuen, gemeinsamen
`.mobile-header-right`-Wrapper (`flex:0 0 auto`, schrumpft nie), damit `.mobile-header` weiterhin
genau zwei direkte Kindelemente hat und dessen `justify-content:space-between` unverändert greift.
Kollidiert dadurch strukturell nicht mit dem Suchfeld (1.3.65, eigene Zeile darunter) oder den vier
Reitern (ebenfalls eigene Zeile) -- beide sitzen in eigenen, vom Kopf getrennten Blockzeilen des
seit 1.3.65 gemeinsamen sticky-Wrappers. Auf schmalen Bildschirmen kann nur `.mobile-header-brand`
(bereits mit `overflow:hidden`/Ellipsis) schrumpfen, der rechte Block bleibt bei fester Breite --
die Kopfzeile kann dadurch strukturell nicht umbrechen, unabhängig von der Bildschirmbreite.

Geprüft statt angenommen: `get_theme()` (der seit 1.3.42 ausnahmesichere Jinja-Global) wird in
allen vier Monteursseiten-Templates (`mobil.html`, `mobil_objekt.html`, `field_timesheet.html`,
`time_tracking_field.html`) bereits im eigenen `:root`-Block für `--accent` gelesen, genau wie auf
jeder anderen Seite des Design-Systems -- keine Codeänderung nötig, nur als Regressionstest
festgehalten. Ein Fehler in `get_theme()` sperrt dadurch schon heute keine Monteursseite, exakt
wie gefordert.

## 1.3.67 – Büro-Suche, Etappe 2: die Oberfläche

Nach Rückmeldung zu Etappe 1 gebaut. Suchfeld in der seit 1.3.45 reservierten Topbar-Position
(`app/templates/_topbar.html`) -- Vorschläge beim Tippen mit demselben Debounce (300ms) und
derselben Mindestlänge (2 Zeichen) wie die Monteurs-Suche, ruft ausschließlich `GET /api/search`,
nie den Monteurs-Endpunkt (Separate-Endpunkt-Prinzip). Rendert nur für `admin`/`office` -- für
`field` fehlt das Eingabefeld strukturell im Markup. Ein Vorschlag zeigt Gruppen-Label/Titel/
Untertitel, ein Klick führt direkt auf die `url` des Treffers; Bestätigen öffnet `/suche`.

Neue Ergebnisseite `GET /suche` (`app/routers/pages.py`, `app/templates/search_results.html`):
Gruppierung nach Datensatzart, reale Trefferzahl je Gruppe, Liste auf 20 gekappt mit "weitere
anzeigen" (fragt gezielt nur die eine Gruppe erneut ab), Filter nach Art über 17 hartcodierte
Umschalt-Knöpfe (gegen die Registry abgeglichen, ein Regressionstest verhindert stilles
Auseinanderlaufen). Die Seite trägt dieselbe `require_role(ROLE_ADMIN, ROLE_OFFICE)`-Absicherung
wie jede andere Büro-Seite, nicht nur der API-Endpunkt dahinter -- ein Monteur, der die Adresse
von Hand eintippt, bekommt 403 vor jedem Rendern, per echtem Ende-zu-Ende-Test gegen eine
isolierte, laufende Serverinstanz bestätigt (nicht nur über den vereinfachten Testclient).

Dabei ein kleiner, transparent gemeldeter Fund: die Monteurs-Suche (`_mobile_header.html`)
schloss ihre Vorschlagsliste bisher nur per Klick daneben, keine Escape-Behandlung, obwohl die
Anfrage für die neue Büro-Suche "wie in der Monteurs-Suche" annahm, dass Escape dort schon
funktioniert -- für beide nachgezogen, nicht nur für die neue. 10 neue Tests
(`tests/test_v271_office_search_ui.py`), ein bestehender Test in `tests/test_v254_topbar.py` in
zwei umgeschrieben (die 1.3.45-Erwartung "Suchslot bleibt leer" ist jetzt bewusst überholt).
Volle Suite grün (1344/1344). Damit ist die Büro-Suche vollständig.

## 1.3.66 – Büro-Suche, Etappe 1: Registry, Kernstruktur, Rollensicherheit

Der ursprüngliche Wunsch aus der 1.3.64-Bestandsaufnahme: Vorschläge beim Tippen, Ergebnisseite
mit Filtern bei Bestätigung, für die volle "Gruppe A" (17 Datensatzarten) statt nur Objekte.
Erste von zwei Etappen -- diese Version liefert Registry/Kern/Rollensicherheit, die Oberfläche
(Suchfeld in der Topbar, Ergebnisseite) folgt erst nach Rückmeldung.

Erweitert den geteilten Suchkern aus 1.3.64 (`app/search.py`) um 16 weitere Datensatzarten
(Kunden, Aufträge, Rechnungen, Mahnungen, Angebote, Projekte, Dachflächen, Anfragen, Aufgaben,
Mitarbeiter, Einsatzberichte, Mängel, Wartungsverträge, Leistungen, Materialien, Lieferanten)
über eine neue `SearchSource`-Registry (`OFFICE_SEARCH_SOURCES`) und einen Dispatcher
(`search_office()`) -- `search_properties()` selbst bleibt unverändert, die "properties"-Quelle
ruft sie direkt auf. Der Vollständigkeitstest wurde zusammen mit der Registry gebaut, nicht
danach (Regel-11-Muster).

Vier Entscheidungen vom Betreiber, jede umgesetzt: (1) jede der 17 Quellen bleibt Büro+Admin,
nichts admin-only -- geprüft, ob innerhalb der Finanzdaten etwas admin-only sein müsste
(Kalkulationsgrundlagen sind keine Gruppe-A-Entität, Einkaufspreise/Vergütung sind bereits
anderswo Büro+Admin-sichtbar); der eigentliche Schutz ist strukturell (jede Zeile trägt nur
`{id, title, subtitle, url}`, nie ein Preis-/Lohnfeld). (2) ILIKE statt Volltextsuche, empirisch
begründet (472 Zeilen, ~0.03ms je Abfrage) -- die Schwelle für einen künftigen Wechsel zu
PostgreSQL `pg_trgm`/SQLite `FTS5` ist in CLAUDE.md dokumentiert. (3) "orders"/"invoices"
durchsuchen sowohl den eingefrorenen Kunden-Schnappschuss als auch den live Kundennamen,
unabhängig voneinander -- ein Kunde, dessen Name sich seit einer Rechnung anders formatiert,
wird über beide Schreibweisen gefunden (mit eigenem Test belegt). (4) die Ergebnisseite bekommt
je Datensatzart die reale Trefferzahl plus eine auf 20 gekappte Liste, für ein künftiges "weitere
anzeigen" statt Seitenzahlen.

Neuer, eigenständiger Endpunkt `GET /api/search` (`app/routers/search.py`) -- niemals ein
gemeinsamer, rollenverzweigender Endpunkt mit der Monteurs-Suche (Prinzip seit 1.3.64).
`require_role(ROLE_ADMIN, ROLE_OFFICE)` ist die primäre Sicherung, automatisch vom bestehenden
Rollen-Audit-Test erfasst. Angriffstest wie bei der Monteurs-Suche: ein Monteur bekommt 403 --
plain und mit manipulierten Parametern (`types=`, `limit=999999`) --, identisch, null
durchgelassen; Büro/Admin bekommen 200 inklusive einer `invoices`-Gruppe. 11 neue Tests
(`tests/test_v270_office_search.py`), volle Suite weiterhin grün (1333/1333).

## 1.3.65 – Zwei Anpassungen an der Monteurs-Suche

Nach dem ersten Einsatz gemeldete Rückmeldung zur 1.3.64-Suche.

**Kundenname in den Vorschlägen.** Nur Objektname und Ort reichten zur Identifikation nicht --
ein Objekt ist ohne Kundenname schwer einzuordnen, besonders wenn ein Kunde mehrere Objekte hat.
`PropertySearchHitOut` bekommt ein viertes Feld `customer_name` -- bewusst nicht sensibel (ein
Monteur, der zum Objekt fährt, kennt den Kunden ohnehin). Kundennummer, interne Notizen, die
volle Adresse über den Ort hinaus und alles Finanzielle bleiben weiterhin gesperrt. Die rollenlose
Kernfunktion `search_properties()` bleibt unverändert, nur die feldsichere Reduktionsschicht
wurde erweitert -- der Angriffstest aus 1.3.64 wurde entsprechend angepasst, nicht neu geschrieben.

**Suche in die Kopfzeile.** Das Suchfeld saß bisher nur auf der Einsätze-Seite, unerreichbar von
den drei anderen Monteursseiten aus -- umgezogen in die gemeinsame Kopfzeile `_mobile_header.html`,
die alle vier Seiten ohnehin einbinden. Dabei die alte, seit 1.3.45 bestehende Stapel-Architektur
(zwei einzeln mit hart codierten Pixelwerten aufeinandergesetzte sticky-Elemente) durch einen
gemeinsamen sticky-Wrapper mit normalen, nie überlappenden Blockzeilen abgelöst -- robuster gegen
künftige neue Zeilen und von Natur aus überlappungsfrei auf jeder Bildschirmgröße. Die
Vorschlagsliste öffnet sich bewusst unterhalb der gesamten Kopfzeile statt direkt unter dem
Suchfeld, damit sie die Reiter nie überdeckt -- sonst hätte ein Tipp auf einen Reiter bei offener
Liste zuerst nur die Liste geschlossen, statt sofort zu navigieren. Auf Tablets bekommen Suchfeld
und Vorschlagsliste eine zentrierte Maximalbreite, auf Smartphones bleibt beides unverändert voll
breit.

## 1.3.64 – Dateiablage je Objekt, Schritt 3: die geteilte Suche als Einstieg

Letzter, ursprünglich zweimal zurückgestellter Schritt der Monteurs-Erweiterung -- ein Monteur
findet ein Objekt jetzt über ein Suchfeld auf `/mobil`, statt seine ID kennen zu müssen. Damit
gilt laut Betreibervorgabe: "Damit ist die Monteursansicht vollständig."

**Neue, geteilte Kernfunktion** (`app/search.py`) -- die Büro-Suche existiert weiterhin nicht (nur
Befund, nie gebaut), diese Datei ist aber bereits als Kern angelegt, den eine künftige Büro-Suche
um weitere Datensatzarten erweitert, statt sie zu ersetzen. Zwei Schichten: `search_properties()`
(reine, rollenlose Datenbeschaffung über Objektname/Straße/PLZ/Ort UND den Namen des zugehörigen
Kunden) und `search_properties_for_field()` (reduziert jedes Ergebnis auf `id`/`name`/`city`).
Die Feldbegrenzung sitzt serverseitig, an der Rolle, nicht an der URL -- der neue Endpunkt
`GET /api/field-view/properties/search` ruft ausschließlich die feldsichere Funktion auf,
zusätzlich abgesichert durch ein knappes `response_model`. Registriert vor
`GET .../properties/{property_id}`, sonst die bekannte Literal-vs-Platzhalter-Kollision.

**Index-Frage empirisch geprüft, nicht angenommen**: `EXPLAIN QUERY PLAN` gegen die echte
Datenbank zeigt, dass selbst ein bereits bestehender Index (`customers.name`) bei einer
Substring-Suche (`ILIKE('%term%')`) ignoriert wird (`SCAN`, kein `SEARCH ... USING INDEX`) -- ein
gewöhnlicher B-Baum-Index hilft nur Präfix-Suchen. Bei der aktuellen Datenmenge (163 Objekte, 162
Kunden) ist ein voller Tabellenscan ohnehin irrelevant -- keine neue Migration für Indizes. Gegen
zu teure Anfragen wirken statt eines Index eine serverseitige Mindestlänge (zwei Zeichen) und ein
300ms-Debounce auf `/mobil` (`_debounce.html`, bereits bestehender Helfer, erstmals für eine Suche
statt eines Autosave verwendet).

Vorschlagsliste auf `/mobil` zeigt Objektname und Ort je Treffer, ein Klick führt direkt zu
`/mobil/objekt/{id}`; bei zehn Treffern (dem festen Limit) ein Hinweis, die Suche zu verfeinern.
Angriffstest (12 neue Tests): kein Endpunkt liefert etwas anderes als Objekte, kein gesperrtes
Feld (Kundennummer, interne Notiz) taucht in der Antwort auf, manipulierte Parameter (`limit`,
erfundene Felder) ändern weder die Trefferzahl noch das Antwortschema. Null "durchgelassen".

## 1.3.63 – Dateiablage je Objekt, Schritt 2: die mobile Objektansicht

Zweiter Schritt der "Dateiablage je Objekt" (nach den Kategorie-Stammdaten aus 1.3.62) -- die
mobile Objektansicht selbst, in dieser Version noch über eine feste Objekt-ID erreichbar
(`/mobil/objekt/{property_id}`), die geteilte Suche als eigentlicher Einstieg folgt als eigener,
späterer Schritt.

**Neue Tabelle `PropertyDocument`** (`app/models.py`) -- eigene, objektgebundene Dateiablage für
die eigenen Uploads eines Monteurs vor Ort: ein spontaner Einsatz hat oft gar kein Projekt,
`ProjectDocument` konnte solche Uploads deshalb nicht aufnehmen. Bewusst objektbezogen statt
einem Sammelprojekt je Objekt zugeordnet (Betreiberentscheidung) -- ein Sammelprojekt wäre in
jeder projektbezogenen Auswertung fälschlich als echter Auftrag/Angebot mitgezählt worden.
Anders als `CustomerDocument`/`ProjectDocument` trägt die neue Tabelle bewusst nur `category_id`,
keinen zusätzlichen freien `category`-String -- der Freitext existiert dort nur wegen
Altbestands-Kompatibilität, die eine brandneue Tabelle nicht braucht.

Die mobile Objektansicht führt zwei Dokumentquellen zu einer Liste zusammen
(`list_merged_documents_for_property()`, `app/property_documents.py`): die eigenen
`PropertyDocument`-Uploads UND die Dokumente ALLER nicht archivierten Projekte des Objekts
(`Project.property_id`) -- wie vom Betreiber vorgegeben ("ein Dachdecker denkt in Objekten,
nicht in Projektnummern"). `CustomerDocument` bleibt bewusst außen vor, das ist Kundenebene,
nicht Objektebene. Dieselbe Funktion bedient sowohl die Büro-Sicht (voller Bestand, neuer
Abschnitt "Objektdateien" auf `property.html`, macht Monteur-Uploads dort auffindbar) als auch
die Monteursansicht (`field_visible_only=True`).

**Rechte, der heikelste Teil dieser Runde**: ab der mobilen Objektansicht gilt eine ANDERE Regel
als sonst im Rechtekonzept -- ein Monteur erreicht JEDES Objekt über seine ID, nicht nur die
eigenen (die sonst übliche Zuordnungsprüfung entfällt hier bewusst). Die Grenze sitzt
stattdessen ausschließlich im Inhalt: harmlose Objektfelder (`PropertyAccessOut`, dieselbe
Teilmenge wie beim bereits bestehenden `GET /api/orders/{order_id}/property` -- kein `notes`,
keine `customer_id`), nur für Monteure freigegebene Dokumentkategorien
(`field_may_see_category()`, beide Schlösser aus 1.3.62) und das bereits etablierte reduzierte
Wartungshistorie-Schema (`ServiceReportHistoryOut`). Der Datei-Ausliefer-Endpunkt prüft
`field_may_see_category()` ERNEUT am Ausliefer-Zeitpunkt, nicht nur bei der Auflistung -- eine
über die Liste nie gezeigte, aber per geratener ID angefragte Datei aus einer gesperrten
Kategorie liefert denselben 404 wie eine tatsächlich nicht existierende. Der Upload-Endpunkt
prüft `category_id` serverseitig gegen `field_may_see_category()`, unabhängig davon, was die
Kategorie-Auswahlliste der Oberfläche anbietet -- ein direkter API-Aufruf mit einer gesperrten
Kategorie schlägt ebenso fehl. Bilder werden beim Hochladen wie Berichtsfotos aus 1.2.17
verkleinert, Dokumente bleiben im Original.

15 neue Angriffstests (`tests/test_v267_property_field_documents.py`), wie verlangt: fremdes
Objekt über die ID öffnen (erlaubt, aber nur harmlose Felder), Datei aus gesperrter Kategorie
über geratene ID (abgewiesen, inkl. einer direkten Datenbank-Manipulationssimulation wie in
1.3.62), Datei eines falschen Objekts über die URL (abgewiesen), archivierte Projekte
ausgeschlossen, Upload in eine gesperrte Kategorie serverseitig abgewiesen, kein Endpunkt liefert
Preis-/Kosten-/interne Felder (rekursiver Schlüssel-Scan, Fehlerklasse `purchase_price` aus
1.3.53), Büro sieht Monteur-Uploads. Volle Suite grün.

## 1.3.62 – Dateiablage je Objekt, Schritt 1: Kategorie-Stammdaten mit zwei unabhängigen Schlössern

Erster Schritt der "Runde 2" der Monteurs-Erweiterung (Dateiablage je Objekt) -- ausdrücklich nur
das Fundament, wie vom Betreiber vorgegeben: die Kategorie-Stammdaten samt Migration und der
festen Code-Sperrliste. Die mobile Objektansicht und die geteilte Suche bauen erst in einer
späteren, noch zu bestätigenden Runde darauf auf.

Neue echte Stammdatentabelle `DocumentCategory` (`app/document_categories.py`) löst die bisherige
freie Optionsgruppe `project_document_categories` ab -- dieselbe Hochstufung SettingOptionGroup →
echte Tabelle wie bei `RoofComponentType`/`RoofLayerType` (1.2.19/1.2.18), da eine reine
Auswahlliste `is_sensitive`/`is_field_visible` nicht tragen konnte. Acht Kategorien wortgleich aus
der bisherigen Optionsgruppe übernommen (Pläne, Bilder / Fotos, Lieferscheine, Aufmaß,
Schriftverkehr, Verträge / Freigaben, Rechnungen / Belege, Sonstiges) -- die letzten beiden sind
als sensibel markiert.

**Zwei unabhängige Schlösser gegen "sensible Kategorie für Monteure sichtbar", wie ausdrücklich
verlangt:** (1) `create_category()`/`update_category()` lehnen die Kombination
`is_sensitive=True` + `is_field_visible=True` immer ab, und `is_sensitive` kann, einmal gesetzt,
nie wieder auf `False` zurückgesetzt werden -- weder über die Oberfläche noch über die API. (2)
`HARD_LOCKED_CATEGORY_KEYS` ist eine feste, im Code verankerte Sperrliste ("Rechnungen / Belege",
"Verträge / Freigaben") -- `field_may_see_category()` prüft sie unabhängig von den beiden Feldern,
selbst wenn jemand die Datenbank direkt manipuliert. Mit einem Test belegt, der ein
`DocumentCategory`-Objekt unter Umgehung von `create_category()`/`update_category()` direkt mit
`is_field_visible=True` konstruiert -- `field_may_see_category()` bleibt trotzdem bei `False`.

`category_id` (neue, zusätzliche Fremdschlüsselspalte, die bestehende Freitextspalte `category`
bleibt unverändert bestehen) auf `CustomerDocument`/`ProjectDocument`. Migration `9137945e8785`
folgt Regel 1 (`server_default` bei NOT-NULL-Spalten auf bestehenden Tabellen): die Spalte wird
zunächst nullable angelegt, aus dem Bestand befüllt (exakte Übereinstimmung mit dem `key`, sonst
Rückfall auf "Sonstiges" -- nie auf eine sichtbare oder sensible Kategorie), erst danach auf NOT
NULL gesetzt. Gegen die echte, lokale Datenbank geprüft: `customer_documents` war leer (0 Zeilen),
`project_documents` hatte genau eine Zeile mit `category='Pläne'` -- ein exakter Treffer, kein
einziger unklassifizierbarer String im gesamten Bestand.

Vier bestehende Endpunkte (`upload_customer_document()`, `upload_project_document()`,
`update_customer_document()`, `update_project_document()`) befüllen `category_id` jetzt über eine
neue Hilfsfunktion `resolve_category_id()` -- sonst hätte die neue NOT-NULL-Spalte ab dem Moment
der Migration jeden neuen Upload/jede Aktualisierung brechen lassen. Dabei ein echter, über die
vier bereits bekannten Endpunkte hinausgehender Fund: der Lieferschein-Upload in
`app/routers/work_preparation.py::upload_work_preparation_delivery_note()` legt ebenfalls
`ProjectDocument`-Zeilen an und hätte ohne dieselbe Korrektur in Produktion mit einem
`IntegrityError` fehlgeschlagen -- behoben, bevor es zum echten Vorfall wird. Zwei bestehende
Tests (`test_v066_audit_history.py`, `test_v083_material_bulk_assignment.py`) konstruierten
`ProjectDocument` ebenfalls direkt ohne `category_id` und wurden entsprechend nachgezogen.

Neuer Router `app/routers/document_categories.py` (`GET/POST/PUT` + `activate`/`deactivate`,
Büro/Admin) und ein neuer Einstellungen-Abschnitt "Dokumentkategorien" (Gruppe "Dokumente") --
bewusst kein DELETE-Endpunkt in dieser Runde, Deaktivieren reicht vorerst. Die Oberfläche
spiegelt beide Schlösser: das "Sensibel"-Kontrollkästchen lässt sich nach dem Setzen nicht mehr
entfernen, und ist eine Kategorie sensibel (oder fest gesperrt), ist "Für Monteure sichtbar"
deaktiviert.

20 neue Tests (`tests/test_v266_document_categories.py`): Selbst-Seeding, beide Schlösser samt der
Datenbank-Manipulations-Simulation, Router-Rollenprüfung (`field` bekommt 403), die
Freitext-Zuordnung (`resolve_category_id()`), die vier Regressions-Endpunkte, und die
Seed-/Backfill-Logik der Migration isoliert gegen eine eigene Connection (Muster aus 1.2.19/1.3.12
-- die Resolver-Funktion steckt als eigenständige, testbare Funktion direkt in der
Migrationsdatei).

## 1.3.61 – Fünf weitere Anpassungen an der Monteursansicht

Fünf rollenbezogene Punkte, alle ohne neues Datenmodell.

**Umbenennung** -- `/vor-ort` wird zu `/mobil`, Titel "DACHKONZEPTE GmbH - Mobil". `/vor-ort`
entfällt ersatzlos (keine Weiterleitung, keine bekannten Lesezeichen). Alle drei tatsächlichen
Linkquellen geprüft und mitgezogen: `app/mobile_manifest.py` (`start_url`), `login.html` (der
clientseitige Rückfall ohne `next`), `app/permissions.py::default_home_page_for_role()` (die eine,
gemeinsame Quelle für `login_page()`, den 403-Exception-Handler und `dashboard_page()`).
`app/templates/vor_ort.html` ist gelöscht, `app/templates/mobil.html` tritt an seine Stelle.

**Startseite für Monteure** -- `GET /` leitet für `field` jetzt auf `/mobil` weiter statt mit 403
zu sperren (`dashboard_page()` trägt seither `_any_role_dep` statt `_role_dep`, mit einer
rollenbewussten Weiche im Funktionskörper). Deckt sowohl den Fall nach dem Anmelden als auch
einen von Hand eingetippten Aufruf ab -- die Rolle entscheidet das Ziel, nicht der Weg.

**Tätigkeit im Nachtrag und im Schnellstart** -- ein optionales Tätigkeit-Feld ist jetzt in
BEIDEN Abschnitten von `time_tracking_field.html` vorhanden, aus derselben
`time_entry_activities`-Optionsgruppe wie in der vollen `time_tracking.html`. Ausdrücklich
festgehalten: die als Ausgangspunkt genannte Annahme ("der Schnellstart hat das Feld schon")
traf nicht zu -- vor 1.3.61 hatte keins der beiden Formulare ein Tätigkeitsfeld, nur die
Zeitart-Kacheln. Backend-seitig war nichts zu ändern, `activity` war auf beiden Schemas schon
immer optional.

**Stundenzettel** -- neue Seite `/mobil/stundenzettel`: Monatsansicht am Bildschirm (Standard der
laufende Monat, nur eigene Buchungen, Tagessummen und Monatssumme) sowie ein PDF-Download über
den gemeinsamen PDF-Rahmen mit Briefkopf. Neuer Renderer `app/field_timesheet_pdf.py`, neuer
Dokumenttyp `"field_timesheet"` (`DOCUMENT_TYPES`/`RENDERERS_USING_SHARED_FRAME`) -- fällt ohne
eigene Zeile automatisch auf den bereits bestehenden, geteilten "default"-Satz zurück, keine
Migration nötig. Der bestehende, admin-only Büro-Stundenzettel (`app/time_backoffice.py`, nie auf
dem gemeinsamen Rahmen) diente nur inhaltlich als Vorlage (Spaltenauswahl, Summenzeilen). Kein
neuer JSON-Endpunkt für die Bildschirmansicht -- die nutzt das bereits self-scoped
`GET /api/time-entries`; nur die PDF-Erzeugung braucht den neuen `GET
/api/field-view/timesheet.pdf`.

**Eigene Plantafel-Einträge** -- neue Karte "Meine kommenden Termine" auf `/mobil`:
`list_upcoming_assignments_for_employee()` (`app/planning.py`, ±30 Tage, dieselbe Zuordnung wie
die bestehende Tagesliste, jetzt in einer gemeinsamen Hilfsfunktion ausgelagert) über den neuen
`GET /api/field-view/upcoming`. Reine Leseansicht ohne Zugriff auf die Plantafel selbst --
gerendert als nicht anklickbare Karten.

**Angriffstest wiederholt, wie verlangt** -- volle Plantafel (Seite `/planning` und API
`GET /api/planning`), fremde Stunden (auch bei einem expliziten `?employee_id=`-Manipulationsversuch)
und fremde Plantafel-Einträge bleiben für `field` gesperrt. Null "durchgelassen", zweiter
Testdurchlauf bestätigt. 1267/1267 Tests grün.

## 1.3.60 – Zeiterfassung für Monteure

`/time-tracking` zeigte für die Rolle `field` bisher die volle, sidebar-getragene Bürooberfläche
(`time_tracking.html`) -- seit der Seiten-Klassifizierung (1.3.57) zwar erreichbar, aber ohne die
schmale, handschuhtaugliche Bedienung des übrigen `/vor-ort`. Befund vor dem Bauen: die
API-Endpunkte in `app/routers/time_tracking.py`/`absence_requests.py` waren bereits vollständig
self-scoped (Rechtekonzept Teil B) -- die Reduktion ist eine reine Darstellungsfrage, keine
Zugriffsfrage.

Neue, reduzierte Vorlage `time_tracking_field.html` (Muster `_mobile_header.html`/`vor_ort.html`):
Schnellstart (Auftrag + große Zeitart-Kacheln), laufender Timer mit Stopp, "Heute"-Summen, eigene
Buchungen der letzten 14 Tage mit Ändern/Löschen, eine abgespeckte Nachtrag-Maske (Auftrag, Datum,
Von-Bis oder Dauer als Umschalter, Zeitart, Notiz -- kein Mitarbeiterfeld, keine LV-Position, keine
sichtbaren Pause-Minuten) und Abwesenheitsanträge. Bewusst **ohne** Gruppenbuchung
(Betreibervorgabe: "ein Monteur bucht nur für sich") -- ob künftig ein Kolonnenführer selbst
gruppenbuchen darf, bleibt als offener Punkt festgehalten.

Die Weiche zwischen reduzierter und voller Ansicht hängt an der Rolle, nicht an der URL:
`app/routers/pages.py::time_tracking_page()` rendert unter derselben `/time-tracking`-Adresse
rollenbewusst die passende Vorlage. Das war eine bewusste Entscheidung gegen eine zweite Route
(z. B. `/vor-ort/zeit`) -- es gibt drei unabhängige Linkquellen (`_sidebar.html`,
`_mobile_header.html`, `service_reports.html`s `#timeLink`), eine URL-basierte Weiche hätte jede
einzeln anpassen müssen und wäre bei jedem künftigen neuen Link erneut anfällig gewesen. Damit ist
die volle Seite für `field` jetzt strukturell unerreichbar, unabhängig vom Weg dorthin (Adresse,
altes Lesezeichen, Sidebar-Link, `?order_id=`-Link) -- ein Büro-Konto, das testweise als `field`
unterwegs ist, oder umgekehrt, sieht bei jedem Aufruf exakt das, was die aktuelle Sitzungsrolle
vorsieht.

Die Auftragsauswahl der reduzierten Ansicht nutzt ein neues `list_field_bookable_order_ids()`
(`app/planning.py`) -- dasselbe ±14-Tage-Zeitfenster wie der 1.3.58-Wartungsfinder
(`list_field_relevant_property_ids()`, die gemeinsame Zeitfenster-Logik wurde dafür in
`_relevant_preparation_ids_for_employee()` ausgelagert), auf Aufträge statt Objekte angewendet.
Dabei ein echter, von der Fenstergröße unabhängiger Fund: ein per "Wartung durchführen" gestarteter,
ungeplanter Auftrag hat gar keine `WorkPreparation` (`create_quick_service_order()` legt bewusst
keine an) und wäre in jedem Zeitfenster unsichtbar geblieben. Behoben durch eine ungefensterte
Ergänzung um Aufträge, zu denen der Monteur bereits selbst einen Bericht angelegt hat -- derselbe
zweite Zugriffsweg, den `field_may_access_order()` ohnehin schon kennt. Neuer Endpunkt
`GET /api/field-view/time-tracking/orders` liefert die aufgelöste Liste, self-scoped über
`request.state.erp_user`.

12 neue Tests (`tests/test_v264_field_time_tracking.py`). Volle Suite: 1246/1246. Keine Migration
nötig.

## 1.3.59 – Rechtekonzept: zwei Funde aus einem Sicherheitstest behoben

Ein adversarialer Test gegen eine isolierte Testinstanz (eigene, temporäre Datenbank, ein
synthetisches `field`-Testkonto, danach vollständig gelöscht -- nie gegen die echte
`dachkonzepte_erp.db`) sollte die Negativliste des Rechtekonzepts aus Sicht eines Angreifers
durchgehen, nicht nur aus der eines gutwilligen Nutzers. Zwei echte Lücken, beide behoben, ein
zweiter Durchlauf desselben Tests bestätigt: null "durchgelassen".

**Fund 1, der schwerwiegendere: fremde Berichte lesen und schreiben auf einem gemeinsamen
Auftrag.** `require_field_order_access()` prüfte nur "gehört der Auftrag zu mir", nie "gehört der
Bericht zu mir". Auf jedem Mehrpersonen-Auftrag (Team-Besetzung an der Arbeitsvorbereitung)
konnte ein Monteur mit legitimem Auftragszugriff jeden Bericht eines Kollegen lesen (volles
Schema inkl. Freitext), ändern, löschen und sogar signieren -- dieselbe ungeprüfte Auftragsebene
stand vor PUT/DELETE/sign genauso wie vor Prüfpunkten, Fotos, Material und Mängeln.

Getrennt nach Zugriffsart behoben: Lesen der Berichtsliste (`GET /api/orders/{id}/service-reports`)
bleibt für jeden mit Auftragszugriff erlaubt, aber jetzt pro Bericht statt pro Auftrag -- der
eigene Bericht zeigt weiterhin das volle Schema (zum Bearbeiten unverzichtbar), jeder Bericht
eines anderen Erstellers kommt im bereits bestehenden reduzierten Schema der Wartungshistorie
(`ServiceReportHistoryOut`, neue Funktion `list_reports_for_field()` in `app/service_reports.py`).
Jeder Schreib- und Detailzugriff auf einen KONKRETEN Bericht (PUT/DELETE/sign, Prüfpunkte samt
regenerate/sync, Fotos, Material, Mängel, PDF) verlangt jetzt zusätzlich, dass der angemeldete
Monteur der Ersteller ist -- neue Funktion `require_field_report_ownership()` in
`app/routers/orders.py`, angewendet in `app/routers/service_reports.py` und `app/routers/findings.py`.
Büro/Admin bleiben an keiner Stelle eingeschränkt.

Auf Rückfrage, ob "nur der Ersteller" zu eng ist (arbeiten je zwei Monteure an einem Bericht?):
Betreiberantwort -- in diesem Betrieb schreibt jeder Monteur seinen eigenen Bericht nach getaner
Arbeit, keine Fortführung durch einen Kollegen. Bewusst als betriebliche Festlegung dokumentiert,
nicht als technische Annahme -- ändert sich der Ablauf, ist genau diese eine Stelle auf "alle dem
Auftrag zugeordneten Monteure" zu erweitern.

**Fund 2: fremde Wartung per geratener Vertrags-ID.** `POST /api/maintenance-contracts/{id}/
perform-maintenance` prüfte für Monteure seit 1.3.56 nur die eigene Mitarbeiterverknüpfung, keine
Zuordnung zum Vertrag selbst. Über eine fortlaufende, leicht erratbare ID konnte ein Monteur für
JEDEN Vertrag einen echten Auftrag samt Projekt und vorbereitetem Bericht unter einem ihm
völlig fremden Kunden anlegen. Die ursprüngliche Einstufung ("legt einen Auftrag an, kein
Datenleck, so akzeptiert") ist überholt -- eine Manipulation von Geschäftsdaten über eine triviale
ID-Iteration ist kein tolerierbarer Nebeneffekt. Neue Funktion `field_may_perform_maintenance()`
in `app/maintenance_contracts.py` zieht dieselbe Grenze wie der Vertragsfinder auf `/vor-ort`
(`list_field_relevant_property_ids()`) -- ein Monteur darf eine Wartung nur an einem Objekt
starten, dem er über die Arbeitsvorbereitung tatsächlich zugeordnet ist. Büro/Admin bleiben
unbeschränkt.

18 neue Tests (`tests/test_v263_report_ownership_and_contract_scope.py`), ein bestehender Test
angepasst (die AV-Zuordnung, die "Wartung durchführen" jetzt voraussetzt, gehörte vorher nicht
zum Testaufbau). Keine Migration nötig. Details in CLAUDE.md, Abschnitt "Rechtekonzept" →
"Berichts-Eigentümerschaft" bzw. "Fund: fremde Wartung per geratener Vertrags-ID".

## 1.3.58 – Rechtekonzept, Nachtrag: Vertragsfinder auf /vor-ort ("Wartungen an meinen Objekten")

Letzter offener Punkt aus der 1.3.57-Seitenklassifizierung: "Wartung durchführen" wurde für
Monteure geöffnet (1.3.56), sitzt aber auf der Büro-Vertragsseite (`/maintenance-contracts/{id}`),
die für `field` gesperrt ist -- ein Monteur hatte keinen Weg, einen Wartungsvertrag überhaupt zu
finden, um vor Ort eine ungeplante Wartung zu starten. Auf ausdrückliche Vorgabe NICHT die volle
Vertragsliste öffnen, sondern eine neue Karte "Wartungen an meinen Objekten" auf `/vor-ort`, die
nur die Objekte zeigt, an denen der Monteur aktuell oder in Kürze zu tun hat.

Vor dem Bauen geprüft, wie verlangt: taugt `WorkPreparation.status` als zusätzliches Signal
("offene Arbeitsvorbereitung ODER Zuordnung im Zeitfenster")? Das Feld lässt sich tatsächlich
ändern (`PUT /api/orders/{id}/work-preparation`, Büro-Formular mit fünf Werten) -- kein toter
Code, wie zunächst vermutet. Die reale, lokale Datenbank enthält für die Prüfung aber nur eine
einzige `WorkPreparation`-Zeile, zu dünn für ein Urteil über die Zuverlässigkeit im Alltag.
Entscheidend: eine Kombination mit dem Status hätte das Risiko, das das Zeitfenster gerade
vermeiden soll, an anderer Stelle wieder eingeführt -- eine tatsächlich abgeschlossene, aber nie
manuell auf "abgeschlossen" gesetzte Arbeitsvorbereitung bliebe unabhängig vom Datum sichtbar.
Ergebnis (wie vom Nutzer selbst als Rückfall vorgegeben): das Zeitfenster allein, ohne den Status.

Neue Funktion `app/planning.py::list_field_relevant_property_ids()` -- ein ±14-Tage-Fenster um
eine tatsächliche `PlanningSlot`-Terminierung der AV-Zuordnung (Team oder Einzeln, dieselben
Aufträge wie `employee_assigned_order_ids()`), `WorkPreparation.planned_start`/`planned_end` als
Rückfall ohne Terminierung. Ohne verknüpftes Objekt greift die Hauptadresse des Kunden
(`Property.is_primary_address`), damit ein Wartungsvertrag mit `property_id IS NULL` ebenfalls
gefunden wird. `app/maintenance_contracts.py::list_relevant_contracts_for_employee()` gruppiert
nach Objekt und zeigt alle (nicht archivierten) Verträge, fällige hervorgehoben -- ein Vertrag mit
aktiven Positionen unter `MaintenanceSettings.use_roof_area_items` wird übersprungen, da
"Wartung durchführen" dafür ohnehin ablehnt und ein Button ohne Wirkung schlechter wäre als gar
keiner.

Reduziertes Schema (`FieldMaintenancePropertyGroupOut`/`FieldMaintenanceContractOut`): kein
Kundennummer, keine Straße/PLZ -- nur so viel `property_name`/`customer_name`/Ort, wie zur
Wiedererkennung des Objekts nötig ist. Neuer Endpunkt `GET /api/field-view/maintenance-contracts`
liefert bei fehlender Mitarbeiterverknüpfung oder deaktiviertem Modul "wartungen" bewusst eine
leere Liste statt eines Fehlers -- die Karte auf `vor_ort.html` zeigt dafür einen ruhigen
Hinweistext, nie eine leere Fläche (Muster der beiden bestehenden Karten). Klick auf "Wartung
durchführen" ruft den bereits bestehenden `POST .../perform-maintenance`-Endpunkt und navigiert
direkt zum neuen Bericht. Keine Migration nötig (reine neue Funktionen/ein neuer Endpunkt auf
bereits bestehenden Tabellen). Details in CLAUDE.md, Abschnitt "Rechtekonzept" → "Vertragsfinder
auf /vor-ort".

## 1.3.57 – Rechtekonzept: Seiten-Klassifizierung -- dieselbe Standardverweigerung für Seiten wie für die API

Bis hierhin war ausschließlich die API rollengeprüft -- jede der Seiten-Routen in
`app/routers/pages.py` rendierte ihr Gerüst für jede angemeldete Rolle, unabhängig davon, ob die
API-Aufrufe dahinter überhaupt etwas lieferten. Für einen Monteur bedeutete das: er konnte
`/customers/{id}`, `/finanzen`, `/maintenance-contracts` und jede andere Büro-Seite öffnen und
sah eine leere oder fehlerhafte Ansicht -- kein Datenleck, aber auch keine echte Sperre, nur eine
im Sidebar-Menü versteckte Tür, die trotzdem offen war. Auf ausdrückliche Vorgabe geschlossen:
eine Seite, die eine Rolle nicht öffnen darf, muss serverseitig sperren, nicht nur im Menü fehlen.

`app/permissions.py::require_role()` wird dafür unverändert wiederverwendet (keine neue
Dependency-Art nötig, es braucht nur `request.state.erp_user`) -- jede Seiten-Route bekam
`_role: AppUser = _role_dep` (Büro/Admin) bzw. `_any_role_dep` (jede Rolle). Vier Seiten bleiben
für `field` offen: `/account`, `/vor-ort`, `/time-tracking`, `/orders/{id}/service-reports` --
exakt die vier, die ein Monteur tatsächlich braucht, gespiegelt an der bereits bestehenden
API-Klassifizierung der jeweiligen Fachdomäne. `/users` bekommt eine bespoke, bootstrap-aware
Dependency (`_require_users_page_access()`) statt `require_role(...)` -- derselbe Fall wie
`POST /api/users`: vor dem ersten ERP-Benutzer kann niemand eine Rollenprüfung erfüllen. Neue
`PAGE_AUDIT_EXEMPT`-Liste (`app/permissions.py`) für die vier strukturellen Ausnahmen
(`/login`, `/health`, `/manifest.json`, `/users`).

Ein 403 auf einer Seiten-Route zeigt jetzt `access_denied.html` (bereits in Etappe 1 vorbereitet,
aber nie verdrahtet) statt einer für einen Browser unlesbaren JSON-Antwort -- ein neuer
Exception-Handler in `app/main.py` fängt das ab, jeder andere Fall (API, andere Statuscodes)
läuft unverändert über FastAPIs Standard-Handler. "Zur Startseite" führt rollenabhängig
(`default_home_page_for_role()`, `app/permissions.py`): `/vor-ort` für `field`, sonst `/`, und
`/users` für den anonymen Bootstrap-Fall. Dieselbe Funktion korrigiert auch die Login-Landing
ohne `next` an zwei bisher hartkodierten Stellen (`login_page()`: vorher immer `/`; `login.html`:
vorher immer `/projects`) -- ohne diese Korrektur hätte ein Monteur nach dem Login auf einer nun
gesperrten Seite gestanden.

Ein Nebenfund beim Testen: `tests/test_v256_login_wall_for_pages.py` erzeugte Testkonten mit dem
Rollennamen von vor dem Rechtekonzept (`role="user"`) -- harmlos, solange keine Seite eine Rolle
prüfte, jetzt korrigiert auf `role="office"`. Der Audit-Test (`tests/test_v260_role_audit.py`)
deckt Seiten-Routen jetzt genauso ab wie die API, direkt als harter Test (kein `xfail`-
Zwischenschritt), beide bei null unklassifizierten Routen. Eine zweite Testgruppe belegt
stichprobenhaft die tatsächlich richtige Rollenzuordnung sowie den Exception-Handler selbst
(HTML für Seiten, unverändert JSON für die API). 1199 Tests grün.

Bewusst offen: ein `/vor-ort`-Einstieg, über den ein Monteur einen Wartungsvertrag für eine
ungeplante Wartung findet, ohne die jetzt gesperrte Büro-Vertragsliste zu durchsuchen (Vorschlag
vorgelegt, wartet auf Rückmeldung); der "Auftrag"-Link in `service_reports.html` führt für einen
Monteur jetzt auf `access_denied.html` (kein Datenleck, nur ein unnötiger Zwischenstopp).

## 1.3.56 – Rechtekonzept, Nachtrag zu Teil B: ungeplante Wartung für Monteure, reduzierte Historie, Büro sieht alle Zeiten

Vier Punkte aus der Betreiber-Rückmeldung zu 1.3.55, dazu die Wortwahl an die Vorgabe
angeglichen: ein Monteur sieht einen Auftrag über ZWEI Wege -- Planungsbezug (Team-Besetzung
oder Einzelzuweisung an der Arbeitsvorbereitung) ODER ein selbst angelegter Bericht -- kein
dritter, keine Vertrauensbasis (Auftragsnummern sind fortlaufend, wer eine kennt, kennt alle).

(1) **"Wartung durchführen" für Monteure.** `POST /api/maintenance-contracts/{id}/perform-
maintenance` war seit Teil A Büro/Admin -- ein Monteur, der vor Ort eine ungeplante Wartung
startet, hätte den Weg nicht gehabt. Jetzt für jede Rolle offen; der vorbereitete Bericht trägt
den Anfragenden als Ersteller (`create_maintenance_visit(created_by_employee_id=...)`, dieselbe
`_employee_for_request()`-Regel wie beim Anlegen eines Berichts: Nicht-Admin = eigene
Mitarbeiterverknüpfung, Admin = keine) -- das ist sein Zugriffsweg auf den neu erzeugten
Auftrag, eine Plantafel-Zuordnung gibt es dafür nicht. Ein `field`-Konto ohne
Mitarbeiterverknüpfung wird abgelehnt, der Bericht wäre sonst für niemanden erreichbar. Die
Vertragsdaten selbst (Liste, Detail, Bearbeitung) bleiben Büro. Noch offen: ein Einstieg dazu
auf `/vor-ort` (den Vertrag finden, ohne die Büro-Vertragsseite) -- Teil der ausstehenden
Seiten-Klassifizierung; und jeder Monteur kann den Vorgang für JEDEN Vertrag auslösen (es gibt
keine Zuordnung Monteur ↔ Vertrag), was einen Auftrag anlegt -- Datenintegrität, kein Datenleck,
bewusst so entschieden.

(2) **Wartungshistorie als reduziertes Modell** für `field` (`ServiceReportHistoryOut`,
`list_property_history_for_field()`): Datum, Berichtstyp, Monteur, Prüfergebnisse, Mängel mit
Status -- kein Beschreibungstext, kein Material, keine Unterschrifts-/Vertrags-/Kundenfelder,
keine Erledigungs-Verweise der Mängel. Das PDF eines fremden Berichts bleibt für `field`
gesperrt (es trägt u. a. die Zeitbuchungen der Kollegen); `service_reports.html` zeigt einem
Monteur deshalb Prüfergebnisse und Mängel inline statt des PDF-Links -- erkennbar an der
Anwesenheit von `inspection_items`, keine Rollenlogik im Template. Büro/Admin bekommen
unverändert das volle Modell samt PDF-Link. Entscheidung dabei: die Prüfpunkt-Bemerkung
(`InspectionItem.notes`) zählt zum Prüfergebnis und steht auf dem Kunden-PDF -- keine interne
Bemerkung, deshalb enthalten.

(3) **Büro sieht alle Zeitbuchungen.** Die Eingrenzung auf die eigene Person in
`GET /api/time-entries` gilt jetzt nur noch für `field` (vorher: jeder Nicht-Admin) -- der
1.3.55-Nebenbefund ist damit behoben, `order.html`/`project_folder.html` bekommen für ein
Büro-Konto wieder "alle Buchungen des Auftrags/Projekts", auch ohne Mitarbeiterverknüpfung.
Buchen, Ändern und Löschen bleiben für jeden Nicht-Admin auf die eigene Person begrenzt.

(4) **`sign_report()` unter dem neuen Konzept geprüft.** Die "Rechnung erstellen"-Aufgabe
(`create_task()`) und die Fortschreibung der Vertragsfälligkeit sind reine In-Process-Aufrufe
ohne Rollenprüfung (Rollen-Gates sitzen ausschließlich als `Depends(...)` an Routern) -- kein
Punkt, an dem die Unterschrift eines Monteurs scheitern könnte. Als Ende-zu-Ende-Test
festgehalten: Monteur startet eine ungeplante Wartung, unterschreibt über die echte Route, die
Aufgabe entsteht, die Fälligkeit rückt um zwölf Monate.

## 1.3.55 – Rechtekonzept, Etappe 3 + Rest-Etappe Teil B: Objekt-Filterung für Monteure, Audit-Test bei null

Abschluss der in 1.3.51 begonnenen Klassifizierung: die 65 verbleibenden, aktiv von Monteuren
genutzten Endpunkte (`orders.py`, `service_reports.py`, `findings.py`, `inspection_templates.py`,
`time_tracking.py`) sind klassifiziert, der Vollständigkeits-Audit-Test
(`tests/test_v260_role_audit.py`) steht bei **null** unklassifizierten Endpunkten und ist ab jetzt
ein harter Test (die `xfail`-Markierung aus 1.3.51 ist entfernt) -- ein neuer `/api/`-Endpunkt ohne
Rollenangabe färbt den nächsten vollständigen Testlauf rot. Die neun Einträge in
`ROLE_AUDIT_EXEMPT` (Login, Zwei-Faktor-Einrichtung, eigenes Passwort, `/api/field-view/today`,
PWA-Icon, Bootstrap-Benutzeranlage) bleiben die einzigen rollenlosen Endpunkte, jeder einzeln
begründet.

Kern ist `app/orders.py::field_may_access_order()`, die EINE Definition, wann ein Monteur einen
Auftrag sehen darf. Geprüft, ob die vorgegebene Definition (Plantafel-Team-Besetzung oder direkte
Zuweisung an der Arbeitsvorbereitung) vollständig ist -- war sie nicht, zwei Funde: (1) `/vor-ort`
findet "offene Entwurfsberichte" seit 1.3.0 über `ServiceReport.created_by_employee_id`, ein Weg,
der ohne dritten Zugriffspfad abreißt, sobald das Büro den Monteur umplant oder aus dem Team nimmt
(die Tagesliste zeigte den Entwurf noch, die Berichtsseite hätte 403 geantwortet) -- deshalb ein
dritter, gleichrangiger Weg "eigener Bericht", der bewusst NICHT bootstrappt (den ersten Bericht zu
einem Auftrag kann nur anlegen, wer über Team oder Einzelzuweisung zugeordnet ist; "Wartung
durchführen" legt seinen Bericht ohne Ersteller an). (2) Die Zeiterfassung trug in
`app/time_tracking.py::employee_assigned_order_ids()` bereits eine eigene, zweite Definition
derselben Zuordnung (Auftragsauswahl eines Nicht-Admins) -- jetzt eine reine Weiterleitung auf
`app/orders.py`, damit Zeitbuchung und Berichtszugriff nie auseinanderlaufen. Team-Besetzung wird
an der AV geprüft, nicht am `PlanningSlot`: der Slot trägt nur das Datum, die Zuordnung hängt an
der Arbeitsvorbereitung; die Tagesliste (`list_todays_assignments_for_employee()`) bleibt die
datumsgefilterte Sicht auf dieselben zwei Tabellen. Kein vierter Weg gefunden.

`GET /api/orders/{id}` liefert einem Monteur ein preisfreies `OrderFieldAccessOut` (Auftragsnummer,
Kundenname, LV-Positionen ohne Preise -- exakt, was `service_reports.html`/`time_tracking.html`
lesen; `order_to_dict()` hätte sonst `unit_price`/`line_total`/Summen mitgeliefert), das volle LV
bleibt Büro/Admin. Ohne `customer_id` im reduzierten Schema wird der Kundenname in der
Berichtsseite für Monteure automatisch Text statt Link auf die (Büro-)Kundenseite -- der seit
1.3.51 vorgemerkte offene Punkt, ohne Rollenlogik im Template gelöst. Fremde und nicht
existierende Aufträge antworten für Monteure gleichermaßen 403 (kein URL-Raten von
Auftragsnummern). Wartungshistorie (Anmerkung 2): zeigt gewollt auch fremde, unterschriebene
Berichte desselben Objekts, per Test belegt ohne Preis-/Einkaufs-/Vergütungs-/Kundennotiz-Schlüssel
(auch verschachtelt, inkl. Katalogmaterial). Zeiterfassung (Anmerkung 3): `?order_id=` liefert
einem Monteur NICHT die Buchungen der Kollegen -- die Endpunkte setzten die eigene `employee_id`
für jeden Nicht-Admin schon immer durch, `list_entries()` verknüpft beide Filter mit UND (geprüft,
kein Fund, als Test festgehalten); fremde Zeilen bleiben unveränderbar, Backoffice bleibt
admin-only. Büro/Admin-only innerhalb der Teil-B-Dateien: Auftragsliste, jede Auftragsbearbeitung,
Revisionen, Auftrags-PDF/-Versand, `GET /api/orders/{id}/materials` (Rechnungsentscheidung für
`order.html`), auftragsübergreifende Mängelliste, Bauteil-Mängelhistorie, die gesamte
Prüfvorlagen-Verwaltung (nur die Vorlagenliste bleibt für Monteure lesbar, `service_reports.html`
braucht sie).

Nebenbefund, gemeldet, nicht behoben: dieselbe Selbstbedienungs-Eingrenzung in `GET /api/time-entries`
trifft auch ein `office`-Konto mit Mitarbeiterverknüpfung -- `order.html`/`project_folder.html`
lesen darüber "alle Buchungen des Auftrags/Projekts" (u. a. für "Rechnung aus Aufwand"), ein
Büro-Nutzer ohne Admin-Rolle sähe dort nur seine eigenen. Vorher-Zustand, nicht durch diese
Version verursacht (beide realen Konten sind Administratoren, deshalb bisher unbemerkt), siehe
CLAUDE.md "Bekannte, bewusst offene Punkte".

## 1.3.54 – Rechtekonzept, Rest-Etappe Teil A: 164 weitere Endpunkte klassifiziert

Fortsetzung nach 1.3.51–1.3.53: die verbleibenden ~230 unklassifizierten Endpunkte zerfallen in
zwei Teile (siehe CLAUDE.md "Rechtekonzept" → "Etappenplan"). Diese Version deckt Teil A ab --
Dateien ohne jeden Monteur-Bezug (geprüft: kein Endpunkt wird von `service_reports.html`/
`vor_ort.html`/`_mobile_header.html` aufgerufen), auf Büro+Admin umgestellt: `quotes.py` (22),
`planning.py` (16), `maintenance_contracts.py` (22), `projects.py` (15), `resource_planning.py`
(15, Teams/Ressourcen/Lieferanten), `roof_areas.py` (34, Dachflächen/Bauteile/Schicht-/
Bauteilarten), `properties.py` (4), `inquiries.py` (5), `customer_documents.py` (4),
`project_documents.py` (4), `quick_service_orders.py` (1).

Drei Dateien brauchten dabei eine feinere Prüfung statt eines blanken Sperr-Durchgangs, weil sie
bereits bestehende Selbstbedienungs-Endpunkte mit eigener Eigentümerschafts-Filterung enthalten
-- diese bleiben bewusst für JEDE Rolle offen, nicht nur Büro+Admin, da auch ein Monteur seine
eigenen Anträge/Aufgaben/sein eigenes Dashboard erreichen muss:

- `absence_requests.py`: Abwesenheitsanträge ansehen/stellen/zurückziehen bleibt Selbstbedienung
  für jede Rolle (die bereits bestehende `employee_id`-Filterung sorgt dafür, dass niemand fremde
  Anträge sieht/ändert) -- nur die Freigabe (`review`) bleibt admin-only, wie schon bisher.
- `work_preparation.py`: das Dashboard-Widget "Meine Aufgaben" (`GET /api/work-preparation/tasks`,
  dieselbe Eigentümerschafts-Filterung wie bei Abwesenheitsanträgen) bleibt für jede Rolle offen,
  die eigentliche Arbeitsvorbereitung (Zuordnungen/Material/Teams/Lieferscheine bearbeiten) ist
  Büro+Admin.
- `dashboard.py` (eigenes Widget-Layout, rein per `user.id` isoliert) und `modules.py`/
  `field_view.py`s `GET /api/mobile-settings` (nicht-sensible Ein/Aus-/Konfigurationszustände,
  von jeder Seite clientseitig gebraucht) bleiben für jede Rolle lesbar -- reines Muster wie das
  bereits bestehende `GET /api/settings/option-groups/{key}`.

Der Vollständigkeits-Audit-Test sinkt dadurch von 230 auf 66 unklassifizierte Endpunkte -- die
verbleibenden (Aufträge, Einsatzberichte, Mängel, Prüfvorlagen, Zeiterfassung) sind Teil B und
brauchen zuerst die noch nicht gebaute Objekt-Filterung (`field_may_access_order()`, CLAUDE.md
"Rechtekonzept" → Etappe 3), da sie von Monteuren aktiv genutzt werden und ein blankes
Büro+Admin-Gate den Einsatzbericht-Ablauf brechen würde (exakt der Fehler, der in 1.3.53 bei
`GET /api/employees` bereits einmal passiert ist).

## 1.3.53 – Rechtekonzept: Preisleck bei Monteur-Endpunkten behoben, ein echter Nebenfund

Auf Rückmeldung behoben statt dokumentiert: `GET /api/materials` (für Monteure bewusst offen,
siehe 1.3.52) lieferte weiterhin `purchase_price`/`price_basis` mit -- genau die Einkaufspreise,
die ein Monteur nicht sehen soll. Entscheidung für Weg (a) (ein Endpunkt, rollenabhängige
Antwort) statt eines zweiten, eigenen Endpunkts: geprüft, welche Felder
`service_reports.html`s Materialsuche tatsächlich liest (`id`/`name`/`article_number`/`unit`) --
genau diese vier bildet das neue `MaterialSearchOut` ab. `GET /api/materials` liefert seither für
`field` `list[MaterialSearchOut]`, für Büro/Admin unverändert `list[MaterialCatalogOut]`
(`response_model=list[MaterialCatalogOut] | list[MaterialSearchOut]`, FastAPI/Pydantic wählen
das passende Modell anhand der tatsächlich zurückgegebenen Felder).

Bei der zusätzlich angefragten Prüfung aller für Monteure bewusst offenen Endpunkte auf dasselbe
Muster (Preise/Kosten/Vergütung/interne Notizen in der Antwort, aber nicht in der Oberfläche)
zwei weitere echte Funde:

1. **`GET /api/orders/{order_id}/property`** (seit 1.3.51, für den Einsatzbericht gebaut) lieferte
   die volle `PropertyOut` -- inklusive `notes` (allgemeiner, büro-interner Freitext) und
   `customer_id`, exakt der Kundenkontext, den dieser Endpunkt laut eigener Begründung NICHT
   zeigen sollte. Neues, feldsicheres `PropertyAccessOut` (nur die Felder, die die "Objekt &
   Zugang"-Karte tatsächlich anzeigt: Name/Anschrift/Zugang/Ansprechpartner vor Ort).
2. **`GET /api/employees`** wurde in 1.3.52 blanket auf Büro+Admin gesperrt -- dabei übersehen,
   dass `service_reports.html` (vom Monteur genutzt) darüber sein Mitarbeiter-Auswahlfeld für
   die kompakte Zeitbuchung befüllt (`employees=await api('/api/employees').catch(()=>[])`). Die
   Sperre hätte das Feld für `field` unbemerkt leer gelassen (der Fehler wurde durch `.catch()`
   verschluckt) -- ein echter, in 1.3.52 selbst eingeführter Regressionsfund, kein Preisleck.
   Behoben wie bei den Materialien: `GET /api/employees` bleibt für `field` erreichbar, liefert
   aber `EmployeeNameOut` (nur `id`/`first_name`/`last_name`/`active`) statt der vollen
   `EmployeeOut` mit Lohn-/Gehaltsfeldern und `important_info`. Einzelabruf/Anlegen/Ändern/
   Sachbearbeiter-Liste bleiben für `field` weiterhin gesperrt.

**Bewusst nicht Teil dieser Version**: `GET /api/orders/{id}` liefert weiterhin die volle,
bepreiste Auftrags-LV an jede Rolle (der Endpunkt ist Teil der ~230 noch unklassifizierten
Router aus 1.3.52) -- `service_reports.html` liest davon aktuell nur
Auftragsnummer/Kundenname/-ID und die LV-Positionsliste für das "LV-Position optional"-Feld der
Zeitbuchung, keine Preise. Eine Behebung braucht dieselbe Objekt-Filterung (`field_may_access_order()`,
siehe CLAUDE.md "Rechtekonzept" → Etappe 3), die noch nicht gebaut ist -- eine isolierte
Preis-Ausblendung ohne diese Filterung würde die eigentliche Frage ("darf `field` DIESEN Auftrag
überhaupt sehen") nur verdecken. Gemeldet, nicht verschwiegen.

## 1.3.52 – Rechtekonzept, Etappe 3: der riskante Batch (Finanzen, Kalkulation, Mitarbeiter, Einstellungen, Benutzer, Historie, Aufgaben) + `can()` + Vollständigkeits-Audit

Fortsetzung von 1.3.51, nach Risiko statt Alphabet geordnet (Vorgabe: Geld/Preise/Personendaten
zuerst). Auf Büro+Admin umgestellt, Monteur ausgeschlossen: `settings.py` (24 Endpunkte, davon
drei bewusst weiterhin für jede Rolle offen -- Optionsgruppen-Einzelabruf, Firmenlogo/
Sidebar-Logo-Anzeige, siehe unten), `document_layout.py`, `document_email_templates.py`,
`payment_terms.py`, `tax_keys.py`, `changelog.py`, `catalogs.py`, `labor_rate.py`, `imports.py`,
`audit.py`, `employees.py` (der ursprüngliche Fund der Suche-Bestandsaufnahme:
`hourly_wage`/`effective_hourly_wage`/`annual_gross_wage` sind jetzt kein Monteur-Zugriff mehr),
`services.py`, `catalogs.py`. `materials.py`: Verwaltung Büro+Admin, die Suche
(`GET /api/materials`) bleibt für Monteure offen (Materialerfassung am Einsatzbericht) --
bekannter, bewusst offener Punkt dabei gemeldet: die Suche liefert weiterhin `purchase_price`
mit, ein Monteur sieht darüber Einkaufspreise (siehe CLAUDE.md "Rechtekonzept"). `users.py`:
nur `GET /api/users` (Benutzerliste) neu admin-only gemacht, die übrigen Endpunkte waren es
bereits.

**Aufgaben bleiben für Monteure gesperrt** (bestätigte Entscheidung aus 1.3.51) --
`app/routers/tasks.py`/`app/routers/task_columns.py` auf Büro+Admin umgestellt, dazu die beiden
`/api/tasks/{task_id}/finding`- und `.../create-follow-up-project`-Endpunkte (liegen aus
historischen Gründen in `app/routers/findings.py`, gehören aber inhaltlich zur selben Sperre --
"Vorgang erstellen" aus einer Aufgabe heraus ist ohnehin eine Büro-Aktion am Schreibtisch). Die
übrigen Endpunkte von `findings.py` (Mängel-Workflow während eines Einsatzberichts, von Monteuren
selbst bedient) bleiben bewusst unklassifiziert -- Teil der nächsten Etappe. Dabei ein bereits
vorher bestehender, unabhängiger Code-Fund entdeckt und in CLAUDE.md festgehalten (nicht behoben,
außerhalb dieses Auftrags): `PUT`/`DELETE`/Archivieren/Entarchivieren einer Aufgabe prüfen bis
heute keine Eigentümerschaft, anders als `GET /api/tasks` und die Checklisten-Endpunkte.
CLAUDE.md hält außerdem fest, was für eine künftige Öffnung an Monteure fehlen würde: eine
belastbare Zuweisung an den `AppUser` statt nur an den `Employee`, und ein lückenloser "nur
eigene Aufgaben"-Filter.

**Neuer Jinja-Global `can(current_user, *roles)`** (`app/routers/pages.py`) -- die eine Stelle
für Rollenprüfung in Vorlagen, ersetzt lokale `current_user.role == '...'`-Vergleiche (genau das
Muster, das bei `build_customer_and_meta_block()` zu drei divergierenden Varianten geführt hat,
siehe CLAUDE.md "Kopfbereich"). `_sidebar.html`: Backoffice-Link admin-only wie zuvor (jetzt über
`can()`), Finanzen/Mahnwesen/Stammdaten/Einstellungen-Links sowie der Aufgaben-Link zusätzlich
auf Büro+Admin eingeschränkt -- ein ausgeblendeter Link ist immer sicher, unabhängig vom
Fertigstellungsgrad der Backend-Sperre, da die direkte URL vorher genauso erreichbar war.

**Neuer Test** `tests/test_v260_role_audit.py::test_all_api_routes_have_an_explicit_role_check`
(aus 1.3.51 bereits vorhanden, hier um sechs weitere Nachweis-Tests für den riskanten Batch
sowie zwei für Aufgaben/Kanban-Spalten ergänzt) läuft über alle registrierten Router und meldet
jeden `/api/`-Endpunkt ohne erkennbare Rollenprüfung namentlich -- die unklassifizierten
Endpunkte sanken durch diese Version von 243 auf 230 (der Rest, überwiegend risikoärmer, ist die
nächste, separate Etappe). Sechs Testdateien mit eigenem, gestubbtem Jinja-Environment
(`test_v163`/`test_v249`/`test_v253`/`test_v254`/`test_v255`/`test_v258`) und
`test_v252_deployment_hardening.py` (Zähl-Assertion) mussten dafür um den neuen `can()`-Stub
ergänzt werden.

## 1.3.51 – Rechtekonzept, Etappe 1+2: Fundament, Standardverweigerung, drei Beispieldateien

Vorbereitung für die kommenden Monteurskonten (siehe CLAUDE.md "Rechtekonzept" für die
vollständige Bestandsaufnahme, den Etappenplan und den aktuellen Zwischenstand). Aus zwei
Rollen (`admin`/`user`) werden drei (`admin`/`office`/`field`) -- Bestandskonten (Tobias, Admin)
bleiben unverändert Administratoren. Zentrale, neue Prüffunktion `app/permissions.py::
require_role()`, `app/deps.py::require_admin()` bleibt unverändert bestehen und deckt sich mit
`require_role("admin")`. **Standardverweigerung statt Positivliste**: ein neuer, automatisierter
Test geht jede registrierte `/api/`-Route durch und schlägt mit einer namentlichen Liste fehl,
wenn eine ohne erkennbare Rollenprüfung registriert ist -- ein vergessener Endpunkt fällt dadurch
beim nächsten vollständigen Testlauf auf, nicht erst durch Zufall (siehe CLAUDE.md, neue Regel 11).
Als Nachweis, dass der Mechanismus trägt, sind `customers.py`/`invoices.py`/`reminders.py`
(43 Endpunkte) bereits auf Büro+Admin umgestellt, Monteur ausgeschlossen -- die übrigen, noch
unklassifizierten Endpunkte sind die konkrete Checkliste für die nächste, noch zu bestätigende
Etappe.

Dabei umgesetzt: `Property` bekommt `access_notes`/`site_contact_name`/`site_contact_phone`
(Zugang und Ansprechpartner vor Ort) plus einen neuen, auftragsbezogenen Lesepfad
(`GET /api/orders/{id}/property`) -- ein Monteur soll das über den Einsatzbericht erfahren, nicht
über die Kundenakte. Geprüft, ob Aufgaben heute je einem Monteur zugewiesen werden: nein, in der
echten Datenbank gehen alle zugewiesenen Aufgaben an den Geschäftsführer -- Aufgaben bleiben für
die Monteursrolle deshalb vorerst gesperrt, bis der Bedarf entsteht. `users.html`: drei Rollen im
Auswahlfeld, "Monteur" (die am wenigsten privilegierte) ist jetzt die Voreinstellung statt eines
bare "Benutzer", zusätzlich eine Bestätigungsabfrage beim Anlegen eines neuen Kontos ohne
ausdrücklich gewählte Rolle.

## 1.3.50 – Vier weitere unstyled Links behoben

Nachtrag zu 1.3.49: der dort entfernte "Mein Konto"-Link in der Sidebar hatte keine eigene
Formatierung gehabt. Auf Nachfrage nach demselben Muster im übrigen Projekt gesucht -- vier
weitere, unabhängige Stellen gefunden, an denen ein per JavaScript zusammengesetzter Link die
passende Formatierung nicht bekommen hatte und deshalb als blauer, unterstrichener
Browser-Standardlink statt im einheitlichen Erscheinungsbild erschienen wäre: ein Hinweistext
auf der Kontoseite, ein Verweis in den Kalkulationsgrundlagen der Einstellungen, ein
PDF-Öffnen-Link in der Wartungshistorie eines Einsatzberichts und ein Datei-Öffnen-Link in
der Lieferschein-Tabelle der Arbeitsvorbereitung.

Alle vier jetzt behoben, jeweils mit derselben, bereits an anderer Stelle etablierten,
einfachsten Lösung -- keine Änderung an Aufbau oder Anordnung der betroffenen Seiten, nur die
fehlende Farbgebung ergänzt.

## 1.3.49 – Aufräumen im Fußbereich der Sidebar

Benutzername, "Mein Konto" und "Abmelden" standen im unteren Bereich der Sidebar noch,
obwohl alle drei bereits seit der Topbar (Schritt 2, 1.3.45) über deren Kontoknopf erreichbar
sind -- zwei Stellen für dasselbe verwirren. Entfernt: der untere Bereich zeigt jetzt nur noch
die beiden Schaltflächen für Hell/Dunkel und Ein-/Ausklappen sowie die Versionsnummer.

Das dafür zuständige Element bleibt bestehen, rendert aber nur noch leer -- es wird weiterhin
für den einen verbleibenden Fall gebraucht: eine Sitzung, die während des Browsens abläuft,
bekommt dort ohne Neuladen der Seite ein kompaktes Anmeldeformular zurück. Eine kleine
CSS-Ergänzung verhindert dabei eine unnötig gepolsterte Leerstelle. Toter, dadurch nicht mehr
aufgerufener Code (Escaping-Helfer, Abmelden-Bindung) wurde entfernt statt nur ausgeblendet.
Die Monteursansicht mit ihrem eigenen, unabhängigen Abmelde-Weg bleibt unangetastet.

Nebenbefund: der entfernte "Mein Konto"-Link hatte keine eigene Formatierung und wäre als
blauer Standardlink statt im Design-System erschienen -- erledigt sich durch die Entfernung.
Auf Nachfrage nach demselben Muster gesucht: vier weitere, unabhängige Stellen mit demselben
Fehler gefunden (jeweils ein per JavaScript zusammengesetzter Link, bei dem die passende
Formatierung beim Bauen vergessen wurde) und gemeldet -- Behebung zurückgestellt.

## 1.3.48 – Zwei Fehler in der Anmelde-Umleitung, auf dem Produktivserver gefunden

Zwei reale Beobachtungen aus 1.3.46/1.3.47 behoben. `/login` leitete eine bereits vollständig
angemeldete Person (zweiter Faktor bestätigt) nicht auf das mit `?next=` mitgegebene Ziel
weiter, sondern immer aufs Dashboard. Die konkret gemeldete Beobachtung ("Anmeldemaske
erscheint erneut, obwohl die Sitzung besteht") hatte dabei eine andere, eigentliche Ursache:
der Link "Zur Startseite" auf der Kontoseite sprang bei vorhandenem `document.referrer` per
Browser-Verlauf zurück -- während der Zwei-Faktor-Pflicht zeigte dieser Referrer auf die
noch unangemeldete Anmeldeseite, ein Klick zeigte deshalb ggf. direkt eine gecachte, veraltete
Ansicht, ganz ohne Serveranfrage. Der Link ist jetzt ein einfacher, direkter Verweis auf das
Dashboard.

Zweitens: nach Eingabe und Bestätigung des Codes aus der Authenticator-App landete man auf der
Kontoseite selbst (Passwort ändern, Zwei-Faktor-Status) statt auf dem ursprünglich gewünschten
Ziel. Die Bestätigung führt jetzt weiter zu diesem Ziel bzw. zum Dashboard -- die
Ersteinrichtung des zweiten Faktors bleibt bewusst unverändert auf der Kontoseite, da dort
zuerst die nur einmalig angezeigten Wiederherstellungscodes gesehen werden müssen.

## 1.3.47 – Serverseitige Anmeldeschranke für Seiten

Auf Nutzeranfrage geprüft, wie sich `/` ohne Anmeldung, `/` mit Anmeldung und `/login` bei
bestehender Anmeldung verhalten. Befund: bisher rendierte jede Seite -- auch `/`, `/tasks`,
`/settings` -- ihr Gerüst mit Status 200 unabhängig vom Anmeldestatus, keine Umleitung, kein
Fehler; die einzige Reaktion auf fehlende Anmeldung war ein Login-Formular im Fußbereich der
Sidebar, der übrige Seiteninhalt blieb (nutzlos) stehen. `/` mit Anmeldung zeigte das Dashboard
bereits korrekt (keine separate `/dashboard`-Route, `/` rendert es direkt). `/login` bei
bestehender Anmeldung zeigte die Maske unverändert erneut.

Zwei Behebungen: eine neue, serverseitige Prüfung leitet eine Seitenanfrage ohne angemeldeten
Benutzer jetzt auf `/login` um (ausgenommen `/login` selbst, `/health`, `/manifest.json` und
die Bootstrap-Phase vor der allerersten Kontoanlage); `/login` leitet umgekehrt weiter, wenn
schon jemand angemeldet ist -- aufs Dashboard, oder auf "Mein Konto", falls ein Administrator
den zweiten Faktor noch nicht bestätigt hat.

Auf Nachfrage zusätzlich ergänzt, mit minimalem Aufwand, da die Anmeldeseite den nötigen
Parameter bereits liest: die neue Umleitung merkt sich die ursprünglich gewünschte Seite
(`?next=`) und führt nach dem Anmelden dorthin zurück, statt immer aufs Dashboard.

## 1.3.46 – Mobiler Öffnen-Umschalter für die Sidebar

Echter Nebenbefund aus 1.3.45, behoben vor Schritt 3 (Suche). Auf einem schmalen Bildschirm gab
es keinen erreichbaren Weg, die Off-Canvas-Sidebar zu öffnen -- ihr einziger Umschalter
(`#appSidebarToggle`, unten in der Sidebar) steckte selbst innerhalb des `<aside>`, das im
geschlossenen Zustand komplett unsichtbar ist. Die gesamte Navigation war dadurch auf schmalen
Bildschirmen unerreichbar.

Neuer Umschalter links in der Topbar (`#appTopbarMenuBtn`), außerhalb der Sidebar und deshalb
auch bei geschlossener Sidebar erreichbar -- erscheint nur unterhalb desselben Umbruchpunkts wie
die Off-Canvas-Sidebar selbst, steht vor dem für die kommende Suche (Schritt 3) reservierten
Platz. Klick öffnet, erneuter Klick oder ein Klick auf den Hintergrund schließt, exakt wie
bisher gefordert.

Der alte Umschalter unten in der Sidebar blendet sich dafür unterhalb des Umbruchpunkts
vollständig aus -- auf Mobilgeräten gibt es kein Kollabieren im Desktop-Sinn, nur Auf/Zu, und
zwei Bedienungen für dieselbe Aktion nebeneinander wären nur verwirrend gewesen. Ein neuer Test
sichert gezielt die Ursache des Fehlers ab (der Öffnen-Auslöser liegt außerhalb des Elements,
das er öffnet) -- genau die Art Fehler, die eine reine Struktur-/CSS-Prüfung ohne echten
Browser sonst übersieht.

## 1.3.45 – Umgestaltung der Sidebar, Schritt 2: Topbar

Zweiter von vier geplanten Schritten (Suche und Schnellzugriff folgen einzeln in späteren
Versionen). Eine neue, beim Scrollen sichtbare Leiste (`_topbar.html`) sitzt jetzt oberhalb des
Inhaltsbereichs auf allen 31 Seiten mit Sidebar -- beginnt rechts neben der Sidebar, nie über sie
hinweg, im bestehenden Design-System ohne eigene Farben. Links bleibt in diesem Schritt Platz für
die in Schritt 3 folgende Suche reserviert.

Rechts erscheint ein runder Kontoknopf mit den Initialen des angemeldeten Benutzers -- bei
"Tobias Rödchen" also "TR". Ein neuer, gemeinsamer Helfer (`resolve_account_display()`) liest den
vollen Namen bevorzugt vom über `employee_id` verknüpften `Employee` (Vor-/Nachname), fällt ohne
Verknüpfung auf den Benutzernamen zurück -- bewusst nicht auf das freie `display_name`-Feld, das
sich nicht verlässlich in zwei Namensteile trennen lässt. Ein Klick öffnet ein kleines Menü mit
vollem Namen, "Mein Konto" und "Abmelden"; es schließt sich bei Klick daneben oder mit Escape.
"Abmelden" bleibt zusätzlich unten in der Sidebar, ebenso Benutzername/Versionsnummer und die
beiden 1.3.44-Schaltflächen -- zwei Wege zum Abmelden schaden nicht.

Die Monteursansicht (`/vor-ort`) bekommt bewusst keine Topbar -- sie nutzt `_mobile_header.html`,
das den Namen des Monteurs bereits zeigt und einen eigenen Abmelden-Button hat; ein zusätzlicher,
für den Desktop gedachter Kontoknopf würde der bewusst schmal gehaltenen Feld-Tablet-Ansicht
entgegenwirken. Kollision mit der Sidebar in beiden Engpasszuständen geprüft: die eingeklappte
Desktop-Sidebar (60px) und die mobile Off-Canvas-Sidebar verschieben die Topbar bereits durch die
bestehende Flexbox-Aufteilung korrekt, ohne eigene Sonderbehandlung -- eine geöffnete mobile
Sidebar überlagert die Topbar dabei absichtlich (niedrigeres z-index). Fünfter, ebenso
ausnahmegesicherter Jinja-Global (`account_display()`, Prinzip aus 1.3.42) -- ein DB-Fehler fällt
auf den Benutzernamen zurück statt die Seite mitzureißen.

## 1.3.44 – Umgestaltung der Sidebar, Schritt 1: Kopfbereich und Schaltflächen

Erster von vier geplanten Schritten (Topbar, Suche und Schnellzugriff folgen einzeln in
späteren Versionen). Das Logo stand bisher oben links neben den beiden Schaltflächen für
Hell/Dunkel und Ein-/Ausklappen -- dadurch blieb wenig Breite, ein Logo mit Schriftzug wäre
darin unlesbar klein geblieben.

Das Logo steht jetzt allein im Kopfbereich, waagerecht zentriert, mit der vollen verfügbaren
Breite (die Breitenbegrenzung ist dafür von einem festen 200px-Wert auf `max-width:100%`
umgestellt -- relativ, damit sie nicht erneut zu eng wird, sollte sich die Sidebar-Breite je
ändern). Die einstellbare Anzeigehöhe reicht seither bis 120px (vorher 80), Standardwert von 48
auf 64 angehoben, da der Kopf sich die Breite nicht mehr mit den Schaltflächen teilen muss. Die
eingeklappte Sidebar (60px) bekommt eine eigene, feste, kleinere Logo-Höhe (32px) statt der
einstellbaren -- dort ist ohnehin kaum Platz.

Die beiden Schaltflächen sind in den unteren Bereich gewandert, direkt über dem
Benutzer-/Abmelden-Block. "Mein Konto" bleibt an seiner bisherigen Stelle -- das wandert erst mit
der Topbar in einem späteren Schritt. Geprüft und als Test festgehalten: die Schaltfläche zum
Wiederausklappen bleibt im eingeklappten Zustand garantiert erreichbar (nur der Hell/Dunkel-
Umschalter verschwindet dort, unverändertes, bestehendes Verhalten) -- die Ausnahmesicherheit
der Jinja-Globals aus 1.3.42 ist von diesem rein strukturellen Umbau nicht betroffen und bleibt
unverändert bestehen.

## 1.3.43 – Korrektur: doch ein Schriftzug -- dedizierter Sidebar-Logo-Upload

Die 1.3.39-Diagnose ("kein Schriftzug im Firmenlogo, nur ein einzelnes geometrisches Symbol",
per Bounding-Box-Auswertung des Alphakanals ermittelt) war falsch -- ein echter Screenshot
zeigt "DACHKONZEPTE GmbH"/"RÖDCHEN" deutlich lesbar unterhalb des Dachzeichens. Der Schriftzug
lag der automatisierten Messung räumlich zu nah am Bildzeichen, um getrennt erkannt zu werden.
Damit war die 1.3.39-Schlussfolgerung ("mehr Höhe reicht, kein zweiter Upload nötig") hinfällig.

Neuer, eigener Sidebar-Logo-Upload (`GeneralSettings.sidebar_logo_filename`, eigener Ordner
unter `ERP_DATA_DIR`, zwei neue Endpunkte `POST/GET/DELETE /api/settings/general/sidebar-logo`)
nach dem Muster des bestehenden Firmenlogo-Uploads -- beide teilen sich Speicher- und
Validierungslogik über einen `root`-Parameter. `company_logo.py::sidebar_logo_filename()` löst
jetzt drei Stufen auf: eigenes Sidebar-Logo, sonst Firmenlogo, sonst der Schriftzug
"DACHKONZEPTE" -- und liefert dafür ein `SidebarLogoReference`-Tupel statt eines nackten
Dateinamens, da beide Logos in getrennten Ordnern hinter getrennten Auslieferungsrouten liegen.
Die 1.3.42-Ausnahmesicherheit des zugehörigen Jinja-Globals bleibt dabei vollständig erhalten.
Einstellungen zeigen "Firmenlogo" (PDFs, PWA-Icon) und "Sidebar-Logo" (nur Navigation) jetzt als
zwei klar getrennte Abschnitte, inklusive eines Live-Hinweises, welche Stufe ohne eigenes
Sidebar-Logo aktuell greift.

## 1.3.42 – Zwei Vorfälle beim Ausliefern von 1.3.38–1.3.41 behoben

Beim Einspielen von 1.3.38 bis 1.3.41 lief `alembic upgrade head` auf dem Server ohne geladene
Umgebungsvariablen -- der Bereitstellungsablauf hatte den Schritt "Umgebung laden" verloren.
`alembic/env.py` importierte `DATABASE_URL` bisher über `app.database` (dort ein bewusster,
stiller SQLite-Rückfall für die lokale Entwicklung) -- ohne geladene `.env` griff derselbe
Rückfall auch beim Deployment, die Migration lief scheinbar fehlerfrei durch, traf aber nicht die
echte Datenbank. Aufgefallen ist es erst, als eine fehlende Spalte jede Seite mit 500
beantwortete. Behoben: `alembic/env.py` liest `DATABASE_URL` jetzt unbedingt direkt aus der
Umgebung und bricht mit einer klaren Fehlermeldung ab, wenn sie fehlt -- unabhängig von `ERP_ENV`
(sonst hätte dieselbe fehlende Umgebung auch `ERP_ENV` selbst auf ihren Entwicklungs-Vorgabewert
zurückfallen lassen). Der dokumentierte Bereitstellungsablauf bekommt dafür die beiden
verlorengegangenen Zeilen zurück (`set -a; source .env; set +a` und `alembic current` als
Nachweis, dass die Migration tatsächlich gegriffen hat).

Nachdem die Migration nachgeholt war, legte das Hochladen eines Logos danach jede Seite lahm,
einschließlich der Anmeldeseite -- Notbehelf war ein direkter Datenbank-Eingriff. Ursache: (1)
der Logo-Upload-Endpunkt prüfte nur den vom Client frei wählbaren `content_type`-Header, nicht
den tatsächlichen Dateiinhalt -- neue `company_logo.py::validate_logo_image()` verlangt jetzt,
dass Pillow die Datei tatsächlich dekodieren kann (SVG ausgenommen), der Endpunkt antwortet bei
einem ungültigen Bild mit 400 statt eines später anderswo durchschlagenden Fehlers; (2) keiner
der vier Jinja-Globals, die auf jeder Seite laufen (`get_theme()`, `is_module_enabled()`,
`sidebar_logo_url()`, `sidebar_logo_height_px()`), fing eine Ausnahme ab -- ein DB-Zustand, der
eine davon zum Werfen brachte, beantwortete dadurch JEDE Seite mit 500. Alle vier fallen jetzt bei
jedem Fehler auf einen sicheren Wert zurück (Standard-Akzentfarbe, Modul aktiv, kein Logo, Standard-
Höhe), statt die Ausnahme durchschlagen zu lassen -- ein Jinja-Global, das auf jeder Seite läuft,
darf niemals eine Ausnahme werfen. Siehe CLAUDE.md "Produktivbetrieb" für die vollständige
Herleitung beider Vorfälle.

## 1.3.41 – backup_windows.ps1: Bereinigung nur noch auf eigene Ordner beschränkt

Echter Vorfall, kein vorsorglicher Fix: die automatische Bereinigung (seit 1.1.5, behält nur die
3 jüngsten Backups) nahm bisher JEDEN Ordner unter `C:\DACHKONZEPTE-ERP\Backup\` in die Rotation
auf, nicht nur die vom Skript selbst erzeugten (`v<VERSION>_<Zeitstempel>`). Ein dort ohne Bezug
zu diesem Skript abgelegter Ordner `Server` (Kopien der Server-Sicherungen von
`/home/tobias/backups/`) fiel dadurch bei einem Lauf aus der Rotation und wurde per
`Remove-Item -Recurse -Force` gelöscht -- ohne Papierkorb, unwiderruflich. Kein echter
Datenverlust (dieselben Sicherungen liegen unverändert auf dem Produktivserver), aber ein
Weckruf: die Bereinigung filtert jetzt zusätzlich auf das eigene Namensmuster (`-Filter
"v*_*"`) und rührt nichts anderes mehr an. **Neue Regel (siehe CLAUDE.md Regel 9): unter
`Backup\` dürfen ausschließlich vom Skript selbst erzeugte Ordner liegen** -- alles andere
gehört in einen separaten Ordner außerhalb davon.

## 1.3.40 – Firmenlogo: verkleinerte Anzeige-Rendition für Sidebar/Vorschau

Die real hochgeladene Logo-Datei war 8000×5295px/252KB. Da dieses Projekt ausschließlich
klassische Mehrseiten-Navigation macht (keine SPA), lädt und dekodiert der Browser bei JEDER
Seitenanfrage die vollen 42 Megapixel, nur um sie in der Sidebar auf 24-80px Höhe darzustellen.

`replace_logo()` (`app/company_logo.py`) erzeugt beim Hochladen jetzt zusätzlich zur
unveränderten Originaldatei (weiterhin für PDFs/das PWA-Icon, die beide direkt von der Platte
lesen -- dort zählt die volle Auflösung tatsächlich) eine verkleinerte Anzeige-Rendition
(längste Kante max. 480px, reicht für 80px CSS-Höhe selbst auf einem 3x-Retina-Bildschirm
bequem aus). `GET /api/settings/general/logo` -- der einzige HTTP-Auslieferungsweg, genutzt von
der Sidebar UND der Vorschau in den Einstellungen -- liefert bevorzugt diese Rendition, fällt
auf das Original zurück, wenn keine existiert (SVG, oder ein vor dieser Version hochgeladenes
Logo). Scheitert die Rendition-Erzeugung, bricht der Upload nicht ab. Zusätzlich
`Cache-Control: private, max-age=31536000, immutable` auf der Antwort, sicher dank des
bereits bestehenden `?v=<stored_filename>`-Cache-Brechers in der URL.

Real gemessen (mit der tatsächlichen Logo-Datei, gegen eine isolierte Testinstanz): Original
258.475 Bytes/8000×5295px -- ausgelieferte Rendition 19.530 Bytes/480×318px. Faktor ~13 bei der
Übertragungsgröße, Faktor ~278 bei der Pixelzahl.

## 1.3.39 – Firmenlogo in der Sidebar: CSS-Fehler behoben, Höhe einstellbar

Rückmeldung nach dem ersten echten Einsatz: bei 32px Höhe war ein Schriftzug unter dem
Bildzeichen nicht mehr lesbar.

**Echter, selbst gefundener CSS-Fehler behoben.** Der ursprüngliche Ansatz (`height` +
`max-width` + `object-fit:contain` auf demselben `<img>`) verkleinert bei einem breiten Logo die
Höhe wieder -- die CSS-Ersatzelement-Breiten/Höhen-Auflösung verwirft die feste Höhe, sobald
`max-width` eingreift. Behoben durch Entkopplung: die Breitenbegrenzung (200px) sitzt jetzt auf
einem umschließenden `<span>` mit `overflow:hidden`, das `<img>` selbst trägt nur noch die feste
Höhe -- ein zu breites Logo wird dadurch rechts abgeschnitten statt verkleinert. An einem
synthetischen 1000×60px-Testbild nachgewiesen.

**Anzeigehöhe einstellbar** (24-80px, Standard 48, Feld direkt neben dem Upload in
Einstellungen → Unternehmensstammdaten) -- neue Spalte `GeneralSettings.sidebar_logo_height_px`,
neuer Jinja-Global `sidebar_logo_height_px()`.

**Untersucht, bevor über einen zweiten, eigenen Sidebar-Upload entschieden wurde**: die
tatsächlich hochgeladene Datei (8000×5295px RGBA-PNG) enthält entgegen der ursprünglichen
Annahme ("Bildzeichen mit Schriftzug darunter") **keinen Schriftzug** -- nur ein einzelnes,
durchgehendes geometrisches Symbol (Alphakanal-Bounding-Box lückenlos über die gesamte Höhe).
Ergebnis: mehr Höhe reicht, ein zweiter Upload ist nicht nötig -- vom Nutzer bestätigt, nicht
gebaut.

## 1.3.38 – Firmenlogo in der Sidebar statt des Schriftzugs "DACHKONZEPTE"

Befund vor dem Bauen ergab zwei Überraschungen: `GeneralSettings.logo_filename` stand in der
echten Datenbank auf `NULL` -- es wurde noch nie ein Firmenlogo hochgeladen, obwohl das dafür
zuständige Backend (`app/company_logo.py`, seit 1.0.58, für PDF-Dokumente und das PWA-Icon der
Monteursansicht) seit langem existiert. Und: es gab dafür überhaupt keine Oberfläche -- der
Upload-Endpunkt (`POST /api/settings/general/logo`) wurde von keinem Template aufgerufen,
vermutlich ein Rest aus der 1.0.58-Grundlage für den 1.3.20 entfernten PDF-Layout-Editor. Auf
Rückfrage ergänzt: ein minimales Upload-Feld (Vorschau, Hochladen, Entfernen) in Einstellungen
→ Unternehmensstammdaten, ohne das sich die neue Sidebar-Anzeige nie hätte befüllen oder testen
lassen.

Wie vom Nutzer entschieden: kein zweiter, eigener Sidebar-Logo-Upload -- die Sidebar
(`_sidebar.html`) zeigt dasselbe Firmenlogo wie PDFs/das PWA-Icon, statt des bisherigen reinen
Schriftzugs "DACHKONZEPTE". Bewusst über eine eigene Funktion entkoppelt
(`app/company_logo.py::sidebar_logo_filename()`, mit Existenzprüfung der Datei -- ein
Datenbankeintrag ohne Datei fällt auf den Schriftzug zurück statt auf ein defektes Bild) plus
einen neuen Jinja-Global (`sidebar_logo_url()`, Muster `get_theme()`/`is_module_enabled()`, inkl.
cache-brechendem `?v=`-Parameter): ein späterer, dedizierter Sidebar-Logo-Upload müsste nur diese
eine Funktion umstellen, keine der Aufrufstellen. CSS (`height:32px;width:auto;max-width:160px;
object-fit:contain`) hält jedes Seitenverhältnis unverzerrt und zentriert, verhält sich beim
Einklappen der Sidebar und auf Mobilgeräten wie der bisherige Schriftzug. Ist kein Logo
hinterlegt, bleibt der Schriftzug -- eine leere Stelle wäre schlechter als Text. Die mobile
Kopfzeile der Monteursansicht (`_mobile_header.html`) bleibt bewusst unverändert, war nicht Teil
der Anfrage. Mangels echtem Firmenlogo mit drei synthetischen Testbildern (quadratisch, breit,
hoch) gegen eine isolierte Testinstanz durchgespielt -- Hochladen, Sidebar-Anzeige, Entfernen,
alle drei Seitenverhältnisse byte- und pixelgenau bestätigt; ein echter Browser-Screenshot war in
dieser Umgebung nicht möglich (kein Automatisierungswerkzeug verfügbar).

## 1.3.37 – Produktivbetrieb: Rahmenbedingungen dokumentiert, zwei Nebenbefunde behoben

Das ERP läuft seit dem 14.09.2026 auf einem echten Server (Ionos-VPS, Ubuntu, 2 Kerne, 4 GB RAM,
PostgreSQL, Nginx, Let's Encrypt, `gunicorn` als systemd-Dienst unter `app.dachkonzepte.gmbh`).
Neuer CLAUDE.md-Abschnitt "Produktivbetrieb" hält die daraus folgenden Rahmenbedingungen fest:
die zwei Umgebungen (Entwicklung jetzt ebenfalls gegen die lokale PostgreSQL-Instanz statt
SQLite), das 4-GB-Speicherbudget (beim ersten Anlauf wurden Arbeitsprozesse bei 809 MB vom
System abgeschossen), die Serverumgebung im Einzelnen (Pfade, Datenbanken, Dienst, Sicherung,
Notfallskripte), der Weg einer Änderung auf den Server als kopierbarer Befehlsblock, und was das
für künftige Migrationen bedeutet (Rückweg ist ein Backup-Restore, kein Rückgängig nebenbei) --
mit Verweis auf den bereits gemachten `e057d15af828`-Fund und die 1.3.35-Reparaturrunde als
Beleg, dass das keine abstrakte Vorsicht ist.

Zwei Nebenbefunde vom Server-Aufsetzen behoben: (1) die Verbindungszeichenfolge wurde dort
zunächst mit `postgresql+psycopg2` angelegt, obwohl `requirements.txt` ausschließlich `psycopg`
(Version 3) installiert -- `psycopg2-binary` musste von Hand nachinstalliert werden, ein
zweiter, nirgends dokumentierter Treiber. `requirements.txt` und `.env.example` stellen jetzt
unmissverständlich klar, dass es `postgresql+psycopg` heißen muss. (2) Ein
Microsoft-365-Client-Secret ließ sich nach dem Umzug nicht mehr entschlüsseln (verschlüsselt mit
einem inzwischen anderen Schlüssel) -- CLAUDE.md hält als dauerhafte Regel fest, dass
`data/.erp_secret`/`ERP_SECRET_KEY` niemals gelöscht oder ersetzt werden dürfen, solange
verschlüsselte Werte in der Datenbank stehen; der bereits betroffene Wert muss einmalig über die
Einstellungen neu eingetragen werden.

Dazu die beiden zuletzt zurückgestellten Punkte umgesetzt: `app/main.py` ruft
`Base.metadata.create_all()` nicht mehr auf, wenn die neue Umgebungsvariable `ERP_ENV=production`
gesetzt ist (die Migrationskette ist dort seither die einzige Quelle für das Schema -- genau der
Mechanismus, der den `e057d15af828`-Fund erst ermöglicht hatte, ist damit für die Produktion
entschärft); `backup_windows.ps1` trägt jetzt einen deutlichen Kopfkommentar, dass es
ausschließlich die lokale Windows-Entwicklungsumgebung sichert, nicht den Server (der sein
eigenes `/home/tobias/backup.sh` hat).

## 1.3.36 – PostgreSQL-Umstieg: Datenumzugsskript, erste Runde (nur lokal erprobt)

Erste Runde des eigentlichen Datenumzugs -- nur das Skript bauen und gegen die lokale,
portable PostgreSQL-Instanz ausprobieren. Der Umzug auf den Server bleibt ein eigener,
späterer Schritt.

**`scripts/migrate_sqlite_to_postgres.py`** (neu, neben `reset_admin_2fa.py`). Die reale
`dachkonzepte_erp.db` wird ausschließlich lesend geöffnet -- über SQLites Online-Backup-API in
eine temporäre Kopie gesichert (verträgt sich mit einer parallel laufenden Anwendung) und
zusätzlich per `mode=ro`-URI geöffnet, ein Schreibversuch würde vom Treiber selbst verweigert.
Sicherheitsnetz gegen eine falsch übergebene Zielverbindung: das Skript verweigert den Dienst,
sobald in der Zieldatenbank bereits Daten stehen, außer `--force-truncate` wird ausdrücklich
gesetzt -- das Leeren selbst bleibt dabei auf genau die dem ORM bekannten Tabellen beschränkt,
nie ein pauschales DROP SCHEMA/DATABASE. Ablauf: `alembic upgrade head` gegen das Ziel, Daten
laden (`Base.metadata.sorted_tables`-Reihenfolge, die beiden selbstreferenzierenden Tabellen
`quote_sections`/`order_sections` in mehreren Durchläufen), Fremdschlüssel-Konsistenz der
geladenen Daten prüfen (SQLite erzwingt Fremdschlüssel in diesem Projekt nicht selbst -- ein
eigener Scan deckt etwaige, unter SQLite nie aufgefallene Wanderleichen auf), Sequenzen für
jede Tabelle mit Integer-Primärschlüssel zurücksetzen, Zeilenzahlen Quelle gegen Ziel
verifizieren, verschlüsselte SMTP-/Microsoft-365-/TOTP-Felder probeweise entschlüsseln.

**Echter Fund beim ersten Versuch**: der ursprüngliche Plan, Fremdschlüssel-Trigger während des
Ladens abzuschalten (`ALTER TABLE ... DISABLE TRIGGER ALL`), scheiterte mit
`InsufficientPrivilege` -- die internen, eine Fremdschlüssel-Bedingung durchsetzenden Trigger
lassen sich nur von einem Superuser abschalten, eine gewöhnliche Anwendungsrolle (wie sie auf
einem gehosteten Server zu erwarten ist) hat dieses Recht nicht. Ersetzt durch einen
rechtefreien, mehrstufigen Ladevorgang genau für die beiden betroffenen Tabellen. Siehe
CLAUDE.md "PostgreSQL-Umstieg" für die volle Begründung, warum das über diese eine Migration
hinaus für jedes künftige Skript gilt.

**Lauf gegen die lokale `spielwiese`-Instanz**: 121 Tabellen, 3040 Zeilen, 1,7 Sekunden, 0
Zeilenzahl-Abweichungen, 0 verwaiste Fremdschlüssel. Anschließend die Anwendung tatsächlich
lokal gegen PostgreSQL gestartet und geprüft: Kundenliste (162 Kunden), ein Angebot als PDF
(225 KB), ein Einsatzbericht als PDF (2,7 MB inkl. Fotos), das verschlüsselte
Microsoft-365-Client-Secret weiterhin entschlüsselbar. Wichtigster Test: ein neuer Kunde per
`POST /api/customers` angelegt -- id=163, exakt der nächste freie Wert nach dem bisherigen
Maximum 162, bestätigt die zurückgesetzten Sequenzen unter echter Last. Volle Testsuite
weiterhin 1040/1040 grün.

## 1.3.35 – PostgreSQL-Umstieg: Migrationskette repariert

Erste Reparaturrunde vor dem eigentlichen Datenumzug -- Datenumzug, Backup-Skript-Umbau und die
Abschaltung von `create_all()` im Produktionsbetrieb bleiben ausdrücklich spätere Schritte.

**Fehlende Tabellen `invoices`/`invoice_items` nachgetragen.** Migration `e057d15af828` war ein
echter No-op (nur `pass`/`pass`) -- verursacht durch denselben `Base.metadata.create_all()`-
Mechanismus, der schon im Migrations-Workflow-Abschnitt als Warnung beschrieben ist: die Tabellen
entstanden beim App-Start automatisch aus den ORM-Modellen, bevor die Migration per
`--autogenerate` erzeugt wurde, wodurch Autogenerate keinen Unterschied mehr fand. Unter SQLite
unsichtbar, weil `create_all()` bei jedem Start nachzieht -- auf einer frischen PostgreSQL-
Datenbank ohne diesen Sicherheitsnetz-Aufruf hätte die Kette dagegen mit `NoSuchTableError`
abgebrochen. Migration nachträglich mit dem historischen Spaltenstand befüllt (23 Spalten bei
`invoices`, ohne die 8 später per `add_column` ergänzten; `invoice_items` mit dem vollen
heutigen Schema, da keine spätere Migration diese Tabelle je verändert) -- in-place editiert,
nicht als neue Migration angehängt, da die reale Datenbank bereits weit darüber steht und
Alembic Revisionen nie erneut ausführt.

**Dialektneutrale Fixes.** `datetime('now')` (SQLite-spezifisch) durch gebundene Parameter
ersetzt (zwei Migrationen); Boolean-Literale (`1`/`0` in rohem SQL, unter PostgreSQL strikt
typisiert statt implizit konvertiert) auf gebundene Parameter bzw. `TRUE`/`FALSE`-Schlüsselwörter
umgestellt (sieben Migrationen) -- App-seitige `Column == True/False`-Vergleiche blieben
unangetastet, die übersetzt SQLAlchemy bereits korrekt. `app/audit.py`: `.contains()` (unter
SQLite case-insensitive, unter PostgreSQL case-sensitive) auf `.ilike()` umgestellt.

**Verifiziert, nicht nur behauptet.** Eine lokale, portable PostgreSQL-17-Instanz (ohne
Admin-Rechte, EnterpriseDB-ZIP-Binaries) durchlief `alembic upgrade head` von einer leeren
Datenbank aus vollständig -- alle 55 Migrationen, 122 Tabellen. Dieselbe Kette lief anschließend
gegen eine frische, leere SQLite-Datei durch (keine Regression), und die reale, bereits
vollständig migrierte `dachkonzepte_erp.db` blieb beim erneuten `alembic upgrade head` unverändert
bei ihrem Head-Stand (reines No-op, wie erwartet). Volle Testsuite 1040/1040 grün. Siehe CLAUDE.md
"Migrations-Workflow" für die Einordnung als erster tatsächlicher Beleg, dass die Kette dort läuft.

## 1.3.34 – Anmeldesicherheit für den Onlinebetrieb: Zwei-Faktor-Anmeldung, persistente Sperre, Mein Konto

Vorbereitung auf den frei aus dem Internet erreichbaren Server. Drei Teile, gemeinsam umgesetzt:

**Persistente Anmeldesperre statt In-Memory-Zähler.** Der bisherige Zähler lebte nur im
Arbeitsspeicher eines einzelnen Prozesses -- bei zwei uvicorn-Workern hätte jeder für sich
gezählt (aus fünf zulässigen Fehlversuchen wären zehn geworden), nach jedem Neustart war er
ohnehin leer. Neue Tabelle `failed_login_attempts` (eine Zeile je Fehlversuch, automatisch
aufgeräumt bei jedem neuen Fehlversuch, kein separater Aufräumjob nötig). Zwei unabhängige
Sperren gemeinsam: je Benutzername (5 Versuche/15 Minuten) UND je IP-Adresse (20 Versuche/15
Minuten) -- eine reine Benutzernamen-Sperre ließe sich durch rotierende Benutzernamen umgehen,
eine reine IP-Sperre träfe bei wechselnden Adressen nie. Die Fehlermeldung war bereits vorher
für unbekannten Benutzernamen und falsches Passwort identisch ("Benutzername oder Passwort ist
falsch") -- unverändert, verrät also weiterhin nicht, ob ein Konto existiert.

**Zwei-Faktor-Authentifizierung (TOTP) für Administratoren, verpflichtend.** Nur für
Administratoren (nicht für Monteure, die sich täglich auf dem Fahrzeug-Tablet anmelden und
deutlich weniger Rechte haben) -- Administratoren haben Zugriff auf alle Kunden-, Mitarbeiter-
und Finanzdaten. Neue Abhängigkeiten `pyotp` (MIT) und `qrcode[pil]` (BSD-3-Clause, zieht
`pillow` als Extra -- bereits Pflichtabhängigkeit, kein neues Gewicht) -- reine Pip-Pakete ohne
Systemabhängigkeit, wie zuvor bei `pypdfium2`. Ablauf: Passwort-Anmeldung setzt das normale
Sitzungs-Cookie immer, aber ein zweites, unabhängiges Cookie (`dk_erp_otp_ok`) fehlt zunächst --
ohne dieses zweite Cookie bleiben für einen Administrator ausschließlich "Mein Konto"
(Einrichtung/Code-Eingabe) und Abmelden erreichbar, jeder andere Endpunkt liefert 401. Erst nach
einem erfolgreich geprüften Code (Ersteinrichtung mit QR-Code + Bestätigungscode, oder bei
jedem weiteren Login erneut) wird dieses zweite Cookie gesetzt. Nichts wird als aktiv markiert,
bevor nicht ein echter, von der App gelieferter Code bestätigt wurde -- ein abgebrochener
Einrichtungsversuch (Fenster geschlossen, ohne zu bestätigen) hinterlässt dadurch nie einen
halb aktiven Zustand, ein neuer Versuch überschreibt einfach das alte, nie bestätigte Geheimnis.
Zehn Wiederherstellungscodes werden bei der ersten Bestätigung einmalig angezeigt (gehasht
gespeichert, jeder genau einmal verwendbar). Ein Administrator kann den zweiten Faktor eines
ANDEREN Administrators zurücksetzen (verlorenes/neues Telefon), aber bewusst nicht den eigenen
-- sonst ließe sich die Pflicht über die eigene Benutzerverwaltung wieder abschalten. Gibt es
nur einen einzigen aktiven Administrator, zeigt die Benutzerverwaltung dafür eine deutliche
Warnung (dieser Weg existiert dann praktisch nicht). Für den Fall, dass auch die
Wiederherstellungscodes verloren sind: neues Notfallskript `scripts/reset_admin_2fa.py`, direkt
auf dem Server ausführbar, mit Rückfrage vor dem Zurücksetzen.

**Neue Seite "Mein Konto".** Vorher konnte niemand sein eigenes Passwort selbst ändern -- nur
ein Administrator konnte das Passwort eines ANDEREN Kontos setzen. Jeder angemeldete Benutzer
kann dort jetzt sein eigenes Passwort ändern; Administratoren richten dort außerdem den zweiten
Faktor ein und geben ihn bei jedem Login erneut ein.

## 1.3.33 – Geheimnisse für den Serverbetrieb: ERP_SECRET_KEY/ERP_DATA_DIR tatsächlich genutzt

Direkte Fortsetzung der Git-Einrichtung (siehe README/Betriebsdokumentation): `.env.example` hatte
`ERP_SECRET_KEY`/`ERP_DATA_DIR` bereits vorgesehen, der Code nutzte sie aber nur teilweise.
Bestandsaufnahme vor dem Bauen ergab: `ERP_SECRET_KEY` wurde bereits vorrangig gelesen,
`data/.erp_secret` bereits automatisch nur als Rückfall erzeugt, `DATABASE_URL` funktionierte
bereits vollständig -- lediglich die sieben unabhängigen Upload-Pfade (Firmenlogo,
Briefpapier-Hintergründe, Kunden-/Projektdateien, Dachflächen-Skizzen, Einsatzbericht-Fotos/
-Unterschriften) kannten `ERP_DATA_DIR` nicht, jeder fiel einzeln auf einen eigenen, am
Projektordner verankerten Pfad zurück.

**Neues, gemeinsames `app/paths.py`** mit einer einzigen Funktion `data_dir()` -- von
`app/auth.py` (Verschlüsselungsschlüssel), `app/logging_config.py` (Protokoll) und allen sieben
Upload-Modulen genutzt, statt dass jedes seinen eigenen `ERP_DATA_DIR`-Rückfall mitbringt. Dabei
eine echte, kleine Inkonsistenz behoben: die beiden bereits bestehenden `ERP_DATA_DIR`-Leser
lösten ihren Rückfall relativ zum AKTUELLEN ARBEITSVERZEICHNIS auf, die sieben Upload-Pfade
dagegen relativ zur LAGE DER DATEI SELBST -- heute folgenlos, da jeder bekannte Startweg
(`start_windows.bat`, `pytest`) das Arbeitsverzeichnis ohnehin auf den Projektordner setzt, aber
eine tickende Falle für einen künftigen Server-Start mit einem anderen Arbeitsverzeichnis
(systemd-Unit, Docker-`WORKDIR`). `data_dir()` verankert den Rückfall jetzt einheitlich an der
Lage der Datei, nicht am Arbeitsverzeichnis -- lokal ändert sich dadurch nichts (beide Pfade
waren bei gleichem Arbeitsverzeichnis ohnehin identisch).

**Warnung statt Blockade bei abweichendem Schlüssel**: `data/.erp_secret` entschlüsselt die
bereits gespeicherten SMTP-/Microsoft-365-Zugangsdaten in der Datenbank -- wird auf dem Server
versehentlich ein anderer `ERP_SECRET_KEY` gesetzt als der, mit dem eine übernommene Datenbank
verschlüsselt wurde, werden diese Werte unlesbar. Neue Funktion
`warn_if_secret_key_mismatches_file()`, beim Start aufgerufen: loggt eine deutliche Warnung, wenn
`ERP_SECRET_KEY` gesetzt UND `data/.erp_secret` vorhanden UND beide unterschiedlich sind -- ohne
den Start zu blockieren (ein abweichender Schlüssel ist bei einer frischen Installation normal)
und ohne den Schlüssel selbst jemals auszugeben, auch nicht gekürzt.

`.env.example` um alle sieben `DACHKONZEPTE_*_FILE_ROOT`-Variablen ergänzt (auskommentiert, mit
Hinweis, dass sie nur gebraucht werden, wenn ein einzelner Ordner abweichend von `ERP_DATA_DIR`
woanders liegen soll) -- sichtbar beim Einrichten, ohne gesetzt werden zu müssen.

## 1.3.32 – Objekte: Hauptadressen kennzeichnen und ausblenden

Nach dem Adressimport (1.3.31) bestand die Objektliste in den Stammdaten überwiegend aus reinen
Hauptadress-Kopien (jeder importierte/angelegte Kunde bekommt automatisch ein "Hauptadresse"-
Objekt) -- die eigentlich interessanten, zusätzlichen Objekte (Baustellen, Zweitgebäude) gingen
darin unter.

**Neue, robuste Kennzeichnung statt Namensvergleich**: `Property.is_primary_address` (Boolean,
indiziert) wird ausschließlich dort gesetzt, wo eine Hauptadresse automatisch entsteht --
`create_customer()`/`update_customer()` (`app/routers/customers.py`) und
`_create_customer_from_row()` (`app/address_import.py`), nie über das normale Objektformular.
`update_customer()`s Suche nach der vorhandenen Hauptadresse lief bisher über den Namen
(`p.name == "Hauptadresse"`) -- jetzt über das Flag, mit einem Namens-Fallback plus
Selbstheilung für den Fall, dass eine Zeile aus irgendeinem Grund noch nicht geflaggt ist (sonst
Gefahr einer zweiten, doppelten "Hauptadresse"-Zeile).

**Migration, mit vorab geprüfter Erkennungssicherheit** (wie verlangt, vor dem Schreiben
berichtet): von 163 Objekten in der echten Datenbank tragen 161 den Namen "Hauptadresse" -- bei
allen 161 stimmt zusätzlich Straße/PLZ/Ort exakt mit dem jeweiligen Kunden überein (0 unsichere
Fälle, 0 Abweichungen zwischen Namens- und Adresskriterium). Migration `2fffb80e5567` markiert
deshalb konservativ nur bei **beiden** Kriterien zusammen -- ein Namenstreffer ohne
Adressübereinstimmung wird bewusst NICHT markiert, lieber eine echte Hauptadresse übersehen als
eine echte Liegenschaft fälschlich aus der Objektliste verschwinden zu lassen (siehe
`_resolve_primary_address_property_ids()`, eigenständig testbar nach dem etablierten
Migrations-Testmuster).

**Wo Hauptadressen jetzt ausgeblendet werden**: die Stammdaten-Objektliste
(`master_data.html`) versteckt sie standardmäßig, mit einem Kontrollkästchen "Hauptadressen
anzeigen" zum Wiedereinblenden -- die Suche durchsucht dabei weiterhin ALLE Objekte, auch
versteckte, bevor der Sichtbarkeitsfilter greift (ein Anruf mit nur einer Adresse muss weiter
etwas finden). Dieselbe Behandlung für die Objekt-Filterliste in `findings.html`. Die beiden
Objekt-Auswahlfelder bei Wartungsverträgen (`maintenance_contracts.html`/
`maintenance_contract.html`, `propertyOptionsHtml()`) blenden Hauptadressen aus der Auswahlliste
aus -- die bereits vorhandene Option "— Hauptadresse verwenden —" deckt genau diesen Fall
bereits redundant ab, `contract_to_dict()` liefert für `property_id=None` byte-identisch dasselbe
Ergebnis wie eine explizit gewählte Hauptadresse.

**Wo Hauptadressen bewusst NICHT ausgeblendet werden**: die Objekt-Auswahl bei Projekten/Vorgängen
(`project_folder.html`/`project_form.html`) und bei Anfragen (`inquiries.html`) bleibt
unverändert -- dort erzeugt `NULL` gegenüber einer explizit gewählten Hauptadresse-Zeile ein
tatsächlich unterschiedliches Ergebnis im eingefrorenen Auftrags-Schnappschuss (siehe nächster
Punkt), die Auswahl muss deshalb möglich bleiben. Auf der Kundenseite selbst (`customer.html`)
bleibt jedes Objekt inkl. Hauptadresse sichtbar, nur jetzt über das Flag statt den Namen als
solches markiert.

**Nebenbefund behoben, nicht nur gemeldet**: ein Wartungsvertrag ohne Objekt zeigt
"Hauptadresse" (`contract_to_dict()` synthetisiert das seit 1.2.9), ein daraus per Schnellauftrag
erzeugter Auftrag zeigte dagegen gar kein Objekt -- derselbe Fall, zweimal unterschiedlich
dargestellt. `_copy_quote_scope_to_order()` (`app/orders.py`) schreibt beim Beauftragen jetzt
denselben Hauptadress-Schnappschuss, den `contract_to_dict()` für die Anzeige liefert, statt
`None`. Bestehende Aufträge bleiben unangetastet -- der Snapshot ist eingefroren, nur künftige
Beauftragungen sind betroffen.

## 1.3.31 – Adressimport aus dem Altsystem

Einmaliger Import einer CSV-/Excel-Datei mit Adressen aus dem alten Programm (345 Zeilen, 19
Spalten). Neue Seite `/address-import`, verlinkt aus Einstellungen → neue Gruppe "Importe" (der
XML-Leistungsimport ist als Kandidat vorgemerkt, künftig ebenfalls dorthin zu wandern -- nicht
Teil dieser Version).

**Dreistufiger Ablauf**: Hochladen (CSV oder Excel/.xlsx, neue Abhängigkeit `openpyxl`) → Vorschau
(zeigt Klassifikation je Zeile -- Kunde/Lieferant/unzugeordnet/bereits importiert -- sowie
Auffälligkeiten wie fehlender Name, fehlende Adresse, doppelte oder bereits vergebene Nummer) →
erst nach Bestätigung wird geschrieben. Eine neue Spalte `legacy_address_number` (direkt auf
`Customer` und `Supplier`) erkennt bei einem erneuten Import bereits übernommene Zeilen wieder und
überspringt sie. Zeilen ohne Kunden-/Lieferantennummer landen in einer neuen Arbeitsliste
(Suche + drei Aktionen: als Objekt einem bestehenden Kunden zuordnen, als neuen Kunden anlegen,
verwerfen). Ein Importlauf (`ImportRun`) lässt sich vollständig rückgängig machen, alles-oder-
nichts, solange an keinem dabei erzeugten Kunden/Lieferanten bereits etwas hängt.

**Größere Datenmodell-Änderung als für einen Import erwartet, nach Rückfrage bewusst in Kauf
genommen**: `Customer.name` wird seit dieser Version serverseitig aus neuen Feldern
`salutation`/`title`/`first_name`/`last_name` zusammengesetzt (`last_name` das eigentliche
Pflichtfeld) statt direkt eingegeben zu werden -- betraf 61 Konstruktionsaufrufe in 44
Testdateien, alle auf `last_name` umgestellt, keine Kompatibilitätsbrücke für die alte `name`-Kwarg.
Migration mit Backfill (bestehende Kunden zeigen exakt denselben Namen wie vorher). Zusätzlich neu:
`Customer.country`/`.mobile`/`.email_2` (zweite E-Mail-Adresse, bewusst rein informativ -- der
Versand kennt strukturell nur einen Empfänger je Sendevorgang) und `Property.country`. Alle neuen
Felder sind auch im normalen Kundenformular sichtbar und editierbar, nicht nur über den Import
befüllbar.

## 1.3.30 – Mitarbeiter zurück in die Stammdaten: ein Muster statt zwei Ähnlicher

Direkte Fortsetzung von 1.3.29 -- dieselbe gemeldete Abweichung, zwei weitere Punkte: die
Stammdaten-Navigationsleiste fehlte auf `/employees` (nur ein Zurück-Link als Ersatz), und
Anlegen/Bearbeiten blendeten ein Formular ein statt eine eigene Seite zu öffnen -- bei
Teams/Lieferanten/Fuhrpark/Materialien läuft beides über `master_data_form.html`.

**Vor dem Bauen geprüft**, ob sich `/employees` überhaupt in das bestehende Muster einfügen
lässt (Mitarbeiter wird ein regulärer `master_data.html`-Bereich, Formular über
`master_data_form.html`), statt Navigation und Formularseiten-Aufbau auf der eigenen Seite
nachzubauen. Der Vergütungsrechner -- der einzige Teil, der über ein gewöhnliches Adressformular
hinausgeht -- zerfällt sauber in zwei Teile: aggregierte Kennzahlen (reine Client-Berechnung aus
der bereits geladenen Mitarbeiterliste, ein Listen-Feature) und eine Live-Vorschau des
kalkulatorischen Stundenlohns im Formular (reine Formular-JS-Logik, architektonisch nichts
anderes als die bereits bestehenden dynamischen Team-Checkboxen in `master_data_form.html`). Kein
Feld, kein Endpunkt und keine Interaktion gefunden, die sich dort nicht unterbringen lässt --
Ergebnis vor dem Bauen berichtet und bestätigt, danach umgesetzt.

**Umgesetzt**: Mitarbeiter ist wieder ein regulärer `master_data.html`-Bereich (Kennzahlen-Kacheln
+ Liste, trägt automatisch die volle Stammdaten-Navigation); Anlegen/Bearbeiten laufen über eine
neue `employeeForm()` in `master_data_form.html`, erreichbar unter `/master-data/employees/new`
bzw. `/master-data/employees/{id}/edit`, exakt wie bei jedem anderen Bereich. `employees.html` und
die eigene Route `/employees` entfallen vollständig.

Der Kalkulationsgrundlagen-Link in `settings.html` zeigt bewusst wieder auf
`/master-data#employees` -- **das ist eine bewusste Rücknahme der 1.3.28-Korrektur, keine
wiedereingeschleppte Regression**: die 1.3.28-Korrektur (Umstellung auf `/employees`) war zum
damaligen Zeitpunkt richtig, weil der Hash-View seinerzeit nicht mehr existierte; jetzt gilt das
Gegenteil, weil `#employees` durch diese Version wieder existiert.

**Neues, dauerhaftes Prinzip in CLAUDE.md festgehalten (Regel 10)**: jeder Stammdatenbereich zeigt
beim Einstieg die Liste, trägt die Stammdaten-Navigation, und Anlegen wie Bearbeiten öffnen immer
eine eigene Formularseite -- gilt auch für jeden künftig hinzukommenden Bereich, nicht nur
rückwirkend für Mitarbeiter.

## 1.3.29 – Mitarbeiter-Formular: Liste statt Formular als Einstieg

Gemeldeter Ausreißer: `/employees` zeigte beim Aufruf direkt das Anlegeformular statt zuerst die
Mitarbeiterliste -- anders als jeder andere Stammdatenbereich (Kunden, Objekte, Teams, Fuhrpark,
Lieferanten, Kataloge, Materialien), die alle über `master_data.html` als Liste mit ausgelagertem
Formular laufen.

**Ursache**: `employees.html` bestand von Anfang an (vor dem `master_data.html`/
`master_data_form.html`-Muster und vor der 1.3.26-Mitarbeiter-Migration gebaut) aus einem
zweispaltigen Layout, das Formular und Liste gleichzeitig zeigte, das Formular immer im
Anlegen-Zustand vorbelegt. Der Ausreißer bestand also schon länger, fiel aber erst jetzt auf, seit
die Seite mit 1.3.26 der alleinige Weg zu Mitarbeitern ist.

**Umgebaut, ohne die Seite aufzuteilen**: die Mitarbeiterübersicht ist jetzt die einzige beim Laden
sichtbare Sektion; ein neuer Knopf "+ Neuer Mitarbeiter" blendet das (weiterhin auf derselben Seite
lebende) Formular ein, "Bearbeiten" tut dasselbe für einen bestehenden Datensatz. "Abbrechen" sowie
ein erfolgreiches Speichern blenden das Formular wieder aus und kehren zur Liste zurück -- das
Muster von `master_data_form.html`, das nach jedem Speichern zur Liste zurückspringt, hier ohne
Seitenwechsel. Dabei zwei Meldungen gefunden und mitkorrigiert, die im (jetzt versteckbaren)
Formular unsichtbar geworden wären: die "Gespeichert."-Bestätigung entfällt ersatzlos (die
aktualisierte Liste ist die Bestätigung, entspricht dem Projektstandard), eine Startfehler-Meldung
bekommt ein eigenes, immer sichtbares Element.

**Geprüft, dass nichts verlorengeht**: Vergütungsrechner, `show_on_planning_board` (1.3.26) und
alle übrigen Formularfelder sind unverändert vorhanden -- nur ihre Sichtbarkeit beim Laden ändert
sich. Beim erneuten Vergleich der übrigen Stammdatenbereiche kein weiterer Ausreißer gefunden.

## 1.3.28 – Vierter Fall: Benutzer und Änderungshistorie nur noch in den Einstellungen

Setzt dieselbe Aufräumreihe fort (nach Leistungskatalog, Mitarbeitern, Kalkulationsvorgaben) --
vor dem Ändern geprüft, ob es überhaupt zwei konkurrierende Oberflächen zu vergleichen gibt.

**Ergebnis der Prüfung: nein.** `settings.html` hatte für "Benutzer" und "Änderungshistorie" nie
einen eigenen Datenbereich -- nur einen reinen Navigationslink zu den bereits bestehenden,
alleinigen Seiten `users.html`/`history.html` (kein `data-settings-section`, kein Aufruf von
`/api/users`/`/api/audit-logs`). Anders als bei Mitarbeitern/Kalkulationsvorgaben gab es hier also
keine Gefahr, dass eine Funktion nur in einer der beiden Varianten existiert -- es gibt nur eine.
Die "vollständigere Oberfläche" ist damit trivial die jeweils einzige echte Seite; die Einstellungen
verlinkten bereits vorher darauf.

**Umgesetzt:** Sidebar-Direktlinks "Benutzer" und "Änderungshistorie" entfernt; `users.html` und
`history.html` bekommen eine Rückwärtsnavigation "← Einstellungen" (Muster `/employees`/1.3.26,
`/leistungskatalog`/1.3.27).

**Zwei Nebenbefunde:** ein bei der 1.3.26-Mitarbeiter-Migration liegen gebliebener toter Link in
`settings.html` (`/master-data#employees` -- dieser Hash-View existiert seit 1.3.26 nicht mehr,
der Link fiel seither still auf die Kunden-Ansicht zurück) wurde auf `/employees` korrigiert.
`/time-backoffice` ist ebenfalls doppelt verlinkt, bleibt aber bewusst unverändert: es sitzt in der
täglichen Sidebar-Gruppe (1.3.26-Entscheidung: fachlich Tagesgeschäft), nicht in der System-Gruppe
wie Benutzer/Historie.

Bei der abschließend erneut angefragten Vollprüfung der Sidebar gegen die Einstellungen (alle 14
Ziele gegen alle Menüpunkte abgeglichen) kein weiterer Fund über die beiden genannten Nebenbefunde
hinaus.

## 1.3.27 – Letzter Schritt des Sidebar-Aufräumens: "Leistungskatalog" entfällt

Schließt die aus 1.3.25/1.3.26 verbliebene Lücke, damit der Sidebar-Eintrag "Leistungskatalog"
entfallen kann -- vor dem Bauen erst geprüft, ob überhaupt eine neue Ansicht nötig ist.

**Ergebnis der Prüfung: nein.** `/leistungskatalog` (`app/templates/index.html`) funktioniert
bereits ohne `catalog_id` sinnvoll -- XML-Import und der (seit 1.3.26) reine Verweis auf die
Kalkulationsvorgaben sind ohnehin immer sichtbar, die Leistungsliste lädt ohne Parameter schlicht
alle Leistungen ungefiltert, Suche/Detail/Kalkulation/Verschieben/Kopieren funktionieren
katalogübergreifend identisch. Eine zweite, einfachere Ansicht in den Stammdaten wäre reine
Duplikation gewesen. "Leistungen ansehen" in der Stammdaten-Katalogliste verlinkte bereits seit
1.3.25 korrekt auf `/leistungskatalog?catalog_id=<id>`.

**Umgesetzt stattdessen:** der Sidebar-Eintrag "Leistungskatalog" entfällt; die
Stammdaten-Katalogliste bekommt einen zusätzlichen Link zum parameterlosen Einstieg (Suche,
XML-Import), nach demselben Muster, das "alle Materialien anzeigen" in der Materialkataloge-
Ansicht bereits nutzt; `/leistungskatalog` bekommt eine Rückwärtsnavigation zu den Stammdaten
(Muster `/employees` aus 1.3.26), da die Seite jetzt nur noch von dort aus erreichbar ist.

**Randbefund im selben Zug behoben:** sowohl die Leistungs- als auch die Materialliste hatten eine
mit "Katalog" beschriftete Tabellenspalte, die tatsächlich Aktionen (Bearbeiten/Verschieben/
Kopieren) zeigte, nicht den Herkunftskatalog der Zeile -- beim jetzt neu hinzukommenden
katalogübergreifenden Durchsuchen ohne `catalog_id` fehlte dadurch eine sichtbare Zuordnung. Beide
Tabellen zeigen jetzt eine echte Katalog-Spalte (`ServiceListOut.catalog_name`, bereits seit 1.3.24
vorhanden, bzw. eine neue, client-seitige Auflösung aus dem bereits geladenen
`materialGroups`-Array für Materialien), die bisherige Aktionsspalte heißt jetzt "Verschieben /
Kopieren".

## 1.3.26 – Sidebar aufgeräumt: Mitarbeiter, Kalkulationsvorgaben-Duplikat, Gruppenüberschriften

Setzt die 1.3.25-Sidebar-Bestandsaufnahme um, mit vier vom Nutzer bestätigten Anmerkungen plus
einer mitten in der Umsetzung nachgereichten, ausdrücklich vor jeder Änderung zu prüfenden fünften.

**Mitarbeiter zieht in die Stammdaten um.** Stammdaten → "Mitarbeiter" zeigt jetzt auf `/employees`
(die reichhaltigere, bereits bestehende Oberfläche) statt auf ein eigenes, schlankeres Formular;
der separate Sidebar-Eintrag "Mitarbeiter" entfällt, `master_data_form.html`s Mitarbeiterformular
ist vollständig entfernt. Beim Umbau ein echter, sonst stiller Funktionsverlust gefunden und noch
vor Abschluss behoben: `/employees` kannte die Plantafel-Sichtbarkeit (`show_on_planning_board`)
bisher gar nicht -- ohne Nachrüsten wäre diese Steuerung mit dem alten Formular verschwunden.
`/employees` bekommt außerdem eine Rückwärtsnavigation zu den Stammdaten, da es jetzt nur noch von
dort aus erreichbar ist.

**Kalkulationsvorgaben: vom vermuteten Umzug zum bestätigten Duplikat.** Geprüft, bevor etwas
geändert wurde: die globalen Kalkulationsvorgaben in `/leistungskatalog` und Einstellungen →
"Kalkulationsgrundlagen" schreiben auf dieselbe einzige Datenbankzeile über denselben Endpunkt
(`GET/PUT /api/calculation-settings`) -- kein zweiter, divergierender Datensatz, `build_calculation()`
liest garantiert denselben Wert, den beide Oberflächen zeigen. Die Karte in `/leistungskatalog`
entfällt deshalb zugunsten eines Verweises auf die Einstellungen. Bei der Gelegenheit nach weiteren
solchen Doppelungen gesucht (welche Seiten schreibend, nicht nur lesend, auf einen
Einstellungs-Endpunkt zugreifen) -- keine weiteren gefunden.

**Sichtbare Gruppenüberschriften.** Die beiden Sidebar-Gruppen am Seitenende heißen jetzt
"Stammdaten" und "System", optisch nach dem bereits etablierten Muster von `settings.html`s eigenen
Abschnittsüberschriften.

**Backoffice bleibt bei Zeiterfassung** -- fachlich Tagesgeschäft, admin-only ist eine reine
Sichtbarkeits-, keine Kategorisierungsfrage.

Damit schrumpft die aus 1.3.25 verbliebene Lücke (was fehlt, wenn "Leistungskatalog" eines Tages
aus der Sidebar entfernt werden soll) auf eine Leistungen-Ansicht in den Stammdaten nach dem
Materialien-Muster plus den XML-Import -- als eigener, späterer Schritt in CLAUDE.md festgehalten,
kein Teil dieser Version.

## 1.3.25 – "Leistungen ansehen" führte auf die Startseite

Stammdaten → Leistungskataloge → "Leistungen ansehen" landete auf dem Dashboard statt beim
Katalog -- der Link zeigte auf `/?catalog_id=<id>`, ein Ziel, das diesen Parameter nirgends
auswertet.

Erste Diagnose ging von einer fehlenden Seite aus (die Leistungen-Ansicht wurde geladen, aber
nirgends in `master_data.html` gerendert) und baute dafür probeweise eine neue "Leistungen"-Ansicht
innerhalb der Stammdatenverwaltung. Bei der anschließenden Sidebar-Bestandsaufnahme (separat
angefragt) stellte sich heraus: unter `/leistungskatalog` (Sidebar-Eintrag "Leistungskatalog",
`app/templates/index.html`) existiert bereits eine vollständige, deutlich reichhaltigere
Leistungsverwaltung -- Suche, Bearbeiten-Link, Verschieben/Kopieren zwischen Katalogen,
Kalkulationsdetail mit Materialstückliste, XML-Import, globale Kalkulationsvorgaben -- inklusive
eines bereits funktionierenden `catalog_id`-Parameters. Der eigentliche Fehler war also ein
fehlendes Pfadsegment (`/` statt `/leistungskatalog`), keine fehlende Seite. Die zuvor probeweise
gebaute, redundante Ansicht wurde deshalb wieder entfernt.

Korrigiert: `master_data.html`s "Leistungen ansehen"-Link sowie zwei weitere Vorkommen desselben
Fehlers in `service_form.html` (Redirect nach dem Anlegen bzw. Bearbeiten einer Leistung) zeigen
jetzt auf `/leistungskatalog?catalog_id=<id>`.

## 1.3.24 – Direkteinstieg Dashboard, Katalogauswahl, Position bei pauschaler Abschlagsrechnung

Die drei Punkte aus dem laufenden Betrieb, die zuerst einen Befund verlangten -- alle drei nach
Rückmeldung wie vorgeschlagen umgesetzt.

**Direkteinstieg vom Dashboard zu Aufgabe/Anfrage/Abwesenheitsantrag.** Nach dem Muster von
`?report=` (1.2.22): `tasks.html` (`?task=<id>`) und `inquiries.html` (`?inquiry=<id>`) öffnen
beim Laden direkt den passenden Editor und scrollen dorthin; `time_backoffice.html`
(`?absence=<id>`) markiert die Zeile in der Antragsliste, ohne die bestehende Hash-basierte
Tab-Auswahl anzufassen (der Dashboard-Link setzt beides: `?absence=<id>#absences`). Bewusst drei
eigene, kleine Umsetzungen statt eines gemeinsamen JS-Bausteins -- die wiederverwendbare Logik
wäre eine einzige Zeile (Query-Parameter parsen), das Verhalten danach ist an jeder Stelle
unterschiedlich genug (Editor öffnen und scrollen / nur markieren und scrollen, ohne Tab zu
wechseln), dass eine Abstraktion nichts einspart. Arbeitsvorbereitung und akute Mängel bleiben
unverändert auftragsbezogen verlinkt.

**Katalog-Dropdown im Angebotseditor.** `GET /api/services` liefert jetzt `catalog_id`/
`catalog_name` mit (`ServiceListOut`, `Service.catalog` per `selectinload` mitgeladen). Neues
Dropdown über dem Suchfeld in `quote_editor.html`, befüllt aus `GET /api/catalogs`, mit "Alle
Kataloge" als zusätzlicher Option (= bisheriges Verhalten). Vorbelegt mit dem zuletzt gewählten
Katalog (`localStorage`, je Browser) oder dem ersten. Filterung bleibt bewusst clientseitig (alle
Leistungen sind ohnehin schon vollständig geladen, ein Server-Roundtrip bei jeder Auswahl brächte
keinen Vorteil) -- der bereits bestehende, jetzt weiterhin unbenutzte `catalog_id`-Parameter des
Endpunkts bleibt unverändert funktionsfähig. Jeder Treffer zeigt zusätzlich seinen Herkunftskatalog,
damit zwei ähnliche Leistungen aus unterschiedlichen Katalogen bei "Alle Kataloge" unterscheidbar
bleiben.

**Position bei pauschaler Abschlagsrechnung.** Neue, einzige `InvoiceItem`-Zeile je
`abschlag_pauschal`-Rechnung (`_sync_lump_sum_pauschal_item()` in `app/invoices.py`) -- eine reine
Projektion von `lump_sum_net`/`progress_description`, niemals unabhängig editierbar.
`lump_sum_net` bleibt die alleinige Quelle der Wahrheit für den Rechnungsbetrag
(`compute_invoice_totals()` unverändert); `add_invoice_item()`/`update_invoice_item()`/
`remove_invoice_item()` lehnen jede Änderung an dieser Zeile über den allgemeinen Positionsweg
jetzt ab, damit später niemand versehentlich eine zweite, unabhängig editierbare Zahl für
denselben Betrag baut -- exakt der Fehler, der beim Mahntext (1.3.21) bewusst vermieden wurde.
PDF (`invoice_pdf.py`): eine neue Rechnung mit Projektions-Position zeigt jetzt die reguläre
Positionstabelle statt nur Netto/MwSt./Brutto; die bisherige Überschrift entfällt dabei (der
Text steht bereits als Positionsbeschreibung in der Tabelle, sonst erschiene er doppelt).

Vor dem Schreiben einer Migration geprüft: **2 bereits existierende pauschale
Abschlagsrechnungen** in der Produktionsdatenbank (R-2026-0001, R-2026-0002), **beide bereits
`status='versendet'`**, keine mit einer Position. Entscheidung: **keine Migration** -- eine
nachträglich erzeugte Position an einem bereits versendeten, GoBD-unveränderlichen Dokument hätte
das PDF anders aussehen lassen als beim tatsächlichen Versand. Beide Rechnungen bleiben deshalb
unverändert ohne Position; `invoice_pdf.py` behält dafür den alten Rendering-Pfad (Überschrift +
Summenblock, keine Tabelle) exakt bei -- die Weiche ist nicht der Rechnungstyp allein, sondern ob
tatsächlich eine Position existiert. Ein bereits im Entwurf befindlicher (nicht finalisierter)
pauschaler Abschlag holt die Position automatisch nach, sobald Bezeichnung oder Betrag das
nächste Mal gespeichert werden -- in der echten Datenbank betraf das aktuell keine Zeile (beide
vorhandenen sind bereits versendet).

## 1.3.23 – Breadcrumb Kunde/Projekt/Auftrag, Spaltenkopf-Ausrichtung

Zwei von sechs gemeldeten Punkten aus dem laufenden Betrieb, unabhängig von den anderen vier
umgesetzt (drei davon warten auf Rückmeldung zu vorgelegten Befunden, einer -- Einsatzberichte in
der Projektübersicht -- war bei Prüfung bereits vollständig funktionsfähig, keine Änderung nötig).

**Breadcrumb Kunde → Projekt → [Angebot|Auftrag|Auftrag → Rechnung].** Angebotseditor, Auftrag und
Rechnung hatten keine durchgängige Navigation zurück zum Kunden/Projekt -- der Auftrag hatte
immerhin einen einzelnen "← Projektmappe"-Link, die Rechnung einen einzelnen "← Auftrag"-Link,
das Angebot gar nichts. Neu, nach dem Muster aus `property.html`/`roof_area.html` (1.2.18): ein
`<div class="breadcrumb">` mit anklickbaren Zwischenebenen, aktuelle Seite als reiner Text.
`quote_to_dict()` bekommt dafür `customer_id` (Projekt/Kunde-Name waren schon da),
`invoice_to_dict()` bekommt `order_number`/`project_id`/`project_number`/`customer_id` (kannte
bisher nur `order_id`) -- `order_to_dict()` hatte alles Nötige bereits seit 1.2.20. Die Rechnung
bekommt bewusst eine vierte Ebene (Kunde → Projekt → **Auftrag** → Rechnung, nicht nur drei) --
ihr tatsächlicher fachlicher Elternknoten ist der Auftrag, nicht das Projekt direkt, und
`invoice_detail.html` hatte bisher überhaupt keinen Weg zum Projekt/Kunden. Die bereits
bestehenden Einzel-Links ("← Projektmappe", "← Auftrag") bleiben zusätzlich bestehen.

**"EP/EUR"/"GP/EUR" jetzt tatsächlich über den Werten.** Im Angebot bereits seit 1.3.16 korrekt
zentriert (Kopfzeile inklusive). Bei Auftrag und Rechnung galt die `ALIGN`-Regel für diese beiden
Spalten nur ab Zeile 1 (Positionszeilen) -- die Kopfzeile selbst (Zeile 0) fiel dadurch auf
reportlabs Table-Standard LEFT zurück, während die Werte darunter RECHTS standen: nicht nur nicht
zentriert, sondern nicht einmal gleich ausgerichtet wie die Werte. Nachgemessen
(`pypdfium2`-Zeichenboxen, Beispieldokument mit 100 × 50,00 €): Kopf/Wert-Mittelpunkt lagen beim
Auftrag 9,9mm (EP) bzw. 11,9mm (GP) auseinander, bei der Rechnung 6,9mm bzw. 11,9mm. Auf dieselbe
Zentrierung wie das Angebot umgestellt (`ALIGN` jetzt ab Zeile 0, `CENTER` statt `RIGHT`) --
danach beträgt der Versatz in allen drei Dokumenttypen unter 0,1mm.

## 1.3.22 – Eingefrorene Prüfvorlagenbezeichnung im Einsatzbericht

Letzter loser Faden aus 1.3.12 (CLAUDE.md "Bekannte, bewusst offene Punkte"): der Bericht friert
seit 1.2.16 die Vorlagenversion ein und kopiert die Prüfpunkte physisch, aber die Bezeichnung der
Vorlage selbst wurde weiterhin live über `link.inspection_template.label` gelesen -- eine
Umbenennung der Vorlage hätte sich in der Anzeige eines längst unterschriebenen Berichts
rückwirkend geändert.

Genau nach dem 1.3.12-Muster für Bauteil-/Dachflächennamen behoben: neue, nullable Spalte
`ServiceReportRoofArea.inspection_template_label_snapshot`, physisch beim Anlegen aus
`template.label` befüllt (`_generate_inspection_items_for_areas()`), bevorzugt gelesen
(`_report_roof_areas_to_dicts()`), Rückfall auf den aktuellen Namen nur bei leerem Schnappschuss.
Migration `14b130f9c315` (Wortlaut/Aufbau wie `5149d369dbb6`) befüllt Bestandszeilen aus dem
heutigen Vorlagennamen -- gegen die echte Datenbank angewendet und an allen vier bestehenden
Zeilen stichprobenhaft bestätigt.

Bewusst NICHT auf den Legacy-Zweig gespiegelt (Berichte von vor 1.2.22, über
`ServiceReport.inspection_template_id`): dieselbe Asymmetrie, die `roof_area_name` dort bereits
seit 1.3.12 hat -- diese Spalten werden von `create_report()` für keinen neuen Bericht mehr
beschrieben, ein nachträglicher Schnappschuss würde dort nie mehr etwas einfrieren, was nicht
schon vorher eingefroren war.

Bei der Gelegenheit ein letztes Mal projektweit geprüft, ob im Einsatzbericht noch weitere
Stellen aktuelle statt eingefrorene Daten lesen -- kein weiterer Fund. Mitarbeitername bleibt wie
besprochen ausgenommen (projektweite `TimeEntry`-Konvention, keine für Einsatzberichte
spezifische Lücke).

## 1.3.21 – Mahnwesen vervollständigen (Löschen/Versenden/Bearbeiten)

Zwei gemeldete Lücken im Mahnwesen behoben, ein drittes Risiko untersucht und mit einem
gezielten Hinweis statt einer neuen Erkennungsspalte adressiert.

**Löschen/Versenden in "Alle Mahnungen" angebunden.** `delete_reminder_draft()`/
`DELETE /api/reminders/{id}` existierten bereits und waren korrekt auf Entwürfe beschränkt,
waren aber nur in `invoice_detail.html` und der "Benötigt Aufmerksamkeit"-Tabelle angebunden --
nicht in "Alle Mahnungen", ausgerechnet dort, wo ein Entwurf anhand der Statusspalte erkennbar
ist. `renderAllRows()` in `app/templates/mahnwesen.html` zeigt für Entwürfe jetzt dieselben
Versenden-/PDF-/Löschen-Aktionen wie die andere Tabelle, über dieselben, bereits bestehenden
JS-Funktionen. Geprüft, ob es weitere Mahnwesen-Tabellen mit derselben Lücke gibt:
`invoice_detail.html` war bereits korrekt, Dashboard/Finanzen zeigen nur zusammenfassende
Widgets ohne Zeilenaktionen -- kein weiterer Fund.

**Bearbeiten neu gebaut.** Fehlte bisher an jeder Stelle (Geschäftslogik, Schema, Endpunkt,
Oberfläche). Neu: `update_reminder_draft()` (`app/reminders.py`), Schema `ReminderUpdate`, Endpunkt
`PUT /api/reminders/{id}`. Änderbar sind `text`, `fee_amount`, `new_due_date` -- der Status-Schutz
sitzt in der Geschäftsfunktion selbst (`status != "entwurf"` -> `ValueError` -> 400), nicht nur in
der Oberfläche, exaktes Vorbild `update_report()` beim Einsatzbericht. Eine bereits versendete
Mahnung bleibt unveränderlich. Oberfläche: ein "Bearbeiten"-Knopf bei jedem Entwurf öffnet ein
bereits vorausgefülltes Formular direkt auf der Seite (kein `prompt()`, Regel 4) -- ein geteiltes
Panel in `mahnwesen.html` (von beiden Tabellen aus erreichbar) sowie ein eigenes, kleineres Panel
in `invoice_detail.html`. Der Text bleibt bewusst das ROHE Feld mit unaufgelösten Platzhaltern
(`{mahngebuehr}` usw.), exakt die schon etablierte Konvention aus Einstellungen → Mahnstufen
(`ReminderLevel.text_template`) -- keine neue Bearbeitungskonvention für dasselbe Konzept.

**Zusammenspiel von Mahntext und Zahlen bei einer Bearbeitung -- untersucht und adressiert, ohne
eine neue Spalte einzuführen.** `Reminder.text` ist schon heute nur ein beim Anlegen kopierter,
roher Vorlagen-Schnappschuss mit unaufgelösten Platzhaltern -- `formatted_text` wird bei JEDEM
Lesezugriff frisch aus `text` + den aktuellen Feldwerten zusammengesetzt
(`format_reminder_text()`/`_reminder_placeholders()`), nie gespeichert. Eine Änderung von
`fee_amount`/`new_due_date` über die neue Bearbeiten-Funktion wirkt sich dadurch beim nächsten
Lesen bereits automatisch auf den Fließtext aus, SOLANGE die Platzhalter im Text erhalten
bleiben -- das eigentliche Risiko entsteht erst, wenn jemand einen Platzhalter manuell durch eine
fest eingetippte Zahl ersetzt (dann läuft dieser Wert bei einer späteren Zahlenänderung
unbemerkt auseinander). Bewusst KEINE neue Erkennungsspalte für "manuell bearbeitet" (ein
Abgleich gegen `ReminderLevel.text_template` wäre ohnehin unzuverlässig, da sich die Vorlage
einer Stufe unabhängig von einer bereits erzeugten Mahnung weiterändern kann) -- stattdessen
zwei kleine, rein clientseitige Maßnahmen im Bearbeiten-Panel: (1) `reminderMissingPlaceholderWarning()`
zeigt beim Speichern einen nicht-blockierenden Hinweis, wenn der zu `fee_amount`/`new_due_date`
gehörende Platzhalter im Text fehlt -- gespeichert wird trotzdem immer, es kann gute Gründe für
einen Ersatz geben; (2) die Platzhalterliste im Panel nennt jetzt zu jedem Token seine Bedeutung
statt nur den Token selbst (dabei einen Fehler in der ersten 1.3.21-Fassung korrigiert: sie
listete fälschlich `{mahnstufe}`, das nur für die E-Mail-Vorlagen gilt, nicht für `Reminder.text`).
Begründung in CLAUDE.md "Bekannte, bewusst offene Punkte" festgehalten.

## 1.3.20 – Aufräumen nach dem PDF-Umbau

Der alte, positionsbasierte Angebots-Renderer und alles, was nur noch wegen ihm existierte, ist
entfernt. Reihenfolge: erst die Zusammenführung, dann das Löschen.

**Schritt 1 (Prüfung).** Die 1.3.13-Liste wurde gegen den heutigen Stand geprüft -- alle sechs
Positionen bestätigt. Zwei zusätzliche Funde, nicht auf der Liste: der `PUT .../background/repeat`-
Endpunkt (nur vom alten Editor genutzt) und das `DocumentTableField`-Modell/die Tabelle selbst
(nicht nur die Geschäftslogik-Datei) -- beide mit entfernt.

**Schritt 2 (Zusammenführung).** "quote" ist kein Sonderfall mehr in
`resolve_shared_document_type()` -- fällt wie jeder andere Dokumenttyp auf "default" zurück. Eine
Migration löscht die zuvor eigenständigen "quote"-Zeilen in `document_layout_blocks`/
`document_layout_backgrounds`/`document_page_margins` (downgrade stellt den echten letzten Stand
wieder her). Schreibende Endpunkte akzeptieren nur noch "default", nicht mehr zusätzlich "quote".
Die verwaiste Briefpapier-Datei (nach Pixelvergleich als identisch zu "default"s eigener Datei
bestätigt) wurde von der Festplatte gelöscht. Der Übergangsparameter `suppress_drawn_blocks`
entfällt ersatzlos. Ein neuer Test simuliert beide Zustände (eigene Zeilen vs. Rückfall) und
vergleicht Textextraktion + Seitenzahl -- identisch, bis auf einen nicht messbaren 1mm-Versatz
durch geringfügig unterschiedliche linke/rechte Randbreiten (Gesamtbreite bleibt gleich).

**Schritt 3 (Löschen).** `app/quote_pdf.py`, `app/quote_layout_pdf.py`,
`app/templates/document_layout_editor.html`, `app/document_table_fields.py` sowie das
`DocumentTableField`-Modell/die Tabelle vollständig entfernt, dazu die zugehörigen Endpunkte
(fünf Tabellenfeld-Endpunkte, die `custom_text`-Anlegen/Löschen-Endpunkte, die Vergleichsansicht
`GET /api/quotes/{id}/pdf-layout-preview`, die Editor-Seitenroute). In `quote_editor.html` sind
Button und Checkbox der Vergleichsansicht entfernt -- Entscheidung gegen Beibehalten, da dafür
fast die gesamte gelöschte Liste hätte bestehen bleiben müssen. Referenz-PDFs (1.3.19) sind kein
Ersatz für einen Alt-Vergleich, aber Backup-Stände bleiben ein Notausgang.

Drei Testdateien vollständig gelöscht (100% renderer-/editor-spezifisch), drei weitere gekürzt
(generische Geschäftslogik bleibt, jetzt gegen "default" statt "quote" geprüft). Ein Test ist
ersatzlos entfallen, dessen Prämisse (ein Dokumenttyp ganz ohne Überschreibung) seit der
Zusammenführung keinen realen Anwendungsfall mehr hat. `pytest` vollständig grün (904/904).

## 1.3.19 – Oberer Rand "default" übernommen, Referenz-PDFs, PDF-Umbau abgeschlossen

Letzter Schritt der 1.3.17/1.3.18-Randkorrektur, dann Abschluss des gesamten PDF-Umbaus.

**`top_mm` für "default" auf `25mm`/`40mm` gesetzt** (wie "quote"), nachdem die 1.3.18-Messung
keine Überlappung an vier echten Dokumenten fand -- Code-Standard
(`DOCUMENT_TYPE_MARGIN_OVERRIDES`) und die reale DB-Zeile (`update_margins()`, kein rohes SQL).
Bewusst in Kauf genommene Nebenwirkung: 25mm unterschreitet die Unterkante des generischen,
gezeichneten `logo`-Bausteins (30mm) -- kein neues Risiko, sondern dieselbe, seit "quote"s
eigener 1.3.16-Korrektur unkommentiert bestehende Situation, unschädlich, solange `logo`/
`company_header` (Standard seit 1.3.2/1.3.8) unsichtbar bleiben. Der zugehörige
Regressionstest aus 1.3.2 prüft diese Geometrie seither nur noch für Folgeseiten (40mm, klart
sicher) -- sechs Tests mit hartkodierten 42mm-Erwartungen entsprechend aktualisiert.

**Fünf Referenz-PDFs unter `docs/referenz-pdf/`** -- je ein Dokument aus echten
Produktionsdaten (Angebot, Auftrag, Rechnung, Mahnung, Einsatzbericht), Dateiname mit Version
und Datum. Fester Bezugspunkt für künftige, bewusste Layoutänderungen am gemeinsamen Rahmen --
Details und Pflegehinweis (wann neu erzeugen) in `CLAUDE.md`.

Damit ist der komplette, in `docs/bestandsaufnahme_pdf.md` skizzierte PDF-Umbau abgeschlossen --
alle fünf Dokumenttypen nutzen den gemeinsamen Rahmen (Angebot mit eigenen, noch nicht
zusammengeführten Werten), offen bleibt nur die bereits als ein Schritt gebündelte Aufräumliste
(Entfernen von `quote_layout_pdf.py` + Zusammenführung von "quote" in den "default"-Satz).

`pytest` vollständig grün (979/979).

## 1.3.18 – Randkorrektur "default": unterer Rand behoben, oberer Rand vermessen

Drei Entscheidungen zur 1.3.17-Untersuchung ("Randeinstellungen wirken nicht") umgesetzt.

**`bottom_mm` sofort behoben.** Der generische 20mm-Standardwert für den geteilten "default"-Satz
(Mahnung/Rechnung/Auftrag/Einsatzbericht) unterschritt den real bedruckten Fußbereich desselben
Briefpapiers, das "quote" bereits in 1.3.16 auf 32mm korrigiert hat -- derselbe Fehlertyp wie die
Fußzeile in 1.3.8, hier nur noch nicht aufgetreten. Auf denselben, gegen das echte Briefpapier
vermessenen Wert gesetzt (`32mm`, für beide Seitentypen) -- sowohl im Code-Standard
(`DOCUMENT_TYPE_MARGIN_OVERRIDES`, `app/document_page_margins.py`) als auch in der bereits
gesäten Datenbankzeile (`update_margins()`, kein rohes SQL). Danach an je einem echten Dokument
pro Typ geprüft: Mahnung/Rechnung/Auftrag unverändert in der Seitenzahl, der Einsatzbericht
wuchs von 5 auf 6 Seiten -- geprüft und bestätigt, dass das kein Renderfehler ist (die neue
Seite 6 ist eine saubere, vollständige Fortsetzung, nichts überlappt oder wird abgeschnitten),
sondern die korrekte, erwartete Konsequenz einer zuvor zu knapp bemessenen Sicherheitsspanne.

**`top_mm=42` vermessen und vorgeschlagen, bewusst noch nicht gesetzt.** Der Wert stammt aus
1.3.2 und war zur Kollisionsvermeidung mit den mittlerweile standardmäßig unsichtbaren,
gezeichneten Ersatz-Bausteinen (Logo/Firmenkopf) bemessen, nicht gegen das tatsächliche
Briefpapier. Probeweise auf 25mm (Seite 1, wie "quote") / 40mm (Folgeseiten, wie "quote" --
dort begrenzt nicht die Kopfgrafik, sondern der gezeichnete `continuation_header`-Baustein)
gesetzt, an allen vier Dokumenttypen gerendert und wieder zurückgesetzt (`update_margins()`,
kein Zwischenzustand hinterlassen) -- keine Überlappung gefunden. Vorschlag steht, Entscheidung
noch aus.

**Zwischenlösung auf der Einstellungsseite.** `app/templates/settings.html`, Abschnitt
"Dokumente & Layout": ein neuer, deutlich hervorgehobener Hinweis benennt jetzt, dass die
Einstellungen für Mahnung/Rechnung/Auftrag/Einsatzbericht gelten und das Angebot bis auf
Weiteres eigene, unabhängige Werte hat. Der bestehende, dynamische Rollout-Status-Hinweis wurde
um denselben Zusatz ergänzt. Kein neuer Bedienweg für `document_type="quote"` -- entfällt
ohnehin mit der Zusammenführung.

**Zusammenführung auf die Aufräumliste gesetzt, als EIN Schritt.** Wenn `quote_layout_pdf.py`
entfernt wird, nimmt "quote" im selben Zug am "default"-Rückfall teil, die eigenen quote-Zeilen
werden gelöscht, `suppress_drawn_blocks` entfällt -- keine drei separaten Entscheidungen mehr,
siehe `CLAUDE.md`.

Ein neuer Regressionstest (`test_ensure_default_margins_shared_bottom_matches_the_real_letterhead`,
`tests/test_v229_shared_document_layout.py`) sichert den korrigierten Standardwert für eine
frische Installation ab. `pytest` vollständig grün (979/979).

## 1.3.17 – Währung in den Spaltenkopf, Menge/EH vor Leistung, engerer Kopfbereich

Drei Punkte am Angebots-PDF, alle auch an Auftrag und Rechnung nachgezogen ("gleiche
Beschriftung in allen Dokumenten", wie zuvor bei "Pos.").

**Punkt 1 – Währung raus aus den Wertespalten.** "288,75 EUR" in jeder Zeile wurde zu "288,75" --
die Einheit steht seither nur noch im Spaltenkopf ("EP/EUR"/"GP/EUR"), Vorbild ist das dem
Betreiber bekannte Vergleichsdokument. Neue, kleine Hilfsfunktion `money_bare()`
(`app/document_pdf.py`) neben dem bestehenden `money()` -- der Summenblock (Nettosumme/MwSt./
Brutto) bleibt bei `money()` mit Währung, da sie dort nur wenige Male auftaucht. Die Rechnung
hatte für dieselbe Spalte bisher abweichend "Betrag" statt "GP" stehen -- im selben Zug auf
"GP/EUR" vereinheitlicht (dieselbe Größe, nur eine ältere, nie angeglichene Eigenbezeichnung).
Die Übertragszeile des Angebots (laufende Summe über Seitenumbrüche, seit 1.3.15) folgt derselben
Konvention: sie liegt IN der GP-Spalte und zeigt den Wert deshalb ebenfalls ohne Währungssuffix.

**Punkt 2 – Menge/EH vor die Leistung.** Neue Spaltenreihenfolge Pos., Menge, EH, Leistung,
EP/EUR, GP/EUR (vorher: Pos., Leistung, Menge, EH, EP, GP) -- ebenfalls nach dem
Vergleichsdokument, dessen gemeinsame Menge/Einheit-Überschrift "Menge Einh." hier per `SPAN`
über beide Spalten übernommen wird. Menge rechtsbündig, EH linksbündig mit knappem
Zwischenpolster direkt daneben, damit z.B. "1,25 m²" wie eine zusammengehörige Einheit wirkt statt
wie zwei beliebige Zellen. Betrifft `app/quote_framed_pdf.py`, `app/order_pdf.py` und
`app/invoice_pdf.py` gleichermaßen -- Fortsetzungszeilen langer Positionstexte im Angebot
verankern ihren Text weiterhin unter der (jetzt verschobenen) Leistungsspalte, nicht unter Pos.

**Kopfbereich: Absenderzeile enger an die Anschrift.** Der Abstand zwischen der kleinen,
unterstrichenen Absenderzeile (DIN 5008) und der Empfängeranschrift darunter war mit 2mm zu
großzügig bemessen -- beide sollten als ein zusammengehöriger Block wirken, nicht wie zwei
getrennte. Auf 0,8mm reduziert in `build_din5008_header_block()` (`app/document_pdf.py`) --
betrifft dadurch automatisch alle vier Dokumenttypen, die diesen gemeinsamen Baustein nutzen
(Mahnung, Rechnung, Auftrag, Angebot).

Bestehende Tests an die neue Spaltengeometrie angepasst (Positionen der Fortsetzungs-Markierung
und der "Leistung"-Spalte verschoben sich durch den Reorder), Mindestabstand Menge/EH in den
bereits bestehenden Rechnungs-/Auftragstests bewusst von 1,0mm auf einen kleineren, aber weiterhin
sichtbaren Wert gesenkt -- passend zum neuen, absichtlich engen Erscheinungsbild. Mehrere neue
Tests ergänzt (Währung nur im Kopf/Summenblock, Spaltenreihenfolge, Menge/EH-Abstand, verkleinerter
Absenderzeilen-Abstand). `pytest` vollständig grün (978/978).

Im selben Zug eine gemeldete, mögliche Ursache für "Randeinstellungen wirken scheinbar nicht"
untersucht (noch ohne Codeänderung, siehe Rückmeldung an den Betreiber): die Einstellungsseite
"Dokumente & Layout" schreibt beim Speichern von Rändern ausschließlich auf `document_type=
"default"` -- für "quote" (das eigene, nie am Rückfall teilnehmende Randzeilen hat, seit 1.3.6)
gibt es dort keinen Bedienweg. Zusätzlich unabhängig gefunden: der reale Fußbereich des
hinterlegten Briefbogens reicht ca. 27mm von unten hoch (identisch zu der für "quote" in 1.3.16
bereits korrigierten Messung) -- der geteilte "default"-Rand (`bottom_mm=20`) unterschreitet das
weiterhin, ein am Seitenende eng gesetztes Dokument (Mahnung/Rechnung/Auftrag/Einsatzbericht)
kann deshalb in den bedruckten Fußbereich laufen.

## 1.3.16 – Fünf Feinheiten am Angebots-PDF: Ränder, Ausrichtung, Spaltenbreite, Beschriftung

An A-2026-0016 beobachtet, alle fünf umgesetzt.

**Ränder neu gemessen statt geschätzt.** Unterer Rand (Seite 1 UND Folgeseiten) von 50mm auf
**32mm**: der tatsächliche Fußbereich des echten Briefbogens endet bei 28mm (Pixelanalyse wie
1.3.12/1.3.15 für die Kopfgrafik, +4mm Sicherheitsspanne). Oberer Rand Seite 1 von 17mm auf
**25mm** -- hier vorher geprüft, ob es sich um dieselbe, für alle Dokumenttypen geteilte
Einstellung handelt: nein, "quote" behält seine eigenen, unabhängigen Randzeilen
(`resolve_shared_document_type()` lässt "quote" nie am "default"-Rückfall teilnehmen, den
Mahnung/Rechnung/Auftrag nutzen) -- eine Änderung hier hat auf die anderen drei Dokumenttypen
keine Auswirkung, es gab dafür keinen Vorher-Nachher-Vergleich zu zeigen. Zusätzlich geprüft, ob
überhaupt eine echte Überlappung vorlag: nein -- die Absenderzeile (x=18-88mm) und die tiefer
reichende Kopfgrafik (x=97-113mm, bis 30,8mm) liegen in unterschiedlichen Spalten, kein
Pixel-Overlap. Die 25mm sind eine bewusste Weißraum-/Komfortentscheidung, keine Fehlerbehebung.
Beide Werte über `update_margins()` gesetzt (kein rohes SQL), am echten Angebot vorher probeweise
gerendert und wieder zurückgesetzt, bevor endgültig übernommen wurde.

**Menge/EH/EP/GP zentriert** (Betreiberwunsch) -- fachlicher Hinweis mitgegeben, wie verlangt:
rechtsbündig ist bei Geldbeträgen üblich, weil Dezimalstellen dann untereinanderstehen; trotzdem
wie gewünscht umgesetzt, inklusive der Spaltenköpfe.

**Positionsspalte verschmälert, Gewinn vollständig an "Leistung".** Die längste tatsächlich in
der Datenbank vorkommende Positionsnummer ist 7 Zeichen (z.B. "01.0030") -- bei Helvetica 8pt
~11mm breit. Spalte von 23mm auf **15mm** verschmälert (11mm Text + Zellenpolster + Sicherheits-
spanne); da "Leistung" als `content_width` minus Summe der übrigen Spalten berechnet wird, fließt
die komplette Differenz automatisch dorthin: bei quote's Satzspiegelbreite (176mm) von 73mm auf
**81mm**, ohne eigene Rechnung. Nur für das Angebot geändert -- Auftrag/Rechnung behalten ihre
eigene, unveränderte 23mm-Breite, das war nicht angefragt.

**Spaltenüberschrift "OZ" → "Pos.".** Auftrag trug tatsächlich dieselbe Überschrift ("OZ") und
wurde mitgeändert. Die Rechnung dagegen zeigte gar nicht "OZ", sondern bereits "Position" (seit
1.3.9) -- der ursprüngliche Verdacht ("dieselbe Überschrift") traf für die Rechnung also nicht
zu, das erklärte Ziel ("alle Dokumente gleich beschriftet") aber schon: auch dort auf "Pos."
vereinheitlicht. Der alte, nur noch als Vergleichsansicht erreichbare `quote_layout_pdf.py`
bleibt bei "OZ" -- entfällt ohnehin mit ihm, siehe Liste der Aufräumschritte.

## 1.3.15 – Große Leerräume behoben: lange Positionstexte brechen jetzt zeilenweise um

Letzter offener Punkt aus 1.3.14. reportlab kann eine Tabellenzeile nur als Ganzes umbrechen --
verifiziert direkt am reportlab-Quelltext (`Table._splitRows()`s `doInRowSplit`-Zweig splittet
ausschließlich rohe, mehrzeilige Strings, keine `Paragraph`-Flowables). Jede Position ist deshalb
jetzt eine unteilbare Kopfzeile (OZ/Kurztext/Menge/EH/EP/GP, wie gefordert nie von ihrem Preis
getrennt) GEFOLGT von einer eigenen Tabellenzeile je durch `\n` getrenntem Absatz im Langtext --
reportlab kann jetzt zwischen jeder dieser Zeilen umbrechen, auch mitten in einer Position, nicht
nur zwischen zwei Positionen. Auswirkung auf die Übertragslogik minimal: Fortsetzungszeilen
tragen die laufende Summe unverändert weiter, exakt wie die bereits bestehenden Titelzeilen es
tun -- keine Änderung an `_CarryForwardItemsTable.split()`s Kernlogik.

**Erkennbarkeit über den Seitenumbruch hinweg.** Eine Fortsetzungszeile, die zufällig eine neue
Seite eröffnet, hätte dort weder OZ-Nummer noch Kurztext -- sie könnte wie ein eigenständiges
Fragment aussehen. `split()` erkennt diesen Fall jetzt (über eine neue, parallel zu
`row_cumulative` geführte `row_kind`-Liste) und schiebt einen kleinen, kursiven Hinweis
"(Fortsetzung zu Position {OZ})" vor die Fortsetzungszeile, wenn der Umbruch dort tatsächlich
hinfällt -- nur dann, nicht auf jeder Fortsetzungszeile, sonst wäre er auf den meisten Seiten
überflüssiges Rauschen. Die Trennlinie zwischen Positionen (vorher blanko auf jeder Zeile) sitzt
jetzt ausschließlich nach der LETZTEN Zeile eines Positions-Blocks, nicht mehr zwischen der
Kopfzeile und ihren eigenen Fortsetzungszeilen -- sonst hätte jede Fortsetzungszeile wie eine
neue, eigenständige Position ausgesehen.

**Reduziertes Zellenpolster für Fortsetzungszeilen** -- ohne diese Korrektur wuchs A-2026-0016
entgegen der eigentlichen Absicht von 11 auf 12 Seiten: das volle 4pt/4pt-Polster kam vorher nur
einmal pro Position vor (ein einziger mehrzeiliger Paragraph mit normalem Zeilenabstand), jetzt
einmal PRO Absatz. Mit auf 0pt/1pt reduziertem Polster für Fortsetzungszeilen sinkt die
Seitenzahl stattdessen auf 10 (von ursprünglich 11 vor dieser Version).

**Nachgemessen, nicht nur behauptet.** Leerraum am Seitenende (ohne die letzte Seite, die
strukturbedingt immer einen Rest zeigt) vorher: bis zu 31 % der Seitenhöhe auf mehreren Seiten
(vier Seiten mit 21–31 % Leerraum). Nachher: eine einzige verbleibende Seite mit 7 % --
alle anderen füllen sich vollständig. Ende-zu-Ende an einem eigens gebauten, absichtlich langen
Fließtext bestätigt: die Fortsetzungs-Kennzeichnung erscheint zuverlässig genau dort, wo der
Umbruch tatsächlich mitten in einer Position landet.

**Bewusst nicht gelöst**: ein Langtext ganz ohne eingebettete Zeilenumbrüche bleibt weiterhin
eine einzige, unteilbare Zeile -- echtes Umbrechen mitten in einem durchgehenden Absatz würde
die von reportlab bereits umbrochenen Zeilen aus einem gelayouteten `Paragraph`-Objekt
extrahieren (kein dokumentiertes öffentliches API dafür, versionsabhängige interne
Datenstruktur) -- die Fragilität stünde in keinem Verhältnis zum Gewinn gegenüber der bereits
deutlich wirksameren `\n`-Aufteilung. Als bekannter, akzeptierter Punkt in CLAUDE.md vermerkt,
damit sich niemand in einem Jahr fragt, warum ausgerechnet diese eine Position noch am Stück
umbricht.

## 1.3.14 – Drei echte Funde am neuen Angebots-Renderer (A-2026-0016), einer noch offen

An einem echten, zehnseitigen Angebot gemeldet, direkt gegen die Produktionsdatenbank
nachvollzogen. Zwei der drei Funde sind behoben, der dritte (große Leerräume durch
unteilbare Positionszeilen) bleibt bewusst offen -- Vorschlag steht, Bau erst nach Rückmeldung.

**Übertrag fehlte scheinbar -- war aber ein zweites, echtes Problem.** Beim Nachbauen zeigte
sich: die Übertragszeile war nicht komplett verschwunden, sondern `carry_out_row`/`carry_in_row`
landeten an manchen Seitenumbrüchen BEIDE auf der alten Seite statt die neue zu markieren --
reportlabs `Frame.add()` platziert jedes von `split()` zurückgegebene Element dort, wo gerade
noch Platz ist, und nach einer nur einzeiligen Höhenreservierung reichte der Rest oft für beide
winzigen Zeilen. `_CarryForwardItemsTable.split()` (`app/quote_framed_pdf.py`) fügt jetzt ein
`PageBreak()` zwischen beiden ein -- reportlab erkennt das auch dann, wenn es aus einem
split()-Ergebnis stammt, nicht nur aus der ursprünglichen Story. Der ursprünglich gemeldete
Verdacht (Abschnittsgrenzen statt Tabellenmitte) traf nicht zu; das ohnehin schon
lückenlos gebaute Übertrags-System selbst war nicht die Ursache.

**Zwei Doppelungen im Inhalt, beide Datenfragen, nicht Renderfehler.** (a) Kundenname und
Ansprechpartner sind beim echten Kunden identisch ("Wolfgang Rödchen" zweimal) --
`build_quote_framed_pdf()` unterdrückt die Ansprechpartner-Zeile jetzt, wenn sie (getrimmt,
ohne Groß-/Kleinschreibung) dem Kundennamen gleicht. (b) `outro_text`/`outro_text_2` trugen bei
diesem Angebot Wort für Wort denselben Schlusssatz -- behoben in der gemeinsamen
`build_payment_tax_closing_block()` (`app/document_pdf.py`), nicht nur im Angebot: `outro_text_2`
wird unterdrückt, wenn er exakt `outro_text` entspricht. Betrifft dadurch auch den Auftrag
(`order_pdf.py`), der dieselbe Funktion nutzt -- dort bisher nicht beobachtet, aber derselben
Gefahr ausgesetzt. Ein dritter, gemeldeter Verdacht (Positions-Kurz-/Langtext scheinbar doppelt)
bestätigte sich als reines Datenproblem: bei 17 von 25 Positionen dieses Angebots beginnt
`long_text` wortgleich mit `short_text` -- offenbar wurde beim Anlegen der Kurztext in den
Langtext hineinkopiert und dahinter weitergeschrieben. Nicht verändert, wie verlangt.

**Große Leerräume am Seitenende -- Ursache gefunden, Lösung vorgeschlagen, noch nicht gebaut.**
reportlab kann eine Tabellenzeile nur als Ganzes umbrechen, nie mitten im Zelleninhalt --
verifiziert direkt am reportlab-Quelltext (`Table._splitRows()`s `doInRowSplit`-Zweig splittet
ausschließlich rohe, mehrzeilige Strings, keine `Paragraph`-Flowables, wie sie für Kurz-/
Langtext hier verwendet werden). Passt eine Position mit langem `long_text` nicht mehr
vollständig auf die restliche Seite, wandert die komplette Zeile (Kopf UND Langtext) auf die
Folgeseite, die alte Seite bleibt bis zu einem Drittel leer -- bestätigt per Bildvergleich, UND
zwar identisch im alten UND im neuen Renderer. Vorschlag (noch nicht umgesetzt): jede Position
wird eine Kopfzeile (OZ/Kurztext/Menge/EH/EP/GP, bleibt als Ganzes unteilbar) PLUS eine eigene
Tabellenzeile je durch Zeilenumbruch getrennten Absatz im Langtext -- an echten Positionen dieses
Angebots geprüft (eine mit 14 eingebetteten Zeilenumbrüchen, also 15 möglichen zusätzlichen
Umbruchstellen). Auswirkung auf die Übertragslogik: minimal -- Fortsetzungszeilen tragen die
laufende Summe unverändert weiter, exakt wie die bereits bestehenden Titelzeilen es tun, keine
Änderung an `split()` selbst nötig.

## 1.3.13 – Letzte Etappe des PDF-Umbaus: das Angebot wechselt auf den gemeinsamen Rahmen

**Neuer, paralleler Renderer, dann Vergleich, dann Umstellung -- wie geplant, nicht in einem
Schritt.** `app/quote_framed_pdf.py` (neu) rendert das Angebot über `render_framed_pdf()`
(`document_type="quote"`), Kopfbereich über `build_din5008_header_block()`, Positionstabelle über
`frame_content_width()`, Summenblock wie bei Rechnung/Auftrag. Gebaut PARALLEL zum bestehenden,
positionsbasierten `app/quote_layout_pdf.py` und dem älteren, einfachen `app/quote_pdf.py` --
beide bleiben unangetastet. "quote" nimmt dabei bewusst weiterhin NICHT am gemeinsamen
"default"-Satz teil (siehe `app/document_type_fallback.py`) -- der neue Renderer liest die schon
heute produktiv angepassten "quote"-Zeilen (Briefpapier/Ränder) direkt, keine neue Migration
für Briefpapier/Ränder nötig.

**Echte Übertragszeile -- eine neue Funktion, keine Migration eines bestehenden Features.**
Weder der alte noch der neue Renderer hatten je eine laufende Summe über Seitenumbrüche, nur eine
statische Fortsetzungs-Beschriftung ohne Betrag (Premise-Mismatch, vor dem Bauen aufgeklärt). Die
gesamte Positionsliste (alle Abschnitte samt Titeln) ist jetzt EINE einzige Tabelle
(`_CarryForwardItemsTable`, `Table.split()`-Überschreibung) statt mehrerer separater Tabellen mit
dazwischenliegenden Titel-Absätzen -- notwendig, damit die Übertragszeile bei JEDEM Seitenumbruch
innerhalb der Liste erscheint, auch wenn er genau zwischen zwei Abschnitten liegt, nicht nur
mitten in einer Positionsgruppe. Verfügbarer Platz vor dem eigentlichen Split wird um die Höhe
einer Übertragszeile verkleinert, damit sie tatsächlich noch auf der laufenden Seite Platz
findet, statt selbst auf die nächste zu rutschen. Verifiziert an einem synthetischen 90-Positionen/
5-Seiten-Angebot (exakte Beträge auf beiden Seiten jedes Umbruchs) UND am echten, zweiseitigen
Angebot A-2026-0001.

**Zwei echte Funde beim Vergleich gegen A-2026-0001, beide behoben.** (1) Doppelter Firmenkopf:
"quote" behält (anders als jeder andere Dokumenttyp seit 1.3.2) seine eigene, historische
`company_header`-Zeile mit `visible=True` -- der neue Renderer zeichnete dadurch sowohl seine
eigene DIN5008-Absenderzeile ALS AUCH den gezeichneten Rückfall-Baustein, dessen volle
Kontaktzeile zusätzlich in den Meta-Block hineinlief. Neuer, ausdrücklich als Übergangslösung
dokumentierter Parameter `suppress_drawn_blocks` an `render_framed_pdf()` (`app/document_frame.py`)
-- ein Ändern der Datenbank-Zeile selbst kam nicht in Frage, der alte Renderer liest dieselbe
Zeile und ist weiterhin aktiv. (2) Briefpapier verschwand auf Folgeseiten: "quote" hat nur eine
`page_type="first"`-Zeile mit `repeat_on_every_page=True` (Altbestand von vor der 1.3.1-
Seitentyp-Aufteilung) -- `get_effective_background()` (`app/document_layout.py`) kannte dieses
Feld bisher gar nicht. Fällt jetzt auf die "first"-Zeile zurück, wenn keine eigene
"continuation"-Zeile existiert UND `repeat_on_every_page` gesetzt ist -- ein generischer Fix,
nicht quote-spezifisch, betrifft aber aktuell nur "quote" (alle anderen Dokumenttypen haben
bereits zwei echte, getrennt hochgeladene Briefpapier-Dateien).

**Wiederholungszeile auf Folgeseiten nachgerüstet.** Mit sechzehn Seiten ist das Angebot das
längste Dokument im ganzen Projekt -- `DEFAULT_QUOTE_LAYOUT` bekommt einen elften Baustein
(`continuation_header`, Migration `ab5eef23f9ed` für die bereits bestehenden zehn
"quote"-Zeilen). Derselbe generische Standardwert wie überall seit 1.3.12 (12mm/4mm) im Code --
die bereits gesäte Zeile in der echten Datenbank ist zusätzlich auf 34mm korrigiert (am
tatsächlichen Briefpapier gemessen: dieselbe ~30,8mm tiefe Kopfgrafik wie beim "default"-Satz).

**Umstellung (Punkt 4): der reguläre PDF-Abruf und der E-Mail-Versand, nicht mehr.**
`GET /api/quotes/{id}/pdf` (`app/routers/quotes.py`) nutzt jetzt `build_quote_framed_pdf()` statt
des ältesten, einfachen `build_quote_pdf()` -- damit zeigt dieser Endpunkt erstmals dasselbe
Ergebnis wie der E-Mail-Versand. `send_quote_email()` (`app/projects.py`) nutzt ebenfalls
`build_quote_framed_pdf()` statt des bisherigen `build_quote_layout_pdf()`. Vor der Umstellung
geprüft, ob es weitere Aufrufer gibt (Dokumentenmanagement, Sammelversand) -- keine gefunden,
`send_quote_email()` hat genau einen Aufrufer, `customer_documents.py` kennt Angebote gar nicht.
`GET /api/quotes/{id}/pdf-layout-preview` (der alte, positionsbasierte Renderer) bleibt
ausdrücklich unverändert erreichbar, als reine Vergleichsansicht -- die beiden zugehörigen
Vorschau-Buttons (in `quote_editor.html` UND im PDF-Layout-Editor, `document_layout_editor.html`)
sind umbeschriftet: der Button, der jetzt den produktiven Endpunkt zeigt, heißt schlicht
"PDF-Vorschau"; der Button zum alten Renderer heißt jetzt deutlich "Vergleichsansicht: alter
Renderer (entfällt demnächst)" -- vorher hießen sie "Bisherige PDF-Vorschau"/"Layout-PDF-Vorschau"
bzw. "PDF-Vorschau"/"PDF-Vorschau (älterer Weg)", nach der Umstellung wäre das genau verkehrt
gewesen (die "bisherige" zeigte nach dem Umschalten das NEUE Ergebnis).

**Bewusst NICHT in dieser Etappe:** das Löschen von `quote_pdf.py`/`quote_layout_pdf.py`, dem
PDF-Layout-Editor, `DocumentTableField` oder den quote-eigenen Zeilen in
`DocumentLayoutBackground`/`DocumentPageMargins`/`DocumentLayoutBlock` -- erst wenn sich der neue
Renderer eine Weile im Einsatz bewährt hat, in einem eigenen, separat gemeldeten Schritt (Liste
der betroffenen Dateien/Endpunkte liegt vor, siehe Gesprächsverlauf).

## 1.3.12 – Zwei Funde aus 1.3.11 behoben: Wiederholungszeile einstellbar, Namen eingefroren

**Wiederholungszeile auf Folgeseiten -- vertikale Position jetzt einstellbar.** Der 1.3.11-Fund
(die feste Position bei 8mm von oben überlagerte auf jeder Folgeseite die Dekorfläche des echten,
hochgeladenen Briefpapiers) lässt sich nicht wie die Fußzeile in 1.3.8 einfach abschalten -- der
Bezug zum Dokument wird auf einer Folgeseite gebraucht. `app/document_frame.py` liest die
vertikale Position jetzt tatsächlich aus dem bestehenden `DocumentLayoutBlock.y_mm` des
`continuation_header`-Bausteins (vorher ignoriert, fest bei der entfernten Konstante
`CONTINUATION_HEADER_Y_MM`) -- kein neues Feld im Datenmodell, dieselbe Oberfläche
(`PUT /api/document-layout/blocks/{id}`) wie die Sichtbarkeit. `height_mm` wird ebenfalls
tatsächlich gelesen (vorher nur ein bedeutungsloser Platzhalterwert), für die geometrische
Kollisionsprüfung gegen company_header/den Inhaltsbereich.

Am echten Briefpapier nachgemessen (Pixelanalyse der hochgeladenen Datei, 200dpi): die Dekorfläche
reicht an ihrer tiefsten Stelle (Firmenlogo samt Schriftzug, zentriert) bis 30,8mm von oben.
Neuer Standardwert im Code (`DEFAULT_SHARED_LAYOUT`) 12mm/4mm -- passend für einen Briefbogen OHNE
eigene Kopfgrafik (bleibt unterhalb von Logo/Firmenkopf, die bei 17mm beginnen), nicht auf diesen
einen, ungewöhnlich tief reichenden Fund zugeschnitten. Die bereits gesäte "default"-Zeile in der
echten Datenbank wurde zusätzlich (über `update_layout_block()`, kein rohes SQL) auf 34mm
korrigiert -- klärt tatsächlich am echten, gerenderten Dokument geprüft, mit 1,2mm Puffer unter
der Dekorfläche und 4mm Puffer über dem oberen Randabstand für Folgeseiten (42mm). Neuer Test
`test_continuation_header_vertical_position_is_configurable` weist die Konfigurierbarkeit
end-to-end nach (Position ändern, neu rendern, verschobene Zeile nachmessen); die bestehende
Kollisions-Invariante liest jetzt ebenfalls den konfigurierten statt eines hart codierten Werts.

Der Hinweistext in Einstellungen → Dokumente & Layout wurde -- wie in 1.3.2 und 1.3.8 für die
jeweils betroffenen Bausteine ergänzt -- jetzt allgemeiner gefasst: er beschreibt zuerst das
gemeinsame Prinzip (jeder gezeichnete Baustein kollidiert möglicherweise mit einem eigenen
Briefbogen, die Position muss zu dessen tatsächlicher Gestaltung passen), bevor die vier
Bausteine einzeln erläutert werden -- das ist jetzt der dritte Baustein mit genau diesem Problem.

**Bauteil-/Dachflächennamen im unterschriebenen Bericht -- jetzt eingefroren.** Der 1.3.11-Fund
(`finding.roof_component.name`/`link.roof_area.name` lasen den aktuellen statt den zum
Signierzeitpunkt gültigen Namen) ist behoben: zwei neue, nullable Spalten
`Finding.roof_component_name_snapshot`/`ServiceReportRoofArea.roof_area_name_snapshot`, physisch
beim Anlegen befüllt (`create_finding()`/`_generate_inspection_items_for_areas()`) -- dasselbe
Prinzip wie `InspectionItem.text` seit 1.2.16. Im PDF UND in der Anzeige (`finding_to_dict()`,
`_report_roof_areas_to_dicts()`) bevorzugt gelesen, mit Rückfall auf den aktuellen Namen nur für
Bestandszeilen ohne Schnappschuss. Migration befüllt bestehende Zeilen aus dem heutigen Namen
(nicht historisch korrekt, aber näher an der Wahrheit als leer, siehe Migrationskommentar) --
gegen die echte Datenbank angewendet und stichprobenhaft geprüft.

Bei der zusätzlich angefragten Prüfung auf weitere live statt eingefroren gelesene Stellen
(Bauteiltyp, Dachtyp, Mitarbeitername, Prüfvorlagenbezeichnung): Bauteiltyp/Dachtyp werden
nirgends für die Anzeige eines bereits erzeugten Berichts gelesen, nur bei der Erzeugung selbst
(Vorlagenauflösung/Zuordnung) -- kein Fund. Prüfvorlagenbezeichnung (`inspection_template.label`)
IST ein echter Fund (live über `link.inspection_template.label`, änderbar über
`update_template()`) -- bisher nicht im PDF, aber in der Bildschirmansicht sichtbar. Mitarbeiter-
name: `created_by_employee_name` (Monteur-Meta-Zeile, seit 1.3.11) ist ebenfalls live; die
Zeiten-Tabelle nutzt zusätzlich `entry_to_dict()`s allgemein im Projekt live gehaltenen
`employee_name` -- letzteres ist die etablierte, projektweite TimeEntry-Konvention, keine
speziell für Einsatzberichte eingeführte Lücke. Alle drei gemeldet, keiner ohne Rückfrage
geändert.

## 1.3.11 – Fünfte Etappe des PDF-Umbaus: der Einsatzbericht wechselt auf den gemeinsamen Rahmen

`app/service_report_pdf.py` wechselt auf `render_framed_pdf()` (`document_type="service_report"`,
neu in `RENDERERS_USING_SHARED_FRAME` UND in `DOCUMENT_TYPES` in `app/document_layout.py` --
dieser Dokumenttyp existierte dort bisher gar nicht), Kopfbereich über
`build_din5008_header_block()` statt des bisherigen `build_company_header_block()`. Vorgehen wie
bei Rechnung/Auftrag: die bestehende Testabdeckung (Prüfpunkte, Mängel, Material) war bereits
gut, aber ohne einen Test für Auftrags-/Kundenidentität und die beiden Unterschriften-
Beschriftungen -- ein solcher Inhaltstest wurde ergänzt, vor UND nach dem Umbau grün.

Meta-Zeilen gegen den Bestand geprüft: Auftragsnr./Datum/Berichtstyp/Kunden-Nr. (falls
vorhanden)/Monteur (falls vorhanden)/Seite -- alle aus bereits vorhandenen Daten, nichts
erfunden. Kunde/Auftrag/Datum standen vorher als Fließtext im Bericht selbst ("Auftrag: ...
Kunde: ... Datum des Einsatzes: ..."), jetzt im gemeinsamen Kopfbereich wie bei den anderen drei
Dokumenttypen.

Alle KeepTogether-Blöcke aus 1.2.21 (Unterschriftenblock, Mangel-Blöcke, Prüfpunkt-Gruppen,
Fotoblöcke) bleiben unverändert bestehen und funktionieren nach dem Umbau weiterhin -- geprüft
nicht nur per Test, sondern an einem eigens erzeugten, elfseitigen Bericht mit zwei Dachflächen,
16 Bauteilen, 12 Mängeln mit Fotos und mehreren Materialpositionen: jede Seite einzeln als Bild
gerendert und durchgesehen, keine Tabelle, kein Mangel-Block und keine Unterschrift über einen
Seitenumbruch gerissen. Auffällig, aber bereits VOR diesem Umbau genauso vorhanden (keine
Regression, nicht Teil dieser Etappe): die Abschnitts-/Dachflächen-Überschriften selbst
("Prüfpunkte", "Festgestellte Mängel", der Name einer Dachfläche) sind nicht mit ihrem jeweils
ersten Block per KeepTogether verbunden und können deshalb allein am Seitenende stehen, während
ihr erster Tabellen-/Mangel-Block schon auf der nächsten Seite beginnt -- anders als bei den vier
vom Auftraggeber genannten Blöcken (die tatsächlich reißen könnten) ist hier nur eine Überschrift
betroffen, kein Inhalt.

Foto-Breite (`_pdf_image()`/`_render_photo_flowables()`) folgt jetzt `frame_content_width()`: die
beiden Standardgrößen (70mm Einzelfoto, 80mm je Vorher/Nachher-Bild) bleiben als Vorschaugrößen
bei ausreichend Platz unverändert, werden aber nach unten gekappt, sobald der tatsächlich
konfigurierte Satzspiegel schmaler ist -- vorher hart codiert, unabhängig von den Rändern.

Alle Tabellen im Bericht auf `colWidths`-Summe/`hAlign` geprüft, drei Funde: die
Vorher/Nachher-Fototabelle UND die zweispaltige Unterschriften-Tabelle (Punkt 6 der Anfrage)
hatten beide `colWidths=[95mm, 95mm]` = 190mm bei nur 176mm verfügbarer Standardbreite --
14mm zu breit, reportlabs Tabellen-Standard `hAlign="CENTER"` zentrierte beide dadurch sichtbar
nach links. Nachgemessen an der Unterschriften-Tabelle: vorher "Monteur"/"Bestätigt von: Monteur
Meier" bei 17,35mm/13,32mm (statt 18,20mm), "Kunde"-Spalte durch die Zentrierung merklich zu weit
links; nachher exakt bei 18,21mm (erste Spalte) bzw. 108,32mm (zweite Spalte, exakt
`content_width`/2 + Standard-Zellenpolster). Mit testweise auf 30mm/25mm geänderten Rändern
zusätzlich nachgewiesen, dass beide Spalten dem neuen Rand folgen (30,21mm/109,82mm), nicht mehr
dem alten 190mm-Wert. Prüfpunkt-/Material-/Zeiten-Tabelle summierten sich schon vorher exakt auf
176mm (kein Überlauf bei Standardrändern), aber ebenfalls hart codiert -- jetzt auf dieselbe Art
wie bei der Rechnung (1.3.9) aus `frame_content_width()` abgeleitet, die jeweils eine
Text-/Beschreibungsspalte nimmt den variablen Rest auf.

Geprüft, ob der Renderer irgendwo auf aktuelle statt eingefrorene Daten zugreift (wie beim
Auftrag in 1.3.10): **zwei echte Funde**, anders als beim Auftrag. `finding.roof_component.name`
und `link.roof_area.name` (Gruppierung von Prüfpunkten UND Material nach Dachfläche) lesen den
JEWEILS AKTUELLEN Namen des Bauteils bzw. der Dachfläche zum Zeitpunkt des PDF-Renderns, nicht
einen zum Zeitpunkt der Unterschrift eingefrorenen Schnappschuss -- weder `RoofComponent` noch
`RoofArea` noch die verlinkenden Tabellen (`Finding`, `ServiceReportRoofArea`) tragen dafür eine
eigene Namensspalte. Ein nach der Unterschrift umbenanntes Bauteil/eine umbenannte Dachfläche
würde im PDF eines bereits unterschriebenen, eigentlich unveränderlichen Berichts anders
erscheinen als zum Unterschriftszeitpunkt. Bewusst NICHT in dieser Etappe behoben (reine
Rahmen-Umstellung, kein Datenmodell-Umbau) -- gemeldet, keine Änderung ohne Rückfrage.

## 1.3.10 – Vierte Etappe des PDF-Umbaus: der Auftrag wechselt auf den gemeinsamen Rahmen

`app/order_pdf.py` wechselt auf `render_framed_pdf()` (`document_type="order"`, neu in
`RENDERERS_USING_SHARED_FRAME`), Kopfbereich über `build_din5008_header_block()` statt des
bisherigen `build_customer_and_meta_block()`, Firmenkopf/Fußzeile nicht mehr fest im Renderer.
Vorgehen wie bei der Rechnung in 1.3.7: zuerst ein Inhaltstest gegen die noch unveränderte
Fassung (`test_order_pdf_contains_expected_content`, `tests/test_v232_order_pdf_shared_frame.py`)
geschrieben, der vor UND nach dem Umbau unverändert grün bleibt.

Die in 1.3.9 an der Rechnung gefundene Breitenkorrektur (`colWidths`-Summe 185mm statt der
tatsächlich verfügbaren Breite, reportlabs `Table`-Standard `hAlign="CENTER"`) betraf den Auftrag
identisch -- an einer Beispielrechnung nachgemessen: die Positionstabelle begann vorher bei
15,74mm statt 18,20mm und endete bei 196,35mm statt 194,00mm; nachher bei 18,12mm/193,96mm.
Zusätzlich fiel beim Auftrag ein DRITTER Effekt auf, den es bei Mahnung/Rechnung so nicht gab: der
bisherige Renderer nutzte `SimpleDocTemplate`, dessen Standard-`Frame` selbst ein ungenulltes
6pt-Innenpolster mitbringt (reportlab-Vorgabe) -- der Summenblock (`hAlign="RIGHT"`, 160mm breit)
endete dadurch bei 189,75mm statt der erwarteten 194mm, trotz an sich korrektem `hAlign`. Mit dem
Wechsel auf `document_frame.py::_build_frame()` (nullt dieses Innenpolster bereits) entfällt dieser
Effekt automatisch; der Summenblock wurde zusätzlich auf dieselbe volle-Breite-plus-genulltes-
Zellenpolster-Bauweise wie bei Mahnung/Rechnung umgestellt (`_totals_table()`, jetzt mit
`frame_content_width()` statt `colWidths=[115mm, 45mm]`) und endet jetzt bei 193,98mm.

Sachbearbeiter/Projektleiter (`caseworker_employee_id`/`project_manager_employee_id`) sind beim
Auftrag -- anders als bei der Rechnung, wo die Spalte nie befüllt wird -- tatsächlich in Gebrauch
(4 von 5 echten Aufträgen haben einen Sachbearbeiter hinterlegt) und bleiben deshalb im
Kopfbereich sichtbar, jetzt aber unabhängig voneinander: vorher erschien "Projektleiter" nur in
derselben Zeile wie "Sachbearbeiter" und damit nie, wenn nur ein Projektleiter (ohne
Sachbearbeiter) hinterlegt war -- mit dem neuen, einer-Zeile-pro-Feld-Kopfbereich zeigt jedes
Feld unabhängig, ob es gesetzt ist.

Geprüft, bevor etwas geändert wurde (wie verlangt): weder `order_to_dict()` noch `order_pdf.py`
lesen `order.project.customer`/`order.project.property` live -- beide verwenden ausschließlich die
bei Beauftragung eingefrorenen Order-Spalten `customer_name`/`customer_address`/`property_name`/
`property_address`. Als Regression festgehalten (`test_order_pdf_uses_frozen_snapshot_not_live_customer_or_property_data`).
Bereits versendete Auftrags-PDFs per E-Mail: **keine** -- von 5 Aufträgen in der echten Datenbank
hat noch keiner `email_sent_at` gesetzt, das PDF wird ohnehin bei jedem Versand/Download live neu
erzeugt (nie gespeichert), also ohne jede GoBD-Relevanz für diese Etappe.

Mit dem Auftrag sind jetzt drei Renderer auf denselben Summenblock-Aufbau umgestellt (Mahnung,
Rechnung, Auftrag) -- laut Klärung genau die Schwelle, ab der eine Zusammenführung zu einem
gemeinsamen Baustein lohnt. Vorgeschlagen, aber bewusst noch nicht gebaut (siehe CLAUDE.md).

Angebot und Einsatzbericht bleiben vollständig unangetastet. `pytest` vollständig grün (920/920).

## 1.3.9 – Positionstabelle: eine Mengenspalte mit Einheit, korrekte Tabellenbreite

An einer echten Schlussrechnung gemeldet (Screenshot des Betreibers), vier Punkte, vor dem
geplanten Auftrags-Umbau erledigt, damit die Tabellen nicht zweimal angefasst werden.

**Eine Mengenspalte statt drei**: die Rechnung zeigte bisher "Menge (Soll)"/"Ist (gesamt)"/"abger.
Menge" nebeneinander -- auf einem Kundendokument gehört davon nur die tatsächlich abgerechnete
Menge hin, jetzt schlicht als "Menge" beschriftet. Geprüft, bevor etwas entfernt wurde: die
Bildschirmansicht (`invoice_detail.html`) zeigt weiterhin alle drei Werte nebeneinander (Spalten
"Soll"/"Ist (gesamt)"/"abgerechnet") -- nur das PDF wird reduziert, die Information geht nirgends
verloren. Angebot und Auftrag zeigten schon vorher nur eine einzige Mengenspalte (`QuoteItem`/
`OrderItem` kennen gar keine Soll/Ist-Aufteilung) -- für den Auftrag ist das fachlich die
beauftragte Menge, genau wie vorgeschlagen; an beiden musste nichts geändert werden.

**Einheit ergänzt**: `InvoiceItem.unit` existierte bereits (unverändert aus der Auftragsposition
übernommen) und stand bisher einfach nirgends auf dem PDF. Neue Spalte "EH" direkt neben "Menge" --
dieselbe Spaltenbezeichnung/-breite (14mm), die `order_pdf.py` und `quote_layout_pdf.py` für
denselben Zweck bereits verwenden. Eine Prüfung des tatsächlichen Angebots-PDFs ergab: die
erwartete Beschriftung "Menge Einh." als EINE gemeinsame Spaltenüberschrift existiert dort nicht
(weder im Code noch im gerenderten Dokument) -- Angebot und Auftrag zeigen "Menge" und "EH" schon
heute als zwei eigenständige, nebeneinanderliegende Spalten. Die Rechnung übernimmt jetzt exakt
dieses bereits etablierte Muster, statt ein neues zu erfinden.

**Tabellenbreite aus den echten Randeinstellungen statt eines hart codierten Wertes**: an der
Positionstabelle gemessen (nicht geschätzt) lag die Ursache in zwei Dingen gleichzeitig -- ihre
`colWidths` summierten sich auf 185mm bei nur 176mm verfügbarer Breite (Standardränder), und ohne
eigenes `hAlign` zentriert reportlab eine Tabelle standardmäßig, wodurch die zu breite Tabelle
sowohl links (Position bei 15,82mm statt 18,20mm) als auch rechts (Betrag-Wert bei 196,35mm statt
194,00mm) über die gemeinsame Fluchtlinie hinausragte. Neue, öffentliche Funktion
`document_frame.py::frame_content_width()` liefert die tatsächlich konfigurierte Breite (dieselbe
Formel wie beim Frame selbst) -- `invoice_pdf.py` und `reminder_pdf.py` lesen sie jetzt vor dem
Aufbau der Story und reichen sie an `build_din5008_header_block()` (neuer optionaler Parameter
`content_width`), die eigene Summentabelle UND (bei der Rechnung) die neu vermessene
Positionstabelle durch -- betrifft beide bereits umgestellten Renderer (Mahnung, Rechnung)
gleichermaßen, nicht nur die Rechnung. Mit einem testweise auf 30mm/25mm geänderten Rand
nachgewiesen: alle Tabellen folgen dem neuen Randabstand exakt, nicht mehr dem alten 176mm-Wert.
Nachher: Position bei 18,21mm, Betrag-Wert bei 193,96mm (Standardränder) bzw. 30,21mm/184,96mm
(30mm/25mm-Testränder) -- beide innerhalb der Messtoleranz auf der jeweils erwarteten Fluchtlinie.
Nur die äußeren Zellenränder der Positionstabelle wurden genullt (erste Spalte links, letzte
rechts), nicht alle -- sonst hätten Menge und Einheit ohne jeden Zwischenraum aneinandergeklebt
("50,223m²" statt "50,223 m²").

**Farbe der Langtexte geprüft, nicht geändert**: eine echte Rechnung gerendert und pixelgenau
untersucht (vollständiges Farbhistogramm der Seite) -- weder Grün noch Braun kommen im
gerenderten PDF vor, nur zwei neutrale Grautöne (`#555555` für die Positionsnummer, `#666666` für
den Langtext). Dieselbe Kombination aus kleinerer Schrift und `#666666`-Grau für den Langtext
findet sich identisch in allen vier LV-Positionstabellen-Renderern (`quote_pdf.py`,
`quote_layout_pdf.py`, `order_pdf.py`, jetzt auch `invoice_pdf.py`) -- eine klar erkennbare,
wiederholt eingesetzte Gestaltungsabsicht (dezente Zweitrangigkeit des Langtexts gegenüber dem
Kurztext), kein Überbleibsel einer einzelnen Datei. Deshalb unverändert gelassen; das
wahrgenommene Grün/Braun kommt vermutlich vom Papier/Drucker/Bildschirm, nicht vom PDF selbst.

## 1.3.8 – Fehlerbehebung: Fußzeile überlagerte echtes Briefpapier

Kleinstmögliche Lösung für den in 1.3.7 gefundenen Fund: `footer_text` steht im gemeinsamen
Standard (`DEFAULT_SHARED_LAYOUT`, `app/document_layout.py`) jetzt auf `visible=False` (vorher, seit
1.3.1, `True`). Begründung: der Briefbogen trägt unten bereits Anschrift, Kontakt,
Registergericht und Bankverbindung, und die Seitenangabe wird an der festen Fußzeilen-Position
ohnehin nicht mehr gebraucht -- sie steht seit 1.3.4 im Meta-Block auf Seite 1 und seit 1.3.7 in
der Wiederholungszeile auf Folgeseiten. `continuation_header` bleibt bewusst Standard AN -- eine
reine Text-Zeile mit Belegnummer/Kunden-Nr./Datum liefert Informationen, die kein Briefbogen von
sich aus haben kann, und ihre feste Position (oberhalb von Logo/Firmenkopf) läuft nicht in den
Fußbereich eines Briefpapiers.

Die bereits gesäte "default"-Zeile in der echten Datenbank musste nachträglich korrigiert werden
-- derselbe Mechanismus wie schon in 1.3.2 (ein geänderter Standardwert im Code wirkt nicht
rückwirkend auf bereits vorhandene Zeilen). Mit den bestehenden Anwendungsfunktionen erledigt
(`update_layout_block()`), kein rohes SQL.

Der Hinweistext bei den drei Sichtbarkeitsschaltern in Einstellungen → Dokumente & Layout (seit
1.3.2 dort für den oberen Rand vorhanden) wurde erweitert statt einen zweiten daneben zu
schreiben: er erklärt jetzt zusätzlich, dass alle drei Bausteine nur für Installationen ohne
eigenen Briefbogen gedacht sind, und dass die Fußzeile anders als Logo/Firmenkopf an einer FESTEN
Position sitzt (unabhängig vom Randabstand) und deshalb bei einem echten Briefbogen typischerweise
dessen aufgedrucktem Fußbereich in die Quere kommt.

## 1.3.7 – Zweite Etappe des PDF-Umbaus: Rechnung auf den gemeinsamen Rahmen, Wiederholungszeile

Die Rechnung (`app/invoice_pdf.py`) wechselt auf den gemeinsamen PDF-Rahmen (`render_framed_pdf()`,
Vorbild `reminder_pdf.py` aus 1.3.1), Folgeseiten bekommen erstmals eine abschaltbare
Wiederholungszeile. Angebot, Auftrag und Einsatzbericht bleiben vollständig unangetastet --
`quote_layout_pdf.py` wurde nicht berührt.

Vorgehen wie vorgegeben: zuerst ein Inhaltstest gegen die noch unveränderte Fassung
(Rechnungsnummer, Kundenname, Positionen, Netto, Steuer, Brutto, Zahlungsbedingungen als
Teilstrings), der vor UND nach dem Umbau unverändert grün bleiben musste -- ist er. Kopfbereich
jetzt wie bei der Mahnung (`build_din5008_header_block()` aus 1.3.3, nicht mehr die alte
`build_customer_and_meta_block()`). Firmenkopf/Fußzeile stehen nicht mehr fest im Renderer, sie
kommen wie bei der Mahnung entweder aus dem Briefbogen oder den abschaltbaren Rahmen-Bausteinen.

Die Meta-Zeilen wurden gegen den tatsächlichen Datenbestand geprüft, nichts erfunden:
Rechnungsnr./Datum/Kunden-Nr. direkt aus den vorhandenen Feldern, Vorgangs-Nr. über die Auftrag-
Projekt-Beziehung, Seite über den unveränderten Zweidurchlauf-Mechanismus aus 1.3.4/1.3.5. Zwei
bewusste Auslassungen: "Sachbearbeiter" fehlt, weil `Invoice.caseworker_employee_id` zwar als
Spalte existiert, aber nirgends im Code je gesetzt wird (dauerhaft `NULL`) -- eine leere Zeile
wäre schlechter als keine, siehe "Bekannte, bewusst offene Punkte" für den vollständigen Befund.
**"Fällig bis" ist aus dem Meta-Block entfernt -- das ist eine sichtbare Änderung am
Erscheinungsbild der Rechnung, nicht nur eine technische Umstellung.** Das Fälligkeitsdatum bleibt
trotzdem genauso auffindbar wie vorher: der automatisch erzeugte Satz "Zahlbar rein netto bis
zum ..." steht bereits mit eigenem, fett hervorgehobenem Label "Zahlungsbedingungen:" weiter unten
auf dem Dokument -- vor der Entscheidung geprüft, dass dort keine Prominenz verloren geht.

Neu, bewusst als Teil des RAHMENS statt des einzelnen Renderers (damit künftige Dokumenttypen sie
einfach mitbekommen): eine abschaltbare Wiederholungszeile auf Folgeseiten (vierter gezeichneter
Baustein `continuation_header`), die dort den vollen Kopfbereich ersetzt, der nur auf Seite 1
steht. `render_framed_pdf()` bekommt dafür einen neuen, optionalen Parameter
`continuation_header_rows` (fertige Beschriftung/Wert-Paare, z. B. Rechnungsnr./Datum/Kunden-Nr.).
Die Seitenzahl in dieser Zeile nutzt denselben Zweidurchlauf-/Canvas-Mechanismus wie die Fußzeile
seit 1.3.4/1.3.5, kein zweiter wurde gebaut. Position fest oberhalb von Logo/Firmenkopf, damit
sich beide Bausteine nie überlappen können -- mit einem eigenen geometrischen Test abgesichert,
genau wie bei der 1.3.2-Regression der Mahnung. Kleine Korrektur zur ursprünglichen Beschreibung:
das heutige Angebot zeigt auf Folgeseiten nur einen einzelnen Fortsetzungshinweis, keine Feldliste
-- die Feldliste war von Anfang an das Ziel für den neuen, gemeinsamen Mechanismus, keine 1:1-Kopie
des heutigen Angebots-Verhaltens.

Der laut Bestandsaufnahme vierfach duplizierte Summenblock (Angebot/Auftrag/Rechnung/Mahnung)
wurde geprüft: Rechnung und Mahnung könnten sich denselben Baustein teilen (beide jetzt exakt
gleich formatiert, nur die Zeilenbeschriftungen unterscheiden sich) -- wie besprochen aber noch
nicht zusammengeführt, das lohnt erst, wenn ein dritter Renderer umgestellt ist.

Migration `257fb2967c93` (reine Daten-Migration): ergänzt den neuen `continuation_header`-Baustein
für jede Installation, die den geteilten Satz ("default", seit 1.3.6) bereits geseedet hat --
automatisches Seeding greift nur für eine komplett frische Installation, nicht für einen einzelnen
neuen Baustein an einem bereits bestehenden Dokumenttyp.

Bei der Verifikation gegen die echte, migrierte Produktionsdatenbank ein echter, bisher unbemerkter
Fund: die Fußzeile ("Seite X von Y", fest bei 20mm/12mm) überlagert sichtbar das tatsächlich von
Tobias hochgeladene Briefpapier, das an derselben Stelle bereits eine eigene, aufgedruckte
Adresszeile trägt. Das ist keine neue Nebenwirkung dieser Etappe -- die Überlagerung war seit 1.3.1
latent vorhanden, nur bisher nie mit dem echten Briefpapier UND einer sichtbaren Fußzeile
zusammen gegen echte Daten geprüft worden. Bewusst nicht im Vorbeigehen mitbehoben (siehe
"Bekannte, bewusst offene Punkte"), da die richtige Lösung eine eigene Entscheidung braucht.

Vor Rückfrage außerdem geprüft: die Rechnung wird bei jedem Abruf frisch erzeugt, kein PDF wird je
gespeichert -- wie bei jedem Dokumenttyp in diesem ERP. Nach diesem Umbau sieht eine bereits
versendete Rechnung beim nächsten Abruf entsprechend anders aus als beim ursprünglichen Versand.
Betroffen in der echten Datenbank: 4 versendete + 1 stornierte Rechnung, davon 2 tatsächlich per
E-Mail verschickt -- alle vom 04./11.09.2026, erkennbar Test-/Demobetrieb einer frischen
Installation. Auf dieser Grundlage wurde der Umbau freigegeben.

## 1.3.6 – Zusammenführung der Layout-Einstellungen: ein gemeinsamer Dokumenttyp

Betreiber-Entscheidung: alle Dokumenttypen (außer dem Angebot) nutzen künftig denselben
Briefbogen, denselben Satz Ränder und dieselben optionalen gezeichneten Bausteine, statt jeder
Dokumenttyp seine eigene Einstellung zu pflegen -- die Unterscheidung Seite 1/Folgeseiten bleibt
dabei bestehen (auf Folgeseiten darf der Inhalt weiter oben beginnen, da dort kein
Anschriftenfeld mehr im Weg steht).

**Ein gemeinsamer Dokumenttyp statt vier**: `DocumentLayoutBackground`/`DocumentPageMargins`/
`DocumentLayoutBlock` bekommen keine neue Spalte -- `document_type` bleibt eine unbeschränkte
Zeichenkette, "default" ist nur ein weiterer, bisher ungenutzter Wert darin. Rückfall-Regel
(Option a): existiert für den tatsächlich angefragten Dokumenttyp (z. B. "reminder") bereits eine
eigene Zeile, gilt sie unverändert -- ein künftiger, echter Sonderfall je Dokumenttyp bleibt damit
möglich, ohne das Datenmodell erneut anzufassen. Existiert keine, wird die Zeile des geteilten
Satzes ("default") verwendet. Das Angebot nimmt an diesem Rückfall nie teil -- `quote_layout_pdf.py`
und seine Zeilen bleiben vollständig unangetastet, bis das Angebot in einer eigenen, späteren
Etappe umgebaut wird.

Die Regel ist **einmal** implementiert (`resolve_shared_document_type()` in neuem Modul
`app/document_type_fallback.py`) und wird von `app/document_layout.py` (Bausteine, Briefpapier)
und `app/document_page_margins.py` (Ränder) importiert, statt sie parallel nachzubauen --
`build_customer_and_meta_block()` mit seinen inzwischen drei auseinandergelaufenen Varianten
(siehe "Kopfbereich" oben) war die Warnung dafür. `DEFAULT_REMINDER_LAYOUT` heißt jetzt
`DEFAULT_SHARED_LAYOUT`, `DOCUMENT_TYPE_MARGIN_OVERRIDES` ist von `"reminder"` auf `"default"`
umgeschlüsselt -- der Mechanismus selbst bleibt nötig (er gibt dem geteilten Satz seine eigenen
42mm Standard-Oberrand, ohne ihn würde eine frische Installation den 1.3.2-Überlappungsfehler mit
dem Angebots-Standardwert 17mm wieder einführen).

**Schutzprüfung an den schreibenden Endpunkten**: damit nicht irgendwann versehentlich eine Zeile
mit einem echten Dokumenttyp (z. B. `document_type="invoice"`) angelegt wird und der Rückfall für
genau diesen Typ ab sofort lautlos nicht mehr greift, akzeptieren die schreibenden Endpunkte
(Briefpapier hochladen/löschen, Ränder ändern/zurücksetzen, Bausteine anlegen/zurücksetzen) jetzt
ausschließlich `"quote"` und `"default"` -- alles andere wird mit 422 abgelehnt. Lesend bleibt der
volle Rückfall bestehen (z. B. `GET .../reminder/margins/first` zeigt weiterhin, was für die
Mahnung tatsächlich WIRKT). Die Business-Logik-Ebene trennt dafür literale Schreibfunktionen
(`update_margins()`, `set_background()`) konsequent von Rückfall-bewussten Lesefunktionen
(`get_margins()`, `get_effective_background()`) -- ein Schreibzugriff findet/ändert immer exakt
die Zeile seines eigenen `document_type`, nie die geteilte Zeile eines anderen.

**Migration**: reine Daten-Migration (keine Schema-Änderung) überführt die bereits erprobten,
1.3.1/1.3.2 angepassten Mahnung-Zeilen (oberer Rand 42mm, Logo/Firmenkopf ausgeblendet, die beiden
tatsächlich hochgeladenen Briefpapier-Dateien für Seite 1/Folgeseiten) unverändert in den
geteilten Satz -- nichts davon wird neu erfunden. Die Angebots-Zeilen bleiben unberührt (geprüft:
vor der Migration hatten nur "quote" und "reminder" überhaupt Zeilen in diesen drei Tabellen,
"order"/"invoice" keine).

**Ein Eintrag in den Einstellungen**: aus "Mahnwesen-Layout" wird "Dokumente & Layout" -- inhaltlich
unverändert (Briefpapier je Seitentyp, Ränder je Seitentyp mit Hinweis zum kleineren oberen Rand
auf Folgeseiten, die drei Sichtbarkeitsschalter), nur zeigt jedes Feld/jeder Button jetzt auf
`document_type="default"` statt `"reminder"`. Neu: eine Vorschau, welche Dokumenttypen diese
Einstellungen bereits nutzen und welche noch nicht -- gespeist direkt aus
`RENDERERS_USING_SHARED_FRAME` in `app/document_frame.py` (`GET /api/document-layout/rollout-status`),
nicht aus einer separaten, leicht vergessbaren Liste im Template: `render_framed_pdf()` lehnt
einen dort nicht eingetragenen Dokumenttyp mit einem Fehler ab, ein künftiger Renderer MUSS diese
Zuordnung also zwangsläufig ergänzen, bevor sein erster Testaufruf überhaupt gelingt. Der
bisherige "PDF-Layout-Editor" bleibt bestehen, solange das Angebot ihn noch braucht, mit einem
neuen, deutlichen Hinweis, dass er nach dessen Umbau entfällt und wo die gemeinsamen Einstellungen
inzwischen liegen.

Akzeptanzkriterien geprüft: ein Briefbogen gilt jetzt für Mahnung und jeden künftig umgebauten
Dokumenttyp gemeinsam; die Ränder sind einmal je Seitentyp einstellbar; die Mahnung sieht nach der
Zusammenführung nachweislich genau aus wie vorher (bestehender Inhaltstest weiterhin grün, PDF
visuell mit dem Stand vor dieser Version verglichen -- identisch); das Angebots-PDF und seine
Tests sind unverändert; `pytest` vollständig grün (890/890).

## 1.3.5 – Seitenangabe im Meta-Block der Mahnung

Dritter Smoke-Test verlangte zwei Dinge. **Erstens**: die Seitenangabe soll wie beim Angebot als
eigene Zeile ("Seite 1 / N") im Meta-Block stehen, nicht nur in der Fußzeile. Technisch nicht
trivial, weil die Gesamtseitenzahl erst in `_NumberedCanvas.save()` bekannt ist (siehe CLAUDE.md
"PDF-Rahmen"), der Meta-Block aber beim Aufbau der Story entsteht, lange davor. Recherche ergab:
`quote_layout_pdf.py` löst dieses Problem gar nicht -- es zeigt nirgends eine Gesamtseitenzahl
(nur die laufende Seite, "Fortsetzung, Seite N" bzw. ein hartkodiertes Literal "Seite 1" auf
Seite 1), es gibt also nichts zu übernehmen. Von zwei vorgeschlagenen Ansätzen (Platzhalter, den
die Canvas-Unterklasse nachträglich überschreibt, vs. zweiter Renderdurchlauf) fiel die
Entscheidung auf den zweiten: ein nachträglich überschriebener Platzhalter müsste bereits fertig
positionierte PDF-Textoperatoren patchen -- hat der Platzhalter eine andere Zeichenlänge als die
echte Zahl, verschiebt sich die gerade erst (1.3.4) behobene Rechtsbündigkeit der Wertespalte
wieder. Der doppelte Durchlauf ist dafür unter dem Strich kein großer Mehraufwand: die eigentlich
teure Arbeit bei reportlab ist die Platypus-Layoutberechnung (die über Seitenumbrüche entscheidet),
die fällt bei einem "billigeren" Zähl-Durchlauf ohnehin genauso an -- ein dritter, stillgelegter
Zwischenweg hätte kaum etwas gespart und wurde deshalb nicht gebaut.

`render_framed_pdf()` (`app/document_frame.py`) nimmt `content_story` jetzt entweder wie bisher
als fertige Liste, oder -- neu, und bewusst so verallgemeinert, dass jeder künftige Dokumenttyp es
nutzen kann -- als Funktion `(total_pages: int | None) -> list`: ein erster, komplett verworfener
Durchlauf ruft sie mit `None` auf, ermittelt darüber `doc.page` (die dann bekannte
Gesamtseitenzahl), ein zweiter, echter Durchlauf ruft sie erneut mit der echten Zahl auf und
liefert die tatsächlichen Bytes. Bestehende Aufrufer (bisher nur die Mahnung selbst, weiterhin mit
einer einfachen Liste denkbar) ändern sich nicht. `app/reminder_pdf.py::build_reminder_pdf()` baut
seine Story jetzt in einer lokalen Funktion, die die Meta-Zeile "Seite" ("1 / N", die Mahnung sitzt
immer auf Seite 1) aus dem übergebenen `total_pages`-Parameter befüllt.

**Fußzeile bleibt unabhängig**: geprüft, ob Fußzeile (abschaltbarer Rahmen-Baustein) und die neue
Meta-Block-Zeile (fester Inhaltsbestandteil wie Datum/Belegnummer, nicht extra abschaltbar)
gleichzeitig aktiv sein können und ob das sinnvoll ist -- ja zu beidem: sie sind unabhängig
voneinander verdrahtet, beide gleichzeitig aktiv ist redundant (zeigt die Seitenzahl zweimal), aber
nicht falsch -- die Fußzeile dient dem Blättern im ausgedruckten Stapel (jede Seite), die
Meta-Zeile ist ein einmaliger Fakt vorneweg (nur Seite 1). Keine Kopplung eingebaut.

**Zweitens**, die im selben Smoke-Test gemeldeten "zu großen Zeilenabstände" im Meta-Block: direkt
am `Table`-Objekt nachgemessen (`_rowHeights`) und zusätzlich isoliert mit verschiedenen
Schriftgrößen (8,5/9/20/60pt) geprüft -- die Zeilenhöhe ist in Angebot UND Mahnung identisch 18pt/
6,35mm pro Zeile, unabhängig von der Schriftgröße (reportlabs Standardwert für eine einfache
Tabellenzeile ohne explizit gesetzte `rowHeights`). Es gibt hier also keinen Unterschied zum
Angebot zu beheben -- diese Etappe ändert daran bewusst nichts, auf Wunsch zurückgestellt, bis
klarer ist, welcher konkrete visuelle Effekt gemeint war (vermutet, aber nicht bestätigt: der durch
die kürzere, nur dreizeilige Mahnungs-Anschrift erzwungene Leerraum unter der Anschrift, da die
äußere Tabelle beide Spalten auf die Höhe der längeren -- hier: der Meta-Spalte -- aufzieht).

## 1.3.4 – Fehlerbehebung am 1.3.3-Kopfbereich: Meta-Block zu weit links, uneinheitliche Ränder

Zweiter Smoke-Test des 1.3.3-Kopfbereichs fand drei Abweichungen vom Angebot als Maßstab, alle
tatsächlich im PDF nachgemessen (`pypdfium2`-Zeichenboxen), nicht nach Augenmaß korrigiert:

1. **Meta-Block zu weit links, Wertespalte nicht rechtsbündig.** Gemessen vorher: die Wertespalte
   (z. B. Rechnungsnummer) endete bei ca. 142mm, 52mm vor dem rechten Rand (194mm). Ursache: die
   Spaltenbreiten der Meta-Tabelle waren zwar korrekt bemessen (Zellgrenze lag bereits bei 194mm),
   aber es fehlte eine `ALIGN`-Regel für die Wertespalte -- der Text blieb linksbündig in einer
   viel zu breiten Zelle und wirkte dadurch weit von der rechten Kante entfernt. Behoben durch
   `("ALIGN", (1,*), "RIGHT")` auf der Meta-Tabelle, zusätzlich die Spaltenaufteilung selbst an die
   tatsächlich gemessene, produktiv angepasste Angebotsseite angeglichen (70mm Anschrift, 70mm
   Meta-Block, 36mm sichtbare Lücke dazwischen, statt einer selbst erfundenen Aufteilung).

2. **Uneinheitliche linke/rechte Fluchtlinien.** Gemessen vorher: Absenderzeile bei 20,32mm statt
   18mm, Forderungstabelle sogar bei 36,27mm statt 18mm -- während Überschrift/Fließtext/
   "Ausführungsort" bereits korrekt bei 18,00-18,45mm lagen. Zwei getrennte Ursachen gefunden:
   (a) ein reportlab-`Table` hat per Default 6pt (~2,1mm) Zellenpolster auf jeder Seite, ein
   `Paragraph` keins -- jeder Tabelleninhalt (Absenderzeile+Anschrift stecken in einer Tabelle,
   um neben dem Meta-Block zu stehen) begann dadurch systematisch ~2mm zu weit rechts. (b) die
   Forderungstabelle stand auf `hAlign="RIGHT"` bei einer Breite von nur 160mm statt der vollen
   176mm Rahmenbreite -- die verbleibenden 16mm Lücke schob die GANZE Tabelle (inkl. ihrer
   linksbündigen Beschriftungsspalte) nach rechts, statt nur ihre Wertespalte rechtsbündig
   auszurichten. Behoben durch explizites Nullen von `LEFTPADDING`/`RIGHTPADDING` auf beiden
   Tabellen sowie durch Verbreiterung der Forderungstabelle auf die volle Rahmenbreite (statt
   `hAlign="RIGHT"`, das dadurch ohnehin gegenstandslos wird).

   Gemessen nachher: Absenderzeile/Ausführungsort/Überschrift/Fließtext/Forderungstabelle liegen
   jetzt alle zwischen 18,00mm und 18,45mm (vorher bis zu 36,27mm), Meta-Wertespalte und
   Forderungstabelle enden jetzt bei 193,45mm bzw. 193,98mm (vorher 142,18mm bzw. 191,87mm) --
   beide praktisch auf dem rechten Rand bei 194mm.

3. Die Absenderzeile selbst war inhaltlich bereits korrekt und wurde nicht angefasst.

Zwei neue Regressionstests lesen dafür direkt die Zeichenpositionen aus dem erzeugten PDF
(`pypdfium2.PdfTextPage.get_charbox()`) statt nur die Flowable-Struktur zu prüfen -- geprüft und
für machbar befunden, bevor sie geschrieben wurden (siehe CLAUDE.md, Abschnitt "Kopfbereich").

## 1.3.3 – Gemeinsamer Kopfbereich (Anschrift + Meta-Block): erster Nutzer die Mahnung

Zweiter Smoke-Test der Mahnung fand einen Stilbruch: die Empfängeranschrift stand dort in zwei
zusammengezogenen Zeilen statt jede Angabe in einer eigenen Zeile, und der Meta-Block hatte eine
andere Spaltenaufteilung als das Angebot. Untersuchung ergab: `build_customer_and_meta_block()`
(bisher von `quote_pdf.py`/`order_pdf.py`/`invoice_pdf.py`/`reminder_pdf.py` identisch genutzt)
zeigt die Anschrift als EINEN zusammengezogenen Absatz -- bei Auftrag/Rechnung/Mahnung kommt sie
aus einem eingefrorenen Textschnappschuss (`customer_address`, Straße+Ort bereits durch Komma zu
EINER Zeile verschmolzen, siehe `orders.py::_address()`), nicht aus strukturierten Einzelfeldern
wie beim Angebot. Der Meta-Block dort zeigt zusätzlich zwei Beschriftung/Wert-Paare pro Zeile statt
eines einzelnen -- uneinheitlich zur tatsächlichen, produktiv angepassten Angebotsseite
(`quote_layout_pdf.py`), die für genau diesen Zweck bereits eigene, private Bausteine
(`_build_line_list_block()`/`_build_field_rows_table()`) besitzt, dort aber fest an die
Layout-Designer-Feldkonfiguration und live Kundendaten gekoppelt und daher nicht direkt
wiederverwendbar.

Neuer, eigenständiger Baustein `build_din5008_header_block()` (`app/document_pdf.py`): nimmt eine
optionale Absenderzeile, die Empfängeranschrift als Liste einzelner Zeilen und den Meta-Block als
Liste von Beschriftung/Wert-Paaren entgegen und liefert daraus den fertigen Kopfbereich als
Flowables -- Empfängeranschrift jetzt als echte, einzelne Zeilen, Meta-Block als schlichte
Zweispalten-Tabelle mit genau einer Zeile pro Paar. Zusätzlich, als bewusste Nutzerentscheidung für
den neuen, gemeinsamen Auftritt (nicht identisch zum heutigen Ist-Zustand des Angebots, das seine
eigene Absenderzeile normal groß und ohne Linie zeigt): eine kleine, unterstrichene Absenderzeile
über der Anschrift, nach dem Muster der DIN-5008-Rücksendeangabe im Anschriftenfenster.
`build_customer_and_meta_block()` selbst bleibt unverändert -- Angebot, Auftrag und Rechnung nutzen
es weiterhin unangetastet und folgen erst in eigenen, späteren Etappen.

Erster und in dieser Etappe einziger Nutzer ist die Mahnung (`app/reminder_pdf.py`): baut die
Absenderzeile aus den Firmenstammdaten, teilt den eingefrorenen `customer_address`-Schnappschuss
einmalig an der bekannten ", "-Fuge (Straße/Ort, siehe `orders.py::_address()`) in zwei Zeilen auf
-- ohne die Schnappschuss-Erzeugung selbst anzufassen --, und baut den Meta-Block jetzt mit vier
statt zwei Zeilen. Vor dem Abschluss mit dem echten, produktiv angepassten Angebots-PDF
nebeneinander verglichen: Aufbau (Absenderzeile über Anschrift, Meta-Block rechts als
Zweispalten-Tabelle) stimmt jetzt überein, die schmalere Anschrift der Mahnung (3 statt 4 Zeilen)
liegt daran, dass Auftrag/Rechnung anders als das Angebot keinen separaten Ansprechpartner
einfrieren -- keine künstlich erfundene vierte Zeile.

## 1.3.2 – Fehlerbehebung: Firmenkopf überlagerte Inhalt der Mahnung

Smoke-Test von 1.3.1 fand zwei Befunde. **Befund 1 (echter Fehler, behoben):** der gezeichnete
Firmenkopf-Baustein der Mahnung überlagerte den fließenden Inhalt -- Firmenname/Kundenadresse
sowie Telefonnummer/Internetadresse standen im PDF übereinander. Ursache wie vom Nutzer selbst
vermutet: `DEFAULT_REMINDER_LAYOUT` setzte den Firmenkopf auf `y=17mm`, der obere Rand für Seite 1
stand ebenfalls auf `17mm` -- gezeichneter Block und Inhaltsbereich beanspruchten dieselbe Fläche.
Zwei Teile der Behebung: (1) `company_header` (und geprüft ebenso `logo`, derselbe Fehlertyp wäre
dort genauso aufgetreten) steht in `DEFAULT_REMINDER_LAYOUT` jetzt standardmäßig auf
`visible=False` -- wer Briefpapier hinterlegt hat, braucht ihn nicht, wer keins hat, schaltet ihn
bewusst ein. (2) Ein neuer, dokumenttyp-spezifischer Standard-Rand-Mechanismus
(`DOCUMENT_TYPE_MARGIN_OVERRIDES` in `app/document_page_margins.py`) hebt den Standard-Rand der
Mahnung (Seite 1 und Folgeseiten) auf `42mm` an, unterhalb der Unterkante der beiden Bausteine --
`ensure_default_margins()`/`reset_margins_to_default()` prüfen jetzt zuerst diese Überschreibung,
bevor sie auf den generischen `DEFAULT_MARGINS`-Wert zurückfallen; für `quote` (und jeden weiteren
Dokumenttyp ohne eigenen Eintrag) unverändert. In den Einstellungen steht jetzt direkt bei den drei
Kontrollkästchen ein Hinweistext, der genau diesen Zusammenhang erklärt (oberer Rand muss
mindestens bis zur Unterkante von Logo/Firmenkopf reichen), damit niemand erneut in dieselbe Falle
läuft. **Befund 2 (kein Fehler, nur geprüft):** ob der neue Abschnitt Einstellungen →
Mahnwesen-Layout erreichbar ist und alle drei Bereiche (Briefpapier je Seitentyp, Ränder je
Seitentyp, die drei Kontrollkästchen) zeigt -- Code-Durchsicht fand keinen Fehler, eine isolierte
zweite Serverinstanz (separater Port, separate, temporäre Testdatenbank, keine Berührung der
echten `dachkonzepte_erp.db`) mit echter Browser-Automatisierung (Login, Klick, Sichtbarkeitsprüfung,
Screenshot) bestätigte den Abschnitt vollständig funktionsfähig. Im PDF-Layout-Editor
(`document_layout_editor.html`) steht jetzt zusätzlich ein Hinweis mit Link, dass Mahnungen separat
unter Einstellungen → Mahnwesen-Layout konfiguriert werden, damit die beiden Orte für dieselbe Art
Einstellung nicht gegeneinander verwirren. Zwei neue Regressionstests in
`tests/test_v226_document_frame.py` sichern die Rahmen-Geometrie (kein gezeichneter Block ragt in
den Randbereich) sowie den konkret vom Nutzer geforderten Fall (Firmenkopf aktiviert, Standard-Rand,
PDF rendert ohne Überlappung) dauerhaft ab.

Nebenbei aufgefallen und korrigiert: die eigenen Smoke-Test-Aufrufe gegen den 1.3.1-Server hatten
in der echten `dachkonzepte_erp.db` bereits drei Zeilen mit den alten, fehlerhaften Vorgabewerten
angelegt (`ensure_default_layout()`/`ensure_default_margins()` seeden beim ersten Lesezugriff und
rühren danach nie wieder an bereits bestehende Zeilen). Diese drei Zeilen wurden nachträglich mit
denselben Funktionen, die auch die Anwendung selbst nutzt, auf die jetzt korrigierten Werte
gebracht -- kein rohes SQL, keine sonstigen Daten berührt.

## 1.3.1 – Gemeinsamer PDF-Rahmen (erste Etappe): app/document_frame.py, erprobt an der Mahnung

Erster Schritt des geplanten PDF-Umbaus (siehe `docs/bestandsaufnahme_pdf.md`): ein neues,
dokumenttyp-unabhängiges Modul `app/document_frame.py` trennt den wiederkehrenden RAHMEN
(Briefpapier-Hintergrund, Ränder, optionale gezeichnete Bausteine) vom fließenden INHALT. Der
Rahmen besteht -- korrigiert gegenüber der ursprünglichen Annahme -- in erster Linie aus
hinterlegtem Briefpapier, nicht aus gezeichneten Bausteinen: ein Unternehmen mit fertigem
Briefbogen blendet Logo/Firmenkopf/Fußzeile gerade deshalb aus, genau wie beim Angebot heute
schon. Reihenfolge: (1) Briefpapier-Hintergrund, getrennt für Seite 1/Folgeseiten, (2) Ränder je
Seitentyp, die bestimmen, wo der Inhalt beginnen/enden darf, (3) drei optionale, einzeln
abschaltbare gezeichnete Bausteine (Logo, Firmenkopf, Fußzeile mit Seitenzahl) als Rückfall für
Installationen ohne eigenes Briefpapier -- nie fest verdrahtet.

Erster Nutzer ist bewusst die Mahnung (`app/reminder_pdf.py`) -- kürzestes Dokument, bisher ohne
Testabdeckung, kein Bezug zum bestehenden Layout-Designer. Angebot, Auftrag, Rechnung,
Einsatzbericht bleiben in dieser Etappe vollständig unangetastet, insbesondere
`quote_layout_pdf.py` mit seinen produktiv angepassten Layouts. `reminder_pdf.py`s `story` enthält
nach dem Umbau ausschließlich noch Inhalt (Anschrift, Meta-Zeilen, Objektanschrift, Betreff,
Mahntext, Forderungsaufstellung) -- inhaltlich unverändert, nur ohne Firmenkopf/Fußzeile, die jetzt
aus dem Rahmen kommen. Architektur: `BaseDocTemplate` (statt `SimpleDocTemplate`) mit zwei
`PageTemplate`s ("first"/"later"), je mit eigenem `Frame` aus `DocumentPageMargins` und eigenem
`onPage`-Callback. Die Fußzeile mit Seitenzahl nutzt reportlabs Standardtechnik für "Seite X von
Y" (`canvasmaker`-Canvas-Unterklasse, die `showPage()` abfängt und erst in `save()` -- wenn die
Gesamtzahl real bekannt ist -- jede Seite fertig beschriftet) -- eine bewusste Neuerung, keine
Fehlerbehebung: der ursprünglich gemeldete Seitenzahl-Befund kam nach eingehender Untersuchung vom
PDF-Betrachter, nicht vom eigenen Code (kein einziger der sieben bestehenden Renderer zeigte je
eine Gesamtseitenzahl).

Einzige Datenmodell-Erweiterung: `DocumentLayoutBackground` bekommt eine `page_type`-Spalte
(`'first'`/`'continuation'`, Muster wie `DocumentPageMargins`) -- vorher konnte die Tabelle nur
einen Hintergrund je Dokumenttyp halten, keinen getrennten für Seite 1/Folgeseiten.
Rückwärtskompatibel: alle bestehenden Aufrufer (`quote_layout_pdf.py`, der alte
Bild-Upload-Endpunkt des Angebots) übergeben weiterhin keinen `page_type` und treffen nach der
Migration exakt dieselbe Zeile wie vorher (`server_default='first'`). Neue, eigenständige
Endpunkte `.../backgrounds/{page_type}` (Plural, bewusst ein anderes Pfadsegment als das
bestehende `.../background` -- vermeidet jede Literal-vs-Platzhalter-Kollision mit den
bestehenden `.../background/file`- und `.../background/repeat`-Routen) akzeptieren zusätzlich
`application/pdf` als Briefpapier-Quelle (reportlab kann keine PDF-Seite direkt zeichnen; nur
Seite 0 wird über `pypdfium2` -- neue, reine Wheel-Abhängigkeit ohne externe
Poppler-Installation, keine AGPL-Lizenzfrage wie bei PyMuPDF -- gerastert). Jede Quelle (PDF
oder direkt hochgeladenes Bild) wird einheitlich nach JPEG normalisiert: gemessen wurde, dass ein
ganzseitiger fotografischer/körniger Hintergrund als PNG bis zu ~3,7 MB groß werden kann, als
JPEG q85 nur ~0,9 MB -- bei sauberem, typischem Briefpapier ist der Unterschied vernachlässigbar.
Zusätzlich geprüft und beruhigend: reportlab bettet ein mehrfach identisch gezeichnetes
Hintergrundbild nur EINMAL in die PDF ein, unabhängig von der Seitenzahl. Ein deutlich von
A4-Hochformat abweichendes Seitenverhältnis wird beim Hochladen abgelehnt statt später verzerrt
gedruckt; innerhalb der Toleranz zeichnet der Rahmen mit `preserveAspectRatio=True` (skaliert und
zentriert) statt zu strecken -- anders als der unveränderte `quote_layout_pdf.py`, der weiterhin
streckt.

Neue Oberfläche unter Einstellungen → Mahnwesen-Layout (bewusst NICHT der bestehende
Drag-Canvas-Editor `document_layout_editor.html`, der für frei positionierbare Bausteine gebaut
ist -- die drei Rahmen-Bausteine der Mahnung sind nicht frei positionierbar, eine
Positions-Oberfläche wäre irreführend): zwei Briefpapier-Upload-Felder, Randabstände je
Seitentyp (wiederverwendet die bereits bestehenden, unveränderten `/margins/{page_type}`-
Endpunkte), drei Kontrollkästchen für Logo/Firmenkopf/Fußzeile.

## 1.3.0 – Monteursansicht ("Vor Ort") für das Fahrzeug-Tablet

Erster Minor-Sprung seit 1.2.0 -- der Monteur bekommt eine schmale, eigene Einstiegsseite
(`GET /vor-ort`, `app/templates/vor_ort.html`) statt einer zweiten App: dieselbe Codebasis,
dieselbe Anmeldung, aber eine reduzierte Kopfzeile (`_mobile_header.html` statt der vollen
Sidebar -- Einsätze/Zeiterfassung/Abmelden, alle ≥44px) und ein Web-App-Manifest fürs "Zum
Startbildschirm hinzufügen". Zeigt zwei unabhängige Listen: die heutigen Einsätze aus der
Plantafel (`list_todays_assignments_for_employee()` in `app/planning.py`, neuer Endpunkt
`GET /api/field-view/today`) und offene Entwurfsberichte, an denen der Mitarbeiter zuletzt
gearbeitet hat (`list_draft_reports_for_employee()`). Die Plantafel-Auflösung deckt beide
Zuordnungswege ab, über eine `PlanningSlot.id IN (...)`-Vereinigung: Team-Zugehörigkeit
(`WorkPreparationTeamEmployee`, Snapshot der Team-Besetzung) UND direkte Einzelzuweisung
(`WorkPreparationEmployee`, an der `WorkPreparation` selbst, nicht am Slot) -- ein Mitarbeiter
auf beiden Wegen für dieselbe AV zählt nur einmal. Ein Klick führt direkt zu
`/orders/{id}/service-reports` (die Berichtsseite), nie zur Auftragsseite. Kein neuer
`OPTIONAL_MODULES`-Eintrag -- eine neue Oberfläche über bereits bestehenden (Plantafel) bzw.
bereits eigenständig geschalteten (Wartungsberichte) Daten, kein neues fachliches Modul, analog
zu Dashboard und Plantafel selbst.

`service_reports.html` bleibt bewusst EIN Template (keine zweite mobile Vorlage), wird aber
responsiv: neue `@media(max-width:900px)`-Regeln bringen alle Bedienelemente auf mindestens
44px (Bestandsaufnahme hatte 34-40px gemessen), `ja_nein`/`leak_test` werden zu drei großen
Kacheln (`.result-picker`), `condition_grade` wechselt von einem `<select>` zu vier
Klartext-Kacheln (`setGradeAndSave()`, Muster `setResultAndSave()`), die Material- und
Zeitbuchungen-Tabellen klappen bei schmaler Breite zu gestapelten Karten (`data-label`-Attribute
+ CSS, kein horizontales Scrollen mehr nötig) statt nur zu scrollen, und alle drei
Foto-`<input type="file">` bekommen `capture="environment"`, damit die Kamera direkt öffnet. Die
Flächen-/Gruppen-Zuklappblöcke aus 1.2.22 bleiben unverändert -- sie funktionieren auf Tablet
bereits gut.

`ServiceReport` bekommt eine zweite, parallele Unterschrift: drei neue, nullable Spalten
`installer_signature_path`/`installer_signature_name`/`installer_signed_at`, exakt neben den
bestehenden (unverändert des Kunden gebliebenen) `signature_path`/`signature_name`/`signed_at` --
keine neue Tabelle, da die Kardinalität fix zwei bleibt (Monteur, Kunde). `sign_report()`
verlangt jetzt beide Unterschriften in einem Aufruf (Monteur zuerst, dann Kunde -- exakt der
Geräteablauf: Monteur unterschreibt, reicht das Tablet an den Kunden weiter), alle bestehenden
Vollständigkeitsprüfungen bleiben davor unverändert. Das Frontend macht daraus einen
Zwei-Schritt-Assistenten auf derselben Karte (Name des Monteurs vorbelegt mit dem angemeldeten
Benutzer, aber änderbar -- es kann jemand anders vor Ort gewesen sein). Das PDF zeigt bei einem
gesetzten `installer_signature_path` beide Unterschriften nebeneinander in einer Tabelle
("Monteur"/"Kunde") im selben 1.2.21-`KeepTogether`-Block; ein Bericht ohne
`installer_signature_path` (jeder vor 1.3.0 unterschriebene Bestandsbericht) durchläuft
unverändert den alten Ein-Block-Pfad -- byte-/textidentisches PDF, geprüft mit einem eigenen
Regressionstest.

**Härtung von `created_by_employee_id` an allen vier Stellen, die ihn kennen** (nicht nur beim
Bericht): ein neuer, gemeinsamer Helfer `_employee_for_request()`
(`app/routers/service_reports.py`, Kopie des Musters von
`_time_entry_employee_for_request()` in `app/routers/time_tracking.py`) sperrt einen
Nicht-Admin auf seine eigene `employee_id` -- angewendet auf `POST
/api/orders/{id}/service-reports` (Bericht), `POST /api/service-reports/{id}/photos` (Foto,
bekommt dafür erstmals einen `request`-Parameter), `POST /api/service-reports/{id}/materials`
(Material) UND `POST /api/service-reports/{id}/findings` (Mangel, `app/routers/findings.py`
importiert den Helfer statt ihn zu duplizieren). Vorher kam `created_by_employee_id` an allen
vier Stellen ungeprüft aus dem Client-Payload -- ein Mangel ist die Feststellung, aus der ein
Folgeauftrag entsteht, ein Bericht kann versehentlich unter fremdem Namen unterschrieben werden,
beides galt es zu verhindern, nicht nur beim Bericht selbst.

Automatisches Abmelden nach Feierabend: neue Singleton-Tabelle `MobileSettings`
(`shift_end_time`, Default 19:00, Verwaltung unter Einstellungen → Vor Ort) wird ausschließlich
an den beiden mobilen Einstiegspunkten geprüft (`GET /vor-ort`-Seite lädt nur das Gerüst, die
eigentliche Prüfung sitzt in `GET /api/field-view/today` -- ein serverseitiger Redirect auf der
Seite selbst wäre wanduhrzeit-abhängig gewesen und hätte den generischen Seiten-Rendertest
flackern lassen), NICHT in der globalen Middleware -- Schreibtisch-Nutzer mit demselben
Login-Mechanismus bleiben unberührt. Bewusst begrenzt: ein bereits offener Berichtstab wird beim
Erreichen der Grenze nicht mitten in der Bearbeitung abgemeldet (siehe "Bekannte, bewusst offene
Punkte"). Die 12-Stunden-Token-Laufzeit (`COOKIE_MAX_AGE`) reicht für eine normale Schicht,
keine Änderung nötig.

Web-App-Manifest (`GET /manifest.json`, `start_url: "/vor-ort"`, `display: "standalone"`) und
PWA-Icons (`GET /api/mobile-icon/{size}.png`, `app/mobile_manifest.py`) laufen wie jede andere
Datei-Auslieferung in diesem Projekt über einen dedizierten Endpunkt, kein `StaticFiles`-Mount
(es gibt im ganzen Projekt keinen einzigen). Ist ein Firmenlogo hinterlegt, wird es zentriert auf
ein Quadrat in der Akzentfarbe skaliert (Pillow, bereits Pflichtabhängigkeit seit 1.2.17), sonst
bleibt es beim einfarbigen Platzhalter -- reine Laufzeit-Erzeugung ohne Caching, da Icons nur
beim "Zum Startbildschirm hinzufügen" gebraucht werden. Kein Service Worker, keine
Offline-Logik (bewusst außerhalb dieser Iteration).

## 1.2.23 – Materialerfassung am Einsatzbericht, Rechnung aus Aufwand um Material erweitert

Der Monteur erfasst jetzt auch Materialverbrauch am Einsatzbericht -- neue Tabelle
`ServiceReportMaterial`, bewusst ohne jede Preisspalte, denn die Bepreisung passiert ausschließlich
beim Rechnungslauf im Büro. Zwei gleichwertige Erfassungswege: aus dem Katalog (`material_id`
gesetzt, `Bezeichnung`/`Einheit` werden dabei als Schnappschuss aus `Material` kopiert -- ändert
sich der Katalogeintrag später, bleibt im Bericht stehen, was tatsächlich verbaut wurde) oder frei
eingetippt (kein neuer Katalogeintrag, der Katalog ist Stammdatenpflege des Büros, nicht des
Monteurs). `roof_area_id`/`inspection_item_id`/`finding_id` sind alle unabhängig optional und
schließen sich -- anders als bei `ServiceReportPhoto` -- nicht aus; am Mangel gibt es dafür einen
neuen "+ Material"-Button, der den nächsten Eintrag direkt zuordnet. Unveränderlich nach der
Unterschrift wie Prüfpunkte und Fotos, `sign_report()` bekommt keine neue Pflichtprüfung. Die
Berichtsseite bekommt einen dritten Panel-Umschalter ("Material") auf gleicher Stufe wie
Prüfpunkte/Mängel, mit derselben Materialsuche (`GET /api/materials?search=`), die
`service_form.html` bereits für die Kalkulation nutzt -- kein zweites Widget, derselbe Endpunkt.
Das Berichts-PDF zeigt einen neuen Abschnitt "Verbrauchtes Material" nach den Prüfpunkten
(Bezeichnung/Menge/Einheit, keine Preise), bei mehreren Dachflächen nach Fläche gruppiert; ohne
Material bleibt das PDF byte-identisch zu 1.2.22.

`create_invoice_from_time_entries()` (Rechnung aus Aufwand) bekommt dafür einen neuen
`materials`-Parameter und bepreist Katalogmaterial mit dem AKTUELLEN Katalogpreis -- **mit** dem
Materialaufschlag aus `CalculationSettings.material_markup_pct`, demselben Mechanismus, der auch
im Leistungskatalog aus Einkaufs- den Verkaufspreis macht (neue Funktion
`effective_material_sale_price()` in `app/calculation.py`, dieselbe Formel wie
`build_calculation()`, ohne dieses bestehende, funktionierende Stück Code anzufassen). Den
ungefilterten Einkaufspreis als Rechnungspreis zu setzen, hätte Material ohne Aufschlag an den
Kunden weitergegeben, ohne dass es auffällt -- steht der Aufschlag auf 0 % (Standardwert jeder
Installation, die ihn nie konfiguriert hat), bekommt die Antwort deshalb einen sichtbaren,
einmaligen Hinweis (`material_markup_hint`, kein persistiertes Feld, keine neue Warnleiste, nur ein
`alert()` vor dem Navigieren zur neuen Rechnung). Frei eingetipptes Material bleibt bei Preis 0 und
wird -- anders als Katalogmaterial (nach `material_id`+Einheit gruppiert und summiert) -- nie
zusammengefasst, auch nicht bei identischem Text. Geprüft, ob eine zweite Rechnung aus Aufwand für
denselben Auftrag bereits abgerechnete Zeit/Material doppelt abrechnen könnte: ja, genau dieselbe
Lücke besteht heute schon bei Zeitbuchungen (kein "bereits abgerechnet"-Merkmal) -- Material
bekommt bewusst dieselbe, nicht behobene (Nicht-)Behandlung, keine neue Asymmetrie zwischen beiden;
siehe "Bekannte, bewusst offene Punkte".

## 1.2.22 – Ein Bericht je Objekt, ein Klick von der Vertragsseite, kompakte Berichtsseite

Umstrukturierung des Wartungsablaufs nach dem ersten echten Mehrflächen-Einsatz. Bisher hing ein
`ServiceReport` an genau einer `RoofArea` -- ein Objekt mit mehreren Dachflächen hätte mehrere
Berichte und mehrere Unterschriften gebraucht, obwohl der Kunde fachlich eine Wartung bekommt und
einmal unterschreibt. Neue Tabelle `ServiceReportRoofArea` (eine Zeile je beteiligter Fläche, mit
eigenem Vorlagen-Schnappschuss) löst das: `create_report()` nimmt jetzt `roof_area_ids` (Liste)
statt `roof_area_id`, generiert Prüfpunkte für jede Fläche gegen ihre eigene, passende Vorlage und
markiert `InspectionItem.roof_area_id` (neue Spalte) auf jedem erzeugten Punkt -- unabhängig davon,
ob er an ein Bauteil gebunden ist. Die bisherigen Schnappschuss-Spalten am Bericht selbst
(`roof_area_id`/`inspection_template_id`/`inspection_template_version`) bleiben für bestehende,
vor dieser Version angelegte Berichte unverändert bestehen (nie verworfene Daten), werden aber für
neue Berichte -- auch bei nur einer Fläche, bewusst ohne Sonderfall -- nicht mehr beschrieben.
`sign_report()`s Vollständigkeits-/Mängel-Prüfungen blieben dabei unverändert richtig, da sie
ohnehin über alle Prüfpunkte eines Berichts zählen, unabhängig von der Fläche.

Zweitens bestimmt der Dachtyp jetzt explizit statt implizit, welche Vorlage gilt: neue Tabelle
`RoofTypeInspectionTemplateDefault` (Einstellungen -> Prüfvorlagen, neuer Abschnitt), eine
Migration übernimmt für bestehende Installationen genau die Vorlage, die die bisherige implizite
Auflösung (niedrigster `sort_order`) auch gewählt hätte. Gibt es für einen Dachtyp keine explizite
Zuordnung, aber genau einen nicht archivierten Kandidaten, wird dieser trotzdem verwendet -- erst
bei mehreren Kandidaten ohne explizite Zuordnung wird nicht mehr geraten (das war die eigentliche
Beschwerde: "zu implizit" bezog sich auf den Mehrdeutigkeitsfall, nicht auf den eindeutigen).

Drittens ein neuer Button "Wartung durchführen" auf der Vertragsseite (`app/maintenance_contracts.
py::create_maintenance_visit()`, `POST /api/maintenance-contracts/{id}/perform-maintenance`):
legt in einem Schritt Auftrag (über `create_quick_service_order()`, ohne Mustervorgang -- Wartung
wird über die Vertragspauschale oder nach Aufwand abgerechnet) UND einen vorbereiteten
Wartungsbericht über ALLE nicht archivierten Dachflächen des Objekts an und navigiert direkt in
den Bericht. Die Fälligkeit des Vertrags wird dabei bewusst NICHT beim Anlegen fortgeschrieben
(anders als beim bestehenden "Vorgang erstellen"), sondern erst bei der Unterschrift (neue Spalte
`ServiceReport.advance_due_date_on_sign`) -- ein angelegter, aber nie unterschriebener Bericht soll
den Turnus nicht verschieben. Dafür wandert die bisher lokale `_add_months()`-Datumsarithmetik aus
`app/maintenance_contracts.py` in ein neues, gemeinsames Hilfsmodul `app/date_utils.py`, damit
`service_reports.py` sie ohne Zirkel-Import mitverwenden kann.

Viertens wird die Berichtsseite (`service_reports.html`) bei mehreren Flächen mit je ~20
Prüfpunkten kompakt: Prüfpunkte gruppieren sich nach Dachfläche (zugeklappt, mit Fortschritt "12
von 31") und darin nach `group_name` (aufgeklappt), ein Gesamtfortschritt samt Liste offener
Pflichtpunkte steht oberhalb allem, Mängel rendern jetzt inline am jeweiligen Prüfpunkt statt nur
in einem separaten Block am Seitenende (das flache Panel bleibt zusätzlich als Übersicht für
Mängel ohne Prüfpunktbezug bestehen), und jeder Prüfpunkttyp kann jetzt eine Bemerkung tragen
(vorher nur Freitext-Punkte), aufklappbar bei Bedarf. Beim Öffnen eines Berichts ist keine
Prüfliste aufgeklappt.

## 1.2.21 – Vier Korrekturen: Monteur bleibt im Bericht, Vorgang aus der Aufgabe, Zeitbuchung ohne Ausflug, Unterschrift ungeteilt

Erster vollständiger Durchlauf durch einen Wartungsbericht, vier Korrekturen, alle an Stellen,
an denen der Monteur mitten in der Erfassung aus dem Ablauf geworfen wurde. Größter Eingriff:
die Mangel-Maßnahmen "folgeauftrag" und "angebot_erforderlich" waren fachlich dieselbe
Entscheidung ("das muss vom Büro aus weiterbearbeitet werden"), zwangen den Monteur auf dem
Dach aber vorher zu raten, ob daraus ein Angebot oder ein Auftrag wird -- und "folgeauftrag"
erzeugte dabei sofort einen echten Auftrag samt Projekt über `create_quick_service_order()`
und sprang mitten im noch nicht unterschriebenen Bericht in die Projektmappe. Beide Maßnahmen
sind jetzt zu einer einzigen, "buero_pruefen" ("Büro prüfen lassen"), zusammengeführt, die IMMER
nur eine Aufgabe erzeugt, nie einen Auftrag/nie ein Navigieren. Der eigentliche Vorgang entsteht
erst, wenn der Sachbearbeiter aus dieser Aufgabe heraus bewusst auf eine neue Schaltfläche
"Vorgang erstellen" klickt (zwei neue Endpunkte `GET/POST /api/tasks/{id}/finding` bzw.
`/create-follow-up-project`, Business-Logik in `app/findings.py`) -- der Rückweg von der Aufgabe
zum Mangel läuft dabei bewusst über die bereits seit 1.2.17 bestehende Spalte
`Finding.follow_up_task_id` (eine gezielte Abfrage), keine neue Spalte an `Task`. Eine reine
Daten-Migration schreibt bestehende Findings mit den beiden alten Maßnahmen auf "buero_pruefen"
um, ohne ihre `follow_up_*`-Spalten anzufassen -- dabei ein eigener Fund: ein ehemals
"folgeauftrag"-Mangel trägt nur `follow_up_order_id`, nie ein `follow_up_task_id` (er hat ja nie
eine Aufgabe erzeugt); die Idempotenzsperre musste deshalb auf beide Artefakte erweitert werden,
sonst hätte ein migrierter Mangel fälschlich eine zweite, überflüssige Aufgabe bekommen können.

Zweitens führte eine Zeitbuchung aus dem Einsatzbericht heraus in die volle Zeiterfassungsseite,
ohne einen Weg zurück -- der Monteur verlor seinen Platz im Bericht. Geprüft, ob sich das
Rückspringen einfacher lösen lässt als ein zweites Formular: die eigentliche Geschäftslogik
einer manuellen Zeitbuchung (Validierung, Rundung nach den Zeiterfassungs-Einstellungen,
Berechtigung "nur eigene Zeiten außer Admin") sitzt bereits vollständig im bestehenden Endpunkt
`POST /api/time-entries`, nicht im Template der Zeiterfassungsseite -- ein kompaktes,
zusätzliches Formular direkt auf der Berichtsseite ruft genau diesen Endpunkt auf und dupliziert
damit keine Logik, nur eine schlankere Eingabemaske. Timer und Gruppenbuchungen (die tatsächlich
komplexen Teile der vollen Zeiterfassung) werden bewusst nicht nachgebaut -- der Berichts-
Kontext braucht nur eine bereits abgeschlossene Menge Stunden. Zeitart bekommt dabei ein eigenes
Dropdown (vorbelegt "Baustellenzeit") statt fest verdrahtet zu sein, sonst müsste der Monteur für
Anfahrtszeit doch wieder in die volle Zeiterfassung wechseln. Die Tabelle "Erfasste Zeiten zu
diesem Auftrag" bekommt zusätzlich eine Summenzeile.

Viertens konnte im erzeugten Einsatzbericht-PDF die Unterschrift über den Seitenumbruch
gerissen werden, für ein Nachweisdokument nicht hinnehmbar. `reportlab`s `KeepTogether` (bisher
nirgends im Projekt verwendet) hält den kompakten Unterschriftenblock (Titel, Bestätigungssatz,
Bild) jetzt zusammen -- bewusst kein erzwungener Seitenumbruch davor, das hätte bei jedem kurzen
Bericht eine unnötige, fast leere Seite erzeugt. Bei der Gelegenheit dieselbe Behandlung für
jeden Mangel-Block (Beschreibung plus seine Fotos, der vom Klicktest selbst genannte Fall),
jede Prüfpunkt-Gruppen-Überschrift plus ihre Tabelle, jeden Dokumentation-Fotoblock und den
Abschnitt "Erfasste Zeiten" -- überall dort, wo eine Überschrift von ihrem zugehörigen Bild/
ihrer Tabelle getrennt werden könnte. Bewusst nicht angewendet auf den freien Beschreibungstext,
der wie in jedem Dokument über Seiten umbrechen darf.

## 1.2.20 – Zweiter Klicktest: Weg zum Einsatzbericht, irreführende Feldbeschriftung

Zweiter Klicktest, diesmal auf 1.2.19. Größter Blocker: aus einem per "Vorgang erstellen"
angelegten Projekt fand sich kein Weg zum Einsatzbericht – `order.html` hatte schlicht keinen
Link auf `/orders/{id}/service-reports`, nicht nur einen unauffälligen. Neuer, erst nach
`isModuleEnabled('wartungen')` eingeblendeter Link im `top-actions`-Bereich der Auftragsseite
(Text `Einsatzberichte (N)` bzw. `Einsatzbericht anlegen` bei 0), dieselbe Ergänzung als neue
Spalte in der Auftragstabelle auf der Projektseite (gated über eine neue, per Jinja-Global
gesetzte JS-Konstante `maintenanceModuleEnabled` – gleiches Muster wie der dort bereits
vorhandene "Wartungsvertrag erstellen"-Button, nur für eine clientseitig gebaute Tabellenzelle
statt einen serverseitig ausgeblendeten Button). Die Zählung läuft über eine neue, schlanke
`count_reports_for_order()` (Muster `finding_count`), durchgereicht über ein neues Feld
`OrderListOut.service_report_count`. Die Berichtsseite selbst hatte zwar schon einen Rückweg zum
Auftrag, aber der Kunde stand dort nur als Text – `OrderOut`/`order_to_dict()` bekommen dafür
zusätzlich `customer_id` (aus dem bereits eager geladenen `Order.project`, keine neue Abfrage),
womit eine echte Breadcrumb (Kunde → Auftrag → "Einsatzberichte", Muster `property.html`/
`roof_area.html`) möglich wird.

"Vorgang erstellen" auf der Vertragsdetailseite navigiert seit dieser Version bewusst NICHT mehr
sofort weiter, sondern zeigt ein Ergebnis-Panel mit echtem Link – eine ausdrücklich geforderte
Ausnahme von der sonst geltenden Sofort-Navigieren-Regel, weil der eigentliche nächste Schritt
(Einsatzbericht) vom neuen Vorgang aus zwei Ebenen entfernt liegt (Angebot beauftragen → Auftrag
entsteht → darüber Bericht anlegen) und ein stiller Sprung zum Projekt allein nicht zeigt, wie es
weitergeht. Geprüft, ob das neue Projekt schon einen Auftrag hat (praktisch nie der Fall direkt
nach dem Anlegen, siehe unten) – falls doch, verlinkt das Panel direkt auf dessen Berichtsseite.

Zweiter Fund: "Mustervorgang" war auf der Vertragsdetailseite und dem Anlegen-Formular als
"(optional)" beschriftet, obwohl `create_project_from_contract()` ohne ihn zuverlässig mit
`ValueError` ablehnt. Beide Stellen bekommen jetzt denselben Hinweistext wie die bereits
bestehende Meldung unter der deaktivierten "Vorgang erstellen"-Schaltfläche, damit beide dieselbe
Sprache sprechen; derselbe, eine Ebene tiefer liegende Fall bei der Positions-Ebene
(`itemTemplate`, "sonst der des Vertrags") ebenfalls ergänzt. Alle übrigen "optional"-
Beschriftungen im Modul wurden geprüft – keine weiteren Fälle, jede hat einen echten, im
Hinweistext bereits genannten Rückfall.

Dritter Punkt war eine Beobachtung, keine Änderung: ein aus einem Wartungsvertrag erzeugtes
Projekt zeigte angeblich sowohl ein Angebot als auch einen Auftrag, was `duplicate_project()`s
eigenem Docstring widerspräche ("Bewusst NICHT mitkopiert: ein eventuell vorhandener Auftrag").
Sowohl die Code-Prüfung (kein `Order`-Konstrukt in `duplicate_project()` oder
`_copy_quote_into_project()`, `status` immer hartkodiert `"anfrage"`) als auch der einzige dazu
nachvollziehbare echte Datensatz in der laufenden Installation bestätigten übereinstimmend das
korrekte, erwartete Verhalten – nicht reproduzierbar, deshalb bewusst keine Codeänderung.
Wahrscheinlichste Erklärung: der Auftrag entstand durch einen eigenen, nicht mehr erinnerten
Klick auf "Beauftragen" beim Testen des neuen Angebots, unabhängig vom "Vorgang erstellen"-Weg.

Zusätzlich, unabhängig von den drei gemeldeten Punkten: ein neuer Test rendert jede Seiten-Route
aus `app/routers/pages.py` einmal über den `TestClient` und prüft auf Status 200 – die Suite
deckte Templates bisher gar nicht ab, ein Rekursionsfehler wie der in `_debounce.html` (1.2.19)
wurde nur durch die manuelle Server-Smoke-Prüfung gefunden. Die Route-Liste wird dynamisch aus
den registrierten Routen gewonnen statt hartkodiert, damit sie nicht veraltet. Dabei eine
bestehende, vom Test nicht verursachte Kopplung entdeckt und geprüft, ob sie sich mit wenig
Aufwand beheben lässt: die Jinja-Globals `get_theme()`/`is_module_enabled()` öffnen bei jedem
Rendern eine eigene Verbindung zur echten Datenbankdatei statt die per `get_db()` injizierte,
in Tests austauschbare Session zu nutzen. Eine echte Umstellung hätte sieben Vorlagen und rund
30 Seiten-Router angefasst oder einen neuen contextvar-Mechanismus verlangt – kein kleiner Fix,
bleibt daher im Merkzettel; für den rein lesenden Rendertest selbst unschädlich, aber im
Test-Docstring festgehalten, damit kein künftiger, auch schreibender Test sich daran orientiert.

## 1.2.19 – Erster echter Klicktest: Datenverlust, Bedienlücken, fehlende Felder

Sieben Punkte aus dem ersten echten Klicktest von 1.2.18. Am wichtigsten: ein in der
Dachaufbau-Schichtenliste eingetippter Bemerkungstext ging nach einem Neuladen verloren. Die
tatsächliche Ursache erst gesucht, dann behoben, wie ausdrücklich verlangt -- beide vorab
geäußerten Vermutungen waren wörtlich falsch, hatten aber je einen realen, verwandten Kern.
Erstens ist `onchange` blur-abhängig: tippt man den Text ein und lädt direkt neu, ohne vorher
wegzuklicken, feuert der Handler nie, der Wert wird nie abgeschickt -- unabhängig von jeder
Zeitkoinzidenz, allein aus der HTML-Spezifikation. Zweitens überschrieb `upsert_roof_layer()`
unbedingt alle vier Spalten bei jedem Aufruf; da `setLayerPresent()` seinen eigenen Speichervorgang
ohne `await` auslöst und kurz danach ein zweiter Speichervorgang für den eingetippten Text folgt,
ließ sich das (empirisch mit zwei nebenläufigen Sessions auf derselben Engine nachgestellt) so
zu einem Race verschärfen, bei dem ein älterer Schnappschuss beim Server zuletzt committet und
einen neueren überschreibt -- exakt der `build_up`-Fehlertyp aus 1.2.18, nur eine Ebene tiefer.
Behoben in zwei Teilen: `RoofLayerUpsert` unterscheidet jetzt über `exclude_unset` "nicht
mitgeschickt" von "ausdrücklich geleert", `upsert_roof_layer()` überschreibt nur noch tatsächlich
enthaltene Felder, und `roof_area.html` sendet je Änderung nur noch das geänderte Feld statt eines
vollen Zeilen-Schnappschusses. Ein neuer, geteilter Helfer `_debounce.html` (per Jinja-Include,
ein zweites Mittel neben `_sidebar.html`, JS zwischen Seiten zu teilen) schließt zusätzlich die
Blur-Abhängigkeit: Bemerkungs- und Dicke-Felder speichern jetzt auch 600ms nach der letzten
Eingabe, unabhängig vom Fokus. Bei der Gelegenheit geprüft: `update_inspection_item()` hatte
dieselbe Lücke in einer deterministischen (nicht Race-abhängigen) Variante -- `setResultAndSave()`
sendete bei jedem OK/Nicht-OK/Entfällt-Klick nur `{result}` und übersprang dabei den sonst
üblichen Container-Read, wodurch ein `leak_test`-Punkt sein `duration_minutes` bei jedem Klick
verlor. Jetzt liest `saveInspectionResult()` den Container immer und legt Overrides nur noch
darüber, `update_inspection_item()` selbst wechselt ebenfalls auf `exclude_unset`. Aus demselben
Anlass bekommt auch das Pflicht-Freitextfeld in `service_reports.html` das debounced Speichern --
tippt ein Monteur einen Punkt aus und drückt direkt "Unterschreiben", hätte `sign_report()` sonst
fälschlich "Pflichtpunkt nicht beantwortet" gemeldet. `update_roof_component()` wurde ebenfalls
geprüft: sein einziger Aufrufer sendet immer einen vollständigen Schnappschuss aus einem echten
Bearbeiten-Formular, kein granulares Autosave -- bewusst unverändert gelassen.

Zweitens verschwindet das Wort "Position" aus der Oberfläche der Wartungsverträge -- was fachlich
weiterhin `MaintenanceContractItem` heißt, heißt für den Nutzer jetzt durchgängig "Zu wartende
Dachfläche". Eine neue Einstellung `MaintenanceSettings.use_roof_area_items` (Default aus)
entscheidet, ob dieser ganze Mechanismus überhaupt zum Einsatz kommt: ist sie aus, verhält sich
jeder Vertrag ausschließlich über Intervall/nächste Fälligkeit, auch wenn er noch Altbestand-
Positionen aus einer Zeit trägt, in der die Einstellung an war -- diese Zeilen bleiben in der DB
stehen, werden aber weder angezeigt noch für Fälligkeit/Erinnerung ausgewertet
(`_is_due()`/`check_due_contracts_and_create_reminders()`/`create_project_from_contract()`, dazu
das Dashboard-Widget "Fällige Wartungen", das dieselbe Lücke unabhängig vom Auftrag hatte).
`create_contract_item()` lehnt bei ausgeschalteter Einstellung zusätzlich ab (Verteidigung in der
Tiefe, die Oberfläche zeigt den Abschnitt dann ohnehin nirgends).

Drittens ist "Vorgang erstellen" jetzt immer sichtbar, sobald ein Mustervorgang existiert --
vorher nur bei Fälligkeit, was einen frisch angelegten Vertrag praktisch untestbar machte. Ist der
Vertrag noch nicht fällig, fragt ein `confirm()` mit dem regulären Fälligkeitsdatum nach, bevor der
ohnehin schon fälligkeitsblinde `create_project_from_contract()` aufgerufen wird. Fehlt ein
Mustervorgang, bleibt die Schaltfläche sichtbar, aber deaktiviert, mit einem erklärenden Hinweis --
nie einfach ausgeblendet.

Viertens bekommt jeder Wartungsvertrag eine eigene Seite `GET /maintenance-contracts/{id}`
(`maintenance_contract.html`, Muster `property.html`): Breadcrumb Kunde → Objekt → Vertrag,
Stammdaten-Editor, Status-Aktionen, die "Zu wartende Dachflächen" (nur bei eingeschalteter
Einstellung), Vertragshistorie und "Vorgang erstellen" -- alles, was bisher inline auf der Liste
aufklappte. Die Liste `/maintenance-contracts` bleibt schlank (Übersicht, Anlegen-Formular,
"Fällige Wartungen im Fenster", Reparatur/Wartung erfassen), jede Zeile verlinkt auf die
Detailseite; nach dem Anlegen eines Vertrags geht es direkt dorthin.

Fünftens wird `RoofLayerType.has_thickness` zu drei Flags: `has_execution` (Ausführungsauswahl
unabhängig von der hinterlegten Optionsgruppe abschaltbar), `has_thickness` (unverändert) und
`has_notes` (Bemerkungsfeld abschaltbar) -- ein deaktiviertes Feld verschwindet nur aus der
Anzeige, die neue `exclude_unset`-Architektur aus Punkt 1 sorgt automatisch dafür, dass es beim
Speichern nie überschrieben wird. Kleine Korrektur am eigenen Entwurf: die Vorgabe für `has_notes`
widersprach sich selbst (`default=True` bei gleichzeitigem `server_default="0"`) -- vereinheitlicht
auf `True`/`"1"`, da die Migration ohnehin alle 25 bestehenden Schichttypen auf `has_notes=true`
setzt.

Sechstens lassen sich Bauteile jetzt auch flächig auf der Skizze markieren (z. B. ein
Photovoltaik-Feld als Rechteck statt als Punkt) -- Ziehen statt Tippen, per `pointerdown`/
`pointermove`/`pointerup` wie beim Unterschriften-Canvas. Ob eine Bauteilart flächig ist, hängt
an der Bauteilart selbst, nicht am einzelnen Bauteil: `roof_component_types` (bisher eine reine
`SettingOptionGroup`) wird dafür zur echten Tabelle `RoofComponentType` hochgestuft, nach dem
`RoofLayerType`-Vorbild aus 1.2.18 -- ein `grep` über das Projekt zeigte, dass `component_type`
nicht nur für die Skizzenmarker gelesen wird, sondern auch von `InspectionTemplateItem.
component_type` für den 1.2.16-Abgleich "Vorlage gegen Bauteilbestand"; der neue `key` bleibt
deshalb textidentisch zu den bisherigen Options-Werten, `RoofComponent.component_type` bleibt ein
einfacher String, kein Fremdschlüssel. Die Migration liest die Werte für die neue Tabelle bewusst
NICHT aus der Code-Konstante, sondern aus den tatsächlichen, bereits vorhandenen
`setting_options`-Zeilen der DB -- eine Installation kann seit 1.2.14 eigene Bauteilarten angelegt
haben, die nur dort stehen; erst wenn die Gruppe ganz fehlt (frische, nie gesäte DB), fällt sie auf
die 15 Code-Werte zurück. Dabei zwei weitere, an derselben Stelle hängende Fundstellen korrigiert:
`inspection_template.html` und die generische Auswahllisten-Verwaltung in `settings.html` lasen
noch von der jetzt entfernten Optionsgruppe.

Siebtens: `Customer.phone` existierte entgegen der Annahme bereits und war bereits überall
angebunden -- nur `fax` fehlte tatsächlich und wurde ergänzt (`customer.html`,
`master_data_form.html`). Weitere Prüfung wie gefordert: keine anderen unangebundenen Felder an
`Customer`/`CustomerProfile` gefunden.

Bei der abschließenden Smoke-Prüfung am echten Server ein eigener Fehler im ersten Entwurf
gefunden: der Kommentar in `_debounce.html` erklärte den Einbindungsmechanismus, indem er den
wörtlichen Jinja-Tag als Text zitierte -- Jinja erkennt `{% include %}` unabhängig davon, ob er in
einem JS-Kommentar steht, band die Datei damit rekursiv in sich selbst ein und brachte `/roof-areas/
{id}` und die Einsatzbericht-Seite mit `RecursionError` zum Absturz. Der Kommentar beschreibt den
Mechanismus jetzt in Prosa statt den Tag zu zitieren.

## 1.2.18 – Objekt-/Dachflächen-Stammdaten aufgeräumt, Dachaufbau als Schichtenliste

1.2.14 war im ersten echten Gebrauch an fünf Stellen unfertig geblieben. Erstens fehlte auf `/roof-areas/{id}` die Rückwärts-Navigation -- die Breadcrumb zeigte das Objekt nur als Text, nicht als Link. Zweitens gab es zwei unterschiedlich reiche Ansichten auf dasselbe Objekt: die Kundenakte (mit Dachflächenliste) und die generische Stammdatenmaske (nur vier flache Felder). Eine neue, echte Objektseite `GET /properties/{id}` (`property.html`, Muster `roof_area.html`) zeigt jetzt beides gemeinsam plus -- sofern das Modul "Wartungen & Reparaturen" aktiv ist -- die zugehörigen Wartungsverträge (`list_contracts_for_property()`, eine reine `select`-Abfrage statt einer Relationship nur für diesen einen Anzeigefall, da `Property` laut Bestandsaufnahme keine Rückwärts-Relationship zu `MaintenanceContract` hat). Beide bestehenden Wege führen jetzt dorthin: die Kundenakte bekommt einen "Öffnen"-Link je Objekt-Karte, die generische Stammdatenmaske leitet beim Bearbeiten sofort auf die neue Seite weiter und navigiert nach dem Anlegen direkt zum neuen Datensatz -- beide Änderungen bewusst auf den ohnehin typspezifischen `properties`-Zweig der generischen Verwaltung begrenzt, kein Umbau, der andere Stammdatentypen berührt.

Drittens ließ sich nur eine Dachfläche auf einmal anlegen, obwohl ein Gebäude selten nur eine hat -- ein neues Mehrfach-Formular auf der Objektseite (ein Dachtyp für alle, mehrere Namenszeilen) legt sie über einen neuen Endpunkt `POST /api/properties/{id}/roof-areas/bulk` in einem Schritt an, intern unverändert über `create_roof_area()` je Zeile. Viertens war die Klick-Positionierung auf der Dachskizze ohne hochgeladene Skizze unerklärt -- die Spalte "Position gesetzt" (jetzt "Auf Skizze markiert") blendet sich ganz aus, solange keine Skizze hinterlegt ist, mit einem klaren Hinweis statt der Spalte; ist eine Skizze da, erklärt ein Satz über dem Bild, wozu die Marker dienen.

Fünftens und fachlich am größten: `RoofArea.build_up` (Freitext) und `RoofArea.insulation` weichen einer strukturierten, dachtyp-abhängigen Schichtenliste (`RoofLayerType`/`RoofLayer`) -- ein Steildach fragt nach Unterspannbahn und Aufsparrendämmung, ein Flachdach nach Dampfsperre und Gefälledämmung. Die Ausführungslisten laufen über den bestehenden `SettingOptionGroup`-Mechanismus (sechs neue Gruppen `layer_*`), bewusst NICHT über den Leistungskatalog -- der Katalog dient der Preisfindung, der Dachaufbau der Dokumentation, was vor zwanzig Jahren verbaut wurde steht in keinem aktuellen Katalog. Fehlt eine Ausführung im Dropdown, lässt sie sich direkt dort per "+ Neu…" ergänzen (über den bereits bestehenden Endpunkt zum Anlegen einer Option), kein `prompt()`. Die 25 Schichttypen (Steildach 7, Flachdach 7, Gründach 11) kommen als Daten-Migration, nicht als Selbst-Seeding wie die Optionsgruppen -- eine echte Tabelle mit eigener Verwaltung unter Einstellungen → Dachaufbau (ungated, Muster wie die Wartungsfenster: Löschen blockiert bei Verwendung, Deaktivieren bleibt frei).

Gründach bekommt dabei bewusst dieselben 7 Schichten wie Flachdach unter eigenen `key`-Werten noch einmal, statt sie über `roof_type IS NULL` zu teilen -- NULL bedeutet "gilt für jeden Dachtyp" und hätte einem Steildach fälschlich auch Dampfsperre und Abdichtung angezeigt. Bekannte, in Kauf genommene Schwachstelle dieser Redundanz: siehe "Bekannte, bewusst offene Punkte" unten. Bei einem nachträglichen Dachtypwechsel bleiben bereits erfasste Schichten stehen, statt gelöscht zu werden -- eine erfasste "Aufsparrendämmung, 160mm, Mineralwolle" bleibt eine wahre Aussage über das Gebäude, auch wenn der Dachtyp jetzt anders heißt; die Oberfläche kennzeichnet nur, dass eine Zeile nicht mehr zum aktuellen Dachtyp passt. Die alten Spalten `build_up`/`insulation` werden nicht gelöscht, aber kein Code-Pfad schreibt sie mehr -- die Oberfläche zeigt sie nur noch schreibgeschützt als "Aufbau (Altbestand, Freitext)", wenn befüllt. Das war nötig, um einen im ersten Entwurf gefundenen Fehler zu vermeiden: ein `update_roof_area()`, das diese Felder weiterhin als Parameter angenommen hätte, hätte bei jedem Speichern über das neue, reduzierte Formular automatisch `None` übernommen und den historischen Freitext beim nächsten Speichern eines beliebigen anderen Feldes stillschweigend gelöscht.

## 1.2.17 – Mängel und Fotos am Einsatzbericht

Bisher endete ein Wartungsbericht bei einer abgehakten Checkliste (`InspectionItem`, 1.2.16) -- ein negatives Ergebnis ("Ablauf nicht frei") hatte keine Konsequenz. Zwei neue Tabellen schließen genau diese Lücke: `Finding` (Mangel, mit festen Tupeln `severity`/`action`/`status` statt Optionsgruppen) und `ServiceReportPhoto` (Foto, gehört immer zu GENAU EINEM Prüfpunkt ODER GENAU EINEM Mangel -- rein in der Business-Logik erzwungen, kein `CheckConstraint`, da es der erste seiner Art in diesem Projekt wäre). `roof_component_id` wird beim Anlegen eines Mangels aus dem Prüfpunkt übernommen, falls vorhanden -- der 1.2.16 vorausschauend gebaute Blockier-Schutz auf `delete_roof_component()` bekommt damit einen zweiten, vom Berichtsstatus unabhängigen Fall: ein Mangel entfaltet seine Wirkung (Folgeauftrag, Aufgabe, Wiedervorlage) bereits während der Bericht noch Entwurf ist. Fotos werden serverseitig mit Pillow (bereits eine über `reportlab` gezogene Pflichtabhängigkeit, jetzt zusätzlich explizit in `requirements.txt`) auf 1600 px verkleinert und einheitlich als JPEG gespeichert, inklusive `exif_transpose()` gegen die reine Metadaten-Drehung von Handyfotos.

Die vier Maßnahmen (`action`) haben je einen eigenen, einmaligen Ausführungsschritt: "sofort_behoben" schließt direkt, "folgeauftrag" erzeugt über das bestehende `create_quick_service_order()` (unverändert wiederverwendet, keine neue Project→Quote→Order-Kette) einen echten Reparaturauftrag und schreibt die Herkunft zusätzlich als Text in die `description` des neuen Projekts -- so überlebt die Spur auch das spätere Löschen des ursprünglichen Entwurfsberichts, "angebot_erforderlich" legt bei aktivem Aufgabenmodul über `create_task()` eine Aufgabe an, "zurueckgestellt" verlangt ein Wiedervorlagedatum. Die Idempotenzsperre gegen ein doppeltes Anlegen hängt bewusst NICHT an "war die Maßnahme vorher etwas anderes", sondern am eigenen Ausführungs-Artefakt der jeweiligen Maßnahme (`follow_up_order_id`/`follow_up_task_id`) -- das erlaubt sowohl das spätere Nachholen einer bei deaktiviertem Aufgabenmodul ausgefallenen Aufgabe als auch einen jederzeitigen Wechsel weg von "sofort_behoben" (mit Rücksetzen von `closed_at`). `update_finding_followup()` ist dabei die einzige Stelle, die einen Mangel auch nach der Unterschrift des Berichts noch ändern darf -- eingefroren ist die Feststellung (Beschreibung, Schweregrad, Bauteilbezug, Fotos), lebendig bleibt ihre Nachverfolgung, genau das bereits etablierte Muster von `sign_report()` neben dem allgemein blockierten `update_report()`. Bewusst NICHT gebaut: ein zweiter, aus dem Folgeauftrag entstandener Bericht schließt den ursprünglichen Mangel nie automatisch -- passend zum durchgängigen "kein Schritt ohne bewussten Klick"-Prinzip dieses Projekts, der Rückweg bleibt ein manuelles `update_finding_followup(status="erledigt")`.

`sign_report()` bekommt drei weitere Prüfungen nach der bestehenden Pflichtpunkt-Prüfung aus 1.2.16: ein Prüfpunkt mit negativem Ergebnis braucht einen Mangel, jeder Mangel braucht mindestens ein Foto, ein zurückgestellter Mangel braucht ein Wiedervorlagedatum -- ein Bericht ohne Prüfpunkte und ohne Mängel bleibt davon unberührt. Bei der Umsetzung ein echter Fehler im ersten Entwurf gefunden und korrigiert: `create_finding()`/`update_finding_followup()` fingen einen Fehler bei der Maßnahmen-Ausführung (z. B. "zurueckgestellt" ohne Datum) zunächst nicht ab -- die bereits angelegte bzw. geänderte Zeile blieb dadurch als nie zurückgerollte Karteileiche in der Datenbank-Sitzung hängen und wäre vom nächsten, völlig unabhängigen erfolgreichen Speichern stillschweigend mit übernommen worden. Beide Funktionen rollen bei einem Fehlschlag jetzt gezielt zurück. Neue Übersichtsseite `/findings` (Mängelliste über alle Objekte, Filter nach Status/Schweregrad/Objekt/Zeitraum/überfälliger Wiedervorlage), Mängelhistorie je Bauteil auf der Dachflächenseite, Dashboard-Widget "Akute Mängel" und zwei neue PDF-Abschnitte ("Dokumentation" für Prüfpunkt-Fotos ohne Mangel, "Festgestellte Mängel") -- ein Bericht ohne Mängel und ohne Fotos rendert dabei exakt wie vor dieser Version.

## 1.2.16 – Strukturierte Prüfpunkte für Einsatzberichte

Eine Wartung prüft nicht "das Dach", sondern sieben Gullys, vierzig Meter Rinne und drei Lichtkuppeln -- bisher war `ServiceReport.description` dafür nur ein einziges Freitextfeld ohne Struktur. Neue Prüfvorlagen (`InspectionTemplate`/`InspectionTemplateItem`, verwaltet unter Einstellungen → Prüfvorlagen, je Dachtyp) beschreiben, was je Bauteilart zu prüfen ist -- beim Anlegen eines Wartungsberichts wird die Vorlage gegen den tatsächlichen Bauteilbestand der ausgewählten Dachfläche multipliziert und erzeugt so konkrete Prüfpunkte (`InspectionItem`, sieben Punkttypen: Ja/Nein, Zustandsstufe, Messwert mit Soll-Bereich, Menge, Dichtheitsprüfung, Freitext, Foto). Alle anzeigerelevanten Felder werden dabei physisch auf den Prüfpunkt kopiert, nie zur Laufzeit von der Vorlage gelesen -- ändert sich die Vorlage später, ändert sich ein bereits erzeugter Bericht nicht rückwirkend, genau wie bei anderen unveränderlichen Dokumenten in diesem Projekt.

Für den Fall, dass sich der Bauteilbestand zwischen Berichtsanlage und Ausführung ändert, gibt es zwei getrennte Mechanismen: eine neue, rein additive `sync_inspection_items()` ergänzt automatisch und unauffällig beim Öffnen der Berichtsseite fehlende Punkte für inzwischen hinzugekommene Bauteile, ohne je erfasste Ergebnisse anzurühren oder Punkte zu entfernten Bauteilen zu löschen; `regenerate_inspection_items()` baut auf ausdrücklichen Klick mit Datenverlust-Warnung alles neu auf. `sign_report()` verschärft sich um eine Vollständigkeitsprüfung: existieren Prüfpunkte, müssen alle Pflichtpunkte beantwortet sein, sonst schlägt die Unterschrift mit der Anzahl der offenen Punkte fehl -- Berichte ohne Prüfpunkte verhalten sich unverändert wie bisher. Der PDF-Export bekommt einen neuen Abschnitt "Prüfpunkte" (gruppiert, mit formatiertem Ergebnis je Punkttyp, ein Messwert außerhalb des Soll-Bereichs wird optisch hervorgehoben) -- ohne den wäre der zentrale Zweck eines Wartungsberichts für den Kunden nicht im Dokument gelandet, das noch im ersten Entwurf übersehen und vor der Umsetzung ergänzt wurde.

`delete_roof_component()` bekommt vorausschauend denselben Blockier-Schutz wie `delete_roof_area()` (1.2.15): ein Bauteil, auf das ein bereits unterschriebener Bericht verweist, kann nicht mehr gelöscht werden, nur archiviert -- obwohl die aktuellen Prüfpunkte das eigentlich nicht bräuchten (sie kopieren ihren Text physisch), wird eine für die nächste Iteration geplante Mängelhistorie das Bauteil aktiv dereferenzieren, und den Schutz dann nachzurüsten wäre eine Verhaltensänderung an einem bereits benutzten Endpunkt. Bei der Umsetzung außerdem zwei kleinere, im ersten Entwurf übersehene Probleme gefunden und korrigiert: die Formel für die Sortierreihenfolge generierter Prüfpunkte wäre bei einer Bauteil-Sortierposition ab 1000 in das Band des nächsten Vorlagenpunkts gerutscht (jetzt mit einem Modulo auf ein festes Band begrenzt), und die seit 1.2.15 neu eingeführten echten Routen-Tests (`_router_test_client`/`_threaded_db_session`) waren nur lokal in einer Testdatei definiert -- jetzt als gemeinsame `pytest`-Fixtures in `tests/conftest.py`, bevor ein drittes Duplikat entstehen konnte.

## 1.2.15 – Saisonale Wartungsfenster und Positionen je Dachfläche

`MaintenanceContract` kannte bisher nur einen einzigen Fälligkeitstermin für den ganzen Vertrag. Ein Wartungsvertrag betrifft in der Praxis aber oft mehrere unabhängig zu wartende Dachflächen (`RoofArea`, seit 1.2.14), und die Wartung selbst ist saisonal, nicht kalendergenau ("Herbstreinigung der Rinnen", "Frühjahrs-Sichtkontrolle Flachdach"). Zwei neue Tabellen: `MaintenanceWindow` (admin-verwaltete saisonale Fenster wie "Frühjahr"/"Herbst", definiert über Start-/Endmonat statt Kalendertage, seedet sich per Migration mit diesen beiden Standardfenstern) und `MaintenanceContractItem` (eine Position je Dachfläche innerhalb eines Vertrags, gekoppelt an genau ein Fenster, mit eigenem Mustervorgang-Rückfall und eigener Dauer). Hat ein Vertrag mindestens eine aktive Position, übernimmt die Positionsebene die Fälligkeitssteuerung vollständig -- Fälligkeit, Erinnerungs-Aufgabe und "Vorgang erstellen" laufen dann ausschließlich über die Positionen, nicht mehr über `MaintenanceContract.next_due_date`; ein Vertrag ohne Positionen verhält sich unverändert wie bisher. Positionen kennen neben "fällig" (`is_due`, innerhalb der Vorlaufzeit) zusätzlich "überfällig" (`is_overdue`, das Fenster ist bereits vollständig verstrichen), damit eine seit Monaten verpasste Herbstwartung auf der Seite nicht wie eine harmlos anstehende aussieht.

Zusätzlich bekommt `ServiceReport` einen Bezug zum Wartungsvertrag/zur Position (`maintenance_contract_id`/`maintenance_contract_item_id`), ohne `Order` anzufassen (unveränderlicher LV-Snapshot): `create_project_from_contract()` markiert das neu erzeugte Projekt über `ProjectProfile` (bereits bestehender Mechanismus für "Projektstammdaten ohne ALTER TABLE"), `create_report()` übernimmt diese Markierung beim Anlegen eines Berichts als einmaligen Schnappschuss. Ein "Vorgang kopieren"/"Als Mustervorgang speichern" schleppt diese Herkunft bewusst nicht mit. Neue Übersicht "Fällige Wartungen im Fenster" auf `/maintenance-contracts`, gruppiert nach PLZ/Ort für die Tourenplanung, sowie eine Vertragshistorie (bereits unterschriebene Berichte) je Vertrag.

Löschen bleibt beim etablierten Blockieren-statt-Kaskadieren-Muster: ein Wartungsvertrag oder eine Position mit bereits unterschriebenem Einsatzbericht lässt sich nicht mehr löschen, nur archivieren (exakt wie `delete_project()` bei bestehenden Aufträgen) -- Entwürfe blockieren dagegen nicht. Ebenso blockiert das Löschen eines noch verwendeten Wartungsfensters und (rückwirkend auf 1.2.14) einer Dachfläche, die noch als Position verwendet wird, da SQLite in diesem Projekt Fremdschlüssel nicht selbst erzwingt. Bei der Umsetzung fiel zudem eine echte Lücke in der bisherigen Router-Testabdeckung auf: bislang testete kein einziger der 687 Tests die tatsächliche FastAPI-Routenauflösung (nur die Business-Funktionen direkt) -- ein `/reorder`-Pfad nach einem gleich langen `/{id}`-Platzhalter derselben Methode wäre damit unbemerkt geblieben. Neu deshalb echte, über einen `TestClient` laufende Routen-Tests (neue Testabhängigkeit `httpx`) für genau diesen Fall.

## 1.2.14 – Dachflächen und Bauteile unter Objekten

Ein Dachdeckerbetrieb wartet nicht "ein Objekt", sondern einzelne Dachflächen, die aus einzelnen Bauteilen bestehen -- erst auf Bauteil-Ebene wird eine Historie brauchbar ("Gully Nordost, dritte Verstopfung in zwei Jahren" statt "Dach hat Probleme"). Zwei neue Tabellen `RoofArea`/`RoofComponent` unterhalb des bestehenden `Property`-Modells (unverändert in seinen bisherigen Spalten). Die bestehende Objekte-Verwaltung in der Kundenakte zeigt je Objekt jetzt eine Dachflächen-Liste (Name, Fläche, Eindeckung, Gewährleistung) mit Schnellanlage; jede Dachfläche bekommt eine eigene neue Seite (`/roof-areas/{id}`) mit vollem Formular, Skizzenbild-Upload und Bauteilliste. Bauteile lassen sich per Klick direkt auf der hochgeladenen Skizze positionieren (Pointer-Events wie beim Unterschriften-Canvas der Einsatzberichte, funktioniert also auch auf dem Tablet). `Dachtyp`/`Eindeckung`/`Bauteiltyp` sind bewusst freie, über die bestehende Optionsgruppen-Verwaltung pflegbare Auswahllisten statt eigener Stammdatentabellen, `Einheit` nutzt die schon vorhandene Gruppe `units`.

Bewusst keine `is_module_enabled("wartungen")`-Prüfung: `Property` ist Kern-Stammdatum ohne Modul-Zugehörigkeit, Dachflächen daran zu koppeln würde bei deaktiviertem Modul Stammdaten verstecken. Archivieren (gleiches Muster wie bei Wartungsverträgen/Aufgaben) ist der Standardweg zum Ausblenden, echtes Löschen bleibt zusätzlich erlaubt, da es sich um Planungs-Stammdaten und kein GoBD-Dokument handelt. Da `Property` selbst nirgends im Code gelöscht wird, aber die neue `Property.roof_areas`-Relationship trotzdem `cascade="all, delete-orphan"` trägt (anders als das bestehende `Property.projects`), räumt ein SQLAlchemy-`before_delete`-Event auf `RoofArea` zusätzlich die Skizzendatei von der Festplatte ab -- und zwar unabhängig davon, ob eine Dachfläche direkt oder über eine (heute noch hypothetische) künftige Objekt-Löschung kaskadiert entfernt wird.

## 1.2.13 – Bestandsaufnahme gegen den echten Code, CLAUDE.md korrigiert

Reiner Dokumentations-Durchgang, kein Produktivcode und kein Schema geändert: CLAUDE.md weist selbst darauf hin, dass Teile davon aus dem Gedächtnis einer früheren claude.ai-Sitzung stammen und gegen den echten Code geprüft werden sollten -- genau das wurde vor der nächsten Erweiterung des Wartungsmoduls nachgeholt. Neuer Bericht `docs/bestandsaufnahme.md` (plus Anlage `docs/bestandsaufnahme_modelle.md` mit allen 104 Modellen) dokumentiert schwarz auf weiß: die tatsächliche Alembic-Kette (34 Migrationen), das komplette Modell-Inventar, das Objekt-/Gebäudemodell (`Property`, nur drei FK-Referenzen im ganzen Projekt), `MaintenanceContract` und `ServiceReport` vollständig inkl. aller Funktionen, `TimeEntry`, das Planungsmodul, `OPTIONAL_MODULES`, alle Datei-Upload-Pfade unter `data/` und die Mobile-Tauglichkeit der Oberfläche.

Dabei einen echten Fehler in CLAUDE.md gefunden und korrigiert: die Datei behauptete, `bb175f455b64` sei die älteste Alembic-Migration -- tatsächlich gibt es acht weitere Migrationen davor, angeführt von der Baseline `2befd7907eef`. Außerdem bestätigt: die in CLAUDE.md dokumentierte Aussage, `Order`/`Invoice` hätten nur `property_name`/`property_address` als Textschnappschuss statt einer echten `property_id`, war bereits korrekt. Die Datei `Roadmap_Zurueckgestellte_Vorhaben.md` existiert nachweislich nicht im Projektverzeichnis.

## 1.2.12 – Schnellauftrag für Reparatur/Wartung, Wartungsvertrag aus einem Projekt erzeugen

Reparaturen und einmalige (noch nicht vertraglich wiederkehrende) Wartungen hatten bisher keinen sichtbaren Platz im Modul "Wartungen & Reparaturen" -- sie liefen technisch über einen ganz normalen Auftrag, der aber erst über den vollen Weg Projekt → Angebot mit Positionen → Beauftragung entsteht. Neuer Bereich "Reparatur/Wartung erfassen" auf der (jetzt "Wartungen & Reparaturen" betitelten) Seite `/maintenance-contracts`: ein kompaktes Formular (Kunde, optional Objekt, Art Reparatur/Wartung, Bezeichnung, optional Zuständig/Ausführungsdatum) legt im Hintergrund in einem Schritt Projekt, Angebot (mit einer Platzhalter-Position "Reparatur/Wartung nach Aufwand" à 0,00 €) und dessen Beauftragung an und leitet direkt zum neuen Auftrag weiter. Die eigentliche Abrechnung läuft danach wie gewohnt über "Rechnung aus Zeitbuchungen" auf Basis der tatsächlich gebuchten Stunden.

Als Rückweg: ein neuer Button "Wartungsvertrag erstellen" auf der Projektseite (neben "Als Mustervorgang speichern") erzeugt aus einem bestehenden Projekt -- auch einem so per Schnellauftrag angelegten -- einen neuen Mustervorgang samt passendem Wartungsvertrag (Intervall und nächste Fälligkeit werden dabei abgefragt, da sich das aus einem einmaligen Auftrag nicht automatisch ableiten lässt). Damit lässt sich aus einer einfachen, einmaligen Wartung bei Bedarf jederzeit ein wiederkehrender Vertrag machen, ohne bei null anzufangen.

## 1.2.11 – Archivieren für Wartungsverträge und Aufgaben

Ergänzt "Löschen" (1.2.8) um eine mildere, jederzeit umkehrbare Alternative -- gleiches Muster wie das etablierte `Project.archived` (seit 1.0.94): ein archivierter Wartungsvertrag bzw. eine archivierte Aufgabe verschwindet aus der normalen Ansicht, bleibt aber über "Archivierte anzeigen" abrufbar und lässt sich jederzeit wieder einblenden. Für Wartungsverträge (`GET/POST /api/maintenance-contracts/{id}/archive`+`/unarchive`) ist das Archivieren unabhängig vom Status aktiv/pausiert/beendet und stoppt zusätzlich die automatische Fälligkeits-Erinnerung -- sinnvoll für Verträge, die formal noch nicht beendet, aber schon nicht mehr relevant sind (z. B. ein Kunde, der das Objekt verkauft hat). Für Aufgaben (`.../api/tasks/{id}/archive`+`/unarchive`) hilft es, das Kanban-Board von alten, längst abgeschlossenen Aufgaben freizuhalten, ohne sie wie bisher unwiderruflich zu löschen.

## 1.2.10 – Gelöschter Wartungsvertrag hinterlässt keine verwaiste Erinnerungs-Aufgabe mehr

Nach dem Löschen eines Wartungsvertrags blieb die zuvor automatisch erzeugte Erinnerungs-Aufgabe ("Wartung fällig: …") unter Aufgaben stehen -- sie hängt nur locker über `source_module`/`source_url` am Vertrag (bewusst keine Fremdschlüssel-Beziehung, siehe Automatisierungs-Anschlussstelle), SQLAlchemy kaskadiert hier also nichts von allein. `delete_contract()` räumt jetzt vorab genau die zu diesem Vertrag gehörenden Aufgaben mit auf, unabhängig davon, ob sie bereits erledigt oder archiviert sind -- ein toter Link auf einen nicht mehr existierenden Wartungsvertrag wäre ohnehin nutzlos.

## 1.2.9 – Objekt bei Wartungsverträgen optional, Intervall frei eintragbar

Zwei Anpassungen am Anlegen-Formular für Wartungsverträge: das Auswahlfeld hieß bisher "Gebäude", in den Stammdaten (Kundenseite) heißt die gleiche Sache aber "Objekt" -- umbenannt, damit der Begriff konsistent ist. Wichtiger: das Feld war bisher Pflicht, dabei hat nicht jeder Kunde ein zusätzliches Objekt über seine eigene Hauptadresse hinaus -- ein Wartungsvertrag für die Kundenadresse selbst ließ sich bisher gar nicht anlegen. Jetzt optional (Standardauswahl "— Hauptadresse verwenden —"); ist kein Objekt ausgewählt, gilt die in den Kundenstammdaten hinterlegte Hauptadresse als Einsatzort und wird in der Liste entsprechend angezeigt ("Hauptadresse" samt Adresse). Die Objekt-Zuordnung lässt sich nachträglich beim Bearbeiten setzen oder wieder entfernen (vorher war sie über die Bearbeiten-Maske ohnehin nicht änderbar). Zusätzlich bekommt das Intervall-Feld eine Auswahlhilfe für 1 bis 24 Monate (`<datalist>`), bleibt aber ein normales Zahlenfeld -- jeder andere Wert lässt sich weiterhin frei eintragen.

## 1.2.8 – Wartungsverträge löschen

Bisher ließ sich ein Wartungsvertrag nur bearbeiten oder über Status-Buttons pausieren/reaktivieren/beenden, nicht aber vollständig entfernen -- etwa wenn er versehentlich mit falschen Stammdaten angelegt wurde oder sein hinterlegter Mustervorgang (wie im Fall von "DachCheck Plus" bei 1.2.7) inzwischen gelöscht wurde und der Vertrag dadurch ohnehin nicht mehr sinnvoll nutzbar ist. Neuer "Löschen"-Button (mit Sicherheitsabfrage) auf der Wartungen-Seite, dahinter ein neues `DELETE /api/maintenance-contracts/{id}`. Anders als bei Rechnungen/Aufträgen/Mahnungen ist ein Wartungsvertrag kein GoBD-pflichtiges Dokument, sondern reine Planungsinformation -- echtes Löschen ist daher unabhängig vom Status jederzeit erlaubt, und da keine andere Tabelle eine Fremdschlüsselspalte darauf trägt, bleiben auch keine verwaisten Zeilen zurück.

## 1.2.7 – "Vorgang erstellen" bei Wartungsverträgen führt jetzt direkt zum neuen Vorgang

Behebt eine zweite Verwirrung nach dem ersten echten Einsatz des Moduls: nach Klick auf "Vorgang erstellen" bei einem fälligen Wartungsvertrag erschien nur eine kurze, leicht zu übersehende Statuszeile mit der neuen Vorgangsnummer -- keine Verlinkung, kein automatischer Wechsel zur neuen Seite. Da der neue Vorgang zudem den Namen des hinterlegten Mustervorgangs trägt (nicht den Namen des Wartungsvertrags), war er in der normalen Projektliste kaum wiederzufinden. `createProjectNow()` springt jetzt direkt zum neu erstellten Vorgang (`/projects/{id}`), analog zum bereits etablierten Muster bei neu erstellten Rechnungen auf der Auftragsseite.

## 1.2.6 – Einstellungen für Wartungen & Reparaturen: Vorlaufzeit und Standard-Sachbearbeiter

Behebt eine Verwirrung, die direkt nach dem Anlegen eines echten Wartungsvertrags auffiel: ein erst in wenigen Tagen fälliger Vertrag erschien nirgends (nicht im Dashboard-Widget, nicht auf der Wartungen-Seite als "fällig") -- `is_due` prüfte bisher ausschließlich, ob die Fälligkeit bereits eingetreten oder überschritten ist, ohne jede Vorlaufzeit. Neuer Einstellungen-Bereich "Wartungen" (Einstellungen → Wartungen) mit zwei Feldern: **Vorlaufzeit (Tage)** -- ab wie vielen Tagen vor der Fälligkeit ein Vertrag bereits als fällig gilt (wirkt einheitlich im Dashboard-Widget, auf der Wartungen-Seite und für die automatische Erinnerungs-Aufgabe), Standardwert 30 Tage -- und **Standard-Sachbearbeiter** als Rückfall für die Erinnerungs-Aufgabe, falls ein einzelner Vertrag keinen eigenen zuständigen Mitarbeiter hat.

## 1.2.5 – Dashboard-Widget "Fällige Wartungen"

Neuer, optionaler Baustein für die bei Version 1.0.102 gebaute Widget-Registry des Start-Dashboards: zeigt fällige Wartungsverträge direkt neben Aufgaben, Kennzahlen und laufenden Projekten, mit Link zur Wartungsverträge-Seite. Wie bei den anderen Erweiterungen des Moduls "Wartungen & Reparaturen" verschwindet der Baustein automatisch, sobald das Modul deaktiviert ist. Bewusst nicht automatisch in ein bestehendes Dashboard-Layout eingeblendet -- wie jedes andere Widget wird es über "+ Widget hinzufügen" bewusst dazugeholt.

## 1.2.4 – Wartungshistorie pro Gebäude

Auf der Einsatzbericht-Seite erscheint jetzt zusätzlich eine "Frühere Berichte zu diesem Gebäude" -- alle bereits unterschriebenen Berichte aus ANDEREN Aufträgen desselben Gebäudes, damit ein Monteur beim nächsten Einsatz frühere Feststellungen sofort sieht, ohne erst im jeweils alten Auftrag suchen zu müssen. Da `Order` selbst nur einen Text-Schnappschuss der Objektadresse trägt (kein `property_id`), wird das zugehörige Gebäude über `order.project.property_id` aufgelöst -- ohne verknüpftes Gebäude bleibt die neue Karte einfach ausgeblendet, das ist kein Fehlerfall.

## 1.2.3 – Reparatur/Wartung als Tätigkeiten in der Zeiterfassung

Die bereits bestehende, frei editierbare Auswahlliste "Zeiterfassung · Tätigkeiten" (Einstellungen → Auswahllisten) hat jetzt von Anfang an die Werte "Reparatur" und "Wartung" -- Grundlage für spätere Auswertungen, welcher Anteil der gebuchten Zeit auf Wartungen/Reparaturen im Vergleich zum übrigen Baustellenbetrieb entfällt. Reine Daten-Migration (keine Schema-Änderung): da die Liste für eine bereits bestehende Installation nur beim allerersten Anlegen mit Standardwerten befüllt wird, mussten die beiden neuen Werte per Migration nachgetragen werden, nicht nur im Code ergänzt.

## 1.2.2 – Rechnung aus Zeitbuchungen

Drittes und letztes Teilstück des Moduls "Wartungen & Reparaturen" für diese Iteration: ein neuer Rechnungstyp "Rechnung aus Zeitbuchungen" (`invoice_type="aufwand"`) auf der Auftragsseite, sichtbar sobald zu einem Auftrag Zeitbuchungen vorliegen. Die Positionen entstehen automatisch aus den gebuchten Ist-Stunden -- gruppiert nach Mitarbeiter und Tätigkeit, bepreist mit dem globalen Stundenverrechnungssatz -- landen aber wie jede andere Rechnung zunächst als Entwurf: Positionen, Preise und Texte bleiben vor dem Finalisieren vollständig prüf- und änderbar. Genau der Endpunkt, auf den die bei der Berichts-Unterschrift automatisch erzeugte "Rechnung erstellen"-Aufgabe verweist -- damit ist die komplette Kette (Wartungsvertrag → Erinnerung → Vorgang → Zeiterfassung → Einsatzbericht mit Unterschrift → Aufgabe → Rechnung) erstmals durchgängig.

Beim Testen einen bestehenden, subtilen Fallstrick in der gemeinsamen Kalkulationsgrundlagen-Funktion gefunden (nicht neu eingeführt, aber erstmals wirklich getroffen): wird sie aufgerufen, während die Datenbank noch keine gespeicherten Kalkulationsgrundlagen hat *und* die aktuelle Datenbank-Sitzung bereits einen noch nicht gespeicherten Datensatz enthält, kann dieser unter bestimmten Verbindungsbedingungen verloren gehen. Betrifft nur ganz frische Installationen bzw. Testdatenbanken vor der ersten Kalkulationsgrundlagen-Speicherung, nicht den Normalbetrieb -- als Vorsichtsmaßnahme ruft `create_invoice_from_time_entries()` diese Funktion deshalb bewusst als ersten Schritt auf, bevor die neue Rechnung angelegt wird.

## 1.2.1 – Digitale Einsatzberichte mit Unterschrift

Zweites Teilstück des Moduls "Wartungen & Reparaturen": auftragsgebundene Einsatzberichte (Rapportbericht bei Reparaturen, Wartungsbericht bei Wartungen) mit den durchgeführten Arbeiten als Freitext. Der Monteur lässt den Kunden direkt auf seinem Gerät per Finger oder Stift auf einem neuen Unterschriftsfeld (HTML5 Canvas, kein Kunden-Login nötig) unterschreiben -- danach ist der Bericht unveränderlich, genau wie Rechnung/Auftrag/Mahnung nach ihrer Finalisierung. Ein PDF mit Auftragsdaten, den erfassten Zeitbuchungen des Auftrags und der eingebetteten Unterschrift lässt sich ab diesem Zeitpunkt abrufen.

Die Unterschrift löst außerdem automatisch eine "Rechnung erstellen"-Aufgabe für den Sachbearbeiter des Auftrags aus -- der erste echte Aufrufer der beim Aufgabenmanagement gebauten Automatisierungs-Anschlussstelle außerhalb der Wartungsverträge selbst. Neue, beidseitige Verlinkung zwischen Zeiterfassung und Einsatzberichten: aus der Zeiterfassung heraus direkt zum Bericht des gewählten Auftrags, vom Bericht zurück zur Zeiterfassung.

## 1.2.0 – Wartungen & Reparaturen: Wartungsverträge

Erstes Teilstück des neuen Moduls "Wartungen & Reparaturen" (schaltbar wie Aufgabenmanagement, unter Einstellungen → Module): wiederkehrende Wartungsverträge je Kunde/Gebäude mit Intervall (in Monaten) und nächster Fälligkeit. Ist ein Vertrag fällig, entsteht beim Aufruf der neuen Seite „Wartungen" automatisch eine Aufgabe für den zuständigen Mitarbeiter -- bewusst kein Hintergrund-Scheduler (davon gibt es im Projekt bislang keinen), sondern dasselbe On-Demand-Muster wie bei den Mahnungs-Entwürfen. Ein neuer Vorgang aus dem hinterlegten Mustervorgang entsteht weiterhin nur durch einen bewussten Klick ("Vorgang erstellen"), nie automatisch -- das rückt die Fälligkeit dann direkt um das Intervall weiter.

Damit bekommt die bei Version 1.1.0 gebaute Automatisierungs-Anschlussstelle für Aufgaben (`source_module`/`source_label`/`source_url`) ihren ersten echten Aufrufer außerhalb des Aufgabenmanagement-Moduls selbst.

## 1.1.5 – Automatische Bereinigung alter Backups

`backup_windows.ps1` behält nach jedem Lauf nur noch die 3 jüngsten Backup-Ordner unter `C:\DACHKONZEPTE-ERP\Backup`, ältere werden automatisch gelöscht -- bei einem Backup pro abgeschlossenem Update entspricht das den letzten 3 Versionen. Verhindert, dass der Backup-Ordner unbegrenzt wächst, ohne dass dafür jemand händisch aufräumen muss.

## 1.1.4 – Automatisches Backup nach jedem Update

Neues Skript `backup_windows.ps1` kopiert nach jedem abgeschlossenen Update das komplette Projekt -- Code, die SQLite-Datenbank und den `data`-Ordner (Firmenlogo, hochgeladene Projektdateien, Verschlüsselungsschlüssel) -- nach `C:\DACHKONZEPTE-ERP\Backup\v<Version>_<Zeitstempel>`, ein eigener Ordner pro Lauf. Hintergrund: das Projekt liegt bisher in keinem Git-Repository, ein fehlerhaftes Update hätte also ohne eigenes Backup keinen Weg zurück zu einer zuletzt funktionierenden Version gehabt. Ausgenommen sind nur `.venv`, `__pycache__`, `.pytest_cache` (über `requirements.txt` reproduzierbar) und Log-Dateien.

## 1.1.3 – E-Mail-Benachrichtigung bei Aufgaben-Zuweisung

Wird einer Aufgabe ein Mitarbeiter neu zugewiesen oder auf eine andere Person geändert, erhält diese jetzt automatisch eine kurze E-Mail mit Titel, Priorität, Fälligkeit und ggf. Projektbezug -- über dieselbe SMTP/Microsoft-365-Konfiguration wie der übrige E-Mail-Versand. Ein Ein-/Ausschalter dafür ("Mitarbeiter bei Zuweisung per E-Mail benachrichtigen") ist neu unter Einstellungen → Aufgaben, standardmäßig aktiv. Kein Versand, wenn der Mitarbeiter keine E-Mail-Adresse hinterlegt hat oder ein Mailserver-Fehler auftritt -- das Speichern der Aufgabe selbst gelingt in beiden Fällen trotzdem, die Benachrichtigung ist bewusst nur ein Nebeneffekt, kein blockierender Schritt.

## 1.1.2 – Checklisten in Aufgaben

Jede Aufgabe kann jetzt eine eigene Checkliste mit abhakbaren Unterpunkten bekommen, um sie strukturiert abzuarbeiten -- direkt im Bearbeiten-Panel der Aufgabe hinzufügen, umbenennen, abhaken oder löschen. Die Karte auf dem Board zeigt bei vorhandener Checkliste ein Fortschritts-Badge ("3/5"). Verfügbar erst nach dem ersten Speichern einer neuen Aufgabe, da ein Checklisten-Punkt an eine bestehende Aufgabe gehängt wird.

## 1.1.1 – Konfigurierbare Aufgaben-Spalten

Die bisher fest kodierten drei Status Offen/In Arbeit/Erledigt sind jetzt eine vom Administrator frei verwaltbare Spaltenliste (Einstellungen → Aufgaben): umbenennen, neu sortieren, zusätzliche Spalten anlegen (angelehnt an den mehrstufigen Ablauf einer Kundenanfrage) und wieder löschen, sobald keine Aufgabe mehr darin liegt. Jede Spalte trägt ein Häkchen "zählt als erledigt" -- damit hängt das automatische Setzen/Löschen von "erledigt am" nicht mehr am Literal "erledigt", sondern an dieser Markierung, und funktioniert genauso für selbst angelegte Spalten. Bestehende Aufgaben bleiben nach dem Upgrade unverändert den drei ursprünglichen Spalten zugeordnet.

## 1.1.0 – Aufgabenmanagement

Erstes eigenständiges Aufgaben-Modul: freie Aufgaben mit Titel, Beschreibung, Status, Priorität und Fälligkeit, optional einem Mitarbeiter und/oder einem Projekt zugeordnet, auf einer neuen Kanban-Board-Seite unter „Aufgaben" (Offen/In Arbeit/Erledigt). Sichtbarkeit genau wie beim Dashboard etabliert: ein Sachbearbeiter sieht ausschließlich eigene Aufgaben, serverseitig erzwungen, Administratoren können auf einen beliebigen Mitarbeiter oder „alle" umschalten. Die neue „Meine Aufgaben"-Quelle im Dashboard-Widget reiht sich in die bestehende Liste ein.

Aufgaben lassen sich außerdem automatisiert von künftigen Modulen anlegen, ohne dass die Aufgaben-Tabelle dafür geändert werden muss: drei freie Felder (`source_module`, `source_label`, `source_url`) markieren automatisch erzeugte Aufgaben auf der Karte und verlinken zurück zum auslösenden Datensatz, etwa einem später kommenden digitalen Wartungsbericht, der eine Rechnungs-Aufgabe beim zuständigen Sachbearbeiter erzeugt. Aufgabenmanagement ist zugleich das erste Modul, das sich über den neuen Umschalter (siehe 1.0.103) pro Installation abschalten lässt.

## 1.0.103 – Modul-Umschalter

Neue, generelle Infrastruktur, um künftig einzelne ERP-Bausteine pro Installation ein- oder auszuschalten, während die Kernfunktionen (Kunde bis Mahnung, Zeiterfassung, Planung) immer aktiv bleiben. Ein Administrator schaltet Module live in den Einstellungen um, ohne Neustart -- fehlt ein Modul in der neuen Liste, gilt es als aktiv, damit das Einführen eines neuen Moduls nie stillschweigend etwas an einer bestehenden Installation ändert. Für sich allein noch ohne sichtbaren Effekt; Aufgabenmanagement (1.1.0) ist der erste tatsächliche Anwendungsfall.

## 1.0.102 – Dashboard als neue, modulare Startseite

„/" zeigt jetzt ein personalisierbares Dashboard statt des bisherigen Leistungskatalog-Imports (der ist unverändert unter „/leistungskatalog" erreichbar, neuer Eintrag „Leistungskatalog" in der Seitenleiste). Modulares Widget-System: drei Start-Widgets (Meine Aufgaben, Kennzahlen, Laufende Projekte), die sich einzeln aus-/einblenden und per Pfeiltasten umsortieren lassen -- das Layout wird pro Benutzer in einer neuen Tabelle gespeichert. Bewusst als Grundgerüst für kommende Module angelegt (Aufgabenmanagement, Kalender u. a.), die sich später nur als weitere Einträge in die bestehende Widget-Registry eintragen müssen, ohne die Seite selbst umzubauen.

„Meine Aufgaben" bündelt offene Arbeitsvorbereitungs-Aufgaben, überfällige Mahnungen, auslaufende Angebots-Bindefristen und fällige Anfragen-Wiedervorlagen aus mehreren bestehenden Bereichen an einer Stelle. Ein normaler Sachbearbeiter sieht dabei ausschließlich eigene Aufgaben, serverseitig erzwungen genau wie beim bestehenden Abwesenheits-Workflow, nicht nur im Frontend versteckt. Administratoren bekommen zusätzlich eine Auswahl, für welchen Mitarbeiter (oder alle) die Aufgaben angezeigt werden.

## 1.0.101 – Keine Browser-Popups mehr für Dateneingaben

Letzte verbliebene `prompt()`-Aufrufe entfernt: Bezeichnung beim Sichern eines Auftragsstands, eigene Textblöcke und Tabellenfelder im PDF-Layout-Editor, Notiz bei der Abwesenheitsprüfung. Durchgängig ersetzt durch sichtbare, teils vorausgefüllte Eingabefelder direkt auf der Seite statt Popup-Dialogen, wie an anderer Stelle bereits für den E-Mail-Versand gefordert und umgesetzt.

## 1.0.100 – Redesign Gruppe 4: verbleibende Seiten

Letzte acht Seiten auf das neue Design umgestellt, darunter der Leistungskatalog, das Zeiterfassungs-Backoffice, die Arbeitsvorbereitung, Finanzen, Mahnwesen sowie drei schlanke Formularseiten ohne Seitenleiste (neues Projekt/Angebot/Leistung), bei denen die farbige Kopfleiste durch einen schlichten Zurück-Link ersetzt wurde. Damit ist der komplette Seitenbestand auf das im Piloten erarbeitete Design umgestellt.

## 1.0.99 – Redesign Gruppe 3: komplexeste Seiten

Angebots-Editor, Auftrag, Rechnungsdetail, Projektmappe und PDF-Layout-Editor umgestellt -- die funktional aufwendigsten Seiten der Anwendung, u. a. mit Drag-&-Drop-Leistungsverzeichnis und dem visuellen Bausteine-Editor. Beim Angebots-Editor musste die feste Kopfleiste anders als bei den bisherigen Seiten in die bestehende Werkzeugleiste integriert statt ersatzlos entfernt werden, da sie echte Funktionsknöpfe enthielt, keine reine Markenleiste.

## 1.0.98 – Redesign Gruppe 2

Anfragen, Projekte, Planungstafel und Zeiterfassung umgestellt. Bei der Planungstafel u. a. Wochenend-/Feiertags-/Schulferien-Kennzeichnung und Konflikt-Markierungen an das neue Farbsystem angepasst.

## 1.0.97 – Visuelles Redesign: Grundlagen und erste Seiten

Design von Grund auf überarbeitet statt nur aufgefrischt, Pilot auf den Einstellungen: anpassbare Akzentfarbe, durchgängiges Hell-/Dunkel-Theme, eckige statt runde Eingabefelder, einfarbige statt bunte Sidebar-Icons, farbige Kopfleisten entfernt. Anschließend auf Anmeldung, Änderungshistorie, Benutzer, Mitarbeiter, Stammdaten und Kundenakte ausgerollt.

## 1.0.94 – Projekte archivieren und löschen

Rein informatives Aus-/Einblenden eines Projekts, jederzeit umkehrbar, ohne die zugrundeliegenden Daten anzufassen -- gilt für Mustervorgänge wie für normale Projekte gleichermaßen. Echtes, unwiderrufliches Löschen bleibt zusätzlich möglich, aber nur solange noch kein Auftrag aus dem Projekt entstanden ist.

## 1.0.92 – Mustervorgänge (Projektvorlagen)

Ein als Vorlage markiertes Projekt bleibt technisch ein ganz normales Projekt (gleiche Tabelle, gleiche Beziehungen), taucht aber nicht in der normalen Projektliste auf, sondern in einer eigenen Vorlagenübersicht. Ein gemeinsamer Kopiermechanismus steckt hinter „Vorgang kopieren", „als Mustervorgang speichern" und „neuen Vorgang aus Vorlage erstellen" -- kopiert dabei auch das zuletzt erstellte Angebot des Projekts mit.

## 1.0.90 – Auftragsbestätigung per E-Mail

`send_order_email()` analog zu Angebot/Rechnung/Mahnung. Ein Auftrag kennt anders als die anderen drei Dokumenttypen von Anfang an keinen Entwurfsstatus -- er entsteht erst durch die Beauftragung eines Angebots.

## 1.0.87 – Angebot per E-Mail versenden

`send_quote_email()` analog zu Rechnung und Mahnung, auch wenn ein Angebot keinen expliziten „versendet"-artigen Status wie eine Rechnung kennt.

## 1.0.84 – Verständlichere Fehlermeldungen beim Versand über Microsoft 365

Microsofts eigene Graph-API-Fehlermeldungen sind oft wenig aussagekräftig („Access is denied. Check credentials and try again."). Konkrete, umsetzbare Hinweise zu den häufigsten Fehlerfällen ergänzt.

## 1.0.82 – Rechnung per E-Mail versenden, eigene E-Mail-Vorlagen je Dokumenttyp

`send_invoice_email()` analog zur Mahnung. Neue eigenständige Tabelle für Betreff/Text-Vorlagen je Dokumenttyp (Angebot/Auftrag/Rechnung).

## 1.0.79 – Versand über Microsoft 365 (OAuth 2.0)

Erweiterung des seit 1.0.74 bestehenden E-Mail-Versands um Microsoft 365/Graph-API als Alternative zu klassischem SMTP, umschaltbar.

## 1.0.74 – E-Mail-Versand für Mahnungen (Grundlage)

Erste Version des allgemeinen E-Mail-Versands, zunächst für Mahnungen: Verschlüsselung sensibler Zugangsdaten, gemeinsame Platzhalter für PDF-Text und E-Mail-Betreff/-Text, eigener Versand-Nachweis (E-Mail-Adresse und Zeitpunkt) getrennt vom eigentlichen Rechnungs-/Mahnungsstatus.

## 1.0.71 – Automatisch Mahnungsentwürfe anlegen

Sobald eine Rechnung überfällig und die nächste Mahnstufe fällig ist, wird automatisch ein Mahnungsentwurf angelegt (ein- und ausschaltbar) -- der eigentliche Versand bleibt bewusst immer ein manueller Schritt.

## 1.0.70 – Mahnwesen-Übersicht

Neues Feld an der Rechnung für einen bereits vorhandenen, noch nicht versendeten Mahnungsentwurf, dazu eine systemweite Mahnungshistorie unabhängig von einer einzelnen Rechnung.

## 1.0.69 – Konfigurierbare Randabstände

Feste, bisher hart codierte Randabstände je Seitentyp (Seite 1 / Folgeseiten) jetzt einstellbar statt fest im Code verankert.

## 1.0.68 – Lehre aus einer fehlgeschlagenen Migration

Eine neue NOT-NULL-Spalte auf einer bereits gefüllten Tabelle ohne `server_default` ließ die Migration fehlschlagen. Seither feste Regel: jede neue NOT-NULL-Spalte auf einer bestehenden Tabelle bekommt zwingend einen `server_default`.

## 1.0.67 – Mehrseitige Angebote im Layout-Editor

Seitenumbruch bei langen Positionslisten im positionsbasierten Layout-Renderer: schlichte Fortsetzungs-Kopfzeile auf Folgeseiten (nur Angebotsnummer, „Fortsetzung", Seitenzahl statt wiederholter Bausteine), Hintergrund optional auf jeder Seite wiederholbar.

## 1.0.66 – Briefbogen-Druck und schlichte Bausteine

Option, den digitalen Hintergrund/Briefkopf zu unterdrücken, für Betriebe, die auf vorgedrucktem Briefpapier drucken. Zusätzlich Bausteine, die als schlichte Zeilenliste ohne eigene Beschriftung gerendert werden, u. a. konfigurierbare Firmenkopf-Felder.

## 1.0.65 – Projektmappe: Kennzahlen in drei Gruppen

Die Kennzahlen-Sektion der Projektmappe in drei natürliche, gleich große Gruppen aufgeteilt (Finanzen, Stunden, Dokumente) statt einer unstrukturierten Liste.

## 1.0.64 – Konfigurierbare Tabellen-Inhalte im Layout-Editor

Neue eigenständige Tabelle steuert, welche einzelnen Felder/Spalten innerhalb eines Tabellen-Bausteins erscheinen -- ergänzt die bereits bestehende Positions-/Größensteuerung des gesamten Bausteins.

## 1.0.61 – Kundenadresse und Briefbogen-Hintergrund als eigene Bausteine

Kundenadresse als eigenständiger, unabhängig positionierbarer Baustein statt Teil der Meta-Tabelle. Neue Hintergrundbild-Ablage für den Layout-Editor, je Dokumenttyp getrennt.

## 1.0.59 – Positionsbasierter PDF-Renderer für Angebote

Der neue, visuelle Layout-Editor bekommt einen eigenen PDF-Renderer parallel zum bisherigen, fließenden. Gemeinsame Bausteine (Positionsliste, Summenblock) aus dem bestehenden Renderer herausgelöst, damit beide sie nutzen können. Bewusst ein separater Vorschau-Endpunkt statt Ersatz des bisherigen PDF-Wegs, solange der visuelle Editor noch nicht der einzige Weg ist.

## 1.0.58 – PDF-Layout-Editor (Grundlage)

Firmenlogo-Ablage als Basis, dazu die Geschäftslogik für den neuen visuellen PDF-Layout-Editor: frei positionierbare Bausteine auf der Angebotsseite.

## 1.0.57 – Änderungshistorie aus der Hauptnavigation entfernt

Der Link zur Änderungshistorie/zum Changelog sitzt seither bewusst nicht mehr in der Hauptnavigation, sondern unter Einstellungen, neben der Änderungshistorie.

## 1.0.56 – Fünf Testfehler aus dem ersten echten pytest-Lauf seit 1.0.44 behoben

Wichtigster Fund: `Form(None)` wird von FastAPI nur bei echten HTTP-Anfragen aufgelöst -- ruft ein Test eine Datei-Upload-Funktion direkt auf und lässt einen optionalen Parameter weg, landet das `Form`-Objekt selbst im Code statt `None`. Betraf die Upload-Funktionen für Projekt- und Kundendokumente, jetzt mit expliziter Typprüfung behoben und gegen alle vier Fälle (Form-Objekt, `None`, echter Text, nur Leerzeichen) von Hand durchgerechnet. Die übrigen beiden Fehler lagen in eigenen Tests (doppelte Datenbank-ID, ein unter Windows fehlschlagender Pfad-Vergleich), nicht in der Anwendung selbst.

## 1.0.55 – Beide lokal erzeugten Migrationen fest ins Paket übernommen

Reines Nachliefer-Paket ohne Anwendungscode-Änderung: die von Hand über `alembic revision --autogenerate` erzeugten Migrationen für Mahnwesen und Dokumentenmanagement liegen jetzt fest im Projekt, gegen die Modelle geprüft. Ab dieser Version reicht `alembic upgrade head` allein, ohne vorheriges `revision --autogenerate`.

## 1.0.54 – Dokumentenmanagement

Fünfter Roadmap-Punkt: feste Kategorien mit frei anlegbaren Unterordnern darin, von Anfang an für Kunden- und Projektmappe, beide teilen sich dieselbe Kategorien-Liste. Der bestehende Datei-Upload im Projekt ist bewusst die Grundlage geblieben statt einer zweiten, parallelen Lösung. Dabei einen eigenen, potenziell ernsten Fehler vor dem Ausliefern selbst gefunden: ein neues Unterordner-Feld mitten in einer bestehenden Funktionssignatur hätte zwei bestehende Tests durch verrutschte, positional übergebene Parameter stillschweigend kaputt gemacht -- beim systematischen Suchen nach allen Aufrufstellen aufgefallen und korrigiert.

## 1.0.53 – Mahnwesen

Vierter Roadmap-Punkt: bis zu drei konfigurierbare Mahnstufen (einzeln aktivierbar, falls nicht alle genutzt werden sollen), mit Mahngebühren, als eigenes PDF-Dokument analog zur Rechnung, dafür dieselben gemeinsamen Bausteine wie Angebot/Auftrag/Rechnung wiederverwendet. Neue Übersicht "benötigt Aufmerksamkeit" in Finanzen für überfällige Rechnungen samt aktueller Mahnstufe. Größte neue Funktion seit dem ursprünglichen Rechnungswesen.

## 1.0.52 – In-App Changelog eingeführt

Dritter Roadmap-Punkt: dieses Changelog selbst, aufrufbar direkt im ERP. Rückwirkend bis 1.0.6 rekonstruiert (aus den vollständigen README-Inhalten der bisherigen Sitzungs-Transkripte extrahiert und jeweils knapp zusammengefasst), ab hier laufend mit jeder neuen Version fortgeschrieben.

## 1.0.51 – Haupt-Navigation bleibt beim Scrollen stehen

Die App-weite Sidebar (Anfragen, Projekte, Finanzen, ...) scrollte auf Desktop-Breiten bisher mit der Seite mit, statt stehen zu bleiben – besonders auf der seit 1.0.48 langen, konsolidierten Projektmappe aufgefallen. Jetzt mit `position:sticky` fixiert, wirkt automatisch auf jeder Seite.

## 1.0.50 – Module in der Projektmappe einklappbar

Jedes der neun Module (Kennzahlen, Projektinformationen, Dateien, Angebote, Aufträge, Rechnungen, Arbeitsvorbereitung, Zeiten, Änderungshistorie) lässt sich einzeln ein-/ausklappen. Der Zustand wird im Browser gemerkt (localStorage) und bleibt beim nächsten Besuch erhalten.

## 1.0.49 – Soll/Ist-Stundenvergleich in den Projekt-Kennzahlen

Aus der einzelnen "Produktive Ist-Stunden"-Kachel wurde ein Dreier-Vergleich: Soll-Stunden (Summe über alle Aufträge, dieselbe Berechnung wie in der Arbeitsvorbereitung), Ist-Stunden, Abweichung mit Vorzeichen.

## 1.0.48 – Projektmappen-Übersicht als zentrales Cockpit

Größter Umbau der Projektmappe seit ihrer Einführung: keine einzeln umschaltbaren Reiter mehr, alle Bereiche stehen gleichzeitig auf einer durchgehenden Seite (Seitenleiste dient jetzt als Sprungmarken-Liste). Neue Kennzahlen-Sektion ganz oben: Projektwert (Netto/Brutto), Abgerechnet/Offen, Zeiterfassungsstand, Anzahl Angebote/Aufträge/Rechnungen.

## 1.0.47 – Rechnungsentwürfe löschbar

Nur Rechnungen im Entwurf (noch keine Rechnungsnummer vergeben, daher keine Lücke in der Nummernfolge) lassen sich jetzt unwiderruflich löschen – sowohl auf der Rechnungsseite selbst als auch direkt aus der Rechnungsliste im Auftrag.

## 1.0.46 – Fix: Steuerschlüssel-Reiter in den Einstellungen ließ sich nicht öffnen

Die interne Whitelist gültiger Einstellungs-Abschnitte (`SETTINGS_SECTIONS`) wurde beim Anlegen der Steuerschlüssel-Sektion in 1.0.44 nicht aktualisiert – ein Klick sprang deshalb still zurück zu "Unternehmensstammdaten". Regressionstest ergänzt, der diese Fehlerklasse künftig automatisch fängt; dabei auffällig geworden, dass der bestehende Sidebar-Test schon länger unvollständig war.

## 1.0.45 – Vier Testfunde aus dem ersten vollständigen 1.0.44-Testlauf behoben

Alle vier lagen in eigenen Testdateien, keiner in der Anwendungslogik selbst: eine veraltete Test-Erwartung ("Rechnungen" in /projects, das war in 1.0.42 bewusst entfernt worden), sowie ein wiederkehrender Fehler in einer Test-Hilfsfunktion (erfundene Projekt-ID ohne tatsächlich angelegtes Projekt) an vier Stellen, plus eine Property ohne Setter, versehentlich im Test direkt gesetzt.

## 1.0.44 – Steuerschlüssel mit echter Berechnungsauswirkung & einheitliche Dokumentstruktur

Größter fachlicher Umbau bisher. Steuerschlüssel (Privat, Gewerbe, §13b Bauleistungen, Solar) steuern nicht nur einen Hinweistext, sondern auch tatsächlich den verwendeten MwSt.-Satz (§13b/Solar setzen ihn auf 0 %), ohne die bestehende Berechnungslogik selbst anzufassen. Alle drei Dokumenttypen (Angebot, Auftrag, Rechnung) folgen jetzt demselben Aufbau: Firmenkopf, Kundenadresse + Meta-Tabelle nebeneinander, Objektanschrift als eigener Absatz (vorher in der Meta-Tabelle versteckt), Titel, Vortext, Positionen, Summen, Zahlungsbedingungen (mit automatischem Fälligkeitssatz nur bei Rechnungen), Steuerhinweis, zwei unabhängige Schlusstext-Blöcke. Dafür ein neues, gemeinsames PDF-Modul geschaffen – Grundlage für einen künftigen Layoutdesigner.

## 1.0.43 – Zahlungsbedingungs-Übernahme repariert, Abrechnungs-Übersicht im Auftrag

Die im Auftrag hinterlegte Zahlungsbedingung wurde nicht in neue Rechnungen übernommen – Ursache war ein Anzeigefehler auf der Rechnungsseite (Dropdown zeigte bei fehlendem exaktem Treffer einfach die erste Option) plus ein zu strenger Text-Abgleich, jetzt robuster gegen Groß-/Kleinschreibung und Leerzeichen. Neu: Abrechnungs-Übersicht im Auftrag (Auftragswert, abgerechnet, offen – Netto und Brutto), mit korrekter Behandlung von Stornorechnungen (heben sich exakt auf, zählen nicht fälschlich negativ).

## 1.0.42 – "Rechnungen" aus /projects entfernt, eigene Textvorlage für Zahlungsbedingungen

Der Menüpunkt "Rechnungen" in der allgemeinen Projektübersicht war ein ungenutzter Platzhalter von vor dem eigentlichen Rechnungsmodul – entfernt. Neu: eigener, frei formulierbarer Text je Zahlungsbedingung mit Platzhaltern ({faelligkeitsdatum}, {skontodatum}, {skontoprozent}, {skontobetrag}), die beim Erstellen der Rechnung automatisch durch echte Werte ersetzt werden.

## 1.0.41 – Skonto bei Zahlungsbedingungen

Neue, optionale Felder Skonto-Prozent und Skonto-Frist je Zahlungsbedingung, mit Validierung (beide zusammen oder keins, Frist nicht länger als Zahlungsfrist). Jede Rechnung zeigt jetzt automatisch einen Satz mit den tatsächlichen Daten ("Zahlbar bis zum ... Bei Zahlung bis zum ... X % Skonto, das entspricht Y €") statt nur der abstrakten Bezeichnung. Wird bei Rechnungserstellung eingefroren – eine spätere Änderung der Zahlungsbedingung wirkt sich nicht rückwirkend auf bereits erstellte Rechnungen aus.

## 1.0.40 – Rechnungen als eigener Reiter in der Projektmappe

Statt nur als Spalte in der Auftragstabelle jetzt ein vollwertiger, eigener Reiter in der Projektmappe (bündelt über alle Aufträge des Projekts). Neue Gruppe "Finanzen" in den Einstellungen fasst Nummernkreise und Zahlungsbedingungen zusammen.

## 1.0.39 – Zahlungsbedingungen vereinheitlicht

Angebot, Auftrag und Rechnung nutzten bisher zwei getrennte Zahlungsbedingungs-Systeme nebeneinander – jetzt eine einzige, gemeinsame Verwaltung. Die im Auftrag hinterlegte Zahlungsbedingung fließt automatisch in neue Rechnungen (Bezeichnung 1:1, Fälligkeitstage über eine passende Zahlungsbedingung ermittelt). Neuer Menüpunkt "Finanzen" mit einer Übersicht aller Rechnungen im System.

## 1.0.38 – Zahlungsbedingungen bearbeitbar

Bestehende Zahlungsbedingungen ließen sich bisher nur neu anlegen und archivieren, jetzt auch nachträglich bearbeiten. Zusätzlich eine Roadmap-Datei für bewusst zurückgestellte Vorhaben angelegt (Dokumentenmanagement, PDF-Layoutdesigner, Mahnwesen, die zwei parallelen Zahlungsbedingungs-Systeme).

## 1.0.37 – Feedback aus dem Rechnungswesen-Start umgesetzt

Fehler beim Laden der Rechnungsliste wurden bisher still verschluckt statt angezeigt – behoben, dabei auch Rechnungen in der Projektmappe sichtbar gemacht. "Versenden" in "Rechnung finalisieren" umbenannt (kein tatsächlicher Versand, nur Nummernvergabe + Sperre). Automatische Nummerierung der Abschlagsrechnungen direkt beim Anlegen sichtbar. Neu: Zahlungsbedingungen mit Tagen und automatischer Fälligkeitsberechnung, Einleitungs-/Schlusstext-Vorlagen für Rechnungen. PDF-Layoutdesigner bewusst noch nicht begonnen, erst gemeinsam umreißen.

## 1.0.36 – Rechnungswesen Teil 2: API, Oberfläche, PDF

Baut auf der in 1.0.33 abgesicherten Kernlogik auf, jetzt vollständig nutzbar. Neue Rechnungen-Karte im Auftrag (Pauschal, nach Leistungsstand oder Schlussrechnung anlegen), eigene Rechnungsseite mit editierbaren Kopfdaten, Ist-Werten direkt in der Tabelle, Finalisieren/Bezahlt markieren/Stornieren, PDF-Download.

## 1.0.35 – Dritter Versuch beim Material-Cascade-Fehler

Der Fix aus 1.0.34 hatte den Fehler entgegen der eigenen Einschätzung nicht behoben. Neuer Ansatz: die Material-Änderung wird jetzt vollständig committet, bevor die Verkaufspreis-Neuberechnung beginnt – zwei sauber getrennte Transaktionen statt einer vermischten.

## 1.0.34 – Drei Testfehler behoben, davon ein bisher nie aufgedeckter Bug

17 neue Rechnungswesen-Tests liefen fehlerfrei durch. Ein Test kannte noch die alte Bezeichnung "Kataloge" statt "Leistungskataloge". Wichtigerer Fund: ein echter, bereits seit 1.0.28 im Code stehender Cascade-Delete-Fehler bei Materialzuordnungen zu Leistungen (direkter Session-Zugriff statt über die Relationship) – der allererste erfolgreiche Testdurchlauf dieser beiden Tests deckte ihn erstmals auf.

## 1.0.33 – Rechnungswesen – Datenmodell und Kernlogik (Teil 1 von 2)

Neue Modelle Invoice/InvoiceItem für Abschlags-, Leistungsstand- und Schlussrechnungen sowie Storno. Kernmechanik: kumulierter Ist-Stand je Position, das System zieht automatisch den zuletzt abgerechneten Stand ab. Rechnungsnummer wird erst beim Versenden vergeben. Beim Von-Hand-Durchrechnen ein echter Fehler gefunden und behoben: eine Stornorechnung hätte sich selbst fälschlich als neuen gültigen Ist-Stand ausgegeben. Noch ohne Oberfläche, reine Grundlage.

## 1.0.32 – Vier Korrekturen aus dem Feedback

"Kataloge" zu "Leistungskataloge" umbenannt zur Abgrenzung von "Materialkataloge", Materialien-Übersicht aus der Hauptnavigation entfernt (nur noch über den jeweiligen Materialkatalog erreichbar), Header-Unterzeile im Leistungskatalog entfernt. Sidebar-Versatz im Backoffice behoben – Ursache war eine zu unspezifische CSS-Regel, die auch die Hauptnavigation traf; beim genaueren Hinsehen betraf das vier weitere Stellen, nicht nur die gemeldete.

## 1.0.31 – Kritischer Hotfix: App startete nach 1.0.30 gar nicht mehr

Eine in 1.0.30 verwendete, aber nie tatsächlich geschriebene Funktion (`_materials_table_has_catalog_column`) führte zu einem ImportError beim Start. Behoben, und ein zweites Prüfwerkzeug gebaut, das künftig prüft, ob jeder importierte Name auch wirklich in der Zieldatei definiert ist (nicht nur, ob er als "importiert" auftaucht).

## 1.0.30 – Vollständige Materialkataloge

Eigenständiges Katalog-Konzept für Materialien, spiegelt die Leistungskataloge: automatischer Fertigkatalog, Verschieben, Kopieren, eigene Verwaltungsoberfläche.

## 1.0.29 – Drei Korrekturen aus dem Feedback

Sidebar-Farbfehler auf acht statt der gemeldeten fünf Seiten behoben (inkonsistente CSS-Variablennamen `--g` vs. `--green`). "Zurück"-Button ging bisher zu einer fest verdrahteten Seite statt tatsächlich zurück – auf vier Formularen auf `history.back()` umgestellt. Leistungstyp jetzt über eine Auswahlliste steuerbar statt im Formular fest hinterlegt.

## 1.0.28 – Erweiterte Erfassungs-/Bearbeitungsmaske mit Live-Kalkulation

Ersetzt die reduzierte Erfassungsmaske aus 1.0.23 vollständig: Grunddaten, Arbeitszeit, Material (mit Suche und Zeilensumme), Fremdleistung, Zuschläge – alle Zwischenwerte und der Verkaufspreis aktualisieren sich live beim Tippen. Nur nicht-importierte Leistungen bearbeitbar.

## 1.0.27 – Kritischer Hotfix: 40 Tests durch 1.0.25 kaputt gemacht

Ein `commit()` innerhalb von `ensure_import_catalog()` markierte bei SQLAlchemy alle Objekte der Sitzung als abgelaufen, auch ein schon vorher angelegtes, noch unvollständiges Leistungsobjekt – der spätere Zugriff darauf löste einen verfrühten, fehlerhaften Datenbank-Insert aus. Behoben durch Aufruf-Reihenfolge.

## 1.0.26 – Materialien verwalten, Leistungen kopieren/verschieben

Neue Materialverwaltung unter Stammdaten. Leistungen lassen sich zwischen Katalogen kopieren (unabhängige Kopie) oder verschieben (nur Zuordnung ändert sich). Zwei "verwendet, aber nicht importiert"-Fehler vor dem Ausliefern selbst gefunden und behoben.

## 1.0.25 – Grundlage für den Materialkatalog, zwei Altlasten behoben

Fertigkatalog-Zuordnung für neue Importe repariert (lief bisher nur einmalig beim ersten Start), "Icking" aus der Oberfläche entfernt. Neues Fundament für einen zentralen Materialkatalog: eigene `materials`-Tabelle mit definierter Dedublizierungslogik (gleiche Artikelnummer + gleiche Werte → ein Material, sonst sichtbar gekennzeichnetes Duplikat statt stillem Zusammenführen).

## 1.0.24 – Zwei Lücken in der manuellen Erfassung behoben

Langtext-Feld ergänzt. Wichtigerer Fund: der eingetippte Verkaufspreis wurde bei manuell erfassten Leistungen fälschlich gegen einen aus Zeit × Stundensatz berechneten Wert verglichen, obwohl beide unabhängige Schätzungen sind – zeigte eine irreführende Differenz. Behoben, indem der eingetippte Preis von Anfang an als verbindlich hinterlegt wird.

## 1.0.23 – Leistungen manuell erfassen

Bewusst ohne neue Migration umgesetzt: manuell erfasste Leistungen bekommen einen gemeinsamen, automatisch angelegten synthetischen Import-Batch statt eine Schema-Änderung am Pflichtfeld zu benötigen. Formular mit reduzierten Feldern direkt im jeweiligen Katalog erreichbar.

## 1.0.22 – Fix: Test erwartete noch "Leistungskatalog"

Ein bestehender Test wurde bei der Umbenennung zu "Kataloge" in 1.0.21 nicht mitgezogen. Kein neuer Bug, reine Testpflege.

## 1.0.21 – Katalog-Verwaltung (Liste, Anlegen, Archivieren)

Erste Bedienoberfläche für das seit 1.0.14 bestehende Backend. Zwei echte Fehler vor dem Ausliefern selbst gefunden: eine Hilfsfunktion, die in dieser Datei gar nicht existiert (hätte zum Absturz geführt), und ein fehlender Eintrag in der Liste erlaubter Stammdaten-Typen (hätte zu 404 geführt).

## 1.0.20 – `alembic/env.py`: SQLite-Batch-Modus ergänzt

Vorab entdeckt und behoben, bevor es bei der anstehenden Migration (Unique-Constraint auf einer bestehenden Tabelle) zu Problemen geführt hätte – `render_as_batch=True` fehlte.

## 1.0.19 – Fix: "Einstellungen konnten nicht geladen werden"

Der ursprünglich geplante Fallback hätte am selben Grundproblem gescheitert. Stattdessen jetzt eine klare, protokollierte Fehlermeldung mit Handlungsanweisung statt eines stillen Fehlers, solange die Migration aus 1.0.14 noch nicht angewendet wurde.

## 1.0.18 – Fix: `get_or_create_settings()` verließ sich auf `id=1`

Nach der Änderung in 1.0.17 hätte eine katalogeigene Kalkulationsgrundlage durch reines Autoincrement fälschlich als "die globale" erkannt werden können. Der globale Datensatz wird jetzt korrekt über `catalog_id IS NULL` gefunden statt über seine zufällige ID.

## 1.0.17 – Fix: `CalculationSettings.id` hätte kollidieren können

Ein `default=1`-Muster, das für Einstellungstabellen mit genau einem Datensatz gedacht war, hätte bei mehreren katalogeigenen Kalkulationsgrundlagen zu Konflikten geführt. Beim Schreiben der Tests entdeckt, bevor es echten Code betraf – entfernt.

## 1.0.16 – Fix: Programmstart brach vor der Migration ab

Der automatische Backfill für neue Katalog-Zuordnungen griff beim Start sofort auf eine Spalte zu, die vor der 1.0.14-Migration noch nicht existierte – Absturz schon beim Import von `app.main`. Jetzt wird die Spalten-Existenz vorher geprüft, der Backfill übersprungen statt abzustürzen.

## 1.0.15 – Fix: `CatalogCreate` fehlte

Eine Textersetzung beim Aufräumen in 1.0.14 hatte versehentlich eine ganze Klassendefinition mitgelöscht – syntaktisch weiterhin gültiges Python, aber strukturell falsch, daher von der reinen Syntaxprüfung nicht erkannt. Erst der ImportError beim Start zeigte es.

## 1.0.14 – Kataloge: Datenmodell & Grundgerüst

Backend-Grundlage für mehrere anlegbare Leistungskataloge (noch ohne Bedienoberfläche): neues `Catalog`-Modell, automatischer Fertigkatalog für Importe, eigene Kalkulationsgrundlagen je Katalog mit demselben Fallback-Muster wie die bestehende Leistungs-Kalkulation.

## 1.0.13 – Sidebar-Navigation auf alle Seiten ausgerollt

Baut auf dem Machbarkeitsnachweis aus 1.0.12 auf, jetzt alle 16 Seiten mit Navigation umgebaut. Zwei echte Bugs unterwegs gefunden (ein ungeschützter Element-Zugriff, der die ganze Seite zum Absturz gebracht hätte; ein eigener, nicht geschlossener HTML-Wrapper). Anmeldename + Abmelden jetzt auf jeder Seite verfügbar, nicht nur in der Benutzerverwaltung.

## 1.0.12 – Sidebar-Navigation: Machbarkeitsnachweis auf 2 Seiten

Neue, gemeinsame Navigations-Komponente (`_sidebar.html`): ein-/ausklappbar, rollenbasiert, aktuelle Seite hervorgehoben. Dabei eine Konzept-Lücke entdeckt: die funktionsreiche Mitarbeiterseite war bisher von keiner einzigen Seite aus verlinkt.

## 1.0.11 – Die vier verbliebenen Punkte aus der Sicherheits-/Architekturrunde

Cookie-secure-Flag (per Umgebungsvariable, standardmäßig aus, da die App bisher über HTTP läuft), keine hart codierten Zugangsdaten mehr in docker-compose.yml, unnötigen `--reload`-Prozess aus dem Windows-Start entfernt, gemeinsame pytest-Fixture für neue Tests.

## 1.0.10 – Vier Testfunde aus dem ersten echten pytest-Lauf behoben

Der allererste tatsächliche pytest-Lauf dieser Zusammenarbeit deckte 4 Fehler auf. Wichtigster Fund: ein echter, seit der main.py-Aufteilung in 1.0.7 bestehender fehlerhafter relativer Import, der bei jedem tatsächlichen Aufruf der betroffenen Funktion zum Absturz geführt hätte. Dafür ein Regressionstest ergänzt, der diese Fehlerklasse künftig automatisch fängt.

## 1.0.9 – Berechtigungen vereinheitlicht

Vier verschiedene "nur Administratoren"-Prüfungen zu einer zentralen FastAPI-Dependency zusammengeführt. Dabei zwei stille Regressionen aus früheren Versionen gefunden: 15 Testdateien prüften noch das alte main.py-Format von vor der 1.0.7-Aufteilung, 6 Testdateien hatten die Versionsnummer 1.0.5 fest einprogrammiert.

## 1.0.8 – Login-Schutz gegen Brute-Force & strukturiertes Logging

Login-Sperre nach 5 Fehlversuchen innerhalb von 60 Sekunden. Neuer rotierender Datei-Log (`data/erp.log`) für App-Start, fehlgeschlagene Logins und unbehandelte Fehler mit vollständigem Traceback.

## 1.0.7 – main.py-Aufteilung & Alembic-Grundgerüst

Die zentrale `main.py` (2.835 Zeilen, 196 Endpunkte) in 22 fachlich sortierte Router-Dateien aufgeteilt – reine Verschiebung, byte-identische Funktionskörper. Alembic-Grundgerüst für künftige Datenbankmigrationen eingerichtet.

## 1.0.6 – Zugriffskontrolle auf lesende API-Endpunkte

Bisher war ein Login nur bei schreibenden Anfragen erforderlich – lesende Zugriffe auf Mitarbeiterdaten (inkl. Löhne), Kalkulationsgrundlagen und Kunden-/Projektdaten waren ungeschützt, sobald der Server im Netzwerk erreichbar war. Ab 1.0.6 sind alle lesenden API-Zugriffe ebenfalls login-pflichtig.
