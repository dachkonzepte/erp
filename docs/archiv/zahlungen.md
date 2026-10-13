# Zahlungen (Zahlungsstufe Z1 seit 1.8.78, Mahnwesen Z2a seit 1.8.79, Mahngebühren und Verzug Z2b seit 1.8.80/1.8.81)

Seit 1.8.89 (R4c): Mahnen nach der Endrechnung -- abgezogene Rechnungen nicht mehr einzeln, Mahnung der Schlussrechnung über den
Zahlbetrag, Verzugszinsen auf den angemahnten Betrag (`app/final_dunning.py`); seit 1.8.90 Überzahlung: Guthaben am Kunden,
Erstattung als Zahlungsausgang (`book_refund()`, Zuordnung Art "erstattung"). Herleitung, Festlegungen und Tests:
`docs/archiv/befund-vor-echtbetrieb.md`, "Umsetzung R4c".

Grundlage: Befund Zahlungsstufe in `befund-vor-echtbetrieb.md` ("Umsetzung 1.8.77" -> "Befund Zahlungsstufe") und dort
"Entscheidungen Rechnungen" (Zahlung auf den Zahlbetrag, Einbehalt). Code: `app/payments.py` (Geschäftslogik),
`app/routers/payments.py` (Endpunkte), Modelle `Payment`/`PaymentAllocation` (`app/models.py`), Migration `c7d41e9a2b63`.
Das Mahnwesen (Z2a, seit 1.8.79): `app/reminders.py`, `app/routers/reminders.py`, Migration `5db1a12b4a66` -- siehe
"Umsetzung 1.8.79"; ältere Herleitung des Mahnwesens in `mahnwesen.md`. Mahngebühren und Verzugszinsen (Z2b): Befund in
"Umsetzung 1.8.79", gebaut ab 1.8.80 (`app/dunning_charges.py`, `app/routers/dunning_charges.py`, Migration `8e2f4b6d1c97`) -- siehe
"Umsetzung 1.8.80"; die Punkte 7–9 (Verzugszinsen, Zahlungen auf Nebenforderungen, Rechtstexte) seit 1.8.81 (`app/default_interest.py`,
`app/dunning_texts.py`, Migration `a4c9e2f7b815`) -- siehe "Umsetzung 1.8.81".

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

### Festlegungen 1.8.78 (alle bestätigt am 12.10.2026: Nr. 3, 4, 5, 6, 11, 12 mit der Vorgabe zu 1.8.79, Nr. 1, 2, 7–10, 13–15 mit der zu 1.8.80)

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

### Festlegungen 1.8.79 (Nr. 1–5, 7–12 bestätigt am 12.10.2026; Nr. 6 geändert: Ersatz derselben Stufe, siehe "Umsetzung 1.8.80", Vorweg 2)

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

## Umsetzung 1.8.80: Vertragspartner am Auftrag, Mahnung ersetzen, Mahngebühren und Pauschale (Z2b, Punkte 3–6)

### Vorgabe vom 12.10.2026 (übernommen wie gegeben)

1.8.79 geprüft. Festlegungen 1.8.78 Nr. 1, 2, 7–10, 13–15 und 1.8.79 Nr. 1–5, 7–12 bestätigt; Nr. 6 geändert, siehe Vorweg 2.

Vorweg:
1. Vertragspartner am Auftrag (Nebenbefund 1): Der Auftrag hält beim Beauftragen seinen Kunden fest; Rechnungen übernehmen Kunde,
   Name und Anschrift vom Auftrag. Kundenwechsel am Projekt mit Auftrag nur zusammen mit bewusster Änderung am Auftrag, mit
   Begründung, und nur solange weder Rechnung noch Vertrag festgeschrieben ist.
2. Zu Nr. 6: Eine festgeschriebene Mahnung, die nie versendet oder zugestellt wurde, lässt sich durch eine neue derselben Stufe
   ersetzen; die alte gilt als ersetzt. Erreicht ist eine Stufe erst mit Versand oder Zustellung.

Z2b Mahngebühren und Verzugszinsen, zuschaltbar (zahlungen.md fortschreiben):
3. Schalter in den Einstellungen, Vorgabe aus. Aus heißt: keine Felder, keine Beträge; auch die heutigen Gebühren je Stufe wirken dann
   nicht.
4. Nebenforderungen als eigene, unveränderliche Tabelle je Rechnung (Art: Gebühr, Pauschale, Zinsen), nie im Rechnungsbetrag, ohne
   USt; in jeder Mahnung aufsummiert. Korrektur nur per Gegenbuchung.
5. Gebühr je Stufe als Vorschlag, je Mahnung bewusst übernommen; Vorgabe für Stufe 1: 0 €.
6. Pauschale 40 € (§ 288 Abs. 5 BGB): nur bei Kunden, die keine Verbraucher sind, einmal je Rechnung, erst ab Verzug, als Vorschlag.
7. Verzugszinsen: 5 Prozentpunkte über dem Basiszinssatz bei Verbrauchern, sonst 9. Basiszinssatz als Tabelle mit Gültigkeit, nur
   Admin, mit „geprüft am/durch“. Taggenau auf den jeweils offenen Betrag, abschnittsweise nach Zahlungen, als Vorschlag bis zum
   Mahndatum. Verzugsbeginn als Vorschlag zum Bestätigen: Zugang der ersten Mahnung (Versand oder nachgetragene Zustellung), bei
   Nicht-Verbrauchern spätestens 30 Tage nach Fälligkeit und Zugang der Rechnung.
8. Zahlungen: Vorschlag der Verteilung nach § 367 BGB, erst Kosten, dann Zinsen, dann Rechnung; das Büro bestätigt.
9. Texte zu Verzug, Zinsen und Pauschale als Rechtstexte (Admin, geprüft); ungeprüft werden sie nicht gedruckt, mit Warnung.

Angriffstests mit Gegenprobe, Gleichzeitigkeit gegen PostgreSQL. Eigene Festlegungen mit „Bitte bestätigen“. Nebenbefunde nur
melden. Wird der Umfang zu groß: nach Punkt 6 committen und den Rest auflisten. Commit nach Regel 13, Bericht kurz.

### Vorweg

- Festlegungen 1.8.78 und 1.8.79 an ihren Überschriften als bestätigt markiert, 1.8.79 Nr. 6 als geändert.
- **Umfang**: nach Punkt 6 committet (Vorgabe "wird der Umfang zu groß"). Gebaut sind Vorweg 1 und 2 und die Punkte 3–6; aus Punkt 7
  nur der **Verzugsbeginn** (Vorschlag und Bestätigen), weil die Pauschale "erst ab Verzug" ihn braucht. Offen: Punkt 7 ohne den
  Verzugsbeginn (Basiszinssatz, Zinsen), Punkt 8, Punkt 9 -- siehe "Rest (Punkte 7–9)" unten.

### Was gebaut ist

**Vorweg 1 -- Vertragspartner am Auftrag** (Migration `8e2f4b6d1c97`):
- `Order.customer_id` (FK `customers`, NOT NULL, Index): beim Beauftragen der Kunde des Projekts (`create_order_from_quote()` setzt ihn
  ausdrücklich; wer einen Auftrag ohne ihn anlegt -- Schnellauftrag, Tests --, bekommt den Kunden des Projekts im selben Augenblick,
  ORM-Ereignis `_order_holds_customer()`). Das Beauftragen sperrt dafür die Projektzeile (`SELECT … FOR UPDATE`) und liest das Projekt
  frisch.
- **Rechnung**: beim Festschreiben (unter der Sperre der Auftragszeile) Kunde (`_customer_at_finalize()`: der des Auftrags, beim Storno
  weiter der der stornierten Rechnung), Name, Kundennummer und Anschrift vom Auftrag; im Entwurf gilt der Kunde des Auftrags
  (`invoice_customer()`). Auftragsbestätigung per E-Mail an den Kunden des Auftrags; `order_to_dict()["customer_id"]` ist er. Der
  Abgleich mit dem Angebot zieht Name und Anschrift aus den Stammdaten des Kunden **des Auftrags** nach, er wechselt ihn nicht.
- **Kundenwechsel am Projekt** (`check_client_change(…, reason=)`, `PUT /api/projects/{id}` mit `customer_change_reason`): zuerst die
  Sperre der Projektzeile, dann aller Auftragszeilen; abgelehnt (409) bei festgeschriebener Rechnung (seit 1.8.79), festgeschriebenem
  Vertrag (seit 1.8.44), wenn der neue Kunde Beteiligter ist (seit 1.8.41) und -- neu -- wenn am Projekt ein Auftrag hängt und keine
  Begründung kam. Mit Begründung wechseln alle Aufträge des Projekts mit (`app/orders.py::change_orders_customer()`): Kunde, Name,
  Kundennummer, Anschrift; dazu der Schnappschuss der Rechnungsentwürfe. Je Auftrag eine Zeile `OrderCustomerChange` (alter und neuer
  Kunde mit Namen, Begründung, wer, wann; unveränderlich, in der Historie der Projektmappe unter "Auftrag").
