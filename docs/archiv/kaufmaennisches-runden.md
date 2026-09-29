# Kaufmännisches Runden (seit 1.8.11)

Runde 0e. Vorher rundete das Projekt Geld und Stunden an vielen Stellen halb-gerade
(`ROUND_HALF_EVEN`, "Banker's Rounding": 0,125 -> 0,12), ohne dass das irgendwo entschieden
worden wäre: `Decimal.quantize()` ohne `rounding=` nimmt die Rundungsart des Decimal-Kontexts,
und die steht in Python auf halb-gerade. Dasselbe gilt für die Formatierung `f"{betrag:.2f}"`.
Angebot, Auftrag, Kalkulation und Verrechnungssatz rundeten schon kaufmännisch
(`ROUND_HALF_UP`), Rechnung, Skonto, Mahnung, Eingangsrechnung, Betriebskosten und alle
Stundensummen nicht.

## Regel

- **Geld und Stunden über `app/rounding.py`**: `round_money()` (Cent), `round_hours()`
  (Hundertstel), `round_half_up(wert, stellen)` für alles andere (Auslastung in 0,1 %,
  gespeicherte Stunden in 0,0001). Die Hälfte rundet vom Nullpunkt weg, -0,125 -> -0,13, genau wie
  PostgreSQL `NUMERIC` rundet. Ein `float` geht über seinen Text (0.285 -> 0,29), nicht über
  seinen Binärwert (0,28499…).
- **Kein `quantize()` ohne Rundungsart unter `app/`.** `tests/test_v315_commercial_rounding.py`
  durchsucht `app/` per AST (auch Aufrufe über mehrere Zeilen, `rounding=` oder zweites
  Positionsargument) und nennt jede Fundstelle mit Datei und Zeile.
- **Vor dem Formatieren runden.** `f"{x:.2f}"` rundet halb-gerade, sobald `x` mehr als zwei
  Nachkommastellen hat. Die Formatierer `money()`/`money_bare()`/`qty()` in
  `app/document_pdf.py` bleiben bewusst unverändert (siehe unten); was sie bekommen, muss schon
  gerundet sein.
- Die lokalen Helfer `calculation.q()`, `labor_rate.q()`, `orders.money_q()`,
  `projects.money_q()` und `productive_hours._q()` rundeten schon kaufmännisch und rufen jetzt
  die zentralen Helfer auf.

## Rechnungen: Rundungsregel je Rechnung (GoBD)

`compute_invoice_totals()` speichert nichts, sondern rechnet bei jedem Aufruf neu, auch für das
PDF einer längst versendeten Rechnung. Hätte 1.8.11 einfach umgestellt, zeigte der Nachdruck einer
alten Rechnung mit halbem Cent einen anderen Betrag als das versendete Dokument (Regel 5).
Deshalb trägt jede Rechnung ihre Regel:

- **`Invoice.rounding_rule`** (Migration `7e3c1b9a5d24`, nullable, Vorgabe `"half_up"`):
  `"half_up"` rundet Positionsbeträge, Pauschalbetrag, USt und Skonto kaufmännisch auf den Cent,
  Netto ist die Summe der gerundeten Positionen, Brutto = Netto + USt (wie Angebot und Auftrag).
  Leer heißt "vor 1.8.11 versendet": Die Rechnung rechnet genau wie damals, ungerundet, gerundet
  erst beim Formatieren, halb-gerade. Das PDF bleibt dasselbe.
- **Die Migration markiert nur offene Entwürfe**, keine Storno-Entwürfe. Kein Betrag wird neu
  berechnet oder geschrieben; `billed_total` bleibt mit sechs Nachkommastellen gespeichert,
  gerundet wird beim Lesen (`invoice_line_total()`).
- **Storno übernimmt die Regel des Originals** (`create_storno_draft()`), damit sich beide auf
  den Cent aufheben. Die Zuweisung steht nach dem `flush()`: Ein `None` im Konstruktor ersetzt
  SQLAlchemy durch den Vorgabewert `"half_up"` (beim Bauen so aufgefallen).
- **Mahnung folgt der Rechnung** (`reminders.reminder_total()`): Offener Betrag + Gebühr rundet
  nach `invoice_rounding()` der Rechnung, eine alte Mahnung druckt also denselben Gesamtbetrag.
  Der offene Betrag einer neuen Mahnung ist das gerundete Brutto.

## Wo sich ein Geldbetrag ändert (Liste zu Punkt 3 der Runde)

Jeweils nur bei einem exakt halben Cent (bzw. halben Hundertstel), sonst gleich. Je Stelle ein
Halbcent-Test in `tests/test_v315_commercial_rounding.py`.

