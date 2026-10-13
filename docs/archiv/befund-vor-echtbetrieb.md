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
| `tests/test_v372_befund_schlussrechnung.py` | 1 | 7 (1c, 1e-1h seit 1.8.72 behoben, vorher 15) | 12 |
| `tests/test_v372_befund_fremdes_objekt.py` | 2 | 0 (seit 1.8.70 behoben, vorher 10) | 12 |
| `tests/test_v372_befund_abgleich.py` | 3 | 0 (seit 1.8.71 behoben, vorher 9) | 11 (5 nur PostgreSQL) |
| `tests/test_v372_befund_rechnungsdatum.py` | 4 | 4 (4d seit 1.8.71 behoben) | 3 |
| `tests/test_v372_befund_spaltenschluessel.py` | 5 | 0 (seit 1.8.71 behoben, vorher 5) | 7 (6 nur PostgreSQL) |

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

Entscheidungen dazu (10.10.2026, festgehalten, nicht gebaut): siehe "Entscheidungen Rechnungen" unten. **1c, 1e, 1f, 1g, 1h seit
1.8.72 behoben** (Sperren, siehe "Umsetzung 1.8.72"); 1a, 1b, 1d offen bis R4 -- bis dahin ist die Schlussrechnung neben einem
nicht stornierten pauschalen Abschlag gesperrt. Befund zu R4 (Schlussrechnung als Endrechnung, 12.10.2026): "Befund R4" unten.

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

**Seit 1.8.71 behoben**, siehe "Umsetzung 1.8.71".

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

4d seit 1.8.71 behoben ("Umsetzung 1.8.71"); 4a-4c seit 1.8.75 ("Umsetzung 1.8.75": Rechnungsdatum = Tag des Festschreibens in
Berlin, Fälligkeit rückt mit); Entscheidungen dazu unter "Entscheidungen Rechnungen".

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

**Seit 1.8.71 behoben**, siehe "Umsetzung 1.8.71".

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

### Festlegungen 1.8.70 (bestätigt am 10.10.2026, Vorgabe R2; Nr. 5 geändert, Nr. 7 erweitert gewünscht -- siehe dort)

1. 404-Texte „Dachfläche nicht gefunden.“ / „Bauteil nicht gefunden.“ – gleich für fremd und unbekannt. Die Prüfung sitzt in der
   Geschäftslogik und gilt für jede Rolle, auch fürs Büro.
2. Bauteil und Fläche beide angegeben: das Bauteil muss auf genau dieser Fläche sitzen (sonst 404 wie fremd).
3. Archivierte Dachflächen und Bauteile des eigenen Objekts bleiben erlaubt.
4. Auftrag ohne Objekt am Projekt (Hauptadresse): keine Dachfläche annehmbar – wie die Auswahl, die dort keine anbietet.
5. Ohne ausdrückliche Auswahl nimmt der Bericht die Fläche der Vertragsposition – gehört sie nicht zum Objekt des Auftrags, wird
   sie still weggelassen (kein Fehler), damit „Wartung durchführen“ an älteren Vorgängen nicht scheitert. **Geändert am
   10.10.2026 (in der Vorgabe „Zu 2“): nicht still** -- Hinweis am Bericht fürs Büro und `logger.warning`, kein Fehler für den
   Monteur. Gebaut in 1.8.71.
6. Material an einer Fläche des eigenen Objekts, die nicht am Bericht ist: weiter 400 mit Grund (kein Geheimnis).
7. Historie: Liste für ein Objekt ohne eigenen Auftrag 403 mit Hinweis (das Objekt selbst ist für den Monteur offen, also kein
   Geheimnis), PDF 404. Der Weg „eigener Bericht“ zählt mit, ein Zeitfenster nicht. **Am 10.10.2026 (in der Vorgabe „Zu 3“)
   gewünscht: Objektansicht und Dokumente in /mobil nach derselben Regel, einheitlich 404; hängt ein Ablauf an der offenen
   Ansicht, melden statt bauen** -- es hängen drei daran, gemeldet in 1.8.71 (siehe dort, „Zu 3“), nicht gebaut.
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

- **Nachtrag 1.8.71** (Frage „nur Testdaten oder auch Erwartungen?“): angepasst wurden 43 Testfunktionen in den neun Dateien
  unten (test_v213 13, test_v214 6, test_v222 7, test_v223 3, test_v233 1, test_v234 4, test_v237 4, test_v267 2, test_v273 3)
  und die Hilfsfunktionen `_make_order_for_report` (vier Dateien) und `_current_order_at` (neu). **Nur Testdaten**: im
  AST-Vergleich alter gegen neuer Stand ist keine `assert`-Anweisung geändert. Eine Erwartung lief danach aber über einen
  anderen Weg: `test_v223::test_add_material_rejects_roof_area_not_covered_by_report` übergab eine Fläche eines fremden Objekts,
  die seit 1.8.70 schon `require_in_order_property()` ablehnt (Text „Dachfläche nicht gefunden.“ erfüllt `"Dachfläche" in …`) --
  seit 1.8.71 prüft er wieder seinen Fall (Fläche des eigenen Objekts, nicht am Bericht, genauer Text).
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

## Umsetzung 1.8.71: Abgleich, Spaltenschlüssel, Auftragsdatum (Punkte 3, 5, 4d)

### Vorgabe vom 10.10.2026 (übernommen wie gegeben)

R2: Abgleich mit dem Angebot, Spaltenschlüssel und 4d (befund-vor-echtbetrieb.md, Punkte 3, 5 und 4d). Festlegungen 1.8.70 als
bestätigt markieren, mit diesen Änderungen:
- Zu 2: Eine Fläche der Vertragsposition aus einem fremden Objekt wird nicht still weggelassen: Hinweis am Bericht fürs Büro und
  logger.warning, kein Fehler für den Monteur.
- Zu 3: Objektansicht und Dokumente in /mobil nach derselben Regel wie die Historie; einheitlich 404 wie bei den übrigen fremden
  IDs. Hängt ein Ablauf an der offenen Ansicht: melden statt bauen.

Vorweg:
- task.project_id sowie customer_id bei Schnellauftrag und Vertrag ohne Objekt: Eine unbekannte ID ergibt 404 statt 500. Wie
  waren sie in test_v373 eingeordnet, dass der Test das nicht bemerkt hat? Lücke im Test schließen.
- Die 42 angepassten Alttests aus 1.8.70: nur Testdaten geändert oder auch Erwartungen? Falls Erwartungen: Liste.
- Ins Archiv befund-vor-echtbetrieb.md, Abschnitt „Entscheidungen Rechnungen“ (nur festhalten, nicht bauen): Schlussrechnung
  als Endrechnung, alle Positionen zu 100 %, Abzug aller festgeschriebenen, nicht stornierten Abschlagsrechnungen je mit Netto
  und USt, darunter „zzgl. noch offen aus Abschlag Nr. …“ und Zahlbetrag. Abschlagsrechnungen selbst nicht kumuliert. Offene
  Abschläge nach der Schlussrechnung nur noch über diese gemahnt. Zahlung auf den Zahlbetrag: Vorschlag zuerst auf offene
  Abschläge (ältester zuerst), dann Schlussrechnung, das Büro bestätigt. Rechnungsdatum = Tag der Ausgabe, jede Rechnung mit
  Pflicht-Leistungszeitraum, Nummer beim Festschreiben, Nummernkreise beim Start auf 1. Höchstens ein Storno je Rechnung, kein
  Storno eines Stornos. Keine mehreren Steuersätze je Rechnung.

1. Abgleich: gesperrt mit Begründung (409), sobald an den Positionen etwas hängt (Rechnung auch als Entwurf, Zeitbuchung,
   AV-Material), eine Abnahme besteht oder der Auftrag storniert oder abgeschlossen ist. Ist er erlaubt, funktioniert er auch mit
   Untertiteln unter PostgreSQL. Den Projektstatus fasst er nicht an.
2. Spaltenschlüssel von Aufgaben und Pipeline: gekürzt und eindeutig, passend zur kürzesten Spalte, in die er geschrieben wird.
   Muster: Abgeleitete Werte werden dort gekürzt, wo sie entstehen, gegen die Spaltenlänge aus dem Modell.
3. 4d: OrderCreateFromQuote ohne Rechner-Uhr; fehlt das Datum, gilt das Berliner Datum. Regel-20-Ausnahmeliste entsprechend
   kürzen.

Die xfail-Tests zu 3, 5 und 4d müssen grün werden, Markierung dann entfernen; test_v325 auch gegen PostgreSQL grün. Angriffstests
mit Gegenprobe. Eigene Festlegungen mit „Bitte bestätigen“. Nebenbefunde nur melden. Commit nach Regel 13, Bericht kurz.

### Vorweg

- **Wie waren sie eingeordnet?** Alle drei standen in `FREI` ("die ID legt den Besitzer bzw. Kontext fest -- jede vorhandene ist
  richtig"), die Aufgabe sogar mit dem Vermerk "Existenz prüft nur der Fremdschlüssel". `FREI` trug bis 1.8.70 nur einen Grund;
  der Test prüfte die Einordnung, nicht ob eine **unbekannte** ID abgefangen wird. **Lücke geschlossen**: jeder `FREI`-Eintrag
  trägt jetzt wie `GEPRUEFT` die Funktion und den Vergleich der Existenzprüfung, und der Test verlangt beides auf dem Weg vom
  Endpunkt (`test_geprueft_wird_vom_endpunkt_erreicht_und_enthaelt_den_vergleich`). Durchsicht der 30 `FREI`-Einträge: 26 prüften
  schon (404 bzw. 422), 4 nicht -- Aufgabe POST/PUT (`project_id`), Schnellauftrag und Wartungsvertrag ohne Objekt
  (`customer_id`; mit Objekt prüfte ihn `property_customer_mismatch()` nur, wenn das Objekt einem anderen Kunden gehört).
  Gebaut: `app/zugehoerigkeit.py::IdNichtGefunden` (ein `ValueError`, Router 404 mit Text), `require_customer()` (in
  `require_confirmed_property()` vor allem anderen, also auch ohne Objekt), `require_project()` (in `create_task()`/`update_task()`
  bei gesetzter ID). Ein unbekanntes Objekt beim Schnellauftrag und Vertrag (POST/PUT) antwortet seither ebenfalls 404 statt 400.
  Dieselbe Lücke hat `STAMMDATEN` (siehe Nebenbefunde).
- **Die angepassten Alttests aus 1.8.70**: 43 Testfunktionen (nicht 42), nur Testdaten, keine Erwartung geändert -- Einzelheiten
  oben unter "Umsetzung 1.8.70" -> "Tests und Prüfung" (Nachtrag), dort auch der eine Test, der seither über einen anderen Weg lief
  (`test_v223`, in 1.8.71 zurückgeholt).
- **Entscheidungen Rechnungen**: festgehalten im eigenen Abschnitt unten, nicht gebaut.
- **Festlegungen 1.8.70**: an der Überschrift als bestätigt markiert; Nr. 5 geändert (gebaut, siehe unten), Nr. 7 gemeldet.

### Was gebaut ist

- **Abgleich gesperrt** (`app/orders.py`): `sync_block_reasons()` sammelt die Gründe -- Auftrag `storniert` oder `abgeschlossen`;
  an einer Position hängt eine Rechnungsposition (`invoice_items.source_order_item_id`, jeder Status und jede Art), eine Zeitbuchung
  (`time_entries.order_item_id`) oder Gruppenbuchung (`time_entry_groups.order_item_id`), Material der Arbeitsvorbereitung
  (`work_preparation_materials.source_order_item_id` oder `source_material_snapshot_id`). `sync_block_text()` macht daraus
  "Der Abgleich mit dem Angebot ist gesperrt: …; …. Änderungen (z. B. Nachträge) direkt am Auftrag erfassen." mit Rechnungsnummern
  bzw. Anzahl der Entwürfe und Anzahl der Buchungen und Materialzeilen. `sync_order_from_source_quote()` wirft nach Vertrag und
  Abnahme (unverändert) `SyncBlockedError` (ein `ValueError`), der Router antwortet 409. Vorher nichts geändert, keine Revision.
  Die Freigabe des AV-Materials vor dem Ersetzen entfällt (es sperrt jetzt); eine Arbeitsvorbereitung ohne Material bekommt nach
  dem Abgleich das Material der neuen Positionen (`refresh_preparation_materials()`).
- **Untertitel unter PostgreSQL**: `_copy_quote_scope_to_order()` löscht erst die Positionen, löst dann `parent_id` aller Titel des
  Auftrags und löscht sie danach -- vorher in einem Flush in beliebiger Reihenfolge (`order_sections_parent_id_fkey`).
- **Projektstatus**: der Abgleich setzt ihn nicht mehr; das Angebot bleibt "beauftragt" wie bisher.
- **Oberfläche**: `order_to_dict()` liefert `source_quote_sync_blocked` (der Text, nur wenn der Auftrag vom Angebot abweicht).
  Auftragsseite: Karte "Quellangebot geändert" mit dem Grund statt des Knopfs (nach den Hinweisen zu Abnahme und Vertrag).
  Angebots-Editor: bei Sperre (Grund oder Abnahme) "Auftrag … öffnen" statt "Änderungen … übernehmen", der Grund im Hinweis.
- **Spaltenschlüssel** (`app/spaltenlaenge.py`): `laenge(*spalten)` liest die kürzeste Länge aus dem Modell,
  `eindeutig_gekuerzt(basis, max_laenge, belegt)` kürzt, lässt ein "_" am Ende weg und hängt bei Gleichheit "_2", "_3" … an (die
  Basis dafür weiter gekürzt). Aufgabenspalte: `laenge(TaskColumn.key, Task.status)` = 30, Pipelinespalte:
  `laenge(ProjectPipelineColumn.key)` = 40 (Projekte verweisen über die ID). Muster im Moduldocstring; Gegenstück für feste Werte
  bleibt `test_v364`.
- **4d**: `OrderCreateFromQuote.order_date = Field(default_factory=berlin_today)`; Eintrag aus `BEKANNTE_VORGABEN` gestrichen (jetzt
  fünf).
- **Zu 2 -- Fläche der Vertragsposition aus einem fremden Objekt** (`app/service_reports.py`): der Bericht entsteht weiter ohne sie
  (kein Fehler für den Monteur), dazu `logger.warning` mit Bericht, Fläche, Vertragsposition und Auftrag -- nur IDs (Regel 18).
  `contract_area_hint()` rechnet den Hinweis live aus Vertragsposition und Auftrag; die Büro-Liste
  (`GET /api/orders/{id}/service-reports`, nicht `field`) liefert ihn als `office_hint`, `service_reports.html` zeigt ihn über dem
  Bericht. Der Monteur bekommt seine Berichte über `ServiceReportOut`, das das Feld nicht kennt.

### Zu 3 -- gemeldet, nicht gebaut

An der offenen Objektansicht in /mobil hängen drei Abläufe:

1. **Objektsuche in der Kopfzeile** jeder Monteursseite (`_mobile_header.html`, `GET /api/field-view/properties/search`,
   `app/search.py`): findet jedes Objekt und verlinkt auf `/mobil/objekt/{id}` -- der Hauptweg zu einem Objekt ohne eigenen Auftrag.
2. **Dateiablage je Objekt** (Betreiberentscheidung, `docs/archiv/rechtekonzept.md` "jeder Mitarbeiter -- auch Monteure -- kann
  Bilder und Dokumente zu einem Objekt hochladen und ansehen", "ein Monteur erreicht JEDES Objekt über seine ID"): Dokumentliste,
  Ansehen/Laden und Upload (`app/routers/field_view.py`, `mobil_objekt.html`).
3. **Checklisten im Kontext Objekt** (Betreiberentscheidung A, `docs/archiv/modul-checklisten.md`): angelegt aus der Objektansicht
  (`_checklists_section.html`), Rücksprung `checklist.html` -> `/mobil/objekt/{id}`; die Checkliste speichert Objektname, Adresse
  und Kunde (`app/checklists.py::_context_snapshot()`) -- auch bei gesperrter Ansicht ein Weg zu diesen Daten.

Die Sperre würde diese drei Entscheidungen zurücknehmen; dazu bräche `test_v267` (sieben Tests: "fremdes Objekt öffnen -- erlaubt"),
`test_v373::test_history_only_for_properties_of_own_orders` (Objektansicht/Dokumente 200), `test_v260` (`/mobil/objekt/1`) und
der Klicktest `klicktest_objekt_anderer_kunde.py`. "Einheitlich 404" beträfe auch die Historie selbst: heute Liste 403 mit
ruhigem Hinweis, PDF 404 "Bericht nicht gefunden." (unbekanntes Objekt "Objekt nicht gefunden.").

**Entscheidung (10.10.2026, Vorgabe R3):** Objektsuche, Dateiablage und Checklisten am Objekt bleiben für Monteure offen; die
Wartungshistorie bleibt auf die Objekte eigener Aufträge beschränkt, die Liste darf dort mit Hinweis 403 antworten (PDF weiter 404).
Damit ist der Wunsch "Objektansicht und Dokumente nach derselben Regel, einheitlich 404" (Festlegung 1.8.70 Nr. 7) erledigt -- es
bleibt beim Stand von 1.8.70. Vermerkt auch in `docs/archiv/rechtekonzept.md` (Nachtrag 1.8.70).

### Festlegungen 1.8.71 (bestätigt am 10.10.2026, Vorgabe R3)

1. "Rechnung an einer Position" = jede Rechnungsposition mit Bezug auf eine Position des Auftrags, jeder Status und jede Art (auch
   Entwurf, Storno, stornierte Rechnung) -- an allen hängt der Fremdschlüssel. Ein pauschaler Abschlag (Position ohne Bezug) sperrt
   nicht.
2. Zeitbuchung: Einzel- und Gruppenbuchung mit Position, auch eine laufende; eine Buchung nur auf den Auftrag sperrt nicht.
3. AV-Material: jede Materialzeile mit Bezug auf eine Position oder deren Kalkulation. Da es aus der Kalkulation entsteht, sperrt
   praktisch jede Arbeitsvorbereitung mit kalkuliertem Material den Abgleich; eine ohne Material nicht.
4. Abnahme: wie seit 1.8.46 nur eine nicht verworfene; der unterschriebene Vertrag sperrt weiter.
5. Status: nur "storniert" und "abgeschlossen" sperren ("pausiert", "in_ausfuehrung", "arbeitsvorbereitung" nicht).
6. Die Sperre greift vor dem Vergleich: auch ein Auftrag ohne Abweichung antwortet 409 (wie Vertrag und Abnahme). Die Oberfläche
   bietet den Abgleich ohnehin nur bei Abweichung an.
7. Alle Gründe auf einmal, Rechnungen mit Nummer (Entwürfe als Anzahl), Buchungen und Material als Anzahl.
8. Spaltenschlüssel: Kürzung ohne Rücksicht auf Wortgrenzen. Bestehende Schlüssel werden nicht umbenannt (keine Migration). Auf dem
   Server zu prüfen (nur lesen): `SELECT key FROM task_columns WHERE length(key) > 30;` -- ein Treffer kann keine Aufgabe aufnehmen;
   steht er vorn, scheitert jede neue Aufgabe ohne Status. Bei Treffern: melden, dann eine Migration.
9. Unbekannte ID: 404 mit Text "Projekt nicht gefunden." / "Kunde nicht gefunden." / "Objekt nicht gefunden." (Büro-Wege, kein
   Geheimnis); das unbekannte Objekt bei Schnellauftrag und Vertrag dabei 400 -> 404 (`test_v373` angepasst).
10. Aufgabe: Projekt nur bei gesetzter ID geprüft, `null` bleibt erlaubt; auch die Aufgaben aus Modulen (Mangel, Folgen) laufen
    über die Prüfung.
11. Hinweis fürs Büro: live gerechnet, keine neue Spalte -- erscheint auch an Berichten vor 1.8.71 und verschwindet, wenn der Vertrag
    korrigiert ist; ebenso bei ausdrücklicher Flächenwahl, wenn die Fläche der Vertragsposition fremd ist (sie steht dann ebenfalls
    nicht im Bericht). Er nennt Fläche und Objekt (nur Büro).
12. `FREI` verlangt die Existenzprüfung, `STAMMDATEN` nicht (unverändert, siehe Nebenbefunde).

### Tests und Prüfung

- xfail entfernt: `test_v372_befund_abgleich.py` 3a-3e (9), `test_v372_befund_spaltenschluessel.py` 5a-5c (5),
  `test_v372_befund_rechnungsdatum.py` 4d (1). 3e prüft jetzt zusätzlich: mit Untertiteln gelingt der Abgleich (Baum und Zuordnung
  der Position), mit Zeitbuchung oder Rechnung ist er gesperrt. Angepasst, weil das Verhalten sich gewollt ändert: der grün
  festgehaltene "Schlüssel ungekürzt"-Test (jetzt: gekürzt, auch unter SQLite) und die Vorbedingung von 5c (verlangte den
  40 Zeichen langen Schlüssel, aus dem der Fehler entstand).
- Neu: `test_v374_abgleich_sperre.py` (20), `test_v374_spaltenlaenge.py` (12, einer gegen PostgreSQL),
  `test_v374_unbekannte_ids_und_hinweis.py` (11); Strukturtest mit Existenzprüfung für `FREI`.
- Erwartung geändert: `test_v373::test_quick_order_at_a_property_of_another_customer_needs_confirmation` (unbekanntes Objekt 400
  -> 404); `test_v316` ein Eintrag weniger; `test_v223::test_add_material_rejects_roof_area_not_covered_by_report` wieder auf
  seinen Fall (genauer Text).
- Gegenproben (Regel 24): 20 von 20 rot -- Status, Rechnung, Zeitbuchung, Gruppenbuchung allein, AV-Material über Position und
  über Kalkulation, Projektstatus, Untertitel (PostgreSQL, auch `test_v325`), Router 409, Aufgabenspalte gekürzt und gegen
  `Task.status`, Pipelinespalte, Eindeutigkeit mit Anhang, 4d (auch `test_v316`), Projekt der Aufgabe (Anlegen, Prüffunktion
  samt Strukturtest), Kunde vorhanden, Router 404, Hinweis, Warnung. Die Gegenprobe "Gruppenbuchung allein" war zuerst falsch
  gebaut (die Einzelbuchungen der Gruppe sperrten ohnehin, Test grün) -- neuer Test mit Gruppenbuchung ohne Einzelbuchung an der
  Position, dann rot. Jede Datei byte-genau zurück (SHA-256), kein Marker übrig.
- PostgreSQL (pytest-Plugin, Wegwerf-Schemas der lokalen Instanz): `test_v374_*` (3 Dateien), `test_v373_zugehoerigkeit`, die vier
  Befunddateien zu 2-5, `test_v325_quote_order_copy_fields` (Untertitel), `test_v081`, `test_v223`: 139 grün, 4 erwartet
  fehlgeschlagen (4a-4c, offen).
- Klicktest `scripts/klicktest_abgleich_sperre.py` 13/13: gesperrter Auftrag zeigt den Grund ohne Knopf (hell/dunkel), API 409;
  freier Auftrag gleicht ab, Projektstatus bleibt "ausfuehrung"; Angebots-Editor "Auftrag … öffnen" mit Grund; Einsatzbericht:
  Hinweis fürs Büro (hell/dunkel), Monteurin auf 412 px ohne Hinweis und ohne Namen des fremden Objekts.
- Volle Suite (mit den opt-in-Tests gegen PostgreSQL): 3236 grün, 0 rot, 19 erwartet fehlgeschlagen (Punkt 1: 15, 4a-4c: 4).

### Nebenbefunde (nur gemeldet)

1. **`STAMMDATEN` hat dieselbe Lücke wie `FREI` bis 1.8.70**: 100 ID-Eingaben (35 Feldnamen) sind nach Feldname eingeordnet, ohne
   dass der Test eine Existenzprüfung verlangt. Beispiel laut Code: `POST /api/tasks` mit unbekanntem `assigned_employee_id` --
   `create_task()` prüft nicht, unter PostgreSQL 500 am Fremdschlüssel.
2. **Gleichzeitig angelegte Rechnung**: die Prüfung im Abgleich sperrt die Zeile des Auftrags (über die Abnahme-Prüfung), das
   Anlegen einer Rechnung nicht. Unter PostgreSQL scheitert im Wettlauf eine Seite am Fremdschlüssel (500, kein Schaden); unter
   SQLite bleibt ein schmales Fenster.
3. **Auftragsseite und Angebots-Editor bei 1280 px Breite**: der Inhalt läuft rechts über (waagrechte Scrollleiste, Spaltenkopf
   "GP" bzw. "Gesamtpreis" unter der Seitenspalte) -- in den Screenshots des Klicktests sichtbar, unabhängig von dieser Änderung,
   nicht weiter geprüft.
4. Der Angebots-Editor kennt den unterschriebenen Vertrag nicht (`OrderOut` ohne Vertragsstatus): dort bleibt der Knopf
   "Änderungen … übernehmen", der Klick antwortet 409 mit Text (wie bisher).

## Umsetzung 1.8.72: Rechnungen, Teil 1 (Punkt 1: 1c, 1e-1h)

### Vorgabe vom 10.10.2026 (übernommen wie gegeben)

R3 Rechnungen, Teil 1 (befund-vor-echtbetrieb.md, Punkt 1; Entscheidungen Rechnungen im Archiv). Festlegungen 1.8.71 als bestätigt
markieren. Zu 3 ins Archiv als Entscheidung: Objektsuche, Dateiablage und Checklisten am Objekt bleiben für Monteure offen; die
Historie bleibt auf eigene Aufträge beschränkt, die Liste darf dort mit Hinweis 403 antworten.

Befund vorab, nur lesen, im Bericht mit Fundstellen:
a) Zahlungseingänge: Wie werden sie heute erfasst (Betrag, Teilzahlung, Datum, Skonto)? Gibt es offene Posten je Rechnung?
b) Rechnungsnummer: Wird sie beim Entwurf oder beim Festschreiben vergeben? Lassen sich Entwürfe löschen, entstehen Lücken?
c) Leistungszeitraum: Gibt es ihn an Rechnung, Auftrag oder Einsatzbericht? Woraus ließe er sich vorschlagen?

Bauen:
1. Höchstens eine gültige Schlussrechnung je Auftrag, auch als Entwurf (1c). Nach einer festgeschriebenen Schlussrechnung keine
   weiteren Abschläge.
2. Höchstens ein Storno je Rechnung, kein Storno eines Stornos (1e, 1f).
3. Kein Storno eines Abschlags, solange eine gültige Schlussrechnung besteht (1g).
4. Mahnung: Entwurf und Versand prüfen unter Sperre, dass die Rechnung weder storniert noch bezahlt ist (1h).
5. Bis R4: Schlussrechnung gesperrt (409 mit Begründung), solange am Auftrag ein nicht stornierter pauschaler Abschlag besteht.

Die xfail-Tests zu 1c, 1e, 1f, 1g und 1h müssen grün werden, Markierung dann entfernen; die übrigen bleiben. Angriffstests mit
Gegenprobe, Gleichzeitigkeit gegen PostgreSQL. Eigene Festlegungen mit „Bitte bestätigen“. Nebenbefunde nur melden. Commit nach
Regel 13, Bericht kurz.

### Vorweg

- **Festlegungen 1.8.71**: an der Überschrift als bestätigt markiert.
- **Zu 3**: als Entscheidung festgehalten unter "Umsetzung 1.8.71" -> "Zu 3", Verweis in `rechtekonzept.md` (Nachtrag 1.8.70).
  Nichts gebaut, Stand von 1.8.70 bleibt.

### Befund vorab (nur gelesen; Zeilen nach dem Stand 1.8.72)

**a) Zahlungseingänge.** Es gibt keine. "Bezahlt" ist ein Status mit Datum: `mark_invoice_paid()` (`app/invoices.py:691`) setzt
`status="bezahlt"` und `paid_date` (`models.py:1659`) -- kein Betrag, keine Teilzahlung, kein Skonto-Abzug, keine Zahlungstabelle.
`POST /api/invoices/{id}/mark-paid` nimmt nur `paid_date` (`InvoiceMarkPaid`, `schemas.py:2120`), die Rechnungsseite schickt nicht
einmal das (`markPaid()`, `invoice_detail.html:190`: leerer Body -> `berlin_today()`). Skonto steht nur als eingefrorene Bedingung an
der Rechnung (`skonto_percent`/`skonto_days`) und im Zahlungssatz (`format_payment_terms_sentence()`, `:834`); ob es gezogen wurde,
hält nichts fest. **Offene Posten je Rechnung gibt es nicht**: offen = Status `versendet`, der offene Betrag ist immer der volle
Bruttobetrag -- in der Mahnung (`Reminder.outstanding_amount = gross_total` beim Anlegen, `reminders.py:211`), in der
Mahnwesen-Liste (`:457`) und in Finanzen/Dashboard ("Offener Betrag" = Summe der versendeten, `finanzen.html:47`,
`dashboard.html:137`). "Noch offen" am Auftrag (`orders.py:471`) heißt "noch nicht abgerechnet", nicht "noch nicht bezahlt".
Zahlungsstatus mit Datum gibt es nur an Eingangsrechnungen (`IncomingInvoice.payment_status`/`payment_date`, Buchhaltung).

**b) Rechnungsnummer.** Vergeben beim Festschreiben, nicht beim Entwurf: `finalize_and_send_invoice()` ->
`issue_number(db, "invoice")` (`invoices.py:680`, `settings.py:157`); der Entwurf hat `invoice_number = NULL`. Entwürfe lassen sich
löschen (`delete_invoice_draft()`, `:705`, nur Status `entwurf`) -- das reißt keine Lücke. Lücken und Doppel entstehen anders:
- **Doppelte Nummer bei gleichzeitigem Festschreiben -- nachgestellt (PostgreSQL)**: zwei Schlussrechnungen verschiedener
  Aufträge gleichzeitig festgeschrieben (Commit der ersten eine Sekunde angehalten) -> beide `R-2026-0001`. `issue_number()` liest
  den Nummernkreis ohne Sperre (`load_sequence()`), das UPDATE der zweiten wartet zwar auf die erste, schreibt dann aber denselben
  Folgewert; `invoices.invoice_number` hat nur einen Index, keine Eindeutigkeit (`models.py:1653`). Gilt für jeden Nummernkreis
  (Mahnung, Auftrag, Angebot, Projekt …). Die Sperre aus 1.8.72 hilft nur innerhalb eines Auftrags.
- **Entwurf gelöscht, während er festgeschrieben wird -- nachgestellt (PostgreSQL)**: `delete_invoice_draft()` prüft den Status ohne
  Sperre; das DELETE wartet auf das Festschreiben und löscht danach die festgeschriebene Rechnung samt Positionen. Ergebnis: Nummer
  vergeben, Rechnung weg -- eine Lücke.
- Von Hand: Einstellungen -> Nummernkreise setzt `next_value` frei (`update_sequence()`, `settings.py:167`); nach vorn entsteht eine
  Lücke, nach hinten zieht `_sync_from_existing()` (`:76`) auf die höchste vorhandene Nummer des Musters im laufenden Jahr nach.
  Jahreswechsel mit `reset_yearly` (`:142`) beginnt neu (gewollt).
- Stornorechnungen ziehen aus demselben Nummernkreis (gewollt).

**c) Leistungszeitraum.** An der Rechnung nicht (kein Feld, kein Text im PDF). Am Auftrag geplant: `execution_start`/
`execution_end` (Datum, `models.py:1033-1034`, aus dem Beauftragen-Dialog, auf der Auftragsseite änderbar) und `execution_period`
(Freitext aus dem Angebot, `:1038`; ebenso am Vertragsentwurf, `:1442`); Auftrags-PDF und Vertrag zeigen sie
(`orders.py::execution_period_text()`). Am Einsatzbericht `performed_at` (ein Tag). Woraus sich ein Vorschlag ableiten ließe, je
Auftrag: Arbeitstage der gebuchten Zeiten (`TimeEntry.work_date`, `TimeEntryGroup.work_date`, `order_id`), Einsatzberichte
(`ServiceReport.performed_at`), Plantafel (`PlanningSlot.start_date`/`end_date` über die Arbeitsvorbereitung des Auftrags), Abnahme
(`OrderAcceptance.accepted_on`, nicht verworfen -- Ende der Leistung für die Schlussrechnung), geplanter Zeitraum am Auftrag, und für
den nächsten Abschlag das Ende des Zeitraums des vorigen. Nicht gebaut.

### Was gebaut ist

- **Sperre** `app/invoices.py::lock_order_invoices()`: dieselbe Zeile wie Abnahme und Abgleich (`acceptances.lock_order()`, Auftrag
  `FOR UPDATE`), danach Auftrag und alle seine Rechnungen frisch geladen (`populate_existing`). Genommen von: Abschlag pauschal und
  nach Leistungsstand anlegen, Schlussrechnung anlegen, Festschreiben (jede Art, auch Storno), Storno-Entwurf anlegen, "bezahlt",
  Mahnung anlegen und festschreiben. Ein zweites gleichzeitiges Festschreiben desselben Entwurfs (Rechnung oder Mahnung) findet ihn
  danach festgeschrieben (400) statt eine zweite Nummer zu ziehen.
