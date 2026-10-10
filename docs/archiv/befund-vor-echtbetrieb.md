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
nicht stornierten pauschalen Abschlag gesperrt.

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

4d seit 1.8.71 behoben ("Umsetzung 1.8.71"); 4a-4c offen, Entscheidungen dazu unter "Entscheidungen Rechnungen".

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
unbestätigt; aus Nr. 9 ist "Entwurf löschen" seit 1.8.73 unter der Sperre.

1. "Gültig" heißt festgeschrieben und nicht storniert (`versendet`/`bezahlt`). Wo die Vorgabe "auch als Entwurf" sagt (Punkt 1,
   Anlegen der Schlussrechnung), zählt der Entwurf mit; Punkt 3 nur die festgeschriebene -- ein Entwurf der Schlussrechnung sperrt
   das Storno eines Abschlags nicht (dass er dann falsch rechnet, ist 1b, R4).
2. Beim Festschreiben sperrt nur eine schon festgeschriebene Schlussrechnung bzw. ein festgeschriebenes Storno -- Altbestand mit zwei
   Entwürfen: der zuerst festgeschriebene gilt, der andere bleibt Entwurf ohne Nummer (löschbar).
3. "Keine weiteren Abschläge" gilt für pauschal und nach Leistungsstand, beim Anlegen und beim Festschreiben eines älteren Entwurfs.
   Ein Entwurf der Schlussrechnung sperrt keinen Abschlag. **"Rechnung aus Aufwand" bleibt nach der Schlussrechnung möglich** (kein
   Abschlag, nicht Teil der Vorgabe). **Offen (10.10.2026): nichts ändern.**
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
   (siehe Nebenbefund 2). Seit 1.8.73 ist "Entwurf löschen" unter der Sperre.

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
  still zu entstehen.

### Festlegungen – Bitte bestätigen

1. Gesperrt wird mit einem UPDATE ohne Änderung statt `SELECT … FOR UPDATE` -- dieselbe Wirkung unter PostgreSQL, dazu unter SQLite
   (Entwicklung) die Schreibsperre der Datenbank; die Sperre hält bis zum Commit. Ein Ablauf, der mehrere Nummern zieht
   (Schnellauftrag: Projekt, Angebot, Auftrag), hält sie bis zum Ende; gleichzeitige Anlagen derselben Art warten kurz.
2. Kunde, Anfrage, Projekt und Angebot zählen jetzt hoch: eine gelöschte Nummer wird nicht wieder vergeben (vorher die nächste freie
   über der höchsten). Die Kundennummer wird wie bisher nur beim ersten Anlegen des Profils gezogen -- auch über die zwei GET-Routen,
   die ein fehlendes Profil nachlegen (`GET /api/customers`, `/{id}`).
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

## Entscheidungen Rechnungen (10.10.2026, festgehalten, nicht gebaut)

Vorgabe vom 10.10.2026, übernommen wie gegeben (Bezug Punkt 1 und 4):

- **Schlussrechnung als Endrechnung**: alle Positionen zu 100 %, Abzug aller festgeschriebenen, nicht stornierten
  Abschlagsrechnungen je mit Netto und USt, darunter „zzgl. noch offen aus Abschlag Nr. …“ und Zahlbetrag.
- **Abschlagsrechnungen** selbst nicht kumuliert.
- **Offene Abschläge** nach der Schlussrechnung nur noch über diese gemahnt.
- **Zahlung auf den Zahlbetrag**: Vorschlag zuerst auf offene Abschläge (ältester zuerst), dann Schlussrechnung, das Büro bestätigt.
- **Rechnungsdatum** = Tag der Ausgabe, jede Rechnung mit Pflicht-Leistungszeitraum, Nummer beim Festschreiben, Nummernkreise beim
  Start auf 1. (Was dabei heute passiert: "Umsetzung 1.8.73" -> Befund b.)
- **Storno**: höchstens ein Storno je Rechnung, kein Storno eines Stornos.
- **Steuersatz**: keine mehreren Steuersätze je Rechnung.
