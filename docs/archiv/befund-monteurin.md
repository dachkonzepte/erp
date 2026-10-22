# Befund Stufe 4 „Monteurin“ (nur Befund, nichts am Programm geändert)

Vorgabe vom 22.10.2026 (Teil B, übernommen wie gegeben): „B. Befund Stufe 4, nichts am Programm ändern: 1. /mobil, Zeiterfassung der
Monteure, Stundenzettel: welche Daten und Aktionen je Abschnitt, aus welchen Endpunkten, was die Monteurin darf (auch Kolonne und
Abwesenheit). 2. Zeiterfassung: Zustände des Timers, Zeitarten (Liste, Herkunft, Farben), Zeitregeln, was bei vergessenem Stopp passiert.
3. Einsatzbericht: Abfolge und Daten von Prüfpunkten, Mängeln ohne Prüfpunkt, Material, Betriebsmittel, Fotos und Unterschrift;
Pflichtangaben und was vor dem Unterschreiben erfüllt sein muss. 4. „Heutige Einsätze“ und „Meine kommenden Termine“: Herkunft
(Plantafel, Kalender) und Abgrenzung. 5. Was auf dem TerraPad per Finger schwierig ist (Ziehen, Hover, Datumsfelder, Datei mit Kamera,
kleine Ziele). 6. Vorschlag: Was kann „Heute“ oben zeigen (Zeitstatus, heutiger Einsatz, nächster Schritt) mit vorhandenen Endpunkten, und
was fehlt dafür?“

**Stand**: Code auf `main` nach 1.9.30 (22.10.2026). Gelesen, nicht ausgeführt; Pixelmaße aus dem CSS gerechnet, nicht gemessen. Die
wichtigsten Aussagen sind am Code nachgeprüft (Panel der Prüfpunkte, Zeiten im PDF, Pause als Maximum, Termine ab heute, `/today` ohne
Rollenprüfung, Fingermaße bis 900 px). Was nur aus dem Code geschlossen ist, steht als „unsicher“ da. Pfade relativ zum Projekt; ohne
Ordner = `app/templates/`.

## Zusammenfassung

- **Die drei Seiten der Monteurin** (Einsätze, Zeiterfassung, Stundenzettel) sind aufgeschoben (Stufe 4) und tragen weder `.ds-seite`
  noch den Seitenkopf. Daten kommen über rund 30 Endpunkte, alle ab Rolle `field` offen (einer ganz ohne Rollenprüfung); die Eingrenzung auf die eigene Person sitzt in
  jedem Endpunkt (Mitarbeiter aus der Anmeldung, nie aus der Anfrage).
- **Zeiterfassung**: nur zwei Zustände (`running`, `booked`), kein Pausieren. Ein vergessener Timer läuft unbegrenzt weiter, niemand
  bekommt einen Hinweis, das Büro kann ihn nicht stoppen (nur Admin), nach einem Monatsabschluss ist die Monteurin blockiert.
- **Einsatzbericht**: Pflichten werden erst nach beiden Unterschriften geprüft; ein Rapportbericht mit gewählter Prüfvorlage hat
  unsichtbare Pflichtpunkte, die die Unterschrift sperren; das PDF zeigt die Zeiten aller Kolleginnen.
- **Heute / kommend**: beide aus der Plantafel (`PlanningSlot`), nicht aus dem Kalender; jeder heutige Einsatz steht in beiden Listen; je
  Zeitabschnitt eine Karte, ohne Filter nach Status.
- **Finger auf dem TerraPad**: kein Ziehen, kein Hover-Zwang. Hürden: der Einsatzbericht quer (1280 px) mit Büro-Maßen (31–34 px), ein
  Neuzeichnen nach jedem Speichern, das Fokus und Tastatur nimmt, kleine Kreuze (18 px), Kamera ohne Galerie, `--ds-klick-tablet` (64 px)
  ungenutzt.
- **„Heute“ oben** lässt sich aus vorhandenen Endpunkten bauen (laufende Zeit, heutige Einsätze, eigene Entwürfe, Mängel, Checklisten);
  es fehlen Startzeit und Datum der laufenden Zeit in der Anzeige, eine Warnung bei Zeit von gestern, Einsätze je Auftrag statt je
  Abschnitt und der Stand der Pflichten je Bericht.

---

## B1. Die drei Seiten: Daten, Aktionen, Endpunkte, Rechte

### Rahmen

- Seitenrouten: `/mobil` → `mobil.html` (`app/routers/pages.py:246-258`), `/mobil/stundenzettel` → `field_timesheet.html` (`:261-267`),
  `/time-tracking` → für `field` `time_tracking_field.html`, sonst `time_tracking.html` (`:345-358`, Weiche `:357`). Alle mit
  `require_min_role(ROLE_FIELD)` (`:162`) -- auch das Büro öffnet `/mobil` und den Stundenzettel.
- Kopf `_mobile_header.html`: Reiter Einsätze · Zeiterfassung · Stundenzettel (`:69-71`), Lupe = Objektsuche
  `GET /api/field-view/properties/search` (`:117`; `app/routers/field_view.py:235-253`), Kontomenü mit „Mein Konto“ und Abmelden
  (`_kontomenue.html:29, 69`).
- Rollen der APIs: fast alle `require_min_role(ROLE_FIELD)`; Ausnahme `GET /api/field-view/today` ganz ohne Rollenprüfung (bewusst in
  `ROLE_AUDIT_EXEMPT`, `app/permissions.py:208-211`).

