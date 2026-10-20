# Befund Stufe 2 „Rahmen“ (nur Befund, nichts geändert)

Vorgabe vom 20.10.2026 (übernommen wie gegeben): „Stufe 2 „Rahmen“ – erst Befund, nichts ändern außer Doku. 1. Seitenleiste
(_sidebar.html): Einträge je Rolle, wie der aktive Eintrag bestimmt wird, Höhe bei 1440 × 900 und 1280 × 800, ab wann sie scrollt, was das
Logo oben an Höhe kostet. Wie hoch wäre sie mit vier Gruppen (Übersicht; Aufträge; Kaufmännisch mit Personal; Verwaltung = Stammdaten +
System), den heutigen Einträgen und einem Logo von 48 px? 2. Seitenköpfe: Gruppiere die 53 Seiten nach Kopf-Muster (Titel, Kennung, Status,
Aktionen, Zurück-Link, Pfad). Was davon baut jede Seite selbst? 3. Monteurskopf (_mobile_header.html): Höhe bei 1280 × 620 und 800 × 1100,
welche Seiten ihn nutzen. Was hängt daran, dass Einsatzbericht und Konto noch den Büro-Rahmen haben? 4. Was würde ein Rahmen mit den
--ds-*-Werten auf den 53 Seiten sofort sichtbar ändern (Schrift, Farben, Abstände), und wo droht etwas zu brechen, auch im Dunkelmodus?
5. Vorschlag: gemeinsamer Seitenkopf als Jinja-Baustein (Pfad, Kennung, Titel, Status, eine Hauptaktion, Menü „⋮“) und eine Reihenfolge, in
der die Seiten umziehen, ohne dass zwischendurch etwas bricht. Bericht mit Zahlen, bei Bedarf mit Bildern aus bildgrundlage/31b85e8.“

Stand: Commit `7c5172c` (1.8.160). **Gemessen** in einer Instanz wie die Bildgrundlage (Testdaten aus `scripts/bildgrundlage.py::befuellen()`,
stehende Uhr 14.10.2026 10:00, Wegwerf-SQLite, Chrome 155.0.8059.40, alle Module an), mit einem Messskript nur im Scratchpad: Seitenleiste je
Rolle und Fenster (auch mit simuliertem Logo und umgebauten Gruppen, nur im DOM), Kopf jeder Seite (1440 und 412 px), Monteurskopf
(1280 × 620, 800 × 1100, 412 × 900, als Gerät) und eine Probe mit den `--ds-*`-Werten (Abschnitt 4). Dazu statisch über die 53 Seiten aus
`tests/vorlagen_js.py::seiten()` und die Bilder in `bildgrundlage/31b85e8`. Nichts an Code, Vorlagen oder Tests geändert.

Rollen wie in der Bildgrundlage: „Finanzen“ = Büro – Finanzen, „Auftrag“ = Büro – Auftrag, „Monteurin“ = field.

## Rahmen der 53 Seiten

| Rahmen | Seiten |
|---|---|
| Seitenleiste + Kopfzeile (`_sidebar.html`, `_topbar.html`) | 40 |
| je nach Rolle Büro-Rahmen oder Monteurskopf (`checklist.html`, `checklist_order.html`) | 2 |
| nur Monteurskopf (`_mobile_header.html`): `mobil`, `mobil_objekt`, `field_timesheet`, `time_tracking_field`, `operational_asset_field` | 5 |
| ohne Rahmen: `login`, `access_denied` und die vier Formularseiten `project_form`, `quote_form`, `master_data_form`, `service_form` | 6 |

Die Monteurin sieht den Büro-Rahmen auf `service_reports.html` (Einsatzbericht) und `account.html` (Konto), sonst den Monteurskopf
(`tests/test_v431_bildgrundlage.py::test_monteurin_hat_den_rahmen_auf_einsatzbericht_und_konto`).

## 1. Seitenleiste

### Einträge je Rolle

Sechs Gruppen seit 1.8.112 (`docs/archiv/stammdaten-und-sidebar.md`, „Neue Ordnung“); eine Überschrift steht nur, wo die Rolle etwas sieht.

| Rolle | Gruppen | Einträge (alle Module an) |
|---|---|---|
| Finanzen, Admin | Übersicht · Aufträge · Kaufmännisch · Personal · Stammdaten · System | 17: Start, Aufgaben, Kalender · Anfragen, Projekte, Plantafel, Checklisten, Wartungen, ↳ Befunde · Finanzen, Mahnwesen, Eingangsrechnungen, Betriebskosten · Zeiterfassung, Backoffice · Stammdaten · Einstellungen |
| Auftrag | dieselben sechs | 15: ohne Eingangsrechnungen und Betriebskosten |
| Monteurin (nur auf Einsatzbericht und Konto) | Übersicht · Personal | 2: Start (führt über `/` nach `/mobil`), Zeiterfassung |

