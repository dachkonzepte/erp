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
- **Seit 1.8.13 sperrt eine Unterschrift** Antworten und Fotos (siehe "Umsetzung 1.8.13"), **seit
  1.8.14 nur die Felder oberhalb von ihr** (siehe "Umsetzung 1.8.14"); weitere Unterschriften und
  Abschließen bleiben möglich, keine Unterschrift wird ersetzt oder gelöscht, Entsperren nur über
  "Unterschrift verwerfen" (Büro, Begründung; **seit 1.8.15 je gewählter Unterschrift**, die in
  Feldern darunter fallen mit, siehe "Umsetzung 1.8.15").
- Abschließen prüft Pflichtfelder (inkl. `min_count` bei Foto/Unterschrift) und friert ein, **seit
  1.8.15 mit fester Kopie aller Felder und Prüfsumme**. Danach kein Ändern, kein Löschen. Ein Entwurf darf vom Ersteller bzw. Büro gelöscht werden (Anhänge
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
  `behinderung`, `bedenken`). **Seit 1.8.16 umgesetzt, mit den Schlüsseln der Betreibervorgabe:**
  `abnahme`, `behinderungsanzeige`, `bedenkenanzeige` -- ein `regiebericht` steht (noch) nicht in der
  Registry, siehe "Umsetzung 1.8.16".
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
| **1.8.4** | PDF über den gemeinsamen Rahmen (ursprünglich 1.8.3) | erledigt |
| **1.8.5** | 13 Startvorlagen per Daten-Migration (Entwurf) (ursprünglich 1.8.4). **Danach berichten** (Betreibervorgabe: nach Abschluss der geplanten Etappen) | erledigt, Bericht an den Betreiber offen |
| **1.8.13** | Stufe 2, Runde 2a-1: Unterschrift bindet den Inhalt (Sperre, Prüfsumme, "Unterschriften verwerfen", Historie, Notiz-Pflicht bei "repariert") | erledigt |
| **1.8.14** | Stufe 2, Runde 2a-1b: Unterschrift versiegelt abschnittsweise (feste Kopie, Prüfung je Unterschrift auf Seite und PDF, Fotos verworfener Unterschriften nie gelöscht, Heißarbeiten in zwei Abschnitten) | erledigt |
| **1.8.15** | Stufe 2, Runde 2a-1c: Verwerfen je Unterschrift (die darunter fallen mit), Abschluss mit fester Kopie und Prüfsumme, Nachtragsmeldung und Entsorgungsnachweis in zwei Abschnitten | erledigt |
| **1.8.16** | Stufe 2, Runde 2a-2: Zweck-Registry (Kontexte, Systemfelder, Folgen), Zweck an der Fassung eingefroren, Systemfelder geschützt und beim Veröffentlichen geprüft, Folgetabelle mit Nachholen | erledigt |
| **1.8.17** | Stufe 2, Runde 2a-3a: Ablage versendeter Dokumente und Versandprotokoll, Sperre gegen Doppelversand, mehrere Empfänger/CC, 3-MB-Grenze; Regel 18 im Regel-Protokoll. Eigene Archivdatei `docs/archiv/versandprotokoll-und-ablage.md` | erledigt |
| **1.8.19** | Stufe 2, Runde 2a-3b, Teil 1: Sperre "läuft gerade" in der Datenbank, Adressprüfung und deutsche Graph-Meldungen, hängende Einträge klären, Rechnung/Storno/Mahnung aus der Ablage (Details in `docs/archiv/versandprotokoll-und-ablage.md`) | erledigt |
| **1.8.20** | Stufe 2, Runde 2a-3b, Teil 2: Versandverlauf am Dokument, Checkliste per E-Mail mit verkleinerten Fotos (unter 3.000.000 Bytes), Zustellung auf anderem Weg nachtragen (Details in `docs/archiv/versandprotokoll-und-ablage.md`) | erledigt |
| **1.8.21** | Stufe 2b, Runde 2b-1a: Verbraucher-Merkmal und Vertragsgrundlage an Angebot/Auftrag (Kern, kein Modul). **Stufe 2b hat einen eigenen Etappenplan** (2b-1a bis 2b-4, Vertrag, Beteiligte, Behinderungs- und Bedenkenanzeige) in `docs/archiv/vertragsgrundlage-und-vertrag.md` | erledigt |

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

---

## Umsetzung 1.8.4 (29.09.2026)

- **Dateien**: `app/checklist_pdf.py` (`build_checklist_pdf()`, `format_answer()`), Eintrag
  `"checklist"` in `RENDERERS_USING_SHARED_FRAME` (`app/document_frame.py`) UND `DOCUMENT_TYPES`
  (`app/document_layout.py`), Endpunkt `GET /api/checklists/{id}/pdf` (gewöhnliche `def`-Route,
  dieselbe Leseprüfung `_checklist_for()` wie der Einzelabruf, 400 bei Entwurf), Knopf "PDF" in
  `checklist.html`. Tests `tests/test_v308_checklist_pdf.py`; `test_v229`s festgeschriebene
  Liste der Rahmen-Nutzer um `checklist` ergänzt. Keine Migration, kein eigenes Briefpapier (fällt
  auf `default` zurück wie der Stundenzettel).
- **Aufbau**: Kopfbereich `build_din5008_header_block()` -- Absender + Anschrift nur im Kontext
  Auftrag (aus dem Auftrags-Schnappschuss, dazu `build_object_address_block()`), sonst leer;
  Meta: Checkliste Nr., Bereich, Auftragsnr./Kunden-Nr. (Auftrag), Abschlussdatum, Seite 1/N.
  Wiederholungszeile auf Folgeseiten: Checkliste Nr., Auftragsnr., Abgeschlossen. Danach Titel
  (Schnappschuss), Bezug (Schnappschuss), Angelegt/abgeschlossen/Fassung; Felder in
  Vorlagenreihenfolge, `group_name` als Abschnittsüberschrift, Antworten als zweispaltige Tabelle
  (Antwortspalte 70 mm, Frage nimmt den Rest des tatsächlichen Satzspiegels), `hinweis` als
  kleiner Absatz, Fotos 70 mm (höchstens Satzspiegelbreite), Unterschriften 60×25 mm mit Name und
  Zeitpunkt.
- **Seitenumbruch** (Sichtprüfung, erste Fassung korrigiert): eigene Überschriftenstile mit
  `keepWithNext` (Abschnitts- und Feldüberschrift nie allein am Seitenende; die Feldüberschrift
  ohne den 4-mm-Einzug von `styles["h3"]`, der für Tabellenzellen des Einsatzberichts gedacht
  ist), Bilder `hAlign="LEFT"`, je Unterschrift Bild + Name als `KeepTogether` statt eines Blocks
  über alle (zehn Unterschriften hätten eine Seite gesprengt).
