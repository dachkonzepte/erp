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

### Festlegungen 1.8.82 (Nr. 1–5 bestätigt am 12.10.2026, Vorgabe R4b; Nr. 6–9 bestätigt am 13.10.2026, Vorgabe Nacharbeiten R4c)

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

### Festlegungen 1.8.83 (Nr. 1–5 bestätigt am 12.10.2026, Vorgabe R4b; Nr. 6 geändert, siehe dort; Nr. 7–8 bestätigt am 13.10.2026, Vorgabe Nacharbeiten R4c)

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

#### Festlegungen 1.8.87 (alle bestätigt am 13.10.2026, Vorgabe "Vor dem Abnahmetest")

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

#### Festlegungen 1.8.88 (alle bestätigt am 13.10.2026, Vorgabe "Vor dem Abnahmetest")

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

Umfang: nach Punkt 5 committet (Vorgabe); Punkte 6 und 7 als eigene Version 1.8.90 (unten) -- R4c damit vollständig.

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

#### Festlegungen 1.8.89 (Nr. 2 und 3 bestätigt am 13.10.2026, solange die Mahngebühren aus sind -- `zahlungen.md`, "Vor dem Einschalten der Mahngebühren"; Nr. 1, 4–7 bestätigt am 13.10.2026, Vorgabe "Vor dem Abnahmetest")

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

### Umsetzung 1.8.90: Überzahlung, Erstattung, E-Mail (Punkte 6 und 7)

#### Was gebaut ist

- **Schlussrechnung unter 0 €** (`app/invoices.py::amount_block_reason()`): die Sperre "nicht unter 0 € bis R4c" entfällt; ein Abschlag
  bleibt über 0 € Pflicht. Zahlungshinweis (`payment_note()`): bei negativem Zahlbetrag zusätzlich `refund_amount` (= −Zahlbetrag); PDF
  "Erstattungsbetrag (Überzahlung)" statt "Zahlbetrag", Rechnungsseite ebenso.
- **Ohne Skonto und ohne "zahlbar"**: `format_payment_terms_sentence()` liefert bei einem Erstattungsbetrag "Den Erstattungsbetrag von
  … überweisen wir Ihnen." (auch statt einer Textvorlage der Zahlungsbedingung), das PDF überschreibt den Block "Erstattung:" statt
  "Zahlungsbedingungen: …" (`build_payment_tax_closing_block(payment_label=…)`). `skonto_offer()`: kein Skonto bei einem
  Rechnungsbetrag von 0 € oder weniger -- auch kein Skonto-Vorschlag beim Zahlungseingang.
- **Guthaben** (`app/final_dunning.py`): an einer Endrechnung unter 0 € ist ihr eigener Teil die Überzahlung (negativ) zuzüglich der
  gebuchten Erstattungen (`own_part`); was nach Verrechnung mit den offenen abgezogenen Rechnungen negativ bleibt, ist das Guthaben
  (`credit`), positiv bleibt der angemahnte Zahlbetrag. `app/payments.py::customer_credits()` je Kunde; `GET
  /api/customers/{id}/payments` mit `credits` und `credit_total`. Mahnung: "Die Schlussrechnung … weist eine Überzahlung aus --
  Guthaben des Kunden …, nichts zu mahnen."; mit offenem Abschlag über den Rest, Aufstellung "Überzahlung aus dieser Rechnung".
- **Erstattung als Zahlungsausgang** (`app/payments.py::book_refund()`, `POST /api/invoices/{invoice_id}/refunds`): eine Zahlung des
  Kunden über −Betrag mit einer Zuordnung Art `erstattung` (ebenfalls −Betrag) an der Schlussrechnung -- unter der Sperre der
  Auftragszeile, nur an einer gültigen Endrechnung mit Guthaben, höchstens das Guthaben, Datum nicht in der Zukunft (409 bzw. 400).
  Zahlungsausgang ohne "nicht zugeordnet" (Art `erstattung` zählt zum Betrag der Zahlung), Zuordnung allein nicht gegenbuchbar (409),
  zurück nur als Ganzes (`reverse_payment()`); Storno der Schlussrechnung gesperrt, solange eine Erstattung gebucht ist
  (`allocation_block_reason()` nennt sie). `not_payable_reason()` nennt die Überzahlung statt "über 0 € oder weniger".
- **Oberfläche**: Rechnungsseite -- Kennzeichen "Guthaben …", Karte "Zahlungen" mit Guthaben und "Erstattung buchen" (Datum, Betrag,
  Notiz, ohne Popup), Erstattung in den Zuordnungen mit Verweis auf die Kundenakte; Kundenakte -- "Guthaben: …" mit Verweis auf die
  Rechnung, Zahlungsausgang gekennzeichnet; Einstellungen -- die neuen Platzhalter der E-Mail-Vorlage.
- **E-Mail zur Schlussrechnung** (`send_invoice_email()`, Punkt 7): `{zahlbetrag}` (an der Endrechnung der Zahlbetrag, bei Erstattung
  leer, sonst der Rechnungsbetrag), `{erstattungsbetrag}`, `{zahlungshinweis}` ("Laut Zahlungshinweis (Stand …) beträgt der Zahlbetrag
  … ." bzw. "… ergibt sich ein Erstattungsbetrag von … – den überweisen wir Ihnen."); nennt die Vorlage keinen der drei, steht der Satz
  als eigener Absatz vor dem letzten (`_with_payment_note()`). `{gesamtbetrag}` bleibt der Rechnungsbetrag.
- Klicktest `scripts/klicktest_ueberzahlung.py`.

#### Festlegungen 1.8.90 (Nr. 4 bestätigt am 13.10.2026 zusammen mit Nacharbeit 1, gebaut als 1.8.91; Nr. 1–3, 5–7 bestätigt am 13.10.2026, Vorgabe "Vor dem Abnahmetest"; Nr. 5 erweitert durch 1.8.93 Nr. 8)

1. **Unter 0 € nur die Schlussrechnung**; ein Abschlag bleibt über 0 € Pflicht (Festlegung 1.8.83 Nr. 6 geändert).
2. **Erstattungsbetrag** = −Zahlbetrag laut Zahlungshinweis (beim Festschreiben eingefroren, wie der Zahlbetrag); "Erstattung" mit
   festem Satz statt der Zahlungsbedingungen, auch statt einer Textvorlage. Liegt nur der Rechnungsbetrag unter 0 € und der Zahlbetrag
   darüber, bleibt der Zahlungssatz (ohne Skonto).
3. **Skonto** nur über 0 € -- für jede Rechnung (unter 0 € gibt es nur die Schlussrechnung, 0 € nur Altbestand).
4. **Guthaben** live (wie der angemahnte Betrag): Überzahlung − offene abgezogene Rechnungen − gebuchte Erstattungen; eine spätere Zahlung
   auf einen abgezogenen Abschlag erhöht es. Verrechnet wird nur in der Rechnung (Zahlbetrag), nicht als Buchung an den Abschlägen.
5. **Zahlungsausgang** als Zahlung mit negativem Betrag (keine neue Tabelle, keine Migration); höchstens das Guthaben, nie in die Zukunft,
   nur an der Schlussrechnung gebucht, nur als Ganzes zurückgenommen.
6. **Storno** einer Schlussrechnung mit gebuchter Erstattung erst nach deren Rücknahme (wie jede Zuordnung).
7. **E-Mail**: der Betrag laut Zahlungshinweis (Stand des PDFs), nicht der Stand des Versandtags; Satz als eigener Absatz vor dem Gruß,
   wenn die Vorlage keinen der neuen Platzhalter nennt.

#### Tests und Prüfung

- Neu `tests/test_v393_ueberzahlung.py` (16, davon 2 gegen PostgreSQL): Schlussrechnung −1.190 € festschreibbar, Erstattungsbetrag, Satz statt Skonto, kein Skonto,
  Guthaben, nicht bebuchbar mit Grund; PDF mit "Erstattungsbetrag" und "Erstattung:", ohne "Zahlbar", "Skonto" und
  "Zahlungsbedingungen:"; Entwurf live, Mehrmenge mit Skonto; Rechnungsbetrag negativ mit offenem Abschlag -> Mahnung über den Rest
  (760 €) mit "Überzahlung aus dieser Rechnung"; teilweise offener Abschlag mindert das Guthaben; Guthaben am Kunden, Erstattung 1.000 €
  (Zahlung −1.000 €, Zuordnung "erstattung", Rest 0), zu viel 409, Rest 190 €, danach "kein Guthaben"; nichts zu mahnen bei Überzahlung;
  keine Erstattung ohne Guthaben bzw. am Abschlag, nicht in die Zukunft (nichts geschrieben); Zuordnung allein nicht gegenbuchbar, Storno
  gesperrt bis zur Rücknahme, danach Storno +1.190 €; Router (200, 409, 404, Kundenakte); E-Mail mit Erstattungsbetrag bzw. Zahlbetrag
  als Absatz vor dem Gruß, eigene Vorlage mit Platzhalter ohne Zusatz, andere Rechnung unverändert. **Gleichzeitig (PostgreSQL):** zwei
  Erstattungen zugleich -> die zweite 409 (nur noch 19 €); Erstattung wartet auf das Storno der Schlussrechnung und wird abgelehnt.
- **Erwartung geändert**: `test_v388_endrechnung` (die negative Schlussrechnung geht jetzt durch, statt 409 "bis R4c"),
  `test_v381_zahlungen_pg` (Rundgang über jeden schreibenden Zahlungsweg: neues Szenario für `POST /api/invoices/{invoice_id}/refunds`,
  unter der Sperre der Auftragszeile).
- Klicktest `klicktest_ueberzahlung.py` 16/16 (Entwurf −119 € mit Erstattungsbetrag und Satz statt Fälligkeit und Skonto, finalisieren;
  Kennzeichen und Karte Guthaben, Erstattung 100 € gebucht, Guthaben 19 €, Zeile ohne Gegenbuchen, zu viel 409, PDF; Kundenakte mit
  Guthaben und Zahlungsausgang ohne "nicht zugeordnet", zurückgenommen -> Guthaben 119 €; 412 px dunkel; Monteurin 403).
- Gegenproben 16 von 16 rot.
- Volle Suite (mit den opt-in-Tests gegen PostgreSQL, Arbeitskopie, drei Teile parallel): 3854 grün, 0 rot.
- Alle Klicktests (Regel 26, Arbeitskopie): 56 von 56 wie erwartet in 12:45 min.

#### Nebenbefunde (nur gemeldet)

1. **Schlusstext der Rechnung**: die Vorgabe "Bitte überweisen Sie den Rechnungsbetrag …" steht auch auf einer Schlussrechnung mit
   Erstattungsbetrag -- der Text wird nicht von selbst angepasst (im Entwurf änderbar).
2. **Verrechnung nur im Zahlbetrag**: verrechnet die Überzahlung einen noch offenen Abschlag, bleibt dieser je Rechnung "teilweise
   bezahlt" mit offenem Betrag stehen (Zahlstand je Rechnung, Festlegung 4) -- auch nach der Erstattung des Rests; Finanzen zählen ihn
   im "Offenen Betrag" mit, das Guthaben nicht dagegen (Nebenbefund 1 aus 1.8.89).
3. **Rest einer Zahlung und Guthaben** stehen in der Kundenakte nebeneinander -- ein nicht zugeordneter Rest wird nicht mit einem Guthaben
   verrechnet und umgekehrt.

## Nacharbeiten R4c (ab 1.8.91)

### Vorgabe vom 13.10.2026 (übernommen wie gegeben)

R4c geprüft. Festlegungen 1.8.82 Nr. 6–9 und 1.8.83 Nr. 7–8 bestätigt. Die neuen aus R4c (1.8.87–1.8.90) bitte alle je in einer Zeile
vorlegen. In CLAUDE.md als Regel: Der Bericht nennt jede neue Festlegung in einer Zeile, nicht nur die wichtigsten.

1.8.89 Nr. 2/3 bestätigt, solange die Mahngebühren aus sind; ins Archiv unter „Vor dem Einschalten der Mahngebühren“. 1.8.90 Nr. 4
bestätigt zusammen mit Punkt 1.

Nacharbeiten R4c:
1. Nach der gültigen Schlussrechnung zählen Finanzen und Dashboard je Auftrag nur noch ihren Zahlbetrag: positiv als offen, negativ als
   Guthaben. Die abgezogenen Rechnungen zählen dort nicht mehr einzeln; an ihnen steht „enthalten in Schlussrechnung R-…“ statt
   „teilweise bezahlt“.
2. Ist der Zahlbetrag negativ, entfällt die Zahlungsaufforderung im Schlusstext; stattdessen ein eigener Text für die Erstattung,
   gepflegt in den Einstellungen.
3. Am Kunden stehen nicht zugeordneter Rest und Guthaben zusammen als „Guthaben des Kunden“, aufgeschlüsselt; eine Erstattung kann
   beides ausgleichen.

Angriffstests mit Gegenprobe. Eigene Festlegungen mit „Bitte bestätigen“, je in einer Zeile. Nebenbefunde nur melden. Commit nach
Regel 13, Bericht kurz.

### Vorweg

- Festlegungen 1.8.82 Nr. 6–9 und 1.8.83 Nr. 7–8 an den Überschriften als bestätigt markiert; 1.8.89 Nr. 2 und 3 als bestätigt, solange
  die Mahngebühren aus sind, und in `zahlungen.md` unter "Vor dem Einschalten der Mahngebühren" festgehalten; 1.8.90 Nr. 4 als bestätigt
  zusammen mit Punkt 1 (gebaut als 1.8.91).
- CLAUDE.md Regel 28: der Bericht nennt jede neue Festlegung in einer Zeile.
- **Zur Bestätigung vorgelegt, je eine Zeile** (Wortlaut oben unter "Umsetzung R4c"):
  - 1.8.87 Nr. 1: "Heute" ist auf jeder Seite der Berliner Tag, auch wo bisher die Zeitzone des Geräts galt.
  - 1.8.87 Nr. 2: Umgestellt ist nur das heutige Datum (und die Uhrzeit beim Vorbelegen); gespeicherte UTC-Zeitstempel im Browser
    bleiben offen.
  - 1.8.87 Nr. 3: Plantafel und Kalender rechnen weiter in Ortszeit des Geräts, nur ihr Ausgangstag ist der Berliner; Tage über
    `localDateIso()`.
  - 1.8.87 Nr. 4: Der Strukturtest sucht per Muster im Text der Vorlagen; jede Fundstelle braucht einen Eintrag mit Grund.
  - 1.8.88 Nr. 1: Markiert wird ein Ist ungleich der Auftragsmenge und ein Ist unter der zuletzt abgerechneten Menge; nur Hinweis, kein
    Sperrgrund.
  - 1.8.88 Nr. 2: Verglichen wird mit der Auftragsmenge von heute, nicht mit dem Schnappschuss des Entwurfs.
  - 1.8.88 Nr. 3: Der Vergleich steht nur im Entwurf der Schlussrechnung; das PDF bleibt unverändert.
  - 1.8.89 Nr. 1: Abgezogen heißt Abzug einer gültigen Schlussrechnung; ohne Abzüge (Altbestand) und nach ihrem Storno gilt wieder je
    Rechnung.
  - 1.8.89 Nr. 4: Der Einbehalt einer abgezogenen Rechnung gehört zum angemahnten Betrag; der eigene der Schlussrechnung wird nicht
    gemahnt.
  - 1.8.89 Nr. 5: Mahnstufen und Fristen folgen der Schlussrechnung; eine erreichte Stufe eines Abschlags zählt nicht.
  - 1.8.89 Nr. 6: Verzugszinsen der Schlussrechnung laufen auf den angemahnten Betrag ab ihrem eigenen Verzugsbeginn; die Pauschale je
    Rechnung.
  - 1.8.89 Nr. 7: "Überfällig" richtet sich nach dem angemahnten Betrag; der Zahlstand je Rechnung bleibt (seit 1.8.91 heißt die
    abgezogene in Listen "enthalten in …").
  - 1.8.90 Nr. 1: Unter 0 € darf nur die Schlussrechnung lauten; ein Abschlag bleibt über 0 € Pflicht.
  - 1.8.90 Nr. 2: Erstattungsbetrag = −Zahlbetrag laut eingefrorenem Zahlungshinweis, mit festem Satz statt der Zahlungsbedingungen;
    ist nur der Rechnungsbetrag negativ, bleibt der Zahlungssatz ohne Skonto.
  - 1.8.90 Nr. 3: Skonto gibt es nur bei einem Rechnungsbetrag über 0 €, für jede Rechnungsart.
  - 1.8.90 Nr. 5: Der Zahlungsausgang ist eine Zahlung mit negativem Betrag, höchstens das Guthaben, nicht in der Zukunft, nur an der
    Schlussrechnung, nur als Ganzes zurückzunehmen.
  - 1.8.90 Nr. 6: Eine Schlussrechnung mit gebuchter Erstattung lässt sich erst nach deren Rücknahme stornieren.
  - 1.8.90 Nr. 7: Die E-Mail nennt den Betrag laut Zahlungshinweis (Stand des PDFs), als eigenen Absatz vor dem Gruß, wenn die Vorlage
    keinen der neuen Platzhalter nennt.

### Umsetzung 1.8.91: Finanzen und Dashboard zählen je Auftrag den Zahlbetrag (Punkt 1)

#### Was gebaut ist

- **Wie eine Rechnung zählt** (neu `app/final_dunning.py::overview()`, aus Zahlstand und `DunningState`, an jeder Rechnungszeile als
  `overview` = {state, state_label, open, retained, credit, settled_in}; `_payment_info()` in `app/invoices.py`, also in
  `/api/invoices`, `/api/projects/{id}/invoices`, `/api/orders/{id}/invoices` und `/api/invoices/{id}`):
  - an einer in einer gültigen Endrechnung abgezogenen Rechnung mit offenem Betrag (auch nur Einbehalt): Zustand `enthalten`, "enthalten
    in Schlussrechnung R-…", zählt 0; bezahlt bleibt `bezahlt`;
  - an der gültigen Endrechnung: Zahlbetrag = eigener offener Betrag (einschließlich Einbehalt; unter 0 € die Überzahlung zuzüglich der
    Erstattungen) + offene Beträge der abgezogenen. Positiv: offen, davon Einbehalt = eigener + der abgezogenen; Zustand ihr eigener
    Zahlstand, wenn keine abgezogene mehr offen ist, sonst `zahlbetrag_offen` ("Zahlbetrag offen"). Negativ: `guthaben`, Guthaben = das
    Guthaben des Kunden (`DunningState.credit`). Null: `bezahlt` bzw. ohne eigenen Zahlstand (unter 0 €) `ausgeglichen`;
  - sonst der Zahlstand der Rechnung; Entwurf, Storno und stornierte Rechnung zählen nicht (`overview` leer).
- **Finanzen**: offene Rechnungen, offener Betrag und "davon Einbehalt" aus `overview`, neue Kennzahl "Guthaben (Überzahlung)"; Spalte
  "Offen" mit dem Zahlbetrag, "—" an einer enthaltenen Rechnung, "Guthaben …" an der Endrechnung mit Überzahlung; Filter "Offen" mit
  "Zahlbetrag offen", "Bezahlt" mit "ausgeglichen", neu "Guthaben" und "In Schlussrechnung".
- **Dashboard** (Kennzahlen): offene Rechnungen und offener Betrag wie Finanzen, dazu "Guthaben (Überzahlung)".
- **Auftrag und Projektmappe** (Rechnungslisten) und **Kennzeichen der Rechnungsseite** nach `overview` ("Enthalten in Schlussrechnung …",
  "Zahlbetrag offen 495,00 €", "Guthaben 24,00 €"); die Karte "Zahlungen" der Rechnung zeigt weiter ihren eigenen Zahlstand -- gebucht
  wird je Rechnung.

#### Festlegungen 1.8.91 (alle bestätigt am 13.10.2026, Vorgabe "Vor dem Abnahmetest"; Nr. 5 geändert durch 1.8.93 Nr. 7)

1. **Zahlbetrag einschließlich Einbehalt**: offen an der Endrechnung = eigener offener Betrag samt Einbehalt + offene abgezogene
   Rechnungen samt Einbehalt (wie "Offener Betrag" bisher je Rechnung); der eigene Einbehalt der Schlussrechnung zählt dort als offen,
   gemahnt wird er weiter nicht.
2. **"Enthalten in Schlussrechnung R-…"** nur an einer abgezogenen Rechnung mit offenem Betrag (auch nur Einbehalt); eine bezahlte bleibt
   "bezahlt".
3. **Überall, wo der Zustand einer Rechnung steht**: Finanzen, Dashboard, Auftrag, Projektmappe und Kennzeichen der Rechnungsseite; die
   Karte "Zahlungen" der Rechnung bleibt beim eigenen Zahlstand.
4. **Zustand der Endrechnung**: ohne offene abgezogene Rechnung ihr eigener Zahlstand, sonst "Zahlbetrag offen"; negativ "Guthaben",
   ausgeglichen ohne eigenen Zahlstand "ausgeglichen".
5. **Guthaben in Finanzen und Dashboard** = Summe der Guthaben aus Endrechnungen (`DunningState.credit`), als eigene Kennzahl neben dem
   offenen Betrag, nie mit ihm verrechnet.
6. **Filter in Finanzen**: neu "Guthaben" und "In Schlussrechnung"; "Offen" schließt "Zahlbetrag offen" ein, "Bezahlt" "ausgeglichen".

#### Tests und Prüfung

- Neu `tests/test_v394_finanzen_zahlbetrag.py` (12): teilweise bezahlter Abschlag in der Schlussrechnung enthalten, nur die
  Schlussrechnung zählt (4.950 €); Rechnungsbetrag unter 0 € mit offenem Abschlag zählt den positiven Zahlbetrag (760 €); negativer
  Zahlbetrag als Guthaben (240 €); bezahlter Abschlag bleibt bezahlt, Guthaben 1.190 €; ausgeglichen; Einbehalte des Abschlags und der
  Schlussrechnung; eigener Zahlstand der Schlussrechnung ohne offenen Abschlag; nach Storno der Schlussrechnung wieder je Rechnung;
  Altbestand ohne Abzüge; Entwurf und Storno zählen nicht; vier Routen mit `overview`; Finanzen und Dashboard summieren `overview`.
- Klicktest `scripts/klicktest_finanzen_zahlbetrag.py` (neu) 15/15: Finanzen mit offenen Rechnungen 1, 495 €, Guthaben 24 €, Abschläge
  "Enthalten in Schlussrechnung …" mit "—", Filter; Dashboard; Auftrag und Projektmappe; Kennzeichen der Rechnungsseite, Karte
  "Zahlungen" weiter "teilweise bezahlt"; 412 px dunkel; Monteurin 403.
- **Erwartung geändert**: `klicktest_mahnen_endrechnung` prüfte am Abschlag das Kennzeichen "… · in … abgezogen", jetzt "Enthalten in
  Schlussrechnung …" (seit 1.8.91), 18/18; `klicktest_ueberzahlung` 16/16 unverändert.
- Gegenproben (Regel 24): 9 von 9 rot -- abgezogene zählt einzeln, bezahlte auch "enthalten", Endrechnung ohne die abgezogenen, negativ
  nicht als Guthaben, Einbehalt der abgezogenen fehlt, Zeilen ohne `overview`, Schema der Finanzen ohne `overview`, Finanzen bzw.
  Dashboard nach dem alten Stand. Jede Datei byte-genau zurück, kein Marker.
- Volle Suite (mit den opt-in-Tests gegen PostgreSQL, Arbeitskopie, drei Teile parallel): 3866 grün, 0 rot. Alle Klicktests auf dem Stand 1.8.93, der diese Version enthält (siehe dort).

#### Nebenbefunde (nur gemeldet)

1. **"Bezahlt (gesamt)" in Finanzen** zählt Zahlungen auf Rechnungen; ein Zahlungsausgang (Erstattung) mindert die Kennzahl nicht.
2. **Zahlung auf eine enthaltene Rechnung**: der Zahlungsdialog und "Rest zuordnen" bieten abgezogene Rechnungen weiter einzeln an (gebucht
   wird je Rechnung, der Vorschlag geht schon zuerst auf die älteren des Auftrags) -- richtig, aber in Finanzen steht die Rechnung ohne
   offenen Betrag.

### Umsetzung 1.8.92: Schlusstext bei Erstattung (Punkt 2)

#### Was gebaut ist

- **Auswahlliste** "Rechnungs-Schlusstexte bei Erstattung" (`invoice_refund_texts`, `app/option_settings.py`, angelegt von den
  Grunddaten beim Start, Regel 23) mit dem Standard-Eintrag "Vielen Dank für Ihren Auftrag. Sollte sich Ihre Bankverbindung geändert
  haben, teilen Sie uns diese bitte für die Erstattung mit." -- gepflegt unter Einstellungen → Auswahllisten (ab Büro, wie die anderen
  Textvorlagen).
- **Welcher Schlusstext gilt** (`app/invoices.py::refund_outro_text()`): im Entwurf einer Schlussrechnung mit Erstattungsbetrag (negativer
  Zahlbetrag laut Zahlungshinweis, `refund_due()`) der Standard-Eintrag der Auswahlliste, "" ohne aktiven Eintrag; sonst keiner.
  `invoice_to_dict()` liefert `refund_outro_text` und `printed_outro_text` (was das PDF druckt); `outro_text` bleibt der gespeicherte.
- **Festschreiben** (`finalize_and_send_invoice()`): nach dem Einfrieren des Zahlungshinweises, unter der Sperre der Auftragszeile -- ist
  der Zahlbetrag negativ, wird der Text der Erstattung der Schlusstext der Rechnung (`outro_text`, ohne aktiven Eintrag leer), vor der
  festen Fassung des PDFs. Danach druckt die Rechnung ihren gespeicherten Schlusstext.
- **PDF** (`app/invoice_pdf.py`): Schlusstext = `printed_outro_text`.
- **Rechnungsseite**: im Entwurf mit Erstattungsbetrag ein Hinweis am Schlusstext mit dem Text aus den Einstellungen bzw. "dort ist kein
  Eintrag aktiv"; das Feld Schlusstext bleibt bearbeitbar und gilt, sobald der Zahlbetrag nicht mehr negativ ist.

#### Festlegungen 1.8.92 (alle bestätigt am 13.10.2026, Vorgabe "Vor dem Abnahmetest")

1. **Ganzer Schlusstext statt eines Teils**: bei negativem Zahlbetrag ersetzt der Text der Erstattung den Schlusstext ganz, auch einen von
   Hand geänderten -- im Schlusstext steht in der Vorgabe nur die Zahlungsaufforderung; Schlusstext 2 bleibt.
2. **Auswahlliste statt eines Einzelfelds**: gepflegt unter Einstellungen → Auswahllisten wie die anderen Rechnungstexte; es gilt der
   Standard-Eintrag, eine Auswahl je Rechnung gibt es nicht.
3. **Live im Entwurf, eingefroren beim Festschreiben**: maßgeblich ist der Zahlbetrag beim Festschreiben (unter der Sperre), nicht der
   Stand der Seite; danach ändern weder die Einstellung noch spätere Zahlungen den Schlusstext.
4. **Nur negativer Zahlbetrag**: ist nur der Rechnungsbetrag negativ und der Zahlbetrag positiv (offene Abschläge), bleibt der
   Schlusstext mit der Zahlungsaufforderung; bei einem Zahlbetrag von genau 0 € ebenso.
5. **Ohne aktiven Eintrag kein Schlusstext** (nicht die Zahlungsaufforderung als Rückfall).
6. **Storno** einer solchen Schlussrechnung: unverändert, ein Storno übernimmt keinen Schlusstext.

#### Tests und Prüfung

- Neu `tests/test_v395_erstattung_schlusstext.py` (14, davon 1 gegen PostgreSQL): Auswahlliste aus den Grunddaten; Entwurf mit
  Erstattungsbetrag druckt den Text der Erstattung statt der Zahlungsaufforderung (PDF); Zahlbetrag positiv trotz negativem
  Rechnungsbetrag behält den Schlusstext; andere Rechnungen unverändert; im Entwurf live mit Einstellung und Zahlbetrag; ohne aktiven
  Eintrag kein Schlusstext; Festschreiben friert ein, spätere Einstellung ändert nichts; von Hand geänderter Schlusstext ersetzt,
  Schlusstext 2 bleibt; Zahlbetrag wird vor dem Festschreiben negativ bzw. positiv -- maßgeblich der Stand beim Festschreiben; Storno
  ohne den Text; Router und Einstellungen; Monteurin 403 beim Ändern. **Gleichzeitig (PostgreSQL):** das Festschreiben wartet auf
  eine Zahlung auf den Abschlag und nimmt den Text der Erstattung.
- Klicktest `klicktest_ueberzahlung.py` erweitert, 19/19: Hinweis am Schlusstext im Entwurf, nach dem Finalisieren Schlusstext = Text
  der Erstattung, Auswahlliste in den Einstellungen.
- Gegenproben (Regel 24): 10 von 10 rot -- Entwurf druckt die Zahlungsaufforderung, PDF nimmt den gespeicherten Schlusstext, Text der Erstattung auch bei positivem Zahlbetrag, Festschreiben friert nicht ein, Festschreiben nach dem Stand der Seite, festgeschrieben weiter live aus den Einstellungen, ohne aktiven Eintrag die Zahlungsaufforderung, Auswahlliste fehlt in den Grunddaten, Schema ohne den Text, Zahlung ohne Zeilensperre (PostgreSQL: das Festschreiben wartet nicht). Jede Datei byte-genau zurück, kein Marker.
- Volle Suite (mit den opt-in-Tests gegen PostgreSQL, Arbeitskopie, drei Teile parallel): 3880 grün, 0 rot. Alle Klicktests auf dem Stand 1.8.93, der diese Version enthält (siehe dort).

#### Nebenbefunde (nur gemeldet)

1. **Zahlbetrag genau 0 €**: die Schlussrechnung trägt weiter "Bitte überweisen Sie den Rechnungsbetrag …" und die Zahlungsbedingungen
   ("zahlbar bis …"), obwohl nichts zu zahlen ist (Festlegung 4).
2. **E-Mail-Vorlage**: der Text der E-Mail zur Schlussrechnung kommt weiter aus der einen Vorlage "Rechnung"; einen eigenen Text für die
   Erstattung gibt es dort nicht (nur den Satz `{zahlungshinweis}`).

### Umsetzung 1.8.93: Guthaben des Kunden, eine Erstattung für Rest und Überzahlung (Punkt 3)

#### Was gebaut ist

- **Erstattung aus dem Rest einer Zahlung** (neue Tabelle `payment_refund_sources`, Modell `PaymentRefundSource`, Migration
  `7b3e9d1f5a26`): je Zahlungsausgang und Zahlung eine Zeile mit dem Betrag (UNIQUE), unveränderlich (ORM-Sperre wie Zahlung und
  Zuordnung). `app/payments.py::payment_rest()`: der Rest einer Zahlung sinkt um das, was aus ihm erstattet ist (über Zahlungsausgänge,
  die nicht zurückgenommen sind, `refunded_from_rest()`); an einem Zahlungsausgang zählt es als zugeordnet. Eine Zuordnung braucht eine
  Rechnung (`payment_allocations.invoice_id` NOT NULL) -- deshalb eine eigene Tabelle statt einer neuen Art.
- **Guthaben des Kunden** (`customer_balance()`, in `GET /api/customers/{id}/payments` als `balance`): Reste der Zahlungen (älteste
  zuerst) und Guthaben aus Endrechnungen (`customer_credits()`, seit 1.8.90), je eine Zeile, mit Summen. Je Kunde für Finanzen und
  Dashboard `customer_balances()` (`GET /api/payments/customer-balances`): Rest wie bisher je Kunde (`unallocated_by_customer()`) und die
  Guthaben der gültigen Endrechnungen.
- **Erstattung** (`book_customer_refund()`, `POST /api/customers/{customer_id}/refunds` mit Zeilen {invoice_id | payment_id, amount}):
  ein Zahlungsausgang über die Summe; je Schlussrechnung eine Zuordnung Art `erstattung` (Prüfung wie `book_refund()`, gemeinsam
  `_check_credit()`), je Zahlung eine Zeile `PaymentRefundSource` (`_check_rest_line()`: derselbe Kunde, ein Zahlungseingang, nicht
  zurückgenommen, höchstens der Rest). Sperren über `lock_for_booking()`: die Aufträge der Schlussrechnungen, dann die Zahlungen
  aufsteigend -- Zuordnen eines Rests, Zurücknehmen der Zahlung und Erstatten aus ihr warten so aufeinander. Fehlerhafte Zeilen (keine,
  beide oder keine ID, doppelt, 0 €, mehr als zwei Nachkommastellen) 400, Datum in der Zukunft 400, unbekannte ID 404, am Stand nicht
  möglich 409.