Sieben Einträge hängen an Modulen (Aufgaben, Kalender, Checklisten, Wartungen + Befunde, Eingangsrechnungen, Betriebskosten) -- mit allen
Modulen aus hat Finanzen 10 Einträge.

### Aktiver Eintrag

Jinja vergleicht `request.url.path` **genau** mit der Adresse des Eintrags (`' active' if path == '/projects'`), nur Checklisten mit
`path.startswith('/checklisten')`. Gemessen auf allen 42 Seiten mit Seitenleiste: **21 markieren einen Eintrag, 21 keinen** -- jede
Detailseite unter einem Bereich:

| läge unter | Seiten ohne aktiven Eintrag |
|---|---|
| Projekte | Projektmappe, Angebot, Auftrag, Arbeitsvorbereitung, Einsatzbericht, Rechnung |
| Wartungen | Wartungsvertrag, Prüfvorlagen, Prüfvorlage |
| Stammdaten | Kunde, Objekt, Dachfläche, Betriebsmittel, Leistungskatalog |
| Einstellungen | Benutzer, Änderungshistorie, Adressimport, Versandprotokoll, Changelog |
| keinem | Suche, Konto |

Ebenso der Monteurskopf: der Reiter ist nur bei genau `/mobil`, `/time-tracking`, `/mobil/stundenzettel` aktiv -- Objekt, Betriebsmittel und
die Checklisten der Monteurin zeigen keinen.

### Höhe und Bildlauf

Die Leiste ist `position:sticky; height:100vh`, Kopf und unterer Bereich stehen fest, nur die Navigation (`.app-sidebar-nav`,
`overflow-y:auto`) scrollt. Ein Eintrag ist 36–37 px hoch (+1 px Abstand), eine Gruppenüberschrift rund 35 px (die erste rund 25), die
Navigation hat 2 × 10 px Polster. Kopf mit Schriftzug 62 px, unterer Bereich 86 px (Hell/Dunkel und Einklappen, Version); die Kopfzeile
(`_topbar.html`, 63 px) liegt im Inhaltsbereich, nicht über der Leiste.

| Rolle | Navigation, Inhalt | Fensterhöhe ohne Bildlauf | 1440 × 900: sichtbar / verdeckt | 1280 × 800: sichtbar / verdeckt |
|---|---|---|---|---|
| Finanzen, Admin | 866 px | **1014 px** | 752 / 114 px | 652 / 214 px |
| Auftrag | 790 px | **938 px** | 752 / 38 px | 652 / 138 px |
| Monteurin | rund 156 px | rund 304 px | kein Bildlauf | kein Bildlauf |

Bild: `bildgrundlage/31b85e8/buero__hell__1440__start--leiste_unten.png` (Finanzen bei 900 px, Navigation ganz unten gescrollt),
`buero_auftrag__hell__1440__start--leiste.png`.

### Was das Logo kostet

Der Kopf ist **Logo-Höhe + 41 px** (20 + 20 px Polster, 1 px Linie): mit Schriftzug (ohne Logo, wie in den Testdaten) 62 px, Logo 48 px →
89 px (+27), **Vorgabe 64 px → 105 px (+43)**, Höchstwert 120 px → 161 px (+99). Mit dem Logo der Leiste in der Vorgabehöhe braucht
Finanzen 1057 px Fensterhöhe ohne Bildlauf. (Eingeklappt, 60 px breit: Logo fest 32 px.)

### Vier Gruppen mit Logo 48 px

Umgebaut im DOM: Übersicht (Start, Aufgaben, Kalender) · Aufträge (Anfragen, Projekte, Plantafel, Checklisten, Wartungen, ↳ Befunde) ·
Kaufmännisch (Finanzen, Mahnwesen, Eingangsrechnungen, Betriebskosten, Zeiterfassung, Backoffice) · Verwaltung (Stammdaten, Einstellungen).
Zwei Überschriften weniger sparen 70 px, das Logo 48 kostet 27 mehr als der Schriftzug.

| Rolle | Navigation | Fensterhöhe ohne Bildlauf | bei 900: verdeckt | bei 800: verdeckt |
|---|---|---|---|---|
| Finanzen, Admin | 796 px | **971 px** (Logo 64: 987) | 71 px | 171 px |
| Auftrag | 720–725 px | **896–900 px** (Logo 64: 911) | 0 (passt genau) | rund 100 px |
| Monteurin | rund 156 px (zwei Gruppen wie heute) | rund 331 px | 0 | 0 |

- Bei 1280 × 800 scrollt die Leiste für die Büro-Rollen auch mit vier Gruppen. Damit 17 Einträge in 800 px passen, fehlen rund 171 px --
  z. B. Zeilen von 30 statt 37 px (−119) und ein unterer Bereich von 36 statt 86 px (Hell/Dunkel und Einklappen in die Kopfzeile, −50)
  ergäben ≈ 802 px, knapp darüber.
