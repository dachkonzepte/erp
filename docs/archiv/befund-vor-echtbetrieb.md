# Befund „Vor dem Echtbetrieb: Geld und Sicherheit“ (09.10.2026)

Reiner Befund: App-Code unverändert. Jeder Fehler ist mit einem Test nachgestellt, markiert als
`xfail(strict=True)` mit Verweis auf diese Datei und die Nummer des Fehlers -- die Tests werden später die Abnahmetests der
Reparatur. Keine Lösungsvorschläge. Stand des Codes: 1.8.69 (`26c3ce9`).

## Vorgabe vom 09.10.2026 (übernommen wie gegeben)

Befund „Vor dem Echtbetrieb: Geld und Sicherheit“. App-Code nicht ändern. Jeden Fehler mit einem Test nachstellen, markiert als
xfail(strict=True) mit Verweis auf den Befund; die Tests werden später zu den Abnahmetests der Reparatur. Wichtige auch gegen
PostgreSQL.

Vorab: Festlegungen 1.8.65 Nr. 2, 4, 5, 1.8.66 Nr. 4, 1.8.67 Nr. 8 und 1.8.69 im Archiv als bestätigt markieren. Bestätigen: Fehlt
die Adresse des Auftraggebers (An) oder ist sie ungültig, wird der Versand abgelehnt und geht nicht nur an die Kopien. Falls nicht
so: melden.

1. Schlussrechnung nach pauschalen Abschlägen nachstellen. Wie werden Abschläge (pauschal und nach Leistungsstand) heute abgezogen:
   netto oder mit Steuer je Abschlag, nach gestellten oder bezahlten Beträgen? Ist eine zweite Schlussrechnung möglich? Zusammenspiel
   mit Storno.
2. Einsatzbericht: Dachflächen beim Anlegen sowie Bauteile an Mangel und Prüfpunkt aus einem fremden Objekt, als Monteur
   nachstellen. Was sieht er danach vom fremden Objekt (rekursiver Schlüssel-Scan)? Dann das Muster im ganzen Code suchen: IDs aus
   der Anfrage, die gespeichert werden, ohne zu prüfen, dass sie zum selben Objekt, Auftrag oder Kunden gehören. Liste mit
   Fundstellen.
3. Abgleich mit dem Angebot bei vorhandenen Rechnungen oder Zeitbuchungen unter SQLite und PostgreSQL nachstellen. Was hängt alles
   an den Positionen? Dazu die Rücksetzung des Projektstatus.
4. Rechnungsdatum: wo gesetzt, wann (Entwurf, Festschreiben, Versand), in welcher Zeitzone; hängen Fälligkeit und Skonto daran?
   Dasselbe kurz für die übrigen Fälle der Regel-20-Ausnahmeliste.
5. Schlüssel von Aufgaben- und Pipelinespalten über 40 bzw. 30 Zeichen unter PostgreSQL nachstellen.

Bericht als Liste mit Fundstellen, je Punkt: nachgestellt ja/nein, Auswirkung, betroffene Daten. Keine Lösungsvorschläge.
Nebenbefunde nur melden. Commit nach Regel 13, nur Tests und Archiv.

## Die Tests

| Datei | Punkt | xfail | grün |
|---|---|---|---|
| `tests/test_v372_befund_an_pflicht.py` | Vorab (An) | 0 | 14 |
| `tests/test_v372_befund_schlussrechnung.py` | 1 | 15 | 4 |
| `tests/test_v372_befund_fremdes_objekt.py` | 2 | 0 (seit 1.8.70 behoben, vorher 10) | 12 |
| `tests/test_v372_befund_abgleich.py` | 3 | 9 (4 nur PostgreSQL) | 2 (1 nur PostgreSQL) |
| `tests/test_v372_befund_rechnungsdatum.py` | 4 | 5 | 2 |
| `tests/test_v372_befund_spaltenschluessel.py` | 5 | 5 (alle nur PostgreSQL) | 2 (1 nur PostgreSQL) |

- `tests/befund_vor_echtbetrieb.py`: `befund(nr, text)` = `xfail(strict=True, raises=AssertionError, reason=…)` mit Verweis auf
  diese Datei. **strict**: ist ein Fehler behoben, wird sein Test rot (XPASS), bis die Markierung fällt -- dann ist er der
  Abnahmetest. **raises=AssertionError**: scheitert ein Test an etwas anderem (Aufbau, neue Ausnahme), ist er rot statt still
  "erwartet fehlgeschlagen". Vorbedingungen deshalb mit `vorbedingung()` (eigene Ausnahme). Ein Abbruch an der Datenbank
  (IntegrityError, DataError) wird in den Tests zu AssertionError, damit er als Befund zählt.
- Geprüft wird jeweils eine **Eigenschaft**, kein Weg: z. B. "nach einer gültigen Schlussrechnung sind die gültigen Rechnungen
  zusammen die Auftragssumme", "nichts mit Bezug auf das fremde Objekt gespeichert". Darf die Reparatur eine Aktion ablehnen
  (ValueError), lässt der Test das zu und prüft danach den Zustand.
- PostgreSQL: Punkte 3 und 5 haben eigene opt-in-Tests (`pg_sitzung()`, Wegwerf-Schema, `ERP_TEST_POSTGRES_URL`, sonst skip).
  Die Dateien zu Punkt 1, 2, 4 und Vorab liefen zusätzlich über das pytest-Plugin gegen PostgreSQL (siehe Verifikation).
- Bei jedem xfail-Test mit `--runxfail` geprüft, dass er aus dem genannten Grund scheitert (Werte unten je Fehler). Dabei
  gefunden und korrigiert: ein Test (2d) wäre zuerst an "Nur unterschriebene Berichte können als PDF exportiert werden" gescheitert
  -- als AssertionError und damit still "erwartet"; seither die Trennung Vorbedingung/Befund. Ebenso 2f an einer erfundenen
  Angebots-ID der Testwelt (über `except ValueError` grün) -- jetzt mit Vorbedingung.

## Vorab

- **Festlegungen bestätigt**: 1.8.65 Nr. 2, 4, 5; 1.8.66 Nr. 4; 1.8.67 Nr. 8; 1.8.69 Nr. 1–6 -- in
  `docs/archiv/abnahme-und-gewaehrleistung.md` an den Überschriften markiert.
- **An-Adresse: bestätigt, so ist es.** Fehlt die Adresse des Auftraggebers, ist sie leer, besteht nur aus Trennzeichen, ist sie
  ungültig oder enthält das Feld neben einer gültigen eine ungültige, lehnt der Versand mit 400 ab; nichts geht hinaus, auch nicht an
  die Kopien; kein Eintrag im Versandprotokoll, keine Zeile in `dispatch_copies`. Fundstellen: `app/notice_letters.py::client_address()`
  (Pflicht, "Der Auftraggeber hat keine E-Mail-Adresse …"), `app/email_dispatch.py::dispatch_email()` -> `parse_recipients(to, …)`
  (prüft jede Adresse, bevor etwas gespeichert wird; leer -> "Keine E-Mail-Adresse hinterlegt …"). Beim Brief läuft
  `client_address()` vor `ensure_letter()` -- es entsteht auch keine Fassung. Festlegung 1.8.69 Nr. 3 ("ungültige Adresse sperrt nicht")
  gilt nur für die Kopien. Test: `test_v372_befund_an_pflicht.py`, Abnahmeprotokoll und Brief der Behinderungsanzeige, je 7 Fälle.

