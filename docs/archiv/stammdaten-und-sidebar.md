# Leistungskatalog vs. Stammdaten, Firmenlogo, Umgestaltung der Sidebar

Ausgelagert aus CLAUDE.md am 2026-09-28 im Zuge der Aufteilung in eine schlanke
CLAUDE.md plus themensortiertes Archiv (siehe CLAUDE.md, Abschnitt "Modulübersicht",
und `docs/archiv/regel-abgleich.md` für die vollständige Zuordnung). Der Inhalt ist
wortgetreu (per Skript, zeilenweise) aus der vorherigen CLAUDE.md übernommen, keine
Umformulierung. Versionsangaben ("seit 1.x.y") beziehen sich auf den Stand zum
jeweiligen Zeitpunkt der ursprünglichen Aufzeichnung.

---

## Leistungskatalog vs. Stammdaten (seit 1.3.25, Sidebar-Umbau seit 1.3.26–1.3.28)

**`/leistungskatalog` (`app/templates/index.html`), bisher nirgends in dieser Datei dokumentiert.**
Sidebar-Eintrag "Leistungskatalog" (nicht zu verwechseln mit Stammdaten → "Leistungskataloge",
das nur die `Catalog`-Container selbst verwaltet -- siehe unten). Diese Seite ist die tatsächliche
Leistungsverwaltung: XML-Import ("Leistungen Dach"), globale Kalkulationsvorgaben
(Lohnansatz/Materialaufschlag/Gemeinkosten/Wagnis & Gewinn, `GET/PUT /api/calculation-settings`),
eine durchsuchbare Leistungsliste mit Verschieben/Kopieren zwischen Katalogen
(`moveOrCopyService()`, `POST /api/services/{id}/move|copy`) und ein Kalkulationsdetail je
Leistung (Quelldaten, DACHKONZEPTE-Kalkulation mit Overrides, Materialstückliste). Kennt bereits
`?catalog_id=<id>` zur Vorfilterung auf einen Katalog. `/services/new`/`/services/{id}/edit`
(`service_form.html`) sind die zugehörigen Anlegen-/Bearbeiten-Unterseiten.

**Fehlerbehebung: "Leistungen ansehen" führte auf die Startseite.** `master_data.html`
(Stammdaten → Leistungskataloge) und `service_form.html` (Redirect nach Speichern) verlinkten auf
`/?catalog_id=<id>` -- ein Ziel, das diesen Parameter nirgends auswertet, daher der Rückfall auf
das Dashboard. Ursprünglich als fehlende Seite diagnostiziert (dafür eine neue "Leistungen"-Ansicht
probeweise in `master_data.html` gebaut) -- die tatsächliche Ursache war aber nur ein fehlendes
Pfadsegment: `/leistungskatalog` (siehe oben) leistete bereits alles Nötige, inklusive desselben
`catalog_id`-Parameters. Die probeweise gebaute Ansicht wurde deshalb wieder verworfen, korrigiert
sind stattdessen die drei betroffenen Links (`/leistungskatalog?catalog_id=<id>`).

**Sidebar-Bestandsaufnahme (im selben Zug angefragt, keine Codeänderung, Vorschlag wartet auf
Rückmeldung).** Vollständige Liste aller 17 `_sidebar.html`-Ziele und aller 8
`master_data.html`-Bereiche wurde erstellt (nicht hier wiederholt, siehe Chatverlauf) -- die
wichtigsten Ergebnisse:
- **Keine zwei Sidebar-Einträge zeigen auf dasselbe Ziel.** Jeder der 17 Einträge hat ein eigenes,
  gültiges Ziel; keiner führt ins Leere oder auf eine nach jüngeren Umbauten leere Seite (`/finanzen`,
  `/history`, `/findings` wurden gezielt gegengeprüft -- alle drei vollständig funktionsfähig,
  keine Karteileichen).
- **"Mitarbeiter" ist ein ECHTES Duplikat**, wie vom Nutzer vermutet: Sidebar → `/employees`
  (`employees.html`, ein einzelnes, reichhaltiges Formular+Übersicht-Blatt mit Vergütungsrechner)
  und Stammdaten → "Mitarbeiter" (`master_data_form.html`s `employeeForm()`, separate Anlegen-/
  Bearbeiten-Seite) verwalten dieselben `Employee`-Datensätze über dieselbe API, nur mit
  unterschiedlicher, unterschiedlich reichhaltiger Oberfläche.
- **"Leistungskatalog" ist KEIN Duplikat von Stammdaten → "Leistungskataloge"**, anders als vom
  Nutzer zunächst vermutet (sie tragen nur ähnliche Namen): Stammdaten verwaltet ausschließlich die
  `Catalog`-CONTAINER (Name, Beschreibung, Archivieren) -- für die enthaltenen LEISTUNGEN selbst
  (Suche, Bearbeiten, Kalkulation, XML-Import, globale Kalkulationsvorgaben) gibt es in der
  Stammdatenverwaltung heute **keine** Entsprechung. Würde "Leistungskatalog" ersatzlos aus der
  Sidebar entfernt, wären XML-Import und die globalen Kalkulationsvorgaben ohne jede Ersatzseite
  nicht mehr erreichbar -- diese Lücke müsste zuerst geschlossen werden (naheliegend: eine
  "Leistungen"-Unteransicht analog zum bereits bestehenden "Materialien"-Muster in
  `master_data.html` ergänzen; die globalen Kalkulationsvorgaben passen inhaltlich eher zu
  Einstellungen als zu Stammdaten, da sie Systemkonfiguration und keine Stammdaten-Entität sind).
- **"Vor Ort" fehlt in der Sidebar**, obwohl vom Nutzer als tägliches Werkzeug erwartet -- das ist
  KEIN Versehen, sondern die seit 1.3.0 dokumentierte, bewusste Entscheidung: die Monteursansicht
  hat einen eigenen, reduzierten Einstiegspunkt (`_mobile_header.html` + PWA-Manifest fürs
  Fahrzeug-Tablet), keinen Platz in der vollen Desktop-Sidebar.
- **"Angebote"/"Aufträge"/"Rechnungen" haben keine eigenen Sidebar-Einträge** -- es gibt
  projektweit keine eigenständige Listenseite für Angebote oder Aufträge (`grep` bestätigt: kein
  `/quotes`- oder `/orders`-Listenendpunkt, nur `/quotes/{id}/edit` bzw. `/orders/{id}` für ein
  einzelnes Dokument); beide werden ausschließlich über "Projekte" (`project_folder.html`)
  erreicht. Rechnungen laufen über "Finanzen" (`/finanzen`, vollständige Rechnungsliste). Das
  entspricht dem heutigen Stand, nicht notwendigerweise dem, was der Nutzer mit "täglich: ...
  Angebote, Aufträge, Rechnungen" gemeint hat -- zur Klärung vorgemerkt, nicht selbst entschieden.
- Vorschlag für eine neue Sidebar-Struktur wurde vorgelegt (täglich vorne, Einrichtung hinten,
  "Mitarbeiter" aus der Sidebar zugunsten von Stammdaten entfernt, "Leistungskatalog" bleibt
  vorerst, bis die Lücke in Stammdaten geschlossen ist) -- **noch keine Entscheidung des Nutzers,
  keine Codeänderung**.

### Umsetzung der vier Anmerkungen (seit 1.3.26)

Der Nutzer hat den 1.3.25-Vorschlag mit vier Anmerkungen bestätigt ("Ja, bau das") und zusätzlich,
mitten in der Umsetzung, eine fünfte, ausdrücklich vor jeder Codeänderung zu prüfende Ergänzung
nachgereicht (siehe Anmerkung 2 unten).

**1. Mitarbeiter -> `/employees`.** Stammdaten → "Mitarbeiter" leitet jetzt per
`location.href='/employees'` um, statt eine eigene Inline-Ansicht zu zeigen. Der eigenständige
Sidebar-Eintrag "Mitarbeiter" entfällt (die Duplikat-Feststellung aus 1.3.25 war korrekt: dieselben
`Employee`-Datensätze über dieselbe API, nur unterschiedlich reichhaltig dargestellt).
`master_data_form.html`s `employeeForm()`/`syncFunction()`/`syncCompensation()` sind vollständig
entfernt, `pages.py`s `master_data_create_page`/`master_data_edit_page` akzeptieren `"employees"`
als `data_type` nicht mehr. `/employees` bekommt eine Rückwärtsnavigation ("← Stammdaten",
`history.back()` -- dasselbe Muster wie in `master_data_form.html`/`service_form.html`), da man ab
jetzt ausschließlich über Stammdaten dorthin gelangt, nicht mehr über einen eigenen Sidebar-Link.

**Echter Funktionsverlust gefunden und vor Abschluss behoben**: "die reichhaltigere Oberfläche
gewinnt" traf nur teilweise zu -- `/employees` kannte `show_on_planning_board`
(Plantafel-Sichtbarkeit/Kapazitätsberücksichtigung) bisher gar nicht; das war ausschließlich über
`master_data_form.html`s jetzt entfernte `employeeForm()` steuerbar. Ohne Nachrüsten wäre diese
Steuerung beim Wegfall der schlanken Variante ersatzlos verschwunden. Nachgerüstet: eine Checkbox
in `employees.html`, verdrahtet in `editEmployee()`/`resetForm()`/`saveEmployee()`s Payload (Feld
existiert bereits als `EmployeeUpdate.show_on_planning_board: bool = True`, `app/schemas.py`),
sowie eine neue Spalte "Planung" in der Übersichtstabelle. Die alte, in `syncFunction()` verbaute
Heuristik (automatisches Abwählen bei Funktionsnamen wie "Lager"/"Büro"/"Verwaltung") wurde bewusst
NICHT übernommen -- eine Verfeinerung, kein Kernverhalten, außerhalb des Umfangs dieser Aufräumung.

**2. Kalkulationsvorgaben -- vom vermuteten Umzug zum bestätigten Duplikat.** Der Nutzer reichte
mitten in der Umsetzung nach: die globalen Kalkulationsvorgaben stehen bereits unter Einstellungen
→ "Kalkulationsgrundlagen" -- kein Umzug, sondern mutmaßlich ein Duplikat, und forderte eine Prüfung
VOR jeder Änderung (Sorge: zwei getrennte Datensätze, von denen einer nie in `build_calculation()`
einfließt -- das wäre ein ernster Befund gewesen). Geprüft, bevor irgendetwas geändert wurde:

- Beide Oberflächen rufen exakt denselben Endpunktpaar auf: `GET/PUT /api/calculation-settings`
  (`app/routers/settings.py`), das ausschließlich `get_or_create_settings(db)`
  (`app/calculation.py`) liest/schreibt -- eine einzige, durch `catalog_id IS NULL` bestimmte
  Singleton-Zeile in `calculation_settings`.
- Direkte Abfrage der echten `dachkonzepte_erp.db` bestätigt: genau eine Zeile
  `(id=1, catalog_id=NULL, labor_rate=82.5, material_markup_pct=10, overhead_pct=0,
  risk_profit_pct=0, use_source_time_as_minutes=1)`.
- Beide Oberflächen bilden identisch dieselben fünf Felder ab (`labor_rate`/`material_markup_pct`/
  `overhead_pct`/`risk_profit_pct`/`use_source_time_as_minutes`) -- **keine** zeigt mehr oder
  andere Felder als die andere.
- `build_calculation()` liest ausschließlich über denselben `get_or_create_settings()`/
  `get_settings_for_catalog()`-Pfad -- es gibt keinen zweiten, unbenutzten Datensatz, der jemals
  gepflegt, aber nie für Angebotspreise verwendet würde. Der vom Nutzer befürchtete ernste Fall
  (Divergenz zwischen gepflegtem und tatsächlich wirksamem Wert) tritt nicht ein, weil es nur eine
  einzige Zeile gibt, die von beiden UIs gemeinsam benutzt wird.