- **Gleichzeitig** (PostgreSQL): ein Beauftragen wartet auf einen Wechsel und hält danach den neuen Kunden; ein Wechsel wartet auf das
  Beauftragen, findet den Auftrag und verlangt die Begründung.
- Oberfläche: Projektmappe → "Projektmappe bearbeiten": wählt man bei einem Projekt mit Auftrag einen anderen Kunden, erscheint das
  Pflichtfeld "Begründung des Kundenwechsels" mit Hinweis.
- Bestand: `scripts/pruefabfrage_auftrag_kunde.sql` listet Aufträge, deren Name im Schnappschuss nicht der ihres Kunden ist (Kunde am
  Projekt nach dem Beauftragen gewechselt oder im Kundenstamm umbenannt), und festgeschriebene Rechnungen mit anderem Kunden als ihr
  Auftrag (sollte leer sein).

**Vorweg 2 -- erreicht erst mit Versand oder Zustellung, Ersatz**:
- `app/email_dispatch.py::document_reached_on()` (für jede Dokumentart; `reached_client()` von den Briefen der Anzeigen hierher
  verlegt): je Dokument der erste Tag, an dem es beim Auftraggeber ankam -- E-Mail gesendet (Tag des Abschlusses in Berlin) oder
  Zustellung nachgetragen (Zustelldatum), nicht als unzustellbar vermerkt, nicht nur an Beteiligte ohne Empfangsvollmacht. Bestand von
  vor dem Versandprotokoll (1.8.17): `email_sent_at` ohne jeden Protokolleintrag zählt.
- Mahnstufe (`app/reminders.py::_step()`, `reached_map()`): erreicht ist nur die höchste Stufe einer **hinausgegangenen** Mahnung; die
  Frist der vorigen ist die der zuletzt hinausgegangenen. Eine festgeschriebene, nie hinausgegangene (`pending_reminder()`) hält eine
  neue derselben Stufe nicht auf.
- **Ersatz**: beim Festschreiben einer Mahnung gelten alle festgeschriebenen, nie hinausgegangenen, nicht ersetzten Mahnungen der Rechnung
  bis zu dieser Stufe als ersetzt (`Reminder.replaced_by_id`, `replaced_at`, unter der Sperre der Auftragszeile); ihre Nebenforderungen
  werden gegengebucht ("… ging nie hinaus und ist durch die Mahnung … ersetzt."). Eine ersetzte Mahnung geht weder per E-Mail noch als
  Zustellung hinaus (409 "… ist durch die Mahnung … ersetzt"). Ging die alte doch noch hinaus, bevor der Ersatz festgeschrieben ist, ist
  der Ersatz "überholt" (409) -- unter PostgreSQL wartet das eine auf das andere.
- "Zur Mahnung fällig" (`due_for_reminder()`, Feld der Liste): nicht, solange eine festgeschriebene Mahnung noch hinausgehen kann -- die
  Zeile steht unter "Weitere überfällige" mit "… ging aber noch nicht hinaus – bitte versenden oder die Zustellung nachtragen" und
  "Durch neue ersetzen". Kann sie nicht mehr hinausgehen (Betrag überholt), ist die Rechnung zur Mahnung fällig, der Knopf heißt
  "… als Entwurf anlegen (ersetzt M-…)".
- Zustellung nachtragen liest die Mahnung nach der Sperre frisch und lehnt einen Tag vor dem Mahndatum ab.
- `{vorheriges_mahndatum}` ist das der vorigen Stufe, die hinausging.
- Oberfläche: Mahnwesen "Alle Mahnungen" mit Status Entwurf / Festgeschrieben (noch nicht hinaus) / Hinausgegangen (Datum) / Ersetzt
  (durch …); Rechnungsseite je Mahnung "Hinausgegangen am …", "Noch nicht versendet oder zugestellt – die Stufe gilt erst danach als
  erreicht" bzw. "Ersetzt durch …", Kopfzeile "Erreicht: Stufe …".
- Bestand: `scripts/pruefabfrage_mahnungen_zugang.sql` listet festgeschriebene Mahnungen ganz ohne Versand- oder Zustellnachweis.

**Nr. 3 -- Schalter** (`GeneralSettings.dunning_charges_enabled`, Vorgabe aus; `GET/PUT /api/dunning-settings`, PUT nur Admin): Einstellungen
→ Mahnstufen, Karte "Mahngebühren und Verzugszinsen". Aus: keine Gebührenfelder in den Mahnstufen und im Entwurf,
`PUT /api/reminders/{id}/charges` 409, ein neuer Entwurf trägt keine Gebühr, beim Festschreiben wird eine Gebühr aus einem älteren
Entwurf auf 0 gesetzt, die Mahnung nennt keine Nebenforderungen. Ein Text mit `{mahngebuehr}` bekommt in den Einstellungen und im Editor
einen Hinweis ("ergibt 0,00 €"). Die Mahnstufen speichern seit 1.8.80 nur gesendete Felder (`ReminderLevelUpdate` als Teil-Update, aus
den Altfällen gestrichen); der Bereich "E-Mail-Vorlagen" schickt nur Betreff und Text.

**Nr. 4 -- Nebenforderungen** (`InvoiceCharge`, `app/dunning_charges.py`): je Rechnung, Art `gebuehr` oder `pauschale` (Zinsen mit
Punkt 7), Betrag auf den Cent, die Mahnung, mit deren Festschreiben sie entstand; nie im Rechnungsbetrag, nicht im Zahlstand, ohne USt.
Unveränderlich (ORM-Sperre), Gegenbuchung ganz mit Begründung (`reverse_charge()`, `POST /api/invoice-charges/{id}/reverse`, unter der
Sperre der Auftragszeile, einmal, UNIQUE). Geltend = nicht gegengebucht. Jede Mahnung zeigt die geltenden der Rechnung aufsummiert:
Aufstellung Format 2 (`amounts_json` dazu mit `charges_enabled`, je Nebenforderung Bezeichnung und Betrag, `charges_open`, `total`), im
PDF nach "Angemahnter Betrag" je Zeile und "Gesamtbetrag"; `{gesamtbetrag}` ist angemahnter Betrag + Nebenforderungen, neu
`{nebenforderungen}`. Versand und Zustellung prüfen die Nebenforderungen wie den Betrag (am Zustelltag die bis dahin entstandenen; eine
gegengebuchte gilt nie). Rechnungsseite: Karte "Nebenforderungen und Verzug" (Liste mit Gegenbuchen und Begründung, offen). Mahnungen
von vor 1.8.80 bleiben, wie sie sind (Gebühr an der Mahnung, keine Nebenforderung).

**Nr. 5 -- Gebühr als Vorschlag**: ein neuer Entwurf (eingeschaltet) trägt die Gebühr der Stufe als Vorschlag (`fee_amount`), übernommen
nur mit Häkchen (`Reminder.fee_accepted`; `PUT /api/reminders/{id}/charges` mit `fee_amount`, `fee_accepted`, `flat_fee_accepted`, alle
Pflicht; `PUT /api/reminders/{id}` trägt die Gebühr nicht mehr). Nicht übernommen: beim Festschreiben 0, keine Nebenforderung. Stufe 1
schlägt 0 € vor (`DEFAULT_REMINDER_LEVELS`; Migration: 5,00 € → 0,00 €). Die drei Standard-Mahntexte nennen den Gesamtbetrag
("Betrag von {gesamtbetrag} (Aufstellung unten)") statt "zuzüglich einer Mahngebühr von {mahngebuehr}" -- unveränderte Texte stellt die
Migration um.

**Nr. 6 -- Pauschale und Verzugsbeginn**:
- Pauschale 40 € (`FLAT_FEE`) im Entwurf als Vorschlag, übernommen mit Häkchen (`flat_fee_accepted`); möglich nur
  (`flat_fee_block_reason()`): eingeschaltet, Kunde der Rechnung kein Verbraucher, Verzugsbeginn bestätigt und spätestens am Mahndatum,
  keine geltende Pauschale an der Rechnung (die der Mahnungen, die der Entwurf ersetzen wird, zählen nicht). Geprüft beim Übernehmen und
  noch einmal beim Festschreiben unter der Sperre (409 mit Grund); der Editor zeigt den Grund und sperrt das Häkchen.