## Punkt 1: Abschläge, Schlussrechnung, Storno -- nachgestellt: ja

**Wie heute abgezogen wird** (`app/invoices.py`, grün festgehalten):

- Nach Leistungsstand: über die **Menge**, nicht über Beträge. Die Schlussrechnung setzt Ist = Soll
  (`_copy_order_items_with_default_ist(full_completion=True)`), abgerechnet wird `Ist − letzter Stand` je Auftragsposition
  (`compute_billed_quantity_and_total()`, `get_previous_cumulative_ist()`: letzte Rechnung mit Status `versendet`/`bezahlt` und Art
  `abschlag_leistungsstand`/`schluss` zur selben `source_order_item_id`, sortiert nach `invoice_date`, dann ID).
- Damit **netto** (Menge × EP). Die USt rechnet jede Rechnung nur auf ihren eigenen Betrag mit ihrem eigenen Satz
  (`compute_invoice_totals()`); die USt der Abschläge erscheint auf der Schlussrechnung nicht, die Schlussrechnung zeigt nur den
  Rest (Positionen mit abgerechneter Menge, "Nettosumme (diese Rechnung)", `app/invoice_pdf.py`), keine Gesamtleistung und keine
  Liste der Abschläge. Ob das als Endrechnung genügt (§ 14 Abs. 5 UStG), ist eine Rechtsfrage und hier nicht bewertet.
- Nach **gestellten** Rechnungen (versendet oder bezahlt), nicht nach Zahlungen -- eine Zahlungstabelle gibt es nicht, "bezahlt" ist
  Status plus Datum. Entwürfe zählen nicht, stornierte und Stornorechnungen nicht.
- **Pauschal**: gar nicht (1a). Der pauschale Abschlag ist ein Nettobetrag (`lump_sum_net`) mit einer reinen Projektionsposition
  ohne `source_order_item_id` (`_sync_lump_sum_pauschal_item()`), die Suche oben kennt die Art nicht.
- **Zweite Schlussrechnung**: möglich, keine Sperre (`create_schlussrechnung()`, `finalize_and_send_invoice()`, Oberfläche). Nach
  einer gültigen lautet sie über 0,00 € und bekommt eine Nummer; zwei Entwürfe nebeneinander lauten beide über 100 % (1c). Nach
  Storno der ersten rechnet eine neue richtig (grün).

Auswirkung: Zahlen aus dem Test; "laut Code" = abgeleitet, nicht im Test.

| Nr. | Fehler | Fundstelle | Auswirkung | Betroffene Daten |
|---|---|---|---|---|
| 1a | Pauschale Abschläge zieht weder die Schlussrechnung noch ein folgender Abschlag nach Leistungsstand ab | `invoices.py:158` (Arten), `:282` (Position ohne Bezug) | Auftrag 5.000 € netto, pauschal 2.000 €, dann Schluss: 7.000 € netto / 8.330 € brutto gestellt statt 5.000 / 5.950; mit Leistungsstand dazwischen ebenso 7.000. Bezahlt oder nicht: gleich. Laut Code zeigt die Auftragsseite "offen" −2.000 € (`orders.py:451`) | jede gültige Schlussrechnung und jeder Abschlag nach Leistungsstand zu einem Auftrag mit gültigem pauschalem Abschlag |
| 1b | Der Abzug wird beim Anlegen des Entwurfs gerechnet und gespeichert (`billed_*`), beim Festschreiben nicht neu | `finalize_and_send_invoice()` `:536` | (a) Schluss als Entwurf, danach Abschlag 40 % festgeschrieben, dann Schluss: 7.000 statt 5.000; (b) zwei Abschläge nach Leistungsstand als Entwurf (40 und 80 kumuliert): 6.000 statt 4.000; (c) Abschlag storniert, während die Schluss Entwurf ist: 3.000 statt 5.000 | Rechnungen, deren Entwurf vor einer anderen Festschreibung oder einem Storno desselben Auftrags angelegt wurde |
| 1c | Zweite Schlussrechnung und Abschlag nach der Schlussrechnung ohne Sperre | `create_schlussrechnung()` `:328`, `create_abschlag_pauschal()` `:294` | zwei gültige Schlussrechnungen (10.000 €); pauschaler Abschlag nach der Schluss zusätzlich (5.500 €) | Aufträge mit mehr als einer gültigen Schlussrechnung bzw. einem gültigen Abschlag nach ihr |
| 1d | Storno eines pauschalen Abschlags ohne Position (vor 1.3.24) lautet über 0,00 €, das Original steht trotzdem auf "storniert" | `create_storno_draft()` `:605` kopiert nur Positionen, `compute_invoice_totals()` `:218` summiert für `storno` nur Positionen | Storno 0 statt −2.000 € | laut `projektliste-und-mappe.md` (1.3.24) R-2026-0001 und R-2026-0002, beide versendet, ohne Position -- mit dem Umzug vermutlich auch auf dem Server (nicht geprüft, Regel 16) |
| 1e | Mehrere Storno-Entwürfe zur selben Rechnung, alle festschreibbar | `create_storno_draft()` prüft nur den Status des Originals beim Anlegen (`:588`) | zwei gültige Stornos zu einer Rechnung, Gutschrift doppelt | Originale mit mehr als einem nicht-Entwurf-Storno |
| 1f | Eine Stornorechnung lässt sich stornieren | `create_storno_draft()`, keine Prüfung der Art | gültige "Storno" einer Storno; das Original bleibt storniert, die Rückgängigmachung zählt nirgends (`compute_order_billing_progress()` lässt Art `storno` weg) | Stornos mit `storno_of_invoice_id` auf eine Storno |
| 1g | Storno eines Abschlags hinter einer gültigen Schlussrechnung | `get_previous_cumulative_ist()` / `compute_order_billing_progress()` | der Auftrag ist danach mit 3.000 statt 5.000 € abgerechnet, eine neue Schluss rechnet 0 € -- still unterabgerechnet | Stornos von Abschlägen nach Leistungsstand, deren Auftrag eine gültige Schlussrechnung hat |
| 1h | Ein Mahnungsentwurf geht noch hinaus, nachdem die Rechnung storniert oder bezahlt ist | `reminders.py::finalize_and_send_reminder()` `:195` (nur `create_reminder()` prüft "versendet", `:177`) | Mahnung M-2026-0001 "versendet" zu stornierter bzw. bezahlter Rechnung | versendete Mahnungen, deren Rechnung vorher storniert bzw. bezahlt war |

Prüfabfragen (PostgreSQL, nur lesen):

