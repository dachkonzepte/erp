# DACHKONZEPTE ERP – Projektkontext für Claude Code

Diese Datei fasst zusammen, was in einer langen Entwicklungssitzung mit Claude (über claude.ai)
erarbeitet wurde – Konventionen, wiederkehrende Fallstricke und der aktuelle Stand. Zweck: eine
neue Claude-Code-Sitzung soll nicht bei null anfangen, sondern die dort hart erarbeiteten Regeln
von Anfang an kennen.

**Wichtiger Hinweis zur Verlässlichkeit dieser Datei:** Sie wurde ursprünglich nicht aus dem
vollständigen lokalen Projekt erstellt, sondern aus dem Gedächtnis einer claude.ai-Sitzung und
einem Arbeits-Container, der nur die dort tatsächlich bearbeiteten Dateien enthielt. Am
09.09.2026 wurde deshalb eine vollständige Bestandsaufnahme gegen den echten Code durchgeführt
(`docs/bestandsaufnahme.md`, Anlage `docs/bestandsaufnahme_modelle.md`) – Migrationskette,
komplettes Modell-Inventar, Objekt-/Gebäudemodell, `MaintenanceContract`/`ServiceReport`
vollständig, `TimeEntry`, Plantafel, Modul-Registry, Datei-Uploads, Mobile-Tauglichkeit. Dabei
wurde u. a. eine falsche Behauptung dieser Datei korrigiert: **nicht** `bb175f455b64` ist die
älteste Alembic-Migration, sondern `2befd7907eef` ("baseline: bestehendes Schema",
02.09.2026) – acht weitere Migrationen liegen vor `bb175f455b64`. Bei Zweifeln an einer Aussage
unten zuerst in `docs/bestandsaufnahme.md` nachsehen, sonst wie bisher gegen den Code prüfen
(z. B. mit `alembic history`).

## Projektüberblick

DACHKONZEPTE ERP ist die betriebsinterne Software eines Dachdeckerbetriebs (DACHKONZEPTE
GmbH) -- deckt die komplette kaufmännische und operative Kette ab: Kundenverwaltung, Objekte/
Dachflächen, Angebot → Auftrag → Rechnung → Mahnung, Zeiterfassung und Personalplanung
(Plantafel), Wartungsverträge mit digitalen Einsatzberichten, eine reduzierte Monteursansicht
fürs Fahrzeug-Tablet, sowie neuere Module wie Betriebsmittelverwaltung, Betriebskosten-Übersicht,
Buchhaltung (Eingangsrechnungen) und einen Büro-Kalender mit Outlook-Synchronisation. Einzelner
Nutzer bzw. kleines Team (Innendienst + Monteure), ein Server, keine Mandantenfähigkeit.

Diese Datei ist bewusst schlank gehalten (Ziel: unter 2.500 Zeilen) und enthält nur, was in
JEDER Sitzung gelten muss -- verbindliche Regeln, Stack, Kernbegriffe, Produktivbetrieb,
Modulübersicht mit Archivpfaden. Die ausführliche Herleitung, Versionsverläufe und
Einzelbefunde stehen themensortiert unter `docs/archiv/` (siehe "Modulübersicht" unten) und
werden nur bei Bedarf gelesen, nicht automatisch geladen (keine `@`-Imports).

## Stand bei Übergabe

- Version: **1.9.93** (siehe `CHANGELOG.md` für die vollständige Versionshistorie; diese Zeile stand
  bis Runde 0e noch auf 1.7.6 -- maßgeblich ist immer die Datei `VERSION`)
- Stabiler Pfad: `C:\DACHKONZEPTE-ERP\1 Prototype\`
- Das komplette visuelle Redesign (anpassbare Akzentfarbe, Hell-/Dunkel-Theme, eckige
  Eingabefelder, einfarbige Sidebar-Icons) ist auf **alle** Templates ausgerollt (1.0.97–1.0.100,
  siehe Changelog) – neue Seiten müssen diesem Design-System folgen, siehe unten.
- Ausführliche Migrationsketten- und Testlauf-Historie (Version für Version nachvollziehbar): `docs/archiv/versionsverlauf.md`. Vollständige Versionshistorie 1.1.0–1.6.0 ("Neu seit ..."-Kette): `docs/archiv/chronik-1.1-1.6.md`. Ab 1.6.0 siehe `CHANGELOG.md` für die laufende Historie.

## Produktivbetrieb (seit 14.09.2026)

Das ERP läuft seit diesem Tag auf einem echten Server, nicht mehr nur lokal auf Tobias'
Windows-Rechner. Das ändert die Rahmenbedingungen für alles, was künftig gebaut wird -- dieser
Abschnitt hält sie fest, damit eine neue Sitzung nicht erst am Betrieb selbst lernen muss, was
davor nur Theorie war.

### Die zwei Umgebungen

- **Entwicklung**: Windows-Rechner (`C:\DACHKONZEPTE-ERP\1 Prototype\`), weiterhin der Ort, an
  dem gebaut und getestet wird. **Ab sofort mit der lokalen PostgreSQL-Instanz statt SQLite**
  (siehe Abschnitt "PostgreSQL-Umstieg" unten für die portable, admin-rechte-freie Instanz),
  damit ein Postgres-spezifischer Fehler hier auffällt und nicht erst auf dem Server -- SQLite
  bleibt als schneller Einstieg für einen frischen Checkout ohne installiertes PostgreSQL
  nutzbar, ist aber nicht mehr das, wogegen ernsthaft entwickelt werden soll.
- **Produktion**: ein Ionos-VPS, Ubuntu, 2 Kerne, 4 GB RAM. PostgreSQL, Nginx als Reverse Proxy,
  HTTPS über Let's Encrypt, `gunicorn` als systemd-Dienst, erreichbar unter
  `app.dachkonzepte.gmbh`.

**Der Code kommt ausschließlich über Git dorthin. Niemals Dateien von Hand kopieren** -- jede
Abweichung zwischen dem, was lokal committet wurde, und dem, was tatsächlich auf dem Server
liegt, ist ab jetzt ein echtes Risiko (überschriebene, nie committete Änderungen; ein Server-
Stand, den `git log` nicht erklären kann), nicht nur ein theoretisches.

### Was beim Bauen zu beachten ist

- **Speicherbudget.** Der Server hat 4 GB RAM -- beim Entwickeln auf einem deutlich größeren
  Rechner fällt Speicherverbrauch nicht auf, auf dem Server schon. Beim ersten Anlauf wurden die
  Arbeitsprozesse bei 809 MB vom System abgeschossen (OOM). Bei allem, was größere Datenmengen
  im Speicher hält -- PDF-Erzeugung mit vielen Fotos (siehe `service_report_pdf.py`), Importe
  (Adressimport, XML-Import), Massenabfragen ohne Begrenzung -- den Verbrauch mitdenken, nicht
  erst auf dem Server merken.
- **Umgebungsvariablen statt fest verdrahteter Pfade/Werte.** Alles, was der Server anders
  macht als die Entwicklungsumgebung, gehört in eine Umgebungsvariable (Muster: `ERP_SECRET_KEY`,
  `ERP_DATA_DIR`, `DATABASE_URL`, jetzt auch `ERP_ENV`, siehe unten) -- nie ein Pfad oder Wert,
  der nur unter Windows bzw. nur lokal stimmt. Die vorhandenen Variablen sind in `.env.example`
  dokumentiert, das ist die verbindliche Liste.
- **Datenmenge wächst.** Heute (Stand des ersten Datenumzugs) 3040 Zeilen über alle Tabellen,
  162 Kunden. Das ist der Anfang, nicht der Bestand, mit dem langfristig geplant werden darf --
  eine Abfrage, die lokal an einer kleinen Datenmenge schnell ist, muss das bei tausenden Kunden/
  Aufträgen/Zeitbuchungen nicht bleiben. Bei neuen, potenziell großen Abfragen (fehlender Index,
  `N+1`-Nachladen, ungefilterte Listen) das im Kopf behalten, nicht erst wenn es spürbar wird.

### Die Serverumgebung im Einzelnen

| Was | Wo |
|---|---|
| Projektordner | `/home/tobias/erp` |
| Datenordner (`ERP_DATA_DIR`, außerhalb von Git) | `/home/tobias/erp-data` |
| Umgebung | `/home/tobias/erp/.env` |
| Datenbank | `dachkonzepte` (produktiv), `spielwiese` (Probe, siehe unten) |
| Dienst | `erp.service`, `gunicorn -w 2 --timeout 120` |
| Sicherung | `/home/tobias/backup.sh`, täglich 2 Uhr UTC, 14 Tage Aufbewahrung; sichert `erp-data` vollständig (Betreiberangabe 05.10.2026) |
| Einspielen | ausschließlich `/home/tobias/update.sh` (auf dem Server, nicht im Repo; probt eine Migration selbst gegen `spielwiese`), nie einzelne `alembic`-Befehle -- auch nicht für die Probe |
| Notfallskripte | `scripts/reset_admin_2fa.py`, `scripts/migrate_sqlite_to_postgres.py`; erstes Konto (seit 1.8.130): `scripts/erstes_konto.py`; nur lesend (seit 1.9.119): `scripts/pruefe_stornos.py` (hebt jeder Storno sein Original genau auf?), seit 1.9.125 `scripts/pruefe_projektstatus.py` (passt der gespeicherte Projektstatus zur Ableitung?), seit 1.9.142 `scripts/pruefe_outlook.py` (Stand des Outlook-Abgleichs je Postfach, wartende und doppelte Termine, ganztägige aus dem ERP) |
| Zeitzone | `Etc/UTC` (`timedatectl`) -- Datum und Uhrzeit deshalb nur über `app/berlin_time.py`, Regel 20 |

**Korrigiert (KI-Fundament-Runde, seit 1.6.2)**: diese Datei behauptete hier bisher fälschlich
"ein Arbeitsprozess, kein `--workers 2+`" -- am 22.09.2026 direkt gegen den echten `ExecStart`
der systemd-Unit auf dem VPS verifiziert: **zwei** Arbeitsprozesse (`-w 2`), explizites
`--timeout 120`. Woher die falsche Behauptung kam, lässt sich nicht mehr rekonstruieren (keine
Quellenangabe in der ursprünglichen Fassung) -- sie wurde nie gegen den echten Server geprüft,
bis zu diesem Zeitpunkt. Zwei Arbeitsprozesse bedeuten zwei unabhängige asyncio-Event-Loops mit
je eigenem Starlette-Threadpool (kein gemeinsamer Speicher, keine gemeinsame Warteschlange) --
die Gesamtkapazität ist dadurch GRÖSSER als bei einem Prozess, aber eine blockierte Event-Loop
legt jetzt "nur" die Hälfte der Kapazität lahm, nicht alles (siehe "KI-Fundament" ->
"Untersuchung" unten für die konkrete Auswirkung). Jede an dieser Stelle vorher gemachte
Speicherbudget-Begründung ("ein Worker, weil jeder zusätzliche den Speicherbedarf verdoppelt")
war demnach ebenfalls nicht (mehr) zutreffend für den tatsächlich laufenden Server -- ob das
4-GB-Budget mit zwei Workern tatsächlich knapp ist, ist an dieser Stelle nicht neu untersucht
worden, nur die Tatsachenbehauptung selbst korrigiert.

### Der Weg einer Änderung auf den Server

Lokal bauen, volle Testsuite, bei Oberflächenänderungen zusätzlich ein Klicktest im Browser.
Committen -- der Betreiber pusht (etablierte Praxis dieser Sitzungen: Claude Code committet,
aber pusht nie ohne ausdrückliche Aufforderung). Auf dem Server: sichern, `git pull`, Abhängigkeiten,
Migrationen, Dienst neu starten.

**Seit 05.10.2026 (Betreibervorgabe): eingespielt wird nur mit `/home/tobias/update.sh`, nie mit einzelnen
`alembic`-Befehlen.** Das Skript liegt auf dem Server, nicht im Repo, und probt eine Migration selbst zuerst gegen
`spielwiese` (Betreiberangabe 05.10.2026, in CLAUDE.md seit 1.8.54) -- eine Anleitung oder ein Bericht nennt deshalb
`update.sh`, nicht die Einzelschritte und keinen eigenen Probe-Befehl. `backup.sh` sichert `erp-data` vollständig (auch die
Ablagen unter `ERP_DATA_DIR`, z. B. `acceptance_documents`). Die Abfolge unten ist die frühere Handabfolge
(Stand 1.3.42) und bleibt als Nachweis dessen, was ein Einspielen leisten muss (Sicherung, Umgebung laden,
Migration, `alembic current` als Beleg, Neustart) -- nicht zum Abtippen.

**Korrigiert seit 1.3.42, nach einem realen Vorfall beim Ausliefern von 1.3.38–1.3.41** (siehe
"Zwei Vorfälle beim Ausliefern von 1.3.38–1.3.41" unten für die volle Herleitung) -- exakt diese
Abfolge, keine Zeile auslassen:

```bash
/home/tobias/backup.sh
cd /home/tobias/erp
git pull
set -a; source .env; set +a
.venv/bin/pip install -r requirements.txt
.venv/bin/alembic upgrade head
.venv/bin/alembic current
sudo systemctl restart erp
```

Die vierte Zeile (`set -a; source .env; set +a`) lädt `DATABASE_URL`/`ERP_SECRET_KEY`/`ERP_ENV`
usw. tatsächlich in die Shell-Umgebung -- ohne sie fiel `alembic upgrade head` bisher
stillschweigend auf einen falschen Wert zurück (siehe Vorfall 1 unten); seit 1.3.42 bricht
alembic statt eines stillen Rückfalls mit einer klaren Fehlermeldung ab, wenn `DATABASE_URL`
fehlt. Die siebte Zeile (`alembic current`) ist der einzige tatsächliche Nachweis, dass die
Migration gegriffen hat -- "keine Fehlermeldung gesehen" ist kein Ersatz dafür, siehe Vorfall 1.

Bei Schemaänderungen läuft die Migration vorher zusätzlich einmal gegen `spielwiese` (die
Probe-Datenbank auf demselben Server, nicht die lokale, portable Instanz aus der Entwicklung) -- das erledigt
`update.sh` selbst, kein einzelner `alembic`-Befehl. Bis 1.8.53 stand hier ein Befehl
`DATABASE_URL=…/spielwiese alembic upgrade head` zum Abtippen und seit 1.8.51 die offene Frage, ob die Probe über
`update.sh` laufen soll; beides ist mit der Betreiberangabe vom 05.10.2026 erledigt.

### Was das für Migrationen heißt

Eine Migration läuft künftig auf echten Produktivdaten, nicht mehr nur auf einer leeren
Testdatenbank oder Tobias' lokaler Entwicklungskopie. Der Rückweg ist ein Backup-Restore, keine
Kleinigkeit mehr, die man nebenbei rückgängig macht.

Prüfe künftig bei **jeder** Migration, bevor sie auf den Server geht:

- **Läuft sie tatsächlich gegen PostgreSQL?** Kein `datetime('now')` (SQLite-spezifisch), keine
  nackten Boolean-Literale `1`/`0` in rohem SQL (unter PostgreSQL strikt typisiert, unter
  SQLite stillschweigend als Integer durchgewunken) -- siehe Abschnitt "PostgreSQL-Umstieg"
  unten für die Fehlerklasse im Detail.
- **Ist sie auf einem Bestand mit echten Daten getestet, nicht nur auf einer leeren
  Datenbank?** Eine leere Datenbank verdeckt genau die Fehler, die an echten Daten auffallen --
  siehe unten.
- **Kann sie rückgängig gemacht werden, und stellt `downgrade()` den tatsächlichen Vorzustand
  wieder her?** Nicht nur "irgendein" Vorzustand -- siehe die `5c8715dba230`/`0064c87051aa`-
  Migrationen (Abschnitt "Aufräumen nach dem PDF-Umbau") als Vorbild: ihr `downgrade()` liest die
  zuletzt tatsächlich vorhandenen Werte vor dem Schreiben aus, nicht nur Code-Standardwerte.
- **Ist sie tatsächlich gelaufen?** Seit 1.3.37 ist `Base.metadata.create_all()` im
  Produktivbetrieb abgeschaltet (`ERP_ENV`) -- gewollt, aber mit einer echten Konsequenz: eine
  übersprungene oder fehlgeschlagene Migration wird seither nicht mehr stillschweigend
  überbrückt (wie es unter SQLite/lokal noch geschähe), sondern legt das System beim nächsten
  Zugriff auf eine fehlende Spalte/Tabelle sofort lahm. `alembic upgrade head` ohne Fehlermeldung
  ist deshalb kein ausreichender Nachweis -- siehe Vorfall 1 im nächsten Abschnitt, in dem genau
  das passierte, weil die Migration in Wirklichkeit gegen die falsche Datenbank lief. Der Ablauf
  ("Der Weg einer Änderung auf den Server" oben) endet deshalb ausdrücklich mit `alembic
  current`, nicht mit `alembic upgrade head`.

**Warum das keine abstrakte Vorsicht ist, sondern eine bereits gemachte Erfahrung**: die
Migration `e057d15af828` war seit ihrer Erstellung eine leere Hülle (nur `pass`/`pass`) --
entstanden, weil `Base.metadata.create_all()` beim App-Start die Tabellen
`invoices`/`invoice_items` bereits real angelegt hatte, bevor `alembic revision --autogenerate`
lief, wodurch Autogenerate keinen Unterschied mehr fand. Unter SQLite (und lokal, wo
`create_all()` bis zu diesem Server-Rollout bei jedem Start nachzog) blieb das unbemerkt --
erst eine frische PostgreSQL-Datenbank
ohne dieses Sicherheitsnetz hätte die Kette mit `NoSuchTableError` abgebrochen. Siehe Abschnitt
"PostgreSQL-Umstieg: Migrationskette repariert" unten für die vollständige Herleitung und die
1.3.35-Reparaturrunde, die das (und sechs weitere, dialektbedingte Fixes) behoben hat, bevor
überhaupt umgezogen wurde. Diese Erfahrung ist der Grund für die drei Prüfpunkte oben -- nicht
Vorsicht um ihrer selbst willen.

### Zwei Vorfälle beim Ausliefern von 1.3.38–1.3.41, beide behoben (seit 1.3.42)

**Vorfall 1: `alembic upgrade head` lief ohne geladene Umgebungsvariablen, migrierte dadurch die
falsche Datenbank, und der Fehler ging unbemerkt unter.** Beim Einspielen von 1.3.38 bis 1.3.41
lief `alembic upgrade head` auf dem Server, ohne dass zuvor `.env` geladen wurde -- der
Bereitstellungsablauf hatte genau diesen Schritt verloren (siehe die korrigierte Abfolge oben).
`alembic/env.py` importierte `DATABASE_URL` bis dahin aus `app.database` -- dort ist ein stiller
Rückfall auf SQLite eine bewusste, für die lokale Entwicklung gedachte Bequemlichkeit
(`os.getenv("DATABASE_URL", "sqlite:///...")`). Ohne geladene Umgebung griff genau dieser
Rückfall auch beim Deployment: `alembic upgrade head` lief scheinbar fehlerfrei durch, migrierte
aber nicht `dachkonzepte`, ohne das an dieser Stelle sichtbar zu machen. Aufgefallen ist es erst,
als eine fehlende Spalte jede Seite mit 500 beantwortete -- die Datenbank blieb auf `1b55170709a6`,
dem Stand vor dem gesamten Umzug.

Behoben: `alembic/env.py` liest `DATABASE_URL` jetzt direkt über `os.environ.get(...)`, nicht
mehr über den bereits mit einem Vorgabewert versehenen Import aus `app.database` -- fehlt die
Variable, bricht alembic mit einer klaren, erklärenden Fehlermeldung ab, statt still auf
irgendeinen Wert zurückzufallen. **Unbedingt, unabhängig von `ERP_ENV`**: eine an
`ERP_ENV=="production"` gekoppelte Prüfung hätte hier nicht geholfen -- fehlt die Umgebung
komplett, fiele `ERP_ENV` selbst ebenso auf seinen Entwicklungs-Vorgabewert zurück, die Prüfung
griffe also nie genau dann, wenn sie gebraucht wird. Das ist eine bewusste, unbedingte Abweichung
von der bisherigen, lokal etablierten Praxis dieser Sitzungen (alembic ohne gesetzte Variablen
laufen zu lassen und sich auf denselben SQLite-Rückfall wie die App zu verlassen) -- lokal muss
`DATABASE_URL` für einen alembic-Aufruf ab jetzt ausdrücklich gesetzt werden, z. B.
`DATABASE_URL=sqlite:///./dachkonzepte_erp.db alembic upgrade head` (oder die lokale
Postgres-Verbindungszeichenfolge). Zusätzlich verlangte der Vorfall die oben bereits
beschriebene Korrektur des Bereitstellungsablaufs selbst (`set -a; source .env; set +a` UND
`alembic current` waren beide verlorengegangen).

**Vorfall 2: ein fehlgeschlagener Logo-Upload legte danach jede Seite lahm, einschließlich der
Anmeldeseite.** Nachdem die nachgeholte Migration griff, führte das Hochladen eines Logos dazu,
dass jede Seite mit 500 antwortete. Bei der Untersuchung ließ sich der genau gemeldete Ablauf
(eine Funktion `save_logo()`, bestimmte Zeilennummern in `company_logo.py`) im tatsächlichen Code
nicht wortgleich wiederfinden -- vermutlich eine sinngemäße statt einer wörtlichen Beschreibung
des Vorfalls (weder `save_logo` noch der genannte Fehlertext kamen im Projekt vor). Der reale, im
Code tatsächlich vorhandene Risikobereich war aber ebenso ernst und traf denselben Kern der
Meldung: (1) der Upload-Endpunkt (`POST /api/settings/general/logo`) prüfte bis dahin
ausschließlich den vom Client mitgeschickten `content_type`-Header -- frei wählbar, kein
Nachweis des tatsächlichen Dateiinhalts, eine beliebige Datei mit vorgetäuschtem
`image/png`-Header wäre durchgekommen; (2) KEINER der vier Jinja-Globals, die auf jeder Seite
laufen (`get_theme()`, `is_module_enabled()`, `sidebar_logo_url()`, `sidebar_logo_height_px()`
in `app/routers/pages.py`), fing eine Ausnahme ab -- ein DB-Zustand, der eine davon zum Werfen
brachte (z. B. genau die in Vorfall 1 beschriebene fehlende Spalte, oder eine kaputte
Logo-Referenz), schlug ungefiltert durch und beantwortete dadurch JEDE Seite mit 500,
einschließlich `login.html` (das `get_theme()` direkt für seine Akzentfarbe aufruft, nicht nur
über das dort gar nicht eingebundene `_sidebar.html`) -- niemand konnte sich mehr anmelden, um es
zu reparieren. Notbehelf war `UPDATE general_settings SET logo_filename = NULL` direkt in der
Datenbank.

Behoben, drei Teile:
1. `company_logo.py::validate_logo_image()` prüft jetzt VOR jeder Persistierung (vor
   `replace_logo()`, vor dem Setzen von `logo_filename`, vor `db.commit()`), ob Pillow die Datei
   tatsächlich öffnen/dekodieren kann -- SVG ausgenommen (Pillow kann SVG grundsätzlich nicht
   öffnen, das ist dort kein Fehler). `routers/settings.py::upload_company_logo()` fängt ein
   daraus resultierendes `ValueError` ab und antwortet mit **400** und einem verständlichen Text,
   nicht mit 500.
2. **Alle vier** Jinja-Globals in `app/routers/pages.py` sind jetzt gegen jede Ausnahme
   abgesichert (`try/except Exception`, über einen neuen `logger` protokolliert, mit sicherem
   Rückfallwert): `get_theme()` → Standard-Akzentfarbe (`#0d9488`), `is_module_enabled()` →
   `True` (dieselbe Opt-out-Philosophie wie im Normalfall, siehe `app/modules.py`),
   `sidebar_logo_url()` → `None` (Rückfall auf den Schriftzug), `sidebar_logo_height_px()` →
   `DEFAULT_SIDEBAR_LOGO_HEIGHT_PX`. **Prinzip, nicht nur Einzelfall-Fix**: ein Jinja-Global, der
   auf jeder Seite läuft, darf NIE eine Ausnahme werfen -- ein DB-Zustand, der das auslöst, darf
   höchstens den betroffenen Teil der Seite auf einen Rückfallwert reduzieren, niemals die ganze
   Seite (und damit möglicherweise auch die Anmeldeseite) unerreichbar machen. Geprüft, ob es
   weitere solche Globals gibt (`grep "env.globals\["` über `app/`): nein -- diese vier sind die
   einzigen mit Datenbankzugriff, alle vier sind jetzt abgesichert.
3. Tests ergänzt (`tests/test_v108_login_lockout_and_logging.py`-Nachbarschaft bzw. neue Datei,
   siehe "Testen" unten) für: den Upload-Endpunkt mit einer nicht dekodierbaren Datei (400, nicht
   500), jedes der vier Globals unter einer simulierten, fehlschlagenden Funktion (Rückfall
   greift, keine Ausnahme verlässt die Funktion), und einen Ende-zu-Ende-Test, dass eine
   `general_settings`-Zeile in einem ungültigen Zustand das Rendern echter Seiten nicht verhindert.

### Zwei Nebenbefunde vom Server, beide behoben

1. **`psycopg` (Version 3) vs. `psycopg2` -- Verwechslungsgefahr in der Verbindungszeichenfolge.**
   `requirements.txt` installiert ausschließlich `psycopg[binary]` (Version 3, SQLAlchemy-
   Dialektname `psycopg`) -- beim erstmaligen Aufsetzen des Servers wurde die
   Verbindungszeichenfolge trotzdem mit `postgresql+psycopg2://` angelegt (der weithin bekanntere,
   ältere Treibername), was zu einem Importfehler führte, da das dafür nötige, separate Paket
   `psycopg2` nirgends installiert war. Behoben durch `psycopg2-binary`, von Hand
   nachinstalliert -- funktionierte, aber ein zweiter, in `requirements.txt` nirgends
   dokumentierter Treiber, der bei einer künftigen Neuinstallation wieder fehlen würde. Jetzt
   vereinheitlicht: `requirements.txt` trägt einen erklärenden Kommentar direkt an der
   `psycopg`-Zeile, `.env.example` erklärt explizit, dass die Verbindungszeichenfolge
   `postgresql+psycopg` lauten muss und **nicht** `postgresql+psycopg2` -- mit einem Verweis auf
   genau diesen Vorfall. `psycopg2-binary` kann auf dem Server bei Gelegenheit entfernt werden,
   sobald die Verbindungszeichenfolge dort korrigiert ist (das ist eine Server-Administrations-
   aufgabe, kein Teil dieser Änderung).
2. **Ein Microsoft-365-Client-Secret ließ sich nach dem Umzug nicht mehr entschlüsseln.** Der
   gespeicherte Wert stammt aus einer Zeit mit einem anderen `ERP_SECRET_KEY`/einer anderen
   `data/.erp_secret` als der, die jetzt tatsächlich gilt -- Entschlüsselung schlägt seither mit
   dem in `app/crypto.py::decrypt_secret()` dokumentierten `ValueError` fehl. **Daraus folgt eine
   dauerhafte Regel, nicht nur eine Randnotiz: `data/.erp_secret` darf niemals gelöscht oder durch
   einen neuen, zufällig erzeugten Wert ersetzt werden, solange verschlüsselte Werte (SMTP-
   Passwort, Microsoft-365-Client-Secret, TOTP-Geheimnisse) in der Datenbank stehen** -- jeder
   dieser Werte wird mit genau diesem einen Schlüssel verschlüsselt (`app/crypto.py`, abgeleitet
   von `secret_key()` in `app/auth.py`) und wird ohne ihn unwiederbringlich unlesbar, nicht nur
   vorübergehend. Auf einem Server, auf dem `ERP_SECRET_KEY` als Umgebungsvariable gesetzt ist
   (siehe `.env.example`), gilt dasselbe für diese Variable -- sie darf sich nach dem ersten
   Verschlüsseln eines Werts nicht mehr ändern. Der bereits betroffene Wert selbst lässt sich
   nicht nachträglich reparieren (der alte Schlüssel ist verloren) -- ein Administrator muss das
   Microsoft-365-Client-Secret einmalig über Einstellungen → E-Mail-Versand neu eintragen.

## Stack & Struktur

- **Backend:** FastAPI, SQLAlchemy 2.0, Alembic, Pydantic, ReportLab
- **Frontend:** Jinja2-Templates mit eingebettetem, framework-losem JavaScript (kein React/Vue) –
  jede Seite ist eine einzelne `.html`-Datei mit `<style>` und `<script>` direkt darin
- **Datenbank:** PostgreSQL produktiv (seit 14.09.2026, siehe Abschnitt "Produktivbetrieb"
  oben) und seither auch in der lokalen Entwicklung Standard, statt der früher rein lokalen
  SQLite-Datei -- SQLite bleibt als schneller Einstieg für einen frischen Checkout ohne
  installiertes PostgreSQL nutzbar (`DATABASE_URL`-Standardwert), ist aber nicht mehr das,
  wogegen ernsthaft entwickelt werden soll
- **Tests:** pytest, Dateien unter `tests/test_vNNN_thema.py` – die Nummer bezieht sich lose auf
  die Version, in der das Feature entstand
- **Layout:** `app/*.py` enthält die Geschäftslogik modulweise (z. B. `projects.py`, `invoices.py`,
  `orders.py`, `reminders.py`, `email_sending.py`), `app/routers/*.py` die dazugehörigen
  FastAPI-Endpunkte (aus `main.py` in Version 1.0.7 herausgezogen), `app/templates/*.html` die
  Oberfläche
- **Design-System (seit 1.0.97, auf alle Seiten ausgerollt):** die Seiten nutzen dieselben CSS-Variablen (`--accent`, `--bg`,
  `--card`, `--ink`, `--muted`, `--line`, `--field-border(-hover)`, `--soft`, `--danger(-soft)`, `--warning(-soft)`,
  `--success(-soft)`, `--info(-soft)`) -- **seit 1.9.5 nur noch zentral** in `app/static/ds/ds-alte-namen.css` (über `_ds_kopf.html`),
  dort auf die `--ds-*`-Werte gelegt; bis 1.9.4 trug jede Seite eine Kopie der Palette im eigenen `:root`, `--accent` aus der
  Akzentfarbe der Einstellungen. Doppelnamen (`--accent`, `--danger`, `--warning`, `--success`, `--info`) stehen zentral für die
  Textfarbe; als Fläche (Hintergrund, Rahmen, Umriss, Schatten) nimmt eine Seite direkt den Flächenwert (`--ds-aktion`, `--ds-fehler`,
  `--ds-warn-text`, `--ds-ok`, `--ds-info`). Eine Seite definiert keinen alten Namen und keinen festen alten Farbwert
  (`tests/test_v442_alte_farbnamen.py`). Dazu ein FOUC-Vermeidungs-Script vor dem `<style>`-Block. Bis 1.9.29 eckige Ecken durchgängig (seit 1.9.30
  Karten mit `var(--ds-ecke-karte)`, siehe Stufe 2 unten), keine farbige Kopfleiste – Seitentitel/Aktionen stattdessen in einer normalen
  Karte. `settings.html` als Referenzvorlage für Feldlayout, Buttons, Status-Meldungen.
- **Neues Design-System „Schiefer & Signal“ (seit 1.8.127, Redesign Stufe 1):** `app/static/ds/ds.css`
  mit Tokens `--ds-*` (hell und dunkel; seit 1.8.155 Firmengrün `--ds-aktion*` als Hauptaktion, Signal nur „wartet auf dich“) und selbst gehosteten Schriften (Archivo, IBM Plex Sans, IBM Plex Mono), über
  `_ds_kopf.html` in jeder Seite eingebunden -- Regel 37, `docs/archiv/redesign.md`. **Stufe 2 „Rahmen“ (seit 1.8.161)**: Entscheidungen für
  die ganze Stufe -- Hauptaktion in `--ds-aktion`, die Akzentfarbe aus den Einstellungen färbt die Oberfläche nicht mehr (App-Symbol bleibt
  vorerst); Ecken 10/12 px, Tablet 12/16 px; Seitentitel 30 px, Tablet 26 px; Leiste dunkel in beiden Modi mit vier Gruppen;
  Formularseiten bekommen den Rahmen; Einsatzbericht und Konto der Monteure im Monteursrahmen; oben links in Leiste und Monteurskopf fest die Bildmarke (`_bildmarke.html`, seit 1.8.165) auf weißer Kachel, nie ein hochgeladenes Logo. Grundregeln einer umgezogenen Seite in
  `app/static/ds/ds-basis.css`, nur unter `.ds-seite` (die Seite setzt die Klasse beim Umzug an ihr `<body>`); gemeinsamer Seitenkopf als
  Makro `teile/seitenkopf.html` mit `_seitenkopf.html` (`seitenkopf()`), Menüs über `_menue.html` (`dsMenue()`); der Status im Kopf nur
  über `statusKennzeichen()` aus `_statuskennzeichen.html` (seit 1.9.9: Status -> Text und Farbe an einer Stelle, ein neuer Status kommt dort hinein, `tests/test_v445_statuskennzeichen.py`). Jede Seite mit Leiste
  beginnt mit `{% set bereich = "…" -%}` -- die Leiste markiert danach ihren Eintrag (seit 1.8.162); Wächter `tests/test_v441_rahmen_baustein.py`.
  **Umgezogen** (`UMGEZOGEN` dort): seit 1.9.3 die Prüfvorlagen als Pilot, seit 1.9.7 die 15 Seiten der Gruppe „Titelzeilen und Titelkarten“ (Kopf, Links in `--ds-link`, Fokus in `--ds-fokus`; Strukturtest `test_umgezogene_seite_hat_den_gemeinsamen_kopf`), seit 1.9.10 die 7 Seiten der Gruppe „Datensatz mit Pfad“ (Pfad mit den Rückwegen, Kennung, Status über `statusKennzeichen()`, „Löschen“ im Menü; ein Menüeintrag, der nicht gilt, trägt `hidden`, nie die Klasse `.hidden`; `tests/test_v446_datensatzkopf.py`), seit 1.9.13 die Rechnung (Pfad bis zum Auftrag, Kennung = Nummer oder „ohne Nummer“, Kennzahlen im Kopf über den Teil `kennzahlen` des Makros, neben der grünen Hauptaktion höchstens eine neutrale Nebenaktion), seit 1.9.18 das Angebot (LV-Editor; Variante `breit` des Makros: Kennzahlen und Aktionen unter der Titelzeile), seit 1.9.21 die 3 Seiten mit Untermenü links (Kopf über Menü und Inhalt, ohne Pfad) und die 5 mit Zurück-Link und Karte (der Zurück-Link als Pfad; `tests/test_v454_untermenue_und_karte.py`), seit 1.9.22 Stammdaten-Formular und Leistung im Rahmen (Leiste, Kopfzeile, Pfad bis zur Seite, im Kopf „Abbrechen“ neutral und „Speichern“ grün, der Knopf unten bleibt; `tests/test_v455_formularseiten_im_rahmen.py`; seit 1.9.23 fragt „Abbrechen“ „Änderungen verwerfen?“, nur bei ungespeicherten Änderungen, `_abbrechen.html`), seit 1.9.24 Anfragen und Arbeitsvorbereitung (Pfad über Projekt und Auftrag, Status der Arbeitsvorbereitung über die Gruppe `arbeitsvorbereitung`), seit 1.9.25 die Monteursseiten Checkliste, Checklisten zum Auftrag, Objekt, Betriebsmittel der Monteurin (im Monteursrahmen Variante `tablet` des Makros: Pfad 15 px, Titel 26 px, Knöpfe 48 px -- ebenso Einsatzbericht und Konto der Monteurin; `tests/test_v457_monteursseiten.py`), seit 1.9.27 Anmeldung und Sperrseite (über dem Kopf die Bildmarke mit Schriftzug aus `_marke.html`; die Sperrseite zeigt die allgemeine Meldung der Rollenprüfung `ROLLE_NICHT_VERFUEGBAR` nicht, `tests/test_v458_anmeldung_und_sperrseite.py`; seit 1.9.28 nennt kein sichtbarer Text und keine Meldung eine interne Datei, sondern sagt, was zu tun ist -- `tests/test_v459_keine_internen_dateien.py`). **Stufe 2 abgeschlossen mit 1.9.29**: jede Seite steht in `UMGEZOGEN` oder in `AUFGESCHOBEN` mit Stufe und Grund („Heute“ und „Meine Zeiten“ -> 4 -- „Meine Zeiten“ ersetzt seit 1.9.59 Zeiterfassung der Monteure und Stundenzettel; Projektmappe und Auftrag seit 1.9.129 als Akte umgezogen, die Kundenakte seit 1.9.137; Kalender, Plantafel -> 6; Neues Projekt, Neues Angebot -> 7), Wächter `test_jede_seite_umgezogen_oder_aufgeschoben`; eine neue Seite kommt umgezogen dazu oder mit Stufe und Grund in die Liste. **Seit 1.9.30 Karten mit Ecken** auf allen Seiten: jede Karte trägt `border-radius: var(--ds-ecke-karte)` (12 px), im Monteursrahmen legt `_mobile_header.html` den Wert auf `--ds-ecke-tablet-karte` (16 px); was Karte ist und was nicht (Knöpfe, Felder, Kennzeichen, Raster), steht in `tests/test_v460_ecken_der_karten.py` -- eine neue umrandete Fläche kommt dort in eine der beiden Listen -- `.ds-seite` am `<body>`, Seitenkopf über das Makro, eigene
  Farben nur über `--ds-*` (keine Akzentfarbe mehr);
  in `ds-basis.css` steht seit 1.9.4 jeder Selektor ganz in `:where(…)` (Gewicht null): die Grundregeln gelten für alle Elemente, jede
  Klasse überstimmt sie (ersetzt „nur ohne Klasse“, 1.9.3).
