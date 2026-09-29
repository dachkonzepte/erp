# Checklisten und Formulare für Monteure (Modul `checklisten`)

Vorhaben in vier Stufen, begonnen am 29.09.2026. Diese Datei ist die verbindliche Grundlage für
den Bau -- eine neue Sitzung (auch nach `/clear` zwischen zwei Versionen) liest ZUERST diese Datei
(Regel 14), dann den Abschnitt "Etappenplan" unten, um zu sehen, welche Version als nächste dran
ist, und prüft den tatsächlichen Stand gegen `VERSION`/`CHANGELOG.md`/`git log`.

- **Stufe 1** (dieses Dokument, Versionen 1.8.0–1.8.5; ursprünglich bis 1.8.4 geplant, "repariert"
  kam als 1.8.2 dazu): allgemeiner Checklisten-Baukasten. Büro legt
  Vorlagen an, Monteur füllt sie aus -- am Auftrag, am Objekt, am Betriebsmittel (QR-Code) oder
  (Betreiberentscheidung D) im Kontext "Betrieb". Abgeschlossen = unveränderlich, PDF über den
  gemeinsamen Rahmen.
- **Stufe 2** (später): Regiebericht, Abnahme, Behinderungs- und Bedenkenanzeige, jeweils mit
  eigener fachlicher Folge -- dockt über `purpose` + Folge-Registry an (siehe unten).
- **Stufe 3** (später): Offline-Betrieb. Stufe 1 bereitet nur `client_uuid` und idempotentes
  Speichern vor, keine Warteschlange, kein Service Worker.
- **Stufe 4**: noch nicht beschrieben.

---

## Befund vor dem Bauen (29.09.2026, keine Codeänderung)

### Vier Funde, die den Entwurf prägen

1. **`client_uuid` am Einsatzbericht ist NICHT idempotent.** `InspectionItem`, `Finding`,
   `ServiceReportPhoto`, `ServiceReportMaterial` und `ServiceReportAsset` tragen `client_uuid` mit
   Unique-Constraint (`(service_report_id, client_uuid)`), aber kein Code prüft vor dem Einfügen
   und keiner fängt die `IntegrityError` ab -- eine wiederholte Anfrage endet als unbehandelter
   500 statt 200. `tests/test_v213_inspection_items.py`/`tests/test_v223_service_report_materials.py`
   erwarten die `IntegrityError` sogar ausdrücklich. "Vorbereitet" hieß dort nur "Constraint
   existiert". **Als offener Punkt in CLAUDE.md vermerkt, Pflicht vor Stufe 3** (Betreibervorgabe);
   der Baukasten macht es von Anfang an richtig.
2. **"Betriebsmittel über QR" = jedes Betriebsmittel über seine ID.** Der QR-Code kodiert nur
   `/betriebsmittel/{id}` (`asset_qr_target_url()`), kein Geheimnis; IDs sind fortlaufend. Das ist
   dieselbe bewusste Ausnahme wie die mobile Objektansicht (siehe
   `docs/archiv/rechtekonzept.md`, "Punkt 3 (Rechte) -- die eine bewusste Ausnahme").
3. **Monteure haben keinen Zugriff auf Aufgaben** (`/api/tasks*` Büro/Admin), und
   `Task.min_visible_role` wirkt nur auf empfängerlose Aufgaben. Eine Regel darf als Zielrolle
   deshalb nur `buero_auftrag`/`buero_finanzen`/`admin` anbieten, nie `field`.
4. **`app/tasks.py::create_task()` committet selbst.** Aufgaben können erst NACH dem Commit des
   Abschlusses entstehen (Muster `sign_report()`), mit eigener Idempotenzsperre -- sonst doppelte
   oder fehlende Aufgaben bei einem wiederholten/abgebrochenen Abschluss.

### Warum ein eigenes Modell statt Verallgemeinerung von `InspectionTemplate`

`InspectionTemplate`/`InspectionTemplateItem`/`InspectionItem` (siehe
`docs/archiv/modul-wartungen-und-monteursansicht.md`, "Strukturierte Prüfpunkte") ist fachlich an
die Dachwartung gebunden: vierstufige Auflösung über den Dachtyp inkl.
`RoofTypeInspectionTemplateDefault`, Multiplikation von `component_type` gegen den
`RoofComponent`-Bestand mit `sort_order`-Bandrechnung, wartungsspezifische Typen
(`condition_grade`, `leak_test`, `target_min/max`), `InspectionItem.service_report_id NOT NULL`,
Fotos genau an Prüfpunkt ODER Mangel, `sign_report()`-Logik (nok → Mangel → Foto, zwei feste
Unterschriftsspalten, Vertragsfortschreibung, "Rechnung erstellen"-Aufgabe) und Modul `wartungen`
(Checklisten am Betriebsmittel müssen ohne dieses Modul funktionieren). Verallgemeinern hieße, den
reifsten, am dichtesten getesteten Produktivbereich samt Migration auf echten Daten umzubauen.
**Entscheidung: eigenes Modell**, übernommen werden nur die Prinzipien (Schnappschuss, Einfrieren
beim Abschluss, `exclude_unset`-Speichern, rollenabhängige Schemata, Fotoverkleinerung).

**Nebenbefund Foto-Helfer**: `resize_and_store_photo()` (`app/service_report_photos.py`) ist fest
an `PHOTO_ROOT` gebunden, `app/property_documents.py` hat deshalb schon eine Kopie
(`_store_uploaded_file()`). Für Checklisten KEINE dritte Kopie -- ein kleiner, parametrisierter
Helfer (Zielordner als Argument). Neue Foto-Upload-Routen als gewöhnliche `def`-Route (Starlette-
Threadpool), NICHT `async def` (Befund 1.3.62: sonst blockiert jede Verkleinerung einen der beiden
gunicorn-Worker).

---

## Betreiberentscheidungen (29.09.2026)

- **Feldtypen** wie vorgeschlagen (siehe Datenmodell). Bewusst NICHT in Stufe 1: bedingte
  Sichtbarkeit, berechnete Felder, wiederholbare Zeilengruppen.
- **F -- Schnappschuss über unveränderliche, veröffentlichte Vorlagenfassungen** statt Feldkopie
  in jede Antwort.