```sql
-- 1a: Aufträge mit gültigem pauschalem Abschlag und gültiger Schlussrechnung
SELECT o.order_number FROM orders o
WHERE EXISTS (SELECT 1 FROM invoices i WHERE i.order_id = o.id AND i.invoice_type = 'abschlag_pauschal'
              AND i.status IN ('versendet', 'bezahlt'))
  AND EXISTS (SELECT 1 FROM invoices i WHERE i.order_id = o.id AND i.invoice_type = 'schluss'
              AND i.status IN ('versendet', 'bezahlt'));
-- 1c: mehr als eine gültige Schlussrechnung je Auftrag
SELECT order_id, count(*) FROM invoices WHERE invoice_type = 'schluss' AND status IN ('versendet', 'bezahlt')
GROUP BY order_id HAVING count(*) > 1;
-- 1d: Stornos pauschaler Abschläge ohne Position
SELECT s.invoice_number, o.invoice_number FROM invoices s JOIN invoices o ON o.id = s.storno_of_invoice_id
WHERE o.invoice_type = 'abschlag_pauschal' AND NOT EXISTS (SELECT 1 FROM invoice_items it WHERE it.invoice_id = o.id);
-- 1e/1f: mehr als ein Storno zu einer Rechnung, Storno einer Storno
SELECT storno_of_invoice_id, count(*) FROM invoices WHERE invoice_type = 'storno' AND status <> 'entwurf'
GROUP BY storno_of_invoice_id HAVING count(*) > 1;
SELECT s.invoice_number FROM invoices s JOIN invoices o ON o.id = s.storno_of_invoice_id WHERE o.invoice_type = 'storno';
```

## Punkt 2: fremdes Objekt im Einsatzbericht, als Monteur -- nachgestellt: ja

Welt: Monteurin über die Kolonne an der Arbeitsvorbereitung dem Auftrag am Objekt "Eigen" zugeordnet; zweites Objekt eines anderen
Kunden mit Dachfläche und Bauteil. Die Oberfläche bietet nur die eigenen Flächen an -- der Weg ist der direkte API-Aufruf mit
fortlaufenden IDs; eine unbekannte ID überspringt `create_report()` still (die Antwort verrät, ob es eine Dachfläche gibt).

| Nr. | Fehler | Fundstelle | Auswirkung | Betroffene Daten |
|---|---|---|---|---|
| 2a | `roof_area_ids` beim Anlegen ohne Abgleich mit `order.project.property_id` (auch archivierte) | `app/service_reports.py:552` (`create_report()`), Route `POST /api/orders/{id}/service-reports` (field) | `ServiceReportRoofArea` mit Namens-Schnappschuss der fremden Fläche; bei Wartung bzw. Vorlage Prüfpunkte aus deren Bauteilen ("FREMDGULLY Villa: Ablauf frei …"); laut Code holen `regenerate`/`sync` deren Bauteile nach | `service_report_roof_areas`, `inspection_items` mit Fläche/Bauteil eines anderen Objekts |
| 2b | Prüfpunkt: `roof_component_id`, `roof_area_id` ungeprüft, nicht einmal auf Existenz | `add_inspection_item()` `:696`, Route `POST /api/service-reports/{id}/inspection-items` (field, eigener Bericht) | Prüfpunkt an fremdem Bauteil; laut Code eine nicht vorhandene ID unter PostgreSQL 500 (Fremdschlüssel) | `inspection_items` |
| 2c | Mangel: `roof_component_id` ungeprüft (nur `inspection_item_id` wird gegen den Bericht geprüft) | `app/findings.py::create_finding()` `:289`, Route `POST /api/service-reports/{id}/findings` (field) | Namens-Schnappschuss des fremden Bauteils; laut Code steht der Mangel in dessen Bauteil-Historie (`list_findings_for_component()`), zählt in `finding_count` und sperrt das Löschen des Bauteils (`roof_areas.py:350–356`) -- im Büro mit Kunde und Objekt des eigenen Auftrags | `findings` |
| 2d | Was die Monteurin danach sieht | siehe unten | Namen und IDs von Dachfläche und Bauteil des fremden Objekts | -- |

**2d, was sie sieht** (Werte-Scan über jede Antwort, `_fremde_werte()`; Ausgabe des Tests mit `--runxfail`):