- **Gründe** (reine Funktionen über die Rechnungen des Auftrags): `create_block_reason()`, `finalize_block_reason()`,
  `storno_block_reason()`; Fehler `InvoiceBlocked` (ein `ValueError`), Router 409 mit dem Text.
  1. Schlussrechnung anlegen: gesperrt, solange eine nicht stornierte besteht, auch ein Entwurf ("Am Auftrag besteht schon eine
     Schlussrechnung (R-… / ein Entwurf). Eine weitere ist erst möglich, wenn sie storniert bzw. der Entwurf gelöscht ist.").
     Festschreiben: gesperrt neben einer festgeschriebenen (Altbestand mit zwei Entwürfen). Abschläge (beide Arten) anlegen und
     festschreiben: gesperrt nach einer festgeschriebenen Schlussrechnung.
  2. Storno: keins einer Stornorechnung; keins, wenn schon eines besteht (beim Anlegen auch ein Entwurf, beim Festschreiben nur ein
     festgeschriebenes); keins einer schon stornierten Rechnung (jetzt 409 mit der Nummer des Stornos, vorher 400).
  3. Storno eines Abschlags: gesperrt, solange eine festgeschriebene, nicht stornierte Schlussrechnung besteht ("… zuerst die
     Schlussrechnung stornieren"); beim Anlegen und beim Festschreiben eines älteren Storno-Entwurfs.
  4. Mahnung (`app/reminders.py::send_block_reason()`): Anlegen und Festschreiben unter der Sperre, nicht zu einer stornierten oder
     bezahlten Rechnung ("Die Rechnung R-… ist bezahlt (am …) -- dazu geht keine Mahnung mehr hinaus."); dazu der E-Mail-Versand einer
     schon festgeschriebenen Mahnung (Prüfung ohne Sperre). Ein Entwurf bekommt dann keine Nummer.
  5. Bis R4: Schlussrechnung anlegen und festschreiben gesperrt neben einem nicht stornierten pauschalen Abschlag (auch Entwurf):
     "Die Schlussrechnung ist vorerst gesperrt: am Auftrag besteht ein pauschaler Abschlag (R-…). Die Schlussrechnung zieht pauschale
     Abschläge noch nicht ab -- der Auftrag wäre doppelt abgerechnet."
- **Oberfläche** (Grund statt Knopf, Muster 1.8.71): Auftragsseite "Neue Rechnung" -- je gewählter Art der Grund
  (`order_to_dict()["invoice_create_blocks"]`), der Knopf "Rechnung anlegen" fehlt; nach "Löschen" eines Entwurfs in der Liste neu
  geladen. Rechnungsseite: `finalize_block` statt "Rechnung finalisieren" ("Entwurf löschen" bleibt), `storno_block` statt
  "Stornieren" (`invoice_to_dict()`). Mahnwesen, "Alle Mahnungen": `send_block` statt "Versenden" bzw. E-Mail-Feld.
- Moduldocstring `app/invoices.py` ("Sperren") und der veraltete Verweis auf `berechne_abgerechnete_menge()` (Nebenbefund 7)
  korrigiert.

### Festlegungen 1.8.72 (Rückmeldung 10.10.2026, Vorgabe 1.8.73)

Der Bericht nannte sieben Punkte (Nr. 7 dort = Nr. 8 hier; Nr. 7 und 9 hier standen nicht im Bericht). Bestätigt: 1, 2, 4,
6. Nr. 5 als Übergang bestätigt, der Sperrtext nennt seit 1.8.73 den Ausweg. Nr. 3 offen, nichts ändern. Nr. 8 gilt für die
Geschäftsregeln, nicht für Rechnungsnummern (dort ist eine Datenbank-Bedingung vorgesehen, siehe "Umsetzung 1.8.73"). Nr. 7 und 9
unbestätigt; aus Nr. 9 ist "Entwurf löschen" seit 1.8.73 unter der Sperre. **Nr. 7 bestätigt, Nr. 9 nicht (Vorgabe 1.8.75)** --
seit 1.8.75 laufen auch die übrigen dort genannten Wege unter der Sperre ("Umsetzung 1.8.75").

1. "Gültig" heißt festgeschrieben und nicht storniert (`versendet`/`bezahlt`). Wo die Vorgabe "auch als Entwurf" sagt (Punkt 1,
   Anlegen der Schlussrechnung), zählt der Entwurf mit; Punkt 3 nur die festgeschriebene -- ein Entwurf der Schlussrechnung sperrt
   das Storno eines Abschlags nicht (dass er dann falsch rechnet, ist 1b, R4).
2. Beim Festschreiben sperrt nur eine schon festgeschriebene Schlussrechnung bzw. ein festgeschriebenes Storno -- Altbestand mit zwei
   Entwürfen: der zuerst festgeschriebene gilt, der andere bleibt Entwurf ohne Nummer (löschbar).
3. "Keine weiteren Abschläge" gilt für pauschal und nach Leistungsstand, beim Anlegen und beim Festschreiben eines älteren Entwurfs.
   Ein Entwurf der Schlussrechnung sperrt keinen Abschlag. **"Rechnung aus Aufwand" bleibt nach der Schlussrechnung möglich** (kein
   Abschlag, nicht Teil der Vorgabe). **Offen (10.10.2026): nichts ändern.** **Entschieden am 12.10.2026: nach der
   Schlussrechnung keine Rechnung aus Aufwand im selben Auftrag** (festgehalten, nicht gebaut -- "Entscheidungen Rechnungen").
4. Storno: auch ein Storno-Entwurf zählt beim Anlegen (wie bei der Schlussrechnung) -- ein zweiter Klick auf "Stornieren" antwortet
   409 statt eines zweiten Entwurfs. Storno eines Entwurfs bleibt 400 wie bisher; Storno einer schon stornierten Rechnung jetzt 409.
5. Punkt 5: jeder pauschale Abschlag, der nicht `storniert` ist -- auch ein Entwurf -- sperrt Anlegen und Festschreiben der
   Schlussrechnung. Ein pauschaler Abschlag darf neben einem Schlussrechnungs-Entwurf entstehen; dann ist dessen Festschreiben
   gesperrt. Der Text nennt Grund und Nummern, keinen Ausweg (ob stornieren oder auf R4 warten, entscheidet das Büro).
   **Als Übergang bestätigt; seit 1.8.73 mit Ausweg**: nur Entwürfe -> "Ausweg: den Entwurf löschen.", sonst "Schlussrechnungen
   mit pauschalen Abschlägen kommen mit R4."
6. Mahnung: zusätzlich zur Vorgabe auch der E-Mail-Versand einer schon festgeschriebenen Mahnung nach Storno oder Zahlung gesperrt --
   ohne Sperre der Auftragszeile, weil der Versand sie sonst über die Verbindung zum Mailserver hielte. Ein vorhandener Entwurf bleibt
   stehen (löschbar), die Mahnwesen-Liste nennt den Grund. Bezahlt markieren und Storno löschen keine Mahnungsentwürfe.
7. Alle neuen Sperren 409 mit Text; vorhandene 400 (Entwurf stornieren, zu einem Entwurf mahnen, bezahlt nur aus "versendet")
   bleiben.
8. Keine Datenbank-Bedingung (eindeutiger Teilindex je Auftrag bzw. Original): Altbestand könnte sie verletzen und die Migration auf
   dem Server scheitern lassen. Prüfabfragen 1c/1e/1f oben. Unter SQLite (nur Entwicklung) wirkt `FOR UPDATE` nicht.
   **Gilt nur für die Geschäftsregeln, nicht für Rechnungsnummern** (Rückmeldung 10.10.2026).
9. Nicht unter der Sperre (nicht Teil der Vorgabe): "Rechnung aus Aufwand" anlegen, Positionen und Kopf bearbeiten, Entwurf löschen
   (siehe Nebenbefund 2). Seit 1.8.73 ist "Entwurf löschen" unter der Sperre. **Nicht bestätigt -- seit 1.8.75 alle unter der
   Sperre.**

### Tests und Prüfung

- `test_v372_befund_schlussrechnung.py`: xfail entfernt bei 1c (3), 1e, 1f, 1g, 1h (2) -- 8 grün. Bei 1c (zwei Entwürfe) und 1e
  läuft jetzt auch das **zweite Anlegen** über `_versuch()`, weil die Reparatur schon dort ablehnt (vorher nur das Festschreiben);
  keine `assert`-Zeile geändert. 1a bleibt xfail, der Weg angepasst: die Schlussrechnung läuft über `_versuch()` (bis R4 gesperrt),
  und der Test verlangt **zusätzlich eine gültige Schlussrechnung** -- ohne sie wäre `test_lump_sum_then_progress…` zufällig grün
  (2.000 pauschal + 60 % = 5.000). 1b und 1d unverändert. Mit `--runxfail` scheitern alle sieben an ihrer Prüfung.
- Angepasst (nur Testdaten): `test_v324::test_manual_delivery_rights_and_documents` brauchte einen Entwurf und legte dafür eine
  zweite Schlussrechnung neben der festgeschriebenen an -- jetzt ein Storno-Entwurf; Erwartung unverändert.
- Neu `tests/test_v375_rechnungen_sperren.py` (41, davon 11 gegen PostgreSQL): je Regel Anlegen und Festschreiben, Altbestand mit
  zwei Entwürfen (Schluss, Storno, Storno eines Stornos), Nummernkreis bleibt bei Ablehnung, Aufwand nach Schluss, pauschal in drei
  Zuständen, nach Storno/Löschen frei; Mahnung anlegen, festschreiben, E-Mail; Router 409/400; Gründe in Auftrag, Rechnung, Mahnung.
  **Gleichzeitig (PostgreSQL, Commit der ersten Aktion eine Sekunde angehalten, die zweite lädt vorher ihre Objekte wie der Router):**
  zwei Schlussrechnungen, zwei Stornos, Storno des Abschlags gegen Festschreiben der Schluss, Abschlagsentwurf gegen Schluss,
  Schluss gegen pauschalen Abschlag, derselbe Entwurf zweimal (eine Nummer), Mahnung gegen Storno und gegen "bezahlt", neue Mahnung
  gegen "bezahlt", dieselbe Mahnung zweimal -- jeweils wartet die zweite (≥ 0,9 s) und wird abgelehnt.
- Gegenproben (Regel 24): 16 von 16 rot -- zweite Schluss beim Anlegen und beim Festschreiben, Abschlag nach Schluss, Storno eines
  Stornos, zweites Storno, Storno hinter der Schluss, pauschal, Mahnung (Status), Mahnung (E-Mail), Sperre der Auftragszeile, frisches
  Laden nach der Sperre, Sperre beim Bezahlen, Router Rechnungen und Mahnungen (409), Anzeige an Rechnung und Auftrag. Die letzte war
  zuerst falsch gebaut (der Marker-Kommentar verschluckte den Rest der Zeile: Syntaxfehler statt Gegenprobe) -- neu gebaut, dann rot.
  Jede Datei byte-genau zurück (SHA-256), kein Marker übrig.
- Klicktest `scripts/klicktest_rechnungen_sperren.py` 21/21: Auftragsseite (Schluss neben pauschal mit Grund und API 409, nach der
  Schluss Abschläge und zweite Schluss gesperrt, freier Auftrag mit Knopf, Schluss-Entwurf in der Liste gelöscht -> frei),
  Rechnungsseite (Abschlagsentwurf ohne Finalisieren, verrechneter Abschlag ohne Stornieren, Stornorechnung; hell und dunkel),
  Mahnwesen (Entwurf zu bezahlter Rechnung mit Grund, API 409).
- PostgreSQL über das pytest-Plugin (Wegwerf-Schemas der lokalen Instanz): `test_v372_befund_schlussrechnung`, `test_v375`,
  `test_v133`, `test_v141`, `test_v143`, `test_v153`, `test_v236`, `test_v240`, `test_v315`, `test_v374_abgleich_sperre`: 191 grün,
  7 erwartet fehlgeschlagen (1a, 1b, 1d).
- Volle Suite (mit den opt-in-Tests gegen PostgreSQL, Arbeitskopie): 3285 grün, 0 rot, 11 erwartet fehlgeschlagen (Punkt 1: 7,
  4a-4c: 4). Danach nur noch ein Kommentar in `app/reminders.py` geändert; Kontrolle `test_v375`, `test_v372_befund_schlussrechnung`,
  `test_v153`, `test_v236`: 87 grün, 7 erwartet fehlgeschlagen.

### Nebenbefunde (nur gemeldet)

1. **(seit 1.8.73 behoben)** **Doppelte Nummern bei gleichzeitigem Festschreiben** (siehe b, nachgestellt): `issue_number()` ohne Sperre des Nummernkreises,
   keine Eindeutigkeit an `invoices.invoice_number` -- betrifft alle Nummernkreise. GoBD-relevant.
2. **(seit 1.8.73 behoben)** **Entwurf löschen gegen Festschreiben** (siehe b, nachgestellt): `delete_invoice_draft()` ohne Sperre löscht unter PostgreSQL eine
   gerade festgeschriebene Rechnung.
3. **Finanzen und Dashboard zählen Stornorechnungen als offen**: "Offene Rechnungen"/"Offener Betrag" = alle mit Status `versendet`
   (`finanzen.html:47`, `dashboard.html:137`) -- eine Stornorechnung bleibt `versendet` und geht mit negativem Betrag in den offenen
   Betrag ein, während ihr Original als `storniert` herausfällt.
4. **"+ Position hinzufügen" auf einer festgeschriebenen Rechnung**: der Knopf in der Positionskarte (`invoice_detail.html`, Zeile 20)
   wird nicht ausgeblendet; der Server lehnt ab (400).
5. Ein Mahnungsentwurf derselben Stufe lässt sich zweimal anlegen (`create_reminder()` prüft keinen vorhandenen Entwurf); die
   Mahnwesen-Übersicht zeigt nur einen davon.

## Umsetzung 1.8.73: Nummernvergabe und Entwurf löschen unter Sperre (Nebenbefunde 1 und 2 aus 1.8.72)

### Vorgabe vom 10.10.2026 (übernommen wie gegeben)

1.8.72 geprüft. Festlegungen 1, 2, 4, 6 bestätigt.
5: als Übergang bestätigt. Der Sperrtext soll den Ausweg nennen: bei Entwurf „Entwurf löschen“, sonst, dass Schlussrechnungen mit
pauschalen Abschlägen mit R4 kommen.
3: offen, nichts ändern.
7: gilt für die Geschäftsregeln, nicht für Rechnungsnummern.

1.8.73 – Nebenbefunde 1 und 2:
- Nummernvergabe je Nummernkreis atomar unter Sperre, für alle Nummernkreise.
- Entwurf löschen unter derselben Sperre wie Festschreiben. Gelöscht wird nur, was nach der Sperre noch Entwurf ist, sonst 409.
- Nebenläufigkeitstests unter PostgreSQL mit Gegenprobe, wie in deinem Nachweis.
- Eindeutige Nummer als Datenbank-Bedingung: noch keine Migration. Liefere eine SQL-Abfrage, die auf dem Server Dubletten und
  Lücken je Nummernkreis zeigt.

Befund, nichts bauen:
a) Wie geht eine Rechnung aus Aufwand heute in die Schlussrechnung ein (Gesamtwert, Abzug oder gar nicht)?
b) Wie ist der Neustart der Nummernkreise auf 1 zum Echtbetrieb vorgesehen, und was passiert dabei mit vorhandenen Rechnungen?

### Vorweg

- Festlegungen 1.8.72 markiert (an der Überschrift, Nummern wie im Archiv -- "7" der Rückmeldung ist dort Nr. 8).
- Nr. 5: der Sperrtext nennt den Ausweg (`app/invoices.py::_lump_sum_reason()`): nur Entwürfe -> "Ausweg: den Entwurf löschen."
  (bzw. "die Entwürfe"), sonst -- mindestens ein festgeschriebener -- "Schlussrechnungen mit pauschalen Abschlägen kommen mit R4."

### Was gebaut ist

- **Nummernvergabe atomar** (`app/settings.py`): `issue_number()` sperrt zuerst die Zeile des Nummernkreises (`_lock_sequence()`:
  ein UPDATE ohne Änderung -- unter PostgreSQL die Zeilensperre, unter SQLite die Schreibsperre der Datenbank) und lädt sie danach
  frisch (`populate_existing`); Jahreswechsel, Abgleich mit den vorhandenen Nummern und Hochzählen laufen so je Nummernkreis
  nacheinander, die Sperre hält bis zum Commit des Aufrufers. Wird er zurückgerollt, ist die Nummer nicht verbraucht.
- **Alle sieben Nummernkreise** vergeben darüber: Kunde, Anfrage, Projekt und Angebot liefen bis 1.8.72 über `preview_number()`
  ("höchste vorhandene + 1", ohne Hochzählen) -- zwei gleichzeitig angelegte scheiterten am Eindeutigkeitsindex (500); jetzt
  `next_customer_number()`, `next_inquiry_number()`, `next_project_number()`, `next_quote_number()` -> `issue_number()`.
  `preview_number()` ist nur noch Anzeige (Kundennummer im Formular, Einstellungen); ein Strukturtest prüft die Aufrufer.
- **Entwurf löschen** (`delete_invoice_draft()`, `delete_reminder_draft()`): unter derselben Sperre wie das Festschreiben
  (`lock_order_invoices()`, Auftragszeile), danach frisch geprüft -- nur ein Entwurf wird gelöscht, sonst 409 "Nur Rechnungen im
  Entwurf können gelöscht werden. Die Rechnung ist inzwischen festgeschrieben (R-…)." (vorher 400 ohne Nummer); schon gelöscht:
  409 "Der Entwurf wurde inzwischen gelöscht.". Umgekehrt findet das Festschreiben einen inzwischen gelöschten Entwurf nicht mehr
  und antwortet 409, ohne eine Nummer zu verbrauchen (Rechnung und Mahnung; vorher 500 am Speichern).
- **Prüfabfrage** `scripts/pruefabfrage_nummernkreise.sql` (siehe unten), keine Migration.

### Prüfabfrage: Dubletten und Lücken je Nummernkreis

`scripts/pruefabfrage_nummernkreise.sql`, nur lesen, auf dem Server z. B. `psql -d dachkonzepte -f scripts/pruefabfrage_nummernkreise.sql`.
Drei Ergebnisse:

1. **Dubletten** je Nummernkreis (Kunde, Anfrage, Projekt, Angebot, Auftrag, Rechnung inkl. Storno, Mahnung), unabhängig vom Format.
2. **Lücken** je Nummernkreis und Gruppe (alles außer der laufenden Nummer, z. B. "R-2026-…", also je Jahr): erste, letzte, Anzahl,
   fehlende dazwischen (bis 50 aufgelistet) und fehlende vor der ersten, gemessen am Startwert. Das Format kommt aus
   `number_sequences.format_pattern` (`{YYYY}`, `{YY}`, `{N…}`); nur Nummern im aktuellen Format zählen.
3. **Anderes Format** (Altsystem, früheres Format, von Hand): Anzahl und bis zu 20 Beispiele -- für Lücken nicht gezählt.

Entwürfe ohne Nummer zählen nicht. Geprüft auf einem Wegwerf-Schema der lokalen PostgreSQL mit eingebauter Dublette, Lücke, zwei
Jahren, fremden Formaten und Entwürfen: alle Fälle richtig erkannt. Gegen echte Daten ist sie nicht gelaufen (Regel 16). Eine Lücke
bei Kunde, Anfrage, Projekt, Angebot oder Auftrag kann vom Löschen kommen (seit 1.8.73 zählen auch die ersten vier hoch), bei
Rechnung und Mahnung ist sie erklärungsbedürftig.

### Befund (nichts gebaut)

**a) Rechnung aus Aufwand und Schlussrechnung: gar nicht.** Die Rechnung aus Aufwand (`create_invoice_from_time_entries()`,
`invoices.py:475`) hat nur Positionen ohne Bezug zum Auftrag (`source_order_item_id = NULL`: Zeit je Mitarbeiter und Tätigkeit,
Material); die Schlussrechnung setzt jede Auftragsposition auf 100 % und zieht nur Abschläge nach Leistungsstand derselben Position ab
(`get_previous_cumulative_ist()`, `:265`) -- die Aufwand-Rechnung ist weder im Gesamtwert enthalten noch abgezogen, sie kommt
obendrauf. Nachgerechnet (Wegwerf-SQLite): Auftrag 5.000 € netto, Aufwand 10 h × 82 € = 820 €, Schlussrechnung 5.000 €; der Auftrag
zeigt "abgerechnet 5.820 €, noch offen −820 €" (`compute_order_billing_progress()`, `:996`, zählt die Aufwand-Rechnung mit). Auch ein
Abschlag nach Leistungsstand kennt sie nicht (40 % = 2.000 € unabhängig davon).
- Beim **Schnellauftrag** (eine Position "Reparatur/Wartung nach Aufwand", 1 × 0 €, `quick_service_orders.py`) ist das gewollt: die
  Schlussrechnung lautet über 0 €, die Aufwand-Rechnung ist die eigentliche Rechnung.
- Beim **Auftrag aus einem Angebot mit Preisen** wird dieselbe Leistung doppelt berechnet, wenn die Stunden zu einer LV-Position
  gehören: die Zeitbuchung trägt `order_item_id`, die Aufwand-Rechnung übernimmt ihn nicht und berechnet die Stunden zusätzlich zum
  Einheitspreis der Position.
- Dieselben Buchungen lassen sich in eine zweite Aufwand-Rechnung übernehmen (bekannt, CLAUDE.md "Keine Doppel-Abrechnungs-Sperre").
- Nach der Schlussrechnung bleibt sie möglich (Festlegung 1.8.72 Nr. 3, offen), ihr Storno ebenso (kein Abschlag).
- Für R4 (Endrechnung mit Abzug der Abschläge) ist offen, ob und wie Aufwand-Rechnungen darin erscheinen.

**b) Neustart der Nummernkreise auf 1.** **Vorgesehen ist dafür nichts außer der Entscheidung** ("Nummernkreise beim Start auf 1",
"Entscheidungen Rechnungen"): kein Skript, keine Migration, keine Funktion. Was heute möglich ist und was dabei passiert:
- **Jahreswechsel**: alle sieben Nummernkreise haben im Standard `{YYYY}` im Format und `reset_yearly` -- bei der ersten Nummer im
  neuen Jahr beginnen sie von selbst beim Startwert (`_apply_year_reset()`, `settings.py:142`). Beginnt der Echtbetrieb am
  01.01.2027, steht jede Nummer ohnehin bei 1; die Nummern von 2026 bleiben, wie sie sind.
- **Anderes Format** (Einstellungen -> Nummernkreise, z. B. "RE-{YYYY}-{NNNN}"): beginnt bei der eingetragenen Nummer; die alten
  behalten ihr Format, keine Überschneidung.
- **Gleiches Format, gleiches Jahr, "nächste Nummer" = 1** (`update_sequence()`, `:191`, PUT `/api/settings/number-sequences/{key}`):
  - Kunde, Anfrage, Projekt, Angebot, Auftrag: der Abgleich mit den vorhandenen Nummern (`_sync_from_existing()`, `:76`) hebt die
    nächste Nummer wieder über die höchste vorhandene -- ein Neustart findet still nicht statt.
  - **Rechnung und Mahnung: kein Abgleich** (`_existing_column()`, `:56`, kennt sie nicht) -- die nächste festgeschriebene Rechnung
    bekommt eine schon vergebene Nummer. **Nachgestellt (Wegwerf-SQLite): R-2026-0001 vorhanden, "nächste Nummer" 1 gespeichert, das
    nächste Festschreiben vergibt wieder R-2026-0001.** Die Vorschau in den Einstellungen zeigt dabei "R-2026-0001" ohne Warnung.
- **Vorhandene Rechnungen**: bleiben in jedem Fall unverändert -- Nummer, Status, PDF in der unveränderlichen Ablage, Einträge im
  Versandprotokoll. In der App lassen sie sich nicht entfernen (nur Entwürfe löschbar, Projekte mit Auftrag nur archivierbar, Ablage
  und Protokoll unveränderlich); sie bleiben in Finanzen, Dashboard und Mahnwesen sichtbar, überfällige versendete bekommen beim
  Öffnen des Mahnwesens Mahnungsentwürfe (automatische Entwürfe, wenn eingeschaltet). Ein Neustart im selben Format und Jahr ohne
  Dubletten hieße, diese Rechnungen außerhalb der App zu entfernen -- gegen Ablage und Protokoll, und unzulässig, falls eine davon
  echt hinausging. Zu entscheiden: Jahreswechsel bzw. neues Format, neue Datenbank mit übernommenen Stammdaten, oder die
  Probe-Rechnungen stehen lassen (stornieren).
- Mit der vorgesehenen eindeutigen Rechnungsnummer (Datenbank-Bedingung) schlüge eine solche Dublette am Speichern fehl (500) statt
  still zu entstehen. **Seit 1.8.77 gebaut** (alle sieben Nummernkreise, "Umsetzung 1.8.77"); die Vergabe springt seit 1.8.74/1.8.76
  ohnehin über vergebene Nummern.

### Festlegungen 1.8.73 (bestätigt am 10.10.2026, Vorgabe 1.8.74)

1. Gesperrt wird mit einem UPDATE ohne Änderung statt `SELECT … FOR UPDATE` -- dieselbe Wirkung unter PostgreSQL, dazu unter SQLite
   (Entwicklung) die Schreibsperre der Datenbank; die Sperre hält bis zum Commit. Ein Ablauf, der mehrere Nummern zieht
   (Schnellauftrag: Projekt, Angebot, Auftrag), hält sie bis zum Ende; gleichzeitige Anlagen derselben Art warten kurz.
2. Kunde, Anfrage, Projekt und Angebot zählen jetzt hoch: eine gelöschte Nummer wird nicht wieder vergeben (vorher die nächste freie
   über der höchsten). Die Kundennummer wird wie bisher nur beim ersten Anlegen des Profils gezogen -- auch über die zwei GET-Routen,
   die ein fehlendes Profil nachlegen (`GET /api/customers`, `/{id}`). **Seit 1.8.76 eingeengt: die GET-Routen legen kein Profil
   mehr an (eine Anzeige verbraucht keine Nummer, "Umsetzung 1.8.76").**
3. Auch der **Mahnungsentwurf** wird unter der Sperre gelöscht (die Vorgabe nennt "Entwurf löschen" allgemein, Nebenbefund 2 betraf
   Rechnungen).
4. Löschen eines nicht (mehr) vorhandenen Entwurfs: 409 "inzwischen gelöscht", nicht 404. Ein festgeschriebener: 409 mit Nummer.
5. Gemischt (festgeschriebener und Entwurf eines pauschalen Abschlags): der Text nennt R4, nicht das Löschen.

### Tests und Prüfung

- Neu `tests/test_v376_nummernkreise.py` (19): je Nummernkreis zwei gleichzeitige Vergaben unter PostgreSQL (7, die zweite Sitzung hält
  den alten Stand des Nummernkreises), zwei Rechnungen verschiedener Aufträge gleichzeitig (der Nachweis aus 1.8.72, Nebenbefund 1),
  Löschen gegen Festschreiben in beiden Reihenfolgen für Rechnung und Mahnung (Nebenbefund 2, ohne verbrauchte Nummer), zwei
  gleichzeitige Vergaben unter SQLite mit Datei (2), Hochzählen statt Vorschau, Rückrollen, Strukturtest der Vorschau-Aufrufer,
  409 beim Löschen über die Router, Löschen von Entwürfen.
- `test_v375`: Sperrtext mit Ausweg (Erwartung geändert, wie gewünscht), dazu der gemischte Fall.
- Gegenproben (Regel 24): 11 von 11 rot -- Sperre des Nummernkreises, frisch lesen nach der Sperre, Projektnummer über die Vorschau,
  Löschen ohne Sperre, Festschreiben eines gelöschten Entwurfs, 409 statt 400 (Geschäftslogik, Router Rechnung, Router Mahnung),
  Mahnungsentwurf löschen ohne Sperre, Mahnung gelöschter Entwurf, Ausweg im Text. "Frisch lesen" blieb zuerst grün: der Test lud den
  Nummernkreis vorher, hielt das Objekt aber nicht fest (die Sitzung hält unveränderte Objekte nur schwach, es wurde neu geladen) --
  Test korrigiert, dann rot. Jede Datei byte-genau zurück (SHA-256), kein Marker übrig.
- Klicktest `klicktest_rechnungen_sperren.py` erweitert, 24/24: Ausweg "R4" am festgeschriebenen pauschalen Abschlag, Ausweg "Entwurf
  löschen" am Entwurf, danach gelöscht und frei.
- Erwartung geändert: `test_projects.py::test_project_number_sequence` rief `next_project_number()` einmal nur zum Nachsehen auf
  (Vorschau-Logik) -- jetzt zieht jeder Aufruf eine Nummer; der Test nimmt die erste für das Projekt und erwartet danach 0002.
- PostgreSQL über das pytest-Plugin (Wegwerf-Schemas): `test_v376`, `test_v375`, `test_projects`, `test_v051`, `test_inquiries`,
  `test_v05`, `test_v133`, `test_v153`, `test_v192`, `test_v209`: 135 grün, 1 rot (`test_project_number_sequence`, siehe oben) --
  nach der Anpassung `test_projects` unter SQLite und PostgreSQL 3 grün.
- Volle Suite (mit den opt-in-Tests gegen PostgreSQL, Arbeitskopie): 3304 grün, 11 erwartet fehlgeschlagen, 1 rot (derselbe Test,
  danach angepasst und grün). Sonst nur Doku geändert; VERSION/Strukturtests im Hauptbaum 21 grün.

### Nebenbefunde (nur gemeldet)

1. **Rechnungs- und Mahnungsnummer ohne Abgleich mit den vorhandenen** (siehe b): "nächste Nummer" zurückgesetzt -> Dublette, ohne
   Warnung. GoBD-relevant; die übrigen fünf Nummernkreise haben den Abgleich.
2. `_sync_from_existing()` lädt bei jeder Vergabe alle Nummern der Tabelle und prüft sie in Python -- wächst mit dem Bestand.

## Umsetzung 1.8.74: Leistungszeitraum, nächste Nummer nicht auf oder unter eine vergebene

### Vorgabe vom 10.10.2026 (übernommen wie gegeben)

1.8.73 geprüft, Festlegungen 1–5 bestätigt.
Bitte im nächsten Bericht:
- welcher Test rot war und welche Erwartung du geändert hast (eine Zeile),
- Archiv-Punkte 7 und 9 aus „Umsetzung 1.8.72“ im Wortlaut.

1.8.74:
- Einstellungen, alle sieben Nummernkreise: Die nächste Nummer darf nicht auf oder unter eine vorhandene Nummer desselben Formats
  und Jahres gesetzt werden. Ablehnung mit Meldung, die die höchste vergebene Nummer nennt; kein stilles Überspringen.
- Leistungszeitraum (Regel: jede Rechnung hat einen):
  - Felder Beginn/Ende an der Rechnung, Ende ≥ Beginn, auf dem PDF. Pflicht beim Festschreiben, sonst 409 mit Grund.
  - Vorschlag im Entwurf mit Quellenangabe, Übernahme per Klick, nicht still eintragen:
    - Abschlag: erste bis letzte Zeitbuchung nach Ende des Zeitraums des vorigen gültigen Abschlags.
    - Rechnung aus Aufwand: erste bis letzte abgerechnete Zeitbuchung.
    - Schlussrechnung: erste Zeitbuchung des Auftrags bis Abnahmedatum, ohne Abnahme bis letzte Zeitbuchung.
    - Ohne Zeitbuchungen: geplanter Zeitraum des Auftrags.
  - Storno übernimmt den Zeitraum der stornierten Rechnung.
  - Festgeschriebener Altbestand bleibt unverändert.
- Tests mit Gegenprobe.
Die Datenbank-Bedingung für eindeutige Nummern folgt nach meiner Prüfabfrage auf dem Server.

### Vorweg

- Festlegungen 1.8.73 an der Überschrift als bestätigt markiert.
- Der rote Test in 1.8.73: `tests/test_projects.py::test_project_number_sequence` -- er rief `next_project_number()` einmal nur zum
  Nachsehen auf (erwartete "…0001", nahm für das Projekt dieselbe Nummer und danach "…0002"); jetzt bekommt das Projekt die erste
  gezogene Nummer, danach "…0002".
- Archiv-Punkte 7 und 9 aus "Umsetzung 1.8.72" stehen dort unverändert (bei 9 seit 1.8.73 der Zusatz zu "Entwurf löschen").

### Was gebaut ist