- **A -- Anlegen an beliebigen Objekten/Betriebsmitteln über die ID**: erlaubt (konsistent mit dem
  Objekt-Upload). Die Regel-Aufgaben nennen den Ersteller, die Änderungshistorie schreibt mit.
  Bewusst benanntes Restrisiko: dieselbe Fehlerklasse wie der 1.3.59-Fund (Geschäftsdaten per
  erratener ID erzeugen), aber deutlich harmloser (kein Auftrag/Projekt entsteht).
- **B -- Checklisten von Kollegen**: ein Monteur sieht fremde Checklisten nur als Titel/Datum/
  Ersteller/Status, die Antworten nur, wenn die Vorlage `field_readable` ("für Monteure lesbar")
  trägt. Standard AUS, bei den Startvorlagen **Geräte-Sichtprüfung** und **Schadensmeldung Gerät
  AN**. **Zusätzlich**: die letzte Meldung "nicht einsatzbereit" erscheint deutlich oben auf der
  Geräteseite in `/mobil` (`operational_asset_field.html`) -- siehe "Einsatzbereitschaft" unten.
- **C -- Aufgabenmodul aus**: die Auslösung wird protokolliert (`ChecklistRuleExecution` mit
  Status `modul_aus`) und kann nachgeholt werden, statt still zu entfallen.
- **D -- vierter Kontext "Betrieb"** (Beispiel: jährliche Sicherheitsunterweisung, kein Auftrag):
  anlegen nur `buero_auftrag` aufwärts; Teilnehmer unterschreiben auf dem Gerät des
  Unterweisenden (Unterschriftsfeld mit `multiple=True`, Name je Unterschrift). Monteure haben auf
  Betrieb-Checklisten keinen Zugriff.
- **E -- Aufmaß**: ein Bereich je Checkliste (mehrere Checklisten je Auftrag).
- **Startvorlagen**: alle als Entwurf, jede mit dem Hinweis "vor Veröffentlichung durch Fachkraft
  für Arbeitssicherheit prüfen" (als `hinweis`-Feld ganz oben UND in der Vorlagenbeschreibung).
  Ergänzungen siehe Abschnitt "Startvorlagen".
- **Einsatzbericht-`client_uuid`** (Fund 1): offener Punkt in CLAUDE.md, Pflicht vor Stufe 3.

---

## Datenmodell (verbindlich für 1.8.0)

Alle Tabellen in EINER Migration (1.8.0). Zeilen statt JSON (im ganzen `app/models.py` gibt es
keine JSON-Spalte). NOT-NULL-Spalten mit `server_default` (Regel 1, auch wenn die Tabellen neu
sind -- Gewohnheit). Booleans in rohem SQL nie als `1`/`0` (PostgreSQL).

### Vorlagen

**`ChecklistTemplate`** (`checklist_templates`) -- Identität und veränderliche Verwaltungsdaten:
`id`, `label` (String 160), `description` (Text), `purpose` (String 40, Default `allgemein`),
`context_order`/`context_property`/`context_asset`/`context_company` (vier Booleans, erlaubte
Kontexte), `field_readable` (Boolean, Default aus -- Entscheidung B), `sort_order`, `archived`,
`created_at`/`updated_at`. Label/Kontexte/`field_readable` dürfen sich ändern -- eine Checkliste
friert ihr Label beim Anlegen ein, die Kontexte wirken nur aufs Anlegen neuer Checklisten.

**`ChecklistTemplateVersion`** (`checklist_template_versions`) -- die Fassung, das eigentliche
Schnappschuss-Objekt: `template_id`, `version_no` (unique je Vorlage), `status`
(`entwurf`|`veroeffentlicht`|`abgeloest`), `published_at`, `published_by_user_id`, `created_at`.
Regeln:
- Höchstens EINE Entwurfsfassung je Vorlage. "Bearbeiten" einer Vorlage mit nur veröffentlichter
  Fassung legt eine neue Entwurfsfassung als Kopie (Felder, Optionen, Regeln) an.
- Veröffentlichen: Entwurf → `veroeffentlicht`, die bisher veröffentlichte → `abgeloest`. Nur
  Felder/Regeln einer Entwurfsfassung sind änderbar -- jede andere Fassung ist eingefroren.
- Eine Fassung, auf die eine Checkliste verweist, ist nicht löschbar (Muster
  `delete_component_type()`). Eine unbenutzte Entwurfsfassung darf verworfen werden.
- Monteure sehen nur die veröffentlichte Fassung.

**`ChecklistTemplateField`** (`checklist_template_fields`) -- hängt an der Fassung:
`version_id`, `field_key` (String 80, unique je Fassung, stabil über Fassungen hinweg -- wird beim
Kopieren übernommen), `sort_order`, `group_name` (Abschnitt), `field_type`, `label` (String 500),
`help_text`, `required`, `allow_na` (ja_nein: dritte Wahl "entfällt"), `multiline` (text),
`multiple` (auswahl, unterschrift), `unit`, `min_value`/`max_value` (Numeric 18,4), `decimals`,
`min_count`/`max_count` (foto, unterschrift), `prefill_now` (datum/uhrzeit/datum_uhrzeit),
`signer_label` (String 80, unterschrift: "Monteur", "Kunde", "Brandwache"…), `is_system`
(Stufe 2: umbenennbar, nicht löschbar, Schlüssel nicht änderbar).

`field_type` ist ein Code-Tupel (Muster `ITEM_TYPES`), keine Optionsgruppe:
`ja_nein`, `text`, `zahl`, `auswahl`, `datum`, `uhrzeit`, `datum_uhrzeit`, `foto`,
`unterschrift`, `hinweis` (keine Antwort, `required` wird ignoriert).

**`ChecklistTemplateFieldOption`** (`checklist_template_field_options`): `field_id`,
`option_key` (String 80, unique je Feld), `label` (String 160), `sort_order`.

