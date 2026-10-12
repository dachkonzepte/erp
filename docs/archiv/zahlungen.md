# Zahlungen (Zahlungsstufe Z1 seit 1.8.78, Mahnwesen Z2a seit 1.8.79)

Grundlage: Befund Zahlungsstufe in `befund-vor-echtbetrieb.md` ("Umsetzung 1.8.77" -> "Befund Zahlungsstufe") und dort
"Entscheidungen Rechnungen" (Zahlung auf den Zahlbetrag, Einbehalt). Code: `app/payments.py` (Geschäftslogik),
`app/routers/payments.py` (Endpunkte), Modelle `Payment`/`PaymentAllocation` (`app/models.py`), Migration `c7d41e9a2b63`.
Das Mahnwesen (Z2a, seit 1.8.79): `app/reminders.py`, `app/routers/reminders.py`, Migration `5db1a12b4a66` -- siehe
"Umsetzung 1.8.79"; ältere Herleitung des Mahnwesens in `mahnwesen.md`. Mahngebühren und Verzugszinsen (Z2b): Befund in
"Umsetzung 1.8.79".

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

### Festlegungen 1.8.78 (Nr. 3, 4, 5, 6, 11, 12 bestätigt am 12.10.2026; die übrigen in "Umsetzung 1.8.79" je in einer Zeile vorgelegt)

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

## Umsetzung 1.8.79: Mahnwesen Z2a, die Rechnung hält ihren Kunden fest; Befund Z2b

### Vorgabe vom 12.10.2026 (übernommen wie gegeben)

Z1 (1.8.78) geprüft. Festlegungen 3, 4, 5, 6, 11, 12 bestätigt. Die übrigen (1, 2, 7–10, 13–15) bitte je in einer Zeile vorlegen.

Vorweg (Nebenbefund 1 aus 1.8.78):
- Eine Rechnung hält ab dem Festschreiben ihren Kunden fest.
- Kundenwechsel am Projekt gesperrt (409 mit Grund), sobald eine Rechnung festgeschrieben oder eine Zahlung gebucht ist. Ausweg:
  stornieren, neu anlegen.

Z2a Mahnwesen (zahlungen.md fortschreiben):
1. Keine Mahnungsentwürfe mehr beim Öffnen des Mahnwesens. Stattdessen eine Liste „zur Mahnung fällig“, nur lesend; Entwürfe
   entstehen per Klick, einzeln oder für mehrere.
2. Prüfungen beim Anlegen und Festschreiben, unter der Sperre: keine Mahnung zu einem Storno, zu einer nicht fälligen oder nicht
   mahnfähigen Rechnung; nur die nächste Stufe; die nächste Stufe frühestens nach Ablauf der Frist der vorigen. Je Stufe eine Zahl:
   die Zahlungsfrist.
3. Mahnungsentwurf bearbeiten und löschen unter derselben Sperre. Mahndatum = Tag des Festschreibens (Berliner Zeit), Frist ab dann.
4. Die Mahnung zeigt Brutto, gezahlte Beträge, Skonto, Einbehalt und den mahnfähigen Betrag.
5. Versand und Zustellung einer festgeschriebenen Mahnung nur, solange ihr Betrag noch dem mahnfähigen entspricht und die Rechnung
   nicht storniert ist; sonst 409 mit Hinweis auf eine neue Mahnung.
6. Dashboard: Mahnungen auch bei gewähltem Mitarbeiter (Nebenbefund 6 aus 1.8.77).

Befund für Z2b (Mahngebühren und Verzugszinsen als zuschaltbare Funktion), nur lesen, mit Fundstellen:
a) Welche Gebühren-Einstellungen gibt es heute je Stufe, und wo wirken sie?
b) Welche Zugangsdaten von Rechnung und Mahnung hält das ERP fest (Versand, nachgetragene Zustellung)?
c) Wie ließen sich Nebenforderungen (Gebühren, Zinsen) je Rechnung abbilden, ohne den Rechnungsbetrag zu ändern?

Angriffstests mit Gegenprobe, Gleichzeitigkeit gegen PostgreSQL. Eigene Festlegungen mit „Bitte bestätigen“. Nebenbefunde nur
melden. Wird der Umfang zu groß: nach Punkt 3 committen und den Rest auflisten. Commit nach Regel 13, Bericht kurz.

### Vorweg

