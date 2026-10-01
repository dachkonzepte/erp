# Speichern übernimmt nur gesendete Felder (seit 1.8.25)

Vor jeder Änderung an einem PUT/PATCH-Endpunkt oder an einer Speichern-Funktion der Oberfläche diese
Datei lesen (Regel 14, Regel 22).

## Die Fehlerklasse

Ein Update-Schema hat Felder mit Vorgabewert (`notes: str | None = None`, `break_minutes: int = 0`).
Schickt ein Aufrufer ein Feld nicht mit, setzt Pydantic den Vorgabewert ein. Liest der Handler dann
`payload.feld` oder `payload.model_dump()`, speichert er den Vorgabewert über den gespeicherten Wert.
Niemand sieht einen Fehler, der Wert ist einfach weg. Erster Fall: `internal_note` am Angebot (1.8.23).
Der Sweep 1.8.24 fand sechs weitere, je mit einer Oberfläche, die das Feld weglässt:

| Endpunkt | Oberfläche | verloren |
|---|---|---|
| `PUT /api/properties/{id}` | Kundenseite, Objekt bearbeiten | Zugangshinweise, Ansprechpartner vor Ort |
| `PUT /api/tasks/{id}` | Aufgaben-Editor | `min_visible_role` (Finanz-Aufgabe für jedes Büro-Konto sichtbar) |
| `PUT /api/time-entries/{id}`, `PUT /api/time-entry-groups/{id}` | mobile Zeiterfassung, Ändern | Pause (durch Standard ersetzt), LV-Position |
| `PUT /api/settings/general` | Einstellungen | Logohöhe beim Stammdaten-Speichern; beim Logohöhe-Speichern alle Stammdaten (gemerkter Stand vom Laden der Seite) |
| `PUT /api/invoices/{id}` | Rechnung, Pauschale speichern | Schlusstext 2 |
| `PUT /api/services/{id}/calculation` | Leistungsformular | interne Kalkulationsnotiz |

## Umsetzung

- **`PartialUpdate`** (`app/schemas.py`): Basisklasse für Teil-Update-Schemas. Jedes Feld darf fehlen,
  der Handler nimmt `payload.model_dump(exclude_unset=True)`. Felder in `NOT_NULL` dürfen fehlen, aber
  nicht ausdrücklich `null` sein (NOT-NULL-Spalte, sonst 422). Ein ausdrückliches `null` in einem
  nullbaren Feld leert es weiterhin.
- **Geschäftsfunktionen** `update_task()` und `update_invoice_header()` nehmen `**changes` und ändern
  nur die übergebenen Felder; ein unbekannter Schlüssel ist ein `TypeError`.
- **Zeitbuchungen**: `_merge_time_changes()` (`app/routers/time_tracking.py`) legt die gesendeten Werte
  über die gespeicherten, alle Prüfungen (Pflicht-LV-Position, buchbarer Auftrag, Sperrdatum) laufen
  auf dem Ergebnis. Wechselt der Auftrag ohne neue LV-Position, entfällt die alte (sie gehört zum
  alten Auftrag, `validate_order_item()` würde sie ablehnen). Fehlt `employee_id`, bleibt der
  Mitarbeiter der Buchung -- vorher setzte der Server dann den des angemeldeten Kontos ein.
- **Oberflächen schicken nur, was sie bearbeiten**: mobile Zeiterfassung beim Ändern ohne Pause und
  Mitarbeiter (beim Anlegen weiter mit Standardpause), Backoffice-Korrektur ohne Pause und Mitarbeiter,
  "Logohöhe übernehmen" nur die Höhe, "Pauschale speichern" nur Bezeichnung und Betrag, "Texte
  speichern" der Rechnung nur die drei Texte, Leistungsformular ohne `material_overrides: []`.

## Tests

- `tests/test_v329_teil_updates.py`: je Oberfläche liest `ui_keys()` die Schlüssel des geschickten
  Objektliterals aus der Vorlage (Funktion suchen, Klammern zählen, Zeichenketten und Kommentare
  überspringen, mit Selbsttest) und schickt genau diese Schlüssel. Ein Schlüssel ohne Testwert ist rot,
  die Schlüsselmenge je Oberfläche steht fest. Gegenproben: alter Server 13 von 18 rot; alte Oberfläche
  7 von 18 rot, und auf Datenebene verliert die alte Oberfläche auch beim neuen Server die Pause
  (Einzel- und Kolonnenbuchung) und beim Logohöhe-Speichern die Stammdaten.