- **Stufe 4 „Monteurin“ (seit 1.9.33):** seit 1.9.45 ist `/mobil` die Seite „Heute“ nach den Vorlagen
  `bildgrundlage/entwurf-stufe4/heute-*.html` (Daten nur aus `app/heute.py`, Schlüssel `heute` in `GET /api/field-view/today`; die Seite
  rechnet nichts nach); Reiter und Pfad-Anfang der Seiten darunter heißen „Heute“ (Adresse bleibt). Seit 1.9.58 startet „Heute“ auch
  mit Tätigkeit und für die Kolonne („⋮“ in „nichts läuft“); Zeitart-Kacheln quer 3, hoch 2 Spalten. Seit 1.9.59 ersetzt „Meine Zeiten“
  (`/mobil/zeiten`, `mobil_zeiten.html`, Daten aus `app/meine_zeiten.py`) Zeiterfassung und Stundenzettel der Monteurin; Reiter „Heute ·
  Meine Zeiten“, die alten Adressen leiten weiter; Klicktest `klicktest_meine_zeiten.py`; seit 1.9.86 nennt die Vorwahl aus der Adresse ihren
  Auftrag auch außerhalb der Liste („Nummer · Titel (Auftrag abgeschlossen)“, `vorwahl` nur bei Zugang, `tests/test_v507_vorwahl_zeile.py`). Seit 1.9.60 trägt die Monteurin nur mit Von und
  Bis nach (`app/permissions.py::zeit_nur_mit_von_bis()`, Server 422 für eine reine Dauer), auch im Einsatzbericht; seit 1.9.63 auch der
  Kolonnenführer für die Kolonne (eine Von/Bis-Angabe, Pause und Rundung je Mitglied nach seinem Tag über
  `app/time_tracking.py::kolonne_rechnen()`, Vorschau je Mitglied, `tests/test_v489_kolonne_von_bis.py`). Seit 1.9.65 bleibt in den
  Dialogen des Monteursrahmens die Knopfleiste unten im Bild (`position:sticky`, `tests/test_v491_dialog_knopfleiste.py`); seit 1.9.83 steht
  die Meldung eines Dialogs darin über den Knöpfen (`flex:1 0 100%`). **Seit 1.9.67** steht
  der Einsatzbericht auf `/service-reports/{id}` (`service_report.html`, umgezogen) in fünf Schritten nach den Vorlagen `bericht-*`: Kopf mit
  „⋮“, Schritte mit Haken, „Noch offen“ rechts bzw. hoch als Leiste unten, Fokus bleibt nach dem Speichern (`teilErsetzen()`), Ziele ≥ 48 px;
  die Seite des Auftrags (`service_reports.html`, „Einsatzberichte“) listet die Berichte, legt an und zeigt der Monteurin statt der
  Buchungskarte „Zeit nachtragen“; `?report=` leitet weiter (`dk_ohne_seite` mit Benutzer und Anfrage). Klicktest
  `klicktest_bericht_schritte.py`. Seit 1.9.72 hat Schritt 5 unten eine feste Leiste („Zurück“, „Fehlt: …“, „Bericht abschließen“, bei
  1280 × 620 ohne Bildlauf), „⋮“ eines Prüfpunkts steht oben rechts in seiner Titelzeile; seit 1.9.73 zeigt „Einsatzberichte“ den Status
  über `statusKennzeichen()` (`tests/test_v496_berichtsliste_status.py`). Seit 1.9.75 legt die Monteurin auf „Heute“ auch ohne Einsatz einen
  Bericht an („Bericht anlegen“ in der leeren Karte, mit Einsatz „Bericht für einen anderen Auftrag“; Dialog „Für welchen Auftrag?“ seit
  1.9.80 mit Suche über alle nicht stornierten Aufträge über „Deine Aufträge“ (`heute.auftraege`), angelegt wird im Dialog -- bis 1.9.79 über
  `?neu=1` auf der Seite des Auftrags; `tests/test_v503_dialog_suche_und_anlegen.py`), Klicktest `klicktest_bericht_ohne_einsatz.py`. Wie ein Auftrag der Liste
  heißt (Nummer · Titel, Objekt · Kunde · Adresse; in der Auswahl einzeilig, gekürzt), steht seit 1.9.78 nur in `_auftrag_text.html`. Seit 1.9.69 heißen die freigegebenen Mängel der Abnahme auch für die Monteurin „Mangel“ („Mängel
  zur Beseitigung“), „Befund“ nur die Befunde aus Einsatzberichten (`tests/test_v493_mangel_und_befund.py`; 1.9.68 hieß auch der Mangel
  kurz „Befund“). Sie bleibt in `AUFGESCHOBEN` (die
  Vorlage hat keinen Seitenkopf). Klicktest `klicktest_heute.py`, Wächter `tests/test_v472_heute_seite.py`. **Seit 1.9.49** stehen die
  Listen (offene Berichte, Mängel, Checklisten, Wartungen) auf „Heute / Offen“ (`/mobil/offen`, `mobil_offen.html`, umgezogen: Monteursrahmen
  mit Seitenkopf); ein leerer Abschnitt fehlt, „Heute“ endet mit „Nächste Tage“, die Zeilen von „Offen“ springen dorthin; Wächter
  `tests/test_v476_heute_offen.py`. Seit 1.9.50 ein Feld auf der Signalfläche mit `--ds-feld-rand-signal` (≥ 3 : 1 zu signal-hell).
  **Seit 1.9.88** setzt jede Seite im Monteursrahmen `.ds-tablet` am `<body>` (unter derselben Bedingung wie `_mobile_header.html`): Knöpfe
  und Felder 12 px, Ziele ≥ 48 px (Grundregel in `ds-basis.css`), Seitentitel 26 px, Grundschrift 17 px; Wächter `tests/test_v509_ds_tablet.py`,
  gemessen in `klicktest_tablet.py` (jede Seite der Monteurin, beide TerraPad-Fenster).
  Archiv: `docs/archiv/redesign.md`, „Stufe 4, R2“ und „R2 Nachrunde“.
- **Stufe 4, R5b „Zeiten“ (Büro, seit 1.9.96):** `/zeiten` (`zeiten.html`, Daten nur aus `app/zeiten.py` über `GET /api/zeiten/pruefen`,
  `/buchungen`, `/abwesenheiten`, `/monat`) mit den Reitern Prüfen · Buchungen · Abwesenheiten · Monat & Lohn (nur Admin und Büro – Finanzen,
  `darf_lohndaten()`); Büro – Auftrag sieht Prüfen und Buchungen ohne Knöpfe. **Seit 1.9.98** ersetzt sie Zeiterfassung (Büro) und Backoffice: in
  der Leiste ein Eintrag „Zeiten“, `/time-tracking` und `/time-backoffice` leiten weiter (das Büro mit Filter und Reiter, die Monteurin auf „Meine
  Zeiten“), die Anker der früheren Reiter öffnen die neuen; jede Funktion der alten Seiten steht in `FUNKTIONEN`
  (`tests/test_v520_zeiten_umstellung.py`), entfallen sind nur die eigene Uhr des Büros und der Gruppen-Timer. Eine Zahl aus der Adresse nur über
  `app/routers/pages.py::_zahl()` (0–9, höchstens 9 Stellen). Klicktest `klicktest_zeiten.py`. Archiv: `docs/archiv/redesign.md`, „R5b“.
- **Stufe 5, R2 „Akte je Projekt“ (seit 1.9.124):** Vorlagen `bildgrundlage/entwurf_stufe5/akte-*.html`; Bildgrundlage vor dem Umbau
  `bildgrundlage/e13058e/`. 1.9.124 Auftragsstatus (vier Werte, Übergänge mit Begründung, siehe `Order` unter „Fachbegriffe“); 1.9.125 Phase und
  abgeleiteter Projektstatus (`app/akte.py`); 1.9.126 Zahlen der Akte je Auftrag (`app/akte.py::zahlen()`, `GET /api/orders/{id}/zahlen`: Leistung
  netto, Zahlung brutto wie Finanzen, Stunden mit Soll nur „in Summe“ und Ist = Baustelle & Werkstatt, je Position) -- dieselben Zahlen in
  Arbeitsvorbereitung, Plantafel und Auftragslisten (`planned_hours()` = `soll_stunden()`, `tests/test_v546_akte_zahlen.py`); 1.9.127 Verlauf der
  Akte (`app/akte_verlauf.py`, `GET /api/projects/{id}/verlauf`: ein Strom aus Änderungs- und Versandprotokoll, eine Zeile je Aktion -- Konto, Anfrage,
  5 s --, Filter nach Art und Auftrag über die Kennung des Datensatzes, ohne Zeitbuchungen, geschwärzt wie `/api/audit-logs` über
  `app/routers/audit.py::sichtbar()`; Befunde stehen seitdem im Änderungsprotokoll; `tests/test_v547_akte_verlauf.py`); 1.9.128 Kopf und Übersicht
  der Akte (`app/akte.py::akte_kontext()`, `GET /api/projects/{id}/akte`: Auftragswahl, Phasen, was ansteht, Termine, Ausführung, Zähler, Hauptaktion
  je Phase und Rolle über `hauptaktion()`), Art einer Rechnung in Worten (`app/invoices.py::rechnungsart_text()`), Summe je LV-Titel
  (`section_totals`), nach der Schlussrechnung Auftragsdaten gesperrt außer Sachbearbeiter und Bemerkungen (`FREI_NACH_SCHLUSS`, 409), „Zeiten“ mit
  `zeitraum=alle` für einen Auftrag (`tests/test_v548_akte_kontext.py`); 1.9.129 die Akte als Seite: `app/templates/akte.html` statt
  `project_folder.html` und `order.html` (`/orders/{id}` leitet auf `/projects/{p}?auftrag={id}`, die Seiten des Auftrags führen im Pfad direkt
  auf den Reiter der Akte), Reiter mit Anker, LV ohne Eingaben in der Zeile (Dialog der Position), eine Rechnungsliste für Akte und Finanzen
  (`_rechnungsliste.html`), Verlauf mit Ziel je Zeile, kein Hauptknopf am Mustervorgang; jede Funktion der früheren Seiten steht in `FUNKTIONEN`
  (`tests/test_v549_akte_seite.py`) -- eine neue Funktion an Projekt oder Auftrag kommt dort hinein. **R2 Nachrunde:** 1.9.130 im Kopf der Akte
  nur das Kennzeichen des Auftrags, die Übergänge im „⋮“ -- nur die, die `status_info()` gerade erlaubt (kein „Abschließen“ mit einer Rechnung ohne
  Schlussrechnung; `tests/test_v550_status_im_menue.py`), nach jeder Änderung am Auftrag auch der Verlauf neu; 1.9.131 Storno zurücknehmen nur
  der Admin (`app/auftragsstatus.py::storno_zuruecknehmen()`, `POST /api/orders/{id}/storno-zuruecknehmen`, `darf_storno_zuruecknehmen()`), mit
  Begründung, zurück auf „läuft“ (`tests/test_v551_storno_zuruecknehmen.py`); 1.9.132 Stunden in der Akte mit zwei Stellen wie „Zeiten“
  (`stunden_text()`, `stunden()`), „Entwurf öffnen“ statt „Entwurf anlegen“, wenn schon ein Entwurf vorliegt, ein Datum, das für sich steht, mit Jahr
  (`tagLang()`, kurz nur in Phasen und Listen; `tests/test_v552_akte_stunden_daten_entwurf.py`); 1.9.133 „Zahlbetrag unbezahlt“ auch auf der
  Rechnungsseite (`OVERVIEW_LABELS`, Kennzeichen; Schlüssel `zahlbetrag_offen` bleibt). Archiv: `docs/archiv/redesign.md`, „Stufe 5, R2“ und „R2 Nachrunde“.
- **Stufe 5, R3 „Kundenakte“ (seit 1.9.134):** Vorlagen `bildgrundlage/entwurf_stufe5_kunde/kunde-*.html`. 1.9.134 jede Funktion der heutigen
  Kundenakte als Tabelle `FUNKTIONEN` (`tests/test_v554_kundenakte_funktionen.py`: Art, Endpunkt, Rolle laut Route, Ziel-Reiter, Belege; jeder Aufruf
  unter `/api/` der Seite steht darin). Am Kunden gibt es kein Archivieren (Punkt 4, nicht gebaut). 1.9.135 Zahlen vom Server
  (`app/kundenakte.py::kunde_kontext()`, `GET /api/customers/{id}/akte`): je Projekt Status und Zahlen wie die Akte (`akte.leistung()`/`zahlung()` je
  Auftrag, ohne Mustervorgänge), Geld über `Invoice.customer_id` und die Zahlungen (unbezahlt, überfällig, Guthaben, je Jahr abgerechnet und bezahlt),
  Vorschläge für einen Rest (`tests/test_v555_kundenakte_zahlen.py`); 1.9.136 Verlauf des Kunden (`app/kunde_verlauf.py`,
  `GET /api/customers/{id}/verlauf`: Kunde, Kundenwissen, Objekte mit Dachflächen, Anfragen, Zahlungen, Versand; Zuordnung über die Kennung, gelöschte
  über den Schnappschuss, eine gelöschte Kennung nur im Zeitfenster ihres Datensatzes), Seiten beider Verläufe über `akte_verlauf.zeilen_seite()`,
  `PUT /api/customers/{id}` als Teil-Update (`tests/test_v556_kunde_verlauf_und_stammdaten.py`); 1.9.137 die Kundenakte als Seite (`customer.html`, umgezogen):
  Kopf mit Kategorie (`statusFreieGruppen()`), Untertitel mit Links (`seitenkopf({untertitel:[…]})`), Reiter mit Anker (`#zahlungen`, `#versand`), Stammdaten lesend mit Dialog
  (Felder füllt erst das Öffnen, gesendet nur die Abweichung), Zahlungen mit Vorschlägen und „⋮“ je Eingang, Geld nur `darf_geld()`; „⋮“ von Akte und Kundenakte mit Trennlinien
  (`.ds-menue-trenner`, `dsMenueTrennerOrdnen()`) -- jede Funktion in `FUNKTIONEN` (`tests/test_v554_kundenakte_funktionen.py`, eine neue Funktion am Kunden kommt dort hinein),
  `tests/test_v557_kundenakte_seite.py`, Klicktest `klicktest_kundenakte.py`. Archiv: `docs/archiv/redesign.md`, „Stufe 5, R3“.
- **Stufe 5, R4 „Abschluss“ (seit 1.9.138):** 1.9.138 Klicktests messen bei 412 px gegen die Gerätebreite (`tab.ueberlauf()`), keine Seite lief über; 1.9.139 Verlaufstexte der
  Zahlungen: ein Satz je Buchung, gleich in Akte und Kunde (`app/akte_verlauf.py::zahlung_text()`, aus dem Schnappschuss, das Protokoll bleibt), Einzelheiten über `verlaufEinzelheit()`
  aus `_verlauf.html` (`tests/test_v559_verlauf_zahlungen.py`); 1.9.140 Kundendokumente im Änderungsprotokoll und im Verlauf des Kunden (`tests/test_v560_kundendokumente_verlauf.py`); 1.9.141 Projektzeile der Kundenakte: Name und
  Kennzeichen auf einer Zeile, langer Name mit „…“ und vollem Namen als title (`tests/test_v561_projektzeile.py`). **Stufe 5 ist damit fertig**, Bildgrundlage des Endstands unter `bildgrundlage/<commit>/`.
  Archiv: `docs/archiv/redesign.md`, „Stufe 5, R4“.

## Kritische, nicht verhandelbare Regeln

Diese Punkte wurden in der Sitzung mehrfach zum echten Problem, bevor sie zur festen Regel
wurden. Bitte in jeder neuen Sitzung beachten, nicht neu lernen müssen:

1. **`server_default` bei NOT-NULL-Spalten auf bestehenden Tabellen ist Pflicht**, nicht nur
   `default=`. Ohne `server_default` schlägt die Migration auf einer bereits gefüllten Tabelle
   fehl. Gilt für jede neue Spalte, die per Alembic auf eine existierende Tabelle kommt.

2. **Keine Funktionen mit `test_`-Präfix außerhalb von Testdateien.** pytest sammelt jedes
   importierte Symbol mit diesem Präfix als eigenen Test ein und bricht ab. Wurde einmal so
   benannt (`test_smtp_connection`) und musste in `check_smtp_connection` umbenannt werden.

3. **Zirkel-Import-Falle bei PDF-Renderern:** `X_pdf.py`-Module importieren fast immer aus dem
   zugehörigen `X.py`-Geschäftslogik-Modul zurück (z. B. `invoice_pdf.py` aus `invoices.py`,
   `reminder_pdf.py` aus `reminders.py`, `quote_layout_pdf.py` aus `projects.py`, `order_pdf.py`
   aus `orders.py`). Wird `X.py` um eine neue Funktion erweitert, die ihrerseits den PDF-Renderer
   braucht, **immer lokal innerhalb der Funktion importieren**, nie auf Modulebene – sonst
   Zirkel-Import. Vor dem Hinzufügen kurz prüfen: `grep "^from \." app/X_pdf.py`.

4. **Nie `prompt()` oder andere Browser-Popups für Dateneingabe.** Ausdrücklich von Tobias
   gefordert: Eingaben (z. B. eine E-Mail-Adresse vor dem Versand) müssen als bereits sichtbares,
   vorausgefülltes Eingabefeld direkt auf der Seite erscheinen, nicht als Popup. `confirm()` für
   einfache Ja/Nein-Bestätigungen (z. B. "wirklich löschen?") ist dagegen etabliert und in Ordnung.

5. **GoBD-Unveränderlichkeit ernst nehmen.** Finalisierte Rechnungen und Mahnungen (Status
   ungleich Entwurf) dürfen nie bearbeitet oder gelöscht werden – nur Entwürfe. Ein Projekt mit
   bestehendem Auftrag darf nicht hart gelöscht werden: `Order.invoices` trägt
   `cascade="all, delete-orphan"`, ein uneingeschränktes Löschen würde auch bereits finalisierte
   Rechnungen mitreißen. Solche Projekte lassen sich nur archivieren, nicht löschen.

6. **Migrationsarme Zusatztabellen haben keine ORM-Relationship, also keine automatische
   Kaskade.** Um spätere Features ohne `ALTER TABLE` auf Kerntabellen einzuführen, wurden
   mehrfach separate "Zusatztabellen" mit reiner Fremdschlüsselspalte angelegt (Beispiel:
   `QuoteSection`, `QuoteDocumentMeta`, `QuoteEmployeeAssignment`, `QuoteItemLayout` – Zugriff
   überall per expliziter `select(...)`-Abfrage, nie über ein Attribut wie `quote.sections`).
   **Wird ein übergeordneter Datensatz (Quote, QuoteItem, …) gelöscht, müssen solche
   Zusatztabellen manuell vorher geleert werden** – SQLAlchemy kaskadiert hier nichts von allein.
   Genau das wurde einmal übersehen und führte zu verwaisten Zeilen; seither expliziter Test dafür.

7. **Vor jedem Modell-Konstruktor-Aufruf in neuem Code (Anwendungscode wie Tests) die
   tatsächlichen Feldnamen in `app/models.py` gegenprüfen**, nicht aus dem Gedächtnis raten.
   Besonders bei Tests wichtig, da diese in dieser Sitzung immer wieder real mit `pytest`
   ausgeführt wurden und falsche Feldnamen sofort auffielen. Für einen schnellen Überblick ohne
   die ganze (2361 Zeilen lange) Datei zu lesen: `docs/bestandsaufnahme_modelle.md` listet alle
   104 Modelle mit Spalten/FKs/Relationships (Stand 09.09.2026) – bei neueren Änderungen bleibt
   trotzdem `app/models.py` selbst die verbindliche Quelle, die Anlage kann veralten.

8. **`CHANGELOG.md` und `VERSION` gehören zu jeder abgeschlossenen, spürbaren Änderung dazu, nicht
   nur zu "richtigen Features".** Diese Datei war über ~45 Versionen (1.0.57–1.0.96 sowie das
   komplette visuelle Redesign) ungepflegt und musste rückwirkend aus `seit 1.0.NN`-Codekommentaren
   rekonstruiert werden, was für die undokumentierten Versionen nur noch lückenhaft möglich war –
   das soll sich nicht wiederholen. Vorgehen bei jeder abgeschlossenen Änderung (nicht erst am
   Ende einer langen Sitzung sammeln): `VERSION` um genau einen Patch-Level erhöhen, dann in
   `CHANGELOG.md` **oben** (unterhalb der Kopfzeilen) einen neuen Abschnitt `## <neue Version> –
   <Kurztitel>` einfügen, ein bis zwei Absätze in der etablierten Erzählweise (was wurde geändert
   und warum, ggf. ein dabei gefundener Fehler) – siehe bestehende Einträge als Vorlage. Auch reine
   Aufräum-/Redesign-/Cleanup-Durchgänge zählen als eigene Version, nicht nur neue fachliche
   Funktionen. Bei mehreren klar trennbaren Änderungen in einer Sitzung lieber mehrere kleine
   Versionssprünge als einen vagen Sammel-Eintrag. **Seit 1.1.0 zusätzlich:** ein
   Minor-Versionssprung (`1.X.0`) markiert die Einführung eines neuen, echten Moduls (siehe
   Modul-Umschalter unten), ein reiner Patch-Level (`1.0.X`) alles andere – Infrastruktur, Fixes,
   Redesign, Anpassungen an bestehenden Modulen. **Ergänzt am 21.10.2026 (Betreibervorgabe):** Ein Minor-Sprung
   markiert ein neues, echtes Modul oder den Beginn einer großen, über viele Seiten sichtbaren Überarbeitung
   (z. B. Stufe 2: 1.9.0); was dazu zählt, legt Tobias fest. Innerhalb zählt der Patch-Level weiter.

