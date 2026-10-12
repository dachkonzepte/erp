# Zahlungen (Zahlungsstufe Z1 seit 1.8.78)

Grundlage: Befund Zahlungsstufe in `befund-vor-echtbetrieb.md` ("Umsetzung 1.8.77" -> "Befund Zahlungsstufe") und dort
"Entscheidungen Rechnungen" (Zahlung auf den Zahlbetrag, Einbehalt). Code: `app/payments.py` (Geschäftslogik),
`app/routers/payments.py` (Endpunkte), Modelle `Payment`/`PaymentAllocation` (`app/models.py`), Migration `c7d41e9a2b63`.
Das Mahnwesen folgt in Z2.

## Umsetzung 1.8.78: Zahlungseingänge (Z1)

### Vorgabe vom 12.10.2026 (übernommen wie gegeben)

1.8.77 geprüft, Festlegungen 1–5 bestätigt.

Zahlungsstufe Z1: Zahlungseingänge. Grundlage: Befund 1.8.77 und „Entscheidungen Rechnungen“ im Archiv. Neue Archivdatei
zahlungen.md.

1. Modell: Zahlung (Kunde, Eingangsdatum, Betrag, Notiz) mit Zuordnungen auf eine oder mehrere festgeschriebene Rechnungen
   desselben Kunden; nicht zugeordneter Rest bleibt am Kunden sichtbar. Abzüge je Rechnung mit Art Skonto oder Einbehalt.
2. Buchen an der Rechnung: Vorschlag zuerst auf die älteren offenen Rechnungen desselben Auftrags, dann diese; weitere
   Rechnungen nur von Hand. Skonto als Vorschlag, wenn der Eingang in der Frist liegt und der Betrag passt. Einbehalt nie
   automatisch. Alles wird bewusst bestätigt.
3. Beträge je Rechnung: offen = Brutto − Zuordnungen − Skonto; mahnfähig = offen − Einbehalt. Status nur abgeleitet: offen,
   teilweise bezahlt, Einbehalt offen, bezahlt. Der Knopf „bezahlt“ entfällt.
4. Unveränderlich: Korrektur nur als Gegenbuchung mit Begründung, nichts löschen. Buchen und Korrigieren unter der Sperre der
   betroffenen Auftragszeilen, in fester Reihenfolge.
5. Storno: Eine Stornorechnung ist nie offen und nicht bebuchbar. Eine Rechnung mit zugeordneten Zahlungen lässt sich erst
   stornieren, wenn die Zuordnungen gelöst sind; die Zahlung bleibt dann nicht zugeordnet.
6. Finanzen und Dashboard rechnen mit dem offenen Betrag statt mit dem Brutto der versendeten Rechnungen; Stornorechnungen
   zählen nicht als offen.
7. Altbestand „bezahlt“: Die Migration legt je Rechnung eine Zahlung über das Brutto zum bezahlt-Datum an, gekennzeichnet als
   übernommen.

Das Mahnwesen kommt in Z2; dort nur ändern, was Punkt 3 zwingend verlangt.
Angriffstests mit Gegenprobe: Überbuchung, Rechnung eines fremden Kunden, Buchung auf Storno, gleichzeitiges Buchen gegen
PostgreSQL. Eigene Festlegungen mit „Bitte bestätigen“. Nebenbefunde nur melden. Wird der Umfang zu groß: nach Punkt 4 committen
und den Rest auflisten. Commit nach Regel 13, Bericht kurz.

### Vorweg

- Festlegungen 1.8.77 Nr. 1–5 in `befund-vor-echtbetrieb.md` als bestätigt markiert.
- Der Umfang blieb in einer Version: alle sieben Punkte gebaut, ein Commit.

### Was gebaut ist

**Modell** (Migration `c7d41e9a2b63`, zwei neue Tabellen, keine Spalte an einer bestehenden):
- `Payment` (`payments`): Kunde, Eingangsdatum (`received_on`), Betrag (`Numeric(18, 2)`), Notiz, Herkunft `origin`
  (`erfasst` | `uebernommen`), erfasst von (Konto ohne Fremdschlüssel wie bei der Abnahme, Name als Schnappschuss).
- `PaymentAllocation` (`payment_allocations`): Zahlung, Rechnung, Art `kind` (`zahlung` | `skonto` | `einbehalt`), Betrag.
  Skonto und Einbehalt sind Abzüge an der Rechnung -- kein Geld aus der Zahlung, aber mit ihr gebucht und mit ihr zurückgenommen.
