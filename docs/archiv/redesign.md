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