9. **Nach jedem abgeschlossenen Update (seit 1.1.4) läuft zusätzlich `backup_windows.ps1`.**
   Grund: das Projekt liegt bisher in keinem Git-Repository – ohne ein eigenes Backup gibt es
   keinen Rollback-Mechanismus, falls sich ein Update im Nachhinein als fehlerhaft herausstellt.
   Das Skript kopiert das komplette Projekt (Code **und** Datenbank `dachkonzepte_erp.db` **und**
   `data/` mit Firmenlogo, hochgeladenen Projektdateien und dem Verschlüsselungsschlüssel
   `data/.erp_secret`) nach `C:\DACHKONZEPTE-ERP\Backup\v<VERSION>_<Zeitstempel>\` – ein neuer
   Ordner pro Lauf, nichts wird überschrieben. Ausgenommen sind nur `.venv`, `__pycache__`,
   `.pytest_cache` (reproduzierbar über `requirements.txt`) sowie Log-Dateien (kein Teil eines
   funktionierenden Zustands). Reihenfolge bei jedem abgeschlossenen Update: zuerst `VERSION` +
   `CHANGELOG.md` (Regel 8), dann `.\backup_windows.ps1` ausführen und den Erfolg (Zielordner,
   Größe) kurz prüfen. **Automatische Bereinigung (seit 1.1.5):** das Skript behält nach jedem
   Lauf nur die 3 jüngsten Backup-Ordner, ältere werden am Ende desselben Laufs automatisch
   gelöscht (Parameter `-KeepCount`, falls doch mal mehr/weniger gebraucht wird) – bei normalem
   Betrieb (ein Backup pro abgeschlossenem Update) entspricht das genau den letzten 3 Versionen.
   **Deshalb (seit 1.3.40, echter Vorfall): unter `C:\DACHKONZEPTE-ERP\Backup\` dürfen
   ausschließlich vom Skript selbst erzeugte Ordner liegen (Namensmuster `v<VERSION>_<Zeitstempel>`,
   z. B. `v1.3.40_20260914-135537`).** Die Bereinigung filtert seit 1.3.40 zwar zusätzlich auf
   genau dieses Muster (`Get-ChildItem ... -Filter "v*_*"`, vorher griff sie auf JEDEN Ordner in
   diesem Verzeichnis zu) -- ein zuvor dort abgelegter, fremder Ordner (`Server`, Kopien der
   Server-Sicherungen von `/home/tobias/backups/`) wurde dadurch real gelöscht, bevor die
   Filterung existierte (zum Glück ohne echten Datenverlust, da dieselben Sicherungen unverändert
   auf dem Produktivserver lagen). Andere Dateien -- auch fremde, auch scheinbar sicher benannte
   -- gehören deshalb in einen ANDEREN Ordner, nie direkt unter `Backup\`.

10. **Jeder Stammdatenbereich folgt demselben Muster, ausnahmslos (seit 1.3.30 als Regel
    festgehalten, nachdem Mitarbeiter zweimal davon abwich):** beim Einstieg zeigt sich immer
    zuerst die LISTE, nie ein Formular; die Seite trägt die gemeinsame Stammdaten-Navigation
    (`master_data.html`s `.side`-Leiste, mit der zwischen Kunden, Objekten, Mitarbeitern, Teams
    und allen übrigen Bereichen gewechselt wird); Anlegen UND Bearbeiten öffnen immer eine eigene
    Formularseite (`master_data_form.html`, parametrisiert über `data_type`/`record_id` -- oder,
    wenn ein Bereich eine eigene, reichhaltigere Detailseite rechtfertigt, wie bei Kunden/Objekten,
    diese eigene Seite), nie ein Formular, das unterhalb oder neben der Liste eingeblendet wird.
    Ein "Zurück"-Link ist kein Ersatz für die Navigationsleiste -- wo die Leiste vorhanden ist,
    braucht es ihn nicht. Gilt für JEDEN künftigen Stammdatenbereich, auch wenn er zunächst
    einfacher erscheint, als eigene Seite gebaut zu werden. Historie, warum das eine echte Regel
    und keine Stilfrage ist: Mitarbeiter wich davon zweimal ab -- zuerst (bis 1.3.26) implizit
    nie geprüft, dann (1.3.26–1.3.29) als bewusst gebaute, aber grundverschiedene Einzelseite
    `/employees` (Formular immer sichtbar statt Liste zuerst) --, beide Male fiel es erst auf,
    als es der einzige Weg zu Mitarbeitern war. Details der endgültigen Korrektur (inkl. der
    Prüfung, warum sich der Vergütungsrechner doch vollständig in `master_data_form.html`
    unterbringen ließ) im Abschnitt "Mitarbeiter-Formular: ein Bereich statt zwei Ähnlicher"
    unten.

11. **Jeder neue `/api/`-Endpunkt braucht eine ausdrückliche Rollenangabe
    (`Depends(require_min_role(...))` aus `app/permissions.py` -- seit der Vier-Rollen-
    Erweiterung 1.4.7 die primäre, hierarchiebasierte Prüfart für die überwältigende Mehrheit
    der Fälle, siehe "Rechtekonzept" -> "Vier Rollen" --, das ältere, flache
    `Depends(require_role(...))` für echte, nicht-hierarchische Rollenmengen, oder das noch
    ältere `Depends(require_admin(...))` aus `app/deps.py`) -- Standardverweigerung, nicht
    Positivliste (seit "Rechtekonzept", siehe eigener Abschnitt unten für die volle
    Begründung).** Fehlt sie, gilt der Endpunkt als admin-only, nicht als für jeden
    Angemeldeten offen -- das ist die Umkehrung des tatsächlich wiederholt aufgetretenen
    Fehlers (`/users` seit 1.3.28, `EmployeeOut`-Lohnfelder seit 1.0.6, siehe dort): eine
    Positivliste (Sidebar/Menü zeigt einer Rolle nur, was für sie gedacht ist) lässt einen
    ungesicherten Endpunkt einfach für jeden funktionieren -- niemand merkt es, bis jemand
    gezielt danach sucht. `tests/test_v260_role_audit.py` erzwingt die Regel mechanisch: er
    geht jede registrierte Route durch und benennt jede ohne erkennbare Rollenprüfung
    namentlich -- ein vergessener Endpunkt fällt dadurch beim nächsten vollständigen
    Testlauf auf, nicht erst durch Zufall. Diese eine Prüfung bleibt bis zum Abschluss der
    dort dokumentierten Etappe 2/3 absichtlich rot (`xfail`, `strict=False`) -- ihre
    namentliche Liste ist die Checkliste für diese Etappe, kein Fehlerbefund.

12. **Testprozesse nie pauschal über den Namen beenden (`Get-Process chrome | Stop-Process`
    o. Ä.), sondern ausschließlich über die konkrete PID der selbst gestarteten Instanz.**
    Bei einer CDP-gesteuerten Headless-Chrome-Verifikation (1.5.10) wurde versehentlich
    `Get-Process chrome -ErrorAction SilentlyContinue | Stop-Process -Force
    -ErrorAction SilentlyContinue` ausgeführt, um vermeintlich verwaiste Testprozesse
    aufzuräumen -- das hat stattdessen JEDES `chrome.exe` auf der Maschine beendet,
    einschließlich des regulären, parallel geöffneten Chrome-Fensters des Nutzers (mit
    allen offenen Tabs). Tobias arbeitet auf demselben Rechner parallel mit seinem eigenen
    Browser -- ein namensbasiertes Beenden trifft dessen Fenster genauso wie die eigene,
    isolierte Testinstanz. Seither verbindlich: die PID des selbst per
    `Start-Process -PassThru` gestarteten Prozesses merken und ausschließlich
    `Stop-Process -Id <diese PID>` zum Aufräumen verwenden. Ist die PID nicht mehr bekannt
    (z. B. nach einem Sitzungswechsel), vor jedem Beenden über
    `Get-CimInstance Win32_Process -Filter "Name='chrome.exe'"` die vollständige
    Befehlszeile jedes einzelnen Treffers prüfen und ausschließlich Prozesse mit dem
    eigenen, eindeutigen `--user-data-dir`-Scratchpad-Pfad treffen -- nie ein bloßer
    Namensfilter ohne diese Prüfung, egal wie plausibel "das sind sicher meine
    Testprozesse" erscheint. Gilt sinngemäß für jeden anderen, für Tests/Automatisierung
    selbst gestarteten Prozess (nicht nur Chrome), auf dem der Nutzer möglicherweise
    parallel arbeitet.

13. **Nach jeder abgeschlossenen Runde wird committet, ohne dass Tobias das jedes Mal
    einzeln freigeben muss -- gepusht wird ausschließlich durch den Betreiber.** Vorher
    galt das nur als informelle, an einer einzelnen Stelle (Abschnitt "Produktivbetrieb")
    notierte Praxis dieser Sitzungen ("Claude Code committet, aber pusht nie ohne
    ausdrückliche Aufforderung") -- auf ausdrücklichen Wunsch jetzt als feste, durchgängige
    Regel festgehalten, damit für jede abgeschlossene Version (Regel 8: neuer `VERSION`-Stand
    + `CHANGELOG.md`-Eintrag) automatisch auch ein Commit entsteht, ohne dass jedes Mal erst
    nachgefragt werden muss. Ein Commit fasst dabei genau eine inhaltlich zusammenhängende
    Änderung, nicht mehrere unabhängige Themen gemeinsam, und nur nach grünem Lauf (Regel 15) (Vorbild: das eigene
    1.3.71-Vorgehen, dort ausdrücklich "eigener Commit, wie verlangt" für einen von der
    Hauptänderung unabhängigen Fund). `git push` bleibt davon ausgenommen und wird niemals
    von selbst ausgeführt -- das Hochladen auf den gemeinsamen Verlauf (und damit potenziell
    auf den Server, siehe "Produktivbetrieb") ist und bleibt ausschließlich eine Entscheidung
    des Betreibers.

14. **Vor Änderungen an einem Modul oder Themenbereich zuerst die zugehörige Archivdatei unter
    `docs/archiv/` lesen** (siehe Abschnitt "Modulübersicht" oben für die Zuordnung Modul →
    Datei). Die ausführliche Herleitung, frühere Fehlversuche, Betreiberentscheidungen und
    Begründungen stehen dort, nicht mehr in dieser Datei -- ohne sie zu lesen, fehlt der
    Kontext, warum eine Stelle so und nicht anders gebaut ist, und eine Änderung riskiert, eine
    bereits gelöste Frage unwissentlich erneut aufzurollen oder eine bewusste Entscheidung
    rückgängig zu machen.

15. **Testläufe mit knapper Ausgabe fahren, nicht die volle pytest-Ausgabe in den Kontext
    holen.** `pytest -q` (oder `pytest --tb=short -q`) statt der Standardausgabe -- bei über
    1800 Tests füllt eine ausführliche Ausgabe (inkl. aller Warnungen, siehe `pytest.ini`) den
    Kontext unnötig, ohne zusätzliche Information zu liefern, solange alles grün ist. Bei einem
    tatsächlichen Fehlschlag gezielt den einzelnen Testnamen erneut mit voller Ausgabe laufen
    lassen (`pytest -k <name> -v`), nicht die ganze Suite. Die `datetime.utcnow()`-
    `DeprecationWarning` ist in `pytest.ini` bereits gezielt ausgeblendet (siehe "Bekannte,
    bewusst offene Punkte" unten für die geplante, noch nicht umgesetzte Umstellung). **Seit 1.8.108 läuft die volle Suite
    parallel** (pytest-xdist): `.venv\Scripts\python.exe -m pytest -q -n 16 --dist loadfile` -- je Testdatei ein Arbeitsprozess,
    dynamisch verteilt, gemessen rund 7 min statt 41 min nacheinander (16 Arbeitsprozesse sind auf diesem Rechner das Optimum, mehr
    werden langsamer). **Vor jedem Commit läuft die volle Suite so, parallel -- nicht gezielte Teilläufe** (die bleiben für die
    Arbeit dazwischen und die Suche nach einem Fehler); Regel 26 bleibt unverändert. **Ein Commit läuft nur nach grünem Lauf** (seit
    1.9.32, Betreibervorgabe 22.10.2026): die volle Suite auf genau dem Stand, der committet wird (auch `VERSION`, `CHANGELOG.md`, Doku);
    ist ein Test rot -- auch einer, der mit der Änderung nichts zu tun scheint --, wird er zuerst geklärt, nie trotzdem committet.
    **Befehle hintereinander mit `&&`, nie mit `;`** (Bash wie PowerShell 7): die Kette bricht beim ersten Fehler ab. Anlass: 1.9.26
    wurde hinter `;` committet, obwohl der Teillauf davor einen roten Test hatte. **Vor jedem Commit laufen auch die Klicktests, die
    eine geänderte Seite berühren** (seit 1.9.38, Betreibervorgabe 22.10.2026): gesucht in `scripts/klicktest_*.py` nach der Vorlage, dem
    Seitenpfad und den geänderten Funktionen bzw. Element-IDs, jeder Treffer einzeln auf genau dem Stand des Commits; der Bericht nennt sie.
    Anlass: 1.9.36 machte „Weiter“ im Einsatzbericht asynchron, `klicktest_vertrag_unterschrift` (unterschreibt auch einen
    Einsatzbericht) lief erst im Endlauf und war rot. Klicktests zugleich:
    `scripts\klicktest_alle.py --gleichzeitig 4`. Messungen und Festlegungen: `docs/archiv/testablauf-und-klicktests.md`. **Seit 1.8.111**
    hat jeder Test eine Zeitgrenze (300 s, `tests/zeitgrenze.py`; `@pytest.mark.zeitgrenze(n)`, `--zeitgrenze SEK`, 0 = aus): ein
    hängender Test beendet seinen Testprozess mit dem Stapel aller Threads, im parallelen Lauf geht der Lauf ohne ihn weiter.

16. **Jede Verifikation -- CDP-Browsertest, Sicherheits-/Angriffstest, Datenumzugs-/
    Reparaturskript -- läuft gegen eine isolierte, temporäre Test- oder Probe-Instanz
    (SQLite/PostgreSQL), NIEMALS gegen die echte, produktive Datenbank (`dachkonzepte_erp.db`
    lokal bzw. `dachkonzepte` auf dem Server).** Gilt unabhängig davon, wie harmlos ein Schreib-
    zugriff erscheint -- ein Migrationsskript öffnet den Bestand bestenfalls "ausschließlich
    lesend" und kopiert in eine neue Zieldatenbank (Muster
    `scripts/migrate_sqlite_to_postgres.py`), ein Browser-/Angriffstest baut sich eine eigene,
    kurzlebige Datenbank auf einem separaten Port auf und räumt sie danach vollständig ab.
    Schema-Änderungen laufen zusätzlich einmal gegen die Probe-Datenbank `spielwiese` -- das
    erledigt `update.sh` selbst (siehe "Produktivbetrieb" → "Der Weg einer Änderung auf den Server"),
    ebenfalls nicht gegen `dachkonzepte`. Diese Regel gilt themenübergreifend -- unabhängig davon, welches
    Modul gerade getestet wird (real wiederholt angewendet u. a. bei Kalender-Sync,
    Buchhaltung, Projektliste, Betriebsmittelverwaltung; Details siehe jeweilige Archivdatei).

17. **Ein Microsoft-Graph-Recht (App-Berechtigung) wird NIE in Entra ID erteilt -- weder per
    "Administratorzustimmung erteilen" noch als bloß hinzugefügte Berechtigung ohne Zustimmung
    --, sondern ausschließlich über Exchange "RBAC for Applications"** (Exchange Online
    PowerShell), Scope `ERP-Zugriff` = Mitglieder der E-Mail-aktivierten Sicherheitsgruppe
    `ERP-Zugriff@dachkonzepte.gmbh`. Gilt ausnahmslos, auch für `Mail.Send`: auf dem Server
    verifizierter Stand (28.09.2026) -- App-Registrierung und Unternehmensanwendung tragen in
    Entra nur noch `User.Read` (delegiert), KEINE Graph-Anwendungsberechtigung; `Mail.Send` UND
    `Calendars.ReadWrite` laufen beide über die RBAC-Rollenzuweisung. Einrichtung:
    `Enable-OrganizationCustomization`, `New-ServicePrincipal` (ObjectId der
    Unternehmensanwendung), `New-ManagementScope` mit `MemberOfGroup`-Filter,
    `New-ManagementRoleAssignment -CustomResourceScope "ERP-Zugriff"`. Ein neues Postfach wird
    ausschließlich durch Aufnahme in die Gruppe freigeschaltet. Grund: eine Entra-Berechtigung
    gilt für JEDES Postfach im Mandanten -- bei `Mail.Send` hieß das Senden im Namen jedes
    Postfachs, also ausdrücklich NICHT unproblematisch (eine frühere Fassung dieser Regel
    behauptete das fälschlich). Wiedererteilung in Entra nur als Notfall-Rückweg, nie als
    Einrichtungsweg. Drei Konsequenzen: **das Absenderpostfach aus Einstellungen →
    E-Mail-Versand MUSS Mitglied der Gruppe sein**, sonst `ErrorAccessDenied` (real so
    aufgetreten); das Zugriffstoken verrät nie, welche Postfächer freigegeben sind (immer
    derselbe `.default`-Scope) -- einzige verlässliche Prüfung ist der tatsächliche API-Aufruf;
    ein `403`/`ErrorAccessDenied` von Graph bedeutet "Postfach nicht in der Gruppe", nicht
    "Zugangsdaten falsch" (das wäre `401`). Details:
    `docs/archiv/modul-kalender-und-outlook-sync.md`.

18. **Ein Protokoll/Log, das eine Funktion über ihre eigenen Aufrufe führt, enthält NIE den
    eigentlichen Inhalt (Titel, Adresse, Notiz, Prompt, Anhang, Antworttext) -- nur Metadaten**
    (IDs, Zähler, Zeitstempel, Erfolg/Fehlschlag, der reine Exception-Klassenname statt dessen
    Text). Unabhängig voneinander an zwei Stellen so gebaut: `AICallLog`
    (`app/ai_service.py`, siehe `docs/archiv/ki-fundament.md`) hat strukturell keine Spalte, die
    Prompt/Antwort aufnehmen könnte; die Outlook-Sync-Diagnosezeile
    (`app/outlook_calendar_sync.py`, siehe `docs/archiv/modul-kalender-und-outlook-sync.md`)
    protokolliert bewusst nie Titel/Ort/Notiz eines Termins. Gilt für jedes künftige Protokoll
    mit Zugriff auf Kunden-/Personendaten oder externe Anfrageinhalte -- am besten strukturell
    absichern (keine passende Spalte/kein passendes Feld anlegen), nicht nur als Verhaltenszusage
    im Code.

19. **Geld und Stunden werden kaufmännisch gerundet (`ROUND_HALF_UP`), immer über `app/rounding.py`
    (`round_money()`, `round_hours()`, `round_half_up()`), seit 1.8.11.** `Decimal.quantize()` ohne
    `rounding=` rundet halb-gerade (0,125 -> 0,12) und ist unter `app/` verboten --
    `tests/test_v315_commercial_rounding.py` sucht jeden solchen Aufruf per AST und nennt Datei und
    Zeile. Dasselbe halb-gerade Runden steckt in `f"{x:.2f}"`: Beträge vor dem Formatieren runden.
    Rechnungsbeträge werden live gerechnet, auch für versendete Rechnungen; deshalb trägt jede
    Rechnung ihre Regel (`Invoice.rounding_rule`): leer = vor 1.8.11 versendet, rechnet unverändert
    wie damals (Regel 5). Storno und Mahnung folgen der Regel ihrer Rechnung. Liste aller
    Geldstellen und was sich wo geändert hat: `docs/archiv/kaufmaennisches-runden.md`.

20. **"Heute" und "jetzt" kommen auf dem Server nur aus `app/berlin_time.py` (`berlin_today()`,
    `berlin_now()`), seit 1.8.12.** Der VPS läuft in UTC, `date.today()`/`datetime.now()` liefern
    dort bis 1–2 Uhr nachts den Vortag und an Silvester das alte Jahr -- lokal unter deutscher
    Windows-Zeit unsichtbar. Beide sind unter `app/` verboten, `tests/test_v316_berlin_time.py`
    sucht sie per AST -- seit 1.8.46 auch als Spaltenvorgabe ohne Klammern (`default=date.today`,
    `default_factory=date.today`); `BEKANNTE_VORGABEN` ist seit 1.8.75 leer (die fünf Altfälle nehmen `berlin_today()`) und bleibt es. Gespeicherte Zeitstempel aus `datetime.utcnow()` bleiben naive UTC; wer sie
    druckt oder ein Datum daraus ableitet, rechnet mit `to_berlin()` um; wer nach Tagen filtert, nimmt `berlin_tag_beginn_utc()` als
    Grenze (seit 1.9.52). Beginn/Ende einer
    Zeitbuchung sind dagegen naive Ortszeit. Browser-Seite: "heute" nur aus `_berlin_date.html` (`berlinToday()` u. a.,
    seit 1.8.87); `tests/test_v390_browser_datum.py` lässt `toISOString()`, `new Date()`/`Date.now()` ohne Argument in den
    Vorlagen nur als begründeten Zeitpunkt zu. Details: `docs/archiv/zeiterfassung-und-abwesenheit.md`, "Kalenderdatum in Europe/Berlin
    statt UTC". **Seit 1.9.46 jeder angezeigte gespeicherte Zeitpunkt** (naives UTC) im Browser nur über `berlinZeitpunkt(wert, art)` aus
    `_berlin_date.html` -- nie `new Date(x)`, `+'Z'`, `toLocale…` ohne `timeZone` oder `slice()` auf einem UTC-Feld
    (`tests/test_v473_zeitpunkte_berlin.py`, Liste `UTC_FELDER`); naive Ortszeit und `*_local`-Felder nie durch den Helfer.

21. **Jede E-Mail geht über `app/email_dispatch.py::dispatch_email()`, seit 1.8.17** -- nie direkt
    über `app/email_sending.py::send_message()`, SMTP oder Graph. Nur so entsteht der
    Protokolleintrag (vor dem Senden, mit Schlüssel gegen Doppelversand) und landet ein PDF in der
    unveränderlichen Ablage. `tests/test_v321_email_dispatch.py` sucht jeden anderen Aufrufer per
    AST. Eine neue Versandstelle von der Oberfläche schickt einen `dispatch_key` je Klick mit
    (`_email_dispatch.html`). Ablage und Protokoll werden nie geändert oder gelöscht (einzige
    Ausnahme seit 1.8.19: ein hängender Eintrag wird einmal mit Notiz geklärt). Rechnung und Storno liegen seit 1.8.82 ab dem
    Festschreiben dort (feste Fassung im selben Commit, `Invoice.pdf_document_id`, `app/invoices.py::_store_fixed_pdf()`; ohne PDF
    kein Festschreiben), die Mahnung und Rechnungen von vor 1.8.82 ab dem ersten Versand -- alle aus der Ablage
    (`frozen_or_fresh_pdf()`), nie neu erzeugt; der Vertrag
    liegt seit 1.8.33 schon ab dem Festschreiben dort (Fassung, `app/contract_versions.py`), seit 1.8.34 auch
    Unterschriftsblatt, Unterschriftsbilder und Papier-Scan (`app/contract_signatures.py`), seit 1.8.35 die
    unterschriebene Abschrift (Fassung + Blatt bzw. Scan), die Versand und Zustellung danach hinausgeben; seit 1.8.40 ebenso die
    Briefe zur Behinderungsanzeige (seit 1.8.44 auch zur Bedenkenanzeige) ab dem Erstellen (`app/notice_letters.py`), dazu je Versand die Vollmacht eines
    empfangsbevollmächtigten Empfängers (`dispatch_email(before_send=…)`); seit 1.8.66 jede Checkliste ab jeder Unterschrift und
    dem Abschluss (feste Fassung, `app/checklist_versions.py`, überholt nach verworfener Unterschrift); seit 1.8.67 geht das
    Abnahmeprotokoll über den Weg der Briefe (`app/protocol_dispatch.py`, gemeinsame Funktionen `client_recipients()`,
    `client_address()`, `dispatch_to_client()` in `app/notice_letters.py`) -- nur die jüngste gültige Fassung, seit 1.8.68 in
    Kopie genau an die in der Fassung eingefrorenen Empfänger (kein freies CC). Seit 1.8.69 für Protokoll und Briefe: wo ein PDF
    "Kopie an:" zeigt, gehen die Mails genau an diese Personen, an ihre Adresse von heute (`app/frozen_copies.py`,
    `dispatch_to_client(copies=…)`); wer keine Mail bekam, hält `dispatch_copies` fest; ein neues PDF mit "Kopie an:" braucht
    einen Eintrag in `KOPIE_AN_PDFS` (`tests/test_v371_kopien_an_personen.py`).
    Eine Zustellung auf anderem Weg (Einschreiben, Übergabe, Bote, Fax) wird seit 1.8.20 im selben
    Protokoll nachgetragen (`record_manual_delivery()`, seit 1.8.41 mit Empfängerauswahl aus Auftraggeber und
    Beteiligten, Vollmacht eingefroren); seit 1.8.41 je gesendetem Eintrag einmal "Empfang bestätigt" oder
    "unzustellbar" (`record_dispatch_outcome()`, eigene Tabelle, unveränderlich); eine neue Dokumentart braucht einen Eintrag
    in `app/dispatch_documents.py`. Details: `docs/archiv/versandprotokoll-und-ablage.md`.

22. **Ein Update-Endpunkt übernimmt nur gesendete Felder, seit 1.8.25.** Hat ein PUT-Schema Felder
    mit Vorgabewert, setzt Pydantic für ein weggelassenes Feld den Vorgabewert ein -- liest der Handler
    `payload.feld` oder `model_dump()`, ist der gespeicherte Wert still weg (so Zugangshinweise, Pause,
    Schlusstext 2, Sichtbarkeitsgrenze einer Aufgabe). Neues Teil-Update: Schema von `PartialUpdate`
    (`app/schemas.py`, `NOT_NULL` für Pflichtspalten), Handler mit `model_dump(exclude_unset=True)`;
    oder alle Felder ohne Vorgabewert (fehlt eins, 422). Die Oberfläche schickt nur, was sie bearbeitet,
    nie einen beim Laden gemerkten Stand. Eine Auswahlliste aus Stammdaten baut ihre Optionen über
    `auswahlOptionen()` (`_auswahl.html`, seit 1.8.30): ein inaktiver gespeicherter Wert bleibt vorgewählt
    und gekennzeichnet; der Server prüft "aktiv" nur bei einem neu gewählten Wert. Ein leerer gespeicherter
    Wert bleibt leer -- eine Vorgabe aus den Einstellungen gilt nur beim Anlegen (seit 1.8.31). **Seit 1.9.12 jedes Auswahlfeld mit
    gespeichertem Text oder Zahl** (Optionsgruppe oder feste Liste, die der Server nicht erzwingt) über `auswahlOptionen()`, eine feste
    Liste im Markup über `auswahlWert()`: ein Wert außerhalb der Liste bleibt gewählt ("… (nicht mehr verfügbar)") und erhalten; nie
    `select.value = gespeichert` oder Optionen von Hand mit bedingtem `selected` -- Wächter `tests/test_v447_auswahl_altwerte.py`
    (Scanner `tests/vorlagen_auswahl.py`, jede andere Fundstelle in `KLASSEN` mit Grund), Prüfabfrage `scripts/pruefabfrage_auswahlwerte.sql`.
    **Seit 1.9.16 ebenso jeder Fremdschlüssel** (Auftrag, Objekt, Mitarbeiter, Vorlage …): ein archiviertes, inaktives oder nicht mehr
    in der Auswahl stehendes Ziel bleibt gewählt und gekennzeichnet (`opt.aktiv`/`opt.vermerk`, `opt.fehlt` mit dem Namen aus dem
    Datensatz), nie still umgestellt; nie `auswahlOptionen()` über eine vorher gefilterte Liste (Wächter P3); `KLASSEN` kennt dafür nur
    `vollstaendig` (Liste enthält jede speicherbare ID), `neu` oder `eigen` (`tests/test_v450_auswahl_fremdschluessel.py`).
    `tests/test_v329_update_handler_struktur.py` prüft jeden
    PUT/PATCH-Handler per AST; die 59 Altfälle (seit 1.9.145, bis 1.9.144 60, bis 1.9.135 61, bis 1.9.65 62, bis 1.8.95 70) stehen dort als Liste, die nur kürzer werden darf.
    Details: `docs/archiv/teil-updates.md`.

23. **Grunddaten legt der Start an, nie ein Lesepfad -- kein GET schreibt, seit 1.8.42.** Einstellungen
    (Singletons, id=1) und Standardsätze (Optionsgruppen, Kategorien, Spalten, Nummernkreise, Layout, Ränder …)
    legt `app/grunddaten.py::anlegen()` beim Start an (`app/main.py`, auch in Produktion); zwei gleichzeitig
    startende Arbeitsprozesse warten an der Sperrzeile `general_settings`. Lesefunktionen (`load_*`,
    `get_margins()`, `load_layout()`) lesen nur und melden eine fehlende Zeile mit `GrunddatenFehlen`. Eine neue
    Einstellung oder ein neuer Standardsatz kommt in `grunddaten.py`, nie als Anlegen in eine Lesefunktion;
    Anlegeschritte committen nicht (ein Commit gäbe die Sperre frei). `test_kein_get_schreibt`
    (`tests/test_v326_monteur_datengrenze.py`) ruft jeden GET-Endpunkt als Monteur und als Admin mit
    Datenbank-Listener auf; seit 1.8.84 ohne Ausnahmeliste, mit einem dritten Rundgang auf Testdaten mit Lücken und einem
    Beobachter an der Sitzung. **Daten je Datensatz** (Profil, Angebotskopf und -layout, Kalkulation, Arbeitsvorbereitung,
    Lohnstammdaten) legt das Anlegen des Datensatzes oder der erste Schreibweg an; ein Lesepfad zeigt die Vorgabe ohne zu speichern
    (`load_employees()`, `quote_structure()`, `quote_item_calculation_preview()`, `preparation_preview()`, `load_employee_payroll()`,
    leeres `id`). Testdatenbanken bekommen die Grunddaten nach `create_all()` (conftest), ohne sie: `tests/grunddaten_schalter.py`.
    Details: `docs/archiv/grunddaten-beim-start.md`.

24. **Eine Gegenprobe bleibt nie im Code, seit 1.8.55.** Eine Gegenprobe hebelt einen Schutz in `app/` absichtlich aus, um
    zu zeigen, dass sein Test dann rot wird. Jede Änderung dafür trägt den Marker `GEGENPROBE` (Kommentar in der geänderten
    Zeile, in Vorlagen `/* GEGENPROBE */`); `tests/test_v357_gegenprobe_marker.py` schlägt an, sobald er irgendwo unter
    `app/` steht, mit Datei und Zeile. Danach die Datei byte-genau zurück (Prüfsumme vergleichen). Solange eine Gegenprobe
    läuft, läuft nichts anderes gegen diesen Code -- Anlass: in 1.8.54 fiel eine Migrationsprobe in eine laufende
    Gegenprobe (`docs/archiv/abnahme-und-gewaehrleistung.md`, "Verifikation 1.8.54" und "Umsetzung 1.8.55"). **Seit 1.8.108** bricht
    jeder Klicktest nach höchstens 2 min ab, solange der Marker unter `app/` steht (eigene Prozesse über ihre PID beendet,
    Rückgabecode 3, `scripts/cdp_klicktest.py::Wachhund`) -- ein ausgehebelter Schutz lässt eine Seite sonst im Kreis laufen.

25. **Eine ID aus der Anfrage gehört zum selben Objekt, Auftrag oder Kunden, seit 1.8.70.** Wer eine fremde ID speichert, ohne
    das zu prüfen, öffnet einen Weg über fortlaufende IDs (Befund: Dachfläche eines fremden Objekts im Einsatzbericht, Position
    eines fremden Auftrags in der Rechnung). Prüfungen in `app/zugehoerigkeit.py` (`require_in_order_property()`: Dachfläche und
    Bauteil nur aus dem Objekt des Auftrags, fremd wie unbekannt 404 ohne Grund; `require_confirmed_property()`: Objekt eines
    anderen Kunden nur mit Bestätigung, sonst 409) oder eine eigene. `tests/test_v373_zugehoerigkeit_struktur.py` findet jede
    ID-Eingabe schreibender Routen (Body, Formular, Query) und jedes ID-Paar im Pfad; jede steht in `STAMMDATEN` (Feldname),
    `GEPRUEFT` (Funktion und Vergleich, der Test verlangt beides auf dem Weg vom Endpunkt), `FREI` (legt Besitzer/Kontext fest;
    seit 1.8.71 ebenfalls mit Funktion und Vergleich der Existenzprüfung -- unbekannt 404 statt 500 am Fremdschlüssel,
    `IdNichtGefunden`) oder `AUSNAHMEN` (darf nur kürzer werden). "Erfasst von"/"geschlossen von" setzt der Server aus der
    Anmeldung, mitgeschickt 422. Details: `docs/archiv/befund-vor-echtbetrieb.md`, "Umsetzung 1.8.70" und "Umsetzung 1.8.71".

26. **Vor jedem Bericht läuft `scripts/klicktest_alle.py`, das Ergebnis steht im Bericht, seit 1.8.77.** Alle Klicktests auf
    dem Stand, über den berichtet wird (Arbeitskopie wie bei der vollen Suite): wie viele wie erwartet, welche rot mit der roten
    Prüfung, Laufzeit. Eine rote Prüfung wird benannt, nicht still angepasst -- ist ihre Erwartung veraltet, sagt der Bericht das
    und seit wann. Anlass: `klicktest_vertragsvorlagen.py` erwartete seit 1.8.50 22 statt 23 Platzhalter; aufgefallen erst beim
    ersten Gesamtlauf (1.8.76). **Seit 1.8.99 (Betreibervorgabe 14.10.2026): volle Suite und alle Klicktests laufen auf dem committeten
    Endstand bei sauberer Arbeitskopie** (`git status` ohne Änderungen, z. B. eine frische Arbeitskopie auf dem Commit), der Bericht nennt
    den Hash dieses Commits; ändert sich danach noch etwas (auch nur ein Kommentar oder eine Doku-Zeile), laufen beide neu. **Seit
    15.10.2026 (Betreibervorgabe): ein Commit, der nur `docs/` ändert, löst keinen neuen Endlauf aus.**

27. **Kein Test gegen PostgreSQL läuft im Schema `public` der Spielwiese, seit 1.8.81.** Jeder PostgreSQL-Test nimmt ein
    Wegwerf-Schema (`connect_args={"options": "-csearch_path=<schema>"}` bzw. `tests/befund_vor_echtbetrieb.py::pg_sitzung()`); eine
    Engine ohne eigenes Schema dient nur der Verwaltung (CREATE/DROP SCHEMA, `pg_terminate_backend`). Der Wächter in `tests/pg_schutz.py`
    (eingerichtet in `tests/conftest.py`) bricht jede andere Anweisung in `public` ab; wer `DATABASE_URL` an einen Kindprozess gibt
    (alembic, `app.main`), prüft sie mit `pg_url_pruefen()`. `tests/test_v384_pg_nicht_public.py` erzwingt beides per AST. Eine
    Migration, die Daten ändert, wird zusätzlich auf einem Bestand gegen PostgreSQL geprobt, nicht nur auf leerem Schema. Anlass:
    `test_v297` lief bis 1.8.80 in `public` (dort fehlte eine neue Spalte, drei Tests rot). **Seit 1.8.108** trägt jedes Schema
    `pgtest_*` als Kommentar die Kennung des Testprozesses, der es anlegt (Rechner, PID, Startzeit; der Wächter hängt sie an jedes
    `CREATE SCHEMA`); zu Beginn eines Testlaufs löscht `tests/conftest.py` jedes, dessen Prozess nicht mehr läuft -- nie eines eines
    laufenden Prozesses, nie eines ohne Kennung (nur genannt), nie `public` (`tests/pg_schutz.py::liegen_gebliebene_schemas_loeschen()`).
    Die Spielwiese läuft mit `max_locks_per_transaction = 1024`: ein `DROP SCHEMA` braucht über 1100 Sperren, mit der Vorgabe 64 brachen
    gleichzeitige Läufe mit "Shared Memory aufgebraucht" ab. **Seit 1.9.31** ersetzt `ERP_TEST_RECHNER` (nur Tests) den Rechnernamen in
    der Kennung: ein Test, der ein liegen gebliebenes Schema nachstellt, gibt ihm einen eigenen Namen -- kein anderer, gleichzeitig
    startender Lauf räumt es weg (`tests/test_v413_testlauf_parallel.py`).

28. **Der Bericht nennt jede neue Festlegung in einer Zeile, nicht nur die wichtigsten, seit 1.8.91.** Jede Festlegung, die eine Runde
    trifft (im Archiv unter "Festlegungen <Version> (Bitte bestätigen)"), steht im Bericht mit Version und Nummer in genau einer Zeile --
    auch wenn es viele sind; die ausführliche Fassung bleibt im Archiv. Was noch nicht bestätigt ist, bleibt so lange in dieser Form
    vorgelegt. Anlass: der Bericht zu R4c nannte nur eine Auswahl, die Festlegungen 1.8.87–1.8.90 mussten eigens angefordert werden.
    **Seit 1.8.99 ebenso jede angepasste Erwartung eines Tests oder Klicktests**: Test, altes Soll, neues Soll (im Archiv unter "Tests
    und Prüfung", im Bericht je eine Zeile) -- auch wenn nur der Aufbau geändert ist, wird das gesagt. **Seit 1.8.108: Festlegungen, die
    nur Klicktest-Werkzeug und Testablauf betreffen, stehen im Archiv** (`docs/archiv/testablauf-und-klicktests.md`, je eine Zeile mit
    "Bitte bestätigen"), **der Bericht nennt ihre Zahl** statt jeder einzelnen.

29. **Jede Anfrage per fetch läuft über den Baustein `app/templates/_speichern.html`, seit 1.8.95 (Lesen ohne Ausnahme seit 1.8.97).**
    Schreibende Anfrage (Methode ungleich GET, auch Löschen, Versand, Anmelden): `await speichern('<bereich>', ()=>api(url,{method:…}),
    {anwenden | neuLaden})` -- der Pfeil enthält genau die eine Anfrage; `speichern()` baut sie sofort (Werte vom Klick), sendet je Bereich
    nacheinander und kehrt erst zurück, wenn die Antwort angewandt bzw. über `lesen()` neu geladen ist; Erfolgstexte ("Gespeichert.")
    stehen dahinter. Lesen: `await lesen('<bereich>', ()=>api(…), anwenden)` -- auch das erste Laden, das Öffnen eines Dialogs, der Wechsel
    einer Auswahl (auch auf "keine", als Lesen ohne Anfrage), im Bereich des Speicherns, dessen Antwort denselben Stand ersetzt; zwei Bereiche
    setzen nie denselben Stand. Bereich = was eine Antwort ersetzt; alles gilt **je Bereich**: laufende Nummer, eine Antwort oder ein Fehler,
    älter als eine schon angewandte, wird verworfen (nach einem Fehler des neuesten Lesens auch ein älteres), Lesen wartet auf laufendes
    Speichern desselben Bereichs, Speichern geht nacheinander, dieselbe Anfrage (Doppelklick) geht nicht ein zweites Mal hinaus, solange
    die erste wartet oder unterwegs ist (seit 1.8.97). Ohne Antwort 60 s nach dem Senden (beim Hochladen -- Body FormData, Blob, Binärdaten --
    seit 1.8.99 nach dem Ende der Übertragung, über XMLHttpRequest) bricht der Baustein ab, der Bereich ist
    "unklar" (Fehler, Hinweis oben "Seite neu laden", bis zum Neuladen geht dort nichts mehr hinaus); solange ein Speichern läuft oder wartet,
    warnt die Seite beim Verlassen (seit 1.8.96). **Abschließende Aktionen** (Unterschrift, Festschreiben, Versand, Buchung, Storno, Abnahme,
    Mangel u. ä.) über `abschliessen()`: gesendet erst, wenn jedes beim Klick laufende oder wartende Speichern der Seite zurück ist, gar
    nicht in einem unklaren Bereich und nicht, solange in einem Bereich das letzte Speichern gescheitert ist (seit 1.8.99 auch vor dem
    Klick, bis ein späteres Speichern im selben Bereich gelingt; eine abgelehnte abschließende Aktion sperrt keine weitere; seit 1.8.109 auch
    nicht, solange ein Zahlenfeld der Seite abgelehnt ist, Regel 34); eine neue gehört in `ABSCHLIESSEND` (`tests/test_v399_abschliessen.py`,
    prüft auch abschließend klingende Adressen). Eine Anfrage außerhalb des Bausteins gibt es nur ohne Formular (nur Anzeige, Suche,
    Anmeldestatus, Prüfung), eingetragen in `AUSNAHMEN` (`tests/test_v400_lesen_ueber_baustein.py`, Scanner
    `tests/vorlagen_js.py::anfragen_ausserhalb()`, seit 1.8.99 auch Aufrufe von `api()`/`fetch()` direkt aus einem on…-Attribut; darf nur
    kürzer werden). `window.__dkZeitlimit` steht nur im Baustein und unter `scripts/` (eine Vorlage fragt `zeitlimitSekunden()`). `tests/test_v398_speichern_baustein.py` prüft jede Vorlage:
    Schreiben nur über `speichern()`/`abschliessen()`, danach nur `lesen()`/`speichern()` (transitiv), "Gespeichert" nur danach, einbinden wer
    nutzt, jedes Seitenskript in node auf Syntax. Klicktests: `klicktest_veraltete_antworten` (`Tab.zurueckhalten()`), `klicktest_abschliessen`
    (Zeitlimit über `window.__dkZeitlimit`), `klicktest_anmelden`; das Klicktest-Werkzeug nennt beim Scheitern die offenen Anfragen
    (Netzwerkprotokoll), `klicktest_hochladen` (seit 1.8.99, gedrosseltes Netz). Details: `docs/archiv/befund-vor-echtbetrieb.md`,
    "Umsetzung 1.8.95" bis "Umsetzung 1.8.97" und "Umsetzung 1.8.99".

30. **Weiterleitungen nur auf lokale Pfade, Sitzungen auf dem Server, kein Cache für angemeldete Sitzungen, seit 1.8.98.** Ein Ziel aus
    Anfrage oder Adresse (`next` u. ä.) geht über `app/weiterleitung.py::sicheres_ziel()` (Server) bzw. `sicheresZiel()` aus
    `_weiterleitung.html` (Browser): nur ein lokaler Pfad, sonst die Startseite. Sonst hat jede `RedirectResponse` ein festes Ziel und jede
    Navigation einer Vorlage zu einem Wert aus der Adresse einen festen lokalen Anfang (`tests/test_v401_weiterleitung.py`: AST bzw.
    `tests/vorlagen_navigation.py`, dazu eine Angriffstabelle für beide Fassungen). Anmelden legt eine Sitzung an (`app/sitzungen.py`,
    Tabelle `user_sessions`: nur der Hash des Cookie-Werts, fest 12 h, zweiter Faktor je Sitzung); Abmelden beendet sie, wer Passwort,
    zweiten Faktor oder Aktiv-Status eines Kontos ändert, beendet im selben Commit alle seine Sitzungen (`alle_beenden()`) -- eine neue
    solche Stelle ebenso (`tests/test_v402_sitzungen.py`). Die Anmeldeschranke (`app/anmeldeschranke.py`, aus `app/main.py`) setzt
    `Cache-Control: no-store` an jede Antwort an eine angemeldete Sitzung, auch an Dateien; `tests/test_v403_kein_cache.py` läuft alle
    GET-Routen ab. Tests mit echter Anmeldung binden die Schranke über `tests/anmeldung.py` ein, statt sie nachzubauen; im Klicktest ist
    jedes `k.cookies()` eine eigene Sitzung (nach dem Abmelden gilt sie nicht mehr). **Seit 1.8.103:** „Alle vertrauten Geräte abmelden“
    beendet alle anderen Sitzungen (`andere_beenden()`), ein Admin alle eines Benutzers (`POST /api/users/{id}/end-sessions`, seit 1.8.106 samt
    seiner vertrauten Geräte), der Feierabend in `/mobil` die Sitzung des Geräts (seit 1.8.106 `POST /api/field-view/feierabend`; der GET der
    Einsätze meldet nur "feierabend", kein GET schreibt); Rolle und Rechte gelten ab der nächsten Anfrage (Angriffstest `tests/test_v408_vorweg.py`). Ein Cookie ohne
    gültige Sitzung bekommt auf API-Anfragen 401 mit `X-DK-Anmeldung: abgelaufen`, der Baustein `_speichern.html` zeigt „Anmeldung abgelaufen“
    und lässt die Eingaben stehen. Details: `docs/archiv/befund-vor-echtbetrieb.md`, "Umsetzung 1.8.98" und "Umsetzung 1.8.103".
    **Einzige Ausnahme seit 1.8.127:** Design-Dateien unter `/static/` (Regel 37) gehen ohne Anmeldung und ohne Datenbank durch, wenn
    `app/design_dateien.py::ist_design_pfad()` sie annimmt (GET/HEAD, eng gefasster Pfad, nichts kodiert -- nie ein Präfixvergleich);
    eine Antwort 200 trägt dann `Cache-Control: public, max-age=31536000, immutable`, jede andere dort `no-store`.
    **Seit 1.8.128 gilt die Anmeldepflicht für jede Methode** (bis 1.8.127 nur GET und POST/PUT/PATCH/DELETE -- HEAD, OPTIONS, TRACE und
    erfundene Methoden kamen ohne Anmeldung bis zum Routing, HEAD auf `/openapi.json` und `/docs` lieferte 200): ohne gültige Sitzung eine
    Seite mit GET/HEAD → Umleitung auf `/login`, sonst 401; öffentlich nur `OEFFENTLICH` in `app/anmeldeschranke.py` (Pfad mit Methoden:
    `/login`, `/health`, `/manifest.json`, `/api/auth/status` mit GET/HEAD, `/api/auth/login` und `/logout` mit POST) und die
    Design-Dateien. Ein neuer öffentlicher Pfad kommt dort hinein, mit genau seinen Methoden (`tests/test_v433_schranke_alle_methoden.py`:
    Angriffe mit 7 Methoden gegen echten uvicorn, kein Endpunkt erreicht). **Seit 1.8.129:** `/health` beantwortet auch HEAD; die
    Schnittstellen-Doku (`/docs`, `/redoc`, `/openapi.json`) gibt es nur mit `ERP_API_DOKU=1` und `ERP_ENV=development`/`test`
    (`app/main.py::api_doku_aktiv()`), im Betrieb sind die Routen nicht angelegt (404, auch mit Anmeldung). **Seit 1.8.130 ohne Konto
    geschlossen** (bis dahin legte dann jeder über `POST /api/users` das erste Konto als Admin an): durch gehen nur `/health` und die
    Design-Dateien, eine Seite zeigt den Hinweis mit dem Befehl, alles andere 503 (`ersteinrichtung_antwort()`, nach der
    Ursprungsprüfung); das erste Konto legt nur `scripts/erstes_konto.py <benutzername>` auf dem Server an (`DATABASE_URL` Pflicht,
    Passwort verdeckt, nie als Argument). `POST /api/users` nur Admin, `/users` seit 1.8.134 auch nur Admin (bis dahin ab Büro – Auftrag); die PWA-Symbole
    `/api/mobile-icon/192.png` und `/512.png` öffentlich wie `/manifest.json` (GET, HEAD); die Akzentfarbe ändert nur ein Admin
    (`tests/test_v435_ersteinrichtung_geschlossen.py`).

31. **Jede abgelegte Datei geht über `app/dateiauslieferung.py::datei_antwort()` an den Browser, seit 1.8.101.** Den Typ bestimmt der
    Server an den ersten Bytes, nie am Namen oder an der Angabe des Browsers; angezeigt (inline) werden nur JPEG, PNG, GIF, WebP und PDF,
    alles andere kommt als Download (`application/octet-stream`, `attachment`, CSP `sandbox`), immer mit nosniff; SVG nur als Logo in
    `<img>` (`svg_als_bild=True`). Eine neue Ablage speichert `gespeicherter_typ()` statt der Angabe des Browsers; Vorschau und "Öffnen"
    nur über `is_image_type()`/`can_preview_type()` (`app/document_storage.py`). `tests/test_v406_dateien_nie_aktiv.py` hält `FileResponse`
    per AST im Modul und verlangt für jede andere Antwort mit Inhalt einen festen Typ (was der Server selbst erzeugt). Details:
    `docs/archiv/befund-vor-echtbetrieb.md`, "Umsetzung 1.8.101". Design-Dateien unter `/static/` (seit 1.8.127) sind keine abgelegten
    Dateien: `StaticFiles` nur in `app/design_dateien.py`, Typ fest nach Endung, nur `.css`, `.woff2` und Lizenztexte (Regel 37).

32. **Daten im HTML der Vorlagen nur über esc(), Handler ohne Werte, Links geprüft, seit 1.8.102.** Jeder Wert, der in HTML geht
    (Template-Literal oder Verkettung mit Markup, innerHTML/outerHTML/insertAdjacentHTML), steht in esc() -- es sei denn, er ist beweisbar
    ohne Markup (Zahl, ID "…_id" außer `TEXT_IDS`, Literal, Datum; Regeln im Kopf von `tests/vorlagen_html.py`). Ein on…-Attribut setzt
    keinen Wert ein: das Element trägt `data-klick`/`data-aenderung`/`data-eingabe` und seine Werte als data-Attribute (mit esc()), die
    Seite meldet `aktion('name', el => …)` an (`_aktionen.html`, liest `el.dataset` -- immer Text). Ein href/src/Navigation aus Daten geht
    über `sichererLink()`/`sichereBildquelle()` (`_links.html`) oder beginnt mit einem festen lokalen Pfad, mailto:, tel: oder http(s)://.
    `tests/test_v407_daten_im_html.py` prüft alle drei über alle Vorlagen; die Ausnahmelisten (Changelog; 260 Handler mit Zahlen/IDs) dürfen
    nur kürzer werden. Details: `docs/archiv/befund-vor-echtbetrieb.md`, "Umsetzung 1.8.102".

33. **Schreibende Anfragen nur von einer Seite des ERP, kein Einrahmen, Secure und HSTS, seit 1.8.104.** Die Anmeldeschranke lehnt
    jedes POST/PUT/PATCH/DELETE mit 403 ab, dessen `Sec-Fetch-Site` nicht `same-origin` ist (auch von einer Unterdomain derselben Site), ohne
    `Sec-Fetch-Site` dessen `Origin` nicht zu `Host` passt, oder ohne beides -- auch beim Anmelden (`app/anmeldeschranke.py::ursprung_passt()`).
    Jede Antwort trägt `X-Frame-Options: DENY` und `frame-ancestors 'none'` (an eine CSP des Endpunkts angehängt). **Seit 1.8.107** ist das
    Anmelde-Cookie `Secure`, außer mit `ERP_ENV=development` (lokal, `start_windows.bat`) oder `ERP_ENV=test` (Tests) -- fehlt `ERP_ENV`, bleibt es
    Secure (`app/auth.py::NUR_HTTPS`); dort trägt jede Antwort HSTS (`max-age=31536000`, ohne `includeSubDomains`). Auch die 500 aus dem
    Fehler-Handler trägt die Schutzkopfzeilen und nennt nichts aus dem Fehler (`serverfehler()`); Schranke und Handler bindet
    `app/anmeldeschranke.py::einbinden()` ein, in `app/main.py` wie in `tests/anmeldung.py`. Wer außerhalb des Browsers schreibt (Skript, Klicktest per urllib), schickt `Origin`; Tests über die
    echte Schranke nehmen `tests/anmeldung.py::browser_client()`. `tests/test_v409_ursprung_und_rahmen.py` (Angriffstabelle, Rundgang über
    alle GET-Routen), `tests/test_v412_hsts_und_fehlerseite.py`, Klicktest `klicktest_fremde_seite.py`. Details:
    `docs/archiv/befund-vor-echtbetrieb.md`, "Umsetzung 1.8.104" und "Umsetzung 1.8.107".

34. **Jede Zahleneingabe über `app/templates/_zahl.html`, seit 1.8.109.** Ein Zahlenfeld ist `<input type="text" inputmode="decimal"
    data-zahl>` (ganze Zahlen `inputmode="numeric" data-zahl="ganz"`), nie `type="number"` -- Chrome liest dort bei deutscher Sprache
    "1.250" still als 1,25 und gibt den Rohtext nicht heraus. Gelesen nur über `zahlFeld()` (Optionen auch aus dem Feld: `data-min`/
    `data-max`, `data-stellen`, `required`, Beschriftung aus `data-feld` oder dem Label) bzw. `zahlLesen()`, Anzeigen während der Eingabe
    über `zahlVorschau()`, gefüllt über `zahlText()`; gelesen wird vor dem ersten Speichern. Deutsches Format: Komma dezimal, Punkt nur als
    Tausender vor je drei Ziffern; Mehrdeutiges ("1.25") mit Meldung abgelehnt, das Feld bleibt markiert, `abschliessen()` sperrt solange
    (Regel 29). `tests/test_v414_zahleneingaben.py` (Scanner `tests/vorlagen_zahlen.py`) findet `type="number"`, parseFloat/parseInt,
    Komma ersetzen, jede Umwandlung eines Feldwerts (Number(), +, Rechnen) außerhalb des Bausteins -- Auswahllisten, Häkchen und Datum
    erkennt er über die ID --, den rohen Text eines Zahlenfelds und Füllen ohne `zahlText()`; `AUSNAHMEN` darf nur kürzer werden.
    Klicktest `klicktest_zahleneingaben.py`. Details: `docs/archiv/befund-vor-echtbetrieb.md`, "Umsetzung 1.8.109". **Seit 1.8.119** ist
    keine Grenze im Browser strenger als die des Servers: jedes Zahlenfeld und jeder Leseaufruf mit Grenzen steht in `ABGLEICH`
    (`tests/test_v424_zahlgrenzen.py`, Lesen in `tests/zahlgrenzen.py`) mit dem Schemafeld, Grenzen nur im Code mit Beleg; ein neues
    Feld mit Grenzen gehört dort hinein, eine neue Grenze im Browser auch auf den Server ("Umsetzung 1.8.119"). Ist-Mengen nehmen 0 an
    (seit 1.8.121 Wächter in `tests/test_v426_ist_menge_null.py`, Server und Browser). **Seit 1.9.17 auch jede Anzeige einer Zahl**
    (Satz, Menge, Stunden, Dateigröße) über `zahlText(wert, stellen)` -- nie Komma per `replace`, nie `toFixed` in der Anzeige (nur fürs
    Maschinenformat, je Vorlage gezählt in `MASCHINENFORMAT`), kein Dezimalfeld roh im HTML; Wächter `tests/test_v451_zahlformat_anzeige.py`.
35. **Keine Datenbank auf der Event-Loop, Sitzung vor dem Senden zu, eine Verbindung je Seite, seit 1.8.114.** Jeder Endpunkt bindet seine
    Sitzung mit `Depends(get_db, scope="function")` ein (FastAPI schließt sie, bevor die Antwort gesendet wird -- bis 1.8.113 hielt eine
    Datei ihre Verbindung samt offener Transaktion bis zum letzten Byte); ein Endpunkt oder eine Abhängigkeit mit Datenbank ist nie
    `async def` (ein Upload liest die Datei mit `file.file.read()`), die Anmeldeschranke liest im Threadpool (`_lesen()`). Jinja-Globals
    lesen nur die Seitendaten der Anfrage (`app/seitendaten.py`, von der Schranke in ihrer Sitzung mitgeladen, seit 1.8.120 nur für Seiten,
    die gezeichnet werden: `wird_gezeichnet()`, eine umleitende Seitenroute trägt `dk_ohne_seite(user, request)`) -- ein neuer Global mit
    Daten kommt dort in `laden()`, mit Rückfallwert. Ein leerer Pool ergibt 503 („ausgelastet“). Pool unter PostgreSQL in
    `app/database.py` (5 + 35 = Threadpool 40 je Prozess, 10 s, `pool_pre_ping`; `ERP_DB_*`, `.env.example`).
    `tests/test_v419_verbindungen.py` prüft jede Route und die Verbindungen je Seite, `tests/test_v419_verbindungen_unter_last.py` greift
    einen echten Server gegen PostgreSQL an (kleiner Pool, langsame Downloads, viele Seiten, gesperrte Tabelle). Details:
    `docs/archiv/serverbetrieb-und-anmeldesicherheit.md`, "Datenbankverbindungen unter Last".

36. **Eine JS-Ausnahme in einem node-Test lässt den Test scheitern, seit 1.8.116.** Jedes Seitenskript, das ein Test in node ausführt,
    läuft über `tests/node_lauf.py` (`node_ausfuehren()`/`node_lauf()`, auch `_node()` und `im_browser()`): ein Programmfehler (TypeError,
    ReferenceError, SyntaxError, RangeError, URIError, EvalError) lässt den Test scheitern, auch wenn die Seite ihn fängt -- eine Seite
    fängt fast jede Ausnahme und zeigt sie an, ein Test sah dann nur, dass "nichts Falsches" erscheint. Erlaubt nur mit Grund (`ERLAUBT`,
    `ERLAUBT_TEXT`, je Test `erlaubt=`). Was dadurch rot wird, ist ein Befund (Attrappe oder Seite) und wird behoben. Die Attrappe einer
    Seite (`seite()`) bindet genau die Bausteine ein, die die Seite einbindet. `tests/test_v421_node_ausnahmen.py` (AST: kein node-Lauf
    daran vorbei). Details: `docs/archiv/testablauf-und-klicktests.md`, "JS-Ausnahmen in node-Tests".

37. **Das Design-System liegt in `app/static/ds/ds.css`, jede Seite bindet `_ds_kopf.html` ein, seit 1.8.127 (Redesign Stufe 1).**
    `ds.css` enthält nur `--ds-*`-Eigenschaften in `:root` und `:root[data-theme="dark"]`, `@font-face` und Regeln, deren Selektoren alle
    als Ziel (letzter Teil nach Leerraum, `>`, `+`, `~`) selbst eine Klasse `.ds-…` tragen (seit 1.8.129; `.ds-x div`, `.ds-x + p`,
    `div:not(.ds-x)` verboten) -- nie `--accent` (die alten Namen stehen seit 1.9.5 in `ds-alte-namen.css`), kein `color-scheme`, keine
    Element-Selektoren, keine andere At-Regel. In `app/static/` liegen nur `.css`, `.woff2` und Lizenztexte (`ofl-*.txt`), alle Namen kleingeschrieben (sonst ohne
    Anmeldung nicht erreichbar), keine Symlinks. Jede Seite aus `seiten()` bindet `_ds_kopf.html` im Kopf vor ihrem eigenen `<style>` ein
    (`ds.css?v=<Prüfsumme des Inhalts>`, seit 1.9.2 aus `app/design_dateien.py::pruefsumme()`, bis dahin die Version); eine neue Seite ebenso. Seit 1.9.5 bindet `_ds_kopf.html` dazu `ds-alte-namen.css` ein: nur `:root`, nur die alten Farbnamen der Seiten, jeder auf einen `--ds-*`-Wert (`tests/test_v442_alte_farbnamen.py`). Seit 1.9.122 dazu `ds-gesperrt.css`: die eine Regel für gesperrte und nur lesbare Felder jeder Seite (Fläche `--ds-feld-gesperrt`, Schrift `--ds-text-2`, Mauszeiger „nicht erlaubt“, als einzige Stelle mit `!important`) -- keine Seite trägt eine eigene, eine Ausnahme nur mit `data-gesperrt-eigen` und Grund (`tests/test_v542_gesperrte_felder.py`). Die Prüfpaare im Kopfkommentar von `ds.css` halten hell und dunkel (Text 4,5 : 1,
    Bedienelemente 3 : 1). `/static/` wird ein Jahr zwischengespeichert: eine geänderte Schrift bekommt einen neuen Dateinamen.
    `tests/test_v432_design_fundament.py` (Wächter, Kontrast, Auslieferung, Angriffe über ASGI und echten uvicorn samt Gegenprobe
    „Präfixvergleich“), Klicktest `klicktest_ds_schriften.py`. Details: `docs/archiv/redesign.md`.

## Fachbegriffe & Domänenmodell

- **"Vorgang"** (in normalem Gespräch) = **Projekt** (`Project`) – wurde in der Sitzung explizit
  geklärt, da der Begriff auf mehrere Dinge hätte zeigen können.
- Kette: `Customer` → `Project` → `Quote` (Angebot) → `Order` (Auftrag) → `Invoice` (Rechnung) →
  `Reminder` (Mahnung).
- **Phase und Projektstatus aus den Daten** (seit 1.9.125, `app/akte.py`): je Auftrag Angebot · Auftrag · Ausführung (erste Buchung, begonnener Einsatz
  oder Bericht) · Abnahme (gültig, abgenommen) · Schlussrechnung (gültig bzw. abschließend aus Aufwand), die letzte erreichte ist die Phase
  (`phasen()`); der Projektstatus ist Anfrage (kein Angebot), Angebot (kein Auftrag) oder die früheste Phase der laufenden und pausierten Aufträge,
  sonst Abgeschlossen/Storniert (`projekt_status_alle()`, je Art eine Abfrage). Kein Feld von Hand: Status beim Anlegen oder Ändern eines Projekts 422;
  `projects.status` liest niemand mehr (`scripts/pruefe_projektstatus.py` nennt Abweichungen). Listen und Dashboard nehmen `status`/`status_label`.
- `Quote`: frei bearbeitbar, Status u. a. `entwurf`/`versendet`/`beauftragt`. Kann `is_template=True`
  sein (Mustervorgang) und/oder `archived=True`.
- `Order`: entsteht ausschließlich durch Beauftragung eines Angebots, ist ein **unveränderlicher
  LV-Snapshot**. Kein Entwurfsstatus – startet direkt bei „läuft“. **Seit 1.9.124 nur vier Status** (`app/auftragsstatus.py`: läuft, pausiert,
  abgeschlossen, storniert; bis 1.9.123 freier Text, beauftragt/arbeitsvorbereitung/in_ausfuehrung gingen in „läuft“ auf, Migration `8d3f6a2c91e7`),
  geändert nur über `status_aendern()` (`POST /api/orders/{id}/status`, unter der Sperre der Auftragszeile, Historie `OrderStatusChange`): Pausieren und
  Stornieren mit Begründung, Abschließen nach der Schlussrechnung oder „ohne Rechnung“ mit Begründung (nur ohne jede Rechnung), Fortsetzen; ein Status in
  PUT oder beim Beauftragen 422; seit 1.9.131 nimmt nur der Admin einen Storno zurück (`storno_zuruecknehmen()`, mit Begründung, zurück auf
  „läuft“). Wirkung: pausiert keine Sperre; abgeschlossen und storniert kein neuer Einsatz, nicht in der Plantafel, die Monteurin
  bucht nicht; storniert dazu kein neuer Bericht (jede Rolle) -- je 409; Rechnungen und Buchungen des Büros bleiben (`tests/test_v544_auftragsstatus.py`).
  Seine Revisionen (`OrderRevision`) entstehen seit 1.8.110
  unter der Sperre der Auftragszeile in der Transaktion der Änderung, die sie sichern: `create_order_revision()` committet nie
  selbst, der Aufrufer committet beides zusammen.
- `Invoice`: `entwurf` bis zur Finalisierung (vergibt Nummer aus Nummernkreis), danach
  unveränderlich außer über eine Stornorechnung. Seit 1.8.72 je Auftrag höchstens eine nicht stornierte Schlussrechnung (auch
  Entwurf), danach keine Abschläge; je Rechnung höchstens ein Storno, keins eines Stornos oder eines verrechneten Abschlags; bis R4
  keine Schlussrechnung neben einem pauschalen Abschlag -- geprüft beim Anlegen und Festschreiben unter der Sperre der
  Auftragszeile (`app/invoices.py::lock_order_invoices()`, Gründe `*_block_reason()`, `InvoiceBlocked` = 409). Seit 1.8.74
  hat jede Rechnung einen Leistungszeitraum (`service_period_start/_end`, Ende >= Beginn, auf dem PDF), Pflicht beim
  Festschreiben (409); der Vorschlag mit Quelle (`app/service_period.py::proposal()`) wird nur per Klick übernommen, nie still
  eingetragen; Storno übernimmt den Zeitraum; Altbestand ohne Zeitraum bleibt. Seit 1.8.75 ist das Rechnungsdatum der Tag des
  Festschreibens in Berlin (`finalize_dates()`, die Fälligkeit rückt mit dem Zahlungsziel des Entwurfs mit; der Entwurf trägt bis
  dahin das Datum seines Anlegens), und jeder schreibende Weg an einer Rechnung läuft unter der Sperre der Auftragszeile
  (`_lock_draft()` vor jeder Änderung am Entwurf: nur, was danach noch Entwurf ist, sonst 409) --
  `tests/test_v378_rechnung_sperre_und_datum.py` prüft das per AST und Rundgang mit Beobachter; neue Schreibwege nur in
  `app/invoices.py`, mit Sperre vor dem ersten Schreiben. Seit 1.8.78 kein Status "bezahlt" mehr (nur `entwurf`/`versendet`/
  `storniert`, `paid_date` wird nicht mehr geschrieben): der Zahlstand ist abgeleitet, siehe "Zahlung". Seit 1.8.79 hält die
  Rechnung beim Festschreiben ihren Kunden fest (`Invoice.customer_id`, Storno: der der stornierten; `invoice_customer()`): Zahlungen,
  offene Rechnungen des Kunden und die Empfängeradresse folgen ihm; Kundenwechsel am Projekt mit festgeschriebener Rechnung 409
  (`check_client_change()`, unter der Sperre der Auftragszeilen). Seit 1.8.80 (Z2b "Vorweg" 1) hält der Auftrag seinen Kunden
  (`Order.customer_id`, Vertragspartner, beim Beauftragen unter der Sperre der Projektzeile); die Rechnung übernimmt beim Festschreiben
  Kunde, Name, Kundennummer und Anschrift vom Auftrag. Kundenwechsel am Projekt mit Auftrag nur mit Begründung
  (`customer_change_reason`), der Auftrag wechselt mit (`app/orders.py::change_orders_customer()`, Historie `OrderCustomerChange`,
  Rechnungsentwürfe ebenso), nie mit festgeschriebener Rechnung oder Vertrag. Seit 1.8.82 (R4a) entsteht das PDF beim Festschreiben
  als feste Fassung in der Ablage (Regel 21), und der Auftrag ist nicht mehr frei änderbar (`app/order_locks.py`, `OrderLocked` = 409
  mit Grund, unter der Sperre der Auftragszeile): Einheitspreis, Einheit und "in Summe" einer Position gesperrt, sobald eine gültige
  Rechnung sie abrechnet (Verweis, Ist ≠ 0); der Steuerschlüssel ab der ersten gültigen Rechnung; Mengen und Texte bis zur
  Schlussrechnung, danach alles (Positionen, LV-Titel, Steuerschlüssel, Abgleich mit dem Angebot). Seit 1.8.83: ein Nachtrag ist
  eine gekennzeichnete Auftragsposition (`OrderItem.is_addendum`, "N1" …, `app/orders.py::add_order_addendum()`, entfernen nur ohne
  Anhänge), jede folgende Rechnung übernimmt ihn; freie Positionen ohne Auftragsbezug nur in Rechnungen aus Aufwand (`FREE_ITEM_TEXT`,
  409); kein negativer Abschlag nach Leistungsstand; "letzter Stand" einer Position = der zuletzt festgeschriebenen Rechnung
  (`Invoice.finalized_at`, je Auftrag streng steigend). Seit 1.8.85 (R4b) ist die Schlussrechnung eine **Endrechnung**
  (`app/invoices.py::final_breakdown()`): Positionen mit voller Ist-Menge (Vorschlag: Menge des Auftrags) und Rechnungen aus Aufwand =
  Gesamtleistung, abzüglich jeder festgeschriebenen, nicht stornierten Abschlagsrechnung und Rechnung aus Aufwand mit Netto/USt/Brutto;
  Rechnungsbetrag = Gesamtleistung − Abzüge (`compute_invoice_totals()`, für Zahlungen und "abgerechnet"); Abzüge beim Festschreiben
  eingefroren (`InvoiceDeduction`, unveränderlich), im Entwurf live. Beim Festschreiben jeder Art neu gerechnet (`_recompute_draft()`)
  und gegen den Auftrag geprüft (`order_deviation_reason()`: Preis, Einheit, Steuerschlüssel, Positionen; 409, Ausweg
  `refresh_draft_from_order()`); Preis, Einheit und Steuerschlüssel eines Entwurfs nur aus dem Auftrag. Abschlag nur über 0 €,
  Schlussrechnung nicht unter 0 € (bis R4c); nach der gültigen Schlussrechnung keine Rechnung aus Aufwand. Seit 1.8.86: Zahlungshinweis
  der Endrechnung "Stand <Tag>" (`payment_note()`: je abgezogener Rechnung noch offen samt Einbehalt, Zahlbetrag; beim Festschreiben an
  den Abzügen eingefroren, nur Hinweis -- Betrag der Rechnung bleibt der Rechnungsbetrag); ein **Auftrag nach Aufwand** (Auftragssumme
  0 €, `effort_only()`) schließt mit einer abschließenden Rechnung aus Aufwand ab (`Invoice.closes_order`, `closing_invoices()`:
  vollständig abgerechnet und gesperrt wie nach der Schlussrechnung), eine Schlussrechnung gibt es dort nicht. Seit 1.8.95 lauten über
  0 € oder weniger nur ein Storno und eine Endrechnung mit Abzügen; jede andere Rechnung (auch eine abschließende aus Aufwand und eine
  Schlussrechnung ohne Abzüge) muss über 0 € liegen, sonst 409 beim Festschreiben (`amount_block_reason()`, nach der Neuberechnung unter
  der Sperre).
- **Zahlung** (`Payment`, seit 1.8.78, Zahlungsstufe Z1, `app/payments.py`): Zahlungseingang eines Kunden (Eingangsdatum, Betrag,
  Notiz), zugeordnet über `PaymentAllocation` (Art `zahlung`, Abzüge `skonto`/`einbehalt`) auf festgeschriebene Rechnungen desselben
  Kunden (seit 1.8.79 der an der Rechnung festgehaltene); der Rest bleibt am Kunden (Kundenakte). Je Rechnung abgeleitet, nie gespeichert (`payment_state()`):
  offen = Brutto auf den Cent − Zahlungen − Skonto, mahnfähig = offen − Einbehalt (der Einbehalt deckt höchstens den offenen Betrag),
  Zustand offen / teilweise bezahlt / Einbehalt offen / bezahlt; Entwurf, Storno(rechnung) und Rechnung über 0 € oder weniger haben
  keinen. Vorschlag (`proposal()`) zuerst auf ältere offene Rechnungen desselben Auftrags, Skonto nur in der Frist und bei passendem
  Betrag, Einbehalt nie; gebucht wird nur Bestätigtes (`book_payment()`, `allocate_rest()`), ohne Überbuchung von Rechnung oder
  Zahlung. Unveränderlich (ORM-Sperre); Korrektur nur als Gegenbuchung mit Begründung (`reverse_allocation()`, `reverse_payment()`).
  Sperren in fester Reihenfolge: Auftragszeilen aufsteigend, dann Zahlung (`lock_for_booking()`). Storno erst nach gelösten
  Zuordnungen (`storno_block_reason()`). Mahnwesen: mahnfähiger Betrag, ohne ihn keine Mahnung (seit 1.8.79 Z2a, siehe `Reminder`).
  Migration `c7d41e9a2b63` übernahm "bezahlt" als Zahlung (Herkunft `uebernommen`). **Seit 1.8.81** auch auf Nebenforderungen (Art
  `nebenforderung`, `charge_id` einer Nebenforderung derselben Rechnung): mindert sie, nicht den Zahlstand der Rechnung; Vorschlag nach
  § 367 BGB -- je Rechnung erst Kosten (Gebühr, Pauschale), dann Zinsen, dann die Rechnung, die älteste Rechnung zuerst --, das Büro
  bestätigt (auch abweichend); höchstens der offene Rest, nur unter der Sperre der Auftragszeile. Details: `docs/archiv/zahlungen.md`.
  **Seit 1.8.89 (R4c Punkte 3–5, `app/final_dunning.py`)**: mit einer gültigen Endrechnung (Schlussrechnung mit Abzügen) wird eine darin
  abgezogene Rechnung nicht mehr einzeln gemahnt (nicht fällig, kein Entwurf, ein offener überholt, eine festgeschriebene Mahnung geht ab
  dem Tag der Endrechnung nicht mehr hinaus), ihr Einbehalt ist mit der Endrechnung fällig, und die Mahnung der Endrechnung lautet über
  den Zahlbetrag (ihr mahnfähiger Betrag + offene abgezogene Rechnungen, Aufstellung Format 4 je Rechnung mit Nummer); `DunningState`
  ist überall im Mahnwesen der Stand (`dunnable` = angemahnter Betrag), auch für Verzugszinsen und "überfällig". **Seit 1.8.90 (Punkte
  6–7)**: eine Schlussrechnung darf unter 0 € lauten; ein negativer Zahlbetrag ist ein Erstattungsbetrag (PDF "Erstattung", ohne Skonto
  und "zahlbar"; Skonto nur über 0 €); das Guthaben (`DunningState.credit`) steht am Kunden und wird als Zahlungsausgang erstattet
  (`app/payments.py::book_refund()`: Zahlung mit negativem Betrag, Zuordnung Art `erstattung`, nur als Ganzes zurück); die E-Mail nennt
  Zahl- bzw. Erstattungsbetrag (`{zahlbetrag}`, `{erstattungsbetrag}`, `{zahlungshinweis}`, sonst eigener Absatz). **Seit 1.8.91
  (Nacharbeiten R4c, Punkt 1)**: Finanzen, Dashboard und die Rechnungslisten zählen nach der gültigen Endrechnung je Auftrag nur ihren
  Zahlbetrag -- positiv offen, negativ Guthaben (`app/final_dunning.py::overview()`, als `overview` an jeder Rechnungszeile); eine darin
  abgezogene Rechnung mit offenem Betrag heißt "enthalten in Schlussrechnung R-…", ihr eigener Zahlstand bleibt (Karte "Zahlungen").
  **Seit 1.8.92 (Punkt 2)**: bei negativem Zahlbetrag druckt die Schlussrechnung statt des Schlusstexts (Zahlungsaufforderung) den
  Standard-Eintrag der Auswahlliste "Rechnungs-Schlusstexte bei Erstattung" (`app/invoices.py::refund_outro_text()`, im Entwurf live,
  beim Festschreiben in `outro_text` eingefroren). **Seit 1.8.93 (Punkt 3)**: das Guthaben des Kunden sind die nicht zugeordneten
  Reste seiner Zahlungen und die Guthaben aus Endrechnungen zusammen (`app/payments.py::customer_balance()`, je Kunde für Finanzen und
  Dashboard `customer_balances()`); ein Zahlungsausgang erstattet beides (`book_customer_refund()`, aus einem Rest über
  `PaymentRefundSource`: Rest der Zahlung sinkt, nur als Ganzes zurück, die Zahlung selbst erst danach). **Seit 1.8.94** (vor dem
  Abnahmetest): „Bezahlt (gesamt)“ in Finanzen abzüglich der Erstattungen an Schlussrechnungen (`overview.refunded`); Zahlbetrag genau
  0 € -> fester Satz statt der Zahlungsbedingungen, kein Schlusstext (`app/invoices.py::nothing_due()`, im Entwurf live, beim
  Festschreiben eingefroren); „Zahlung zurücknehmen“ nur ohne Grund (`app/payments.py::reverse_block_reason()`); enthaltene Rechnungen
  im Zahlungsdialog und bei „Rest zuordnen“ gruppiert unter ihrer Schlussrechnung (`settled_in`, `_zahlung_gruppen.html`).
- `Reminder`: hängt an überfälligen Rechnungen, hat Stufen (1./2./3. Mahnung), jede Stufe mit
  eigenen Fristen/Gebühren/Textvorlagen (`ReminderLevel`). `Reminder.text` ist beim Anlegen
  (`create_reminder()`) eine reine Kopie von `ReminderLevel.text_template` mit noch
  unaufgelösten Platzhaltern (`{mahngebuehr}` usw.) – `formatted_text` (`reminder_to_dict()`)
  wird bei JEDEM Lesezugriff frisch aus `text` + den aktuellen Feldwerten zusammengesetzt
  (`format_reminder_text()`/`_reminder_placeholders()`), nie gespeichert oder gecacht. Solange
  `status="entwurf"` ist, lässt sich `text`/`fee_amount`/`new_due_date` über
  `update_reminder_draft()` (seit 1.3.21, `PUT /api/reminders/{id}`) ändern – Statusschutz sitzt
  in der Geschäftsfunktion selbst, gleiches Muster wie `update_report()` beim Einsatzbericht,
  siehe Abschnitt "Mahnwesen: Löschen/Versenden/Bearbeiten" unten. Nach `finalize_and_send_reminder()`
  (Status `versendet`, Nummernvergabe) unveränderlich wie `Invoice`/`Order` (Regel 5). **Seit 1.8.79 (Z2a, `app/reminders.py`)**:
  kein Entwurf von selbst -- "zur Mahnung fällig" liest nur, Entwürfe per Klick einzeln oder für mehrere (`create_reminders()`);
  `create_block_reason()` beim Anlegen und Festschreiben unter der Sperre der Auftragszeile (nichts zu mahnen, nicht fällig = vor dem
  Tag nach der Fälligkeit, höchstens ein Entwurf, nur die nächste aktive Stufe, die erst ab dem Tag nach dem Fristende der vorigen);
  je Stufe eine Zahl, die Zahlungsfrist (`ReminderLevel.days_after_previous_step`, Name von früher); Bearbeiten und Löschen unter der
  Sperre, Frist im Entwurf in Tagen, Mahndatum = Tag des Festschreibens; Aufstellung (Brutto, Zahlungen, Skonto, Einbehalt,
  mahnfähig) eingefroren in `Reminder.amounts_json`; E-Mail und nachgetragene Zustellung nur mit passendem Betrag und nicht storniert
  (`dispatch_block_reason()`, Zustellung: Stand am Zustelltag). Details: `docs/archiv/zahlungen.md`, "Umsetzung 1.8.79".
  **Seit 1.8.80 (Z2b)**: erreicht ist eine Stufe erst mit Versand oder Zustellung (`reached_map()`,
  `app/email_dispatch.py::document_reached_on()`); eine festgeschriebene, nie hinausgegangene Mahnung ersetzt eine neue derselben Stufe
  beim Festschreiben (`Reminder.replaced_by_id`, danach geht sie nicht mehr hinaus, ihre Nebenforderungen werden gegengebucht).
  **Nebenforderung** (`InvoiceCharge`, `app/dunning_charges.py`): Mahngebühr oder Pauschale nach § 288 Abs. 5 BGB je Rechnung, nie im
  Rechnungsbetrag, ohne USt, unveränderlich, Gegenbuchung mit Begründung; entsteht beim Festschreiben einer Mahnung aus dem, was ihr
  Entwurf bewusst übernahm (`fee_accepted`/`flat_fee_accepted`, `PUT /api/reminders/{id}/charges`); jede Mahnung zeigt die geltenden
  aufsummiert (Aufstellung Format 2). Zuschaltbar: `GeneralSettings.dunning_charges_enabled`, nur Admin, Vorgabe aus -- aus heißt keine
  Gebühr, keine Beträge; vor dem Einschalten `docs/archiv/zahlungen.md`, "Vor dem Einschalten der Mahngebühren" lesen. Pauschale nur ohne Verbraucher, einmal je Rechnung, ab bestätigtem **Verzugsbeginn** (`InvoiceDefaultStart`,
  Vorschlag aus dem Zugang der ersten Mahnung bzw. 30 Tagen nach Fälligkeit und Zugang der Rechnung). Details:
  `docs/archiv/zahlungen.md`, "Umsetzung 1.8.80". **Seit 1.8.81 (Punkte 7–9)**: **Verzugszinsen** (`app/default_interest.py`) als
  Vorschlag im Entwurf bis zum Mahndatum (`interest_accepted`), beim Festschreiben frisch unter der Sperre berechnet und eine
  Nebenforderung Art `zinsen` mit Zeitraum und eingefrorener Berechnung: Basiszinssatz je Halbjahr (`BaseInterestRate`, nur Admin,
  geprüft; fehlt ein Halbjahr oder ist es ungeprüft, kein Vorschlag) + 5 bzw. 9 Punkte, ab dem Tag nach dem Zugang der Mahnung (30-Tage-
  Regel: ab dem 31. Tag), auf den mahnfähigen Betrag, Abschnitte ab Zahlungseingang und Halbjahr, tatsächliche Tage durch 365, je Abschnitt
  exakt, einmal am Ende kaufmännisch gerundet; Anschluss an schon berechnete. Keine Gebühr neben gebuchter oder übernommener Pauschale
  (§ 288 Abs. 5 S. 3 BGB, `fee_block_reason()`); Storno nur ohne offene Nebenforderungen (`charges_storno_block_reason()`); Gegenbuchung
  einer Nebenforderung erst nach gelöster Zuordnung. **Rechtstexte** zu Verzug, Zinsen, Pauschale (`app/dunning_texts.py`, nur Admin,
  geprüft) druckt die Mahnung nur geprüft und zum genannten Thema, eingefroren in der Aufstellung (Format 3); ungeprüft warnt der
  Entwurf. Vor dem Ersetzen nennen Liste, Editor und Rückfrage die gegengebuchten Nebenforderungen. Details: `docs/archiv/zahlungen.md`,
  "Umsetzung 1.8.81".
- **`Property`** ("Objekt", `app/models.py`): eigenständige Tabelle (`customer_id`, `name`,
  `street`, `postal_code`, `city`, `notes`) für ein zusätzliches Gebäude/Objekt eines Kunden
  über dessen eigene Hauptadresse hinaus. Per 09.09.2026 verifiziert (siehe
  `docs/bestandsaufnahme.md` Abschnitt 3, seither um `RoofArea` ergänzt): **vier** Stellen im
  Projekt referenzieren `properties.id` per FK – `Inquiry.property_id`, `Project.property_id`
  (beide optional, bidirektionale Relationship), `MaintenanceContract.property_id` (optional,
  unidirektional) und seit 1.2.14 `RoofArea.property_id` (Pflicht, bidirektional, **mit**
  `cascade="all, delete-orphan"` – anders als bei `projects`, siehe eigener Abschnitt unten).
  `Order` und `Invoice` haben **kein** `property_id` – nur `property_name`/`property_address`
  als reinen Text-Schnappschuss zum Zeitpunkt der Beauftragung/Rechnungsstellung. Wer von einem
  `Order` zum zugehörigen `Property` will, muss über `order.project.property_id` gehen (siehe
  `list_property_history()` in `app/service_reports.py`).
- **Adressbuch und Beteiligte** (seit 1.8.37): `Contact` ist eine Person oder Firma, die an Projekten beteiligt ist,
  ohne Kunde zu sein (Architekt, Hausverwaltung, Sachverständiger …); `ProjectParticipant` ordnet sie mit einer festen
  Rolle (`app/project_participants.py::ROLES`) einem Projekt zu, eindeutig je Projekt, Kontakt und Rolle. Der Kunde ist
  Auftraggeber und nie Beteiligter. Seit 1.8.39 auch ein Eintrag mit Verweis auf Kunde oder Lieferant
  (`Contact.customer_id`/`supplier_id`, höchstens einer je Stammsatz): Name, Kontaktwege, Adresse kommen live aus dem
  Stammsatz (`contact_values()`), Suche/Sortierung brauchen `with_sources()`. Seit 1.8.41 lehnt ein Kundenwechsel am
  Projekt ab (409), wenn der neue Kunde dort schon Beteiligter ist (`check_client_change()`). Details:
  `docs/archiv/vertragsgrundlage-und-vertrag.md`, "Umsetzung 1.8.37" und "Umsetzung 1.8.39".
- **Behinderungsanzeige** (seit 1.8.38): eine Checkliste mit Zweck `behinderungsanzeige` (Systemfelder in
  `app/checklist_purposes.py`): Meldung (meist Monteur) → Anzeige (nur Büro) → Wegfall, je mit Unterschrift; nach der
  Unterschrift der Meldung die Aufgabe "Behinderungsanzeige versenden" (`app/obstruction_notices.py`). Seit 1.8.40 Brief an den
  Auftraggeber (`app/notice_letters.py`): Behinderungsanzeige nach der Unterschrift Büro, Anzeige der Wiederaufnahme nach dem
  Wegfall, Inhalt aus der versiegelten Kopie der Unterschrift, Fassung je Unterschrift in der Ablage, Vorbehalt nur geprüft,
  An immer der Auftraggeber, CC seit 1.8.69 fest die Personen unter "Kopie an:" im Brief (Adresse von heute, wie beim
  Abnahmeprotokoll). Seit 1.8.41: Zeitstrahl (bekannt seit → Meldung → versendet), "versendet" heißt beim
  Auftraggeber angekommen (`reached_client()`: nicht unzustellbar, keine reine Kopie an Beteiligte), Wiederaufnahme "i. A."
  mit dem Büro-Konto statt der Wegfall-Unterschrift, Status `gegenstandslos` (`void_checklist()`, auch Bedenkenanzeige, nur
  Büro, mit Begründung versiegelt, keine Folgen/Briefe mehr). Details: `docs/archiv/vertragsgrundlage-und-vertrag.md`,
  "Umsetzung 1.8.38", "Umsetzung 1.8.40" und "Umsetzung 1.8.41".
- **Bedenkenanzeige** (seit 1.8.43): Checkliste mit Zweck `bedenkenanzeige` nach dem Muster der Behinderungsanzeige: Meldung →
  Anzeige (nur Büro, "Entscheidung erbeten bis") → Entscheidung des Auftraggebers (nur Büro), je mit Unterschrift. Folgen
  (`app/concern_notices.py`): nach der Meldung "Bedenkenanzeige versenden", nach dem Versand (`FollowUp.after_letter`)
  "Antwort des Auftraggebers prüfen", nach der Unterschrift der Entscheidung erledigt. Ohne gültige Unterschrift der
  Entscheidung zeigen Auftragsseite und `/mobil` "Offene Bedenken …" (`open_concerns()`). Seit 1.8.44 Brief und Versand wie
  die Behinderungsanzeige (Briefarten je Zweck in `app/notice_letters.py`: `NOTICE_PURPOSES`, `LetterKind.purpose`); weicht der
  Kunde des Projekts vom Kunden laut Auftrag ab (`customer_mismatch()`), entstehen und gehen Briefe beider Anzeigen nur mit
  Bestätigung; Kundenwechsel im Projekt gesperrt, sobald ein Auftrag einen festgeschriebenen Vertrag hat. Seit 1.8.45
  ist "Antwort als Beleg" ein Feld vom Typ `beleg` (PDF oder Foto), und den Hinweis zeigen auch Einsatzbericht- und
  Checklisten-Seite des Auftrags, für Büro und Monteur (`_offene_bedenken.html`, Link nur, wo der Monteur öffnen darf).
  Details: `docs/archiv/vertragsgrundlage-und-vertrag.md`, "Umsetzung 1.8.43" und "Umsetzung 1.8.45".
- **Abnahme und Gewährleistung** (seit 1.8.46, Stufe 2c): am Auftrag Leistungsart (`work_kind`) und
  Gewährleistungsdauer (`warranty_months`/`warranty_days`), leer = "nicht festgelegt", gesetzt nur bewusst über
  `app/warranty.py::set_order_warranty()` (Vorschlag je Vertragsgrundlage mit Fundstelle, Abweichung mit Begründung).
  `OrderAcceptance` (mehrere je Auftrag, `app/acceptances.py`): nach dem Speichern unveränderlich (ORM-Sperre, Belege
  schreibgeschützt mit SHA-256, `content_sha256` über den Inhalt), Korrektur nur durch Verwerfen mit Begründung und
  einen neuen Eintrag. Das Gewährleistungsende wird nie gespeichert, sondern aus Abnahmedatum und Dauer abgeleitet
  (`warranty_end()`, § 188 Abs. 2/3 BGB, angezeigt als "Gewährleistung regulär bis" -- ohne Hemmung oder Neubeginn). Eine
  nicht verworfene Abnahme sperrt den Abgleich mit dem Angebot und (seit 1.8.47) jede Änderung von Leistungsart oder
  Dauer ohne Begründung. Beim Erklärenden zählt nur die "Vollmacht zur Abnahme" am Beteiligten
  (`acceptance_authorized` + Beleg), nicht die Empfangsvollmacht.
  `RoofArea.third_party_guarantee_until` ist die Garantie Dritter (Hersteller/Fremdfirma), nicht die Gewährleistung des
  Betriebs. Seit 1.8.48 kommt jedes angezeigte Gewährleistungsende samt Prüfstatus aus `acceptance_warranty()`.
  **Mangel** (`Defect`, seit 1.8.49, `app/defects.py`, bewusst nicht der Befund `Finding`): nur an einer nicht verworfenen
  Abnahme mit Vorbehalt Mängel oder Verweigerung (`acceptance_allows_defects()`), unveränderlich wie die Abnahme; Haltung,
  Status und Freigabe zur Beseitigung sind verkettete Einträge (`DefectEvent`), der Stand ergibt sich aus ihnen
  (`defect_state()`); beim Erfassen eine Aufgabe im Büro-Eingang, die die Erledigung des Mangels mit erledigt (umgekehrt nicht),
  seit 1.8.51 mit Kurzfassung der Beschreibung im Titel; Fotos und Belege nur ergänzen. Seit 1.8.52 sieht der Monteur in
  `/mobil` freigegebene, offene Mängel seiner Aufträge (`field_may_see_defect()`, Antwortschema `FieldDefectOut` als
  Positivliste) und meldet "beseitigt" mit Foto, idempotent über `DefectEvent.client_uuid`. Seit 1.8.54 folgt die Aufgabe
  dem Status ("beseitigt" -> "Beseitigung abnehmen lassen", zurück auf offen -> wieder "Mangel beseitigen", am Eintrag
  `DefectEvent.task_id`, aktuelle über `current_task()`), die Meldung trägt optional einen Hinweis des Monteurs, nur fürs Büro.
  Seit 1.8.55 trägt "zurück auf offen" optional eine neue Beseitigungsfrist (`DefectEvent.due_on`, nicht vor heute); Aufgabe,
  Büro und `/mobil` nutzen die aktuelle (`current_due()`). Seit 1.8.60 auch aus dem Feld "Mängel" eines Abnahmeprotokolls
  (`source` "protokoll", `Defect.checklist_id`, gebundener Inhalt mit der Checkliste statt der Abnahme): je Mangel Kennung und
  Prüfsumme in der Kopie jeder Unterschrift darunter -- ob ein verworfener dazugehört, sagt seit 1.8.62 die Kopie selbst,
  kein Zeitvergleich (`defect_in_seal()`, `sealed_defect_ids()`); nach der Unterschrift keine neuen; bis zur Abnahme aus dem
  Protokoll nur verwerfbar (`protocol_pending()`).
  **Abnahmeprotokoll** (seit 1.8.61): Checkliste mit Zweck `abnahme`, nur Büro (`ChecklistPurpose.office_only`), Systemfelder
  Befund / Erklärungen des Auftraggebers / Schluss; Unterschrift des Auftraggebers mit Unterzeichner `ag_oder_beteiligter`,
  davor prüft `app/acceptance_protocol.py::check_customer_signature()` die Widersprüche (Mängel ohne Vorbehalt, Vorbehalt ohne
  Mangel, "verweigert" ohne Mangel) und was die Abnahme nicht annähme (seit 1.8.63 zum Schluss `check_acceptance()`, dieselbe
  Prüfung wie von Hand). Seit 1.8.63 legt die Folge danach die **Abnahme aus dem Protokoll** an
  (`acceptance_from_protocol()`, über `create_acceptance(…, protocol=ProtocolSource)`): je Unterschrift höchstens eine (UNIQUE
  `order_acceptances.checklist_attachment_id`, Folge `per_signature`), förmlich, Nachweis = Verweis auf die Unterschrift
  (Prüfsummenformat 3), Datum der Unterschrift in Europe/Berlin, Werte aus der versiegelten Kopie, Erklärender samt eingefrorener
  Vollmacht aus der Unterschrift; im selben Commit die Mängel der Kopie (bedingtes UPDATE, von leer oder einer verworfenen
  Abnahme) mit Aufgabe. Die Unterschrift lässt sich nicht verwerfen, solange die Abnahme gilt; eine neue Abnahme nur über eine
  neue Unterschrift. Ausstehende am Auftrag mit Grund und "Abnahme jetzt anlegen"; an einer Abnahme aus dem Protokoll keine
  Mängel von Hand. Seit 1.8.64 Erklärungen und Mängel gebündelt auf der Protokollseite und im PDF (`protocol_summary()`, nach
  der Unterschrift aus ihrer Kopie; im PDF die Mängel im Protokoll ohne Begründungen, seit 1.8.68 mit den Fotos beim Erfassen --
  nur wenn der Mangel zur Kopie passt, verkleinert). Seit 1.8.65 zählt für
  "bleibt im Protokoll" überall die erste gültige Unterschrift unter dem Feld (`protocol_defect_ids()`, auch für jede weitere
  Kopie und die Abnahme); eine unlesbare oder abweichende Kopie gilt nie als "ohne Mängel" (`SealedCopyError`, sichtbarer Fehler,
  `logger.error`, keine Unterschrift/kein Abschluss darunter). Seit 1.8.66 feste Fassung je Unterschrift (`app/checklist_versions.py`),
  seit 1.8.67 Versand an den Auftraggeber über den Weg der Anzeigen (`app/protocol_dispatch.py`: An fest, CC "Kopie bei Anzeigen",
  "Kopie an:" im PDF, nur die jüngste gültige Fassung, Prüfung vor dem Senden unter der Zeilensperre) und die Abnahme verweist auf
  die Fassung ihrer Unterschrift (Prüfsummenformat 4). Seit 1.8.68 CC genau die in der Fassung eingefrorenen Empfänger, seit 1.8.69
  als Personen an ihre Adresse von heute (`app/frozen_copies.py`, auch für die Briefe der Anzeigen), Hinweis vor dem Versand mit alter
  und neuer Adresse (`changes()`), wer keine Mail bekam im Versandverlauf (`DispatchCopy`).
  Seit 1.8.50 setzt `{gewaehrleistung}` in Vertragsvorlagen die Dauer ein; ein Vertrag damit wird erst mit festgelegter Dauer
  festgeschrieben, danach sind Leistungsart und Dauer gesperrt (`warranty_contract_lock()`, Sperrreihenfolge Vertrag ->
  Auftrag wie beim Abgleich). Details: `docs/archiv/abnahme-und-gewaehrleistung.md`.
- **Weitere Fachbegriffe ausgelagert**: Dachflächen & Bauteile, Wartungsvertrag,
  Einsatzbericht, Rechnung aus Zeitbuchungen, Schnellauftrag, Wartungshistorie und
  Monteursansicht stehen vollständig in `docs/archiv/modul-wartungen-und-monteursansicht.md`;
  Aufgabe (`Task`) in `docs/archiv/modul-aufgaben.md` -- beide vor einer Änderung an diesen
  Bereichen lesen (siehe Regel 14).
- **Zeiterfassung (`TimeEntry`)**: hängt zwingend an einem `Order` (`order_id` NOT NULL,
  `order_item_id` optional), Status nur `running`/`booked` (kein Enum). `activity` ist ein
  freier String, fachlich befüllt über die konfigurierbare Optionsgruppe
  `time_entry_activities`. `TimeEntryGroup`/`TimeEntryGroupMember` bilden Gruppen-Zeitbuchungen
  mehrerer Mitarbeiter gleichzeitig ab (bisher hier nicht dokumentiert). Details, inkl. wie
  Zeitbuchungen zu einem Auftrag aufgelöst werden: `docs/bestandsaufnahme.md` Abschnitt 6.
  `entry_type` ist entgegen einer früheren Beschreibung KEIN hart geschlossener Satz (nur weich
  gegen `app/time_tracking.py::ENTRY_TYPES` geprüft) -- seit 1.5.3 kommen `weather_winter`/
  `weather_summer` (Schlechtwetter Winter/Sommer) dazu, beide `counts_as_productive=False`
  (`entry_type_is_productive()`), siehe Abschnitt "Schlechtwetter-Zeitarten und
  Abwesenheitskategorie" unten.
- **Plantafel**: verplant wird ein Zeitabschnitt (`PlanningSlot`) je Auftrag **×** Team, nicht
  eine einzelne LV-Position und nicht direkt ein einzelner Mitarbeiter. `Team`/`TeamEmployee`
  ist eine dauerhafte, zeitlose n:m-Mitgliedschaft; beim Zuweisen eines Teams zu einer
  Arbeitsvorbereitung friert `WorkPreparationTeamAssignment` die damalige Besetzung als
  Snapshot ein. UI: Gantt-artige Zeitachse mit Drag & Drop – **funktioniert auf Touch-Geräten
  nicht** (native HTML5-DnD-API), Klick-Fallback-Dialog aber schon. Details:
  `docs/bestandsaufnahme.md` Abschnitt 7 und 10.
- **Mustervorgang** (`Project.is_template`): technisch ein ganz normales Projekt, taucht aber
  nicht in der normalen Projektliste auf. Kopieren/Als-Mustervorgang-speichern/Neuen-Vorgang-aus-
  Muster-erstellen laufen alle über dieselbe Funktion `duplicate_project()` in `app/projects.py`.
  **`duplicate_project()` kopiert nie einen Auftrag** (nur das zuletzt angelegte Angebot,
  `status` immer hartkodiert `"anfrage"`, unabhängig von `as_template`) – im zweiten Klicktest
  (1.2.20) wurde ein aus einem Wartungsvertrag erzeugtes Projekt mit sowohl Angebot ALS AUCH
  Auftrag beobachtet; Code-Prüfung (Docstring sagt es explizit) und der einzige dazu
  nachvollziehbare echte Datensatz (Projekt mit `ProjectProfile.source_maintenance_contract_id`
  gesetzt: ein Angebot, kein Auftrag) bestätigten übereinstimmend das erwartete Verhalten – nicht
  reproduzierbar, keine Codeänderung. Wahrscheinlichste Erklärung: der Auftrag entstand durch
  einen eigenen, nicht mehr erinnerten Klick auf "Beauftragen" beim Testen des neuen Angebots.
- **E-Mail-Versand**: gemeinsame Infrastruktur in `app/email_sending.py` (SMTP oder Microsoft 365
  OAuth2/Graph API, umschaltbar). Im Graph-Weg wird ausschließlich vom einen hinterlegten
  `SmtpSettings.graph_sender_mailbox` gesendet (kein `from`-Überschreiben, geprüft 28.09.2026);
  dieses Postfach muss Mitglied der RBAC-Gruppe `ERP-Zugriff` sein (Regel 17). Betrifft/Auftrag/
  Angebot/Rechnung teilen sich eine Textvorlagen-
  Tabelle (`app/document_email_templates.py`), Mahnungen haben eigene Vorlagen pro Stufe direkt
  auf `ReminderLevel` (historisch zuerst gebaut, nie migriert). Seit 1.8.17 läuft jeder Versand
  über das Versandprotokoll mit Ablage (Regel 21), mehrere Empfänger und CC, Anhang höchstens 3 MB. Aufgaben-Mails
  enthalten seit 1.8.53 keinen Inhalt der Aufgabe (nur Art und Link, `notify_task_assignment()`), geprüft für jede
  Versandstelle in `tests/test_v355_aufgaben_mail_ohne_inhalt.py`.
- **Modul-Umschalter** (seit 1.1.0): Tabelle `EnabledModule` (`module_key`, `enabled`), Registry
  `OPTIONAL_MODULES` in `app/modules.py` ist die einzige Stelle, an der sich ein künftiges Modul
  eintragen muss. Opt-out-Default – fehlt eine Zeile für einen `module_key`, gilt das Modul als
  aktiv, damit ein neuer Registry-Eintrag nie stillschweigend eine bestehende Installation
  verändert. Ein Admin schaltet Module live unter Einstellungen → Module um (`PUT
  /api/modules/{key}`), Prüfung überall live per `is_module_enabled(db, key)` bzw. dem
  gleichnamigen Jinja-Global – **kein** Modul darf nur an einer Stelle (z. B. nur im Sidebar-Link)
  versteckt sein; API-Endpunkte müssen den Zustand selbst prüfen (403 bei deaktiviert, auch für
  Admins), sonst bleibt die Funktion über die API erreichbar, obwohl die Oberfläche sie versteckt.
  Die Kern-ERP-Kette (`Customer`→…→`Reminder`, Zeiterfassung, Planung) hat bewusst **keinen**
  Registry-Eintrag und bleibt immer aktiv.

## Modulübersicht

Jeder Eintrag nennt die zugehörige Archivdatei -- **vor einer Änderung an diesem Bereich lesen**
(Regel 14). Reihenfolge ohne Wertung.

- **Aufgabenmanagement** (`Task`, Modul `aufgabenmanagement`) -- `docs/archiv/modul-aufgaben.md`
- **Wartungen & Reparaturen + Monteursansicht** (`MaintenanceContract`, `ServiceReport`,
  `/mobil`, Modul `wartungen`) -- `docs/archiv/modul-wartungen-und-monteursansicht.md`
- **PDF-Erzeugung** (gemeinsamer Rahmen `render_framed_pdf()`, DIN5008-Kopfbereich,
  dokumenttyp-übergreifende Layout-Einstellungen) -- `docs/archiv/pdf-architektur.md`
- **Mahnwesen** (Bearbeiten/Löschen/Versenden von Mahnungsentwürfen) --
  `docs/archiv/mahnwesen.md`
- **Projektliste & Projektmappe** (Kanban-Pipeline, Breadcrumbs, Direkteinstieg,
  Katalogauswahl, pauschale Abschlagsrechnung) -- `docs/archiv/projektliste-und-mappe.md`
- **Stammdaten-Bereinigung, Firmenlogo, Sidebar/Topbar** (Leistungskatalog vs. Stammdaten,
  Mitarbeiter-Reintegration, Sidebar-Umgestaltung; seit 1.8.112 neue Ordnung von Seitenleiste und Einstellungen, Stufe 1 „Ordnen“:
  Gruppen mit Überschrift, Einstellungen in zehn Gruppen, nur Admin speichert = für das Büro ausgeblendet, Zeitregeln/DATEV/Zeit-Listen
  aus dem Backoffice, frühere Adressen leiten weiter; Stufe 2 „Bereinigen“ dort festgehalten, nicht gebaut; seit 1.8.113
  Versandprotokoll je Projekt und Kunde in Projektmappe und Kundenakte, Mahnung verlinkt in ihre Rechnung, „Mein Konto“ mobil,
  Leistungsformular für Büro – Auftrag; seit 1.8.117 Zeiterfassungs-Backoffice für die Büro-Rollen; seit 1.8.118 Outlook-Hinweis nur ohne
  Zugangsdaten) -- `docs/archiv/stammdaten-und-sidebar.md`
- **Adressimport & Objekte** (Altsystem-Import, Hauptadressen-Kennzeichnung) --
  `docs/archiv/adressimport-und-objekte.md`
- **Serverbetrieb & Anmeldesicherheit** (Geheimnisse/`ERP_DATA_DIR`, Zwei-Faktor-Pflicht,
  Geräte-Vertrauen, serverseitige Anmeldeschranke für Seiten, PostgreSQL-Migrationsreparatur; seit 1.8.98 Sitzungen auf dem Server,
  siehe Regel 30; seit 1.8.114 Datenbankverbindungen unter Last: Schranke im Threadpool, Sitzung vor dem Senden zu, Seitendaten statt
  Sitzungen der Jinja-Globals, Pool passend zum Threadpool, Angriffstest gegen PostgreSQL, Regel 35; seit 1.8.128 Anmeldepflicht für
  jede Methode, öffentliche Pfade mit ihren Methoden; seit 1.8.130 ohne Konto geschlossen, erstes Konto per `scripts/erstes_konto.py`,
  PWA-Symbole öffentlich, Akzentfarbe nur Admin)
  -- `docs/archiv/serverbetrieb-und-anmeldesicherheit.md`
- **Rechtekonzept** (vier Rollen `admin`/`buero_finanzen`/`buero_auftrag`/`field`,
  Standardverweigerung, Objekt-Filterung, Dateiablage je Objekt, Büro-Suche) --
  `docs/archiv/rechtekonzept.md` (siehe auch "Rechtekonzept (kurz)" unten)
- **Betriebsmittelverwaltung & Betriebskosten-Übersicht** (Modul `betriebsmittel`/
  `betriebskosten`, Verrechnungssatz-Kreislauf, Produktivstunden-Rechner) --
  `docs/archiv/modul-betriebsmittel-und-betriebskosten.md`
- **Zeiterfassung & Abwesenheit** (Schlechtwetter-Zeitarten, Krankheitssichtbarkeit für
  `buero_auftrag`, Abschluss/Sperrdatum seit 1.7.10) -- `docs/archiv/zeiterfassung-und-abwesenheit.md`
  (die Monteur-Zeiterfassung selbst und ihre Zugriffsregeln stehen im Rechtekonzept-Archiv,
  Abschnitt "Zeiterfassung für Monteure")
- **Buchhaltung** (Modul `buchhaltung`, Eingangsrechnungen, Kontenstamm/Vorkontierung) --
  `docs/archiv/modul-buchhaltung.md`
- **KI-Fundament** (anbieterunabhängige Schnittstelle `call_ai()`, noch keine Fachfunktion) --
  `docs/archiv/ki-fundament.md`
- **Kalender-Modul & Outlook-Synchronisation** (Modul `kalender`, `CalendarEvent`, Graph-Sync,
  Echo-Erkennung) -- `docs/archiv/modul-kalender-und-outlook-sync.md`
- **Checklisten & Formulare** (Modul `checklisten`, Vorlagenfassungen, Kontexte Auftrag/Objekt/
  Betriebsmittel/Betrieb, Regeln → Aufgaben, Etappenplan 1.8.0–1.8.5 und Stufen 2–4; seit 1.8.38 Systemfelder mit
  Abschnitt und "nur Büro", Folgen nach einer Unterschrift, Regel-Aufgabe mit Link zum Anlegen; seit 1.8.41 Status
  "gegenstandslos" für Behinderungs- und Bedenkenanzeige; seit 1.8.43 Folgen nach dem Versand eines Briefs; seit 1.8.45
  Feldtyp "beleg": PDF oder Foto, am Inhalt erkannt, unverändert gespeichert, in Prüfsumme und Versiegelung; seit 1.8.56
  verlangt eine Unterschrift alle Pflichtangaben oberhalb, `missing_before_signature`; seit 1.8.57 Unterzeichner je
  Unterschriftsfeld -- frei, angemeldetes Konto, Auftraggeber laut Auftrag, Beteiligter mit eingefrorener Vollmacht zur
  Abnahme --, beim Unterschreiben im Siegel (`seal_format` 3), Unterschrift bis aufs Verwerfen unveränderlich; seit 1.8.59
  beim Auftraggeber Pflicht "Name der unterschreibenden Person" (optional Funktion), Vollmacht immer "Vollmacht zur Abnahme:
  ja/nein", Veröffentlichen lehnt Pflichtfelder "nur Büro" über einer Unterschrift ab, die auch der Monteur leistet --
  bekannte Ausnahme Behinderungsanzeige in `SIGNER_FILL_EXCEPTIONS`; seit 1.8.60 Feldtyp "maengel", nur als Systemfeld eines
  Zwecks (`SYSTEM_ONLY_FIELD_TYPES`), Mängel als eigene Datensätze im Siegel; seit 1.8.61 Zweck "nur Büro"
  (`office_only`), fester Unterzeichner je Systemfeld (`SystemField.signer_mode`), Prüfung vor einer Unterschrift je Zweck
  (`signature_checks`), Feldtyp "dachflaechen" mit Namens-Schnappschuss; seit 1.8.63 Folge je Unterschrift
  (`FollowUp.per_signature`, Zeile `<Folge>#<Unterschrift>`, "entfallen" nach verworfener Unterschrift); seit 1.8.66 feste
  Fassung je Unterschrift und Abschluss in der Ablage, nie neu erzeugt, überholt nach verworfener Unterschrift
  (`app/checklist_versions.py`, Karte "Feste Fassungen" nur Büro)) -- `docs/archiv/modul-checklisten.md`