- `tests/test_v329_update_handler_struktur.py` (Dauertest, Regel 22): jede PUT/PATCH-Route aus
  `app.main`, Handler-Quelltext per AST. Hat das Schema Felder mit Vorgabewert, darf der Handler den
  Payload nur über `model_dump(exclude_unset=True)`, `model_fields_set`, Pflichtfelder oder unter einer
  Bedingung lesen, die das Feld selbst prüft. Funde: `payload.<Feld mit Vorgabe>`, `model_dump()` ohne
  `exclude_unset`, Payload als Ganzes weitergegeben. Grenze der Suche: sie sieht nicht in die
  aufgerufene Geschäftsfunktion -- behandelt die None als "unverändert", ist das kein Verstoß, der
  Test meldet es trotzdem. Gegenprobe gegen den alten Code: genau die sieben Routen.
- `scripts/klicktest_teil_updates.py`: Monteur ändert Buchung und Kolonnenbuchung, Admin speichert
  Stammdaten und Logohöhe im Wechsel, Pauschale, Leistung. 9/9, mit altem Code 2/9.

## Die eingefrorene Liste (BEKANNT im Strukturtest)

Beim Einführen fand der Test 77 weitere Handler. Ein Agent hat alle 117 PUT/PATCH-Routen samt
Geschäftsfunktion und jedem Aufrufer in den Vorlagen durchgesehen (01.10.2026):

- **69 übernehmen nicht gesendete Felder**, aber jede Oberfläche schickt dort heute alle Felder -- kein
  Datenverlust, solange kein neuer Aufrufer ein Feld weglässt. Davon 6 absichtlich ("Weglassen heißt
  leeren"): Checklisten-Antwort, Dashboard-Layout, Standard-Prüfvorlage je Dachtyp, Betriebskosten des
  Betriebsmittels, Position in der Dachskizze, Sperrdatum der Zeiterfassung. `PUT
  /api/maintenance-contract-items/{id}` hat keinen Aufrufer.
- **8 sind kein Verstoß**, die Geschäftsfunktion behandelt None als "unverändert"; der Test sieht das
  nicht.

Die Liste darf nur kürzer werden; ein Eintrag ohne Fund ist rot. Abbau: Teil-Update wie oben, oder
alle Felder zu Pflichtfeldern machen (fehlt eins, 422 statt stillem Leeren) -- dann aber jeden
Aufrufer und jeden Test prüfen, der heute Felder weglässt.

## Nebenbefunde der Durchsicht (nur gemeldet)

Keine Weglassung, aber die Oberfläche schickt einen Wert, den niemand bearbeitet hat:

1. Fest verdrahtet in `work_preparation.html`: `saveEmployee` schickt immer `planned_hours:null`,
   `saveMaterial` immer `supplier:null` (leert bei Altzeilen ohne Lieferanten-Datensatz den
   Freitext-Lieferanten), `saveTask` immer `sort_order:100`.
2. Auswahllisten, die den gespeicherten Wert nicht anzeigen können -- Speichern schreibt dann leer
   oder einen Vorgabewert: `order.html` Sachbearbeiter/Projektleiter (nur aktive Mitarbeiter),
   `maintenance_contract.html` Verantwortlicher (Server prüft nicht auf aktiv), Einstellungen
   Wartungen Standard-Verantwortlicher, `work_preparation.html` Aufgaben-Zuständiger,
   `master_data_form.html` Ressourcenart (nur aktive Arten), `quote_editor.html` `fillTextSelect`
   (wählt bei leerem Text die Vorgabe vor, das nächste Speichern schreibt sie). Nicht vollständig
   gesucht.
3. Gemerkte Werte für nicht bearbeitete Felder (nur veraltet, wenn der Datensatz nach dem Laden
   anderswo geändert wurde): `order.html` `quickItem`, `quote_editor.html` `saveInlineField`,
   Drag-and-drop-Layout und `saveCalc` (price_basis), `planning.html` `dropSlot`, `settings.html`
   `toggleDocumentLayoutBlock`/`saveContinuationHeaderPosition`/`saveEmailTemplate` (Mahnstufe),
   `incoming_invoices.html` `markPaidNow`, `recurring_costs.html` `toggleActive`.
4. `app/document_layout.py::update_layout_block()` nimmt `content` an, schreibt ihn aber nie.
5. `EmployeeAbsenceUpdate` (1.5.4) erlaubt `null` für `start_date`/`end_date`/`employee_id`, die Spalten
   sind NOT NULL -- ein ausdrückliches `null` endet als 500 statt 422 (heute ruft keine Oberfläche den
   Endpunkt auf).
