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

- Version: **1.8.39** (siehe `CHANGELOG.md` für die vollständige Versionshistorie; diese Zeile stand
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
| Sicherung | `/home/tobias/backup.sh`, täglich 2 Uhr UTC, 14 Tage Aufbewahrung |
| Notfallskripte | `scripts/reset_admin_2fa.py`, `scripts/migrate_sqlite_to_postgres.py` |
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
Probe-Datenbank auf demselben Server, nicht die lokale, portable Instanz aus der Entwicklung) --
`DATABASE_URL=postgresql+psycopg://<user>:<pass>@localhost:5432/spielwiese .venv/bin/alembic
upgrade head`, geprüft, danach erst die Abfolge oben gegen `dachkonzepte`.

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
- **Design-System (seit 1.0.97, auf alle Seiten ausgerollt):** jede Seite mit `{% include
  "_sidebar.html" %}` definiert im eigenen `:root`/`:root[data-theme="dark"]`-Block dieselben
  CSS-Variablen (`--accent` aus `{{ get_theme().accent_color }}`, `--bg`, `--card`, `--ink`,
  `--muted`, `--line`, `--field-border(-hover)`, `--soft`, `--danger(-soft)`, ggf.
  `--warning(-soft)`/`--success(-soft)`, plus die `--sidebar-*`-Token für `_sidebar.html`), dazu ein
  FOUC-Vermeidungs-Script vor dem `<style>`-Block. Eckige Ecken durchgängig (kein
  `border-radius`), keine farbige Kopfleiste – Seitentitel/Aktionen stattdessen in einer normalen
  Karte. `settings.html` als Referenzvorlage für Feldlayout, Buttons, Status-Meldungen.

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
   Redesign, Anpassungen an bestehenden Modulen.

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
    Änderung, nicht mehrere unabhängige Themen gemeinsam (Vorbild: das eigene
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
    bewusst offene Punkte" unten für die geplante, noch nicht umgesetzte Umstellung).

16. **Jede Verifikation -- CDP-Browsertest, Sicherheits-/Angriffstest, Datenumzugs-/
    Reparaturskript -- läuft gegen eine isolierte, temporäre Test- oder Probe-Instanz
    (SQLite/PostgreSQL), NIEMALS gegen die echte, produktive Datenbank (`dachkonzepte_erp.db`
    lokal bzw. `dachkonzepte` auf dem Server).** Gilt unabhängig davon, wie harmlos ein Schreib-
    zugriff erscheint -- ein Migrationsskript öffnet den Bestand bestenfalls "ausschließlich
    lesend" und kopiert in eine neue Zieldatenbank (Muster
    `scripts/migrate_sqlite_to_postgres.py`), ein Browser-/Angriffstest baut sich eine eigene,
    kurzlebige Datenbank auf einem separaten Port auf und räumt sie danach vollständig ab.
    Schema-Änderungen laufen bei Bedarf zusätzlich einmal gegen die Probe-Datenbank
    `spielwiese` (siehe "Produktivbetrieb" → "Der Weg einer Änderung auf den Server"), ebenfalls
    nicht gegen `dachkonzepte`. Diese Regel gilt themenübergreifend -- unabhängig davon, welches
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
    sucht sie per AST. Gespeicherte Zeitstempel aus `datetime.utcnow()` bleiben naive UTC; wer sie
    druckt oder ein Datum daraus ableitet, rechnet mit `to_berlin()` um. Beginn/Ende einer
    Zeitbuchung sind dagegen naive Ortszeit. Browser-Seite: `_berlin_date.html`. Details und die
    offenen Browser-Stellen: `docs/archiv/zeiterfassung-und-abwesenheit.md`, "Kalenderdatum in
    Europe/Berlin statt UTC".