### /mobil „Einsätze“ (`mobil.html:67-81`)

| Abschnitt | Daten | Aktionen | Endpunkt |
|---|---|---|---|
| Heutige Einsätze (`:107-123`) | Objekt (sonst Kunde), Adresse, „Auftrag <Nr> · Zeitraum“, Plakette „N Bericht(e)“/„Kein Bericht“; roter Hinweis „Offene Bedenken“ (`:99-106`); Link „Checklisten zu diesem Auftrag →“ (`:121`, Modul Checklisten) | Karte → Einsatzbericht `/orders/{id}/service-reports` | `GET /api/field-view/today` (`field_view.py:103-129`): ohne Anmeldung 401, nach Feierabend 401 `feierabend`, ohne Mitarbeiter 422 `KEIN_MITARBEITER` |
| Offene Berichte (`:124-134`) | eigene Berichte im Entwurf (`app/service_reports.py:265-276`), nur mit Modul Wartungen (`field_view.py:124`) | Karte → Einsatzbericht | dieselbe Antwort, `draft_reports` |
| Mängel zur Beseitigung (`:199-269`) | freigegebene, offene Mängel der zugänglichen Aufträge, ohne Datumsfilter (`app/defects.py:1055-1071`), Fotos (`field_defects.py:59`) | „Beseitigt melden“: Datum (höchstens heute), mindestens ein Foto, Hinweis bis 500 Zeichen, über `abschliessen()` | `GET /api/field-view/defects` (`app/routers/field_defects.py:54-56`), `POST /api/field-view/defects/{id}/remedied` (`:72`) |
| Offene Checklisten (`:308-322`, Modul) | eigene Entwürfe ohne Kontext „Betrieb“ und ohne Zwecke „nur Büro“ | Karte → `/checklisten/{id}` | `GET /api/checklists/mine` (`app/routers/checklists.py:243-257`) |
| Meine kommenden Termine (`:135-148`) | wie heute, 30 Tage voraus; Karten **nicht anklickbar** (`<div>`, `:141`) | – | `GET /api/field-view/upcoming` (`field_view.py:189-203`) |
| Wartungen an meinen Objekten (`:149-186`) | Verträge nach Objekt, Plakette „Fällig“ | „Wartung durchführen“ → neuer Auftrag mit Wartungsbericht, Sprung dorthin | `GET /api/field-view/maintenance-contracts` (`field_view.py:155-169`), `POST /api/maintenance-contracts/{id}/perform-maintenance` (`app/routers/maintenance_contracts.py:196-217`; Monteurin nur an zugeordneten Objekten, `app/maintenance_contracts.py:635-655`) |

### Zeiterfassung der Monteure (`time_tracking_field.html`)

Beim Laden (`:515-558`): `GET /api/auth/status` (ohne Mitarbeiter Warnung, Abbruch), `GET /api/time-tracking/settings`,
`GET /api/field-view/time-tracking/orders` (`field_view.py:172-186` → `app/planning.py:867-886`: ±14 Tage Planung plus Aufträge mit eigenem
Bericht, ohne abgeschlossene und stornierte), drei Optionsgruppen (Zeitarten, Tätigkeiten, Abwesenheitsarten).

| Abschnitt | Daten | Aktionen | Endpunkt |
|---|---|---|---|
| Laufende Zeiterfassung (`:92-101`) | laufende Uhr hh:mm:ss, Auftrag · Projekt · Zeitart -- **ohne Startdatum und Startuhrzeit** | „Zusätzliche Pause beim Stoppen (Min.)“, „■ Zeit stoppen“ | `GET /api/time-entries/active`, `POST /api/time-entries/{id}/stop` |
| Schnell starten (`:103-109`, nur ohne laufende Zeit) | Auftrag, Tätigkeit, Zeitart-Kacheln (Schlechtwetter-Vorschlag nach Monat) | **Tipp auf eine Kachel startet sofort** | `POST /api/time-entries/start` |
| Kolonne (`:111-127`, nur für Kolonnenführerinnen) | Team, Mitglieder (sie selbst fest), Auftrag, Zeitart, Tätigkeit; „Meine Kolonnenbuchungen“ 14 Tage | „▶ Kolonne starten“, „+ Nachtrag für Kolonne“, Ändern, Löschen | `GET /api/time-tracking/crews`, `GET /api/time-entry-groups/active`, `POST …/start`, `POST /api/time-entry-groups`, `GET …/mine`, `PUT`/`DELETE /api/time-entry-groups/{id}` |
| Heute (`:129-136`) | Produktiv, Fahrzeit, Gesamt -- nur gebuchte Zeiten von heute (die laufende zählt nicht) | – | aus der Liste darunter |
| Meine Buchungen (`:138-141`) | letzte 14 Tage, nur gebucht: Zeitart, Datum, Auftrag, „gebucht von …“, Notiz, Stunden -- ohne Von/Bis, ohne Pause | „+ Nachtragen“, „Ändern“, „×“ (nur mit „manuelle Buchungen erlaubt“ und offenem Zeitraum) | `GET /api/time-entries`, `POST`, `PUT`, `DELETE /api/time-entries/{id}` |
| Abwesenheit (`:143-146`) | eigene Anträge | „+ Antrag“: Kategorie (Urlaub, Krankheit, Fortbildung, Unbezahlt), Art, Von, Bis, Notiz; „Zurückziehen“ (nur offene) | `GET`/`POST /api/absence-requests`, `DELETE …/{id}` (`app/routers/absence_requests.py:33-74`) |