- Festlegungen 1.8.78 Nr. 3, 4, 5, 6, 11, 12 an der Überschrift als bestätigt markiert. Die übrigen, je in einer Zeile:
  1. `Invoice.status` nur Entwurf / versendet / storniert; „bezahlt“ wird nicht mehr gespeichert, `paid_date` bleibt ungeschrieben
     stehen.
  2. Gebucht wird gegen das Brutto auf den Cent nach der Rundungsregel der Rechnung, jeder Betrag einer Zahlung auf den Cent.
  7. Eingangsdatum nicht in der Zukunft; vor dem Rechnungsdatum erlaubt.
  8. Keine Überzahlung einer Rechnung: was darüber hinausgeht, bleibt Rest am Kunden.
  9. Gegenbuchung je Eintrag nur ganz; ein falscher Betrag wird gegengebucht und neu gebucht.
  10. Sperrreihenfolge: Auftragszeilen aufsteigend, dann Zahlungszeilen aufsteigend.
  13. Überfällig = mahnfähiger Betrag und Fälligkeit vor heute; ein offener Einbehalt ist nicht überfällig.
  14. Zahlungen buchen, zuordnen und gegenbuchen ab `buero_auftrag`; der Monteur nirgends (403).
  15. Finanzen „Bezahlt (gesamt)“ = Summe der zugeordneten Zahlungen ohne Skonto und Rest; der Rest steht eigens als „Nicht
      zugeordnet“.
- Der Umfang blieb in einer Version: Vorweg und alle sechs Punkte gebaut, Befund Z2b geschrieben, ein Commit.

### Was gebaut ist

**Vorweg: die Rechnung hält ihren Kunden fest** (Migration `5db1a12b4a66`):
- `Invoice.customer_id` (FK `customers`, Index): beim Festschreiben gesetzt (`app/invoices.py::_customer_at_finalize()`, frisch nach
  der Sperre der Auftragszeile gelesen) -- der Kunde des Projekts, beim Storno der Kunde der stornierten Rechnung; im Entwurf leer.
  `invoice_customer()`/`invoice_customer_id()` (jetzt in `app/invoices.py`, in `app/payments.py` weiter importierbar): festgeschrieben
  der festgehaltene, im Entwurf der des Projekts. Zahlungen buchen nur auf Rechnungen dieses Kunden, „offene Rechnungen des Kunden“
  (`open_invoices_of_customer()`) nach ihm, die Empfängeradresse von Rechnung und Mahnung ist seine, `invoice_to_dict()["customer_id"]`
  (Rechnungsseite, Zahlungsdialog) ebenso.
- **Kundenwechsel** (`app/project_participants.py::check_client_change()`, `PUT /api/projects/{id}`): sperrt alle Auftragszeilen des
  Projekts (aufsteigend, dieselbe Sperre wie das Festschreiben) und lehnt ab (409, `ClientChangeConflict`), sobald am Projekt eine
  Rechnung festgeschrieben ist -- auch storniert oder ein Storno; Entwürfe zählen nicht. Grund: „Am Projekt ist die Rechnung … fest-
  geschrieben -- sie gehören zum Kunden …. Der Kunde lässt sich im Projekt nicht mehr wechseln. Ausweg: die Rechnungen stornieren
  und für den richtigen Kunden in einem eigenen Projekt neu anlegen.“ Eine gebuchte Zahlung hängt immer an einer festgeschriebenen
  Rechnung, ist also mit gesperrt. Gleichzeitig: ein Festschreiben wartet auf den Wechsel und hält danach den neuen Kunden, ein
  Wechsel wartet auf das Festschreiben und lehnt ab.
- Migration: jede nicht als Entwurf geführte Rechnung bekommt den Kunden ihres Projekts (bis 1.8.78 galt genau der als Kunde der
  Rechnung); Rückweg entfernt die Spalten, verweigert, solange eine festgeschriebene Mahnung eine Aufstellung trägt.