- **Nächste Nummer** (`app/settings.py::update_sequence()`, alle sieben Nummernkreise): liegt sie auf oder unter der höchsten
  vergebenen Nummer desselben Formats im laufenden Jahr (Berlin; ein Format ohne Jahr gegen alle Nummern dieses Formats), lehnt das
  Speichern mit 409 ab: "Die nächste Nummer darf nicht auf oder unter einer vergebenen liegen: höchste vergebene Nummer in diesem Format
  ist R-2026-0042 -- nächste Nummer mindestens 43." Nichts wird gespeichert (`NumberBelowExisting`, `highest_existing()`). Vorher sprang
  die Vorschau danach still über die vergebenen -- bei Rechnung und Mahnung nicht einmal das: `_existing_column()` kennt sie jetzt
  (Nebenbefund 1 aus 1.8.73). Die Vergabe selbst gleicht weiter mit den vergebenen ab (Sicherheitsnetz, Festlegung 2).
- **Leistungszeitraum** (`Invoice.service_period_start/_end`, Migration `9b4e2c7a1d58`, `app/service_period.py`):
  - Pflicht beim Festschreiben, jede Art auch Storno: fehlt Beginn oder Ende oder liegt das Ende vor dem Beginn, antwortet
    Festschreiben 409 mit Grund ("Der Leistungszeitraum fehlt (Ende) -- jede Rechnung braucht einen. …"); die Rechnungsseite zeigt
    den Grund statt "Rechnung finalisieren" (`finalize_block`, nach den Sperren aus 1.8.72).
  - Speichern im Entwurf über den Rechnungskopf (`PUT /api/invoices/{id}`, je Feld einzeln): Ende vor Beginn -- auch gegen den
    gespeicherten Wert der anderen Seite -- 400 mit Grund.
  - PDF unter der Überschrift: "Leistungszeitraum: 01.09.2026 bis 18.09.2026", an einem Tag "Leistungsdatum: 08.09.2026".
  - Storno übernimmt Beginn und Ende der stornierten Rechnung beim Anlegen.
  - Vorschlag im Entwurf (`invoice_to_dict()["service_period_proposal"]`: Beginn, Ende, Quelle), nur gelesen; die Rechnungsseite
    zeigt ihn mit Quelle und "Übernehmen" (speichert beide Felder); ohne Daten den Grund, warum es keinen gibt.
  - Rechnung aus Aufwand hält beim Anlegen den ersten und letzten Arbeitstag der übernommenen Buchungen fest
    (`Invoice.billed_work_from/_to`) -- welche Buchungen abgerechnet wurden, stand sonst nirgends.
  - Altbestand: keine Spalte wird befüllt; festgeschriebene Rechnungen ohne Zeitraum bleiben, wie sie waren (PDF ohne Zeile,
    unveränderlich).

### Festlegungen 1.8.74 (bestätigt am 10.10.2026; Nr. 2 geändert, Vorgabe 1.8.75)

1. Nächste Nummer: Ablehnung mit 409 (die übrigen Fehler der Seite bleiben 422). Gemessen am neuen Format im laufenden Jahr; die
   Startnummer prüft nichts (sie gilt erst beim Jahreswechsel).
2. Die Vergabe springt weiter still über vergebene Nummern, wenn die nächste Nummer an den Einstellungen vorbei darunter liegt
   (Nummer von Hand, Import, Datenbank) -- statt das Festschreiben einer Rechnung zu blockieren. "Kein stilles Überspringen" gilt für
   das Speichern in den Einstellungen. **Geändert (Vorgabe 1.8.75): das Überspringen bleibt, aber nicht still -- `logger.warning` mit
   Nummernkreis und übersprungenen Nummern** (gebaut in 1.8.76).
3. Pflicht für jede Rechnungsart, auch Storno. Storno einer Rechnung ohne Zeitraum (vor 1.8.74): kein Vorschlag, von Hand eintragen.
4. Zeitbuchungen im Vorschlag: gebucht, mit Stunden, ohne Schlechtwetter -- dieselbe Auswahl wie die Rechnung aus Aufwand; Fahrzeit
   zählt.
5. Abschlag: "vorig" sind alle festgeschriebenen, nicht stornierten Abschläge (beide Arten) desselben Auftrags mit Zeitraum, maßgeblich
   das späteste Ende; einer ohne Zeitraum (Altbestand) zählt nicht. Gibt es Buchungen, aber keine danach: kein Vorschlag (mit Grund),
   nicht der geplante Zeitraum.
6. Schluss: Abnahmedatum = jüngstes Datum einer nicht verworfenen Abnahme "abgenommen"; eine verweigerte zählt nicht. Liegt es vor der
   ersten Buchung: bis zur letzten Buchung, mit Hinweis.
7. Ohne Zeitbuchungen am Auftrag: geplanter Zeitraum; ist nur Beginn oder Ende geplant, schlägt der Vorschlag nur dieses vor. Aufwand
   nur mit Material (oder vor 1.8.74 angelegt): ebenfalls der geplante Zeitraum.
8. Ende vor Beginn: beim Speichern 400 (wie die übrigen Fehler im Rechnungskopf), beim Festschreiben 409. Keine Datenbank-Bedingung
   (Geschäftsregel, wie 1.8.72 Nr. 8).
9. "Übernehmen" speichert sofort; das Ändern eines Datumsfelds speichert nur dieses Feld.

### Tests und Prüfung

- Neu `tests/test_v377_leistungszeitraum.py` (26): nächste Nummer je Nummernkreis (7) auf und unter der höchsten abgelehnt, darüber
  gespeichert; Vorjahr und anderes Format sperren nicht; Route 409 mit Nummer, nichts gespeichert; Vergabe überspringt eine vergebene
  Rechnungsnummer statt sie doppelt zu vergeben. Leistungszeitraum: Pflicht (409, nichts vergeben), Ende vor Beginn beim Speichern
  (auch einseitig) und beim Festschreiben, PDF (Zeitraum, ein Tag), Storno übernimmt, Altbestand und sein Storno, Vorschlag je Art
  (geplant, Abschlag nach dem vorigen, ohne neue Buchungen, stornierter zählt nicht, Schluss bis Abnahme mit verweigerter und
  verworfener, Aufwand ohne später gebuchte), nichts still eingetragen, Übernahme per PUT, Seite.
- **Testdaten angepasst** (Pflicht beim Festschreiben): neuer Helfer `tests/leistungszeitraum.py::festschreiben()` (trägt in einen
  Entwurf ohne Zeitraum einen ein, über denselben Weg wie "Übernehmen", dann Festschreiben) in 16 Testdateien statt
  `finalize_and_send_invoice()`; in den Gleichzeitigkeitstests trägt die Vorbereitung den Zeitraum ein (die erste Aktion soll nur beim
  Festschreiben anhalten); über die API ein PUT vor `/send`. `test_v372_befund_schlussrechnung` 1d setzt den Zeitraum direkt (das
  Kopf-Update hätte die fehlende Position der pauschalen Altrechnung wieder angelegt) -- 1d bleibt xfail aus seinem Grund.
  `test_v227`/`test_v231`: die Spaltensuche im PDF findet "Leistung" als ganzes Wort (sonst "Leistungszeitraum").
- **Erwartung geändert**: `test_v375::test_invoice_dict_carries_both_reasons_and_order_dict_without_db_has_none` -- ein Entwurf
  ohne Zeitraum hat jetzt einen Grund (`finalize_block` = Leistungszeitraum fehlt) statt keinen.
- Gegenproben (Regel 24): 13 von 13 rot -- Ablehnung der nächsten Nummer, Rechnung im Abgleich, Pflicht beim Festschreiben, Ende vor
  Beginn beim Speichern und beim Festschreiben, PDF-Zeile, Storno übernimmt, Aufwand-Buchungstage, Abschlag nach dem vorigen,
  stornierte zählen nicht, Schluss bis zur Abnahme, ohne Schlechtwetter, Vorschlag nur im Entwurf. Jede Datei byte-genau zurück
  (SHA-256), kein Marker übrig.
- Migration `9b4e2c7a1d58`: SQLite (Wegwerf-Datei) und PostgreSQL (Wegwerf-Schema mit einer Rechnung als Bestand): hoch, `current`
  head, `check` ohne Unterschied, Bestand leer, `downgrade` mit gespeichertem Zeitraum verweigert, ohne erlaubt, wieder hoch.
- Klicktests: neu `klicktest_leistungszeitraum.py` 16/16 (Vorschlag mit Quelle, Grund statt Finalisieren, nichts still
  eingetragen, Übernehmen, Ende vor Beginn, Finalisieren; geplanter Zeitraum; Nummernkreis-Meldung mit der höchsten, nichts
  gespeichert; hell und dunkel). Mit Zeitraum in `befuellen()`: `klicktest_rechnungen_sperren` 24/24, `klicktest_rechnung_rundung`
  10/10, `klicktest_versandprotokoll` 45/45, `klicktest_versandverlauf` 31/32 (die eine rote Prüfung ist auf 1.8.73 genauso rot,
  Nebenbefund 1).
- PostgreSQL über das pytest-Plugin (Wegwerf-Schemas): `test_v377`, `test_v375`, `test_v376`, `test_v133`, `test_v153`,
  `test_v051`, `test_v143`, die Befunddateien zu Punkt 1 und 4: 156 grün, 11 erwartet fehlgeschlagen (1a, 1b, 1d, 4a-4c).
- Volle Suite (mit den opt-in-Tests gegen PostgreSQL, Arbeitskopie): 3331 grün, 0 rot, 11 erwartet fehlgeschlagen (1a, 1b, 1d,
  4a-4c). Danach nur Doku geändert.

### Nebenbefunde (nur gemeldet)

1. `klicktest_versandverlauf.py`: "Checkliste: PDF-Knopf weiter in voller Auflösung (über 3 MB)" ist rot -- auch auf dem Stand
   1.8.73 (in einer Arbeitskopie nachgeprüft), also nicht von dieser Änderung; nicht untersucht.
2. Einstellungen -> Nummernkreise: der Text "Die Rechnungs- und Auftragsnummernkreise werden bereits gespeichert und später vom
   jeweiligen Modul verwendet." ist veraltet (beide werden längst verwendet).
3. Ein Format ohne Jahr mit "Jahreswechsel: auf Startnummer zurück" setzt die nächste Nummer zum Jahreswechsel auf die Startnummer --
   die Vergabe springt dann still über die vergebenen (Festlegung 2); die Einstellungen warnen vor der Kombination nicht.

## Umsetzung 1.8.75: Rechnungsdatum = Tag des Festschreibens, jeder schreibende Weg an einer Rechnung unter der Sperre (4a-4c, Punkte 1 und 2)

### Vorgabe vom 10.10.2026 (übernommen wie gegeben)

1.8.74 geprüft. Festlegungen 1.8.74 bestätigt, mit einer Änderung zu 2: Die Vergabe springt weiter über eine vergebene Nummer, aber
nicht still: logger.warning mit Nummernkreis und übersprungenen Nummern. Archiv-Punkt 7 aus 1.8.72 bestätigt; Punkt 9 nicht, siehe 2.

1.8.75:
1. Rechnungsdatum = Tag des Festschreibens in Berliner Zeit (Tag der Ausgabe). Fälligkeit und Skonto werden beim Festschreiben ab
   diesem Datum gerechnet. Beim Versand an einem späteren Tag ein Hinweis. Die xfail-Tests 4a–4c müssen grün werden;
   Regel-20-Ausnahmeliste kürzen.
2. Rechnung aus Aufwand anlegen sowie Positionen und Kopf bearbeiten unter derselben Sperre wie das Festschreiben; geändert wird nur,
   was danach noch Entwurf ist, sonst 409. Strukturtest: Jeder schreibende Weg an einer Rechnung läuft unter dieser Sperre.
3. Nummern: Gibt es Aufrufer, die eine Nummer nur anzeigen wollen und seit 1.8.73 eine verbrauchen (Vorschau in Einstellungen oder
   Formularen)? Liste aller Aufrufer; eine Anzeige darf nie eine Nummer verbrauchen.
4. Einstellungen: Format ohne Jahr zusammen mit „Jahreswechsel: auf Startnummer zurück“ wird abgelehnt (409 mit Grund). Den
   veralteten Satz unter Nummernkreise entfernen.
5. Klicktests: Ist die rote Prüfung in klicktest_versandverlauf.py durch Festlegung 3 aus 1.8.66 überholt? Dann Erwartung anpassen.
   Dazu ein Skript, das alle Klicktests nacheinander laufen lässt; Laufzeit melden.

Angriffstests mit Gegenprobe, Gleichzeitigkeit gegen PostgreSQL. Eigene Festlegungen mit „Bitte bestätigen“. Nebenbefunde nur
melden. Wird der Umfang zu groß: nach Punkt 2 committen und den Rest auflisten. Commit nach Regel 13, Bericht kurz.

### Vorweg

- Festlegungen 1.8.74 an der Überschrift als bestätigt markiert, Nr. 2 mit der Änderung (Warnung im Log) -- gebaut in 1.8.76.
- Festlegungen 1.8.72: Nr. 7 bestätigt; Nr. 9 nicht -- die dort genannten Wege ("aus Aufwand" anlegen, Positionen und Kopf
  bearbeiten) laufen seit 1.8.75 unter der Sperre (Punkt 2).
- Umfang: nach Punkt 2 committet (1.8.75), Punkte 3-5 als eigene Version 1.8.76 (siehe dort).

### Was gebaut ist

- **Rechnungsdatum = Tag des Festschreibens** (`app/invoices.py::finalize_dates()`, aufgerufen in `finalize_and_send_invoice()`):
  das Festschreiben setzt `invoice_date` auf `berlin_today()` -- jede Art, auch Storno. Die Fälligkeit behält das Zahlungsziel des
  Entwurfs (Tage zwischen seinem Datum und seiner Fälligkeit, aus der Zahlungsbedingung oder wie angegeben) und rückt mit; ohne
  Fälligkeit (Storno) bleibt sie leer. Das Skontodatum rechnet ohnehin ab `invoice_date` (`format_payment_terms_sentence()`), also
  ebenfalls ab dem Tag des Festschreibens. Die Nummer nimmt wie bisher das Berliner Jahr -- an Silvester passen Datum und Nummer.
- **Entwurf**: trägt bis dahin das Datum seines Anlegens, ausdrücklich aus `berlin_today()` (`_default_invoice_header_fields()`,
  Storno-Entwurf ebenso) -- dieselbe Uhr wie die Fälligkeit beim Anlegen (4b). Die Rechnungsseite zeigt unter den Rechnungsdaten,
  was das Finalisieren heute setzen würde ("Finalisiert heute: Rechnungsdatum …, fällig …", `invoice_to_dict()["finalize_dates"]`,
  nur gelesen); der Statustext nennt es beim Finalisieren mit.
- **Hinweis beim späteren Versand** (`send_hint()`, `invoice_to_dict()["send_hint"]`): eine festgeschriebene, nicht bezahlte Rechnung,
  deren Rechnungsdatum vor heute liegt, zeigt über "Per E-Mail senden": "Die Rechnung ist vom … (Tag des Finalisierens), heute ist
  der …. Fälligkeit (…) und Skontofrist (bis …) rechnen ab dem Rechnungsdatum, nicht ab dem Versand." -- dazu "Die Fälligkeit ist
  schon überschritten." bzw. "Die Skontofrist ist schon abgelaufen.". Nur ein Hinweis, der Versand bleibt möglich.
- **Regel-20-Ausnahmeliste leer**: die fünf Spaltenvorgaben (`Invoice.invoice_date`, `Order.order_date`, `Reminder.reminder_date`,
  `ServiceReport.performed_at`, `QuoteDocumentMeta.quote_date`) nehmen `berlin_today()` statt `date.today`; `BEKANNTE_VORGABEN` in
  `test_v316_berlin_time.py` ist leer. Die vier übrigen griffen ohnehin nirgends (Befund Punkt 4, "Die übrigen Fälle").
- **Jeder schreibende Weg an einer Rechnung unter der Sperre** (`lock_order_invoices()`, Auftragszeile): neu `_lock_draft()` vor
  jeder Änderung an einem Entwurf -- Positionen hinzufügen, ändern, entfernen, Kopf (auch Pauschalbetrag und Leistungszeitraum),
  Zahlungsbedingung, Steuerschlüssel. Danach sind Rechnung und Positionen frisch geladen; geändert wird nur, was noch Entwurf ist,
  sonst `InvoiceBlocked` = 409 "Nur Rechnungen im Entwurf können bearbeitet werden. Die Rechnung ist inzwischen festgeschrieben
  (R-…)." bzw. "Der Entwurf wurde inzwischen gelöscht." / "Die Position wurde inzwischen entfernt.". "Rechnung aus Aufwand" anlegen
  nimmt die Sperre (`_check_create(…, "aufwand")`, ohne eigene Regel), ebenso der Versandnachweis an der Rechnung nach dem Senden
  (`email_sent_at/_to`, Sperre erst nach dem Senden). Router: 409 vor 400.
- **Vorher (bis 1.8.74)**: die Änderung prüfte "Entwurf" ohne Sperre am vorher geladenen Objekt; unter PostgreSQL wartete ihr UPDATE
  auf ein gleichzeitiges Festschreiben und schrieb danach in die festgeschriebene Rechnung (Positionen, Betrag, Zeitraum) -- in den
  Gegenproben nachgestellt.
- **Strukturtest** `tests/test_v378_rechnung_sperre_und_datum.py`: (1) AST über `app/invoices.py` -- jede öffentliche Funktion, die
  schreibt (über die Hilfsfunktionen des Moduls), sperrt vor dem ersten Schreiben; (2) außerhalb von `app/invoices.py` legt niemand
  `Invoice`/`InvoiceItem` an und schreibt kein Feld einer Rechnung (`incoming_invoices.py` ausgenommen: Eingangsrechnungen); (3)
  Rundgang über jeden schreibenden Endpunkt der Rechnungen (aus dem Router, ein neuer ohne Szenario ist rot) mit einem Beobachter an
  der Sitzung, der jede geschriebene Rechnung und Position gegen die Sperre ihres Auftrags hält (`SELECT orders … FOR UPDATE`, auch
  unter SQLite sichtbar). Ausnahmeliste `OHNE_SPERRE` leer.
- Klicktest `scripts/klicktest_rechnungsdatum.py`.

### Festlegungen 1.8.75 (bestätigt am 12.10.2026, Nr. 1–8)

1. **Zahlungsziel = Abstand im Entwurf**: die Fälligkeit rückt um denselben Abstand mit, den sie im Entwurf zum Rechnungsdatum hatte
   (Zahlungsbedingung, Vorgabe des Kunden/Systems, oder über die API angegeben) -- kein neues Feld "Tage". Ein über die API vor das
   Entwurfsdatum gesetztes Fälligkeitsdatum bleibt ebenso viele Tage vor dem Rechnungsdatum (die Oberfläche setzt es nie).
2. **Der Entwurf trägt bis zum Festschreiben das Datum seines Anlegens** (die Spalte ist Pflicht); Feld und Entwurfs-PDF zeigen es
   weiter, die Rechnungsseite darunter "Finalisiert heute: …". Kein Neuberechnen beim Lesen (Regel 23).
3. **Hinweis beim Versand** nur für Status "versendet" (nicht "bezahlt") und nur auf der Rechnungsseite über dem E-Mail-Versand, nicht
   bei "Zustellung nachtragen"; er sperrt nichts. Storno (ohne Fälligkeit): nur Rechnungsdatum und heute.
4. **Alle fünf Spaltenvorgaben** der Regel-20-Ausnahmeliste auf `berlin_today()`, nicht nur das Rechnungsdatum -- die vier übrigen
   griffen nirgends, die Liste ist leer.
5. **Bearbeiten einer festgeschriebenen Rechnung: 409 mit Nummer statt 400** -- wie das Löschen seit 1.8.73: dieselbe Lage, ein Code,
   unabhängig davon, ob das Festschreiben gleichzeitig oder vor Tagen war. Die übrigen 400 beim Bearbeiten (Position der pauschalen
   Rechnung, fremde Auftragsposition, Ende vor Beginn, unbekannte Zahlungsbedingung/Steuerschlüssel) bleiben 400 (Festlegung 1.8.72
   Nr. 7).
6. **Auch der Versandnachweis** an der Rechnung (`email_sent_at/_to`) schreibt unter der Sperre -- genommen erst nach dem Senden, nicht
   über die Verbindung zum Mailserver gehalten. Damit hat der Strukturtest keine Ausnahme.
7. **"Rechnung aus Aufwand"**: nur die Sperre, keine neue Regel (Festlegung 1.8.72 Nr. 3 bleibt offen).
8. **Mahnungen** zählen nicht als "Rechnung" im Sinne von Punkt 2: Anlegen, Festschreiben und Löschen liefen schon unter der Sperre
   (1.8.72/1.8.73), das Bearbeiten eines Mahnungsentwurfs nicht -- als Nebenbefund gemeldet.

### Tests und Prüfung

- Neu `tests/test_v378_rechnung_sperre_und_datum.py` (56, davon 12 gegen PostgreSQL; im Commit 1.8.75 stand "10", berichtigt in 1.8.76): Rechnungsdatum und Fälligkeit beim späteren
  Festschreiben, Fälligkeit über die API, Storno, Silvester (Datum 01.01.2027 zu R-2027-…), Vorschau im Entwurf ohne Schreiben,
  Versandhinweis (gleicher Tag, später, Skonto abgelaufen, überfällig, bezahlt), PDF mit dem Tag des Festschreibens; Bearbeiten je
  Weg (7) an einer festgeschriebenen Rechnung 409 mit Nummer und unverändert, am Entwurf weiter möglich, gelöschter Entwurf 409, Router
  409; Strukturtest in drei Teilen (siehe oben) samt Selbstprüfung der AST-Analyse und des Beobachters. **Gleichzeitig (PostgreSQL,
  Commit der ersten Aktion eine Sekunde angehalten, die zweite lädt vorher ihre Objekte wie der Router):** jede der sieben Änderungen
  gegen Festschreiben (wartet, 409 mit Nummer), Festschreiben gegen laufende Änderung (wartet, schreibt deren Stand fest), Änderung
  gegen Löschen, zweite Änderung derselben Position rechnet mit der Menge der ersten (4 × 60 statt 100 × 60), Pauschalbetrag gegen
  Festschreiben, "aus Aufwand" gegen Festschreiben.
- `test_v372_befund_rechnungsdatum`: xfail bei 4a (2), 4b, 4c entfernt -- grün, keine Prüfung geändert. **Erwartung geändert**:
  `test_today_invoice_date_is_neither_editable_nor_renewed` hieß "nicht erneuert" und erwartete das Datum des Entwurfs nach dem
  Festschreiben -- jetzt `test_invoice_date_is_not_editable_and_renewed_when_finalized`, erwartet den Tag des Festschreibens.
  `test_v316`: `BEKANNTE_VORGABEN` leer.
- Gegenproben (Regel 24): 19 von 19 rot -- Rechnungsdatum beim Festschreiben, Fälligkeit rückt mit, Entwurfsdatum aus Berlin,
  Spaltenvorgabe, Sperre je Weg (Position ändern, hinzufügen, entfernen, Kopf, Zahlungsbedingung, Steuerschlüssel, aus Aufwand,
  Versandnachweis; je durch die alte Prüfung ohne Sperre ersetzt), Positionen frisch nach der Sperre, "noch Entwurf" und "noch da"
  nach der Sperre, Router 409, Versandhinweis, Vorschau im Entwurf, Schreiben außerhalb von `app/invoices.py` (in `app/reminders.py`).
  Dabei gesehen: der PostgreSQL-Test "aus Aufwand wartet" blieb ohne die Sperre grün -- das Anlegen wartet dort auch über den
  Fremdschlüssel auf die gesperrte Auftragszeile; rot wurden Strukturtest, Beobachter und Rundgang (am Test vermerkt). Jede Datei
  byte-genau zurück (SHA-256), kein Marker übrig.
- Klicktest `klicktest_rechnungsdatum.py` 13/13: Entwurf von vor drei Wochen mit "Finalisiert heute", Finalisieren -> Datum heute,
  fällig in 14 Tagen, Skonto ab heute; vor zehn Tagen finalisierte Rechnung mit Versandhinweis (hell und dunkel); veraltete Seite nach
  Finalisieren in anderer Sitzung -> Meldung mit Nummer, nichts geändert, Position 409.
- Rechnungs-Testdateien (alle `tests/test_*.py` mit "invoice"/"rechnung", mit den opt-in-Tests gegen PostgreSQL): 1493 grün,
  7 erwartet fehlgeschlagen (1a, 1b, 1d).
- Volle Suite (mit den opt-in-Tests gegen PostgreSQL, Arbeitskopie): 3391 grün, 0 rot, 7 erwartet fehlgeschlagen (1a, 1b, 1d).
  Danach nur Doku geändert.

### Nebenbefunde (nur gemeldet)

1. **Mahnungsentwurf bearbeiten ohne Sperre**: `update_reminder_draft()` (`PUT /api/reminders/{id}`, Text, Gebühr, neue Frist) prüft
   "Entwurf" am vorher geladenen Objekt -- dasselbe Rennen wie bis 1.8.74 bei Rechnungen: gleichzeitig zum Festschreiben der Mahnung
   kann die Änderung danach in die festgeschriebene Mahnung schreiben. Anlegen, Festschreiben und Löschen der Mahnung laufen schon
   unter der Sperre.
2. **Mahndatum bleibt der Tag des Entwurfs** (Befund Punkt 4, "übrige Fälle"): `Reminder.reminder_date` und die neue Frist (Datum +
   Tage der Stufe) werden beim Festschreiben nicht erneuert -- dieselbe Frage wie 4c, jetzt für Mahnungen.

**Beide kommen mit der Zahlungsstufe** (Rückmeldung 12.10.2026, Vorgabe 1.8.77).

## Umsetzung 1.8.76: Nummernkreise -- keine Anzeige schreibt, Überspringen mit Warnung, Format ohne Jahr; Klicktests (Punkte 3-5)

Vorgabe: siehe "Umsetzung 1.8.75" (Punkte 3-5 und die Änderung zu Festlegung 1.8.74 Nr. 2). Nach Punkt 2 committet (1.8.75), der
Rest hier als eigene Version.

### Zu 3: Aufrufer der Nummernkreise (Befund)

**Vergabe** (`app/settings.py::issue_number()`, zählt hoch, unter der Sperre der Nummernkreis-Zeile):

| Nummernkreis | Funktion | Aufgerufen von |
|---|---|---|
| Kunde | `crm.py::next_customer_number()` <- `ensure_customer_profile()` | `POST /api/customers` (`routers/customers.py:163`), `PUT /api/customers/{id}` nur ohne Profil (`:80`), Adressimport (`address_import.py:349`); **bis 1.8.75 auch `GET /api/customers` und `/{id}`** (siehe unten) |
| Anfrage | `inquiries.py::next_inquiry_number()` | `POST /api/inquiries` (`routers/inquiries.py:90`) |
| Projekt | `projects.py::next_project_number()` | `POST /api/projects` (`routers/projects.py:147`), Anfrage -> Projekt (`routers/inquiries.py:126`), `duplicate_project()` (`projects.py:770`: Kopieren, als Mustervorgang, aus Muster), Schnellauftrag (`quick_service_orders.py:46`) |
| Angebot | `projects.py::next_quote_number()` | `POST /api/projects/{id}/quotes` (`routers/projects.py:327`), Anfrage -> Angebot (`routers/inquiries.py:142`), `duplicate_project()` (`projects.py:657`), Schnellauftrag (`quick_service_orders.py:53`) |
| Auftrag | `orders.py::create_order_from_quote()` (`:732`) | Beauftragen, Schnellauftrag |
| Rechnung | `invoices.py::finalize_and_send_invoice()` | Finalisieren (auch Storno) |
| Mahnung | `reminders.py::finalize_and_send_reminder()` (`:237`) | Mahnung versenden |

**Vorschau** (`preview_number()`, zählt nie hoch): `GET /api/settings/number-sequences` (Einstellungen), `PUT …/{key}` (Antwort nach
dem Speichern), `GET …/{key}/preview` (Kundenformular `master_data_form.html`: vorgeschlagene Kundennummer); `crm.py::
customer_number_preview()` war unbenutzt -- entfernt.

**Ergebnis**: Keine Vorschau in Einstellungen oder Formularen hat seit 1.8.73 eine Nummer verbraucht -- `preview_number()` zählte nie
hoch. Aber zwei Anzeigewege schrieben:
- **`preview_number()` schrieb** Jahreswechsel (`next_value` = Startnummer, `last_year`) und Abgleich (`next_value` über die höchste
  vergebene) in den Nummernkreis, ohne Sperre; `GET /api/settings/number-sequences` und `/{key}/preview` committeten das (in
  `SCHREIBT_BEKANNT` seit 1.8.42). Mit einem veralteten Stand gelesen (vor dem Commit einer gleichzeitigen Vergabe) konnte das die
  nächste Nummer unter eine schon vergebene, später gelöschte zurücksetzen (Kunde, Anfrage, Projekt, Angebot -- deren Nummern werden
  seit 1.8.73 nicht wieder vergeben).
- **`GET /api/customers` und `/{id}` zogen eine Kundennummer**, wenn ein Kunde kein Profil hatte (Festlegung 1.8.73 Nr. 2: "auch über
  die zwei GET-Routen") -- seit 1.8.73 über `issue_number()`, also verbraucht. Jeder Anlegeweg legt das Profil an; betroffen sind nur
  Altkunden ohne Profil.

### Was gebaut ist

- **Vorschau nur lesend** (`preview_number()`, neu `effective_next_value()`): Jahreswechsel und Abgleich werden ausgerechnet, nicht
  geschrieben; geschrieben werden sie erst bei der Vergabe, unter der Sperre. Die beiden GET-Routen committen nichts mehr,
  `SCHREIBT_BEKANNT` (`test_v326`) ohne den Eintrag. Die Einstellungen zeigen als "Nächste Nr." die Nummer, die die nächste Vergabe
  zöge -- nach dem Jahreswechsel also die Startnummer, nicht den gespeicherten Wert des alten Jahres (sonst überschriebe ein
  unverändertes Speichern der Zeile den Jahreswechsel).
- **Kunden-GET legt kein Profil an**: ein Altkunde ohne Profil zeigt keine Kundennummer (Kategorie "Privatkunde"), bis er
  gespeichert wird (`PUT` legt das Profil an und zieht die Nummer). `CustomerOut.customer_number` darf leer sein; die Oberflächen
  zeigen dann nichts. `crm.py::ensure_customer_profiles()` (nur von dort benutzt) entfernt.
- **Strukturtest**: kein GET-Endpunkt erreicht `issue_number()` (AST über alle Funktionen in `app/`, Aufrufweg im Fehlertext,
  `GET_MIT_NUMMER` leer).
- **Überspringen mit Warnung** (Festlegung 1.8.74 Nr. 2, geändert): liegt die nächste Nummer bei der Vergabe auf oder unter einer
  vergebenen, springt `issue_number()` weiter darüber und schreibt `logger.warning`: "Nummernkreis invoice: nächste Nummer R-2026-0002
  lag auf oder unter einer vergebenen -- übersprungen: R-2026-0002 bis R-2026-0003, vergeben wird R-2026-0004." (nur Nummernkreis und
  Nummern, Regel 18).
- **Zu 4**: `update_sequence()` lehnt ein Format ohne `{YYYY}`/`{YY}` mit "Jahreswechsel: auf Startnummer zurück" ab
  (`YearlyResetWithoutYear`, 409): "Ein Format ohne Jahr ({YYYY} oder {YY}) kann zum Jahreswechsel nicht auf die Startnummer
  zurückgehen -- die Nummern des neuen Jahres wären dieselben wie die des alten. Bitte das Jahr ins Format aufnehmen oder
  „fortlaufend“ wählen." Gemeinsame Oberklasse `SequenceConflict` (auch `NumberBelowExisting`), der Router antwortet darauf 409; ein
  ungültiges Format bleibt 422 und wird zuerst geprüft. Der veraltete Satz unter Nummernkreise ist entfernt, der Hinweis zu den
  Platzhaltern nennt die Regel.
- **Zu 5a**: die rote Prüfung in `klicktest_versandverlauf.py` ("PDF-Knopf weiter in voller Auflösung, über 3 MB") ist durch
  Festlegung 3 aus 1.8.66 überholt -- die Checkliste im Klicktest wird abgeschlossen, ihr PDF-Knopf liefert seitdem die feste Fassung
  (Fotos verkleinert bis unter 3 MB; "die Fassung ersetzt den Download in voller Auflösung"). Neue Erwartung: der PDF-Knopf liefert
  dieselbe Datei wie der Anhang der Mail (SHA-256 gleich), unter 3 MB.
- **Zu 5b**: `scripts/klicktest_alle.py` lässt alle `scripts/klicktest_*.py` nacheinander laufen, je einer mit eigenem Arbeitsordner
  unter einem gemeinsamen Ausgabeordner (Protokoll je Test, Screenshots), Zeitlimit je Test (Vorgabe 900 s, danach der eigene
  Prozessbaum über die PID beendet, Regel 12), Übersicht mit Ergebnis, Prüfungen und Laufzeit je Test und gesamt
  (`zusammenfassung.txt`); `--nur`, `--ab`.

