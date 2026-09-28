# Geheimnisse für den Serverbetrieb, Anmeldesicherheit, Geräte-Vertrauen, Anmeldeschranke für Seiten, PostgreSQL-Migrationsreparatur

Ausgelagert aus CLAUDE.md am 2026-09-28 im Zuge der Aufteilung in eine schlanke
CLAUDE.md plus themensortiertes Archiv (siehe CLAUDE.md, Abschnitt "Modulübersicht",
und `docs/archiv/regel-abgleich.md` für die vollständige Zuordnung). Der Inhalt ist
wortgetreu (per Skript, zeilenweise) aus der vorherigen CLAUDE.md übernommen, keine
Umformulierung. Versionsangaben ("seit 1.x.y") beziehen sich auf den Stand zum
jeweiligen Zeitpunkt der ursprünglichen Aufzeichnung.

---

## Geheimnisse für den Serverbetrieb (`app/paths.py`, seit 1.3.33)

Vorbereitung für den geplanten Umzug auf einen echten Server (das Projekt liegt seit derselben
Sitzung erstmals in einem privaten GitHub-Repository, siehe unten). Ziel: kein Geheimnis liegt
als Datei im Projektordner, der aus Git kommt; `ERP_SECRET_KEY` kommt aus der Umgebung;
`ERP_DATA_DIR` zeigt auf einen Ordner außerhalb des Checkouts, damit ein `git pull` nie Fotos,
Unterschriften oder den Verschlüsselungsschlüssel berührt; die Datenbankverbindung kommt aus
`DATABASE_URL`. Lokal soll ohne gesetzte Variablen weiterhin alles mit den bisherigen
Vorgabewerten funktionieren.

**Bestandsaufnahme vor dem Bauen ergab: das meiste war schon da.** `secret_key()`
(`app/auth.py`) liest `ERP_SECRET_KEY` bereits vorrangig -- ist die Variable gesetzt, wird
`data/.erp_secret` gar nicht erst gelesen oder angelegt. Die Datei wird nur als Rückfall beim
allerersten Start automatisch erzeugt (`secrets.token_hex(32)`). `DATABASE_URL`
(`app/database.py`) funktionierte bereits vollständig über die Umgebungsvariable. **Fehlend war
nur eine Vereinheitlichung**: die sieben unabhängigen Upload-Pfade (Firmenlogo,
Briefpapier-Hintergründe, Kunden-/Projektdateien, Dachflächen-Skizzen,
Einsatzbericht-Fotos/-Unterschriften) kannten `ERP_DATA_DIR` bisher nicht -- jeder hätte auf
einem Server einzeln über seine eigene, spezifischere Variable (`DACHKONZEPTE_LOGO_FILE_ROOT`
usw.) umgelenkt werden müssen.

### `app/paths.py::data_dir()` -- eine Stelle statt neun

Neues, kleines Modul mit einer einzigen Funktion, von `app/auth.py`
(Verschlüsselungsschlüssel), `app/logging_config.py` (Protokoll) und allen sieben
Upload-Modulen (`app/company_logo.py`, `app/customer_documents.py`,
`app/document_layout_background.py`, `app/project_documents.py`, `app/roof_area_sketches.py`,
`app/service_reports.py`, `app/service_report_photos.py`) genutzt:

```python
_PROJECT_ROOT = Path(__file__).resolve().parent.parent

def data_dir() -> Path:
    root = Path(os.getenv("ERP_DATA_DIR", str(_PROJECT_ROOT / "data")))
    root.mkdir(parents=True, exist_ok=True)
    return root
```

Jedes der sieben Upload-Module behält seine eigene, spezifischere Variable als Override erster
Priorität (`Path(os.getenv("DACHKONZEPTE_LOGO_FILE_ROOT", data_dir() / "company_logo"))`) --
`ERP_DATA_DIR` bestimmt nur den gemeinsamen Fallback, falls keine der spezifischeren Variablen
gesetzt ist. Lokal ändert sich dadurch nichts: ohne jede Variable ergibt `data_dir()` exakt
denselben Pfad wie vorher (`<Projektordner>/data`).

**Dabei eine echte, kleine Inkonsistenz behoben.** Die beiden schon vorher bestehenden
`ERP_DATA_DIR`-Leser (`_secret_path()` in `app/auth.py`, `configure_logging()` in
`app/logging_config.py`) lösten ihren Fallback relativ zum AKTUELLEN ARBEITSVERZEICHNIS auf
(`Path("data")`), die sieben Upload-Pfade dagegen relativ zur LAGE DER DATEI SELBST
(`Path(__file__).resolve().parent.parent`). Heute folgenlos, weil jeder bekannte Startweg
(`start_windows.bat` wechselt vorher per `cd /d %~dp0` dorthin, `pytest` liest `pytest.ini` aus
dem Projektordner) das Arbeitsverzeichnis ohnehin auf den Projektordner setzt -- aber eine
tickende Falle für einen künftigen Server-Start mit einem anderen Arbeitsverzeichnis
(systemd-Unit, Docker-`WORKDIR`): der Ordner würde dann STILLSCHWEIGEND woanders landen (er
wird ja automatisch neu angelegt), der Schaden zeigt sich erst später als "die Uploads von
vorher sind weg". `data_dir()` verankert den Fallback jetzt einheitlich dateibasiert -- der
Docstring hält diese Begründung ausdrücklich fest, damit ein künftiger Durchgang sie nicht als
Übervorsicht wieder auf einen arbeitsverzeichnis-relativen Fallback "vereinfacht".

### Warnung statt Blockade bei abweichendem Schlüssel

`data/.erp_secret` entschlüsselt die bereits in der Datenbank gespeicherten SMTP-/
Microsoft-365-Zugangsdaten (`password_encrypted`/`graph_client_secret_encrypted`, siehe
`app/crypto.py`/`app/email_sending.py`). Setzt jemand auf dem Server versehentlich einen
anderen `ERP_SECRET_KEY` als den, mit dem eine übernommene Datenbank verschlüsselt wurde, werden
diese Werte unlesbar -- bisher unbemerkt bis zum nächsten Versandversuch
(`decrypt_secret()` wirft dann erst `ValueError`). Neue Funktion
`warn_if_secret_key_mismatches_file()` (`app/auth.py`, beim Start aus `app/main.py` aufgerufen,
direkt nach `configure_logging()`): loggt eine deutliche Warnung, wenn `ERP_SECRET_KEY` gesetzt
UND `data/.erp_secret` vorhanden UND beide unterschiedlich sind -- **kein Abbruch** (ein
abweichender Schlüssel ist bei einer frischen Testinstallation normal) und **gibt den Schlüssel
selbst nie aus, auch nicht gekürzt**. Ist `ERP_SECRET_KEY` gesetzt, aber es existiert keine
`data/.erp_secret` (frische Installation) oder ist die Variable gar nicht gesetzt, bleibt es
stumm.

**Wie der bestehende Schlüssel sauber auf den Server kommt**: der Inhalt der lokalen
`data/.erp_secret` (`Get-Content data\.erp_secret`) muss unverändert als Wert von
`ERP_SECRET_KEY` in der Serverumgebung landen -- über den Secret-Mechanismus der jeweiligen
Plattform, nie als Datei im Repository (bleibt gitignored) und nie unverschlüsselt durch einen
Chat/eine E-Mail geleitet.

### `.env.example`

Um `ERP_DATA_DIR` (jetzt mit vollständiger Erklärung, was alles darüber verlegt wird) und alle
sieben `DACHKONZEPTE_*_FILE_ROOT`-Variablen ergänzt -- auskommentiert, mit dem Hinweis, dass sie
nur gebraucht werden, wenn ein einzelner Ordner abweichend von `ERP_DATA_DIR` woanders liegen
soll. So sind sie beim Einrichten eines Servers sichtbar, ohne gesetzt werden zu müssen.

### Tests