- **Monteurin**: ihre einzige Gruppe mit Zeiterfassung hieße „Kaufmännisch“ -- die Überschrift bräuchte für sie einen anderen Namen oder
  entfällt.

## 2. Seitenköpfe

### Muster

Gruppiert nach dem, was über dem ersten Inhalt steht (Bilder `bildgrundlage/31b85e8/buero__hell__1440__<seite>.png`). Abstand Oberkante →
Inhalt bei 1440 px: Kopfzeile 63 px, dann der Seitenkopf.

| Muster | Seiten | Aufbau | Inhalt beginnt bei |
|---|---|---|---|
| K1 Titelzeile auf dem Grund (9) | Start, Aufgaben, Checklisten, Checklisten-Vorlagen, Wartungen, Befunde, Prüfvorlagen, Eingangsrechnungen, Betriebskosten | h1 22 px + Untertitel ohne Karte; Aktion rechts (4) oder unter dem Untertitel (3), Schalter „Archivierte anzeigen“ daneben | 151–225 px |
| K2 Titelkarte (7) | Projekte, Finanzen, Mahnwesen, Versandprotokoll, Changelog, Suche, Zeiterfassung (Büro) | Titel in einer weißen Karte, teils mit Filtern oder Suchfeld darin; 5 davon h1 in Browser-Größe (32 px), Zeiterfassung h2 | 162–314 px |
| K3 Datensatz mit Pfad (7) | Objekt, Dachfläche, Betriebsmittel, Wartungsvertrag, Checklisten-Vorlage, Prüfvorlage, Einsatzbericht | Pfad · Titel = Name · Unterzeile; Aktionen rechts (bis 6), Status unter dem Titel (2) | 174–178 px (Wartungsvertrag mit Hinweiszeile mehr) |
| K4 Belegkopf in Karte (8) | Projektmappe, Angebot, Auftrag, Rechnung, Arbeitsvorbereitung, Kunde, Checkliste, Checklisten je Auftrag | Pfad über der Karte (3); Karte mit Kennung · Titel, Kunde/Objekt, Status, Beträge oder Kennzahlen, Knopfreihe; bei Angebot, Auftrag, Rechnung, Arbeitsvorbereitung ist der „Titel“ ein fettes `div`, kein h1 | rund 205–285 px |
| K5 Untermenü links (3) | Stammdaten, Einstellungen, Backoffice | eigene Menüspalte; Titel des Bereichs in der rechten Karte, Einstellungen ohne Seitentitel | 152–252 px |
| K6 Zurück-Link + Karte (5) | Konto, Benutzer, Änderungshistorie, Adressimport, Leistungskatalog | „← Ziel“, darunter eine Karte mit h2; kein Seitentitel (Konto: „Passwort ändern“) | 178–330 px |
| K7 Formularseite ohne Rahmen (4) | Neues Projekt, Neues Angebot, Mitarbeiter bearbeiten, Leistung bearbeiten | ohne Seitenleiste und Kopfzeile: „← Ziel“, zentrierte Karte, h1 32 px | 166–187 px |
| K8 Werkzeugleiste (2) | Kalender, Plantafel | Titel 20 px in einer Leiste mit 7 bzw. 8 Bedienelementen | 136–199 px |
| K9 ohne Seitentitel (1) | Anfragen | zuerst Kennzahlen, dann die Karte „Neue Anfrage“ (h2) | Kennzahlen direkt unter der Kopfzeile |
| K10 Monteursansicht (5) | Mobil, Objekt (mobil), Stundenzettel, Zeiterfassung (Monteurin), Betriebsmittel (Monteurin) | Monteurskopf, darunter nur Abschnittsüberschriften (h1/h2 15 px, Großbuchstaben) oder eine Karte; Objekt mit „← Einsätze“ | nach dem Monteurskopf (173–188 px) |
| K11 eigenständig (2) | Anmeldung, Sperrseite | zentrierte Karte | -- |

Bilder je Muster: `…__1440__pruefvorlagen.png` (K1), `…__finanzen.png` (K2), `…__wartungsvertrag.png` (K3, 6 Aktionen),
`…__projektmappe.png` und `…__auftrag.png` (K4), `…__stammdaten.png` (K5), `…__verlauf.png` (K6), `…__projekt_neu.png` (K7),
`…__plantafel.png` (K8), `monteur__hell__800__mobil.png` (K10).

### Die sechs Bestandteile