- **Speicher**: gemessen in einem eigenen Prozess nur für das Rendern (Windows
  `GetProcessMemoryInfo`), Beispiel mit 20 Fotos (Rauschbilder 4000×3000, auf 1600 px verkleinert,
  also eher große Dateien) und 6 Unterschriften: Arbeitsspeicher-Spitze +82 MB, 3,1 s, 12,8 MB
  PDF, 9 Seiten. Der doppelte Durchlauf für "Seite 1/N" ist darin enthalten.
- **Verifikation**: 6 Tests, Gegenprobe (PDF-Endpunkt ohne Leseprüfung) rot; volle Suite 1966
  grün; CDP-Klicktest: Knopf erscheint für Büro (Desktop) und Monteur (412 px) auf der
  abgeschlossenen Checkliste, Abruf liefert `application/pdf`.

---

## Umsetzung 1.8.5 (29.09.2026) -- Stufe 1 abgeschlossen

- **Migration `349704eab07d`** (`alembic/versions/349704eab07d_checklisten_startvorlagen.py`):
  Daten auf Modulebene (`STARTER_TEMPLATES`, Hilfen `_f()`/`_sig()`/`_r()`), Einfügen und
  Entfernen als eigene Funktionen `insert_starter_templates(bind)` / `remove_starter_templates(bind)`
  mit eigenen `sa.Table`-Definitionen (Primärschlüssel angegeben -- mit `sa.table()` ohne PK
  lieferte `inserted_primary_key` nichts; im ersten Testlauf gefunden). Kein Import aus
  `app.models`.
- **Verhalten**: Vorlage + Fassung 1 (`entwurf`) + Felder/Optionen/Regeln; eine schon vorhandene
  gleichnamige Vorlage wird übersprungen. `downgrade()` entfernt nur Startvorlagen, deren
  Fassungen alle `entwurf` sind und die keine Checkliste haben -- ein bearbeiteter, aber nie
  veröffentlichter Entwurf geht dabei mit (keine Spalte weist "unverändert" nach), bewusst so
  dokumentiert. Einzelunterschrift wie `_normalize_field()` mit `max_count=1`.
- **Inhalt gegenüber der Liste oben, Festlegungen im Detail**: erstes Feld `hinweis_pruefung`
  (FaSi-Satz, Hilfetext "nach der Prüfung löschen"); Gefahrstoff-Verdacht und Nachtragsmeldung
  mit einem zweiten Hinweisfeld (einstellen bzw. keine Zusagen). Fotofelder ohne Mengenangabe im
  Plan: 0–5, "Fotos (0–10)" wie angegeben. Unterschriften ohne "P" im Plan sind nicht Pflicht
  (so steht es dort; bei Heißarbeiten ggf. vor Veröffentlichung auf Pflicht stellen). Entsorgung:
  neun Abfallarten mit AVV-Nummer (gefährliche mit *), Hilfetext "mit dem Entsorger abgleichen";
  zusätzlich ein Bemerkungsfeld (die Option "Sonstiges" verweist darauf). Heißarbeiten: Hilfetext
  am Feld "Nachkontrolle bis", dass der Betrieb die Mindestdauer festlegt. Geräte-Sichtprüfung:
  Beschreibung "Keine Prüfung nach DGUV/UVV -- Prüffristen bleiben unverändert". Regeln ohne
  Prioritätsangabe im Plan: `normal`; Zielrolle aller Regeln `buero_auftrag`; "Aufgabe" ohne
  Empfängerangabe → Rolle, "an Sachbearbeiter" → `sachbearbeiter` (bei Tagesbericht und
  verdeckten Arbeiten ebenfalls Sachbearbeiter, weil auftragsbezogen). 13 Vorlagen, 132 Felder,
  11 Regeln.
- **Verifikation**: `tests/test_v309_checklist_starter_templates.py` (6 Tests: 13 Entwürfe mit
  Hinweis, echte Veröffentlichungsprüfung + Feldnormalisierung ohne stille Änderung -- Gegenprobe
  mit `max_count=30` rot --, veröffentlichen und anlegen, Kontexte/`field_readable`/
  `einsatzbereit`/Regelrollen, keine Dublette und Wiederholung ohne Wirkung, Downgrade lässt
  veröffentlichte/benutzte stehen). Alembic hin/zurück/hin gegen frische SQLite und gegen die
  Postgres-Probe `checklisten_probe` (mit Bestand aus den früheren Probe-Skripten: der Downgrade
  ließ genau die zwei fremden Vorlagen stehen), `alembic check` sauber, Veröffentlichungsprüfung
  aller 13 direkt auf PostgreSQL ohne Befund. Probe-DB danach gelöscht, portable Instanz wieder
  gestoppt. Volle Suite 1972 grün. Klicktest: Liste zeigt 13 Entwürfe, Editor von
  Sicherheitscheck (15 Felder, Regel) und Entsorgungsnachweis ohne JS-Ausnahme.
- **Stufe 1 damit fertig.** Nächste Schritte laut Plan: Stufe 2 (Regiebericht, Abnahme,
  Behinderungs-/Bedenkenanzeige über `purpose` + Folge-Registry), Stufe 3 (offline; Pflicht davor:
  `client_uuid`-Idempotenz am Einsatzbericht, siehe CLAUDE.md "Bekannte, bewusst offene Punkte").

---

## Umsetzung 1.8.13 (30.09.2026) -- Stufe 2, Runde 2a-1: Unterschrift bindet den Inhalt

Betreibervorgabe: (1) erste Unterschrift sperrt Antworten und Anhänge, jede Unterschrift mit
eigenem Zeitpunkt (UTC, Anzeige über `app/berlin_time.py`) und SHA-256 des unterschriebenen
Inhalts, weitere Unterschriften möglich, Ersetzen/Löschen nicht; (2) "Unterschriften verwerfen" nur
Büro, Begründung Pflicht, entsperrt; (3) Checklisten in `AUDITED_TYPES`, Unterschreiben/Verwerfen/
Abschließen/"repariert" in der Änderungshistorie; (4) "repariert" mit Pflicht-Notiz; (5)
Angriffstests mit Gegenprobe. Nur melden: Startvorlagen mit Feldern nach der ersten Unterschrift,
Migration bestehender unterschriebener Entwürfe, Nebenbefunde.

- **Datenmodell** (Migration `9e1377e27340`, fünf nullable Spalten an `checklist_attachments`):
  `content_sha256`, `discarded_at`, `discarded_by_user_id` (FK `app_users`), `discarded_by_name`,
  `discard_reason`. Zeitpunkt der Unterschrift = das schon vorhandene `created_at` (UTC, je
  Unterschrift); die API liefert zusätzlich `created_at_local` (Berliner Zeit, vom Server).