### Festlegungen 1.8.76 (bestätigt am 12.10.2026, Nr. 1–5)

1. **Kunde ohne Profil**: die beiden GET-Routen legen keins mehr an, die Kundennummer bleibt leer, bis der Kunde gespeichert wird --
   engt Festlegung 1.8.73 Nr. 2 ein ("auch über die zwei GET-Routen" gilt nicht mehr). Kein Nachlegen beim Start: jeder Anlegeweg legt
   das Profil an, betroffen wäre nur Altbestand.
2. **"Nächste Nr." in den Einstellungen** ist die Nummer, die die nächste Vergabe zöge (Jahreswechsel und Abgleich ausgerechnet),
   nicht der gespeicherte Wert.
3. **Warnung nur bei der Vergabe** (nicht bei Vorschau oder beim Anlegen eines Nummernkreises beim Start), Stufe WARNING, Text nur mit
   dem Schlüssel des Nummernkreises und den Nummern.
4. **Format ohne Jahr mit Jahreswechsel**: geprüft nur beim Speichern; ein schon so eingestellter Nummernkreis bleibt, bis er
   gespeichert wird (die Vergabe springt dort mit Warnung). `{YY}` zählt als Jahr. Reihenfolge: ungültiges Format (422), dann diese
   Prüfung (409), dann "nächste Nummer zu tief" (409).
5. **Alle Klicktests**: Zeitlimit 900 s je Test; nicht Teil der pytest-Suite; der Ausgabeordner bleibt liegen (Temp, wie bei
   einzelnen Klicktests).

### Tests und Prüfung

- Neu `tests/test_v379_nummern_anzeige.py` (26): Vorschau nach dem Jahreswechsel und über vergebenen Nummern ohne Schreiben, GET-Routen
  der Einstellungen ohne Schreiben und mit "Nächste Nr." = was die Vergabe zöge, unverändertes Speichern nach dem Jahreswechsel behält
  ihn, Kunden-GET ohne Profil und ohne Nummer (PUT zieht sie), Strukturtest kein GET erreicht `issue_number()`, Warnung beim
  Überspringen (mehrere, eine) und keine bei normaler Vergabe (7), Format ohne Jahr mit Jahreswechsel je Nummernkreis abgelehnt (7),
  fortlaufend und `{YY}` erlaubt, 422 vor 409, Route 409 mit Grund, Satz entfernt.
- **Erwartung geändert**: `test_v05_customer_and_quote_calc.py::test_customer_number_category_and_legacy_backfill` erwartete, dass
  `GET /api/customers` einem Altkunden ohne Profil eins samt Kundennummer anlegt -- jetzt
  `…_legacy_without_profile`: keine Nummer, kein Profil. Angepasst: `test_v376` (Liste der Vorschau-Aufrufer ohne die entfernte
  Funktion), `test_v326` (`SCHREIBT_BEKANNT` ohne die Nummernkreise).
- Gegenproben (Regel 24): 8 von 8 rot -- Vorschau schreibt (flush; und mit commit im Rundgang `test_kein_get_schreibt`), Kunden-GET legt
  Profil an (auch der Strukturtest wurde rot), Warnung, Jahreswechsel bei der Vergabe, Format ohne Jahr, Router 409, "Nächste Nr." aus
  dem gespeicherten Wert. Jede Datei byte-genau zurück (SHA-256), kein Marker übrig.
- Klicktests: `klicktest_leistungszeitraum.py` 20/20 (neu: Satz weg, "ANF-{NNNN}" mit Jahreswechsel -> Grund, nichts gespeichert,
  fortlaufend gespeichert), `klicktest_versandverlauf.py` 32/32 (Erwartung zu 5a).
- **Alle Klicktests** (`scripts/klicktest_alle.py`, Arbeitskopie mit dem Stand 1.8.76): 45 von 46 wie erwartet, **Laufzeit
  gesamt 9:49 min** (je Klicktest 7-30 s, die längsten Versandprotokoll, Behinderungsanzeige-Abschluss, Vertrag-Unterschrift).
  Rot: `klicktest_vertragsvorlagen.py` 35/36 (Nebenbefund 1).
- Volle Suite (mit den opt-in-Tests gegen PostgreSQL, Arbeitskopie): 3417 grün, 0 rot, 7 erwartet fehlgeschlagen (1a, 1b, 1d).
  Danach nur Doku geändert.

### Nebenbefunde (nur gemeldet)

1. **(seit 1.8.77 behoben)** **`klicktest_vertragsvorlagen.py`: Platzhalterliste 23 statt erwartet 22** -- seit 1.8.50 gibt es `{gewaehrleistung}`, der
   Klicktest wurde zuletzt in 1.8.42 geändert; veraltete Erwartung, nicht von dieser Änderung (Prüfung in Zeile 88).
2. **Einstellungen -> Nummernkreise bei 1280 px Fensterbreite**: jede Zeile ragt rechts über die Karte ("Speichern" angeschnitten,
   die Seite scrollt seitlich) -- im Screenshot des Klicktests gesehen, nicht untersucht.

## Umsetzung 1.8.77: eindeutige Nummer in der Datenbank, Klicktests vor jedem Bericht; Befund Zahlungsstufe

### Vorgabe vom 12.10.2026 (übernommen wie gegeben)

1.8.75/76 geprüft. Festlegungen bestätigt (1.8.75 Nr. 1–8, 1.8.76 Nr. 1–5). Die Mahnungen (Sperre beim Bearbeiten, Mahndatum beim
Festschreiben) kommen mit der Zahlungsstufe.

1.8.77:
1. Eindeutige Nummer als Datenbank-Bedingung für alle sieben Nummernkreise; die Prüfabfrage auf dem Server fand keine Dubletten.
   Entwürfe ohne Nummer bleiben erlaubt. Die Migration sucht vorher selbst nach Dubletten und bricht mit klarer Liste ab statt mit
   einem Datenbankfehler.
2. klicktest_vertragsvorlagen.py auf 23 Platzhalter. In CLAUDE.md als Regel: Vor jedem Bericht läuft scripts/klicktest_alle.py, das
   Ergebnis steht im Bericht.
3. Ins Archiv befund-vor-echtbetrieb.md, Abschnitt „Entscheidungen Rechnungen“ ergänzen (nur festhalten, nicht bauen): Einbehalt nur
   bewusst gebucht, nie automatisch aus einer Unterzahlung; wird nicht gemahnt; Zustand „Einbehalt offen“; erscheint im
   Zahlungshinweis der Schlussrechnung; Gewährleistungseinbehalt mit Freigabedatum später. Rechnungen aus Aufwand zählen in der
   Schlussrechnung zum Gesamtwert und werden wie Abschläge abgezogen; nach der Schlussrechnung keine Rechnung aus Aufwand im selben
   Auftrag; welche Stunden abrechenbar sind, regelt Stufe 2d. Auf dem Server sind keine echten Bewegungsdaten: Zum Echtbetrieb werden
   die Probebelege entfernt.

Befund Zahlungsstufe, nur lesen, mit Fundstellen:
a) Wo wird „bezahlt“ heute gelesen (Mahnwesen, Finanzen, Dashboard, Buchhaltung, Export)?
b) Was bieten Buchhaltung Stufe 1 und 2 für Zahlungen (Bankkonto, Kontoauszug, Buchungen)? Ließe sich ein Zahlungseingang dort
   anbinden?
c) Skonto: Wo stehen Satz und Frist, und wie wird es heute angezeigt?
d) Wie entstehen Mahnungsentwürfe, und über welchen Betrag mahnen sie?

Angriffstests mit Gegenprobe für Punkt 1. Nebenbefunde nur melden. Commit nach Regel 13, Bericht kurz.

### Vorweg

- Festlegungen 1.8.75 und 1.8.76 an der Überschrift als bestätigt markiert; die beiden Mahnungs-Nebenbefunde aus 1.8.75 tragen den
  Vermerk "kommen mit der Zahlungsstufe".
- Zu 3: unten unter "Entscheidungen Rechnungen" ergänzt; Festlegung 1.8.72 Nr. 3 ("Aufwand nach der Schlussrechnung möglich") trägt
  den Vermerk der Entscheidung.

### Was gebaut ist

- **Fünf von sieben waren schon eindeutig**: Kunde, Anfrage, Projekt, Angebot und Auftrag tragen seit der Baseline (`2befd7907eef`)
  eine UNIQUE-Bedingung (`uq_customer_number`, `uq_inquiry_number`, `uq_project_number`, `uq_quote_number`, `uq_order_number`) --
  der Server bekam sein Schema über `alembic upgrade head` (`scripts/migrate_sqlite_to_postgres.py`), also auch diese. Es fehlten
  **Rechnung und Mahnung** (nur ein Index, `ix_invoices_invoice_number`/`ix_reminders_reminder_number`).
- **Migration `f3a8c2d6b190`** (`nummern_eindeutig`): `uq_invoice_number` auf `invoices.invoice_number`, `uq_reminder_number` auf
  `reminders.reminder_number`; der Index bleibt (wie bei den übrigen fünf). Entwürfe haben NULL -- in einer UNIQUE-Bedingung unter
  PostgreSQL und SQLite nie gleich, also beliebig viele. Stornorechnungen gehören zum Kreis der Rechnungen.
  - **Vorher, ohne etwas zu ändern** (`pruefen()`): je Nummernkreis (alle sieben) jede Nummer, die mehr als einmal vergeben ist, mit
    Anzahl und IDs, dazu jede der fünf alten Bedingungen, die in der Datenbank fehlt (sie wird nicht still angelegt). Abbruch mit:
    "Migration abgebrochen, nichts geändert: jede vergebene Nummer soll in ihrem Nummernkreis eindeutig sein, aber in dieser
    Datenbank\n  - Rechnung R-2026-0001: 2-mal vergeben (invoices.id 1, 2)\n  - …\nBitte zuerst klären (Dubletten und Lücken zeigt
    scripts/pruefabfrage_nummernkreise.sql), dann erneut einspielen." Die Zuordnung Nummernkreis -> Tabelle/Spalte steht fest in
    der Migration (wie `_existing_column()`, ein Test hält beide gleich).
  - `downgrade()`: entfernt die beiden Bedingungen, keine Nummer geht verloren -- daher nicht verweigert.
- **Modell**: `Invoice`/`Reminder` mit `__table_args__` (UniqueConstraint wie die übrigen fünf). Veralteter Docstring an `Invoice`
  ("`issue_invoice()`", "beim Versenden") korrigiert.
- **Klicktest** `klicktest_vertragsvorlagen.py`: Platzhalterliste 23 (seit 1.8.50 `{gewaehrleistung}`).
- **CLAUDE.md Regel 26**: vor jedem Bericht `scripts/klicktest_alle.py`, Ergebnis im Bericht.

### Befund Zahlungsstufe (nur gelesen; Zeilen nach dem Stand 1.8.77)

Der Befund aus 1.8.72 (a) gilt weiter: **"bezahlt" ist ein Status mit Datum** -- kein Betrag, keine Teilzahlung, keine
Zahlungstabelle, kein offener Betrag je Rechnung.

**a) Wo "bezahlt" gesetzt und gelesen wird**
- **Setzen**: `mark_invoice_paid()` (`app/invoices.py:769`) unter `lock_order_invoices()`, nur aus `versendet`, `paid_date` aus der
  Anfrage oder `berlin_today()`; `POST /api/invoices/{id}/mark-paid` (`routers/invoices.py:252`, ab `buero_auftrag`), Schema
  `InvoiceMarkPaid` ohne Prüfung des Datums; die Rechnungsseite schickt `{}` (`invoice_detail.html:201`) -- immer heute. **Kein
  Zurücknehmen** (nur Storno; das Original wird `storniert`, `paid_date` bleibt), **kein Audit** (`Invoice` nicht in
  `AUDITED_TYPES`, `app/audit.py:46`).
- **"gültig" = versendet oder bezahlt** (`VALID_STATUSES`, `invoices.py:55`): Sperrgründe (`_final_invoices()`,
  `storno_block_reason()`), Abzug in der Schlussrechnung (`get_previous_cumulative_ist()`, `:304`), Abrechnungsstand am Auftrag
  (`compute_order_billing_progress()`, `:1121` -- "noch offen" dort = noch nicht abgerechnet, nicht unbezahlt), Vorschlag des
  Leistungszeitraums (`service_period.py:27`).
- **Überfällig** = `versendet` und Fälligkeit vor heute (`invoice_to_dict()`/`invoice_overview_row()`, `:1073`/`:1174`); ein Storno
  hat keine Fälligkeit, ist also nie überfällig. `paid_date` steht nur in `invoice_to_dict()`, nicht in der Übersicht
  (`invoice_overview_row()`, `:1161`) -- Finanzen und Projektmappe zeigen kein Zahldatum.
- **Mahnwesen**: `send_block_reason()` (`reminders.py:176`, "bezahlt (am …)", "storniert"), Anlegen nur zu `versendet`
  (`create_reminder()`, `:207`), Liste und Kennzahlen aus `list_invoices_needing_attention()` (`:455`: versendet und überfällig,
  offener Betrag = volles Brutto, `:473`).
- **Finanzen** (`finanzen.html:47-51`) und **Dashboard** (`dashboard.html:137-138`): "Offene Rechnungen"/"Offener Betrag" = alle mit
  Status `versendet` (Abschläge, Aufwand und Stornorechnungen mit negativem Betrag eingeschlossen), "Bezahlt (gesamt)" = Brutto aller
  mit `bezahlt`; Dashboard-Aufgaben: eine Zeile "Mahnung" je überfälliger Rechnung (`dashboard.html:120`).
- **Rechnungsseite**: Statusknöpfe (`invoice_detail.html:156-171`; bei `versendet` "Als bezahlt markieren" -- auch an einer
  Stornorechnung), Mahnkarte nur bei `versendet` (`:99`).
- **Buchhaltung**: liest den Status der Ausgangsrechnungen nicht. **Export**: für Ausgangsrechnungen keiner (CSV/DATEV nur Stunden
  und Lohn, `routers/time_backoffice.py:133`). PDF der Rechnung, Suche, Projektliste/Kanban: kein Zahlstatus.

**b) Buchhaltung und Zahlungen**
- **Stufe 1** (1.6.0, `modul-buchhaltung.md`): Eingangsrechnungen (`IncomingInvoice`, `models.py:4697`) mit `payment_status`
  offen/bezahlt und `payment_date` (`:4775`), Skonto-Satz und -Frist, Beleg; "bezahlt" per Bearbeiten zurücknehmbar
  (`incoming_invoices.py:283`), offene Verbindlichkeiten (`open_liabilities_summary()`, `:388`), Skonto-Erinnerung als Aufgabe
  (`:406`). Kein Betrag, keine Teilzahlung, kein gezogenes Skonto.
- **Stufe 2, erster Teil** (1.6.1): Kontenstamm `Account` (`models.py:4435`: Nummer, Bezeichnung, Steuersatz, aktiv -- **kein
  Kontotyp**) und Vorkontierung an Eingangsrechnung und Position ("Vorkontierung, keine Buchung"). Geplant, nicht gebaut: Import der
  Kontendatei, DATEV-Export; Stufe 3 KI-Belegauswertung.
- **Nicht vorhanden, auch nicht geplant**: Bankkonto, Kontoauszug-Import (CAMT/MT940/CSV), Buchungen/Journal, Zahlungen, Debitoren.
  "iban" gibt es nur als eigene Bankverbindung in den Einstellungen (`GeneralSettings.iban`, `models.py:2590`).
- **Anbinden**: an die Buchhaltung nicht -- dort gibt es nur das Muster "Status mit Datum"; Ein- und Ausgang sind bewusst getrennte
  Tabellen, und die Buchhaltung ist nur für `buero_finanzen` mit Modul `buchhaltung` offen (`routers/incoming_invoices.py:36`),
  Rechnungen und Mahnwesen ab `buero_auftrag`. Anknüpfen ließe sich am Rechnungswesen: `Invoice.id` als Ziel einer Zahlung,
  `lock_order_invoices()` als Sperre (bezahlt und Mahnung laufen schon darunter), `compute_invoice_totals()["gross_total"]` als
  Soll, `mark_invoice_paid()` als die Stelle, die "bezahlt" aus Zahlungen ableiten würde, `create_reminder()`/
  `list_invoices_needing_attention()`/`invoice_overview_row()` für den offenen Betrag. Es fehlen: Zahlungstabelle (Betrag, Datum,
  Weg, Referenz, Skontoabzug), Zuordnung Zahlung <-> Rechnung (die Entscheidung "Zahlung auf den Zahlbetrag, zuerst offene
  Abschläge" braucht mehrere Rechnungen je Zahlung), eine Funktion "offener Betrag", Korrektur einer Zahlung, Audit; Bankkonto und
  Kontoauszug nur, wenn gewünscht.

**c) Skonto**
- **Satz und Frist** an der Zahlungsbedingung (`PaymentTerm.skonto_percent/skonto_days`, `models.py:381`; beide oder keins, Frist ≤
  Zahlungsziel, `payment_terms.py:44`; die Standardbedingungen haben keins). Vorgabe je Kunde über
  `CustomerProfile.default_payment_term_id`; am Auftrag nur die Bezeichnung (`Order.payment_terms`).
- **An der Rechnung eingefroren** (`Invoice.skonto_percent/skonto_days`, `:1720`) beim Anlegen (`_default_payment_terms_for_order()`,
  `invoices.py:255`: Bedingung laut Auftrag, sonst Kunde, sonst System), im Entwurf änderbar (`update_invoice_payment_term()`, `:893`).
  Skontodatum = Rechnungsdatum + Tage, seit 1.8.75 also ab dem Tag des Festschreibens. Ein Storno übernimmt kein Skonto.
- **Anzeige**: Zahlungssatz `format_payment_terms_sentence()` (`:932`, Platzhalter `{skontodatum}`, `{skontoprozent}`,
  `{skontobetrag}` = der Abzug, nicht der Zahlbetrag) im PDF und auf der Rechnungsseite; Versandhinweis (`send_hint()`, `:993`,
  "Skontofrist schon abgelaufen"). Mahnung und Rechnungs-Mail kennen kein Skonto. Die Skonto-Erinnerung (`incoming_invoices.py:406`)
  gilt nur für Eingangsrechnungen. **Ob Skonto gezogen wurde, hält nichts fest.**

**d) Mahnungsentwürfe**
- **Von Hand**: `create_reminder()` (`reminders.py:207`) unter der Sperre: Rechnung `versendet`, weder storniert noch bezahlt, Stufe
  aktiv -- nicht geprüft: Fälligkeit, Art der Rechnung, Reihenfolge der Stufen, vorhandener Entwurf.
- **Automatisch**: `auto_create_due_reminder_drafts()` (`:397`) beim Öffnen des Mahnwesens (`POST /api/reminders/auto-create`,
  `mahnwesen.html:240`), Schalter `reminders_auto_create_drafts` (Standard an, `models.py:2623`): je überfälliger Rechnung ohne
  Entwurf, deren nächste Stufe fällig ist (`compute_reminder_status()`, `:107`: nächste aktive Stufe über der höchsten versendeten,
  fällig ab Fälligkeit bzw. Datum der letzten Mahnung + Tage der nächsten Stufe; Vorgabe 7/7/7 Tage, 5/10/15 €).
- **Betrag**: `outstanding_amount = compute_invoice_totals(invoice)["gross_total"]` (`:220`) -- das volle Brutto dieser einen
  Rechnung, ohne frühere Mahngebühren, ohne Bezug zu Abschlägen oder Schlussrechnung, im Entwurf nicht änderbar. Gebühr aus der
  Stufe, neue Frist = heute + Tage der Stufe (`:219`). Text, PDF-Tabelle "Offener Rechnungsbetrag / Mahngebühr / Gesamtbetrag"
  (`reminder_pdf.py:83`) und Mail nehmen diesen Betrag; die Mahnwesen-Liste rechnet ihn live.

### Festlegungen 1.8.77 (bestätigt am 12.10.2026, Nr. 1–5; Vorgabe Z1, siehe `zahlungen.md`)

1. **Die fünf alten Bedingungen bleiben, wie sie sind**; die Migration legt nur Rechnung und Mahnung an und prüft, dass die fünf da
   sind -- fehlt eine, bricht sie mit Namen ab, statt sie still anzulegen (das bliebe in `downgrade()` unsichtbar).
2. **Geprüft werden alle sieben Kreise auf Dubletten** (dieselbe Frage wie die Prüfabfrage), nicht nur die zwei neuen.
3. **`downgrade()` ist erlaubt** (nimmt nur die Bedingungen weg).
4. **Keine eigene Fehlerbehandlung in der App**: Die Vergabe läuft unter der Sperre und springt über vergebene Nummern; eine Dublette
   erreicht die Datenbank nur am Nummernkreis vorbei (Skript, Import, Fehler) -- dann 500 mit zurückgerolltem Vorgang, nichts halb
   (Storno bleibt Entwurf, Original nicht storniert; im Test nachgestellt).
5. **Klicktest**: die Erwartung ist die feste Zahl 23 (wie verlangt), nicht die Länge der Liste im Code -- ein neuer Platzhalter
   fällt damit beim nächsten Gesamtlauf auf (Regel 26).

### Tests und Prüfung

- Neu `tests/test_v380_nummern_eindeutig.py` (20, davon 5 gegen PostgreSQL): Struktur (jeder Nummernkreis aus `DEFAULT_SEQUENCES`
  hat seine Bedingung im Modell; die Migration deckt genau die sieben ab); **Angriffe**: dieselbe Nummer am Nummernkreis vorbei ein
  zweites Mal speichern, je Nummernkreis (SQLite 7, PostgreSQL alle sieben -- die Meldung nennt die Bedingung); Entwürfe ohne Nummer
  (je drei Rechnungen und Mahnungen, SQLite und PostgreSQL); die Vergabe liefert eine vergebene Nummer (Storno-Festschreiben unter
  SQLite und PostgreSQL, Mahnung) -> abgelehnt, nichts halb; zwei Sitzungen schreiben gleichzeitig dieselbe Rechnungsnummer
  (PostgreSQL, die erste hält ihren Commit eine Sekunde: die zweite wartet am Index und wird abgelehnt); **Migration** auf einem
  Bestand mit Dubletten (2 Rechnungen, 3 Mahnungen) und Entwürfen, SQLite und PostgreSQL: Abbruch mit der Liste und den IDs, kein
  `IntegrityError`, Stand und Schema unverändert; geklärt -> hoch, Bedingungen da, Entwürfe unverändert, Dublette danach abgelehnt;
  runter (Nummern bleiben), wieder hoch; Prüfung meldet eine fehlende alte Bedingung samt Dublette dort, ein sauberer Bestand geht
  durch.
- Gegenproben (Regel 24): 6 von 6 rot, je alle genannten Tests -- Bedingung an der Rechnung im Modell (6 Tests), an der Mahnung (4),
  Migration ohne Prüfung vorher (2: Datenbankfehler statt Liste), Migration ohne Anlegen der Bedingungen (2), Prüfung übersieht eine
  fehlende alte Bedingung (1), Prüfung zählt Entwürfe ohne Nummer als Dublette (4). Jede Datei byte-genau zurück (SHA-256), kein
  Marker unter `app/` und `alembic/`.
- Migration `f3a8c2d6b190`: SQLite (Wegwerf-Datei) und PostgreSQL (Wegwerf-Schema, leer): hoch, `current` head, `check` ohne
  Unterschied, runter, wieder hoch; danach alle sieben Spalten mit Bedingung (Reflexion).
- **Alle Klicktests** (`scripts/klicktest_alle.py`, Arbeitskopie mit dem Stand 1.8.77, Regel 26): 46 von 46 wie erwartet, Laufzeit
  gesamt 9:50 min; `klicktest_vertragsvorlagen.py` 36/36.
- Volle Suite (mit den opt-in-Tests gegen PostgreSQL, Arbeitskopie): 3437 grün, 0 rot, 7 erwartet fehlgeschlagen (1a, 1b, 1d). Keine
  Erwartung geändert. Danach nur Doku geändert.

### Nebenbefunde (nur gemeldet)

1. **Stornorechnung zählt in Finanzen und Dashboard als offen** (Nebenbefund 3 aus 1.8.72, weiter offen); ein bezahltes, danach
   storniertes Original fällt aus "Bezahlt (gesamt)" heraus, `paid_date` bleibt an ihm stehen.
2. **Eine Stornorechnung lässt sich "bezahlt" markieren**: `mark_invoice_paid()` prüft die Art nicht, die Rechnungsseite zeigt den
   Knopf.
3. **`create_reminder()` über die API** (`POST /api/invoices/{id}/reminders`, Stufe 1–3): auch zu einer Stornorechnung (negativer
   Betrag), zu einer noch nicht fälligen Rechnung, in beliebiger Stufe und ein zweiter Entwurf derselben Stufe (letzteres Nebenbefund
   5 aus 1.8.72).
4. **Nächste Mahnstufe ab dem Mahndatum, nicht ab der gesetzten Frist**: fällig = Datum der letzten Mahnung + Tage der nächsten Stufe
   (`compute_reminder_status()`), die Frist in der Mahnung = Datum + Tage ihrer Stufe. Mit der Vorgabe 7/7/7 wird die nächste Stufe am
   letzten Tag der Frist fällig; bei kürzeren Tagen der nächsten Stufe oder einer im Entwurf verlängerten Frist schon davor.
5. **Zustellung einer Mahnung auf anderem Weg** (Einschreiben usw.) geht auch bei bezahlter oder stornierter Rechnung
   (`dispatch_documents.py:84`, ohne `send_block_reason()`) -- der Moduldocstring sagt "dieselben Bedingungen wie beim E-Mail-Versand".
6. **Dashboard verliert die "Mahnung"-Zeilen**, sobald ein Mitarbeiter gewählt ist (für Nicht-Admins mit Mitarbeiter immer): gefiltert
   wird auf `Invoice.caseworker_employee_id`, die nie gesetzt wird (bekannt aus CLAUDE.md, die Folge im Dashboard nicht).
7. "Bezahlt": Datum ohne Prüfung (Zukunft, vor dem Rechnungsdatum), keine Rücknahme, kein Audit; die Rechnungsseite blendet die
   Mahnhistorie aus, sobald die Rechnung bezahlt oder storniert ist (`invoice_detail.html:99`); eine bezahlte oder stornierte Rechnung
   lässt sich weiter per E-Mail senden (`send_invoice_email()` sperrt nur Entwürfe).
8. **Probebelege entfernen** (Entscheidung unten): einen Weg dafür gibt es nicht -- bewusst, Ablage und Versandprotokoll sind
   unveränderlich, Rechnungen nur als Entwurf löschbar. Es bräuchte ein einmaliges Skript (Rechnungen, Mahnungen, Ablage-Dateien unter
   `ERP_DATA_DIR`, Versandprotokoll, Nummernkreise zusammen), gegen `spielwiese` geprobt.

## Befund R4: Schlussrechnung als Endrechnung (12.10.2026)

Nur gelesen: App-Code und Tests unverändert, keine Lösungsvorschläge. Zeilen nach dem Stand 1.8.81 (`b7cd16e`). "Nachgerechnet" =
in einer Wegwerf-SQLite im Speicher mit den Testhelfern (`tests/test_v133_invoices.py::make_order_with_item()`,
`tests/leistungszeitraum.py::festschreiben()`), Skript nur im Scratchpad, nicht im Repo; "laut Code" = abgeleitet. Beispiel wie in
Punkt 1: Auftrag 100 m² × 50 € = 5.000 € netto, 19 % = 5.950 € brutto. Grundlage: Punkt 1 oben, xfail 1a, 1b, 1d
(`tests/test_v372_befund_schlussrechnung.py`), "Entscheidungen Rechnungen" unten.

### Vorgabe vom 12.10.2026 (übernommen wie gegeben)

1.8.81 geprüft. Festlegungen 1–18 bestätigt.

R4 Schlussrechnung, zuerst Befund: nur lesen, keine Lösungsvorschläge, mit Fundstellen. Grundlage: „Entscheidungen Rechnungen“ im
Archiv, befund-vor-echtbetrieb.md Punkt 1, xfail 1a, 1b, 1d.
a) Wie entsteht die Schlussrechnung heute Schritt für Schritt (Mengen, Abzüge, Nachträge, Steuer), und wo müsste die Endrechnung
   ansetzen?
b) Abschläge nach Leistungsstand: Wie hängt die abgerechnete Menge je Position an der Schlussrechnung, und was davon bleibt in einer
   Endrechnung nötig?
c) Rechnung aus Aufwand am Auftrag mit Preisen und am Schnellauftrag: Wie ist sie heute aufgebaut, und was bedeutet „vollständig
   abgerechnet“ beim Schnellauftrag?
d) Negativer Rest (Überzahlung): Wo verhindern Schema, Rundung, PDF und Zahlungen heute eine Schlussrechnung mit negativem
   Rechnungsbetrag?
e) 1d: Warum lautet das Storno eines alten pauschalen Abschlags auf 0 €?
f) Mahnwesen und Zahlungen: Was müsste sich ändern, damit nach der Schlussrechnung nur noch ihr Zahlbetrag gemahnt wird und die
   Abschläge nicht mehr einzeln?
g) PDF der Schlussrechnung: Aufbau heute, und wo stünden Abzugsblock und Zahlungshinweis.

Befund ins Archiv. Nebenbefunde nur melden. Commit nach Regel 13, nur Archiv.

### Vorweg

- Festlegungen 1.8.81 Nr. 1–18 in `zahlungen.md` an der Überschrift als bestätigt markiert.

### a) Wie die Schlussrechnung heute entsteht

1. **Anlegen**: Auftragsseite "Neue Rechnung" → `POST /api/orders/{id}/invoices/schlussrechnung` (`routers/invoices.py:102`) →
   `create_schlussrechnung()` (`invoices.py:521`). Unter der Sperre der Auftragszeile (`_check_create()`, `:203`): keine zweite
   nicht stornierte Schlussrechnung, auch kein Entwurf (`create_block_reason()`, `:141`); bis R4 kein nicht stornierter pauschaler
   Abschlag (`_lump_sum_reason()`, `:117`). Die Auftragsseite zeigt den Grund statt des Knopfs (`orders.py:474`, `order.html:308`).
2. **Kopf**: Schnappschuss aus dem Auftrag (`_snapshot_order_fields()`, `:234`: Kunde, Objekt, `vat_rate`, Steuerschlüssel samt
   Hinweistext), Zahlungsbedingung mit Skonto (`:280`), Einleitung und Schlusstext; Rechnungsdatum = Tag des Entwurfs (`:313`).
   Keine Bezeichnung (`progress_description`), kein Bezug auf die Abschläge.
3. **Mengen**: `_copy_order_items_with_default_ist(full_completion=True)` (`:420`) kopiert jede Auftragsposition mit "in Summe"
   (Bedarfs- und Alternativpositionen fallen weg, `:429`): Ist = **heutige** Menge der Auftragsposition (`:432`), EP = **heutiger** EP
   (`:442`), Soll nur informativ.
4. **Abzüge -- nur über die Menge, je Position**: abgerechnet = Ist − Ist der letzten gültigen Rechnung derselben Auftragsposition
   (`compute_billed_quantity_and_total()`, `:360`; `get_previous_cumulative_ist()`, `:329`: nur die Arten `abschlag_leistungsstand`
   und `schluss`, `:349`, Status `versendet`, `:348`, nach Rechnungsdatum, dann ID, `:352`). Gerechnet und gespeichert
   (`billed_quantity`/`billed_total`) beim Anlegen des Entwurfs und bei jeder Positionsänderung (`update_invoice_item()`, `:723`),
   **nicht beim Festschreiben** (1b). Pauschale Abschläge (Position ohne Bezug, `:474`) und Rechnungen aus Aufwand (`:610`, `:647`)
   kommen in der Suche nicht vor (1a, c). Abgezogen wird Gestelltes, Zahlungen spielen keine Rolle. Abzugszeilen gibt es nicht -- der
   Abzug steckt in der kleineren Menge.
5. **Nachträge**: einen Nachtrag am Auftrag gibt es nicht. Am Rechnungsentwurf lässt sich eine Position ohne Bezug hinzufügen
   (`add_invoice_item()`, `:657`, "für Nachträge/neue Positionen") -- mit voller Ist-Menge berechnet (`:368`), auf keine spätere
   Rechnung übernommen, von keiner abgezogen. Nachgerechnet: Nachtrag 10 m × 100 € auf einem Abschlag (40 %) -- die Schlussrechnung
   kennt ihn nicht (nur Position 1 mit 60 m²), der Auftrag zeigt danach 6.000 € abgerechnet bei 5.000 € Auftragssumme. Ändern lässt
   sich dagegen jederzeit die Auftragsposition selbst (Nebenbefund 1).