**`ChecklistTemplateRule`** (`checklist_template_rules`) -- hängt an der Fassung:
`version_id`, `field_key` (nullable -- NULL nur bei `immer`), `operator`
(`immer`|`ist_ja`|`ist_nein`|`enthaelt`|`kleiner`|`groesser`|`gleich`|`ausgefuellt`),
`operand` (String 160, bei `enthaelt` der `option_key`, bei Zahlvergleichen die Zahl),
`task_title` (String 255, Platzhalter `{vorlage}`, `{kontext}`, `{ersteller}`),
`task_description`, `task_priority` (Werte wie `Task.priority`), `due_in_days` (nullable),
`assignee_mode` (`rolle`|`sachbearbeiter`), `min_visible_role` (nur `buero_auftrag`/
`buero_finanzen`/`admin`, Fund 3), `sort_order`. `sachbearbeiter` = `Order.caseworker_employee_id`,
nur im Kontext Auftrag sinnvoll; fehlt er, wird die Aufgabe empfängerlos mit `min_visible_role`.

### Ausgefüllte Checklisten

**`Checklist`** (`checklists`): `template_id`, `template_version_id`,
`template_label_snapshot`, `context_type` (`auftrag`|`objekt`|`betriebsmittel`|`betrieb`),
`order_id`/`property_id`/`operational_asset_id` (je nullable FK, genau einer passend zum
Kontext gesetzt, bei `betrieb` keiner -- geprüft in der Geschäftslogik, kein CheckConstraint,
Projektkonvention), `context_label_snapshot` (Auftragsnummer/Objektname/Gerätename),
`context_detail_snapshot` (Adresse/Kunde, für PDF und Liste), `status` (`entwurf`|
`abgeschlossen`), `created_by_employee_id`, `created_by_user_id`, `completed_at`,
`completed_by_employee_id`, `client_uuid` (String 36, global unique, NULL erlaubt),
`created_at`/`updated_at`.

**`ChecklistAnswer`** (`checklist_answers`) -- genau eine je Feld (unique
`(checklist_id, template_field_id)`, dadurch Speichern = Upsert = von Natur aus idempotent):
`checklist_id`, `template_field_id`, `field_key` (Kopie, für Abfragen/Stufe 2),
`value_text` (text; bei ja_nein `ja`|`nein`|`entfaellt`; bei Einfachauswahl der `option_key`),
`value_number`, `value_date`, `value_time`, `value_datetime`, `recorded_at`,
`recorded_by_employee_id`, `client_uuid` (unique je Checkliste), `client_recorded_at`
(Stufe-3-Vorbereitung: eine ältere Antwort überschreibt keine neuere).

**`ChecklistAnswerSelection`** (`checklist_answer_selections`) -- Mehrfachauswahl:
`answer_id`, `option_key`, unique `(answer_id, option_key)`.

**`ChecklistAttachment`** (`checklist_attachments`) -- Fotos UND Unterschriften:
`checklist_id`, `template_field_id`, `kind` (`foto`|`unterschrift`), `stored_filename`,
`signer_name` (nur Unterschrift), `sort_order`, `created_by_employee_id`, `created_at`,
`client_uuid` (unique je Checkliste). Eigener Datenordner mit eigener Env-Var
(`DACHKONZEPTE_CHECKLIST_FILE_ROOT`, Muster der übrigen Upload-Pfade, in `.env.example`
eintragen), Auslieferung über einen dedizierten, rollengeprüften Endpunkt.

**`ChecklistRuleExecution`** (`checklist_rule_executions`) -- Idempotenzsperre der Regeln:
`checklist_id`, `rule_id`, unique `(checklist_id, rule_id)`, `task_id` (nullable),
`status` (`aufgabe_angelegt`|`modul_aus`), `executed_at`.

---

## Verhalten

### Ausfüllen und Abschließen
- Speichern einer Antwort: `exclude_unset`-Muster, nur im Entwurf, nur durch den Ersteller
  (Büro/Admin: jeder Entwurf).
- **Idempotenz** (Stufe-3-Vorbereitung): existiert eine `client_uuid` schon (Checkliste, Antwort,
  Anhang), Antwort 200 mit dem vorhandenen Datensatz -- geprüft VOR dem Einfügen, zusätzlich
  `IntegrityError` in einem `db.begin_nested()`-SAVEPOINT abgefangen (gleichzeitige Anfragen,
  Muster "Self-Seeding"). Eine Wiederholung einer bereits gespeicherten `client_uuid` nach dem
  Abschluss liefert ebenfalls 200; eine NEUE Änderung an einer abgeschlossenen Checkliste 409.
  Der Abschluss selbst ist idempotent (zweiter Aufruf = aktueller Stand).
- Abschließen prüft Pflichtfelder (inkl. `min_count` bei Foto/Unterschrift) und friert ein. Danach
  kein Ändern, kein Löschen. Ein Entwurf darf vom Ersteller bzw. Büro gelöscht werden (Anhänge
  samt Dateien werden mit entfernt -- `before_delete`-Event wie `roof_areas.py`).
- Regeln laufen NACH dem Commit des Abschlusses (Fund 4), nur auf eingefrorenen Antworten. Je
  ausgelöster Regel eine `ChecklistRuleExecution`-Zeile; Aufgabenmodul aus → Status `modul_aus`,
  im Büro sichtbar, per "Aufgaben nachholen" idempotent nachholbar. `source_module="checklisten"`,
  `source_url="/checklisten/{id}"`.

### Einsatzbereitschaft (Entscheidung B, Zusatz)
Generisch über den festen Feldschlüssel **`einsatzbereit`** (ja_nein): die jüngste
ABGESCHLOSSENE Checkliste am Betriebsmittel, die eine Antwort auf `einsatzbereit` trägt,
entscheidet. `nein` → deutlicher Hinweis oben auf `operational_asset_field.html` (Datum, Vorlage,
Ersteller); eine spätere Checkliste mit `ja` hebt ihn auf, seit 1.8.2 alternativ die Büro-
Markierung "repariert" (`ChecklistAssetRelease`, siehe "Umsetzung 1.8.2"). Die Startvorlagen Geräte-Sichtprüfung
und Schadensmeldung Gerät tragen genau diesen Schlüssel. Sinnvoll auch auf der Büro-Geräteseite.