- Verzugsbeginn (`InvoiceDefaultStart`): Vorschlag `default_start_proposal()` mit Quelle -- Zugang der ersten Mahnung (Tag des Zugangs)
  und, bei Kunden, die keine Verbraucher sind, der 31. Tag nach dem späteren von Fälligkeit (`due_date`, ohne sie das Rechnungsdatum)
  und Zugang der Rechnung (Versand oder Zustellung der Rechnung); das frühere. Ohne Quelle der Grund. Bestätigen
  (`confirm_default_start()`, `POST /api/invoices/{id}/default-start`): der Vorschlag oder ein anderer Tag mit Begründung (Grundlage
  "abweichend festgelegt"), nicht in der Zukunft, nicht vor dem Tag nach der Fälligkeit, nur an einer festgeschriebenen, nicht
  stornierten Rechnung (keine Stornorechnung), höchstens einer (unter der Sperre). Verwerfen mit Begründung
  (`POST /api/invoice-default-starts/{id}/discard`), nicht solange eine Pauschale gilt. Unveränderlich bis aufs Verwerfen.
- Rechnungsseite: Karte "Nebenforderungen und Verzug" mit Vorschlag, "Verzugsbeginn bestätigen", "Anderen Tag festlegen" (Datum,
  Begründung), "Verwerfen". Mahnungs-Editor (Mahnwesen und Rechnungsseite): Vorschlag der Gebühr mit Häkchen und Betrag, Pauschale mit
  Häkchen oder Grund, die schon geltenden Nebenforderungen.

**Migration `8e2f4b6d1c97`**: Spalten `orders.customer_id` (gefüllt mit dem Kunden des Projekts, dann NOT NULL),
`reminders.replaced_by_id/replaced_at/fee_accepted/flat_fee_accepted`, `general_settings.dunning_charges_enabled`; Tabellen
`order_customer_changes`, `invoice_charges`, `invoice_default_starts`; Stufe 1 5,00 € → 0,00 €, unveränderte Standardtexte → neue.
`downgrade()` verweigert, solange eine Nebenforderung, ein Verzugsbeginn, ein Kundenwechsel am Auftrag oder eine ersetzte Mahnung besteht;
sonst Texte und Gebühr zurück, soweit sie noch genau auf dem Stand der Migration stehen.

**Rollen**: Schalter nur Admin (lesen ab `buero_auftrag`), alles andere ab `buero_auftrag` wie die Rechnungen; der Monteur nirgends (403).

### Festlegungen 1.8.80 (alle bestätigt am 12.10.2026; zu Nr. 2 und 13 siehe "Umsetzung 1.8.81", Vorweg)

1. **Hinausgegangen** heißt: E-Mail gesendet oder Zustellung nachgetragen, beim Auftraggeber angekommen (nicht "unzustellbar", nicht nur an
   Beteiligte ohne Empfangsvollmacht) -- wie bei den Briefen der Anzeigen; "in Arbeit" zählt nicht. Bestand: eine E-Mail von vor dem
   Versandprotokoll (nur `email_sent_at`) zählt; eine festgeschriebene Mahnung ohne jeden Nachweis (ausgedruckt, per Post) zählt **nicht**
   -- Ausweg: Zustellung nachtragen (Prüfabfrage `pruefabfrage_mahnungen_zugang.sql`).
2. **Ersatz** erfasst beim Festschreiben alle nie hinausgegangenen, nicht ersetzten Mahnungen der Rechnung bis zu dieser Stufe und bucht ihre
   Nebenforderungen von selbst gegen (Begründung mit beiden Nummern). Ersetzen geht auch, solange die alte noch hinausgehen könnte; "zur
   Mahnung fällig" ist die Rechnung dann aber nicht ("bitte versenden", Knopf "Durch neue ersetzen").
3. **Zustellung vor dem Mahndatum** nachtragen: abgelehnt (409) -- neu, eine Plausibilitätsprüfung.
4. **Kundenwechsel**: am Auftrag wechseln Kunde, Name, Kundennummer und Anschrift, das Objekt im Auftrag bleibt; Rechnungsentwürfe bekommen
   den neuen Schnappschuss; eine Begründung für alle Aufträge des Projekts. Reihenfolge der Gründe: Rechnung → Vertrag → Beteiligter →
   Begründung.
5. **Rechnung beim Festschreiben**: Kunde, Name, Kundennummer und Anschrift kommen vom Auftrag, frisch unter der Sperre -- auch wenn der
   Entwurf anderes trug (Storno: wie die stornierte Rechnung).
6. **Bestand der Aufträge**: der Kunde des Projekts am Tag der Migration (wie 1.8.79 bei den Rechnungen); abweichende Namen zeigt die
   Prüfabfrage, die Migration ändert keinen Namen.
7. **Schalter aus**: schon gebuchte Nebenforderungen bleiben gebucht, auf der Rechnungsseite sichtbar und gegenbuchbar; neue Mahnungen
   nennen keine (auch keine schon gebuchten).
8. **Standardtexte**: nur unverändert gebliebene werden ersetzt; geänderte Texte mit `{mahngebuehr}` bekommen bei ausgeschalteten Gebühren
   einen Hinweis, keine Sperre.
9. **Gebühr der Stufe 1 im Bestand**: genau 5,00 € → 0,00 €; der Rückweg setzt 0,00 € wieder auf 5,00 € (stand Stufe 1 schon vor dem
   Update von Hand auf 0 €, stünde sie nach einem Rückweg auf 5 €).
10. **Gebühr**: Betrag im Entwurf änderbar (Vorschlag vorausgefüllt), gilt nur mit Häkchen; die Nebenforderung entsteht beim Festschreiben
    der Mahnung, nicht im Entwurf und nicht erst mit dem Versand.
11. **Gegenbuchung einer Nebenforderung** ganz, mit Begründung, ab `buero_auftrag`; eine Mahnung, deren Nebenforderungen sich danach
    ändern, geht nicht mehr hinaus.
12. **Pauschale**: der festgehaltene Kunde der Rechnung entscheidet über "Verbraucher"; eine gegengebuchte Pauschale zählt nicht für
    "einmal je Rechnung".
13. **Verzugsbeginn** ist der erste Tag im Verzug: Mahnung -- der Tag ihres Zugangs (Versand bzw. Zustelldatum); 30 Tage -- der 31. Tag
    nach dem späteren von Fälligkeit (`due_date`, ohne sie Rechnungsdatum) und Zugang der Rechnung; das frühere gilt. Verbraucher nur über
    die Mahnung (der Hinweis nach § 286 Abs. 3 BGB auf der Rechnung ist nicht festgehalten). Bestätigen nicht in der Zukunft, nicht vor dem
    Tag nach der Fälligkeit, abweichend nur mit Begründung. Ab welchem Tag Zinsen laufen (Folgetag des Zugangs, § 187 BGB), legt Punkt 7
    fest.
14. **Rollen**: Schalter nur Admin; Verzugsbeginn, Gebühr, Pauschale, Gegenbuchung ab `buero_auftrag`.

### Rest (Punkte 7–9) -- nicht gebaut, zum Festlegen

- **Punkt 7 (ohne den Verzugsbeginn)**: Tabelle Basiszinssatz (gültig ab, Satz -- auch negativ --, geprüft am/durch, nur Admin, nach der
  Prüfung unveränderlich); Zinsen als Nebenforderung Art `zinsen` mit Zeitraum und eingefrorener Berechnung (je Abschnitt: von, bis,
  offener Betrag, Satz, Tage, Betrag) -- dafür Spalten an `invoice_charges`. Zu entscheiden: Tage im Jahr (365 oder tatsächliche),
  Zinsbeginn (Folgetag des Zugangs der Mahnung nach § 187 Abs. 1 BGB, beim 30-Tage-Fall der 31. Tag), Rundung je Abschnitt oder gesamt,
  und wie eine spätere Mahnung an die schon berechneten Zinsen anschließt (ab dem Tag nach dem letzten berechneten).
- **Punkt 8**: Zuordnung einer Zahlung auf Nebenforderungen (`PaymentAllocation` mit Verweis auf `InvoiceCharge`), Vorschlag nach
  § 367 BGB -- je Rechnung (älteste zuerst, wie heute) erst Kosten (Gebühren, Pauschale), dann Zinsen, dann die Rechnung; Gegenbuchung
  einer Nebenforderung erst nach gelöster Zuordnung; Rest einer Zahlung und "Nicht zugeordnet" in Finanzen zählen die Zuordnungen auf
  Nebenforderungen mit.
- **Punkt 9**: Rechtstexte zu Verzug, Zinsen und Pauschale (Admin, geprüft am/durch, wie die Klauseln der Vertragsgrundlagen); im PDF nur
  geprüft, sonst Warnung im Entwurf.