- Beide unveränderlich und nie gelöscht (ORM-Sperre am Ende von `app/models.py`, keine Ausnahme). Korrektur nur als Gegenbuchung:
  eine Zeile mit `reverses_payment_id` bzw. `reverses_allocation_id`, umgekehrtem Vorzeichen und Begründung (`reason`), höchstens
  eine je Eintrag (UNIQUE `uq_payment_reverses`, `uq_payment_allocation_reverses`). Kein `update()`/`delete()` auf beide unter
  `app/` (AST-Test).
- Historie (`app/audit.py`): jede Zahlung, Zuordnung und Gegenbuchung unter der Kennung der Zahlung ("Zahlungseingang");
  Zuordnungen auch in der Historie der Projektmappe.

**Beträge und Zustand je Rechnung** (`payment_state()`, nie gespeichert):
- Brutto für Zahlungen = `compute_invoice_totals()["gross_total"]` auf den Cent nach der Rundungsregel der Rechnung
  (`payable_gross()`; Altbestand vor 1.8.11 ungerundet, wie die Mahnung es schon tat).
- offen = Brutto − Zahlungen − Skonto; Einbehalt offen = der kleinere von Einbehalt und offen; mahnfähig = offen − Einbehalt offen.
- Zustand: `bezahlt` (offen 0, "am" = Eingangsdatum der jüngsten noch geltenden Zahlung), `einbehalt_offen` (mahnfähig 0),
  `teilweise_bezahlt` (Zahlung oder Skonto gebucht), sonst `offen`.
- Kein Zustand (nie offen, nicht bebuchbar, `not_payable_reason()`): Entwurf, Stornorechnung, stornierte Rechnung, Rechnung über
  0 € oder weniger.
- `Invoice.status` kennt nur noch `entwurf` / `versendet` / `storniert`; `VALID_STATUSES = ("versendet",)`. `paid_date` wird nicht
  mehr geschrieben (Nachweis der übernommenen Zahlung, Rückweg der Migration). `mark_invoice_paid()` und
  `POST /api/invoices/{id}/mark-paid` sind entfallen, ebenso der Knopf "Als bezahlt markieren".

**Vorschlag** (`proposal()`, `GET /api/invoices/{id}/payment-proposal?amount=…&received_on=…`, liest nur): Kandidaten sind die
älteren offenen Rechnungen desselben Auftrags (nach Rechnungsdatum, dann ID) und die gewählte. Reicht der Betrag für alle, werden
alle voll zugeordnet, der Rest bleibt am Kunden. Skonto: nur wo der Eingang in der Frist liegt (Skontodatum laut Rechnung,
`skonto_offer()`, derselbe Betrag wie im Zahlungssatz) und noch keins gebucht ist, und nur wenn der Betrag genau passt -- für alle
mit Skonto zusammen, oder an der Rechnung, an der der Betrag endet. Einbehalt nie. Neuere Rechnungen des Auftrags und Rechnungen
anderer Aufträge desselben Kunden nur von Hand (`GET /api/customers/{id}/open-invoices`).

**Buchen** (`book_payment()`, `POST /api/payments`; Rest einer Zahlung: `allocate_rest()`, `POST /api/payments/{id}/allocations`):
gebucht wird, was das Büro bestätigt. Geprüft unter der Sperre, sonst nichts geschrieben (PaymentRejected = 409): Rechnung desselben
Kunden wie die Zahlung (Kunde der Rechnung = Kunde ihres Projekts, `invoice_customer_id()`), bebuchbar, Zahlung + Skonto nicht über
offen ("Überbuchung der Rechnung"), Summe der Zuordnungen nicht über den Rest der Zahlung ("Überbuchung der Zahlung"), Einbehalt nicht
über dem danach offenen Betrag, Zahlung nicht zurückgenommen. Eingabe (400 bzw. 422): Betrag > 0, alle Beträge auf den Cent und nicht
negativ, Eingangsdatum nicht in der Zukunft (Berlin), jede Rechnung höchstens einmal je Buchung, keine Zeile ohne Betrag; unbekannter
Kunde bzw. unbekannte Rechnung 404. "Erfasst von" setzt der Server aus der Anmeldung.