### Rechte
| Kontext | Monteur (`field`) | Büro (`buero_auftrag`+) |
|---|---|---|
| Auftrag | Zugriff nur über `field_may_access_order()` (Planungsbezug ODER eigener Bericht); eine Checkliste ist KEIN dritter Zugriffsweg. Auswahl auf `/mobil` über `list_field_bookable_order_ids()` | alles |
| Objekt | jedes Objekt über die ID (wie Objektansicht) | alles |
| Betriebsmittel | jedes Betriebsmittel über die ID (Fund 2), Modul `betriebsmittel` muss aktiv sein | alles |
| Betrieb | kein Zugriff | anlegen/ausfüllen `buero_auftrag`+ |

- Schreiben: nur der Ersteller, nur im Entwurf (Muster `require_field_report_ownership()`).
- Fremde Checklisten desselben Kontexts: Monteur sieht Titel/Datum/Ersteller/Status, Antworten
  nur bei `field_readable`, Anhänge fremder Checklisten nur bei `field_readable`.
- Vorlagen pflegen: `require_min_role(ROLE_OFFICE_AUFTRAG)`. Monteure lesen nur veröffentlichte
  Fassungen passender Kontexte.
- Neues Modul `checklisten` in `OPTIONAL_MODULES` (Minor-Sprung 1.8.0, Regel 8); jede API prüft
  `is_module_enabled()` (403). Opt-out-Default: nach dem Einspielen sofort aktiv, aber leer
  (Startvorlagen sind Entwürfe).
- Jede neue Seite in die Seitenklassifizierung, jeder Endpunkt mit Rollenangabe (Audit-Test).

### PDF (1.8.3)
Neuer `document_type="checklist"` in `RENDERERS_USING_SHARED_FRAME` UND `DOCUMENT_TYPES`. Nur für
abgeschlossene Checklisten, bei jedem Abruf erzeugt (wie Einsatzbericht). Kopf aus den
Schnappschüssen; Kontext Betriebsmittel/Betrieb ohne Anschriftenfeld. Fotos mit `KeepTogether`,
Speicherbudget beachten (`max_count`). Monteur bekommt das PDF der eigenen Checkliste und fremder
nur bei `field_readable`.

### Zuschnitt für Stufe 2
- `purpose` an der Vorlage (Stufe 1 immer `allgemein`; Stufe 2: `regiebericht`, `abnahme`,
  `behinderung`, `bedenken`).
- Folge-Registry nach `purpose`, beim Abschluss neben den Regeln aufgerufen, gleiche
  Idempotenzsperre.
- `is_system`-Felder mit festen `field_key`s (z. B. `abnahme.vorbehalt_maengel`) -- Folgelogik
  liest nach Schlüssel, nie nach Beschriftung.
- Fachdaten in 1:1-Zusatztabellen zur Checkliste (Regel-6-Muster), keine neuen Spalten an
  `checklists`.
- Ein generischer PDF-Renderer; Stufe 2 steuert Titel/Zusatzabschnitte bei, bei Bedarf eigener
  `document_type`.

---

## Startvorlagen (1.8.4, Daten-Migration, alle als Entwurf)

Einmalig per Daten-Migration, NICHT per Self-Seeding (das würde vom Büro gelöschte Vorlagen
wiederherstellen). Jede Vorlage: erstes Feld `hinweis` "Vor Veröffentlichung durch eine Fachkraft
für Arbeitssicherheit prüfen." plus derselbe Satz in `description`. P = Pflicht, U = Unterschrift.
Werte für `allow_na` bei "ja/nein/entfällt".

1. **Sicherheitscheck vor Arbeitsbeginn** (Auftrag): Absturzsicherung vorhanden und geprüft
   (ja/nein, P); Art der Absturzsicherung (Auswahl mehrfach: Gerüst, Seitenschutz, Fangnetz,
   PSAgA, Dachfanggerüst; P); **nicht durchtrittsichere Bauteile gesichert (ja/nein/entfällt, P)**;
   **Anschlagpunkte geprüft und Rettung aus PSAgA geklärt (ja/nein/entfällt)**; PSA vollständig
   (ja/nein, P); Leitern/Gerüst Sichtprüfung ok (ja/nein); Witterung geeignet (ja/nein, P);
   Gefahrenbereich abgesperrt (ja/nein/entfällt); Freileitungen im Arbeitsbereich (ja/nein);
   Erste Hilfe und Notruf geklärt (ja/nein); Arbeitsbeginn freigegeben (ja/nein, P); Bemerkung;
   Foto (0–3); U Monteur (P). Regel: "freigegeben = nein" → Aufgabe an Sachbearbeiter,
   **Priorität hoch**.
2. **Heißarbeiten mit Brandwache** (Auftrag): Freigabe durch Auftraggeber (ja/nein/entfällt);
   Arbeitsbereich (Text, P); **Gasflasche/Schlauch/Brenner Sichtprüfung ok (ja/nein, P)**;
   Brennbares entfernt oder abgedeckt (ja/nein, P); Löschmittel bereitgestellt (Auswahl, P);
   Brandwache Name (Text, P); Beginn / Ende (Datum+Uhrzeit, P); Nachkontrolle bis
   (Datum+Uhrzeit, P; Mindestdauer legt der Betrieb im Hilfetext fest); Nachkontrolle ohne Befund
   (ja/nein, P); Foto; U Ausführender, U Brandwache. Regel: **"Nachkontrolle ohne Befund = nein"
   → Aufgabe, Priorität hoch**.
3. **Sicherheitsunterweisung** (Kontext **Betrieb**, zusätzlich Auftrag für baustellenbezogene
   Unterweisung): Themen (Auswahl mehrfach: Absturz, Heißarbeiten, Gefahrstoffe/Asbest,
   Leitern/Gerüste, Witterung, Erste Hilfe, Sonstiges); Inhalt (Text, P); Unterweisender
   (Text, P); Datum+Uhrzeit (P); Dauer (Zahl, min); U Teilnehmer (mehrfach, P); U Unterweisender.