### Tests und Prüfung

- Neu `tests/test_v383_nebenforderungen.py` (52): Vorweg 1 (Auftrag hält den Kunden, Rechnung übernimmt Kunde, Name und Anschrift vom
  Auftrag, auch an einem am Wechsel vorbei geänderten Projekt; Kundenwechsel mit Auftrag ohne Begründung 409, mit Begründung samt
  Auftrag, Rechnungsentwurf und unveränderlicher Historie; mit festgeschriebener Rechnung auch mit Begründung 409; ohne Auftrag ohne
  Begründung); Vorweg 2 (Stufe erst mit Zustellung erreicht; was als hinausgegangen zählt: E-Mail, Einschreiben, Altbestand
  `email_sent_at` -- nicht unzustellbar, nur Beteiligter, "in Arbeit"; Ersatz einer überholten, nie versendeten Mahnung, danach E-Mail und
  Zustellung 409; eine hinausgegangene wird nicht ersetzt; eine versendbare hält "zur Mahnung fällig" an, Ersatz geht trotzdem; Ersatz
  überholt, wenn die alte vorher hinausgeht; `{vorheriges_mahndatum}`; Zustellung vor dem Mahndatum 409); Nr. 3 (Vorgabe aus, keine
  Gebühr und keine Beträge, auch ein Entwurf mit Gebühr; Übernehmen 409; nur Admin schaltet -- vier Rollen; Mahnstufen nur gesendete
  Felder); Nr. 4 (Gebühr und Pauschale als Nebenforderungen, in der 3. Mahnung aufsummiert, PDF, nie im Rechnungsbetrag; ORM-Sperre,
  Gegenbuchung einmal mit Begründung; Mahnung mit geänderten Nebenforderungen geht nicht hinaus; kein `update()`/`delete()` (AST)); Nr. 5
  (Vorschlag nicht übernommen -> keine Nebenforderung; Stufe 1 ohne, Standardtexte ohne `{mahngebuehr}`); Nr. 6 (Pauschale nicht für
  Verbraucher, nur mit bestätigtem Verzug und beim Festschreiben neu geprüft, einmal je Rechnung auch am Entwurf vorbei; Ersatz bucht die
  alten Nebenforderungen gegen und erlaubt die Pauschale neu; Vorschlag Verzugsbeginn: früheres von Mahnung und 30 Tagen, Verbraucher
  nur Mahnung; Bestätigen: Zukunft, vor Fälligkeit, ohne Begründung abweichend, zweimal -- je abgelehnt; Verwerfen nicht mit Pauschale;
  Stornorechnung, Entwurf, stornierte ohne Verzug); Router (200/409/422/404, "erfasst von" aus der Anmeldung), Monteurin 403 an fünf
  Endpunkten; **Rundgang mit Beobachter**: jeder neue schreibende Weg (Festschreiben mit Gebühr und Pauschale, Übernehmen, Gegenbuchen,
  Verzugsbeginn bestätigen und verwerfen, Kundenwechsel) schreibt Nebenforderung, Verzugsbeginn, Mahnung, Rechnung, Auftrag und
  Kundenwechsel nur unter der Sperre der Auftragszeile; jede schreibende Route des neuen Routers ist im Rundgang.
- Neu `tests/test_v383_nebenforderungen_pg.py` (8, gegen PostgreSQL): Verzugsbeginn zweimal -> einer; Ersatz gegen Zustellung der alten
  in beiden Reihenfolgen; dieselbe Gegenbuchung zweimal -> eine; Pauschale beim Festschreiben gegen Verwerfen des Verzugsbeginns in beiden
  Reihenfolgen; Kundenwechsel gegen Beauftragen in beiden Reihenfolgen.
- Neu `tests/test_v383_nebenforderungen_migration.py` (3, davon 1 gegen PostgreSQL): neue Standardtexte der Migration = die heutigen;
  Probe auf einem Bestand (drei Aufträge, einer mit nach dem Beauftragen gewechseltem Kunden; Stufen mit alten Texten, einem eigenen
  Text, 5 € an Stufe 1): hoch -> Kunden der Aufträge, Stufe 1 0 €, eigener Text bleibt, Prüfabfrage findet genau den gewechselten
  Auftrag; runter -> exakt wie vorher; wieder hoch, eine Nebenforderung -> Rückweg verweigert, nichts geändert.
- **Angepasst, weil die Vorgabe die Erwartung überholt**: `test_v153` (Stufe 1 ohne Gebühr, nächste Stufe erst nach Zustellung,
  Gesamtbetrag ohne Gebühr), `test_v236` (Entwurfs-PUT ohne Gebühr, Platzhalterliste), `test_v382` (Kundenwechsel mit Begründung, Stufe
  erst nach Zustellung, Aufstellung Format 2, PUT ohne Gebühr, Rundgang um `PUT /api/reminders/{id}/charges`, Zustellung nicht vor dem
  Mahndatum), `test_v382_mahnwesen_pg` (dasselbe), `test_v315` (Rundung des Gesamtbetrags an einer Mahnung von vor 1.8.80), `test_v227`
  und `test_v231` (Gesamtbetrag 5.950 statt 5.955), `test_v344` und `test_v347` (Kundenwechsel mit Begründung), `test_v375` und
  `test_v380` (Stufe 2 erst nach Zustellung). Strukturtests: `test_v325_quote_order_copy_fields` (`Order.customer_id` eigen),
  `test_v329` (Mahnstufen aus den Altfällen zu den reparierten), `test_v364` (`invoice_charges.kind`, `invoice_default_starts.basis`).
  Migrationsproben: `test_v325_contract_basis` (Core-Insert mit `customer_id`), `test_v380`/`test_v381`/`test_v382` (Bestand über
  `tests/bestand_alt.py`). `test_v297` (Outlook gegen PostgreSQL) in ein Wegwerf-Schema statt `public` (dort fehlte die neue Spalte,
  `create_all()` zieht bestehende Tabellen nicht nach). Testhilfe `tests/mahnung.py::zustellen()`.
- **Gegenproben** (Regel 24): 33 von 33 rot -- Kunde des Auftrags beim Festschreiben (1), Name und Anschrift vom Auftrag (1), Begründung
  beim Kundenwechsel (1), Rechnungsentwürfe beim Wechsel (1), Sperre der Projektzeile beim Beauftragen und beim Wechsel (je 1,
  PostgreSQL), Kunde am Auftrag ohne Angabe (1), erreicht nur mit Versand/Zustellung (1), unzustellbar (1), nur Beteiligter (1), Ersatz
  markiert (1), ersetzte geht nicht hinaus (1), Zustellung liest frisch (1, PostgreSQL), aus: keine Gebühr (1), aus: Übernehmen 409 (1),
  Schalter nur Admin (1), ORM-Sperre (1), Gegenbuchung einmal (2, davon 1 PostgreSQL), Gegenbuchung unter der Sperre (2, davon 1
  PostgreSQL), Gebühr nur übernommen (1), Pauschale: Verbraucher (1), bestätigter Verzug (1), einmal (1), beim Festschreiben (2, davon
  1 PostgreSQL), Verwerfen mit Pauschale (2, davon 1 PostgreSQL), Verzugsbeginn einmal (2, davon 1 PostgreSQL), nicht in der Zukunft (1),
  Ersatz bucht gegen (1), Ersatz-Entwurf ohne die alten (1), Versand prüft die Nebenforderungen (1), Mahnstufen Teil-Update (1),
  Migration Stufen und Texte (1), Rückweg verweigert (1). Jede Datei byte-genau zurück (SHA-256), kein Marker unter `app/` und `alembic/`.
  Ein erster Lauf übersprang 15 Proben (mehrzeilige Muster ohne CRLF) -- wiederholt, alle rot.
- Migration `8e2f4b6d1c97`: Wegwerf-SQLite und leeres Wegwerf-Schema der lokalen PostgreSQL: hoch, `current` head, `check` ohne
  Unterschied, runter, wieder hoch.
- Klicktests: neu `klicktest_nebenforderungen.py` 30/30 (erster Lauf 19/30: die Einstellungsseite blieb beim Wechsel auf das
  Admin-Konto mit gleicher Adresse stehen -- Testfehler, Adresse geändert). `klicktest_mahnwesen.py` erwartete die überholte, nie
  versendete Mahnung nicht unter "zur Mahnung fällig" -- seit 1.8.80 veraltet (Vorweg 2), jetzt mit Ersatz; die 1. Mahnung in der Frist
  ist dort zugestellt, die neue wird zugestellt. **Alle Klicktests** (`scripts/klicktest_alle.py`, Arbeitskopie mit dem Endstand,
  Regel 26): 49 von 49 wie erwartet, 10:49 min.
