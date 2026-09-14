# Changelog – DACHKONZEPTE ERP

Rückwirkend rekonstruiert aus den Entwicklungssitzungen seit Version 1.0.6 (die erste Version, ab der ein durchgehendes README pro Version vorliegt). Neueste Version zuerst. Ab 1.0.52 wird diese Datei laufend mit jeder neuen Version fortgeschrieben.

Die Versionen 1.0.57–1.0.101 wurden nachträglich aus `seit 1.0.NN`-Vermerken im Code sowie aus dem Gesprächsverlauf der jeweiligen Entwicklungssitzung rekonstruiert, nachdem diese Datei über einen langen Zeitraum nicht mitgepflegt wurde. Für folgende Versionsnummern ließ sich im Code kein zuordenbarer Vermerk mehr finden; damit hier nichts erfunden wird, bleiben sie bewusst ohne eigenen Eintrag: 1.0.60, 1.0.62, 1.0.63, 1.0.72, 1.0.73, 1.0.75–1.0.78, 1.0.80, 1.0.81, 1.0.83, 1.0.85, 1.0.86, 1.0.88, 1.0.89, 1.0.91, 1.0.93, 1.0.95, 1.0.96.

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
