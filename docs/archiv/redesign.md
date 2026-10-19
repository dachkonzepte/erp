# Redesign: Design-System „Schiefer & Signal“

Ab Stufe 1 (1.8.127) hier. Die Vorbereitung -- Stufen 0a bis 0d: Strukturtests für Basis-Templates und Makros, Bildgrundlage
`scripts/bildgrundlage.py` -- steht in `docs/archiv/testablauf-und-klicktests.md` (Abschnitte „Strukturtests …“ ab 1.8.123 und
„Bildgrundlage für das Redesign, Stufe 0d“).

## Stufe 1: Fundament (1.8.127)

Vorgabe vom 19.10.2026 (übernommen wie gegeben): „Stufe 1 des Redesigns: Fundament. Sichtbar ändert sich nichts. Vorab bestätigt:
Festlegungen 1.8.125 (alle) und 1.8.126 Nr. 12 und 13. 1. app/static/ als /static/ ausliefern: ohne Anmeldung, nur GET und HEAD, kein
Verzeichnislisting, keine Symlinks. Antworten 200 mit "Cache-Control: public, max-age=31536000, immutable"; die Ausnahme von Regel 30 gilt
nur dafür. 2. app/static/ds/ds.css: ds-tokens.css aus dem Projektordner mit unveränderten Werten übernehmen (die Datei danach entfernen),
dazu @font-face für Archivo 500/600/700, IBM Plex Sans 400/500/600 und IBM Plex Mono 400/500, selbst gehostet als woff2 (latin und
latin-ext), OFL-Lizenztexte daneben. 3. Baustein _ds_kopf.html mit <link> auf ds.css?v={{ app_version }}. Jede Seite aus seiten() bindet
ihn im <head> vor ihrem eigenen <style> ein, auch login. Die Akzentfarbe aus den Einstellungen bleibt unberührt. 4. Wächter: ds.css
enthält nur --ds-*-Eigenschaften in :root und :root[data-theme="dark"], @font-face und Selektoren mit .ds-. In app/static/ liegen nur
.css, .woff2 und Lizenztexte. Jede Seite bindet _ds_kopf.html ein. 5. Kontrasttest über die Prüfpaare im Kopfkommentar der Datei, hell und
dunkel. 6. Angriffstests ohne Anmeldung: /static/../…, %2e%2e, %2f, doppelt kodiert, Backslash, /staticx, /static ohne Schrägstrich,
POST, nicht vorhandene Datei. Keiner liefert etwas außer Design-Dateien oder kommt an der Anmeldung vorbei. Gegenprobe: Mit einer
absichtlich naiven Ausnahme (reiner Präfixvergleich) wird mindestens ein Test rot. 7. Klicktest: Auf der Anmeldeseite lädt
document.fonts.load alle drei Familien. 8. Bildvergleich gegen die Grundlage: 0 abweichende Pixel in allen 240 Bildern. Der Vergleich
bricht ab, wenn die Chrome-Versionen in bilder.json verschieden sind; dann die Grundlage auf 08b538c neu erzeugen.“

### Befund

- **Vorher**: kein `app/static/`, keine Auslieferung statischer Dateien; die Anmeldeschranke (`app/anmeldeschranke.py`) ließ ohne Anmeldung
  nur `/login`, `/health`, `/manifest.json` und `/api/auth/*` durch und setzte an jede Antwort an eine angemeldete Sitzung
  `Cache-Control: no-store` (Regel 30). Jede Seite trägt ihr CSS inline (eigener `:root`-Block, Theme-Skript davor).
- **Vorgabe `ds-tokens.css`** (unversioniert im Projektordner, sha256 `7bc9581f…`): nur `--ds-*` in `:root` und
  `:root[data-theme="dark"]`, Prüfpaare im Kopfkommentar -- 26 Paare Text ≥ 4,5 : 1, 8 Paare Bedienelemente/Rahmen ≥ 3 : 1. Vorab
  nachgerechnet: alle 34 halten hell und dunkel; am knappsten Feldrand auf Fläche hell 3,17, Signal und Fehler auf Fläche dunkel 3,18
  bzw. 3,16.