- Volle Suite (mit den opt-in-Tests gegen PostgreSQL, Arbeitskopie, Endstand): 3582 grün, 0 rot, 7 erwartet fehlgeschlagen (1a, 1b,
  1d), 27:57 min. Ein erster Lauf hatte 3 rot (`test_v297` in `public`, siehe oben); danach umgestellt und der zweite Lauf. Danach nur
  Doku geändert.

### Nebenbefunde (nur gemeldet)

1. **Pauschale neben Mahngebühren**: nach § 288 Abs. 5 S. 3 BGB wird die Pauschale auf einen Schadensersatz angerechnet, soweit der Schaden
   in Kosten der Rechtsverfolgung begründet ist -- Mahngebühren daneben sind nach verbreiteter Ansicht anzurechnen. Das ERP schlägt beides
   vor und rechnet nichts an.
2. **Storno mit Nebenforderungen**: ein Storno sperrt nur bei Zuordnungen (1.8.78), nicht bei geltenden Nebenforderungen -- sie bleiben
   gebucht und müssen von Hand gegengebucht werden.
3. **Zahlungen auf Gebühren und Pauschale** landen bis Punkt 8 als Rest am Kunden (eine Zahlung über Rechnung + Gebühr ist an der Rechnung
   eine Überbuchung) -- den Schalter bis dahin aus lassen.
4. **Mahnung per E-Mail ohne Sperre**: zwischen Prüfung und Senden kann eine neue derselben Stufe festgeschrieben werden -- dieselbe bewusste
   Lücke wie 1.8.79 Nebenbefund 2.
5. **Projekt und Auftrag**: rund 36 Stellen lesen weiterhin den Kunden des Projekts (Briefe, Checklisten, Beteiligte …). Seit 1.8.80 bleiben
   beide gleich; ein Altbestand mit abweichendem Kunden zeigt sich in der Prüfabfrage und wie bisher in `customer_mismatch()`.
6. **Migrationsproben älterer Stände** legten ihren Bestand mit dem heutigen ORM an und brachen an jeder neuen Spalte (1.8.79:
   `invoices.customer_id`, jetzt `orders.customer_id` und `general_settings.dunning_charges_enabled`, die `app.grunddaten.anlegen()` liest)
   -- seit 1.8.80 über `tests/bestand_alt.py` (Core-Insert mit den Spalten des jeweiligen Stands).
7. Unverändert: Rechnung per E-Mail auch bezahlt oder storniert, Mahnhistorie auf der Rechnungsseite nur bei "versendet" (1.8.77 Nr. 7),
   Probebelege entfernen (1.8.77 Nr. 8), Mahnwesen lädt alle Mahnungen (1.8.79 Nr. 3).

## Umsetzung 1.8.81: Verzugszinsen, Zahlungen auf Nebenforderungen, Rechtstexte (Z2b, Punkte 7–9)

### Vorgabe vom 12.10.2026 (übernommen wie gegeben)

1.8.80 geprüft. Festlegungen 1–14 bestätigt. Zu 2: Der Dialog nennt vor dem Ersetzen die Nebenforderungen, die gegengebucht werden. Zu
13: Die 30-Tage-Regel gilt nur für Kunden, die keine Verbraucher sind, solange Rechnungen an Verbraucher keinen Hinweis nach § 286 Abs. 3
BGB tragen; ist das schon so, nur bestätigen.

Vorweg:
1. Ist für eine Rechnung die Pauschale gebucht, schlägt die Mahnung keine Gebühr mehr vor, mit Hinweis „durch die Pauschale abgegolten
   (§ 288 Abs. 5 S. 3 BGB)“.
2. Storno nur ohne offene Nebenforderungen, wie bei Zahlungen; sonst 409 mit Hinweis.
3. Muster: Kein Test gegen PostgreSQL läuft im Schema public der Spielwiese; Strukturtest. Migrationen, die Daten ändern, auch gegen
   PostgreSQL mit Daten prüfen, nicht nur auf leerem Schema.

Punkte 7–9:
4. Zinsen: Basiszinssatz-Tabelle (nur Admin, „geprüft am/durch“); fehlt ein Zeitraum, kein Vorschlag, mit Hinweis. Tatsächliche Tage
   durch 365. Zinsen laufen ab dem Tag nach dem Zugang der Mahnung, nach der 30-Tage-Regel ab dem 31. Tag. Je Abschnitt exakt, gerundet
   wird einmal am Ende kaufmännisch. Vorschlag bis zum Mahndatum, die Nebenforderung entsteht beim Festschreiben.
5. Verteilung nach § 367 BGB: je Rechnung erst Kosten (Gebühr, Pauschale), dann Zinsen, dann Rechnung; über mehrere Rechnungen weiter die
   älteste zuerst. Vorschlag, das Büro bestätigt.
6. Rechtstexte für Verzug, Zinsen und Pauschale wie vorgegeben (nur Admin, geprüft; ungeprüft nicht gedruckt, mit Warnung).

Angriffstests mit Gegenprobe, Gleichzeitigkeit gegen PostgreSQL. Eigene Festlegungen mit „Bitte bestätigen“. Nebenbefunde nur melden.
Commit nach Regel 13, Bericht kurz.

### Vorweg

- Festlegungen 1.8.80 an ihrer Überschrift als bestätigt markiert.
- **Zu Nr. 2**: Liste ("Alle Mahnungen", "Weitere überfällige", "Zur Mahnung fällig"), Mahnungs-Editor und die Rückfrage vor dem
  Festschreiben nennen die Mahnungen, die das Festschreiben ersetzt, und je Mahnung die Nebenforderungen, die dabei gegengebucht werden
  ("Beim Festschreiben ersetzt: M-… – gegengebucht werden: Mahngebühr (2. Mahnung M-…) 10,00 €"); vom Server `reminder_to_dict()["replaces"]`
  (`replaces_info()`) und `compute_reminder_status()["pending"]["charges"]`.
- **Zu Nr. 13**: ist schon so -- nur bestätigt. Die 30-Tage-Regel gilt nur für Kunden, die keine Verbraucher sind
  (`app/dunning_charges.py::default_start_proposal()`); die Rechnung trägt keinen Hinweis nach § 286 Abs. 3 BGB (das Rechnungs-PDF nennt
  weder Verzug noch 30 Tage, Test `test_thirty_day_rule_only_for_customers_who_are_not_consumers`). Kommt der Hinweis auf die Rechnung,
  muss der Vorschlag für Verbraucher angepasst werden.
- Der Umfang blieb in einer Version: Vorweg 1–3 und die Punkte 4–6 gebaut, ein Commit.

### Was gebaut ist

**Vorweg 1 -- keine Gebühr neben der Pauschale** (`fee_block_reason()`, `app/dunning_charges.py`): gilt an der Rechnung eine Pauschale
(die der Mahnungen, die der Entwurf ersetzen wird, zählen nicht), schlägt ein neuer Entwurf keine Gebühr vor (`fee_amount` 0), die
Vorschläge tragen `fee.block` "Keine Mahngebühr – durch die Pauschale abgegolten (§ 288 Abs. 5 S. 3 BGB): die Pauschale ist an dieser
Rechnung gebucht (mit der Mahnung …)". Übernimmt der Entwurf selbst die Pauschale, gilt dasselbe für ihn. Geprüft beim Übernehmen
(`set_reminder_charges()`, 409) und beim Festschreiben unter der Sperre (409). Editor: Hinweis statt Vorschlag, das Häkchen der Pauschale
sperrt das der Gebühr.

**Vorweg 2 -- Storno nur ohne offene Nebenforderungen** (`charges_storno_block_reason()`, aus `app/invoices.py::storno_block_reason()`):
beim Anlegen und beim Festschreiben des Stornos unter der Sperre: "An der Rechnung gelten offene Nebenforderungen (Mahngebühr 10,00 €).
Erst gegenbuchen (Karte „Nebenforderungen und Verzug“, mit Begründung), dann stornieren." -- 409, die Rechnungsseite zeigt den Grund statt
"Stornieren". Eine bezahlte Nebenforderung sperrt über ihre Zuordnung (wie jede Zahlung, `allocation_block_reason()`).

