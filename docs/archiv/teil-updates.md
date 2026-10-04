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

Beim Einführen fand der Test 77 weitere Handler (seit 1.8.29 noch 74, seit 1.8.32 noch 73, seit 1.8.46 noch 72: die Dachfläche, siehe unten). Ein Agent hat alle 117 PUT/PATCH-Routen samt
Geschäftsfunktion und jedem Aufrufer in den Vorlagen durchgesehen (01.10.2026):

- **69 übernehmen nicht gesendete Felder** (seit 1.8.29 noch 66: die drei der Arbeitsvorbereitung sind
  Teil-Updates, siehe Nebenbefund 1; seit 1.8.32 noch 65: der Auftragskopf, siehe unten; seit 1.8.46 noch 64: die Dachfläche, `docs/archiv/abnahme-und-gewaehrleistung.md`), aber jede Oberfläche schickt dort heute alle Felder -- kein
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
   Freitext-Lieferanten), `saveTask` immer `sort_order:100`. **Behoben seit 1.8.29**: die Seite schickt
   nur, was sie bearbeitet (auch beim Anlegen keine Vorgabewerte mehr), die drei PUT-Endpunkte
   (`/api/work-preparation/employees|materials|tasks/{id}`) sind Teil-Updates und aus `BEKANNT` gestrichen.
   Die Lieferanten-Auswahl zeigt einen Freitext-Lieferanten als vorgewählte Option "<Name> (Freitext)";
   bleibt sie gewählt, geht kein `supplier_id` mit und der Freitext bleibt. "— kein Lieferant —" schickt
   `supplier_id: null` und leert Verknüpfung und Freitext; nur `supplier` (ohne `supplier_id`) setzt den
   Freitext und löst eine Verknüpfung, wie bisher. `tests/test_v332_arbeitsvorbereitung_teil_updates.py`
   (Schlüssel aus der Vorlage, Gegenprobe: alter Stand 7 von 13 rot, neuer Server mit alter Oberfläche
   5 von 13), `scripts/klicktest_arbeitsvorbereitung.py` 6/6, mit altem Stand 2/6.
2. **Behoben seit 1.8.30**, siehe "Auswahllisten mit inaktivem gespeichertem Wert" unten.
   Auswahllisten, die den gespeicherten Wert nicht anzeigen können -- Speichern schreibt dann leer
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

## Auswahllisten mit inaktivem gespeichertem Wert (seit 1.8.30)

Nebenbefund 2 oben, behoben. Ein Agent hat alle Auswahllisten der Vorlagen durchgesehen (01.10.2026).
Gemeinsame Stelle: `auswahlOptionen(eintraege, gespeichert, beschriftung, opt)` in
`app/templates/_auswahl.html` (per `{% include %}` eingebunden). Neu angeboten werden nur aktive Einträge,
der gespeicherte bleibt vorgewählt, ein inaktiver mit " (inaktiv)". Liefert die Quelle ihn gar nicht,
erscheint er trotzdem (`opt.fehlt` oder "(nicht mehr verfügbar)"). Wo die Quelle inaktive Einträge
wegließ, lädt die Seite sie jetzt mit (`include_archived`/`include_inactive`).

Umgestellt, mit dem, was vorher beim Speichern geschah:

| Seite | Feld | vorher |
|---|---|---|
| Auftrag | Sachbearbeiter, Projektleiter | leer gespeichert; Server lehnte inaktiv auch unverändert ab (422) |
| Auftrag | Einheit der Position | behalten, jetzt gekennzeichnet |
| Wartungsvertrag | Verantwortlicher; Mustervorgang (archiviert) | leer gespeichert |
| Einstellungen | Wartungen: Standard-Verantwortlicher | leer gespeichert |
| Einstellungen | Schichttyp: Dachtyp | wurde "gilt für jeden Dachtyp" |
| Aufgaben-Editor | Zuständig; Projekt (archiviert) | Aufgabe landete in "Ohne Zuständigkeit" bzw. ohne Projekt |
| Arbeitsvorbereitung | Aufgabe: Zuständig | leer gespeichert (Server lehnte inaktiv ab) |
| Arbeitsvorbereitung | Material: Lieferant | Server 422, die Zeile ließ sich gar nicht mehr speichern |
| Stammdaten-Formular | Ressource: Ressourcenart | wurde der erste Eintrag |
| Betriebsmittel | Ressourcenbezug | fehlte, Speichern blockiert |
| Kunde | Standard-Zahlungsbedingung (archiviert) | wurde Systemstandard |
| Kunde, Projektmappe | Dokument- und Projektkategorie | behalten, jetzt gekennzeichnet |
| Leistungsformular | Leistungsart | wurde "nicht klassifiziert" |
| Dachfläche | Dachtyp, Eindeckung, Bauteiltyp, Einheit, Ausführung einer Schicht | leer gespeichert |
| Prüfvorlage | Bauteiltyp | jedes Verlassen der Zeile leerte ihn |
| Zeiterfassung Büro, Backoffice | Zeitart, Tätigkeit beim Bearbeiten | Zeitart leer, Tätigkeit null |
| Zeiterfassung mobil | Tätigkeit; Kolonnenbuchung: Zeitart, Tätigkeit | Tätigkeit null, Zeitart wurde die erste |
| Zeiterfassung Backoffice | Standard-Arbeitszeitmodell; Modell je Mitarbeiter (Anzeige) | leer bzw. erstes Modell angezeigt |
| Kalender | Besitzer eines Termins (deaktiviertes Konto) | wurde still das erste Konto, danach Outlook-Push |
| Eingangsrechnungen | Lieferant, Konto; Projekt (archiviert) | behalten bzw. Projekt leer gespeichert |
| Plantafel | Team | behalten, jetzt gekennzeichnet |

Server, nur ein neu gewählter Wert muss aktiv sein: `app/orders.py::_validate_employees()` (Sachbearbeiter,
Projektleiter), `app/routers/quotes.py` (Sachbearbeiter am Angebot -- der Editor zeigte ihn schon
"nicht mehr verfügbar", das Speichern scheiterte), `app/employees.py::apply_employee_payload()` (Funktion,
steht in `EmployeeProfile.function_id`), `app/routers/work_preparation.py` (Zuständiger, Lieferant).

Bewusst nicht geändert: Teambesetzung im Stammdaten-Formular (Häkchenliste, behält schon); mobile
Zeitart-Kacheln (Wert bleibt, keine Kachel markiert); Einsatzbericht "Durchgeführt von" (nur Anzeige). Die
übrigen hier zuerst zurückgestellten Fälle sind seit 1.8.31 behoben, siehe nächster Abschnitt.

Tests: `tests/test_v333_auswahl_inaktiv.py` -- der Helfer in node, die Auftragsseite in node
(Sachbearbeiter und Projektleiter vorgewählt, "(inaktiv)"), Speichern des Auftrags mit den Schlüsseln der
Vorlage (unverändert inaktiv 200, neu inaktiv 422), dazu Arbeitsvorbereitung, Angebot, Mitarbeiter-Funktion,
und ein Dauertest: jede Seite, die `auswahlOptionen(` aufruft, bindet `_auswahl.html` ein. Gegenprobe mit
dem Stand von 1.8.29: 10 von 10 rot. `scripts/klicktest_auswahl_inaktiv.py` 13/13, alter Stand 3/13.

## Restfälle (seit 1.8.31)