- **Sperre** hängt am Vorhandensein einer nicht verworfenen Unterschrift (`is_signed()`), nicht an
  einer Statusspalte. Gilt für jede Rolle, auch fürs Büro. `save_answer()`, Foto-Upload,
  `delete_attachment()` (Foto wie Unterschrift) und `delete_checklist()` → `ChecklistLocked` (409).
  Einzelunterschrift mit vorhandener Unterschrift → 409 (früher: ersetzt). Mehrfachunterschrift
  bis `max_count` und weitere Unterschriftsfelder bleiben offen, Abschließen auch. Eine
  Wiederholung derselben `client_uuid` bleibt 200 (Stufe-3-Vorbereitung unverändert).
- **Prüfsumme** (`signed_content_sha256()`): kanonisches JSON (`"v": 1`, sortierte Schlüssel) über
  Checklisten-ID, Fassung, Bezeichnungs-/Kontext-Schnappschüsse, jede ausgefüllte Antwort nach
  `field_key` (Zahlen normalisiert: 12.5000 aus der DB = 12.5) und jedes nicht verworfene Foto mit
  der SHA-256 seiner gespeicherten Datei (blockweise gelesen). Andere Unterschriften gehören nicht
  dazu: bei unverändertem Inhalt tragen alle Unterschriften dieselbe Summe. Berechnet VOR dem
  Einfügen der Unterschrift. Anzeige: gekürzt an der Unterschrift (voll im `title`), voll im PDF.
  Eine laufende Nachprüfung in der Oberfläche gibt es bewusst noch nicht; der Test
  `test_hash_covers_answers_and_photo_files` zeigt, dass eine Änderung an Datenbank oder Fotodatei
  an der Sperre vorbei die Summe verändert.
- **Zeilensperre**: schreibende Funktionen laden die Checkliste mit `with_for_update(of=Checklist)`
  + `populate_existing` (PostgreSQL; SQLite ignoriert es) -- sonst könnte eine Antwort zwischen
  Sperrprüfung und Unterschrift durchrutschen.
- **Verwerfen** (`discard_signatures()`, `POST /api/checklists/{id}/discard-signatures`,
  `require_min_role(ROLE_OFFICE_AUFTRAG)`): nur Entwurf (abgeschlossen → 409), Begründung Pflicht
  (400), ohne Unterschrift 400. Markiert statt löscht -- Bild, Name, Zeitpunkt, Prüfsumme bleiben;
  `active_attachments()` blendet verworfene überall aus (Pflichtangaben, Regel `ausgefuellt`, PDF,
  Anzeige). Eine verworfene Unterschrift ist nie löschbar. Seite: sichtbares Begründungsfeld in der
  Karte "Unterschrieben" (Regel 4), danach Karte "Verworfene Unterschriften".
- **Änderungshistorie**: `Checklist`, `ChecklistAttachment`, `ChecklistAssetRelease` in
  `AUDITED_TYPES`, eigene Bezeichnungen in `_normalize()` ("Checkliste", "Checklisten-Unterschrift",
  "Checklisten-Foto", "Gerät als repariert markiert"), `entity_id` = Checkliste, `project_id` über
  den Auftrag (erscheint in der Projektmappe). Verwerfen erscheint je Unterschrift als geänderte
  Felder, darunter "Begründung (Verwerfen)"; Abschließen als Status entwurf → abgeschlossen; die
  Notiz bei "repariert" steht im Schnappschuss (`details`). `ChecklistAnswer` bewusst NICHT (Tippen
  erzeugt alle 700 ms eine Zeile; verbindlich macht den Inhalt die Prüfsumme).
- **Oberfläche** (`checklist.html`): `can_edit` (Antworten/Fotos) getrennt von `can_sign`
  (Unterschreiben, Abschließen) und `can_discard_signatures`. Vor der ersten Unterschrift werden
  ausstehende Eingaben gespeichert (`flushAll()`, sonst käme ein verzögerter Text nach der
  Unterschrift an und würde abgewiesen) und `confirm()` nennt die Pflichtangaben, die danach nicht
  mehr ergänzbar sind; dieselben stehen danach als Warnung in der Karte "Unterschrieben".
  `operational_asset.html`: Notiz-Pflicht auch clientseitig.
- **Verifikation**: `tests/test_v317_checklist_signature_binding.py` (20 Tests), Gegenproben je
  Schutzstelle rot (Sperre aus 3 rot, Einzelunterschrift ersetzbar 1, Verwerfen für jede Rolle 1,
  ohne Begründung 4, repariert ohne Notiz 4); `test_v305` zwei Tests umgestellt. Checklisten-Tests
  v305-v308 + v317 (67) zusätzlich gegen PostgreSQL (Wegwerf-Schema in `spielwiese`) grün. Migration
  SQLite + PostgreSQL hin/zurück/hin mit Bestand, `alembic check` sauber. Klicktest
  `scripts/klicktest_checkliste_unterschrift.py` 23/23. Volle Suite mit PostgreSQL 2063 grün.

### Befund: Startvorlagen mit Feldern nach der ersten Unterschrift (nur gemeldet)
In allen 13 Startvorlagen stehen die Unterschriftsfelder am Ende; das Problem ist der Ablauf, nicht
die Reihenfolge. Konflikt, wenn die erste Unterschrift fällt, bevor alles erfasst ist:
- **Heißarbeiten mit Brandwache** (deutlich): Ende, Nachkontrolle bis, Nachkontrolle ohne Befund
  (alle Pflicht) entstehen erst nach der Arbeit; wird der Erlaubnisschein vor Beginn unterschrieben
  (üblicher Ablauf), ist die Checkliste bis zum Verwerfen durch das Büro nicht abschließbar.
- **Nachtragsmeldung**: unterschreibt der Kunde bei der Anordnung, fehlen oft noch Fotos (Pflicht,
  min. 1) und "bereits ausgeführt".
- **Entsorgungsnachweis**: Beleg-Foto (Pflicht) und Wiegeschein-Nr. kommen oft erst von der
  Annahmestelle, nach der Übergabe.
- **Sicherheitsunterweisung**: Dauer (nicht Pflicht) steht erst am Ende; Teilnehmer, die später
  unterschreiben, gehen weiterhin.
- **Tagesbericht**: nur, wenn vor Feierabend unterschrieben wird.
Ohne Konflikt: Sicherheitscheck, Gefahrstoff-Verdacht, verdeckte Arbeiten, Geräte-Sichtprüfung,
Schadensmeldung Gerät, Abfahrtkontrolle. Vorher/Nachher und Aufmaß haben keine Unterschrift, werden
also nie gesperrt und tragen keine Prüfsumme.