**Vorweg 3 -- kein Test gegen PostgreSQL im Schema public** (`tests/pg_schutz.py`, Regel 27): ein Wächter für den ganzen Testprozess
(`tests/conftest.py`): jede neue PostgreSQL-Verbindung merkt sich `current_schema()`; in `public` lässt er nur CREATE/DROP SCHEMA,
`pg_terminate_backend` und die Anfragen des Treibers beim Verbinden durch, alles andere bricht mit `SchemaPublicVerboten` ab.
Kindprozesse (alembic, ein Start von `app.main`) sieht er nicht: jede Funktion unter `tests/`, die `DATABASE_URL` an einen Kindprozess
gibt, prüft die URL mit `pg_url_pruefen()` (PostgreSQL nur mit eigenem `search_path`, nicht `public`). Strukturtest
`tests/test_v384_pg_nicht_public.py`: Wächter eingerichtet; Kindprozess-Weitergaben geprüft (AST); jede Engine auf
`ERP_TEST_POSTGRES_URL` hat ein eigenes Schema oder dient nur der Verwaltung (AST); gegen PostgreSQL: eine Verbindung in public darf
nichts außer Schemas anlegen/löschen. Alle 147 bestehenden PostgreSQL-Tests laufen mit dem Wächter. **Migrationen mit Daten**: die
Migration dieser Runde ändert keine Daten, ist aber trotzdem auf einem Bestand gegen PostgreSQL geprobt
(`tests/test_v384_verzugszinsen_migration.py`).

**Punkt 4 -- Basiszinssatz und Verzugszinsen** (`app/default_interest.py`):
- `BaseInterestRate` (`base_interest_rates`): je Halbjahr eine Zeile (`half_year_start` 1. Januar oder 1. Juli, UNIQUE), Satz in Prozent
  (auch negativ, drei Nachkommastellen), "geprüft am/durch". Gezählt wird nur ein geprüfter Satz; ändert sich der Satz ohne neue
  Prüfangabe, fällt sie weg (`update_rate()`, `review_reset`); löschen nur ungeprüft. `GET /api/base-interest-rates` ab buero_auftrag,
  `POST`/`PUT`/`DELETE` nur Admin (409 Halbjahr doppelt bzw. geprüft löschen, 422 Eingabe). Einstellungen → Mahnstufen, Tabelle mit
  Halbjahr, Satz, Prüfangabe und einer Zeile "Neu, gültig ab". Keine vorgegebenen Werte.
- Vorschlag (`interest_proposal(db, invoice, until=Mahndatum)`): Zinsbeginn (`interest_start_day()`) der Tag nach dem Verzugsbeginn
  (Zugang der Mahnung, ebenso ein abweichend festgelegter), nach der 30-Tage-Regel der Verzugsbeginn selbst (der 31. Tag); ohne
  bestätigten Verzugsbeginn kein Vorschlag. Schließt an geltende Zinsen an (ab dem Tag nach ihrem spätesten Ende, `last_interest_end()`).
  Fehlt im Zeitraum ein Halbjahr oder ist es ungeprüft: kein Vorschlag, Hinweis mit den Halbjahren (`rate_gap_reason()`). Zinssatz =
  Basiszinssatz + 5 (Verbraucher) bzw. 9 Prozentpunkte (Kunde der Rechnung). Verzinst wird der mahnfähige Betrag (`payment_state_on()`);
  Abschnitte beginnen am Eingangstag einer Zahlung (der gezahlte Teil ist ab dann zinsfrei) und am Halbjahresbeginn, gleiche
  aufeinanderfolgende werden zusammengefasst. Je Abschnitt `Hauptbetrag × Satz × Tage / (100 × 365)` exakt (Decimal), tatsächliche Tage
  mit beiden Enden, auch im Schaltjahr durch 365; die Summe einmal kaufmännisch auf den Cent (`round_money()`).
- Im Entwurf ein Vorschlag mit Häkchen (`Reminder.interest_accepted`, `PUT /api/reminders/{id}/charges` mit `interest_accepted`, Pflicht;
  409 ohne Vorschlag), mit Zeitraum und Abschnitten. Beim Festschreiben unter der Sperre frisch bis zu dessen Tag berechnet; nicht mehr
  möglich (Verzugsbeginn verworfen, Satz nicht mehr geprüft …) -> 409, nichts geschrieben. Die Nebenforderung (`InvoiceCharge` Art
  `zinsen`) trägt `period_start`, `period_end` und `calculation_json` (je Abschnitt von, bis, Hauptbetrag, Basiszinssatz, Satz, Tage,
  Zinsen exakt; Zuschlag; 365). Ausgeschaltet: nichts.
- Verwerfen des Verzugsbeginns gesperrt, solange Zinsen gelten (wie bei der Pauschale). Bucht jemand später eine Zahlung mit früherem
  Eingang, bleibt die gebuchte Zinsforderung; die Karte zeigt "Mit dem Stand heute ergäben sich …" (`recalculated()`).

**Punkt 5 -- Zahlungen auf Nebenforderungen nach § 367 BGB** (`app/payments.py`):
- `PaymentAllocation` Art `nebenforderung` mit `charge_id` (Nebenforderung derselben Rechnung, Gegenbuchung mit derselben `charge_id`).
  Sie mindert die Nebenforderung (offen = Betrag − Zahlungen, `charge_paid()`, `open_charges()`), nicht den Zahlstand der Rechnung; sie
  zählt zum zugeordneten Teil der Zahlung (`payment_rest()`, "Nicht zugeordnet").
- Vorschlag (`proposal()`): je Rechnung zuerst ihre offenen Nebenforderungen -- Kosten (Gebühr, Pauschale), dann Zinsen, je Art die älteste
  zuerst (`open_charge_rows()`) --, dann der Rechnungsbetrag; über die Rechnungen des Auftrags weiter die älteste zuerst. Skonto nur am
  Rechnungsbetrag, "Betrag passt genau" zählt die Nebenforderungen mit. `GET /api/customers/{id}/open-invoices` listet auch Rechnungen mit
  nur offenen Nebenforderungen.
- Buchen (`POST /api/payments`, `POST /api/payments/{id}/allocations`, Zeile mit `charges: [{charge_id, amount}]`), unter derselben Sperre
  (Aufträge, dann Zahlung): nur eine geltende Nebenforderung derselben Rechnung (409 "gehört nicht zur Rechnung", unbekannt 404,
  gegengebucht 409), höchstens ihr offener Rest (409 "Überbuchung der Nebenforderung"), mit dem Rest der Zahlung zusammen gezählt,
  jede Nebenforderung höchstens einmal je Buchung. Gebucht wird, was das Büro bestätigt -- auch abweichend.
- Gegenbuchung einer Nebenforderung erst nach gelöster Zuordnung (409); ebenso der Ersatz einer Mahnung, deren Nebenforderung bezahlt ist
  (409 "lässt sich nicht ersetzen"). "Zahlung zurücknehmen" bucht die Zuordnungen auf Nebenforderungen mit gegen.
- Eine festgeschriebene Mahnung geht nach einer Zahlung auf eine Nebenforderung nicht mehr hinaus (ihre Nebenforderungen stimmen nicht mehr).
- Oberfläche: Zahlungsdialog mit einer Zeile je offener Nebenforderung vor der Rechnung, Betrag vorbelegt mit Rechnungsbetrag +
  Nebenforderungen, Warnung bei Überbuchung einer Nebenforderung; Karte "Nebenforderungen und Verzug" mit "gezahlt … · offen …" und "darauf
  gezahlt"; "Zahlungseingang buchen" auch bei nur offenen Nebenforderungen. Die Kundenakte ordnet ihren Rest weiter nur Rechnungsbeträgen zu.

**Punkt 6 -- Rechtstexte** (`app/dunning_texts.py`, `DunningLegalText`): drei feste Schlüssel `verzug`, `zinsen`, `pauschale`; Text mit
Platzhaltern (`{verzugsbeginn}`; `{prozentpunkte}`, `{zinsen_von}`, `{zinsen_bis}`; `{pauschale}`, unbekannte gewarnt), "geprüft am/durch"
wie die Klauseln (geänderter Text hebt die Prüfung auf). `GET /api/dunning-legal-texts` ab buero_auftrag, `PUT …/{key}` nur Admin. Die
Mahnung druckt einen Text nur geprüft und nur, wenn sie das Thema nennt (`legal_topics()`): Verzug = bestätigter Verzugsbeginn bis zum
Mahndatum, Zinsen bzw. Pauschale = eine solche Zeile in der Aufstellung; nur eingeschaltet. Ungeprüft: Warnung im Entwurf und in der
Liste ("Der Rechtstext „Verzug“ ist nicht geprüft – er wird nicht gedruckt …"). Beim Festschreiben in der Aufstellung eingefroren.

**Aufstellung Format 3** (`amounts_snapshot()`): je geltender Nebenforderung Betrag, darauf gezahlt, bei Zinsen die Abschnitte;
`charges_paid`, `charges_open` = Summe − gezahlt, `total`; die gedruckten Rechtstexte. PDF: unter jeder Zinszeile ihre Abschnitte, eine Zeile
"abzüglich Zahlungen auf Nebenforderungen", nach der Aufstellung die Rechtstexte. Format 1/2 bleiben lesbar.