- **Rücknahme**: der Zahlungsausgang nur als Ganzes (`reverse_payment()`, wie seit 1.8.90) -- danach ist der Rest wieder offen; eine
  Zahlung, aus deren Rest ein geltender Zahlungsausgang erstattet, lehnt `reverse_payment()` ab ("… erst den Zahlungsausgang
  zurücknehmen.").
- **Kundenakte**: Karte "Guthaben des Kunden" mit den Zeilen, je Zeile ein Betrag (vorgeschlagen: alles), Datum (Berlin) und Notiz,
  "Erstattung buchen"; Kennzeichen "Guthaben des Kunden: …" bzw. "Kein Guthaben"; am Zahlungsausgang "Erstattung aus dem Rest der Zahlung
  Nr. …", an der Zahlung "aus dem Rest erstattet mit Zahlungsausgang Nr. …".
- **Finanzen**: Kennzahl "Guthaben der Kunden" (Rest + Überzahlung, darunter "davon nicht zugeordnet") statt "Nicht zugeordnet" und
  "Guthaben (Überzahlung)" (1.8.91); Karte "Guthaben der Kunden" je Kunde mit Rest und Überzahlung. **Dashboard**: "Guthaben der Kunden"
  aus derselben Quelle.

#### Festlegungen 1.8.93 (alle bestätigt am 13.10.2026, Vorgabe "Vor dem Abnahmetest")

1. **Guthaben des Kunden** = nicht zugeordnete Reste seiner Zahlungen + Guthaben aus Endrechnungen; je Zahlung bzw. Schlussrechnung eine
   Zeile, die Zahlungen zuerst (älteste vorn).
2. **Eigene Tabelle für die Erstattung aus einem Rest** (`PaymentRefundSource`, Migration) statt einer Zuordnung -- eine Zuordnung hängt
   immer an einer Rechnung; die Zuordnungen bleiben unverändert.
3. **Ein Zahlungsausgang für beliebig viele Zeilen** (Reste mehrerer Zahlungen, Guthaben mehrerer Schlussrechnungen), je Zeile höchstens
   Rest bzw. Guthaben; in der Kundenakte vorgeschlagen: alles, änderbar je Zeile.
4. **Rücknahme nur als Ganzes**; die Zahlung, aus deren Rest erstattet ist, lässt sich erst nach der Rücknahme des Zahlungsausgangs
   zurücknehmen (sonst wäre Geld erstattet, das nie eingegangen ist).
5. **Quelle nur ein Zahlungseingang** desselben Kunden, nicht zurückgenommen -- kein Zahlungsausgang, keine Gegenbuchung.
6. **Sperren wie beim Buchen**: Aufträge der Schlussrechnungen aufsteigend, dann die Zahlungen aufsteigend (`lock_for_booking()`).
7. **Finanzen und Dashboard**: "Guthaben der Kunden" (Rest + Überzahlung je Kunde) ersetzt "Nicht zugeordnet" und "Guthaben
   (Überzahlung)" aus 1.8.91 (Festlegung 1.8.91 Nr. 5 damit geändert); in Finanzen mit "davon nicht zugeordnet" und je Kunde
   aufgeschlüsselt.
8. **Rechnungsseite** erstattet weiter nur das Guthaben dieser Schlussrechnung (1.8.90); Rest und mehrere Schlussrechnungen zusammen nur in
   der Kundenakte (Festlegung 1.8.90 Nr. 5 "nur an der Schlussrechnung" damit erweitert).

#### Tests und Prüfung

- Neu `tests/test_v396_guthaben_des_kunden.py` (27, davon 4 gegen PostgreSQL): Guthaben aus Rest und Überzahlung je Zeile und je Kunde;
  ein Zahlungsausgang erstattet beides (Zuordnung "erstattung", Zeile aus dem Rest, Rest und Zahlungsausgang ohne Rest, nichts mehr in
  Finanzen); teilweise aus dem Rest; erstatteter Rest lässt sich nicht mehr zuordnen. **Angriffstests:** Rest einer fremden Zahlung (409,
  nichts geschrieben), Guthaben einer fremden Schlussrechnung (409), unbekannte IDs und Kunde (404), Zahlungsausgang, zurückgenommene
  Zahlung und Gegenbuchung als Quelle (409), mehr als Rest bzw. Guthaben (409, nichts geschrieben), keine/beide IDs, 0 €, negativ, drei
  Nachkommastellen, doppelt, Zukunft (400); Quelle zurücknehmen erst nach dem Zahlungsausgang; Zeilen unveränderlich; Erstattung an der
  Rechnungsseite unverändert; Router (200, 409, 422, 400, 404) und Kundenakte; Monteurin 403; Finanzen und Dashboard aus
  `customer-balances`. **Gleichzeitig (PostgreSQL):** zwei Erstattungen aus demselben Rest -- die zweite 409; Zuordnen des Rests wartet auf
  die Erstattung aus ihm und wird abgelehnt; Zurücknehmen der Zahlung wartet und wird abgelehnt; Erstattung wartet auf das Storno der
  Schlussrechnung und wird abgelehnt (nichts geschrieben, Rest unverändert).
- Neu `tests/test_v396_guthaben_migration.py` (2, davon 1 gegen PostgreSQL): Bestand mit Zahlung, Rest und Zahlungsausgang -- hoch jede Zeile
  unverändert, Tabelle leer mit UNIQUE; runter exakt wie vorher; wieder hoch mit einer Erstattung aus dem Rest -> Rückweg verweigert,
  nichts geändert. `alembic check` nach `upgrade head`: keine Abweichung zwischen Modell und Migration.
- `tests/test_v373_zugehoerigkeit_struktur.py`: die zwei neuen IDs aus der Anfrage in `GEPRUEFT` (`book_customer_refund()` bzw.
  `_check_rest_line()`); **Erwartung geändert** in `tests/test_v394_finanzen_zahlbetrag.py` (das Guthaben kommt seit 1.8.93 aus
  `customer-balances`).
- Klicktest `klicktest_ueberzahlung.py` erweitert, 26/26: Kundenakte mit Guthaben des Kunden 69 € (Rest 50 € + 19 €) aufgeschlüsselt
  (**Erwartung geändert**, bis 1.8.92 nur das Guthaben der Schlussrechnung), nach Rücknahme 169 €; Finanzen "Guthaben der Kunden" 169 €
  davon nicht zugeordnet 50 € und Zeile des Kunden; eine Erstattung für beides -> "Kein Guthaben", Quelle an Zahlungsausgang und Zahlung,
  Zahlung zurücknehmen mit Grund abgelehnt, API 409; 412 px dunkel; Monteurin 403.
- Gegenproben (Regel 24): 16 von 16 rot -- Rest sinkt nicht, Zahlungsausgang mit Rest, fremde Zahlung, fremde Schlussrechnung, mehr als
  der Rest, Zahlungsausgang bzw. zurückgenommene Zahlung als Quelle, Quelle zurücknehmen trotz Erstattung, zurückgenommener
  Zahlungsausgang mindert weiter, Kundenakte ohne Überzahlung, Finanzen ohne Rest, Finanzen nach dem alten Abruf (zunächst grün: der
  Strukturtest fand die Adresse auch im Kommentar -- nachgeschärft auf den Abruf, dann rot), Zeilen veränderlich, Strukturtest Regel 25
  ohne Vergleich, Erstattung ohne Sperre der Zahlungen (PostgreSQL und im Rundgang unter SQLite). Jede Datei byte-genau zurück, kein Marker.
- Volle Suite (mit den opt-in-Tests gegen PostgreSQL, Arbeitskopie, drei Teile parallel): 3908 grün, 1 rot -- `test_v381_zahlungen_pg::test_every_writing_payment_route_has_a_scenario` verlangt für jeden schreibenden Zahlungsweg einen Rundgang unter dem Sperr-Beobachter; für `POST /api/customers/{customer_id}/refunds` ergänzt (der Beobachter prüft seit 1.8.93 auch die Erstattung aus dem Rest: nur unter der Sperre ihrer Zahlung, Gegenprobe rot), die Datei danach 14 grün.
- Alle Klicktests (Regel 26, Arbeitskopie): 55 von 57 wie erwartet in 11:46 min; rot `klicktest_zahlungen` 38/40 -- **Erwartung veraltet seit 1.8.93** (Kennzeichen der Kundenakte „Nicht zugeordnet: …“/„Nichts offen zuzuordnen“, jetzt „Guthaben des Kunden: …“/„Kein Guthaben“), angepasst, danach 40/40; rot `klicktest_checkliste_abschnitte` 27/28 („Hinweis weg nach der Antwort“), einzeln 28/28 -- nicht von dieser Runde (Nebenbefund).

#### Nebenbefunde (nur gemeldet)

1. **Verrechnen statt erstatten**: ein Guthaben aus einer Schlussrechnung lässt sich nicht mit einer offenen Rechnung desselben Kunden
   (anderer Auftrag) verrechnen, nur erstatten; ein nicht zugeordneter Rest dagegen schon (zuordnen).
2. **`GET /api/payments/unallocated`** wird von keiner Seite mehr gelesen (Finanzen nimmt `customer-balances`); der Endpunkt bleibt.
3. **Kundenakte**: "Zahlung zurücknehmen" steht auch an einer Zahlung, aus deren Rest erstattet ist -- die Ablehnung kommt erst beim
   Bestätigen (mit Grund).
4. **`klicktest_checkliste_abschnitte`** war im Gesamtlauf 27/28 ("Hinweis weg nach der Antwort" las noch "Vor der Unterschrift
   fehlen noch: Nachkontrolle ohne Befund."), einzeln 28/28 -- vermutlich liest die Prüfung vor dem Neuladen (wie `klicktest_mahnwesen`
   bis 1.8.87); der Klicktest ist nicht von dieser Runde berührt.

## Vor dem Abnahmetest (1.8.94)

### Vorgabe vom 13.10.2026 (übernommen wie gegeben)

Nacharbeiten R4c geprüft. Alle Festlegungen aus R4c (1.8.87–1.8.90) und 1.8.91–1.8.93 bestätigt.

1.8.94, Kleinkram vor dem Abnahmetest:
1. „Bezahlt (gesamt)“ in Finanzen zieht Zahlungsausgänge ab.
2. Zahlbetrag genau 0 €: keine Zahlungsaufforderung und kein „zahlbar bis“, stattdessen ein fester Satz, dass nichts mehr zu zahlen ist.
3. „Zahlung zurücknehmen“ nur anzeigen, wenn es möglich ist; sonst steht dort der Grund.
4. Zahlungsdialog und „Rest zuordnen“: Enthaltene Rechnungen stehen gruppiert unter ihrer Schlussrechnung, mit dem Hinweis „enthalten in …“.
5. Klicktests: ein gemeinsamer Helfer „warte auf neu geladene Liste“ im Klicktest-Werkzeug; klicktest_checkliste_abschnitte und alle Stellen
   mit demselben Muster nutzen ihn.

Angriffstests mit Gegenprobe. Eigene Festlegungen je in einer Zeile. Nebenbefunde nur melden. Commit nach Regel 13, Bericht kurz.

### Vorweg

- Festlegungen 1.8.87–1.8.93 an den Überschriften als bestätigt markiert (1.8.89 Nr. 2 und 3 weiter "solange die Mahngebühren aus
  sind"; 1.8.91 Nr. 5 geändert und 1.8.90 Nr. 5 erweitert durch 1.8.93, wie dort vermerkt).
- Mit dieser Runde erledigt: Nebenbefunde 1.8.91 Nr. 1 ("Bezahlt (gesamt)") und Nr. 2 (enthaltene Rechnungen im Zahlungsdialog), 1.8.92
  Nr. 1 (Zahlbetrag 0 €), 1.8.93 Nr. 3 ("Zahlung zurücknehmen") und Nr. 4 (`klicktest_checkliste_abschnitte`, siehe aber Nebenbefund 1
  unten: die Ursache war nicht der Klicktest allein).

### Umsetzung 1.8.94

#### Was gebaut ist

- **Punkt 1, "Bezahlt (gesamt)"** (Finanzen): Zahlungen auf Rechnungen abzüglich der Zahlungsausgänge an Schlussrechnungen. Dafür trägt
  `overview` jeder Rechnungszeile `refunded` (`app/final_dunning.py::DunningState.refunded`, an der gültigen Endrechnung die nicht
  zurückgenommenen Erstattungen, sonst 0); unter der Kennzahl "abzüglich Erstattungen …". Eine Erstattung aus dem Rest einer Zahlung
  (seit 1.8.93) zieht nichts ab -- der Rest zählte dort nie.
- **Punkt 2, Zahlbetrag genau 0 €** (`app/invoices.py::nothing_due()`: Zahlungshinweis einer Endrechnung mit Zahlbetrag 0, also
  Rechnungsbetrag und noch Offenes aus den abgezogenen Rechnungen gleichen sich aus): statt der Zahlungsbedingungen ("Zahlbar rein netto
  bis …", auch statt einer Textvorlage) der feste Satz `NOTHING_DUE_SENTENCE` "Mit den geleisteten Zahlungen ist der Zahlbetrag
  ausgeglichen – es ist nichts mehr zu zahlen." (`format_payment_terms_sentence()`), im PDF unter "Zahlung" ohne die Bezeichnung der
  Zahlungsbedingung; kein Schlusstext (er trägt die Zahlungsaufforderung) -- im Entwurf live (`printed_outro_text` leer,
  `nothing_due_outro` für den Hinweis am Schlusstext der Rechnungsseite), beim Festschreiben unter der Sperre geleert (`outro_text`);
  Schlusstext 2 bleibt. Die E-Mail nennt "Laut Zahlungshinweis (Stand …) ist nichts mehr zu zahlen (Zahlbetrag 0,00 €)."
  (`payment_note_sentence()`).
- **Punkt 3, "Zahlung zurücknehmen"**: `app/payments.py::reverse_block_reason()` (Erstattung aus dem Rest dieser Zahlung, schon
  zurückgenommen, Gegenbuchung) -- dieselbe Prüfung, die `reverse_payment()` unter der Sperre macht; `payment_to_dict()` liefert sie je
  Zahlung (`reverse_block_reason`), die Kundenakte zeigt den Grund statt des Knopfs.
- **Punkt 4, gruppiert**: offene Rechnungen des Kunden (`/api/customers/{id}/open-invoices`) und Vorschlagszeilen
  (`/api/invoices/{id}/payment-proposal`) tragen `settled_in` = die gültige Endrechnung, in der die Rechnung abgezogen ist
  (`settled_in_map()` über `app/final_dunning.py::settling_finals()`). Neuer Helfer `app/templates/_zahlung_gruppen.html`
  (`zahlungsGruppen()`, `zahlungsOptionen()`, `enthaltenText()`): im Zahlungsdialog ein Block "Schlussrechnung R-… und die darin
  enthaltenen Rechnungen" mit der Schlussrechnung zuerst und darunter jeder enthaltenen mit "enthalten in Schlussrechnung R-…"; in den
  Auswahlen "Weitere Rechnung des Kunden von Hand" und "Rest zuordnen auf …" je Schlussrechnung ein `<optgroup>`. Nur die Anzeige ist
  gruppiert: Vorschlag (ältere zuerst) und Buchung bleiben je Rechnung, jede Zeile behält ihren Index.
- **Punkt 5, Klicktest-Helfer** (`scripts/cdp_klicktest.py`): `ANFRAGEN_ZAEHLER` zählt in jedem Dokument die Anfragen der Seite (fetch und
  XMLHttpRequest, eingesetzt in `_lauf()`); `Tab.warte_auf_neu_geladene_liste(aktion, liste)` löst die Aktion aus und wartet, bis seither
  eine Anfrage gestartet, keine mehr unterwegs und 0,3 s Ruhe ist (`neu_geladen_bedingung()`), mit `liste` zusätzlich, bis die vorher darin
  stehenden Elemente aus dem Dokument sind; ohne Aktion (nach `oeffnen()`) nur bis zur Ruhe. Zeitüberschreitung: Meldung, der Test zählt
  als nicht wie erwartet.
  **Durchsicht** aller 37 festen Pausen und der Statustexte, die eine Seite vor dem Neuladen setzt: umgestellt sind
  `klicktest_checkliste_abschnitte` (zwei Speichern gleichzeitig, dann der Hinweis), `klicktest_checkliste_verwerfen` (Speichern, dann
  lesen; 0,5 s Pause), `klicktest_mahnwesen` (von Hand seit 1.8.87), `klicktest_abnahme` ("Vorschlag übernommen." vor dem Neuladen der
  Karte), `klicktest_bedenkenanzeige` (zweimal: ein Hinweis darf NICHT erscheinen -- nach fester Pause war das auch vor dem Nachladen
  grün), `klicktest_nebenforderungen` (Text vor `loadAndRenderReminders()`). Kein Treffer, obwohl ein Text vor dem Neuladen steht:
  `klicktest_vertragsgrundlage` und `klicktest_maengel` rufen die async-Funktion der Seite direkt auf, `Tab.js()` wartet ihr Ende ab.
  Die übrigen Pausen stehen vor Screenshots, beim Zeichnen oder zwischen Mausereignissen.

#### Festlegungen 1.8.94 (alle bestätigt am 13.10.2026, Vorgabe 1.8.95; zu Nr. 2: eine andere Rechnung über 0,00 € lässt sich seit 1.8.95 nicht mehr festschreiben, Punkt 2)

1. **"Bezahlt (gesamt)" abzüglich nur der Erstattungen an Schlussrechnungen** (Zuordnung "erstattung"); eine Erstattung aus dem Rest einer
   Zahlung zieht nichts ab, weil der Rest dort nie mitzählte. Unter der Kennzahl "abzüglich Erstattungen …".
2. **Zahlbetrag genau 0 € = Zahlungshinweis einer Endrechnung**; eine andere Rechnung über 0,00 € (Rechnung aus Aufwand, Schlussrechnung
   ohne Abzüge) behält ihre Zahlungsbedingungen (Nebenbefund 2).
3. **Fester Satz** "Mit den geleisteten Zahlungen ist der Zahlbetrag ausgeglichen – es ist nichts mehr zu zahlen." statt der
   Zahlungsbedingungen, im PDF unter "Zahlung" ohne Bezeichnung der Zahlungsbedingung; nicht in den Einstellungen pflegbar.
4. **Schlusstext entfällt ganz** (auch ein von Hand geänderter), Schlusstext 2 bleibt -- wie bei der Erstattung (1.8.92 Nr. 1).
5. **Live im Entwurf, eingefroren beim Festschreiben** (Schlusstext geleert, unter der Sperre der Auftragszeile); eine festgeschriebene
   Rechnung folgt ihrem eingefrorenen Zahlungshinweis. Altbestand (vor 1.8.94 festgeschrieben, Zahlbetrag 0 €): die feste Fassung bleibt,
   Rechnungsseite und E-Mail nennen den neuen Satz.
6. **E-Mail**: bei 0 € lautet der Satz zum Zahlungshinweis "Laut Zahlungshinweis (Stand …) ist nichts mehr zu zahlen (Zahlbetrag
   0,00 €)."
7. **Grund statt Knopf aus derselben Prüfung** wie das Zurücknehmen (`reverse_block_reason()`); die API lehnt weiter mit 409 ab.
8. **Gruppiert nur in der Anzeige**: Vorschlag, Reihenfolge der Verteilung und Buchung bleiben je Rechnung; in der Gruppe die
   Schlussrechnung zuerst, die Gruppe an der Stelle ihrer ersten Zeile; ist die Schlussrechnung selbst nicht offen, steht die Gruppe mit
   "auf die Schlussrechnung selbst ist nichts offen".
9. **"Enthalten" wie in Finanzen**: in einer gültigen Endrechnung abgezogen (`settling_finals()`); nach ihrem Storno wieder einzeln.
10. **"Neu geladen" im Klicktest** = seit der Aktion eine Anfrage gestartet, keine mehr unterwegs, 0,3 s Ruhe, mit Liste deren alte
    Elemente weg; eine erst nach der Ruhezeit startende Anfrage (Entprellung) ist nicht erfasst; Zeitüberschreitung zählt als Abweichung.
11. **Umgestellt nur Stellen mit dem Muster** (Aktion lädt nach, der Test liest ohne Beleg); Pausen vor Screenshots, beim Zeichnen und
    zwischen Mausereignissen bleiben, ebenso überflüssige Pausen ohne Nachladen.

#### Tests und Prüfung

- Neu `tests/test_v397_kleinkram_zahlungen.py` (30, davon 1 gegen PostgreSQL): `overview.refunded` an der Endrechnung, nach Rücknahme 0,
  Erstattung aus dem Rest ohne Wirkung; Finanzen in node mit den Daten der API: 5.950 € -> nach Erstattung 1.190 € "4.760,00 €" mit
  "abzüglich Erstattungen", Erstattung aus dem Rest ändert nichts; Zahlbetrag 0 € (Rechnungsbetrag −1.190 € mit 1.190 € offen und
  Rechnungsbetrag 0 € bei bezahltem Abschlag): Satz, kein Schlusstext, PDF ohne "Zahlbar rein netto", Zahlungsaufforderung und
  "Zahlungsbedingungen:"; Schlusstext 2 bleibt; Zahlbetrag 1 € bzw. Erstattung unverändert; Abschlag nie; Festschreiben leert den
  Schlusstext, feste Fassung mit dem Satz; Zahlbetrag wird vor dem Festschreiben 0 bzw. nicht mehr 0 -- maßgeblich der Stand beim
  Festschreiben; spätere Zahlung ändert nichts; E-Mail-Satz; Storno; Router. Zurücknehmen: Grund gleich der Ablehnung (nichts
  geschrieben), Zahlungsausgang frei, danach die Zahlung frei; schon zurückgenommen, Gegenbuchung; Route mit Grund, API trotzdem 409;
  Kundenakte in node (Grund statt Knopf). Gruppiert: `settled_in` an offenen Rechnungen, nach Storno weg; Vorschlag und Routen; Helfer in
  node (Reihenfolge, ohne Schlussrechnung, `<optgroup>` mit Hinweis); **Angriffstests:** Rechnungsnummer mit HTML erscheint als Text;
  Zahlungsdialog in node (Gruppe, Hinweis, Index der Zeile); Vorlagen rufen den Helfer auf; Monteurin 403 für offene Rechnungen, Vorschlag,
  Zahlungen und Zurücknehmen. **Gleichzeitig (PostgreSQL):** das Festschreiben wartet auf die Zahlung, die den Zahlbetrag auf 0 € bringt,
  und leert den Schlusstext.
- Neu `tests/test_v397_klicktest_helfer.py` (12): Zählerskript und Wartebedingung in node mit gestellter Uhr -- wartet auf laufende
  Anfragen und die Ruhezeit, Kette Speichern -> Neuladen, XMLHttpRequest, ohne Aktion, Liste; jeder Tab bekommt den Zähler; die sechs
  Klicktests mit dem Muster rufen den Helfer auf, ohne feste Pause an den Stellen.
- Klicktest `scripts/klicktest_zahlungen_kleinkram.py` (neu) 23/23: Finanzen 1.271 € abzüglich Erstattungen 100 €; Kundenakte Grund statt
  Knopf, Zahlungsausgang mit Knopf, "Rest zuordnen" gruppiert, 30 € auf den enthaltenen Abschlag; Zahlungsdialog gruppiert, Beträge
  umverteilt und auf der richtigen Rechnung gebucht; Entwurf mit Zahlbetrag 0 €: Satz und Hinweis, finalisiert ohne Schlusstext, PDF aus der
  Ablage; 412 px dunkel; Monteurin 403. Umgestellte Klicktests einzeln: `checkliste_abschnitte` 29/29, `checkliste_verwerfen` 23/23,
  `mahnwesen` 29/29, `nebenforderungen` 31/31, `abnahme` 57/57, `bedenkenanzeige` 22/22.
- Gegenproben (Regel 24): 25 von 25 rot -- `refunded` fehlt, Finanzen zieht nicht ab, `nothing_due()` nie, Satz fehlt, Festschreiben leert
  nicht, Entwurf druckt den Schlusstext, PDF-Überschrift "Zahlungsbedingungen", E-Mail-Satz alt, Grund fehlt, Kundenakte zeigt immer den
  Knopf, Zurücknehmen ohne Prüfung (API an der Oberfläche vorbei), `settled_in` leer bzw. an offenen Rechnungen oder im Vorschlag fehlend,
  Helfer ordnet nicht um, Helfer maskiert nicht, Dialog ohne Gruppen bzw. ohne Hinweis, Kundenakte ohne Helfer, Zahlung ohne Sperre
  (PostgreSQL), Monteurin darf Zahlungen, Klicktest-Helfer ohne Warten auf laufende Anfragen bzw. ohne Ruhezeit, Zähler nicht
  eingesetzt, Klicktest wieder mit Pause. Jede Datei byte-genau zurück (SHA-256), kein Marker.
- Volle Suite (mit den opt-in-Tests gegen PostgreSQL, Arbeitskopie, drei Teile parallel): 3952 grün, 0 rot.
- Alle Klicktests (Regel 26, Arbeitskopie): 57 von 58 wie erwartet in 12:08 min, `klicktest_checkliste_abschnitte` 29/29 und `klicktest_zahlungen_kleinkram` 23/23 darunter; rot `klicktest_ueberzahlung` 25/26 ("Zahlung mit erstattetem Rest zurücknehmen: abgelehnt mit Grund") -- **Erwartung veraltet seit 1.8.94**: die Prüfung klickte "Zahlung zurücknehmen" und erwartete die Ablehnung, jetzt steht dort der Grund statt des Knopfs; angepasst (Grund da, kein Knopf, API 409), danach 26/26.

#### Nebenbefunde (nur gemeldet)

1. **Checklistenseite übernimmt eine spät eintreffende, veraltete Speicher-Antwort** (die eigentliche Ursache des roten
   `klicktest_checkliste_abschnitte` aus 1.8.93): `sendAnswer()` übernimmt aus jeder Antwort `answers`, `missing_required` und
   `missing_before_signature`, ohne Stand -- es gilt die zuletzt ankommende, nicht die neueste. Laufen zwei Speichern gleichzeitig (Feld
   per blur, sofort danach eine Kachel) und kommt die früher berechnete Antwort später an, steht "Vor der Unterschrift fehlen noch: …"
   wieder da, `cl.answers` verliert die Kachel, und eine Unterschrift darunter lehnt die Seite bis zum Neuladen ab; gespeichert ist
   alles richtig. Nachgestellt mit einer zurückgehaltenen Antwort (Skript nur im Scratchpad): 7 von 7 wie beschrieben. Der Klicktest
   wartet jetzt beide Antworten ab und wird rot, wenn das im Lauf passiert. Abhilfe wäre ein Stand vom Server, nach dem nur neuere
   Antworten übernommen werden, oder ein Neulesen, sobald nichts mehr unterwegs ist.
2. **Andere Rechnungen über 0,00 €** (Rechnung aus Aufwand, Schlussrechnung ohne Abzüge) tragen weiter "Zahlbar rein netto bis …" und
   den Schlusstext mit der Zahlungsaufforderung (Festlegung 2).
3. **Statustext vor dem Neuladen** steht auf vielen Seiten (u. a. `_abnahme.html`, Mahnungen auf `invoice_detail.html`, `checklist.html`
   Versand und Unterschrift, `settings.html`, `time_tracking.html`, `inquiries.html`): kurz steht "Gespeichert." neben der alten Anzeige.
   Für Klicktests fängt das der Helfer ab; an den Seiten nichts geändert.
4. **Überflüssige feste Pausen** ohne Nachladen dazwischen (`klicktest_beleg_und_hinweis`, `klicktest_checkliste_unterschrift`,
   `klicktest_checkliste_zweck`, `klicktest_maengel_monteur`, `klicktest_zeitbuchungen_liste`) -- gelassen, schaden nicht.

## Veraltete Antworten und Rechnungen über 0 € (1.8.95)

### Vorgabe vom 13.10.2026 (übernommen wie gegeben)

1.8.94 geprüft. Festlegungen 1–11 bestätigt.

1.8.95:
1. Veraltete Antworten (Nebenbefunde 1 und 3): Seiten übernehmen nie eine Antwort, die älter ist als eine schon angewandte. Gemeinsamer
   Baustein in den Vorlagen, z. B. eine laufende Nummer je Formular oder Feld; „Gespeichert.“ erst, wenn die Antwort angewandt ist.
   Strukturtest: Jedes Speichern per fetch läuft über den Baustein. Klicktest mit gezielt zurückgehaltener Antwort, mindestens für
   Checkliste, Abnahme, Mahnung und Einstellungen.
2. Rechnungen über 0 € oder weniger gibt es nur als Storno oder als Endrechnung mit Abzügen; jede andere Rechnung muss über 0 € liegen,
   sonst 409 beim Festschreiben (Nebenbefund 2).

Angriffstests mit Gegenprobe. Eigene Festlegungen je in einer Zeile. Nebenbefunde nur melden. Commit nach Regel 13, Bericht kurz.

### Umsetzung 1.8.95

#### Was gebaut ist

- **Baustein `app/templates/_speichern.html`** mit zwei Funktionen. Ein Bereich ist, was eine Antwort auf der Seite ersetzt (Formular,
  Karte, Liste, Feld; Name je Seite frei). Je Bereich bekommt jede Anfrage, deren Antwort die Seite übernimmt, beim Absenden die nächste
  laufende Nummer; übernommen wird eine Antwort nur, wenn keine mit höherer Nummer schon angewandt ist.
  - `lesen(bereich, anfrage, anwenden)`: Lesen geht erst hinaus, wenn im Bereich kein Speichern unterwegs ist; `anwenden` läuft nur für
    eine nicht veraltete Antwort (Rückgabe true/false).
  - `speichern(bereich, anfrage, {anwenden | neuLaden})`: `anfrage` ist genau ein schreibender Aufruf `()=>api(…)`/`()=>fetch(…)`.
    Speichern geht je Bereich nacheinander hinaus (das nächste erst nach der Antwort des vorigen) -- so bearbeitet der Server sie in der
    Reihenfolge der Nummern, auch mit zwei Arbeitsprozessen, und die zuletzt angewandte Antwort kennt alles davor. Gebaut wird die Anfrage
    trotzdem beim Aufruf (URL und Body mit den Werten vom Klick): `fetch()` ist während des Aufrufs durch eine Fassung ersetzt, die bis zur
    Freigabe wartet -- sonst schickte ein wartendes Speichern ein Formular, das die Antwort des vorigen inzwischen neu gezeichnet hat
    (beim Umbau der Arbeitsvorbereitung gefunden). Erreicht der Pfeil `fetch()` nicht sofort, meldet der Baustein es (`console.error`).
    `speichern()` kehrt erst zurück, wenn `anwenden` gelaufen bzw. über `neuLaden` (mit `lesen()`) neu geladen ist; ein Fehler geht an den
    Aufrufer, eine fetch-Antwort mit Fehlerstatus kommt unverändert zurück -- beides ohne anzuwenden.
  - Mehrfach einbindbar (Stand an `window`), jede Vorlage, die ihn selbst nutzt, bindet ihn ein.
- **Alle Vorlagen umgestellt**: jede Anfrage mit Methode ungleich GET (Speichern, Anlegen, Löschen, Versand, Hochladen, Anmelden,
  Abmelden) über `speichern()`; die Ladefunktionen, die danach laufen, über `lesen()`; Erfolgstexte hinter `await speichern(…)`. Behoben
  damit Nebenbefund 1 aus 1.8.94 (Checkliste: Feld und Kachel gehen nacheinander hinaus, eine ältere Antwort überschreibt die neuere nicht
  mehr) und Nebenbefund 3 (Statustext vor dem Neuladen). Wo eine Seite die Antwort des E-Mail-Versands direkt übernahm (Auftrag, Rechnung,
  Vertrag), lädt sie jetzt neu. Bereiche je Seite (Auswahl): Checkliste `checkliste` (Antworten, Anhänge, Unterschrift, Abschluss,
  Neuladen), `anzeige`, `protokoll-versand`, `fassungen`, `folgen`, `regeln`, `erklaerungen`, `maengel-<Feld>`; Auftrag `auftrag`
  (`ladeAuftrag(zeichnen)`: ist die Antwort veraltet, zeichnet die Stelle aus dem schon neueren Auftrag), `vertrag`, `vertrag-anlage`,
  `vertragsgrundlage`, `rechnungen`, `gewaehrleistung`, `abnahmen`, `protokoll-abnahmen`, `maengel`, `einsatzberichte`; Rechnung
  `rechnung`, `zahlungen`, `zahlungsvorschlag`, `mahnungen`, `nebenforderungen`; Mahnwesen `mahnwesen`; Versandverlauf
  `versandverlauf-<Container>`, Versand `versand-<Platz>`. Die Umstellung der übrigen Vorlagen haben sechs parallele Helfer nach einer
  gemeinsamen Anleitung gemacht, der Strukturtest ist das Abnahmekriterium; ihre Berichte sind in die Nebenbefunde eingegangen.
- **Strukturtest** `tests/test_v398_speichern_baustein.py` über einen Scanner `tests/vorlagen_js.py` (Tokenizer für Strings,
  Template-Literale, Regex, Kommentare, Klammern; Jinja-Includes eingesetzt, Positionen der Vorlage für die Meldung), je Vorlage:
  (a) jede schreibende Anfrage ist der ganze Rumpf eines Pfeils ohne Parameter als zweites Argument eines abgewarteten `speichern()`
  (`await`/`return` davor oder `.then`/`.finally` danach), die Optionen mit `method` direkt im Aufruf; (b) in jeder Funktion, die
  speichert (selbst oder über eine Funktion der Seite), fragt alles danach -- Aufrufe, übergebene Funktionen, `anwenden`, `neuLaden`,
  transitiv über Funktionsnamen der Seite samt Teilvorlagen -- nur über `lesen()`/`speichern()` an; (c) "Gespeichert" in einem String nur
  hinter einem abgewarteten Speichern derselben Funktion; (d) wer den Baustein selbst aufruft, bindet ihn ein, wer nicht, nicht. Dazu der
  Scanner an Beispielen und jedes Skript jeder gerenderten Seite (als Admin und als Monteur) in node auf Syntax (`vm.Script`).
- **Klicktest-Werkzeug**: `ANTWORT_RUECKHALT` in `scripts/cdp_klicktest.py`, in jedes Dokument vor dem Anfragenzähler eingesetzt;
  `Tab.zurueckhalten(muster, methode, art="antwort"|"anfrage")`, `freigeben()`, `gehalten()`, `warte_bis_gehalten()`, `warte_auf_ruhe()`.
  Neuer Klicktest `scripts/klicktest_veraltete_antworten.py`.
- **Rechnungen über 0 € oder weniger** (`app/invoices.py::amount_block_reason()`): nur ein Storno und eine Schlussrechnung mit mindestens
  einem Abzug (`final_breakdown()` nicht leer) dürfen 0 € oder weniger lauten; jede andere -- Abschlag (wie bisher), Rechnung aus Aufwand
  (auch die abschließende) und Schlussrechnung ohne Abzüge -- wird beim Festschreiben mit 409 abgelehnt, Grund mit dem Satz "Über 0 € oder
  weniger lauten nur ein Storno und eine Schlussrechnung mit abgezogenen Rechnungen." (`NOT_ABOVE_ZERO_TEXT`), auf der Rechnungsseite statt
  "Finalisieren" (`finalize_block`). Geprüft nach der Neuberechnung unter der Sperre der Auftragszeile (wie jede Regel in
  `finalize_block_reason()`): fällt der Abzug weg, weil der Abschlag inzwischen storniert ist, gilt die Regel ohne Abzüge.

#### Festlegungen 1.8.95 (bestätigt am 13.10.2026, Vorgabe 1.8.96: 1, 2, 5, 6, 7, 10, 11, 12; 4 je Bereich; 3 für Speichern, bei Lesen gegen Lesen wird nach einem gescheiterten neueren das ältere verworfen; 8 und 9 ersetzt durch Punkt 4 der Vorgabe 1.8.96)

1. **"Speichern" = jede Anfrage mit Methode ungleich GET** in einer Vorlage, ohne Ausnahmeliste (auch Löschen, Versand, Hochladen,
   Anmelden, Abmelden).
2. **Bereich = was eine Antwort ersetzt**, Name je Seite frei; laufende Nummer je Bereich beim Absenden; unabhängige Formulare in eigenen
   Bereichen.
3. **Veraltet = eine Antwort mit kleinerer Nummer als die schon angewandte** desselben Bereichs; sie wird verworfen. Schlägt die neuere
   fehl, wird die ältere noch angewandt (sie ist dann die neueste angekommene).
4. **Speichern je Bereich nacheinander, Lesen wartet auf laufendes Speichern** -- statt eines Stands vom Server; die Antwort mit der
   höchsten Nummer kennt so alles davor, auch bei zwei Arbeitsprozessen.
5. **Die Anfrage wird beim Aufruf gebaut, nur das Senden wartet** (`fetch()` während des Aufrufs zurückgestellt); ein Pfeil, der `fetch()`
   nicht sofort erreicht, wird gemeldet (`console.error`, im Klicktest ein Fehler).
6. **"Gespeichert." und jeder Erfolgstext erst nach dem Anwenden bzw. Neuladen** (hinter `await speichern(…)`); ist das eigene Neuladen
   veraltet, gilt das schon angewandte neuere -- es kennt dieses Speichern.
7. **Antwort des Versands nicht mehr direkt übernommen** (Auftrag, Rechnung, Vertrag): nach dem Versand wird neu geladen.
8. **Lesen ohne vorheriges Speichern** (erstes Laden, Filter, Blättern) muss nicht über den Baustein; die umgestellten Seiten nutzen ihn
   dort meist trotzdem, wo dieselbe Ladefunktion auch nach dem Speichern läuft.
9. **Fehler wie bisher**: der Fehlertext der Seite bleibt; ein Fehler eines älteren Lesens kann eine neuere Anzeige noch mit einer
   Fehlermeldung überschreiben (nicht abgefangen).
10. **Strukturtest folgt Funktionen über ihren Namen** auf der Seite samt Teilvorlagen; Aufrufe über Parameter oder Tabellen
    (`WIDGETS[…]`, Rückrufe wie `onChange`) sieht er nicht -- dort gilt die Regel ohne mechanische Prüfung.
11. **Klicktest hält Antworten in der Seite zurück** (fetch-Wrapper, der Server hat die Anfrage schon bearbeitet), nicht im Netz;
    Einstellungen geprüft an den Aufgabenspalten, Mahnung auf Rechnungsseite und im Mahnwesen.
12. **Über 0 € oder weniger nur Storno und Schlussrechnung mit mindestens einem Abzug**; jede andere Rechnung, auch die abschließende
    Rechnung aus Aufwand und die Schlussrechnung ohne Abzüge, muss über 0 € liegen -- geprüft beim Festschreiben, nicht beim Anlegen;
    Altbestand bleibt, wie er ist.

#### Tests und Prüfung

- Neu `tests/test_v398_speichern_baustein.py` (319): der Baustein in node mit gestelltem fetch (16: älteres Lesen nach neuerem verworfen, in
  Reihenfolge beide angewandt, andere Bereiche unabhängig, Speichern nacheinander, andere Bereiche zusammen, Lesen wartet nur auf Speichern
  seines Bereichs, vorher abgeschicktes Lesen überschreibt die Antwort des Speicherns nicht, Rückkehr erst nach dem Neuladen, zwei Speichern
  mit Neuladen enden beim neuesten Stand, Fehler blockiert nichts, Fehlerstatus ohne Anwenden, Checklisten-Fall mit Server, der B zuerst
  bearbeitet, wartendes Speichern mit den Werten vom Klick, Pfeil ohne sofortiges fetch gemeldet, sofortiger Fehler gibt den Bereich frei,
  doppelt eingebunden); Strukturtest je Vorlage (4 × 70); Scanner an 21 Beispielen; jedes Skript jeder gerenderten Seite als Admin und als
  Monteur in node auf Syntax.
- Neu `tests/test_v398_rechnung_ueber_null.py` (12, davon 1 gegen PostgreSQL): Aufwand 0 € und negativ abgelehnt (nichts festgeschrieben,
  keine Nummer verbraucht, Grund in `finalize_block`), über 0 € geht; abschließende Rechnung aus Aufwand 0 € abgelehnt; Schlussrechnung ohne
  Abzüge 0 € abgelehnt, über 0 € geht; Schlussrechnung mit Abzügen 0 € und −1.190 € geht; Storno negativ und positiv; **Angriffstests:** API
  `/send` 409 mit dem Grund der Seite, negative Position schon 422, Menge auf 0 gesetzt und dann `/send` 409; Abzug vor dem Festschreiben
  storniert -> abgelehnt. **Gleichzeitig (PostgreSQL):** das Festschreiben der Schlussrechnung wartet auf den Storno ihres Abzugs und wird
  danach abgelehnt.
- Neu `tests/test_v398_klicktest_rueckhalt.py` (6): Rückhalter in node mit dem Anfragenzähler -- Antwort erst nach Freigabe (zählt als
  unterwegs), Anfrage erst nach Freigabe, andere URL/Methode geht durch, Freigabe in Reihenfolge; Rückhalter vor dem Zähler eingesetzt; der
  Klicktest hält auf jeder der vier verlangten Seiten eine Antwort zurück.
- Erwartungen geändert seit 1.8.95: `test_v358` (Antworten und Anhänge über zwei Übernahme-Funktionen), `test_v236` (Speichern der Mahnung
  über den Baustein), `test_v385` (zwei Rechnungen aus Aufwand mit Betrag), `test_v334::seite()` (Testseite mit dem Baustein); in
  `_mobile_header.html` steht das Einbinden vor dem Stilblock (`test_v269` liest die Struktur des Kopfs).
- Klicktest `scripts/klicktest_veraltete_antworten.py` (neu) 27/27.
- Gegenproben (Regel 24): 19 von 19 rot -- im Baustein kein Verwerfen, nicht nacheinander (der Checklisten-Fall in node war dabei zunächst
  grün, weil er A vor B beantwortete; nachgeschärft: ist B schon beim Server, bearbeitet er B zuerst), Lesen wartet nicht, Rückkehr vor dem
  Neuladen, Anfrage erst beim Senden gebaut, Fehlerstatus angewandt, keine Meldung ohne sofortiges fetch; Strukturtest mit Schreiben ohne
  Baustein (Checkliste), ungeprüftem Neuladen (Abnahme), "Gespeichert." vor dem Speichern (Rechnung), fehlendem Einbinden (Mahnwesen),
  Syntaxfehler (Finanzen); Rückhalter ohne Wirkung; Rechnungen: Regel aus, Schlussrechnung ohne Prüfung der Abzüge, Storno nicht ausgenommen;
  dazu der Klicktest mit ausgehebeltem Verwerfen (Abnahme, Mahnung, Mahnwesen, Einstellungen rot), ohne "nacheinander" (Checkliste rot) und
  ohne Warten auf das Neuladen (Texte zu früh). Jede Datei byte-genau zurück (SHA-256), kein Marker.
- Volle Suite (mit den opt-in-Tests gegen PostgreSQL, Arbeitskopie, drei Teile parallel): 4285 grün, 4 rot -- zwei Strukturtests zu
  `settings.html` (in der Arbeitskopie lag noch der alte Stand, der Umbau lief parallel), zwei in `test_v385` (Erwartung veraltet seit 1.8.95:
  Rechnung aus Aufwand über 0,00 €), angepasst, danach 36 grün. Nachlauf auf dem Endstand für alle Testdateien, die `settings.html` oder
  `inquiries.html` lesen, dazu `test_v385`, `test_v218`, `test_v328`, `test_v334`, `test_v269` und `test_v398_*`: 35 Dateien, 738 grün.
- Alle Klicktests (Regel 26): 59 von 59 wie erwartet in 12:18 min, `klicktest_veraltete_antworten` 27/27 darunter. In einem Frühlauf
  während der Umstellung war `klicktest_vertragsgrundlage` einmal rot (29/30): beim Öffnen der Kundenakte kam eine von neun Anfragen nie
  beim Server an (nicht protokolliert), die Seite wartete -- einzeln und im Endlauf grün; parallel liefen damals Suite und ein weiterer
  Klicktest.

#### Nebenbefunde (nur gemeldet)

1. **Adressimport: endlose Anfragen bei gefülltem Suchfeld** (schon vor 1.8.95): `renderWorklist()` ruft bei Suchtext `loadWorklist(q)` auf,
   das wieder `renderWorklist()` -- solange etwas im Suchfeld steht, gehen ohne Ende Anfragen hinaus (`address_import.html`).
2. **Auftrag nach Aufwand ohne Betrag** (Folge von Punkt 2): eine abschließende Rechnung aus Aufwand über 0,00 € geht nicht mehr durch;
   einen anderen Weg, so einen Auftrag "vollständig abgerechnet" zu schließen, gibt es nicht.
3. **Erfolgstexte, die nie zu sehen sind** (schon vorher): "Benutzer aktualisiert./angelegt." (`users.html`, `cancelEdit()` leert sofort),
   "Titel gespeichert." im Angebots-Editor (`resetSectionEditor()`).
4. **Angebots-Editor, zwei schnelle Inline-Änderungen derselben Position** (schon vorher, Thema Regel 22): `saveInlineField` baut den Body
   aus dem gemerkten `quote.items` -- die zweite schreibt den alten Wert der ersten zurück.
5. **Lesen ohne Baustein, wo vorher nichts gespeichert wird** (Festlegung 8): Monatswechsel im Stundenzettel (`field_timesheet.html`),
   Dachtyp-Wechsel der Schichten (`roof_area.html`), erstes Laden u. a. der Einstellungen -- dort kann eine späte, ältere Antwort noch eine
   neuere überschreiben.
6. **Zwei Bereiche teilen einen Stand** (selten): `checklist_template.html` setzt `version` aus den Antworten von "vorlage" und "fassung";
   die Kundenakte lädt Dokumente in `load()` (Bereich "kunde") und getrennt (Bereich "dokumente"); E-Mail-Vorlagen in den Einstellungen
   setzen die Felder der Mahnstufe ohne Anfrage, eine späte Antwort eines vorher gewählten Dokumenttyps kann sie überschreiben.
7. **Dashboard nach dem Speichern des Layouts**: die Widgets laden über eine Tabelle (`WIDGETS[…]`), die der Strukturtest nicht verfolgt
   (Festlegung 10); unschädlich, die alten Container sind weg.
8. **Einsatzbericht**: die Unterschrift (Bereich `berichte`) wartet nicht auf ein laufendes Speichern eines Prüfpunkts (Bereich
   `pruefpunkte-<Bericht>`) -- wie vorher.
9. **Kundenakte**: `allProjects` ist eine nicht deklarierte, implizit globale Variable (schon vorher).
10. **Windows-Pfadlänge in Klicktests**: `klicktest_maengel_monteur` scheitert beim Befüllen, wenn der Ausgabeordner tief liegt (Pfad über
    260 Zeichen unter `acceptance_documents/maengel/…`); mit kurzem `--ausgabe` grün.

## Zeitlimit, abschließende Aktionen, Teil-Updates, Lesen über den Baustein (1.8.96, 1.8.97)

### Vorgabe vom 13.10.2026 (übernommen wie gegeben)

Vorweg zu 1.8.95: Festlegungen 1, 2, 5, 6, 7, 10, 11, 12 bestätigt. 4 bestätigt je Bereich; Regel 29 sagt das ausdrücklich. 3 bestätigt
für Speichern; bei Lesen gegen Lesen wird nach einem gescheiterten neueren das ältere verworfen. 8 und 9 ersetzt diese Runde.

1. Zeitlimit im Baustein: Ohne Antwort nach 60 s wird die Anfrage abgebrochen. Der Bereich meldet, dass unklar ist, ob gespeichert wurde,
   und bittet um Neuladen und Prüfen. Wartende Speichervorgänge des Bereichs werden nicht gesendet, die Knöpfe werden frei. Solange etwas
   läuft oder wartet, warnt die Seite beim Verlassen.
2. Abschließende Aktionen (Unterschrift, Festschreiben, Versand u. ä.) warten auf alles laufende Speichern der ganzen Seite und laufen
   nicht, wenn eines davon scheitert. Strukturtest über die Liste dieser Aufrufe. Klicktest: Speichern eines Prüfpunkts zurückhalten,
   dann unterschreiben.
3. Teil-Update nach Regel 22 statt gemerkter Werte, zuerst Geld: Angebots-Editor saveInlineField und saveCalc, order.html quickItem,
   incoming_invoices.html markPaidNow; dann settings.html saveEmailTemplate, toggleDocumentLayoutBlock, saveContinuationHeaderPosition,
   planning.html dropSlot, Layout-Drag-and-drop im Angebots-Editor, recurring_costs.html toggleActive. Gleichzeitigkeit gegen PostgreSQL.
4. Strukturtest: kein fetch() außerhalb von _speichern.html, Ausnahmeliste darf nur kürzer werden. Sofort über lesen(): jedes Lesen,
   das ein Formular füllt, aus dem gespeichert werden kann, mindestens E-Mail-Vorlagen, Dokumente der Kundenakte, Checklisten-Vorlage,
   Dachtyp-Wechsel, Monatswechsel im Stundenzettel. Veraltete Fehler verwirft der Baustein wie veraltete Erfolge.
5. Klicktests für Anmelden (Formular und Seitenleiste) und Abmelden (beide Kopfzeilen). Das Klicktest-Werkzeug zeichnet die
   Netzwerkereignisse des Browsers auf und nennt beim Scheitern offene Anfragen mit Adresse, Startzeit und ob sie gesendet wurden.
6. Regel 29 nachziehen.

Ins Archiv (2d und Rüge, nur festhalten, nicht bauen): Gewährleistungs- und Kulanzstunden werden auf den ursprünglichen Auftrag
gebucht. Eine Zeitbuchung lässt sich einem Mangel zuordnen oder als Kulanz kennzeichnen; sie ist dann nie abrechenbar und erscheint in
der Nachkalkulation getrennt als „davon Mängelbeseitigung / Kulanz“. Ein Auftrag mit offenem, freigegebenem Mangel bleibt für
Plantafel, /mobil und Zeiterfassung wählbar, auch wenn er abgeschlossen ist. Stunden nach der Schlussrechnung ohne diese Zuordnung zeigt
das Backoffice als „nach Schlussrechnung, nicht abrechenbar“ zum Einordnen. Auftrag ohne Rechnung: „Abschließen ohne Rechnung“ nur
Büro, nur solange keine Rechnung existiert, mit Pflichtbegründung und Hinweis auf nicht abgerechnete Stunden (Parkplatz vor dem
Echtbetrieb).

Angriffstests mit Gegenprobe. Eigene Festlegungen mit „Bitte bestätigen“, je in einer Zeile. Nebenbefunde nur melden. Wird der Umfang
zu groß: nach Punkt 3 committen und den Rest auflisten. Commit nach Regel 13, Bericht kurz.

(Festgehalten: die Sätze zu 2d und Rüge unter "Entscheidungen Rechnungen", Ergänzung nach Nachfrage 10; „Abschließen ohne Rechnung“
stand schon im "Parkplatz vor dem Echtbetrieb".)

### Umsetzung 1.8.96: Zeitlimit, abschließende Aktionen (Punkte 1 und 2), Teil-Updates (Punkt 3)

#### Was gebaut ist

- **Zeitlimit im Baustein** (`app/templates/_speichern.html`, Punkt 1): jedes Speichern bekommt beim Bauen ein Abbruchsignal
  (`AbortController`, über die fetch-Fassung, die schon das Senden zurückstellt). Kommt 60 s nach dem Senden keine Antwort, bricht der
  Baustein die Anfrage ab -- auch wenn die Anfrage das Signal nicht weiterreicht (Rennen gegen den Zeitgeber, eine späte Antwort wird
  nie angewandt). Der Bereich ist danach "unklar": `speichern()` endet mit dem Fehler "Keine Antwort vom Server nach 60 Sekunden – unklar,
  ob gespeichert wurde. Bitte die Seite neu laden und prüfen." (`e.dkBaustein === 'unklar'`), die Seite zeigt ihn wie jeden Fehler und gibt
  ihre Knöpfe frei; zusätzlich steht oben auf der Seite ein Hinweis mit diesem Text und "Seite neu laden" (`#dkSpeichernUnklar`).
  Wartende und neue Speichervorgänge des unklaren Bereichs gehen nicht hinaus ("Nicht gesendet: ein Speichern davor blieb ohne Antwort –
  …", `'nicht-gesendet'`); Lesen und andere Bereiche laufen weiter. Solange ein Speichern läuft oder wartet, warnt der Browser beim
  Verlassen (`beforeunload`, einmal je Seite). Für Klicktests lässt sich das Zeitlimit vor dem Laden über `window.__dkZeitlimit` kürzen.
- **`abschliessen(bereich, anfrage, optionen)`** (Punkt 2): wie `speichern()`, die Anfrage wird beim Klick gebaut, gesendet aber erst,
  wenn jedes Speichern der ganzen Seite, das beim Klick lief oder wartete, zurück ist (`window.__dkSpeichern`, je Speichern ein Ergebnis).
  Ist eines davon gescheitert (Fehler oder Fehlerstatus) oder ist ein Bereich der Seite unklar, läuft die Aktion nicht: Fehler "Nicht
  ausgeführt: ein Speichern auf der Seite ist gescheitert (<Grund>). Bitte prüfen und erneut versuchen." bzw. "… unklar …"
  (`'abschluss'`), nichts gesendet. Eingaben, die `_debounce.html` noch zurückhält, werden vorher gespeichert (`window.__dkEntprellt`).
- **38 abschließende Aufrufe umgestellt**, Liste `ABSCHLIESSEND` in `tests/test_v399_abschliessen.py`: Unterschrift (Checkliste über die
  neue `uploadSignature()`, Einsatzbericht, Vertrag auf dem Gerät und als Papier-Scan), Festschreiben (Rechnung festschreiben und
  versenden, Mahnung auf Rechnungsseite und im Mahnwesen, Vertrag, Brief zur Anzeige), Abschluss und "gegenstandslos" der Checkliste,
  Unterschrift verwerfen, Versand (alle Dokumente über `postEmailDispatch`), Zustellung nachtragen, Versandergebnis, hängenden Versand
  klären, Abnahme (von Hand, aus dem Protokoll an Auftrag und Protokoll, verwerfen), Mangel (erfassen, Haltung/Status/Freigabe/Verwerfen,
  im Protokoll erfassen und verwerfen, in /mobil "beseitigt" melden), Buchungen (Zahlung, Rest zuordnen, Erstattung an Rechnung und
  Kundenakte, Zuordnung gegenbuchen, Zahlung zurücknehmen, Nebenforderung gegenbuchen, Verzugsbeginn bestätigen und verwerfen), Storno,
  Beauftragen und Abgleich (Angebot -> Auftrag in beiden Richtungen). Der Versand reicht die Meldungen des Bausteins wörtlich durch und sagt
  nach dem Zeitlimit "neu laden und im Versandverlauf prüfen" statt "erneut klicken".
- **Strukturtest** (`tests/test_v399_abschliessen.py`): je Vorlage gehen genau die Aufrufe der Liste über `abschliessen()`, alle anderen
  über `speichern()`; jede schreibende Anfrage, deren Adresse nach einer abschließenden Aktion klingt (`/sign`, `/send`, `/complete`,
  `/freeze`, `/storno`, `/void`, `/discard…`, `/reverse`, `/refunds`, `/allocations`, `/payments`, `/acceptances`, `/defects`, `/remedied`,
  `/outcome`, `/manual`, `/resolve`, `/convert-to-order`, `/sync-source-quote`, `/default-start`, `/notice-letters`), steht in der Liste oder
  mit Grund in `NICHT_ABSCHLIESSEND` (zwei: Verwerfen der Import-Vorschau und einer Zeile der Import-Arbeitsliste); jeder Eintrag beider
  Listen trifft eine schreibende Anfrage. Eine Adresse in einer Variablen wird über ihre letzte Zuweisung davor aufgelöst.
- **Scanner** (`tests/vorlagen_js.py`): `abschliessen()` zählt wie `speichern()`; den Funktionen des Bausteins selbst folgt er nicht mehr
  (sonst hielt er einen Namen im Baustein für eine gleichnamige Funktion der Seite).
- **Klicktest** `scripts/klicktest_abschliessen.py` (neu): Einsatzbericht mit Pflicht-Prüfpunkt -- Speichern zurückhalten, unterschreiben:
  Unterschrift nicht gesendet, Warnung beim Verlassen, nach der Freigabe erst Prüfpunkt, dann Unterschrift, unterschrieben mit dem Wert;
  Prüfpunkt anderswo gelöscht -> Speichern scheitert, Unterschrift "Nicht ausgeführt", Bericht bleibt Entwurf; Zeitlimit 2 s mit
  zurückgehaltener Antwort -> Meldung, Hinweis mit "Seite neu laden", Unterschrift abgelehnt, nach dem Neuladen der gespeicherte Wert.

- **Teil-Updates statt gemerkter Werte** (Punkt 3, `docs/archiv/teil-updates.md`, Nebenbefund 3 der Durchsicht 1.8.25): jede der
  genannten Stellen schickt nur, was sie bearbeitet; der Endpunkt ist ein Teil-Update nach Regel 22 (Schema von `PartialUpdate` mit
  `NOT_NULL`, Handler `model_dump(exclude_unset=True)`, Geschäftsfunktion ändert nur Übergebenes), Prüfungen über mehrere Felder laufen auf
  gespeichertem Stand + gesendeten Werten, und wo gelesen-geändert-geschrieben wird, unter einer Zeilensperre. Zuerst Geld:
  - Angebots-Editor inline (`saveInlineField`): `PUT /api/quotes/{id}/items/{item_id}`, `QuoteItemUpdate(PartialUpdate)`; schickt
    `{quantity}` bzw. `{unit}` -- zwei schnelle Änderungen derselben Position schreiben nicht mehr den alten Wert der ersten zurück
    (Nebenbefund 4 aus 1.8.95).
  - Kalkulation (`saveCalc`): `PUT …/calculation`, `QuoteItemCalculationUpdate`/`QuoteItemMaterialCalculationUpdate(PartialUpdate)` (fehlt
    `materials`, bleiben die Zeilen; je Zeile nur die gesendeten Werte); unter der Sperre der Angebotsposition (der EP folgt aus der ganzen
    Kalkulation); `ensure_quote_item_calculation()` ohne eigenen Commit. Das Formular schickt seine Felder ohne die Preiseinheit.
  - Drag-and-drop auf einen Titel (`wireDragDrop`): `PUT …/layout`, `QuoteItemLayoutUpdate(PartialUpdate)`, `set_item_layout(**changes)`;
    schickt nur `{section_id}`.
  - Auftragsseite inline (`quickItem`): `PUT /api/orders/{id}/items/{item_id}`, `OrderItemUpdate(PartialUpdate)`; die Sperren am Auftrag
    (`item_change_reason()`, Sperre der Auftragszeile) prüfen die gesendeten Felder; schickt `{[feld]: wert}`.
  - Eingangsrechnung "als bezahlt markieren" (`markPaidNow`): `PUT /api/incoming-invoices/{id}`, eigenes `IncomingInvoiceUpdate(PartialUpdate)`;
    `update_invoice()` unter der Sperre der Zeile, ohne `items` bleiben die Positionen (Summe gegen die gespeicherten); schickt
    `{payment_status, payment_date}` statt der ganzen Rechnung samt Positionen.
  Dann: Bausteine in den Einstellungen (`toggleDocumentLayoutBlock` `{visible}`, `saveContinuationHeaderPosition` `{y_mm}`;
  `DocumentLayoutBlockUpdate(PartialUpdate)`, `update_layout_block(**changes)`), Plantafel verschieben (`dropSlot` `{team_id, start_date,
  end_date}`; `PlanningSlotUpdate(PartialUpdate)`, `update_slot(**changes)` unter der Sperre der Arbeitsvorbereitung, Ende vor Beginn auf
  dem zusammengeführten Stand), Kostenposten aktivieren/deaktivieren (`toggleActive` `{active}`; eigenes `RecurringCostUpdate(PartialUpdate)`,
  `update_cost()` unter der Sperre der Zeile, Jahresbetrag aus dem Ergebnis). Die E-Mail-Vorlage einer Mahnstufe (`saveEmailTemplate`) ist
  seit 1.8.80 Teil-Update -- nichts gebaut, mit einem Test abgesichert. Die Löschwege derselben Zeilen sperren zuerst dieselbe Zeile
  (`delete_quote_item()`, `delete_invoice()`, `delete_slot()`): mit den neuen Sperren gab es unter PostgreSQL sonst Deadlocks. Strukturtest
  `tests/test_v329_update_handler_struktur.py`: acht Routen aus `BEKANNT` gestrichen (70 -> 62) und in `REPARIERT_SPAETER` eingetragen.
  Gebaut von einem Helfer in eigener Arbeitskopie, geprüft und zusammengeführt.

#### Festlegungen 1.8.96 (Bitte bestätigen)

1. **Zeitlimit 60 s ab dem Senden**, für jedes Speichern und jede abschließende Aktion (auch Hochladen und Versand), nicht für Lesen.
2. **Unklar bis zum Neuladen**: nach dem Zeitlimit gehen wartende und neue Speichervorgänge dieses Bereichs nicht hinaus; Lesen und andere
   Bereiche laufen weiter.
3. **Meldung doppelt**: als Fehler des Bereichs (die Seite zeigt ihn an ihrer Stelle) und als Hinweis oben auf der Seite mit "Seite neu
   laden" -- auch für Speichern im Hintergrund, das Fehler still schluckt.
4. **"Knöpfe frei" = speichern() endet mit einem Fehler**; die Seite gibt ihre Knöpfe frei wie bei jedem anderen Fehler, der Baustein
   sperrt und entsperrt selbst keine Knöpfe.
5. **Warnung beim Verlassen**, solange ein Speichern (auch eine abschließende Aktion) läuft oder wartet; Lesen zählt nicht.
6. **Abschließend = macht etwas unveränderlich oder gibt es hinaus** (Liste oben, 38 Aufrufe); Löschen, Entwürfe anlegen, Einstellungen und
   Stammdaten nicht.
7. **Gewartet wird auf jedes Speichern der Seite, das beim Klick läuft oder wartet**; was danach beginnt, nicht. Ein schon vor dem Klick
   gescheitertes Speichern hindert nicht (es war schon gemeldet).
8. **Gescheitert = Fehler oder Fehlerstatus**, auch ein selbst abgelehntes abschließendes; die Meldung nennt den ersten Grund.
9. **Keine abschließende Aktion, solange ein Bereich der Seite unklar ist** -- auch wenn das Zeitlimit vor dem Klick lag.
10. **Zurückgehaltene Eingaben (`_debounce.html`) laufen vor einer abschließenden Aktion sofort**, auch eine zurückgehaltene Suche.
11. **Strukturtest über Liste und Adressmuster**: Liste je Vorlage und Funktion; eine schreibende Anfrage, deren Adresse nach einer
    abschließenden Aktion klingt, muss eingeordnet sein; eine Adresse als Parameter (Versand, Mängel) sieht das Muster nicht -- dort hilft
    nur die Liste.
12. **Versand nach dem Zeitlimit: neu laden und im Versandverlauf prüfen** statt "erneut klicken" (der Platz nimmt bis zum Neuladen nichts
    mehr an; ein neuer Versand danach hat einen neuen Versandschlüssel).
13. **Zeitlimit im Klicktest über `window.__dkZeitlimit`**, vor dem Laden gesetzt; keine Seite setzt es.
14. **Formulare schicken weiter alle ihre Felder** (Positions-Formular, Auftrags-Dialog, Bearbeiten-Formulare, Plantafel-Dialog,
    Kalkulationsformular); nur Werte, die das Formular nicht zeigt (Preiseinheit), entfallen.
15. **Verschieben auf der Plantafel schickt Team, Beginn und Ende** (Ende aus Beginn + der beim Laden angezeigten Dauer); Status, Notiz,
    Planstunden, Anfahrt bleiben.
16. **Ausdrückliches null für Team, Planstunden und Anfahrt am Planeinsatz ist 422** (bis 1.8.95 hieß null "unverändert"; weglassen heißt
    jetzt unverändert, kein Aufrufer schickt null).
17. **"Als bezahlt markieren" setzt Status und Zahlungsdatum heute ohne Vergleich mit dem Stand beim Laden** -- der letzte Klick gewinnt,
    wie bisher.
18. **"Aktivieren"/"Deaktivieren" schickt den Zielzustand, den der Knopf zeigt**; der Server schaltet nicht um.
19. **Zeilensperre nur, wo gelesen-geändert-geschrieben wird**: Kalkulation (Angebotsposition), Eingangsrechnung, Kostenposten, Planeinsatz
    (Arbeitsvorbereitung); Angebotsposition, Layout und Baustein ohne Sperre (nichts abgeleitet); Auftragsposition wie bisher unter der Sperre
    der Auftragszeile.
20. **Löschen sperrt zuerst dieselbe Zeile wie das Speichern** (Angebotsposition, Eingangsrechnung, Arbeitsvorbereitung des Einsatzes).
21. **Eine Projektkalkulation aus der Vorschau bleibt bei einer Ablehnung nicht mehr stehen** (kein eigener Commit beim Anlegen).
22. **`update_invoice()`/`update_cost()` übernehmen nur bekannte Schlüssel**; ein fehlender Schlüssel heißt für direkte Aufrufer
    "unverändert" statt Vorgabewert.
23. **Zahlungsdatum ohne gesendeten Status zählt nur, wenn der zusammengeführte Status "bezahlt" ist**, sonst wird es geleert.
24. **`content` am Layout-Baustein weiter angenommen und nicht geschrieben** (Nebenbefund 4 aus 1.8.25 bleibt nur gemeldet).

#### Tests und Prüfung

- Neu `tests/test_v399_abschliessen.py` (162): der Baustein in node mit kurzem Zeitlimit -- Abbruch nach dem Zeitlimit mit Meldung
  "unklar", späte Antwort nie angewandt (auch wenn die Anfrage das Signal nicht weiterreicht), Antwort in der Zeit ohne Abbruch, wartende
  und neue Speichervorgänge des Bereichs nicht gesendet, anderer Bereich und Lesen weiter, Hinweis oben mit "Seite neu laden", Warnung
  beim Verlassen solange etwas läuft oder wartet (nicht beim Lesen), einmal je Seite trotz doppeltem Einbinden; `abschliessen()` wartet
  auf laufendes und wartendes Speichern anderer Bereiche, läuft nicht nach einem gescheiterten (auch Fehlerstatus 409) und nennt den
  Grund, ein vor dem Klick gescheitertes hindert nicht, ein nach dem Klick begonnenes wird nicht abgewartet, unklarer Bereich lehnt ab,
  zurückgehaltene Eingabe aus `_debounce.html` geht vorher hinaus (und nicht noch einmal), im selben Bereich wie Speichern, zwei
  abschließende nach einem gescheiterten beide abgelehnt; Versand nennt "nicht ausgeführt", Zeitlimit und Netzfehler je mit eigenem Text;
  der Strukturtest je Vorlage (2 × 70: nur die Liste über `abschliessen()`, jede Adresse, die abschließend klingt, eingeordnet), jeder
  Listeneintrag trifft, Unterschrift der Checkliste über die eigene Funktion.
- Neu `tests/test_v399_teil_updates_geld.py` (25, davon 7 gegen PostgreSQL) und `tests/test_v399_teil_updates_rest.py` (13, davon 3 gegen
  PostgreSQL): die echte Funktion der Vorlage in node (mit `_speichern.html`) auf dem Stand beim Laden, danach ein anderswo geänderter
  Wert, der genaue Body und der echte Server, der den geänderten Wert stehen lässt (10 Stellen, auch zwei schnelle Änderungen derselben
  Position); Teil-Updates lassen die übrige Zeile stehen, abgeleitete Werte passen; **Angriffstests:** null in jedem Pflichtfeld 422 ohne
  Speichern, zusammen mit dem gespeicherten Stand ungültig 422 ohne Speichern (zweite Zuordnung, Summe der Positionen, Ende vor Beginn,
  Anfahrt), gesperrte Felder am Auftrag per Teil-Update weiter 409, fremde IDs abgelehnt; **gleichzeitig gegen PostgreSQL** je zwei
  Teil-Updates derselben Zeile (Angebotsposition, Kalkulation mit passendem EP, Auftragsposition, Eingangsrechnung, Kostenposten,
  Planeinsatz) und drei Deadlock-Tests (Speichern gegen Löschen).
- Geändert: `tests/test_v398_speichern_baustein.py` (Ablauf in node beendet sich sofort -- ein offener Zeitgeber hielt node sonst bis zu
  60 s; Zeitlimit und Vorspann einstellbar), `tests/vorlagen_js.py` (`abschliessen()` wie `speichern()`, Funktionen des Bausteins
  undurchsichtig), `tests/test_v329_update_handler_struktur.py` (acht Routen von `BEKANNT` nach `REPARIERT_SPAETER`).
- Klicktest `scripts/klicktest_abschliessen.py` (neu) 19/19.
- Gegenproben (Regel 24): 34 von 34 rot. Punkte 1 und 2 (14): kein Zeitlimit, wartende trotz unklar gesendet, keine Warnung beim
  Verlassen, kein Hinweis, `abschliessen()` wartet nicht (dazu der Klicktest: Unterschrift vor dem Prüfpunkt, Bericht ohne den
  Pflicht-Prüfpunkt), Scheitern ignoriert, Unklar ignoriert, Fehlerstatus als Erfolg, zurückgehaltene Eingabe nicht ausgeführt, Entprellen
  ohne Eintrag, Einsatzbericht über `speichern()` (Strukturtest und Klicktest: unterschrieben trotz Zeitlimit), Unterschrift der
  Checkliste über `speichern()`, Versand übersetzt die Meldung, Rechnungsversand aus der Liste gestrichen. Punkt 3 (20): alter Server mit
  neuer Oberfläche 31 von 38 rot, alte Oberfläche 11 von 38 (genau die Oberflächen-Tests), alte Oberfläche auf Datenebene 10 von 11,
  `NOT_NULL` leer 5 von 5, dazu 16 gezielte je 1/1 (sechs ohne Sperre, drei Löschen ohne Sperre, drei Teilmengen aus veraltetem Stand,
  Summe, Zuordnung, Datum, Commit, Auftragssperre, Mahnstufe). Jede Datei byte-genau zurück (SHA-256), kein Marker.
- Volle Suite (mit den Tests gegen PostgreSQL, Arbeitskopie, drei Teile parallel): **4489 grün, 0 rot**.
- Alle Klicktests (Regel 26, Arbeitskopie des Stands 1.8.96): 60 von 60 wie erwartet in 13:26 min, `klicktest_abschliessen` 19/19 darunter.

#### Nebenbefunde (nur gemeldet)

1. **60 s auch beim Hochladen** (Festlegung 1): ein großes Foto über eine langsame Verbindung (z. B. 10 MB bei 1 Mbit/s, rund 80 s) endet
   als "unklar", obwohl es noch läuft -- danach nimmt der Bereich bis zum Neuladen nichts mehr an.
2. **Speichern im Hintergrund schluckt Fehler** (Outlook-Abgleich im Kalender, Layout des Dashboards): dort zeigt nur der Hinweis oben das
   Zeitlimit.
3. **Checkliste warnt doppelt beim Verlassen** (eigene Warnung für ihre Zeitgeber und laufenden Anfragen neben der des Bausteins) --
   harmlos.
4. **Einsatzbericht**: ein Prüfpunkt meldet seinen Fehler über `alert()` (wie bisher); eine Eingabe in einem entprellten Feld geht vor der
   Unterschrift zweimal hinaus (beim Verlassen des Felds und aus `_debounce.html`) -- gleicher Wert, harmlos.
5. **Angebots-Editor, Umsortieren per Drag-and-drop auf eine Position** (`moveItemBefore`, `POST /api/quotes/{id}/reorder`): schickt
   `section_id` aller Positionen des Zieltitels aus dem Stand beim Laden (gemerkter Wert, POST, nicht Teil des Auftrags).
6. **Neuer Planeinsatz gleicht Beginn/Ende der Arbeitsvorbereitung ohne Sperre ab** (`create_slot()`): gleichzeitig mit dem Verschieben
   eines anderen Einsatzes derselben Vorbereitung kann Beginn/Ende der Vorbereitung veralten.
7. **Unbekanntes oder inaktives Team am Planeinsatz ist 404** (der Router macht aus jedem Text mit "nicht gefunden" 404), eher 422.
8. **`QuoteItemUpdate` ohne Längengrenzen** (`unit` 50, `position_type` 30, `gaeb_oz` 100): unter PostgreSQL ein zu langer Wert 500 statt 422
   (wie vorher; `OrderItemUpdate` hat sie).
9. **`content` am Layout-Baustein** wird angenommen und nie geschrieben (Nebenbefund 4 aus 1.8.25, unverändert).
10. **Zweimal gleichzeitig denselben Planeinsatz entfernen**: die zweite endet mit `StaleDataError` (500) statt 404 (wie vorher).
11. **Zahl der Altfälle in der Doku war falsch**: Regel 22 nannte 72, `BEKANNT` hatte vor dieser Runde 70 (jetzt 62) -- in CLAUDE.md
    nachgezogen.

### Umsetzung 1.8.97: Lesen über den Baustein (Punkt 4), Anmelden und Abmelden im Klicktest, Netzwerkprotokoll (Punkt 5), Regel 29 (Punkt 6)

#### Was gebaut ist

- **Veraltete Fehler** (`app/templates/_speichern.html`, `lesen()`): ein Fehler eines Lesens, das inzwischen veraltet ist, kommt nicht mehr
  an -- `lesen()` gibt false zurück wie bei einer veralteten Antwort. Ein Fehler des neuesten Lesens zählt wie eine angewandte Antwort:
  ein älteres Lesen, das danach ankommt, wird verworfen (Bestätigung zu Festlegung 1.8.95 Nr. 3: Lesen gegen Lesen). Beim Speichern bleibt
  es bei Festlegung 1.8.95 Nr. 3 (scheitert ein Speichern, gilt die zuletzt angekommene Antwort).
- **Keine Anfrage außerhalb des Bausteins** (Strukturtest `tests/test_v400_lesen_ueber_baustein.py`, Scanner
  `tests/vorlagen_js.py::anfragen_ausserhalb()`): jede Stelle, an der eine Seite außerhalb von `lesen()`/`speichern()`/`abschliessen()`
  anfragt -- fetch direkt oder über einen Anfrage-Helfer der Seite (eine Funktion, die selbst fetch ruft, z. B. `api()`) --, ist ein Fund
  (Datei, Funktion, Ziel). Eine Funktion, die nur innerhalb des Anfrage-Arguments erreicht wird, ist frei; ein Aufruf aus dem HTML
  (`on…="name(…)"`, auch in Template-Literalen) zählt als Verweis außerhalb. Vorher 101 Funde; **64 umgestellt**, 37 stehen in `AUSNAHMEN`,
  jede mit einem von vier Gründen ohne Formular: nur Anzeige (Dashboard-Widgets, Finanzen, Verlauf, Changelog, Befunde, Hinweise
  "offene Bedenken" und Gewährleistungen, /mobil-Übersichten u. ä.), Suche (Kopfzeilen, Suchergebnisse, Material- und Beteiligtensuche),
  Anmeldestatus (Seitenleiste, Stundenzettel), Prüfung ohne Formular (Modulstatus, Ablage prüfen, Fassung prüfen, Knopf "Projekt anlegen").
  Die Liste darf nur kürzer werden: ein neuer Fund ist rot, ein Eintrag ohne Fund ebenso.
- **Jedes Lesen, das ein Formular füllt, über `lesen()`**, im Bereich des Speicherns, dessen Antwort denselben Stand ersetzt -- so wartet
  das erste Laden auf ein laufendes Speichern und überschreibt nie eine neuere Antwort. Die fünf ausdrücklich verlangten Stellen:
  - **E-Mail-Vorlagen** (Einstellungen): beide Arten über `lesen('emailvorlagen')`; die Mahnstufe kommt frisch vom Server
    (`/api/reminder-levels`) statt aus dem gemerkten Stand, ihr Speichern läuft im Bereich des Formulars -- die zuletzt gewählte Art gilt
    (Nebenbefund 6 aus 1.8.95).
  - **Dokumente der Kundenakte**: `load()` lädt die Dokumente nicht mehr selbst (Bereich 'kunde'), sondern über `loadDocuments()` im
    Bereich 'dokumente' -- vorher setzten beide Bereiche `customerDocuments` (Nebenbefund 6 aus 1.8.95).
  - **Checklisten-Vorlage**: ein Bereich 'vorlage' für Vorlage und Fassung (beide setzen `version`), erstes Laden darüber, Ansicht einer alten
    Fassung im Bereich 'fassungsansicht' (Nebenbefund 6 aus 1.8.95).
  - **Dachtyp-Wechsel** (Dachfläche): `loadLayers()` über `lesen('schichten')` wie das Speichern einer Schicht, auch der Wechsel auf "keine
    Auswahl" (ein Lesen ohne Anfrage, damit eine späte Antwort des vorher gewählten Dachtyps verworfen wird); erstes Laden im Bereich
    'dachflaeche' (Nebenbefund 5 aus 1.8.95).
  - **Monatswechsel im Stundenzettel**: `loadMonth()` über `lesen('monat')` (Nebenbefund 5 aus 1.8.95).
  Dazu die Einstellungen ganz: `load()` lädt jeden Abschnitt im Bereich, in dem er speichert (13 Abschnitte, ein nicht geladener bekommt wie
  bisher seinen leeren Stand und steht in der Meldung), ebenso Mobil, Dokumentlayout (Bausteine, Briefpapier, Ränder, Stand der Umstellung)
  und Design. Die übrigen 33 Vorlagen haben drei Helfer nach einer gemeinsamen Anleitung umgestellt (Auftrag, Rechnung, Mahnwesen,
  Angebot, Eingangsrechnungen, Kostenposten, Projektmappe und -formular, Abnahme-, Mängel- und Versand-Teilvorlagen; Kalender, Plantafel,
  Zeiterfassung Büro und mobil, Backoffice, Aufgaben, Arbeitsvorbereitung, Wartungsverträge, Einsatzbericht, Leistung; Checklisten-Abschnitt,
  Adressimport, Checklisten- und Prüfvorlagen, Dashboard-Layout, Anfragen, Stammsatz-Formular, Betriebsmittel, Objekt), der Strukturtest
  ist das Abnahmekriterium; ihre Berichte sind in die Festlegungen und Nebenbefunde eingegangen. Dialoge, die beim Öffnen Optionen laden,
  haben je einen eigenen Bereich (Abnahme, Mangel, Zahlung, Abwesenheit, Beteiligter, Buchung).
- **Angebots-Editor, Kalkulation in eigenem Bereich** 'kalkulation' (Laden beim Öffnen einer Position und `saveCalc`): im Bereich
  'angebot' verwarfen sich das Laden der Kalkulation und das Neuladen des LV gegenseitig (beim Umbau gefunden); eine Position ohne
  Kalkulation liest ebenfalls über den Bereich -- eine späte Kalkulation der vorher gewählten Position wird verworfen, statt den EP der neuen
  zu setzen (vorher schon so).
- **Doppelklick: dieselbe Anfrage nur einmal** (`_speichern.html`, gefunden mit dem neuen Klicktest Anmelden): seit 1.8.96 warnt die
  Seite beim Verlassen, solange ein Speichern wartet -- nach einem Doppelklick auf "Anmelden" (oder "… erstellen" mit Weiterleitung) wartete
  die eingereihte zweite, gleiche Anfrage noch, als die erste weiterleitete, und Chrome hielt die Seite mit "Seite verlassen?" fest (im
  Gesamtlauf blieb `klicktest_anmelden` bis zum Zeitlimit hängen). Jetzt geht dieselbe Anfrage (Methode, Adresse, Body als Text) nicht ein
  zweites Mal hinaus, solange die erste im Bereich wartet oder unterwegs ist: sie bekommt deren Ergebnis (eine fetch-Antwort als eigene
  Kopie, ein Fehler ebenso) und zählt nicht als wartend. Ein anderer Body oder eine Datei (FormData) ist nie dieselbe Anfrage; nach der
  Antwort geht dieselbe Anfrage wieder normal hinaus. Damit läuft auch eine doppelt geklickte abschließende Aktion nur einmal, und ein
  Doppelklick mit falschem Passwort zählt nur einen Fehlversuch.
- **Netzwerkprotokoll im Klicktest-Werkzeug** (`scripts/cdp_klicktest.py`, `Netzprotokoll`, je Tab `tab.netz`; Punkt 5): je Anfrage Adresse,
  Methode, Start, gesendet (`requestWillBeSentExtraInfo` oder schon ein Antwort-Kopf), Antwort-Kopf, fertig oder fehlgeschlagen mit
  `errorText`. Beim Scheitern -- Abweichung in `pruefe()`, Seite nicht bereit, abgebrochener Warte-Helfer, abgelaufenes `warten()` (Zeile mit
  "--"; `melden=False` für eine gewollte Pause) und am Ende eines nicht erfolgreichen Laufs -- druckt es die offenen Anfragen samt Startzeit
  und "gesendet ja/nein", die beim Dokumentwechsel offen gebliebenen, die fehlgeschlagenen und den Anfragenzähler der Seite, wenn er abweicht
  (je Abschnitt höchstens 8). Neu "im Netz anhalten" (CDP Fetch, Stufe Request: begonnen, nicht gesendet), `warten()` übersteht eine
  Navigation.
- **Klicktest `scripts/klicktest_anmelden.py`** (Punkt 5): Formular mit falschem und richtigem Passwort (Weiterleitung auf `next`, Cookie
  httpOnly und SameSite=Lax), Doppelklick nicht parallel, Admin bis zum zweiten Faktor, Abmelden über die Kopfzeile im Büro und in /mobil
  (Abmeldung im Netz angehalten: die Seite bleibt, bis die Antwort da ist; danach gesendet, 200, Navigation erst danach, Cookies weg, API 401),
  Anmelden über die Seitenleiste (nachgestellt, siehe Festlegung 1.8.97 Nr. 27 und Nebenbefund 5), serverseitiges `next` gegen fremde
  Adressen. Gefundene Lücken stehen als `BEFUND`-Zeilen da und zählen nicht als Prüfung.
- **`klicktest_alle.py` ungepuffert** (Festlegung Nr. 32).
- **Regel 29 nachgezogen** (Punkt 6): jede Anfrage über den Baustein, alles je Bereich, Zeitlimit, abschließende Aktionen, Ausnahmen nur
  ohne Formular, veraltete Fehler.

#### Festlegungen 1.8.97 (Bitte bestätigen)

1. **"Kein fetch() außerhalb von _speichern.html" = keine Anfrage außerhalb von `lesen()`/`speichern()`/`abschliessen()`**; der Anfrage-Helfer
   der Seite (`api()`) ruft fetch weiter selbst und zählt als innerhalb, solange er nur dort aufgerufen wird.
2. **Ausnahmen nur ohne Formular, vier Gründe** (nur Anzeige, Suche, Anmeldestatus, Prüfung ohne Formular); Liste je Datei, Funktion und Ziel.
3. **Ein Aufruf aus dem HTML zählt als Verweis außerhalb**; eine Funktion, die nur im Anfrage-Argument erreicht wird, ist frei.
4. **Veralteter Fehler beim Lesen: false ohne Meldung; ein Fehler des neuesten Lesens verwirft ältere**; beim Speichern wie bisher.
5. **Erstes Laden im Bereich des Speicherns, das denselben Stand ersetzt**; setzen zwei Bereiche denselben Stand, wird es einer
   (Checklisten-Vorlage, Kundenakte, E-Mail-Vorlagen).
6. **Ein Wechsel ohne Anfrage läuft trotzdem durch den Bereich** (Dachtyp "keine Auswahl", Position ohne Kalkulation) -- eine späte Antwort
   der vorigen Auswahl wird verworfen.
7. **Kalkulation im Angebots-Editor in eigenem Bereich** 'kalkulation', getrennt vom LV ('angebot').
8. **E-Mail-Vorlage einer Mahnstufe frisch vom Server und im Bereich des Formulars gespeichert** (nicht mehr 'mahnstufen'); die Karte
   "Mahnstufen" lädt danach wie bisher neu.
9. **Einstellungen: jeder Abschnitt in eigenem Bereich**; ein nicht geladener Abschnitt bekommt wie bisher seinen leeren Stand, gesammelt in
   einer Meldung.
10. **Dialoge, die beim Öffnen laden, je eigener Bereich** (Abnahme, Mangel, Zahlung, Abwesenheit, Beteiligter, Buchung im Backoffice).
11. **Suchen bleiben Ausnahme** (Kopfzeilen, Suchergebnisse, Material-, Beteiligtensuche); die Verknüpfungssuche im Kalender geht trotzdem
    über `lesen()` (sie füllt den Termin-Dialog).
12. **Anmeldestatus bleibt direkt** (Seitenleiste, Stundenzettel); auf anderen Seiten liest er mit über `lesen('anmeldestatus'|'anmeldung')`.
13. **Erstes Laden wird ganz verworfen, wenn schon eine neuere Antwort desselben Bereichs angewandt ist** (Auftrag, Rechnung, Projektmappe):
    nur möglich, wenn vor dem Ende des Ladens gespeichert wird; die Auswahllisten bleiben dann bis zum nächsten Laden leer.
14. **Fehler beim Zeichnen des Formulars im Breadcrumb** (Betriebsmittel, Objekt) statt einer unbehandelten Ausnahme.
15. **`prepareWarranty()`: eine später ankommende, ältere Vorschau wird verworfen und speichert nicht**; das Speichern steht nicht im anwenden.
16. **Gesendet = `requestWillBeSentExtraInfo` (oder schon ein Antwort-Kopf) für den letzten Schritt der Anfrage**; `requestWillBeSent`
    allein heißt nur "die Seite will senden", aus dem Cache = nicht gesendet (im echten Chrome belegt).
17. **Gemeldet werden offene Anfragen, die beim letzten Dokumentwechsel offen gebliebenen und fehlgeschlagene mit `errorText`**;
    abgeschlossene nicht.
18. **Höchstens 8 Anfragen je Abschnitt, eine unveränderte Meldung nur einmal**; am Ende eines nicht erfolgreichen Laufs vollständig.
19. **`pruefe()` bleibt synchron und druckt den Stand des letzten Lesens**; die async Stellen lesen vorher nach (0,2 s, dann ein
    `Runtime.evaluate`).
20. **Der Anfragenzähler der Seite erscheint nur, wenn er von den offenen Fetch/XHR im Netz abweicht.**
21. **`warten()` meldet nach Ablauf mit "--", nicht als Fehler**; `melden=False` für eine gewollte Pause.
22. **`warten()` übersteht eine Navigation**, wie `oeffnen()`.
23. **"Im Netz anhalten" (CDP Fetch, Stufe Request) neben `zurueckhalten()`** in der Seite.
24. **Eine Ausnahme in `pruefen()` druckt das Netzwerkprotokoll und geht danach weiter** (Rückgabecode wie bisher).
25. **Klicktest Anmelden tippt und klickt über CDP-Eingabeereignisse**, nicht über `value=` und `.click()`.
26. **Abmelden ist richtig, wenn die Seite bis zur Antwort bleibt, der POST gesendet und mit 200 beantwortet ist und die Navigation danach
    beginnt**; "fertig" (`loadingFinished`) wird nicht verlangt (Chrome liefert es teils erst aus dem Back-Forward-Cache).
27. **Die Seitenleiste wird angemeldet, indem die Sitzung beim Laden endet** (Statusabfrage angehalten, Cookie gelöscht, fortgesetzt) -- der
    einzige erreichbare Weg (Nebenbefund 5).
28. **Lücken aus Angriffen sind im Klicktest `BEFUND`-Zeilen, gemeldet und nicht gezählt** -- nach einer Behebung werden sie Prüfungen.
29. **Die "fremde Adresse" der Angriffe ist 127.0.0.1 auf einem freien Port** (verlässt den Rechner nicht).
30. **Doppelklick auf "Anmelden" = genau eine Anmeldung** (solange die erste hängt, ist nur sie im Netz; die zweite, gleiche geht gar
    nicht hinaus -- Nr. 31; im Bericht des Helfers stand noch "zwei Anmeldungen, nacheinander").
31. **Dieselbe Anfrage (Methode, Adresse, Body als Text), während die erste im Bereich wartet oder unterwegs ist, geht nicht ein zweites
    Mal hinaus**; sie bekommt das Ergebnis der ersten und zählt nicht als wartend; Dateien (FormData) nie zusammengefasst.
32. **`klicktest_alle.py` startet jeden Klicktest ungepuffert** (`PYTHONUNBUFFERED=1`) -- bei einem Zeitlimit steht im Protokoll, was der Test
    bis zuletzt gedruckt hat, auch das Netzwerkprotokoll; gepuffert ging es beim Beenden verloren.

#### Tests und Prüfung

- Neu `tests/test_v400_lesen_ueber_baustein.py` (25): veraltete Fehler in node (ein älteres Lesen, das nach einem angewandten neueren
  scheitert, endet still; nach einem gescheiterten neueren wird ein älteres verworfen; ein Fehler des neuesten kommt an; beim Speichern wie
  bisher); keine Anfrage außerhalb des Bausteins über die Ausnahmen hinaus, jede Ausnahme mit einem Grund ohne Formular, der Scanner an
  sieben Beispielen (direkt, Helfer nur im Baustein, Helfer außerhalb, Ladefunktion im Baustein und zusätzlich direkt, oben im Skript,
  Aufruf aus dem HTML); die verlangten Stellen mit der echten Funktion der Vorlage in node und Antworten in falscher Reihenfolge -- E-Mail-
  Vorlagen (Rechnung, dann Mahnstufe: es bleibt die Mahnstufe), Speichern der Mahnstufe im Bereich des Formulars, Dachtyp (A, dann B, und
  A, dann "keine Auswahl"), Monat (September, dann Oktober), Kundenakte (Dokumente nur in ihrem Bereich), Checklisten-Vorlage (ein
  Bereich); Angebots-Editor (Kalkulation und LV verwerfen sich nicht, späte Kalkulation einer vorher gewählten Position verworfen);
  Doppelklick (dieselbe Anfrage einmal, wartet nicht; anderer Body und Datei zweimal; nach der Antwort wieder; eigene lesbare
  fetch-Antwort, gemeinsamer Fehler; abschließende Aktion einmal).
- Neu `tests/test_v400_klicktest_netzwerk.py` (31, ohne Chrome): Recorder mit gestellten CDP-Ereignissen (offen, gesendet in sechs Fällen,
  Weiterleitung, Cache, fehlgeschlagen, Dokumentwechsel, im Netz angehalten, Anfragenzähler nur bei Abweichung, Kürzen auf 8, unveränderte
  Meldung einmal), Tab mit gestelltem websocket (`cmd()` reicht weiter, `pruefe()`, `oeffnen()` und jeder Warte-Helfer drucken beim
  Scheitern, `warten(…, melden=False)` nicht, Ende des Laufs druckt, ein erfolgreicher nicht).
- Klicktest `scripts/klicktest_anmelden.py` (neu) 50/50 (8 `BEFUND`-Zeilen, Nebenbefunde 1–4); `klicktest_abschliessen` mit gewollten
  Pausen ohne Meldung; die drei Helfer haben je Seite mit Klicktest mindestens einen passenden laufen lassen (alle wie erwartet) und für
  Seiten ohne eigenen einen Wegwerf-Klicktest mit zurückgehaltener Antwort.
- Gegenproben (Regel 24): 36 von 36 rot. Punkt 4 (18): veralteter Fehler kommt an, neuerer Fehler markiert nicht, Mahnstufe aus dem
  gemerkten Stand, Mahnstufe im alten Bereich, Dachtyp direkt, "keine Auswahl" direkt, Monat direkt, Dokumente wieder in `load()`,
  Checklisten-Vorlage mit zweitem Bereich, Scanner ohne Aufrufe aus dem HTML, Scanner ohne "nur im Baustein erreicht", erstes Laden des
  Auftrags direkt, Kalkulation im Bereich 'angebot', dazu (Helfer A, in einer Kopie) Projektformular und Projektmappe auf dem alten Stand:
  Objektliste des vorher gewählten Kunden überschreibt die Auswahl; Einstellungen ohne Fehlerfang je Abschnitt (`test_v054`); Doppelklick
  zweimal gesendet, ohne eigene Kopie der Antwort, auch mit Datei zusammengefasst. Punkt 5 (18): Werkzeug 14 von 14 (ExtraInfo nicht gezählt, `pruefe()`
  und `oeffnen()` drucken nicht, kein Nachlesen, Dokumentwechsel nicht ausgewertet, je Warte-Helfer, kein Schlussbericht, Anhalten und
  Fehlschlag nicht aufgezeichnet, `cmd()` reicht nichts weiter), Klicktest 4 von 4 (Abmelden ohne Abwarten in beiden Kopfzeilen -- das
  Protokoll nennt den POST als "gesendet: nein, im Netz angehalten" --, Anmelden ohne Baustein: zwei POST parallel, `_safe_next_target()`
  ohne Prüfung). Jede Datei byte-genau zurück, kein Marker.
- Volle Suite (mit den Tests gegen PostgreSQL, Arbeitskopie, drei Teile parallel): 4539 grün, 1 rot -- `test_v054` (Erwartung veraltet seit 1.8.97: prüfte den alten Aufbau von `load()` wörtlich), angepasst, danach grün; nach der Änderung am Baustein (Doppelklick) alle 24 Testdateien, die den Baustein oder Seitenskripte in node ausführen: 817 grün (19 Tests gegen PostgreSQL ohne Bezug zum Baustein dabei übersprungen).
- Alle Klicktests (Regel 26): 61 von 61 wie erwartet in 13:47 min (`klicktest_anmelden` 50/50). Davor zwei Gesamtläufe mit `klicktest_anmelden` im Zeitlimit: der erste vor der Doppelklick-Änderung (Dialog "Seite verlassen?", siehe oben), der zweite danach -- Ursache nicht belegt (Ausgabe gepuffert; während des Laufs wurde `_speichern.html` in der Arbeitskopie neu geschrieben, nur ein Kommentar, gegen die eigene Regel); einzeln, über den Läufer und in der Reihenfolge des Gesamtlaufs je 50/50, danach der Gesamtlauf neu (ungepuffert, Festlegung Nr. 32).

#### Nebenbefunde (nur gemeldet)

1. **Skript über `next` im Anmeldeformular (XSS)**: `login.html` setzt nach der Anmeldung `location.href` ungeprüft auf `next` --
   `/login?next=javascript:…` führt das Skript im ERP aus, mit der frischen Sitzung (im Klicktest belegt). Wer sich über einen solchen Link
   anmeldet, führt es mit den eigenen Rechten aus; ein Admin mit vertrautem Gerät sofort, sonst nach dem zweiten Faktor über
   `account.html` (Zeile 177 setzt `next` ebenso ungeprüft; nach Code). Abhilfe wäre die Regel von `_safe_next_target()` auch im Browser.
2. **Offene Weiterleitung über `next` im Anmeldeformular** (bekannt seit 1.3.48): absolute Adresse, `//host`, `/\host`; serverseitig
   geschlossen.
3. **Abmelden beendet die Sitzung nicht serverseitig**: das Cookie ist zustandslos (12 h), der alte Wert bekommt nach dem Abmelden weiter
   200; auch ein Passwortwechsel beendet keine Sitzung (nach Code).
4. **"Zurück" nach dem Abmelden zeigt die Daten** (Back-Forward-Cache, ohne ihn der HTTP-Cache: Seite und 9 API-Antworten); kein
   `Cache-Control: no-store` -- auf dem Fahrzeug-Tablet mit mehreren Monteuren.
5. **Formular "Nicht angemeldet" der Seitenleiste praktisch nicht erreichbar** (jede Seite verlangt die Anmeldung, der Status wird nur
   beim Laden abgefragt); der Kopfkommentar in `_sidebar.html` stimmt nicht.
6. **Abmelden ohne Antwort**: `.finally` navigiert trotzdem, `/login` leitet zurück -- ohne Meldung weiter angemeldet.
7. **Anmelden im Formular ohne Netz** zeigt nichts (unbehandelte Ablehnung; nach Code).
8. **Doppelklick mit falschem Passwort** zählte zwei Fehlversuche (der Baustein reihte ein) -- seit Festlegung 1.8.97 Nr. 31 behoben (eine
   Anfrage).
9. **`GET /api/employees` 500 für Admin und Büro – Finanzen**, sobald ein Mitarbeiter mit Kostenzuordnung "labor_rate" keinen Stundenlohn
   hat (der Validator von `EmployeeOut` läuft auch beim Ausgeben, `app/routers/employees.py::_employee_out_for_role`): Mitarbeiterfilter im
   Dashboard still leer, "Kolonne / Team" und "Mitarbeiter bearbeiten" nur mit Fehler. Ob es solche Zeilen im Bestand gibt, ist nicht
   geprüft.
10. **Angebots-Editor `saveCalc()` lädt mit der gerade gewählten Position neu**: wird während des Speicherns eine andere Position gewählt,
    kann sie die Kalkulation der ersten zeigen (schon vorher).
11. **Setzen ohne Anfrage kann noch überschrieben werden**: Kalender blendet bei Suchtext unter 2 Zeichen die Vorschläge ohne Anfrage aus,
    eine laufende ältere Suche blendet sie wieder ein; `time_tracking.html::openManual()` setzt die Positionen direkt, eine laufende Antwort
    aus `orderChanged('manual')` kann sie danach überschreiben.
12. **Materialsuchen** (Leistung, Einsatzbericht) füllen eine Auswahl, aus der gespeichert wird -- eine späte ältere Trefferliste kann die
    neuere ersetzen (gespeichert wird nur Gewähltes); als Suche in den Ausnahmen, die Verknüpfungssuche im Kalender dagegen umgestellt.
13. **Projekt anlegen/bearbeiten**: vorher konnte das Objekt eines anderen Kunden in der Auswahl landen und mitgeschickt werden (späte
    Objektliste nach Kundenwechsel) -- durch die Umstellung behoben; ob der Server es ablehnt (Regel 25), ist nicht geprüft.
14. **Kleinigkeiten**: `time_tracking.html::groupOrderChanged()` lädt keine Positionen nach (Gruppen-Dialog ohne LV-Positionen, wenn der
    Kontext nicht lud); `ensureOrderItems()` legt Positionen im Zwischenspeicher je Auftrag schon in der Anfrage ab; `defOptions()` legt auch
    eine verworfene Antwort im Cache ihrer Abnahme ab; `operational_asset.html::markRepaired()` übernimmt die Antwort nach dem Speichern
    direkt; `inspection_template.html::loadTemplate()` setzt das Metadaten-Formular nicht -- alle schon vorher, unschädlich.
15. **Adressimport, endlose Anfragen bei gefülltem Suchfeld** (Nebenbefund 1 aus 1.8.95) besteht unverändert.
16. **Drei Klicktests warten je 15 s auf eine Bedingung, die nie eintritt, und sind danach grün** (`klicktest_behinderungsanzeige_abschluss`
    Z. 204, `klicktest_versandprotokoll` Z. 280, `klicktest_vertrag_unterschrift` Z. 287) -- sichtbar erst durch die neue "--"-Zeile.
17. **Zum roten `klicktest_vertragsgrundlage` aus 1.8.95** (nur Hinweis): die Kundenakte startet beim Laden 13 Anfragen gleichzeitig, Chrome
    öffnet höchstens sechs Verbindungen je Server; eine wartende stünde jetzt im Protokoll als offen mit "gesendet: nein".

## Weiterleitung, Sitzungen, Cache-Verbot, Befund Seiten (ab 1.8.98)

### Vorgabe vom 14.10.2026 (übernommen wie gegeben)

Vorweg zu 1.8.96/1.8.97: Festlegungen bestätigt, mit diesen Korrekturen:
- 96-1: Beim Hochladen läuft das Zeitlimit erst ab dem Ende der Übertragung.
- 96-6: Zahlung, Gegenbuchung, Erstattung, Storno, Abnahme, Mangel und Nebenforderung sind abschließend; was in der Liste fehlt, aufnehmen.
- 96-7: Ein gescheitertes Speichern ohne nachfolgendes erfolgreiches im selben Bereich sperrt abschließende Aktionen wie „unklar“. Das gilt
  nur für Speichern: Eine vom Server abgelehnte abschließende Aktion sperrt keine weitere, eine unklare schon (96-9). Dazu ein Test mit
  Gegenprobe; den Docstring des umbenannten Tests in test_v399 berichtigen.
- 96-13: Dauertest: __dkZeitlimit steht nur im Baustein und unter scripts/.
- 96-19: Zeilensperre überall, wo ein gespeicherter Wert aus mehreren Feldern abgeleitet wird (etwa Gesamtpreis einer Position);
  Angriffstest mit zwei gleichzeitigen Teil-Updates verschiedener Felder gegen PostgreSQL.
- 96-24: content am Layout-Baustein wird gespeichert, nie still verworfen.
- 97-1: Auch ein direkter Aufruf von api() außerhalb von lesen()/speichern()/abschliessen() wird gemeldet.
- 97-7: Ändert das Speichern der Kalkulation Werte im LV, lädt das LV in seinem Bereich neu.
- moveItemBefore auf Teil-Update.
- Regel 26 erweitern: volle Suite und alle Klicktests auf dem committeten Endstand bei sauberer Arbeitskopie, Hash im Bericht; ändert sich
  danach etwas, laufen beide neu. Regel 28 erweitern: jede angepasste Erwartung mit altem und neuem Soll.

1. Weiterleitungsziele (next und alle anderen): eine gemeinsame Prüffunktion auf dem Server und eine im Browser, nur lokale Pfade, sonst
   die Startseite. Strukturtest: jede Navigation zu einem Wert aus Anfrage oder Adresse läuft darüber. Angriffstests mit javascript:,
   data:, //, /\, fremden Hosts und kodierten Varianten. Die BEFUND-Zeilen der Klicktests werden zu Prüfungen.
2. Abmelden beendet die Sitzung auf dem Server. Passwort- und 2FA-Änderung sowie das Deaktivieren eines Benutzers beenden alle seine
   Sitzungen. Angriffstest: altes Cookie nach dem Abmelden.
3. Cache-Control: no-store für jede Antwort an eine angemeldete Sitzung, auch PDFs und Dateien; Dauertest über alle GET-Endpunkte.
4. Nur Befund, Fehler als xfail(strict=True): Cookie-Flags, Schutz schreibender Anfragen gegen fremde Seiten, und wo Daten ungeschützt in
   die Seite gelangen (innerHTML, |safe), besonders Daten von außen (Outlook-Termine, Adressimport, Altkunden).

Reihenfolge: Punkte 1–3, dann Vorweg, dann Punkt 4. Angriffstests mit Gegenprobe. Eigene Festlegungen mit „Bitte bestätigen“, je in einer
Zeile. Nebenbefunde nur melden. Wird der Umfang zu groß: nach Punkt 3 committen und den Rest auflisten. Commit nach Regel 13, Bericht
kurz.

### Umsetzung 1.8.98: Weiterleitungsziele (Punkt 1), Sitzungen auf dem Server (Punkt 2), Cache-Verbot (Punkt 3)

#### Was gebaut ist

- **Eine Prüffunktion je Seite** (Punkt 1): `app/weiterleitung.py::sicheres_ziel(wert, startseite)` / `ist_lokal(wert)` auf dem Server,
  `app/templates/_weiterleitung.html::sicheresZiel(wert, startseite)` / `istLokalesZiel(wert)` im Browser, dieselbe Regel: genau ein "/" am
  Anfang (nicht "//", nicht "/\"), nur druckbare ASCII-Zeichen ohne Leerzeichen und Rückstrich (Browser entfernen Tab und Zeilenumbruch
  und lesen "\" wie "/"), jedes "%" mit zwei Hex-Ziffern, auch dekodiert (höchstens fünfmal) kein Steuerzeichen, kein Leerzeichen, kein
  Rückstrich und kein "//" am Anfang, kein Schema und kein Host (im Browser zusätzlich derselbe Ursprung über `new URL()`); sonst die
  Startseite. `_safe_next_target()` (seit 1.3.48, nur "/" und "//" geprüft) entfällt.
- **Angewandt**: `login_page()` (angemeldet: `next` über `sicheres_ziel()`, sonst die Startseite der Rolle; zweiter Faktor offen:
  `/account` und `next` nur, wenn lokal), `login.html::login()` (`sicheresZiel(next, '/projects' bzw. '/mobil')`, an `/account` nur ein
  lokales `next` -- bis 1.8.97 `location.search` unverändert) und `account.html::verifyCode()` (bis 1.8.97 `next` ungeprüft).
  Nebenbefunde 1 und 2 aus 1.8.97 behoben.
- **Strukturtest Server** (`tests/test_v401_weiterleitung.py`, AST): jede `RedirectResponse` und jede Kopfzeile `Location` in `app/` nimmt
  ein festes Ziel (Text mit lokalem Anfang, `default_home_page_for_role()`) oder `sicheres_ziel()`, auch über eine Variable, `a if b else
  c` und `a or b`; vier Weiterleitungen gefunden (Anmeldeschranke, `login_page()` zweimal, Dashboard für Monteure).
- **Strukturtest Browser** (`tests/vorlagen_navigation.py`): jede Navigation (Zuweisung an `location`, `location.href`, `X.href`;
  `location.assign/replace()`, `window.open()`) in allen Vorlagen und ihren Handlern im HTML zu einem Wert aus der Adresse
  (`location.search/hash/href`, `document.referrer/URL/documentURI/baseURI`, `window.name`, auch über Variablen und Funktionen) geht über
  `sicheresZiel()` oder beginnt mit einem festen lokalen Pfad (`'/projects/'+x`), bei `a?b:c` und `a||b` jeder mögliche Wert. 100
  Navigationen, 10 zu Werten aus der Adresse, alle geprüft (vorher wären `login.html` und `account.html` rot gewesen).
- **Sitzungen auf dem Server** (Punkt 2, `app/sitzungen.py`, Tabelle `user_sessions`, Migration `8c86e12540cf`): das Cookie `dk_erp_auth`
  trägt einen Zufallswert (`secrets.token_urlsafe(32)`), gespeichert ist nur sein SHA-256; Ablauf fest 12 h ab der Anmeldung. Abmelden
  beendet die eigene Sitzung (`beenden()`); ein neues Passwort (eigenes und durch einen Administrator), die Ersteinrichtung des zweiten
  Faktors, sein Zurücksetzen (Administrator oder Notfallskript, `two_factor.reset()`) und das Deaktivieren eines Benutzers beenden alle
  seine Sitzungen (`alle_beenden()`) -- wer selbst ändert, bleibt auf diesem Gerät mit einer neuen Sitzung angemeldet. Die Anmeldung
  vergibt immer einen neuen Wert und beendet einen mitgeschickten (Sitzungsfixierung). Der zweite Faktor steht an der Sitzung
  (`second_factor_at`) statt im Cookie `dk_erp_otp_ok`, das an den Benutzer gebunden war und sich in eine neue Anmeldung mitnehmen ließ
  (12 h gültig); die Bestätigung gibt der Sitzung einen neuen Wert. Benutzer löschen nimmt seine Sitzungen mit (ORM-Beziehung und
  `ON DELETE CASCADE` -- unter SQLite ohne erzwungene Fremdschlüssel bekäme sonst der nächste neue Benutzer mit derselben ID die alte
  Sitzung). Nebenbefund 3 aus 1.8.97 behoben.
- **Anmeldeschranke als eigenes Modul** (`app/anmeldeschranke.py::middleware(session_factory)`): Identität aus der Sitzung, Anmeldepflicht,
  zweiter Faktor, Cache-Verbot; `app/main.py` bindet sie mit `SessionLocal` ein, die Tests mit ihrer Sitzungsfabrik
  (`tests/anmeldung.py`) -- `test_v250`, `test_v256`, `test_v257` und `test_v292` bauten die Middleware bis 1.8.97 je nach.
- **Cache-Verbot** (Punkt 3): jede Antwort an eine angemeldete Sitzung und jede Antwort, die das Anmelde-Cookie setzt oder löscht,
  trägt `Cache-Control: no-store` -- auch PDFs und Dateien, eine eigene Angabe des Endpunkts (Logo ein Jahr `immutable`, Fotos einer
  Checkliste eine Stunde) wird ersetzt. "Zurück" nach dem Abmelden fragt den Server und landet auf der Anmeldung (Nebenbefund 4 aus 1.8.97
  behoben).
- **Klicktest `klicktest_anmelden`**: die acht BEFUND-Zeilen sind Prüfungen (alter Cookie-Wert 401 nach dem Abmelden in Büro und /mobil,
  "Zurück" ohne Daten in drei Fällen, `next` über das Formular: fremde Adresse, `//`, Rückstrich, Tab, `/%2F`, `/%5C`, `https:` ->
  Startseite; `javascript:`, ` JavaScript:`, `data:` -> kein Skript; angemeldet acht Werte am Server); je Abschnitt, der sich abmeldet, eine
  eigene Sitzung (`k.cookies()` legt seit 1.8.98 eine Sitzung an).

#### Festlegungen 1.8.98 (bestätigt am 14.10.2026; Nr. 5: 12 h passen dem Betrieb; Nr. 11 und 12 korrigiert, siehe Vorgabe ab 1.8.101)

1. **Lokal = die Regel oben**, bewusst streng: auch harmlose Pfade mit kodiertem Leerzeichen, Rückstrich oder `%25` am Ende (`/100%25`) werden abgelehnt.
2. **Startseite = die der Rolle**: Server `/` bzw. `/mobil`, im Anmeldeformular wie bisher `/projects` bzw. `/mobil`, zweiter Faktor offen `/account` ohne `next`.
3. **"Wert aus Anfrage oder Adresse"**: am Server jede Weiterleitung, im Browser Werte aus der Adresse; Werte aus API-Antworten (z. B. `product_url` als Link) gehören zu Punkt 4.
4. **Ein fester lokaler Anfang gilt als geprüft** (`'/projects/'+x`, `` `/a/${x}` ``): der Wert bestimmt nur den Rest des Pfads.
5. **Sitzung fest 12 h ab der Anmeldung**, keine gleitende Verlängerung (ein GET schreibt nicht); abgelaufene Zeilen räumt die nächste Anmeldung auf.
6. **Wer selbst ändert, bleibt auf diesem Gerät angemeldet** (eigenes Passwort, Ersteinrichtung, eigenes Passwort in der Benutzerverwaltung), mit neuer Sitzung; alle anderen enden, auch die alte dieses Geräts.
7. **Die Bestätigung des zweiten Faktors gibt der Sitzung einen neuen Wert**; die übrigen Sitzungen des Kontos bleiben.
8. **Zweiter Faktor je Sitzung statt eigenem Cookie**; `dk_erp_otp_ok` wird beim Anmelden und Abmelden nur noch gelöscht.
9. **Die Anmeldung beendet eine mitgeschickte Sitzung** und vergibt immer einen neuen Wert, auch wenn schon jemand angemeldet war.
10. **Nach dem Einspielen gilt kein altes Cookie mehr**: jede Person meldet sich einmal neu an.
11. **Rolle, Name, Mitarbeiter und Postfach ändern beendet keine Sitzung** (die Rolle wird je Anfrage frisch gelesen), ebenso "Alle vertrauten Geräte abmelden".
12. **Feierabend in /mobil löscht weiter nur das Cookie** (GET, Regel 23); die Sitzung endet mit ihrem Ablauf.
13. **no-store auch für Anmelden und Abmelden** (Antworten, die das Cookie setzen oder löschen); Antworten ohne Sitzung (Anmeldeseite, `/health`, 401) bleiben ohne.
14. **Eigene Cache-Angaben werden für angemeldete Sitzungen ersetzt**: das Logo lädt jede Seite neu (vorher ein Jahr aus dem Cache).
15. **"Zurück" im Klicktest**: keine Daten, nicht aus dem Back-Forward-Cache, keine Seite und keine API-Antwort aus dem HTTP-Cache -- die Anmeldeseite selbst (ohne Sitzung, ohne Daten) darf daraus kommen.
16. **Die Tests binden die echte Anmeldeschranke ein** (`tests/anmeldung.py`) statt sie nachzubauen.

#### Tests und Prüfung

- Neu `tests/test_v401_weiterleitung.py` (255): Angriffstabelle (66 Werte: `javascript:` in vier Schreibweisen, `data:`, `vbscript:`,
  `//`, `///`, `/\`, `\\`, fremde Hosts mit und ohne Schema, Tab/Zeilenumbruch/Leerzeichen/NUL, `/．`, `/∕`, kodiert `/%2F`, `%2F%2F`,
  `/%5C`, `/%09/`, `/%0a/`, doppelt und dreifach kodiert, kaputte Kodierung, zu lang, kein Text) und 14 erlaubte Pfade gegen beide Fassungen
  (die Browser-Fassung in node, dieselbe Entscheidung, jeder erlaubte Pfad mit demselben Ursprung), die Weiterleitung des Servers als
  Büro, Monteurin und Admin mit offenem zweitem Faktor, `login.html::login()` und `account.html::verifyCode()` in node; Strukturtest Server
  (AST, vier Weiterleitungen) mit zwölf Beispielen, Strukturtest Browser (alle Vorlagen samt Handlern) mit zwanzig Beispielen und einem
  Handler im HTML.
- Neu `tests/test_v402_sitzungen.py` (31, davon 2 gegen PostgreSQL): **Angriffstests** mit dem Cookie-Wert von vorher -- nach dem
  Abmelden (API 401, Seite auf die Anmeldung), nach eigenem Passwort (auch der alte Wert dieses Geräts), nach einem Passwort durch einen
  Administrator, nach Deaktivieren (auch nach dem Reaktivieren), nach Zurücksetzen und Notfallskript, nach der Ersteinrichtung, nach der
  Bestätigung des zweiten Faktors; untergeschobener Wert vor der Anmeldung (Sitzungsfixierung), erfundene und kaputte Werte, das
  zustandslose Cookie von 1.8.97, das alte Cookie des zweiten Faktors; gespeichert nur der Hash; Ablauf; Lesen schreibt nicht; Benutzer
  löschen mit Wiedervergabe der ID unter SQLite; Gegenstück (Name/Rolle ändern beendet nichts).
- Neu `tests/test_v403_kein_cache.py` (4): alle 310 GET-Routen (API und Seiten) über die echte Anmeldeschranke als Admin (mit Logo und PDFs)
  und als Monteurin -- jede Antwort `no-store`; Anmelden und Abmelden ebenso.
- Neu `tests/anmeldung.py` (Testanwendung mit der echten Anmeldeschranke); `test_v400_klicktest_netzwerk.py` +1 (Dialog des Browsers).
- **Angepasste Erwartungen** (altes -> neues Soll): `test_v257::test_safe_next_target_*` `_safe_next_target(None/""/absolut) is None` ->
  `sicheres_ziel(...) == "/"`; `test_v257::test_login_html_forwards_the_query_string_to_account` `'/account'+location.search` -> nur ein
  lokales `next`; `test_v066::test_password_hash_and_signed_cookie` `parse_cookie(make_cookie(42)) == 42` -> Sitzung hin und zurück. Nur der
  Aufbau geändert (Soll gleich): `test_v257` (zweiter Faktor offen über eine neue Anmeldung statt OTP-Cookie löschen), `test_v250`,
  `test_v256`, `test_v292` (echte Anmeldeschranke), `test_v067` (unbenutzter Helfer mit altem Cookie entfernt).
- Klicktest `klicktest_anmelden` 69/69 (vorher 50 Prüfungen und 8 BEFUND-Zeilen), mehrfach; je Abschnitt eine eigene Sitzung, zwischen den
  Angriffen Ruhe abwarten.
- Migrationsprobe gegen PostgreSQL (Wegwerf-Schema): Vorgänger, Bestand, hin, UNIQUE und ON DELETE CASCADE, `alembic check` ohne Unterschied,
  zurück (Tabelle weg), wieder hin. Unter SQLite `alembic check` ohne Unterschied.
- Gegenproben (Regel 24): 24 von 24 rot -- Server ohne Rückstrich- bzw. ohne Dekodierprüfung, `login_page()` ohne Prüfung, Browser ohne
  Dekodieren, `login.html`/`account.html` ungeprüft, Scanner ohne Variablen; Abmelden, eigenes Passwort, Deaktivieren, Zurücksetzen,
  Ersteinrichtung je ohne Beenden, Bestätigung ohne neuen Wert, Anmeldung ohne Beenden des mitgeschickten, Benutzer ohne Beziehung zu den
  Sitzungen, zweiter Faktor nicht je Sitzung, Ablauf nicht geprüft; kein Cache-Verbot, ohne PDFs/Bilder, eigene Angabe bleibt; Werkzeug ohne
  Dialog; Klicktest mit `login.html` ungeprüft (10 rot), Abmelden ohne Beenden (2 rot), ohne Cache-Verbot (3 rot). Jede Datei byte-genau
  zurück, kein Marker. Im ersten Lauf der Klicktest-Gegenproben hing `klicktest_anmelden` an "Seite verlassen?" (eine Anmeldung war bei
  der nächsten Navigation noch unterwegs) -- über die eigenen PIDs beendet, der Klicktest wartet seither zwischen den Angriffen, das
  Werkzeug meldet und schließt solche Dialoge; die drei Klicktest-Gegenproben danach neu.
- Volle Suite (mit den Tests gegen PostgreSQL, Arbeitskopie, drei Teile parallel): 4839 grün, 3 rot -- `test_v251` ×3 (ruft
  `change_password()` direkt mit Positionsargumenten; der neue Parameter `response` stand vor `db`, und ohne Antwort las `alle_beenden()`
  das Cookie eines gestellten Anfrageobjekts): `response` ans Ende, ohne Antwort kein Cookie lesen; danach `test_v251`, `test_v402`,
  `test_v250`, `test_v292` 78 grün.
- Alle Klicktests (Regel 26, Arbeitskopie des Stands 1.8.98): 61 von 61 wie erwartet in 16:26 min.

#### Nebenbefunde (nur gemeldet)

1. **Die Anmeldeseite selbst kommt beim "Zurück" aus dem HTTP-Cache** (sie trägt ohne Sitzung kein `no-store`) -- ohne Daten, harmlos.
2. **Sechs Handler im HTML liest der Navigations-Scanner nicht** (Jinja oder unvollständiges JS im Attribut); keiner enthält eine Navigation,
   der Test prüft das.
3. **Feierabend in /mobil beendet die Sitzung nicht** (Festlegung Nr. 12): bis zu ihrem Ablauf gilt sie an allen übrigen Endpunkten weiter.
4. **Zwischen dem Ablesen der Sitzung in der Anmeldeschranke und dem Endpunkt** kann eine gleichzeitige Abmeldung liegen -- die eine Anfrage
   läuft noch mit der eben beendeten Sitzung zu Ende (jede weitere nicht mehr).

### Umsetzung 1.8.99: Vorweg (Korrekturen der Festlegungen 1.8.96/1.8.97)

#### Was gebaut ist

- **96-1 Zeitlimit beim Hochladen** (`app/templates/_speichern.html`): ein Speichern, dessen Body eine Datei ist (FormData, Blob/File,
  ArrayBuffer oder eine Sicht darauf), geht über XMLHttpRequest statt fetch; die Uhr läuft erst ab dem Ende der Übertragung (Ereignis
  `upload.loadend`, spätestens mit dem Antwortkopf), ohne Datei wie bisher ab dem Senden. Die Seite bekommt eine gewöhnliche Response
  (Status, Kopfzeilen, Body), ein Netzfehler ist ein TypeError, ein Abbruch über das Signal ein AbortError -- wie bei fetch. Ohne
  XMLHttpRequest (node) bleibt es bei fetch. Nebenbefund 1 aus 1.8.96 behoben.
- **96-7 gescheitertes Speichern sperrt** (`_speichern.html`): jeder Bereich merkt sich, ob sein letztes Speichern gescheitert ist (Fehler
  oder Fehlerstatus); `abschliessen()` geht nicht hinaus, solange das in irgendeinem Bereich der Seite gilt -- auch wenn es vor dem Klick
  gescheitert ist --, bis ein späteres Speichern im selben Bereich gelingt (Meldung wie bisher "Nicht ausgeführt: ein Speichern auf der
  Seite ist gescheitert (<Grund>) …"). Nur `speichern()` setzt das: eine vom Server abgelehnte abschließende Aktion sperrt keine weitere,
  eine unklare (Zeitlimit) schon. Docstring von `test_two_final_actions_after_a_failed_save_are_both_refused_naming_it` berichtigt.
- **96-6 abschließend** (`tests/test_v399_abschliessen.py`): alle Aufrufe zu Zahlung, Gegenbuchung, Erstattung, Storno, Abnahme, Mangel
  und Nebenforderung standen schon in `ABSCHLIESSEND` (geprüft über alle Vorlagen und Endpunkte); neu "Eingangsrechnung als bezahlt
  markieren" (`incoming_invoices.html::markPaidNow`, Zahlung). `charges` gehört jetzt zu den Adressmustern; die Übernahme von Gebühr,
  Pauschale und Zinsen in den Entwurf einer Mahnung (`saveReminderCharges` in Rechnung und Mahnwesen) steht mit Grund in
  `NICHT_ABSCHLIESSEND` -- gebucht wird die Nebenforderung erst beim Festschreiben (abschließend).
- **96-13 Dauertest** (`tests/test_v404_vorweg.py`): `window.__dkZeitlimit` steht im Code nur im Baustein und unter `scripts/` (Tests und
  Doku zählen nicht); `_email_dispatch.html` las es bis 1.8.98 selbst für die Sekundenangabe -- jetzt `zeitlimitSekunden()` aus dem Baustein.
- **96-19 Zeilensperren** an jedem Teil-Update, das einen gespeicherten Wert aus mehreren Feldern ableitet (Bestandsaufnahme aller 25
  `PartialUpdate`-Schemas; fünf ohne Sperre gefunden):
  - Kalkulation einer Leistung (`PUT /api/services/{id}/calculation`): Sperre der Leistung, ein Commit -- der Verkaufspreis wurde bis 1.8.98
    nach einem ersten Commit ungesperrt neu gerechnet.
  - Angebot: Nummerierung (OZ, Titelnummern) und Reihenfolge (`app/projects.py::lock_quote()` in `auto_number_quote()`, `set_item_layout()`,
    `reorder_quote()` und dem neuen Verschieben) -- sie leiten sich aus allen Positionen und Titeln ab.
  - Zeit- und Gruppenbuchung (`PUT /api/time-entries/{id}`, `PUT /api/time-entry-groups/{id}`): Zeile vor dem Zusammenführen (Auftrag und
  LV-Position gehören zusammen), bei der Gruppe zusätzlich die Mitgliedsbuchungen und ihre Verknüpfungen frisch (eine gleichzeitige
  Einzelkorrektur wird übersprungen oder wartet).
  - Auftragsposition -> Materialbedarf der Arbeitsvorbereitung: der Neuaufbau (`refresh_preparation_materials()`) unter der Sperre der
  Auftragszeile, im selben Commit wie die Position; das Ändern einer Materialzeile sperrt dieselbe Zeile.
  - Kontakt (`update_contact()`): Art und Name/Firma werden auf dem zusammengeführten Stand geprüft -- jetzt unter der Sperre der Zeile.
- **96-24** `content` am Layout-Baustein wird gespeichert (`update_layout_block()`), gezeichnet wird er weiterhin nicht.
- **97-1 Scanner** (`tests/vorlagen_js.py::anfragen_ausserhalb()`): ein Aufruf von `fetch()` oder einem Anfrage-Helfer direkt aus einem
  on…-Attribut (Markup oder Template-Literal) ist ein Fund ("<html>"). Gefunden: "weitere anzeigen" der Suchseite -- die Suchseite liest
  jetzt ganz über `lesen()` (Bereich 'suche'), ihre vier Ausnahmen entfallen (37 -> 33).
- **97-7 Kalkulation** (`quote_editor.html::saveCalc()`): nach dem Speichern lädt das LV in seinem Bereich 'angebot' neu (der EP kommt
  aus der Kalkulation); Formular und Kalkulation nur, wenn noch dieselbe Position gewählt ist (Nebenbefund 10 aus 1.8.97 behoben).
- **moveItemBefore als Teil-Update**: `POST /api/quotes/{id}/items/{item_id}/move` mit `{before_item_id}` (`move_quote_item_before()`):
  Titel und Reihenfolge rechnet der Server aus dem gespeicherten Stand unter der Sperre des Angebots, beide Positionen müssen zum Angebot
  gehören (Regel 25, 404). Nebenbefund 5 aus 1.8.96 behoben.
- **Regel 26 und 28 erweitert** (CLAUDE.md), Regel 29 nachgezogen.
- **Klicktest `scripts/klicktest_hochladen.py`** (neu): Kundenakte, Zeitlimit 2 s, Upload auf 100 KB/s gedrosselt, 400 KB -- fertig ohne
  "unklar", als XHR, länger als das Zeitlimit unterwegs, Datei mit voller Größe am Server, danach ein zweites Dokument.

#### Festlegungen 1.8.99 (bestätigt am 14.10.2026; Nr. 6 richtig, Test mit Gegenprobe; Nr. 10 und 13 korrigiert, siehe Vorgabe ab 1.8.101)

1. **Hochladen = Body FormData, Blob/File, ArrayBuffer oder eine Sicht darauf**; Text (auch JSON) geht wie bisher über fetch.
2. **Ende der Übertragung = `upload.loadend` oder der Antwortkopf**, was zuerst kommt; während der Übertragung läuft kein Zeitlimit (bricht die Verbindung ab, meldet der Browser einen Netzfehler).
3. **Hochladen über XMLHttpRequest liefert eine Response wie fetch**; `response.url` und `redirected` gibt es dabei nicht (keine Seite nutzt sie).
4. **"Gescheitert" gilt je Bereich bis zum nächsten erfolgreichen Speichern dort**, auch wenn es vor dem Klick lag; erst Neuladen oder ein gelungenes Speichern hebt es auf.
5. **Abschließende Aktionen warten weiter auf jede laufende**, gezählt wird aber nur gescheitertes Speichern.
6. **Als "umbenannten Test" in test_v399 habe ich `test_two_final_actions_after_a_failed_save_are_both_refused_naming_it` berichtigt** (sein Docstring sagte, die erste Aktion zähle für die zweite als gescheitert) -- war ein anderer gemeint?
7. **"Eingangsrechnung als bezahlt markieren" ist abschließend** (Zahlung).
8. **Nebenforderung in den Entwurf einer Mahnung übernehmen ist nicht abschließend** (gebucht beim Festschreiben); `charges` steht dafür im Adressmuster.
9. **`__dkZeitlimit` im Code nur in `_speichern.html` und unter `scripts/`**; Tests und Doku zählen nicht, Vorlagen fragen `zeitlimitSekunden()`.
10. **Zeilensperre an den fünf gefundenen Stellen und am Kontakt**; nicht an Aufgabe (`completed_at` folgt nur aus dem Status), Lieferant am Material (nur aus `supplier_id`), Vertragsentwurf (Nebenbefund 2).
11. **Die Sperre des Angebots sitzt in `auto_number_quote()`** und damit in jedem Weg, der neu nummeriert (auch Anlegen, Löschen, Kopieren von Positionen und Titeln).
12. **Ein Materialbedarf, den ein gleichzeitiger Neuaufbau ersetzt hat, ist weg** (404, die Seite lädt neu).
13. **`content` wird gespeichert, nicht gezeichnet.**
14. **Direkter Aufruf aus dem HTML = jedes on…-Attribut mit `fetch()` oder einem Anfrage-Helfer**, auch in Template-Literalen; statt einer neuen Ausnahme ging die Suchseite ganz über `lesen()`.
15. **Verschieben: Positionen des Zieltitels danach 10, 20, …**, die verschobene übernimmt den Titel der Zielposition; `/reorder` bleibt für Titel (`moveSectionBefore`).
16. **Die Kalkulation lädt das LV nach jedem Speichern neu**, auch wenn sich der EP nicht ändert.
17. **Regel 26 "sauber" = `git status` ohne Änderungen** auf dem Commit des Berichts (eine frische Arbeitskopie); nach jeder Änderung laufen Suite und Klicktests neu.
18. **Regel 28: auch ein nur im Aufbau geänderter Test wird genannt** ("Soll gleich").

#### Tests und Prüfung

- Neu `tests/test_v404_hochladen_zeitlimit.py` (7): der Baustein in node mit gestelltem XMLHttpRequest -- Übertragung länger als das
  Zeitlimit ohne Abbruch, danach das gewöhnliche Zeitlimit, Antwortkopf als Ende der Übertragung, Reihenfolge im Bereich und Netzfehler
  (gescheitert, sperrt Abschließendes), Fehlerstatus als Response, Kopfzeilen und Methode, Text weiter über fetch, ohne XMLHttpRequest fetch.
- Neu `tests/test_v404_vorweg.py` (14, davon 8 gegen PostgreSQL): Dauertest `__dkZeitlimit`; Verschieben (node: nur `before_item_id`;
  Server: Reihenfolge und OZ aus dem gespeicherten Stand, auch mit einer inzwischen angelegten Position; **Angriffstest Regel 25**: fremde
  und unbekannte Positionen in Pfad und Body 404, sich selbst und leer 422, nichts geändert); Kalkulation (LV lädt im Bereich 'angebot' neu;
  eine inzwischen gewählte Position bleibt); **Angriffstests 96-19 gegen PostgreSQL** mit zwei gleichzeitigen Teil-Updates verschiedener
  Felder: Leistung (Stundensatz und Materialabweichung -- der gespeicherte Preis ist der aus der ganzen Kalkulation), Angebot (zwei
  Verschiebungen -- OZ passt zum gespeicherten Stand), Zeit- und Gruppenbuchung (Auftragswechsel und LV-Position des alten Auftrags: die zweite
  422, am Ende kein fremdes Paar, auch in der Mitgliedsbuchung), Materialbedarf (im selben Commit wie die Menge: während des Neuaufbaus sieht
  eine andere Sitzung die neue Menge nicht), Kontakt (Art und Firmenname: das Leeren wird abgelehnt); dazu der Nachweis der Sperre selbst
  (`SELECT … FOR UPDATE NOWAIT` scheitert, solange die erste Aktion hält) für Leistung, Verschieben und Titel ändern.
- **Angepasste Erwartungen** (altes -> neues Soll): `test_v399::test_a_final_action_does_not_run_if_a_running_save_fails` "U2 (nach dem
  Scheitern geklickt) gesendet" -> "U2 abgelehnt, nach einem gelungenen Speichern im selben Bereich geht U3 hinaus";
  `test_v399::test_a_save_failed_before_the_click_does_not_block` (umbenannt in
  `…_blocks_until_a_later_save_of_the_same_area_succeeds`) "U1 gesendet" -> "U1 abgelehnt, ein gelungenes Speichern in einem anderen
  Bereich hebt das nicht auf, eins im selben Bereich schon"; `test_v399_teil_updates_rest::test_baustein_null_ist_422_content_bleibt_
  ungeschrieben` (umbenannt in `…_content_wird_gespeichert`) "Zeile unverändert" -> "content gespeichert, alles andere unverändert";
  `test_v158::test_update_layout_block_ignores_content_for_predefined_blocks` (umbenannt in `…_stores_content_for_predefined_blocks`, im
  Gesamtlauf rot, Erwartung veraltet seit 1.8.99) "content bleibt None" -> "content gespeichert". Nur der Docstring: `test_two_final_actions_after_a_failed_save_are_both_refused_naming_it` (Soll gleich). Klicktest
  `klicktest_leistungszeitraum` (im Gesamtlauf 17/20, Erwartung veraltet seit 1.8.99): "nach 'Ende vor Beginn' finalisiert" -> "Finalisieren
  abgelehnt (gescheitertes Speichern), Ende wieder eingetragen und gespeichert, dann finalisiert" (+2 Prüfungen, 22/22). Listen: `ABSCHLIESSEND` +1, `NICHT_
  ABSCHLIESSEND` +2, Adressmuster +`charges` (`test_v399`); `AUSNAHMEN` −4 (`test_v400`, 37 -> 33); `GEPRUEFT` +2 (`test_v373`).
- Neu in `test_v399` (4): Fehlerstatus vor dem Klick sperrt, abgelehnte abschließende Aktion sperrt nicht, unklare abschließende Aktion
  sperrt, gescheitertes Lesen sperrt nicht; in `test_v400` (4): Aufruf aus dem HTML.
- Klicktest `scripts/klicktest_hochladen.py` (neu) 6/6.
- Gegenproben (Regel 24): 22 von 22 rot -- gescheitertes Speichern nicht gemerkt, nicht geprüft, abgelehnte abschließende Aktion sperrt; Uhr
  ab dem Senden, ohne XMLHttpRequest (je auch im Klicktest: "unklar" nach 2 s); Versand liest `__dkZeitlimit`; `content` verworfen; Scanner
  ohne HTML; Kalkulation füllt die andere Position, LV nicht neu geladen; `moveItemBefore` wie bis 1.8.98; Verschieben ohne ausdrückliche
  Zugehörigkeit (Strukturtest Regel 25 -- der Angriffstest blieb grün, weil eine fremde Position dann an einem KeyError scheitert, auch 404);
  Eingangsrechnung über `speichern()`; je ohne Sperre: Leistung (zuerst grün, weil beide Anfragen dieselbe Kalkulationszeile schrieben und
  dadurch ohnehin warteten -- der Test ändert seither eine andere Zeile), Angebot (zuerst grün, Zeilensperren beim Umnummerieren hielten die
  zweite Aktion ebenfalls auf -- seither der Nachweis mit NOWAIT), Zeitbuchung, Gruppenbuchung, Materialbedarf nach dem Commit, Kontakt;
  Suchseite außerhalb des Bausteins. Jede Datei byte-genau zurück, kein Marker.
- Volle Suite (mit den Tests gegen PostgreSQL) auf dem Arbeitsstand vor dem Commit: 4870 grün, 1 rot -- `test_v158` (siehe oben),
  angepasst, die Datei danach 23 grün. Alle Klicktests: 61 von 62 wie erwartet in 16:47 min, rot `klicktest_leistungszeitraum` 17/20
  (siehe oben), angepasst 22/22. Der Lauf nach Regel 26 auf dem Commit steht im Bericht zu 1.8.100.

#### Nebenbefunde (nur gemeldet)

1. **"Storniert" im Auftragskopf** ist ein freies Statusfeld ohne Folgen (keine Sperre, kein Beleg) -- deshalb nicht abschließend; ein
   echtes Storno eines Auftrags gibt es nicht.
2. **Vertragsentwurf ändern** (`PUT /api/orders/{id}/contract`) prüft den Status "Entwurf" ohne Sperre -- gleichzeitig mit dem
   Festschreiben könnte ein Text noch in den Entwurf gehen, nachdem die Fassung entstand (die Fassung selbst bleibt unverändert).
3. **Speichern im Hintergrund, das Fehler schluckt** (Outlook-Abgleich im Kalender, Layout des Dashboards), sperrt jetzt abschließende
   Aktionen seiner Seite bis zum nächsten gelungenen Speichern -- beide Seiten haben keine.
4. **Hochladen über XMLHttpRequest**: die Response hat kein `url`/`redirected` wie bei fetch (keine Seite nutzt sie).
5. **Der Neuaufbau des Materialbedarfs vergibt neue IDs** (wie bisher): eine offene Arbeitsvorbereitung bekommt beim Speichern einer
   ersetzten Zeile 404 und muss neu laden.

### Befund 1.8.100: Cookie-Flags, schreibende Anfragen von fremden Seiten, ungeschützte Daten in Seiten (Punkt 4, nur Befund)

Nichts am Code geändert. Jede Lücke steht als Test mit `xfail(strict=True)` in `tests/test_v405_befund_seiten.py` (er beschreibt das
gewünschte Verhalten; wird die Lücke geschlossen, schlägt xfail an und der Marker fällt weg); jeder davon mit `--runxfail` geprüft: er
scheitert genau an seiner Prüfung, nicht an seinem Aufbau. Die Suche nach ungeschützten Stellen in den Vorlagen hat ein lesender Helfer
vorbereitet; jeder Fund unten ist hier nachgestellt.

#### Befunde (Lücken, je ein xfail)

1. **Cookie `Secure` nur über `ERP_COOKIE_SECURE=1`** (Vorgabe aus), auch mit `ERP_ENV=production`. Fehlt der Eintrag in der `.env` des
   Servers, geht das Anmelde-Cookie auch über http (z. B. bei einem Aufruf von `http://app.dachkonzepte.gmbh` vor der Umleitung). Ob er auf
   dem Server gesetzt ist, ist von hier aus nicht prüfbar. Die übrigen Flags sind richtig (siehe unten).
2. **Kein Schutz schreibender Anfragen gegen Seiten derselben Site**: kein Abgleich von `Origin`/`Sec-Fetch-Site`, kein Token. Gegen fremde
   Sites schützt `SameSite=Lax` (moderne Browser schicken das Cookie bei einer seitenfremden POST-Anfrage nicht mit), und JSON-Endpunkte
   verlangen `application/json` -- eine fremde Seite käme nur nach einer CORS-Vorabanfrage durch, die der Server nicht beantwortet. Offen
   bleiben Seiten derselben Site (jede Unterdomain von `dachkonzepte.gmbh`, etwa die Firmenwebsite): sie können "einfache" Anfragen mit dem
   Anmelde-Cookie schicken -- an **154 schreibende Endpunkte ohne Body** (darunter Rechnung festschreiben und versenden, Storno, Mahnung
   versenden, Checkliste abschließen, Abmelden) und **30 mit Formular oder Datei** (Uploads, Logo, Importe). Ältere Browser ohne SameSite
   wären auch von fremden Sites aus offen.
3. **Kein Schutz gegen Einrahmen** (weder `X-Frame-Options` noch `Content-Security-Policy: frame-ancestors`): eine Seite derselben Site
   kann das ERP angemeldet in einem Rahmen zeigen und Klicks unterschieben (seitenfremde Rahmen bekommen das Lax-Cookie nicht).
4. **Hochgeladene Dateien als aktiver Inhalt** (schwerster Fund): Kundenakte, Projektmappe, Objekt (auch der Upload des Monteurs in
   /mobil, gleiche Ablage) liefern über `…/view` inline mit dem Typ aus, den der Browser beim Hochladen nannte -- ohne Prüfung des Inhalts,
   ohne `X-Content-Type-Options: nosniff`, ohne CSP. Eine SVG- oder HTML-Datei mit Skript (etwa eine per Mail eingegangene "Zeichnung")
   läuft beim Öffnen auf dem ERP-Ursprung, mit der Sitzung der Person, die öffnet -- ein Admin öffnet, das Skript handelt als Admin. Am
   Objekt werden Bilder neu kodiert (SVG scheitert dort), HTML bleibt. `can_preview_type()` zeigt für jedes `image/*` (auch SVG) den Link
   "Öffnen".
5. **Gruppenname eines Prüfpunkts im Einsatzbericht** (`service_reports.html::inspectionItemsPanelHtml()`): geht nur für JS geschützt
   (`\'`) in ein onclick-Attribut -- ein `"` beendet das Attribut, `<img onerror>` läuft beim Zeichnen. Setzen kann ihn jede Rolle, die den
   Bericht bearbeitet, auch der Monteur (`POST /api/service-reports/{id}/inspection-items`, ohne Längengrenze).
6. **"Neues Projekt" und "Neues Angebot"** (`project_form.html`, `quote_form.html`): Kundennummer und -name, Objektname und Ort, Projekt
   und Kunde gehen ohne Schutz in die Auswahl (innerHTML) -- ein Altkunde oder ein Name aus dem Adressimport mit `<img onerror>` läuft beim
   Öffnen der Seite (beide Seiten ohne esc()).
7. **Verknüpfungssuche im Kalender** (`calendar.html`): `JSON.stringify` im onclick-Attribut, nur `'` als `&#39;`; der Browser dekodiert
   `&quot;` im Attribut zu `"` -- ein Projekt- oder Angebotstitel mit `&quot;` beendet die Zeichenkette (Skript beim Klick).
8. **Planungsvorschlag der Plantafel** (`planning.html::calculateSuggestion()`): Namen abwesender Mitarbeiter und Feiertage ohne Schutz in
   innerHTML.

#### Geprüft und in Ordnung

- Anmelde-Cookie `HttpOnly`, `SameSite=Lax`, `Path=/`, `Max-Age` 12 h (wie die Sitzung); Cookie "vertrautes Gerät" `HttpOnly`,
  `SameSite=Lax`, 30 Tage; das alte Cookie des zweiten Faktors wird gelöscht (Test).
- JSON-Endpunkte nehmen kein JSON ohne `application/json` (`text/plain`, ohne Content-Type, Formular -> 422; Test).
- Jinja escapt alle `.html`-Vorlagen; nirgends `|safe`, `Markup(` oder `autoescape false` (Test); jedes `{{ … }}` in einem Skript ist eine
  Zahl, ein fester Text oder `|tojson`.
- **Outlook-Termine**: Titel, Ort, Notiz und Besitzer gehen überall, wo sie erscheinen (Kalender, Projektmappe, Angebots-Editor), durch
  `esc()` bzw. `auswahlOptionen()`. **Adressimport**: Vorschau, Arbeitsliste und Läufe über `esc()`. **Altkunden**: Kundenliste, Kundenakte,
  Objekt und Projektmappe über `esc()` -- offen nur die beiden Formulare aus Nr. 6. GAEB/Leistungen, Dateinamen in Listen,
  Lieferanten der Eingangsrechnungen ebenso geschützt.
- `product_url` am Betriebsmittel (als Link) nimmt nur http/https mit Host an (Validator im Schema); serverseitig gebaute Links
  (`source_url` der Aufgaben, Suchtreffer, Checklisten-Belege) bestehen aus IDs und festen Pfaden.

#### Weniger dringend (kein Weg für fremde Daten gefunden)

- Weitere onclick-Handler mit `'${esc(…)}'` (Checkliste, Prüfvorlagen, Einstellungen, Dachfläche) bekommen nur interne Schlüssel oder
  Optionswerte, die ein Admin pflegt -- dasselbe unsichere Muster wie Nr. 5 (esc() schützt das HTML, nicht die JS-Zeichenkette, denn der
  Browser dekodiert `&#39;` vor dem Ausführen).

#### Festlegungen 1.8.100 (bestätigt am 14.10.2026)

1. **"Fehler" = eine Lücke mit einem nachgestellten Angriff** (Nr. 1–8); was nur nach Muster unsicher aussieht, ohne Weg für fremde Daten, steht als "weniger dringend" ohne xfail.
2. **Gewünschtes Verhalten im xfail** (das der Test prüft): Secure in Produktion von selbst; schreibende Anfrage mit fremdem `Origin`/`Sec-Fetch-Site: same-site` 403; `X-Frame-Options` oder `frame-ancestors`; SVG/HTML aus Uploads nicht inline als aktiver Inhalt (Anhang oder CSP sandbox); jede genannte Stelle zeigt `<img onerror>` als Text.
3. **"Seite derselben Site" = jede Unterdomain von `dachkonzepte.gmbh`** -- wie viele es gibt und wer sie betreibt, ist von hier aus nicht prüfbar.
4. **Nr. 4 ist der dringendste Fund**, vor Nr. 5–8 (ein Upload erreicht jede Rolle, die die Datei öffnet).
5. **Was der Lauf nach Regel 26 im eigenen Test einer Version findet, behebt ein Nachtrag-Commit derselben Version** (keine neue Versionsnummer, Eintrag im Archiv), danach laufen Suite und Klicktests neu.

#### Tests und Prüfung

- Neu `tests/test_v405_befund_seiten.py` (15): 3 grün (Flags des Anmelde-Cookies, JSON nur mit `application/json`, kein `|safe`),
  12 `xfail(strict=True)` (Nr. 1, Nr. 2 zweimal, Nr. 3, Nr. 4 dreimal, Nr. 5, Nr. 6 zweimal, Nr. 7, Nr. 8); jeder mit `--runxfail`
  an seiner Prüfung gescheitert (drei scheiterten zuerst am eigenen Aufbau -- Herauslösen der Funktion, esc() mit Semikolon,
  fehlendes `_berlin_date.html` -- und wurden nachgebessert).
- Gegenproben (Regel 24): 5 von 5 rot -- Anmelde-Cookie ohne HttpOnly, `|safe` in einer Vorlage; drei Lücken probeweise geschlossen
  (X-Frame-Options, Escaping in "Neues Angebot", Secure in Produktion): XPASS, damit rot. Jede Datei byte-genau zurück, kein Marker.
- Volle Suite und alle Klicktests auf dem Commit dieser Version: im Bericht (Regel 26). Der erste Lauf auf `ae6c3a1` war rot an
  `test_v384::test_every_function_handing_database_url_to_a_child_checks_it`: der neue Test zu Nr. 1 gab `DATABASE_URL` an einen
  Kindprozess, ohne sie mit `pg_url_pruefen()` zu prüfen (Regel 27; harmlos, die URL war `sqlite://`, aber der Strukturtest hat recht).
  Im Nachtrag-Commit geprüft, danach Suite und Klicktests neu (Regel 26).

## Sicherheit der Seiten: Uploads, Daten im HTML, Anfragen fremder Seiten (ab 1.8.101)

### Vorgabe vom 14.10.2026 (übernommen wie gegeben)

Vorweg zu 1.8.98–1.8.100: Festlegungen bestätigt (98-5: 12 h passen dem Betrieb), mit diesen Korrekturen:
- 98-11: „Alle vertrauten Geräte abmelden“ beendet auch alle anderen Sitzungen. Rolle und Rechte werden bei jeder Anfrage frisch gelesen;
  Angriffstest: Rolle herabsetzen, die nächste Anfrage der laufenden Sitzung hat die neuen Rechte. Ein Admin kann alle Sitzungen eines
  Benutzers beenden.
- 98-12: Feierabend in /mobil beendet die Sitzung auf dem Server wie Abmelden.
- 99-6: richtig. Dazu ein Test mit Gegenprobe: Eine vom Server abgelehnte abschließende Aktion sperrt keine weitere.
- 99-10: Änderungen am Vertragsentwurf laufen unter derselben Sperre wie das Festschreiben; Gleichzeitigkeit gegen PostgreSQL.
- 99-13: nur Befund: Wo wird content eingegeben, wo erscheint es?
- Läuft die Sitzung beim Speichern ab, meldet der Bereich „Anmeldung abgelaufen“, die Eingaben bleiben stehen; nach Anmelden in einem neuen
  Tab lässt sich erneut speichern.

Die 12 xfail aus 1.8.100 werden grün und verlieren die Markierung:
1. Hochgeladene Dateien nie als aktiver Inhalt, an allen Stellen, die abgelegte Dateien ausliefern, über eine gemeinsame Funktion
   (Strukturtest). Den Typ bestimmt der Server. Im Browser angezeigt werden nur Rasterbilder und PDF, alles andere kommt als Download.
   Klicktest: SVG und HTML laufen nicht, Foto und PDF erscheinen weiter.
2. Daten im HTML: Nr. 5–8 beheben, dazu Strukturtests mit Ausnahmelisten, die nur kürzer werden: kein innerHTML/insertAdjacentHTML mit
   ${…} ohne esc(); keine on…-Attribute mit eingesetzten Werten, sondern data-Attribute und addEventListener (auch die Admin-Stellen aus dem
   Nebenbefund); jedes href/src aus Daten nur http(s), mailto, tel oder lokal.
3. Schreibende Anfragen ohne passenden Origin bekommen 403, auch von Unterdomains.
4. Kein Einrahmen der Seiten.
5. Secure am Anmelde-Cookie in Produktion ohne Schalter.

Reihenfolge: 1, 2, dann Vorweg, dann 3–5. Angriffstests mit Gegenprobe. Eigene Festlegungen mit „Bitte bestätigen“, je in einer Zeile.
Nebenbefunde nur melden. Wird der Umfang zu groß: nach Punkt 2 committen und den Rest auflisten. Commit nach Regel 13, Bericht kurz.

### Umsetzung 1.8.101: hochgeladene Dateien nie als aktiver Inhalt (Punkt 1, Befund 1.8.100 Nr. 4)

#### Was gebaut ist

- **Eine Funktion für jede abgelegte Datei**: `app/dateiauslieferung.py::datei_antwort(quelle, dateiname, herunterladen=, svg_als_bild=,
  kopfzeilen=)` (Pfad oder Inhalt). Den Typ bestimmt der Server an den ersten Bytes (`typ_aus_inhalt()`: PDF, PNG, JPEG, GIF, WebP), nie am
  Namen oder an der Angabe des Browsers -- auch für Einträge von vor 1.8.101. Inline nur diese fünf mit genau diesem Typ; alles andere als
  `application/octet-stream`, `Content-Disposition: attachment`, `Content-Security-Policy: sandbox`; immer `X-Content-Type-Options:
  nosniff`. Der Dateiname geht prozentkodiert in `filename*`, sobald er etwas anderes als einfache Zeichen enthält (kein Aufbrechen der
  Kopfzeile). Weitere Kopfzeilen (Cache) können Typ, Disposition, nosniff und CSP nicht ersetzen.
- **Umgestellt, 27 Aufrufe in 17 Routern**: Kundenakte, Projektmappe, Objekt (Büro und /mobil, je Anzeigen und Download), Abnahme-Belege,
  Mängel (Büro und Monteur), Checklisten-Anhänge und eingefrorene Vollmacht, Belege im Versandprotokoll, Vollmacht am Beteiligten,
  Eingangsrechnung, Betriebsmittel (Prüffrist und Dokument), Betriebskosten, Skizze der Dachfläche, Briefpapier (beide Routen),
  Berichtsfotos, Firmen- und Seitenleisten-Logo. Bis 1.8.100 lieferten Skizze und altes Briefpapier mit dem Typ der Endung aus, die der
  Browser genannt hatte ("plan.html" mit Angabe image/png lief als HTML), Kundenakte, Projektmappe und Objekt mit dem Typ des Browsers.
- **Typ beim Hochladen vom Server**: Kundenakte, Projektmappe, Lieferschein und Objekt speichern `gespeicherter_typ()` (anzeigbar oder
  `application/octet-stream`) statt der Angabe des Browsers; `is_image`/`can_preview` (Vorschau, "Öffnen", "Ansehen" in /mobil) gelten nur
  noch für Rasterbilder bzw. Rasterbilder und PDF (`app/document_storage.py`). Am Objekt entscheidet der erkannte Typ, ob neu kodiert wird;
  ein Rasterbild, das Pillow nicht lesen kann, bleibt unverändert ohne Vorschau (bis 1.8.100 ein 500, ebenso jedes als Bild gemeldete SVG).
- **SVG-Logo nur als Bild** (`svg_als_bild=True`, nur die beiden Logo-Endpunkte): ein am Inhalt erkanntes SVG geht als `image/svg+xml`, aber
  mit `attachment` und `Content-Security-Policy: sandbox; default-src 'none'; style-src 'unsafe-inline'; img-src data:` -- in der
  Seitenleiste (`<img>`) erscheint es, direkt geöffnet kommt es als Download und ohne Skript.
- **Strukturtest** (`tests/test_v406_dateien_nie_aktiv.py`, AST über `app/`): `FileResponse` kommt nur in `app/dateiauslieferung.py` vor;
  jede andere `Response`/`StreamingResponse` mit Inhalt trägt einen festen Typ (Text, `a if b else c` aus Texten, eine Variable mit nur
  solchen Zuweisungen) -- was der Server selbst erzeugt (PDF, PNG, CSV). Dazu die Zählung der Aufrufe je Router.
- **Klicktest-Werkzeug**: `Tab.downloads` sammelt `Page.downloadWillBegin` (jeder Download, den der Tab beginnt).
- **Klicktest `scripts/klicktest_dateien_nie_aktiv.py`** (neu): jedes Skript in den Testdateien schreibt in den localStorage des ERP.
  Kundenakte, Projektmappe, Objekt: SVG und HTML hochgeladen (Typ vom Server) und als Eintrag von vor 1.8.101 (Typ des Browsers) --
  Vorschaubild nur beim Foto, "Öffnen" nur bei Foto und PDF, jede view-Adresse direkt geöffnet: Foto als Bild, PDF als PDF, SVG und HTML als
  Download (Ereignis und Datei), kein Skript gelaufen; SVG-Logo mit Skript in der Seitenleiste sichtbar, direkt geöffnet ein Download;
  /mobil/objekt als Monteurin auf 412 px: "Ansehen" nur bei Foto und PDF, dieselben Prüfungen.

#### Festlegungen 1.8.101 (bestätigt am 14.10.2026; Nr. 4 korrigiert, siehe Vorgabe ab 1.8.105)

1. **Anzeigbar = JPEG, PNG, GIF, WebP und PDF**, erkannt an den ersten Bytes; alles andere (auch SVG, HTML, XML, Text, Office, BMP, TIFF, HEIC) als Download.
2. **Der Typ wird beim Ausliefern immer neu am Inhalt bestimmt**, auch für alte Einträge; gespeicherte Typen alter Einträge bleiben unverändert (keine Migration), sie bestimmen nur Vorschau und "Öffnen".
3. **Neue Einträge in Kundenakte, Projektmappe, Lieferschein und Objekt speichern den Typ des Servers** (`application/octet-stream`, wenn nicht anzeigbar); das DOC-/XLS-Symbol der Liste kommt dann aus der Endung des Namens.
4. **SVG nur beim Firmen- und Seitenleisten-Logo als Bild**, direkt geöffnet ein Download; überall sonst ist SVG ein gewöhnlicher Download.
5. **Was bisher als Download kam, bleibt Download** (Eingangsrechnung, Betriebsmittel, Betriebskosten, jedes `/download`), mit dem erkannten Typ.
6. **Vom Server erzeugte Dateien mit festem Typ** (PDFs, QR-Code, Symbol der App, CSV/DATEV) gehen nicht über `datei_antwort()`; der Strukturtest verlangt dort einen festen Typ.
7. **Objekt: ein Rasterbild, das Pillow nicht lesen kann, wird unverändert abgelegt** (ohne Vorschau, direkt geöffnet als Bild mit nosniff) statt eines 500; ein GIF wird wie bisher jedes Bild als JPEG abgelegt.
8. **Der Dateiname geht prozentkodiert** (`filename*=utf-8''…`), sobald er etwas anderes als Buchstaben, Ziffern und `-._~` enthält.

#### Tests und Prüfung

- Neu `tests/test_v406_dateien_nie_aktiv.py` (86): Erkennung am Inhalt (15 Fälle), die Antwort für zwölf Inhalte als Pfad, als Inhalt und als
  Download, SVG als Bild nur für echtes SVG, Dateinamen mit Anführungszeichen, Umlaut, Semikolon, Zeilenumbruch und Pfad, Kopfzeilen ersetzen
  nichts; **Angriffstests** über die Ablagen (SVG, HTML, HTML als "Foto", XHTML, XML mit Skript, dazu Foto mit falscher Angabe, PDF als
  octet-stream, GIF): Kundenakte, Projektmappe, Objekt im Büro und in /mobil (je Anzeigen und Download, auch über die Monteur-Wege),
  Einträge von vor 1.8.101, kaputtes Rasterbild am Objekt, Skizze, Briefpapier, beide Logos, Eingangsrechnung, Betriebsmittel (zwei Wege),
  Betriebskosten; Strukturtest mit sieben Umgehungen und vier erlaubten Fällen.
- `tests/test_v405_befund_seiten.py`: die drei Tests zu Nr. 4 ohne xfail (grün).
- **Angepasst** (Regel 28): `test_v326` legt das Objekt-Dokument ohne `content_type` an (Parameter entfällt, der Server bestimmt ihn) -- nur
  der Aufbau, Soll gleich.
- Klicktest `klicktest_dateien_nie_aktiv` 42/42 (mehrfach). Im ersten Lauf zählte er Downloads über den Ordner: Chrome überschreibt
  gleichnamige Dateien und benennt HTML-Downloads erst nach einer Prüfung um, dazwischen legte headless Chrome nach dem PDF-Betrachter eine
  `downloads.htm` an -- seither eindeutige Namen je Ablage und die Ereignisse des Tabs (Nebenbefund 1).
  **Nachtrag** (Lauf nach Regel 26 zu 1.8.104, eigener Commit nach Festlegung 1.8.100 Nr. 5): der Lauf brach mit `FileNotFoundError` ab --
  der Helfer `_direkt()` listete den Download-Ordner und las danach die Zeitstempel, dazwischen hatte Chrome eine Zwischendatei
  (`downloads.htm (1).crdownload`) schon wieder entfernt. Eine verschwundene Datei zählt jetzt nicht mehr (Soll gleich, nur Aufbau).
- Gegenproben (Regel 24): 13 von 13 rot -- Typ aus der Endung statt am Inhalt (auch im Klicktest: 21/42, Skript gelaufen), Kundenakte über
  `FileResponse` mit gespeichertem Typ, Abnahme-Beleg über `Response` mit gespeichertem Typ (Strukturtest), Kundenakte speichert den Typ des
  Browsers, Vorschau für jedes `image/*` (auch im Klicktest: Vorschaubild des alten SVG), SVG-Logo inline ohne CSP, Kopfzeilen ersetzen die
  Sicherheit, Dateiname roh, ohne nosniff, Strukturtest ohne Auflösung von Variablen; Objekt: Typ nicht am Inhalt, kaputtes Rasterbild ohne
  Rückfall. Eine dritte Objekt-Probe ("SVG als PNG gemeldet") blieb zuerst grün, weil der Rückfall für unlesbare Bilder sie abfing -- durch
  die beiden zuletzt genannten ersetzt. Jede Datei byte-genau zurück, kein Marker.
- Volle Suite und alle Klicktests: im Bericht (Regel 26).

#### Nebenbefunde (nur gemeldet)

1. **Headless Chrome legt nach dem Öffnen eines PDF gelegentlich eine `downloads.htm` im Download-Ordner an** und verwirft sie wieder -- kein
   Download der Seite (kein `Page.downloadWillBegin`).
2. **Eingangsrechnung, Betriebsmittel, Betriebskosten, Skizze und das alte Briefpapier prüfen beim Hochladen weiter nur die Angabe des
   Browsers** (PDF/Bild): eine HTML-Datei mit der Angabe "PDF" wird angenommen und abgelegt -- seit 1.8.101 als Download ohne Typ
   ausgeliefert, also harmlos, aber als "Beleg" unbrauchbar.
3. **Die Logo-Endpunkte geben weiter `max-age=31536000, immutable` an**; seit 1.8.98 ersetzt die Anmeldeschranke das für jede angemeldete
   Sitzung durch `no-store` -- die Angabe wirkt nie.

### Umsetzung 1.8.102: Daten im HTML (Punkt 2, Befund 1.8.100 Nr. 5–8)

#### Was gebaut ist

- **Nr. 5–8 behoben**: Gruppenname im Einsatzbericht und die Fläche gehen als data-Attribute statt als JS-Zeichenkette ins onclick
  (`service_reports.html`); "Neues Projekt" und "Neues Angebot" setzen Kundennummer, Kunde, Objekt, Ort, Kategorie und Projekt über esc()
  (beide Seiten hatten kein esc()); die Verknüpfungssuche im Kalender trägt Art, ID und Titel als data-Attribute statt JSON im onclick;
  der Planungsvorschlag der Plantafel setzt Feiertage und abwesende Mitarbeiter über esc().
- **Baustein `_aktionen.html`** (neu): ein Element trägt `data-klick="name"` (bzw. `data-aenderung`, `data-eingabe`) und seine Werte als
  data-Attribute (mit esc()); die Seite meldet `aktion('name', (el, ev) => …)` an, ein Listener am Dokument ruft sie mit dem innersten
  Element. Gesperrte Elemente lösen nichts aus; mehrfach einbindbar (eine Teilvorlage, die ihn nutzt, bindet ihn selbst ein).
- **Werte in on…-Attributen**: jede Stelle mit Text umgebaut (66, alle aus dem Nebenbefund 1.8.100 eingeschlossen) -- Einsatzbericht,
  Kalender, Versandverlauf (`_email_dispatch.html`), Mängel, Checkliste (Wahl, Optionen, Brief erstellen und senden), Kundenakte und
  Projektmappe (Kategorien und Unterordner -- dort schützte `esc(c).replace(/'/g,"\\'")` nichts, esc() macht aus ' schon &#39;),
  Dashboard (Widgets), Einstellungen (Rechtstexte, Klauseln, Vorbehalte, Vertragsvorlagen und ihre Abschnitte, Module, Nummernkreise,
  Reihenfolge der Schichttypen), Dachfläche (Ausführung), Suche, Prüfvorlagen, Finanzen, Verzugsbeginn. Übrig sind 375 Stellen mit Zahlen
  und IDs (Ausnahmeliste).
- **Jeder übrige Wert in HTML über esc()**: 246 Stellen, die der Scanner nicht als sicher beweisen kann (fast alle Zahlen: Fassungen,
  Mengen, Zähler, Beträge aus Feldern), automatisch in die esc-Funktion der Datei gefasst (`esc`, in `_email_dispatch.html` `_dhEsc`, in
  `_topbar.html` `escHtml`; `account.html` bekam ein esc()); der linke Teil von `a || b` bzw. `a ?? b` als Ganzes (`esc(a||b)`), damit
  sich 0 und false nicht ändern; eine Rechnung (`p.left+4` in der Plantafel) als Ganzes. Von Hand: die Art eines Betriebsmittels (neben
  HTML-Badges), die Kontexte einer Checklisten-Vorlage, die Pausenregeln eines Arbeitszeitmodells. Übrig: das Changelog (HTML aus
  CHANGELOG.md, vom Server maskiert).
- **Links aus Daten**: Baustein `_links.html` (neu) mit `sichererLink(wert, ersatz='#')` -- nur http(s)://, mailto:, tel:, ein lokaler
  Pfad nach `istLokalesZiel()` (dieselbe Regel wie Weiterleitungen) oder "#…"/"?…" -- und `sichereBildquelle()` (zusätzlich
  data:image/png|jpeg|gif|webp;base64, ohne mailto/tel). 19 Stellen umgestellt (Belege, Fotos, Unterschriften und Folgen der Checkliste,
  Abnahme und Protokoll, Mängel-Aufgabe, Suche oben und Suchseite, Dashboard-Aufgaben, Aufgaben, Beteiligte, Adressbuch, Produktlink des
  Betriebsmittels, QR-Code der Zwei-Faktor-Einrichtung).
- **Scanner `tests/vorlagen_html.py`** (neu, Tokenizer aus `tests/vorlagen_js.py`): HTML ist ein Template-Literal oder eine Verkettung
  mit Markup und jeder Wert eines HTML-Ziels (innerHTML, outerHTML, insertAdjacentHTML, document.write); ein HTML-Zustandsautomat
  liefert je Wert den Zusammenhang (Text, Tag, Attribut samt festem Anfang des Werts). Sicher ist, was kein Markup enthalten kann
  (Regeln im Kopf des Moduls); Parameter über ihre Aufrufstellen, Rückrufe von map/forEach … (Index, Elemente), Variablen über ihre
  Zuweisungen samt push/Index-Zuweisungen, feste Tabellen, Funktionen im Gültigkeitsbereich, Teilvorlagen im Zusammenhang jeder Seite, die
  sie einbindet. Gemeldet wird der kleinste ungeschützte Ausdruck, bei einer Variable mit HTML die Teile ihrer Zuweisungen (dort wird
  behoben).

#### Festlegungen 1.8.102 (bestätigt am 14.10.2026; zu Nr. 2: einmal alle Text-IDs prüfen, siehe Vorgabe ab 1.8.105)

1. **Text-Werte in on…-Attributen sind umgebaut, Zahlen und IDs (375) stehen in der Ausnahmeliste**, die nur kürzer wird.
2. **"Sicher" nach den Regeln im Kopf von `tests/vorlagen_html.py`**; ein Feld "id"/"…_id" gilt als Zahl, außer TEXT_IDS -- ein Test prüft an Modellen und Antwortschemas, dass jedes Text-Feld unter diesem Namen dort steht (gefunden: `series_master_id`).
3. **Was der Scanner nicht beweisen kann, geht durch esc()**, auch Zahlen -- statt in eine Ausnahmeliste; null/undefined erscheinen dadurch leer statt als "null"/"undefined".
4. **`a || b` und `a ?? b` werden als Ganzes gefasst**, nie nur `a` (0 und false bleiben falsch); eine Rechnung ebenso.
5. **Ein Wert in einem on…-Attribut zählt nur unter "Handler"**, nicht unter "ohne esc()" -- esc() hilft dort nicht.
6. **Verkettungen ('<td>'+x+'</td>') zählen wie ${…}**.
7. **Eine Teilvorlage wird im Zusammenhang jeder Seite gelesen, die sie einbindet**; eine Funktion ohne Aufrufstelle in einem Zusammenhang läuft dort nicht (ihre Parameter gelten als sicher), eine aus einem on…-Attribut gerufene hat unbekannte Parameter.
8. **Ausnahme Changelog**: HTML aus CHANGELOG.md, der Server maskiert den Text vorher.
9. **Erlaubte Links**: http(s), mailto, tel, lokal wie bei Weiterleitungen, "#…", "?…"; sonst '#'. Bildquellen zusätzlich data:image (PNG, JPEG, GIF, WebP) als base64, kein mailto/tel.
10. **Ein fester Anfang eines href/src gilt als geprüft**, wenn er mit "/" (nicht "//", "/\"), "#", "?", mailto:, tel: oder http(s):// beginnt -- wie bei Weiterleitungen (Festlegung 1.8.98 Nr. 4).
11. **`.action =` zählt nicht als Link** (meist ein Feld eines Objekts, z. B. `payload.action`); `setAttribute('action', …)` schon.
12. **Aktionen: data-klick, data-aenderung, data-eingabe**; ein gesperrtes Element und ein Name ohne Funktion lösen nichts aus; der Listener hängt einmal je Seite.
13. **Die Ausnahmelisten zählen je Schlüssel "Datei | Funktion | Ausdruck"**: eine weitere gleiche Stelle in derselben Funktion fällt auf.

#### Tests und Prüfung

- Neu `tests/test_v407_daten_im_html.py` (68): die drei Strukturtests (ohne esc: 1 Ausnahme; Handler: 375 Ausnahmen in 191 Schlüsseln; Links:
  keine), Jinja-Werte in on…-Attributen (keine), die Handler-Liste enthält nur Zahlen/IDs; der Scanner an 22 Funden, 18 sicheren Fällen,
  Handlern, zehn Link-Funden und fünf geprüften Links; jede esc-Variante der Vorlagen in node (alle fünf Zeichen), die Datumsfunktionen, die
  als Ziffern gelten, **Angriffstabelle** für `sichererLink()`/`sichereBildquelle()` (27 Werte: javascript: in vier Schreibweisen, mit
  Tab und Steuerzeichen, vbscript:, data:text/html, data:image/svg+xml, //, /\, /Tab/, /%2F/, Rückstrich im Host, Leerzeichen, fremder Host
  ohne Schema, leer, keine Zeichenkette), der Baustein `_aktionen.html` in node (Wert mit ' und ", gesperrt, unbekannt, change, zweimal
  eingebunden), TEXT_IDS gegen Modelle und Schemas.
- `tests/test_v405_befund_seiten.py`: Nr. 5, Nr. 6 (zweimal) und Nr. 8 ohne xfail.
- **Angepasste Erwartungen** (Regel 28): `test_v405::test_vorschlag_der_verknuepfungssuche_bleibt_daten` "das onclick-Attribut dekodiert zu
  pickLink(<JSON>)" -> "kein on…-Attribut, data-art/-id/-label dekodieren zum Treffer, pickLink bekommt die Werte aus dem Element"; Nr. 5, 6,
  8 nur xfail entfernt (Soll gleich). Nur Aufbau: `test_v334::seite()` bindet `_aktionen.html`, `_weiterleitung.html`, `_links.html` ein (die
  Seitenskripte melden Aktionen an); Klicktest `klicktest_maengel` sucht die Knöpfe Freigabe/Status über `data-art` statt `onclick*=` (Soll
  gleich -- die alte Suche hätte nach dem Umbau immer "keiner" ergeben und die Prüfung still bestanden);
  `test_v105::test_backoffice_ui_exposes_project_order_and_calendar_week_fields` sucht den Quelltext `KW ${esc(m.valid_from_week` statt
  `KW ${m.valid_from_week` (Soll gleich: die Kalenderwochen stehen in der Liste; der Test liest den Text wörtlich und war in der vollen
  Suite rot, nachdem esc() dazukam).
- Neuer Klicktest `scripts/klicktest_daten_im_html.py` 21/21: Kunde, Unterordner, Gruppe eines Prüfpunkts, Projekt und Art eines
  Betriebsmittels mit `"><img onerror>`, `');…//` und `&quot;…` -- kein Skript auf sieben Seiten, Namen als Text, die umgebauten Knöpfe
  tun es weiter mit genau dem gespeicherten Wert (Unterordner filtern in Kundenakte und Projektmappe, Gruppe zu und auf, Vorschlag im
  Kalender verknüpft, Modul-Schalter aus und an).
- Gegenproben (Regel 24): 15 von 15 rot -- Nr. 5 wieder im onclick (auch im Klicktest), Nr. 6 und Nr. 8 ohne esc(), Nr. 7 wieder JSON im
  onclick, Unterordner der Kundenakte wieder im onclick (auch im Klicktest), eine Fassungsnummer ohne esc(), Art des Betriebsmittels ohne
  esc() (auch im Klicktest: Skript gelaufen), ein Link ohne `sichererLink()`, `sichererLink()` lässt javascript: durch, Aktion auf
  gesperrtem Element, Listener ohne Wächter (doppelt), Scanner ohne push, jede "…_id" als Zahl, TEXT_IDS ohne `series_master_id`, Handler
  mit esc() nicht gemeldet. Jede Datei byte-genau zurück, kein Marker.
- Volle Suite und alle Klicktests: im Bericht (Regel 26).

#### Nebenbefunde (nur gemeldet)

1. **`tests/vorlagen_js.py::_ausdruck_ende()` beendet den Rumpf eines Pfeils ohne Klammern an der ersten schließenden Klammer eines
   Aufrufs auf oberster Ebene** (`s => String(s ?? '').replace(…)` endet nach `String(s ?? ''`): die Funktionsbereiche von `a.funktionen`
   sind für solche Pfeile zu kurz. Der neue Scanner nutzt eigene Bereiche; ob die Scanner von test_v398/test_v400 dadurch etwas übersehen,
   ist nicht untersucht.
2. **375 on…-Attribute mit Zahlen und IDs** (Ausnahmeliste) -- harmlos, solange die Werte Zahlen sind, aber dasselbe Muster.
3. **Zahlen aus Antworten des Servers lassen sich im Browser nicht als Zahl beweisen** (Fassung, Menge, Zähler): sie gehen jetzt durch esc();
   ein Feld, das später Text trägt, wäre damit schon geschützt.

### Umsetzung 1.8.103: Vorweg -- Sitzungen, Feierabend, „Anmeldung abgelaufen“, Vertragsentwurf (Korrekturen zu 1.8.98–1.8.100)

Die Festlegungen 1.8.98–1.8.100 sind bestätigt (98-5: 12 h passen dem Betrieb), mit den Korrekturen aus der Vorgabe oben.

#### Was gebaut ist

- **98-11 „Alle vertrauten Geräte abmelden“** (`POST /api/account/trusted-devices/revoke-all`) beendet im selben Commit alle anderen
  Sitzungen des Kontos (`app/sitzungen.py::andere_beenden()`), dieses Gerät bleibt mit seiner Sitzung angemeldet; die Antwort nennt
  `sitzungen_beendet`.
- **98-11 Administrator beendet alle Sitzungen eines Benutzers**: `POST /api/users/{id}/end-sessions` (nur Admin, `alle_beenden()`); fremde:
  jede Anmeldung endet; die eigenen: dieses Gerät bleibt mit einer neuen Sitzung angemeldet (wie beim eigenen Passwort, Festlegung 1.8.98
  Nr. 6). Benutzerverwaltung: Spalte „Sitzungen“ (Zahl der geltenden, `AppUserOut.active_sessions`, nur gelesen) und Knopf „Alle Sitzungen
  beenden“ mit Rückfrage, sichtbar, solange es Sitzungen gibt.
- **98-11 Rolle je Anfrage**: war seit 1.8.98 so (die Anmeldeschranke liest Benutzer und Rolle bei jeder Anfrage aus der Datenbank,
  `require_min_role()`/`require_admin()` prüfen `request.state.erp_user`); neu ist der Angriffstest dazu.
- **98-12 Feierabend**: `GET /api/field-view/today` nach `shift_end_time` beendet die Sitzung auf dem Server (`sitzungen.beenden()`, Commit),
  dann 401 und Cookie löschen wie bisher. Nur diese Sitzung -- ein zweites Gerät desselben Monteurs bleibt angemeldet, wie beim Abmelden.
- **99-10 Vertragsentwurf**: `app/contract_templates.py::update_contract_draft()` liest den Vertrag unter der Zeilensperre des
  Festschreibens (`_locked_contract()`, FOR UPDATE) und prüft den Status danach frisch. Ein gleichzeitiges Festschreiben wartet auf die
  Änderung (der Text steht in der Fassung) oder die Änderung wartet und wird danach abgelehnt („Nur ein Vertragsentwurf kann geändert
  werden …“). `freeze_contract()` und `start_new_version()` sperrten schon.
- **„Anmeldung abgelaufen“**: schickt eine Anfrage ein Anmelde-Cookie ohne gültige Sitzung (abgelaufen, abgemeldet, beendet), antwortet die
  Anmeldeschranke (`app/anmeldeschranke.py`) auf API-Anfragen mit 401, Kopfzeile `X-DK-Anmeldung: abgelaufen` und dem Text
  `ANMELDUNG_ABGELAUFEN`; ohne Cookie wie bisher „Bitte zuerst als ERP-Benutzer anmelden.“, Seiten weiter auf `/login`. Der Baustein
  `_speichern.html` prüft jede Antwort eines Speicherns (in der fetch-Hülle, also auch wo `api()` bei einem Fehler wirft) und zeigt oben den
  Hinweis (`#dkAnmeldungAbgelaufen`, Farben aus `--warning`); der Bereich meldet den Text des Servers, das Speichern gilt als gescheitert
  (abschließende Aktionen warten, Regel 29), keine Weiterleitung, die Eingaben bleiben. Ein späteres gelungenes Speichern -- nach dem Anmelden
  in einem neuen Tab, dessen Cookie auch hier gilt -- nimmt den Hinweis weg.
- **99-6** (eine vom Server abgelehnte abschließende Aktion sperrt keine weitere): der Test steht seit 1.8.99
  (`tests/test_v399_abschliessen.py::test_a_final_action_refused_by_the_server_does_not_block_another`); die Gegenprobe ist jetzt gelaufen
  (unten), am Code nichts geändert.

#### Befund 99-13: `content` der Layout-Bausteine (nur Befund)

- **Eingegeben**: nirgends in der Oberfläche. Einstellungen → Dokumentlayout schickt nur `visible` („anzeigen“) bzw. `y_mm` (Position des
  Folgeseiten-Kopfs). Schreiben lässt sich `content` nur über `PUT /api/document-layout/blocks/{id}` (ab `buero_auftrag`, seit 1.8.99
  gespeichert, `app/document_layout.py::update_layout_block()`), Spalte `Text` ohne Längengrenze; die Grunddaten legen die vier Bausteine
  mit leerem `content` an.
- **Erscheint**: nur in den JSON-Antworten von `GET /api/document-layout/{typ}`, des PUT und von `POST …/reset` (`DocumentLayoutBlockOut`).
  Keine Vorlage zeigt ihn (`settings.html` liest ihn nicht), kein PDF zeichnet ihn -- `app/document_frame.py` setzt Logo, Absenderzeile,
  Firmenkopf und Fußzeile aus den Einstellungen bzw. Dokumentdaten. Damit ist er heute weder ein Weg für Skript in eine Seite noch für Text
  in ein Dokument; erst eine Oberfläche oder ein Renderer, der ihn liest, müsste ihn wie jeden Text behandeln (esc(), Paragraph-Escaping).

#### Festlegungen 1.8.103 (bestätigt am 14.10.2026; Nr. 2 und 3 korrigiert, siehe Vorgabe ab 1.8.105)

1. „Alle vertrauten Geräte abmelden“ beendet alle anderen Sitzungen des Kontos; dieses Gerät behält seine Sitzung (kein neuer Cookie-Wert).
2. „Alle Sitzungen beenden“ (Admin) lässt vertraute Geräte bestehen (sie ersparen nur den zweiten Faktor) und geht auch für einen
   inaktiven Benutzer (dort ohnehin keine); für sich selbst bleibt dieses Gerät mit neuer Sitzung angemeldet.
3. Der Feierabend-Aufruf `GET /api/field-view/today` ist die einzige Stelle, an der ein GET schreibt (er löscht die eigene Sitzung) --
   bewusste Ausnahme von Regel 23, `test_kein_get_schreibt` sieht sie nicht (feste Uhr 10:00).
4. Feierabend beendet nur die Sitzung dieses Geräts, nicht alle des Monteurs (wie Abmelden).
5. „Anmeldung abgelaufen“ heißt: Cookie mitgeschickt, aber keine gültige Sitzung -- abgelaufen, abgemeldet, beendet, deaktiviert; ohne
   Cookie bleibt es „Bitte zuerst … anmelden“. Seitenaufrufe führen weiter auf `/login`.
6. Den Hinweis oben zeigt nur Speichern und Abschließen (der Baustein); ein Lesen mit abgelaufener Anmeldung zeigt den Text des Servers am
   Bereich, ohne Hinweis oben. Der Text nennt „erneut speichern“ auch dort.
7. `GET /api/users` liefert je Benutzer `active_sessions` (Zahl der nicht abgelaufenen Sitzungen) -- nur Lesen, nur Admin.

#### Tests und Prüfung

- Neu `tests/test_v408_vorweg.py` (23, davon 2 gegen PostgreSQL): **Angriffstests** Rolle herabgesetzt (Büro Finanzen -> Monteur und zurück,
  Admin -> Büro Finanzen an `/api/users`, Anlegen, Sitzungen beenden: ab der nächsten Anfrage derselben Sitzung 403/200), „alle vertrauten
  Geräte“ (die mitgelesenen Werte der anderen Geräte 401, dieses Gerät 200, anderer Benutzer unberührt), Admin beendet alle eines Benutzers
  (Werte 401, Anzahl in der Liste, neu anmelden geht), seine eigenen (alter Wert auch hier 401, neuer gilt), nur Admin (drei Rollen 403),
  unbekannt 404, Feierabend (der Wert des Tablets von außen 401, zweites Gerät 200), vor dem Feierabend bleibt sie; „Anmeldung abgelaufen“
  (abgelaufen, abgemeldet, beendet: 401 mit Kopfzeile; ohne Cookie ohne), Baustein in node (Hinweis da, Fehler am Bereich, abschließende
  Aktion gesperrt, gelungenes Speichern nimmt den Hinweis weg; fetch direkt; 401 ohne Kopfzeile ohne Hinweis); **PostgreSQL**: Festschreiben
  hält die Sperre, die Änderung wartet und wird abgelehnt (Fassung ohne den Text); umgekehrt steht der Text in der Fassung.
- Klicktest `scripts/klicktest_anmeldung_abgelaufen.py` 13/13: Kundenakte geändert, Admin beendet Beas Sitzungen von außen, Speichern -> PUT
  401, „Fehler: Anmeldung abgelaufen –“ am Bereich, Hinweis oben, keine Navigation, Eingaben stehen, kein Dialog, Server unverändert; im
  zweiten Tab über das Formular angemeldet; derselbe Klick „Gespeichert.“, Hinweis weg, Server gespeichert; ohne Cookie 401 ohne Kopfzeile.
  Dafür `scripts/cdp_klicktest.py`: `Tab.zweiter_tab()` (weiterer Tab desselben Browsers über `/json/new`, am Ende geschlossen).
  **Nachtrag** (beim Bau von 1.8.104 gefunden, eigener Commit nach Festlegung 1.8.100 Nr. 5): die Prüfung „ohne Cookie: 401 ohne
  ‚abgelaufen‘“ las die Kopfzeile als `X-DK-Anmeldung` aus einem `dict` der Antwort -- der Server schickt die Namen klein, sie war also immer
  `None` und die Prüfung bestand auch ohne die Unterscheidung. Jetzt mit kleinen Namen, dazu eine Prüfung „alter Wert: 401 mit ‚abgelaufen‘“
  (der beendete Cookie-Wert von außen); 14/14.
- Gegenproben (Regel 24): 8 von 8 rot -- Rolle aus dem Sitzungsbeginn zwischengespeichert, „alle vertrauten Geräte“ ohne Sitzungen,
  Admin beendet nichts, Feierabend nur Cookie, Anmeldeschranke ohne Kopfzeile, Baustein prüft nur die Rückgabe (auch im Klicktest: Hinweis
  fehlt), 99-6: abgelehnte abschließende Aktion setzt „gescheitert“, Vertragsentwurf ohne Sperre (PostgreSQL). Jede Datei byte-genau zurück,
  kein Marker.
- Angepasste Erwartungen: Klicktest `klicktest_anmeldung_abgelaufen` „ohne Cookie: 401 ohne ‚abgelaufen‘“ liest die Kopfzeile
  `x-dk-anmeldung` statt `X-DK-Anmeldung` (Soll gleich: keine Kopfzeile; vorher immer bestanden), neue Prüfung „alter Wert: 401 mit
  ‚abgelaufen‘“ (Nachtrag).

#### Nebenbefunde (nur gemeldet)

1. **`GET /mobil` prüft den Feierabend nicht**, obwohl `is_past_shift_end()` und der Docstring von `MobileSettings` „GET /mobil und GET
   /api/field-view/today“ nennen -- nur der API-Aufruf prüft; die Seite lädt, ihr erster Aufruf von `/api/field-view/today` meldet dann ab.
2. **`field_timesheet.html` und `time_tracking_field.html` leiten bei jedem Fehler mit „401“ im Text beim ersten Laden auf `/login`** -- dort
   ohne Eingaben unschädlich, aber eine Erkennung über den Text der Meldung.

### Umsetzung 1.8.104: Anfragen fremder Seiten, Einrahmen, Secure (Punkte 3–5, Befund 1.8.100 Nr. 1–3)

#### Was gebaut ist

- **Punkt 3, Ursprung** (`app/anmeldeschranke.py::ursprung_passt()`, als Erstes in der Middleware, ohne Datenbank): eine schreibende
  Anfrage (POST, PUT, PATCH, DELETE) geht nur durch, wenn `Sec-Fetch-Site` `same-origin` ist; ohne diese Kopfzeile, wenn `Origin` http(s)
  ohne Pfad ist und Host samt Port der Kopfzeile `Host` entspricht; sonst 403 „Anfrage von einer fremden Seite abgelehnt.“ und
  `logger.warning` mit Methode, Pfad und den beiden Kopfzeilen. Gilt für jeden Pfad, angemeldet oder nicht (auch `/api/auth/login`).
- **Punkt 4, Einrahmen** (`_schutzkoepfe()`): jede Antwort der Schranke -- Seiten, API, Weiterleitungen, 401/403, Dateien -- trägt
  `X-Frame-Options: DENY` und `Content-Security-Policy: frame-ancestors 'none'`; hat ein Endpunkt schon eine CSP (Dateien: `sandbox`), wird
  `frame-ancestors` angehängt. Keine Vorlage rahmt eine Seite des ERP ein (kein iframe/embed/object), `DENY` statt `SAMEORIGIN`.
- **Punkt 5, Secure** (`app/auth.py`): `COOKIE_SECURE = IS_PRODUCTION or ERP_COOKIE_SECURE` -- mit `ERP_ENV=production` immer, auch mit
  `ERP_COOKIE_SECURE=0`; gilt für das Anmelde-Cookie und das Cookie „vertrautes Gerät“. `.env.example` sagt das.
- **Tests über die echte Schranke**: `tests/anmeldung.py::browser_client()` schickt `Origin: http://testserver` und `Sec-Fetch-Site:
  same-origin` wie ein Browser auf einer Seite des ERP; `client_mit_schranke()`, `test_v402` und `test_v292` nehmen ihn.

#### Festlegungen 1.8.104 (bestätigt am 14.10.2026; Nr. 8 korrigiert, siehe Vorgabe ab 1.8.105)

1. Geprüft werden POST, PUT, PATCH und DELETE auf allen Pfaden (API, Seiten, Anmelden, Abmelden), mit und ohne Anmeldung; GET, HEAD und
   OPTIONS nie.
2. Zuerst zählt `Sec-Fetch-Site`: nur `same-origin`; `same-site` (Unterdomain), `cross-site`, `none` und jeder andere Wert -> 403, auch wenn
   `Origin` passt.
3. Ohne `Sec-Fetch-Site` (ältere Browser) muss `Origin` passen (http/https, ohne Pfad, Host samt Port = Kopfzeile `Host`); fehlt sie, ist sie
   leer oder `null` -> 403. `Referer` wird nicht ausgewertet.
4. Mit `Sec-Fetch-Site: same-origin` wird `Origin` nicht zusätzlich mit `Host` verglichen -- so hängt die Prüfung nicht davon ab, welchen
   `Host` Nginx weitergibt (die Konfiguration liegt nicht im Repo und ist von hier nicht prüfbar).
5. Kein Token (Synchronizer oder Double-Submit): die Kopfzeilen setzt der Browser selbst, eine Seite kann sie nicht fälschen; ein Token
   hätte jede schreibende Anfrage aller Vorlagen geändert.
6. Ablehnung als 403 „Anfrage von einer fremden Seite abgelehnt.“ mit `logger.warning` (nur Metadaten, Regel 18).
7. Einrahmen: `DENY` und `frame-ancestors 'none'` an jeder Antwort der Schranke, an Dateien an die Sandbox angehängt; eine 500 aus dem
   Fehler-Handler außerhalb der Schranke trägt sie nicht (Nebenbefund 2).
8. Secure: mit `ERP_ENV=production` immer, ein `ERP_COOKIE_SECURE=0` ändert dort nichts; außerhalb der Produktion weiter über
   `ERP_COOKIE_SECURE`.
9. Tests über die echte Schranke schicken `Origin` und `Sec-Fetch-Site` der eigenen Seite (`browser_client()`); ein Test des Ursprungs baut
   seinen Client ohne.

**Vor dem Einspielen (Betreiber)**: moderne Browser schicken `Sec-Fetch-Site` (Chrome, Edge, Firefox, Safari ab 16.4) -- dort hängt nichts
an Nginx. Ein älteres Tablet ohne sie (Safari vor 16.4) speichert nur, wenn Nginx den Host weitergibt (`proxy_set_header Host $host;`),
sonst 403. Nach dem Einspielen einmal auf einem Fahrzeug-Tablet speichern; ein 403 steht als Warnung im Log des Dienstes.

#### Tests und Prüfung

- Neu `tests/test_v409_ursprung_und_rahmen.py` (113): **Angriffstabelle** 15 Ursprünge × POST/PUT/PATCH/DELETE -> 403 (Unterdomain, Unterdomain
  mit gefälscht passendem Origin, fremde Site, Adresszeile, unbekannter Wert; ohne Sec-Fetch-Site: Unterdomain, Host als Präfix, anderer
  Port, Benutzerteil, mit Pfad, anderes Schema, null, leer; nur Referer; gar nichts), 5 erlaubte × 4 Methoden (eigene Seite, Origin vom Proxy
  umgeschrieben, Großbuchstaben, Origin passt), Lesen von überall, Upload und Abmelden von der Unterdomain ändern nichts (kein Dokument,
  Sitzung lebt), Anmelden von fremder Seite 403 ohne Cookie, die Funktion direkt, `app.main` bindet die Schranke ein; **Rahmen** ohne
  Anmeldung (Anmeldeseite, API, Weiterleitung), angemeldet, Dateien mit Sandbox (auch SVG als Bild), Rundgang über alle GET-Routen als
  Administratorin und Monteurin; **Secure** in sechs Umgebungen (Unterprozess), Set-Cookie mit Secure.
- `tests/test_v405_befund_seiten.py`: Nr. 1, Nr. 2 (zweimal) und Nr. 3 ohne xfail -- die Datei hat keinen xfail mehr.
- Klicktest `scripts/klicktest_fremde_seite.py` 9/9: zweiter Server auf 127.0.0.1 (anderer Port = dieselbe Site): Rahmen auf `/account`
  nicht angezeigt (`chrome-error://`), Upload, Abmelden, Anmelden per `no-cors` -> 403, weiter angemeldet, kein Dokument; die eigene Seite
  speichert und lädt hoch; Anmeldeseite mit `X-Frame-Options: DENY`.
- Gegenproben (Regel 24): 8 von 8 rot -- keine Ursprungsprüfung (auch im Klicktest: die fremde Seite lud ein Dokument hoch und meldete Bea
  ab, 200), Unterdomain erlaubt (ebenso), ohne Origin erlaubt, nur Hostname ohne Port (auch Benutzerteil durch), kein X-Frame-Options,
  Schranke ohne Schutzkopfzeilen (auch im Klicktest: Rahmen angezeigt), Sandbox der Dateien ersetzt statt ergänzt, Secure nur mit Schalter.
  Jede Datei byte-genau zurück, kein Marker.
- **Angepasste Erwartungen** (Regel 28): `test_v405` Nr. 1, 2 und 3 nur xfail entfernt (Soll gleich). Nur Aufbau: `tests/anmeldung.py`
  `client_mit_schranke()` über `browser_client()`; `test_v402::Welt.client()` und die vier Clients in `test_v292` über `browser_client()`
  (Soll gleich -- ohne Origin bekämen ihre schreibenden Anfragen jetzt 403); `test_v403::_rundgang()` hält zusätzlich `X-Frame-Options`
  und CSP fest (Soll der eigenen Tests gleich, test_v409 prüft sie).

#### Nebenbefunde (nur gemeldet)

1. **Kein HSTS** (`Strict-Transport-Security`) in der Anwendung -- gehört zu Nginx; ob es dort gesetzt ist, ist von hier nicht prüfbar.
2. **Eine 500 aus dem Fehler-Handler von Starlette** (außerhalb der Middleware) trägt weder `Cache-Control: no-store` noch die
   Rahmen-Kopfzeilen -- sie enthält nur „Internal Server Error“, keine Daten.

### Stand nach 1.8.104: Sicherheit der Seiten

Alle zwölf Tests aus Befund 1.8.100 sind grün und ohne xfail: Uploads nie als aktiver Inhalt (1.8.101, Regel 31), Daten im HTML (1.8.102,
Regel 32), Ursprung schreibender Anfragen, Einrahmen und Secure (1.8.104, Regel 33).

## Sicherheit der Seiten, Nacharbeiten: Scanner, Sitzungen, Schutzkopfzeilen (ab 1.8.105)

### Vorgabe vom 14.10.2026, zweite (übernommen wie gegeben)

Vorweg zu 1.8.101–1.8.104: Festlegungen bestätigt, mit diesen Korrekturen:
- 101-4: Auch das SVG-Logo kommt mit Sandbox, wenn man seine Adresse direkt öffnet.
- 102-2: Einmal prüfen, ob alle Text-IDs (Outlook, UUID u. ä.) in TEXT_IDS stehen; Fundliste im Bericht.
- 103-2: Beendet ein Admin die Sitzungen eines Benutzers, meldet das auch alle seine vertrauten Geräte ab.
- 103-3: Feierabend als POST; die Ausnahme von Regel 23 entfällt.
- 104-8: Secure ist die Vorgabe; ohne Secure nur bei ausdrücklich lokalem Betrieb oder in Tests. Fehlt ERP_ENV, bleibt Secure.

1. Der JS-Scanner in tests/vorlagen_js.py liest Pfeilfunktionen vollständig; Gegenprobe mit einem Pfeil, der einen Wert ungeschützt
   einsetzt. Was die Strukturtests danach neu finden, wird behoben; die Ausnahmelisten werden nicht länger.
2. HSTS in Produktion, ohne includeSubDomains. Die Schutzkopfzeilen tragen alle Antworten, auch die 500 aus dem Fehler-Handler.

Ins Archiv (nur festhalten, nicht bauen): content an den Layout-Bausteinen wird nirgends eingegeben und nirgends gezeigt; mit den übrigen
ungenutzten Spalten entfernen.

Angriffstests mit Gegenprobe. Eigene Festlegungen mit „Bitte bestätigen“, je in einer Zeile. Nebenbefunde nur melden. Wird der Umfang zu
groß: nach Punkt 1 committen und den Rest auflisten. Commit nach Regel 13, Bericht kurz.

Reihenfolge der Umsetzung: Punkt 1 (1.8.105), Vorweg 101-4, 102-2, 103-2, 103-3 (1.8.106), Vorweg 104-8 mit Punkt 2 (1.8.107) -- Secure
und HSTS hängen an derselben Frage "ausdrücklich lokal oder nicht".

### Umsetzung 1.8.105: die Scanner lesen Pfeilfunktionen vollständig (Punkt 1, Nebenbefund 1.8.102 Nr. 1)

#### Was gebaut ist

- **Ende eines Ausdrucks** (`tests/vorlagen_js.py::_ausdruck_ende()`): bis 1.8.104 endete der Rumpf eines Pfeils ohne geschweifte Klammern
  an der ersten schließenden Klammer derselben Ebene, auch wenn ihre öffnende im Rumpf stand -- `s => String(s ?? '').replace(…)` endete
  nach `String(s ?? ''`. Jetzt gehört jede Klammer, die ab dem Anfang geöffnet wurde, dazu; der Ausdruck endet vor `;` oder `,` derselben
  Ebene, vor einer Klammer, die eine Klammer vor ihm schließt, oder an einem Zeilenumbruch vor einer neuen Anweisung: Schlüsselwort wie
  bisher, dazu nach der Regel der automatischen Semikolon-Einfügung (`_neue_anweisung()`: die Zeile davor endet mit einem Namen, Literal,
  einer schließenden Klammer oder ++/--, die neue beginnt mit einem Namen außer in/instanceof/of, einer Zahl, einem String, ++/--, ! oder ~;
  ein Operator, ein Punkt, eine öffnende Klammer oder ein Template-Literal setzt fort).
- **Eine Funktion für alle Scanner**: `tests/vorlagen_navigation.py::_ende()` (Navigation, und darüber die Rümpfe und Werte in
  `tests/vorlagen_html.py`) hatte die Klammer schon richtig, aber nicht das Zeilenende; es ruft jetzt `_ausdruck_ende()`. Damit gelten
  dieselben Grenzen für `a.funktionen` (test_v398 schreibende Funktionen und "Gespeichert", test_v399 Adressen, test_v400 Anfragen außerhalb,
  die Funktion jeder Fundstelle in test_v407) und für die Rümpfe des HTML-Scanners.
- **Neu gefunden und behoben**: in `work_preparation.html` setzte der Knopf "×" am Lieferschein einer Materialposition Material- und
  Lieferschein-ID ins onclick (`deliveryTags`, ein Pfeil, dessen Rumpf mit `(x.delivery_notes||[])` beginnt -- die beiden Werte zählten bis
  1.8.104 zu `renderMaterials`). Der Knopf trägt sie jetzt als `data-material`/`data-lieferschein` mit `data-klick="lieferschein-loesen"`
  (`_aktionen.html`, auf der Seite neu eingebunden). Sonst fand keiner der Strukturtests etwas Neues (test_v398, test_v399, test_v400,
  test_v401, test_v405, test_v407 ohne esc und Links); keine Ausnahmeliste ist länger, `AUSNAHMEN_HANDLER` kürzer (375 -> 373).

#### Festlegungen 1.8.105 (Bitte bestätigen)

1. **Ein Ausdruck endet auch an einem Zeilenumbruch, den JavaScript als Ende der Anweisung liest** (vereinfachte Regel der automatischen Semikolon-Einfügung, oben), nicht nur vor einem Schlüsselwort; alle Scanner nutzen dieselbe Funktion.
2. **Ändert sich durch die neuen Grenzen nur die Funktion im Schlüssel einer Ausnahme, wird die Stelle behoben, nicht der Schlüssel umbenannt** (so beim Lieferschein-Knopf) -- die Listen werden nur kürzer.

#### Tests und Prüfung

- Neu `tests/test_v410_pfeile_vollstaendig.py` (25): Rumpf eines Pfeils bis zum Ende seines Ausdrucks (17 Fälle: Aufruf, Klammer, Array und
  Objekt am Anfang, Klammer der Umgebung, Zeilenende mit neuer Anweisung oder Fortsetzung), Wert einer Zuweisung ebenso; was die
  Strukturtests dadurch sehen: ein Speichern in einem Pfeil macht ihn zur schreibenden Funktion (fetch danach gefunden), eine Anfrage in der
  Zeile nach einem Pfeil ohne Semikolon gehört nicht zum Pfeil (sonst blieb sie in einer nur im Baustein gerufenen Funktion unbemerkt), ein
  Anfrage-Helfer als Pfeil wird erkannt, **ein Pfeil, der einen Wert ungeschützt einsetzt** (`k => Number(k.nr ?? 0).toFixed(0) + ' ' +
  k.name`, bis 1.8.104 nach `Number(k.nr ?? 0` zu Ende und damit sicher), mit esc() still; die Funktion einer Fundstelle ist der Pfeil.
- **Angepasste Erwartungen** (Regel 28): `test_v407::AUSNAHMEN_HANDLER` `'work_preparation.html | renderMaterials | onclick: d.id': 1`
  gestrichen und `'… | renderMaterials | onclick: x.id'` 2 -> 1 (die Stelle ist behoben, nicht umbenannt). Klicktest
  `klicktest_arbeitsvorbereitung`: zwei neue Prüfungen (Knopf mit data-Attributen ohne onclick, "×" entfernt genau diese Zuordnung), dafür
  zwei Lieferscheine in `befuellen()` und `confirm()` per Skript angenommen (nur Aufbau); 8/8.
- Gegenproben (Regel 24): 5 von 5 rot -- Pfeilende wie bis 1.8.104 (23 von 25 Tests rot), Zeilenende nur mit Schlüsselwörtern (11 rot, auch
  "Anfrage nach einem Pfeil ohne Semikolon"), Navigation mit eigenem Ende ohne Zeilenende, Lieferschein-Knopf wieder mit onclick (test_v407
  Handler rot; im Klicktest: 5/8, Knopf ohne data-Attribute, Zuordnung nicht entfernt). Jede Datei byte-genau zurück, kein Marker.
- Volle Suite und alle Klicktests: im Bericht (Regel 26).

#### Nebenbefunde (nur gemeldet)

1. **Der Scanner in `tests/vorlagen_js.py` kennt als Funktionen nur `function name(…)` und `name = …`** -- eine Methode in einem Objekt
   (`{ laden(){…} }`, `laden: () => …`) oder einer Klasse zählt zur umgebenden Funktion bzw. zu `<oben>`. Für test_v398 hieße das: ein
   Speichern in einer solchen Methode macht sie nicht zur schreibenden Funktion. Ob eine Vorlage das so verwendet, ist nicht untersucht.

### Umsetzung 1.8.106: Vorweg -- SVG-Logo, Text-IDs, vertraute Geräte, Feierabend als POST (Korrekturen 101-4, 102-2, 103-2, 103-3)

#### Was gebaut ist

- **101-4 SVG-Logo mit Sandbox**: war seit 1.8.101 so -- ein am Inhalt erkanntes SVG-Logo geht direkt geöffnet als Download mit
  `Content-Security-Policy: sandbox; default-src 'none'; style-src 'unsafe-inline'; img-src data:` (seit 1.8.104 mit `frame-ancestors
  'none'` angehängt), `sandbox` ohne `allow-…`: kein Skript, kein Formular, ein undurchsichtiger Ursprung statt dem des ERP. Am Code nichts
  geändert; neu ist der Test über die echte Route und die echte Anmeldeschranke (je Direktive geprüft, nicht nur der Anfang) und die
  Gegenprobe. Die Festlegung 1.8.101 Nr. 4 lautet damit: "SVG nur beim Firmen- und Seitenleisten-Logo als Bild, direkt geöffnet ein Download
  mit Sandbox".
- **102-2 Text-IDs, einmal geprüft** (Fundliste): keine Text-ID fehlt in `TEXT_IDS`. Geprüft wurden (1) jede Spalte "id"/"…_id", die keine
  Ganzzahl ist: zehn, alle String (`services.external_id`, `quote_items`/`order_items.source_external_id`, `general_settings.vat_id`,
  `audit_logs.entity_id`, `smtp_settings.graph_tenant_id`/`graph_client_id`, `calendar_events`/`outlook_series_occurrences.outlook_event_id`,
  `outlook_series_occurrences.series_master_id`), keine UUID-Spalte; (2) jedes Pydantic-Modell in jedem Modul unter `app/` (503 Modelle,
  bis 1.8.105 prüfte der Test nur `app/schemas.py`): 14 Felder mit Text, alle aus `app/schemas.py` und in TEXT_IDS (dazu `tenant_id`,
  `client_id` aus `GraphSettingsUpdate`); (3) jeder Schlüssel "id"/"…_id" eines dict-Literals unter `app/`, der keiner Ganzzahl-Spalte
  gleichen Namens entspricht (17 Namen, von Hand gelesen: alle mit Zahlen oder None belegt, außer den Text-IDs oben); (4) die JSON-Antworten
  aller GET-Routen in den drei Rundgängen aus test_v326 (198 Routen mit Inhalt): Text unter einem solchen Schlüssel nur `entity_id` (Audit)
  und `external_id` (Leistung), beide in TEXT_IDS; (5) die Vorlagen: jeder Wert eines `data-id`/`data-…-id` ist eine Zahl, kein Element-ID
  (`el.id`) geht in HTML. "UUID u. ä." heißen im ERP `client_uuid`, `dispatch_key`, `token…` -- nicht "…_id", für den Scanner also nie eine
  Zahl. Dauerhaft: `test_v407::test_jedes_id_feld_mit_text_steht_in_text_ids` liest jetzt jeden Spaltentyp außer Ganzzahl und alle
  Pydantic-Modelle unter `app/`; `test_v411` prüft die Antworten der Rundgänge.
- **103-2 vertraute Geräte**: `POST /api/users/{id}/end-sessions` meldet im selben Commit alle vertrauten Geräte des Benutzers ab
  (`device_trust.revoke_all()`); beendet der Administrator seine eigenen, bleibt dieses Gerät angemeldet, sein Cookie "vertrautes Gerät" wird
  gelöscht. Die Antwort nennt `geraete_abgemeldet`. Die Benutzerverwaltung zeigt unter der Zahl der Sitzungen "N vertraute(s) Gerät(e)"
  (`AppUserOut.trusted_device_count`, nur gelesen, `device_trust.anzahl()`), der Knopf steht da, solange es Sitzungen oder vertraute Geräte
  gibt, die Rückfrage nennt die Geräte.
- **103-3 Feierabend als POST**: `GET /api/field-view/today` schreibt nichts mehr -- nach der Feierabend-Uhrzeit 401 mit `"feierabend":
  true`, Sitzung und Cookie bleiben. Neu `POST /api/field-view/feierabend` (jede Rolle ab Monteur): nach der Uhrzeit beendet er die Sitzung
  dieses Geräts auf dem Server und löscht das Cookie, davor 409 ohne Wirkung. `/mobil` schickt ihn über `speichern('feierabend', …)`, sobald
  der GET "feierabend" meldet, und geht danach zur Anmeldung -- nur wenn die Sitzung damit endete (200) oder schon weg war (401). Scheitert
  der POST (Netz, 403 von einem Tablet ohne `Sec-Fetch-Site`, Server), bleibt die Seite mit "Feierabend -- Abmelden fehlgeschlagen: …"
  stehen: mit einer noch gültigen Sitzung schickt `/login` sofort zurück nach `/mobil`, die Seite liefe im Kreis (in der Gegenprobe ohne POST
  so beobachtet, siehe unten). Die Ausnahme von Regel 23 (Festlegung 1.8.103 Nr. 3) ist weg.

#### Festlegungen 1.8.106 (Bitte bestätigen)

1. **101-4 ohne Codeänderung**: die Sandbox stand seit 1.8.101 in der CSP des SVG-Logos; neu sind nur der Test über die echte Route und die Gegenprobe.
2. **102-2 dauerhaft statt einmal**: der Test prüft künftig alle Spaltentypen außer Ganzzahl und alle Pydantic-Modelle unter `app/`, dazu die Antworten der Rundgänge -- eine neue Text-ID fällt beim nächsten Testlauf auf.
3. **103-2 auch die eigenen**: beendet ein Administrator seine eigenen Sitzungen, sind auch seine vertrauten Geräte abgemeldet, dieses eingeschlossen (dieses Gerät bleibt angemeldet, die nächste Anmeldung braucht den zweiten Faktor).
4. **103-2 Knopf und Anzeige**: "Alle Sitzungen beenden" steht da, solange Sitzungen oder vertraute Geräte bestehen; die Liste zeigt die Zahl der vertrauten Geräte unter der der Sitzungen.
5. **103-3 der GET meldet, der POST beendet**: nach Feierabend antwortet der GET 401 mit `feierabend: true` und lässt Sitzung und Cookie stehen; der POST beendet nur die Sitzung dieses Geräts und löscht das Cookie, vor der Uhrzeit 409 ohne Wirkung.
6. **103-3 ohne Seite kein Ende**: öffnet niemand `/mobil` nach Feierabend, gilt die Sitzung bis zu ihrem Ablauf (12 h) -- wie bis 1.8.102; `/mobil` selbst bekommt nach Feierabend keine Einsätze mehr (401).
7. **103-3 über speichern(), nicht abschliessen()**: der Feierabend ist ein Abmelden (Bereich `feierabend`), keine abschließende Aktion.
8. **103-3 zur Anmeldung nur mit beendeter Sitzung**: nach 200 oder 401 des POST; sonst bleibt `/mobil` mit der Meldung stehen (kein Kreis über `/login`, das eine gültige Sitzung zurückschickt).

#### Tests und Prüfung

- Neu `tests/test_v411_vorweg.py` (17): SVG-Logo beider Routen über die echte Anmeldeschranke (Download, nosniff, `sandbox` ohne `allow-…`,
  `default-src 'none'`, kein `script-src`, `frame-ancestors 'none'`); Text-IDs in den Antworten der drei Rundgänge (über 150 Routen, `entity_id`
  und `external_id` gefüllt, keine fehlt); **Angriffstests** vertraute Geräte (Admin beendet die eines anderen Admins: Sitzungen 401, das alte
  Cookie "vertrautes Gerät" erspart den zweiten Faktor nicht mehr; die eigenen: dieses Gerät angemeldet, sein Cookie gelöscht, das andere 401;
  nur Geräte, keine Sitzungen); Feierabend (der GET schreibt nichts -- Datenbank-Listener -- und lässt das Cookie, die Sitzung gilt; der POST
  beendet nur diese Sitzung, der Wert von außen 401, das zweite Gerät 200; vor der Uhrzeit 409; von einer fremden Seite 403); `/mobil` ruft
  den POST über `speichern()`; in node: zur Anmeldung nur nach 200 oder 401, bei 403, 409, 502 und Netzfehler die Meldung und keine
  Navigation.
- Neue Klicktests `klicktest_feierabend` 12/12 (feste Uhr 20:00: der GET von außen schreibt nichts; POST im Browser blockiert --
  `/mobil` bleibt mit der Meldung stehen, ein GET, ein POST, kein `/login`, die Sitzung gilt; sonst schickt `/mobil` genau einen POST mit 200
  und landet auf `/login?next=%2Fmobil`, Cookie im Browser weg, Wert des Tablets von außen 401, das Handy bleibt angemeldet) und
  `klicktest_vertraute_geraete` 6/6 (Liste mit "1 vertrautes Gerät" und Knopf ohne Sitzung, Rückfrage nennt die Geräte, danach weg, Server 0).
- **Angepasste Erwartungen** (Regel 28): `test_v224::test_field_view_today_logs_out_past_shift_end` "GET 401 und Cookie gelöscht" -> "GET 401
  mit `feierabend`, kein Cookie gelöscht; `end_shift()` 200 und Cookie gelöscht"; `test_v408::test_feierabend_beendet_die_sitzung_auf_dem_server`
  "GET beendet die Sitzung" -> "GET meldet, POST /api/field-view/feierabend beendet sie" (die Angriffsprüfungen danach gleich);
  `test_v407::test_jedes_id_feld_mit_text_steht_in_text_ids` liest mehr (alle Spaltentypen außer Ganzzahl, alle Pydantic-Modelle unter
  `app/`), Soll gleich (keine fehlt).
- Gegenproben (Regel 24): 11 von 11 rot -- SVG-Logo ohne `sandbox` (2 rot); `outlook_event_id` nicht in TEXT_IDS; ein Pydantic-Modell
  mit Text-ID in einem Router und eine UUID-Spalte unter dem Namen einer ID (beide rot, der Test bis 1.8.105 sah keins von beiden);
  `external_id` nicht in TEXT_IDS (Laufzeit rot); Admin beendet ohne die vertrauten Geräte (3 rot); Knopf nur mit Sitzungen (Klicktest 1/6);
  der GET beendet die Sitzung wieder selbst (der Listener sieht das DELETE); der POST ohne Prüfung der Uhrzeit; `/mobil` ohne POST zur
  Anmeldung (Klicktest: kein POST, Sitzung gilt -- danach lief die Seite `/mobil` ↔ `/login` im Kreis, der Klicktest kam nicht zu Ende und
  wurde über seine PIDs beendet; Anlass für Festlegung 8); `/mobil` auch nach gescheitertem POST zur Anmeldung (node, 3 rot). Jede Datei
  byte-genau zurück, kein Marker.
- Volle Suite und alle Klicktests: im Bericht (Regel 26).

#### Nebenbefunde (nur gemeldet)

1. **Jeder Weg, der mit einer noch gültigen Sitzung nach `/login?next=…` geht, läuft im Kreis**, wenn das Ziel wieder dorthin schickt: die
   Anmeldeseite leitet eine gültige Sitzung serverseitig auf `next` weiter. Für den Feierabend abgefangen (Festlegung 8); andere Seiten gehen
   nur bei 401 nach `/login` (Sitzung ungültig, kein Kreis) -- `field_timesheet.html` und `time_tracking_field.html` erkennen den 401 aber am
   Text der Meldung (Nebenbefund 1.8.103 Nr. 2).

### Umsetzung 1.8.107: Secure als Vorgabe, HSTS, Schutzkopfzeilen an der 500 (Korrektur 104-8, Punkt 2)

#### Was gebaut ist

- **104-8 Secure als Vorgabe** (`app/auth.py`): `NUR_HTTPS` ist wahr, außer `ERP_ENV` ist ausdrücklich `development` (lokal über reines
  HTTP) oder `test` (Testlauf); `COOKIE_SECURE = NUR_HTTPS or ERP_COOKIE_SECURE`. Fehlt `ERP_ENV`, ist sie leer oder hat einen anderen Wert,
  bleibt das Anmelde-Cookie (und das Cookie "vertrautes Gerät") Secure -- bis 1.8.106 galt eine fehlende `ERP_ENV` als lokal. Ausdrücklich
  lokal setzen jetzt: `start_windows.bat` (`set ERP_ENV=development` vor uvicorn), die Klicktests (seit jeher), `tests/conftest.py`
  (`ERP_ENV=test` statt sie zu entfernen; sonst schickte der TestClient über http://testserver kein Cookie zurück). `.env.example` sagt es.
- **Punkt 2, HSTS** (`app/anmeldeschranke.py::HSTS`): `Strict-Transport-Security: max-age=31536000` an jeder Antwort der Schranke, wo das
  Cookie Secure ist (`NUR_HTTPS`: Produktion, auch mit fehlender `ERP_ENV`), ohne `includeSubDomains` und ohne `preload`; lokal und in Tests
  keine. Ein Browser beachtet die Kopfzeile nur über HTTPS.
- **Punkt 2, die 500** (`app/anmeldeschranke.py::serverfehler()`): ein unbehandelter Fehler kommt aus dem äußersten Fehler-Handler von
  Starlette, an der Schranke vorbei -- bis 1.8.106 ohne Rahmen-Kopfzeilen und ohne Cache-Verbot (Nebenbefund 1.8.104 Nr. 2). Jetzt ist
  `serverfehler()` dieser Handler: "Internal Server Error" (text/plain, nichts aus dem Fehler), `Cache-Control: no-store`, `X-Frame-Options`,
  `frame-ancestors`, HSTS. Das gilt auch für einen Fehler in der Schranke selbst (Datenbank weg, bevor sie weiß, wer anfragt). Starlette gibt
  den Fehler danach weiter an den Server (Protokoll wie bisher). Schranke und Handler bindet `einbinden(app, session_factory)` ein -- in
  `app/main.py` und in `tests/anmeldung.py::app_mit_schranke()`, damit die Tests dieselbe Anwendung prüfen.

#### Festlegungen 1.8.107 (Bitte bestätigen)

1. **Ausdrücklich lokal ist `ERP_ENV=development`, Tests sind `ERP_ENV=test`** (Groß-/Kleinschreibung und Leerzeichen egal); fehlend, leer oder jeder andere Wert (auch `production`, `staging`) heißt Secure.
2. **`ERP_COOKIE_SECURE` schaltet nur ein** (lokal oder im Test hinter HTTPS), nie aus -- auch `0` ändert außerhalb von lokal/Test nichts.
3. **`start_windows.bat` setzt `ERP_ENV=development`** (127.0.0.1 über http ist ausdrücklich lokal); wer anders startet (uvicorn direkt, Zugriff vom Tablet über die LAN-Adresse), setzt sie selbst, sonst meldet ein Aufruf über http nicht an.
4. **HSTS dort, wo das Cookie Secure ist** -- in Produktion und bei fehlender `ERP_ENV`, nicht nur mit `ERP_ENV=production`; lokal (`development`) auch dann nicht, wenn `ERP_COOKIE_SECURE=1` gesetzt ist.
5. **HSTS: `max-age=31536000`** (ein Jahr), ohne `includeSubDomains` (Vorgabe) und ohne `preload`.
6. **Die 500 nennt nichts aus dem Fehler** ("Internal Server Error", text/plain) und trägt `Cache-Control: no-store` wie eine Antwort an eine angemeldete Sitzung, dazu die Rahmen-Kopfzeilen und HSTS.
7. **Schranke und Fehler-Handler über eine Funktion** (`einbinden()`), in der Anwendung wie in den Tests.

**Vor dem Einspielen (Betreiber)**: auf dem Server ändert sich nichts, solange die `.env` `ERP_ENV=production` setzt (Secure wie bisher, neu
HSTS). Setzt Nginx schon `Strict-Transport-Security`, stehen danach zwei Kopfzeilen in der Antwort (der Browser nimmt die erste) -- einmal mit
`curl -sI https://app.dachkonzepte.gmbh/login` ansehen und die von Nginx entfernen oder gleich lassen. Lokal startet `start_windows.bat` wie
bisher; ein anderer Start über http braucht `ERP_ENV=development`.

#### Tests und Prüfung

- Neu `tests/test_v412_hsts_und_fehlerseite.py` (30): Secure und HSTS in zehn Umgebungen (Unterprozess: fehlend, leer, production auch mit
  Leerzeichen und `ERP_COOKIE_SECURE=0`, staging, nur `ERP_COOKIE_SECURE=0`, development, test, development mit `ERP_COOKIE_SECURE=1`); der
  Testlauf selbst als `test`; `start_windows.bat` setzt `development` vor uvicorn; **Angriffstests** die 500 (API, Seite, POST, je mit und
  ohne HSTS: Schutzkopfzeilen, no-store, kein Text des Fehlers, kein Traceback; ohne Anmeldung 401 statt 500), ein Fehler in der Schranke
  selbst (Sitzungsfabrik wirft), HSTS an jeder Antwort (Anmeldeseite, API, 404, Weiterleitung, 403 fremder Ursprung, HEAD, OPTIONS -- mit und
  ohne Anmeldung, ohne `includeSubDomains`/`preload`), `app.main` bindet den Handler ein; Rundgang über alle GET-Routen als Administratorin und
  Monteurin mit HSTS.
- **Angepasste Erwartungen** (Regel 28): `test_v409::test_secure_in_produktion_ohne_schalter` `({}, "False")` -> `({}, "True")` (fehlt
  `ERP_ENV`, bleibt Secure). Nur Aufbau: `tests/conftest.py` setzt `ERP_ENV=test` (und entfernt `ERP_COOKIE_SECURE`) statt `ERP_ENV` zu
  entfernen; `tests/anmeldung.py::app_mit_schranke()` bindet über `einbinden()` ein (mit Fehler-Handler); `test_v403::_rundgang()` hält HSTS
  fest; `test_v111::test_cookie_secure_defaults_to_off` nur der Kommentar (Soll gleich: im Testlauf aus).
- Gegenproben (Regel 24): 10 von 10 rot -- fehlende `ERP_ENV` wieder lokal (4 rot, auch test_v409), `ERP_COOKIE_SECURE=0` schaltet aus,
  `start_windows.bat` ohne `ERP_ENV`, HSTS mit `includeSubDomains`, HSTS nur mit `production` (4 rot), Schranke ohne HSTS (13 rot, auch der
  Rundgang), kein Fehler-Handler (8 rot), Handler ohne Schutzkopfzeilen (7 rot), Handler nennt den Fehler (7 rot), `app/main.py` nur mit der
  Middleware. Jede Datei byte-genau zurück, kein Marker.
- Volle Suite und alle Klicktests: im Bericht (Regel 26).

#### Nebenbefunde (nur gemeldet)

1. **`create_all()` beim Start läuft weiter bei fehlender `ERP_ENV`** (`app/main.py`: nur `production` schaltet es ab) -- Secure und HSTS
   sind jetzt bei fehlender Umgebung auf der sicheren Seite, das Sicherheitsnetz für das Schema nicht: auf dem Server mit nicht geladener
   `.env` verdeckte es eine fehlende Migration (Vorfall 1 in CLAUDE.md).
2. **Ob Nginx HSTS schon setzt, ist von hier nicht prüfbar** -- siehe "Vor dem Einspielen".

### Stand nach 1.8.107: Nacharbeiten Sicherheit der Seiten

Die zweite Vorgabe vom 14.10.2026 ist umgesetzt: Scanner liest Pfeile vollständig (1.8.105), Vorweg 101-4, 102-2, 103-2, 103-3 (1.8.106),
104-8 und Punkt 2 (1.8.107); `content` der Layout-Bausteine steht im Parkplatz.

## Vor dem Abnahmetest: Zahleneingaben, lesbare Fehler, Revisionsnummer, Testablauf (ab 1.8.109)

### Vorgabe vom 15.10.2026 (übernommen wie gegeben)

> Vorweg zu 1.8.108: Alle 16 Festlegungen bestätigt. Regel 26 ergänzen: Ein Commit, der nur docs/ ändert, löst keinen neuen Endlauf aus.
>
> Vor dem Abnahmetest, je mit Angriffstest und Gegenprobe:
> 1. Zahleneingaben im Browser lesen das deutsche Format über eine gemeinsame Funktion: „1.250“ ist 1250, „1.250,5“ ist 1250,5;
>    Mehrdeutiges wie „1.25“ wird mit Meldung abgelehnt, nie still umgedeutet. Strukturtest: keine eigene Umwandlung von Zahleneingaben
>    außerhalb dieser Funktion; Ausnahmeliste darf nur kürzer werden.
> 2. Zahlungsbedingungen: Ein leeres „Tage bis Fälligkeit“ wird abgelehnt statt still als 0 gespeichert; Fehler erscheinen dort lesbar
>    statt „[object Object]“.
> 3. Mahnwesen: Der Knopf, der nur festschreibt, heißt „Festschreiben“, nicht „Versenden“.
> 4. Die Plantafel zeigt Eingabefehler lesbar; „Team entfernen“ in der Arbeitsvorbereitung zeigt eine Ablehnung an.
> 5. create_order_revision() vergibt die Revisionsnummer unter Sperre und vor dem Commit; zwei gleichzeitige Nachträge ergeben keinen
>    500. Gleichzeitigkeit gegen PostgreSQL.
> 6. klicktest_zeitbuchungen_liste zwischen 0 und 2 Uhr: mit fester Uhr klären, ob der Test oder die Anwendung falsch rechnet; liegt es
>    an der Anwendung, beheben.
> 7. Testablauf: Zeitgrenze je Test; die _run-Kopien in test_v363 und test_v365 schließen ihre Sitzungen; taskkill in beenden() mit
>    Zeitlimit.
>
> Eigene Festlegungen mit „Bitte bestätigen“, je in einer Zeile. Nebenbefunde nur melden. Wird der Umfang zu groß: nach Punkt 5
> committen und den Rest auflisten. Commit nach Regel 13, Bericht kurz.

Aufteilung: 1.8.109 Punkte 1–4 (Browser: Zahlen, Meldungen, Beschriftung), 1.8.110 Punkt 5 (Anwendung, Sperre), 1.8.111 Punkte 6–7
(Klicktest und Testablauf, Archiv `docs/archiv/testablauf-und-klicktests.md`). Der Vorweg-Teil steht dort und in Regel 26.

### Umsetzung 1.8.109: Zahleneingaben im deutschen Format, lesbare Fehler, Festschreiben (Punkte 1–4)

#### Befund vorweg: was Chrome aus einem Zahlenfeld macht

Gemessen am 15.10.2026 (headless Chrome, mit und ohne `--lang=de-DE`, Sprache des Browsers de-DE, Eingabe getippt über
`Input.insertText`): in `<input type="number">` liest Chrome den Punkt als Dezimaltrenner, das Komma ebenso -- "1.250" ergab `value`
"1.250" und `valueAsNumber` **1,25**, "1.250,5" ergab "1.2505" (**1,2505**), "1,5" ergab "1.5"; `validity.badInput` blieb in allen Fällen
falsch. Die Seite bekam den Rohtext nie zu sehen: mit `type="number"` lässt sich "1.250" nicht als 1250 lesen und "1.25" nicht ablehnen.
Bis 1.8.108 gab es 159 solche Felder in 25 Vorlagen (Markup und Template-Literale), dazu eigene Umwandlungen: rund 30 Stellen ersetzten
das Komma selbst (`service_form.html` 20), `customer.html` und `invoice_detail.html` hatten je ein `num()` (Punkt nur als Tausender,
wenn ein Komma folgte -- "1.250" ohne Komma war 1,25), `settings.html` `rateValue()`; Felder gingen auch roh an den Server
(Betriebsmittel-Kosten, Rand der Wiederholungszeile, Antworten vom Typ Zahl in Checklisten -- dort ersetzte der Server das Komma), wo
Pydantic "1.250" als 1,25 las.

#### Was gebaut ist

- **Baustein `app/templates/_zahl.html`** (Punkt 1), die einzige Stelle, an der eine Seite aus einer Eingabe eine Zahl macht:
  `zahlLesen(text, optionen)` (Regeln unten; Fehler mit `zahlFehler`, Meldung mit Feld und Eingabe), `zahlFeld(el|id, optionen)` (liest
  das Feld; Optionen auch aus dem Feld: `data-zahl="ganz"`, `data-stellen`, `data-min`/`data-max`, `required`, Beschriftung aus
  `data-feld` oder dem `<label>`; markiert ein abgelehntes Feld mit `aria-invalid`, rot, bis zur nächsten Eingabe), `zahlVorschau()` (wirft
  nie, `null` bei leer oder ungültig -- nur für Anzeigen während der Eingabe), `zahlText(wert, stellen)` (füllt ein Feld deutsch ohne
  Tausenderpunkte; liest einen Wert der API im Maschinenformat, "1.250" aus der API ist 1,25).
- **Regeln**: Komma = Dezimaltrenner, Punkt = Tausendertrenner nur vor je drei Ziffern und nicht hinter einer führenden 0 ("1.250" =
  1250, "1.250,5" = 1250,5, "1.250.000" = 1250000); ein Punkt ohne drei Ziffern danach ("1.25", "0.5", "12.50", "1.") ist mehrdeutig
  und wird mit "… ist nicht eindeutig – Dezimalstellen bitte mit Komma (z. B. 1,25), Tausender mit Punkt vor je drei Ziffern (z. B.
  1.250)." abgelehnt; sonst nur Ziffern 0–9, höchstens ein Komma, ein Vorzeichen (+, -, −) -- kein Leerzeichen, keine Einheit, kein
  Exponent ("1e3"), keine anderen Ziffern (arabisch, vollbreit); ",5" = 0,5, "5," abgelehnt; leer = Vorgabe (`leer`, sonst null), mit
  `pflicht` "<Feld> fehlt."; `ganz`, `stellen` (Nullen am Ende zählen nicht), `min`/`max`.
- **Alle Zahlenfelder umgestellt**: `<input type="text" inputmode="decimal" data-zahl>` (ganze Zahlen `inputmode="numeric"
  data-zahl="ganz"`), `step` entfällt, `min`/`max` werden `data-min`/`data-max`; Platzhalter deutsch. Gelesen nur über `zahlFeld()`,
  Live-Rechnungen über `zahlVorschau()`, gefüllt über `zahlText()`. Gelesen wird vor dem ersten `speichern()` -- eine abgelehnte Zahl
  speichert nichts halb (Mahnungs-Editor: Zahlungsfrist und Gebühr vor dem ersten von zwei Speichern, `chargesBody()`; Ränder alle acht vor
  Seite 1; Kalkulation samt Materialzeilen; Leistung: Grunddaten und Kalkulation). Eigene Umwandlungen entfallen (`num()`, `cents()`,
  `rateValue()`, alle Komma-Ersetzungen). In 29 Vorlagen, davon fünf Gruppen durch Helfer bearbeitet (je Gruppe Dateiliste, Auftrag und
  Bericht im Scratchpad), jede Gruppe gegengelesen.
- **`abschliessen()` sperrt bei einem abgelehnten Zahlenfeld** (`_speichern.html`): eine abschließende Aktion (Unterschrift,
  Festschreiben …) geht nicht hinaus, solange auf der Seite ein Feld `input[data-zahl][aria-invalid="true"]` steht ("Nicht ausgeführt:
  eine Zahl auf der Seite ist ungültig (<Feld>) und nicht gespeichert …") -- die Eingabe ging nicht hinaus, gespeichert ist der alte
  Wert, eine Unterschrift versiegelte ihn still. Checkliste und Einsatzbericht prüfen das zusätzlich schon vor ihrer Rückfrage.
- **Strukturtest** `tests/test_v414_zahleneingaben.py` mit Scanner `tests/vorlagen_zahlen.py` (Tokenizer aus `tests/vorlagen_js.py`), je
  Fund Vorlage, Zeile, Art, Ausschnitt: `type-number`; `parse` (parseFloat/parseInt/valueAsNumber -- jede Verwendung); `komma`; `wert`
  (ein Feldwert wird zur Zahl: Argument von Number()/Math.*()/isNaN()/isFinite(), unäres +, Rechnen mit * / % - **, auch über eine
  Variable, einen Lese-Helfer der Seite `v('id')` oder ein on…-Attribut); `roh` (der Text eines `data-zahl`-Felds außerhalb von
  `zahlLesen()` -- roh an den Server, auf leer geprüft); `schreiben` (ein Zahlenfeld ohne `zahlText()` gefüllt: `value="${…}"`,
  `el.value = …`, Setter-Helfer); `inputmode`; `einbinden`. Felder ohne freien Text (Auswahlliste, Häkchen, Datum, versteckt …) erkennt er
  über die ID -- auch zusammengesetzte (`'rl'+id+'Days'` gegen `rl${x.id}Days`: Anfang und Ende), Selektoren (`#id`, `.klasse`,
  `[type=…]`, Pseudoklassen ignoriert), Callback-Parameter über `querySelectorAll(…)`, `this` im Attribut; was er nicht auflösen kann,
  gilt als Textfeld. Ausnahmeliste `AUSNAHMEN`: zwei Stellen ohne Zahleneingabe (darf nur kürzer werden).
- **Punkt 2, Zahlungsbedingungen** (`settings.html`): "Tage bis Fälligkeit" ist Pflicht (`zahlFeld('ptDays', {pflicht: true})`, ganze
  Zahl ≥ 0): leer -> "Fehler: Tage bis Fälligkeit fehlt.", nichts gesendet; bis 1.8.108 machte `Number('')` daraus still 0. 0 bleibt
  eingebbar (sofort fällig). Der Server war schon streng (`days: int`, Pflicht) -- er bekam nur nie ein leeres Feld. `api()` der
  Einstellungen geht über `fehlerText()` mit `FELDNAMEN` (ein 422 erschien als "[object Object]").
- **Punkt 3, Mahnwesen**: der Knopf am Entwurf heißt "Festschreiben" (Mahnwesen: "Zur Mahnung fällig"/Aufmerksamkeit und "Alle
  Mahnungen"; Rechnungsseite: Karte Mahnungen), die Rückfrage "Mahnung jetzt festschreiben? … Festschreiben verschickt nichts – die Mahnung
  geht danach per E-Mail hinaus … oder wird anders zugestellt (Zustellung nachtragen).", die Statuszeile "Festgeschrieben.", "erst nach dem
  Festschreiben" statt "erst nach Finalisieren". Funktionsnamen (`sendReminder()`, `sendReminderNow()`) und der Endpunkt bleiben.
- **Punkt 4, Plantafel und Arbeitsvorbereitung**: `api()` der Plantafel über `fehlerText()` mit `FELDNAMEN` (ein 422, z. B. Anfahrt ≥ 24 h,
  heißt jetzt "Bitte die Eingabe prüfen – Anfahrt je MA / Tag ist zu groß."), Zahlen im Dialog über den Baustein mit Meldung im Dialog.
  "Entfernen" an einer Kolonne: bis 1.8.108 ohne `catch` -- die Ablehnung des Servers (409 "Diese Kolonne besitzt noch einen Einsatz in der
  Plantafel …") lief ins Leere; jetzt in einer neuen Statuszeile unter "Zugewiesene Kolonnen / Teams". `api()` der Arbeitsvorbereitung
  ebenso über `fehlerText()`.

#### Festlegungen 1.8.109 (Bitte bestätigen)

1. **Zahlenfelder sind Textfelder** (`type="text"`, `inputmode="decimal"`, ganze Zahlen `"numeric"` mit `data-zahl="ganz"`), nicht `type="number"` -- nur so kommt der Rohtext an; die Pfeiltasten am Feld entfallen.
2. **"1,250" ist 1,25** (deutsches Format) -- abgelehnt wird nur, was mit Punkt mehrdeutig ist; ein Punkt ohne drei Ziffern danach ist nie ein Dezimaltrenner.
3. **Leer behält je Feld seine bisherige Bedeutung** (0, Vorgabe wie 12 oder 100, null); Pflicht nur, wo leer bisher still zu 0 wurde und fachlich nichts bedeutet (Liste unter "Leer jetzt Pflicht").
4. **Grenzen aus dem Markup gelten jetzt im Browser** (`data-min`/`data-max`, bisher wirkungslos) -- z. B. Wartungsintervall 1–24 statt "0" still zu 12, Dauer in `/mobil` ab 0,25 h (der Server nimmt mehr als 0).
5. **`data-stellen` dort, wo der Server Nachkommastellen begrenzt** (Mahngebühr 2, Basiszinssatz 3) **und bei Geldfeldern auf einer Spalte mit zwei Stellen** (Zahlungen, Erstattung, Rest zuordnen, Eingangsrechnung, Betriebskosten, Anschaffungs- und laufende Kosten) -- sonst keine Grenze, auch wo die Spalte weniger Stellen hat (Nebenbefund 3).
6. **Ein abgelehntes Feld bleibt rot markiert bis zur nächsten Eingabe, und keine abschließende Aktion der Seite geht hinaus, solange es markiert ist** (`abschliessen()`).
7. **Ein Wert wird gelesen, bevor irgendetwas gespeichert wird** -- auch wo eine Funktion zwei Speichern hintereinander auslöst.
8. **Die Zeilen des Zahlungsdialogs der Rechnungsseite tragen kein `data-zahl`**: sie halten den getippten Text beim Neuzeichnen und werden über `zahlLesen()` mit eigenem Feldnamen ("Zahlung R-…") gelesen; ein abgelehnter Betrag sperrt "Buchung bestätigen".
9. **Funktionen, die Klicktests und Tests mit einem Text aufrufen, nehmen weiter einen Text** (`quickItem()`, `quickIst()`, `saveInlineField()`, `saveContinuationHeaderPosition()`): ein Text geht über `zahlLesen()`, ein Feld über `zahlFeld()`.
10. **Ausnahmeliste mit zwei Einträgen**: `Number(p.value)` in `_berlin_date.html` (Teil von `Intl.formatToParts()`, kein Feld) und die Kunden-Auswahl in `inquiries.html` (ID aus einer Schleife).
11. **Der Scanner sieht Texte, die nicht auflösbar sind, als Zahlenfeld-Kandidaten** (lieber ein Fund zu viel), und der rohe Text eines `data-zahl`-Felds ist immer ein Fund, auch nur auf leer geprüft.
12. **Zahlungsbedingung "Tage" 0 bleibt erlaubt**; nur leer ist abgelehnt. Der Server bleibt unverändert (Pflichtfeld, ganze Zahl ≥ 0).
13. **Feldnamen für lesbare 422** stehen je Seite in `FELDNAMEN` (Einstellungen, Plantafel, Arbeitsvorbereitung); fehlt ein Name, erscheint der der API.
14. **Punkt 3 ändert nur Beschriftung, Rückfrage und Statuszeile**; Funktionsnamen und Endpunkt (`/api/reminders/{id}/send`) bleiben.
15. **"Team entfernen" meldet unter den zugewiesenen Teams** (neue Statuszeile); Einzelmitarbeiter entfernen und Material speichern bleiben, wie sie sind (Nebenbefund 5).

#### Leer jetzt Pflicht (bis 1.8.108 still 0 oder erst vom Server abgelehnt)

Einstellungen: Tage bis Fälligkeit, MwSt.-Satz eines Steuerschlüssels, acht Ränder, Nummernkreis Start und nächste Nummer, Zahlungsfrist
der Mahnstufe, SMTP-Port, Position der Wiederholungszeile, Basiszinssatz, Wartungsfenster (Monate). Mahnwesen und Rechnungsseite:
Zahlungsfrist im Mahnungs-Editor. Angebot: Menge und Einheitspreis der Position. Auftrag: Menge und Preis in der Liste und im Dialog, Menge
des Nachtrags. Rechnung: Pauschalbetrag, Ist-Menge (Dialog und Liste). Zeiterfassung Büro: Stunden (Einzel- und Gruppenbuchung),
Backoffice: Stunden der Korrektur, Tagesstunden eines Zeitmodells, Pausenregel (ab Stunden, Minuten). Stammdaten: Wochenstunden,
Einkaufspreis. Alle übrigen Felder behalten ihre Vorgabe bei leer.

#### Tests und Prüfung

- Neu `tests/test_v414_zahleneingaben.py`: Angriffstabelle in node -- 21 gültige Eingaben, 10 mehrdeutige ("1.25", "0.5", "12.50",
  "1.250.5" …, jeweils mit Meldung und dem richtigen Weg darin), 25 Nicht-Zahlen ("1,2,3", "1e3", "Infinity", "1 250", "12 %", "1.25,5",
  "1,250.5", arabische und vollbreite Ziffern, geschütztes Leerzeichen …), Grenzen, ganze Zahl, Nachkommastellen, leer und Pflicht, gekürzte
  Meldung; `zahlText()` (auch "1.250" aus der API = "1,25") und der Weg hin und zurück für zwölf Werte; `zahlFeld()` mit Optionen aus dem
  Feld, Beschriftung aus dem Label, Markierung und ihr Ende, `zahlVorschau()` wirft nie; `abschliessen()` geht mit einem markierten Feld
  nicht hinaus; Strukturtest über alle Vorlagen, Ausnahmeliste ohne veraltete Einträge, jede Seite mit Zahlenfeld bindet den Baustein ein,
  es gibt Zahlenfelder und sie lesen über `zahlFeld()`; Selbsttest des Scanners an 30 erfundenen Vorlagen (18 Funde, 11 erlaubt, Einbindung).
- Klicktest neu `klicktest_zahleneingaben.py` (Angriffstest im echten Browser, getippt über `Input.insertText`, 26 Prüfungen): Nachtrag
  "1.250"/"1.250,5" gespeichert als 1250/1250,5, "1.25" mit Meldung abgelehnt, nichts gespeichert, Feld markiert und nach dem
  Korrigieren nicht mehr; Zahlungsbedingung ohne Tage und mit "1.5" abgelehnt, nichts gespeichert, 422 (Bezeichnung zu lang) lesbar, "30"
  gespeichert; "Festschreiben" statt "Versenden", geklickt festgeschrieben ohne E-Mail; Plantafel "1.25" und 422 lesbar; Team entfernen
  mit dem Grund des Servers. Dabei auch der Befund vorweg (Chrome macht aus "1.250" in `type="number"` 1,25) mit einem Probe-Skript
  gemessen.
- **Angepasste Erwartungen** (Regel 28):
  - `klicktest_rechnungen_sperren`, Prüfung "Mahnung: kein Versenden": sucht jetzt den Knopf "Festschreiben" (Name "Mahnung: kein
    Festschreiben"); altes Soll "kein Knopf 'Versenden'" -- nach der Umbenennung wäre das immer erfüllt.
  - `klicktest_vertrag_abschrift`, Prüfung "422 Abschlag: lesbar" -> "Abschlag 1.25: lesbar": altes Soll "1.234,56" ergibt den 422
    "Betrag netto muss eine Zahl sein (ohne Tausenderpunkt)." -- seit 1.8.109 ist "1.234,56" gültig (1234,56) und erreicht den Server
    als Zahl; neues Soll: "1.25" ergibt die Meldung des Bausteins. Den lesbaren 422 der Seite prüft weiter das Auftragsdatum.
  - `klicktest_nebenforderungen`, Prüfung "Vorschläge 0 / 10 / 15 €": liest die Gebührenfelder über `zahlLesen()` statt `Number()`
    (das Feld zeigt jetzt "10,00"); Soll unverändert.
  - `test_v377_leistungszeitraum::test_invoice_page_takes_the_proposal_only_by_click`: altes Soll "das Wort 'festschreiben' kommt in
    der Rechnungsseite nicht vor" (gemeint: kein Helfer, der den Zeitraum still einträgt) -- die Rückfrage der Mahnung sagt jetzt
    "festschreiben"; neues Soll: kein Aufruf `festschreiben(`.
  - Aufbau ohne geänderte Prüfung: `test_v334_auswahl_restfaelle.py::seite()` bindet `_zahl.html` ein (Attrappe mit `getAttribute`),
    `test_v397_kleinkram_zahlungen.py::_zahlungskarte()` liest den Baustein statt der entfallenen Zeile `fmt`,
    `test_v399_teil_updates_geld.py` (Attrappe und Baustein; die Kalkulation füllt ihre Felder deutsch über `zahlText()` statt über `v()`).
- Gegenproben (Regel 24): 19 von 19 rot, jede aus dem erwarteten Grund -- Punkt ohne drei Ziffern angenommen (Mehrdeutiges, auch im
  Klicktest: "1.25" ohne Meldung), Punkt als Dezimaltrenner ("1.250" = 1,25), `type="number"`, eigene Umwandlung `Number(…value)`
  (auch im Klicktest: Plantafel "1.25" ohne Meldung), roher Feldtext an den Server, Füllen ohne `zahlText()`, Komma ersetzen,
  `parseFloat`, Baustein nicht eingebunden, `abschliessen()` ohne Sperre, Scanner ohne Prüfung der Feldwerte, "Tage" leer als 0 (auch im
  Klicktest), `detail` roh in Einstellungen und Plantafel, Knopf wieder "Versenden", "Team entfernen" ohne `catch`. Jede Datei byte-genau
  zurück (SHA-256), kein Marker.

#### Nebenbefunde (nur gemeldet)

1. **Der Server ersetzt bei Antworten vom Typ Zahl (Checklisten) selbst das Komma** (`app/checklists.py:1094`,
   `app/checklist_rules.py:78`: `Decimal(str(value).replace(",", "."))`) -- käme dort Text an, wäre "1.250" 1,25. Die Seite schickt seit
   1.8.109 eine Zahl; andere Wege (ein älteres Gerät, ein Skript) gingen weiter durch diese Umwandlung.
2. **`inputmode="decimal"` zeigt auf iOS kein Minus** -- Felder, die negativ sein dürfen (Zuschläge in Leistung und Kalkulation, Verschnitt,
   Messwerte und Grenzwerte), lassen sich auf dem iPad nur mit externer Tastatur negativ eingeben.
3. **Spalten mit weniger Nachkommastellen als die Eingabe erlaubt, ohne `decimal_places` im Schema** -- PostgreSQL rundet still: Ränder
   `Numeric(5,1)`, Position der Wiederholungszeile `Numeric(6,2)`, Skonto `Numeric(5,2)`, geplante Stunden `Numeric(18,2)`, Neigung
   `Numeric(5,2)` (über 999,99 Überlauf), Fläche, Mengen, Messwerte `(18,2)`, Material `(18,3)`.
4. **Anzeigen im Maschinenformat** (keine Eingaben): Menge und Verschnitt in der Materialtabelle der Leistung ("1.5"), "Soll: 12.50–…" im
   Einsatzbericht, der Vergleichswert in der Regelbeschreibung der Checklisten-Vorlage.
5. **Fehler des Servers ohne Anzeige**: Arbeitsvorbereitung Einzelmitarbeiter ändern/entfernen und Material speichern (kein `catch`);
   Zeiterfassung Büro und Backoffice zeigen ein 422 weiter als "[object Object]" (`api()` ohne `fehlerText()`); in der Backoffice-Einstellung
   erscheint eine abgelehnte Standardpause beim DATEV-Häkchen auf dem anderen Reiter.
6. **`_fehlertext.html` sagt bei `decimal_parsing` "(ohne Tausenderpunkt)"** -- seit die Seiten Zahlen schicken, kann das nur noch ein
   anderer Weg auslösen; der Hinweis passt nicht mehr zur Eingabe.
7. **`tests/test_v362_maengel_im_protokoll.py`** startet die zweite Aktion zweier PG-Tests mit `Session()` direkt im Thread, ohne die
   Sitzung zu schließen -- dasselbe Muster wie die `_run`-Kopien (Punkt 7), dort nicht als `_run`.

### Umsetzung 1.8.110: Revisionsnummer unter der Sperre der Auftragszeile (Punkt 5)

#### Befund

Gefunden in den Endläufen zu 1.8.108 (`b8ddb1c`, einer von vier Läufen, `test_v386::test_postgresql_two_addenda_at_once_get_two_numbers`):
`app/orders.py::create_order_revision()` las `max(revision_number) + 1` ohne Sperre und lief erst NACH dem Commit der Änderung, die sie
sichert (Beauftragen, Abgleich mit dem Angebot, Nachtrag anlegen und entfernen; die Revision von Hand committete sie selbst). Zwei
gleichzeitige Nachträge: beide lasen dieselbe Höchstnummer, der zweite scheiterte am Unique-Index `uq_order_revision_number` (API 500) --
sein Nachtrag war da schon committet. Der Test traf den Wettlauf nur, wenn die beiden Revisionen nach dem Freigeben der Sperre zufällig
gleichzeitig liefen; derselbe Doppel-Commit von `create_order_from_quote()` war die Ursache der Verklemmung im Nachtrag 2 zu 1.8.108.

#### Was gebaut ist

- `create_order_revision()` sperrt die Auftragszeile (`app/acceptances.py::lock_order()`, dieselbe Sperre wie Abnahme, Abgleich und
  Rechnungen), schreibt die Änderung des Aufrufers (`flush()`), liest den Auftrag frisch (`load_order(…, frisch=True)`, populate_existing --
  der Stand MIT der noch nicht committeten Änderung), vergibt die Nummer und legt die Revision an, ohne zu committen.
- Jeder Aufrufer committet Änderung und Revision zusammen: Beauftragen (Auftrag und Revision 1 in einem Commit), Abgleich mit dem Angebot
  (Abgleich und Revision; danach wie bisher `refresh_preparation_materials()`), Nachtrag anlegen und entfernen (unter der Sperre, die sie
  ohnehin halten), Revision von Hand (der Router committet), Start (`ensure_existing_order_revisions()`, je Auftrag ein Commit).
- Unter SQLite wirkt `FOR UPDATE` nicht (nur Entwicklung, wie überall); dort wartet ein zweiter Schreiber an der Schreibsperre der
  Datenbank, sobald die Transaktion geschrieben hat.

#### Festlegungen 1.8.110 (Bitte bestätigen)

1. **`create_order_revision()` committet nie selbst**; jeder Aufrufer committet Änderung und Revision in einem Commit -- scheitert die Revision, ist auch die Änderung nicht gespeichert.
2. **Gesperrt wird die Zeile des Auftrags** (`lock_order()`), nicht eine eigene Zeile oder Tabelle -- dieselbe Sperrreihenfolge wie alle Wege am Auftrag.
3. **Der Stand der Revision ist der vor dem Commit** (nach `flush()` frisch gelesen); er enthält genau die Änderung, die die Revision sichert.

#### Tests und Prüfung

- Neu `tests/test_v415_revision_unter_sperre.py` (7, davon 3 gegen PostgreSQL): die Revision committet nicht und fällt mit der Transaktion
  des Aufrufers; scheitert die Revision eines Nachtrags, ist auch der Nachtrag nicht gespeichert; die Revision eines Nachtrags enthält ihn,
  die des Entfernens nicht mehr; die Revision von Hand über die API ist committet. **Angriffstest gegen PostgreSQL** (Helfer `_run`: die
  erste Aktion hält ihren Commit eine Sekunde): zwei Revisionen von Hand zugleich -> 2 und 3 (nach altem Stand deterministisch
  `UniqueViolation uq_order_revision_number`); zwei Nachträge zugleich -> Revisionen "Nachtrag N1 angelegt" (2) und "Nachtrag N2 angelegt"
  (3); ein Nachtrag wartet auf eine Revision von Hand.
- Gegenproben (Regel 24): 4 von 4 rot -- ohne Sperre (PG: `UniqueViolation … (order_id, revision_number)=(1, 2)`), Revision committet wie
  bis 1.8.109 (die Revision bleibt nach dem Zurückrollen des Aufrufers), Nachtrag vor der Revision committet (der Nachtrag bleibt, obwohl
  die Revision scheitert), Router ohne Commit (die Revision fehlt danach). Jede Datei byte-genau zurück (SHA-256).
- Angepasste Erwartungen (Regel 28): keine.

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
  positivem Rechnungsbetrag. (Seit 1.8.90 gebaut.)
- **E-Mail zur Schlussrechnung** nennt den Zahlbetrag bzw. den Erstattungsbetrag. (Seit 1.8.90 gebaut.)

Ergänzt am 13.10.2026 (Nacharbeiten R4c), übernommen wie gegeben -- Wortlaut unter "Nacharbeiten R4c":

- **Finanzen und Dashboard** zählen nach der gültigen Schlussrechnung je Auftrag nur ihren Zahlbetrag: positiv als offen, negativ als
  Guthaben; die abgezogenen Rechnungen zählen nicht mehr einzeln, an ihnen steht „enthalten in Schlussrechnung R-…“ statt „teilweise
  bezahlt“. (Seit 1.8.91 gebaut.)
- **Schlusstext bei negativem Zahlbetrag**: ohne Zahlungsaufforderung, stattdessen ein eigener Text für die Erstattung, gepflegt in den
  Einstellungen. (Seit 1.8.92 gebaut.)
- **Guthaben des Kunden**: nicht zugeordneter Rest und Guthaben zusammen, aufgeschlüsselt; eine Erstattung kann beides ausgleichen.
  (Seit 1.8.93 gebaut.)

Ergänzt am 13.10.2026 (Vorgabe 1.8.95, Punkt 2), übernommen wie gegeben -- Wortlaut unter "Veraltete Antworten und Rechnungen über 0 €":

- **Rechnungen über 0 € oder weniger** gibt es nur als Storno oder als Endrechnung mit Abzügen; jede andere Rechnung muss über 0 € liegen,
  sonst 409 beim Festschreiben. (Seit 1.8.95 gebaut.)

Ergänzt am 13.10.2026 (nach Nachfrage 10 zu 1.8.95: Zeitbuchung nach der Schlussrechnung), übernommen wie gegeben -- festgehalten,
nicht gebaut:

- **Gewährleistungs- und Kulanzstunden** (für Stufe 2d und die Rüge): werden auf den ursprünglichen Auftrag gebucht. Eine Zeitbuchung
  lässt sich einem Mangel zuordnen oder als Kulanz kennzeichnen; sie ist dann nie abrechenbar und erscheint in der Nachkalkulation
  getrennt als „davon Mängelbeseitigung / Kulanz“. Ergänzt mit der Vorgabe 1.8.96 (13.10.2026): Ein Auftrag mit offenem, freigegebenem
  Mangel bleibt für Plantafel, /mobil und Zeiterfassung wählbar, auch wenn er abgeschlossen ist. Stunden nach der Schlussrechnung ohne
  diese Zuordnung zeigt das Backoffice als „nach Schlussrechnung, nicht abrechenbar“ zum Einordnen.
- **Auftrag ohne Rechnung** (Parkplatz vor dem Echtbetrieb, siehe unten): „Abschließen ohne Rechnung“ nur Büro, nur solange keine
  Rechnung existiert, mit Pflichtbegründung und Hinweis auf nicht abgerechnete Stunden.

Anlass, der Befund zu Nachfrage 10 (13.10.2026, Stand 1.8.95): Nach der Schlussrechnung bzw. der abschließenden Rechnung aus Aufwand
buchen Monteur (/mobil, solange ein Einsatz in ±14 Tagen eingeplant ist) und Büro weiter auf den Auftrag; der Server prüft beim Buchen
weder Rechnung noch Auftragsstatus, nur die Zuordnung des Monteurs und das Sperrdatum. Die Stunde steht am Auftrag und zählt in den
Summen, eine Rechnung aus Aufwand danach lehnt der Server ab (409) -- sie wird nie abgerechnet, und beim Buchen sagt das niemand. Den
Status „abgeschlossen“ setzt keine Rechnung, nur das Büro von Hand; dann fehlt der Auftrag in den Auswahllisten (/mobil,
Büro-Zeiterfassung, Plantafel), die API nimmt Buchungen trotzdem an, ein vorher gestarteter Timer lässt sich danach stoppen. Eine
Buchung ohne Auftrag gibt es nicht (`TimeEntry.order_id` ist Pflicht) -- eine Gewährleistungsstunde landet heute auf irgendeinem
angebotenen Auftrag oder wird gar nicht gebucht.

## Parkplatz vor dem Echtbetrieb

Festgehalten, nicht gebaut; vor dem Echtbetrieb zu entscheiden bzw. zu bauen.

- **`content` der Layout-Bausteine entfernen** (14.10.2026, Vorgabe ab 1.8.105, zum Befund 99-13 unter "Umsetzung 1.8.103"): die Spalte
  `document_layout_blocks.content` wird nirgends eingegeben (nur über `PUT /api/document-layout/blocks/{id}`) und nirgends gezeigt (kein
  PDF, keine Vorlage) -- mit den übrigen ungenutzten Spalten entfernen (Migration, Antwortschema `DocumentLayoutBlockOut`, PUT-Schema `DocumentLayoutBlockUpdate`).
- **„Abschließen ohne Rechnung“** (13.10.2026, siehe "Entscheidungen Rechnungen", Ergänzung nach Nachfrage 10 zu 1.8.95): für einen
  Auftrag ohne Rechnung -- nur Büro, nur solange keine Rechnung existiert, mit Pflichtbegründung und Hinweis auf nicht abgerechnete
  Stunden.