| Stelle | Beispiel | vorher | ab 1.8.11 | Gilt für |
|---|---|---|---|---|
| Rechnung, USt (auch Pauschal-Abschlag) | 1,50 € × 19 % = 0,285 | PDF 0,28 / Brutto 1,78 (API 0,285) | 0,29 / 1,79 | Rechnungen ab 1.8.11 und offene Entwürfe |
| Rechnung, Positionsbetrag und Netto | 2,5 × 0,85 = 2,125 | PDF 2,12; Netto 2,12 + USt 0,40 ≠ Brutto 2,53 | 2,13 + 0,40 = 2,53 | dto. |
| Rechnung, Netto aus mehreren Positionen | 2 × 0,125 | 0,25 (ungerundet summiert) | 0,26 (Summe der gerundeten) | dto. |
| Rechnung aus Aufwand | 1,2525 Std. × 50,00 = 62,625 | PDF 62,62 | 62,63 | dto. |
| Skonto im Zahlungssatz | 2 % von 10,25 = 0,205 | 0,20 € | 0,21 € | dto. |
| Mahnung, offener Betrag | Brutto 1,785 | gespeichert 1,785, im PDF 1,78 | 1,79 | neue Mahnungen zu Rechnungen ab 1.8.11 |
| Mahnung, Gesamtbetrag | 1,79 + 2,515 = 4,305 | 4,30 | 4,31 | dto.; alte Rechnungen weiter halb-gerade |
| Eingangsrechnung, Brutto (je Position und gesamt) | 1,50 € × 1,19 = 1,785 | 1,78 | 1,79 | **alle**, auch bestehende (nur Anzeige, nie gespeichert) |
| Offene Verbindlichkeiten (Summe) | Summe gerundeter Bruttobeträge | – | folgt der Zeile darüber | alle |
| Betriebskosten, Brutto | 1,50 € × 1,19 | 1,78 | 1,79 | alle (nur Anzeige) |
| Betriebskosten, Monatssumme | 1,26 € / 12 = 0,105 | 0,10 | 0,11 | alle (nur Anzeige) |
| DATEV-Export (Stunden, keine Beträge) | 1,125 Std., Rundungsintervall 0 | 1,12 | 1,13 | jeder Export ab 1.8.11, auch für abgeschlossene Zeiträume |

**Unverändert:** Angebot und Auftrag (rundeten schon kaufmännisch), Kalkulation,
Verrechnungssatz, Produktivstunden, der gespeicherte Jahresbetrag der Betriebskosten
(`annual_amount`: Netto × 12/4/2/1 kann keinen halben Cent ergeben; bestehende Werte werden ohnehin
nicht neu berechnet), die Stundenberechnung eines Timers (`compute_hours()`, schon kaufmännisch).

**Stunden** (keine Geldbeträge, dieselbe Umstellung): Summen der Zeiterfassung
(`summarize_entries()`, Auftragsstunden, Backoffice-Übersicht, DATEV, Stundenzettel-PDF des
Monteurs, Einsatzbericht-PDF), Plantafel (Kapazität, verplante Stunden, Auslastung),
Arbeitsvorbereitung (Soll/Ist-Abweichung), Stunden einer Gruppenbuchung (Mittelwert, vier
Nachkommastellen). Ein halbes Hundertstel entsteht nur bei 18-Sekunden-genauen Zeiten oder
Mittelwerten, mit einem Rundungsintervall der Zeiterfassung (ganze Minuten) nie.

**DATEV bei abgeschlossenem Zeitraum:** Ein erneuter Export eines vor 1.8.11 exportierten Monats
kann bei einer Buchung mit halbem Hundertstel um 0,01 Std. vom damaligen abweichen. Die Buchungen
selbst sind unverändert. Bewusst nicht eingefroren (kein gespeicherter Export, keine
GoBD-Rechnung); bei Bedarf den damals erzeugten Export verwenden.

## Bewusst nicht geändert

- **Formatierer in `app/document_pdf.py`** (`money()`, `money_bare()`, `qty()`) runden weiter
  halb-gerade, wenn sie mehr Stellen bekommen. Eine alte Rechnung liefert ihre ungerundeten
  Beträge und muss genau so formatiert werden wie damals. Neue Beträge kommen schon gerundet an.
  Betroffen bleiben nur Einzelpreise und Mengen mit mehr Stellen als angezeigt (EP mit drei
  Nachkommastellen, Menge mit vier).
- **Die Oberfläche formatiert selbst** (`toLocaleString`, rundet die kürzeste Dezimaldarstellung
  kaufmännisch). Für alte Rechnungen zeigt die Rechnungsseite deshalb 0,29 € USt, ihr PDF 0,28 EUR
  -- so war es schon vor 1.8.11 (Klicktest `scripts/klicktest_rechnung_rundung.py`, Rechnung D).
  Für Rechnungen ab 1.8.11 liefert der Server gerundete Beträge, Seite und PDF stimmen überein.

## Verifikation (1.8.11)

27 neue Tests, Gegenproben je Stelle (alter Code rein, zugehörige Tests rot, danach
wiederhergestellt): Suchtest, Helfer, Rechnungsregel, Positionsbetrag, Storno, Mahnung, Skonto,
DATEV, Migration, beide PDF-Formatierer. Migration unter SQLite und in einem Wegwerf-Schema der
lokalen PostgreSQL-Instanz: ganze Kette bis `head`, dann mit Rechnungen in allen Zuständen zweimal
zurück und wieder hin, `alembic check` ohne Abweichung. Klicktest der Rechnungsseite 10/10, gegen
den alten Code 3 rot (vom Server gelieferte Beträge, Skonto).