**Gegenbuchung** (Begründung Pflicht): `reverse_allocation()` (`POST /api/payment-allocations/{id}/reverse`) nimmt eine Zuordnung
bzw. einen Abzug ganz zurück -- der Betrag geht an die Rechnung zurück, eine Zahlung wird wieder Rest am Kunden. `reverse_payment()`
(`POST /api/payments/{id}/reverse`, "Zahlung zurücknehmen") bucht jede noch geltende Zuordnung und die Zahlung selbst gegen, mit
derselben Begründung. Eine Gegenbuchung lässt sich nicht gegenbuchen; zweimal dasselbe 409.

**Sperren in fester Reihenfolge** (`lock_for_booking()`): erst die Auftragszeilen aller betroffenen Rechnungen aufsteigend nach ID
(`lock_order_invoices()`, dieselbe Sperre wie Festschreiben, Storno und Mahnung), dann die Zahlungszeile(n) aufsteigend
(`SELECT … FOR UPDATE`). Die Zahlungssperre braucht es für den Rest einer Zahlung: zwei Zuordnungen aus demselben Rest auf Rechnungen
verschiedener Aufträge sperren verschiedene Aufträge und würden sonst beide den ganzen Rest sehen. "Zahlung zurücknehmen" liest die
Aufträge vor der Sperre; kam bis dahin eine Zuordnung auf einen weiteren Auftrag dazu, wird neu gesperrt (bis zu dreimal), damit die
Reihenfolge bleibt.

**Storno** (Vorgabe Nr. 5): `storno_block_reason()` lehnt ab, solange der Rechnung Zahlung, Skonto oder Einbehalt zugeordnet ist
(`allocation_block_reason()`) -- beim Anlegen und beim Festschreiben des Stornos unter der Sperre, die Rechnungsseite zeigt den Grund
statt "Stornieren". Nach den Gegenbuchungen ist der Storno frei; die Zahlung bleibt als Rest am Kunden. Ein Storno-Entwurf von vor einer
Buchung lässt sich danach nicht festschreiben.

**Finanzen und Dashboard** (Vorgabe Nr. 6): `invoice_overview_rows()` liefert den Zahlstand aller Rechnungen in zwei Abfragen.
Finanzen: "Offene Rechnungen"/"Offener Betrag" aus dem offenen Betrag, "davon Einbehalt", "Bezahlt (gesamt)" = Summe der zugeordneten
Zahlungen, "Nicht zugeordnet" und eine Karte "Nicht zugeordnete Zahlungen" (`GET /api/payments/unallocated`, Link in die
Kundenakte); Filter Entwurf / Offen / Einbehalt offen / Bezahlt / Storniert-Storno; Spalte "Offen". Dashboard: offene Rechnungen und
offener Betrag ebenso. Überfällig (`is_overdue`) nur mit mahnfähigem Betrag. Auftragsseite und Projektmappe zeigen den Zahlstand.

**Mahnwesen, nur was Punkt 3 verlangt**: gemahnt wird der mahnfähige Betrag statt des Bruttos (`create_reminder()`, Liste
`list_invoices_needing_attention()` nur mit mahnfähigem Betrag); ohne mahnfähigen Betrag keine nächste Stufe und keine Mahnung
(`send_block_reason()` -> `dunning_block_reason()`: "ist bezahlt (am …)", "nur noch der Einbehalt offen … wird nicht gemahnt",
Stornorechnung); ein Entwurf, dessen Betrag seit dem Anlegen nicht mehr stimmt, wird nicht festgeschrieben (`stale_amount_reason()`,
409, Grund statt "Versenden").

**Oberfläche**: Rechnungsseite mit Karte "Zahlungen" (Brutto, Zahlungen, Skonto, offen, davon Einbehalt, mahnfähig, Zahlstand,
Zuordnungen mit "Gegenbuchen" und Begründungsfeld) und Dialog "Zahlungseingang buchen" (neuer Eingang oder Rest einer vorhandenen
Zahlung, Vorschlag, Beträge je Zeile änderbar, weitere Rechnung von Hand, Summen mit Rest, Warnung und gesperrtes Bestätigen bei
Überbuchung). Kundenakte mit Karte "Zahlungen" (Rest, Rest zuordnen, Zahlung zurücknehmen). Keine Popups für Eingaben (Regel 4);
abgelehnte Antworten über `fehlerText()`.

