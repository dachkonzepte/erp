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

**Warum im Endlauf rund 500 ms:** Dort liefen vier Klicktests samt Chrome zugleich. Mit vier Servern zugleich steigt die erste Anfrage
hier auf 380–458 ms: derselbe Aufbau, langsamer bei geteilter CPU. Die 506 ms im Verbindungsprotokoll liegen in derselben Größenordnung.

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