### Stundenzettel (`field_timesheet.html`)

- Monat (`type=month`, Vorgabe Berliner Monat, `:128`), „PDF herunterladen“ → `GET /api/field-view/timesheet.pdf?year=&month=`
  (`field_view.py:206-232`).
- Liste des Monats (`GET /api/time-entries?…&limit=2000`, `:91`), nur gebucht, nach Tag: Auftrag, Tätigkeit, Stunden, Tages- und
  Monatssumme -- **ohne Zeitart** (`:96-120`). Keine weiteren Aktionen.
- PDF (`app/field_timesheet_pdf.py:63-151`): DIN-5008-Kopf mit der Monteurin als Empfängerin, Personalnummer, Tabelle Datum · Auftrag ·
  Zeitart · Tätigkeit · Stunden -- **mit laufenden Buchungen (0,00 h)**, der Bildschirm ohne (`:68` gegen `field_timesheet.html:98`).

### Was die Monteurin darf

- **Eigene Zeit** buchen (Timer, Nachtrag nur mit `allow_manual_entries`), ändern und löschen (nicht laufend); eine fremde Person 403 --
  für andere bucht nur ein Admin (`app/permissions.py:103-107`). Auftrag: Server prüft nur den Zugriff (Zuweisung an der
  Arbeitsvorbereitung oder eigener Bericht, `app/orders.py:297-335`) -- **ohne Datumsfenster und Auftragsstatus**; die Oberfläche bietet
  weniger an (±14 Tage, ohne abgeschlossene).
- **Fremde Zeit**: nie lesen (`app/routers/time_tracking.py:303-314`); buchen nur als Kolonnenführerin über die Gruppe.
- **Kolonne**: starten und nachtragen nur als Kolonnenführerin eines aktiven Teams (`TeamEmployee.is_crew_leader`), mit
  „Gruppenbuchungen erlaubt“, sie selbst dabei, alle Gebuchten aktuelle Mitglieder (`app/time_tracking.py:399-424`), Auftrag ihr
  zugeordnet, kein Mitglied mit laufender Zeit (`:456-457`). Stoppen über ihr eigenes „Zeit stoppen“: als Initiatorin und Kolonnenführerin
  die ganze Gruppe, sonst nur sich (`app/routers/time_tracking.py:378-389`). Ändern und Löschen einer Gruppe nur als Initiatorin und
  Kolonnenführerin, nur abgeschlossene. Von den Kolleginnen sieht sie Name, Stunden, Status.
- **Abwesenheit**: alle vier Kategorien beantragen, auch Krankheit; Art freier Text (nicht gegen die Liste geprüft); jedes Datum;
  Überschneidung nur gegen eigene offene Anträge (`app/absence_requests.py:83-92`); **entscheiden nur Admin** (`require_admin`,
  `app/routers/absence_requests.py:55-61`); zurückziehen eigene offene.
- **Stundenzettel-PDF**: nur eigene Zeiten, jeder Monat.
- **Sperrdatum** (Monatsabschluss, `locked_until`): Anlegen, Starten, Stoppen, Ändern, Löschen mit Datum bis dahin 403 für jede Rolle außer
  Admin (`app/routers/time_tracking.py:94-103`); vorrücken darf das Büro, zurücknehmen nur Admin (`app/routers/time_backoffice.py:51-61`).
- **„LV-Position erforderlich“** (Backoffice-Schalter) macht die mobile Zeiterfassung unbenutzbar: die Maske hat kein LV-Feld (bekannt,
  `docs/archiv/rechtekonzept.md`).

---

## B2. Zeiterfassung: Timer, Zeitarten, Zeitregeln, vergessener Stopp

### Zustände des Timers

- Nur `running` und `booked` (`app/models.py:2800`), kein Pausieren, kein Abbrechen. Laufend: 0 h, kein Ende (`app/time_tracking.py:131`).
  Das Buchungsdatum ist immer das **Startdatum** (`:129`).
- Übergänge: Start (409, wenn schon eine läuft, `:118-119`) · Stopp (Pause und Rundung, `:138-156`, `app/routers/time_tracking.py:369-396`) ·
  Nachtrag (sofort gebucht) · Ändern und Löschen nur gebucht (`app/time_tracking.py:178-179, 208`).
- Die API nimmt beim Start `started_at` und beim Stopp `ended_at` an (`app/schemas.py:3161, 3164`) -- frei wählbar, auch rückdatiert oder in
  der Zukunft; die Oberfläche nutzt das nicht.
- Kolonne: ein Kopf `TimeEntryGroup` und je Person eine `TimeEntry` (`app/models.py:2813-2856`).

### Zeitarten

| Wert | Beschriftung (Optionsgruppe) | produktiv | Fahrzeit | Farbe Monteurin | Farbe Büro |
|---|---|---|---|---|---|
| `site` | Baustellenzeit (Standard) | ja | nein | – | – |
| `travel` | Fahrzeit | nein | ja | Randlinie `#3d6a8c` | Grund, Pill |
| `workshop` | Werkstattzeit | ja | nein | Randlinie `#7a5a34` | Grund |
| `other` | Sonstige Arbeitszeit | ja | nein | – (`--other-btn` unbenutzt) | Grund |
| `weather_winter` | Schlechtwetter Winter | nein | nein | – (Vorschlag mit ✓) | Pill in Fahrzeit-Farbe |
| `weather_summer` | Schlechtwetter Sommer | nein | nein | – (Vorschlag mit ✓) | Pill in Fahrzeit-Farbe |