21. **Jede E-Mail geht über `app/email_dispatch.py::dispatch_email()`, seit 1.8.17** -- nie direkt
    über `app/email_sending.py::send_message()`, SMTP oder Graph. Nur so entsteht der
    Protokolleintrag (vor dem Senden, mit Schlüssel gegen Doppelversand) und landet ein PDF in der
    unveränderlichen Ablage. `tests/test_v321_email_dispatch.py` sucht jeden anderen Aufrufer per
    AST. Eine neue Versandstelle von der Oberfläche schickt einen `dispatch_key` je Klick mit
    (`_email_dispatch.html`). Ablage und Protokoll werden nie geändert oder gelöscht (einzige
    Ausnahme seit 1.8.19: ein hängender Eintrag wird einmal mit Notiz geklärt). Rechnung, Storno und
    Mahnung kommen ab dem ersten Versand aus der Ablage (`frozen_or_fresh_pdf()`), nie neu erzeugt; der Vertrag
    liegt seit 1.8.33 schon ab dem Festschreiben dort (Fassung, `app/contract_versions.py`), seit 1.8.34 auch
    Unterschriftsblatt, Unterschriftsbilder und Papier-Scan (`app/contract_signatures.py`), seit 1.8.35 die
    unterschriebene Abschrift (Fassung + Blatt bzw. Scan), die Versand und Zustellung danach hinausgeben.
    Eine Zustellung auf anderem Weg (Einschreiben, Übergabe, Bote, Fax) wird seit 1.8.20 im selben
    Protokoll nachgetragen (`record_manual_delivery()`); eine neue Dokumentart braucht einen Eintrag
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
    Wert bleibt leer -- eine Vorgabe aus den Einstellungen gilt nur beim Anlegen (seit 1.8.31).
    `tests/test_v329_update_handler_struktur.py` prüft jeden
    PUT/PATCH-Handler per AST; die 73 Altfälle stehen dort als Liste, die nur kürzer werden darf.
    Details: `docs/archiv/teil-updates.md`.

## Fachbegriffe & Domänenmodell

- **"Vorgang"** (in normalem Gespräch) = **Projekt** (`Project`) – wurde in der Sitzung explizit
  geklärt, da der Begriff auf mehrere Dinge hätte zeigen können.
- Kette: `Customer` → `Project` → `Quote` (Angebot) → `Order` (Auftrag) → `Invoice` (Rechnung) →
  `Reminder` (Mahnung).
- `Quote`: frei bearbeitbar, Status u. a. `entwurf`/`versendet`/`beauftragt`. Kann `is_template=True`
  sein (Mustervorgang) und/oder `archived=True`.
- `Order`: entsteht ausschließlich durch Beauftragung eines Angebots, ist ein **unveränderlicher
  LV-Snapshot**. Kein Entwurfsstatus – startet direkt bei `beauftragt`.
- `Invoice`: `entwurf` bis zur Finalisierung (vergibt Nummer aus Nummernkreis), danach
  unveränderlich außer über eine Stornorechnung.
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
  (Status `versendet`, Nummernvergabe) unveränderlich wie `Invoice`/`Order` (Regel 5).
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
  Stammsatz (`contact_values()`), Suche/Sortierung brauchen `with_sources()`. Details:
  `docs/archiv/vertragsgrundlage-und-vertrag.md`, "Umsetzung 1.8.37" und "Umsetzung 1.8.39".
- **Behinderungsanzeige** (seit 1.8.38): eine Checkliste mit Zweck `behinderungsanzeige` (Systemfelder in
  `app/checklist_purposes.py`): Meldung (meist Monteur) → Anzeige (nur Büro) → Wegfall, je mit Unterschrift; nach der
  Unterschrift der Meldung die Aufgabe "Behinderungsanzeige versenden" (`app/obstruction_notices.py`). Details:
  `docs/archiv/vertragsgrundlage-und-vertrag.md`, "Umsetzung 1.8.38".
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
  über das Versandprotokoll mit Ablage (Regel 21), mehrere Empfänger und CC, Anhang höchstens 3 MB.
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
  Mitarbeiter-Reintegration, Sidebar-Umgestaltung) -- `docs/archiv/stammdaten-und-sidebar.md`
- **Adressimport & Objekte** (Altsystem-Import, Hauptadressen-Kennzeichnung) --
  `docs/archiv/adressimport-und-objekte.md`