**Nr. 1 -- keine Entwürfe von selbst**: `auto_create_due_reminder_drafts()`, `POST /api/reminders/auto-create`, `GET/PUT
/api/reminder-settings` und der Schalter in Einstellungen → Mahnstufen entfallen (`GeneralSettings.reminders_auto_create_drafts` bleibt
ungenutzt stehen). `list_invoices_needing_attention()` (`GET /api/reminders/overdue`) liest nur: überfällige Rechnungen mit
mahnfähigem Betrag, je mit Stufe, `next_due_on`, `is_due_now` und `create_block` (warum jetzt kein Entwurf entsteht); „zur Mahnung
fällig“ = `is_due_now` und kein Grund, diese zuerst. Mahnwesen-Seite: Karte „Zur Mahnung fällig“ mit Auswahl je Zeile und „alle“,
Knopf je Zeile und „Entwürfe für Auswahl anlegen (n)“ (`POST /api/reminders/bulk`, `create_reminders()`: je Rechnung einzeln unter ihrer
Sperre, eine abgelehnte hält die anderen nicht auf, Antwort mit angelegten und abgelehnten samt Grund); Karte „Weitere überfällige
Rechnungen“ mit offenem Entwurf oder Grund; Kennzahlen „Zur Mahnung fällig“, „Entwürfe offen“, „Überfällig gesamt“, „Festgeschrieben“.

**Nr. 2 -- Prüfungen** (`create_block_reason()`, beim Anlegen und noch einmal beim Festschreiben unter der Sperre der Auftragszeile,
`InvoiceBlocked` = 409, nichts geschrieben), in dieser Reihenfolge: nichts zu mahnen (Entwurf, storniert, Stornorechnung, bezahlt, nur
Einbehalt, 0 €); keine Fälligkeit oder nicht fällig (Stufe 1 ab dem Tag nach der Fälligkeit); schon ein Entwurf (nur beim Anlegen);
keine weitere aktive Stufe; nicht die nächste Stufe (verlangt beim Anlegen bzw. die Stufe des Entwurfs: „überholt … bitte löschen“);
die nächste erst ab dem Tag nach dem Ende der Frist der vorigen (`deadline_of()`: ihre neue Frist, bei Altbestand ohne Frist Mahndatum
+ Tage der Stufe). **Je Stufe eine Zahl**: `ReminderLevel.days_after_previous_step` ist jetzt die Zahlungsfrist in Tagen ab dem
Mahndatum (Spaltenname von früher; Einstellungen: „Zahlungsfrist (Tage ab Mahndatum)“). `POST /api/invoices/{id}/reminders` nimmt die
Stufe nur noch zur Kontrolle (leer = die nächste). Rechnungsseite: Grund statt „… anlegen“.

**Nr. 3 -- Bearbeiten und Löschen unter der Sperre; Mahndatum = Festschreiben**: `update_reminder_draft()` sperrt die Auftragszeile,
lädt frisch und ändert nur, was noch Entwurf ist (sonst 409, vorher 400 ohne Sperre); `delete_reminder_draft()` tat das seit 1.8.73.
Die Frist ist im Entwurf eine Länge in Tagen (`payment_days`, 1–365; `PUT /api/reminders/{id}` verlangt `text`, `fee_amount`,
`payment_days` -- Regel 22, aus der Liste der Altfälle gestrichen). Festschreiben: Mahndatum = heute (Berlin), Frist = heute + Tage
(`finalize_dates()`). Ein Entwurf zeigt in Liste, Text (`{neue_frist}`) und PDF die Daten des Festschreibens heute
(`effective_dates()`), der Editor einen Hinweis dazu.

**Nr. 4 -- Aufstellung**: `Reminder.amounts_json` (kanonisches JSON: Brutto, je noch geltender Zahlung Eingangsdatum und Betrag,
Skonto, Einbehalt = der abgezogene Teil, mahnfähig), beim Anlegen und beim Festschreiben unter der Sperre aus dem Zahlstand
geschrieben (`amounts_snapshot()`), danach fest. PDF: „Rechnungsbetrag (brutto)“, „abzüglich Zahlung vom …“ je Zahlung, „abzüglich
Skonto“ und „abzüglich Einbehalt (wird nicht angemahnt)“ nur, wenn gebucht, „Angemahnter Betrag“, Mahngebühr, Gesamtbetrag
(`app/reminder_pdf.py::amount_rows()`); Rechnungsseite eine Zeile je Mahnung. Mahnungen von vor 1.8.79 ohne Aufstellung: wie bisher
„Offener Rechnungsbetrag“.