- Herkunft: angeboten wird die Optionsgruppe `time_entry_types` (`app/option_settings.py:218-233`, Einstellungen → Zeit-Listen); die Bedeutung
  hängt an Code-Konstanten (`ENTRY_TYPES`, `NON_PRODUCTIVE_ENTRY_TYPES`, `app/time_tracking.py:18, 24`), die Schlechtwetter-Liste steht
  viermal im Code (`app/time_tracking.py:24`, `app/invoices.py:1015`, `app/service_period.py:26`, `app/productive_hours.py:58`).
- Der Server prüft die Zeitart nicht gegen die Liste (nur Länge 40, `app/schemas.py:3133`); eine neue Zeitart zählt als produktiv.
  `counts_as_productive` wird beim Schreiben eingefroren.
- Farben (`time_tracking_field.html:32, 49-52`): feste Hex-Werte ohne Dunkel-Variante; gewählte Kachel `--ds-aktion`, Vorschlag `--ds-ok`.
  Plantafel, beide Stundenzettel-PDFs und `/mobil` zeigen keine Zeitart-Farben; das Backoffice zeigt den Rohwert (`time_backoffice.html:103`),
  der Bildschirm-Stundenzettel gar keine Zeitart.
- Tätigkeit (`activity`, Optionsgruppe `time_entry_activities`, Standard „Allgemeine Baustellenarbeiten“) ist freier Text ohne Logik -- wird
  aber in der Rechnung aus Aufwand zum Positionstext, also für den Kunden sichtbar (`app/invoices.py:1042-1056`).

### Zeitregeln (`TimeTrackingSettings`, Einstellungen → „Zeitregeln und DATEV“, ab Büro – Auftrag)

- Schalter: manuelle Buchungen (nicht geprüft bei Ändern und Löschen), Gruppenbuchungen, LV-Position Pflicht, Tätigkeit Pflicht
  (`app/routers/time_tracking.py:63-73`).
- Rundung (0, 5, 10, 15, 30 Minuten; auf das nächste Vielfache, `app/time_backoffice.py:171-177`): beim Nachtrag und beim Einzel-Stopp,
  **nicht** beim Ändern, beim Gruppen-Nachtrag und beim Gruppen-Stopp. Ein kurzer Timer kann so auf **0,00 h** fallen; der Nachtrag lehnt 0
  ab.
- Automatische Pause je Arbeitszeitmodell (Vorgabe ab 6 h 30 min, ab 9 h 45 min, `app/work_time_models.py:84-88`) -- **nur beim Stopp eines
  Timers, je Timer, nicht je Tag**; Ergebnis `max(Eingabe, automatisch)` (`app/time_tracking.py:146-147`), obwohl das Feld „Zusätzliche
  Pause“ heißt. Beim Nachtrag wird die Standardpause nur gespeichert, nicht abgezogen (`:96-100`): Von/Bis 7–16 Uhr ergibt im Nachtrag 9 h,
  als Timer 8,25 h.
- Grenzen: Nachtrag und Ändern 0,01–24 h, Pause 0–720 min; **Timer ohne Obergrenze**; keine Prüfung auf Überschneidung, Zukunft oder
  Tagessumme; Von/Bis über Mitternacht in der Maske nicht möglich; ein Timer über Mitternacht zählt ganz zum Startdatum.
- Ein laufender Timer je Person nur in der Anwendung geprüft, ohne Datenbank-Bedingung (unsicher: zwei Geräte gleichzeitig).

### Vergessener Stopp

- **Nichts stoppt automatisch**, es gibt keine Höchstdauer, keinen Hinweis, keine Übersicht laufender Zeiten fürs Büro. Der Feierabend
  (19:00) beendet nur die Sitzung des Geräts, nicht die Zeit.
- Am nächsten Morgen: `/mobil` zeigt nichts zur Zeit. Im Reiter Zeiterfassung läuft die Uhr bei z. B. „25:14:03“, ohne Datum, ohne Warnung.
  Stoppen bucht z. B. 24,25 h **auf gestern**. Korrigieren: „Ändern“ öffnet 24,25 h, der Browser lehnt über 24 ab; der PUT ändert nur die
  Stunden, Beginn und Ende bleiben stehen -- Backoffice-Stundenzettel und CSV zeigen dann alte Uhrzeiten zu neuen Stunden. Ohne „manuelle
  Buchungen erlaubt“ gibt es kein „Ändern“ in der Oberfläche (der Server nähme es an).
- Ist der Tag inzwischen abgeschlossen: Stoppen 403, neu starten „läuft bereits“ -- **blockiert, bis ein Admin stoppt**. Das Büro kann nicht
  korrigieren (fremde Zeit nur Admin); ein Admin stoppt nur „jetzt“, ein Feld für das Ende gibt es nirgends (die API kann es).
- Kolonne: der vergessene Timer eines Mitglieds sperrt den Kolonnenstart.

---

