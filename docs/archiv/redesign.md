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

#### Festlegungen 1.8.129 (Nr. 1–5 bestätigt am 19.10.2026)

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
   speichert“) eher beim Admin läge; nicht geändert (Befund 5). *Seit 1.8.130 nur Admin.*
2. **`/api/mobile-icon/{size}.png`** steht in `ROLE_AUDIT_EXEMPT` mit der Begründung „muss vor dem ersten Login erreichbar sein“, liegt aber
   als `/api/`-Pfad hinter der Schranke (ohne Anmeldung 401, so schon vor 1.8.128); `/manifest.json` dagegen ist öffentlich. Die
   Installation aus `/mobil` heraus geschieht angemeldet und funktioniert; die Begründung im Kommentar stimmt nicht. *Seit 1.8.130
   öffentlich (GET, HEAD), der Kommentar stimmt.*
3. **`GET /api/auth/status` meldet ohne Anmeldung `configured`** -- im leeren Zustand verrät das jedem, dass das erste Konto noch fehlt.
   *Seit 1.8.130 ohne Konto nicht mehr erreichbar (503); die Hinweisseite sagt es dort absichtlich selbst.*

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

## Runde 1d: Ersteinrichtung geschlossen, Akzentfarbe nur Admin, PWA-Symbole öffentlich (1.8.130)

Sicherheitsrunde vor Stufe 2 -- Vorgabe, Umsetzung, Festlegungen 1.8.130 und Tests stehen beim Thema Schranke:
`docs/archiv/serverbetrieb-und-anmeldesicherheit.md`, „Ersteinrichtung geschlossen (seit 1.8.130)“. Für das Redesign: die Hinweisseite
der Ersteinrichtung ist die erste Seite außerhalb der Vorlagen, die nur das Design-System nutzt (`ds.css`, Tokens `--ds-…`, keine eigenen
Farben); der Bildvergleich gegen die Grundlage `08b538c` steht dort unter „Bildvergleich“.

## Stufe 2a: Bildgrundlage erweitert (1.8.131)

Die Bildgrundlage nimmt die Seiten der Monteurin zusätzlich auf dem TerraPad auf (800 und 1280 px) und fünf Zustände des Rahmens (Menü
aufgeklappt, Seitenleiste eingeklappt, Kontomenü offen, Seitenleiste ganz unten, Seitenleiste von Büro – Auftrag) -- 304 statt 240 Bilder
je Lauf. Vorgabe, Befund, Festlegungen 1.8.131 und Tests: `docs/archiv/testablauf-und-klicktests.md`, „Bildgrundlage erweitert, Stufe 2a“.

## Fehlerrunde vor Stufe 2 (1.8.132 ff.)

Vorgabe vom 19.10.2026 (übernommen wie gegeben): „Fehlerrunde vor Stufe 2. Nur diese Punkte, kein Design, sonst nichts ändern. Beheben, je Punkt ein Test, der vorher scheitert und danach besteht: 1. Anfragen: „Projekt öffnen“ führt auf /projects?project_id=…, die Liste wertet den Parameter nicht aus. Ziel: direkt die Projektmappe. Nach „Projekt + Angebot erzeugen“ direkt ins neue Angebot. 2. LV-Editor und Auftrag: Spalte Gesamtpreis/EP läuft rechts aus der Tabelle. Ziel: kein Überlauf bei 1440 und 1280 px. 3. /users als Büro: Fehlermeldung statt Liste, trotzdem Formular „Benutzer hinzufügen“. Ziel: jede Rolle sieht nur, was sie darf. Satz „Der erste angelegte Benutzer wird automatisch Administrator“ entfernen. 4. Zurück-Links in Neues Projekt („← Projekte & Belege“), Neues Angebot, Stammdaten-Formular, Leistung bearbeiten: echtes Ziel mit echtem Namen statt history.back(). 5. LV-Editor: „Auftrag öffnen“ und „Auftrag AUF-… öffnen“ → ein Knopf. 6. Zeiterfassung (Büro): „+ Manuell buchen“ und „+ Zeitbuchung anlegen“ → ein Knopf. 7. Änderungshistorie: lesbare Namen statt technischer (WorkPreparationTeamEmployee, property_address, entwurf → beauftragt), Blättern statt bis zu 500 Einträgen. 8. Seitentitel einheitlich „DACHKONZEPTE ERP – <Seite>“, ohne Versionsnummer (u. a. „Anfragen & Pipeline 0.6“, Leistungskatalog „– Version“). 9. Leistung bearbeiten: „Standard: 0.0000%“ → „0 %“. 10. Finanzen: Platzhalter „Weitere buchhalterische Themen folgen hier künftig.“ entfernen. Nur Befund, nichts ändern: 11. Einsatzbericht als Monteurin zeigt bei Zeit buchen die Auswahl „Mitarbeiter“. Kann eine Monteurin über Oberfläche oder API für andere buchen, auch außerhalb ihrer Kolonne? Welche Endpunkte, welche Rollenprüfung? Mit Angriffstest und Gegenprobe. Entscheidung steht: Monteure buchen nur für sich und ihre Kolonne, Umsetzung in der nächsten Runde. Am Ende: volle Suite, Bericht je Punkt (Ursache, Datei, Änderung, Test). Ein Commit je Punkt, nicht pushen.“

Anlass ist der Befund Seiten-Inventar vom 19.10.2026 (`bildgrundlage/pruefung/`, außerhalb von Git). Tests: `tests/test_v436_fehlerrunde_vor_stufe_2.py`, je Punkt ein Abschnitt; jeder Test scheiterte am Stand davor (geprüft, indem die Datei des Punkts auf den alten Stand zurückgesetzt wurde). Die volle Suite läuft nach der Vorgabe einmal am Ende der Runde, nicht vor jedem Commit (Regel 15).

### Punkt 1 (1.8.132): Anfragen

- **Ursache**: `inquiries.html::openLinkedProject()` navigierte auf `/projects?project_id=<id>`; `projects.html` liest keinen Parameter aus der Adresse. `convertInquiry()` setzte nach dem Umwandeln nur die Statuszeile.
- **Änderung**: „Projekt öffnen“ → `/projects/<id>`; nach „Projekt + Angebot erzeugen“ → `/quotes/<id>/edit` (ohne Angebot `/projects/<id>`), IDs über `Number()`.
- **Test**: `test_anfrage_projekt_oeffnen_fuehrt_in_die_projektmappe`, `test_nach_projekt_und_angebot_erzeugen_ins_neue_angebot` (node, Seitenskript mit Attrappe aus `test_v334`): vorher `/projects?project_id=7` bzw. leer, jetzt `/projects/7` bzw. `/quotes/9/edit`.

### Punkt 2 (1.8.133): Preisspalten im LV

- **Ursache**: `quote_editor.html` -- `.lv-columns,.lv-item` mit festen Spalten (28 84 minmax(250,1fr) 92 100 112 120 82 px + Abstände, rund 920 px), Seitenraster `minmax(760px,1.9fr) minmax(390px,.72fr)`; `order.html` -- `.lv-head,.lv-row` (85 minmax(240,1fr) 95 90 110 115 55 px, rund 850 px), Seitenraster `minmax(680px,1fr) 390px`. Bei 1440 px blieben für das LV rund 736 bzw. 720 px; bei 1280 px war das Seitenraster selbst zu breit (Seite 60 px breiter als das Fenster). Dazu schnitt die Aktionsspalte (82 px) den Knopf „Bearbeiten“ (106 px) ab.
- **Änderung**: Spalten mit `minmax()` (LV-Editor: OZ 48–84, Leistung ab 120, Menge 70–92, Einheit 76–100, Einheitspreis 84–112, Gesamtpreis 120, Aktionen ab 106 px; Auftrag: OZ 44–85, Leistung ab 110, Menge 60–95, EH 60–90, EP 72–110, GP 108–115, Bearbeiten 36–55 px); linke Spalte des Seitenrasters `minmax(0,…)`; LV-Editor einspaltig bis 1380 px (neue Regel vor der bestehenden bis 1200 px, Katalog unter dem LV wie dort). Keine andere Gestaltung geändert.
- **Test**: Klicktest `scripts/klicktest_lv_ueberlauf.py` (13 Prüfungen: LV-Editor und Auftrag bei 1440 und 1280 px, Desktop, mit großen Beträgen 12.345,678 m² × 1.234,56 € = 15.241.480,23 €) -- jede Zelle endet in ihrer Karte, Preiszellen nicht abgeschnitten, Seite ohne waagerechten Bildlauf. Vorher 9 von 13 (alle vier Überlauf-Prüfungen rot, bis 180 px außerhalb), danach 13 von 13. Ein Klicktest, weil sich ein Überlauf nur im Browser messen lässt.
- **Nicht geändert** (nur gesehen): zwischen 1001 und rund 1130 px gilt im LV-Editor weiter die feste Spaltenregel für bis 1200 px (rund 850 px, Aktionen 76 px) -- dort dürfte es weiter überlaufen; außerhalb der Vorgabe (1440 und 1280 px). Der Auftrag zeigt Menge und EP ohne Tausenderpunkt („12345,6“, „1234,56“).

### Punkt 3 (1.8.134): Benutzerverwaltung

- **Ursache**: `app/routers/pages.py::users_page` mit `require_min_role(ROLE_OFFICE_AUFTRAG)` (Stand seit 1.8.130, vorher die Ausnahme der Ersteinrichtung), `GET`/`POST /api/users` dagegen `require_admin`; `users.html` lädt Status, Liste und Mitarbeiter in einem `Promise.all` -- für das Büro scheiterte die Liste, `authInfo` zeigte den Fehler, das Formular `editorCard` blieb im Markup (ausgeblendet nur per Skript nach erfolgreichem Laden). Der Satz zur Ersteinrichtung (`#hint`) stammte aus der Zeit vor 1.8.130.
- **Änderung**: Seite mit `require_admin("Die Benutzerverwaltung ist nur für Administratoren verfügbar.")`, Büro und Monteur sehen die Sperrseite; Absatz `#hint` entfernt. `scripts/bildgrundlage.py`: Aufnahme „benutzer“ mit Rolle Admin statt Büro (die Grundlage `2d4c37b` hat diese Bilder noch als Büro; die nächste Grundlage nimmt sie als Admin auf).
- **Test**: `test_benutzerseite_nur_fuer_admins` (Büro – Finanzen, Büro – Auftrag, Monteur 403 ohne Formular; Admin 200 mit Formular), `test_satz_zur_ersteinrichtung_entfernt` -- vorher beide rot (Büro 200, Satz vorhanden).
- **Angepasste Tests** (Regel 28):
  - `test_v260::TestPageRouteClassification::test_users_page_buero_only_also_without_any_account` → `test_users_page_admin_only_also_without_any_account`: Soll „Büro – Auftrag 200“ (ohne und mit Konto in der Datenbank) → 403, dazu Büro – Finanzen 403 und Admin 200.
  - `test_v435::test_benutzerseite_und_konto_anlegen_mit_rollen`: Soll „Bernd (Büro – Finanzen) und Berta (Büro – Auftrag) 200 auf /users“ → 403.
  - `test_v431::test_namen_und_rollen`: Soll der Seiten ohne Büro-Rolle um `users.html` ergänzt (die Aufnahme „benutzer“ ist jetzt Admin); `test_jede_adresse_zeichnet_ihre_vorlage` dadurch unverändert grün.
  - **Nachtrag** (gefunden im Endlauf der Runde auf `d1c2ab9`, Regel 26): `test_v419_verbindungen_unter_last.py::test_viele_gleichzeitige_seiten_und_abfragen` (nur gegen PostgreSQL, in den Teilläufen zu Punkt 3 nicht dabei) rief `/users` als Büro – Finanzen auf und erwartete 200 -- Soll jetzt 403 für `/users` (`ERWARTET`), alle anderen Seiten und Abfragen weiter 200; die Sperrseite wird unter Last ebenso gezeichnet. Dazu Regel 30 in CLAUDE.md berichtigt (dort stand noch „`/users` ab Büro – Auftrag“). Eigener Commit „1.8.134 (Nachtrag)“, danach Suite und Klicktests neu.

#### Festlegungen 1.8.134 (Bitte bestätigen)

1. **`/users` nur für Administratoren** -- wie Liste und Anlegen; Büro und Monteur bekommen die Sperrseite (statt einer Seite mit Fehlermeldung und Formular). Das Büro erreicht die Seite über keinen Link (Einstellungen zeigen „Benutzer und Zugriff“ nur Admins).

### Punkt 4 (1.8.135): Zurück-Links

- **Ursache**: `project_form.html`, `quote_form.html`, `master_data_form.html`, `service_form.html` -- `<a class="back" href="#" onclick="history.back();return false">` mit festen Namen „Projekte & Belege“, „Angebote“, „Stammdaten“, „Leistungskatalog“; die Seiten haben keine Seitenleiste, der Link ist der einzige Weg zurück.
- **Änderung**: `app/routers/pages.py` gibt jeder dieser Seiten `zurueck = {href, text}` mit (`_zahl()`: nur Ziffern, sonst das allgemeine Ziel; `STAMMDATEN_BEREICHE`, `zurueck_stammdaten()`): `/projects/new` → `/projects` „Projekte“ bzw. mit `customer_id` `/customers/<id>` „Kundenakte“; `/quotes/new` → `/projects` bzw. mit `project_id` `/projects/<id>` „Projektmappe“; Stammdaten-Formular → `/master-data#<Bereich>` „Stammdaten: <Name des Bereichs>“ (Ressourcen: Bereich `assets`, „Fuhrpark & Maschinen“ -- so heißt er nur bei abgeschaltetem Modul Betriebsmittel, und nur dann gibt es Ressourcen dort), Objekt bearbeiten → `/properties/<id>` „Objekt“, Kontakt neu mit `projekt` → `/projects/<id>#sec-participants` „Projektmappe“ (dorthin führt auch das Speichern); Leistung → `/leistungskatalog`. Die Vorlagen: `href="{{ zurueck.href }}">← {{ zurueck.text }}`.
- **Test**: `test_zurueck_link_mit_echtem_ziel` (13 Fälle: Adresse → Ziel und Name, kein onclick), `test_kein_history_back_in_den_formularseiten`, `test_zurueck_ziele_fuehren_auf_seiten` -- vorher 13 von 14 rot (der letzte prüft nur, dass die Ziele Seiten sind).
- **Nicht geändert** (nur gesehen): `users.html` hat dasselbe Muster („← Einstellungen“ per `history.back()`), außerhalb der Vorgabe. Das Stammdaten-Formular springt nach dem Speichern einer Ressource auf `/master-data#resources` -- den Bereich gibt es nicht, die Liste zeigt dann Kunden.

### Punkt 5 (1.8.136): ein Weg zum Auftrag

- **Ursache**: `quote_editor.html::renderAll()` blendete bei vorhandenem Auftrag immer den Link `#orderOpenLink` („Auftrag öffnen“) ein und machte zugleich den Hauptknopf `#orderButton` zu „Auftrag AUF-… öffnen“ (Angebot und Auftrag gleich, oder Abgleich gesperrt) bzw. „Änderungen in AUF-… übernehmen“ (Abgleich möglich).
- **Änderung**: der Link bekommt den Text „Auftrag AUF-… öffnen“ und erscheint nur im Zustand „Änderungen übernehmen“; in den beiden anderen Zuständen öffnet allein der Hauptknopf den Auftrag. Ohne Auftrag unverändert „Angebot beauftragen“.
- **Test**: `test_lv_editor_ein_weg_zum_auftrag` (node, das echte `renderAll()` mit der Attrappe aus `test_v334`, der Versand-Baustein gestubbt; vier Zustände: gleich, gesperrt, abgleichbar, ohne Auftrag) -- genau ein sichtbarer Weg „Auftrag AUF-2026-0001 öffnen“; vorher in drei Zuständen rot (Link und Knopf, bzw. Link ohne Nummer).

### Punkt 6 (1.8.137): manuell buchen

- **Ursache**: `time_tracking.html` -- zwei `<button onclick="openManual()">`: „+ Manuell buchen“ (Kopf der Karte „Heutige Buchungen“) und „+ Zeitbuchung anlegen“ (Karte „Manuelle Buchung“).
- **Änderung**: Karte „Manuelle Buchung“ entfernt, „+ Manuell buchen“ mit `title` (der Satz der Karte). Das Ausblenden bei abgeschalteten manuellen Buchungen (`button[onclick="openManual()"]`) trifft weiter den einen Knopf.
- **Test**: `test_zeiterfassung_buero_ein_knopf_zum_manuellen_buchen` (gerenderte Seite als Büro – Finanzen: genau ein Knopf mit `openManual()`, „+ Manuell buchen“; keine Karte „Manuelle Buchung“) -- vorher rot (zwei Knöpfe).

### Punkt 7 (1.8.138): Änderungshistorie

- **Ursache**: `app/audit.py` speichert beim Schreiben `TYPE_LABELS.get(type(obj))` bzw. `FIELD_LABELS.get(feld, feld)` -- fehlte ein Eintrag, landete der Klassen- bzw. Spaltenname in der Zeile (16 von 81 protokollierten Arten, 199 von 419 Feldnamen; bis 1.8.150 stand hier „16 von 104“, berichtigt in Punkt 8 der Nachrunde). Werte wurden roh gespeichert und roh angezeigt (`history.html` setzte `old_value`/`new_value` unverändert ein). Die Seite rief `/api/audit-logs?limit=500` auf; die API kannte keinen Versatz, ältere Einträge waren nicht erreichbar.
- **Änderung**:
  - `app/audit.py`: 16 Arten und 199 Feldnamen ergänzt; Rückfall der Art im Eintragsnamen auf `TYPE_LABELS`; `audit_rows(..., offset=0)`.
  - neues `app/verlauf_namen.py`: `lesbar(zeile)` übersetzt beim Lesen Art (`entity_type_label`, auch ein gespeicherter Klassenname als Eintragsname), Feldname (gespeicherte Bezeichnung, wenn sie eine ist, sonst die heutige) und Werte je Feldname (`wert_lesbar()`, Tabellen aus den Konstanten der Fachmodule -- Status, Rollen, Zeitarten, Abwesenheiten, Vertragsgrundlage, Leistungsart, Mängel, Nebenforderungen, Zahlungsarten, Rechtstexte, Optionsgruppen u. a.). Ein Code, den keine Tabelle kennt, bleibt stehen.
  - `app/routers/audit.py`: `offset`, liest `limit + 1` Zeilen und setzt `X-DK-Weitere` (1/0, gezählt vor der Schwärzung), übersetzt jede Zeile nach der Schwärzung -- die hängt an den rohen `entity_type`/`field_name`, die gespeichert und ausgeliefert unverändert bleiben. `AuditLogOut.entity_type_label` neu.
  - `history.html`: Blättern zu je 100 („← Neuere“, „Seite n“, „Ältere →“, über die Kopfzeile), Filter „Bereich“ mit Wert = gespeicherte Art und Text = lesbare Art, Anzeige und Suche über die lesbare Art; das Lesen bleibt in `load()` (Ausnahme „nur Anzeige“ in `tests/test_v400_lesen_ueber_baustein.py`).
  - `project_folder.html`: Reiter „Verlauf“ zeigt `entity_type_label` (lädt weiter höchstens 300 Einträge des Projekts, kein Blättern -- nicht Teil des Punkts).
- **Test** (alle vorher rot): `test_jede_protokollierte_art_hat_einen_namen`, `test_jedes_protokollierte_feld_hat_einen_namen` (jede Spalte jedes protokollierten Modells außer `EXCLUDED_FIELDS`), `test_feste_werte_der_historie_sind_lesbar` (jeder feste Wert einer protokollierten Spalte aus dem Katalog von `tests/test_v364_feste_werte_spaltenlaenge.py`, der ein Code ist -- klein, ohne Leerzeichen --, hat eine Bezeichnung), `test_historie_zeigt_lesbare_namen_auch_fuer_alte_eintraege` (gespeicherte Zeilen mit Klassen- und Spaltennamen über die echte Schranke: lesbar; Büro – Auftrag sieht den Lohn-Eintrag weiter nicht), `test_historie_blaettert` (150 Einträge: 100 + 50, Kopfzeile 1/0, neueste zuerst, lückenlos), `test_verlaufsseite_laedt_seitenweise` (Seitenskript in node: `load()` und `aeltere()` fragen `offset=0` und `offset=100` ab).
- **Nebenbefund**: der Reiter „Verlauf“ der Projektmappe lädt weiter bis zu 300 Einträge ohne Blättern.

### Punkt 8 (1.8.139): Seitentitel

- **Ursache**: jede Vorlage schreibt ihren `<title>` selbst, ohne gemeinsame Vorgabe -- drei Schreibweisen (`DACHKONZEPTE ERP – …`, `DACHKONZEPTE ERP · …`, `DACHKONZEPTE GmbH - …`), Formularseiten ohne Präfix, Versionsnummern aus frühen Ständen (`Version {{ app_version }}` in `index.html` und `quote_editor.html`, „0.6“ fest in `inquiries.html`).
- **Änderung**: 16 Vorlagen -- `index.html` (Leistungskatalog), `quote_editor.html` (LV-Editor), `inquiries.html` (Anfragen & Pipeline), `order.html`, `invoice_detail.html`, `finanzen.html`, `mahnwesen.html`, `search_results.html`, `email_dispatches.html`, `changelog.html`, `mobil.html`, `mobil_objekt.html`, `quote_form.html`, `project_form.html`, `service_form.html`, `master_data_form.html`. Seitennamen unverändert (außer dem Leistungskatalog, der bisher nur die Version trug).
- **Test** (beide vorher rot): `test_jede_seite_hat_den_einheitlichen_titel` (jede Seite aus `seiten()`, zusammengesetzt: genau ein `<title>`, Form „DACHKONZEPTE ERP – <Seite>“, kein „Version“, keine Versionsnummer), `test_gerenderte_titel_ohne_versionsnummer` (jede Seitenroute gerendert als Admin, Büro – Finanzen und Monteurin, 109 Titel).
- **Angepasste Erwartungen**: `tests/test_v061_compact_lv.py::test_v061_compact_table_editor_features_exist` -- alt: `Version {{ app_version }}` im LV-Editor, neu: `<title>DACHKONZEPTE ERP – LV-Editor</title>`. `tests/test_v265_mobile_rename_and_extras.py::test_mobil_reachable_for_field_with_correct_title` -- alt: „DACHKONZEPTE GmbH - Mobil“, neu: „DACHKONZEPTE ERP – Mobil“.

### Punkt 9 (1.8.140): Standardwerte der Prozente

- **Ursache**: `service_form.html::renderDefaults()` setzte die Prozente der Kalkulationsvorgaben unverändert ein (`${x}%`); die API liefert sie als Dezimaltext mit vier Stellen ("0.0000").
- **Änderung**: Anzeige über `zahlText()` aus `_zahl.html` (deutsches Format, ohne überflüssige Nullen) mit Leerzeichen vor dem Prozentzeichen: `${zahlText(x)} %`. Der Stundensatz lief schon über `money()` und bleibt.
- **Test**: `test_leistung_standardwerte_der_prozente_lesbar` (Seitenskript in node, `renderDefaults()` mit "0.0000", "12.5000", "5.0000" → „(Standard: 0 %)“, „(Standard: 12,5 %)“, „(Standard: 5 %)“) -- vorher rot („(Standard: 0.0000%)“).

### Punkt 10 (1.8.141): Finanzen

- **Ursache**: fester Text im Kopf von `finanzen.html` aus der Zeit, als die Seite nur die Rechnungsliste war.
- **Änderung**: der Satz „Weitere buchhalterische Themen folgen hier künftig.“ entfernt, „Alle Rechnungen im Überblick.“ bleibt.
- **Test**: `test_finanzen_ohne_platzhalter` (gerenderte Seite als Büro – Finanzen: erster Satz da, Platzhalter nicht) -- vorher rot.
- **Korrektur zu Punkt 9**: dort stand zuerst „mit geschütztem Abstand vor dem Prozentzeichen“; im Code steht ein gewöhnliches Leerzeichen (`${zahlText(x)} %`) -- im Abschnitt oben berichtigt.

### Punkt 11 (1.8.142): Befund Zeit buchen für andere

Nur Befund, kein Code der Anwendung geändert. Ausführlich mit Tabelle aller Endpunkte und ihrer Prüfung: `docs/archiv/rechtekonzept.md`, „Befund 1.8.142: Zeit buchen für andere (Monteurin)“.

- **API**: Einzelbuchungen nur für die eigene Person (`_time_entry_employee_for_request()`, `_time_entry_can_edit()`, 403), auch nicht für die Kolonne; Gruppenbuchung nur als Kolonnenführerin für Mitglieder des eigenen Teams (`_require_crew_leader()`, `validate_group_members()`).
- **Oberfläche**: `service_reports.html` bietet der Monteurin alle aktiven Mitarbeiter an (vorgewählt „— nicht zugeordnet —“), ein Kollege scheitert erst am Server (403).
- **Nebenbefund**: Stopp einer laufenden Gruppe prüft nur „hat angelegt“, nicht „noch Kolonnenführerin“.
- **Test**: `tests/test_v437_befund_zeit_fuer_andere.py` -- vier Angriffstests (grün: der Server lehnt ab), Ist-Stand der Auswahl, ein `xfail(strict=True)` für das Ziel der nächsten Runde. Gegenprobe a und b (Prüfungen ausgehebelt) machten die Angriffstests rot.
- **Für die nächste Runde zu bestätigen**: Kolonne nur über die Kolonnenführerin (heute) oder auch Mitglieder; Stopp nach entzogenem Kennzeichen.

### Endlauf der Runde (Regel 26)

- Erster Endlauf auf `d1c2ab9` (1.8.142): volle Suite 6144 bestanden, 1 rot -- `test_v419_verbindungen_unter_last.py::test_viele_gleichzeitige_seiten_und_abfragen` erwartete `/users` als Büro mit 200 (Folge von Punkt 3, nur gegen PostgreSQL, in den Teilläufen nicht dabei). Behoben im Commit „1.8.134 (Nachtrag)“ `8f22d36` (siehe Punkt 3, angepasste Tests), Regel 30 in CLAUDE.md berichtigt.
- Endlauf auf `8f22d36` bei sauberer Arbeitskopie: volle Suite (`-n 16 --dist loadfile`) 6145 bestanden, 3 übersprungen, 1 xfail (`test_v437…::test_einsatzbericht_bietet_der_monteurin_nur_an_was_der_server_annimmt`, Befund Punkt 11), 7:19 min; Klicktests (`klicktest_alle.py --gleichzeitig 4`) 78 von 78 wie erwartet, darunter der neue `klicktest_lv_ueberlauf.py` mit 13/13, 6:48 min.

## Nachrunde zur Fehlerrunde (1.8.143 ff.)

Vorgabe vom 19.10.2026 (übernommen wie gegeben): „Nachrunde zur Fehlerrunde. Entscheidungen von Tobias: /users bleibt nur für Admins (Festlegung 1.8.134 bestätigt). Für die Kolonne bucht nur, wer das Kolonnenführer-Kennzeichen hat (wie heute). Gruppenzeit stoppen ohne Kennzeichen wird gesperrt wie Ändern. Umsetzen, je Punkt ein Test, der vorher scheitert: 1. Einsatzbericht: Monteure sehen bei Zeit buchen keine Auswahl „Mitarbeiter“, sie buchen für sich. Das xfail aus test_v437 wird ein normaler grüner Test. 2. Gruppenzeit stoppen ohne Kennzeichen → 403 wie Ändern. Angriffstest mit Gegenprobe. Prüfe, dass ein Admin sie danach stoppen kann; falls nicht, nur melden. 3. Kennzeichen entziehen, während für das Team eine Gruppenzeit läuft: Rückfrage „Gruppenzeit läuft noch – trotzdem entziehen?“. Nichts wird automatisch gestoppt. 4. users.html: Zurück-Link mit echtem Ziel statt history.back(). 5. Stammdaten-Formular: nach Speichern einer Ressource in den richtigen Bereich statt /master-data#resources. 6. Auftrag: Menge und EP mit Tausenderpunkt über zahlText(). 7. Einstellungen und alle anderen Stellen: Links nach /users nur für Admins zeigen. 8. /api/audit-logs: offset negativ oder keine Zahl → 422, sehr groß → leere Seite, nie 500. Dazu ein Test, der rot wird, wenn eine Audit-Art oder ein Feld keinen lesbaren Namen hat, falls es ihn noch nicht gibt. Am Ende: volle Suite und Klicktests auf sauberer Arbeitskopie, Bericht je Punkt (Ursache, Datei, Änderung, Test). Ein Commit je Punkt, nicht pushen.“

Festlegung 1.8.134 Nr. 1 (`/users` nur für Administratoren) damit bestätigt. Die Punkte 1–3 betreffen die Zeiterfassung der Monteure: Befund und Herleitung in `docs/archiv/rechtekonzept.md`, „Befund 1.8.142“ (dort unter „Umsetzung“ ein Verweis hierher). Tests der Punkte 1–3 in `tests/test_v437_befund_zeit_fuer_andere.py`, der übrigen in `tests/test_v438_nachrunde.py`. Die volle Suite und alle Klicktests laufen nach der Vorgabe einmal am Ende auf sauberer Arbeitskopie; je Punkt laufen die berührten Tests (auch die gegen PostgreSQL) und Klicktests.

### Punkt 1 (1.8.143): Einsatzbericht ohne Auswahl „Mitarbeiter“ für Monteure

- **Ursache**: `service_reports.html` füllte `#teEmployee` für jede Rolle mit `employeeOptionsHtml(null)` -- alle aktiven Mitarbeiter, vorgewählt „— nicht zugeordnet —“. Der Server nimmt für jede Rolle außer Admin nur die eigene Person an (`_time_entry_employee_for_request()`), ein gewählter Kollege endete mit 403.
- **Änderung**: `nurFuerSichBuchen()` (Rolle `field` laut `/api/auth/status`) und `zeitMitarbeiterOptionen()`: für Monteure fest die eigene Person (aus `/api/employees` über `employee_id`), das Feld `#teEmployeeField` verborgen -- schon im Markup (`{% if not darf_buero_seiten %} hidden`), damit nichts aufblitzt, und vom Skript ebenso gesetzt. Ohne zugeordneten Mitarbeiter: „Ihr Benutzer ist keinem Mitarbeiter zugeordnet – Zeit buchen ist nicht möglich.“ Das Büro unverändert (alle aktiven Mitarbeiter).
- **Test**: `test_einsatzbericht_bietet_der_monteurin_nur_an_was_der_server_annimmt` (bis 1.8.142 `xfail(strict=True)`, jetzt grün und erweitert: Auswahl nur „Mia Test“, Feld verborgen, die Buchung geht mit ihrer `employee_id` hinaus), `test_einsatzbericht_mitarbeiterfeld_im_markup_nur_fuers_buero` (gezeichnete Seite: als Monteurin `hidden`, als Büro nicht) -- beide vorher rot. Klicktest `klicktest_monteur_dachflaechen.py` um vier Prüfungen erweitert (Feld verborgen, nur die eigene Person, „Gebucht.“, Buchung für ihn mit 2,5 h): 10/10, ohne die Änderung 5/10.
- **Angepasste Erwartung** (Regel 28): `test_einsatzbericht_ist_stand_mitarbeiterauswahl` (Ist-Stand 1.8.142: Monteurin sieht alle aktiven Mitarbeiter) → `test_einsatzbericht_buero_behaelt_die_auswahl` (Büro – Finanzen sieht alle, Feld nicht verborgen).

### Punkt 2 (1.8.144): Gruppenzeit stoppen ohne Kennzeichen

- **Ursache**: `app/routers/time_tracking.py::stop_time_group()` prüfte nur „Initiator oder Admin“, ebenso der Gruppenweg in `stop_time_entry()`; `_require_group_owner()` (Ändern, Löschen) verlangt für Monteure zusätzlich das Kennzeichen im Team der Buchung.
- **Änderung**: `_noch_kolonnenfuehrer()` -- für Monteure das Kennzeichen im (aktiven) Team der Gruppe, für Büro und Admin immer wahr. `stop_time_group()`: ohne Kennzeichen 403 mit derselben Meldung wie Ändern („Gruppenbuchungen sind für Monteure dem Kolonnenführer des Teams vorbehalten.“). `stop_time_entry()`: die Gruppe für alle nur mit Kennzeichen; sonst der Weg eines Mitglieds -- nur die eigene Zeit, als einzeln geändert markiert (`stop_timer()`), die Gruppe läuft weiter. Die mobile Zeiterfassung stoppt über diesen Weg (`time_tracking_field.html`), sie bleibt bedienbar.
- **Admin**: geprüft -- `POST /api/time-entry-groups/{id}/stop` als Admin stoppt die Gruppe danach (200, alle Zeiten gebucht). Kein Befund.
- **Test**: `test_ehemalige_kolonnenfuehrerin_stoppt_die_gruppe_nicht` (über die echte Anmeldeschranke: Kontrolle mit Kennzeichen 200; nach entzogenem Kennzeichen Ändern 403, Gruppen-Stopp 403 mit Meldung, beide Zeiten laufen weiter; eigene Zeit stoppen 200, nur ihre steht, Max und die Gruppe laufen; Admin stoppt die Gruppe 200, nichts läuft mehr) -- vorher rot (Gruppen-Stopp 200).
- **Gegenprobe** (Regel 24, Marker `GEGENPROBE`, Datei danach byte-genau zurück, SHA-256 `9fb0a8d1eb2d6985…` vorher = nachher): (a) Prüfung im Gruppen-Stopp ausgehebelt -- rot (200 statt 403); (b) Prüfung im Gruppenweg von „Zeit stoppen“ ausgehebelt -- rot (ihre Zeit stoppte die Gruppe für alle).
- **Angepasste Erwartung** (Regel 28): `test_nebenbefund_ehemalige_kolonnenfuehrerin_stoppt_die_gruppe_weiter` (Ist-Stand 1.8.142: Gruppen-Stopp 200) → `test_ehemalige_kolonnenfuehrerin_stoppt_die_gruppe_nicht` (403, eigene Zeit, Admin).
- Klicktests `klicktest_teil_updates`, `klicktest_zeitbuchungen_liste`, `klicktest_browser_datum`, `klicktest_monteur_dachflaechen` grün.

#### Festlegungen 1.8.144 (Bitte bestätigen)

1. **„Zeit stoppen“ an der eigenen Zeit ohne Kennzeichen stoppt nur die eigene Zeit** -- wie bei jedem Mitglied (als einzeln geändert markiert), nicht 403: sonst könnte die ehemalige Kolonnenführerin ihre eigene laufende Zeit gar nicht beenden. Die Gruppe läuft weiter, bis ein Admin sie stoppt oder jedes Mitglied seine eigene Zeit stoppt.

### Punkt 3 (1.8.145): Rückfrage beim Entziehen des Kennzeichens

- **Ursache**: `app/routers/resource_planning.py::update_team()` legt die Mitglieder samt Kennzeichen bei jedem Speichern neu an, ohne auf laufende Gruppenzeiten zu sehen; seit 1.8.144 verliert die Initiatorin damit den Stopp für alle.
- **Änderung**: `_entzieht_bei_laufender_gruppenzeit()` -- wer vorher das Kennzeichen in einem aktiven Team hatte und es nachher nicht mehr hat (abgewählt, aus dem Team genommen, Team inaktiv), während eine Gruppenzeit des Teams läuft (`TimeEntryGroup.status == "running"`); dann 409 mit `detail = {"code": "laufende_gruppenzeit", "message": "Gruppenzeit läuft noch – trotzdem entziehen?"}`, außer mit `?trotz_laufender_gruppenzeit=true`. Andere Änderungen am Team speichern ohne Rückfrage. `master_data_form.html`: `api()` gibt Status und `detail` am Fehler mit; `save(trotzLaufenderGruppenzeit)` fragt bei genau dieser 409 mit `confirm()` (Regel 4: Ja/Nein ist erlaubt) und speichert mit „OK“ erneut mit Bestätigung, mit „Abbrechen“ Meldung „Nicht gespeichert – das Kennzeichen bleibt.“. Nichts wird gestoppt.
- **Test**: `test_kennzeichen_entziehen_bei_laufender_gruppenzeit_fragt_nach` (echte Anmeldeschranke: andere Änderung während der Gruppe 200; Kennzeichen weg 409 mit Rückfrage, Kennzeichen bleibt; mit Bestätigung 200, Kennzeichen weg, beide Zeiten und die Gruppe laufen; ohne laufende Gruppe keine Rückfrage) und `test_teamformular_fragt_vor_dem_entziehen_nach` (OK und Abbrechen: das Skript der vom Server gezeichneten Seite `/master-data/teams/5/edit` in node -- neuer Helfer `tests/gerenderte_seite.py`, weil `seite()` jeden Jinja-Ausdruck auf 1 setzt und das Formular an der Art des Bereichs hängt) -- alle drei vorher rot. Neuer Klicktest `klicktest_kennzeichen_entziehen.py` (Abbrechen: Rückfrage, Meldung, Kennzeichen bleibt; OK: zurück in die Liste, Kennzeichen weg, beide Zeiten laufen): 8/8, ohne die Änderung 3/8.
- **Nebenbefund** (nicht geändert): `DELETE /api/teams/{id}` deaktiviert ein eingeplantes Team ohne diese Rückfrage (das Kennzeichen gilt dann ebenso nicht mehr).

### Punkt 4 (1.8.146): Zurück-Link der Benutzerverwaltung

- **Ursache**: `users.html` -- `<a class="back" href="#" onclick="history.back();return false">← Einstellungen</a>` (dasselbe Muster wie bei den vier Formularseiten bis 1.8.134, außerhalb der damaligen Vorgabe).
- **Änderung**: `<a class="back" href="/settings">← Einstellungen</a>` -- fest, die Seite hat kein Ziel aus der Adresse und nur einen Weg dorthin (Einstellungen → System → Benutzer und Zugriff).
- **Test**: `test_benutzerseite_zurueck_in_die_einstellungen` (gerenderte Seite als Admin: genau ein Zurück-Link, Ziel `/settings`, Text „← Einstellungen“, kein onclick, kein `history.back` mehr auf der Seite; `/settings` öffnet sich) -- vorher rot (Ziel „#“).
- **Nebenbefund** (nicht geändert): `history.back()` steht noch in `account.html`, `address_import.html`, `history.html` und `index.html`.

### Punkt 5 (1.8.147): Ziel nach dem Speichern im Stammdaten-Formular

- **Ursache**: `master_data_form.html::save()` endete mit `location.href='/master-data#'+type`. Für `resources` ergibt das `#resources`; `master_data.html::viewFromHash()` kennt nur customers, properties, employees, teams, assets, suppliers, contacts, catalogs, materials, materialGroups und fällt sonst auf Kunden zurück. Ressourcen führt die Liste unter `assets` („Fuhrpark & Maschinen“ bei abgeschaltetem Modul Betriebsmittel, 1.8.135).
- **Änderung**: `app/routers/pages.py` gibt beiden Formularrouten `listenbereich = STAMMDATEN_BEREICHE[data_type][0]` mit (dieselbe Zuordnung wie der Zurück-Link); das Formular springt nach dem Speichern auf `'/master-data#'+LISTENBEREICH` (fester lokaler Anfang, Regel 30). Die Sonderwege (neues Objekt, neuer Kontakt aus der Projektmappe, neues Betriebsmittel) bleiben.
- **Test**: `test_stammdaten_formular_springt_in_den_bereich_der_liste` (das Skript der vom Server gezeichneten Seite in node, `tests/gerenderte_seite.py`: Ressource neu und bearbeiten → `#assets`, Team bearbeiten → `#teams` als Kontrolle) -- die beiden Ressourcen-Fälle vorher rot (`#resources`); `test_jeder_stammdatenbereich_hat_einen_bereich_der_liste` (jeder Bereich der Zuordnung steht in `viewFromHash()`, Wächter, auch vorher grün). Klicktests `klicktest_kennzeichen_entziehen`, `klicktest_beteiligte`, `klicktest_beteiligte_stammdaten`, `klicktest_auswahl_inaktiv`, `klicktest_auswahl_restfaelle`, `klicktest_daten_im_html` grün.
- **Korrektur zu Punkt 4**: dort steht als Nebenbefund `history.back()` auch in `account.html` -- dort nur in einem Kommentar; aktiv noch in `address_import.html`, `history.html` und `index.html`.

### Punkt 6 (1.8.148): Menge und Einheitspreis mit Tausenderpunkt

- **Ursache**: `_zahl.html::zahlText()` formatiert mit `useGrouping: false`; `order.html` füllt die Felder Menge und Einheitspreis der LV-Zeile (`rowHtml()`) und des Positionsdialogs (`openItem()`) damit.
- **Änderung**: `zahlText(wert, stellen, optionen)` -- `optionen.tausender` schaltet den Tausenderpunkt ein (Vorgabe aus, alle anderen Felder unverändert). `order.html` nimmt `TAUSENDER = {tausender: true}` für Menge und Einheitspreis in LV-Zeile und Dialog. Der Rückweg ist unverändert: `zahlLesen()` nimmt den Punkt vor je drei Ziffern an (Regel 34), „12.345,678“ → 12345.678.
- **Spaltenbreiten**: der Klicktest fand bei 1280 px das Mengenfeld 59 px breit (47 px Text) -- „12.345,678“ braucht 67 px, „12345,678“ ohne Punkt schon 64 px, eine übliche Menge wie „1.234,50“ 52 px; abgeschnitten seit 1.8.133 (dort wurde nur das Auslaufen aus der Tabelle gemessen, nicht der Text im Feld). Gemessen bei 1280 px: alle Spalten auf ihrem Mindestmaß, die Leistung nie über ihren 110 px. Neu `minmax(44px,85px) minmax(104px,1fr) minmax(82px,95px) minmax(58px,90px) minmax(72px,110px) minmax(108px,115px) minmax(36px,55px)` (Mindestbreiten 504 px + Abstände = 552 px von 559 px bei 1280): Menge 82 px, Leistung 104 statt 110 px, Einheit 58 statt 60 px (breiteste übliche Einheit „psch“ 29 px Text).
- **Test**: `test_zahltext_mit_tausenderpunkt_und_zurueck` (Fälle mit Option, Rückweg über `zahlLesen()`, ohne Option weiter ohne Punkt) und `test_auftrag_zeigt_menge_und_ep_mit_tausenderpunkt` (Seitenskript in node: LV-Zeile und Dialog „12.345,678“/„1.234,56“) -- beide vorher rot. `klicktest_lv_ueberlauf.py` um „Tausenderpunkt, passt ins Feld“ bei 1440 und 1280 px erweitert: 15/15, ohne die Änderung 13/15. Klicktests der Auftragsseite (`auftrag_sperren`, `nachtrag`, `zahleneingaben`, `endrechnung`, `mahnen_endrechnung`, `rechnungen_sperren`, `abgleich_sperre`) grün.
- **Bildgrundlage**: die Auftragsseite zeichnet Menge, EP und Spalten anders -- die nächste Grundlage weicht dort ab.

#### Festlegungen 1.8.148 (Bitte bestätigen)

1. **Tausenderpunkt nur auf Wunsch** -- `zahlText()` bleibt ohne Punkt, die Option `{tausender: true}` nutzt nur die Auftragsseite für Menge und Einheitspreis; jedes andere Zahlenfeld der Anwendung schreibt unverändert.
2. **Spalten im LV des Auftrags neu verteilt** -- Menge mindestens 82 px (vorher 60), dafür Leistung 104 statt 110 px und Einheit 58 statt 60 px; sonst wäre die Menge bei 1280 px abgeschnitten.

### Punkt 7 (1.8.149): Links nach /users nur für Administratoren

- **Befund**: kein Fehler. Verweise auf die Seite `/users` gibt es in den Vorlagen nur zwei: `settings.html` (Menü „System → Benutzer und Zugriff“, seit 1.8.112 im Block `{% if ist_admin %}`) und `users.html` selbst (`/login?next=/users` nach dem Abmelden). Kein Skript baut einen Link dorthin, kein „…url“ im Python-Code. Auf der Benutzerseite selbst landet nur, wer sie öffnen darf (seit 1.8.134 nur Admin).
- **Änderung**: keine an der Anwendung; zwei Wächter, damit es so bleibt. Der Punkt verlangte einen Test, der vorher scheitert -- das ist hier nicht möglich, weil der Stand schon richtig war; stattdessen zeigen zwei Gegenproben, dass die Wächter anschlagen.
- **Test**: `test_links_nach_users_nur_fuer_admins` (jede Seitenroute gezeichnet als Büro – Finanzen, Büro – Auftrag und Monteurin, 105 Seiten mit 200: kein `href`, keine Navigation und keine Zeichenkette auf `/users`; als Admin zeigen die Einstellungen den Link) und `test_verweise_nach_users_nur_in_den_einstellungen_fuer_admins` (in allen Vorlagen nur `settings.html` und `users.html`, in `settings.html` innerhalb von `{% if ist_admin %}`).
- **Gegenprobe** (Marker `GEGENPROBE`, Dateien danach byte-genau zurück): (a) in `settings.html` `{% if ist_admin %}` vor dem Menü „Module/Benutzer“ durch `{% if true %}` ersetzt -- beide rot (Büro sieht den Link auf `/settings`; Link nicht mehr im Admin-Block); (b) in `dashboard.html` ein Skript mit `location.href='/users'` eingesetzt -- beide rot (Startseite für Büro; Vorlage außerhalb der erlaubten).

### Punkt 8 (1.8.150): /api/audit-logs ohne Serverfehler, Namen lesbar

- **Ursache**: `app/routers/audit.py::list_audit_logs()` nahm `offset: int = 0` ohne Grenze; `audit_rows()` setzte einen negativen still auf 0 (`max(offset, 0)`), eine Zahl über 64 Bit ging an die Datenbank -- SQLite `OverflowError: Python int too large to convert to SQLite INTEGER`, PostgreSQL ebenso nur bigint -- und wurde ein 500. Dasselbe bei `project_id`. Ein `offset`, der keine ganze Zahl ist, war schon 422 (FastAPI).
- **Änderung**: `offset: int = Query(0, ge=0)` (negativ oder keine ganze Zahl 422); über `GROESSTER_VERSATZ = 2**62` oder mit einer `project_id` außerhalb von 64 Bit sofort eine leere Seite mit `X-DK-Weitere: 0`, ohne Datenbank. `limit` bleibt wie bisher auf 1…1000 begrenzt (auch riesig oder negativ kein Fehler).
- **Test**: `test_audit_logs_versatz_nie_500` (11 Fälle: `-1`, `x`, `1.5` → 422; `1000000`, `2**62`, `2**63`, `10**30` und `project_id=10**30` → 200 und leer; `limit` riesig und negativ, `offset=0` → 200 mit Einträgen) -- vorher rot: `offset=-1` (200), `2**63`, `10**30`, `project_id=10**30` (500).
- **Lesbare Namen**: den Test gab es seit 1.8.138 als „hat einen Namen“ (`test_jede_protokollierte_art_hat_einen_namen`, `test_jedes_protokollierte_feld_hat_einen_namen` in `tests/test_v436_fehlerrunde_vor_stufe_2.py`) -- ein technischer Name als Bezeichnung (`"property_address": "property_address"`) blieb dort grün. Neu `test_namen_der_historie_sind_lesbar`: jede Art und jedes Feld der protokollierten Modelle hat einen Namen, der nicht leer, nicht der technische Name, ohne Unterstrich und nicht in Klassenschreibweise ist; heute alle 81 Arten und 419 Felder lesbar (Wächter, auch vorher grün). Gegenprobe (Marker `GEGENPROBE`, `app/audit.py` danach byte-genau zurück, SHA-256 `a8997f110f3605b8…`): (a) Feldname = technischer Name -- nur der neue Test rot; (b) Art ohne Namen -- beide rot; (c) Art in Klassenschreibweise -- nur der neue Test rot.
- **Korrektur zu Punkt 7 der Fehlerrunde (1.8.138)**: dort stand „16 von 104“ Arten ohne Namen; protokolliert werden 81 Modelle (`AUDITED_TYPES`), 104 ist die Zahl aller Modelle. Nachgezählt am Stand 1.8.137 (Git-Arbeitskopie auf `324954b`): 16 von 81 Arten, 199 von 419 Feldnamen ohne Namen. Im Changelog und oben berichtigt.

### Endlauf der Nachrunde (Regel 26)

- Auf `0dad8c4` (1.8.150 samt Nachtrag in CLAUDE.md) bei sauberer Arbeitskopie: volle Suite (`-n 16 --dist loadfile`) 6171 bestanden, 3 übersprungen, kein xfail mehr (das aus `test_v437` ist seit 1.8.143 grün), 7:02 min; Klicktests (`klicktest_alle.py --gleichzeitig 4`) 79 von 79 wie erwartet, darunter neu `klicktest_kennzeichen_entziehen` 8/8 und erweitert `klicktest_lv_ueberlauf` 15/15 und `klicktest_monteur_dachflaechen` 10/10, 6:53 min.

## Nachrunde 2 zur Fehlerrunde (1.8.151 ff.)

Vorgabe vom 19.10.2026 (übernommen wie gegeben): „Nachrunde 2. Festlegungen 1.8.144 Nr. 1 sowie 1.8.148 Nr. 1 und 2 sind bestätigt. Erst prüfen: 1. zahlLesen() seit 1.8.148: Tabelle Eingabe → Ergebnis für „1.234,50“, „1.234“, „1,5“, „1.5“, „1234.5“, „12.345.678,9“. Dazu ein Roundtrip-Test für Menge und EP im Auftrag: Wert mit Tausenderpunkt angezeigt, unverändert gespeichert → derselbe Betrag in der Datenbank. Speichert der Roundtrip einen anderen Betrag: anhalten und melden, nichts weiter ändern. Dann umsetzen, je Punkt ein Test, der vorher scheitert: 2. Einsatzbericht: Auswahl „Mitarbeiter“ nur für Rollen, die laut Server für andere buchen dürfen (heute Admin). Alle anderen buchen für sich, wie die Monteure. 3. DELETE /api/teams/{id}: dieselbe Rückfrage (409) wie beim Entziehen des Kennzeichens, wenn für das Team eine Gruppenzeit läuft. 4. history.back() in address_import.html, history.html und index.html durch echte Ziele ersetzen. Am Ende: volle Suite und Klicktests auf sauberer Arbeitskopie, Bericht je Punkt. Ein Commit je Punkt, nicht pushen.“

Festlegungen 1.8.144 Nr. 1 und 1.8.148 Nr. 1 und 2 damit bestätigt. Tests in `tests/test_v439_nachrunde_2.py`.

### Punkt 1 (1.8.151): Prüfung zahlLesen() und Rundweg im Auftrag

- **Tabelle** (`zahlLesen()`, `_zahl.html`, unverändert seit 1.8.109; 1.8.148 änderte nur `zahlText()`):

| Eingabe | Ergebnis |
|---|---|
| „1.234,50“ | 1234,5 |
| „1.234“ | 1234 (Punkt vor drei Ziffern = Tausender) |
| „1,5“ | 1,5 |
| „1.5“ | abgelehnt: „nicht eindeutig – Dezimalstellen bitte mit Komma (z. B. 1,25), Tausender mit Punkt vor je drei Ziffern (z. B. 1.250).“ |
| „1234.5“ | abgelehnt, dieselbe Meldung |
| „12.345.678,9“ | 12345678,9 |

- **Rundweg**: angezeigt mit Tausenderpunkt, unverändert gespeichert → derselbe Betrag in der Datenbank, für Menge/EP 12.345,678/1.234,56, 1.234,5/1.000, 1.000.000/0,5 und 0,125/12.345.678,9 -- aus der LV-Zeile (`quickItem()` je Feld) und aus dem Dialog (`openItem()`, `saveItemDialog()`). Kein abweichender Betrag, die Runde ging weiter.
- **Test**: `test_zahllesen_tabelle_seit_1_8_148` (die Tabelle); `test_auftrag_rundweg_menge_und_ep_mit_tausenderpunkt` (Auftrag vom echten Dienst als Büro – Finanzen, das Seitenskript in node zeichnet die Zeile, verlässt die Felder unverändert und speichert den Dialog; jede gebaute Anfrage geht an den echten Dienst, danach Menge und EP aus der Datenbank = Ausgangswert); `klicktest_lv_ueberlauf.py` um „Rundweg speichert denselben Betrag“ erweitert (im echten Chrome die angezeigten Felder unverändert verlassen, zwei PUT laut Verbindungsprotokoll, danach 12345,678 und 1234,56): 16/16. Als Prüfung keine vorher rote Erwartung.

### Punkt 2 (1.8.152): Auswahl „Mitarbeiter“ nur für Rollen, die für andere buchen

- **Ursache**: 1.8.143 band das Ausblenden an die Rolle `field` (`authStatus.user.role==='field'`, im Markup `darf_buero_seiten`). Der Server lässt aber jede Rolle außer Admin nur für sich buchen (`_time_entry_employee_for_request()`, `_time_entry_can_edit()`, je mit eigener Abfrage `role == "admin"`) -- das Büro sah Kollegen, die der Server ablehnte.
- **Änderung**: `app/permissions.py::darf_zeit_fuer_andere_buchen(user)` (Admin; ohne Konto wie bisher ohne Einschränkung) -- genutzt von `_time_entry_employee_for_request()` und `_time_entry_can_edit()` (Verhalten unverändert), von `/api/auth/status` (`user.zeit_fuer_andere_buchen`) und von der Seitenroute `/orders/{id}/service-reports` (`zeit_fuer_andere_buchen` im Kontext). `service_reports.html`: `nurFuerSichBuchen()` liest den Wert aus dem Anmeldestatus, das Markup verbirgt das Feld nach dem Kontext -- beide aus derselben Funktion.
- **Test**: `test_einsatzbericht_bietet_nur_an_was_der_server_annimmt[rolle]` (je Rolle mit echter Anmeldung: `/api/auth/status` und `/api/employees` vom echten Dienst, derselbe Dienst nimmt eine Buchung für Max an oder nicht; das Seitenskript in node: Admin -- 200, Auswahl aller, nichts vorgewählt; Büro – Finanzen, Büro – Auftrag, Monteurin -- 403, nur die eigene Person, Feld verborgen, Buchung für sich) und `test_einsatzbericht_mitarbeiterfeld_im_markup_nur_wer_fuer_andere_bucht[rolle]` (gezeichnete Seite: verborgen außer für Admin) -- die vier Büro-Fälle vorher rot. `klicktest_monteur_dachflaechen.py` um Büro und Admin erweitert (Büro: Feld verborgen, nur „Bea Büro“, gebucht für sich; Admin: Auswahl aller): 16/16, ohne die Änderung 13/16.
- **Angepasste Erwartungen** (Regel 28): `test_einsatzbericht_buero_behaelt_die_auswahl` (Büro sieht alle, Feld sichtbar) entfällt -- jetzt der Fall `buero_finanzen` im parametrisierten Test (nur die eigene Person, verborgen); `test_einsatzbericht_bietet_der_monteurin_nur_an_was_der_server_annimmt` (nur Monteurin) → `test_einsatzbericht_bietet_nur_an_was_der_server_annimmt[rolle]` für alle vier Rollen, Daten jetzt von echter Anmeldung statt erfundenem Anmeldestatus; `test_einsatzbericht_mitarbeiterfeld_im_markup_nur_fuers_buero` (Büro sichtbar, Monteurin verborgen) → `…_nur_wer_fuer_andere_bucht[rolle]` (verborgen außer Admin).
- **Nebenbefund** (nicht geändert): die Büro-Zeiterfassung (`time_tracking.html`) blendet ihre Auswahlen für Nicht-Admins schon aus, aber mit eigener Rollenabfrage im Skript (`auth.user?.role==='admin'`), nicht über `zeit_fuer_andere_buchen`; ebenso `get_time_tracking_context()` mit `user.role == "admin"`.

### Punkt 3 (1.8.153): Team löschen bei laufender Gruppenzeit

- **Ursache**: `app/routers/resource_planning.py::delete_team()` deaktivierte nur ein eingeplantes Team (`WorkPreparationTeamAssignment`), sonst `db.delete(team)` -- ohne Blick auf laufende Gruppenzeiten (1.8.145 fragte nur beim Speichern nach) und auf Gruppenbuchungen, die über `time_entry_groups.team_id` auf das Team verweisen.
- **Änderung**: läuft eine Gruppenzeit des Teams, 409 mit demselben `detail` wie beim Entziehen (`LAUFENDE_GRUPPENZEIT`), außer mit `?trotz_laufender_gruppenzeit=true` (gemeinsame Prüfung `_laufende_gruppenzeit()`). Gestoppt wird nichts. Ein Team mit Gruppenbuchungen (laufend oder abgeschlossen) wird deaktiviert statt gelöscht, wie ein eingeplantes.
- **Oberfläche**: keine -- geprüft, keine Vorlage ruft `DELETE /api/teams/{id}` auf (Stammdaten-Liste und -Formular nicht, `work_preparation.html::removeTeam()` entfernt nur die Zuordnung zur Arbeitsvorbereitung).
- **Test**: `test_team_loeschen_bei_laufender_gruppenzeit_fragt_nach` (echte Anmeldeschranke, Welt aus `test_v437`: 409 mit Rückfrage, Team bleibt aktiv; mit Bestätigung 200 `{"deleted": false, "deactivated": true}`, beide Zeiten und die Gruppe laufen; Team ohne Gruppen löscht ohne Rückfrage) -- vorher rot (`{"deleted": true}` ohne Rückfrage); `test_team_mit_gruppenbuchungen_wird_unter_postgresql_deaktiviert` (gegen PostgreSQL, Wegwerf-Schema: Team ohne Arbeitsvorbereitung mit abgeschlossener Gruppenbuchung wird deaktiviert) -- vorher rot mit `ForeignKeyViolation … time_entry_groups_team_id_fkey` (in einer ersten Fassung scheiterte der Test vorher am neuen Parameter statt am Fremdschlüssel; nachgeschärft, die Probe belegt jetzt den Fremdschlüssel).

### Punkt 4 (1.8.154): Zurück-Links mit echtem Ziel

- **Ursache**: `address_import.html` und `history.html` -- `<a class="back" href="#" onclick="history.back();return false">← Einstellungen</a>`; `index.html` (Leistungskatalog) -- dasselbe mit „← Stammdaten“. Nach direktem Aufruf führte der Link ins Leere.
- **Änderung**: Adressimport und Änderungshistorie fest `/settings` „← Einstellungen“ (der Adressimport hängt an Einstellungen → Anbindungen, die Änderungshistorie an Einstellungen → Protokolle; aus der Projektmappe führt „Gesamte Historie“ ebenfalls hin, zurück geht es dann in die Einstellungen). Leistungskatalog: `zurueck_stammdaten("catalogs")` aus der Seitenroute → `/master-data#catalogs` „← Stammdaten: Leistungskataloge“ (die Seite öffnet sich aus Stammdaten → Leistungskataloge, „Leistungen ansehen“ bzw. „Leistungen durchsuchen“). Der Kommentar in `account.html`, der das Muster noch „sonst im Projekt üblich“ nannte, berichtigt.
- **Test**: `test_zurueck_link_mit_echtem_ziel[3 Seiten]` (gerendert: genau ein Zurück-Link, Ziel und Name, kein onclick, das Ziel öffnet sich) und `test_kein_history_back_mehr_in_den_vorlagen` (keine Vorlage ruft `history.back` auf, Kommentare ausgenommen) -- alle vier vorher rot. Klicktests `klicktest_neue_ordnung`, `klicktest_monteur_navigation`, `klicktest_versand_im_kontext` grün.
- **Angepasste Erwartungen** (Regel 28): `tests/test_v243_leistungskatalog_sidebar_entry_point.py::test_leistungskatalog_page_has_back_link_to_master_data` -- alt „← Stammdaten“ und `history.back()` in `index.html`, neu der Zurück-Link mit `zurueck` und `zurueck_stammdaten("catalogs")` = `/master-data#catalogs`, „Stammdaten: Leistungskataloge“. `tests/test_v244_users_history_settings_only.py::test_users_and_history_pages_have_back_link_to_settings` -- alt „← Einstellungen“ und `history.back()` in `users.html` und `history.html`, neu `<a class="back" href="/settings">← Einstellungen</a>` und kein `onclick="history.back()`.
- **Eigener Fehler, berichtigt**: die alte Erwartung von `test_v244` war für `users.html` seit 1.8.146 falsch und blieb grün, weil der neue Jinja-Kommentar dort „statt history.back()“ enthält; in den Teilläufen zu 1.8.146 lief der Test mit und fiel nicht auf. Die neue Erwartung prüft den Link selbst.

### Endlauf der Nachrunde 2 (Regel 26)

- Auf `2b7e3ab` (1.8.154 samt Nachtrag in CLAUDE.md) bei sauberer Arbeitskopie: volle Suite (`-n 16 --dist loadfile`) 6187 bestanden, 3 übersprungen, 7:17 min; Klicktests (`klicktest_alle.py --gleichzeitig 4`) 79 von 79 wie erwartet, darunter erweitert `klicktest_lv_ueberlauf` 16/16 (Rundweg) und `klicktest_monteur_dachflaechen` 16/16 (Büro und Admin), 7:16 min.

## Stufe „Grundlage“ (1.8.155 ff.)

Vorgabe vom 19.10.2026 (übernommen wie gegeben): „Stufe „Grundlage“. Drei Teile. Nichts an Seitenaufbau oder Navigation ändern. A. Farben in app/static/ds/ds.css – Firmengrün wird Hauptaktion. Neu (hell / dunkel): --ds-aktion #367337 / #3B7D3C, --ds-auf-aktion #FFFFFF / #FFFFFF, --ds-aktion-hell #EEF5E8 / #17281A, --ds-aktion-rand #C4DDB0 / #2F5A30, --ds-aktion-text #2A5C2B / #B9DA86, --ds-marke-hell #A7CD5D / #A7CD5D (nur Schmuck, nie Text auf hellem Grund). Geändert: --ds-ok, --ds-ok-hell, --ds-ok-text bekommen die Werte von aktion, aktion-hell, aktion-text. --ds-signal bleibt Orange, aber nur noch für „wartet auf dich“ und Vorschläge. Wo signal heute als Hauptaktion genutzt wird: auf aktion umstellen und im Bericht auflisten. Kontrasttest um die neuen Paare erweitern: auf-aktion/aktion, aktion/flaeche, aktion/grund, aktion-text/aktion-hell, aktion-text/flaeche (Text ≥ 4,5, Bedienelement ≥ 3). PWA-Symbol und theme-color nicht anfassen. B. Bildgrundlage: Tablet-Aufnahmen auf das TerraPad 1201 – quer 1280 × 620, hoch 800 × 1100 (statt 1280 × 800 / 800 × 1280). Danach neue Grundlage aufnehmen, die Aufnahme „benutzer“ als Admin. C. Du statt Sie – nur Befund, nichts ändern: Liste aller Sie-Anreden (Sie, Ihnen, Ihr/Ihre als Anrede, „Bitte … Sie“), die ein Nutzer sieht: Vorlagen, Skripte, Server-Meldungen, PDFs, E-Mails. Je Stelle Datei, Text und Gruppe: „Oberfläche“ (wird Du), „an Kunden“ (Angebote, Rechnungen, Mahnungen, E-Mails, PDFs – bleibt Sie) oder „unklar“. Zahlen je Gruppe. „sie“ als dritte Person nicht mitzählen. Dazu ein Vorschlag für einen Wächter-Test, der Kundentexte beim Sie hält. Am Ende: volle Suite und Klicktests auf sauberer Arbeitskopie, Bericht je Teil. Commits, nicht pushen.“

### Teil A (1.8.155): Firmengrün als Hauptaktion

- **Befund**: `--ds-signal` und `--ds-ok` stehen nur in `ds.css` -- keine Vorlage, kein Skript, kein Test außer dem Kontrasttest nutzt sie (Stufe 1: die Tokens zeichnen noch nichts, die Seiten nehmen weiter `--accent`). „Signal als Hauptaktion“ war allein die Beschriftung des Blocks in `ds.css` („Signal: Hauptaktion und Vorschläge“).
- **Änderung** (`app/static/ds/ds.css`): neuer Block „Aktion: Firmengrün, Hauptaktion“ vor Signal mit den sechs Werten aus der Vorgabe, hell und dunkel; Signal beschriftet „„wartet auf dich“ und Vorschläge (bis 1.8.154 auch Hauptaktion)“; `--ds-ok`/`-hell`/`-text` hell `#367337`/`#EEF5E8`/`#2A5C2B` (vorher `#0F766E`/`#DDF1EE`/`#0B5B55`), dunkel `#3B7D3C`/`#17281A`/`#B9DA86` (vorher `#2BA196`/`#0F2E2B`/`#86DCCF`); Kopfkommentar: Herkunft der Werte und die fünf neuen Prüfpaare. PWA-Symbol (`/api/mobile-icon/…`) und `theme-color` nicht angefasst.
- **Kontrast** (WCAG 2, wie der Test):

| Paar | Grenze | hell | dunkel |
|---|---|---|---|
| auf-aktion/aktion | 4,5 | 5,73 | 5,02 |
| aktion-text/aktion-hell | 4,5 | 7,08 | 9,92 |
| aktion-text/flaeche | 4,5 | 7,88 | 10,53 |
| aktion/flaeche | 3 | 5,73 | 3,28 |
| aktion/grund | 3 | 5,01 | 3,62 |

  Die beiden Paare von ok (ok-text/ok-hell, ok/flaeche) tragen jetzt dieselben Werte und halten ebenso. Nicht verlangt, zur Einordnung: aktion auf `flaeche-2` (Hover, Infokasten) dunkel 2,91 -- ein grüner Knopf auf einem leicht abgesetzten dunklen Feld läge knapp unter 3; aktion-rand auf Fläche 1,47/2,06 und marke-hell auf Fläche hell 1,82 sind Schmuck, kein Bedienelement.
- **Test**: `test_kontrast_der_pruefpaare_hell_und_dunkel` verlangt die fünf neuen Paare ausdrücklich und 39 statt 34 Paare; `test_kontrast_gegenprobe` um drei Fälle erweitert (dunkles Grün `#2F5A30` → „dunkel aktion/flaeche“ rot; Grün `#A7CD5D` als Knopf → „hell auf-aktion/aktion“ rot; `aktion-text` fehlt → „Token fehlt“). Ohne die neuen Werte beide Tests rot. Klicktest `klicktest_ds_schriften` 27/27.
- **Angepasste Erwartungen** (Regel 28): `tests/test_v432_design_fundament.py::test_kontrast_der_pruefpaare_hell_und_dunkel` -- alt 34 Prüfpaare, neu 39 und die fünf neuen ausdrücklich; `::test_kontrast_gegenprobe` -- alt entfernt `--ds-ok-hell: #DDF1EE;`, neu `--ds-ok-hell: #EEF5E8;` (der neue Wert), dazu drei Fälle.

#### Festlegungen 1.8.155 (Bitte bestätigen)

1. **ok mit eigenen Werten, nicht als Verweis** -- `--ds-ok`, `-hell`, `-text` tragen dieselben Hex-Werte wie aktion statt `var(--ds-aktion…)`: der Kontrasttest liest Hex-Werte, ein Verweis bliebe dort ungeprüft. Eine spätere Änderung an aktion muss ok mitziehen (Kommentar „= aktion“ an den drei Zeilen).

### Teil B (1.8.156): Bildgrundlage mit den Fenstern des TerraPad 1201

- **Vorher**: `scripts/bildgrundlage.py` -- `STARTHOEHEN = {800: 1280, 1280: 800}`, die Fenster der TerraPad-Aufnahmen so groß wie die ganze Anzeige (1.8.131, Festlegung 1.8.131 Nr. 1 und 3).
- **Änderung**: `STARTHOEHEN = {800: 1100, 1280: 620}` -- hoch 800 × 1100, quer 1280 × 620, wie vorgegeben (die Höhe der Anzeige ohne die Leisten von System und Browser); Breiten (`TABLET = (800, 1280)`), Gerätemodus, 412 und 1440 unverändert. Ganzseitige Bilder: Mindesthöhe ist die Fensterhöhe, sonst die Höhe der Seite -- sie ändern sich nur, wo die Seite kürzer als das alte Fenster war. Zustandsbilder (Bild des Fensters): „Menü aufgeklappt“ bei 800 jetzt 800 × 1100, „Seitenleiste eingeklappt“ bei 1280 jetzt 1280 × 620. Die Aufnahme „benutzer“ ist seit 1.8.134 Admin (`AUFNAHMEN`, unverändert).
- **Test**: `tests/test_v431_bildgrundlage.py::test_monteurin_auch_auf_dem_terrapad` verlangt die neuen Fenster -- vorher rot. Probe `--nur einsatzbericht` (22 Bilder, 34 von 34 Prüfungen): Zustände 800 × 1100 und 1280 × 620, ganzseitig 800 × 1461 und 1280 × 1162.
- **Angepasste Erwartung** (Regel 28): `test_monteurin_auch_auf_dem_terrapad` -- alt `STARTHOEHEN == {800: 1280, 1280: 800}`, neu `{800: 1100, 1280: 620}`.
- Festlegung 1.8.131 Nr. 3 nannte die Fenster 800 × 1280 und 1280 × 800 -- seit 1.8.156 durch die Vorgabe ersetzt (800 × 1100, 1280 × 620).

### Teil C: Befund Du statt Sie (nur Befund, nichts geändert)

Ausführlich mit der Liste aller Stellen und dem Vorschlag für einen Wächter-Test: `docs/archiv/befund-du-statt-sie.md`. Gesucht in
Vorlagen (ohne Kommentare), allen Zeichenketten unter `app/` (ohne Docstrings und Protokollaufrufe), den Migrationen und den
Betreiber-Skripten; 108 Treffer an 89 Stellen, davon 9 dritte Person (nicht gezählt). **Oberfläche (wird Du): 50 Stellen, 53 Anreden;
an Kunden (bleibt Sie): 30 Stellen, 46 Anreden; unklar: 0.** 20 der Oberflächen-Stellen sind dieselbe Meldung „… keinem Mitarbeiter
zugeordnet“ in neun Fassungen -- bei der Umstellung eine gemeinsame Meldung.

### Nachtrag (Endlauf der Stufe „Grundlage“): `klicktest_anmelden` rot -- Wartebedingung zu schwach

- **Befund**: im Endlauf auf `04b2db2` war `klicktest_anmelden` rot (66 von 69): „Formular: falsches Passwort -> Meldung“ leer, keine
  Anfrage, JS-Fehler `ReferenceError: login is not defined` beim Enter im Passwortfeld. Wiederholt zweimal gleich rot -- und ebenso auf
  `2b7e3ab` (Stand vor dieser Runde, dort am Nachmittag noch 69/69, in einer Git-Arbeitskopie). Nicht durch Teil A, B oder C verursacht.
- **Ursache**: der Klicktest tippt, sobald das Feld `#u` im DOM steht. Das Skript der Anmeldeseite läuft aber erst, wenn das Stylesheet
  im Kopf (`ds.css`) geladen ist -- und die erste Design-Datei nach dem Start des Servers brauchte jetzt rund 500 ms (gemessen: erste
  Datei unter `/static/` 509 ms, jede weitere 5–6 ms, egal welche; im Browser `readyState` „loading“ und `typeof login` „undefined“, als
  getippt wurde, nach 3 s beides da). Woher die 500 ms im Server kommen, ist nicht geklärt: `app/design_dateien.py` allein (ohne Server)
  braucht beim ersten Abruf 47 ms (28 ms davon `mimetypes` aus der Registry); am Nachmittag fiel die Zeit nicht auf. Ein Nutzer ist nicht
  betroffen: der Browser zeichnet die Seite erst mit `ds.css` (erstes Bild nach 572 ms) -- vorher ist kein Feld zu sehen.
- **Änderung**: `scripts/klicktest_anmelden.py::_anmelden_formular()` wartet vor dem Tippen, bis `login` definiert ist (bis 10 s). Danach
  69/69, zweimal hintereinander. Eigener Commit „1.8.156 (Nachtrag)“; Suite und Klicktests danach neu (Regel 26).
- **Offen**: warum die erste Design-Datei im Server jetzt eine halbe Sekunde braucht. Im Betrieb träfe das je Arbeitsprozess einmal nach
  dem Start eine Anfrage.

### Endlauf der Stufe „Grundlage“ (Regel 26)

- Neue Bildgrundlage `bildgrundlage/31b85e8` (Commit von Teil B, saubere Arbeitskopie, Chrome 155.0.8059.40): 304 Bilder, 330 von 330
  Prüfungen, 406 s, 20 MB; „benutzer“ als Admin, TerraPad-Zustände 800 × 1100 und 1280 × 620.
- Erster Endlauf auf `04b2db2`: Suite 6187 bestanden, 3 übersprungen; Klicktests 78 von 79 -- `klicktest_anmelden` rot, siehe Nachtrag
  oben, behoben in `26a93ce`.
- Endlauf auf `26a93ce` bei sauberer Arbeitskopie: Klicktests 79 von 79 wie erwartet (7:23 min, `klicktest_anmelden` 69/69). Suite im
  ersten Lauf 6186 bestanden, 1 rot: `tests/test_v376_nummernkreise.py::test_postgresql_finalizing_waits_for_the_delete_and_uses_no_number`
  (`AttributeError: 'NoneType' object has no attribute 'status'` statt `InvoiceBlocked`) -- ein Gleichzeitigkeitstest gegen PostgreSQL:
  die erste Aktion löscht den Entwurf und hält die Sperre 1 s, die zweite soll in dieser Zeit festschreiben wollen und danach „Der Entwurf
  wurde inzwischen gelöscht.“ bekommen. Die zweite holt den Entwurf aber erst beim Start (`s.get()` im Test); unter 16 parallelen
  Prozessen startete sie nach dem Ende der ersten und bekam `None` -- der Fehler entsteht im Test, nicht in der Anwendung (über die API
  lädt `_get_invoice_or_404()` vorher und meldet einen schon gelöschten Entwurf mit 404). Allein fünfmal grün, die Datei 19/19; mit dieser
  Runde ohne Zusammenhang. Zweiter voller Lauf auf `26a93ce`: 6187 bestanden, 3 übersprungen (8:22 min). Nicht geändert, als
  Nebenbefund gemeldet: der Test wackelt unter Last (die zweite Aktion sollte den Entwurf vor dem Warten laden).

## Runde „Du“ (1.8.157 ff.)

Vorgabe vom 20.10.2026 (übernommen wie gegeben): „Runde „Du“. Festlegungen 1.8.155 Nr. 1 und zum Klicktest-Werkzeug sind bestätigt. 1. ds.css, dunkel: --ds-aktion und --ds-ok von #3B7D3C auf #3D823E (grüner Knopf auf flaeche-2 lag bei 2,91). Kontrasttest um aktion/flaeche-2 erweitern, hell und dunkel, Grenze 3. Dazu ein Wächter: ok, ok-hell, ok-text tragen dieselben Werte wie aktion, aktion-hell, aktion-text. 2. Du statt Sie nach docs/archiv/befund-du-statt-sie.md: die 50 Oberflächen-Stellen auf Du. Ton kurz und sachlich, z. B. „Bitte wählen Sie einen Kunden aus.“ → „Wähle einen Kunden aus.“ Die 30 Kundentexte nicht anfassen. 3. „… keinem Mitarbeiter zugeordnet“: eine gemeinsame Meldung statt neun Fassungen. 4. Wächter-Test wie vorgeschlagen: Verzeichnis aller Kundentexte, darin keine Du-Form (auch in echten PDFs aus Testdaten); Texte mit Kundentext-Merkmal müssen im Verzeichnis stehen; außerhalb keine Sie-Anrede. 5. Nur Befund: Warum braucht die erste Design-Datei nach dem Serverstart im Klicktest-Server rund 500 ms, allein aber 47 ms? Messen und melden, nichts ändern. Am Ende: volle Suite und Klicktests auf sauberer Arbeitskopie, Bericht je Punkt, dazu eine Liste alt → neu für alle geänderten Texte. Ein Commit je Punkt, nicht pushen.“

Festlegung 1.8.155 Nr. 1 (ok mit eigenen Werten) und die Festlegung zum Klicktest-Werkzeug (Formular-Klicktests warten auf das Skript der Seite) damit bestätigt.

### Punkt 1 (1.8.157): dunkles Grün, ok gleich aktion

- **Änderung** (`app/static/ds/ds.css`, dunkel): `--ds-aktion` und `--ds-ok` `#3B7D3C` → `#3D823E`; Prüfpaar `aktion/flaeche-2` (Bedienelement, 3 : 1) im Kopfkommentar.
- **Kontrast dunkel mit `#3D823E`**: aktion/flaeche-2 3,10 (vorher 2,91), aktion/flaeche 3,50 (3,28), aktion/grund 3,86 (3,62), auf-aktion/aktion 4,71 (5,02 -- bleibt über 4,5); hell aktion/flaeche-2 5,24.
- **Test**: `test_kontrast_der_pruefpaare_hell_und_dunkel` verlangt 40 Paare samt aktion/flaeche-2; `test_kontrast_gegenprobe` zusätzlich: das alte Grün `#3B7D3C` → „dunkel aktion/flaeche-2“ rot; neu `test_ok_traegt_die_werte_von_aktion` (ok, ok-hell, ok-text = aktion, aktion-hell, aktion-text, hell und dunkel; Gegenprobe: nur aktion geändert → „dunkel ok: #3D823E statt #3E843F (aktion)“). Ohne die Änderung alle drei rot. Klicktest `klicktest_ds_schriften` 27/27.
- **Angepasste Erwartungen** (Regel 28): `test_kontrast_der_pruefpaare_hell_und_dunkel` -- alt 39 Paare, neu 40 samt aktion/flaeche-2; `test_kontrast_gegenprobe` -- der Fall „dunkles Grün zu dunkel“ ersetzt jetzt `#3D823E` statt `#3B7D3C`.

### Punkt 2 (1.8.158): Oberfläche per Du

- **Umfang**: die 50 Oberflächen-Stellen aus `docs/archiv/befund-du-statt-sie.md` -- hier die 30 ohne „… keinem Mitarbeiter
  zugeordnet“ (dazu in `time_backoffice.html:60` der zweite Text derselben Zeile, „Hier stehen nur Ihre eigenen Anträge“); die 20 mit
  dieser Meldung bekommen in Punkt 3 die gemeinsame Meldung per Du. Die 30 Kundentexte und die neun Stellen in dritter Person
  („Sie bleibt als Beleg …“) unverändert.
- **Ton**: kurz und sachlich, Imperativ wie vorgegeben („Zieh …“, „Klick …“, „Wende dich …“), sonst nur die Anrede getauscht.
- **Prüfung**: dieselbe Suche wie im Befund danach -- außerhalb der Kundentexte nur noch die 20 Stellen für Punkt 3 und die dritte
  Person.
- **Angepasste Erwartungen** (Regel 28): `tests/test_v260_role_audit.py` (Sperrseite) alt „Diese Seite ist für Ihre Rolle nicht
  verfügbar“, neu „… für deine Rolle …“; `tests/test_v373_zugehoerigkeit.py` (Wartungshistorie in /mobil) alt „Objekte Ihrer Aufträge“,
  neu „Objekte deiner Aufträge“; `tests/test_v437_befund_zeit_fuer_andere.py::test_monteurin_bucht_einzeln_nur_fuer_sich` alt „Sie dürfen
  nur eigene Zeiten erfassen.“, neu „Du darfst nur eigene Zeiten erfassen.“; Klicktest `klicktest_backoffice_buero` alt „Hier stehen nur
  Ihre eigenen Anträge“, neu „… deine eigenen …“; Klicktest `klicktest_objekt_anderer_kunde` alt „… Objekte Ihrer Aufträge.“, neu
  „… Objekte deiner Aufträge.“
- Klicktests `klicktest_backoffice_buero`, `klicktest_objekt_anderer_kunde`, `klicktest_aufgaben_ohne_zustaendigkeit`,
  `klicktest_monteur_navigation` grün.

#### Liste alt → neu (31 Texte)

| Datei:Zeile | alt | neu |
|---|---|---|
| `app/templates/access_denied.html:22` | Diese Seite ist für Ihre Rolle nicht verfügbar | Diese Seite ist für deine Rolle nicht verfügbar |
| `app/templates/access_denied.html:23` | Bitte wenden Sie sich an eine Person mit den passenden Rechten, falls Sie diese Seite benötigen. | Brauchst du diese Seite, wende dich an eine Person mit den passenden Rechten. |
| `app/templates/checklist_template.html:217` | Sie bearbeiten den <b>Entwurf | Du bearbeitest den <b>Entwurf |
| `app/templates/checklist_template.html:218` | Sie sehen die <b>gültige Fassung | Du siehst die <b>gültige Fassung |
| `app/templates/mobil.html:151` | el.textContent='Keine Wartungen an Ihren aktuellen Objekten.';return} | el.textContent='Keine Wartungen an deinen aktuellen Objekten.';return} |
| `app/templates/mobil.html:339` | textContent='Keine Wartungen an Ihren aktuellen Objekten.'; | textContent='Keine Wartungen an deinen aktuellen Objekten.'; |
| `app/templates/roof_area.html:534` | `Ziehen Sie ein Rechteck auf der Skizze auf, | `Zieh ein Rechteck auf der Skizze auf, |
| `app/templates/roof_area.html:535` | `Klicken Sie auf die Skizze, | `Klick auf die Skizze, |
| `app/templates/tasks.html:80` | „Übernehmen“ macht die Aufgabe zu Ihrer eigenen. | „Übernehmen“ macht die Aufgabe zu deiner eigenen. |
| `app/templates/tasks.html:395` | Übernommen – die Aufgabe steht jetzt bei Ihren Aufgaben. | Übernommen – die Aufgabe steht jetzt bei deinen Aufgaben. |
| `app/templates/time_backoffice.html:60` | 'Hier stehen nur Ihre eigenen Anträge – | 'Hier stehen nur deine eigenen Anträge – |
| `app/templates/time_tracking_field.html:113` | Als Kolonnenführer buchen Sie hier für die ausgewählten Kollegen mit. Jede Buchung zeigt, dass Sie sie angelegt haben. | Als Kolonnenführer buchst du hier für die ausgewählten Kollegen mit. Jede Buchung zeigt, dass du sie angelegt hast. |
| `app/templates/time_tracking_field.html:534` | Keine eigenen Aufträge im Zeitraum gefunden. Ist ein Einsatz nicht dabei, wenden Sie sich an das Büro. | Keine eigenen Aufträge im Zeitraum gefunden. Fehlt ein Einsatz, wende dich an das Büro. |
| `app/operational_assets.py:413` | gelöscht werden -- archivieren Sie es stattdessen (Status auf Inaktiv). | gelöscht werden -- archiviere es stattdessen (Status auf Inaktiv). |
| `app/operational_assets.py:421` | "Archivieren Sie es stattdessen (Status auf Inaktiv)." | "Archiviere es stattdessen (Status auf Inaktiv)." |
| `app/permissions.py:89` | _DEFAULT_MESSAGE = "Für Ihre Rolle nicht verfügbar." | _DEFAULT_MESSAGE = "Für deine Rolle nicht verfügbar." |
| `app/routers/absence_requests.py:70` | Sie dürfen diesen Abwesenheitsantrag nicht zurückziehen. | Du darfst diesen Abwesenheitsantrag nicht zurückziehen. |
| `app/routers/checklists.py:83` | Von dieser Checkliste sind für Sie nur Titel, Datum und Ersteller sichtbar. | Von dieser Checkliste sind für dich nur Titel, Datum und Ersteller sichtbar. |
| `app/routers/field_view.py:371` | Die Wartungshistorie zeigt die Monteursansicht nur für Objekte Ihrer Aufträge. | Die Wartungshistorie zeigt die Monteursansicht nur für Objekte deiner Aufträge. |
| `app/routers/maintenance_contracts.py:214` | Dieses Objekt ist Ihnen aktuell nicht zugeordnet. | Dieses Objekt ist dir aktuell nicht zugeordnet. |
| `app/routers/orders.py:41` | Dieser Auftrag ist Ihnen nicht zugeordnet. | Dieser Auftrag ist dir nicht zugeordnet. |
| `app/routers/project_participants.py:70` | sind für Ihre Rolle nicht sichtbar. | sind für deine Rolle nicht sichtbar. |
| `app/routers/service_reports.py:91` | Sie dürfen nur sich selbst als Mitarbeiter angeben. | Du darfst nur dich selbst als Mitarbeiter angeben. |
| `app/routers/tasks.py:59` | Diese Aufgabe ist für Sie nicht sichtbar. | Diese Aufgabe ist für dich nicht sichtbar. |
| `app/routers/time_tracking.py:48` | Sie dürfen nur eigene Zeiten erfassen. | Du darfst nur eigene Zeiten erfassen. |
| `app/routers/time_tracking.py:374` | Sie dürfen diese Zeiterfassung nicht ändern. | Du darfst diese Zeiterfassung nicht ändern. |
| `app/routers/time_tracking.py:406` | Sie dürfen diese Zeitbuchung nicht ändern. | Du darfst diese Zeitbuchung nicht ändern. |
| `app/routers/time_tracking.py:427` | Sie dürfen diese Zeitbuchung nicht löschen. | Du darfst diese Zeitbuchung nicht löschen. |
| `app/tasks.py:202` | Diese Aufgabe ist für Ihre Rolle nicht sichtbar. | Diese Aufgabe ist für deine Rolle nicht sichtbar. |
| `app/time_tracking.py:419` | Sie gehören nicht zum ausgewählten Team. | Du gehörst nicht zum ausgewählten Team. |
| `app/time_tracking.py:422` | Sie dürfen nur für Kollegen des ausgewählten Teams mitbuchen. | Du darfst nur für Kollegen des ausgewählten Teams mitbuchen. |

### Punkt 3 (1.8.159): eine Meldung „… keinem Mitarbeiter zugeordnet“

- **Neu an allen 20 Stellen**: „Dein Konto ist keinem Mitarbeiter zugeordnet. Ein Administrator kann das unter Einstellungen → Benutzer und Zugriff ändern.“ -- per Du, mit dem Weg zur Abhilfe (die Benutzerverwaltung kann nur ein Admin öffnen,
  seit 1.8.134). Bis 1.8.158 neun Fassungen: „Ihr ERP-Benutzer …“ (10), „Ihr ERP-Benutzerkonto …“ (4, zwei davon „-- bitte einen
  Administrator kontaktieren“), „Ihr Büro-Konto …“ (2), je einmal „Ihr Benutzer … – Aufgaben können nicht angezeigt werden“, „Ihr
  Benutzer … – Zeit buchen ist nicht möglich“, „Ihr Konto … und hat keine eigenen Anträge …“, „Ihr Konto ist mit keinem Mitarbeiter
  verknüpft“; drei davon nannten den Menüpunkt noch „Benutzer & Zugriff“ (heute „Benutzer und Zugriff“).
- **Umsetzung**: `app/meldungen.py::KEIN_MITARBEITER` (neu) -- die 14 Stellen im Server (`app/tasks.py`, `app/time_tracking.py`,
  `app/routers/absence_requests.py`, `checklists.py`, `field_defects.py`, `field_view.py` ×2, `maintenance_contracts.py`, `time_tracking.py`
  ×4, `work_preparation.py`) nehmen die Konstante; die 6 Vorlagen (`dashboard.html`, `field_timesheet.html`, `service_reports.html`,
  `time_backoffice.html`, `time_tracking.html`, `time_tracking_field.html`) den Jinja-Global `kein_mitarbeiter` als
  `{{ kein_mitarbeiter|tojson }}` (im Dashboard in `esc()`, Regel 32). Was eine Seite zusätzlich sagte („Aufgaben können nicht
  angezeigt werden“, „hat keine eigenen Anträge – die Anträge anderer sieht ein Administrator“), entfällt -- eine Meldung.
- **Test** (neu `tests/test_v440_runde_du.py`, alle vorher rot): `test_keine_eigene_fassung_der_meldung` (keine Zeichenkette unter `app/`
  außer `app/meldungen.py` und keine Vorlage enthält die Meldung selbst; genau die sechs Vorlagen nehmen den Global),
  `test_seiten_zeigen_die_gemeinsame_meldung` (fünf gezeichnete Seiten tragen sie), `test_server_meldet_die_gemeinsame_meldung`
  (Zeiterfassung und Monteursansicht als Konto ohne Mitarbeiter: 403/422 mit genau der Meldung). Klicktest `klicktest_backoffice_buero`
  prüft im Browser genau die neue Meldung (Konto „Fin“ ohne Mitarbeiter): 23/23.
- **Angepasste Erwartungen** (Regel 28): `tests/test_v100_time_tracking.py::test_time_tracking_ui_loads_core_data_independently_and_auth_exposes_employee_id`
  -- alt „keinem Mitarbeiter zugeordnet“ im Quelltext von `time_tracking.html`, neu `{{ kein_mitarbeiter|tojson }}`; Klicktest
  `klicktest_backoffice_buero` -- alt enthält „keinem Mitarbeiter zugeordnet“, neu enthält die ganze neue Meldung.

#### Liste alt → neu (20 Stellen, neu jeweils „Dein Konto ist keinem Mitarbeiter zugeordnet. Ein Administrator kann das unter Einstellungen → Benutzer und Zugriff ändern.“)

| Datei:Zeile | alt |
|---|---|
| `app/templates/dashboard.html:87` | Ihr Benutzer ist keinem Mitarbeiter zugeordnet – Aufgaben können nicht angezeigt werden. |
| `app/templates/field_timesheet.html:125` | Ihr ERP-Benutzer ist keinem Mitarbeiter zugeordnet. Bitte unter Einstellungen → Benutzer & Zugriff einen Mitarbeiter zuordnen lassen. |
| `app/templates/service_reports.html:1377` | Ihr Benutzer ist keinem Mitarbeiter zugeordnet – Zeit buchen ist nicht möglich. |
| `app/templates/time_backoffice.html:60` | Ihr Konto ist keinem Mitarbeiter zugeordnet und hat keine eigenen Anträge – die Anträge anderer sieht und entscheidet ein Administrator. |
| `app/templates/time_tracking.html:55` | Ihr ERP-Benutzer ist keinem Mitarbeiter zugeordnet. Bitte unter Einstellungen → Benutzer & Zugriff einen Mitarbeiter zuordnen lassen. |
| `app/templates/time_tracking_field.html:515` | Ihr ERP-Benutzer ist keinem Mitarbeiter zugeordnet. Bitte unter Einstellungen → Benutzer & Zugriff einen Mitarbeiter zuordnen lassen. |
| `app/routers/absence_requests.py:37` | Ihr ERP-Benutzer ist keinem Mitarbeiter zugeordnet. |
| `app/routers/checklists.py:99` | Ihr Konto ist mit keinem Mitarbeiter verknüpft. |
| `app/routers/field_defects.py:42` | Ihr ERP-Benutzerkonto ist keinem Mitarbeiter zugeordnet -- bitte einen Administrator kontaktieren. |
| `app/routers/field_view.py:121` | Ihr ERP-Benutzerkonto ist keinem Mitarbeiter zugeordnet -- bitte einen Administrator kontaktieren. |
| `app/routers/field_view.py:221` | Ihr ERP-Benutzerkonto ist keinem Mitarbeiter zugeordnet. |
| `app/routers/maintenance_contracts.py:212` | Ihr ERP-Benutzerkonto ist keinem Mitarbeiter zugeordnet. |
| `app/routers/time_tracking.py:46` | Ihr ERP-Benutzer ist keinem Mitarbeiter zugeordnet. |
| `app/routers/time_tracking.py:169` | Ihr ERP-Benutzer ist keinem Mitarbeiter zugeordnet. |
| `app/routers/time_tracking.py:187` | Ihr ERP-Benutzer ist keinem Mitarbeiter zugeordnet. |
| `app/routers/time_tracking.py:311` | Ihr ERP-Benutzer ist keinem Mitarbeiter zugeordnet. |
| `app/routers/work_preparation.py:44` | Ihr ERP-Benutzer ist keinem Mitarbeiter zugeordnet. |
| `app/tasks.py:167` | Ihr Büro-Konto ist keinem Mitarbeiter zugeordnet. |
| `app/tasks.py:197` | Ihr Büro-Konto ist keinem Mitarbeiter zugeordnet. |
| `app/time_tracking.py:412` | Ihr ERP-Benutzer ist keinem Mitarbeiter zugeordnet. |

### Punkt 4 (1.8.160): Wächter „Kundentexte beim Sie, Oberfläche beim Du“

Umgesetzt wie im Befund vorgeschlagen (`docs/archiv/befund-du-statt-sie.md`, „Vorschlag: Wächter-Test“), in
`tests/test_v440_runde_du.py`. Kein Text geändert.

- **Verzeichnis `KUNDENTEXTE`**: je Datei die Namen auf oberster Ebene, deren Zeichenketten an Kunden gehen -- die Vorgaben der
  E-Mails (`DEFAULT_*_EMAIL_BODY` in `projects.py`, `orders.py`, `invoices.py`, `reminders.py`, `contract_versions.py`,
  `checklist_email.py`, `notice_letters.py::DEFAULT_EMAIL_BODY`), die Briefe (`notice_letters.py`: `INTRO`, `salutation_line`,
  `build_letter_content`), die Sätze der Rechnung (`refund_sentence`, `payment_note_sentence`), die Standardsätze
  (`option_settings.py::DEFAULT_OPTION_GROUPS`), die Mahntexte (`reminders.py::DEFAULT_REMINDER_LEVELS`, Migration `8e2f4b6d1c97`:
  `OLD_TEXTS`, `NEW_TEXTS`); die neun PDF-Renderer an Kunden als ganze Datei (`checklist_pdf`, `contract_pdf`, `document_pdf`,
  `invoice_pdf`, `notice_letter_pdf`, `order_pdf`, `quote_framed_pdf`, `reminder_pdf`, `service_report_pdf`); dazu
  `KUNDENTEXTE_PLATZHALTER` -- die zwei Platzhalter in `settings.html` über ihre id (`ptTextTemplate`, `rl${x.id}EmailBody`).
  Zusammen 2201 Zeichenketten, 31 davon mit Sie-Anrede.
- **`test_verzeichnis_der_kundentexte_ist_aktuell`**: jede Datei und jeder Name existiert und trägt Text -- ein umbenannter Kundentext
  fiele sonst still aus der Prüfung.
- **`test_kundentexte_ohne_du`**: keine Zeichenkette des Verzeichnisses enthält eine Du-Form (du, dich, dir, dein…, euch, euer…,
  eure… als ganzes Wort, groß oder klein).
- **Echte PDFs aus Testdaten** (`test_pdfs_an_kunden_ohne_du`, `test_behinderungsanzeige_als_brief_ohne_du`,
  `test_bedenkenanzeige_als_brief_ohne_du`): Angebot mit dem Standard-Vortext, Auftrag, Vertrag, Rechnung mit Erstattung, Mahnung,
  Behinderungs- und Bedenkenanzeige als Brief (die Fassung aus der Ablage) -- Text über pypdfium2 (`test_v325::pdf_text`), keine
  Du-Form, und der Kundentext per Sie steht darin („Vielen Dank für Ihre Anfrage“, „Ihr Angebot“, „überweisen wir Ihnen“, „Bitte
  begleichen Sie“, „hiermit zeigen wir Ihnen an“, „hiermit melden wir Ihnen Bedenken“) -- sonst prüfte der Test nichts.
- **`test_kundentext_merkmal_nur_im_verzeichnis`**: jede Zeichenkette mit „Sehr geehrte“, „anbei erhalten“, „Mit freundlichen
  Grüßen“ oder „überweisen wir Ihnen“ unter `app/`, in den Migrationen und den Betreiber-Skripten steht im Verzeichnis; in den
  Vorlagen nur in den eingetragenen Platzhaltern. Sonst Datei und Zeile.
- **`test_ausserhalb_der_kundentexte_keine_sie_anrede`**: außerhalb des Verzeichnisses keine Sie-Anrede (Sie, Ihnen, Ihr…) --
  Oberfläche, Meldungen des Servers, Ausgaben der Skripte. „Sie“ als dritte Person steht in `DRITTE_PERSON` (Datei, Text ab dem
  Treffer, Bezug): 7 Einträge für 8 Stellen (Adressimport „Sie erscheint …“, Checkliste ×2, Stornorechnung, Planstunden, verworfene
  Unterschriften, `amount_block_reason` ×2). Ein Eintrag, den nichts mehr braucht, lässt den Test scheitern; die Liste darf nur kürzer
  werden (höchstens 7). Gescannt wie im Befund: Zeichenketten ohne Docstrings, freistehende Zeichenketten und Protokollaufrufe,
  Vorlagen ohne Kommentare.
- **Gegenproben** (Marker `GEGENPROBE`, je Probe byte-genau zurück, Prüfsummen verglichen; `test_v357` jeweils mit rot):
  G1 im Mahntext „Bitte begleichen Sie“ → „Bitte begleiche du“ -- rot `test_kundentexte_ohne_du` (`app/reminders.py:113: 'du'`) und
  `test_pdfs_an_kunden_ohne_du` (Mahnung: `['du']`); G2 in der Einleitung der Behinderungsanzeige „Ihnen“ → „dir“ -- rot
  `test_kundentexte_ohne_du` und `test_behinderungsanzeige_als_brief_ohne_du`; G3 eine neue Zeichenkette „Sehr geehrte Damen und
  Herren“ in `app/tasks.py` -- rot `test_kundentext_merkmal_nur_im_verzeichnis`; G4 „für dich“ → „für Sie“ in `app/routers/tasks.py`
  und „bei deinen Aufgaben“ → „bei Ihren Aufgaben“ in `tasks.html` -- rot `test_ausserhalb_der_kundentexte_keine_sie_anrede` mit
  beiden Stellen; G5 „Sie erscheint dann nicht mehr“ → „Die Adresse erscheint …“ in `address_import.html` -- rot derselbe Test,
  „nicht mehr gebraucht -- aus DRITTE_PERSON streichen“; G6 im Platzhalter `ptTextTemplate` „Bitte begleichen Sie“ → „Bitte
  begleiche du“ -- rot `test_kundentexte_ohne_du`.
- **Angepasste Erwartungen** (Regel 28): keine.

#### Festlegungen 1.8.160 (Bitte bestätigen)

1. Das Verzeichnis nennt Namen auf oberster Ebene; `DEFAULT_OPTION_GROUPS` steht als Ganzes darin (auch Einheiten und andere
   Auswahllisten, die keine Kundentexte sind), die neun PDF-Renderer an Kunden als ganze Datei. `field_timesheet_pdf.py` (Stundenzettel
   des Mitarbeiters) gilt als Oberfläche, nicht als Kundentext.
2. „Sie“ als dritte Person bleibt mit Bezug in `DRITTE_PERSON` (7 Einträge, 8 Stellen), statt umformuliert zu werden.
3. Geprüft wird, was ein Nutzer sehen kann: Zeichenketten unter `app/`, in `alembic/versions/` und in `scripts/erstes_konto.py`,
   `scripts/reset_admin_2fa.py`, dazu alle Vorlagen ohne Kommentare; Docstrings, freistehende Zeichenketten und Protokollaufrufe
   zählen nicht.
4. Texte, die ein Admin in den Einstellungen selbst einträgt (E-Mail-Vorlagen, Mahntexte, Standardsätze), prüft der Wächter nicht --
   nur die Vorgaben im Code und die PDFs aus Testdaten.

### Punkt 5 (Befund, nur docs/): die erste Design-Datei nach dem Serverstart

Frage: Warum braucht die erste Design-Datei nach dem Serverstart im Klicktest-Server rund 500 ms, allein aber 47 ms? Nur gemessen,
nichts geändert.

**Messaufbau.** Wie der Klicktest-Server: Wegwerf-SQLite mit Grunddaten und einem Konto (ohne Konto antwortet seit 1.8.130 jede Seite
mit 503), `ERP_ENV=development`, `python -m uvicorn app.main:app --log-level trace` mit der Log-Konfiguration aus
`scripts/cdp_klicktest.py::log_konfiguration()`. Bereit ist der Server, sobald `/login` 200 liefert (wie `_warte_auf()`). Danach per urllib
`ds.css`, zwei Schriften und noch einmal `ds.css`, je drei Läufe. Zum Zerlegen lief derselbe Server in einem Hilfsskript mit Zeitmessern
an den Schritten: StaticFiles, FileResponse, `mimetypes`, `anyio.to_thread`, BaseHTTPMiddleware, `_IncludedRouter.effective_candidates`.
Dazu ein GC-Rückruf und Stichproben der Aufrufkette. Alles nur im Messprozess, nichts in `app/`.

| | erste Design-Datei | weitere Design-Dateien |
|---|---|---|
| Server wie im Klicktest, ohne andere Last | 321–336 ms | 2–19 ms |
| derselbe mit Zeitmessern | 339–348 ms | 2–4 ms (im Server) |
| vier solche Server zugleich | 380–458 ms | 3–24 ms |

**Zerlegung der ersten Anfrage** (339–348 ms, je Lauf gleich):
- **308–315 ms: FastAPI baut die Routen der eingebundenen Router auf.** In der installierten FastAPI 0.141.1 bleibt jedes
  `include_router()` ein `_IncludedRouter`. Der baut seine Routen erst beim ersten Abgleich auf (`effective_candidates()` →
  `_EffectiveRouteContext.from_api_route`: Abhängigkeiten, pydantic-Schemas), je Router einmal, danach zwischengespeichert. Die App hat
  oben 71 Einträge: 70 eingebundene Router und als letzten den Mount `/static` (`app/design_dateien.py::einbinden()`).
  - `/login` passt schon im ersten Router (pages): aufgebaut 1 Router mit 54 Routen in 7 ms.
  - Die erste Design-Datei passt erst am Mount und läuft dabei an allen 69 übrigen Routern vorbei: aufgebaut 69 Router mit 703 Routen
    in 308–315 ms (auf der Event-Loop; in den Stichproben `pydantic/_internal/_generate_schema.py`).
  - Danach kostet derselbe Weg nichts mehr (0 Router aufgebaut).
- **25–30 ms: `mimetypes.init()`** beim ersten `guess_type()`. Starlettes FileResponse ohne `media_type` liest dafür unter Windows die
  Registry, obwohl DesignDateien den Typ danach fest setzt.
- Rest unter 5 ms (check_config, lookup_path, Senden).

**Warum allein 47 ms:** Die Einzelmessung lief mit DesignDateien ohne die 70 Router, dort fehlt der Aufbau. Ihre 28 ms für `mimetypes`
und 15 ms für Importe passen zur Zerlegung.

**Warum damals rund 500 ms:** `klicktest_anmelden` läuft allein (`ALLEIN`), nicht neben anderen Klicktests. Die erste Fassung dieses
Befunds (Commit `e82e41d`) nannte hier fälschlich vier Klicktests zugleich. Im Endlauf auf `3463e2c` brauchte die erste Design-Datei
dort 364 ms (Verbindungsprotokoll; allein, Chrome lädt die Seite zugleich), passend zu 321–348 ms ohne Chrome. Die 509 ms im Endlauf
der Stufe „Grundlage“ sind dieselbe Arbeit bei mehr Last auf dem Rechner; welche Last das war, lässt sich nicht mehr feststellen. Wie
stark Last die Zeit streckt, zeigen vier Server zugleich: 380–458 ms.

**Folgen:**
- **Klicktest:** Die erste Seite nach dem Start wartet 0,35–0,5 s auf `ds.css`. Das war der Anlass der Wartebedingung in
  `klicktest_anmelden` (1.8.156, Nachtrag).
- **Betrieb:** Jeder der zwei gunicorn-Arbeitsprozesse zahlt den Aufbau einmal nach dem Neustart, bei der ersten Anfrage, die an Routern
  vorbeiläuft. Auf dem VPS mit zwei Kernen eher länger. Danach nie wieder. Kein Fehler, nur eine einmalige Verzögerung.
- Das betrifft nicht nur Design-Dateien: Jede erste Anfrage an einen Router weit hinten baut alle Router davor auf.

**Möglichkeiten** (nicht umgesetzt, Punkt 5 heißt nur messen):
- den Aufbau beim Start vorwegnehmen: ein Startereignis, das jede `_IncludedRouter.effective_candidates()` einmal aufruft (private API von
  FastAPI);
- den Mount `/static` vor die Router setzen: dann zahlt die Design-Datei nichts, die erste API-Anfrage weiterhin;
- `mimetypes.init()` beim Start aufrufen oder FileResponse mit festem `media_type` bauen.

### Nachtrag (Endlauf der Runde „Du“): `test_v252` rot -- der neue Jinja-Global aus 1.8.159

- **Befund**: Die volle Suite auf `e82e41d` hatte einen roten Test, `tests/test_v252_deployment_hardening.py::
  test_no_further_database_backed_jinja_globals_exist_unguarded` („assert 8 == 7“). Der Test zählt die Zuweisungen
  `templates.env.globals[…]` in `app/routers/pages.py`. Mit `kein_mitarbeiter` (Punkt 3, 1.8.159) sind es acht.
- **Eigener Fehler**: Vor dem Commit von 1.8.159 lief nur `tests/test_v440_runde_du.py` und die angepassten Tests, nicht die volle Suite
  (Regel 15). Sonst wäre der Test dort rot geworden.
- **Änderung**: `kein_mitarbeiter` ist wie `app_version` eine feste Zeichenkette ohne Datenbank und braucht keine Absicherung. Der Test
  erwartet jetzt acht Zuweisungen und prüft zusätzlich, dass `kein_mitarbeiter` genau die Konstante `KEIN_MITARBEITER` aus
  `app/meldungen.py` bekommt. Eigener Commit „1.8.159 (Nachtrag)“; Suite und Klicktests danach neu (Regel 26).
- **Angepasste Erwartung** (Regel 28): `test_v252::test_no_further_database_backed_jinja_globals_exist_unguarded` -- alt 7 Zuweisungen
  (`app_version`, fünf abgesicherte Globals mit Datenbank, `can`), neu 8 (dazu `kein_mitarbeiter`, nur die Konstante).

### Endlauf der Runde „Du“ (Regel 26)

- **Erster Lauf auf `e82e41d`**: volle Suite 6201 grün, 3 übersprungen, 1 rot (`test_v252`, siehe Nachtrag oben), 7:25 min. Klicktests nicht
  gestartet, weil der Stand danach ohnehin neu lief.
- **Endstand `3463e2c`** (saubere Arbeitskopie): volle Suite `pytest -q -n 16 --dist loadfile` 6202 grün, 3 übersprungen, 0 rot, 7:20 min;
  `klicktest_alle.py --gleichzeitig 4` 79 von 79 wie erwartet, 1775 von 1775 Prüfungen, 7:01 min (sechs allein: `klicktest_abschliessen`,
  `klicktest_anmelden`, `klicktest_feierabend`, `klicktest_fremde_seite`, `klicktest_hochladen`, `klicktest_veraltete_antworten`).
- Danach nur `docs/` geändert (Korrektur im Befund zu Punkt 5, dieses Ergebnis) -- kein neuer Endlauf (Regel 26).

## Stufe 2 „Rahmen“: Befund (nur docs/, nichts geändert)

Vorgabe vom 20.10.2026 und der ganze Befund mit Zahlen, Mustern und Vorschlag: `docs/archiv/befund-rahmen.md`. Gemessen in einer Instanz wie
die Bildgrundlage (Stand `7c5172c`, Chrome 155.0.8059.40), Bilder aus `bildgrundlage/31b85e8`. Kurz:

- **Seitenleiste**:
  - 17 Einträge in 6 Gruppen (Finanzen, Admin), 15 (Auftrag), 2 (Monteurin, nur auf Einsatzbericht und Konto).
  - Ohne Bildlauf braucht sie 1014 px Fensterhöhe (Auftrag 938) -- bei 900 px sind 114 px verdeckt, bei 800 px 214.
  - Das Logo kostet seine Höhe + 41 px (Vorgabe 64 → Kopf 105 statt 62 px).
  - Vier Gruppen mit Logo 48: 971 px (Auftrag 900) -- bei 800 px scrollt sie weiter.
  - Der aktive Eintrag hängt am genauen Pfad: 21 der 42 Seiten mit Leiste markieren keinen.
- **Seitenköpfe**: 11 Muster, jede Seite baut ihren Kopf selbst (kein Baustein).
  - Pfad auf 10 Seiten (10 Umsetzungen), Kennung und Status je auf 8 Seiten an drei bis vier verschiedenen Orten.
  - Zurück-Link auf 12 Seiten mit acht Wortlauten, „⋮“ nur in der Projektmappe.
  - Titel von 15 bis 32 px, 14 Seiten ohne h1.
- **Monteurskopf**: 173 px (auf drei Seiten 188, weil deren `button`-Regel in den Kopf greift).
  - Bei 1280 × 620 sind das 28–30 % des Fensters.
  - Auf Einsatzbericht und Konto fehlt der Monteurin der Name, den der Kopf eigens immer zeigt -- ausgerechnet dort, wo sie unterschreibt.
- **Probe mit den --ds-*-Werten** (nur im Browser):
  - Kein waagrechter Bildlauf, nichts abgeschnitten, Seiten 0,9 % kürzer.
  - Die Seitenleiste wird dunkel; hell 612 → 584 Kontrast-Fehlstellen, dunkel 578 → 598.
  - Die meisten Fehlstellen bestehen schon heute: Weiß auf der Akzentfarbe `#0d9488` hat 3,74 : 1.
  - Die Statusfarben sind heute Textfarben (`--danger` 127 × Text, 5 × Fläche), im ds Flächenfarben.
  - Auf 28 Seiten stehen Steuerelemente in Arial; Regel 37 lässt in `ds.css` keine Grundregeln für Schrift und Steuerelemente zu.
- **Vorschlag**:
  - Makro `teile/seitenkopf.html` mit wörtlichen Teilen über `{% call %}` (Makro-Regel), Skript `seitenkopf()` für nachgeladene Köpfe,
    `.ds-kopf`-Regeln, `bereich` für den aktiven Eintrag.
  - Reihenfolge in 11 Schritten vom Pilot (Prüfvorlagen) bis zur Monteursansicht; sieben Entscheidungen vorab.

## Stufe 2 „Rahmen“, Runde 1 (1.8.161 ff.)

Vorgabe vom 20.10.2026 (übernommen wie gegeben): „Stufe 2 „Rahmen“, Runde 1. Entscheidungen von Tobias für die ganze Stufe 2: - Hauptaktion in --ds-aktion; die Akzentfarbe aus den Einstellungen färbt die Oberfläche künftig nicht mehr (App-Symbol bleibt vorerst). - Ecken 10 px Knöpfe/Felder, 12 px Karten, Tablet 12/16 px. Seitentitel 30 px, Tablet 26 px. - Seitenleiste dunkel in beiden Modi, vier Gruppen. - Grundregeln für Schrift und Steuerelemente in eigener Datei ds-basis.css, nur unter .ds-seite; eine Seite schaltet beim Umzug um. Regel 37 bleibt. - Formularseiten bekommen den Rahmen. Einsatzbericht und Konto der Monteure kommen in den Monteursrahmen (ersetzt Festlegung 1.8.113 Nr. 6). Diese Runde, ein Commit je Teil: 1. Baustein ohne sichtbare Änderung: ds-basis.css, Makro teile/seitenkopf.html, Skript seitenkopf(), `bereich` je Seite. Wächter: jede Seite mit Leiste nennt ihren Bereich. 2. Seitenleiste: 232 px, navi-Farben, Logo-Zeile 52 px (Kachel 36 px, „DACHKONZEPTE“ / „Rödchen GmbH · ERP“). Gruppen: Übersicht (Start, Aufgaben, Kalender) · Aufträge (Anfragen, Projekte, Plantafel, Checklisten, Wartungen, Befunde eingerückt) · Kaufmännisch (Finanzen, Mahnwesen, Eingangsrechnungen, Betriebskosten, Zeiterfassung, Backoffice) · Verwaltung (Stammdaten, Einstellungen). Zeilen 36 px, Schrift 14 px, Symbole 18 px. Aktiv: navi-aktiv mit 3 px Strich links in marke-hell, gesetzt über `bereich`. Fuß nur „Version …“. 3. Kopfzeile Büro: 64 px, Suche 480 px breit, rechts Kontoknopf mit Initialen (Kreis in aktion) und vollem Namen. Menü: Mein Konto, Hell/Dunkel, Abmelden. 4. Monteurskopf: 64 px, navi-grund, Logo-Kachel 40 px, Reiter Einsätze · Zeiterfassung · Stundenzettel (48 px hoch, 16 px Schrift, aktiv mit 3 px Strich unten in marke-hell). Rechts: Lupe 48 px, öffnet die bisherige Objektsuche; Kontoknopf mit Initialen und vollem Namen, Menü wie oben. Gilt für alle Monteursseiten samt Einsatzbericht und Konto. Die button-Regeln dreier Seiten dürfen nicht mehr in den Kopf greifen. Prüfen: Leiste ohne Bildlauf bei 1440 × 900 in jeder Rolle. Monteurskopf 64 px und einzeilig bei 1280 × 620 und 800 × 1100, Name immer sichtbar. Menüs per Tastatur bedienbar, mit aria. Hell und dunkel. Bildvergleich: außer Leiste, Kopfzeile und Monteurskopf weicht nichts ab. Am Ende: volle Suite und Klicktests auf sauberer Arbeitskopie, Bericht je Teil. Dazu als ZIP je ein Bild: Projektmappe 1440 × 900 hell und dunkel, Einsatzbericht als Monteurin 1280 × 620 und 800 × 1100. Nicht pushen.“

Grundlage: der Befund `docs/archiv/befund-rahmen.md`. Die Entscheidungen oben gelten für die ganze Stufe 2; Festlegung 1.8.113 Nr. 6
(Konto der Monteurin mit Seitenleiste) ist damit ersetzt.

### Teil 1 (1.8.161): Baustein ohne sichtbare Änderung

- **`app/static/ds/ds-basis.css`** (neu): Grundregeln einer umgezogenen Seite -- Schrift (IBM Plex Sans, 15 px, Tablet 17 px), Farben
  von Grund und Text, Titel in Archivo, `font:inherit` für Steuerelemente, Felder mit Rand `feld-rand` und Ecke 10 px (Tablet 12 px),
  Links, Fokus. Jede Regel nur unter `.ds-seite` (die Klasse setzt eine Seite beim Umzug an ihr `<body>`, für das Tablet dazu
  `.ds-tablet`); keine `--ds-*`-Werte, keine At-Regeln, kein `!important`. `_ds_kopf.html` bindet sie auf jeder Seite nach `ds.css` ein
  -- ohne `.ds-seite` wirkt nichts. Regel 37 für `ds.css` bleibt.
- **`ds.css`**: Werte nach den Entscheidungen -- `--ds-groesse-9` (Seitentitel) 30 statt 38 px, neu `--ds-groesse-9-tablet` 26 px;
  `--ds-ecke-tablet` (20 px) ersetzt durch `--ds-ecke-tablet-feld` 12 px und `--ds-ecke-tablet-karte` 16 px. Dazu Regeln für Bausteine,
  alle mit einer `.ds-`-Klasse als Ziel (Regel 37): Seitenkopf `.ds-kopf…`, Knöpfe `.ds-knopf`, `.ds-knopf-aktion` (Hauptaktion in
  `--ds-aktion`), `.ds-knopf-symbol`, Menü `.ds-menue`, `.ds-menue-eintrag`, Status `.ds-status-<art>`. Jede setzt ihre Maße selbst
  (Höhe, Breite, Hintergrund, Schrift), damit Element-Regeln einer Seite sie nicht verschieben. Leere Teile des Kopfes blendet `:empty` aus.
- **Makro `app/templates/teile/seitenkopf.html`**: `{% call(teil) seitenkopf(titel, untertitel, kennung, mit_pfad, mit_aktion,
  mit_menue) %}` -- Pfad (`nav`, aria-label), Kennung, genau ein h1, Status (`role="status"`), Untertitel, Hauptaktion, Menü „⋮“
  (`aria-haspopup`, `aria-expanded`, `aria-controls`). Pfad-Links, Hauptaktion und Menüeinträge schreibt die Seite wörtlich in den
  Aufruf -- so bleibt die Makro-Regel (kein Jinja in `href`/`type`/`on…` im Makro) eingehalten und die Scanner sehen sie.
- **`_seitenkopf.html`**: `seitenkopf({kennung, titel, untertitel, status, pfad})` für Köpfe, deren Daten nachgeladen werden -- Text nur
  über `textContent`, Links über `sichererLink()`, Status-Art aus fester Liste (`neutral`, `info`, `ok`, `warn`, `fehler`, `signal`),
  Trenner „/“, letztes Glied ohne Link mit `aria-current="page"`. Importiert das Makro (sonst zählte `seiten()` es als 54. Seite).
- **`_menue.html`** (neu): `dsMenue(knopf, liste)` -- eine Umsetzung für das Menü „⋮“ und die Kontomenüs (Teil 3 und 4), nach dem
  Muster „Menu Button“: role `menu`/`menuitem`, aria, Klick/Enter öffnen mit Fokus auf dem ersten Eintrag, Pfeile, Pos1/Ende, Escape
  schließt mit Fokus zurück, Tab und Klick daneben schließen.
- **`bereich` je Seite**: jede der 42 Seiten mit Seitenleiste beginnt mit `{% set bereich = "…" -%}` (Teil 2 markiert danach den
  Eintrag); das `-` vor `%}` nimmt den Zeilenumbruch mit, die Seite beginnt weiter mit `<!doctype html>`. Zuordnung: Projektmappe,
  Angebot, Auftrag, Arbeitsvorbereitung, Einsatzbericht, Rechnung → `projekte`; Wartungsvertrag, Prüfvorlagen, Prüfvorlage →
  `wartungen`; Kunde, Objekt, Dachfläche, Betriebsmittel, Leistungskatalog → `stammdaten`; Benutzer, Änderungshistorie, Adressimport,
  Versandprotokoll, Changelog → `einstellungen`; Checklisten-Seiten → `checklisten`; Suche, Konto → `keiner`; sonst der eigene Eintrag.

#### Tests und Prüfung

- Neu `tests/test_v441_rahmen_baustein.py` (26 Tests): Wächter `ds-basis.css` (nur unter `.ds-seite`, keine Werte, keine At-Regeln, kein
  `!important`; 7 Gegenbeispiele, ein Durchlass), auf jeder Seite einmal nach `ds.css` geladen, noch keine Seite mit `.ds-seite`
  (`UMGEZOGEN`); Makro gerendert mit allen und ohne Teile (ein h1, IDs, aria, Text maskiert), Makro-Regel; `dsMenue()` und
  `seitenkopf()` in node mit einem kleinen DOM-Nachbau (Tastatur, aria, schließen; Text als Text, `javascript:` → `#`, unbekannte
  Art → neutral, nur genannte Teile ändern sich); `bereich` auf allen 42 Seiten mit Leiste, auf keiner ohne, als erste Anweisung
  (4 Gegenbeispiele); Seiten beginnen weiter mit `<!doctype html>`.
- **Gegenproben** (Regel 24, je Datei byte-genau zurück): Regel ohne `.ds-seite` in `ds-basis.css`; Seite ohne `bereich`; Menüknopf
  ohne `aria-expanded`; Escape ohne Fokus zurück; Titel als HTML; Pfad ohne `sichererLink()` -- 6 von 6 rot, je mit `test_v357`.
- **Angepasste Erwartung** (Regel 28): `tests/test_v432_design_fundament.py::test_ds_kopf_bindet_nur_ds_css_mit_version_ein` -- alt
  genau ein Link (`ds.css`), neu zwei (`ds.css`, danach `ds-basis.css`).

#### Festlegungen 1.8.161 (Bitte bestätigen)

1. **`ds-basis.css` lädt jede Seite**, wirksam erst mit `.ds-seite` am `<body>` -- kein Umschalten der Links beim Umzug.
2. **Tablet-Werte als eigene Token**: `--ds-groesse-9-tablet` 26 px, `--ds-ecke-tablet-feld` 12 px, `--ds-ecke-tablet-karte` 16 px;
   die Seite schaltet sie mit `.ds-tablet` zu.
3. **Bausteine in `ds.css`** (Seitenkopf, Knopf, Menü, Status) -- erlaubt nach Regel 37, weil jedes Ziel eine `.ds-`-Klasse trägt;
   Seitenleiste, Kopfzeile und Monteurskopf behalten ihre Regeln im eigenen Baustein (sie brauchen `@media`, das `ds.css` nicht zulässt).
4. **Pfad-Trenner „/“** (bisher „·“ auf 8 und „/“ auf 2 Seiten).
5. **Ein Menü für alle**: `_menue.html` für „⋮“ und die Kontomenüs.
6. **`bereich` als erste Anweisung der Vorlage**, Zuordnung wie oben (Prüfvorlagen unter Wartungen, Leistungskatalog unter Stammdaten,
   die System-Seiten unter Einstellungen, Suche und Konto ohne Bereich).

### Teil 2 (1.8.162): Seitenleiste

- **`_sidebar.html`** neu: 232 px, Farben nur aus `--ds-navi-*` (dunkel in beiden Modi) -- nicht mehr aus den `--sidebar-*`-Werten
  der Seiten und nicht aus der Akzentfarbe. **Logo-Zeile 52 px**: Kachel 36 px (Logo der Leiste bzw. Firmenlogo auf weißer Kachel,
  ohne Logo ein Dach auf `marke-hell`), daneben „DACHKONZEPTE“ (Archivo 14 px) / „Rödchen GmbH · ERP“ (11,5 px, `navi-leise`).
  **Vier Gruppen**: Übersicht (Start, Aufgaben, Kalender) · Aufträge (Anfragen, Projekte, Plantafel, Checklisten, Wartungen, Befunde
  eingerückt) · Kaufmännisch (Finanzen, Mahnwesen, Eingangsrechnungen, Betriebskosten, Zeiterfassung, Backoffice) · Verwaltung
  (Stammdaten, Einstellungen); eine Überschrift nur, wo die Rolle etwas sieht, Rollen- und Modulbedingungen unverändert. **Zeilen**
  36 px, Schrift 14 px (IBM Plex Sans), Symbole 18 px. **Aktiv** ist der Eintrag mit `data-bereich` gleich dem `bereich` der Seite
  (Teil 1): `navi-aktiv` mit 3 px Strich links in `marke-hell`, `aria-current="page"`. **Fuß** nur „Version …“ (dazu das leere
  `#appSidebarFoot` für eine abgelaufene Sitzung). Eingeklappt 60 px (Kachel und Symbole), schmal wie bisher außerhalb.
- **Was die Leiste abgibt, in die Kopfzeile** (`_topbar.html`, Teil 3 baut sie danach um): der Menüknopf `#appTopbarMenuBtn` ist
  auch am Desktop sichtbar und klappt dort ein (localStorage `erp_sidebar_collapsed`, wie bisher der Knopf unten in der Leiste),
  schmal öffnet er die Leiste; Hell/Dunkel (`#appThemeToggle`) steht im Kontomenü.
- **Gemessen** (Instanz der Bildgrundlage, Chrome 155, vor der letzten Feinabstimmung): Leiste 232 px, Kopf 52 px, Fuß 31 px,
  Navigation bei 17 Einträgen 724 px -- ohne Bildlauf ab 807 px Fensterhöhe; bei 1440 × 900 in allen vier Rollen kein Bildlauf.
  Danach 2 px weniger Abstand über den Gruppen und unten: rund 799 px, die Leiste passt auch bei 1280 × 800.

#### Tests und Prüfung

- `tests/test_v441_rahmen_baustein.py` um zwei Tests: die Bereiche sind genau die `data-bereich` der Leiste (+ „keiner“); jede der 42
  Seiten mit Leiste, gezeichnet als Admin, markiert genau ihren Bereich mit `aria-current` (Suche und Konto keinen).
- `scripts/bildgrundlage.py`: Zustand „Leiste eingeklappt“ über den Menüknopf der Kopfzeile; „Leiste ganz unten“ entfällt (die Leiste
  scrollt bei 1440 × 900 nicht mehr), dafür prüft das Aufnehmen bei „Kontomenü offen“ und „Leiste von Büro – Auftrag“, dass die Leiste
  ohne Bildlauf passt. 302 statt 304 Bilder.
- Klicktests `klicktest_neue_ordnung` 81/81, `klicktest_monteur_navigation` 27/27, `klicktest_dateien_nie_aktiv` 42/42.
- **Gegenproben** (Regel 24): aktiv nach Adresse statt `bereich`; Eintrag ohne `data-bereich`; Hell/Dunkel nicht im Kontomenü;
  Menüknopf am Desktop versteckt -- 4 von 4 rot, je Datei byte-genau zurück.
- **Angepasste Erwartungen** (Regel 28):
  - `test_v253_sidebar_layout`: die neun Tests zu Kopf, Logo und Knöpfen unten (Logo allein im Kopf, Schriftzug als Ersatz, zentriert,
    Höhe 24–120 px als Inline-Maß, eingeklappt 32 px, Schriftzug eingeklappt aus, beide Knöpfe unten, Einklappen nie versteckt, Gruppen
    Stammdaten/System) ersetzt durch: Kachel mit Logo und Schriftzug ohne Knöpfe, Dach ohne Logo, 52 px Kopf/36 px Kachel/232 px, die
    eingestellte Höhe wirkt nicht mehr, eingeklappt 60 px, Fuß nur Version, Hell/Dunkel im Kontomenü und Einklappen am Menüknopf
    (außerhalb der Leiste, nie versteckt), vier Gruppen in Reihenfolge, aktiv über `bereich`.
  - `test_v258::test_bottom_area_still_shows_both_buttons_and_the_version` → `…_shows_only_the_version_since_1_8_162`: alt beide
    Knöpfe und Version, neu nur die Version.
  - `test_v249`: Schriftzug ohne Logo -- alt `app-sidebar-brand`, neu `app-sidebar-marke-name`; Logo vorhanden -- alt ohne Schriftzug,
    neu Kachel `mit-logo` (Schriftzug bleibt); `…_uses_configured_height_as_inline_style` → `…_sits_in_a_fixed_tile_since_1_8_162`:
    alt Inline-Höhe, neu keine; Begrenzung auf dem umschließenden Element -- alt `app-sidebar-logo-wrap`, neu die Kachel (nur Aufbau).
  - `test_v242`: Gruppen -- alt „Stammdaten“ und „System“, neu „Verwaltung“; Backoffice nach der Zeiterfassung -- alt Gruppe „Personal“
    vor „Stammdaten“, neu „Kaufmännisch“ vor „Verwaltung“.
  - `test_v054::test_main_app_sidebar_stays_pinned_while_scrolling`: alt Regel `.app-sidebar{width:240px…`, neu `…232px…` (nur Aufbau).
  - `test_v255`: Menüknopf -- alt am Desktop `display:none`, neu sichtbar; alt sichtbar erst im `@media`-Block, neu derselbe Umbruch
    im Skript (breit einklappen, schmal öffnen); alt `aria-label="Navigation öffnen"`/`aria-expanded="false"`, neu „Navigation ein- und
    ausblenden“, `aria-expanded` vom Skript; die zwei Tests zum alten Knopf in der Leiste (unter 1000 px versteckt, Klick ohne
    `mobile-open`) → einer: es gibt ihn nicht mehr; Scrim-Abgleich und Umschalten -- nur Aufbau (Regex statt Wortlaut).
  - `test_v417::test_seitenleiste_in_gruppen_je_rolle`: alt sechs Gruppen, Monteurin „Personal“; neu vier, Monteurin „Kaufmännisch“
    (bis Teil 4, danach hat sie keine Leiste).
  - `test_v431`: Zustände -- alt mit „leiste_unten“ (24 Bilder, 304 gesamt, Kennung `appSidebarToggle`), neu ohne (22, 302, ohne).
  - Klicktest `klicktest_neue_ordnung`: alt sechs Gruppen, Monteurin „Personal“; neu vier, „Kaufmännisch“.
  - `test_v272_mobile_header_theme_toggle`: Hell/Dunkel des Monteurskopfs -- alt derselbe Mechanismus und dieselben Symbole wie der
    Knopf der Seitenleiste, neu derselbe Mechanismus wie das Kontomenü der Kopfzeile; Symbole nur noch im Monteurskopf geprüft (das
    Kontomenü zeigt Text).

#### Festlegungen 1.8.162 (Bitte bestätigen)

1. **Einklappen am Menüknopf der Kopfzeile**, jetzt auch am Desktop (schmal öffnet er die Leiste wie bisher); Hell/Dunkel im Kontomenü.
2. **Logo in fester Kachel** (36 px, weiß; ohne Logo ein Dach auf `marke-hell`): die einstellbare Höhe des Logos der Leiste wirkt nicht
   mehr -- die Einstellung bleibt bis zur Bereinigung stehen.
3. **Schriftzug fest** „DACHKONZEPTE“ / „Rödchen GmbH · ERP“ wie vorgegeben, nicht aus dem Firmennamen der Einstellungen.
4. **Zeilen ohne Ecken**, der Strich als linker Rand 3 px; Befunde 28 px eingerückt.
5. **Abstände so knapp, dass die Leiste auch bei 1280 × 800 passt** (rund 799 px Bedarf mit 17 Einträgen).
6. **Die `--sidebar-*`-Werte der 42 Seiten bleiben stehen** (ungelesen), bis die Farben der Seiten umziehen.
7. **Monteurin bis Teil 4**: ihre Zeiterfassung steht unter „Kaufmännisch“ (vier Gruppen) -- ab Teil 4 hat sie keine Leiste mehr.

### Teil 3 (1.8.163): Kopfzeile Büro

- **`_topbar.html`** neu: 64 px (Rahmen-Box samt Linie unten), Farben aus `--ds-flaeche`/`--ds-linie`/`--ds-text`, Schrift IBM Plex
  Sans 14 px; links der Menüknopf 40 px (seit 1.8.162 auch am Desktop), daneben die Büro-Suche mit Lupe, 40 px hoch, höchstens
  480 px breit (Logik unverändert: ab zwei Zeichen nach 300 ms, Enter öffnet `/suche`); rechts der Kontoknopf.
- **`_kontomenue.html`** (neu, eine Fassung für Kopfzeile und -- ab Teil 4 -- Monteurskopf): Initialen im Kreis 36 px in
  `--ds-aktion` und der volle Name (`account_display()`), Pfeil; `aria-label="Konto: <Name>"`. Menü `.ds-menue` mit Mein Konto ·
  Hell/Dunkel (mit Zustand „hell“/„dunkel“) · Abmelden, bedient über `dsMenue()` (`_menue.html`, Teil 1): Enter, Pfeil runter/hoch
  öffnen, Pfeile im Kreis, Pos1/Ende, Escape mit Fokus zurück, Tab und Klick daneben schließen, `role=menu`/`menuitem`,
  `aria-haspopup`/`-controls`/`-expanded`. Der Name stand bis 1.8.162 erst im Menü, der Knopf zeigte nur die Initialen in der
  Akzentfarbe. Unter 600 px zeigt die Kopfzeile nur die Initialen (Regel in `_topbar.html`, nicht im Kontomenü).
- **Seitenregeln greifen nicht in den Kopf**: 34 Seiten haben `button:hover`, eine `button:active` (Spezifität 0,1,1). Jede Regel an
  Knopf, Feld oder Treffer des Kopfs trägt deshalb zwei Klassen (0,2,0); `ds.css` hat `:active` (und `text-decoration:none`) für
  `.ds-knopf`, `.ds-knopf-aktion` und `.ds-menue-eintrag`. Anlass im Klicktest: per Leertaste gedrückt (`:active` ohne `:hover`)
  färbte sich ein Knopf mit nur einer Klasse auf den Einstellungen in der Akzentfarbe.
- `_topbar.html` bindet `_speichern.html` nicht mehr selbst ein -- das Abmelden steht im Kontomenü, das ihn einbindet.

#### Tests und Prüfung

- `tests/test_v254_topbar.py`: drei neue Tests -- 64 px, Suche 480 px, Initialen in `--ds-aktion`; jede Regel an Knopf, Feld und
  Treffer des Kopfs mit zwei Klassen, `:active` in `ds.css`; Name nur unter 600 px und nur in der Kopfzeile ausgeblendet --, dazu
  „Kontomenü über `dsMenue()`“.
- **Neuer Klicktest `scripts/klicktest_rahmen.py`** (Testdaten der Bildgrundlage, `--nur TEIL` für Gegenproben): Seitenleiste je Rolle
  bei 1440 × 900 hell/dunkel und 1280 × 800 ohne Bildlauf, Maße, Gruppen; aktiver Eintrag auf acht Seiten; Menüknopf klappt ein und aus;
  Kopfzeile 64 px, Suche 480 px, Name ganz zu sehen, Kreis in aktion, 412 px nur Initialen; Kontomenü per Tastatur mit aria, Hell/Dunkel
  per Enter, Klick daneben; Seitenregeln auf den Einstellungen (Maus und Leertaste). 150 von 150.
- Klicktests `klicktest_anmelden` 69/69 (Abmelden über das Kontomenü), `klicktest_monteur_navigation` 27/27,
  `klicktest_versand_im_kontext` 24/24, `klicktest_neue_ordnung` 81/81.
- **Gegenproben** (Regel 24, pytest und der passende Klicktest-Teil): Kontoknopf mit nur einer Klasse (Klicktest: per Leertaste in der
  Akzentfarbe); Name ausgeblendet; Kontomenü ohne `dsMenue()` (30 von 38 Prüfungen rot); Kopfzeile 63 px und Suche 470 px; `ds.css`
  ohne `:active` am Menüeintrag -- 5 von 5 rot, je Datei byte-genau zurück.
- **Angepasste Erwartungen** (Regel 28):
  - `test_v254::test_search_slot_*` (zwei Tests): Ende des Suchbereichs -- alt `<div class="app-topbar-account">`, neu
    `<div class="app-konto">` (nur Aufbau).
  - `test_v254::test_account_button_shows_the_resolved_initials` → `…_shows_initials_and_full_name_since_1_8_163`: alt Knopf
    `app-topbar-account-btn` mit genau „TR“; neu `app-konto-knopf` mit Initialen und vollem Namen, aria-label und Menü-aria.
  - `test_v254::test_account_menu_contains_full_name_account_link_and_logout` → `test_account_menu_has_account_theme_and_logout_since_1_8_163`:
    alt Name als Überschrift im Menü; neu genau Mein Konto · Hell/Dunkel · Abmelden, der Name nicht im Menü.
  - `test_v254::test_topbar_is_sticky_and_uses_design_system_variables_only`: alt `var(--card)`/`var(--line)`; neu `var(--ds-flaeche)`/
    `var(--ds-linie)`, in Kopfzeile und Kontomenü kein `--accent`.
  - `test_v251::test_account_page_is_reachable_from_the_global_chrome`: alt `href="/account"` in `_topbar.html`; neu in
    `_kontomenue.html`, das die Kopfzeile einbindet.
  - `test_v253::test_hell_dunkel_im_kontomenue_…`: alt Hell/Dunkel in `_topbar.html`; neu in `_kontomenue.html` (nur Aufbau).
  - `test_v272::test_toggle_uses_the_same_storage_key_and_attribute_as_the_account_menu`: alt Vergleich mit `_topbar.html` (seit
    1.8.162); neu mit `_kontomenue.html` (nur Aufbau).

#### Nebenbefund

- Ein Konto ohne verknüpften Mitarbeiter zeigt im Kontoknopf den **Benutzernamen** als „vollen Namen“ (Testdaten: „ada“ statt „Ada
  Admin“) -- so liefert es `app/auth.py::resolve_account_display()` seit 1.3.45, auch für Kalender und Outlook-Sync. Nicht geändert;
  wäre `display_name` als zweiter Rückfall gewünscht, ist das eine eigene Entscheidung (drei Tests in `test_v254` halten den
  Benutzernamen fest).

#### Festlegungen 1.8.163 (Bitte bestätigen)

1. **Unter 600 px nur die Initialen** in der Kopfzeile des Büros (der Name bleibt in `aria-label` und `title`); im Monteurskopf
   immer mit Name.
2. **Das Menü nennt den Namen nicht noch einmal** (er steht im Knopf); Hell/Dunkel zeigt den aktuellen Zustand.
3. **Kontoknopf rund (Pille), Initialen-Kreis in `--ds-aktion`**, Hover `--ds-flaeche-2`; Menüknopf und Suchfeld mit `--ds-ecke-feld`.
4. **Zwei Klassen je Regel des Kopfs und `:active` in `ds.css`** als Schutz gegen die button-Regeln der Seiten (bis sie umziehen).

### Teil 4 (1.8.164): Monteurskopf

- **`_mobile_header.html`** neu, eine Zeile von 64 px in `--ds-navi-grund` (dunkel in beiden Modi): Logo-Kachel 40 px (Firmenlogo
  auf Weiß, sonst Dach auf `marke-hell`), die Reiter **Einsätze · Zeiterfassung · Stundenzettel** (48 px, 16 px, `navi-leise`; aktiv
  `navi-text` mit 3 px Strich unten in `marke-hell` und `aria-current`), rechts die **Lupe** (48 × 48, `aria-controls`/`-expanded`) und
  der **Kontoknopf** aus `_kontomenue.html` (Teil 3) mit Initialen und vollem Namen, 48 px; Menü Mein Konto · Hell/Dunkel · Abmelden
  mit 48 px hohen Einträgen. Einsätze ist auch auf Objekt, Einsatzbericht, Checklisten und Betriebsmittel aktiv, auf dem Konto keiner.
  Unter 600 px rutschen die Reiter in eine zweite Zeile (Kopf 112 px), der Name bleibt.
- **Objektsuche hinter der Lupe**: bis 1.8.163 eine eigene Zeile unter dem Kopf (Kopf 173 px, auf drei Seiten 188 px); jetzt eine Fläche
  unter dem Kopf (absolut am sticky-Wrapper), Fokus ins Feld; Escape schließt erst die Vorschläge, dann die Fläche mit Fokus zurück an
  die Lupe. Logik unverändert (ab zwei Zeichen nach 300 ms, `GET /api/field-view/properties/search`).
- **Einsatzbericht und Konto der Monteurin** bekommen den Monteurskopf (`service_reports.html`, `account.html`: Weiche
  `can(current_user, 'field')` wie `checklist.html`; ersetzt Festlegung 1.8.113 Nr. 6). Damit hat die Monteurin auf keiner Seite mehr
  Seitenleiste und Kopfzeile des Büros, der Name steht auch dort, wo unterschrieben wird.
- **Die button-Regeln dreier Seiten greifen nicht mehr in den Kopf** (Zeiterfassung, Objekt, Stundenzettel: `button{min-height:44px;
  width:100%}`): jede Regel des Kopfs trägt zwei Klassen und setzt ihre Maße selbst (Breite und Flex-Basis der Lupe, Höhe des
  Kontoknopfs). `_mobile_header.html` bindet `_speichern.html` nicht mehr ein (das Abmelden steht im Kontomenü).
- **Gemessen** (Instanz der Bildgrundlage): Kopf 64 px auf allen neun Seiten der Monteurin bei 1280 × 620 und 800 × 1100, auch auf den
  drei mit der button-Regel -- bis 1.8.163 173/188 px, für den Inhalt bleiben quer jetzt 556 statt 447 px (432 auf den drei Seiten);
  412 px: 112 px statt 173.

#### Tests und Prüfung

- `klicktest_rahmen.py` um den Teil `monteurskopf`: neun Seiten der Monteurin bei 1280 × 620 und 800 × 1100 (hell; Einsatzbericht, Konto
  und Zeiterfassung auch dunkel): 64 px, einzeilig (Mitte von Kachel, Reitern, Lupe und Konto auf ±2 px), keine Leiste und Kopfzeile des
  Büros, Name ganz, Reiter 48 px/16 px, der richtige aktiv, Lupe 48 × 48, kein waagrechter Bildlauf; 412 px zwei Zeilen; Lupe per
  Tastatur mit Fokus; Kontomenü per Tastatur. Die Monteurin fällt aus dem Teil `seitenleiste` heraus. 289 von 289.
- `test_v272`: neue Tests zu Zeile, Name, Maßen, Seitenregeln (jede Regel mit `.mobile-header-wrap` und zwei Klassen), aktivem Reiter;
  `test_v431`: die Monteurin hat überall den Monteurskopf.
- `scripts/bildgrundlage.py`: Zustände Menü aufgeklappt und Leiste eingeklappt nur noch fürs Büro, Kontomenü offen für Büro und Monteurin
  (dasselbe Menü), neu **Objektsuche offen** der Monteurin bei 800 und 1280 px -- 298 statt 302 Bilder.
- Klicktests `klicktest_anmelden` (Abmelden auf `/mobil` über das Kontomenü), `klicktest_monteur_navigation`, `klicktest_neue_ordnung`,
  `klicktest_versand_im_kontext` angepasst (siehe unten).
- **Gegenproben** (Regel 24, pytest und `klicktest_rahmen --nur monteurskopf`): Lupe ohne Breite und Flex-Basis (Klicktest 128 von 154:
  die button-Regel der Seite macht sie breit); Einsätze nur auf `/mobil` aktiv (142 von 154); Name im Monteurskopf ausgeblendet
  (129 von 154); Einsatzbericht der Monteurin weiter im Büro-Rahmen (134 von 154, dazu v431 und v328); Kopf 72 px (130 von 154) --
  5 von 5 rot, je Datei byte-genau zurück. Die erste Fassung der Lupen-Probe nahm nur die Breite weg und blieb im Klicktest grün
  (`flex:0 0 48px` hielt sie) -- verschärft, nicht als Beleg gezählt.
- **Angepasste Erwartungen** (Regel 28):
  - `test_v431::ERWARTETE_ZUSTAENDE`: alt Menü und Leiste eingeklappt für Büro und Monteurin; neu nur Büro, dazu „suche_offen“ (Monteurin,
    800/1280); Zustandsbilder alt 22, neu 18; Bilder alt 302, neu 298; Teilauswahl alt `(MONTEUR, "menue_offen")`, neu
    `(MONTEUR, "suche_offen")`.
  - `test_v431::test_zustandsseiten_zeichnen_den_rahmen_fuer_ihre_rolle`: alt dieselben vier Kennungen und die Leiste für jede Rolle; neu je
    Rolle die Kennungen ihrer Zustände, die Leiste nur fürs Büro.
  - `test_v431::test_monteurin_hat_den_rahmen_auf_einsatzbericht_und_konto` → `test_monteurin_hat_ueberall_den_monteurskopf_seit_1_8_164`:
    alt genau Einsatzbericht und Konto mit Leiste und Kontoknopf; neu jede Seite mit Monteurskopf und Kontoknopf, keine mit Leiste.
  - `test_v417::test_seitenleiste_in_gruppen_je_rolle[field]`: alt Leiste Übersicht/Start und Kaufmännisch/Zeiterfassung auf `/account`;
    neu dort der Monteurskopf ohne Leiste.
  - `test_v258::test_mobile_header_keeps_its_own_independent_logout`: alt `#mobileHeaderLogout` im Kopf; neu über `_kontomenue.html`
    (`#appTopbarLogout`).
  - `test_v418::test_mobile_kopfzeile_mit_mein_konto`: alt Link `.mobile-header-account` rechts im Kopf; neu Eintrag im Kontomenü.
  - `test_v400::test_the_login_click_test_covers_both_forms_and_both_headers`: alt `"#mobileHeaderLogout"` im Klicktest; neu
    `seite="/mobil"` (Abmelden über das Kontomenü des Monteurskopfs).
  - `test_v269`: Ankerung der Vorschläge -- alt Suchzeile und Liste nach den Reitern, Liste mit eigenem z-index; neu
    `test_search_opens_from_the_magnifier_below_the_header_since_1_8_164` (Lupe mit aria, Fläche nach den Reitern, absolut mit
    `top:100%`, Fokus) und Fläche absolut mit z-index am Wrapper; Maximalbreite alt an `.mobile-search-bar input`, neu an
    `.mobile-suche-feld`; „gestapelt ohne Überlappen“ nur Aufbau (Selektoren mit `.mobile-header-wrap`).
  - `test_v272`: die Tests zum eigenen Hell/Dunkel-Knopf (`#mobileThemeToggle` in der Kopfzeile neben dem Namen, genau zwei Kinder,
    30 px, Sonne/Mond, Klick) → Hell/Dunkel im Kontomenü des Monteurskopfs, derselbe Mechanismus weil dasselbe Kontomenü, Zustand statt
    Symbol, Klick im Kontomenü; `_render_mobile_header()` mit Stubs für Logo und Konto (nur Aufbau).
  - `test_v328::test_seitenleiste_des_monteurs_auf_der_berichtsseite`: alt `{"/", "/time-tracking"}`; neu die drei Reiter
    `{"/mobil", "/time-tracking", "/mobil/stundenzettel"}`. `test_gegenprobe_links_ohne_rollenbedingung_fallen_auf`: alt `can()` immer
    wahr; neu immer wahr außer `can(user, 'field')` (die Weiche zum Monteurskopf -- sonst gäbe es keine Leiste zu prüfen).
  - Klicktest `klicktest_anmelden`: Abmelden auf `/mobil` -- alt `#mobileHeaderLogout` und `.mobile-header-user`; neu
    `#appTopbarAccountBtn`, `#appTopbarLogout` und `.app-konto-name`.
  - Klicktest `klicktest_versand_im_kontext`: „Mein Konto“ auf `/mobil` -- alt Link `.mobile-header-account`; neu Eintrag im Kontomenü.
  - Klicktest `klicktest_monteur_navigation`: Monteurin auf Bericht und Konto -- alt Seitenleiste [Start, Zeiterfassung]; neu keine
    Leiste und die drei Reiter, Navigation auch aus `.mobile-header-wrap`; feste Uhr 10:00 (der Reiter Einsätze führt nach `/mobil`).
  - Klicktest `klicktest_neue_ordnung`: Monteurin -- alt Seitenleiste auf `/account`; neu Monteurskopf mit Reitern ohne 403/404; feste
    Uhr 10:00.
  - Klicktest `klicktest_rahmen`: Monteurin -- alt im Teil `seitenleiste` mit Übersicht und Kaufmännisch auf dem Einsatzbericht; neu im
    Teil `monteurskopf`.

#### Nachtrag 1.8.164: Erwartung von `klicktest_ds_schriften`

- Im Endlauf auf `cbd99f4` war `klicktest_ds_schriften` rot (26 von 27): „ds.css eingebunden“ erwartete nur `/static/ds/ds.css`, die
  Anmeldeseite bindet seit 1.8.161 (Teil 1) danach auch `ds-basis.css` ein. Veraltet seit 1.8.161 -- der Klicktest lief in Teil 1 nicht mit
  (Versäumnis). **Angepasste Erwartung** (Regel 28): `klicktest_ds_schriften` „ds.css eingebunden“ → „ds.css und ds-basis.css
  eingebunden“: alt `["/static/ds/ds.css"]`, neu `["/static/ds/ds.css", "/static/ds/ds-basis.css"]`; dazu die Kopfzeilen von `ds-basis.css`
  ohne Anmeldung (neue Prüfung). 28 von 28.

#### Festlegungen 1.8.164 (Bitte bestätigen)

1. **Abmelden und Hell/Dunkel im Kontomenü** auch im Monteurskopf -- Abmelden braucht zwei Tipps statt einem (bis 1.8.163 eigener
   Reiter), dafür dasselbe Menü wie im Büro.
2. **Objektsuche hinter der Lupe** als Fläche unter dem Kopf statt einer immer sichtbaren Zeile; Escape schließt erst die Vorschläge,
   dann die Fläche.
3. **Einsätze aktiv** auf Mobil, Objekt, Einsatzbericht, Checklisten und Betriebsmittel; auf dem Konto kein Reiter.
4. **Telefon (unter 600 px): zwei Zeilen**, die Reiter gleich breit darunter, Kopf 112 px; der Name bleibt.
5. **Kontoknopf und Menüeinträge 48 px**, Name 15 px; sehr lange Namen mit „…“, die Reiter schrumpfen nie.
6. **Logo-Kachel 40 px statt Schriftzug** „DACHKONZEPTE · Mobil“ (bleibt als `title`), wie die Kachel der Leiste.
7. **Weiche an der Rolle** (`can(current_user, 'field')`) in Einsatzbericht und Konto; die Einträge der Seitenleiste für die Monteurin
   (Start, Zeiterfassung) bleiben im Markup, keine Seite zeigt sie ihr noch -- Aufräumen bei der Bereinigung.

### Runde 1 abgeschlossen: Endläufe und Bildvergleich (Stand `581a80a`)

- **Volle Suite** auf sauberer Arbeitskopie, Commit `581a80a`: 6258 passed, 3 skipped (dritter Lauf; im zweiten ein wackelnder Test, siehe unten).
- **Alle Klicktests** (`klicktest_alle.py --gleichzeitig 4`): 80 von 80 wie erwartet, Laufzeit 7:12. Im ersten Endlauf auf `cbd99f4` war
  `klicktest_ds_schriften` rot (Erwartung veraltet seit 1.8.161, siehe „Nachtrag 1.8.164“), danach Nachtrag `581a80a` und beide Läufe neu.
- **Nebenbefund, ein wackelnder Test**: im zweiten Suite-Lauf auf `581a80a` war `tests/test_v323_dispatch_completion.py::test_two_simultaneous_dispatches_on_postgresql_exactly_one_sends` rot (beide Versände „gesendet“), einzeln zehnmal grün, der dritte volle
  Lauf grün. Ursache im Testaufbau: die Schranke (`threading.Barrier`) hält beide Threads nur bis nach der Vorabprüfung; wird B danach
  unter Last lange genug aufgehalten, hat A seinen Versand schon abgeschlossen (Status „gesendet“), der Eintrag „läuft“, an dem die
  Datenbank B abweisen soll, ist weg -- und zwei Versände nacheinander sind erlaubt. Kein Fehler im Versand, nicht in dieser Runde
  geändert; der Test müsste B vor dem Abschluss von A anlegen lassen (z. B. A im Senden anhalten, bis B angelegt hat). Offen.
- **Bildvergleich „außer Leiste, Kopfzeile und Monteurskopf weicht nichts ab“**: Bildgrundlage ohne die Zustände (280 Bilder) auf
  `82d5c71` (vor Teil 1, Git-Worktree) und auf `cbd99f4`. In beiden Läufen sind Seitenleiste, Kopfzeile und Monteurskopf einfarbig
  (#FF00FF) und ohne sichtbaren Inhalt; im alten Lauf haben sie die Maße von heute (Leiste 232 px, Kopfzeile 64 px, Monteurskopf 64 px,
  unter 600 px 112 px), und auf Einsatzbericht und Konto der Monteurin ist die alte Leiste weg und die Kopfzeile so hoch wie der
  Monteurskopf. Ergebnis: **280 gleich, 0 abweichend** -- kein Pixel des Inhalts hat sich geändert, auf keiner Seite, in keiner Rolle,
  keinem Thema, keiner Breite. Werkzeug: `rahmen_vergleich.py` (Scratchpad, umhüllt `scripts/bildgrundlage.py` unverändert: Zusatz zu
  `STILL`, Zustände ausgelassen) -- nicht ins Projekt übernommen; bei Bedarf für die nächsten Runden.
- **Bilder für den Bericht**: `bildgrundlage/rahmen_runde1_581a80a.zip` (Projektmappe 1440 × 900 hell und dunkel, Einsatzbericht als
  Monteurin 1280 × 620 und 800 × 1100), Ordner in `.gitignore`.

## Nachrunde zu Runde 1 (Festlegungen 1.8.161–1.8.164 bestätigt)

### Punkt 1 (1.8.165): Bildmarke statt Haus

- **`_bildmarke.html`** (neu): die Bildmarke von DACHKONZEPTE als feste SVG -- `viewBox="240 47 1441 1184"`, zwei Polygone in
  #A7CD5D, eines in #367337, genau wie vorgegeben. Feste Farben der Marke, keine --ds-Werte (sie ändern sich nicht mit dem Modus).
- **Seitenleiste** (Kachel 36 px, 4 px Abstand) und **Monteurskopf** (Kachel 40 px, 5 px Abstand) binden sie ein, auf weißer Kachel
  (`#FFFFFF`) auch im Dunkelmodus. Bis 1.8.164 zeigte die Kachel das Logo der Leiste bzw. das Firmenlogo (`sidebar_logo_url()`), sonst ein
  Haus auf `marke-hell`. Das hochgeladene Firmenlogo bleibt für die PDF-Dokumente und das Symbol der Monteursansicht.
- **Einstellungen → Erscheinungsbild**: der Abschnitt „Logo der Leiste“ (eigener Upload samt Höhe, seit 1.3.43) bewirkt nichts mehr --
  er bleibt stehen, sein Hinweis sagt das jetzt; der Hinweis beim Firmenlogo nennt die Seitenleiste nicht mehr, und der Hinweis bei der
  Akzentfarbe nennt Hell/Dunkel im Kontomenü (stand seit 1.8.162 noch „unten in der Seitenleiste“).

#### Tests und Prüfung

- `test_v253::test_bildmarke_wie_vorgegeben_in_leiste_und_monteurskopf` (neu): viewBox, die drei Polygone mit Farbe und Punkten, beide
  Köpfe binden `_bildmarke.html` ein, kein Aufruf von `sidebar_logo_url()`, Kachel 36/40 px auf `#FFFFFF`.
- `klicktest_rahmen`: Bildmarke auf weißer Kachel in der Leiste (alle Büro-Rollen, hell und dunkel) und im Monteurskopf (40 px, kein
  `<img>`). 322 von 322. `klicktest_dateien_nie_aktiv` 43/43, `klicktest_neue_ordnung` 80/80, `klicktest_teil_updates` 9/9.
- **Gegenproben**: Kachel der Leiste wieder hellgrün (pytest und Klicktest 45 von 54); Monteurskopf mit Haus statt Bildmarke (pytest
  und Klicktest 154 von 178); Bildmarke in falscher Farbe (pytest) -- 3 von 3 rot, je Datei byte-genau zurück.
- **Angepasste Erwartungen** (Regel 28):
  - `test_v249::test_sidebar_shows_logo_image_when_present` → `…_shows_the_brand_mark_even_with_an_uploaded_logo_since_1_8_165`: alt
    `<img>` mit der Logo-Adresse in der Kachel `mit-logo`; neu die Bildmarke, kein `<img>`, keine Logo-Adresse.
  - `test_v249::test_sidebar_logo_wrapped_in_width_limiting_clip_container_not_on_img_itself` →
    `test_sidebar_tile_is_white_in_both_themes_since_1_8_165`: alt `<img>` ohne eigene Breitenbegrenzung; neu Kachel `#FFFFFF`, kein --ds-Wert.
  - `test_v253::test_kopf_kachel_mit_logo_und_schriftzug_ohne_knoepfe` → `…_mit_bildmarke_…`: alt `<img>` in der Kachel; neu die Bildmarke.
  - `test_v253::test_kopf_ohne_logo_zeigt_ein_dach_auf_der_kachel` → `…_zeigt_dieselbe_bildmarke`: alt Haus-SVG; neu die Bildmarke.
  - Klicktest `klicktest_dateien_nie_aktiv` „Logo“: alt SVG-Logo in der Seitenleiste als Bild sichtbar; neu in der Vorschau der
    Einstellungen, dazu: die Leiste zeigt die Bildmarke, kein `<img>`.

#### Festlegungen 1.8.165 (Bitte bestätigen)

1. **Bildmarke als eigener Baustein** `_bildmarke.html` mit festen Farben der Marke, von Leiste und Monteurskopf eingebunden.
2. **Abstand in der Kachel** 4 px (Leiste) bzw. 5 px (Monteurskopf) -- die Marke steht etwa 28 × 23 bzw. 30 × 25 px groß.
3. **„Logo der Leiste“ bleibt bis zur Bereinigung** in den Einstellungen (Upload, Höhe, Endpunkte, Spalten, die Globals
   `sidebar_logo_url()`/`sidebar_logo_height_px()` und das Lesen in den Seitendaten), mit Hinweis, dass es nicht mehr angezeigt wird;
   Vorschlag: bei der Bereinigung samt allem entfernen.
4. **Schriftzug bleibt** neben der Kachel in der Leiste; im Monteurskopf nur die Kachel (`aria-label` „DACHKONZEPTE“).

### Punkt 2 (1.8.166): Schriftstärke der Leiste

- Geprüft: `.app-sidebar-link` hatte `font-weight:500`, der aktive Eintrag setzte keine eigene Stärke und erbte die 500. Jetzt
  `.app-sidebar-link.active{…;font-weight:600}`; keine andere Regel der Leiste setzt eine Stärke an Eintrag oder Beschriftung.
- Gemessen im Browser auf jeder Seite, die Büro – Finanzen mit Leiste öffnet (Teil `schrift` von `klicktest_rahmen`): normale
  Einträge 500, der aktive 600, auf keiner Seite eine abweichende Stärke durch Seitenregeln.

#### Tests und Prüfung

- `test_v253::test_schriftstaerke_normal_500_aktiv_600` (neu); `klicktest_rahmen` Teil `schrift` (neu). Mit dem Teil „aktiv“ zusammen 63 von 63; im Teil „schrift“ 40 Seiten mit Leiste.
- **Gegenproben**: aktiver Eintrag ohne eigene Stärke (Klicktest 3 von 41, rot auf jeder Seite mit aktivem Eintrag); Beschriftung mit eigener Stärke 700 (Klicktest 1 von 41) -- 2 von 2 rot, je mit pytest, Datei byte-genau zurück.
- Angepasste Erwartungen: keine.

#### Festlegungen 1.8.166 (Bitte bestätigen)

1. **Nur die Stärke ändert sich** (Schrift, Größe und Farben wie gehabt); die Gruppenüberschriften bleiben 600 in Großbuchstaben.

### Punkt 3 (1.8.167): voller Name im Kontomenü

- `_kontomenue.html`: oben im Menü `#appKontoVollname` (`.ds-menue-kopf`, `role="presentation"`, kein Menüeintrag -- Pfeile und
  Pos1 springen darüber), sichtbar genau dann, wenn der Name im Knopf gekürzt ist (`scrollWidth > clientWidth`) oder ausgeblendet
  (`offsetWidth === 0`, Kopfzeile unter 600 px); geprüft beim Laden, nach dem Laden der Schriften, bei Größenänderung und bei jedem
  Öffnen. Der Kopf bricht um statt zu kürzen; das Menü wird so breit wie nötig, höchstens 360 px.

#### Tests und Prüfung

- `test_v254::test_full_name_in_the_menu_when_the_button_shortens_it_since_1_8_167` (neu); `klicktest_rahmen` Teil `vollname` (neu):
  Büro 1440 px ohne Kopf, 412 px mit „Bernd Büro“; Monteurin hell und dunkel: ganz ohne Kopf, mit schmalem Knopf Kopf mit
  „Mia Monteurin“, ganz zu sehen; Fokus jeweils auf „Mein Konto“. Mit dem Teil „kontomenue“ zusammen 47 von 47.
- **Gegenproben**: voller Name nie im Menü (Klicktest 6 von 9); immer im Menü (6 von 9); Kopf kürzt wieder mit „…“ (pytest) -- 3 von 3 rot, je mit pytest, Datei byte-genau zurück.
- **Angepasste Erwartung** (Regel 28): `test_v254::test_account_menu_has_account_theme_and_logout_since_1_8_163`: alt „der Name steht
  nicht im Menü“; neu genau einmal, im verborgenen Kopf `#appKontoVollname`.

#### Festlegungen 1.8.167 (Bitte bestätigen)

1. **Kopf nur bei Bedarf**: passt der Name in den Knopf, zeigt das Menü ihn nicht noch einmal (Festlegung 1.8.163 Nr. 2 bleibt so).
2. **Ausgeblendet zählt als gekürzt** (Kopfzeile des Büros unter 600 px zeigt nur die Initialen).
3. **Der Kopf ist kein Menüeintrag** (`role="presentation"`); Bildschirmleser hören den Namen weiter über `aria-label` des Knopfs.

### Punkt 4 (1.8.168): Anzeigename vor Benutzername

- **Geprüft vor der Änderung**: `resolve_account_display()` nutzen außer dem Kontoknopf (Seitendaten) nur `app/calendar_events.py`
  (`_owner_name()` → `owner_name` an jedem Termin und an der „belegt“-Fassung privater Termine; `list_owners()` → Beschriftung der
  Besitzer-Auswahl, Wert ist die ID) und `app/outlook_calendar_sync.py::list_series_occurrences()` (`owner_name` an Serien-Terminen,
  gemerkt je `owner_user_id`). Überall **nur Anzeige** (Kalenderseite: Besitzer, Titel „Privater Termin von …“, Auswahl); Schlüssel
  und Vergleiche laufen über `owner_user_id`, nach Outlook geschrieben wird der Name nicht, sortiert wird die Auswahl in SQL nach
  `display_name`. Deshalb geändert, nichts zu melden.
- `app/auth.py::resolve_account_display()`: Mitarbeiter (Vor- und Nachname) → **Anzeigename des Kontos** → Benutzername; Initialen
  aus der neuen Funktion `name_und_initialen()`. Der Rückfall der Seitendaten ohne Datenbank (`konto_rueckfall()`) folgt derselben
  Reihenfolge (bis 1.8.167 nur der Benutzername).

#### Tests und Prüfung

- `test_v254`: Anzeigename ohne Mitarbeiter, Benutzername ohne Anzeigenamen (nur Leerzeichen), Rückfall der Seitendaten mit
  Anzeigenamen (neu). Klicktest-Teil „kopfzeile“ 18 von 18 (Admin heißt „Ada Admin“).
- **Gegenproben**: wieder der Benutzername (pytest v254 und v296, Klicktest 16 von 18); Anzeigename aus Leerzeichen gilt als gesetzt (pytest); Rückfall der Seitendaten nur mit dem Benutzernamen (pytest) -- 3 von 3 rot, Dateien byte-genau zurück.
- **Angepasste Erwartungen** (Regel 28):
  - `test_v254::test_resolve_account_display_falls_back_to_username_without_employee_link` → `…_to_display_name_…`: alt „admin“/„AD“;
    neu der Anzeigename „Ada Admin“/„AA“ (Testkonto mit diesem Anzeigenamen statt „Administrator“).
  - `test_v254::test_resolve_account_display_falls_back_to_username_when_employee_id_points_nowhere` → `…_to_display_name_…`: alt
    „geist“; neu „Geist“.
  - `test_v296::test_create_event_basic_and_owner_name_resolved`: `owner_name` alt „tobias“, neu „Tobias“ (Anzeigename des Testkontos).
  - Klicktest `klicktest_rahmen` Kopfzeile Admin: alt Name „ada“, neu „Ada Admin“.

#### Festlegungen 1.8.168 (Bitte bestätigen)

1. **Leerer Anzeigename** (auch nur Leerzeichen) zählt als fehlend -- dann der Benutzername.
2. **Kalender und Outlook-Serien zeigen denselben Namen** wie der Kontoknopf (eine Funktion für alle Anzeigen).

### Nachrunde abgeschlossen: Endläufe (Stand `331745e`)

- **Volle Suite** auf sauberer Arbeitskopie, Commit `331745e`: 6269 passed, 3 skipped.
- **Alle Klicktests** (`klicktest_alle.py --gleichzeitig 4`): 80 von 80 wie erwartet, Laufzeit 7:31.
- **Bilder** der Runde 1 neu: `bildgrundlage/rahmen_runde1_331745e.zip` (Projektmappe 1440 × 900 hell und dunkel, Einsatzbericht als
  Monteurin 1280 × 620 und 800 × 1100), Ordner in `.gitignore`.

## Korrektur an Leiste und Monteurskopf nach Zeichnung (ersetzt Festlegung 1.8.162 Nr. 4)

### Punkt 1 (1.8.169): Einträge der Leiste

- `_sidebar.html`: Navigation `padding:4px 12px` (Einträge 12 px vom linken und rechten Rand, bis 1.8.168 8 px), Eintrag
  `padding:0 12px; border:0; border-radius:8px` (bis dahin ohne Ecken, mit linkem Rand 3 px). Aktiv: `background` navi-aktiv,
  `color:#FFFFFF`, `font-weight:600`, `box-shadow:inset 3px 0 0 var(--ds-marke-hell)` -- der Strich liegt innerhalb der Ecken.
  Hover der übrigen `#2A3238` mit denselben Ecken; der aktive behält beim Hover seine Fläche. Befunde `padding-left:40px` (12 px
  wie jeder Eintrag + 28 px Einzug wie bisher); Gruppenüberschriften 12 px eingerückt (über den Symbolen); eingeklappt die Einträge
  36 px breit, das Symbol mit 9 px Abstand in der Mitte.
- Höhen unverändert (Zeilen 36 px): bei 1280 × 800 und 1440 × 900 in allen Büro-Rollen ohne Bildlauf (Klicktest).
- **Hinweis zum Dunkelmodus**: `#2A3238` ist fest vorgegeben; im Dunkelmodus ist navi-aktiv `#232B30`, der Hover also eine Spur
  heller als der aktive Eintrag (im hellen Modus dunkler: navi-aktiv `#333C43`). Der aktive bleibt durch weiße 600er-Schrift und
  Strich unterscheidbar; soll der Hover im Dunkelmodus dunkler sein, bräuchte er einen eigenen Wert.

#### Tests und Prüfung

- `test_v253::test_eintraege_mit_abstand_ecken_und_strich_als_schatten` (neu).
- `klicktest_rahmen` Teil `aktiv`: Schatten in marke-hell, Fläche navi-aktiv, Schrift weiß, Ecken 8 px, 12 px vom linken und
  rechten Rand; Hover eines anderen Eintrags `rgb(42, 50, 56)` mit 8 px Ecken (hell und dunkel). Teile `seitenleiste`, `aktiv`,
  `menueknopf` zusammen 86 von 86.
- **Gegenproben**: Strich wieder als linker Rand (Klicktest 18 von 24); Einträge 8 px vom Rand (18 von 24); Hover in navi-aktiv
  (22 von 24) -- 3 von 3 rot, je mit pytest, Datei byte-genau zurück.
- **Angepasste Erwartung** (Regel 28): Klicktest `klicktest_rahmen` „Strich 3 px in marke-hell auf navi-aktiv“: alt
  `[borderLeftWidth 3px, Randfarbe marke-hell, Fläche navi-aktiv]`; neu `[Schatten inset 3px in marke-hell, Fläche navi-aktiv,
  Schrift weiß, Ecken 8 px, 12 px links, 12 px rechts]`.

#### Festlegungen 1.8.169 (Bitte bestätigen)

1. **Gruppenüberschriften 12 px eingerückt**, bündig mit den Symbolen der Einträge.
2. **Der aktive Eintrag behält beim Hover seine Fläche** (navi-aktiv), nur die übrigen werden `#2A3238`.
3. **Eingeklappt** Einträge 36 px breit, Symbol in der Mitte (9 px Abstand), dieselben Ecken und derselbe Strich.

### Punkt 2 (1.8.170): aktiver Reiter des Monteurskopfs

- `_mobile_header.html`: Reiter `border:0; border-radius:10px` (bis 1.8.169 unterer Rand 3 px, keine Ecken); aktiv
  `background` navi-aktiv, `box-shadow:inset 0 -3px 0 var(--ds-marke-hell)` -- der Strich liegt innerhalb der Ecken. Schrift wie
  bisher (navi-text, 16 px, 500). Hover der übrigen wie bisher navi-aktiv, jetzt mit denselben Ecken.

#### Tests und Prüfung

- `klicktest_rahmen` Teil `monteurskopf`: aktiver Reiter mit Schatten in marke-hell, Fläche navi-aktiv, Ecken 10 px auf allen
  neun Seiten bei 1280 × 620 und 800 × 1100. 178 von 178.
- **Gegenproben**: aktiver Reiter wieder mit unterem Rand statt Schatten (Klicktest 158 von 178); Reiter ohne Ecken (158 von 178) -- 2 von 2 rot, je mit pytest, Datei byte-genau zurück.
- **Angepasste Erwartungen** (Regel 28):
  - `test_v272::test_kopf_64_px_reiter_48_px_lupe_48_px`: Reiter alt `border-bottom:3px solid transparent`, aktiv
    `border-bottom-color` marke-hell; neu `border-radius:10px` ohne unteren Rand, aktiv Fläche navi-aktiv und
    `box-shadow:inset 0 -3px 0` in marke-hell.
  - Klicktest `klicktest_rahmen` „aktiver Reiter“: alt `[Text, aria-current, borderBottomWidth 3px, Randfarbe marke-hell]`; neu
    `[Text, aria-current, Schatten unten in marke-hell, Fläche navi-aktiv, Ecken 10 px]`.

#### Festlegungen 1.8.170 (Bitte bestätigen)

1. **Schrift des aktiven Reiters bleibt** navi-text in 500 (die Zeichnung nennt für den Reiter nur Fläche, Ecken und Strich).
2. **Hover der übrigen Reiter** bleibt navi-aktiv, mit denselben 10 px Ecken.

### Punkt 3: Versionszusatz an ds.css und ds-basis.css (nur geprüft, nichts geändert)

- **Ja**: `_ds_kopf.html` bindet beide mit `?v={{ app_version }}` ein, alle 53 Seiten aus `seiten()` binden `_ds_kopf.html` ein (auch die
  Anmeldeseite). `app_version` ist `APP_VERSION` aus `app/version.py` -- beim Start aus der Datei `VERSION` gelesen; `update.sh` startet
  den Dienst neu, danach steht die neue Version in jeder Seite. `/static/` antwortet mit `public, max-age=31536000, immutable`; die
  Seiten einer angemeldeten Sitzung mit `no-store` -- jede Navigation holt also neues HTML mit der neuen Adresse, und die neue Datei
  kommt, statt der alten aus dem Zwischenspeicher. Einen Service Worker gibt es nicht. Schriften stehen ohne Zusatz in `ds.css`, eine
  geänderte Schrift bekommt aber einen neuen Dateinamen (Regel 37).
- **Grenze 1 -- der Zusatz ist die Version, nicht der Inhalt**: ändert ein Commit `ds.css` oder `ds-basis.css`, ohne `VERSION` zu
  erhöhen (z. B. ein Nachtrag-Commit „<Version> (Nachtrag)“, der die Version beibehält), bleibt die Adresse gleich, und Geräte, die
  die Datei schon haben, behalten die alte bis zu einem Jahr (`immutable`). Heute sichert das nur Regel 8 (jede spürbare Änderung
  erhöht `VERSION`). Abhilfe, falls gewünscht: Prüfsumme des Inhalts statt der Version im Zusatz (beim Start berechnet), oder ein
  Wächter, der eine Änderung an `app/static/ds/` ohne neue Version ablehnt.
- **Grenze 2 -- eine offene Seite**: ein Tablet mit einer geöffneten Seite behält die alte Gestaltung bis zum nächsten Laden oder
  Wechsel der Seite; ein Deploy lädt offene Seiten nicht neu.
- Am Rande: die Anmeldeseite ohne Sitzung trägt keinen `Cache-Control`-Kopf (`no-store` nur für angemeldete Sitzungen); ohne
  `ETag`/`Last-Modified` nimmt der Browser sie beim normalen Laden nicht aus dem Zwischenspeicher, höchstens beim Zurück-Blättern.

### Korrektur abgeschlossen: Endläufe (Stand `d83996c`)

- **Volle Suite** auf sauberer Arbeitskopie, Commit `d83996c`: 6270 passed, 3 skipped.
- **Alle Klicktests** (`klicktest_alle.py --gleichzeitig 4`): 80 von 80 wie erwartet, Laufzeit 7:43.
- **Bilder**: `bildgrundlage/rahmen_korrektur_d83996c.zip` (Leiste 1440 × 900 hell und dunkel auf der Projektmappe, Monteurskopf 1280 × 620 auf dem
  Einsatzbericht), Ordner in `.gitignore`.

## Runde 2 (Festlegungen 1.8.169 und 1.8.170 bestätigt, außer 1.8.170 Nr. 1)

### Punkt 1 (1.9.0): aktiver Reiter weiß in 600

- `_mobile_header.html`: `.mobile-nav-reiter.active` mit `color:#FFFFFF; font-weight:600` (bis 1.8.170 navi-text in 500) --
  ersetzt Festlegung 1.8.170 Nr. 1. Fläche, Ecken und Strich unverändert.

#### Tests und Prüfung

- `test_v272::test_kopf_64_px_reiter_48_px_lupe_48_px` um Weiß und 600 ergänzt; `klicktest_rahmen` Teil `monteurskopf` misst Farbe
  und Stärke des aktiven Reiters auf allen Seiten der Monteurin. 178 von 178.
- **Gegenproben**: aktiver Reiter wieder navi-text in 500 (pytest; Klicktest 158 von 178) -- 1 von 1 rot, Datei byte-genau zurück.
- **Angepasste Erwartung** (Regel 28): Klicktest `klicktest_rahmen` „aktiver Reiter“: alt `[Text, aria-current, Schatten, Fläche,
  Ecken]`; neu dazu Farbe `rgb(255, 255, 255)` und Stärke `600`.

### Punkt 2 (1.9.1): --ds-navi-hover

- `ds.css`: `--ds-navi-hover` hell `#2A3238`, dunkel `#171D20` (zwischen navi-grund `#0B0F11` und navi-aktiv `#232B30`); Prüfpaar
  `navi-text/navi-hover` im Kopfkommentar, also im Kontrasttest (hell 9,32 : 1, dunkel 12,19 : 1, gefordert 4,5).
- Leiste: Hover der Einträge `var(--ds-navi-hover)` (bis 1.9.0 fest `#2A3238`). Monteurskopf: Hover der Reiter, der Lupe und des
  Kontoknopfs `var(--ds-navi-hover)` (bis dahin navi-aktiv); geöffnet (Lupe, Kontomenü: `aria-expanded="true"`) bleiben sie
  navi-aktiv.

#### Tests und Prüfung

- `test_v432`: Prüfpaar navi-text/navi-hover in beiden Modi (der Test liest die Paare aus dem Kopfkommentar, dazu eine Prüfung,
  dass das Paar dort steht); `test_v253`, `test_v272`: Hover über den Wert. `klicktest_rahmen`: Hover der Leiste hell und dunkel,
  Hover eines Reiters im Monteurskopf. Teile „aktiv“ und „monteurskopf“ zusammen 206 von 206.
- **Gegenproben**: Hover der Leiste wieder fest #2A3238 (Klicktest 23 von 24: rot genau im Dunkelmodus); Hover der Reiter in navi-aktiv (180 von 182); navi-hover dunkel zu hell für navi-text (Kontrasttest) -- 3 von 3 rot, je mit pytest, Dateien byte-genau zurück.
- **Angepasste Erwartungen** (Regel 28):
  - `test_v253::test_eintraege_mit_abstand_ecken_und_strich_als_schatten`: Hover alt `background:#2A3238`, neu
    `background:var(--ds-navi-hover)`.
  - Klicktest `klicktest_rahmen` Hover der Leiste: alt `rgb(42, 50, 56)` in beiden Modi; neu der Wert `--ds-navi-hover` (dunkel
    `rgb(23, 29, 32)`).

#### Festlegungen 1.9.1 (Bitte bestätigen)

1. **Geöffnet bleibt navi-aktiv**: Lupe und Kontoknopf mit offenem Feld bzw. Menü behalten navi-aktiv, nur der Hover nimmt navi-hover.

### Punkt 3 (1.9.2): Prüfsumme statt Version

- `app/design_dateien.py::pruefsumme(name)`: die ersten 10 Zeichen der SHA-256 des Inhalts einer Datei unter `app/static/ds/`;
  beim Start einmal gebildet (`ds_pruefsummen()`), als Jinja-Werte `ds_css_pruefsumme` und `ds_basis_pruefsumme`
  (`app/routers/pages.py`). `_ds_kopf.html` bindet `ds.css?v=…` und `ds-basis.css?v=…` damit ein (bis 1.9.1 `?v={{ app_version }}`).
  Grenze 1 aus dem Befund der Korrektur ist damit weg; Grenze 2 (eine offene Seite bis zum Neuladen) bleibt.

#### Tests und Prüfung

- `test_v432`: die Seite nennt die Prüfsumme des heutigen Inhalts; geänderter Inhalt → andere Prüfsumme und andere Adresse (Datei
  im Wegwerf-Ordner); dieselbe Prüfsumme für denselben Inhalt. Klicktest `klicktest_ds_schriften` 28 von 28 (Pfade und Kopfzeilen unverändert).
- **Gegenproben**: wieder die Version als Zusatz (pytest, drei Tests rot); Prüfsumme unabhängig vom Inhalt (pytest) -- 2 von 2 rot, Dateien byte-genau zurück.
- **Angepasste Erwartungen** (Regel 28):
  - `test_v432::test_ds_kopf_bindet_nur_ds_css_mit_version_ein` → `test_ds_kopf_bindet_ds_css_und_ds_basis_mit_pruefsumme_ein`:
    alt `?v={{ app_version }}`; neu die Prüfsummen-Werte.
  - `test_v252::test_no_further_database_backed_jinja_globals_exist_unguarded`: alt 8 Jinja-Globals; neu 10 -- dazu die beiden
    Prüfsummen, feste Zeichenketten ohne Datenbank, geprüft mit genau ihrer Zuweisung.

#### Festlegungen 1.9.2 (Bitte bestätigen)

1. **Prüfsumme beim Start**, nicht je Anfrage -- die Dateien ändern sich nur mit einem Deploy, und `update.sh` startet neu.

### Punkt 4 (1.9.3): Pilot Prüfvorlagen

- `inspection_templates.html` ist die erste umgezogene Seite (`UMGEZOGEN` in `test_v441`):
  - `<body class="ds-seite">` -- Schrift, Farben und Felder aus `ds-basis.css`.
  - **Seitenkopf** über `teile/seitenkopf.html` (Variante Liste): Titel „Prüfvorlagen“ 30 px, Untertitel, genau eine grüne Hauptaktion
    „+ Neue Vorlage“ (`.ds-knopf-aktion`), im Menü „⋮“ „Archivierte anzeigen/ausblenden“ (bis dahin ein Häkchen im Kopf); Skript
    `_seitenkopf.html`.
  - **Eigene Farben nur über `--ds-*`**: Karten `--ds-flaeche`/`--ds-linie` mit 12 px Ecken, Knöpfe `.ds-knopf`/`.ds-knopf-aktion` mit
    10 px Ecken, Felder 40 px hoch, Tabellenköpfe `--ds-text-2`, Hinweise `--ds-text-2`, Fehler `--ds-fehler-text`. Die Akzentfarbe aus
    den Einstellungen färbt die Seite nicht mehr (kein `--accent` mehr); im `:root` bleiben nur `--danger`, `--danger-soft`,
    `--warning`, `--warning-soft` -- auf `--ds-*` gelegt, für `_speichern.html` (Hinweise „Seite neu laden“, „Anmeldung abgelaufen“).
  - Abschnitte „Standardvorlage je Dachtyp“ und „Vorlagen“ als Karten mit Überschrift; archivierte Zeilen in `--ds-text-2` statt halber
    Deckkraft; „Archivieren“ je Zeile über `data-klick` statt Werten im `onclick` (zwei Einträge weniger in `AUSNAHMEN_HANDLER`).
  - **Dachtyp ausgeschrieben**: die Liste der Vorlagen zeigt den Namen aus der Auswahlliste (bis dahin den gespeicherten Wert), auch bei
    anderer Schreibweise -- die Testdaten der Bildgrundlage speichern „flachdach“, das Programm selbst die Werte der Auswahlliste
    („Flachdach“, Migration `09b654357a58`).
- **`ds-basis.css` korrigiert** (erst jetzt wirksam, die Prüfvorlagen sind die erste Seite mit `.ds-seite`): die Regeln für `a` und
  `button` gelten nur für Elemente ohne Klasse (`:not([class])`). Ein Element unter `.ds-seite` (Spezifität 0,1,1) wog mehr als eine
  Klasse (0,1,0): `.ds-seite a` hätte Einträge der Leiste und „Mein Konto“ im Kontomenü in Linkfarbe gesetzt, `color:inherit` dem grünen
  Knopf die weiße Schrift genommen (gemessen in der Gegenprobe: 3,00 : 1).
- **Kontrast der Seite** (Klicktest, jeder sichtbare Text gegen seinen tatsächlichen Hintergrund, 4,5 : 1, großer Text 3 : 1): kleinster
  Wert hell 5,73 : 1, dunkel 4,71 : 1 -- auch mit offenem Menü „⋮“ und offenem Editor, bei 412 px ohne waagrechten Bildlauf.

#### Tests und Prüfung

- `test_v441::test_grundregeln_fuer_a_und_button_nur_ohne_klasse` (neu), `UMGEZOGEN` mit der Seite.
- `klicktest_rahmen` Teil `pruefvorlagen` (neu): `.ds-seite`, Titel 30 px, genau eine grüne Hauptaktion mit Schrift auf-aktion und 10 px
  Ecken, Menü per Tastatur mit Umschalten, Karten 12 px, Knöpfe 10 px, „Flachdach“, Leiste in navi-text, „Mein Konto“ in Textfarbe,
  Editor mit Fokus im Feld, Kontrast in drei Zuständen hell und dunkel, 412 px. 20 von 20; mit den Teilen `kontomenue` und
  `seitenleiste` 112 von 112.
- **Gegenproben** (pytest und Klicktest): `a` wieder ohne `:not([class])` (Leiste in Linkfarbe, 18 von 20); `button` wieder ohne
  `:not([class])` (dunkle Schrift auf dem grünen Knopf, Kontrast 3,00 bzw. 4,00, 11 von 20); Seite ohne `.ds-seite` (Titel im
  Dunkelmodus 1,18 : 1, 15 von 20); Dachtyp wieder als gespeicherter Wert (18 von 20); Hinweistext mit zu wenig Kontrast (1,57 : 1,
  13 von 20) -- 5 von 5 rot, Dateien byte-genau zurück.
- **Angepasste Erwartungen** (Regel 28):
  - `test_v441::UMGEZOGEN`: alt leer (keine Seite mit `.ds-seite`), neu `{"inspection_templates.html"}`.
  - `test_v407::AUSNAHMEN_HANDLER`: die zwei Einträge `inspection_templates.html | row | onclick: !t.archived` und `… onclick: t.id`
    gestrichen (Liste darf nur kürzer werden; jetzt 364 -- CLAUDE.md nannte noch 373).

#### Nebenbefund

- Die Testdaten der Bildgrundlage legen die Prüfvorlage mit `roof_type="flachdach"` an, das Programm speichert die Werte der Auswahlliste
  („Flachdach“). Ob die Detailseite einer Prüfvorlage einen so geschriebenen Wert in ihrer Auswahl vorwählt, ist nicht untersucht -- bei
  ihrem Umzug prüfen. Die Testdaten bleiben, wie sie sind (sie steuern auch die Vorlage im Einsatzbericht).

#### Festlegungen 1.9.3 (Bitte bestätigen)

1. **„Archivierte anzeigen“ ins Menü „⋮“** als einziger Eintrag (Text wechselt auf „Archivierte ausblenden“), statt eines Häkchens.
2. **Abschnitte als Karten mit Überschrift** („Standardvorlage je Dachtyp“ mit Hinweis, „Vorlagen“).
3. **„Anlegen“ im Editor grün** (Hauptaktion des Formulars, nur sichtbar, solange der Editor offen ist), „Abbrechen“ und „Archivieren“
   neutral.
4. **Archivierte Zeilen in `--ds-text-2`** statt halber Deckkraft (Kontrast).
5. **Grundregeln für `a` und `button` nur ohne Klasse** -- gilt für jede weitere umgezogene Seite.
6. **Alte Namen nur noch für `_speichern.html`** (`--danger`/`--warning` im `:root` der umgezogenen Seite, auf `--ds-*` gelegt), bis der
   Baustein selbst umzieht; `color-scheme` bleibt auf der Seite.

### Runde 2 abgeschlossen: Endläufe und Bildvergleich (Stand `f1fcac7`)

- **Volle Suite** auf sauberer Arbeitskopie, Commit `f1fcac7`: 6273 passed, 3 skipped.
- **Alle Klicktests** (`klicktest_alle.py --gleichzeitig 4`): 80 von 80 wie erwartet, Laufzeit 7:36.
- **Bildvergleich** (volle Bildgrundlage, 298 Bilder, `f231b1e` vor der Runde gegen `f1fcac7`): 211 gleich, 86 abweichend wie
  erwartet -- die Prüfvorlagen (nur der Inhalt: das Rechteck beginnt bei x = 232 bzw. y = 64, Leiste und Kopfzeile der Pilotseite
  pixelgleich) und der aktive Reiter im Monteurskopf (alle Abweichungen in den obersten 64 px, bei 412 px 112 px; bei der Monteurin auf
  jeder Seite, beim Büro auf den Seiten der Monteursansicht). Hover kommt in den Bildern nicht vor.
- **Ein Bild abweichend ohne Änderung**: `buero__hell__1440__start--kontomenue_offen.png`, 10 Pixel im Kalender-Symbol der Leiste um 2
  von 255 Stufen -- Kantenglättung: eine zweite Aufnahme desselben Stands weicht an derselben Stelle ab und gleicht dem Stand vorher
  pixelgenau. Kein Befund am Code; der Vergleich der Bildgrundlage kennt keine Toleranz, solches Rauschen erscheint dort als Abweichung.
- **Bilder**: `bildgrundlage/rahmen_runde2_f1fcac7.zip` (Prüfvorlagen 1440 × 900 vorher und nachher je hell und dunkel, Monteurskopf
  1280 × 620), Ordner in `.gitignore`.

## Nachtrag zu Runde 2 und Runde 3 (Festlegungen 1.9.1–1.9.3 bestätigt, außer 1.9.3 Nr. 5)

### Punkt 0: Versionsnummer -- das Redesign läuft unter 1.9.x

- **Regel 8 (Wortlaut des maßgeblichen Satzes):** „**Seit 1.1.0 zusätzlich:** ein Minor-Versionssprung (`1.X.0`) markiert die
  Einführung eines neuen, echten Moduls (siehe Modul-Umschalter unten), ein reiner Patch-Level (`1.0.X`) alles andere – Infrastruktur,
  Fixes, Redesign, Anpassungen an bestehenden Modulen.“
- **Warum der Sprung ausblieb:** die Regel nennt das Redesign ausdrücklich unter dem Patch-Level -- jede Runde zählte deshalb 1.8.x
  weiter. Eine Regel, die eine große Überarbeitung als Minor-Sprung führt, gibt es nicht.
- **Umbenannt (Vorgabe Betreiber, 20.10.2026):** die nicht gepushten Versionen 1.8.171–1.8.174 heißen 1.9.0–1.9.3 -- im Changelog (mit
  Vermerk unter jeder Überschrift: zuerst als 1.8.17x committet, mit Commit), in `VERSION`, CLAUDE.md, Kommentaren, Tests und in diesem
  Archiv (die Abschnitte von Runde 2 oben heißen jetzt 1.9.0–1.9.3, die Festlegungen 1.8.172–1.8.174 sind 1.9.1–1.9.3). Die Commits
  `0838162`, `9de69fb`, `bc2b7e4`, `f1fcac7` behalten ihre Nachrichten. Diese Runde zählt ab 1.9.4.
- **Vorschlag für Regel 8 (nicht festgeschrieben):** „Ein Minor-Sprung (`1.X.0`) markiert die Einführung eines neuen, echten Moduls
  **oder den Beginn einer großen, über viele Seiten sichtbaren Überarbeitung** (z. B. Stufe 2 des Redesigns: 1.9.0); was dazu zählt,
  legt der Betreiber fest. Innerhalb zählt der Patch-Level weiter. Alles andere bleibt Patch-Level -- Infrastruktur, Fixes, einzelne
  Anpassungen an bestehenden Modulen.“

### Punkt 2: Befund Dachtyp (nur festgehalten, nichts geändert)

Anlass: die Testdaten der Bildgrundlage speichern an einer Prüfvorlage „flachdach“, die Liste der Prüfvorlagen zeigt seit 1.9.3 den
Namen aus der Auswahlliste ohne Rücksicht auf die Schreibweise (Nebenbefund 1.9.3).

**Was das Programm speichert.**

- Vier Spalten tragen einen Dachtyp, alle freier Text (`String(80)`), kein Fremdschlüssel, keine Prüfung gegen die Auswahlliste:
  `inspection_templates.roof_type` (leer = jeder Dachtyp), `roof_type_inspection_template_defaults.roof_type` (eindeutig),
  `roof_areas.roof_type`, `roof_layer_types.roof_type` (Schichttypen des Dachaufbaus). Die Schemas `InspectionTemplateCreate/Update`
  und `RoofAreaCreate/Update` nehmen jeden Text an (`str | None`).
- Die Oberfläche schreibt den Wert (`value`) eines Eintrags der Auswahlliste „Dachtypen“ (`roof_types`). Vorgabe
  (`app/option_settings.py`, `DEFAULT_OPTION_GROUPS`): Steildach, Flachdach, Gründach, Terrasse -- Wert gleich Bezeichnung, groß
  geschrieben.
- Die Migrationen schreiben dieselbe Schreibweise: `09b654357a58` (Startvorlagen „Flachdach“, „Steildach“), `b8adafd0b997`
  (Schichttypen mit Dachtyp Steildach, Flachdach, Gründach; `flachdach_*` sind dort Schlüssel der Schichttypen, kein Dachtyp),
  `06299a5101f5` übernimmt die vorhandenen Werte der Vorlagen in die Standardzuordnung.
- **„flachdach“ klein schreibt weder das Programm noch eine Migration** -- nur die Testdaten der Bildgrundlage
  (`pruefvorlage_anlegen(…, roof_type="flachdach")`).

**Was aus älteren Versionen in der Datenbank stehen kann.**

- Eine andere Schreibweise aus dem Programm: keine gefunden (Migrationskette und Grunddaten durchgesehen).
- Werte eines später umbenannten Eintrags: in Einstellungen → Auswahllisten ist „Wert / Text“ frei änderbar
  (`PUT /api/settings/option-groups/roof_types/options/{id}` mit `value`), ein Eintrag lässt sich auch löschen -- gespeicherte
  Vorlagen, Zuordnungen, Dachflächen und Schichttypen behalten den alten Wert.
- Werte eines deaktivierten Eintrags (bleibt in der Liste, `active` falsch).
- Jeder Text, der über die Schnittstelle oder direkt in der Datenbank gesetzt wurde.

**Was im Editor einer Prüfvorlage passiert** (`inspection_template.html`).

- `roofTypeOptionsHtml()` (Zeile 105 f.) wählt nur einen Eintrag vor, dessen Wert genau gleich ist (`selected===o.value`), nicht über
  `auswahlOptionen()` (Regel 22). Ein Wert ohne genau passenden Eintrag erscheint nicht, die Auswahl zeigt „— jeder Dachtyp —“.
  Deaktivierte Einträge liefert die Schnittstelle mit, sie werden vorgewählt (ohne Kennzeichnung).
- Belegt mit der Funktion selbst (in node, Auswahlliste der Vorgabe, Terrasse deaktiviert): „flachdach“ → nichts vorgewählt;
  „Flachdach“ → Flachdach; „Terrasse“ → Terrasse; „Pultdach“ (nicht in der Liste) → nichts.
- **Speichern:** `saveTemplateMeta()` (Zeile 130) schickt `roof_type: <Auswahl> || null` mit, auch wenn nur Bezeichnung oder
  Beschreibung geändert wurden; `update_template()` setzt `roof_type` auf leer und erhöht die Version. **Der Altwert ist danach still
  weg, die Vorlage gilt für jeden Dachtyp.** Der Endpunkt steht in `BEKANNT` (`test_v329`, „volles Formular“) -- das Formular schickt
  zwar alle Felder, aber einen Wert, den es nicht anzeigen konnte.
- Zum Vergleich die Dachfläche (`roof_area.html`): sie baut ihre Auswahl über `auswahlOptionen()`, der Altwert bleibt vorgewählt
  („flachdach (nicht mehr verfügbar)“) und geht beim Speichern unverändert zurück.

**Was ein Altwert sonst bewirkt (überall genauer Vergleich, Groß-/Kleinschreibung zählt).**

- Einsatzbericht: `_resolve_inspection_template()` (`app/service_reports.py`) sucht die Standardvorlage und danach eine Vorlage mit
  genau dem Dachtyp der Dachfläche. Eine Dachfläche „flachdach“ findet weder die Standardvorlage „Flachdach“ noch eine Vorlage
  „Flachdach“ -- nur eine unter „flachdach“ zugeordnete, eine Vorlage „flachdach“ oder die für jeden Dachtyp; umgekehrt ebenso.
- Standardvorlage je Dachtyp (Einstellungen): `list_roof_type_template_defaults()` listet nur aktive Werte der Auswahlliste -- eine
  Zuordnung unter einem Altwert ist dort unsichtbar, wirkt im Einsatzbericht aber weiter.
- Dachaufbau einer Dachfläche: Schichttypen genau nach Dachtyp (`app/roof_areas.py`, Zeile 391) -- „flachdach“ zeigt keine
  Flachdach-Schichten.
- Liste der Prüfvorlagen (seit 1.9.3): `dachtypName()` vergleicht ohne Rücksicht auf die Schreibweise und zeigt „Flachdach“ -- das
  **verdeckt** die Abweichung, die der Einsatzbericht macht. Bei einer Behebung dort die Abweichung kennzeichnen statt angleichen.

**Abfrage für den Server:** `scripts/pruefabfrage_dachtypen.sql` (nur lesend: schreibgeschützte Transaktion, endet mit `ROLLBACK`;
Aufruf `psql -d dachkonzepte -f scripts/pruefabfrage_dachtypen.sql`). Zwei Ergebnisse: jeder Wert je Ort mit Anzahl (die Auswahlliste mit
„aktiv“, dazu die vier Spalten), und jeder Wert, den kein Eintrag der Auswahlliste genau so trägt -- mit dem Eintrag, der nur in der
Schreibweise abweicht. Geprobt gegen die lokale PostgreSQL-Spielwiese in einem Wegwerf-Schema (Grunddaten, dazu Vorlagen „flachdach“,
„Flachdach“ und „jeder Dachtyp“, Dachflächen „flachdach“, „Steildach“, „Pultdach“, Standardzuordnung „Flachdach“): beide Ergebnisse wie
erwartet (zweites: Dachfläche „flachdach“ → Flachdach, Dachfläche „Pultdach“ → ohne Entsprechung, Prüfvorlage „flachdach“ →
Flachdach), Zeilenzahlen vorher und nachher gleich, Schema danach gelöscht.

**Mögliche Behebung (nicht gebaut, zur Entscheidung nach dem Ergebnis der Abfrage):** Editor der Prüfvorlage über `auswahlOptionen()`
wie die Dachfläche (Altwert bleibt vorgewählt und gekennzeichnet); Werte, die nur in der Schreibweise abweichen, per Migration auf den
Wert der Auswahlliste bringen -- erst, wenn die Abfrage auf dem Server zeigt, dass es solche gibt.

### Punkt 1 (1.9.4): Grundregeln mit Gewicht null über `:where()`

- **`ds-basis.css`**: jeder Selektor steht ganz in `:where(…)` -- Spezifität 0,0,0. Die Grundregeln gelten wieder für alle Elemente
  (auch für Knöpfe und Links mit Klasse), jede Klasse überstimmt sie. Ersetzt Festlegung 1.9.3 Nr. 5 („nur ohne Klasse“, `:not([class])`).
  Gilt für alle Regeln der Datei, auch für `.ds-seite` selbst, Felder, Überschriften und den Fokusrahmen: bis 1.9.3 überstimmte
  `.ds-seite input` (0,1,1) die Klasse eines Felds (0,1,0), jetzt nicht mehr. Bei gleichem Gewicht entscheidet die Reihenfolge -- die
  Tablet-Regeln stehen hinter den allgemeinen. Die Regeln selbst (Werte, Reihenfolge) sind unverändert.
- **Beleg im Browser** (`klicktest_rahmen`, Teil `pruefvorlagen`, hell und dunkel): grüner Knopf mit Schrift auf-aktion und 10 px Ecken,
  Leiste in navi-text, „Mein Konto“ im Kontomenü in Textfarbe -- wie in 1.9.3. Neu eingeschoben und gemessen: ein alter Knopf mit eigener
  Klasse (ohne Regel für Schrift und Ecken) bekommt Schrift, Größe und 10 px Ecken wie ein Knopf ohne Klasse; ein Link mit und einer ohne
  Klasse stehen in Linkfarbe; die Klasse einer Seite überstimmt die Ecken eines Felds (0 px) und die Farbe eines Links.
- **Pixelgleich**: Bildgrundlage `--nur pruefvorlagen` (412 und 1440 px, hell und dunkel) und Fenster 1440 × 900 mit offenem Menü „⋮“
  und offenem Editor (hell und dunkel) vor und nach der Umstellung -- 8 von 8 Bildern ohne ein abweichendes Pixel.
- Folge, gewollt: ein Link mit Klasse, dessen Klasse keine Farbe setzt, steht auf einer umgezogenen Seite jetzt in Linkfarbe (bis 1.9.3
  in der geerbten Farbe). Auf den Prüfvorlagen gibt es keinen solchen (pixelgleich); ein Baustein, der eine andere Farbe will, setzt sie
  in seiner Klasse.

#### Tests und Prüfung

- **Gegenproben** (pytest und Klicktest): Knopf wieder nur ohne Klasse (`test_grundregeln_mit_gewicht_null` rot, Klicktest 20 von 22:
  alter Knopf ohne Schrift und Ecken); Feld wieder mit Gewicht (Wächter und Test rot, Klicktest 20 von 22: Klasse der Seite überstimmt
  die Ecken nicht); Link wieder mit Gewicht (Wächter und Test rot, Klicktest 18 von 22: Leiste in Linkfarbe) -- 3 von 3 rot, Datei
  byte-genau zurück.
- **Angepasste Erwartungen** (Regel 28):
  - `test_v441::basis_verstoesse` (Wächter): alt „jeder Selektor beginnt mit `.ds-seite`“, neu „jeder Selektor ganz in `:where(…)`,
    darin jeder Teil unter `.ds-seite`“; Beispiele in `test_waechter_ds_basis_findet` von 7 auf 11 (die alte Form `.ds-seite a` ist jetzt
    ein Fund), `test_waechter_ds_basis_laesst_durch` in der `:where`-Form.
  - `test_v441::test_grundregeln_fuer_a_und_button_nur_ohne_klasse` ersetzt durch `test_grundregeln_mit_gewicht_null`: alt „Regeln für
    `a` und `button` tragen `:not([class])`“, neu „kein `:not([class])`, je eine Regel für a, a:hover, button, input, select, textarea,
    h1–h3, :focus-visible“.
  - `klicktest_rahmen` Teil `pruefvorlagen`: neue Prüfung „Grundregeln mit Gewicht null“ je Thema (Teil 20 → 22 Prüfungen).

#### Festlegungen 1.9.4 (Bitte bestätigen)

1. **Gewicht null für jede Regel von `ds-basis.css`**, nicht nur für `a` und `button` -- auch `.ds-seite` selbst, Felder, Überschriften,
   Fokusrahmen; der Wächter verlangt `:where(…)` um jeden Selektor.
2. **Reihenfolge statt Gewicht** innerhalb der Datei: die Tablet-Regeln stehen hinter den allgemeinen und gelten deshalb.

### Punkt 3 (1.9.5): Runde 3 -- Farben aller Seiten

- **Keine Kopie der alten Palette mehr in den Seiten**: 53 Vorlagen trugen im `:root` (hell) und 52 im
  `:root[data-theme="dark"]` dieselben alten Werte (`--bg`, `--card`, `--ink`, `--muted`, `--line`, `--field-border(-hover)`,
  `--soft`, `--danger(-soft)`, `--warning(-soft)`, `--success(-soft)`, `--info(-soft)`), dazu `--accent` aus der Akzentfarbe der
  Einstellungen und die seit 1.8.162 ungelesenen `--sidebar-*` -- 1834 Deklarationen in 60 Vorlagen, entfernt mit einem Werkzeug
  (Scratchpad der Runde, `umbau_p3.py`). Es bleiben Schrift, `color-scheme`, `color:var(--ink)` und eigene Werte einer Seite
  (`--dayw`, `--travel-btn`, `--workshop-btn`, `--other-btn`).
- **Zentral**: `app/static/ds/ds-alte-namen.css`, über `_ds_kopf.html` mit Prüfsumme eingebunden (Global
  `ds_alte_namen_pruefsumme`). Ein `:root`-Block genügt für hell und dunkel -- die Werte zeigen auf `--ds-*`, die `ds.css` je Thema
  setzt. Zuordnung: `--bg`→`--ds-grund`, `--card`→`--ds-flaeche`, `--soft`→`--ds-flaeche-2`, `--ink`→`--ds-text`, `--muted`→
  `--ds-text-2`, `--line`→`--ds-linie`, `--field-border`→`--ds-feld-rand`, `--field-border-hover`→`--ds-text-3`, `--accent`→
  `--ds-aktion-text`, `--danger`→`--ds-fehler-text`, `--warning`→`--ds-warn-text`, `--success`→`--ds-ok-text`, `--info`→
  `--ds-info-text`, die `-soft`-Namen → die `-hell`-Werte.
- **Text oder Fläche**: die Doppelnamen (`--accent`, `--danger`, `--warning`, `--success`, `--info`) zeigen zentral auf den Textwert.
  Jede Verwendung in einer Vorlage wurde nach ihrer Eigenschaft eingeordnet (rückwärts bis zum Doppelpunkt, auch in `style="…"` und in
  Zeichenketten des Skripts): als Textfarbe (`color`, `caret-color`, `text-decoration-color` …) bleibt der alte Name; als Fläche
  (Hintergrund, Rahmen, Umriss, Schatten, auch in `color-mix()`) steht direkt der Flächenwert -- `--accent`→`--ds-aktion` (342 Stellen),
  `--danger`→`--ds-fehler` (52), `--warning`→`--ds-warn-text` (31, es gibt keinen eigenen Flächenwert), `--success`→`--ds-ok` (7),
  `--info`→`--ds-info` (1). Als Text blieben 113 × `--accent`, 127 × `--danger`, 55 × `--warning`, 29 × `--success`. Keine Stelle
  ließ sich nicht einordnen.
- **Feste alte Werte**: der Verlauf (`.old` `#a53636`, `.new` `#1f8a5f` = altes `--success`), die Kundenakte (`.status.ok`), die
  Stammdaten (`#fbeae8`) nehmen jetzt die alten Namen; Rückfallwerte `var(--x,#…)` entfallen (Versandverlauf, Checklisten-Abschnitt,
  `_speichern.html`). Bewusst fest bleiben die Unterschriftsfläche (`_unterschrift.html`, weiß in beiden Themen) und die Signaturkarte
  der Checkliste (`checklist.html` `.sig`, auf weißem Grund).
- **Akzentfarbe**: färbt die Oberfläche nicht mehr (Stufe 2, Entscheidung 1.8.161). Sie bleibt für das App-Symbol und das Manifest
  (`theme_color`) und die `theme-color` der Monteursansicht (`mobil.html`). In den Einstellungen keine Vorschau mehr auf der Seite
  (`previewAccentColor()` prüft nur noch den Kontrast), Untertitel „Akzentfarbe des App-Symbols“, Hinweis „Färbt seit 1.9.5 nur noch …“.

#### Kontrast je Seite, vorher und nachher

Gemessen mit einer Instanz der Bildgrundlage (feste Testdaten, stehende Uhr; Werkzeug `messen_p3.py` im Scratchpad der Runde): jede
Aufnahme der Bildgrundlage je Rolle, hell und dunkel, bei 1440 × 900, die Seiten der Monteurin zusätzlich bei 412 × 900 und 1280 × 620
-- 160 Messungen. Geprüft wird jedes sichtbare Element mit eigenem Text und jedes gefüllte Feld gegen seinen tatsächlichen Hintergrund
(4,5 : 1, großer Text 3 : 1), 21 540 je Lauf; Rahmen von Bedienelementen (3 : 1) sind nicht Teil der Messung. Vorher = Commit `3e54421`
(1.9.4, Worktree), nachher = Arbeitskopie mit dem Umbau.

- **Fehlstellen gesamt: vorher 1183 (hell 617, dunkel 566), nachher 0.** Davon vorher 796 die Versionsmarken im Changelog
  (`.entry-version`, Text in der Akzentfarbe). 142 Messungen besser, 18 gleich (0 → 0), **keine schlechter**; keine neuen JS-Fehler.
- Ein erster Nachher-Lauf ließ 18 Fehlstellen, alle im Verlauf (`.old`/`.new` mit festen alten Werten, s. o.) -- umgestellt, zweiter
  Lauf 0.

| Seite | hell vorher → nachher (kleinster Kontrast) | dunkel vorher → nachher (kleinster Kontrast) |
|---|---|---|
| start | 3 → 0 (3,74 → 5,73) | 2 → 0 (4,34 → 4,71) |
| aufgaben | 1 → 0 (3,74 → 5,73) | 1 → 0 (3,74 → 4,71) |
| kalender | 3 → 0 (3,39 → 5,73) | 3 → 0 (3,74 → 4,71) |
| anfragen | 1 → 0 (3,74 → 5,73) | 1 → 0 (3,74 → 4,71) |
| projekte | 2 → 0 (3,74 → 5,73) | 2 → 0 (3,74 → 4,71) |
| projekt_neu | 2 → 0 (3,45 → 5,73) | 1 → 0 (3,74 → 4,71) |
| projektmappe | 6 → 0 (3,45 → 5,73) | 3 → 0 (3,74 → 4,71) |
| angebot_neu | 2 → 0 (3,45 → 5,73) | 1 → 0 (3,74 → 4,71) |
| angebot | 7 → 0 (3,45 → 5,73) | 5 → 0 (3,74 → 4,71) |
| auftrag | 7 → 0 (3,45 → 5,73) | 5 → 0 (3,74 → 4,71) |
| arbeitsvorbereitung | 2 → 0 (3,74 → 5,73) | 2 → 0 (3,74 → 4,71) |
| einsatzbericht | 18 → 0 (3,45 → 5,73) | 12 → 0 (3,74 → 4,71) |
| rechnung | 5 → 0 (3,45 → 5,73) | 2 → 0 (3,74 → 4,71) |
| plantafel | 2 → 0 (3,74 → 5,73) | 2 → 0 (3,74 → 4,71) |
| checklisten | 2 → 0 (3,74 → 5,73) | 1 → 0 (4,34 → 4,71) |
| checklistenvorlagen | 4 → 0 (3,74 → 5,73) | 3 → 0 (3,74 → 4,71) |
| checklistenvorlage | 5 → 0 (3,45 → 5,73) | 2 → 0 (3,74 → 4,71) |
| checkliste | 16 → 0 (3,45 → 5,73) | 8 → 0 (3,74 → 4,71) |
| checklisten_auftrag | 12 → 0 (3,45 → 5,73) | 8 → 0 (4,34 → 4,71) |
| wartungen | 3 → 0 (3,74 → 5,73) | 3 → 0 (3,74 → 4,71) |
| wartungsvertrag | 4 → 0 (3,45 → 5,73) | 2 → 0 (3,74 → 4,71) |
| befunde | 2 → 0 (3,74 → 5,73) | 1 → 0 (4,34 → 4,71) |
| pruefvorlagen | 0 → 0 (5,73 → 5,73) | 0 → 0 (4,71 → 4,71) |
| pruefvorlage | 3 → 0 (3,45 → 5,73) | 2 → 0 (3,74 → 4,71) |
| finanzen | 3 → 0 (3,74 → 5,73) | 3 → 0 (3,74 → 4,71) |
| mahnwesen | 2 → 0 (3,74 → 5,73) | 2 → 0 (3,74 → 4,71) |
| eingangsrechnungen | 2 → 0 (3,74 → 5,73) | 1 → 0 (3,74 → 4,71) |
| betriebskosten | 1 → 0 (3,74 → 5,73) | 1 → 0 (3,74 → 4,71) |
| zeiterfassung | 2 → 0 (3,74 → 5,73) | 2 → 0 (3,74 → 4,71) |
| zeiterfassung_monteur | 0 → 0 (4,74 → 5,73) | 0 → 0 (4,71 → 4,71) |
| backoffice | 2 → 0 (3,74 → 5,73) | 2 → 0 (3,74 → 4,71) |
| stammdaten | 6 → 0 (3,74 → 5,73) | 6 → 0 (3,74 → 4,71) |
| stammdaten_mitarbeiter | 2 → 0 (3,74 → 5,73) | 2 → 0 (3,74 → 4,71) |
| kunde | 9 → 0 (3,74 → 5,73) | 9 → 0 (3,74 → 4,71) |
| objekt | 9 → 0 (3,45 → 5,73) | 8 → 0 (3,74 → 4,71) |
| dachflaeche | 4 → 0 (3,45 → 5,73) | 2 → 0 (3,74 → 4,71) |
| betriebsmittel | 5 → 0 (3,45 → 5,73) | 4 → 0 (3,74 → 4,71) |
| betriebsmittel_monteur | 0 → 0 (4,92 → 5,73) | 0 → 0 (4,71 → 4,71) |
| leistungskatalog | 5 → 0 (3,45 → 5,73) | 4 → 0 (3,74 → 4,71) |
| leistung | 3 → 0 (3,45 → 5,73) | 2 → 0 (3,74 → 4,71) |
| einstellungen | 3 → 0 (3,74 → 5,73) | 3 → 0 (3,74 → 4,71) |
| benutzer | 2 → 0 (3,45 → 5,73) | 1 → 0 (3,74 → 4,71) |
| verlauf | 10 → 0 (3,45 → 5,73) | 15 → 0 (2,46 → 4,71) |
| adressimport | 2 → 0 (3,45 → 5,73) | 1 → 0 (3,74 → 4,71) |
| versandprotokoll | 0 → 0 (5,35 → 5,73) | 0 → 0 (4,71 → 4,71) |
| changelog | 398 → 0 (3,39 → 5,73) | 398 → 0 (3,93 → 4,71) |
| suche | 2 → 0 (3,74 → 5,73) | 2 → 0 (3,74 → 4,71) |
| konto | 8 → 0 (3,45 → 5,73) | 4 → 0 (3,74 → 4,71) |
| mobil | 9 → 0 (3,74 → 5,73) | 6 → 0 (3,74 → 4,71) |
| mobil_objekt | 8 → 0 (3,74 → 5,73) | 8 → 0 (3,74 → 4,71) |
| stundenzettel | 4 → 0 (3,74 → 5,73) | 4 → 0 (3,74 → 4,71) |
| anmeldung | 1 → 0 (3,74 → 5,73) | 1 → 0 (3,74 → 4,71) |
| sperrseite | 3 → 0 (3,74 → 5,73) | 3 → 0 (3,74 → 4,71) |

(Zusammengefasst über Rollen und Breiten; „kleinster Kontrast“ = kleinster gemessener Wert der Seite.)

#### Maße: nur Farben geändert

Dieselben 160 Messungen nehmen `getBoundingClientRect()` jedes Elements unter `body` in Dokumentreihenfolge und Breite/Höhe des
Bildlaufs: **alle 160 vorher und nachher gleich** (jedes Element, auf die Hundertstel Pixel). Gegenprobe am Werkzeug: 1 px Polster an
`.new` und hellgraues `.old` im Verlauf (Marker, byte-genau zurück) → 1018 Elemente mit anderen Maßen, 6 neue Fehlstellen.

#### Tests und Prüfung

- `tests/test_v442_alte_farbnamen.py` (neu, 13 Tests): `ds-alte-namen.css` nur `:root` mit genau der Zuordnung, jeder Wert in `ds.css`
  hell und dunkel; `_ds_kopf.html` bindet die Datei mit Prüfsumme ein; keine Vorlage definiert einen alten Namen oder `--sidebar-*`;
  keine Rückfallwerte an alten Namen; Akzentfarbe nur im `theme-color` von `/mobil`; Doppelnamen nur als Textfarbe (Wächter mit
  Beispielen).
- **Gegenproben** (pytest, drei auch Klicktest `klicktest_ds_schriften`): Kopie `--card:#fff` in der Projektliste; `--accent` als
  Hintergrund im Auftrag; zentral `--accent` auf `--ds-aktion`; Akzentfarbe wieder im `:root` der Anmeldeseite; Kopf ohne
  `ds-alte-namen.css` -- 5 von 5 rot, Dateien byte-genau zurück.
- Klicktests `klicktest_akzentfarbe`, `klicktest_ds_schriften`, `klicktest_behinderungsanzeige_versand`, `klicktest_feste_fassung`,
  `klicktest_rahmen`: 5 von 5 wie erwartet (513 Prüfungen).
- **Angepasste Erwartungen** (Regel 28):
  - `test_v432::test_ds_kopf_bindet_ds_css_und_ds_basis_mit_pruefsumme_ein`: alt zwei Zeilen (ds.css, ds-basis.css), neu drei (dazu
    ds-alte-namen.css).
  - `test_v252::…globals…`: alt 10 Globals (2 Prüfsummen), neu 11 (`ds_alte_namen_pruefsumme`).
  - `test_v272::test_get_theme_is_used_in_root_block_of_every_page_including_mobile_header` ersetzt durch
    `test_monteursseiten_nehmen_die_alten_farbnamen_zentral`: alt „`get_theme().accent_color` im `:root` der vier Monteursseiten“, neu
    „kein `get_theme()`, `--accent:`, `--card:` im `:root`, `_ds_kopf.html` eingebunden“.
  - `klicktest_ds_schriften`: alt „Akzentfarbe unverändert“ (`--accent` = Akzentfarbe der Einstellungen) und zwei Stylesheets; neu
    `--accent` = `--ds-aktion-text` (hell `#2a5c2b`, dunkel `#b9da86`), drei Stylesheets, Kopfzeilen auch für `ds-alte-namen.css`.
  - `klicktest_akzentfarbe`: alt „Vorschau beim Tippen“, „nach dem Neuladen gilt die neue Farbe“ und „Büro sieht die neue Farbe“ an
    `--accent`, „Farbe unverändert“ an `--accent`; neu keine Vorschau (`--accent` bleibt `--ds-aktion-text`), neue Farbe im Manifest
    (`theme_color`) bei unveränderter Seite für Admin und Büro, „Farbe unverändert“ am Manifest.
  - `test_v419_verbindungen::test_die_globals_lesen_die_seitendaten_der_schranke`: alt „Akzentfarbe `#123456` auf `/projects`“, neu
    „nicht auf `/projects`, aber in der `theme-color` von `/mobil`“ (Modul-Schalter und Konto unverändert).
  - `test_v425_seitendaten_nur_fuer_seiten` (Monteurin, ungültiger Pfad → Sperrseite 403): alt „gezeichnet → einmal nachgeladen“, neu
    „die Sperrseite lädt nichts nach“ -- sie liest seit 1.9.5 keine Seitendaten mehr (bis dahin nur die Akzentfarbe über `get_theme()`),
    eine Datenbankverbindung weniger.
- Erster voller Lauf mit 1.9.5: 4 rot -- die zwei oben und zwei Zeittests gegen PostgreSQL (`test_v376_nummernkreise::…waits_for_the_delete…`,
  `test_v419_verbindungen_unter_last::test_langsame_downloads_halten_keine_verbindung`), die parallel zu Bildaufnahmen liefen; einzeln grün,
  im nächsten vollen Lauf ohne Nebenlast geprüft.

#### Festlegungen 1.9.5 (Bitte bestätigen)

1. **Eigene Datei `ds-alte-namen.css`** statt `ds.css` (Regel 37 lässt dort nur `--ds-*` zu), ein `:root`-Block für beide Themen.
2. **`--field-border-hover` → `--ds-text-3`**: es gibt keinen Hover-Wert für Feldrahmen; `--ds-text-3` ist kräftiger als
   `--ds-feld-rand`, wie früher der Hover kräftiger als der Rahmen war (`--ds-linie-stark` wäre heller).
3. **Fläche = jede Eigenschaft außer Textfarbe** (Hintergrund, Rahmen, Umriss, Schatten, Tönungen in `color-mix()`).
4. **`--warning` als Fläche → `--ds-warn-text`** (kein eigener Flächenwert für Warnung).
5. **Fokusrahmen der Seiten** (`outline` aus `--accent`, 47 Stellen) → `--ds-aktion`, nicht `--ds-fokus`; auf `--ds-fokus` beim Umzug der
   jeweiligen Seite.
6. **`--sidebar-*` ersatzlos gestrichen** (seit 1.8.162 ungelesen).
7. **Feste alte Farben und Rückfallwerte in Seiten entfallen**; fest bleiben Unterschriftsfläche und Signaturkarte (weiß in beiden
   Themen).
8. **Akzentfarbe nur noch für App-Symbol, Manifest und `theme-color` von `/mobil`**; die Einstellungen zeigen keine Vorschau mehr und
   sagen, wofür die Farbe noch gilt.

#### Nachtrag 1.9.5: vier Klicktests mit festen alten Farbwerten

- Der Endlauf auf `4cb9b79` (alle Klicktests) fand vier Klicktests, die fest mit Werten der alten Palette verglichen -- veraltete
  Erwartungen seit 1.9.5, kein Fehler der Seiten. Vor dem Commit liefen nur die fünf Klicktests, die `--accent` lesen; die vier fielen
  erst im Gesamtlauf auf (Regel 26). Ein erster Gesamtlauf scheiterte vorher an einem schon benutzten Ausgabeordner (alle 80 nach
  0:00 „Arbeitsordner ist nicht leer“) und wurde mit neuem Ordner wiederholt.
- **Angepasste Erwartungen** (Regel 28):
  - `klicktest_checkliste_verwerfen` „Abweichung in der Warnfarbe“: alt hell `rgb(192, 54, 44)` (#c0362c), dunkel `rgb(242, 131, 122)`;
    neu `--ds-fehler-text` hell `rgb(143, 26, 26)`, dunkel `rgb(246, 170, 168)`.
  - `klicktest_versandprotokoll` „Hintergrund hell/dunkel“: alt `rgb(244, 246, 245)` / `rgb(18, 24, 22)`, neu `--ds-grund`
    `rgb(238, 240, 241)` / `rgb(18, 22, 25)`; „Warnkarte nicht weiß“ dunkel: alt `rgb(58, 47, 20)`, neu `--ds-warn-hell` `rgb(54, 32, 15)`.
  - `klicktest_versandverlauf` Pille „Gesendet“: alt hell `rgb(234, 245, 239)`, dunkel `rgb(23, 50, 38)`; neu `--ds-ok-hell`
    `rgb(238, 245, 232)` / `rgb(23, 40, 26)`.
  - `klicktest_beleg_und_hinweis` „deutlich/lesbar“ (Hinweis „Offene Bedenken“): alt „Rahmenfarbe = Textfarbe“ (beide `--danger`), neu
    „Rahmen `--ds-fehler`, Text `--ds-fehler-text`“ (Fläche und Text getrennt, Festlegung 1.9.5 Nr. 3).
- Die vier einzeln: 4 von 4 wie erwartet (124 Prüfungen). Übrige Klicktests mit festen alten Werten: keine (Suche über `scripts/`).

### Ergebnis der Endläufe (Nachtrag zu Runde 2 und Runde 3)

- Auf `d56c7d7` (1.9.5 Nachtrag) bei sauberer Arbeitskopie (vorher und nachher keine Änderung): **volle Suite 6290 bestanden, 3
  übersprungen, 0 rot** (7:56); **alle Klicktests 80 von 80 wie erwartet** (2377 Prüfungen, zu viert, 7:54).
- Commits der Runde: `085dd5d` (Punkt 0, Versionsnummern 1.9.0–1.9.3), `56e13e3` (Punkt 2, Befund Dachtyp mit
  `scripts/pruefabfrage_dachtypen.sql`), `3e54421` (1.9.4, Punkt 1), `4cb9b79` (1.9.5, Punkt 3), `d56c7d7` (1.9.5 Nachtrag).
- **Bilder**: `bildgrundlage/rahmen_runde3_4cb9b79.zip` -- Start, Projektmappe, Rechnung, LV-Editor, Zeiterfassung Büro je 1440 × 900
  hell und dunkel, `/mobil` als Monteurin 1280 × 620 hell und dunkel; je vorher (`3e54421`) und nachher (der Nachtrag ändert nur
  Klicktests). Ordner in `.gitignore`.

## Runde 4 (Festlegungen 1.9.4 und 1.9.5 bestätigt)

### Punkt 0: Regel 8 ergänzt (nur CLAUDE.md, `520241c`)

- Wortlaut (Betreibervorgabe 21.10.2026): „Ein Minor-Sprung markiert ein neues, echtes Modul oder den Beginn einer großen, über viele
  Seiten sichtbaren Überarbeitung (z. B. Stufe 2: 1.9.0); was dazu zählt, legt Tobias fest. Innerhalb zählt der Patch-Level weiter.“
  Diese Runde zählt ab 1.9.6.

### Punkt 1 (1.9.6): Dachtyp -- Altwerte sichtbar und erhalten

- **a) Editor einer Prüfvorlage** (`inspection_template.html`): die Auswahl entsteht über `auswahlOptionen()` wie bei der Dachfläche.
  Ein gespeicherter Wert ohne Eintrag (andere Schreibweise, umbenannt, gelöscht) bleibt vorgewählt als „… (nicht mehr verfügbar)“,
  ein deaktivierter als „… (inaktiv)“; Speichern des Kopfs schickt ihn unverändert zurück. Bis 1.9.5 stand die Auswahl dann auf
  „— jeder Dachtyp —“, das Speichern löschte den Wert still und erhöhte die Version.
- **b) Liste der Prüfvorlagen** (`inspection_templates.html`, `dachtypZelle()`): der gespeicherte Wert, wie er steht; ohne Eintrag
  mit Marke „nicht mehr verfügbar“, bei deaktiviertem Eintrag „inaktiv“ (`.ds-status-warn`). Ersetzt das Ausschreiben aus 1.9.3, das
  „flachdach“ als „Flachdach“ zeigte, obwohl der Einsatzbericht beide trennt.
- **c) Testdaten der Bildgrundlage**: die Prüfvorlage „Flachdach-Wartung“ trägt „Flachdach“ (bis 1.9.5 „flachdach“); der Altwert
  bleibt als eigener Fall -- Prüfvorlage „Altbestand Flachdach“ mit `DACHTYP_ALTWERT = "flachdach"` (`scripts/bildgrundlage.py`,
  Seed `pruefvorlage_altwert`). Die Liste der Prüfvorlagen zeigt damit beide Fälle.
- **d) Abfrage auf dem Server**, als Benutzer `tobias` (Pfad laut Betriebsdoku: `/home/tobias/erp`, Umgebung `.env`, Datenbank
  `dachkonzepte`; einen eigenen Datenbank-Benutzer nennt die Betriebsdoku nicht -- der Befehl nimmt den der Anwendung aus
  `DATABASE_URL`):

      cd /home/tobias/erp
      set -a; source .env; set +a
      PGOPTIONS='-c default_transaction_read_only=on' psql "${DATABASE_URL/postgresql+psycopg:/postgresql:}" -v ON_ERROR_STOP=1 -f scripts/pruefabfrage_dachtypen.sql

  `${…/postgresql+psycopg:/postgresql:}` nimmt den Treiberzusatz weg, den psql nicht kennt; `PGOPTIONS` macht jede Transaktion der
  Sitzung schreibgeschützt (dazu die Abfrage selbst: `BEGIN TRANSACTION READ ONLY` … `ROLLBACK`). Steht so im Kopf der Abfrage. Die
  zweite Abfrage prüft jetzt mit `NOT EXISTS` statt `NOT IN` (robust gegen leere Werte). **Geprobt wörtlich** in Git Bash mit einer
  `.env` wie auf dem Server gegen die lokale Spielwiese (nur zusätzlich `search_path` auf ein Wegwerf-Schema): Abfrage Rückgabecode 0,
  beide Ergebnisse wie erwartet; ein `DELETE` in derselben Art Sitzung scheitert („DELETE kann nicht in einer Read-Only-Transaktion
  ausgeführt werden“); Zeilenzahlen unverändert, Schema gelöscht.

#### Tests und Prüfung

- `tests/test_v443_dachtyp.py` (neu, 7 Tests, die Seiten in node mit Antworten des echten Dienstes): Editor mit „flachdach“,
  „Pultdach“, „Terrasse“ (deaktiviert), „Flachdach“ und ohne Dachtyp -- vorgewählt und gesendet; Liste mit fünf Vorlagen; Testdaten
  der Bildgrundlage per AST. **Vor der Änderung 5 rot** (Editor: „— jeder Dachtyp —“ vorgewählt, gesendet `null`; Liste: „Flachdach“
  statt „flachdach“; Testdaten: „flachdach“ ohne Erklärung), danach 7 grün.
- `klicktest_rahmen` Teil `pruefvorlagen`: Editor der Vorlage mit Altwert -- vorgewählt, Kopf gespeichert, nach dem Neuladen weiter
  „flachdach“ (5 neue Prüfungen, 27 von 27).
- **Gegenproben** (pytest und Klicktest): Editor wieder mit dem Vergleich von vorher (3 rot, Klicktest 25 von 27); Liste ohne Marke
  (1 rot, Klicktest 25 von 27) -- 2 von 2 rot, Dateien byte-genau zurück.
- **Angepasste Erwartungen** (Regel 28):
  - `klicktest_rahmen` „Dachtyp ausgeschrieben“ → „Dachtyp wie gespeichert (Altwert markiert)“: alt `["Flachdach"]`, neu
    `["Flachdach", "flachdach nicht mehr verfügbar"]` (zweite Vorlage aus den Testdaten); Teil `pruefvorlagen` 22 → 27 Prüfungen.
  - Bildgrundlage: Testdaten mit einer Prüfvorlage mehr -- ändert die Liste der Prüfvorlagen und die Prüfvorlage (Dachtyp jetzt
    „Flachdach“ vorgewählt statt „— jeder Dachtyp —“).

#### Festlegungen 1.9.6 (Bitte bestätigen)

1. **Marken der Liste wie im Editor**: „nicht mehr verfügbar“ ohne Eintrag, „inaktiv“ bei deaktiviertem Eintrag, als `.ds-status-warn`.
2. **Deaktivierte Dachtypen im Editor nicht mehr neu wählbar** (`auswahlOptionen()`, Regel 22) -- bis 1.9.5 bot der Editor jeden
   Eintrag an, auch deaktivierte, ohne Kennzeichen.
3. **Altwert der Testdaten als eigene Prüfvorlage** „Altbestand Flachdach“ (`DACHTYP_ALTWERT`), die bisherige trägt „Flachdach“.
4. **Serverbefehl mit dem Datenbank-Benutzer der Anwendung** aus `.env` (keiner in der Betriebsdoku) und doppelt schreibgeschützt
   (`PGOPTIONS` und `BEGIN TRANSACTION READ ONLY`).

### Punkt 2 (1.9.7): Seitenkopf der Gruppe „Titelzeilen und Titelkarten“ (15 Seiten)

- Die 15 Seiten aus `befund-rahmen.md` (K1 ohne die Prüfvorlagen, K2) tragen `.ds-seite` und den gemeinsamen Seitenkopf
  (`teile/seitenkopf.html`, `_seitenkopf.html`): Titel 30 px, Untertitel, höchstens eine grüne Hauptaktion, Weiteres im Menü „⋮“.
  Umgestellt wurde nur, was im Kopf stand; kein Knopf aus dem Inhalt wandert in den Kopf, Filter und Werkzeugleisten bleiben, wo
  sie waren. Kopf-Knöpfe über `data-klick` (`_aktionen.html`), die IDs bleiben (`addLink`).
- **Links in `--ds-link`**: jede Linkregel der Seiten in der Akzentfarbe (`a.link`, `.link`, `td a`, `a.row-link`,
  `.contract-link`) und jeder Link mit `style="…color:var(--accent)…"` -- 24 Stellen. **Fokus in `--ds-fokus`**: die Fokusregeln
  der Seiten (Umriss und Rahmenfarbe, bis dahin `--ds-aktion`) -- 9 Seiten (Festlegung 1.9.5 Nr. 5 für diese Seiten eingelöst).
- Folgen von `.ds-seite` (Grundregeln mit Gewicht null, 1.9.4): Schrift IBM Plex Sans, Überschriften Archivo, Felder und Knöpfe ohne
  eigene Ecken bekommen 10 px -- der Inhalt bleibt, wie er war.

| Seite | Hauptaktion | ins Menü „⋮“ |
|---|---|---|
| Start | -- (keine im Kopf; „+ Widget hinzufügen“ bleibt unter den Widgets) | -- |
| Aufgaben | „+ Aufgabe“ | -- (Filter und „Archivierte anzeigen“ bleiben in der Werkzeugleiste) |
| Checklisten | -- | „Vorlagen verwalten“ (Link, bis dahin Knopf rechts im Kopf) |
| Checklisten-Vorlagen | „+ Neue Vorlage“ | „Archivierte anzeigen“ (Umschalter, bis dahin Häkchen im Kopf) |
| Wartungen & Reparaturen | „+ Wartungsvertrag“ | „Archivierte anzeigen“ (Umschalter, bis dahin Häkchen im Kopf) |
| Mängel (Befunde) | -- | -- (Filter bleiben in der Werkzeugleiste) |
| Eingangsrechnungen | „+ Eingangsrechnung“ | -- |
| Betriebskosten-Übersicht | „+ Kostenposten“ | „Inaktive anzeigen“ (Umschalter, bis dahin Häkchen im Kopf) |
| Projekte | „+ Projekt“ (Link nach /projects/new, bei „Nur Mustervorgänge“ ausgeblendet wie bisher) | -- (Werkzeugleiste mit Suche, Filtern, Liste/Kanban bleibt in der Karte unter dem Kopf) |
| Finanzen | -- | -- |
| Mahnwesen | -- | „Versandprotokoll der Mahnungen“ (Link, bis dahin im Untertitel) |
| Versandprotokoll | -- | -- |
| Changelog | -- | -- |
| Suche | -- | -- (Suchformular und Arten-Filter bleiben in der Karte unter dem Kopf) |
| Zeiterfassung (Büro) | -- (Starten, „+ Manuell buchen“, „Gruppe buchen“ bleiben in ihren Karten) | -- (Auswahl „Mitarbeiter“, nur Admin, in eigener Karte links oben, bis dahin rechts im Titel) |

#### Tests und Prüfung

- `test_v441`: `UMGEZOGEN` um die 15 Seiten (`TITELZEILEN_UND_TITELKARTEN`); neuer Strukturtest
  `test_umgezogene_seite_hat_den_gemeinsamen_kopf` je umgezogener Seite (16): Makro importiert und `_seitenkopf.html` eingebunden,
  genau ein Aufruf des Seitenkopfs, kein eigenes `.hero`/`.head`/`.breadcrumb`/`.back`, genau ein h1, höchstens eine
  `.ds-knopf-aktion` im call-Block, Fokusregeln nur in `--ds-fokus`, keine Linkregel und kein Link-Stil in Akzent- oder Aktionsfarbe.
- `klicktest_rahmen` Teil `kopfgruppe` (neu): je Seite hell und dunkel bei 1440 × 900 -- `.ds-seite`, genau ein h1 mit dem Titel,
  Hauptaktion grün mit Schrift auf-aktion, Menü per Tastatur (Umschalter wechseln den Text, Links mit Ziel, Escape schließt), jeder
  sichtbare Textlink im Inhalt in `--ds-link` (Zeilen- und Kachellinks ausgenommen), erstes Feld mit Fokus im Umriss `--ds-fokus`
  (mit Fokus-Emulation -- das kopflose Chrome hat keinen Fensterfokus), Kontrast jedes Texts auch mit offenem Menü, die Hauptaktion
  tut, was sie tat (Editor offen bzw. Ziel /projects/new). 205 von 205.
- **Gegenproben** (pytest und Klicktest): Befunde ohne `.ds-seite`; Finanzen-Link wieder in der Akzentfarbe; Fokus der Aufgaben wieder
  in `--ds-aktion`; zweite grüne Hauptaktion in den Aufgaben -- 4 von 4 rot (Klicktest je 203 von 205). Die vierte blieb im
  Strukturtest zuerst grün (er zählte im zusammengesetzten Makro, in dem der call-Block nicht steht) -- korrigiert, danach rot.
- **Angepasste Erwartungen** (Regel 28): `test_v441::UMGEZOGEN`: alt `{"inspection_templates.html"}`, neu dazu die 15 Seiten.

#### Festlegungen 1.9.7 (Bitte bestätigen)

1. **Keine Hauptaktion, wo der Kopf keine Aktion hatte** (Start, Checklisten, Mängel, Finanzen, Mahnwesen, Versandprotokoll, Changelog,
   Suche, Zeiterfassung): kein Knopf aus dem Inhalt wandert in den Kopf.
2. **Schalter „Archivierte/Inaktive anzeigen“ aus dem Kopf ins Menü** (wie beim Pilot); in einer Werkzeugleiste mit Filtern
   (Aufgaben, Projekte) bleibt er dort.
3. **Navigation ins Menü statt als Hauptaktion**: „Vorlagen verwalten“ (Checklisten), „Versandprotokoll der Mahnungen“ (Mahnwesen;
   der Untertitel nennt das Menü statt eines Links).
4. **Zeiterfassung**: Titel als h1 über dem Raster (bis dahin h2 in der linken Spalte), Auswahl „Mitarbeiter“ in eigener Karte.
5. **Projekte und Suche**: Kopf über der Karte; Werkzeugleiste bzw. Suchformular bleiben in der Karte.
6. **Textlinks in `--ds-link`, Zeilen- und Kachellinks in Textfarbe** (ganze Zeile klickbar mit Fläche beim Überfahren: Aufgaben auf
   dem Start, Treffer der Suche).
7. **Fokus der Seiten in `--ds-fokus`** (Umriss und Rahmenfarbe).

### Punkt 3 (1.9.8): test_v323, test_v376 und test_v419 ohne Zeitabhängigkeit

Was bis dahin von der Zeit abhing und unter Last kippen konnte, und was jetzt stattdessen gilt:

- **`_run()`** (`tests/test_v375_rechnungen_sperren.py`, benutzt von test_v376 und test_v378–v386): die erste Aktion hielt ihre
  Sperre eine feste Sekunde, dann ließ `_run()` los -- egal, ob die zweite schon wartete -- und verlangte, dass die zweite mindestens
  0,9 s gebraucht hatte. Unter Last (Lauf mit 1.9.5 parallel zu Bildaufnahmen) startete die zweite Aktion erst nach dem Commit der
  ersten, fand den gelöschten Entwurf nicht mehr und scheiterte anders („'NoneType' object has no attribute 'status'“). Jetzt gibt
  `_run()` frei, sobald die zweite Aktion **nachweislich auf die Sperre wartet** (`_wartet_auf_sperre()`: unter PostgreSQL eine nicht
  gewährte Sperre ihres Backends in `pg_locks`; unter SQLite, ohne Sicht auf wartende Sperren, ihre erste schreibende Anweisung --
  die erste hält die Schreibsperre). Statt „≥ 0,9 s“ wird geprüft, dass sie gewartet hat. Das Freigeben im angehaltenen Commit wartet
  nur noch als Sicherheitsnetz (300 s statt 30 s).
- **test_v323** (zwei Versände gleichzeitig unter PostgreSQL): beide warten nach der Vorabprüfung an einer Barriere, dann entscheidet
  der Sperrschlüssel. Unter Last konnte der Gewinner fertig sein (Sperrschlüssel wieder leer), bevor der andere anlegte -- der legte
  dann ungehindert an und sendete ein zweites Mal. Jetzt sendet der Gewinner erst, wenn der andere seinen Konflikt gemeldet hat
  (`FakeSMTP.during_send` wartet auf dieses Ereignis). Zeitgrenzen an Barriere und `join()` nur noch als Sicherheitsnetz, danach
  geprüft, dass kein Versand hängt.
- **test_v419_verbindungen_unter_last**:
  - Langsame Downloads: statt „jede Antwort unter 2 s“ (unter Last 3,5 s bei richtigem Ergebnis) jede mit 200 -- ein gehaltener Pool
    gäbe nach seinem Zeitlimit 503; statt „keine Verbindung seit über 1 s ‚idle in transaction‘“ keine mit einer Transaktion von vor
    dem Start der Prüfrunden (`xact_start` gegen die Uhr der Datenbank) -- ein Download, der seine Verbindung hielte, hätte sie vorher
    begonnen. 15 Prüfrunden statt 6 s mit Pausen; erst geprüft, wenn jeder Download Daten bekommen hat.
  - Viele gleichzeitige Seiten: die Schranke „längste Antwort unter 10 s“ entfällt (Status und Rückfallwerte bleiben).
  - Leerer Pool: die zwei gesperrten Abfragen werden abgewartet, bis `pg_stat_activity` sie zeigt (bis dahin höchstens 15 s, dann
    rot); statt 4,5 s Schlaf und „Pause unter 1,5 s“ werden die beiden Antworten (503 nach dem Zeitlimit des Pools) abgewartet und
    geprüft, dass der Download in dieser Zeit mindestens eine Sekunde seiner Lesemenge bekam (`RATE` Bytes) -- stünde der Prozess
    still, kämen nur die Puffer. „503 in unter 6 s“ entfällt.
  - Beendete Verbindungen: statt einer festen halben Sekunde abwarten, bis `pg_stat_activity` keine Verbindung des Servers mehr zeigt.
- Was bleibt: das Zeitlimit des Pools im Testserver (3 s, der Mechanismus unter Test) und Sicherheitsnetze gegen einen hängenden Lauf
  (`_bis()` mit 120 s, dann rot mit Grund). `test_v419_verbindungen.py` hatte keine Zeitabhängigkeit.

#### Tests und Prüfung

- Die betroffenen Dateien einzeln (ohne Last): 319 Tests grün (test_v323, v375, v376, v378–v386, v419 beide).
- **Beleg unter Last** (Werkzeug `last_parallel.py` im Scratchpad der Runde): je Lauf pytest über den Versandtest von test_v323,
  test_v376 (ganz) und test_v419 (beide Dateien), 36 Tests. Alter Stand (`58074cb`, 1.9.7) und neuer Stand (`ab5ebfb`, 1.9.8) liefen
  **zur selben Zeit** in eigenen Worktrees, je drei Testströme mit sieben Läufen, dazu 14 Prozesse mit Dauerschleife (28 logische
  Kerne). Ergebnis: **neuer Stand 21 von 21 Läufen grün**; alter Stand 16 von 21 Läufen mit Fehlschlag -- 9 × viele Seiten (der Grund
  steht nicht im Protokoll des Laufs; Status und Rückfallwerte prüft der neue Stand unverändert und war grün, also sehr wahrscheinlich
  die Schranke „unter 10 s“), 4 × langsame Downloads, 2 × leerer Pool, 1 × test_v323. Ein Lauf dauerte 214–260 s.
- Gegenlauf nur mit CPU-Last (28 Prozesse, ein Strom, alter Stand, 10 Läufe): 10 von 10 grün, je 6–9 min -- reine CPU-Last löste die
  Fehler nicht aus, erst gleichzeitige Testströme (wie in der parallelen Suite).
- **Gegenproben** (Marker, Dateien byte-genau zurück) -- die zeitfreien Prüfungen erkennen den Fehler weiterhin:
- Auftragszeile nicht gesperrt (`lock_order()` ausgelassen): die vier Gleichzeitigkeitstests von test_v376 rot -- die zweite
    Aktion wartet nicht.
  - Schranke liest auf der Event-Loop (ohne `run_in_threadpool`): leerer Pool und viele Seiten rot (test_v419).
  - Download hält seine Sitzung (`Depends(get_db)` ohne `scope="function"`): langsame Downloads und leerer Pool rot.
  - Versand ohne Sperrschlüssel: test_v323 rot (zweimal gesendet).
  - 4 von 4 rot (FAILED, nicht ERROR).
- **Angepasste Erwartungen** (Regel 28): `_run()`: alt „zweite Aktion ≥ 0,9 s“, neu „zweite Aktion hat nachweislich gewartet“;
  test_v419 langsame Downloads: alt „unter 2 s mit 200“ und „keine seit über 1 s idle in transaction“, neu „200“ und „keine mit
  Transaktion von vor den Prüfrunden“; viele Seiten: alt „unter 10 s“, neu entfällt; leerer Pool: alt „Pause unter 1,5 s“ und „503
  unter 6 s“, neu „mindestens RATE Bytes während des Wartens“ und „503“.

#### Festlegungen 1.9.8 (Bitte bestätigen)

1. **Synchronisation im gemeinsamen `_run()`** statt nur in test_v376 -- dieselbe Ursache trifft test_v378–v386.
2. **„Gewartet“ unter SQLite = erste schreibende Anweisung begonnen** (SQLite zeigt keine wartenden Sperren); unter PostgreSQL der
   Nachweis aus `pg_locks`.
3. **Fortschritt in Bytes statt Pausenlänge** beim leeren Pool (mindestens eine Sekunde der Lesemenge während der drei Sekunden, die
   die Schranke auf den Pool wartet).
4. **Beleg unter Last** = CPU-Last (14 Prozesse mit Dauerschleife, halb so viele wie logische Kerne) und je drei gleichzeitige
   Testströme mit altem und neuem Stand, zur selben Zeit unter derselben Last.

#### Nachtrag 1.9.7: überdeckte Konstante im Klicktest

- Der Endlauf auf `8bb0e86` fand `klicktest_rahmen` rot (Abbruch im Teil „kopfzeile“, `'NoneType' object is not subscriptable`):
  der neue Teil „kopfgruppe“ legte eine Konstante `KOPF` an, die die gleichnamige des Teils „kopfzeile“ überdeckte -- „kopfzeile“
  führte danach das Skript des Seitenkopfs auf der Projektmappe aus. Mein Fehler: geprüft hatte ich nur mit `--nur kopfgruppe` und
  `--nur pruefvorlagen`. Umbenannt in `KOPFGRUPPE_JS` und `KOPFGRUPPE_FOKUS`; der ganze Klicktest 610 von 610.
- Neuer Wächter `tests/test_v444_klicktest_eindeutige_namen.py`: kein Name auf oberster Ebene eines Klicktest-Skripts (dazu
  `cdp_klicktest.py`, `bildgrundlage.py`) zweimal vergeben. Gegenprobe: auf dem Stand mit der Überdeckung meldet er „KOPF (Zeile 451)“.

### Runde 4 abgeschlossen: Endläufe und Bildvergleich (Stand `0df8d8b`)

- **Endlauf** auf `0df8d8b` bei sauberer Arbeitskopie (vorher und nachher keine Änderung): volle Suite **6397 bestanden, 3
  übersprungen, 0 rot** (6:56); **alle Klicktests 80 von 80** (2587 Prüfungen, zu viert, 7:21). Ein erster Endlauf auf `8bb0e86`
  fand `klicktest_rahmen` rot (Nachtrag 1.9.7 oben).
- **Bildvergleich** (volle Bildgrundlage, 298 Bilder) Ausgangsstand `70c3617` gegen `8bb0e86` (der Nachtrag ändert nur Klicktest und
  Wächter): **218 gleich, 76 erlaubt abweichend** (die 15 Seiten der Gruppe und die Liste der Prüfvorlagen), **4 auf der
  Prüfvorlage** als Folge von 1c (nur das Feld „Dachtyp“: jetzt „Flachdach“ vorgewählt statt „— jeder Dachtyp —“), **0 unerwartet**.
  Die erste Grundlage vom Morgen taugte nicht: derselbe Stand `70c3617` zeichnete am Nachmittag die Anmeldeseite in der
  Kantenglättung des Formulars anders (gleiche Chrome-Version 155.0.8059.40) -- verglichen wurde deshalb mit einer Grundlage, die
  unmittelbar vor dem Vergleich vom Ausgangsstand neu aufgenommen wurde. Die Ursache der Abweichung liegt außerhalb des Codes
  (Umgebung), sie ist nicht untersucht.
- **Bilder**: `bildgrundlage/rahmen_runde4_8bb0e86.zip` -- die 15 Seiten 1440 × 900 hell, Start, Projekte und Zeiterfassung auch
  dunkel, je nachher und vorher (`70c3617`); Ordner in `.gitignore`.
- Commits der Runde: `520241c` (Regel 8), `b4aba7f` (1.9.6 Dachtyp), `58074cb` (1.9.7 Seitenkopf), `ab5ebfb` (1.9.8 Wartung),
  `8bb0e86` (1.9.8 Nachtrag: Beleg unter Last, CLAUDE.md), `0df8d8b` (1.9.7 Nachtrag: Klicktest).

## Runde 5: Seitenkopf der Gruppe „Datensatz mit Pfad“

Auftrag (21.10.2026): die 7 Seiten der Gruppe K3 aus `befund-rahmen.md` (Objekt, Dachfläche, Betriebsmittel, Wartungsvertrag,
Checklisten-Vorlage, Prüfvorlage, Einsatzbericht) bekommen den gemeinsamen Seitenkopf mit Pfad, Kennung, Titel, Status, höchstens einer
grünen Hauptaktion und Menü „⋮“; der Pfad schließt die fehlenden Rückwege aus `bildgrundlage/pruefung/ablaeufe.md`; der Status erscheint
als lesbares Kennzeichen in der Farbe seiner Bedeutung, die Zuordnung an einer Stelle; „Löschen“ ins Menü mit Rückfrage wie bisher.

### Punkt 3 (1.9.9): Statuskennzeichen an einer Stelle

- Neuer Baustein `app/templates/_statuskennzeichen.html`, eingebunden über `_seitenkopf.html` (jede Seite mit dem Seitenkopf hat ihn):
  - `statusBedeutungen()`: Bedeutung -> Art des Seitenkopfs -- `laeuft` info, `erledigt` ok (auch bezahlt), `wartet` signal (wartet
    auf dich), `fehler` fehler (überfällig, Fehler), `entwurf` warn, `ruht` neutral (pausiert, storniert, archiviert, inaktiv).
  - `statusTabelle()`: je Gruppe jeder Wert mit Text und Bedeutung -- Auftrag (beauftragt, abgeschlossen, storniert), Wartungsvertrag
    (aktiv, pausiert, beendet, archiviert), Checklisten-Vorlage (entwurf, veroeffentlicht, archiviert), Prüfvorlage und Dachfläche
    (archiviert), Betriebsmittel (pruefung_ueberfaellig, pruefung_faellig, inaktiv).
  - `statusKennzeichen(gruppe, wert)` -> `{text, art}` für `seitenkopf({status: …})`. Unbekannter Wert: lesbar (erster Buchstabe groß,
    `_` als Leerzeichen), neutral -- der Auftragsstatus kommt laut Schema auch frei vom Client. Leer: kein Kennzeichen (ds.css blendet
    das leere aus).
- Die Zuordnung liegt im Browser, weil die Köpfe dieser Seiten sich erst nach dem Laden füllen (Daten per `lesen()`).

#### Tests und Prüfung

- Neu `tests/test_v445_statuskennzeichen.py` (7 Tests): Bedeutungen wie festgelegt und jede Art eine des Seitenkopfs; jeder Eintrag
  mit Text und bekannter Bedeutung; jeder Wert, den der Server schreibt, steht in der Tabelle (`orders.status` aus `FESTE_LITERALE`,
  `app.maintenance_contracts.STATUSES` und archiviert, Fassungen der Checklisten-Vorlage ohne „abgeloest“ und archiviert);
  Kennzeichen in node (Text, Art, unbekannt, leer, HTML bleibt Text); `_seitenkopf.html` bindet den Baustein ein; Scanner über alle
  Vorlagen: jeder Status in `seitenkopf({…})` als `statusKennzeichen('<gruppe>', …)` mit bekannter Gruppe, jeder feste Wert darin ein
  Wert der Gruppe, kein Skript setzt `seitenkopfStatus` an `seitenkopf()` vorbei; Wächter des Scanners an erfundenen Vorlagen.
- **Gegenproben** (Marker `GEGENPROBE`, byte-genau zurück): läuft in ok; „abgeschlossen“ fehlt beim Auftrag; unbekannter Wert ohne
  großen Anfangsbuchstaben; `_seitenkopf.html` ohne den Baustein -- 4 von 4 rot aus dem richtigen Grund.
- Angepasste Erwartungen: keine.

#### Festlegungen 1.9.9 (Bitte bestätigen)

1. **Sechste Bedeutung „ruht“ = neutral** für pausiert, storniert, archiviert und inaktiv (der Auftrag nennt fünf Bedeutungen).
2. **Storniert ruht** (neutral), nicht fehler; **pausiert ruht**, **beendet ist erledigt** (ok).
3. **Ein unbekannter Wert ist kein Fehler**: lesbar und neutral.
4. **Die Zuordnung liegt im Browser** (`_statuskennzeichen.html`), nicht im Server.

### Punkte 1, 2 und 4 (1.9.10): Seitenkopf der Gruppe „Datensatz mit Pfad“ (7 Seiten)

- Die 7 Seiten aus `befund-rahmen.md` (K3) tragen `.ds-seite` und den gemeinsamen Seitenkopf (`teile/seitenkopf.html`,
  `_seitenkopf.html`): Pfad, Kennung, Titel 30 px, Status, Untertitel, höchstens eine grüne Hauptaktion, Weiteres im Menü „⋮“.
  Umgestellt wurde nur, was im Kopf stand; kein Knopf aus dem Inhalt wandert in den Kopf (wie 1.9.7). Kopf-Knöpfe über `data-klick`
  (`_aktionen.html`), ihre IDs bleiben (`archiveBtn`, `performMaintenanceBtn`, `createProjectBtn`, `pauseBtn`, `reactivateBtn`,
  `finishBtn`, `timeLink`, `copyLabel`). Was erst nach dem Laden feststeht, setzt `seitenkopf()` (Text über textContent, Links über
  `sichererLink()`), der Status kommt über `statusKennzeichen()` (1.9.9).
- **Pfad**: Bereich der Seitenleiste, dann die Kette über den Kunden bis zum Datensatz, das letzte Glied ist die Seite selbst
  (`aria-current="page"`). Die Ziele stehen fest im call-Block oder werden aus den geladenen Daten gebaut.
- **Löschen** im Menü in der Fehlerfarbe (`.ds-menue-eintrag-fehler`), die Rückfrage (`confirm`) unverändert in der bisherigen Funktion.
- **Verborgene Einträge**: was nicht gilt (Pausieren/Reaktivieren/Beenden je Status, Vorgang erstellen mit Positionen, Entwurf
  verwerfen, Löschen einer Vorlage mit Zweck), trägt `hidden` statt der Klasse `.hidden` -- `dsMenue()` überspringt es auch per
  Tastatur. Neu in `ds.css`: `.ds-knopf[hidden], .ds-menue-eintrag[hidden] {display: none}` (das `display` der Klassen schlug `[hidden]`).
- **Links in `--ds-link`** (Regeln und `style="…color:var(--accent)…"`, auch `a{…}` des Einsatzberichts und der Knopf „Mängel“ der
  Dachfläche), **Fokus in `--ds-fokus`** auf allen 7 Seiten; die toten Regeln `.breadcrumb`, `.hero`, `.top-links` entfernt.

| Seite | Pfad | Kennung / Status | Hauptaktion | Menü „⋮“ |
|---|---|---|---|---|
| Objekt | Stammdaten / Kunde / Objekt | -- / -- (kein Status) | -- | -- |
| Dachfläche | Stammdaten / Kunde / Objekt / Dachfläche | -- / „Archiviert“ (neutral) | -- | Archivieren bzw. Entarchivieren, Löschen |
| Betriebsmittel | Stammdaten / Betriebsmittel / Name | Inventarnummer / „Prüfung überfällig“ (fehler), „Prüfung fällig“ (signal), „Inaktiv“ (neutral) | -- | Etikett drucken, Löschen |
| Wartungsvertrag | Wartungen / Kunde / Objekt / Vertrag | -- / „Aktiv“ (info), „Pausiert“ (neutral), „Beendet“ (ok), „Archiviert“ (neutral) | „Wartung durchführen“ | Vorgang erstellen, Pausieren bzw. Reaktivieren, Beenden, Archivieren bzw. Entarchivieren, Löschen |
| Checklisten-Vorlage | Checklisten / Vorlagen / Vorlage | -- / „Entwurf“ (warn, nie veröffentlicht), „Veröffentlicht“ (ok), „Archiviert“ (neutral) | „Entwurf veröffentlichen“ bzw. „Neuen Entwurf anlegen“ | Entwurf verwerfen, Kopieren …, Archivieren bzw. Entarchivieren, Löschen (nur Zweck „allgemein“) |
| Prüfvorlage | Einstellungen / Prüfvorlagen / Vorlage | -- (Version im Untertitel) / „Archiviert“ (neutral) | -- | Vorlage kopieren … |
| Einsatzbericht (Büro) | Projekte / Kunde / [Wartungsvertrag] / Projekt / Auftrag / Einsatzbericht | Auftragsnummer / „Beauftragt“ (info), „Abgeschlossen“ (ok), „Storniert“ (neutral) | -- | Zeiterfassung (Auftrag) |
| Einsatzbericht (Monteurin) | Einsätze / Einsatzbericht | Auftragsnummer / -- (der Server liefert ihr keinen Status) | -- | Zeiterfassung (Auftrag) |

**Rückwege** (`bildgrundlage/pruefung/ablaeufe.md`, „Fehlende Wege zurück“): Wartungsvertrag -> Wartungen geschlossen; Einsatzbericht
-> Projektmappe geschlossen, -> Wartungsvertrag geschlossen, sobald ein Bericht des Auftrags aus einem Vertrag entstand
(`ServiceReport.maintenance_contract_id`, Vertrag nachgeladen nur fürs Büro); Einsatzbericht (Monteurin) -> `/mobil` geschlossen (Pfad
„Einsätze“, dazu seit 1.8.164 der Reiter); Prüfvorlage -> Einstellungen geschlossen (von der Vorlage aus); Checklisten-Vorlage ->
Einstellungen bleibt offen (der Pfad folgt dem Bereich Checklisten, Festlegung 4). Erhalten: Objekt/Dachfläche/Wartungsvertrag -> Kunde
und Objekt, Einsatzbericht -> Auftrag und Kundenakte, Vorlagen -> Vorlagenliste.

#### Tests und Prüfung

- `test_v441`: `UMGEZOGEN` um die 7 Seiten (`DATENSATZ_MIT_PFAD`), der Strukturtest `test_umgezogene_seite_hat_den_gemeinsamen_kopf`
  läuft damit für 23 Seiten.
- Neu `tests/test_v446_datensatzkopf.py` (36 Tests): jedes Ziel im Pfad (fest im call-Block oder als Glied `{text, href}` im Skript)
  ist eine Seitenroute und öffnet sich mit 200 als HTML für Büro – Auftrag (`/mobil` für die Monteurin); der Pfad nach dem Laden enthält
  die Rückwege je Seite und den festen Pfad; ein Menüeintrag, der nicht gilt, wird über `hidden` verborgen, nie über die Klasse `.hidden`; „Löschen“ nur im Menü in der Fehlerfarbe und die aufgerufene Funktion fragt zuerst (`confirm`); ds.css hält `[hidden]`.
- `klicktest_rahmen` Teil `datensatzkopf` (neu): je Seite hell und dunkel bei 1440 × 900, der Einsatzbericht auch als Monteurin --
  `.ds-seite`, genau ein h1 mit dem Titel, Kennung, Untertitel, Status (Text, Art, sichtbar), Pfad mit Texten und Zielen, **jeder Link
  im Pfad mit der Anmeldung der Seite geladen: 200 ohne Umleitung, HTML**, Hauptaktion grün, Menü mit genau den geltenden Einträgen
  (verborgene verborgen, „Löschen“ in Fehlerfarbe), Menü per Tastatur (am Vertrag überspringt Pfeil runter den gesperrten „Vorgang
  erstellen“ und das verborgene „Reaktivieren“), Textlinks in `--ds-link`, Fokus in `--ds-fokus`, Kontrast auch mit offenem Menü;
  „Löschen“ fragt wie bisher (abgelehnt, die Seite bleibt), „Kopieren …“ öffnet die Karte mit „<Name> (Kopie)“ und Fokus, Pausieren und
  Reaktivieren wechseln Status und Menü; „Wartung durchführen“ öffnet den Einsatzbericht des neuen Auftrags mit Projekte / Kunde /
  Wartungsvertrag / Projekt / Auftrag / Einsatzbericht, jeder Link öffnet sich. 201 von 201.
- **Gegenproben** (Marker `GEGENPROBE`, byte-genau zurück, je pytest und Klicktest-Teil): Wartungsvertrag ohne Rückweg zu Wartungen; Prüfvorlage mit Pfad-Link ins Leere (`/einstellungen`); Status des Vertrags ohne Kennzeichen (`{text:contract.status}`); „Löschen“ der Dachfläche nicht in der Fehlerfarbe; Menüeintrag über die Klasse `.hidden` statt `[hidden]`; ds.css ohne `[hidden]` für Menüeinträge -- der Klicktest-Teil 6 von 6 rot (197 bis 199 von 201), pytest zuerst nur 4 von 6: der Rückweg-Test sah den festen Link „Wartungen“ im call-Block statt des Pfads nach dem Laden, und die Klasse `.hidden` prüfte nur der Klicktest. **Selbst gefunden und nachgeschärft**: Rückwege nur gegen den Pfad des Skripts (der feste Pfad muss darin enthalten sein), neuer Test `test_menueeintraege_verborgen_ueber_hidden`; danach beide rot, dazu „Einsatzbericht ohne Projektmappe im Pfad“ rot.
- **Angepasste Erwartungen** (Regel 28):
  - `test_v328::test_berichtsseite_baut_auftrags_und_kundenlinks_nur_fuers_buero`: alt `id="orderLink"` nur fürs Büro im Markup; neu
    der Anfang des Pfads -- „Projekte“ fürs Büro, „Einsätze“ (`/mobil`) für den Monteur.
  - `test_v441::UMGEZOGEN`: alt 16 Seiten; neu dazu die 7.
  - `klicktest_monteur_navigation`: alt bereit, wenn `#breadcrumb` Text hat, Prüfung `#breadcrumb a[href^="/orders/"]`; neu bereit, wenn
    `#seitenkopfKennung` Text hat, Prüfung `#seitenkopfPfad a[href^="/orders/"]` (weiter nur fürs Büro).
  - `klicktest_checkliste_zweck`: alt `#versionBadges` enthält „Zweck: Abnahme“ bzw. „Gültig: Fassung 1“, „Löschen“ unter `#heroActions`;
    neu `#seitenkopfUntertitel`, „Löschen“ = `#vorlageLoeschen` nicht verborgen.
  - `klicktest_daten_im_html`: alt `#assetMeta` beginnt mit der Art; neu `#seitenkopfUntertitel`.
  - `test_v259::test_service_reports_html_has_a_general_link_color_rule`: alt `a{color:var(--accent)}` im Stil des Einsatzberichts; neu
    `a{color:var(--ds-link)}`.
- **Attrappe der node-Tests** (`tests/test_v334_auswahl_restfaelle.py::seite()`): `BAUSTEINE` um `_menue.html`, `_statuskennzeichen.html`
  und `_seitenkopf.html` ergänzt, die Element-Attrappe um `replaceChildren`, `document` um `createElement` -- die volle Suite fand
  `test_v443` rot („seitenkopf is not defined“: die Prüfvorlage ruft `seitenkopf()` jetzt beim Füllen des Formulars). Keine Erwartung
  geändert; die 12 Testdateien, die die Attrappe nutzen, grün.

#### Nebenbefund (nur festgehalten, nicht behoben)

- **Betriebsmittel, Feld „Typ“**: `typeOptionsHtml()` (`operational_asset.html`) baut die Optionen ohne `auswahlOptionen()` -- ein
  gespeicherter Typ außerhalb der Auswahlliste „resource_types“ (in den Testdaten der Bildgrundlage „Leiter“) wird nicht vorgewählt, die
  Auswahl zeigt die erste Option („Fahrzeug“), und Speichern überschriebe den Typ still. Dieselbe Fehlerklasse wie der Dachtyp der
  Prüfvorlage (1.9.6, Regel 22). Der Kopf zeigt den gespeicherten Typ im Untertitel richtig.

#### Festlegungen 1.9.10 (Bitte bestätigen)

1. **Pfad = Bereich der Seitenleiste, dann die Kette über den Kunden bis zum Datensatz**, das letzte Glied ist die Seite selbst.
2. **Einsatzbericht (Büro)**: Projekte / Kunde / [Wartungsvertrag] / Projekt / Auftrag / Einsatzbericht -- der Vertrag zwischen Kunde und
   Projekt (das Projekt entstand aus ihm), nur wenn ein Bericht des Auftrags einen Vertrag nennt.
3. **Einsatzbericht (Monteurin)**: Einsätze / Einsatzbericht, ohne Status (der Server liefert ihr keinen, Datengrenze).
4. **Prüfvorlage** beginnt mit Einstellungen (einziger Einstieg), der Bereich der Leiste bleibt Wartungen; **Checklisten-Vorlage** folgt
   dem Bereich (Checklisten / Vorlagen), ihr Rückweg in die Einstellungen bleibt offen.
5. **Status nur, wo der Datensatz einen hat**: Objekt keiner; Dachfläche und Prüfvorlage nur „Archiviert“; Betriebsmittel überfällig vor
   fällig vor inaktiv (sonst kein Status, „Inaktiv“ neben einer Prüfung im Untertitel); Wartungsvertrag archiviert vor dem Vertragsstatus;
   Checklisten-Vorlage archiviert vor veröffentlicht vor Entwurf -- eine veröffentlichte Vorlage mit neuem Entwurf heißt „Veröffentlicht“,
   der Entwurf steht im Untertitel.
6. **Hauptaktion nur, wo der Kopf einen grünen Knopf hatte** (Wartungsvertrag, Checklisten-Vorlage); bei der Checklisten-Vorlage ein Knopf,
   der je nach Stand veröffentlicht oder einen Entwurf anlegt (bis dahin zwei Knöpfe im Wechsel).
7. **Kopieren** (Checklisten-Vorlage, Prüfvorlage): Feld und Knopf aus dem Kopf in eine Karte unter dem Kopf, die „Kopieren …“ im Menü
   öffnet; der Name ist mit „<Name> (Kopie)“ vorausgefüllt (bis dahin leer mit Platzhalter).
8. **Kennung = Nummer des Datensatzes** (Inventarnummer, Auftragsnummer), sonst leer; die Prüfvorlage zeigt ihre Version im Untertitel.
9. **Was nicht gilt, ist verborgen** (`hidden`), auch für die Tastatur; ds.css hält `[hidden]` an Knöpfen und Menüeinträgen durch.
10. **„Löschen“ im Menü in der Fehlerfarbe**, Rückfrage unverändert.
11. **Der Untertitel behält die bisherige Zeile** (der Wartungsvertrag nennt Kunde und Objekt auch dort, obwohl sie im Pfad stehen; der
    Einsatzbericht nennt den Kunden statt „Auftragsnummer · Kunde“, die Nummer steht als Kennung).

### Runde 5 abgeschlossen: Endläufe und Bildvergleich (Stand `440828e`)

- **Endlauf** auf `440828e` bei sauberer Arbeitskopie (vorher und nachher keine Änderung): volle Suite **6453 bestanden, 3
  übersprungen, 0 rot** (7:01). **Klicktests**: der erste Gesamtlauf 78 von 80 -- `klicktest_rahmen` 810 von 811 (Teil
  „seitenleiste“: die Startseite wurde nicht bereit, `GET /api/payments/customer-balances` laut Chrome gesendet, laut
  Verbindungsprotokoll nie beim Server angekommen) und `klicktest_objekt_anderer_kunde` im Zeitlimit von 15 min (Wartungsliste:
  `ds-alte-namen.css` gesendet, nie angekommen); beide Seiten gehören nicht zur Runde. Einzeln wiederholt 21 von 21 und 811 von 811;
  der **zweite Gesamtlauf 80 von 80** (2788 Prüfungen, zu viert, 7:31). Warum unter vier gleichzeitigen Instanzen gelegentlich eine
  Anfrage nicht ankommt, ist nicht untersucht.
- **Bildvergleich** (volle Bildgrundlage, 298 Bilder), Ausgangsstand `8c80435` (Worktree) gegen `440828e`, unmittelbar hintereinander
  aufgenommen: **255 gleich, 42 erlaubt abweichend** (die 7 Seiten in allen Rollen, Breiten, Themen und Zuständen), **1 unerwartet**:
  Büro dunkel 1440 Projekte, ein einzelnes Pixel (212, 245) an der Rundung des aktiven Eintrags der Seitenleiste (RGB 23,29,23 statt
  11,15,17). Gegenprobe: dieselbe Seite einzeln aufgenommen, vom Ausgangsstand und von `440828e` je 23,29,23 -- gleich dem Vorher des
  vollen Laufs; ein Ausreißer der Kantenglättung im vollen Lauf, nicht die Änderung. Außer den 7 Seiten weicht damit nichts ab.
- **Bilder**: `bildgrundlage/rahmen_runde5_440828e.zip` -- die 7 Seiten 1440 × 900 hell, Wartungsvertrag und Einsatzbericht auch
  dunkel, je nachher und vorher (`8c80435`), 18 Bilder; Ordner in `.gitignore`.
- Commits der Runde: `25f09f7` (1.9.9 Statuskennzeichen), `440828e` (1.9.10 Seitenkopf der 7 Seiten).

## Runde 6 (Festlegungen 1.9.9 und 1.9.10 bestätigt)

Auftrag (21.10.2026): 1. Auswahlfelder mit gespeichertem Freitext über `auswahlOptionen()`, Wächter, je Feld ein Test, Abfrage für den
Server; 2. nur Befund: Anfragen, die im Klicktest-Gesamtlauf nie beim Server ankommen; 3. Kennung als Kennzeichen in Mono mit Rahmen
neben dem Status auf allen umgezogenen Seiten; 4. Seitenkopf der Rechnung. Bildvergleich: außer Rechnung, den Köpfen mit Kennung und den
korrigierten Auswahlfeldern weicht nichts ab.

### Punkt 3 (1.9.11): Kennung als Kennzeichen

- Makro `teile/seitenkopf.html`: die Kennung (`#seitenkopfKennung`) ist ein `span` in der Titelzeile zwischen h1 und Status (bis
  1.9.10 ein `div` über dem Titel). `ds.css` `.ds-kopf-kennung`: `inline-flex`, 24 px hoch (wie `.ds-status`), Innenabstand 0 8 px,
  Rahmen 1 px `--ds-linie-stark`, Ecken 6 px, IBM Plex Mono `--ds-groesse-1` (12 px, laut Tokenliste für Kennzeichen) in 500, Schrift
  `--ds-text-2` (Prüfpaar text-2/grund und text-2/flaeche). Ohne Kennung blendet `:empty` sie aus wie bisher; in der Titelzeile zählt
  ein ausgeblendetes Element nicht für den Abstand -- Köpfe ohne Kennung bleiben pixelgleich.
- Betroffen sind die Köpfe mit Kennung: heute der Einsatzbericht (Auftragsnummer, Büro und Monteurin), das Betriebsmittel mit
  Inventarnummer und ab 1.9.13 die Rechnung.

#### Tests und Prüfung

- `test_v441`: neu `test_kennung_ist_ein_kennzeichen_in_mono_mit_rahmen` (Stil in ds.css); `test_makro_gliederung_mit_allen_teilen`
  prüft die Reihenfolge in der Titelzeile (Titel, Kennung, Status).
- `klicktest_rahmen` Teil `datensatzkopf`: je Seite „Kennung als Kennzeichen“ -- Mono, Rahmen `solid` in linie-stark, Schrift text-2,
  auf der Höhe des Titels, rechts davon und links vom Status; ohne Kennung verborgen (217 von 217).
- **Gegenproben** (Marker `GEGENPROBE`, byte-genau zurück): Kennung wieder über dem Titel -- pytest und Klicktest rot; Kennzeichen ohne
  Rahmen -- zuerst nur der Klicktest rot, nach dem neuen Stiltest auch pytest rot.
- **Angepasste Erwartungen** (Regel 28):
  - `test_v441::test_makro_gliederung_mit_allen_teilen`: alt `id="seitenkopfKennung">…</div>` über dem Titel; neu `…</span>` in der
    Titelzeile zwischen Titel und Status.
  - `test_v441::test_makro_ohne_teile_ohne_pfad_aktion_und_menue`: alt `id="seitenkopfKennung"></div>`; neu `…></span>`.

#### Festlegungen 1.9.11 (Bitte bestätigen)

1. **Maße ohne Zeichnung**: die Zeichnung liegt im Projekt nicht vor -- umgesetzt nach dem Wortlaut: Reihenfolge Titel · Kennung · Status,
   24 px hoch wie der Status, Ecken 6 px (der Status ist rund), Rahmen linie-stark, Schrift text-2, Mono 12 px.
2. **Ohne Kennung kein leeres Kennzeichen** (verborgen wie bisher).

### Punkt 1 (1.9.12): Auswahlfelder mit gespeichertem Text

**Bestandsaufnahme** (alle 233 `<select>` in 45 Vorlagen, nur lesend): (A) gespeicherter Text oder Zahl -- 7 echte Fehler, 10 nur
theoretisch (feste Liste im Browser, der Server nimmt jeden Text), alle übrigen in Ordnung (über `auswahlOptionen()`, eigene
Altwert-Behandlung, vom Server erzwungene Liste oder Ja/Nein); (B) Fremdschlüssel -- 5 echte Fehler, 3 nur bei abgeschaltetem Modul
(siehe Befund unten); (C) nur für neue Datensätze, Filter, Ziel einer Aktion. Wichtig für die Bewertung: `GET /api/settings/option-groups/{key}`
liefert auch abgeschaltete Einträge, Einträge lassen sich umbenennen und löschen -- ein gespeicherter Wert außerhalb der Liste ist
realistisch.

**Umgestellt (17 Felder)** -- bis 1.9.11 stand jeweils der erste Eintrag oder nichts gewählt, das nächste Speichern schrieb das:

| Seite, Feld | Spalte | Liste | bis 1.9.11 | seit 1.9.12 |
|---|---|---|---|---|
| Betriebsmittel, Typ | `operational_assets.asset_type` | Optionsgruppe `resource_types` | erster Typ (auch statt leer) | `auswahlOptionen()`, ohne Typ Leer-Option „— kein Typ —“ |
| Betriebsmittel, Prüfungsart | `operational_asset_inspections.inspection_type` | `operational_asset_inspection_types` | leer, Speichern verlangte eine andere; Neuladen beim Bearbeiten setzte auf den ersten Eintrag | `auswahlOptionen()`, Neuladen behält die Auswahl |
| Betriebskosten, Kategorie | `recurring_costs.category` | `recurring_cost_categories` | „— keine —“ (gelöscht) | `auswahlOptionen()` |
| Auftrag, Positionsart | `order_items.position_type` | fest (normal, zulage, bedarf, **alternativ**) | Alternativposition ohne Auswahl, Speichern `''` | `auswahlWert()`, Wert „alternativ“ wie im Angebot |
| Kunde, Art der Zusatzinfo | `customer_extra_infos.info_type` | fest (phone, email, birthday, info) | „Telefon“ wurde phone | `auswahlOptionen()`; „Kunde anlegen“ schreibt die Schlüssel |
| Projektmappe, Status | `projects.status` | fest, **„Angebot“ ergänzt** | „angebot“ ohne Auswahl, Speichern `''` | `auswahlWert()` |
| Checklisten-Vorlage, Regel: Feld | `checklist_template_rules.field_key` | Felder der Fassung | „— Feld wählen —“ | `auswahlOptionen()` |
| Checklisten-Vorlage, Regel: Option | `checklist_template_rules.operand` | Optionen des Felds | erste Option, still geändert | `auswahlOptionen()` |
| Einstellungen, Schichttyp: Auswahlliste | `roof_layer_types.option_group` | Gruppen `layer_*` | leer | `auswahlWert()` |
| Plantafel, Status | `planning_slots.status` | fest | leer | `auswahlWert()` |
| Arbeitsvorbereitung, Status | `work_preparations.status` | fest | leer | `auswahlWert()` |
| Arbeitsvorbereitung, Material: Status | `work_preparation_materials.status` | fest | erster Eintrag | `auswahlOptionen()` (`MATERIAL_STATUS`) |
| Arbeitsvorbereitung, Aufgabe: Status | `work_preparation_tasks.status` | fest | erster Eintrag | `auswahlOptionen()` (`AUFGABE_STATUS`) |
| Arbeitsvorbereitung, Aufgabe: Priorität | `work_preparation_tasks.priority` | fest | erster Eintrag | `auswahlOptionen()` (`AUFGABE_PRIO`) |
| Aufgaben, Priorität | `tasks.priority` | fest | leer | `auswahlWert()` |
| Angebot, Positionsart und Status | `quote_items.position_type`, `quotes.status` | fest | leer | `auswahlWert()` |
| Auftrag, Status | `orders.status` | fest | leer | `auswahlWert()` |

- **`auswahlWert(feld, gespeichert, opt)`** (neu in `_auswahl.html`): für feste Listen im Markup -- liest die Optionen der Vorlage und
  baut sie über `auswahlOptionen()` neu; ein fehlender Wert erscheint als „… (nicht mehr verfügbar)“ und fällt beim nächsten Aufruf
  wieder heraus; ein leerer Wert ohne Leer-Option wählt nichts (wie bisher `feld.value = ''`).
- `_auswahl.html` neu eingebunden in `recurring_costs.html` und `checklist_template.html`.
- **Wächter** `tests/vorlagen_auswahl.py` + `test_v447::test_kein_auswahlfeld_fuer_gespeicherte_werte_ohne_auswahloptionen`: findet
  Optionen von Hand mit bedingtem `selected` (P1) und Wertzuweisungen an ein `<select>` (P2, auch über `setv()`); jede Fundstelle steht
  in `KLASSEN` mit Klasse und Grund -- 105 heute: vom Server erzwungene Listen (`server_fest`, mit der Liste im Grund), Ja/Nein, nur für
  Neues/Filter (`neu`), eigene geprüfte Altwert-Behandlung (`eigen`: Zahlungsbedingung im Auftrag, Einheit im Angebot, zwei schon über
  `auswahlOptionen()` gebaute) und Fremdschlüssel. Eine Liste aus einer Optionsgruppe von Hand ist nur für Neues erlaubt. Grenze: eine
  Zuweisung über eine Variable findet der Scanner nicht.
- **Prüfabfrage für den Server**: `scripts/pruefabfrage_auswahlwerte.sql`, nur lesend (`BEGIN TRANSACTION READ ONLY` … `ROLLBACK`,
  dazu `PGOPTIONS`), über alle 17 Spalten -- je Spalte jeder Wert außerhalb der Liste mit Anzahl und Hinweis (inaktiv, abweichende
  Schreibweise). Befehl auf dem Server, als `tobias`:

      cd /home/tobias/erp
      set -a; source .env; set +a
      PGOPTIONS='-c default_transaction_read_only=on' psql "${DATABASE_URL/postgresql+psycopg:/postgresql:}" -v ON_ERROR_STOP=1 -f scripts/pruefabfrage_auswahlwerte.sql

#### Tests und Prüfung

- Neu `tests/test_v447_auswahl_altwerte.py`: **je Feld ein Test** (Seitenskript in node mit den Optionen aus der Vorlage), 25 Fälle,
  **23 bis 1.9.11 rot** aus dem richtigen Grund (falsche oder keine Auswahl; die zwei grünen sind Vergleichsfälle mit einem Wert aus der
  Liste), dazu der Test für „Kunde anlegen“ (Schlüssel); Wächter (fünf Tests); feste Listen der Prüfabfrage wie auf den Seiten
  (12 Tests); Prüfabfrage nur lesend; Prüfabfrage unter PostgreSQL im Wegwerf-Schema (Regel 27) mit gesäten Altwerten -- genau sie.
- Attrappe der node-Tests (`test_v334`): `_berlin_date.html` in `BAUSTEINE`, Elemente mit `scrollIntoView`, `window.addEventListener`,
  `MutationObserver` -- die Einstellungen, Betriebskosten, Aufgaben, Projektmappe und Plantafel liefen in node bisher nicht.
- **Gegenproben** (Marker `GEGENPROBE`, byte-genau zurück): Typ des Betriebsmittels wieder von Hand -- Feldtests und Wächter rot;
  Auftragsstatus wieder per `.value` -- Feldtest und Wächter rot; `auswahlWert()` ohne Altwert -- neun Feldtests rot; Prüfabfrage nimmt
  „Telefon“ in die Liste -- Listenabgleich und PostgreSQL-Test rot.
- Angepasste Erwartungen: keine.

#### Befund Fremdschlüssel (B, nicht behoben)

- Zeiterfassung (Büro und Monteurin): ein Auftrag, der nicht in der Liste steht (abgeschlossen, außerhalb ±14 Tage, nicht zugeordnet),
  zwingt beim Bearbeiten einer Buchung zum Umbuchen; im Ausweichweg ohne Kontext geht die LV-Position still auf null (`time_tracking.html`
  `orderOptions`/`itemOptions`/`#manualOrder`, `time_tracking_field.html` `orderOptions`, `#manualOrder`, `#crewDialogOrder`).
- Projektmappe, Objekt: ohne gespeichertes Objekt still die Hauptadresse; ein bestätigtes Objekt eines anderen Kunden wird überschrieben.
- Wartungsvertrag, Objekt: die Liste lässt das Objekt mit Hauptadresse weg (`_objekt_anderer_kunde.html`) -- ohne Positionen wird NULL
  gespeichert, mit Positionen scheitert jedes Speichern mit 400.
- Nur bei abgeschaltetem Modul: Betriebsmittel/Kostenposten an Eingangsrechnung und Kostenposten (leere Liste, Speichern schreibt null).

#### Nebenbefunde (nicht behoben)

- `app/routers/time_backoffice.py:89–94`: die Zeitregeln lehnen ein abgeschaltetes Standardmodell auch dann ab, wenn es unverändert
  bleibt -- nach dem Abschalten lassen sie sich nicht mehr speichern (widerspricht Regel 22).
- `time_tracking.html` `editEntry`: sucht die Buchung in der Liste des Auswertungsdatums -- steht dort ein anderes Datum, tut „Ändern“
  bei einer Buchung von heute still nichts.

#### Festlegungen 1.9.12 (Bitte bestätigen)

1. **Umfang = gespeicherter Text oder Zahl** (Abschnitt A, 17 Felder); Fremdschlüssel nur als Befund, eigener Punkt.
2. **Vom Server erzwungene Listen bleiben** (im Wächter `server_fest` mit der Liste im Grund).
3. **Die zweite Quelle mit behoben**: Auftragsdialog „alternativ“ wie das Angebot, „Kunde anlegen“ schreibt phone/email/birthday/info,
   Projektmappe bietet „Angebot“.
4. **Ein Altwert heißt „… (nicht mehr verfügbar)“**, auch „Telefon“ usw. aus dem alten Formular (keine Umdeutung in phone).
5. **Betriebsmittel ohne Typ**: Leer-Option „— kein Typ —“, nur wenn kein Typ gespeichert ist.
6. **Neu angeboten nur aktive Einträge** (Typ, Prüfungsart; bis 1.9.11 auch abgeschaltete ohne Kennzeichen).
7. **Feste Listen im Markup über `auswahlWert()`**, die Zeilen der Arbeitsvorbereitung über Konstanten im Skript.
8. **Wächter mit Klassen und Grund** statt einer Liste, die nur kürzer werden darf: `server_fest`, `ja_nein`, `neu`, `eigen` bleiben,
   `fremdschluessel` bis zum eigenen Punkt.

### Punkt 4 (1.9.13): Seitenkopf der Rechnung

- `invoice_detail.html` trägt `.ds-seite` und den gemeinsamen Seitenkopf (aus der Gruppe K4 „Belegkopf in Karte“ in `befund-rahmen.md`,
  die erste Seite dieser Gruppe). Pfad `Projekte / <Kunde> / <Projektnummer> / <Auftragsnummer> / Rechnung` -- fest im call-Block steht
  „Projekte“, das Skript setzt den ganzen Pfad nach dem Laden (`renderBreadcrumb()` über `seitenkopf({pfad})`); er ersetzt die
  Brotkrume `#breadcrumb` und den Knopf „← Auftrag“. Titel = Art der Rechnung (`TYPE_LABELS`), Kennung = `invoice_number` oder „ohne
  Nummer“, Untertitel = Kunde · Objekt (bis 1.9.12 der Titel „<Nummer oder Entwurf> · <Art>“ mit dieser Unterzeile).
- Status über `statusKennzeichen('rechnung', overview.state oder status, {zusatz, ueberfaellig})`: dieselben Texte wie das bisherige
  Kennzeichen `#statusBadge` -- Zahlbetrag mit Betrag, Guthaben mit Betrag, „Enthalten in Schlussrechnung R-…“, „· in R-… abgezogen“,
  „· überfällig“. `_statuskennzeichen.html`: neue Gruppe „rechnung“ (Entwurf warn; Finalisiert, Offen, Teilweise bezahlt, Einbehalt
  offen, Zahlbetrag offen info; Bezahlt, Ausgeglichen ok; Guthaben signal; Storniert, Enthalten neutral), `statusKennzeichen()` mit
  `opt.zusatz` und `opt.ueberfaellig` (Farbe fehler). Dazu in der Gruppe „auftrag“ Arbeitsvorbereitung, In Ausführung (info) und Pausiert
  (neutral): die Auswahl „Status“ der Auftragsseite bietet sie an, der Server nimmt sie, am Einsatzbericht erschienen sie bis dahin nur
  lesbar gemacht („In ausfuehrung“, neutral).
- Netto/MwSt./Brutto bleiben im Kopf: neuer Teil `kennzahlen` des Makros (`mit_kennzahlen=true`, `.ds-kopf-kennzahlen` zwischen Text und
  Aktionen; je `.ds-kennzahl` mit `.ds-kennzahl-name` in Großbuchstaben 12 px, text-3, und `.ds-kennzahl-wert` 600 mit Ziffern gleicher Breite, gleiche IDs `mNet`,
  `mVat`, `mGross` wie bisher). Rechts daneben „PDF herunterladen“ als neutraler Knopf (`.ds-knopf`, `data-klick="pdf"`, öffnet dieselbe
  Adresse wie bisher). Keine grüne Hauptaktion, kein Menü (siehe Festlegungen).
- Links in `--ds-link` (Zahlungen, Endrechnung), Fokus in `--ds-fokus`; die Grundregeln aus `ds-basis.css` gelten jetzt auch hier (Felder
  und Knöpfe wie auf den übrigen umgezogenen Seiten).
- **Beleg „Beträge, Festschreiben und Versand unverändert“**: Testdaten der Bildgrundlage (Abschlag pauschal 12.000 € netto, Entwurf),
  je im Stand vor der Runde (`97b9dc0`, Worktree) und nach dem Umbau: PDF des Entwurfs holen, Leistungszeitraum eintragen, über den Knopf
  „Rechnung finalisieren“ der Karte „Status“ festschreiben, PDF aus der Ablage holen. Ergebnis: Rechnung R-2026-0001 vom 14.10.2026, netto
  12.000,00, USt 2.280,00, brutto 14.280,00 in beiden Ständen; je PDF der dekodierte Inhaltsstrom byte-gleich (37 bzw. 38 Textstücke
  gleich), verschieden nur Erstellungs- und Änderungszeit in den Metadaten (Uhr des Rechners). Versand: `klicktest_versandverlauf`,
  `klicktest_versandprotokoll` und die Mahn- und Zahlungs-Klicktests im Endlauf.

#### Tests und Prüfung

- `test_v441`: `BELEGKOPF = {"invoice_detail.html"}` in `UMGEZOGEN` (alle Regeln der umgezogenen Seiten); in
  `test_umgezogene_seite_hat_den_gemeinsamen_kopf` neu: im Teil „aktion“ höchstens ein `.ds-knopf` ohne `-aktion`; neu
  `test_makro_kennzahlen_zwischen_text_und_aktionen`.
- `test_v445`: Beispiele mit Zusatz, überfällig, Guthaben, Enthalten, Entwurf, Finalisiert, In Ausführung; Vollständigkeit auch für die
  Auswahl „Status“ der Auftragsseite und jeden Stand einer Rechnung (`invoices.status`, `payments.STATES`, `OVERVIEW_LABELS`, enthalten).
- `test_v446`: Rechnung in `RUECKWEGE` (Projekte, Kunde, Projekt, Auftrag); die Pfad-Tests laufen über `RUECKWEGE`. Der Scanner
  `skript_pfad_ziele()` las ein Ziel als Template-Literal nur bis zum ersten `${…}` (der Tokenizer zerlegt `` `/a/${x}` `` in Stücke) --
  bis 1.9.12 nutzte keine Seite im Pfad ein Template-Literal; neu `test_scanner_liest_template_literale_ganz`.
- `klicktest_rahmen` Teil `rechnungskopf`: Entwurf hell und dunkel (.ds-seite, ein h1, Kennung „ohne Nummer“ als Kennzeichen neben dem
  Status „Entwurf“ warn, Pfad mit Texten und Zielen, jeder Link öffnet eine Seite, einzige Aktion „PDF herunterladen“ neutral, kein Menü,
  Kennzahlen, kein alter Kopf, Links, Fokus, Kontrast; „PDF herunterladen“ öffnet das PDF), dann über die Karte „Status“ festgeschrieben:
  Kennung = Rechnungsnummer, Status „Offen“ info, Beträge gleich -- 24 von 24; Teil gesamt 851 von 851.
- **Gegenproben** (Marker `GEGENPROBE`, byte-genau zurück, je pytest und Klicktest-Teil): G1 Status roh statt `statusKennzeichen()` --
  `test_v445` und Klicktest rot; G2 Pfad ohne Projekt -- `test_v446`, `test_v238` und Klicktest rot; G3 zweite neutrale Nebenaktion --
  `test_v441` und Klicktest rot; G4 „PDF herunterladen“ grün -- nur der Klicktest rot (eine grüne Aktion ist erlaubt, nur nicht für diese
  Nebenaktion); G5 Kennung „Entwurf“ statt „ohne Nummer“ -- nur der Klicktest rot; G6 überfällig ohne Fehlerfarbe -- `test_v445` rot; G7
  Kennzahlen fehlen im Makro -- `test_v441` und Klicktest rot.
- **Angepasste Erwartungen** (Regel 28):
  - `test_v238::test_invoice_detail_has_breadcrumb_with_customer_project_and_order_links`: alt `id="breadcrumb"`; neu `mit_pfad=true` und
    `seitenkopf({pfad:` (die drei Links unverändert geprüft).
  - `klicktest_finanzen_zahlbetrag` (4 Stellen), `klicktest_mahnen_endrechnung` (2), `klicktest_ueberzahlung` (1), `klicktest_zahlungen`
    (1): alt der Text von `#statusBadge`; neu der Text von `#seitenkopfStatus` -- die erwarteten Texte unverändert.
  - `test_v446`: Pfad-Tests über `RUECKWEGE` statt `DATENSATZ_MIT_PFAD` (nur Aufbau, dieselben 7 Seiten plus die Rechnung).
  - `test_v445::test_kennzeichen_lesbar_und_in_der_farbe_der_bedeutung`: sieben Beispiele dazu, die alten unverändert.

#### Festlegungen 1.9.13 (Bitte bestätigen)

1. **Keine grüne Hauptaktion im Kopf der Rechnung**: Festschreiben und Versand bleiben unverändert in der Karte „Status“ (Auftrag:
   „unverändert“; 1.9.7 Nr. 1: kein Knopf wandert aus dem Inhalt in den Kopf).
2. **Kein Menü „⋮“**: es gibt keine weitere Kopfaktion (bis 1.9.12 nur „← Auftrag“, jetzt im Pfad, und „PDF herunterladen“); Storno und
   „Entwurf löschen“ bleiben in der Karte „Status“.
3. **Titel = Art der Rechnung, Kennung = Nummer oder „ohne Nummer“, Untertitel = Kunde · Objekt.**
4. **Pfad wie die bisherige Brotkrume, vorn „Projekte“**: Kunde mit Namen, Projekt mit Projektnummer, Auftrag mit Auftragsnummer, am Ende
   „Rechnung“ ohne Link.
5. **Farben der Rechnungsstände**: Entwurf warn; Finalisiert, Offen, Teilweise bezahlt, Einbehalt offen, Zahlbetrag offen info; Bezahlt,
   Ausgeglichen ok; Guthaben signal (wartet auf eine Erstattung); Storniert, Enthalten neutral; überfällig fehler. Bis 1.9.12 waren
   Guthaben grün und Einbehalt offen gelb.
6. **Texte des Kennzeichens unverändert**; „· überfällig“ steht jetzt immer am Ende (bis 1.9.12 vor „· in R-… abgezogen“ -- beides
   zugleich tritt nur bei einer abgezogenen, bezahlten Rechnung auf, die nicht überfällig ist).
7. **Kennzahlen als Teil des Makros** (`mit_kennzahlen`), für Angebot und Auftrag wiederverwendbar.
8. **Auftragsstände der Auswahl in der Tabelle** (Arbeitsvorbereitung, In Ausführung info, Pausiert neutral); der Wächter prüft auch die
   Auswahl der Auftragsseite.

### Punkt 2 (nur Befund): Anfragen, die im Gesamtlauf nie ankommen

Ausführlich in `docs/archiv/testablauf-und-klicktests.md`, „Befund: Anfragen, die im Klicktest-Gesamtlauf nie beim Server ankommen“.
Kurz: zwei von 269 128 Anfragen in allen aufbewahrten Gesamtläufen, beide im ersten Gesamtlauf von Runde 5; uvicorn nahm die Verbindung
an, las aber nie ein Byte, die App wurde nie aufgerufen -- **Testaufbau, nicht das Programm**; uvicorn allein unter Windows lässt sich mit
denselben Mustern nicht dazu bringen (über 550 000 Anfragen, Proactor und Selector, auch während die Schleife steht). Im Betrieb existiert
der Weg nicht (nginx vor gunicorn unter Linux); käme dort eine Anfrage nie an, endet sie nach 60 s sichtbar (504 von nginx, „unklar“ im
Baustein), nichts geht still verloren. Nichts geändert.

### Runde 6 abgeschlossen: Endläufe, Bildvergleich, Beleg (Stand `f700950`)

- **Endlauf** auf `f700950` bei sauberer Arbeitskopie (vorher und nachher keine Änderung): volle Suite **6505 bestanden, 3 übersprungen,
  0 rot** (7:06); **Klicktests 80 von 80** wie erwartet (zu viert, 7:33).
- **Bildvergleich** (volle Bildgrundlage, 298 Bilder), Ausgangsstand `97b9dc0` (Worktree, Stand vor der Runde) gegen `f700950`,
  unmittelbar hintereinander aufgenommen: **271 gleich, 26 erlaubt abweichend** -- Rechnung (Büro, hell und dunkel, 412 und 1440 px),
  Einsatzbericht (Kennung in der Titelzeile, Seite 21 px kürzer; Büro und Monteurin samt Zuständen „Suche offen“ und „Kontomenü
  offen“), Betriebsmittel (nur das Feld „Typ“: „Leiter (nicht mehr verfügbar)“ statt „Fahrzeug“, 190 × 14 px) --, **1 unerwartet**:
  Büro dunkel 1440 Projekte, dasselbe einzelne Pixel (212, 245) wie in Runde 5 (vorher RGB 11,15,17, nachher 23,29,23). Gegenprobe: die Projektliste
  einzeln aus beiden Ständen aufgenommen, alle vier Bilder pixelgleich (das Pixel je 23,29,23) -- ein Ausreißer der Kantenglättung im
  vollen Lauf, nicht die Änderung. Außer Rechnung, den Köpfen mit Kennung und dem korrigierten Auswahlfeld weicht damit nichts ab. Die
  übrigen 16 korrigierten Auswahlfelder stehen in Dialogen oder auf Seiten ohne Altwert in den Testdaten; sie erscheinen nicht im Bild.
- **Beleg Rechnung**: PDF des Entwurfs und der festgeschriebenen Rechnung aus den Testdaten, vor der Runde (`97b9dc0`) und auf `f700950`:
  Inhaltsstrom byte-gleich, R-2026-0001 vom 14.10.2026, 12.000,00 / 2.280,00 / 14.280,00 € in beiden Ständen.
- **Bilder**: `bildgrundlage/rahmen_runde6_f700950.zip` -- Rechnung als Entwurf und festgeschrieben, hell und dunkel, je vorher und
  nachher, das Betriebsmittel nachher (alle 1440 × 900), dazu die vier PDFs und der Textvergleich (14 Dateien).
- Commits der Runde: `9ef5b62` (1.9.11 Kennung als Kennzeichen), `b14cdc6` (1.9.12 Auswahlfelder), `f700950` (1.9.13 Seitenkopf der
  Rechnung).

## Runde 7 (Festlegungen 1.9.11 bis 1.9.13 bestätigt)

Auftrag (21.10.2026): 1. die Auswahlfelder für Fremdschlüssel (Befund 1.9.12 B): archivierte oder inaktive Ziele vorwählen und behalten,
nie still umstellen, je Feld ein Test, Wächter erweitern; 2. Zeitregeln speichern nach dem Abschalten des Standardmodells; 3. „Ändern“ in
der Zeiterfassung bei abweichendem Auswertungsdatum; 4. Zahlenformat aller Anzeigen über `zahlText()`, Wächter gegen Rohformate; 5.
Seitenkopf des Angebots (LV-Editor); 6. Klicktest einmal automatisch wiederholen, nur wenn die einzige Abweichung „Anfrage nicht
angekommen“ ist. Bildvergleich: außer Angebot und den korrigierten Feldern weicht nichts ab. Server-Abfrage der Auswahlwerte (1.9.12):
ein Altwert („Geburtstag“), vom Betreiber korrigiert, jetzt 0.

### Punkt 2 (1.9.14): Zeitregeln mit abgeschaltetem Standardmodell

- `app/time_backoffice.py::update_time_settings()`: „aktiv“ nur prüfen, wenn `default_work_time_model_id` vom gespeicherten abweicht
  (bis 1.9.13 bei jedem Speichern -- nach dem Abschalten des Standardmodells scheiterte jedes Speichern der Zeitregeln mit 422).
- Tests: neu `tests/test_v448_zeitregeln_standardmodell.py` -- Speichern mit abgeschaltetem Standardmodell (Rundung geändert, Modell
  bleibt; bis 1.9.13 rot mit 422), neu gewähltes abgeschaltetes und unbekanntes Modell 422 ohne Änderung, Oberfläche baut die Auswahl über
  `auswahlOptionen()` und schickt ihren Wert. Angepasste Erwartungen: keine.

### Punkt 3 (1.9.15): „Ändern“ in der Zeiterfassung bei anderem Auswertungsdatum

- `time_tracking.html::editEntry()` sucht die Buchung in `todayEntries` (Liste „Heutige Buchungen“, dort steht der Knopf) und in `entries`
  (Auswertung); bis 1.9.14 nur in `entries` -- zeigte die Auswertung einen anderen Tag, öffnete „Ändern“ an einer Buchung von heute nichts.
  Steht die Buchung in keiner Liste, erscheint unter „Heutige Buchungen“ (`#todayMsg`, role="status") „Diese Buchung steht nicht mehr in
  der Liste (gelöscht oder verschoben) – bitte die Seite neu laden.“
- **Entscheidung: ändern statt ablehnen.** Die Buchung ist geladen und gehört zur Liste, an der der Knopf sitzt; das Bearbeiten selbst
  prüft der Server wie bisher (Abschluss, eigene Buchung, Teil-Update). Ein „geht nicht“ hätte nur die Lücke der Seite benannt.
- Monteursseite (`time_tracking_field.html`): nicht betroffen, `editEntry()` sucht dort in `allEntries`, der Liste mit den Knöpfen.
- Tests: neu `tests/test_v449_zeiterfassung_aendern.py` -- Seitenskript in node (`openManual` aufgezeichnet): Auswertung gestern, „Ändern“
  an der Buchung von heute öffnet sie (bis 1.9.14 rot: nichts geöffnet); gleiches Datum (Vergleichsfall, auch vorher grün); Buchung in
  keiner Liste -> Meldung; Meldungsfeld im Markup. Angepasste Erwartungen: keine.

### Punkt 1 (1.9.16): Auswahlfelder für Fremdschlüssel

**Bestandsaufnahme** (alle 32 Fundstellen mit Klasse „fremdschluessel“ aus 1.9.12, nur lesend): 6 echte Fehler (die „fünf“ aus Befund B --
Büro-Zeiterfassung mit Auftrag und LV-Position, Monteurs-Zeiterfassung, Projektmappe, Wartungsvertrag), 2 nur falsch angezeigt
(Ersteller des Einsatzberichts, Standardvorlage je Dachtyp), 3 nur bei abgeschaltetem Modul (Eingangsrechnung: Betriebsmittel und
Kostenposten; Kostenposten: Betriebsmittel), dazu ein Randfall der Anfrage (Objekt nachträglich einem anderen Kunden zugeordnet); die
übrigen zeigen nie einen gespeicherten Wert oder ihre Liste enthält jede speicherbare ID.

**Umgestellt (11 Felder, alle über `auswahlOptionen()`):**

| Seite, Feld | bis 1.9.15 | seit 1.9.16 |
|---|---|---|
| Büro-Zeiterfassung, Auftrag (Bearbeiten) | Auftrag abgeschlossen, storniert oder nicht zugeordnet: Auswahl leer, Speichern 422 „Auftrag wurde nicht gefunden“ bzw. Umbuchen | nachgeladen (`bearbeitungsAuftrag()`, `GET /api/orders/{id}`), gewählt „… (abgeschlossen)“/„(storniert)“/„(nicht in der Auswahl)“ |
| Büro-Zeiterfassung, LV-Position | im Ausweichweg ohne Kontext (`items: null`) nur „— keine —“, Speichern null | Positionen nachgeladen; fehlt die Position, bleibt sie mit Namen aus der Buchung |
| Monteurs-Zeiterfassung, Auftrag (Einzel und Kolonne) | außerhalb der Auswahl (±14 Tage, abgeschlossen): „— Auftrag wählen —“, Umbuchen erzwungen | bleibt „AUF-… · Projekt (nicht mehr in der Auswahl)“; neue Buchungen schlagen nur Aufträge der Auswahl vor |
| Projektmappe, Objekt | Öffnen setzte bei „kein Objekt“ und einem fremden Objekt still die Hauptadresse | bleibt; fremdes „… (Objekt eines anderen Kunden)“; Hauptadresse nur beim Kundenwechsel |
| Wartungsvertrag, Objekt | Objekt mit Hauptadresse fehlte (`_objekt_anderer_kunde.html`) | bleibt in der Liste, wenn gespeichert |
| Anfrage, Objekt | nachträglich einem anderen Kunden zugeordnet: still „Kein Objekt“ | bleibt „… (gehört nicht mehr zum Kunden)“; der Server lehnt beim Speichern ab (sichtbar) |
| Einsatzbericht, Ersteller | inaktiv: „— nicht zugeordnet —“ (nur Anzeige) | „(inaktiv)“, neu nur aktive |
| Prüfvorlagen, Standardvorlage je Dachtyp | archiviert: „— keine —“ (nur Anzeige) | „(archiviert)“, neu nur aktive |
| Eingangsrechnung, Betriebsmittel / Kostenposten | Modul aus: Liste leer, Speichern null; inaktive ohne Kennzeichen wählbar | Name aus der Rechnung „… (nicht in der Auswahl)“; „(inaktiv)“, neu nur aktive |
| Kostenposten, Betriebsmittel | Modul aus: Liste leer, Speichern null | Name aus `asset_name` (neu in `cost_to_dict()`/`RecurringCostOut`) |

- **Server**: keine Prüfung geändert. Den unveränderten abgeschlossenen Auftrag einer Buchung nimmt der Server fürs Büro an
  (`update_entry()` prüft nur die Existenz), für die Monteurin solange der Auftrag ihr zugeordnet ist (`require_field_order_access()`, ohne
  Zeitfenster); ein Objekt eines anderen Kunden am Projekt unverändert ebenso. Neu nur `asset_name` am Kostenposten.
- **Wächter** (`test_v447`, `tests/vorlagen_auswahl.py`): die Freiklasse `fremdschluessel` ist weg; die verbleibenden Fremdschlüssel sind
  `vollstaendig` (10, Grund mit Quelle: alle Kunden, alle Abschnitte des Angebots, nachgeladener Auftrag im Backoffice …), `neu` (9) oder
  `eigen` (2: Objekt-Baustein, Mitarbeiterfunktion). Neue Fundart **P3**: `auswahlOptionen()`/`auswahlEintraege()` über eine vorher mit
  `.filter(` gefilterte Liste -- sie wirft einen gespeicherten inaktiven Eintrag hinaus, bevor die Altwert-Behandlung ihn sieht (den
  Filter macht `opt.aktiv`); heute keine Fundstelle. Grenze: ein Filter in einer Hilfsfunktion, die die Liste liefert, bleibt unsichtbar.

#### Tests und Prüfung

- Neu `tests/test_v450_auswahl_fremdschluessel.py`: je Feld ein Test (Seitenskript in node, Antworten des Servers aus der Attrappe), dazu
  Speichern in der Büro-Zeiterfassung (PUT behält Auftrag und Position) und der Server-Test für `asset_name`; **19 von 22 im Stand des
  Rundenstarts rot** aus dem richtigen Grund (falsche oder leere Auswahl, PUT mit `order_id` 0 und ohne Position, `asset_name` fehlt), die
  drei grünen sind Vergleichsfälle (neue Buchung Büro und Monteurin, Kundenwechsel in der Projektmappe).
- `test_v447`: neu `test_waechter_findet_vorher_gefilterte_liste` (P3 an erfundenen Stücken).
- Attrappe der node-Tests (`test_v334`): `_objekt_anderer_kunde.html` und `_time_entries_list.html` in `BAUSTEINE`.
- **Gegenproben** (Marker `GEGENPROBE`, byte-genau zurück): Auftrag der Buchung nicht nachgeladen -- vier Büro-Tests rot; Monteurin ohne
  Altwert -- beide Monteur-Tests rot; Ersteller über `employees.filter(e=>e.active)` -- Feldtest und Wächter (P3) rot; Hauptadresse im
  Wartungsvertrag wieder ausgeschlossen -- rot; Projektmappe beim Öffnen wieder Hauptadresse -- beide rot.
- **Angepasste Erwartungen** (Regel 28): `test_v447::KLASSEN` -- alt 32 Einträge mit Klasse `fremdschluessel`; neu 11 entfallen (umgebaut),
  10 `vollstaendig`, 9 `neu`, 2 `eigen` (die Erwartung des Wächters selbst ist strenger, nicht schwächer).

#### Festlegungen 1.9.16 (Bitte bestätigen)

1. **Umfang**: die fünf aus Befund B, dazu die zwei Anzeigefehler, die drei Felder bei abgeschaltetem Modul und der Randfall der Anfrage --
   „nie still umstellen“ gilt für alle.
2. **Kennzeichen** nach dem Grund: „(abgeschlossen)“/„(storniert)“ (Stand des Auftrags), „(inaktiv)“, „(archiviert)“, „(nicht mehr in der
   Auswahl)“ (Monteurin, Auftrag außerhalb ±14 Tage), „(nicht in der Auswahl)“ (Büro, Auftrag nicht zugeordnet; Modul abgeschaltet),
   „(Objekt eines anderen Kunden)“, „(gehört nicht mehr zum Kunden)“.
3. **Neue Buchungen** schlagen nur Ziele der Auswahl vor (ein Auftrag aus der Adresse außerhalb der Auswahl wird nicht vorgewählt).
4. **Inaktive und archivierte Ziele werden nicht mehr neu angeboten** (Eingangsrechnung: Betriebsmittel und Kostenposten; Einsatzbericht;
   Standardvorlage) -- wie Festlegung 1.9.12 Nr. 6.
5. **Projektmappe**: die Hauptadresse ist nur beim Kundenwechsel Vorschlag; beim Öffnen bleibt auch „kein Objekt“.
6. **Anfrage**: ein Objekt, das nicht mehr zum Kunden gehört, bleibt gewählt; der Server lehnt das Speichern ab, bis ein anderes gewählt
   ist (statt still „Kein Objekt“).
7. **Wächter**: Klassen `vollstaendig`/`neu`/`eigen` statt der Freiklasse; neue Fundart P3.

### Punkt 4 (1.9.17): Zahlen in der Anzeige über zahlText()

**Befund** (alle Vorlagen, nur lesend): von Hand formatiert -- Komma per `replace` an 9 Stellen, `toFixed` in der Anzeige an 4, ein
Dezimalfeld roh an 2; `toFixed` im Maschinenformat an 14 Stellen (Körper von Zahlung und Erstattung, Adresse des Zahlungsvorschlags, Werte
der Auswahl Steuersatz „19.00“, Mahngebühr); lokale Formatierer mit `toLocaleString('de-DE')` (`qty()`, `num()`, `signed()`, `money()`)
formatieren schon deutsch.

| Seite, Anzeige | bis 1.9.16 | seit 1.9.17 |
|---|---|---|
| Rechnung, Auftrag, Angebot: Auswahl Steuerschlüssel (`steuerschluesselOptionen()`, `_auswahl.html`) | „Regelsteuersatz (19,0000 %)“ | „Regelsteuersatz (19 %)“, „Sonder (10,7 %)“ |
| Rechnung: Zahlungsbedingung mit Skonto | „2,50 % Skonto“ (Komma von Hand) | „2,5 % Skonto“ |
| Rechnung, Mahnwesen: Verzugszinsen „… Prozentpunkte über dem Basiszinssatz“ | „9,00“ | „9“ |
| Rechnung: Zeilen des Zahlungsdialogs (`fmt()`, füllt Eingabefelder) | `toFixed(2)` + Komma | `zahlText(x, 2)` (gleicher Text, Regel 34) |
| Einstellungen: Steuerschlüssel, Zahlungsbedingungen, Konten | „19,0000 %“, „2,50 % bei“, „19,00 %“ | „19 %“, „2,5 % bei“, „19 %“ |
| Kundenakte, Projektmappe: Dateigröße | „1.5 KB“ (Punkt) | „1,5 KB“ |
| Auftrag, Versandprotokoll: Dateigröße | „1,5 MB“ (Komma von Hand) | „1,5 MB“ über `zahlText()` |
| Leistungsformular: Menge eines Materials | „2.500“ roh | „2,5“ |
| Plantafel, Ressourcen: Belegung | `${c.planned_hours}× belegt` (ganze Zahl) | über `zahlText()` (gleicher Text) |

- `_zahl.html` neu eingebunden in `email_dispatches.html` (Dateigröße) und -- weil `_auswahl.html` jetzt `zahlText()` aufruft -- in
  `calendar.html`, `inquiries.html`, `inspection_templates.html`, `tasks.html` (Wächter `test_v414::test_jede_seite_mit_zahlenfeld_bindet_
  den_baustein_ein` über `vorlagen_zahlen.ohne_einbindung()`); `_zahl.html` bringt nur CSS für abgelehnte Zahlenfelder mit, keine sichtbare
  Änderung.

#### Tests und Prüfung

- Neu `tests/test_v451_zahlformat_anzeige.py`: Wächter (kein Komma von Hand; `toFixed` je Vorlage gezählt in `MASCHINENFORMAT` mit Grund;
  kein Satz/Menge/Stunden roh im HTML; wer `zahlText()` oder `steuerschluesselOptionen()` nutzt, bindet `_zahl.html` ein; Gegenprobe der
  Muster an erfundenen Stücken) und die Anzeigen in node (Steuerschlüssel in Rechnung, Auftrag, Angebot; Skonto und Zinsaufschlag der
  Rechnung; Steuerschlüssel, Skonto, Konten der Einstellungen; Dateigrößen in Kundenakte, Projektmappe, Auftrag, Versandprotokoll; Menge im
  Leistungsformular). **11 von 15 vor dem Umbau rot**; grün waren die zwei Strukturtests und zwei Vergleichsfälle (Dateigröße in Auftrag und
  Versandprotokoll war mit Komma von Hand schon deutsch).
- **Gegenproben** (Marker `GEGENPROBE`, byte-genau zurück): Steuerschlüssel wieder mit Komma von Hand -- Wächter und drei Anzeigetests rot;
  Menge wieder roh -- Wächter und Anzeigetest rot; Dateigröße wieder per `toFixed` -- Zählung und Anzeigetest rot.
- **Angepasste Erwartungen** (Regel 28): `test_v334::test_archivierter_steuerschluessel_bleibt_sichtbar_und_vorgewaehlt` -- alt: Text beginnt
  mit „Alt 16 (16,“ und endet mit „ %) (inaktiv)“ (hielt das Rohformat „16,0000 %“ fest); neu genau „Alt 16 (16 %) (inaktiv)“.

#### Festlegungen 1.9.17 (Bitte bestätigen)

1. **Anzeige = `zahlText()` ohne feste Stellen** (so viele wie nötig: „19 %“, „10,7 %“), Dateigrößen mit einer Stelle, Felder, die ein
   Eingabefeld füllen, mit zwei (wie bisher).
2. **Lokale Formatierer mit `toLocaleString('de-DE')` bleiben** (`qty()`, `num()`, `signed()`, `money()`) -- kein Rohformat.
3. **`toFixed` bleibt fürs Maschinenformat** (Körper, Adresse, Wert einer Auswahl) und wird je Vorlage gezählt; jede neue Stelle muss dort
   eingeordnet werden.
4. **Wer `_auswahl.html` einbindet, bindet `_zahl.html` ein** (vier Seiten neu), statt `_auswahl.html` eine eigene Formatierung zu geben.

### Punkt 5 (1.9.18): Seitenkopf des Angebots (LV-Editor)

- `quote_editor.html` trägt `.ds-seite` und den gemeinsamen Seitenkopf (Gruppe K4 „Belegkopf in Karte“, nach der Rechnung die zweite
  Seite). Pfad `Projekte / <Kunde> / <Projektnummer> / Angebot` (ersetzt die Brotkrume `#breadcrumb` „Kunde · Projekt · Nummer“), Titel =
  Bezeichnung (`quote.title`), Kennung = Angebotsnummer, Untertitel wie bisher „Kunde · Projekt · Objekt“ (bis 1.9.17 Titel „Nummer ·
  Bezeichnung“ mit dieser Unterzeile).
- Status über `statusKennzeichen('angebot', quote.status)`; neue Gruppe „angebot“: Entwurf warn, Versendet und In Prüfung info (läuft beim
  Kunden), Beauftragt ok, Abgelehnt neutral -- bis 1.9.17 stand der rohe Wert im Kennzeichen („beauftragt“, „in_pruefung“).
- Kennzahlen Netto, Optional, MwSt., Brutto (gleiche IDs `sumNet`, `sumOptional`, `sumVat`, `sumGross`, gleiche Beträge über `money()`).
- Aktionen: grüne Hauptaktion = der bisherige grüne Knopf `#orderButton` (Text und Ziel wie bisher je nach Auftrag: „Angebot beauftragen“
  -> Dialog, „Auftrag … öffnen“, „Änderungen in … übernehmen“); daneben „PDF-Vorschau“ neutral (`data-klick="pdf-vorschau"`, öffnet
  dieselbe Adresse). Menü „⋮“: „Angebotsdetails“ (Reiter), „OZ neu nummerieren“ und `#orderOpenLink` „Auftrag … öffnen“ -- verborgen über
  das Attribut `hidden` (bis 1.9.17 Klasse `.hidden`), sichtbar nur, wenn der Hauptknopf die Änderungen übernimmt (ein Weg zum Auftrag,
  1.8.136).
- **Variante `breit`** des Makros (`seitenkopf(…, breit=true)`, Klasse `ds-kopf-breit`, ds.css `.ds-kopf-breit .ds-kopf-text {flex-basis:
  100%}`): mit vier Kennzahlen, zwei Knöpfen und Menü blieben dem Titel in einer Zeile gut 300 px -- „Dachsanierung Halle Nord“ brach um,
  Kennung und Status rutschten unter den Titel. Breit steht die Titelzeile allein oben, Kennzahlen links und Aktionen rechts darunter.
  Nur das Angebot nutzt sie; die Rechnung passt in eine Zeile und bleibt.
- Fokus in `--ds-fokus` (zwei Regeln), Kopf-CSS der Brotkrume und der Werkzeugleiste entfernt; die Grundregeln aus `ds-basis.css` gelten
  jetzt auch hier (Felder und Knöpfe wie auf den übrigen umgezogenen Seiten).
- **Beleg „Beträge, LV und Versand unverändert“**: Testdaten der Bildgrundlage (A-2026-0001, beauftragt, zwei Positionen), Stand vor der
  Runde (`bee5363`, Worktree) und nach dem Umbau: Netto 45.945,00, Optional 0,00, USt 8.729,55, Brutto 54.674,55 in beiden Ständen; der
  dekodierte Inhaltsstrom des Angebots-PDFs byte-gleich (43 Textstücke). Versand: `klicktest_versandprotokoll` und
  `klicktest_versand_im_kontext` wie erwartet.
- **Nebenbefund (nicht behoben)**: das Angebotsdatum der Testdaten ist der Tag des Laufs (das Angebot hat kein Datum in der Kopfzeile,
  `_default_quote_meta()` nimmt `created_at`, und die Bildgrundlage setzt `created_at` des Angebots nicht auf die stehende Uhr) -- das PDF
  zeigt „Datum 21.10.2026“, obwohl die Uhr der Instanz auf 14.10.2026 steht. Der Vergleich vorher/nachher lief am selben Tag; zwischen
  zwei Tagen weicht der Text an dieser Stelle ab.

#### Tests und Prüfung

- `test_v441`: `quote_editor.html` in `BELEGKOPF` (alle Regeln der umgezogenen Seiten); neu `test_makro_variante_breit`.
- `test_v445`: Vollständigkeit auch für die Auswahl „Status“ des LV-Editors und `quotes.status`.
- `test_v446`: Angebot in `RUECKWEGE` (Projekte, Kunde, Projekt; jeder Link öffnet eine Seite).
- `klicktest_rahmen` Teil `angebotskopf`: hell und dunkel -- .ds-seite, h1 = Bezeichnung, Kennung, Untertitel, Status „Beauftragt“ ok,
  Kennzeichen neben dem Titel, Pfad mit Texten und Zielen (jeder Link öffnet eine Seite), „PDF-Vorschau“ neutral und Hauptaktion grün,
  Menü mit zwei Einträgen (Link zum Auftrag verborgen) per Tastatur, Kennzahlen, kein alter Kopf, Links, Fokus, Kontrast; hell zusätzlich
  „PDF-Vorschau“ öffnet das PDF, „Angebotsdetails“ den Reiter, die Hauptaktion den Auftrag -- 25 von 25; Teil gesamt 876 von 876.
- **Gegenproben** (Marker `GEGENPROBE`, byte-genau zurück): Status roh -- `test_v445` und Klicktest rot; Link zum Auftrag beim Übernehmen
  über die Klasse statt das Attribut -- `test_v436` rot (der erste Versuch störte nur Zweige, in denen der Link ohnehin verborgen bleibt,
  und blieb grün -- benannt, wiederholt); ohne `breit` -- Klicktest rot (Kennung unter dem Titel); „PDF-Vorschau“ grün -- `test_v441` und
  Klicktest rot; Pfad ohne Kunde -- `test_v446`, `test_v238` und Klicktest rot.
- **Angepasste Erwartungen** (Regel 28):
  - `test_v238::test_quote_editor_has_breadcrumb_with_customer_and_project_links`: alt `id="breadcrumb"`; neu `mit_pfad=true` und
    `seitenkopf({pfad:` (die zwei Links unverändert geprüft).
  - `test_v436::test_lv_editor_ein_weg_zum_auftrag`: alt Sichtbarkeit des Links über die Klasse `hidden` (Attrappe mit `classList`); neu
    über das Attribut `hidden` -- Soll der vier Zustände unverändert.
  - `test_v446`, `test_v441`, `test_v445`: nur Einträge ergänzt (Angebot), keine bestehende Erwartung geändert.

#### Festlegungen 1.9.18 (Bitte bestätigen)

1. **Hauptaktion = der bisherige grüne Knopf** mit seinem Verhalten je Auftrag (Beauftragen, Auftrag öffnen, Änderungen übernehmen).
2. **Nebenaktion „PDF-Vorschau“**; im Menü „Angebotsdetails“, „OZ neu nummerieren“ und „Auftrag … öffnen“ (nur beim Übernehmen).
3. **Titel = Bezeichnung, Kennung = Angebotsnummer, Untertitel = Kunde · Projekt · Objekt.**
4. **Pfad wie die Brotkrume, vorn „Projekte“, am Ende „Angebot“** ohne Link.
5. **Farben der Angebotsstände**: Entwurf warn, Versendet und In Prüfung info, Beauftragt ok, Abgelehnt neutral.
6. **Variante `breit` des Seitenkopfs** (Kennzahlen und Aktionen unter der Titelzeile), heute nur am Angebot.

### Punkt 6 (1.9.19): Klicktest einmal wiederholen, wenn nur eine Anfrage nicht ankam

Ausführlich in `docs/archiv/testablauf-und-klicktests.md`, „Wiederholung bei „Anfrage nicht angekommen““ (Erkennung, Ablauf, Ausweisen, fünf
Festlegungen zum Testablauf). Test `tests/test_v452_klicktest_wiederholung.py`. Angepasste Erwartungen: keine (die Zeilen von `ausfuehren()`
haben ein fünftes Feld; `test_v413` prüft nur die ersten drei).

### Runde 7 abgeschlossen: Endläufe, Bildvergleich, Beleg (Stand `babfaca`)

- **Endlauf** auf `babfaca` bei sauberer Arbeitskopie (vorher und nachher keine Änderung): volle Suite **6567 bestanden, 3 übersprungen,
  0 rot** (7:10); **Klicktests 80 von 80** wie erwartet (zu viert, 7:33), **keine Wiederholung** nötig (Punkt 6 griff nicht).
- **Bildvergleich** (volle Bildgrundlage, 298 Bilder), Ausgangsstand `bee5363` (Worktree, Stand vor der Runde) gegen `babfaca`, unmittelbar
  hintereinander aufgenommen: **286 gleich, 12 abweichend** -- 4 Angebot (Büro, hell und dunkel, 412 und 1440 px: neuer Kopf, Grundregeln
  der umgezogenen Seite) und 8 Auftrag und Rechnung (je hell/dunkel, 412/1440): je ein Rechteck von 55–62 × 14 px, die Auswahl
  Steuerschlüssel „Privat (19,0000 %)“ -> „Privat (19 %)“ (Punkt 4, korrigiertes Feld; Ausschnitt geprüft). Die übrigen korrigierten
  Auswahlfelder (Punkt 1) stehen in Dialogen oder zeigen in den Testdaten keinen Altwert, die übrigen Zahlenanzeigen (Punkt 4) erscheinen in
  den Testdaten nicht (keine Dokumente mit Dateigröße, kein Material im Leistungsformular, Einstellungen mit unveränderten Texten der
  sichtbaren Bereiche); die vier Seiten, die `_zahl.html` neu einbinden, sind pixelgleich. Außer Angebot und den korrigierten Feldern weicht
  damit nichts ab.
- **Beleg Angebot**: PDF aus den Testdaten, vor der Runde (`bee5363`) und auf `babfaca`, am selben Tag: Inhaltsstrom byte-gleich (43
  Textstücke), A-2026-0001, 45.945,00 / 0,00 / 8.729,55 / 54.674,55 € in beiden Ständen.
- **Bilder**: `bildgrundlage/rahmen_runde7_babfaca.zip` -- Angebot 1440 × 900 hell und dunkel, je vorher und nachher, dazu die zwei
  Angebots-PDFs und der Textvergleich (7 Dateien).
- Commits der Runde: `747f084` (1.9.14 Zeitregeln), `681ccb0` (1.9.15 Ändern in der Zeiterfassung), `c27c9f3` (1.9.16 Fremdschlüssel),
  `e2874a3` (1.9.17 Zahlen über zahlText()), `0f3e86c` (1.9.18 Seitenkopf des Angebots), `babfaca` (1.9.19 Wiederholung im Klicktest).

## Runde 8 (Festlegungen 1.9.14 bis 1.9.19 bestätigt)

Auftrag (21.10.2026): 1. das Angebotsdatum der Testdaten läuft auf der stehenden Uhr der Bildgrundlage, dazu prüfen, ob weitere Testdaten
am Lauftag hängen; 2. Seitenkopf der Gruppen „Untermenü links“ und „Zurück-Link + Karte“ (Makro, `.ds-seite`, Links in `--ds-link`, Fokus
in `--ds-fokus`, der Zurück-Link wird zum Pfad; grüne Hauptaktion nur, wo der Kopf eine hatte; Löschen ins Menü); 3. Stammdaten-Formular
und Leistung bekommen den Rahmen (Leiste, Kopfzeile, Seitenkopf mit Pfad; „Abbrechen“ neutral zum bisherigen Zurück-Ziel, „Speichern“ grün,
der Knopf unten bleibt; Bereich Stammdaten; Felder und Speichern unverändert). Neues Projekt und Neues Angebot bleiben (Stufe 7: Dialoge).
Bildvergleich: außer diesen Seiten weicht nichts ab.

### Punkt 1 (1.9.20): Testdaten hängen nicht am Lauftag

Ausführlich in `docs/archiv/testablauf-und-klicktests.md`, „Testdaten der Bildgrundlage hängen nicht am Lauftag“. Test
`tests/test_v453_bildgrundlage_lauftag.py`. Angepasste Erwartungen: keine.

### Punkt 2 (1.9.21): Seitenkopf der Gruppen „Untermenü links“ und „Zurück-Link + Karte“ (8 Seiten)

- Die 8 Seiten aus `befund-rahmen.md` (K5, K6) tragen `.ds-seite` und den gemeinsamen Seitenkopf (`teile/seitenkopf.html`,
  `_seitenkopf.html`). Umgestellt wurde, was im Kopf stand: Titel, Untertitel, „← Ziel“; kein Knopf aus dem Inhalt wandert in den Kopf,
  Filter und Werkzeugleisten bleiben in ihren Karten (Suche der Stammdaten, Zeitraum und „Aktualisieren“ des Backoffice, Filter der
  Änderungshistorie).
- **Untermenü links** (Stammdaten, Einstellungen, Backoffice): der Kopf steht über Menü und Inhalt, an derselben Stelle wie auf jeder
  anderen Seite; ohne Pfad (Einstiegsseiten ihres Bereichs der Leiste, das Menü bleibt die Navigation). Stammdaten: Titel und Untertitel des
  gewählten Bereichs im Kopf (bis dahin das h1 der Karte, `render()` setzt sie wie bisher, jetzt in `#seitenkopfTitel` und
  `#seitenkopfUntertitel`), „+ Hinzufügen“ als Hauptaktion (Ziel je Bereich wie bisher, verborgen über `hidden` statt `style.display` -- das
  hätte das `display` von `.ds-knopf` überschrieben). Einstellungen: Titel „Einstellungen“ (bis dahin ohne Seitentitel), das Menü ohne
  eigene Überschrift, jeder Bereich behält seine Überschrift in der Karte. Backoffice: Titel und Untertitel aus der ersten Karte in den Kopf,
  der Kopf vor `<main>` (ein Ladefehler ersetzt nur `main`, der Kopf bleibt); das Raster ohne `min-height:100vh` (mit dem Kopf darüber
  rollte sonst jede Seite um dessen Höhe).
- **Zurück-Link + Karte**: „← Ziel“ wird zum Pfad, das letzte Glied ist die Seite selbst; Titel = Name des Eintrags, über den man die Seite
  öffnet. Die Karten behalten ihre Überschriften, außer die eine, die bis dahin den Titel trug (Änderungshistorie).
- **Links in `--ds-link`** (`a{…}` von Konto und Einstellungen, `.link` der Stammdaten, drei Links mit `style="color:var(--accent)"`),
  **Fokus in `--ds-fokus`** auf allen 8 Seiten (Einstellungen auch `button:focus-visible` und das Menü, bis dahin `--ink`); die toten Regeln
  `.back`, `.head`, `.add` und `.settings-sidebar h2` entfernt. Die Akzentfarbe an Stellen, die keine Links sind (Monatsbanner des
  Backoffice, Pfeil der aufklappbaren Rechner in den Einstellungen), bleibt -- wie bei den früheren Gruppen.

| Seite | Pfad | Hauptaktion | Menü „⋮“ |
|---|---|---|---|
| Stammdaten | -- | „+ Hinzufügen“ (je Bereich; bei Mitarbeitern nur Büro – Finanzen und Admin, wie bisher) | -- |
| Einstellungen | -- | -- | -- |
| Zeiterfassungs-Backoffice | -- | -- („Aktualisieren“ bleibt bei den Filtern) | -- |
| Mein Konto | Start / Mein Konto (Monteurin: Einsätze / Mein Konto) | -- | -- |
| Benutzer und Zugriff | Einstellungen / Benutzer und Zugriff | -- | -- |
| Änderungshistorie | Einstellungen / Änderungshistorie | -- | -- |
| Adressimport | Einstellungen / Adressimport | -- | -- |
| Leistungskatalog | Stammdaten / Leistungskataloge / Leistungskatalog | -- („+ Leistung anlegen“ bleibt in der Liste) | -- |

#### Tests und Prüfung

- `test_v441`: `UMGEZOGEN` um die 8 Seiten (`UNTERMENUE_LINKS`, `ZURUECK_UND_KARTE`), der Strukturtest
  `test_umgezogene_seite_hat_den_gemeinsamen_kopf` läuft damit für 33 Seiten.
- Neu `tests/test_v454_untermenue_und_karte.py` (13 Tests): der Pfad jeder K6-Seite je Rolle gerendert (das Konto auch als Monteurin), jedes
  Ziel öffnet sich für diese Rolle mit 200 ohne Umleitung; die K5-Seiten ohne Pfad; Stammdaten: „+ Hinzufügen“ als einzige Aktion im Kopf,
  `render()` schreibt in den Kopf und blendet über `hidden` aus; Einstellungen: Menü ohne eigene Überschrift; Backoffice: Kopf vor `<main>`,
  Raster ohne `min-height`.
- `klicktest_rahmen` Teil `untermenue` (neu): je Seite hell und dunkel bei 1440 × 900, das Konto auch als Monteurin -- `.ds-seite`, ein h1
  mit dem Titel, Untertitel, Pfad mit Texten und Zielen (jeder Link mit der Anmeldung der Seite geladen: 200 ohne Umleitung, HTML), kein
  `.back`, Hauptaktion nur in den Stammdaten, kein Menü, Textlinks in `--ds-link`, Fokus in `--ds-fokus`, Kontrast; Stammdaten: „Objekte“ im
  Untermenü wechselt Titel und Ziel von „+ Hinzufügen“, Büro – Auftrag ohne „+ Hinzufügen“ bei Mitarbeitern (sichtbar bei Lieferanten);
  Einstellungen behalten den Titel beim Wechsel des Bereichs; „Aktualisieren“ im Backoffice lädt die Kennzahlen neu.
- **Gegenproben** (Marker `GEGENPROBE`, byte-genau zurück, je pytest und -- wo der Browser es zeigt -- Klicktest-Teil):
„+ Hinzufügen“ der Stammdaten wieder über `style.display` (G1); Pfad-Link der Benutzerseite ins Leere (`/einstellungen`, G2); Fokus der
  Änderungshistorie wieder in `--ds-aktion` (G3); Pfad der Monteurin im Konto über `/` statt `/mobil` (G4); Link im Leistungskatalog wieder
  in der Akzentfarbe (G5); Backoffice-Raster wieder mit `min-height:100vh` (G6); Überschrift „Einstellungen“ wieder im Menü (G7) -- **7 von
  7 rot** in pytest (FAILED, je der zuständige Test: `test_v454` G1, G2 mit `test_v438`, G4, G6, G7; `test_v441` G3, G5), der Klicktest-Teil
  `untermenue` für G1–G5 je rot (167, 164, 166, 164, 166 von 168: Büro – Auftrag sähe „+ Hinzufügen“ mit `hidden=false` versteckt, Pfad
  und 404, Fokus, Umleitung über `/`, Linkfarbe); G6 und G7 zeigt der Browser nicht als Abweichung (Höhe des Rasters, eine Überschrift
  mehr), dafür nur pytest.
- **Angepasste Erwartungen** (Regel 28):
  - `test_v441::UMGEZOGEN`: alt 25 Seiten; neu dazu die 8.
  - `test_v438::test_benutzerseite_zurueck_in_die_einstellungen`: alt genau ein `.back`-Link „← Einstellungen“ nach /settings; neu der Pfad
    „Einstellungen“ (/settings) / „Benutzer und Zugriff“, kein `.back`.
  - `test_v439::test_zurueck_link_mit_echtem_ziel`: alt je ein `.back`-Link „← Einstellungen“ (Adressimport, Änderungshistorie) bzw. „←
    Stammdaten: Leistungskataloge“; neu die Pfad-Glieder mit Zielen und das letzte Glied, jedes Ziel 200.
  - `test_v244::test_users_and_history_pages_have_back_link_to_settings`: alt der wörtliche `.back`-Link; neu der wörtliche Pfad-Link
    „Einstellungen“.
  - `test_v243::test_leistungskatalog_page_has_back_link_to_master_data`: alt `.back`-Link aus `zurueck` und
    `zurueck_stammdaten("catalogs")`; neu die Pfad-Links „Stammdaten“ und „Leistungskataloge“, kein `.back` (die Route gibt kein `zurueck`
    mehr).
  - `test_v257::test_account_html_back_link_has_no_history_back_shortcut`: alt `class="back no-print"` mit `href="/"`; neu der Pfad „Start“
    (`/`) und für die Monteurin „Einsätze“ (`/mobil`), ohne history.back.
  - `test_v259`: alt `a{color:var(--accent)}` in Konto und Einstellungen und `.back{color:var(--accent)…` im Konto; neu
    `a{color:var(--ds-link)}` und kein `.back` (Pfad-Link statt dessen).
  - `klicktest_beteiligte`, `klicktest_beteiligte_stammdaten`: alt bereit, wenn `#title` „Adressbuch“ zeigt; neu `#seitenkopfTitel`.

#### Festlegungen 1.9.21 (Bitte bestätigen)

1. **Untermenü-Seiten ohne Pfad**, Kopf über Menü und Inhalt (wie auf jeder Seite oben links); das Untermenü bleibt die Navigation.
2. **Stammdaten: Titel = gewählter Bereich** (wie bis dahin das h1 der Karte), Untertitel = Zahl der Einträge, „+ Hinzufügen“ als
   Hauptaktion; die Suche bleibt in der Karte; die Links „Leistungen durchsuchen / XML importieren“ und „alle Materialien anzeigen“ bleiben im
   Untertitel.
3. **Einstellungen: Titel „Einstellungen“**, das Menü ohne eigene Überschrift, die Bereiche behalten ihre Überschrift in der Karte (kein
   wechselnder Titel -- er stünde doppelt).
4. **Backoffice: Zeitraum und „Aktualisieren“ bleiben als Werkzeugleiste** in der ersten Karte (keine Hauptaktion im Kopf); Raster ohne
   `min-height:100vh`.
5. **Zurück-Link-Seiten: Titel = Name des Eintrags, über den man kommt** (Mein Konto, Benutzer und Zugriff, Änderungshistorie,
   Adressimport, Leistungskatalog); die Karten behalten ihre Überschriften („ERP-Benutzer“, „Adressimport aus dem Altsystem“, die Liste des
   Leistungskatalogs), nur die Änderungshistorie verliert ihre (sie war der Titel).
6. **Pfad = bisheriger Rückweg + Seite**: Einstellungen / …, Stammdaten / Leistungskataloge / Leistungskatalog, Start / Mein Konto; die
   Monteurin Einsätze / Mein Konto (dorthin leitete „Zur Startseite“ sie schon).
7. **Akzentfarbe an Nicht-Links bleibt** (Monatsbanner im Backoffice, Pfeil der aufklappbaren Rechner, Kennzeichen „Lieferant“ im
   Adressimport) -- wie bei den früheren Gruppen.

### Punkt 3 (1.9.22): Stammdaten-Formular und Leistung im Rahmen

- **Rahmen**: Seitenleiste (Bereich „Stammdaten“, als erste Anweisung) und Kopfzeile, `.ds-seite`, der Inhalt in `<main>` links unter dem
  Kopf (bis dahin eine zentrierte Karte ohne Leiste); die Karte behält ihre Breite (1000 bzw. 1100 px), der Kopf ist so breit wie sie.
  Damit haben 44 Seiten die Leiste (bis dahin 42); ohne Rahmen bleiben Anmeldung, Sperrseite, Neues Projekt und Neues Angebot.
- **Pfad**: Bereich der Leiste, dann der bisherige Rückweg, am Ende die Seite selbst. Stammdaten-Formular: die Glieder vor der Seite kommen
  vom Server (`app/routers/pages.py::pfad_stammdaten()`: Stammdaten / <Bereich>, beim Objekt Stammdaten / Objekt, aus der Projektmappe
  Projekte / Projektmappe), das letzte setzt `titel()` zusammen mit dem Titel (bis dahin `el('heading').textContent=…`, die Texte sind
  dieselben). Leistung: fest Stammdaten / Leistungskataloge / Leistungskatalog.
- **Kopf**: „Abbrechen“ (neutral, `href` = bisheriges Zurück-Ziel `zurueck.href`, dasselbe wie das letzte Glied vor der Seite) und
  „Speichern“ (grün, `data-klick="speichern"` -> dasselbe `save()` wie der Knopf unten). Der Knopf unten bleibt, mit seiner Meldung `#msg`;
  bleibt die Seite nach einem Klick oben stehen (abgelehnte Eingabe, Fehler), rückt die Meldung ins Bild (`scrollIntoView` mittig, nur dann).
  Eine importierte Leistung (nicht bearbeitbar) verbirgt beide „Speichern“.
- **Unverändert**: Felder, `save()` und die Ziele danach (Liste des Bereichs, Objekt, Betriebsmittel, Projektmappe mit neuem Kontakt,
  Katalog der Leistung), die Rückfrage bei laufender Gruppenzeit (Teams). Links im Kontaktformular („Kunde öffnen“, die Projekte) in
  `--ds-link` (bis dahin die Klasse `.back` in der Akzentfarbe), Fokus in `--ds-fokus`; tote Regeln `header`, `.back`, `.topnav`, `h1`
  entfernt.

| Seite | Pfad | Hauptaktion | Menü „⋮“ |
|---|---|---|---|
| Stammdaten-Formular | Stammdaten / <Bereich> / <Titel> (z. B. Mitarbeiter bearbeiten, Kunde anlegen); Objekt: Stammdaten / Objekt / …; Kontakt aus der Projektmappe: Projekte / Projektmappe / Kontakt anlegen | „Speichern“ (daneben „Abbrechen“ neutral) | -- |
| Leistung | Stammdaten / Leistungskataloge / Leistungskatalog / Leistung bearbeiten bzw. anlegen | „Speichern“ (daneben „Abbrechen“ neutral; bei einer importierten Leistung nur „Abbrechen“) | -- |

#### Tests und Prüfung

- `test_v441`: `UMGEZOGEN` um die 2 Seiten (`FORMULARSEITEN`, 35 Seiten); 44 statt 42 Seiten mit Leiste, beide mit `bereich`.
- Neu `tests/test_v455_formularseiten_im_rahmen.py` (17 Tests): Rahmen und Bereich; im Kopf genau „Abbrechen“ (neutral, Zurück-Ziel) und
  „Speichern“ (grün, ruft `save()` und holt die Meldung ins Bild), der Knopf unten bleibt; jeder Titel über `titel()`; für jeden Bereich endet
  `pfad_stammdaten()` am Ziel von `zurueck_stammdaten()`; neun Adressen gerendert: Pfad, „Abbrechen“ = letztes Glied, jedes Ziel 200,
  „Stammdaten“ in der Leiste aktiv; importierte Leistung ohne „Speichern“ oben.
- `klicktest_rahmen` Teil `formularseiten` (neu): Mitarbeiter bearbeiten, Leistung bearbeiten, Kunde anlegen, Kontakt aus der Projektmappe,
  je hell und dunkel bei 1440 × 900 -- Leiste mit „Stammdaten“ aktiv, Kopfzeile, `.ds-seite`, ein h1 mit dem Titel, Pfad (jeder Link öffnet
  eine Seite), „Abbrechen“ neutral mit dem Zurück-Ziel, „Speichern“ grün, Knopf unten mit `save()`, Links, Fokus, Kontrast; dazu „Speichern“
  oben ohne Kurztext -> „Bitte Kurztext und Einheit ausfüllen.“ unten im Bild, Seite bleibt; mit Kurztext gespeichert, Ziel der Katalog;
  Mitarbeiter mit „Speichern“ oben -> Liste der Mitarbeiter; „Abbrechen“ mit geändertem Nachnamen -> Liste, nichts gespeichert.
- **Gegenproben** (Marker `GEGENPROBE`, byte-genau zurück, je pytest und -- wo der Browser es zeigt -- Klicktest-Teil):
„Abbrechen“ im Stammdaten-Formular nach `/master-data` statt zum Zurück-Ziel (H1); „Speichern“ oben in der Leistung ohne `save()` (H2);
  Pfad des Stammdaten-Formulars ohne den Bereich der Leiste (H3, `pfad_stammdaten()`); Meldung nicht ins Bild (H4); importierte Leistung mit
  „Speichern“ oben (H5); Stammdaten-Formular ohne `bereich` (H6) -- **6 von 6 rot** in pytest (FAILED: H1 15 Tests aus `test_v455` und
  `test_v436`, H2 1, H3 6, H4 1, H5 1, H6 10 mit den beiden Zählungen in `test_v441`), der Klicktest-Teil `formularseiten` für H1–H4 und
  H6 je rot (73, 78, 76, 79, 74 von 80: „Abbrechen“ mit falschem Ziel und die Liste ohne `#employees`; keine Meldung und kein Speichern;
  Pfad ohne „Stammdaten“; Meldung unter dem Fenster; kein aktiver Eintrag der Leiste); H5 zeigt der Browser nicht (die Testdaten haben
  keine importierte Leistung), dafür nur pytest.
- **Untersucht und geändert** (vor dem Commit): der erste Lauf des Klicktest-Teils fand die Meldung nach „Speichern“ oben nicht im Bild --
  mit `scrollIntoView({block:'nearest'})` lag sie genau am unteren Fensterrand (Unterkante 900 von 900 px, mit Bruchteil darüber). Jetzt
  `block:'center'`: die Meldung steht mit dem Knopf unten mitten im Fenster.
- **Angepasste Erwartungen** (Regel 28):
  - `test_v436::test_zurueck_link_mit_echtem_ziel` (9 der 13 Fälle): alt genau ein `.back`-Link „← Stammdaten: Mitarbeiter“ usw. bzw. „←
    Leistungskatalog“; neu das letzte Glied des Pfads („Mitarbeiter“, „Kunden“, „Fuhrpark & Maschinen“, „Betriebsmittel“,
    „Materialkataloge“, „Objekt“, „Projektmappe“, „Leistungskatalog“) und „Abbrechen“, beide zum selben Ziel wie bisher, kein `.back`.
  - `test_v246::test_form_page_renders_the_employee_form`: alt `el('heading').textContent=editing?'Mitarbeiter bearbeiten':'Mitarbeiter
    anlegen'`; neu `titel(editing?'Mitarbeiter bearbeiten':'Mitarbeiter anlegen')`.
  - `test_v441::test_jede_seite_mit_leiste_nennt_ihren_bereich` und `test_jede_seite_markiert_ihren_bereich`: alt 42 Seiten; neu 44.
  - `test_v441::UMGEZOGEN`: alt 33 Seiten; neu dazu die 2.
  - `klicktest_versand_im_kontext`: alt bereit, wenn `#heading` „Leistung bearbeiten“ zeigt; neu `#seitenkopfTitel`.

#### Festlegungen 1.9.22 (Bitte bestätigen)

1. **Inhalt links unter dem Kopf** in der bisherigen Breite der Karte (1000 bzw. 1100 px), der Kopf so breit wie die Karte; nicht mehr
   zentriert.
2. **Pfad des Stammdaten-Formulars = Bereich der Leiste + bisheriger Rückweg + Seite**; aus der Projektmappe beginnt er mit Projekte (die
   Leiste zeigt weiter Stammdaten).
3. **Titel unverändert** (die Texte aus dem Skript, bis zum Laden „Stammdaten“ bzw. „Leistung anlegen“ wie bisher), er ist zugleich das
   letzte Glied des Pfads; der Hilfetext bleibt als erster Absatz in der Karte.
4. **„Speichern“ oben = derselbe Weg wie unten**; bleibt die Seite stehen, rückt die Meldung unten ins Bild -- sonst sähe man oben nach einer
   abgelehnten Eingabe nichts.
5. **„Abbrechen“ ohne Rückfrage** zum bisherigen Zurück-Ziel (wie der Zurück-Link bisher); Speichern unten bleibt mit seiner Meldung.
   -- **Nicht bestätigt** (Runde 9): ersetzt durch 1.9.23, „Abbrechen“ fragt bei ungespeicherten Änderungen.
6. **Importierte Leistung**: oben nur „Abbrechen“ (wie unten kein Speichern).

### Runde 8 abgeschlossen: Endläufe, Bildvergleich, Beleg (Stand `dc0224c`)

- **Endlauf** auf `dc0224c` bei sauberer Arbeitskopie (vorher und nachher keine Änderung): volle Suite **6611 bestanden, 3 übersprungen,
  0 rot** (7:53); **Klicktests 80 von 80** wie erwartet (zu viert, 8:15), keine Wiederholung nötig.
- **Bildvergleich** (volle Bildgrundlage, je 298 Bilder, drei Läufe unmittelbar hintereinander, gleiche Chrome-Version):
  - Rundenstart `fd499ab` gegen 1.9.20 `dffe586` (Punkt 1): **298 von 298 gleich** -- Angebotsdatum und „Gültig bis“ stehen auf keiner
    aufgenommenen Seite (nur im PDF und im Reiter „Angebotsdetails“), die Abschrift des Auftrags ebenso nicht; die Änderung wirkt auf die
    Belege und die Daten selbst (`test_v453`).
  - 1.9.20 `dffe586` gegen `dc0224c` (Punkte 2 und 3): **250 gleich, 48 abweichend, alle auf den 10 Seiten der Runde** -- Stammdaten,
    Einstellungen, Backoffice, Benutzer, Änderungshistorie, Adressimport, Leistungskatalog, Stammdaten-Formular und Leistung je 4 Bilder
    (hell/dunkel, 412/1440), Mein Konto 12 (Büro 4, Monteurin 8 mit TerraPad). Jede Seite der Runde weicht ab, keine andere.
- **Bilder**: `bildgrundlage/rahmen_runde8_dc0224c.zip` (14 Dateien) -- `nachher/`: die 11 Ansichten der Runde als Fenster 1440 × 900 hell
  (Konto auch als Monteurin), die Stammdaten auch dunkel; `vorher/` (1.9.20): Stammdaten-Formular (Mitarbeiter bearbeiten) und Leistung.
- Commits der Runde: `dffe586` (1.9.20 Testdaten nicht am Lauftag), `d734c64` (1.9.21 Untermenü und Zurück-Link), `dc0224c` (1.9.22
  Formularseiten im Rahmen).
- **Nebenbefund** aus einem Zwischenlauf (16 Klicktests zu viert, vor dem Commit von 1.9.22): im Teil „schrift“ von `klicktest_rahmen` kam
  eine Anfrage der Seite „Checklisten je Auftrag“ nie beim Server an (`/api/checklists/startable-templates`, „Server: nicht angekommen“) --
  derselbe Befund wie in Runde 6, Punkt 2. Die Wiederholung (1.9.19) griff dort nicht, weil derselbe Lauf eine zweite, echte Abweichung
  hatte (die Meldung nach „Speichern“ oben, siehe Punkt 3); der Teil lief danach einzeln und im Endlauf grün.

## Runde 9 (Festlegungen 1.9.20 bis 1.9.22 bestätigt, außer 1.9.22 Nr. 5) -- letzte Runde des Rahmens

Auftrag (22.10.2026): 1. Formularseiten: „Abbrechen“ fragt „Änderungen verwerfen?“, nur bei ungespeicherten Änderungen, mit einem Test,
der vorher scheitert; 2. Seitenkopf von Anfragen und Arbeitsvorbereitung (diese mit Pfad über Projekt und Auftrag, Kennung und Status);
3. Monteursseiten, die bleiben (Checkliste, Checklisten zum Auftrag, Objekt der Monteursansicht, Betriebsmittel der Monteurin): Seitenkopf
im Monteursrahmen mit Tablet-Maßen (Pfad 15 px, Titel 26 px, Knöpfe mindestens 48 px), Pfad zurück zu „Einsätze“ bzw. zum Auftrag; 4.
Anmeldung und Sperrseite: `.ds-seite`, Bildmarke mit Schriftzug, neuer Untertitel der Anmeldung, auf der Sperrseite nichts doppelt; 5.
„Benutzer und Zugriff“: der Hinweis nennt keine internen Dateien; 6. Abschluss Stufe 2: Wächter, jede Seite umgezogen oder aufgeschoben
mit Stufe und Grund. Bildvergleich: außer den Seiten der Runde weicht nichts ab.

### Punkt 1 (1.9.23): „Abbrechen“ fragt bei ungespeicherten Änderungen

- Neuer Baustein `app/templates/_abbrechen.html` (braucht `_aktionen.html`): `abbrechenEinrichten(wurzel, zusatz)` merkt am Ende des Ladens
  den Stand jedes Felds unter `wurzel` -- Wert, Häkchen, gewählte Dateien; ein Feld mit `data-ohne-stand` zählt nicht -- und, wenn
  angegeben, `zusatz()`; der Link „Abbrechen“ (`data-klick="abbrechen"`, `href` unverändert das bisherige Zurück-Ziel) vergleicht beim
  Klick: unterscheidet sich der Stand, fragt `confirm('Änderungen verwerfen?')`; abgelehnt `preventDefault()` (die Seite bleibt mit allen
  Eingaben), bestätigt folgt der Link. Vor dem Ende des Ladens (oder wenn es scheiterte) gibt es keinen Stand und keine Frage; ein Klick
  mit Strg, Umschalt, Alt oder Cmd (neuer Tab oder Fenster) verwirft nichts und fragt nicht.
- **Stammdaten-Formular**: Stand über `#form` am Ende von `init()`; vorgemerkte Dokumente eines neuen Betriebsmittels zählen mit
  (`pendingAssetDocuments`), die Felder zum Vormerken (Art, Datei, Bemerkung) nicht. **Leistung**: Stand über `#editableArea`; Material
  einer neuen Leistung zählt mit (geht erst mit dem Speichern hinaus; beim Bearbeiten speichert „+ Hinzufügen“ sofort), die Felder zum
  Hinzufügen (Suche, Auswahl, Menge, Verschnitt) nicht.

#### Tests und Prüfung

- Neu `tests/test_v456_abbrechen_fragt.py` (4 Tests): die vom Server gezeichnete Seite läuft in node bis zum Ende von `init()` (Stammdaten-
  Formular „Lieferant anlegen“, „Leistung anlegen“), danach der Klick auf „Abbrechen“: vor dem Laden keine Frage, ohne Änderung keine Frage
  und kein `preventDefault`, nach einer Änderung die Frage -- abgelehnt verhindert, bestätigt nicht --, mit Strg keine Frage,
  zurückgeändert keine Frage; Materialsuche zählt nicht, vorgemerktes Material und Kurztext zählen; Stand am Ende von `init()` über die
  Felder des Formulars, Hilfsfelder mit `data-ohne-stand`. **Gegen 1.9.22: 4 von 4 rot** („Abbrechen“ ohne Aktion, kein Stand).
- `klicktest_rahmen` Teil `formularseiten` erweitert: Mitarbeiter -- „Abbrechen“ ohne Änderung ohne Rückfrage zur Liste; Nachname geändert:
  Rückfrage „Änderungen verwerfen?“, abgelehnt bleibt die Seite mit der Eingabe (der ausgelöste Klick meldet `preventDefault`, der Zustand
  im selben Schritt gelesen -- kein Wartefenster), bestätigt zur Liste, nichts gespeichert; Leistung -- nur die Materialsuche geändert: ohne
  Rückfrage zum Katalog, Kurztext geändert: Rückfrage, abgelehnt bleibt die Seite. 87 von 87.
- **Gegenproben** (Marker `GEGENPROBE`, byte-genau zurück): „Abbrechen“ fragt immer (J1), nie (J2), Materialsuche zählt mit (J3), Stand
  über die ganze Seite statt `#form` (J4), vorgemerktes Material zählt nicht (J5) -- **5 von 5 rot** in pytest (FAILED, `test_v456`), der
  Klicktest-Teil für J1–J3 rot (85, ..., 86 von 87: ohne Änderung gefragt bzw. nicht weiter; geändert nicht gefragt; Suche gefragt); J4 und J5
  zeigt der Browser nicht (die ganze Seite enthält das Formular; die Testdaten legen keine neue Leistung mit Material an). **Selbst gefunden**:
  unter J2 stürzte der Klicktest ab (die Seite folgte dem Link, bevor der Zustand gelesen war), statt die Abweichung zu melden -- seither
  liest er Klick und Zustand in einem Schritt; danach meldete J2 seine zwei Abweichungen.
- **Angepasste Erwartungen** (Regel 28):
  - `test_v455::test_kopf_abbrechen_neutral_speichern_gruen_knopf_unten_bleibt`: alt `<a class="ds-knopf" id="abbrechenLink" href="{{
    zurueck.href }}">Abbrechen</a>`; neu mit `data-klick="abbrechen"`.
  - `test_v455::test_pfad_gerendert_und_ziele_oeffnen_sich` und `test_v436::test_zurueck_link_mit_echtem_ziel`: nur der Aufbau -- das
    Muster des Links lässt weitere Attribute nach `href` zu.
  - `klicktest_rahmen` (formularseiten): alt „Abbrechen“ mit geändertem Nachnamen führt ohne Frage zur Liste; neu fragt es, abgelehnt bleibt
    die Seite, bestätigt zur Liste.
- **Attrappe der node-Tests** (`tests/test_v334_auswahl_restfaelle.py`): `BAUSTEINE` um `_abbrechen.html` (eine Seite, die ihn einbindet,
  bekommt ihn auch im Test).

#### Festlegungen 1.9.23 (Bitte bestätigen)

1. **Gefragt wird nur bei „Abbrechen“**; Pfad, Leiste und Kopfzeile verlassen die Seite wie bisher ohne Frage.
2. **Ungespeichert = Stand der Felder des Formulars nach dem Laden ungleich jetzt** -- zurückgeändert gilt als unverändert; vorgemerkte
   Zeilen zählen, Felder zum Hinzufügen nicht.
3. **Frage als Ja/Nein-Dialog des Browsers** (`confirm`, wie „wirklich löschen?“, Regel 4): „Änderungen verwerfen?“, OK verwirft.
4. **Klick mit Strg/Cmd/Umschalt/Alt** (neuer Tab oder Fenster) fragt nicht -- die Seite bleibt ja offen.
5. **Vor dem Ende des Ladens fragt „Abbrechen“ nie.**

### Punkt 2 (1.9.24): Seitenkopf von Anfragen und Arbeitsvorbereitung

- **Anfragen** (befund-rahmen.md K9, bis dahin ohne Seitentitel): Titel „Anfragen“ mit Untertitel über den Kennzahlen; keine Hauptaktion
  (es gab keinen Kopf) -- „Neue Anfrage“ bleibt die Karte darunter, „Aktualisieren“ bei der Pipeline.
- **Arbeitsvorbereitung** (K4, bis dahin `.hero` mit fettem `div` als Titel, „← Auftrag“, „Projektmappe“, „Zeiterfassung (Auftrag)“ als
  umrandete Links, Status roh als Pille): Pfad Projekte / Kunde / Projekt / Auftrag / Arbeitsvorbereitung -- den Kunden nennt erst der
  Auftrag, die Seite lädt dafür zusätzlich `GET /api/orders/{id}` (fehlt er, steht der Pfad ohne Kunden); das Projekt führt wie bis
  dahin „Projektmappe“ auf den Reiter Aufträge (`#sec-orders`, `test_v064`); Kennung = Auftragsnummer;
  Untertitel wie bis dahin „Projektnummer · Projektname“; Status der Arbeitsvorbereitung über `statusKennzeichen('arbeitsvorbereitung', …)`;
  „Zeiterfassung (Auftrag)“ im Menü (wie am Einsatzbericht, `#timeLink` mit dem Auftrag); die sechs Kennzahlen in der Zeile unter dem Kopf.
  Ändert das Büro den Status und speichert, zeichnet `render()` den Kopf mit (über `kopfZeichnen()`).
- Neue Gruppe `arbeitsvorbereitung` in `_statuskennzeichen.html`: Offen (wartet auf dich), In Planung (läuft), Bereit (erledigt), In
  Ausführung (läuft), Abgeschlossen (erledigt).
- Links in `--ds-link` (`a{…}`, `.delivery-tag a`), Fokus in `--ds-fokus` auf beiden Seiten; tote Regeln `.hero`, `.grow`, `.top-actions`
  entfernt.

| Seite | Pfad | Hauptaktion | Menü „⋮“ |
|---|---|---|---|
| Anfragen | -- | -- | -- |
| Arbeitsvorbereitung | Projekte / Kunde / Projekt / Auftrag / Arbeitsvorbereitung | -- | Zeiterfassung (Auftrag) |

#### Tests und Prüfung

- `test_v441`: `UMGEZOGEN` um die 2 Seiten (`ANFRAGEN_UND_ARBEITSVORBEREITUNG`, 37 Seiten).
- `test_v446::RUECKWEGE` um die Arbeitsvorbereitung (Projekte, Kunde, Projekt, Auftrag; jedes Ziel eine Seite für Büro – Auftrag).
- `test_v445::test_jeder_wert_des_servers_steht_in_der_tabelle` um die Arbeitsvorbereitung (jede Option der Auswahl „Status“ und der Wert,
  den der Server schreibt).
- `klicktest_rahmen` Teil `anfragen_av` (neu): beide Seiten hell und dunkel bei 1440 × 900 -- `.ds-seite`, ein h1, Kennung, Untertitel,
  Status (Arbeitsvorbereitung: „Offen“, signal), Pfad mit Zielen (jeder Link öffnet eine Seite), kein alter Kopf, keine Hauptaktion, Menü,
  Links, Fokus, Kontrast; die Kennzahlen der Anfragen unter dem Kopf; „Zeiterfassung (Auftrag)“ mit dem Auftrag; Status „In Planung“
  gespeichert -> der Kopf zeigt „In Planung“ (info). 39 von 39. Dazu die Klicktests, die die Seiten öffnen (`klicktest_arbeitsvorbereitung`,
  `klicktest_auswahl_inaktiv`, `klicktest_zahleneingaben`): 3 von 3.
- **Selbst gefunden** (volle Suite vor dem Commit): `test_v064` verlangt den Sprung der Arbeitsvorbereitung auf den Reiter Aufträge der
  Projektmappe (`#sec-orders`) -- das Pfad-Glied des Projekts führte zuerst nur auf `/projects/{id}`; seither mit `#sec-orders`.
- **Gegenproben** (Marker `GEGENPROBE`, byte-genau zurück): Pfad der Arbeitsvorbereitung ohne Kunden (K1); Status roh statt über das
  Kennzeichen (K2); Fokus der Anfragen wieder in `--ds-aktion` (K3); Gruppe ohne „bereit“ (K4) -- **4 von 4 rot** in pytest (FAILED:
  `test_v446` Rückwege, `test_v445` Status nur über das Kennzeichen, `test_v441` Fokus, `test_v445` Werte des Servers), der Klicktest-Teil
  für K1–K3 rot (37, 36, 37 von 39); K4 zeigt der Browser nicht (die Testdaten stehen auf „offen“).
- **Angepasste Erwartungen** (Regel 28):
  - `test_v441::UMGEZOGEN`: alt 35 Seiten; neu dazu die 2.
  - `test_v259::test_work_preparation_html_has_a_general_link_color_rule`: alt `a{color:var(--accent)}`; neu `a{color:var(--ds-link)}`.
  - `test_v259::test_more_specific_link_styles_are_still_present_and_unaffected` (Arbeitsvorbereitung): alt `.top-actions a{` und
    `.delivery-tag a{` vorhanden; neu kein `.top-actions a{` (Pfad-Link statt dessen), `.delivery-tag a{color:var(--ds-link)}`.

#### Festlegungen 1.9.24 (Bitte bestätigen)

1. **Anfragen: Titel „Anfragen“, Untertitel „Vertriebsfälle von der Anfrage bis zum Projekt“**, keine Hauptaktion, die Kennzahlen unter
   dem Kopf.
2. **Arbeitsvorbereitung: Pfad Projekte / Kunde / Projekt / Auftrag / Arbeitsvorbereitung** (wie Rechnung und Einsatzbericht), Kennung =
   Auftragsnummer, Untertitel „Projektnummer · Projektname“ wie bis dahin.
3. **Status im Kopf = Status der Arbeitsvorbereitung** (nicht der des Auftrags): Offen wartet auf dich (signal), In Planung und In
   Ausführung laufen (info), Bereit und Abgeschlossen erledigt (ok).
4. **„Zeiterfassung (Auftrag)“ ins Menü**, „← Auftrag“ und „Projektmappe“ in den Pfad; keine Hauptaktion (der Kopf hatte keine grüne).
5. **Die sechs Kennzahlen unter dem Kopf** (für den Kopf zu viele; an der Rechnung drei, am Angebot vier im Kopf).

### Punkt 3 (1.9.25): Monteursseiten im Seitenkopf mit Tablet-Maßen

- **Befund vorweg**: der Auftrag nennt den Einsatzbericht als Vorbild für die Tablet-Maße (Pfad 15 px, Titel 26 px, Knöpfe mindestens
  48 px). Der Einsatzbericht hatte sie nicht: keine Seite setzte die Tablet-Klasse, die Monteurin sah dort den Kopf des Büros (Titel 30 px,
  Pfad 13 px, Menüknopf 40 px); in `ds.css` stand nur `.ds-tablet .ds-kopf-titel` (26 px) für eine Klasse, die niemand setzte. Umgesetzt
  daher als Variante des Makros und für jede Seite im Monteursrahmen, den Einsatzbericht und das Konto der Monteurin eingeschlossen.
- **Variante `tablet`** (`seitenkopf(…, tablet=…)`, Klasse `ds-kopf-tablet`, Regeln in `ds.css`): Pfad `--ds-groesse-4` (15 px), Titel
  `--ds-groesse-9-tablet` (26 px), `.ds-knopf`, Menüknopf (`.ds-knopf-symbol` 48 × 48) und `.ds-menue-eintrag` 48 px hoch. Nur der Kopf --
  keine Tablet-Klasse am `<body>`, die übrige Seite bleibt, wie sie war.
- **Checkliste** (Büro und Monteur; bis dahin „← zurück“ und eine Karte mit h1, Kennzeichen und PDF, alles aus `renderHeader()`): der Kopf
  steht vor dem neu gezeichneten Inhalt (`#clMain`), `kopfZeichnen()` setzt nach dem Laden Titel (Vorlage), Untertitel (Kontextangabe ·
  angelegt … · Fassung), Status (`statusKennzeichen('checkliste', …)`, neue Gruppe: Entwurf, Abgeschlossen, Gegenstandslos) und Pfad:
  Bereich (Büro „Checklisten“, Monteur „Einsätze“) / Kontext mit dem bisherigen Rückweg (`backLink()`: der Monteur über „Checklisten zum
  Auftrag“ bzw. Objekt und Betriebsmittel der Monteursansicht, das Büro über Auftrag, Objekt, Betriebsmittel; bei „Betrieb“ ohne
  Kontextglied) / Titel. „PDF“ als neutrale Aktion im Kopf, verborgen, solange die Checkliste Entwurf ist; „Nur lesen …“ und das
  Abschlusssiegel in einer Karte unter dem Kopf.
- **Checklisten zum Auftrag** (bis dahin „← zurück“ und eine Karte „Auftrag <Nummer>“): Titel „Checklisten zum Auftrag“, Kennung =
  Auftragsnummer, Untertitel = Kunde; Pfad Büro Checklisten / <Auftrag> / Checklisten zum Auftrag, Monteur Einsätze / Checklisten zum
  Auftrag.
- **Objekt der Monteursansicht** (für jede Rolle im Monteursrahmen; bis dahin „← Einsätze“ und der Name fett in der Karte): Titel = Name
  des Objekts, Pfad Einsätze / <Objekt>; die Karte mit Adresse, Ansprechpartner und Zugang (ohne Angaben verborgen); die Abschnitte
  (Dokumente, Datei hochladen, Checklisten, Frühere Wartungsberichte) als h2 statt h1.
- **Betriebsmittel der Monteurin** (bis dahin ohne Rückweg außer dem Reiter, h1 und Zeile in der Karte): Titel = Name, Untertitel Art ·
  Hersteller · Modell, Pfad Einsätze / <Betriebsmittel>; die Meldung „Nicht einsatzbereit“ direkt unter dem Kopf; die Karte nur mit den
  Bedienungshinweisen (ohne verborgen).
- Links in `--ds-link`, Fokus in `--ds-fokus`; tote Regeln `.back`, `.back-link`, `h1`, `.obj-name`, `.meta` entfernt.

| Seite | Pfad | Hauptaktion | Menü „⋮“ |
|---|---|---|---|
| Checkliste (Monteurin) | Einsätze / Auftrag <Nr.> (Checklisten zum Auftrag) bzw. Objekt / Betriebsmittel / <Vorlage> | -- („PDF“ neutral ab Abschluss) | -- |
| Checkliste (Büro) | Checklisten / Auftrag <Nr.> bzw. Objekt / Betriebsmittel / <Vorlage> | -- („PDF“ neutral ab Abschluss) | -- |
| Checklisten zum Auftrag (Monteurin) | Einsätze / Checklisten zum Auftrag | -- | -- |
| Checklisten zum Auftrag (Büro) | Checklisten / <Auftragsnummer> / Checklisten zum Auftrag | -- | -- |
| Objekt der Monteursansicht | Einsätze / <Objekt> | -- | -- |
| Betriebsmittel der Monteurin | Einsätze / <Betriebsmittel> | -- | -- |
| Einsatzbericht, Konto (Monteurin, nur Maße) | unverändert | -- | unverändert |

#### Tests und Prüfung

- `test_v441`: `UMGEZOGEN` um die 4 Seiten (`MONTEURSSEITEN`, 41 Seiten); Makro mit `tablet=true` -> `ds-kopf-tablet`.
- Neu `tests/test_v457_monteursseiten.py` (20 Tests): je Seite und Rolle gerendert -- Kopf mit `ds-kopf-tablet` genau im Monteursrahmen,
  feste Pfad-Links (jedes Ziel 200 für die Rolle), kein „← …“, genau ein h1; die Regeln der Variante in `ds.css` (15 px, 26 px, 48 px);
  jede Seite im Monteursrahmen ruft das Makro mit `tablet`; Pfad der Checkliste nach dem Laden über den bisherigen Rückweg, Status über
  das Kennzeichen.
- `test_v445::test_jeder_wert_des_servers_steht_in_der_tabelle` um die Checkliste (`app/checklists.py::STATUS_LABELS`).
- `klicktest_rahmen` Teil `monteursseiten` (neu): Checkliste, Checklisten zum Auftrag, Objekt, Betriebsmittel, Einsatzbericht und Konto als
  Monteurin bei 1280 × 620 hell und dunkel -- Monteursrahmen ohne Leiste, Kopf `ds-kopf-tablet` mit Pfad 15 px, Titel 26 px, jeder sichtbare
  Knopf im Kopf mindestens 48 px; Titel, Kennung, Status, Untertitel, Pfad nach dem Laden (jeder Link öffnet eine Seite), „PDF“ nur ohne
  Entwurf, kein alter Kopf, Links, Fokus, Kontrast; Checkliste und Checklisten zum Auftrag dazu fürs Büro bei 1440 × 900 (Kopf 13/30/40 px,
  Pfad über Checklisten und den Auftrag). 150 von 150.
- Dazu die Klicktests, die eine der Seiten öffnen (38, zu viert): 34 sofort wie erwartet; drei mit überholter Erwartung (unten), danach
  grün; `klicktest_veraltete_antworten` rot aus einem Grund außerhalb der Runde -- auch auf dem Stand vor der Runde (`4527b7c`) rot, behoben
  in 1.9.26.
- **Nebenbefund** (nicht geändert): der Baustein Versandverlauf (`_email_dispatch.html`) färbt seine Links weiter in `--accent` -- auch auf
  den schon umgezogenen Seiten, die ihn einbinden (Rechnung, Angebot, Versandprotokoll, Mahnwesen, jetzt Checkliste); in den Testdaten
  ohne Versand unsichtbar. Gehört in die Runde, in der seine letzten Nutzer umziehen (Stufe 5: Projektmappe, Auftrag, Kundenakte).
- **Gegenproben** (Marker `GEGENPROBE`, byte-genau zurück): Titel im Tablet-Kopf wieder 30 px (L1); Pfad der Checkliste für den Monteur
  über den Auftrag des Büros (L2); Objekt ohne Tablet-Variante (L3); „PDF“ auch im Entwurf (L4); Einsatzbericht der Monteurin ohne
  Tablet-Variante (L5) -- in pytest 4 von 5 rot (FAILED, `test_v457`; L4 prüft nur der Browser), im Klicktest-Teil **5 von 5 rot** (138,
  146, 148, 146, 148 von 150 -- L2 dazu: der Link auf den Auftrag ergibt für den Monteur 403).
- **Angepasste Erwartungen** (Regel 28):
  - `test_v441::UMGEZOGEN`: alt 37 Seiten; neu dazu die 4.
  - `klicktest_checkliste_unterschrift`, `klicktest_checkliste_abschnitte`: alt bereit, wenn `.badge.done` erscheint, „PDF-Knopf da“ =
    `#pdfLink` vorhanden; neu der Status im Seitenkopf „Abgeschlossen“, `#pdfLink` nicht verborgen.
  - `klicktest_checkliste_verwerfen`: alt bereit bei `.badge.done`; neu der Status im Seitenkopf „Abgeschlossen“.
  - `klicktest_behinderungsanzeige_abschluss`: alt Text von `.badge.void` und `#pdfLink` vorhanden; neu Text von `#seitenkopfStatus`
    („Gegenstandslos“) und `#pdfLink` nicht verborgen.
  - `klicktest_objekt_anderer_kunde`: alt `#propertyCard` enthält den Namen des Objekts; neu `#seitenkopfTitel` ist der Name.
  - `klicktest_versandverlauf`: alt bereit bei `.card h1` der Checkliste; neu bereit, wenn der Pfad sein letztes Glied trägt.
  - `klicktest_behinderungsanzeige`: alt bereit, wenn `#clMain h1` erscheint, Titel aus `#clMain h1`; neu bereit mit dem letzten Glied
    des Pfads, Titel aus `#seitenkopfTitel`.
  - `klicktest_behinderungsanzeige_versand`: alt beide Links in der Akzentfarbe; neu der Brief-Link der Seite in `--ds-link`, der Link im
    Versandverlauf in der Farbe des Bausteins (`--accent`, unverändert, siehe Nebenbefund).
  - `klicktest_feste_fassung`: alt PDF-Link der Fassungen in der Akzentfarbe; neu in `--ds-link`.

#### Festlegungen 1.9.25 (Bitte bestätigen)

1. **Tablet-Maße nur im Kopf** (Variante `tablet`: Pfad 15 px, Titel 26 px, Knöpfe, Menüknopf, Menüeinträge 48 px); keine Tablet-Klasse
   am `<body>` -- die übrige Seite bleibt.
2. **Jede Seite im Monteursrahmen nimmt die Variante**, auch Einsatzbericht und Konto der Monteurin (der Einsatzbericht hatte sie noch
   nicht); das Objekt der Monteursansicht auch fürs Büro (dieselbe Seite im Monteursrahmen).
3. **Pfad der Monteurin**: Einsätze / [Kontext] / Seite -- eine Checkliste am Auftrag über „Auftrag <Nr.>“ zu den Checklisten zum Auftrag
   (der bisherige Rückweg; den Auftrag selbst öffnet sie nicht), am Objekt über das Objekt, am Betriebsmittel über das Betriebsmittel.
4. **Pfad im Büro**: Checklisten (Bereich der Leiste) / Kontext mit dem bisherigen Rückweg (Auftrag, Objekt, Betriebsmittel) / Seite;
   Checklisten „Betrieb“ ohne Kontextglied.
5. **Checkliste**: Titel = Vorlage, Untertitel Kontextangabe · angelegt … · Fassung, Status Entwurf (warn) / Abgeschlossen (ok) /
   Gegenstandslos (neutral), „PDF“ neutral im Kopf ab Abschluss, keine Hauptaktion.
6. **Checklisten zum Auftrag**: Titel „Checklisten zum Auftrag“, Kennung Auftragsnummer, Untertitel Kunde.
7. **Objekt und Betriebsmittel**: der Name als Titel (aus der Karte genommen); Objekt-Abschnitte als h2; leere Karten verborgen; „Nicht
   einsatzbereit“ direkt unter dem Kopf.

### Punkt 4 (1.9.27): Anmeldung und Sperrseite

- **Beide Seiten** (ohne Leiste und Kopfzeile, die Karte mittig): `<body class="ds-seite">`, in der Karte oben die Bildmarke mit
  Schriftzug (neuer Baustein `_marke.html`: Kachel 44 px, weiß mit Rand wie in Leiste und Monteurskopf, darin `_bildmarke.html`;
  daneben „DACHKONZEPTE“ in Archivo 700 und „Rödchen GmbH · ERP“ in den Farben der Karte -- hell und dunkel lesbar; die Regeln mit `svg`
  stehen im Baustein, `ds.css` nimmt nur Klassen `.ds-…`, Regel 37), darunter der gemeinsame Seitenkopf ohne Pfad (Titel 30 px). Text
  in IBM Plex Sans (die Grundregeln von `.ds-seite`), Links in `--ds-link`, Fokus in `--ds-fokus`. Die Karte bleibt eckig wie auf den
  übrigen umgezogenen Seiten.
- **Anmeldung**: Titel „Anmelden“, Untertitel „Melde dich mit deinem Benutzernamen an.“ (bis dahin h1 „DACHKONZEPTE ERP“ und „Anmeldung
  für personengenaue Änderungshistorie“). Felder und der grüne Knopf „Anmelden“ unverändert (Knopf über die ganze Breite unter den
  Feldern, keine Aktion im Kopf); `<title>` bleibt „DACHKONZEPTE ERP – Anmeldung“.
- **Sperrseite**: bis dahin h1 „Diese Seite ist für deine Rolle nicht verfügbar“ und darunter die Meldung der Prüfung -- fast immer die
  Vorgabe von `require_role()`/`require_min_role()` „Für deine Rolle nicht verfügbar.“, also zweimal dasselbe; nur ohne Meldung stand
  „Brauchst du diese Seite, wende dich …“ da. Jetzt: Titel „Kein Zugriff auf diese Seite“; die allgemeine Meldung lässt der 403-Handler
  in `app/main.py` weg (Vergleich mit `app/permissions.py::ROLLE_NICHT_VERFUEGBAR`, der Vorgabe beider Prüfungen), eine genauere (z. B.
  `require_admin()`: „Diese Aktion ist nur für Administratoren verfügbar.“) steht einmal unter dem Titel; darunter immer „Brauchst du sie,
  wende dich an eine Person mit den passenden Rechten.“ und „Zur Startseite“ als grüne Hauptaktion (`.ds-knopf.ds-knopf-aktion`, Ziel wie
  bisher die Startseite der Rolle). `<title>` bleibt „DACHKONZEPTE ERP – Kein Zugriff“.

| Seite | Pfad | Hauptaktion | Menü „⋮“ |
|---|---|---|---|
| Anmeldung | -- | „Anmelden“ (unter den Feldern) | -- |
| Sperrseite | -- | „Zur Startseite“ (unter dem Text) | -- |

#### Tests und Prüfung

- `test_v441`: `UMGEZOGEN` um die 2 Seiten (`ANMELDUNG_UND_SPERRSEITE`, 43 Seiten).
- Neu `tests/test_v458_anmeldung_und_sperrseite.py` (7 Tests): beide Seiten `.ds-seite` mit `_marke.html`; die Marke mit Bildmarke,
  Schriftzug und weißer Kachel, Regeln im Baustein; Anmeldung gerendert mit Marke vor dem Kopf vor den Feldern, h1 „Anmelden“, Untertitel,
  ohne den alten Text, Felder und Knopf unverändert; Sperrseite hinter dem 403-Handler für `require_role()` und `require_min_role()`: genau
  der Titel, kein „nicht verfügbar“, „Zugriff“ einmal, der sichtbare Text vollständig; `require_admin()` zeigt seine Meldung einmal zwischen
  Titel und Hinweis; „Zur Startseite“ grün mit der Startseite der Rolle; `ROLLE_NICHT_VERFUEGBAR` ist die Vorgabe beider Prüfungen.
- `klicktest_rahmen` Teil `anmeldung` (neu): Anmeldung ohne Anmeldung und Sperrseite als Monteurin auf `/projects`, je 1440 × 900 und
  412 × 915, hell und dunkel -- `.ds-seite`, Grund `--ds-grund`, ein h1 in Archivo 30 px, Untertitel, Text in IBM Plex Sans, kein alter Kopf,
  kein waagrechter Bildlauf; Marke mit Schriftzug, Kachel 44 × 44 weiß, über dem Kopf; Anmeldung: Knopf grün, Fokus im Benutzernamen in
  `--ds-fokus`; Sperrseite: darunter nur der Hinweis, kein „nicht verfügbar“, „Zur Startseite“ grün 40 px nach `/mobil` (Klick öffnet
  `/mobil`); Kontrast in der Karte. 57 von 57.
- Betroffene Klicktests (Anmeldung, Sperrseite, Schriften, Beteiligte, Abnahme, Versandprotokoll, Navigation der Monteurin, neue Ordnung,
  Ersteinrichtung, Akzentfarbe, Feierabend, fremde Seite, Anmeldung abgelaufen): **15 von 15** wie erwartet (zu 4 zugleich, 1:59).
- **Gegenproben** (Marker `GEGENPROBE`, byte-genau zurück): alter Untertitel der Anmeldung (M1); allgemeine Meldung wieder unter dem
  Titel der Sperrseite (M2); Sperrseite ohne Bildmarke (M3); Anmeldung ohne `.ds-seite` (M4); Kachel der Marke in der Kartenfarbe statt
  weiß (M5) -- in pytest **5 von 5 rot** (FAILED; `test_v458`, M4 dazu `test_v441`), im Klicktest-Teil **5 von 5 rot** (53, 53, 49, 53,
  53 von 57).
- **Angepasste Erwartungen** (Regel 28):
  - `test_v441::UMGEZOGEN`: alt 41 Seiten; neu dazu die 2.
  - `test_v260::test_403_on_a_page_route_renders_access_denied_html_not_json`: alt „Diese Seite ist für deine Rolle nicht verfügbar“ im
    HTML; neu „Kein Zugriff auf diese Seite“.
  - `klicktest_beteiligte` („Monteur: Formularseite gesperrt“): alt „nicht verfügbar“ im Text der Seite; neu „Kein Zugriff auf diese Seite“.
  - `klicktest_ds_schriften`: alt „Schrift der Seite unverändert (keine neue Familie)“ -- kein Archivo/Plex in der Schrift von `body` --
    und „vorher nichts geladen“ (0 geladene Schriften); neu „Schrift der Seite IBM Plex Sans“ und „vorher nur die Familien der Seite
    geladen“ (nach `document.fonts.ready` genau Archivo und IBM Plex Sans). Die Anmeldung ist umgezogen, die Seite lädt die Schriften
    des Design-Systems selbst.

#### Festlegungen 1.9.27 (Bitte bestätigen)

1. **Bildmarke mit Schriftzug auf Seiten ohne Leiste** (`_marke.html`): Kachel 44 px weiß mit Rand, „DACHKONZEPTE“ / „Rödchen GmbH · ERP“
   in den Farben der Karte, über dem Seitenkopf -- heute Anmeldung und Sperrseite.
2. **Anmeldung**: Titel „Anmelden“, Untertitel „Melde dich mit deinem Benutzernamen an.“; „Anmelden“ bleibt der breite grüne Knopf unter
   den Feldern, keine Aktion im Kopf.
3. **Sperrseite**: Titel „Kein Zugriff auf diese Seite“; die allgemeine Meldung der Rollenprüfung entfällt, eine genauere steht einmal
   darunter; danach immer „Brauchst du sie, wende dich an eine Person mit den passenden Rechten.“; „Zur Startseite“ grüne Hauptaktion unter
   dem Text.
4. **Karten bleiben eckig** auf beiden Seiten, wie auf den übrigen umgezogenen Seiten (Ecken der Karten sind nicht Teil von Stufe 2).

### Punkt 5 (1.9.28): Hinweise ohne interne Dateien

- **„Benutzer und Zugriff“** (Warnung bei nur einem aktiven Administrator, `#soleAdminWarning`): bis dahin „Es gibt aktuell nur einen
  einzigen aktiven Administrator. Der Weg "Zweiten Faktor zurücksetzen" über diese Seite steht deshalb praktisch nicht zur Verfügung -- die
  eigenen, ausgedruckten Wiederherstellungscodes und das Notfallskript auf dem Server (siehe CLAUDE.md) sind die einzige Absicherung, falls
  das Telefon mit der Authenticator-App verloren geht.“ Jetzt: „Es gibt nur einen aktiven Administrator – den zweiten Faktor kann dir
  deshalb niemand über diese Seite zurücksetzen. Bewahre deine ausgedruckten Wiederherstellungscodes sicher auf und lege einen zweiten
  Administrator an. Geht das Telefon mit der Authenticator-App verloren und fehlen die Codes, kann den zweiten Faktor nur noch
  zurücksetzen, wer Zugang zum Server hat.“
- **Beim Durchsehen gefunden** (Suche über alle Vorlagen ohne Kommentare und alle Texte in `app/` außer Docstrings): der Hinweis zum
  Outlook-Kalender in den Einstellungen endete mit „(vollständige Anleitung: docs/archiv/modul-kalender-und-outlook-sync.md)“ -- jetzt
  „aufnehmen kann es, wer euer Microsoft 365 verwaltet“; die Meldung eines mit 403 abgelehnten Graph-Aufrufs
  (`app/outlook_calendar_sync.py`, angezeigt beim Abgleich) endete mit „siehe docs/archiv/…“ -- jetzt „das Postfach in die Gruppe
  ERP-Zugriff aufnehmen“. Der Befehl der geschlossenen Ersteinrichtung (`python scripts/erstes_konto.py <benutzername>`,
  `app/anmeldeschranke.py`) bleibt: er ist selbst, was zu tun ist.

#### Tests und Prüfung

- Neu `tests/test_v459_keine_internen_dateien.py` (9 Tests): keine Vorlage nennt im sichtbaren Text oder im Skript (ohne Kommentare
  `{# … #}`, `<!-- … -->`, `/* … */`, `// …`) CLAUDE.md, `docs/…`, `scripts/….py` oder `app/….py`; kein Text in `app/` ebenso, außer
  freistehenden Strings (Docstrings und Beschreibungen unter einer Zuweisung wie in `app/ai_types.py` -- nie angezeigt); Ausnahmen mit Grund
  nur der Befehl der Ersteinrichtung und die `ValueError` eines nicht eingetragenen Dokumenttyps in `app/document_frame.py` (Programmierfehler,
  die Oberfläche sieht nur die 500 ohne Text), jede Ausnahme muss es noch geben; der Hinweis auf „Benutzer und Zugriff“ sagt, was zu tun
  ist; Selbsttests des Wächters (findet in Text und Skript, lässt Kommentare und Adressen durch, freistehende Strings in Python).
- Vor der Änderung 3 von 9 rot (Vorlagen: `users.html`, `settings.html`; Meldungen: `app/outlook_calendar_sync.py`; Hinweis).
- **Gegenproben** (Marker `GEGENPROBE`, byte-genau zurück): „siehe CLAUDE.md“ wieder im Hinweis auf „Benutzer und Zugriff“ (N1);
  „docs/archiv/…“ wieder im Outlook-Hinweis der Einstellungen (N2); „siehe docs/archiv/…“ wieder in der Graph-Meldung (N3) -- in pytest
  **3 von 3 rot** (FAILED, `test_v459`; N1 dazu der Test des Hinweises).
- **Angepasste Erwartungen** (Regel 28): keine.

#### Festlegungen 1.9.28 (Bitte bestätigen)

1. **Kein sichtbarer Text und keine Meldung nennt eine interne Datei** (CLAUDE.md, `docs/…`, `scripts/….py`, `app/….py`), sondern sagt,
   was zu tun ist; Ausnahmen nur mit Grund: ein Befehl, der selbst die Handlung ist (Ersteinrichtung), und die Meldung eines
   Programmierfehlers an Entwickler, die die Oberfläche nie erreicht. Wächter über alle Vorlagen und `app/`.
2. **Mit umgestellt, obwohl nicht im Auftrag**: der Outlook-Hinweis in den Einstellungen und die Meldung eines abgelehnten Graph-Aufrufs
   (dieselbe Art Fehler, der Wächter hätte sie sonst als Ausnahme gebraucht).
3. **Wortlaut der Warnung** auf „Benutzer und Zugriff“: Codes sicher aufbewahren, zweiten Administrator anlegen; ohne Telefon und Codes
   nur noch über den Server -- ohne Namen des Notfallskripts.

### Punkt 6 (1.9.29): Abschluss Stufe 2

- **Wächter** `test_jede_seite_umgezogen_oder_aufgeschoben` (`tests/test_v441_rahmen_baustein.py`): jede Seite aus `seiten()` steht in
  `UMGEZOGEN` oder in `AUFGESCHOBEN`, keine in beiden, keine der Listen nennt eine Seite, die es nicht gibt; jede aufgeschobene mit einer
  Stufe von 3 bis 7 und einem Grund (mindestens vier Wörter). Eine aufgeschobene Seite trägt kein `.ds-seite` (das prüft weiter
  `test_umgezogen_heisst_ds_seite_am_body`: `.ds-seite` genau auf den Seiten in `UMGEZOGEN`).
- **Stand am Ende von Stufe 2**: 53 Seiten, davon 43 umgezogen, 10 aufgeschoben:

| Seite | Vorlage | Stufe | Grund |
|---|---|---|---|
| Einsätze | `mobil.html` | 4 | Startseite der Monteursansicht, die Stufe 4 als Ganzes gestaltet |
| Zeiterfassung der Monteure | `time_tracking_field.html` | 4 | gehört zur Monteursansicht |
| Stundenzettel | `field_timesheet.html` | 4 | gehört zur Monteursansicht |
| Projektmappe | `project_folder.html` | 5 | große Arbeitsseite mit Reitern, zusammen mit Auftrag und Kundenakte |
| Auftrag | `order.html` | 5 | große Arbeitsseite mit vielen Karten, zusammen mit Projektmappe und Kundenakte |
| Kundenakte | `customer.html` | 5 | große Arbeitsseite mit Reitern, zusammen mit Projektmappe und Auftrag |
| Kalender | `calendar.html` | 6 | Ansicht über eine Zeitachse, zusammen mit der Plantafel |
| Plantafel | `planning.html` | 6 | Ansicht über eine Zeitachse, zusammen mit dem Kalender |
| Neues Projekt | `project_form.html` | 7 | wird ein Dialog statt einer eigenen Seite |
| Neues Angebot | `quote_form.html` | 7 | wird ein Dialog statt einer eigenen Seite |

- Stufen und Zuordnung wie vorgegeben (Auftrag Runde 9, Punkt 6); die Gründe sind meine Kurzfassung. Mit Stufe 5 zieht auch der
  Versandverlauf (`_email_dispatch.html`, Links noch in `--accent`) um -- seine letzten Nutzer sind Projektmappe, Auftrag und Kundenakte.

#### Tests und Prüfung

- `test_v441`: neue Liste `AUFGESCHOBEN` (10 Seiten mit Stufe und Grund), neuer Wächter `test_jede_seite_umgezogen_oder_aufgeschoben`,
  Selbsttest `test_waechter_umgezogen_oder_aufgeschoben_findet` (drei erfundene Fälle: weder noch, beides, keine Seite).
- Ohne `AUFGESCHOBEN` (Stand vor 1.9.29) scheitert der Wächter mit „weder umgezogen noch aufgeschoben“ an genau den 10 Seiten der Tabelle.
- **Gegenproben** (Marker `GEGENPROBE`, danach zurück: Prüfsummen gleich bzw. Datei gelöscht): eine neue Seitenvorlage
  `gegenprobe_neue_seite.html` (O1, „weder umgezogen noch aufgeschoben“); „Neues Projekt“ in die Projektliste eingebunden -- keine Seite
  mehr, steht aber in `AUFGESCHOBEN` (O2, „keine Seite“; dazu zwei Strukturtests der Projektliste); Kalender mit `.ds-seite`, steht aber
  in `AUFGESCHOBEN` (O3, `test_umgezogen_heisst_ds_seite_am_body`) -- in pytest **3 von 3 rot** (FAILED).
- **Angepasste Erwartungen** (Regel 28): keine.

#### Festlegungen 1.9.29 (Bitte bestätigen)

1. **Stufe 2 ist abgeschlossen**, wenn jede Seite umgezogen oder mit Stufe und Grund aufgeschoben ist; eine neue Seite kommt umgezogen dazu
   oder in `AUFGESCHOBEN`.
2. **Gründe der aufgeschobenen Seiten** wie in der Tabelle oben (Kurzfassung nach den vorgegebenen Stufen).

### Runde 9 abgeschlossen: Endläufe, Bildvergleich, Beleg (Stand `f8da8c0`) -- Stufe 2 „Rahmen“ abgeschlossen

- **Endlauf** auf `f8da8c0` bei sauberer Arbeitskopie (vorher und nachher keine Änderung): volle Suite **6679 bestanden, 3 übersprungen,
  0 rot** (7:21); **Klicktests 80 von 80** wie erwartet (zu viert, 8:13), keine Wiederholung nötig.
- **Bildvergleich** Rundenstart `4527b7c` gegen `f8da8c0` (volle Bildgrundlage, je 298 Bilder, unmittelbar hintereinander, gleiche
  Chrome-Version): **207 gleich, 90 abweichend auf den Seiten der Runde, 1 weitere**:
  - Seiten der Runde: Anfragen, Arbeitsvorbereitung, Checkliste (Büro 4, Monteurin 8), Checklisten zum Auftrag (Büro 4, Monteurin 8), Objekt
    der Monteursansicht (Büro 4, Monteurin 8), Betriebsmittel der Monteurin 8, Einsatzbericht nur der Monteurin 14 (die vier Bilder des Büros
    gleich), Konto nur der Monteurin 8 (Büro gleich), Anmeldung 4, Sperrseite 8, Benutzer und Zugriff 4 (der Hinweis bei nur einem
    Administrator, Punkt 5). Ohne Abweichung: Stammdaten-Formular und Leistung (Punkt 1 ändert nur das Verhalten von „Abbrechen“) und die
    Einstellungen (der geänderte Outlook-Hinweis steht nicht im aufgenommenen Bereich).
  - **Die eine weitere**: Angebot, Büro, hell, 1440 px -- Rechteck 73 × 15 px (387 Pixel) im abgeschnittenen Text des Knopfs „+ Übernehmen“
    in der Leistungssuche. **Kein Befund der Runde, ein Zufall der Darstellung**: das Angebot je zweimal auf beiden Ständen aufgenommen
    (abwechselnd, `--nur angebot`) -- dasselbe Rechteck wechselt zwischen zwei Varianten, unabhängig vom Stand: hell liefert der Endstand
    beide (eine seiner Wiederholungen gleicht dem Rundenstart bis aufs Pixel), dunkel der Rundenstart beide (eine Wiederholung weicht genau
    in diesem Rechteck ab). Das Angebot ist in Runde 9 nicht geändert.
- **Nebenbefund** (alt, nicht behoben): im Angebot (LV-Editor, 1440 px) bricht in der Leistungssuche der Knopf „+ Übernehmen“ um, wird
  rechts abgeschnitten („Übernehm…“) und erzeugt einen waagrechten Bildlauf in der Karte. Schon auf `bee5363` (vor Runde 7, vor dem Umzug
  des Angebots in 1.9.18) so; der abgeschnittene Text ist auch die Stelle, an der die Kantenglättung zwischen zwei Läufen wechselt.
- **Bilder**: `bildgrundlage/rahmen_runde9_f8da8c0.zip` (16 Dateien): Stammdaten-Formular (Mitarbeiter), Leistung, Anfragen,
  Arbeitsvorbereitung, Checkliste und Checklisten zum Auftrag (Büro), Benutzer und Zugriff, Sperrseite als Fenster 1440 × 900 hell; Checkliste,
  Checklisten zum Auftrag, Objekt, Betriebsmittel, Einsatzbericht und Konto der Monteurin 1280 × 620 hell; die Anmeldung 1440 × 900 hell und
  dunkel. Der Hinweis bei nur einem Administrator ist in den Testdaten sichtbar (ein Admin).
- Commits der Runde: `ecff1f7` (1.9.23 Abbrechen fragt), `4ee72d0` (1.9.24 Anfragen und Arbeitsvorbereitung), `df8a4b0` (1.9.25
  Monteursseiten), `1168956` (1.9.26 Klicktest Mahnwesen), `c17fa57` (1.9.27 Anmeldung und Sperrseite), `817278c` (1.9.28 Hinweise ohne
  interne Dateien), `f8da8c0` (1.9.29 Abschluss Stufe 2).
- **Nebenbefund** aus einem Teillauf vor dem Commit von 1.9.26: `tests/test_v413_testlauf_parallel.py::test_pg_ein_testlauf_raeumt_zu_beginn_auf`
  scheiterte einmal in einem kleinen parallelen Lauf weniger Dateien und lief danach einzeln und in allen vollen Läufen grün -- vermutlich ein
  Wettlauf beim Aufräumen der Testschemas, wenn zwei Arbeitsprozesse fast gleichzeitig beginnen; nicht weiter untersucht.

## Nachtrag Stufe 2 (ab 1.9.30)

Vorgabe vom 22.10.2026 (übernommen wie gegeben): „Nachtrag Stufe 2 und Befund Stufe 4 „Monteurin“. Festlegungen 1.9.23 bis 1.9.29
bestätigt, außer 1.9.27 Nr. 4. Version weiter ab 1.9.30. A. Nachtrag Stufe 2: 1. Karten auf allen Seiten mit 12 px Ecken, im
Monteursrahmen 16 px (Entscheidung 2 der Stufe 2; ersetzt 1.9.27 Nr. 4). Bildvergleich: nur Ecken weichen ab. 2. CLAUDE.md: Ein Commit
läuft nur nach grünem Lauf; Befehle mit && verketten, nie mit ;. 3. test_v413::test_pg_ein_testlauf_raeumt_zu_beginn_auf: Ursache des
einmaligen Fehlschlags klären und ohne Zeitabhängigkeit machen. B. Befund Stufe 4, nichts am Programm ändern: […] Am Ende: volle Suite
und Klicktests auf sauberer Arbeitskopie für Teil A. Bericht je Punkt. Dazu als ZIP die Monteursseiten heute bei 1280 × 620 und
800 × 1100 und eine Seite mit den neuen Ecken vorher und nachher. Nicht pushen.“ (Teil B vollständig in `docs/archiv/befund-monteurin.md`.)

### Punkt A1 (1.9.30): Karten mit 12 px Ecken, im Monteursrahmen 16 px

- **Befund vorweg**: `.card` steht auf 44 Vorlagen, dazu rund 20 weitere Klassen mit „card“ im Namen; bis auf `.pv-karte` (Prüfvorlagen)
  und die Bausteine des Design-Systems (Menü „⋮“, Suchergebnisse: schon `--ds-ecke-karte`) hatte keine eine Ecke. Dieselbe Fläche
  (Kartengrund oder Rand) zeichnen viele Regeln ohne diesen Namen -- Kopf- und Formularkarten, Kennzahl-Kacheln, Spalten, Kästen in
  Karten, Hinweise, Dialoge. Wären nur die „card“-Klassen rund geworden, hätte die Projektmappe runde Karten mit eckigen Kästen darin
  gezeigt.
- **Was eine Karte ist** (`tests/test_v460_ecken_der_karten.py`): eine Regel, deren Ziel genau eine Karten-Klasse ist -- Name mit „card“
  oder „karte“, eine der Flächen in `KARTEN_OHNE_NAMEN` (63, je mit Grund) oder `dialog` -- und die eine Fläche zeichnet (umlaufender
  Rand oder ein Grund). Zustände (`:hover`) und Teile einer Karte (`.card h2`) zählen nicht. **Keine Karte** (`NICHT_KARTEN`, 41, je mit
  Grund): Knöpfe und Felder (eigene Ecke 10 px, nicht Teil dieses Punkts), Kennzeichen, Raster und Tafelteile (Monatsraster, Plantafel,
  Zeitstrahl, Kopf der Positionen), die Skizze der Dachfläche, Vorschaubilder, die Kachel der Bildmarke. Jede umrandete Fläche einer
  Vorlage (Ziel genau eine Klasse, ohne Leiste, Kopfzeile, Monteurskopf und Design-System) steht in einer der beiden Listen -- eine neue
  kommt dort hinein.
- **Ecke**: `border-radius: var(--ds-ecke-karte)` an jeder solchen Regel (180 Regeln in 55 Vorlagen, dazu `.pv-karte` mit schon vorhandener Ecke; per Skript mit derselben Erkennung
  wie der Wächter). Kein `overflow: hidden` -- der Inhalt der Karten hat Innenabstand; im Bildvergleich geprüft.
- **Monteursrahmen**: `_mobile_header.html` steht genau in den Seiten des Monteursrahmens (bei Einsatzbericht, Konto, Checkliste und
  Checklisten zum Auftrag nur für die Monteurin) und setzt in einem eigenen Block `:root{--ds-ecke-karte:var(--ds-ecke-tablet-karte)}` --
  keine Seite braucht eine Bedingung, keine Klasse am `<body>` (Festlegung 1.9.25 Nr. 1 bleibt). Damit ist im Rahmen alles 16 px, was
  `--ds-ecke-karte` nimmt, auch das Menü „⋮“ und das Kontomenü. Sonst setzt keine Vorlage einen `--ds-`-Wert, keine nimmt die Tablet-Ecke
  selbst (Wächter).
- **Anschluss** in `/mobil`: Hinweis „Offene Bedenken“ (`.concern-alert`, `border-top:none`) und Link „Checklisten zu diesem Auftrag“ hängen
  unter ihrer Einsatzkarte. Was darüber steht, ist unten eckig (`.assign-card:has(+ .concern-alert)` u. a.), der letzte Kasten nur unten
  rund (`0 0 var(--ds-ecke-karte) var(--ds-ecke-karte)`).

#### Tests und Prüfung

- Neu `tests/test_v460_ecken_der_karten.py` (8 Tests): jede Karte jeder Vorlage mit der Ecke (angeschlossen nur unten); jede umrandete
  Fläche eingeordnet; Karten auf mindestens 48 Seiten (Start, Aufgaben, /mobil, Formularseiten eingeschlossen); der Block im Monteurskopf;
  kein anderer `--ds-`-Wert in einer Vorlage, keine Tablet-Ecke außerhalb des Kopfs; Anschluss in `/mobil`; Selbsttests des Wächters.
- `klicktest_rahmen` Teil `ecken` (neu): Start, Projekte, Einstellungen, Rechnung, Stammdaten-Formular, Checkliste und Einsatzbericht im Büro
  (1440 × 900) mit 12 px; /mobil, Zeiterfassung, Stundenzettel, Checkliste, Einsatzbericht, Konto, Objekt und Betriebsmittel der Monteurin
  (1280 × 620) mit 16 px -- je oben und unten links, hell und dunkel; in /mobil die Einsatzkarte über dem Link unten 0, oben 16 px, der Link
  oben 0, unten 16 px. 92 von 92.
- **Gegenproben** (Marker `GEGENPROBE`, byte-genau zurück): Monteurskopf ohne den Block mit 16 px (P1); Widgets der Startseite ohne Ecke
  (P2); Einsatzkarte über Hinweis und Link unten rund (P3); Frage der Checkliste nimmt die Tablet-Ecke selbst (P4) -- in pytest **4 von 4
  rot** (FAILED; `test_v460`, P1 dazu `test_v272`), im Klicktest-Teil **4 von 4 rot** (74, 90, 90, 90 von 92).
- **Angepasste Erwartungen** (Regel 28):
  - `test_v272::test_seitenregeln_greifen_nicht_in_den_kopf`: alt nur der erste `<style>`-Block des Monteurskopfs (jede Regel mit zwei
    Klassen); neu dazu genau ein zweiter Block mit der einen Regel `:root{--ds-ecke-karte:var(--ds-ecke-tablet-karte)}` (Aufbau erweitert,
    die Prüfung des ersten Blocks unverändert).

#### Festlegungen 1.9.30 (Bitte bestätigen)

1. **Karte** = jede Fläche mit Rand oder Grund aus einer Karten-Klasse (Name mit „card“/„karte“ oder in `KARTEN_OHNE_NAMEN`: Kopf- und
   Formularkarten, Kennzahl-Kacheln, Spalten, Einträge und Kästen in Karten, Hinweiskästen, Ablage- und Leerflächen, Dialoge,
   Aufklappmenüs); **keine Karte**: Knöpfe und Felder, Kennzeichen, Raster und Tafelteile, Skizze, Vorschaubilder, Kachel der Bildmarke.
2. **Auch die aufgeschobenen Seiten** (Stufen 4–7) bekommen die Ecken jetzt („auf allen Seiten“).
3. **16 px über den Monteurskopf**: `_mobile_header.html` legt `--ds-ecke-karte` auf die Tablet-Ecke; alles, was diesen Wert nimmt, ist im
   Rahmen 16 px -- auch Menü „⋮“, Kontomenü und Suchergebnisse.
4. **Angeschlossene Kästen** (Hinweis und Link unter einer Einsatzkarte) nur unten rund, die Karte darüber unten eckig.
5. **Kein `overflow: hidden`** an Karten.

### Nachtrag Stufe 2 abgeschlossen: Endlauf, Bildvergleich, Beleg (Stand `6d81016`)

- **Commits**: `e495046` (1.9.30 Karten mit Ecken), `f94afec` (1.9.31 Testschemas ohne Zeitfenster), `6d81016` (1.9.32 Commit nur nach
  grünem Lauf). Vor jedem Commit lief die volle Suite auf genau dem Stand, der committet wurde (Regel 15, seit 1.9.32 ausdrücklich), bei
  1.9.30 zweimal (vor und nach der Doku).
- **Endlauf** auf `6d81016` bei sauberer Arbeitskopie (vorher und nachher keine Änderung): volle Suite **6687 bestanden, 3 übersprungen,
  0 rot** (7:14); **Klicktests 80 von 80** wie erwartet (zu viert, 8:06), keine Wiederholung nötig.
- **Bildvergleich** Stand vor Teil A (`cb27ba5`, Worktree) gegen `6d81016` (volle Bildgrundlage, je 298 Bilder, unmittelbar hintereinander,
  gleiche Chrome-Version): **alle Bildgrößen gleich** (kein Layout verschoben); 8 Bilder gleich (Prüfvorlagen -- hatten die Ecke schon --
  und `/mobil` des Büros ohne Karte im Bild); **258 weichen nur in Eckzwickeln ab** (jede zusammenhängende Abweichung höchstens 18 × 18 px,
  automatisch geprüft); **32 zusätzlich entlang ganzer Ränder** -- alle aus den Ecken: gestrichelte Ränder verteilen ihre Striche entlang
  des gerundeten Rands neu (leere Listen, „Positionen ohne Titel“ im Angebot), Kästen mit verschieden breiten oder halbtransparenten Rändern
  werden mit Ecke als Pfad gezeichnet (Fragen der Checkliste mit Pflichtstrich links, Hinweis am Auftrag, Erfolgskasten im Backoffice), und
  Schatten folgen der Ecke (Kontomenü im Monteursrahmen 16 statt 12 px, Fußleiste der Checkliste). Alle 2842 Flecken dieser 32 Bilder
  eingeordnet: 2722 Eckzwickel, 34 Randlinien (höchstens 3 px), 86 Rahmen um einen Kasten oder Schattenzonen an Ecken (bis 36 px) --
  stichprobenweise je Art im Bild nachgesehen (Checkliste, Angebot, Backoffice, Auftrag, Zeiterfassung, Kontomenü, Fußleiste). Sichtbar
  ändern sich nur die Ecken.
- **Bilder**: `bildgrundlage/nachtrag_stufe2_6d81016.zip` (20 Dateien): die neun Seiten der Monteurin als Fenster 1280 × 620 und
  800 × 1100 hell (`monteursseiten_heute/`), die Projektmappe 1440 × 900 hell vorher (`cb27ba5`) und nachher (`ecken_vorher_nachher/`).
- **Teil B**: Befund Stufe 4 „Monteurin“ in `docs/archiv/befund-monteurin.md` (nur Befund, nichts am Programm geändert).

## Stufe 4 „Monteurin“ (ab 1.9.33)

Grundlage: `docs/archiv/befund-monteurin.md` (Befund vom 22.10.2026, Entwurf von Tobias freigegeben). Plan der Stufe:

| Runde | Inhalt |
|---|---|
| R1 | **Regeln** (Server und kleinste Anzeige): Zugriff auf die Einsätze nur für die Rollen der Monteursansicht, vergessener Feierabend („Ende nachtragen“, nichts automatisch), eine Pausenregel für Stopp und Nachtrag, Pflichten des Einsatzberichts vor jeder Unterschrift, Pflichtpunkte sichtbar und nicht löschbar, im PDF nur die Zeiten des Einsatzes |
| R2 | **Heute** -- die Karte oben auf /mobil (Zeitstatus, heutiger Einsatz, nächster Schritt) |
| R3 | **Meine Zeiten und Nachtragen** -- die Zeiterfassung der Monteurin neu |
| R4 | **Einsatzbericht in 5 Schritten** und Tablet-Ziele (Fingermaße) |
| R5 | **Büro**: Einsätze, Zeiterfassung der Monteure, Stundenzettel aus Sicht des Büros |

Vorgabe R1 vom 22.10.2026 (übernommen wie gegeben, gekürzt um die Testliste): „Stufe 4 · Runde 1 – Regeln für die Monteurin (Server +
Minimal-Anzeige). […] Diese Runde baut nur die Regeln; die neuen Oberflächen kommen ab Runde 2. […] 1. Zugriff – GET /api/field-view/today
nur für Rollen mit /mobil, sonst 403. Büro-Nutzer werden auf /mobil nach 19 Uhr nicht mehr abgemeldet (Ursache aus dem Befund beheben).
2. Vergessener Feierabend – nichts automatisch […] 3. Nachtragen – Dieselbe Pausenregel wie beim Feierabend – eine gemeinsame Funktion,
keine Kopie. Antwort enthält anwesend, Pause, gebucht. „Zusätzliche Pause“ bleibt Mindestpause. 4. Einsatzbericht – Die Pflichten, die heute
erst nach beiden Unterschriften geprüft werden, vor jeder Unterschrift prüfen. […] PDF: nur Zeiten dieses Einsatzes […]“

### R1 Punkt 1 (1.9.33): Zugriff

- **Befund** (`docs/archiv/befund-monteurin.md`, Auffälligkeit 24): `GET /api/field-view/today` stand ohne Rollenprüfung in
  `ROLE_AUDIT_EXEMPT` und meldete ab der Feierabend-Uhrzeit jeder angemeldeten Rolle 401 „feierabend“; `/mobil` schickte darauf
  `POST /api/field-view/feierabend` (ab Rolle `field`, also auch für das Büro) -- die Sitzung des Büros war beendet.
- **Änderung**: `MOBIL_ROLLEN = {field}` und `hat_monteursansicht()` in `app/permissions.py` (wer `/mobil` als Arbeitsplatz hat -- die
  Startseite der Rolle). `today` und der Feierabend-POST über `require_role(*MOBIL_ROLLEN)` mit der Meldung „Die Einsätze gibt es nur in der
  Monteursansicht.“; die Rollenprüfung läuft vor der Feierabend-Prüfung im Rumpf. `today` aus `ROLE_AUDIT_EXEMPT` gestrichen (jetzt mit
  Rollenprüfung). `/mobil` zeigt bei 403 die Meldung einmal in „Heutige Einsätze“ statt in fünf Listen.

#### Tests und Prüfung

- Neu `tests/test_v461_monteurin_zugriff.py` (7 Tests, echte Anmeldeschranke): Büro – Auftrag, Büro – Finanzen und Admin bekommen `today`
  403 mit Meldung (Angriff) / die Monteurin 200 (Gegenprobe); das Büro um 20 Uhr: GET ohne „feierabend“, POST 403, Sitzung gilt weiter
  (Angriff) / die Monteurin wird um 20 Uhr weiter abgemeldet (Gegenprobe).
- **Gegenproben** (Marker `GEGENPROBE`, byte-genau zurück): `today` ohne Rollenprüfung (Q1) -- 4 rot; Feierabend-POST für jede Rolle (Q2) --
  1 rot (FAILED).
- **Angepasste Erwartungen**: keine.

#### Festlegungen 1.9.33 (Bitte bestätigen)

1. **Rollen der Monteursansicht** = die Rolle `field` (`MOBIL_ROLLEN`); auch Admin bekommt `today` und den Feierabend nicht.
2. **Die Seite `/mobil` bleibt für jede Rolle offen** (wie bisher, Bildgrundlage nimmt sie auch fürs Büro auf); das Büro sieht dort die
   Meldung statt der Einsätze -- die übrigen Abschnitte (Termine, Wartungen) bleiben, wie sie sind (R5).
3. **Auch der Feierabend-POST** nur für diese Rollen (sonst bliebe die Ursache über einen direkten Aufruf bestehen).

### R1 Punkt 3 (1.9.34): Nachtragen nach derselben Pausenregel

Vor Punkt 2 gebaut, weil „Ende nachtragen“ dieselbe Pausenregel und dieselben Antwortfelder braucht.

- **Befund** (Befund Stufe 4, B2): `stop_timer()` rechnete `max(eingegeben, automatisch)`, der Router für Einzel- und Gruppen-Stopp noch
  einmal je für sich (`automatic_break_minutes_for_timer()`), `stop_group_timer()` ein drittes Mal; der Nachtrag speicherte die Pause nur.
  Die Zeiterfassung der Monteurin rechnete bei Von/Bis die Stunden im Browser (Bis − Von) und buchte sie ohne Pause.
- **Eine Funktion**: `pause_nach_zeitregel(db, employee_id, anwesend, am, mindestpause)` = `max(mindestpause, automatische Pause des
  Arbeitszeitmodells für die Anwesenheit am Tag)`; dazu `anwesend_stunden(beginn, ende)` und `nachtrag_nach_zeitregel()` (Von/Bis →
  anwesend, Pause, netto). `stop_timer()`, `stop_group_timer()` (je Mitglied nach seinem Modell; der Parameter `break_minutes_by_employee`
  entfällt) und der Nachtrag rufen sie; der Router rechnet keine Pause mehr. Wächter: unter `app/` ruft außerhalb von
  `work_time_models.py` nur `pause_nach_zeitregel()` die automatische Pause auf.
- **Nachtrag**: `POST /api/time-entries` nimmt entweder `hours` (gebuchte Arbeitszeit, netto -- unverändert) oder `von` und `bis` (die
  Anwesenheit am `work_date`; der Server zieht die Pause nach der Regel ab, speichert Beginn und Ende als Nachweis, rundet wie bisher).
  `create_manual_entry()` nimmt die Stunden immer, wie sie kommen (bis dahin rechnete es sie aus Beginn und Ende selbst, ohne Regel). Die
  Zeiterfassung der Monteurin schickt bei „Von / Bis“ jetzt Von und Bis; „Ändern“ schickt weiter die Stunden.
- **Antwort**: jede Zeitbuchung (`TimeEntryOut`) trägt `anwesend` (Stunden vor der Pause: aus Beginn und Ende, ohne beide gebucht + Pause),
  `pause` (Minuten) und `gebucht` (Stunden); bei laufender Zeit leer. Nach dem Nachtragen zeigt die Zeiterfassung der Monteurin „Nachgetragen:
  gebucht … h · anwesend … h · Pause … min“.

#### Tests und Prüfung

- Neu `tests/test_v462_nachtrag_pausenregel.py` (11 Tests): 06:45–16:00 → anwesend 9,25, Pause 45, gebucht 8,50 (Angriff auf die alte
  Rechnung) / 4 h als Dauer und als 07:00–11:00 → kein Abzug (Gegenprobe); 9 h als Dauer bleiben 9 h; Mindestpause 20 → 45, 60 → 60; Von ohne
  Bis, Bis vor Von, ohne beides 422; der Stopp 06:45–16:00 ergibt dieselben Werte; Wächter „eine Pausenregel“.
- Bestehende Zeiterfassungs-Tests unverändert grün (Stopp und Gruppen-Stopp rechnen wie vorher).
- **Gegenproben** (Marker `GEGENPROBE`, byte-genau zurück): Stopp ohne Regel (R1) -- 2 rot; Nachtrag ohne Abzug (R2) -- 3 rot; Summe statt
  Mindestpause (R3) -- 2 rot; zweite, gleich rechnende Stelle im Stopp (R4) -- der Wächter rot. Alle FAILED.
- **Angepasste Erwartung** (Regel 28): `test_v424::ABGLEICH`, Eintrag `time_tracking.html id=manualHours`: alt ohne Grenze im Code; neu
  `code={"pflicht": True}` mit Beleg „Bitte die Dauer oder Von und Bis angeben.“ in `app/schemas.py` -- die Stunden sind im Schema optional
  (ein Nachtrag mit Von/Bis braucht keine), ohne Von/Bis verlangt sie der Validator.

#### Festlegungen 1.9.34 (Bitte bestätigen)

1. **Die Regel gilt, wo die Anwesenheit eingegeben wird**: Timer-Stopp, Ende nachtragen, Nachtrag mit Von/Bis. **Eine Dauer ist gebuchte
   Arbeitszeit (netto)** und wird nicht gekürzt -- wie „Stunden (netto)“ im Büro (sonst zöge der Server dem Büro die Pause doppelt ab).
2. **Mindestpause**: die eingegebene Pause (auch die Standardpause aus den Zeitregeln, die die Monteurin beim Nachtragen mitschickt) gilt als
   Mindestpause, die Regel kann sie erhöhen, nie senken; keine Summe.
3. **Rundung** wie bisher: nach Abzug der Pause auf die Rundung der Zeitregeln (Nachtrag und Einzel-Stopp; Gruppen-Stopp und
   Gruppen-Nachtrag weiter ohne Rundung -- Befund, nicht Teil dieser Runde).
4. **Der Kolonnen-Nachtrag** hat nur „Stunden je Person“ (eine Dauer) und bleibt, wie er ist.
5. **anwesend ohne Beginn und Ende** (eine Dauer) = gebucht + Pause.

### R1 Punkt 2 (1.9.35): vergessener Feierabend

- **Befund** (Befund Stufe 4, B2): `stop_timer()` nahm jedes Ende nach dem Start -- der Stopp am nächsten Morgen buchte die Zeit auf den
  Starttag bis jetzt (über 24 h, Pause nach der Regel). `start_timer()` meldete bei jeder laufenden Zeit „läuft bereits“, ohne zu sagen, seit
  wann; `/mobil` und die Zeiterfassung zeigten eine Uhr mit 25 Stunden. Ein Monat ließ sich mit einer laufenden Zeit abschließen (siehe unten).
- **Offene Zeit**: `laeuft_seit_frueher(row)` -- läuft, Start an einem früheren Tag (Berliner Datum, `berlin_today()`). `TimeEntryOut` trägt
  `laeuft_seit_frueher`; `GET /api/field-view/today` liefert `offene_zeit` (`offene_zeit_info()`: ID, Start, Tag, Zeitart mit Namen aus der
  Optionsgruppe, Auftragsnummer, ob Gruppe, ob sie selbst schließen darf) oder `null`. Nichts geschieht von selbst.
- **Stopp**: `POST /api/time-entries/{id}/stop` und `POST /api/time-entry-groups/{id}/stop` lehnen eine offene Zeit von früher mit 409 ab
  („Diese Zeit läuft seit dem … – bitte „Ende nachtragen“ (Ende am Starttag) statt stoppen.“) -- nach der Rechte- und Abschlussprüfung (die
  Monteurin im abgeschlossenen Monat sieht weiter die Meldung des Abschlusses). Eine heute gestartete Zeit stoppt wie bisher.
- **Ende nachtragen**: `POST /api/time-entries/{id}/ende-nachtragen` (`TimeEndeNachtragen`: `ende`, `pause_minuten` 0–720). Prüfungen der
  Reihe nach: unbekannt 404; nicht die eigene Zeit und nicht `darf_zeit_fuer_andere_buchen()` 403 „Du darfst diese Zeit nicht schließen.“;
  schon geschlossen 409; seit heute 409 „… bitte normal stoppen.“; Monteurin und Monat des Starttags abgeschlossen 403 „Monat abgeschlossen –
  das Büro schließt die Zeit.“; sonst `_require_open_period()` wie bisher (nur Admin); laufende Gruppe: nur wer sie gestartet hat und noch
  Kolonnenführer ist (`_noch_kolonnenfuehrer()`), oder nach `darf_zeit_fuer_andere_buchen()`, sonst 403 „Die Gruppenzeit schließt der
  Kolonnenführer.“. Dann `ende_nachtragen()`: Ende am Starttag (422 „Das Ende muss am Starttag liegen (…).“), nach dem Start (422 „Das Ende
  muss nach dem Start liegen (… Uhr).“); eine laufende Gruppe über `stop_group_timer()` für alle, sonst `stop_timer()` -- beide mit
  `pause_nach_zeitregel()` (1.9.34); der Einzelfall rundet wie der Einzel-Stopp. Ein Ende mit Zeitzone rechnet der Server in Ortszeit um.
- **Start**: `start_timer()` wirft `OffeneZeit` (409): „Die Zeit vom … läuft noch – zuerst das Ende nachtragen, dann neu starten.“; gehört sie
  zu einer laufenden Gruppe eines anderen: „Die Gruppenzeit vom … läuft noch – das Ende trägt der Kolonnenführer nach, dann kannst du neu
  starten.“ Der Gruppen-Start nennt bei belegten Personen „(offen seit TT.MM.)“.
- **Verlauf**: jede Änderung an `TimeEntry` steht im Änderungsverlauf mit dem Namen des Kontos (`AuditLog.actor_name` aus der
  Anmeldeschranke) -- schließt ein Admin, steht er dort.
- **Anzeige (Minimal)**: `/mobil` oben eine Karte (`.zeit-offen-karte`, Ecke `--ds-ecke-karte`) „Deine Zeit läuft noch seit <Tag>, <Uhrzeit>
  Uhr“ mit Zeitart, Auftrag und „Ende nachtragen →“ zur Zeiterfassung (darf sie nicht selbst schließen: „Das Ende trägt der Kolonnenführer nach
  – zur Zeiterfassung →“). Zeiterfassung der Monteurin und im Büro: statt Uhr und „Zeit stoppen“ der Hinweis „Die Zeit vom … läuft noch (seit
  … Uhr)“, Feld „Ende an diesem Tag“ (Uhrzeit), „Zusätzliche Pause (Min.)“ und „Ende nachtragen“; danach „Ende nachgetragen: gebucht … h ·
  anwesend … h · Pause … min“. „Schnell starten“ bleibt bei der Monteurin sichtbar und zeigt die Meldung des Servers; im Büro meldet die Seite
  die offene Zeit selbst.

#### Was gilt (nur berichtet, nichts geändert)

- **Monat abschließen, während eine Zeit läuft**: geht. `set_time_lock()` (`app/time_backoffice.py:66`) prüft keine laufenden Zeiten. Die
  Zeit bleibt laufend mit einem Starttag im abgeschlossenen Zeitraum; danach schließt sie nur ein Admin (Stopp und „Ende nachtragen“ prüfen
  den Abschluss).
- **Büro im abgeschlossenen Monat**: unverändert -- jede Änderung im abgeschlossenen Zeitraum nur ein Admin (`_require_open_period()`);
  Büro – Auftrag und Büro – Finanzen schließen dort auch die eigene Zeit nicht. Fremde Zeiten schließen sie nirgends
  (`darf_zeit_fuer_andere_buchen()` = nur Admin). „Das Büro schließt die Zeit“ heißt heute also: ein Admin.

#### Tests und Prüfung

- Neu `tests/test_v463_ende_nachtragen.py` (25 Tests): today nennt die offene Zeit / ohne bei heute gestarteter; Stopp am nächsten Morgen
  409, Zeit läuft weiter (Angriff) / heute gestartet 200 (Gegenprobe); Gruppen-Stopp am nächsten Morgen 409; Ende vor dem Start, gleich dem
  Start, am Folgetag 422 (Angriff) / 16:00 am Starttag: gebucht 8,50 h, Pause 45 min, anwesend 9,25 h (Gegenprobe); Mindestpause 60; zweimal
  schließen 409; heute gestartet über „Ende nachtragen“ 409; Start mit offener Zeit 409 mit Meldung / neben heute laufender Zeit „läuft
  bereits“ / nach dem Nachtragen 200; Monteurin schließt Toms Zeit 403, Büro – Finanzen und Büro – Auftrag 403 (Angriff) / Admin 200, im
  Verlauf „Admin Anna“ für Ende und Status (Gegenprobe); Ex-Kolonnenführerin 403 (Angriff), Mitglied 403 und sein Start nennt den
  Kolonnenführer / Kolonnenführerin schließt die ganze Gruppe, je Person 45 min und 8,50 h (Gegenprobe); Monteurin im abgeschlossenen Monat 403
  mit der Meldung / Admin 200; `laeuft_seit_frueher()` nach Berliner Datum.
- Neuer Klicktest `scripts/klicktest_monteurin_regeln.py` (19 Prüfungen): Mia 412 px dunkel -- Hinweis in `/mobil` (16 px Ecke, kein
  waagrechter Bildlauf), offene Anzeige in der Zeiterfassung, Start abgelehnt mit Meldung, „Bitte das Ende angeben.“, Ende 06:00 mit Meldung des
  Servers, 16:00 gebucht mit Pause, neu gestartet; Anna 1400 px hell -- Toms offene Zeit, 15:30 gebucht (8,25 h, 30 min), Verlauf. Beim ersten
  Lauf war eine Prüfung rot: meine Erwartung für 15:30 (8,00 h, 45 min) war falsch gerechnet (8,75 h anwesend liegen unter 9 h), korrigiert auf
  8,25 h und 30 min -- so rechnet der Server.
- **Gegenproben** (Marker `GEGENPROBE`, byte-genau zurück, alle FAILED): Stopp vom Vortag erlaubt (S1) -- 2 rot; Ende am Folgetag (S2) -- 1;
  Start trotz offener Zeit (S3) -- 2; Gruppenzeit ohne Kolonnenführer-Kennzeichen (S4) -- 1; Monteurin im abgeschlossenen Monat (S5) -- 1;
  „Ende nachtragen“ schließt nur die eigene Zeit der Gruppe (S6) -- 1; today ohne offene Zeit und Seite ohne offene Anzeige (S7) -- 1 Test und
  5 Prüfungen des Klicktests rot.
- **Angepasste Erwartungen** (Regel 28):
  - `test_v100::test_timer_start_stop_computes_net_hours_and_prevents_parallel_timer`: alt Meldung „läuft bereits“ beim zweiten Start; neu
    „läuft noch – zuerst das Ende nachtragen“ -- die Zeit begann am 07.09.2026, vor heute, ist also eine offene Zeit von früher (der Fall
    „heute schon gestartet“ steht neu in `test_v463`).
  - `test_v300::test_field_cannot_stop_a_timer_that_runs_in_the_locked_period`: alt Admin stoppt die Zeit im abgeschlossenen Zeitraum (200);
    neu Admin-Stopp 409, Admin „Ende nachtragen“ 200 -- die Zeit läuft seit einem früheren Tag. Die Prüfung der Monteurin (403) unverändert.

#### Festlegungen 1.9.35 (Bitte bestätigen)

1. **„Früherer Tag“** = Starttag vor dem heutigen Berliner Datum (`berlin_today()`); eine Nachtschicht über Mitternacht gilt damit am Morgen
   als offen und wird über „Ende nachtragen“ am Starttag geschlossen (ein Ende nach Mitternacht ist so nicht buchbar -- heute kein Fall).
2. **Auch ein Admin stoppt eine Zeit von früher nicht** -- der Stopp lehnt für jede Rolle ab, geschlossen wird nur über „Ende nachtragen“
   (eine Regel für alle, kein 24-h-Stopp durchs Büro).
3. **Reihenfolge der Ablehnungen**: Rechte und Abschluss vor „seit früher“ -- die Monteurin im abgeschlossenen Monat sieht beim Stopp die
   Meldung des Abschlusses, bei „Ende nachtragen“ „Monat abgeschlossen – das Büro schließt die Zeit.“
4. **Im abgeschlossenen Monat** gilt für das Büro die bisherige Meldung (`_require_open_period()`, nur Admin); die neue Meldung nur für die
   Monteurin.
5. **Gruppenzeit**: „Ende nachtragen“ an der eigenen Zeit einer laufenden Gruppe schließt die ganze Gruppe (wie der Gruppen-Stopp), erlaubt
   nur der Kolonnenführerin, die sie gestartet hat und es noch ist, oder einem Admin; ein Mitglied schließt seine Zeit nicht einzeln (anders als
   beim Stopp am selben Tag) und kann bis dahin nicht neu starten -- die Meldung sagt es.
6. **Rundung**: der Einzelfall rundet nach den Zeitregeln wie der Einzel-Stopp, die Gruppe nicht (wie der Gruppen-Stopp; Festlegung 1.9.34
   Nr. 3).
7. **Uhrzeit statt Datum und Uhrzeit**: die Oberfläche fragt nur die Uhrzeit („Ende an diesem Tag“), das Datum ist der Starttag.
8. **„Schnell starten“ bleibt bei offener Zeit sichtbar** (Monteurin): der Start zeigt die Meldung des Servers; bis Runde 2 keine eigene
   Sperre im Browser.
9. **`offene_zeit` in today** nennt nur Start, Tag, Zeitart, Auftragsnummer und zwei Kennzeichen (Gruppe, selbst schließen) -- keine Inhalte
   darüber hinaus (Datengrenze der Monteurin).

### R1 Punkt 4 (1.9.36): Einsatzbericht – „Noch offen“ vor jeder Unterschrift

- **Befund** (Befund Stufe 4, B3): `sign_report()` prüfte die Pflichten (seit 1.2.16 Pflichtpunkte, seit 1.2.17 negatives Ergebnis ohne Mangel,
  Mangel ohne Foto, zurückgestellt ohne Wiedervorlage) erst im Aufruf mit beiden Unterschriften -- nach der Prüfung der Bilder, mit
  Meldungen wie „3 Pflichtpunkt(e) sind noch nicht beantwortet.“ (400). Monteurin und Kunde hatten dann schon unterschrieben. Ein
  Rapportbericht mit ausdrücklich gewählter Prüfvorlage bekam Pflichtpunkte, aber die Seite zeigte keine Prüfpunkte (`hasInspectionSection()`
  las die Spalte `inspection_template_id`, die `create_report()` seit 1.2.22 nicht mehr schreibt) -- die Pflicht war unsichtbar. Jeder
  Prüfpunkt, auch ein Pflichtpunkt, ließ sich im Entwurf löschen.
- **Eine Liste**: `noch_offen(report)` -- dieselben vier Pflichten, keine neuen, in dieser Reihenfolge, je ein Eintrag mit dem Namen des
  Prüfpunkts bzw. der Kurzfassung des Mangels („Pflichtpunkt „…“ beantworten“, „Mangel zum Prüfpunkt „…“ erfassen (negatives Ergebnis)“,
  „Foto zum Mangel „…“ aufnehmen“, „Wiedervorlagedatum zum zurückgestellten Mangel „…“ angeben“). `sign_report()` wirft `NochOffen` (mit
  der Liste) vor der Prüfung der Bilder; der Router prüft sie vor dem Dekodieren der Unterschriften und antwortet 409
  `{"detail": "Noch offen: a; b", "offen": [a, b]}`. `GET /api/service-reports/{id}/noch-offen` → `{"offen": [...]}` (Ersteller-Prüfung wie
  jeder Bericht-Endpunkt; unterschrieben: leer). `ServiceReportOut` trägt `noch_offen` (nur im Entwurf).
- **Vor jeder Unterschrift**: `openSignPanel()` und der Schritt „Weiter“ zum Kunden fragen die Liste über `nochOffenPruefen()` -- erst nach
  `nachDemSpeichern()` (neu im Baustein `_speichern.html`: wartet auf jedes laufende und wartende Speichern der Seite, speichert
  zurückgehaltene Eingaben vorher), damit der Server den gespeicherten Stand prüft. Ist sie nicht leer, öffnet die Unterschrift nicht bzw. geht
  nicht zum Kunden weiter; die Liste steht als „Noch offen vor der Unterschrift:“ unter den Knöpfen des Berichts (schon beim Laden aus
  `noch_offen` des Berichts).
- **Pflichtpunkte bleiben**: `delete_inspection_item()` lehnt einen Pflichtpunkt ab (`PflichtpunktGeschuetzt`, 409 „Ein Pflichtpunkt lässt sich
  nicht löschen.“), der Knopf „×“ fehlt dort. Von Hand ergänzte Punkte sind nie Pflicht (die Seite setzt `required` nicht) -- „Pflichtpunkt“
  heißt also: aus der Prüfvorlage. „Neu erzeugen“ und „Abgleich“ bauen aus der Vorlage und bleiben, wie sie sind.
- **Rapport mit Vorlage**: `hasInspectionSection()` erkennt die Vorlage zusätzlich an der Dachfläche (`roof_areas[].inspection_template_id`).

#### Tests und Prüfung

- Neu `tests/test_v464_noch_offen.py` (10 Tests): Rapport mit Vorlage trägt sie an der Dachfläche (vier Pflichtpunkte); Bericht und GET nennen
  die vier Pflichtpunkte mit Namen; Unterschrift mit einem offenen Pflichtpunkt 409, genau dieser Punkt in Liste und Meldung, Bericht bleibt
  Entwurf (Angriff) / alles beantwortet: unterschrieben, nichts offen (Gegenprobe); Pflichten vor den Bildern (kaputte Unterschrift + offene
  Pflicht → 409); alle vier Pflichten mit Namen nacheinander; Pflichtpunkt löschen 409 (Angriff) / freier Punkt aus der Vorlage und von Hand
  ergänzt 200 (Gegenprobe); unterschriebener Bericht ohne Liste; Seite: Prüfung vor beiden Unterschriften nach `nachDemSpeichern()`, kein
  „×“ am Pflichtpunkt, Vorlage an der Fläche.
- `scripts/klicktest_monteurin_regeln.py` um den Einsatzbericht ergänzt (27 Prüfungen): Mia 412 px dunkel -- Knopf „Prüfpunkte“ am Rapport,
  Liste „Noch offen vor der Unterschrift“ mit vier Pflichtpunkten, Pflicht mit „*“ ohne „×“, frei mit „×“, „Unterschreiben“ öffnet nicht,
  Pflichtpunkt löschen 409, beantwortet: Liste weg, Unterschrift öffnet.
- **Gegenproben** (Marker `GEGENPROBE`, byte-genau zurück, alle FAILED): Unterschrift ohne Prüfung (N1) -- 8 rot; Pflichtpunkt löschbar (N2) --
  1; noch-offen meldet nichts (N3) -- 1; Seite öffnet trotz offener Pflichten (N4) -- 1 Test, 1 Prüfung des Klicktests; alte Erkennung der
  Vorlage und „×“ am Pflichtpunkt (N5) -- 1 Test, 2 Prüfungen des Klicktests.
- **Angepasste Erwartungen** (Regel 28):
  - `test_v213::test_sign_report_blocks_on_open_required_items_and_names_count_then_succeeds`: alt „4“ bzw. „1“ in der Meldung (Anzahl); neu
    `NochOffen.offen` mit vier Einträgen, Meldung beginnt mit „Noch offen: Pflichtpunkt „“, bzw. genau der letzte Pflichtpunkt mit Namen.
  - `test_v213::test_router_endpoints_generate_items_and_reject_open_required_via_http`: alt 400 und „\d+ Pflichtpunkt“; neu 409, „Noch
    offen: Pflichtpunkt „…“, `offen` mit vier Einträgen.
  - `test_v214::test_router_endpoints_create_finding_and_reject_sign_without_photo`: alt 400 und „Foto“ in der Meldung; neu 409 und genau
    „Noch offen: Foto zum Mangel „Kaputt“ aufnehmen“.
  - `klicktest_abschliessen` (Aufbau, dieselben 19 Prüfungen und Soll-Werte): der Pflichtpunkt ist vorab beantwortet („vorher“), geändert
    wird, während der Kunde unterschreibt (bis 1.9.35 vor dem Öffnen der Unterschrift, mit unbeantwortetem Pflichtpunkt -- das lässt die
    Prüfung jetzt nicht mehr zu); „Scheitern“ löscht einen freien Punkt (ein Pflichtpunkt ist nicht mehr löschbar); `_unterschreiben()`
    wartet auf die geöffnete Unterschrift und den Schritt des Kunden statt fester Pausen.

#### Festlegungen 1.9.36 (Bitte bestätigen)

1. **„Vor jeder Unterschrift“** = vor der Unterschrift des Monteurs (Öffnen) und vor der Übergabe an den Kunden („Weiter“), jeweils über
   `GET …/noch-offen`; beim Absenden prüft der Server ein drittes Mal (409). Die Unterschriften bleiben ein Aufruf (getrennte Aufrufe sind
   Runde 4).
2. **Status 409** für „Noch offen“ (Zustand des Berichts), mit `offen` als Liste neben `detail`; die übrigen Ablehnungen der Unterschrift
   (Bild, Name, schon unterschrieben) bleiben 400.
3. **Die Prüfung wartet auf das Speichern der Seite** (`nachDemSpeichern()`): sonst meldete sie einen gerade beantworteten Punkt als offen.
4. **Die Liste steht schon beim Laden** am Bericht (aus `noch_offen` der Berichtsliste); nach dem Beantworten eines Punkts frischt sie erst der
   nächste Klick auf „Unterschreiben“ oder das Neuladen auf (Übergang bis Runde 4).
5. **Pflichtpunkt = `required`** am Prüfpunkt (aus der Vorlage; von Hand ergänzte sind nie Pflicht). „Neu erzeugen“ löscht weiter alle Punkte
   und baut sie aus der Vorlage neu -- die Pflichtpunkte kommen dabei wieder.
6. **Wortlaut** der Einträge wie oben, Kurzfassung des Prüfpunkts bis 80, des Mangels bis 60 Zeichen.

### R1 Punkt 4 (1.9.37): PDF nur mit den Zeiten dieses Einsatzes

- **Befund** (Befund Stufe 4, B3): `build_service_report_pdf()` nahm `list_entries(db, order_id=…)` -- jede Zeit des Auftrags, aller Tage und
  Personen. Bei einem Auftrag mit mehreren Einsätzen (verschiedene Wochen, verschiedene Kolonnen) stand im PDF eines Einsatzes jede Zeit der
  anderen.
- **Einsatz-Bezug**: `einsaetze_des_berichts(db, report)` -- die Abschnitte der Plantafel (`PlanningSlot`) zur Arbeitsvorbereitung des
  Auftrags, deren Zeitraum den Tag des Berichts (`performed_at`) umfasst; je Beginn, Ende und die eingeteilten Personen: die Besetzung der
  Team-Zuweisung des Abschnitts (Schnappschuss `WorkPreparationTeamEmployee`) und die Einzelzuweisungen an der Arbeitsvorbereitung
  (`WorkPreparationEmployee`, gelten für jeden Abschnitt) -- dieselben zwei Wege wie `/mobil` (`planning._employee_assignment_slot_condition()`).
  `None`, wenn kein Abschnitt den Tag umfasst.
- **Filter**: `zeit_gehoert_zum_einsatz(entry, einsaetze)` -- Tag der Zeit im Zeitraum eines Einsatzes und ihre Person dort eingeteilt. Das PDF
  filtert die Zeiten des Auftrags damit; ohne Einsatz-Bezug bleibt es bei allen.

#### Was gilt ohne Einsatz-Bezug (nur berichtet, nicht geraten)

Ein Bericht hat keinen Einsatz-Bezug, wenn kein Abschnitt der Plantafel zu seinem Auftrag seinen Tag umfasst: ein Auftrag ohne Plantafel
(Schnellauftrag, Wartungsbesuch aus dem Vertrag ohne Einplanung, „ungeplante Wartung“ aus `/mobil`), ein Bericht an einem Tag außerhalb der
geplanten Abschnitte (Einsatz verschoben, ohne die Plantafel nachzuziehen). Dort zeigt das PDF weiter alle Zeiten des Auftrags. Zur
Entscheidung offen: so lassen, nur die Zeiten am Tag des Berichts, oder die des Erstellers/der Personen mit Zeiten an diesem Tag.

#### Tests und Prüfung

- Neu `tests/test_v465_pdf_einsatz.py` (5 Tests): ein Auftrag, Einsatz A (5.–7.10., Kolonne A mit Mia), Einsatz B (12.–13.10., Kolonne B mit
  Tom), vier Zeiten: Einsatz des Berichts = A mit Mia; PDF von A enthält nur Mias Zeit vom 6.10., keine von B, nicht Toms Zeit am Tag von A,
  nicht Mias Zeit an einem Tag von B (Angriff) / PDF von B nur Toms Zeit vom 12.10. (Gegenprobe); Einzelzuweisung an der Arbeitsvorbereitung
  zählt für jeden Einsatz; ohne Einsatz-Bezug alle vier Zeiten.
- **Gegenproben** (Marker `GEGENPROBE`, byte-genau zurück, alle FAILED): PDF ohne Filter (E1) -- 3 rot; ohne die Personen (nur Zeitraum,
  E2) -- 2 rot; ohne Einzelzuweisungen (E3) -- 1 rot.
- Zum PDF bestehende Tests (18 Dateien, die das PDF des Einsatzberichts erzeugen) unverändert grün; der Test unterschreibt seine Berichte
  (ein PDF gibt es nur für unterschriebene), die Unterschriften liegen über `monkeypatch` im Testordner.
- **Angepasste Erwartungen**: keine.

#### Festlegungen 1.9.37 (Bitte bestätigen)

1. **Einsatz** = jeder Abschnitt der Plantafel zum Auftrag, dessen Zeitraum den Tag des Berichts umfasst; mehrere solche (zwei Kolonnen
   gleichzeitig) zählen zusammen.
2. **Zeitraum des Einsatzes** = Beginn bis Ende des Abschnitts (ganze Tage), nicht nur der Tag des Berichts -- ein Bericht am Ende eines
   dreitägigen Einsatzes zeigt alle drei Tage.
3. **Eingeteilte Personen** = Besetzung der Team-Zuweisung (Schnappschuss) und Einzelzuweisungen an der Arbeitsvorbereitung; eine Zeit einer
   nicht eingeteilten Person am selben Auftrag und Tag fehlt im PDF.
4. **Ohne Einsatz-Bezug** alle Zeiten des Auftrags wie bisher -- offen (siehe oben).
5. **Nur das PDF**: die Tabelle „Erfasste Zeiten zu diesem Auftrag“ auf der Berichtsseite bleibt auftragsweit; das PDF wird bei jedem Abruf neu
   erzeugt, auch für schon unterschriebene Berichte gilt damit der Filter.

### R1 Nachtrag (nach 1.9.37): Endlauf

- **Endlauf auf bcfdcec** (saubere Arbeitskopie): volle Suite 6746 passed, 3 skipped; Klicktests 80 von 81 wie erwartet. Rot:
  `klicktest_vertrag_unterschrift`, Prüfung „Bericht: Schritt Kunde, Fläche geleert“ -- ist `['Unterschrift Monteur', True]`, Soll
  `['Unterschrift Kunde', False]`. Ursache: seit 1.9.36 fragt „Weiter“ vor dem Schritt des Kunden den Server (`GET …/noch-offen`), der
  Schritt wechselt erst nach der Antwort; der Klicktest prüfte sofort nach dem Klick (im Netzprotokoll die Anfrage noch offen). Die
  Unterschrift selbst ging danach durch. Mein Versäumnis in 1.9.36: dieser Klicktest unterschreibt ebenfalls einen Einsatzbericht und lief
  vor dem Commit nicht mit.
- **Angepasste Erwartung** (Regel 28, nur Aufbau, Soll unverändert): `klicktest_vertrag_unterschrift`, Einsatzbericht -- wartet nach
  „Weiter“ auf die Überschrift „Unterschrift Kunde“ (bis zu 10 s), statt sofort zu prüfen.
- Ohne Bezug zu dieser Runde, nur genannt: derselbe Klicktest meldet bei „Vorlage: Kennzeichen ändern“ in jedem Lauf (auch allen früheren
  grünen) „warten: nach 15 s nicht erfüllt: … .ctStatus …“ -- die Seite schreibt dort nicht „Gespeichert.“; die Prüfung danach ist grün.

## Stufe 4, R1 Nachrunde (1.9.38–): Entscheidungen von Tobias

Vorgabe vom 22.10.2026: Festlegungen R1 bestätigt, außer 1.9.34 Nr. 3, 1.9.35 Nr. 6 und 1.9.37 Nr. 1–5 -- die ersetzt diese Runde.
(1) Zeiten im Einsatzbericht: ein Bericht je Tag, alle Zeiten des Auftrags am Tag des Berichts, alle Personen, mit und ohne Plantafel; Seite
und PDF dieselben Zeilen; mit der Unterschrift gespeichert. (2) Rundung der Gruppenzeiten je Mitglied wie Einzelzeiten, eine Funktion.
(3) Nur selbst hinzugefügte Prüfpunkte löschbar, Löschknopf 48 × 48 px mit Rückfrage. (4) Zeiterfassung: alte Fehlermeldung weg nach „Ende
nachtragen“, kein „✓“ nach abgelehntem Start. (5) CLAUDE.md: Klicktests der geänderten Seiten vor jedem Commit.

### Nachrunde Punkt 5 (1.9.38): Klicktests der geänderten Seiten vor jedem Commit

Regel 15 ergänzt: vor jedem Commit zusätzlich zur vollen Suite jeder Klicktest, der eine geänderte Seite berührt (Suche in
`scripts/klicktest_*.py` nach Vorlage, Seitenpfad, geänderten Funktionen und Element-IDs), auf genau dem Stand des Commits; der Bericht
nennt sie. Anlass: Endlauf zu 1.9.37 (siehe „R1 Nachtrag“). Keine Festlegung, Betreibervorgabe.

### Nachrunde Punkt 2 (1.9.39): Gruppenzeiten gerundet wie Einzelzeiten

- **Befund**: gerundet wurde im Router (`_apply_time_rounding()` nach dem Einzel-Stopp, `rounded_hours()` beim Einzel-Nachtrag); im
  Gruppenfall des Stopps traf `_apply_time_rounding()` nur die Zeit dessen, der stoppte, der Gruppen-Stopp und der Gruppen-Nachtrag rundeten
  gar nicht, „Ende nachtragen“ für eine Gruppe ebenfalls nicht (Festlegungen 1.9.34 Nr. 3 und 1.9.35 Nr. 6, beide ersetzt).
- **Eine Funktion**: `gebucht_nach_zeitregel(db, stunden)` -- Rundung der Zeitregeln (`rounding_minutes`, `time_backoffice.rounded_hours()`),
  ohne eingestellte Rundung der Wert unverändert. Aufgerufen in `stop_timer()`, `stop_group_timer()` (je Mitglied),
  `create_manual_entry()`, `create_group_manual_entry()` (je Mitglied); „Ende nachtragen“ und der Stopp im Gruppenfall laufen über
  `stop_timer()`/`stop_group_timer()`. Der Router rundet nicht mehr (`_apply_time_rounding()` entfällt). Ändern einer Buchung rundet wie
  bisher nicht. Wächter: unter `app/` ruft `rounded_hours()` nur sie -- und der DATEV-Export (`build_datev_export()`, summiert gerundet,
  unverändert).

#### Tests und Prüfung

- Neu `tests/test_v466_rundung_gruppen.py` (8 Tests, Rundung 15 min, 07:00–12:07 = 5,1167 h): Gruppen-Stopp, Stopp im Gruppenfall,
  Gruppen-Nachtrag (5,1 h) und Ende nachtragen der Gruppe -- je Mitglied 5,00 h (Angriff auf die alte Rechnung) / Einzel-Stopp 5,00 h
  (Gegenprobe); ohne Rundung 5,1167 h; eine schon gebuchte, ungerundete Gruppenzeit bleibt nach dem Einschalten der Rundung 5,1167 h;
  Wächter „eine Rundung“.
- **Gegenproben** (Marker `GEGENPROBE`, byte-genau zurück, alle FAILED): keine Rundung (G1) -- 6 rot; Gruppen-Stopp ohne Rundung (G2) -- 3;
  Gruppen-Nachtrag ohne Rundung (G3) -- 1; zweite Rundung im Router (G4) -- Wächter rot.
- Alle Zeiterfassungs-Tests (68 Dateien) unverändert grün. **Angepasste Erwartungen**: keine.

#### Festlegungen 1.9.39 (Bitte bestätigen)

1. **Ohne eingestellte Rundung bleibt jede Buchung, wie gerechnet** (vier Nachkommastellen) -- auch der Einzel-Nachtrag, der bis 1.9.38
   dann auf zwei Stellen rundete (`round_hours()`); so ergeben Nachtrag mit Von/Bis und Stopp derselben Zeiten genau dieselben Stunden.
2. **Gruppen-Nachtrag**: die eingegebenen Stunden je Person werden einmal gerundet, jede Person bekommt denselben Wert.
3. **Ändern** einer Buchung (einzeln oder Gruppe) rundet weiter nicht -- wie bisher, nicht Teil dieser Vorgabe.

### Nachrunde Punkt 4 (1.9.40): Zeiterfassung der Monteurin

- **Alte Meldung**: `endeNachtragen()` leert nach dem Erfolg `#quickStatus` (Meldung des abgelehnten Starts) und `#endeStatus`.
- **„✓“**: Befund -- das Zeichen kam nicht vom Start. `renderQuickTiles()` und `renderManualTiles()` hängen seit 1.5.3 an die zur
  Jahreszeit passende Schlechtwetter-Zeitart (`weatherSeasonFor()`: 1.12.–31.3. Winter, sonst Sommer) „✓“ und einen grünen Rand; das stand
  vor und nach jedem Klick da. Jetzt der Text „Vorschlag“ (`.vorschlag`, kleine zweite Zeile) statt „✓“, der Rand bleibt.

#### Tests und Prüfung

- `klicktest_monteurin_regeln` um zwei Prüfungen ergänzt (29): nach dem abgelehnten Start kein „✓“ an einer Kachel, „Vorschlag“ als Text;
  nach „Ende nachtragen“ sind beide Meldungen leer.
- **Gegenproben** (Marker `GEGENPROBE`, byte-genau zurück): wieder „✓“ (V1) -- 1 Prüfung rot; Meldung bleibt (V2) -- 1 Prüfung rot.
- **Angepasste Erwartungen**: keine.

#### Festlegungen 1.9.40 (Bitte bestätigen)

1. **„Vorschlag“ statt „✓“** an der vorgeschlagenen Schlechtwetter-Kachel, in „Schnell starten“ und im Dialog „Nachtragen“; der grüne Rand
   bleibt.

### Nachrunde Punkt 3 (1.9.41): Prüfpunkte -- nur eigene löschbar, Löschknopf 48 px mit Rückfrage

- **Unterscheidbar?** Ja: `_generate_inspection_items()` setzt an jedem Punkt aus der Vorlage `template_item_id`, `add_inspection_item()`
  (von Hand ergänzt, Seite und Schnittstelle) setzt es nie; andere Wege, Prüfpunkte anzulegen, gibt es nicht (keine Migration legt welche
  an). Die Spalte kann nicht nachträglich leer werden: `delete_template_item()` löscht die Vorlagenzeile, der Fremdschlüssel hat kein
  `ON DELETE` -- unter SQLite zeigt er danach ins Leere (bleibt gesetzt), unter PostgreSQL scheitert das Löschen eines in einem Bericht
  benutzten Vorlagenpunkts (Befund, siehe unten).
- **Server**: `delete_inspection_item()` lehnt jeden Punkt mit `template_item_id` ab (`VorlagenpunktGeschuetzt` statt
  `PflichtpunktGeschuetzt`, 409 „Ein Prüfpunkt aus der Vorlage lässt sich nicht löschen – trifft er nicht zu, „Entfällt“ wählen.“), für jede
  Rolle. Ein von Hand ergänzter Punkt bleibt löschbar, auch wenn er über die Schnittstelle als Pflicht angelegt wurde.
- **Seite**: Titelzeile `.ikopf` (Text, am Ende der Knopf); `.punkt-loeschen` 48 × 48 px, nur bei `template_item_id == null`. Rückfrage
  `rueckfrage()` über `<dialog id="punktLoeschenDialog" class="rueckfrage-karte">` mit „Abbrechen“ (Fokus) und „Löschen“, 48 px hoch;
  Esc = Abbrechen.

#### Befund (nicht geändert)

- `delete_template_item()` (Einstellungen → Prüfvorlagen): ein Vorlagenpunkt, aus dem schon Prüfpunkte in Berichten entstanden sind,
  lässt sich unter PostgreSQL nicht löschen -- `inspection_items.template_item_id` verweist ohne `ON DELETE` darauf, das Löschen endet mit
  einem Fehler der Datenbank (500). Unter SQLite fällt es nicht auf.

#### Tests und Prüfung

- Neu `tests/test_v469_vorlagenpunkte.py` (5 Tests, als Monteurin): Herkunft unterscheidbar; Pflichtpunkt und freier Punkt aus der Vorlage
  löschen 409, der Punkt bleibt (Angriff) / eigener Punkt und eigener Pflichtpunkt löschen 200 (Gegenprobe); Seite: Knopf nur am eigenen
  Punkt, Rückfrage ohne `confirm()`, Dialog, 48 px.
- `klicktest_monteurin_regeln` (35 Prüfungen): „×“ nur am von Hand ergänzten Punkt; Knopf ≥ 48 × 48 px, schmaler als die halbe Zeile, am
  Ende der Titelzeile; Rückfrage „Prüfpunkt „Dachluke geprüft“ löschen?“; Abbrechen: Punkt bleibt; Löschen: Punkt weg; Punkt aus der
  Vorlage (Pflicht und frei) über die Schnittstelle 409. Beim ersten Lauf zwei Prüfungen rot -- mein Fehler im Klicktest (ein Teil des
  JS-Ausdrucks war kein f-String), korrigiert.
- **Gegenproben** (Marker `GEGENPROBE`, byte-genau zurück): Server löscht Vorlagenpunkte (P1) -- 4 Tests rot; Knopf an jedem Punkt (P2) --
  2 Tests und 4 Klicktest-Prüfungen rot; Löschen ohne Rückfrage (P3) -- 1 Test und 2 Klicktest-Prüfungen rot.
- **Angepasste Erwartungen** (Regel 28):
  - `test_v464::test_pflichtpunkt_loeschen_abgelehnt`: alt Meldung „Ein Pflichtpunkt lässt sich nicht löschen.“; neu „Ein Prüfpunkt aus der
    Vorlage lässt sich nicht löschen – trifft er nicht zu, „Entfällt“ wählen.“
  - `test_v464::test_freier_punkt_loeschen_ok`: alt freier Punkt aus der Vorlage löschen 200; neu 409 (eigener Punkt weiter 200).
  - `test_v464::test_seite_fragt_vor_jeder_unterschrift_und_ohne_kreuz_am_pflichtpunkt`: alt Knopf bei `!item.required`; neu bei
    `item.template_item_id==null` mit Klasse `punkt-loeschen`.
  - `klicktest_monteurin_regeln`, Prüfung „Prüfpunkte“: alt „×“ an den beiden freien Punkten aus der Vorlage; neu „×“ nur am von Hand
    ergänzten Punkt (Testdaten um diesen Punkt ergänzt, 7 statt 6 Punkte); „Pflichtpunkt löschen (API)“ prüft jetzt Pflicht- und freien
    Punkt aus der Vorlage mit der neuen Meldung.

#### Festlegungen 1.9.41 (Bitte bestätigen)

1. **„Selbst hinzugefügt“ = von Hand ergänzt** (ohne Herkunft aus der Vorlage), gleich wer ihn ergänzt hat; die Regel gilt für jede Rolle,
   auch Büro und Admin.
2. **Rückfrage auf der Seite** (`<dialog>`, 48-px-Knöpfe, Fokus auf „Abbrechen“) statt `confirm()` -- sichtbar im Bild und auf dem Tablet
   gut zu treffen; andere Seiten fragen weiter über `confirm()`.
3. **Knopf schmaler als die halbe Zeile** gilt im Klicktest als „nicht über die ganze Breite“.

### Nachrunde Punkt 1 (1.9.42): Zeiten im Einsatzbericht -- ein Bericht je Tag

- **Gespeichert schon heute?** Nein. Ein unterschriebener Einsatzbericht speichert keinen Stand seiner Zeiten: das PDF entsteht bei jedem
  Abruf neu (`GET /api/service-reports/{id}/pdf`, auch das der Monteurin in der Wartungshistorie), es gibt keinen Versand über das
  Versandprotokoll und keine Kopie in der Ablage (`app/dispatch_documents.py` kennt den Einsatzbericht nicht). Mit der Unterschrift
  unveränderlich sind bisher nur Unterschriftsbilder und -namen, Prüfpunkte, Mängel, Material und Betriebsmittel. Darauf ließ sich nicht
  aufbauen -- neu ist die Spalte `service_reports.time_rows_json`.
- **Regel** (ersetzt 1.9.37 Nr. 1–5): `zeiten_am_tag(db, report)` -- `list_entries(order_id, start_date = end_date = performed_at)`, alle
  Personen, jeder Status; sortiert nach Beginn (ohne Beginn zuletzt), Person, ID. Eine Zeile `{tag, person, von, bis, stunden, laeuft}`:
  von/bis „HH:MM“ aus Beginn und Ende (ohne: leer), Stunden kaufmännisch auf zwei Stellen als Text; läuft die Zeit: kein Ende, keine Stunden.
  `einsaetze_des_berichts()` und `zeit_gehoert_zum_einsatz()` (1.9.37) entfallen.
- **Stand**: `sign_report()` schreibt im selben Commit wie die Unterschrift `time_rows_json = {"format": 1, "zeilen": zeiten_am_tag()}`.
- **Eine Funktion für Seite und PDF**: `zeiten_des_berichts()` -- `gespeichert` (Stand), `aktuell` (Entwurf, live), `alt` (unterschrieben ohne
  Stand: wie vor 1.9.37 alle Zeiten des Auftrags, `{tag, person, taetigkeit, stunden}`). `GET /api/service-reports/{id}/zeiten` (Ersteller-
  Prüfung wie jeder Bericht-Endpunkt) liefert sie der Seite; das PDF druckt dieselben Zeilen -- „Zeiten am <Tag>“ mit Tag, Person, von–bis,
  Stunden (alt: „Erfasste Zeiten“ mit Datum, Mitarbeiter, Tätigkeit, Stunden wie bisher).
- **Seite**: je Bericht in seiner Karte die Tabelle mit Titel („Zeiten am … – Stand der Unterschrift“, „– Stand jetzt, wird mit der
  Unterschrift gespeichert“, alt „Zeiten des Auftrags (wie im PDF dieses älteren Berichts)“); nach „Zeit buchen“ laden die Entwürfe neu.
- **Migration** `b7e3d91c4a58`: Spalte hinzu (leer), keine vorhandene Zeile geändert; `downgrade()` verweigert, solange ein Bericht einen Stand
  hat (er ginge verloren).

#### Tests und Prüfung

- Neu `tests/test_v467_zeiten_einsatzbericht.py` (7 Tests): Vortag und Folgetag desselben Auftrags nicht im Bericht (Angriff) / die Zeit des
  Kollegen am Berichtstag drin (Gegenprobe); mit einem Plantafel-Abschnitt nur für Mia dieselben Zeilen; nach der Unterschrift eine Zeit am
  Berichtstag gebucht und eine geändert -- Seite und PDF des unterschriebenen Berichts unverändert (Angriff) / ein Entwurf desselben Tages
  zeigt beides (Gegenprobe); laufende Zeit beim Unterschreiben „läuft seit 13:00“ ohne Stunden, bleibt nach dem Stopp so, im PDF; alter
  unterschriebener Bericht ohne Stand wie vor 1.9.37 (alle Zeiten mit Tätigkeit, Seite und PDF); Seite und PDF dieselben Zeilen; Monteurin
  sieht die Zeilen ihres Berichts, einen fremden nicht (403).
- Neu `tests/test_v468_zeiten_stand_migration.py` (2 Tests): Bestand auf 8c86e12540cf (Auftrag, unterschriebener Bericht, Entwurf), hoch --
  jede Zeile unverändert, Spalte leer; runter -- wie vorher; mit Stand runter -- verweigert, nichts geändert; SQLite und PostgreSQL
  (Wegwerf-Schema).
- Neuer Klicktest `scripts/klicktest_einsatzbericht_zeiten.py` (11 Prüfungen): Anna 1400 px hell -- unterschriebener Bericht und Entwurf mit
  denselben Zeilen, ohne Vortag; PDF vorher (pdf_vorher.pdf); Zeit über das Formular der Seite gebucht und Mias Zeit geändert -- unterschriebener
  Bericht und PDF (pdf_nachher.pdf) unverändert, Entwurf mit beidem; Mia 412 px dunkel -- ihr Bericht mit denselben Zeilen. Beim ersten Lauf
  drei Prüfungen rot: mein Fehler im Klicktest (JS-Ausdruck mit doppelten Klammern), korrigiert.
- **Gegenproben** (Marker `GEGENPROBE`, byte-genau zurück, alle FAILED): kein Stand bei der Unterschrift (Z1) -- 3 Tests und 5
  Klicktest-Prüfungen rot; alle Tage des Auftrags (Z2) -- 5; gespeicherter Stand übergangen (Z3) -- 3; Rückweg ohne Schutz (Z4) -- 2.
- **Angepasste Erwartungen** (Regel 28):
  - `tests/test_v465_pdf_einsatz.py` (5 Tests, Regel von 1.9.37) entfällt -- die Regel ist ersetzt; die neuen Fälle stehen in `test_v467`.
  - `test_v315::test_hours_in_service_report_and_field_timesheet_pdfs_round_up` (nur Aufbau, Soll „1,13“ unverändert): der Bericht liegt auf
    dem Tag der Buchung (bis dahin heute -- dann stünde die Buchung nicht im Bericht).
  - `test_v273::test_field_pdf_never_calls_list_entries_and_carries_no_price_key` (nur Aufbau): `list_entries()` wird in
    `app/service_reports.py` abgefangen statt im PDF-Modul (dort wird es nicht mehr aufgerufen).
  - `test_v311::test_service_report_pdf_lists_all_501_entries_of_order` (nur Aufbau, Soll unverändert): der Bericht der Fixture hat keinen
    gespeicherten Stand (wie vor 1.9.42 unterschrieben) -- nur dann zeigt das PDF alle Zeiten des Auftrags, und damit jede der 501.

#### Festlegungen 1.9.42 (Bitte bestätigen)

1. **Stand** = JSON in `service_reports.time_rows_json` (Tag, Person, von, bis, Stunden auf zwei Stellen, läuft), gespeichert im selben
   Aufruf wie beide Unterschriften.
2. **Reihenfolge** der Zeilen: nach Beginn, Zeiten ohne Beginn (Dauer) zuletzt, dann Person; eine Dauer ohne Beginn und Ende zeigt „–“.
3. **Laufende Zeit von einem früheren Tag** gehört zu ihrem Starttag (wie ihr Buchungstag), nicht zum späteren Bericht.
4. **Seite**: die Zeiten stehen je Bericht in seiner Karte; die Karte „Erfasste Zeiten zu diesem Auftrag“ (Buchen, alle Zeiten des Auftrags)
   bleibt, wie sie ist.
5. **Alter Bericht** (vor 1.9.42 unterschrieben): die Seite zeigt dieselben Zeilen wie sein PDF (alle Zeiten des Auftrags, mit Tätigkeit)
   und sagt das; nichts wird nachträglich gespeichert.
6. **Die Monteurin** sieht in ihrem eigenen Bericht die Zeilen aller Personen des Tages -- wie im PDF dieses Berichts, das sie schon abrufen
   kann; das Monteur-PDF der Wartungshistorie bleibt ohne Zeiten.
7. **PDF**: Titel „Zeiten am <Tag>“, Spalten Tag (25 mm), Person (50 mm), von–bis (Rest), Stunden (30 mm) -- die Breiten von bisher.
8. **Rückweg** der Migration verweigert, solange ein Bericht einen gespeicherten Stand hat.

## Stufe 4, R2 „Heute“ für die Monteurin (1.9.43–)

Auftrag von Tobias (22.10.2026): der Reiter „Einsätze“ wird „Heute“ nach den freigegebenen Vorlagen
`bildgrundlage/entwurf-stufe4/heute-quer.html`, `heute-gestern.html`, `heute-hoch.html` (Maße, Abstände, Reihenfolge, Texte gelten;
Farben über die Tokens). Dazu nebenbei: Zeitpunkte in Europe/Berlin, Vorlagenpunkt mit Berichten nicht löschbar; nur berichtet: wie die
Pausenregel rechnet. Die Runde beginnt mit den kleinen Punkten (7), dann Server und Seite für „Heute“.

### R2 Punkt 7a (1.9.43): Vorlagenpunkt, der in Berichten steckt -- 409 statt 500

- **Vorher**: `delete_template_item()` löschte ohne Prüfung. Unter PostgreSQL lehnt der Fremdschlüssel `inspection_items.template_item_id`
  (ohne `ON DELETE`) das ab, der Router fing nichts -- 500. Unter SQLite (Fremdschlüssel nicht erzwungen) blieb `template_item_id` auf eine
  nicht mehr vorhandene Zeile gesetzt.
- **Jetzt**: die Zeile des Vorlagenpunkts wird gesperrt (`with_for_update()`: unter PostgreSQL wartet die Sperre auf einen Bericht, der gerade
  aus der Vorlage entsteht -- er hält den Punkt mit FOR KEY SHARE --, danach zählt die Abfrage ihn mit), dann zählt
  `_berichte_mit_punkt()` die Berichte (je Bericht einmal, auch wenn der Punkt je Bauteil mehrfach im Bericht steht); mindestens einer ->
  `VorlagenpunktInBerichten` (409): „Dieser Prüfpunkt steckt in einem Einsatzbericht | n Einsatzberichten und lässt sich deshalb nicht
  löschen. Für neue Berichte ohne ihn: Vorlage kopieren und den Punkt in der Kopie löschen.“ Punkt, Version und Verweise bleiben. Als Netz
  endet ein `IntegrityError` beim Commit ebenfalls in dieser Meldung (nie 500). Kein `ON DELETE SET NULL` oder `CASCADE`.
- Die Seite der Prüfvorlage zeigt die Meldung unter der Tabelle („Fehler: …“), wie jede abgelehnte Änderung dort -- an der Seite nichts
  geändert.

#### Nebenbefund (nicht geändert)

- `delete_roof_component()` sperrt nur bei Verweisen aus **unterschriebenen** Berichten und bei Mängeln; ein Prüfpunkt eines
  **Entwurfs** mit `roof_component_id` auf das Bauteil dürfte unter PostgreSQL denselben Fehler am Fremdschlüssel auslösen (500). Aus dem
  Code gelesen, nicht nachgestellt.

#### Tests und Prüfung

- Neu `tests/test_v470_vorlagenpunkt_loeschen.py` (4 Tests): Punkt in einem bzw. zwei Berichten -> 409 mit „einem Einsatzbericht“ bzw.
  „2 Einsatzberichten“, Punkt, Version und Verweise unverändert (Angriff); neuer Punkt ohne Bericht -> gelöscht, Version + 1 (Gegenprobe);
  unter PostgreSQL (Wegwerf-Schema) Sperre statt `IntegrityError`, danach löscht dieselbe Sitzung einen freien Punkt.
- **Gegenproben** (Marker `GEGENPROBE`, byte-genau zurück): ohne Zählung und ohne Netz (Stand 1.9.42, P1) -- 3 Tests rot (SQLite 200,
  PostgreSQL `IntegrityError`); nur das Netz (P2) -- 2 Tests rot, der PostgreSQL-Test bleibt grün (das Netz fängt den Fremdschlüssel, wie
  gewollt); Router ohne 409 (P3) -- 2 Tests rot.

#### Festlegungen 1.9.43 (Bitte bestätigen)

1. **Gezählt werden alle Berichte**, Entwurf wie unterschrieben, je Bericht einmal.
2. **Die Meldung nennt den Ausweg** „Vorlage kopieren und den Punkt in der Kopie löschen“ -- ein Ausblenden einzelner Punkte gibt es nicht.
3. **Netz**: ein `IntegrityError` beim Löschen endet ebenfalls in 409 (Anzahl neu gezählt, mindestens 1).

### R2 Punkte 2–5 (1.9.44): der Server für „Heute“

- **Ein Endpunkt**: `GET /api/field-view/today` trägt zusätzlich `heute` (`app/heute.py::heute_fuer()`), die alten Schlüssel bleiben
  (Tests, ältere Seitenstände). Die Seite rechnet nichts davon nach.
- **Arbeitszeit** (`arbeitszeit()`): „laeuft“ -- Zeitart, Beginn HH:MM, Dauer in Minuten bis jetzt (Anwesenheit ohne Pause), Auftrag und
  Objekt; in einer laufenden Gruppe `gruppe.kolonnenfuehrer` nur für den, der sie gestartet hat und es im Team noch ist (wie der
  Gruppen-Stopp seit 1.8.144), sonst `gruppe.stoppt` mit dessen Namen. „frueher“ -- die Zeit läuft seit einem früheren Tag: Tag, „gestern“,
  Beginn, `monat_abgeschlossen` (Monteurin, Starttag im abgeschlossenen Zeitraum), `nachtragen_durch` (Mitglied einer Gruppe: der
  Kolonnenführer). „nichts“ -- buchbare Aufträge (`list_field_bookable_orders()`), `vorbelegt` nur bei genau einem Auftrag im heutigen
  Einsatz, der buchbar ist. Dazu die aktiven Zeitarten für die Kacheln.
- **Einsatz** (`einsaetze()`): eine Karte je Auftrag, Zeitraum von der frühesten bis zur spätesten Grenze der heute geltenden Abschnitte;
  Objekt, Kunde, Adresse wie die Plantafel; darin die eigenen Berichte (Entwürfe mit „noch n offen“ aus `noch_offen()`, dazu heute
  unterschriebene mit Berichtstag heute) und die eigenen Checklisten am Auftrag (offen mit der Zahl der fehlenden Pflichtangaben aus
  `missing_required_labels()`, dazu heute abgeschlossene; nie eine nur fürs Büro), offene Bedenken wie bisher.
- **Offen** (`offen()`): eigene Berichtsentwürfe, eigene offene Checklisten (wie `GET /api/checklists/mine`), Mängel zur Beseitigung (wie
  `GET /api/field-view/defects`).
- **Nächste Tage** (`naechste_tage()`): morgen bis heute + 14; je Auftrag aufeinander folgende Tage in einer Zeile; Nebentext „Fortsetzung“,
  wenn der Auftrag heute Einsatz ist, sonst der Titel des Auftrags (ohne Titel die Nummer). Bei einer offenen Zeit von früher steht heute
  vorn als eigene Zeile (Vorlage „Heute und nächste Tage“, dort ersetzt diese Liste die Einsatzkarte).
- **Zeitart wechseln** (`zeitart_wechseln()`, `POST /api/time-entries/{id}/zeitart-wechseln`): die laufende Zeit endet jetzt nach der
  Zeitregel (`ende_rechnen()`), die neue beginnt im selben Augenblick mit der neuen Zeitart, demselben Auftrag, derselben LV-Position und
  Tätigkeit; ein Commit. Abgelehnt: fremde Zeit 403, abgeschlossener Zeitraum 403, Zeit von früher 409, laufende Gruppenzeit 409, dieselbe
  oder eine unbekannte Zeitart 422; dazu die Regeln eines Starts (LV-Position, Tätigkeit, buchbarer Auftrag).
- **Vorschau** (`ende_vorschau()`, `GET /api/time-entries/{id}/ende-vorschau`): dieselben Prüfungen wie „Ende nachtragen“, dieselbe Rechnung,
  bucht nichts.
- Befund zur Pausenregel (Punkt 8, je Buchung statt je Tag): `docs/archiv/zeiterfassung-und-abwesenheit.md`, „„Heute“: Zeitart wechseln und
  Vorschau“.

#### Tests und Prüfung

- Neu `tests/test_v471_heute_server.py` (17 Tests): Vorschau = Buchung (drei Enden bzw. Mindestpause, dazu die Gruppenzeit des
  Kolonnenführers), Vorschau-Rechte (fremd 403, heute gestartet 409); Arbeitszeit läuft mit Dauer; Gruppenmitglied ohne Knopf / Kolonnenführer
  mit, ohne Kennzeichen kein Knopf, Gruppen-Stopp durch das Mitglied 403; nichts läuft mit Vorbelegung (ein Auftrag) bzw. ohne (zwei);
  früher offen mit „Monat abgeschlossen“ und Nachtragen durch den Kolonnenführer; zwei Zeitfenster am selben Auftrag -> eine Karte; heute
  nicht in „Nächste Tage“, morgen drin, nach 14 Tagen nichts; bei offener Zeit von früher heute vorn; Zeitart wechseln ohne Lücke und
  Überschneidung, abgelehnt (Gruppe, gestern, fremd, gleich, unbekannt).
- **Gegenproben** (Marker `GEGENPROBE`, byte-genau zurück): Vorschau ohne Mindestpause (P1) -- 1 Test rot; Zeitart wechseln mit Lücke (P2) --
  1 rot; Einsatz je Abschnitt (P3) -- 1 rot; Nächste Tage ab heute (P4) -- 2 rot; jedes Gruppenmitglied als Kolonnenführer (P5) -- 3 rot;
  Zeitart wechseln in der Gruppe (P6) -- 1 rot.
- **Angepasste Erwartungen** (Regel 28):
  - `test_v462::test_eine_pausenregel_keine_zweite_rechnung`: alt Stopp, Gruppen-Stopp und Nachtrag rufen `pause_nach_zeitregel()`; neu
    `ende_rechnen()` und Nachtrag rufen sie, Stopp, Gruppen-Stopp, Vorschau und Zeitart wechseln rufen `ende_rechnen()`.
  - `test_v326` (Testdaten, Aufbau): die Gruppenzeit der Monteurin startet gestern 07:00 statt beim Anlegen -- so liefern „Heute“ (Zustand
    „früher“) und die Vorschau Inhalt; dazu `entry_id` und `ende` für die neue Route. Ein Schlüssel `zusatz` fiel dort als verboten auf
    (Wortteil „satz“), er heißt `nebentext`.

#### Festlegungen 1.9.44 (Bitte bestätigen)

1. **„Heute“ im bestehenden Endpunkt** `GET /api/field-view/today` (Schlüssel `heute`), kein neuer.
2. **Zeitart wechseln übernimmt LV-Position und Tätigkeit**; die neue Zeitart nur aus den aktiven Zeitarten; nicht für eine Gruppenzeit (409).
3. **Knopf in der Gruppe** nur für den, der sie gestartet hat, solange er Kolonnenführer ist; alle anderen „stoppt <Name>“.
4. **Im Einsatz** die eigenen Berichte (Entwürfe und heute unterschriebene) und eigenen Checklisten (offene und heute abgeschlossene), keine
   eines Kollegen -- seinen Bericht darf die Monteurin ohnehin nicht öffnen.
5. **„noch n offen“ einer Checkliste** = Zahl der fehlenden Pflichtangaben (`missing_required_labels()`), wie beim Abschließen.
6. **Nächste Tage**: Nebentext „Fortsetzung“, wenn der Auftrag heute Einsatz ist, sonst der Titel des Auftrags; bei offener Zeit von früher
   heute als eigene Zeile vorn, nicht mit den folgenden Tagen zusammengefasst.
7. **Vorbelegung** nur bei genau einem Auftrag im heutigen Einsatz, der auch buchbar ist.
8. **Dauer** = Anwesenheit seit Beginn (vor Abzug der Pause), vom Server in Minuten; die Seite zählt jede Minute weiter.

### R2 Punkte 1–6 (1.9.45): die Seite „Heute“

- **Aufbau** (`app/templates/mobil.html`): oben `.heute` -- ab 1000 px ein Raster `minmax(0,1fr) 420px`, Abstand 16 px, Rand 16 px 20 px;
  darunter eine Spalte (Rand 16 px) in der Reihenfolge der Vorlage heute-hoch (links Arbeitszeit und Einsatz, rechts Offen und Nächste
  Tage, im Quelltext hintereinander). Karten `.heute-karte`/`.signal-karte` mit `var(--ds-ecke-karte)` (im Monteursrahmen 16 px wie die
  Vorlage), Farben nur über `--ds-*`; dunkel über die Tokens. Unter „Heute“ die bisherigen Listen (offene Berichte, Mängel zur Beseitigung
  mit „Beseitigt melden“, offene Checklisten, Wartungen an meinen Objekten) mit Ankern -- dorthin führen die Zeilen von „Offen“. „Meine
  kommenden Termine“ ist in „Nächste Tage“ aufgegangen (der Endpunkt `GET /api/field-view/upcoming` bleibt).
- **Arbeitszeit**: läuft -- Kopf „Arbeitszeit · Do 22.10.“ mit „läuft“ (Info-Töne), „<Zeitart> seit HH:MM“ (Archivo 26 px), Auftrag · Objekt,
  Dauer h:mm (40 px; vom Server in Minuten, im Browser über `performance.now()` jede Minute weiter, nie über Datum oder Zeitzone des
  Geräts); „Feierabend“ (`--ds-stark`) und „Zeitart wechseln“ (neutral) je 64 px, die Kacheln der anderen Zeitarten erst nach dem Klick.
  Gruppenzeit: Kolonnenführer „Feierabend für die Gruppe“ (`POST /api/time-entry-groups/{id}/stop`), Mitglied „Gruppenzeit · stoppt <Name>“
  ohne Knopf. Nichts läuft: Auswahl „Auftrag“ (`auswahlOptionen()`, vorbelegt nach dem Server) und die Kacheln der Zeitarten (64 px,
  „Vorschlag“ an der Schlechtwetter-Zeitart der Jahreszeit wie „Schnell starten“). Zeit von früher offen: Signalkarte (`--ds-signal-*`)
  „Wartet auf dich“, „Deine Zeit von gestern läuft noch“ bzw. „vom <Tag>“, „<Zeitart> seit <Tag>, HH:MM · Auftrag · Objekt“, Feld „Feierabend
  gestern um“ bzw. „am <Tag> um“ (64 × 180 px, leer), darunter die Vorschau aus `GET …/ende-vorschau` („Anwesend h:mm · Pause nach Zeitregel
  − h:mm“, „Gebucht werden x,xx h“), „Feierabend eintragen“ (grün, 64 px) mit dem Hinweistext; Mitglied einer Gruppe ohne Feld („Gruppenzeit –
  das Ende trägt <Name> nach.“), Monat abgeschlossen ohne Feld mit der Meldung aus R1 (seit 1.9.45 in `app/meldungen.py`). Darunter die
  Karte für heute mit gesperrtem „Arbeitsbeginn buchen“. Jede Aktion über `speichern('heute', …)`, danach lädt `lesen('heute', …)` neu.
- **Einsatz**: je Auftrag eine Karte „Heutiger Einsatz · 21.–24.10.“, Objekt (24 px), „Route“ (≥ 48 px) öffnet
  `https://www.google.com/maps/search/?api=1&query=<Adresse>` in einem neuen Fenster (auf Tablet und Telefon die Karten-App), „Kunde ·
  Adresse“; Hinweis „Offene Bedenken“ in der Karte; Berichtsentwurf mit „Entwurf · noch n offen“ bzw. „bereit zur Unterschrift“ und grünem
  „Weiter“ (56 px, zum Bericht), heute unterschriebener Bericht und Checklisten als Zeile mit Pfeil; unten „Bericht anlegen“ und „Checklisten
  zum Auftrag“ (48 px). Kein Einsatz: „Heute ist nichts eingeplant.“ Bei offener Zeit von früher keine Einsatzkarte (Vorlage heute-gestern):
  der Einsatz steht dann in „Heute und nächste Tage“.
- **Offen**: „Berichte“, „Checklisten“, „Mängel zur Beseitigung“ mit Anzahl (60 px), leere Gruppen fehlen, alle leer: „Nichts offen.“
  **Nächste Tage**: Datum 96 px (hoch 110 px; steht ein Bereich in der Liste, für alle Zeilen 156 bzw. 166 px), Objekt · Nebentext, 56 px;
  leer: „In den nächsten 14 Tagen ist nichts eingeplant.“
- **Reiter und Pfad**: der Reiter „Einsätze“ heißt „Heute“ (`_mobile_header.html`), ebenso der Anfang des Pfads auf Konto, Checkliste,
  Checklisten zum Auftrag, Objekt, Betriebsmittel und Einsatzbericht der Monteurin; die Adresse bleibt `/mobil`. „Meine Zeiten“ aus der Vorlage
  ist nicht Teil von R2 -- die Reiter „Zeiterfassung“ und „Stundenzettel“ bleiben.
- `[hidden]{display:none!important}` auf der Seite: sonst überstimmt `display:grid/flex` der Karten und Kacheln das Attribut (im ersten
  Klicktest waren die Kacheln von „Zeitart wechseln“ ohne Klick offen).

#### Tests und Prüfung

- Neu `tests/test_v472_heute_seite.py` (4 Tests): Einsatz mit eigenem Bericht („Wartungsbericht · Dachfläche Nord“, noch 3 offen) und
  eigener Checkliste (noch 1 offen), Toms Bericht nicht bei Mia; Raster, Maße und `[hidden]` im Stil; Lesen über `lesen()`, Route mit festem
  https-Anfang, Aktionen über `speichern()`; Reiter und Pfad „Heute“ in allen Vorlagen.
- Neu `scripts/klicktest_heute.py` (32 Prüfungen): Mia quer und hoch, hell und dunkel (Bilder), zwei Spalten mit rechts 420 px, eine Spalte
  in der Reihenfolge der Vorlage, Inhalte der Karten, Maße (Zeilen ≥ 56, Knöpfe ≥ 48, Hauptknöpfe 64, „Weiter“ 56), Zeitart wechseln -> zwei
  Buchungen ohne Lücke, Feierabend -> nichts läuft; Ole mit Zeit von gestern: Signalkarte, Vorschau „Anwesend 9:15 h · Pause nach Zeitregel −
  0:45 h“, „Gebucht werden 8,50 h“, gebucht wie die Vorschau, „Heute und nächste Tage“; Lea: nichts läuft mit Vorbelegung und Vorschlag,
  Start; Tom ohne Knopf mit „stoppt Kai Kolonne“, Kai mit „Feierabend für die Gruppe“. Beim ersten Lauf vier Prüfungen rot: der Berichtstitel
  ohne Dachfläche (falscher Schlüssel in `app/heute.py`, behoben), die Uhr der Instanz läuft weiter (Prüfung „ohne Lücke“ auf Ende = Beginn
  umgestellt, mein Fehler), „Feierabend“ in derselben Sekunde wie der Wechsel (`berlin_now()` ist sekundengenau -- 422 „Endzeit muss nach der
  Startzeit liegen“; der Klicktest wartet eine Sekunde über `tab.warten()`), das Thema vor dem ersten Laden gesetzt (mein Fehler).
- **Gegenproben** (Marker `GEGENPROBE`, byte-genau zurück): Titel ohne Dachfläche (P1) -- 1 Test und 1 Klicktest-Prüfung rot; `[hidden]` ohne
  Vorrang (P2) -- 1 Test und 1 Prüfung; Einsatzkarte auch bei Zeit von gestern (P3) -- 1 Prüfung; leere Gruppe in „Offen“ (P4) -- 1
  Prüfung; Reiter wieder „Einsätze“ (P5) -- 3 Tests und 1 Prüfung. P1 lief zuerst mit einem Marker mitten im Ausdruck (ERROR statt FAILED,
  mein Fehler) und wurde wiederholt.
- **Angepasste Erwartungen** (Regel 28):
  - `test_v272` (2 Tests), `test_v257`, `test_v328`, `test_v454`, `test_v457`, `klicktest_monteur_navigation`, `klicktest_neue_ordnung`,
    `klicktest_rahmen` (Reiter, Pfade): alt „Einsätze“; neu „Heute“.
  - `test_v460::test_kaesten_unter_der_einsatzkarte_schliessen_an`: alt Hinweis und „Checklisten zu diesem Auftrag“ unten an der Karte (Karte
    unten eckig); neu beides in der Karte, kein angehängter Kasten, der Hinweis mit eigener Ecke. `NICHT_KARTEN` um `knopf-neutral` und
    `knopf-gesperrt` ergänzt (Knöpfe).
  - `klicktest_rahmen`, Teil „ecken“: alt `.assign-card` 16 px und „Link schließt unten an“; neu `.heute-karte` 16 px und „Hinweis und Wege in
    der Einsatzkarte, nichts angehängt“.
  - `klicktest_bedenkenanzeige`: alt Hinweis unter der Karte `.assign-card`; neu in der Einsatzkarte `[data-einsatz]` (Aufbau).
  - `klicktest_monteurin_regeln`, `/mobil`: alt Hinweis „Deine Zeit läuft noch seit <Datum>, 06:45 Uhr“ mit Link „Ende nachtragen →“ zur
    Zeiterfassung; neu Signalkarte „Deine Zeit von gestern läuft noch“ mit Feld und „Feierabend eintragen“.
  - `test_v411` (Aufbau): der Ausschnitt für den node-Lauf endet an „// Seit 1.9.45 über lesen()“ statt am direkten `fetch()`.
  - `test_v400`: Ausnahme `("mobil.html", "<oben>", "fetch")` gestrichen (alles Lesen über `lesen()`).
  - `test_v441`: Grund von `mobil.html` in `AUFGESCHOBEN`: „Heute -- seit 1.9.45 nach den Vorlagen der Stufe 4, die keinen Seitenkopf haben“.
  - `test_v265::test_mobil_reachable_for_field_with_correct_title`: alt Titel „DACHKONZEPTE ERP – Mobil“; neu „DACHKONZEPTE ERP – Heute“.
  - `klicktest_bedenkenanzeige`, „Hinweis deutlich“: alt obere bzw. linke Rahmenfarbe = Textfarbe (der Hinweis hing oben ohne Rahmen unter
    der Karte); neu Rahmen oben und links in `--ds-fehler`, Text in `--ds-fehler-text` (der Hinweis steht mit vollem Rahmen in der Karte).
    Im ersten vollen Lauf auf 1.9.45 waren diese Prüfung und die beiden Tests rot, dazu `test_v346` (die Seite nannte `concernAlert(k)`
    statt `concernAlert(a)` -- an der Seite zurückbenannt, der Test unverändert).

#### Festlegungen 1.9.45 (Bitte bestätigen)

1. **Pfad-Anfang „Heute“** auch auf den Seiten unter /mobil (Konto, Checkliste, Objekt, Betriebsmittel, Einsatzbericht), nicht nur der Reiter.
2. **„Meine Zeiten“ aus der Vorlage nicht übernommen** -- R2 benennt nur „Einsätze“ um; „Zeiterfassung“ und „Stundenzettel“ bleiben.
3. **/mobil bleibt in `AUFGESCHOBEN`**: umgezogen hieße Seitenkopf mit Titel und Pfad, die Vorlage hat keinen.
4. **Die bisherigen Listen bleiben unter „Heute“** (offene Berichte, Mängel mit „Beseitigt melden“, offene Checklisten, Wartungen an meinen
   Objekten); „Offen“ springt dorthin. „Meine kommenden Termine“ entfällt (in „Nächste Tage“).
5. **Route über Google Maps** (`https://www.google.com/maps/search/?api=1&query=…`): öffnet auf Android und iOS die Karten-App, am Rechner die
   Webseite; die Adresse geht erst mit dem Klick hinaus.
6. **Feld „Feierabend gestern um“ ohne Vorbelegung** (die Vorlage zeigt 16:00 als Beispiel) -- die Vorschau erscheint mit der ersten Eingabe.
7. **Gruppenzeit ohne „Zeitart wechseln“**, auch nicht für den Kolonnenführer (Server 409).
8. **Status im Einsatz**: Bericht „Entwurf · noch n offen“ / „Entwurf · bereit zur Unterschrift“ / „Unterschrieben“, Checkliste „Entwurf · noch
   n offen“ / „Entwurf · alles ausgefüllt“ / „Abgeschlossen“ (statt „Schritt 1 von 5“ und „ein Pflichtpunkt fehlt“ der Vorlage).
9. **Alles leer in „Offen“**: die Karte bleibt mit „Nichts offen.“ (statt ganz zu fehlen).
10. **Datumsspalte in „Nächste Tage“** 96 px wie die Vorlage; steht ein Bereich darin, für alle Zeilen 156 px (hoch 166 px), ohne Umbruch.

#### Hinweis (nicht geändert)

- Feldrahmen auf der Signalfläche: `--ds-feld-rand` auf `--ds-signal-hell` hat hell 2,84 : 1 (dunkel 3,48 : 1) -- wie die Vorlage (#88929A
  auf #FDF0E7); das Feld selbst ist weiß. Text auf der Signalfläche: `--ds-text` 15,4 : 1, `--ds-text-2` 6,8 : 1 (dunkel 13,0 und 8,6).

### R2 Punkt 7b (1.9.46): angezeigte Zeitpunkte in Europe/Berlin

Herleitung, Helfer und die Liste aller Stellen: `docs/archiv/zeiterfassung-und-abwesenheit.md`, „Angezeigte Zeitpunkte in Europe/Berlin
(seit 1.9.46)“. Das Inventar entstand über alle 83 Vorlagen (Feld bis zum Serializer und zur Spalte verfolgt): 18 falsche Anzeigen, 20 nur im
Berliner Browser richtige, rund 30 schon richtige (`*_local`), rund 13 mit naiver Ortszeit, 1 unklar (Änderungsprotokoll, alter/neuer Wert).

#### Tests und Prüfung

- Neu `tests/test_v473_zeitpunkte_berlin.py`: der Helfer in node unter Europe/Berlin, UTC, America/New_York und Asia/Tokyo (Sommer- und
  Winterzeit, über Mitternacht, Silvester, beide Umstellungen, mit 'Z' und Versatz, leer, unlesbar); Wächter über alle Vorlagen (kein 'Z'
  angehängt, kein UTC-Feld in `new Date()`/`fmtDate()`/`fmt()`/`dateDe()`/`accDateTime()` u. a., keins abgeschnitten) samt Gegenprobe an den
  Mustern des Inventars; wer den Helfer nimmt, bindet `_berlin_date.html` ein; Unterschrift: gespeichert und geliefert 15:33 UTC, Seite
  „22.10.2026 17:33“ (Helfer in einem Browser in UTC) = PDF „am 22.10.2026 17:33 Uhr“.
- `klicktest_einsatzbericht_zeiten` um die Prüfung „Unterschrift auf der Seite = Zeit im PDF“ ergänzt (im Browser: die Zeit in „Kunde: …
  (TT.MM.JJJJ HH:MM Uhr)“ steht als „am … Uhr“ im PDF).
- Nebenbei: `users.html` zeigt für „nie angemeldet“ weiter „—“; die nicht mehr gebrauchten Hilfsfunktionen (`fmtDate` in users.html,
  `fmt` in checklists.html und `_checklists_section.html`, `fmtDateTime` in checklist.html und service_reports.html, die schon vorher tote
  `fmtDateTime` in mobil_objekt.html) sind entfernt; jeder Aufruf in HTML steht in `esc()` (der Helfer gibt Unlesbares unverändert zurück).
  `_berlin_date.html` ist in 15 weiteren Seiten eingebunden (wer den Helfer nimmt, auch über einen Teil wie `_checklists_section.html`).
- **Gegenproben** (Marker `GEGENPROBE`, byte-genau zurück): Helfer liest naives UTC als Ortszeit des Browsers (P1) -- 3 Tests rot (Berlin, New
  York, Tokio; in UTC stimmt es zufällig) und die Prüfung im Klicktest; Unterschrift wieder über `new Date()` (P2) -- Wächter, Test
  „Seite = PDF“ und Klicktest rot; Stand der Unterschrift in der Checkliste wieder roh (P3) -- Wächter und `test_v366` rot.
- **Angepasste Erwartungen** (Regel 28): `test_v366::test_page_shows_the_summary_card`: alt `fmtDateTime(s.signature.signed_at)`; neu
  `berlinZeitpunkt(s.signature.signed_at)`.

#### Festlegungen 1.9.46 (Bitte bestätigen)

1. **Ein Format** „TT.MM.JJJJ HH:MM“ (wie die PDFs und `_berlin_text()`) für jeden Zeitpunkt mit Uhrzeit, „TT.MM.JJJJ“ für ein Datum --
   ersetzt „22.10.26, 17:33“ (Checklisten) und „22.10.2026, 17:33:12“ (`toLocaleString`).
2. **Die Unterschrift im Einsatzbericht mit „Uhr“** wie im PDF.
3. **Das Änderungsprotokoll (alter/neuer Wert) bleibt roh** -- dafür bräuchte der Server die Art der Spalte.

## Stufe 4, R2 Nachrunde (1.9.47–): Pause je Tag, Listen auf eigene Seite

Auftrag von Tobias (23.10.2026): Festlegungen R2 bestätigt außer 1.9.45 Nr. 4 (die Listen bleiben nicht unter „Heute“, sondern kommen auf eine
eigene Seite „Heute / Offen“); Pausenregel je Tag (nur neue Buchungen, Schwellen „mehr als“), Kleinigkeiten auf „Heute“, Nebenbefunde aus R2
(Bauteil löschen, Tagesgrenzen der Befunde).

### R2 Nachrunde, Vorweg (1.9.47): die Rückfrage beim Löschen eines Prüfpunkts

- **Befund**: `klicktest_monteurin_regeln` war beim ersten Lauf der Nachrunde rot („Löschen: Punkt weg, kein Knopf mehr“, dazu „nicht neu
  geladen (#reportList)“), allein wiederholt einmal grün, einmal rot. Eine Messkopie des Klicktests (Scratchpad) zeichnete `rueckfrage()`,
  `speichern()` und die `close`-Ereignisse des Dialogs auf: 4 von 4 Läufen bekam die zweite Rückfrage (nach „Abbrechen“) gleich nach dem
  Öffnen ein `close`, antwortete „nein“, kein DELETE ging hinaus. Das `close` stammte vom Schließen der ersten Rückfrage -- Chrome liefert es
  verspätet aus, hier beim nächsten Öffnen; `rueckfrage()` nahm jedes `close` als Esc.
- **Behebung**: `beiEsc` antwortet „nein“ nur, wenn der Dialog beim `close` wirklich zu ist (Esc schließt ihn, dann kommt `close`); ein `close`
  bei offenem Dialog zählt nicht. Andere Vorlagen haben keinen `close`-Listener.
- **Tests**: neu `tests/test_v475_rueckfrage_close.py` (2 Tests, node mit Attrappe des Dialogs): verspätetes `close` nach dem neuen Öffnen ->
  die Rückfrage bleibt offen, „Löschen“ antwortet „ja“ (Angriff); Esc -> „nein“ (Gegenprobe). Messkopie danach 3 von 3 grün (einmal traf das
  alte `close` sichtbar ein und wurde ignoriert). **Gegenprobe** (alter Stand, jedes `close` als Esc): der Angriffstest rot; der Klicktest in
  diesem Lauf grün -- er trifft das Rennen nur manchmal, der node-Test immer.

### R2 Nachrunde, Punkt 1 (1.9.48): Pausenregel je Tag

- **Umsetzung**: `app/time_tracking.py::pause_nach_zeitregel()` rechnet je Tag (`buchungen_am_tag()`, `_anwesend_der_buchung()`), `ende_rechnen()`
  liefert dazu `tag_zusammen`/`tag_buchungen`, `tag_stand()` für die Antworten (`app/routers/time_tracking.py::_mit_tag()`: Nachtrag, Stopp, Ende
  nachtragen, Zeitart wechseln; Gruppen-Stopp für den, der stoppt). Schwelle `>` in `automatic_break_minutes_for_duration()`. „Heute“: Ergebnis
  nach dem Feierabend (`#zeitErgebnis`, grün, bleibt bis zum nächsten Laden), „Tag zusammen“ in der Vorschau; Zeiterfassung der Monteurin: Hinweis
  nach Stopp (neu mit Ergebnis), Ende nachtragen und Nachtrag. Einstellungen „über … h“. Herleitung: `docs/archiv/zeiterfassung-und-abwesenheit.md`,
  „Pausenregel je Tag (seit 1.9.48)“.

**Festlegungen 1.9.48 (Bitte bestätigen)**

1. „Mehr als“ wirkt nur für neue Buchungen: `automatic_break_minutes_for_duration()` hat keinen anderen Aufrufer als `pause_nach_zeitregel()`;
   Pausen, die nach „ab“ entstanden, bleiben.
2. Der Tag ist der Starttag (`work_date`) aller gebuchten Zeiten der Person; eine laufende zählt nicht mit. Anwesenheit = Ende − Beginn, ohne
   Uhrzeiten Stunden + Pause.
3. Frisst die fehlende Pause die ganze neue Buchung (07:00–13:00, dann 13:00–13:20 -> 20 min Pause), schließen Stopp, Gruppen-Stopp, Ende
   nachtragen und Wechsel sie mit 0 h; ein Nachtrag mit Von/Bis wird abgelehnt (wie bisher bei 0 h). Eine eingegebene Pause über der
   Anwesenheit bleibt abgelehnt.
4. „Tag zusammen“ = gebuchte Stunden (netto) des Tages samt der neuen, als h:mm; angezeigt nur, wenn der Tag mehr als diese eine Buchung hat.
5. Gruppen-Stopp: die Antwort nennt den Tag dessen, der stoppt (wenn er Mitglied ist); jedes Mitglied rechnet seinen eigenen Tag.
6. Das Beispiel der Vorgabe (07:00–12:00, Wechsel, Werkstatt bis 16:00 -> 2. Buchung − 45 min, Tag 8,25 h) widerspricht „genau 9:00 -> 30“:
   der Tag hat genau 9:00 h -> 30 min, Tag 8,50 h. Gebaut nach der Regel; der Test prüft bis 16:00 (− 30 min, 8,50 h) und bis 16:15 (− 45 min,
   8,50 h); je Buchung wären es 9,00 bzw. 9,25 h.
7. Die Einstellungen sagen „über … h“ (Liste der Pausenregeln und Beschriftung des Felds).
8. „Heute“: das Ergebnis nach „Feierabend“/„Feierabend eintragen“ steht in der Karte „nichts läuft“, bis die Seite neu lädt; die Zeiterfassung
   der Monteurin zeigt nach dem Stopp jetzt auch ein Ergebnis (bis dahin keins).

**Tests und Prüfung**

- Neu `tests/test_v474_pause_je_tag.py` (16 Tests): Schwelle (genau 6:00 -> 0, 6:01 -> 30, genau 9:00 -> 30, 9:01 -> 45), Wechsel mittags (bis
  16:00 und 16:15), zwei Buchungen à 5 h -> 45 min, Nachtrag für den Vormittag nach der Nachmittagsbuchung (fehlender Teil beim Nachtrag, frühere
  unverändert), eingegebene Pause 60 -> 60, Dauer-Buchung zählt mit, Gruppenmitglied mit eigener früherer Buchung, frühere Buchungen unverändert,
  fehlende Pause frisst die letzte Buchung (Stopp 0 h, Nachtrag 422), Vorschau = Buchung samt „Tag zusammen“, Feierabend nennt „Tag zusammen“.
- Angepasste Erwartungen: `test_v100::test_timer_start_stop_computes_net_hours_and_prevents_parallel_timer` 07:00–16:00, Pause 30: alt 8,25 h,
  neu 8,50 h; `test_v102::test_group_timer_starts_and_stops_all_members` ebenso alt 8,25 h, neu 8,50 h;
  `test_v104::test_work_time_models_and_automatic_break_on_timer` alt 6,00 -> 30 und 9,00 -> 45, neu 6,00 -> 0, 6,0167 -> 30, 9,00 -> 30,
  9,0167 -> 45, der Stopp bis 16:15 statt 16:00 (45 min, 8,50 h statt 8,25 h); `test_v424` Beschriftung „Pausenregel – über Brutto-Stunden“
  statt „ab“; `klicktest_heute` Ole: neu die Fahrzeit 06:00–06:45 in den Testdaten und Ende 15:45 statt 16:00 (die Baustelle allein hat
  dann genau 9:00 h, je Buchung wären es 30 min -- mit 16:00 gaben je Buchung und je Tag dieselben 45 min, die Gegenprobe P1 blieb im
  Klicktest grün); Vorschau alt [„Anwesend 9:15 h · Pause nach Zeitregel − 0:45 h“, „Gebucht werden 8,50 h“], neu [„Anwesend 9:00 h · Pause
  nach Zeitregel − 0:45 h“, „Gebucht werden 8,25 h“, „Tag zusammen 9:00 h“]; gebucht alt [9,25 h, 45 min, 8,50 h], neu Fahrzeit [0,75, 0, 0,75]
  und Baustelle [9,00 h, 45 min, 8,25 h]; neu die Prüfungen „Ergebnis mit Tag zusammen“ (Mia und Ole) und ein Bild dunkel.
- **Gegenproben** (Marker GEGENPROBE, byte-genau zurück): P1 je Buchung statt je Tag -> 7 Tests rot, `klicktest_heute` 3 Prüfungen rot;
  P2 Schwelle „ab“ -> 5 rot (v474, v104); P3 eingegebene Pause nicht als Mindestpause -> 1 rot; P4 „Tag zusammen“ ohne frühere Buchungen ->
  3 rot, `klicktest_heute` 3 rot; P5 Pause nicht auf die Anwesenheit begrenzt -> 1 rot.

### R2 Nachrunde, Punkt 2 (1.9.49): „Heute / Offen“

- **Umsetzung**: Seite `/mobil/offen` (`app/routers/pages.py::field_open_page()`, für jede Rolle wie das Objekt), Vorlage `mobil_offen.html`
  (umgezogen: `.ds-seite`, Monteursrahmen, `seitenkopf("Offen", mit_pfad=true, tablet=true)` mit Pfad „Heute“; in `UMGEZOGEN` als
  `HEUTE_OFFEN`). Die vier Abschnitte (Reihenfolge wie bisher die Listen: offene Berichte, Mängel zur Beseitigung, offene Checklisten,
  Wartungen an meinen Objekten) tragen `hidden`, bis ihr Laden etwas bringt; danach „Nichts offen.“ oder der Sprung zum Anker. Markup und
  Verhalten der Listen aus `mobil.html` übernommen (Karten, „Beseitigt melden“ mit Kennung, „Wartung durchführen“), Knöpfe 48 px hoch.
  Neu `GET /api/field-view/offene-berichte` (`app/routers/field_view.py`, Mitarbeiter aus der Anmeldung, ohne Modul „wartungen“ leer). „Heute“
  (`mobil.html`): Listen, ihr CSS und Skript entfernt; `renderOffen()` verlinkt auf `/mobil/offen#…`, Zeile „Wartungen an meinen Objekten“ aus
  `heute.offen["wartungen"]` (`app/heute.py::offen()`, zählt Verträge aus `list_relevant_contracts_for_employee()`). Reiter „Heute“ auch auf
  `/mobil/offen` aktiv (`_mobile_header.html`). Bildgrundlage: Aufnahme `mobil_offen` für Büro und Monteurin.

**Festlegungen 1.9.49 (Bitte bestätigen)**

1. „Heute / Offen“ liegt unter `/mobil/offen`, Titel „Offen“, Pfad „Heute“; im Monteursrahmen für jede Rolle (wie das Objekt), umgezogen.
2. Ein Abschnitt erscheint nur, wenn er beim Laden etwas enthält; scheitert sein Laden, erscheint er mit der Meldung (ein Fehler bleibt nie
   unsichtbar); ist alles leer, steht „Nichts offen.“.
3. Nach „Beseitigt melden“ bleibt der Abschnitt mit der Bestätigung stehen, auch wenn er leer wird („Keine Mängel zur Beseitigung.“) -- er
   verschwindet erst beim nächsten Laden; es lädt nur die Mängelliste neu (bis 1.9.48 lud „Heute“ ganz neu, um die Zahl in „Offen“
   nachzuziehen).
4. Die Reihenfolge der Zeilen in „Offen“ bleibt (Berichte, Checklisten, Mängel), „Wartungen an meinen Objekten“ kommt als letzte dazu und
   zählt Verträge, nicht Objekte; die Seite behält die Reihenfolge der bisherigen Listen.
5. Der Sprung zum Abschnitt geschieht, wenn alle vier geladen sind (vorher stehen sie nicht); 80 px Abstand oben für den festen Kopf.
6. `GET /api/field-view/today` liefert `draft_reports` weiter (Tests nutzen es), `/mobil` liest es nicht mehr; die neue Schnittstelle gibt
   nur `id`, `order_id`, `order_number`, `report_type_label` heraus.
7. „Beseitigt melden“, „Meldung senden“ und „Wartung durchführen“ sind 48 px hoch (bis dahin 44 px bzw. etwa 33 px), das Kennzeichen
   „Fällig“ nur so breit wie sein Text; sonst sehen die Listen aus wie bisher (ihr Umbau ins neue Design gehört zu Stufe 4 als Ganzes).

**Tests und Prüfung**

- Neu `tests/test_v476_heute_offen.py` (8 Tests): „Heute“ ohne Listen, endet mit „Nächste Tage“, keine Anfragen der Listen im Skript; Zeilen
  von „Offen“ mit Zielen auf `/mobil/offen#…` samt Wartungen; Seite im Monteursrahmen für drei Rollen (Kopf, Pfad, Reiter, Abschnitte
  verborgen); das Seitenskript in node: genau die nicht leeren Abschnitte, alles leer -> „Nichts offen.“, ein Fehler beim Laden bleibt
  sichtbar; Schnittstelle nur eigene Entwürfe und nur die Felder der Seite; `offen()["wartungen"]` zählt Verträge an Objekten meiner Einsätze.
- Angepasste Erwartungen: `test_v354::test_mobil_page_carries_the_defect_section` alt `/mobil`, neu `/mobil/offen`; `test_v457` FAELLE neu
  `/mobil/offen` für Monteurin und Büro, Tablet-Variante neu `mobil_offen.html`; `test_v260` Seiten der Monteurin neu `/mobil/offen`;
  `test_v441` neu `HEUTE_OFFEN` in `UMGEZOGEN`; `test_v431::test_dateinamen_eindeutig_und_die_bisherigen_zuerst` alt 298 Bilder (240 in
  412/1440), neu 310 (248); `klicktest_heute` „Offen“ alt [Titel, Zahl, „#offene-…“, Ziel auf der Seite vorhanden] für Berichte und
  Checklisten, neu [Titel, Zahl, „/mobil/offen#…“] mit der Zeile Wartungen (Wartungsvertrag neu in den Testdaten), neu die Prüfungen „Heute
  ohne Listen“ und fünf zu „Heute / Offen“, Bilder „Heute“ bis zum Seitenende, neu `heute_offen_hoch_hell/dunkel`;
  `klicktest_maengel_monteur` alt `/mobil`, neu `/mobil/offen` (5 Stellen); `klicktest_behinderungsanzeige_abschluss` alt `/mobil` mit
  Bereitschaft der Checklistenliste, neu `/mobil/offen` mit `offenLaedt` verborgen (2 Stellen); `klicktest_abnahmeprotokoll` neu die
  Prüfung „„Heute / Offen“ nennt kein Abnahmeprotokoll“; `test_v399` `ABSCHLIESSEND` alt (`mobil.html`, `sendReport`), neu
  (`mobil_offen.html`, `sendReport`); `test_v356::test_mobil_page_has_the_optional_note` alt `/mobil`, Rumpf bis `loadDefects`, neu
  `/mobil/offen`, Rumpf bis `ladeMaengel` (beide erst im vollen Lauf rot gewesen).
- **Gegenproben**: P1 jeder Abschnitt sichtbar -> 3 Tests rot, `klicktest_heute` 1 rot; P2 `offen()` ohne Wartungen -> 1 rot,
  `klicktest_heute` 1 rot; P3 Schnittstelle mit allen Feldern -> 1 rot; P4 kein Sprung -> `klicktest_heute` 1 rot (in node nicht prüfbar);
  P5 „Heute“ ohne Zeile Wartungen -> 1 rot.

### R2 Nachrunde, Punkt 3 (1.9.50): Kleinigkeiten auf „Heute“

- **Umsetzung**: `app/heute.py::checklisten_titel()` für die Zeilen der Checklisten im Einsatz; `mobil.html`: Wege des Einsatzes als
  `knopf knopf-neutral knopf-klein` (48 px, 12 px Abstand, umbrechend; Hover ohne Linkfarbe), `#assignmentsList:empty{display:none}`, Feld der
  Signalkarte mit `--ds-feld-rand-signal`; `ds.css`: Token hell #7A848C, dunkel #6E7A83, Prüfpaare `feld-rand-signal/signal-hell` und
  `feld-rand-signal/flaeche` (hell 3,41 und 3,81, dunkel 3,48 und 3,74).

**Festlegungen 1.9.50 (Bitte bestätigen)**

1. „Checkliste <Name>“ setzt der Server (`checklisten_titel()`); beginnt der Name schon mit „Checkliste“ (Groß- und Kleinschreibung egal),
   bleibt er unverändert; gilt für die Zeile im Einsatz auf „Heute“, nicht für die Liste auf „Heute / Offen“ (Überschrift „Offene Checklisten“).
2. Die beiden Wege sind neutrale Knöpfe nebeneinander (Rahmen linie-stark, 48 px, 12 px Abstand), auf schmalem Gerät untereinander.
3. Der leere Einsatzbereich wird bei einer Zeit von gestern ausgeblendet (`:empty`), nicht aus der Seite genommen.
4. Neues Token `--ds-feld-rand-signal` nur für ein Feld auf der Signalfläche; dunkel gleich `--ds-feld-rand` (dort schon 3,48 : 1).

**Tests und Prüfung**

- Neu `tests/test_v477_heute_kleinigkeiten.py` (8 Tests): Titel der Checkliste (fünf Fälle), Wege als neutrale Knöpfe 48 px ohne
  Link-Regel, leerer Einsatz ohne Platz, Feldrahmen mit Token, Prüfpaaren und Kontrast hell und dunkel (und dass feld-rand hell nicht reicht).
- Angepasste Erwartungen: `test_v472::test_einsatz_mit_eigenen_berichten_und_checklisten` Titel alt „Sicherheitscheck“, neu „Checkliste
  Sicherheitscheck“; `test_v472::test_seite_masse_und_spalten` alt `.einsatz-wege a{min-height:48px`, neu `.knopf-klein{height:48px`;
  `test_v432::test_kontrast_der_pruefpaare_hell_und_dunkel` alt 41 Prüfpaare, neu 43; `klicktest_heute` Einsatz alt „Sicherheitscheck“, neu
  „Checkliste Sicherheitscheck“, neu die Prüfungen „Wege als neutrale Knöpfe 48 px“, „Ole hoch: 16 px“ und „Feldrahmen ≥ 3 : 1 hell und
  dunkel“ (an den berechneten Farben gemessen).
- **Gegenproben**: P1 Checkliste ohne Vorsatz -> 4 Tests rot, `klicktest_heute` 1 rot; P2 „Bericht anlegen“ wieder Link -> 1 rot, Klicktest 1
  rot; P3 leerer Einsatz nimmt Platz -> 1 rot, Klicktest 1 rot (32 px); P4 feld-rand auf der Signalfläche -> 1 rot, Klicktest 1 rot (hell 2,84).

### R2 Nachrunde, Nebenbefund Bauteil (1.9.51): ein Prüfpunkt sperrt das Löschen

- **Befund (aus R2)**: `delete_roof_component()` prüfte nur Prüfpunkte unterschriebener Berichte (seit 1.2.16) und Befunde (seit 1.2.17).
  Ein Wartungsbericht legt je Bauteil Prüfpunkte an (`InspectionItem.roof_component_id`, Fremdschlüssel ohne ON DELETE) -- steckte das Bauteil
  nur in einem Entwurf, lief das Löschen unter PostgreSQL in den Fremdschlüssel (500), unter SQLite blieb ein Verweis ins Leere.
- **Umsetzung** (Muster `VorlagenpunktInBerichten`, 1.9.43): Zeile des Bauteils `FOR UPDATE`, dann Zahl der Berichte mit einem Prüfpunkt zum
  Bauteil; mehr als null -> `BauteilInBerichten` (Router 409), sonst wie bisher die Befunde (400) und Löschen; eine `IntegrityError` beim Commit
  (ein Verweis, den die Sperre nicht abfing) -> ebenfalls `BauteilInBerichten`, nie 500.

**Festlegungen 1.9.51 (Bitte bestätigen)**

1. Jeder Prüfpunkt sperrt das Löschen, gleich ob der Bericht Entwurf oder unterschrieben ist; die Meldung nennt die Zahl der Berichte und
   „Archivieren geht weiter.“ (409). Kein ON DELETE SET NULL oder CASCADE.
2. Die Sperre bei erfassten Befunden bleibt wie seit 1.2.17 (400, eigener Text) und wird erst nach den Prüfpunkten geprüft.
3. Nicht mitgebaut: „Dachfläche löschen“ (`delete_roof_area()`) prüft Prüfpunkte, Berichte und Befunde zur Fläche ebenso wenig und reißt
   über die Kaskade ihre Bauteile mit -- unter PostgreSQL dieselbe 500, sobald ein Bericht die Fläche oder eines ihrer Bauteile nennt. Gemeldet,
   nicht behoben (eigener Punkt, Vorschlag: dieselbe Regel).

**Tests und Prüfung**

- Neu `tests/test_v478_bauteil_loeschen.py` (4 Tests): Bauteil in einem bzw. zwei Entwürfen -> 409 mit Anzahl, Bauteil und Verweise
  unverändert; ein Bauteil ohne Prüfpunkt gelöscht, das gesperrte archivierbar; unter PostgreSQL (Wegwerf-Schema) Sperre statt
  `IntegrityError`, die Sitzung bleibt brauchbar.
- Angepasste Erwartung: `test_v213::test_sync_inspection_items_is_purely_additive` alt „Bauteil eines Entwurfs löschen erlaubt“, neu
  `BauteilInBerichten`, das Bauteil wird archiviert (der Rest des Tests unverändert).
- **Gegenproben**: P1 kein Prüfpunkt sperrt (das Netz bleibt) -> 4 Tests rot (v478 SQLite zweimal, v213 zweimal); der Test unter
  PostgreSQL bleibt grün -- das Netz fängt den Fremdschlüssel und antwortet mit derselben Sperre; P2 dazu ohne Netz -> 5 rot, auch unter
  PostgreSQL (`IntegrityError` wie bis 1.9.50); P3 Router 400 statt 409 -> 2 rot.

### R2 Nachrunde, Nebenbefund Befunde (1.9.52): Tagesgrenzen in Europe/Berlin

- **Umsetzung**: `app/berlin_time.py::berlin_tag_beginn_utc()`, `app/findings.py::list_findings()` filtert `date_from`/`date_to` damit.
  Herleitung: `docs/archiv/zeiterfassung-und-abwesenheit.md`, „Tagesgrenzen gespeicherter Zeitstempel (seit 1.9.52)“.

**Festlegungen 1.9.52 (Bitte bestätigen)**

1. Der Datumsfilter der Befundliste meint Kalendertage in Europe/Berlin (`date_to` einschließlich), an den Tagen der Zeitumstellung mit der
   Mitternacht vor der Umstellung.

**Tests und Prüfung**

- Neu `tests/test_v479_befunde_tage_berlin.py` (7 Tests): Tagesbeginn in UTC (Sommer, Winter, beide Umstellungstage); ein Befund kurz nach
  Mitternacht in Berlin (Sommer und Winter) und kurz vor Mitternacht steht an seinem Tag, nicht am Vortag oder Folgetag, auch mit nur einer
  Grenze. Keine angepasste Erwartung.
- **Gegenproben**: P1 Filter mit UTC-Mitternacht (Stand bis 1.9.51) -> 2 Tests rot (nach Mitternacht, Sommer und Winter); P2 Tagesbeginn
  ohne Zeitzone -> 6 rot. Der Fall „kurz vor Mitternacht“ bleibt in beiden grün (dort lag auch die alte Grenze richtig).

## Stufe 4, R2 Nachrunde 2 (1.9.53–): „Tag zusammen“ verständlich, Dachfläche löschen

Auftrag von Tobias (23.10.2026): Festlegungen der R2-Nachrunde bestätigt außer 1.9.48 Nr. 4 (ersetzt durch Punkt 1); zu 1.9.48 Nr. 6: das
Beispiel der Vorgabe war falsch, „mehr als“ gilt wie gebaut. Punkte: „Tag zusammen“ erklärt die Pause, Dachfläche löschen wie das Bauteil,
`_unterschreiben()` im Klicktest misst erst nach dem Speichern.

### R2 Nachrunde 2, Punkt 1 (1.9.53): „Tag zusammen“ erklärt die Pause

- **Umsetzung**: `app/time_tracking.py::_anwesend_summe()` für Pausenregel, `ende_rechnen()` (Vorschau, Stopp, Wechsel, Ende nachtragen) und
  `tag_stand()` (Antworten); `mobil.html`: Vorschau mit „Tag zusammen“ in der ersten Zeile, `ergebnisBuchung()` in der Reihenfolge der
  Vorschau, `ergebnisTeile()` (jeder Teil ohne Umbruch in sich); `time_tracking_field.html`: `ergebnisText()` für Stopp, Ende nachtragen und
  Nachtrag. Herleitung: `docs/archiv/zeiterfassung-und-abwesenheit.md`, „„Tag zusammen“ = Anwesenheit des Tages (seit 1.9.53)“.

**Festlegungen 1.9.53 (Bitte bestätigen)**

1. „Tag zusammen“ = Anwesenheit aller gebuchten Zeiten des Starttags samt der neuen, vor der Pause (eine reine Dauer zählt mit Stunden +
   Pause) -- in der Antwort auf eine Buchung (auch dem Gruppen-Stopp für den, der stoppt) und in der Vorschau; ersetzt 1.9.48 Nr. 4.
2. Vorschau: eine Zeile „Anwesend … · Tag zusammen … · Pause nach Zeitregel − …“, darunter „Gebucht werden … h“; die eigene Zeile „Tag
   zusammen“ (1.9.48) entfällt.
3. Ergebnis auf „Heute“: „<Was>: anwesend … · Tag zusammen … · Pause nach Zeitregel − … · gebucht … h“ (bis 1.9.52 „<Was>: … h · Pause … ·
   Tag zusammen …“); das Ergebnis für die Gruppe bleibt im Aufbau, „Tag zusammen“ ist dort die Anwesenheit dessen, der stoppt.
4. Zeiterfassung der Monteurin ebenso: „Gestoppt/Ende nachgetragen/Nachgetragen: anwesend 9:15 h · [Tag zusammen …] · Pause 0:45 h · gebucht
   8,50 h“ (bis 1.9.52 „gebucht 8,50 h · anwesend 9,25 h · Pause 45 min“) -- Dauern in h:mm, gebuchte Stunden dezimal.
5. Ein Teil des Ergebnisses zwischen „ · “ bricht nicht in sich um (vorher stand „3,50“ am Zeilenende und „h“ darunter).

**Tests und Prüfung**

- Neu: `tests/test_v480_tag_zusammen_anzeige.py` (5 Tests, Texte der Seiten in node zusammengesetzt: Ergebnis auf „Heute“ mit und ohne frühere
  Buchung, Vorschau, Zeiterfassung mit und ohne frühere Buchung); in `tests/test_v474_pause_je_tag.py` zwei neue Tests (ohne frühere Buchung:
  „Tag zusammen“ = eigene Anwesenheit, eine Buchung; der echte Tag: Werkstatt 4,25 / Tag 9,25 / 45 / 3,50, Tag gebucht 8,50); neuer Klicktest
  `scripts/klicktest_echter_tag.py` (7 Prüfungen, Bild nach dem Feierabend und Vorschau ohne frühere Buchung).
- Angepasste Erwartungen: `test_v474::test_nachtrag_vormittag_nach_der_nachmittagsbuchung` „Tag zusammen“ alt 8 (gebucht), neu 8,5
  (Anwesenheit 3:30 + 5:00); `test_v474::test_vorschau_gleich_buchung_mit_frueherer_buchung_am_tag` alt Ende 16:00 -> (45 min, 8,50 h, Tag 9,25,
  2), neu Ende 15:45 -> (anwesend 9, Tag 9,75, 45 min, 8,25 h, 2) -- der Fall der Vorgabe; `test_v474::test_feierabend_nennt_tag_zusammen` alt
  1 + gebuchte Stunden, neu 1 + Anwesenheit; `klicktest_heute` Mia Ergebnis alt „Feierabend gebucht: 0,0x h · Pause 0:00 h · Tag zusammen
  3:15 h“, neu „Feierabend gebucht: anwesend 0:00 h · Tag zusammen 3:15 h · Pause nach Zeitregel − 0:00 h · gebucht 0,0x h“; Ole Vorschau alt
  [„Anwesend 9:00 h · Pause nach Zeitregel − 0:45 h“, „Gebucht werden 8,25 h“, „Tag zusammen 9:00 h“], neu [„Anwesend 9:00 h · Tag zusammen 9:45 h ·
  Pause nach Zeitregel − 0:45 h“, „Gebucht werden 8,25 h“]; Ole Ergebnis alt „Feierabend gestern eingetragen: 8,25 h · Pause 0:45 h · Tag
  zusammen 9:00 h“, neu „Feierabend gestern eingetragen: anwesend 9:00 h · Tag zusammen 9:45 h · Pause nach Zeitregel − 0:45 h · gebucht 8,25
  h“; `klicktest_monteurin_regeln` alt „Ende nachgetragen: gebucht 8,50 h · anwesend 9,25 h · Pause 45 min“, neu „Ende nachgetragen: anwesend
  9:15 h · Pause 0:45 h · gebucht 8,50 h“.
- **Gegenproben**: P1 „Tag zusammen“ als gebuchte Stunden -> 4 Tests rot, `klicktest_echter_tag` 1 rot („Tag zusammen 8:30 h“); P2 Vorschau
  ohne „Tag zusammen“ -> 1 rot, `klicktest_heute` 1 rot; P3 „Tag zusammen“ auch ohne frühere Buchung -> 1 rot, `klicktest_echter_tag` 1 rot
  (Pia); P4 Zeiterfassung in alter Reihenfolge -> 2 rot, `klicktest_monteurin_regeln` 1 rot.

### R2 Nachrunde 2, Punkt 2 (1.9.54): Dachfläche löschen wie das Bauteil

- **Befund (1.9.51 Nr. 3)**: `delete_roof_area()` sperrte bei Wartungsvertrag, Abnahme und Mangel, prüfte Einsatzberichte aber nicht; die
  Bauteile gingen per ORM-Kaskade mit. Fremdschlüssel ohne ON DELETE auf die Fläche: `ServiceReport.roof_area_id`, `ServiceReportRoofArea`,
  `InspectionItem.roof_area_id`, `ServiceReportMaterial.roof_area_id`; auf ihre Bauteile: `InspectionItem.roof_component_id`,
  `Finding.roof_component_id`. Unter PostgreSQL 500, unter SQLite Verweise ins Leere.
- **Umsetzung** (Muster `BauteilInBerichten`, 1.9.51): Zeile der Fläche `FOR UPDATE`; nach den bisherigen Sperren die Zahl der Berichte, die
  die Fläche oder eines ihrer Bauteile nennen (`_berichte_mit_dachflaeche()`, eine UNION, jeder Bericht einmal); mehr als null ->
  `DachflaecheInBerichten` (Router 409); eine `IntegrityError` beim Commit -> ebenfalls `DachflaecheInBerichten`.

**Festlegungen 1.9.54 (Bitte bestätigen)**

1. Es sperrt jeder Bericht, der die Fläche als seine Fläche, an einem Prüfpunkt oder an einem Material nennt, und jeder, der eines ihrer
   Bauteile an einem Prüfpunkt oder Befund nennt -- Entwurf oder unterschrieben; die Meldung nennt die Zahl der Berichte (jeder einmal) und
   „Archivieren geht weiter.“ (409).
2. Die bisherigen Sperren (Wartungsvertrag, Abnahme, Mangel; 400, eigene Texte) kommen zuerst und bleiben unverändert.
3. Eine Fläche ohne Bericht wird wie bisher samt Bauteilen, Schichten und Skizze gelöscht.

**Tests und Prüfung**

- Neu `tests/test_v481_dachflaeche_loeschen.py` (6 Tests): Fläche mit einem bzw. zwei Wartungsberichten (Entwürfe) -> 409 mit Anzahl, Fläche,
  Bauteil, Verweise, Prüfpunkte und Befunde unverändert; ein Bericht nur mit einem Befund am Gully der Fläche -> 409; ein Bericht nur mit
  Material an der Fläche -> Sperre; ohne Bericht gelöscht samt Bauteil, eine gesperrte Fläche archivierbar; unter PostgreSQL (Wegwerf-Schema)
  Sperre statt `IntegrityError`, eine freie Fläche danach löschbar. Keine angepasste Erwartung.
- **Gegenproben**: P1 Berichte sperren nicht (Netz bleibt) -> 5 rot (der PostgreSQL-Test bleibt grün: das Netz fängt den Fremdschlüssel);
  P2 dazu ohne Netz -> 6 rot, auch PostgreSQL; P3 nur die Fläche des Berichts zählt (Befund am Bauteil und Material vergessen) -> 2 rot; P4
  Router 400 statt 409 -> 4 rot.

### R2 Nachrunde 2, Punkt 3 (1.9.55): Unterschrift im Klicktest erst nach dem Speichern

`_unterschreiben()` wartet zuerst auf Ruhe (`Tab.warte_auf_ruhe()`) -- Herleitung, Wächter und Gegenprobe in
`docs/archiv/testablauf-und-klicktests.md`, „Unterschrift im Klicktest erst nach dem Speichern (1.9.55)“. Keine Festlegung außer der zum
Testablauf, keine angepasste Erwartung.

### R2 Nachrunde 2, Nachtrag (1.9.56): Test „Zeitart wechseln ohne Lücke“ unabhängig von der Sekunde

Gefunden im vollen Lauf vor dem Commit von 1.9.55 (ein roter Test, der mit 1.9.55 nichts zu tun hatte, Regel 15): Herleitung, Festlegung zum
Testablauf, angepasste Erwartung und Gegenprobe in `docs/archiv/testablauf-und-klicktests.md`, „Test mit laufender fester Uhr prüft keine
Sekunde (1.9.56)“.

## Stufe 4, R3 (1.9.57–): „Meine Zeiten“

Auftrag von Tobias (23.10.2026): Vorlage `bildgrundlage/entwurf-stufe4/zeiten-nachtragen.html` (freigegeben, nur quer); „Meine Zeiten“
ersetzt die Reiter „Zeiterfassung“ und „Stundenzettel“, Starten und Stoppen nur noch auf „Heute“, Nachtragen und Ändern nach der Tagesregel,
„Pausen neu rechnen“ nur auf Klick, Zeitart-Kacheln quer 3 und hoch 2 Spalten. Befund zuerst: keine Funktion fällt still weg.

### Befund (vor dem Umbau): was „Zeiterfassung“ und „Stundenzettel“ der Monteurin können -- und wo es danach steht

Reiter „Zeiterfassung“ (`/time-tracking` für die Rolle `field`, `time_tracking_field.html`):

| # | Funktion heute | danach |
|---|---|---|
| Z1 | laufende Zeit sehen (Uhr, Auftrag · Projekt · Zeitart) | „Heute“, Karte Arbeitszeit; „Meine Zeiten“: Zeile „läuft seit HH:MM“ |
| Z2 | Zeit stoppen | „Heute“: „Feierabend“ |
| Z3 | zusätzliche Pause beim Stoppen (Mindestpause) | „Meine Zeiten“: „⋮ Ändern“ → „Weitere Angaben“ → „Pause mindestens“ (nach dem Feierabend) |
| Z4 | Ende nachtragen (Zeit von früher), mit zusätzlicher Pause | „Heute“: Signalkarte; „Meine Zeiten“: Zeile mit Link zu „Heute“; längere Pause danach wie Z3 |
| Z5 | Schnell starten: Auftrag, Zeitart-Kacheln, Vorschlag Schlechtwetter | „Heute“ (nichts läuft) |
| Z6 | Schnell starten mit Tätigkeit | „Heute“: „⋮ Mit Tätigkeit starten“ |
| Z7 | Kolonne starten (Kolonne, Mitglieder, Auftrag, Zeitart, Tätigkeit) | „Heute“: „⋮ Für die Kolonne starten“ (nur Kolonnenführer) |
| Z8 | Kolonnenzeit für alle stoppen | „Heute“: „Feierabend für die Gruppe“ (seit 1.9.45) |
| Z9 | Nachtrag für die Kolonne (Stunden je Person) | „Meine Zeiten“: „⋮“ neben „+ Nachtragen“ → „Nachtrag für die Kolonne“ |
| Z10 | Meine Kolonnenbuchungen (14 Tage): Mitglieder, „selbst geändert“, Ändern und Löschen für alle | „Meine Zeiten“: an der eigenen Buchung der Gruppe „⋮ Für die Kolonne ändern / löschen“; Mitglieder im Dialog |
| Z11 | Kennzahlen heute: produktiv, Fahrzeit, gesamt | Kachel „Heute“ (gesamt); Fahrzeit und produktiv als Monatswerte in der Karte „Monat“ |
| Z12 | Meine Buchungen (14 Tage): Zeitart, Datum, Auftrag, „gebucht von“, Notiz, Stunden | „Meine Zeiten“: Buchungen des Monats (‹ ›), Tag als Kopfzeile; „gebucht von“, Tätigkeit und Notiz als zweite Zeile |
| Z13 | Buchung nachtragen: Auftrag, Datum, Von/Bis oder Dauer, Zeitart, Tätigkeit, Notiz | Dialog „Zeit nachtragen“ (Datum, Zeitart, Von, Bis, Auftrag); Tätigkeit und Notiz unter „Weitere Angaben“; Dauer für die Monteurin nicht mehr (Server 422) |
| Z14 | Ergebnis nach Nachtrag, Stopp, Ende nachtragen | Vorschau im Dialog vor dem Speichern, danach die Meldung über den Buchungen; Stopp und Ende auf „Heute“ (Ergebnis dort) |
| Z15 | Buchung ändern | „⋮ Ändern“ (derselbe Dialog, Von/Bis) |
| Z16 | Buchung löschen (Rückfrage des Browsers) | „⋮ Löschen“ mit Rückfrage auf der Seite |
| Z17 | „abgeschlossen“ statt Ändern/Löschen | abgeschlossener Monat: Hinweis, kein „⋮“, kein Nachtragen in den Zeitraum |
| Z18 | Abwesenheit beantragen (Kategorie, Art, Von, Bis, Notiz) | Karte „Abwesenheit“: „+ Antrag“ (Dialog) |
| Z19 | eigene Anträge (Status, Freigabe-Notiz), Zurückziehen | im Dialog der Abwesenheit wie bisher; die Karte nennt offene Anträge |
| Z20 | Hinweise: kein Mitarbeiter verknüpft, keine eigenen Aufträge | oben auf „Meine Zeiten“ |
| Z21 | `?order_id=` (Einsatzbericht „Zeiterfassung (Auftrag)“) wählt den Auftrag vor | Weiterleitung auf „Meine Zeiten“, Auftrag im Dialog „Zeit nachtragen“ vorgewählt |
| Z22 | Nachtragen, Ändern, Löschen nur mit „manuelle Buchungen erlaubt“ | unverändert |

Reiter „Stundenzettel“ (`/mobil/stundenzettel`, `field_timesheet.html`):

| # | Funktion heute | danach |
|---|---|---|
| S1 | Monat wählen | ‹ › über den Buchungen |
| S2 | je Tag: Auftrag, Tätigkeit, Stunden, Tagessumme | Buchungen je Tag mit Kopfzeile und Summe; Tätigkeit in der zweiten Zeile |
| S3 | Monatssumme | Kachel „<Monat>“ und Karte „Monat“ („x,xx h an n Tagen“) |
| S4 | PDF herunterladen | Karte „Monat“: „Stundenzettel als PDF“ |
| S5 | Hinweis „Liste gekürzt“ | entfällt: die Seite holt den Monat vollständig (`limit=None` im Server) |

### R3, Nur Von und Bis für die Monteurin (1.9.60)

- **Umsetzung**: `app/permissions.py::zeit_nur_mit_von_bis()` (heute `field`), `app/meldungen.py::NUR_VON_BIS`; `POST /api/time-entries`
  ohne Von/Bis und `PUT /api/time-entries/{id}` mit `hours` 422 für diese Rolle; Seitenroute des Einsatzberichts mit
  `zeit_nur_mit_von_bis`, die Karte „Erfasste Zeiten“ mit `teVon`/`teBis` statt `teHours` (welches Feld sichtbar ist, legt der Server
  fest; das Skript nimmt Von/Bis nur, wenn das Feld ausdrücklich sichtbar ist).

**Festlegungen 1.9.60 (Nr. 1, 2 und 4 bestätigt am 23.10.2026; Nr. 3 ersetzt durch 1.9.63 Nr. 1)**

1. Eine reine Dauer trägt nur das Büro ein: für die Monteurin lehnen Nachtrag ohne Von/Bis und Ändern mit Stunden mit 422 und der
   Meldung „Bitte Von und Bis angeben – eine reine Dauer trägt nur das Büro ein.“ ab.
2. Ändern ohne Zeiten (Tätigkeit, Notiz, Auftrag, Zeitart) bleibt der Monteurin erlaubt; mit Von/Bis rechnet es nach der Tagesregel
   (1.9.57).
3. Kolonnen-Nachtrag und -Ändern („Stunden je Person“) bleiben eine Dauer -- die Gruppenbuchung ist nicht betroffen.
4. Einsatzbericht: die Karte „Erfasste Zeiten“ zeigt der Monteurin Von und Bis statt „Stunden“, dem Büro unverändert die Stunden.

**Tests und Prüfung**

- Neu `tests/test_v485_nur_von_bis.py` (6 Tests): die Regel nur für `field`; Nachtrag mit Stunden als Monteurin 422 (nichts gebucht), mit
  Von/Bis gebucht, als Büro wie bisher; Ändern mit Stunden als Monteurin 422, mit Von/Bis und nur Notiz gespeichert, als Büro wie bisher;
  Einsatzbericht zeigt der Monteurin Von/Bis, dem Büro die Stunden.
- Die Ablehnung kommt nach den Rechteprüfungen: was nicht erlaubt ist (fremde Person, fremder Auftrag, abgeschlossener Monat, Konto ohne
  Mitarbeiter), bleibt 403 bzw. die Meldung „Konto ohne Mitarbeiter“ -- zuerst stand sie vorn, sieben Tests sahen 422 statt 403.
- Angepasste Erwartungen (Test: alt -> neu, jeweils weil die Monteurin dort eine reine Dauer buchte; geprüft wird weiter dasselbe):
  - `test_v437::_manuell` (Einzelbuchung, Kontrolle „für sich selbst geht es“): `hours` 3 -> Von/Bis 07:00–10:00.
  - `test_v265::test_time_entries_start_and_manual_create_accept_an_activity_value`: `hours` 2,5 -> 07:00–09:30.
  - `test_v329::test_auftragswechsel_ohne_neue_position_laesst_die_alte_fallen`: PUT mit `order_id` und `hours` -> nur `order_id`.
  - `test_v462::test_nachtrag_4_stunden_ohne_abzug[dauer]`, `::test_eine_dauer_bleibt_gebuchte_arbeitszeit`: die Dauer als Monteurin -> als
    Büro (die Dauer-Regel selbst unverändert).
  - `test_v300::_entry` (Abschluss): `hours` 2 -> 07:00–09:00.
  - `test_v303` (2 Tests): Max ändert die eigene Buchung der Gruppe mit `hours` 7 -> 07:00–14:30 (30 min Pause, 7 h); beim zweiten Test
    jetzt mit geprüftem Status 200.
  - `test_v299::_manual` (Auftragsbezug): `hours` 2 -> 07:00–09:00.
  - `klicktest_monteur_dachflaechen`: Monteur „Zeit buchen“ mit „2,5“ Stunden -> 07:00–09:30 (gebucht 2,5 h wie bisher), dazu die Prüfung
    „Von und Bis statt Stunden“.
- **Gegenproben**: P1 Nachtrag mit Dauer als Monteurin angenommen -> 1 rot (test_v485); P2 Ändern mit Stunden angenommen -> 1 rot; P3
  Einsatzbericht zeigt der Monteurin Stunden -> 1 rot und Klicktest rot („Von und Bis statt Stunden“, Buchung ohne Stunden abgelehnt).

### R3, Meine Zeiten (1.9.59)

- **Umsetzung**: `app/templates/mobil_zeiten.html` (neu; Skript auf oberster Ebene, Ereignisse in `binden()` -- die node-Tests führen
  das Skript bis davor aus), Route `/mobil/zeiten`, `/mobil/stundenzettel` und `/time-tracking` (field) als Weiterleitung mit
  `dk_ohne_seite`; `_mobile_header.html` zwei Reiter; `app/meine_zeiten.py`: Daten der Dialoge (Zeitarten, Tätigkeiten, buchbare Aufträge,
  „Nachtragen erlaubt“, Standardpause, Kolonnen, eigene Gruppenbuchungen des Monats, Arten der Abwesenheit, `mitarbeiter_id`), Gruppen in
  einer Abfrage (`_gruppen()`); `time_tracking_field.html` und `field_timesheet.html` entfernt.

**Festlegungen 1.9.59 (Nr. 1–3, 5 und 7–16 bestätigt am 23.10.2026; Nr. 4 ohne den Teil Kolonne bestätigt, der Teil Kolonne ersetzt
durch 1.9.63 Nr. 1; Nr. 6 ersetzt durch 1.9.61 Nr. 1)**

1. „Meine Zeiten“ unter `/mobil/zeiten` (eigene Adresse wie „Heute / Offen“); Reiter „Heute · Meine Zeiten“; `/time-tracking` leitet für die
   Monteurin dorthin (ein `?order_id=` nur als Zahl), `/mobil/stundenzettel` immer; das Büro behält `/time-tracking`.
2. Die Seite steht in `AUFGESCHOBEN` (Stufe 4; die Vorlage hat keinen Seitenkopf), wie „Heute“.
3. Zeile: in der Datumsspalte (96 px) Von–Bis, dann „Zeitart · Auftrag“, rechts gebucht; zweite Zeile Tätigkeit · Notiz · „gebucht von …“
   (nur wenn ein anderer gebucht hat); laufend ohne Stunden und ohne „⋮“, von früher mit „Feierabend auf „Heute“ eintragen“.
4. „⋮“ an jeder gebuchten Zeile außerhalb des Abschlusses: Ändern und Löschen nur mit „manuelle Buchungen erlaubt“; an der eigenen
   Gruppenbuchung des Kolonnenführers dazu „Für die Kolonne ändern / löschen“; „Nachtrag für die Kolonne“ im „⋮“ neben „+ Nachtragen“
   (Kolonnenführer, manuelle und Gruppenbuchungen erlaubt). Kolonnen-Nachtrag und -Ändern bleiben „Stunden je Person“ wie bisher (eine
   Dauer, keine Pausenregel).
5. Dialog „Zeit nachtragen“ / „Zeit ändern“: Datum, Zeitart, Von, Bis, Auftrag; unter „Weitere Angaben“ Tätigkeit, Notiz und „Pause
   mindestens“ (leer = nach Zeitregel; beim Ändern mit dem Hinweis „Bisher abgezogen …“), immer zugeklappt -- beim Ändern nennt der
   Knopf Tätigkeit und Notiz der Buchung (aufgeklappt rutschten Vorschau und Knopf bei 620 px Höhe aus dem Bild). Knopf aus der
   Vorschau „x,xx h nachtragen“ bzw. „x,xx h speichern“, ohne Vorschau „Nachtragen“/„Speichern“.
6. Der Nachtrag schickt als Mindestpause nur „Pause mindestens“ (sonst 0) -- die alte Seite setzte die Standardpause der Zeitregeln ein;
   jetzt gilt wie beim Feierabend die Pausenregel des Tages. Der Kolonnen-Nachtrag schickt die Standardpause wie bisher.
7. Eine Buchung ohne Uhrzeiten (Dauer, z. B. aus dem Büro) ändert die Monteurin nur mit Von und Bis (Hinweis im Dialog).
8. Löschen fragt in einem Dialog auf der Seite nach (Buchung: mit dem Hinweis auf „Pausen neu rechnen“; Kolonnenbuchung: selbst geänderte
   bleiben); „Zurückziehen“ eines Antrags fragt in seiner Zeile nach (bis 1.9.58 confirm()).
9. „Pausen neu rechnen“ steht in der Kopfzeile des Tages, nicht im Abschluss; der Klick lädt die Vorschau frisch vom Server, „So buchen“
   bucht genau sie (sonst 409 mit Meldung).
10. Nach dem Speichern zeigt die Seite den Monat der Buchung; „›“ nicht über den laufenden Monat hinaus.
11. Abwesenheit: die Karte nennt die offenen Anträge, „+ Antrag“ öffnet den Dialog mit Formular und „Meine Anträge“ (wie bisher).
12. Monat: Summe, Tage, „davon Fahrzeit · produktiv“ des angezeigten Monats (bis 1.9.58 die Kennzahlen „Heute“), „Stundenzettel als PDF“
    für diesen Monat.
13. Hinweise oben: „Konto ohne Mitarbeiter“ (app/meldungen.py), keine eigenen Aufträge.
14. `meine_zeiten()` liest die Gruppen aller Zeilen in einer Abfrage (bis dahin eine je Zeile).
15. Bildgrundlage: „meine_zeiten“ (Büro und Monteurin) statt „zeiterfassung_monteur“ und „stundenzettel“.
16. Die Pausenprüfung eines Tags (`pausen_vorschau()`) lässt eine reine Dauer stehen: sie ist gebuchte Arbeitszeit, ihre Pause bleibt; sie
    zählt mit Stunden + Pause vor den Buchungen mit Uhrzeiten zur Anwesenheit des Tags (wie beim Buchen). Neu gerechnet werden nur Buchungen
    mit Von und Bis.

**Befund im Klicktest (behoben in dieser Version)**: ein Tag mit nur einer reinen Dauer (Kolonnen-Nachtrag 8 h, Pause 0) zeigte „Pause
abgezogen 0:00 h · nach Zeitregel 0:30 h“, „Pausen neu rechnen“ hätte 7,50 h gebucht -- `pausen_vorschau()` (1.9.57) rechnete auch eine
Dauer nach der Regel neu. Seit 1.9.59 bleibt sie (Festlegung 16), Tests `test_v483::test_reine_dauer_behaelt_ihre_pause` und
`::test_dauer_zaehlt_vor_den_zeiten_zum_tag`.

**Tests und Prüfung**

- Neu `scripts/klicktest_meine_zeiten.py` (45 Prüfungen, stehende Uhr Mi 14.10.2026 10:00): alte Adressen und Reiter, quer und hoch hell
  und dunkel, Kacheln ohne laufende Zeit, Tage und Zeilen, Abwesenheit und Monat, PDF, Nachtragen mit „Tag zusammen“, Ändern mit
  Mindestpause, Löschen mit Rückfrage, „Pausen neu rechnen“, Kolonne ändern, nachtragen, löschen, abgeschlossener September, Antrag und
  Zurückziehen, „gebucht von“, Zeit von früher, Konto ohne Mitarbeiter -- jede Funktion aus dem Befund hier oder in `klicktest_heute`.
- `test_v483`: zwei Tests zur Dauer (Befund oben), 15 Tests.
- Angepasste Erwartungen (Test: alt -> neu):
  - `test_v260::test_field_reaches_only_the_pages_it_needs`: `/mobil/stundenzettel` und `/time-tracking` 200 -> 302 auf `/mobil/zeiten`; dazu
    `/mobil/zeiten` 200.
  - `test_v264::test_field_gets_the_reduced_template_without_sidebar_or_group_booking` (jetzt `test_field_is_sent_to_meine_zeiten`): 200 mit
    `time_tracking_field.html` -> 302 auf „Meine Zeiten“, dort ohne Seitenleiste, Büro-Gruppenbuchung und Mitarbeiterfeld, Kolonne verborgen.
  - `test_v264::test_field_gets_reduced_template_even_with_order_id_query_param`: 200 -> 302 auf `/mobil/zeiten?order_id=1`, sonst ohne Zahl.
  - `test_v265::test_quick_and_manual_activity_selects_are_present`: `quickActivity`/`manualActivity` auf `/time-tracking` -> `startTaetigkeit`
    auf `/mobil`, `zdTaetigkeit` auf `/mobil/zeiten`.
  - `test_v269` (2 Tests), `test_v272::test_monteursseiten_nehmen_die_alten_farbnamen_zentral`: Seiten des Monteurskopfs mit
    `field_timesheet.html`, `time_tracking_field.html` -> mit `mobil_zeiten.html`.
  - `test_v272::test_kopf_ist_eine_zeile_mit_kachel_reitern_lupe_und_konto`: Reiter Heute · Zeiterfassung · Stundenzettel -> Heute · Meine Zeiten.
  - `test_v272::test_einsaetze_ist_auch_auf_den_seiten_darunter_aktiv`: aktiv auf `/time-tracking` und `/mobil/stundenzettel` -> „Meine Zeiten“
    auf `/mobil/zeiten`.
  - `test_v313::test_every_page_listing_time_entries_reads_total_and_shows_truncation_notice`: Liste mit den beiden alten Seiten -> ohne sie,
    `mobil_zeiten.html` nicht darunter (holt den Monat vollständig).
  - `test_v328::test_seitenleiste_des_monteurs_auf_der_berichtsseite`: Links `/mobil`, `/time-tracking`, `/mobil/stundenzettel` -> `/mobil`,
    `/mobil/zeiten`.
  - `test_v329::test_mobile_zeitbuchung_aendern_laesst_pause_und_lv_position` (jetzt `test_meine_zeiten_aendern_laesst_die_lv_position`):
    Schlüssel mit `hours`, Pause 45 bleibt -> Schlüssel mit `von`/`bis` (dazu `pause_minuten`), LV-Position bleibt, Pause nach der Tagesregel
    (0 bei 6:00 h).
  - `test_v329::test_mobile_kolonnenbuchung_aendern_laesst_pause_und_lv_position`: `saveCrewDialog` der Zeiterfassung -> `kolonneSpeichern`
    von „Meine Zeiten“ (Schlüssel gleich).
  - `test_v390`: begründeter Zeitpunkt `updateClock` der alten Seite entfällt; `today()` der alten Seite -> `berlinToday()` als Vorgabedatum
    der Dialoge.
  - `test_v400`: Ausnahme `field_timesheet.html | init` entfällt; „Monatswechsel des Stundenzettels“ -> „Monatswechsel von Meine Zeiten“
    (`laden()`, der zuletzt gewählte Monat gewinnt).
  - `test_v407`: drei Handler-Ausnahmen der alten Seite entfallen (Liste kürzer).
  - `test_v424`: drei Felder der alten Seite -> zwei von „Meine Zeiten“ (`zdPause`, `kdStunden`); Mindestzahl der Felder 88 -> 87.
  - `test_v425::test_jede_umleitung_einer_seitenroute_steht_an_der_route`: umleitend login, dashboard -> dazu Stundenzettel und Zeiterfassung.
  - `test_v401::test_jede_weiterleitung_des_servers_hat_ein_festes_oder_geprueftes_ziel`: 4 -> 6 Weiterleitungen.
  - `test_v431`: Seiten ohne Büro ohne `time_tracking_field.html`; Bilder 310 -> 302, die bisherigen 248 -> 244.
  - `test_v440`: Nutzer der Meldung „Konto ohne Mitarbeiter“ `field_timesheet.html`, `time_tracking_field.html` -> `mobil_zeiten.html`;
    gezeichnete Seiten `/time-tracking` (field) und `/mobil/stundenzettel` -> `/mobil/zeiten`.
  - `test_v441`: `AUFGESCHOBEN` mit den beiden alten Seiten -> mit `mobil_zeiten.html` (Stufe 4).
  - `test_v450` (3 Tests): Dialoge der Zeiterfassung -> `zeitDialogOeffnen()`/`kolonneDialogOeffnen()` (Ergebnisse gleich).
  - `test_v480::test_ergebnis_in_der_zeiterfassung` (jetzt `test_ergebnis_auf_meine_zeiten`): „Ende nachgetragen: … · Pause 0:45 h · gebucht
    …“ -> „Nachgetragen: … · Pause nach Zeitregel − 0:45 h · gebucht …“ (wie „Heute“).
  - `klicktest_monteurin_regeln`: offene Anzeige der Zeiterfassung, abgelehnter Start, „Bitte das Ende angeben.“, „Ende nachgetragen: anwesend
    9:15 h · Pause 0:45 h · gebucht 8,50 h“, Uhr und „Zeit stoppen“ -> Zeile „läuft seit 06:45“ mit Weg zu „Heute“; auf „Heute“ Start
    gesperrt, „Bitte die Uhrzeit des Feierabends angeben.“, „Feierabend gestern eingetragen: anwesend 9:15 h · Pause nach Zeitregel − 0:45 h
    · gebucht 8,50 h“, Start über die Kachel.
  - `klicktest_teil_updates`: Buchung ändern -- Pause 45 bleibt -> mit Von/Bis, Pause nach der Tagesregel (0), 4,00 h, LV-Position bleibt;
    Kolonnenbuchung -- Meldung „Korrektur gespeichert“ -> „Kolonnenbuchung geändert.“
  - `klicktest_zeitbuchungen_liste`: Monteurin Hinweis „gekürzt“ (500 bzw. 2000) -> Vormonat vollständig, jede Buchung eine Zeile, kein Hinweis.
  - `klicktest_browser_datum`: `today()` und Monat des Stundenzettels -> Buchung von heute in der Liste, Vorgabedatum des Dialogs, Monat der
    Seite.
  - `klicktest_rahmen`: Reiter Heute · Zeiterfassung · Stundenzettel -> Heute · Meine Zeiten; Seiten `stundenzettel`/`zeiterfassung_monteur`
    -> `meine_zeiten`; Ecken `.card` -> `.zahl-karte`, `.zeiten-karte`.
  - `klicktest_monteur_navigation`, `klicktest_neue_ordnung`: Reiter wie oben.
  - Bildgrundlage: Aufnahmen `zeiterfassung_monteur` und `stundenzettel` -> `meine_zeiten`.
- **Gegenproben**: P1 reine Dauer wieder neu gerechnet -> 2 rot (test_v483, Dauer); P2 `/time-tracking` leitet die Monteurin nicht weiter -> 3
  rot (test_v264 2, test_v260); P3 Löschen ohne Rückfrage -> Klicktest rot („Rückfrage auf der Seite“, „Abbrechen lässt alles“).

**Offen (für 1.9.60)**: Die Karte „Erfasste Zeiten“ im Einsatzbericht bucht für die Monteurin noch eine Dauer -- lehnt der Server eine
reine Dauer von `field` ab (Auftrag R3, Punkt 3), muss sie Von/Bis bekommen; deshalb in einer eigenen Version mit der Ablehnung.

### R3, Heute (1.9.58)

- **Umsetzung**: `app/heute.py`: `taetigkeiten()`, in "nichts" `taetigkeiten`, `taetigkeit_pflicht` (Zeitregeln) und `kolonnen`
  (`list_crews_for_leader()`, nur mit Gruppenbuchungen); `app/templates/mobil.html`: „⋮“ in der Karte „nichts läuft“ (`dsMenue()` aus
  `_menue.html`), Dialog `#startDialog` (POST `/api/time-entries/start` bzw. `/api/time-entry-groups/start`, wie die Zeiterfassung), Kacheln
  `repeat(3,…)`, unter 1000 px `repeat(2,…)`.

**Festlegungen 1.9.58 (bestätigt am 23.10.2026)**

1. „⋮“ in „nichts läuft“ nur, wenn es etwas zu wählen gibt: „Mit Tätigkeit starten“ bei mindestens einer aktiven Tätigkeit, „Für die
   Kolonne starten“ nur für den Kolonnenführer und nur mit Gruppenbuchungen (der Start lehnte sonst ab).
2. Ein Dialog für beide: Auftrag aus der Karte vorgewählt, Zeitart die erste aktive (bzw. die angeklickte Kachel), Tätigkeit leer =
   „ohne Tätigkeit“; für die Kolonne alle Mitglieder angehakt, die eigene Person fest (wie die Zeiterfassung).
3. Verlangen die Zeitregeln eine Tätigkeit, öffnet auch eine Zeitart-Kachel den Dialog mit dieser Zeitart -- bis 1.9.57 lehnte der Server
   den Start über die Kachel ab (422).
4. „Quer 3 / hoch 2“ an derselben Grenze wie die Seite (unter 1000 px gilt als hoch); auch für „Zeitart wechseln“.
5. Der Dialog trägt die Ecke der Karte (im Monteursrahmen 16 px) statt der 20 px der Vorlage (Wächter `test_v460`); Maße sonst wie der
   Dialog der Vorlage zeiten-nachtragen (620 px, Felder 52 px, Knöpfe 56 px, Schließen 48 px).

**Tests und Prüfung**

- Neu `tests/test_v484_heute_starten.py`: Tätigkeiten und Kolonne in "nichts" (Mitglied ohne Kolonne), ohne Gruppenbuchungen keine Kolonne,
  Pflicht der Tätigkeit, inaktive Tätigkeit fehlt, Start mit Tätigkeit und für die Kolonne wie der Dialog (Mitglied 403), Kacheln 3/2,
  Menü und Dialog in der Seite.
- `scripts/klicktest_heute.py` erweitert (nur ergänzt): Kacheln quer 3 und hoch 2 („Zeitart wechseln“ und Start), Lea startet über „⋮ Mit
  Tätigkeit starten“ (bis 1.9.57 über die Kachel -- angepasste Erwartung: „Lea: gestartet“ jetzt mit Tätigkeit und Dialog zu), Ole startet
  über die Kachel, Kai stoppt die Gruppe und startet sie über „⋮ Für die Kolonne starten“.
- `klicktest_heute`: dazu „Lea 1440 px: Kacheln in 3 Spalten“ -- bei 1280 px ergab „so viele wie passen“ zufällig ebenfalls drei (die
  Gegenprobe P2 blieb dort zuerst grün).
- **Gegenproben**: P1 Kolonne auch ohne Gruppenbuchungen -> 1 rot (test_v484); P2 Kacheln wieder „so viele wie passen“ -> 1 rot
  (test_v484) und im Klicktest bei 1440 px 4 statt 3 Spalten; P3 Dialog startet ohne die Tätigkeit -> Klicktest rot („Lea: die
  Tätigkeit an der laufenden Zeit“ None).

### R3, Server (1.9.57)

Fund im vollen Lauf vor dem Commit: `pausen_vorschau()` rief `automatic_break_minutes_for_duration()` selbst auf -- der Wächter
`test_v462::test_eine_pausenregel_keine_zweite_rechnung` lässt das nur `pause_nach_zeitregel()`. Behoben über den Parameter `vorher`
(Anwesenheit und abgezogene Pause der früheren Buchungen statt der gespeicherten): die Vorschau rechnet über die eine Pausenregel, mit
denselben Zahlen (test_v483 unverändert grün).

- **Umsetzung**: `app/time_tracking.py`: `buchungen_am_tag(…, ohne_id)`, `pause_nach_zeitregel(…, ohne_id)`, `nachtrag_nach_zeitregel()` mit
  gebucht, „Tag zusammen“ und `ohne_id`, `update_entry(…, von, bis, mindestpause)`, `pausen_vorschau()`, `pausen_neu_rechnen()`
  (`PausenVorschauVeraltet`); `app/routers/time_tracking.py`: `GET …/nachtrag-vorschau`, `GET …/tagespause`, `POST …/pausen-neu-rechnen`, PUT mit
  von/bis/pause_minuten (Schema `TimeEntryUpdate`); `app/meine_zeiten.py` (`meine_zeiten()`, `tagessumme()`, auch im Stundenzettel als PDF),
  `GET /api/field-view/meine-zeiten`.

**Festlegungen 1.9.57 (Nr. 1, 3 und 5–9 bestätigt am 23.10.2026; Nr. 2 ersetzt durch 1.9.62 Nr. 3, Nr. 4 durch 1.9.62 Nr. 5)**

1. Ändern mit Von/Bis rechnet wie ein Nachtrag: Pause aus dem Tag ohne die alte Fassung dieser Buchung, gebucht nach der Rundung der
   Zeitregeln (bis 1.9.56 rundete Ändern nicht); Ändern mit Dauer (Büro) wie bisher.
2. „Pause mindestens“ beim Ändern ist die Mindestpause dieses Ändern; ohne Angabe 0 -- eine früher eingegebene längere Pause gilt nach einem
   Ändern nicht weiter (sie ist nicht gespeichert).
3. „Nach Zeitregel“ eines Tags ist, was die Regel den Buchungen in der Reihenfolge des Tags gäbe (nach Beginn, reine Dauern zuletzt; jede
   bekommt, was dem Tag fehlt, höchstens ihre Anwesenheit; ohne Mindestpausen); der Tag passt, wenn die Summen gleich sind -- eine andere
   Verteilung bei gleicher Summe passt. **Für reine Dauern ersetzt durch Festlegung 1.9.59 Nr. 16**: eine Dauer behält ihre Pause und
   zählt vor den Buchungen mit Uhrzeiten (bis dahin rechnete die Prüfung sie neu, Befund im Klicktest 1.9.59).
4. Eine bewusst längere Pause lässt den Tag als „passt nicht“ erscheinen; „Pausen neu rechnen“ würde sie auf die Zeitregel zurücksetzen --
   die Vorschau zeigt das vor dem Klick, nichts geschieht von selbst.
5. „Pausen neu rechnen“ ändert nur Buchungen mit anderer Pause (Pause und gebucht nach der Rundung), bucht genau die gezeigte Vorschau (sonst
   409), eine Buchung einer Gruppe gilt danach als einzeln geändert; im Verlauf die Feldänderungen und eine Zeile „Pausen neu gerechnet“ mit der
   Pause des Tages alt -> neu; im abgeschlossenen Zeitraum nur ein Admin.
6. Kacheln: heute, diese Woche (Montag bis Sonntag) und der angezeigte Monat, je gebuchte Stunden; eine laufende Zeit zählt nicht und steht
   ohne Stunden.
7. Summen addieren die gespeicherten Stunden (vier Stellen) und runden das Ergebnis; die Zeilen zeigen gerundet -- die Summe der angezeigten
   Zeilen kann um 0,01 von der Summe abweichen (wie im Stundenzettel als PDF).
8. Tage neueste zuerst, die Zeilen eines Tags in seiner Reihenfolge, eine laufende Zeit zuletzt.
9. `GET /api/field-view/meine-zeiten` zeigt immer die eigenen Zeiten (Mitarbeiter nur aus der Anmeldung), für jede Rolle mit Mitarbeiter.

**Tests und Prüfung**

- Neu `tests/test_v483_meine_zeiten_server.py` (13 Tests): Nachtrag mit und ohne Vorbuchung (Vorschau = Buchung), Rundung gleich; Ändern ohne
  die alte Fassung, andere Buchung unverändert, mit Mindestpause, im abgeschlossenen Monat 403, fremd 403/404, Von ohne Bis 422; Löschen ->
  Hinweis am Tag, nichts von selbst; „Pausen neu rechnen“ genau die Vorschau, veraltet 409, Verlauf; gleiche Summe passt; im abgeschlossenen
  Monat 403; Kacheln ohne laufende Zeit; Monat und Tage; dieselbe Summenfunktion im PDF (AST).
- Angepasst (nur Aufbau): `test_v326_monteur_datengrenze` -- `QUERY_JE_ROUTE` mit `nachtrag-vorschau` und `tagespause`, die Testdaten mit
  `heute`, `ERLAUBT_JE_ROUTE` mit der Notiz der eigenen Buchung in `meine-zeiten`.
- **Gegenproben**: P1 Ändern mit der alten Fassung im Tag -> 1 rot; P2 „passt“ nach Verteilung statt Summe -> 1 rot; P3 „Pausen neu rechnen“
  ohne Abgleich -> 1 rot; P4 laufende Zeile mit Stunden -> 1 rot; P5 Mindestpause beim Ändern ignoriert -> 1 rot.

## Stufe 4, R3 Nachrunde (1.9.61–): Kolonne mit Von/Bis, keine Standardpause, Mindestpause merken

Auftrag von Tobias (23.10.2026), Start auf 16c8571. Festlegungen R3 bestätigt, außer 1.9.57 Nr. 2 und 4 (-> Punkt 3), 1.9.59 Nr. 4 (Teil
Kolonne) und 1.9.60 Nr. 3 (-> Punkt 1), 1.9.59 Nr. 6 (-> Punkt 2).

1. Kolonne mit Von/Bis: Kolonnen-Nachtrag und -Ändern des Kolonnenführers mit einer Von/Bis-Angabe für die angehakten Mitglieder; Pause und
   Rundung je Mitglied nach seinem Tag (dieselbe Funktion); Vorschau je Mitglied; reine Dauer für die Kolonne nur noch das Büro
   (Kolonnenführer 422).
2. Standardpause entfällt: überall nur die Pause nach Zeitregel je Tag und die selbst eingetragene Mindestpause; zuerst alle Stellen
   auflisten, die sie lesen; die Einstellung aus den Zeitregeln entfernen, die Spalte bleibt und wird nirgends mehr gelesen (Wächter).
3. Eingetragene Mindestpause merken: neue Spalte (Migration, Rückweg verweigert, sobald ein Wert gespeichert ist); „Pausen neu rechnen“ nie
   unter diese Mindestpause, alte Buchungen ohne Wert mit der abgezogenen Pause als Mindestpause; „passt nicht“ nur, wenn neu rechnen etwas
   ändern würde; „Ändern“ belegt „Pause mindestens“ damit vor.
4. Für R5 vormerken: ändert das Büro die Stunden einer Buchung, bleiben Von/Bis stehen.

### R3 Nachrunde, Punkt 2 (1.9.61): die Standardpause entfällt

**Befund (vor dem Umbau): wer die Standardpause liest** (`TimeTrackingSettings.default_break_minutes`, Einstellung „Manuelle Standardpause /
Fallback“ in den Zeitregeln, Vorgabe 0):

| # | Stelle | was sie damit tat | danach |
|---|---|---|---|
| L1 | `app/schemas.py::TimeTrackingSettingsOut` | Feld der Zeitregeln samt Grenze 0–240 (Validator) | entfernt; eine mitgeschickte wird nicht übernommen |
| L2 | `app/time_backoffice.py::time_settings_dict()`, `update_time_settings()` | lesen und speichern der Zeitregeln | entfernt |
| L3 | `app/meine_zeiten.py::meine_zeiten()` (`standardpause`) -> `mobil_zeiten.html::kolonneSpeichern()` | Kolonnen-Nachtrag schickte sie als `break_minutes` | entfernt; Pause 0 |
| L4 | `app/templates/settings.html` | Feld `defaultBreak` (Lesen, Anzeigen, Speichern) | entfernt |
| L5 | `app/templates/time_tracking.html` (Büro) | Vorgabe in `timeSettings`, Vorbelegung „Pause“ im Nachtrag (ohne Buchung) und im Gruppen-Nachtrag | entfernt; Vorbelegung 0 bzw. die Pause der Buchung |
| L6 | `app/audit.py` (`FIELD_LABELS`) | Bezeichnung „Standardpause (Min.)“ für Einträge im Änderungsverlauf | **außerhalb der Zeitbuchung, nicht geändert** (alte Einträge bleiben lesbar) |
| L7 | `scripts/klicktest_teil_updates.py` | Testdaten setzten 30 min | entfernt |
| L8 | `tests/test_v424_zahlgrenzen.py`, `tests/test_v450_auswahl_fremdschluessel.py` | Abgleich des Felds, Seitenkontext | angepasst |

Nicht mitgezählt: die Spalte selbst in `app/models.py` und in der Baseline-Migration `2befd7907eef` (bleibt), die Doku (historisch).
Kein Server-Weg einer Zeitbuchung (Stopp, Ende nachtragen, Nachtrag, Ändern, Gruppen) las die Standardpause -- sie kam nur über die beiden
Seiten (L3, L5) als eingegebene Mindestpause in die Buchung.

- **Umsetzung**: L1–L5 und L7 entfernt; `app/models.py` mit Kommentar an der Spalte (nirgends mehr gelesen); Karte „Zeitregeln“ neu
  geordnet (Standard-Arbeitszeitmodell neben der Rundung, die vier Häkchen paarweise darunter -- ohne das Feld stand das Modell allein in
  einer Zeile und die Häkchen versetzt).

**Festlegungen 1.9.61 (Bitte bestätigen)**

1. Keine Zeitbuchung nimmt mehr die Standardpause: Feierabend, Nachtrag, Kolonne und Büro nur mit der Pause nach Zeitregel je Tag und der
   eingetragenen Mindestpause (leer = 0); der Kolonnen-Nachtrag schickt keine Pause mehr (ersetzt 1.9.59 Nr. 6).
2. Die Spalte `time_tracking_settings.default_break_minutes` bleibt in der Datenbank (keine Migration); außer der Spalte in `app/models.py`
   nennt kein Code unter `app/` sie (Wächter `test_v486`, Bezeichner `default_break_minutes`, `defaultBreak`, `standardpause`).
3. Die Bezeichnung „Standardpause (Min.)“ in `app/audit.py` bleibt (Änderungsverlauf alter Einträge; liest keinen Wert für eine Buchung).
4. Die Schnittstelle der Zeitregeln (`GET/PUT /api/time-backoffice/settings`) liefert den Wert nicht mehr; ein mitgeschickter wird still nicht
   übernommen (kein 422 -- wie jedes andere unbekannte Feld).
5. Büro-Zeiterfassung: „Pause“ im Nachtrag ist 0 (beim Ändern die Pause der Buchung), im Gruppen-Nachtrag 0.
6. Karte „Zeitregeln“: Standard-Arbeitszeitmodell neben der Rundung, die vier Häkchen paarweise darunter.

**Tests und Prüfung**

- Neu `tests/test_v486_keine_standardpause.py` (5 Tests): Wächter über `app/` (`.py`, `.html`, `.js`, `.css`, groß/klein genau -- die
  Erklärung „Standardpause“ in Kommentaren zählt nicht) mit eigener Gegenprobe über einen Leser in `tmp_path`; Zeitregeln ohne das Feld
  (GET, PUT mit 45 nicht übernommen, Seite ohne `defaultBreak` und ohne „Standardpause“); 5:00 h bei alter Spalte 30 über Feierabend (Ende
  nachtragen), Nachtrag (Monteurin, Von/Bis) und Kolonne (Büro, Dauer) je 0 min Pause; Vorbelegung im Büro.
- Angepasste Erwartungen:
  - `test_v424_zahlgrenzen`: Eintrag `defaultBreak` in `ABGLEICH` entfernt, Untergrenze der Einträge 87 -> 86.
  - `test_v450_auswahl_fremdschluessel`: Seitenkontext ohne `default_break_minutes`/`standardpause` (nur Aufbau).
  - `klicktest_teil_updates`: Testdaten ohne Standardpause 30 (nur Aufbau, geprüft wird dasselbe).
  - `klicktest_neue_ordnung`: neue Prüfung „Zeitregeln ohne Standardpause“ (kein Feld, kein Text).
- **Gegenproben**: P1 Nachtrag nimmt die Standardpause als Mindestpause (Router) -> 2 rot (Wächter, 5:00 h); P2 „Meine Zeiten“ liefert sie
  wieder -> 1 rot (Wächter); P3 Büro belegt den Gruppen-Nachtrag mit ihr vor -> 2 rot (Wächter, Vorbelegung).

### Vorgemerkt für R5 (Punkt 4)

- Ändert das Büro die Stunden einer Buchung (reine Dauer im Ändern), bleiben Von und Bis stehen -- Beginn und Ende passen dann nicht mehr zu
  den Stunden. Zu klären in R5 (Büro): Von/Bis leeren, anpassen oder mit Hinweis stehen lassen.

### R3 Nachrunde, Punkt 3 (1.9.62): die eingetragene Mindestpause wird gemerkt

- **Umsetzung**: Spalte `time_entries.min_break_minutes` (Integer, leer erlaubt), Migration **`c4f2a8e61d35`** (auf `b7e3d91c4a58`;
  `downgrade()` verweigert, solange eine Buchung einen Wert hat). `app/time_tracking.py::mindestpause_der_buchung()` (gemerkter Wert, ohne
  die abgezogene Pause); gesetzt in `create_manual_entry()` (`min_break_minutes`, ohne Angabe die Pause), `stop_timer()`,
  `stop_group_timer()`, `zeitart_wechseln()` (0), `update_entry()` (mit Von/Bis die Mindestpause des Ändern, sonst `min_break_minutes`, wenn
  angegeben), `create_group_manual_entry()` und `update_group()` (die Pause der Gruppe); `pausen_vorschau()` gibt jeder Buchung mindestens
  ihre Mindestpause, `pausen_neu_rechnen()` schreibt bei einer Buchung ohne Wert die bisherige Pause als Mindestpause fest. Router: PUT ohne
  `pause_minuten` mit der gemerkten Mindestpause, Dauer mit `hours`/`break_minutes` merkt die Pause; `nachtrag-vorschau` mit `entry_id` ohne
  `pause_minuten` ebenso. `TimeEntryOut.min_break_minutes`, „Meine Zeiten“ je Zeile `mindestpause`; `mobil_zeiten.html` belegt „Pause
  mindestens“ beim Ändern vor und nennt sie im Knopf „Weitere Angaben“. Im Änderungsverlauf heißt die Spalte „Pause mindestens (Min.)“
  (`app/audit.py`; im ersten Lauf der Suite fehlte der Name, `test_v436::test_jedes_protokollierte_feld_hat_einen_namen` und
  `test_v438::test_namen_der_historie_sind_lesbar` waren rot).

**Festlegungen 1.9.62 (Bitte bestätigen)**

1. Neue Spalte `time_entries.min_break_minutes`, leer erlaubt (Migration `c4f2a8e61d35`); Rückweg verweigert, sobald ein Wert gespeichert ist
   (wie 1.9.42).
2. Gesetzt: Nachtrag = „Pause mindestens“ (leer 0), eine reine Dauer = die eingetragene Pause; Ändern mit Von/Bis = `pause_minuten`; Ändern
   einer Dauer mit Stunden oder Pause (Büro) = die Pause; Kolonne (Nachtrag, Ändern) = die Pause der Gruppe; Feierabend, Gruppen-Feierabend
   und „Ende nachtragen“ = die eingegebene Pause, ohne Eingabe 0; Zeitart wechseln = 0; eine laufende Zeit hat noch keinen Wert.
3. Ändern ohne `pause_minuten` behält die gemerkte Mindestpause (Regel 22; ersetzt 1.9.57 Nr. 2 „ohne Angabe 0“); ebenso die Vorschau beim
   Ändern ohne Angabe.
4. Eine Buchung von vor 1.9.62 (ohne Wert): die abgezogene Pause gilt als Mindestpause (`mindestpause_der_buchung()`); ändert „Pausen neu
   rechnen“ eine solche Buchung, schreibt es die bisherige Pause als Mindestpause fest -- sonst läge die Mindestpause danach bei der neuen,
   höheren Pause.
5. Die Pausenprüfung gibt jeder Buchung mindestens ihre Mindestpause; „passt nicht“ nur, wenn neu rechnen etwas ändern würde -- eine bewusst
   längere Pause lässt den Tag passen (ersetzt 1.9.57 Nr. 4). Gleiche Summe bei anderer Verteilung passt weiter (1.9.57 Nr. 3).
6. „Ändern“ belegt „Pause mindestens“ mit der Mindestpause vor, auch 0; der Knopf „Weitere Angaben“ nennt sie, wenn sie über 0 liegt
   („Pause mindestens 1:00 h“); der Hinweis darunter lautet „Bisher abgezogen: … Abgezogen wird die Pause nach Zeitregel, mindestens
   „Pause mindestens“.“
7. Antworten: `min_break_minutes` an jeder Zeitbuchung (roh, leer bei alten), `mindestpause` je Zeile von „Meine Zeiten“ (wirksam; laufend
   leer).

**Tests und Prüfung**

- Neu `tests/test_v487_mindestpause_merken.py` (8 Tests): Nachtrag mit und ohne „Pause mindestens“; Feierabend ohne und mit Pause, „Ende
  nachtragen“, Zeitart wechseln; Ändern setzt sie und behält sie ohne Angabe (auch die Vorschau), nur die Notiz lässt sie; Büro: Dauer und
  Kolonne merken die Pause; 08:00–12:00 und 12:30–16:30 mit 60, die erste gelöscht -> kein Hinweis, Pause bleibt 60 (Gegenprobe im Test:
  ohne Mindestpause 30 -> 0); Mindestpause über der Regel passt; alte Buchungen ohne Wert: nach dem Löschen nicht nach unten, 0 -> 30 nach
  oben und danach 0 festgeschrieben; „Meine Zeiten“ liefert die Mindestpause (gemerkt, alt, laufend) und der Dialog belegt sie vor.
- Neu `tests/test_v488_mindestpause_migration.py` (2 Tests): Bestand auf `b7e3d91c4a58` (eine Buchung mit Uhrzeiten und Pause, eine Dauer),
  hoch ohne Änderung einer Zeile, runter exakt wie vorher, mit Wert Rückweg verweigert -- SQLite und PostgreSQL (Wegwerf-Schema).
- Angepasste Erwartungen (`klicktest_meine_zeiten`; die Buchung „Ändern“ der Testdaten ist jetzt eine von vor 1.9.62, ohne Wert):
  - „Ändern: vorbelegt“: acht Felder -> neun, dazu „Pause mindestens“ = „30“ (die abgezogene Pause).
  - „Ändern: „Weitere Angaben“ zu, der Knopf nennt Tätigkeit und Notiz“: „Weitere Angaben · Dachdeckung · Rinne geprüft“ -> „… · Pause
    mindestens 0:30 h“ (Name der Prüfung um „und Mindestpause“ ergänzt).
  - neu: leer gespeichert -> „0“ vorbelegt; mit 60 gespeichert -> „60“ vorbelegt, Knopf und Hinweis; Vorschau mit der gemerkten Mindestpause
    (− 1:00 h); Bild `meine_zeiten_aendern_mindestpause_hell`.
- `klicktest_teil_updates`, „Buchung ändern (Von/Bis): … Pause nach der Tagesregel“: Pause 0, gebucht 4,00 h -> Pause 45, gebucht 3,25 h
  (Prüfung umbenannt in „…, mindestens die gemerkte“). Die Buchung der Testdaten ist eine Dauer mit eingetragener Pause 45 min; seit 1.9.62
  belegt „Ändern“ sie als Mindestpause vor (Festlegungen 2 und 6) -- rot im ersten Endlauf von 1.9.62, die Erwartung war seit dieser
  Version veraltet.
- **Gegenproben**: P1 Pausenprüfung ohne Mindestpause -> 3 rot; P2 alte Buchung ohne Wert gilt als 0 -> 2 rot, Klicktest 2 rot (Vorbelegung
  „0“ statt „30“, Knopf ohne Mindestpause); P3 Ändern ohne Angabe nimmt 0 -> 1 rot; P4 Feierabend merkt die Pause nicht -> 1 rot; P5 Ändern
  ohne Vorbelegung -> 1 rot, Klicktest 4 rot; P6 neu rechnen schreibt die alte Pause nicht fest -> 1 rot; P7 Rückweg der Migration nicht
  verweigert -> 2 rot (SQLite und PostgreSQL).

### R3 Nachrunde, Punkt 1 (1.9.63): die Kolonne mit Von und Bis

- **Umsetzung**: `app/time_tracking.py::kolonne_rechnen()` (je Mitglied `nachtrag_nach_zeitregel()`, Fehler mit Namen, Bis vor Von vorab);
  `create_group_manual_entry(von=…, bis=…)` über `_kolonne_von_bis_anlegen()`, `update_group(von=…, bis=…, mindestpause=…)` (rechnet vor jeder
  Änderung, selbst geänderte bleiben), `_kolonne_kopf()` (Beginn, Ende, Stunden im Mittel, größte Pause), `kolonne_vorschau()`;
  `list_groups_initiated_by()` mit `von`, `bis`, `mindestpause`. Schemas: `TimeGroupManualCreate` (hours optional, von/bis, Validator),
  `TimeGroupUpdate` (von/bis/pause_minuten), `TimeKolonneVorschauOut`, `CrewGroupSummaryOut` mit von/bis/mindestpause. Router: POST ohne
  Von/Bis und PUT mit `hours` 422 für `zeit_nur_mit_von_bis()` (nach den Rechteprüfungen), neue Route
  `GET /api/time-entry-groups/nachtrag-vorschau`. `mobil_zeiten.html`: Dialog mit `kdVon`/`kdBis`, „Weitere Angaben“ (`kdWeitere`:
  Tätigkeit, `kdPause`, Notiz), Hinweis für eine Kolonnenbuchung ohne Uhrzeiten, Vorschau `kdVorschau` über `lesen('kolonne-vorschau')`,
  Mitglieder nebeneinander.

**Festlegungen 1.9.63 (Bitte bestätigen)**

1. Kolonnen-Nachtrag und -Ändern des Kolonnenführers mit einer Von/Bis-Angabe für die angehakten Mitglieder; Pause und Rundung je Mitglied
   nach seinem Tag (`kolonne_rechnen()`, dieselbe Rechnung wie sein eigener Nachtrag); jede Mitgliedsbuchung trägt Beginn und Ende;
   „Pause mindestens“ ist die Mindestpause, gemerkt je Mitglied (ersetzt 1.9.60 Nr. 3 und den Teil Kolonne von 1.9.59 Nr. 4).
2. Eine reine Dauer für die Kolonne nur noch das Büro: der Kolonnenführer (Rolle `field`) bekommt beim Nachtrag ohne Von/Bis und beim Ändern
   mit Stunden 422 mit der Meldung von 1.9.60, nach den Rechteprüfungen; der Gruppen-Dialog der Büro-Zeiterfassung bleibt eine Dauer.
3. Ändern der Kolonne: selbst geänderte Mitglieder bleiben (wie seit 1.7.13); ohne `pause_minuten` gilt je Mitglied die gemerkte
   Mindestpause; eine Kolonnenbuchung ohne Uhrzeiten (Dauer: von vor 1.9.63 oder vom Büro) ändert der Kolonnenführer nur mit Von und Bis
   (Hinweis im Dialog „… keine Uhrzeiten (8,00 h je Person) – trag Von und Bis ein …“).
4. Kopf der Kolonnenbuchung mit Von/Bis: Beginn und Ende, Stunden im Mittel der Mitglieder (wie der Gruppen-Stopp), Pause die größte; sind
   beim Ändern alle Mitglieder selbst geändert, behält der Kopf Stunden und Pause.
5. Vorschau `GET /api/time-entry-groups/nachtrag-vorschau` (Nachtrag: `team_id` und `employee_ids`, Ändern: `group_id`), Rechte wie beim
   Buchen (Kolonnenführer der Kolonne bzw. wer die Kolonnenbuchung angelegt hat); je Mitglied Name, anwesend, Pause, gebucht, Tag zusammen;
   beim Ändern dazu `uebersprungen`.
6. Anzeige: „Mia Monteurin 5,50 h · Tom Mitglied 5,00 h (Tag zusammen 6:15 h)“ -- volle Namen wie in der Mitgliederliste, „Tag zusammen“ nur
   mit weiteren Buchungen an dem Tag; beim Ändern „· bleibt: … (selbst geändert)“. Die Meldung nach dem Speichern nennt die gebuchten
   Stunden je Person („Für die Kolonne nachgetragen: …“, „Kolonnenbuchung geändert: …“).
7. Scheitert die Rechnung für ein Mitglied (z. B. bleibt nach der Pause keine Arbeitszeit), nennt die Meldung das Mitglied und es wird für
   niemanden gebucht; „Bis muss nach Von liegen.“ ohne Namen.
8. Dialog „Nachtrag für die Kolonne“ / „Kolonnenbuchung ändern“: Kolonne, Mitglieder nebeneinander, Datum, Zeitart, Von, Bis, Auftrag;
   Tätigkeit, „Pause mindestens“ und Notiz unter „Weitere Angaben“ (zugeklappt, beim Ändern nennt der Knopf sie); die Vorschau rückt sich im
   Dialog ins Bild (bei 1280 × 620 lag sie sonst unter dem Rand).
9. Die eigenen Kolonnenbuchungen (`GET /api/time-entry-groups/mine`, „Meine Zeiten“) nennen `von`, `bis` (leer bei einer Dauer) und
   `mindestpause` (die gemerkte eines nicht selbst geänderten Mitglieds, sonst die Pause des Kopfs) -- „Für die Kolonne ändern“ belegt
   damit vor.

**Tests und Prüfung**

- Neu `tests/test_v489_kolonne_von_bis.py` (6 Tests): 07:00–12:30 für Mia (ohne Vorbuchung) und Tom (Fahrzeit 06:15–07:00) -> 5,50 h ohne
  Pause bzw. 5,00 h mit 30 min, Vorschau = Buchung, Kopf; Kolonnenführer mit Dauer 422 (nichts gebucht), Stunden ändern 422, Notiz 200, Büro
  mit Dauer wie bisher; 5:00 h über die Kolonne je 0 min; Ändern mit Von/Bis je Mitglied, der selbst geänderte bleibt (Vorschau
  „uebersprungen“); Ändern ohne Pause behält die Mindestpause 45 je Mitglied, mit 0 -> 0, `/mine` mit von/bis/mindestpause; Rechte der
  Vorschau (kein Kolonnenführer 403, fremde Kolonnenbuchung 403), Bis vor Von 422 (Vorschau und Buchung, nichts gebucht).
- Angepasste Erwartungen (Test: alt -> neu):
  - `test_v302::_manual` (Kolonnenführer bucht): Dauer `hours` -> Von/Bis ab 07:00 so lang wie die Stunden (nur Aufbau, bis 6 h ohne Pause).
  - `test_v302::test_crew_leader_summary_and_list_contain_only_own_bookings`: Büro-Summe 18,00 h -> 17,50 h (Max bekommt am selben Tag
    4 h + 3 h, seine zweite Kolonnenbuchung nach der Tagesregel 30 min Pause, 2,50 h).
  - `test_v303::_correction` (Kolonnenführer korrigiert): `hours` mit `break_minutes` 0 -> Von/Bis mit `pause_minuten` 0, so dass dieselben
    Stunden gebucht werden (8,5 -> 07:00–16:00, 6 -> 07:00–13:00, 5 -> 07:00–12:00; nur Aufbau).
  - `test_v437::_gruppe`: Dauer 4 h -> 07:00–11:00 (nur Aufbau).
  - `test_v329::test_mobile_kolonnenbuchung_aendern_laesst_pause_und_lv_position`: Schlüssel von `kolonneSpeichern` mit `hours` -> mit
    `von`/`bis`; PUT mit 07:00–13:45 statt 6 h -- Ergebnis unverändert (Pause 45 bleibt als gemerkte Mindestpause, je 6,00 h).
  - `test_v424_zahlgrenzen`: `kdStunden` -> `kdPause` (Mindestpause); `groupHours` mit Beleg „Bitte die Dauer oder Von und Bis angeben.“
    (die Stunden der Kolonne sind im Schema optional).
  - `test_v326_monteur_datengrenze`: `QUERY_JE_ROUTE` mit der neuen Vorschau (nur Aufbau).
  - `klicktest_meine_zeiten`: Testdaten mit Toms Fahrzeit 06:15–07:00 am 07.10.; „Kolonnenbuchung ändern: Mitglieder, vorbelegt“ Stunden „8“
    -> Von/Bis leer, Pause „0“ und Hinweis „keine Uhrzeiten (8,00 h je Person)“; geändert mit 07:00–15:00 statt „7,5“, Meldung
    „Kolonnenbuchung geändert.“ -> „Kolonnenbuchung geändert: Mia Monteurin 7,50 h · Tom Mitglied 7,50 h“ (Summe 7,50 h wie bisher);
    Nachtrag 07.10. mit 07:00–12:30 statt „6“, Meldung „Für die Kolonne nachgetragen.“ -> „…: Mia Monteurin 5,50 h · Tom Mitglied 5,00 h“,
    Summe 6,00 h -> 5,50 h; Tom sieht am 07.10. eine Zeile ohne Uhrzeit mit 6,00 h -> seine Fahrzeit und 07:00–12:30 mit 5,00 h; neu zwei
    Prüfungen der Vorschau und das Bild `meine_zeiten_kolonne_nachtrag_vorschau_hell`.
  - `klicktest_teil_updates`: „Kolonnenbuchung ändern“ nur mit Notiz -> mit Von/Bis 07:00–15:45 (die Buchung der Testdaten ist eine Dauer),
    Meldung „Kolonnenbuchung geändert.“ -> „…: Max Kolonne 8,00 h · Moritz Mitglied 8,00 h“; Pause 45 und LV-Position bleiben wie bisher.
- **Gegenproben**: P1 Kolonnenführer darf eine Dauer nachtragen -> 1 rot; P2 darf die Stunden der Kolonne ändern -> 1 rot; P3 alle Mitglieder
  rechnen mit dem Tag des ersten -> 1 rot, Klicktest 5 rot; P4 Ändern ohne Angabe nimmt 0 -> 1 rot; P5 Vorschau ohne Prüfung des
  Kolonnenführers -> 1 rot; P6 Vorschau ohne „Tag zusammen“ -> Klicktest 1 rot (die Anzeige prüft nur der Klicktest).

## Stufe 4, R4 (ab 1.9.64): Einsatzbericht in fünf Schritten

Auftrag von Tobias (24.10.2026), Start auf 49089bb. Vorlagen `bildgrundlage/entwurf-stufe4/bericht-pruefpunkte.html` und
`bericht-unterschrift.html` (freigegeben, nur quer). Punkt 0: Befund zuerst -- welche Berichtsarten es gibt, welche Abschnitte jede hat, auf
welchen der fünf Schritte (1 Prüfpunkte · 2 Befunde · 3 Material · 4 Betriebsmittel · 5 Unterschrift) sie kommen; ein Schritt ohne Inhalt
entfällt; passt eine Art nicht sauber in die Schritte: anhalten und berichten, nicht bauen.

### Befund (vor dem Umbau): Berichtsarten, Abschnitte, Schritte

**Die Seite heute** ist eine Seite je **Auftrag**, nicht je Bericht: `/orders/{id}/service-reports` (`service_reports.html`) zeigt alle Berichte
des Auftrags als Karten, jeder mit den Umschaltern Prüfpunkte · Mängel ohne Prüfpunkt · Material · Betriebsmittel. Eingänge: „Heute“
(„Bericht fortsetzen“ mit `?report=<id>`, „Bericht anlegen“ ohne), „Heute / Offen“ (`?report=`), Wartungsvertrag „Wartung durchführen“
(`?report=`), das Büro über die Auftragsseite. `?report=` klappt heute nur die Prüfpunkte dieses Berichts auf.

**Berichtsarten** (`ServiceReport.report_type` nur `rapport` oder `wartung`, `app/service_reports.py::REPORT_TYPES`; ob es Prüfpunkte gibt,
entscheidet `hasInspectionSection()`: Wartung immer, Rapport nur mit Vorlage an einer seiner Dachflächen):

| Art | entsteht | Prüfpunkte |
|---|---|---|
| A Wartungsbericht | „+ Bericht“ mit Art Wartung; „Wartung durchführen“ (Vertrag, „Heute / Offen“) über alle Flächen | aus der Standardvorlage je Dachtyp je gewählter Fläche (ohne Fläche keine, „+ Punkt“ geht immer) |
| B Rapportbericht mit Prüfvorlage | „+ Bericht“ mit Art Rapport, genau einer Fläche und gewählter Vorlage | aus der Vorlage, „+ Punkt“ |
| C Rapportbericht ohne Prüfvorlage | „+ Bericht“ mit Art Rapport ohne Vorlage (Reparatur) | keine, auch kein „+ Punkt“ |

Status für alle: `entwurf` oder `unterschrieben`. Die Art lässt sich im Entwurf über „Bearbeiten“ wechseln (A <-> C/B), Prüfpunkte entstehen
dabei nicht neu.

**Abschnitte je Bericht und ihr Schritt**:

| Abschnitt | A | B | C | Schritt |
|---|---|---|---|---|
| Prüfpunkte: Antworten (OK/Nicht OK/Entfällt, Dichtheit mit Minuten, Zustand 1–4, Messwert mit Soll, Menge, Freitext, Foto-Punkt), „+ Bemerkung“, Fotos am Punkt (auch Vorher/Nachher), „+ Punkt“, eigenen Punkt löschen, „Prüfpunkte neu erzeugen“, Hinweis „n Prüfpunkte ergänzt“, Stand „x von y, n Pflichtpunkte offen“ | ja | ja | -- | 1 |
| Befund am Prüfpunkt: „Mangel fehlt noch“ mit „+ Mangel“, Karte mit Schwere, Maßnahme, Wiedervorlage, Fotos, „+ Material“, Nachverfolgung (Status, Maßnahme, „Aufgabe nachholen“) | ja | ja | -- | 1 (direkt unter dem Punkt) und 2 |
| Befunde ohne Prüfpunkt (dieselbe Karte, „+ Mangel“) | ja | ja | ja | 2 |
| Material (Katalogsuche, freie Bezeichnung, Menge, Einheit, Fläche ab zwei, Zuordnung zum Befund, ändern, löschen) | ja | ja | ja | 3 |
| Betriebsmittel (Modul `betriebsmittel`; Auswahl, Notiz, entfernen) | ja | ja | ja | 4 (entfällt ohne Modul) |
| Zeiten am Tag des Berichts (Regel aus R1, `zeiten_des_berichts()`) | ja | ja | ja | 5 |
| Unterschrift Monteur und Kunde mit Namen, „Noch offen“ | ja | ja | ja | 5 |
| PDF (nach der Unterschrift), Löschen (Entwurf), Hinweis fürs Büro (Fläche fremd) | ja | ja | ja | Kopf („⋮“) |
| **Beschreibung „Durchgeführte Arbeiten / Feststellungen“** (steht im PDF; heute nur über „Bearbeiten“ → „Speichern“) | ja | ja | ja | **keiner** |
| **Kopfdaten: Art, Datum** (über „Bearbeiten“; „Durchgeführt von“ nur beim Anlegen) | ja | ja | ja | **keiner** |

**Auf der Ebene des Auftrags** (nicht je Bericht, in der Vorlage nicht enthalten -- sie zeigt einen Bericht): Objekt & Zugang, offene
Bedenken, die Liste der Berichte mit „+ Bericht“ (Anlegen: Art, Datum, Durchgeführt von, Dachflächen, Vorlage nur bei genau einer Fläche,
Beschreibung), „Frühere Berichte zu diesem Gebäude“, „Erfasste Zeiten zu diesem Auftrag“ mit Buchen (Punkt 5), im Menü „Zeiterfassung
(Auftrag)“.

**Schritte je Art**: A und B alle fünf (4 entfällt ohne Modul Betriebsmittel); C ohne Schritt 1 -- 2 Befunde · 3 Material · 4 Betriebsmittel
· 5 Unterschrift.

**Ergebnis: angehalten, nichts am Einsatzbericht gebaut.** Der Rapportbericht ohne Prüfvorlage (C) passt nicht sauber: sein Kern, die
Beschreibung der durchgeführten Arbeiten, hat keinen Schritt -- bei A und B ebenso, dort ist sie Ergänzung. Dazu fehlt in den Vorlagen die
Ebene des Auftrags, auf die der Pfad „Heute / <Auftrag> / <Art>“ zeigt.

**Vorschläge (Entscheidung Tobias)**

1. Beschreibung „Durchgeführte Arbeiten / Feststellungen“:
   a) **Empfehlung**: Schritt 1 heißt je Art „Prüfpunkte“ (A, B) bzw. „Arbeiten“ (C); das Feld steht bei C als Inhalt von Schritt 1, bei A und B
      unter den Prüfpunkten -- fünf Schritte für jede Art, keiner entfällt bei C.
   b) eigener Schritt „Arbeiten“ vor „Befunde“ für alle Arten (sechs Schritte).
   c) das Feld in Schritt 5 über „Das steht im Bericht“ (zuletzt geschrieben, der Kunde liest es vor der Unterschrift).
   In allen Fällen gespeichert wie die Bemerkungen (600 ms nach der letzten Taste und beim Verlassen, der Fokus bleibt), nicht mehr über
   „Bearbeiten“.
2. Kopfdaten: „⋮ → Datum ändern“ (Dialog auf der Seite); die Art nur beim Anlegen (ein Wechsel ändert, welche Schritte es gibt, ohne
   Prüfpunkte zu erzeugen) -- oder die Art weiter änderbar, dann wechseln die Schritte mit.
3. Zwei Seiten: die **Auftragsseite** `/orders/{id}/service-reports` bleibt für Liste, „+ Bericht“, Objekt & Zugang, offene Bedenken,
   frühere Berichte und die Zeiten (Büro unverändert, die Monteurin „Zeit nachtragen“ → „Meine Zeiten“, Punkt 5); der **Bericht** bekommt
   eine eigene Seite `/service-reports/{id}` mit den fünf Schritten, Pfad „Heute / <Auftrag> / <Art>“ (Auftrag = die Auftragsseite), fürs
   Büro „Projekte / … / Auftrag / Einsatzberichte / <Art>“. `?report=<id>` leitet auf die Berichtsseite, „+ Bericht“ öffnet nach dem Anlegen
   den neuen Bericht (Regel „nach dem Anlegen zum Datensatz“), „Heute“ öffnet „Bericht fortsetzen“ direkt dort.
4. Benennung: auf der Seite „Befund“ statt „Mangel“ (wie die Vorlage; Modell `Finding`), der Mangel an der Abnahme (`Defect`) bleibt
   „Mangel“.

### R4, Punkt 7 (1.9.64): Werkzeug -- Zeichnen erst bei ruhiger Fläche

Umgesetzt, obwohl der Einsatzbericht angehalten ist: der Punkt hängt nicht an der Entscheidung zu den Schritten. Einzelheiten in
`docs/archiv/testablauf-und-klicktests.md`, „Zeichnen erst, wenn die Fläche ruhig liegt“.

### R4, Punkt 6 (1.9.65): Dialoge im Monteursrahmen -- die Knopfleiste bleibt unten im Bild

Umgesetzt, obwohl der Einsatzbericht angehalten ist (der Punkt betrifft „Heute“ und „Meine Zeiten“). Befund: im Monteursrahmen haben nur
`mobil.html` (Start mit Tätigkeit / für die Kolonne) und `mobil_zeiten.html` (Zeit nachtragen/ändern, Kolonne, Löschen, Abwesenheit)
Dialogkarten; der Einsatzbericht hat nur die kleine Rückfrage beim Löschen eines Prüfpunkts (eigene Klasse). Bei 1280 × 620 waren der
Kolonnen-Dialog und „Zeit ändern“ mit aufgeklappten „Weiteren Angaben“ höher als das Fenster.

- **Umsetzung**: je Seite `.dialog-karte>.dialog-knoepfe{position:sticky;bottom:-22px;…}` (über die Innenabstände der Karte bis an ihre
  Ränder, Hintergrund der Karte, Strich oben) und `.dialog-karte .vorschau{scroll-margin-bottom:96px}`.

**Festlegungen 1.9.65 (Bitte bestätigen)**

1. In jeder Dialogkarte des Monteursrahmens bleibt die Knopfleiste unten im Bild; der Inhalt läuft unter ihr durch, ein Strich (`--ds-linie`)
   trennt sie -- auch in Dialogen, die ins Fenster passen.
2. Was sich in einem Dialog selbst ins Bild rückt (die Vorschau der Kolonne), hält Abstand zur Leiste.

**Tests und Prüfung**

- Neu `tests/test_v491_dialog_knopfleiste.py` (4 Tests): es gibt Dialogkarten auf „Heute“ und „Meine Zeiten“; jede Seite im Monteursrahmen
  mit Dialogkarten hält die Leiste fest; jede Dialogkarte endet mit ihrer Leiste; eine Vorschau im Dialog hält Abstand.
- `klicktest_meine_zeiten`: neu zwei Prüfungen bei 1280 × 620 -- Kolonnen-Dialog: „Speichern“ im Bild und nicht verdeckt, Vorschau über der
  Leiste; „Zeit ändern“ aufgeklappt: „Speichern“ im Bild.
- **Gegenproben**: P1 Leiste auf „Meine Zeiten“ nicht festgehalten -> 1 rot, Klicktest 1 rot („Zeit ändern“; der Kolonnen-Dialog rückt die
  Vorschau ins Bild und blieb grün); P2 ohne Abstand der Vorschau -> Klicktest 1 rot, nach dem Nachschärfen auch pytest 1 rot; P3 Leiste auf
  „Heute“ nicht festgehalten -> 1 rot.

## Stufe 4, R4 Fortsetzung (ab 1.9.66): Einsatzbericht bauen

Auftrag von Tobias (24.10.2026), Start auf 29a936d. Festlegungen 1.9.65 Nr. 1–2 und die Werkzeug-Festlegung zu 1.9.64 bestätigt. Entscheidungen
zum Befund:

- **A** Schritt 1 heißt beim Rapport ohne Vorlage „Arbeiten“ und enthält „Durchgeführte Arbeiten / Feststellungen“; bei Wartung und Rapport
  mit Vorlage steht das Feld unter den Prüfpunkten. Jede Art hat fünf Schritte. Gespeichert wie die Bemerkungen (der Fokus bleibt).
- **B** Rapport ohne Vorlage: die Beschreibung ist Pflicht -- leer steht sie unter „Noch offen“ und sperrt die Unterschrift (Server und Seite).
- **C** Die Art ist änderbar, nur solange der Bericht leer ist (keine Antwort, kein Befund, kein Material, kein Betriebsmittel, keine
  Beschreibung, kein Foto); danach fest, Meldung mit dem Hinweis „Entwurf löschen und neu anlegen“. Datum über „⋮ → Datum ändern“.
- **D** Zwei Seiten: die Auftragsseite bleibt (Liste, „+ Bericht“, Objekt & Zugang, Bedenken, frühere Berichte; die Monteurin bekommt „Zeit
  nachtragen“ statt der Buchungskarte), der Bericht kommt neu unter `/service-reports/{id}`; `?report=`, „+ Bericht“ und „Bericht
  fortsetzen“ führen direkt hin.
- **E** „Befund“ statt „Mangel“ in allen Monteursansichten (auch „Heute / Offen“: „Befunde zur Beseitigung“); der Mangel der Abnahme bleibt
  „Mangel“.

Dazu die Punkte 1–5 aus R4 (Kopf mit Pfad, Status und „⋮“; Schritte mit Haken, feste Leiste, „Noch offen“ rechts bzw. hoch über der Leiste;
Segmentknöpfe ≥ 52 px, „Nicht OK“ öffnet den Befund darunter; Unterschrift mit Zusammenfassung, Zeiten am Tag, Namensfeldern, Fläche ≥ 160 px,
„Bericht abschließen“ gesperrt mit „Fehlt: …“; Tablet: Ziele ≥ 48 px, Fokus bleibt, Foto löschen 48 px mit Rückfrage, „Aufnehmen“ und „Aus
Galerie“; keine Buchungskarte für die Monteurin). Gebaut in drei Versionen: 1.9.66 Server, 1.9.67 die Berichtsseite und die Auftragsseite,
1.9.68 „Befund“ in den übrigen Monteursansichten.

### R4 Fortsetzung, Server (1.9.66)

- **Beschreibung** (B): `app/service_reports.py::hat_pruefpunkte()` -- Wartung immer, Rapport nur mit Vorlage an einer seiner Flächen (oder in
  der Altspalte); dieselbe Regel wie `hasInspectionSection()` der Seite bis hierher. Ohne Prüfpunkte und ohne Beschreibung steht
  `ARBEITEN_BESCHREIBEN` („Durchgeführte Arbeiten beschreiben“) als erster Eintrag unter „Noch offen“ und `sign_report()` lehnt ab (409 mit
  der Liste, wie seit 1.9.36).
- **„Noch offen“ je Schritt**: `noch_offen_je_schritt()` liefert je Eintrag Text und Schritt (`arbeiten`, `pruefpunkte`, `befunde`);
  `noch_offen()` nimmt die Texte daraus. `GET …/noch-offen` antwortet `{"offen": […], "eintraege": […]}`, die Berichtsantwort trägt
  `noch_offen_je_schritt`, `hat_pruefpunkte`, `art_aenderbar`.
- **Art** (C): `bericht_leer()`; `update_report()` lehnt einen Wechsel mit `ArtFest` ab (409, `ART_FEST`), dieselbe Art geht immer durch.
  `_pruefpunkte_wie_beim_anlegen()`: nach dem Wechsel Vorlagen und Prüfpunkte wie `create_report()` ohne ausdrückliche Vorlage.
- **Teil-Update**: `ServiceReportUpdate` von `PartialUpdate` (`NOT_NULL` Art und Datum), Handler mit `model_dump(exclude_unset=True)`; aus
  `BEKANNT` in `tests/test_v329_update_handler_struktur.py` gestrichen (61 statt 62).
- **Ein Bericht**: `GET /api/service-reports/{id}` -- die Monteurin nur ihren eigenen (`require_field_report_ownership()`, wie Ändern und PDF,
  Schema `ServiceReportOut`), das Büro dazu mit `office_hint` (wie die Liste).
- **Benennung** (E, Server): „Befund zum Prüfpunkt … erfassen“, „Foto zum Befund … aufnehmen“, „Wiedervorlagedatum zum zurückgestellten Befund
  … angeben“.

**Festlegungen 1.9.66 (Bitte bestätigen)**

1. Eine Beschreibung nur aus Leerzeichen zählt nicht -- sie steht weiter unter „Noch offen“.
2. „Leer“ für die Art: ein Prüfpunkt zählt als Eingabe, sobald er ein Ergebnis, einen Zustand, einen Messwert, eine Menge, eine Dauer oder
   eine Bemerkung trägt; ein Punkt ohne all das (auch ein Foto-Punkt ohne Foto) nicht. Ein Foto am Bericht zählt immer.
3. Mit der Art wechseln Vorlagen und Prüfpunkte wie beim Anlegen mit der neuen Art (Wartung: Vorlage je Fläche über Vertragsposition und
   Standardvorlage des Dachtyps; Rapport: ohne Vorlage, Schritt „Arbeiten“) -- auch eine beim Anlegen ausdrücklich gewählte Vorlage eines
   Rapports entfällt. Es geht nichts verloren, der Bericht ist leer. Ein Altbestand-Bericht von vor 1.2.22 (ohne Flächenzeilen) behält seine
   Punkte.
4. Die Reihenfolge unter „Noch offen“: zuerst die Beschreibung, dann Pflichtpunkte, Befunde zu negativen Ergebnissen, Fotos, Wiedervorlagen.

**Tests und Prüfung**

- Neu `tests/test_v492_bericht_regeln.py` (14 Tests): Rapport ohne Vorlage leer gesperrt, nur Leerzeichen gesperrt, ausgefüllt frei; Wartung
  und Rapport mit Vorlage ohne Beschreibung; Art leer geht, nach Antwort, Beschreibung, Befund, Material, Betriebsmittel oder Foto 409 und
  nichts geändert; Art-Wechsel legt Prüfpunkte wie beim Anlegen; Datum allein lässt Art und Beschreibung, `null` für Art oder Datum 422; ein
  Bericht: Monteurin eigener 200 ohne Hinweis, fremder 403, Büro mit Hinweis, unbekannt 404; „Noch offen“ je Schritt mit „Befund“.
- Angepasste Erwartungen: `test_v464` (`GET …/noch-offen` zusätzlich `eintraege`; „Mangel“ -> „Befund“ in vier Texten); `test_v214`
  `test_router_endpoints_create_finding_and_reject_sign_without_photo` („Noch offen: Foto zum Mangel „Kaputt“ aufnehmen“ -> „… zum Befund …“, der
  Bericht bekommt beim Anlegen eine Beschreibung); `test_v329` (`BEKANNT` ohne `PUT /api/service-reports/{report_id}`).
- Nur Aufbau angepasst (Rapport ohne Vorlage mit Beschreibung, sonst lehnt die Unterschrift ab): `test_v203` (Helfer `sign_report_for_test`
  trägt eine Beschreibung ein, wenn sie fehlt; `update_report()` mit einem dict), `test_v214`, `test_v223`, `test_v234`, `test_v280`,
  `test_v338`, `test_v358` (`create_report(…, "rapport", description="Arbeiten laut Testfall")`).
- **Gegenproben** (je nur `test_v492`): Beschreibung nicht Pflicht -> 1 rot; Leerzeichen zählen -> 1 rot; Art immer änderbar -> 6 rot;
  Betriebsmittel zählt nicht -> 1 rot; Foto zählt nicht -> 1 rot; PUT übernimmt alle Felder -> 9 rot (Datum `null` an der Spalte); ein
  Bericht ohne Besitzprüfung -> 1 rot; „Mangel“ statt „Befund“ -> 1 rot; Art wechselt ohne Prüfpunkte -> 1 rot.

### R4 Fortsetzung, Berichtsseite und Auftragsseite (1.9.67)

- **Zwei Seiten** (D): `/service-reports/{id}` (`service_report.html`, Seitenroute `service_report_page`, Daten über `GET /api/service-reports/{id}`
  -- die Monteurin nur ihren eigenen) und `/orders/{id}/service-reports` (`service_reports.html`, verschlankt). `?report=<id>` auf der Seite
  des Auftrags leitet der Server weiter (`_bericht_aus_adresse()`, Ziel fest `/service-reports/<Zahl>`); `dk_ohne_seite` bekommt dafür seit
  1.9.67 Benutzer und Anfrage (`app/seitendaten.py::wird_gezeichnet()`). Eingänge: „Heute“ (Weiter am Bericht), „Heute / Offen“ (offene
  Berichte, „Wartung durchführen“), Wartungsvertrag („Wartung durchführen“) direkt zum Bericht; „Bericht anlegen“ auf „Heute“ weiter zur Seite
  des Auftrags, „+ Bericht“ dort öffnet nach dem Anlegen den neuen Bericht.
- **Kopf**: Makro `seitenkopf` (tablet für die Monteurin), Titel = Art, Status über `statusKennzeichen('einsatzbericht', …)` (neue Gruppe:
  Entwurf, Unterschrieben), Untertitel Objekt · Dachflächen; Menü „⋮“: Datum ändern, Art ändern, Prüfpunkte neu erzeugen, PDF öffnen, Löschen.
- **Schritte**: `schritte()` -- Schritt 1 nach `hat_pruefpunkte` vom Server, Betriebsmittel nur mit Modul; der Schritt steht in der Adresse
  (`#pruefpunkte` …); „Noch offen“ aus `GET …/noch-offen` (`eintraege` je Schritt), nach jedem Speichern frisch (`nochOffenLaden()`).
- **Fokus**: `teilErsetzen()` ersetzt nach dem Speichern nur Kopf, Zusatz oder Befund eines Punkts und lässt einen Teil mit dem fokussierten
  Feld stehen; ein fokussierter Knopf bekommt den Fokus nach dem Ersetzen zurück. Die Texte speichern 600 ms nach der letzten Taste und beim
  Verlassen (`entprellt()` über `_debounce.html`; vor „Bericht abschließen“ von `nachDemSpeichern()` sofort ausgelöst).
- **Unterschrift**: `berichtAbschliessen()` -- `fehlt()` (Noch offen, Namen, Flächen), dann `nachDemSpeichern()` und `nochOffenLaden()`,
  erst dann `abschliessen('bericht', …/sign)`.
- **Auftragsseite**: je Bericht `reportRow()`; ein Bericht einer Kollegin (reduziertes Schema ohne `status`) ohne Link; die Buchungskarte nur
  fürs Büro (`{% if monteursrahmen %}`), die Monteurin „Zeit nachtragen“ -> `/mobil/zeiten?order_id=<id>`.

**Festlegungen 1.9.67 (Bitte bestätigen)**

1. Schritt 5 wie die Vorlage ohne die Spalte „Noch offen“: was offen ist, steht dort in der Karte „Unterschriften“ (Liste „Noch offen“,
   Kennzeichen „n offen“ bzw. „Nichts mehr offen“); „Zurück“ / „Weiter“ entfallen in Schritt 5 (die Schritte sind frei anwählbar).
2. „Das steht im Bericht“ hat zusätzlich die Zeile „Arbeiten“ (Beschreibung, nach 140 Zeichen gekürzt); die Zeiten heißen „Zeiten am <Tag>“
   (Regel aus R1) statt „Zeiten dieses Einsatzes“ der Vorlage, darunter „Nur dieser Tag …“ bzw. „Stand der Unterschrift.“
3. Monteur und Kunde unterschreiben auf einer Seite nebeneinander, ein Klick „Bericht abschließen“ sendet beides (bis 1.9.66 nacheinander im
   Panel); der Name des Monteurs ist mit dem angemeldeten Konto vorbelegt und änderbar.
4. „Fehlt: …“ nennt in dieser Reihenfolge die Zahl der Punkte unter „Noch offen“, Name und Unterschrift des Monteurs, Name und Unterschrift
   des Kunden.
5. Haken: Prüfpunkte bzw. Arbeiten, wenn dort nichts offen ist (Prüfpunkte: alle beantwortet); Befunde, wenn nichts offen und angesehen
   oder mit Einträgen; Material und Betriebsmittel, sobald angesehen (je Gerät und Sitzung) oder mit Einträgen; Unterschrift nach dem
   Abschluss.
6. Der Schritt steht in der Adresse (`#pruefpunkte`, `#arbeiten`, `#befunde`, `#material`, `#betriebsmittel`, `#unterschrift`); Neuladen
   bleibt im Schritt, ein Link kann einen Schritt öffnen.
7. Prüfpunkte je Dachfläche zusammen (Reihenfolge der Flächen am Bericht), darin nach Gruppe; ohne Fläche zuletzt („Ohne Fläche“, nur bei
   mehreren Flächen benannt).
8. „Bemerkung“, „Foto aufnehmen“, „Foto aus Galerie“ und „Prüfpunkt löschen“ (nur am von Hand ergänzten Punkt, rot) stehen im Menü „⋮“
   je Punkt (Einträge 48 px); eine vorhandene Bemerkung steht als Feld unter dem Punkt.
9. „Nicht OK“ und Zustand 3/4 öffnen das Befund-Formular direkt unter dem Punkt (Schwere als Segmente, Maßnahme, Wiedervorlage); danach
   steht dort der Befund mit Stand („Foto fehlt“ / „1 Foto“), „Foto“ (Aufnehmen, Aus Galerie) und „Befund bearbeiten“ (springt zu Schritt 2).
10. „Aufnehmen“ öffnet die Kamera (`capture="environment"`), „Aus Galerie“ die Dateiauswahl -- bei Vorher/Nachher je Platz beide Knöpfe.
11. Jede Rückfrage der Berichtsseite (Bericht, Prüfpunkt, Foto, Material, Betriebsmittel löschen; Prüfpunkte neu erzeugen) im Dialog der
    Seite mit 48-px-Knöpfen, nie `confirm()`.
12. „Art ändern“ bleibt im Menü, auch wenn der Bericht nicht mehr leer ist: der Dialog zeigt dann gesperrt den Hinweis „… Entwurf löschen
    und neu anlegen.“
13. „Prüfpunkte neu erzeugen“ bleibt im Menü (mit Rückfrage), nur im Entwurf mit Prüfpunkten und Dachflächen; „PDF öffnen“ erst nach der
    Unterschrift (im Menü und in der Karte „Unterschriften“).
14. Hochformat ab unter 1000 px: eine Spalte, „Noch offen“ als feste Leiste unten (Liste höchstens 18 % der Höhe, mit Bildlauf), Knöpfe dort
    56 px.
15. Kopf ohne Kennung (wie die Vorlage), Untertitel Objekt · Dachflächen, ohne beides das Datum.
16. Meldungen des vorigen Schritts verschwinden beim Schrittwechsel.
17. Die Seite des Auftrags heißt „Einsatzberichte“ (Titel und letztes Pfadglied); je Bericht eine anklickbare Zeile (Art, Status, Datum,
    wer, Flächen, „Noch offen: n Punkte“, Hinweis fürs Büro) mit „Bericht fortsetzen“ bzw. „Bericht ansehen“; ein Bericht einer Kollegin
    ohne Link mit Hinweis. Bearbeiten nur noch auf der Berichtsseite, die Seite des Auftrags legt nur an.
18. Die Monteurin bekommt auf der Seite des Auftrags die Karte „Zeiten“ mit „Zeit nachtragen“ (`/mobil/zeiten?order_id=…`); „Zeiterfassung
    (Auftrag)“ im Menü bleibt (führt für sie ebenso auf „Meine Zeiten“).
19. Die Seitenroute `/service-reports/{id}` prüft selbst nicht, wer den Bericht öffnen darf (wie die Seite des Auftrags); fremd für die
    Monteurin heißt „Bericht nicht geladen: …“ (403 der Schnittstelle).

**Tests und Prüfung**

- Neu `scripts/klicktest_bericht_schritte.py` (43 Prüfungen): Eingänge („Heute“ -> Weiter, `?report=`, „+ Bericht“), Kopf, fünf Schritte,
  jede Funktion der bisherigen Seite in ihrem Schritt (Liste aus dem Befund R4), „Nicht OK“ -> Befund darunter und „Noch offen“ sofort,
  Foto aus der Galerie, Foto löschen 48 px mit Rückfrage, Fokus nach Segmentknopf und Bemerkung (auch wenn eine Antwort beim Weitertippen
  ankommt), 48 px in jedem Schritt quer (1280 × 620) und
  hoch (800 × 1100), Befund-Status, Material aus dem Katalog, Betriebsmittel, Schritt 5, Rapport ohne Vorlage gesperrt -> Beschreibung ->
  abgeschlossen, Art leer/gesperrt, Datum, Löschen, Auftragsseite der Monteurin ohne Buchungskarte, Büro unverändert; Bilder hell und dunkel.
- Neue Fassungen gegen die Berichtsseite (alt -> neu): `test_v405` Gruppenname in `inspectionItemsPanelHtml()` -> in `pruefpunkteHtml()`;
  `test_v464` „fragt vor beiden Unterschriften (`openSignPanel`, `confirmSignatureStep`)“ -> „vor ‚Bericht abschließen‘ Speichern abwarten
  und ‚Noch offen‘ frisch“, „×“ am eigenen Punkt -> Menüeintrag „Prüfpunkt löschen“; `test_v469` Knopf „×“ 48 px mit `punktLoeschenDialog`
  -> Menüeintrag 48 px mit `rueckfrageDialog`; `test_v475` `rueckfrage(text)` mit `punktLoeschen*` -> `rueckfrage(titel,text,ja)` mit
  `rueckfrage*`; `test_v485` Monteurin Von/Bis auf der Buchungskarte -> keine Buchungskarte, „Zeit nachtragen“; `test_v437` Auswahl für alle
  vier Rollen -> für die drei Büro-Rollen, die Monteurin ohne Feld; `test_v337`/`test_v360` `service_reports.html` -> `service_report.html`
  (Pfad `/service-reports/1`); `test_v259` `.report-actions a{` vorhanden -> `a.bericht-zeile:hover{`; `test_v425` vier umleitende
  Seitenrouten -> fünf (mit `?report=`), dazu zwei Umleitungsfälle; `test_v401` 6 Weiterleitungen -> 7; `test_v399` `confirmSignatureStep`
  -> `berichtAbschliessen`; `test_v424` drei Zahlenfelder auf die Berichtsseite; `test_v431` 302 Bilder -> 314, 244 bisherige -> 252;
  `test_v441` 44 Seiten mit Leiste -> 45.
- Nur kürzer: `test_v400` (eine Ausnahme weniger), `test_v407` (36 Einträge mit 72 Handlern weniger, 357 -> 285), `test_v447` (vier Einträge weniger).
- Neu eingetragen: `test_v441` und `test_v446` (Datensatz mit Pfad, Rückwege, Löschen nur im Menü -- dort seit 1.9.67 auch mit der Rückfrage
  der Seite statt `confirm()`), `test_v457` (Tablet-Variante), `test_v460` (sechs Knöpfe und Felder, die Zeile je Bericht als Eintrag).
- Klicktests (alt -> neu): `klicktest_abschliessen` (Unterschriften-Panel, Meldungen per alert und mit „Fehler: “ -> Schritt 5, Meldungszeile,
  Meldung des Bausteins wörtlich); `klicktest_vertrag_unterschrift` (Fläche 220 px, Monteur dann Kunde -> beide Flächen ≥ 160 px, gesperrt
  mit „Fehlt“); `klicktest_zeichenflaeche` (`#sigCanvas` -> `#padKunde`); `klicktest_einsatzbericht_zeiten` (Tabelle je Bericht auf der
  Seite des Auftrags, „Zeiten am … – Stand …“ -> Schritt 5 der Berichtsseite, „Zeiten am …“ mit „Person · von–bis“); `klicktest_monteurin_regeln`
  (Knopf „Prüfpunkte“, „×“, Panel -> Schritt 1, Menüeintrag, Schritt 5 gesperrt); `klicktest_daten_im_html` (Gruppe als Klappknopf -> als
  Überschrift); `klicktest_abgleich_sperre` (`.report-card` -> `.bericht-zeile`, dazu die Berichtsseite); `klicktest_monteur_dachflaechen`
  (Monteurin bucht hier -> keine Buchungskarte, Anlegen öffnet den Bericht; Büro „Bea Büro|Max Monteur“ -> „Bea Büro“, Klick über
  `data-klick`); `klicktest_heute` (`?report=` -> `/service-reports/{id}`, zwei Stellen); `klicktest_rahmen` (Titel und Pfadende
  „Einsatzbericht“ -> „Einsatzberichte“ an drei Stellen, „Wartung durchführen“ -> Berichtsseite, Pfad mit „Einsatzberichte / Wartungsbericht“).
- Bildgrundlage: neue Aufnahme `bericht` (Büro und Monteurin) am Ende der Liste.
- **Gegenproben** (Tests und Klicktest je Probe): `?report=` leitet nicht weiter -> `test_v425` 1 rot, Klicktest rot (landet auf der Seite
  des Auftrags); „Noch offen“ nach dem Speichern nicht frisch -> Klicktest 1 rot; Feld mit Fokus wird neu gezeichnet -> zuerst grün (der
  Klicktest tippte alles vor der Antwort), nach dem Nachschärfen (Antwort beim Weitertippen) Klicktest 1 rot; Knopf verliert den Fokus ->
  Klicktest 1 rot; Segmente 40 px -> Klicktest 2 rot (quer und hoch); „Bericht abschließen“ nicht gesperrt -> Klicktest 2 rot; Abschließen
  ohne frisches „Noch offen“ -> `test_v464` 1 rot; Monteurin mit Buchungskarte -> `test_v485` und `test_v437` je 1 rot, Klicktest rot;
  „Heute“ verlinkt auf `?report=` -> `klicktest_heute` 1 rot; Löschen ohne Rückfrage -> `test_v446` 1 rot.

### R4 Fortsetzung, „Befund“ in den Monteursansichten (1.9.68)

- „Heute“: Zeile „Befunde zur Beseitigung“ (Sprungziel bleibt `#maengel`, der Schlüssel `maengel` in `app/heute.py` bleibt). „Heute / Offen“:
  Überschrift, „Keine Befunde zur Beseitigung.“, „Befund als beseitigt gemeldet – das Büro prüft die Abnahme der Beseitigung.“, Bildtext
  „Foto zum Befund“.
- Server, nur der Weg der Monteurin: `app/routers/field_defects.py::NOT_FOUND` „Befund nicht gefunden.“; `app/defects.py::report_remedied()`
  „… bei der der Befund festgehalten wurde.“ (dieselbe Meldung beim Büro, `set_status()`, bleibt „Mangel“).
- Befund des Einsatzberichts (`Finding`): „Befund nicht gefunden.“ in `app/routers/findings.py` (zwei Stellen) und `app/service_reports.py`
  (`add_photo()`, `add_material()`, `update_material()`).

**Festlegungen 1.9.68 (Bitte bestätigen)**

1. In den Monteursansichten heißt auch der freigegebene Mangel der Abnahme „Befund“ (Entscheidung E: „Befunde zur Beseitigung“); im Büro
   bleibt er „Mangel“ (Seite des Auftrags, Mängel-Karte, Aufgaben „Mangel beseitigen“).
2. Meldungen, die Büro und Monteurin teilen (z. B. „Der Mangel steht auf …“ beim Konflikt), bleiben „Mangel“ -- nur was allein der Weg der
   Monteurin meldet, sagt „Befund“.
3. Der Befund des Einsatzberichts (`Finding`) meldet auch im Büro „Befund nicht gefunden.“ -- er heißt seit 1.9.66 überall „Befund“.

**Tests und Prüfung**

- Angepasste Erwartungen (alt -> neu): `test_v354` 404 „Mangel nicht gefunden.“ -> „Befund nicht gefunden.“; `test_v476` Zeile „Mängel zur
  Beseitigung“ -> „Befunde zur Beseitigung“; `test_v399` Beschreibung des Eintrags `sendReport` „Mangel als beseitigt melden“ -> „Befund als
  beseitigt melden“ (nur der Text des Eintrags); `klicktest_maengel_monteur` „Mangel als beseitigt gemeldet …“/„Keine Mängel zur
  Beseitigung.“ -> „Befund …“/„Keine Befunde zur Beseitigung.“ (zwei Stellen).
- `test_v223` `test_add_material_rejects_inspection_item_and_finding_from_other_report`: Meldung enthält „Mangel“ -> „Befund“.
- **Gegenproben**: „Heute“ sagt wieder „Mängel zur Beseitigung“ -> `test_v476` 1 rot; „Heute / Offen“ meldet „Keine Mängel zur
  Beseitigung.“ -> `klicktest_maengel_monteur` 2 rot; der Weg der Monteurin meldet „Mangel nicht gefunden.“ -> `test_v354` 1 rot.

## Stufe 4, R4 Nachrunde (ab 1.9.69)

Auftrag von Tobias (24.10.2026), Start auf 1cb35ae. Festlegungen R4 (1.9.66–1.9.68) bestätigt, außer 1.9.67 Nr. 1 (Schritt 5 ohne feste
Leiste -> Punkt 1) und 1.9.68 Nr. 1 (Mängel der Abnahme als „Befund“ -> Punkt 5). Punkte: 1 Schritt 5 mit fester Leiste („Bericht
abschließen“, „Fehlt: …“), bei 1280 × 620 ohne Bildlauf sichtbar; 2 „Noch offen“ mit der Dachfläche bei mehr als einer Fläche, keine zwei
gleichen Zeilen; 3 „⋮“ eines Prüfpunkts in seiner Titelzeile; 4 Status auf „Einsatzberichte“ über den Statusbaustein; 5 Mängel der Abnahme
bleiben auch für die Monteurin „Mangel“; 6 Schlüssel-Scan als Monteurin über den Bericht und „Noch offen“; 7 Bildgrundlage neu.

### R4 Nachrunde, Punkt 5 (1.9.69): „Mangel“ für die Mängel der Abnahme

- Zurück auf den Stand vor 1.9.68: `mobil.html` (Zeile „Mängel zur Beseitigung“), `mobil_offen.html` (Überschrift, leere Liste,
  Bestätigung, Bildtext), `app/routers/field_defects.py::NOT_FOUND` („Mangel nicht gefunden.“), `app/defects.py::report_remedied()`
  (Datum der Beseitigung vor der Abnahme). Im Kopf von `mobil_offen.html` steht die Regel als Kommentar.
- Bleibt „Befund“ (Befund aus Einsatzberichten): „Noch offen“ (seit 1.9.66), „Befund nicht gefunden.“ in `app/routers/findings.py` und
  `app/service_reports.py` (seit 1.9.68).
- Festlegung 1.9.68 Nr. 1 ist damit ersetzt; Nr. 2 und Nr. 3 gelten weiter (Nr. 2 ist gegenstandslos: der Weg der Monteurin sagt wieder
  „Mangel“).

**Tests und Prüfung**

- Neu `tests/test_v493_mangel_und_befund.py` (4 Tests): „Heute“ mit „Mängel zur Beseitigung“; „Heute / Offen“ für die Monteurin mit
  „Mangel“ in Überschrift, leerer Liste, Bestätigung und Bildtext, nirgends „Befund“; die Meldungen ihres Wegs sagen „Mangel“; der Befund
  des Einsatzberichts bleibt „Befund“ („Noch offen“, „Befund nicht gefunden.“, Schritt „Befunde“).
- Angepasste Erwartungen (alt -> neu), zurück auf den Stand vor 1.9.68: `test_v354` „Befund nicht gefunden.“ -> „Mangel nicht gefunden.“;
  `test_v476` „Befunde zur Beseitigung“ -> „Mängel zur Beseitigung“; `test_v399` Beschreibung „Befund als beseitigt melden“ -> „Mangel als
  beseitigt melden“; `klicktest_maengel_monteur` „Befund als beseitigt gemeldet …“/„Keine Befunde …“ -> „Mangel …“/„Keine Mängel …“.
- **Gegenproben 1.9.69**: „Heute / Offen“ sagt „Befunde zur Beseitigung“ -> `test_v493` 1 rot; der Weg der Monteurin meldet „Befund nicht
  gefunden.“ -> `test_v493` und `test_v354` je 1 rot; der Befund im Bericht meldet „Mangel nicht gefunden.“ -> `test_v493` 1 rot.

### R4 Nachrunde, Punkt 2 (1.9.70): „Noch offen“ mit der Dachfläche

- `app/service_reports.py::noch_offen_je_schritt()`: `_flaechen_des_berichts()` (Fläche -> Name aus dem Schnappschuss am Bericht, nur bei
  mehr als einer Fläche), `_befund_flaeche()` (Prüfpunkt, sonst Bauteil); danach werden gleiche Zeilen durchgezählt. `noch_offen()`, die
  Ablehnung der Unterschrift und die Berichtsseite nehmen die Texte unverändert daraus.

**Festlegungen 1.9.70 (Bitte bestätigen)**

1. Die Fläche steht als „ · <Name der Fläche>“ am Ende der Zeile (Name wie am Bericht festgehalten), nur bei mehr als einer Fläche am Bericht.
2. Ein Befund bekommt die Fläche seines Prüfpunkts, ohne Prüfpunkt die seines Bauteils; ohne beides keine Angabe.
3. Bleiben zwei Zeilen gleich, bekommt die zweite „(2)“, die dritte „(3)“ -- die erste bleibt ohne Zahl.

**Tests und Prüfung**

- Neu `tests/test_v494_noch_offen_flaechen.py` (4 Tests): derselbe Pflichtpunkt auf zwei Flächen -> zwei Zeilen mit Fläche, keine doppelt,
  ebenso in der Ablehnung der Unterschrift; eine Fläche ohne Angabe; Befund mit Fläche über Prüfpunkt und Bauteil, ohne beides ohne; zwei
  gleichnamige Punkte ohne Fläche -> „(2)“.
- `klicktest_bericht_schritte`: neu „Noch offen“ mit beiden Flächen und ohne doppelte Zeile; angepasste Erwartung „Foto zum Befund „Gully
  verstopft, Laub“ aufnehmen“ -> „… aufnehmen · Dachfläche Nord“ (der Bericht hat zwei Flächen).
- **Gegenproben**: ohne Fläche in der Zeile -> `test_v494` 2 rot, Klicktest 2 rot; gleiche Zeilen nicht gezählt -> `test_v494` 1 rot.

### R4 Nachrunde, Punkt 6 (1.9.71): Schlüssel-Scan der Berichtsseite als Monteurin

- Neu `tests/test_v495_bericht_schluessel_monteurin.py`: ein Wartungsbericht der Monteurin mit zwei Dachflächen, Befund und Material aus dem
  Katalog (Einkaufspreis 987,65), Stundenlohn 54,32 an beiden Personen; Zeiten am Berichtstag auf dem Auftrag (sie und ein Kollege), am Vortag
  auf demselben Auftrag und am Berichtstag auf einem anderen Auftrag eines anderen Kunden, dort auch ihr eigener Bericht mit Befund. Am Code war
  nichts zu ändern -- die drei Antworten hielten die Grenze schon.

**Festlegungen 1.9.71 (Bitte bestätigen)**

1. Der Scan nimmt zu den beiden genannten Routen `…/zeiten` dazu -- von dort lädt die Berichtsseite die Zeiten, „Zeiten nur vom Berichtstag“
   lässt sich sonst nicht prüfen.
2. Geprüft werden Schlüssel (`_verboten()`/`_privatadresse()` aus `test_v326`, ohne Ausnahmeliste) und Werte: Einkaufspreis und Stundenlohn als
   Zahl in keinem Wert, `order_id`/`order_number` überall die des Berichts, kein Text des anderen Auftrags (Nummer, Projekt, Titel, Kunde, Befund).
3. Ein vor 1.9.42 unterschriebener Bericht zeigt weiter alle Zeiten des Auftrags (Art „alt“, Festlegung von 1.9.42, nichts wird rückwirkend
   geändert) -- nicht Gegenstand des Tests.

**Tests und Prüfung**

- Neu `test_v495` (4 Tests): keine verbotenen Schlüssel; kein Preis und kein Lohn als Wert; keine Daten anderer Aufträge; Zeiten nur vom Berichtstag.
- **Gegenproben**: Zeiten ab dem Vortag -> „Zeiten“ rot; Zeiten ohne Auftragsfilter -> „Zeiten“ rot; dazu die Auftragsnummer je Zeile -> „andere
  Aufträge“ und „Zeiten“ rot; Stundenlohn im Bericht der Monteurin -> „Schlüssel“ und „Wert“ rot.

### R4 Nachrunde, Punkte 1 und 3 (1.9.72): feste Leiste in Schritt 5, „⋮“ in der Titelzeile

- `service_report.html`: `#abschlussLeiste` nach dem Raster (`position:sticky; bottom:0`, oben runde Ecken und Schatten wie „Noch offen“ hoch)
  mit „Zurück“, `#fehltText`, `#abschliessenKnopf` und `#signStatus`; `abschlussZeichnen()` zeigt sie nur in Schritt 5 eines Entwurfs,
  `inhaltZeichnen()` ruft es nach jedem Zeichnen. Der Punkt: `.punkt-kopf` mit `position:relative`, „⋮“ (`.menue-anker`) direkt nach dem Text
  und absolut oben rechts, der Kopf hält 64 px frei (`.mit-menue`, nur wenn es ein Menü gibt); der Titel bekommt dann 12 px Innenabstand
  oben und unten, damit „⋮“ (48 px) auf der Höhe seiner ersten Zeile steht.
- Ersetzt 1.9.67 Festlegung 1 (Schritt 5 ohne feste Leiste, Knopf am Ende der Karte) -- nicht bestätigt.

**Festlegungen 1.9.72 (Bitte bestätigen)**

1. Die Leiste in Schritt 5: „Zurück“ links, „Fehlt: …“ dazwischen, „Bericht abschließen“ rechts (mindestens 280 px); hoch (unter 1000 px)
   steht „Fehlt: …“ über den Knöpfen. Eine Meldung beim Abschließen steht in der Leiste über den Knöpfen.
2. Die Leiste gibt es nur in Schritt 5 eines Entwurfs; in einem unterschriebenen Bericht zeigt Schritt 5 Unterschriften und PDF ohne Leiste.
3. Die Liste „Noch offen“ bleibt in Schritt 5 in der Karte „Unterschriften“ (wie 1.9.67); die Leiste nennt ihre Zahl in „Fehlt: …“.
4. „⋮“ steht bei jeder Punktart oben rechts auf Höhe der ersten Textzeile; die Eingabe steht daneben (wenn Platz ist) oder darunter.

**Tests und Prüfung**

- `klicktest_bericht_schritte` neu: Schritt 5 quer (1280 × 620) -- ohne Bildlauf „Bericht abschließen“ und „Fehlt: …“ im Bild, der Knopf nicht
  verdeckt, beide Zeichenflächen auf der Seite, die Seite länger als das Fenster; ebenso hoch und nach beiden Unterschriften; andere Schritte
  und der abgeschlossene Bericht ohne Leiste; „⋮“ jedes Prüfpunkts in seiner Titelzeile quer und hoch (mit Bewertungen). Die Messung „≥ 48 px“
  nimmt die Leiste dazu. Keine bestehende Erwartung geändert.
- `test_v460`: `abschluss-leiste` in `NICHT_KARTEN` (Leiste am Fensterrand, oben runde Ecken).
- **Gegenproben**: Leiste ohne `position:sticky` -> Klicktest rot (Schritt 5 quer, hoch, mit Unterschriften); „⋮“ wieder in der Eingabe ->
  Klicktest rot (Titelzeile quer und hoch).

### R4 Nachrunde, Punkt 4 (1.9.73): Status auf „Einsatzberichte“

- `service_reports.html::reportRow()`: `statusKennzeichen('einsatzbericht', r.status)` (Gruppe seit 1.9.67), Kennzeichen
  `ds-status ds-status-<art>` mit der ID `bericht-status-<id>`; `.badge.entwurf`/`.badge.unterschrieben` entfallen (`.badge` bleibt für die
  Art in der Wartungshistorie).

**Festlegungen 1.9.73 (Bitte bestätigen)**

1. Der Status steht an derselben Stelle wie bisher (hinter der Art), Text und Farbe wie im Kopf der Berichtsseite: „Entwurf“ gelb (warn),
   „Unterschrieben“ grün (ok).

**Tests und Prüfung**

- Neu `tests/test_v496_berichtsliste_status.py` (3 Tests): die Zeile nimmt `statusKennzeichen()`, kein Rohwert und kein `.badge` mehr, die Seite
  hat den Baustein mit der Gruppe `einsatzbericht`.
- `klicktest_bericht_schritte` neu: Auftragsseite der Monteurin -- „Entwurf“ (ds-status-warn) und „Unterschrieben“ (ds-status-ok), Schrift ohne
  Großbuchstaben.
- **Gegenprobe**: Zeile wieder mit dem Rohwert als `.badge` -> `test_v496` 2 rot, Klicktest rot („entwurf“, `badge entwurf`, `uppercase`).
  Beim ersten Lauf war der Klicktest auch auf dem echten Stand rot: die neue Prüfung selbst hatte einen Syntaxfehler (`}}` in einem
  Teil ohne f-String) -- vor dem Commit behoben, die Gegenprobe danach erneut gelaufen.

## Stufe 4, R4 Nachtrag (ab 1.9.74): Bericht anlegen ohne Einsatz

Vorgabe vom 24.10.2026 (Start HEAD 2483eb1, live): ohne Einsatz in der Plantafel kann die Monteurin keinen Bericht anlegen (Notdienst,
spontane Reparatur) -- Tobias will das flexibler. Punkte: 0 berichten, ob das vor Stufe 4 auf einem anderen Weg ging; 1 „Heute“: ohne Einsatz
„Bericht anlegen“ in der Karte „Heute ist nichts eingeplant.“, mit Einsatz zusätzlich „Bericht für einen anderen Auftrag“, beides mit dem
Dialog „Für welchen Auftrag?“ (dieselbe Liste wie „Zeit nachtragen“) und danach dem gewohnten Weg zum Anlegen; 2 Server: nur für einen Auftrag
dieser Liste, eine Regel an einer Stelle, sonst 403.

### Punkt 0: Ging das vor Stufe 4 auf einem anderen Weg?

Nein, nicht für einen ungeplanten Auftrag. Vor Stufe 4 (bis 1.9.32, `/mobil` „Einsätze“) führten nur „Heutige Einsätze“ und „Offene Berichte“
zur Seite des Auftrags (`/orders/{id}/service-reports`), dort „+ Bericht“; Zeiterfassung, Stundenzettel und Objektansicht der Monteurin
hatten keinen Weg dorthin (geprüft an 6d81016, 1.9.32). Ohne Einsatz heute kam sie also nur über einen eigenen offenen Bericht oder eine
gemerkte Adresse an „+ Bericht“; der Server ließ jeden Auftrag zu, dem sie an der Arbeitsvorbereitung zugeordnet war (auch ohne Datum) oder
zu dem sie einen eigenen Bericht hatte (`require_field_order_access()`). Daneben seit 1.3.56 „Wartung durchführen“ an einem Wartungsvertrag
eines Objekts, an dem sie in den letzten oder nächsten 14 Tagen eingeplant ist (`field_may_perform_maintenance()`): legt einen ungeplanten
Auftrag samt Bericht an -- heute auf „Heute / Offen“ unter „Wartungen an meinen Objekten“, unverändert. Den Schnellauftrag legt nur das Büro
an (`/api/quick-service-orders`, ab Büro – Auftrag). Einen Notdienst ganz ohne Auftrag ihrer Liste kann die Monteurin auch nach dieser Runde
nicht selbst beginnen: das Büro legt den Auftrag an und plant sie ein (ein Datum an der Arbeitsvorbereitung genügt) -- danach steht er in
ihrer Liste.

### R4 Nachtrag, Punkt 2 (1.9.74): Bericht nur für einen Auftrag der Liste

- `app/planning.py::field_order_in_list(db, employee_id, order_id)`: ob `list_field_bookable_orders()` den Auftrag enthält -- dieselbe Liste
  wie „Zeit nachtragen“ in „Meine Zeiten“ (`app/meine_zeiten.py`), die Auftragsauswahl auf „Heute“ und `GET /api/field-view/time-tracking/
  orders`. `POST /api/orders/{id}/service-reports` fragt für die Monteurin nur noch sie (sonst 403 `BERICHT_NUR_EIGENE_AUFTRAEGE` aus
  `app/meldungen.py`; ohne Mitarbeiter 403 `KEIN_MITARBEITER`); die Liste liegt ganz in der Zugriffsregel (Zuordnung an der
  Arbeitsvorbereitung oder eigener Bericht), die das Anlegen deshalb nicht mehr eigens fragt. Lesen und Bearbeiten bestehender Berichte
  bleiben bei `require_field_order_access()` und `require_field_report_ownership()`.

**Festlegungen 1.9.74 (Bitte bestätigen)**

1. Beim Anlegen gilt nur die Liste: ein Auftrag, dem die Monteurin an der Arbeitsvorbereitung ohne Datum zugeordnet ist, einer außerhalb der
   14 Tage und ein abgeschlossener oder stornierter bekommen keinen neuen Bericht mehr von ihr (bis 1.9.73 schon) -- wie beim Buchen von Zeit.
2. Die Meldung: „Einen Bericht legst du nur für einen deiner Aufträge an – dieselbe Auswahl wie bei „Zeit nachtragen“. Fehlt ein Auftrag, wende
   dich an das Büro.“ (in `app/meldungen.py`).
3. Ein Konto ohne Mitarbeiter bekommt beim Anlegen die gemeinsame Meldung `KEIN_MITARBEITER` (bis 1.9.73 die allgemeine Meldung der
   Auftragsprüfung).
4. „+ Bericht“ auf der Seite des Auftrags bleibt sichtbar; für einen Auftrag außerhalb der Liste kommt die Meldung beim Anlegen (erreichbar nur
   noch über eine gemerkte Adresse oder einen abgeschlossenen Auftrag mit eigenem Bericht).
5. „Wartung durchführen“ behält seine Regel (`field_may_perform_maintenance()`), das Büro legt weiter für jeden Auftrag an.

**Tests und Prüfung**

- Neu `tests/test_v497_bericht_nur_aus_der_liste.py` (10 Tests): ohne heutigen Einsatz (gestern eingeplant) angelegt; zugeordnet ohne Datum,
  vor 30 Tagen, nie zugeordnet, abgeschlossen -> 403 mit Meldung, nichts angelegt; eigener Bericht genügt; für jeden Auftrag „in der Liste“
  (`…/time-tracking/orders`, ebenso „Meine Zeiten“) genau dann, wenn das Anlegen gelingt; Büro für jeden Auftrag; ohne Mitarbeiter 403; die
  Regel an einer Stelle (AST: das Anlegen fragt `field_order_in_list()`, die liest `list_field_bookable_orders()`).
- Angepasste Erwartungen (nur Aufbau, Soll unverändert): `test_v260` (`test_report_and_finding_endpoints_follow_the_same_order_access`,
  `test_own_draft_report_survives_being_taken_off_the_planning`), `test_v372` und `test_v373` (Fixture `welt`, damit auch `test_v374`) legen
  über eine Zuordnung ohne Datum einen Bericht an -- ihr Auftrag wird jetzt für heute eingeplant (`tests/eingeplant.py::heute()`, Datum an der
  Arbeitsvorbereitung). Der gemeinsame Helfer `_assign_via_team` bleibt ohne Datum (15 Dateien, darunter Tests des Zeitfensters selbst).
  Ebenso `klicktest_monteur_dachflaechen` (Max war nur ohne Datum zugeordnet, „Bericht mit Fläche angelegt“ rot): seine Arbeitsvorbereitung
  trägt jetzt heute als Datum -- Soll unverändert (13/13).
- **Gegenproben**: Anlegen wieder mit der Zugriffsregel -> `test_v497` 7 rot; `field_order_in_list()` immer wahr -> 6 rot; Liste mit
  abgeschlossenen Aufträgen -> 2 rot (Anlegen und Liste wandern zusammen).

### R4 Nachtrag, Punkt 1 (1.9.75): „Heute“ -- Bericht anlegen ohne Einsatz

- `app/heute.py::heute_fuer()`: neuer Schlüssel `auftraege` (`list_field_bookable_orders()`, einmal geholt und an `arbeitszeit()` für die
  Auswahl „nichts läuft“ weitergereicht) -- mit und ohne Einsatz, auch während eine Zeit läuft.
- `mobil.html`: ohne Einsatz in der Karte `#berichtOhneEinsatz` („Bericht anlegen“, `knopf-aktion knopf-56`), mit Einsatz nach den Karten
  `.weitere-wege` mit `#berichtAndererAuftrag` („Bericht für einen anderen Auftrag“, `knopf-neutral knopf-klein`); beide öffnen
  `#berichtDialog` („Für welchen Auftrag?“, Dialogkarte mit Knopfleiste unten wie seit 1.9.65): je Auftrag aus `H.auftraege` eine Zeile
  (Auftragsnummer, darunter Kunde · Adresse, 64 px) als Link `/orders/<id>/service-reports?neu=1`, leer derselbe Hinweis wie in „Meine Zeiten“.
- `service_reports.html`: `?neu=1` öffnet nach dem Laden der Berichte `openCreateEditor()` (Art Rapport, Datum heute wie „+ Bericht“) und
  entfernt den Parameter aus der Adresse (`history.replaceState`).

**Festlegungen 1.9.75 (Bitte bestätigen)**

1. „Bericht anlegen“ ohne Einsatz ist grün (die Hauptaktion dieser Karte), 56 px, in der Karte unter „Heute ist nichts eingeplant.“
2. „Bericht für einen anderen Auftrag“ steht einmal unter allen Einsatzkarten (außerhalb der Karten), neutral, 48 px.
3. Der Dialog zeigt die Aufträge als Zeilen zum Antippen (Auftragsnummer, darunter Kunde · Adresse; ein Tipp öffnet die Seite des Auftrags)
   statt Auswahlliste mit „Weiter“ wie bei „Zeit nachtragen“ -- dieselbe Liste in derselben Reihenfolge (neueste Auftragsnummer zuerst), ein
   Tipp weniger, Ziele ≥ 56 px.
4. Die Liste enthält auch die Aufträge mit heutigem Einsatz -- es ist dieselbe Liste wie „Zeit nachtragen“, nicht nur „andere“.
5. Ohne Auftrag in der Liste bleibt der Knopf; der Dialog sagt „Keine eigenen Aufträge im Zeitraum gefunden. Fehlt ein Einsatz, wende dich an
   das Büro.“ (wie „Meine Zeiten“).
6. Läuft eine Zeit seit einem früheren Tag (vergessener Feierabend), gibt es wie bisher keine Einsatzkarte und damit keinen der beiden Knöpfe --
   zuerst Feierabend nachtragen.
7. Nach der Wahl öffnet die Seite des Auftrags „Bericht anlegen“ gleich (Art Rapport, Datum heute); die Adresse verliert `?neu=1` (Neuladen
   öffnet nicht noch einmal), „Abbrechen“ bleibt auf der Seite des Auftrags.
8. „Bericht anlegen“ in der Einsatzkarte führt wie bisher auf die Seite des Auftrags, ohne den Editor zu öffnen.

**Tests und Prüfung**

- Neu `tests/test_v498_heute_bericht_anlegen.py` (4 Tests): ohne Einsatz liefert „Heute“ die Liste (= `list_field_bookable_orders()`), mit
  Einsatz und laufender Zeit ebenso; Knöpfe, Dialog und Zeilen aus `H.auftraege` mit `?neu=1` (Aufbau); `?neu=1` öffnet den Editor nach dem
  Laden der Berichte.
- Neu `scripts/klicktest_bericht_ohne_einsatz.py`: Mia ohne Einsatz -- Knopf in der Karte (grün, 56 px), Dialog mit genau ihrer Liste
  (B, A; nicht F), Zeilen ≥ 56 px mit `?neu=1`, „Abbrechen“, Zeile A -> „Bericht anlegen“ offen (Rapport, heute, Adresse ohne `?neu`),
  „Anlegen“ -> neuer Bericht an A von Mia; F über die API 403 mit der Meldung; hoch mit Dialog und Knopfleiste im Bild. Tom mit Einsatz --
  „Bericht anlegen“ in der Karte wie bisher, darunter „Bericht für einen anderen Auftrag“ (neutral, 48 px, außerhalb der Karte), Dialog mit C
  und A. Keine JS-Fehler.
- Keine bestehende Erwartung geändert (`klicktest_heute` misst die neuen Knöpfe mit, ≥ 48 px).
- **Gegenproben**: kein Knopf ohne Einsatz -> `test_v498` 1 rot, Klicktest 6 rot; kein Knopf für einen anderen Auftrag -> `test_v498` 1
  rot, Klicktest 3 rot; `?neu=1` nicht ausgewertet -> `test_v498` 1 rot, Klicktest 1 rot (Adresse mit `?neu=1`, Datum leer); Liste nur,
  wenn nichts läuft -> `test_v498` 1 rot.

## Stufe 4, R4 Nachtrag 2 (ab 1.9.76): Liste der Aufträge

Vorgabe vom 24.10.2026 (Start HEAD 8d47237): Festlegungen des Nachtrags bestätigt, außer 1.9.74 Nr. 1 (-> Punkt 1) und Nr. 4 (-> Punkt 2).
Punkte: 1 die Liste (`list_field_bookable_orders()`) enthält zusätzlich Aufträge, denen die Monteurin an der Arbeitsvorbereitung ohne Datum
zugeordnet ist -- für „Zeit nachtragen“, „Heute“ und das Anlegen gleich (eine Funktion); abgeschlossene, stornierte und solche außerhalb der
14 Tage bleiben draußen; 2 Seite des Auftrags: „+ Bericht“ nur, wenn der Auftrag in ihrer Liste ist, sonst an seiner Stelle „Für diesen Auftrag
legt das Büro Berichte an.“; 3 jede Zeile der Liste nennt den Titel des Auftrags -- im Dialog „AUF-2026-0102 · Attika“, darunter „Halle Nord ·
Hallenbau GmbH · Werkstr. 5, …“, in der Auswahl „Auftrag“ einzeilig, gekürzt.

### R4 Nachtrag 2, Punkt 1 (1.9.76): Aufträge ohne Datum in der Liste

- `app/planning.py::_undatiert_zugeordnete_order_ids()`: Aufträge aus `employee_assigned_order_ids()` (einzeln oder über die Kolonne), deren
  Arbeitsvorbereitung weder einen Abschnitt der Plantafel noch einen geplanten Zeitraum trägt; `list_field_bookable_order_ids()` nimmt sie
  ungefenstert dazu (wie die Aufträge mit eigenem Bericht). `list_field_bookable_orders()` filtert wie bisher abgeschlossene und stornierte;
  `field_order_in_list()`, „Meine Zeiten“, „Heute“ und `GET /api/field-view/time-tracking/orders` fragen alle diese eine Funktion.
- Ersetzt 1.9.74 Festlegung 1 (ohne Datum kein Bericht) -- nicht bestätigt. Die Testanpassungen von 1.9.74 sind zurückgenommen: `test_v260`
  (zwei Tests), `test_v372`, `test_v373` (damit `test_v374`) und `klicktest_monteur_dachflaechen` legen ihren Bericht wieder über eine
  Zuordnung ohne Datum an, `tests/eingeplant.py` ist gelöscht.

**Festlegungen 1.9.76 (Bitte bestätigen)**

1. „Ohne Datum“ heißt: die Arbeitsvorbereitung trägt weder einen Abschnitt der Plantafel noch einen geplanten Zeitraum; zugeordnet einzeln oder
   über die Kolonne. Trägt sie ein Datum, entscheidet weiter das Zeitfenster (14 Tage vor und nach heute).
2. „Wartungen an meinen Objekten“ (eigene Liste der Objekte, `list_field_relevant_property_ids()`) nimmt Aufträge ohne Datum weiter nicht auf.
3. Das Buchen von Zeit prüft auf dem Server weiter die Zugriffsregel (`require_field_order_access()`: zugeordnet mit oder ohne Datum, eigener
   Bericht) -- die Liste liegt darin. Über die API bucht die Monteurin damit weiter auch auf einen abgeschlossenen Auftrag, den keine Liste
   zeigt (unverändert seit 1.7.9, hier nur festgehalten).

**Tests und Prüfung**

- Neu `tests/test_v499_liste_ohne_datum.py` (8 Tests): einzeln und über die Kolonne ohne Datum -> in der Liste (Funktion, Auswahl der
  Zeiterfassung, „Meine Zeiten“, „Heute“), Bericht und Nachtrag gehen; nie zugeordnet -> Bericht und Nachtrag 403 wie bisher; abgeschlossen,
  storniert, außerhalb der 14 Tage -> nicht in der Liste, 403; „Wartungen an meinen Objekten“ unverändert.
- Angepasste Erwartungen: `test_v497` -- „ohne_datum“ 403 -> in der Liste und angelegt (aus der Parametrisierung der 403 genommen, in der
  Menge „in der Liste = angelegt“ ergänzt). Zurück auf den Stand vor 1.9.74 (Aufbau): `test_v260`, `test_v372`, `test_v373`,
  `klicktest_monteur_dachflaechen`.
- **Gegenproben**: ohne Datum nicht in der Liste -> `test_v499` 3 rot, `test_v497` 1 rot; jede Zuordnung ohne Zeitfenster -> `test_v499` 2 rot,
  `test_v497` 2 rot; abgeschlossene in der Liste -> `test_v499` 2 rot, `test_v497` 2 rot.

### R4 Nachtrag 2, Punkt 2 (1.9.77): „+ Bericht“ nur für Aufträge der Liste

- `OrderFieldAccessOut.bericht_anlegen` (`app/schemas.py`), gesetzt in `app/routers/orders.py::get_order()` für die Monteurin aus
  `field_order_in_list()` -- dieselbe Regel wie `POST /api/orders/{id}/service-reports`.
- `service_reports.html`: „+ Bericht“ (`#neuerBericht`) für die Monteurin im Markup verborgen, `berichtKnopfZeichnen()` zeigt ihn nach dem
  Laden des Auftrags (`berichtAnlegenErlaubt()`), sonst `#berichtNurBuero` („Für diesen Auftrag legt das Büro Berichte an.“) an derselben
  Stelle; `?neu=1` wartet auf den Auftrag und öffnet „Bericht anlegen“ nur, wenn sie darf.
- Ersetzt 1.9.74 Festlegung 4 („+ Bericht“ bleibt sichtbar, Meldung erst beim Anlegen) -- nicht bestätigt.

**Festlegungen 1.9.77 (Bitte bestätigen)**

1. Die Seite fragt den Server (`bericht_anlegen` an der Antwort des Auftrags) statt selbst zu rechnen; für die Monteurin ist „+ Bericht“ bis
   dahin verborgen (kein kurzes Aufblitzen), das Büro sieht ihn sofort.
2. Der Hinweis steht rechts in der Kopfzeile der Karte „Berichte zu diesem Auftrag“, in gedämpfter Schrift.
3. `?neu=1` (aus dem Dialog auf „Heute“) öffnet „Bericht anlegen“ nur für einen Auftrag der Liste; sonst bleibt es beim Hinweis.

**Offene Frage (nicht gebaut)**: auf derselben Seite bleibt „Zeit nachtragen“ auch für einen Auftrag außerhalb der Liste; „Meine Zeiten“
wählt ihn dann als „… (nicht in der Auswahl)“ vor, und der Server bucht ihn (Zugriffsregel, 1.9.76 Festlegung 3). Soll „Zeit nachtragen“ dort
ebenso dem Hinweis weichen?

**Tests und Prüfung**

- Neu `tests/test_v500_auftragsseite_bericht_knopf.py` (3 Tests): für jeden zugänglichen Auftrag meldet `GET` `bericht_anlegen` genau dann,
  wenn das Anlegen gelingt (ohne Datum und eigener Bericht ja; vor 40 Tagen eingeplant und abgeschlossen mit eigenem Bericht nein); das Büro
  legt weiter an; Aufbau der Seite (Knopf verborgen für die Monteurin, Hinweis, Kennzeichen, `?neu=1` nach dem Auftrag).
- `klicktest_bericht_ohne_einsatz` neu: Seite von G (vor 40 Tagen eingeplant, auch mit `?neu=1`) ohne „+ Bericht“ mit dem Hinweis und ohne
  Editor (Bild 6, ganze Seite); Seite von A mit „+ Bericht“ ohne Hinweis.
- Angepasste Erwartung: `test_v260` `test_field_gets_only_assigned_orders_and_no_prices` -- Felder der Antwort an die Monteurin
  `{id, order_number, customer_name, items}` -> dazu `bericht_anlegen` (und es ist für den ohne Datum zugeordneten Auftrag wahr).
- **Gegenproben**: Server meldet immer `bericht_anlegen` -> `test_v500` 1 rot, Klicktest 1 rot; Seite fragt das Kennzeichen nicht ->
  `test_v500` 1 rot, Klicktest 1 rot; `?neu=1` ohne Prüfung -> `test_v500` 1 rot, Klicktest 1 rot (Editor offen).

### R4 Nachtrag 2, Punkt 3 (1.9.78): der Titel in jeder Zeile der Liste

- `list_field_bookable_orders()` liefert dazu `title` und `property_name` (Schnappschuss am Auftrag).
- Neu `app/templates/_auftrag_text.html`: `auftragTitel(o)` („Nummer · Titel“), `auftragNeben(o)` („Objekt · Kunde · Adresse“),
  `auftragText(o)` (beides einzeilig, höchstens `AUFTRAG_TEXT_MAX` = 60 Zeichen, sonst mit „…“ gekürzt). `mobil.html` (Auswahl „Auftrag“,
  „Mit Tätigkeit starten“, „Für die Kolonne starten“, Dialog „Für welchen Auftrag?“) und `mobil_zeiten.html` („Zeit nachtragen“, Kolonne)
  binden ihn ein; ihre eigenen `auftragText()` sind entfallen.

**Festlegungen 1.9.78 (Bitte bestätigen)**

1. Im Dialog die erste Zeile „Nummer · Titel“, die zweite „Objekt · Kunde · Adresse“ (Objekt wie am Auftrag festgehalten); fehlt ein Teil,
   entfällt er samt Trenner.
2. In der Auswahl „Nummer · Titel · Objekt · Kunde · Adresse“ in einer Zeile, ab 60 Zeichen nach dem 59. Zeichen mit „…“ gekürzt (nicht an
   einer Wortgrenze).
3. Eine Stelle (`_auftrag_text.html`) für „Heute“ und „Meine Zeiten“; die anderen Auftragsanzeigen (Kopf der Seiten, Einsatzkarten, „Nächste
   Tage“) bleiben, wie sie sind.

**Tests und Prüfung**

- Neu `tests/test_v501_auftrag_mit_titel.py` (4 Tests): die Liste liefert Titel und Objekt; Dialog zweizeilig mit Titel (node, Baustein);
  zwei Aufträge am selben Objekt in der Auswahl verschieden, je höchstens 60 Zeichen, gekürzt mit „…“, kurz ungekürzt; beide Seiten binden
  den Baustein ein und haben keine eigene Fassung.
- `klicktest_bericht_ohne_einsatz` neu: Zeilen des Dialogs „AUF-2026-0102 · Attika“ / „AUF-2026-0101 · Notdienst Rinne“, je darunter „Halle
  Nord · Hallenbau GmbH · Werkstr. 5, 52531 Übach-Palenberg“; Auswahl in „Zeit nachtragen“ einzeilig mit Titel, höchstens 60 Zeichen,
  verschieden (Bild 7, die Auswahl fürs Bild als offene Liste). Keine bestehende Erwartung geändert.
- Aufbau: `tests/test_v334_auswahl_restfaelle.py::BAUSTEINE` nimmt `_auftrag_text.html` auf -- die Attrappe der Seiten in node bindet nur
  Bausteine dieser Liste ein; ohne ihn liefen `test_v450` (drei Tests zu „Meine Zeiten“) im ersten Lauf auf „auftragText is not defined“.
- **Gegenproben**: Titel fehlt in der Liste -> `test_v501` 2 rot, Klicktest 2 rot; Auswahl ungekürzt -> `test_v501` 1 rot, Klicktest 1 rot;
  Dialog ohne Titel -> `test_v501` 1 rot, Klicktest 1 rot.

## Stufe 4, R4 Nachtrag 3 (ab 1.9.79): Berichte zu jedem Auftrag, keine Zeiten auf abgeschlossene

Vorgabe vom 25.10.2026 (Start HEAD ea0db21, live): Festlegungen des Nachtrags 2 bestätigt, außer 1.9.77 Nr. 1–3 (-> A). Entscheidungen von
Tobias: A Berichte -- die Monteurin legt zu jedem Auftrag einen Bericht an, eingeplant oder nicht, auch abgeschlossen, nur stornierte nicht
(403); Dialog „Für welchen Auftrag?“ mit Suchfeld (ab 2 Zeichen; Nummer, Titel, Objekt, Kunde, Adresse; alle nicht stornierten; höchstens 20
Treffer) über „Deine Aufträge“; angelegt direkt aus dem Dialog, danach direkt in den Bericht; die Seite des Auftrags öffnet sich danach über
„eigener Bericht“, sonst keine neuen Leserechte; die Suche liefert nur Anzeigefelder; „+ Bericht“ bei jedem nicht stornierten Auftrag.
B Zeiten -- die Monteurin bucht nicht auf abgeschlossene oder stornierte Aufträge (Start, Nachtrag, Ändern, Kolonne, „Zeitart wechseln“;
„Der Auftrag ist abgeschlossen – Zeiten dafür trägt das Büro ein.“), eine laufende Zeit lässt sich immer beenden, auf der Seite des Auftrags
weicht „Zeit nachtragen“ dort dem Hinweis, das Büro bucht wie bisher. C „Zeit nachtragen“ auf der Seite des Auftrags mit den Ecken der übrigen
Knöpfe.

### Nachtrag 3, A Server (1.9.79): Bericht zu jedem nicht stornierten Auftrag, Suche, Daten zum Anlegen

- `app/service_reports.py::bericht_zum_auftrag_moeglich(order)`: nicht storniert. `POST /api/orders/{id}/service-reports` fragt sie für die
  Monteurin (unbekannt 404, storniert 403 `BERICHT_STORNIERT`, ohne Mitarbeiter 403 `KEIN_MITARBEITER`); `get_order()` setzt
  `bericht_anlegen` daraus; `app/planning.py::field_order_in_list()` ist entfallen.
- `app/planning.py::auftrag_zeile(o)`: die sechs Anzeigefelder (Nummer, Titel, Objekt, Kunde, Adresse, Id) -- für die Liste, die Suche und die
  Daten zum Anlegen.
- `app/search.py::search_orders_for_field(db, q)` und `GET /api/field-view/auftraege-suche` (`response_model=list[FieldOrderLineOut]`): alle
  nicht stornierten Aufträge, Teilwort ohne Groß/Klein in Nummer, Titel, Objekt, Kunde, Adresse, `%` und `_` wörtlich, ab 2 Zeichen, höchstens
  20 (`FIELD_ORDER_SEARCH_LIMIT`), neueste Nummer zuerst; nur mit dem Modul „Wartungen“.
- `GET /api/field-view/auftraege/{id}/bericht-anlegen` (`FieldReportCreateDataOut`): der Auftrag als Zeile und seine Dachflächen (Id, Name) für
  jeden nicht stornierten Auftrag (storniert 403, unbekannt 404).
- Ersetzt 1.9.74–1.9.78 („nur Aufträge der Liste“) und damit 1.9.77 Festlegungen 1–3 (Hinweis statt „+ Bericht“ außerhalb der Liste) --
  den Hinweis „Für diesen Auftrag legt das Büro Berichte an.“ gibt es nur noch beim stornierten Auftrag.

**Festlegungen 1.9.79 (Bitte bestätigen)**

1. Zum stornierten Auftrag kein Bericht von der Monteurin (403 „Der Auftrag ist storniert – dazu legst du keinen Bericht an.“); ein unbekannter
   Auftrag antwortet 404 (bis 1.9.78 403 wie ein fremder -- die Suche zeigt ohnehin alle nicht stornierten).
2. Die Suche: Teilwort ohne Groß/Klein in Nummer, Titel, Objekt, Kunde, Adresse (wie am Auftrag festgehalten), `%` und `_` wörtlich, ab 2
   Zeichen, höchstens 20 Treffer, neueste Nummer zuerst, nur mit dem Modul „Wartungen“.
3. Für das Anlegen aus dem Dialog liest die Monteurin von einem fremden Auftrag dessen Zeile und die Namen seiner Dachflächen (Id, Name) --
   das einzige Lesen außerhalb ihrer Aufträge; ohne Flächen ließe sich kein Wartungsbericht anlegen.
4. Das Büro bleibt unverändert (es legt auch zu einem stornierten Auftrag an).
5. Der Hinweis „Für diesen Auftrag legt das Büro Berichte an.“ statt „+ Bericht“ bleibt für den stornierten Auftrag.

**Tests und Prüfung**

- Neu `tests/test_v502_bericht_zu_jedem_auftrag.py` (17 Tests): Bericht zu nie zugeordnetem offenem und abgeschlossenem Auftrag angelegt, danach
  Leserecht über den eigenen Bericht; storniert 403, nichts angelegt; unbekannt 404; keine neuen Leserechte auf einen anderen Auftrag;
  `bericht_anlegen` wie das Anlegen; Büro unverändert; Suche nach Nummer, Titel, Objekt, Adresse findet den fremden, nie den stornierten; ab 2
  Zeichen, höchstens 20, neueste zuerst; `%`/`_` wörtlich; nur Anzeigefelder ohne verbotene Schlüssel; Daten zum Anlegen (Zeile, Dachflächen
  Id/Name, Schlüssel-Scan; storniert 403, unbekannt 404); eine Regel (AST).
- Entfallen: `tests/test_v497_bericht_nur_aus_der_liste.py` (Regel „nur aus der Liste“, 1.9.74–1.9.78).
- Angepasste Erwartungen: `test_v499` `test_nie_zugeordnet_403_wie_bisher` -> `test_nie_zugeordnet_kein_nachtrag` (Bericht 403 -> angelegt,
  Nachtrag 403 bleibt); `test_abgeschlossen_storniert_und_alt_nicht_in_der_liste_kein_bericht` -> `…_nicht_in_der_liste` (Bericht 403 ->
  angelegt, außer storniert); `test_v500` `test_bericht_anlegen_folgt_der_liste_und_dem_anlegen` -> `…_folgt_dem_anlegen` (`alt` und
  `abgeschlossen_eigen` falsch -> wahr, neu `storniert_eigen` falsch); `test_v260` `test_report_and_finding_endpoints_follow_the_same_order_access`
  (Anlegen zum fremden Auftrag 403 -> 200); `test_v326` Suchbegriff für den Rundgang (Aufbau); `klicktest_bericht_ohne_einsatz` -- F über die
  API 403 -> angelegt (ans Ende von Mias Teil, sonst stünde F danach in ihrer Liste), Seite von G Hinweis -> „+ Bericht“ und Editor bei `?neu=1`,
  neu S (storniert mit eigenem Bericht): Hinweis statt „+ Bericht“ (Bild 6 jetzt S).
- **Gegenproben**: auch zum stornierten -> `test_v502` 2, `test_v500` 1, `test_v499` 1 rot; Suche mit stornierten -> `test_v502` 1 rot; Suche mit
  Kundennummer -> `test_v502` 2 rot; Anlegen nur mit Zugriff -> `test_v502` 6, `test_v499` 1 rot.

### Nachtrag 3, A Oberfläche (1.9.80): Suche und Anlegen im Dialog

- `mobil.html`, Dialog `#berichtDialog`: oben `#auftragSuche` (Hinweis „Ab 2 Zeichen über alle Aufträge.“), darunter `#berichtListeTitel`
  („Deine Aufträge“, „Treffer“, „Keine Treffer“) und `#berichtAuftraege` (Zeilen als Knöpfe mit `data-auftrag`, „Nummer · Titel“ / „Objekt ·
  Kunde · Adresse“); `sucheGeaendert()` liest 250 ms nach dem letzten Tastendruck über `lesen('auftragssuche', …)` und zeichnet eine Antwort
  zu einem überholten Suchbegriff nicht. Zweiter Schritt `#berichtNeu` (`berichtNeuOeffnen()`: `GET /api/field-view/auftraege/{id}/
  bericht-anlegen` und die Vorlagen): Berichtstyp, Datum (heute), Dachflächen als Häkchen, Vorlage nur bei genau einer Fläche (sonst der
  Hinweis), Beschreibung; „Anlegen“ (`berichtAnlegen()`) über `speichern('bericht-neu', …)` an `POST /api/orders/{id}/service-reports`,
  danach `/service-reports/{id}`.

**Festlegungen 1.9.80 (Bitte bestätigen)**

1. Ab 2 Zeichen ersetzen die Treffer „Deine Aufträge“ (Überschrift „Treffer“ bzw. „Keine Treffer“); darunter wieder „Deine Aufträge“. Gesucht
   wird 250 ms nach dem letzten Tastendruck.
2. Der zweite Schritt zeigt oben den gewählten Auftrag, dann Berichtstyp (Rapport vorgewählt), Datum (heute), Dachflächen (nur wenn das Objekt
   welche hat), Vorlage (nur bei genau einer Fläche), Beschreibung (freiwillig) -- wie auf der Seite des Auftrags, ohne „Durchgeführt von“ (der
   Server trägt die Monteurin ein).
3. Knöpfe des zweiten Schritts: „Abbrechen“, „Anderer Auftrag“ (zurück zur Wahl, der Suchbegriff bleibt) und „Anlegen“ (grün).
4. Die Seite des Auftrags behält „+ Bericht“ und `?neu=1`; der Dialog nimmt sie nicht mehr.

**Tests und Prüfung**

- Neu `tests/test_v503_dialog_suche_und_anlegen.py` (3 Tests): Dialog mit Suche, Liste und zweitem Schritt, endet mit der Knopfleiste; Suche ab
  2 Zeichen über den Server ohne überholte Antworten; zweiter Schritt und Anlegen über `speichern()`, danach zum Bericht.
- Angepasste Erwartungen: `test_v498` `test_heute_knoepfe_und_dialog` (die Liste in `berichtDialogOeffnen()` mit Links `?neu=1` -> in
  `eigeneAuftraegeZeigen()`, Zeilen als Knöpfe); `klicktest_bericht_ohne_einsatz` -- Zeilen `[Id, Link mit ?neu=1, ≥ 56 px]` -> `[Id, ≥ 56 px]`,
  „Zeile A -> Seite von A mit offenem Editor, Adresse ohne ?neu“ -> „Zeile A -> im Dialog „Bericht anlegen“ (A, Rapport, heute, Dachfläche,
  Vorlage erst bei einer Fläche)“, „F über die API angelegt“ -> „Suche „auftrag“: G und F, nicht S; aus dem Treffer F angelegt“, die Prüfung der
  Titel (1.9.78) liest die Zeilen über `[data-auftrag]`; die Testdaten bekommen „Dachfläche Nord“.
- **Gegenproben**: Suche nur in der eigenen Liste -> `test_v503` 1 rot, Klicktest 3 rot; Zeile ohne Anlegen im Dialog -> `test_v503` 1 rot,
  Klicktest 5 rot; Vorlage immer zur Wahl -> Klicktest 1 rot.

### Nachtrag 3, B Server (1.9.81): keine Zeiten der Monteurin auf abgeschlossene Aufträge

- `app/time_tracking.py::auftrag_zeiten_gesperrt(order)`: rollenlos, die Meldung bei Status „abgeschlossen“ bzw. „storniert“ (Groß- und
  Kleinschreibung, Leerraum egal), sonst None; Meldungen `AUFTRAG_ABGESCHLOSSEN_ZEITEN`, `AUFTRAG_STORNIERT_ZEITEN` in `app/meldungen.py`.
- `app/routers/time_tracking.py::_require_order_open_for_field(request, db, *order_ids)`: nur für die Rolle `field`, 403 mit der Meldung.
  Aufgerufen in `_require_bookable_order()` nach der Zugangsprüfung -- damit für Start, Nachtrag, den Zielauftrag beim Ändern, Kolonne
  (Nachtrag, Start, Ändern) und „Zeitart wechseln“ --, dazu für den bisherigen Auftrag beim Ändern einer Buchung und einer Kolonnenbuchung,
  beim Löschen beider und für die Buchungen, die „Pausen neu rechnen“ ändern würde. Stopp, Gruppen-Stopp und „Ende nachtragen“ rufen sie
  nicht auf; die Vorschauen lesen nur.

**Festlegungen 1.9.81 (Bitte bestätigen)**

1. Storniert sperrt wie abgeschlossen, mit „Der Auftrag ist storniert – Zeiten dafür trägt das Büro ein.“
2. Gesperrt sind auch: eine Buchung von dort wegschieben, eine Buchung oder Kolonnenbuchung dort löschen, „Pausen neu rechnen“, wenn es eine
   Buchung dort ändern würde -- alle drei ändern Zeiten des Auftrags.
3. 403 wie beim abgeschlossenen Monat; geprüft nach dem Zugang (ein fremder oder unbekannter Auftrag bleibt 403 bzw. 404) und vor dem
   Zeitraum; gilt für die Rolle `field` (auch die Kolonnenführerin), nicht für Büro und Admin.
4. „Meine Zeiten“ und „Heute“ blenden nichts aus: „⋮ Ändern/Löschen“ an einer Buchung eines geschlossenen Auftrags und „Start“ an einem
   Einsatz eines geschlossenen Auftrags bleiben, der Server lehnt mit der Meldung ab; ausgeblendet wird nur „Zeit nachtragen“ auf der Seite
   des Auftrags (1.9.82).

**Tests und Prüfung**

- Neu `tests/test_v504_keine_zeiten_auf_abgeschlossene.py` (10 Tests): Meldung je Status; Start und Nachtrag (abgeschlossen und storniert)
  403, auf dem offenen Auftrag 200, Büro – Auftrag bucht für sich; Ändern dorthin, dort und weg 403, der Admin ändert; Löschen 403, der Admin
  löscht; Kolonne (Nachtrag, Start, Ändern, Wegschieben, Löschen) 403, der Admin trägt nach; „Zeitart wechseln“ 403, der Stopp beendet;
  „Ende nachtragen“ und Gruppen-Stopp auf geschlossenem Auftrag 200; „Pausen neu rechnen“ 403, der Admin rechnet.
- Keine angepassten Erwartungen.
- **Gegenproben** (je rot, FAILED): Buchungsweg ohne Status -> 5 rot; Ändern ohne den bisherigen Auftrag -> 1; Kolonne ändern ohne den
  bisherigen Auftrag -> 1; Löschen ohne Status -> 1; Kolonne löschen ohne Status -> 1; „Pausen neu rechnen“ ohne Status -> 1; Beenden prüft
  den Status (Stopp, Ende nachtragen, Gruppen-Stopp) -> 3; Sperre für alle Rollen -> 6.

### Nachtrag 3, B Oberfläche (1.9.82): Hinweis auf der Seite des Auftrags

- `OrderFieldAccessOut.zeiten_gesperrt` (GET /api/orders/{id} für die Monteurin): `auftrag_zeiten_gesperrt(order)`, sonst null.
- `service_reports.html`, Karte „Zeiten“ (nur im Monteursrahmen): `zeitenKarteZeichnen()` nach dem Laden des Auftrags blendet `#zeitenText` und
  `#zeitNachtragen` aus und zeigt die Meldung in `#zeitenGesperrt`; `.zeit-nachtragen[hidden]{display:none}` (sonst gewänne `display:inline-flex`).

**Festlegungen 1.9.82 (Bitte bestätigen)**

1. Der Hinweis steht in der Karte „Zeiten“ an der Stelle von Text und Knopf, gedämpft wie „Für diesen Auftrag legt das Büro Berichte an.“; die
   Überschrift „Zeiten“ bleibt.
2. Bis der Auftrag geladen ist, steht „Zeit nachtragen“ da wie bisher (der Status kommt mit dem Auftrag).
3. Wird der Auftrag abgeschlossen, während die Seite offen ist, zeigt sie den Hinweis erst nach dem Neuladen; „Meine Zeiten“ lehnt den Nachtrag
   dann im Dialog mit der Meldung ab, der Dialog bleibt offen.

**Tests und Prüfung**

- Neu `tests/test_v505_auftragsseite_zeiten_gesperrt.py` (2 Tests): `zeiten_gesperrt` folgt dem Buchen (beauftragt, abgeschlossen, storniert);
  Karte, Stil und `zeitenKarteZeichnen()` nach dem Laden.
- Neu `scripts/klicktest_zeiten_abgeschlossen.py`: Seite von Z (abgeschlossen) mit Meldung statt Knopf (Bilder 1 hoch, 1a quer), Seite von S
  (storniert), Seite von A (offen) wie bisher; das Büro schließt A, während die Seite offen ist -- „Zeit nachtragen“ -> „Meine Zeiten“ mit A
  „(nicht in der Auswahl)“, „Nachtragen“ -> Meldung im Dialog, nichts gebucht (Bild 2); Ändern der Buchung auf Z abgelehnt, sie bleibt; A neu
  geladen mit Meldung.
- Angepasste Erwartung: `test_v260` `test_field_gets_only_assigned_orders_and_no_prices` -- Schlüssel `{id, order_number, customer_name, items,
  bericht_anlegen}` -> dazu `zeiten_gesperrt` (null am offenen Auftrag).

- **Gegenproben 1.9.82** (nachgetragen mit 1.9.83, gelaufen nach dem Commit b35b0b4; je rot, FAILED): kein Kennzeichen vom Server -> `test_v505`
  1 rot, Klicktest 3 rot; Seite zeichnet die Karte nicht -> `test_v505` 1, Klicktest 3; `hidden` ohne `display:none` -> `test_v505` 1, Klicktest 3
  (der Knopf blieb mit `hidden` 48 px hoch sichtbar).

### Nachtrag 3, Meldung im Dialog (1.9.83): über den Knöpfen in der festen Leiste

Befund am Bild des abgelehnten Nachtrags (1.9.82, 1280 × 620): die Meldung stand am Ende des scrollenden Inhalts, die feste Knopfleiste
(1.9.65) verdeckte ihre untere Hälfte. Gleich gebaut waren sieben Dialoge: `startDialog`, `berichtDialog` (`mobil.html`), `zeitDialog`,
`kolonneDialog`, `loeschDialog`, `abwDialog` samt Ergebnis (`mobil_zeiten.html`), `datumDialog`, `artDialog` (`service_report.html`). Jetzt
steht die Meldung als erstes Element in `.dialog-knoepfe`, mit `flex:1 0 100%` in einer eigenen Zeile über den Knöpfen; leer ohne Platz
(`:empty`). Vorbild: `.abschluss-leiste .meldung` im Einsatzbericht (1.9.72).

**Festlegungen 1.9.83 (Bitte bestätigen)**

1. Jede Meldung eines Dialogs im Monteursrahmen (`role="status"`, auch das Ergebnis des Abwesenheitsantrags) steht in seiner festen
   Knopfleiste über den Knöpfen, über deren ganze Breite.
2. Die sieben Dialoge in einer Version, nicht nur „Zeit nachtragen“ -- alle hatten denselben Aufbau.

**Tests und Prüfung**

- `tests/test_v491_dialog_knopfleiste.py`: neu `test_jede_meldung_steht_in_der_knopfleiste` (keine Meldung vor der Leiste, eigene Zeile
  per CSS, mindestens acht Meldungen in Leisten), Kopf ergänzt.
- `klicktest_zeiten_abgeschlossen`: neu „Die Meldung ganz im Bild, über den Knöpfen und über die ganze Leiste, Ober- und Unterkante
  unverdeckt“.
- Keine angepassten Erwartungen.
- **Gegenproben** (je rot, FAILED): Meldung wieder vor der Leiste -> `test_v491` 1 rot, Klicktest 1 rot (Unterkante verdeckt); Meldung ohne
  eigene Zeile -> `test_v491` 1, Klicktest 1 (nicht über die ganze Leiste). Die erste Fassung der Klicktest-Prüfung tastete nur die Mitte der
  Meldung ab und blieb in beiden Gegenproben grün (die Mitte lag gerade noch über der Leiste; eine lange Meldung bricht auch ohne eigene Zeile
  um) -- verschärft auf Ober- und Unterkante und volle Breite.

**Befund, gemeldet, nicht behoben**: „Zeit nachtragen“ von der Seite eines Auftrags, der nicht in ihrer Liste steht (abgeschlossen seit dem
Öffnen der Seite, außerhalb ±14 Tage), wählt ihn in „Meine Zeiten“ vor, die Auswahl zeigt aber nur die nackte ID: „1 (nicht in der Auswahl)“
(`zeitDialogOeffnen()`, `fehlt` ohne Namen; seit 1.9.67, als die Seite des Auftrags nach „Meine Zeiten“ verlinkte). Vorschlag: „Meine Zeiten“
liefert zur Vorwahl die Zeile des Auftrags mit (`auftrag_zeile()`, nur bei Zugang).

### Nachtrag 3, C (1.9.84): Ecken von „Zeit nachtragen“

`service_reports.html`: `.zeit-nachtragen` (ein `<a>`, die Grundregel `:where(.ds-seite button){border-radius:var(--ds-ecke-feld)}` greift nur
für `button`) bekommt `border-radius:var(--ds-ecke-feld)` -- dieselbe Ecke wie „+ Bericht“ (10 px).

**Festlegung 1.9.84 (Bitte bestätigen)**

1. Die Ecke ist `--ds-ecke-feld` (10 px) wie bei den übrigen Knöpfen der Seite, nicht die Tablet-Ecke `--ds-ecke-tablet-feld` (12 px): die
   Klasse `.ds-tablet`, an der die Tablet-Ecke für Knöpfe hängt (`ds-basis.css`), setzt keine Vorlage (siehe Befund).

**Tests und Prüfung**

- `tests/test_v505_auftragsseite_zeiten_gesperrt.py`: neu `test_zeit_nachtragen_hat_die_ecken_der_knoepfe`.
- `klicktest_zeiten_abgeschlossen`: neu „„Zeit nachtragen“ mit den Ecken von „+ Bericht““ (berechnete Ecke gleich, nicht 0 px), Bild 3.
- Keine angepassten Erwartungen.
- **Gegenprobe**: ohne die Ecke -> `test_v505` 1 rot, Klicktest 1 rot.

**Befund, gemeldet, nicht behoben**: `.ds-tablet` steht nur in `ds-basis.css` (Grundregel der Seite, Ecke der Knöpfe und Felder 12 px) und in
`ds.css` (`.ds-tablet .ds-kopf-titel`), keine Vorlage setzt die Klasse -- der Monteursrahmen legt nur die Ecke der Karten um
(`_mobile_header.html`), der Seitenkopf nimmt `ds-kopf-tablet`. Knöpfe und Felder im Monteursrahmen haben deshalb 10 statt der in Stufe 2
beschlossenen 12 px. Zu entscheiden: die Klasse im Monteursrahmen setzen (alle Knöpfe und Felder dort 12 px, neue Bildgrundlage) oder die
Regeln streichen.

## Stufe 4, R5 (ab 1.9.85): Teil 1 bauen, Teil 2 nur Befund (Büroseiten)

Vorgabe vom 26.10.2026 (Start HEAD cdf41a6, live): Festlegungen des Nachtrags 3 alle bestätigt; zu den drei Befunden entschieden.
Teil 1 bauen: (1) „Meine Zeiten“ nennt die Vorwahl außerhalb der Liste mit ihrer Zeile (nur bei Zugang); (2) der Monteursrahmen setzt
`.ds-tablet` (Knöpfe und Felder 12 px, Seitentitel 26 px; feste Leisten, Dialoge, Ziele ≥ 48 px mitprüfen; neue Bildgrundlage); (3) ein
abgeschlossener oder stornierter Auftrag wird auf „Heute“ nicht vorbelegt, seine Einsatzkarte zeigt „Auftrag abgeschlossen“, in „Meine
Zeiten“ kein „⋮“ an Buchungen dort; (4) Werkzeug: Port-Wettlauf beheben (1.9.85, `docs/archiv/testablauf-und-klicktests.md`, „Umsetzung
1.9.85“). Teil 2: Befund der Büroseiten der Zeiterfassung, nichts bauen.

### R5, Punkt 1 (1.9.86): die Vorwahl beim Namen

- `GET /api/field-view/meine-zeiten?vorwahl=<id>` (`app/routers/field_view.py`): `"vorwahl"` = `auftrag_zeile()` samt `"geschlossen"`
  (`app/time_tracking.py::auftrag_geschlossen()`, neu: abgeschlossen/storniert, dieselbe Regel wie `auftrag_zeiten_gesperrt()`), nur bei
  Zugang -- die Monteurin über `field_may_access_order()`, das Büro immer; sonst null, ohne Fehler.
- `mobil_zeiten.html`: `laden()` schickt die Vorwahl aus der Adresse mit; `vorwahlText()` für die Auswahl „Auftrag“ in „Zeit nachtragen“ und
  „Nachtrag für die Kolonne“, wenn die Vorwahl nicht in der Liste steht.

**Festlegungen 1.9.86 (Bitte bestätigen)**

1. Die Vorwahl außerhalb der Liste heißt „Nummer · Titel (Auftrag abgeschlossen)“, „(Auftrag storniert)“ bzw. „(nicht in der Auswahl)“ --
   nicht die ganze Zeile mit Objekt und Adresse: die schnitt das Feld bei 1280 × 620 vor dem Kennzeichen ab.
2. Ohne Zugang (fremder oder unbekannter Auftrag) ist `vorwahl` null, die Auswahl zeigt wie bisher die Nummer; ein Fehler entsteht nicht.
3. Das Büro (mit Mitarbeiter auf „Meine Zeiten“) bekommt jede Vorwahl.

**Tests und Prüfung**

- Neu `tests/test_v507_vorwahl_zeile.py` (5 Tests): Kennzeichen als Wort; Vorwahl mit Zugang, auch abgeschlossen und außerhalb der Liste;
  fremd oder unbekannt null, nichts über den Auftrag, 0 abgelehnt (422); Büro jede; die Seite fragt und nennt die Vorwahl.
- Angepasste Erwartung: `klicktest_zeiten_abgeschlossen` „A gewählt, als „nicht in der Auswahl“ gekennzeichnet“ `[Id, true]` -> „A gewählt,
  beim Namen und als abgeschlossen gekennzeichnet“ `[Id, „AUF-2026-0201 · Dachsanierung (Auftrag abgeschlossen)“, true]`; neu Bild 2a.
  `test_v400` `test_meine_zeiten_month_change_the_last_chosen_month_wins`: der node-Aufbau legt `VORWAHL=null` an (nur Aufbau, `laden()`
  liest sie jetzt).
- **Gegenproben** (je rot, FAILED): Vorwahl ohne Zugangsprüfung -> `test_v507` 1; Seite fragt die Vorwahl nicht -> `test_v507` 1, Klicktest 1;
  Vorwahl ohne Namen -> `test_v507` 1, Klicktest 1.

### R5, Punkt 3 (1.9.87): abgeschlossene Aufträge auf „Heute“ und in „Meine Zeiten“

- `app/heute.py`: `einsaetze()` trägt je Karte `auftrag_geschlossen` (Status der Aufträge in einer Abfrage); `arbeitszeit()` im Zustand
  „läuft“ ebenso; „nichts“: `vorbelegt` aus den Einsätzen, die in ihrer Liste stehen (`set(einsatz_auftraege) & buchbar`).
- `app/meine_zeiten.py::_zeile()`: `auftrag_geschlossen` je Buchung.
- `mobil.html`: Einsatzkarte mit `.einsatz-zu` („Auftrag abgeschlossen“) unter Kunde und Adresse, beim stornierten ohne „Bericht anlegen“;
  `laeuftKarte()` auf einem geschlossenen Auftrag nur „Feierabend“, das Kennzeichen in der Unterzeile. `mobil_zeiten.html`: `menueHtml()`
  ohne „⋮“, `zeileHtml()` mit `.zeile-zu`, der Pausenhinweis ohne „Pausen neu rechnen“, wenn die Vorschau eine solche Buchung ändern würde.

**Festlegungen 1.9.87 (Bitte bestätigen)**

1. Die Einsatzkarte hatte nie einen Start-Knopf -- gestartet wird in der Karte „Arbeitszeit“, und dort steht ein geschlossener Auftrag nicht
   zur Wahl. „Statt Start“ heißt deshalb: das Kennzeichen „Auftrag abgeschlossen“ bzw. „Auftrag storniert“ in der Einsatzkarte unter Kunde und
   Adresse, als Marke.
2. Vorbelegt wird der einzige offene Einsatz, auch wenn daneben ein geschlossener steht (bis 1.9.86 dann keiner).
3. Läuft die Zeit auf einem geschlossenen Auftrag: nur „Feierabend“ (kein „Zeitart wechseln“), das Kennzeichen in der Unterzeile.
4. Beim stornierten Einsatz kein „Bericht anlegen“ (der Server lehnt seit 1.9.79 ab); „Checklisten zum Auftrag“ bleibt.
5. „Meine Zeiten“: an der Buchung „Auftrag abgeschlossen“ unter dem Titel, kein „⋮“; würde „Pausen neu rechnen“ eine solche Buchung ändern,
   steht statt des Knopfs „Auftrag abgeschlossen – das Büro rechnet neu.“

**Tests und Prüfung**

- Neu `tests/test_v508_abgeschlossen_heute_und_zeiten.py` (6 Tests): Vorbelegung nur des offenen, Kennzeichen an der Karte (Gegenprobe beide
  offen); nur ein geschlossener -> nichts vorbelegt; laufende Zeit mit Kennzeichen; Buchung mit Kennzeichen; Seiten „Heute“ und „Meine Zeiten“.
- Angepasste Erwartungen: `klicktest_zeiten_abgeschlossen` -- Z heute statt gestern eingeplant (Aufbau, Einsatzkarte auf „Heute“); „Ändern der
  Buchung auf Z abgelehnt: die Meldung im Dialog“ und „Die Buchung bleibt 06:00–07:00“ -> „Buchung auf Z: kein „⋮“, Kennzeichen „Auftrag
  abgeschlossen““ `[false, „Auftrag abgeschlossen“]` (der Dialog ist dort nicht mehr erreichbar); neu „Heute: Karte von Z mit „Auftrag
  abgeschlossen“, A ohne; A vorbelegt, Z nicht in der Auswahl“, Bild 0. `test_v460`: `einsatz-zu` unter den Kennzeichen (neue umrandete Fläche).
- **Gegenproben** (je rot, FAILED): Vorbelegung zählt den geschlossenen mit -> `test_v508` 2; Einsatzkarte ohne Kennzeichen -> `test_v508` 2,
  Klicktest 1; Buchung dort mit „⋮“ -> `test_v508` 1, Klicktest 1; laufende Zeit dort mit „Zeitart wechseln“ -> `test_v508` 1; Buchung ohne
  Kennzeichen (Server) -> `test_v508` 1.

**Befund, gemeldet, nicht behoben**: zwei Einsätze am selben Objekt sehen auf „Heute“ gleich aus -- die Karte nennt Objekt, Kunde und Adresse,
nicht Nummer und Titel des Auftrags (im Bild 0 unterscheidet sie nur das Kennzeichen). Vorschlag: „Nummer · Titel“ in der Karte, wie in „Für
welchen Auftrag?“.

### R5, Punkt 2 (1.9.88): der Monteursrahmen setzt .ds-tablet

- `<body>` jeder Vorlage mit `_mobile_header.html`: immer (`mobil`, `mobil_zeiten`, `mobil_offen`, `mobil_objekt`,
  `operational_asset_field`), nach `monteursrahmen` (`account`, `service_report`, `service_reports` -- dort steht das `{% set monteursrahmen %}`
  jetzt am Anfang der Vorlage, Jinja rendert der Reihe nach) bzw. nach `is_field` (`checklist`, `checklist_order`).
- `ds-basis.css`: neue Grundregel `min-height: 48px` für Knöpfe, Auswahlen und einzeilige Felder unter `.ds-seite.ds-tablet` (Gewicht null);
  `ds.css`: `.ds-tablet .ds-knopf` mit `--ds-ecke-tablet-feld`; `service_reports.html`: `.ds-tablet .zeit-nachtragen` ebenso; `checklist.html`,
  `_checklists_section.html`, `mobil_objekt.html`: ihre eigenen 44 px im Tablet bzw. immer 48 px; `service_report.html`: `.segment` ohne Ecke.
- Gemessen vorher (Stand 7b4c1cf): 59 von 105 Prüfungen -- die Klasse fehlte überall; Ecken 10 px an Knöpfen und Feldern von Einsatzberichten,
  Bericht (Kopfknopf, mittleres Segment), Checkliste, Checklisten zum Auftrag, Konto, Heute / Offen, Objekt; Ziele unter 48 px: Konto (Felder
  und Knopf 40 px), Objekt („Hochladen“, Kategorie 44 px), Checkliste (Knöpfe 44 px, Felder 47 px), Checklisten zum Auftrag (Start 44 px).
  Nachher 105 von 105.

**Festlegungen 1.9.88 (Bitte bestätigen)**

1. Die Klasse setzt der Server am `<body>`, unter derselben Bedingung wie die Einbindung des Monteurskopfs; „Heute“ und „Meine Zeiten“ tragen sie
   auch (sie sind noch nicht umgezogen, die Grundregeln wirken dort nicht -- ihre Knöpfe haben die 12 px schon selbst).
2. Mit der Klasse kommt die Grundschrift 17 px (`--ds-groesse-5`, in `ds-basis.css` seit 1.8.161 für das Tablet vorgesehen) auf die umgezogenen
   Monteursseiten.
3. Ziele im Tablet mindestens 48 px als Grundregel (Knöpfe, Auswahlen, einzeilige Felder; nicht Häkchen, nicht mehrzeilige Felder); wo eine
   Seite selbst 44 px setzte, im Tablet 48 px.
4. Der Knopf des Seitenkopfs (`.ds-knopf`) im Tablet 12 px; die Einträge der Menüs bleiben, wie sie sind.
5. Die Segmentgruppe im Bericht innen ohne Ecke, außen 12 px.

**Tests und Prüfung**

- Neu `tests/test_v509_ds_tablet.py` (3 Tests): jede Monteursseite setzt die Klasse unter derselben Bedingung wie den Monteurskopf; die Büroansicht
  derselben Vorlage ohne (gerendert als Monteurin und als Büro); die Regeln in `ds.css`, `ds-basis.css`, Einsatzberichte und Bericht.
- Neu `scripts/klicktest_tablet.py` (105 Prüfungen, Testdaten und Seiten der Bildgrundlage): je Seite der Monteurin bei 1280 × 620 und 800 × 1100
  Klasse, Seitentitel 26 px, Ecken 12 px (Segmentgruppen als Gruppe, rahmenlose Textknöpfe ohne), Ziele ≥ 48 px; Dialog „Zeit nachtragen“ samt
  Knopfleiste im Bild.
- Keine angepassten Erwartungen.
- **Gegenproben** (je rot, FAILED): Konto ohne `ds-tablet` -> `test_v509` 2, Klicktest 6; Grundregel ohne Mindesthöhe -> `test_v509` 1,
  Klicktest 2; Knopf des Seitenkopfs ohne Tablet-Ecke -> `test_v509` 1, Klicktest 4; Segment in der Mitte mit Ecke -> `test_v509` 1, Klicktest 2.

### R5, Punkt 2: neue Bildgrundlage (nach 1.9.88)

Vor dem Umbau `bildgrundlage/cdf41a6` (314 Bilder), danach `bildgrundlage/8b68dda` (314 Bilder, sauberer Stand nach 1.9.88). Vergleich: 241 gleich,
73 abweichend (Differenzbilder `bildgrundlage/vergleich_cdf41a6_8b68dda`):
- 62 Bilder der Monteurin -- alle Seiten im Monteursrahmen (`.ds-tablet`: 12-px-Ecken, Ziele ≥ 48 px, Grundschrift 17 px).
- 11 Bilder des Büros: „mobil_objekt“ 4 (die Objektseite steht für jede Rolle im Monteursrahmen), „bericht“ 4 (das mittlere Segment ohne Ecke, auch
  in der Büroansicht), „angebot“ 2 und „kalender“ 1 -- Rauschen der Darstellung (die Beschriftung „+ Übernehmen“ um ein Pixel versetzt, die
  Kantenglättung des Symbols in der Leiste); beide Seiten hat die Runde nicht berührt, die neue Regel in `ds.css` greift dort nicht.

### R5, Teil 2: Befund der Büroseiten der Zeiterfassung (nichts gebaut)

**Welche Seiten.** `AUFGESCHOBEN` (`tests/test_v441_rahmen_baustein.py`) führt für Stufe 4 seit 1.9.59 nur noch „Heute“ (`mobil.html`) und „Meine
Zeiten“ (`mobil_zeiten.html`) -- die Liste „Einsätze, Zeiterfassung der Monteure, Stundenzettel -> 4“ in CLAUDE.md ist überholt: „Einsätze“ hieß
`/mobil` bis 1.9.45 (heute „Heute“), Zeiterfassung und Stundenzettel der Monteurin ersetzt seit 1.9.59 „Meine Zeiten“ (die alten Adressen leiten
weiter). Büroseiten der Zeiterfassung sind die „Zeiterfassung“ (`/time-tracking`, `time_tracking.html`, umgezogen seit 1.9.7) und das
„Zeiterfassungs-Backoffice“ (`/time-backoffice`, `time_backoffice.html`, umgezogen seit 1.9.21); den Stundenzettel des Büros gibt es als Reiter
„Stundenzettel“ im Backoffice. Ein Büro-Konto auf `/mobil` sieht nur „Die Einsätze gibt es nur in der Monteursansicht.“ in Fehlerfarbe (das
Wort „Einsätze“ ist dort übrig geblieben, der Reiter heißt „Heute“), auf `/mobil/zeiten` mit verknüpftem Mitarbeiter „Meine Zeiten“ mit der
roten Zeile „Keine eigenen Aufträge im Zeitraum gefunden. Fehlt ein Einsatz, wende dich an das Büro.“ -- an das Büro selbst (Bilder 7 und 8).
Die Zeile in CLAUDE.md („Einsätze, Zeiterfassung der Monteure, Stundenzettel -> 4“) ist überholt und wird mit dem nächsten Code-Commit
nachgezogen.

#### Zeiterfassung (`/time-tracking`)

Zweck: die eigenen Zeiten des Büro-Kontos erfassen (Uhr, Nachtrag), als Admin auch die anderer; Kolonne buchen; Abwesenheit beantragen; ein Tag
zur Auswertung. Rollen: Büro – Auftrag, Büro – Finanzen, Admin (die Monteurin leitet die Seite zu „Meine Zeiten“ um); nur der Admin wählt einen
Mitarbeiter, bucht für andere und entscheidet Anträge. Ohne verknüpften Mitarbeiter der Hinweis „Konto ohne Mitarbeiter“.

Funktionen:
- „Mitarbeiter“ (nur Admin): wessen Zeiten die Seite zeigt und bucht.
- „Laufende Zeiterfassung“: Uhr, Auftrag, Zeitart; „■ Zeit stoppen“ mit zusätzlicher Pause; seit 1.9.35 bei einer Zeit von früher „Ende
  nachtragen“ (Ende am Starttag).
- „Schnell starten“: Auftrag (nur offene), LV-Position, Tätigkeit, Notiz, vier Knöpfe „▶ Baustelle / Fahrzeit / Werkstatt / Sonstige“; Link zum
  Rapport des Auftrags.
- „Heutige Buchungen“: Kacheln Produktiv, Fahrzeit, Gesamt; Liste mit „Ändern“ und „×“ (Löschen).
- „+ Manuell buchen“: Dialog Mitarbeiter (Admin), Datum, Auftrag, LV-Position, Zeitart, Tätigkeit, Stunden (netto), Pause, Notiz -- eine Dauer,
  kein Von/Bis; dasselbe Formular für „Ändern“.
- „👥 Gruppe buchen“: Kolonne, Mitglieder, Auftrag, LV-Position, Zeitart, Tätigkeit, Datum, Stunden je Mitarbeiter, Pause; „Manuell buchen“
  oder „▶ Gruppen-Timer starten“.
- „📅 Abwesenheit“: Antrag (Kategorie, Art, Von, Bis, Notiz), Liste der Anträge, Admin genehmigt/lehnt ab, eigene zurückziehen; Hinweis auf
  offene Anträge (Admin).
- „Auswertung“: die Buchungen eines gewählten Tags.

Was dort aus Stufe 4 fehlt oder nicht passt:
- Offene Zeiten von früher: sichtbar nur die eigene (Admin: die des gewählten Mitarbeiters), keine Übersicht aller offenen Zeiten; schließen für
  andere nur der Admin (`darf_zeit_fuer_andere_buchen()`).
- „Pausen neu rechnen“: fehlt (nur in „Meine Zeiten“); für andere Personen nur der Admin über die Schnittstelle. „Meine Zeiten“ sagt seit 1.9.87
  „Auftrag abgeschlossen – das Büro rechnet neu“ -- das Büro kann es nicht.
- Abgeschlossene Aufträge: die Auswahl kommt aus `time_tracking_context()`, der nur offene Aufträge führt -- eine neue Buchung auf einen
  abgeschlossenen oder stornierten Auftrag geht in der Oberfläche gar nicht, auch nicht für den Admin; Ändern behält ihn (nachgeladen,
  gekennzeichnet). Die Meldung seit 1.9.81 „Zeiten dafür trägt das Büro ein“ läuft damit ins Leere; für eine andere Person bucht ohnehin nur der
  Admin.
- Monatsabschluss bei laufender Zeit: kein Hinweis; nach dem Abschluss schließt eine solche Zeit nur der Admin (Monteurin: „Monat abgeschlossen –
  das Büro schließt die Zeit“, das Büro scheitert an `_require_open_period()`).
- Büro ändert die Stunden mit Von/Bis (vorgemerkt): das Formular kennt nur Stunden und Pause; eine Buchung mit Von/Bis behält beim Ändern der
  Stunden ihre alten Uhrzeiten (der Stundenzettel zeigt dann Von/Bis, die nicht zu den Stunden passen), die Pausenregel gilt nicht.
- Zeitarten-Farben: `--travel-btn`, `--workshop-btn`, `--other-btn` als feste Werte (#3d6a8c, #7a5a34, #5c6660) ohne Dunkelvariante und ohne
  `--ds-*`-Token.
- Emojis und Zeichen als Symbole: 👥, 📅, ▶, ■ -- auf „Heute“ SVG.
- Weiter: eigenes `api()` ohne `fehlerText()` (eine 422 erscheint als „[object Object]“); `alert()` bei Fehlern (Stoppen, Gruppe ohne Kolonne); die
  Kolonne nur als Dauer (die Monteurin seit 1.9.63 mit Von/Bis); Zeitart-Knöpfe statt der Kacheln von „Heute“.

#### Zeiterfassungs-Backoffice (`/time-backoffice`)

Zweck: Kontrolle, Monatsauswertung, Stundenzettel, Abschluss und Lohnexport. Rollen: ab Büro – Auftrag (`require_min_role(buero_auftrag)`, Seite
und Schnittstellen); nur der Admin ändert und löscht fremde Buchungen und jede im abgeschlossenen Zeitraum, entscheidet Anträge, öffnet einen
abgeschlossenen Zeitraum wieder. Ohne verknüpften Mitarbeiter liest ein Büro-Konto den Buchungskontext nicht.

Funktionen:
- Filter „von“, „bis“, „Mitarbeiter“, „Aktualisieren“ (für Dashboard und Exporte).
- „Dashboard“: Kacheln Buchungen, Mitarbeiter, Produktiv, Fahrzeit, Gesamt; „Stunden je Mitarbeiter“ (Tage, Produktiv, Fahrt, Gesamt); offene
  Abwesenheitsanträge.
- „Buchungen“: immer der laufende Kalendermonat, unabhängig vom Filter; Tabelle Datum, Mitarbeiter (gebucht von), Projekt / Auftrag, LV, Zeitart,
  Tätigkeit, Pause, Stunden; „Bearbeiten“ und „Löschen“ (Büro nur eigene, offene), sonst „nur Admin“; Link „+ Buchung über Zeiterfassung“.
- „Zeitbuchung bearbeiten“: Projekt, Auftrag (ein geschlossener nachgeladen und gekennzeichnet), LV-Position, Datum, Stunden, Zeitart,
  Tätigkeit, Notiz -- keine Pause, kein Von/Bis.
- „Abwesenheiten“: Anträge, Genehmigen/Ablehnen (Admin), dem Büro nur die eigenen.
- „Stundenzettel“: „Stundenzettel PDF“, „Stundendaten CSV“ für Zeitraum und Mitarbeiter.
- „DATEV / Lohn“: „Abgeschlossen bis einschließlich“ mit „Abschließen“ (vorrücken das Büro, zurück nur der Admin) und „Abschluss aufheben“
  (Admin); „DATEV-Lohndaten exportieren“ mit Stand (Ziel, Personalnummern, gepflegte Lohnarten).
- „Einrichtung“: Links zu Zeitregeln und DATEV sowie zu den Zeit-Listen in den Einstellungen.

Was dort aus Stufe 4 fehlt oder nicht passt:
- Offene Zeiten von früher: keine Liste; eine laufende Zeit steht in „Buchungen“ als gewöhnliche Zeile mit 0,00 h ohne „läuft“ und zählt bei
  „Buchungen“ mit.
- „Pausen neu rechnen“: fehlt; ob die Pause eines Tags noch passt, zeigt das Backoffice nicht.
- Abgeschlossene Aufträge: Bearbeiten behält und kennzeichnet sie; anlegen nur über die Zeiterfassung -- dort nicht wählbar (oben).
- Monatsabschluss bei laufender Zeit: „Abschließen“ prüft keine laufenden oder seit früher offenen Zeiten bis zum Datum; danach schließt sie nur
  der Admin; der DATEV-Export enthält sie mit 0 h.
- Von/Bis: „Bearbeiten“ nur mit Stunden (wie oben); die Spalte „Zeitart“ zeigt den rohen Wert („site“, „weather_winter“), nicht die Bezeichnung.
- Rollen: Stundenzettel aller Mitarbeiter und DATEV-Lohnexport schon ab Büro – Auftrag -- zu entscheiden, ob der Lohnexport zu den
  Finanzbereichen gehört (Büro – Auftrag ist „der fachliche Kern ohne die vier Finanzbereiche“).
- Farben und Symbole: keine Emojis; die Untermenü-Knöpfe und die Monatsmarke („month-banner“ in `--accent`) mit eigenen Farben.
- Weiter: eigenes `api()` ohne `fehlerText()`; „Buchungen“ unabhängig vom Filter oben (steht als Hinweis da, ist aber eine Falle).

#### DATEV-Export (`app/time_backoffice.py::build_datev_export()`)

- Stunden je Lohnart: jede Buchung des Zeitraums (auch laufende, mit 0 h) bekommt die Lohnart ihrer Zeitart aus den Einstellungen (Baustelle,
  Fahrzeit, Werkstatt, Sonstige, Schlechtwetter Winter, Schlechtwetter Sommer); eine andere Zeitart nimmt „Sonstige“. Summiert je Mitarbeiter,
  Kalendertag, Zeitart und Lohnart; vorher je Buchung `rounded_hours()` mit der Rundung der Zeitregeln -- Buchungen seit 1.9.39 sind beim Buchen
  schon gerundet (zweimal gerundet, gleich, solange die Rundung gleich bleibt; ändert sie sich, weicht DATEV vom Stundenzettel ab), Buchungen vor
  1.9.39 rundet nur der Export (auch dann weicht er ab).
- Ausgabe: „Lohn und Gehalt“ als CSV (Personalnummer, Name, Kalendertag, Stundenanzahl, Lohnart, Zeitart) je Tag; „LODAS“ als `[Bewegungsdaten]`,
  Tabelle 3 je Tag und Lohnart, Buchungszeitraum immer der Monatserste.
- Pause: geht nur über die gebuchten Stunden ein (netto, `hours`), keine eigene Zeile. Entstanden ist sie beim Buchen: seit 1.9.48 je Tag
  (Pflichtpause aus der Anwesenheit des Tags, auf die neue Buchung), gespeichert je Buchung; der Export summiert je Tag -- die Tagespause stimmt,
  solange die Buchungen stimmen („Pausen neu rechnen“ nur auf Klick, nur die Monteurin selbst oder der Admin).
- Schlechtwetter: eigene Lohnarten ohne Rückfall auf „Sonstige“ (Saison-Kurzarbeitergeld bzw. Ausfallgeld); fehlt die Lohnart, fällt die Zeit
  mit Warnung aus dem Export.
- Fahrzeit: eigene Lohnart, fehlt sie, still „Sonstige“; sonst keine Sonderbehandlung (nur die Kacheln zählen sie nicht als produktiv).
- Warnungen (Personalnummer fehlt, Lohnart fehlt) stehen nur als Anzahl in der Kopfzeile `X-DATEV-Warnings` -- die Seite lädt den Export über
  `location.href`, niemand sieht sie; die betroffenen Stunden fehlen still.
- Abwesenheiten (Urlaub, Krankheit) gehen nicht in den Export; der Export prüft den Abschluss nicht (jeder Zeitraum, auch ein offener).

#### Stundenzettel im Büro und bei der Monteurin

- Monteurin („Meine Zeiten“ -> „Stundenzettel als PDF“, `app/field_timesheet_pdf.py`): ein Monat, Briefkopf über den gemeinsamen Rahmen
  (`render_framed_pdf()`, DIN 5008), Spalten Datum, Auftrag, Zeitart, Tätigkeit, Stunden, je Tag „Tagessumme“ aus `tagessumme()` (nur gebuchte
  Zeiten), „Monatssumme“ = Summe der Tagessummen; höchstens 2000 Buchungen je Monat.
- Büro (Backoffice, `build_timesheet_pdf()`): beliebiger Zeitraum, je Mitarbeiter eine Seite, Querformat, eigener Aufbau ohne Briefkopf-Rahmen,
  Spalten mit Von, Bis und Pause, „Summe“ über alle Zeilen, keine Tagessummen, Unterschriftszeilen; nicht `tagessumme()`.
- Dieselbe Rechnung? Im Ergebnis ja: beide summieren die gebuchten Stunden (`hours`), eine laufende Zeit hat 0 h (`tagessumme()` lässt sie aus,
  das Büro zählt 0), gerundet wird erst die Summe. Verschieden sind Darstellung (Tagessummen, Von/Bis/Pause, Rahmen, Zeitraum), die Grenze von
  2000 Buchungen und die Bezeichnung der Zeitart (Büro mit Rückfall auf die eingebauten Namen, Monteurin ohne). Der DATEV-Export rechnet anders
  (Rundung je Buchung, oben).

Bilder (1440 × 900, hell, ganze Seite, Testdaten der Bildgrundlage, Büro – Finanzen): 1 Zeiterfassung, 2–6 Backoffice (Dashboard, Buchungen,
Abwesenheiten, Stundenzettel, DATEV / Lohn), 7 „/mobil“ als Büro, 8 „Meine Zeiten“ als Büro -- im Bericht `bericht_stufe4_r5_8b68dda`.
Nichts davon ist gebaut; Vorschläge und Entscheidungen bleiben Tobias.

## Stufe 4, R5a (ab 1.9.89): Büro -- Regeln auf dem Server (Fundament für „Zeiten“)

Vorgabe 26.10.2026: Festlegungen R5 Teil 1 bestätigt; Tobias hat den Entwurf der Büroseite freigegeben (`bildgrundlage/entwurf-stufe4/zeiten-*.html`,
gebaut in R5b). Entscheidungen: das Büro erfasst keine eigene Zeit; Zeiten anderer und Lohndaten haben Admin und Büro – Finanzen; der
DATEV-Export geht nur für abgeschlossene Zeiträume. R5a baut die Regeln auf dem Server, eine Version je Punkt.

### R5a, Punkt 1 (1.9.89): Rechte

Je Recht eine Regel in `app/permissions.py` (`darf_zeit_fuer_andere_buchen()`, `darf_zeit_buchen()`, `darf_lohndaten()`), die alten Seiten blenden
aus, was der Server ablehnt. Herleitung, Tabelle der Rechte, Festlegungen 1.9.89 (8), angepasste Erwartungen und Gegenproben:
`docs/archiv/rechtekonzept.md`, „Nachtrag 1.9.89“.

### R5a, Punkte 2 und 3 (1.9.90): abgeschlossene Aufträge, Von/Bis, Dauer ohne Uhrzeiten

- Punkt 2: wer für andere bucht, bucht und ändert auch auf abgeschlossenen und stornierten Aufträgen -- der Server ließ das Büro schon seit 1.9.81
  dort buchen (`_require_order_open_for_field()` sperrt nur die Monteurin); neu bietet der Kontext sie an (`time_tracking_context(…,
  mit_geschlossenen=True)`, nach den offenen, `geschlossen`/`status`), und jede Buchung trägt `auftrag_geschlossen` (das Kennzeichen in Listen).
  Büro – Auftrag (bucht nicht) bekommt weiter nur offene.
- Punkt 3: Nachtrag und Ändern mit Von/Bis rechneten schon für jede Rolle über `nachtrag_nach_zeitregel()` bzw. `update_entry(von=…)`, die
  Vorschau nimmt seit 1.9.89 für Büro – Finanzen jede Person -- belegt im Test. Neu `app/routers/time_tracking.py::_als_dauer()`: ohne Von/Bis
  Stunden oder Pause gesendet oder einen anderen Tag -> `update_entry(…, als_dauer=True)` bzw. `update_group(…, als_dauer=True)` leeren Beginn
  und Ende.
- Befund dabei: `update_group()` ohne Von/Bis setzte jedem Mitglied immer Stunden und Pause des Kopfs -- nach einem Kolonnen-Nachtrag mit Von/Bis
  das Mittel (der Kopf hält seit 1.9.63 das Mittel und die größte Pause). Jetzt nur bei einer Dauer.

#### Festlegungen 1.9.90 (Bitte bestätigen)

1. „Als Dauer gespeichert“ heißt: ohne Von/Bis Stunden oder Pause gesendet oder ein anderer Tag -- dann sind Beginn und Ende leer; Auftrag,
   LV-Position, Zeitart, Tätigkeit, Notiz allein lassen sie stehen.
2. Die Monteurin (und der Kolonnenführer) ändert Stunden, Pause oder Tag nur mit Von/Bis -- 422 auch für Pause oder Tag allein (bis 1.9.89 nur für
   die Stunden); „Meine Zeiten“ schickt immer Von und Bis.
3. Eine Kolonnenbuchung ohne Von/Bis und ohne Dauer behält Stunden, Pause und Zeiten jedes Mitglieds (Behebung des Befunds); mit Dauer bekommen alle
   nicht einzeln geänderten Mitglieder Stunden und Pause der Kolonne ohne Uhrzeiten.
4. Die geschlossenen Aufträge bekommt im Kontext nur, wer für andere bucht (nach den offenen); Büro – Auftrag nicht.

#### Tests und Prüfung

Neu `tests/test_v511_buero_von_bis_und_geschlossen.py`: Monteurin auf dem geschlossenen Auftrag 403 / Büro – Finanzen bucht dort als Dauer und mit
Von/Bis, ändert, löscht (je abgeschlossen und storniert), Buchung gekennzeichnet; Kontext für Büro – Finanzen mit dem geschlossenen Auftrag hinter
dem offenen, für Büro – Auftrag ohne; Liste mit Kennzeichen; Nachtrag mit Von/Bis für Tom: 45 min aus dem Tag, Vorschau = Buchung; Dauer netto ohne
Uhrzeiten; Ändern mit Von/Bis; als Dauer gespeichert (Stunden, Pause, Tag) leert Beginn und Ende / Notiz, Tätigkeit, Zeitart, Auftrag lassen sie
stehen; Kolonne nur Notiz behält Mia 3,50 h und Tom 4,25 h; Kolonne als Dauer ohne Uhrzeiten auch am Kopf; Monteurin Pause oder Tag ohne Von/Bis 422.

Angepasste Erwartungen:
- `test_v334::test_backoffice_korrektur_behaelt_den_abgeschlossenen_auftrag`: der Kontext (Admin) liefert nur den offenen Auftrag -> den
  offenen und danach den abgeschlossenen, gekennzeichnet; der Dialog zeigt ihn weiter „(abgeschlossen)“.
- `klicktest_einsatzbericht_zeiten`, „Entwurf nachher“: Mias als Dauer gespeicherte Buchung „Mia Monteurin · 06:45–12:00“, 6,50 h -> „Mia
  Monteurin“, 6,50 h (ohne die stehen gebliebenen Uhrzeiten; rot im ersten Lauf vor dem Commit, die alte Erwartung).

Gegenproben (Marker `GEGENPROBE`, byte-genau zurück, je FAILED): Dauer leert Beginn und Ende nicht -> 3 Tests rot; Kolonne ohne Dauer setzt
die Stunden des Kopfs (der Stand bis 1.9.89) -> der Test „nur Notiz“ rot (der Befund); Kontext ohne geschlossene -> 2 Tests rot; Monteurin nur
bei Stunden 422 -> 2 Tests rot; ein anderer Tag zählt nicht als Dauer -> 2 Tests rot; Buchung ohne `auftrag_geschlossen` -> 3 Tests rot;
Backoffice ohne Kennzeichen für `geschlossen` -> 1 Test und 1 Prüfung von `klicktest_auswahl_restfaelle` rot.

### R5a, Punkt 4 (1.9.91): Abschließen sperren

`PUT /api/time-backoffice/lock` beim Vorrücken (neues Datum nach dem bisherigen oder erster Abschluss): `abschluss_hindernisse(db, bis)` --
laufende Zeiten mit `work_date <= bis` und Tage (Mitarbeiter × Tag mit gebuchten Zeiten) mit `pausen_vorschau()["passt"] == False` ab dem Tag nach
dem bisherigen Abschluss; nicht leer -> 409 `{"detail": "Abschließen geht noch nicht: …", "liste": [{art, employee_id, name, tag, entry_id, text}]}`
(Muster der Unterschrift im Einsatzbericht, `noch offen`). Zurücknehmen und Aufheben (nur Admin) prüfen nichts.

#### Festlegungen 1.9.91 (Bitte bestätigen)

1. Die Pausen prüft der Abschluss ab dem Tag nach dem bisherigen Abschluss; ohne bisherigen Abschluss nur im Monat des Datums (ältere Tage können
   aus der Zeit vor der Pausenregel je Tag stammen und sperrten den ersten Abschluss sonst dauerhaft).
2. Laufende Zeiten sperren unabhängig vom bisherigen Abschluss -- jede mit Tag bis zum Datum.
3. Die Sperre gilt auch für den Admin (er schließt wie das Büro erst nach dem Klären ab); Zurücknehmen und Aufheben prüfen nichts.
4. Die Ablehnung kommt als 409 mit `detail` (lesbarer Text, die alte Seite zeigt ihn) und `liste` (für die Seite „Zeiten“ in R5b).

#### Tests und Prüfung

Neu `tests/test_v512_abschluss_pruefen.py`: laufende Zeit seit gestern -> 409 mit Liste, nichts gespeichert, auch für den Admin / nach „Ende
nachtragen“ 200; heute laufende Zeit sperrt nur einen Abschluss bis heute; unpassende Pause -> 409 mit dem Tag / nach „Pausen neu rechnen“ 200;
beides in einer Liste; Personalnummer, Lohnart, DATEV-Nummern sperren nicht; nur ab dem bisherigen Abschluss; ohne bisherigen Abschluss der Monat;
Zurücknehmen ungeprüft.

Angepasste Erwartungen: keine.

Gegenproben (Marker `GEGENPROBE`, byte-genau zurück, je FAILED): laufende Zeiten nicht gesucht -> 4 Tests rot; Pausen nicht geprüft -> 4
Tests rot; das Vorrücken prüft nichts -> 7 Tests rot; Pausen über die ganze Zeit statt ab dem bisherigen Abschluss -> 2 Tests rot.

### R5a, Punkt 5 (1.9.92): DATEV-Export

- Zeitraum: `build_datev_export()` nur mit `end_date <= locked_until`, sonst `DatevExportGesperrt` -> 409 („Der DATEV-Export geht nur für
  abgeschlossene Zeiträume – abgeschlossen ist bis …“ bzw. „– noch ist nichts abgeschlossen“), Liste leer.
- Vollständig: `datev_fehlt()` -- je Mitarbeiter mit Lohnexport und Buchungen die Personalnummer, je gebuchter Zeitart die Lohnart
  (`_wage_type()`), Berater- und Mandantennummer; nicht leer -> 409 `{"detail": "Kein DATEV-Export: …", "liste": [{art, …, text}]}`, keine Datei.
- Stunden: die gespeicherten, über `tagessumme()` (jetzt in `app/time_tracking.py`, `app/meine_zeiten.py` importiert sie) -- auch
  `backoffice_summary()` (Kacheln, Stunden je Mitarbeiter) und der Stundenzettel des Büros; `rounded_hours()` rechnet der Export nicht mehr.
- Berater- und Mandantennummer: `TimeTrackingSettings.datev_beraternummer` (String 7) und `datev_mandantennummer` (String 5), Migration `750d709a4863`;
  `PUT /api/time-backoffice/datev-nummern` nur Admin, Schema `DatevNummernUpdate` (beide Pflicht, leer = nicht eingetragen); das allgemeine
  Formular der Zeitregeln (jedes Büro) lässt sie stehen; Einstellungen → Zeitregeln und DATEV zeigt sie jedem Büro, speichern nur der Admin.
- Format im Bericht: Beraternummer 4 bis 7 Ziffern, mindestens 1001; Mandantennummer 1 bis 5 Ziffern, mindestens 1 (die Bereiche des
  DATEV-Datenkopfs, 1001–9999999 bzw. 1–99999).
- LODAS: Kopf `[Allgemein]` (Ziel=LODAS, Version_SST=1.0, BeraterNr, MandantenNr, Datumsformat TT/MM/JJJJ, Feldtrennzeichen ;, Zahlenkomma ,),
  `[Satzbeschreibung]` `3;u_lod_bwd_buchung_standard;abrechnung_zeitraum#bwd;bs_wert_butab#bwd;bs_nr#bwd;la_eigene#bwd;pnr#bwd;`, dann
  `[Bewegungsdaten]` -- je Personalnummer, Monat und Lohnart eine Zeile (der Satz trägt nur den Abrechnungsmonat). Bestätigt ist der Kopf mit
  BeraterNr/MandantenNr aus Importdateien anderer Anbieter (DATEV-Community); die Felder des Satzes stehen in der Schnittstellenbeschreibung von
  LODAS (Hilfe-Dokument 1080789, `LODAS_SSH.pdf`) -- mit der Steuerkanzlei an einer Probedatei prüfen.
- Lohn und Gehalt: die CSV (Personalnummer, Name, Kalendertag, Stundenanzahl, Lohnart, Zeitart) hat keinen Platz für die beiden Nummern, und ein
  Vorlaufsatz mit ihnen ist nicht bestätigt -- importiert wird in den geöffneten Mandanten. Offen: mit der Steuerkanzlei klären, ob ihr Import
  einen Kopf erwartet.

#### Festlegungen 1.9.92 (Bitte bestätigen)

1. Jede Zeitart mit eigener Einstellung braucht ihre Lohnart -- auch Baustelle, Fahrzeit und Werkstatt fallen nicht mehr still auf „Sonstige“;
   nur eine Zeitart ohne eigene Einstellung (aus der Liste der Zeitarten) nimmt die Lohnart „Sonstige“.
2. Ohne Berater- und Mandantennummer kein Export -- für beide Zielsysteme, auch Lohn und Gehalt (dessen Datei sie nicht trägt).
3. Format: Beraternummer 4 bis 7 Ziffern ab 1001, Mandantennummer 1 bis 5 Ziffern ab 1; leer ist erlaubt (= nicht eingetragen).
4. LODAS bekommt je Personalnummer, Monat und Lohnart eine Zeile (bis 1.9.91 je Tag und Zeitart, alle mit demselben Monat).
5. Die Übersicht zählt wie Stundenzettel und DATEV nur gebuchte Zeiten (eine laufende nicht mehr mit; sie hat ohnehin keine Stunden).
6. Ohne Lohnexport (am Mitarbeiter ausgeschaltet) braucht es keine Personalnummer; seine Stunden gehen nicht in die Datei.
7. Die Nummern sieht jedes Büro in den Zeitregeln (nur lesbar), speichern kann nur der Admin; ein eigener Endpunkt, nicht das allgemeine Formular.
8. `X-DATEV-Warnings` entfällt -- was fehlt, steht in der 409.

#### Tests und Prüfung

Neu `tests/test_v513_datev_export.py`: offener Zeitraum 409 / abgeschlossen Datei ohne Warnkopf; DATEV-Summe je Mitarbeiter = Stundenzettel =
Übersicht (9,92 / 8,08 h, keine zweite Rundung); laufende Zeit in keiner Summe; fehlende Lohnart 409 auch mit „Sonstige“; fehlende
Personalnummer 409; ohne Lohnexport keine nötig; fehlende Berater-/Mandantennummer 409 (drei Fälle); alles Fehlende in einer Liste; LODAS-Datei
Zeile für Zeile; Nummern nur Admin; falsches Format 422 (sieben Fälle); speichern und leeren, beide Pflicht; das Formular der Zeitregeln lässt sie
stehen. `tests/test_v514_datev_nummern_migration.py`: Migration `750d709a4863` auf einem Bestand (SQLite und PostgreSQL-Wegwerf-Schema), Rückweg
verweigert mit eingetragener Nummer.

Angepasste Erwartungen:
- `test_v103::test_backoffice_summary_pdf_csv_and_datev_export`: Export ohne Abschluss, drei Rückgabewerte, keine Warnungen -> mit Abschluss
  und Berater-/Mandantennummer, zwei Rückgabewerte (nur Aufbau).
- `test_v311::test_datev_export_contains_all_2001_hours`: ebenso (nur Aufbau; die Summe 2001 h bleibt).
- `test_v387::test_die_lesewege_legen_nichts_an_und_zeigen_die_vorgaben`: alle Lesewege 200 -> der DATEV-Export 409 (abgeschlossen bis
  31.12.2026, Liste „datev_nummern“), weiter nichts angelegt.
- `test_v387::test_pg_gleichzeitige_lesewege_ohne_fehler_und_ohne_schreiben`: alle 200 -> der DATEV-Export 409, die übrigen 200, nichts
  geschrieben.
- `test_v422::test_jede_anfrage_der_seite_ist_dem_buero_erlaubt[buero_finanzen]`: DATEV 200 -> 409 (der laufende Monat ist offen).
- `test_v510::test_lohndaten_nur_admin_und_finanzen[admin, buero_finanzen]`: DATEV 200 -> 409 mit „nur für abgeschlossene Zeiträume“.
- `klicktest_backoffice_buero`: Fin, Exporte [200, 200, 200] -> [200, 200, 409].
- `test_v315::test_datev_export_hours_half_hundredth_round_up` und `test_v104::test_datev_can_use_erp_employee_number`: Export ohne Abschluss,
  drei Rückgabewerte, keine Warnungen -> mit Abschluss und Berater-/Mandantennummer, zwei Rückgabewerte (nur Aufbau; 1,13 bzw. „MA-0042“
  bleiben).
- `test_v466::test_waechter_eine_rundung`: die Rundung der Zeitregeln in `gebucht_nach_zeitregel()` und im DATEV-Export -> nur noch in
  `gebucht_nach_zeitregel()` (keine zweite Rundung im Export).
- `test_v436::test_jedes_protokollierte_feld_hat_einen_namen` und `test_v438::test_namen_der_historie_sind_lesbar` blieben, wie sie sind: die
  beiden neuen Spalten bekamen ihre Namen im Änderungsverlauf (`app/audit.py`: „DATEV-Beraternummer“, „DATEV-Mandantennummer“) -- im ersten
  Lauf rot, weil sie fehlten.

Gegenproben: (Marker `GEGENPROBE`, byte-genau zurück, je FAILED) Export auch offen -> 1 Test rot; zweite Rundung im Export -> der Summentest rot;
Rückfall auf „Sonstige“ für Baustelle/Fahrzeit/Werkstatt -> 3 Tests rot; Fehlendes nicht geprüft -> 6 Tests rot; LODAS ohne Kopf -> 1 Test
rot; Nummern für jedes Büro -> 1 Test und 1 Prüfung von `klicktest_datev_nummern` rot; Beraternummer ungeprüft -> 4 Tests und 2 Prüfungen rot;
Felder für das Büro bearbeitbar -> 1 Prüfung rot. Neuer Klicktest `klicktest_datev_nummern` (13 Prüfungen).

### R5a, Punkt 6 (1.9.93): Kleinigkeiten

- Einsatzkarte auf „Heute“: `einsaetze()` liefert `title`, die Karte zeigt unter dem Objekt `<p class="einsatz-auftrag">` mit
  `auftragTitel(k)` („AUF-2026-0001 · Wartung“), dann Kunde · Adresse.
- Büro auf `/mobil`: `NUR_MONTEURSANSICHT` = „„Heute“ gibt es nur in der Monteursansicht.“ (403 von `GET /api/field-view/today` für jede Rolle
  außerhalb der Monteursansicht; bis 1.9.92 „Die Einsätze gibt es nur in der Monteursansicht.“).
- „Meine Zeiten“ als Büro: `GET /api/field-view/meine-zeiten` trägt `buero` (nicht in den Rollen der Monteursansicht) -- die Seite zeigt dann nicht
  „… wende dich an das Büro.“; `nachtragen_erlaubt` zusätzlich nach `darf_zeit_buchen()` (Büro – Auftrag ohne „+ Nachtragen“ und „⋮“).
- CLAUDE.md: die Zeile „(Einsätze, Zeiterfassung der Monteure, Stundenzettel -> 4 …)“ heißt jetzt „(„Heute“ und „Meine Zeiten“ -> 4 -- „Meine
  Zeiten“ ersetzt seit 1.9.59 Zeiterfassung der Monteure und Stundenzettel …)“, wie `AUFGESCHOBEN` in `tests/test_v441_rahmen_baustein.py`.

#### Festlegungen 1.9.93 (Bitte bestätigen)

1. „Nummer · Titel“ steht als eigene Zeile unter dem Objekt der Einsatzkarte (vor Kunde · Adresse), aus `auftragTitel()` wie im Dialog „Für
   welchen Auftrag?“.
2. „buero“ heißt: nicht in den Rollen der Monteursansicht (`hat_monteursansicht()`) -- auch der Admin bekommt die rote Zeile nicht.
3. „Meine Zeiten“ bietet Nachtragen und Ändern nur, wer Zeiten bucht: Büro – Auftrag nicht, Büro – Finanzen (mit Mitarbeiter) weiter (der Server
   erlaubt ihm die eigene Zeit, Festlegung 1.9.89 Nr. 2).

#### Tests und Prüfung

Neu `tests/test_v515_kleinigkeiten_buero.py`: Einsatz mit Titel; Karte über `auftragTitel(k)`; Büro auf `/mobil` 403 mit dem neuen Text;
`buero` und `nachtragen_erlaubt` je Rolle (Monteurin, Büro – Auftrag, Büro – Finanzen, Admin); die rote Zeile nicht fürs Büro.

Angepasste Erwartungen:
- `klicktest_heute`, „Einsatz: eine Karte für A …“: [Zeitraum, Objekt, Kunde · Adresse, Route] -> [Zeitraum, Objekt, „AUF-2026-0001 · Wartung“,
  Kunde · Adresse, Route].

Gegenproben (Marker `GEGENPROBE`, byte-genau zurück, je FAILED): Einsatz ohne Titel -> 1 Test und 1 Prüfung von `klicktest_heute` rot; Karte
ohne die Zeile -> 1 Test und 2 Prüfungen rot; `buero` immer falsch -> 3 Tests rot; Nachtragen für jedes Büro -> 1 Test rot.

## Stufe 4, R5b (ab 1.9.94): Büro -- die Seite „Zeiten“

Vorgabe 26.10.2026: Festlegungen R5a alle bestätigt. Vorlage (von Tobias freigegeben): `bildgrundlage/entwurf-stufe4/zeiten-pruefen.html`,
`zeiten-buchungen.html`, `zeiten-aendern.html`, `zeiten-monat.html` -- Maße und Texte gelten, Farben über Tokens, hell und dunkel, Seitenkopf über
den Baustein. Eine Seite „Zeiten“ ersetzt Zeiterfassung (Büro) und Backoffice.

### R5b, Punkt 0 (1.9.94): Vorweg

- Bildgrundlage vom Stand `d54f7e4` (vor dem Umbau): `bildgrundlage/d54f7e4/`, 314 Bilder, 338 von 338 Prüfungen wie erwartet -- die Grundlage für
  den Vergleich nach der Umstellung.
- `scripts/pruefabfrage_kolonne_mittel.sql` (nur lesen): Kolonnenbuchungen seit dem 23.10.2026, deren Mitglieder durch ein Ändern ohne Von/Bis
  dieselben Stunden bekamen (Fehler bis 1.9.89, siehe R5a Punkte 2 und 3, „Befund dabei“). Erkannt im Änderungsverlauf (`audit_logs`): Änderung der
  Stunden (`hours`) einer Zeitbuchung über `PUT /api/time-entry-groups/{id}`, je Gruppe und Anfrage (Pfad und Minute) mindestens zwei Mitglieder,
  nachher eine Zahl, vorher mehrere, und keine Änderung der Stunden des Kopfs („Gruppen-Zeitbuchung“) in derselben Anfrage. Ergebnis je Mitglied:
  Gruppe, Tag, Auftrag (Nummer · Titel), Mitarbeiter, Stunden vorher/nachher, geändert am (Europe/Berlin), geändert von.

#### Festlegungen 1.9.94 (Bitte bestätigen)

1. „Seit dem 23.10.2026“ heißt ab 00:00 Uhr Europe/Berlin (22.10.2026 22:00 UTC, der Verlauf speichert UTC).
2. Eine Anfrage = derselbe Pfad in derselben Minute (der Verlauf trägt keine Kennung der Anfrage).
3. Eine bewusst eingetragene Dauer ändert die Stunden des Kopfs mit und erscheint nicht; eine Dauer, die genau die alten Stunden des Kopfs trifft,
   erschiene -- im Zweifel am Verlauf der Gruppe prüfen (steht im Kopf der Datei).
4. Aufruf auf dem Server mit `psql` und `PGOPTIONS='-c default_transaction_read_only=on'` (doppelt zum `BEGIN TRANSACTION READ ONLY`), die
   Verbindung aus `.env` ohne `+psycopg`.

#### Tests und Prüfung

Neu `tests/test_v516_pruefabfrage_kolonne_mittel.py`: nur lesende Anweisungen; unter PostgreSQL (Wegwerf-Schema) ein Bestand mit einer betroffenen
Gruppe (zwei Zeilen: 3,50 und 4,25 h -> 3,875 h) und vier, die nicht erscheinen (Dauer mit geändertem Kopf, Änderung am 22.10. um 23:59 Berlin,
nur ein Mitglied, vorher schon gleich). Gegenproben (Marker `GEGENPROBE`, byte-genau zurück, je FAILED): Dauer nicht ausgenommen, ohne Stichtag,
„vorher gleich“ zählt mit -> je der PostgreSQL-Test rot.

### R5b, Punkte 1–3 und 6, Server (1.9.95): die Daten der Seite

- `app/zeiten.py` (rollenlos) und `app/routers/zeiten.py` (Rechte je Zeile): `GET /api/zeiten/pruefen` und `GET /api/zeiten/buchungen` ab Büro –
  Auftrag (`require_min_role(buero_auftrag)`), `GET /api/zeiten/monat` mit den Lohndaten (`require_lohndaten`). Nur lesen; geschrieben wird über
  die bestehenden Endpunkte (Ende nachtragen und seine Vorschau, Pausen neu rechnen, Zeiten, Abschluss, Anträge), die ihre Rechte selbst prüfen.
- Je Zeile, was das Konto darf: `darf_schliessen` (Zeit von früher), `darf_buchen` (Pause des Tags), `darf_aendern` (Buchung) -- buchen darf das
  Konto (`darf_zeit_buchen()`), die Zeit ist die eigene oder es bucht für andere, im abgeschlossenen Zeitraum nur der Admin (dieselben Regeln wie
  `_time_entry_can_edit()` und `_require_open_period()`); dazu je Antwort `rechte` (zeit_buchen, zeit_fuer_andere, lohndaten,
  antraege_entscheiden, admin).
- Prüfen: `offene_zeiten()` (jede Zeit mit `laeuft_seit_frueher()`, älteste zuerst, Zeitart mit Namen, Auftrag Nummer · Titel, `gruppe` bei
  laufender Kolonne); `pausen_tage()` über `app/time_backoffice.py::unpassende_pausen()` (neu, eine Liste auch für `abschluss_hindernisse()`), je
  Buchung Zeitart, Von–Bis, Pause und gebucht alt -> neu -- genau das, was „So buchen“ an `POST /api/time-entries/pausen-neu-rechnen` schickt;
  Anträge wie `GET /api/absence-requests` mit Arbeitstagen; der Monat (`monat_stunden()`: Gebucht, Fahrzeit, je Mitarbeiter Tage und Stunden über
  `tagessumme()`); „Vor dem Abschluss“ (`vor_dem_abschluss()`); `zahlen` an den Reitern.
- Buchungen: `buchungen()` -- der Monat nach den Filtern (UND), je Zeile `entry_to_dict()` mit Zeitart, `vom_buero`, Kennzeichen des Auftrags,
  „Summe der Auswahl“ über `tagessumme()`, `laufend` (Zahl), Auswahl der Filter.
- Monat & Lohn: `monat()` -- Status (offen, teilweise, abgeschlossen), Lücken (`abschluss_hindernisse()` bis zum Monatsende, mit
  `luecken_text`: „2 laufende Zeiten, 1 Pause“), was DATEV fehlt (`datev_fehlt()`, mit `datev_text`: „1 Personalnummer, 1 Lohnart,
  DATEV-Nummern“), offene Anträge (Zahl), Tabelle je Mitarbeiter mit Personalnummer, Lohnexport, Tagen, Stunden je Spalte und zusammen.

#### Festlegungen 1.9.95 (Bitte bestätigen)

1. Der Monat rechts auf „Prüfen“ ist der erste noch nicht ganz abgeschlossene: der Monat nach „Abgeschlossen bis“, höchstens der von heute; ohne
   Abschluss der von heute.
2. „Pause passt nicht zum Tag“ prüft vom Tag nach „Abgeschlossen bis“ bis heute, ohne Abschluss ab dem Ersten des laufenden Monats -- dieselbe
   Grenze wie das Abschließen.
3. Die Zahl am Reiter „Prüfen“ = Zeiten von früher + Tage mit unpassender Pause; am Reiter „Abwesenheiten“ = offene Anträge, die das Konto sieht
   (wie die Vorlage: 3 und 1, die Anträge stehen auch auf „Prüfen“).
4. Anträge sieht das Büro wie bisher nur die eigenen, der Admin alle (`GET /api/absence-requests`) -- auch auf „Prüfen“.
5. „5 Arbeitstage“ am Antrag zählt Montag bis Freitag im Zeitraum, ohne Feiertage.
6. „Summe der Auswahl“ = die gebuchten Stunden genau der gefilterten Zeilen (`tagessumme()`); eine laufende Zeit steht in der Liste und zählt nicht
   mit, auch wenn sie Stunden trüge.
7. Auswahl der Filter: Mitarbeiter = jeder aktive und jeder, der im Monat gebucht hat; Aufträge = die des Monats und der gefilterte; Zeitarten =
   die Liste der Zeitarten und jede im Monat gebuchte.
8. „Stunden je Mitarbeiter“ auf „Monat & Lohn“: Spalten Baustelle, Fahrzeit, Werkstatt, Schlechtwetter (Winter und Sommer zusammen); „Sonstige“
   (die Zeitart „Sonstige“ und jede ohne eigene Spalte) nur, wenn dort Stunden stehen.
9. „Dauer · vom Büro“ heißt: ohne Uhrzeiten, gebucht von einem Konto außerhalb der Monteursansicht (`vom_buero`); ohne Uhrzeiten von der
   Monteurin oder dem Kolonnenführer nur „Dauer“.
10. „Vor dem Abschluss“ auf „Prüfen“ nennt die Lücken der Zeiten als Zahl („2 Zeiten laufen noch“, „1 Tag mit unpassender Pause“) und, was dem
    DATEV-Export des Monats fehlt, einzeln (wie die Vorlage).

#### Tests und Prüfung

Neu `tests/test_v517_zeiten_server.py` (19 Tests): wer was liest (Monteurin nichts, Büro – Auftrag nicht „Monat & Lohn“); Rechte und Knöpfe je Rolle
(Büro – Auftrag auch an der eigenen Zeit keine); im abgeschlossenen Zeitraum nur der Admin; Monat als JJJJ-MM; Zeiten von früher mit Ende eintragen
= Vorschau; Pause passt nicht mit Vorschau, „So buchen“ = Vorschau; Pausen erst nach dem Abschluss; Anträge je Konto; Monat und „Vor dem
Abschluss“ (dieselbe Summe wie die Übersicht); der erste offene Monat; Filter ändern Liste und Summe, laufende zählt nicht; Kennzeichen; Lücken und
DATEV getrennt; Tabelle = DATEV-Export (eine Rechnung), „Sonstige“ nur mit Stunden. Keine angepassten Erwartungen (`test_v512` unverändert grün
mit `unpassende_pausen()`).

Gegenproben (Marker `GEGENPROBE`, byte-genau zurück, je FAILED): „Monat & Lohn“ für Büro – Auftrag; Summe mit laufenden; Ändern ohne Abschluss;
Pausen ohne Abschlussgrenze; offene Zeiten auch von heute; Anträge aller für das Büro; Knöpfe für Büro – Auftrag (zuerst grün -- der Test prüfte
Büro – Auftrag nur ohne eigenen Mitarbeiter; nachgeschärft: das Konto ist Tom, Toms eigene laufende Zeit) -> je 1 Test rot.

### R5b, Punkte 2–4 und 7 (1.9.96): die Seite mit Prüfen und Buchungen

- Seite `/zeiten` (`app/routers/pages.py::zeiten_page()`, ab Büro – Auftrag; die Monteurin -> `/mobil/zeiten`), Vorlage `zeiten.html` in
  `UMGEZOGEN` (`tests/test_v441_rahmen_baustein.py`), in der Bildgrundlage (`scripts/bildgrundlage.py`, Büro 4 Bilder). Bis zur Umstellung
  (Punkt 1) markiert sie in der Leiste „Backoffice“ (`bereich`), die alten Seiten bleiben erreichbar.
- Kopf über das Makro: Titel, Untertitel, „+ Buchung“ (nur mit `darf_zeit_buchen()`, sonst fehlt der Knopf), „⋮“ mit „Zeitregeln und DATEV“ und
  „Zeit-Listen“. Darunter die Reiter (`nav.reiter`, 44 px, aktiver mit grünem Strich, Zahl in Signal), Adresse `#pruefen`/`#buchungen`.
- Prüfen: Karte „Wartet auf dich“ (Signalfläche) nur mit Zeiten von früher -- „Ende um“ fragt bei jeder Eingabe `GET
  /api/time-entries/{id}/ende-vorschau` (über `lesen()`), „Ende eintragen“ erst mit Vorschau, schickt genau dieses Ende an
  `…/ende-nachtragen`; „Pause passt nicht zum Tag“ zeigt die Vorschau vom Server sofort, „Abbrechen“ klappt sie zu („Neu rechnen“ öffnet
  wieder), „So buchen“ schickt sie an `pausen-neu-rechnen`; Anträge (Ablehnen/Genehmigen nur Admin, `POST …/review`); ohne alles „Nichts zu
  prüfen“. Rechts der Monat (Status offen/teilweise/abgeschlossen, Gebucht, Fahrzeit, Tabelle) und „Vor dem Abschluss“ (sonst ein Haken).
- Buchungen: Filterleiste wie die Vorlage (‹ Monat ›, Mitarbeiter 150 px, Auftrag 180 px, Zeitart 120 px, „Summe der Auswahl“), Auswahl über
  `auswahlOptionen()`; Tabelle Datum, Mitarbeiter, Von–Bis („06:45 – läuft“ mit „von früher“, „Dauer · vom Büro“ bzw. „Dauer“), Zeitart mit
  Farbpunkt, Auftrag (Nummer · Titel, Kennzeichen „abgeschlossen“), Pause (h:mm), Stunden; „Ende eintragen“ springt zu Prüfen und setzt den Fokus
  ins Feld; „⋮“ (`dsMenue()`) mit Ändern und Löschen nur mit `darf_aendern`.
- Dialog „Buchung ändern“ / „Neue Buchung“ (640 px, Ecke 16 px): Mitarbeiter (nur neu), Datum, Zeitart, Auftrag (aus dem Kontext der Zeiterfassung,
  geschlossene gekennzeichnet), Erfassung „Von – Bis | Dauer“, unter „Weitere Angaben“ LV-Position, Tätigkeit, Pause mindestens, Notiz. Von–Bis:
  Vorschau über `nachtrag-vorschau` (mit `employee_id`, beim Ändern `entry_id`), POST mit `break_minutes`, PUT mit `pause_minuten`; Dauer:
  Stunden (Pflicht) und Pause, ohne Von/Bis -- der Server leert Beginn und Ende (seit 1.9.90). Löschen über einen eigenen Dialog.
- Befund R5: `--ds-zeitart-baustelle/-fahrt/-werkstatt/-sonstige` in `ds.css` (hell aus der Vorlage, dunkel aufgehellt; vier Prüfpaare
  „zeitart-*/flaeche“ ≥ 3 : 1); keine Emojis, ▶ oder ■; `fehlerText()` mit den Feldnamen der Seite; Rückfragen auf der Seite, kein `confirm()`.
- Befund dabei: der Monat (rechts und „Stunden je Mitarbeiter“) zeigte eine Person mit nur einer laufenden Zeit als „0 Tage, 0,00“ -- jetzt
  nur Mitarbeiter mit gebuchten Zeiten (`app/zeiten.py`, Test `test_nur_laufende_zeit_ohne_zeile_im_monat`).

#### Festlegungen 1.9.96 (Bitte bestätigen)

1. Bis zur Umstellung (Punkt 1) markiert „Zeiten“ in der Leiste den Eintrag „Backoffice“; erreichbar über die Adresse `/zeiten`.
2. Im Seitenkopf steht „+ Buchung“ rechts, „⋮“ daneben -- die Reihenfolge des Makros (Hauptaktion, dann Menü); die Vorlage hat „⋮“ links.
3. „Abbrechen“ an „Pause passt nicht zum Tag“ klappt die Vorschau zu; „Neu rechnen“ öffnet sie wieder (nichts wird gebucht).
4. „Ende eintragen“ an einer laufenden Zeit in „Buchungen“ springt zu „Prüfen“ und setzt den Fokus in „Ende um“ dieser Zeit.
5. Eine laufende Zeit von heute zeigt „läuft“ ohne Kennzeichen und ohne Knopf (die Monteurin beendet sie).
6. Die Pause steht in der Liste als h:mm ohne „h“ (wie die Vorlage), die Stunden dezimal.
7. Der Dialog öffnet bei einer Buchung ohne Uhrzeiten „Dauer“, sonst „Von – Bis“; beim Ändern ist der Mitarbeiter fest.
8. „Weitere Angaben“ enthält zusätzlich die LV-Position (die Zeiterfassung und das Backoffice hatten sie, die Vorlage nennt sie nicht).
9. Ein Timer (Schnell starten, Gruppen-Timer) wird im Büro nicht angeboten -- die Monteurin startet auf „Heute“, das Büro bucht nachträglich.
10. Die Liste nennt den Auftrag mit „Nummer · Titel“ (`auftragTitel()`), wie die Vorlage.
11. Der Grund in „Pause passt nicht zum Tag“ („nach Löschen einer Buchung“) entfällt -- der Server kennt ihn nicht.
12. Nach jedem Speichern laden Prüfen und (wenn geladen) Buchungen neu; die Meldung steht unter den Reitern.

#### Tests und Prüfung

Neu `tests/test_v518_zeiten_seite.py` (14 Tests): Seite je Rolle (+ Buchung, Rechte), Monteurin -> „Meine Zeiten“; Buchungszeile mit Von–Bis und
„⋮“, ohne Recht ohne „⋮“, laufend von früher mit Weg, Dauer und abgeschlossener Auftrag, Werte in `esc()`; Pause passt nicht mit Vorschau und So
buchen (ohne Recht ohne Knöpfe); Zeit von früher mit „Ende um“ (ohne Recht ohne); Anträge nur Admin; Wechsel zu Dauer; Befund R5. Neu
`scripts/klicktest_zeiten.py` (50 Prüfungen): Admin Prüfen (Vorschau, Ende eintragen = Vorschau, So buchen = Vorschau), Büro – Finanzen Buchungen
(Zeilen, Filter und Summe, Ändern mit Vorschau, Wechsel zu Dauer mit leeren Uhrzeiten, neue Buchung, Löschen mit Rückfrage), Büro – Auftrag ohne
Knöpfe, hell/dunkel mit den Farbtokens, 412 px.

Angepasste Erwartungen:
- `test_v432::test_kontrast_der_pruefpaare_hell_und_dunkel`: 43 Prüfpaare -> 47 (die Farbpunkte der Zeitarten).
- `test_v441::test_jede_seite_mit_leiste_nennt_ihren_bereich` und `test_jede_seite_markiert_ihren_bereich`: 45 Seiten mit Leiste -> 46.
- `test_v431::test_dateinamen_eindeutig_und_die_bisherigen_zuerst`: 314 Bilder -> 318, davon in 412/1440 252 -> 256.
- `test_v401::test_jede_weiterleitung_des_servers_hat_ein_festes_oder_geprueftes_ziel`: 7 Weiterleitungen -> 8 (`/zeiten` der Monteurin).
- `test_v425::test_jede_umleitung_einer_seitenroute_steht_an_der_route`: fünf umleitende Seitenrouten -> sechs (`zeiten_page`, mit
  `dk_ohne_seite`); im ersten vollen Lauf rot.
- `test_v424`: `ABGLEICH` um die drei Zahlenfelder des Dialogs ergänzt (`bdPause`, `bdStunden`, `bdPauseDauer`); im ersten Lauf rot, weil die
  Stunden zwei Nachkommastellen verlangten (strenger als der Server) -- `data-stellen` entfernt.
- Im ersten Lauf rot und an der Seite behoben: `test_v398` (die Optionen mit `method` standen in einer Hilfsfunktion statt im Aufruf),
  `test_v407` (die Tage ohne `esc()`).

Gegenproben (Marker `GEGENPROBE`, byte-genau zurück, je FAILED): „+ Buchung“ für Büro – Auftrag; „Dauer“ leert Von/Bis nicht; „⋮“ ohne Recht;
„Ende um“ ohne Recht; Zeitart-Farbe ohne Token -> je 1 Test und 1 Prüfung von `klicktest_zeiten` rot.

### R5b, Punkte 5, 6 und 3 (1.9.97): Abwesenheiten, Monat & Lohn, Kolonne buchen

- Server: `GET /api/zeiten/abwesenheiten?status=` (ab Büro – Auftrag) -- Sichtbarkeit wie `GET /api/absence-requests` (Admin alle, sonst die
  eigenen, ohne Mitarbeiter keine), je Antrag Arbeitstage, `darf_entscheiden`, `darf_zurueckziehen`; dazu Hinweis, `darf_beantragen`,
  `fuer_andere`, Mitarbeiter (nur Admin), Arten (`absence_types`), offen. `app/routers/absence_requests.py::_antrag_fuer()`: ein Antrag für eine
  andere Person nur vom Admin (403 „Du darfst nur eigene Abwesenheiten beantragen.“), ohne Mitarbeiter 403 -- bis 1.9.96 über
  `_time_entry_employee_for_request()`, die seit 1.9.89 Büro – Finanzen für andere buchen lässt.
- Abwesenheiten: Filter Status (Offen, Alle, Genehmigt, Abgelehnt, Zurückgezogen), Zeile Name · Kategorie (Art), Zeitraum · Arbeitstage ·
  beantragt am, Notiz, Freigabe-Notiz, Status als Kennzeichen; Admin: Notiz, Ablehnen, Genehmigen; der eigene offene: Zurückziehen mit Rückfrage
  in der Zeile; Dialog „Abwesenheit beantragen“ (Mitarbeiter nur für den Admin, Kategorie, Art, Von, Bis, Notiz).
- Monat & Lohn (`{% if lohndaten %}` -- Reiter und Inhalt fehlen sonst, `GET /api/zeiten/monat` 403): Filterleiste mit Status und „Abgeschlossen
  bis“, Schritte 1–3 wie die Vorlage, Tabelle mit den Spalten vom Server (Name -> Stundenzettel dieser Person als PDF). Abschließen über
  `abschliessen()` (`ABSCHLIESSEND` in `tests/test_v399_abschliessen.py`), die Ablehnung (409) zeigt `liste` unter dem Knopf.
- Kopf „⋮“: „Kolonne buchen“ (nur wer bucht) -- Kolonne, alle aktiven Mitglieder angehakt, Datum, Zeitart, Auftrag, Von–Bis mit Vorschau je Person
  (`GET /api/time-entry-groups/nachtrag-vorschau`) oder Dauer je Person, LV-Position, Tätigkeit, Pause mindestens, Notiz; „Abschluss aufheben“
  (nur Admin) -- Dialog mit dem Stand und „Abgeschlossen bleibt bis“ (die zwölf Monatsenden davor oder „nichts“), `PUT /api/time-backoffice/lock`.
- Prüfen: „Zu „Monat & Lohn““ unter „Vor dem Abschluss“ (nur mit den Lohndaten); die Zahl am Reiter „Abwesenheiten“.

#### Festlegungen 1.9.97 (Bitte bestätigen)

1. „Abwesenheiten“ zeigt zuerst die offenen Anträge; „Alle“ und die übrigen Status über die Auswahl „Status“.
2. Entscheiden (mit optionaler Notiz in der Zeile) nur der Admin, wie bisher; das Büro sieht nur die eigenen Anträge, wie bisher.
3. Einen Antrag für eine andere Person stellt nur der Admin; das Büro für sich (mit Mitarbeiter), ohne Mitarbeiter kein „beantragen“.
4. Zurückziehen mit Rückfrage in der Zeile (wie „Meine Zeiten“), nur der eigene offene Antrag -- auch der Admin zieht die Anträge anderer
   nicht zurück, er entscheidet sie (der Server erlaubt ihm das Zurückziehen weiter, die Seite bietet es nicht an).
5. „Monat & Lohn“ öffnet den ersten noch offenen Monat (wie „Prüfen“ rechts).
6. Abgeschlossen wird monatsweise bis zum Monatsende („Oktober 2026 abschließen“); ein Abschluss mitten im Monat geht nicht mehr über die Seite.
7. „Abschluss aufheben“ (Admin, „⋮“) setzt „Abgeschlossen bis“ auf ein früheres Monatsende -- vorgeschlagen das vor dem jetzigen, wählbar die
   zwölf davor -- oder hebt ihn ganz auf; Rückfrage im Dialog.
8. Die Wege im Schritt „Prüfen“: „Prüfen“ (Reiter Prüfen), „Personal“ und „Zeitregeln“ (Einstellungen → Zeitregeln und DATEV, dort Personalnummern,
   Lohnarten, DATEV-Nummern), „Abwesenheiten“ (Reiter).
9. Personalnr.: „fehlt“, wenn der Lohnexport an ist und keine Nummer gilt; „ohne Export“ ohne Lohnexport.
10. Ein Name in „Stunden je Mitarbeiter“ öffnet den Stundenzettel dieser Person für den Monat als PDF.
11. „Kolonne buchen“ hakt alle aktiven Mitglieder an; Von–Bis mit Vorschau je Person (Pause und Rundung nach ihrem Tag), „Dauer“ gibt jeder Person
    dieselben Stunden (netto); der Knopf heißt „Für n Personen speichern“.
12. „Abschließen“ ist eine abschließende Aktion (wartet auf jedes Speichern der Seite) -- im Backoffice lief es bis 1.9.96 über `speichern()`.

#### Tests und Prüfung

Neu `tests/test_v519_zeiten_abwesenheiten_monat.py`: Abwesenheiten je Konto (Admin alle und entscheidet, Büro nur die eigenen, ohne Mitarbeiter
Hinweis), Status und Rechte, Antrag für andere nur der Admin (Angriff Büro – Finanzen 403); Reiter und Menü je Rolle; „Monat & Lohn“ in node:
„Fehlt“ nur die Lücken, DATEV getrennt, Abschließen gesperrt bzw. frei, DATEV erst abgeschlossen und vollständig, Tabelle mit Personalnummer,
Abschließen über `abschliessen()` mit Liste; Anträge mit Knöpfen nach dem Server. `scripts/klicktest_zeiten.py` um Kolonne, Abwesenheiten, Monat
& Lohn und „Abschluss aufheben“ erweitert (87 Prüfungen).

Angepasste Erwartungen: keine geänderte -- `test_v399` `ABSCHLIESSEND` um „Monat der Zeiterfassung abschließen“ ergänzt, `test_v424` `ABGLEICH` um die
drei Zahlenfelder von „Kolonne buchen“ ergänzt (im ersten Lauf rot, wie vorgesehen); `test_v517::test_monat_tabelle_eine_rechnung_mit_dem_datev_export`:
nur der Aufbau -- `datev_target` „lohn_gehalt“ statt des ungültigen „lohn_und_gehalt“ (der Export las ihn als „nicht LODAS“, das Ergebnis bleibt).
Im ersten Lauf rot und an der Seite behoben: `test_v407` (die Klasse des Status, der Weg im Schritt „Prüfen“ als fertiges HTML aus einer Variablen --
jetzt fest in der Seite, Text in `esc()`).

Gegenproben (Marker `GEGENPROBE`, byte-genau zurück, je FAILED): Antrag für andere erlaubt -> 1 Test; Reiter „Monat & Lohn“ für Büro – Auftrag ->
1 Test und 1 Prüfung von `klicktest_zeiten`; „Fehlt“ mit DATEV -> 1 Test und 1 Prüfung; DATEV-Link vor dem Abschluss -> 2 Tests und 2 Prüfungen;
Abschließen über `speichern()` -> 2 Tests; Entscheiden ohne Admin -> 1 Test.

### R5b, Punkt 1 (1.9.98): „Zeiten“ ersetzt Zeiterfassung und Backoffice

- Leiste: ein Eintrag „Zeiten“ (`data-bereich="zeiten"`, `/zeiten`, Symbol der Zeiterfassung) an der Stelle der Zeiterfassung, für jede Rolle
  sichtbar wie bisher die Zeiterfassung; „Backoffice“ entfällt. `zeiten.html` setzt `bereich = "zeiten"`.
- Entfernt: `time_tracking.html`, `time_backoffice.html` (auch aus `UMGEZOGEN`, der Bildgrundlage und allen Ausnahmelisten der Strukturtests).
- Weiterleitungen (`app/routers/pages.py`, beide mit `dk_ohne_seite`): `/time-tracking` -- die Monteurin auf `/mobil/zeiten` (mit `?order_id=`),
  das Büro auf `/zeiten`, mit `?order_id=`/`?employee_id=` auf `/zeiten?auftrag=…&mitarbeiter=…#buchungen`; `/time-backoffice` -- die Monteurin auf
  `/mobil/zeiten`, das Büro auf `/zeiten` (mit `?absence=`). Werte nur als Zahl (`_zahl()`).
- Anker der früheren Reiter in `zeiten.html::binden()`: `#dashboard` -> Prüfen, `#entries` -> Buchungen, `#absences` -> Abwesenheiten,
  `#timesheets`/`#datev` -> Monat & Lohn (ohne Lohndaten Prüfen), `#workmodels`/`#settings` -> `/settings#time-rules`, `#options` ->
  `/settings#time-entry-types`. `?absence=` öffnet die Abwesenheiten mit Status „Alle“ und hebt den Antrag hervor (`antragHervorheben()`, Fläche
  `--ds-signal-hell`, ins Bild geholt, einmal).
- Links: Einsatzberichte und Arbeitsvorbereitung „Zeiten (Auftrag)“ -> `/zeiten?auftrag=<id>#buchungen` (die Monteurin auf den Einsatzberichten
  weiter `/mobil/zeiten?order_id=`); Projektmappe „Zeiten öffnen“ -> `/zeiten#buchungen`; Dashboard „Freigabe“ -> `/zeiten?absence=<id>#abwesenheiten`;
  Einstellungen (Hinweis bei Zeitregeln) „auf der Seite Zeiten“.
- Nebenbefund: `_zahl()` (Zurück-Links seit 1.8.135), `_bericht_aus_adresse()` und die beiden Weiterleitungen prüften mit `isdigit()` allein --
  „²“ und Zahlen über 4300 Stellen ergaben 500. Jetzt `_zahl()` für alle: nur ASCII-Ziffern, höchstens 9 Stellen.

#### Jede Funktion der alten Seiten (Befund R5, „R5, Teil 2“)

Zeiterfassung: Mitarbeiter wählen -> Filter „Mitarbeiter“ und Feld im Dialog; laufende Uhr und „Schnell starten“ -> entfallen (Entscheidung R5a);
„Ende nachtragen“ -> Prüfen, „Zeiten von früher“; Kacheln des Tags -> Prüfen, „Monat“; Liste mit Ändern/Löschen -> Buchungen, „⋮“; „+ Manuell
buchen“ -> „Buchung“ im Kopf (Von–Bis oder Dauer); „Gruppe buchen“ -> „⋮ Kolonne buchen“; Gruppen-Timer -> entfällt (Kolonnenführer auf „Heute“);
Abwesenheit, Anträge, Hinweis -> Reiter Abwesenheiten, Zahl am Reiter; Auswertung eines Tags -> Buchungen (Monat, Filter, Tag je Zeile).
Backoffice: Filter -> Monat ‹ › und Filter der Buchungen; Dashboard -> Prüfen (Monat, Anträge) und „Stunden je Mitarbeiter“ in Monat & Lohn;
Buchungen, Bearbeiten -> Buchungen und Dialog; Abwesenheiten -> Reiter; Stundenzettel PDF/CSV, Abschließen, DATEV -> Monat & Lohn; Abschluss
aufheben -> „⋮“ (Admin); Einrichtung -> „⋮“ (Zeitregeln und DATEV, Zeit-Listen). Festgehalten als Tabelle in `tests/test_v520_zeiten_umstellung.py`
(`FUNKTIONEN`), geprüft gegen die gezeichnete Seite des Admins.

#### Festlegungen 1.9.98 (Bitte bestätigen)

1. Ein Eintrag „Zeiten“ in der Leiste an der Stelle der Zeiterfassung (Gruppe „Kaufmännisch“, Symbol der Zeiterfassung), für jede Rolle.
2. `/time-tracking` mit `?order_id=`/`?employee_id=` öffnet „Zeiten“ auf „Buchungen“ mit gesetztem Filter; ohne Angabe „Prüfen“.
3. `/time-backoffice` führt die Monteurin zu „Meine Zeiten“ (bis 1.9.97 ein 403), wie `/time-tracking`.
4. Die Anker der früheren Reiter öffnen den passenden neuen; „Stundenzettel“ und „DATEV / Lohn“ ohne Lohndaten „Prüfen“.
5. `?absence=` öffnet die Abwesenheiten mit Status „Alle“ und hebt den Antrag hervor, ohne Reiterwechsel danach.
6. „Zeiten (Auftrag)“ auf Einsatzberichten und Arbeitsvorbereitung öffnet „Buchungen“ mit dem Auftrag im Filter.
7. Projektmappe: „Zeiten öffnen“ (bis 1.9.97 „Zeiterfassung öffnen“) öffnet „Buchungen“ ohne Filter (einen Filter „Projekt“ gibt es nicht).
8. Ohne Ersatz entfallen die eigene Uhr des Büros („Laufende Zeiterfassung“, „Schnell starten“) und der Gruppen-Timer.
9. „Buchungen“ zeigt einen Monat vollständig -- die Grenzen der alten Listen (Backoffice 2000, Zeiterfassung 500 je Tag) und ihr Hinweis
   „gekürzt“ entfallen.
10. Eine Zahl aus der Adresse hat höchstens 9 Stellen aus 0–9, sonst gilt sie als nicht angegeben.

#### Tests und Prüfung

Neu `tests/test_v520_zeiten_umstellung.py`: Weiterleitungen je Rolle mit Filtern, Angriff „nur eine Zahl“ (²,  ٣, 5000 Stellen, `//evil…`),
Zurück-Links mit „²“, Anker der früheren Reiter in node, Leiste mit einem Eintrag, kein Link mehr auf die alten Adressen, jede Funktion des
Befunds erreichbar (Tabelle, vollständig gegen die Spiegelstriche des Befunds), was eine Rolle nicht darf, fehlt im Markup. `test_v449` entfernt
(prüfte den Dialog der Zeiterfassung, ersetzt durch den Dialog von „Zeiten“ in `test_v450`/`test_v518`).

Angepasste Erwartungen (Tests):
- `test_v100` (2): „Schnell starten“, Ausweichwege der Zeiterfassung -> LV-Position und Kontext im Dialog von „Zeiten“, Tätigkeiten mit Rückfall.
- `test_v102`: „Gruppenbuchung“, „Abwesenheitsanträge“ -> „Kolonne buchen“, „Abwesenheit beantragen“.
- `test_v103`: „Zeiterfassungs-Backoffice“, „DATEV / Lohn“, „Stundenzettel“ -> „Monat & Lohn“, „DATEV-Export“, „Stundenzettel aller als PDF“;
  Einstellungen verlinken `/zeiten`.
- `test_v104`: Buchungen „immer der laufende Monat“ (`currentMonthQs()`) -> ein Monat mit ‹ › (`MONAT`).
- `test_v105`: `editProject`/`editOrder`/`editOrderItem` -> `bdAuftrag`/`bdPosition`.
- `test_v203`: die Zeiterfassung verlinkt die Einsatzberichte -> die Einsatzberichte verlinken „Zeiten (Auftrag)“.
- `test_v239` (2): Dashboard-Link `/time-backoffice?absence=…#absences` -> `/zeiten?absence=…#abwesenheiten`; Hervorheben ohne `showTab()` ->
  ohne `reiterZeigen()`, mit `scrollIntoView`.
- `test_v242`: Backoffice direkt nach der Zeiterfassung -> „Zeiten“ als letzter Eintrag von „Kaufmännisch“, keine alten Links.
- `test_v244`: Doppellink `/time-backoffice` in Leiste und Einstellungen -> `/zeiten`.
- `test_v253`, `test_v417` (Leiste): „zeiterfassung“, „backoffice“ -> „zeiten“.
- `test_v417`: Reiter des Backoffice -> Reiter von „Zeiten“, Abschluss/Export/PDF über ihre neuen IDs.
- `test_v264`: Büro auf `/time-tracking` 200 mit `groupDialog` -> 302 auf `/zeiten`, dort `kolonneDialog`.
- `test_v282`: `/time-backoffice` Monteurin 403, Büro 200 -> 302 auf `/mobil/zeiten` bzw. `/zeiten`.
- `test_v313`: Seiten mit Zeitbuchungslisten ohne Zeiterfassung und Backoffice, „Zeiten“ nicht darunter.
- `test_v329`: Felder der Backoffice-Korrektur (`ui_keys`) -> `buchungSpeichern` ohne `employee_id` beim Ändern.
- `test_v334`: Backoffice-Dialog in node entfällt (Dialog von „Zeiten“ in `test_v450`), der Server-Teil bleibt.
- `test_v390`: `today()` der Zeiterfassung, `updateClock` in `ERLAUBT` -> Vorgabedatum `bdDatum`/`kdDatum` aus `berlinToday()`; Eintrag entfernt.
- `test_v401`: 10 -> 11 Weiterleitungen mit f-String.
- `test_v407`, `test_v424`, `test_v447`: Ausnahmen der beiden Seiten entfernt (3 Handler, Zahlenfelder der Zeiterfassung, 8 Auswahlfelder).
- `test_v419`: `/time-backoffice` -> `/zeiten` unter den Seiten unter Last.
- `test_v422`: Prüfungen der Seite (ICH, Rollenprüfung im Browser, Anfragen der Seite) entfallen, die Regeln des Servers bleiben.
- `test_v425`: umleitende Seitenrouten + `time_backoffice_page`.
- `test_v431`: 318 -> 310 Bilder, 256 -> 248 bisherige.
- `test_v436`: „+ Manuell buchen“ einmal -> „Buchung“ (`neueBuchung`) einmal.
- `test_v440`: Nutzer der Meldung „Konto ohne Mitarbeiter“ ohne die beiden Seiten; Adressen ohne `/time-tracking`, `/time-backoffice`.
- `test_v441`: Bereiche „zeiterfassung“, „backoffice“ -> „zeiten“; 46 -> 44 Seiten mit Leiste (zweimal); Titelzeilen und Untermenü ohne die beiden.
- `test_v450` (5): Dialog der Büro-Zeiterfassung (`openManual`) -> Dialog „Buchung ändern“ von „Zeiten“, Kennzeichen „(Auftrag abgeschlossen)“.
- `test_v454`: Untermenü ohne Backoffice; `test_backoffice_kopf_ueberlebt_den_ladefehler` entfällt.
- `test_v486`: Standardpause `manualBreak`/`groupBreak` -> `bdPause`/`kdPause` leer bzw. Mindestpause der Buchung.

Angepasste Erwartungen (Klicktests):
- `klicktest_rahmen`: Kopfgruppe „Zeiterfassung“ (ohne Aktion, ohne Menü) -> „Zeiten“ (Aktion „Buchung“, Menü Kolonne buchen, Zeitregeln und
  DATEV, Zeit-Listen); aktiver Bereich zeiterfassung -> zeiten; Menü „Zeiterfassung (Auftrag)“ -> „Zeiten (Auftrag)“ (Einsatzberichte,
  Arbeitsvorbereitung), Link `/time-tracking?order_id=` -> `/zeiten?auftrag=…#buchungen`; Untermenü ohne Backoffice.
- `klicktest_neue_ordnung`: Leiste „Zeiterfassung“, „Backoffice“ -> „Zeiten“ (Monteurin „Zeiterfassung“ -> „Zeiten“); Reiter und Links des
  Backoffice -> Reiter von „Zeiten“ und Links im „⋮“; `/time-backoffice#workmodels` usw. wie bisher in die Einstellungen.
- `klicktest_zeitbuchungen_liste`: Backoffice „gekürzt: 2000 von N“ und 2000 Zeilen -> „Zeiten“ N Zeilen ohne Hinweis, Summe ohne die laufende;
  Büro-Zeiterfassung „gekürzt: 500 von 501“ an Annas Tag -> „Zeiten“ mit Filter Anna, 501 Zeilen, 501,00 h.
- `klicktest_browser_datum`: `today()` der Zeiterfassung -> Datum im Dialog „Buchung“.
- `klicktest_auswahl_restfaelle`: Backoffice-Korrektur „(abgeschlossen)“ -> Dialog „Buchung ändern“ „(Auftrag abgeschlossen)“.
- `klicktest_monteurin_regeln`: Zeiterfassung für Tom („Ende nachgetragen (…): gebucht 8,25 h · anwesend 8,75 h · Pause 30 min“) -> „Zeiten“,
  Prüfen: Vorschau „anwesend 8:45 h · Pause nach Zeitregel − 0:30 h · gebucht 8,25 h“, Meldung „Ende eingetragen: …“, gebucht 8,25 h mit 30 min.
- `klicktest_backoffice_buero` entfernt -- übernommen in `klicktest_zeiten`: Büro – Auftrag ohne Anfrage an Kontext und Personalnummern, Exporte
  403; Büro – Finanzen im abgeschlossenen Monat ohne „⋮“, Stundenzettel 200, kein „Abschluss aufheben“, zurücknehmen 403. Entfallen: die Hinweise
  und Spalten des Backoffice („nur lesen“, „nur Admin“), „Abgeschlossen bis“ auf einen Tag (seit 1.9.97 monatsweise).

Im ersten Lauf rot und am Klicktest behoben: `klicktest_zeitbuchungen_liste` erwartete die Summe mit Tausenderpunkt („2.500,00 h“) -- `zahlText()`
setzt keinen, wie überall. Nebenbei: eine ungültige Escape-Folge (`\s`) in `klicktest_zeiten.py` (SyntaxWarning seit 1.9.97).

Gegenproben (Marker `GEGENPROBE`, byte-genau zurück, je FAILED): Zahl mit `isdigit()` allein -> 7 Tests; Backoffice wieder in der Leiste -> 4 Tests
und 3 Prüfungen von `klicktest_neue_ordnung`; Anker `#entries` ohne Zuordnung -> 1 Test und 6 Prüfungen von `klicktest_auswahl_restfaelle`;
Weiterleitung ohne Filter -> 3 Tests und 1 Prüfung von `klicktest_monteurin_regeln`; Link „Zeit-Listen“ fehlt -> 1 Test.

### R5b, Punkt 8 (1.9.99): „Berater- und Mandantennummer speichern“ als Hauptknopf

- `settings.html`: der Knopf `datevNummernSpeichern` ohne die Klasse `secondary` -- grün (`--ds-aktion`) wie „Zeitregeln und Lohnarten speichern“.
- Neu `tests/test_v521_datev_nummern_knopf.py`: derselbe Knopf wie „Zeitregeln und Lohnarten speichern“; kein Speichern-Knopf einer Karte (im
  Markup, `onclick="save…()"`) mit `secondary`. `klicktest_datev_nummern`: Farbe und Schrift wie der Knopf der Zeitregeln, Fläche `--ds-aktion`;
  das Bild zeigt den Knopf (bis 1.9.98 auf das Feld „Beraternummer“ gerollt -- nur der Aufbau).

#### Festlegungen 1.9.99 (Bitte bestätigen)

1. Jeder Speichern-Knopf einer Karte der Einstellungen ist der grüne Hauptknopf; die Knöpfe „Speichern“ je Zeile einer Liste (Basiszinssatz,
   Lohndaten je Mitarbeiter) bleiben ohne Fläche.

#### Tests und Prüfung

Angepasste Erwartungen: keine. Gegenprobe (Marker `GEGENPROBE`, byte-genau zurück, FAILED): der Knopf wieder mit `secondary` -> 2 Tests und 1 Prüfung
von `klicktest_datev_nummern`.

## Stufe 4, R5b Nachrunde (ab 1.9.100)

Vorgabe 27.10.2026: Festlegungen R5b bestätigt, außer 1.9.95 Nr. 5 und 9 und 1.9.97 Nr. 7 (ersetzt durch Punkt 6); 1.9.95 Nr. 4 und 1.9.97 Nr. 2–4
ersetzt Punkt 1. Die Prüfabfrage von 1.9.94 ergab auf dem Server 0 Zeilen.

### R5b Nachrunde, Punkt 0 (1.9.100): Prüfabfrage Kolonnenbuchungen, weit gefasst

`scripts/pruefabfrage_kolonne_weit.sql` (nur lesen: `BEGIN TRANSACTION READ ONLY` … `ROLLBACK`, Aufruf wie 1.9.94 mit `PGOPTIONS` und `psql`), drei
Teile, je mit Überschrift (`\echo`), ein Teil ohne Treffer zeigt „(0 Zeilen)“:

- a) jede Änderung „hours“ einer Zeitbuchung im Verlauf mit `PUT /api/time-entry-groups/{id}`, ohne Änderung „hours“ des Kopfs (Gruppen-Zeitbuchung)
  in derselben Anfrage -- ohne Datumsgrenze, ohne „mindestens zwei Mitglieder“, ohne „vorher verschieden“. Eine Anfrage: die Einträge eines Pfads,
  zwischen denen höchstens 5 Sekunden liegen (Inseln über `lag()`), statt „dieselbe Minute“ -- eine Anfrage über eine Minutengrenze wurde bis
  dahin zerteilt (eine bewusste Dauer, deren Kopf eine Sekunde später im Verlauf steht, erschiene dann als Fehler). Spalten: Gruppe, Tag, Auftrag,
  Mitarbeiter, Buchung, Stunden vorher/nachher, wann (Europe/Berlin) und von wem, `uhrzeiten_geaendert` (in derselben Anfrage änderten sich Beginn
  oder Ende des Mitglieds -- ein Ändern mit Von/Bis, bei dem das Mittel des Kopfs gleich blieb, kein Fehler). Gelöschte Buchungen oder Gruppen
  erscheinen mit leerem Namen (LEFT JOIN, die Gruppe aus dem Pfad).
- b) ohne Verlauf: jedes Mitglied einer Kolonnenbuchung (gebucht, mit Beginn und Ende), dessen Stunden nicht zu Von/Bis minus seiner Pause passen
  -- Anwesenheit auf vier Stellen, minus Pause, mit der Rundung der Zeitregeln (`rounding_minutes`, sonst vier Stellen), wie
  `nachtrag_nach_zeitregel()`/`ende_rechnen()`; Abweichungen unter 0,005 h zählen nicht (Stopp und Nachtrag runden an der vierten Stelle
  verschieden). Findet auch Fälle ohne Verlauf (vor dessen Einführung) und den Fehler bis 1.9.89 an Mitgliedern mit Von/Bis (ihre Uhrzeiten blieben
  stehen, die Stunden waren das Mittel). Gerechnet mit der Rundung von heute (Spalte `rundung_min`).
- c) Kontrollzahlen je Monat (Europe/Berlin): Anfragen, Kolonnen, Einträge, Stundenänderungen der Mitglieder und des Kopfs, davon in a).

**Probe: schrieb der fehlerhafte Weg (Code von 1.9.89) für die Mitglieder Einträge in `audit_logs`? Ja.** Arbeitskopie auf `9637819` (1.9.89),
echte Anmeldeschranke (setzt Konto, Pfad und Methode für den Verlauf), als Admin über die API: Kolonne 07:00–12:30 für Mia (ohne Vorbuchung) und Tom
(Fahrzeit 06:15–07:00 am Morgen) -> Mia 5,50 h ohne Pause, Tom 5,00 h mit 30 min, Kopf 5,25 h (Mittel); dann `PUT /api/time-entry-groups/1` mit nur
`{"notes": "nur die Notiz"}`. Ergebnis: beide Mitglieder 5,25 h, Mia mit 30 min Pause; der Verlauf dieser Anfrage (alle mit „Anna Admin“, PUT,
`/api/time-entry-groups/1`):

    Zeitbuchung 2 (Mia)  break_minutes      0 -> 30
    Zeitbuchung 2 (Mia)  min_break_minutes  0 -> 30
    Zeitbuchung 2 (Mia)  hours              5.5000 -> 5.2500
    Zeitbuchung 2 (Mia)  notes              -> nur die Notiz
    Zeitbuchung 3 (Tom)  min_break_minutes  0 -> 30
    Zeitbuchung 3 (Tom)  hours              5.0000 -> 5.2500
    Zeitbuchung 3 (Tom)  notes              -> nur die Notiz
    Gruppen-Zeitbuchung 1  notes            -> nur die Notiz

Der Weg ändert die Mitglieder über das ORM (`update_group()`: `entry.hours = amount`), der Verlauf (`app/audit.py::collect_audit()`, vor jedem
Flush) schreibt jede geänderte Spalte -- für ein Mitglied, dessen Stunden schon den Stunden des Kopfs glichen, keine Zeile „hours“ (nichts geändert).
Der Kopf bekommt keine Zeile „hours“, er behält seine Stunden. Genau das sucht a). Gegenprobe auf dem heutigen Stand (1.9.99): dieselbe Anfrage
lässt die Stunden stehen, im Verlauf nur die drei Zeilen „notes“. Dass die Prüfabfrage von 1.9.94 auf dem Server leer blieb, heißt also: seit dem
23.10.2026 keine solche Anfrage mit mindestens zwei Mitgliedern mit verschiedenen Stunden -- was davor lag, prüft erst a).

#### Festlegungen 1.9.100 (Bitte bestätigen)

1. Eine Anfrage im Verlauf = die Einträge desselben Pfads mit höchstens 5 Sekunden Abstand zum vorigen (auch über eine Minutengrenze).
2. a) zeigt auch Änderungen mit Von/Bis, bei denen das Mittel des Kopfs gleich blieb -- gekennzeichnet in `uhrzeiten_geaendert`, kein Fehler.
3. b) rechnet mit der Rundung der Zeitregeln von heute; Abweichungen unter 0,005 h zählen nicht.
4. c) zählt je Monat (Europe/Berlin) Anfragen, Kolonnen, Einträge, Stundenänderungen von Mitgliedern und Kopf und, wie viele davon a) zeigt.
5. Die Prüfabfrage von 1.9.94 bleibt im Repo (die enge Fassung, Abgleich mit dem Ergebnis vom 27.10.2026).

#### Tests und Prüfung

Neu `tests/test_v522_pruefabfrage_kolonne_weit.py`: nur lesend mit drei Teilen; unter PostgreSQL (Wegwerf-Schema) ein Bestand -- gefunden: zwei
Mitglieder vorher verschieden, nur ein Mitglied, alte Werte gleich, über die Minutengrenze (08:00:59,8 und 08:01:00,3), vor dem 23.10.2026, ein Ändern
mit Von/Bis (mit `uhrzeiten_geaendert`), der Fehler 25 Sekunden vor einer bewussten Dauer derselben Gruppe; nicht gefunden: bewusste Dauer mit Kopf
über die Minutengrenze, ein einzelnes Mitglied über `/api/time-entries/{id}`, eine Notiz; b) die Kolonne mit den Stunden des Fehlers (beide
Mitglieder 5,25 statt 5,00) gefunden, eine richtige, eine mit Rundung auf 15 min und eine Einzelbuchung mit falschen Stunden nicht; c) je Monat. Die
Datei läuft mit `psql` (Rückgabe 0, drei Überschriften, je „(0 Zeilen)“ auf leerem Schema).

Angepasste Erwartungen (Nebenbefund im Lauf vor dem Commit): `test_v365::test_date_is_the_day_of_the_signature_in_berlin_not_of_the_follow_up` --
nur der Aufbau: Unterschrift um 22:30 UTC von vorgestern -> 23:30 UTC. Der Test erwartete „in Berlin der nächste Tag“, das galt für 22:30 UTC nur in der
Sommerzeit (UTC+2); seit dem 25.10.2026 (UTC+1) ist es 23:30 am selben Tag, der Test war jeden Tag rot (im ersten vollen Lauf dieser Runde
aufgefallen). 23:30 UTC ist in beiden Zeiten nach Mitternacht; die anderen Tests mit 22:00/22:30 UTC nehmen feste Daten. Gegenproben (Marker
`GEGENPROBE`, byte-genau zurück, je FAILED mit Abweichung im Ergebnis): eine Anfrage = dieselbe
Minute (die bewusste Dauer erscheint) -> 1 Test; Datumsgrenze 23.10.2026 (die Gruppe vom 15.09. fehlt) -> 1 Test; Kopf irgendwann statt in derselben
Anfrage geändert (der Fehler vor der Dauer fehlt) -> 1 Test; b) ohne Rundung (die Kolonne mit 15 min erscheint) -> 1 Test.

### R5b Nachrunde, Punkt 3 (1.9.100): Befund -- die Pause einer Dauer (nichts geändert)

Vorgabe: „Tom 15.10. war 07:00–16:30 mit 0:45, ist jetzt „Dauer“ 8,00 – die Zeile zeigt weiter Pause 0:45. Woher, und zählt diese Pause in „Tag
zusammen“, „Pause passt nicht zum Tag“, Stundenzettel, CSV, DATEV? Was rechnet der Server für einen Tag mit einer Dauer?“ Nachgerechnet mit dem Code
von 1.9.99 (Toms Tag wie in `klicktest_zeiten`: Fahrzeit 06:15–07:00, Baustelle 07:00–16:30, dann als Dauer 8,00 h gespeichert).

**Woher.** Der Dialog „Buchung ändern“ belegt in „Dauer“ das Feld „Pause (Min.)“ mit der gespeicherten Pause vor (`bdPauseDauer` =
`break_minutes`, 45) und schickt sie mit (`break_minutes`). Der Server speichert eine Dauer, wie sie kommt: Beginn und Ende leer (seit 1.9.90), Pause
45 min, Mindestpause 45 (`min_break_minutes`, weil Stunden oder Pause gesendet wurden), 8,00 h. Er rechnet die Pause einer Dauer nie neu.

**Was die Pause einer Dauer bewirkt.** Eine Dauer ist gebuchte Arbeitszeit (netto); ihre Anwesenheit ist Stunden + Pause
(`_anwesend_der_buchung()`, `entry_to_dict()`): hier 8,00 + 0,75 = 8,75 h.

| Stelle | zählt die Pause der Dauer? | Toms 15.10. |
|---|---|---|
| „Tag zusammen“ (`tag_stand()`, Vorschauen von Nachtrag, Ende, Ändern) | ja, über die Anwesenheit | 0,75 + 8,75 = 9:30 h (vorher 10:15 h) |
| „Pause passt nicht zum Tag“ (`pausen_vorschau()`, auch der Abschluss) | ja: Dauern zählen zuerst, ihre Pause als schon abgezogene Pause des Tags; Buchungen mit Uhrzeiten bekommen nur, was dann noch fehlt | Pflichtpause für 9,5 h = 45 min (mehr als 9 h; korrigiert 1.9.107, hier stand 30 min), abgezogen 45 -> passt |
| die Pause jeder neuen Buchung dieses Tags (`pause_nach_zeitregel()`) | ja, wie oben | -- |
| Stundenzettel (PDF des Büros) | angezeigt in der Spalte „Pause“, Stunden unverändert | Pause 45, Stunden 8,00, von/bis leer |
| Stundendaten als CSV | angezeigt (`Pause_Min`), Stunden unverändert | `;;;45;8,00;` |
| DATEV-Export | nein, nur die gespeicherten Stunden (`tagessumme()`) | 8,00 + 0,75 |
| „Meine Zeiten“ der Monteurin | angezeigt: anwesend 8:45, Pause 0:45, gebucht 8,00 | -- |

Gegenprobe derselben Dauer mit Pause 0: „Tag zusammen“ 8:45 h; der Tag passt dann nicht mehr (Pflichtpause 30 min, abgezogen 0) -- „Prüfen“ schlüge
vor, der Fahrzeit 06:15–07:00 30 min abzuziehen (0,75 -> 0,25 h), weil nur sie Uhrzeiten hat.

**Was der Server für einen Tag mit einer Dauer rechnet:** die Dauer bleibt, wie eingetragen (Stunden und Pause); sie zählt mit Stunden + Pause zur
Anwesenheit des Tags und mit ihrer Pause zur schon abgezogenen Pause, vor den Buchungen mit Uhrzeiten; die Pflichtpause, die dann noch fehlt, geht nur
an Buchungen mit Uhrzeiten (höchstens ihre Anwesenheit). Die Pause einer Dauer ist also nicht „nur Anzeige“: sie entscheidet, ob der Tag passt.

**Vorschlag (nicht gebaut).** Die Pause einer Dauer ist eine Angabe über den Tag, keine Rechnung -- der Dialog soll das zeigen statt sie still
mitzunehmen: (1) beim Wechsel von „Von – Bis“ zu „Dauer“ bleibt „Pause (Min.)“ mit der bisherigen Pause vorbelegt (sie war die Pause dieses
Abschnitts), heißt aber „Pause an diesem Tag (Min.)“ mit dem Satz „zählt zur Pause des Tags – ohne Pause muss der Tag sie anderswo haben“;
(2) die Vorschau rechnet auch für „Dauer“ beim Server (wie für Von – Bis): „Anwesend 8:45 h · Tag zusammen 9:30 h · Pause des Tags passt“ bzw. „…
passt danach nicht – der Tag erscheint unter „Prüfen““; (3) in der Liste steht die Pause einer Dauer wie bisher (sie zählt). Alternative, wenn
eine Dauer nie eine Pause tragen soll: „Dauer“ ohne Pausenfeld, die Pause des Tags dann nur über Buchungen mit Uhrzeiten -- das ändert, was alte
Dauern (Kolonnen-Nachträge mit Pause) bisher bewirken, und bräuchte eine Entscheidung zum Bestand.

### R5b Nachrunde, Punkt 1 (1.9.101): Abwesenheiten -- Büro – Finanzen sieht alle

Entscheidung von Tobias: Büro – Finanzen sieht alle Abwesenheiten und Anträge und stellt Anträge auch für andere; entscheiden nur der Admin;
zurückziehen darf, wer den Antrag gestellt hat. Büro – Auftrag: nur eigene. Zahl am Reiter, „Anträge“ auf Prüfen und „Vor dem Abschluss“ folgen
daraus; „✓ Anträge entschieden“ nur, wenn wirklich keiner offen ist. Ersetzt Festlegung 1.9.95 Nr. 4 und 1.9.97 Nr. 2–4.

- `app/permissions.py`: `darf_abwesenheiten_aller()` (Admin, Büro – Finanzen) und `darf_antrag_zurueckziehen(user, antrag)` (wer ihn gestellt hat,
  `requested_by_user_id`; ohne Angabe die Person, für die er gilt). Tabelle im Rechtekonzept-Archiv, „Nachtrag 1.9.101“.
- `app/routers/absence_requests.py`: `GET` alle nach `darf_abwesenheiten_aller()`, sonst die eigenen; `POST` für andere ebenso; `DELETE` nur nach
  `darf_antrag_zurueckziehen()` (403 `NUR_WER_GESTELLT`); jede Antwort mit `darf_zurueckziehen` (offen und von diesem Konto gestellt).
  `app/absence_requests.py::request_to_dict()` mit `beantragt_von` (Anzeigename des Antragstellers, wenn er nicht die Person selbst ist).
- `app/routers/zeiten.py`: `_sichtbare_antraege()` für Prüfen und Abwesenheiten; „Vor dem Abschluss“ bekommt „n Anträge offen“ (die das Konto
  sieht) und `antraege_entschieden` (kein Antrag offen, auch keiner, den das Konto nicht sieht); der Hinweis für Büro – Auftrag heißt jetzt „Hier stehen
  nur deine eigenen Anträge – die Anträge aller sehen Admin und Büro – Finanzen.“; Büro – Finanzen beantragt mit Feld „Mitarbeiter“, auch ohne
  eigenen Mitarbeiter.
- `zeiten.html`: `abschlussHtml()` -- offene Punkte, dazu „✓ Anträge entschieden“ nur mit `antraege_entschieden`; ohne offenen Punkt „✓ Nichts offen
  – der Monat lässt sich abschließen.“ nur mit `antraege_entschieden`, sonst „✓ Der Monat lässt sich abschließen.“; Anträge mit „beantragt von …“;
  der Dialog wählt den eigenen Mitarbeiter vor.
- `mobil_zeiten.html` („Meine Zeiten“): „Zurückziehen“ nur nach `darf_zurueckziehen`, „beantragt von …“ unter dem Antrag.

#### Festlegungen 1.9.101 (Bitte bestätigen)

1. „Zurückziehen darf, wer den Antrag gestellt hat“ gilt auch für den Admin: Anträge anderer entscheidet er, er zieht sie nicht zurück (bis 1.9.100
   erlaubte der Server es ihm).
2. Ein Antrag ohne vermerkten Antragsteller (angelegt ohne Konto, z. B. aus Testdaten oder Altbestand) zieht die Person zurück, für die er gilt.
3. Ein Antrag, den das Büro für Tom gestellt hat, sieht Tom in „Meine Zeiten“ mit „beantragt von …“, ohne „Zurückziehen“.
4. „Abwesenheiten“ zeigt weiter die Anträge; die Abwesenheiten der Plantafel (direkt eingetragen) bleiben auf der Plantafel.
5. „Vor dem Abschluss“ nennt die offenen Anträge, die das Konto sieht, als letzten Punkt („1 Antrag offen“); „Anträge entschieden“ steht dort (wie
   in „Monat & Lohn“) nur neben anderen offenen Punkten, ohne offenen Punkt heißt es „Nichts offen – der Monat lässt sich abschließen.“ -- beides nur,
   wenn kein Antrag offen ist; sieht das Konto offene Anträge nicht (Büro – Auftrag), steht „Der Monat lässt sich abschließen.“
6. Büro – Finanzen ohne eigenen Mitarbeiter stellt Anträge nur für andere (Feld „Mitarbeiter“, ohne Vorwahl); mit eigenem Mitarbeiter ist er
   vorgewählt.

#### Tests und Prüfung

Neu `tests/test_v523_abwesenheiten_rechte.py`: Regel je Rolle; Büro – Finanzen sieht Toms Antrag (API und „Zeiten“, ohne eigenen Mitarbeiter),
stellt „Krank“ für Tom, entscheidet nicht (403), zieht Toms Antrag nicht zurück (403), den eigenen schon; Büro – Auftrag für Tom 403, sieht nur
eigene; Tom zieht den Antrag des Büros nicht zurück (403), seinen schon, „beantragt von“; der Admin zieht Toms Antrag nicht zurück (403), entscheidet
ihn; ohne Antragsteller die Person; Zahl, Anträge und „Vor dem Abschluss“ je Konto; in node die Haken von „Vor dem Abschluss“, „beantragt von“ in der
Zeile, „Meine Zeiten“ nur mit `darf_zurueckziehen`. `klicktest_zeiten`: Büro – Finanzen sieht alle, stellt „Krank“ für Tom (Bild), Entscheiden 403,
zieht zurück; Büro – Auftrag für Tom 403.

Angepasste Erwartungen:
- `test_v519::test_abwesenheiten_buero_nur_die_eigenen` (Büro – Finanzen sieht nur die eigenen, Hinweis) -> `test_abwesenheiten_buero_auftrag_nur_die_eigenen`
  (dasselbe für Büro – Auftrag).
- `test_v519::test_antrag_fuer_andere_nur_der_admin`: Büro – Finanzen für Tom 403 (mit und ohne Mitarbeiter) -> 200, neu Büro – Auftrag für Tom 403;
  umbenannt in `test_antrag_fuer_andere_admin_und_finanzen`.
- `test_v517::test_pruefen_antraege_je_konto`: Büro – Finanzen keine Anträge, Zahl 0 -> Toms Antrag, Zahl 1; Büro – Auftrag keine, Zahl 0.
- `test_v422::test_jede_anfrage_der_seite_ist_dem_buero_erlaubt`: `GET /api/absence-requests` ohne Mitarbeiter 403 -> für Büro – Finanzen 200.
- `klicktest_zeiten`: „Fin: Hinweis und kein „beantragen““ (ohne Mitarbeiter) -> alle Anträge, kein Hinweis, beantragen für Tom; der Hinweis für Büro –
  Auftrag mit dem neuen Text.
- `test_v518::test_antraege_entscheidet_nur_der_admin` und `test_v519::test_antrag_knoepfe_nach_dem_server`: nur der Aufbau -- die neue Hilfsfunktion
  `beantragtText` in der Liste der Funktionen, die der node-Lauf lädt (im ersten Lauf rot: ReferenceError).

Gegenproben (Marker `GEGENPROBE`, byte-genau zurück, je FAILED mit Abweichung im Ergebnis): alle Anträge nur der Admin -> 6 Tests (v523, v517, v519);
zurückziehen die Person selbst statt wer gestellt hat -> 3 Tests; „Anträge entschieden“ ohne `antraege_entschieden` -> 1 Test; „Meine Zeiten“ mit
„Zurückziehen“ an jedem offenen Antrag -> 1 Test; „Vor dem Abschluss“ ohne die offenen Anträge -> 1 Test.

### R5b Nachrunde, Punkt 4 (1.9.102): „Prüfen“ für Büro – Auftrag

- `app/routers/zeiten.py`: `zahlen.pruefen` = Zeiten von früher mit `darf_schliessen` + Tage mit `darf_buchen` (bis 1.9.101 alle) -- für Büro – Auftrag
  0, die Seite zeigt dann keine Zahl.
- `zeiten.html`: die Karte „Zeiten von früher laufen noch“ ist „Wartet auf dich“ (Signalkarte, Punkt) nur, wenn das Konto an mindestens einer Zeit das
  Ende eintragen darf; sonst ruhige Karte mit „Zur Info“ (Augenbraue ohne Punkt) und unten „Das Ende trägt der Admin oder Büro – Finanzen ein.“
  statt „Gebucht wird erst mit deinem Klick …“.

#### Festlegungen 1.9.102 (Bitte bestätigen)

1. „Wartet auf dich“ oder „Zur Info“ entscheidet die Karte an den Zeilen: darf das Konto an keiner Zeit das Ende eintragen, ist sie „Zur Info“ (heute
   Büro – Auftrag; ebenso, wenn alle Zeiten im abgeschlossenen Zeitraum lägen und das Konto nicht Admin ist).
2. „Zur Info“ ist eine ruhige Karte (weiß mit Rahmen, Augenbraue grau ohne Punkt) -- keine Signalfarbe für etwas, das nicht auf einen wartet.
3. Die Zahl am Reiter „Prüfen“ zählt nur, was auf das Konto wartet (Ende eintragen, Pause buchen); „Pause passt nicht zum Tag“ bleibt für Büro –
   Auftrag sichtbar, ohne Knöpfe, ohne eigenen Hinweis.

#### Tests und Prüfung

Neu: `test_v517::test_zahl_am_reiter_pruefen_nur_was_auf_das_konto_wartet` (eine Zeit von früher und ein Tag mit unpassender Pause: Büro – Auftrag 0,
Büro – Finanzen und Admin 2, die Listen für alle); `test_v518::test_karte_zeiten_von_frueher_wartet_nur_auf_wer_das_ende_eintraegt` (in node: „Wartet
auf dich“ mit Signal und dem Satz zum Klick, „Zur Info“ ruhig mit dem Satz, wer das Ende einträgt). `klicktest_zeiten`: Büro – Auftrag sieht „Zur
Info“, den Satz, keinen Punkt, keine Zahl am Reiter „Prüfen“ (Bild); der Admin „Wartet auf dich“ als Signalkarte.

Angepasste Erwartungen: keine geänderte. Im ersten Klicktest-Lauf rot und am Klicktest behoben: die zwei neuen Prüfungen der Karte lasen die
Augenbraue mit `innerText` -- die zeigt sie in Großbuchstaben („WARTET AUF DICH“, CSS `text-transform`); jetzt `textContent`. Gegenproben (Marker
`GEGENPROBE`, byte-genau zurück, je FAILED): die Zahl zählt alles -> 1 Test; die Karte immer „Wartet auf dich“ -> 1 Test.

### R5b Nachrunde, Punkt 2 (1.9.103): Reihenfolge der Buchungen

- `app/zeiten.py::reihenfolge()`: Datum absteigend, im Tag nach dem Namen des Mitarbeiters (wie angezeigt, „Vorname Nachname“, ohne Groß-/Kleinschreibung),
  dann Beginn aufsteigend, Buchungen ohne Beginn (Dauer) zuletzt, bei Gleichstand nach der Nummer der Buchung; `buchungen()` sortiert die gefilterten
  Zeilen damit (bis 1.9.102 die Reihenfolge von `list_entries()`, die neuesten zuerst).

#### Festlegungen 1.9.103 (Bitte bestätigen)

1. „Nach Mitarbeiter“ heißt nach dem angezeigten Namen (Vorname Nachname), bei gleichem Namen nach der Nummer des Mitarbeiters.
2. Eine laufende Zeit steht im Tag nach ihrem Beginn wie jede andere (auch „von früher“). Die Vorlage zeigt am 19.10. Toms laufende Zeit vor Mias
   Zeiten -- nach der Regel steht Mia vorn; das ist die einzige Abweichung von der Vorlage (am 16.10. und 15.10. stimmt die Regel mit ihr überein).
3. Gleicher Beginn derselben Person: nach der Nummer der Buchung (die zuerst angelegte zuerst).

#### Tests und Prüfung

Neu `test_v517::test_buchungen_reihenfolge_wie_die_vorlage` (Mia 07:00–12:00 vor 12:00–16:15, obwohl umgekehrt angelegt; Toms Dauer nach seiner Zeit mit
Uhrzeiten; Tom nach Mia; der Vortag danach). `klicktest_zeiten`: Ausschnitt um den 19.10. erweitert.

Angepasste Erwartungen (`klicktest_zeiten`):
- „Fin: Zeilen wie die Vorlage (Ausschnitt)“: Do 15.10. Tom 07:00–16:30, Tom 06:15–07:00, Mia Dauer -> Mia Dauer, Tom 06:15–07:00, Tom 07:00–16:30;
  neu dazu Mo 19.10. Mia 07:00–12:00, Mia 12:00–16:15, Tom 06:45–16:00.
- „Fin: Kolonne gebucht -- beide in der Liste“: Fr 23.10. Tom, Mia -> Mia, Tom.

Gegenproben (Marker `GEGENPROBE`, byte-genau zurück, je FAILED): ohne Sortierung (die neuesten zuerst) -> 1 Test; Dauer vorn statt zuletzt -> 1 Test.

### R5b Nachrunde, Punkte 5 und 6 (1.9.104): „gebucht/geändert von …“ und „Dauer · vom Büro“

- `app/zeiten.py::_verlauf_der_buchungen()`: je Buchung der Liste aus dem Verlauf (`audit_logs`, Art „Zeitbuchung“, „geändert“, nur lesen, je 500
  Buchungen eine Abfrage über den Index auf `entity_id`):
  - `gebucht_von`/`gebucht_am`: wer die Zeit beendet hat (Status läuft -> gebucht: Stopp, Gruppen-Stopp, „Ende nachtragen“, „Zeitart wechseln“) und
    wann; ohne solchen Eintrag (Nachtrag, Kolonnen-Nachtrag, Buchung des Büros) der Anleger (`created_by`) mit `created_at`; steht im Verlauf kein
    Konto („System“: Testdaten, Skripte), der Anleger, ohne ihn kein Name.
  - `geaendert_von`/`geaendert_am`: der letzte Eintrag nach dem Buchen, ohne die Anfrage, die gebucht hat (derselbe Pfad, höchstens 5 Sekunden).
  - `vom_buero`: das Konto, das zuletzt Stunden, Beginn, Ende, Tag oder Pause geändert hat, arbeitet außerhalb der Monteursansicht
    (`MOBIL_ROLLEN`); ohne solche Änderung mit Konto der Anleger. Eine Notiz danach zählt nicht.
- `zeiten.html::unterzeile()`: „<Name> · gebucht von … am … · geändert von … am …“ (Zeitpunkte über `berlinZeitpunkt()`); fehlt der Name, „gebucht
  am …“. `tests/test_v473_zeitpunkte_berlin.py`: `gebucht_am` und `geaendert_am` in `UTC_FELDER`.
- `klicktest_zeiten`: Tom hat ein Konto (Monteursansicht); seine Zeit am 15.10. bucht er selbst, beendet um 16:31 Berlin -- der Verlauf wie in der
  Anwendung (Konto und Pfad), sein Zeitpunkt im Befüllen auf den 15.10. gesetzt.

#### Festlegungen 1.9.104 (Bitte bestätigen)

1. „Gebucht von … am …“: bei einer gestoppten Zeit, wer sie beendet hat und wann (auch Admin oder Büro – Finanzen über „Ende eintragen“), sonst wer sie
   angelegt hat und wann.
2. „Geändert von … am …“: die letzte Änderung nach dem Buchen, jede Spalte (auch Notiz, Zeitart, Auftrag) und jeder Weg (Ändern, Kolonne, „Pausen neu
   rechnen“); nicht die Anfrage, die gebucht hat.
3. „Dauer · vom Büro“: wer zuletzt Stunden, Uhrzeiten, Tag oder Pause gesetzt hat, arbeitet außerhalb der Monteursansicht; eine Notiz oder Zeitart
   der Monteurin danach ändert das nicht (ersetzt Festlegung 1.9.95 Nr. 9).
4. Die Rolle eines Kontos zählt, wie sie heute ist (wie bisher beim Anleger), nicht wie sie beim Ändern war.
5. Gelesen wird aus dem Verlauf, keine neue Spalte: das gilt rückwirkend auch für Buchungen, die vor 1.9.104 geändert wurden; ohne Konto im Verlauf
   (Testdaten, Skripte, der Verlauf vor seiner Einführung) zählt der Anleger.

#### Tests und Prüfung

Neu `tests/test_v524_buchung_verlauf.py` (Verlauf mit Konto und Pfad wie die Anmeldeschranke): gebucht von Tom beim Stoppen, ohne Änderung; Büro –
Finanzen stellt Toms Buchung auf Dauer -> „geändert von Fin Finanzen“, `vom_buero`; Toms Notiz danach -> „geändert von Tom“, die Dauer bleibt „vom
Büro“; angelegte Dauer nach dem Konto (Monteurin nein, Büro ja); ohne Konto im Verlauf der Anleger; in node die Unterzeile wie die Vorlage.
`klicktest_zeiten`: Unterzeile „Tom Monteur · gebucht von Tom Monteur am 15.10., 16:31“, nach dem Speichern mit „· geändert von Fin Finanzen am …“.

Angepasste Erwartungen:
- `klicktest_zeiten` „Fin: als Dauer gespeichert -- Zeile“: „Dauer“ -> „Dauer · vom Büro“ (Festlegung 1.9.95 Nr. 9 ersetzt).
- `test_v473`: `UTC_FELDER` um `gebucht_am`, `geaendert_am` ergänzt (der Wächter kennt die neuen Zeitpunkte).

Gegenproben (Marker `GEGENPROBE`, byte-genau zurück, je FAILED mit Abweichung im Ergebnis): „vom Büro“ nur nach dem Anleger -> 2 Tests; „gebucht“ immer
der Anleger beim Anlegen -> 1 Test; „geändert“ auch die Anfrage, die gebucht hat -> 1 Test; eine Notiz zählt als gesetzte Zeit -> 1 Test; Unterzeile
ohne „geändert von“ -> 1 Test.

### R5b Nachrunde, Punkt 6 (1.9.105): Arbeitstage ohne Feiertage NRW, „Abschluss aufheben“ nur auf ein Monatsende

Festlegungen von Tobias (ersetzen 1.9.95 Nr. 5 und 1.9.97 Nr. 7; „Dauer · vom Büro“ steht in 1.9.104):

- `app/zeiten.py::arbeitstage()`: Montag bis Freitag ohne die gesetzlichen Feiertage in NRW -- `app/planning.py::automatic_public_holidays("NW", …)`,
  die Rechnung der Plantafel (Ostern nach Gauß, Fronleichnam und Allerheiligen für NW), fest „NW“, ohne die Einstellung „Bundesland“ der Plantafel und
  ohne betriebsfreie Tage.
- **Befund: wird die Zahl gespeichert oder verrechnet? Nein.** `arbeitstage()` rufen nur `GET /api/zeiten/pruefen` und `GET /api/zeiten/abwesenheiten`
  für die Anzeige am Antrag auf (`app/routers/zeiten.py`); kein Modell hat eine Spalte dafür, kein Urlaubskonto zieht sie ab, die Genehmigung legt eine
  Abwesenheit mit Von und Bis an (`EmployeeAbsence`), nicht mit Tagen. `ProductiveHoursSettings.vacation_days` (Produktivstunden-Rechner) ist eine
  Annahme der Kalkulation und hat mit Anträgen nichts zu tun. „Meine Zeiten“ zeigt keine Arbeitstage.
- `PUT /api/time-backoffice/lock` (`app/routers/time_backoffice.py`): zurücknehmen (ein Tag vor „Abgeschlossen bis“ oder leer) nur auf ein Monatsende
  -- leer 422 `ABSCHLUSS_NICHT_GANZ`, ein anderer Tag 422 `NUR_AUF_MONATSENDE`, nach der Rollenprüfung (Büro – Finanzen bekommt weiter 403). Vorrücken
  unverändert (auch auf einen Tag mitten im Monat über die API).
- `zeiten.html`: „Abschluss aufheben“ bietet die zwölf Monatsenden vor dem Abschluss, ohne „nichts – Abschluss ganz aufheben“, und schickt nie leer.

#### Festlegungen 1.9.105 (Bitte bestätigen)

1. Feiertage fest für NRW (Vorgabe), aus der Rechnung der Plantafel; die Einstellung „Bundesland“ der Plantafel und betriebsfreie Tage zählen nicht.
2. Auch ein Halbtag (24.12., 31.12.) ist ein Arbeitstag -- gesetzlich kein Feiertag.
3. „Abschluss aufheben“ heißt weiter so (im „⋮“ des Seitenkopfs, nur Admin); zurückgenommen wird auf eines der zwölf Monatsenden davor.
4. Der Server lehnt Zurücknehmen auf einen Tag mitten im Monat ab, Vorrücken auf einen solchen Tag nicht (die Seite rückt nur monatsweise vor,
   Festlegung 1.9.97 Nr. 6; ein Abschluss mitten im Monat aus der Zeit davor lässt sich so weiter auf ein Monatsende zurücknehmen).

#### Tests und Prüfung

Neu `tests/test_v525_arbeitstage_und_aufheben.py`: Arbeitstage (Weihnachten 2026 = 8, Ostern 2027, Fronleichnam, Allerheiligen, Buß- und Bettag nicht in
NRW, ohne Feiertag, Feiertag am Samstag), der Antrag über Weihnachten mit 8 auf Prüfen und Abwesenheiten; ganz aufheben 422, mitten im Monat 422, nichts
geändert, Monatsende 200, Büro – Finanzen 403, vorrücken wie bisher; der Dialog ohne „ganz“. `klicktest_zeiten`: zwölf Monatsenden, ganz aufheben 422.

Angepasste Erwartungen:
- `test_v300::test_backoffice_may_advance_but_only_admin_may_reopen_or_clear`: Admin zurück auf LOCK (heute − 10 Tage) 200 und ganz aufheben 200 -> auf
  LOCK 422 (außer LOCK ist ein Monatsende), auf das Monatsende davor 200, ganz 422.
- `test_v510::test_abschluss_aufheben_nur_der_admin`: Admin ganz aufheben 200 -> 422, auf das Monatsende vor gestern 200.
- `test_v512::test_zuruecknehmen_wird_nicht_geprueft`: zurück auf gestern − 5 Tage 200 und ganz 200 -> auf das Monatsende davor 200 (die laufende Zeit
  zwei Tage davor), ganz 422.
- `klicktest_zeiten` „Admin: Dialog -- Text und gewählt“: letzte Option „nichts – Abschluss ganz aufheben“ -> zwölf Optionen, letzte „31.10.2025“.

Gegenproben (Marker `GEGENPROBE`, byte-genau zurück, je FAILED mit Abweichung im Ergebnis): Arbeitstage ohne Feiertage -> 5 Tests; ganz aufheben
erlaubt -> 1 Test (200 statt 422); zurücknehmen auf jeden Tag -> 1 Test (200 statt 422); der Dialog wieder mit „nichts“ -> 1 Test. Die beiden
Gegenproben am Abschluss liefen zuerst über einen KeyError (die Antwort 200 hat kein `detail`); der Test vergleicht jetzt Status und Meldung
zusammen, dieselben Gegenproben scheitern seither an „200 != 422“.

### R5b Nachrunde, Punkt 7 (1.9.106): Berater- und Mandantennummer für Büro – Finanzen erkennbar nur lesbar

- `settings.html`: `datevBerater`/`datevMandant` für Nicht-Admins `disabled` statt `readonly`; neue Regel `input:disabled,select:disabled,
  textarea:disabled{background:var(--soft);color:var(--muted);cursor:not-allowed}` -- wie die gesperrten Felder auf Auftrag und Checkliste. Bis
  dahin gab die Seite allen Feldern `background:var(--card);color:var(--ink)`, das überdeckte das Grau des Browsers für gesperrte Felder: auch die
  schon gesperrten Felder der Einstellungen (Basiszinssatz, Rechtstexte, Vertragsklauseln und -vorlagen für Nicht-Admins, der Schlüssel eines
  Schichttyps, einer Bauteilart, einer Dokumentkategorie beim Bearbeiten) sahen bearbeitbar aus und sind jetzt ebenso grau.

#### Festlegungen 1.9.106 (Bitte bestätigen)

1. „Nur lesbar“ in den Einstellungen heißt gesperrt (`disabled`) -- wie die übrigen gesperrten Felder dort; der Hinweis „Ändern kann sie nur ein
   Administrator.“ bleibt.
2. Jedes gesperrte Feld der Einstellungen bekommt dieselbe Darstellung (graue Fläche `--soft`, Schrift `--muted`, Mauszeiger „nicht erlaubt“), nicht
   nur die beiden Nummern.

#### Tests und Prüfung

Neu `tests/test_v526_datev_nummern_gesperrt.py` (Büro – Finanzen gesperrt, Admin nicht, nie `readonly`; die Regel für gesperrte Felder).
`klicktest_datev_nummern`: Fin -- gesperrt, Fläche und Schrift anders als ein bearbeitbares Feld (Lohnart Baustelle) und wie `--soft`/`--muted`,
Mauszeiger „nicht-erlaubt“ (Bild).

Angepasste Erwartungen (`klicktest_datev_nummern`): „Ada: Felder leer, bearbeitbar, Knopf da“ und „Fin: Nummern sichtbar, nur lesbar …“ prüfen
`disabled` statt `readOnly` (dasselbe Soll: Admin bearbeitbar, Büro nicht) -- nur der Aufbau.

Gegenproben (Marker `GEGENPROBE`, byte-genau zurück, je FAILED): wieder `readonly` -> 1 Test; ohne Regel für gesperrte Felder -> 1 Test.

## Stufe 4, R5b Nachrunde 2 (ab 1.9.107)

Vorgabe 27.10.2026, Start auf `ceae467`: Festlegungen 1.9.100–1.9.106 bestätigt, außer 1.9.105 Nr. 1 (ersetzt durch Punkt 2). Die Prüfabfrage
`scripts/pruefabfrage_kolonne_weit.sql` ergab auf dem Server a), b) und c) je 0 Zeilen.

### R5b Nachrunde 2, Punkt 1 (1.9.107): die Pause einer Dauer gibt man an

Entscheidung von Tobias zum Befund 3 (1.9.100): „Pause angeben“ -- der Vorschlag von damals, gebaut. Korrektur zum Befund: dort stand für Toms Tag mit
9,5 h Anwesenheit „Pflichtpause 30 min“; die Regeln des Arbeitszeitmodells sind „mehr als 6 h -> 30 min, mehr als 9 h -> 45 min“, für 9,5 h also 45 min
(das Ergebnis „passt“ stimmte, die Dauer trägt 45 min; in der Tabelle oben korrigiert).

**Befund: ein Tag nur aus Dauern.** `pausen_vorschau()` rechnete die Dauern eines Tags zuerst mit ihrer Pause und gab nur den Buchungen mit Uhrzeiten,
was dem Tag noch fehlte; „passt“ hieß „neu rechnen ändert nichts“. Ohne Buchung mit Uhrzeiten ändert neu rechnen nie etwas -- ein Tag nur aus Dauern
passte deshalb immer, auch 8 h ohne Pause; ebenso blieb unbemerkt, was eine zu kurze Buchung mit Uhrzeiten nicht aufnehmen konnte (höchstens ihre
Anwesenheit). „Prüfen“ kann dort nichts abziehen: die Pause steht in der Dauer.

**Lösung.**
- `app/time_tracking.py::pausen_vorschau()` (Rechnung in `_pausen_stand()`): hat der Tag eine Dauer, rechnet `pause_nach_zeitregel(…, deckel=False)` (die
  eine Pausenregel, ohne „höchstens ihre Anwesenheit“) am Ende, was dem ganzen Tag dann noch fehlt -- `fehlt` (Minuten); der Tag passt nur, wenn neu
  rechnen nichts ändert und nichts fehlt. Dazu `noetig` = `nach_zeitregel` + `fehlt`, angezeigt als „nach Zeitregel“ (Prüfen, Meine Zeiten, Abschluss).
  `nach_zeitregel` bleibt, was „So buchen“ ergibt. Ein Tag nur mit Uhrzeiten bleibt, wie er war (Festlegung Nr. 1).
- `dauer_vorschau()` und `kolonne_dauer_vorschau()`: was eine Dauer mit der angegebenen Pause am Tag bewirkt -- anwesend (Stunden + Pause), „Tag
  zusammen“, ob die Pause des Tags danach passt (`_pausen_stand()` mit der gedachten Buchung, nie in die Sitzung gegeben); beim Ändern ohne die alte
  Fassung. Endpunkte `GET /api/time-entries/dauer-vorschau` und `GET /api/time-entry-groups/dauer-vorschau` (Rechte wie das Speichern, die Monteurin 422
  `NUR_VON_BIS`).
- `pausen_neu_rechnen()`: ändert neu rechnen an einem unpassenden Tag nichts, 409 `NICHTS_NEU_ZU_RECHNEN` (bis dahin 409 „inzwischen geändert“).
- `app/zeiten.py::pausen_tage()`: je Tag `fehlt`, `noetig` und, wenn etwas fehlt, die Dauern des Tags als Zeilen wie in „Buchungen“ (`_listenzeilen()`,
  von `buchungen()` mitbenutzt).
- `zeiten.html`: in „Dauer“ beider Dialoge „Pause an diesem Tag (Min.)“ mit „zählt zur Pause des Tags“ (sichtbar, nicht unter „Weitere Angaben“),
  vorbelegt wie bisher; die Vorschau vom Server bei jeder Eingabe (`dauerVorschauHtml()`, `kdDauerHtml()`); die Sätze: „„Dauer“ bucht die Stunden netto;
  die Pause gibst du an.“ und „Mit „Dauer“ entfallen Von und Bis – gespeichert werden die Stunden (netto) und die Pause, die du angibst.“ (Kolonne: „jede
  Person bekommt dieselben Stunden (netto) und die Pause, die du angibst.“). „Prüfen“: `fehltHtml()` -- „Pause angeben“ mit jeder Dauer des Tags und
  „Ändern“ (öffnet „Buchung ändern“), statt „So buchen“; mit Vorschlag zuerst „So buchen“, darunter „Danach fehlen noch …“.
- `mobil_zeiten.html` („Meine Zeiten“): fehlt nur die Pause einer Buchung ohne Uhrzeiten, kein Knopf „Pausen neu rechnen“, sondern der Weg („über „⋮
  Ändern“ Von und Bis eintragen“ bzw. „die Pause trägt das Büro ein“).
- Bestehende Dauern bleiben, wie sie sind: keine Migration, kein Lesen schreibt; was sich ändert, ist nur die Prüfung.

#### Festlegungen 1.9.107 (Bitte bestätigen)

1. „Fehlt“ gibt es nur an einem Tag mit mindestens einer Dauer: die Pflichtpause der Anwesenheit des Tags minus das, was die Regel den Buchungen mit
   Uhrzeiten geben kann. Ein Tag nur mit Uhrzeiten passt wie bisher, wenn die Pausen der Regel entsprechen -- auch wenn eine letzte, kurze Zeit nicht die
   ganze Pflichtpause aufnehmen konnte (sie wird dann ganz Pause, 0 h).
2. Ein Tag, dem die Pause einer Dauer fehlt, ist ein „Tag mit unpassender Pause“ überall: Zahl am Reiter „Prüfen“, „Vor dem Abschluss“, „Monat & Lohn“,
   und er sperrt „Abschließen“ (409). Nach dem Einspielen zeigt „Prüfen“ solche Tage ab dem Tag nach „Abgeschlossen bis“; der Bestand bleibt unverändert.
3. „Prüfen“ zeigt an einem solchen Tag „Pause angeben“ mit jeder Dauer des Tags und „Ändern“ statt „So buchen“; kann neu rechnen einen Teil abziehen,
   steht zuerst der Vorschlag mit „So buchen“, darunter „Danach fehlen noch …“. Büro – Auftrag sieht beides ohne Knöpfe.
4. „Pause an diesem Tag“ ist bei „Ändern“ mit der gespeicherten Pause der Buchung vorbelegt (beim Wechsel von „Von – Bis“ die Pause dieses Abschnitts),
   bei „+ Buchung“ und „Kolonne buchen“ leer (zählt als 0).
5. Die Vorschau einer neuen Dauer rundet nach den Zeitregeln wie das Speichern, die einer geänderten nicht (wie das Speichern); „Tag zusammen“ steht nur bei
   mehr als einer Buchung am Tag (wie bei „Von – Bis“).
6. Die Vorschau einer Dauer lehnt für die Monteurin ab (422 „nur mit Von und Bis“) wie das Speichern; Büro – Auftrag bekommt 403.
7. Neu rechnen an einem Tag, an dem es nichts ändert, lehnt der Server mit eigenem Text ab (409); „Meine Zeiten“ zeigt dort keinen Knopf, sondern wie die
   Pause hineinkommt.
8. Der Satz unter der Vorschau heißt „Dieselbe Regel wie auf dem Tablet. „Dauer“ bucht die Stunden netto; die Pause gibst du an.“ -- „– nur das Büro“
   entfällt (die Seite ist nur fürs Büro).

#### Tests und Prüfung

Neu `tests/test_v527_pause_einer_dauer.py`: Toms 15.10. (Dauer 8,00 mit 0:45 neben der Fahrzeit -> „Tag zusammen 9:30 h“, passt; mit 0 -> passt danach
nicht, gespeichert unter „Prüfen“ mit dem Vorschlag für die Fahrzeit; mit 0:45 gespeichert kein Eintrag); Rundung der neuen Dauer wie das Speichern;
Rechte (Büro – Auftrag 403, Monteurin 422, fremde Buchung 404, 0 h 422); Tag nur aus Dauern (fehlt 30, ohne Vorschlag, die Dauer als Zeile, neu rechnen
409 mit eigenem Text, über „Ändern“ 0:30 -> weg) und der Abschluss (409, „Vor dem Abschluss“); Fahrzeit zu kurz (erst „So buchen“, danach nur „Ändern“);
ein Tag nur mit Uhrzeiten wie bisher; Kolonne mit Dauer je Person (ohne Pause beide nicht, mit 0:30 nur Mia, mit 0:45 beide, gebucht wie die Vorschau)
und ihre Rechte; bestehende Dauern unverändert nach Prüfen, Buchungen, Monat & Lohn, beiden Vorschauen, „tagespause“ und einem abgelehnten Abschluss; in
node die Vorschau des Dialogs, Feld und Sätze, „Prüfen“ (kein „So buchen“, „Ändern“ nur mit Recht, mit Vorschlag beides), die Kolonne und „Meine Zeiten“.
`klicktest_zeiten`: Toms Dauer mit 0:45 („passt“, Bild) und 0 („passt danach nicht“, Bild), Feld und Sätze; „Kolonne buchen“ mit Dauer (ohne Pause /
mit 30); Mia am 20.10. „Dauer“ 8,00 ohne Pause -> „Prüfen“ mit „Pause angeben“ und „Ändern“ (Bild) -> 0:30 -> weg, danach gelöscht.

Angepasste Erwartungen:
- `test_v483::test_reine_dauer_behaelt_ihre_pause`: Kolonnen-Nachtrag 8 h ohne Pause -- passt True -> passt False, `fehlt` 30, `noetig` 30 (der Vorschlag
  bleibt leer, die Pause der Dauer unverändert).
- `test_v518::test_wechsel_zu_dauer_leert_von_bis_und_sagt_es`: Hinweis „… gespeichert wird nur die Dauer (netto), ohne Pausenregel.“ -> „… gespeichert
  werden die Stunden (netto) und die Pause, die du angibst.“
- `test_v518::test_pause_passt_nicht_mit_vorschau_und_so_buchen`: nur der Aufbau -- die Testdaten des Tags um `fehlt`, `noetig`, `dauern` ergänzt (die
  Seite zeigt „nach Zeitregel“ aus `noetig`), `fehltHtml` in der Liste der Funktionen des node-Laufs (im ersten Lauf rot: ReferenceError).
- `test_v508::test_meine_zeiten_seite`: Bedingung des Knopfs „Pausen neu rechnen“ `(t.abgeschlossen||zu?''` -> `(t.abgeschlossen||zu||!plan?''`
  (dasselbe Soll für abgeschlossene Aufträge, dazu ohne Vorschlag kein Knopf).
- `test_v326`: `OHNE_200` und `QUERY_JE_ROUTE` um die beiden neuen Vorschauen ergänzt (die Monteurin bekommt 422 wie beim Speichern) -- neue Einträge,
  keine geänderte Erwartung.
- `klicktest_zeiten` „Fin: Wechsel zu „Dauer“ …“: Hinweis wie oben.

Im ersten Lauf rot und am Code behoben: `test_v462::test_eine_pausenregel_keine_zweite_rechnung` (die Pflichtpause rechnete `_pausen_stand()` zuerst
selbst über das Arbeitszeitmodell -- jetzt über `pause_nach_zeitregel(deckel=False)`, die eine Regel).

Gegenproben (Marker `GEGENPROBE`, byte-genau zurück, je FAILED mit Abweichung im Ergebnis): kein „fehlt“ -> 6 Tests (v527, v483); Vorschau ohne die
angegebene Pause -> 3 Tests; Vorschau beim Ändern mit der alten Fassung -> 2 Tests; neu rechnen ohne die Prüfung „nichts zu rechnen“ -> 1 Test (anderer
Text); Vorschau der Dauer für die Monteurin -> 1 Test; Kolonnen-Vorschau für die Kolonnenführerin -> 1 Test; „Prüfen“ mit dem Vorschlag-Kasten auch ohne
Vorschlag -> 1 Test; „Prüfen“ ohne den Weg zu „Ändern“ -> 1 Test; Dialog „Dauer“ ohne Anfrage -> 1 Test; „Meine Zeiten“ mit „Pausen neu rechnen“ auch
ohne Vorschlag -> 2 Tests (v527, v508). Zwei Gegenproben griffen zuerst nicht: „So buchen“ auch ohne Vorschlag über die Knöpfe blieb grün (ohne Vorschlag
werden die Knöpfe nie gezeichnet -- die Gegenprobe sitzt jetzt am Kasten), die Monteurin scheiterte über einen KeyError (der Test vergleicht jetzt Status
und Meldung zusammen).

### R5b Nachrunde 2, Punkt 2 (1.9.108): Arbeitstage nach dem Bundesland der Plantafel

Vorgabe: „Arbeitstage: Feiertage nach der Einstellung „Bundesland“ der Plantafel (eine Quelle), ohne Einstellung NRW.“ Ersetzt Festlegung 1.9.105
Nr. 1 (fest NRW).

- `app/zeiten.py::feiertage_bundesland()`: das Bundesland aus `PlanningRegionSettings.federal_state_code` (dieselbe Zeile, die die Plantafel liest und
  in ihren Einstellungen ändert), ohne Zeile oder ohne Wert „NW“; nur lesen. `arbeitstage(start, ende, bundesland="NW")` nimmt es als Argument.
- `app/routers/zeiten.py`: „Prüfen“ und „Abwesenheiten“ lesen das Bundesland einmal je Anfrage und geben es an `arbeitstage()`.

#### Festlegungen 1.9.108 (Bitte bestätigen)

1. Quelle der Feiertage ist allein die Einstellung „Bundesland“ der Plantafel; geändert wird sie dort, „Zeiten“ hat keine eigene.
2. „Feiertage automatisch“ der Plantafel aus ändert die Arbeitstage nicht -- gezählt werden die gesetzlichen Feiertage des Bundeslands; eigene Feiertage
   und betriebsfreie Tage der Plantafel zählen nicht.
3. Ohne Einstellungszeile oder ohne Wert gilt Nordrhein-Westfalen.

#### Tests und Prüfung

Neu `tests/test_v528_arbeitstage_bundesland.py`: Mo 04.01.–Fr 08.01.2027 in NRW 5, in Bayern, Baden-Württemberg, Sachsen-Anhalt 4, in Niedersachsen 5;
Toms Antrag auf „Abwesenheiten“ und „Prüfen“ mit Bayern 4, mit NRW 5 (umgestellt über die Funktion der Plantafel); Bayern auch mit „Feiertage
automatisch“ aus; ohne Wert und ohne Zeile NRW. Angepasste Erwartungen: keine.

Gegenproben (Marker `GEGENPROBE`, byte-genau zurück, je FAILED mit Abweichung im Ergebnis): fest NRW -> 2 Tests; „Abwesenheiten“ ohne das Bundesland
-> 2 Tests; „Prüfen“ ohne das Bundesland -> 2 Tests; ohne Rückfall auf NRW -> 1 Test.

### R5b Nachrunde 2, Punkt 3 (1.9.109): Zahl am Reiter „Abwesenheiten“

Vorgabe: „Zahl am Reiter „Abwesenheiten“ wie bei „Prüfen“: nur, was auf das Konto wartet – offene Anträge beim Admin; Büro – Finanzen und Büro –
Auftrag ohne Zahl. „Vor dem Abschluss“ nennt offene Anträge weiter.“

- `app/routers/zeiten.py::zeiten_pruefen()`: `zahlen.abwesenheiten` = offene Anträge nur, wenn das Konto sie entscheidet (`rechte.antraege_entscheiden`,
  der Admin), sonst 0 -- die Seite zeigt dann keine Zahl (`zahlSetzen()`); 1.9.101–1.9.108 die offenen Anträge, die das Konto sieht. „Vor dem
  Abschluss“ und die Karte „Anträge“ auf „Prüfen“ unverändert.
- `offen` in `GET /api/zeiten/abwesenheiten` bleibt die Zahl der offenen Anträge, die das Konto sieht; der Kommentar „dieselbe Zahl wie am Reiter“
  ist korrigiert (die Seite liest das Feld nicht).

#### Festlegungen 1.9.109 (Bitte bestätigen)

1. Die Zahl am Reiter „Abwesenheiten“ zählt beim Admin alle offenen Anträge; Büro – Finanzen und Büro – Auftrag sehen keine Zahl -- auch nicht für einen
   eigenen offenen Antrag (er wartet auf den Admin).
2. Für Büro – Finanzen bleibt der offene Antrag sichtbar: auf „Prüfen“ (Karte „Anträge“, ohne Knöpfe), auf „Abwesenheiten“ und unter „Vor dem
   Abschluss“; nur die Zahl entfällt.
3. `offen` in `GET /api/zeiten/abwesenheiten` bleibt „offene Anträge, die das Konto sieht“ -- nicht die Zahl am Reiter.

#### Tests und Prüfung

Neu `tests/test_v529_zahl_abwesenheiten.py`: ein offener Antrag -- Admin Zahl 1, Büro – Finanzen 0 mit dem Antrag auf „Prüfen“ und unter „Vor dem
Abschluss“, Büro – Auftrag 0 ohne ihn; ein eigener offener Antrag von Büro – Auftrag: 0, unter „Vor dem Abschluss“, beim Admin 1; ohne Antrag 0.
`klicktest_zeiten`: Büro – Finanzen stellt „Krank“ für Tom -- keine Zahl am Reiter (Bild), „Vor dem Abschluss“ nennt „1 Antrag offen“; der Admin sieht
„1“ (wie bisher, Bild).

Angepasste Erwartungen:
- `test_v517::test_pruefen_antraege_je_konto`: Büro – Finanzen `zahlen.abwesenheiten` 1 -> 0.
- `test_v523::test_zahl_antraege_und_vor_dem_abschluss_je_konto`: Büro – Finanzen `zahlen.abwesenheiten` 1 -> 0.
- `klicktest_zeiten` „Fin: „Krank“ für Tom gestellt -- …, Zahl am Reiter 1“ -> „…, keine Zahl am Reiter“ (die Zahl verborgen); neu „Fin: „Vor dem
  Abschluss“ nennt den offenen Antrag“.

Gegenproben (Marker `GEGENPROBE`, byte-genau zurück, je FAILED mit Abweichung im Ergebnis): die Zahl wie 1.9.101–1.9.108 -> 4 Tests (v529, v517, v523);
die Zahl nie, auch nicht beim Admin -> 3 Tests (v529, v517).

### R5b Nachrunde 2, Punkt 4 (1.9.110): gesperrte Felder im Dunkeln

Vorgabe: „Dunkel: gesperrte Felder erkennbar wie hell (heute #222A2F auf #1A2024 kaum zu sehen).“

**Befund.** Seit 1.9.106 tragen gesperrte Felder der Einstellungen die Fläche `--soft` (= `--ds-flaeche-2`), ebenso schon vorher Checkliste,
Checklisten-Vorlage, der Positionsdialog des Auftrags und die nur lesbaren Felder des Stammdaten-Formulars. Gemessen (CIELAB L*, Abstand der Feldfläche
zur Fläche der Karte): hell 3,6 (#F3F5F6 auf #FFFFFF), dunkel 4,7 (#222A2F auf #1A2024) -- dunkel rechnerisch sogar mehr, auf dem Bildschirm aber kaum zu
sehen; dazu ist dunkel auch der Unterschied der Schrift kleiner (text-2 #BAC3C9 statt text #E9EDEF).

- `app/static/ds/ds.css`: neues Token `--ds-feld-gesperrt` -- hell #F3F5F6 (wie flaeche-2, hell bleibt alles, wie es war), dunkel #2B3339 (L*-Abstand
  8,9); neues Prüfpaar `text-2/feld-gesperrt` (hell 6,97 : 1, dunkel 7,18 : 1).
- `settings.html`, `checklist.html`, `checklist_template.html`, `order.html` (`#itemDialog`, `#taxKey`), `master_data_form.html` (`input[readonly]`): die
  Fläche gesperrter bzw. nur lesbarer Felder `var(--ds-feld-gesperrt)` statt `var(--soft)`; die Schrift bleibt je Seite, wie sie war.

#### Festlegungen 1.9.110 (Bitte bestätigen)

1. Maß für „erkennbar wie hell“: dunkel mindestens doppelt so großer Helligkeitsabstand (CIELAB L*) zwischen Feldfläche und Karte wie hell -- gewählt
   #2B3339 (8,9 gegen 3,6 hell; bis 1.9.109 4,7).
2. Hell ändert sich nichts (`--ds-feld-gesperrt` hell = flaeche-2).
3. Gilt für jede Seite, die gesperrte oder nur lesbare Felder mit eigener Fläche zeigt (fünf Seiten, Liste oben), nicht nur für die Einstellungen;
   Wächter: keine Regel für gesperrte oder nur lesbare Felder mit `--soft` in einer Vorlage.
4. Der Rahmen gesperrter Felder bleibt `feld-rand` (dunkel 2,92 : 1 auf der neuen Fläche; für gesperrte Felder verlangt WCAG keinen Kontrast).

#### Tests und Prüfung

Neu `tests/test_v530_gesperrte_felder_dunkel.py`: hell unverändert, dunkel doppelter L*-Abstand (Gegenprobe im Test: #222A2F erfüllt es nicht); die
fünf Seiten nehmen das Token; Wächter über alle Vorlagen ohne `--soft` an gesperrten Feldern. `klicktest_datev_nummern`: Büro – Finanzen zuerst
ausdrücklich hell (Fläche rgb(243, 245, 246)), dann dunkel (rgb(43, 51, 57), anders als die Karte und das bearbeitbare Feld, Bild).

Angepasste Erwartungen:
- `test_v432::test_kontrast_der_pruefpaare_hell_und_dunkel`: 47 -> 48 Prüfpaare, neu `text-2/feld-gesperrt`.
- `test_v526::test_gesperrte_felder_der_einstellungen_grau`: Regel mit `background:var(--soft)` -> `background:var(--ds-feld-gesperrt)`.
- `klicktest_datev_nummern` „Fin: erkennbar nur lesbar …“: Fläche wie `--soft` -> wie `--ds-feld-gesperrt`, dazu der Farbwert; der Teil läuft jetzt
  ausdrücklich hell (bis 1.9.109 im Thema der Vorgabe, dunkel -- im ersten Lauf rot, weil dort schon die dunkle Fläche kam); neu der dunkle Teil. Das
  Bild `einstellungen_datev_nummern_buero` ist dadurch hell, neu `…_buero_dunkel`.

Gegenproben (Marker `GEGENPROBE`, byte-genau zurück, je FAILED mit Abweichung im Ergebnis): dunkel wieder #222A2F -> 1 Test; Einstellungen wieder
`--soft` -> 3 Tests (v530, v526); Auftrag wieder `--soft` -> 2 Tests; Stammdaten-Formular wieder `--soft` -> 2 Tests.

Offen (nicht untersucht): Seiten, die ein Eingabefeld sperren, ohne eine eigene Regel für gesperrte Felder zu haben, zeigen es je nach eigener
Feldfläche wie ein bearbeitbares (so die Einstellungen bis 1.9.106). Eine grobe Suche nennt 23 Vorlagen mit gesperrten Elementen und eigener Feldfläche,
überwiegend Knöpfe -- eine Durchsicht je Seite steht aus.

## Stufe 5, R1 (ab 1.9.111): Fundament (ohne neues Aussehen)

Vorgabe 28.10.2026, Start auf `47e3d17` (1.9.110): Befund Stufe 5 (Auftragsakte, `bildgrundlage/bericht_stufe5_befund_auftragsakte_47e3d17.txt`)
gelesen. Entscheidungen Tobias: eine Akte je Projekt -- Projektmappe und Auftrag werden eine Seite (R2); mit Geld arbeiten nur Admin und Büro –
Finanzen. R1 legt das Fundament ohne neues Aussehen: Rechte am Geld, Befund im fremden Bericht, eine Zeitbuchung statt drei, Sperren an Storno und
Schlussrechnung, Änderungsprotokoll, keine verlorenen Eingaben, Mustervorgang und Projekt löschen, lesbare Fehler. Die Kürzel F…, D…, E…, B… sind die
Nummern des Befunds (Abschnitt 6).

### R1, Punkt 1 (1.9.111): Rechte am Geld

Eine Regel in `app/permissions.py`: `darf_geld()` (Admin, Büro – Finanzen; ohne Konto wie die anderen Regeln ohne Einschränkung), dazu `require_geld`
(403 `GELD_NUR_LESEN`: „Rechnungen, Zahlungen und Mahnungen bearbeiten Admin und Büro – Finanzen – du kannst sie lesen.“).

| Recht | Wer | Wo |
|---|---|---|
| Rechnung anlegen (alle vier Arten), Kopf, Zahlungsbedingung, Steuerschlüssel, Positionen, „Aus dem Auftrag aktualisieren“, Finalisieren, E-Mail, Storno, Entwurf löschen | Admin, Büro – Finanzen (bis 1.9.110 jedes Büro) | `app/routers/invoices.py`, 15 Endpunkte, `_geld_dep` |
| Zahlung buchen, Rest zuordnen, Zahlung und Zuordnung zurücknehmen, Erstattung (Rechnung, Kunde) | dieselben | `app/routers/payments.py`, 6 Endpunkte |
| Mahnung anlegen (einzeln, Auswahl), bearbeiten, Nebenforderungen übernehmen, festschreiben, E-Mail, löschen | dieselben | `app/routers/reminders.py`, 7 Endpunkte |
| Verzugsbeginn bestätigen und verwerfen, Nebenforderung gegenbuchen | dieselben | `app/routers/dunning_charges.py`, 3 Endpunkte |
| Zustellung nachtragen, Empfang bestätigt/unzustellbar, hängenden Versand klären -- an Rechnung und Mahnung (`GELD_DOKUMENTE`) | dieselben; an jedem anderen Dokument unverändert ab Büro – Auftrag | `app/routers/email_dispatches.py::_require_geld_for()`; die Liste meldet je Eintrag `can_resolve`, `can_record_outcome` |
| alles lesen (Rechnungen, Zahlungen, Mahnungen, Nebenforderungen, Versand, PDF) | jedes Büro | unverändert |
| Mahnstufen in den Einstellungen | unverändert ab Büro – Auftrag | Festlegung Nr. 1 |

Oberfläche: die Seitenrouten von Auftrag, Rechnung, Kundenakte und Mahnwesen geben `geld` (= `darf_geld()`) und `geld_nur_lesen` mit; die Seite
setzt `const GELD="ja"|"nein"!=="nein"` (auch ungerendert gültiges JS -- die node-Tests lesen die Vorlage roh) und zeichnet ohne Geld den Hinweis
(`data-geld-nur-lesen`) statt der Knöpfe:
- Auftrag: statt „Neue Rechnung“ der Hinweis (nicht im Markup), kein „Löschen“ am Rechnungsentwurf.
- Rechnung: `bearbeitbar()` = `GELD && invoice.is_editable` für jedes Feld und jeden Knopf (Pauschalbetrag, Kopf, Leistungszeitraum samt
  „Übernehmen“, Positionen, „+ Position“, Mengenvergleich der Schlussrechnung); Karte „Status“ ohne Knöpfe (die Info bleibt), Versandverlauf ohne
  Nachtragen und Ergebnis; Zahlungen ohne „Zahlungseingang buchen“, Erstattung, Gegenbuchen; Nebenforderungen ohne Bestätigen/Verwerfen/Gegenbuchen
  (der Vorschlag des Verzugsbeginns als Text); Mahnungen ohne Anlegen, Festschreiben, Bearbeiten, Löschen (PDF bleibt).
- Kundenakte: Guthaben ohne Eingabe „davon erstatten“ und ohne „Erstattung buchen“, Zahlungen ohne Zuordnen und Zurücknehmen, Hinweis in der Karte.
- Mahnwesen: ohne Auswahl und „Entwürfe für Auswahl anlegen“ (nicht im Markup), ohne „als Entwurf anlegen“, „Durch neue ersetzen“, Festschreiben,
  Bearbeiten, Löschen, E-Mail; Verlauf ohne Nachtragen.
- Versandprotokoll: ein hängender Eintrag an Rechnung oder Mahnung ohne Klären-Formular („klären können Admin und Büro – Finanzen“).
Projektmappe und Finanzen hatten keine Geld-Knöpfe -- unverändert.

#### Festlegungen 1.9.111 (Nr. 2–4 und 6 bestätigt am 28.10.2026; Nr. 1 und 5 ersetzt durch die Nachrunde, Punkt 2 -- 1.9.120)

1. Die Mahnstufen in den Einstellungen (Bezeichnung, Zahlungsfrist, Gebühr, Text, Mahn-E-Mail-Vorlagen; `PUT /api/reminder-levels/{id}`) speichert
   weiter jedes Büro -- keine Mahnung, keine Buchung. Schalter Mahngebühren, Basiszinssatz und Rechtstexte bleiben nur Admin.
2. Zum Versenden gehören an Rechnung und Mahnung auch „Zustellung nachtragen“, „Empfang bestätigt / unzustellbar“ und das Klären eines hängenden
   Versands; an allen anderen Dokumenten (Angebot, Auftrag, Vertrag, Checkliste, Briefe) bleiben sie ab Büro – Auftrag.
3. Büro – Auftrag sieht an einem Mahnungsentwurf weiter das PDF und den Grund einer Sperre; Rechnungs- und Mahnungs-PDF bleiben lesbar.
4. Lesende Vorschauen bleiben jedem Büro: Zahlungsvorschlag (`GET …/payment-proposal`), Empfängerauswahl der Zustellung, „zur Mahnung fällig“.
5. Zahlungsbedingungen, Steuerschlüssel und Nummernkreise in den Einstellungen unverändert (keine Aktion an einem Beleg).
6. Der Kundenwechsel am Projekt mit Auftrag (stellt Rechnungsentwürfe mit um, mit Begründung) bleibt eine Aktion der Projektmappe ab Büro – Auftrag.

#### Tests und Prüfung

Neu `tests/test_v531_rechte_geld.py`: Regel je Rolle; Struktur über jede Route der vier Geld-Router mit einer anderen Methode als GET (Rollen höchstens
Admin und Büro – Finanzen, nur die Mahnstufen ausgenommen); Rundgang über alle 34 schreibenden Geld-Aktionen (die 15 Rechnungs-Szenarien aus
`test_v378`, 6 Zahlungen, 7 Mahnwesen, 3 Nebenforderungen, 3 Versandprotokoll) -- vorbereitet als Admin, dann als Büro – Auftrag je 403 mit
`GELD_NUR_LESEN` und jede Zeile aller Geld-Tabellen unverändert, als Büro – Finanzen und Admin je 200 und geschrieben; Zustellung eines Auftrags
als Büro – Auftrag weiter 200 (Grenze der Regel); Büro – Auftrag liest 13 Lese-Endpunkte, die Liste des Versandprotokolls meldet je Eintrag
`can_resolve`/`can_record_outcome`; die Seitenrouten zeichnen `GELD` und Hinweis je Rolle, ohne Geld kein „Neue Rechnung“, keine Auswahl im
Mahnwesen; jede Stelle der Skripte, die eine Geld-Aktion anbietet, fragt `GELD` bzw. `bearbeitbar()`.
Neu `scripts/klicktest_rechte_geld.py` (23 Prüfungen): Büro – Auftrag auf Auftrag, Rechnung (Entwurf und festgeschrieben), Kundenakte, Mahnwesen,
Versandprotokoll ohne Knöpfe, mit allem Gelesenen, Angriff aus der Seite 403; Büro – Finanzen mit allen Knöpfen, finalisiert.

Angepasste Erwartungen (Büro – Auftrag -> Büro – Finanzen, wo der Test Geld bewegt; wo nicht anders gesagt nur der Aufbau):
- `test_v323::test_office_resolves_stuck_entry_with_note_and_history[gesendet|fehlgeschlagen]`: klärt als Büro – Auftrag („Buero_auftrag“) -> als
  Büro – Finanzen („Buero_finanzen“).
- `test_v323::test_resolution_is_refused_where_it_does_not_belong`: Prüfungen als Büro – Finanzen; neu: Büro – Auftrag 403 an der Rechnung.
- `test_v321::test_same_key_twice_through_the_api`, `test_v373::test_invoice_item_only_from_the_order_of_the_invoice`,
  `test_v386::test_the_routes_for_addenda`, `test_v386::test_the_finalize_route_answers_409_for_a_negative_progress_invoice`,
  `test_v385::test_a_manual_delivery_refers_to_the_fixed_pdf`, `test_v385::test_the_finalize_route_answers_400_without_a_fixed_pdf`: Büro – Auftrag
  -> Büro – Finanzen.
- `test_v324`: die sieben Tests der Zustellung an einer Rechnung (`test_manual_delivery_lands_in_log_and_archive`, `…_uses_the_archived_version…`,
  `test_invalid_manual_delivery_writes_nothing[5]`, `test_too_large_receipt_is_rejected`, `test_manual_entry_is_unchangeable`,
  `test_history_of_a_document_shows_email_and_manual_deliveries`, `test_manual_delivery_rights_and_documents`) -> Büro – Finanzen; im letzten neu:
  Büro – Auftrag 403.
- `test_v397::test_customer_page_shows_the_reason_instead_of_the_button`: die Zeile `GELD` der Seite in den node-Lauf aufgenommen (im ersten Lauf
  rot: ReferenceError).
- Klicktests, Büro-Konto Büro – Auftrag -> Büro – Finanzen: `klicktest_endrechnung`, `klicktest_mahnen_endrechnung`, `klicktest_mahnwesen`,
  `klicktest_nachtrag`, `klicktest_nebenforderungen`, `klicktest_rechnungen_sperren`, `klicktest_ueberzahlung`, `klicktest_versandprotokoll`,
  `klicktest_versandverlauf`, `klicktest_vertrag_abschrift`, `klicktest_verzugszinsen`, `klicktest_zahlungen`, `klicktest_zahlungen_kleinkram`
  (im ersten Lauf rot, alle an einer Geld-Aktion).
- `klicktest_zeitbuchungen_liste` „Auftrag: Rechnung aus Aufwand“ als Karl (Büro – Auftrag) -> als Anna (Admin); neu: Karl sieht den Hinweis statt
  „Neue Rechnung“ (20 -> 21 Prüfungen).

Im ersten Lauf rot und an der Seite behoben: `test_v407::test_keine_werte_in_on_attributen` (zwei zusätzliche onclick-Stellen für das PDF einer
Mahnung im Mahnwesen -- jetzt eine Stelle wie bisher, die anderen Knöpfe nur mit `GELD`), `test_v333::test_auftragsseite_…` (die Zeile `GELD`
war ungerendert kein gültiges JS -- seitdem `"{{ … }}"!=="nein"`).

Gegenproben (Marker `GEGENPROBE`, byte-genau zurück, Prüfsumme verglichen, je FAILED): Büro – Auftrag in `GELD_ROLLEN` -> 37 Tests rot (34 Szenarien,
Regel, Liste, Seiten); „Zustellung nachtragen“ ohne `_require_geld_for()` -> 1 Test rot.

### R1, Punkt 2 (1.9.112): Befund im Bericht jeder Person, „Durchgeführt von“

Befund F1: die Berichtsseite schickte beim Anlegen eines Befunds `created_by_employee_id` = Ersteller des Berichts mit; der Server
(`_employee_for_request()`) ließ eine fremde Person nur dem Admin -- Büro – Finanzen und Büro – Auftrag bekamen 403, der Admin schrieb den Befund still
der Monteurin zu. Ebenso bot „Durchgeführt von“ beim Anlegen eines Berichts allen Rollen alle Mitarbeiter an (403 bei einer fremden Person).

- „Erfasst von“ ist das anlegende Konto: `app/routers/findings.py::post_finding()` setzt `created_by_user_id`, `created_by_name` (Anzeigename) und
  `created_by_employee_id` (Mitarbeiter des Kontos, sonst leer) aus der Anmeldung, für jede Rolle; „geschlossen von“ bei „sofort behoben“ wie seit
  1.8.70 das Konto. `FindingCreate` lehnt `created_by_employee_id` mit 422 ab (wie `FindingFollowupUpdate` „geschlossen von“). Migration
  `3e9b7c41d2a8`: zwei leere Spalten an `findings` (ohne Fremdschlüssel wie `email_dispatches.created_by_user_id`); `downgrade()` verweigert, solange
  ein Befund ein Konto trägt.
- Ausgabe `created_by_name`: das Konto, bei Befunden von vor 1.9.112 der Name des Mitarbeiters. Die Befundkarte im Einsatzbericht zeigt
  „· erfasst von …“.
- „Durchgeführt von“: die Regel steht jetzt in `app/permissions.py::darf_fuer_andere_erfassen()` (nur Admin, dieselbe wie seit 1.3.0, bis dahin in
  `_employee_for_request()`); die Seitenroute von „Einsatzberichte“ gibt sie mit, `durchgefuehrtVonOptionen()` bietet dem Admin jede Person, jedem
  anderen Konto „— nicht zugeordnet —“ und sich selbst (vorgewählt).

#### Festlegungen 1.9.112 (Nr. 1, 2 und 4 bestätigt am 28.10.2026; Nr. 3 ersetzt durch die Nachrunde, Punkt 3 -- 1.9.121)

1. „Erfasst von“ eines Befunds ist für jede Rolle das anlegende Konto -- auch der Admin schreibt einen Befund keiner anderen Person mehr zu; ein Konto
   ohne Mitarbeiter hinterlässt Name und Konto, keinen Mitarbeiter.
2. Wer „erfasst von“ beim Anlegen mitschickt, bekommt 422 (auch der Admin), statt dass der Wert still verworfen wird.
3. „Durchgeführt von“ eines Berichts bleibt eine Mitarbeiterwahl (nicht das Konto); Büro – Finanzen darf dort -- anders als bei den Zeiten -- weiter nur
   sich selbst wählen (die Regel von 1.3.0 unverändert, nur sichtbar gemacht).
4. Bestehende Befunde bleiben, wie sie sind (keine Datenübernahme in die neuen Spalten); sie nennen ihren Mitarbeiter.

#### Tests und Prüfung

Neu `tests/test_v532_befund_im_fremden_bericht.py`: Büro – Finanzen und Büro – Auftrag (mit Mitarbeiter) legen im Bericht der Monteurin einen Befund
an (200, Konto, Name und Mitarbeiter des Büros, nicht Mia); der Admin ohne Mitarbeiter („Ada Admin“, kein Mitarbeiter); die Monteurin im eigenen Bericht
(sie selbst, „sofort behoben“ von ihr geschlossen); „erfasst von“ mitgeschickt 422 für Admin, Büro und Monteurin, nichts angelegt; ein Befund von vor
1.9.112 nennt seinen Mitarbeiter; „Durchgeführt von“ Regel und Server je Rolle (fremde Person nur Admin 200, sonst 403; eigene 200); in node auf der
vom Server gezeichneten Seite die Optionen je Rolle; die Berichtsseite schickt kein „erfasst von“ und zeigt es.
Neu `tests/test_v532_befund_erfasst_von_migration.py`: Migration `3e9b7c41d2a8` auf einem Bestand mit Befund (SQLite und PostgreSQL im
Wegwerf-Schema): hoch -- Befund unverändert, Spalten leer; runter -- exakt wie vorher; mit Konto -- Rückweg verweigert, nichts geändert.
Neu `scripts/klicktest_befund_fremder_bericht.py` (10 Prüfungen): Bernd (Büro – Finanzen) legt im Bericht von Mia einen Befund an, Karte „erfasst von
Bernd Büro“, Server Konto und Mitarbeiter Bernd (Bild); Admin „Ada Admin“ ohne Mitarbeiter; Mia sieht beide; „Durchgeführt von“ je Rolle.

Angepasste Erwartungen:
- `test_v373::test_closed_by_is_set_from_the_login` -- der Admin legte einen Befund mit `created_by_employee_id` des Kollegen an (200, Ersteller der
  Kollege) -> mitgeschickt 422, ohne Angabe 200 mit „erfasst von“ = Admin (kein Mitarbeiter), „geschlossen von“ wie bisher.
- `test_v224::test_non_admin_cannot_set_foreign_employee_id_on_create_finding` -- fremde Person: 403 im Endpunkt -> das Schema lehnt ab (über die API
  422), ohne Angabe der eigene Mitarbeiter; `post_finding()` ohne `request` (im ersten Lauf rot).

Gegenproben (Marker `GEGENPROBE`, byte-genau zurück, je FAILED): „erfasst von“ wieder der Ersteller des Berichts -> 3 Tests; das Schema nimmt
`created_by_employee_id` wieder an -> 4 Tests (v532, v373); „Durchgeführt von“ allen alle -> 2 Tests (die beiden Büro-Rollen). Eine erste Gegenprobe griff
aus dem falschen Grund (Name im Router nicht importiert, 500) -- wiederholt mit dem Import im Ausdruck.

### R1, Punkt 3 (1.9.113): „Einsatzberichte“ bucht über den Dialog von „Zeiten“

Befund F3/D14: drei Buchungsformulare mit verschiedenen Regeln -- „Einsatzberichte“ (Büro, eine Dauer ohne Pause und ohne Vorschau), „Zeiten“ (Pause des
Tags und Vorschau seit 1.9.107), „Meine Zeiten“ (nur Von/Bis). Vorgabe: „Einsatzberichte“ bucht keine eigene Dauer mehr, der Knopf öffnet den Dialog von
„Zeiten“ mit dem Auftrag vorbelegt.

- `service_reports.html`: die Felder zum Buchen (Mitarbeiter, Datum, Zeitart, Tätigkeit, LV-Position, Stunden bzw. Von/Bis, Notiz) und ihr Skript
  (`saveReportTimeEntry()`, `zeitMitarbeiterOptionen()`, `refreshTimeEntryOrderItemOptions()`, das Laden von Zeitarten und Tätigkeiten) sind weg; die
  Karte „Erfasste Zeiten“ zeigt die Zeiten wie bisher, wer bucht (`darf_zeit_buchen()`, Admin und Büro – Finanzen), dazu „Zeit buchen“ -- ein Link auf
  `/zeiten?auftrag=<id>&buchung=neu#buchungen`; Büro – Auftrag der Hinweis wie seit 1.9.89. Der Monteursrahmen erkennt die Seite jetzt an der Karte „Zeiten“
  der Monteurin (`#zeitenKarte`, bis 1.9.112 an `#teHours`).
- `zeiten.html::binden()`: `?buchung=neu` öffnet „Neue Buchung“ -- nur, wenn es „+ Buchung“ gibt (wer bucht) --, auf dem Reiter „Buchungen“; der Auftrag
  kommt aus `?auftrag=` (`FILTER.auftrag`, wie bisher die Vorwahl des Dialogs); `buchung` wird aus der Adresse gestrichen (Neuladen öffnet nicht noch einmal).
- Server unverändert: gebucht wird über `POST /api/time-entries` mit der Pausenregel des Tags, die Vorschau über `GET /api/time-entries/dauer-vorschau`.

#### Festlegungen 1.9.113 (bestätigt am 28.10.2026)

1. „Zeit buchen“ ist ein Link auf „Zeiten“ (die Seite wechselt), kein Dialog auf „Einsatzberichte“ -- ein Dialog an einer Stelle; nach dem Speichern bleibt
   man auf „Zeiten“ (Reiter „Buchungen“, gefiltert auf den Auftrag), zurück über den Pfad bzw. den Browser.
2. Der Dialog öffnet für einen neuen Eintrag mit dem Datum heute und ohne Mitarbeiter (wie „+ Buchung“); die Mitarbeiterwahl bleibt dem Dialog.
3. `?buchung=neu` ohne Recht zum Buchen (Büro – Auftrag) öffnet nichts und meldet nichts.

#### Tests und Prüfung

Neu `tests/test_v533_einsatzberichte_zeit_ueber_zeiten.py`: die Karte je Rolle (Admin und Büro – Finanzen „Zeit buchen“ mit dem Link, keine Felder zum
Buchen; Büro – Auftrag der Hinweis; Monteurin „Zeit nachtragen“); `binden()` öffnet „Neue Buchung“ nur mit `?buchung=neu` und „+ Buchung“, der Auftrag
aus `?auftrag=`; die Vorschau des Dialogs vom Server: 8 h Dauer ohne Pause -> passt nicht, mit 30 min -> passt.
Neu `scripts/klicktest_zeit_aus_einsatzberichte.py` (11 Prüfungen): Büro – Finanzen klickt „Zeit buchen“ -> „Neue Buchung“ auf „Zeiten“ mit dem
Auftrag, `?buchung=neu` gestrichen; Mia, „Dauer“ 8,00 ohne Pause -> „Pause des Tags passt danach nicht“ (Bild), mit 30 -> passt, gespeichert, auf
„Einsatzberichte“ 8,00 h; Büro – Auftrag ohne „Zeit buchen“, `?buchung=neu` öffnet nichts.

Angepasste Erwartungen:
- `test_v424` (`ABGLEICH`): der Eintrag `service_reports.html id=teHours` entfällt (das Feld gibt es nicht mehr).
- `test_v485::test_einsatzbericht_monteurin_ohne_buchungskarte`: Büro – Finanzen sieht „Stunden“, Von/Bis verborgen -> keine Felder zum Buchen, der Link
  „Zeit buchen“.
- `test_v437::test_einsatzbericht_bietet_nur_an_was_der_server_annimmt[admin|buero_finanzen|buero_auftrag]`: Auswahl „Mitarbeiter“ und Buchung über die
  Seite -> die Seite bucht nicht (keine Funktion, kein POST); der Server unverändert (Buchung für Max: Admin und Büro – Finanzen 200, Büro – Auftrag 403).
- `test_v437::test_einsatzbericht_mitarbeiterfeld_im_markup_nur_wer_fuer_andere_bucht[4 Rollen]` -> umbenannt in
  `test_einsatzbericht_zeit_buchen_im_markup_nur_wer_bucht`: Feld „Mitarbeiter“ verborgen/sichtbar -> „Zeit buchen“ nur Admin und Büro – Finanzen,
  Hinweis für Büro – Auftrag, „Zeit nachtragen“ für die Monteurin.
- `klicktest_bericht_schritte` „Büro: Buchungskarte unverändert“ -> „Büro: „Zeit buchen“ statt Buchungskarte“.
- `klicktest_einsatzbericht_zeiten` „Zeit gebucht“: über das Formular der Seite („Gebucht.“) -> über die Schnittstelle (200), der Rest unverändert.
- `klicktest_monteur_dachflaechen`: Büro – Finanzen und Admin mit Auswahl „Mitarbeiter“, gebucht über das Formular -> „Zeit buchen“ (Link), für Max
  über die Schnittstelle gebucht; Büro – Auftrag ohne Link statt verborgener Felder (14 -> 12 Prüfungen).
- `test_v447` (`KLASSEN`): der Eintrag `service_reports.html P1 o.value===selected` (Zeitart und Tätigkeit der Buchung) entfällt; `test_v440::
  test_keine_eigene_fassung_der_meldung`: die Seiten mit der Meldung „Konto ohne Mitarbeiter“ ohne `service_reports.html` (im ersten Lauf der Suite rot,
  beide Listen dürfen nur kürzer werden).

Im ersten Lauf rot und behoben: `klicktest_zeiten` (104/118) -- der Klicktest lädt `/zeiten?neu=1#…` neu (Trick gegen „gleiche Adresse lädt nicht
neu“); der Schalter hieß zuerst ebenfalls `?neu=1` und öffnete dort den Dialog. Seitdem `?buchung=neu`.

Gegenproben (Marker `GEGENPROBE`, byte-genau zurück, je FAILED): „Zeit buchen“ auch für Büro – Auftrag -> 2 Tests (v533, v437); `binden()` öffnet den
Dialog auch ohne „+ Buchung“ -> 1 Test.

### R1, Punkt 4 (1.9.114): Storno-Entwurf und Schlussrechnung -- Positionen gesperrt

Vorgabe: „erst mit einem Test zeigen, dann sperren“. Der Test `tests/test_v534_storno_und_schluss_positionen.py` lief zuerst ohne die Sperre (auf dem
Code von 1.9.110 für Rechnungen, 28.10.2026) und war rot (4 von 5) -- der Beleg:
- Storno-Entwurf eines Abschlags nach Leistungsstand (40 m² × 50 € = 2.000,00 € netto): `PUT …/items/{id}` mit Ist 7 -> 200, die Position rechnete
  danach −33 m² und −1.650,00 €, der Storno lautete netto −1.650,00 € statt −2.000,00 € (er hebt seine Rechnung nicht mehr auf -- der Test brach dort
  ab, Kurztext und Entfernen wurden nicht mehr versucht); `add_invoice_item()` legte am Storno eine weitere Position an.
- Schlussrechnung: `DELETE` einer Position des Auftrags -> 200; danach `finalize_block` „Der Entwurf weicht vom Auftrag ab: es fehlen Positionen des
  Auftrags (1). …“ -- bis „Aus dem Auftrag aktualisieren“ sie wieder einfügte.

Sperre (unter der Sperre der Auftragszeile wie jeder Schreibweg einer Rechnung, `_lock_draft()`):
- `app/invoices.py`: `add_invoice_item()`, `update_invoice_item()`, `remove_invoice_item()` lehnen am Storno mit `InvoiceBlocked(STORNO_POSITION_TEXT)`
  ab (409, nichts geändert); `remove_invoice_item()` an der Schlussrechnung eine Position mit Auftragsbezug mit `SCHLUSS_POSITION_TEXT` (409). „Aus dem
  Auftrag aktualisieren“ am Storno war schon gesperrt (seit 1.8.85).
- `invoice_detail.html`: `positionBearbeitbar()` (bearbeitbar und kein Storno) für Ist-Feld und „✎“, `positionEntfernbar(i)` zusätzlich nicht an einer
  Position des Auftrags in der Schlussrechnung für „✕“ -- in der Liste und im Mengenvergleich der Schlussrechnung.

#### Festlegungen 1.9.114 (bestätigt am 28.10.2026)

1. Am Storno-Entwurf bleiben Kopf (Einleitung, Schlusstexte), Leistungszeitraum, Finalisieren und „Entwurf löschen“ -- gesperrt sind nur die Positionen;
   wer eine andere Storno-Fassung braucht, löscht den Entwurf und legt ihn neu an.
2. In der Schlussrechnung bleibt eine Position des Auftrags drin; „nicht abrechnen“ heißt Ist-Menge 0. Eine Position ohne Auftragsbezug gibt es dort ohnehin
   nicht (seit 1.8.83).
3. Abschläge nach Leistungsstand behalten „✕“ (eine Position des Auftrags darf dort fehlen -- der Abschlag rechnet nur, was drinsteht).

#### Tests und Prüfung

Neu `tests/test_v534_storno_und_schluss_positionen.py` (vor der Sperre 4 von 5 rot, siehe oben): Storno-Position ändern (Ist, Kurztext) und entfernen ->
409 mit „Storno“, Positionen und Summe unverändert, Summe = Gegenbetrag der Rechnung; Position am Storno hinzufügen -> `InvoiceBlocked`; Schlussrechnung:
Position des Auftrags entfernen -> 409, Ist 0 weiter 200; Gegenprobe Abschlag nach Leistungsstand (Ist ändern und entfernen 200); die Seite fragt
`positionBearbeitbar()`/`positionEntfernbar(i)`.
Neu `scripts/klicktest_storno_positionen.py` (8 Prüfungen): Storno-Entwurf ohne Ist-Feld, „✎“ und „✕“, mit Finalisieren und „Entwurf löschen“, Angriff
aus der Seite 409, Summe bleibt −2.000,00 € (Bild); Schlussrechnung mit Ist-Feld und „✎“, ohne „✕“, `DELETE` 409; Abschlag mit „✕“.

Angepasste Erwartungen:
- `test_v378::test_editing_a_draft_still_works[position_entfernen]`: an der Schlussrechnung -> am Abschlag nach Leistungsstand; ebenso das Szenario
  `DELETE …/items/{item_id}` im Rundgang von `test_v378` (und damit in `test_v531`): Entwurf einer Schlussrechnung -> eines Abschlags nach Leistungsstand.
- `test_v133::test_remove_invoice_item`: Schlussrechnung -> Abschlag nach Leistungsstand.
- `test_v386::test_a_free_position_is_rejected_outside_time_based_invoices[storno]`: Grund `FREE_ITEM_TEXT` -> `STORNO_POSITION_TEXT` (der Storno lehnt
  jede Position ab).

Gegenproben (Marker `GEGENPROBE`, byte-genau zurück, je FAILED): Storno-Sperre beim Ändern aus -> 1 Test; Sperre der Schlussrechnung beim Entfernen aus
-> 1 Test; `positionBearbeitbar()` ohne Storno -> 1 Test (der Klicktest prüft dasselbe im Browser).

### R1, Punkt 5 (1.9.115): Änderungsprotokoll -- neue Arten, „verworfen“ und „Pausen neu gerechnet“

Befund F13: nicht in `AUDITED_TYPES` waren Auftragspositionen und -titel, Rechnungen, Mahnungen, Einsatzberichte, Wartungsverträge, Dachflächen, Termine
(die Zweige für `OrderItem`/`OrderSection` in `_normalize()` liefen nie); die Karte „Auftragsstände“ sagte trotzdem „Einzeländerungen bleiben zusätzlich
im Änderungsprotokoll sichtbar“. F14: /history zeigte jede Aktion außer „geändert“ und „angelegt“ als „Datensatz gelöscht“.

- `app/audit.py`: `AUDITED_TYPES` um `OrderItem`, `OrderSection`, `Invoice`, `InvoiceItem`, `Reminder`, `ServiceReport`, `MaintenanceContract`,
  `RoofArea`, `CalendarEvent`; Namen in `TYPE_LABELS`, jedes neue Feld in `FIELD_LABELS`; `_normalize()` je Art mit Bezeichnung und Projekt (über den
  Auftrag bzw. die Rechnung, beim Termin sein Projekt) -- Rechnung „R-2026-0001 · Schlussrechnung“ bzw. „Entwurf · …“, Rechnungsposition mit ihrer
  Rechnung, Mahnung „M-… · 1. Mahnung zu R-…“, Bericht „Rapportbericht vom 20.10.2026 · AUF-…“, Dachfläche mit Objekt, Wartungsvertrag mit Kunde.
- Still (`STILL_JE_ART`, `_still()`): Outlook-Abgleich (`outlook_synced_at`, `outlook_etag`, `outlook_event_id`), der Stempel gegen doppeltes Erinnern am
  Wartungsvertrag, die eingefrorenen Aufstellungen (`Reminder.amounts_json`, `ServiceReport.time_rows_json`) und die Beschreibung eines Berichts, solange
  er Entwurf ist -- der Schnappschuss beim Anlegen enthält sie.
- Privater Termin: Titel, Ort und Notiz nie in der Historie -- im Schnappschuss und als alt/neu „(privat)“, Bezeichnung „Privater Termin · Datum“
  (`_privat()`, `PRIVATE_TERMINFELDER`); /history liest jedes Büro.
- `app/templates/_verlauf.html` (neu): `verlaufAenderung(zeile)` -- „angelegt“/„gelöscht“ als Satz, „verworfen“ mit „Begründung: …“, „geändert“ und jede
  andere Aktion mit Werten (z. B. „Pausen neu gerechnet“: Pause des Tages alt -> neu) als alt -> neu; eingebunden in `history.html` und
  `project_folder.html` (Verlauf der Projektmappe zeigte bis dahin nur den Namen der Aktion).
- `app/verlauf_namen.py`: Bezeichnungen der neuen Festwerte -- `invoice_type` (aus `app/audit.py::RECHNUNGSARTEN`, dieselben Wörter wie in der Bezeichnung
  der Rechnung), `report_type` (`app/service_reports.py::REPORT_TYPE_LABELS`, auch für die Bezeichnung des Berichts), Status „Unterschrieben“, „Aktiv“,
  „Pausiert“, „Beendet“, „Bezahlt“ (Rechnungen vor 1.8.78), `rounding_rule` „Kaufmännisch (ab 1.8.11)“, `external_source` „Im ERP angelegt“/„Aus Outlook“,
  Einheit `pschl.` „Pauschal (pschl.)“ -- `test_v436::test_feste_werte_der_historie_sind_lesbar` verlangt das für jede protokollierte Spalte.

#### Festlegungen 1.9.115 (bestätigt am 28.10.2026)

1. Eine Rechnung wird wie jede andere Art je Feld protokolliert -- beim Festschreiben stehen deshalb mehrere Zeilen (Status, Nummer, Datum, Fälligkeit,
   feste Fassung, Kunde); die Neuberechnung beim Festschreiben erscheint an den Positionen (abgerechnete Menge, Betrag).
2. Die Beschreibung eines Einsatzberichts im Entwurf erscheint nicht je Speichern (wie die Antworten einer Checkliste, Entscheidung 1.8.13); sie steht im
   Schnappschuss beim Anlegen und ist nach der Unterschrift unveränderlich.
3. Ein privater Termin erscheint nur mit „Privater Termin · Datum“ und ohne Inhalte; Beginn, Ende, Besitzer und „Privat“ stehen da. Ein Termin, der von
   privat auf öffentlich wechselt, zeigt seinen Titel erst ab dann.
4. Termine aus dem Outlook-Abgleich erscheinen mit dem Auslöser „System“, wie jede Änderung ohne Anfrage.
5. Bestehende Einträge bleiben, wie sie sind; nichts wird nachgetragen.

#### Tests und Prüfung

Neu `tests/test_v535_aenderungsprotokoll.py` (9 Tests): Menge einer Auftragsposition und Titel eines LV-Titels mit alt und neu, unter dem Projekt und dem
Konto; Rechnung: Ist-Menge einer Position („Entwurf · Abschlag (Leistungsstand) · 1 …“), Festschreiben mit Status entwurf -> versendet und Nummer, Anlegen
des Stornos; Mahnung: Anlegen („Entwurf · 1. Mahnung zu …“), Festschreiben, keine Zeile für die Aufstellung; Einsatzbericht: Anlegen, Datum geändert, die
Beschreibung im Entwurf still, Bezeichnung „Rapportbericht vom 20.10.2026 · …“; Wartungsvertrag (Stempel still), Dachfläche („Nordseite · Halle“), Termin
mit alt und neu und Projekt, privater Termin nur „(privat)“ (Schnappschuss und Änderung, kein Titel in Bezeichnung oder Schnappschuss), Outlook-Stand
still; die Karte „Auftragsstände“ und `AUDITED_TYPES`; `verlaufAenderung()` in node („verworfen“ mit Begründung, „Pausen neu gerechnet“ alt -> neu,
„angelegt“, „gelöscht“, Werte maskiert); `history.html` und `project_folder.html` binden `_verlauf.html` ein und nehmen `verlaufAenderung(x)`.

Angepasst (keine Erwartung geändert): `tests/test_v334_auswahl_restfaelle.py::BAUSTEINE` um `_verlauf.html` -- die Attrappe einer Seite bindet die
Bausteine ein, die die Seite einbindet (Regel 36); ohne den Eintrag scheiterte `test_v436::test_verlaufsseite_laedt_seitenweise` an
„verlaufAenderung is not defined“.
Angepasst (nur der Aufbau): `tests/test_v381_zahlungen_migration.py::_rechnung()` legt die Rechnungsposition des Altbestands als Core-Insert an (bis
1.9.114 über das ORM) -- die Bezeichnung der neuen Historienzeile lädt die Rechnung über das heutige Modell, mit `invoices.customer_id`, die es auf dem Stand
vor der Migration noch nicht gibt (beide Proben, SQLite und PostgreSQL, im ersten Suitenlauf rot).

Gegenproben (Marker `GEGENPROBE`, byte-genau zurück, je FAILED in `test_v535`): `OrderItem` nicht protokolliert -> 2 Tests; `Invoice`/`InvoiceItem` nicht
protokolliert -> 2; privater Termin ohne Maske -> 1; Beschreibung des Berichts im Entwurf nicht still -> 1; „verworfen“ ohne Begründung -> 1. Ein erster
Lauf der beiden ersten hatte den Marker als Kommentar mitten in der Zeile (der Rest der Liste fiel mit weg, 4 statt 2 rot) -- wiederholt mit der ganzen
Zeile.

### R1, Punkt 6 (1.9.116): keine Eingabe geht beim Neuzeichnen verloren

Befund E2: jede Antwort im Bereich „rechnung“ zeichnet die Rechnung über `render()` neu und setzte Einleitung, Schlusstext, Schlusstext 2,
Pauschalbetrag (Bezeichnung, Betrag) und An/CC des Versands auf den Stand vom Server. E4: ein Schrittwechsel im Einsatzbericht zeichnet Schritt 5 neu --
gezeichnete Unterschriften und Namen weg; ein angefangener Befund verlor nach `inhaltZeichnen()` seinen Text (`BEFUND_FORM` merkte nur Schwere und
Maßnahme).

- `invoice_detail.html`: `EINGABEN` merkt getippte Werte der Felder `MERKFELDER` (ein `input`-Lauscher am Dokument); `render()` und die Versandknöpfe setzen
  `feldWert(id, server)` -- getippt vor Server. Speichern (`saveHeader()`, `savePauschal()`) nimmt die gesendeten Werte heraus, wenn das Feld seither
  nicht weiter geändert wurde (`eingabenGespeichert()`); eine Vorlage aus der Auswahl zählt wie getippt; nach dem Versand gelten An/CC wieder vom Server.
- `_unterschrift.html`: `stand()` (Striche in Punkten der Basisgröße, Basis, „hat Inhalt“) und `setzen(stand)` (zeichnet sie auf der neuen Fläche,
  skaliert wie beim Drehen) -- die eine Zeichenfläche bleibt die einzige.
- `service_report.html`: `unterschriftMerken()` vor jedem `inhaltZeichnen()` (Namen und Striche aus Schritt 5), `unterschriftEinrichten()` setzt sie
  wieder; mit dem Abschluss verworfen. Der Befund merkt Text (`befund-text`, bei jeder Eingabe) und Wiedervorlage (`befund-wiedervorlage`) in
  `BEFUND_FORM` wie Schwere und Maßnahme.

#### Festlegungen 1.9.116 (bestätigt am 28.10.2026)

1. Getippte, nicht gespeicherte Werte bleiben, solange die Seite offen ist -- nicht über ein Neuladen der Seite hinweg (kein Zwischenspeicher im Browser).
2. Auf der Rechnung gilt ein getippter Wert vor einem neuen Stand vom Server, auch wenn jemand anders das Feld inzwischen gespeichert hat; mit dem eigenen
   Speichern gewinnt der eigene Wert (wie bisher).
3. Die Unterschriften im Einsatzbericht bleiben über Schrittwechsel und jedes Neuzeichnen stehen; „Leeren“ leert wie bisher.

#### Tests und Prüfung

Neu `tests/test_v536_eingaben_bleiben.py` (6 Tests): in node mit der Rechnungsseite -- getippt gilt vor dem Stand vom Server, bis gespeichert; ein nach
dem Senden weiter geändertes Feld bleibt; ein Feld außerhalb von `MERKFELDER` wird nicht gemerkt; An/CC stehen im neu gezeichneten Versand; eine Vorlage aus
der Auswahl zählt wie getippt; jedes Merkfeld wird über `feldWert()` gefüllt, beide Speicherwege nehmen nur das Gesendete heraus. Zeichenfläche in node
(Canvas-Attrappe): Striche auf 300 × 150 gezeichnet, auf einer Fläche 600 × 300 gesetzt -- nicht leer, derselbe Strich, Maßstab 2; `setzen(null)` lässt
stehen; „Leeren“ leert. Bericht: `inhaltZeichnen()` merkt zuerst, `unterschriftEinrichten()` setzt (abgeschlossen: verworfen), Text und Wiedervorlage des
Befunds mit Aktion.
Neu `scripts/klicktest_eingaben_bleiben.py` (12 Prüfungen): Rechnung (Entwurf, pauschaler Abschlag) -- Einleitung, Schlusstexte, Bezeichnung und Betrag
getippt, Leistungszeitraum und Zahlungsbedingung geändert (neu gezeichnet), alles steht noch (Bild), „Kopfdaten speichern“ und „Pauschale speichern“
speichern es; festgeschriebene Rechnung: An/CC über `reload()`; Einsatzbericht als Monteurin: angefangener Befund mit Text, „zurückgestellt“ und
Wiedervorlage über einen Schrittwechsel; Namen und beide Unterschriften gezeichnet, Schritt „Arbeiten“ und zurück -- noch da, „Bericht abschließen“ frei
(Bild).

Im ersten Lauf rot und behoben: `test_v414` (Regel 34) -- `savePauschal()` las den Rohtext des Betragsfelds für den Vergleich mit dem Merker; jetzt aus dem
Merker selbst (`EINGABEN.pAmount`, er hält den zuletzt getippten Text).

Gegenproben (Marker `GEGENPROBE`, byte-genau zurück): `setzen()` tut nichts -> 1 Test (v536); `eingabenGespeichert()` tut nichts -> 1; der Lauscher merkt
nichts -> 2; `inhaltZeichnen()` ohne `unterschriftMerken()` -> Klicktest 11/12 („Namen und Unterschriften noch da“: Kunde leer, beide Flächen leer); der
Befund merkt den Text nicht -> Klicktest 11/12 (Text leer, Maßnahme und Wiedervorlage noch da).

### R1, Punkt 7 (1.9.117): Mustervorgang nicht beauftragbar, „Projekt löschen“ nur ohne Auftrag

Befund F6: weder Editor noch Server prüften `Project.is_template`; `delete_project()` und `duplicate_project()` nehmen an, ein Mustervorgang habe nie einen
Auftrag. F15: „Löschen“ stand auch bei Projekten mit Auftrag und endete mit 400.

- `app/orders.py::create_order_from_quote()`: ist das Projekt ein Mustervorgang, `MustervorgangNichtBeauftragbar` (`MUSTERVORGANG_TEXT` mit dem Weg),
  bevor etwas geschrieben wird; `app/routers/quotes.py` antwortet 409. Jeder andere Aufrufer (Schnellauftrag) legt ein eigenes Projekt an.
- `quote_to_dict()` meldet `project_is_template`; der Angebots-Editor blendet „Angebot beauftragen“ aus und zeigt den Hinweis im Kasten über dem LV.
- Projektmappe: Kennzeichen „Mustervorgang“ im Kopf (`templateBadge`), „Löschen“ im Menü nur ohne Auftrag (`deleteMenuItem`, nach `order_count`);
  Projektliste: „Löschen“ im Menü einer Zeile nur ohne Auftrag. Der Server lehnt wie bisher ab (400).

#### Festlegungen 1.9.117 (bestätigt am 28.10.2026)

1. Ein Mustervorgang wird nie beauftragt, auch nicht vom Admin; der Weg ist „Neuen Vorgang erstellen“.
2. Ohne „Löschen“ bleibt bei einem Projekt mit Auftrag „Archivieren“ -- kein zusätzlicher Hinweis im Menü.
3. Bestehende Aufträge an Mustervorgängen (falls es welche gibt) bleiben, wie sie sind; nichts wird umgestellt.

#### Tests und Prüfung

Neu `tests/test_v537_mustervorgang_und_loeschen.py` (8 Tests): Beauftragen des Angebots eines Mustervorgangs als Büro – Auftrag 409 mit dem Weg, kein
Auftrag, `project_is_template` am Angebot; Gegenprobe: dasselbe Angebot nach „Neuen Vorgang erstellen“ (`duplicate_project()`) lässt sich beauftragen;
die Fachfunktion wirft auch ohne Router; der Editor in node (der Teil von `renderAll()` bis zum Seitenkopf) -- Muster: Knopf verborgen, Hinweis mit dem
Weg; gewöhnlich: „Angebot beauftragen“; die Projektliste in node (`menuItemsFor()`): „Löschen“ nur ohne Auftrag, auch in „Nur Mustervorgänge“; die
Projektmappe: Kennzeichen und „Löschen“ nach `order_count`.
Neu `scripts/klicktest_mustervorgang.py` (9 Prüfungen): Editor des Musters ohne „Angebot beauftragen“ mit Hinweis (Bild), POST aus der Seite 409; Editor
eines gewöhnlichen Angebots wie bisher; Projektmappe des Musters mit Kennzeichen (Bild), mit Auftrag ohne „Löschen“, ohne Auftrag mit; Projektliste und
„Nur Mustervorgänge“.

Gegenproben (Marker `GEGENPROBE`, byte-genau zurück, je FAILED in `test_v537`): der Server prüft den Mustervorgang nicht -> 2 Tests (409, Fachfunktion); der
Editor ohne Hinweis -> 1; Projektliste mit „Löschen“ auch mit Auftrag -> 1; Projektmappe ebenso -> 1.

### R1, Punkt 8 (1.9.118): fehlerText() in Berichtsliste und Objekt (mobil)

Befund B12: `service_reports.html` (`api()`) und `mobil_objekt.html` (`api()`, das Hochladen eines Dokuments und -- beim Umbau gefunden -- das Laden der
Wartungshistorie) gaben `detail` roh an `Error()` -- eine
422-Liste erschien als „[object Object]“. Beide binden `_fehlertext.html` ein und nehmen `fehlerText(body, status, FELDNAMEN)` (Feldnamen der Seite:
Berichtstyp, Datum des Einsatzes, Durchgeführt von, Dachflächen, Vorlage, Beschreibung bzw. Kategorie, Beschreibung, Datei). Keine Festlegungen.

#### Tests und Prüfung

Neu `tests/test_v538_fehlertext_berichtsliste_objekt.py` (5 Tests): beide Seiten binden `_fehlertext.html` ein und reichen `detail` nicht roh an `Error()`;
in node die `api()` der Seite mit einer 422-Liste -- „Bitte die Eingabe prüfen – Berichtstyp fehlt; Datum des Einsatzes ist kein gültiges Datum.“ bzw.
„… – Kategorie muss eine ganze Zahl sein; Datei fehlt.“; ein Text (409) bleibt wörtlich. Kein Klicktest: über die Oberfläche lässt sich keine 422-Liste
auslösen (die Felder geben keinen ungültigen Wert her); die Klicktests beider Seiten liefen unverändert grün.

Gegenproben (Marker `GEGENPROBE`, byte-genau zurück, je FAILED in `test_v538`): `api()` der Berichtsliste wieder roh -> 1 Test; `api()` des Objekts wieder roh
-> 1; die Feldnamen der Berichtsliste fehlen -> 1.

## Stufe 5, R1 Nachrunde (ab 1.9.119)

Vorgabe 28.10.2026, Start auf `1eda18a` (1.9.118, live). Festlegungen R1 bestätigt, außer 1.9.111 Nr. 1 und Nr. 5 (Einstellungen mit Geld,
Punkt 2) und 1.9.112 Nr. 3 („Durchgeführt von“, Punkt 3) -- die Überschriften oben tragen das. Live: 6 Rechnungen, darunter 1 Storno,
angelegt vor 1.9.114. Punkte: 1 Prüfung der Stornos, 2 Einstellungen mit Geld, 3 „Durchgeführt von“ nach der Regel der Zeiten, 4 gesperrte
Felder hell erkennbar, 5 Verlauf lesbar (Merkliste 7b).

### Nachrunde, Punkt 1 (1.9.119): hebt jeder Storno sein Original genau auf?

Anlass: bis 1.9.113 ließen sich die Positionen eines Storno-Entwurfs ändern, ergänzen und entfernen (Befund F8, Beleg unter „R1, Punkt 4“);
der Storno von vor 1.9.114 auf dem Server kann deshalb von seinem Original abweichen.

`scripts/pruefe_stornos.py`:
- je festgeschriebenem Storno (Art `storno`, nicht Entwurf) Netto, USt und Brutto aus `compute_invoice_totals()` gegen das Gegenteil des
  Originals; jede Position -- gepaart nach Sortierung und Positionsnummer, so verschiebt eine ergänzte oder entfernte Position die übrigen
  nicht -- mit Menge, Einzelpreis und Betrag (`invoice_line_total()`, nach der Rundungsregel der Rechnung). Ein pauschaler Abschlag ohne
  Position (vor 1.3.24) hat als Soll die eine Position, die sein Storno seit 1.8.83 bekommt.
- Ausgabe je Treffer „Storno R-… (ID n) zu R-… (ID m):“ und je Abweichung eine Zeile „Netto: Soll −2.000,00 €, Ist −1.650,00 €“ bzw.
  „Position 1 Dacheindeckung: Menge Soll −40, Ist −33; Betrag …“, „… fehlt im Storno“, „… nur im Storno“; ungerundete Beträge (vor
  1.8.11) mit ihrer ganzen Genauigkeit. Ohne Treffer „Alle n Stornos heben ihr Original genau auf.“, ohne Storno „Kein festgeschriebener
  Storno -- nichts zu prüfen.“ Rückgabe 0 / 1 (Treffer) / 2 (Umgebung fehlt).
- Nur lesen: eigene Engine aus `DATABASE_URL` (Pflicht, wie bei alembic), jede Verbindung schreibgeschützt, bevor die erste Anfrage läuft
  (PostgreSQL `SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY`, SQLite `PRAGMA query_only`), am Ende zurückgerollt; `app.main` wird
  nicht geladen (keine Grunddaten, kein `create_all`). Aufruf auf dem Server im Kopf der Datei:
  `cd /home/tobias/erp`, `set -a; source .env; set +a`, `.venv/bin/python scripts/pruefe_stornos.py`.

#### Festlegungen 1.9.119 (bestätigt am 28.10.2026)

1. Geprüft werden nur festgeschriebene Stornos; ein Entwurf zählt nicht (er lässt sich seit 1.9.114 nicht mehr an den Positionen ändern und
   löschen und neu anlegen).
2. Ein Treffer korrigiert nichts -- das Skript berichtet nur. Was mit einem abweichenden Storno geschieht (ein zweiter Storno ist nicht
   möglich, GoBD), entscheidet der Betreiber.

#### Tests und Prüfung

Neu `tests/test_v539_pruefe_stornos.py` (10 Tests): genauer Storno eines Abschlags nach Leistungsstand -> kein Treffer, „Alle 1 Stornos heben ihr
Original genau auf.“, Rückgabe 0; derselbe mit Ist 7 am Storno (−33 m², −1.650,00 €, direkt in der Datenbank wie vor 1.9.114) -> Treffer mit
Netto, USt, Brutto und der Position Soll/Ist, Rückgabe 1; ergänzte und entfernte Position; ein Entwurf zählt nicht; pauschaler Abschlag mit und
ohne Position; Rechnung vor 1.8.11 mit krummem Preis (ungerundet) genau -- und um 0,0042 € daneben sichtbar; Schlussrechnung mit Abzug; ohne
`DATABASE_URL` Rückgabe 2; die eigene Sitzung schreibt nicht, gegen eine SQLite-Datei und gegen PostgreSQL (Wegwerf-Schema, URL über
`pg_url_pruefen()`): Lauf über `DATABASE_URL` gibt Rückgabe 0, ein `UPDATE` scheitert, Änderungsprotokoll und Status unverändert.

Im ersten Lauf rot und am Test behoben: der Bestand für PostgreSQL über `make_order_with_item()` (verweist auf ein Angebot 1, das es nicht
gibt -- unter PostgreSQL ein Fremdschlüsselfehler) -> Auftrag über Angebot und Beauftragen; der krumme Preis im Entwurf statt im Auftrag
(seit 1.8.85 Abweichung vom Auftrag, 409) -> im Auftrag; `test_v384` (Regel 27) -> die URL geht über `pg_url_pruefen()`.

Gegenproben (Marker `GEGENPROBE`, byte-genau zurück, je FAILED in `test_v539`): Summen nicht verglichen -> 3 Tests; Positionen nicht verglichen
-> 2; SQLite ohne Schreibschutz -> 1; PostgreSQL ohne Schreibschutz -> 1.

### Nachrunde, Punkt 2 (1.9.120): Einstellungen mit Geld

Festlegung 1.9.111 Nr. 1 (Mahnstufen speichert jedes Büro) und Nr. 5 (Zahlungsbedingungen, Steuerschlüssel, Nummernkreise unverändert) nicht
bestätigt; Vorgabe: höchstens Admin und Büro – Finanzen.

Wer darf das -- bis 1.9.119 und seit 1.9.120:

| Bereich | bis 1.9.119 speichern | seit 1.9.120 speichern | lesen |
|---|---|---|---|
| Mahnstufen: Bezeichnung, Zahlungsfrist, Gebühr, aktiv, Mahntext, E-Mail-Betreff und -Text (`PUT /api/reminder-levels/{id}`, auch über E-Mail-Vorlagen) | Admin, Büro – Finanzen, Büro – Auftrag | Admin, Büro – Finanzen | jedes Büro |
| Schalter Mahngebühren, Basiszinssatz, Mahn-Rechtstexte | Admin | Admin (unverändert) | jedes Büro |
| Zahlungsbedingungen: anlegen, ändern, als Standard, archivieren, wiederherstellen (5 Endpunkte) | Admin, Büro – Finanzen, Büro – Auftrag | Admin, Büro – Finanzen | jedes Büro |
| Steuerschlüssel: ebenso (5 Endpunkte) | Admin, Büro – Finanzen, Büro – Auftrag | Admin, Büro – Finanzen | jedes Büro |
| Nummernkreise, alle sieben: Format, Start, nächste Nummer, Jahreswechsel (`PUT /api/settings/number-sequences/{key}`) | Admin, Büro – Finanzen, Büro – Auftrag | Admin, Büro – Finanzen | jedes Büro |

Die Monteurin erreicht keinen dieser Endpunkte (unverändert).

- `app/permissions.py`: `require_geld_einstellung` -- dieselben Rollen wie `darf_geld()`/`require_geld` (`GELD_ROLLEN`), eigene Meldung
  `EINSTELLUNGEN_GELD_NUR_LESEN` („Mahnstufen, Zahlungsbedingungen, Steuerschlüssel und Nummernkreise ändern Admin und Büro – Finanzen – du kannst
  sie lesen.“); an den 12 Endpunkten (`app/routers/payment_terms.py`, `tax_keys.py`, `reminders.py`, `settings.py`).
- Seite: die Seitenroute der Einstellungen gibt `geld` und `geld_nur_lesen` mit; ohne `geld` zeigen Nummernkreise, Zahlungsbedingungen, Steuer und
  Mahnwesen den Hinweis (`data-geld-nur-lesen`), sperren jedes Feld und blenden jedes Speichern aus (`geldNurLesen()`, Knöpfe mit
  `data-geld-knopf`); „+ Zahlungsbedingung“ und „+ Steuerschlüssel“ fehlen im Markup, die Zeile bietet „Ansehen“ (Formular gesperrt, „Schließen“)
  statt „Bearbeiten“, „Als Standard“, „Archivieren“, „Wiederherstellen“. Unter E-Mail-Vorlagen sind Betreff und Text einer Mahnstufe gesperrt, mit
  dem Hinweis; die übrigen Dokumente bleiben offen.

#### Festlegungen 1.9.120 (bestätigt am 28.10.2026)

1. Die ganze Mahnstufe zählt dazu -- auch Bezeichnung, Mahntext und die E-Mail-Texte (auch unter E-Mail-Vorlagen), nicht nur Frist und Gebühr;
   die E-Mail-Vorlagen der übrigen Dokumente (auch der Rechnung) speichert weiter jedes Büro.
2. Alle sieben Nummernkreise, auch Kunden, Anfragen, Projekte, Angebote und Aufträge -- nicht nur Rechnung und Mahnung.
3. Büro – Auftrag sieht die vier Bereiche gesperrt mit Hinweis (liest alles), statt dass sie aus dem Menü verschwinden.
4. Die Zahlungsbedingung am Kunden (Kundenvorgabe in den Stammdaten) bleibt eine Angabe des Kunden -- jedes Büro wählt sie wie bisher.

#### Tests und Prüfung

Neu `tests/test_v540_einstellungen_mit_geld.py` (46 Tests): Struktur -- die 12 schreibenden Routen nehmen nur Admin und Büro – Finanzen, das Lesen
der Zahlungsbedingungen und Steuerschlüssel bleibt jedem Büro; der Rundgang deckt jede der 12 Routen; als Büro – Auftrag je 403 mit der Meldung
und jede Zeile der vier Tabellen unverändert; als Büro – Finanzen und Admin je 200 und geschrieben; Büro – Auftrag liest alle vier; die Seite als
Büro – Auftrag mit dem Hinweis in allen vier Bereichen und ohne „+ …“, als Büro – Finanzen ohne; in node auf der vom Server gezeichneten Seite die
Knöpfe der Listen je Rolle und die Mahnstufe unter E-Mail-Vorlagen gesperrt bzw. offen, das Angebot offen.
Neu `scripts/klicktest_einstellungen_geld.py` (14 Prüfungen): Büro – Auftrag -- die vier Bereiche mit Hinweis, kein offenes Feld, kein Speichern;
„Ansehen“ zeigt die Zahlungsbedingung gesperrt mit ihrem Text und „Schließen“ (Bild); E-Mail-Vorlagen: Mahnstufe gesperrt, Angebot offen; Angriff
aus der Seite (Mahnstufe, Zahlungsbedingung) 403; Büro – Finanzen: Felder offen, Nummernkreis und Zahlungsbedingung gespeichert.

Angepasste Erwartungen:
- `test_v531::test_jede_schreibende_geld_route_nimmt_nur_admin_und_finanzen`: `KEIN_GELD` = {PUT Mahnstufe} -> leer (keine Ausnahme mehr).
- `test_v531::test_rundgang_deckt_jede_schreibende_geld_route`: die Mahnstufe fiel über `KEIN_GELD` heraus -> ausdrücklich ausgenommen, ihr Rundgang
  steht in `test_v540` (nur Aufbau).
- `test_v400::test_email_templates_the_last_chosen_type_wins`: die Vorbereitung um `const GELD=true` ergänzt (nur Aufbau; im ersten Lauf rot:
  „GELD is not defined“).

Gegenproben (Marker `GEGENPROBE`, byte-genau zurück, je FAILED): Büro – Auftrag in `require_geld_einstellung` -> 14 Tests (v540, v531); der
Nummernkreis wieder ab Büro – Auftrag -> 2; die Liste bietet „Bearbeiten“ ohne `GELD` -> 1; die Mahnstufe unter E-Mail-Vorlagen offen -> 1.

### Nachrunde, Punkt 3 (1.9.121): „Durchgeführt von“ nach der Regel der Zeiten

Festlegung 1.9.112 Nr. 3 (Büro – Finanzen wählt dort nur sich selbst) nicht bestätigt; Vorgabe: nach `darf_zeit_fuer_andere_buchen()`.

- `app/routers/service_reports.py::_employee_for_request()` (Bericht anlegen, Foto, Material, Betriebsmittel, Wartungseinsatz) fragt
  `darf_zeit_fuer_andere_buchen()` -- Admin und Büro – Finanzen frei, sonst nur die eigene Person oder keine (403 wie bisher);
  `darf_fuer_andere_erfassen()` (nur Admin) ist aus `app/permissions.py` entfernt.
- Seite „Einsatzberichte“: `durchgefuehrtVonOptionen()` nach `zeit_fuer_andere_buchen` der Seitenroute (der Wert stand dort schon), der eigene
  Wert `fuer_andere_erfassen` entfällt.
- Bisher schickt nur „Durchgeführt von“ eine Person mit; Foto, Material und Betriebsmittel setzt die Seite ohne Angabe (der Server nimmt das Konto).

Keine neuen Festlegungen.

#### Tests und Prüfung

Neu `tests/test_v541_durchgefuehrt_von.py` (4 Tests): Bericht „durchgeführt von“ Mia als Büro – Finanzen 200 (Mia im Bericht), als Admin 200, als
Büro – Auftrag 403 mit der Meldung; eine Regel -- `darf_fuer_andere_erfassen` gibt es nicht mehr, `_employee_for_request()` ruft
`darf_zeit_fuer_andere_buchen()`.

Angepasste Erwartungen:
- `test_v532::test_durchgefuehrt_von_regel_und_server[buero_finanzen]`: Regel False, fremde Person 403 -> Regel True (`darf_zeit_fuer_andere_buchen()`),
  fremde Person 200.
- `test_v532::test_einsatzberichte_seite_bietet_nur_an_was_der_server_annimmt[buero_finanzen]`: „— nicht zugeordnet —“ und sich selbst -> alle
  Mitarbeiter (eigener vorgewählt).
- `klicktest_befund_fremder_bericht` „„Durchgeführt von“ (Büro – Finanzen): nur sie selbst“ -> „… alle“; neu: Bernd legt über die Seite einen
  Bericht „durchgeführt von“ Mia an (200) (10 -> 11 Prüfungen).

Gegenproben (Marker `GEGENPROBE`, byte-genau zurück, je FAILED): der Server wieder nur der Admin -> 3 Tests (v541, v532); die Seite wieder nur der
Admin -> 1 Test (v532).

### Nachrunde, Punkt 4 (1.9.122): gesperrte Felder hell erkennbar -- eine Regel

Befund: das Token `--ds-feld-gesperrt` (1.9.110) nahmen nur fünf Seiten mit je eigener Regel (Einstellungen, Checkliste, Checklisten-Vorlage,
Stammdaten-Formular `input[readonly]`, Auftrag `#itemDialog`/`#taxKey`; die LV-Zeilen des Auftrags zeigten gesperrte Felder durchsichtig); jede andere
Seite zeigte ein gesperrtes Feld wie ein offenes -- gemessen (Gegenprobe 4 unten): die Rechnung als Büro – Auftrag mit 14 gesperrten Feldern, hell je
`rgb(255, 255, 255)`, Schrift `rgb(23, 28, 31)`, Mauszeiger `default`.

- Neu `app/static/ds/ds-gesperrt.css`, eingebunden über `_ds_kopf.html` nach `ds-alte-namen.css` (Zusatz `?v=` aus der Prüfsumme,
  `ds_gesperrt_pruefsumme`): eine Regel -- `input` mit Fläche (nicht Kästchen, Optionsfeld, Knopf, Datei, Farbe, Schieber, verborgen), `textarea` je
  `:disabled` oder `[readonly]`, `select` `:disabled`, jeweils ohne `data-gesperrt-eigen` -- mit `background: var(--ds-feld-gesperrt)`,
  `color: var(--ds-text-2)`, `cursor: not-allowed`, je `!important`.
- Warum eine eigene Datei und nicht `ds-basis.css`: dort gilt jede Regel nur unter `.ds-seite` (die aufgeschobenen Seiten -- Projektmappe, Auftrag,
  Kundenakte, Kalender, Plantafel, Heute, Meine Zeiten, Neues Projekt, Neues Angebot -- hätte sie nicht erreicht) und mit dem Gewicht null (jede
  Feldregel einer Seite, schon `input{background:…}`, hätte sie überstimmt).
- Warum `!important`: die Regel wiegt ohne (0,2,1) und schlägt damit `.field input` (0,1,1) -- die Gegenprobe ohne `!important` änderte auf den
  gemessenen Seiten nichts (Gegenprobe 3). Feldregeln mit gleichem oder höherem Gewicht gibt es aber, z. B. `#signDialog .sign-row input` (1,1,1) und
  `.contract-sign input[type=date]` (0,2,1) im Auftrag, `.zeile input.antrag-notiz` (0,2,1) in „Zeiten“, `.app-topbar .app-topbar-search input`
  (0,2,1); gesperrt sähen sie ohne `!important` wieder offen aus. `!important` gibt es unter `app/static/` nur in dieser Datei (Wächter).
- Entfallen: die Regeln in `settings.html`, `checklist.html` (dort bisher Schrift `--ink`), `checklist_template.html`, `master_data_form.html` (bisher
  Mauszeiger `default`; die Regel für den Rahmen beim Überfahren bleibt) und `order.html` (`#itemDialog`, `#taxKey`, `.lv-row`) -- an ihrer Stelle
  ein Kommentar.

#### Festlegungen 1.9.122 (bestätigt am 28.10.2026)

1. Schrift gesperrter Felder überall `--ds-text-2` -- auch in der unterschriebenen Checkliste (bisher `--ink`): 6,97 : 1 hell, 7,18 : 1 dunkel.
2. Auch in den LV-Zeilen des Auftrags tragen gesperrte Felder die Fläche (bisher durchsichtig, ohne Rahmen) -- keine Ausnahme ohne Begründung.
3. Hell bleibt die Fläche `#F3F5F6` (Festlegung 1.9.110 Nr. 2); erkennbar macht sie zusammen mit der gedämpften Schrift und dem Mauszeiger.
4. `readonly` zählt wie `disabled` (beide nicht bearbeitbar); Kästchen und Optionsfelder bleiben, wie der Browser sie gesperrt zeigt.

#### Tests und Prüfung

Neu `tests/test_v542_gesperrte_felder.py` (12 Tests): genau eine Regel mit den drei Eigenschaften und den Ausnahmen der Feldarten; `!important` nur
hier; eine Design-Datei, auf jeder Seite aus `seiten()` genau einmal nach `ds-alte-namen.css`; keine Vorlage mit eigener Regel für Fläche, Schrift
oder Mauszeiger gesperrter oder nur lesbarer Felder (Knöpfe ausgenommen, `#id` über das Element der Vorlage) mit Angriffen und Durchlässen für den
Wächter; `data-gesperrt-eigen` nur mit Grund (`AUSNAHMEN`, leer); hell und dunkel ist die Fläche anders als die eines offenen Felds (`--card` zeigt
auf `--ds-flaeche`), die Schrift darauf mindestens 4,5 : 1.
Neu `scripts/klicktest_gesperrte_felder.py` (12 Prüfungen, Testdaten der Bildgrundlage): Rechnung als Büro – Auftrag (jedes Feld gesperrt) und als Büro
– Finanzen, Einstellungen als Büro – Auftrag (Nummernkreise, Mahnwesen) und als Büro – Finanzen (DATEV) -- je hell und dunkel jedes sichtbare
gesperrte Feld mit Fläche, Schrift und Mauszeiger der Regel, die Fläche anders als die eines offenen Felds, kein offenes Feld mit der Fläche der Regel
(Bilder hell und dunkel).

Angepasste Erwartungen:
- `test_v530::test_gesperrte_felder_nehmen_das_token[5 Seiten]`: jede der fünf Seiten hat eine eigene Regel mit dem Token -> keine eigene Regel, die
  Regel in `ds-gesperrt.css` nimmt das Token.
- `test_v526::test_gesperrte_felder_der_einstellungen_grau`: die Regel der Seite im HTML -> keine Regel der Seite, `ds-gesperrt.css` eingebunden.
- `test_v432::test_ds_kopf_bindet_ds_css_und_ds_basis_mit_pruefsumme_ein`: drei Zeilen -> vier (dazu `ds-gesperrt.css`).
- `test_v252` (Globals der Vorlagen): 11 -> 12, dazu `ds_gesperrt_pruefsumme`.
- `klicktest_ds_schriften` „ds.css, ds-basis.css und ds-alte-namen.css eingebunden“: drei Dateien -> vier (dazu `ds-gesperrt.css`); neu: ihre
  Kopfzeilen (200, CSS, langer Cache, nosniff) -- 30 -> 31 Prüfungen (im ersten Gesamtlauf der Klicktests rot, die Erwartung war mit 1.9.122 veraltet).

Gegenproben (Marker `GEGENPROBE`, byte-genau zurück): die Regel nicht eingebunden -> 1 Test (v542) und der Klicktest 2/12 (jedes gesperrte Feld der
gemessenen Seiten hell weiß, dunkel `rgb(26, 32, 36)` wie ein offenes, Mauszeiger `default` -- der Zustand bis 1.9.121); eine Seite mit eigener Regel ->
1 Test; die Fläche ohne `!important` -> Klicktest unverändert 12/12 (siehe oben: auf den gemessenen Seiten gewinnt die Regel durch ihr Gewicht, nötig ist
`!important` gegen schwerere Feldregeln).

### Nachrunde, Punkt 5 (1.9.123): Verlauf lesbar (Merkliste 7b)

Befund (Merkliste 7b des Befunds Stufe 5): Fremdschlüssel als Zahl, Dezimalzahlen mit Punkt und allen Stellen („850.000000“, „19.0000“, „7.5000“),
Tage und Zeitpunkte als ISO-Text (naive UTC wie naive Ortszeit, im Browser nicht unterscheidbar), JSON roh, Codes im Namen des Datensatzes
(„… · 2026-10-28 · site · 7.5000 h“, „Mitarbeiter #12“, „Gruppe #7“), „value“ jeder Art über die Tabelle des Mangels.

- `app/verlauf_namen.py`: `lesbar_alle(db, zeilen)` je Antwort von `GET /api/audit-logs` (`app/routers/audit.py`, nach der Schwärzung, für jede
  Rolle) mit einem `Kontext`: Namen zu den IDs je Zielklasse in einer Abfrage, die Einheiten der Positionen, die Zeitarten der Auswahlliste
  „Zeitarten“. Je Wert nach der Spalte der Art (`_spalte()`, aus `TYPE_LABELS` und dem Modell):
  * Fremdschlüssel (auch `…_user_id` und die Herkunft einer Angebotsposition ohne Fremdschlüssel im Modell) -> Name des Datensatzes von heute
    (`_name()`, wie `app/audit.py::_entity_label()`), unbekannt „Nr. n (nicht mehr vorhanden)“; `task_id` bleibt eine Nummer (Titel nur für Admin und
    Zuständige).
  * Zahl -> deutsch: Geld mit zwei Stellen (kaufmännisch, `round_money()`), sonst ohne Nullen am Ende; Einheit je Feld (`EINHEITEN`: €, %, h, min,
    m², °, px, Monate, Tage), Mengen mit der Einheit ihrer Position; Dateigrößen als Byte/KB/MB. Neues Feld `einheit` an `AuditLogOut`.
  * Tag -> „TT.MM.JJJJ“; Zeitpunkt -> „TT.MM.JJJJ HH:MM“ in Europe/Berlin -- naive UTC über `to_berlin()`, naive Ortszeit (`ORTSZEIT`: `started_at`,
    `ended_at`, `start_at`, `end_at`, `visit_at`, `follow_up_at`) unverändert.
  * JSON -> „Daten (n Angaben)“ bzw. „n Einträge“.
  * Code -> Bezeichnung wie bisher (`wert_lesbar()`), Zeitarten nach der Auswahlliste (statische Namen seit 1.9.123 wie dort: „Baustellenzeit“,
    „Werkstattzeit“, „Sonstige Arbeitszeit“; bis 1.9.122 „Baustelle“, „Werkstatt“, „Sonstige“); „value“/„previous_value“ nur am Mangel.
  * Eine Art ohne Modell (z. B. „Vertrag“, „Aufgabe“): nur, was der Wert selbst zeigt (ISO-Zeit, ISO-Tag, Dezimalzahl).
- Name des Datensatzes (`name_lesbar()`): ISO-Tage deutsch, Zeitarten zwischen „ · “ übersetzt, Stunden deutsch, „Mitarbeiter #12“ als Name,
  „Gruppe #7“ als „Gruppenbuchung Nr. 7“.
- `_verlauf.html::verlaufAenderung()`: die Einheit hinter dem neuen Wert -- „850 → 851 m²“.

#### Festlegungen 1.9.123 (bestätigt am 28.10.2026)

1. Übersetzt wird beim Lesen, gespeichert bleibt jeder Wert roh -- auch Einträge von vor 1.9.123 erscheinen lesbar.
2. Die Einheit steht einmal, hinter dem neuen Wert („850 → 851 m²“, „19 → 7 %“).
3. Geld mit zwei Nachkommastellen, jede andere Zahl ohne Nullen am Ende; ganze Zahlen ohne Einheit (Sortierung, Nummern, Jahr, Stufe) ohne
   Tausenderpunkt.
4. Zeitarten heißen wie in der Auswahlliste der Datenbank (wie die Oberfläche): „site“ -> „Baustellenzeit“.
5. Eine ID erscheint mit dem Namen des Datensatzes von heute (ein umbenannter Kunde mit dem heutigen Namen), ein gelöschter als „Nr. n (nicht mehr
   vorhanden)“; die Aufgabe bleibt eine Nummer.
6. JSON erscheint als „Daten (n Angaben)“ bzw. „n Einträge“ -- der Inhalt bleibt im Eintrag, angezeigt wird er nicht.

#### Tests und Prüfung

Neu `tests/test_v543_verlauf_lesbar.py` (9 Tests) über `GET /api/audit-logs`: Menge einer Auftragsposition 850 -> 851 mit „m²“ aus der Position; MwSt.
„19“ -> „7“ mit „%“, Einheitspreis „50,00“ -> „1.250,50“ mit „€“, Stunden „7,5“ -> „8“ mit „h“; ein UTC-Zeitpunkt in Berlin („01.07.2026 12:00“ aus 10:00),
der Beginn einer Zeitbuchung unverändert, ein Tag deutsch; die Zeitbuchung im Namen „E-1 Mia Monteurin · 14.10.2026 · Baustellenzeit · 3,25 h“ und die
Zeitart als Wert; Sachbearbeiter und Kunde als Name, ein gelöschter Kunde „Nr. 999 (nicht mehr vorhanden)“, die Aufgabe als Nummer; die Pipeline-Spalte
als Name; JSON „Daten (2 Angaben)“, „value“ eines Kundenwissens unverändert, am Mangel „Offen“; eine ganze Antwort ohne „.000000“, ohne ISO-Tag, ohne
„site“; in node `verlaufAenderung()` mit der Einheit (maskiert).
Neu `scripts/klicktest_verlauf_lesbar.py` (6 Prüfungen, Testdaten der Bildgrundlage): Menge einer Auftragsposition um 1 erhöht -- /history mit
„850 → 851 m²“ (Bild), ohne „.000000“, ISO-Tag und „site“, die Zeitbuchungen mit „Baustellenzeit“; dieselben Prüfungen in der Historie der Projektmappe.

Im ersten Lauf rot und behoben: `_spalte()` mit einer Zeile ohne Feld („angelegt“) -- die Spaltensammlung lehnt `None` ab; jetzt vorher abgefangen.
Im ersten Suitenlauf rot und behoben: `test_v486::test_waechter_niemand_liest_die_standardpause` -- die Einheitenliste nannte die Standardpause
(seit 1.9.61 liest sie niemand); jetzt ohne sie, ein alter Eintrag dazu erscheint ohne Einheit.

Keine angepassten Erwartungen.

Gegenproben (Marker `GEGENPROBE`, byte-genau zurück, je FAILED in `test_v543`): IDs nicht aufgelöst -> 2; keine Einheit -> 2; Zahlen roh -> 4; UTC nicht
umgerechnet -> 1; Name des Datensatzes roh -> 2 und der Klicktest 4/6 (ISO-Tage und „site“ in /history und Projektmappe); die Einheit nicht angezeigt -> 1.

## Stufe 5, R2 (ab 1.9.124): die Akte je Projekt

Vorgabe 28.10.2026 (übernommen wie gegeben): „Stufe 5 · R2 – die Akte je Projekt. Start: HEAD e13058e (live), Arbeitskopie sauber. Version ab 1.9.124.
Nicht pushen. Festlegungen R1 Nachrunde: alle bestätigt. Vorlage (freigegeben): bildgrundlage/entwurf-stufe5/akte-uebersicht.html,
akte-leistungen.html, akte-verlauf.html, akte-zuordnung.html. Maße und Texte gelten, Zahlen sind Beispiel; Farben über Tokens, hell und dunkel;
Seitenkopf über den Baustein. 0. Vorweg: neue Bildgrundlage vom Stand e13058e (1.9.122 änderte jede Seite mit gesperrten Feldern). 1. Server zuerst:
Auftragsstatus nur noch läuft, pausiert, abgeschlossen, storniert – Liste am Server (sonst 422). Übergänge als eigene Aktionen mit Rückfrage: Pausieren
und Stornieren mit Pflichtbegründung; Abschließen nach Schlussrechnung oder mit Begründung „ohne Rechnung“; Fortsetzen. Begründung im Verlauf. Wirkung:
pausiert sperrt nichts. abgeschlossen: Monteure buchen nicht (Büro weiter, R5a); nicht mehr in der Plantafel, keine neuen Einsätze (F5). storniert: dazu
keine neuen Berichte; Rechnungen bleiben möglich (Teilleistung). Migration: beauftragt, arbeitsvorbereitung, in_ausfuehrung → läuft; die übrigen
bleiben; Rückweg mit Daten verweigert. Live sind alle 8 Aufträge „beauftragt“. Phase je Auftrag aus den Daten, eine Funktion, wie akte-zuordnung.html.
Der Projektstatus wird abgeleitet (Anfrage → Angebot → Phase des Auftrags), kein Feld mehr von Hand; Archivieren bleibt. Dashboard und Listen lesen die
abgeleiteten Werte. Im Bericht: Projekte, deren gespeicherter Status nicht zur Ableitung passt (live mindestens eines: „beauftragt“ ohne Auftrag). Zahlen
der Akte vom Server, je eine Rechnung, die AV und Projektmappe mitbenutzen (F18, F19, F21): Leistung netto (Auftragssumme mit Nachträgen, abgerechnet,
noch nicht abgerechnet), Zahlung brutto (in Rechnung gestellt, bezahlt, unbezahlt, überfällig), Stunden (Soll aus der Kalkulation nur „in Summe“,
gebucht, Fahrzeit, Baustelle und Werkstatt), je Position abgerechnet (Menge, %) und Std. Ist/Soll. 2. /projects/{id} wird die Akte wie die Vorlage: Kopf
mit Auftragswahl (nur bei mehreren Aufträgen) und Phasen; Reiter Übersicht · Angebote · Vertrag · Leistungen · Ausführung · Abnahme & Mängel · Rechnungen ·
Dateien · Verlauf. Inhalte von Projektmappe und Auftragsseite ziehen um wie akte-zuordnung.html; jede Funktion bleibt erreichbar (Liste aus dem Befund
Stufe 5 als Tabelle im Test, wie test_v520). Hauptknopf je Phase und Rolle. 3. /orders/{id} leitet auf /projects/{id}?auftrag={id}; Arbeitsvorbereitung,
Einsatzberichte, Rechnung und Checklisten führen in die Akte zurück. 4. Verlauf der Akte: ein Strom (Änderungen, Versand, Zahlungen, Berichte, Status,
Termine) mit Filter und Auftragswahl; Einträge einer Aktion (gleiches Konto, gleicher Pfad, wenige Sekunden) als eine Zeile mit aufklappbaren
Einzelheiten; „Zustellung nachtragen“ im „⋮“ der Zeile. 5. Rollen: Büro – Auftrag sieht Geld ohne Knöpfe; die Monteurin bekommt keine Akte (403 wie
heute). 6. Aus dem Befund, soweit die Akte sie berührt: D1, D2 (eine Rechnungsliste), D3, D5 („offen“ nur noch als „unbezahlt“ oder „noch nicht
abgerechnet“), D15, L2, L3, B4 (Status nie roh), E1 (Eingaben bleiben), F2 (nach der Schlussrechnung ist gesperrt, was aufs Dokument geht; Sachbearbeiter
und Bemerkungen bleiben frei). In Etappen committen, Server und Migration zuerst, je mit vollem Lauf. Tests (Angriff / Gegenprobe), u. a.: Status
außerhalb der Liste → 422; Stornieren ohne Begründung → 422; Abschließen ohne Schlussrechnung und ohne Begründung → 409; storniert: Einsatz planen,
Bericht anlegen, Buchung der Monteurin → 409 / Rechnung anlegen, Buchung des Büros → 200; Migration: jeder alte Wert landet richtig; Rückweg mit Daten
verweigert; Phase je Fall: kein Auftrag, Angebot, Zeit gebucht, Abnahme, Schlussrechnung; Zahlen der Übersicht = Summe der Rechnungen bzw. Buchungen,
im Test nachgerechnet; /orders/{id} → Akte mit gewähltem Auftrag; jede Funktion aus dem Befund erreichbar; Büro – Auftrag: kein Geld-Knopf in der Akte;
Monteurin 403. Ende: Bericht als .txt; ZIP: jeder Reiter neben der Vorlage (1440, hell), Übersicht dunkel, Büro – Auftrag, Projekt mit zwei Aufträgen,
Projekt ohne Auftrag (Phase Angebot).“

Die Vorlagen liegen unter `bildgrundlage/entwurf_stufe5/` (mit Unterstrich; die Vorgabe schreibt `entwurf-stufe5`). Festlegungen der R1 Nachrunde
(1.9.119–1.9.123) bestätigt am 28.10.2026, die Überschriften oben tragen das.

Vorweg (Punkt 0): neue Bildgrundlage vom Stand `e13058e` in einer Arbeitskopie auf genau diesem Commit (`git worktree add --detach … e13058e`, sauber;
Ziel `bildgrundlage/e13058e/`) -- 310 Bilder, 334 von 334 Prüfungen wie erwartet, Chrome/155.0.8059.40, 411 s. Grundlage für den Vergleich nach dem
Umbau der Akte.

Etappen (je eine Version mit vollem Lauf): 1.9.124 Auftragsstatus; 1.9.125 Phase und abgeleiteter Projektstatus; 1.9.126 Zahlen der Akte; danach der
Verlauf als Strom, die Akte selbst, die Weiterleitung von /orders/{id} und die Befundpunkte.

### R2, Punkt 1a (1.9.124): Auftragsstatus -- vier Werte, Übergänge mit Begründung

Befund (Stufe 5, 3.1, F2, F4, F5, F20): `Order.status` war freier Text, die Auftragsseite bot sechs Werte an (beauftragt, arbeitsvorbereitung,
in_ausfuehrung, pausiert, abgeschlossen, storniert), der Server prüfte gegen keine Liste, gesetzt über `PUT /api/orders/{id}` ohne Rückfrage; Wirkung
hatten nur „abgeschlossen“ und „storniert“, und das nur für die Monteurin; die Plantafel bot beide zum Einplanen an (F5); die Prüfungen verglichen teils
exakt, teils ohne Groß-/Kleinschreibung (F20).

- `app/auftragsstatus.py` (neu): `STATUS` = laeuft, pausiert, abgeschlossen, storniert mit Namen; `status_aendern()` als einziger Weg -- unter der Sperre
  der Auftragszeile (`lock_order_invoices()`), Übergänge `UEBERGAENGE` (pausieren aus läuft; fortsetzen aus pausiert oder abgeschlossen; abschließen und
  stornieren aus läuft oder pausiert; aus storniert nichts), Begründung Pflicht beim Pausieren, Stornieren und Fortsetzen aus „abgeschlossen“
  (`BegruendungFehlt`, 422), Abschließen ohne gültige Schlussrechnung bzw. abschließende Rechnung aus Aufwand nur ohne jede Rechnung (sonst
  `RECHNUNG_DA_TEXT`, 409) und mit Begründung „ohne Rechnung“ (sonst `OHNE_RECHNUNG_TEXT`, 409); `status_info()` (Übergänge mit Pflicht, was
  Abschließen verlangt samt gebuchter Stunden, letzter Wechsel); `wert()` liest jeden Status klein und ohne Leerraum (F20) -- `einsatz_gesperrt()`,
  `bericht_gesperrt()`, `geschlossen()`, `storniert()`, `pause_begruendung()`.
- `OrderStatusChange` (neu, `order_status_changes`): alter und neuer Status, Begründung, „ohne Rechnung“, Zeitpunkt, Konto und Name; unveränderlich und nie
  gelöscht (ORM-Sperre); im Änderungsprotokoll als Art „Auftragsstatus“ („AUF-… · läuft → pausiert“) unter dem Projekt, daneben die Zeile „Auftrag ·
  Status“ alt -> neu.
- Routen: `POST /api/orders/{id}/status` (`OrderStatusChangeRequest`: `Literal` der vier Werte, Pausieren und Stornieren ohne Begründung 422; 409 bei
  Konflikt, 404) und `GET /api/orders/{id}/status-changes`, je ab Büro – Auftrag. `OrderUpdate` und `OrderCreateFromQuote` lehnen einen Status mit 422
  ab (`STATUS_NUR_UEBER_AKTIONEN`), `update_order_header()` ebenso; ein neuer Auftrag beginnt immer mit „läuft“. `OrderOut` trägt `status_label` und
  `status_info`.
- Wirkung: „abgeschlossen“ und „storniert“ -- `create_slot()` lehnt ab (`AuftragGeschlossen`, 409; ein bestehender Einsatz lässt sich weiter verschieben
  und löschen), die Plantafel nimmt sie nicht mehr unter „Nicht eingeplant“ und nicht mehr in die Auswahl beim Einplanen (`planning.html`); die
  Monteurin bucht nicht (seit 1.9.81, jetzt 409 statt 403). „storniert“ dazu: kein neuer Bericht für jede Rolle (`create_report()` und die Route, 409;
  bis 1.9.123 nur die Monteurin, 403; der Dialog der Monteurin `GET /api/field-view/auftraege/{id}/bericht-anlegen` ebenso 409). Rechnungen und
  Buchungen des Büros unverändert. „pausiert“ sperrt nichts: Einsatz und Rückstand der Plantafel tragen `order_status` und `order_status_reason`
  („Auftrag pausiert · <Begründung>“).
- Migration `8d3f6a2c91e7`: Tabelle `order_status_changes`; beauftragt, arbeitsvorbereitung, in_ausfuehrung, leer und jeder unbekannte Wert -> laeuft;
  pausiert, abgeschlossen, storniert bleiben (Schreibweise vereinheitlicht). `downgrade()` verweigert, solange ein Auftrag „läuft“ oder ein
  Statuswechsel festgehalten ist; sonst entfernt es die Tabelle.
- Oberfläche: `_auftragsstatus.html` (neu) -- Kennzeichen mit Begründung, die Knöpfe der Übergänge, der Dialog mit Wirkung, Begründung (Pflicht
  gekennzeichnet) und bei „Abschließen“ dem Stand der Rechnungen bzw. den Stunden, die ohne Rechnung nicht abgerechnet werden; abschließende Aktion über
  `abschliessen()`. Auftragsseite: Karte „Status“ statt der Auswahl in „Auftragsdaten“, der Kopf zeigt den Status lesbar (B4, bis zur Akte);
  `_statuskennzeichen.html` Gruppe `auftrag` mit den vier Werten. „Angebot beauftragen“ ohne Auswahl „Status“. Prüfabfrage
  `scripts/pruefabfrage_auswahlwerte.sql`: `orders.status` gegen die vier Werte.

#### Festlegungen 1.9.124 (Nr. 2–8 bestätigt am 29.10.2026; Nr. 1 ersetzt durch die Nachrunde, Punkt 2 -- 1.9.131)

1. Fortsetzen geht aus „pausiert“ ohne und aus „abgeschlossen“ mit Begründung; ein stornierter Auftrag bleibt storniert (kein Weg zurück).
2. Stornieren geht aus „läuft“ und „pausiert“, nicht aus „abgeschlossen“ (erst fortsetzen).
3. „Ohne Rechnung“ abschließen nur, solange am Auftrag keine Rechnung besteht -- auch kein Entwurf; stornierte Rechnungen und ihre Stornos zählen nicht
   (nach dem „Parkplatz vor dem Echtbetrieb“, 13.10.2026). Mit Abschlägen schließt die Schlussrechnung ab. Mit Schlussrechnung ist die Begründung
   freiwillig.
4. Den Status ändert jedes Büro (ab Büro – Auftrag) -- es ist keine Aktion mit Geld.
5. Was am Stand des Auftrags scheitert, antwortet 409: neuer Einsatz, neuer Bericht, Buchung der Monteurin (bis 1.9.123 403), auch der Dialog
   „Bericht anlegen“ der Monteurin.
6. Ein leerer oder unbekannter Status wird bei der Migration „läuft“; andere Schreibweisen der drei bleibenden werden vereinheitlicht.
7. Bestehende Einsätze eines abgeschlossenen oder stornierten Auftrags bleiben in der Plantafel und lassen sich verschieben und löschen; gesperrt ist
   nur ein neuer.
8. Die Begründung einer Pause steht in der Plantafel am Einsatz und im Rückstand.

#### Tests und Prüfung

Neu `tests/test_v544_auftragsstatus.py` (26 Tests): neuer Auftrag „läuft“ mit Übergängen und Abschluss-Info; ein Status außerhalb der Liste (sechs Werte,
darunter die alten und „LAEUFT“) 422 ohne Änderung und Historie; Pausieren und Stornieren ohne Begründung (leer, nur Leerzeichen) 422; PUT und
Beauftragen mit Status 422, ohne Status 200 bzw. „läuft“; Pausieren und Fortsetzen mit Historie, Person und Änderungsprotokoll („Auftragsstatus“ und
„Auftrag · Status“); Übergänge aus „storniert“ und derselbe Status 409; Abschließen ohne Schlussrechnung und ohne Begründung 409 mit dem Weg, mit
Begründung „ohne Rechnung“ festgehalten; mit Abschlag (Entwurf, dann festgeschrieben) 409 mit der Nummer, nach der Schlussrechnung ohne Begründung;
Fortsetzen aus „abgeschlossen“ nur mit Begründung; Historie unveränderlich; pausiert sperrt nichts (Buchung, Bericht, Einsatz mit Begründung in der
Antwort); abgeschlossen: Einsatz 409, nicht im Rückstand (ein offener Auftrag bleibt), Monteurin 409 ohne Buchung, Büro bucht, Bericht geht;
storniert: Einsatz, Bericht (Büro und Monteurin) und Buchung der Monteurin 409, Rechnung (Büro – Finanzen) und Buchung des Büros 200; `create_report()`
ohne Route gesperrt; Statusregeln ohne Groß-/Kleinschreibung; Auftragsseite und Angebot ohne Auswahl „Status“, der Baustein eingebunden.
Neu `tests/test_v544_auftragsstatus_migration.py` (3 Tests): die Regel je Wert (zehn Werte samt Schreibweisen und unbekannter); Probe auf SQLite und
PostgreSQL (Wegwerf-Schema): hoch -- jeder alte Wert richtig, alles andere am Auftrag unverändert, Tabelle da; runter mit „läuft“ verweigert, nichts
geändert; mit einem Statuswechsel (ohne „läuft“) ebenso verweigert; ohne beides zurück auf `3e9b7c41d2a8`, Tabelle weg.

Angepasste Erwartungen:
- `test_v504_keine_zeiten_auf_abgeschlossene.py` (7 Tests über `_abgelehnt()`): Buchung der Monteurin am abgeschlossenen bzw. stornierten Auftrag 403 ->
  409 (Meldung unverändert).
- `test_v511::test_buero_bucht_auf_geschlossenem_auftrag_monteurin_nicht[abgeschlossen|storniert]`: Monteurin 403 -> 409.
- `test_v499::test_abgeschlossen_storniert_und_alt_nicht_in_der_liste[storniert]`: Bericht der Monteurin zum stornierten 403 -> 409.
- `test_v505::test_zeiten_gesperrt_folgt_dem_buchen`: Nachtrag der Monteurin 403 -> 409.
- `test_v502::test_storniert_403_und_nichts_angelegt` -> `test_storniert_409_und_nichts_angelegt`: 403 -> 409.
- `test_v502::test_buero_unveraendert` (Büro legt zum stornierten an, 200) -> `test_buero_zum_stornierten_ebenso_409`: 409 mit `BERICHT_STORNIERT`, zum
  abgeschlossenen 200.
- `test_v502::test_daten_zum_anlegen_storniert_403_unbekannt_404` -> `…_409_…`: 403 -> 409.
- `test_v445::test_jeder_wert_des_servers_steht_in_der_tabelle`: `FESTE_LITERALE["orders.status"]` und die Auswahl der Auftragsseite in der Tabelle ->
  `app/auftragsstatus.py::STATUS` gleich der Tabelle (die Auswahl gibt es nicht mehr).
- `test_v445::test_kennzeichen_lesbar_und_in_der_farbe_der_bedeutung`: Beispiele `auftrag/beauftragt` („Beauftragt“, info) -> `auftrag/laeuft` („Läuft“,
  info); `auftrag/in_ausfuehrung` („In Ausführung“, info) -> `auftrag/pausiert` („Pausiert“, neutral).
- `test_v447::test_auftrag_status` entfällt (hielt einen unbekannten Status in der Auswahl der Auftragsseite gewählt -- Auswahl und unbekannte Werte gibt es
  nicht mehr); `test_v447::test_feste_listen_der_pruefabfrage_wie_auf_den_seiten['orders.status]`: Quelle Auswahl der Auftragsseite -> `STATUS` des
  Servers, die Prüfabfrage mit den vier Werten.
- `test_v364`: `orders.status` aus `FESTE_LITERALE` ("beauftragt", "storniert", "abgeschlossen") nach `FESTE_WERTE` (`app/auftragsstatus.py::STATUS`), dazu
  `order_status_changes.old_status`/`new_status`.
- `test_v070::test_order_changes_are_audited_with_project`: Statuswechsel über `update_order_header(status="arbeitsvorbereitung")`, alt „beauftragt“ ->
  über `status_aendern(…, "pausiert", …)`, alt „laeuft“ neu „pausiert“; `create_order()` ohne `status` (nur Aufbau, 4 Tests).
- `test_v381_zahlungen_migration.py` (beide Proben): hoch bis `head` -> bis `3e9b7c41d2a8` (`BIS`) -- der Rückweg über `8d3f6a2c91e7` verweigert jeden
  Bestand mit Auftrag (nur Aufbau).
- `test_v334::BAUSTEINE` um `_auftragsstatus.html` (nur Aufbau, Regel 36: die Attrappe bindet ein, was die Seite einbindet; ohne den Eintrag scheiterten
  die node-Tests der Auftragsseite in v334, v438, v439, v447, v451 an „auftragsstatusEinrichten is not defined“).
- `test_v399::ABSCHLIESSEND` um `_auftragsstatus.html::statusDialogSenden` (neue abschließende Aktion).
- `klicktest_bericht_ohne_einsatz` „S (storniert) direkt über die API: 403 mit der Meldung“ -> 409 mit der Meldung.
- `klicktest_zeiten`: Testdaten der zwei offenen Aufträge mit Status „laeuft“ statt „beauftragt“ (nur Aufbau).
- `klicktest_rahmen` „Datensatzkopf einsatzbericht (buero) hell/dunkel: Status“: „Beauftragt“ (info) -> „Läuft“ (info) -- im ersten Lauf der Klicktests
  rot, die Erwartung war mit 1.9.124 veraltet.
- `klicktest_zeiten_abgeschlossen` „Das Büro schließt A ab“: `PUT /api/orders/{id}` mit Status -> `POST /api/orders/{id}/status` mit Begründung „ohne
  Rechnung“ (200) -- im ersten Lauf rot (422 im Ablauf, der alte Weg ist gesperrt).

Klicktests vor dem Commit: alle 99 (die Auftragsseite und der Status berühren fast jede): 97 wie erwartet, die zwei oben rot -- angepasst, danach beide
grün (13/13, 1436/1436).

Im ersten Suitenlauf rot und behoben: die eben genannten (37 Tests); dazu `test_v398` -- der Baustein nutzt `abschliessen()` und band `_speichern.html`
nicht ein (jetzt auch `_zahl.html` und `_berlin_date.html`).

Gegenproben (Marker `GEGENPROBE`, byte-genau zurück, je FAILED in `test_v544`): die Liste nur im Schema weg -> grün (der Server lehnt in
`status_aendern()` ein zweites Mal ab, 422); an beiden Stellen weg -> 6 Tests; Abschließen ohne Begründung erlaubt -> 1; `einsatz_gesperrt()` aus ->
2; `bericht_gesperrt()` aus -> 1 (die Route prüft vorher selbst); Route und `bericht_gesperrt()` aus -> 2; Buchung der Monteurin wieder 403 -> 2.

### R2, Punkt 1b (1.9.125): Phase je Auftrag, abgeleiteter Projektstatus

Befund (Stufe 5, 3.2, 3.9, F7): die Phasen standen in keinem Feld; `Project.status` war frei wählbar (Neues Projekt ohne „Angebot“, Projektmappe mit,
Dashboard-Labels ohne „angebot“), die Umwandlung einer Anfrage setzte „angebot“, jede Beauftragung „beauftragt“ -- auch aus „abgeschlossen“; das Dashboard
zählte feste Wörter (planung, beauftragt, ausfuehrung).

- `app/akte.py` (neu): `signale()` -- je Auftrag erste Buchung und gebuchte Stunden, erster begonnener und nächster geplanter Einsatz, erster Bericht,
  früheste gültige abgenommene bzw. jüngste verweigerte Abnahme, abschließende Rechnung (`closing_invoices()`), Stand des Vertrags; je Art eine Abfrage
  für alle Aufträge. `phasen()` -- fünf Schritte mit „erreicht“, „jetzt“ (die letzte erreichte) und Text wie in `akte-uebersicht.html` („A-… ·
  angenommen 26.08.“, „26.08. · VOB/B · Vertrag unterschrieben“, „seit 15.09. · 186,0 h gebucht“ bzw. „geplant ab …“/„noch nicht begonnen“, „abgenommen …“
  bzw. „verweigert …“/„noch nicht erfasst“, Nummer und Tag der Schlussrechnung bzw. „nach der Abnahme“; Tage im laufenden Jahr ohne Jahr).
  `phasen_ohne_auftrag()` -- vor dem ersten Auftrag die Phase des Angebots (das jüngste nicht abgelehnte, mit Stand). `projekt_status_alle()` -- ohne
  Angebot `anfrage`, mit Angebot ohne Auftrag `angebot`, sonst die früheste Phase der laufenden und pausierten Aufträge; alle geschlossen: `abgeschlossen`
  (mindestens einer) bzw. `storniert`.
- `OrderOut` trägt `phase`, `phase_label`, `phasen`; `OrderListOut` (beide Listen) `status_label`, `phase`, `phase_label`. `ProjectListOut` und
  `ProjectDetailOut` tragen den abgeleiteten `status` mit `status_label` (Liste, Anlegen, Archivieren, Kopieren, Pipeline-Spalte, Detail, Anfrage).
- `ProjectCreate`/`ProjectUpdate`: ein Status ergibt 422 (`PROJEKTSTATUS_ABGELEITET`); `update_project()` schreibt keinen mehr; `create_order_from_quote()`
  und `convert_inquiry` ebenso nicht (Vorgabe der Spalte beim Anlegen bleibt „anfrage“). Die Spalte bleibt -- niemand liest sie.
- Seiten: „Neues Projekt“ und der Dialog „Projektmappe bearbeiten“ ohne Auswahl „Status“; Projektliste (Tabelle, Kanban, Suche) und Kopf der Projektmappe
  zeigen `status_label` (B4); Dashboard: „Aktive Projekte“ = Status auftrag, ausfuehrung, abnahme, schlussrechnung, das Widget alle außer abgeschlossen und
  storniert, Spalte „Status“ mit `status_label`. `_statuskennzeichen.html`: Gruppen `projekt` und `phase`.
- `scripts/pruefe_projektstatus.py` (neu, nur lesend wie `pruefe_stornos.py`): je Projekt (ohne Mustervorgänge) gespeicherter gegen abgeleiteten Status
  nach einer Tabelle „passt“ (anfrage -> Anfrage; angebot -> Angebot; planung -> Angebot, Auftrag; beauftragt -> Auftrag bis Schlussrechnung; ausfuehrung
  -> Ausführung, Abnahme; abgeschlossen -> Schlussrechnung, Abgeschlossen, Storniert); Treffer mit Nummer, Bezeichnung, beiden Werten, Zahl der Angebote und
  Aufträge, archiviert. Aufruf auf dem Server wie bei den Stornos. Die Prüfabfrage `pruefabfrage_auswahlwerte.sql` prüft `projects.status` nicht mehr.

#### Festlegungen 1.9.125 (bestätigt am 29.10.2026)

1. Ein Einsatz zählt für die Ausführung erst ab seinem Beginn (bis heute); ein geplanter in der Zukunft zeigt „geplant ab …“, die Phase bleibt „Auftrag“.
2. Eine verweigerte Abnahme erreicht die Phase „Abnahme“ nicht (der Schritt zeigt „verweigert …“); eine verworfene zählt gar nicht.
3. Der Projektstatus mit mehreren Aufträgen ist die früheste Phase der laufenden und pausierten -- ein Projekt ist erst fertig, wenn jeder Auftrag es ist;
   stornierte zählen dabei nicht, sind alle geschlossen, „Abgeschlossen“ (mindestens einer abgeschlossen) bzw. „Storniert“.
4. Vor dem ersten Auftrag zeigt die Phase das jüngste nicht abgelehnte Angebot mit seinem Stand; ohne Angebot ist kein Schritt erreicht (Status „Anfrage“).
5. Die Spalte `projects.status` bleibt bis zu einer Aufräumrunde stehen (kein Schema-Rückweg nötig); geschrieben wird nur noch ihre Vorgabe beim Anlegen.
6. „Aktive Projekte“ im Dashboard sind Projekte mit einem laufenden oder pausierten Auftrag (bis 1.9.124: planung, beauftragt, ausfuehrung).
7. Das Kennzeichen „Anfrage“ trägt die Farbe eines Entwurfs, die Phasen die von „läuft“, „Abgeschlossen“ die von „erledigt“, „Storniert“ ruht.

#### Tests und Prüfung

Neu `tests/test_v545_phase_projektstatus.py` (14 Tests): Phase ohne Auftrag (ohne und mit Angebot); Auftrag ohne Ausführung (alle fünf Texte); Ausführung
ab der ersten Buchung mit den gebuchten Stunden; Einsatz in der Zukunft nur „geplant ab“, begonnener zählt; ein Bericht beginnt die Ausführung; Abnahme
nur gültig und abgenommen (verweigert und verworfen nicht); Schlussrechnung erst festgeschrieben (der Entwurf zählt nicht); Phase in der Antwort des
Auftrags; Projektstatus Anfrage, Angebot, Auftrag (gespeichert „beauftragt“ zählt nicht); früheste Phase bei zwei Aufträgen (pausiert, storniert,
abgeschlossen, nur storniert); Status beim Anlegen und Ändern 422, ohne 200, Liste mit dem abgeleiteten Wert und Namen; Beauftragen schreibt den gespeicherten
Status nicht mehr; Projektliste, Projektmappe, Neues Projekt und Dashboard lesen den abgeleiteten (Struktur); das Prüfskript (ohne Treffer 0, „beauftragt“
ohne Auftrag als Treffer mit der genauen Zeile, 1).

Angepasste Erwartungen:
- `test_v065::test_project_masterdata_can_be_updated`: nach dem Ändern Status „planung“ (gesendet) -> „anfrage“ (abgeleitet, kein Angebot); Anlegen und
  Ändern ohne Status.
- `test_v209::test_create_quick_service_order_reparatur_creates_full_chain`: `project.status == "beauftragt"` -> `projekt_status() == "auftrag"`.
- `test_v275::test_move_pipeline_column_changes_only_the_column_never_status`: Status der Antwort = gespeicherter („in_arbeit“) -> abgeleitet („anfrage“);
  der gespeicherte bleibt unverändert (wie bisher geprüft).
- `test_v372::test_today_postgresql_sync_without_titles_invoices_or_time_entries_works`: Projektstatus nach dem Abgleich „beauftragt“ -> unverändert gegenüber
  vor dem Abgleich (das Beauftragen schreibt ihn nicht mehr).
- `test_v447::test_projekt_status` entfällt (die Auswahl „Status“ der Projektmappe gibt es nicht mehr); `test_v447::test_feste_listen…['projects.status]`
  entfällt mit der Zeile der Prüfabfrage.
- Nur Aufbau, Projekt ändern ohne Status: `test_v066::test_project_change_logs_actor_old_and_new_value`, `test_v382::test_client_change_with_drafts_only_is_allowed`,
  `test_v383` (drei Tests zum Kundenwechsel), `test_v373::test_project_with_confirmed_foreign_property_can_be_saved_unchanged`,
  `test_v344::test_client_change_refused_while_the_new_client_is_a_participant`, `test_v347::test_client_change_locked_once_an_order_has_a_frozen_contract`.

Im ersten Suitenlauf rot und behoben (17 Tests): die eben genannten; dazu `test_v315` (eine Rundung mit `quantize()` ohne Rundungsart in `app/akte.py`,
jetzt `round_half_up()`), `test_v109` (ein lokaler Import einer Konstante in `app/routers/inquiries.py`, jetzt auf Modulebene) und `test_v194` (der Test
liest die ersten 1500 Zeichen von `get_project_detail()` -- `archived` steht jetzt vorn im Aufruf).

Klicktests (Endlauf 97 von 99, beide roten aus demselben Grund, danach 2 von 2): `klicktest_mahnwesen` „API: Kundenwechsel mit festgeschriebener Rechnung 409“ schickte den Status mit -> jetzt ohne (sonst 422); `klicktest_abgleich_sperre` „Auftrag frei: Projektstatus bleibt“: alt „ausfuehrung“ (gespeichert), neu „auftrag“ (abgeleitet, kein Einsatz, keine Buchung).

Gegenproben (Marker `GEGENPROBE`, byte-genau zurück, je FAILED in `test_v545`): späteste statt früheste Phase -> 1; ein geplanter Einsatz zählt -> 1; eine
verweigerte Abnahme zählt -> 1; der Status in `ProjectUpdate` ohne Ablehnung -> 1.

### R2, Punkt 1c (1.9.126): Zahlen der Akte

Befund (Stufe 5, D1, D5, F18, F19, F21): Summen des Auftrags dreimal auf der Auftragsseite, „Noch offen“ = noch nicht abgerechnet neben „Offen“ =
unbezahlt; `planned_hours()` zählte jede Position mit Kalkulation, auch außerhalb der Summe; die AV verglich „produktiv“ (ohne Fahrzeit und
Schlechtwetter, mit „Sonstige“) mit dem Soll, die Berichtsliste zeigte „Gesamt“; GET /api/orders lieferte `invoiced_net`, `invoiced_gross`,
`planned_hours` nur mit der Vorgabe 0.

- `app/akte.py` (Teil „Zahlen der Akte“): `soll_stunden()` (Kalkulation × Menge, nur „in Summe“), `leistung()` (Auftragssumme aus
  `app/invoices.py::order_sum()`, Nachträge, abgerechnet aus `compute_order_billing_progress()`, `vollstaendig` aus der abschließenden Rechnung,
  `noch_nicht_abgerechnet`, `unter_auftragssumme`, `ueber_auftragssumme`), `zahlung()` (je festgeschriebener Rechnung ohne Storno die Zeile aus
  `invoice_overview_rows()`: Brutto, bezahlt, Skonto, `overview.open/retained/credit/refunded`, überfällig = mahnfähiger Betrag nach der Fälligkeit),
  `stunden()` (gebucht, Fahrzeit, Baustelle & Werkstatt, ohne Position, Abweichung, je Zeitart, je Mitarbeiter mit Tagen), `ist_je_position()`,
  `positionen()` (Stand der zuletzt festgeschriebenen Abschlagsrechnung nach Leistungsstand bzw. Schlussrechnung wie
  `get_previous_cumulative_ist()`, Quelle des Stands), `zahlen()`.
- `GET /api/orders/{id}/zahlen` (`AkteZahlenOut`, ab Büro – Auftrag; die Monteurin 403).
- `app/work_preparation.py`: `planned_hours()` = `soll_stunden()`; die Stundenfelder der AV aus `stunden()` (`_stunden_felder()`), auch in der
  Vorschau ohne AV. Die Seite benennt sie wie die Akte: „Soll (Kalkulation)“, „Gebucht (alle Zeitarten)“, „davon Fahrzeit“, „Baustelle & Werkstatt“,
  „Abweichung Baustelle & Werkstatt − Soll“.
- GET /api/orders: `invoiced_net`, `invoiced_gross`, `planned_hours` wie GET /api/projects/{id}/orders (F21).
- `app/time_tracking.py`: `order_actual_hours()` und `order_item_actual_hours()` entfallen (keine zweite Rechnung).

#### Festlegungen 1.9.126 (bestätigt am 29.10.2026)

1. Ist gegen Soll = gebuchte Stunden Baustelle und Werkstatt (die Zeitarten der Kalkulation); „Sonstige Arbeitszeit“ und Schlechtwetter zählen im
   Gebuchten, nicht im Vergleich (bis 1.9.125 verglich die AV „produktiv“, also mit „Sonstige“).
2. Std. Ist je Position: Baustelle und Werkstatt mit Bezug auf die Position; was ohne Position gebucht ist, steht als „ohne Position“ daneben, die
   Fußzeile nimmt die Summe der Stunden (dieselbe Zahl wie in der Übersicht).
3. Nach der abschließenden Rechnung ist nichts mehr „noch nicht abgerechnet“; liegt die Endrechnung unter der Auftragssumme, steht der Rest als
   „weniger abgerechnet als beauftragt“, über der Auftragssumme als „mehr abgerechnet“.
4. „Bezahlt“ ist wie „Bezahlt (gesamt)“ in Finanzen: Zahlungen auf die Rechnungen abzüglich der Erstattungen an der Schlussrechnung; Skonto steht
   getrennt, so dass in Rechnung gestellt = bezahlt + Skonto + unbezahlt.
5. „Überfällig“ ist der mahnfähige Betrag der Rechnungen nach ihrer Fälligkeit (ohne Einbehalt), mit dem Tag der ältesten Fälligkeit.
6. Abgerechnet je Position ist die kumulierte Ist-Menge der zuletzt festgeschriebenen Abschlagsrechnung nach Leistungsstand bzw. Schlussrechnung
   (wie der Vorschlag der nächsten Rechnung); ein Storno nimmt den Stand zurück, ein Entwurf zählt nicht, ein pauschaler Abschlag hat keinen Stand.
7. Prozent ganzzahlig, kaufmännisch gerundet; ohne Bezugsgröße (Auftragssumme, Menge, Soll 0) keine Angabe.

#### Tests und Prüfung

Neu `tests/test_v546_akte_zahlen.py` (8 Tests), jede Zahl aus den Rechnungen bzw. Buchungen nachgerechnet: Auftrag mit drei Positionen, einer
Bedarfsposition außerhalb der Summe und einem Nachtrag ohne Kalkulation; zwei festgeschriebene Abschläge (bezahlt; teilweise bezahlt und überfällig),
ein dritter storniert, ein vierter im Entwurf; Buchungen zweier Mitarbeiter in allen Zeitarten mit und ohne Position, ein laufender Timer. Leistung
(Summe der Netto der gültigen Rechnungen), Zahlung (Summe Brutto, bezahlt, offen wie Finanzen, überfällig mit Tag), Stunden (Summe der gebuchten,
Soll ohne die Bedarfsposition, je Mitarbeiter), je Position (Stand aus dem 2. Abschlag, nicht aus dem stornierten; Ist und Soll), nach der
Schlussrechnung nichts mehr offen, ohne Rechnung und Buchung alles 0; dieselben Zahlen in AV, GET /api/orders und GET /api/projects/{id}/orders;
der Endpunkt für die drei Büro-Rollen 200, für die Monteurin 403, unbekannter Auftrag 404.

Angepasste Erwartungen:
- `test_v100::test_manual_productive_and_travel_hours_are_separated`: `order_actual_hours()` -> `app/akte.py::stunden()`, „produktiv“ 7,50 ->
  „Baustelle & Werkstatt“ 7,50, Fahrzeit und gebucht unverändert; je Position über `ist_je_position()` (gleicher Wert).
- `test_v440::DRITTE_PERSON`: der Eintrag „Sie entsprechen automatisch“ (Hinweis der AV) entfällt -- der Satz ist neu gefasst, ohne „Sie“.

Gegenproben (Marker `GEGENPROBE`, byte-genau zurück, je FAILED in `test_v546`): Soll auch aus Positionen außerhalb der Summe -> 2; „Sonstige“ zählt
zu Baustelle & Werkstatt -> 2; Stand je Position auch aus dem Storno -> 1. Die Erstattung an der Schlussrechnung ist in den Testdaten nicht
vorhanden (die Rechnung „bezahlt“ übernimmt die Formel von Finanzen, `test_v394`), dafür keine eigene Gegenprobe.

### R2, Punkt 4 (1.9.127): Verlauf der Akte, Server

Befund (Stufe 5, D8, F14, 7b): Historie der Projektmappe Zeile für Zeile (eine Aktion als viele Zeilen, ohne Bezug auf den Auftrag), Versand
getrennt im Reiter „Versand“ und im Versandprotokoll, „Zustellung nachtragen“ nur am Dokument; Befunde gar nicht im Änderungsprotokoll.

- `app/akte_verlauf.py` (neu): `auftraege_je_zeile()` (je Art eine Abfrage: Auftrag, Position, LV-Titel, Revision, Status, Rechnung,
  Rechnungsposition, Mahnung, Nebenforderung, Verzugsbeginn, Abnahme, Mangel, Einsatzbericht, Befund, Checkliste samt Unterschrift und Foto,
  Arbeitsvorbereitung samt AV-Zeilen, Plantafel-Einsatz und -Kapazität, Angebot über `Order.source_quote_id`, Zahlung über ihre Zuordnungen -- auch
  mehrere Aufträge), `auftraege_je_versand()`, `gruppieren()` (gleiches Konto, gleiche Methode und gleicher Pfad, höchstens `GRUPPE_SEKUNDEN` = 5 zur
  ersten Zeile; ohne Pfad jede Zeile für sich), `versand_zuordnen()` (zu einer Gruppe desselben Kontos innerhalb von 5 s -- zuerst der, die dasselbe Dokument betrifft, `VERSAND_ART`, sonst der nächsten --, sonst eigene Zeile),
  `ueberschrift()` (Hauptzeile nach `VORRANG`, „angelegt“ vor „geändert“; Status mit Begründung, Versand mit Weg und Empfängern), `strom()` (Filter,
  Seiten über `vor`).
- `GET /api/projects/{id}/verlauf?auftrag=&art=&vor=` (ab Büro – Auftrag): höchstens `ZEILEN_JE_ABRUF` = 600 Protokollzeilen je Abruf, ohne
  Zeitbuchungen schon in der Abfrage; gibt es ältere, fällt die letzte Gruppe weg und `vor` zeigt auf sie (nichts doppelt, nichts verloren);
  unbekannte Art 422, Auftrag eines anderen Projekts 404. Die Schwärzung ist jetzt `app/routers/audit.py::sichtbar()` -- dieselbe für
  /api/audit-logs und den Verlauf. Je Versand `zustellung_nachtragen` und `can_record_outcome` nach `darf_geld()` wie GET /api/email-dispatches.
- `app/audit.py`: `Finding` („Befund“) protokolliert, Bezeichnung „Beschreibung · Auftrag“, Projekt über den Bericht; `app/verlauf_namen.py` liest
  Schwere, Maßnahme und Stand lesbar. `dispatch_to_dict()` trägt `created_by_user_id` (Zuordnung zur Aktion).

#### Festlegungen 1.9.127 (bestätigt am 29.10.2026)

1. Eine Aktion = dasselbe Konto, dieselbe Anfrage (Methode und Pfad) und höchstens 5 Sekunden zur ersten Zeile; Einträge ohne Anfrage (Skripte,
   Grunddaten) stehen einzeln.
2. Ein Versand gehört in die Zeile der Aktion desselben Kontos, die höchstens 5 Sekunden daneben liegt -- zuerst in die, die dasselbe Dokument
   betrifft, sonst in die nächste; die Zeile heißt dann „Versand“.
3. Mit gewähltem Auftrag zeigt der Strom dessen Zeilen und die projektweiten (Projekt, Dateien, Beteiligte, Termine, Angebot ohne Auftrag); eine
   Zahlung auf Rechnungen mehrerer Aufträge steht bei jedem.
4. Zeitbuchungen stehen nicht im Verlauf der Akte (sie stehen unter „Zeiten“); Arbeitsvorbereitung, Einsätze und Termine schon.
5. Arten: Status = Statuswechsel des Auftrags; Zahlung = Zahlungseingang, Nebenforderung, Verzugsbeginn; Bericht = Einsatzbericht, Befund,
   Checkliste; Termin = Termin, Plantafel-Einsatz; alles andere Änderung.
6. Befunde kommen ins Änderungsprotokoll (bis 1.9.126 gar nicht) -- die Monteurin sieht das Protokoll nicht, das Büro auch auf /history.

#### Tests und Prüfung

Neu `tests/test_v547_akte_verlauf.py` (8 Tests): zwei Änderungen einer Anfrage als eine Zeile mit beiden Einzelheiten und dem Auftrag; Status mit
Begründung, Filter nach Art; Filter nach Auftrag (projektweite Zeile bei beiden, die Pause des zweiten nur bei ihm); keine Zeitbuchung; Versand in der
Zeile der Rechnung, Zahlung mit Auftrag; Gruppenregel (Konto, Pfad, Zeit); Seiten mit kleiner Grenze ergeben genau den ganzen Strom; Rollen (Büro –
Auftrag 200, Monteurin 403, unbekanntes Projekt 404, unbekannte Art 422).

Im ersten Lauf der neuen Tests aufgefallen und behoben: ein Versand ging an die zeitlich nächste Aktion desselben Kontos (eine Zahlung 0,1 s danach)
statt an die Rechnung, die er versendet -- seitdem zählt zuerst dasselbe Dokument (Festlegung 2); die Begründung eines Statuswechsels steht im
Schnappschuss des Anlegens (`details`), nicht in einer eigenen Zeile. Im vollen Lauf aufgefallen: zwölf Felder des Befunds hatten keinen Namen
für die Historie (`test_v436`, `test_v438`: in der Historie stand der Spaltenname) -- seitdem in `FIELD_LABELS` mit den Wörtern der Berichtsseite
(Schwere, Maßnahme, Wiedervorlage, Folgeauftrag …).

Gegenproben (Marker `GEGENPROBE`, byte-genau zurück, je FAILED in `test_v547`): Zeitbuchungen im Strom -> 1; Gruppe ohne Prüfung von Pfad und Zeit
-> 5; Filter nach Auftrag ausgeschaltet -> 1; `vor` auf die älteste statt die jüngste Zeile der weggelassenen Gruppe -> 1.

### R2, Punkt 2 (1.9.128): Kopf und Übersicht der Akte, Server

Befund (Stufe 5, D1, D3, F2, L3, 7a): die Projektmappe zeigte Summen über alle Aufträge ohne Auswahl, kein „was jetzt“, keine Termine des Auftrags;
Auftragsdaten nach der Schlussrechnung frei änderbar; „Zeiten“ aus Mappe und Auftrag nur im laufenden Monat.

- `app/akte.py`: `auftrag_waehlen()`, `ansteht()`, `einsaetze()`, `ausfuehrung()`, `befunde()`, `termine()`, `hauptaktion()`, `akte_kontext()`;
  `GET /api/projects/{id}/akte?auftrag=` (ab Büro – Auftrag, Monteurin 403): Aufträge mit Summe, Status und Phase, gewählter Auftrag, Phasen (ohne
  Auftrag die des Angebots), jüngstes nicht abgelehntes Angebot, was ansteht, Termine, Ausführung (Arbeitsvorbereitung, Einsätze, Berichte,
  Checklisten je Stand, Stunden aus `stunden()`), Befunde, „Bericht anlegen“ nach `bericht_zum_auftrag_moeglich()`, Zähler der Reiter, Hauptaktion
  (der Router entscheidet mit `darf_geld()`).
- `app/invoices.py::rechnungsart_text()`; `invoice_overview_row()` und `invoice_to_dict()` mit `art_text`, `project_id`, `net_total`, Leistungszeitraum
  (Schemas `InvoiceOverviewOut`, `InvoiceListOut`).
- `app/orders.py::order_to_dict()` mit `section_totals` (Summe je LV-Titel samt Untertiteln, Positionen „in Summe“; Nachträge eigens); `OrderOut`
  trägt sie, das reduzierte Schema der Monteurin nicht.
- F2: `update_order_header()` unter der Sperre der Auftragszeile -- nach der Schlussrechnung (bzw. der abschließenden Rechnung aus Aufwand,
  `final_lock_reason()`) 409 `OrderLocked` für jedes Feld außer `FREI_NACH_SCHLUSS` (Sachbearbeiter, Bemerkungen).
- L3: `app/zeiten.py::buchungen(alle_monate=True)` und `GET /api/zeiten/buchungen?zeitraum=alle` (nur mit `auftrag`, sonst 422; ein anderer Wert
  422); `zeiten.html` übernimmt `?zeitraum=alle` mit Auftrag, die Monatspfeile führen zurück in den Monat.

#### Festlegungen 1.9.128 (bestätigt am 29.10.2026)

1. Gewählter Auftrag ohne Angabe: der älteste laufende oder pausierte, sonst der jüngste; ein Auftrag eines anderen Projekts 404.
2. Hauptaktion: ohne Auftrag „Angebot“ (ohne Angebot) bzw. „Beauftragen“; Phase Auftrag „Einsatz planen“; Ausführung „Rechnung erstellen“, für Büro
   – Auftrag „Einsatz planen“, nach verweigerter Abnahme „Abnahme erfassen“; Abnahme „Schlussrechnung erstellen“ bzw. „Abnahme & Mängel“;
   Schlussrechnung „Auftrag abschließen“; abgeschlossen oder storniert keine.
3. Was ansteht: überfällige Rechnung (Knopf „Mahnen“ ins Mahnwesen, nur mit `darf_geld()`), offener Befund (zum Bericht), Checkliste im Entwurf.
4. Termine: ab heute höchstens acht -- Kalender des Projekts (ohne Modul keine; fremde private als „Belegt“) und Einsätze des gewählten Auftrags.
5. F2: nach der Schlussrechnung ist jedes Feld der Auftragsdaten gesperrt, das auf ein Dokument geht; frei bleiben Sachbearbeiter und Bemerkungen.
6. Art einer Rechnung in Worten: „n. Abschlag nach Leistungsstand“, pauschal die Bezeichnung (aus „n. Abschlagsrechnung“ wird „n. Abschlag“),
   „Schlussrechnung“, „Rechnung aus Aufwand“ bzw. „Abschließende Rechnung aus Aufwand“, „Storno“.
7. Summe je LV-Titel = Positionen „in Summe“ des Titels und seiner Untertitel; Nachträge eine eigene Summe.
8. L3: „alle Monate“ nur mit einem Auftrag; aus „alle Monate“ führen die Monatspfeile in den Monat von heute.

#### Tests und Prüfung

Neu `tests/test_v548_akte_kontext.py` (13 Tests): Hauptaktion je Phase und Rolle (Auftrag, Ausführung mit und ohne Geld, verweigerte Abnahme,
Abnahme, Schlussrechnung, abgeschlossen); ohne Auftrag „Angebot“ bzw. „Beauftragen“ mit der Phase des Angebots; zwei Aufträge (der älteste
laufende, nach Storno der andere, gewählt bleibt gewählt, Auftrag eines anderen Projekts 404); was ansteht, Termine (fremder privater als
„Belegt“, vergangene nicht), Zähler, Befunde, Berichte; F2 (vier Felder 409 mit Grund, Bemerkungen und Sachbearbeiter 200); Summen je Titel samt
Untertitel und Nachträge, nicht für die Monteurin, `art_text` in beiden Rechnungslisten; Art einer Rechnung in Worten (5 Fälle); Monteurin 403;
L3 (zwei Monate, Summe, ohne Auftrag 422, unbekannter Zeitraum 422).

Gegenproben (Marker `GEGENPROBE`, byte-genau zurück, je FAILED in `test_v548`): Hauptaktion ohne Rolle -> 1; F2 ohne Sperre -> 1; Summe je Titel
ohne Untertitel -> 1; „alle Monate“ ohne Wirkung -> 1.

### R2, Punkte 2, 3, 5 und 6 (1.9.129): die Akte als Seite

Befund (Stufe 5, Abschnitte „Projektmappe“ und „Auftrag“; D1, D2, D3, D5, D15, D17, L2, L3, B4, E1): zwei Seiten für einen Vorgang, Summen
über alle Aufträge ohne Auswahl, Status roh, drei Rechnungslisten mit eigenem Code und eigenen Wörtern, „offen“ in zwei Bedeutungen, zwei
„+ Angebot“, der Kasten „Offene Bedenken“ als eigene Fassung, Eingaben im Vertragsentwurf gingen beim Neuzeichnen verloren.

- `app/templates/akte.html` (neu, ersetzt `project_folder.html` und `order.html`): Kopf über das Makro (Pfad Projekte / Kunde / Objekt /
  Projektnummer, Titel = Projektname, Untertitel Anschrift · Bauleitung · archiviert · Mustervorgang, Status über `statusKennzeichen('projekt')`,
  Hauptknopf aus GET /api/projects/{id}/akte, Menü „⋮“ mit Projekt bearbeiten, Beteiligte, Auftragsbestätigung (PDF), Arbeitsvorbereitung,
  Einsatzberichte, Kopieren, Als Mustervorgang, Wartungsvertrag, Archivieren, Löschen); Karte Auftrag und Phase (Auftragswahl ab zwei
  Aufträgen über `?auftrag=`, sonst der eine; fünf Phasen; Status mit Übergängen `_auftragsstatus.html`); Reiter mit Anker in der Adresse, die
  Anker der früheren Seiten (`#sec-…`, `#mangel-…`) öffnen den passenden Reiter. Ein Seitenskript (die node-Tests führen das letzte aus).
- Inhalte wie `akte-zuordnung.html`: Übersicht (Abrechnung und Stunden aus GET /api/orders/{id}/zahlen, nächste Rechnung als Entwurf nur mit
  Geld, Was ansteht, Termine, Beteiligte kurz, Verlauf kurz); Angebote (Tabelle, ein „+ Angebot“); Vertrag (Auftragsdaten lesend mit Dialog,
  Auftragsbestätigung mit Versand, Vertragsgrundlage, Vertrag wörtlich aus der Auftragsseite, Gewährleistung); Leistungen (LV mit Summe je Titel,
  abgerechnet je Position mit Balken, Std. Ist/Soll, Nachträge, Quellangebot, Auftragsstände); Ausführung (Arbeitsvorbereitung, Einsätze,
  Zeiten als Stand mit Link nach „Zeiten“, Einsatzberichte, Checklisten); Abnahme & Mängel (Bausteine `_abnahme.html`/`_maengel.html`,
  Befunde der Berichte); Rechnungen (die eine Liste, neue Rechnung nur mit Geld); Dateien (wie die Projektmappe); Verlauf (GET
  /api/projects/{id}/verlauf: Filter nach Art, Auftragswahl, „Ältere laden“, Einzelheiten aufklappbar, „⋮“ einer Versandzeile mit dem
  Versandverlauf des Dokuments im Dialog -- Zustellung nachtragen, Empfang bestätigt/unzustellbar).
- `app/templates/_rechnungsliste.html` (neu): `rechnungsZahlstand()` und `rechnungsTabelleHtml(rows, {spalten})` für Akte und Finanzen.
- `app/routers/pages.py`: `/projects/{id}` zeichnet die Akte (`auftrag` nur als Zahl über `_zahl()`, `geld`); `/orders/{id}` leitet mit eigener
  Sitzung auf das Projekt des Auftrags (unbekannt: `/projects`; die Monteurin bekommt wie bisher die Sperrseite, `dk_ohne_seite` nur ab Büro –
  Auftrag); „Projektmappe“ heißt in den Pfaden „Akte“.
- Rückwege: Pfad des Auftrags in Arbeitsvorbereitung, Einsatzberichten, Bericht, Rechnung und Checklisten zum Auftrag direkt in die Akte
  (`/projects/<p>?auftrag=<a>#ausfuehrung` bzw. `#rechnungen`), die Checkliste über `/orders/<a>#ausfuehrung`; Angebot `?beauftragen=1` öffnet den
  Dialog, Plantafel `?auftrag=<id>` „Neuer Einsatz“; Finanzen mit der einen Liste, „Unbezahlt“.

#### Festlegungen 1.9.129 (Nr. 1–14, 16 und 17 bestätigt am 29.10.2026; Nr. 15 ersetzt durch die Nachrunde, Punkt 1 -- 1.9.130)

1. `/projects/{id}` ist die Akte; `/orders/{id}` leitet auf `/projects/{p}?auftrag={id}` (Anker bleibt), ein unbekannter Auftrag auf die
   Projektliste.
2. Die Übersicht zeigt Abrechnung und Stunden des gewählten Auftrags; die Summe aller Aufträge steht nur in der Auftragswahl („n Aufträge · Summe“).
3. Projektweites (Angebote, Termine, Beteiligte, Dateien, Verlauf) gilt bei jeder Auftragswahl; die Reiter Vertrag bis Rechnungen erscheinen nur
   mit Auftrag.
4. Eine Position des LV wird nur im Dialog bearbeitet (bis 1.9.128 Menge, Einheit und EP auch direkt in der Zeile); die Zeile zeigt EP mit zwei
   Stellen.
5. Auftragsdaten stehen lesend im Reiter „Vertrag“ und werden im Dialog bearbeitet, gefüllt beim Öffnen.
6. Beteiligte sind ein Dialog (Menü und Karte der Übersicht); Versand und Historie stehen zusammen im Verlauf; die Zeiten des Auftrags stehen als
   Stand im Reiter „Ausführung“, die Buchungen in „Zeiten“ (alle Monate des Auftrags).
7. Ziele des Hauptknopfs: „Angebot“ -> neues Angebot, „Beauftragen“ -> Angebot mit offenem Dialog, „Einsatz planen“ -> Plantafel mit „Neuer
   Einsatz“, „Rechnung erstellen“/„Schlussrechnung erstellen“ -> Reiter Rechnungen mit der Art vorgewählt, „Abnahme erfassen“ -> Dialog,
   „Abnahme & Mängel“ -> Reiter, „Auftrag abschließen“ -> Übergang mit Rückfrage.
8. Eine Rechnungsliste für Akte und Finanzen; Zahlstand in Worten (bezahlt mit Tag, überfällig seit, unbezahlt, teilweise bezahlt · unbezahlt,
   Zahlbetrag unbezahlt, Einbehalt unbezahlt, Guthaben, Enthalten in Schlussrechnung); „offen“ heißt nur noch „unbezahlt“ bzw. „noch nicht
   abgerechnet“.
9. Einen Rechnungsentwurf löscht man auf seiner Rechnungsseite, nicht mehr aus der Liste (Befund D17).
10. Der Auftrag im Pfad anderer Seiten führt direkt in die Akte auf den passenden Reiter; ein fester Link vor dem Laden entfällt, wo das Projekt
    noch nicht bekannt ist (Checklisten zum Auftrag).
11. „Projektmappe“ heißt in Pfaden, Menüs und Hinweisen „Akte“; „Neues Projekt“ (Stufe 7) behält seine Texte.
12. Dialoge der Akte tragen die Ecke der Karte (12 px) -- die Regel der Karten (Wächter `test_v460`) geht der Vorlage (16 px) vor.
13. „Offene Bedenken“ über den Baustein `_offene_bedenken.html` (D17, Datum „9.10.2026“ wie auf Einsatzberichten und Checklisten).
14. Der Verlauf wie die Vorlage: Zeitpunkt kurz („28.10. 07:15“, außerhalb des laufenden Jahres mit Jahr), die Art als Kennzeichen in den
    Farben der Tokens (Termin wie Änderung neutral -- die Tokens kennen kein Violett), rechts das Ziel vom Server: „Öffnen“ bei Bericht,
    Rechnung, Angebot, Checkliste, „Ansehen“ beim Befund (sein Bericht), „⋮“ beim Versand.
15. Die Übergänge des Status stehen als kleine neutrale Knöpfe neben dem Status („Stornieren …“ mit roter Schrift); die Vorlage zeigt nur das
    Kennzeichen.
16. Ein Mustervorgang hat keine Hauptaktion (er wird nicht beauftragt); `?beauftragen=1` öffnet am Muster keinen Dialog.
17. Nach jeder Änderung am Auftrag in der Akte (Position, Nachtrag, Abnahme) lädt die Akte Kopf, Phasen, „Was ansteht“ und Zähler neu.

#### Tests und Prüfung

Neu `tests/test_v549_akte_seite.py` (22 Tests), dazu `test_v547::test_ziel_einer_zeile` und `test_v548::test_mustervorgang_ohne_hauptaktion`: /orders/{id} -> Akte mit Auftrag (drei Büro-Rollen), unbekannt -> /projects; Monteurin 403 auf
Akte und Weiterleitung; ?auftrag= nur als Zahl (fünf Angriffe); Tabelle FUNKTIONEN mit jeder Funktion der Projektmappe (21) und der
Auftragsseite (26) samt Beleg im gezeichneten HTML, eine entfallen (Entwurf löschen, D17); Büro – Auftrag ohne Geld-Knöpfe, mit Hinweis;
alte Anker; Rückwege der sechs Seiten; die beiden alten Vorlagen gibt es nicht mehr.

Im Lauf aufgefallen und an der Seite behoben: die Reiterleiste lief bei 412 px nicht über, aber ein langer Titel in der Verlaufsvorschau (ohne
Umbruchstelle) schob die Seite auf 650 px (`overflow-wrap:anywhere`, vier Klicktests mit 412 px); die Weiterleitung zeichnete für die
Monteurin die Sperrseite, ohne Seitendaten (`dk_ohne_seite` nur ab Büro – Auftrag, `test_v425`); der Versandbaustein stand zwischen Kopfzeile
und Inhalt (`test_v254`); drei Werte des LV ohne Nachweis von `esc()` (`test_v407`: eigene Funktionen `lvMenge()`, `lvStand()`, `lvStd()`);
die Auswahl des Auftrags im Verlauf ohne `auswahlOptionen()` (`test_v447`); `Number()` an einer Auswahl (`test_v414`); `_rechnungsliste.html`
band `_berlin_date.html` nicht ein (`test_v390`); Startpunkt des Angebots wieder `load().catch(` (`?beauftragen=1` danach); „Zahlbetrag offen“
hieß in der Liste „teilweise bezahlt“ (jetzt „Zahlbetrag unbezahlt“).

Angepasste Erwartungen (Test: altes Soll -> neues Soll):
- 48 Testdateien: Vorlagenname „order.html“/„project_folder.html“ als Text -> „akte.html“ (Aufbau).
- node-Tests (`test_v334`, `v438`, `v439`, `v447`, `v450`, `v451`): Startpunkt `load().catch(` der Auftragsseite/Projektmappe -> `akteStarten().catch(` (Aufbau).
- `test_v405`, `test_v447`: Startpunkt der Plantafel `\nloadBoard();` -> `\nloadBoard().then(` (Aufbau; `?auftrag=` öffnet „Neuer Einsatz“).
- `test_v441`: Projektmappe und Auftrag in AUFGESCHOBEN (Stufe 5) -> Akte in UMGEZOGEN; Seiten mit Leiste 44 -> 43 (zweimal).
- `test_v431`: Bilder je Lauf 310 -> 306; bisherige Bilder zuerst 248 -> 244.
- `test_v460`: neu eingeordnet `participant` (Karte), `auftragswahl` (Knopf), `phase-kreis` (Kennzeichen).
- `test_v407`: Ausnahmen der Handler 7 Einträge von order.html/project_folder.html -> akte.html; 6 entfallen (rowHtml 4, secBtn 1, renderInvoices 1).
- `test_v424`: Abgleich ohne `zahlLesen(value)`/`zahlFeld(value)` der LV-Zeile (entfallen).
- `test_v400`: Ausnahme `loadOpenConcerns -> api` gestrichen (Baustein).
- `test_v401`: Weiterleitungen 11 -> 13 (/orders/{id}: Projekt des Auftrags, sonst /projects).
- `test_v419`: Seitenrouten mit eigener Sitzung {} -> {"/orders/{order_id}"}.
- `test_v446`: Rückwege „/orders/{x}“ -> in die Akte („/projects/{x}“, Rechnung „/projects/{x}?auftrag={x}#rechnungen“).
- `test_v457`: Checklisten zum Auftrag vor dem Laden [Checklisten, Auftrag] -> [Checklisten]; backLink der Checkliste mit `#ausfuehrung`.
- `test_v436`, `test_v455`: Pfadtext „Projektmappe“ -> „Akte“.
- `test_v163`, `v249`, `v253`, `v254`, `v255`, `v258`: „beliebige Seite“ project_folder.html -> projects.html (die Akte zeigt im Dialog den Namen des Kontos); `test_v254` sucht weiter `<main>` darin.
- `test_v064`: acht Tests der Projektmappe (Reiter, Anker, Standardreiter, Zähler, Kopf mit einer Aktion, Kennzahlen-Streifen, Zeiten-Tabelle) -> dieselben Fragen an der Akte (Reiter `reiter-*`, `reiterAusAnker()`, `aria-current` auf Übersicht, Zähler vom Server, Hauptaktion und Menü, Karten Abrechnung/Stunden, Stand der Zeiten mit Link `zeitraum=alle`); „Projektmappe“ in projects.html -> „Akte“.
- `test_v438`: Menge/EP der LV-Zeile als `value` der Eingabe -> als Text der Zelle (EP zwei Stellen); Dialog unverändert.
- `test_v439`: Rundweg drei Anfragen (Zeile Menge, Zeile EP, Dialog) -> eine (Dialog); Zeile = Dialog nur noch für die Menge; die Attrappe stellt `akteNachAenderung()` still (Kopf der Akte, ohne Belang).
- `test_v399_teil_updates_geld`: zwei Tests der Eingabe in der LV-Zeile (`quickItem()`) -> ein Test, dass die Zeile keine Eingabe hat und „✎“ den Dialog öffnet.
- `test_v333`: `employeeOptions()` aus dem Seitenskript bis `load(` -> die beiden Funktionen der Akte; Schlüssel von `saveOrder()` aus `body` und `frei`.
- `test_v535`: „Einzeländerungen bleiben zusätzlich im Änderungsprotokoll sichtbar“ -> „jede Einzeländerung steht zusätzlich im Verlauf“; `verlaufAenderung(x)` -> für die Akte `verlaufAenderung(z)`.
- `test_v537`: Kennzeichen `templateBadge` -> „Mustervorgang“ im Untertitel; Löschen im Menü nur ohne Auftrag (unverändert).
- `test_v531`: `${GELD&&inv.status==='entwurf'?` (Löschen am Entwurf) -> „Mahnen“ unter „Was ansteht“ nur mit GELD, „Entwurf anlegen“ nur mit `geld`.
- `test_v418`: Reiter „Versand“ mit `renderDispatchList` -> Verlauf mit Filter „Versand“ und Link ins Versandprotokoll des Projekts.
- `test_v394`: `invoiceStatusText` aus overview in Auftrag und Projektmappe -> die eine Liste liest overview, Akte und Finanzen nutzen sie.
- `test_v545`: `project.status_label||project.status` -> `statusKennzeichen('projekt',project.status)`.
- `test_v340`: Reiter „Beteiligte“ -> Dialog (`beteiligte-oeffnen`, `#sec-participants` öffnet ihn).
- `test_v338`, `test_v337`: Seite `/orders/1` -> `/projects/1` (Weiterleitung).
- `test_v313`: Projektmappe listet Zeitbuchungen -> die Akte nicht (Stand vom Server, Link nach „Zeiten“).
- `test_v238`: Brotkrume `#breadcrumb` des Auftrags -> Pfad des Seitenkopfs der Akte; Rechnung -> Pfad in die Akte.
- `test_v194`: `archivedBadge` -> „archiviert“ im Untertitel.
- `test_v080`: `workPrepLink` -> `#avLink`/`#menueAv`.
- `test_v070`: „Aufträge im Projekt“ -> Auftragswahl; „PDF-Auftragsbestätigung“ -> „Auftragsbestätigung (PDF)“.
- `test_v066`: „Änderungshistorie“/`historyRows` -> Reiter „Verlauf“ und Link „Ganze Änderungshistorie“.
- `test_v065`: „Projektmappe bearbeiten“ -> „Projekt bearbeiten“.
- `test_v100`: Reiter „Zeiterfassung im Projekt“ -> Stand der Zeiten im Reiter „Ausführung“.

Klicktests (25 rot nach dem Umbau, in vier Gruppen umgestellt; je Gruppe grün im eigenen Lauf). Gefunden und an der Seite behoben: nach dem
Speichern oder Verwerfen einer Abnahme blieben Phasen, „Was ansteht“ und Hauptaktion alt (`accNeuLaden()` ruft jetzt `akteNachAenderung()`,
ebenso das Speichern einer Position); ein Mustervorgang bot „Beauftragen“ an (Festlegung 16); der Reiter „Leistungen“ lief bei 412 px über (der
Vorlesetext „Aktionen“ im Kopf des LV hing an der Seite -- `.tabelle-wrap` ist jetzt sein Rahmen). Neu geprüft: `klicktest_lv_ueberlauf` „auftrag
412: kein waagrechter Bildlauf der Seite“, `klicktest_mustervorgang` „Akte (Muster): keine Hauptaktion“. Offen gemeldet (außerhalb der Akte): der
Kopf der Rechnungsseite sagt weiter „Zahlbetrag offen“ (`app/final_dunning.py::OVERVIEW_LABELS`).

Angepasste Erwartungen der Klicktests (Prüfung: altes Soll -> neues Soll, „Aufbau“ = nur Adresse, Reiter, Selektor oder Dialog):
- klicktest_vertrag_abschrift „422 Auftragsdatum: lesbar“: Aufbau (Dialog „Auftragsdaten bearbeiten“, Meldung in #auftragsdatenStatus statt #saveStatus), Soll gleich.
- klicktest_vertrag_abschrift „Abschlag 1.25: lesbar“: Aufbau (Dialog zu, Reiter Rechnungen); Bild fehler_422 zeigt den Dialog, neu Bild fehler_abschlag.
- klicktest_vertrag_abschrift Klara/Lena/Paul/Otto: Aufbau (Anker #vertrag; „412 px ohne seitliches Scrollen“ misst mit sichtbarem Reiter).
- klicktest_vertragsvorlagen „Ausführungszeitraum aus dem Angebot“: Aufbau (Dialog öffnen), Soll gleich; neu „… (lesend)“ (#auftragsdatenListe enthält den Zeitraum, True).
- klicktest_vertragsvorlagen „Zeitraum gespeichert, Rest unverändert“: Aufbau (Dialog, saveOrder()), Soll gleich; neu „Dialog nach dem Speichern zu“ (False).
- klicktest_abnahme Gewährleistung (3 Prüfungen), „Abnahme: Kopf und Ergebnis“, „Büro Auftrag: keine JS-Fehler“: Aufbau (Reiter #vertrag bzw. #abnahme; der JS-Fehler kam aus der Prüfung, .split auf innerText ohne Zeilen).
- klicktest_maengel „Mangel: Kopf …“, „Verlauf: sechs Einträge“: Aufbau (#abnahme); „Sprung zum neuen Eintrag (sichtbar)“ prüfte im verborgenen Reiter nichts (Maße 0), jetzt wirklich.
- klicktest_maengel_monteur Büro-Prüfungen: Aufbau (#abnahme; JS-Fehler kam aus der Prüfung, .startsWith).
- klicktest_bedenkenanzeige Bereitschaft: #orderTitle -> order.order_number und #auftragEinzeln.
- klicktest_objekt_anderer_kunde „Schnellauftrag: zum Auftrag gewechselt“: Soll Pfad beginnt mit /orders/ -> /projects/<zahl>?auftrag=<zahl> (Auftrags-ID aus ?auftrag=).
- klicktest_verlauf_lesbar „Projektmappe, Historie: 850 → 851 m²“ -> „Akte, Verlauf: …“: Aufbau (#verlauf, .vl-zeile mit Einzelheiten statt #historyRows), Soll gleich; „kein .000000 …“ Aufbau.
- klicktest_mustervorgang „Projektmappe (Muster): Kennzeichen sichtbar, Löschen im Menü“: [True, 'Mustervorgang', True] (#templateBadge) -> [True, True, True, 'Löschen'] (Untertitel mit „Mustervorgang“, „Löschen“ im offenen Menü).
- klicktest_mustervorgang „… mit Auftrag: kein Kennzeichen, kein Löschen“: Aufbau (Untertitel), Soll gleich; „ohne Auftrag“: Bereitschaft #seitenkopfKennung.
- klicktest_beteiligte „Reiter aktiv über die Adresse“ -> „Dialog „Beteiligte“ offen über die Adresse“ (#sec-participants.active -> #beteiligteModal.open, True).
- klicktest_beteiligte „Noch keine Beteiligten“: '0' (#tabCountParticipants) -> [0, True] (keine Karte, Hinweis).
- klicktest_beteiligte „Hinzugefügt: Rolle, Kopie, Zähler“: […, '1'] -> […, 1] (Zahl der Karten).
- klicktest_beteiligte „Adresse ohne ?kontakt=“: '#sec-participants' -> '#uebersicht'; neu drei Prüfungen (Karte der Übersicht öffnet den Dialog, Hinzugefügt auf der Karte, zurück mit offenem Dialog).
- klicktest_versand_im_kontext „Projektmappe: Reiter Versand aktiv“ -> „Akte: #sec-dispatch öffnet den Reiter Verlauf“ ('Versand' -> 'Verlauf'); „nur die Dokumente des Projekts“: Aufbau (Filter Versand, .vl-zeile), Soll gleich; Link: Aufbau (#versandprotokollLink); neu drei Prüfungen (Filter, „⋮“ nur an Angebot und Auftrag für Büro – Auftrag, „⋮“ öffnet Zustellung nachtragen).
- klicktest_versandprotokoll: Bereitschaft display 'block' -> 'flex' (#vertrag); „Auftrag: Link ins Protokoll“: Aufbau (#orderDispatchHistory .dh-head a), Soll gleich; Wartebedingung beim Klären (seit 1.8.41 veraltet, lief 15 s ab) auf #resolveNote<id>.
- klicktest_zeitbuchungen_liste „Projektmappe: Hinweis“ (gekürzt 1.000 von 1.001) -> „Akte: keine Zeitbuchungstabelle, kein Hinweis“ [True, True].
- klicktest_zeitbuchungen_liste „Projektmappe: Kennzahlen“ ['999,00 h', '2,50 h', '1.001,50 h', '2'] (Projekt) -> je Auftrag: Ausführung A ['501,5 h', '2,5 h', '499,0 h'], Übersicht A ['501,5 h', 'davon Fahrzeit 2,5 h', '499,0 h', 2], B über die Auftragswahl ['#ausfuehrung', ['500,0 h', '0,0 h', '500,0 h']].
- klicktest_zeitbuchungen_liste „Ist-Stunden (Kopf)“ '999,00 h' -> „Phase Ausführung: gebuchte Stunden“ (endet auf „501,5 h gebucht“, True).
- klicktest_zeitbuchungen_liste „Reiterzahl“ '1001' -> Auftragswahl [A, ['AUF-KT-A', 'AUF-KT-B']] und Links nach „Zeiten“ mit zeitraum=alle.
- klicktest_zeitbuchungen_liste „Tabellenzeilen“ 999 -> „Zeiten (über den Link der Akte): alle 501 Buchungen von A …“ [Link, 501, False, '501,50 h', 1, True]; neu JS-Fehler „Zeiten (Auftrag A)“, „Akte (B)“.
- klicktest_lv_ueberlauf „geladen“, „LV-Zeilen gemessen“, „kein Überlauf“: Aufbau (#leistungen; Zeilen #lvTabelle thead tr, #lv tr.lv-row).
- klicktest_lv_ueberlauf „Tausenderpunkt, passt ins Feld“ -> „… passt in die Zelle“: dieselben Werte als Text der Zelle statt im Feld der Zeile; neu „Dialog der Position: Tausenderpunkt, passt ins Feld“, „Rundweg -- Dialog gespeichert und geschlossen“ [False, ""]; „Rundweg speichert denselben Betrag“: Aufbau (Dialog), Soll gleich.
- klicktest_auftrag_sperren: neu „keine Eingabe in der LV-Zeile, „✎“ an jeder Position“ [0, 2]; „EP und Einheit gesperrt“, „Menge offen“, „zweite Position frei“: Aufbau (Dialog der Position), Soll gleich; „Grund im Tooltip“: Aufbau (title von .price-lock); „Menge gespeichert“: Aufbau (saveItemDialog(), Dialog zu); Steuerschlüssel (2): Aufbau (Dialog Auftragsdaten).
- klicktest_auftrag_sperren „Schluss: jede Eingabe der Positionen gesperrt“: True -> [0, 0] (keine Eingabe, kein „✎“).
- klicktest_nachtrag „Kennzeichen unter „Nachträge“ hinter dem Titel“: Aufbau (#lv tr.lv-titel), Soll gleich.
- klicktest_rechnungen_sperren: neu „E Liste: Entwurf gelistet, kein „Löschen““ [1, False]; „E nach dem Löschen: frei“: Aufbau (Löschen auf der Rechnungsseite), Soll gleich.
- klicktest_rechnungen_sperren „E nach dem Löschen: Hinweis weg“: True -> [False, "", True]; „G nach dem Löschen: Schluss frei“: True -> [True, [False, "", True]].
- klicktest_rechte_geld „Auftrag: Rechnungen gelistet, kein „Löschen““: Aufbau (tr[data-rechnung], #rechnungen), Soll gleich.
- klicktest_rechte_geld „Finanzen: „Neue Rechnung“, „Löschen“ am Entwurf“ (Rolle Büro – Finanzen auf dem Auftrag): [True, False, True] -> [True, False, False, 3] (kein „Löschen“ in der Liste, D17).
- klicktest_auswahl_inaktiv (4 Auftrags-Prüfungen), klicktest_auswahl_restfaelle „archivierter Steuerschlüssel“: Aufbau (#vertrag, Dialog Auftragsdaten), Soll gleich.
- klicktest_finanzen_zahlbetrag „Schlussrechnung A Zahlbetrag offen 495 €“ -> „… unbezahlt …“: ["Zahlbetrag offen", "495,00 €"] -> ["Zahlbetrag unbezahlt 495,00 €", "495,00 €"].
- klicktest_finanzen_zahlbetrag „Schlussrechnung B Guthaben 24 €“: ["Guthaben", "Guthaben 24,00 €"] -> ["Guthaben 24,00 €", "Guthaben 24,00 €"].
- klicktest_finanzen_zahlbetrag Filter „In Schlussrechnung“, „Guthaben“, „Offen“ -> „Unbezahlt“: Aufbau (#rows tbody tr), Soll gleich; neu „Filter „Unbezahlt“: Beschriftung“, „Kacheln „Unbezahlte Rechnungen“ und „Unbezahlt““.
- klicktest_finanzen_zahlbetrag „Auftrag A: … Zahlbetrag offen“ -> „Akte A: … Zahlbetrag unbezahlt“: Text „Zahlbetrag offen (offen 495,00“ -> „Zahlbetrag unbezahlt 495,00“ (#rechnungen).
- klicktest_finanzen_zahlbetrag „Projektmappe B: …“ -> „Akte B: …“: Aufbau (#rechnungen, #invoicesList), Soll gleich.
- klicktest_zahlungen „Filter Einbehalt offen“: Aufbau (#rows tbody tr), Soll gleich.
- klicktest_nebenforderungen Kundenwechsel: Bereitschaft project&&customers.length>0 -> project&&order (Kunden lädt openProjectEdit()), Prüfungen gleich.
- klicktest_monteur_navigation „Auftragsnummer im Pfad verlinkt“: a[href^="/orders/"] true/false -> Ziel /projects/<p>?auftrag=<a>#ausfuehrung (Büro) bzw. None (Monteurin).
- klicktest_rahmen: Aufnahme „projektmappe“ -> „akte“ (Aufbau); Kopfzeile „Knopf rechts“ innerWidth -> clientWidth (ohne Bildlaufleiste; die Akte ist höher als das Fenster); Pfade der Seiten des Auftrags /orders/{a} -> /projects/{p}?auftrag={a}#ausfuehrung bzw. #rechnungen, Arbeitsvorbereitung Projekt ohne #sec-orders; Wartung durchführen Projekt == neues Projekt, Auftrag in der Akte; Angebotskopf „Hauptaktion öffnet den Auftrag“: /orders/{a} -> /projects/{p}?auftrag={a} mit geladenem order; Formular Kontakt: „Projektmappe“ -> „Akte“; Checkliste /orders/<a> -> /orders/<a>#ausfuehrung, Checklisten zum Auftrag -> Akte; „jeder Link im Pfad öffnet eine Seite“: die eine Weiterleitung /orders/<a> -> /projects/<p>?auftrag=<a> (Link der Checkliste) zählt als ohne Umleitung.

Gegenproben (Marker `GEGENPROBE`, byte-genau zurück, je FAILED): Weiterleitung ohne `?auftrag=` -> 3 (`test_v549`); „Entwurf anlegen“ ohne
`geld` -> 1; alter Anker `#sec-files` auf die Übersicht -> 1; Mustervorgang mit Hauptaktion -> 1 (`test_v548`); Befund ohne seinen Bericht -> 1
(`test_v547`).

## Stufe 5, R2 Nachrunde (ab 1.9.130)

Vorgabe 29.10.2026 (übernommen wie gegeben): „Stufe 5 · R2 Nachrunde. Start: HEAD 23b74bf (live), Arbeitskopie sauber. Version ab 1.9.130. Nicht
pushen. Festlegungen R2: bestätigt, außer 1.9.124 Nr. 1 (Punkt 2) und 1.9.129 Nr. 15 (Punkt 1). 1. Status wie die Vorlage: im Kopf nur das
Kennzeichen; Pausieren, Fortsetzen, Abschließen, Stornieren im „⋮“ – nur die Übergänge, die der Server gerade erlaubt (z. B. kein „Abschließen …“
mit Rechnungsentwurf und ohne Schlussrechnung). 2. Storno zurücknehmen: nur Admin, mit Pflichtbegründung, zurück auf „läuft“, im Verlauf (ein
versehentlicher Storno sperrt sonst Auftrag und Angebot für immer). 3. Stunden in der Akte mit zwei Stellen wie in „Zeiten“ (10,75 h statt 10,8 h) –
Übersicht, Phase, Leistungen, Ausführung. Die Vorlage zeigte eine Stelle; das war falsch. 4. „Nächste Rechnung“: liegt schon ein Entwurf vor,
„Entwurf öffnen“ (führt auf ihn) statt „Entwurf anlegen“. 5. Daten mit Jahr, wo sie für sich stehen (Auftragsdaten: Auftragsdatum, Ausführung); kurz
nur in Phasen und Listen. 6. Rechnungsseite: „Zahlbetrag offen“ → „Zahlbetrag unbezahlt“ (OVERVIEW_LABELS), wie die Listen. Tests (Angriff /
Gegenprobe), u. a.: „⋮“ zeigt nur erlaubte Übergänge; ein nicht erlaubter über die API weiter 409; Storno zurücknehmen: Büro 403, Admin ohne
Begründung 422, mit Begründung 200 und Eintrag im Verlauf; dieselben Stunden in Akte und „Zeiten“ (z. B. 10,75 h); mit Entwurf „Entwurf öffnen“,
ohne „Entwurf anlegen“. Ende: Bericht als .txt; ZIP: Kopf mit offenem „⋮“, Übersicht mit Entwurf.“

Festlegungen R2 (1.9.124–1.9.129) bestätigt am 29.10.2026, außer 1.9.124 Nr. 1 (ersetzt durch Punkt 2, 1.9.131) und 1.9.129 Nr. 15 (ersetzt
durch Punkt 1, 1.9.130) -- die Überschriften oben tragen das. Etappen: 1.9.130 Punkt 1, 1.9.131 Punkt 2, 1.9.132 Punkte 3–5, 1.9.133 Punkt 6.

### Nachrunde, Punkt 1 (1.9.130): Status wie die Vorlage

Bis 1.9.129 stand der Status des Auftrags unter den Phasen in einer Zeile „Status“ mit kleinen Knöpfen je Übergang aus dem Status
(Festlegung 1.9.129 Nr. 15, nicht bestätigt) -- auch „Abschließen …“ mit Rechnungsentwurf und ohne Schlussrechnung, das der Server mit 409 ablehnte.
Die Vorlage `akte-uebersicht.html` zeigt im Kopf nur das Kennzeichen.

- `app/auftragsstatus.py::status_info()`: „Abschließen“ fehlt in `aktionen`, solange `abschluss_info()` einen Grund nennt (eine Rechnung ohne
  Schlussrechnung, auch ein Entwurf); der Grund bleibt in `abschluss.grund`. `status_aendern()` prüft unverändert unter der Sperre (409).
- `app/templates/akte.html`: im Seitenkopf `statusKennzeichen('auftrag', order.status)` des gewählten Auftrags, ohne Auftrag der Projektstatus.
  Im Menü „⋮“ vorn „Fortsetzen …“, „Pausieren …“, „Abschließen …“, vor „Löschen“ „Stornieren …“ (rot) -- je ein Eintrag mit
  `data-klick="statusAktion"` und `data-ziel`, `hidden`. Die Zeile unter den Phasen zeigt nur den Hinweis, solange der Auftrag nicht läuft.
- `app/templates/_auftragsstatus.html`: `auftragsstatusZeigen()` setzt `hidden` je Eintrag nach `status_info.aktionen` und schreibt
  `auftragsstatusHinweis()` („Pausiert seit 28.10.2026 · Olga Office · Begründung: …“, ohne Knöpfe; leer, wenn er läuft). Dialog, Rückfrage und
  `abschliessen('auftragsstatus', …)` unverändert.
- Der Status im Kopf geht je Fall über `statusKennzeichen('auftrag', …)` bzw. `statusKennzeichen('projekt', …)` in einem eigenen
  `seitenkopf({status})` -- ein `?:` um die beiden Aufrufe erkennt der Wächter `test_v445` nicht (im ersten Suite-Lauf rot, behoben).
- Fund des neuen Klicktests: nach einem Statuswechsel blieb der Verlauf (Reiter und Vorschau der Übersicht) alt, bis die Seite neu geladen
  wurde. `akteNachAenderung()` lädt seitdem nach dem Kopf auch den Verlauf (Filter bleiben), der Statuswechsel ruft sie statt `akteLaden()`
  -- damit auch nach Position, Nachtrag und Abnahme.
- Fund im Bild „Kopf mit offenem ⋮“: die Seiten setzen `button{justify-content:center}`, `.ds-menue-eintrag` setzte das nicht zurück -- Knöpfe
  im Menü standen mittig, Links links. `app/static/ds/ds.css`: `.ds-menue-eintrag` mit `justify-content: flex-start` (gilt für jedes Menü).

#### Festlegungen 1.9.130 (bestätigt am 29.10.2026)

1. Das Kennzeichen im Kopf der Akte ist der Status des gewählten Auftrags (Läuft, Pausiert, Abgeschlossen, Storniert); ohne Auftrag der Projektstatus.
   Die Phase des Auftrags steht in den Phasen darunter.
2. Im Menü „⋮“ stehen die Übergänge vorn (Fortsetzen, Pausieren, Abschließen -- in dieser Reihenfolge), „Stornieren …“ rot vor „Löschen“; ein
   Eintrag, den der Server gerade nicht erlaubt, fehlt (`hidden`), statt ausgegraut zu sein.
3. „Abschließen …“ fehlt, solange am Auftrag eine Rechnung ohne Schlussrechnung besteht (auch ein Entwurf); ohne jede Rechnung erscheint es („ohne
   Rechnung“ mit Begründung), nach der Schlussrechnung ebenso.
4. Unter den Phasen steht, solange der Auftrag nicht läuft, „<Status> seit <Datum> · <Konto> · Begründung: …“ ohne Knöpfe; läuft er, entfällt die Zeile.
5. Nach jeder Änderung am Auftrag in der Akte (Status, Position, Nachtrag, Abnahme) lädt die Akte auch den Verlauf neu, mit dem gewählten Filter
   (ergänzt Festlegung 1.9.129 Nr. 17).
6. Ein Eintrag eines Menüs „⋮“ steht links, ob Knopf oder Link -- in `ds.css` für alle Seiten, nicht je Seite.

#### Tests und Prüfung

Neu `tests/test_v550_status_im_menue.py` (3 Tests): ohne Rechnung pausiert/abgeschlossen/storniert; mit Abschlag im Entwurf ohne „abgeschlossen“,
Grund in `abschluss.grund`, POST „abgeschlossen“ 409; nach dem Festschreiben des Abschlags weiter ohne, nach der Schlussrechnung wieder mit;
pausiert mit „laeuft“; die vier Menüeinträge mit Ziel, Text, `hidden`, nur „Stornieren“ rot, kein Knopf im Hinweis, Kennzeichen des Auftrags im
Kopf; `auftragsstatusZeigen()` in node: sichtbar genau die erlaubten, Hinweis nur außerhalb von „läuft“, Begründung mit `esc()`.
Neuer Klicktest `scripts/klicktest_status_im_menue.py` (Büro – Finanzen, 1440 px): Kennzeichen „Läuft“, keine Zeile unter den Phasen; „⋮“ mit
Pausieren, Abschließen, Stornieren (Bild `kopf_mit_offenem_menue`); mit Rechnungsentwurf ohne „Abschließen …“; Pausieren und Stornieren über den
Dialog, Hinweis mit Begründung, „⋮“ je Status; der Verlauf zeigt den Wechsel ohne Neuladen.
Angepasste Erwartungen: keine.

Gegenproben (Marker `GEGENPROBE`, byte-genau zurück, je FAILED in `test_v550`): Filter in `status_info()` ausgebaut -> 1; `hidden` je Eintrag
nicht nach `aktionen` -> 1.

### Nachrunde, Punkt 2 (1.9.131): Storno zurücknehmen

Bis 1.9.130 blieb ein stornierter Auftrag storniert (Festlegung 1.9.124 Nr. 1, nicht bestätigt): ein versehentlicher Storno sperrte Auftrag
und Angebot für immer -- keine Einsätze, Berichte und Buchungen der Monteure, und aus dem Angebot entsteht kein zweiter Auftrag.

- `app/auftragsstatus.py::storno_zuruecknehmen(db, order_id, begruendung, *, user_id, user_name)`: unter der Sperre der Auftragszeile
  (`lock_order_invoices()` wie `status_aendern()`), nur aus „storniert“ (sonst `StatusKonflikt`, 409), Begründung Pflicht (`BegruendungFehlt`,
  422), setzt „läuft“ und schreibt `OrderStatusChange` (storniert -> läuft, mit Begründung) im selben Commit -- gemeinsam mit `status_aendern()`
  über `_wechsel_schreiben()`. Rollenlos; `status_info()` meldet `storno_zuruecknehmen` (der Auftrag ist storniert), `wechsel_dict()` nennt die
  Aktion „Storno zurücknehmen“. Der allgemeine Weg (`POST /api/orders/{id}/status`) lehnt aus „storniert“ weiter ab (409), jetzt mit dem Hinweis
  auf „Storno zurücknehmen“.
- `app/permissions.py::darf_storno_zuruecknehmen()` (nur Admin, `STORNO_ZURUECK_ROLLEN`): `POST /api/orders/{id}/storno-zuruecknehmen`
  (`require_role`, Büro 403 mit „Einen Storno nimmt nur der Admin zurück.“, Schema `OrderStornoZurueckRequest`: Begründung Pflicht, leer 422) und
  die Seitenroute der Akte (`storno_zuruecknehmen` im Kontext).
- `app/templates/akte.html`: im „⋮“ nach den Übergängen „Storno zurücknehmen …“ (`data-klick="stornoZuruecknehmen"`, `hidden`), nur für den
  Admin im Markup. `_auftragsstatus.html`: sichtbar, solange `status_info.storno_zuruecknehmen` gilt; derselbe Dialog (Titel „Storno
  zurücknehmen – <Nummer>“, Wirkung, Begründung *, Knopf „Storno zurücknehmen“) über `abschliessen('auftragsstatus', …)`. Der Hinweis beim
  Stornieren sagt „Zurücknehmen kann den Storno nur der Admin, mit Begründung.“ statt „Ein Storno lässt sich nicht zurücknehmen.“
- Verlauf: die Zeile „<Auftragsnummer> · storniert → läuft“ mit „Begründung: …“ (Änderungsprotokoll, wie jeder Statuswechsel); nach dem
  Zurücknehmen lädt die Akte Kopf, Phasen und Verlauf neu (1.9.130).

#### Festlegungen 1.9.131 (bestätigt am 29.10.2026)

1. Storno zurücknehmen ist ein eigener Weg (`POST /api/orders/{id}/storno-zuruecknehmen`), nicht ein weiteres Ziel von `POST /api/orders/{id}/status`;
   dort bleibt „storniert“ eine Sackgasse (409 mit dem Hinweis).
2. Zurück geht es immer auf „läuft“, auch wenn der Auftrag vor dem Storno pausiert war (wieder pausieren ist ein eigener Schritt mit Begründung).
3. Zurückgenommen wird nur der Status: was während des Stornos geschah (Rechnungen, Buchungen des Büros), bleibt; ein Einsatz, der beim Storno
   bestand, bestand weiter.
4. Die Begründung ist Pflicht (leer oder nur Leerzeichen 422) und steht im Verlauf und im Statusverlauf (Aktion „Storno zurücknehmen“).
5. „Storno zurücknehmen …“ steht im „⋮“ nach den Übergängen, vor „Projekt bearbeiten“; für Büro – Finanzen und Büro – Auftrag fehlt der Eintrag
   im Markup ganz (nicht nur verborgen), für den Admin ist er sichtbar, solange der Auftrag storniert ist.

#### Tests und Prüfung

Neu `tests/test_v551_storno_zuruecknehmen.py` (12 Tests): Büro – Auftrag und Büro – Finanzen 403 (Status bleibt storniert); Admin ohne
Begründung (fehlt, null, leer, Leerzeichen) 422; mit Begründung 200: „läuft“, Übergänge wieder da, letzter Wechsel storniert -> läuft mit Aktion
„Storno zurücknehmen“ und gekürzter Begründung, Zeile in `order_status_changes`, Statusverlauf „Stornieren“, „Storno zurücknehmen“, im Verlauf
„… storniert → läuft“ mit „Begründung: …“, ein neuer Bericht geht wieder (vorher 409); nicht storniert (läuft, pausiert) 409, der allgemeine Weg
aus „storniert“ 409 mit dem Hinweis, unbekannter Auftrag 404; der Eintrag im Markup nur für den Admin; `auftragsstatusZeigen()` in node: sichtbar
genau, solange storniert.

Angepasste Erwartungen:
- `tests/test_v399_abschliessen.py`, `ABSCHLIESSEND[("_auftragsstatus.html", "statusDialogSenden")]` -- Soll unverändert (über `abschliessen()`),
  nur die Beschreibung um „Storno zurücknehmen“ ergänzt (Aufbau; dieselbe Funktion sendet beide Wege).
- `scripts/klicktest_zeitbuchungen_liste.py`, „Auftrag (Admin): Rechnung aus Aufwand“ -- Soll unverändert, nur die Bereitschaft (Aufbau): alt
  `#newInvoiceType option` (schon von den Optionen im Markup erfüllt, bevor die Akte den Auftrag geladen hat), neu
  `timeTotals&&#newInvoiceType option` -- die Option „aufwand“ entsteht erst mit den Zeiten des Auftrags. Im Lauf von 1.9.131 einmal rot (zu früh
  geprüft, zwei Anfragen der Akte noch offen), in den Läufen davor grün; ein Rennen seit 1.9.129 (Akte statt Auftragsseite), kein Fehler der Seite.

Klicktest `scripts/klicktest_status_im_menue.py` erweitert (der Admin-Teil): kein „Storno zurücknehmen“ im Markup für das Büro; als Admin
„Storno zurücknehmen …“ im „⋮“, Dialog mit Titel, ohne Begründung abgelehnt, mit Begründung „Läuft“, im Verlauf „storniert → läuft“ mit der
Begründung.

Gegenproben (Marker `GEGENPROBE`, byte-genau zurück, je FAILED in `test_v551`): Endpunkt mit der Rolle des Büros -> 2; ohne Pflicht der Begründung
(Schema und Funktion) -> 4; ohne Prüfung „storniert“ -> 1; Eintrag für jede Rolle im Markup -> 2; Eintrag immer sichtbar -> 1.

### Nachrunde, Punkte 3–5 (1.9.132): Stunden mit zwei Stellen, „Entwurf öffnen“, Daten mit Jahr

Punkt 3: die Akte zeigte Stunden mit einer Stelle (Vorlage, „10,8 h“), „Zeiten“ mit zwei („10,75 h“) -- `klicktest_zeitbuchungen_liste` hielt
beides nebeneinander fest („501,5 h“ in der Akte, „501,50 h“ in „Zeiten“). Punkt 4: „Nächste Rechnung“ bot „Entwurf anlegen“ auch mit einem
vorhandenen Entwurf an (`create_block_reason()` sperrt einen weiteren Abschlag nicht). Punkt 5: Auftragsdaten zeigten Daten im laufenden Jahr
ohne Jahr (`tagKurz()`).

- Stunden: `app/akte.py::stunden_text()` mit zwei Stellen über `round_hours()` (Phase „Ausführung“: „seit 24.10. · 10,75 h gebucht“);
  `app/templates/akte.html`: `stunden()` = `zahlText(h, 2)` wie `stunden()` in `zeiten.html` (Übersicht „Stunden“ samt je Mitarbeiter,
  Ausführung „Stand der Zeiten“, „Davon ohne Bezug auf eine Position“), `lvStd()` „10,75 / 12,00 h“.
- „Nächste Rechnung“: `naechsteRechnungZeichnen()` sucht zuerst Entwürfe des Auftrags (ohne Storno-Entwürfe), der älteste zuerst: Text „<Art in
  Worten> liegt als Entwurf vor (netto …)“ (ohne Betrag bei 0 €), bei mehreren „dazu n weitere Entwürfe“, Link „Entwurf öffnen“ auf
  `/invoices/{id}` statt des Knopfs „Entwurf anlegen“. Ohne Entwurf wie bisher. Nur mit `darf_geld()` (die Karte steht nur dann im Markup).
- Daten: `tagLang()` neben `tagKurz()` -- mit Jahr in den Auftragsdaten (Auftragsdatum, Ausführung von – bis), im geplanten Zeitraum der
  Arbeitsvorbereitung (Reiter Ausführung), im Stand des LV („aus der Rechnung … (01.10.2026)“) und bei „überfällig seit“ in der Übersicht. Kurz
  bleiben die Phasen (Text vom Server) und die Listen (Einsätze, Berichte, Termine, Was ansteht, Verlauf, Rechnungen).

#### Festlegungen 1.9.132 (bestätigt am 29.10.2026)

1. Stunden haben in der Akte überall zwei Stellen, auch Soll und Fahrzeit und „0,00 h“ -- wie „Zeiten“.
2. „Entwurf öffnen“ gilt für jeden Entwurf des Auftrags außer einem Storno-Entwurf (Abschlag, Schlussrechnung, Rechnung aus Aufwand); bei mehreren
   führt der Link auf den ältesten, der Text nennt die Zahl der weiteren.
3. Die Karte nennt den Betrag des Entwurfs netto, bei 0 € (frischer Abschlag nach Leistungsstand) keinen.
4. „Für sich stehend“ heißt: Auftragsdaten (Auftragsdatum, Ausführung), geplanter Zeitraum der Arbeitsvorbereitung, Stand des LV, „überfällig
   seit“ -- mit Jahr; Phasen und Listen kurz („24.10.“, außerhalb des laufenden Jahres mit Jahr).
5. Zwischen zwei Daten eines Zeitraums steht „ – “ mit Leerzeichen (geplanter Zeitraum, bis 1.9.131 „13.10.–20.10.“), wie in der Ausführung.

#### Tests und Prüfung

Neu `tests/test_v552_akte_stunden_daten_entwurf.py` (11 Tests): 8 h + 2,75 h -- Zahlen der Akte, „Zeiten“ mit allen Monaten und die Phase je
10,75 h; `stunden_text()` (10,75 · 9,50 · 0,00 · 0,13 h); die Helfer der Akte und von „Zeiten“ in node gleich („10,75 h“, „10,75 / 12,00 h“);
„Nächste Rechnung“ in node: mit Entwurf „Entwurf öffnen“ auf ihn (Storno-Entwurf zählt nicht, der älteste, „dazu 1 weiterer Entwurf“, ohne
Betrag bei 0 €), ohne Entwurf „Entwurf anlegen“, gesperrt keine Karte; Knopf und Link im Markup; `tagLang()`/`tagKurz()` in node; die Stellen
mit Jahr.

Angepasste Erwartungen:
- `tests/test_v545_phase_projektstatus.py::test_phase_ausfuehrung_ab_der_ersten_buchung` -- alt „… 9,5 h gebucht“, neu „… 9,50 h gebucht“.
- `scripts/klicktest_zeitbuchungen_liste.py`, Akte (A), Ausführung -- alt „501,5 h“, „2,5 h“, „499,0 h“, neu „501,50 h“, „2,50 h“, „499,00 h“.
- dort Phase „Ausführung“ -- alt endet auf „501,5 h gebucht“, neu „501,50 h gebucht“.
- dort Übersicht „Stunden“ -- alt „501,5 h“, „davon Fahrzeit 2,5 h“, „499,0 h“, neu „501,50 h“, „davon Fahrzeit 2,50 h“, „499,00 h“.
- dort Akte (B) -- alt „500,0 h“, „0,0 h“, „500,0 h“, neu „500,00 h“, „0,00 h“, „500,00 h“.

Neuer Klicktest `scripts/klicktest_akte_stunden_entwurf.py` (Büro – Finanzen, 1440 px): 8 h + 2,75 h auf Position 1 (Soll 12 h) -- Übersicht
12,00/10,75/10,75 h, Phase „10,75 h gebucht“, Leistungen „10,75 / 12,00 h“, Ausführung 10,75/0,00/10,75 h, „Zeiten“ über den Link der Akte 10,75 h;
Abschlag im Entwurf: „Entwurf öffnen“ mit dem Link auf die Rechnung (Bild `uebersicht_mit_entwurf`), Klick führt dorthin; ohne Entwurf „Entwurf
anlegen“; Auftragsdaten mit Jahr.

Gegenproben (Marker `GEGENPROBE`, byte-genau zurück, je FAILED in `test_v552`): Server mit einer Stelle -> 5; Akte mit einer Stelle -> 1; Entwurf
nie gefunden -> 1; Storno-Entwurf zählt mit -> 1; Auftragsdatum kurz -> 1.

### Nachrunde, Punkt 6 (1.9.133): „Zahlbetrag unbezahlt“ auf der Rechnungsseite

Im Bericht zu R2 als offen gemeldet: der Kopf der Rechnungsseite sagte „Zahlbetrag offen“ (Text vom Server bzw. das Kennzeichen), die Listen
„Zahlbetrag unbezahlt“ (D5).

- `app/final_dunning.py::OVERVIEW_LABELS["zahlbetrag_offen"]` = „Zahlbetrag unbezahlt“ (der `state_label` jeder Rechnungszeile nach einer gültigen
  Endrechnung, u. a. in Finanzen); `app/templates/_statuskennzeichen.html`, Gruppe `rechnung`: `zahlbetrag_offen` -> „Zahlbetrag unbezahlt“ (Kopf der
  Rechnungsseite). Der Schlüssel `zahlbetrag_offen` bleibt (Filter „Unbezahlt“ in Finanzen, Kennzeichen, Tests).

#### Festlegungen 1.9.133 (bestätigt am 29.10.2026)

1. Nur der angezeigte Name wechselt; der Schlüssel `zahlbetrag_offen` bleibt in Daten, Filtern und Kennzeichen (kein Umbenennen im Code).

#### Tests und Prüfung

Neu `tests/test_v553_zahlbetrag_unbezahlt.py` (2 Tests): `state_label` der Schlussrechnung mit enthaltenem Abschlag; Kennzeichen im Kopf und Zahlstand der
Liste in node gleich („Zahlbetrag unbezahlt 495,00 €“).

Angepasste Erwartungen:
- `tests/test_v445_statuskennzeichen.py` (Tabelle der Kennzeichen) -- alt „Zahlbetrag offen 495,00 €“ (und „… · überfällig“), neu „Zahlbetrag unbezahlt
  495,00 €“ (und „… · überfällig“).
- `scripts/klicktest_finanzen_zahlbetrag.py`, „Rechnungsseite Schlussrechnung A“ -- alt „Zahlbetrag offen 495,00 €“, neu „Zahlbetrag unbezahlt 495,00 €“.
- `scripts/klicktest_mahnen_endrechnung.py`, „Schlussrechnung: überfällig, Zahlbetrag …“ -- alt enthält „Zahlbetrag offen 495,00“, neu „Zahlbetrag
  unbezahlt 495,00“.

Gegenproben (Marker `GEGENPROBE`, byte-genau zurück, je FAILED in `test_v553`): Name am Server alt -> 1; Kennzeichen alt -> 1.

## Stufe 5, R3 (ab 1.9.134): die Kundenakte

Vorgabe 29.10.2026 (übernommen wie gegeben): „Stufe 5 · R3 – die Kundenakte. Start: HEAD 4c5dd4e (live), Arbeitskopie sauber. Version ab 1.9.134.
Nicht pushen. Festlegungen R2 Nachrunde: alle bestätigt. Vorlage (freigegeben): bildgrundlage/entwurf-stufe5/kunde-uebersicht.html,
kunde-zahlungen.html, kunde-zuordnung.html. Maße und Texte gelten, Zahlen sind Beispiel; Aufbau, Bausteine und Regeln wie die Akte je Projekt
(akte.html). 0. Vorweg: jede Funktion der heutigen Kundenakte (customer.html) als Liste (Knopf, Link, Endpunkt, Rolle) – als Tabelle im Test wie
test_v549. 1. Server, eine Rechnung mit den Funktionen der Akte: je Projekt Phase und Zahlen; Unbezahlt, überfällig, Guthaben, abgerechnet und
bezahlt je Jahr. Verlauf des Kunden (wie app/akte_verlauf.py): Änderungen am Kunden, Kontakte, Objekte, Versand, Zahlungen. 2. /customers/{id} wird
die Kundenakte wie die Vorlage: Pfad, Kopf (Name, Kundennummer, Kategorie, Anschrift, Telefon und E-Mail als Link), „+ Projekt“, „⋮“; Reiter
Übersicht · Projekte · Objekte · Anfragen · Zahlungen · Dokumente · Kontakte · Verlauf. Stammdaten lesend mit Dialog „Stammdaten bearbeiten“
(Eingaben bleiben). Jede Funktion aus Punkt 0 bleibt erreichbar; alte Anker (z. B. #zahlungen) öffnen den passenden Reiter. 3. Zahlungen:
unbezahlte Rechnungen, Zahlungseingänge mit Zuordnung und Rest; ein Rest als Vorschlag „Auf RE-… zuordnen“ (älteste unbezahlte) bzw. „Erstattung
buchen“, gebucht erst mit Klick; „⋮“ je Eingang: Zuordnen, Erstatten, Zurücknehmen (mit Begründung). Geld nur Admin und Büro – Finanzen, Büro –
Auftrag liest. Kein Zahlungseingang ohne Rechnung (Entscheidung Tobias: Zahlungen nur zu Abschlagsrechnungen). 4. „Kunde archivieren“ im „⋮“ nur
ohne laufendes Projekt – gibt es Archivieren am Kunden heute nicht, im Bericht sagen, nicht bauen. 5. Aus R2 übernehmen: Stunden mit zwei Stellen,
Daten mit Jahr, wo sie für sich stehen, „unbezahlt“ bzw. „noch nicht abgerechnet“. Dazu das „⋮“ der Akte und der Kundenakte mit Trennlinien zwischen
Status, Projekt bzw. Kunde und Wegen. Tests (Angriff / Gegenprobe), u. a.: jede Funktion aus Punkt 0 erreichbar; #zahlungen öffnet den Reiter
Zahlungen; Zahlen der Kundenakte = Summe seiner Akten bzw. seiner Rechnungen und Zahlungen (im Test nachgerechnet); Rest zuordnen: Büro – Auftrag
403 und kein Knopf / Finanzen 200, Rest danach 0; Stammdaten im Dialog: Eingaben bleiben beim Neuzeichnen; Speichern ändert nur Geändertes;
Monteurin 403. Ende: Bericht als .txt; ZIP: jeder Reiter neben der Vorlage (1440, hell), Übersicht dunkel, Zahlungen als Büro – Auftrag, Kunde ohne
Projekt.“

Die Vorlagen liegen unter `bildgrundlage/entwurf_stufe5_kunde/` (die Vorgabe schreibt `entwurf-stufe5`). Festlegungen der R2 Nachrunde
(1.9.130–1.9.133) bestätigt am 29.10.2026, die Überschriften oben tragen das. Aus `kunde-zuordnung.html` (Tobias, 29.10.2026): ein Zahlungseingang
ohne offene Rechnung (Vorauszahlung, Befund L7) ist nicht nötig -- Zahlungen gibt es nur zu Rechnungen, es bleibt wie heute; „Kunde archivieren“
im „⋮“ nur ohne laufendes Projekt (Vorschlag).

Punkt 4: am Kunden gibt es heute kein Archivieren -- `Customer` und `CustomerProfile` haben kein Feld dafür, kein Endpunkt archiviert oder löscht
einen Kunden (geprüft `app/models.py`, `app/routers/customers.py`). Nach der Vorgabe nicht gebaut, im Bericht genannt.

Etappen (je eine Version mit vollem Lauf): 1.9.134 Punkt 0; 1.9.135 Punkt 1 Zahlen und Kontext; 1.9.136 Punkt 1 Verlauf, dazu das Speichern der
Stammdaten als Teil-Update; danach die Seite (Punkte 2, 3, 5).

### R3, Punkt 0 (1.9.134): jede Funktion der heutigen Kundenakte

`tests/test_v554_kundenakte_funktionen.py`, Tabelle `FUNKTIONEN` (31 Zeilen): Funktion, Art (Knopf, Link, Feld, Anzeige, Anker), Endpunkte mit
Methode, Rolle der Funktion laut Route, Reiter der neuen Kundenakte (nach `kunde-zuordnung.html`), Belege im gezeichneten HTML. Nach Bereich:

| Bereich | Funktionen | Endpunkte | Rolle |
|---|---|---|---|
| Kopf, Kennzahlen | Name, Nummer, Kategorie; fünf Kacheln (Objekte, Anfragen, Projekte, Angebote, Angebotssumme) | GET Kunde, Objekte, Anfragen, Projekte, Angebote je Projekt | Au |
| Stammdaten | 18 Felder, „Stammdaten speichern“ | GET Optionsgruppen, Zahlungsbedingungen; PUT /api/customers/{id} | Au |
| Kontakte & Kundenwissen | anzeigen, anlegen, speichern, löschen | POST/PUT/DELETE /api/customers/{id}/extra-infos | Au |
| Objekte | Liste mit Hauptadresse, anlegen, bearbeiten, Dachflächen, „+ Dachfläche“ | GET/POST/PUT /api/properties, GET/POST /api/roof-areas | Au |
| Anfragen | Liste, „Pipeline öffnen“, „Neue Anfrage“ | GET /api/inquiries | Au |
| Dokumente | hochladen, Kacheln, Suche, öffnen, Download, bearbeiten, löschen | /api/customers/{id}/documents, /api/customer-documents/{id} | Au |
| Projekte & Angebote | Projekte mit Angeboten, „Projekt öffnen“, „Projekt anlegen“ | GET /api/projects, /api/projects/{id}/quotes | Au |
| Zahlungen | Guthaben, Erstattung buchen, Zahlungen mit Zuordnungen, Rest zuordnen, zurücknehmen, Hinweis, Anker #zahlungen | GET payments, open-invoices; POST refunds, allocations, reverse | lesen Au, buchen Geld |
| Versand | Versand des Kunden (Projekte und Objekte), Empfang bestätigt / unzustellbar | GET /api/email-dispatches?customer_id= | Au |

Beim Erfassen aufgefallen (für den Umbau, nicht einzeln behoben):
- „Projekt öffnen“ führt auf `/projects?project_id=…` -- die Projektliste wertet `project_id` nicht aus, man landet in der ungefilterten Liste.
- Projektstatus (`Status ${p.status}`) und Angebotsstatus (Kennzeichen mit dem Wert) stehen roh da (Befund B4).
- „Kontakte & Kundenwissen“ bearbeitet in Zeilen: jedes Neuladen des Kunden (z. B. nach dem Speichern eines anderen Eintrags) zeichnet alle Zeilen
  neu, eine angefangene Eingabe in einer anderen Zeile ist weg (wie E1 in der Akte); Fehler erscheinen als `alert()`.
- Die Stammdaten speichert `PUT /api/customers/{id}` als volles Formular (in `BEKANNT` von `tests/test_v329_update_handler_struktur.py`).
- Am Kunden gibt es weder Archivieren noch Löschen (Punkt 4).

#### Festlegungen 1.9.134 (bestätigt am 30.10.2026)

1. Die Rolle einer Funktion gilt für ihre schreibenden Endpunkte; jeder lesende muss für Büro – Auftrag offen sein (die Zahlungen liest es ganz).
2. Die Ziel-Reiter folgen `kunde-zuordnung.html`; „Projekt anlegen“ wird „+ Projekt“ im Kopf, die fünf Kacheln werden die Zähler an den Reitern
   (Geld steht in der Karte „Geld“), der Versand steht im Verlauf (Filter „Versand“).

#### Tests und Prüfung

Neu `tests/test_v554_kundenakte_funktionen.py` (8 Tests): Liste vollständig (≥ 30, jeder Reiter bekommt etwas); jede Funktion steht in der Seite;
jeder Endpunkt ist eine Route mit der Rolle der Funktion; jeder Pfad unter `/api/`, den die Seite aufruft (22), steht in der Liste; Monteurin 403,
jedes Büro 200. Angepasste Erwartungen: keine.

Gegenproben (Marker `GEGENPROBE`, byte-genau zurück, je FAILED in `test_v554`): „Stammdaten speichern“ ohne Aufruf -> 1; neuer, nicht gelisteter
Aufruf unter `/api/` -> 1.

### R3, Punkt 1a (1.9.135): Zahlen der Kundenakte

- `app/kundenakte.py` (neu, rollenlos): `projekte()` je Projekt des Kunden ohne Mustervorgänge -- Status aus `app/akte.py::projekt_status_alle()`,
  Aufträge mit Status, Bauleitung, seit, Zahlen; `_zahlen_je_auftrag()` rechnet je Auftrag wie `akte.leistung()` (Auftragssumme über `order_sum()`,
  abgerechnet = Netto der festgeschriebenen Rechnungen ohne Stornos und stornierte, nach der abschließenden Rechnung nichts mehr „noch nicht
  abgerechnet“) und `akte.zahlung()` (unbezahlt über `invoice_overview_rows()`), die Rechnungen aller Aufträge in einer Abfrage;
  `angebot_summen()` netto/brutto je Angebot wie `quote_to_dict()` (Layout „in Summe“, je Position gerundet) in zwei Abfragen. `geld()` über die
  Rechnungen mit `Invoice.customer_id` und die Zahlungen des Kunden; `guthaben()` wie `customer_payments()["balance"]`; `vorschlaege()`;
  `zaehler()` (Projekte ohne Muster, Objekte, Anfragen, Dokumente, Kontakte); `kunde_kontext()`.
- `GET /api/customers/{customer_id}/akte` (`app/routers/customers.py`, ab Büro – Auftrag, Monteurin 403, unbekannt 404).

#### Festlegungen 1.9.135 (bestätigt am 30.10.2026)

1. Die Kundenakte zählt keine Mustervorgänge. „Laufend“ heißt: nicht abgeschlossen, nicht storniert, nicht archiviert; laufende stehen zuerst, je
   Gruppe die jüngsten zuerst.
2. Die Zahlen eines Projekts sind die Summe seiner Aufträge nach `akte.leistung()`/`akte.zahlung()` (Rechnungen des Auftrags); das Geld des Kunden
   rechnet über die Rechnungen, die er beim Festschreiben festhielt (`Invoice.customer_id`) -- wie Zahlungen, offene Rechnungen und Finanzen.
3. „seit“ eines Projekts ist das Datum seines ersten Auftrags; „Bauleitung“ der Projektleiter / Vorarbeiter des ersten Auftrags, der einen hat.
4. Ohne Auftrag zeigt ein Projekt das jüngste nicht abgelehnte Angebot mit Stand, netto und dem Tag des E-Mail-Versands (Berlin).
5. Abgerechnet je Jahr = Netto der festgeschriebenen Rechnungen (ohne Stornos und stornierte) nach Rechnungsdatum; bezahlt je Jahr = Eingänge minus
   Zahlungsausgänge nach Eingangstag, ohne zurückgenommene, dazu die Zahl der Eingänge und der erstattete Betrag. Laufendes Jahr und Vorjahr stehen
   immer da (auch mit 0 €).
6. Vorschlag je Rest einer Zahlung: die älteste unbezahlte Rechnung des Kunden (Rechnungsdatum, dann Kennung), höchstens ihr unbezahlter Betrag; ohne
   unbezahlte Rechnung „Erstattung buchen“; die Überzahlung einer Schlussrechnung immer „Erstattung buchen“. Eine Rechnung, an der nur
   Nebenforderungen offen sind, zählt dafür nicht (Zahlungen darauf laufen über die Rechnungsseite, § 367 BGB).
7. Büro – Auftrag liest die ganze Kundenakte, auch das Geld; die Monteurin bekommt sie nicht (403).

#### Tests und Prüfung

Neu `tests/test_v555_kundenakte_zahlen.py` (9 Tests) mit einer Welt aus Vorjahr und laufendem Jahr (Abschlag im Vorjahr festgeschrieben und
bezahlt, Schlussrechnung vor 60 Tagen -- überfällig, pauschaler Abschlag mit Rest, Erstattung, zurückgenommene Zahlung, Projekt nur mit Angebot samt
Bedarfsposition, stornierter Auftrag, Mustervorgang, zwei weitere Kunden): je Projekt Status und Zahlen = Summe der Akten seiner Aufträge (dazu
exakt 5.000 / 5.000 / 0 / 3.570 €); Angebot und Summen wie der Editor; unbezahlt = Summe der Akten (3.570 €), überfällig seit der Fälligkeit der
Schlussrechnung, Guthaben = Rest (310 €), je Jahr abgerechnet = Netto der Rechnungen, bezahlt = Zahlungen ohne zurückgenommene, Zahl der Eingänge,
erstattet; Vorschlag „zuordnen“ auf die Schlussrechnung, beim Kunden ohne unbezahlte Rechnung „erstatten“; Zähler ohne Muster; Endpunkt für jedes Büro
200, Monteurin 403, unbekannt 404. Angepasste Erwartungen: keine.

Gegenproben (Marker `GEGENPROBE`, byte-genau zurück, je FAILED in `test_v555`): ohne Kundenfilter an den Rechnungen -> 4; Mustervorgänge mitgezählt
-> 4; zurückgenommene Zahlung mitgezählt -> 1; Vorschlag „erstatten“ trotz unbezahlter Rechnung -> 1; Bedarfsposition in der Angebotssumme -> 1.

### R3, Punkt 1b (1.9.136): Verlauf des Kunden, Stammdaten als Teil-Update

- `app/kunde_verlauf.py` (neu): `kennungen()` je Art im Änderungsprotokoll die Kennungen des Kunden -- „Kunde“ (auch das Profil), „Kundenwissen“,
  „Objekt“, „Anfrage“, „Zahlungseingang“ über die Spalte `customer_id` heute und über den Schnappschuss beim Anlegen oder Löschen (`details`,
  `"customer_id": "<id>"`), „Dachfläche“ über die Objekte (heute) bzw. `"property_id"` im Schnappschuss; `_fenster()`: eine Kennung, die irgendwann
  gelöscht wurde, gilt nur vom Anlegen beim Kunden bis zum Löschen (ein Datensatz von heute ohne Ende) -- die übrigen in einem `IN`;
  `zeilen_bedingung()`; `strom()` mit `gruppieren()`/`gruppe_dict()` aus `app/akte_verlauf.py`, ein Versand als eigene Gruppe.
- `GET /api/customers/{customer_id}/verlauf` (`app/routers/customers.py`, ab Büro – Auftrag): Filter `art` (aenderung, versand, zahlung; sonst
  422), Seiten über `vor`, geschwärzt über `app/routers/audit.py::sichtbar()`, „Zustellung nachtragen“ an Rechnung und Mahnung nach `darf_geld()`.
- `app/akte_verlauf.py`: `zeilen_seite()` (beide Verläufe) -- reicht eine Aktion über `ZEILEN_JE_ABRUF`, wächst die Seite (×4) bis
  `GRENZE_HOECHSTENS` (10.000); bleibt danach eine einzige Gruppe, steht sie da und `vor` geht zu älteren Zeilen. `ZIEL_JE_TYP` um Objekt
  (`/properties/{id}`) und Dachfläche (`/roof-areas/{id}`).
- `app/schemas.py::CustomerUpdate` ist ein `PartialUpdate` (`NOT_NULL` last_name, category, country, is_consumer); der Handler übernimmt
  `model_dump(exclude_unset=True)`, die Zahlungsbedingung nur, wenn gesendet (`set_payment_term`). `BEKANNT` in
  `tests/test_v329_update_handler_struktur.py` ohne `PUT /api/customers/{customer_id}` (61 -> 60).

Funde beim Bau (behoben): (1) unter SQLite bekam ein neuer Eintrag von Kunde B die Kennung eines gelöschten von Kunde A -- seine Zeilen erschienen im
Verlauf von A; behoben über das Zeitfenster. (2) Verlauf der Akte und des Kunden: eine Aktion mit mehr Zeilen als eine Seite fasst -- die Seite warf
ihre einzige Gruppe weg, `vor` zeigte immer wieder auf dieselbe Stelle; behoben über `zeilen_seite()` und den Rückfall in `strom()`. (3) Ein Versand
hing im Strom des Kunden an der nächsten Aktion desselben Kontos (der Zahlungsbuchung) und machte sie zur Versandzeile -- im Kunden fehlt die Zeile
des Dokuments selbst; ein Versand ist dort eine eigene Zeile.

#### Festlegungen 1.9.136 (bestätigt am 30.10.2026)

1. Der Verlauf des Kunden zeigt Kunde (samt Profil), Kundenwissen, Objekte mit Dachflächen, Anfragen, Zahlungen und den Versand seiner Dokumente;
   Projekte, Angebote, Aufträge und Rechnungen stehen im Verlauf ihrer Akte, nicht hier. Kundendokumente fehlen (sie stehen nicht im
   Änderungsprotokoll). Überholt seit 1.9.140: Kundendokumente stehen im Protokoll und im Verlauf des Kunden.
2. Arten im Verlauf des Kunden: Änderung, Versand, Zahlung.
3. Ein Versand ist im Verlauf des Kunden immer eine eigene Zeile (in der Akte gehört er weiter zur Aktion an seinem Dokument).
4. Eine Seite des Verlaufs (Akte und Kunde) wächst, bis eine Aktion ganz darauf steht, höchstens auf 10.000 Zeilen; darüber geht es mit älteren
   Zeilen weiter, Zeilen derselben Aktion mit genau demselben Zeitpunkt können dann fehlen.
5. Die Stammdaten speichern nur Gesendetes; Name, Kategorie, Land und „Verbraucher“ ausdrücklich leer 422; die Zahlungsbedingung leer =
   „Systemstandard verwenden“.
6. Eine Zeile zu einem Objekt bzw. einer Dachfläche führt mit „Öffnen“ auf deren Seite -- in beiden Verläufen.

#### Tests und Prüfung

Neu `tests/test_v556_kunde_verlauf_und_stammdaten.py` (16 Tests): Strom des Kunden mit Kunde und Profil in einer Zeile, Kundenwissen (auch der
gelöschte Eintrag), Objekt und Dachfläche mit Ziel, Zahlung, Versand als eigene Zeile, nichts von einem anderen Kunden (über die Protokollzeilen,
auch bei neu vergebener Kennung); Filter nach Art, unbekannte Art 422; Seiten mit kleiner Grenze ohne Doppelte und Lücken (je Protokollzeile und
Versand); eine Aktion mit fünf Zeilen gleichen Zeitpunkts über der Grenze kommt ganz; an der Höchstgrenze endet das Blättern; dasselbe im Verlauf der
Akte; Rollen (Büro 200, Monteurin 403, unbekannt 404); Stammdaten: nur das Telefon gesendet -> nur das Telefon geändert und protokolliert,
Zahlungsbedingung ausdrücklich leer, vier Pflichtfelder leer 422.

Angepasste Erwartungen:
- `tests/test_v329_update_handler_struktur.py`, `BEKANNT` -- alt mit `PUT /api/customers/{customer_id}` (volles Formular), neu ohne (61 -> 60
  Einträge; die Liste darf nur kürzer werden).

Gegenproben (Marker `GEGENPROBE`, byte-genau zurück, je FAILED in `test_v556`): gelöschte Einträge nicht über den Schnappschuss -> 2; Kennungen
aller Kunden -> 1; Seite wächst nicht -> 1; alle Felder statt der gesendeten -> 2; Versand an die nächste Aktion gehängt -> 1; ohne Zeitfenster -> 1;
ohne Rückfall an der Höchstgrenze -> 1.

### R3, Punkte 2, 3, 5 (1.9.137): die Kundenakte als Seite

- `app/templates/customer.html` neu nach den Vorlagen, Aufbau und CSS wie `akte.html`: Pfad, Kopf über das Makro (`.ds-seite`, steht seit dieser Version in
  `UMGEZOGEN`), „+ Projekt“, „⋮“; Reiter mit Anker (`reiterZeigen()`, `ALTE_ANKER={versand:'verlauf'}`, `#zahlungen` ist selbst ein Reiter). Bereiche des Lesens:
  `kunde` (Kunde, Objekte mit Dachflächen, Anfragen, Auswahllisten), `akte` (`GET /api/customers/{id}/akte`), `dokumente`, `zahlungen`, `verlauf`; `render()`
  fasst keinen Dialog an, die Felder füllt erst das Öffnen. Stammdaten: `stammdatenOeffnen()` merkt den Stand (`stammdatenStand`), `saveCustomer()` schickt nur
  die Abweichung, ohne Abweichung keine Anfrage. Dialoge: Stammdaten, Eintrag, Objekt, Dachfläche, Dokument; mit `{% if geld %}` Zuordnen, Erstatten,
  Zurücknehmen. Alle Knöpfe über `data-klick`/`aktion()` (zwölf Handler mit IDs weniger, `AUSNAHMEN_HANDLER` jetzt 260 statt 272; die Zahl 285 in dieser Datei
  und in CLAUDE.md stand seit dem Umbau der Akte zu hoch).
- `app/kundenakte.py`: `geld()["unbezahlte"]` (Zeilen aus `invoice_overview_rows()`, älteste Fälligkeit zuerst), `projekte()` mit `property_id`.
- Bausteine: `_statuskennzeichen.html::statusFreieGruppen()` (Gruppe `kundenkategorie`: freier Wert aus den Stammdaten, Text unverändert, eine Bedeutung);
  `_seitenkopf.html`: Untertitel darf eine Liste aus Text und `{text, href}` sein (Link über `sichererLink()`); `_menue.html::dsMenueTrennerOrdnen()` und
  `.ds-menue-trenner` in `ds.css`; `_rechnungsliste.html`: Spalte `projekt`, `opt.kopf`, `opt.mitJahr`.
- `akte.html`: „⋮“ in drei Gruppen -- Status (Fortsetzen, Pausieren, Abschließen, Storno zurücknehmen, Stornieren), Projekt (bearbeiten, Beteiligte, Kopieren, Muster,
  Wartungsvertrag, Archivieren, Löschen), Wege (Auftragsbestätigung, Arbeitsvorbereitung, Einsatzberichte).
- `app/audit.py::_entity_label()`: ein Eintrag des Kundenwissens heißt im Protokoll nach seiner Bezeichnung; `akte_verlauf.ueberschrift()` nennt Art und Name nicht doppelt,
  wenn der Name nur die Art ist (ältere Zeilen: „Kundenwissen Kundenwissen angelegt“).

Punkt 4: „Kunde archivieren“ nicht gebaut (am Kunden gibt es kein Archivieren). Punkt 5: Stunden zeigt die Kundenakte keine; Daten, die für sich stehen, mit Jahr
(`tagLang`), kurz nur im Stand der Rechnungsliste („überfällig seit 03.10.“, wie die Vorlage) und im Verlauf; „unbezahlt“ und „noch nicht abgerechnet“ durchgängig,
auch in der Auswahl „Rest zuordnen“ (bis 1.9.136 „offen“).

Fund beim Bau (behoben): auf 412 px ragte die Tabelle der Zahlungseingänge über die Karte (sie darf nicht rollen, sonst schneidet sie das „⋮“ ab). Die Prüfung
`document.documentElement.scrollWidth<=innerWidth+1` sah das nicht: `innerWidth` wächst in der Mobil-Emulation mit dem Inhalt. Schmal steht je Eingang ein Block; der
Klicktest misst je Reiter gegen die Gerätebreite 412. Dieselbe schwache Prüfung steht noch in 15 älteren Klicktests (`grep scrollWidth scripts/`) -- nur in
`klicktest_zahlungen_kleinkram` geändert, weil er die Kundenakte betrifft; die übrigen sind offen und im Bericht genannt.

#### Festlegungen 1.9.137 (bestätigt am 30.10.2026)

1. Die Kategorie steht im Kopf an der Stelle des Status, blau wie die Vorlage; sie ist kein Status (freie Gruppe `kundenkategorie`, Wert unverändert).
2. „Rechnungen an“ in der Karte Stammdaten ist die primäre E-Mail des Kunden -- an sie geht die Rechnung (`get_invoice_recipient_email()`); ein eigenes Feld gibt es nicht. Im Dialog heißt das Feld „Primäre E-Mail (Rechnungen an)“.
3. Die Spalte „Art“ der Zahlungseingänge nennt Zahlung, Erstattung (Zahlungsausgang) oder übernommen aus „bezahlt“ -- „Überweisung“ der Vorlage gibt es nicht als Feld und ist nicht erfunden.
4. „Zugeordnet“ nennt Rechnung und Betrag, die Art nur bei Skonto und Einbehalt; „· bezahlt“ der Vorlage steht nicht dort (das ist der Stand der Rechnung, nicht der Zuordnung).
5. Kennzeichen der Phase in den Projektzeilen: Anfrage und Angebot blau, ab dem Auftrag grün, abgeschlossen und storniert grau.
6. „Abgeschlossen: …“ nennt abgeschlossene, stornierte und archivierte Projekte, höchstens fünf, danach „und n weitere“ auf den Reiter Projekte.
7. Die Objektzeile der Übersicht nennt Dachflächen und Projekte; „Wartungsvertrag · nächste Wartung“ der Vorlage fehlt -- die Daten des Kunden liefern das nicht, der Reiter Objekte führt zum Objekt.
8. Die Karte „Versand“ entfällt: Filter „Versand“ im Verlauf, `#versand` führt dorthin; „Zustellung nachtragen“, „Empfang bestätigt“ und „unzustellbar“ im Dialog am „⋮“ der Versandzeile, Rechnung und Mahnung nur mit `darf_geld()` -- wie in der Akte.
9. „⋮“ je Eingang: Zuordnen nur mit Rest und unbezahlter Rechnung, Erstatten nur mit Rest; Zurücknehmen immer -- geht es nicht, nennt der Dialog den Grund und zeigt keinen Knopf.
10. Vorschläge: im Reiter Zahlungen je Posten des Guthabens einer, in der Übersicht nur der erste.
11. Der Dialog „Erstattung buchen“ zeigt alle Posten des Guthabens, vorbelegt nur den gewählten; weitere Beträge lassen sich eintragen -- ein Zahlungsausgang für alle.
12. Stammdaten ohne Änderung: der Dialog schließt ohne Anfrage.
13. Die Karte Stammdaten nennt neben den Zeilen der Vorlage nur gefüllte Felder: Ansprechpartner, zweite E-Mail, Mobil (wenn der Kopf das Telefon zeigt), Fax.
14. „⋮“ der Akte: „Stornieren …“ steht in der Gruppe Status (bis 1.9.136 vor „Löschen“), die Wege am Ende.
15. Schmal (bis 760 px) stehen die Zahlungseingänge als Blöcke statt als Tabelle.
16. Ein Eintrag des Kundenwissens heißt im Verlauf nach seiner Bezeichnung („Kundenwissen Sabine Kessler, Geschäftsführung angelegt“), ohne Bezeichnung nur „Kundenwissen angelegt“; der Text der Vorlage „Kontakt „…“ ergänzt“ ist nicht übernommen (ein Satz für alle Arten wie in der Akte).

#### Tests und Prüfung

Neu `tests/test_v557_kundenakte_seite.py` (15 Tests, das Skript der Seite in node mit den Antworten der echten Endpunkte): `#zahlungen` öffnet den Reiter mit den Zahlen des
Servers, `#versand` den Verlauf mit „Versand“, ohne Anker die Übersicht; Büro – Auftrag ohne Knöpfe und Dialoge, Zuordnen 403, Finanzen 200, Rest danach 0; Stammdaten: Eingabe
bleibt nach `render()` und `load()`, gesendet nur das Geänderte, ohne Änderung nichts; Kunde ohne Projekt; Zeilen `unbezahlte`; Trennlinien; Untertitel mit Links (fremder Link
`#`); „⋮“ von Akte und Kundenakte; Rechnungsliste. `tests/test_v554_kundenakte_funktionen.py`: die Tabelle jetzt mit den Belegen der neuen Seite (38 Funktionen). Neu
`scripts/klicktest_kundenakte.py` (Kopf, jeder Reiter, „⋮“, Dialoge, Zuordnen über den Vorschlag, Stammdaten, Verlauf, dunkel, 412 px gegen die Gerätebreite, Akte-Menü, Kunde
ohne Projekt, Monteurin 403; nimmt die Bilder der Übergabe auf).

Angepasste Erwartungen, Tests:
- `tests/test_v554_kundenakte_funktionen.py`, `FUNKTIONEN` -- alt Belege der früheren Seite (`onclick="saveCustomer()"`, `id="metricNet"`, `id="customerDispatches"` …), neu die der Kundenakte; Testname `…auf_der_heutigen_seite` -> `…auf_der_kundenakte`; Pfade aus Kommentaren („/api/customers/{id}/akte“) zählen mit.
- `tests/test_v441_rahmen_baustein.py` -- alt `customer.html` in `AUFGESCHOBEN` (Stufe 5), neu in `UMGEZOGEN`.
- `tests/test_v407_daten_im_html.py`, `AUSNAHMEN_HANDLER` -- alt fünf Einträge zu `customer.html` (zwölf Handler), neu keine.
- `tests/test_v424_zahlgrenzen.py`, `ABGLEICH` -- alt `id=restAmount-${p.id}`, neu `id=restAmount`.
- `tests/test_v451_zahlformat_anzeige.py`, `tests/test_v334_auswahl_restfaelle.py` -- alt Start `load().catch(`, neu `kundenakteStarten().catch(`; Soll gleich.
- `tests/test_v447_auswahl_altwerte.py::test_kunde_zusatzinfo_art` -- alt Auswahl `.xt` je Zeile über `renderExtras()`, neu Dialog `editExtra(1)`, Feld `extraTyp`; Soll gleich.
- `tests/test_v445_statuskennzeichen.py` -- alt jede Gruppe muss in der Tabelle stehen, neu auch eine freie Gruppe (`statusFreieGruppen()`); neuer Test `test_freie_gruppen`.
- `tests/test_v397_kleinkram_zahlungen.py` -- alt `paymentCardHtml()` mit Knopf „Zahlung zurücknehmen“ bzw. Grund, neu `zahlungZeile()` mit „Zurücknehmen …“ im „⋮“ und der Dialog mit Knopf bzw. Grund; alt `const opts=zahlungsOptionen(customerOpenInvoices.filter(`, neu `zahlungsOptionen(unbezahlteZumZuordnen(),`.
- `tests/test_v418_versand_im_kontext.py` -- alt `renderDispatchList('customerDispatches',…)`, neu Filter „Versand“ und Link `/versandprotokoll?kunde=`.
- `tests/test_v531_rechte_geld.py` -- alt `if(!p.reversed&&GELD){` und Karte `data-erstattung`, neu `if(GELD&&!p.reversed){`, Knöpfe der Vorschläge nur mit `GELD`, Dialoge unter `{% if geld %}`.

Angepasste Erwartungen, Klicktests (Bereit-Bedingung alt `lastName`-Feld, neu der geladene Kunde; das Feld steht erst im Dialog):
- `klicktest_anmelden` -- nur die Bereit-Bedingung.
- `klicktest_anmeldung_abgelaufen`, `klicktest_fremde_seite` -- Dialog öffnen; alt `customerStatus` „Gespeichert.“, neu `seitenStatus` „Stammdaten gespeichert.“ und Dialog zu.
- `klicktest_auswahl_restfaelle`, `klicktest_vertragsgrundlage` -- Felder im Dialog; `klicktest_vertragsgrundlage` neu: die Karte nennt die Vertragsgrundlage.
- `klicktest_dateien_nie_aktiv`, `klicktest_daten_im_html`, `klicktest_hochladen` -- Reiter `#dokumente` (Vorschaubilder laden erst sichtbar), Bereit-Bedingung.
- `klicktest_rechte_geld` -- alt `#zahlungen button`, `[data-erstattung]`, Knöpfe „Zuordnen“, „Zahlung zurücknehmen“; neu `#reiter-zahlungen button`, `#erstattenDialog`, Menüeinträge „Zuordnen …“, „Zurücknehmen …“.
- `klicktest_ueberzahlung` -- alt Karte mit `data-guthaben-summe` und Kennzeichen „Guthaben des Kunden: 69,00 €“, neu Kennzahl „69,00 €“, Posten `rest`, `guthaben`, zwei Vorschläge; alt „Zahlungsausgang Nr.“, „Erstattung aus dem Rest der Zahlung“, „aus dem Rest erstattet“; neu „Erstattung (Zahlungsausgang)“, „aus dem Rest des Eingangs“, „erstattet am“; Grund im Dialog.
- `klicktest_versand_im_kontext` -- alt Karte `#customerDispatches`, neu Reiter Verlauf über `#versand`, gleiche Nummern, Link `#versandprotokollLink`.
- `klicktest_zahlungen` -- alt Kennzeichen `paymentRestBadge`, Felder `restInvoice-<id>`, neu Kennzahl und Dialog.
- `klicktest_zahlungen_kleinkram` -- wie `klicktest_zahlungen`; alt Auswahl „· offen …“, neu „· unbezahlt …“; alt `scrollWidth<=innerWidth+1`, neu `scrollWidth<=412`.

Gegenproben (Marker `GEGENPROBE`, byte-genau zurück, je FAILED in `test_v557`): Anker nicht ausgewertet -> 3; alle Felder gesendet -> 2; Neuzeichnen füllt den Dialog -> 1; „⋮“ je Eingang ohne `GELD` -> 1; Knöpfe der Vorschläge ohne
`GELD` -> 1; alle Rechnungen als unbezahlt -> 1; Trennlinie immer -> 1; Link im Untertitel ungeprüft -> 1; Kategorie neutral -> 1; Daten ohne Jahr -> 2; Dialoge des Gelds für alle -> 1.

## Stufe 5, R4 (ab 1.9.138): Abschluss

Auftrag vom 30.10.2026 (Start HEAD 20aa620; Festlegungen R3 alle bestätigt; Kunde archivieren nicht bauen, steht auf der Merkliste im Parkplatz, `docs/archiv/befund-vor-echtbetrieb.md`):

1. Die 15 Klicktests mit der schwachen Breitenprüfung messen bei 412 px gegen die Gerätebreite wie `klicktest_kundenakte`; was dann überläuft, beheben; je Seite im Bericht: lief über ja/nein, was behoben.
2. Verlaufstexte der Zahlungen kürzer, ein Satzbau für Akte und Kunde: „Zahlungseingang 3.000,00 € vom 18.08.2025“, „144,00 € auf R-… zugeordnet“, „Erstattung 144,00 € gebucht“, „Zuordnung zurückgenommen – Begründung: …“; Einzelheiten weiter aufklappbar.
3. Kundendokumente ins Änderungsprotokoll (hochladen, Angaben ändern, löschen) und in den Verlauf des Kunden.
4. Projektzeile der Kundenakte: das Kennzeichen der Phase bricht nicht um (langer Name mit „…“ und vollem Namen als title).
5. Am Ende eine neue Bildgrundlage vom Endstand (Stufe 5 fertig).

### Umsetzung 1.9.138: Punkt 1

`scripts/cdp_klicktest.py`: `UEBERLAUF` (JS) und `Tab.ueberlauf(breite=None)` -- die Seite (`documentElement.scrollWidth`) und jedes sichtbare Element mit rechter Kante über der Breite, außer in einem Behälter mit `overflow-x` ungleich `visible` (eine Tabelle in ihrem rollenden Rahmen ist gewollt); höchstens sechs Zeilen je Messung, leer = passt. Ohne Angabe die Breite aus `tab.fenster()`. `Tab.bild_ganz()` nimmt die ganze Seite auf. `ROLLT_IM_RAHMEN` schreibt ins Protokoll, was im eigenen Rahmen rollt (kein Fehler).

Ergebnis je Seite, gemessen auf 20aa620 (lief über: nein bei allen; behoben: nichts):

| Klicktest | Seite | lief über | rollt im eigenen Rahmen |
|---|---|---|---|
| bedenkenanzeige, behinderungsanzeige | Checkliste, Monteurin | nein | -- |
| bedenkenanzeige_versand, behinderungsanzeige_abschluss, behinderungsanzeige_versand, versandverlauf | Checkliste, Büro | nein | -- |
| beleg_und_hinweis | Einsatzberichte, Checklisten zum Auftrag (Monteurin) | nein | -- |
| beteiligte | Akte mit Dialog „Beteiligte“ | nein | Reiterleiste |
| beteiligte_stammdaten | Dialog „Beteiligten hinzufügen“ | nein | Reiterleiste |
| ersteinrichtung | Hinweisseite ohne Konto | nein | -- |
| nebenforderungen | Rechnung | nein | -- |
| rahmen | Kopfzeile, Monteurskopf, Prüfvorlagen, Anmeldung, Sperrseite | nein | Tabelle „Vorlagen“ der Prüfvorlagen |
| versandprotokoll | Versandprotokoll | nein | Tabelle |
| vertragsvorlagen | Einstellungen | nein | -- |
| zeiten | Prüfen, Buchungen, Abwesenheiten, Monat & Lohn | nein | Reiterleiste; Tabellen in Buchungen und Monat & Lohn |

Dazu dieselbe Umstellung in `klicktest_lv_ueberlauf` (seit dieser Version auch jeder Reiter der Akte: nichts ragt hinaus, Reiterleiste und Tabellen rollen) und `klicktest_zahlungen_kleinkram`; `klicktest_kundenakte` nimmt `tab.ueberlauf()` statt der eigenen Messung.

Die Bilder bei 412 px sind von Hand durchgesehen (Kontaktbogen aller 23): nichts abgeschnitten außer in den genannten Rahmen.

**Zur Prüfung gegen `clientWidth`:** rund 15 Klicktests (u. a. abnahme_aus_protokoll, feste_fassung, maengel_monteur, neue_ordnung, vertrag_unterschrift) messen `scrollWidth<=documentElement.clientWidth+1`. `clientWidth` bleibt in der Emulation fest; `feste_fassung` und `maengel_monteur` wurden in der Gegenprobe rot. Sie sind deshalb nicht umgestellt.

#### Tests und Prüfung

Neu `tests/test_v558_klicktest_breite.py`: Wächter (kein Klicktest misst `scrollWidth` gegen `innerWidth`, ohne Kommentare; das Muster erkennt die alte Schreibweise), jeder umgestellte Klicktest nutzt `.ueberlauf(`, `UEBERLAUF` in node an einer Attrappe (zu breite Seite, zu breites Element bei passender Seite, Element im rollenden Behälter, verstecktes und leeres Element, Rand ±0,5 px), ohne Breite ein Fehler.

Gegenproben:
- A, alle Seiten breiter (`_ds_kopf.html` und `_ersteinrichtung_seite()`, Marker GEGENPROBE: `body{min-width}` 700 px bis 500 px Fensterbreite, sonst 1500 px): alle 15 Klicktests rot an der Breitenprüfung mit „Seite 700 px breit“ und den Elementen (`rahmen`: Kopfzeile, Monteurskopf bei 412/800/1280, Prüfvorlagen, Anmeldung und Sperrseite hell und dunkel, bei 412 und 1440); ebenso `kundenakte`, `lv_ueberlauf`, `zahlungen_kleinkram` und die beiden Klicktests mit `clientWidth`. Grün blieb nur `zeiten_abgeschlossen`, das bei 412 px nichts misst. Vorher und nachher byte-genau gleich (Prüfsumme), danach grün.
- B, nur ein Element ragt hinaus und die Seite schneidet (`html,body{overflow-x:hidden}`, `h1{min-width:700px}`): vier Klicktests rot mit `h1#seitenkopfTitel.ds-kopf-titel bis 718 px` -- die Elementprüfung trägt allein.

Angepasste Erwartungen (Regel 28), alle mit gleichem Soll „nichts ragt hinaus“ und strengerer Messung: altes Soll `document.documentElement.scrollWidth<=innerWidth` wahr, neues Soll `tab.ueberlauf()` leer: bedenkenanzeige, bedenkenanzeige_versand, behinderungsanzeige, behinderungsanzeige_abschluss, behinderungsanzeige_versand, beleg_und_hinweis (2), beteiligte, beteiligte_stammdaten, ersteinrichtung, nebenforderungen, rahmen (Kopfzeile, Monteurskopf, Prüfvorlagen, Anmeldung, Sperrseite; der Listenwert `breit_scroll` entfällt, dort steht die Liste aus `ueberlauf()`), versandprotokoll, versandverlauf, vertragsvorlagen, zeiten (1440 und 412), lv_ueberlauf, zahlungen_kleinkram. `zeiten`: eine Prüfung bei 412 px wird zu vier (je Reiter); `lv_ueberlauf`: zehn neue (alle Reiter sichtbar, je Reiter der Akte).

Festlegungen zu Werkzeug und Testablauf: 5, in `docs/archiv/testablauf-und-klicktests.md`.

### Umsetzung 1.9.139: Punkt 2

`app/akte_verlauf.py`: `_zahlung_teile(z)` liefert je Protokollzeile `(Satz, Zusatz)` aus dem Schnappschuss des Anlegens (`details`), `zahlung_text(z)` den Satz für sich (`Satz · Zusatz`, für „Einzelheiten“), `_zahlung_ueberschrift(g)` Überschrift und Zeile darunter einer Gruppe. Art der Zeile: Schlüssel `kind` = Zuordnung, `received_on` = Zahlung (beide stehen im Protokoll unter „Zahlungseingang“). Die Rechnungsnummer steht nur in der Bezeichnung (`… an R-…`, `_rechnung_aus_bezeichnung()`), der Schnappschuss kennt nur die Kennung; fehlt sie, „Rechnung“.

| Buchung | Satz | darunter |
|---|---|---|
| Zahlungseingang | Zahlungseingang 3.000,00 € vom 18.08.2025 | die Zuordnungen derselben Aktion |
| Zuordnung | 144,00 € auf R-… zugeordnet | |
| Skonto, Einbehalt | Skonto 5,00 € auf R-… | |
| auf eine Nebenforderung | 5,00 € auf Nebenforderung von R-… zugeordnet | |
| Erstattung (Zahlungsausgang) | Erstattung 144,00 € gebucht | aus R-… (bei einer Endrechnung) |
| Zuordnung zurückgenommen | Zuordnung zurückgenommen – Begründung: … | 144,00 € auf R-… |
| Zahlung zurückgenommen | Zahlungseingang zurückgenommen – Begründung: … | 3.000,00 € vom 18.08.2025 |
| Erstattung zurückgenommen | Erstattung zurückgenommen – Begründung: … | 144,00 € |

`_einzelheit(z)` ersetzt in `einzelheiten` die lange Bezeichnung durch `kurz` (`entity_label` = null); `verlaufEinzelheit(z)` (`_verlauf.html`) zeichnet die Zeile für Akte und Kundenakte. Eine Zeile ohne lesbaren Schnappschuss fällt auf den allgemeinen Satz zurück, ohne die Art davor („Zahlungseingang Zahlung …“ gibt es nicht mehr).

#### Festlegungen 1.9.139 (Bitte bestätigen)

1. Die Sätze entstehen beim Lesen aus dem Schnappschuss, nicht aus einer geänderten Bezeichnung: so gelten sie auch für ältere Zeilen, und das Protokoll (`/history`, unveränderlich) bleibt, wie es ist.
2. In der Akte steht weiter nur die Zuordnung, nicht der Eingang: die Zahlung gehört zum Kunden, nicht zum Projekt (`Payment` trägt kein Projekt). Ein Eingang über 3.000 € mit 144 € auf dieses Projekt zeigt in der Akte „144,00 € auf R-… zugeordnet“.
3. Unter einer Überschrift höchstens zwei weitere Buchungen, dann „und n weitere Einzelheiten“.
4. Unter einer Zurücknahme steht der Betrag, was mit ihr zurückgeht, steht unter „Einzelheiten“.
5. Skonto, Einbehalt und die Erstattung aus einer Endrechnung sind in der Vorgabe nicht genannt: gleicher Satzbau („Skonto 5,00 € auf R-…“, „Erstattung 144,00 € gebucht“ / „aus R-…“).

#### Tests und Prüfung

Neu `tests/test_v559_verlauf_zahlungen.py` (Sätze aller Buchungen über die echten Endpunkte beider Verläufe; jede Zeile, die in beiden Strömen steht, trägt denselben Satz; kein `Zahlung.*Zahlung` in Überschrift, Unterzeile und Einzelheiten; Protokoll unverändert; Zeile ohne Schnappschuss; Baustein der Seite in node). `klicktest_kundenakte`: Zahlungseingang, Zurücknahme und Erstattung über die API, Verlauf beider Seiten im Browser, Einzelheiten aufklappbar, Bilder `verlauf_zahlungen_kunde` und `verlauf_zahlungen_akte`.

Angepasste Erwartungen: `tests/test_v535_aenderungsprotokoll.py::test_history_und_projektmappe_nehmen_verlauf_aenderung[akte.html]`: altes Soll `${verlaufAenderung(z)}` steht in `akte.html`, neues Soll `verlaufEinzelheit(z)` in `akte.html` und `${verlaufAenderung(z)}` im Baustein `_verlauf.html`. Sonst keine; die bestehenden Prüfungen nennen die alten Sätze nicht.

Gegenproben (je FAILED, byte-genau zurück), rote Tests in Klammern: lange Bezeichnung in den Einzelheiten (1); kein kurzer Satz in der Überschrift (7); Art davor beim Rückfall (1); Kopf nicht die Zahlung (2); Erstattung wie Eingang (1); Zurücknahme ohne Begründung (3); alle Zuordnungen darunter (1); Seite ohne `kurz` (1); `kurz` ohne Maskierung (1); Rechnungsnummer fehlt (5). „Art davor“ blieb zuerst grün: der Test machte nur eine von zwei Zeilen unlesbar und erreichte den Rückfall nicht; jetzt beide, mit genauer Erwartung.

### Umsetzung 1.9.140: Punkt 3

`app/audit.py`: `CustomerDocument` in `AUDITED_TYPES` und `TYPE_LABELS` („Kundendokument“), Bezeichnung = `original_filename` wie an der Projektdatei. `app/kunde_verlauf.py`: Art „Kundendokument“ in `TYPEN`, Zuordnung zum Kunden wie die übrigen Arten (heute über die Spalte, gelöscht über den Schnappschuss, Zeitfenster bei einer wiederverwendeten Kennung). Die Endpunkte bleiben unverändert: die Protokollzeilen entstehen beim Flush.

Eine Zeile je Aktion wie überall: zwei Dateien in einer Anfrage derselben Aktion wären eine Zeile mit zwei Einzelheiten; die Seite lädt je Datei einzeln hoch, innerhalb von 5 s (`GRUPPE_SEKUNDEN`) stehen mehrere in einer Zeile.

**Fund:** `category` und `category_id` ändern sich zusammen und ergaben zwei gleiche Zeilen („Kategorie Sonstiges → Rechnungen / Belege“), der Verlauf schrieb „und 1 weitere Einzelheit“. Jetzt `STILL_JE_ART` für beide Dateiarten (auch die Projektdatei in der Akte, dieselbe Doppelung).

#### Festlegungen 1.9.140 (Bitte bestätigen)

1. Überholt Festlegung 1.9.136 Nr. 1: Kundendokumente stehen jetzt im Verlauf des Kunden.
2. Im Verlauf steht „Kundendokument vertrag.pdf angelegt“ wie an der Projektdatei, nicht „hochgeladen“: ein Satzbau für alle Arten.
3. Protokolliert wird der Name der Kategorie, nicht zusätzlich ihre Kennung -- auch an der Projektdatei, über die Vorgabe hinaus, weil es dieselbe Doppelung ist.
4. Keine Zeile führt zur Datei („Öffnen“): nach dem Löschen gäbe es sie nicht mehr, und die Vorgabe verlangt es nicht.

#### Tests und Prüfung

Neu `tests/test_v560_kundendokumente_verlauf.py`: Hochladen und Löschen über die echten Endpunkte ergeben zwei Zeilen im Verlauf und im Protokoll; gelöschtes Dokument bleibt sichtbar; Angaben ändern ist eine Zeile mit den geänderten Feldern; nichts beim anderen Kunden, auch nicht nach dem Löschen; Filter; Ablagename nicht in der Zeile; Kategorie einmal und lesbar. `klicktest_kundenakte`: Hochladen und Löschen, beide Zeilen nebeneinander im Verlauf, Bild `verlauf_kundendokument`.

Angepasste Erwartungen: keine.

Gegenproben (je FAILED, byte-genau zurück), rote Tests in Klammern: nicht im Protokoll (7); nicht im Verlauf (7); zwei Zeilen „Kategorie“ (2); ohne Dateiname (5); gelöschtes Dokument nicht mehr dem Kunden zugeordnet (2).