**Nr. 5 -- Versand und Zustellung** (`dispatch_block_reason()`): eine festgeschriebene Mahnung geht nicht mehr hinaus, wenn die
Rechnung storniert ist oder ihr Betrag nicht mehr dem mahnfähigen entspricht -- 409 „Die Mahnung … lautet über …, mahnfähig sind
inzwischen … -- sie geht nicht mehr hinaus. Bitte eine neue Mahnung anlegen -- die 2. Mahnung ist ab dem … möglich.“ E-Mail
(`send_reminder_email()`) prüft den Stand heute, ohne Sperre (wie seit 1.8.72: sonst hielte der Versand sie über die Verbindung zum
Mailserver). Zustellung nachtragen (`record_manual_delivery()` → `DispatchDocument.before_delivery` → `check_delivery()`) prüft unter
der Sperre der Auftragszeile den Stand am Zustelltag (`payment_state_on()`: Zahlungen mit Eingangsdatum bis dahin, eine
zurückgenommene Buchung gilt nie); der Router antwortet 409. Mahnwesen-Seite und Rechnungsseite zeigen den Grund statt E-Mail bzw.
„Versenden“.

**Nr. 6 -- Dashboard**: `caseworker_employee_id` der Mahnungszeilen ist der Sachbearbeiter des Auftrags (die Spalte an der Rechnung
setzt niemand); bei gewähltem Mitarbeiter erscheinen seine und die ohne Sachbearbeiter.

**Oberfläche**: Mahnwesen-Seite seit 1.8.79 über `fehlerText()` (lesbare 422). Keine Popups für Eingaben (Regel 4).

### Festlegungen 1.8.79 – Bitte bestätigen

1. **Kundenwechsel dauerhaft gesperrt**, sobald am Projekt irgendeine Rechnung festgeschrieben ist -- auch nach dem Storno. „Neu
   anlegen“ heißt: ein eigenes Projekt für den richtigen Kunden. (Nach dem Storno freizugeben hätte neue Rechnungen mit dem Namen aus
   dem Auftrag, also dem alten Kunden, erzeugt -- siehe Nebenbefund 1.)
2. **Kunde der Rechnung**: beim Storno der der stornierten Rechnung; Altbestand (Migration) der Kunde des Projekts am Tag der Migration.
3. **Empfänger** von Rechnung und Mahnung: die Adresse von heute des festgehaltenen Kunden (nicht des Projekts).
4. **Stufe 1 ab dem Tag nach der Fälligkeit**, ohne Wartezeit; jede weitere ab dem Tag nach dem Fristende der vorigen (die Frist schließt
   ihren letzten Tag ein). Die eine Zahl je Stufe ist die Zahlungsfrist; die Spalte behält ihren alten Namen.
5. **Höchstens ein Entwurf je Rechnung** (beim Anlegen). Beim Festschreiben zählt ein zweiter (Altbestand) nicht -- er ist danach
   „überholt“ und nur noch löschbar.
6. **Eine festgeschriebene Mahnung zählt als erreichte Stufe**, auch wenn sie nach einer Teilzahlung nicht mehr hinausgeht oder nie
   hinausging; die neue Mahnung ist die nächste Stufe nach Ablauf der Frist. (Alternative, nicht gebaut: Ersatz derselben Stufe, wenn
   die überholte nie versendet oder zugestellt wurde.)
7. **Frist im Entwurf in Tagen** (1–365), nicht mehr als Datum; leeren lässt sie sich nicht mehr.
8. **Automatik ganz entfernt** (Funktion, Endpunkte, Schalter); die Spalte `reminders_auto_create_drafts` bleibt ungenutzt stehen.
9. **Entwürfe für mehrere**: je Rechnung einzeln, Antwort 200 mit angelegten und abgelehnten (Grund); höchstens 200 Rechnungen je Aufruf.
10. **Aufstellung**: eingefroren an der Mahnung (beim Anlegen, frisch beim Festschreiben), Zahlungen je Eingang mit Datum, Skonto und
    Einbehalt nur, wenn gebucht; im PDF „Angemahnter Betrag“ statt „mahnfähig“.
11. **Zustellung nachtragen prüft den Stand am Zustelltag** (eine danach eingegangene Zahlung verhindert den Nachtrag nicht -- die
    Zustellung war richtig und ist für Z2b ein Zugangsnachweis); E-Mail den Stand heute; „storniert“ sperrt beides immer.
12. **Dashboard**: Sachbearbeiter des Auftrags; Mahnungen ohne Sachbearbeiter für jeden gewählten Mitarbeiter.

### Befund Z2b: Mahngebühren und Verzugszinsen (nur gelesen; Zeilen nach dem Stand 1.8.79)