**Migration `c7d41e9a2b63`** (Vorgabe Nr. 7): je Rechnung mit Status "bezahlt" eine Zahlung über das Brutto zum bezahlt-Datum, Herkunft
`uebernommen`, Notiz "Übernommen aus dem Status „bezahlt“ (bis 1.8.77)", ganz ihr zugeordnet; die Rechnung steht danach auf
"versendet". Das Brutto rechnet die Migration selbst (Kopie von `compute_invoice_totals()` zum Stand 1.8.78, ein Test hält beide
gleich). `downgrade()` stellt "bezahlt" exakt wieder her und entfernt die Tabellen; verweigert, sobald etwas gebucht ist, das der
Rückweg verlöre (erfasste Zahlung, Gegenbuchung, weitere Zuordnung).

### Festlegungen 1.8.78 – Bitte bestätigen

1. **Status nur noch Dokument-Lebenslauf**: `Invoice.status` = Entwurf / versendet / storniert; "bezahlt" wird nicht mehr gespeichert.
   `paid_date` bleibt als Spalte stehen und wird nicht mehr geschrieben (Nachweis, Rückweg der Migration).
2. **Gebucht wird gegen das Brutto auf den Cent** nach der Rundungsregel der Rechnung; alle Beträge einer Zahlung auf den Cent.
3. **Der Einbehalt deckt höchstens den offenen Betrag**: "Einbehalt offen" = der kleinere von Einbehalt und offen, mahnfähig = offen
   minus diesen Teil. Zahlt der Kunde den Einbehalt später, wird das als Zahlung gebucht und der Einbehalt ist erledigt, ohne
   Gegenbuchung. (Wörtlich "offen − Einbehalt" würde danach negativ.)
4. **Abzüge gehören zu einer Zahlung**: Skonto und Einbehalt werden mit einem Zahlungseingang gebucht (nicht allein) und mit "Zahlung
   zurücknehmen" ebenfalls gegengebucht.
5. **Skonto von Hand auch ohne Frist**: vorgeschlagen wird es nur in der Frist und bei passendem Betrag; von Hand lässt es sich immer
   eintragen (bis zum offenen Betrag), der Dialog zeigt dann "außerhalb der Frist".
6. **Rechnung eines anderen Kunden: 409 mit Grund** ("gehört zu einem anderen Kunden als die Zahlung"), keine Bestätigung als
   Ausweg -- nur Büro-Rollen sehen Rechnungen, ein verdecktes 404 schützte nichts. Kunde der Rechnung = Kunde ihres Projekts.
7. **Eingangsdatum nicht in der Zukunft**; vor dem Rechnungsdatum erlaubt.
8. **Keine Überzahlung einer Rechnung**: was über die Rechnungen hinausgeht, bleibt als Rest am Kunden.
9. **Gegenbuchung je Eintrag ganz**: ein falscher Betrag wird gegengebucht und neu gebucht, keine Teilkorrektur.
10. **Sperrreihenfolge**: Auftragszeilen aufsteigend nach ID, dann Zahlungszeilen aufsteigend; die Zahlung zusätzlich, weil sonst
    zwei Zuordnungen aus demselben Rest gleichzeitig durchgingen.
11. **Migration**: eine Stornorechnung mit "bezahlt" bekommt keine Zahlung (nie offen) und steht danach auf "versendet"; eine
    stornierte Rechnung mit bezahlt-Datum bleibt unverändert (keine Zahlung, kein Rest am Kunden -- ob das Geld zurückging oder auf die
    neue Rechnung kam, steht nirgends); ohne bezahlt-Datum zählt das Rechnungsdatum; eine Rechnung über 0 € oder weniger bekommt keine
    Zahlung. Der Rückweg verweigert, sobald etwas erfasst ist.
12. **Mahnwesen nur so weit**: mahnfähiger Betrag beim Anlegen, keine Mahnung ohne mahnfähigen Betrag, kein Festschreiben eines
    Entwurfs mit veraltetem Betrag (409 mit altem und neuem Betrag, Ausweg: löschen und neu anlegen). Eine schon festgeschriebene Mahnung
    bleibt, wie sie ist (siehe Nebenbefunde).
13. **Überfällig** heißt: mahnfähiger Betrag und Fälligkeit vor heute -- ein offener Einbehalt ist nicht überfällig.
14. **Rollen**: Zahlungen buchen, zuordnen und gegenbuchen ab `buero_auftrag`, wie die Rechnungen; der Monteur nirgends (403).
15. **Finanzen "Bezahlt (gesamt)"** = Summe der zugeordneten Zahlungen (ohne Skonto, ohne nicht zugeordneten Rest); der Rest steht
    eigens als "Nicht zugeordnet".