### Befund: Migration bestehender unterschriebener, nicht abgeschlossener Checklisten
Keine Datenänderung. Die Sperre gilt ab dem Upgrade sofort (sie hängt an der vorhandenen
Unterschrift), die Prüfsumme bleibt NULL = "vor 1.8.13 unterschrieben" (der damals unterschriebene
Inhalt ist nicht mehr bekannt, eine nachgerechnete Summe würde ihn falsch bescheinigen). Abschließen
geht, Ändern nur nach "Unterschriften verwerfen". Betroffene auf dem Server finden:
`SELECT c.id, c.template_label_snapshot FROM checklists c WHERE c.status = 'entwurf' AND EXISTS
(SELECT 1 FROM checklist_attachments a WHERE a.checklist_id = c.id AND a.kind = 'unterschrift');`

### Nebenbefunde
- **Geisterzeilen in der Änderungshistorie (mitbehoben, weil Punkt 3 sie sonst auf Checklisten
  ausgedehnt hätte)**: `collect_audit()` merkt in `before_flush` vor, `write_audit()` schreibt in
  `after_flush_postexec`. Scheiterte der Flush dazwischen (Unique-Kollision im SAVEPOINT), blieb die
  Vormerkung liegen und wurde beim nächsten Flush als "angelegt" mit `entity_id` "None"
  geschrieben. Betraf jeden protokollierten Typ mit SAVEPOINT-Muster (z. B. `SettingOptionGroup`
  beim gleichzeitigen ersten Seeding). Jetzt räumt `after_soft_rollback` die Vormerkung ab;
  Test `test_failed_flush_leaves_no_stale_history_entry`, vorher rot.
- **Benutzer löschen scheitert unter PostgreSQL**, sobald der Benutzer irgendwo per FK steht
  (15 FKs auf `app_users`, ohne `ON DELETE`; SQLite erzwingt FKs hier nicht): gegen PostgreSQL
  nachgestellt, `DELETE /api/users/{id}` für einen Benutzer mit angelegter Checkliste → 500
  (`checklists_created_by_user_id_fkey`). `discarded_by_user_id` ist ein weiterer solcher FK.
  Nicht behoben.
- **Testaufbau `world` (test_v305) läuft nur unter SQLite**: Aufträge mit erfundener
  `source_quote_id`, unter PostgreSQL FK-Verletzung. Für die PG-Probe im Wegwerf-Schema die eine
  FK entfernt. Nicht geändert.
- Vorbestehend: bei einer Einzelunterschrift mit Rollenbeschriftung "Monteur" belegt die Seite
  den Namen mit dem angemeldeten Konto vor -- auch wenn das Büro die Seite offen hat.

---

## Umsetzung 1.8.14 (30.09.2026) -- Stufe 2, Runde 2a-1b: Unterschrift versiegelt abschnittsweise

Betreibervorgabe: (1) eine Unterschrift versiegelt nur die Felder vor ihr, Felder danach bleiben bis
zur nächsten Unterschrift offen, Vorlagen mit einer Unterschrift am Ende wie bisher; (2) beim
Unterschreiben den versiegelten Inhalt als feste Kopie ablegen (Fassung, Feldschlüssel, Antworten,
Prüfsummen der Fotos), `content_sha256` = Prüfsumme genau dieser Kopie, Fotos einer Unterschrift --
auch einer verworfenen -- nie physisch löschen; (3) Seite und PDF zeigen je Unterschrift, ob der
aktuelle Inhalt noch passt; (4) Heißarbeiten in zwei Abschnitte, für Nachtragsmeldung,
Entsorgungsnachweis, Tagesbericht nur Vorschläge; (5) Angriffstests mit Gegenprobe.

- **Regel** (`sealed_field_ids()`): gesperrt sind Antworten und Fotos aller Felder oberhalb der
  untersten gültigen Unterschrift ("oberhalb" = Reihenfolge der Vorlagenfassung). Hinweise und
  Unterschriftsfelder sperren sich nicht gegenseitig: eine obere Unterschrift bleibt möglich, auch
  wenn schon eine untere geleistet ist (Teilnehmer einer Unterweisung unterschreiben weiter nach
  dem Unterweisenden). Felder nach der letzten Unterschrift werden nur durch das Abschließen
  eingefroren, ohne Prüfsumme.
- **Unterschriften von vor 1.8.14** (ohne Kopie, also 1.8.13 mit Prüfsumme über die ganze Checkliste
  oder noch ältere ohne) versiegeln weiterhin die ganze Checkliste -- so galt es beim
  Unterschreiben, und die 1.8.13-Summe bleibt nur so nachprüfbar (`_legacy_content_sha256()`).
- **Feste Kopie** (Migration `8f73789cdd66`, Spalte `checklist_attachments.sealed_content`, Text,
  nullable): `seal_content()` erzeugt kanonisches JSON (`"v": 2`, sortierte Schlüssel) mit
  Checkliste, Vorlage, Fassung (ID und Nummer), eingefrorenen Bezeichnungen, Schlüssel des
  Unterschriftsfelds und JEDEM versiegelten Feld mit Schlüssel und Wert -- auch leere, damit ein
  später ergänztes Feld auffällt --, bei Fotofeldern jedes Foto mit ID und SHA-256 der Datei.
  `content_sha256 = sha256(sealed_content)`. Bewusst eine Zeichenkette statt Zeilen (sonst gilt im
  Modul "Zeilen statt JSON"): die Prüfsumme soll über genau die abgelegten Bytes gehen, ohne dass
  sie zum Nachprüfen erst wieder serialisiert werden müssen. Nicht in der Änderungshistorie
  (`EXCLUDED_FIELDS`), dort steht die Prüfsumme.
- **Prüfung** (`check_signature()`, bei jedem Abruf, je gültige Unterschrift unter `seal`):
  `unveraendert`, `abweichend` (mit den betroffenen Feldern aus dem Vergleich Kopie ↔ aktueller
  Stand), `kopie_veraendert` (Inhalt passt, die abgelegte Kopie selbst nicht) oder
  `ohne_pruefsumme`. Den Text liefert der Server, Seite und PDF zeigen denselben. Jede Fotodatei
  wird je Abruf höchstens einmal gelesen.
- **Fotos als Nachweis** (`_photo_bound_by_signature()`): ein Foto, das in der Kopie irgendeiner
  Unterschrift steht -- auch einer verworfenen --, ist nicht löschbar (409); die Seite zeigt dafür
  kein ×. Fehlt die Kopie oder passt sie nicht zu ihrer Prüfsumme, gilt jedes Foto als gebunden,
  das beim Unterschreiben schon da war. **Lücke aus 1.8.13 mitgeschlossen**: ein Entwurf, dessen
  Unterschriften alle verworfen waren, ließ sich löschen -- samt verworfener Unterschriften und
  Fotodateien (Kaskade + `before_delete`). Jetzt 409, sobald irgendeine Unterschrift existiert.