6. **Steuer**: ein Satz je Rechnung (`Invoice.vat_rate`), beim Anlegen vom Auftrag (`:245`), im Entwurf über den Steuerschlüssel
   änderbar (`update_invoice_tax_key()`, `:964`). Die USt wird einmal auf die Nettosumme der Rechnung gerundet
   (`compute_invoice_totals()`, `:416`); die Schlussrechnung rechnet sie nur auf ihren Rest, die USt der Abschläge erscheint nicht.
   Nichts gleicht den Satz der Abschläge mit dem der Schlussrechnung ab -- nachgerechnet: Abschlag mit Steuerschlüssel 0 % (3.000 €
   netto samt Nachtrag, 0 € USt), Schlussrechnung 19 % auf 60 m² (3.570 € brutto).
7. **Summen**: `compute_invoice_totals()` (`:394`): Netto = Summe der auf den Cent gerundeten Positionsbeträge, USt, Brutto -- nie
   gespeichert, bei jedem Lesen neu (Regel 19).
8. **Festschreiben** (`finalize_and_send_invoice()`, `:759`): unter der Sperre `finalize_block_reason()` (`:181`: zweite
   Schlussrechnung, pauschaler Abschlag, Leistungszeitraum), Rechnungsdatum und Fälligkeit auf heute (`:782`), Kunde, Name und
   Anschrift vom Auftrag (`:785`), Nummer (`:791`). Die Beträge werden nicht neu gerechnet.
9. **Danach**: keine Abschläge mehr (`:132`), kein Storno eines Abschlags (`:164`), "vollständig abgerechnet"
   (`invoice_summary_for_order()`, `:1191`). Zahlstand, Mahnung und Abrechnungsstand nehmen das Brutto der Schlussrechnung = den Rest
   (siehe f).

**Wo die Endrechnung ansetzen müsste** -- die Stellen, die heute Betrag und Bedeutung der Schlussrechnung tragen:
- **Positionen zu 100 %**: `_copy_order_items_with_default_ist()` `:431-437` -- heute "100 % minus letzter Stand" je Position.
- **Betrag**: `compute_invoice_totals()` (`:394`) ist die einzige Rechenstelle, jeder Leser nimmt `gross_total` als den einen Betrag
  der Rechnung: Zahlstand und Buchen (`payable_gross()`, `payments.py:77`), Skonto (`skonto_offer()`, `invoices.py:981`), Mahnung
  (über den Zahlstand, `reminders.py:701`), Abrechnungsstand am Auftrag (`invoices.py:1203`), Finanzen und Projektmappe
  (`invoice_overview_row()`, `:1250`), Rechnungs-Mail `{gesamtbetrag}` (`:1330`), PDF (`invoice_pdf.py:181`), Rechnungsseite
  (`invoice_detail.html:96`). **Einen Zahlbetrag neben dem Rechnungsbetrag gibt es nirgends**, auch nicht als Begriff im Code.
- **Abzugsliste**: die festgeschriebenen, nicht stornierten Abschläge eines Auftrags sind über `VALID_STATUSES` (`:69`) und
  `PROGRESS_INVOICE_TYPES` (`:66`) bestimmbar, Rechnungen aus Aufwand (Entscheidung 12.10.) über die Art `aufwand`. "Noch offen aus
  Abschlag" liefert je Abschlag der Zahlstand (`payments.py:166`: offen, Einbehalt offen, mahnfähig) -- live, mit jeder Buchung anders.
- **Zeitpunkt**: das Festschreiben (`invoices.py:759`) liest vom Stand der anderen Rechnungen nur die Sperrgründe; der Abzug stammt
  aus dem Entwurf (1b).
- **Sperre**: `_lump_sum_reason()` (`:117`) ist der Übergang bis R4.
- **Abrechnungsstand**: `compute_order_billing_progress()` (`:1203`) summiert das Brutto jeder gültigen Rechnung außer Stornos
  (`:1213`) -- stimmig, solange die Schlussrechnung nur den Rest trägt; mit der Gesamtleistung als Rechnungsbetrag zählten die
  Abschläge doppelt. Daran messen die Auftragsseite ("Noch offen", `orders.py:471`) und die xfail-Tests 1a/1b (siehe unten).
- **Storno der Schlussrechnung**: kopiert ihre Positionen mit umgekehrtem Vorzeichen (`invoices.py:893`); danach sind die Abschläge
  wieder stornierbar, eine neue Schlussrechnung rechnet neu (grün, Punkt 1).

### b) Abschläge nach Leistungsstand: die abgerechnete Menge je Position

- **Verknüpfung**: `InvoiceItem.source_order_item_id` (`models.py:1808`) auf die Auftragsposition; `ist_quantity` = kumulierter
  Stand, `billed_quantity`/`billed_total` = Differenz zur letzten gültigen Rechnung derselben Position (Abschlag nach Leistungsstand
  oder Schluss, `invoices.py:329`, `:360`). Ein neuer Abschlag beginnt mit Ist = letzter Stand (`:434`, abgerechnet 0), das Büro
  trägt den neuen Stand ein (`update_invoice_item()`, `:696`; Rechnungsseite "Ist (gesamt)", `invoice_detail.html:139`). Die
  Schlussrechnung setzt Ist = Menge des Auftrags und rechnet so den Rest (a 3/4).
- **"Letzter Stand"** ist der der Rechnung mit dem spätesten Rechnungsdatum (seit 1.8.75 der Tag des Festschreibens), am selben Tag
  der mit der höheren ID (= später **angelegt**, nicht später festgeschrieben, `:352`) -- nicht der höchste Stand. Unterschiedlich
  nur bei Entwürfen nebeneinander (1b).
- **Preis**: abgerechnet wird Menge × EP der Schlussrechnung = heutiger EP der Auftragsposition; die Abschläge tragen den EP ihres
  Anlegens. Nachgerechnet: Abschlag 40 m² × 50 € (2.000 €), danach Auftragsposition auf 120 m² × 60 € geändert (Nebenbefund 1),
  Schlussrechnung 80 m² × 60 € = 4.800 € -- zusammen 6.800 € bei 7.200 € Auftragssumme, "noch offen" 400 € trotz gültiger
  Schlussrechnung.
- **Wer die Mengen-Differenz liest** (`grep` über `app/`): Anlegen und Bearbeiten der Abschläge nach Leistungsstand (`:434-437`,
  `:723`), Anlegen der Schlussrechnung (`:431-437`), Nachtrags-Positionen (`:368`), Storno (übernimmt Ist, kehrt `billed_*` um,
  `:893-900`; die Suche schließt die Art `storno` aus, `:349`), Sperre des Abgleichs mit dem Angebot (`orders.py:842-850`, über
  `source_order_item_id`), PDF (Menge = `billed_quantity`, `invoice_pdf.py:138`; Positionen mit Ist 0 ausgeblendet,
  `invoices.py:910`), Rechnungsseite (Soll / Ist (gesamt) / abgerechnet, `invoice_detail.html:23`, `:139`). Sonst niemand.
- **In einer Endrechnung** (laut Entscheidung alle Positionen zu 100 %, Abzug je Abschlag mit Netto und USt) bestimmt die
  Mengen-Differenz den Betrag der Schlussrechnung nicht mehr. Weiter auf sie angewiesen sind dann: der Abschlag nach Leistungsstand
  selbst (er zeigt nur seinen Zuwachs, Entscheidung "nicht kumuliert" -- heute genau `billed_quantity`), der Vorschlag "Ist = letzter
  Stand" beim nächsten Abschlag, die Sperre des Abgleichs (über die Verknüpfung), die Anzeige Soll/Ist am Abschlag. Pauschale
  Abschläge und Rechnungen aus Aufwand haben keine Mengen je Auftragsposition, nur Beträge -- ein Abzug über die Menge erreicht sie
  nicht (1a), über Beträge stehen alle drei Arten gleich da. Von 1b betreffen (a) und (c) den Abzug der Schlussrechnung (aus dem
  Entwurf); (b), zwei Abschläge nach Leistungsstand als Entwürfe nebeneinander, bleibt auch mit einer Endrechnung ein Fall der
  Mengen-Differenz.

### c) Rechnung aus Aufwand

- **Aufbau**: Auftragsseite "Rechnung aus Aufwand", nur angeboten, wenn gebuchte Zeiten oder Material da sind (`order.html:329`);
  `POST …/invoices/aus-zeitbuchungen` (`routers/invoices.py:112`) übergibt **alle** Zeitbuchungen des Auftrags und das Material
  unterschriebener Einsatzberichte (`service_reports.py:1136`). `create_invoice_from_time_entries()` (`invoices.py:539`): nur
  `booked`, mit Stunden, ohne Schlechtwetter (`:569`); je Mitarbeiter und Tätigkeit eine Position Stunden × globaler
  Stundenverrechnungssatz (`:581`, `:598-615`); Katalogmaterial zusammengefasst mit heutigem Einkaufspreis + Aufschlag (`:619-640`),
  freies Material mit EP 0 (`:641`); alle Positionen ohne `source_order_item_id` (`:610`, `:647`), ohne Soll, abgerechnet = Ist.
  Erster und letzter Arbeitstag als Quelle des Leistungszeitraums (`:589`, `service_period.py:103`). Steuer, Kunde, Zahlungsbedingung
  wie jede Rechnung. `TimeEntry.order_item_id` wird nicht ausgewertet.
- **Regeln**: unter der Sperre der Auftragszeile, aber ohne eigene Regel (`create_block_reason()` liefert für `aufwand` nichts,
  `:139-149`; die Auftragsseite kennt für sie keinen Sperrgrund, `orders.py:475-477`). Keine Markierung an Buchung oder Material:
  dieselben Buchungen gehen in eine zweite Rechnung (nachgerechnet: zweimal 246 €; bekannt, CLAUDE.md).
- **Am Auftrag mit Preisen**: Befund 1.8.73 a gilt unverändert -- weder im Gesamtwert der Schlussrechnung noch abgezogen, kommt
  obendrauf, "noch offen" wird negativ (`orders.py:471`); nach der Schlussrechnung weiter möglich (nachgerechnet; die Entscheidung
  vom 12.10. ist nicht gebaut). Stunden zu einer LV-Position werden zusätzlich zu deren EP berechnet.
- **Schnellauftrag** (`quick_service_orders.py:58`): eine Position "Reparatur/Wartung nach Aufwand", 1 pauschal × 0 €; ebenso die
  Wartung aus dem Wartungsvertrag (`maintenance_contracts.py:691`) und der Auftrag aus einem Befund (`findings.py:244`).
  Auftragssumme 0 €; abgerechnet wird über die Rechnung aus Aufwand (Anstoß: Aufgabe "Rechnung erstellen" nach der Unterschrift des
  Einsatzberichts, `service_reports.py:1336`).
- **"Vollständig abgerechnet"** heißt überall: es gibt eine festgeschriebene, nicht stornierte Schlussrechnung
  (`invoice_summary_for_order()`, `invoices.py:1191-1200`) -- angezeigt in der Projektmappe (`project_folder.html:197`) und in den
  Auftragslisten (`routers/orders.py:105`, `routers/projects.py:299`). Beim Schnellauftrag also nur mit einer Schlussrechnung über
  0 €. Nachgerechnet: Aufwand 3 h × 82 € = 246 € netto festgeschrieben → 1 Rechnung, **nicht** vollständig abgerechnet, "noch
  offen" −246 €; Schlussrechnung über 0 € festgeschrieben (eigene Nummer, "lautet über 0 € oder weniger und ist nicht bebuchbar")
  → vollständig abgerechnet; danach weiter eine Rechnung aus Aufwand möglich. Ohne Schlussrechnung bleibt ein Schnellauftrag
  dauerhaft "nicht vollständig abgerechnet", mit ihr gibt es eine Rechnung über 0 € mit Nummer.
- Aus den Entscheidungen vom 12.10. folgt für den Schnellauftrag rechnerisch (festgestellt, nicht bewertet): der Aufwand zählt zum
  Gesamtwert und wird abgezogen, nach der Schlussrechnung keine Rechnung aus Aufwand -- die Schlussrechnung eines Schnellauftrags
  trüge den Aufwand als Gesamtwert und einen Zahlbetrag von 0 €; "vollständig abgerechnet" bliebe an sie gebunden. Welche Stunden
  abrechenbar sind, regelt Stufe 2d.

### d) Negativer Rest

Ein negativer Betrag entsteht heute nicht über die Eingaben, sondern über die Mengen-Differenz: Ist der Schlussrechnung (oder eines
Abschlags) unter dem schon abgerechneten Stand, z. B. Aufmaß kleiner als abgeschlagen (`invoices.py:374`). Nachgerechnet: Abschlag
100 m² (5.950 €), Schlussrechnung Ist 80 → −20 m², −1.000 € netto, −1.190 € brutto, festgeschrieben mit Nummer. Eine Überzahlung im
Sinne der Endrechnung (Abschläge über der Gesamtleistung) gibt es heute nicht als eigenen Betrag -- die Schlussrechnung *ist* der
Rest.
- **Schema**: Eingaben nicht negativ -- Ist und EP einer Rechnungsposition `ge=0` (`schemas.py:2423-2424`, `:2434-2435`),
  Pauschalbetrag `gt=0` (`:2396`, `:2410`), Menge und EP der Auftragsposition `ge=0` (`:1267`, `:1269`). Keine Prüfung des
  Rechnungsbetrags beim Festschreiben (`finalize_block_reason()`, `invoices.py:181`), keine CHECK-Bedingung in der Datenbank
  (`models.py:1806-1819`). Eine negative Schlussrechnung verhindert also nichts.
- **Rundung**: `round_money()` rundet symmetrisch (Hälfte vom Nullpunkt weg, `rounding.py`), USt und Skonto ebenso
  (`invoices.py:416`, `:989`) -- verhindert nichts; das Skonto wird negativ.
- **PDF**: kein Sonderfall, das PDF entsteht fehlerfrei: "Schlussrechnung", "Rechnungsbetrag brutto -1.190,00 EUR"
  (`invoice_pdf.py:181`), darunter der Zahlungssatz "Zahlbar rein netto bis zum … Bei Zahlung bis zum … gewähren wir 2 % Skonto, das
  entspricht -23,80 €." (`invoices.py:1026-1031`, nachgerechnet). Die Rechnungs-Mail nennt `{gesamtbetrag}` negativ (`:1330`).
- **Zahlungen**: hier wird abgelehnt -- `not_payable_reason()`: "lautet über 0 € oder weniger und ist nicht bebuchbar"
  (`payments.py:94`), kein Zahlstand (`:186`): nie offen, nie überfällig, keine Mahnung (`reminders.py:286`, derselbe Text,
  nachgerechnet), nicht im "Offenen Betrag" (`finanzen.html:56`). Eine Erstattung lässt sich nicht buchen: Zahlungen nur über 0 €
  (`payments.py:526`, `_cents()` `:383-391`), Zuordnungen nicht negativ; die Gegenbuchung (`reverse_payment()`) nimmt eine Buchung
  zurück, sie zahlt nichts aus. Ein Guthaben des Kunden erscheint nirgends: die bezahlten Abschläge bleiben "bezahlt", "nicht
  zugeordnet" zählt nur Eingänge (`unallocated_by_customer()`, `payments.py:755`).
- **Abrechnungsstand**: zählt die negative Schlussrechnung mit (nachgerechnet 4.000 € abgerechnet, "vollständig abgerechnet"). Ihr
  Storno lautet positiv (+1.190 €) und ist als Stornorechnung nie offen (`payments.py:86`).
- In einer Endrechnung wäre der Rechnungsbetrag (Gesamtleistung) positiv und nur der Zahlbetrag negativ; heute gibt es nur den einen
  Betrag, an dem `payable_gross()` hängt (a).

### e) 1d: das Storno eines alten pauschalen Abschlags lautet über 0 €

- Bis 1.3.24 hatte der pauschale Abschlag keine Position, der Betrag stand nur in `lump_sum_net` (`models.py:1735-1739`). Seit 1.3.24
  spiegelt ihn eine Projektionsposition (`_sync_lump_sum_pauschal_item()`, `invoices.py:451`); festgeschriebene Altfälle bekamen sie
  nie -- sie entsteht nur beim Anlegen und beim Bearbeiten eines Entwurfs (`:499`, `:935-936`).
- `create_storno_draft()` (`:857`) legt eine Rechnung der Art `storno` an, übernimmt `lump_sum_net` negiert (`:884`) und kopiert die
  Positionen mit umgekehrtem Vorzeichen (`:893-900`) -- beim Altfall keine. Die Rundungsregel wird übernommen (`:892`), beim Altfall
  leer.
- `compute_invoice_totals()` liest `lump_sum_net` nur für die Art `abschlag_pauschal` (`:406`, `:412`), für jede andere Art die Summe
  der Positionen (`:409`, `:415`). Das Storno hat die Art `storno` -- also 0. Nachgerechnet: Storno-Entwurf mit `lump_sum_net`
  −2.000, 0 Positionen, Regel leer → netto 0, USt 0, brutto 0. Zum Vergleich ein pauschaler Abschlag mit Projektionsposition: Storno
  −2.000 / −380 / −2.380 €.
- Das Festschreiben setzt das Original trotzdem auf `storniert` (`:793-796`) -- es fällt aus Abrechnungsstand, Zahlungen und
  Mahnwesen heraus, eine Gutschrift über 2.380 € steht nirgends. Das PDF des Stornos zeigt "Stornierung zu Rechnung …", eine leere
  Positionstabelle und 0,00 EUR (`invoice_pdf.py:117-119`, `:125-182`).
- Betroffen: pauschale Abschläge ohne Position (vor 1.3.24), laut `projektliste-und-mappe.md` R-2026-0001/-0002 im alten lokalen
  Bestand. Auf dem Server Probebelege, die zum Echtbetrieb entfernt werden (Entscheidung 12.10.); dort nichts geprüft (Regel 16),
  Prüfabfrage 1d in Punkt 1.

### f) Mahnwesen und Zahlungen nach der Schlussrechnung

Heute ist jede Rechnung für sich offen und wird für sich gemahnt; die Schlussrechnung ist eine weitere, über den Rest. Nachgerechnet:
Abschlag 40 % festgeschrieben und überfällig, danach Schlussrechnung festgeschrieben und überfällig -- "zur Mahnung fällig" listet
beide (2.380 € und 3.570 €), zum Abschlag entsteht weiter ein Mahnungsentwurf.

Die Stellen, die das Mahnen an eine einzelne Rechnung binden:
1. **Liste "zur Mahnung fällig"** (`list_invoices_needing_attention()`, `reminders.py:1082`): jede festgeschriebene, überfällige
   Rechnung außer Stornos (`:1088-1091`) mit mahnfähigem Betrag -- ohne Blick auf eine Schlussrechnung am Auftrag. Darauf bauen
   Dashboard ("Mahnung" je überfälliger Rechnung) und Finanzen ("überfällig").
2. **Anlegen und Festschreiben** (`create_block_reason()`, `:291`; `finalize_and_send_reminder()`, `:730`): die Gründe kennen Storno,
   bezahlt, Einbehalt, Fälligkeit und Stufe, nicht die Art der Rechnung oder eine Schlussrechnung. Eine festgeschriebene Mahnung zum
   Abschlag geht nach der Schlussrechnung weiter hinaus, solange ihr Betrag stimmt (`dispatch_block_reason()`, `:592`;
   nachgerechnet: M-2026-0001 zum Abschlag, danach Schlussrechnung festgeschrieben -- kein Sperrgrund).
3. **Die Mahnung hängt an genau einer Rechnung** (`Reminder.invoice_id`, `models.py:1892`): Betrag = mahnfähiger Betrag dieser
   Rechnung (`reminders.py:701`), Aufstellung aus ihrem Zahlstand (`amounts_snapshot()`, `:406`), PDF "zu Rechnung …" mit deren
   Beträgen (`reminder_pdf.py:57-65`, `:117`).
4. **Stufen je Rechnung**: erreichte und nächste Stufe, Frist aus den Mahnungen und der Fälligkeit dieser Rechnung (`_step()`,
   `:259`). Die Schlussrechnung beginnt bei Stufe 0, auch wenn ein Abschlag schon in der 2. Mahnung steht.
5. **Verzug und Nebenforderungen je Rechnung**: Verzugsbeginn (`InvoiceDefaultStart.invoice_id`, `models.py:2038`), Nebenforderung
   (`InvoiceCharge.invoice_id`, `:2011`), Pauschale einmal je Rechnung (`dunning_charges.py:489-512`), Verzugszinsen auf den
   mahnfähigen Betrag der Rechnung (`interest_proposal()`, `default_interest.py:238`). Was an einem Abschlag entstanden ist, bleibt
   dort; das Storno eines Abschlags ist nach der Schlussrechnung gesperrt (`invoices.py:164`).
6. **Zahlstand je Rechnung** (`payments.py:166`): offen = Brutto dieser Rechnung − Zahlungen − Skonto; Einbehalt je Rechnung. Ein
   Einbehalt am Abschlag steht nach der Schlussrechnung weiter dort ("Einbehalt offen"); einen Zahlungshinweis der Schlussrechnung,
   der ihn nennt, gibt es nicht (g).
7. **Zahlungen**: der Vorschlag geht schon heute zuerst auf die älteren offenen Rechnungen desselben Auftrags, dann auf die gewählte
   (`proposal()`, `payments.py:285-287`) -- nachgerechnet: 5.950 € auf die Schlussrechnung → 2.380 € Abschlag, 3.570 €
   Schlussrechnung, Rest 0. Das entspricht der Entscheidung "zuerst offene Abschläge, ältester zuerst", nimmt aber auch Rechnungen aus
   Aufwand des Auftrags mit und nur solche mit älterem Rechnungsdatum. Mit der Gesamtleistung als Rechnungsbetrag wäre das "offen" der
   Schlussrechnung die Gesamtleistung, nicht der Zahlbetrag (`payable_gross()`, a).
8. Ob ein Abschlag nach der Schlussrechnung noch selbständig gemahnt oder verzinst werden darf, ist eine Rechtsfrage und hier nicht
   bewertet.

### g) PDF der Schlussrechnung

Aufbau heute (`build_invoice_pdf()`, `invoice_pdf.py:61`), für alle Arten gleich:
1. DIN-5008-Kopf mit Rechnungsnr., Datum, Kunden-Nr., Vorgangs-Nr., Seite (`:92-98`), Objektadresse (`:100`).
2. Überschrift "Schlussrechnung" (`:16-22`, `:106`), Leistungszeitraum (`:109`), Einleitung (`:120`) -- eine Bezeichnung wie beim
   Abschlag hat die Schlussrechnung nicht.
3. Positionstabelle Pos. / Menge Einh. / Leistung / EP / GP (`:125-180`): Menge = **abgerechnete** Menge (`:138`), GP = abgerechneter
   Betrag (`:142`); Positionen mit Ist 0 ausgeblendet -- eine von Abschlägen ganz abgedeckte Position erscheint mit Menge 0 und 0,00.
4. Summenblock "Nettosumme (diese Rechnung)" / "zzgl. MwSt. x %" / "Rechnungsbetrag brutto" (`:181-182`, `_totals_table()`, `:25`).
5. Schlussblock (`build_payment_tax_closing_block()`, `document_pdf.py:267`): "Zahlungsbedingungen" mit dem Zahlungssatz
   (`format_payment_terms_sentence()`, `invoices.py:992`: Fälligkeit, Skonto auf das Brutto dieser Rechnung, `:981`), Hinweis zur
   Umsatzsteuer, Schlusstexte.

- **Abzugsblock**: stünde zwischen Positionstabelle bzw. Summenblock (`invoice_pdf.py:180-182`) und Schlussblock (`:187`) -- der
  Summenblock ist die einzige Stelle, an der Beträge zusammengezählt werden; heute steht dort nur der Rest.
- **Zahlungshinweis**: der Zahlungssatz im Schlussblock (`:188`) kennt nur Fälligkeit und Skonto; Einbehalt, "noch offen aus
  Abschlag" und Zahlbetrag kommen nirgends vor. Rechnungsseite (Netto/USt/Brutto, `invoice_detail.html:96`) und Rechnungs-Mail
  (`{gesamtbetrag}`) kennen ebenfalls nur den einen Betrag.
- **Zeitpunkt**: bis zum ersten Versand entsteht das PDF einer festgeschriebenen Rechnung bei jedem Abruf neu
  (`frozen_or_fresh_pdf()`, `sent_documents.py:172`; Download `routers/invoices.py:278`), erst ab dem Versand liegt es in der Ablage
  (Regel 21). Beträge werden nie gespeichert (Regel 19); einen eingefrorenen Stand von Zahlungen gibt es heute nur an der Mahnung
  (`Reminder.amounts_json`). Ein Abzugsblock mit "noch offen aus Abschlag" aus dem Zahlstand ergäbe zwischen Festschreiben und
  Versand je nach Buchungsstand ein anderes PDF.
- **Steuer**: ein Satz je Rechnung ("zzgl. MwSt. x %", `invoice_pdf.py:181`); ein Abschlag mit anderem Satz (a 6) brächte im
  Abzugsblock einen zweiten -- die Entscheidung "keine mehreren Steuersätze je Rechnung" betrifft das (festgestellt, nicht bewertet).
  Die USt jeder Rechnung ist einmal gerundet (`invoices.py:416`); die Summe der gerundeten USt der Abschläge kann vom auf die
  Gesamtleistung gerundeten Betrag um Cent abweichen (drei Abschläge zu 100,03 € netto: 3 × 19,01 = 57,03 €; 300,09 € × 19 % =
  57,0171 → 57,02 €; gerechnet, nicht im Test). Ob die Endrechnung so § 14 Abs. 5 UStG genügt, ist eine Rechtsfrage.

### Zu den xfail-Tests 1a, 1b, 1d

- **1a und 1b** messen über `compute_order_billing_progress()`: "die gültigen Rechnungen eines Auftrags zusammen = Auftragssumme"
  (`test_v372_befund_schlussrechnung.py:9-12`, `_abgerechnet()` `:59-61`). Das trägt, solange die Schlussrechnung nur den Rest als
  Rechnungsbetrag hat; trägt sie die Gesamtleistung, zählt dieselbe Funktion die Abschläge doppelt (a). Eigenschaft der Tests und
  Bedeutung von "abgerechnet" hängen an derselben Frage.
- **1a** (`:120-141`) verlangt dazu eine gültige Schlussrechnung neben dem pauschalen Abschlag -- bis R4 gesperrt.
- **1d** (`:236-252`) prüft netto −2.000 und brutto −2.380 am Storno -- unabhängig von der Endrechnung.

### Klicktests (Regel 26)

`scripts/klicktest_alle.py` auf dem Stand 1.8.81 (`b7cd16e`, Arbeitskopie; App-Code in dieser Runde unverändert): 50 von 50 wie
erwartet, Laufzeit gesamt 10:43 min. Keine rote Prüfung.

### Nebenbefunde (nur gemeldet)

1. **Auftragspositionen jederzeit änderbar**: Menge, Einheit, EP, Texte und "in Summe" lassen sich auf der Auftragsseite direkt in
   der Zeile ändern (`order.html:101`, `quickItem()` `:314`; `PUT /api/orders/{id}/items/{item_id}`, `routers/orders.py:180`;
   `update_order_item()`, `orders.py:925`) -- ohne Sperre der Auftragszeile, ohne Prüfung auf Rechnungen, Abnahme oder Vertrag, ohne
   Revision. CLAUDE.md nennt den Auftrag einen "unveränderlichen LV-Snapshot". Nachgerechnet (b): nach einem Abschlag Menge und EP
   geändert → Schlussrechnung mit neuem EP, 400 € "noch offen" trotz gültiger Schlussrechnung; danach noch einmal geändert → 2.200 €
   "noch offen". Ebenso der Steuersatz des Auftrags (`update_order_tax_key()`, `orders.py:599`).
2. **Negative Abschläge**: ein Abschlag nach Leistungsstand mit Ist unter dem letzten Stand rechnet negativ (`invoices.py:374`) und
   lässt sich festschreiben -- nie offen, wie die negative Schlussrechnung. Nachgerechnet: Abschlag 40 m², danach Abschlag mit Ist
   30 → −10 m², −595 € brutto, mit Nummer.
3. **"Vertragspauschale" ohne Grundlage**: der Docstring von `create_maintenance_visit()` (`maintenance_contracts.py:663`) sagt,
   Wartung werde "über die Vertragspauschale oder nach Aufwand" abgerechnet; der Wartungsvertrag hat kein Preisfeld
   (`MaintenanceContract`, `MaintenanceContractItem`), und die Wartung ist ein Schnellauftrag über 0 €. Eine Pauschale ginge dort nur
   als pauschaler Abschlag -- der sperrt bis R4 die Schlussrechnung.

## Umsetzung 1.8.82: feste Fassung der Rechnung, Sperren am Auftrag (R4a, Punkte 1 und 2)

### Vorgabe vom 12.10.2026 (übernommen wie gegeben)

Befund R4 geprüft. Klarstellung zu den xfail-Tests: Der Betrag der Schlussrechnung (Brutto für Zahlungen, offene Posten,
„abgerechnet“) ist der Rechnungsbetrag nach dem Abzugsblock, nicht die Gesamtleistung; die Gesamtleistung ist nur Anzeige im PDF.
Damit bleibt „abgerechnet = Summe der gültigen Rechnungsbeträge“ richtig, und 1a und 1b messen das Richtige.

R4a Fundament (befund-vor-echtbetrieb.md, „Befund R4“; Entscheidungen ins Archiv):
1. Rechnungs-PDF jeder Art wird beim Festschreiben erzeugt und als feste Fassung mit Prüfsumme abgelegt; danach nie neu erzeugt.
   Versand und Download nur aus der Ablage.
2. Sperren am Auftrag (Nebenbefund 1): Einheitspreis und „in Summe“ einer Position gesperrt, sobald eine festgeschriebene Rechnung
   auf sie verweist; Steuersatz gesperrt ab der ersten festgeschriebenen Rechnung; Mengen bis zur Schlussrechnung änderbar; nach
   gültiger Schlussrechnung alles gesperrt. 409 mit Grund.
3. Nachträge nur als gekennzeichnete Auftragsposition; freie Positionen ohne Auftragsbezug nur in Rechnungen aus Aufwand.
4. Ein Abschlag nach Leistungsstand mit negativem Betrag wird abgelehnt, 409 mit Hinweis auf Storno oder Schlussrechnung
   (Nebenbefund 2).
5. „Letzter Stand“ einer Position ist der des zuletzt festgeschriebenen Abschlags, nicht des zuletzt angelegten.
6. 1d: Das Storno eines pauschalen Abschlags ohne Positionen lautet auf den Gegenbetrag des Originals.

xfail 1d muss grün werden, Markierung dann entfernen. Angriffstests mit Gegenprobe, Gleichzeitigkeit gegen PostgreSQL. Eigene
Festlegungen mit „Bitte bestätigen“. Nebenbefunde nur melden. Wird der Umfang zu groß: nach Punkt 2 committen und den Rest
auflisten. Commit nach Regel 13, Bericht kurz.

### Vorweg

- Klarstellung und Entscheidungen R4a unter "Entscheidungen Rechnungen" (Ende dieser Datei) eingetragen.
- Umfang: nach Punkt 2 committet (1.8.82); Punkte 3–6 als eigene Version 1.8.83 ("Umsetzung 1.8.83" unten).

### Was gebaut ist

- **Feste Fassung beim Festschreiben** (`app/invoices.py::_store_fixed_pdf()`, aufgerufen in `finalize_and_send_invoice()` nach
  Datum, Kunde, Nummer und Status, vor dem Commit): das PDF jeder Rechnung -- jede Art, auch Storno -- entsteht im Stand des
  Festschreibens und geht in die Ablage (`app/sent_documents.py::store_sent_document()`, Art "rechnung", Dokument-ID = Rechnung,
  Nummer, Datei `<Nummer>.pdf`, SHA-256, angelegt von der festschreibenden Person). Die Rechnung verweist darauf
  (`Invoice.pdf_document_id`, FK `sent_documents`, Migration `6d1e8b3f2a47`). Alles in einem Commit: keine festgeschriebene
  Rechnung ohne Fassung. Scheitert das PDF oder die Ablage, rollt das Festschreiben zurück -- Status Entwurf, keine Nummer, der
  Nummernkreis unverändert --, ValueError mit Text, Router 400; `logger.error` mit Rechnungs-ID und Klassenname (Regel 18).
- **Danach nie neu erzeugt**: `frozen_version()` liefert bei einer Rechnung zuerst die feste Fassung -- Download
  (`GET /api/invoices/{id}/pdf`, Kopfzeile `X-DK-Ablage`), E-Mail-Versand (`send_invoice_email()`: der Anhang IST die Fassung, der
  Eintrag verweist nur, legt nichts ab) und nachgetragene Zustellung (`app/dispatch_documents.py`) nehmen nur diese Bytes, nur mit
  stimmender Prüfsumme (sonst 409/410 bzw. "nicht mehr unversehrt", nie still neu erzeugt) -- auch vor dem ersten Versand, nach
  einem geänderten Briefkopf und nach einem fehlgeschlagenen Versand. Vorher (bis 1.8.81) entstand das PDF bis zum ersten
  nicht fehlgeschlagenen Versand bei jedem Abruf neu, mit dem Briefkopf von heute.