| Bestandteil | Seiten | Befund |
|---|---|---|
| **Titel** | 39 mit h1 | Größe 22 px (20 Seiten), 20–21 px (6), 32 px Browser-Vorgabe (11), 15 px als Abschnitt (2); 14 Seiten ohne h1 -- h2 als Titel (6), fettes `div` im Belegkopf (4), keiner (4). Titel und Name in der Leiste weichen ab: Befunde/„Mängel“, Wartungen/„Wartungen & Reparaturen“, Betriebskosten/„Betriebskosten-Übersicht“, Backoffice/„Zeiterfassungs-Backoffice“, Benutzer und Zugriff/„ERP-Benutzer“, Konto/„Passwort ändern“ |
| **Kennung** | 8 | an vier Orten: eigene Zeile über dem Titel (Projektmappe), „Kennung · Titel“ (Angebot, Auftrag, Arbeitsvorbereitung), in der Unterzeile (Einsatzbericht, Checkliste), im Titel (Checklisten je Auftrag); die Rechnung trägt im Entwurf keine Nummer, der Titel lautet „Entwurf · Abschlagsrechnung (Pauschal)“ |
| **Status** | 8 | Projektmappe, Angebot, Auftrag, Rechnung, Arbeitsvorbereitung, Checklisten-Vorlage, Checkliste, Betriebsmittel; an drei Orten (unter dem Titel, rechts neben den Knöpfen, zwischen Titel und Beträgen); 24 Seiten definieren eine eigene `.badge`, 15 eine eigene `.pill` |
| **Aktionen** | rund 26 mit Knöpfen im Kopf | eine gefüllte Hauptaktion auf rund 15 Seiten; bis zu 6 Aktionen nebeneinander (Wartungsvertrag), 8 Bedienelemente in der Plantafel; „Löschen“ direkt im Kopf auf 4 Seiten (Checklisten-Vorlage, Wartungsvertrag, Dachfläche, Betriebsmittel); ein Menü „⋮“ nur in der Projektmappe |
| **Zurück-Link** | 12 + 4 | `.back` auf 12 Seiten mit acht Wortlauten („← zurück“, „← Zur Startseite“, „← Einstellungen“, „← Projekte“, „← Stammdaten: Mitarbeiter“, „← Leistungskatalog“, „← Stammdaten: Leistungskataloge“, „← Einsätze“); dazu „← Auftrag“/„← Projektmappe“ als Knopf in der Knopfreihe (Einsatzbericht, Rechnung, Arbeitsvorbereitung, Auftrag) |
| **Pfad** | 10 | Angebot, Auftrag, Rechnung, Einsatzbericht, Objekt, Dachfläche, Betriebsmittel, Wartungsvertrag, Checklisten-Vorlage, Prüfvorlage; Trenner „·“ (8) oder „/“ (2); der Auftrag hat Pfad **und** „← Projektmappe“ |

### Was jede Seite selbst baut

**Alles.** Gemeinsam sind nur Seitenleiste, Kopfzeile (Suche, Kontoknopf) und Monteurskopf. Titel, Untertitel, Pfad, Kennung, Status, Aktionen
und Zurück-Link baut jede Seite selbst -- in `app/templates/` gibt es kein Makro und keinen Baustein für den Kopf. Die Kopf-Klassen sind je
Seite eigens definiert: `.hero` in 19 Seiten, `.toolbar` in 13, `.breadcrumb` in 10, `.back` in 12, `.section-title` in 10, `.badge` in 24,
`.pill` in 15. Bei Angebot, Auftrag, Rechnung, Arbeitsvorbereitung, Einsatzbericht und den Datensatz-Seiten mit Pfad füllt das Skript der
Seite Kennung, Titel, Status und Pfad erst nach dem Laden (die Daten kommen per `lesen()`); die 10 Pfade sind 10 Umsetzungen (8 ganz im
Skript, 2 mit festem erstem Glied im Markup: Checklisten-Vorlage, Prüfvorlage). Dazu trägt jede
der 53 Seiten ihren eigenen `:root`-Block mit denselben Farben (357–1618 Bytes, zusammen 58 kB; Werte überall gleich, Abschnitt 4).

## 3. Monteurskopf

### Seiten

`_mobile_header.html` binden 7 Vorlagen ein: Mobil, Objekt (`mobil_objekt`), Stundenzettel (`field_timesheet`), Zeiterfassung der Monteurin
(`time_tracking_field`), Betriebsmittel der Monteurin (`operational_asset_field`) und -- für die Monteurin -- Checkliste und Checklisten je
Auftrag. Aufbau: Zeile mit „DACHKONZEPTE · Mobil“, Name, „Mein Konto“, Hell/Dunkel; Objektsuche; vier Reiter (Einsätze, Zeiterfassung,
Stundenzettel, Abmelden). Alles in einem `sticky`-Block -- er bleibt beim Scrollen stehen.

### Höhe

| Fenster | Kopf gesamt | davon Zeile / Suche / Reiter | Anteil am Fenster | bleibt für den Inhalt |
|---|---|---|---|---|
| 1280 × 620 (TerraPad quer) | 173 px (188 auf 3 Seiten) | 51 / 61 / 61 | **27,9 %** (30,3 %) | 447 px (432) |
| 800 × 1100 (TerraPad hoch) | 173 px (188) | 51 / 61 / 61 | 15,7 % (17,1 %) | 927 px (912) |
| 412 × 900 (Telefon) | 173 px (188) | 51 / 61 / 61 | 19,2 % (20,9 %) | 727 px (712) |