- **API/Seite**: `sealed_field_ids`, `has_signatures`, `can_delete` (neu, "Entwurf löschen" nur
  ohne jede Unterschrift), `can_edit` = mindestens ein Feld noch offen. Die Seite sperrt je Feld,
  markiert bei teilweiser Sperre die gesperrten Felder ("· gesperrt"), der Hinweis vor dem
  Unterschreiben erscheint immer, wenn die Unterschrift neue Felder sperrt, und nennt, ob darunter
  etwas offen bleibt.
- **Startvorlage Heißarbeiten** (Daten-Migration `05a080705f2c`): Unterschrift Ausführender direkt
  nach "Beginn" (Abschnitt "Freigabe vor Arbeitsbeginn"), Ende/Nachkontrolle/Fotos darunter bis zur
  Unterschrift Brandwache (Abschnitt "Nachkontrolle"), Hilfetexte an beiden Unterschriften. Nur,
  wenn die Vorlage noch genau so ist, wie 1.8.5 sie angelegt hat (eine Fassung, Entwurf, gleiche
  Felder in gleicher Reihenfolge) -- eine veröffentlichte oder umsortierte bleibt unangetastet, dann
  im Editor umsortieren. Die Unterschriften bleiben wie in 1.8.5 ohne Pflicht (dort als
  Betreiberentscheidung vor der Veröffentlichung vermerkt).
- **Verifikation**: `tests/test_v318_checklist_signature_sections.py` (13 Tests). Angriffstests mit
  Gegenprobe (Schutz im Code ausgehebelt, Test rot, Datei danach byte-genau zurück): Feld oberhalb
  ändern (Sperre aus → rot), Feld darunter ändern (ganze Liste gesperrt wie 1.8.13 → rot), Foto einer
  verworfenen Unterschrift löschen (Bindung aus → rot; Entwurfslöschung ohne Sperre → rot), direkt in
  der Datenbank geänderte Antwort (Prüfung gegen die Kopie statt den aktuellen Stand → rot).
  `test_v317` unverändert grün bis auf den Hilfsaufruf der Prüfsumme -- belegt, dass Vorlagen mit
  der Unterschrift am Ende sich wie in 1.8.13 verhalten. Checklisten-Tests (80) zusätzlich gegen
  PostgreSQL (Wegwerf-Schemas in `spielwiese`) grün; Migrationen SQLite + PostgreSQL hin/zurück/hin
  mit Bestand (eine 1.8.13-Unterschrift), `alembic check` sauber. Klicktest
  `scripts/klicktest_checkliste_abschnitte.py` 25/25 (u. a. Antwort direkt in der Wegwerf-SQLite
  geändert → Unterschrift zeigt "weicht ab: Arbeitsbereich"), `klicktest_checkliste_unterschrift.py`
  weiter 23/23.

### Vorschläge: Nachtragsmeldung, Entsorgungsnachweis, Tagesbericht (nur gemeldet, nicht umgesetzt)
- **Nachtragsmeldung**: Abschnitt "Anordnung" (Art, Beschreibung, Menge/Einheit, angeordnet durch)
  → Unterschrift Kunde; Abschnitt "Ausführung" (geschätzter Zeitaufwand, Material, bereits
  ausgeführt, Fotos) → neue Unterschrift Monteur. Der Kunde bestätigt nur die Anordnung, Fotos und
  "bereits ausgeführt" bleiben danach ergänzbar.
- **Entsorgungsnachweis**: Abschnitt "Übergabe" (Abfallart, Menge/Einheit, Entsorger, Übergabe) →
  Unterschrift Monteur; Abschnitt "Beleg" (Wiege-/Lieferschein-Nr., Beleg-Foto, Bemerkung) → zweite
  Unterschrift ("Beleg erfasst", Monteur oder Büro). Einfachere Variante: Beleg-Felder ohne zweite
  Unterschrift unter die erste -- dann friert erst das Abschließen sie ein, ohne Prüfsumme.
- **Tagesbericht**: so lassen (eine Unterschrift am Ende, geleistet bei Feierabend). Eine
  Gegenzeichnung der Anordnungen durch den Auftraggeber bräuchte die Anordnungen ganz oben und
  würde alles darüber sperren -- passt nicht zu einem Bericht, der über den Tag wächst.

### Offene Punkte (nur gemeldet)
- ~~**Verwerfen wirft alle gültigen Unterschriften**~~ -- seit 1.8.15 je gewählter Unterschrift, siehe
  "Umsetzung 1.8.15".
- **Ein Entwurf mit verworfenen Unterschriften ist nicht mehr löschbar**: er bleibt als Entwurf
  stehen, bis er abgeschlossen wird (Folge aus Punkt 2 der Vorgabe).

---

## Umsetzung 1.8.15 (30.09.2026) -- Stufe 2, Runde 2a-1c: Verwerfen je Unterschrift, Abschluss mit Prüfsumme

Betreibervorgabe: (1) Verwerfen wählt eine Unterschrift, verworfen werden sie und alle Unterschriften
in Feldern, die in der Vorlage nach ihrem Feld stehen, Unterschriften im selben Feld bleiben,
Begründung weiter Pflicht; (2) Abschließen legt wie eine Unterschrift eine feste Kopie aller Felder mit
Prüfsumme an, Seite und PDF zeigen "Inhalt unverändert" oder "weicht ab", Bestand ohne Kopie bleibt
ohne Prüfsumme; (3) Nachtragsmeldung und Entsorgungsnachweis wie Heißarbeiten nur als unveränderter
Entwurf umbauen; (4) Angriffstests mit Gegenprobe (Brandwache verwerfen → Nachkontrolle änderbar,
Freigabe gesperrt; Freigabe verwerfen → Brandwache fällt mit; ein Teilnehmer der Unterweisung → die
anderen bleiben).

- **Verwerfen** (`discard_signatures(…, signature_id=…)`, `signatures_discarded_with()`): die gewählte
  gültige Unterschrift plus jede gültige Unterschrift in einem Feld mit höherer Position in der
  Fassung. Begründung: die Kopie einer unteren Unterschrift enthält den Inhalt, den die obere gesperrt
  hat -- nach einer Korrektur passte sie nicht mehr. Prüfreihenfolge: Entwurf (409), Begründung (400),
  überhaupt eine gültige Unterschrift (400), Auswahl vorhanden (400), Unterschrift gehört zu DIESER
  Checkliste und ist eine Unterschrift (404, auch für ein Foto), nicht schon verworfen (400). Was danach
  gesperrt bleibt, ergibt sich wie bisher aus `sealed_field_ids()` der verbleibenden Unterschriften.
  Eine Unterschrift ohne Kopie (vor 1.8.14) versiegelt weiterhin alles -- liegt sie oberhalb der
  verworfenen, bleibt die Checkliste gesperrt, bis auch sie verworfen ist.