- **Verweis steht fest**: ORM-Sperre `_invoice_pdf_fixed` (`app/models.py`) -- `pdf_document_id` einmal von leer auf die Ablage,
  danach weder auf ein anderes Dokument noch zurück auf leer (`ArchiveImmutableError`).
- **Sperren am Auftrag** (neu `app/order_locks.py`, geprüft unter der Sperre der Auftragszeile `lock_order_invoices()`, dieselbe
  wie das Festschreiben; abgelehnt wird nur eine tatsächliche Änderung, `OrderLocked` = 409 mit Grund):
  - **Einheitspreis, Einheit, "in Summe"** einer Position (`update_order_item()`): gesperrt, sobald eine gültige Rechnung
    (festgeschrieben, nicht storniert, kein Storno) sie abrechnet -- Rechnungsposition mit Verweis und Ist ≠ 0. Grund nennt die
    Rechnungen: "Einheitspreis, Einheit und „in Summe“ sind gesperrt: die Position ist in R-… abgerechnet. Die Menge bleibt bis zur
    Schlussrechnung änderbar; für einen anderen Preis zuerst die Rechnung stornieren."
  - **Steuerschlüssel** (`update_order_tax_key()`): ab der ersten gültigen Rechnung gleich welcher Art (auch pauschal, Aufwand).
  - **Menge, Texte, Positionstyp, OZ**: bis zur Schlussrechnung frei.
  - **Nach einer gültigen Schlussrechnung**: jedes Feld jeder Position, LV-Titel (`update_order_section()`), Steuerschlüssel --
    "Nach der Schlussrechnung R-… ist der Auftrag abgerechnet: … Ausweg: die Schlussrechnung stornieren."
  - **Abgleich mit dem Angebot** (`sync_block_reasons()`): zusätzlich gesperrt nach einer gültigen Schlussrechnung (auch einer ohne
    Positionen) und, solange eine gültige Rechnung besteht, wenn das Angebot einen anderen Steuerschlüssel oder Satz hat (vorher
    hätte ein pauschaler Abschlag, der an keiner Position hängt, den Abgleich samt Steuersatz durchgelassen).
  - Router (`app/routers/orders.py`): Position, Steuerschlüssel, LV-Titel 409 vor 400/404.
- **Auftragsseite** (`order.html`, `order_to_dict()`: `order_lock`, `tax_lock`, je Position `price_lock`): an einer abgerechneten
  Position "Abgerechnet – Einheitspreis, Einheit und „in Summe“ gesperrt", Preis und Einheit gesperrt (Grund als Tooltip, im Dialog
  als Hinweis, dort auch "in Summe"); Steuerschlüssel gesperrt mit Grund darunter; nach der Schlussrechnung der Grund über dem LV,
  jede Eingabe gesperrt, keine Bearbeiten-Knöpfe an Positionen und Titeln. Der Hinweis "Prozesslogik" nennt die Sperren.
- Klicktest `scripts/klicktest_auftrag_sperren.py`.

### Festlegungen 1.8.82 (Nr. 1–5 bestätigt am 12.10.2026, Vorgabe R4b; Nr. 6–9 dort nicht genannt)

1. **Feste Fassung jeder Art**, auch Storno; im selben Commit wie das Festschreiben. Scheitert das PDF oder die Ablage, ist nichts
   festgeschrieben (400 mit Text) -- lieber kein Festschreiben als eine Rechnung ohne Fassung.
2. **Altbestand** (vor 1.8.82 festgeschrieben, ohne Fassung): bleibt bei der alten Regel -- bis zum ersten nicht fehlgeschlagenen
   Versand neu erzeugt, danach aus der Ablage. Keine nachträgliche Fassung, weder per Migration (sie entstünde mit dem Briefkopf von
   heute) noch beim Lesen (Regel 23). Auf dem Server sind es Probebelege.
3. **Entwurf**: die PDF-Vorschau entsteht weiter neu ("(Entwurf)", ohne Ablage). Mahnungen bleiben bei der alten Regel -- Punkt 1
   nennt nur Rechnungen.
4. **"Verweist" = rechnet ab**: eine Rechnungsposition mit Verweis und Ist ≠ 0 einer gültigen Rechnung (festgeschrieben, nicht
   storniert, kein Storno). Eine Position mit Ist 0 steht nicht auf der Rechnung (ein Abschlag kopiert alle Positionen, auch die
   noch nicht begonnenen) und sperrt nicht; ist die Rechnung storniert, ist die Position wieder frei -- so lässt sich ein falscher
   Preis über Storno und neuen Abschlag berichtigen.
5. **Mit dem Einheitspreis auch die Einheit**: der Preis gilt je Einheit, "m² → Stk." bei gleichem Preis änderte, was abgerechnet
   ist. Texte, Positionstyp und OZ bleiben bis zur Schlussrechnung frei wie die Menge.
6. **Steuersatz = Steuerschlüssel** (Satz und Hinweistext); gesperrt, solange eine gültige Rechnung besteht -- sind alle storniert,
   wieder frei. Derselbe Schlüssel noch einmal geht durch.
7. **"Alles" nach der Schlussrechnung** = Positionen (jedes Feld), LV-Titel, Steuerschlüssel und der Abgleich. Nicht gesperrt: die
   Auftragsdaten im Kopf (Status -- "abgeschlossen" kommt nach der Schlussrechnung --, Termine, Sachbearbeiter, Texte, Bemerkungen);
   Vertragsgrundlage und Gewährleistung haben eigene Sperren. Nach dem Storno der Schlussrechnung wieder offen, die Preise der von
   Abschlägen abgerechneten Positionen bleiben gesperrt.
8. **Nur eine tatsächliche Änderung wird abgelehnt**: die Oberfläche schickt beim Speichern einer Position alle Felder; unverändert
   (auch "50.000" statt "50") geht durch (200).
9. **Abgleich mit dem Angebot**: zusätzlich gesperrt nach gültiger Schlussrechnung und bei anderem Steuerschlüssel/Satz des Angebots,
   solange eine gültige Rechnung besteht (sonst ein zweiter Weg am gesperrten Steuersatz vorbei).

### Tests und Prüfung

- Neu `tests/test_v385_feste_fassung_rechnung.py` (17, davon 2 gegen PostgreSQL): feste Fassung je Art (pauschal, Leistungsstand,
  Schluss, Aufwand) mit Nummer, Datum und Briefkopf vom Festschreiben, Storno mit eigener Fassung (die des Originals bleibt), Entwurf
  neu erzeugt ohne Ablage; Download und erster Versand nach geändertem Briefkopf = Fassung, ein fehlgeschlagener Versand ändert nichts,
  eine nachgetragene Zustellung verweist auf sie. **Angriffe**: Datei verändert bzw. gelöscht -> 409/410, kein Versand, nicht neu
  erzeugt; Verweis über das ORM ändern oder leeren -> abgelehnt; PDF bzw. Ablage scheitert -> nichts festgeschrieben, Nummer frei,
  Router 400. **Gleichzeitig (PostgreSQL, Commit der ersten Aktion eine Sekunde angehalten):** zwei Festschreiben desselben Entwurfs
  -> eine Nummer, eine Fassung; das Festschreiben wartet auf eine laufende Änderung und legt deren Stand ab.
- Neu `tests/test_v385_auftrag_sperren.py` (36, davon 4 gegen PostgreSQL): Preis, Einheit und "in Summe" je gesperrt nach einem
  Abschlag, Menge und Texte offen, unverändertes Speichern geht; frei ohne Rechnung, mit Entwurf, mit Ist 0, nach Storno, mit
  pauschalem Abschlag; Steuerschlüssel nach Abschlag nach Leistungsstand, pauschalem Abschlag und Rechnung aus Aufwand gesperrt, nach
  Storno aller frei; nach der Schlussrechnung jedes Feld, LV-Titel und Steuerschlüssel, nach ihrem Storno wieder offen (der Preis der
  vom Abschlag abgerechneten Position bleibt gesperrt); Gründe für die Auftragsseite; Router 409 bzw. 404; Abgleich gesperrt nach einer
  Schlussrechnung ohne Positionen und bei anderem Steuersatz. **Gleichzeitig (PostgreSQL):** Preis-, Mengen- und Steueränderung warten
  auf das Festschreiben und lehnen danach ab; das Festschreiben wartet auf eine Mengenänderung, die durchgeht.
- Neu `tests/test_v385_feste_fassung_migration.py` (2, davon 1 gegen PostgreSQL): Bestand bleibt, keine nachträgliche Fassung, Rückweg
  exakt, mit Fassung verweigert. `alembic check` auf einer Wegwerf-SQLite: keine Abweichung zwischen Modell und Migrationen.
- **Erwartung geändert** (die Regel "bis zum ersten Versand neu erzeugt" gilt für Rechnungen nicht mehr, "nichts abgelegt" heißt jetzt
  "nur die feste Fassung"): `test_v321` (ungültige Adresse; Versender "rechnung": die Fassung vom Festschreiben), `test_v323` (ungültige
  Adresse; Nachdruck schon vor dem Versand aus der Ablage; Nachdruck der Mahnung zählt nur Mahnungen; fehlgeschlagener und hängender
  erster Versand jetzt an einer Rechnung von vor 1.8.82, `vor_1_8_82()`), `test_v324` (ungültige Zustellung), `test_v382` (Zustellung
  einer Mahnung).
- Gegenproben (Regel 24): 21 von 21 rot -- Festschreiben ohne Fassung, Fassung vor der Nummer, Fehler beim PDF ohne Rücknahme,
  maßgeblich erst ab Versand, ORM-Sperre aus; Position bzw. Steuer ohne Zeilensperre (PostgreSQL), Preis bzw. Einheit nicht gesperrt,
  nach der Schlussrechnung nicht alles, Entwurf, Storno bzw. Ist 0 sperren den Preis, Steuer nicht gesperrt bzw. Storno zählt, Titel
  frei, Abgleich ohne Schlussrechnung bzw. Steuer, Auftragsseite ohne Gründe, Router 404 statt 409, unveränderte Werte abgelehnt. Jede
  Datei byte-genau zurück (SHA-256), kein Marker.
- Klicktest `klicktest_auftrag_sperren.py` 17/17 (abgerechnete Position mit gesperrtem Preis und Einheit, Grund im Tooltip, an der
  Position und im Dialog, Menge gespeichert, API 409; Steuerschlüssel gesperrt; nach der Schlussrechnung Grund über dem LV, jede Eingabe
  gesperrt, keine Bearbeiten-Knöpfe; Rechnungs-PDF aus der Ablage, Entwurf neu erzeugt; hell, dunkel, 412 px).
- Volle Suite (mit den opt-in-Tests gegen PostgreSQL, Arbeitskopie): 3706 grün, 1 rot, 7 erwartet fehlgeschlagen (1a, 1b, 1d) -- rot
  war `test_v382_mahnwesen.py::test_manual_delivery_counts_the_state_on_the_delivery_day` (erwartete eine leere Ablage, siehe "Erwartung
  geändert"), angepasst, die Datei danach 34 grün.
- Alle Klicktests (Regel 26, `scripts/klicktest_alle.py`, Arbeitskopie): 51 von 51 wie erwartet, Laufzeit gesamt 10:38 min. Keine rote
  Prüfung.

### Nebenbefunde (nur gemeldet)

1. **Rechnungsentwurf mit altem Einheitspreis**: ein Entwurf übernimmt den Preis beim Anlegen. Ändert das Büro den Preis am Auftrag,
   solange die Position nur in Entwürfen steht (das ist erlaubt), schreibt das Festschreiben des Entwurfs den alten Preis fest --
   danach ist der Auftrag mit dem neuen gesperrt, Auftrag und Rechnung weichen ab. Ebenso lässt sich der Preis einer Position mit
   Auftragsbezug im Entwurf frei ändern (`update_invoice_item(unit_price=…)`, Rechnungsseite). Gehört zu 1b (Abzug aus dem Entwurf).
2. **Steuerschlüssel des Rechnungsentwurfs frei**: `update_invoice_tax_key()` wählt je Rechnung einen beliebigen Schlüssel, unabhängig
   vom gesperrten Steuersatz des Auftrags -- Abschlag mit 0 %, Schlussrechnung mit 19 % bleibt möglich (Befund R4 a6).
3. **Datei ohne Eintrag**: scheitert der Commit nach dem Ablegen (Datenbankfehler), bleibt die Datei der Fassung ohne Eintrag in der
   Ablage liegen -- dasselbe wie bei Vertrag und Checkliste; nichts verweist auf sie.
4. **Auftragsliste rechnet je Auftrag alles**: `GET /api/orders` (`app/routers/orders.py::list_all_orders()`) ruft für jeden Auftrag
   das volle `order_to_dict()` mit Abgleich, Abrechnungsstand, Rechnungssperren und seit 1.8.82 den Sperren am Auftrag auf -- nur um
   Netto und Brutto zu zeigen; dazu je Auftrag `invoice_summary_for_order()`. Bei wachsender Zahl der Aufträge eine Abfrageflut
   (CLAUDE.md "Datenmenge wächst"); vorher schon so, 1.8.82 legt je Auftrag eine Abfrage dazu.

## Umsetzung 1.8.83: Nachtrag am Auftrag, kein negativer Abschlag, letzter Stand, Storno 1d (R4a, Punkte 3–6)

Vorgabe wie bei 1.8.82 (dort wörtlich); nach Punkt 2 committet (1.8.82), die Punkte 3–6 als diese Version.

### Was gebaut ist

- **Nachtrag als gekennzeichnete Auftragsposition** (Punkt 3; `app/orders.py::add_order_addendum()`, `POST /api/orders/{id}/items`):
  `OrderItem.is_addendum` (Migration `3b8f1d6c9e24`), Positionsnummer "N1", "N2" … (höchste vergebene + 1), hinter allen anderen
  Positionen, ohne LV-Titel; unter der Sperre der Auftragszeile, mit Revision "Nachtrag N1 angelegt". Jede folgende Rechnung kopiert
  ihn wie jede Position (Abschlag nach Leistungsstand mit Ist = letzter Stand, Schlussrechnung zu 100 %), der Auftrag zählt ihn zur
  Summe -- abgerechnet = Auftragssumme mit Nachtrag. Gesperrt nach einer gültigen Schlussrechnung und am stornierten Auftrag
  (`OrderLocked`, 409). **Entfernen** (`remove_order_addendum()`, `DELETE /api/orders/{id}/items/{item_id}`): nur ein Nachtrag, an dem
  nichts hängt (Rechnung jeder Art und jedes Status, Zeit- oder Gruppenbuchung, Material der Arbeitsvorbereitung), nicht nach der
  Schlussrechnung, mit Revision; eine Position aus dem Angebot nie (409). Was an Positionen hängt, prüft seither eine Funktion für
  Abgleich und Nachtrag (`_attached()`, Texte des Abgleichs unverändert). **Abgleich mit dem Angebot** gesperrt, solange Nachträge
  stehen ("am Auftrag steht der Nachtrag N1, den der Abgleich löschen würde").
- **Freie Positionen nur in Rechnungen aus Aufwand**: `add_invoice_item()` ohne Auftragsbezug an jeder anderen Art 409
  (`FREE_ITEM_TEXT`, mit Hinweis auf "+ Nachtrag"); ein Entwurf von Abschlag nach Leistungsstand oder Schlussrechnung, der vorher eine
  freie Position bekam, lässt sich nicht festschreiben (`free_items_reason()`, nennt die Positionen). Die Projektionsposition des
  pauschalen Abschlags bleibt ohne Bezug. Vorher (bis 1.8.82) stand ein Nachtrag nur in der einen Rechnung, keine spätere übernahm oder
  zog ihn ab (Befund R4 a 5).
- **Kein negativer Abschlag nach Leistungsstand** (Punkt 4, `negative_progress_reason()` in den Regeln des Festschreibens): Betrag
  unter 0 -> 409 "Der Abschlag lautet über -595,00 €: das Ist liegt unter dem zuletzt abgerechneten Stand. Ein Abschlag nach
  Leistungsstand nimmt nichts zurück – zu viel Abgerechnetes korrigiert das Storno des Abschlags, der zu viel abgerechnet hat, oder die
  Schlussrechnung."; die Rechnungsseite zeigt den Grund statt "Finalisieren". 0 € und eine einzelne Position darunter bei positivem
  Betrag gehen.
- **Letzter Stand = zuletzt festgeschrieben** (Punkt 5): `Invoice.finalized_at` (naive UTC, Migration `3b8f1d6c9e24`), gesetzt beim
  Festschreiben (`_finalized_at()`: mindestens eine Mikrosekunde nach dem jüngsten des Auftrags -- unter der Sperre je Auftrag streng
  steigend, auch bei zurückgestellter Uhr); `get_previous_cumulative_ist()` ordnet danach, Rechnungen ohne Zeitpunkt (vor 1.8.83) wie
  bisher nach Datum und ID hinter jeder späteren. Vorher galt am selben Tag der Stand der zuletzt angelegten Rechnung.
- **1d** (Punkt 6, `create_storno_draft()`): das Storno eines pauschalen Abschlags ohne Position (vor 1.3.24) bekommt die
  Projektionsposition mit umgekehrtem Vorzeichen -- Gegenbetrag des Originals (-2.000 / -380 / -2.380 €), im PDF als Zeile; xfail 1d
  grün, Markierung entfernt.
- **Oberfläche**: Auftragsseite "+ Nachtrag" unter dem LV (derselbe Dialog als "Nachtrag anlegen", ohne Positionstyp und OZ),
  Nachträge mit Kennzeichen unter "Nachträge" hinter allen Titeln, im Dialog "Nachtrag entfernen" bzw. der Grund, warum nicht; nach der
  Schlussrechnung oder am stornierten Auftrag statt des Knopfs der Grund. Auftrags-PDF: Abschnitt "Nachträge" hinter allen Titeln.
  Rechnungsseite: "+ Position hinzufügen" nur bei Rechnung aus Aufwand, bei Abschlag nach Leistungsstand und Schlussrechnung der Hinweis
  auf den Nachtrag.
- Klicktest `scripts/klicktest_nachtrag.py`.

### Festlegungen 1.8.83 (Nr. 1–5 bestätigt am 12.10.2026, Vorgabe R4b; Nr. 6 geändert, siehe dort; Nr. 7–8 dort nicht genannt)

1. **Kennzeichen und Nummer**: `is_addendum` an der Auftragsposition, Nummer "N" + laufende Zahl je Auftrag (die höchste vergebene + 1,
   ein entfernter wird nicht neu vergeben, solange ein höherer steht), hinter allen anderen Positionen, ohne LV-Titel. In Rechnungen
   steht er als Position "N1" (die Nummer wird wie jede Positionsnummer kopiert); das Auftrags-PDF bekommt den Abschnitt "Nachträge".
2. **Wann ein Nachtrag geht**: jederzeit bis zur gültigen Schlussrechnung -- auch nach Vertrag, Abnahme oder "abgeschlossen" (ein
   Nachtrag nach Vertragsschluss ist der Normalfall) --, nicht am stornierten Auftrag. Nach dem Storno der Schlussrechnung wieder.
3. **Entfernen** nur eines Nachtrags ohne Anhänge, auch ohne Rechnungsentwurf; sonst bleibt er (Menge 0 oder "in Summe" aus, solange
   nicht abgerechnet). Mit Revision je Anlegen und Entfernen.
4. **Abgleich mit dem Angebot** gesperrt, solange Nachträge stehen -- er ersetzte alle Positionen und löschte sie.
5. **Freie Positionen**: nur in Rechnungen aus Aufwand; an Abschlag nach Leistungsstand, Schlussrechnung und Storno 409. Altbestand:
   Entwürfe mit freier Position werden beim Festschreiben abgelehnt (Position entfernen, Nachtrag anlegen, neu anlegen) -- nicht still
   umgewandelt. Ein bestehender Entwurf übernimmt einen später angelegten Nachtrag nicht von selbst.
6. **Negativer Abschlag**: maßgeblich der Rechnungsbetrag; 0 € ist nicht negativ, eine einzelne Position unter dem letzten Stand bei
   positivem Betrag geht. Geprüft beim Festschreiben, nicht beim Bearbeiten des Entwurfs (die Seite zeigt den Grund vorher). Nur Abschlag
   nach Leistungsstand -- der pauschale ist schon über 0 € Pflicht.
   **Geändert am 12.10.2026 (Vorgabe R4b):** ein Abschlag muss über 0 € liegen; 0 € wird wie negativ abgelehnt (umgesetzt mit R4b,
   siehe "Umsetzung R4b" unten).
7. **Zeitpunkt des Festschreibens** als neue Spalte (naive UTC wie alle gespeicherten Zeitpunkte), nicht die Rechnungsnummer (Format
   und Jahreswechsel). Bestehende Rechnungen bekommen keinen nachträglich. Bestehende Entwürfe werden nicht nachgerechnet (1b bleibt bis
   R4b offen).
8. **1d über eine Position** statt über einen Sonderfall in der Summe: das Storno zeigt wie jedes Storno eine Zeile mit umgekehrtem
   Vorzeichen, die Rundungsregel bleibt die des Originals.

### Tests und Prüfung

- Neu `tests/test_v386_nachtrag_und_abschlag.py` (25, davon 3 gegen PostgreSQL): Nachtrag mit Kennzeichen, Nummer N1/N2 (nach dem
  Entfernen die höchste + 1), hinter allen Positionen, Revisionen; folgende Abschläge und die Schlussrechnung übernehmen ihn,
  abgerechnet = Auftragssumme mit Nachtrag; kein Nachtrag nach der Schlussrechnung (nach ihrem Storno wieder) und am stornierten
  Auftrag; freie Position an Abschlag, Schlussrechnung und Storno 409, an Rechnung aus Aufwand weiter; Altbestand mit freier Position
  nicht festschreibbar; Projektionsposition des pauschalen Abschlags bleibt; Entfernen mit Rechnungsentwurf 409 mit Grund, Position aus
  dem Angebot 409, fremder Auftrag 404, ohne Anhang entfernt; Abgleich gesperrt; Auftrags-PDF mit "Nachträge" hinter dem Titel; Router.
  Negativer Abschlag 409 mit Weg (-595,00 €), 0 € und gemischte Positionen gehen, Router 409. Letzter Stand = zuletzt festgeschrieben,
  Vorschlag des nächsten Abschlags; Zeitpunkte steigen auch bei zurückgestellter Uhr; Altbestand ohne Zeitpunkt dahinter. 1d: Storno
  mit Zeile, -2.000/-380/-2.380 €, Abrechnungsstand zurück auf 0, Beträge in der festen Fassung; Storno des heutigen pauschalen
  Abschlags unverändert. **Gleichzeitig (PostgreSQL):** zwei Nachträge zugleich -> N1 und N2; ein Nachtrag wartet auf das
  Festschreiben der Schlussrechnung und wird abgelehnt; Entfernen wartet auf einen neuen Rechnungsentwurf und wird abgelehnt.
- Neu `tests/test_v386_nachtrag_migration.py` (2, davon 1 gegen PostgreSQL): Bestand bleibt, keine Position ist Nachtrag, keine
  Rechnung hat einen Zeitpunkt, Vorgabe "nein" für neue Zeilen, Rückweg exakt, mit Nachtrag bzw. Zeitpunkt verweigert. `alembic check`:
  keine Abweichung.
- `test_v372_befund_schlussrechnung`: xfail 1d entfernt -- grün, keine Prüfung geändert. **Erwartung geändert** (freie Positionen nur
  noch aus Aufwand): `test_v133` (`test_nachtrag_ohne_auftragsbezug_wird_voll_abgerechnet` heißt jetzt
  `test_freie_position_nur_in_rechnung_aus_aufwand_und_voll_abgerechnet`: an der Schlussrechnung 409, an der Rechnung aus Aufwand voll
  abgerechnet), `test_v230`/`test_v231` (weitere Positionen am Auftrag statt frei an der Rechnung), `test_v315` und `test_v378`
  ("Position neu" und Rundgang: die Position des Auftrags noch einmal), `test_v373_zugehoerigkeit` (freie Position an der
  Schlussrechnung 409 statt 200), `test_v373_zugehoerigkeit_struktur` (neue Route `DELETE /api/orders/{order_id}/items/{item_id}` in
  GEPRUEFT), `test_v325_quote_order_copy_fields` (`OrderItem.is_addendum` als eigenes Feld des Auftrags eingeordnet),
  `test_v381_zahlungen_migration` (der negative Abschlag, an dem die Migration ihre Bruttorechnung prüft, entsteht jetzt als
  Altbestand wie vor 1.8.83 -- die App schreibt ihn nicht mehr fest).
- Gegenproben (Regel 24): 16 von 16 rot -- freie Position überall, Altbestand festschreibbar, Nachtrag nach der Schlussrechnung,
  Nachtrag ohne Zeilensperre (PostgreSQL), ohne Kennzeichen, Entfernen trotz Anhang, Position aus dem Angebot entfernbar, Abgleich
  löscht Nachträge, Nachträge im PDF vorn, Router 404 statt 409; negativer Abschlag festschreibbar, auch 0 € abgelehnt; letzter Stand =
  zuletzt angelegt, Zeitpunkt nur von der Uhr, Zeitpunkt nicht gesetzt; Storno des alten Abschlags über 0 €. Jede Datei byte-genau
  zurück, kein Marker.
- Klicktest `klicktest_nachtrag.py` 13/13.
- Volle Suite (mit den opt-in-Tests gegen PostgreSQL, Arbeitskopie): 3733 grün, 2 rot, 6 erwartet fehlgeschlagen (1a, 1b) -- rot waren
  `test_v325_quote_order_copy_fields.py::test_every_field_is_classified` (das neue Feld nicht eingeordnet) und
  `test_v381_zahlungen_migration.py::test_the_migration_computes_the_same_gross_as_the_app` (schrieb einen negativen Abschlag fest),
  beide angepasst (siehe "Erwartung geändert"), die zwei Dateien danach 7 grün.
- Alle Klicktests (Regel 26, `scripts/klicktest_alle.py`, Arbeitskopie): 51 von 52 wie erwartet, Laufzeit gesamt 10:58 min. Rot:
  `klicktest_auswahl_inaktiv` (11/13 -- Sachbearbeiter und Projektleiter am Auftrag "Bisheriger Mitarbeiter (nicht mehr verfügbar)"
  statt "Erika Ehemalig (inaktiv)"). Ursache laut Server-Protokoll ein 500 bei `GET /api/employees` (Nebenbefund 4: zwei gleichzeitige
  Lesezugriffe legen dasselbe Mitarbeiterprofil an), nicht von 1.8.83; einzeln wiederholt 13/13. Die Erwartung des Klicktests ist
  richtig und bleibt.

### Nebenbefunde (nur gemeldet)

1. **Kein Weg, eine Auftragsposition in einen Entwurf zurückzuholen**: `add_invoice_item(source_order_item_id=…)` gibt es nur über die
   API; die Rechnungsseite kennt nur freie Positionen. Ein Entwurf, der vor einem Nachtrag angelegt wurde, bekommt ihn nur durch
   Löschen und neu Anlegen.
2. **Nachtrag ohne Kalkulation**: ein Nachtrag hat keinen Kalkulations-Schnappschuss -- Arbeitsvorbereitung und Plantafel sehen für ihn
   keine Planstunden und kein Material.
3. **Negativ-Prüfung nach dem Stand des Entwurfs**: der Betrag eines Abschlags wird beim Anlegen und Bearbeiten gerechnet, nicht beim
   Festschreiben (1b) -- zwei Abschläge als Entwürfe nebeneinander rechnen gegen denselben Stand; der zweite kann danach zu viel oder zu
   wenig abrechnen, ohne negativ zu sein.
4. **`GET /api/employees` schreibt -- und kollidiert mit sich selbst**: `ensure_employee_profiles()` (`app/employees.py`, aufgerufen
   von `GET /api/employees`, `/api/employees/caseworkers` u. a.) legt beim Lesen fehlende Mitarbeiterprofile an und committet. Die
   Auftragsseite ruft beide gleichzeitig ab; fehlt ein Profil, legen beide es an, der zweite scheitert an `employee_profiles.employee_id`
   (UNIQUE) mit 500 -- die Seite zeigt Sachbearbeiter und Projektleiter als "Bisheriger Mitarbeiter (nicht mehr verfügbar)". So im
   Gesamtlauf der Klicktests 1.8.83 bei `klicktest_auswahl_inaktiv` gesehen (Server-Protokoll des Laufs), einzeln nicht wieder. Ein
   Lesepfad, der schreibt (Regel 23), vom Rundgang in `test_v326` nicht ausgelöst, weil dessen Testdaten Profile haben.

## Umsetzung R4b: Schlussrechnung als Endrechnung (ab 1.8.84)

### Vorgabe vom 12.10.2026 (übernommen wie gegeben)

R4a geprüft. Festlegungen 1.8.82/83 Nr. 1–5 bestätigt. Nr. 6 geändert: Ein Abschlag muss über 0 € liegen; 0 € wird wie negativ
abgelehnt.

Vorweg:
1. Regel 23 als Muster: GET /api/employees legt Profile an (Ursache des roten Klicktests). Alle Stellen suchen und beheben, an denen ein
   Lesepfad etwas anlegt oder schreibt (get_or_create, „ensure“, Profile, Metadaten beim ersten Lesen). Strukturtest: Ein Beobachter an
   der Sitzung meldet jedes Schreiben während eines GET-Aufrufs, über alle GET-Endpunkte, auch mit fehlenden Profilen und ähnlichen
   Lücken in den Testdaten.

R4b Endrechnung (Entscheidungen Rechnungen im Archiv):
2. Schlussrechnung: alle Auftragspositionen einschließlich Nachträge mit Ist-Mengen (Vorschlag Ist = letzter Stand, im Entwurf
   änderbar), Gesamtleistung netto, USt, brutto. Darunter Abzugsblock: jede festgeschriebene, nicht stornierte Abschlagsrechnung und
   Rechnung aus Aufwand mit Nummer, Datum, Netto, USt, Brutto. Rechnungsbetrag = Gesamtleistung − Abzüge; das ist der Betrag der
   Rechnung für Zahlungen, offene Posten und „abgerechnet“.
3. Beim Festschreiben wird alles unter der Sperre neu gerechnet (1b). Weichen Preise oder Steuerschlüssel eines Entwurfs vom Auftrag
   ab: 409 mit Hinweis zum Aktualisieren, für jede Rechnungsart (Nebenbefunde 1 und 2). Hat ein abgezogener Abschlag einen anderen
   Steuersatz: Hinweis.
4. Zahlungshinweis „Stand <Tag des Festschreibens>“: je Abschlag mit offenem Betrag, einschließlich Einbehalt, „zzgl. noch offen aus
   Abschlag Nr. …“, darunter der Zahlbetrag. Die Mahnfähigkeit nach der Schlussrechnung regelt R4c.
5. Die Sperre der Schlussrechnung nach pauschalen Abschlägen entfällt. Nach der gültigen Schlussrechnung keine Rechnung aus Aufwand mehr
   im selben Auftrag.
6. Schnellauftrag: Eine Rechnung aus Aufwand kann als abschließend gekennzeichnet werden und zählt dann als „vollständig abgerechnet“;
   keine Schlussrechnung über 0 €.

xfail 1a und 1b müssen grün werden, Markierung dann entfernen. Ein negativer Rechnungsbetrag wird bis R4c mit 409 abgelehnt.
Angriffstests mit Gegenprobe, Gleichzeitigkeit gegen PostgreSQL. Eigene Festlegungen mit „Bitte bestätigen“. Nebenbefunde nur melden.
Wird der Umfang zu groß: nach Punkt 3 committen und den Rest auflisten. Commit nach Regel 13, Bericht kurz.

### Vorweg

- Festlegungen 1.8.82 und 1.8.83 Nr. 1–5 an den Überschriften als bestätigt markiert, 1.8.83 Nr. 6 mit der Änderung. Die Vorgabe nennt
  1.8.82 Nr. 6–9 und 1.8.83 Nr. 7–8 nicht -- dort steht das so, ohne Bestätigung.
- Punkt 1 (kein Lesepfad legt an) ist Version 1.8.84: `docs/archiv/grunddaten-beim-start.md`, "Umsetzung 1.8.84".
- Umfang: nach Punkt 3 committet (1.8.85, mit Punkt 5 -- die Sperre neben dem pauschalen Abschlag hängt an der Endrechnung, der
  Aufwand nach der Schlussrechnung an ihrem Abzug); Punkte 4 und 6 als 1.8.86 -- R4b damit vollständig.

### Umsetzung 1.8.85: Endrechnung, Neuberechnung beim Festschreiben, Abweichung vom Auftrag (Punkte 2, 3 und 5)

#### Was gebaut ist

- **Endrechnung** (`app/invoices.py::final_breakdown()`, `FinalBreakdown`): die Schlussrechnung trägt alle Auftragspositionen samt
  Nachträgen mit der vollen Ist-Menge (abgerechnete Menge = Ist, `compute_billed_quantity_and_total(invoice_type="schluss")`),
  Vorschlag beim Anlegen die Menge des Auftrags (`_proposed_ist()`, Festlegung 1). Gesamtleistung = Positionen + jede Rechnung aus
  Aufwand (eigene Zeile "Leistungen nach Aufwand, Rechnung … vom …"), USt einmal auf die Gesamtleistung; darunter der Abzugsblock:
  jede festgeschriebene, nicht stornierte Abschlagsrechnung (pauschal, nach Leistungsstand) und Rechnung aus Aufwand desselben
  Auftrags mit Nummer, Datum, Netto, USt, Brutto, älteste zuerst (`deductible_invoices()`). Rechnungsbetrag = Gesamtleistung −
  Abzüge, netto, USt und brutto je als Differenz -- `compute_invoice_totals()` liefert ihn, also Zahlungen (`payable_gross()`),
  offene Posten, Skonto, Mahnung, `{gesamtbetrag}` und "abgerechnet" (`compute_order_billing_progress()`, Summe der gültigen
  Rechnungsbeträge = Gesamtleistung).
- **Abzüge eingefroren**: im Entwurf zählen die gerade gültigen Rechnungen; beim Festschreiben unter der Sperre der Auftragszeile
  entstehen die Zeilen `InvoiceDeduction` (neue Tabelle `invoice_deductions`, Migration `8c2e5a7d4f19`, UNIQUE je Schlussrechnung und
  abgezogener Rechnung, ORM-Sperre: nie geändert, nie gelöscht). Beträge stehen dort nicht -- sie kommen aus der abgezogenen Rechnung,
  die selbst unveränderlich ist (Regel 19). Das Storno einer Endrechnung lautet auf den Gegenbetrag (ihre Positionen negiert, die
  Abzüge des Originals mit umgekehrtem Vorzeichen); ihr Betrag und der des Stornos bleiben, auch wenn danach ein Abschlag storniert
  wird.
- **PDF** (`app/invoice_pdf.py::_final_invoice_blocks()`): zwischen Positionstabelle und Schlussblock "Summe der Positionen" und je
  Rechnung aus Aufwand eine Zeile (nur wenn es sie gibt), Gesamtleistung netto/MwSt./brutto, "Abzüglich bereits gestellter
  Rechnungen" (Rechnung, Datum, Art -- bei anderem Steuersatz mit dem Satz --, netto, USt, brutto, Summe), Rechnungsbetrag
  netto/MwSt./brutto. Ohne Abzüge wie bisher.
- **Rechnungsseite**: Karte "Endrechnung" mit derselben Aufstellung (Links auf die abgezogenen Rechnungen), Hinweis bei anderem
  Steuersatz; oben Netto/MwSt./Brutto = Rechnungsbetrag.
- **Neu rechnen beim Festschreiben** (Befund 1b; `_recompute_draft()`): unter der Sperre, vor den Prüfungen -- Abschlag nach
  Leistungsstand gegen den letzten Stand von jetzt, Schlussrechnung mit der vollen Ist-Menge. Danach ziehen im selben Commit die
  anderen Entwürfe eines Abschlags nach Leistungsstand desselben Auftrags nach (`_refresh_other_drafts()`), auch nach einem Storno.
- **Abweichung vom Auftrag** (`order_deviations()`, `order_deviation_reason()`, Teil von `finalize_block_reason()`): jede Art außer
  Storno -- Steuerschlüssel bzw. Satz, Einheitspreis und Einheit einer Position mit Auftragsbezug, eine Position, die nicht mehr in
  der Summe des Auftrags steht, bei der Schlussrechnung fehlende Positionen des Auftrags (z. B. ein späterer Nachtrag). 409 mit
  "Der Entwurf weicht vom Auftrag ab: … „Aus dem Auftrag aktualisieren“ übernimmt …". Im Entwurf lassen sich Preis und Einheit einer
  Position mit Auftragsbezug (`update_invoice_item()`, `add_invoice_item()`) und der Steuerschlüssel (`update_invoice_tax_key()`)
  nicht mehr abweichend setzen (409, nur eine tatsächliche Änderung) -- Befund R4 Nebenbefunde 1 und 2 aus 1.8.82; beim Storno nur
  der Schlüssel des Originals.
- **"Aus dem Auftrag aktualisieren"** (`refresh_draft_from_order()`, `POST /api/invoices/{id}/refresh-from-order`): übernimmt
  Steuerschlüssel, Satz und Hinweistext, Einheitspreise und Einheiten; Positionen außerhalb der Summe gehen heraus, beim Abschlag nach
  Leistungsstand und der Schlussrechnung kommen fehlende Positionen mit dem Ist-Vorschlag dazu (auch spätere Nachträge -- löst
  Nebenbefund 1 aus 1.8.83); Ist-Mengen und Texte bleiben. Rechnungsseite: Knopf neben dem Grund; Steuerschlüssel gesperrt mit
  Hinweis, Preis und Einheit einer Position mit Auftragsbezug im Dialog gesperrt.
- **Beträge** (`amount_block_reason()`, ersetzt `negative_progress_reason()`): Abschlag nach Leistungsstand unter 0 € wie bisher, über
  0 € neu abgelehnt (Festlegung 1.8.83 Nr. 6 geändert), pauschaler Abschlag (gerundet) über 0 € oder weniger abgelehnt;
  Schlussrechnung unter 0 € (Abzüge über der Gesamtleistung) 409 bis R4c, über 0 € geht (Endrechnung nach voller Abdeckung).
- **Punkt 5**: die Sperre der Schlussrechnung neben einem pauschalen Abschlag (`_lump_sum_reason()`, seit 1.8.72) entfällt. Nach der
  gültigen Schlussrechnung keine Rechnung aus Aufwand mehr -- weder anlegen noch einen älteren Entwurf festschreiben -- und kein
  Storno einer abgezogenen Rechnung aus Aufwand (wie beim Abschlag); nach dem Storno der Schlussrechnung wieder. Auftragsseite: Grund
  auch für "Rechnung aus Aufwand" (`invoice_create_blocks["aufwand"]`).
- Klicktest `scripts/klicktest_endrechnung.py`.

#### Festlegungen 1.8.85 (Nr. 1–11 bestätigt am 13.10.2026, Nr. 1 mit Ergänzung, Vorgabe R4c)

1. **Vorschlag Ist der Schlussrechnung = Menge des Auftrags** (der letzte Stand des Auftrags, dessen Mengen bis zur Schlussrechnung
   änderbar bleiben), im Entwurf änderbar. Gelesen wurde "letzter Stand" damit nicht wie beim Abschlag (Ist der zuletzt
   festgeschriebenen Rechnung): eine Schlussrechnung ohne vorherigen Abschlag nach Leistungsstand schlüge sonst überall 0 vor, und die
   Abnahmetests 1a und 1b setzen "Aufmaß wie beauftragt" voraus (sie legen die Schlussrechnung an und schreiben sie fest, ohne ein Ist
   einzutragen). War der Stand der Abschläge gemeint: eine Zeile (`_proposed_ist()`), die Tests 1a/1b trügen dann ihr Ist ein.
2. **Gesamtleistung** = Positionen (volle Ist-Menge) + Rechnungen aus Aufwand (netto, je eine Zeile), USt einmal auf die
   Gesamtleistung gerundet; jeder Abzug mit seiner eigenen USt; Rechnungsbetrag netto, USt, brutto je als Differenz -- er geht auf den
   Cent auf, die USt des Rechnungsbetrags kann von "19 % des Rechnungsbetrags netto" um Cent abweichen (Befund R4 g).
3. **Abzüge**: jede festgeschriebene, nicht stornierte Abschlagsrechnung und Rechnung aus Aufwand des Auftrags, älteste zuerst (nach
   dem Zeitpunkt des Festschreibens, Altbestand davor) -- auch eine aus dem Altbestand über 0 € oder darunter. Im Entwurf die gerade
   gültigen, beim Festschreiben eingefroren; ohne Beträge in der eigenen Tabelle.
4. **Altbestand**: eine Schlussrechnung von vor 1.8.85 behält ihren Betrag (Rest über die Menge, keine Abzüge). Ein Entwurf von vor
   1.8.85 rechnet ab sofort als Endrechnung (volle Ist-Menge statt des gespeicherten Rests); keine Migration der Daten.
5. **Storno der Endrechnung**: Gegenbetrag samt umgekehrter Abzüge; ihr PDF zeigt dieselbe Aufstellung mit umgekehrtem Vorzeichen.
6. **Abweichung**: geprüft werden Steuerschlüssel/Satz, Einheitspreis, Einheit, "in Summe" und bei der Schlussrechnung die
   Vollständigkeit -- nicht Mengen (das Ist ist Sache der Rechnung) und nicht Texte. Ein Entwurf übernimmt Preis, Einheit und
   Steuerschlüssel nur aus dem Auftrag (im Entwurf 409 bei Abweichung), der Storno den Schlüssel des Originals.
7. **Aktualisieren** übernimmt auch fehlende Positionen beim Abschlag nach Leistungsstand (nicht nur bei der Schlussrechnung), ohne
   Rückfrage; Texte, die im Entwurf geändert wurden, bleiben.
8. **Nachziehen anderer Entwürfe**: nur Abschläge nach Leistungsstand (ihre abgerechnete Menge hängt am letzten Stand); die
   Schlussrechnung im Entwurf rechnet ihre Abzüge ohnehin beim Lesen.
9. **Beträge**: 0 € gilt für jeden Abschlag als abgelehnt (pauschal: der auf den Cent gerundete Betrag); eine Schlussrechnung über 0 €
   ist erlaubt (Endrechnung, wenn die Abschläge die Gesamtleistung decken) -- ausgenommen beim Schnellauftrag (Punkt 6, 1.8.86);
   unter 0 € 409 bis R4c, der Grund nennt Ist-Mengen und Storno als Ausweg.
10. **Anderer Steuersatz eines Abzugs**: Hinweis auf der Rechnungsseite, im PDF der Satz in der Spalte "Art"; kein Sperrgrund.
11. **Nach der gültigen Schlussrechnung** gilt für Rechnungen aus Aufwand dasselbe wie für Abschläge: kein neues Anlegen, kein
    Festschreiben eines älteren Entwurfs, kein Storno (sie ist abgezogen).

#### Tests und Prüfung

- Neu `tests/test_v388_endrechnung.py` (28, davon 5 gegen PostgreSQL): Gesamtleistung mit Aufwand, Abzüge in Reihenfolge (Entwurf und
  stornierte zählen nicht), Rechnungsbetrag für Zahlungen und "abgerechnet"; Nachtrag und eingetragenes Ist; ohne Abzüge die
  Gesamtleistung; eingefrorene Abzüge nach Storno von Schlussrechnung und Abschlag, Storno mit Gegenbetrag; ORM-Sperre (ändern,
  löschen, leeren); anderer Steuersatz mit Hinweis; PDF; andere Entwürfe ziehen nach; Preisänderung am Auftrag sperrt Abschlag und
  Schlussrechnung bis zum Aktualisieren; Steueränderung sperrt jede Art; Aktualisieren ergänzt einen Nachtrag und nimmt eine Position
  außerhalb der Summe heraus; Preis/Einheit und Steuerschlüssel im Entwurf nur aus dem Auftrag, Storno mit dem des Originals; Router
  (409, Aktualisieren, kein Entwurf mehr 409); Abschlag über 0 € und negativ abgelehnt; Schlussrechnung negativ 409, über 0 € erlaubt;
  Schlussrechnung neben pauschalem Abschlag; kein Aufwand nach der Schlussrechnung (anlegen, Entwurf, Storno), nach ihrem Storno
  wieder; Auftragsseite. **Gleichzeitig (PostgreSQL, Commit der ersten Aktion eine Sekunde angehalten):** zwei Abschläge -> der zweite
  rechnet gegen den ersten; Schlussrechnung wartet auf einen Abschlag und zieht ihn ab; Abschlag wartet auf die Schlussrechnung und
  wird abgelehnt; Storno vor der Schlussrechnung -> nicht abgezogen; Preisänderung am Auftrag vor dem Festschreiben -> 409 mit
  Abweichung.
- Neu `tests/test_v388_endrechnung_migration.py` (2, davon 1 gegen PostgreSQL): Bestand mit alter Schlussrechnung bleibt, keine Abzüge,
  Rückweg exakt, mit Abzug verweigert. `alembic check` auf einer Wegwerf-SQLite: keine Abweichung.
- `test_v372_befund_schlussrechnung`: xfail 1a und 1b entfernt -- grün, keine Prüfung geändert; der "heutige" Test beschreibt jetzt
  die Endrechnung (derselbe Rechnungsbetrag 3.570 €). **Erwartung geändert**: `test_v133` (Schlussrechnung nach zwei Abschlägen:
  volle Menge, Rechnungsbetrag der Rest; Preisänderung nur an freier Position), `test_v144` (Steuerschlüssel über den Auftrag),
  `test_v315` (Position mit Einheit des Auftrags), `test_v375` (Sperre neben pauschalem Abschlag entfallen, kein Aufwand nach der
  Schlussrechnung, Gründe der Auftragsseite mit "aufwand", PostgreSQL: Schlussrechnung entsteht nach dem Warten), `test_v378`
  (Steuerschlüssel über den Auftrag, Position mit Einheit und Preis des Auftrags, Szenario für "Aus dem Auftrag aktualisieren", zweite
  Änderung über den Text statt den Preis, Aufwand neben einem Abschlag statt nach der Schlussrechnung), `test_v381_zahlungen_migration`
  (Altbestand mit anderem Preis: Abweichungsprüfung ausgesetzt wie die Betragsprüfung), `test_v386` (Nachtrag in der Schlussrechnung
  mit voller Menge, Abschlag über 0 € abgelehnt, letzter Stand mit dem höheren Stand zuletzt festgeschrieben).
- Gegenproben (Regel 24): 17 von 17 rot -- Abzüge nicht eingefroren, pauschaler Abschlag nicht abgezogen, Aufwand nicht in der
  Gesamtleistung, keine Neuberechnung, andere Entwürfe ziehen nicht nach, Abweichung bzw. fehlende Positionen nicht geprüft,
  Aktualisieren ohne Nachtrag, Preis bzw. Steuerschlüssel im Entwurf frei, Abschlag über 0 € bzw. negative Schlussrechnung geht durch,
  Aufwand bzw. sein Storno nach der Schlussrechnung, ORM-Sperre aus, PDF ohne Abzugsblock, Festschreiben ohne Zeilensperre
  (PostgreSQL). Jede Datei byte-genau zurück, kein Marker.
- Klicktest `klicktest_endrechnung.py` 14/14 (Karte Endrechnung mit Gesamtleistung samt Aufwand, drei Abzügen, Rechnungsbetrag = oben
  Brutto; Steuerschlüssel und Preis/Einheit gesperrt; finalisieren, PDF aus der Ablage; Grund für Aufwand auf der Auftragsseite;
  Abweichung mit Grund und "Aus dem Auftrag aktualisieren"; hell, dunkel, 412 px).
- Volle Suite (mit den opt-in-Tests gegen PostgreSQL, Arbeitskopie, drei Teile parallel): 3780 grün, 0 rot, keine erwarteten Fehlschläge mehr. Danach die Reihenfolge der Gründe beim Finalisieren korrigiert (Abweichung, Betrag, erst dann der Leistungszeitraum -- wie bis 1.8.84 der negative Abschlag vor dem Zeitraum; im ersten Gesamtlauf nannte `klicktest_nachtrag` den Zeitraum zuerst) und alle rechnungsnahen Testdateien auf dem Endstand nachlaufen lassen: 1870 grün.
- Alle Klicktests (Regel 26, `scripts/klicktest_alle.py`, Arbeitskopie): 50 von 53 wie erwartet, Laufzeit gesamt 13:15 min. Rot: `klicktest_mahnwesen` 28/29 (Nebenbefund 2 aus 1.8.84, seit etwa 23 Uhr auch einzeln und auf 1.8.83 jedes Mal rot -- nicht von dieser Version); `klicktest_nachtrag` 12/13 (Reihenfolge der Gründe, korrigiert, danach 13/13); `klicktest_rechnungen_sperren` 19/24 -- **Erwartung veraltet seit 1.8.85**: er prüfte die Sperre der Schlussrechnung neben einem pauschalen Abschlag (Grund, Ausweg R4 bzw. Entwurf löschen, API 409), die mit R4b Punkt 5 entfällt; angepasst (frei, Knopf da, API 200), danach 22/22. `klicktest_endrechnung` 14/14.

#### Nebenbefunde (nur gemeldet)

1. **Rechnungsseite breiter als das Fenster**: bei 1280 px ragen die Spalte "Betrag" der Positionen und die rechte Spalte über den
   Rand (waagerechte Bildlaufleiste) -- schon vor 1.8.85 so (Screenshot des Klicktests `klicktest_nachtrag` aus 1.8.84).
2. **Der Abzug ändert das Mahnen noch nicht**: nach der Endrechnung lassen sich Abschläge weiter einzeln mahnen, und die Endrechnung
   mahnt nur ihren Rechnungsbetrag -- die Vorgabe verweist das auf R4c.
3. **Entwurf der Schlussrechnung in Listen**: jede Berechnung ihres Betrags fragt die Rechnungen des Auftrags ab (Abzüge im Entwurf
   live) -- in Finanzen und Projektmappe je Entwurf einer Schlussrechnung eine Abfrage mehr.
4. **"Rechnung aus Aufwand" auf der Auftragsseite** erscheint in der Auswahl nur mit gebuchten Zeiten oder Material eines
   unterschriebenen Berichts (`renderInvoiceTypeOptions()`); der Grund aus `invoice_create_blocks["aufwand"]` zeigt sich deshalb nur,
   wo die Auswahl ihn anbietet.
5. **Testhelfer `_run` (`tests/test_v375_rechnungen_sperren.py`) schließt die Sitzung der zweiten Aktion nicht**: wirft sie (wie
   erwartet) nach der Sperre, bleibt ihre Transaktion offen und hält die Sperre der Auftragszeile. Trifft die erste Aktion danach noch
   darauf, wartet sie ewig -- so hing `test_v383_nebenforderungen_pg.py::test_pg_client_change_waits_for_ordering_and_asks_for_a_reason`
   einmal im Nachlauf 1.8.85 (Beauftragen: Revision anlegen nach dem Kundenwechsel, der die Auftragszeile sperrte), während parallel ein
   zweiter Testlauf gegen dieselbe PostgreSQL lief; in allen vollen Läufen grün. Kein Fehler der App (der Router rollt eine abgelehnte
   Anfrage zurück). Im selben parallelen Lauf brach in `test_v382_mahnwesen_pg.py` einmal die Verbindung ab ("server closed the
   connection unexpectedly"), einzeln grün.

### Umsetzung 1.8.86: Zahlungshinweis, abschließende Rechnung aus Aufwand (Punkte 4 und 6)

#### Was gebaut ist

- **Zahlungshinweis** (`app/invoices.py::payment_note()`): jede Endrechnung (Schlussrechnung mit Abzügen) nennt "Zahlungshinweis (Stand
  <Tag>)" -- Rechnungsbetrag brutto, je abgezogener Rechnung mit offenem Betrag "zzgl. noch offen aus Abschlag Nr. …" (bei einer
  Rechnung aus Aufwand "aus Rechnung Nr. …"), offen = Brutto − Zahlungen − Skonto einschließlich Einbehalt ("davon Einbehalt …"),
  darunter der Zahlbetrag = Rechnungsbetrag + noch Offenes. Im Entwurf der Stand von heute aus dem Zahlstand
  (`app/payments.py::payment_states()`); beim Festschreiben unter der Sperre der Auftragszeile -- unter der auch Zahlungen buchen --
  an den Abzügen eingefroren (`InvoiceDeduction.open_amount`, `.retained_open`, Migration `4e7a9c2b6d58`), Stand = Rechnungsdatum (Tag
  des Festschreibens). Danach gebuchte Zahlungen ändern den Hinweis nicht. PDF (`_payment_note_blocks()`, unter dem
  Rechnungsbetrag) und Rechnungsseite (Karte "Endrechnung"). Der Betrag der Rechnung -- für Zahlungen, offene Posten, Skonto, Mahnung
  -- bleibt der Rechnungsbetrag.