Ergebnis: dasselbe, kein Duplikat im Sinne getrennter Datensätze, sondern **dieselbe Einstellung an
zwei Stellen editierbar** -- der genau vom Nutzer benannte Duplikat-Fall, nur mit demselben statt
verschiedenen Daten. Wie vom Nutzer für diesen Fall vorgegeben ("Falls es dasselbe ist, entfällt
die Ansicht im Leistungskatalog"): die Kalkulationsvorgaben-Karte in `/leistungskatalog`
(`app/templates/index.html`, samt `loadSettings()`/`saveSettings()`) ist entfernt, ersetzt durch
einen Verweis-Text mit Link auf `/settings#calculation` -- Einstellungen → Kalkulationsgrundlagen
bleibt die einzige Bearbeitungsoberfläche.

**Weitere Doppelungen im Projekt gesucht (auf Nachfrage), keine gefunden.** Geprüft, welche
Templates tatsächlich `PUT`-Aufrufe (nicht nur `GET`) gegen die bekannten Einstellungs-Endpunkte
absetzen (`calculation-settings`, `maintenance-settings`, `labor-rate-settings`,
`reminder-settings` u. Ä.): schreibend ist in jedem Fall ausschließlich `settings.html` --
`employees.html`/`master_data_form.html` (liest `labor-rate-settings` für die
Stundenlohn-Vorschau), `dashboard.html`/`maintenance_contract.html` (liest `maintenance-settings`
für Fälligkeitsanzeige/Vorbelegung) und `service_form.html` (liest `calculation-settings` für die
Live-Kalkulationsvorschau) sind bestätigt reine Lesezugriffe für Anzeige/Vorbelegung, keine
konkurrierenden Bearbeitungsoberflächen. Die Kalkulationsvorgaben-Karte war der einzige echte Fund.

**Damit schrumpft die verbleibende Lücke aus 1.3.25** auf genau das, was übrig bleibt, wenn
"Leistungskatalog" eines Tages aus der Sidebar entfernt werden soll: eine **Leistungen-Ansicht in
den Stammdaten** (nach dem bereits etablierten "Materialien"-Muster in `master_data.html`) **plus
der XML-Import**. Beide sind bewusst noch NICHT gebaut -- eigener, späterer Schritt, siehe
"Nächster Schritt" unten. Die Kalkulationsvorgaben sind mit dieser Version bereits vollständig aus
der Lücke heraus (nie verlagert, weil sie nie ein zweiter Ort waren -- nur der zweite Zugang
entfällt).

**Nächster Schritt, wie hier vorgemerkt, umgesetzt -- aber anders als ursprünglich skizziert (seit
1.3.27):** vor dem Bauen einer eigenen Leistungen-Ansicht in `master_data.html` erst geprüft, ob
sie überhaupt gebraucht wird. Ergebnis: nein -- `/leistungskatalog` (`app/templates/index.html`)
funktioniert bereits ohne `catalog_id` sinnvoll (XML-Import-Karte und Kalkulationsvorgaben-Verweis
sind ohnehin immer sichtbar, die Leistungsliste lädt ohne Parameter schlicht `/api/services`
ungefiltert -- Suche, Detail/Kalkulation, Verschieben/Kopieren funktionieren katalogübergreifend
identisch). Eine zweite, einfachere Ansicht in den Stammdaten wäre reine Duplikation gewesen.
Stattdessen: die Stammdaten-Katalogliste bekommt einen zusätzlichen Link zum parameterlosen
Einstieg (nach demselben Muster, das "alle Materialien anzeigen" in der Materialkataloge-Ansicht
bereits nutzt), und `/leistungskatalog` bekommt eine Rückwärtsnavigation zu den Stammdaten (Muster
`/employees` aus 1.3.26) -- die Seite ist ab jetzt nur noch von dort aus erreichbar, nicht mehr
über einen eigenen Sidebar-Eintrag. Der Sidebar-Eintrag "Leistungskatalog" entfällt damit, siehe
Abschnitt "Umsetzung der vier Anmerkungen" oben für die Bestätigung, dass "Leistungen ansehen" in
der Katalogliste bereits seit 1.3.25 korrekt verlinkt.

**Randbefund bei der Prüfung gefunden und auf Wunsch im selben Zug behoben:** sowohl die
Leistungsliste (`index.html`) als auch die Materialliste (`master_data.html`) hatten eine mit
"Katalog" beschriftete Tabellenspalte, die tatsächlich die Bearbeiten-/Verschieben-/
Kopieren-Aktionen zeigte, nicht den Herkunftskatalog der Zeile -- beim gezielt gefilterten
Aufruf (`catalog_id` gesetzt) unproblematisch, beim jetzt neu hinzukommenden parameterlosen,
katalogübergreifenden Durchsuchen fehlte dadurch eine sichtbare Zuordnung. `ServiceListOut.
catalog_name` stand bereits seit 1.3.24 bereit (`Service.catalog` per `selectinload`), musste in
`index.html`s `renderServices()` nur noch tatsächlich angezeigt werden. Für die Materialliste
existiert kein serverseitiges `catalog_name` (`MaterialCatalogOut` trägt nur `catalog_id`) --
dafür aber bereits das komplett geladene `materialGroups`-Array, aus dem eine neue, kleine
Hilfsfunktion `materialGroupName(id)` (Muster `customerName(id)`) den Namen client-seitig
auflöst, ohne Backend-Änderung. In beiden Tabellen wurde dafür eine echte, neue "Katalog"-Spalte
ergänzt und die bisher fälschlich so benannte Aktionsspalte in "Verschieben / Kopieren"
umbenannt -- statt nur einer der beiden Spalten, damit die Bedeutung an keiner Stelle mehrdeutig
bleibt.

**3. Sichtbare Gruppenüberschriften.** Neue CSS-Klasse `.app-sidebar-group` in `_sidebar.html`,
optisch nach demselben Muster wie `settings.html`s `.settings-group` (klein, fett, Großbuchstaben,
gedämpfte Farbe), inkl. eingeklappter Variante für die eingeklappte Sidebar. Die beiden Gruppen am
Seitenende heißen "Stammdaten" (Stammdatenverwaltung, Leistungskatalog) und "System" (Einstellungen,
Benutzer, Änderungshistorie).

**4. Backoffice bleibt bei Zeiterfassung.** Backoffice ist fachlich ein Teil der Zeiterfassung
(Abwesenheitsanträge/Korrekturen für den ganzen Betrieb, nicht Systemkonfiguration) und wird
täglich bzw. mehrmals wöchentlich gebraucht, nicht nur bei der Einrichtung -- admin-only ist hier
eine reine Sichtbarkeits-/Berechtigungsfrage, keine Häufigkeits- oder Kategorisierungsfrage (auch
Benutzerverwaltung ist admin-only und trotzdem eindeutig System, weil sie fachlich Einrichtung ist;
Backoffice ist fachlich Tagesgeschäft und bleibt es, unabhängig davon, wer sie sehen darf). Bleibt
deshalb unverändert als eingerückter Unterpunkt direkt unter "Zeiterfassung" im täglichen,
oberen Bereich der Sidebar -- keine Codeänderung an dieser Stelle nötig, nur die Einordnung explizit
bestätigt.

**Bestätigte, bereits vorher entschiedene Abweichungen vom 1.3.25-Vorschlag** (keine Codeänderung):
"Vor Ort" bleibt außerhalb der Desktop-Sidebar; eigene Listenseiten für Angebote/Aufträge/
Rechnungen werden nicht gebaut -- beides bleibt so, bis der laufende Betrieb zeigt, dass es fehlt.

### Benutzer und Änderungshistorie (seit 1.3.28)

Vierter Fall derselben Aufräumreihe (nach Leistungskatalog, Mitarbeitern, Kalkulationsvorgaben).
Vor jeder Änderung geprüft, wie bei den drei vorherigen Fällen:

- **Was zeigt `/users`, was der "Benutzer"-Menüpunkt in den Einstellungen?** `settings.html` hat
  in der System-Gruppe nur einen reinen Navigationslink (`<a href="/users">Benutzer &amp;
  Zugriff</a>`) -- kein eigenes `data-settings-section`, kein `<section>`, kein einziger Aufruf
  von `/api/users`/`/api/auth/status` irgendwo in der Datei. Es gibt also nur **eine** echte
  Oberfläche (`users.html`), keine zwei konkurrierenden Implementierungen wie bei Mitarbeitern
  (`employees.html` vs. das entfernte `employeeForm()`) oder Kalkulationsvorgaben (zwei Formulare
  für dieselbe Zeile). Dieselbe Prüfung für `/history`: identisches Bild, nur ein Link zu
  `history.html`, kein eigener Datenbereich, kein `/api/audit-logs`-Aufruf in `settings.html`.
- **Funktionen, die nur auf einer Seite existieren?** Erübrigt sich -- da es nur je eine echte
  Oberfläche gibt, kann nichts zwischen zwei Varianten auseinanderlaufen. Anders als beim
  1.3.26-Fund bei `show_on_planning_board` gab es hier keine zweite Implementierung, in der ein
  Feld hätte fehlen können.
- **Entscheidung**: "vollständigere Oberfläche gewinnt" löst sich trivial zugunsten der jeweils
  einzigen echten Seite auf -- beide bleiben bestehen, `settings.html` verlinkte bereits vorher
  darauf (die "wird von dort verlinkt"-Bedingung war also schon erfüllt). Übrig blieb nur die
  Navigationsfrage: Sidebar-Direktlinks entfernen (`_sidebar.html`), Rückwärtsnavigation
  "← Einstellungen" auf `users.html`/`history.html` ergänzen (Muster `/employees`/1.3.26,
  `/leistungskatalog`/1.3.27).
- **Nebenbefund 1, echter Bug, unabhängig von der Entscheidung behoben**: `settings.html`
  (Kalkulation → Stundenverrechnungssatz) verlinkte noch auf `/master-data#employees` -- dieser
  Hash-View existiert seit der 1.3.26-Mitarbeiter-Migration nicht mehr in `master_data.html`
  (`viewFromHash()`s erlaubte Liste kennt `'employees'` nicht mehr), der Link fiel seither
  stillschweigend auf die Kunden-Ansicht zurück. Korrigiert auf `/employees`.
- **Nebenbefund 2, bewusst NICHT angefasst**: `/time-backoffice` ist ebenfalls doppelt verlinkt
  (Sidebar, eingerückt unter Zeiterfassung, admin-gated -- UND Einstellungen → System →
  "Zeiterfassungs-Backoffice"). Anders als Benutzer/Historie sitzt Backoffice aber bewusst in der
  TÄGLICHEN Sidebar-Gruppe, nicht unter "System" -- die 1.3.26-Entscheidung ("fachlich
  Tagesgeschäft, admin-only ist nur eine Sichtbarkeitsfrage") bleibt gültig, das Muster
  "in beiden Oberflächen unter System einsortiert" trifft hier nicht zu. Unverändert gelassen.
- **Zugriffsasymmetrie bei `/users`, gemeldet, nicht behoben (kein Teil dieses Auftrags)**: der
  jetzt entfernte Sidebar-Link war admin-gated (`{% if is_admin %}`), der Settings-Link war es
  nie. Das ändert an der tatsächlichen Erreichbarkeit nichts -- weder `/users` selbst noch
  `GET /api/users` sind serverseitig auf Admins beschränkt (nur `PUT`/`POST`(bei bereits
  konfiguriertem System)/`DELETE`), ein Nicht-Admin konnte die volle Benutzerliste also schon
  vorher sehen, die Sidebar hat es ihm nur versteckt. `/history`/`GET /api/audit-logs` waren auf
  beiden Wegen schon immer ungated, keine Asymmetrie dort.
- **Abschließende erneute Vollprüfung der Sidebar gegen die Einstellungen** (vierter Durchgang,
  alle 14 damaligen Sidebar-Ziele gegen alle Einstellungen-Menüpunkte abgeglichen): kein weiterer
  Fund über die beiden oben genannten Nebenbefunde hinaus. Die übrigen `data-settings-section`-
  Menüpunkte (Aufgaben, Wartungen, Plantafel & Kapazität, …) sind reine Konfiguration zu einem
  Sidebar-Modul, nicht dieselben Daten -- kein Duplikat. `/inspection-templates` und `/changelog`
  waren schon vorher nur über die Einstellungen erreichbar.

### Mitarbeiter-Formular list-first (seit 1.3.29)

Gemeldeter Ausreißer, unabhängig von den vier Doppelungen-Fällen oben, aber im selben
Aufräum-Umfeld: `/employees` verhielt sich anders als jeder andere Stammdatenbereich.

- **Ursache**: `employees.html` ist eine der ältesten Seiten des Projekts (schon vor der
  1.3.26-Mitarbeiter-Migration und lange vor dem `master_data.html`/`master_data_form.html`-Muster
  gebaut) -- ein zweispaltiges `.grid`-Layout zeigte Formular UND Liste immer gleichzeitig
  nebeneinander, das Formular immer im Anlegen-Zustand vorbelegt (`<h2 id="formTitle">Mitarbeiter
  anlegen</h2>`). Mit der 1.3.26-Migration wurde diese Seite zum alleinigen Einstieg für
  Mitarbeiter, ohne dass ihr grundlegender Aufbau dabei geprüft wurde -- der Ausreißer bestand
  vorher schon, fiel aber erst jetzt auf, wo die Seite der einzige Weg zu Mitarbeitern ist.
- **Vergleich mit den übrigen Stammdatenbereichen, wie angefragt**: Kunden, Objekte, Teams,
  Fuhrpark & Maschinen, Lieferanten, Leistungskataloge, Materialkataloge/Materialien laufen alle
  über `master_data.html` -- dessen `render()` zeigt für jeden `current`-Typ sofort eine Liste
  (`table(...)`), NIE ein eingebettetes Formular. Anlegen/Bearbeiten passiert ausschließlich auf
  einer eigenen Seite (`master_data_form.html`, bzw. bei Kunden/Objekten deren eigene Detailseiten
  `customer.html`/`property.html`), erreichbar erst über einen bewussten Klick auf "+
  Hinzufügen"/"Bearbeiten"/"Öffnen" -- der SEKTIONS-Einstieg selbst ist überall die Liste. Kein
  weiterer Ausreißer gefunden.
- **Umbau, ohne die Seite auf zwei Routen aufzuteilen**: `employees.html` bleibt EINE Seite (kein
  Umzug des Formulars auf eine zweite URL wie bei den `master_data.html`-Bereichen) -- die
  Mitarbeiterübersicht ist jetzt die einzige beim Laden sichtbare Sektion (steht auch im Markup
  zuerst), das Formular steckt in einem `id="formCard"`-Abschnitt mit `class="hidden"`
  (`.hidden{display:none!important}`, Muster `index.html`/`master_data.html`). Ein neuer Knopf
  "+ Neuer Mitarbeiter" (`openCreateForm()`) im Listenkopf ruft `resetForm();showForm()` auf;
  "Bearbeiten" (`editEmployee()`) endet jetzt auf `showForm()` statt auf dem bisherigen, rohen
  `window.scrollTo({top:0,...})` (das ins Bild scrollte, aber nichts einblenden musste, da das
  Formular vorher ohnehin immer sichtbar war). Der bisherige "Neu / Abbrechen"-Knopf heißt jetzt
  schlicht "Abbrechen" (`cancelForm()`: `resetForm();hideForm()`) -- ein "Neu, aber offen bleiben"
  ergibt im list-first-Modell keinen Sinn mehr. Nach erfolgreichem Speichern (Anlegen ODER
  Bearbeiten) blendet `saveEmployee()` das Formular jetzt ebenfalls aus und kehrt zur Liste zurück
  -- exakt das Muster von `master_data_form.html`, das nach jedem Speichern auf
  `/master-data#<type>` zurückspringt, hier eben ohne Seitenwechsel.
- **Dabei gefunden und mitkorrigiert**: die bisherige "Gespeichert."-Bestätigung stand im
  `#status`-Feld INNERHALB des Formulars -- wird das Formular nach dem Speichern ausgeblendet,
  wäre sie unsichtbar gewesen. Entfernt (kein Ersatz nötig, die aktualisierte Liste ist die
  Bestätigung -- entspricht dem Projektstandard, siehe die stillen Re-Renders nach
  Archivieren/Verschieben/Kopieren in `master_data.html`/`index.html`, dort ebenfalls ohne eigene
  Erfolgsmeldung). Ein zweiter, selbst gefundener Fall derselben Art: eine STARTFEHLER-Meldung
  (`load().catch(...)`) landete vorher ebenfalls im Formular-Status -- das hätte einen echten
  Ladefehler jetzt unsichtbar gemacht, da das Formular beim ersten Laden ja gerade ausgeblendet
  ist. Dafür ein neues, immer sichtbares `<div id="startupError" class="status err hidden">`
  direkt unter der Rückwärtsnavigation ergänzt.
- **Geprüft, dass nichts verlorengeht** (wie verlangt): Vergütungsrechner (`syncCompensation()`,
  `#effectiveWage`/`#wageFormula`), `show_on_planning_board` (1.3.26) und alle übrigen Formularfelder
  (Adresse, Kontaktdaten, Kosten-Zuordnung, Sachbearbeiter-Freigabe usw.) sind unverändert im
  `#formCard`-Abschnitt vorhanden -- nur ihre Sichtbarkeit beim Laden hat sich geändert, keine
  Funktion wurde entfernt. Acht neue Tests (`tests/test_v245_employees_list_first.py`) sichern
  Struktur (Liste vor Formular im Markup, Formular initial `hidden`), Verhalten (Öffnen/Schließen/
  Speichern/Abbrechen) und die vollständige Feldliste einzeln ab.
- **UI-Testabdeckung, ehrlich benannt**: `tests/test_v218_template_rendering.py` bestätigt (als
  Teil der vollen Suite), dass die Seite server-seitig weiterhin fehlerfrei rendert; das
  clientseitige JS wurde durch sorgfältiges manuelles Nachvollziehen geprüft (Klammerbilanz,
  Kontrollfluss), nicht durch einen echten Browser -- in dieser Umgebung stand kein
  Browser-Automatisierungswerkzeug (Playwright o. Ä.) zur Verfügung, `.venv` enthält es nicht als
  Projektabhängigkeit. Kein automatisierter Ersatz für einen echten Klicktest, sollte bei
  Gelegenheit von Tobias einmal im Browser bestätigt werden.
- **Bewusst nur eine Zwischenstation**: diese Etappe behob ausschließlich das gemeldete
  list-first-Symptom, ließ `/employees` aber als eigene Seite mit eigener Formular-Logik bestehen
  -- zwei weitere Abweichungen vom Stammdaten-Muster (fehlende Navigationsleiste, Formular statt
  eigener Seite bei Anlegen/Bearbeiten) blieben zunächst bestehen und wurden erst in 1.3.30
  behoben, siehe dort. `employees.html` (inkl. `tests/test_v245_employees_list_first.py`)
  existiert seit 1.3.30 nicht mehr.

### Mitarbeiter-Formular: ein Bereich statt zwei Ähnlicher (seit 1.3.30)

Direkte Fortsetzung von 1.3.29 -- derselbe Ausreißer, zwei weitere gemeldete Abweichungen vom
Stammdaten-Muster: die Stammdaten-Navigationsleiste fehlte auf `/employees` (nur ein
Zurück-Link), und Anlegen/Bearbeiten blendeten ein Formular ein statt eine eigene Seite zu öffnen
-- bei Teams/Lieferanten/Fuhrpark/Materialien läuft beides über `master_data_form.html`.

**Vor dem Bauen geprüft, wie verlangt: lässt sich `/employees` in das bestehende Muster
einfügen, statt es dort nachzubauen?** Zwei Wege standen zur Wahl -- (a) Mitarbeiter wird ein
regulärer `master_data.html`-Bereich, Formular über `master_data_form.html`; (b) `/employees`
bleibt eigene Seite, übernimmt aber Navigation und Formularseiten-Aufbau des Stammdaten-Musters.
Geprüft wurde konkret, ob der Vergütungsrechner (der einzige Teil von `/employees`, der über ein
gewöhnliches Adressformular hinausgeht) sich sinnvoll in `master_data_form.html` unterbringen
lässt:

- Der Vergütungsrechner zerfällt bei genauem Hinsehen in ZWEI unabhängige Teile. **Aggregierte
  Kennzahlen** (gewichteter Mittellohn, Mitarbeiterzahl je Kosten-Zuordnung) sind reine
  Client-Berechnung aus dem bereits geladenen `employees`-Array -- ein reines LISTEN-Feature,
  gehört fachlich nach `master_data.html`, nicht in eine Formularseite. **Die Live-Vorschau des
  kalkulatorischen Stundenlohns** (aktualisiert sich beim Tippen von Monatsgehalt/Wochenstunden,
  bevor gespeichert wird) ist reine Formular-JS-Logik ohne Serverkontakt -- architektonisch nichts
  anderes als das, was `master_data_form.html`s `teamForm()` bereits heute mit den dynamischen
  Mitarbeiter-/Ressourcen-Checkboxen macht (Fetch beim Laden, Nachrendern bei Auswahländerung).
- Alle Felder aus `EmployeeCreate`/`EmployeeOut` (`app/schemas.py`) entsprachen 1:1 dem, was
  `employees.html` ohnehin schon abfragte -- kein Endpunkt, kein Feld verlangt etwas, das
  `master_data_form.html`s generische `init()`/`save()`-Struktur nicht bereits für andere Typen
  leistet (Datensatz laden bei `editing`, Payload zusammenbauen, `PUT`/`POST`). `EmployeeOut`
  liefert `function_name`/`effective_hourly_wage` bereits serverseitig berechnet -- die
  LISTE braucht dafür keine einzige Zusatzabfrage (kein `functions`-Fetch nötig, anders als im
  Formular).
- **Kein Hindernis gefunden -- Weg (a) gewählt**, wie vom Nutzer favorisiert ("dann existiert ein
  Muster statt zwei Ähnlicher"). Vor dem Bauen wurde das Ergebnis der Prüfung berichtet und
  bestätigt (wie verlangt), erst danach umgesetzt.

**Umsetzung:**

- `master_data.html`: Mitarbeiter ist jetzt ein regulärer `current`-Bereich wie jeder andere.
  Der Sidebar-Knopf lautet wieder `data-view="employees" onclick="showView('employees')"` (keine
  eigene Seite mehr). `employees` kommt zurück in den `load()`-`Promise.all(...)`-Aufruf
  (`/api/employees`, ungefiltert -- kein `functions`/`labor-rate-settings`-Fetch nötig, siehe
  oben). Ein neuer `current==='employees'`-Zweig zeigt die Kennzahlen-Kacheln (wiederverwendet
  die bereits vorhandene, bis dahin ungenutzte `.metric`-CSS-Klasse dieser Datei) und darunter
  die Tabelle (Muster: exakt dieselben Spalten wie das frühere `employees.html`, "Bearbeiten"
  verlinkt jetzt auf `/master-data/employees/${x.id}/edit` statt eine Inline-Funktion aufzurufen).
- `master_data_form.html`: neue `employeeForm()` plus die dafür nötigen Helfer
  (`activeFunctions()`/`renderFunctionSelect()`/`selectedFunction()`/`syncFunction()`/
  `syncCompensation()`, 1:1 aus `employees.html` übernommen, nur `document.getElementById`-Aufrufe
  auf den bereits vorhandenen `el()`-Helfer umgestellt). Neue globale Variablen `functions`/
  `laborRateSettings`, in `init()`s `employees`-Zweig per `Promise.all([...])` geladen (Muster:
  `teams`-Zweig lädt genauso `employees`/`resources`). Neue CSS-Klasse `.hint` ergänzt (für die
  Stundenlohn-Vorschau-Box) -- `.check` (Checkbox-Zeile) existierte bereits unbenutzt in dieser
  Datei und wird jetzt zum ersten Mal wirklich gebraucht. Bewusst OHNE die alten "Adresse"/
  "Kontaktdaten"-Zwischenüberschriften von `employees.html` -- kein anderes Formular in dieser
  Datei gliedert seine Felder so, ein flaches `.grid` wie überall sonst passt besser zum
  etablierten Stil dieser Datei als die alte Optik von `employees.html` zu bewahren.
- `save()` bekommt einen `employees`-Zweig; die allgemeine Pflichtfeldprüfung
  (`if(!body.name)throw Error(...)`) greift für Mitarbeiter nicht (kein `name`-Feld, nur
  `first_name`/`last_name`) -- exakt dieselbe Ausnahme-Logik, die schon vor der 1.3.26-Migration
  hier stand und beim Entfernen extra dokumentiert wurde, jetzt identisch wiederhergestellt.
- `pages.py`: Route `/employees` entfernt, `"employees"` wieder in die erlaubten `data_type`-Mengen
  von `master_data_create_page`/`master_data_edit_page` aufgenommen. `employees.html` gelöscht.
- `settings.html` (Kalkulationsgrundlagen-Hinweis): Link zurück auf `/master-data#employees`
  (die 1.3.28-Korrektur auf `/employees` wird damit bewusst zurückgenommen) -- **ausdrücklich
  keine wiedereingeschleppte Regression**: die 1.3.28-Korrektur war zum damaligen Zeitpunkt
  richtig (der Hash-View existierte seinerzeit nicht mehr), jetzt gilt das Gegenteil, weil
  `#employees` durch diese Version wieder existiert. Wer `git blame`/die Versionshistorie liest,
  soll diesen Link nicht für eine versehentliche Rückkehr des ursprünglichen 1.3.26-Bugs halten.
- **Neues, dauerhaftes Prinzip**: siehe Regel 10 oben -- jeder Stammdatenbereich zeigt beim
  Einstieg die Liste, trägt die Stammdaten-Navigation, Anlegen/Bearbeiten öffnen immer eine
  eigene Formularseite. Gilt für jeden künftigen Bereich, nicht nur rückwirkend für Mitarbeiter.
- **Tests**: `tests/test_v246_employees_master_data_reintegration.py` (neu) prüft die
  Wiedereingliederung vollständig -- Route/Datei weg, Navigationsleiste vorhanden, Liste vor
  Formular, Anlegen/Bearbeiten verlinken auf `master_data_form.html`, Vergütungsrechner in beiden
  Teilen (Kennzahlen in der Liste, Live-Vorschau im Formular) vorhanden,
  `show_on_planning_board` und alle übrigen Felder vollständig, `settings.html`-Link korrekt.
  Mehrere ältere Tests (`test_v242`, `test_v244`, `test_v063`, `test_v067`, `test_v092`,
  `test_v062`), deren Annahmen die 1.3.26–1.3.29-Zwischenstände geprüft hatten, wurden umgeschrieben
  statt nur angepasst -- sie prüfen jetzt den aktuellen, nicht mehr den historischen Zustand;
  `test_v245_employees_list_first.py` entfiel vollständig (sein gesamtes Prüfobjekt existiert
  nicht mehr). Volle Suite grün.


## Firmenlogo in der Sidebar (seit 1.3.38)

Die Sidebar zeigte oben links immer nur den Schriftzug "DACHKONZEPTE" (`_sidebar.html`, reiner
`<span>`, keine Gestaltung außer fett/Letter-Spacing). Sollte durch ein Logo ersetzt werden,
das jederzeit austauschbar ist.

### Befund vor dem Bauen -- zwei echte Überraschungen

Es gibt bereits seit 1.0.58 ein Firmenlogo-System (`app/company_logo.py`,
`GeneralSettings.logo_filename`, `DACHKONZEPTE_LOGO_FILE_ROOT`, über `data_dir()` also bereits
`ERP_DATA_DIR`-fähig) -- genutzt für den gezeichneten `logo`-PDF-Baustein
(`app/document_frame.py::_draw_logo()`, Standard `visible=False`, siehe "PDF-Rahmen" oben) und
das PWA-Startbildschirm-Icon der Monteursansicht (`app/mobile_manifest.py::build_icon_png()`).
Erlaubt: PNG/JPEG/WebP/SVG, max. 5 MB, keine Prüfung von Seitenverhältnis oder Pixelmaßen.
Ausgeliefert über `GET /api/settings/general/logo` (nur die normale Anmeldepflicht, kein
Admin-Vorbehalt -- unabhängig davon geprüft, nicht in dieser Runde geändert).

**Erste Überraschung: es gibt (und gab) nie ein hochgeladenes Logo.** `GeneralSettings.
logo_filename` stand in der echten Datenbank auf `NULL`, `data/company_logo/` war leer. Die
Frage "taugt das vorhandene Logo für die schmale Sidebar" ließ sich deshalb nicht beantworten --
es gab keine Datei zum Ansehen.

**Zweite Überraschung: es gab (und gibt jetzt neu) keine Oberfläche dafür.** Der Upload-Endpunkt
(`POST /api/settings/general/logo`) existierte, wurde aber von KEINEM Template aufgerufen --
weder ein `<input type="file">` noch ein Aufruf der URL fand sich irgendwo. Die
"Unternehmensstammdaten"-Sektion in `settings.html` hatte nur Textfelder (Name, Adresse, Bank,
Steuer), kein Logo-Feld. Vermutlich ein Rest aus der 1.0.58-Grundlage für den seither (1.3.20)
wieder entfernten PDF-Layout-Editor, dessen eigentliche Logo-Verwaltung mit ihm verschwunden ist,
ohne dass eine Ersatzstelle nachgezogen wurde. Auf Rückfrage ergänzt (siehe unten) -- ohne sie
wäre die neue Sidebar-Anzeige nie zu testen oder zu befüllen gewesen.

### Entscheidung: dasselbe Logo, keinen zweiten Upload

Wie vom Nutzer vorgegeben: kein eigener, zweiter Sidebar-Logo-Upload. Stattdessen zeigt die
Sidebar dasselbe Firmenlogo, das auch PDFs/das PWA-Icon nutzen -- mit einer bewussten
Vorkehrung für später:

- **`app/company_logo.py::sidebar_logo_filename(db) -> str | None`** -- die eigentliche
  "welches Logo zeigt die Sidebar"-Entscheidung, heute immer `GeneralSettings.logo_filename`
  (mit Existenzprüfung der Datei -- ein Datenbankeintrag ohne Datei fällt auf den Schriftzug
  zurück, nicht auf ein defektes `<img>`). Ein späterer, dedizierter Sidebar-Logo-Upload müsste
  nur diese eine Funktion umstellen, keine der Aufrufstellen.
- **`sidebar_logo_url()`** (Jinja-Global, `app/routers/pages.py`, Muster `get_theme()`/
  `is_module_enabled()` -- eigene, kurzlebige `SessionLocal()` je Aufruf, damit ein Logo-Wechsel
  ohne Serverneustart auf der nächsten Seitenanfrage sichtbar wird, siehe "Bekannte, bewusst
  offene Punkte" für die dabei bereits bekannte Einschränkung, dass das nicht per Test-Session
  umstellbar ist). Liefert `/api/settings/general/logo?v=<stored_filename>` oder `None` --
  der `?v=`-Parameter (der pro Upload neue, zufällige `stored_filename`, siehe
  `document_storage.py::make_stored_filename()`) bricht gezielt das Browser-Bild-Caching, sobald
  ein Logo ersetzt wird.
- **`_sidebar.html`**: `{% if sidebar_logo_url() %}` zeigt ein `<img class="app-sidebar-logo">`,
  sonst unverändert der `<span class="app-sidebar-brand">`-Schriftzug -- eine leere Stelle wäre
  schlechter als Text. Ursprünglich `height:32px;width:auto;max-width:160px;object-fit:contain`
  auf demselben `<img>` -- **in 1.3.39 als echter Fehler erkannt und anders gelöst, siehe dort**.
  Verhält sich beim Einklappen der Sidebar (60px-Icon-Leiste) und auf Mobilgeräten exakt wie der
  bisherige Schriftzug (dieselben CSS-Regeln um die Logo-Elemente ergänzt statt neuer, eigener
  Regeln).
- **`_mobile_header.html` (Monteursansicht) bewusst unverändert** -- der Auftrag bezog sich
  ausdrücklich auf "die Sidebar"; die mobile Kopfzeile hat einen eigenen, deutlich schmaleren
  Aufbau (geteilte Zeile mit dem Mitarbeiternamen, Zusatz "· Vor Ort") und war nicht Teil dieser
  Anfrage.
- **Settings-Oberfläche ergänzt** (Einstellungen → Unternehmensstammdaten, neuer Abschnitt
  "Firmenlogo" -- Datei-Upload/Vorschau/Entfernen, Muster der bereits bestehenden
  Briefpapier-Upload-Felder unter Dokumente & Layout): da es vorher gar keine Oberfläche gab,
  war ein bloßer Hinweistext ("dieses Logo erscheint auch in der Sidebar") ohne Weg, überhaupt
  eines hochzuladen, wirkungslos gewesen -- die Ergänzung war Voraussetzung dafür, dass sich die
  neue Sidebar-Anzeige praktisch nutzen und testen lässt, nicht nur Text.

### Geprüft, nicht nur behauptet

Kein reales Firmenlogo vorhanden, also mit drei synthetischen Testbildern (quadratisch 200×200,
breit 600×100, hoch 100×600) gegen eine isolierte, lokale Testinstanz (frische SQLite-Datei,
eigener Port) tatsächlich durchgespielt: Hochladen über den echten Endpunkt, Sidebar zeigt danach
das `<img>` mit korrekter, cache-brechender URL, ausgeliefertes Bild byte- und
pixelgenau identisch mit der hochgeladenen Datei (Content-Type `image/png`, Pillow-Nachmessung
der Maße), für alle drei Seitenverhältnisse. Entfernen des Logos lässt die Sidebar korrekt zum
Schriftzug zurückfallen. **Kein echter Browser-Screenshot** -- in dieser Umgebung stand kein
Browser-Automatisierungswerkzeug zur Verfügung (dieselbe, bereits in "Mitarbeiter-Formular
list-first" dokumentierte Einschränkung). Genau dieser fehlende Browser-Screenshot ließ einen
echten CSS-Fehler durchrutschen -- siehe "Fehlerbehebung und einstellbare Höhe" unten: die
Behauptung "mathematisch aspect-ratio-treu" für `height`+`max-width`+`object-fit:contain` auf
demselben `<img>` war falsch.

### Fehlerbehebung und einstellbare Höhe (seit 1.3.39)

Rückmeldung nach dem ersten echten Einsatz: bei 32px Höhe war ein Schriftzug unter dem
Bildzeichen nicht mehr lesbar. Zwei Änderungen plus eine Untersuchung an der tatsächlich
hochgeladenen Datei, bevor irgendetwas an einem zweiten Upload gebaut wurde.

**Echter, selbst gefundener CSS-Fehler.** Der ursprüngliche Ansatz (`height`, `max-width` und
`object-fit:contain` alle auf demselben `<img>`) verkleinert bei einem breiten Logo die Höhe
wieder: die CSS-Ersatzelement-Breiten/Höhen-Auflösung (CSS 2.1 §10.3.2/§10.4) verwirft die feste
Höhe, sobald `max-width` als Override eingreift -- `width` wird dann auf `max-width` festgelegt
UND `height` bleibt zwar formal wie angegeben, aber `object-fit:contain` skaliert den
sichtbaren Bildinhalt anschließend so, dass er in die (jetzt schmalere) Box passt, was bei einem
hinreichend breiten Bild die tatsächlich sichtbare Höhe unter den konfigurierten Wert drückt --
exakt das Symptom, das man vermeiden will. Behoben durch Entkopplung: die Breitenbegrenzung
(jetzt 200px) sitzt auf einem umschließenden `<span class="app-sidebar-logo-wrap">`
(`overflow:hidden`), das `<img>` selbst trägt NUR noch die feste Höhe (als Inline-Style, siehe
unten) und `flex:0 0 auto` (verhindert zusätzlich ein Verkleinern durch Flexbox selbst). Ein zu
breites Logo wird dadurch rechts **abgeschnitten**, nicht mehr verkleinert -- an einem
synthetischen 1000×60px-Testbild (Seitenverhältnis 16,7:1) nachgewiesen: bei 64px eingestellter
Höhe liefert die Sidebar exakt `style="height:64px"` ohne jedes `max-width` auf dem `<img>`.
**Grundsatz für jedes künftige `<img>` mit unbekanntem Seitenverhältnis**: `height` (oder
`width`) UND eine Begrenzung der anderen Achse (`max-width`/`max-height`) nie auf demselben
Element -- die Begrenzung gehört auf einen Wrapper mit `overflow:hidden`, sonst kann die feste
Achse bei einem extremen Seitenverhältnis unbemerkt unterlaufen werden.

**Einstellbare Höhe** (24-80px, Feld direkt neben dem Upload in Einstellungen →
Unternehmensstammdaten): `GeneralSettings.sidebar_logo_height_px` (Migration `c327ff4ad332`,
`server_default='48'`), `app/company_logo.py::sidebar_logo_height_px(db)` (auf den erlaubten
Bereich geklammert, dieselbe Verteidigung-in-der-Tiefe wie bei `sidebar_logo_filename()`), neuer
Jinja-Global `sidebar_logo_height_px()` -- die Sidebar liest die Höhe live, kein
Serverneustart nötig. Auswirkung auf den Kopfbereich (wie vom Nutzer verlangt, VOR dem Bauen
berichtet): bei 48px (neuer Standard) wächst die Kopfzeile von vorher ca. 52px auf ca. 80px
(+~54%), am oberen Ende (80px) auf ca. 112px (+~115%) -- beides im normalen Rahmen für einen
Sidebar-Header mit Logo, kein Kompromiss nötig, aber bewusst nicht unbegrenzt (deshalb die
80px-Obergrenze).

**Die tatsächlich hochgeladene Datei, genau untersucht, bevor über einen zweiten Upload
entschieden wurde**: 8000×5295px RGBA-PNG, Inhalts-Bounding-Box (per Alphakanal) 5970×4907px
(Seitenverhältnis ≈1,22:1). Der Inhalt ist eine EINZIGE, durchgehende geometrische Form (ein
zweifarbiges Chevron/Dach-Symbol) -- lückenlos von y≈132px bis y≈5148px, **kein Schriftzug an
irgendeiner Stelle** (auch am unteren Rand der Inhalts-Box vergrößert nachgeprüft: reines Weiß).
Das widerlegt die ursprüngliche Annahme "Bildzeichen mit Schriftzug darunter" -- vermutlich wird
der Firmenname in PDFs ohnehin separat als echter Text gezeichnet
(`build_din5008_header_block()`), nicht als Teil der Logo-Grafik; der optische Gesamteindruck
"Icon + Name" entsteht erst durch beides zusammen, nicht durch eine einzelne Bilddatei.
**Ergebnis: mehr Höhe reicht, kein eigener Sidebar-Upload nötig** -- ein einfaches, kräftiges,
fast quadratisches Symbol ohne feine Details bleibt bei jeder Höhe zwischen 24 und 80px klar
erkennbar, die Rechnung "wird der Schriftzug bei X px unter 8px und damit unlesbar" war für
diese Datei von Anfang an gegenstandslos, da es keinen Schriftzug gibt. Vom Nutzer bestätigt --
kein zweiter Upload gebaut, `sidebar_logo_filename()` bleibt bei genau einer Stufe
(Firmenlogo → Schriftzug). **Diese Diagnose war falsch -- seit 1.3.43 korrigiert, siehe
"Korrektur: doch ein Schriftzug" am Ende dieses Abschnitts.**

### Anzeige-Rendition (seit 1.3.40)

Die echte, hochgeladene Datei war 8000×5295px/252KB -- in der Sidebar auf 24-80px Höhe
dargestellt. Ohne Gegenmaßnahme lädt UND dekodiert der Browser bei JEDER Seitenanfrage die
vollen 42 Megapixel, da dieses Projekt ausschließlich klassische Mehrseiten-Navigation macht
(keine SPA) -- die Sidebar wird bei jedem Klick neu angefordert, nicht nur einmal. Selbst mit
perfektem Netzwerk-Caching bliebe der Dekodier-Aufwand (42 Mio. Pixel → Bitmap im Speicher)
bei jedem Rendern bestehen.

**Lösung**: `replace_logo()` (`app/company_logo.py`) erzeugt beim Hochladen zusätzlich zur
unveränderten Originaldatei (weiterhin für PDFs/das PWA-Icon, die beide `logo_path()` direkt von
der Platte lesen, siehe `document_frame.py`/`mobile_manifest.py` -- dort zählt die volle
Auflösung tatsächlich, ein Druck-PDF darf nicht durch diese Änderung an Qualität verlieren) eine
verkleinerte Anzeige-Rendition (`display_logo_path()`, `<stem>_display.png`, längste Kante auf
`MAX_DISPLAY_DIMENSION=480` px herunterskaliert -- reicht für 80px CSS-Höhe selbst auf einem
3x-Retina-Bildschirm bequem aus). `GET /api/settings/general/logo` -- der EINZIGE
HTTP-Auslieferungsweg (Sidebar-`<img>` UND die Vorschau in den Einstellungen; PDFs/PWA-Icon
nutzen ihn nie) -- liefert bevorzugt diese Rendition, fällt auf das Original zurück, wenn keine
existiert (SVG -- dort unnötig, bereits vektoriell/klein -- oder ein vor 1.3.40 hochgeladenes
Logo). Scheitert die Rendition-Erzeugung (z. B. ein Pillow nicht bekanntes/beschädigtes Format),
bricht der Upload NICHT ab -- ein etwas größeres Original ist besser als ein fehlgeschlagener
Upload, `view_company_logo()` fällt dann einfach auf das Original zurück. Zusätzlich
`Cache-Control: private, max-age=31536000, immutable` auf der Antwort -- sicher, weil die URL
bereits einen `?v=<stored_filename>`-Cache-Brecher trägt (derselbe Name zeigt nie auf einen
später geänderten Inhalt, ein neuer Upload bekommt einen neuen Namen).

**Real gemessen, nicht nur behauptet** (mit der tatsächlichen Logo-Datei, gegen eine isolierte
Testinstanz): Original 258.475 Bytes/8000×5295px -- ausgelieferte Rendition 19.530 Bytes/
480×318px. **Faktor ~13 bei der Übertragungsgröße, Faktor ~278 bei der Pixelzahl** (42,4 Mio. →
153.000 Pixel). Beide Dateien bestätigt nebeneinander auf der Platte vorhanden, Sidebar zeigt
weiterhin `style="height:48px"` unverändert korrekt.

### Korrektur: doch ein Schriftzug -- dedizierter Sidebar-Logo-Upload (seit 1.3.43)

Die 1.3.39-Diagnose ("kein Schriftzug an irgendeiner Stelle", per Bounding-Box-Auswertung des
Alphakanals ermittelt) war falsch. Auf einem echten Screenshot der Sidebar ist "DACHKONZEPTE
GmbH" und darunter gesperrt "RÖDCHEN" klar erkennbar, unterhalb des Dachzeichens -- die
automatisierte Auswertung hat das nicht erkannt, mutmaßlich weil Schriftzug und Bildzeichen
räumlich zu nah beieinander liegen, um über eine einzelne Inhalts-Bounding-Box getrennt zu
werden (die Messung selbst -- 8000×5295px, Inhalts-Box 5970×4907px -- bleibt richtig, nur ihre
Interpretation "eine einzige, durchgehende Form ohne Text" war es nicht). Das ändert die
1.3.39-Antwort: ein zweiter, dedizierter Sidebar-Logo-Upload ist doch nötig.

- **Zwei unabhängige Uploads statt einem** (`app/company_logo.py`, vollständig überarbeiteter
  Moduldocstring dort): **Firmenlogo** (`LOGO_ROOT`, `GeneralSettings.logo_filename`) bleibt für
  PDFs und das PWA-Icon zuständig, unverändert. Neu: **Sidebar-Logo** (`SIDEBAR_LOGO_ROOT`, neue
  Spalte `GeneralSettings.sidebar_logo_filename`, Migration `4ba46163a7e8`, eigener Ordner unter
  `ERP_DATA_DIR` -- Umgebungsvariable `DACHKONZEPTE_SIDEBAR_LOGO_FILE_ROOT`, achte Variable dieser
  Art, siehe `.env.example`). Beide Uploads teilen sich dieselbe Speicher-/Validierungslogik
  (`validate_logo_image()`, Anzeige-Rendition aus 1.3.40) über einen gemeinsam genutzten
  `root`-Parameter an `logo_directory()`/`logo_path()`/`display_logo_path()`/
  `_generate_display_rendition()`/`replace_logo()`/`delete_logo()` -- `replace_sidebar_logo()`/
  `delete_sidebar_logo()`/`sidebar_logo_path()`/`sidebar_logo_display_path()` sind dünne
  Wrapper, die `root=SIDEBAR_LOGO_ROOT` fest einsetzen. **Fallstrick beim Bauen, selbst gefunden
  und behoben, bevor er in Produktion gegangen wäre**: ein naiver `root: Path = LOGO_ROOT`-
  Vorgabewert an diesen Funktionen hätte den bestehenden Testmustern
  (`monkeypatch.setattr(company_logo, "LOGO_ROOT", tmp_path / ...)`, u. a. in
  `tests/test_v158_pdf_layout_foundation.py`/`test_v249_sidebar_logo.py`) den Boden entzogen --
  ein Vorgabewert wird einmalig bei der Modul-Definition gebunden, nicht bei jedem Aufruf neu aus
  dem (dann längst geänderten) Modul-Global gelesen. Stattdessen `root: Path | None = None` mit
  `if root is None: root = LOGO_ROOT` im Funktionskörper -- liest `LOGO_ROOT` bei jedem Aufruf
  frisch, genau wie vor dem Umbau.
- **Drei statt zwei Stufen** (`sidebar_logo_filename(db)`, weiterhin in `company_logo.py`): (1)
  Sidebar-Logo, falls hinterlegt und die Datei existiert, (2) sonst Firmenlogo unter derselben
  Bedingung, (3) sonst `None` (Schriftzug). Liefert dafür seit 1.3.43 kein nacktes
  `str | None` mehr, sondern ein `SidebarLogoReference`-NamedTuple (`source: "sidebar"|"company"`,
  `stored_filename`) -- der einzige Aufrufer (`sidebar_logo_url()` in `app/routers/pages.py`)
  braucht die Quelle, um die richtige von zwei getrennten Auslieferungsrouten anzusprechen
  (`GET /api/settings/general/sidebar-logo` bzw. `.../logo`, je im eigenen Ordner). Die
  1.3.42-Ausnahmesicherheit dieses Jinja-Globals bleibt dabei unverändert vollständig -- der
  gesamte Rangfolge-Aufruf UND das URL-Zusammensetzen aus `ref.source`/`ref.stored_filename`
  liegen innerhalb desselben `try/except Exception`-Blocks, ein unerwarteter Wert schlägt also
  ebenso wenig durch wie ein DB-Fehler.
- **Zwei neue Endpunkte** (`app/routers/settings.py`, Muster der bestehenden Firmenlogo-Routen):
  `POST/GET/DELETE /api/settings/general/sidebar-logo` -- Upload validiert genauso über
  `validate_logo_image()` (400 statt 500 bei einem ungültigen Bild, siehe 1.3.42), GET liefert
  bevorzugt die Anzeige-Rendition mit demselben unveränderlichen Cache-Header wie beim
  Firmenlogo.
- **Einstellungen klar getrennt** (Unternehmensstammdaten → zwei eigene Abschnitte
  "Firmenlogo"/"Sidebar-Logo" statt eines gemeinsamen): das Firmenlogo-Feld verlor dabei sein
  bisheriges Höhenfeld (das war ohnehin die Sidebar-Anzeigehöhe, nicht seine eigene) -- es wandert
  vollständig zum neuen Sidebar-Logo-Abschnitt, wo es fachlich hingehört (gilt für das jeweils
  tatsächlich in der Seitenleiste gezeigte Logo, unabhängig davon, welche Stufe greift). Ein
  client-seitig berechneter Hinweistext im Sidebar-Logo-Abschnitt sagt live, welche Stufe ohne
  eigenes Sidebar-Logo aktuell greift ("zeigt ersatzweise das Firmenlogo" / "zeigt den
  Schriftzug").
- **Tests** (`tests/test_v249_sidebar_logo.py`, überarbeitet): alle drei Stufen einzeln (nur
  Firmenlogo, Sidebar-Logo vor Firmenlogo, Sidebar-Logo-Datei fehlt → Rückfall auf Firmenlogo,
  beides fehlt → `None`), die drei neuen Endpunkte über `router_test_client()`, und dass ein
  Sidebar-Logo-Upload den Firmenlogo-Ordner/-Datensatz unangetastet lässt (getrennte Ordner,
  getrennte Spalten).

## Umgestaltung der Sidebar (seit 1.3.44)

Größerer Umbau von `_sidebar.html`/dem Seitenlayout in vier einzelnen Schritten -- dieser
Abschnitt wächst mit jedem Schritt. Schritt 1 (1.3.44): Kopfbereich (Logo) und die beiden
Kopfzeilen-Schaltflächen. Schritt 2 (1.3.45, diese Version): eine Topbar über dem Inhaltsbereich
samt Kontobereich rechts. Schritt 3-4 (Suche, Schnellzugriff) folgen einzeln in späteren
Versionen -- **bewusst nicht vorgezogen**, auch wenn der links reservierte, noch leere
Suchen-Platz in der Topbar bereits auf Schritt 3 vorbereitet.

### Schritt 1: Kopfbereich und Schaltflächen

**Ausgangslage**: das Logo stand oben links, direkt daneben (im selben, schmalen Kopfbereich)
die beiden Schaltflächen für Hell/Dunkel und Ein-/Ausklappen -- dadurch blieb für das Logo selbst
wenig Breite, ein Logo mit Schriftzug wäre darin unlesbar klein geblieben.

**Punkt 1 -- Logo allein, zentriert, volle Breite.**

- `.app-sidebar-head` wechselt von `justify-content:space-between` (Logo links, Buttons rechts)
  zu `justify-content:center` mit nur noch einem Kind (Logo bzw. Schriftzug-Fallback) -- die
  beiden Schaltflächen sind komplett aus dem Kopf entfernt, siehe Punkt 2.
- `.app-sidebar-logo-wrap`s Breitenbegrenzung wechselt von einem festen `max-width:200px` zu
  `max-width:100%` -- **bewusst relativ statt eines neuen, größeren festen Werts**: genau das
  war die vom Nutzer benannte Gefahr ("die Breitenbegrenzung muss entsprechend mitwachsen,
  sonst greift sie wieder zuerst und drückt die Höhe herunter") -- ein fester Wert hätte bei
  einer künftigen Änderung der Sidebar-Breite (240px) wieder auseinanderlaufen können, ein
  relativer nie. Die zugrundeliegende 1.3.39-Regel (Höhe und Breitenbegrenzung nie auf
  demselben `<img>`, die Begrenzung gehört auf einen Wrapper mit `overflow:hidden`) bleibt
  unverändert gültig und wird hier nur konsequent weitergeführt, nicht neu erfunden.
- **Höhenbereich auf 24-120px erweitert** (vorher 24-80), Standardwert von 48 auf 64 angehoben
  -- `company_logo.py::MIN/MAX/DEFAULT_SIDEBAR_LOGO_HEIGHT_PX`, `GeneralSettings.
  sidebar_logo_height_px` (Migration `60d7c8a775f0`, reiner `server_default`-Wechsel 48→64),
  `GeneralSettingsUpdate.sidebar_logo_height_px` (Pydantic-Grenzen), `settings.html` (Zahlenfeld
  `min`/`max`, Hinweistext, JS-Validierung). Begründung für den angehobenen Standardwert: der
  Kopf teilt sich die Breite nicht mehr mit den beiden Schaltflächen, ein größerer Standardwert
  wirkt dadurch nicht mehr gedrängt wie vorher. **Ausdrücklich transparent**: eine erneute,
  präzise Nachrechnung "wird ein Schriftzug bei Höhe X noch lesbar" (wie in 1.3.39 versucht)
  konnte für diese Version nicht wiederholt werden -- die lokal verfügbare Beispieldatei
  (`4ce61c7cadf743b7bee52db6bac1b4f8.png`) enthält bei tatsächlichem Nachsehen (Pillow-
  Zeilenprofil der Alphakanal-Tinte UND direktes Betrachten der Datei) nachweislich **keinen**
  Schriftzug, nur das zweifarbige Dachzeichen -- ein Widerspruch zur zuletzt beschriebenen
  Beobachtung ("DACHKONZEPTE GmbH"/"RÖDCHEN" auf einem Sidebar-Screenshot erkennbar), der sich
  mit den hier verfügbaren Mitteln nicht auflösen ließ (vermutlich zeigte jener Screenshot eine
  andere, tatsächlich hochgeladene Datei aus einer Umgebung, die dieser Sitzung nicht zugänglich
  ist). 64px ist deshalb eine begründete, aber nicht anhand einer konkreten Schriftzug-Höhe
  durchgerechnete Zwischenlösung -- bei Gelegenheit gegen die tatsächlich verwendete Datei
  visuell im Browser zu prüfen.
- **Eingeklappte Sidebar (60px) -- eigene, feste Behandlung statt der einstellbaren Höhe.** Wie
  vom Nutzer erwartet ("vermutlich braucht es dafür eine eigene Behandlung") reicht die für die
  volle Breite gedachte, einstellbare Höhe bei 60px nicht: bei 6px Kopf-Padding je Seite (eigens
  für den eingeklappten Zustand reduziert, vorher 14px) bleiben nur 48px Breite, ein bei 120px
  Höhe konfiguriertes Logo würde bei gleichem Seitenverhältnis weit darüber liegen. Lösung:
  `.app-sidebar.collapsed .app-sidebar-logo{height:32px!important}` -- eine feste, vom
  eingestellten Wert unabhängige, kleinere Höhe (die `!important` ist nötig, da die konfigurierte
  Höhe als Inline-Style sonst Vorrang hätte). Für das reine Text-Schriftzug-Fallback (kein Logo
  hinterlegt) bleibt es bei "gar keins" -- vollständig ausgeblendet wie bisher, für
  "DACHKONZEPTE" ist bei 60px kein sinnvoller Platz, anders als bei einem meist eher quadratischen
  Bildzeichen. Beide Regeln bewusst in `@media(min-width:1001px)` gekapselt (nicht einfach nur
  `.app-sidebar.collapsed ...`) -- auf Mobilgeräten kann die `collapsed`-Klasse durch einen
  Resize ohne Neuladen bestehen bleiben (siehe das bereits bestehende
  `@media(max-width:1000px)`-Zurücksetzen), dort soll das aber weiterhin die volle, unveränderte
  Darstellung bedeuten, nicht die geschrumpfte Desktop-Variante.

**Punkt 2 -- Hell/Dunkel und Ein-/Ausklappen in den unteren Bereich.**

Neuer Wrapper `.app-sidebar-bottom` (mit dem `border-top`, das vorher auf `.app-sidebar-foot`
saß) umschließt jetzt in dieser Reihenfolge: eine neue Zeile `.app-sidebar-utilities` (beide
Schaltflächen, direkt unter der Navigation), `#appSidebarFoot` (Benutzer/Abmelden bzw.
Login-Formular, unverändert), `.app-sidebar-version`. "Neben Abmelden" wörtlich als eigene Zeile
direkt darüber umgesetzt, nicht als eine einzige, gemeinsame Zeile mit dem Abmelden-Button --
letzteres hätte bei einem vollbreiten Text-Button plus zwei Icon-Buttons zusammengedrängt gewirkt,
genau das vom Nutzer benannte Risiko ("ohne dass es gedrängt wirkt"). Beide Bereiche liegen
dadurch trotzdem sichtbar im selben, unteren Block direkt aneinander angrenzend.

Bewusst **keine** Änderung an `renderAuthFoot()` (dem JS, das `#appSidebarFoot` bei jedem
Auth-Status-Abruf per `innerHTML` neu aufbaut, inkl. "Mein Konto"): die beiden Schaltflächen
sitzen als statisches Jinja-Markup außerhalb von `#appSidebarFoot`, ihre einmalig beim
Skriptstart gebundenen Event-Listener (`toggle.addEventListener(...)`, `themeToggle.
addEventListener(...)`) werden dadurch nie zerstört -- kein erneutes Binden nötig, kein Risiko,
die sicherheitsrelevante Login/Logout-Logik dabei versehentlich anzufassen. "Mein Konto" bleibt
deshalb unverändert innerhalb von `#appSidebarFoot`, exakt wie vom Nutzer vorgegeben ("wandert
erst mit der Topbar in einem späteren Schritt nach oben").

**Bedienbarkeit im eingeklappten Zustand geprüft**: `.app-sidebar.collapsed .app-sidebar-toggle`
wird an KEINER Stelle auf `display:none` gesetzt (nur `.app-theme-toggle` verschwindet
eingeklappt, bereits bestehendes, unverändertes Verhalten) -- die Schaltfläche, mit der man
wieder ausklappt, bleibt im eingeklappten Zustand also garantiert erreichbar. Als Regressionstest
festgehalten (`test_collapse_toggle_is_never_hidden_when_collapsed_but_theme_toggle_is`,
`tests/test_v253_sidebar_layout.py`), da ein versehentliches `display:none` auf der falschen
Klasse genau diese Bedienbarkeit stillschweigend gebrochen hätte.

**Was unverändert bleibt, geprüft statt nur behauptet**: `_mobile_header.html` kennt keine der
hier verschobenen/neuen Klassen (`app-sidebar-head`/`app-sidebar-utilities`/`app-theme-toggle`/
`app-sidebar-toggle`) -- als Test festgehalten. Navigationseinträge, ihre Reihenfolge und die
Gruppen "Stammdaten"/"System" (1.3.28) sind an keiner Stelle angefasst, nur Kopf- und
Fußbereich drumherum.

**Kein echter Browser-Screenshot möglich** (dieselbe, bereits mehrfach dokumentierte
Werkzeug-Einschränkung dieser Umgebung) -- die tatsächliche visuelle Zentrierung/Anordnung ist
deshalb nur an der Markup-/CSS-Struktur nachgewiesen (`tests/test_v253_sidebar_layout.py`), nicht
an einem gerenderten Bild. Sollte bei Gelegenheit im Browser gegenprüft werden, insbesondere mit
dem tatsächlich hochgeladenen Sidebar-Logo.

### Schritt 2: Topbar

**Ausgangslage**: mit "Mein Konto" noch in der Sidebar (Schritt 1 verschiebt es bewusst nicht)
und keiner Leiste über dem Inhaltsbereich gab es weder Platz für eine künftige Suche (Schritt 3)
noch einen für den ganzen Bildschirm einheitlichen Ort für Kontoinformationen.

**Punkt 1 -- die Leiste selbst (`app/templates/_topbar.html`, neu).**

- Waagerecht, beginnt rechts neben der Sidebar (liegt als `{% include %}` innerhalb von
  `.app-content`, direkt nach dessen öffnendem `<div>` -- nie über die Sidebar hinweg, da
  `.app-content{flex:1;min-width:0}` in der bestehenden Flexbox-Aufteilung ohnehin nur den nach
  der Sidebar verbleibenden Platz einnimmt).
- `position:sticky;top:0` -- bleibt beim Scrollen sichtbar. Kein Zwischen-`overflow`-Vorfahre
  zwischen `.app-topbar` und dem Dokument-Scrollroot geprüft (sonst bräche die sticky-
  Positionierung), keiner gefunden.
- Höhe ergibt sich allein aus Innenabstand (`padding:12px 20px`, auf schmalen Bildschirmen
  `10px 16px`) plus dem 38px-Kontoknopf -- bewusst kein festgelegter `height`-Wert, damit die
  Leiste nicht dominiert, aber der Knopf bequem (≥38px) bedienbar bleibt.
- Ausschließlich bestehende Design-System-Variablen (`var(--card)`, `var(--line)`,
  `var(--accent)`, `var(--ink)`, `var(--soft)`) -- keine eigenen Farben. Die einzige feste
  Hex-Farbe (`#fff`, Text auf `var(--accent)` beim Kontoknopf) ist die bereits im ganzen Projekt
  etablierte Konvention für Text auf Akzentfarbe (z. B. `settings.html`s Buttons), keine neue
  Erfindung -- als Test abgesichert (`test_topbar_is_sticky_and_uses_design_system_variables_only`).
- Links bleibt in diesem Schritt ein leerer `<div class="app-topbar-search-slot">` (`flex:1`) --
  reserviert für Schritt 3, absichtlich ohne Inhalt.
- **Kollision mit der Sidebar in beiden Engpass-Zuständen geprüft, nicht nur behauptet:**
  - *Eingeklappte Desktop-Sidebar (60px)*: `.app-content{flex:1}` füllt in der bestehenden
    Flexbox-Aufteilung automatisch den nach der Sidebar verbleibenden Platz, unabhängig von deren
    aktueller Breite (240px oder 60px) -- die (in `.app-content` verschachtelte) Topbar beginnt
    dadurch ganz automatisch dort, wo die Sidebar gerade endet, ohne jede Sonderbehandlung.
  - *Schmaler Bildschirm (`@media(max-width:1000px)`)*: die mobile Sidebar wechselt dort auf
    `position:fixed` und verlässt damit den Flex-Fluss vollständig -- `.app-content` (und darin
    die Topbar) beansprucht dadurch automatisch die volle Breite, unabhängig davon, ob die
    Off-Canvas-Schublade offen oder geschlossen ist. Eine geöffnete mobile Sidebar
    (`z-index:40`)/ihr Scrim (`z-index:39`) sollen die Topbar dabei bewusst überlagern (gewolltes
    Ausklapp-Verhalten, kein Bug) -- die Topbar bekommt deshalb absichtlich ein niedrigeres
    `z-index:10`. Das Kontomenü selbst (`z-index:45`) liegt trotzdem über allem, da es ein
    eigenes, schwebendes Overlay ist.
  - **Nebenbefund, nicht behoben, nur vermerkt**: auf einem wirklich schmalen Bildschirm gibt es
    aktuell offenbar gar keinen Weg, die Off-Canvas-Sidebar überhaupt zu ÖFFNEN -- der einzige
    Umschalter (`#appSidebarToggle`) sitzt selbst innerhalb von `<aside class="app-sidebar">`,
    die im geschlossenen Zustand per `transform:translateX(-100%)` unsichtbar/unerreichbar ist.
    Vorher UND nachher bestehend (durch die 1.3.44-Verschiebung der Schaltflächen nicht
    verursacht), aber jetzt relevant, weil eine künftige Topbar-Hamburger-Schaltfläche eine
    naheliegende Lösung wäre -- nicht Teil dieses Schritts, hier nur festgehalten.

**Punkt 2 -- der Kontobereich rechts.**

- Neuer, gemeinsamer Helfer `app/auth.py::resolve_account_display(db, user) -> dict` (nach
  `user_from_request()`): bevorzugt `Employee.first_name`/`last_name` über
  `AppUser.employee_id` (seit 1.3.34 die Verknüpfung, aber **ohne** ORM-`relationship` -- daher
  ein expliziter `db.get(Employee, id)`), fällt auf `username` zurück, wenn kein Mitarbeiter
  verknüpft ist ODER die `employee_id` ins Leere zeigt (Verteidigung in der Tiefe). Initialen:
  erstes Zeichen von Vor- und Nachname bei ≥2 Namensteilen ("Tobias Rödchen" → "TR"), sonst die
  ersten zwei Zeichen des einzigen Teils, geklammert auf mindestens ein Zeichen (ein
  einbuchstabiger Benutzername liefert genau diesen einen Buchstaben, keinen `IndexError`).
  **Bewusst NICHT `AppUser.display_name`** -- das ist ein freies Textfeld ohne verlässliche
  Vorname/Nachname-Trennung, `Employee.first_name`/`last_name` sind strukturierte Felder.
- Fünfter Jinja-Global `account_display()` (`app/routers/pages.py::_account_display()`) --
  umhüllt `resolve_account_display()` mit einer eigenen, kurzlebigen `SessionLocal()` (Muster
  der bestehenden vier) und fängt jede Ausnahme ab (Prinzip aus 1.3.42: "ein Jinja-Global, der
  auf jeder Seite läuft, darf nie eine Ausnahme werfen") -- Rückfall bei Fehler: der
  Benutzername selbst, notfalls ein bloßes `"?"`. Anonym (kein `current_user`): leere Strings,
  der Kontoknopf erscheint dann gar nicht. Als sechster `env.globals[...]`-Eintrag im
  projektweiten Audit-Test (`test_no_further_database_backed_jinja_globals_exist_unguarded`,
  `tests/test_v252_deployment_hardening.py`) mitgezählt.
- **SSR statt zusätzlichem Fetch, bewusste Entscheidung**: Name/Initialen kommen direkt
  server-seitig gerendert in die Seite (wie schon die Sidebar-Nutzerinfo) -- kein zusätzlicher
  `fetch()`-Aufruf beim Laden nötig, da sich Initialen kaum je innerhalb einer Sitzung ändern.
  Nur das Öffnen/Schließen des Menüs (Klick auf den Knopf, Klick daneben, Escape) braucht JS --
  ohne jeden weiteren Netzwerkzugriff, da Name/Initialen bereits im HTML stehen.
- Menü (`#appTopbarAccountMenu`): voller Name als Überschrift, `<a href="/account">Mein
  Konto</a>`, `<button>Abmelden</button>` -- Logout dupliziert bewusst denselben
  Fetch-plus-Redirect-Code aus `_sidebar.html` (etablierte Projektkonvention: kein gemeinsames
  JS-Modul, kleine Snippets werden geteilt statt ausgelagert). Schließt bei Klick außerhalb
  (`document.addEventListener("click", ...)`, prüft `!menu.contains(e.target)`) oder Escape.

**Punkt 3 -- was in der Sidebar bleibt, unverändert.** "Abmelden" bleibt zusätzlich unten in der
Sidebar (zwei Wege schaden nicht), ebenso Benutzername und Versionsnummer. Die beiden
1.3.44-Schaltflächen (Hell/Dunkel, Ein-/Ausklappen) bleiben, wo sie sind -- `_sidebar.html` wird
in diesem Schritt an keiner Stelle angefasst.

**Rollout auf 31 Seiten**: jede Vorlage mit `{% include "_sidebar.html" %}` bekommt direkt nach
dem öffnenden `<div class="app-content">` zusätzlich `{% include "_topbar.html" %}` -- per Grep
verifiziert: genau 31 Treffer, je Datei genau einmal. **Bewusst ausgenommen**: die Monteursansicht
(`vor_ort.html`, nutzt `_mobile_header.html` statt der Sidebar) -- eigene Einschätzung, die der
Nutzer-Neigung ausdrücklich zustimmt: `_mobile_header.html` zeigt den Namen des angemeldeten
Monteurs bereits prominent und hat einen eigenen Ein-Klick-Abmelden-Button; ein zusätzlicher,
für den Desktop gedachter Kontoknopf/-menü würde der bewusst schmal gehaltenen, aufs Wesentliche
reduzierten Feld-Tablet-Ansicht entgegenwirken. Als Konsistenz-Test festgehalten
(`test_every_template_with_sidebar_also_includes_topbar`, `tests/test_v254_topbar.py`) --
Partials (Dateien mit führendem `_`) sind davon ausgenommen, da `_topbar.html`s eigener,
erklärender Jinja-Kommentar den Text `{% include "_sidebar.html" %}` selbst zitiert und sonst
fälschlich als Treffer gezählt würde (reiner Text-Scan-Fund, kein Rendering-Risiko -- ein
Jinja-Kommentar wird beim Rendern vollständig entfernt, anders als der 1.2.19-Fund in
`_debounce.html`, der ein JS-Kommentar war).

**Kein echter Browser-Screenshot möglich** (dieselbe Werkzeug-Einschränkung wie bei Schritt 1) --
Platzierung/Sticky-Verhalten/Menü-Interaktion sind ausschließlich über eine bare
`jinja2.Environment` mit gestubbten Globals (`tests/test_v254_topbar.py`) sowie an der reinen
Markup-/CSS-Struktur nachgewiesen, nicht an einem gerenderten Bild. Sollte bei Gelegenheit im
Browser gegenprüft werden.

### Nachtrag zu Schritt 2 (seit 1.3.46): mobiler Öffnen-Umschalter

Echter, vor Schritt 3 (Suche) gemeldeter und behobener Nebenbefund -- genau die Art Fehler, die
eine reine Struktur-/CSS-Prüfung ohne echten Browser leicht übersieht, weil sie nichts über
tatsächliche Bildschirmbreiten weiß, siehe unten für den dafür geschriebenen Test.

**Der Fund**: auf einem schmalen Bildschirm (`<1000px`) gab es keinen erreichbaren Weg, die
Off-Canvas-Sidebar überhaupt zu öffnen. Ihr einziger bisheriger Umschalter (`#appSidebarToggle`,
seit 1.3.44 unten in `.app-sidebar-utilities`) steckte selbst innerhalb von
`<aside class="app-sidebar">` -- im geschlossenen Zustand per `transform:translateX(-100%)`
komplett unsichtbar. Bereits in 1.3.45 als Nebenbefund vermerkt (siehe Schritt 2 oben, "vorher
UND nachher bestehend"), hier zuerst behoben.

**Lösung: ein zweiter Umschalter außerhalb der Sidebar.** Neuer `#appTopbarMenuBtn` in
`_topbar.html` -- als erstes Kind von `.app-topbar`, VOR dem für Schritt 3 reservierten
Suchen-Platzhalter (`.app-topbar-search-slot`), damit er auch bei geschlossener Sidebar
erreichbar bleibt (liegt in `.app-content`, nicht in `.app-sidebar`). Erscheint ausschließlich
unterhalb desselben Umbruchpunkts wie die Off-Canvas-Sidebar selbst (`max-width:1000px`, exakt
derselbe Wert wie in `_sidebar.html` -- ein abweichender Wert hätte ein Fenster geöffnet, in dem
der Knopf entweder sichtbar ist, aber nichts Erreichbares steuert, oder unsichtbar bleibt,
während die Sidebar bereits off-canvas ist). Auf Desktop-Breite `display:none`, braucht dort
keinen Platz -- der Suchen-Platzhalter bekommt seine volle Breite ungeschmälert; dieser
reservierte 38px-Knopf muss beim Bauen der Suche (Schritt 3) links mitgedacht werden.

Öffnet/schließt dasselbe Zustandspaar wie zuvor `#appSidebarToggle`
(`#appSidebar.mobile-open`/`#appSidebarScrim.visible`) -- Schließen per Klick auf den
Hintergrund bleibt unverändert bei `_sidebar.html`s bestehendem Scrim-Handler, der neue Knopf
synchronisiert dabei nur sein eigenes `aria-expanded`, damit es nach diesem Weg nicht fälschlich
`"true"` bleibt.

**Geprüft: ist der Umschalter unten aus 1.3.44 auf Mobilgeräten überhaupt noch sinnvoll?** Nein
-- auf Mobilgeräten gibt es kein Kollabieren im Desktop-Sinn (60px-Icon-Leiste), nur Auf/Zu der
Off-Canvas-Sidebar, und genau das übernimmt jetzt `#appTopbarMenuBtn`. `#appSidebarToggle`
blendet sich deshalb unterhalb des Umbruchpunkts vollständig aus (`.app-sidebar-toggle{display:
none}` innerhalb des bestehenden `@media(max-width:1000px)`-Blocks in `_sidebar.html`) --
zwei verschiedene Bedienungen für dieselbe Aktion nebeneinander wären verwirrender gewesen als
eine einzige, und die alte Beschriftung/Ikonografie ("Ein-/Ausklappen", drei horizontale
Striche) beschreibt auf Mobilgeräten ohnehin die falsche Handlung. Sein Klick-Handler verliert
dabei den jetzt toten `isMobile()`-Zweig (unerreichbar, da das Element selbst `display:none`
ist) -- bewusst entfernt statt als totes Code stehen zu lassen. **Bewusst NICHT** dieselbe Regel
wie die 1.3.44-Desktop-Prüfung (`.app-sidebar.collapsed .app-sidebar-toggle{display:none}`, die
bleibt unverändert abwesend/verboten -- dort geht es um das Kollabieren auf Desktop-Breite,
hier um eine komplett andere, mobile-spezifische Regel).

**Test, der genau diese Bildschirmbreiten-Invariante prüft** (`tests/test_v255_mobile_sidebar_
toggle.py`): nicht nur "der Knopf existiert irgendwo", sondern konkret, dass `#appTopbarMenuBtn`
außerhalb von `<aside id="appSidebar">` im Markup steht (die eigentliche Ursache des Fehlers),
dass er vor dem Suchen-Platzhalter steht, denselben Umbruchpunkt wie die Sidebar selbst nutzt,
dasselbe Zustandspaar toggelt wie zuvor `#appSidebarToggle`, `aria-controls`/`aria-expanded`
trägt und bei Klick auf den Hintergrund resynchronisiert, dass `#appSidebarToggle` unterhalb des
Umbruchpunkts tatsächlich verschwindet (und sein Klick-Handler den toten Zweig verloren hat,
ohne das Desktop-Kollabieren selbst anzufassen), und dass `/mobil` (damals `/vor-ort`) unverändert
ohne diesen Knopf bleibt.

### Aufräumen im Fußbereich (seit 1.3.49)

Im unteren Bereich standen noch Benutzername, "Mein Konto" und "Abmelden" -- alle drei bereits
seit Schritt 2 (1.3.45) über den Kontoknopf der Topbar erreichbar. Zwei Stellen für dasselbe
verwirren, alle drei entfernt: der untere Bereich zeigt jetzt nur noch die beiden
Schaltflächen (Hell/Dunkel, Ein-/Ausklappen) und die Versionsnummer.

- **`#appSidebarFoot` bleibt als Element bestehen**, rendert serverseitig aber für JEDEN
  Anmeldestatus leer (`{% if current_user %}...{% else %}...{% endif %}` entfällt, immer nur
  `<div class="app-sidebar-foot" id="appSidebarFoot"></div>`) -- es wird weiterhin gebraucht,
  aber nur noch für den einen verbleibenden Fall: eine Sitzung, die während des Browsens
  abläuft (Cookie verfällt, während der Tab offen bleibt), bekommt dort über
  `renderAuthFoot()`s bestehenden "nicht angemeldet"-Zweig (unverändert) ein kompaktes
  Anmeldeformular zurück, ohne die Seite neu laden zu müssen. Neue Regel
  `.app-sidebar-foot:empty{padding:0}` -- ohne sie hätte das jetzt immer leere Element trotzdem
  sein `padding:10px` behalten und eine unnötige, gepolsterte Leerstelle zwischen den beiden
  Schaltflächen und der Version aufgerissen.
- **Toter Code entfernt, nicht nur ausgeblendet**: `escHtml()` (diente ausschließlich dem
  Escapen von `display_name` beim JS-Aufbau des jetzt entfallenen Benutzernamen-Blocks),
  `bindLogout()` und die `LOGOUT_ICON`-Konstante (der einzige noch verbleibende Abmelden-Weg in
  diesem Include ist entfallen) sowie die CSS-Regeln `.app-sidebar-user`/`.app-sidebar-logout`
  (inkl. der eingeklappt-Sonderregel) -- alle hatten nach der Entfernung des SSR- UND des
  JS-gerenderten authentifizierten Fußbereichs keinen Aufrufer mehr.
- **Geprüft (wie verlangt): `/mobil` (damals `/vor-ort`) unangetastet.** `_mobile_header.html` hat einen
  komplett eigenständigen, unabhängigen Abmelde-Weg (`#mobileHeaderLogout`, eigene
  `.mobile-*`-CSS-Klassen ohne `app-sidebar`-Präfix) -- projektweiter Grep bestätigt, dass
  keine der entfernten Klassen/IDs (`app-sidebar-user`, `app-sidebar-logout`,
  `app-sidebar-account-link`, `appSidebarLogout`, `appSidebarFoot`) außerhalb von
  `_sidebar.html` selbst vorkommt.
- **Geprüft (wie verlangt): unterhalb des mobilen Umbruchpunkts.** Da `#appSidebarToggle`
  dort bereits seit 1.3.46 `display:none` ist, zeigt der untere Bereich auf einem schmalen
  Bildschirm jetzt tatsächlich nur noch die Hell/Dunkel-Schaltfläche (links ausgerichtet,
  passend zu den darüber ebenfalls linksbündigen Navigationseinträgen) und die Version darunter
  -- ein einzelner Icon-Button in einer eigenen Zeile ist ein unauffälliges, bereits an anderer
  Stelle im Projekt vorkommendes Muster (z. B. die eingeklappte Desktop-Sidebar zeigt ebenfalls
  einzelne, freistehende Icons), kein Sonderfall, der eine eigene Zentrierung o. Ä. gebraucht
  hätte. Kein echter Browser-Screenshot möglich (dieselbe, wiederholt dokumentierte
  Werkzeug-Einschränkung dieser Umgebung) -- nur strukturell geprüft.
- **Nebenbefund aus dem Auftrag**: der jetzt entfernte "Mein Konto"-Link
  (`.app-sidebar-account-link`) hatte keine eigene CSS-Regel und wäre als blau unterstrichener
  Browser-Standardlink erschienen, nicht im Design-System -- erledigt sich durch die
  Entfernung selbst. Auf Nachfrage projektweit nach demselben Muster gesucht (ein `<a>` ohne
  eigene Farb-/Unterstreichungsregel, weder über eine allgemeine `a{...}`-Regel im Datei-eigenen
  `<style>` noch über eine spezifische, tatsächlich definierte Klasse) -- vier weitere,
  unabhängige Funde, aber bewusst NICHT im selben Zug mitbehoben (anderer Ursprung, andere
  Dateien, kein Zusammenhang mit der Sidebar):
  - `account.html`: `<a href="/login">anmelden</a>` im "nicht angemeldet"-Hinweis (ohne Klasse,
    kein allgemeines `a{}` in dieser Datei).
  - `settings.html`: `<a href="/master-data#employees">Stammdaten → Mitarbeiter</a>` im
    Kalkulationsgrundlagen-Hinweistext (ohne Klasse, kein allgemeines `a{}`).
  - `service_reports.html`: der PDF-Öffnen-Link in `historyCard()` (Wartungshistorie-Panel) --
    eine zweite, unabhängige Kopie desselben Features, die (anders als die bereits über
    `.report-actions a{...}` gestylte erste Kopie) in einem unstyled `<div class="report-head">`
    landet.
  - `work_preparation.html`: der Datei-Öffnen-Link in `renderDelivery()` (Lieferschein-Tabelle)
    -- eine zweite, unabhängige Kopie desselben Features wie `deliveryTags()` (dort über
    `.delivery-tag a{...}` korrekt gestylt), hier ohne die umschließende Klasse.
  Alle vier folgen demselben Muster wie der ursprüngliche Fund: ein per JS-Template-String
  zusammengesetzter `<a>`, bei dem die passende CSS-Klasse beim Bauen vergessen wurde -- kein
  einzelner Ursprung, eher ein wiederkehrendes Risiko dieser Bauweise. Gemeldet, Behebung auf
  Rückmeldung.

#### Nachtrag (seit 1.3.50): die vier weiteren Funde behoben

Auf Rückmeldung nachgezogen -- alle vier bekommen eine allgemeine `a{color:var(--accent)}`
-Regel in ihrem eigenen `<style>`-Block, exakt das in `login.html` bereits etablierte,
einfachste Muster (recolort, behält den Standard-Unterstrich für einen normalen Inline-Text-
Link -- kein `text-decoration:none` wie bei den button-artigen Links dieses Design-Systems).
Bewusst KEINE HTML-Umstrukturierung (z. B. den `service_reports.html`-Link nachträglich in
`.report-actions` umzuhängen oder den `work_preparation.html`-Link in `.delivery-tag` zu
verpacken) -- beides hätte das Layout sichtbar verändert (Button-Optik bzw. Pill-Hintergrund
an einer Stelle, an der bisher ein einfacher Text stand), mehr als die angefragte, risikoarme
Farbkorrektur. Vor dem Schreiben jeweils per Grep bestätigt: der jeweils einzige unstyled
`<a>` in der betroffenen Datei -- alle bereits spezifischer gestylten Links (`.back`,
`.report-actions a`, `.top-actions a`, `.delivery-tag a`) bleiben durch die höhere
CSS-Spezifität ihrer eigenen Klassen unberührt, unabhängig von der Regel-Reihenfolge im
Stylesheet. Tests: `tests/test_v259_unstyled_link_audit.py`.