| Seite | Feld | vorher | jetzt |
|---|---|---|---|
| Zeiterfassung Backoffice, Korrektur | Auftrag einer Buchung auf einem abgeschlossenen oder stornierten Auftrag | fehlte (der Kontext liefert nur offene); vorgewählt war der erste offene Auftrag des Projekts, Speichern buchte still um | `openEdit()` lädt ihn nach (`GET /api/orders/{id}`), vorgewählt mit "(abgeschlossen)"/"(storniert)", Speichern behält ihn |
| Server | Zeitbuchung einer inaktiven Person | `update_entry()` lehnte jede Änderung ab (422), auch ohne Personenwechsel | "aktiv" nur bei neu eingetragener Person, wie die vier Prüfungen aus 1.8.30 |
| Angebot, Auftrag, Rechnung | archivierter Steuerschlüssel | Auswahl leer (nur Anzeige, gespeichert wird nur über `onchange`) | geladen mit `?include_archived=true`, `steuerschluesselOptionen()` in `_auswahl.html` |
| Dachfläche | Schicht eines inaktiven Schichttyps | stand unter "Passt nicht zum aktuellen Dachtyp" (die Archivdatei sagte bis hier fälschlich "unsichtbar") | in der Liste, " (inaktiv)"; inaktive Typen ohne Schicht werden nicht angeboten (`auswahlEintraege()`) |
| Angebots-Editor | Vortext, Zahlungsbedingung, Schlusstext, Schlusstext 2 | leerer Text wählte die Vorgabe vor, das nächste Speichern des Kopfs schrieb sie -- so bekam jeder leere Schlusstext 2 den Standard-Schlusstext | leer bleibt "— keine Auswahl —"; ein neues Angebot erhält die Vorgaben beim Anlegen vom Server (`create_quote`, `ensure_quote_structure()`), Schlusstext 2 hat keine |
| Angebots-Editor | Einheit einer Position | leere Einheit wurde "Stück" (fest, nicht die Vorgabe aus den Einstellungen) | "— keine Einheit —", Speichern verlangt eine Wahl (der Server lehnt "" ohnehin ab); eine neue Position bekommt die Vorgabe aus den Einstellungen wie bisher |
| Kunde | Kategorie | Rückfall `customer.category\|\|'Privatkunde'`, dann Standard-Kategorie; abgeschaltete hieß "· bisher" | über `auswahlOptionen()`, abgeschaltete "(inaktiv)"; ein leerer Wert bliebe leer und Speichern verlangte eine Wahl -- erreicht die Seite heute aber nicht (siehe unten) |
| Server | `GET /api/tasks/{id}/finding` | prüfte nur das Modul "wartungen" | zusätzlich "aufgabenmanagement" |

Helfer: `auswahlOptionen()` hat `opt.vermerk(x)` (Text in Klammern hinter einem nicht aktiven Eintrag, Vorgabe
"inaktiv"); `auswahlEintraege()` ist dieselbe Regel für Listen, die kein `<select>` sind. Der Dauertest in
`tests/test_v333_auswahl_inaktiv.py` prüft die Einbindung jetzt für jede Funktion des Helfers.

Kunden-Kategorie: ein leerer Wert ist heute nicht erreichbar. `ensure_customer_profile()` (`app/crm.py`) setzt
"Privatkunde", das Schema lehnt "" ab, und ein direkt in der Datenbank geleerter Wert lässt `GET
/api/customers/{id}` mit 500 scheitern (`CustomerOut.category` mit `min_length=1`), die Kundenakte lädt dann gar
nicht. Nicht behoben, nur gemeldet.

Tests: `tests/test_v334_auswahl_restfaelle.py` -- die Oberflächen in node mit einer kleinen Attrappe für DOM und
`fetch` (`FAKE_DOM`: eine Auswahl wählt wie der Browser die letzte Option mit `selected`, sonst die erste; ein
`value` ohne passende Option leert sie), die Antworten vom echten Server. Backoffice: `openEdit()` und
`saveEntryEdit()` laufen echt, der geschickte Body geht an den Server. Angebots-Texte: die vier
`fillTextSelect()`-Aufrufe aus `renderAll()` wörtlich. Gegenprobe mit dem Stand von 1.8.30: 10 von 10 rot.
`scripts/klicktest_auswahl_restfaelle.py` 19/19, alter Stand 6/19 (nur die Prüfungen "keine JS-Fehler" grün).

## Auftragskopf als Teil-Update (seit 1.8.32)

`PUT /api/orders/{order_id}` bekam mit dem Freitext-Ausführungszeitraum (`execution_period`, Stufe 2b,
Runde 2b-1b Teil 1, siehe `docs/archiv/vertragsgrundlage-und-vertrag.md`) ein neues Feld. Im alten
Volles-Formular-Handler hätte jeder Aufrufer, der es nicht kennt, den Zeitraum beim Speichern geleert --
deshalb jetzt `OrderUpdate(PartialUpdate)` mit `NOT_NULL = {title, status, order_date}` und
`model_dump(exclude_unset=True)`. Aus `BEKANNT` gestrichen, in `REPARIERT_SPAETER` des Strukturtests
festgehalten (darf nie wieder einen Fund haben). Die Auftragsseite schickt weiter alle Felder ihres
Formulars, jetzt einschließlich des Zeitraums. Test: `tests/test_v335_vertragsvorlagen.py::
test_order_put_without_execution_period_keeps_it`.