- **Schriftnamen**: keine Vorlage nennt Archivo oder IBM Plex in ihrem Schrift-Stapel -- die neuen `@font-face` laden auf den
  bestehenden Seiten nichts, die Bilder bleiben gleich.
- **`StaticFiles` (Starlette 1.6.0)**: normalisiert `..` selbst und weist Symlinks ab, die aus dem Ordner führen -- folgt aber solchen
  innerhalb; den Typ rät es über `mimetypes`. Der Wächter aus Regel 31 (`tests/test_v406…`) kennt `StaticFiles` nicht.
- **TestClient taugt nicht für Pfad-Angriffe**: httpx normalisiert `/static/../api/x` zu `/api/x` und dekodiert `%252e` doppelt --
  die Angriffstests rufen die App deshalb direkt über ASGI auf (path und raw_path wie uvicorn) und gegen einen echten uvicorn.

### Umsetzung 1.8.127

- **`app/design_dateien.py`**: `DesignDateien(StaticFiles)` -- `html=False` (ein Verzeichnis ergibt 404, kein Listing), keine Symlinks
  (weicht der aufgelöste Pfad vom zusammengesetzten ab, lag ein Symlink oder unter Windows eine Verzeichnisverbindung auf dem Weg: 404,
  auch innerhalb des Ordners), Typ fest nach Endung (`TYPEN`: `.css` → `text/css; charset=utf-8`, `.woff2` → `font/woff2`, `.txt` →
  `text/plain; charset=utf-8`, jede andere Endung 404), `X-Content-Type-Options: nosniff`; `FileResponse` ruft das Modul nicht selbst auf.
  `ist_design_pfad(scope)`: GET oder HEAD, Pfad `/static` und danach Abschnitte aus `[a-z0-9._-]` mit Buchstabe oder Ziffer am Anfang und
  Ende, kein `..`, und `raw_path` gleich dem dekodierten Pfad (nichts prozentkodiert). `einbinden(app)` hängt den Mount an -- `app/main.py`.
- **Anmeldeschranke**: nimmt `ist_design_pfad()` die Anfrage an, geht sie ohne Datenbank und ohne Sitzung durch (auch angemeldet wird die
  Sitzung nicht gelesen); Antwort 200 → `Cache-Control: public, max-age=31536000, immutable`, jede andere `no-store`; Schutzkopfzeilen wie
  immer. Alles andere unter oder neben `/static` (`/staticx`, `/static`, `/static/`, `..`, `%2e`, `%2f`, `%25…`, `\`, `//`, Großbuchstaben,
  Punkt am Ende) geht durch die Schranke wie jede Adresse.
- **`app/static/ds/ds.css`**: Kopfkommentar und Token-Blöcke aus der Vorgabe -- die Blöcke (3.790 Bytes, sha256 `bdefc4a8…`) und die
  Prüfpaare byte-gleich, nur die Kopfzeilen 3–8 nennen jetzt die Datei selbst statt „Vorgabe für“ und „und @font-face“. Danach 16
  `@font-face` (8 Schnitte × latin und latin-ext, `font-display: swap`, `unicode-range` aus den Paketen) und ein Kommentar zur Herkunft.
  `ds-tokens.css` aus dem Projektordner entfernt.
- **Schriften**: Fontsource 5.3.0 aus der npm-Registry (`@fontsource/archivo`, `@fontsource/ibm-plex-sans`, `@fontsource/ibm-plex-mono`,
  veröffentlicht 19.07.2026), sha512 der Registry geprüft, entpackt nur die 16 woff2 (jede beginnt mit `wOF2`) und die Lizenz; Lizenztexte
  `ofl-archivo.txt`, `ofl-ibm-plex-sans.txt`, `ofl-ibm-plex-mono.txt` (SIL OFL 1.1 mit den Copyright-Zeilen der Pakete) daneben in
  `app/static/ds/schriften/` -- kleingeschrieben, damit sie ohne Anmeldung erreichbar sind.