Zur Einordnung, keine Rechtsberatung: Verzug setzt Fälligkeit und Mahnung voraus oder tritt ohne Mahnung ein (kalendermäßig bestimmte
Zeit, § 286 Abs. 2 Nr. 1 BGB; 30 Tage nach Fälligkeit und Zugang der Rechnung, bei Verbrauchern nur mit Hinweis darauf, Abs. 3).
Verzugszinsen 5 Prozentpunkte über dem Basiszinssatz, ohne Verbraucher 9 (§ 288 Abs. 1/2), dazu ohne Verbraucher 40 € Pauschale
(Abs. 5). Mahngebühren sind Verzugsschaden -- die verzugsbegründende erste Mahnung selbst gehört nach verbreiteter Ansicht nicht
dazu. Für Z2b heißt das: Zugang und Verbraucher-Eigenschaft müssen nachweisbar im ERP stehen.

**a) Gebühren-Einstellungen je Stufe und wo sie wirken**
- **Einstellung**: `ReminderLevel.fee_amount` (`app/models.py:1827`, `Numeric(18, 6)`), Vorgabe 5 / 10 / 15 € für Stufe 1 / 2 / 3
  (`app/reminders.py:75` ff., `DEFAULT_REMINDER_LEVELS`), bearbeitbar unter Einstellungen → Mahnstufen (`settings.html:1800`, `PUT
  /api/reminder-levels/{id}`, `ReminderLevelUpdate` mit `fee_amount >= 0`, `app/schemas.py:1771`). Laut Docstring bewusst ohne
  Steuersatz („umsatzsteuerfrei, Schadensersatz“, `app/models.py:1814`). Kein Schalter: jede Stufe hat immer eine Gebühr (auch 0 €),
  auch die erste.
- **Wirkung**: beim Anlegen als Kopie an der Mahnung (`Reminder.fee_amount`, `app/models.py:1874`; `create_reminder()`,
  `app/reminders.py:495`), im Entwurf änderbar (`update_reminder_draft()`, `:660`). Gesamtbetrag = mahnfähiger Betrag + Gebühr
  (`reminder_total()`, `:62`); Platzhalter `{mahngebuehr}` und `{gesamtbetrag}` in Mahntext und E-Mail (`_reminder_placeholders()`,
  `:336`), die Standardtexte aller drei Stufen fordern „zuzüglich einer Mahngebühr“; PDF-Zeilen „Mahngebühr“ und „Gesamtbetrag“
  (`app/reminder_pdf.py:109`).
- **Wo sie nicht wirkt**: nirgends als Forderung. Der Zahlstand kennt nur Brutto, Zahlungen, Skonto, Einbehalt (`app/payments.py:157`,
  `_state()`); eine Zahlung über Rechnung + Gebühr wäre an der Rechnung eine Überbuchung -- der Gebührenanteil bliebe Rest am Kunden.
  Finanzen, Dashboard, Kundenakte und Mahnwesen-Liste zeigen keine Gebühren; die nächste Mahnung nimmt die Gebühr der vorigen nicht mit
  (jede Stufe nur ihre eigene). Keine Verzugszinsen, kein Basiszinssatz, keine Pauschale -- im Code nirgends.

**b) Zugangsdaten von Rechnung und Mahnung**
- **Am Dokument**: `Invoice.email_sent_at/_to` (`app/models.py:1738`), `Reminder.email_sent_at/_to` (`:1888`) -- nur der letzte
  E-Mail-Versand (`mark_document_sent()`, `app/email_dispatch.py:362`), überschrieben bei jedem neuen. Daten des Dokuments selbst:
  Rechnungsdatum = Tag des Festschreibens, Fälligkeit (`Invoice.due_date`, im PDF „Zahlbar rein netto bis zum …“,
  `format_payment_terms_sentence()`, `app/invoices.py:980`), Mahndatum und Frist (`Reminder.reminder_date/new_due_date`).
- **Versandprotokoll** (`EmailDispatch`, `app/models.py:5410`), je Versand eine Zeile, unveränderlich, mit Dokumentart und -ID:
  E-Mail mit `finished_at` (Übergabe an SMTP bzw. Microsoft 365 -- nicht der Zugang), Empfänger, PDF in der Ablage; **nachgetragene
  Zustellung** (Einschreiben, persönlich, Bote, Fax; `record_manual_delivery()`, `app/email_dispatch.py:503`) mit `delivered_on`
  (`:5452`, „Datum der Zustellung“), Notiz, optional Beleg und `delivered_to_client` (`:5458`).