**188 statt 173 px auf drei Seiten** (Zeiterfassung der Monteurin, Objekt, Stundenzettel): diese Seiten setzen eine Regel für jeden `button`
(`button{… min-height:44px}`), die auch den Hell/Dunkel-Knopf im gemeinsamen Kopf trifft -- er wird 44 statt 30 px hoch, die Zeile 65 statt
51 px. Seiten-CSS greift in den gemeinsamen Rahmen durch. Der Inhalt steht bei 1280 px in einer Spalte von 640–760 px in der Mitte.
Bild: `monteur__hell__1280__zeiterfassung_monteur.png`.

### Einsatzbericht und Konto mit dem Büro-Rahmen

Gemessen als Monteurin (Bild `monteur__hell__1280__einsatzbericht.png` gegen `monteur__hell__1280__mobil.png`):

- **1280 × 620**: Seitenleiste 240 px sichtbar (Start, Zeiterfassung, kein aktiver Eintrag, Hell/Dunkel unten), Kopfzeile 63 px mit nur dem
  Kontoknopf (die Suche gibt es für die Monteurin nicht), Inhalt ab x = 240. **800 × 1100 und 412**: Leiste ausgeklappt nur über den
  Menüknopf, Kopfzeile 59 px.
- **Was dort fehlt**: die Reiter Einsätze/Zeiterfassung/Stundenzettel, die Objektsuche, „Abmelden“ mit einem Tipp (nur über das Kontomenü,
  zwei Tipps) -- und **der Name**: der Monteurskopf zeigt ihn immer, weil „ein Bericht, der versehentlich unter fremdem Namen unterschrieben
  wird, das Schlimmste ist, was hier passieren kann“ (Kopfkommentar von `_mobile_header.html`). Ausgerechnet auf dem Einsatzbericht, wo
  unterschrieben wird, stehen nur die Initialen im Kontoknopf.
- **Was daran hängt** (bei einem Wechsel anzufassen):
  - Code: `service_reports.html` und `account.html` sind je eine Vorlage für Büro und Monteurin; die Berichtsseite bekommt vom Server
    `darfBueroSeiten` für ihre Links (Pfad, Folgeauftrag, Kunde).
  - Festlegung 1.8.113 Nr. 6: „die Kontoseite zeigt dem Monteur die Seitenleiste, „Start“ führt ihn nach /mobil zurück“.
  - Tests: `tests/test_v431_bildgrundlage.py::test_monteurin_hat_den_rahmen_auf_einsatzbericht_und_konto` (verlangt genau diese zwei);
    die Bildgrundlage nimmt die Zustände der Monteurin auf dem Einsatzbericht auf (`ZUSTANDSSEITEN`: Menü aufgeklappt 412/800,
    Leiste eingeklappt 1280/1440, Kontomenü offen 1440 -- je hell und dunkel); `scripts/klicktest_monteur_navigation.py` prüft Seitenleiste,
    Kopfzeile und Kontomenü der Monteurin samt `/account`.
  - Bis zu 12 weitere Klicktests öffnen Einsatzbericht oder Konto und kennen eine Monteurin (u. a. `klicktest_monteur_dachflaechen`,
    `klicktest_zeichenflaeche`, `klicktest_abschliessen`, `klicktest_vertrag_unterschrift`); sie prüfen den Inhalt, nicht den Rahmen --
    mit dem Monteurskopf stünde der Inhalt 110 px tiefer (173 statt 63 px Kopf) und hätte bei 1280 px die 240 px der Leiste dazu.

## 4. Ein Rahmen mit den --ds-*-Werten

### Was die Seiten heute haben

- **Farben**: alle 53 Seiten definieren dieselben Werte -- hell `--bg #f4f6f5`, `--card #fff`, `--ink #182420`, `--muted #5c6f68`,
  `--line #dde5e1`, `--field-border #b9c4bd`, Statusfarben `--danger`/`--warning`/`--success`; dunkel `#121816`/`#1a2220`/`#e7ece8`.
  `--accent` kommt aus den Einstellungen (Vorgabe `#0d9488`). Die Seitenleiste ist **hell** (`--sidebar-bg #fbfdfc`, aktiver Eintrag in der
  Akzentfarbe), dunkel `#0e1513`. Feste Farben außerhalb der `:root`-Blöcke: 85, davon 50 × `#fff` (Text auf der Akzentfarbe).
- **Schrift**: `Inter, ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif` auf `:root` -- Inter ist nirgends eingebunden, es
  zeichnet die Systemschrift (Windows: Segoe UI). Auf **28 Seiten** steht mindestens ein Steuerelement in **Arial** (Browser-Vorgabe für
  `button`/`select` ohne `font:inherit`).