- **`app/templates/_ds_kopf.html`**: `<link rel="stylesheet" href="/static/ds/ds.css?v={{ app_version }}">`; in allen 53 Seiten aus
  `seiten()` direkt vor dem ersten `<style>` eingebunden (in 52 nach dem Theme-Skript; in 11 stand das `<style>` mitten in einer Zeile,
  dort mit Zeilenumbruch davor; `checklist.html` schließt den Kopf ohne `</head>`).
- **Bildgrundlage**: `vergleichen` bricht bei verschiedenen Chrome-Versionen ab (Rückgabecode 2), siehe Nachtrag im Archiv der Tests.
- **Klicktest** `scripts/klicktest_ds_schriften.py`.

#### Festlegungen 1.8.127 (Nr. 1–10 und 12–13 bestätigt am 19.10.2026; Nr. 11 ersetzt durch 1.8.129 Nr. 4)

1. **Schriftquelle**: Fontsource 5.3.0 (npm, Prüfsumme der Registry), statische Schnitte je Teilbereich latin und latin-ext, Dateinamen wie
   bei Fontsource, `font-display: swap`.
2. **Lizenztexte** je Paket als `ofl-<familie>.txt` (drei Dateien, Archivo, IBM Plex Sans, IBM Plex Mono), kleingeschrieben.
3. **Pfadregel der Ausnahme**: GET/HEAD, `/static` plus Abschnitte aus `[a-z0-9._-]` (Anfang und Ende Buchstabe oder Ziffer), kein `..`,
   keine Prozent-Kodierung; alles andere geht durch die Schranke -- auch eine echte Design-Datei mit Großbuchstaben oder kodiertem Pfad.
4. **Cache**: nur eine Antwort 200 trägt `public, max-age=31536000, immutable`, jede andere unter der Ausnahme `no-store`; eine geänderte
   Datei bekommt eine neue Adresse (ds.css über `?v=<Version>`, eine Schrift über einen neuen Namen).
5. **Ohne Datenbank**: eine Design-Datei liest weder Konten noch Sitzung, auch nicht für Angemeldete.
6. **Symlinks**: jeder Symlink oder jede Verzeichnisverbindung auf dem Weg ergibt 404, auch wenn das Ziel im Ordner liegt.
7. **Typen fest nach Endung** (`.css`, `.woff2`, `.txt`), jede andere Endung 404, auch wenn die Datei da ist; immer `nosniff`.
8. **Schreibende Methoden**: ohne Anmeldung 403 (fremder Ursprung) bzw. 401 durch die Schranke, angemeldet 405 aus `StaticFiles`.
9. **Kopfkommentar von ds.css**: Zeilen 3–8 an die Datei angepasst, Werte und Prüfpaare byte-gleich zur Vorgabe.
10. **Einbindung**: `_ds_kopf.html` direkt vor dem ersten `<style>` der Seite (nach dem Theme-Skript), `?v={{ app_version }}` wie
    vorgegeben (nicht URL-kodiert).
11. ~~**Wächter ds.css**~~ (ersetzt durch 1.8.129 Nr. 4) (nur Test): „Selektor mit .ds-“ heißt, jeder Selektor einer Liste enthält `.ds-`, die Eigenschaften dort sind frei;
    `@font-face` nur mit den sechs Eigenschaften `font-family`, `font-style`, `font-weight`, `font-display`, `src`, `unicode-range`; keine
    andere At-Regel, nichts verschachtelt.
12. **Kontrasttest** (nur Test): Prüfpaare aus dem Kopfkommentar; ein Token, das dunkel nicht gesetzt ist, erbt von `:root`; WCAG-2-
    Leuchtdichte.
13. **Bildvergleich** (nur Test): verschiedene Chrome-Versionen → Abbruch mit 2; ohne `bilder.json` nur ein Hinweis.

#### Nebenbefunde (nur gemeldet)