### Tests und Prüfung

- Neu `tests/test_v381_zahlungen.py` (30): Beträge und Zustand (offen -> teilweise -> bezahlt am Eingangsdatum, Skonto, Einbehalt offen
  und später gezahlt, Einbehalt über dem danach offenen Betrag, kein Zustand bei Entwurf/Storno/storniert, Altbestand vor 1.8.11 auf den
  Cent); Vorschlag (ältere desselben Auftrags zuerst, neuere und andere Aufträge nicht, Rest; Skonto nur in der Frist und bei passendem
  Betrag, auch für zwei Rechnungen zusammen; Storno und Entwurf abgelehnt); **Angriffe**: Überbuchung der Rechnung (auch über Skonto)
  und der Zahlung, Rechnung eines fremden Kunden (auch beim Rest), Buchung auf Storno, stornierte Rechnung und Entwurf -- je abgelehnt,
  nichts geschrieben; Eingabefehler; Rest am Kunden; ORM-Sperre (Ändern, Löschen), Gegenbuchung mit Begründung einmal, Zahlung
  zurücknehmen samt Abzügen, kein `update()`/`delete()` (AST), Historie; Storno erst nach gelösten Zuordnungen, Storno-Entwurf von vor
  der Buchung; Finanzen-Zeilen, überfällig nur mit mahnfähigem Betrag; Mahnung über den mahnfähigen Betrag, keine bei bezahlt, Einbehalt
  oder Storno, Entwurf mit veraltetem Betrag 409.
- Neu `tests/test_v381_zahlungen_pg.py` (12, davon 5 gegen PostgreSQL): gleichzeitig zwei Buchungen auf dieselbe Rechnung (die zweite
  wartet und wäre Überbuchung, ihre Zahlung nicht angelegt), zwei Zuordnungen aus demselben Rest auf Rechnungen verschiedener Aufträge
  (die zweite wartet an der Zahlung), Buchung gegen Storno und Storno gegen Buchung, dieselbe Gegenbuchung zweimal; Rundgang mit
  Beobachter über jeden schreibenden Endpunkt (Zuordnung nur unter der Sperre ihres Auftrags und, bei einer vorhandenen Zahlung, deren
  Sperre; Aufträge aufsteigend, danach die Zahlung -- mit Zeilen in absteigender Auftragsreihenfolge); Router 404/409/422, "erfasst von"
  aus der Anmeldung (mitgeschickt wirkungslos), Monteurin 403.
- Neu `tests/test_v381_zahlungen_migration.py` (3, davon 1 gegen PostgreSQL): Brutto der Migration = Brutto der App (ab 1.8.11 und
  Altbestand, Pauschale, Storno); Probe auf einem Bestand (bezahlt mit Datum, Altbestand ungerundet bei einem anderen Kunden, bezahlt ohne
  Datum, offen, storniert mit Datum, Storno mit "bezahlt"): hoch -> Zahlungen und Zustand wie festgelegt; runter -> Status und
  bezahlt-Datum exakt wie vorher, Tabellen weg; wieder hoch, eine Zahlung erfasst -> Rückweg verweigert, nichts geändert.