`tests/test_v111_config_hardening.py`: `data_dir()` liefert denselben Pfad unabhängig vom
Arbeitsverzeichnis (der zentrale Fund dieser Etappe) und respektiert `ERP_DATA_DIR`;
`warn_if_secret_key_mismatches_file()` warnt bei Abweichung, bleibt stumm bei Übereinstimmung/
fehlender Datei/fehlender Variable, und gibt in keinem Fall den Schlüsselwert selbst aus (per
`caplog` geprüft). Zusätzlich manuell gegen die echte `data/.erp_secret` verifiziert (mit einem
bewusst falschen Test-Dummywert, nie dem echten Schlüssel).

## Anmeldesicherheit für den Onlinebetrieb (seit 1.3.34)

Der Server wird demnächst frei aus dem Internet erreichbar sein -- die Anmeldeseite wird ab Tag
eins automatisiert durchprobiert. Bestandsaufnahme vor dem Bauen ergab: Passwort-Hashing
(PBKDF2-HMAC-SHA256, 260.000 Iterationen) war bereits solide, das Anmelde-Cookie bereits
`httponly`+`samesite=lax`+`secure` (über `ERP_COOKIE_SECURE`, bereits der richtige
Mechanismus, keine Änderung nötig) -- die drei tatsächlichen Lücken: eine nur im Arbeitsspeicher
lebende, rein benutzernamen-basierte Anmeldesperre, kein zweiter Faktor, und keine
Selbstbedienung fürs eigene Passwort.

### Persistente, doppelte Anmeldesperre (`app/login_security.py`)