- **Abschließende Rechnung aus Aufwand** (`Invoice.closes_order`, gleiche Migration): an einem **Auftrag nach Aufwand** (Auftragssumme
  0 €, `effort_only()` -- Schnellauftrag, Wartung aus dem Vertrag, Auftrag aus einem Befund: "… nach Aufwand", 1 × 0 €) lässt sich
  eine Rechnung aus Aufwand im Entwurf als abschließend kennzeichnen (Rechnungsseite: Häkchen "Abschließende Rechnung",
  `PUT /api/invoices/{id}` mit `closes_order`; `closing_block_reason()`: nur Aufwand, nur Auftrag nach Aufwand, keine gültige
  Schlussrechnung, keine andere abschließende -- geprüft beim Setzen und beim Festschreiben, unter der Sperre). Festgeschrieben gilt
  der Auftrag als vollständig abgerechnet (`closing_invoices()`: `invoice_summary_for_order()`, Projektmappe, Auftragslisten) und wie
  nach einer Schlussrechnung: keine weitere Rechnung (Abschlag, Aufwand, Schlussrechnung), Auftrag gesperrt (`order_locks.py`:
  Positionen, Titel, Steuer; Nachtrag; Abgleich mit dem Angebot), kein Storno einer anderen Rechnung des Auftrags -- Ausweg: das Storno
  der abschließenden.
- **Keine Schlussrechnung über 0 €** am Auftrag nach Aufwand: Anlegen und Festschreiben 409 (`ZERO_FINAL_TEXT`, mit dem Weg über
  "abschließend"); ein Entwurf von einem Auftrag, der damals Preise hatte, wird beim Festschreiben abgelehnt.
- Klicktest `scripts/klicktest_endrechnung.py` um Zahlungshinweis und "abschließend" erweitert.

#### Festlegungen 1.8.86 (Nr. 1–8 bestätigt am 13.10.2026, Vorgabe R4c)

1. **Zahlungshinweis an jeder Endrechnung**, auch wenn nichts mehr offen ist (dann Zahlbetrag = Rechnungsbetrag); je abgezogener
   Rechnung mit offenem Betrag -- auch Rechnungen aus Aufwand ("aus Rechnung Nr. …"). Offen ohne Nebenforderungen (Mahngebühr,
   Pauschale, Zinsen), mit Einbehalt (genannt als "davon Einbehalt").
2. **Stand**: im Entwurf heute, festgeschrieben der Tag des Festschreibens (eingefroren, wie die feste Fassung des PDFs); keine
   Aktualisierung danach.
3. **Der Zahlbetrag ist ein Hinweis**: der Betrag der Rechnung bleibt der Rechnungsbetrag (Zahlungen, offene Posten, Skonto, Mahnung,
   Mail `{gesamtbetrag}`); wie nach der Endrechnung gemahnt wird, regelt R4c.
4. **Kein Zahlungshinweis** am Storno einer Endrechnung und an Abzügen aus 1.8.85 ohne eingefrorenen Stand.
5. **Auftrag nach Aufwand** = Auftragssumme 0 € (Positionen in der Summe, je Position gerundet) -- kein eigenes Kennzeichen am Auftrag.
   Ein Nachtrag mit Preis macht ihn zum Auftrag mit Preisen; eine schon gekennzeichnete Rechnung lässt sich dann nicht als abschließende
   festschreiben (Kennzeichen entfernen geht immer).
6. **Höchstens eine gültige abschließende Rechnung** je Auftrag; danach gilt alles, was nach einer Schlussrechnung gilt, auch die
   Sperre der Storni anderer Rechnungen des Auftrags.
7. **PDF der abschließenden Rechnung unverändert** ("Rechnung nach Aufwand") -- das Kennzeichen wirkt nur im Ablauf.
8. **Keine Schlussrechnung am Auftrag nach Aufwand** -- weder anlegen noch festschreiben, auch nicht über 0 € nach einem pauschalen
   Abschlag (dort lautete sie ohnehin negativ).

#### Tests und Prüfung

- Neu `tests/test_v389_zahlungshinweis_abschliessend.py` (12, davon 3 gegen PostgreSQL): Zahlungshinweis mit Einbehalt und Aufwand, Stand
  heute, eingefroren beim Festschreiben, spätere Zahlung ändert ihn nicht, PDF; ohne Offenes und nicht am Storno; Abzüge ohne Stand ohne
  Hinweis; abschließende Rechnung: vollständig abgerechnet, alle Sperren, Storno öffnet wieder; keine Schlussrechnung über 0 € (anlegen,
  Entwurf von früher); nur Aufwand am Auftrag nach Aufwand; Nachtrag mit Preis sperrt das Festschreiben, nur eine abschließende; Router.
  **Gleichzeitig (PostgreSQL):** Zahlung wartet auf das Festschreiben -> Stand davor; Festschreiben wartet auf die Zahlung -> Stand
  danach; zwei abschließende gleichzeitig -> eine.
- Neu `tests/test_v389_zahlungshinweis_migration.py` (2, davon 1 gegen PostgreSQL). `alembic check`: keine Abweichung.
- **Erwartung geändert**: `test_v385_auftrag_sperren` -- der Abgleich mit dem Angebot ist nach einer abschließenden Rechnung aus Aufwand
  gesperrt (vorher: nach einer Schlussrechnung ohne Positionen, die es am Auftrag mit Auftragssumme 0 € nicht mehr gibt).
- **Fund beim Test**: `Invoice.closes_order` hat nur die Vorgabe der Datenbank, keine in Python -- mit einer Python-Vorgabe schrieben
  die Migrationsproben älterer Stände (`test_v380`, `test_v381_zahlungen_migration`, `test_v382_mahnwesen_migration`, Core-Insert mit der
  heutigen Tabelle) die Spalte in Tabellen, die sie noch nicht haben (6 rot, behoben).
- Gegenproben (Regel 24): 12 von 12 rot -- Hinweis nicht eingefroren bzw. nach dem Festschreiben live, Einbehalt nicht im offenen
  Betrag, PDF ohne Hinweis; abschließend zählt nicht, auch am Auftrag mit Preisen, Schlussrechnung über 0 € am Auftrag nach Aufwand,
  danach weitere Rechnungen, Auftrag nicht gesperrt, zwei abschließende, Storno daneben, Kennzeichen ohne Prüfung. Jede Datei byte-genau
  zurück, kein Marker.
- Klicktest `klicktest_endrechnung.py` 22/22 (dazu: Zahlungshinweis mit drei offenen, einer mit Einbehalt, Zahlbetrag; nach dem
  Finalisieren derselbe Stand; Häkchen "abschließend" am Auftrag mit Preisen gesperrt mit Grund, am Auftrag nach Aufwand gesetzt,
  finalisiert mit Hinweis, Auftrag vollständig abgerechnet, Schlussrechnung dort mit Grund).
- Volle Suite (mit den opt-in-Tests gegen PostgreSQL, Arbeitskopie, drei Teile parallel): 3794 grün, 0 rot, keine erwarteten Fehlschläge.
- Alle Klicktests (Regel 26, `scripts/klicktest_alle.py`, Arbeitskopie): 51 von 53 wie erwartet, Laufzeit gesamt 13:13 min (`klicktest_endrechnung` 22/22, alle übrigen Rechnungs-Klicktests grün). Rot: `klicktest_mahnwesen` 28/29 (vorhandener Fehler des Klicktests, Nebenbefund 2 aus 1.8.84, auch auf 1.8.83) und `klicktest_teil_updates` 8/9 ("/time-tracking: Seite nicht bereit", Buchung ändern: Notiz unverändert) -- gelaufen um 00:11 Uhr; um 00:22 auf 1.8.83 (`e3ae7f9`) genauso rot. Ursache ist der bekannte offene Punkt "Kalenderdatum im Browser noch an weiteren Stellen aus UTC abgeleitet" (CLAUDE.md): `today()` der Büro-Zeiterfassung nimmt zwischen 0 und 2 Uhr den Vortag -- nicht von dieser Version.

#### Nebenbefunde (nur gemeldet)

1. **Die Rechnungs-Mail nennt den Zahlbetrag nicht**: `{gesamtbetrag}` ist der Rechnungsbetrag; den Zahlungshinweis trägt nur das PDF.
2. **Skonto und Zahlbetrag**: der Zahlungssatz bietet Skonto auf den Rechnungsbetrag an; der Zahlbetrag enthält offene Abschläge, deren
   eigene Skontofrist längst vorbei sein kann -- der Satz unterscheidet das nicht.
3. **"Rechnung aus Aufwand" am Schnellauftrag** erscheint auf der Auftragsseite erst mit gebuchten Zeiten oder Material eines
   unterschriebenen Berichts (Nebenbefund 4 aus 1.8.85) -- dort auch das Häkchen erst nach dem Anlegen auf der Rechnungsseite.

## Umsetzung R4c: Mahnen nach der Endrechnung, Überzahlung (ab 1.8.87)

### Vorgabe vom 13.10.2026 (übernommen wie gegeben)

R4b geprüft. Festlegungen bestätigt, Nr. 1 mit Ergänzung: Der Entwurf der Schlussrechnung zeigt je Position Auftragsmenge, zuletzt
abgerechnete Menge und Ist nebeneinander und markiert Abweichungen. Die Festlegungen 1.8.82 Nr. 6–9 und 1.8.83 Nr. 7–8 bitte je in
einer Zeile vorlegen.

Vorweg:
1. Datum im Browser: Alle Stellen, die das heutige Datum aus UTC bilden (toISOString und Ähnliches), auf das Berliner Datum umstellen;
   Strukturtest über Vorlagen und JavaScript. Anlass: klicktest_teil_updates um Mitternacht.
2. klicktest_mahnwesen wartet auf das Neuladen der Liste. Der Testhelfer _run schließt die Sitzung der zweiten Aktion.

R4c (Entscheidungen Rechnungen im Archiv):
3. Nach der gültigen Schlussrechnung stehen abgezogene Rechnungen nicht mehr einzeln in „zur Mahnung fällig“ und lassen sich nicht
   einzeln mahnen; offene Mahnungsentwürfe zu ihnen gelten als überholt.
4. Einbehalte auf abgezogene Rechnungen werden mit der gültigen Schlussrechnung fällig.
5. Mahnung der Schlussrechnung über den Zahlbetrag: mahnfähiger Betrag der Schlussrechnung plus offene Beträge der abgezogenen
   Rechnungen, in der Aufstellung je Rechnung mit Nummer.
6. Überzahlung: Ein negativer Rechnungsbetrag wird zulässig. Ist der Zahlbetrag negativ, weist das PDF einen Erstattungsbetrag aus, ohne
   Skonto und ohne „zahlbar“. Die Erstattung ist als Zahlungsausgang buchbar, ein Guthaben steht am Kunden. Skonto nur bei positivem
   Rechnungsbetrag.
7. Die E-Mail zur Schlussrechnung nennt den Zahlbetrag bzw. den Erstattungsbetrag.

Angriffstests mit Gegenprobe, Gleichzeitigkeit gegen PostgreSQL. Eigene Festlegungen mit „Bitte bestätigen“. Nebenbefunde nur melden.
Wird der Umfang zu groß: nach Punkt 5 committen und den Rest auflisten. Commit nach Regel 13, Bericht kurz.

### Vorweg

- Festlegungen 1.8.85 Nr. 1–11 und 1.8.86 Nr. 1–8 an den Überschriften als bestätigt markiert, 1.8.85 Nr. 1 mit der Ergänzung
  (gebaut als 1.8.88, siehe unten).
- **Zur Bestätigung vorgelegt, je eine Zeile** (Wortlaut oben unter "Umsetzung 1.8.82" bzw. "Umsetzung 1.8.83"):
  - 1.8.82 Nr. 6: Steuersatz = Steuerschlüssel (Satz und Hinweistext), gesperrt, solange eine gültige Rechnung besteht; sind alle
    storniert, wieder frei.
  - 1.8.82 Nr. 7: Nach der Schlussrechnung gesperrt sind Positionen, LV-Titel, Steuerschlüssel und Abgleich, nicht die Kopfdaten des
    Auftrags; nach ihrem Storno wieder offen, Preise schon abgerechneter Positionen bleiben gesperrt.
  - 1.8.82 Nr. 8: Abgelehnt wird nur eine tatsächliche Änderung; unverändert gespeicherte Werte (auch „50.000“ statt „50“) gehen durch.
  - 1.8.82 Nr. 9: Der Abgleich mit dem Angebot ist zusätzlich gesperrt nach gültiger Schlussrechnung und, solange eine gültige
    Rechnung besteht, bei anderem Steuerschlüssel des Angebots.
  - 1.8.83 Nr. 7: Der Zeitpunkt des Festschreibens ist eine eigene Spalte (naive UTC), nicht aus der Rechnungsnummer abgeleitet;
    Bestand ohne Zeitpunkt, Entwürfe nicht nachgerechnet.
  - 1.8.83 Nr. 8: 1d über eine Position: das Storno eines pauschalen Abschlags ohne Position zeigt eine Zeile mit umgekehrtem
    Vorzeichen, mit der Rundungsregel des Originals.