**Migration `a4c9e2f7b815`** (ändert keine Daten): Tabellen `base_interest_rates`, `dunning_legal_texts`; Spalten
`invoice_charges.period_start/period_end/calculation_json`, `reminders.interest_accepted` (server_default 0),
`payment_allocations.charge_id` (FK, Index). `downgrade()` verweigert bei Verzugszinsen, Zuordnungen auf Nebenforderungen, übernommenen
Zinsen, Aufstellung Format 3, Basiszinssatz oder Rechtstext.

**Rollen**: Basiszinssatz und Rechtstexte schreiben nur Admin, lesen ab buero_auftrag; Zinsen übernehmen, Zahlungen auf Nebenforderungen ab
buero_auftrag; der Monteur nirgends (403). Historie: Basiszinssatz und Rechtstext je Änderung (`app/audit.py`).

### Festlegungen 1.8.81 (alle bestätigt am 12.10.2026, Nr. 1–18; Vorgabe R4-Befund, siehe `befund-vor-echtbetrieb.md`)

1. **Basiszinssatz je Halbjahr**: "gültig ab" nur 1. Januar oder 1. Juli, eine Zeile gilt genau ihr Halbjahr -- auch ein unveränderter Satz
   muss für jedes Halbjahr eingetragen werden, sonst "fehlt ein Zeitraum".
2. **Prüfung wie bei den Klauseln**: ändert sich der Satz ohne neue Prüfangabe, fällt sie weg; nur ungeprüfte Sätze lassen sich löschen;
   gebuchte Zinsen behalten den Satz ihrer Berechnung.
3. **Zinsbeginn bei abweichend festgelegtem Verzugsbeginn**: der Tag danach (wie beim Zugang der Mahnung); nur "30 Tage" beginnt am
   Verzugsbeginn selbst.
4. **Eingangstag**: der gezahlte Teil ist ab dem Eingangstag zinsfrei (der neue Abschnitt beginnt an ihm).
5. **Verzinst wird der mahnfähige Betrag** (offen − Einbehalt); Zahlungen auf Nebenforderungen mindern ihn nicht; auf Nebenforderungen
   keine Zinsen (§ 289 BGB).
6. **Zinsen sind ein Vorschlag mit Häkchen** wie Gebühr und Pauschale, beim Festschreiben bis zu dessen Tag neu berechnet; ist der
   Vorschlag dann nicht mehr möglich, 409 (nicht still ohne Zinsen).
7. **Anschluss**: ab dem Tag nach dem spätesten Ende geltender Zinsen; eine gegengebuchte Zinsforderung öffnet ihren Zeitraum (die nächste
   Mahnung rechnet ihn neu). Wird eine mittlere gegengebucht, bleibt deren Zeitraum offen (Lücke).
8. **Später gebuchte Zahlung mit früherem Eingang**: die gebuchten Zinsen bleiben; die Karte zeigt die Neuberechnung, Korrektur per
   Gegenbuchung.
9. **Verzugsbeginn verwerfen** gesperrt, solange Zinsen oder die Pauschale gelten.
10. **"Vorweg" 1 auch innerhalb einer Mahnung**: übernimmt sie die Pauschale, keine Gebühr daneben (409). Gebühren früherer Mahnungen werden
    nicht auf die Pauschale angerechnet (Nebenbefund 2).
11. **Storno**: offene Nebenforderungen gegenbuchen, bezahlte erst über die Zuordnung lösen; Ersatz einer Mahnung mit bezahlter
    Nebenforderung 409.
12. **§ 367 BGB als Vorschlag**, keine Sperre (§ 366 Abs. 1: eine Tilgungsbestimmung des Kunden geht vor); je Art die älteste zuerst; Skonto
    nur am Rechnungsbetrag. Zahlungen auf Nebenforderungen nur über die Rechnungsseite (Kundenakte: nur Rechnungsbeträge).
13. **Finanzen**: "Bezahlt (gesamt)" zählt weiter nur Zahlungen auf Rechnungsbeträge; Zahlungen auf Nebenforderungen gelten als zugeordnet
    (nicht im Rest "Nicht zugeordnet").
14. **Rechtstexte**: gedruckt nur eingeschaltet, geprüft und zum Thema der Mahnung (Verzug: bestätigter Verzugsbeginn bis zum Mahndatum);
    beim Festschreiben eingefroren; Platzhalter je Text wie oben.
15. **Aufstellung Format 3**: jede geltende Nebenforderung mit vollem Betrag, alle Zahlungen darauf als eine Zeile "abzüglich Zahlungen auf
    Nebenforderungen", die Zinsabschnitte unter ihrer Zeile.
16. **Rückweg der Migration** verweigert auch bei Basiszinssatz oder Rechtstext (beides ginge verloren).
17. **Regel 27**: in public erlaubt nur CREATE/DROP SCHEMA, `pg_terminate_backend` und die Anfragen des Treibers beim Verbinden; jede
    Weitergabe von `DATABASE_URL` an einen Kindprozess unter `tests/` geht durch `pg_url_pruefen()`, auch SQLite.
18. **Rollen** wie oben: schreiben von Basiszinssatz und Rechtstexten nur Admin, alles andere ab buero_auftrag.

### Tests und Prüfung

- Neu `tests/test_v384_verzugszinsen.py` (53): Vorweg 1 (kein Gebührvorschlag nach gebuchter Pauschale mit Hinweis, Übernehmen 409,
  Festschreiben am Entwurf vorbei 409; nicht beides in derselben Mahnung -- Router 409/Senden 409; die Pauschale einer zu ersetzenden
  Mahnung sperrt die Gebühr nicht); Vorweg 2 (Storno anlegen 409 mit Grund, Router 409, Storno-Entwurf von vor der Nebenforderung nicht
  festschreibbar, nach Gegenbuchung frei; Zahlung auf Nebenforderung sperrt wie jede Zuordnung); Festlegung 1.8.80 Nr. 2 (`pending.charges`,
  `replaces`); Nr. 13; Basiszinssatz (Regeln, nur Admin -- vier Rollen, Router 409/422/404, schreibt keine Zeile eines Auftrags);
  Zinsen (Zinsbeginn je Grundlage; Abschnitte exakt mit Zahlung und Halbjahreswechsel, einmal gerundet 257,94 € statt 257,95 €;
  Schaltjahr durch 365; 5/9 Punkte; fehlendes und ungeprüftes Halbjahr; ohne Verzug; nur mahnfähiger Betrag; vom Tag nach dem Zugang bis
  zum Mahndatum, Nebenforderung mit eingefrorener Berechnung, Format 3, PDF; nicht übernommen; Anschluss und nach Gegenbuchung wieder ab
  Zinsbeginn; **Angriffe** Übernehmen ohne Verzug bzw. Satz, Satz beim Festschreiben ungeprüft -> 409 ohne Nummer; frisch beim
  Festschreiben; Verwerfen gesperrt; Hinweis bei später gebuchter Zahlung; ausgeschaltet); § 367 (Kosten, Zinsen, Rechnung; älteste
  Rechnung zuerst; Buchung mindert die Nebenforderungen, nicht die Rechnung, Rest und "nicht zugeordnet", Zurücknehmen öffnet sie wieder;
  **Angriffe** Nebenforderung einer anderen Rechnung, Rechnung eines anderen Kunden, unbekannt 404, gegengebucht, Gegenbuchung,
  Überbuchung der Nebenforderung und der Zahlung -- je nichts geschrieben; doppelte Nebenforderung; Gegenbuchung erst nach gelöster
  Zuordnung; Ersatz mit bezahlter Nebenforderung 409; Mahnung geht nach Zahlung auf eine Nebenforderung nicht mehr hinaus; offene Rechnungen
  mit nur Nebenforderungen; Router 200/404/422/409); Rechtstexte (Regeln; ungeprüft nicht gedruckt mit Warnung, geprüft gedruckt mit
  Platzhaltern; nur genannte Themen, ausgeschaltet keine; eingefroren); Pflichtfeld `interest_accepted` 422, Monteurin 403; **Rundgang mit
  Beobachter**: Zinsen übernehmen, Festschreiben mit Zinsen, Zahlung auf eine Nebenforderung schreiben nur unter der Sperre der Auftragszeile.