## B3. Einsatzbericht (`service_reports.html`, im Monteursrahmen)

### Abfolge

1. Monteurskopf, Seitenkopf „Einsatzbericht“ (Kennung = Auftragsnummer, Untertitel = Kunde, Pfad „Einsätze“, Menü „Zeiterfassung
   (Auftrag)“); offene Bedenken als Hinweis; Karte „Objekt & Zugang“.
2. „Berichte zu diesem Auftrag“ mit „+ Bericht“; je Bericht Typ, Status, Datum, Ersteller, Beschreibung; im Entwurf „Bearbeiten“,
   „Unterschreiben“, „Löschen“; Umschalter **Prüfpunkte** · **Mängel ohne Prüfpunkt** · **Material** · **Betriebsmittel** (Modul).
3. „Frühere Berichte zu diesem Gebäude“, „Erfasste Zeiten zu diesem Auftrag“ mit Buchungsformular.

- **Anlegen** (`:376-397`, `POST /api/orders/{id}/service-reports`): Typ Rapport oder Wartung, Datum heute, Dachflächen, Vorlage (nur bei
  genau einer Fläche), Beschreibung. Prüfpunkte entstehen nur bei Wartung oder gewählter Vorlage (`app/service_reports.py:586`), je Bauteil
  kopiert. Mehrere Berichte je Auftrag ohne Grenze. „Wartung durchführen“ in `/mobil` legt Auftrag und Wartungsbericht über alle Flächen an.
- **Status**: nur `entwurf` und `unterschrieben`; löschen nur im Entwurf.

### Bereiche

- **Prüfpunkte**: Ja/Nein und Dichtheit (OK / Nicht OK / Entfällt, Dichtheit mit Minuten), Zustand 1–4, Messwert (mit Soll, nur markiert),
  Menge, Freitext, Foto („Fotoerfassung folgt“). „+ Bemerkung“ je Punkt (im Kunden-PDF). Pflicht mit `*`, Kopf „x von y beantwortet, n
  Pflichtpunkte offen“. Speichern je Punkt `PUT /api/inspection-items/{id}`. Bei „Nicht OK“ oder Zustand 3/4 ohne Mangel: „Mangel fehlt
  noch“ mit „+ Mangel“. Punkte ergänzen (nie Pflicht) und löschen (auch Pflichtpunkte) im Entwurf.
- **Mängel** (am Prüfpunkt oder ohne): Beschreibung (Pflicht), Schwere (gering bis akute Gefahr), Maßnahme -- sofort behoben (erledigt) /
  Büro prüfen lassen (sofort eine Aufgabe an den Sachbearbeiter) / zurückgestellt (Pflichtdatum Wiedervorlage). Fotos erst nach dem
  Anlegen. Nachverfolgung (Status, Maßnahme) auch nach der Unterschrift.
- **Material**: Katalogsuche ohne Preise oder freie Bezeichnung, Menge ab 0,001, Einheit, Fläche (ab zwei); im Entwurf änderbar. Kein
  Verschnitt, kein Preis.
- **Betriebsmittel** (Modul): aus der Liste freigegebener Geräte, mit Notiz; keine Stunden.
- **Fotos**: an Prüfpunkt oder Mangel, `capture="environment"` (nur Kamera), höchstens 15 MB, auf dem Server auf 1600 px verkleinert;
  Vorher/Nachher je eines; keine Anzahlgrenze.
- **Zeiten**: gehören zum Auftrag, nicht zum Bericht; die Monteurin bucht und sieht nur eigene.
- **Unterschrift** (`:460-531`): zwei Schritte auf einer Fläche -- Monteur (Name vorbelegt, änderbar), dann Kunde (Name frei), „Unterschrift
  bestätigen“ sendet beide (`POST …/sign`, über `abschliessen()`). Keine Auswahl Auftraggeber oder Beteiligter, keine Vollmacht.
- Speichern: Freitext und Bemerkung 600 ms nach der letzten Taste und beim Verlassen; Zahlen und Material beim Verlassen; die Beschreibung
  nur über „Bearbeiten“ → „Speichern“. `client_uuid` schickt die Oberfläche nie.

### Pflichten vor dem Unterschreiben (Server, in dieser Reihenfolge; `app/service_reports.py:1277-1307`)

1. Zuständigkeit (eigener Bericht) · 2. beide Bilder und Namen da · 3. noch nicht unterschrieben · 4. Bilder gültig, nicht leer (je höchstens
   2 MB, 5000 px) · 5. **alle Pflichtpunkte beantwortet** · 6. **jeder Punkt mit „Nicht OK“ oder Zustand 3/4 hat einen Mangel** · 7. **jeder
   Mangel hat ein Foto** (auch „sofort behoben“) · 8. **jeder zurückgestellte Mangel hat ein Wiedervorlagedatum** · 9. Namen von Monteur
   und Kunde.
- Nicht geprüft: Fotopflicht am Prüfpunkt (`photo_required` wird nur kopiert), Vorher/Nachher, Punkte vom Typ Foto, Sollbereich,
  Beschreibung, Zeiten, offene Bedenken.
- Im Browser vorher: Name, nicht leere Fläche, kein abgelehntes Zahlenfeld, kein laufendes oder gescheitertes Speichern (`abschliessen()`).
  **Keine Vorprüfung vor dem Öffnen** der Unterschrift: Fehler kommen erst nach beiden Unterschriften; „Abbrechen“ verwirft beide.