- **API/Seite**: `ChecklistDiscardSignaturesWrite.signature_id` (Pflicht, in der Geschäftslogik geprüft,
  400 mit Text statt 422); je gültige Unterschrift `discards_with` (IDs, die mitfallen). Karte
  "Unterschrieben": Auswahlfeld "Unterschrift verwerfen" (Vorlagenreihenfolge, "Feld: Name
  (Zeitpunkt)"), darunter sofort "Mit verworfen werden (Felder darunter): …" bzw. "Nur diese
  Unterschrift.", Begründung, Knopf; `confirm()` wiederholt beides (Regel 4: Eingaben sichtbar, kein
  Popup).
- **Abschluss mit Kopie** (Migration `af9cd6b4e543`, `checklists.sealed_content` Text +
  `content_sha256` String 64, beide nullable): `completion_content()` = derselbe Kopf wie eine
  Unterschrift (`_content_head()`, `"v": 2`) mit `"sealed_by": "abschluss"` und ALLEN Feldern außer
  Hinweisen, **einschließlich der Unterschriftsfelder** (je gültige Unterschrift ID, Name, Zeitpunkt,
  ihre Prüfsumme, SHA-256 der Bilddatei) -- "aller Felder" wörtlich genommen; damit fällt auch ein
  geänderter Name oder ein ausgetauschtes Unterschriftsbild auf, was keine Unterschrift selbst abdeckt.
  Die Unterschriften-Kopien sind unverändert byte-gleich (`seal_content()` nur in Kopf und Feldeinträge
  zerlegt). Spalten an `checklists` statt einer 1:1-Zusatztabelle: die "keine neuen Spalten"-Regel aus
  "Zuschnitt für Stufe 2" gilt für Fachdaten einzelner `purpose`s, der Abschluss ist Kern jeder
  Checkliste. `sealed_content` ist wie an der Unterschrift aus der Änderungshistorie ausgenommen
  (`EXCLUDED_FIELDS` gilt je Spaltenname), die Prüfsumme steht darin.
- **Prüfung** (`check_completion()`, gleiche Vergleichslogik `_compare()` wie `check_signature()`):
  `unveraendert` | `abweichend` (Felder) | `kopie_veraendert` | `ohne_pruefsumme` ("Ohne Prüfsumme
  abgeschlossen (älterer Stand) – nicht prüfbar."). API `completion_seal`/`completion_sha256`, Seite
  im Kopf ("Abschluss: …", Prüfsumme gekürzt, voll im `title`), PDF am Ende ein Block "Abschluss" mit
  voller Prüfsumme und Urteil (Abweichung fett). Ein Entwurf hat keinen. Fotos und Unterschriftsbilder
  werden je Abruf höchstens einmal gelesen (gemeinsamer Cache mit den Unterschriften).
- **Startvorlagen** (Daten-Migration `803d94127c12`, Muster `05a080705f2c`, nur wenn noch genau so wie
  1.8.5 angelegt: eine Fassung, Entwurf, gleiche Felder in gleicher Reihenfolge):
  - Nachtragsmeldung: Hinweise oben ohne Abschnitt; "Anordnung" (Art, Beschreibung, Menge, Einheit,
    angeordnet durch) → Unterschrift Kunde; "Ausführung" (geschätzter Zeitaufwand, Material, bereits
    ausgeführt, Fotos) → neue Unterschrift Monteur. Zeitaufwand und Material stehen wie im Vorschlag
    aus 1.8.14 unter "Ausführung" -- der Kunde bestätigt nur die Anordnung, keine Schätzung (passt zum
    Hinweis "keine Preis- oder Terminzusage").
  - Entsorgungsnachweis: "Übergabe" (Abfallart, Menge, Einheit, Entsorger, Übergabe) → Unterschrift
    Monteur; "Beleg" (Wiege-/Lieferschein-Nr., Foto des Belegs, Bemerkung) → neue Unterschrift "Beleg
    erfasst" (Rollenbeschriftung "Monteur/Büro", der Name wird wie bei "Monteur" mit dem angemeldeten
    Konto vorbelegt). Die Bemerkung bleibt wie im Vorschlag unter "Beleg" -- Folge: bei Abfallart
    "Sonstiges (in der Bemerkung angeben)" ist die Abfallart mit der Übergabe versiegelt, die Erklärung
    kommt erst im Abschnitt Beleg. Vor der Veröffentlichung ggf. Bemerkung nach oben ziehen.
  - Beide neuen Unterschriften ohne Pflicht (wie alle Startvorlagen-Unterschriften, Entscheidung vor der
    Veröffentlichung), mit Hilfetexten an beiden Unterschriften jeder Vorlage.
  - `downgrade()` nur, solange die Vorlage genau der neuen Form entspricht und keine Regel die neue
    Unterschrift verwendet; entfernt dann die neue Unterschrift und die gesetzten Abschnitte/Hilfetexte.