1. **HEAD und OPTIONS** auf geschützte Pfade gehen ohne Anmeldung durch die Schranke (`_request_requires_login()`/`_page_requires_login()`
   gelten nur für GET und schreibende Methoden) und bekommen vom Routing 405 bzw. 404 -- ohne Daten (gemessen an `/api/customers`,
   `/projects`, `/customers/1`). So schon vor 1.8.127, nicht geändert. **Seit 1.8.128 behoben** (Runde 1b): die Schranke gilt
   für jede Methode; der Befund dort fand mehr -- die Doku-Routen von FastAPI beantworteten HEAD mit 200
   (`docs/archiv/serverbetrieb-und-anmeldesicherheit.md`, „Anmeldepflicht für jede Methode“).
2. **Mit einem reinen Präfixvergleich** kämen 23 der 29 Angriffsanfragen an der Anmeldung vorbei (`/staticx…`, `/static`, `..`, kodierte
   Pfade, Großbuchstaben); Daten flössen trotzdem keine, weil `StaticFiles` im Ordner bleibt -- die enge Regel ist die erste Mauer, nicht
   die einzige.

#### Grenzen

- Sichtbar ändert sich nichts: keine Seite nutzt die Tokens oder Schriften (Bildvergleich), die Akzentfarbe bleibt `--accent` aus den
  Einstellungen.
- Ob Nginx vor `/static/` eigene Cache- oder Sicherheitskopfzeilen setzt oder `/static/` selbst ausliefert, ist Sache des Servers -- die
  Anwendung liefert alles selbst aus, nichts in der Nginx-Konfiguration nötig (Betreiberprüfung beim Einspielen).
- Fonts im Browser-Cache ein Jahr: eine neue Fassung einer Schrift braucht einen neuen Dateinamen und eine neue Zeile in `ds.css`.

#### Tests und Prüfung

- Neu `tests/test_v432_design_fundament.py` (61 Tests):
  - **Auslieferung**: ds.css, eine Schrift und ein Lizenztext ohne Anmeldung mit festem Typ, langem Cache, nosniff und ohne
    Datenbanksitzung (gezählt); angemeldet ebenso (die Sitzung bekommt anderswo weiter `no-store`); HEAD ohne Inhalt; Verzeichnisse und
    fehlende Dateien 404 ohne Listing, auch angemeldet; angemeldet POST 405; eigener Ordner mit Symlink auf eine Datei (wenn Windows ihn
    erlaubt), Verzeichnisverbindung auf ein Verzeichnis im Ordner, `.html` und `.svg` → 404.
  - **Angriffe**: 29 rohe Anfragen (Design-Dateien, fehlende Datei, Verzeichnis, `..`, `%2e%2e`, `%2E%2E`, `..%2f`, `%2f`, `%252e`,
    `%252f`, Rückstrich, `/staticx`, `/static`, `/static/`, `//`, `/./`, Großbuchstaben, Punkt am Ende, `::$DATA`) -- direkt über ASGI
    (path und raw_path wie uvicorn) und gegen einen echten uvicorn mit h11 und httptools (rohe Anfragezeilen): jede ist die Design-Datei
    selbst (Inhalt byte-gleich, Typ, Cache), 404 auf einem Design-Pfad oder die Anmeldung (302 auf `/login` bzw. 401); kein Inhalt eines
    geschützten Kunden in irgendeiner Antwort. Am echten Server kam keine einzige 400 -- beide Parser liefern dasselbe wie der ASGI-Aufruf.
    Schreibende Methoden ohne Anmeldung: 403 ohne eigene Seite, 401 mit. `ist_design_pfad()` an 16 Fällen.
  - **Wächter**: ds.css nur Tokens, `@font-face` und `.ds-` (dazu 11 Fixture-Verstöße und ein Durchlass-Fall); `app/static/` nur CSS,
    echte woff2 (alle in ds.css verwendet), OFL-Texte je Familie, keine Symlinks, jeder Name ohne Anmeldung erreichbar; 16 Schriftflächen
    (8 Schnitte × 2 Teilbereiche); jede der 53 Seiten bindet `_ds_kopf.html` ein, ds.css genau einmal im Kopf vor dem eigenen Stilblock
    (Fixture: zu spät, ohne); `_ds_kopf.html` nur der eine Link; `StaticFiles` nur in `app/design_dateien.py`; `app/main.py` hängt
    `DesignDateien` an `/static`.
  - **Kontrast**: 34 Prüfpaare, hell und dunkel; Gegenprobe (zu helles `text-3`, zu dunkles `fehler` dunkel, fehlendes Token).