4. **Gefahrstoff-Verdacht** (Auftrag, Objekt): Hinweis "Arbeiten im Bereich sofort einstellen";
   Verdacht auf (Auswahl mehrfach: Asbest/Faserzement, alte Mineralwolle (KMF), teer-/PAK-haltige
   Abdichtung, Sonstiges; P); Fundort/Bauteil (Text, P); geschätzte Fläche (Zahl m²); Material
   bereits bearbeitet (ja/nein, P); Arbeiten eingestellt (ja/nein, P); Bereich abgesperrt
   (ja/nein); Fotos (min 1, P); Bemerkung; U Monteur (P). Regel: **immer** → Aufgabe, Priorität
   hoch, `buero_auftrag`.
5. **Tagesbericht** (Auftrag): Datum (P, vorbelegt); Wetter (Auswahl); Temperatur (Zahl °C);
   Anwesende (Text); ausgeführte Arbeiten (Text, P); **Materiallieferungen (Text)**;
   **Anordnungen durch Auftraggeber/Bauleitung (Text)**; besondere Vorkommnisse (Text);
   Behinderung aufgetreten (ja/nein, P); Fotos (0–10); U Monteur. Keine Stunden (stehen in der
   Zeiterfassung). Regeln: "Behinderung = ja" → Aufgabe; **"Anordnungen ausgefüllt" → Aufgabe an
   Sachbearbeiter**.
6. **Pflichtfotos verdeckte Arbeiten** (Auftrag): Bereich (Text, P); Art (Auswahl: Dampfsperre,
   Dämmung, Unterdeckbahn, Anschlüsse/Durchdringungen, Abdichtung unter Auflast, Befestigung,
   Sonstiges; P); Fotos (min 2, P); Ausführung nach Vorgabe/Herstellerrichtlinie (ja/nein, P);
   Abweichung (Text); U Monteur. Regel: "nach Vorgabe = nein" → Aufgabe.
7. **Vorher/Nachher** (Auftrag, Objekt): Bereich (Text, P); Vorher-Fotos (min 1, P);
   Nachher-Fotos (min 1, P); Bemerkung.
8. **Entsorgungsnachweis** (Auftrag): Abfallart (Auswahl mit AVV-Bezeichnung; P); Menge (Zahl, P)
   und Einheit (Auswahl t/m³/Big Bag); Entsorger/Annahmestelle (Text, P); Übergabe
   (Datum+Uhrzeit, P); Wiege-/Lieferschein-Nr. (Text); Beleg-Foto (min 1, P); U Monteur.
9. **Aufmaß einfach** (Auftrag, Objekt): Bereich/Position (Text, P); Länge (m), Breite (m), Fläche
   (m², von Hand), Stück (Zahl); Skizze/Foto; Bemerkung. Ein Bereich je Checkliste (E).
10. **Geräte-Sichtprüfung** (Betriebsmittel, `field_readable` AN): Gehäuse/Rahmen unbeschädigt
    (ja/nein, P); Kabel/Stecker/Schläuche (ja/nein/entfällt, P); Schutzeinrichtungen
    funktionsfähig (ja/nein/entfällt); Prüfplakette gültig (ja/nein/entfällt); Funktionstest ok
    (ja/nein, P); Betriebsstunden (Zahl); **Gerät einsatzbereit (ja/nein, P, `field_key`
    `einsatzbereit`)**; Bemerkung; Foto; U Monteur. Regel: "einsatzbereit = nein" → Aufgabe.
    Schreibt `OperationalAssetInspection.last_inspection_date` bewusst NICHT fort (keine
    UVV-Prüfung).
11. **Schadensmeldung Gerät** (Betriebsmittel, `field_readable` AN): Schadensart (Auswahl:
    mechanisch, elektrisch, Verschleiß, fehlt/verloren, Sonstiges; P); Beschreibung (Text, P);
    festgestellt am (Datum+Uhrzeit, P); **noch einsatzbereit (ja/nein, P, `field_key`
    `einsatzbereit`)**; außer Betrieb gekennzeichnet (ja/nein); Fotos (min 1, P); U Monteur.
    Regeln: **immer** → Aufgabe; "einsatzbereit = nein" → Aufgabe, Priorität hoch.
12. **Abfahrtkontrolle** (Betriebsmittel/Fahrzeug): Kilometerstand (Zahl, P); Beleuchtung ok
    (ja/nein, P); Reifen ok (ja/nein, P); Ladung gesichert (ja/nein, P); Anhänger gesichert
    (ja/nein/entfällt); Warnweste/Verbandkasten/Warndreieck an Bord (ja/nein); Werkzeug
    vollständig (ja/nein); Schäden festgestellt (ja/nein, P); Foto; U Fahrer. Regel: "Schäden = ja"
    → Aufgabe.
13. **Nachtragsmeldung** (Auftrag): Hinweis "keine Preis- oder Terminzusage an den Kunden"; Art
    (Auswahl: Zusatzleistung auf Kundenwunsch, geänderte Ausführung, unvorhergesehener Befund,
    Mengenmehrung; P); Beschreibung (Text, P); Menge und Einheit; geschätzter Zeitaufwand
    (Zahl h); Material (Text); angeordnet durch (Text); bereits ausgeführt (ja/nein, P); Fotos
    (min 1, P); U Kunde (optional). Regel: **immer** → Aufgabe an Sachbearbeiter.

---

## Etappenplan

Je Version ein Commit (Regel 13), `VERSION` + `CHANGELOG.md` + `backup_windows.ps1` (Regeln 8/9).
Zwischen den Versionen darf der Betreiber `/clear` machen -- dann diese Datei lesen.

| Version | Inhalt | Stand |
|---|---|---|
| — | Befund, Entscheidungen, Etappenplan (diese Datei), Verweis in CLAUDE.md | erledigt |
| **1.8.0** | Modul `checklisten`, alle Tabellen + Migration, Vorlagenverwaltung (Liste `/checklisten/vorlagen`, eigene Editorseite `/checklisten/vorlagen/{id}`: Felder, Optionen, Regeln, Fassungen, Veröffentlichen), API, Tests | erledigt |
| **1.8.1** | Ausfüllen: Anlegen in allen vier Kontexten, Antworten/Fotos/Unterschriften idempotent, Abschließen, Entwurf löschen, Einstiege in `/mobil` (Auftrag, Objektansicht, Geräteseite mit Einsatzbereitschafts-Hinweis), Büro-Übersicht `/checklisten`, Rechte + Angriffstest. **Danach anhalten und berichten** (Betreibervorgabe) | erledigt, vom Betreiber freigegeben (29.09.2026) |
| **1.8.2** | Nachtrag nach der 1.8.1-Freigabe (Betreibervorgabe): "nicht einsatzbereit" verschwindet wieder -- spätere Checkliste mit "ja" ODER Büro markiert als repariert (Wer/Wann), Tests für beide Wege | erledigt |
| **1.8.3** | Regeln → Aufgaben, `ChecklistRuleExecution`, "Aufgaben nachholen" (ursprünglich als 1.8.2 geplant) | erledigt |
| **1.8.4** | PDF über den gemeinsamen Rahmen (ursprünglich 1.8.3) | offen |
| **1.8.5** | 13 Startvorlagen per Daten-Migration (Entwurf) (ursprünglich 1.8.4). **Danach berichten** (Betreibervorgabe: nach Abschluss der geplanten Etappen) | offen |