Der bisherige In-Memory-Zähler (`app/auth.py`, bis 1.3.33) zählte pro Prozess -- bei zwei
uvicorn-Workern wären aus fünf zulässigen Fehlversuchen zehn geworden, ein Neustart hätte den
Zähler ohnehin geleert. Neue Tabelle `FailedLoginAttempt` (`bucket`, `occurred_at`) -- bewusst
EINE Zeile je Fehlversuch statt eines Zählers je Schlüssel, damit das gleitende Zeitfenster ("die
letzten N Versuche innerhalb von X Sekunden") exakt wie vorher nachbildbar bleibt. Zwei
unabhängige Sperren GEMEINSAM geprüft (`login_lockout_seconds()`): je Benutzername
(`MAX_ATTEMPTS_PER_USER=5`, 15 Minuten) UND je IP-Adresse (`MAX_ATTEMPTS_PER_IP=20`, 15 Minuten,
höhere Schwelle, damit ein Büro mit mehreren Mitarbeitern hinter derselben Adresse sich nicht
durch normale Tippfehler gegenseitig aussperrt) -- eine reine Benutzernamen-Sperre ließe sich
durch rotierende Benutzernamen umgehen, eine reine IP-Sperre träfe bei wechselnden Adressen nie.
Dasselbe Muster (eigener Bucket-Präfix `twofa_user:`) sichert auch das Erraten von TOTP-/
Wiederherstellungscodes beim Login ab (`two_factor_lockout_seconds()`).

**Aufräumen ohne separaten Job**: `register_failed_attempt()` löscht bei JEDEM neuen Fehlversuch
gleich alle Zeilen, die älter als das größte verwendete Zeitfenster sind (`_RETENTION_SECONDS`)
-- kein Scheduler nötig (passt zum durchgängigen "kein echter Scheduler"-Prinzip dieses
Projekts), die Tabelle bleibt dadurch ungefähr auf die Fehlversuche der letzten Zeitfenster
begrenzt, egal wie viele insgesamt je passiert sind. Erfolg löscht nur die eigene
Benutzernamen-Sperre (`clear_failed_login()`), bewusst NICHT die IP-Sperre -- gelingt zufällig
ein Login von einer Adresse, mit der zuvor viele andere Benutzernamen durchprobiert wurden, soll
das die IP-Sperre nicht aufheben. Die Fehlermeldung ("Benutzername oder Passwort ist falsch")
war bereits vorher für unbekannten Benutzernamen und falsches Passwort identisch -- unverändert,
verrät also weiterhin nicht, ob ein Konto existiert (per Test abgesichert).

**Bewusst NICHT in dieser Version**: Auswertung von `X-Forwarded-For` hinter einem
Reverse-Proxy -- `request.client.host` ist der unmittelbare TCP-Peer. Läuft der Server später
hinter einem Reverse-Proxy, sähen alle Anfragen dieselbe (Proxy-)Adresse, die IP-Sperre würde
dann faktisch alle Nutzer gemeinsam treffen. Bekannter, bewusst offener Punkt für den Moment, in
dem ein Reverse-Proxy tatsächlich eingerichtet wird -- dann braucht es eine per Umgebungsvariable
gesteuerte "vertraue dem Proxy-Header"-Option, nicht blind vertrauen (sonst ließe sich die
Absender-IP durch den Header selbst fälschen).

### Zwei-Faktor-Authentifizierung (TOTP) für Administratoren (`app/two_factor.py`)

Nur für Administratoren -- Monteure melden sich täglich auf dem Fahrzeug-Tablet an, ein zweiter
Faktor bei jeder Anmeldung wäre dort täglicher Aufwand, und ihre Konten haben deutlich weniger
Rechte. Administratoren dagegen kommen an alle Kunden-, Mitarbeiter- und Finanzdaten.
**Verpflichtend**, nicht freiwillig -- freiwilliger zweiter Faktor wird in der Praxis fast nie
aktiviert, genau in dem Moment nicht, in dem es zählt. Bewusst KEINE "Später erinnern"-Option.

**Abhängigkeiten, tatsächlich geprüft** (Metadaten/LICENSE-Dateien der herunterladbaren Pakete
gelesen, nicht aus dem Gedächtnis, Muster wie bei `pypdfium2`): `pyotp` 2.10.0 (**MIT**, keine
eigenen Abhängigkeiten) und `qrcode[pil]` 8.2 (**BSD-3-Clause** -- ein zusätzlicher, irreführender
"Other/Proprietary"-Classifier bezieht sich nur auf eine Namensnennung für portierten JS-Code,
keine zusätzlichen Einschränkungen; zieht `pillow` als Extra, bereits Pflichtabhängigkeit über
ReportLab/Einsatzbericht-Fotos, kein neues Gewicht; unter Windows zusätzlich `colorama`, BSD, war
bereits transitiv installiert). Reine Pip-Pakete ohne Systemabhängigkeit.

**Architektur -- ein zweites, unabhängiges Cookie statt eines erweiterten Anmelde-Cookies**:
`make_cookie()`/`parse_cookie()`/`user_from_request()` (bestehend, `app/auth.py`) bleiben
komplett unverändert. Neu: `dk_erp_otp_ok` (`OTP_COOKIE_NAME`), signiert mit demselben
`secret_key()`, aber einem eigenen HMAC-Namespace-Präfix (`"otp:"`), damit eine signierte
otp-Nutzlast nicht als normales Anmelde-Cookie durchgehen könnte. Belegt, dass FÜR DIESE
SITZUNG bereits ein zweiter Faktor bestätigt wurde -- geprüft gegen das Cookie, nicht gegen
einen Zustand auf dem Benutzerdatensatz selbst (sonst würde eine einzige bestätigte Sitzung
alle Geräte/Sitzungen desselben Administrators mit freischalten).

`app/main.py`s Middleware berechnet `otp_ok` nur für Administratoren (`otp_ok_for_user()`) und
blockiert, falls nicht vorhanden, JEDEN `/api/`-Aufruf außer den in `_TWO_FACTOR_SETUP_PATHS`
gelisteten (`/api/account/2fa/setup/start|confirm`, `/api/account/2fa/verify` -- `/api/auth/*`
ist über die bereits bestehende `_request_requires_login()`-Ausnahme ohnehin immer erreichbar)
mit `401 {"two_factor_pending": true}`. Seiten-Gerüste (`GET` auf nicht-`/api/`-Pfade) bleiben
immer erreichbar -- `_sidebar.html`s bereits auf jeder Seite laufender Status-Abruf leitet bei
`two_factor_required && !otp_ok` selbst auf `/account` weiter, kein globaler
Fetch-Interceptor nötig.

`POST /api/auth/login` prüft weiterhin AUSSCHLIESSLICH Benutzername/Passwort und setzt das
normale Anmelde-Cookie IMMER -- unabhängig davon, ob der zweite Faktor noch fehlt. Jede frische
Passwort-Anmeldung löscht das `dk_erp_otp_ok`-Cookie explizit (nicht nur, wenn keiner konfiguriert
ist) -- "bei jeder weiteren Anmeldung wird nach dem Passwort zusätzlich der Code abgefragt" gilt
damit ausnahmslos, auch wenn eine vorherige Sitzung noch nicht abgelaufen wäre.

**Ablauf, wie vorgegeben**: Ersteinrichtung (`app/templates/account.html`, "Mein Konto") zeigt
einen QR-Code (`POST /api/account/2fa/setup/start` -- erzeugt ein neues, noch UNBESTÄTIGTES
Geheimnis, verschlüsselt abgelegt wie das SMTP-Passwort über `app/crypto.py::encrypt_secret()`,
da der Klartext zur Code-Prüfung wiederherstellbar sein muss), der Administrator bestätigt mit
einem ersten, echten Code (`POST /api/account/2fa/setup/confirm`) -- **erst danach** wird
`AppUser.totp_confirmed_at` gesetzt und sind zehn Wiederherstellungscodes einmalig in der
Antwort enthalten (gehasht gespeichert wie Benutzerpasswörter, `hash_password()`/
`verify_password()`, da sie nie zurückgelesen werden müssen -- nur einmal beim Verbrauch
verglichen; jeder Code funktioniert genau einmal, `used_at` markiert den Verbrauch statt den
Code zu löschen). Bei jeder weiteren Anmeldung: `POST /api/account/2fa/verify` prüft einen
aktuellen TOTP-Code (`pyotp.TOTP(secret).verify(code, valid_window=1)`, ±1 Zeitschritt
Toleranz) ODER einen noch nicht verbrauchten Wiederherstellungscode.

**Frage 1 (aus der Planung): abgebrochene Einrichtung, kein Selbstaussperrungsrisiko --
bestätigt und mit Test abgesichert.** Nichts wird als aktiv markiert, bevor nicht ein echter
Code bestätigt wurde -- schließt ein Administrator das Einrichtungsfenster, ohne zu bestätigen,
bleibt `totp_confirmed_at` `NULL`. Beim nächsten Login beginnt der Ablauf einfach neu:
`setup/start` erzeugt ein NEUES Geheimnis, das das alte, nie bestätigte kommentarlos überschreibt
-- ein Code aus dem abgebrochenen ersten Versuch funktioniert danach nachweislich nicht mehr,
nur einer aus dem tatsächlich genutzten zweiten (`test_abandoned_setup_leaves_no_half_active_state_and_retry_works`,
`tests/test_v250_two_factor_auth.py`). Kein halb aktiver Zustand, keine Aussperrungsfalle.

**Frage 2 (aus der Planung): Notfall bei verlorenem Telefon UND verlorenen
Wiederherstellungscodes.** Zwei gestaffelte Wege:
1. Existiert noch ein ANDERER aktiver Administrator: dieser setzt den zweiten Faktor über die
   Benutzerverwaltung zurück (`POST /api/users/{id}/reset-two-factor`, `app/routers/users.py`,
   `require_admin()`-gated) -- ausschließlich für ANDERE Konten, niemals für das eigene (sonst
   ließe sich die Pflicht zum zweiten Faktor über die eigene Benutzerverwaltung wieder
   abschalten). `users.html` zeigt eine deutliche Warnung, wenn nur EIN aktiver Administrator
   existiert -- dann existiert dieser Weg praktisch nicht.
2. **`scripts/reset_admin_2fa.py`** -- Notfallskript, direkt auf dem Server auszuführen:

   ```
   python scripts/reset_admin_2fa.py <benutzername>
   ```

   Nutzt dieselbe `DATABASE_URL`/`ERP_DATA_DIR`-Konfiguration wie die Anwendung selbst (kein
   zweiter Konfigurationsweg), fragt vor dem Zurücksetzen zur Bestätigung nach erneuter Eingabe
   des Benutzernamens (`--yes` überspringt das für ein automatisiertes Runbook), protokolliert
   die Aktion über den normalen Logger nach `data/erp.log` (auditierbar, wer/wann zurückgesetzt
   hat). Danach: der Benutzer wird beim nächsten Login zur vollständigen Neueinrichtung
   aufgefordert, genau wie beim allerersten Mal. Dieselbe Anleitung steht auch im Kopfkommentar
   des Skripts selbst, damit sie im Ernstfall nicht erst gesucht werden muss.

### Selbstbedienungsseite "Mein Konto" (`GET /account`, `app/routers/account.py`)

Bisher konnte NIEMAND sein eigenes Passwort selbst ändern -- nur ein Administrator konnte das
Passwort eines ANDEREN Kontos setzen (`app/routers/users.py`). Im Onlinebetrieb ein eigenes
Problem: wer sein Passwort geändert haben wollte, musste es dem Administrator sagen, der es dann
kannte. `POST /api/account/change-password` (aktuelles + neues Passwort, jeder angemeldete
Benutzer) behebt das. Auf derselben Seite richten Administratoren zusätzlich den zweiten Faktor
ein (siehe oben) -- bewusst EINE Seite statt zwei, da beides "meine eigenen
Zugangsdaten verwalten" ist. Verlinkt aus `_sidebar.html`s Fußbereich neben "Abmelden".

**Bewusst NICHT gebaut**: ein bereits bestätigter zweiter Faktor lässt sich hier nicht durch
einen neuen ersetzen (z. B. neues Telefon, altes nicht verloren) -- dafür bleibt nur der Weg über
einen anderen Administrator oder das Notfallskript, beide setzen zuerst vollständig zurück.
Erkannte, aber nicht angefragte Lücke -- bei Bedarf nachrüstbar (ein "Neu einrichten"-Knopf, der
wie `setup/start` funktioniert, aber ein bereits bestätigtes Geheimnis überschreiben darf).

### Ein real gefundener Fehler, per Smoke-Test gegen eine echte Serverinstanz entdeckt

`request.state.erp_user` wird von `app/main.py`s Middleware über eine EIGENE, bereits wieder
geschlossene `SessionLocal()`-Instanz geladen -- nicht über die Session, die ein Endpunkt per
`Depends(get_db)` bekommt (das ist grundsätzlich eine ANDERE Session, siehe `require_admin()`/
`user_from_request()`). Die erste Fassung von `app/routers/account.py` mutierte dieses Objekt
direkt (`user.totp_secret_encrypted = ...`, `user.password_hash = ...`) und committete über die
Endpunkt-eigene Session -- die Änderung wurde dadurch STILLSCHWEIGEND NICHT persistiert, ohne
jede Fehlermeldung. Aufgefallen erst bei einem echten Ende-zu-Ende-Smoke-Test gegen eine
isolierte, aber echt laufende Serverinstanz (nicht die reine Testsuite: dort teilten sich
Middleware und Endpunkt in `router_test_client()`/den ersten `TestClient`-Testaufbauten
versehentlich dieselbe Session, was den Fehler verdeckte). Behoben in
`app/routers/account.py::_current_user()`: lädt den Benutzer jetzt IMMER über `db.get()` in der
jeweils richtigen Session neu, statt das über `request.state` hereingereichte Objekt direkt zu
verwenden -- exakt das Muster, das der Rest des Projekts (z. B. `routers/users.py`) an dieser
Stelle bereits einhält (`current` aus `require_admin()` wird dort nur für Vergleiche gelesen, nie
mutiert). Die Testaufbauten in `tests/test_v250_two_factor_auth.py` wurden danach bewusst auf
GETRENNTE Session-Objekte für Middleware und Endpunkte umgestellt (ein gemeinsamer Engine, aber
`sessionmaker()` liefert für jeden Aufruf eine neue Session), damit ein künftiger Rückfall in
dasselbe Muster wieder auffällt, statt von einem zu großzügigen Testaufbau verdeckt zu werden.

### Tests

`tests/test_v108_login_lockout_and_logging.py` (überarbeitet, nicht mehr In-Memory): Benutzername-
UND IP-Sperre einzeln und gemeinsam, automatisches Aufräumen alter Zeilen, identische
Fehlermeldung für unbekannten Benutzernamen/falsches Passwort. `tests/test_v250_two_factor_auth.py`:
`app/two_factor.py` isoliert (Setup/Bestätigung/Verifikation/Wiederherstellungscodes/Reset), die
abgebrochene-Einrichtung-Frage explizit, Admin-setzt-anderen-Admin-zurück-nie-sich-selbst, sowie
eine echte Ende-zu-Ende-Prüfung über einen eigens für den Test aufgebauten `TestClient` mit
echten Cookies (nicht `router_test_client()`, das die Identität komplett fälscht) -- Login ohne
zweiten Faktor wird zur Einrichtung geleitet, Business-Endpunkte bleiben bis dahin gesperrt,
nach Bestätigung frei; ein bereits eingerichteter Administrator muss bei jedem Login erneut den
Code eingeben; Nicht-Administratoren sind nie betroffen; wiederholt falsche Codes lösen die
2FA-eigene Sperre aus. `tests/test_v251_account_self_service.py`: Passwortänderung (inkl. für
normale Benutzer, nicht nur Administratoren), Seiteninhalt/Verdrahtung (Muster
`test_v163_sidebar_login_status.py`), und `scripts/reset_admin_2fa.py`s `main()` direkt gegen
eine isolierte Testdatenbank (niemals die echte `DATABASE_URL`) -- Bestätigung korrekt/falsch/
`--yes`/unbekannter Benutzername.

## Diesem Gerät für 30 Tage vertrauen (seit 1.5.11)

Der zweite Faktor musste bis hierhin bei JEDER Anmeldung erneut eingegeben werden -- auf Wunsch
prüfbar/optional machen, ohne die eigentliche Pflicht (1.3.34) aufzuweichen: das Passwort bleibt
in jedem Fall bei jeder Anmeldung verlangt, nur die Code-Abfrage entfällt auf einem zuvor als
vertraut markierten Gerät für 30 Tage. Auf ausdrückliche Vorgabe erst ein reiner Befund (wie 2FA
und das Anmelde-Cookie heute funktionieren, ALLE Stellen im Code, die den zweiten Faktor oder das
Passwort ändern), dann nach Bestätigung gebaut.

### Befund: fünf Stellen ändern den zweiten Faktor oder das Passwort

Ein projektweiter Grep auf `password_hash\s*=|totp_confirmed_at\s*=|totp_secret_encrypted\s*=`
bestätigte Vollständigkeit über die reine Code-Lektüre hinaus. `two_factor.reset()`
(`app/two_factor.py`) ist eine einzige, gemeinsam genutzte Funktion mit ZWEI unabhängigen
Aufrufern (Admin-Reset eines ANDEREN Kontos, `POST /api/users/{id}/reset-two-factor`, UND das
Notfallskript `scripts/reset_admin_2fa.py`) -- ein einziger Hook dort deckt beide automatisch ab.
Dazu zwei Passwort-Stellen (`POST /api/account/change-password` für die eigene Änderung,
`PUT /api/users/{id}` für ein von einem Administrator für ein ANDERES Konto gesetztes Passwort --
letzteres der beim Befund gefundene, in der ursprünglichen Aufzählung nicht enthaltene fünfte
Fall: ohne ihn bliebe die Lücke, dass ein Admin-Passwortwechsel für einen anderen Nutzer dessen
vertraute Geräte stehen lässt). Der fünfte "Stellen"-Zähler zählt den ausdrücklichen Widerruf
("Alle vertrauten Geräte abmelden") als eigene, dritte Bedingung neben "2FA neu eingerichtet/
zurückgesetzt" und "Passwort geändert" mit -- macht rechnerisch: zwei Aufrufer von `reset()` +
zwei Passwort-Stellen + ein expliziter Widerruf = fünf Stellen insgesamt.

**Ersteinrichtung (`confirm_setup()`) ist bewusst KEINE der fünf Stellen** -- sie kann laut
Betreiberentscheidung ohnehin nur einmal auf einem noch unkonfigurierten Konto laufen
(`is_configured()`-Sperre in `start_two_factor_setup()`/`confirm_two_factor_setup()`); eine
"Neueinrichtung" existiert im Code nur als "erst `reset()`, dann `confirm_setup()` auf dem dann
wieder leeren Konto" -- bereits vollständig durch den `reset()`-Hook abgedeckt, kein eigener
sechster Fall.

### Server-seitig verwaltet, eigenständiges Cookie (`app/device_trust.py`)

Ein Cookie allein würde keinen Widerruf erlauben -- deshalb eine neue Tabelle
(`app/models.py::TrustedDevice`, `user_id`/`token_hash`/`expires_at`, `cascade="all,
delete-orphan"`-Relationship auf `AppUser`, Muster `TwoFactorRecoveryCode`) plus ein
DRITTES, von `dk_erp_auth`/`dk_erp_otp_ok` unabhängiges, signiertes Cookie (`dk_erp_trust`).
Anders als bei den beiden bestehenden Cookies trägt es aber keine HMAC-Signatur über
`secret_key()` -- unnötig, da der Cookie-Wert (Zeilen-ID + ein `secrets.token_urlsafe(32)`-
Geheimnis mit 256 Bit Entropie) selbst schon unforgeable ist: der Server vergleicht das
mitgeschickte Geheimnis gegen den in der Zeile gespeicherten Hash
(`hash_password()`/`verify_password()`, dieselbe Technik wie bei Wiederherstellungscodes --
das Geheimnis wird nie zurückgelesen, nur beim Prüfen verglichen). Migration `0f7bda3397f1`
(neue Tabelle, kein Regel-1-Fall -- keine NOT-NULL-Spalte auf einer bestehenden Tabelle).

`app/device_trust.py::create_trust(db, user)` legt eine neue Zeile an und liefert den fertigen
Cookie-Wert; `check_trust(db, user, cookie_value)` prüft Ablauf UND -- entscheidend für die
Konten-Isolation -- dass die geladene Zeile `user_id == user.id` trägt, bevor der Hash überhaupt
verglichen wird: ein (echtes oder gefälschtes) Cookie, das auf ein fremdes Konto zeigt, scheitert
so unabhängig vom Geheimnis; `revoke_all(db, user)` löscht alle Zeilen eines Kontos (aufgerufen
an allen fünf oben genannten Stellen). Gültigkeit ist FEST 30 Tage ab dem Setzen des Häkchens,
keine gleitende Verlängerung bei jeder erneuten Anmeldung.

### Checkbox nur bei der Routine-Bestätigung, nie bei der Ersteinrichtung

Auf ausdrückliche Betreiberentscheidung: die Checkbox "Diesem Gerät für 30 Tage vertrauen"
erscheint AUSSCHLIESSLICH bei `POST /api/account/2fa/verify` (neues Schema
`TwoFactorVerifyRequest(TwoFactorCodeRequest)` mit zusätzlichem `trust_device: bool = False`) --
niemals bei `POST /api/account/2fa/setup/confirm` (bleibt bei `TwoFactorCodeRequest` ohne dieses
Feld, ein untergeschobenes `trust_device` im JSON-Body wird von Pydantic stillschweigend
ignoriert). Begründung: bei der Ersteinrichtung sieht der Nutzer gerade zum ersten Mal die
Wiederherstellungscodes und baut den Schutz gerade erst auf -- ihn im selben Schritt für 30 Tage
auszusetzen wäre widersprüchlich, und wäre zudem inkonsistent mit der dritten Bedingung oben
(eine Neueinrichtung LÖSCHT alles Vertrauen über den `reset()`-Hook, direkt im selben Schritt
wieder eins zu setzen wäre in sich widersprüchlich). Das Vertrauen greift dadurch erst ab der
nächsten, zweiten Anmeldung.

**Before/after-Reihenfolge geprüft, wie vom Betreiber verlangt**: ein Widerruf darf nie ein im
selben Vorgang neu erzeugtes Vertrauen mittreffen. Bei den beiden Passwort-Stellen ist die
Reihenfolge im Code fest verankert -- erst `db.commit()` für den neuen `password_hash`, dann
erst `device_trust.revoke_all()` --, und da an keiner der beiden Stellen im selben Aufruf ein
neues Vertrauen entstehen kann (keine der beiden Endpunkte kennt `trust_device`), gibt es dort
grundsätzlich nichts, was kollidieren könnte. Bei `confirm_setup()` entsteht aus demselben Grund
(kein Häkchen an dieser Stelle) ebenfalls nie ein neues Vertrauen, das ein `reset()`-Aufruf
versehentlich mitlöschen könnte.

### Login-Integration: das Passwort bleibt unberührt, nur die Code-Abfrage entfällt

`POST /api/auth/login` (`app/routers/auth.py`) prüft weiterhin AUSSCHLIESSLICH Benutzername/
Passwort und setzt das Anmelde-Cookie IMMER. Neu: bei einem Administrator mit bereits
konfiguriertem zweiten Faktor wird zusätzlich ein mitgeschicktes `dk_erp_trust`-Cookie gegen
GENAU dieses Konto geprüft (`device_trust.check_trust()`) -- ist es gültig, wird das
`dk_erp_otp_ok`-Cookie direkt hier gesetzt statt (wie bisher unbedingt) gelöscht, und die
Antwort trägt ein neues `otp_ok`-Feld. `login.html` nutzt dieses Feld, um den bisherigen
Zwischenstopp auf `/account` zu überspringen (`(d.two_factor_required&&!d.otp_ok)?'/account':...`
statt zuvor nur `d.two_factor_required?...`) -- ein vertrautes Gerät landet dadurch direkt am
eigentlichen Ziel, nicht erst auf der Kontoseite.

### "Alle vertrauten Geräte abmelden"

Neuer, für jede angemeldete Person erreichbarer Endpunkt `POST
/api/account/trusted-devices/revoke-all` (Selbstbedienungsmuster wie `change_password()` --
`_current_user()`, keine feste Rollenprüfung, in `ROLE_AUDIT_EXEMPT` einzeln begründet wie
`change-password` direkt daneben) -- ruft `revoke_all()` für das EIGENE Konto auf und löscht das
eigene `dk_erp_trust`-Cookie. Button unter "Mein Konto" im 2FA-Statusbereich, mit `confirm()`
(Regel 4: kein `prompt()`, `confirm()` für eine einfache Ja/Nein-Bestätigung ist etabliert).

### Angriffstest

`tests/test_v292_device_trust.py` (20 Tests): `app/device_trust.py` isoliert (Rundlauf, Ablauf,
Kauderwelsch-/fehlendes Cookie, gefälschtes Geheimnis bei echter Zeilen-ID, Konten-Isolation,
`revoke_all()` trifft nie ein fremdes Konto und löscht mehrere eigene Geräte vollständig). Sowie
eine echte Ende-zu-Ende-Prüfung über einen eigens aufgebauten `TestClient` mit echten Cookies
(Muster `test_v250_two_factor_auth.py`): **jede der fünf Stellen einzeln** -- nach jeder von
ihnen ist ein zuvor vertrautes Gerät nachweislich wertlos, ein Login mit dem alten Cookie liefert
`otp_ok: false`, der Code wird wieder verlangt (zusätzlich zur Verhaltensprüfung auch direkt per
`device_trust.check_trust()` und einer leeren `TrustedDevice`-Abfrage bestätigt). Dazu eine
Gegenprobe (eine Änderung OHNE `new_password` an `PUT /api/users/{id}` lässt das Vertrauen
unangetastet -- die Revokation hängt am Passwort, nicht an jeder Änderung des Datensatzes), ein
gefälschtes/manipuliertes Trust-Cookie wird beim Login abgelehnt, und das Trust-Cookie eines
Kontos gewährt nachweislich nie Zugriff unter einem anderen Konto (inkl. der Umkehrprobe, dass
dasselbe Cookie beim RICHTIGEN Konto weiterhin funktioniert). Die Checkbox erzeugt bei
`confirm_setup()` in keinem Fall ein Vertrauen, selbst wenn das Feld im Request-Body
untergeschoben wird. Volle Suite: 1688 Tests grün.

## Serverseitige Anmeldeschranke für Seiten (seit 1.3.47)

Auf Nutzeranfrage geprüft: was passiert bei Aufruf von `/` ohne Anmeldung, `/` mit
Anmeldung, `/login` bei bestehender Anmeldung -- und ob nach dem Anmelden zur ursprünglich
gewünschten Seite zurückgeführt wird. Befund vor dieser Version: **keine** HTML-Seite prüfte
den Anmeldestatus serverseitig -- jede Seite (auch `/tasks`, `/settings`, `/` selbst) rendere
ihr Gerüst mit Status 200, unabhängig davon, ob jemand angemeldet war. Die einzige
Auswirkung fehlender Anmeldung war rein clientseitig: `_sidebar.html`s
`fetch('/api/auth/status')` zeigte dann nur ein Login-Formular im Fußbereich, der übrige
Seiteninhalt blieb (nutzlos) stehen. `/` mit Anmeldung zeigte bereits korrekt das Dashboard
-- aber nicht durch eine Weiterleitung, sondern weil `/` schon immer direkt `dashboard.html`
rendert (`dashboard_page()`, keine separate `/dashboard`-Route). `/login` bei bestehender
Anmeldung zeigte die Maske unverändert erneut -- `login_page()` prüfte den Anmeldestatus
gar nicht.

**Behoben, zwei Teile:**

1. **`app/main.py::_page_requires_login(has_users, method, path)`** -- bewusst eine neue,
   getrennte Funktion, NICHT in `_request_requires_login()` verschmolzen: eine `/api/`-Anfrage
   soll bei fehlender Anmeldung weiterhin die dortige 401-JSON-Antwort bekommen, nie einen
   Redirect auf eine HTML-Seite (ein API-Client könnte damit nichts anfangen). Greift nur bei
   `GET`, nicht `/api/...`, und lässt `/login` (sonst könnte sich niemand anmelden), `/health`
   (externe Überwachung, bereits zuvor ungated) und `/manifest.json` (reine PWA-Ressource der
   Monteursansicht, ohnehin nur von der bereits angemeldeten Seite `/mobil` aus verlinkt)
   sowie die bereits bestehende Bootstrap-Ausnahme (kein einziger ERP-Benutzer angelegt --
   `/users` muss für die allererste Kontoanlage erreichbar bleiben) unangetastet. In der
   Middleware (`identity_and_audit_middleware`) verdrahtet: ohne angemeldeten Benutzer liefert
   eine sonst betroffene Seite jetzt `302 → /login?next=<Pfad>` statt zu rendern.
2. **`app/routers/pages.py::login_page()`** -- leitet weiter, wenn `request.state.erp_user`
   bereits gesetzt ist: auf `/`, außer ein Administrator hat den zweiten Faktor noch nicht
   bestätigt (`not request.state.otp_ok`), dann auf `/account` -- dort ist ohnehin nichts
   anderes nutzbar (siehe `_blocked_pending_two_factor()`), ein Redirect aufs Dashboard hätte
   dort nur einen weiteren, überflüssigen Zwischenschritt über `_sidebar.html`s eigene
   Weiterleitung erzeugt.

**Rückführung zur ursprünglich gewünschten Seite (`?next=`), auf Nachfrage ergänzt** -- Kosten
waren minimal, da `login.html` einen solchen Parameter bereits liest und honoriert (bisher nur
für die bestehenden Abmelden-Links gebaut, siehe `_sidebar.html`/`_topbar.html`/
`_mobile_header.html`/`vor_ort.html`: `location.href='/login?next='+encodeURIComponent(
location.pathname)`). Der neue Redirect in `identity_and_audit_middleware` hängt dieselbe
Konvention an (`?next=<Pfad>`, ohne Query-String -- exakt wie bei jenen Links) -- keine
Template-Änderung nötig, `login.html`s Anmeldeformular führt danach automatisch zur
ursprünglich gewünschten Seite statt immer zu `/projects` (dem bisherigen Rückfall ohne
`next`, unverändert).

**Fallstrick beim Testen, selbst gefunden**: `tests/test_v218_template_rendering.py`
(`router_test_client()`, injiziert einen fest angemeldeten Admin-Kontext OHNE die produktive
Middleware) rendert JEDE Seiten-Route inkl. `/login` -- die neue `login_page()`-Logik griff
dabei auf `request.state.otp_ok` zu, das dieser Testaufbau nie setzt (nur die echte Middleware
tut das). `AttributeError` statt eines einfachen Testfehlers. Behoben durch
`getattr(request.state, "otp_ok", True)` statt direktem Attributzugriff -- robuster
Rückfallwert, passend zum bereits etablierten Muster in `app/deps.py::require_admin()`
(`getattr(request.state, "erp_user", None)`).

**Isolierter Ende-zu-Ende-Test** (`tests/test_v256_login_wall_for_pages.py`, Muster
`test_v250_two_factor_auth.py::_make_test_app()` -- eigene, throwaway In-Memory-SQLite-Engine,
eigene, aus den echten Funktionen `_page_requires_login()`/`_request_requires_login()`
nachgebaute Middleware, NICHT `router_test_client()`, das für "ohne Anmeldung"-Szenarien
ungeeignet ist): direkte Prüfung der Entscheidungsregel selbst (analog
`test_v106_access_control.py`), sowie über einen echten `TestClient` mit echten Cookies --
unangemeldeter Aufruf einer geschützten Seite liefert `302` mit korrektem `next=`, `/login`
selbst bleibt erreichbar und zeigt die Maske, `/health` bleibt ungated, die Bootstrap-Ausnahme
vor der ersten Kontoanlage greift, eine angemeldete Person erreicht Seiten direkt, `/login`
leitet eine bereits angemeldete Person weiter (auf `/` bzw. `/account` bei ausstehendem
zweitem Faktor). **Bewusst nicht end-to-end mit echtem Browser geprüft** (dieselbe, bereits
mehrfach dokumentierte Werkzeug-Einschränkung dieser Umgebung) -- `login.html`s eigene,
bereits bestehende JS-Auswertung von `next` (unverändert) lässt sich ohne echten Browser
nicht ausführen; die Tests belegen stattdessen den vollständigen SERVERSEITIGEN Anteil des
Rundwegs (korrekter `next`-Wert im Redirect, Zielseite nach der Anmeldung tatsächlich direkt
erreichbar).

### Fehlerbehebung (seit 1.3.48): zwei reale Fehler in der Umleitung, auf dem Produktivserver gefunden

**Fehler 1: `/login` leitete trotz bestehender, vollständiger Anmeldung nicht auf `next`
weiter.** `login_page()` (1.3.47) redirectete eine bereits angemeldete Person mit
bestätigtem zweitem Faktor immer auf `/`, unabhängig von einem mitgegebenen `?next=` --
behoben: liest `next` jetzt über die neue `_safe_next_target()` (siehe unten) und leitet
dorthin weiter, sonst weiterhin aufs Dashboard.

Die konkret gemeldete Beobachtung ("Anmeldemaske erscheint erneut, obwohl die Sitzung
besteht") hatte aber eine ANDERE, eigentliche Ursache, die dieser Fix allein nicht behoben
hätte: `account.html`s Link "← Zur Startseite" trug `onclick="if(document.referrer){
history.back();return false}"` -- während der 1.3.34-Zwei-Faktor-Pflicht zeigte
`document.referrer` dort auf `/login` (die Seite, von der `login.html`s JS nach der
Passwort-Eingabe auf `/account` weiterleitet). Ein Klick sprang deshalb über den
Browser-Verlauf zurück auf genau diese Login-Ansicht -- ggf. direkt aus dem bfcache, **ohne
jede Serveranfrage**, weshalb auch ein korrekt umleitendes `login_page()` das Symptom nicht
verhindert hätte: der Browser fragte den Server gar nicht erst. Behoben durch einen
einfachen `href="/"` ohne den `history.back()`-Zusatz -- "Zur Startseite" meint ein
konkretes Ziel, kein "zurück zur vorigen Seite" wie die sonst im Projekt üblichen
`history.back()`-Links (`users.html`, `master_data_form.html` u. a., dort unverändert
richtig, da deren Vorseite immer eine legitime, bereits angemeldete Seite ist).

**Fehler 2: nach Bestätigung des Codes landete man auf `/account` statt auf dem
eigentlichen Ziel.** `account.html::verifyCode()` (die ROUTINE-Bestätigung -- zweiter Faktor
war schon eingerichtet, nur diese Sitzung musste ihn noch bestätigen) rief nach Erfolg nur
`load()` auf, was lediglich die Kontoseite selbst neu zeichnete (zeigt dann "Passwort
ändern"/Zwei-Faktor-Status). Behoben: leitet jetzt auf `next` bzw. das Dashboard weiter.
**Bewusst unverändert**: die ERSTEINRICHTUNG (`confirmSetup()`/`finishSetup()`) bleibt auf
`/account` -- dort müssen erst die einmalig angezeigten Wiederherstellungscodes gesehen
werden, `/account` ist in diesem Fall das tatsächliche, gewollte Ziel, kein Zwischenschritt.
Damit `next` über den Zwischenschritt `/account` hinweg erhalten bleibt (vorher ging dabei
jede Information über das ursprüngliche Ziel verloren), hängt `login.html` beim Weiterleiten
auf `/account` jetzt `location.search` unverändert an.

**`_safe_next_target()`** (`app/routers/pages.py`, neu): da `login_page()` seit 1.3.48 einen
vom Client mitgegebenen `next`-Wert tatsächlich für einen SERVERSEITIGEN Redirect verwendet
(anders als `app/main.py`s Middleware, die `next` selbst aus dem aufgerufenen Pfad baut und
deshalb nichts validieren muss), wird der Wert vorher geprüft -- akzeptiert nur Werte, die
mit genau einem `/` beginnen, lehnt `//...` (protokoll-relativ) und absolute URLs ab. Ohne
diese Prüfung wäre ein serverseitiger offener Redirect entstanden (`?next=https://
evil.example/...`), eine strengere Gefahrenklasse als die bereits bestehende, rein
clientseitige `next`-Auswertung in `login.html` (dort schon seit früherer Version
ungeprüft, aber dort nur wirksam, wenn die Zielseite selbst dieses JS ausführt -- kein
neuer Fund, unverändert gelassen, siehe „Bekannte, bewusst offene Punkte").

**Geprüft, wie verlangt: `request.state.otp_ok` überall korrekt ausgewertet?** Projektweiter
Grep bestätigt genau drei Lesestellen: `app/main.py` selbst (setzt den Wert), `app/routers/
auth.py::auth_status()` und `app/routers/pages.py::login_page()` -- beide Leser nutzen
bereits `getattr(request.state, "otp_ok", True)` mit sicherem Rückfall (der zweite davon erst
seit 1.3.47, siehe dort für den Fund im Testaufbau, der genau diese Absicherung nötig
machte). Kein weiterer Fund.

**Tests** (`tests/test_v257_login_redirect_fixes.py`): vier Kombinationen (next: ja/nein ×
zweiter Faktor eingerichtet: ja/nein) für `login_page()`s Entscheidung bei bestehender
Anmeldung, sowie der vollständige serverseitige Rundweg für alle drei Anmeldewege (ohne
Zwei-Faktor, über die Ersteinrichtung, über die Routine-Bestätigung) -- jeweils bestätigt,
dass ein nachfolgender Aufruf tatsächlich zum ursprünglichen Ziel führt, nicht zurück nach
`/account`. Dazu `_safe_next_target()` isoliert sowie drei Strukturprüfungen der
Template-Quellen (next-Weitergabe in `login.html`, `verifyCode()` leitet weiter statt
`load()` erneut aufzurufen, der "Zur Startseite"-Link trägt kein `history.back()` mehr) --
die eigentliche JS-Navigation selbst lässt sich ohne echten Browser nicht ausführen
(dieselbe, wiederholt dokumentierte Werkzeug-Einschränkung dieser Umgebung).

## PostgreSQL-Umstieg: Migrationskette repariert (seit 1.3.35)

Erste Reparaturrunde vor dem eigentlichen Datenumzug -- Nutzervorgabe: "Wir reparieren zuerst,
bevor irgendetwas umzieht." Datenumzug (eigenes Python-Skript statt pgloader, wie abgestimmt),
Backup-Skript-Umbau und die Abschaltung von `create_all()` im Produktionsbetrieb sind bewusst
NICHT Teil dieser Runde -- alle drei sind erkannt und berichtet, aber eigene, spätere Schritte.

### Der `e057d15af828`-Fund: der Migrations-Workflow-Fallstrick, tatsächlich eingetreten

Die Migration `e057d15af828` ("Rechnungswesen") bestand vollständig aus `pass`/`pass` -- ein
echter No-op, keine invertierte oder unvollständige Logik. Betroffen waren ausgerechnet
`invoices`/`invoice_items`, zwei der zentralsten Tabellen des ganzen Projekts.

**Wie das entstanden ist** -- exakt der Mechanismus, der im Abschnitt "Migrations-Workflow"
unten bereits als allgemeine Warnung beschrieben ist ("Fallstrick, seit 1.2.23 bekannt:
`app/main.py` ruft beim Import `Base.metadata.create_all(bind=engine)` auf"), hier aber der
tatsächliche Beweis, dass er real zugeschlagen hat, nicht nur eine theoretische Gefahr: als das
Rechnungswesen-Feature gebaut wurde, hat irgendein Vorgang (ein Testlauf, ein Serverstart, ein
simpler `import app.main`) `app.main` geladen, BEVOR `alembic revision --autogenerate` für die
neuen `Invoice`/`InvoiceItem`-Modelle lief. `create_all()` legte beide Tabellen dabei bereits
real in der SQLite-Datei an. Als Autogenerate danach lief, verglich es den ORM-Modellstand gegen
die (durch `create_all()` bereits identische) reale Datenbank -- fand keinen Unterschied -- und
erzeugte eine leere Hülle statt der beiden `CREATE TABLE`-Anweisungen.

**Warum das unter SQLite jahrelang unsichtbar blieb**: `create_all()` läuft bei JEDEM Start von
`app/main.py` erneut (dasselbe Sicherheitsnetz, das den Fehler verursacht hat, verdeckte ihn
danach zuverlässig weiter) -- eine lokale, immer schon laufende SQLite-Installation hatte die
Tabellen dadurch bei jedem Start automatisch nachgezogen, unabhängig vom Zustand der
Migrationskette. Erst eine komplett FRISCHE Datenbank, aufgebaut ausschließlich über
`alembic upgrade head` OHNE je einen `create_all()`-Lauf dazwischen, würde diesen Widerspruch
zeigen -- exakt der Fall bei einer neuen PostgreSQL-Installation für den geplanten Serverumzug,
wo bei einer leeren Zieldatenbank kein `create_all()` mehr rettend eingreift. Gefunden per
Skript, das alle `Base.metadata.tables` gegen jeden `create_table(...)`-Aufruf in
`alembic/versions/*.py` abgeglichen hat -- `invoices`/`invoice_items` waren die einzigen beiden
Tabellen im ganzen Projekt ohne eine erzeugende Migration.

**Reparatur, in-place statt angehängt**: da die reale, produktive `dachkonzepte_erp.db` längst
weit über diesem Punkt steht (Head `1b55170709a6`) und Alembic Revisionen ausschließlich über
die `alembic_version`-Tabelle trackt (nie inhaltlich erneut ausführt), ist ein nachträgliches
Befüllen der bereits angewendeten Migration sicher -- verifiziert durch `alembic current`/
`alembic upgrade head` gegen die reale Datei, die dabei unverändert bei ihrem Head-Stand
blieb (kein "Running upgrade"). Die Migration musste dabei den historischen Spaltenstand ZUM
DAMALIGEN ZEITPUNKT DER KETTE abbilden, nicht das heutige Vollschema -- sonst hätten die vier
später folgenden `batch_alter_table('invoices'/'invoice_items', ...)`-Migrationen (`bb175f455b64`,
`3eb9f52b38ab`, `8c0bddc8321c`, `369f94b5d5d3`) versucht, bereits vorhandene Spalten erneut
hinzuzufügen. Rekonstruiert durch Rückrechnen: alle vier Folgemigrationen gelesen, ihre
`add_column`-Aufrufe von `invoices`s heutigem 31-Spalten-Vollschema abgezogen (Ergebnis: 23
historische Spalten -- ohne `tax_key_id`, `tax_notice_text`, `outro_text_2`, `email_sent_at`,
`email_sent_to`, `payment_terms_text_template`, `skonto_percent`, `skonto_days`), gegen
`app/models.py`s eigene "seit 1.0.4x"-datierte Docstring-Kommentare der `Invoice`-Klasse
kreuzgeprüft (deckungsgleich). `invoice_items` bekam dagegen das volle heutige Schema, da KEINE
spätere Migration diese Tabelle je verändert (zweiter Grep bestätigt).

### Die übrigen vier Reparaturpunkte derselben Runde

- **`datetime('now')`** (SQLite-spezifische SQL-Funktion, unter PostgreSQL unbekannt) in
  `257fb2967c93`/`ab5eef23f9ed` durch `sa.text(...).bindparams(now=datetime.utcnow())` ersetzt --
  SQLAlchemy übersetzt den gebundenen Python-`datetime`-Wert dialektkorrekt.
- **Boolean-Literale in rohem SQL** (`1`/`0`, unter PostgreSQL strikt typisiert statt implizit
  nach `boolean` konvertiert wie bei SQLite) in sieben Migrationen (`4609e3fc8976`,
  `06299a5101f5`, `2fffb80e5567`, `0064c87051aa`, `5c8715dba230`) auf gebundene Python-`True`/
  `False`-Parameter bzw. `TRUE`/`FALSE`-SQL-Schlüsselwörter umgestellt (letzteres nur, wo keine
  Bind-Infrastruktur in der jeweiligen Anweisung existierte). **App-seitige
  `Column == True/False`-ORM-Vergleiche blieben ausdrücklich unangetastet** -- die übersetzt
  SQLAlchemy bereits pro Dialekt korrekt, betroffen war ausschließlich rohes `sa.text()`-SQL.
- **`app/audit.py:263`**: `AuditLog.actor_name.contains(actor)` (case-insensitive unter SQLite,
  case-sensitive unter PostgreSQL -- hätte eine Audit-Log-Suche nach Beauftragtem auf Postgres
  unauffindbar strenger gemacht) auf `.ilike(f"%{actor}%")` umgestellt. Projektweite Prüfung auf
  weitere `.contains()`/`.startswith()`-Fälle mit derselben Gefahr: kein zweiter Fund.

### Verifikation -- fester Bezugspunkt für künftige Nachfragen

**Stand: Version 1.3.35, verifiziert am 13.09.2026.** Falls in einem halben Jahr jemand fragt,
ob die Migrationskette tatsächlich vollständig gegen PostgreSQL läuft: ja, ab genau dieser
Version, mit vier konkreten Nachweisen, keiner davon nur behauptet:

1. Eine lokale, portable PostgreSQL-17-Instanz (EnterpriseDB-ZIP-Binaries, kein Admin-Zugriff
   nötig -- `%LOCALAPPDATA%\pgportable`, Port 5433, Datenbank `spielwiese`) wurde geleert und
   `alembic upgrade head` OHNE `DATABASE_URL`-Override auf SQLite ausgeführt -- alle 55
   Migrationen liefen vollständig und fehlerfrei durch, `alembic_version` landete korrekt bei
   `1b55170709a6`, `information_schema.tables` zeigte die erwarteten 122 Tabellen (121
   ORM-Modelle + `alembic_version`).
2. Dieselbe, frisch geleerte SQLite-Datei (kein Bestand, kein `create_all()`-Vorlauf) durchlief
   `alembic upgrade head` ebenfalls vollständig -- keine Regression durch die vier
   dialektneutralen Fixes.
3. Die reale, bereits vollständig migrierte Produktionsdatenbank `dachkonzepte_erp.db` blieb bei
   erneutem `alembic upgrade head` unverändert bei ihrem Head-Stand (kein "Running upgrade") --
   das in-place-Editieren bereits angewendeter Migrationen hat keine Nebenwirkung auf eine
   Installation, die längst darüber hinaus ist.
4. Volle Testsuite `pytest`: 1040/1040 grün.

Sollte diese Prüfung ein weiteres Mal nötig werden (z. B. nach einer künftigen Migration, die
denselben Risikotyp trägt -- ein neues Modell, das versehentlich vor `--autogenerate` per
`create_all()` real angelegt wird), ist die oben beschriebene portable PostgreSQL-Instanz auf
Nutzerwunsch NICHT entfernt worden ("wir brauchen sie noch") -- sie steht für den geplanten
Datenumzug weiterhin bereit, aktuell gestoppt (`pg_ctl stop`), aber mit Daten und Konfiguration
unverändert vorhanden.

### Datenumzugsskript (seit 1.3.36)

Erste Runde des eigentlichen Datenumzugs -- nur das Skript bauen und lokal gegen die portable
PostgreSQL-Instanz ausprobieren; der Umzug auf den Server bleibt ein eigener, späterer Schritt.

**`scripts/migrate_sqlite_to_postgres.py`** -- Notfall-taugliche Aufrufanleitung, direkt
auszuführen (dieselbe Sofort-auffindbar-Anforderung wie bei `reset_admin_2fa.py`, siehe oben):

```
python scripts/migrate_sqlite_to_postgres.py --target-url postgresql+psycopg://user:pass@host:port/dbname
```

Liest standardmäßig die reale `dachkonzepte_erp.db` im Projektordner -- **ausschließlich
lesend**: über SQLites Online-Backup-API in eine temporäre Kopie gesichert (verträgt sich mit
einer parallel laufenden Anwendung), diese zusätzlich per `mode=ro`-URI geöffnet, ein
Schreibversuch würde vom Treiber selbst verweigert, nicht nur vermieden. **Sicherung gegen eine
nicht leere Zieldatenbank** (falsch übergebene Verbindungszeichenfolge, verwechselte
Umgebungsvariable): das Skript verweigert den Dienst, sobald in der Zieldatenbank auch nur eine
Zeile in einer der dem ORM bekannten Tabellen steht -- außer `--force-truncate` wird
ausdrücklich gesetzt, und selbst dann fragt es ohne zusätzliches `--yes` interaktiv nach dem
Datenbanknamen zur Bestätigung (Muster: `reset_admin_2fa.py`). Das Leeren selbst bleibt dabei
strikt auf die Tabellen beschränkt, die `Base.metadata` tatsächlich kennt -- nie ein
pauschales DROP SCHEMA/DATABASE anhand der übergebenen Verbindungszeichenfolge. Ablauf:
`alembic upgrade head` gegen das Ziel, Daten laden (`Base.metadata.sorted_tables`-Reihenfolge),
Fremdschlüssel-Konsistenz der geladenen Daten prüfen, Sequenzen zurücksetzen (jede Tabelle mit
Integer-Primärschlüssel, nicht nur eine vermutete Handvoll), Zeilenzahlen Quelle gegen Ziel
verifizieren, verschlüsselte SMTP-/Microsoft-365-/TOTP-Felder probeweise entschlüsseln (ohne den
Klartext je auszugeben). Dieselbe Anleitung steht auch im Kopfkommentar der Skriptdatei selbst.

**Fund, der über dieses eine Skript hinausgeht -- ein dauerhaftes Prinzip für jedes künftige
Skript gegen PostgreSQL:** der erste Entwurf schaltete für die Dauer des Ladens die
Fremdschlüssel-Trigger auf allen Zieltabellen ab (`ALTER TABLE ... DISABLE TRIGGER ALL`) --
notwendig, weil zwei Tabellen (`quote_sections`/`order_sections`) sich selbst referenzieren
(`parent_id`) und PostgreSQL eine Fremdschlüssel-Bedingung standardmäßig sofort bei jeder
einzelnen Zeile prüft, nicht erst beim Commit. Der erste tatsächliche Testlauf scheiterte damit
sofort: `InsufficientPrivilege: ... ist ein Systemtrigger`. Die internen, eine
Fremdschlüssel-Bedingung durchsetzenden Trigger (`RI_ConstraintTrigger_*`) lassen sich nur von
einem Superuser abschalten -- eine gewöhnliche Anwendungsrolle hat dieses Recht nicht, und genau
eine solche gewöhnliche Rolle ist auf einem gehosteten PostgreSQL-Server (verwaltete Datenbank,
kein eigener Serverzugriff) realistisch alles, was zur Verfügung steht. **Die eigentliche Lehre:
eine Lösung, die Superuser-Rechte voraussetzt, lässt sich lokal (wo die eigene Rolle typischerweise
Eigentümer aller Tabellen ist und mehr darf) erfolgreich testen und scheitert dann erst beim
ersten echten Einsatz auf dem Zielserver -- der schlechteste Zeitpunkt, das zu merken.** Behoben
ohne besondere Rechte: die beiden betroffenen Tabellen werden in mehreren Durchläufen geladen
(erst Zeilen ohne offene Selbstreferenz, dann die, deren Elternzeile bereits geladen ist, beliebig
tief verschachtelbar) -- funktioniert mit jeder Rolle, die schlicht INSERT auf ihre eigenen
Tabellen darf. **Gilt als Grundsatz für jedes künftige Skript, das schreibend gegen eine
PostgreSQL-Datenbank arbeitet**: nichts bauen, das `DISABLE TRIGGER ALL`, `SET
session_replication_role` oder eine vergleichbare, Superuser voraussetzende Abkürzung braucht,
ohne das vorher gegen eine Rolle ohne Superuser-Rechte zu prüfen -- lokal ist die eigene Rolle
fast immer großzügiger berechtigt als später auf dem echten Server.

**Lauf gegen die lokale `spielwiese`-Instanz, Stand 13.09.2026**: 121 Tabellen, 3040 Zeilen,
1,7 Sekunden, 0 Zeilenzahl-Abweichungen, 0 verwaiste Fremdschlüssel. Anschließend die Anwendung
tatsächlich lokal gegen PostgreSQL gestartet (Wegwerf-Testkonto ohne Admin-Rolle, um die
1.3.34-2FA-Pflicht zu umgehen) und geprüft: Kundenliste (162 Kunden), ein Angebot als PDF
(225 KB), ein Einsatzbericht als PDF (2,7 MB inkl. Fotos), das verschlüsselte
Microsoft-365-Client-Secret weiterhin entschlüsselbar. Wichtigster Test: ein neuer Kunde per
`POST /api/customers` angelegt -- id=163, exakt der nächste freie Wert nach dem bisherigen
Maximum 162, bestätigt die zurückgesetzten Sequenzen unter echter Last, nicht nur rechnerisch.
Testkonto/-kunde danach wieder entfernt. **Bewusst NICHT in dieser Runde**: der Umzug auf den
Server selbst -- erst muss der Weg lokal tragen.