- **Kaufmännisches Runden** (Helfer `app/rounding.py`, Rundungsregel je Rechnung, Liste der
  Geldstellen, bewusst nicht geänderte Formatierer) -- `docs/archiv/kaufmaennisches-runden.md`
- **Versandprotokoll und Ablage** (jede E-Mail über `dispatch_email()`, Schlüssel gegen
  Doppelversand, unveränderliche PDF-Ablage mit SHA-256, `/versandprotokoll`) --
  `docs/archiv/versandprotokoll-und-ablage.md`
- **Vertragsgrundlage, Vertrag, Beteiligte, Anzeigen** (Stufe 2b mit eigenem Etappenplan;
  `Customer.is_consumer`, Vertragsgrundlage `vob_b`/`bgb_vob_c_4_5`/`bgb` an Angebot und Auftrag,
  Klausel nur rechtlich geprüft im PDF, Ändern am Auftrag nur mit Begründung; welche Felder
  Beauftragen und Abgleich übernehmen, hält `tests/test_v325_quote_order_copy_fields.py` fest --
  ein neues Feld an Angebot oder Auftrag braucht dort einen Eintrag; seit 1.8.32 Vertragsvorlagen je
  Grundlage und Vertragsentwurf am Auftrag, Dokumenttyp `contract`; seit 1.8.33 Festschreiben als Fassung mit
  eingefrorenem Inhalt und PDF in der Ablage, Anlage = zuletzt versendete Fassung des Angebots oder bewusst
  gewählt, Versand nur einer zum Auftrag passenden Fassung; seit 1.8.34 Unterschrift auf dem Gerät (Kunde und
  Betrieb, gebunden an Fassung und PDF-Prüfsumme, Ankreuzfelder im unterschriebenen Inhalt, Unterschriftsblatt) oder
  Papier-Scan, danach keine neue Fassung und Vertragsgrundlage/Abgleich gesperrt, Widerrufsfrist bei Verbrauchern;
  seit 1.8.35 unterschriebene Abschrift mit eigener Prüfsumme, die Versand und Zustellung nach der Unterschrift
  verwenden; seit 1.8.37 Adressbuch (`Contact`, Stammdaten, archivieren statt löschen) und Beteiligte am Projekt
  (`ProjectParticipant`, Rollen fest im Code, Kopie bei Anzeigen, Empfangsvollmacht mit Beleg, Reiter in der
  Projektmappe); seit 1.8.38 Behinderungsanzeige erfassen (Startvorlage, drei Abschnitte, Anzeige nur Büro, Aufgabe
  "versenden" nach der Unterschrift der Meldung, Tagesbericht-Regel verlinkt aufs Anlegen); seit 1.8.39 Beteiligte aus
  Kunden und Lieferanten (Dialog nach Herkunft, Rollenprüfung der Büro-Suche `office_source_visible()`, Eintrag mit
  Verweis ohne Kopie); seit 1.8.40 Behinderungsanzeige als Brief (zwei Briefarten, Fassung je Abschnittsunterschrift mit PDF
  in der Ablage, Vorbehalt je Briefart und VOB/B bzw. BGB mit Prüfung, An fest der Auftraggeber, CC "Kopie bei Anzeigen",
  Vollmacht beim Versand in der Ablage, Aufgabe "versenden" danach erledigt); seit 1.8.41 Versandergebnis "Empfang
  bestätigt"/"unzustellbar" für alle Dokumente, Zustellung nachtragen mit Empfängerauswahl und Vollmacht, Wiederaufnahme
  "i. A." Büro-Konto, Zeitstrahl, "als gegenstandslos abschließen", Kundenwechsel prüft Beteiligte; seit 1.8.43
  Bedenkenanzeige erfassen mit Folgen und Hinweis "Offene Bedenken"; seit 1.8.44 Bedenkenanzeige als Brief und Versand,
  Bestätigung bei abweichendem Kunden, Kundenwechsel-Sperre bei festgeschriebenem Vertrag; seit 1.8.45 "Antwort als
  Beleg" als PDF oder Foto, Hinweis "Offene Bedenken" auch auf Einsatzbericht- und Checklisten-Seite des Auftrags) --
  `docs/archiv/vertragsgrundlage-und-vertrag.md`
- **Abnahme und Gewährleistung** (Stufe 2c mit eigenem Etappenplan; seit 1.8.46 Leistungsart und
  Gewährleistungsdauer am Auftrag, Abnahme unveränderlich mit Verwerfen, Gewährleistungsende abgeleitet an Auftrag/Objekt/
  Dachfläche, Garantie Dritter an der Dachfläche, Abgleich gesperrt nach Abnahme; seit 1.8.47 Vollmacht zur Abnahme am
  Beteiligten, Begründung mit Vorschau der verschobenen Enden nach der ersten Abnahme, Nachweis förmlich: Beleg, sonst Beleg
  oder Begründung; seit 1.8.48 Prüfstatus neben jedem Gewährleistungsende aus einer Funktion, Siegel des Verwerfens, Fassung
  des Prüfsummenformats je Abnahme; seit 1.8.49 Mängel aus der Abnahme mit Haltung, Status, Freigabe, Verlauf, Aufgabe und
  bei VOB/B "Nachbesserung regulär bis"; seit 1.8.50 Platzhalter `{gewaehrleistung}` in Vertragsvorlagen, Festschreiben erst
  mit Dauer, danach Dauer und Leistungsart gesperrt; seit 1.8.51 Belege am Mangel nachreichen, Aufgabentitel mit Kurzfassung,
  Bindung der Sperren an eine gültige Fassung offen, weil es kein Zurückziehen gibt; seit 1.8.52 Monteur-Sicht auf Mängel in
  `/mobil` mit Positivliste, "beseitigt" melden mit Foto, Fotos nur über den Monteur-Weg; seit 1.8.54 Aufgabe folgt dem
  Status, Hinweis des Monteurs zur Meldung; Stufe 2c-2c ab 1.8.55: neue Frist bei "zurück auf offen", Zurückziehen einer
  Vertragsfassung entschieden, nicht gebaut; Stufe 2c-2d ab 1.8.59: Abnahmeprotokoll als Checkliste, Etappenplan im Archiv;
  seit 1.8.60 Feld "Mängel" im Protokoll; seit 1.8.61 Zweck "abnahme" mit Systemfeldern, Startvorlage, Prüfung der
  Unterschrift des Auftraggebers; Teil 2 ab 1.8.62: Mängel im Protokoll nach der Kopie statt nach der Uhr; seit 1.8.63 Abnahme
  aus dem Protokoll als Folge je Unterschrift, Sperre der Unterschrift, Hinweis und Nachholen am Auftrag; seit 1.8.64
  Erklärungen und Mängel gebündelt auf Protokollseite und im PDF; Stufe 2c-2e ab 1.8.65: Mängel im Protokoll nach der ersten
  gültigen Unterschrift überall, kaputte Kopie als Fehler; seit 1.8.66 feste Fassung je Unterschrift; seit 1.8.67 Versand des
  Protokolls an den Auftraggeber, Abnahme mit Verweis auf die Fassung (Format 4); seit 1.8.68 Fotos der Mängel im Protokoll-PDF,
  Kopien an die in der Fassung eingefrorenen Empfänger; seit 1.8.69 als Personen an ihre Adresse von heute, Kopie ohne Mail im
  Versandverlauf, Briefe der Anzeigen ohne freies CC, Strukturtest "Kopie an:" = Cc)
  -- `docs/archiv/abnahme-und-gewaehrleistung.md`
- **Befund „Vor dem Echtbetrieb: Geld und Sicherheit“** (09.10.2026: Abschläge/Schlussrechnung/Storno, fremde IDs ohne
  Zugehörigkeitsprüfung, Abgleich mit dem Angebot, Rechnungsdatum, Spaltenschlüssel; je Fehler ein Test unter
  `tests/test_v372_befund_*.py`, xfail bis zur Reparatur; seit 1.8.70 Punkt 2 behoben: Zugehörigkeit, Historie in /mobil,
  "erfasst/geschlossen von", Objekt eines anderen Kunden mit Bestätigung, Strukturtest Regel 25; seit 1.8.71 Punkte 3, 5 und
  4d behoben: Abgleich mit dem Angebot gesperrt mit Grund (409), sobald an den Positionen etwas hängt oder der Auftrag storniert
  bzw. abgeschlossen ist (`sync_block_reasons()`), Untertitel unter PostgreSQL, Projektstatus bleibt; Spaltenschlüssel gekürzt
  und eindeutig; Auftragsdatum aus Berlin; Hinweis fürs Büro, wenn die Fläche der Vertragsposition fremd ist; "Entscheidungen
  Rechnungen" festgehalten, nicht gebaut; seit 1.8.72 (R3) 1c, 1e-1h behoben: Sperren an Schlussrechnung, Abschlag, Storno und
  Mahnung unter der Sperre der Auftragszeile, Grund statt Knopf; seit 1.8.73 Nummernvergabe atomar je Nummernkreis, Entwurf löschen
  unter der Sperre, Prüfabfrage `scripts/pruefabfrage_nummernkreise.sql` (Dubletten und Lücken); offen gemeldet: Rechnungs- und
  Mahnungsnummer gleichen nicht mit den vorhandenen ab ("nächste Nummer" zurückgesetzt -> Dublette) -- seit 1.8.74 behoben: die
  Einstellungen lehnen eine nächste Nummer auf oder unter einer vergebenen ab (409); seit 1.8.74 Pflicht-Leistungszeitraum;
  seit 1.8.75 4a-4c behoben (Rechnungsdatum = Tag des Festschreibens, Fälligkeit rückt mit, Hinweis bei späterem Versand) und jeder
  schreibende Weg an einer Rechnung unter der Sperre; seit 1.8.76 Nummernkreise: keine Anzeige schreibt oder verbraucht eine
  Nummer, Überspringen mit Warnung, Format ohne Jahr nicht mit Jahreswechsel; seit 1.8.77 jede Nummer eindeutig in der Datenbank
  (alle sieben Nummernkreise), Befund Zahlungsstufe, Entscheidungen zu Einbehalt und Rechnung aus Aufwand; 1a, 1b und 1d für R4; Befund R4 "Schlussrechnung als
  Endrechnung", Entscheidungen R4a; seit 1.8.82 R4a Punkte 1 und 2: feste Fassung der Rechnung beim Festschreiben, Sperren am
  Auftrag; seit 1.8.83 Punkte 3–6: Nachtrag als Auftragsposition, freie Positionen nur aus Aufwand, kein negativer Abschlag, letzter
  Stand nach dem Festschreiben, 1d behoben; R4b ab 1.8.84: seit 1.8.85 Punkte 2, 3, 5 -- Endrechnung mit Abzugsblock, Neuberechnung
  beim Festschreiben, Abweichung vom Auftrag mit "Aus dem Auftrag aktualisieren", Abschlag über 0 €, kein Aufwand nach der
  Schlussrechnung, 1a und 1b behoben; seit 1.8.86 Punkte 4 und 6 -- Zahlungshinweis "Stand …", abschließende Rechnung aus Aufwand am
  Auftrag nach Aufwand; R4c ab 1.8.87: Vorweg -- "heute" im Browser aus Berlin, Klicktest Mahnwesen wartet, Testhelfer `_run`;
  seit 1.8.88 Mengenvergleich im Entwurf der Schlussrechnung: Auftragsmenge, zuletzt abgerechnet, Ist, Abweichungen markiert; seit
  1.8.89 Punkte 3–5: Mahnen nach der Endrechnung über den Zahlbetrag, abgezogene Rechnungen nicht mehr einzeln, Einbehalt fällig; seit
  1.8.90 Punkte 6–7: Schlussrechnung unter 0 €, Erstattungsbetrag, Guthaben und Zahlungsausgang, E-Mail mit Zahlbetrag -- R4c vollständig;
  Nacharbeiten R4c ab 1.8.91: Finanzen und Dashboard zählen je Auftrag den Zahlbetrag, "enthalten in Schlussrechnung …"; seit 1.8.92
  Schlusstext bei Erstattung aus den Einstellungen; seit 1.8.93 Guthaben des Kunden aus Rest und Überzahlung, eine Erstattung für
  beides -- Nacharbeiten vollständig; vor dem Abnahmetest 1.8.94: Bezahlt abzüglich Erstattungen, Zahlbetrag 0 €, Zurücknehmen mit
  Grund, enthaltene Rechnungen gruppiert, Klicktest-Helfer „neu geladen“; seit 1.8.95 Baustein gegen veraltete Antworten
  (`_speichern.html`, Regel 29) in allen Vorlagen, Rechnungen über 0 € oder weniger nur als Storno oder Endrechnung mit Abzügen;
  seit 1.8.96 Zeitlimit im Baustein (60 s, Bereich unklar, Warnung beim Verlassen), abschließende Aktionen über `abschliessen()` (warten
  auf das Speichern der Seite), Teil-Updates statt gemerkter Werte an acht Endpunkten mit Zeilensperren; seit 1.8.97 jedes Lesen über
  den Baustein (Ausnahmen nur ohne Formular), Klicktests Anmelden/Abmelden mit Netzwerkprotokoll im Werkzeug, Regel 29 nachgezogen;
  festgehalten 13.10.2026, nicht gebaut: Gewährleistungs- und Kulanzstunden für Stufe 2d und die Rüge, „Abschließen ohne Rechnung“ im
  neuen Abschnitt „Parkplatz vor dem Echtbetrieb“; seit 1.8.98 Weiterleitungsziele nur lokal (Server und Browser), Sitzungen auf dem
  Server, `Cache-Control: no-store` für angemeldete Sitzungen, Regel 30; seit 1.8.99 Vorweg: Zeitlimit beim Hochladen ab dem Ende der
  Übertragung, gescheitertes Speichern sperrt abschließende Aktionen, Zeilensperren an abgeleiteten Werten in fünf Teil-Updates,
  Verschieben im Angebot als Teil-Update, Regeln 26 und 28 erweitert; Befund 1.8.100 Sicherheit der Seiten: acht Lücken als xfail in
  `tests/test_v405_befund_seiten.py` -- Uploads als aktiver Inhalt, Secure nur per Umgebung, Anfragen von Seiten derselben Site,
  Einrahmen, ungeschützte Namen an vier Stellen -- nur festgehalten, nicht behoben; seit 1.8.101 hochgeladene Dateien nie als aktiver
  Inhalt, Regel 31; seit 1.8.102 Daten im HTML: esc(), Handler über data-Attribute, Links geprüft, Regel 32; seit 1.8.103 Vorweg:
  Sitzungen beenden (vertraute Geräte, Admin, Feierabend), „Anmeldung abgelaufen“, Vertragsentwurf unter der Sperre des Festschreibens,
  Befund `content` der Layout-Bausteine; seit 1.8.104 schreibende Anfragen nur von der eigenen Seite, kein Einrahmen, Secure in Produktion,
  Regel 33 -- alle zwölf Befund-Tests grün; seit 1.8.105 lesen die Scanner der Strukturtests Pfeilfunktionen vollständig
  (`tests/vorlagen_js.py::_ausdruck_ende()`, eine Funktion für alle, Zeilenende wie die Semikolon-Einfügung), Lieferschein-Knopf ohne Werte
  im onclick; seit 1.8.106 Vorweg: SVG-Logo mit Sandbox geprüft, TEXT_IDS vollständig und dauerhaft über alle Modelle und Antworten
  geprüft, Admin meldet beim Beenden der Sitzungen auch die vertrauten Geräte ab, Feierabend als POST ohne Kreis über `/login`; seit
  1.8.107 Secure als Vorgabe (ohne nur `ERP_ENV=development`/`test`), HSTS, Schutzkopfzeilen auch an der 500; vor dem Abnahmetest
  ab 1.8.109: Zahleneingaben im deutschen Format über `_zahl.html` (Regel 34), lesbare Fehler in Einstellungen, Plantafel und
  Arbeitsvorbereitung, "Festschreiben" am Mahnungsentwurf; seit 1.8.110 Revisionsnummer des Auftrags unter der Sperre der
  Auftragszeile, vor dem Commit; seit 1.8.111 Klicktest nachts geklärt -- der Test rechnete falsch)
  -- `docs/archiv/befund-vor-echtbetrieb.md`
- **Zahlungen** (Zahlungsstufe Z1 seit 1.8.78: Zahlungseingang mit Zuordnungen, Skonto und Einbehalt, Rest am Kunden,
  Zahlstand abgeleitet, Gegenbuchung statt Ändern, Sperrreihenfolge, Storno erst nach gelösten Zuordnungen, Finanzen/Dashboard mit
  offenem Betrag, Migration "bezahlt"; seit 1.8.79 Z2a: Mahnwesen ohne Automatik, Prüfungen unter der Sperre, Mahndatum beim
  Festschreiben, Aufstellung an der Mahnung, Versand nur mit passendem Betrag, Rechnung hält ihren Kunden, Kundenwechsel gesperrt;
  Befund Z2b Mahngebühren/Verzugszinsen; seit 1.8.80 Z2b Punkte 3–6: Auftrag hält seinen Kunden, Kundenwechsel mit Begründung, erreicht
  erst mit Versand oder Zustellung, Ersatz einer nie versendeten Mahnung, Schalter Mahngebühren, Nebenforderungen, Gebühr als
  Vorschlag, Pauschale, Verzugsbeginn; seit 1.8.81 Punkte 7–9: Basiszinssatz je Halbjahr, Verzugszinsen als Nebenforderung, Zahlungen auf
  Nebenforderungen nach § 367 BGB, Rechtstexte, keine Gebühr neben der Pauschale, Storno nur ohne offene Nebenforderungen, Regel 27)
  -- `docs/archiv/zahlungen.md`
- **Grunddaten beim Start** (Einstellungen und Standardsätze in `app/grunddaten.py`, Liste der umgestellten
  Lesepfade, kein GET schreibt, Sperre gegen zwei gleichzeitige Starts, SAVEPOINT unter SQLite; seit 1.8.84 auch keine Daten je
  Datensatz beim Lesen, Rundgang mit Lücken, Beobachter an der Sitzung) --
  `docs/archiv/grunddaten-beim-start.md`
- **Speichern nur gesendeter Felder** (`PartialUpdate`, Strukturtest über alle PUT-Handler, Liste der
  Altfälle, Nebenbefunde der Durchsicht aller Speichern-Aufrufer) -- `docs/archiv/teil-updates.md`
- **Testablauf und Klicktest-Werkzeug** (seit 1.8.108: volle Suite parallel, Kennung und Aufräumen der Testschemas, Sperren der
  Spielwiese, `klicktest_alle.py --gleichzeitig`, `ALLEIN` für zeitkritische Klicktests, Abbruch in Gegenproben, Messungen; die
  Festlegungen zu Werkzeug und Testablauf, Regel 28; seit 1.8.111 Zeitgrenze je Test, Browser-Uhr im Klicktest, taskkill mit
  Zeitlimit; seit 1.8.115 Verbindungsprotokoll von uvicorn je Instanz und Ausgang hängender Anfragen im Netzprotokoll; seit 1.8.116
  JS-Ausnahmen in node-Tests, Regel 36; seit 1.8.123 Strukturtests mit Unterordnern, Basis-Templates und Makros, Stufe 0a des Redesigns;
  seit 1.8.124 Stufe 0b: alle Strukturtests, Wächter über tests/, Seiten-Abgleich, Makro-Regel; seit 1.8.125 Stufe 0c: kein Include per
  Textvergleich, Klicktest-Ports außerhalb der kurzlebigen Ports; seit 1.8.126 Stufe 0d: Bildgrundlage `scripts/bildgrundlage.py` mit
  Vergleich, stehende Uhr im Klicktest, ein Port-Helfer für alle Klicktests; seit 1.8.127 bricht der Vergleich bei verschiedenen
  Chrome-Versionen ab; seit 1.8.131 Stufe 2a: Monteurin auch auf dem TerraPad, fünf Zustände des Rahmens, 304 Bilder je Lauf)
  -- `docs/archiv/testablauf-und-klicktests.md`
- **Redesign: Design-System „Schiefer & Signal“** (Stufen 0a–0d siehe Testablauf; seit 1.8.127 Stufe 1 „Fundament“: `/static/` ohne
  Anmeldung mit langem Cache, `app/static/ds/ds.css` mit Tokens und selbst gehosteten Schriften, `_ds_kopf.html` in jeder Seite, Wächter,
  Kontrasttest, Angriffstests, Regel 37; seit 1.8.128 Runde 1b Anmeldepflicht für jede Methode; seit 1.8.129 Runde 1c Härtung:
  Schnittstellen-Doku nur lokal per `ERP_API_DOKU=1`, `/health` mit HEAD, Wächter ds.css nach dem Ziel des Selektors, Befunde
  Ersteinrichtung und Akzentfarbe; seit 1.8.130 Runde 1d: ohne Konto geschlossen, Akzentfarbe nur Admin, PWA-Symbole öffentlich -- Herleitung
  im Serverbetrieb-Archiv; seit 1.8.131 Stufe 2a: Bildgrundlage um TerraPad und Zustände des Rahmens erweitert; Fehlerrunde vor Stufe 2
  1.8.132–1.8.142, Nachrunde 1.8.143–1.8.150 und Nachrunde 2 1.8.151–1.8.154: Abläufe, Zurück-Links ohne `history.back()`, Seitentitel,
  `/users` nur Admin, Änderungshistorie lesbar und seitenweise, Zeit buchen nur für sich außer Admin, Gruppenzeit stoppen nur mit
  Kolonnenführer-Kennzeichen, Rückfrage beim Entziehen und Löschen; Runde „Du“ ab 1.8.157: Oberfläche per Du (1.8.158), Kundentexte --
  Angebot, Auftrag, Rechnung, Mahnung, Vertrag, Briefe, ihre E-Mails und PDFs -- beim Sie: ein neuer Kundentext gehört in `KUNDENTEXTE`
  (`tests/test_v440_runde_du.py`, seit 1.8.160, prüft auch echte PDFs), außerhalb keine Sie-Anrede; die Meldung „Konto ohne Mitarbeiter“
  nur aus `app/meldungen.py` (1.8.159); Stufe 2 „Rahmen“ ab 1.8.161, Pilot Prüfvorlagen 1.9.3, Grundregeln mit Gewicht null 1.9.4, Runde 3 „Farben aller Seiten“ 1.9.5: alte Farbnamen zentral in `ds-alte-namen.css`, Kontrast je Seite gemessen; das Redesign zählt seit 1.9.0 unter 1.9.x; Runde 9 1.9.23–1.9.29 als letzte Runde von Stufe 2: Abbrechen mit Rückfrage, Anfragen und Arbeitsvorbereitung, Monteursseiten mit Tablet-Maßen, Anmeldung und Sperrseite, Hinweise ohne interne Dateien, Stufe 2 abgeschlossen -- 43 Seiten umgezogen, 10 aufgeschoben) -- `docs/archiv/redesign.md`
- **Ältere Versionshistorie 1.1.0–1.6.0** ("Neu seit"-Kette, vollständig, unverändert) --
  `docs/archiv/chronik-1.1-1.6.md`
- **Migrationsketten- und Testlauf-Historie** (Version-für-Version-Nachweis, wer wann was mit
  wie vielen Tests geprüft hat) -- `docs/archiv/versionsverlauf.md`; ab 1.6.0 siehe
  CHANGELOG.md.

## Architekturentscheidungen (kurz, mit Archivverweis)

Wiederkehrende technische Muster, die mehrere Module gleichermaßen betreffen -- Details und
Herleitung in der jeweils verlinkten Archivdatei, nicht hier dupliziert.

- **PDF-Rahmen statt Einzel-Renderer**: alle Dokumenttypen außer historisch dem Angebot teilen
  sich Briefpapier/Ränder/Kopfbereich über `render_framed_pdf()`/`build_din5008_header_block()`
  -- ein neuer Dokumenttyp muss in `RENDERERS_USING_SHARED_FRAME` UND `DOCUMENT_TYPES`
  eingetragen werden, sonst `ValueError` beim ersten Aufruf. Siehe
  `docs/archiv/pdf-architektur.md`.
- **Rollenhierarchie statt flacher Mengen**: `ROLE_RANK` (`app/permissions.py`) ordnet
  `field < buero_auftrag < buero_finanzen < admin`; `require_min_role(x)` lässt `x` und jede
  höhere Rolle durch, `require_role(...)` bleibt für echte, nicht-hierarchische Mengen (z. B.
  `require_admin()`-Äquivalente). Siehe `docs/archiv/rechtekonzept.md`.
- **On-Demand statt Scheduler**: fällige Erinnerungen (Wartungsverträge, Betriebsmittel-
  Prüffristen, Kündigungsfristen, Skonto) laufen nie als Hintergrundjob, sondern als
  `check_due_*_and_create_reminders()`-Funktion beim Öffnen der jeweiligen Seite, mit einem
  Idempotenz-Stempel (`last_reminder_*`) gegen doppeltes Erinnern. Ausnahme: der Outlook-
  Kalender-Sync läuft zusätzlich per echtem Cron (`scripts/sync_outlook_calendars.py`), siehe
  `docs/archiv/modul-kalender-und-outlook-sync.md`.
- **Live-Auflösung statt Kopie bei optionalem Ressourcenbezug**: `OperationalAsset` mit
  gesetztem `resource_id` hält seine Identitätsfelder bewusst `NULL` und löst sie bei jedem
  Lesezugriff live aus `OperationalResource`, statt sie zu kopieren -- verhindert
  Namensdivergenz. Siehe `docs/archiv/modul-betriebsmittel-und-betriebskosten.md`.
- **Eingefrorene Schnappschüsse bei GoBD-Dokumenten**: `Order`/`Invoice` sind unveränderliche
  LV-/Adress-Schnappschüsse zum Zeitpunkt der Beauftragung/Finalisierung (siehe "Fachbegriffe &
  Domänenmodell" unten, Regel 5) -- ein Renderer darf dafür nie live vom aktuellen
  Kunden-/Objektdatensatz lesen.
- **Grunddaten beim Start statt beim ersten Lesen** (seit 1.8.42, Regel 23): `app/grunddaten.py::anlegen()`
  in einer Transaktion hinter einer Sperrzeile, Schritte mit SAVEPOINT (siehe "Self-Seeding gegen gleichzeitigen
  ersten Zugriff absichern" unten) und ohne eigenen Commit. Siehe `docs/archiv/grunddaten-beim-start.md`.
- **Platzhalter in Textvorlagen über `app/placeholders.py::apply_placeholders()`** (seit 1.8.32,
  vorher je Versender eine eigene Schleife): ersetzt in einem Durchgang, ein eingesetzter Wert wird nie
  erneut ersetzt; Mahnung, E-Mail-Vorlagen und Vertragsvorlagen nutzen es. Eine neue Vorlage mit
  Platzhaltern zeigt ihre Liste in der Oberfläche und warnt vor unbekannten (`unknown_placeholders()`).
- **Abgelehnte API-Antworten lesbar über `app/templates/_fehlertext.html`** (seit 1.8.35, `fehlerText(body, status,
  felder)`): `detail` als Text unverändert, als 422-Liste "Bitte die Eingabe prüfen – <Feld> <Art>." mit den
  Feldnamen der Seite, sonst ein Text je Status. Auftragsseite, seit 1.8.37 Projektmappe und Stammdaten (Liste,
  Formular), seit 1.8.109 Einstellungen, Plantafel und Arbeitsvorbereitung; 28 weitere Vorlagen reichen `detail` noch roh an
  `Error()` weiter ("[object Object]" bei 422) -- eine Seite, die man anfasst, stellt um.
- **Feste Werte passen in ihre Spalte** (seit 1.8.61, seit 1.8.62 für jede Textspalte): unter PostgreSQL lehnt eine zu kurze
  `String(n)`-Spalte einen längeren Wert ab, SQLite nimmt ihn still an. `tests/test_v364_feste_werte_spaltenlaenge.py` prüft
  jede Spalte mit festen Werten gegen ihre Länge -- aus den Konstanten im Code (`FESTE_WERTE`), aus Literalen ohne Konstante
  (`FESTE_LITERALE`), dazu per AST jedes Literal in Konstruktoren, `update().values()` und Vergleichen; jede Spalte mit einem
  Namen nach festen Werten (status, kind, type, mode, key …) muss eingeordnet sein. Eine neue Spalte oder Konstante kommt dort
  in die passende Liste. **Abgeleitete Werte** (seit 1.8.71, z. B. der Schlüssel einer Spalte aus ihrer Bezeichnung) werden dort
  gekürzt, wo sie entstehen, gegen die kürzeste Spalte, in die sie geschrieben werden -- Länge aus dem Modell
  (`app/spaltenlaenge.py`: `laenge()`, `eindeutig_gekuerzt()`).
- **Unterschriften zeichnen über `app/templates/_unterschrift.html`** (seit 1.8.34, `unterschriftsfeld(canvas)`
  auf einem `<canvas class="dk-unterschrift">`): Checkliste, Einsatzbericht und Vertrag teilen sich die Fläche
  (weiß mit dunklem Strich in beiden Themes, Geräteauflösung; seit 1.8.58 neu vermessen bei Drehen und Größenänderung,
  Striche gleichmäßig skaliert neu gezeichnet) -- eine neue Unterschrift baut keine eigene Zeichenlogik. `tests/test_v337_vertrag_unterschrift.py` prüft, dass die drei Seiten keine eigene haben. Seit 1.8.56
  prüft der Server jedes gezeichnete Bild an einer Stelle: `app/signature_image.py::check_signature_png()` (PNG, höchstens
  2 MB und 5000 Pixel je Seite, nicht leer) -- ein neuer Unterschrift-Weg ruft sie auf, bevor er speichert;
  `tests/test_v358_unterschrift_pruefung.py` ordnet jede Spalte ein, die nach Unterschrift klingt, und sucht jeden
  speichernden Weg per AST.
- **Nummern nur über `app/settings.py::issue_number()`** (seit 1.8.73): sperrt die Zeile des Nummernkreises bis zum Commit des
  Aufrufers (UPDATE ohne Änderung -- Zeilensperre unter PostgreSQL, Schreibsperre unter SQLite), alle sieben Nummernkreise.
  `preview_number()` ist nur Anzeige; `tests/test_v376_nummernkreise.py` prüft die Aufrufer. Einen Entwurf mit späterer Nummer
  (Rechnung, Mahnung) löscht nur, wer dieselbe Sperre wie das Festschreiben hält. Seit 1.8.74 lehnt
  `update_sequence()` eine nächste Nummer auf oder unter der höchsten vergebenen desselben Formats und Jahres ab
  (`NumberBelowExisting`, 409); alle sieben Kreise gleichen bei der Vergabe mit den vergebenen ab (`_existing_column()`).
  Seit 1.8.76: eine Anzeige schreibt und verbraucht nie eine Nummer -- `preview_number()`/`effective_next_value()` rechnen
  Jahreswechsel und Abgleich nur aus (geschrieben wird erst bei der Vergabe), kein GET-Endpunkt erreicht `issue_number()`
  (`tests/test_v379_nummern_anzeige.py`, AST); springt die Vergabe über vergebene Nummern, schreibt sie `logger.warning`; ein
  Format ohne Jahr mit "Jahreswechsel: auf Startnummer zurück" lehnt `update_sequence()` ab (`YearlyResetWithoutYear`, 409,
  gemeinsame Oberklasse `SequenceConflict`). Seit 1.8.77 ist jede vergebene Nummer auch in der Datenbank eindeutig (UNIQUE je
  Spalte aus `_existing_column()`, Entwürfe ohne Nummer beliebig viele); ein neuer Nummernkreis braucht seine Bedingung
  (`tests/test_v380_nummern_eindeutig.py`).
- **KI-Aufrufe ausschließlich über `call_ai()`/`call_ai_async()`** (`app/ai_service.py`) --
  nie einen Adapter (`app/ai_adapters.py`) direkt importieren/aufrufen. `call_ai_async()` aus
  `async def`-Routen, `call_ai()` nur aus gewöhnlichen `def`-Routen (Starlette-Threadpool) --
  ein direkter `call_ai()`-Aufruf aus `async def` blockiert sonst die Event-Loop eines ganzen
  gunicorn-Arbeitsprozesses bis zu `AI_CALL_TIMEOUT_SECONDS`. Siehe `docs/archiv/ki-fundament.md`.

## Rechtekonzept (kurz)

Volle Herleitung, Etappenplan und alle Angriffstests: `docs/archiv/rechtekonzept.md` (vor jeder
Rechte-/Rollen-Änderung lesen, Regel 14).

- **Vier Rollen**: `admin` (alles, inkl. Systemverwaltung) > `buero_finanzen` (alles Fachliche
  plus Kalkulationsgrundlagen/Betriebskosten/Mitarbeitervergütung) > `buero_auftrag` (fachlicher
  Kern ohne die vier Finanzbereiche) > `field` (Monteur, stark eingeschränkt). Hierarchisch über
  `ROLE_RANK`, siehe "Architekturentscheidungen" oben.
- **Standardverweigerung, nicht Positivliste** (Regel 11): ein `/api/`-Endpunkt ohne
  ausdrückliche Rollenangabe gilt als admin-only, nicht als offen. `tests/test_v260_role_audit.py`
  erzwingt das mechanisch für API- UND Seiten-Routen, steht bei null Ausnahmen jenseits der
  einzeln begründeten `ROLE_AUDIT_EXEMPT`/`PAGE_AUDIT_EXEMPT`-Einträge.
- **Objekt-Filterung für `field`**: ein Monteur sieht einen Auftrag/Bericht nur über genau zwei
  Wege -- Planungsbezug (Team-Besetzung oder Einzelzuweisung an der Arbeitsvorbereitung) ODER
  einen selbst angelegten Bericht (`ServiceReport.created_by_employee_id`) -- nie über
  Vertrauen in eine fortlaufende ID. `app/orders.py::field_may_access_order()` ist die eine
  Definition dafür, `require_field_report_ownership()` verschärft das für Schreibzugriffe auf
  den eigenen Bericht. Einen Bericht legt sie seit 1.9.79 zu jedem nicht stornierten Auftrag an (`app/service_reports.py::
  bericht_zum_auftrag_moeglich()`, sonst 403; Auftragssuche des Dialogs `app/search.py::search_orders_for_field()`, nur Anzeigefelder;
  `tests/test_v502_bericht_zu_jedem_auftrag.py`) -- ein Leserecht entsteht erst über den eigenen Bericht; 1.9.74–1.9.78 nur für Aufträge
  ihrer Liste. Ihre Liste (`list_field_bookable_orders()`, „Zeit nachtragen“) enthält seit 1.9.76 auch Aufträge ohne Datum
  (`tests/test_v499_liste_ohne_datum.py`); „+ Bericht“ zeigt die Seite des Auftrags nach `OrderFieldAccessOut.bericht_anlegen`
  (`tests/test_v500_auftragsseite_bericht_knopf.py`). Die Wartungshistorie in /mobil gilt seit 1.8.70 nur für Objekte dieser Aufträge
  (`field_accessible_property_ids()`); Objektansicht und Dokumente bleiben für jedes Objekt offen.
- **Einsätze und Feierabend nur für die Rollen der Monteursansicht** (seit 1.9.33, `app/permissions.py::MOBIL_ROLLEN`, heute nur `field`):
  `GET /api/field-view/today` und `POST /api/field-view/feierabend` 403 für jede andere Rolle -- das Büro wird auf `/mobil` nicht abgemeldet.
- **Eine Pausenregel** (seit 1.9.34; seit 1.9.61 ohne Standardpause, die Spalte liest niemand mehr -- Wächter
  `tests/test_v486_keine_standardpause.py`): Stopp, Gruppen-Stopp, Ende nachtragen und Nachtrag mit Von/Bis rechnen die Pause nur über
  `app/time_tracking.py::pause_nach_zeitregel()` (automatisch nach Anwesenheit, eingegebene Pause als Mindestpause); eine reine Dauer ist
  gebuchte Arbeitszeit (netto). Seit 1.9.44 rechnen Stopp, Gruppen-Stopp, Zeitart wechseln und die Vorschau von „Ende nachtragen“ über
  `ende_rechnen()` (Pause und gebuchte Stunden aus einer Funktion). Wächter `tests/test_v462_nachtrag_pausenregel.py`. **Seit 1.9.48 je
  Tag** (nur neue Buchungen): Pflichtpause aus der Anwesenheit des Starttags über alle gebuchten Zeiten samt der neuen (Schwellen „mehr
  als“), die neue Buchung bekommt, was dem Tag fehlt -- mindestens die eingegebene, höchstens ihre Anwesenheit --, frühere bleiben
  unverändert; jede Antwort auf eine Buchung nennt „Tag zusammen“ (`tag_stand()`, seit 1.9.53 die Anwesenheit des Tages vor der Pause,
  angezeigt zwischen „anwesend“ und der Pause); Wächter `tests/test_v474_pause_je_tag.py`, `tests/test_v480_tag_zusammen_anzeige.py`.
  **Seit 1.9.57** rechnet Ändern mit Von/Bis (`PUT /api/time-entries/{id}`) wie ein Nachtrag, mit dem Tag ohne die alte Fassung
  (`buchungen_am_tag(…, ohne_id)`); passt die Pause eines Tags danach nicht mehr, zeigt `pausen_vorschau()` alt -> neu und
  `pausen_neu_rechnen()` bucht genau diese Vorschau, nur auf Klick (`tests/test_v483_meine_zeiten_server.py`). **Seit 1.9.62** merkt jede
  Buchung ihre eingetragene Mindestpause (`TimeEntry.min_break_minutes`, Migration `c4f2a8e61d35`; leer = vor 1.9.62, dann gilt die
  abgezogene Pause, `mindestpause_der_buchung()`): neu rechnen geht nie darunter, „passt nicht“ nur, wenn neu rechnen etwas ändern würde,
  Ändern ohne „pause_minuten“ behält sie (`tests/test_v487_mindestpause_merken.py`). **Seit 1.9.90** leert eine als Dauer gespeicherte Buchung
  (ohne Von/Bis Stunden, Pause oder ein anderer Tag, `app/routers/time_tracking.py::_als_dauer()`) Beginn und Ende, auch je Mitglied und am Kopf
  einer Kolonnenbuchung; ohne Von/Bis und ohne Dauer behält jedes Mitglied seine Stunden; die Monteurin ändert Stunden, Pause oder Tag nur mit
  Von/Bis (422). **Seit 1.9.107** gibt das Büro die Pause einer Dauer an („Pause an diesem Tag“, Vorschau vom Server
  `GET /api/time-entries/dauer-vorschau` bzw. `/api/time-entry-groups/dauer-vorschau`); hat ein Tag eine Dauer und bringt die Regel die Pflichtpause
  nicht unter, fehlt der Rest (`pausen_vorschau()["fehlt"]`, über `pause_nach_zeitregel(deckel=False)`) -- der Tag passt nicht, „Prüfen“ zeigt je Dauer
  „Ändern“ statt „So buchen“ (`tests/test_v527_pause_einer_dauer.py`). **Eine Rundung** (seit 1.9.39): jede neue Buchung --
  auch je Mitglied einer Gruppe -- rundet nur `gebucht_nach_zeitregel()` nach den Zeitregeln (ohne Rundung bleibt der Wert); Wächter
  `tests/test_v466_rundung_gruppen.py`.
- **Vergessener Feierabend** (seit 1.9.35): nichts schließt eine Zeit von selbst. Läuft sie seit einem früheren Tag
  (`app/time_tracking.py::laeuft_seit_frueher()`), lehnt der Stopp ab (409), ebenso jeder neue Start (`OffeneZeit`); geschlossen wird sie
  nur über `POST /api/time-entries/{id}/ende-nachtragen` (Ende am Starttag, Pausenregel; Gruppenzeit nur der Kolonnenführer, fremde nach
  `darf_zeit_fuer_andere_buchen()`, im abgeschlossenen Monat nicht die Monteurin). `tests/test_v463_ende_nachtragen.py`.
- **Einsatzbericht: „Noch offen“ vor jeder Unterschrift** (seit 1.9.36): die Pflichten nur aus `app/service_reports.py::noch_offen()`
  (dieselben wie seit 1.2.16/1.2.17, je mit Namen); die Seite fragt `GET /api/service-reports/{id}/noch-offen` (seit 1.9.67 vor „Bericht
  abschließen“ der Berichtsseite, bis 1.9.66 vor beiden Unterschriften) nach `nachDemSpeichern()` (`_speichern.html`); die Unterschrift lehnt mit 409 und der Liste ab. Ein
  Punkt aus der Prüfvorlage ist nicht löschbar (409, seit 1.9.41 jeder, bis dahin nur Pflichtpunkte), nur ein von Hand ergänzter. Eine neue Pflicht gehört in `noch_offen_je_schritt()` (seit 1.9.66 je Schritt der
  Berichtsseite; `noch_offen()` nimmt die Texte daraus; seit 1.9.70 mit „ · <Dachfläche>“ bei mehr als einer Fläche und ohne zwei gleiche
  Zeilen, `tests/test_v494_noch_offen_flaechen.py`). `tests/test_v464_noch_offen.py`. **Seit 1.9.66** braucht ein Rapport ohne Vorlage
  (`hat_pruefpunkte()`) die Beschreibung, die Art ist nur im leeren Bericht änderbar (`bericht_leer()`, sonst 409 `ART_FEST`; mit ihr wechseln
  Vorlagen und Prüfpunkte wie beim Anlegen), `PUT /api/service-reports/{id}` ist ein Teil-Update, „Befund“ statt „Mangel“
  (`tests/test_v492_bericht_regeln.py`). **Zeiten im
  Bericht** (seit 1.9.42, ersetzt 1.9.37): alle Zeiten des Auftrags am Tag des Berichts, alle Personen (`zeiten_am_tag()`); Seite und PDF
  zeigen dieselben Zeilen (`zeiten_des_berichts()`), mit der Unterschrift in `ServiceReport.time_rows_json` gespeichert und danach
  unverändert; vor 1.9.42 unterschrieben (ohne Stand) wie vor 1.9.37 alle Zeiten des Auftrags. `tests/test_v467_zeiten_einsatzbericht.py`.
- **Keine Zeiten der Monteurin auf abgeschlossene oder stornierte Aufträge** (seit 1.9.81): Start, Nachtrag, Ändern (dorthin, dort,
  weg), Löschen, Kolonne, „Zeitart wechseln“ und „Pausen neu rechnen“ an einer Buchung dort 409 (bis 1.9.123 403) mit der Meldung aus
  `app/time_tracking.py::auftrag_zeiten_gesperrt()` (`_require_order_open_for_field()` in `app/routers/time_tracking.py`); Stopp,
  Gruppen-Stopp und Ende nachtragen bleiben frei, das Büro bucht wie bisher (`tests/test_v504_keine_zeiten_auf_abgeschlossene.py`; seit 1.9.90
  bietet der Kontext dem, der für andere bucht, die geschlossenen Aufträge nach den offenen an, gekennzeichnet, jede Buchung trägt
  `auftrag_geschlossen`, `tests/test_v511_buero_von_bis_und_geschlossen.py`); seit
  1.9.82 zeigt die Seite des Auftrags statt „Zeit nachtragen“ die Meldung (`OrderFieldAccessOut.zeiten_gesperrt`,
  `tests/test_v505_auftragsseite_zeiten_gesperrt.py`, Klicktest `klicktest_zeiten_abgeschlossen.py`); seit 1.9.87 kennzeichnen „Heute“
  (Einsatzkarte, keine Vorbelegung, kein „Zeitart wechseln“) und „Meine Zeiten“ (kein „⋮“) solche Aufträge
  (`app/time_tracking.py::auftrag_geschlossen()`, `tests/test_v508_abgeschlossen_heute_und_zeiten.py`).
- **Zeit für andere buchen nur nach `app/permissions.py::darf_zeit_fuer_andere_buchen()`** (seit 1.8.152, seit 1.9.89 Admin und Büro –
  Finanzen): der Server prüft damit Buchen und Ändern fremder Zeiten, `/api/auth/status` meldet sie (`zeit_fuer_andere_buchen`), der
  Einsatzbericht zeigt die Auswahl „Mitarbeiter“ nur danach -- eine neue Stelle mit derselben Frage nimmt diese Funktion, keine eigene
  Rollenabfrage. **Seit 1.9.89 je Recht eine Regel daneben:** `darf_zeit_buchen()` (Büro – Auftrag liest die Zeiten aller, ändert nichts --
  `require_zeit_buchen` an jedem schreibenden Zeit-Endpunkt) und `darf_lohndaten()` (Stundenzettel, CSV, DATEV, Abschließen: Admin und Büro –
  Finanzen, `require_lohndaten`); im abgeschlossenen Zeitraum, beim Aufheben des Abschlusses und bei Anträgen nur der Admin
  (`tests/test_v510_rechte_zeiten.py`, `docs/archiv/rechtekonzept.md`, „Nachtrag 1.9.89“).
- **Ein Weg für Abwesenheiten** (seit 1.9.146): eine `EmployeeAbsence` entsteht nur in `app/absence_requests.py` (Wächter `tests/test_v566_abwesenheiten_ein_weg.py`). „Abwesenheit eintragen“ auf der Tafel (`POST /api/planning/absences`) ist ein Antrag: `eintragen()`, Admin gleich genehmigt, sonst offen,
  Rechte wie unter „Zeiten“ (`antrag_fuer()`). Löschen einer genehmigten nur der Admin (`darf_abwesenheit_loeschen()`), `abwesenheit_loeschen()`: der Antrag folgt (zurückgezogen, Vermerk). Migration `b2c7f4e19a06`: Abwesenheiten ohne Antrag bekamen einen.
- **Abwesenheiten und Anträge** (seit 1.9.101, Entscheidung Tobias): Admin und Büro – Finanzen sehen alle und stellen Anträge auch für andere
  (`app/permissions.py::darf_abwesenheiten_aller()`), entscheiden nur der Admin, zurückziehen nur, wer den Antrag gestellt hat
  (`darf_antrag_zurueckziehen()`, ohne vermerkten Antragsteller die Person selbst); Büro – Auftrag und die Monteurin nur die eigenen
  (`tests/test_v523_abwesenheiten_rechte.py`). Die Zahl am Reiter „Abwesenheiten“ zählt seit 1.9.109 wie „Prüfen“ nur, was auf das Konto
  wartet -- offene Anträge beim Admin (`tests/test_v529_zahl_abwesenheiten.py`).
- **Eine Zeitbuchung fürs Büro** (seit 1.9.113): „Einsatzberichte“ bucht nicht selbst -- „Zeit buchen“ öffnet auf „Zeiten“ den Dialog „Neue
  Buchung“ mit dem Auftrag (`/zeiten?auftrag=<id>&buchung=neu#buchungen`, Pause des Tags und Vorschau); eine neue Stelle, an der das Büro bucht, führt
  ebenso dorthin (`tests/test_v533_einsatzberichte_zeit_ueber_zeiten.py`).
- **„Erfasst von“ eines Befunds ist das anlegende Konto** (seit 1.9.112): der Server setzt Konto, Name und Mitarbeiter aus der Anmeldung
  (`findings.created_by_user_id`/`created_by_name`), mitgeschickt 422; „Durchgeführt von“ eines Berichts eine andere Person seit 1.9.121 nach
  der Regel der Zeiten `app/permissions.py::darf_zeit_fuer_andere_buchen()` (Admin, Büro – Finanzen; 1.9.112–1.9.120 nur der Admin), die Seite
  bietet nur das an (`tests/test_v532_befund_im_fremden_bericht.py`, `tests/test_v541_durchgefuehrt_von.py`).
- **Mit Geld arbeiten nur nach `app/permissions.py::darf_geld()`** (seit 1.9.111, Admin und Büro – Finanzen): jeder schreibende Endpunkt an
  Rechnungen, Zahlungen, Mahnungen und Nebenforderungen trägt `require_geld`, an Rechnung und Mahnung auch Zustellung nachtragen, Versandergebnis und
  Klären (`GELD_DOKUMENTE`); Büro – Auftrag liest alles, die Seiten bekommen `geld` von der Seitenroute und zeigen ohne den Hinweis statt der Knöpfe.
  Ein neuer Geld-Endpunkt nimmt `require_geld` (`tests/test_v531_rechte_geld.py` prüft jede Route der vier Router). **Seit 1.9.120 auch die
  Einstellungen mit Geld** -- Mahnstufen (samt Texten), Zahlungsbedingungen, Steuerschlüssel, alle Nummernkreise -- über
  `require_geld_einstellung` (dieselben Rollen, eigene Meldung); Büro – Auftrag liest sie gesperrt mit Hinweis (`tests/test_v540_einstellungen_mit_geld.py`).
  Archiv: `docs/archiv/redesign.md`, „Stufe 5, R1“ und „R1 Nachrunde“.
- **Abschließen nur geklärt** (seit 1.9.91): „Abgeschlossen bis“ rückt nur vor ohne laufende Zeiten bis zum Datum und ohne Tage mit unpassender
  Pause ab dem bisherigen Abschluss (ohne ihn im Monat des Datums) -- `app/time_backoffice.py::abschluss_hindernisse()`, sonst 409 mit `detail`
  und `liste`, auch für den Admin; Personalnummer, Lohnart, DATEV-Nummern sperren den Abschluss nicht (`tests/test_v512_abschluss_pruefen.py`).
  Zurückgenommen wird seit 1.9.105 nur auf ein früheres Monatsende, nie ganz (422, auch für den Admin; `tests/test_v525_arbeitstage_und_aufheben.py`).
- **DATEV-Export nur abgeschlossen und vollständig** (seit 1.9.92): Ende bis „Abgeschlossen bis“, sonst 409; fehlt eine Lohnart (je Zeitart,
  kein stiller Rückfall auf „Sonstige“), eine Personalnummer oder Berater-/Mandantennummer, 409 mit Liste, keine Datei
  (`app/time_backoffice.py::datev_fehlt()`); Stunden = die gespeicherten über `app/time_tracking.py::tagessumme()` -- dieselbe Summe in Übersicht,
  Stundenzettel und DATEV. Berater- und Mandantennummer (`TimeTrackingSettings`, Migration `750d709a4863`) speichert nur der Admin
  (`PUT /api/time-backoffice/datev-nummern`), im LODAS-Kopf `[Allgemein]` (`tests/test_v513_datev_export.py`).
- **Einsätze: Konflikte beim Speichern** (seit 1.9.143, Entscheidung Tobias „warnen, trotzdem planbar“): `app/planning.py::einsatz_konflikte()` rechnet wie die Tafel
  (`_conflicts()`). Warnungen (`WARNUNG_ARTEN`: Person, Kolonne, Gerät doppelt; abwesend) -> `PlanungsWarnung`, 409 mit `warnungen` und `hinweise`, nichts gespeichert (auch keine neue
  Arbeitsvorbereitung), bis `trotzdem_planen` mitkommt; Hinweise (`HINWEIS_ARTEN`: Feiertag, betriebsfrei, Wochenende, Kapazität) nur in der Antwort; Ändern fragt nur, wenn sich Kolonne oder
  Zeitraum ändern. Einsätze stornierter Aufträge zählen nicht (`tests/test_v563_konflikte_beim_speichern.py`, Klicktest `klicktest_plantafel_konflikte.py`).
- **Die Plantafel lädt, was sie zeigt** (seit 1.9.144): `GET /api/planning` ohne Abfrage je Auftrag oder Einsatz (`_einsatz_abfrage()`, `rueckstand()`, `slot_to_dict(tafel=…)`), Konflikte nur für
  Einsätze, die den Zeitraum berühren; die Auswahl im Dialog „Einsatz planen“ erst beim Öffnen über `GET /api/planning/auftraege` (`offene_auftraege()`, nur offene). Wächter: die Zahl der Abfragen hängt
  nicht an Rückstand, Einsätzen im Bild und alten Einsätzen (`tests/test_v564_plantafel_leistung.py`).
- **Der Zeitraum der Arbeitsvorbereitung** (seit 1.9.145, F12): kein Einsatz schreibt in `planned_start`/`planned_end`, das sind nur die Eingaben von Hand. Mit Einsätzen gilt deren Zeitraum (`app/work_preparation.py::einsatz_zeitraum()`, gelesen,
  `zeitraum_aus_einsaetzen`), von Hand dann 409 (`zeitraum_ohne_einsatz_pruefen()`); wer den geplanten Zeitraum anzeigt, nimmt diese Rechnung (`tests/test_v565_av_zeitraum.py`).
- **Planungsgrundlagen ändern nur nach `app/permissions.py::darf_planungsgrundlagen()`** (seit 1.9.147, Admin und Büro – Finanzen): `require_planungsgrundlagen` an `PUT /api/planning/settings`, Feiertagen und Ferien-Abgleich; Büro – Auftrag liest gesperrt mit Hinweis (`tests/test_v567_planungsgrundlagen_rechte.py`).
- **Ausblenden statt ausgrauen**: eine für eine Rolle nicht gedachte Seite fehlt im Markup
  (`can()`-Jinja-Global, `_dk_roles`-Markierung), nicht nur deaktiviert -- ein 403 auf einer
  Seiten-Route zeigt `access_denied.html`, nie rohes JSON.
- **Rollenlose Business-Logik, Redaktion im Router**: `app/*.py`-Geschäftslogik kennt keine
  Rollen; die Rollenentscheidung (volles vs. reduziertes Schema, z. B.
  `OrderOut | OrderFieldAccessOut`) sitzt ausschließlich in `app/routers/*.py`.
- **Datengrenze dauerhaft geprüft** (seit 1.8.22): `tests/test_v326_monteur_datengrenze.py` ruft
  jeden GET-Endpunkt unter `/api/` als Monteur auf und prüft jede JSON-Antwort rekursiv auf
  verbotene Schlüssel (Preise, Kosten, Löhne, Sätze, interne Notizen, Kundenkontakt,
  Gewährleistung, seit 1.8.24 Personaldaten samt Privatadresse an Personen, seit 1.8.27 "Wichtige
  Infos" am Mitarbeiter, seit 1.8.46 Vertragsstrafe, Einbehalt und Garantie). Ein neuer Endpunkt für
  `field` braucht Testdaten, die ihn mit Inhalt füllen; ein Feld, das der Monteur trotz verbotenem
  Namen sehen soll, eine begründete Ausnahme in `ERLAUBT_JE_ROUTE`. Seit 1.9.71 prüft
  `tests/test_v495_bericht_schluessel_monteurin.py` die Berichtsseite der Monteurin dazu auf Werte (Preis, Lohn), andere Aufträge und den
  Berichtstag der Zeiten.
- **Kein sichtbarer Link auf eine gesperrte Seite** (seit 1.8.24):
  `tests/test_v328_navigation_ohne_sperrseiten.py` rendert je Rolle jede erlaubte Seite und ruft
  jeden beim Laden sichtbaren Link als dieselbe Rolle auf -- kein 403, seit 1.8.65 auch kein 404; `BEKANNT_OFFEN` ist seit
  1.8.27 leer. Seit 1.8.65 prüft derselbe Test jedes Link-Ziel im JavaScript der Vorlagen und jeden "…url"-Wert im Python-Code
  gegen die Routen (Anlass: `/checklists/` statt `/checklisten/` in 1.8.63). Links, die erst das JavaScript baut (Breadcrumb der Berichtsseite), prüft der
  Klicktest `scripts/klicktest_monteur_navigation.py`; die Seite bekommt dafür vom Server, ob die
  Rolle Büro-Seiten öffnen darf (`darfBueroSeiten`).

## Self-Seeding gegen gleichzeitigen ersten Zugriff absichern (seit 1.4.6)

Das durchgängige `ensure_default_*()`-Muster dieses Projekts (siehe z. B. "Betriebsmittelverwaltung",
"Umbau der Projektliste", "Aufgabe" -- eine Tabelle wird lazy, beim ersten Lesezugriff, mit
Standardwerten befüllt, damit eine per `Base.metadata.create_all()` erzeugte Testdatenbank ohne
Alembic-Migration trotzdem sinnvolle Defaults bekommt) hatte eine reale Race Condition: zwei
gleichzeitige ERSTE Zugriffe auf eine frische, noch nie geseedete Tabelle lesen beide "leer",
versuchen beide dieselben Standardzeilen einzufügen -- der zweite kollidiert mit einer unabgefangenen
`sqlalchemy.exc.IntegrityError` (UNIQUE-Verletzung), die als 500 durchschlägt. Gefunden als
transparenter Nebenbefund während der 1.4.5-Browserverifikation
(`app/option_settings.py::ensure_default_option_groups()`, `group_key='units'`), in 1.4.6 behoben
-- Details, Abwägung Locking vs. Abfangen und der vollständige Sweep über alle `ensure_default_*()`-
Fundstellen stehen in CHANGELOG.md 1.4.6.

**Die Regel für jede künftige `ensure_default_*()`-Funktion, deren Tabelle einen UNIQUE-Constraint
trägt**: der Anlegeversuch (ob eine einzelne Zeile oder ein ganzer Satz -- je nachdem, ob die
Vorbedingung "dieser eine Schlüssel fehlt" oder "die Tabelle ist komplett leer" lautet) läuft in
einem `with db.begin_nested():`-Block (SAVEPOINT); eine dabei auftretende `IntegrityError` wird
abgefangen und als "ein anderer Prozess war schneller, schon gesät" behandelt, nicht als Fehler
weitergereicht. **Kein bloßes `db.rollback()`** auf der ganzen Session -- das würde auch bereits
zuvor in derselben Schleife erfolgreich angelegte, aber noch nicht committete Zeilen mit verwerfen;
das SAVEPOINT begrenzt den Rollback exakt auf den einen kollidierenden Versuch. **Kein
Sperrmechanismus** -- ein Advisory-Lock wäre PostgreSQL-spezifisch und hätte unter SQLite (dem
zweiten, gleichberechtigt unterstützten Dialekt dieses Projekts) keine Entsprechung.

**Trägt die Tabelle KEINEN UNIQUE-Constraint**, ist die Funktion nicht von dieser Race-Condition-
Klasse betroffen (kein Crash), sondern von einer anderen, leiseren: ein Wettlauf würde stille
doppelte Zeilen anlegen. Das Abfangen einer nie geworfenen `IntegrityError` bewirkt dort nichts
(Fälle: `app/document_layout.py`, `app/payment_terms.py`, `app/tax_keys.py`, `app/reminders.py`, siehe
CHANGELOG.md 1.4.6).

**Seit 1.8.42 (Regel 23)** laufen alle `ensure_default_*()` nur noch als Schritte von `app/grunddaten.py::anlegen()`
beim Start, in einer Transaktion hinter einer Sperrzeile (`general_settings` FOR UPDATE, unter SQLite
`BEGIN IMMEDIATE`) -- zwei Prozesse treffen sich nicht mehr im selben Schritt, auch die vier Sätze ohne UNIQUE und
die Singleton-Einstellungen nicht. Der SAVEPOINT je Schritt bleibt als zweite Absicherung; die Schritte committen
nicht selbst (ein Commit gäbe die Sperre frei). Achtung SQLite: pysqlite beginnt die Transaktion erst vor der
ersten Änderung -- ein SAVEPOINT davor ist selbst die Transaktion, sein RELEASE committet.

## Migrations-Workflow

Bisher: Claude erstellt/ändert Modelle → Tobias führt lokal `alembic revision --autogenerate`
aus und schickt die generierte Datei zurück → Claude prüft sie systematisch gegen die
tatsächlichen Modelldefinitionen (Kettenanschluss an den aktuellen Kopf, `server_default` bei
neuen NOT-NULL-Spalten, Spaltennamen 1:1 gegen `app/models.py`) → nach Bestätigung führt Tobias
`alembic upgrade head` aus.

**In Claude Code kann sich das vereinfachen**, da direkter Terminalzugriff besteht: Claude Code
kann `alembic revision --autogenerate` und bei Bedarf auch `alembic upgrade head` selbst
ausführen. Die inhaltliche Prüfung (Kettenanschluss, `server_default`, Feldnamen) bleibt trotzdem
wichtig – nur eben vor Ort statt per Hochladen einer Datei.

**Seit 1.3.42 muss `DATABASE_URL` dafür ausdrücklich gesetzt sein, auch lokal** -- siehe
"Produktivbetrieb" → "Zwei Vorfälle beim Ausliefern von 1.3.38–1.3.41" oben für den realen
Vorfall, der dazu geführt hat. `alembic/env.py` fällt anders als `app/database.py` NICHT mehr
still auf SQLite zurück, sondern bricht mit einer klaren Fehlermeldung ab, wenn die Variable
fehlt. Ein `alembic`-Aufruf in dieser Sitzung/lokal sieht deshalb künftig so aus:
`DATABASE_URL=sqlite:///./dachkonzepte_erp.db alembic upgrade head` (oder die lokale
Postgres-Verbindungszeichenfolge) -- nicht mehr nackt `alembic upgrade head` ohne vorangestellte
Variable, wie es in dieser Sitzung bisher wiederholt üblich war.

**Fallstrick, seit 1.3.31 real erlebt: ein laufender `--reload`-Dev-Server tut dasselbe bei jedem
Speichern.** Läuft während der Arbeit bereits ein `uvicorn --reload`-Prozess gegen die echte
`dachkonzepte_erp.db` (z. B. vom Nutzer selbst gestartet), lädt dessen Auto-Reload bei JEDER
Dateiänderung im Projekt -- nicht nur an tatsächlich importierten Modulen, auch an einer neuen
Alembic-Migrationsdatei selbst -- `app.main` komplett neu, was denselben
`Base.metadata.create_all()`-Sicherheitsnetzaufruf erneut auslöst. Ergebnis real beobachtet: eine
neu erzeugte, noch nicht migrierte Tabelle (hier: `import_runs`/`imported_addresses`) wurde
zwischen zwei `alembic upgrade head`-Versuchen durch genau diesen Reload wiederholt neu angelegt,
obwohl sie zuvor per Skript gezielt gelöscht worden war -- `alembic upgrade head` schlug dadurch
mehrfach mit "table already exists" fehl, bis geprüft wurde, ob ein solcher Prozess überhaupt
läuft (`Get-Process` nach `uvicorn`/`python`). Lehre: vor `alembic upgrade head` prüfen, ob ein
laufender Dev-Server-Prozess existiert; wenn ja, entweder kurz stoppen lassen oder das Fenster
zwischen letzter Dateiänderung und `alembic upgrade head` so kurz wie möglich halten (keine
weitere Datei mehr anfassen, bevor die Migration durchgelaufen ist).

**Fallstrick (seit 1.2.23 bekannt): `app/main.py` ruft beim Import `Base.metadata.create_all(bind=engine)`
auf** – ein alter Sicherheitsnetz-Aufruf, der jede in `app/models.py` neu definierte Tabelle
sofort real anlegt, sobald irgendetwas `app.main` importiert (z. B. ein simpler
Smoke-Test-Aufruf wie `python -c "import app.main"`). Passiert das NACH dem Hinzufügen eines
neuen Modells, aber VOR `alembic revision --autogenerate`, findet Autogenerate keinen
Unterschied mehr (die Tabelle existiert ja schon) und erzeugt eine leere, nutzlose
No-op-Migration – die eigentliche `CREATE TABLE` fehlt dann in der Migrationskette, obwohl die
lokale DB bereits funktioniert. Selbst passiert, real erlebt: die neue Tabelle musste per
`DROP TABLE` wieder entfernt werden, bevor Autogenerate sie korrekt erkannte. Deshalb: nach dem
Anlegen eines neuen Modells zuerst `alembic revision --autogenerate`, danach erst irgendetwas
importieren, das `app.main` lädt (ein reiner `import app.models`-Check löst den Sicherheitsnetz-
Aufruf nicht aus, das ist unbedenklich).

**Dieser Mechanismus ist kein rein theoretisches Risiko** -- er ist bei `invoices`/
`invoice_items` (Migration `e057d15af828`) tatsächlich eingetreten und blieb unter SQLite
jahrelang unsichtbar, bis eine echte, frische PostgreSQL-Verifikation ihn aufgedeckt hat. Siehe
Abschnitt "PostgreSQL-Umstieg: Migrationskette repariert" oben für die vollständige Herleitung
und den Verifikationsnachweis (Version 1.3.35, 13.09.2026).

## Testen

- `pytest` läuft in Tobias' `.venv` unter Windows – **bitte tatsächlich ausführen**, nicht nur
  Syntax/Feldnamen von Hand prüfen, wenn eine Ausführung möglich ist.
- `cryptography`, `pytest` müssen in `requirements.txt` stehen (fehlten beide anfangs).
- E-Mail-Tests mocken `smtplib.SMTP` bzw. `urllib.request.urlopen` **am Verwendungsort**, nicht am
  Ursprungsmodul – also `@patch("app.email_sending.smtplib.SMTP")`, nicht
  `@patch("smtplib.SMTP")`.
- Bestehende Test-Hilfsfunktionen wiederverwenden statt neu bauen, u. a.:
  `db_session()` und `make_sent_overdue_invoice()` in `tests/test_v153_mahnwesen.py`,
  `make_order_with_item()` in `tests/test_v133_invoices.py`,
  `make_quote_with_items()` in `tests/test_v167_pagination.py`,
  `make_full_project()` in `tests/test_v192_project_templates.py` (nimmt seit Kurzem optionale
  `project_number`/`quote_number`-Parameter, falls in einem Test mehrere Projekte gebraucht werden).
- **Echte Routen-Tests über den `TestClient`** (seit 1.2.15, z. B. um eine Literal-vs-
  Platzhalter-Routenkollision zu beweisen, nicht nur die Business-Funktion direkt aufzurufen):
  `tests/conftest.py` stellt dafür die Fixtures `threaded_db_session` (wie `db_session`, aber
  `check_same_thread=False` + `StaticPool`, weil der `TestClient` Endpunkte über einen
  Threadpool ausführt) und `router_test_client` (Fabrik, baut aus echten Router-Instanzen eine
  schlanke Test-App mit fest angemeldetem Admin-Kontext (seit 1.8.57 optional `user_id`/`display_name` -- ein Konto mit
  ID, z. B. für Unterschriften "angemeldetes Konto"), ohne die produktive
  `identity_and_audit_middleware`) bereit – seit 1.2.16 dort zentral, nicht mehr lokal in
  `test_v212_maintenance_windows.py` dupliziert. Verwendung:
  `client = router_test_client(db, some_router, other_router)`.
- **Eine Migrationsdatei selbst testen** (neu seit 1.2.19, `tests/test_v217_*.py`): Migrationen
  laufen sonst nie unter `pytest` (frische `:memory:`-DBs überspringen sie, siehe oben) – für
  Punkt 6 der 1.2.19-Planung (Bauteilarten-Migration muss vorhandene `setting_options`-Zeilen
  statt einer Code-Konstante lesen) war ein echter Test der Migrationslogik trotzdem
  gefordert. Lösung: die eigentliche Auswahl-Logik steckt als eigene, modulweite Funktion
  (`_resolve_roof_component_type_rows(bind)`) direkt in der Migrationsdatei, NICHT in
  `upgrade()` verschachtelt; der Test findet die Datei per `Path(...).glob(...)` über einen
  selbst gewählten, beschreibenden Namensteil (nicht über den Alembic-Hash, der bei einer
  erneuten `--autogenerate`-Ausführung wechseln würde), lädt sie per
  `importlib.util.spec_from_file_location()` + `exec_module()` und ruft die Funktion direkt
  gegen eine präparierte `Connection` auf. Neues Muster, kein bisheriges Vorbild – bei Bedarf
  für künftige Migrationen mit ähnlich nicht-trivialer Datenübernahme wiederverwendbar.
- **Jinja-Vorlagen wirklich rendern lassen** (neu seit 1.2.20, `tests/test_v218_template_rendering.py`):
  vorher deckte die Suite Templates gar nicht ab – ein Rekursionsfehler in `_debounce.html`
  (1.2.19) wurde erst bei der manuellen Server-Smoke-Prüfung gefunden. Neuer Test rendert JEDE
  Seiten-Route aus `app/routers/pages.py` (dynamisch aus `pages_router.routes` gewonnen, kein
  hartkodierter Pfad-Katalog) einmal über `router_test_client()` und prüft auf Status 200 – exakt
  das würde einen erneuten Rekursionsfehler in einer beliebigen Vorlage fangen, ganz unabhängig
  davon, ob die verwendete Beispiel-ID real existiert (Seiten in diesem Projekt laden alle echten
  Daten clientseitig per `fetch()` nach, der Server rendert nur das Gerüst). Siehe "Bekannte,
  bewusst offene Punkte" für die dabei ausgelöste, bestehende `SessionLocal()`-Kopplung der
  Jinja-Globals – für diesen (rein lesenden) Test unschädlich, aber kein Vorbild für einen
  künftigen, auch schreibenden Test.
- **`reportlab.platypus.Frame`-Geometrie direkt prüfen** (neu seit 1.3.1,
  `tests/test_v226_document_frame.py`): um zu belegen, dass unterschiedliche
  `DocumentPageMargins`-Werte tatsächlich unterschiedliche Seitenvorlagen ergeben, wird die
  interne Bausteinfunktion `app/document_frame.py::_build_frame()` direkt aufgerufen (kein
  vollständiges PDF nötig) und die resultierenden `Frame`-Attribute (`x1`/`y1`/`width`/`height`,
  öffentlich, kein Privat-Zugriff nötig) verglichen – robuster und schneller als Text-/
  Positionsextraktion aus gerenderten PDF-Bytes. Für "Seite X von Y" dagegen weiterhin die
  etablierte Content-Stream-Textextraktion (`_extract_pdf_text()`, seit 1.2.16 in
  `tests/test_v213_inspection_items.py`, hier wiederverwendet statt dupliziert).

- **Echte Anmeldung in Tests** (seit 1.8.98, Regel 30): `tests/anmeldung.py::client_mit_schranke(make_session, *router)` bzw.
  `app_mit_schranke()` baut eine Test-App mit der echten Anmeldeschranke (`app/anmeldeschranke.py`) und eigener Sitzungsfabrik
  (`neue_datenbank()`); angemeldet wird über `POST /api/auth/login` oder direkt mit `app.sitzungen.neue_sitzung(db, user,
  zweiter_faktor=True)` als Cookie `dk_erp_auth` (Domäne `testserver.local`, sonst hält httpx zwei Cookies gleichen Namens). Seit 1.8.104
  (Regel 33) einen eigenen Client über die Schranke mit `browser_client(app)` bauen (Origin und Sec-Fetch-Site der eigenen Seite), sonst
  bekommt jede schreibende Anfrage 403. Seit 1.8.107 läuft jeder Test mit `ERP_ENV=test` (`tests/conftest.py`, sonst wäre das Cookie
  Secure), und `app_mit_schranke()` bindet auch den Fehler-Handler ein.

- **Grunddaten in jeder Testdatenbank** (seit 1.8.42): `tests/conftest.py` ruft nach jedem
  `Base.metadata.create_all()` `app.grunddaten.anlegen()` auf -- wie der Start einer echten Installation. Ein Test,
  der den Vorzustand genau braucht (Migrationstests, `anlegen()` selbst), legt die Tabellen in
  `with ohne_grunddaten():` (`tests/grunddaten_schalter.py`) an. Audit-Zähler in Tests: die Grunddaten schreiben
  "System angelegt"-Einträge -- vorher/nachher vergleichen statt absolut zählen.

- **Gleichzeitigkeit in Tests** (`tests/test_v375_rechnungen_sperren.py::_run()`): die erste Aktion hält ihre Sperren, bis die zweite
  nachweislich wartet (seit 1.9.8 `_wartet_auf_sperre()`: unter PostgreSQL eine nicht gewährte Sperre in `pg_locks`, unter SQLite ihre
  erste schreibende Anweisung -- bis dahin eine feste Sekunde, unter Last zu kurz); ein Test wartet nie eine feste Zeit auf einen Zustand,
  sondern bis er eintritt (`_bis()`, Zeitgrenze nur als Sicherheitsnetz), und prüft keine Dauer gegen eine feste Schranke; seit 1.8.87 schließt `_run` auch die Sitzung der zweiten Aktion (sie hielt nach einem Fehler die Sperre der
  Auftragszeile) -- die zweite Aktion gibt Werte zurück, keine Objekte, die erst danach nachladen. Seit 1.8.111 schließen auch die
  Kopien in `tests/test_v363_zweck_abnahme.py` und `tests/test_v365_abnahme_aus_protokoll.py` die zweite Sitzung, bevor sie auf die
  erste warten; eine hängende Aktion macht den Test rot.

- **Mahnung zustellen in Tests** (seit 1.8.80): eine Stufe ist erst mit Versand oder Zustellung erreicht --
  `tests/mahnung.py::zustellen(db, reminder)` trägt eine Zustellung ins Versandprotokoll ein (ohne PDF), `festschreiben_und_ablaufen()`
  schreibt fest, stellt zu und lässt die Frist ablaufen. **Bestand älterer Stände** für Migrationsproben über `tests/bestand_alt.py`
  (Core-Insert mit den Spalten des jeweiligen Stands, ohne `anlegen()`) -- das ORM von heute schreibt Spalten, die es dort nicht gibt.

- **PostgreSQL-Tests nie in `public`** (seit 1.8.81, Regel 27): Wächter `tests/pg_schutz.py` für den ganzen Testprozess, `pg_url_pruefen()`
  für jede `DATABASE_URL` an einen Kindprozess. Seit 1.8.108 bekommt jedes `CREATE SCHEMA pgtest_…` die Kennung des Prozesses als Kommentar
  (nichts dafür zu tun, der Wächter hängt sie an); ein Schema mit erfundenem Kommentar für einen Test über eine Engine mit
  `-csearch_path=pg_catalog` anlegen (Vorlage `tests/test_v413_testlauf_parallel.py`). Verzugszinsen in Tests: Basiszinssätze (Testwerte) direkt als `BaseInterestRate` mit
  Prüfangabe anlegen, Verzugsbeginn direkt als `InvoiceDefaultStart` (Vorlage `tests/test_v384_verzugszinsen.py::_saetze()`,
  `_im_verzug_seit()`).

- **Rechnung festschreiben in Tests** (seit 1.8.74): jede Rechnung braucht beim Festschreiben einen Leistungszeitraum --
  `tests/leistungszeitraum.py::festschreiben(db, invoice)` trägt in einen Entwurf ohne Zeitraum einen ein (wie "Übernehmen")
  und schreibt fest; `mit_zeitraum()` nur den Zeitraum, `ZEITRAUM_JSON` für ein PUT vor `/send`. In Gleichzeitigkeitstests
  den Zeitraum in der Vorbereitung eintragen (der angehaltene Commit soll beim Festschreiben liegen). Die Pflicht selbst prüft
  `tests/test_v377_leistungszeitraum.py` mit `finalize_and_send_invoice()`.

- **Seitenskript in node ausführen** (seit 1.8.95): die Seiten speichern über `speichern()` -- eine Testseite aus Attrappe und
  Seitenskript braucht `_speichern.html` dazu (Vorbild `tests/test_v334_auswahl_restfaelle.py::seite()`), sonst endet jedes Speichern mit
  "speichern is not defined". Ein Test, der den Rumpf einer Speicherfunktion wörtlich liest (`tests/test_v329_teil_updates.py::ui_keys`),
  findet `body:JSON.stringify(` im Pfeil innerhalb von `speichern()`. Seit 1.8.109 dazu `_zahl.html` (Zahlenfelder lesen über
  `zahlFeld()`; die Attrappe eines Felds braucht `dataset`, `getAttribute`, `setAttribute`, `removeAttribute`, der Wert steht deutsch
  im Feld). Seit 1.8.116 bindet `seite()` die Bausteine ein, die die Seite selbst einbindet (auch `_fehlertext.html`), und jeder node-Lauf
  geht über `tests/node_lauf.py` (Regel 36): eine gefangene JS-Ausnahme lässt den Test scheitern -- eine Attrappe, die absichtlich wirft,
  braucht `erlaubt=` mit Grund. Eine Antwort, die die Seite zeichnet, kommt besser vom echten Dienst (`router_test_client`) als erfunden. Hängt das Skript an Werten des Servers (Art des Bereichs, ID, Ziel nach dem Speichern), nimmt der Test die vom Server gezeichnete Seite statt der Vorlage: `tests/gerenderte_seite.py::gerenderte_seite(html, start)` (seit 1.8.145).

- **Vorlagen über `tests/vorlagen_js.py` lesen** (seit 1.8.123, Stufe 0a des Redesigns): eine Prüfung über alle Vorlagen nimmt
  `alle_vorlagen()` (auch Unterordner, Namen wie "teile/x.html"), `seiten()` und die zusammengesetzte Seite aus `zusammensetzen()`
  (extends mit Blöcken und `super()`, Includes, die Makros importierter Dateien; `seitentext()` ohne Includes) -- nie `glob("*.html")`
  (Wächter in `tests/test_v428_strukturtests_basis_und_makros.py`, seit 1.8.124 über jede Datei unter `tests/` und jedes Auflisten des
  Vorlagenordners). Seit 1.8.124 (Stufe 0b): ein Include verlangt ein Test über `bindet_ein()` (selbst oder im Basis-Template);
  `seiten()` = was `app/` per `TemplateResponse` ausliefert, eine neue Seitenroute nimmt einen festen Namen oder `a if b else c`
  (`tests/test_v429_strukturtests_stufe_0b.py`); **Makro-Regel**: in einem Makro kein Jinja in `type=`, `on…=`, `href=` und kein
  `{{ … }}` an der Stelle eines Attributs -- was die Scanner prüfen, steht fest im Makro oder wörtlich in der Seite (über `{% call %}`),
  geprüft in `vorlagen_html.jinja_handler()`. Seit 1.8.125 prüft kein Test ein Include per Textvergleich (`'{% include … %}' in text`,
  ein Vorlagenname gegen eingelesenen Text) -- nur `bindet_ein()` (`nur_selbst=True` für die Datei allein); Wächter in
  `tests/test_v430_strukturtests_stufe_0c.py`. Die Token-Prüfung der Monteursseiten in v272 (bis 1.9.4 `get_theme()` im eigenen
  `:root{`) prüft seit 1.9.5 das Gegenteil: keine Kopie der Palette, `_ds_kopf.html` eingebunden.

- **Feste Uhr statt Tageszeit** (seit 1.8.36): ein Test, dessen Ergebnis von der Uhrzeit abhängt (z. B. Monteur
  an `/api/field-view/today`, ab 19:00 "Feierabend" 401), nimmt die Fixture `feste_uhr` bzw. in einer Modul-Fixture
  `with uhr_festhalten():` (`tests/uhr.py`, laufende Uhr ab heute 10:00 Europe/Berlin über `app.berlin_time._utc_now`).
  `pytest --wanduhr 19:30` lässt die Suite laufen, als wäre es 19:30 -- die Gegenprobe ohne Warten auf den Abend.

- **`pytest -q` als Standard-Aufruf** (Regel 15 oben) -- bei über 1800 Tests erzeugt die volle
  Ausgabe (inkl. `DeprecationWarning`-Sammlung) allein schon zehntausende Zeilen, ohne bei einem
  grünen Lauf zusätzliche Information zu liefern. `pytest.ini` blendet die
  `datetime.utcnow()`-Warnung (siehe "Bekannte, bewusst offene Punkte" unten) gezielt aus, damit
  sie einen knappen Lauf nicht trotzdem mit Warnzeilen flutet.

### Headless-Chrome-Verifikation über CDP (seit 1.3.73)

Dutzende frühere Versionen dieser Datei vermerken "kein Browser-Automatisierungswerkzeug
verfügbar" (kein Playwright/Puppeteer als Projekt- oder Systemabhängigkeit) und belegen
UI-Änderungen deshalb nur strukturell (Quelltext-/CSS-Prüfung, `node --check`). Für 1.3.73 wurde
das erste Mal geprüft, ob das wirklich stimmt -- Ergebnis: **Chrome UND Edge sind auf dieser
Windows-Maschine bereits systemweit installiert** (`C:\Program Files\Google\Chrome\Application\
chrome.exe`, `...\Microsoft\Edge\...`), auch wenn kein npm-Paket wie Playwright/Puppeteer im
Projekt oder global via npm vorhanden ist. Chrome lässt sich mit `--headless=new
--remote-debugging-port=<port>` gezielt für genau eine automatisierte Sitzung starten (eigenes
`--user-data-dir` im Scratchpad, unabhängig vom Profil des Nutzers) und über das Chrome
DevTools Protocol (CDP) fernsteuern -- **ohne** npm-Installation, da PowerShell/.NET bereits
einen WebSocket-Client mitbringt (`System.Net.WebSockets.ClientWebSocket`). Ablauf, der für
1.3.73 tatsächlich funktioniert hat: `GET http://127.0.0.1:<port>/json/list` liefert die
`webSocketDebuggerUrl` der Seite, `Network.setCookie` setzt das Session-Cookie (aus einem
vorherigen HTTP-Login übernommen -- kein UI-Login nötig), `Page.navigate` lädt die Zielseite,
`Runtime.evaluate` führt beliebiges JS aus (Klicks simulieren, Zustand auslesen), `Page.
captureScreenshot` liefert ein PNG zur visuellen Bestätigung. **Wichtig, sonst false positives**:
`Runtime.evaluate` mit `returnByValue:true` liefert bei einem JS-Fehler ein leeres Ergebnis statt
eines Fehlers, wenn `exceptionDetails` nicht explizit geprüft wird -- ein Test, der das
übersieht, hält einen kaputten Aufruf für "erfolgreich, aber leer". Ein eigens ausgeführter
Testlauf hätte ohne diese Prüfung fast einen Testfehler übersehen (siehe Abschnitt "Runde 2" bei
1.3.72 -- der erste Testdurchlauf für "letzte Zeile" schlug fehl, weil `.wrap.scrollTop=999999`
zwar den TABELLEN-eigenen Scroll ausreizt, aber die SEITE selbst (Kopfzeile+Toolbar+Karte)
zusätzlich Platz braucht, den ein echter Mausrad-Scroll durch Scroll-Chaining automatisch
mitnimmt, ein reines `.wrap.scrollTop=...` aber nicht -- `window.scrollTo(0,
document.body.scrollHeight)` musste ergänzt werden, sonst wurde ein tatsächlich unsichtbarer,
außerhalb des Ansichtsfensters liegender Knopf angeklickt, was kein reales Nutzerszenario
abbildet).

**Seit Runde 0e (29.09.2026) liegt das Werkzeug im Projekt, statt je Runde im Scratchpad neu
gebaut zu werden:** `scripts/cdp_klicktest.py` startet eine isolierte Instanz (Wegwerf-SQLite,
eigener `ERP_DATA_DIR` und `ERP_SECRET_KEY` in einem Temp-Ordner, Regel 16), Chrome headless mit
eigenem Profil, und beendet beide nur über die eigene PID (Regel 12); die beiden Fallen oben
(`exceptionDetails`, Bereitschaftsbedingung) sind dort abgefangen. Je Prüfung ein
`scripts/klicktest_*.py` mit `befuellen()` und `pruefen()`, Anleitung und Optionen im Dateikopf,
Aufruf `.venv\Scripts\python.exe scripts\klicktest_<name>.py` (Rückgabecode 0 = alles wie
erwartet). Vorhanden: `klicktest_zeitbuchungen_liste.py` (1.8.9, acht Seiten, Daten relativ zum
heutigen Datum), `klicktest_dashboard_monatswechsel.py` (1.8.10, festgehaltene Browser-Uhr und
-Zeitzone) und `klicktest_rechnung_rundung.py` (1.8.11, Rechnungsseite: USt, Positionsbetrag,
Skonto, dazu die vom Server gelieferten Beträge) und `klicktest_checkliste_unterschrift.py` (1.8.13,
Unterschrift sperrt die Checkliste, Büro verwirft mit Begründung, "repariert" mit Notiz) und
`klicktest_checkliste_abschnitte.py` (1.8.14, Unterschrift versiegelt nur den Abschnitt darüber,
direkt in der Wegwerf-Datenbank geänderte Antwort erscheint als Abweichung) und
`klicktest_checkliste_verwerfen.py` (1.8.15, Verwerfen je Unterschrift, Abschluss mit Prüfsumme, hell
und dunkel) und `klicktest_checkliste_zweck.py` (1.8.16, Zweck und Systemfelder im Vorlagen-Editor,
Start-Auswahl nach Zweck) und `klicktest_versandprotokoll.py` (1.8.17, Versand über alle vier Seiten an
einen SMTP-Empfänger im Skript, Doppelklick, Protokollseite; seit 1.8.19 auch Adressprüfung, Nachdruck
aus der Ablage, Klären eines hängenden Eintrags) und `klicktest_versandverlauf.py` (1.8.20, Versandverlauf auf
allen Dokumentseiten, Zustellung nachtragen mit Beleg-Upload, Checkliste mit 20 Fotos per E-Mail) und
`klicktest_aufgaben_ohne_zustaendigkeit.py` (1.8.18, Abschnitt und Widget "Ohne Zuständigkeit" für vier Rollen,
zweiter Klick nach fremdem Übernehmen, Historie nur für Admin) und `klicktest_vertragsgrundlage.py` (1.8.21,
Verbraucher-Häkchen, Vertragsgrundlage im Angebots-Editor und am Auftrag mit Begründung, Klauseln in den
Einstellungen für Admin und Büro) und `klicktest_monteur_dachflaechen.py` (1.8.22, Dachflächen-Auswahl im
Einsatzbericht als Monteur mit dem reduzierten Schema, Bericht mit Fläche anlegen) und
`klicktest_angebot_interne_notiz.py` (1.8.23, Angebotskopf speichern lässt die interne Notiz stehen) und
`klicktest_monteur_navigation.py` (1.8.24, sichtbare Links in Seitenleiste und Kopfzeile je Rolle ohne 403, seit 1.8.27 auch
im Seiteninhalt und der Adressimport-Knopf) und
`klicktest_teil_updates.py` (1.8.25, Speichern in mobiler Zeiterfassung, Einstellungen, Rechnung und Leistung lässt
nicht bearbeitete Felder stehen) und `klicktest_arbeitsvorbereitung.py` (1.8.29, Freitext-Lieferant, Planstunden und
Reihenfolge bleiben beim Speichern) und `klicktest_auswahl_inaktiv.py` (1.8.30, inaktive Mitarbeiterin, inaktiver
Lieferant und archiviertes Projekt bleiben in Auftrag, Aufgaben-Editor und Arbeitsvorbereitung vorgewählt und gespeichert)
und `klicktest_auswahl_restfaelle.py` (1.8.31, abgeschlossener Auftrag in der Backoffice-Korrektur, archivierter
Steuerschlüssel, inaktiver Schichttyp, leerer Schlusstext 2 und leere Einheit im Angebot, Kunden-Kategorie)
und `klicktest_vertragsvorlagen.py` (1.8.32, Vertragsvorlagen in den Einstellungen für Admin und Büro, Ausführungszeitraum
und Karte "Vertrag" auf der Auftragsseite, Entwurf von Hand anlegen) und
`klicktest_vertrag_festschreiben.py` (1.8.33, Anlage bewusst wählen, Fassung festschreiben, Versand an einen
SMTP-Empfänger im Skript mit Anhang = Fassung, neue Fassung, versendete Fassung ohne Rückfrage, Monteur 403) und
`klicktest_vertrag_unterschrift.py` (1.8.34, Zeichnen über CDP-Mausereignisse: Vertrag auf dem Gerät mit Ankreuzfeld,
Sperren danach, Widerrufsfrist, Papier-Scan, Checkliste und Einsatzbericht über die gemeinsame Fläche, dunkel und hell)
und `klicktest_vertrag_abschrift.py` (1.8.35, unterschriebene Abschrift auf der Karte und als Anhang, nachgeholt für eine
ältere Unterschrift, Papier-Foto; lesbare 422/409 der Auftragsseite) und `klicktest_beteiligte.py` (1.8.37, Adressbuch mit
Archivieren und Löschen, Reiter "Beteiligte": suchen, doppelt, neu anlegen und zurück, Vollmacht, Rolle ändern, hell/dunkel,
412 px, Monteur 403) und `klicktest_behinderungsanzeige.py` (1.8.38, Startvorlagen über die Migrationsfunktionen: Monteurin
meldet und unterschreibt auf 412 px, Anzeige für sie gesperrt; Büro dunkel mit Folgen-Karte, Witterungs-Hinweis, Unterschrift
Büro; Link aus der Tagesbericht-Aufgabe; Editor) und `klicktest_beteiligte_stammdaten.py` (1.8.39, Dialog nach Herkunft
gruppiert, Auftraggeber gesperrt, Kunde und inaktiver Lieferant hinzufügen, geänderte E-Mail im Kunden beim Beteiligten,
ein Eintrag für zwei Projekte, Formular schreibgeschützt, dunkel, 412 px, Monteur 403) und
`klicktest_behinderungsanzeige_versand.py` (1.8.40, Karte "Anzeige an den Auftraggeber": wartet → Unterschrift Büro → bereit mit
Warnung ohne Vorbehalt, Admin prüft den Vorbehalt, Versand an einen SMTP-Empfänger im Skript mit An fest und Anhang = abgelegter
Brief, Vollmacht im Verlauf, Aufgabe erledigt, dunkel 412 px, Monteurin 403, Wiederaufnahme per "Brief erstellen" und
Einschreiben) und `klicktest_behinderungsanzeige_abschluss.py` (1.8.41, Zeitstrahl, "Unzustellbar" und "Empfang bestätigt" mit
Beleg-Upload im Versandverlauf, Zustellung nachtragen mit Empfängerauswahl und Vollmacht ohne E-Mail, Wiederaufnahme "i. A.",
"als gegenstandslos abschließen" für Büro und Monteurin, Kundenwechsel abgelehnt, dunkel 412 px) und
`klicktest_bedenkenanzeige.py` (1.8.43, Monteurin startet und meldet, Hinweis "Offene Bedenken" in `/mobil` und auf dem
Auftrag, Büro füllt Anzeige und Entscheidung, Hinweis weg, hell/dunkel, 412 px) und `klicktest_bedenkenanzeige_versand.py`
(1.8.44, Karte mit dem Brief "Bedenkenanzeige", Bestätigung bei abweichendem Kunden, Versand an einen SMTP-Empfänger im Skript,
Aufgaben "versenden" und "Antwort prüfen", Versandprotokoll, 412 px) und `klicktest_beleg_und_hinweis.py` (1.8.45, Hinweis
"Offene Bedenken" auf Einsatzbericht- und Checklisten-Seite des Auftrags für Monteurin und Büro mit Link nur, wo sie öffnen
darf, "Antwort als Beleg": SVG abgelehnt, PDF als Kachel, Foto als Vorschau, nach der Unterschrift gesperrt, Editor) und
`klicktest_abnahme.py` (1.8.46, Gewährleistung: Vorschlag übernehmen, Abweichung nur mit Begründung; Abnahme-Dialog ohne
Vorauswahl, Dachflächen nur des Objekts, Vollmacht-Warnung, SVG abgelehnt, Beleg, Abgleich gesperrt, Verwerfen mit
Begründung; Objekt und Dachfläche mit Gewährleistung und Garantie Dritter; 412 px dunkel; Monteurin 403; seit 1.8.47
Vorschau der verschobenen Enden mit Pflicht-Begründung, Vollmacht zur Abnahme in Dialog und Projektmappe, Nachweisregel; seit
1.8.48 Prüfstatus rot an Objekt, Dachfläche und Auftrag) und `klicktest_maengel.py` (1.8.49, Warnung und "+ Mangel erfassen"
nur an Abnahmen mit Vorbehalt oder Verweigerung, Dialog ohne Vorauswahl, Haltung, Kulanz-Freigabe, beseitigt und abgenommen,
"Nachbesserung regulär bis", Fotos ergänzen, Verlauf, Verwerfen, Aufgabe im Büro-Eingang mit Sprung zum Mangel, 412 px
dunkel, Monteurin 403; seit 1.8.55 neue Frist bei "zurück auf offen") und `klicktest_vertrag_gewaehrleistung.py` (1.8.50, Hinweis und gesperrtes Festschreiben ohne Dauer,
Vorschlag übernehmen, Fassung 1 festschreiben, danach Karte "Gewährleistung" gesperrt und Festlegen 409, 412 px dunkel) und
`klicktest_maengel_monteur.py` (1.8.52, `/mobil` als Monteurin: nur der freigegebene Mangel ohne Haltung und Belege, Foto über
den Monteur-Weg, verborgene Mängel 404, "Beseitigt melden" ohne Foto abgelehnt, mit Foto gemeldet, dieselbe Kennung noch einmal
dieselbe Antwort, Büro sieht "gemeldet in der Monteursansicht", Freigabe zurückgenommen -> verschwunden, 412 px dunkel und hell;
seit 1.8.51 prüft `klicktest_maengel.py` auch "Belege ergänzen") und `klicktest_unterzeichner.py` (1.8.57, Monteurin auf
412 px: Auftraggeber und Konto ohne Namensfeld, Beteiligte als Auswahl mit Hinweis ohne Vollmacht, vier Unterschriften im
Siegelformat 3; Büro dunkel mit Link auf die eingefrorene Vollmacht; Editor "Unterzeichner") und
`klicktest_zeichenflaeche.py` (1.8.58, Tablet mit Touch-Emulation über `Input.dispatchTouchEvent`, Drehen über
`Emulation.setDeviceMetricsOverride` mit `screenOrientation`: Fläche neu vermessen, Strich unter dem Finger, Einsatzbericht) und
`klicktest_protokoll_maengel.py` (1.8.60, Feld "Mängel" im Protokoll: erfassen mit Foto und Beleg, vor der Unterschrift
verworfen "nicht im Protokoll", Auftragsseite "noch ohne Abnahme", nach der Unterschrift kein Formular und 409, danach verworfen
"bleibt im Protokoll", Monteurin 403; das Feld bis 1.8.61 direkt in der Wegwerf-Datenbank gesetzt) und
`klicktest_abnahmeprotokoll.py` (1.8.61, Startvorlage über ihre Migration: Abschnitte, nichts vorausgewählt, Dachflächen ohne
archivierte, Mangel, "Wer unterschreibt?" mit Vollmacht-Angabe und Warnung, Mangel ohne Vorbehalt abgelehnt, Auftraggeber mit
Person und Auftragnehmer-Konto unterschrieben, Editor "vom Zweck vorgegeben", Monteurin ohne Abnahme in Start-Auswahl und
`/mobil`, Protokoll 403) und `klicktest_abnahme_aus_protokoll.py` (1.8.63, Unterschrift des Auftraggebers -> Abnahme am Auftrag
mit Nachweis Protokoll und Person, ausstehende Abnahmen mit Grund und "Abnahme jetzt anlegen", Verwerfen der Unterschrift 409;
die Protokolle ohne Folge legt `befuellen()` mit abgeschalteter Folge an; seit 1.8.64 Karte "Erklärungen und Mängel" und das PDF
des abgeschlossenen Protokolls, dessen Seiten als PNG im Ordner der Screenshots landen) und `klicktest_feste_fassung.py` (1.8.66,
Karte "Feste Fassungen" mit überholter Fassung, PDF und Prüfen, 412 px, Monteurin ohne Karte und 403; seit 1.8.68 Unterschrift,
deren PDF scheitert: Meldung "nichts gespeichert", Zeichnung bleibt, zweiter Versuch speichert) und
`klicktest_protokoll_versand.py` (1.8.67, Karte "Protokoll an den Auftraggeber", Versand an einen SMTP-Empfänger im Skript mit
Anhang = Fassung, nach verworfener Unterschrift Fassung 1, Abnahme mit "Fassung 1 (PDF)", 412 px; seit 1.8.68 CC fest aus der
Fassung, Hinweis und Rückfrage bei geänderten Beteiligten; seit 1.8.69 Adresse von heute, Hinweis mit alter und neuer, "Laut „Kopie
an:“ ohne Mail" im Versandverlauf; ebenso seit 1.8.69 `klicktest_behinderungsanzeige_versand.py`: CC fest statt Eingabefeld) und
`klicktest_objekt_anderer_kunde.py` (1.8.70, Schnellauftrag, Vertragsanlage und Vertragsseite am Objekt eines anderen Kunden: nur
mit Häkchen, API ohne Bestätigung 409, gespeichertes Objekt "bestätigt", neu gewählt wieder Rückfrage; /mobil: Historie nur am
Objekt des eigenen Auftrags, sonst ruhiger Hinweis, 412 px) und `klicktest_abgleich_sperre.py` (1.8.71, Auftragsseite und
Angebots-Editor nennen den Grund der Sperre statt des Knopfs, API 409, freier Auftrag gleicht ab und behält den Projektstatus;
Einsatzbericht mit Hinweis fürs Büro, Monteurin auf 412 px ohne) und `klicktest_rechnungen_sperren.py` (1.8.72, Auftragsseite
"Neue Rechnung" mit Grund statt Knopf je Rechnungsart, Rechnungsseite ohne Finalisieren bzw. Stornieren mit Grund, hell und dunkel,
Mahnwesen-Entwurf zu bezahlter Rechnung, API 409; seit 1.8.73 der Ausweg im Sperrtext: "R4" bzw. "Entwurf löschen", gelöscht ->
frei) und `klicktest_leistungszeitraum.py` (1.8.74, Rechnungsseite: Vorschlag mit Quelle, Grund statt Finalisieren, nichts still
eingetragen, "Übernehmen", Ende vor Beginn, Finalisieren; geplanter Zeitraum; Nummernkreis: Meldung mit der höchsten vergebenen,
nichts gespeichert; seit 1.8.76 Format ohne Jahr mit Jahreswechsel abgelehnt) und `klicktest_rechnungsdatum.py` (1.8.75, Entwurf von vor drei Wochen mit "Finalisiert heute", Finalisieren ->
Datum und Fälligkeit ab heute; Versandhinweis bei einer früher finalisierten Rechnung; veraltete Seite nach Finalisieren in anderer
Sitzung -> 409 mit Nummer) und `klicktest_zahlungen.py` (1.8.78, Karte "Zahlungen" und Dialog "Zahlungseingang buchen": Vorschlag
zuerst auf den älteren Abschlag, Skonto bei passendem Betrag, Einbehalt von Hand -> "Einbehalt offen", Überbuchung gesperrt,
Gegenbuchen mit Begründung -> Storno frei; Kundenakte: Rest zuordnen, Zahlung zurücknehmen; Finanzen mit offenem Betrag; API fremder
Kunde 409; 412 px dunkel) und `klicktest_mahnwesen.py` (1.8.79, Mahnwesen: Öffnen legt nichts an, "Zur Mahnung fällig" mit Auswahl ->
Entwürfe für mehrere, Grund statt Knopf in der Frist, Frist in Tagen, Festschreiben heute; überholte Mahnung mit Grund statt E-Mail,
API 409 für E-Mail, Zustellung und Kundenwechsel; Rechnungsseite mit Aufstellung; Einstellungen ohne Automatik; Dashboard mit
Mitarbeiter; 412 px dunkel; seit 1.8.80 Zustellung nachgetragen, Ersatz der nie versendeten Mahnung unter "zur Mahnung fällig") und
`klicktest_nebenforderungen.py` (1.8.80, Schalter: Büro liest, Admin schaltet ein; Rechnungsseite: Verzugsbeginn aus dem Zugang der
1. Mahnung bestätigen, 2. Mahnung mit Gebühr und Pauschale übernehmen und festschreiben, Gebühr gegenbuchen -> Mahnung geht nicht mehr
hinaus; Mahnwesen: Ersatz einer nie versendeten Mahnung, Status hinausgegangen/ersetzt; Projektmappe: Kundenwechsel mit Auftrag nur mit
Begründung; Monteurin 403; 412 px dunkel; seit 1.8.81 nur die Pauschale, sie sperrt die Gebühr) und `klicktest_verzugszinsen.py` (1.8.81,
Einstellungen: Büro liest Basiszinssatz und Rechtstexte, Admin legt das laufende Halbjahr und einen geprüften Rechtstext an, unbekannter
Platzhalter gewarnt; Rechnungsseite: Zinsvorschlag erst nach dem Halbjahr, mit Abschnitt, Pauschale sperrt die Gebühr, Warnungen für
ungeprüfte Rechtstexte, Festschreiben mit Zinsen, Aufstellung Format 3; Zahlungsdialog nach § 367 BGB, gebucht, Storno gesperrt; offene
Nebenforderung sperrt das Storno; Mahnwesen: Ersatz nennt die gegengebuchte Gebühr in Zeile und Rückfrage; Monteurin 403; 412 px dunkel)
und `klicktest_auftrag_sperren.py` (1.8.82, Auftragsseite: abgerechnete Position mit gesperrtem Preis und Einheit, Grund als Hinweis,
im Dialog und am Steuerschlüssel, Menge speicherbar, API 409; nach der Schlussrechnung Hinweis über dem LV, jede Eingabe gesperrt;
Rechnungs-PDF aus der Ablage, Entwurf neu erzeugt; hell, dunkel, 412 px) und `klicktest_nachtrag.py` (1.8.83, Auftragsseite:
"+ Nachtrag" mit Dialog, N1 unter "Nachträge" hinter dem Titel, Summe, entfernen; mit Rechnungsentwurf Grund statt Entfernen;
Rechnungsseite: Schlussrechnung ohne "+ Position" mit Hinweis und N1, Aufwand mit Knopf, negativer Abschlag mit Grund statt
Finalisieren; hell, dunkel, 412 px) und `klicktest_endrechnung.py` (1.8.85, Rechnungsseite: Karte "Endrechnung" mit Gesamtleistung
samt Aufwand, Abzugsblock und Rechnungsbetrag, Steuerschlüssel und Preis aus dem Auftrag gesperrt, finalisieren, PDF aus der Ablage;
Abweichung vom Auftrag mit Grund und "Aus dem Auftrag aktualisieren"; Grund für Aufwand auf der Auftragsseite; hell, dunkel, 412 px;
seit 1.8.86 Zahlungshinweis mit Einbehalt und Zahlbetrag, Häkchen "abschließend" am Auftrag nach Aufwand; seit 1.8.88 Mengenvergleich
im Entwurf mit Markierung) und `klicktest_mahnen_endrechnung.py` (1.8.89, Mahnwesen ohne die abgezogenen Abschläge, Schlussrechnung
über den Zahlbetrag samt Abschlägen, Entwurf zum Abschlag überholt, Hinweis am Abschlag mit fälligem Einbehalt, Aufstellung je Rechnung
mit Nummer, neuer Zahlbetrag nach Zahlung auf den Abschlag, 412 px dunkel, Monteurin 403) und `klicktest_ueberzahlung.py` (1.8.90,
Schlussrechnung −119 € mit Erstattungsbetrag und Satz statt Skonto, finalisieren, Guthaben, Erstattung buchen, zu viel 409, Kundenakte
mit Guthaben und Zahlungsausgang, zurücknehmen, 412 px dunkel, Monteurin 403) und
`klicktest_browser_datum.py` (1.8.87, Instanz und Browser-Uhr um 00:30 Uhr, Browser in UTC und New York: Monteur-Zeiterfassung mit der
Buchung von heute, Stundenzettel, Büro-Zeiterfassung, Aufgaben überfällig, Plantafel, Kalender) und `klicktest_zahlungen_kleinkram.py`
(1.8.94, Finanzen „Bezahlt (gesamt)“ abzüglich Erstattungen, Kundenakte mit Grund statt „Zahlung zurücknehmen“ und gruppiertem „Rest
zuordnen“, Zahlungsdialog gruppiert und umverteilt gebucht, Zahlbetrag 0 € mit Satz und ohne Schlusstext, 412 px dunkel, Monteurin 403) und `klicktest_abschliessen.py` (1.8.96, Einsatzbericht: Prüfpunkt zurückhalten, dann unterschreiben -- Unterschrift erst nach dem Prüfpunkt; Prüfpunkt scheitert -- Unterschrift nicht ausgeführt; Zeitlimit 2 s über `window.__dkZeitlimit` -- Meldung, Hinweis oben, Unterschrift abgelehnt) und `klicktest_anmelden.py` (1.8.97, Formular mit falschem und richtigem Passwort, Doppelklick nicht parallel, Admin bis zum zweiten Faktor, Abmelden über beide Kopfzeilen -- die Seite wartet die Abmeldung ab --, Seitenleiste nachgestellt; seit 1.8.98 als Prüfungen: Angriffe auf `next`, der alte Cookie-Wert nach dem Abmelden 401, „Zurück“ ohne Daten) und `klicktest_dateien_nie_aktiv.py` (1.8.101, SVG und HTML aus Kundenakte, Projektmappe, Objekt und /mobil laufen nicht -- jede view-Adresse direkt geöffnet ein Download, kein Eintrag im localStorage --, Foto und PDF erscheinen, SVG-Logo in der Seitenleiste sichtbar; Downloads des Tabs über `tab.downloads`, gesammelt aus `Page.downloadWillBegin`) und `klicktest_daten_im_html.py` (1.8.102, Namen mit `"><img onerror>`, `');…//` und `&quot;` in Kundenakte, Projektmappe, Einsatzbericht, "Neues Projekt"/"Neues Angebot", Kalender, Betriebsmittel: kein Skript, Namen als Text, umgebaute Knöpfe tun es weiter mit genau dem Wert, Modul-Schalter über `data-aenderung`) und `klicktest_anmeldung_abgelaufen.py` (1.8.103, Kundenakte: Admin beendet die Sitzungen von außen, Speichern -> „Anmeldung abgelaufen“ am Bereich und oben, Eingaben stehen; im zweiten Tab angemeldet -- `tab.zweiter_tab()` --, derselbe Klick speichert, Hinweis weg) und `klicktest_fremde_seite.py` (1.8.104, zweiter Server auf 127.0.0.1 als Seite derselben Site: Rahmen nicht angezeigt, Upload/Abmelden/Anmelden von dort 403, die eigene Seite speichert weiter) und `klicktest_zahleneingaben.py` (1.8.109, getippt über `Input.insertText`: Nachtrag mit „1.250“ und „1.250,5“ gespeichert als 1250 und 1250,5, „1.25“ mit Meldung abgelehnt und markiert; Zahlungsbedingung ohne Tage abgelehnt, 422 lesbar; „Festschreiben“ im Mahnwesen; Plantafel und „Team entfernen“ mit lesbarer Meldung) und `klicktest_neue_ordnung.py` (1.8.112, je Rolle: Seitenleiste in Gruppen ohne 403/404, Menü der Einstellungen, jeder Menüpunkt öffnet seinen Bereich, Speichern in den umgezogenen Bereichen, frühere Adressen in Einstellungen und Backoffice, 412 px) und `klicktest_versand_im_kontext.py` (1.8.113, Reiter und Karte „Versand“ mit genau ihren Einträgen, gefiltertes Versandprotokoll, Link der Mahnung, Leistungsformular für Büro – Auftrag, „Mein Konto“ auf 412 px) und `klicktest_backoffice_buero.py` (1.8.117, Backoffice als Büro – Auftrag mit Mitarbeiterin: eigene Buchung ändern, fremde und abgeschlossene „nur Admin“, eigene Anträge ohne Entscheiden, Exporte, Abschluss nur vorrücken, 412 px; als Büro – Finanzen ohne Mitarbeiter: keine Anfrage an Anträge und Buchungskontext; seit 1.9.98 entfernt, die Prüfungen stehen in `klicktest_zeiten.py`) und `klicktest_outlook_hinweis.py` (1.8.118, Outlook-Hinweis ohne Zugangsdaten sichtbar, nach dem Speichern der Zugangsdaten ohne Neuladen und nach echtem Neuladen weg, hell und dunkel) und `klicktest_ds_schriften.py` (1.8.127, Anmeldeseite ohne Anmeldung: ds.css eingebunden, Tokens hell und dunkel, Akzentfarbe und Schrift der Seite unverändert, `document.fonts.load` lädt Archivo, IBM Plex Sans und IBM Plex Mono in allen acht Schnitten je latin und latin-ext, 16 woff2 mit 200, Kopfzeilen mit langem Cache) und `klicktest_rahmen.py` (1.8.163, Testdaten der Bildgrundlage: Seitenleiste je Rolle ohne
Bildlauf und mit aktivem Bereich, Menüknopf, Kopfzeile 64 px mit Suche 480 px und Name, Kontomenü per Tastatur mit aria, button-Regeln der
Seiten greifen nicht in den Kopf; seit 1.8.164 der Monteurskopf auf neun Seiten der Monteurin bei 1280 × 620 und 800 × 1100: 64 px,
einzeilig, Name, Reiter, Lupe; `--nur TEIL` für Gegenproben) und `klicktest_einsatzbericht_zeiten.py` (1.9.42: Zeiten am Berichtstag auf Seite und im PDF, gespeichert mit der Unterschrift, PDFs vor und
nach einer nachträglichen Buchung im Ordner der Screenshots) und `klicktest_monteurin_regeln.py` (1.9.35, Stufe 4 R1: offene Zeit in
`/mobil`, Start mit offener Zeit abgelehnt, „Ende nachtragen“ mit Meldungen und Ergebnis, Admin schließt eine fremde Zeit, Verlauf) und
`klicktest_echter_tag.py` (1.9.53, stehende Uhr 16:15: Baustelle 07:00–12:00, Wechsel, Werkstatt bis 16:15 -- Ergebnis mit „Tag zusammen“;
ohne frühere Buchung keins) und `klicktest_kundenakte.py` (1.9.137: jeder Reiter, „⋮“, Dialoge, Zuordnen über den Vorschlag, Stammdaten, Büro – Auftrag, Kunde ohne Projekt,
412 px; nimmt die Bilder neben die Vorlagen auf). In der Mobil-Emulation wächst `innerWidth` mit dem Inhalt: „ohne waagrechtes Scrollen“ gegen die Gerätebreite messen
(`scrollWidth<=412`), nicht gegen `innerWidth` (Fund 1.9.137); seit 1.9.138 über `await tab.ueberlauf()` (leer = passt, nennt die Seite und jedes hinausragende Element; was im eigenen Rahmen rollt, steht als „rollt im Rahmen“ im Protokoll; `tests/test_v558_klicktest_breite.py`). Kopfzeilen einer Antwort aus urllib klein geschrieben vergleichen (der Server schickt sie klein). **Zeichnen**
(seit 1.9.64) nur über `Tab.strich(fläche)`: wartet auf Ruhe und eine ruhige Lage der Fläche (`ruhig_im_bild()`) statt einer festen Pause und
prüft danach die Tinte; Wächter `tests/test_v490_zeichnen_ruhig.py`. **Netzwerkprotokoll** (seit 1.8.97): jeder Tab zeichnet die Network-Ereignisse auf (`tab.netz`); beim Scheitern (Abweichung in `pruefe()`, Seite nicht bereit, Warte-Helfer abgebrochen, `warten()` abgelaufen, Ende eines nicht erfolgreichen Laufs) druckt das Werkzeug die offenen Anfragen mit Adresse, Startzeit und "gesendet ja/nein"; eine gewollte Pause `warten("false", 1.0, melden=False)`; `tab.im_netz_anhalten()` hält eine Anfrage an, bevor sie gesendet wird. Ein Dialog des Browsers (vor allem „Seite verlassen?“ bei einer Navigation während eines Speicherns) hielt bis 1.8.97 jeden weiteren CDP-Befehl an; seit 1.8.98 meldet das Werkzeug ihn (Lauf nicht wie erwartet, samt Netzprotokoll) und nimmt ihn an. **Verbindungsprotokoll und Ausgang** (seit 1.8.115): jede Instanz schreibt die Spur von uvicorn (trace) in `verbindungen.log` ihres Arbeitsordners; das Netzprotokoll nennt unter jeder gemeldeten Anfrage ihren Stand auf dem Server („Server: [41] angekommen …, Antwort-Kopf 200 …“ oder „nicht angekommen“) und trägt den Ausgang einer zuvor als offen gemeldeten Anfrage nach („fertig, Status 200 nach …“, „fehlgeschlagen: net::… nach …“ aus `loadingFailed`), auch am Ende eines erfolgreichen Laufs; Klicktest `klicktest_verbindungsprotokoll.py`.
**Nach einer Aktion, die neu lädt** (seit 1.8.94), nie eine feste Pause oder einen Statustext als Beleg nehmen -- viele Seiten setzen
ihn vor dem Neuladen --, sondern `await tab.warte_auf_neu_geladene_liste("…click()", "#liste")` (wartet, bis keine Anfrage der Seite
mehr unterwegs und die Liste neu gezeichnet ist; ohne Aktion nach `oeffnen()`, bevor geprüft wird, dass etwas NICHT erscheint);
`tests/test_v397_klicktest_helfer.py`. Ruft der Test die async-Funktion der Seite direkt auf, wartet `tab.js()` ihr Ende schon ab.
**Antwort zurückhalten** (seit 1.8.95): `await tab.zurueckhalten(r"/api/…$", "GET")` hält die nächste passende Antwort der Seite zurück
(der Server hat sie bearbeitet), `await tab.freigeben()` gibt sie frei, `art="anfrage"` hält die Anfrage selbst; dazu `warte_bis_gehalten()`,
`warte_auf_ruhe()` (Ruhe außer den zurückgehaltenen). Eine solche Aktion nie über `tab.js()` abwarten (`void f()` statt `f()`), sonst
wartet der Test auf die zurückgehaltene Antwort. Vorlage `scripts/klicktest_veraltete_antworten.py` (Checkliste, Abnahme, Mahnung,
Einstellungen), `tests/test_v398_klicktest_rueckhalt.py`.
Ein
Klicktest, der als
Monteur `/mobil` öffnet,
hält die Uhr fest (`klicktest_main(..., uhr="10:00")`, seit 1.8.36): ab `MobileSettings.shift_end_time` (Vorgabe 19:00)
meldet `/mobil` ab, eine 403-Prüfung sähe abends 401; `--wanduhr HH:MM` täuscht eine andere Uhrzeit vor (Gegenprobe),
`tests/test_v339_feste_uhr.py` prüft, dass jeder solche Klicktest `uhr=` setzt. Den Browser nimmt die feste Uhr nur mit, wenn der Klicktest es
will (seit 1.8.111): `k.uhr_versatz_ms()` in den Seed, `await tab.browser_uhr(seed[…])` vor dem ersten Laden -- so läuft
`klicktest_zeitbuchungen_liste.py` immer bei 00:30 Uhr (in UTC noch gestern). Eine Seite mit `alert()` beim Laden hält den headless Chrome an --
im Klicktest `window.alert` per `Page.addScriptToEvaluateOnNewDocument` umleiten (Vorlage dort). Ein neuer Klicktest kommt als weitere Datei dazu. Kein Ersatz für pytest: gezielte
Prüfungen der Oberfläche, von Hand gestartet, nicht Teil der Suite. **Alle nacheinander** (seit 1.8.76):
`.venv\Scripts\python.exe scripts\klicktest_alle.py` (je Test eigener Arbeitsordner unter einem Ausgabeordner, Übersicht mit
Ergebnis, Prüfungen und Laufzeit, `--nur`/`--ab`, Zeitlimit je Test, beendet nur den eigenen Prozessbaum). Seit 1.8.77 vor
jedem Bericht, Ergebnis im Bericht (Regel 26). **Mehrere zugleich** (seit 1.8.108): `--gleichzeitig 4` -- zuerst die Klicktests mit
`ALLEIN = "<Grund>"` auf Modulebene einzeln, während kein anderer läuft, dann die übrigen zu viert, die längsten zuerst
(`KLICKTEST_DAUERN` in `klicktest_alle.py`). `ALLEIN` braucht jeder Klicktest, dessen Prüfung an einer Zeitspanne hängt: ein Fenster, in
dem etwas NICHT geschehen darf (`warten("false", …, melden=False)` -- unter Last zu kurz, die Prüfung würde still schwächer), ein
Zeitlimit über `window.__dkZeitlimit`, gedrosseltes Netz (`tests/test_v413_testlauf_parallel.py`). Ohne `--gleichzeitig` wie bisher
nacheinander. **Zeitlimit** (seit 1.8.108): `--zeitlimit SEK` an jedem Klicktest; steht der Marker `GEGENPROBE` unter `app/`, bricht
jeder Klicktest nach höchstens 2 min ab (Rückgabecode 3, `klicktest_alle.py` führt ihn als "Zeitlimit"). **Wiederholung** (seit 1.9.19): ist die einzige Abweichung eines roten (oder ins Zeitlimit gelaufenen) Klicktests eine Anfrage, die nie beim Server ankam (`nur_nicht_angekommen()`), läuft er genau einmal neu (`<name>.wiederholt.log`); die Übersicht weist jede Wiederholung aus, der Bericht nennt sie immer (Befund: `docs/archiv/testablauf-und-klicktests.md`). **Ports** (seit 1.8.125):
`_freier_port()` wählt außerhalb der kurzlebigen Ports des Betriebssystems -- im Bereich ab 49152 konnte sich `_warte_auf()` mit sich
selbst verbinden, solange Chrome noch nicht lauschte (`BadStatusLine: GET /json/version`); ein neuer Port-Helfer nimmt `_freier_port()`.
Seit 1.8.126 nimmt jeder Klicktest diesen einen Helfer (auch die SMTP-Empfänger), geprüft vor der Rückgabe auf 127.0.0.1 und 0.0.0.0.
Seit 1.9.85 ist eine Instanz erst bereit, wenn sie sich ausweist (Kennung `ERP_INSTANZ` an `/health`, sonst neuer Port,
`_mit_eigenem_port()`); Chrome wählt seinen Port selbst (`--remote-debugging-port=0`, `DevToolsActivePort`) --
`tests/test_v506_port_wettlauf.py`.
`--ausgabe` von `klicktest_alle.py` nie tief im Scratchpad: die Ablage der Instanz überschreitet sonst die 260 Zeichen von Windows.

### Bildgrundlage für das Redesign (seit 1.8.126)

`scripts/bildgrundlage.py` nimmt jede Seite aus `tests/vorlagen_js.py::seiten()` als ganzseitiges PNG auf (Instanz von `cdp_klicktest`
mit festen Testdaten, stehender Uhr 14.10.2026 10:00 in Server und Browser, alle gespeicherten Zeitstempel darauf gesetzt, feste
Versionsnummer „Bildgrundlage“ und fester Changelog; seit 1.9.20 laufen beim Befüllen auch die Spaltenvorgaben `datetime.utcnow` auf der stehenden Uhr -- kein Testdatum hängt am Lauftag, `tests/test_v453_bildgrundlage_lauftag.py`): Büro – Finanzen überall, die Monteurin zusätzlich auf jeder Seite, die sie öffnet,
Admin für Adressimport und (seit 1.8.134) Benutzer, anonym die Anmeldeseite, die Sperrseite als Monteurin auf `/projects`; je hell und dunkel, je 412 px
und 1440 px, die Seiten der Monteurin seit 1.8.131 auch 800 und 1280 px (TerraPad; seit 1.8.156 Fenster des TerraPad 1201: hoch 800 × 1100, quer 1280 × 620); dazu seit 1.8.131 Zustände des Rahmens als Bild
des Fensters (`ZUSTAENDE`: Menü aufgeklappt und Seitenleiste eingeklappt fürs Büro, Kontomenü offen, Objektsuche offen für die Monteurin, Leiste von
Büro – Auftrag; bis 1.8.161 dazu „Leiste ganz unten“) -- 298 Bilder je Lauf, die bisherigen zuerst. Ordner `bildgrundlage/<commit>/` im Projekt (in `.gitignore`, Endung `-geaendert` bei geänderter Arbeitskopie) mit
`bilder.json`. Vor einem Umbau eine Grundlage vom Stand davor, danach eine neue und vergleichen:

    .venv\Scripts\python.exe scripts\bildgrundlage.py                       (aufnehmen; --ziel ORDNER, --nur TEIL)
    .venv\Scripts\python.exe scripts\bildgrundlage.py vergleichen ALT NEU   (Rückgabecode 1 bei jeder Abweichung)

Der Vergleich nennt je Bild die abweichenden Pixel und legt ein Differenzbild ab (Abweichungen rot); seit 1.8.127 bricht er mit
Rückgabecode 2 ab, wenn die Chrome-Versionen in `bilder.json` verschieden sind (dann die Grundlage auf ihrem Commit neu erzeugen, z. B. in
einem Git-Worktree; die Version nie mit `chrome.exe --version` abfragen -- das öffnet die Sitzung des Nutzers --, sondern aus der
Dateiversion). Verglichen werden volle Läufe
(Text ohne LCD-Kantenglättung, `--nur` nur zum Ausprobieren); ein Flush mit zwei geänderten Objekten in den Testdaten ordnet den Verlauf
zufällig (`app/audit.py`, `session.dirty`), deshalb setzt `befuellen()` den Projektstatus vorab. Eine neue Seite kommt in
`AUFNAHMEN` (`tests/test_v431_bildgrundlage.py` prüft Abdeckung, Vorlage je Rolle und Monteur-Seiten); neue Testdaten ändern alle Bilder
-- dann zuerst eine neue Grundlage vom Stand vor dem Umbau. Grenzen: `docs/archiv/testablauf-und-klicktests.md`, „Bildgrundlage“.

## Arbeitsweise, die sich bewährt hat

- Bei größeren, mehrdeutigen Anfragen ("Vorgänge kopieren" o. Ä.) lieber kurz nachfragen bzw. den
  eigenen Plan vor dem Bauen kurz zur Bestätigung vorlegen, statt in eine falsche Richtung zu
  bauen – besonders wenn die Wahl (z. B. welcher von zwei PDF-Renderern) schwer rückgängig zu
  machen wäre.
- Selbst gefundene Fehler im eigenen Entwurf offen benennen, nicht still korrigieren.
- Veraltete oder irreführende Code-Kommentare beim Anfassen der jeweiligen Stelle korrigieren,
  nicht stehen lassen.
- Nach jeder Änderung: vollständigen Testlauf erwarten/anstoßen, bevor etwas als fertig gilt.
- **Nach dem Anlegen eines neuen Datensatzes per Klick immer direkt zu diesem Datensatz
  navigieren** (`location.href='/…/'+id`), nicht nur eine Statuszeile mit Erfolg anzeigen –
  etabliertes Muster u. a. in `order.html`s `createNewInvoice()`. Wurde bei
  `createProjectNow()` in `maintenance_contracts.html` zunächst vergessen (nur Textmeldung),
  woraufhin Tobias den neuen Vorgang nicht wiederfand (siehe 1.2.7) – bei jeder neuen
  "X erstellen"-Aktion von Anfang an mitdenken, nicht erst nachträglich beheben. **Bewusste
  Ausnahme seit 1.2.20**: `createProjectNow()` in `maintenance_contract.html` navigiert nicht
  mehr sofort, sondern zeigt ein Ergebnis-Panel mit Link – ausdrücklich vom Nutzer gefordert,
  weil der eigentliche nächste Schritt (Einsatzbericht) zwei Ebenen vom neuen Vorgang entfernt
  liegt und ein stiller Sprung nicht zeigt, wie es weitergeht. Gilt nur für diesen einen Fall,
  keine neue Standardregel – die Sofort-Navigieren-Regel bleibt für alle anderen "X erstellen"-
  Aktionen unverändert in Kraft.
- **Bei mehreren aufeinanderfolgenden Versionen innerhalb derselben Sitzung: jeweils committen,
  bevor die nächste beginnt** -- nicht mehrere Versionsstände ansammeln und erst am Ende in
  einem einzigen Commit zusammenfassen. Bei 1.3.39–1.3.41 (Sidebar-Logo: CSS-Fehler behoben,
  Anzeige-Rendition, Backup-Skript-Fix) ist genau das passiert, weil ein echter Vorfall
  (gelöschter Fremd-Ordner unter `Backup\`, siehe Regel 9) mittendrin die Aufmerksamkeit band --
  nachvollziehbar in diesem einen Fall, aber nicht der Normalfall. Ein Commit pro Version hält
  die Stände einzeln durchsuchbar/rücksetzbar; ein nachträglich zusammengefasster Commit über
  mehrere Versionen (wie bei 1.3.39–1.3.41 nötig, weil keine sauberen Zwischenstände mehr
  vorlagen) ist ein Notbehelf, kein Vorbild für den Regelfall.

## Bekannte, bewusst offene Punkte

- ~~Befund 1.8.100 Sicherheit der Seiten~~ -- seit 1.8.104 alle zwölf Lücken geschlossen (Regeln 31–33), `tests/test_v405_befund_seiten.py`
  ohne xfail. HSTS setzt seit 1.8.107 die Anwendung; offen bleibt, ob Nginx den Host weitergibt (für Tablets ohne `Sec-Fetch-Site`) und
  ob es HSTS zusätzlich setzt -- Betreiberprüfung, `docs/archiv/befund-vor-echtbetrieb.md`, "Umsetzung 1.8.104" und "Umsetzung 1.8.107".
- **260 on…-Attribute mit Zahlen und IDs** (seit 1.9.137) stehen in `AUSNAHMEN_HANDLER` (`tests/test_v407_daten_im_html.py`, Regel 32): kein Text mehr,
  aber dasselbe Muster -- Abbau auf data-Attribute bei Gelegenheit, die Liste darf nur kürzer werden.
- **`client_uuid` am Einsatzbericht ist nicht idempotent -- Pflicht vor Checklisten-Stufe 3
  (offline)** (gefunden beim Checklisten-Befund, 29.09.2026): `InspectionItem`/`Finding`/
  `ServiceReportPhoto`/`ServiceReportMaterial`/`ServiceReportAsset` tragen nur den
  Unique-Constraint `(service_report_id, client_uuid)`; eine wiederholte Anfrage mit derselben
  `client_uuid` endet als unbehandelte `IntegrityError` (500) statt 200 mit dem vorhandenen
  Datensatz. `tests/test_v213_inspection_items.py`/`test_v223_service_report_materials.py`
  erwarten die `IntegrityError` derzeit ausdrücklich. Vorbild für die Behebung: das
  Idempotenzmuster des Checklisten-Moduls, siehe `docs/archiv/modul-checklisten.md`.
- **Benutzer löschen scheitert unter PostgreSQL mit 500, sobald der Benutzer per FK referenziert
  ist** (gefunden 1.8.13, gegen PostgreSQL nachgestellt): 15 FKs auf `app_users` ohne `ON DELETE`,
  z. B. `checklists.created_by_user_id`; SQLite erzwingt FKs hier nicht, deshalb lokal unsichtbar.
  Nicht behoben (Deaktivieren statt Löschen oder FK-Regel wäre zu entscheiden). Details:
  `docs/archiv/modul-checklisten.md`, "Umsetzung 1.8.13" -> "Nebenbefunde".
- ~~Vier `ensure_default_*()` ohne UNIQUE (stille Dopplung) und das "get_or_create_settings(id=1)"-Singleton-
  Muster~~ -- seit 1.8.42 gelöst: Grunddaten legt der Start an, serialisiert über eine Sperrzeile (Regel 23,
  `docs/archiv/grunddaten-beim-start.md`), ohne neue Constraints.
- ~~Ein GET-Endpunkt schreibt noch~~ -- seit 1.8.84 gelöst: kein Lesepfad legt mehr an (Angebotskopf, Mitarbeiterprofile,
  Kalkulation, Arbeitsvorbereitung, Lohnstammdaten), der Strukturtest hat keine Ausnahmeliste mehr
  (`docs/archiv/grunddaten-beim-start.md`, "Umsetzung 1.8.84").
- ~~Kolonnenführer-Rolle für Gruppenbuchungen~~ -- seit 1.7.12 gelöst über das Kennzeichen
  `TeamEmployee.is_crew_leader` (keine eigene Rolle), siehe `docs/archiv/rechtekonzept.md`,
  "Zeiterfassung für Monteure" -> "Nachtrag (seit 1.7.12)".
- **59 Update-Handler stehen noch in `BEKANNT`** (seit 1.9.145 die Arbeitsvorbereitung, seit 1.9.136 die Stammdaten des Kunden; die sechs mit Datenverlust seit 1.8.25 behoben, die drei der
  Arbeitsvorbereitung seit 1.8.29, der Auftragskopf seit 1.8.32, die Dachfläche seit 1.8.46, acht mit gemerkten Werten seit 1.8.96, der
  Einsatzbericht seit 1.9.66, Regel 22;
  darunter die acht, die keine Verstöße sind): jede Oberfläche schickt dort heute alle Felder, kein akuter Datenverlust.
  Eingefroren in `BEKANNT` (`tests/test_v329_update_handler_struktur.py`), Abbau bei Gelegenheit; dazu
  Speichern-Aufrufe, die nicht bearbeitete oder gemerkte Werte schicken: `docs/archiv/teil-updates.md`,
  "Nebenbefunde der Durchsicht".
- **Bewusst keine Erkennungsspalte für manuell bearbeiteten Mahntext -- nur ein Hinweis beim
  Speichern** (seit 1.3.21, siehe Abschnitt "Mahnwesen: Löschen/Versenden/Bearbeiten" oben für die
  volle Untersuchung/Begründung). `update_reminder_draft()` erlaubt das unabhängige Ändern von
  `text`/`fee_amount`/`new_due_date` an einem Mahnungsentwurf. Solange `text` seine Platzhalter
  (`{mahngebuehr}`/`{neue_frist}`) behält, zieht eine Zahlenänderung automatisch nach (der
  Fließtext wird bei jedem Lesezugriff neu zusammengesetzt, `format_reminder_text()`) -- das
  ursprünglich befürchtete Auseinanderlaufen tritt in dieser Form nicht ein. Ersetzt jemand einen
  Platzhalter dagegen manuell durch eine fest eingetippte Zahl, zieht eine spätere Zahlenänderung
  diesen einen Wert NICHT mehr nach -- eine echte Erkennung "wurde manuell bearbeitet" wurde
  bewusst NICHT gebaut (bräuchte eine neue, dauerhaft mitgeführte Spalte für ein Restrisiko, das
  nur diesen einen Sonderfall betrifft), stattdessen zeigt das Bearbeiten-Panel jetzt (1) einen
  nicht-blockierenden Hinweis beim Speichern, wenn der zum geänderten Feld gehörende Platzhalter
  im Text fehlt, und (2) die verfügbaren Platzhalter mit ihrer Bedeutung, damit seltener von Hand
  durch eine Zahl ersetzt wird, was ein Platzhalter bereits leisten würde
  (`reminderMissingPlaceholderWarning()` in `mahnwesen.html`/`invoice_detail.html`). Der
  Sonderfall selbst (ein Platzhalter wird trotz Hinweis absichtlich ersetzt und driftet danach
  unbemerkt auseinander) bleibt ein bewusst akzeptiertes Restrisiko, kein Fehler.
- **Langtext ganz ohne eingebettete Zeilenumbrüche bleibt eine unteilbare Zeile** (seit 1.3.15,
  CLAUDE.md "Gemeinsamer Dokumenttyp"/Angebot -- Zeilenumbruch-Variante für lange Positionstexte):
  die große-Leerräume-Behebung splittet den Langtext einer Position an jedem eingebetteten `\n`
  in eine eigene Tabellenzeile, damit reportlab dazwischen umbrechen kann. Ein Langtext ganz ohne
  `\n` (durchgehender Fließtext) bleibt dagegen weiterhin EINE einzige, unteilbare Zeile -- passt
  sie nicht mehr auf die restliche Seite, wandert sie komplett auf die nächste, mit demselben
  Leerraum-Effekt wie vor 1.3.15, nur seltener (an A-2026-0016 hatten praktisch alle längeren
  Langtexte mehrere `\n`, siehe dortige Zählung). Eine lückenlose Lösung (echtes Umbrechen mitten
  in einem Absatz) würde die von reportlab bereits umbrochenen Zeilen aus einem gelayouteten
  `Paragraph`-Objekt extrahieren (`Paragraph.wrap()` befüllt `blPara`/`lines`, aber als
  Low-Level-Fragmentliste, kein einfacher String je Zeile) -- bewusst verworfen: die Fragilität
  (reportlab-Versions-/Font-abhängige interne Datenstruktur, kein dokumentiertes öffentliches API
  dafür) steht in keinem Verhältnis zum Gewinn gegenüber der bereits deutlich wirksameren,
  einfachen `\n`-Aufteilung. Bewusst in Kauf genommen, kein Fehler -- falls in einem Jahr jemand
  fragt, warum eine bestimmte Position trotzdem noch am Stück umbricht: das ist der Grund.
- **`entry_to_dict()`s `employee_name` (Zeiterfassung) ist projektweit live, nicht nur im
  Einsatzbericht** (gefunden bei derselben 1.3.12-Prüfung): die "Erfasste Zeiten"-Tabelle im
  Einsatzbericht-PDF zeigt über `TimeEntry.employee` den AKTUELLEN Namen des Mitarbeiters --
  ebenso die neue Monteur-Meta-Zeile (`created_by_employee_name`, seit 1.3.11). Anders als die
  beiden anderen 1.3.12-Funde ist das aber keine für Einsatzberichte spezifische Lücke, sondern
  die etablierte, projektweite `TimeEntry`-Konvention (auch auf Rechnungen, in der Plantafel
  usw. immer live aufgelöst) -- ein Einfrieren nur für Einsatzberichte wäre eine neue Asymmetrie
  gegenüber jeder anderen Stelle, die `TimeEntry`/`Employee` genauso verwendet. Bewusst nicht
  behoben, gemeldet.
- **`Invoice.caseworker_employee_id` existiert, wird aber nirgends gesetzt** (gefunden bei der
  1.3.7-Planung, geprüft per projektweitem Grep): die Spalte ist da (FK auf `employees`), aber
  weder `_snapshot_order_fields()` noch sonst irgendeine Stelle kopiert sie beim Anlegen einer
  Rechnung aus `Order.caseworker_employee_id` -- sie bleibt in der Praxis immer `NULL`. `Order`
  trägt dieselbe Spalte und nutzt sie aktiv (z. B. löst `sign_report()` darüber den Empfänger der
  "Rechnung erstellen"-Aufgabe auf, siehe Abschnitt "Einsatzbericht"). Bei `Invoice` fehlt
  offenbar nur das Durchreichen aus dem Auftrag -- ob das ein vergessenes Feature oder absichtlich
  nie gebraucht wurde, ist nicht bekannt. Deshalb bewusst OHNE "Sachbearbeiter"-Zeile im neuen,
  gemeinsamen Kopfbereich der Rechnung (siehe dort) -- eine leere Zeile wäre schlechter als keine.
  Ein eigener, kleiner Punkt für später (Durchreichen beim Anlegen ergänzen, falls tatsächlich
  gewünscht), kein Teil der 1.3.7-Etappe. Seit 1.8.79 filtert das Dashboard Mahnungen deshalb nach dem Sachbearbeiter des
  Auftrags (`list_invoices_needing_attention()`), nicht nach dieser Spalte.
- Roadmap für zurückgestellte Vorhaben wurde in einer früheren Sitzung als Datei
  `Roadmap_Zurueckgestellte_Vorhaben.md` erstellt und zum Download angeboten – **per Prüfung am
  09.09.2026 nicht im Projektverzeichnis vorhanden** (`Glob` über das ganze Projekt, kein
  Treffer). Falls sie noch irgendwo existiert, liegt sie außerhalb dieses Projektordners.
- **Redundanz zwischen Flachdach- und Gründach-Schichttypen** (seit 1.2.18, `RoofLayerType`,
  Migration `b8adafd0b997`): die 7 Schichten, die ein Gründach mit einem Flachdach gemeinsam
  hat (Traglage, Dampfsperre, Dämmung, Gefälledämmung, Trennlage, Abdichtung,
  Oberflächenschutz), existieren als ZWEI unabhängige Zeilensätze mit eigenen `key`-Werten
  (`flachdach_*` bzw. `gruendach_*`), nicht als eine gemeinsame, mehrfach zugeordnete Zeile –
  `RoofLayerType.roof_type` ist ein einzelnes Feld, kein Mehrfachbezug, und `roof_type IS NULL`
  hätte "gilt für jeden Dachtyp" bedeutet (ein Steildach hätte dann fälschlich auch
  Dampfsperre/Abdichtung angezeigt bekommen). Bewusst in Kauf genommen, aber bewusst NICHT
  automatisch synchron gehalten: wird einer der beiden Sätze in Einstellungen → Dachaufbau
  später umbenannt, die Optionsgruppe gewechselt oder die Dicke-Pflicht umgestellt, weicht die
  jeweils andere Kopie stillschweigend ab, ohne dass das an dieser Stelle auffällt. Nicht
  angegangen, solange es nicht stört. Saubere spätere Lösung, falls doch: eine Mehrfachzuordnung
  (Zwischentabelle `roof_layer_type_roof_types`) statt der einzelnen `roof_type`-Spalte.
- **Toter Datenbestand: alte `roof_component_types`-Optionsgruppe** (seit 1.2.19): mit der
  Hochstufung zu `RoofComponentType` (echte Tabelle) wurde `roof_component_types` aus
  `DEFAULT_OPTION_GROUPS` entfernt. Bereits vorhandene `SettingOptionGroup`/`SettingOption`-
  Zeilen einer laufenden Installation bleiben dabei unangetastet in der DB stehen (nichts liest
  sie mehr) statt gelöscht zu werden. Reine Aufräum-Idee für später, kein Fehler.
- **Seit 1.8.114 weitgehend erledigt**: die Globals öffnen keine Sitzung mehr, sie lesen die Seitendaten, die die Anmeldeschranke in
  ihrer Sitzung mitlädt (`app/seitendaten.py`, Regel 35); nur ohne Schranke (Tests mit `router_test_client`) lädt der erste Global einer
  Anfrage einmal über `SessionLocal()` nach -- dort gilt der Rest dieses Eintrags weiter. Bis 1.8.113:
  **Jinja-Globals `get_theme()`/`is_module_enabled()`/`sidebar_logo_url()`/
  `sidebar_logo_height_px()` (letztere beide seit 1.3.38/1.3.39) umgehen `get_db()`**
  (`app/routers/pages.py`): alle vier öffnen bei jedem Template-Rendern selbst eine
  `SessionLocal()`-Verbindung zur echten Datenbankdatei, statt die per `get_db()` injizierte (und
  in Tests per `app.dependency_overrides` austauschbare) Session zu verwenden – sie sind damit
  nicht auf eine Test-Session umstellbar. Seit 1.2.20 (siehe `tests/test_v218_template_rendering.py`)
  löst das der erste Test aus, der praktisch jede Seite rendert (`_sidebar.html` bindet
  `is_module_enabled()` ein, jede Seite bindet `_sidebar.html` ein) – für einen reinen Lesetest
  unschädlich, aber ein Vorbild, dem ein künftiger, auch SCHREIBENDER Test nicht folgen darf.
  Geprüft, ob sich das mit wenig Aufwand beheben lässt: nein – `is_module_enabled('wartungen')`
  wird als Jinja-Global mit nur einem Argument in sieben Vorlagen aufgerufen; eine echte
  Umstellung müsste entweder jeden dieser Aufrufe um einen `db`/`request`-Parameter erweitern und
  jeden der rund 30 Seiten-Router in `app/routers/pages.py` um `db: Session = Depends(get_db)`
  plus passenden Kontext-Eintrag ergänzen, oder einen neuen contextvar-basierten Mechanismus
  einführen, der sowohl in der echten Middleware als auch in `router_test_client` verdrahtet
  werden müsste – beides kein kleiner Fix mehr, bleibt daher im Merkzettel. **Seit 1.3.42
  unabhängig davon abgesichert**: alle vier fangen jetzt jede Ausnahme ab und fallen auf einen
  sicheren Wert zurück (siehe "Produktivbetrieb" → "Zwei Vorfälle beim Ausliefern von
  1.3.38–1.3.41" oben) – das löst NICHT die hier beschriebene Test-Umstellbarkeit, aber das
  eigentlich gefährlichere Problem (eine echte Ausnahme reißt jede Seite mit sich, einschließlich
  der Anmeldeseite) ist damit unabhängig von dieser offenen Baustelle geschlossen.
- **`onchange`-only-Autosave-Muster (Blur-Abhängigkeit) existiert an weiteren Stellen**: bei der
  Behebung des 1.2.19-Datenverlusts in der Dachaufbau-Schichtenliste (siehe dort) wurde der
  neue, geteilte `_debounce.html`-Helfer bewusst nur dort UND beim Pflicht-Freitextfeld in
  `service_reports.html` angewendet, wo eine Blur-Abhängigkeit tatsächlich gemeldet war bzw.
  eine Unterschrift blockieren konnte. `measured_value`/`quantity`-Prüfpunkte in
  `service_reports.html` und potenziell weitere Autosave-Felder auf anderen Seiten haben
  dieselbe Lücke, sind aber nicht Teil dieser Iteration – der Helfer steht für eine künftige
  Behebung an Ort und Stelle bereits bereit, keine zweite Implementierung nötig.
- **Keine Doppel-Abrechnungs-Sperre bei "Rechnung aus Aufwand"** (seit 1.2.2 bei `TimeEntry`,
  jetzt seit 1.2.23 ebenso bei `ServiceReportMaterial` -- bewusst geprüft und bewusst NICHT
  behoben, siehe Rückfrage in der 1.2.23-Planung): `TimeEntry` trägt kein `invoiced`/
  `invoice_id`-Feld, `create_invoice_from_time_entries()` filtert nur `status="booked"` bzw.
  (Material) `ServiceReport.status="unterschrieben"` -- beides ohne jede Rücksicht darauf, ob
  dieselben Zeilen bereits in einer FRÜHEREN Rechnung aus Aufwand abgerechnet wurden. Ein
  zweiter Rechnungslauf für denselben Auftrag würde alle bereits abgerechneten Zeit-/
  Materialzeilen erneut als Position auf einer neuen Rechnung anlegen (volle Duplizierung, kein
  Fehler, keine Warnung). Material bekommt hier ausdrücklich dieselbe (Nicht-)Behandlung wie
  Zeit, keine neue Asymmetrie zwischen beiden. Saubere spätere Lösung, falls das stört: ein
  `invoiced_at`-Stempel auf beiden Tabellen plus eine Entscheidung, was ein zweiter Lauf tun
  soll (nur seit dem letzten Lauf Neues abrechnen? warnen? ablehnen?) -- eine eigene, bisher nie
  angefragte Funktionserweiterung, kein kleiner Fix.
- **Feierabend-Abmeldung deckt keinen bereits offenen Berichtstab ab** (seit 1.3.0, siehe
  Abschnitt "Monteursansicht"): `MobileSettings.shift_end_time` wird nur an den beiden mobilen
  Einstiegspunkten geprüft (`GET /mobil`-Seitenaufruf, `GET /api/field-view/today` -- seit 1.8.106 meldet er
  nur, `POST /api/field-view/feierabend` beendet die Sitzung), bewusst
  NICHT in den gemeinsamen Formular-Endpunkten (`PUT /api/inspection-items/{id}`,
  `POST /api/service-reports/{id}/sign` usw.) – das würde auch Schreibtisch-Nutzer treffen, die
  spät noch etwas nachtragen. Ein Monteur, der einen Bericht vor der Feierabend-Grenze geöffnet
  hat und danach ohne Neuladen weiterarbeitet, wird dadurch nicht unterbrochen. Deckt genau den
  beschriebenen Fall ab (niemand bucht nachts unter fremdem Namen auf einem unbeaufsichtigt
  eingeloggten Fahrzeug-Tablet), nicht jede denkbare Session-Timeout-Variante. Keine kleine
  Behebung ohne echten Bedarf – ein zeitgesteuerter serverseitiger Zwangs-Logout mitten in der
  Bearbeitung wäre eine neue, bisher nirgends im Projekt vorhandene Art von Eingriff.
Der frühere Eintrag "Randeinstellungen der Einstellungsseite betreffen 'quote' nicht" ist mit
1.3.20 vollständig aufgelöst: "quote" nimmt jetzt am "default"-Rückfall teil, siehe Abschnitt
"Aufräumen nach dem PDF-Umbau" unten.

Der frühere Eintrag "Büro-Suche findet Aufgaben unabhängig von der Zuweisung" ist mit 1.4.4
vollständig aufgelöst: `_search_tasks()` (`app/search.py`) nutzt seither `list_tasks_for_user()`
(`app/tasks.py`) und findet damit dieselbe Menge wie `GET /api/tasks`, siehe Abschnitt
"Büro-Suche" -> "Nachtrag (seit 1.4.4)" unten.
- **`datetime.utcnow()` ist projektweit noch nicht auf
  zeitzonenbewusste Objekte (`datetime.now(datetime.UTC)`) umgestellt** -- erzeugt seit neueren
  Python-Versionen eine `DeprecationWarning` bei jedem Aufruf (in `pytest.ini` gezielt
  ausgeblendet, siehe Regel 15, damit ein knapper Testlauf nicht trotzdem flutet). Besonders im
  Kalender-Sync-Modul (`app/outlook_calendar_sync.py`, `CalendarEvent.updated_at`/
  `outlook_synced_at`, siehe `docs/archiv/modul-kalender-und-outlook-sync.md`) ist die Spalte
  zeitkritisch für die Echo-Erkennung -- eine Umstellung dort müsste die volle
  Naiv-vs-Aware-Vergleichslogik (`_write_sync_bookkeeping()`, das Selbstreferenz-UPDATE gegen
  `onupdate`) neu durchdenken, nicht nur `datetime.utcnow()` durch `datetime.now(UTC)` ersetzen.
  Bewusst NICHT jetzt umgebaut -- eigene, spätere, sorgfältig zu planende Runde, kein Teil der
  CLAUDE.md-Aufräumung.
- ~~Zeitstempel im Browser noch aus UTC gelesen~~ -- seit 1.9.46 erledigt (`berlinZeitpunkt()`, Regel 20; alter/neuer Wert im
  Änderungsprotokoll seit 1.9.123 lesbar in Berlin über `app/verlauf_namen.py`, `docs/archiv/zeiterfassung-und-abwesenheit.md`, "Angezeigte Zeitpunkte in Europe/Berlin"). Bis dahin: ("heute" seit 1.8.87 überall aus Berlin, Server seit 1.8.12, Regel
  20): naive UTC-Zeitstempel ohne `'Z'` an `new Date()` (u. a. E-Mail-Versandzeit bei Rechnung, Auftrag, Angebot) und
  `slice(0,10)` eines Zeitstempels (u. a. Mahnwesen "versendet …"). Liste mit Zeilen:
  `docs/archiv/zeiterfassung-und-abwesenheit.md`, "Kalenderdatum in Europe/Berlin statt UTC".