- **Gegenprobe Präfixvergleich**, zweifach: im Test (naive Ausnahme per monkeypatch, die Tabelle wird rot) und nach Regel 24 im Code --
  `ist_design_pfad()` mit Marker als `path.startswith("/static")`: 16 Tests rot (Angriffe über ASGI, beide echten Server, 13 Fälle der
  Pfadprüfung); die Datei danach byte-genau zurück (sha256 `e67af23a…` vorher wie nachher), kein Marker unter `app/`. Mit dem
  Präfixvergleich kämen 23 der 29 Anfragen an der Anmeldung vorbei.
- `tests/test_v431_bildgrundlage.py`: zwei neue Tests (verschiedene Chrome-Versionen → 2 ohne Differenzbilder; gleiche → Vergleich).
- `tests/test_v328_navigation_ohne_sperrseiten.py`: neu `test_design_dateien_nur_wenn_vorhanden` (7 Fälle).
- **Klicktest** `klicktest_ds_schriften.py`: 27 von 27 (Anmeldeseite, Tokens hell und dunkel, Akzentfarbe `#0d9488` unverändert,
  `document.fonts.load` für 8 Schnitte je latin und latin-ext, `document.fonts.check` für alle, 16 woff2 mit 200, Kopfzeilen von woff2
  und ds.css). Erster Lauf 26 von 27: der Test las `--ds-grund` „hell“, während die Seite dem dunklen Farbschema des Systems folgte --
  seither setzt er das Thema ausdrücklich.
- **Bildvergleich gegen `08b538c`** (Arbeitsstand, Chrome 155.0.8059.40 wie die Grundlage): 240 gleich, 0 abweichende Pixel; ds.css kam
  im ganzen Lauf einmal vom Server (200), danach aus dem Browser-Cache. Am Commit wiederholt (Bericht).
- **Angepasste Tests** (Regel 28): `test_v328::test_jeder_link_im_code_fuehrt_auf_eine_vorhandene_route` -- Soll „jedes Link-Ziel führt
  auf eine vorhandene GET-Route“ wird „… oder auf eine vorhandene Design-Datei unter `/static/`“ (der Mount ist keine GET-Route; das
  `href` von `_ds_kopf.html` war das einzige neue Ziel); Aufbau: `_fuehrt_auf_design_datei()`.

## Runde 1b: Anmeldepflicht für jede Methode (1.8.128)

Sicherheitsrunde vor Stufe 2 -- die Herleitung steht beim Thema Schranke: `docs/archiv/serverbetrieb-und-anmeldesicherheit.md`,
„Anmeldepflicht für jede Methode (seit 1.8.128)“. Dazu hier: ein Wächter hält jeden Namen in `app/static/` beim Muster der
Design-Ausnahme (`tests/test_v433_schranke_alle_methoden.py`).

## Runde 1c: Härtung vor Stufe 2 (1.8.129)