- **Ecken**: eckig (CLAUDE.md, Design-System seit 1.0.97); rund nur 4 Stellen in Seiten (Kreise, eine Pille) und der Kontoknopf.
- **Größen**: Titel 15–32 px (meist 22), Tabellen 12,5–13,5 px, Beschriftungen 11–13 px, Abstände je Seite frei gewählt
  (z. B. `main{padding:20px}`).

### Probe

Im Browser dieses Laufs (nicht im Code) die alten Variablen auf die ds-Werte gelegt und die Schrift getauscht, je Seite hell und dunkel, 1440
und 412 px; gemessen vorher und nachher: Kontrast jeder sichtbaren Textstelle gegen ihren tatsächlichen Hintergrund (WCAG 2; 4,5 : 1, große
Schrift 3 : 1), waagrechter Bildlauf, abgeschnittene Texte, Höhe der Seite, gezeichnete Schriften. Zuordnung:

`--bg`→`grund`, `--card`→`flaeche`, `--ink`→`text`, `--muted`→`text-3`, `--line`→`linie`, `--soft`→`flaeche-2`, `--field-border`→`feld-rand`,
`--danger`→`fehler`, `--danger-soft`→`fehler-hell`, `--success`→`ok`, `--success-soft`→`ok-hell`, `--warning`→`signal`,
`--warning-soft`→`warn-hell`, `--sidebar-*`→`navi-*`; Text `--ds-schrift-text`, h1–h3 `--ds-schrift-titel`. **`--accent` blieb** (Regel 37:
die Akzentfarbe aus den Einstellungen bleibt). Größen, Abstände und Ecken nicht angewandt.

| | hell vorher → nachher | dunkel vorher → nachher |
|---|---|---|
| Textstellen unter der Grenze (53 Seiten, 9.931 geprüft) | 612 → 584 | 578 → **598** |
| Seiten mit mindestens einer | 52 → 52 | 52 → 53 |
| waagrechter Bildlauf (1440 / 412) | 0 → 0 | 0 → 0 |
| abgeschnittene Texte (412) | 6 → 6 | 6 → 6 |
| Höhe aller Seiten (1440) | −0,9 % | −0,9 % |

Die meisten Fehlstellen gibt es **schon heute** und bleiben, weil `--accent` bleibt:

- **Weiß auf der Akzentfarbe `#0d9488` hat 3,74 : 1** -- jeder gefüllte Hauptknopf („+ Aufgabe“, „Speichern“, „+ Projekt“ …) und der
  Kontoknopf (42 Seiten) liegen unter 4,5. Mit `--ds-aktion` (`#367337`) wären es 5,73.
- **Changelog**: 383 Versionsnummern (Akzent auf hellem Grund, 3,42 hell / 3,89 dunkel) -- eine Seite.
- Links in der Akzentfarbe auf dem Grund (34 Stellen hell, 3,28).

### Was sofort sichtbar wäre

- **Seitenleiste dunkel in beiden Modi** (`--ds-navi-grund #1F2529` statt `#fbfdfc`) -- der größte Unterschied im hellen Modus; die 21
  Fehlstellen der hellen Leiste (blasse Beschriftungen) verschwinden.
- **Schrift**: IBM Plex Sans für Text, Archivo für Titel statt Segoe UI. Die Seiten werden 0,9 % kürzer, nirgends entsteht ein waagrechter
  Bildlauf oder ein abgeschnittener Text. Die Steuerelemente auf 28 Seiten bleiben in Arial -- daneben fällt der Bruch stärker auf als heute.
- **Farben hell**: Grund kühles Grau `#EEF0F1` statt Grüngrau `#f4f6f5`, Linien `#DADEE1`, Nebentext `#5A646C`; **Feldränder deutlich
  dunkler** (`#88929A`, 3,17 : 1 statt `#b9c4bd`, rund 1,8 : 1). Dunkel ändert sich wenig (`#121619`/`#1A2024`/`#E9EDEF` statt
  `#121816`/`#1a2220`/`#e7ece8`), nur der grüne Stich fällt weg.
- **Würden Größen und Ecken mit angewandt** (nicht geprobt): Seitentitel 38 px statt 22 px (jeder Kopf rund 20 px höher), Fließtext 15 px
  und Tabellen 14 px statt 12,5–13,5 px (breitere Tabellen, im LV möglicher Bildlauf), Klickfläche 44 px, Ecken 10 px (Felder, Knöpfe) und
  12 px (Karten) -- das widerspricht „eckige Ecken durchgängig“ des bisherigen Design-Systems.

### Wo es bricht