- Nach der Unterschrift gesperrt: Bericht, Prüfpunkte, Fotos, Material, Betriebsmittel, neue Mängel; das PDF gibt es erst jetzt. Folgen:
  Aufgabe „Rechnung erstellen“ an den Sachbearbeiter, Fälligkeit des Wartungsvertrags rückt vor, Material für die Rechnung aus Aufwand.

### Was die Monteurin darf

- Nur Berichte zu Aufträgen mit Zuweisung oder eigenem Bericht; bearbeiten nur selbst angelegte (sonst 403 „… von einer anderen Person
  angelegt“). Fremde Berichte nur reduziert. Keine Preise, Kundennummer, Notizen; keine Links auf Büro-Seiten.

---

## B4. „Heutige Einsätze“ und „Meine kommenden Termine“

- **Herkunft beider: nur die Plantafel** (`PlanningSlot`, `app/planning.py:663-716`), **nie der Kalender** (`CalendarEvent` hat keinen Bezug
  zu Team oder Mitarbeiter und ist für Monteure gesperrt, `app/models.py:4800-4806`).
- Zuordnung (`app/planning.py:607-628`): über das Team (Besetzung **eingefroren bei der ersten Zuweisung** an die Arbeitsvorbereitung,
  `:334-379` -- spätere Teamänderungen wirken nicht) oder über eine Einzelzuweisung an der Arbeitsvorbereitung (dann **jeder** Abschnitt
  dieser Arbeitsvorbereitung, auch der eines fremden Teams).
- **Heute**: Abschnitte mit Beginn ≤ heute ≤ Ende (Berliner Datum). **Kommend**: Ende ≥ heute und Beginn ≤ heute + 30 Tage
  (`:697-706`) -- **schließt heute ein**: jeder heutige Einsatz steht in beiden Listen (einmal anklickbar, einmal nicht, der
  Bedenken-Hinweis zweimal).
- Eine Karte **je Abschnitt, nicht je Auftrag**. Nicht gefiltert: Status des Abschnitts (auch pausiert, abgeschlossen), Status des Auftrags
  (auch storniert), eigene Abwesenheit, Feiertage, Wochenenden. Nicht übertragen: Notiz, Team, Status, Stunden des Abschnitts.
- Gar nicht sichtbar: Kalendertermine, Arbeitsvorbereitungen nur mit geplantem Zeitraum ohne Abschnitt, ungeplante Wartungsaufträge (die nur
  als „Offene Berichte“).
- Zum Vergleich: „Wartungen an meinen Objekten“ nimmt ±14 Tage um Abschnitt oder geplanten Zeitraum; „Mängel“ jeden zugänglichen Auftrag.
- „N Bericht(e)“ zählt die Berichte aller Kolleginnen (`app/service_reports.py:174-178`).

---

## B5. Per Finger auf dem TerraPad (800 × 1100 hoch, 1280 × 620 quer)

| Thema | Befund | Stelle | Schwere |
|---|---|---|---|
| Ziehen, Wischen | keins auf den Seiten der Monteurin; Unterschrift über Pointer Events (geht per Finger) | `_unterschrift.html:54-62` | – |
| Hover | nichts erscheint nur bei Hover; Erklärungen nur als `title` (Beschreibung der Vorlage beim Start einer Checkliste, nicht anklickbare Checkliste, warum ein Kreuz fehlt); Hover bleibt nach dem Tippen haften (rein optisch) | `_checklists_section.html:66, 83`; `checklist.html:459, 470` | mittel / gering |
| Datum, Zeit | überall native Felder (Android-Auswahl): `date`, `time` (nur Von/Bis), `datetime-local` (zwei Schritte), `month` ohne Vor/Zurück | `time_tracking_field.html:153, 160-161`; `checklist.html:452-454`; `field_timesheet.html:54` | gering |
| Zahlen | Text mit `inputmode="decimal"`; der Baustein verlangt das Komma -- bietet die Tastatur-App nur den Punkt, geht keine Kommazahl (**auf dem Gerät prüfen**) | `_zahl.html:16-19` | mittel (unsicher) |
| Kamera | `capture="environment"` öffnet direkt die Kamera: keine Galerie, ein Foto je Durchgang, im Einsatzbericht ohne Rückmeldung beim Hochladen; „Beseitigt melden“ ersetzt bei neuer Auswahl die vorige; nirgends Verkleinerung im Browser (Rohfotos übers Mobilnetz) | `checklist.html:460`; `service_reports.html:679-715`; `mobil.html:217` | mittel |
| Einsatzbericht quer | Fingermaße nur bis 900 px (`@media`); quer gelten Büro-Maße: OK/Nicht OK/Entfällt ~31 px, Zahlenfelder ~32 px, Berichtsknöpfe ~34 px („Löschen“ zwischen „Unterschreiben“ und „Prüfpunkte“) | `service_reports.html:85-101, 34, 55-56` | hoch |
| Neuzeichnen | nach jedem Speichern wird die ganze Berichtsliste neu gezeichnet -- das Feld verliert den Fokus, die Tastatur klappt zu, auch 600 ms nach der letzten Taste im Freitext | `service_reports.html:1274-1276, 1082, 1134-1136` | hoch |
| kleine Ziele | Kreuz am Foto 18 × 18 px über einem Link; „+ Mangel“ ~27 px; „+ Bemerkung“ ~25 px; Gruppenköpfe ~18 px; Dachflächen-Häkchen ~19 px; Pfad im Kopf ~22 px (auf der Checkliste der einzige Rückweg); Links „Offene Bedenken“ ~20 px; „Ändern“/„ד der Buchungen 36/27 px | `service_reports.html:67, 1176, 1185, 50, 339-341`; `ds.css:367-375`; `mobil.html:44-45`; `time_tracking_field.html:63-64` | hoch / mittel |
| Weiteres | Beschreibung ohne Zwischenspeichern, „Abbrechen“ verwirft ohne Rückfrage; Dialoge der Zeiterfassung höher als 620 px; Fehler als `alert()`; 9-px-Beschriftungen der Kennzahlen; Telefon im Bericht ohne `tel:` | `service_reports.html:161, 165`; `time_tracking_field.html:57, 149-221` | mittel / gering |
| Design-System | `.ds-tablet` (17 px Schrift) und `--ds-klick-tablet: 64px` sind vorgesehen, aber von keiner Seite genutzt; jede Seite setzt ihre Fingermaße selbst (44, 48, teils 36 und weniger) | `ds.css:125-126`; `ds-basis.css:32-34` | mittel |