Vorgabe vom 19.10.2026 (übernommen wie gegeben): „Runde 1c (Härtung, vor Stufe 2). Vorab bestätigt: 1.8.127 Nr. 12–13; 1.8.128 Nr. 1–3, 5,
7–9. 1.8.127 Nr. 11 wird durch Punkt 4 ersetzt, 1.8.128 Nr. 6 durch Punkt 3, Nr. 4 bleibt offen (Punkt 1). 1. Befund Ersteinrichtung,
nichts ändern: Woran erkennt die Schranke „noch kein Konto“? Was passiert, wenn diese Abfrage scheitert (Datenbank nicht erreichbar,
Fehler in der Abfrage)? Was ist in diesem Zustand ohne Anmeldung erreichbar, und wer kann dann das erste Konto anlegen? 2. /docs, /redoc und
/openapi.json im Betrieb abschalten, lokal per Einstellung verfügbar. Nenne den Schalter. Test: im Betriebsmodus 404, auch mit Anmeldung.
3. /health beantwortet auch HEAD. 4. Wächter ds.css schärfen: Das Ziel jedes Selektors (sein letzter Teil) trägt eine .ds-Klasse; `.ds-x
div` oder `.ds-x + p` sind verboten. Gegenprobe mit Fixture. 5. Befund Akzentfarbe, nichts ändern: Wo wirkt accent_color überall (Seiten,
PDFs, E-Mails, Manifest, Logo)? Wer kann sie ändern? Bericht wie bisher, neue Festlegungen wörtlich, committen, nicht pushen.“

### Befund 1: Ersteinrichtung (nichts geändert)

- **Erkennung**: `app/auth.py::users_exist()` -- `SELECT app_users.id … LIMIT 1`, je Anfrage in `_lesen()` der Schranke. Jede Zeile zählt,
  auch ein deaktiviertes Konto. Über Oberfläche und API kommt der Zustand nicht zurück: das letzte aktive Admin-Konto lässt sich weder
  löschen noch deaktivieren oder herabstufen, das eigene Konto nicht löschen (`app/routers/users.py`). Leer ist die Tabelle nur in einer
  neuen oder geleerten Datenbank (Neuaufsetzen, Migration ohne Datenübernahme, Eingriff von Hand).
- **Wenn die Abfrage scheitert**: die Schranke schließt. Ein Fehler der Datenbank oder der Abfrage (z. B. `OperationalError`) geht aus der
  Middleware an den Fehler-Handler -- 500 mit Schutzkopfzeilen, nichts aus dem Fehler (`serverfehler()`); ein leerer Pool -- 503
  („ausgelastet“, `PoolLeer`). Gemessen an der echten Schranke für `/api/customers`, `/projects`, `/health`, `/login`. Offen ist die
  Ersteinrichtung nur, wenn die Abfrage gelingt und keine Zeile findet. (Design-Dateien fragen die Datenbank nicht und gehen auch dann.)
- **Erreichbar ohne Anmeldung im leeren Zustand**: die Schranke lässt jede Methode auf jedem Pfad durch (`has_users` falsch), dahinter
  aber weist jede Rollenprüfung ab (`require_min_role()` ohne Benutzer: 403; gemessen `/api/customers`, `/projects`). Offen ist, was keine
  Rollenprüfung hat: `GET /users` (Seite zum Anlegen), `GET /api/auth/status` (meldet `"configured": false`), `POST /api/auth/login`,
  `/logout`, `/health`, `/manifest.json`, die Design-Dateien, bis 1.8.128 auch die Schnittstellen-Doku (`/openapi.json` mit allen Pfaden;
  seit 1.8.129 im Betrieb nicht mehr angelegt) -- und `POST /api/users`.
- **Wer das erste Konto anlegt**: jeder, der den Server erreicht -- `POST /api/users` prüft die Admin-Pflicht erst, wenn schon ein Konto
  existiert; das erste Konto wird immer Admin, auch wenn eine andere Rolle verlangt wird (gemessen: Rolle `field` verlangt, `admin`
  angelegt). Die Ursprungsprüfung (Regel 33) hält einen Browser auf einer fremden Seite ab, kein Skript. Danach ist der Zustand vorbei
  (`configured: true`). Ein frisch aufgesetzter, schon erreichbarer Server ist also bis zum ersten Konto offen -- 1.8.128 Nr. 4 bleibt
  offen.

### Befund 5: Akzentfarbe (nichts geändert)