- **Versandergebnis** (`DispatchOutcome`, `app/models.py:5579`; `record_dispatch_outcome()`, `app/email_dispatch.py:674`): je Eintrag
  höchstens einmal „Empfang bestätigt am“ (`outcome_on`, optional Beleg, z. B. Rückschein) oder „unzustellbar“. Das ist der einzige
  ausdrückliche Zugangsnachweis.
- **Was fehlt**: eine Auswertung „zugegangen am“ je Dokument gibt es nur für die Briefe der Anzeigen (`reached_client()`,
  `app/notice_letters.py:392`: gesendet, nicht unzustellbar, an den Auftraggeber) -- für Rechnung und Mahnung nicht. Ob der
  Verbraucher-Hinweis nach § 286 Abs. 3 auf der Rechnung steht, hält nichts fest (nur, ob der Kunde Verbraucher ist:
  `Customer.is_consumer`, `app/models.py:268`). Der Basiszinssatz ist nirgends hinterlegt.

**c) Nebenforderungen je Rechnung, ohne den Rechnungsbetrag zu ändern** (Vorschlag, nichts gebaut)
- **Eigene Tabelle „Nebenforderung“** je Rechnung (nicht an `Invoice`, nicht in `compute_invoice_totals()`): Art (`mahngebuehr`,
  `verzugszinsen`, `pauschale`), Betrag, Grundlage (Mahnung, bzw. Hauptbetrag, Zinssatz, von–bis), angelegt von/am. Unveränderlich wie
  Zahlungen (ORM-Sperre), Korrektur und Erlass nur als Gegenbuchung mit Begründung. Die Rechnung, ihr Zahlstand (`payment_state()`) und
  das Rechnungs-PDF bleiben unverändert; „offen“ der Nebenforderungen ist eine eigene, abgeleitete Summe.
- **Mahngebühr**: entsteht beim Festschreiben der Mahnung (dieselbe Transaktion, je Mahnung höchstens eine, UNIQUE), nicht im Entwurf;
  der Betrag aus `Reminder.fee_amount`. Schalter „Mahngebühren berechnen“ (aus = keine Zeile, Gebühr 0 und nicht im Text).
- **Verzugszinsen**: nur berechnet, nicht laufend gespeichert -- festgehalten erst als Zeile, wenn eine Mahnung oder Forderungsaufstellung
  sie nennt (Stand an deren Tag). Brauchen: Verzugsbeginn (Zugang der ersten Mahnung aus b, oder die Fälligkeit, wenn sie als
  kalendermäßig bestimmt gelten soll -- Rechtsfrage), Basiszinssatz je Halbjahr (Tabelle mit Gültigkeit, von Hand gepflegt),
  Zuschlag 5 bzw. 9 Prozentpunkte nach `is_consumer`, Hauptbetrag je Tag (mahnfähiger Betrag; Zahlungen mit Eingangsdatum mindern ab
  dann -- `payment_state_on()` gibt es seit 1.8.79). Pauschale 40 € nur ohne Verbraucher, einmal je Rechnung.
- **Zahlungen darauf**: `PaymentAllocation` bekäme ein zweites Ziel (Verweis auf die Nebenforderung statt auf die Rechnung, Art
  `nebenforderung`), unter derselben Sperre der Auftragszeile. Entscheiden: die Anrechnungsreihenfolge (§ 367 BGB: Kosten, Zinsen,
  Hauptforderung -- der heutige Vorschlag bucht alles auf die Rechnung) und ob eine Teilzahlung die Mahnung damit zusätzlich „überholt“.
- **Zuschaltbar**: nicht über die Modul-Liste (`OPTIONAL_MODULES`, `app/modules.py:16`): die gilt ohne Eintrag als *an* -- ein Update
  schaltete Gebühren und Zinsen still ein. Besser ein Schalter in den Einstellungen mit Vorgabe *aus* (Grunddaten, Regel 23).
- **Mahnung**: die Aufstellung (`amounts_json`) bekäme die offenen Nebenforderungen als eigene Zeilen unter dem angemahnten Betrag;
  „Betrag stimmt noch“ (Nr. 5) vergliche dann Hauptbetrag und Nebenforderungen.

### Tests und Prüfung