- **Serverbetrieb & Anmeldesicherheit** (Geheimnisse/`ERP_DATA_DIR`, Zwei-Faktor-Pflicht,
  Geräte-Vertrauen, serverseitige Anmeldeschranke für Seiten, PostgreSQL-Migrationsreparatur) --
  `docs/archiv/serverbetrieb-und-anmeldesicherheit.md`
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
  Abschnitt und "nur Büro", Folgen nach einer Unterschrift, Regel-Aufgabe mit Link zum Anlegen) --
  `docs/archiv/modul-checklisten.md`
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
  Verweis ohne Kopie); Brief und Versand folgen) --
  `docs/archiv/vertragsgrundlage-und-vertrag.md`
- **Speichern nur gesendeter Felder** (`PartialUpdate`, Strukturtest über alle PUT-Handler, Liste der
  Altfälle, Nebenbefunde der Durchsicht aller Speichern-Aufrufer) -- `docs/archiv/teil-updates.md`
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
- **Self-Seeding mit SAVEPOINT-Absicherung**: siehe eigener Abschnitt "Self-Seeding gegen
  gleichzeitigen ersten Zugriff absichern" unten -- gilt für jede künftige
  `ensure_default_*()`-Funktion mit UNIQUE-Constraint.
- **Platzhalter in Textvorlagen über `app/placeholders.py::apply_placeholders()`** (seit 1.8.32,
  vorher je Versender eine eigene Schleife): ersetzt in einem Durchgang, ein eingesetzter Wert wird nie
  erneut ersetzt; Mahnung, E-Mail-Vorlagen und Vertragsvorlagen nutzen es. Eine neue Vorlage mit
  Platzhaltern zeigt ihre Liste in der Oberfläche und warnt vor unbekannten (`unknown_placeholders()`).
- **Abgelehnte API-Antworten lesbar über `app/templates/_fehlertext.html`** (seit 1.8.35, `fehlerText(body, status,
  felder)`): `detail` als Text unverändert, als 422-Liste "Bitte die Eingabe prüfen – <Feld> <Art>." mit den
  Feldnamen der Seite, sonst ein Text je Status. Auftragsseite, seit 1.8.37 Projektmappe und Stammdaten (Liste,
  Formular); 33 weitere Vorlagen reichen `detail` noch roh an `Error()` weiter ("[object Object]" bei 422) -- eine
  Seite, die man anfasst, stellt um.
- **Unterschriften zeichnen über `app/templates/_unterschrift.html`** (seit 1.8.34, `unterschriftsfeld(canvas)`
  auf einem `<canvas class="dk-unterschrift">`): Checkliste, Einsatzbericht und Vertrag teilen sich die Fläche
  (weiß mit dunklem Strich in beiden Themes, Geräteauflösung) -- eine neue Unterschrift baut keine eigene
  Zeichenlogik. `tests/test_v337_vertrag_unterschrift.py` prüft, dass die drei Seiten keine eigene haben.
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
  den eigenen Bericht.
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
  Infos" am Mitarbeiter). Ein neuer Endpunkt für
  `field` braucht Testdaten, die ihn mit Inhalt füllen; ein Feld, das der Monteur trotz verbotenem
  Namen sehen soll, eine begründete Ausnahme in `ERLAUBT_JE_ROUTE`.