Nach jeder Version hier die Spalte "Stand" nachziehen und unten einen kurzen Abschnitt
"Umsetzung 1.8.x" mit Abweichungen/Funden ergänzen.

---

## Umsetzung 1.8.0 (29.09.2026)

- **Dateien**: `app/checklist_templates.py` (Geschäftslogik, rollenlos), `app/routers/
  checklist_templates.py` (alle Endpunkte `require_min_role(ROLE_OFFICE_AUFTRAG)` + Modulprüfung),
  Schemas am Ende von `app/schemas.py`, Modelle am Ende von `app/models.py`, Seiten
  `checklist_templates.html` (Liste) und `checklist_template.html` (Editor), Seitenrouten in
  `app/routers/pages.py`, Sidebar-Eintrag "Checklisten" (bis 1.8.1 direkt auf die Vorlagen),
  Migration `9d6f31f78b88`, Tests `tests/test_v304_checklist_templates.py`.
- **API** (Auszug): `/api/checklist-templates` (Liste/Anlegen), `…/{id}` (GET/PUT/DELETE),
  `…/{id}/draft` (POST neuer Entwurf, idempotent / DELETE verwerfen), `…/{id}/publish`,
  `…/{id}/copy`, `…/{id}/archive|unarchive`, `/api/checklist-template-versions/{id}` (GET) mit
  `/fields`, `/fields/reorder`, `/rules`; `/api/checklist-template-fields/{id}` (PUT/DELETE,
  `exclude_unset`) mit `/options`; `/api/checklist-template-field-options/{id}`,
  `/api/checklist-template-rules/{id}`. Fehler: `ValueError` → 400, `LookupError`/fehlend → 404.
- **Abweichungen/Ergänzungen zum Plan**:
  - "+ Neue Vorlage" legt sofort eine Vorlage "Neue Vorlage" mit Entwurf 1 an und springt in den
    Editor -- kein unter der Liste eingeblendetes Formular (Regel 10).
  - Ein Entwurf lässt sich nur verwerfen, wenn schon einmal veröffentlicht wurde (sonst bliebe
    keine Fassung übrig -- dafür "Vorlage löschen").
  - `field_key` wird aus der Beschriftung erzeugt (Umlaute ausgeschrieben, `_` statt Leerzeichen),
    eindeutig je Fassung; Umbenennen zieht die Regeln derselben Fassung mit. Ein Feld/eine Option,
    auf die eine Regel verweist, ist nicht löschbar. Der `option_key` ist nach dem Anlegen fest.
  - Typwechsel setzt typfremde Eigenschaften zurück (`_normalize_field()`), ein Wechsel weg von
    "auswahl" löscht die Optionen. Einzel-Unterschrift erzwingt `max_count=1`.
  - Veröffentlichen prüft: mindestens ein Kontext, mindestens ein ausfüllbares Feld, jedes
    Auswahlfeld hat Optionen, jede Regel ist (noch) gültig.
  - Regelprioritäten = `app/tasks.py::PRIORITIES`.
- **Klicktest-Fund, vor dem Commit behoben**: das Regelformular filterte die Bedingungen nach dem
  noch leeren Feld -- eine neue Regel bot nur "immer" an. Jetzt: alle Bedingungen wählbar, die
  Feldauswahl zeigt die passenden Felder.
- **Nebenbefund, nicht behoben**: ein reiner Import-Check (`python -c "import app.main"`) legt über
  `create_all()` die neuen Tabellen in der lokalen `dachkonzepte_erp.db` an. Die Datei steht
  ohnehin auf dem alten Migrationsstand `1375eeeea2fa` und wird über `create_all()` (auch bei
  jedem Testlauf) nachgezogen, nicht über Alembic -- die zehn leeren Tabellen ändern daran
  nichts. Die Migration war zu dem Zeitpunkt bereits erzeugt und ist vollständig.
- **Verifikation**: Migration gegen frische SQLite UND frische PostgreSQL (portable Instanz,
  eigene Probe-DB `checklisten_probe`, danach gelöscht) hin/zurück/hin, `alembic check` ohne
  Abweichung, Vorlagenlogik direkt gegen PostgreSQL durchgespielt. Volle Suite 1919 grün.
  Klicktest per CDP gegen eine isolierte Instanz (Temp-SQLite, Konto `buero_auftrag`): Liste,
  Anlegen, Felder, Optionen, Typwechsel, Reihenfolge, Regel, Veröffentlichen, neuer Entwurf --
  keine JS-Ausnahme. Die Klicktest-Skripte (Seed, CDP-Treiber) lagen nur im Scratchpad.

---

## Umsetzung 1.8.1 (29.09.2026)

- **Dateien**: `app/checklists.py` (Geschäftslogik, rollenlos), `app/routers/checklists.py`
  (Rechte, siehe Moduldocstring), `app/image_storage.py` (gemeinsamer Bildhelfer; 
  `service_report_photos.resize_and_store_photo()` delegiert seither dorthin, gleiches Verhalten;
  `property_documents.py` bewusst unverändert), Vorlagen `checklist.html` (Ausfüllen, eine Datei
  für alle Rollen: `field` mit `_mobile_header.html`, sonst Sidebar), `checklist_order.html`
  (`/checklisten/auftrag/{order_id}`, Einstieg aus `/mobil`), `checklists.html` (Büro-Übersicht
  `/checklisten` inkl. Bereich Betrieb), Include `_checklists_section.html` (Liste + "Checkliste
  starten", eingebunden in `mobil_objekt.html`, `operational_asset_field.html`, `order.html`,
  `property.html`, `operational_asset.html`). `/mobil`: Link je Einsatz, Abschnitt "Offene
  Checklisten". Sidebar "Checklisten" → `/checklisten`. Tests `tests/test_v305_checklist_filling.py`,
  Stichprobe der Seitenklassifizierung in `test_v260_role_audit.py` erweitert.
