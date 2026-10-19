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

- **Ursache**: `app/audit.py` speichert beim Schreiben `TYPE_LABELS.get(type(obj))` bzw. `FIELD_LABELS.get(feld, feld)` -- fehlte ein Eintrag, landete der Klassen- bzw. Spaltenname in der Zeile (16 von 104 protokollierten Arten, 199 von 419 Feldnamen). Werte wurden roh gespeichert und roh angezeigt (`history.html` setzte `old_value`/`new_value` unverändert ein). Die Seite rief `/api/audit-logs?limit=500` auf; die API kannte keinen Versatz, ältere Einträge waren nicht erreichbar.
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
- **Änderung**: Anzeige über `zahlText()` aus `_zahl.html` (deutsches Format, ohne überflüssige Nullen) mit geschütztem Abstand vor dem Prozentzeichen: `${zahlText(x)} %`. Der Stundensatz lief schon über `money()` und bleibt.
- **Test**: `test_leistung_standardwerte_der_prozente_lesbar` (Seitenskript in node, `renderDefaults()` mit "0.0000", "12.5000", "5.0000" → „(Standard: 0 %)“, „(Standard: 12,5 %)“, „(Standard: 5 %)“) -- vorher rot („(Standard: 0.0000%)“).