- **Verifikation**: `tests/test_v319_checklist_discard_and_completion.py` (14 Tests, mit den echten
  Startvorlagen Heißarbeiten und Sicherheitsunterweisung). Gegenproben (Schutz im Code ausgehebelt,
  Test rot, Datei danach byte-genau zurück): Verwerfen trifft alle (Brandwache-Test rot -- am Angriff
  selbst, die Monteurin ändert die Freigabe mit 200; Teilnehmer-Test rot), nur die gewählte (Freigabe-
  und Teilnehmer-Test rot), selbes Feld fällt mit (Teilnehmer-Test rot), fremde Unterschrift über
  `db.get` statt aus der Checkliste (rot), Abschluss gegen die eigene Kopie statt den aktuellen Stand
  (rot), Abschluss ohne Unterschriften (rot). `test_v317`/`test_v318`: Verwerfen mit `signature_id`,
  PDF-Zählungen um die Abschluss-Zeile erhöht. Checklisten-Tests (128) zusätzlich gegen PostgreSQL grün
  (Wegwerf-Schema je Test in `spielwiese`, danach entfernt). Migrationen SQLite + PostgreSQL
  hin/zurück/hin mit Bestand (veröffentlichter Entsorgungsnachweis blieb unangetastet, abgeschlossene
  Checkliste ohne Prüfsumme), `alembic check` sauber. Klicktest `scripts/klicktest_checkliste_verwerfen.py`
  23/23 (u. a. Name der Brandwache direkt in der Wegwerf-SQLite geändert → Abschluss "weicht ab:
  Unterschrift Brandwache", beide Unterschriften unverändert; Warnfarbe hell und dunkel); die beiden
  älteren Klicktests auf die Auswahl umgestellt, 24/24 und 25/25. Volle Suite mit PostgreSQL 2090 grün.

### Nebenbefunde (nur gemeldet)
- **Klicktests laufen im Farbschema des Rechners**: `scripts/cdp_klicktest.py` emuliert kein
  `prefers-color-scheme`, Headless-Chrome übernimmt die Windows-Einstellung (hier dunkel). Ohne
  ausdrücklich gesetztes `erp_theme` prüfen die Klicktests also nur einen der beiden Modi, je nach
  Rechner. Der neue Klicktest setzt beide ausdrücklich.
- **Kein wiederverwendbarer PostgreSQL-Schalter für die Suite**: jede Runde baut die PG-Probe der
  Checklisten-Tests neu (diesmal ein Scratchpad-Plugin, das `sqlite:///:memory:` durch ein
  Wegwerf-Schema ersetzt und `orders.source_quote_id` wegen des `world`-Aufbaus ohne FK anlegt). Ein
  fester Schalter in `tests/conftest.py` würde das vereinheitlichen.

---

## Umsetzung 1.8.16 (30.09.2026) -- Stufe 2, Runde 2a-2: Zweck, Systemfelder, Folgetabelle

Betreibervorgabe: (1) Zweck-Registry im Code -- allgemein, abnahme, behinderungsanzeige,
bedenkenanzeige; je Zweck erlaubte Kontexte (die drei nur am Auftrag) und Systemfelder (Schlüssel,
Typ), die drei vorerst ohne Systemfelder, für die Tests ein Test-Zweck mit Systemfeldern; (2) Zweck
im Editor setzbar, beim Veröffentlichen an der Fassung eingefroren, Checklisten nutzen den Zweck ihrer
Fassung; (3) Veröffentlichen prüft die Systemfelder; an Systemfeldern Schlüssel, Typ, required,
allow_na, multiple, min_count und Optionen nicht änderbar, nicht löschbar; Kopie erbt Zweck und
Systemfelder; Vorlagen mit Zweck nur archivieren; (4) Start-Auswahl beachtet Zweck und Kontext;
(5) Folgetabelle (Checkliste, Folgeschlüssel, Ziel), eindeutig, mit Nachholen wie bei den Regeln, nur
eine Test-Folge; (6) Tests mit Gegenprobe.

- **Registry** (`app/checklist_purposes.py`): `ChecklistPurpose(key, label, contexts, system_fields,
  follow_ups)`, `SystemField(key, field_type, label, required, allow_na, multiple, min_count,
  options)`, `FollowUp(key, label, handler, module)`. `PURPOSES` ist ein gewöhnliches Dict -- Tests
  tragen ihren Zweck per `monkeypatch.setitem` ein. Kein Import aus `checklist_templates` (das
  importiert von hier). Der Test `test_every_registered_purpose_is_consistent` prüft jede Vorgabe
  (Typ, Schlüsselmuster, Optionen genau bei Auswahl, feste Eigenschaften überstehen
  `_normalize_field()`) -- Wächter für 2b/2c.
- **Festlegung: Zweck an der Vorlage, ab der ersten Veröffentlichung fest.** `ChecklistTemplate.purpose`
  (seit 1.8.0 vorhanden) ist der Wert im Editor; neue Spalte `checklist_template_versions.purpose`
  (Migration `b3a6e4cb70fc`, übernimmt beim Upgrade den Zweck der Vorlage in jede Fassung) wird beim
  Veröffentlichen gesetzt und bei Entwürfen mitgeführt. Geändert werden kann der Zweck nur, solange die
  Vorlage nie veröffentlicht wurde (`purpose_locked`); danach 400 mit dem Hinweis, die Vorlage zu
  kopieren. Abgewogen gegen "Zweck je Entwurf frei": dann könnte Fassung 2 einer Abnahme still
  "allgemein" werden und keine Folgen mehr auslösen, und Systemfelder müssten beim Wechsel mitten in
  einer Fassungskette umgedeutet werden. Eine Kopie ist nie veröffentlicht, dort ist der Zweck wieder
  frei -- das ist der Weg für einen falsch gewählten Zweck.
- **Kontexte**: `_apply_template_meta()` lehnt Kontexte ab, die der Zweck nicht erlaubt (auch beim
  Wechsel des Zwecks im selben Speichern); Veröffentlichen prüft es erneut. Ein unbekannter Zweck (aus
  der Registry entfernt) sperrt die Verwaltungsdaten nicht, ist aber nicht startbar.
- **Systemfelder** (`_sync_system_fields()`): legt fehlende am Ende an, setzt feste Eigenschaften und
  Optionen auf die Vorgabe, übernimmt ein gleichnamiges gewöhnliches Feld desselben Typs; ein Feld mit
  dem Schlüssel, aber anderem Typ → Fehler, bevor sich etwas ändert. Systemfelder, die der Zweck nicht
  (mehr) kennt, werden gewöhnliche Felder (Wechsel zurück auf "allgemein"). Aufgerufen beim Setzen des
  Zwecks, beim Anlegen einer Vorlage mit Zweck, beim neuen Entwurf und bei der Kopie (dort im SAVEPOINT;
  scheitert es, bleibt die reine Kopie und der Editor nennt das Problem) und über "Systemfelder
  angleichen" (`POST /api/checklist-template-versions/{id}/system-fields`). Veröffentlichen gleicht
  bewusst NICHT an, es prüft nur (`system_field_problems()`: fehlt / weicht ab: Eigenschaft, Optionen)
  -- sonst gäbe es die geforderte Ablehnung nie.
- **Schutz**: `update_field()` lehnt eine Änderung an `SYSTEM_LOCKED_ATTRIBUTES` ab, der unveränderte
  Wert darf mitkommen (der Editor schickt ganze Formulare, gesperrte Eingaben aber gar nicht).
  Optionen eines Systemfelds: kein Anlegen, Umbenennen, Löschen ("Optionen nicht änderbar" wörtlich,
  auch die Beschriftung). `delete_template()`: Zweck ungleich "allgemein" an Vorlage oder einer
  Fassung → nur archivieren.
- **Checklisten**: `list_startable_templates()` filtert zusätzlich nach dem Zweck der veröffentlichten
  Fassung, `create_checklist()` prüft ihn (Gegenprobe: mit dem Zweck der Vorlage statt der Fassung rot).
  Liste und Einzelabruf tragen `purpose`/`purpose_label` der Fassung.
- **Folgetabelle** `checklist_follow_ups` (`checklist_id`, `follow_up_key`, `target_type`/`target_id`
  = Ziel, `status`, `executed_at`, unique `(checklist_id, follow_up_key)`), Ablauf in
  `app/checklist_follow_ups.py` nach dem Muster der Regeln (Belegen per Unique + SAVEPOINT, Nachholen
  per bedingtem UPDATE, `modul_aus`, wenn die Folge ein ausgeschaltetes Modul braucht). Abweichung zu
  den Regeln: ein Fehler im Handler wird je Folge abgefangen (Rollback, Protokoll nur Schlüssel, ID,
  Klassenname -- Regel 18), die Folge bleibt `ausstehend`, die übrigen laufen weiter. Aufruf in
  `complete_checklist()` nach den Regeln. Büro-Endpunkte `GET /api/checklists/{id}/follow-ups`,
  `POST …/run-follow-ups`, `POST /api/checklists/run-open-follow-ups`; Monteure 403, im
  Checklisten-Abruf nie enthalten.
- **Oberfläche**: Editor mit Zweck-Auswahl (sperrt unpassende Kontexte, Rückfrage beim Wechsel, nach der
  ersten Veröffentlichung gesperrt), Kennzeichen im Kopf, "Löschen" nur ohne Zweck, an Systemfeldern die
  festen Eingaben gesperrt, Optionen ohne ×/+, Hinweis mit "Systemfelder angleichen". Vorlagenliste mit
  Zweck-Kennzeichen. Für Folgen noch keine Anzeige -- kommt mit der ersten echten Folge (2b/2c), deren
  Ziel fachlich dargestellt werden will.
- **Verifikation**: `tests/test_v320_checklist_purposes.py` (16 Tests). Gegenproben (Schutz im Code
  ausgehebelt, Test rot, Datei byte-genau zurück), alle 12 rot: feste Eigenschaft änderbar, Systemfeld
  löschbar, Optionen änderbar, Veröffentlichen ohne Systemfeld-Prüfung, Zweck nach Veröffentlichen
  änderbar, Start-Auswahl nach dem Zweck der Vorlage, Anlegen ohne Kontextprüfung, Vorlage mit Zweck
  löschbar, erledigte Folge erneut ausgeführt, Belegung ohne Unique-Schutz, Unique-Constraint fehlt,
  Folgen im Monteur-Abruf. Die letzte blieb zuerst grün: nur das Dict zu erweitern reicht nicht, das
  Antwortschema `ChecklistOut` filtert unbekannte Schlüssel -- ein echtes Leck bräuchte beides, die
  Gegenprobe erweitert deshalb Dict UND Schema (dann rot). Der Monteur-Test scannt die Antworten von
  Abschluss, Einzelabruf, Start-Auswahl, Liste und "meine" rekursiv auf Büro-Schlüssel und auf den
  Text der Folge- und Regel-Aufgabe. Checklisten-Tests (144) zusätzlich gegen PostgreSQL grün
  (Wegwerf-Schema je Test in `spielwiese`); Migration SQLite + PostgreSQL hin/zurück/hin mit Bestand
  (13 Startvorlagen, eine davon vorher auf Zweck `abnahme` gesetzt -- Übernahme belegt), `alembic
  check` sauber. Klicktest `scripts/klicktest_checkliste_zweck.py` 28/28 (Systemfelder dort im Befüllen
  direkt markiert, die Instanz läuft in einem eigenen Prozess ohne Test-Zweck). Volle Suite mit
  PostgreSQL 2106 grün.

### Nebenbefunde (nur gemeldet)
- ~~**Regel-Protokoll enthält Ausnahmetext**~~ -- seit 1.8.17 nur ID und Klassenname, mit Test (siehe
  `docs/archiv/versandprotokoll-und-ablage.md`).
- **Folgen sollten selbst idempotent sein**: wie bei den Regeln bleibt ein Restrisiko, wenn der
  Prozess GENAU zwischen Handler und Vermerk abbricht -- Nachholen führt ihn dann erneut aus. Für 2b/2c
  empfohlen: Fachdaten in 1:1-Zusatztabellen mit eindeutiger `checklist_id` (siehe "Zuschnitt für
  Stufe 2"), der Handler findet dann seinen eigenen früheren Datensatz.
- **Regiebericht** stand im ursprünglichen Zuschnitt, nicht in der Vorgabe dieser Runde -- nicht in der
  Registry.
- **Klicktest-Falle**: `localStorage.setItem('erp_theme', …)` vor dem ersten `tab.oeffnen()` läuft auf
  `about:blank` ins Leere, und der Fehler geht verloren, weil `oeffnen()` `tab.fehler` zurücksetzt --
  der erste Screenshot war dadurch still im Farbschema des Rechners. Im neuen Klicktest nach dem ersten
  Laden gesetzt und ausdrücklich geprüft.
- **Selbst verursacht, vor dem Commit behoben**: die Patch-Skripte dieser Runde schrieben unter Windows
  im Textmodus und stellten fünf Dateien auf CRLF um; wieder auf LF gebracht (Git hätte es beim Commit
  wegen `core.autocrlf` ohnehin normalisiert, die Arbeitskopie wäre aber abgewichen).

---

## Nachtrag 1.8.34 (01.10.2026) -- gemeinsame Zeichenfläche

Die Unterschrift der Checkliste zeichnet seit 1.8.34 über `app/templates/_unterschrift.html`
(`unterschriftsfeld()`), gemeinsam mit Einsatzbericht und Vertrag (Stufe 2b, siehe
`docs/archiv/vertragsgrundlage-und-vertrag.md`, "Umsetzung 1.8.34"). `setupPad()`/`clearPad()` in
`checklist.html` sind nur noch Hüllen; IDs `pad_…`/`padName_…` und die Knöpfe sind unverändert, die drei
Checklisten-Klicktests laufen ohne Änderung. Verhalten wie bisher (Fläche weiß, Strich #111, Geräteauflösung,
PNG mit durchsichtigem Hintergrund); Serverseite unverändert.

---

## Nachtrag 1.8.38 (02.10.2026) -- erste echte Systemfelder und Folge (Behinderungsanzeige)

Herleitung und Festlegungen: `docs/archiv/vertragsgrundlage-und-vertrag.md`, "Umsetzung 1.8.38". Was sich am Baukasten
geändert hat und für jeden künftigen Zweck (Abnahme, Bedenkenanzeige) gilt:
- `SystemField.section` -- Abschnitt; das Veröffentlichen prüft die Reihenfolge der Abschnitte, jede Unterschrift am
  Ende ihres Abschnitts (`section_order_problem()`). Die Aussage "Reihenfolge frei" aus 1.8.16 gilt nur noch innerhalb
  eines Abschnitts.
- `SystemField.office_only` -- nur das Büro füllt aus und unterschreibt (Router 403 für Monteure, auch an der eigenen
  Checkliste); `option_hints` -- Hinweis beim Wählen einer Option.
- `FollowUp.after_signature` -- Folge nach der Unterschrift in diesem Systemfeld statt nach dem Abschluss, nachholbar auch
  am Entwurf; die Ausfüllseite zeigt dem Büro die Karte "Folgen", "Alle nachholen" der Übersicht nimmt Folgen mit.
- Regeln: `link_purpose` ("Aufgabe verlinkt auf") -- Aufgabe verlinkt aufs Anlegen einer Checkliste mit Zweck am selben
  Auftrag, keine zweite, solange eine mit demselben Link offen ist (`aufgabe_vorhanden`).