- **API**: `GET /api/checklists/startable-templates?context=`, `GET /api/checklists` (Büro frei
  filterbar; Monteur genau ein Bezug), `GET /api/checklists/mine`, `GET /api/checklists/
  asset-readiness/{asset_id}`, `POST /api/checklists`, `GET /api/checklists/{id}`,
  `PUT /api/checklists/{id}/answers/{field_id}` (`value`, `client_uuid`, `client_recorded_at`),
  `POST /api/checklists/{id}/attachments` (multipart, gewöhnliche `def`-Route),
  `GET|DELETE /api/checklist-attachments/{id}[/file]`, `POST /api/checklists/{id}/complete`,
  `DELETE /api/checklists/{id}`. Fehler: 400 fachlich, 403 Rechte, 404 fehlt, 409 abgeschlossen.
- **Festlegung (im Bericht an den Betreiber benannt)**: die EIGENE Checkliste bleibt für den
  Monteur erreichbar, auch wenn er nicht mehr dem Auftrag zugeordnet ist (Überlegung wie Weg 2
  beim Einsatzbericht). Das öffnet nur diese Checkliste, nie den Auftrag; eine neue Checkliste am
  Auftrag verlangt weiterhin den Auftragszugriff.
- **Weitere Einzelheiten**: eine `client_uuid` beim Anlegen liefert den vorhandenen Datensatz nur
  an dieselbe Person (Konto UND Mitarbeiter), sonst 400. Einzelunterschrift: neu unterschreiben
  ersetzt die alte. Fotofeld ohne `max_count`: höchstens 20. Unterschrift verlangt einen Namen
  (bei Einzelunterschriften mit Rollenbeschriftung "Monteur/Ausführender/Fahrer" mit dem eigenen
  Namen vorbelegt). `prefill_now` belegt ein leeres Datums-/Zeitfeld beim ersten Öffnen mit
  "jetzt" und speichert es. Mehrfachauswahl wird abgeglichen statt ersetzt (Unique-Constraint).
  Einsatzbereitschaft: Feldschlüssel `einsatzbereit`, nur abgeschlossene Checklisten, bewusst
  unabhängig von `field_readable` (Sicherheitsangabe).
- **Verifikation**: 26 Tests inkl. Angriffstest (Monteur ohne Zuordnung probiert Checklisten-,
  Anhang- und Listen-Endpunkte mit erratenen IDs, 0 durchgelassen; Gegenprobe mit abgeschalteter
  Eigentümer-/Kontextprüfung rot). Volle Suite 1945 grün. Klicktest per CDP gegen isolierte
  Instanzen (Temp-SQLite): Monteur auf 412 px Breite startet am Auftrag, Kacheln, Zahl mit
  Grenzwert und Komma, verzögerter Text, Abschließen verweigert, Foto über
  `DOM.setFileInputFiles`, Unterschrift über echte Zeigerereignisse, Abschluss, `/mobil`,
  Gerät "nicht einsatzbereit" → Hinweis oben; Büro: Übersicht, Filter, Ausfüllseite mit Sidebar,
  Geräte-/Objekt-/Auftragsseite. Gefunden und behoben: stehen gebliebene Abschluss-Meldung,
  Kontrast des roten Hinweises im Dunkelmodus. Klicktest-Fallstrick: `confirm()` blockiert in
  Headless-Chrome jede weitere Auswertung -- per `Page.addScriptToEvaluateOnNewDocument` auf jeder
  Seite bestätigen.
- **Noch nicht gebaut (1.8.2 ff.)**: Regeln → Aufgaben (Tabelle `checklist_rule_executions` steht
  bereit, `complete_checklist()` ist die Andockstelle NACH dem Commit), PDF, Startvorlagen.

---

## Umsetzung 1.8.2 (29.09.2026)

Betreibervorgaben bei der Freigabe von 1.8.1: (1) "nicht einsatzbereit" muss wieder verschwinden,
eine spätere Checkliste mit "ja" hebt die Warnung auf, zusätzlich markiert das Büro als
"repariert" mit Wer und Wann, Test für beide Wege; (2) volle Suite; (3) Import-Checks und Prüfungen
nie gegen `dachkonzepte_erp.db` (Regel 16). Bestätigt: die eigene Checkliste bleibt nach einer
Umplanung erreichbar.

- **Neue Tabelle `ChecklistAssetRelease`** (`checklist_asset_releases`, Migration `144a46fc5a97`):
  `operational_asset_id`, `checklist_id` (unique, GENAU die "nein"-Checkliste, die aufgehoben
  wird), `released_at`, `released_by_user_id`/`released_by_employee_id`, `released_by_name`
  (Schnappschuss des Anzeigenamens), `note`. Die Checkliste selbst bleibt eingefroren.
- **`asset_readiness()`**: wirksam ist weiterhin die jüngste abgeschlossene Checkliste mit Antwort
  auf `einsatzbereit`. Ist sie "nein" und hat eine Freigabe → `ready=true` plus `released_*`;
  `reported_ready` trägt, was die Checkliste selbst ergab. Eine neuere "nein"-Checkliste hat keine
  Freigabe und gilt damit wieder -- kein Zeitvergleich nötig.
- **`mark_asset_repaired()`** / `POST /api/checklists/asset-readiness/{asset_id}/repaired`
  (`buero_auftrag` aufwärts, Module `checklisten` UND `betriebsmittel`): ohne wirksames "nein"
  400, zweiter Klick liefert den vorhandenen Stand (Unique + SAVEPOINT). Monteure: 403, sie heben
  nur über eine neue Checkliste auf.