---

## B6. Vorschlag: „Heute“ oben auf /mobil

**Ziel**: oben auf `/mobil` eine Karte „Heute“ mit drei Zeilen -- Zeitstatus, heutiger Einsatz, nächster Schritt -- mit einem Tipp zum
Handeln (48–64 px).

**Mit vorhandenen Endpunkten möglich** (alle schon für die Monteurin offen, über `lesen()` parallel):

| Zeile | Inhalt | Endpunkt |
|---|---|---|
| Zeitstatus | läuft seit … / keine Zeit läuft; Summe heute (gebucht); Knopf „Zeit stoppen“ bzw. „Zeit starten“ (zur Zeiterfassung) | `GET /api/time-entries/active`, `GET /api/time-entries?start_date=heute&end_date=heute` |
| Heutiger Einsatz | Objekt, Adresse, Auftrag, Zeitraum, Bedenken; Knopf „Einsatzbericht“ | `GET /api/field-view/today` (`assignments`) |
| Nächster Schritt | in dieser Reihenfolge: offene Bedenken → laufende Zeit von gestern → Bericht im Entwurf fortsetzen → offene Checkliste → Mangel zur Beseitigung → Zeit starten | `today` (`draft_reports`, `open_concerns`), `GET /api/field-view/defects`, `GET /api/checklists/mine`, `active` |

**Was dafür fehlt**:

1. **Laufende Zeit mit Beginn**: `active` liefert `started_at`, die Oberfläche zeigt es nirgends; für „läuft seit gestern 7:02“ und eine
   **Warnung bei einer Zeit von gestern** reicht die Anzeige -- ein Endpunkt fehlt nicht, eine Regel schon (ab wann warnen, was anbieten).
2. **Ein Ende eintragen**: wer die Zeit von gestern stoppt, bucht bis jetzt. Die API nimmt `ended_at` an, die Oberfläche hat kein Feld --
   ohne ein solches Feld kann „Heute“ nur warnen, nicht helfen.
3. **Einsatz je Auftrag**: `today` liefert je Abschnitt eine Zeile, ohne Status, Team und Notiz; für „der heutige Einsatz“ braucht es eine
   Zusammenfassung je Auftrag (und eine Reihenfolge, wenn es mehrere gibt) und den Ausschluss pausierter oder abgeschlossener Abschnitte.
4. **Stand je Bericht**: für „Bericht fortsetzen: 3 Pflichtpunkte offen, 1 Mangel ohne Foto“ müsste die Seite je Entwurf die Prüfpunkte und
   Mängel laden (mehrere Anfragen); besser liefert `today` je Entwurf die Zahlen, die auch die Unterschrift prüft.
5. **Zeitstatus ohne den Reiter**: `today` kennt die laufende Zeit nicht; entweder ein zweiter Aufruf (`active`) oder `today` liefert sie mit.
6. **Abwesenheit und Feierabend**: eine genehmigte Abwesenheit heute (`EmployeeAbsence`) liest die Monteurin nirgends; „Heute“ könnte
   „Urlaub“ zeigen statt Einsätzen -- dafür fehlt ein Endpunkt. Die Feierabend-Uhrzeit liefert `GET /api/mobile-settings`.
7. **Doppelung**: „Meine kommenden Termine“ sollte ab morgen zählen, sonst steht der heutige Einsatz dreimal (Heute, Heutige Einsätze,
   kommend).

**Empfehlung**: „Heute“ zuerst nur aus `active`, `today`, `defects` und `mine` bauen (keine Änderung am Server), mit Beginn der laufenden
Zeit und Warnung bei Datum vor heute; in einem zweiten Schritt `today` um Zeitstatus, Einsatz je Auftrag und Stand je Entwurf erweitern
(ein Aufruf statt vier) und „kommend“ ab morgen.

---

## Auffälligkeiten (nur benannt, nichts geändert)

**Einsatzbericht**
1. Rapportbericht mit gewählter Prüfvorlage: Prüfpunkte entstehen (`app/service_reports.py:586`), das Panel bleibt verborgen
   (`hasInspectionSection` fragt die Altspalte `inspection_template_id`, die neue Berichte nicht mehr schreiben, `service_reports.html:535-537`;
   `app/service_reports.py:560-565`) -- unsichtbare Pflichtpunkte sperren die Unterschrift. Ebenso nach einem Wechsel Wartung → Rapport.