- **Kein sichtbarer Link auf eine gesperrte Seite** (seit 1.8.24):
  `tests/test_v328_navigation_ohne_sperrseiten.py` rendert je Rolle jede erlaubte Seite und ruft
  jeden beim Laden sichtbaren Link als dieselbe Rolle auf -- kein 403; `BEKANNT_OFFEN` ist seit
  1.8.27 leer. Links, die erst das JavaScript baut (Breadcrumb der Berichtsseite), prüft der
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
doppelte Zeilen anlegen. Das Abfangen einer nie geworfenen `IntegrityError` bewirkt dort nichts --
eine echte Behebung bräuchte zuerst eine Migration, die den fehlenden Constraint ergänzt (bekannte,
noch offene Fälle: `app/document_layout.py`, `app/payment_terms.py`, `app/tax_keys.py`,
`app/reminders.py`, siehe CHANGELOG.md 1.4.6).

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
  schlanke Test-App mit fest angemeldetem Admin-Kontext, ohne die produktive
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
ein Eintrag für zwei Projekte, Formular schreibgeschützt, dunkel, 412 px, Monteur 403). Ein Klicktest, der als Monteur `/mobil` öffnet,
hält die Uhr fest (`klicktest_main(..., uhr="10:00")`, seit 1.8.36): ab `MobileSettings.shift_end_time` (Vorgabe 19:00)
meldet `/mobil` ab, eine 403-Prüfung sähe abends 401; `--wanduhr HH:MM` täuscht eine andere Uhrzeit vor (Gegenprobe),
`tests/test_v339_feste_uhr.py` prüft, dass jeder solche Klicktest `uhr=` setzt. Eine Seite mit `alert()` beim Laden hält den headless Chrome an --
im Klicktest `window.alert` per `Page.addScriptToEvaluateOnNewDocument` umleiten (Vorlage dort). Ein neuer Klicktest kommt als weitere Datei dazu. Kein Ersatz für pytest: gezielte
Prüfungen der Oberfläche, von Hand gestartet, nicht Teil der Suite.

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
- **Vier `ensure_default_*()`-Self-Seeding-Funktionen ohne UNIQUE-Constraint, dadurch weiterhin
  anfällig für stille Dopplung bei gleichzeitigem erstem Zugriff** (gefunden beim 1.4.6-Sweep,
  siehe Abschnitt "Self-Seeding gegen gleichzeitigen ersten Zugriff absichern" oben):
  `app/document_layout.py::ensure_default_layout()`, `app/payment_terms.py::ensure_default_payment_terms()`,
  `app/tax_keys.py::ensure_default_tax_keys()`, `app/reminders.py::ensure_default_reminder_levels()`.
  Andere Fehlerklasse als die acht in 1.4.6 behobenen Fundstellen -- kein Crash (keine
  UNIQUE-Verletzung zum Abfangen vorhanden), sondern im seltenen Kollisionsfall zwei identische
  Standardzeilen. Nicht behoben, da eine echte Behebung zuerst eine neue Migration bräuchte
  (fehlenden Constraint ergänzen) -- ein größerer, separat zu entscheidender Schritt, kein reiner
  Code-Fix wie bei den acht anderen. **Ebenfalls bewusst außerhalb**: das strukturell verwandte,
  aber deutlich umfangreichere "get_or_create_settings(id=1)"-Singleton-Muster (`GeneralSettings`,
  `TaskSettings`, `MaintenanceSettings` u. v. a., über zehn Tabellen) -- dort kollidiert ein
  PRIMARY KEY statt eines Business-Keys, ein eigener, größerer Sweep, nicht Teil der 1.4.6-Anfrage.
- ~~Kolonnenführer-Rolle für Gruppenbuchungen~~ -- seit 1.7.12 gelöst über das Kennzeichen
  `TeamEmployee.is_crew_leader` (keine eigene Rolle), siehe `docs/archiv/rechtekonzept.md`,
  "Zeiterfassung für Monteure" -> "Nachtrag (seit 1.7.12)".
- **65 Update-Handler übernehmen weiterhin nicht gesendete Felder** (die sechs mit Datenverlust seit
  1.8.25 behoben, die drei der Arbeitsvorbereitung seit 1.8.29, der Auftragskopf seit 1.8.32, Regel 22): jede Oberfläche schickt dort heute alle Felder, kein akuter Datenverlust.
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
  gewünscht), kein Teil der 1.3.7-Etappe.
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
- **Jinja-Globals `get_theme()`/`is_module_enabled()`/`sidebar_logo_url()`/
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
  Einstiegspunkten geprüft (`GET /mobil`-Seitenaufruf, `GET /api/field-view/today`), bewusst
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
- **Kalenderdatum im Browser noch an weiteren Stellen aus UTC abgeleitet** (Dashboard seit
  1.8.10 und alle Server-Stellen seit 1.8.12 behoben, Regel 20): `toISOString().slice(0,10)`
  (u. a. `today()` der Büro- und der Monteur-Zeiterfassung, Bezahltdatum Eingangsrechnung) und
  naive UTC-Zeitstempel ohne `'Z'` an `new Date()` (u. a. E-Mail-Versandzeit bei Rechnung, Auftrag,
  Angebot). Liste mit Zeilen: `docs/archiv/zeiterfassung-und-abwesenheit.md`, "Kalenderdatum in
  Europe/Berlin statt UTC". Für den Browser steht `_berlin_date.html` bereit.