- **Gespeichert**: `GeneralSettings.accent_color` (Vorgabe `#0d9488`); gelesen über `app/settings.py::get_accent_color()`.
- **Wirkt**: in allen 53 Seiten als `--accent` im eigenen `:root` (`{{ get_theme().accent_color }}`, aus den Seitendaten der Schranke,
  Rückfall `#0d9488`), auch auf der Anmeldeseite vor dem Anmelden; im Web-App-Manifest der Monteursansicht als `theme_color`
  (`/manifest.json`, ohne Anmeldung) und als Hintergrund der PWA-Symbole (`/api/mobile-icon/{size}.png`, Firmenlogo darauf,
  `app/mobile_manifest.py`). **Nicht**: PDFs, E-Mails, das Firmenlogo selbst (`app/company_logo.py`), `ds.css`.
- **Ändern**: `PUT /api/settings/appearance` ab Büro – Auftrag (`_role_dep` in `app/routers/settings.py`: Büro – Auftrag, Büro – Finanzen,
  Admin); in der Oberfläche unter Einstellungen → Firma → Erscheinungsbild, nicht auf Admins beschränkt. Nur `#rrggbb` (Schema-Muster),
  ein Hinweis bei weißer Schrift unter 3 : 1, keine Sperre. Gilt sofort für alle Benutzer.

### Umsetzung 1.8.129

- **Schnittstellen-Doku**: `app/main.py::api_doku_aktiv()` -- Schalter **`ERP_API_DOKU=1`**, wirksam nur mit `ERP_ENV=development` oder
  `test`. Sonst legt FastAPI `/docs`, `/redoc`, `/docs/oauth2-redirect` und `/openapi.json` gar nicht an (`docs_url`, `redoc_url`,
  `openapi_url` = None): angemeldet 404, ohne Anmeldung leitet die Schranke vorher auf `/login` um. In `.env.example` beschrieben.
- **`/health`**: `@router.api_route("/health", methods=["GET", "HEAD"])` -- HEAD 200 ohne Inhalt, ohne Anmeldung.
- **Wächter ds.css** (`tests/test_v432_design_fundament.py`): das Ziel jedes Selektors (der letzte Teil nach Leerraum, `>`, `+`, `~`, Kommas
  und Kombinatoren nur außerhalb von Klammern und Anführungszeichen) trägt selbst eine Klasse `.ds-…`; was in `(…)` oder `[…]` steht, zählt
  nicht. Funde „Ziel ohne .ds-Klasse“; „Selektor ohne .ds-“ wie bisher.

#### Festlegungen 1.8.129 (Bitte bestätigen)

1. **Schalter `ERP_API_DOKU=1`**, wirksam nur zusammen mit `ERP_ENV=development` oder `test`; im Betrieb (`production`, fehlend, jeder andere
   Wert) nie -- die Doku-Routen werden nicht angelegt (angemeldet 404, ohne Anmeldung vorher die Umleitung auf `/login`).
2. **Lokal ohne Schalter ebenfalls aus**: `start_windows.bat` setzt ihn nicht; wer die Doku lokal braucht, setzt `ERP_API_DOKU=1`.
3. **`/health` mit GET und HEAD** (ersetzt 1.8.128 Nr. 6 für `/health`); `/login`, `/manifest.json` und `/api/auth/status` beantworten HEAD
   weiter mit 405.
4. **Wächter ds.css** (ersetzt 1.8.127 Nr. 11): eine Regel außer `:root`, `:root[data-theme="dark"]` und `@font-face` braucht Selektoren,
   deren Ziel -- der letzte Teil nach Leerraum, `>`, `+` oder `~` -- selbst eine Klasse `.ds-…` trägt; was in `(…)` oder `[…]` steht, zählt
   nicht (`div:not(.ds-x)`, `[class~=ds-x]` sind verboten); Pseudoklassen und -elemente am Ziel sind erlaubt (`.ds-x:hover`,
   `.ds-feld::placeholder`), die Eigenschaften dort frei. Unverändert aus Nr. 11: `@font-face` nur mit `font-family`, `font-style`,
   `font-weight`, `font-display`, `src`, `unicode-range`; keine andere At-Regel; nichts verschachtelt.