- Neu `tests/test_v382_mahnwesen.py` (33): Vorweg (Rechnung hält ihren Kunden, Storno den der stornierten; Zahlung, offene Rechnungen
  und Empfänger folgen ihm; Kundenwechsel abgelehnt, auch nach dem Storno, mit nur Entwürfen erlaubt -- Funktion und Router);
  Nr. 1 (Entwürfe für mehrere mit abgelehnten samt Grund, Router, Liste liest nur); **Angriffe Nr. 2**, je nichts geschrieben:
  Stornorechnung und stornierte, heute fällig (ab morgen geht es), bezahlt und nur Einbehalt, Stufe 2 zuerst, Stufe 1 zweimal, Stufe 3
  statt 2, zweiter Entwurf, nächste Stufe am letzten Tag der Frist, Altbestand mit zwei Entwürfen bzw. einem Entwurf der 2. Stufe vor
  Fristende beim Festschreiben, deaktivierte Stufe übersprungen, Router 409 mit demselben Grund wie die Rechnungsseite; Nr. 3
  (Entwurf von vor drei Wochen: Festschreiben heute, Frist heute + 10; festgeschriebene bzw. gelöschte nicht bearbeitbar, 409; PUT ohne
  ein Feld oder mit 0 Tagen 422); Nr. 4 (Aufstellung mit zwei Zahlungen, Skonto, Einbehalt im JSON und im PDF; frisch beim
  Festschreiben; Altbestand wie bisher); **Angriffe Nr. 5** (E-Mail nach Teilzahlung abgelehnt, nichts gesendet, kein
  Protokolleintrag; Zustellung heute abgelehnt, gestern -- vor der Zahlung -- eingetragen; Zustellung zu einer stornierten Rechnung
  409); Nr. 6; **Rundgang mit Beobachter**: jeder schreibende Endpunkt des Mahnwesens schreibt Mahnungen nur unter der Sperre der
  Auftragszeile; kein `Reminder(…)` außerhalb von `app/reminders.py` (AST).
- Neu `tests/test_v382_mahnwesen_pg.py` (8, gegen PostgreSQL): zwei Entwürfe gleichzeitig (die zweite Sitzung hat die Mahnungen
  vorher geladen) und Entwurf für mehrere gegen einzeln -> einer; Bearbeiten wartet auf das Festschreiben und wird abgelehnt;
  Festschreiben wartet auf das Bearbeiten und nimmt dessen Frist; Festschreiben bzw. Zustellung warten auf eine Zahlung und lehnen den
  alten Betrag ab; Kundenwechsel wartet auf das Festschreiben einer Rechnung und lehnt ab, Festschreiben wartet auf den Wechsel und hält
  den neuen Kunden.
- Neu `tests/test_v382_mahnwesen_migration.py` (2, davon 1 gegen PostgreSQL): Bestand (versendet, zweiter Kunde, storniert, Storno,
  Entwurf, Mahnungen) -> Kunde je festgeschriebener Rechnung, Entwurf leer; Rückweg mit Aufstellung nur an einem Entwurf geht, mit einer
  an einer festgeschriebenen Mahnung verweigert, nichts geändert.
- **Angepasst, weil die Vorgabe die Erwartung überholt**: `test_v171` (die Automatik gibt es nicht mehr -- jetzt: Funktionen,
  Endpunkte, Schalter weg, Liste legt nichts an); `test_v153` (Stufe 1 ab dem Tag nach der Fälligkeit statt Fälligkeit + 7, nächste
  Stufe nach dem Fristende, vor jeder weiteren Stufe die Frist ablaufen lassen -- Hilfe `tests/mahnung.py`); `test_v236` (Frist in
  Tagen statt Datum, leeren nicht mehr möglich, festgeschrieben bearbeiten 409 statt 400); `test_v375` (kein zweiter Entwurf derselben
  Stufe mehr -- der Entwurf ist jetzt die 2. Stufe nach abgelaufener Frist); `test_v380` (Stufe 2 erst nach Ablauf der Frist);
  `test_v315` und `test_v372_befund_rechnungsdatum` (Mahnung erst nach der Fälligkeit -- dort Fälligkeit auf gestern);
  `test_v227` (die Forderungstabelle beginnt mit „Rechnungsbetrag (brutto)“). Bestand der Migrationsproben 1.8.77/1.8.78
  (`test_v380`, `test_v381_zahlungen_migration`) als Core-Insert statt ORM (das ORM schreibt `invoices.customer_id`, die es vor der
  Migration nicht gibt); die Z1-Probe fährt bis `c7d41e9a2b63`, danach bis head und zurück über diese. Strukturtests: `test_v329`
  (`PUT /api/reminders/{id}` aus den Altfällen, zu den reparierten), `test_v373` (`POST /api/reminders/bulk invoice_ids` als FREI).