- Neu `tests/test_v384_verzugszinsen_pg.py` (10, gegen PostgreSQL): zwei Zahlungen auf dieselbe Nebenforderung -> eine; Gegenbuchung gegen
  Zahlung in beiden Reihenfolgen; Festschreiben mit Zinsen gegen Verwerfen des Verzugsbeginns in beiden Reihenfolgen; Festschreiben mit
  Gebühr gegen Storno in beiden Reihenfolgen; Festschreiben wartet auf eine Zahlung auf eine Nebenforderung und zeigt sie; derselbe
  Basiszinssatz zweimal -> einer; derselbe Rechtstext zweimal zum ersten Mal -> eine Zeile.
- Neu `tests/test_v384_verzugszinsen_migration.py` (2, davon 1 gegen PostgreSQL): Bestand auf `8e2f4b6d1c97` (Auftrag, Rechnung, Mahnung
  Format 2, Gebühr, Pauschale samt Gegenbuchung, Verzugsbeginn, Zahlung) -> hoch: jede Zeile unverändert, neue Spalten leer; runter: exakt
  wie vorher; wieder hoch, Basiszinssatz bzw. Zahlung auf die Gebühr -> Rückweg verweigert, nichts geändert.
- Neu `tests/test_v384_pg_nicht_public.py` (5, davon 1 gegen PostgreSQL), siehe Vorweg 3.
- **Angepasst, weil die Vorgabe die Erwartung überholt**: `test_v383` (Gebühr und Pauschale nicht mehr in derselben Mahnung -- die
  Summen-, Ersatz-, Router- und Rundgang-Tests nehmen eine von beiden; der Ersatz-Test legt die Gebühr der alten Mahnung als Bestand von
  1.8.80 an; Format 3; `interest_accepted` im PUT; Vorschlag der Gebühr mit `block`; die schreibenden Routen des Routers um Basiszinssatz und
  Rechtstexte), `test_v382` (Format 3, `interest_accepted`). Strukturtests: `test_v364` (`dunning_legal_texts.text_key`), `test_v373`
  (`lines.charges.charge_id` als GEPRUEFT in `payments._check_charge_lines`). Kindprozesse mit `pg_url_pruefen()`: `test_v380::_alembic`,
  `test_v345::_start`, `test_v252`. Klicktest `klicktest_nebenforderungen.py`: Gebühr und Pauschale in derselben Mahnung -- seit 1.8.81
  veraltet, jetzt nur die Pauschale mit gesperrter Gebühr.
- **Gegenproben** (Regel 24): 44 von 44 rot -- keine Gebühr neben gebuchter Pauschale (1), nicht beides in einer Mahnung (1), beim
  Festschreiben (1), Storno mit offenen Nebenforderungen (2, davon 1 PostgreSQL), Zahlung auf Nebenforderung sperrt das Storno (1),
  Ersatz nennt die Gegenbuchungen (1), Basiszinssatz: Halbjahr (1), Prüfung fällt weg (1), nur Admin (1); Zinsen: fehlendes Halbjahr (1),
  nur geprüfte Sätze (2), Zinsbeginn (2), einmal gerundet (1), durch 365 im Schaltjahr (1), Eingangstag zinsfrei (1), 5/9 Punkte (1),
  mahnfähiger Betrag (1), Anschluss (2), beim Festschreiben neu geprüft (2, davon 1 PostgreSQL), Übernehmen nur mit Vorschlag (1),
  ausgeschaltet (1), Verwerfen gesperrt (2, davon 1 PostgreSQL); § 367: Kosten vor Zinsen (1), Nebenforderungen vor der Rechnung (2);
  Zahlung: derselben Rechnung (2, davon der Strukturtest Regel 25), nur geltende (1), keine Überbuchung (2, davon 1 PostgreSQL), Rest (1),
  nicht zugeordnet (1), Gegenbuchung erst nach gelöster Zuordnung (2, davon 1 PostgreSQL), Ersatz mit bezahlter Nebenforderung (1),
  Gegenbuchung der Zuordnung trägt die Nebenforderung (2), offen = Betrag − Zahlungen (1), offene Rechnungen nur mit Nebenforderungen (1);
  Rechtstexte: ungeprüft nicht gedruckt (1), nur genannte Themen (1), eingefroren (1), Prüfung fällt weg (1); Sperre der Auftragszeile
  bei Zahlungen auf Nebenforderungen (1, PostgreSQL); Migration: Rückweg verweigert (1); Regel 27: Wächter (1, PostgreSQL), URL der
  Kindprozesse (1), Strukturtest Kindprozesse (1), Strukturtest Engines (1). Je Probe mit `-x` -- die Zahl in Klammern nennt die
  angegebenen Tests, rot wurde jeweils mindestens der erste. Jede Datei byte-genau zurück (SHA-256), kein Marker unter `app/`,
  `alembic/` und `tests/`. Probe 41 (Wächter) lief auffällig schnell -- einzeln wiederholt: rot mit "DID NOT RAISE", der richtige Grund.
- Migration `a4c9e2f7b815`: Wegwerf-SQLite hoch, `current` head, `check` ohne Unterschied, runter, wieder hoch; leeres Wegwerf-Schema der lokalen PostgreSQL ebenso; dazu die
  Proben mit Bestand (SQLite und PostgreSQL).
- Klicktests: neu `klicktest_verzugszinsen.py` 27/27 (die ersten Läufe 26/27: eine Prüfung im Skript hatte doppelte Klammern in einem
  Nicht-f-String -- Skriptfehler, behoben; die Tabelle des Basiszinssatzes lief in der Einstellungskarte über -- Prüfangaben übereinander,
  danach ohne Scrollbalken). `klicktest_nebenforderungen.py` angepasst (siehe oben). **Alle Klicktests** (`scripts/klicktest_alle.py`,
  Arbeitskopie, Regel 26): 50 von 50 wie erwartet, 11:50 min; weil sich währenddessen drei Vorlagen noch änderten (siehe Suite), die
  sechs Klicktests, die sie öffnen und vorher liefen, auf dem Endstand noch einmal: 6 von 6.
- Volle Suite (mit den opt-in-Tests gegen PostgreSQL, Arbeitskopie, in drei Teilen parallel, längster 14:01 min): 3650 grün, 2 rot, 7
  erwartet fehlgeschlagen (1a, 1b, 1d). Beide rot waren echte Funde in der neuen Oberfläche: `test_v054` (die Einstellungsseite lädt
  Bereiche nur mit `Promise.allSettled`, der neue Lader für Basiszinssatz und Rechtstexte nahm `Promise.all` -- ein Fehlschlag hätte
  beide Bereiche geleert) und `test_v377` (die Rechnungsseite darf "festschreiben" nicht enthalten, das neue Datenattribut
  `data-ersetzt-beim-festschreiben` tat es -- jetzt `data-ersatz-hinweis`). Behoben; danach die 49 Testdateien, die die geänderten
  Vorlagen lesen, auf dem Endstand: 731 grün. Danach nur Doku geändert.

### Nebenbefunde (nur gemeldet)

1. **Zinsen und Nebenforderungen ohne mahnfähigen Betrag**: beides entsteht bzw. wird angemahnt nur mit einer Mahnung, und eine Mahnung
   gibt es nur mit mahnfähigem Rechnungsbetrag. Bucht das Büro eine Zahlung über den Rechnungsbetrag ganz auf die Rechnung (statt nach
   § 367 erst auf Kosten und Zinsen), lassen sich Zinsen bis zur Zahlung und offene Nebenforderungen nicht mehr anmahnen. Naheliegend: eine
   Forderungsaufstellung bzw. Mahnung nur für Nebenforderungen.
2. **Gebühren vor der Pauschale** (§ 288 Abs. 5 S. 3 BGB): eine Mahngebühr einer früheren Mahnung bleibt neben einer später gebuchten
   Pauschale stehen, sie wird nicht angerechnet (seit 1.8.81 nur: keine neue Gebühr neben der Pauschale).
3. **Finanzen und Dashboard** zeigen offene Nebenforderungen nicht -- nur die Rechnungsseite.
4. **Kundenakte**: "Rest zuordnen" bedient nur Rechnungsbeträge, Nebenforderungen nur über den Dialog der Rechnungsseite.
5. **Zinsen bei später gebuchter Zahlung mit früherem Eingang**: nur ein Hinweis an der Nebenforderung (Festlegung 8), keine Sperre der
   Mahnung.
6. Unverändert: Rechnung per E-Mail auch bezahlt oder storniert, Mahnhistorie auf der Rechnungsseite nur bei "versendet" (1.8.77 Nr. 7),
   Probebelege entfernen (1.8.77 Nr. 8), Mahnwesen lädt alle Mahnungen (1.8.79 Nr. 3), Mahnung per E-Mail ohne Sperre (1.8.79 Nr. 2,
   1.8.80 Nr. 4).