- Angepasst, nur wo "bezahlt" als Status oder die Route entfiel: `test_v133` (`test_mark_paid_nur_ab_versendet` ->
  `test_bezahlt_nur_ab_versendet`), `test_v141`, `test_v372`, `test_v375` (Text "Nur festgeschriebene Rechnungen" statt "Nur versendete
  oder bezahlte"), `test_v378` (Route `mark-paid` aus dem Rundgang, `mark_invoice_paid` aus der Liste der Schreiber); Hilfe
  `tests/zahlung.py::voll_bezahlen()` statt `mark_invoice_paid()`. Ergänzt: `test_v326` (Query-Werte des Vorschlags), `test_v364`
  (Spalten `kind`/`origin`), `test_v373` (Einordnung der neuen IDs), `test_v380` (Probe bis zur eigenen Revision statt "head").
- Gegenproben (Regel 24): 14 von 14 rot -- Überbuchung der Rechnung (2 Tests) und der Zahlung (2), fremder Kunde (2, darunter der
  Strukturtest Regel 25), Buchung auf Storno (2), Sperre der Auftragszeilen (PostgreSQL, 7), Sperre der Zahlung (4), feste Reihenfolge (3),
  Storno nur ohne Zuordnungen (3), ORM-Sperre (1), Gegenbuchung nur einmal (2), Mahnung über den mahnfähigen Betrag (1), Einbehalt nicht
  gemahnt (1), Migration setzt auf "versendet" (1), Rückweg verweigert (1). Jede Datei byte-genau zurück (SHA-256), kein Marker unter
  `app/` und `alembic/`.
- Migration `c7d41e9a2b63` auf einer Wegwerf-SQLite: hoch, `current` head, `check` ohne Unterschied, runter, wieder hoch; dazu die Proben
  der Migrationstests gegen SQLite und PostgreSQL.
- Klicktests: neu `klicktest_zahlungen.py` 40/40. `klicktest_rechnungen_sperren.py` erwartete "Bezahlt-Knopf bleibt" -- seit 1.8.78
  veraltet (der Knopf entfällt), jetzt "kein Bezahlt-Knopf mehr"; die bezahlte Rechnung dort entsteht über eine gebuchte Zahlung.
- **Alle Klicktests** (`scripts/klicktest_alle.py`, Arbeitskopie mit dem Endstand, Regel 26): 47 von 47 wie erwartet, 9:54 min. Ein
  erster Lauf vor zwei Korrekturen ergab ebenfalls 47 von 47.
- Volle Suite (mit den opt-in-Tests gegen PostgreSQL, Arbeitskopie, Endstand): 3481 grün, 0 rot, 7 erwartet fehlgeschlagen (1a, 1b, 1d).
  Der erste Lauf hatte 3 rot: `test_v334` (der Node-Lauf der Rechnungsseite kannte `debounce` aus `_debounce.html` nicht -- jetzt ein
  eigener Zeitgeber) und zwei in `test_v380` (die Migrationsprobe fuhr bis "head", das ist jetzt `c7d41e9a2b63`); beide behoben, danach
  der zweite Lauf. Danach nur Doku geändert.

### Nebenbefunde (nur gemeldet)

1. **Kundenwechsel am Projekt nach festgeschriebenen Rechnungen**: `check_client_change()` sperrt nur bei festgeschriebenem Vertrag
   oder einem Beteiligten. Wechselt der Kunde danach, gehören die Rechnungen des Projekts zum neuen Kunden (Kunde der Rechnung = Kunde
   des Projekts), ihre schon gebuchten Zahlungen bleiben am alten; neue Buchungen gingen nur noch mit Zahlungen des neuen. Naheliegend:
   Kundenwechsel sperren, sobald eine Rechnung festgeschrieben ist.
2. **Festgeschriebene Mahnung nach einer Teilzahlung**: `send_reminder_email()` sperrt nur ohne mahnfähigen Betrag (bezahlt, nur
   Einbehalt, Storno); nach einer Teilzahlung geht eine schon festgeschriebene Mahnung weiter mit dem alten Betrag per E-Mail hinaus.
   Gehört zu Z2.
3. **Zustellung einer Mahnung auf anderem Weg** (Nebenbefund 5 aus 1.8.77) prüft weiter nichts -- auch nicht "bezahlt" oder
   "Einbehalt offen".
4. **Rechnung über 0 € oder weniger** (keine Stornorechnung, z. B. eine Schlussrechnung nach zu hohen Abschlägen): nie offen und nicht
   bebuchbar; eine Gutschrift oder Auszahlung an den Kunden ist nicht abgebildet.
5. **Zahlungshinweis der Schlussrechnung** (Entscheidung "Einbehalt") und ein Zahlstand auf dem PDF gibt es nicht; das Rechnungs-PDF
   bleibt, wie es beim Festschreiben war.
6. **Finanzen lädt alle Rechnungen** ohne Begrenzung, je Rechnung mit ihren Positionen (Brutto). Der Zahlstand kommt mit zwei
   Abfragen für alle dazu, nicht je Rechnung; die Last der Positionen bestand vorher.
7. Unverändert aus 1.8.77: Rechnung per E-Mail auch bezahlt oder storniert (Nr. 7), Dashboard ohne "Mahnung"-Zeilen bei gewähltem
   Mitarbeiter (Nr. 6), Probebelege entfernen (Nr. 8).