- **Gegenproben** (Regel 24): 21 von 21 rot -- Kundenwechsel-Sperre (3 Tests), Sperre der Auftragszeilen beim Wechsel (2, PostgreSQL),
  Kunde beim Festschreiben (3), Kunde beim Storno (1), nichts zu mahnen (3), nicht fällig (3), ein Entwurf (3), nächste Stufe (2),
  Fristende (3), frisches Lesen nach der Sperre (1, PostgreSQL), Bearbeiten unter der Sperre (2), Mahndatum beim Festschreiben (1),
  Aufstellung beim Anlegen (1) und beim Festschreiben (1), E-Mail nur mit passendem Betrag (1), Zustellung prüft vorher (3), Stand am
  Zustelltag (1), Sperre bei der Zustellung (1, PostgreSQL), Dashboard (1), Migration übernimmt den Kunden (2), Rückweg verweigert (2).
  Jede Datei byte-genau zurück (SHA-256), kein Marker unter `app/` und `alembic/`. Ein erster Lauf zeigte Probe 10 grün: das
  zusätzliche Nachladen der Mahnungen nach der Sperre war überflüssig (`lock_order_invoices()` lädt die Rechnungen mit
  `populate_existing` und verwirft dabei die geladene Liste) -- entfernt, die Probe trifft jetzt genau diesen Mechanismus.
- Migration `5db1a12b4a66`: Wegwerf-SQLite und leeres Wegwerf-Schema der lokalen PostgreSQL: hoch, `current` head, `check` ohne
  Unterschied, runter, wieder hoch.
- Klicktests: neu `klicktest_mahnwesen.py` 27/27 (der erste Lauf fand „2 Entwurfe angelegt“ -- Plural ohne Umlaut, behoben).
  **Alle Klicktests** (`scripts/klicktest_alle.py`, Arbeitskopie mit dem Endstand, Regel 26): 48 von 48 wie erwartet, 10:43 min.
- Volle Suite (mit den opt-in-Tests gegen PostgreSQL, Arbeitskopie, Endstand): 3518 grün, 0 rot, 7 erwartet fehlgeschlagen (1a, 1b,
  1d), 27:42 min. Danach nur Doku geändert.

### Nebenbefunde (nur gemeldet)

1. **Name auf der Rechnung kommt aus dem Auftrag**: Rechnungen übernehmen Kundenname und -adresse aus dem Schnappschuss des Auftrags
   (`_snapshot_order_fields()`, `app/invoices.py`). Wird der Kunde am Projekt gewechselt, solange nur ein Auftrag (ohne festgeschriebene
   Rechnung) besteht, trägt jede spätere Rechnung den Namen des alten Kunden, gehört aber zum neuen (`customer_id`) und geht an dessen
   Adresse. Naheliegend: Kundenwechsel schon ab einem Auftrag sperren, oder den Schnappschuss beim Wechsel prüfen.
2. **Mahnung als E-Mail ohne Sperre**: zwischen der Prüfung (Betrag stimmt) und dem Senden kann eine Zahlung gebucht werden -- dieselbe
   bewusste Lücke wie seit 1.8.72 (Festlegung 1.8.72 Nr. 6), jetzt auch für den Betrag.
3. **Mahnwesen lädt alle Mahnungen** ohne Begrenzung (`GET /api/reminders`); der Zahlstand kommt seit 1.8.79 für alle in zwei Abfragen,
   je Entwurf aber eine Abfrage der Stufen (Datum beim Festschreiben) und je Mahnung der Kunde (Adresse).
4. **Gebühr der ersten Mahnung**: die Vorgabe fordert schon in der ersten Mahnung 5 € (Befund a) -- siehe die Einordnung oben.
5. Unverändert: Rechnung per E-Mail auch bezahlt oder storniert, Mahnhistorie auf der Rechnungsseite nur bei „versendet“ (1.8.77 Nr. 7),
   Probebelege entfernen (1.8.77 Nr. 8).