5. **Betriebsmodus-Test** (nur Test): im Kindprozess startet `app.main` mit `ERP_ENV=production` und `ERP_API_DOKU=1` auf einer eigenen
   Wegwerf-SQLite (Tabellen und Grunddaten vorher angelegt, weil der Betrieb sie nicht anlegt), angemeldet über die Cookie-Kopfzeile (im
   Betrieb ist das Cookie Secure, der Test spricht http).

#### Nebenbefunde (nur gemeldet)

1. **Akzentfarbe ab Büro – Auftrag änderbar** -- eine zentrale Einstellung für alle Benutzer, die nach der Ordnung von 1.8.112 („nur Admin
   speichert“) eher beim Admin läge; nicht geändert (Befund 5).
2. **`/api/mobile-icon/{size}.png`** steht in `ROLE_AUDIT_EXEMPT` mit der Begründung „muss vor dem ersten Login erreichbar sein“, liegt aber
   als `/api/`-Pfad hinter der Schranke (ohne Anmeldung 401, so schon vor 1.8.128); `/manifest.json` dagegen ist öffentlich. Die
   Installation aus `/mobil` heraus geschieht angemeldet und funktioniert; die Begründung im Kommentar stimmt nicht.
3. **`GET /api/auth/status` meldet ohne Anmeldung `configured`** -- im leeren Zustand verrät das jedem, dass das erste Konto noch fehlt.

#### Tests und Prüfung

- Neu `tests/test_v434_haertung.py` (15 Tests): Schalter an zehn Umgebungen; `app.main` legt die Doku nur mit Schalter an; Kindprozess im
  Betriebsmodus mit Schalter: `/docs`, `/redoc`, `/docs/oauth2-redirect`, `/openapi.json` angemeldet GET und HEAD 404, ohne Anmeldung 302,
  die Anmeldung selbst gilt; lokal ohne Schalter 404; Gegenstück lokal mit Schalter 200 (GET und HEAD) -- der Kindprozess misst also
  wirklich die Doku; `/health` gegen echten uvicorn: HEAD 200 ohne Inhalt, GET 200, OPTIONS 401, HEAD auf `/login` 405.
- `tests/test_v432_design_fundament.py`: Wächter mit Ziel-Regel; neu 15 Verbotsfälle (`.ds-x div`, `.ds-x + p`, `.ds-x > span`,
  `.ds-x ~ a`, `.ds-x *`, `div:not(.ds-x)`, `div:has(.ds-x)`, `:is(.ds-a, .ds-b) p`, `[class~=ds-b]` …) und 11 erlaubte Fälle, dazu die
  Hilfsfunktionen. **Gegenprobe**: alle 15 Verbotsfälle hätte die alte Regel durchgelassen.
- **Angepasste Tests** (Regel 28): `test_v432::css_verstoesse` (und damit `test_ds_css_nur_tokens_schriften_und_ds_klassen`) -- Soll „jeder
  Selektor enthält `.ds-`“ wird „das Ziel jedes Selektors trägt eine `.ds-`-Klasse“ (Vorgabe Punkt 4); die bisherigen Fixture-Erwartungen
  bleiben unverändert.
- `test_v328::test_jeder_link_im_code_fuehrt_auf_eine_vorhandene_route` -- Aufbau: die Argumente des Konstruktors `FastAPI(…)`
  (`docs_url`, `redoc_url`, `openapi_url`) zählen nicht als Link-Ziele (sie legen Routen an, die es nur mit dem Schalter gibt; seit
  1.8.129 stehen sie in `app/main.py`); das Soll „jedes Link-Ziel führt auf eine vorhandene Route“ bleibt. Neu
  `test_links_aus_code_ohne_konstruktor_von_fastapi` (dasselbe Argument außerhalb des Konstruktors bleibt ein Link-Ziel).