- **Oberfläche**: `operational_asset.html` -- Notizfeld + Knopf im roten Hinweis (sichtbares Feld,
  kein Popup, Regel 4), danach neutrale Zeile `.readiness-info`. `operational_asset_field.html`
  nennt im Hinweistext beide Wege.
- **Nebenbefund, mitbehoben**: `delete_asset()` prüfte keine Checklisten -- jetzt `ValueError`
  (Router 400, "archivieren statt löschen"), Muster der bestehenden Einsatzbericht-Sperre.
- **Regel 16 strukturell**: `tests/conftest.py` setzt `DATABASE_URL`/`ERP_DATA_DIR` vor dem ersten
  `app.*`-Import auf ein frisches Temp-Verzeichnis (eigener Commit ohne Versionssprung). Vorher
  griff jeder Testlauf über `create_all()` und die Jinja-Globals auf `dachkonzepte_erp.db` zu;
  nachgewiesen unberührt (Zeitstempel/Größe vor und nach der vollen Suite gleich). Import-Checks,
  Migrationsprüfungen und Klicktests laufen ausschließlich gegen Wegwerf-Datenbanken im Scratchpad
  bzw. die Probe-DB `checklisten_probe` der portablen PostgreSQL-Instanz.
- **Verifikation**: Migration SQLite + PostgreSQL hin/zurück/hin, `alembic check` sauber; Logik
  direkt gegen PostgreSQL durchgespielt; 7 neue Tests (`tests/test_v306_checklist_asset_release.py`),
  Gegenprobe (Endpunkt für jede Rolle offen) rot. Klicktest per CDP gegen isolierte Instanz:
  Monteur sieht roten Hinweis ohne Knopf, Büro gibt Notiz ein und markiert, neutrale Zeile mit
  Wer/Wann/Notiz auch nach Neuladen und im Dunkelmodus, Monteur danach ohne Hinweis. Keine
  JS-Ausnahme.

---

## Umsetzung 1.8.3 (29.09.2026)

- **Dateien**: `app/checklist_rules.py` (neu, rollenlos), Andockstelle in
  `app/checklists.py::complete_checklist()` NACH dessen Commit (lokaler Import), Endpunkte am Ende
  von `app/routers/checklists.py`, Anzeige in `checklist.html` (Karte "Ausgelöste Aufgaben", nur
  Büro und nur bei abgeschlossener Checkliste) und `checklists.html` (Hinweiskarte + Filter +
  "Alle nachholen"). Tests `tests/test_v307_checklist_rules.py`. Keine Migration.
- **API** (alle `buero_auftrag` aufwärts + Modulprüfung): `GET /api/checklists/{id}/rule-executions`,
  `POST /api/checklists/{id}/run-rules` (nachholen, 400 bei Entwurf), `POST /api/checklists/
  run-open-rules` (alle), `GET /api/checklists?open_rules=true` (Monteur 403).
- **Ablauf**: je zutreffender Regel zuerst `ChecklistRuleExecution` belegen (Unique + SAVEPOINT,
  eigener Commit), dann `create_task()` (committet selbst, Fund 4), dann Status
  `aufgabe_angelegt` + `task_id`. Dritter Status **`ausstehend`** (belegt, Anlegen nicht bestätigt)
  zusätzlich zu `modul_aus` -- beide gelten als offen und sind nachholbar. Nachholen belegt eine
  offene Zeile per bedingtem UPDATE auf (`id`, `status`, `executed_at`); nur einer gewinnt.
  Bewusst benanntes Restrisiko: Abbruch GENAU zwischen `create_task()` und dem Vermerk der
  `task_id` → späteres Nachholen legt eine zweite Aufgabe an. Ein Fehler in der Auswertung wird
  in `run_rules_after_completion()` abgefangen und protokolliert (nur ID, Regel 18) -- der
  Abschluss selbst bleibt gültig.
- **Aufgabenwerte**: Titel/Beschreibung mit Platzhaltern per `replace` (keine `format()`-
  Fehler durch fremde Klammern), Fußzeile "Ausgelöst durch … Bedingung: …", `priority`,
  `due_date` = Abschlussdatum + `due_in_days`, `project_id` des Auftrags, Empfänger
  `Order.caseworker_employee_id` bei `sachbearbeiter` (sonst empfängerlos), `min_visible_role`
  immer aus der Regel, `source_module="checklisten"`, `source_url="/checklisten/{id}"`,
  `created_by_user_id` = Ersteller der Checkliste.
- **Bedingungen**: `ausgefuellt` bei Foto/Unterschrift = mindestens ein Anhang; `enthaelt` bei
  Einfachauswahl = gewählte Option; Zahlvergleiche gegen `value_number`; fehlende Antwort trifft
  nie zu (außer `immer`).
- **Klicktest-Funde, vor dem Commit behoben**: (1) noch nicht angelegte Regeln zeigten den rohen
  Titel mit Platzhaltern -- `list_rule_executions()` setzt sie jetzt ein; (2) "Nachholen" bei
  weiterhin ausgeschaltetem Modul zählte die übersprungenen `modul_aus`-Zeilen nicht, die Seite
  zeigte deshalb keinen Grund -- jetzt `module_off` = Zahl der weiterhin offenen Regeln;
  (3) "Alle nachholen" war niedriger als "Anzeigen" (Stil galt nur für `a.btnlink`).
- **Verifikation**: 8 Tests, zwei Gegenproben rot (ausgehebelte Idempotenzsperre; Belegung ohne
  Stempel -- dafür musste der Test auf eine `ausstehend`→`ausstehend`-Belegung verschärft werden,
  die erste Fassung wäre schon am Statuswechsel gescheitert und hätte den Stempel nie geprüft).
  Logik direkt gegen PostgreSQL (`checklisten_probe`): Modul aus → `modul_aus`, Belegung
  frisch/veraltet True/False, Nachholen 2 → 0. Volle Suite 1960 grün. Klicktest per CDP gegen
  isolierte Instanz: Büro sieht zwei nicht angelegte Regeln, Nachholen bei Modul aus meldet den
  Grund, Übersicht mit Hinweis und Filter, "Alle nachholen" legt 2 an, Links zu `/tasks?task=`,
  Monteur ohne Aufgabenbereich.