### Umsetzung 1.8.87: "heute" im Browser aus Berlin, Klicktest Mahnwesen, Testhelfer _run (Vorweg 1 und 2)

#### Was gebaut ist

- **Helfer** (`app/templates/_berlin_date.html`): `berlinToday()` ('JJJJ-MM-TT'), `berlinMonth()` ('JJJJ-MM'), `berlinTime()` ('HH:MM'),
  `berlinAddDays(tag, n)` (Kalenderrechnung über UTC-Mitternacht, ohne Zeitumstellung), `localDateIso(d)` (Kalendertag eines aus
  einem Datum gebauten Date, Plantafel und Kalender), `berlinTodayDate()` (Ortsmitternacht des Berliner Tages als Startpunkt für
  Kalender und Plantafel); dazu wie bisher `berlinDateParts()` und `berlinMonthRange()`.
- **Aus UTC** (bis 1.8.86 `toISOString().slice(0, 10)`, zwischen 0 und 2 Uhr der Vortag): Büro-Zeiterfassung `today()`,
  Monteur-Zeiterfassung `today()`, ihr 14-Tage-Fenster und das Mindestdatum nach dem Sperrdatum, Einsatzbericht (Ausführungsdatum,
  Datum der Zeitbuchung), Projektmappe (nächste Fälligkeit des Wartungsvertrags), Eingangsrechnung (Bezahltdatum), Plantafel (`iso()`,
  Wochenbeginn, Markierung "heute"), Backoffice-Zeiterfassung (`dateISO()` jetzt über `localDateIso()`, Monat über
  `berlinMonthRange()`).
- **Aus der Zeitzone des Geräts**: Kalender (Ausgangstag, "heute"), Aufgaben und Befunde ("überfällig" bzw. Wiedervorlage über
  `toDateString()`), Stundenzettel (Vorgabemonat), Checkliste ("mit jetzt vorbelegen": Datum und Uhrzeit), Angebot (`localToday()` über
  `getTimezoneOffset()`), Dashboard (Bindefrist in sieben Tagen, Begrüßung nach der Uhrzeit), Einstellungen (Jahr für Basiszinssatz und
  Schulferien). Die Rechnungsseite nahm `berlinDateParts()` schon (seit 1.8.78), jetzt über `berlinToday()`.
- **Bewusst Zeitpunkte** (kein Kalendertag, in `ERLAUBT` des Strukturtests mit Grund): Zeitraum der Kalenderabfrage, Erfassungszeit
  einer Checklistenantwort auf dem Gerät, Wiedervorlage einer Anfrage (Zeitpunktvergleich), Cache-Brecher zweier Bilder, laufende Uhr
  des Timers, `berlinTodayIso()` im Versandverlauf (schon Europe/Berlin über Intl).
- **Klicktest Mahnwesen**: nach "3 Entwürfe angelegt." wartet er auf die neu geladene Liste, dann liest er sie
  (`createSelectedReminders()` setzt den Text vor `await reload()`; Nebenbefund 2 aus 1.8.84).
- **Testhelfer `_run`** (`tests/test_v375_rechnungen_sperren.py`): schließt nach dem Ende beider Aktionen auch die Sitzung der
  zweiten (Nebenbefund 5 aus 1.8.85) -- wirft sie nach der Sperre der Auftragszeile, hielt ihre offene Transaktion die Sperre; eine
  spätere Aktion auf derselben Zeile wartete ewig.

#### Festlegungen 1.8.87 (Bitte bestätigen)

1. **"Heute" = Berliner Tag auf jeder Seite**, auch wo bisher die Zeitzone des Geräts galt (Kalender, Aufgaben, Checkliste, Angebot …)
   -- wie der Server (Regel 20); ein Gerät in einer anderen Zeitzone sieht den Berliner Tag.
2. **Umfang**: das heutige Datum (und Uhrzeit beim Vorbelegen). Gespeicherte naive UTC-Zeitstempel, die eine Seite als Ortszeit
   liest oder per `slice(0, 10)` kürzt (Versandzeit, Hochladezeit, Datum einer Nebenforderung …), sind nicht Teil davon -- weiter
   offen (CLAUDE.md "Bekannte, bewusst offene Punkte").
3. **Plantafel und Kalender** rechnen weiter mit Date-Objekten in Ortszeit des Geräts (12 bzw. 0 Uhr), nur ihr Ausgangstag ist der
   Berliner; ein Tag daraus wird über `localDateIso()` gebildet, nie über `toISOString()`.
4. **Strukturtest per Muster über den Text der Vorlagen**, nicht über einen JavaScript-Parser: jede Fundstelle braucht einen Eintrag mit
   Grund, ein Eintrag ohne Fundstelle wird angemahnt.

#### Tests und Prüfung

- Neu `tests/test_v390_browser_datum.py` (13): kein `toISOString()`, `new Date()` und `Date.now()` ohne Argument außer den neun
  begründeten Zeitpunkten, keine veralteten Einträge, kein `getTimezoneOffset()`/`toDateString()`, jede Vorlage mit Helfer bindet
  `_berlin_date.html` ein, die Zeiterfassungen nehmen `berlinToday()`; in node (vier Zeitzonen) `berlinToday()`, `berlinTime()`,
  `berlinMonth()` an Berliner Mitternacht, Monats- und Jahreswechsel und Zeitumstellung, `berlinAddDays()` über Monats-, Jahres- und
  Schaltjahrgrenzen und die Zeitumstellung, `localDateIso()` und `berlinTodayDate()`.
- Neu `tests/test_v390_testhelfer.py` (1, gegen PostgreSQL): die zweite Aktion wirft mit gehaltener Sperre; danach sperrt eine dritte
  Sitzung dieselbe Auftragszeile innerhalb von 2 s (`lock_timeout`).
- Gegenproben (Regel 24): 8 von 8 rot -- `_run` ohne Schließen, Büro-Zeiterfassung und 14-Tage-Fenster aus UTC, "überfällig" über
  `toDateString()`, `getTimezoneOffset()`, fehlende Einbindung, `berlinToday()` über `toISOString()`, `berlinAddDays()` über Ortszeit.
  Jede Datei byte-genau zurück (SHA-256), kein Marker.
- Klicktest `scripts/klicktest_browser_datum.py` (neu): Instanz ab 00:30 Uhr, Browser-Uhr fest auf heute 00:30 Uhr Berliner Zeit, Zeitzone
  des Browsers UTC und New York (dort noch gestern) -- Monteur-Zeiterfassung mit der Buchung von heute, `today()`, Stundenzettel-Monat,
  Büro-Zeiterfassung, Aufgaben überfällig, Plantafel Wochenbeginn und Markierung, Kalender: 21/21; derselbe Klicktest auf 1.8.86
  (Arbeitskopie): 9/21 -- die Monteur-Zeiterfassung "Seite nicht bereit" wie im Anlass. `klicktest_mahnwesen` 29/29,
  `klicktest_teil_updates` 9/9.
- Volle Suite (mit den opt-in-Tests gegen PostgreSQL, Arbeitskopie, drei Teile parallel): 3808 grün, 0 rot.
- Alle Klicktests (Regel 26, `scripts/klicktest_alle.py`, Arbeitskopie): 54 von 54 wie erwartet, Laufzeit gesamt 11:17 min. Keine rote Prüfung -- `klicktest_mahnwesen` (29/29) und `klicktest_teil_updates` (9/9) sind wieder grün.

#### Nebenbefunde (nur gemeldet)

1. **Zeitstempel ohne Zeitzone im Browser** (bekannt, Festlegung 2): `new Date(r.email_sent_at)` liest naive UTC als Ortszeit, `.slice(0,
   10)` auf einem Zeitstempel ergibt zwischen 0 und 2 Uhr den UTC-Tag (u. a. Mahnwesen "versendet …", Nebenforderung "gebucht …",
   Hochladezeiten).
2. **Wiedervorlage einer Anfrage**: `follow_up_at` ist eine DateTime-Spalte, Dashboard und Anfragen vergleichen sie als Zeitpunkt in
   Ortszeit des Geräts -- ob sie als naive UTC oder als Ortszeit gespeichert wird, ist hier nicht geprüft.

### Umsetzung 1.8.88: Mengenvergleich im Entwurf der Schlussrechnung (Ergänzung zu Festlegung 1.8.85 Nr. 1)

#### Was gebaut ist

- **Vergleich** (`app/invoices.py::final_quantity_checks()`, je Position mit Auftragsbezug im Entwurf der Schlussrechnung, als
  `quantity_check` an der Position in `invoice_to_dict()`): Menge des Auftrags (von heute -- die Mengen des Auftrags bleiben bis zur
  Schlussrechnung änderbar, R4a), zuletzt abgerechnete Menge (`get_previous_cumulative_ist()`: Ist der zuletzt festgeschriebenen
  Rechnung dieser Position, Abschlag nach Leistungsstand oder Schluss; 0, wenn nie abgerechnet; ein Storno setzt auf den Stand davor
  zurück) und die Abweichungen des Ist -- `auftrag` (Ist ≠ Menge des Auftrags), `abgerechnet` (Ist unter der zuletzt abgerechneten
  Menge).
- **Rechnungsseite**: im Entwurf der Schlussrechnung die Spalten Auftrag / zuletzt abgerechnet / Ist (Eingabe) / EP / Betrag; eine
  abweichende Zeile farbig mit dem Grund unter dem Text ("Ist weicht von der Auftragsmenge ab (Auftrag 10)", "Ist liegt unter der
  zuletzt abgerechneten Menge (4)"), darüber "Eine Position weicht ab – bitte das Ist prüfen (markiert)". Nach dem Finalisieren und an
  jeder anderen Rechnung die bisherige Tabelle (Soll, Ist (gesamt), abgerechnet).

#### Festlegungen 1.8.88 (Bitte bestätigen)

1. **Markiert wird** ein Ist ungleich der Menge des Auftrags (mehr oder weniger) und ein Ist unter der zuletzt abgerechneten Menge (die
   Schlussrechnung nähme damit Abgerechnetes zurück); ein Ist zwischen beiden ist nicht "abweichend". Nur Hinweis, kein Sperrgrund --
   das Ist ist Sache der Rechnung (Festlegung 1.8.85 Nr. 6).
2. **Auftragsmenge von heute**, nicht der Schnappschuss beim Anlegen des Entwurfs (`soll_quantity`) -- eine spätere Mengenänderung am
   Auftrag zeigt sich sofort.
3. **Nur im Entwurf** und nur an der Schlussrechnung; das PDF bleibt unverändert.

#### Tests und Prüfung

- Neu `tests/test_v391_schluss_mengenvergleich.py` (7): ohne Abweichung; Ist unter der Auftragsmenge, unter dem zuletzt abgerechneten
  Stand, über der Auftragsmenge; nie abgerechnete Position und Nachtrag bei 0; Auftragsmenge live, zuletzt abgerechnet folgt einem
  später festgeschriebenen Abschlag; nach Storno des letzten Abschlags der Stand davor; kein Vergleich nach dem Festschreiben und an
  einem Abschlag; Router.
- Gegenproben (Regel 24): 5 von 5 rot -- Abweichung vom Auftrag bzw. unter dem abgerechneten Stand nicht markiert, Auftragsmenge aus
  dem Schnappschuss, Vergleich auch nach dem Festschreiben, Schema ohne das Feld. Jede Datei byte-genau zurück, kein Marker.
- Klicktest `klicktest_endrechnung.py` erweitert: Spalten Auftrag 10 / zuletzt 4 / Ist 10 ohne Markierung, Ist 3 markiert mit beiden
  Gründen und Hinweis, zurück auf 10 ohne Markierung.
- Volle Suite (mit den opt-in-Tests gegen PostgreSQL, Arbeitskopie, drei Teile parallel): 3814 grün, 1 rot -- `test_v231_invoice_item_table_width_and_quantity::test_invoice_detail_screen_still_shows_all_three_quantities` suchte den Tabellenkopf ohne Attribut (jetzt `id="itemsHead"`), Erwartung angepasst, die Datei danach 9 grün.
- Klicktest `klicktest_endrechnung` 25/25 (Arbeitskopie); alle Klicktests auf dem Stand 1.8.89, der diese Version enthält (siehe dort).

### Umsetzung 1.8.89: Mahnen nach der Endrechnung (Punkte 3–5)

Umfang: nach Punkt 5 committet (Vorgabe); Punkte 6 und 7 als eigene Version (unten bzw. Rest).

#### Was gebaut ist

- **Was gemahnt werden kann** (neu `app/final_dunning.py`, `DunningState`, nur abgeleitet): je Rechnung der Zahlstand der Rechnung
  selbst (`own`), an einer **gültigen Endrechnung** (festgeschriebene, nicht stornierte Schlussrechnung mit eingefrorenen Abzügen) die
  abgezogenen Rechnungen mit offenem Betrag (`deducted`: offen einschließlich Einbehalt, davon Einbehalt), an einer **abgezogenen
  Rechnung** die Endrechnung (`settled_in`), und der **angemahnte Betrag** (`dunnable`): an der Endrechnung ihr mahnfähiger Betrag
  plus die offenen Beträge der abgezogenen, an einer abgezogenen 0, sonst der mahnfähige wie bisher. `dunning_states()` für viele
  Rechnungen in wenigen Abfragen; mit `on` der Stand an einem Tag (Zustellung nachtragen) -- vor dem Tag der Endrechnung war eine
  Rechnung noch nicht abgezogen.
- **Mahnwesen** (`app/reminders.py`, überall `DunningState` statt des Zahlstands): "zur Mahnung fällig" ohne abgezogene Rechnungen, die
  Endrechnung mit dem Zahlbetrag (auch selbst bezahlt oder über 0 €); Anlegen zu einer abgezogenen 409 "Die Rechnung … ist in der
  Schlussrechnung … abgezogen – gemahnt wird nur noch die Schlussrechnung (über den Zahlbetrag)."; ein offener Entwurf ist überholt
  ("Der Entwurf (1. Mahnung) ist überholt: … Bitte den Entwurf löschen.", Festschreiben 409); eine festgeschriebene Mahnung geht nicht
  mehr hinaus ("… Die Mahnung M-… geht nicht mehr hinaus.", E-Mail und Zustellung ab dem Tag der Endrechnung 409). An der Endrechnung:
  "beglichen" bzw. "nur noch ihr Einbehalt offen" als Gründe, wenn nichts zu mahnen ist; Entwurf veraltet, festgeschriebene Mahnung geht
  nicht mehr hinaus, sobald eine Zahlung auf eine abgezogene Rechnung den Zahlbetrag ändert.
- **Aufstellung Format 4** (`amounts_snapshot()`): wie Format 3 die Zeilen der Rechnung selbst (`dunnable` = ihr mahnfähiger Betrag),
  dazu `deducted` (je abgezogener Rechnung Nummer, Art, offen, davon Einbehalt) und `principal` (angemahnter Betrag = Zahlbetrag);
  Gesamtbetrag = principal + Nebenforderungen. **PDF** (`app/reminder_pdf.py`): nach den eigenen Zeilen "Mahnfähig aus dieser
  Rechnung", je abgezogener "zzgl. noch offen aus Abschlag Nr. …" (mit "davon Einbehalt …, mit der Schlussrechnung fällig"),
  "Angemahnter Betrag (Zahlbetrag)".
- **Verzugszinsen** (`app/default_interest.py`): verzinst wird der angemahnte Betrag am Tag (`_principal_on()`), ein Abschnitt beginnt
  auch am Eingangstag einer Zahlung auf eine abgezogene Rechnung (`principal_invoice_ids()`).
- **Rechnungsseite und Listen** (`app/invoices.py::_payment_info()`, `invoice_overview_rows()`): "überfällig" nach dem angemahnten
  Betrag -- eine abgezogene Rechnung nie, die Endrechnung auch mit nur noch offenem Abschlag; `dunning` und an der abgezogenen der
  Hinweis "In der Schlussrechnung … abgezogen – diese Rechnung wird nicht mehr einzeln gemahnt …" samt "Der Einbehalt (…) ist mit der
  Schlussrechnung fällig." Rechnungsseite: Kennzeichen "in … abgezogen" bzw. "Zahlbetrag offen …", Hinweis in der Karte "Zahlungen",
  "Gemahnt wird der Zahlbetrag …" in der Karte "Mahnwesen", Aufstellung der Mahnung mit den abgezogenen Rechnungen. Mahnwesen: "Zahlbetrag
  samt R-…" unter dem Betrag.
- Zahlungen bleiben je Rechnung (unverändert; der Vorschlag geht schon zuerst auf die älteren offenen Rechnungen des Auftrags).
- Klicktest `scripts/klicktest_mahnen_endrechnung.py`.

#### Festlegungen 1.8.89 (Bitte bestätigen)

1. **Abgezogen** heißt: Abzug (`InvoiceDeduction`) einer gültigen Schlussrechnung. Eine Schlussrechnung von vor 1.8.85 ohne Abzüge
   (Altbestand, Rest über die Menge) ändert nichts -- ihre Abschläge bleiben einzeln mahnbar. Nach dem Storno der Schlussrechnung gilt
   wieder die Regel je Rechnung.
2. **Festgeschriebene, nie hinausgegangene Mahnung** einer abgezogenen Rechnung: geht ab dem Tag der Endrechnung nicht mehr hinaus; eine
   Zustellung mit früherem Tag lässt sich nachtragen (sie ging da wirklich hinaus). Ihre Nebenforderungen werden **nicht** von selbst
   gegengebucht (anders als beim Ersetzen) -- sie stehen an der Rechnung und lassen sich von Hand gegenbuchen.
3. **Nebenforderungen abgezogener Rechnungen** (Gebühren, Pauschale, Zinsen früherer Mahnungen) bleiben an ihrer Rechnung (bebuchbar,
   sichtbar); die Mahnung der Schlussrechnung nennt nur ihre eigenen -- wie der Zahlungshinweis (Festlegung 1.8.86 Nr. 1).
4. **Einbehalt**: der einer abgezogenen Rechnung gehört zum angemahnten Betrag; der eigene Einbehalt der Schlussrechnung wird weiter
   nicht gemahnt.
5. **Stufen und Fristen** folgen der Schlussrechnung (ihre Fälligkeit, ihre Mahnungen); eine erreichte Stufe eines Abschlags zählt
   nicht.
6. **Verzugszinsen** der Schlussrechnung auf den angemahnten Betrag, ab ihrem eigenen Verzugsbeginn; die Pauschale je Rechnung wie
   bisher.
7. **Überfällig** (Finanzen, Rechnungsseite) nach dem angemahnten Betrag; der Zahlstand je Rechnung (offen, bezahlt, Einbehalt offen)
   bleibt unverändert -- an der abgezogenen erklärt der Hinweis, wohin ihr offener Betrag gehört.

#### Tests und Prüfung

- Neu `tests/test_v392_mahnen_nach_endrechnung.py` (22, davon 4 gegen PostgreSQL): abgezogene Rechnung nicht mehr fällig, Endrechnung mit
  5.950 € (3.570 + 2.380); kein neuer Entwurf (Grund, nichts geschrieben); offener Entwurf überholt, Festschreiben 409, löschen geht;
  festgeschriebene Mahnung: E-Mail 409 (nichts gesendet), Zustellung ab dem Tag der Endrechnung 409, davor geht; nach Storno der
  Schlussrechnung wieder einzeln; Altbestand ohne Abzüge unverändert; Hinweis an der abgezogenen, überfällig in Rechnungsseite und
  Finanzen; Einbehalt des Abschlags fällig (3.950 €), eigener Einbehalt der Schlussrechnung nicht gemahnt; Aufstellung Format 4 mit zwei
  abgezogenen Rechnungen und PDF; Schlussrechnung selbst bezahlt -> Mahnung über den offenen Abschlag, geht hinaus; Schlussrechnung über
  0 € -> Mahnung über die Abschläge; Zahlung auf den Abschlag macht Entwurf und Mahnung veraltet; beglichen -> nichts zu mahnen;
  Gegenbuchung macht wieder mahnbar; Router 409 und reminder-status; Verzugszinsen auf den Zahlbetrag mit Abschnitt am Zahlungstag des
  Abschlags. **Gleichzeitig (PostgreSQL, Commit der ersten Aktion eine Sekunde angehalten):** Mahnung zum Abschlag wartet auf das
  Festschreiben der Schlussrechnung und wird abgelehnt; Festschreiben eines Entwurfs zum Abschlag wartet und ist überholt; Mahnung der
  Schlussrechnung wartet auf eine Zahlung auf den Abschlag und nimmt deren Stand; Zustellung zur Mahnung des Abschlags wartet und wird
  abgelehnt.
- **Erwartung geändert** (Format 4 statt 3): `test_v382_mahnwesen` (dazu `deducted` leer, `principal` = mahnfähig),
  `test_v383_nebenforderungen`, `test_v384_verzugszinsen`, `test_v384_verzugszinsen_pg` und der Klicktest
  `klicktest_verzugszinsen` ("Aufstellung Format 4 mit Rechtstext").
- Gegenproben (Regel 24): 14 von 14 rot -- nie als abgezogen erkannt, Einbehalt der abgezogenen nicht fällig, Endrechnung nur mit dem
  eigenen Betrag bzw. ohne eigenen Zahlstand nicht mahnbar, Zustellung ab der Endrechnung nicht gesperrt bzw. davor auch gesperrt,
  Entwurf nicht als überholt benannt, Zinsen nur auf den eigenen Betrag bzw. ohne Abschnitt bei Zahlung auf die abgezogene, überfällig
  nach dem eigenen Zahlstand, Aufstellung bzw. PDF ohne abgezogene, Anlegen ohne Zeilensperre (PostgreSQL), Schema ohne die Angaben.
  Jede Datei byte-genau zurück, kein Marker.
- Klicktest `klicktest_mahnen_endrechnung.py` 18/18 (Mahnwesen: Abschläge nicht fällig, Schlussrechnung 495 € mit "Zahlbetrag samt …",
  Entwurf überholt; Abschlag: Hinweis mit fälligem Einbehalt, nicht überfällig, Grund statt "anlegen"; Schlussrechnung: "Gemahnt wird der
  Zahlbetrag …", Entwurf mit Aufstellung je Rechnung, festgeschrieben, PDF; Zahlung auf den Abschlag -> neuer Zahlbetrag; API 409;
  412 px dunkel; Monteurin 403).
- Volle Suite (mit den opt-in-Tests gegen PostgreSQL, Arbeitskopie, drei Teile parallel): 3836 grün, 1 rot -- `test_v384_verzugszinsen_pg::test_pg_finalizing_waits_for_a_payment_on_a_charge_and_shows_it` erwartete Format 3, angepasst, die Datei danach 10 grün.
- Alle Klicktests (Regel 26, Arbeitskopie): 54 von 55 wie erwartet in 13:04 min; rot `klicktest_verzugszinsen` 26/27 -- **Erwartung veraltet seit 1.8.89** (prüfte Aufstellung Format 3), angepasst, danach 27/27.

#### Nebenbefunde (nur gemeldet)

1. **"Offener Betrag" in Finanzen** summiert weiter je Rechnung (offen einschließlich Einbehalt) -- richtig, solange keine Rechnung
   negativ ist; mit einer Überzahlung (Punkt 6) stünde ein Guthaben nirgends dagegen.
2. **Nebenforderungen einer nie hinausgegangenen Mahnung** an einer abgezogenen Rechnung (Festlegung 2) bleiben offen und sperren nach
   einem Storno der Schlussrechnung das Storno des Abschlags, bis sie gegengebucht sind -- wie jede offene Nebenforderung.
3. **Liste "Alle Mahnungen"** lädt je Mahnung die Abzüge ihrer Rechnung (`dunning_states()` je Liste, nicht je Zeile) -- eine Abfrage
   mehr je Liste.

## Entscheidungen Rechnungen (10.10.2026, festgehalten, nicht gebaut)

Vorgabe vom 10.10.2026, übernommen wie gegeben (Bezug Punkt 1 und 4):

- **Schlussrechnung als Endrechnung**: alle Positionen zu 100 %, Abzug aller festgeschriebenen, nicht stornierten
  Abschlagsrechnungen je mit Netto und USt, darunter „zzgl. noch offen aus Abschlag Nr. …“ und Zahlbetrag.
- **Abschlagsrechnungen** selbst nicht kumuliert.
- **Offene Abschläge** nach der Schlussrechnung nur noch über diese gemahnt.
- **Zahlung auf den Zahlbetrag**: Vorschlag zuerst auf offene Abschläge (ältester zuerst), dann Schlussrechnung, das Büro bestätigt.
  (Seit 1.8.78 gebaut als Zahlungsstufe Z1: Vorschlag zuerst auf die älteren offenen Rechnungen desselben Auftrags -- `zahlungen.md`.)
- **Rechnungsdatum** = Tag der Ausgabe, jede Rechnung mit Pflicht-Leistungszeitraum, Nummer beim Festschreiben, Nummernkreise beim
  Start auf 1. (Was dabei heute passiert: "Umsetzung 1.8.73" -> Befund b.) Pflicht-Leistungszeitraum seit 1.8.74 gebaut,
  Rechnungsdatum = Tag des Festschreibens seit 1.8.75.
- **Storno**: höchstens ein Storno je Rechnung, kein Storno eines Stornos.
- **Steuersatz**: keine mehreren Steuersätze je Rechnung.

Ergänzt am 12.10.2026 (Vorgabe 1.8.77, Punkt 3), übernommen wie gegeben:

- **Einbehalt**: nur bewusst gebucht, nie automatisch aus einer Unterzahlung; wird nicht gemahnt; Zustand „Einbehalt offen“;
  erscheint im Zahlungshinweis der Schlussrechnung; Gewährleistungseinbehalt mit Freigabedatum später. (Seit 1.8.78 gebaut: bewusst
  gebucht, nicht gemahnt, Zustand „Einbehalt offen“ -- `zahlungen.md`; Zahlungshinweis der Schlussrechnung und Freigabedatum offen.)
- **Rechnungen aus Aufwand** zählen in der Schlussrechnung zum Gesamtwert und werden wie Abschläge abgezogen; nach der
  Schlussrechnung keine Rechnung aus Aufwand im selben Auftrag; welche Stunden abrechenbar sind, regelt Stufe 2d. (Heute: weder im
  Gesamtwert noch abgezogen, nach der Schlussrechnung möglich -- "Umsetzung 1.8.73" -> Befund a, Festlegung 1.8.72 Nr. 3.)
- **Echtbetrieb**: Auf dem Server sind keine echten Bewegungsdaten: zum Echtbetrieb werden die Probebelege entfernt. (Damit ist die
  offene Wahl aus "Umsetzung 1.8.73" -> Befund b getroffen; wie entfernt wird, ist nicht festgelegt -- Nebenbefund 8 aus 1.8.77.)

Ergänzt am 12.10.2026 (Vorgabe R4a nach dem Befund R4), übernommen wie gegeben:

- **Betrag der Schlussrechnung** (Brutto für Zahlungen, offene Posten, „abgerechnet“) ist der Rechnungsbetrag nach dem Abzugsblock,
  nicht die Gesamtleistung; die Gesamtleistung ist nur Anzeige im PDF. „Abgerechnet = Summe der gültigen Rechnungsbeträge“ bleibt
  richtig, die xfail-Tests 1a und 1b messen das Richtige.
- **Rechnungs-PDF** jeder Art wird beim Festschreiben erzeugt und als feste Fassung mit Prüfsumme abgelegt; danach nie neu erzeugt.
  Versand und Download nur aus der Ablage. (Seit 1.8.82 gebaut.)
- **Sperren am Auftrag**: Einheitspreis und „in Summe“ einer Position gesperrt, sobald eine festgeschriebene Rechnung auf sie
  verweist; Steuersatz gesperrt ab der ersten festgeschriebenen Rechnung; Mengen bis zur Schlussrechnung änderbar; nach gültiger
  Schlussrechnung alles gesperrt. 409 mit Grund. (Seit 1.8.82 gebaut.)
- **Nachträge** nur als gekennzeichnete Auftragsposition; freie Positionen ohne Auftragsbezug nur in Rechnungen aus Aufwand.
  (Seit 1.8.83 gebaut.)
- **Negativer Abschlag nach Leistungsstand** wird abgelehnt, 409 mit Hinweis auf Storno oder Schlussrechnung. (Seit 1.8.83 gebaut.)
- **„Letzter Stand“** einer Position ist der des zuletzt festgeschriebenen Abschlags, nicht des zuletzt angelegten. (Seit 1.8.83
  gebaut.)
- **Storno eines pauschalen Abschlags ohne Positionen** (1d) lautet auf den Gegenbetrag des Originals. (Seit 1.8.83 gebaut.)

Ergänzt am 12.10.2026 (Vorgabe R4b), übernommen wie gegeben -- Wortlaut unter "Umsetzung R4b":

- **Festlegung 1.8.83 Nr. 6 geändert**: ein Abschlag muss über 0 € liegen; 0 € wird wie negativ abgelehnt. (Seit 1.8.85 gebaut.)
- **Schlussrechnung als Endrechnung**: alle Auftragspositionen einschließlich Nachträge mit Ist-Mengen (Vorschlag Ist = letzter Stand,
  im Entwurf änderbar), Gesamtleistung netto, USt, brutto; Abzugsblock je festgeschriebener, nicht stornierter Abschlagsrechnung und
  Rechnung aus Aufwand mit Nummer, Datum, Netto, USt, Brutto; Rechnungsbetrag = Gesamtleistung − Abzüge, der Betrag für Zahlungen,
  offene Posten und „abgerechnet“. (Seit 1.8.85 gebaut; Vorschlag Ist siehe Festlegung 1.8.85 Nr. 1.)
- **Beim Festschreiben** wird unter der Sperre neu gerechnet; weichen Preise oder Steuerschlüssel eines Entwurfs vom Auftrag ab, 409
  mit Hinweis zum Aktualisieren, für jede Rechnungsart; anderer Steuersatz eines abgezogenen Abschlags: Hinweis. (Seit 1.8.85 gebaut.)
- **Zahlungshinweis** „Stand <Tag des Festschreibens>“: je Abschlag mit offenem Betrag, einschließlich Einbehalt, „zzgl. noch offen
  aus Abschlag Nr. …“, darunter der Zahlbetrag; Mahnfähigkeit nach der Schlussrechnung regelt R4c. (Seit 1.8.86 gebaut.)
- **Keine Sperre** der Schlussrechnung nach pauschalen Abschlägen; nach der gültigen Schlussrechnung keine Rechnung aus Aufwand mehr im
  selben Auftrag. (Seit 1.8.85 gebaut.)
- **Schnellauftrag**: eine Rechnung aus Aufwand kann als abschließend gekennzeichnet werden und zählt dann als „vollständig
  abgerechnet“; keine Schlussrechnung über 0 €. (Seit 1.8.86 gebaut.)
- **Negativer Rechnungsbetrag** wird bis R4c mit 409 abgelehnt. (Seit 1.8.85 gebaut.)

Ergänzt am 13.10.2026 (Vorgabe R4c), übernommen wie gegeben -- Wortlaut unter "Umsetzung R4c":

- **Mengen im Entwurf der Schlussrechnung** (Ergänzung zu Festlegung 1.8.85 Nr. 1): je Position Auftragsmenge, zuletzt abgerechnete
  Menge und Ist nebeneinander, Abweichungen markiert. (Seit 1.8.88 gebaut.)
- **Abgezogene Rechnungen** stehen nach der gültigen Schlussrechnung nicht mehr einzeln in „zur Mahnung fällig“ und lassen sich nicht
  einzeln mahnen; offene Mahnungsentwürfe zu ihnen gelten als überholt. (Seit 1.8.89 gebaut.)
- **Einbehalte** auf abgezogene Rechnungen werden mit der gültigen Schlussrechnung fällig. (Seit 1.8.89 gebaut.)
- **Mahnung der Schlussrechnung** über den Zahlbetrag: mahnfähiger Betrag der Schlussrechnung plus offene Beträge der abgezogenen
  Rechnungen, in der Aufstellung je Rechnung mit Nummer. (Seit 1.8.89 gebaut.)
- **Überzahlung**: ein negativer Rechnungsbetrag wird zulässig; ist der Zahlbetrag negativ, weist das PDF einen Erstattungsbetrag aus,
  ohne Skonto und ohne „zahlbar“; die Erstattung ist als Zahlungsausgang buchbar, ein Guthaben steht am Kunden; Skonto nur bei
  positivem Rechnungsbetrag.
- **E-Mail zur Schlussrechnung** nennt den Zahlbetrag bzw. den Erstattungsbetrag.