- `GET /api/orders/{id}/service-reports`: `$[].roof_areas[].roof_area_id`, `.roof_area_name` ("FREMDDACH Villa Sued")
- `GET /api/service-reports/{id}/inspection-items`: `$[].roof_area_id`, `$[].roof_component_id`, `$[].text` ("FREMDGULLY Villa: Ablauf
  frei und funktionsfähig", "… Laubfang vorhanden und intakt")
- `GET /api/service-reports/{id}/findings`: `$[].roof_component_id`, `$[].roof_component_name` ("FREMDGULLY Villa")
- `GET /api/field-view/today`: `$.draft_reports[].roof_areas[].roof_area_id`, `.roof_area_name`
- nach der Unterschrift `GET /api/field-view/properties/{Eigen}/maintenance-history` -- **für jeden Monteur, der das Objekt
  öffnet** (jedes Objekt ist für ihn offen): `roof_areas[]`, `inspection_items[].roof_area_name`/`.text`,
  `findings[].roof_component_name`
- PDF des Berichts: "FREMDDACH Villa Sued", "FREMDGULLY Villa"
- `GET /api/orders/{id}/property-service-reports` nicht (zeigt nur andere Aufträge des Objekts), `GET /api/orders/{id}/roof-areas`
  nicht (nur das eigene Objekt).
- **Der rekursive Schlüssel-Scan** aus `test_v326_monteur_datengrenze.py` (`_verstoesse()`, verbotene Schlüsselnamen) schlägt bei
  keiner dieser Antworten an -- grün festgehalten: was durchkommt, steht unter erlaubten Namen (`roof_area_name`, `text`,
  `roof_component_name`). Adresse, Kunde und Name des fremden Objekts kommen nicht durch, die Dachflächen-Routen bleiben 403 (grün).

**Das Muster im ganzen Code** (ID aus der Anfrage gespeichert ohne Prüfung, dass sie zum selben Objekt, Auftrag oder Kunden gehört;
alle `*_id`/`*_ids` der Create- und Update-Schemas bis zum Speichern verfolgt):

| Nr. | Fundstelle | Endpunkt, Mindestrolle | Feld -> Ziel | fehlt | Auswirkung | Test |
|---|---|---|---|---|---|---|
| 2a | `service_reports.py:552` | `POST /api/orders/{id}/service-reports`, **field** | `roof_area_ids` -> RoofArea | Objekt des Auftrags | siehe oben | 2a, 2d |
| 2b | `service_reports.py:696` | `POST /api/service-reports/{id}/inspection-items`, **field** | `roof_component_id`, `roof_area_id` | Objekt, Existenz | siehe oben | 2b, 2d |
| 2c | `findings.py:289` | `POST /api/service-reports/{id}/findings`, **field** | `roof_component_id` | Objekt | siehe oben | 2c, 2d |
| 2e | `service_reports.py:1011`, `:1067` | `POST /api/service-reports/{id}/materials`, `PUT /api/service-report-materials/{id}`, **field** | `roof_area_id` | geprüft nur, wenn der Bericht Flächen hat (`if covered and …`) | Materialzeile an fremder Fläche | 2e |
| 2f | `quick_service_orders.py:39` | `POST /api/quick-service-orders`, buero_auftrag | `property_id` (und `customer_id`) | Objekt gehört dem Kunden (anders als `POST/PUT /api/projects`) | Projekt von Kunde X am Objekt von Y; Auftrag und Rechnung tragen Objekt Y als Schnappschuss (GoBD); ein eingeplanter Monteur sieht Zugang, Dachflächen und Historie von Y | 2f |
| 2g | `maintenance_contracts.py:349`, `:366` | `POST`/`PUT /api/maintenance-contracts[/{id}]`, buero_auftrag | `property_id` | Objekt gehört dem Vertragskunden; beim Ändern passen die Positionen (`roof_area_id`) nicht mehr | "Wartung durchführen" (field) legt einen Schnellauftrag für X am Objekt Y an (Folgen wie 2f); Monteure von Y sehen den Vertrag von X | 2g |
| 2h | `maintenance_contracts.py:357`, `:378`, `:724`, `:755`, Verwendung `:551–566` | Vertrag und Position, buero_auftrag | `template_project_id` -> Project | weder Mustervorgang noch Kunde/Objekt des Vertrags | "Vorgang erstellen" kopiert über `duplicate_project()` Kunde und Objekt des Musters (`projects.py:760`) -- der Wartungsvorgang landet beim Kunden des Musters; die Oberfläche bietet die Muster aller Kunden an | 2h |
| 2i | `invoices.py:456` (`add_invoice_item()`) | `POST /api/invoices/{id}/items`, buero_auftrag | `source_order_item_id` -> OrderItem | Position gehört zum Auftrag der Rechnung; Existenz | fremde Position in einer Rechnung (nach dem Festschreiben unveränderlich); kein Vorstand gefunden -> volle Menge berechnet; Abgleich des anderen Auftrags dann unter PostgreSQL 500 | 2i |

Geprüft vorhanden (Gegenprobe der Suche, rund 30 Stellen), z. B. `time_tracking.py::validate_order_item()` (Position gehört zum
Auftrag), `acceptances.py:509–526` (Dachflächen nur des Objekts, Beteiligter nur des Projekts; ebenso `defects.py`,
`checklists.py`), `maintenance_contracts.py:713–719` (Dachfläche der Position gehört zum Vertragsobjekt), Projekte und Anfragen
(Objekt gegen Kunde), nachgetragene Zustellung (Beteiligter des Projekts). Nicht als Fund gewertet: Checklisten im Kontext Objekt
bzw. Betriebsmittel und Objekt-Uploads zu jeder ID (Betreiberentscheidung A, `routers/checklists.py:12–13`).

**Betroffene Daten**: Prüfabfrage für 2a (PostgreSQL, nur lesen):

```sql
SELECT sr.id, sra.roof_area_id FROM service_report_roof_areas sra
JOIN service_reports sr ON sr.id = sra.service_report_id JOIN orders o ON o.id = sr.order_id
JOIN projects p ON p.id = o.project_id JOIN roof_areas ra ON ra.id = sra.roof_area_id
WHERE ra.property_id IS DISTINCT FROM p.property_id;
```

## Punkt 3: Abgleich mit dem Angebot -- nachgestellt: ja (SQLite und PostgreSQL)

`app/orders.py::sync_order_from_source_quote()` (`POST /api/orders/{id}/sync-source-quote`, buero_auftrag) löscht alle Positionen und
Titel des Auftrags und legt sie neu an (`_copy_quote_scope_to_order()`, `orders.py:596–601`) -- neue IDs, keine Zuordnung über die
Angebotsposition. Er prüft weder Rechnungen noch Zeitbuchungen noch den Status des Auftrags. Der Router fängt nur
`ContractSignedError`/`AcceptanceExistsError` (409) und `ValueError` (422).

**Was an den Positionen hängt** (`order_items.id`, alle Fremdschlüssel ohne `ON DELETE`, in Modell und Migrationen):

| Spalte | `models.py` | im Abgleich |
|---|---|---|
| `invoice_items.source_order_item_id` | 1754 | nichts |
| `time_entries.order_item_id` | 2480 | nichts |
| `time_entry_groups.order_item_id` | 2517 | nichts |
| `work_preparation_materials.source_order_item_id` (und `source_material_snapshot_id`) | 1916, 1915 | vorher geleert, danach neu zugeordnet (`orders.py:759–768`, `refresh_preparation_materials()`) |
| `order_item_calculation_snapshots.order_item_id` (samt Material) | 1605 | mitgelöscht (Kaskade) |

Dazu `order_sections.parent_id` -> `order_sections.id` (verschachtelte Titel). Keinen Bezug haben Plantafel, Material im Bericht,
Checklisten, Aufmaß.

| Nr. | Fehler | Auswirkung (Zahlen aus dem Test, "laut Code" abgeleitet) | Betroffene Daten |
|---|---|---|---|
| 3a | Rechnung an einer Position: unter SQLite zeigt sie danach ins Leere, der Leistungsstand beginnt bei 0 | Abschlag 40 % (200 €) festgeschrieben, Angebot um eine Position ergänzt (Auftrag 600 €), Abgleich, Schluss: 800 € statt 600 € abgerechnet | SQLite (lokal); unter PostgreSQL bricht der Abgleich ab (3e) |
| 3b | Zeitbuchung an einer Position: danach ohne gültige Position (SQLite) | `order_item_id` zeigt auf keine Position; laut Code fehlen die Ist-Stunden je Position, und Bearbeiten der Buchung lehnt mit 422 "Die LV-Position gehört nicht zum ausgewählten Auftrag." ab (`validate_order_item()`) | wie 3a |
| 3c | Position einer festgeschriebenen Rechnung: danach ohne Auftragsposition (SQLite) | `source_order_item_id` ins Leere; Betrag und PDF bleiben (gespeicherte Werte, Ablage), die Kette der Abschläge bricht (3a) | wie 3a |
| 3d | Projektstatus ohne Bedingung auf "beauftragt" (`orders.py:772`), Angebot ebenso (`:771`) | "ausfuehrung" bzw. "abgeschlossen" -> "beauftragt"; laut Code zählt ein abgeschlossenes Projekt danach wieder als aktiv (`dashboard.html:162`) | jedes Projekt, dessen Auftrag nach "ausfuehrung"/"abgeschlossen" abgeglichen wurde |
| 3e | **PostgreSQL: Abbruch mit IntegrityError (500)** | `ForeignKeyViolation` an `order_sections_parent_id_fkey` (verschachtelte Titel -- ohne jede Rechnung oder Zeitbuchung), `time_entries_order_item_id_fkey`, `invoice_items_source_order_item_id_fkey` (auch ein Entwurf). Transaktion zurückgerollt, kein Datenschaden -- der Abgleich ist für diese Aufträge dauerhaft unmöglich | auf dem Server jeder Auftrag aus einem Angebot mit Untertitel (Titel und Untertitel im Angebots-Editor, `create_quote_section()`; der Import legt keine Titel an) oder mit einer Zeitbuchung bzw. Rechnung an einer Position |

Unter SQLite zusätzlich (nicht als Test, aus dem Code): waren die gelöschten Positionen die höchsten IDs der Tabelle, vergibt SQLite
dieselben IDs neu (kein `AUTOINCREMENT`) -- dann zeigen Zeitbuchung und Rechnung still auf die neue Position mit derselben ID. Die
Testwelt legt deshalb einen zweiten, späteren Auftrag an. Der vorhandene Test `test_v325_quote_order_copy_fields.py::
test_abgleich_copies_every_field_marked_so_and_keeps_the_others` (verschachtelte Titel) ist über das pytest-Plugin gegen
PostgreSQL rot (dieselbe `ForeignKeyViolation`) -- er lief bisher nur unter SQLite.

## Punkt 4: Rechnungsdatum -- nachgestellt: ja

- **Wo und wann**: `Invoice.invoice_date` setzt keine Funktion ausdrücklich; es greift die Spaltenvorgabe `default=date.today`
  (`models.py:1657`) beim Anlegen des **Entwurfs** -- jede Art (pauschal, Leistungsstand, Schluss, aus Aufwand, Storno;
  `invoices.py:300/315/329/390/590`). Beim Festschreiben (`finalize_and_send_invoice()`: Nummer, Status) und beim E-Mail-Versand
  nicht erneuert; im Entwurf nicht änderbar (`InvoiceHeaderUpdate`, `INVOICE_HEADER_FIELDS`, Feld in der Oberfläche gesperrt).
- **Zeitzone**: die Uhr des Rechners -- auf dem Server UTC: zwischen 0 und 2 Uhr (Sommer) bzw. 0 und 1 Uhr (Winter) Berliner Zeit
  der Vortag, an Silvester das alte Jahr. Die Nummer nimmt dagegen das Berliner Jahr beim Festschreiben (`settings.py:143`).
- **Was daran hängt**: Skontodatum = `invoice_date + skonto_days` (`invoices.py:705`, in Satz, PDF, Platzhalter `{skontodatum}`);
  Fälligkeit nach Wahl einer Zahlungsbedingung = `invoice_date + days` (`:660`); "Datum" im PDF, `{rechnungsdatum}` in Mail und
  Mahnung, "vom" im Mahn-PDF; Reihenfolge des Leistungsstands (`:161`). Die Fälligkeit **beim Anlegen** rechnet dagegen ab
  `berlin_today()` (`:129`). Mahnfristen hängen nur über `due_date` daran. Einen Leistungszeitraum hat die Rechnung nicht.

| Nr. | Fehler | Auswirkung (Test, Server in UTC nachgestellt; "laut Code" abgeleitet) | Betroffene Daten |
|---|---|---|---|
| 4a | Rechnungsdatum aus der Rechner-Uhr | Entwurf am 15.07.2026 um 0:30 Uhr (Berlin): Datum 14.07.; am 01.01.2027 um 0:30 Uhr: Datum 31.12.2026 bei Nummer R-2027-… | Rechnungen, deren Entwurf zwischen 0 und 1 bzw. 2 Uhr Berliner Zeit angelegt wurde |
| 4b | Fälligkeit beim Anlegen ab Berlin, Skontodatum ab `invoice_date` | dieselbe Rechnung: zahlbar bis 29.07. (= Datum + 15), Skonto bis 21.07. (= Datum + 7); nach Wahl der Zahlungsbedingung zahlbar bis 28.07. -- dieselbe Bedingung, zwei Fälligkeiten (Modell-Docstring: `invoice_date + days = due_date`) | wie 4a |
| 4c | Fälligkeit und Skontofrist stehen mit dem Entwurf fest | Entwurf 15.07., festgeschrieben und versendet 05.08.: fällig 29.07. -- bei Versand schon überfällig; laut Code führt das Mahnwesen sie sofort als überfällig (`due_date < berlin_today()`) | jede Rechnung, deren Entwurf länger als ihr Zahlungsziel lag; unabhängig von UTC |
| 4d | `OrderCreateFromQuote.order_date = Field(default_factory=date.today)` (`schemas.py:1203`) | ohne Datum in der Anfrage die Rechner-Uhr; die Oberfläche schickt immer das Datum des Browsers (`quote_editor.html`), betroffen ist nur ein API-Aufruf ohne Datum | Aufträge aus solchen Aufrufen |

**Die übrigen Fälle der Ausnahmeliste** (`BEKANNTE_VORGABEN` in `test_v316_berlin_time.py`): die Spaltenvorgabe greift nirgends,
das Datum wird ausdrücklich aus Berlin gesetzt (grün festgehalten bzw. in `test_v316`):

- `Order.order_date`: der einzige Konstruktor (`orders.py:699`) nimmt das Datum des Aufrufers (Dialog: Browser, Schnellauftrag:
  `berlin_today()`); daran hängen nur Anzeige ("Datum" im Auftrags-PDF, `{auftragsdatum}` im Vertrag), keine Frist; Nummer aus dem
  Berliner Jahr.
- `Reminder.reminder_date`: `berlin_today()` beim Anlegen (`reminders.py:182`), neue Frist = heute + Tage der Stufe; beim
  Festschreiben nicht erneuert (Mahndatum = Tag des Entwurfs), daran hängen die nächste Stufe und `{vorheriges_mahndatum}`.
- `QuoteDocumentMeta.quote_date`: aus `created_at` in Berlin bzw. `berlin_today()` (`projects.py:67–72`, `:665`), "Gültig bis" =
  Datum + 30, änderbar.
- `ServiceReport.performed_at`: `performed_at or berlin_today()` (`service_reports.py:515`), änderbar; die nächste Wartungsfälligkeit
  rechnet nicht damit.

Prüfabfrage für 4a (PostgreSQL, nur lesen; `created_at` ist naive UTC):

```sql
SELECT invoice_number, invoice_date, created_at FROM invoices
WHERE invoice_date <> ((created_at AT TIME ZONE 'UTC') AT TIME ZONE 'Europe/Berlin')::date;
```

## Punkt 5: Spaltenschlüssel -- nachgestellt: ja (PostgreSQL)

Der Schlüssel entsteht aus der Bezeichnung (`_slugify()`: Kleinbuchstaben, alles außer a–z/0–9 wird "_", auch Umlaute; bei
Gleichheit "_2" …), ungekürzt (`task_columns.py:50–61`, `project_pipeline_columns.py:60–71`). Erlaubt sind 80 Zeichen Bezeichnung
(`TaskColumnCreate`, `ProjectPipelineColumnCreate`). `task_columns.key` und `project_pipeline_columns.key` sind `String(40)`,
`tasks.status` -- dort steht der Schlüssel der Spalte einer Aufgabe, ohne Fremdschlüssel -- `String(30)`. Projekte verweisen auf die
Pipelinespalte über die ID. Anlegen nur Admin (`/api/task-columns`, `/api/project-pipeline-columns`); die Router fangen nur
`ValueError`. `test_v364_feste_werte_spaltenlaenge.py` sieht nur feste Werte, die Spalten stehen dort als Nutzerwerte.

| Nr. | Fehler | Auswirkung (im Test) | Betroffene Daten |
|---|---|---|---|
| 5a | Aufgabenspalte, Schlüssel über 40 Zeichen | Bezeichnung "Wartet auf Rückmeldung des Auftraggebers und der Hausverwaltung" (63): `StringDataRightTruncation … varying(40)`, 500 | keine (nichts gespeichert) |
| 5b | Pipelinespalte, Schlüssel über 40 Zeichen | wie 5a | keine |
| 5c | Aufgabenspalte, Schlüssel 31–40 Zeichen | "Wartet auf Rückmeldung des Auftraggebers" (Schlüssel genau 40) entsteht; eine Aufgabe dorthin verschieben, darin anlegen: `… varying(30)`, 500. **Steht die Spalte vorn**, scheitert jede neue Aufgabe ohne Status -- auch die automatischen (Mangel, Folgen der Checklisten, Erinnerungen über `_default_column_key()`) | Spalten mit Schlüssel über 30 Zeichen: `SELECT key FROM task_columns WHERE length(key) > 30;` |

Unter SQLite wird jeder dieser Werte still gespeichert (grün festgehalten).

## Nebenbefunde (nur gemeldet, nicht nachgestellt)

1. **Prüfpunkte ohne Fläche fehlen im PDF eines Berichts mit Flächen** (`service_report_pdf.py:243–250`): gerendert werden je Fläche
   nur Punkte mit deren `roof_area_id`; ein von Hand ergänzter Punkt ohne Fläche (oder mit einer Fläche außerhalb des Berichts)
   fehlt im unterschriebenen PDF -- `add_inspection_item()` verspricht im Docstring "rendert außerhalb jedes Flächen-Blocks".
2. **(seit 1.8.70 behoben, siehe unten)** **Mitarbeiter ohne `_employee_for_request()`**: `recorded_by_employee_id` am Prüfpunkt (`PUT`, Feldliste
   `service_reports.py:720–723`) und `closed_by_employee_id` am Mangel (`routers/findings.py:109`) übernimmt der Server aus der
   Anfrage -- ein Monteur kann einen anderen als "erfasst von"/"geschlossen von" eintragen (Regel im Docstring von
   `_employee_for_request()`).
3. **Objekt wechselt den Kunden** (`PUT /api/properties/{id}` mit `customer_id`, prüft nur Existenz) und **Objektwechsel
   am Projekt** (prüft nicht Berichte, Abnahmen mit Dachflächen des alten Objekts) -- Projekte, Anfragen, Verträge zeigen danach auf
   ein Objekt eines anderen Kunden bzw. Dachflächen eines anderen Objekts. Ein Eigentümerwechsel kann gewollt sein.
4. **Abgleich auch bei stornierten oder abgeschlossenen Aufträgen** (kein Blick auf `order.status`).
5. **Steuersatz je Rechnung änderbar** (`update_invoice_tax_key()`): weicht der Satz der Schlussrechnung von dem der Abschläge ab
   (z. B. § 13b, 0 %), bleibt die USt der Abschläge unberührt -- die Schlussrechnung rechnet nur den Rest mit ihrem Satz.
6. **`test_v143_billing_progress.py:165`** (`due_date == invoice_date + 21`) wird auf einem Rechner in UTC zwischen 22 und 24 Uhr UTC
   rot -- derselbe Mechanismus wie 4b; lokal in deutscher Zeit unsichtbar.
7. **Veraltete Verweise**: `models.py:1741` und `invoices.py:13` nennen `berechne_abgerechnete_menge()`, die es nicht gibt
   (gemeint: `compute_billed_quantity_and_total()`); der Kommentar an `Invoice.invoice_type` (`models.py:1655`) nennt 4 Arten, es
   sind 5 (`aufwand` fehlt).
8. **CLAUDE.md** hat noch keinen Verweis auf diese Datei (Vorgabe: nur Tests und Archiv). Seit 1.8.70 ergänzt (Modulübersicht,
   Regel 25).

## Verifikation

- Die sechs Dateien mit `ERP_TEST_POSTGRES_URL` (opt-in-Tests der Punkte 3 und 5 gegen die lokale PostgreSQL): 26 grün, 44 erwartet
  fehlgeschlagen; mit `--runxfail` scheitert jeder der 44 an seiner Prüfung (AssertionError), keiner an einer Vorbedingung. Ohne die
  Variable: 24 grün, 11 übersprungen, 35 erwartet fehlgeschlagen.
- PostgreSQL über das pytest-Plugin (Wegwerf-Schemas der lokalen Instanz): Punkte 1, 2, 4 und Vorab 22 grün, 30 erwartet
  fehlgeschlagen -- mit `--runxfail` dieselben Gründe wie unter SQLite.
- Die Prüfabfragen oben: `EXPLAIN` jeder Abfrage auf einem Wegwerf-Schema der lokalen PostgreSQL (Tabellen aus den Modellen), alle
  acht gültig. Gegen echte Daten ist keine gelaufen (Regel 16).
- Volle Suite (mit den opt-in-Tests gegen PostgreSQL): 3130 grün, 44 erwartet fehlgeschlagen, 0 rot. Danach nur noch in
  `tests/befund_vor_echtbetrieb.py` der Import von `app.models` in `pg_sitzung()` ergänzt (ohne ihn hat ein Aufruf außerhalb der
  Suite keine Tabellen); Kontrolle der sechs Dateien mit `test_v316` und `test_v357`: 41 grün, 44 erwartet fehlgeschlagen.

## Umsetzung 1.8.70: Reparatur Sicherheit (Punkt 2)

### Vorgabe vom 09.10.2026 (übernommen wie gegeben)

Reparatur Sicherheit (befund-vor-echtbetrieb.md, Punkt 2). In CLAUDE.md den Verweis auf befund-vor-echtbetrieb.md ergänzen.

1. Monteur-Wege (2a–2e): Dachfläche, Bauteil und Material nur aus dem Objekt des Auftrags. Eine gemeinsame Prüffunktion; sonst
   404 ohne Grund.
2. Objekt-Historie in /mobil nur für Objekte seiner zugeordneten Aufträge, nach derselben Zugriffsregel wie Auftrag und Bericht.
3. „Erfasst von“ und „geschlossen von“ setzt der Server aus der Anmeldung; Werte aus der Anfrage werden abgelehnt.
4. 2h: Der Vorgang aus einem Wartungsvertrag bekommt den Kunden des Vertrags. 2i: Eine Rechnungsposition verweist nur auf
   Positionen desselben Auftrags.
5. 2f/2g (Büro): Kunde und Objekt dürfen abweichen (Generalunternehmer, Hausverwaltung), aber nur mit Hinweis und bewusster
   Bestätigung wie beim abweichenden Kunden der Anzeigen.
6. Muster: Strukturtest, der jede Eingabe mit einer fremden ID findet und verlangt, dass sie über eine Zugehörigkeitsprüfung
   läuft. Ausnahmeliste darf nur kürzer werden.

Die xfail-Tests zu Punkt 2 müssen grün werden; Markierung dann entfernen. Angriffstests mit Gegenprobe. Wichtige Tests auch gegen
PostgreSQL. Eigene Festlegungen mit „Bitte bestätigen“. Nebenbefunde nur melden. Wird der Umfang zu groß: nach Punkt 3 committen
und den Rest auflisten. Commit nach Regel 13, Bericht kurz.

### Was gebaut ist

- **Gemeinsame Prüfung** `app/zugehoerigkeit.py::require_in_order_property(db, order, roof_area_ids=…, roof_component_id=…,
  roof_area_id=…)`: jede Dachfläche und das Bauteil gehören zum Objekt des Auftrags (`order.project.property_id`), ein Bauteil mit
  angegebener Fläche sitzt auf genau dieser. Sonst `NotInOrderProperty` (ein `ValueError`), der Router antwortet 404 mit
  „Dachfläche nicht gefunden.“ bzw. „Bauteil nicht gefunden.“ – für eine fremde und eine nicht vorhandene ID dieselbe Antwort.
  Aufgerufen in `create_report()` (2a, ausdrückliche Auswahl), `add_inspection_item()` (2b), `create_finding()` (2c, frei
  angegebenes Bauteil; mit Prüfpunkt kommt das Bauteil wie bisher aus dem Prüfpunkt), `add_material()`/`update_material()` (2e,
  jetzt immer, die Prüfung „gehört zum Bericht“ bleibt danach mit 400). Nichts wird angelegt, wenn eine ID nicht passt.
- **Wartungshistorie in /mobil**: `GET /api/field-view/properties/{id}/maintenance-history` und `…/{report_id}/pdf` für `field`
  nur, wenn das Objekt zu einem Auftrag gehört, den der Monteur öffnen darf (`app/orders.py::field_accessible_property_ids()` über
  `field_accessible_order_ids()`: Team, Einzelzuweisung, eigener Bericht – ohne Zeitfenster). Liste sonst 403 mit Hinweis, PDF 404
  wie „nicht vorhanden“. `mobil_objekt.html` zeigt den Hinweis ruhig statt rot. Objektansicht, Dokumente und Upload bleiben für
  jedes Objekt offen (Betreiberentscheidung „Dateiablage je Objekt“, `rechtekonzept.md`).
- **„Erfasst von“ / „geschlossen von“**: `InspectionItemResultUpdate` und `FindingFollowupUpdate` ohne die Felder; wer sie
  mitschickt, bekommt 422 (Muster `TaskUpdate`), auch mit dem eigenen Wert und als Admin. Der Router übergibt
  `_role.employee_id`: `update_inspection_item(…, recorded_by_employee_id=…)` setzt es bei jeder Änderung wie `recorded_at`,
  `update_finding_followup(closed_by_employee_id=…)` und „sofort behoben“ beim Anlegen (`create_finding(closed_by_employee_id=…)`).
  `service_reports.html` schickt den Wert nicht mehr.
- **2h**: `duplicate_project(…, owner=(customer_id, property_id))`; `create_project_from_contract()` übergibt Kunde und Objekt des
  Vertrags (Vertrags- und Positionsebene) – auch die Vertragsgrundlage des kopierten Angebots folgt dem Vertragskunden. Ein
  Mustervorgang am Vertrag oder an der Position muss ein Mustervorgang sein (`require_template_project()`, `is_template`), geprüft
  beim Anlegen und bei einem neu gewählten Wert.
- **2i**: `add_invoice_item()` nimmt `source_order_item_id` nur aus dem Auftrag der Rechnung (sonst 400 mit Grund).
- **2f/2g**: `property_customer_mismatch()` / `require_confirmed_property()` in `app/zugehoerigkeit.py`: gehört das Objekt einem
  anderen Kunden, braucht `POST /api/quick-service-orders`, `POST /api/maintenance-contracts` und ein neu gewähltes Objekt bei
  `PUT /api/maintenance-contracts/{id}` `confirm_property_customer: true`, sonst 409 mit Hinweistext (beide Kunden und das Objekt).
  Aufrufe im Prozess, die Kunde und Objekt aus einem bestehenden Datensatz übernehmen („Wartung durchführen“, Folgeauftrag aus dem
  Mangel, Vertrag aus Projekt), bestätigen selbst. Oberfläche (`_objekt_anderer_kunde.html`, auf „Wartungen & Reparaturen“ für
  Schnellauftrag und Vertragsanlage und auf der Vertragsseite): Häkchen „Objekte anderer Kunden anzeigen“, bei einem solchen
  Objekt ein Hinweis mit Bestätigungs-Häkchen; ohne Häkchen sendet die Seite nicht. Ein gespeichertes fremdes Objekt bleibt
  vorgewählt („Objekt von … – bestätigt.“). Ein Objektwechsel am Vertrag wird abgelehnt, solange Positionen an Dachflächen eines
  anderen Objekts hängen. `PUT /api/projects/{id}` prüft „Objekt gehört zum Kunden“ nur noch bei geändertem Kunden oder Objekt.
- **Strukturtest** `tests/test_v373_zugehoerigkeit_struktur.py`: geht jede Route aus `app.main` durch und findet jede ID-Eingabe
  einer schreibenden Route (Body auch verschachtelt, Formular, Query) und jedes Paar von IDs im Pfad (jede Methode). Einordnung:
  STAMMDATEN nach Feldname (35 Namen, je mit Grund), GEPRUEFT je Route und Feld mit Funktion und Vergleich (81 Einträge: die
  Funktion muss vom Endpunkt aus erreicht werden – Aufrufgraph über `app/` per AST, auch über weitergereichte Funktionen und
  Import-Aliase – und den Vergleich wörtlich enthalten), FREI mit Grund (die ID legt Besitzer oder Kontext fest, 30), AUSNAHMEN
  (1, darf nur kürzer werden: Eigentümerwechsel am Objekt, Nebenbefund 3). Dazu: „erfasst/geschlossen von“ nimmt keine Route an,
  kein STAMMDATEN-Name zeigt auf eine Tabelle mit Objekt-, Auftrags- oder Kundenbezug. Die Liste der Prüfstellen stammt aus einer
  Durchsicht aller Eingaben bis zur Speicherstelle (87 Felder, 24 Pfad-Paare; zwei weitere Pfad-Paare der
  Positions-Kalkulation fand erst der Test).

### Festlegungen – Bitte bestätigen

1. 404-Texte „Dachfläche nicht gefunden.“ / „Bauteil nicht gefunden.“ – gleich für fremd und unbekannt. Die Prüfung sitzt in der
   Geschäftslogik und gilt für jede Rolle, auch fürs Büro.
2. Bauteil und Fläche beide angegeben: das Bauteil muss auf genau dieser Fläche sitzen (sonst 404 wie fremd).
3. Archivierte Dachflächen und Bauteile des eigenen Objekts bleiben erlaubt.
4. Auftrag ohne Objekt am Projekt (Hauptadresse): keine Dachfläche annehmbar – wie die Auswahl, die dort keine anbietet.
5. Ohne ausdrückliche Auswahl nimmt der Bericht die Fläche der Vertragsposition – gehört sie nicht zum Objekt des Auftrags, wird
   sie still weggelassen (kein Fehler), damit „Wartung durchführen“ an älteren Vorgängen nicht scheitert.
6. Material an einer Fläche des eigenen Objekts, die nicht am Bericht ist: weiter 400 mit Grund (kein Geheimnis).
7. Historie: Liste für ein Objekt ohne eigenen Auftrag 403 mit Hinweis (das Objekt selbst ist für den Monteur offen, also kein
   Geheimnis), PDF 404. Der Weg „eigener Bericht“ zählt mit, ein Zeitfenster nicht.
8. „Erfasst von“ / „geschlossen von“ für jede Rolle aus der Anmeldung, auch Admin (vorher war der Admin frei); ein Konto ohne
   Mitarbeiter setzt leer. Mitgeschickt 422, auch mit dem eigenen Wert. Ändert das Büro ein Ergebnis nach, ist es danach
   „erfasst von“ (wie `recorded_at`). Bei „sofort behoben“ beim Anlegen gilt die Anmeldung, auch wenn ein Admin einen anderen
   Ersteller einträgt. `created_by_employee_id` an Bericht, Foto, Material, Mangel und Betriebsmittel bleibt bei
   `_employee_for_request()` (Admin frei) – nicht Teil der Vorgabe.
9. 2h: der Vorgang bekommt Kunde UND Objekt des Vertrags (Vertrag ohne Objekt: Projekt ohne Objekt = Hauptadresse). Ein
   Mustervorgang muss `is_template` tragen; dessen Kunde und Objekt spielen keine Rolle mehr. Ein schon gespeicherter, der keiner
   (mehr) ist, blockiert das Speichern nicht.
10. 2i: Ablehnung mit 400 und Grund (Büro-Weg, kein Geheimnis).
11. 2f/2g: Bestätigung nur bei einem neu gewählten Objekt; Übernahmen im Prozess bestätigen selbst (siehe oben).
12. Objektwechsel am Vertrag abgelehnt, solange irgendeine Position (auch archiviert) an einer Fläche eines anderen Objekts hängt –
    auch das Entfernen des Objekts.
13. `PUT /api/projects/{id}`: „Objekt gehört zum Kunden“ nur bei geändertem Kunden oder Objekt – sonst blockierte jedes Speichern
    eines bestätigten Vorgangs am Objekt eines anderen Kunden. Das Projektformular selbst bietet keine fremden Objekte an.
14. Strukturtest-Umfang: schreibende Routen (Body, Formular, Query) und Pfad-Paare jeder Methode; Lese-Filter (Query eines GET)
    nicht – sie speichern nichts, ihre Grenze ist die Rolle. Einordnung STAMMDATEN nach Feldname.
15. Neue Regel 25 in CLAUDE.md (Zugehörigkeit, Strukturtest), Verweis auf diese Datei in der Modulübersicht.

### Tests und Prüfung

- Die zehn xfail-Tests aus `test_v372_befund_fremdes_objekt.py` (2a ×2, 2b–2i) meldeten nach der Reparatur XPASS; Markierungen
  entfernt, sie sind die Abnahmetests.
- Neu `tests/test_v373_zugehoerigkeit.py` (30): je Weg fremd und unbekannt gleich (404), nichts angelegt, Büro dieselbe Antwort,
  Auftrag ohne Objekt, Bauteil auf anderer Fläche, Material POST/PUT, Rückfall der Vertragsposition; Historie (403/404, eigener
  Bericht, Büro, Objektansicht bleibt offen); „erfasst/geschlossen von“ (422 mit fremdem, eigenem, leerem Wert; aus der Anmeldung
  für Monteur, Büro, Admin ohne Mitarbeiter; „sofort behoben“); 2h auf Vertrags- und Positionsebene, Mustervorgang; 2i; 2f/2g mit
  und ohne Bestätigung, unverändert speichern, Positionen, „Wartung durchführen“ am bestätigten Objekt, Projekt speichern.
- Neu `tests/test_v373_zugehoerigkeit_struktur.py` (8, davon 2 Selbsttests der Suche).
- Angepasst (lose Testdaten bzw. alte Regel festgehalten): `test_v213`, `test_v214`, `test_v222`, `test_v223`, `test_v233`,
  `test_v234`, `test_v237` – der Auftrag hängt jetzt am Objekt der übergebenen Dachfläche (`_make_order_for_report(db, prop)`);
  `test_v267`, `test_v273` – der Monteur hat am Objekt einen eigenen Auftrag.
- Gegenproben (Regel 24): 14 von 14 rot – Dachfläche, Bauteil, Aufruf im Bericht, Historie, erfasst von (Schema, Anmeldung),
  geschlossen von (Schema, Ersteller), 2h, Mustervorgang, 2i, Bestätigung, Positionen beim Objektwechsel, Material nach altem
  Stand; jede Datei byte-genau zurück (SHA-256), kein Marker übrig.
- PostgreSQL (pytest-Plugin, Wegwerf-Schemas der lokalen Instanz): `test_v373_zugehoerigkeit.py` und
  `test_v372_befund_fremdes_objekt.py` 42 grün.
- Klicktest `scripts/klicktest_objekt_anderer_kunde.py` 21/21: Schnellauftrag (nur eigene Objekte, mit Häkchen die übrigen,
  Hinweis, ohne Bestätigung gesperrt und API 409, mit Bestätigung Auftrag für den Kunden am fremden Objekt), Vertragsanlage,
  Vertragsseite (vorgewählt „bestätigt“, unverändert speichern, neu gewählt wieder Rückfrage, dunkel), /mobil auf 412 px
  (Historie am Objekt des eigenen Auftrags, am fremden ein ruhiger Hinweis, Objektansicht offen). Dabei gefunden und behoben: die
  Seitenregel `.field label{display:block}` ließ das Häkchen im Hinweis am Text kleben.
- Volle Suite: 3178 grün, 0 rot, 34 erwartet fehlgeschlagen (die übrigen Punkte des Befunds; mit den opt-in-Tests gegen PostgreSQL).

### Nebenbefunde (nur gemeldet)

1. `POST`/`PUT /api/tasks` mit `project_id`: nicht einmal die Existenz wird geprüft – unter PostgreSQL 500 (Fremdschlüssel) bei
   einer unbekannten ID, unter SQLite bleibt sie stehen.
2. Schnellauftrag und Wartungsvertrag ohne Objekt: `customer_id` prüft nur der Fremdschlüssel (PostgreSQL 500 bei unbekanntem
   Kunden).
3. `PUT /api/roof-areas/{id}/layers/{layer_type_id}` prüft nicht, ob der Dachtyp des Schichttyps zur Fläche passt.
4. Die Reihenfolge-Endpunkte vergleichen Mengen – doppelte IDs gehen durch (harmlos).
5. Ein von Hand ergänzter Prüfpunkt wird gegen das Objekt geprüft, nicht gegen die Flächen des Berichts – Nebenbefund 1 oben
   (Punkt fehlt im PDF) bleibt so möglich.
6. Kundenwechsel einer Anfrage ist bis zur Projektanlage frei.