1. **Statusfarben sind heute Textfarben, im ds Flächenfarben.** `--danger` steht 127-mal als Textfarbe, 5-mal als Fläche, 17-mal als Rand;
   `--warning` 52 × Text, 23 × Rand; `--success` 27 × Text, 6 × Rand. Auf `fehler`/`signal`/`ok` gelegt, entstehen **im Dunkelmodus 20 neue
   Fehlstellen** („Löschen“-Knöpfe 3,04, Status „Entwurf“ 2,96, „Noch offen“ 2,82, „Abmelden“ im Monteurskopf 2,80, Verlauf 2,49). Auf
   `fehler-text`/`warn-text`/`ok-text` gelegt, stimmen die Texte, aber die rund 50 Flächen und Ränder bekämen die Textfarbe (dunkel: helles
   Rosa unter weißer Schrift). Jede der rund 200 Stellen braucht ihre Zuordnung.
2. **Die Akzentfarbe**: das ds kennt Firmengrün als Hauptaktion (`--ds-aktion`), Regel 37 lässt `--accent` aus den Einstellungen unberührt,
   und der Admin kann sie frei wählen. Bleibt `--accent`, bleibt Weiß darauf mit der Vorgabe unter 4,5 -- und mit einer hellen Wahl noch
   darunter. Zu entscheiden: Hauptaktion = `--ds-aktion`, und wofür bleibt die Akzentfarbe.
3. **Grundschrift und Steuerelemente haben im ds keinen Ort.** Regel 37 verbietet in `ds.css` Element-Selektoren (`body`, `button`, `h1`) --
   heute setzt jede der 53 Seiten ihre Schrift auf `:root`. Ein Rahmen braucht einen Ort für die Grundregeln (Schrift, `font:inherit` für
   Steuerelemente) oder eine Ausnahme in Regel 37.
4. **Seiten-CSS greift in den Rahmen.** Gemessen am Monteurskopf (Abschnitt 3): `button{min-height:44px}` einer Seite verändert den
   gemeinsamen Kopf. Ein neuer Rahmen muss seine Maße auf eigenen `.ds-`-Klassen setzen (auch `min-height`, `font`, `background`) und gegen
   Element-Regeln der 53 Seiten bestehen.
5. **53 Kopien der Farben.** Ein Wechsel der Werte heißt 53 Stellen, oder zuerst eine gemeinsame Quelle -- die es heute nicht gibt
   (`ds.css` darf nur `--ds-*` setzen).
6. **Dunkelmodus ohne ds-Rahmen schon gut**, mit ds-Flächen ohne Umbau der Statusfarben schlechter (Punkt 1) -- der Dunkelmodus ist der
   empfindlichere Teil; die Bildgrundlage nimmt jede Seite hell und dunkel auf.

## 5. Vorschlag: gemeinsamer Seitenkopf und Reihenfolge

### Baustein

Drei Teile, die zusammengehören:

1. **Makro** `app/templates/teile/seitenkopf.html` (Unterordner und Makros kennen die Strukturtests seit 1.8.123/1.8.124), aufgerufen mit
   `{% call(teil) seitenkopf(titel="…", untertitel="…") %} … {% endcall %}`. Das Makro gibt die feste Gliederung aus:
   `<header class="ds-kopf">` mit Pfad (`nav`), Kennung, **einem h1**, Status, Hauptaktion und Menü „⋮“. Was die Scanner prüfen --
   `href` der Pfad-Links, Knöpfe mit `data-klick` (Regel 32), `type=` -- schreibt die Seite **wörtlich** in den Aufruf
   (`{% if teil == 'pfad' %}<a href="/projects">Projekte</a>{% elif teil == 'aktion' %}<button type="button" data-klick="…">…</button>{% elif teil == 'menue' %}…{% endif %}`);
   so bleibt die Makro-Regel (kein Jinja in `href`/`type`/`on…` im Makro) eingehalten. Feste IDs (eine Kopf je Seite): `seitenkopfPfad`,
   `seitenkopfKennung`, `seitenkopfTitel`, `seitenkopfStatus`.
2. **Skript-Baustein** `_seitenkopf.html`: `seitenkopf({kennung, titel, status:{text, art}, pfad:[{text, href}]})` für Köpfe, deren Daten
   erst nach dem Laden kommen (Belege, Datensätze): Text über `textContent`, Links über `sichererLink()` (Regel 32), Status-Art nur aus einer
   festen Liste (`neutral`, `info`, `ok`, `warn`, `fehler`, `signal`). Ersetzt die 10 eigenen Pfade und die vier Orte der Kennung.
   Das Menü „⋮“ öffnet und schließt hier einmal (Tastatur, Escape, Klick daneben) -- heute gibt es zwei Umsetzungen (Projektmappe,
   Kontomenü).
3. **Regeln in `ds.css`** nur auf `.ds-kopf…`-Klassen (Regel 37), mit eigenen Maßen gegen durchgreifende Element-Regeln der Seiten
   (Abschnitt 4, Punkt 4).