2. Pflichtpunkte lassen sich löschen (`service_reports.html:1192`) -- die Pflicht ist umgehbar.
3. Fotopflicht am Prüfpunkt (`photo_required`) nur kopiert, nie geprüft; Typ „Foto“ gilt immer als beantwortet.
4. Prüfpunkt löschen oder neu erzeugen, wenn Foto, Mangel oder Material daran hängt: Fremdschlüssel ohne `ondelete`, nur `ValueError`
   abgefangen -- unter PostgreSQL vermutlich 500 (unsicher, nicht ausgeführt).
5. Kundenunterschrift ist Pflicht, ohne Ausweg (niemand vor Ort); keine Auswahl Beteiligter/Vollmacht wie bei der Checkliste.
6. Keine Vorprüfung vor der Unterschrift; „Abbrechen“ verwirft beide Unterschriften.
7. Unterschriebene Berichte: Kacheln und Felder der Prüfpunkte bleiben bedienbar, ein Tipp ergibt eine `alert`-Meldung (400).
8. Fremde Berichte: leeres Statusabzeichen, „PDF öffnen“ ergibt 403, Panels leer.
9. Das PDF eines eigenen Berichts enthält die Zeitbuchungen aller Kolleginnen am Auftrag (`app/service_report_pdf.py:349`) sowie
   Kundenanschrift und -nummer; es wird bei jedem Abruf neu erzeugt (keine feste Fassung).
10. Zahlen roh angezeigt (Materialmenge „2.500“, Sollbereich, im PDF Punkt statt Komma, Materialmenge mit 2 statt 3 Stellen).
11. Wiedervorlage in der Nachverfolgung wird ohne Statuswechsel nicht gespeichert.
12. „Durchgeführt von“ ist für alle außer Admin wirkungslos bzw. 403.
13. Das Büro (ohne Admin) kann im Bericht einer Monteurin keinen Mangel anlegen (403); ein vom Büro angelegter Bericht ist für die Monteurin
    nicht bearbeitbar.
14. Statusabzeichen mit Rohwert („entwurf“) statt `statusKennzeichen()`; Fehlermeldungen per `alert()`; jeder Seitenaufruf schreibt
    (`POST …/sync` je Entwurf).

**Zeiterfassung**
15. Vergessener Timer: kein Stopp, keine Warnung, Büro machtlos, nach Abschluss blockiert (B2).
16. „Zusätzliche Pause“ wirkt als Mindestwert; Pausen je Timer statt je Tag; Nachtrag ohne Pausenabzug.
17. Rundung uneinheitlich, ein kurzer Timer kann 0,00 h buchen.
18. Zeitart nicht gegen die Liste geprüft, Bedeutung fest im Code (viermal); Farben fest ohne Dunkel; Backoffice zeigt den Rohwert.
19. Die Kolonnen-Karte erscheint auch bei ausgeschalteten Gruppen- bzw. manuellen Buchungen (Server 403); eine Gruppe kann auf „läuft“
    hängen bleiben, wenn alle einzeln stoppen (unsicher).
20. „Heute“ zählt die laufende Zeit nicht; laufende Buchungen erscheinen im Stundenzettel-PDF (0,00 h), nicht auf dem Bildschirm.
21. Per API: Buchungen auf abgeschlossene oder stornierte Aufträge, rückdatierte oder künftige Zeiten.
22. Abwesenheit: Krankheit braucht die Freigabe eines Admins, Art unabhängig von der Kategorie, Text „Urlaub oder Krankheit beantragen“
    bei vier Kategorien.
23. Zeit über die Zeitumstellung (25.10.2026) rechnet mit naiver Ortszeit -- ±1 h (unsicher, nicht ausgeführt).

**/mobil und Rahmen**
24. Feierabend trifft jede Rolle: öffnet das Büro `/mobil` nach 19:00, ist seine Sitzung beendet (`/today` ohne Rollenprüfung).
25. Anmeldeschleife nach Feierabend auf `/mobil`, `/time-tracking` bleibt nutzbar.
26. Überschriften „Wartungen an meinen Objekten“ und „Offene Berichte“ auch ohne Modul Wartungen.
27. Stundenzettel-PDF: `&` vermutlich als „&amp;“ (`app/field_timesheet_pdf.py:119, 121`, unsicher); `month=0` ergibt still den
    laufenden Monat.
28. Veraltete Kommentare (`time_tracking_field.html:17-21` „Gruppenbuchung bewusst nicht“, `app/mobile_settings.py:32-35` und
    `app/models.py:3465-3466` „geprüft an GET /mobil“, `app/routers/field_view.py:107-109`).

## Quellen dieses Befunds

Vier Durchsichten des Codes (Seiten und Endpunkte; Zeiterfassung; Einsatzbericht; Finger-Bedienung) mit Datei und Zeile je Aussage; die
Rohfassungen sind hier verdichtet. Nachgeprüft am Code: `hasInspectionSection` und `create_report` (Auffälligkeit 1), Zeiten im PDF (9),
Pause als Maximum (16), Termine ab heute (B4), `/today` ohne Rollenprüfung (24), Fingermaße bis 900 px (B5).