Regeln für den Inhalt: genau eine Hauptaktion (gefüllt, `--ds-aktion`), alles Weitere ins Menü „⋮“, „Löschen“ immer ins Menü; der Pfad
ersetzt den Zurück-Link (schmal: nur das letzte Glied als „← Eltern“); Status höchstens ein Kennzeichen neben dem Titel; Beträge und
Kennzahlen gehören unter den Kopf, nicht hinein. Dazu für die Seitenleiste: die Seite nennt ihren **Bereich** (`{% set bereich = "projekte" %}`),
die Leiste markiert danach statt nach der genauen Adresse -- das behebt die 21 Seiten ohne aktiven Eintrag; der erste Pfad-Link ist derselbe
Bereich.

### Reihenfolge

Jeder Schritt ändert sichtbar nur die Seiten, die er umzieht -- geprüft mit dem Bildvergleich gegen die Grundlage des Vorschritts (weicht
eine andere Seite ab, ist der Schritt nicht fertig), den Klicktests dieser Seiten und einem Strukturtest mit der Liste der umgezogenen Seiten,
die nur länger werden darf (umgezogen heißt: kein eigenes `.hero`/`.breadcrumb`/`.back`, h1 nur aus dem Makro). IDs der Knöpfe bleiben, weil
die Knöpfe in der Seite stehen (Klicktests und Seitenskripte greifen auf sie zu).

| Schritt | Inhalt | Seiten | Risiko |
|---|---|---|---|
| 0 | Entscheidungen (unten), neue Bildgrundlage als Basis | -- | -- |
| 1 | Baustein (Makro, Skript, `.ds-kopf`-Regeln), Strukturtest, node-Tests für `seitenkopf()` -- noch keine Seite | 0 | keins sichtbar |
| 2 | Pilot: Prüfvorlagen (K1, eine Hauptaktion, heute kein aktiver Eintrag -- zeigt auch `bereich`) | 1 | klein |
| 3 | übrige Titelzeilen und Titelkarten (K1, K2) -- Titel und Aktion stehen fest im Markup | 15 | klein |
| 4 | Datensätze mit Pfad (K3): Pfad und Status über `seitenkopf()` | 7 | mittel |
| 5 | Belege (K4), **einer je Schritt**: Projektmappe (hat schon Hauptaktion + ⋮), Kunde, Checkliste, Checklisten je Auftrag, Arbeitsvorbereitung, Rechnung, Auftrag, Angebot | 8 | hoch: viele Klicktests (Sperren, Endrechnung, Nachtrag …) |
| 6 | Untermenü-Seiten (K5) und Zurück-Link-Seiten (K6): Pfad statt „← …“ | 8 | mittel |
| 7 | Formularseiten (K7): mit oder ohne Rahmen (Entscheidung) | 4 | mittel |
| 8 | Sonderfälle: Kalender, Plantafel (Titel bleibt in der Werkzeugleiste), Anfragen (bekommt einen Titel) | 3 | klein |
| 9 | Seitenleiste und Kopfzeile auf ds-Werte (je eine Datei, wirkt auf alle 42 Seiten zugleich), `bereich` für alle | 42 | mittel: eine Datei, aber überall sichtbar |
| 10 | Farben der Seiten: erst die Zuordnung der rund 200 Statusstellen (Abschnitt 4, Punkt 1), dann eine gemeinsame Quelle statt 53 Kopien | 53 | hoch im Dunkelmodus |
| 11 | Monteursansicht für sich: Monteurskopf neu (Höhe, Name), Einsatzbericht und Konto der Monteurin in den Monteursrahmen (Tests aus Abschnitt 3) | 7 + 2 | mittel |

Schritt 9 kann auch vor Schritt 2 stehen -- er ist von den Köpfen unabhängig; dann sieht der Rahmen zwischendurch neu und die Seiten alt aus,
aber nichts bricht.

### Zu entscheiden (vor Schritt 1)

1. **Hauptaktion in `--ds-aktion`** (Firmengrün) -- und wofür bleibt die Akzentfarbe aus den Einstellungen (Regel 37)?
2. **Ecken**: ds-Werte (10/12 px) oder weiter eckig?
3. **Seitentitel 38 px** (ds) oder kleiner -- jeder Kopf wird mit 38 px rund 20 px höher.
4. **Seitenleiste dunkel auch im hellen Modus** (ds) -- und vier Gruppen? Mit 17 Einträgen scrollt sie bei 800 px trotzdem; ohne Bildlauf
   bei 800 px nur mit niedrigeren Zeilen und ohne den unteren Bereich.
5. **Formularseiten** (Neues Projekt, Neues Angebot, Mitarbeiter, Leistung): Rahmen dazu oder weiter ohne?
6. **Einsatzbericht und Konto der Monteurin** in den Monteursrahmen -- dann entfallen Festlegung 1.8.113 Nr. 6 und die Zustände der
   Monteurin auf dem Einsatzbericht in der Bildgrundlage.
7. **Ort der Grundregeln** (Schrift, `font:inherit` der Steuerelemente): Ausnahme in Regel 37 oder eigene Datei.
