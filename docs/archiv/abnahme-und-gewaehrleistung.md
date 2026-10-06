# Abnahme und Gewährleistung (Stufe 2c)

Stufe 2c des Stufe-2-Vorhabens (2a Unterschrift/Zweck/Versand: `modul-checklisten.md`; 2b Vertragsgrundlage, Vertrag,
Beteiligte, Anzeigen: `vertragsgrundlage-und-vertrag.md`). Kern, kein Modul-Umschalter. Vor jeder Änderung an Abnahme,
Gewährleistungsdauer, Gewährleistungsende oder der Garantie Dritter an der Dachfläche diese Datei lesen (Regel 14).

Grundlage ist der Befund vom 03.10.2026 (Stufe 2c, nur Befund, ohne Änderung): außer einem leeren Checklisten-Zweck
"abnahme", einem von Hand gepflegten Feld "Gewährleistung bis" an der Dachfläche und der Schlussrechnung als eigener
Art gab es nichts zu Fertigstellung, Abnahme, Gewährleistung, Vertragsstrafe oder Sicherheitseinbehalt.

---

## Etappenplan

Je Version ein Commit (Regel 13), `VERSION` + `CHANGELOG.md` + `backup_windows.ps1` (Regeln 8/9).

| Runde | Version | Inhalt | Stand |
|---|---|---|---|
| **2c-1** | 1.8.46, 1.8.47 | Fundament: Regel-20-Test auch für Spaltenvorgaben, Datengrenze (Strafe, Einbehalt), Leistungsart und Gewährleistungsdauer am Auftrag, Abnahme (unveränderlich, Verwerfen, Historie), Gewährleistungsende abgeleitet an Auftrag/Objekt/Dachfläche, Garantie Dritter an der Dachfläche mit Teil-Update, Abgleich gesperrt nach Abnahme (1.8.46); Vollmacht zur Abnahme am Beteiligten, Begründung und Vorschau nach der ersten Abnahme, Nachweis "förmlich: Beleg, sonst Beleg oder Begründung", "Gewährleistung regulär bis" (1.8.47) | erledigt |
| **2c-2a** | 1.8.48–1.8.50 | Vorweg: Prüfstatus neben jedem Gewährleistungsende (eine Funktion, `logger.error` bei Abweichung), Siegel des Verwerfens, Fassung des Prüfsummenformats (1.8.48); Mängel aus der Abnahme mit Haltung, Status, Freigabe, Verlauf, Aufgabe und "Nachbesserung regulär bis" (1.8.49); Platzhalter `{gewaehrleistung}`, Festschreiben erst mit Dauer, danach Dauer und Leistungsart gesperrt (1.8.50) | erledigt |
| **2c-2b** | 1.8.51–1.8.54 | Vorweg: Sperre an eine gültige Fassung binden (nur gemeldet -- es gibt kein Zurückziehen einer Fassung), Belege am Mangel nachreichen, Aufgabentitel mit Kurzfassung, CLAUDE.md `update.sh`/`backup.sh` (1.8.51); Monteur-Sicht auf Mängel in `/mobil` mit Positivliste, "beseitigt" melden mit Foto, idempotent über `client_uuid` (1.8.52); Nacharbeiten: Aufgaben-Mails ohne Inhalt (1.8.53), Aufgabe folgt dem Status des Mangels, Hinweis des Monteurs zur Meldung, `update.sh` probt selbst gegen die Spielwiese (1.8.54) | erledigt; Zurückziehen einer Fassung am 05.10.2026 entschieden, noch nicht gebaut (siehe "Umsetzung 1.8.55", Punkt 0c) |
| **2c-2c** | 1.8.55–1.8.58 | Unterschriften in Checklisten härten, Fundament für das Abnahmeprotokoll. Vorweg: "zurück auf offen" mit neuer Frist, Regel 24 (Marker GEGENPROBE), Entscheidung zum Zurückziehen einer Vertragsfassung ins Archiv (1.8.55); Pflichtfelder oberhalb einer Abschnittsunterschrift, eine gemeinsame Prüfung des Unterschriftsbilds (1.8.56); Unterzeichner je Unterschriftsfeld mit Siegel (1.8.57); Zeichenfläche nach Drehen neu vermessen (1.8.58) | erledigt; Festlegungen 1.8.55–1.8.58 bestätigt (05.10.2026, Vorgabe 2c-2d) |
| **2c-2d** | 1.8.59–1.8.61 | Abnahmeprotokoll als Checkliste, Plan unten ("Etappenplan 2c-2d"). Vorweg: Person und Funktion beim Unterzeichner Auftraggeber, Vollmacht-Kennzeichnung mit Art, Veröffentlichen prüft Pflichtfelder, die der Unterzeichner nicht ausfüllen darf (1.8.59); Feldtyp "Mängel" (1.8.60); Zweck "abnahme" mit Systemfeldern und Startvorlage (1.8.61); Folge "Abnahme anlegen" nach der Unterschrift des Auftraggebers (1.8.62); Mängel und Erklärungen auf Seite und PDF (1.8.63) | Punkte 0–2 erledigt (1.8.59–1.8.61); Punkte 3 und 4 geplant, nicht gebaut -- siehe "Offen aus 2c-2d" bei "Umsetzung 1.8.61" |

Nach jeder Runde die Spalten "Version"/"Stand" nachziehen und unten einen Abschnitt "Umsetzung 1.8.x" ergänzen.

---

## Umsetzung 1.8.46 (03.10.2026) -- Runde 2c-1: Fundament Abnahme und Gewährleistung

Betreibervorgabe (gekürzt): (1) Regel-20-Test findet auch Spaltenvorgaben wie `default=date.today`, Funde in eine
Ausnahmeliste, die nur kürzer werden darf; (2) Datengrenze: Wortteile `strafe`, `penalty`, `einbehalt`, `retention`;
(3) Auftrag: Leistungsart (Bauwerk / sonstige Arbeiten) und Gewährleistungsdauer in Monaten und Tagen, Vorschlag
`vob_b` 48/24, `bgb` und `bgb_vob_c_4_5` 60/24 Monate mit Fundstelle, Übernahme nur bewusst, Abweichung mit Begründung,
sonst "nicht festgelegt"; (4) Tabelle Abnahme (Art, Datum ohne Vorgabe, Umfang mit Dachflächen nur aus dem Objekt des
Projekts, Ergebnis mit zwei Pflichtfragen ohne Vorgabe, "mit Vorbehalten" nur abgeleitet, Einwendungen, Erklärende mit
Vollmacht-Warnung, Beleg oder bei "schlüssig" Pflicht-Begründung, unveränderlich, Verwerfen mit Begründung,
Änderungshistorie, ab `buero_auftrag`, Monteure nichts); (5) Gewährleistungsende nur abgeleitet nach § 188 Abs. 2 und 3
BGB, Tests mit 29.02. und 31.08., Anzeige an Auftrag, Objekt und Dachfläche, nicht bei "verweigert"; (6)
`RoofArea.warranty_until` wird Garantie Dritter, Speicherweg der Dachfläche Teil-Update; (7) Abgleich mit dem Angebot
gesperrt, sobald eine nicht verworfene Abnahme besteht. Angriffstests mit Gegenprobe, wichtige Tests gegen PostgreSQL.

### Punkt 1: Regel 20 auch für Spaltenvorgaben

- `tests/test_v316_berlin_time.py::local_clock_references()`: `date.today`, `datetime.today`, `datetime.now` als Verweis
  ohne Aufruf (Spaltenvorgabe, `onupdate`, `default_factory`, Sortierschlüssel), auch über Aliasse; Ort als
  `Klasse.feld` bzw. umgebende Funktion. Ein Aufruf in einer lambda bleibt Sache von `local_clock_calls()`.
- `BEKANNTE_VORGABEN` (6, je mit Grund): `QuoteDocumentMeta.quote_date`, `Order.order_date`, `Invoice.invoice_date`,
  `Reminder.reminder_date`, `ServiceReport.performed_at` (alle `app/models.py`), `OrderCreateFromQuote.order_date`
  (`app/schemas.py`). Ein neuer Fund ist rot, ein Eintrag ohne Fund ebenso. Abhilfe je Fall: Vorgabe weg, Datum beim
  Anlegen mit `berlin_today()` setzen -- nicht Teil dieser Runde.

### Punkt 2: Datengrenze

`VERBOTENE_WORTTEILE` um `strafe`, `penalty`, `einbehalt`, `retention` ergänzt, dazu (Punkt 6) `garantie`, `guarantee`:
nach der Umbenennung von `warranty_until` wäre die Garantie Dritter sonst nicht mehr verboten (der Monteur bekam sie seit
1.8.22 nicht). Kein heutiger Schlüssel einer Monteur-Antwort enthält einen der neuen Wortteile.

### Punkt 3: Leistungsart und Gewährleistungsdauer (`app/warranty.py`)

- `orders.work_kind` ("bauwerk"/"sonstige", Schlüssel nie umbenennen), `orders.warranty_months`,
  `orders.warranty_days`; alle leer = "nicht festgelegt", auch für den Bestand (die Migration übernimmt nichts).
- `PROPOSALS[(Vertragsgrundlage, Leistungsart)]` = (Monate, Tage, Fundstelle): VOB/B § 13 Abs. 4 Nr. 1 (Bauwerk 48,
  sonst 24), BGB § 634a Abs. 1 Nr. 2 bzw. Nr. 1 (60 bzw. 24) für `bgb` und `bgb_vob_c_4_5`. Ein `assert` verlangt
  einen Vorschlag je Vertragsgrundlage.
- `set_order_warranty()` (`PUT /api/orders/{id}/warranty`, alle Felder Pflicht, `reason` darf null sein): entspricht die
  Dauer dem Vorschlag für Grundlage und Leistungsart, ist das die Übernahme; sonst Begründung Pflicht (422). Historie
  `order_warranty_changes` mit Grundlage und Vorschlag dieses Zeitpunkts (`GET /api/orders/{id}/warranty-changes`);
  zusätzlich die Änderungshistorie des Auftrags (Feldnamen "Leistungsart", "Gewährleistung (Monate/Tage)").
- `order_to_dict()` liefert `work_kind_label`, `warranty_text`, `warranty_set`, `warranty_follows_proposal` (gegen den
  Vorschlag der HEUTIGEN Grundlage) und `warranty_proposals` je Leistungsart; nur in `OrderOut` (Büro).
- Auftragsseite, Karte "Gewährleistung" (`app/templates/_abnahme.html`): Stand, Leistungsart ohne Vorauswahl, Vorschlag
  mit Fundstelle und "Vorschlag übernehmen", "Abweichende Dauer festlegen" mit Pflicht-Begründung, Hinweis bei
  Abweichung vom heutigen Vorschlag, Historie.

### Punkt 4: Abnahme (`app/acceptances.py`, `app/routers/acceptances.py`)

- Tabellen `order_acceptances` (Art, Datum, Umfang, Beschreibung, Ergebnis, `reservation_defects`/`reservation_penalty`,
  Einwendungen, Erklärende, Begründung der schlüssigen Abnahme, `property_id`, `content_sha256`, erfasst/verworfen),
  `order_acceptance_roof_areas` (Name als Schnappschuss, UNIQUE je Abnahme und Dachfläche), `order_acceptance_files`
  (`nachweis`/`vollmacht`, SHA-256). Mehrere Abnahmen je Auftrag.
- Erfassen: `POST /api/orders/{id}/acceptances` als multipart (`data` = JSON nach `OrderAcceptanceCreate`, `files`);
  Pydantic `extra="forbid"`, Vorbehalte als `StrictBool` (ein "false" als Text ist 422, keine stille Umdeutung).
  Regeln in `create_acceptance()` (400, nichts gespeichert, keine Datei liegen gelassen).
- Unveränderlich: ORM-Sperre (`ArchiveImmutableError` für Abnahme, Dachflächen und Belege, Ändern und Löschen);
  Belege exklusiv angelegt und schreibgeschützt unter `DACHKONZEPTE_ACCEPTANCE_FILE_ROOT` (Vorgabe
  `ERP_DATA_DIR/acceptance_documents`, in `.env.example`); `content_sha256` über den ganzen Inhalt samt Prüfsummen der
  Belege -- jede Anzeige rechnet nach ("Inhalt weicht ab", Beleg "abweichend"/"fehlt", Auslieferung dann 409/410).
- Verwerfen: `POST /api/order-acceptances/{id}/discard` mit Pflicht-Begründung, bedingtes UPDATE (genau einmal, sonst
  409) an der ORM-Sperre vorbei, eigene Zeile in der Änderungshistorie ("verworfen", mit Begründung); das Anlegen steht
  dort mit dem ganzen Inhalt ("angelegt"). Die Liste der Auftragsseite zeigt verworfene Einträge gekennzeichnet.
- Rechte: alle Routen `require_min_role(ROLE_OFFICE_AUFTRAG)`, Monteure 403; der Datengrenze-Rundgang ruft jede
  GET-Route als Monteur (403) und als Admin (200 mit Inhalt) auf.
- Folgen an anderer Stelle: eine in einer Abnahme genannte Dachfläche lässt sich nicht mehr löschen (400, archivieren);
  ein Beteiligter, der eine Abnahme erklärt hat, nicht mehr aus dem Projekt entfernen (409).
- Auftragsseite, Karte "Abnahme" und Dialog (`_abnahme.html`): ohne jede Vorauswahl, Dachflächen nur aus dem Objekt,
  Vollmacht-Warnung beim Wählen des Beteiligten, Verwerfen über ein eingeblendetes Feld (kein `prompt()`, Regel 4).

### Punkt 5: Gewährleistungsende

- `warranty_end(Abnahmedatum, Monate, Tage)`: § 187 Abs. 1 BGB (Abnahmetag zählt nicht), § 188 Abs. 2 (Tag mit
  derselben Zahl im letzten Monat), § 188 Abs. 3 (fehlt er, Monatsletzter) -- über `app/date_utils.py::add_months()`;
  Tage danach. Tests u. a. 29.02.2024 + 60 Monate = 28.02.2029, + 48 = 29.02.2028; 31.08.2025 + 18 = 28.02.2027;
  31.08.2026 + 1 = 30.09.2026.
- Nie gespeichert. Nur bei einer nicht verworfenen, abgenommenen Abnahme; ohne festgelegte Dauer "nicht berechenbar".
- Auftrag: je Abnahme in der Liste. Objekt (`GET /api/properties/{id}/acceptance-warranties`): Karte "Gewährleistung
  aus Abnahmen" (alle Abnahmen am Objekt beim Erfassen) und in der Dachflächenliste "Gewährleistung bis" (spätestes
  Ende der Abnahmen, die die Fläche nennen). Dachfläche (`GET /api/roof-areas/{id}/acceptance-warranties`): die
  Abnahmen, die sie nennen, dazu ein Hinweis auf Abnahmen am Objekt ohne Dachflächen.

### Punkt 6: Garantie Dritter an der Dachfläche

- Spalte `roof_areas.warranty_until` heißt `third_party_guarantee_until` (Werte bleiben), Beschriftung "Garantie Dritter
  (Hersteller oder Fremdfirma) bis" bzw. "Garantie Dritter bis" (Dachflächen-, Objekt- und Kundenseite).
- `PUT /api/roof-areas/{id}` ist ein Teil-Update (`RoofAreaUpdate(PartialUpdate)`, `NOT_NULL` name,
  `update_roof_area(**changes)`); aus `BEKANNT` des Strukturtests gestrichen, in `REPARIERT_SPAETER`.
- Objekt-, Dachflächen- und Kundenseite lesen abgelehnte Antworten jetzt über `fehlerText()` (Architekturentscheidung
  1.8.35: eine angefasste Seite stellt um).

### Punkt 7: Abgleich gesperrt

`sync_order_from_source_quote()` ruft nach der Vertragssperre `ensure_no_active_acceptance()`: Sperre der
Auftragszeile, `AcceptanceExistsError` (409), solange eine nicht verworfene Abnahme besteht. Erfassen und Verwerfen
sperren dieselbe Zeile. Auftragsseite: Karte "Quellangebot geändert" ohne Knopf mit Erklärung; nach dem Verwerfen der
letzten Abnahme wieder möglich.

### Festlegungen (nicht vorgegeben, bitte bestätigen)

Stand nach der Rückmeldung vom 04.10.2026: **bestätigt** 4 (nur "erst Monate, dann Tage"), 6, 9, 12, 14 und
`garantie`/`guarantee` (Punkt 2); **geändert in 1.8.47** 3, 10, 11 (siehe "Umsetzung 1.8.47"); **offen** 1, 2, 5, 7, 8, 13,
15 und aus 4 der Teil "§ 193 BGB nicht angewandt".

**Stand 05.10.2026 (Vorgabe 2c-2a): alle Festlegungen aus 1.8.46 und 1.8.47 bestätigt** -- auch die bis dahin offenen
1, 2, 5, 7, 8, 13, 15 und "§ 193 BGB nicht angewandt" aus 4; 3, 10 und 11 in der Fassung von 1.8.47.

1. **Leistungsart nur zusammen mit der Dauer**: eine Festlegung ist immer Leistungsart + Monate + Tage. Abweichung
   heißt: andere Dauer als der Vorschlag für die Grundlage des Auftrags. Eine Begründung bei der Übernahme ist erlaubt
   und wird gespeichert. 0 Monate und 0 Tage sind keine Festlegung; Monate 0–360, Tage 0–366; dieselben Werte noch
   einmal festzulegen wird abgelehnt.
2. **Spätere Änderung der Vertragsgrundlage ändert die Dauer nicht** -- die Karte zeigt "weicht vom Vorschlag ab".
3. **Die Dauer bleibt nach einer Abnahme änderbar** (mit Historie); das Ende jeder Abnahme folgt der aktuellen Dauer,
   es wird nicht je Abnahme eingefroren. Zu entscheiden, ob die Dauer nach der ersten Abnahme gesperrt werden soll.
4. **Fristende: erst Monate, dann Tage; § 193 BGB (Wochenende/Feiertag) nicht angewandt** -- bitte rechtlich prüfen.
5. **Abnahmedatum nicht in der Zukunft.**
6. **Keine Vorauswahl auch bei Art, Umfang, Ergebnis und Erklärenden**, nicht nur bei Datum und den zwei Fragen.
7. **Dachflächen bei Gesamt- und Teilabnahme wählbar**, archivierte nicht neu; ohne Objekt am Projekt keine. Das
   Objekt der Abnahme ist das des Projekts beim Erfassen (`property_id`) -- zieht das Projekt später um, bleibt die
   Abnahme beim alten Objekt.
8. **Beschreibung des Umfangs nur bei Teilabnahme** (bei Gesamtabnahme abgelehnt statt still verworfen).
9. **"Erklärt durch Auftraggeber" = Kunde laut Auftrag** (`Order.customer_name`), nicht der heutige Kunde des Projekts.
   Beteiligter: nur dieses Projekts, nicht archiviert; Name und Rolle als Schnappschuss.
10. **"Vollmacht" = die am Beteiligten hinterlegte Empfangsvollmacht** (Häkchen "empfangsbevollmächtigt" und Beleg mit
    stimmender Prüfsumme) -- eine andere gibt es im ERP nicht. Fehlt sie: Warnung, gespeichert wird trotzdem, der
    Eintrag trägt "ohne hinterlegte Vollmacht". Liegt sie vor, wird der Beleg als Kopie mit der Abnahme festgehalten.
    Ob sie die Abnahme umfasst, prüft das ERP nicht (eine Empfangsvollmacht ist keine Abnahmevollmacht) -- zu
    entscheiden, ob 2c-2 ein eigenes Feld "Vollmacht zur Abnahme" braucht.
11. **Nachweis**: bei förmlich und ausdrücklich mindestens ein Beleg, auch bei "verweigert"; bei schlüssig Begründung
    Pflicht, ein Beleg zusätzlich möglich; bei den anderen Arten wird eine Begründung abgelehnt. Höchstens 5 Belege, je
    15 MB, zusammen 30 MB (Speicherbudget), dieselbe Datei nicht doppelt. Eigene Ablage, nicht die Versandablage (die
    nimmt nur Dokumentarten auf, die zugestellt werden können).
12. **Abgleich auch nach einer verweigerten Abnahme gesperrt** (Wortlaut "nicht verworfene Abnahme"; auch sie hält den
    Leistungsstand fest).
13. **Gewährleistungsende auch für Teilabnahmen**, je Abnahme eines, keine Zusammenfassung zu einem Ende je Auftrag.
14. **Alles in einer Version** statt Commit nach Punkt 5: Punkt 6 benennt dieselben Spalten und Beschriftungen um, die
    Punkt 5 daneben anzeigt -- dazwischen stünden zwei "Gewährleistung" nebeneinander.
15. `created_by_user_id`/`discarded_by_user_id` **ohne Fremdschlüssel** (Benutzer löschen scheitert unter PostgreSQL
    schon an 15 Fremdschlüsseln, bekannter offener Punkt).

### Verifikation

- `tests/test_v349_abnahme_und_gewaehrleistung.py` (65 Tests, einer opt-in gegen PostgreSQL: Erfassen wartet auf einen
  laufenden Abgleich und umgekehrt, über echte Sperren in zwei Verbindungen), `test_v316` (+2), `test_v326` (+3 und
  Rundgang mit Abnahme als Admin), `test_v329`, `test_v211`, `test_v215`, `test_v325` (Feldliste) nachgezogen.
- Dieselben Dateien über das Scratchpad-Plugin gegen PostgreSQL 17 (Wegwerf-Schema je Test): grün bis auf den
  Migrationstest, der seinen Vorzustand mit rohem SQL und erfundenen Fremdschlüsseln sät (bekannte Grenze, siehe
  1.8.35) -- die Migration selbst ist eigens gegen PostgreSQL geprüft (nächster Punkt).
- Migration `e15280e3b567`: SQLite (Kommandozeile hin/zurück/hin, `alembic check`); PostgreSQL 17 im Wegwerf-Schema:
  ganze Kette bis `2798ba2fb235`, Dachfläche mit `warranty_until` per SQL, upgrade (Wert unter
  `third_party_guarantee_until`), `alembic check` sauber, über den App-Code Auftrag + Gewährleistung + Abnahme mit Beleg,
  downgrade verweigert ("1 Abnahmen, 1 Festlegungen der Gewährleistung, 1 Aufträge …"), `current` bleibt head; zweites
  leeres Schema: hin, zurück (Spalte wieder `warranty_until`, Tabellen weg), hin, `check`, `current` = head.
- Gegenproben (Skript im Scratchpad, Schutz im Code ausgehebelt, Datei byte-genau zurück): 39 von 40 rot. Grün blieb
  "Erfassen ohne die ausdrückliche Sperre der Auftragszeile" gegen PostgreSQL: der Fremdschlüssel der neuen Abnahme
  nimmt beim Einfügen selbst FOR KEY SHARE auf die Auftragszeile, das wartet ebenso auf das FOR UPDATE des Abgleichs.
  Die ausdrückliche Sperre bleibt als zweite Absicherung (sie sperrt schon vor den Prüfungen); die Gegenrichtung
  (Prüfung im Abgleich ohne Sperre) ist rot.
- Klicktest `scripts/klicktest_abnahme.py` (der erste Lauf fand einen Fehler der Oberfläche: das Feld zum Verwerfen
  stand bei jedem Eintrag offen, `display:flex` überstimmte `hidden` -- behoben, jetzt geprüft).

### Nebenbefunde 1.8.46 (nur gemeldet)

1. **Eigener Fehler beim Bauen, behoben**: ein `python -c "import app.main"` ohne `DATABASE_URL` lief gegen die lokale
   `dachkonzepte_erp.db` (Regel 16) und legte dort per `create_all()` 20 leere Tabellen an; Daten unverändert (Vergleich
   mit der Sicherung v1.8.45). Tabellen wieder entfernt, Schema danach gleich der Sicherung.
2. **Neuer Datenordner `acceptance_documents`** unter `ERP_DATA_DIR`: `backup_windows.ps1` sichert `data/` ganz; ob
   `/home/tobias/backup.sh` den ganzen Datenordner sichert, steht nicht im Repo -- bitte prüfen. **Beantwortet
   05.10.2026**: `backup.sh` sichert `erp-data` vollständig (CLAUDE.md, Serverumgebung).
3. Die Dachfläche hat weiterhin keine Änderungshistorie (`AUDITED_TYPES`, Befund 2c Nr. 7) -- die Garantie Dritter
   ändert sich ohne Spur.

---

## Umsetzung 1.8.47 (04.10.2026) -- Nachtrag zu 2c-1 nach Betreiberentscheidung

Betreibervorgabe: (1) eigenes Feld "Vollmacht zur Abnahme" am Beteiligten (Häkchen plus Beleg), die Warnung richtet sich nur
danach, eine Empfangsvollmacht genügt nicht; (2) nach der ersten nicht verworfenen Abnahme Dauer oder Leistungsart nur mit
Begründung ändern, vorher zeigen, welche Gewährleistungsenden sich verschieben; (3) Nachweis: bei "förmlich" Beleg Pflicht,
sonst Beleg oder Begründung, mindestens eins; (4) Beschriftung "Gewährleistung regulär bis" mit Hinweis "ohne Hemmung oder
Neubeginn". Bestätigt: Zuschnitt (eine Version), `garantie`/`guarantee`, Auftraggeber laut Auftrag, Abgleichsperre auch nach
"verweigert", keine Vorauswahl, Fristende erst Monate, dann Tage.

- **Vollmacht zur Abnahme** (`project_participants.acceptance_authorized`, `acceptance_poa_*`): zweite Vollmacht neben der
  Empfangsvollmacht, gleiche Regeln (Beleg nur mit gesetztem Häkchen, am Inhalt erkannt, höchstens 15 MB, Ersetzen löscht
  die alte Datei, Entfernen ausdrücklich), gleicher Ordner; `app/project_participants.py::POA_KINDS` ("empfang",
  "abnahme"), Routen `…/acceptance-power-of-attorney` (POST/GET/DELETE, Büro). Reiter "Beteiligte": drittes Häkchen und
  eigener Beleg-Block, auch im Dialog "Beteiligten hinzufügen"; die alte Zeile heißt jetzt "Empfangsvollmacht".
- **Abnahme**: festgehalten wird nur noch die Vollmacht zur Abnahme (Datei-Art `abnahmevollmacht`); die Warnung ("ohne
  Vollmacht zur Abnahme") richtet sich nach dieser Datei. Einträge aus 1.8.46 mit Empfangsvollmacht (Art `vollmacht`,
  `poa_on_record` wahr) bleiben unverändert und mit stimmender Prüfsumme, gelten aber als ohne Vollmacht zur Abnahme --
  keine neue Spalte, damit ihr gebundener Inhalt gleich bleibt.
- **Nach der ersten Abnahme** (`app/warranty.py`): besteht eine nicht verworfene Abnahme (auch eine verweigerte, wie bei
  der Abgleichsperre) und waren Leistungsart oder Dauer schon festgelegt, ist jede Änderung nur mit Begründung möglich, auch
  die Übernahme eines Vorschlags. `GET /api/orders/{id}/warranty-preview` liefert vorher Vorschlag, ob und warum eine
  Begründung nötig ist und je abgenommener Abnahme das Ende bisher und danach; die Karte zeigt das als Tabelle mit
  Begründungsfeld ("So festlegen"). Gespeichert wird die Verschiebung in `order_warranty_changes.acceptance_shifts` und in
  der Historie angezeigt. `set_order_warranty()` sperrt die Auftragszeile wie das Erfassen einer Abnahme.
- **Nachweis**: förmlich -> mindestens ein Beleg (das Protokoll), eine Begründung wird dort abgelehnt; ausdrücklich und
  schlüssig -> Beleg oder Begründung, mindestens eins, beides erlaubt. Die Spalte heißt weiter `conduct_reason`, die
  Oberfläche "Begründung (Nachweis)".
- **"Gewährleistung regulär bis"** an Auftrag, Objekt (Spalte, Karte, Fußnote) und Dachfläche, mit "ohne Hemmung oder
  Neubeginn" (`acceptance_warranty()["hint"]`).
- **Migration `1dcea6473427`**: Spalten wie oben (`acceptance_authorized` NOT NULL, server_default falsch -- vorhandene
  Beteiligte haben danach keine Vollmacht zur Abnahme). `downgrade()` verweigert bei gesetztem Häkchen, Beleg oder
  festgehaltener Verschiebung.

### Festlegungen 1.8.47 (bestätigt am 05.10.2026)

1. **Die erste Festlegung nach einer Abnahme braucht keine Begründung** -- sie verschiebt nichts, sie legt die Enden erst
   fest; die Vorschau zeigt sie trotzdem vorher.
2. **Auch eine verweigerte Abnahme löst die Begründungspflicht aus** (wie die Abgleichsperre), obwohl sich dabei kein
   Ende verschiebt.
3. **Förmlich mit Begründung statt Beleg wird abgelehnt**; bei ausdrücklich und schlüssig sind Beleg und Begründung
   zusammen erlaubt.
4. **Die Vorschau wird nicht erzwungen**: der Server verlangt die Begründung, nicht dass die Vorschau angesehen wurde.

### Antworten auf die Fragen vom 04.10.2026

- **Grüne Gegenprobe (1.8.46)**: der PostgreSQL-Test prüft Erfassen gegen Abgleich, jetzt in zwei Tests getrennt (Abgleich
  hält die Sperre -> Erfassen wartet; Erfassen läuft, noch nicht committet -> Abgleich wartet und sieht die Abnahme, 409),
  beide über den echten Code (`create_acceptance()` mit angehaltenem Commit). Sperre im Abgleich entfernt: beide rot.
  Sperre beim Erfassen entfernt: beide grün -- das Einfügen der Abnahme nimmt über ihren Fremdschlüssel FOR KEY SHARE auf
  die Auftragszeile, und das kollidiert mit dem FOR UPDATE des Abgleichs in beide Richtungen. Die Sperre beim Erfassen
  bleibt als zweite Absicherung; zwei Erfassungen nebeneinander müssen sich nicht ausschließen.
- **Importtest ohne `DATABASE_URL`**: steht nicht in der Suite (eine Kommandozeile während der Arbeit). `tests/conftest.py`
  setzt `DATABASE_URL` vor jedem App-Import auf eine Wegwerf-Datei, die beiden Tests mit Unterprozess (`test_v345`,
  `test_v252`) setzen ihre eigene bzw. prüfen gerade das Fehlen.
- **Prüfsumme stimmt nicht**: die Liste am Auftrag zeigt rot "Der gespeicherte Inhalt weicht von seiner Prüfsumme ab",
  ein Beleg "weicht ab"/"fehlt" und wird nicht ausgeliefert (409/410). Sonst nichts: die Abnahme zählt weiter für
  Abgleichsperre und Gewährleistungsende, es entsteht keine Aufgabe, Objekt- und Dachflächenseite zeigen die Abweichung
  nicht.
- **Teil-Update-Liste**: `BEKANNT` hat 72 Einträge (64 übernehmen nicht gesendete Felder, 8 kein Verstoß); 1.8.46 strich
  die Dachfläche, die Zahlen in CLAUDE.md und `teil-updates.md` sind in 1.8.47 nachgezogen.

---

## Umsetzung 1.8.48 (05.10.2026) -- Runde 2c-2a, Punkt 0: Prüfstatus und Siegel des Verwerfens

Betreibervorgabe "Vorweg": (a) Prüfstatus der Abnahme überall zeigen, wo das Gewährleistungsende erscheint (Auftrag, Objekt,
Dachfläche) -- eine Funktion liefert Ende und Prüfstatus, alle Anzeigen nutzen sie, eine Abweichung zusätzlich mit
`logger.error`; (b) Namen bei "Erfasst von" und "Verworfen von" als Kopie in den versiegelten Inhalt, vorhandene
Prüfsummen nicht neu berechnen, sondern die Fassung des Prüfsummenformats mitspeichern.

- **Eine Quelle** (`app/acceptances.py::acceptance_warranty()`): liefert neben dem Ende `check` = {ok, text} aus
  `verify_acceptance()`; neuer Parameter `duration` für die Vorschau einer Änderung. Benutzt von der Liste am Auftrag,
  der Vorschau (`app/warranty.py::warranty_shifts()`, jede Zeile mit `check`, auch in der gespeicherten Historie), der
  Objektseite (Karte und spätestes Ende je Dachfläche) und der Dachflächenseite. Das späteste Ende je Dachfläche trägt
  den Prüfstatus über ALLE Abnahmen, die die Fläche nennen (ein Höchstwert ist nur so verlässlich wie jede Eingabe).
- **Anzeige**: "✓ Prüfsumme stimmt" bzw. rot "⚠ Prüfung: … – Ende nicht verlässlich" neben jedem Ende (Auftrag:
  `accCheck()`, Spalte "Prüfung" in der Vorschau; Objekt: `acceptanceCheck()`; Dachfläche). Das Ende bleibt sichtbar,
  nur gekennzeichnet.
- **`logger.error`** in `verify_acceptance()` bei jeder Abweichung: Abnahme-ID, Auftrags-ID, welcher Teil (Inhalt,
  Beleg-IDs mit Stand, Verwerfen) -- kein Inhalt (Regel 18).
- **"Erfasst von"** stand schon seit 1.8.46 im gebundenen Inhalt (`created_by_name`), unverändert.
- **"Verworfen von"**: neues Siegel `order_acceptances.discard_sha256` = SHA-256 über Prüfsumme des Inhalts, Zeitpunkt,
  Name (Kopie) und Begründung (`discard_content()`), gesetzt im bedingten UPDATE des Verwerfens.
- **Fassung des Prüfsummenformats** `order_acceptances.checksum_format` (`CHECKSUM_FORMAT` = 2 für neue Einträge):
  1 = Erfassung bis 1.8.47, Inhalt wie bisher; 2 = die Fassung steht im gebundenen Inhalt, ein verworfener Eintrag
  braucht das Siegel. Prüfung des Verwerfens (`_verify_discard()`): nicht verworfen und keine Verwerfen-Spalte gefüllt
  -> nichts; Siegel stimmt -> "unverändert"; kein Siegel bei Fassung 1 -> "vor 1.8.48 erfasst, ohne Prüfsumme" (keine
  Abweichung); kein Siegel bei Fassung 2, Siegel ohne Verwerfen oder abweichend -> "weicht ab".
- **Migration `9c5a97bc71ef`**: beide Spalten, vorhandene Einträge `checksum_format` 1 (server_default), Prüfsummen
  unberührt. `downgrade()` verweigert, solange ein Eintrag der Fassung 2 oder ein Siegel besteht.

### Festlegungen 1.8.48 (bestätigt am 05.10.2026, Vorgabe 2c-2b)

1. **Die Fassung steht ab Fassung 2 im gebundenen Inhalt** -- sonst ließe sich ein verworfener Eintrag am ORM vorbei auf
   Fassung 1 zurücksetzen und sein Siegel löschen, und er ginge als "vor 1.8.48" durch.
2. **Auch Einträge der Fassung 1 bekommen beim Verwerfen ab jetzt das Siegel**; vor dem Update verworfene bleiben ohne
   und gelten nicht als Abweichung.
3. **Bei Abweichung wird das Ende weiter angezeigt (rot gekennzeichnet)** und zählt weiter für Abgleichsperre und
   Begründungspflicht -- wie in den Antworten zu 1.8.47 beschrieben; ausgeblendet wird nichts.
4. **`logger.error` bei jeder Prüfung mit Abweichung**, ohne Drosselung (jeder Seitenaufruf meldet erneut).
5. **Die Vorschau speichert den Prüfstatus mit** (`acceptance_shifts[].check`): die Historie zeigt, ob die Abnahme zum
   Zeitpunkt der Änderung stimmte.

### Grenze

Ein Verwerfen, das am ORM vorbei vollständig zurückgenommen wird (alle vier Spalten geleert), bleibt unerkannt: ein
späteres Ereignis kann nicht im Inhalt stehen, den es selbst versiegelt. Die Zeile "verworfen" in der Änderungshistorie
bleibt dann als einzige Spur.

### Verifikation 1.8.48

- `tests/test_v350_abnahme_pruefstatus.py` (15 Tests: Fassung 2 mit Fassung im Inhalt, Eintrag der Fassung 1 behält
  seine Prüfsumme, Rücksetzen der Fassung erkannt, Siegel mit Name als Kopie, fünf Angriffe auf das Verwerfen am ORM
  vorbei samt Protokoll ohne Inhalt, Fassung 1 ohne Siegel keine Abweichung, Prüfstatus an Auftrag/Vorschau/Objekt/
  Dachfläche mit Gegenprobe, spätestes Ende je Dachfläche, fehlender Beleg, Seiten, Migration); `test_v349` nachgezogen
  (Schlüssel `check`).
- Volle Suite 2709 grün (mit den opt-in-Tests gegen PostgreSQL). `test_v349`/`test_v350` über das Scratchpad-Plugin gegen
  PostgreSQL 17: 85 grün, rot nur die drei Migrationstests mit rohem SQL und erfundenen Fremdschlüsseln (bekannte Grenze).
- Migration `9c5a97bc71ef`: SQLite hin/zurück/hin, `alembic check`; PostgreSQL 17 im Wegwerf-Schema: Kette bis
  `1dcea6473427`, head, Abnahme über den App-Code (Fassung 2, verworfen, Siegel stimmt), downgrade verweigert ("1 Abnahmen
  in Prüfsummenformat 2, 1 versiegelte Verwerfen"), `current` = head, `check` sauber; leeres Schema hin/zurück/hin.
- Gegenproben (Schutz ausgehebelt, Datei byte-genau zurück): 8 von 8 rot.
- Klicktest `klicktest_abnahme.py` 55/55, neu: zweiter Auftrag mit am ORM vorbei verändertem Abnahmedatum -- rot an
  Dachflächenliste und Karte des Objekts, Dachfläche und Auftrag, verworfener Eintrag mit verändertem Siegel; Spalte
  "Prüfung" der Vorschau.

---

## Umsetzung 1.8.49 (05.10.2026) -- Runde 2c-2a, Punkt 1: Mängel aus der Abnahme

Betreibervorgabe (gekürzt): neues Modell Mangel (nicht Finding) nur an Abnahmen mit "Vorbehalt Mängel: ja" oder
"verweigert", Warnung an solchen ohne Mangel, Quelle vorerst nur "Abnahme"; Beschreibung Pflicht, optional Dachfläche (nur
aus dem Objekt der Abnahme), Ortsangabe, Beseitigungsfrist, Fotos und Belege; unveränderlich, Fotos nur ergänzen, Korrektur
durch Verwerfen mit Begründung; Haltung (offen, anerkannt, bestritten mit Begründung) und Status (offen, beseitigt mit Datum,
Beseitigung abgenommen mit Datum/Erklärendem/Beleg oder Begründung, erledigt ohne Beseitigung mit Begründung) mit Historie;
Freigabe zur Beseitigung nur durch das Büro, bewusst, mit Historie, unabhängig von der Haltung; nur bei `vob_b`
"Nachbesserung regulär bis" = das spätere von Regelende und Abnahme der Beseitigung + 24 Monate; beim Erfassen eine Aufgabe
ohne Zuständigkeit, fällig zur Frist, Verweis in beide Richtungen, der Mangel ist die Wahrheit.

### Modell (`app/models.py`, `app/defects.py`, `app/routers/defects.py`)

- **`defects`**: `order_id`, `property_id` (Objekt der Abnahme), `source` ("abnahme"; später "ruege"), `acceptance_id`,
  `description`, `roof_area_id` + `roof_area_name` (Schnappschuss), `location`, `remedy_due_on`, `task_id` (ohne
  Fremdschlüssel, nicht gebunden), `content_sha256` + `checksum_format` (Fassung 1, steht im Inhalt), erfasst/verworfen wie
  bei der Abnahme samt Siegel `discard_sha256`.
- **`defect_events`** (Verlauf): `kind` haltung/status/freigabe/fotos, `value`, `previous_value`, `event_date`, `reason`,
  Erklärender (wie Abnahme, `poa_on_record`), `previous_event_sha256`, `content_sha256` (bindet Prüfsumme des Mangels und
  des vorigen Eintrags -- Kette). Der Stand (`defect_state()`) ergibt sich aus den Einträgen.
- **`defect_files`**: `foto`, `beleg`, `abnahmevollmacht`; `event_id` leer = beim Erfassen (im Inhalt des Mangels), sonst im
  Inhalt des Eintrags. Ablage der Abnahme, Unterordner `maengel` (`_write_file(subdir=…)`), exklusiv, schreibgeschützt.
- ORM-Sperre für alle drei (Ändern, Löschen); Verwerfen per bedingtem UPDATE mit Siegel und Historienzeile.
- **Routen** (alle `require_min_role(buero_auftrag)`): `GET /api/orders/{id}/defects`,
  `GET /api/order-acceptances/{id}/defect-options`, `POST /api/order-acceptances/{id}/defects` (multipart "data",
  "photos", "receipts"), `POST /api/defects/{id}/stance|release` (JSON), `/status` (multipart "data", "receipts"),
  `/photos`, `/discard`, `GET /api/defects/{id}/files/{file_id}` (nur mit stimmender Prüfsumme, nosniff).
- **Sperren**: Erfassen sperrt die Auftragszeile wie das Verwerfen der Abnahme (beide warten aufeinander, danach 409); jeder
  Eintrag im Verlauf sperrt die Zeile des Mangels und liest Stand und Verlauf neu.
- **Abnahmeliste**: `defects` je Eintrag (`defect_summary()`: erwartet, aktiv, gesamt, fehlt + Text);
  `acceptance_allows_defects()` ist die eine Regel (`app/acceptances.py`).
- **Historie**: `Defect` und `DefectEvent` in `AUDITED_TYPES`, beide unter der Kennung des Mangels ("Mangel"), Verwerfen als
  eigene Zeile.
- **Folgen an anderer Stelle**: eine bei einem Mangel genannte Dachfläche lässt sich nicht mehr löschen (400, archivieren);
  ein Beteiligter, der eine Beseitigung abgenommen hat, bleibt im Projekt (409).
- **Oberfläche** (`app/templates/_maengel.html`, in `order.html` nach `_abnahme.html`): Karte "Mängel" mit Stand
  (Status, Haltung, Freigabe), Frist (überschritten rot), Dateien, "Nachbesserung regulär bis" mit Prüfstatus, Aufgabe (mit
  Hinweis, wenn sie erledigt, der Mangel aber offen ist), Verlauf; Aktionen über eingeblendete Felder (kein `prompt()`);
  Dialog "Mangel erfassen" ohne Vorauswahl, geöffnet aus der Abnahme ("+ Mangel erfassen", Warnung "ohne erfassten
  Mangel", "Mängel: n erfasst"); nach dem Speichern Sprung zum Mangel, ebenso über den Verweis der Aufgabe
  (`/orders/<id>#mangel-<id>`).

### Festlegungen 1.8.49 (bestätigt am 05.10.2026, Vorgabe 2c-2b; Nr. 6 seit 1.8.51 um Belege erweitert, Nr. 12 um die Kurzfassung im Titel)

1. **Quelle als Feld** (`source` + `acceptance_id`): die Rüge kommt später als `source` "ruege" ohne Abnahme dazu.
2. **An einer verworfenen Abnahme kein neuer Mangel (409), an einer ohne Vorbehalt 400.** Mängel einer später verworfenen
   Abnahme bleiben bestehen, gekennzeichnet "Abnahme verworfen"; die Warnung "ohne Mangel" entfällt mit dem Verwerfen.
3. **Dachfläche aus dem Objekt der Abnahme** (beim Erfassen der Abnahme festgehalten), nicht aus dem heutigen des Projekts;
   archivierte nicht neu.
4. **Beseitigungsfrist nicht vor dem Abnahmedatum**, in der Vergangenheit erlaubt (nachträgliches Erfassen); "überschritten"
   rot, solange der Mangel nicht erledigt ist.
5. **Dateien**: Fotos nur JPEG/PNG/WebP, Belege PDF oder Foto, am Inhalt erkannt; höchstens 10 je Speichern, je 15 MB,
   zusammen 30 MB; dieselbe Datei nicht doppelt. Ablage der Abnahme (Unterordner `maengel`), keine neue Umgebungsvariable.
6. **"Fotos nur ergänzen"**: nachgereicht werden nur Fotos (keine Belege), als eigener Eintrag im Verlauf -- auch nach der
   Erledigung, nicht nach dem Verwerfen.
7. **Haltung**: "anerkannt" ohne, "bestritten" mit Begründungspflicht; Wechsel zwischen beiden jederzeit (auch nach der
   Erledigung), nie zurück auf "offen"; derselbe Wert zweimal ist 409.
8. **Status**: offen -> beseitigt oder erledigt ohne Beseitigung; beseitigt -> Beseitigung abgenommen oder zurück auf offen
   (Begründung Pflicht, z. B. Nachbesserung misslungen); **nicht** beseitigt -> erledigt ohne Beseitigung. Beseitigung
   abgenommen und erledigt ohne Beseitigung sind endgültig -- Korrektur nur über Verwerfen und neues Erfassen. "beseitigt"
   nicht vor der Abnahme und nicht in der Zukunft, Abnahme der Beseitigung nicht vor "beseitigt". Ein Übergang, den der Stand
   nicht zulässt, ist 409.
9. **Beseitigung abgenommen**: Erklärender wie bei der Abnahme (Auftraggeber = Kunde laut Auftrag oder Beteiligter dieses
   Projekts, Vollmacht zur Abnahme als Kopie, sonst Warnung); Nachweis Beleg oder Begründung, mindestens eins -- ohne
   Unterscheidung nach Art.
10. **Freigabe**: Begründung Pflicht bei "bestritten" (Kulanz) und beim Zurücknehmen, sonst freiwillig; nach der Erledigung
    keine Änderung mehr; "bewusst" heißt: eigener Knopf im eigenen Feld, kein zusätzliches Häkchen.
11. **Nachbesserung regulär bis** nach der HEUTIGEN Vertragsgrundlage des Auftrags; bei verweigerter oder verworfener Abnahme
    und ohne Dauer "nicht berechenbar"; nur am Mangel auf der Auftragsseite, nicht an Objekt und Dachfläche.
12. **Aufgabe**: Titel "Mangel aus Abnahme <Auftrag> – <Dachfläche bzw. Ort>", Beschreibung nur Metadaten (nicht der
    Mangeltext, wie bei den Aufgaben aus Anzeigen), ohne Zuständigkeit mit Sichtbarkeitsgrenze `buero_auftrag`
    (Büro-Eingang), fällig zur Frist (ohne Frist ohne Fälligkeit), Priorität normal, in derselben Transaktion wie der Mangel.
    Ohne Aufgabenmodul keine Aufgabe und kein Nachholen. Erledigt bei Beseitigung abgenommen, erledigt ohne Beseitigung und
    Verwerfen; archivierte bleiben unberührt; eine gelöschte zeigt der Mangel an.
13. **Kette im Verlauf**: ein mittendrin entfernter oder geänderter Eintrag fällt auf, ein entfernter letzter nicht (Grenze
    wie beim Verwerfen, 1.8.48).
14. **Verwerfen auch nach der Erledigung möglich.**

### Verifikation 1.8.49

- `tests/test_v351_maengel.py` (38 Tests, zwei opt-in gegen PostgreSQL: Erfassen wartet auf das Verwerfen der Abnahme und
  bekommt 409; zwei gleichzeitige Statuswechsel -- der zweite wartet und bekommt 409, ein Eintrag); `test_v326` (Pfadwert
  `defect_id`, Mangel mit Foto im Rundgang, drei neue GET-Routen: Monteur 403, Admin 200).
- Volle Suite 2747 grün (mit den opt-in-Tests gegen PostgreSQL). `test_v351`/`test_v326` über das Scratchpad-Plugin gegen
  PostgreSQL 17: 95 grün, rot nur der Migrationstest mit rohem SQL und erfundenen Fremdschlüsseln (bekannte Grenze).
- Gegenproben (Schutz ausgehebelt, Datei byte-genau zurück): 22 von 22 rot, darunter beide Sperren gegen PostgreSQL.
- Migration `60f193510ae2`: SQLite hin/zurück/hin, `alembic check`; PostgreSQL 17 im Wegwerf-Schema: Kette bis `9c5a97bc71ef`,
  head, Mangel über den App-Code (bestritten, Kulanz-Freigabe, beseitigt, abgenommen; Prüfung stimmt, Aufgabe angelegt),
  downgrade verweigert ("1 Mängel samt Verlauf"), `current` = head, `check` sauber; leeres Schema hin/zurück/hin.
- Klicktest `scripts/klicktest_maengel.py` 32/32. Der erste Lauf fand einen eigenen Fehler: `_maengel.html` setzte beim Laden
  `FELDNAMEN` aus `order.html` zusammen, das dort erst nach dem Include steht -- das Skript brach ab, jede Aktion außer dem
  Erfassen lief ins Leere. Behoben (erst beim Aufruf), seither geprüft.
- `klicktest_abnahme.py` 56/56: der Schritt "Verwerfen" klickte den ersten Knopf der Abnahme -- das ist an einer Abnahme
  mit Vorbehalt jetzt "+ Mangel erfassen"; Klick eindeutig gemacht, Warnung und Knopf geprüft.

---

## Umsetzung 1.8.50 (05.10.2026) -- Runde 2c-2a, Punkt 2: Platzhalter {gewaehrleistung}

Betreibervorgabe: Platzhalter `{gewaehrleistung}` für Vertragsvorlagen (Text der Dauer, z. B. "5 Jahre"). Nutzt die Vorlage
ihn, ist Festschreiben gesperrt, solange die Dauer nicht festgelegt ist. Danach sind Dauer und Leistungsart gesperrt wie
beim Kundenwechsel.

- **Platzhalter** (`app/contract_templates.py`): in `CONTRACT_PLACEHOLDERS` (Einstellungen → Vertragsvorlagen zeigen ihn mit
  Erklärung), Wert `app/warranty.py::contract_duration_text()`: volle 12 Monate als Jahre ("5 Jahre", "1 Jahr"), sonst
  Monate ("18 Monate"), Tage mit "und" ("2 Jahre und 10 Tage"); ohne Dauer "nicht festgelegt" (nur im Entwurf sichtbar).
- **Festschreiben** (`app/contract_versions.py::freeze_contract()`): steht `{gewaehrleistung}` in `used_placeholders` und
  ist die Dauer nicht festgelegt -> `ContractStateError` (409). Festschreiben sperrt jetzt nach dem Vertrag auch die
  Auftragszeile und liest den Auftrag danach neu -- eine gleichzeitig festgelegte Dauer steht so im Vertrag, nicht der beim
  Laden gelesene Stand.
- **Sperre** (`app/warranty.py::warranty_contract_lock()`): hat eine festgeschriebene Fassung den Platzhalter genutzt (laut
  `used_placeholders` im eingefrorenen Inhalt), lehnen `set_order_warranty()` und die Vorschau mit `WarrantyLockedError`
  ab (409). `set_order_warranty()` sperrt dafür erst die Vertragszeile, dann die Auftragszeile -- dieselbe Reihenfolge wie
  Festschreiben und der Abgleich mit dem Angebot (`ensure_contract_not_signed()`), damit sich keine zwei Vorgänge
  gegenseitig blockieren.
- **Oberfläche**: Karte "Vertrag" mit Hinweis und gesperrtem Knopf "festschreiben", solange die Dauer fehlt
  (`contract_state()["warranty_missing"]`, nur Abschnitte, die in diesen Vertrag kommen); Karte "Gewährleistung" zeigt bei
  Sperre den Grund (`order_to_dict()["warranty_lock_text"]`, nur in der Einzelansicht) statt Leistungsart, Vorschlag und
  Abweichung; nach dem Festlegen lädt die Vertragskarte neu.

### Festlegungen 1.8.50 (bestätigt am 05.10.2026 außer der Sperre: Nr. 3 und 4 offen, siehe "Umsetzung 1.8.51", Punkt 0a)

1. **Text der Dauer**: Jahre nur bei vollen 12 Monaten, sonst Monate; Tage mit "und"; im Entwurf ohne Dauer "nicht
   festgelegt".
2. **"Die Vorlage nutzt ihn"** = Titel oder ein Abschnitt, der in DIESEN Vertrag kommt (Verbraucher-Abschnitte nur bei
   Verbrauchern) -- dieselbe Regel wie `used_placeholders` beim Festschreiben.
3. **Gesperrt ab der ersten festgeschriebenen Fassung mit dem Platzhalter**, auch ohne Unterschrift, auch nach "Neue
   Fassung" und auch, wenn eine spätere Fassung ihn nicht mehr nutzt -- wie der Kundenwechsel (ab Festschreiben, dauerhaft).
   Folge: eine falsch festgelegte Dauer lässt sich nach dem Festschreiben nicht mehr über eine neue Fassung korrigieren. Zu
   entscheiden, ob die Sperre erst mit der Unterschrift greifen soll.
4. **Eine festgeschriebene Fassung ohne den Platzhalter sperrt nichts.**
5. **Die Sperre geht der Begründungspflicht nach einer Abnahme (1.8.47) vor**: auch mit Begründung keine Änderung.
6. **Die Vorschau antwortet bei Sperre ebenfalls 409**; die Karte zeigt den Grund statt der Bedienelemente.

### Verifikation 1.8.50

- `tests/test_v352_vertrag_gewaehrleistung.py` (17 Tests: Text der Dauer, Platzhalter in der Liste, Festschreiben gesperrt
  bis zur Festlegung samt Inhalt "5 Jahre", Sperre von Dauer und Leistungsart auch nach neuer Fassung und in der
  Geschäftsfunktion, Gegenprobe ohne Platzhalter, Entwurf "nicht festgelegt", Seite; zwei opt-in gegen PostgreSQL: Festlegen
  wartet auf ein laufendes Festschreiben und wird abgelehnt; Festschreiben wartet auf ein laufendes Festlegen und schreibt
  den neuen Wert fest).
- Gegenproben: 8 von 9 rot. Grün blieb "Festschreiben ohne Auftragssperre" gegen PostgreSQL: das Festlegen wartet schon an der
  Vertragssperre -- die Auftragssperre im Festschreiben bleibt als zweite Absicherung (wie beim Erfassen der Abnahme, 1.8.46).
- Keine Migration (keine neue Spalte).
- Volle Suite 2764 grün (mit den opt-in-Tests gegen PostgreSQL). `test_v352`/`test_v336` über das Scratchpad-Plugin gegen
  PostgreSQL 17: 35 grün, rot nur der bekannte Migrationstest von `test_v336` (rohes SQL, erfundene Fremdschlüssel).
- Klicktest `scripts/klicktest_vertrag_gewaehrleistung.py` 8/8; unverändert grün `klicktest_vertrag_festschreiben.py`
  40/40, `klicktest_abnahme.py` 56/56, `klicktest_maengel.py` 32/32.

### Nebenbefunde 2c-2a (1.8.48–1.8.50, nur gemeldet)

1. **Sicherung auf dem Server**: die Dateien der Mängel liegen unter `ERP_DATA_DIR/acceptance_documents/maengel` -- die Frage
   aus 1.8.46 (Nebenbefund 2), ob `/home/tobias/backup.sh` den ganzen Datenordner sichert, gilt damit auch für sie.
   **Beantwortet 05.10.2026**: ja, `erp-data` vollständig.
2. **Meldetext beim Foto**: ein SVG als Foto eines Mangels meldet "Der Beleg muss ein Foto (JPEG, PNG, WebP) oder ein PDF
   sein" -- der Text stammt aus `_checked_upload()` der Abnahme und sagt "Beleg" auch beim Foto. Abgelehnt wird richtig.
3. **Grenze der Siegel**: ein am ORM vorbei vollständig zurückgenommenes Verwerfen (Abnahme oder Mangel) und ein entfernter
   letzter Eintrag im Verlauf eines Mangels bleiben unerkannt; nur die Änderungshistorie behält ihre Zeile.
4. **Mängel einer später verworfenen Abnahme** behalten ihre offene Aufgabe (Festlegung 1.8.49 Nr. 2) -- sie werden nicht an
   die korrigierte Abnahme umgehängt; das Büro verwirft oder erledigt sie bei Bedarf einzeln.
5. **Klicktest `klicktest_abnahme.py`** klickte "den ersten Knopf" einer Abnahme -- mit "+ Mangel erfassen" traf das den
   falschen; im Skript behoben (1.8.49). Ähnliche Selektoren in anderen Klicktests nicht durchgesehen.

---

## Umsetzung 1.8.51 (05.10.2026) -- Runde 2c-2b, Punkt 0 (Vorweg)

Betreibervorgabe "Vorweg": (a) Sperre von Dauer, Leistungsart und Kundenwechsel an eine gültige festgeschriebene Fassung
binden, eine Regel für alle drei; vor der Unterschrift Fassung mit Begründung zurückziehen, korrigieren, neu festschreiben,
nach der Unterschrift endgültig -- gibt es das Zurückziehen noch nicht: nur melden; (b) Belege am Mangel nachreichen wie
Fotos; (c) Aufgabentitel mit Kurzfassung des Mangeltexts, Einwände melden; (d) CLAUDE.md: eingespielt wird nur mit
`update.sh`, `backup.sh` sichert `erp-data` vollständig. Festlegungen 1.8.48–1.8.50 bestätigt außer der Sperre.

### Punkt 0a: Sperre an eine gültige Fassung -- nur gemeldet, nicht gebaut

Ein Zurückziehen einer Fassung gibt es nicht (geprüft: `app/contract_versions.py`, `app/contract_signatures.py`,
Routen `app/routers/contract_templates.py`). Stand heute -- drei Regeln, keine davon kennt "gültig":

| Sperre | Funktion | greift ab | endet |
|---|---|---|---|
| Kundenwechsel im Projekt (1.8.44) | `project_participants.py::check_client_change()` | irgendeine Fassung irgendeines Auftrags des Projekts | nie |
| Dauer und Leistungsart (1.8.50) | `warranty.py::warranty_contract_lock()` | irgendeine Fassung, deren `used_placeholders` `{gewaehrleistung}` enthält (auch überholte) | nie |
| neue Fassung (1.8.33/1.8.34) | `contract_versions.py::start_new_version()` | -- | ab Unterschrift keine neue Fassung |

"Neue Fassung" macht den festgeschriebenen Vertrag ohne Begründung wieder zum Entwurf; die bisherige Fassung bleibt die
geltende (`superseded_at` leer), bis eine neue festgeschrieben ist, und ist bis dahin weiter versendbar. Ein Zurückziehen
im Sinn der Vorgabe (Fassung ungültig, mit Begründung, danach korrigieren) fehlt.

Vorschlag für die Umsetzung (bitte entscheiden):
1. **"Fassung zurückziehen"** nur bei Status "festgeschrieben" (nicht nach der Unterschrift), Büro, Pflicht-Begründung;
   bedingtes UPDATE mit Siegel wie beim Verwerfen der Abnahme (`withdrawn_at`/`_by_name`/`_reason`/`withdraw_sha256` an
   `OrderContractVersion`), Vertrag zurück auf "entwurf", Zeile in der Änderungshistorie. Die Fassung bleibt sichtbar und in
   der Ablage, wird aber nicht mehr versendet oder zugestellt.
2. **Eine Regel** `contract_lock(db, order)`: gesperrt, solange der Auftrag eine **gültige** Fassung hat (festgeschrieben oder
   unterschrieben, nicht zurückgezogen, nicht überholt). Offen: sperrt eine gültige Fassung Dauer und Leistungsart **immer**
   (wie den Kunden) oder nur, wenn sie `{gewaehrleistung}` nutzt (heute Festlegung 1.8.50 Nr. 4)?
3. **"Neue Fassung"** ersetzen durch "zurückziehen" oder daneben behalten? Heute erlaubt sie das Korrigieren ohne
   Begründung, die alte Fassung bleibt bis dahin gültig.
4. **Schon versendete Fassung zurückziehen**: nur mit Hinweis, dass der Kunde sie hat (Versandverlauf), oder gesperrt?

### Punkt 0b: Belege nachreichen

- `app/defects.py::add_receipts()`, `POST /api/defects/{id}/receipts` (multipart "receipts", ab `buero_auftrag`): neuer
  Eintrag im Verlauf `kind` "belege" ("Belege ergänzt"), Dateien Art "beleg" -- PDF oder Foto, am Inhalt erkannt, gleiche
  Grenzen wie beim Erfassen. Keine Migration (`kind` ist ein Text, der Inhalt des Eintrags hat schon `files`).
- Karte "Mängel": Knopf "Belege ergänzen …" neben "Fotos ergänzen …"; der Verlauf zeigt "n Belege ergänzt" mit den Dateien.

### Punkt 0c: Aufgabentitel mit Kurzfassung

`_new_task()`: Titel "Mangel aus Abnahme <Auftrag> – <Dachfläche bzw. Ort>: <Kurzfassung>" (ohne Ort ohne den Teil davor),
Kurzfassung über `short_text()` (Leerraum zusammengezogen, höchstens 60 Zeichen, an einer Wortgrenze mit "…"). Die
Beschreibung der Aufgabe bleibt bei Metadaten. Bestehende Aufgaben behalten ihren Titel.

**Gemeldet, was dagegen sprechen kann** (gebaut trotzdem, weil es alle Aufgabentitel gleich trifft): wird die Aufgabe
übernommen oder zugewiesen, schickt `app/tasks.py::notify_task_assignment()` (Einstellung "bei Zuweisung benachrichtigen")
den Titel per E-Mail an die Adresse im Mitarbeiterprofil (`EmployeeProfile.email`, kann privat sein) und hält ihn im
Versandprotokoll fest -- die Kurzfassung des Mangels verlässt dann das ERP. Monteure sehen Aufgaben nie (`/api/tasks` ist
Büro). Der Titel ist eine bearbeitbare Kopie; maßgeblich bleibt der Mangel. **Erledigt seit 1.8.53**: Aufgaben-Mails
enthalten keinen Inhalt der Aufgabe mehr, nur Art und Link (siehe "Umsetzung 1.8.53/1.8.54").

### Punkt 0d: CLAUDE.md

Serverumgebung (Zeilen "Sicherung" und "Einspielen") und "Der Weg einer Änderung auf den Server": eingespielt wird nur mit
`update.sh` (auf dem Server, nicht im Repo), nie mit einzelnen `alembic`-Befehlen; die frühere Handabfolge bleibt als
Nachweis, was ein Einspielen leisten muss. Offen vermerkt: die Probe gegen `spielwiese` bei Schemaänderungen ist dort ein
einzelner `alembic`-Befehl.

### Festlegungen 1.8.51 (bestätigt am 05.10.2026, Nacharbeiten 2c-2b; Nr. 4 beantwortet: `/home/tobias/update.sh`)

1. **Belege als eigener Eintrag "belege"**, nicht im Eintrag "fotos" -- der Verlauf unterscheidet Fotos und Belege; je
   Speichern nur eine Art.
2. **Belege nachreichen auch nach der Erledigung** (wie Fotos), nicht nach dem Verwerfen; nur das Büro.
3. **Kurzfassung 60 Zeichen** an der Wortgrenze; Titel höchstens 255 Zeichen wie bisher.
4. **Pfad von `update.sh`** in CLAUDE.md ohne Verzeichnis -- bitte den Pfad nennen, wenn er dort stehen soll.
   **Beantwortet 05.10.2026**: `/home/tobias/update.sh`, probt selbst gegen die Spielwiese (CLAUDE.md seit 1.8.54).

### Verifikation 1.8.51

- `tests/test_v353_maengel_belege_und_titel.py` (12 Tests): Belege nur ergänzen (zwei Einträge, nichts ersetzt, Datei
  abrufbar), ungültige Belege (keiner, SVG, doppelt) -- 400 und nichts gespeichert, nach Erledigung ja und nach Verwerfen
  409, Monteur 403 mit Gegenprobe, Knopf auf der Auftragsseite, `short_text()`, Titel mit Dachfläche, Ort oder ohne.
- Volle Suite 2776 grün (mit den opt-in-Tests gegen PostgreSQL). Keine Migration, keine Sperre neu -- kein eigener Lauf
  gegen PostgreSQL nötig (die Belege laufen über dieselbe Sperre des Mangels wie Fotos, 1.8.49 gegen PostgreSQL geprüft).
- Gegenproben (Schutz ausgehebelt, Datei byte-genau zurück): 7 von 7 rot.
- Klicktest `klicktest_maengel.py` 35/35 (neu: "Belege ergänzen" ohne Auswahl abgelehnt, mit PDF als sechster Eintrag im
  Verlauf, Beleg abrufbar mit nosniff, Aufgabentitel mit Kurzfassung).

---

## Umsetzung 1.8.52 (05.10.2026) -- Runde 2c-2b, Punkt 1: Monteur-Sicht auf Mängel in /mobil

Betreibervorgabe: in `/mobil` nur freigegebene, nicht erledigte, nicht verworfene Mängel der zugeordneten Aufträge; Felder als
Positivliste (Beschreibung, Ort, Dachfläche, Frist, Fotos), keine Haltung, keine Abnahmedaten, keine Gewährleistung;
"beseitigt" melden mit mindestens einem Foto, idempotent über `client_uuid` (Stufe 3); Fotos nur über einen eigenen
Monteur-Weg mit derselben Prüfung; wird die Freigabe zurückgenommen, verschwindet der Mangel. Angriffstests mit Gegenprobe,
wichtige Tests gegen PostgreSQL.

### Sichtbarkeit (`app/defects.py`, Abschnitt "Monteur")

- **Eine Regel** `field_may_see_defect()`: freigegeben (letzter Eintrag "freigabe" = freigegeben), Status "offen", nicht
  verworfen -- live aus dem Verlauf, deshalb verschwindet der Mangel mit dem Zurücknehmen der Freigabe sofort.
- **Aufträge**: `app/orders.py::field_accessible_order_ids()` -- dieselben drei Abfragen wie `field_may_access_order()`
  (Einzelzuweisung, Team-Besetzung an der AV ohne Datumsfilter, eigener Bericht), jetzt in `_field_order_id_queries()`
  einmal definiert; `field_may_access_order()` nutzt sie ebenfalls (Verhalten unverändert).
- `list_field_defects()` (Frist zuerst, ohne Frist zuletzt), `field_visible_defect()` (Einzelzugriff), `field_photo()`
  (nur Art "foto" genau dieses Mangels).

### Positivliste

`field_defect_dict()` und das Antwortschema `FieldDefectOut` (`app/schemas.py`): `id`, `order_id`, `order_number`,
`property_name`, `property_address`, `description`, `location`, `roof_area_name`, `remedy_due_on`, `remedy_overdue`,
`photos[].id`. Das Schema ist die eigentliche Grenze -- liefert die Geschäftslogik mehr, kommt es nicht an (Test mit
untergeschobenen Schlüsseln). Objekt: das der Abnahme (live, `Defect.property_id`), sonst der Schnappschuss am Auftrag.

### Routen (`app/routers/field_defects.py`, alle `require_min_role(field)`)

- `GET /api/field-view/defects` -- Mitarbeiter nur aus dem Konto (ohne: 422).
- `GET /api/field-view/defects/{defect_id}/photos/{file_id}` -- dieselbe Prüfung, nur Fotos, nur mit stimmender Prüfsumme
  (409/410), nosniff. Der Büro-Weg `/api/defects/...` bleibt für Monteure 403.
- `POST /api/field-view/defects/{defect_id}/remedied` (multipart "data" = `FieldDefectRemedied`: `client_uuid`,
  `event_date`, `extra="forbid"`; "photos"). Reihenfolge: Wiederholung (dieselbe Kennung -> dieselbe Antwort, auch wenn der
  Mangel durch die Meldung schon unsichtbar ist), Sichtbarkeit (404), Meldung (400/409). Antwort `FieldDefectReportOut`:
  `defect_id`, `event_id`, `event_date`, `photo_count`.
- Nicht sichtbar -- nicht freigegeben, fremder Auftrag, verworfen, schon beseitigt, gibt es nicht: überall 404 "Mangel
  nicht gefunden.", ohne Grund.

### Meldung "beseitigt" (`report_remedied()`)

- Eintrag "Status: offen -> beseitigt" mit Datum und den Fotos als Dateien des Eintrags (in dessen gebundenem Inhalt),
  Ersteller das Konto des Monteurs; kein Text, kein Erklärender. Die Aufgabe bleibt offen (erledigt wird sie erst mit
  "Beseitigung abgenommen", 1.8.49).
- **Idempotenz**: `defect_events.client_uuid` (global eindeutig, UNIQUE). Geprüft vor dem Einfügen und unter der Sperre des
  Mangels; eine gleichzeitige Wiederholung, die beides passiert, fängt der UNIQUE-Schlüssel (`IntegrityError` -> gespeicherte
  Meldung). Gehört die Kennung einer anderen Person oder einem anderen Mangel: 400.
- **Unter der Sperre neu geprüft**: verworfen, Freigabe zurückgenommen, Status nicht mehr "offen" -> 409.
- Büro: der Eintrag im Verlauf trägt "gemeldet in der Monteursansicht" (`_event_dict()["via_field_view"]`).

### Oberfläche (`app/templates/mobil.html`)

Abschnitt "Mängel zur Beseitigung" nach "Offene Berichte": Karte je Mangel (Objekt, Adresse, Beschreibung, Dachfläche,
Ort, Auftrag, Frist rot bei Überschreitung, Fotos als Vorschau über den Monteur-Weg), "Beseitigt melden" öffnet ein Formular
im Abschnitt (kein `prompt()`): Datum vorbelegt mit heute in Europe/Berlin (`_berlin_date.html`), Fotos (mindestens eins),
"Meldung senden". Die Kennung entsteht beim Öffnen und bleibt bei jeder Wiederholung gleich. Fehler über `fehlerText()`.

### Migration `6c7610e54ce3`

`defect_events.client_uuid` (String 36, nullable) mit `uq_defect_event_client_uuid`. `downgrade()` ohne Rückfrage: verloren
gehen nur die Kennungen, die Meldungen bleiben gültige Einträge (die Kennung steht nicht im gebundenen Inhalt).

### Festlegungen 1.8.52 (bestätigt am 05.10.2026 außer Nr. 5 "kein Text des Monteurs" -- seit 1.8.54 optionaler Hinweis, siehe "Umsetzung 1.8.53 und 1.8.54")

1. **"Zugeordnete Aufträge" = `field_may_access_order()`**: Zuweisung an der AV (einzeln oder Team, ohne Datumsfilter) oder
   ein eigener Bericht; kein Filter auf den Auftragsstatus (ein Mangel kommt oft nach dem Abschluss). Jeder so zugeordnete
   Monteur sieht den freigegebenen Mangel -- eine Zuweisung je Mangel gibt es nicht.
2. **"Nicht erledigt" heißt für den Monteur Status "offen"**: nach "beseitigt" verschwindet der Mangel (für alle Monteure);
   setzt das Büro zurück auf "offen", erscheint er wieder.
3. **Positivliste zusätzlich zu den fünf Feldern**: Auftragsnummer und Objekt (Name, Adresse), damit der Monteur weiß, wohin;
   "Frist überschritten" als Ja/Nein. Fotos: alle Fotos des Mangels (beim Erfassen, ergänzt, aus einer früheren Meldung),
   nie Belege oder Vollmachten -- auch nicht ein Beleg, der ein Bild ist.
4. **404 ohne Grund** für alles, was der Monteur nicht sehen darf (nicht 403) -- sonst verriete die Antwort, dass es den
   Mangel gibt.
5. **Meldung**: Datum Pflicht, nicht in der Zukunft, nicht vor der Abnahme; kein Text des Monteurs; Fotos JPEG/PNG/WebP mit
   den Grenzen des Büros (10 je Meldung, je 15 MB, zusammen 30 MB). **Nicht bestätigt**: seit 1.8.54 optional ein kurzer
   Hinweis des Monteurs, nur intern sichtbar (Rest der Festlegung unverändert).
6. **`client_uuid` Pflicht, höchstens 36 Zeichen, global eindeutig**; die Wiederholung liefert dieselbe Antwort nur an dieselbe
   Person für denselben Mangel -- auch nachdem das Büro weitergeschrieben hat. Nicht im gebundenen Inhalt.
7. **Fotos ergänzt der Monteur nur mit der Meldung**, nicht einzeln; "eigener Monteur-Weg" = Abruf und Meldung.
8. **Büro-Konten dürfen die Monteur-Routen nutzen** (eigene Zuordnungen, ohne Mitarbeiter 422), wie `/api/field-view/today`.
9. **Downgrade ohne Rückfrage** (siehe Migration).

### Verifikation 1.8.52

- `tests/test_v354_maengel_monteur.py` (25 Tests, zwei opt-in gegen PostgreSQL): Sichtbarkeit mit Gegenprobe (nicht
  freigegeben, zurückgenommen, beseitigt, erledigt, verworfen, fremder Auftrag), Zurücknehmen der Freigabe (Liste, Foto,
  Meldung), rekursiver Scan der Positivliste mit Gegenprobe an der Büro-Antwort, untergeschobene Schlüssel kommen nicht an,
  Fotos nur über den Monteur-Weg (Beleg als Bild 404, Büro-Weg 403), Foto eines nicht freigegebenen oder fremden Mangels und
  über einen sichtbaren Mangel an das Foto eines anderen (404, Gegenprobe 200), Meldung mit zwei Fotos, acht ungültige
  Meldungen ohne Spur, Meldung an verborgene Mängel 404, doppelte Meldung mit derselben Kennung (auch nach dem Weiterschreiben
  des Büros), fremde Kennung 400, UNIQUE in der Datenbank, Rückfall auf die gespeicherte Meldung, Büro ohne Mitarbeiter 422,
  Seite `/mobil`, Migration; PostgreSQL: zwei gleichzeitige Meldungen mit derselben Kennung (die zweite wartet, ein
  Eintrag), Meldung gegen gleichzeitiges Zurücknehmen der Freigabe (wartet, 409).
- `test_v326`: Monteurswelt mit freigegebenem Mangel (Dachfläche, Ort, Frist, Foto, Beleg, Haltung) -- Liste und Foto 200,
  Wortprüfung ohne Fund; die Abnahme-Prüfung schließt den eigenen Weg des Monteurs aus (+1 Test).
- Volle Suite 2802 grün (mit den opt-in-Tests gegen PostgreSQL).
- Gegen PostgreSQL 17 über das Scratchpad-Plugin: `test_v354`, `test_v353`, `test_v351`, `test_v326` -- 133 grün, rot nur der
  bekannte Migrationstest von `test_v351` (rohes SQL, erfundene Fremdschlüssel).
- Migration: SQLite hin/zurück/hin, `alembic check`; PostgreSQL 17 im Wegwerf-Schema: Kette bis head, Meldung samt
  Wiederholung über den App-Code (Prüfung stimmt), downgrade (Spalte weg, beide Einträge bleiben), upgrade, `check` sauber,
  Prüfung stimmt, `current` = head; leeres Schema hin/zurück/hin.
- Gegenproben (Schutz ausgehebelt, Datei byte-genau zurück): 22 von 22 rot, darunter drei gegen PostgreSQL (Wiederholung
  unter der Sperre, Sperre des Mangels, Freigabe unter der Sperre).
- Klicktest `scripts/klicktest_maengel_monteur.py` 20/20 (412 px dunkel und hell, Büro 1400 px hell); unverändert grün
  `klicktest_maengel.py` 35/35, `klicktest_monteur_navigation.py` 27/27, `klicktest_bedenkenanzeige.py` 22/22 (`/mobil`).

### Nebenbefunde 1.8.52 (nur gemeldet)

1. **Keine Nachricht ans Büro bei einer Meldung**: die Aufgabe zum Mangel bleibt unverändert, "beseitigt" sieht das Büro nur
   auf der Auftragsseite. Möglich wäre eine Folge "Beseitigung abnehmen" -- nicht gebaut. **Erledigt seit 1.8.54**: "beseitigt"
   legt die Aufgabe "Beseitigung abnehmen lassen" im Büro-Eingang an.
2. **Datumsanzeige in `/mobil`** (`fmtDate()`, bestehend) ohne führende Null ("4.10.2026"), im Büro "04.10.2026".
3. **Speicher**: eine Meldung liest bis zu 30 MB Fotos in den Speicher (wie im Büro); Handyfotos haben oft 3–8 MB. Bei zwei
   Arbeitsprozessen und gleichzeitigen Meldungen das Doppelte -- im Budget, aber erwähnt.
4. **Monteur ohne Zuordnung an der AV, mit eigenem Bericht** sieht die freigegebenen Mängel dieses Auftrags (Weg 2 von
   `field_may_access_order()`) -- folgerichtig, aber vielleicht nicht gewollt (Festlegung 1).

---

## Umsetzung 1.8.53 und 1.8.54 (05.10.2026) -- Runde 2c-2b, Nacharbeiten

Betreibervorgabe (gekürzt): (1) Benachrichtigungsmails zu Aufgaben ohne Inhalt der Aufgabe, nur Art und Link, mit
Strukturtest über alle Aufgaben-Mails; (2) wird ein Mangel "beseitigt" (Monteur oder Büro), ist die Aufgabe "Mangel
beseitigen" erledigt und es entsteht "Beseitigung abnehmen lassen", zurück auf "offen" wieder "Mangel beseitigen" -- der
Mangel bleibt die Wahrheit; (3) zur Meldung "beseitigt" ein optionaler kurzer Hinweis des Monteurs, nur intern sichtbar;
(4) CLAUDE.md: `update.sh` liegt unter `/home/tobias/update.sh` und probt selbst gegen die Spielwiese. Festlegungen
1.8.51/1.8.52 bestätigt außer "kein Text zur Meldung" (1.8.52 Nr. 5, durch Punkt 3 ersetzt) und der Sperre (1.8.50 Nr. 3
und 4, weiter offen).

### Punkt 1 (1.8.53): Aufgaben-Mails ohne Inhalt

- `app/tasks.py::notify_task_assignment()`: Betreff immer `TASK_MAIL_SUBJECT` ("Neue Aufgabe im ERP"), Text nur Art und
  Link. Art = `task_mail_kind(source_module)` (Mangel, Einsatzbericht, Wartungsvertrag, Checkliste, Eingangsrechnung,
  Betriebsmittel, Betriebskosten, sonst "allgemeine Aufgabe"); Link = `task_mail_link()`, `/tasks?task=<id>` (öffnet die
  Aufgabe im Editor), absolut nur mit `GeneralSettings.public_base_url` (Einstellungen → Allgemein → "Öffentliche
  Adresse"), sonst als Pfad -- die Mail entsteht in der Geschäftslogik, ohne Anfrage. Keine Anrede mit Vornamen mehr.
- `tests/test_v355_aufgaben_mail_ohne_inhalt.py` (18 Tests): AST über `app/` -- jeder `dispatch_email()`-Aufruf mit
  konstanter Versandart (Ausnahme `send_notice_letter()`, Art aus `LETTER_KINDS`), Versandart "aufgabe" nur aus
  `TASK_MAIL_SENDERS`, dort an der Aufgabe nur `id`, `source_module`, `assigned_employee` und die Aufgabe nie an eine
  Hilfsfunktion; Versand über Anlegen, Bearbeiten und Übernehmen mit einer Markierung in jedem Textfeld der Aufgabe (aus den
  Spalten des Modells -- ein neues Feld ist automatisch dabei), in Projekt, Fälligkeit und Checkliste: keine Markierung in
  Betreff, Text (dekodiert), Rohtext oder Protokollzeile. Gegenproben (Titel im Betreff, Beschreibung, Projekt, Aufgabe an
  eine Hilfsfunktion) 4 von 4 rot.
- Volle Suite 2820 grün (mit den opt-in-Tests gegen PostgreSQL). Keine Migration. Angepasst: `test_v321` erwartet den
  neuen Betreff (zwei Stellen).
- **Auf dem Server prüfen**: ob Einstellungen → Allgemein → "Öffentliche Adresse" gesetzt ist -- sonst enthält die Mail
  statt eines klickbaren Links nur den Pfad.

### Punkt 2 (1.8.54): die Aufgabe folgt dem Status

- **Neue Spalte** `defect_events.task_id` (Migration `d5479410d4ff`, nullable, ohne Fremdschlüssel wie `defects.task_id`,
  nicht im gebundenen Inhalt): die Aufgabe, die ein Eintrag angelegt hat. Gesetzt beim Einfügen -- `_append()` erledigt
  die bisherige Aufgabe und legt die neue an, BEVOR der Eintrag entsteht (danach ist er unveränderlich), alles in einem
  Commit unter der Sperre des Mangels.
- **Welche Aufgabe** (`STATUS_TASKS`, `TASK_KINDS`): "beseitigt" (Büro über `set_status()` oder Monteur über
  `report_remedied()`) -> "Beseitigung abnehmen lassen"; zurück auf "offen" -> "Mangel beseitigen". "Beseitigung
  abgenommen", "erledigt ohne Beseitigung" und Verwerfen erledigen die aktuelle Aufgabe wie bisher.
- **Aktuelle Aufgabe** `current_task(defect, events)`: die des letzten Eintrags mit Aufgabe, sonst die beim Erfassen.
  Die Auftragsseite zeigt sie mit Art ("Aufgabe (Beseitigung abnehmen lassen): …", Link `/tasks?task=<id>`), der Verlauf
  "Aufgabe „…“ angelegt" am Eintrag.
- **Titel**: "Beseitigung abnehmen lassen – Mangel aus Abnahme <Auftrag> – <Ort>: <Kurzfassung>" bzw. "Erneut beseitigen –
  …"; die Aufgabe beim Erfassen behält ihren Titel. Beschreibung nur Metadaten (Mangel Nr., Datum, wer, "in der
  Monteursansicht"), nie Mangeltext, Begründung oder Hinweis des Monteurs. Ohne Zuständigkeit, Sichtbarkeitsgrenze
  `buero_auftrag`, Verweis auf den Mangel (`source_url`).
- **Der Mangel bleibt die Wahrheit**: eine von Hand erledigte Aufgabe ändert am Mangel nichts (Hinweis auf der Seite wie
  bisher); der nächste Statuswechsel legt trotzdem die nächste an.

### Punkt 3 (1.8.54): Hinweis des Monteurs zur Meldung

- `FieldDefectRemedied.note` (optional, höchstens 500 Zeichen, sonst 422; weiter `extra="forbid"`), in
  `report_remedied(note=…)` gekürzt (`_clean`, leer -> kein Text) und als Text des Eintrags (`reason`) gespeichert -- im
  gebundenen Inhalt, also mitversiegelt.
- **Nur intern sichtbar**: die Büro-Seite beschriftet ihn "Hinweis aus der Monteursansicht" (statt "Begründung"); in
  `/mobil` erscheint er nie (die Positivliste `FieldDefectOut` kennt keinen Verlauf, auch nicht nach "zurück auf offen",
  auch nicht für andere Monteure), nicht in der Antwort der Meldung, nicht in Aufgabe oder Aufgaben-Mail.
- `/mobil`: Feld "Hinweis (optional, nur fürs Büro sichtbar)" unter den Fotos.

### Punkt 4 (1.8.54): CLAUDE.md

Serverumgebung ("Einspielen"), "Der Weg einer Änderung auf den Server" und Regel 16: `/home/tobias/update.sh` probt eine
Migration selbst gegen `spielwiese`; kein einzelner `alembic`-Befehl, auch nicht für die Probe. Der bisher dort stehende
Probe-Befehl und die offene Frage aus 1.8.51 sind entfernt.

### Festlegungen 1.8.54 (bestätigt am 05.10.2026, Vorgabe 2c-2c; Nr. 3 seit 1.8.55 zur aktuellen Frist)

1. **Eine offene Aufgabe je Mangel**: jeder Statuswechsel "beseitigt"/"offen" erledigt die aktuelle und legt die nächste
   an -- nie zwei offene gleichzeitig. Eine von Hand erledigte bleibt erledigt.
2. **Neue Aufgaben ohne Zuständigkeit** (Büro-Eingang wie beim Erfassen), auch wenn die bisherige übernommen war -- keine
   Übernahme der Zuständigkeit.
3. **Fälligkeit**: "Beseitigung abnehmen lassen" ohne; "Erneut beseitigen" zur ursprünglichen Beseitigungsfrist (ist sie
   vorbei, steht die Aufgabe gleich als überfällig da -- eine neue Frist gibt es am Mangel nicht).
4. **Titel**: Art vorangestellt ("Beseitigung abnehmen lassen – …", "Erneut beseitigen – …"), die Aufgabe beim Erfassen
   behält "Mangel aus Abnahme …".
5. **Ohne Aufgabenmodul**: keine neue Aufgabe; die bisherige wird trotzdem erledigt (wie beim Verwerfen seit 1.8.49).
6. **Bestand**: Mängel, die vor 1.8.54 auf "beseitigt" gesetzt wurden, haben noch ihre erste Aufgabe offen und keine
   "abnehmen lassen" -- der nächste Statuswechsel erledigt sie; nachträglich angelegt wird nichts.
7. **Hinweis des Monteurs**: höchstens 500 Zeichen, gespeichert als Text des Eintrags (dasselbe Feld wie die Begründung im
   Büro, im gebundenen Inhalt); ändern oder löschen lässt er sich nicht.
8. **Downgrade ohne Rückfrage**: verloren gehen nur die Verweise vom Eintrag auf seine Aufgabe; die Aufgaben bleiben, als
   aktuelle gilt danach wieder die beim Erfassen.

### Verifikation 1.8.54

- `tests/test_v356_maengel_aufgabe_und_hinweis.py` (14 Tests, einer opt-in gegen PostgreSQL): "beseitigt" im Büro und als
  Meldung (erste Aufgabe erledigt, "Beseitigung abnehmen lassen" offen, ohne Zuständigkeit, ohne Fälligkeit, Verweis,
  Metadaten ohne Mangeltext; Wiederholung derselben Kennung legt keine zweite an), zurück auf offen ("Erneut beseitigen"
  zur Frist) und wieder beseitigt und abgenommen (vier Aufgaben, nie zwei offen), Erledigung und Verwerfen nach "zurück auf
  offen" erledigen die aktuelle, von Hand erledigte Aufgabe ändert den Mangel nicht, ohne Aufgabenmodul keine neue,
  Aufgabe und Eintrag in einer Transaktion (Fehler beim Anlegen: weder Eintrag noch Aufgabe noch Fotos), Hinweis
  gespeichert, versiegelt, im Büro sichtbar, in `/mobil` für beide Monteure nie (auch nach "zurück auf offen"), optional,
  gekürzt, höchstens 500 Zeichen, andere Felder weiter 422, Beschriftung auf Büro- und Monteurseite, Migration;
  PostgreSQL: Meldung wartet auf das gleichzeitige "beseitigt" des Büros und bekommt 409 -- ein Eintrag, eine neue Aufgabe.
- Volle Suite 2834 grün (mit den opt-in-Tests gegen PostgreSQL).
- Angepasst: `test_v351` ("beseitigt erledigt noch nichts" gilt nicht mehr: die erste Aufgabe ist erledigt, die neue offen,
  am Ende alle erledigt), `test_v354` (Kommentar, Art der aktuellen Aufgabe).
- Gegenproben (Schutz ausgehebelt, Dateien byte-genau zurück): 13 von 13 rot -- keine Aufgabe nach "beseitigt" bzw.
  "offen", bisherige bleibt offen, nur die beim Erfassen erledigt, aktuelle immer die beim Erfassen, Aufgabe mit eigenem
  Commit, Eintrag ohne Verweis, Hinweis nicht gespeichert, Hinweis in `/mobil`, ohne Längengrenze, nicht gekürzt, im Büro
  als "Begründung", kein Hinweisfeld in `/mobil`.
- Migration `d5479410d4ff`: SQLite hin/zurück/hin, `alembic check`; PostgreSQL 17 im Wegwerf-Schema: Kette bis
  `6c7610e54ce3`, head, Mangel über den App-Code (Meldung mit Hinweis -> "Beseitigung abnehmen lassen", zurück auf offen ->
  "Erneut beseitigen"; Prüfung stimmt), downgrade (Spalte weg, 3 Einträge und 3 Aufgaben bleiben), upgrade, `check`
  sauber, Prüfung stimmt, `current` = head; leeres Schema hin/zurück/hin. **Eigener Fehler dabei**: der erste Lauf der
  Probe fiel in die laufenden Gegenproben, die `app/defects.py` gerade ausgehebelt hatten -- er zeigte nach der Meldung
  keine neue Aufgabe. Wiederholt nach den Gegenproben, Ergebnis wie oben; kein Befund am Code.
- Klicktest `scripts/klicktest_maengel_monteur.py` 27/27 (neu: Hinweisfeld mit Grenze und Beschriftung, Büro sieht
  "Hinweis aus der Monteursansicht", "Aufgabe „Beseitigung abnehmen lassen“ angelegt" und die Aufgabenzeile mit Link;
  zurück auf offen: wieder in `/mobil` ohne Hinweis, im Büro "Erneut beseitigen").

### Nebenbefunde 1.8.53/1.8.54 (nur gemeldet)

1. **Versandprotokoll der Aufgaben-Mails**: auch ohne Inhalt verrät die Zeile Empfänger und Zeitpunkt einer Zuweisung --
   deshalb bleibt sie nur für Admins sichtbar (unverändert seit 1.8.17).
2. **Öffentliche Adresse**: ohne sie trägt die Aufgaben-Mail nur den Pfad `/tasks?task=<id>` (siehe Punkt 1); ob sie auf
   dem Server gesetzt ist, ist nicht geprüft.
3. ~~**"Erneut beseitigen" zur ursprünglichen Frist**~~ -- seit 1.8.55 mit optionaler neuer Frist (siehe "Umsetzung 1.8.55").
   Ursprünglicher Text: ist meist sofort überfällig (Festlegung 3) -- eine neue Frist nach einer
   misslungenen Nachbesserung gibt es am Mangel nicht; das wäre ein eigener Eintrag im Verlauf.
4. **Monteur mit eigenem Bericht, ohne Zuordnung an der AV** (Nebenbefund 4 aus 1.8.52) sieht freigegebene Mängel weiterhin
   -- unverändert, Entscheidung offen.

---

## Umsetzung 1.8.55 (05.10.2026) -- Runde 2c-2c, Punkt 0 (Vorweg)

Betreibervorgabe 2c-2c (gekürzt): Unterschriften in Checklisten härten, Fundament für das Abnahmeprotokoll; Festlegungen
1.8.53/1.8.54 bestätigt. Vorweg: (a) "zurück auf offen" mit optionaler neuer Frist im Eintrag, Aufgabe und Monteur-Sicht nutzen
die jeweils aktuelle; (b) jede Änderung für eine Gegenprobe trägt den Marker GEGENPROBE, ein Dauertest schlägt an, sobald er
unter `app/` steht, als Regel in CLAUDE.md; (c) Vertragsfassungen entschieden, nur ins Archiv, nicht bauen. Danach: (1)
Abschnittsunterschrift prüft die Pflichtfelder oberhalb, (2) eine gemeinsame Prüfung für alle Unterschriften, leeres Bild
abgelehnt, mit Strukturtest, (3) Unterzeichner je Unterschriftsfeld mit Siegel und Fassung des Siegelformats, (4)
Zeichenfläche nach Drehen oder Größenänderung neu vermessen.

### Punkt 0a: neue Frist bei "zurück auf offen"

- **Neue Spalte** `defect_events.due_on` (Migration `90a5ff1e1714`, nullable Datum). Gesetzt nur bei "zurück auf offen" und
  nur, wenn das Büro eine neue Frist angibt (`DefectStatusChange.due_on`, Feld "Neue Beseitigungsfrist (optional …)" im
  Status-Dialog, nur bei "offen" sichtbar). Nicht vor heute (Europe/Berlin); bei jedem anderen Status 400.
- **Aktuelle Frist** `current_due(defect, events)`: die des letzten Eintrags mit einer, sonst die beim Erfassen. Die Aufgabe
  "Erneut beseitigen" ist zur neuen Frist fällig, ohne neue zur aktuellen (also einer früher neu gesetzten, nicht zwingend der
  beim Erfassen). Büro: `remedy_due_on` ist jetzt die aktuelle, dazu `remedy_due_on_original`/`remedy_due_changed` ("neu
  gesetzt; beim Erfassen: …"), Überschreitung nach der aktuellen, der Verlauf zeigt "Neue Beseitigungsfrist: …". `/mobil`:
  `remedy_due_on` und Überschreitung nach der aktuellen, Sortierung ebenso -- die Positivliste `FieldDefectOut` bleibt gleich.
- **Gebundener Inhalt**: `event_content()` nimmt `due_on` nur auf, wenn gesetzt. So bleiben die Prüfsummen aller früheren
  Einträge gültig, ohne neue Fassung des Prüfsummenformats; ein am ORM vorbei gesetztes, geändertes oder entferntes Datum
  ändert den Inhalt und erscheint als "Verlauf weicht von seiner Prüfsumme ab".
- **Downgrade** verweigert, solange ein Eintrag eine neue Frist trägt (sie ginge verloren, und 1.8.54 rechnete den Eintrag
  ohne sie nach -- Prüfsumme falsch).

### Punkt 0b: Regel 24 -- Marker GEGENPROBE

Jede Änderung in `app/`, die für eine Gegenprobe einen Schutz aushebelt, trägt den Marker `GEGENPROBE` (Kommentar in der
geänderten Zeile). `tests/test_v357_gegenprobe_marker.py` durchsucht jede Textdatei unter `app/` (Python, Vorlagen, alles)
und nennt Datei und Zeile; ein zweiter Test prüft die Suche selbst. Anlass: in 1.8.54 lief eine Migrationsprobe, während
eine Gegenprobe `app/defects.py` ausgehebelt hatte ("Verifikation 1.8.54"). Der Gegenproben-Läufer dieser Runde (Scratchpad)
verlangt den Marker in jeder Ersetzung und prüft nach dem Zurücksetzen die Prüfsumme der Datei.

### Punkt 0c: Zurückziehen einer Vertragsfassung -- entschieden am 05.10.2026, nicht gebaut

Auf den Vorschlag aus "Umsetzung 1.8.51", Punkt 0a:
1. **Zurückziehen wie vorgeschlagen**: nur bei Status "festgeschrieben" (nicht nach der Unterschrift), Büro,
   Pflicht-Begründung; bedingtes UPDATE mit Siegel wie beim Verwerfen der Abnahme (`withdrawn_at`/`_by_name`/`_reason`/
   `withdraw_sha256` an `OrderContractVersion`), Vertrag zurück auf "entwurf", Zeile in der Änderungshistorie. Die Fassung
   bleibt sichtbar und in der Ablage, wird aber nicht mehr versendet oder zugestellt.
2. **Eine Regel** `contract_lock(db, order)`: eine **gültige** Fassung (festgeschrieben oder unterschrieben, nicht
   zurückgezogen, nicht überholt) sperrt, was sie enthält -- den Kunden immer, Dauer und Leistungsart nur, wenn sie
   `{gewaehrleistung}` nutzt. Ersetzt `check_client_change()` (Teil Vertrag) und `warranty_contract_lock()`.
3. **"Neue Fassung" entfällt** -- korrigiert wird nur über Zurückziehen und neu Festschreiben.
4. **Versendete Fassung zurückziehen erlaubt**: mit Hinweis auf den Versand (Versandverlauf) und einer Aufgabe "Kunden
   informieren". Eine spätere Unterschrift auf einer zurückgezogenen Fassung (z. B. Papier, das der Kunde vor dem Zurückziehen
   bekommen hat) wird nicht still abgelehnt, sondern mit Warnung erfassbar.

Offen für die Umsetzung (nicht entschieden, nur notiert): ob eine mit Warnung erfasste Unterschrift auf einer
zurückgezogenen Fassung diese wieder gültig macht (und damit die Sperren nach Nr. 2 auslöst) oder nur als Nachweis
festgehalten wird.

### Festlegungen 1.8.55 (bestätigt am 05.10.2026, Vorgabe 2c-2d)

1. **Neue Frist nur bei "zurück auf offen"**, optional; bei jedem anderen Status abgelehnt (400), nicht beim Erfassen
   nachträglich änderbar.
2. **Nicht vor heute** (Europe/Berlin), heute erlaubt -- anders als beim Erfassen (dort: nicht vor der Abnahme).
3. **Ohne neue Frist gilt die zuletzt gesetzte weiter** (auch für die Aufgabe), nicht die beim Erfassen.
4. **Eine einmal gesetzte Frist lässt sich nicht wieder entfernen**, nur durch eine neue ersetzen.
5. **Im gebundenen Inhalt nur, wenn gesetzt** -- keine neue Fassung des Prüfsummenformats für Einträge (Abwägung: eine
   Fassung 2 hätte jeden neuen Eintrag für ein Downgrade unprüfbar gemacht, auch ohne Frist).
6. **Downgrade verweigert**, sobald ein Eintrag eine neue Frist trägt.
7. **Monteur** sieht nur die aktuelle Frist, nicht, dass sie neu gesetzt wurde.

### Verifikation 1.8.55

- `tests/test_v357_maengel_neue_frist.py` (11 Tests): neue Frist am Eintrag, an der Aufgabe "Erneut beseitigen", in der
  Büro-Ansicht mit ursprünglicher und im Verlauf, im gebundenen Inhalt; ohne neue Frist gilt die zuletzt gesetzte; neue Frist
  ohne ursprüngliche; Überschreitung in Büro und `/mobil` nach der aktuellen; abgelehnt bei anderem Status, bei "beseitigt" und
  in der Vergangenheit (nichts gespeichert, heute erlaubt); Angriff am ORM vorbei (gesetzt, geändert, entfernt -> "weicht
  ab", zurück -> stimmt); Einträge ohne Frist mit unveränderter Prüfsumme; Feld auf der Seite; Migration mit verweigertem
  Downgrade. `tests/test_v357_gegenprobe_marker.py` (2).
- Gegenproben (mit Marker, Dateien byte-genau zurück, Prüfsumme verglichen): 10 von 10 rot -- Frist nicht im Inhalt, Aufgabe
  mit der Frist beim Erfassen (mit und ohne neue), Büro und Monteur mit der Frist beim Erfassen, neue Frist bei anderem Status,
  in der Vergangenheit, nicht gespeichert, Downgrade ohne Verweigerung, Marker in `app/berlin_time.py` (Dauertest).
- Migration `90a5ff1e1714`: SQLite hin/zurück/hin, `check`; PostgreSQL 17 im Wegwerf-Schema: Kette bis `d5479410d4ff`, head,
  Mangel über den App-Code (beseitigt, zurück auf offen mit neuer Frist; aktuelle Frist und Prüfung stimmen), Downgrade
  verweigert, `current` = head, `check` sauber; leeres Schema hin/zurück/hin, `check`, `current`.
- Volle Suite 2847 grün (mit den opt-in-Tests gegen PostgreSQL). Dabei rot und behoben: `test_v339` -- der Aufruf
  `klicktest_main(..., uhr="10:00")` in `klicktest_maengel.py` stand nach meiner Änderung auf zwei Zeilen, die Prüfung auf feste
  Uhr sucht ihn auf einer (eigener Fehler, vom Wächter gefunden).
- Klicktest `scripts/klicktest_maengel.py` 39/39 (neu: dritter Mangel, Feld nur bei "zurück auf offen", Frist am Mangel mit
  "(neu gesetzt; beim Erfassen: keine)", im Verlauf, Aufgabe "Erneut beseitigen" zur neuen Frist).
- **Eigener Fehler aus 1.8.54, mitbehoben**: `klicktest_maengel.py` war nach "Aufgabe folgt dem Status" nicht nachgezogen worden
  -- vier Prüfungen erwarteten noch die Aufgabenzeile "Aufgabe: …" und zwei statt drei Aufgaben (seit 1.8.54 "Aufgabe (Art): …"
  und "Beseitigung abnehmen lassen" nach "beseitigt"). Erwartungen auf das bestätigte Verhalten gebracht; am Code kein Befund.


---

## Umsetzung 1.8.56 (05.10.2026) -- Runde 2c-2c, Punkte 1 und 2: Pflichtangaben vor der Unterschrift, eine Bildprüfung

### Punkt 1: Abschnittsunterschrift prüft die Pflichtangaben oberhalb

- `app/checklists.py::add_attachment()` (Feldtyp "unterschrift"): vor allem anderen am Bild
  `missing_required_labels(checklist, before=field)` -- alle Felder oberhalb der Unterschrift, die sie versiegelt (ohne
  Hinweise und Unterschriften), mit derselben Regel wie beim Abschließen (Pflicht, Mindestanzahl bei Foto/Beleg, "entfällt"
  ist eine Antwort). Fehlt etwas: 400 "Vor der Unterschrift „…“ fehlen noch Pflichtangaben: …", nichts gespeichert, kein
  Bild auf der Platte. Gilt für jede Rolle, auch fürs Büro und für eine neue `client_uuid`; eine Wiederholung einer schon
  gespeicherten bleibt 200.
- `checklist_to_dict()` liefert `missing_before_signature` (je Unterschriftsfeld die fehlenden Beschriftungen, nur im
  Entwurf). `checklist.html`: Hinweis über der Zeichenfläche ("Vor der Unterschrift fehlen noch: …", `data-missing-before`),
  der jeder gespeicherten Eingabe folgt; "Unterschrift übernehmen" speichert erst offene Eingaben und bricht dann mit dem
  Hinweis ab, ohne Rückfrage. Die Rückfrage vor dem Versiegeln nennt keine fehlenden Pflichtangaben mehr (es kann keine
  geben); die Warnung "Pflichtangaben, die sich nicht mehr ergänzen lassen" in der Karte "Unterschrieben" bleibt für
  Unterschriften von vor 1.8.56.

### Punkt 2: eine Prüfung für alle Unterschriften

- Neues Modul `app/signature_image.py`: `check_signature_png(data, who)` -- vorhanden, höchstens 2 MB, ein PNG (am Inhalt
  erkannt, vollständig gelesen), höchstens 5000 Pixel je Seite und 12 Mio. Pixel (Speicherbudget: ein kleines PNG kann sich
  riesig entpacken), nicht leer (durchsichtig: ein sichtbares Pixel; deckend: ein dunkles); `signature_png_from_base64()`
  für die JSON-Wege. Aufgerufen von Checkliste (`add_attachment()`), Einsatzbericht (`sign_report()`, Monteur und Kunde)
  und Vertrag auf dem Gerät (`sign_contract_on_device()`, Kunde und Betrieb), jeweils bevor etwas gespeichert wird.
- **Bestand vorher**: der Vertrag prüfte seit 1.8.34 PNG und "nicht leer" (`_has_ink`, jetzt hierher verschoben), die
  Checkliste nur "Pillow kann es öffnen" (jedes Format, auch ein leeres Bild), der Einsatzbericht nur die Größe -- er schrieb
  die Bytes ungeprüft auf die Platte (über die API auch "AAAA"). Die beiden Router-Hilfen zum Base64 sind entfallen.
- **Strukturtest** `tests/test_v358_unterschrift_pruefung.py`: (a) jede Spalte, deren Name nach Unterschrift klingt
  (`signature`, `signer`, `signed`, `unterschrift`, `image`), steht eingeordnet in `SPALTEN` -- "bild" (verweist auf ein
  gezeichnetes Bild) oder mit Grund; eine neue Spalte ist rot, bis sie eingeordnet ist; (b) per AST jede Funktion unter
  `app/`, die ein Unterschriftsbild speichert (Zuweisung an eine "bild"-Spalte, Modell-Konstruktor mit so einem
  Schlüsselwort, Anlegen einer `ChecklistAttachment`), ruft `check_signature_png()` auf -- oder jeder ihrer Aufrufer im
  Modul tut es (so `_finish()` des Vertrags über `sign_contract_on_device()`), ausgenommen mit Grund nur der Papier-Scan
  (`record_paper_signature()`); (c) keine zweite Leer-/PNG-Prüfung außerhalb des Moduls.

### Festlegungen 1.8.56 (bestätigt am 05.10.2026, Vorgabe 2c-2d)

1. **"Oberhalb" heißt alle Felder vor der Unterschrift**, nicht nur ihr Abschnitt -- die Unterschrift versiegelt sie alle.
2. **Pflicht-Unterschriften oberhalb zählen nicht** (seit 1.8.14 bleibt eine obere Unterschrift nach einer unteren möglich,
   z. B. Teilnehmer nach dem Unterweisenden).
3. **Felder "nur Büro" oberhalb zählen mit**: eine Unterschrift des Monteurs unter einem Büro-Abschnitt (z. B. Wegfall unter
   der Anzeige) wartet, bis das Büro dessen Pflichtangaben ausgefüllt hat -- sonst versiegelte sie die Büro-Felder leer.
4. **Reihenfolge der Prüfungen** an der Checkliste: Entwurf, Feld, schon unterschrieben (409), Pflichtangaben (400), Bild
   (400), Name -- an Bericht und Vertrag die Bildprüfung an der Stelle der bisherigen Größenprüfung (vor den inhaltlichen).
5. **PNG überall Pflicht**: die Checkliste nimmt keine JPEG-Unterschrift mehr an (die Zeichenfläche liefert PNG).
6. **Grenzen**: 2 MB wie bisher, dazu 5000 Pixel je Seite und 12 Mio. Pixel; "nicht leer" wie beim Vertrag seit 1.8.34 (ein
   Punkt genügt -- keine Mindestgröße der Unterschrift, die Seite verlangt schon einen Strich).

### Verifikation 1.8.56

- `tests/test_v358_unterschrift_pruefung.py` (27): die Prüfung (neun Ablehnungen, Annahme durchsichtig und deckend, genau an
  der 2-MB-Grenze), Angriff je Weg über die API (Checkliste leer/weiß/JPEG, Bericht Monteur/Kunde leer/weiß/JPEG/kein Bild,
  Vertrag Kunde/Betrieb leer -- 400, nichts gespeichert, kein Bild auf der Platte, mit Strich angenommen), Strukturtest (drei
  Teile), Pflichtangaben (oberhalb ja, darunter nein, "entfällt" genügt, Mindestanzahl Fotos, Pflicht-Unterschrift oberhalb
  nicht, Liste je Unterschrift, Angriff über die API auch fürs Büro und mit neuer Kennung, Seite).
- Angepasst (Attrappen statt echter Bilder bzw. Unterschrift ohne Pflichtangabe): `TINY_PNG` in `test_v203`/`test_v213`
  mit einem dunklen Pixel, `b"fake-signature-bytes"`/`b"sig"` durch `TINY_PNG` in `test_v212`, `test_v213`, `test_v214`,
  `test_v222`, `test_v223` (zusammen 27 Stellen), "AAAA" in `test_v213`/`test_v214`, `test_v338` (Größengrenze mit echtem
  PNG), `test_v305` und `test_v318` (Pflichtangabe vor der Unterschrift).
- Gegenproben (Marker GEGENPROBE, Dateien byte-genau zurück): 14 von 14 rot.
- PostgreSQL (Wegwerf-Schemas über ein pytest-Plugin im Scratchpad): `test_v358` und die Checklisten-Unterschriftstests
  v305/v317/v318/v319 -- 100 grün. Keine Migration.
- Klicktests mit Unterschriften, alle 13 grün: `klicktest_checkliste_abschnitte.py` 28/28 (neu: Hinweis über der Brandwache,
  Unterschreiben ohne Pflichtangabe auf der Seite abgelehnt ohne Rückfrage, Hinweis weg nach der Antwort),
  `klicktest_checkliste_unterschrift.py` 26/26 (umgestellt: der Ablauf von 1.8.13 "unterschreiben, obwohl eine Pflichtangabe
  fehlt, Warnung danach" ist nicht mehr möglich -- jetzt Ablehnung, Antwort "Nein", Unterschrift, Büro verwirft, Korrektur auf
  "Ja"), `klicktest_beleg_und_hinweis.py` 24/24 (Befüllung mit einem weißen Unterschriftsbild -- jetzt abgelehnt, auf ein
  dunkles umgestellt), unverändert grün: `_verwerfen` 23, `_zweck` 28, `behinderungsanzeige` 35, `_versand` 41,
  `_abschluss` 43, `bedenkenanzeige` 22, `_versand` 20, `versandverlauf` 32, `vertrag_unterschrift` 43, `vertrag_abschrift` 26.
- Volle Suite 2874 grün (mit den opt-in-Tests gegen PostgreSQL).


---

## Umsetzung 1.8.57 (05.10.2026) -- Runde 2c-2c, Punkt 3: Unterzeichner je Unterschriftsfeld

### Vorlage

- Neue Spalte `checklist_template_fields.signer_mode` (Migration `5e562a4a172b`, NOT NULL, `server_default` "frei"):
  "frei" (Name eintippen wie bisher), "konto" (angemeldetes Konto), "auftraggeber" (Auftraggeber laut Auftrag), "beteiligter"
  (Beteiligter des Projekts). `SIGNER_MODES` in `app/checklist_templates.py`. Editor: Auswahl "Unterzeichner" am
  Unterschriftsfeld; in der veröffentlichten Fassung gesperrt wie jede Eigenschaft.
- Regeln: nur an Unterschriftsfeldern (sonst "frei"); "konto" und "auftraggeber" nie mit "mehrere Unterschriften" (eine
  Person); "auftraggeber"/"beteiligter" nur, wenn die Vorlage ausschließlich am Auftrag gilt -- geprüft beim Veröffentlichen
  (`order_only_signer_labels()`), beim Ändern der Kontexte (nicht abgelöste Fassungen) und beim Unterschreiben.

### Unterschreiben (`app/checklists.py::_signer()`, `add_attachment()`)

- "frei": `signer_name` Pflicht (höchstens 160 Zeichen). Alle anderen: ein mitgeschickter Name ist 400 ("Den Namen setzt hier
  der Server"), `participant_id` nur bei "beteiligter" (sonst 400).
- "konto": Name und ID des angemeldeten Kontos aus dem Router (`account_user_id`/`account_name`), dasselbe Konto höchstens
  einmal je Feld (409).
- "auftraggeber": `Order.customer_name` als Schnappschuss; nur an einer Checkliste zum Auftrag (sonst 400).
- "beteiligter": `participant_id` Pflicht, Beteiligter dieses Projekts, nicht archiviert, höchstens einmal je Feld (409); Name
  (`contact_display_name()`) und Rolle als Schnappschuss; die Vollmacht zur Abnahme über
  `app/acceptances.py::_frozen_power_of_attorney()` (Häkchen, Datei, stimmende Prüfsumme) als Kopie neben die Unterschrift
  (`vollmacht-<uuid>.<endung>` im Ordner der Checkliste, `signer_poa_*`); ohne sie wird die Unterschrift erfasst und
  gekennzeichnet ("⚠ ohne Vollmacht zur Abnahme"). Ein Beteiligter, der unterschrieben hat, lässt sich nicht mehr aus dem
  Projekt entfernen (409, wie bei Abnahme und Mangel).
- `checklist_to_dict()` liefert `signer_choices` je Feld mit Auftraggeber/Beteiligtem (Name des Auftraggebers bzw. Beteiligte
  mit Name, Rolle, Vollmacht ja/nein, schon unterschrieben) -- auch an Monteure, ohne Kontaktwege und Belege. Die Seite zeigt
  "Unterschreibt: … (…)" statt des Namensfelds bzw. die Auswahl mit Hinweis ohne Vollmacht; an jeder Unterschrift die Zeile
  "Unterzeichner: …", fürs Büro mit Link auf die eingefrorene Vollmacht
  (`GET /api/checklist-attachments/{id}/power-of-attorney`, ab `buero_auftrag`, nosniff, 409 bei abweichender Prüfsumme).
  PDF: dieselbe Zeile unter Name und Zeitpunkt (`signer_text()`).

### Siegel

- Neue Spalten an `checklist_attachments`: `signer_kind`, `signer_user_id` (ohne Fremdschlüssel -- Befund "Benutzer löschen"
  1.8.13), `signer_participant_id` (FK, Index), `signer_role`, `signer_poa_stored_filename`/`_content_type`/`_sha256`,
  `seal_format`. Neue Unterschriften: `seal_format` 3, die Kopie trägt `"v": 3` und `"signer"` (`signer_content()`: Art,
  Name, Konto, Beteiligter, Rolle, Vollmacht mit Prüfsumme und Typ, Zeitpunkt, Prüfsumme des gespeicherten Bilds). Der
  Zeitpunkt wird beim Anlegen auf ganze Sekunden gesetzt.
- `check_signature()` rechnet nach dem Format der Unterschrift nach: 3 mit Unterzeichner, leer wie bisher (Format 2 mit Kopie
  bzw. 1.8.13 ohne) -- vorhandene Siegel bleiben gültig; ein unbekanntes Format ist "abweichend: Siegelformat". Ein am ORM vorbei
  geändertes Format ändert den nachgerechneten Inhalt -- "abweichend". `_changed_fields()` nennt einen geänderten Unterzeichner
  (auch ein ausgetauschtes Bild) als "Unterzeichner".
- **ORM-Sperre**: eine Unterschrift ist nach dem Speichern bis auf die Spalten des Verwerfens unveränderlich, gelöscht wird sie
  nie (`ArchiveImmutableError`, `app/models.py`) -- auch ein Wechsel der Art "unterschrift" zu etwas anderem.
- Der Abschluss (1.8.15) bleibt im Format 2 -- er bindet je Unterschrift deren Prüfsumme, also seit 1.8.57 auch den Unterzeichner.

### Festlegungen 1.8.57 (bestätigt am 05.10.2026, Vorgabe 2c-2d)

1. **Vier Arten**: frei, angemeldetes Konto, Auftraggeber laut Auftrag, Beteiligter. Vorgabe "frei" -- alle vorhandenen Felder und
   Startvorlagen bleiben, wie sie sind; Systemfelder geben keinen Unterzeichner vor (umstellbar im Editor).
2. **Auftraggeber = Kunde laut Auftrag** (`Order.customer_name`, wie bei der Abnahme), ohne Namen der unterschreibenden Person bei
   Firmen -- wer für eine Firma unterschreibt und nicht der Auftraggeber selbst ist, gehört als Beteiligter mit Vollmacht erfasst.
3. **Vollmacht = Vollmacht zur Abnahme** (Häkchen und Beleg am Beteiligten, wie bei der Abnahme), die Empfangsvollmacht zählt nicht;
   ohne sie mit Warnung erfasst, nicht abgelehnt.
4. **Mitgeschickter Name bei festem Unterzeichner ist ein Fehler** (400), keine stille Umdeutung.
5. **Höchstens einmal je Feld** je Konto bzw. Beteiligtem; "konto" und "auftraggeber" nie "mehrere".
6. **Monteur sieht** in der Auswahl Name, Rolle und "ohne Vollmacht" der Beteiligten seines Auftrags, nicht den Beleg (403).
7. **Siegel mit Zeitpunkt und Prüfsumme des Bilds** -- über die Vorgabe (Name, Art, Vollmacht) hinaus; damit fällt auch ein
   ausgetauschtes Bild schon vor dem Abschluss auf. Zwei Unterschriften im selben Feld tragen deshalb verschiedene Prüfsummen.
8. **Auswahl liest die Vollmacht nicht**: "Vollmacht ja/nein" in der Auswahl folgt dem Stand am Beteiligten (Häkchen, Beleg,
   Typ); die Datei samt Prüfsumme liest erst das Unterschreiben -- sonst läse jede gespeicherte Antwort alle Vollmachten. Ist die
   Datei inzwischen kaputt, wird ohne Vollmacht erfasst (gekennzeichnet).
9. **Downgrade verweigert**, sobald eine Unterschrift im Format 3 oder ein Feld mit festem Unterzeichner existiert.

### Verifikation 1.8.57

- `tests/test_v359_unterzeichner.py` (29): Konto (Name und ID vom Konto, Siegel "v": 3 mit Unterzeichner und Prüfsumme des Bilds),
  Auftraggeber (Kunde laut Auftrag, späterer Kundenname am Auftrag ändert nichts), Beteiligter (Auswahl, Vollmacht eingefroren
  als Kopie, ohne Vollmacht gekennzeichnet, später ersetzte Vollmacht ändert Kopie und Siegel nicht, Abruf fürs Büro), frei wie
  bisher; Angriffe: falsche Angaben über die API (Name bei festem Unterzeichner, ohne Wahl, unbekannter Beteiligter,
  Beteiligter eines anderen Projekts, Beteiligter am falschen Feld, frei ohne Name -- je 400, nichts gespeichert), gleiche
  Kennung mit anderem Namen (dieselbe Antwort), derselbe Beteiligte zweimal (409), Änderung am ORM (fünf Spalten und Löschen:
  `ArchiveImmutableError`), Änderung per SQL (acht Fälle: Name, Art, Rolle, Konto, Vollmacht, Beteiligter, Format 2, Format leer
  -> "abweichend"), ausgetauschtes Bild ("Unterzeichner"), Unterzeichner einer veröffentlichten Fassung nicht änderbar; Regeln
  der Vorlage, altes Siegel (Format 2) bleibt gültig, Beteiligter mit Unterschrift bleibt im Projekt, Monteur sieht die Auswahl,
  nicht die Vollmacht; Seiten; Migration (Downgrade verweigert).
- Angepasst: `test_v358` (die neuen Spalten eingeordnet -- der Strukturtest aus 1.8.56 hat sie als neu gemeldet, wie gedacht),
  `test_v317` (Prüfsumme im Format 3 nachgerechnet; zwei Unterschriften im selben Feld haben jetzt verschiedene Summen),
  `test_v318` (Kopie "v": 3; Manipulationen per rohem UPDATE statt am ORM), `test_v319` (ein geänderter Name zeigt jetzt auch die
  Unterschrift selbst als "abweichend"), `test_v316` (Zeitstempel per rohem UPDATE), `tests/conftest.py` (`router_test_client`
  optional mit `user_id`/`display_name`).
- Gegenproben (Marker GEGENPROBE, Dateien byte-genau zurück): 16 von 16 rot. **Eine blieb zuerst grün**: "Beteiligter eines
  anderen Projekts" -- der Test nutzte eine nicht vorhandene ID und deckte die Projektprüfung gar nicht ab; mit einem echten
  Beteiligten des fremden Projekts nachgeschärft, danach rot.
- Migration `5e562a4a172b`: SQLite hin/zurück/hin, `check`; PostgreSQL 17 im Wegwerf-Schema: Kette bis `90a5ff1e1714`, head,
  Checkliste mit Unterschriften über den App-Code (Auftraggeber, Beteiligter mit Vollmacht, Konto -- alle Format 3,
  "unverändert"), Downgrade verweigert, `current` = head, `check` sauber; leeres Schema hin/zurück/hin. **Eigener Fehler, von
  der PostgreSQL-Probe gefunden**: der Name des Fremdschlüssels war 69 Zeichen lang, PostgreSQL erlaubt 63 (SQLite prüft das
  nicht) -- gekürzt auf `fk_checklist_attachments_signer_participant_id`, im Modell benannt (sonst ließe sich die Migration
  auf einer per `create_all()` angelegten Datenbank nicht zurücknehmen).
- PostgreSQL (pytest-Plugin): `test_v359`, `test_v358` und die Checklisten-Unterschriftstests v305/v317/v318/v319 -- 129 grün (114 Wegwerf-Schemas, danach entfernt). Dabei zwei Fehler in meinen eigenen Tests gefunden und behoben: ein Test-Konto ohne Zeile
  in `app_users` (unter PostgreSQL verlangt `checklists.created_by_user_id` eines) und `0`/`1` für Booleans im rohen SQL des
  Migrationstests (jetzt über die App-Funktionen angelegt).
- Klicktests: neu `scripts/klicktest_unterzeichner.py` 17/17; `klicktest_checkliste_verwerfen.py` 23/23 (umgestellt: die
  an der Sperre vorbei umbenannte Brandwache zeigt jetzt auch ihre eigene Unterschrift als "weicht ab: Unterzeichner"); unverändert
  grün: `_abschnitte` 28, `_unterschrift` 26, `_zweck` 28, `behinderungsanzeige` 35, `_versand` 41, `_abschluss` 43,
  `bedenkenanzeige` 22, `_versand` 20, `beleg_und_hinweis` 24, `versandverlauf` 32, `vertrag_unterschrift` 43.
- Volle Suite 2903 grün (mit den opt-in-Tests gegen PostgreSQL). **Eigener Fehler beim Prüfen**: zwei Läufe gegen
  PostgreSQL schrieben in dieselbe Ausgabedatei, die Zusammenfassung stammte vom alten Lauf vor der Konto-Korrektur -- in eine
  eigene Datei wiederholt (oben).

### Nebenbefunde 1.8.57 (nur gemeldet)

1. **`create_checklist()` meldet jede Integritätsverletzung als "Diese Kennung (client_uuid) ist bereits vergeben"** -- auch ohne
   Kennung, z. B. bei einem Fremdschlüssel unter PostgreSQL (in den Tests dieser Runde mit einem Konto ohne Zeile so aufgetreten).
   Der Text führt in die Irre; der SAVEPOINT-Zweig sollte nur bei gesetzter Kennung greifen.
2. **Systemfelder geben keinen Unterzeichner vor**: "Unterschrift Büro" der Behinderungs- und Bedenkenanzeige wäre ein Fall für
   "angemeldetes Konto" (die Wiederaufnahme nutzt schon das Büro-Konto für "i. A."). Eine Vorgabe im Zweck würde veröffentlichte
   Vorlagen als "weicht ab" melden -- deshalb nicht gesetzt, Entscheidung offen.
3. **Startvorlagen**: "Unterschrift Kunde" (Nachtragsmeldung) und ähnliche wären "Auftraggeber laut Auftrag" -- nur als Vorschlag,
   die Startvorlagen bleiben "frei".
4. **Zweck "abnahme" hat noch keine Systemfelder** -- das Abnahmeprotokoll (Fundament dieser Runde) wäre der nächste Schritt:
   Systemfelder mit Unterzeichner Auftraggeber/Beteiligter, Folge "Abnahme erfassen" aus der Checkliste.


---

## Umsetzung 1.8.58 (05.10.2026) -- Runde 2c-2c, Punkt 4: Zeichenfläche nach Drehen neu vermessen

- **Befund vorher**: `unterschriftsfeld()` (`app/templates/_unterschrift.html`, seit 1.8.34) maß die Fläche genau einmal beim
  Aufruf. Wurde das Tablet danach gedreht oder das Fenster schmaler, blieb die Pixelgröße der alten Breite: der Browser streckte
  das Bild, ein neuer Strich landete versetzt neben dem Finger (im Klicktest nachgestellt: quer gedreht lag der Strich nicht unter
  der Berührstelle), und die Auflösung passte nicht mehr. Betrifft Checkliste, Einsatzbericht und Vertrag gleichermaßen.
- **Jetzt**: die Fläche vermisst sich neu, sobald sich ihre angezeigte Größe oder die Geräteauflösung ändert -- `ResizeObserver`
  auf der Fläche plus `resize` am Fenster (Zoom ändert die Auflösung), gebündelt über `requestAnimationFrame`. Die Striche werden
  als Punkte gemerkt, in der Größe beim ersten Strich, und nach dem Vermessen gleichmäßig skaliert neu gezeichnet
  (`Math.min(Breite, Höhe)`-Verhältnis -- nie verzerrt, nichts abgeschnitten); die Strichstärke bleibt am Bildschirm gleich.
  Neue Striche werden in diese Basisgröße umgerechnet und liegen damit unter dem Finger. Unsichtbare Fläche (geschlossener
  Dialog): Vermessen wartet, bis sie sichtbar wird. Eine Fläche, die nicht mehr im Dokument hängt, meldet Beobachter und
  Fenster-Ereignis ab; ein erneuter Aufruf für dieselbe Fläche ersetzt den alten. Schnittstelle unverändert
  (`leer()`, `leeren()`, `alsBlob()`, `alsDataUrl()`, neu `vermessen()`), die drei Seiten bleiben wie sie sind.

### Festlegungen 1.8.58 (bestätigt am 05.10.2026, Vorgabe 2c-2d)

1. **Beim Drehen bleibt die Unterschrift erhalten**, gleichmäßig skaliert -- nicht leeren. Abgewogen: Leeren wäre einfacher und
   "was man sieht, ist was gezeichnet wurde", kostet aber eine schon geleistete Unterschrift, wenn das Gerät beim Weitergeben kippt.
2. **Gleichmäßig skaliert auf die kleinere Seite** -- eine quer gezeichnete Unterschrift wird hochkant kleiner, nie gestaucht.
3. **Strichstärke am Bildschirm gleich** (2,4 Pixel), nicht mitskaliert.
4. **Das PNG ist das, was gerade zu sehen ist** (in der aktuellen Pixelgröße) -- keine zweite, "originale" Fassung.

### Verifikation 1.8.58

- Neuer Klicktest `scripts/klicktest_zeichenflaeche.py` (Tablet 600 x 960 mit Geräteauflösung 2, Touch-Emulation, Striche über
  `Input.dispatchTouchEvent`, Drehen über `Emulation.setDeviceMetricsOverride` mit `screenOrientation`): 11/11 -- hochkant
  vermessen, Touch-Strich, quer neu vermessen, erster Strich sichtbar, zweiter Strich unter dem Finger, zurückgedreht, schmaler
  ohne Drehen, Unterschrift übernommen (Server: nicht leer, Siegel unverändert), Einsatzbericht nach dem Drehen vermessen.
  **Gegenprobe mit der Fläche von 1.8.57** (vor dem Einsetzen der neuen): 4 rot -- quer nicht neu vermessen, Strich nicht unter
  dem Finger, schmaler nicht vermessen, Einsatzbericht nicht vermessen.
- `tests/test_v360_zeichenflaeche.py` (4): Aufbau der Fläche (Beobachter, Fenster-Ereignis, gebündelt, Vermessen, unsichtbar
  später), Striche gemerkt und gleichmäßig neu gezeichnet, Abmelden, Schnittstelle der drei Seiten.
- Gegenproben am Template (Marker GEGENPROBE, Datei byte-genau zurück): 5 von 5 rot -- kein Beobachter, kein
  Fenster-Ereignis, verzerrt statt gleichmäßig, abgelöste Fläche bleibt angemeldet, Striche nicht gemerkt.
- Alle 14 Klicktests mit Unterschriften mit der neuen Fläche grün (`_abschnitte` 28, `_unterschrift` 26, `_verwerfen` 23,
  `_zweck` 28, `behinderungsanzeige` 35, `_versand` 41, `_abschluss` 43, `bedenkenanzeige` 22, `_versand` 20,
  `beleg_und_hinweis` 24, `versandverlauf` 32, `vertrag_unterschrift` 43, `vertrag_abschrift` 26, `unterzeichner` 17).
- Volle Suite 2907 grün (mit den opt-in-Tests gegen PostgreSQL). Keine Migration.

---

## Etappenplan 2c-2d (Vorgabe vom 05.10.2026, übernommen wie gegeben)

Stufe 2c-2d: Abnahmeprotokoll als Checkliste. Grundlage: der Befund aus 2c-2b. Festlegungen 1.8.55–1.8.58 bestätigt.

0. Vorweg:
   - Unterzeichner "Auftraggeber laut Auftrag": Pflichtangabe "Name der unterschreibenden Person" (optional Funktion), ohne
     Vorbelegung, im Siegel.
   - Vollmacht-Kennzeichnung nennt immer die Art ("Vollmacht zur Abnahme: ja/nein"). Als Warnung nur beim Zweck "abnahme".
   - Vorlage veröffentlichen abgelehnt, wenn ein Pflichtfeld, das der Unterzeichner nicht ausfüllen darf, über seiner
     Unterschrift steht. Vorhandene Start- und veröffentlichte Vorlagen prüfen und melden.
1. Feldtyp "Mängel": Mängel entstehen im Entwurf mit Herkunft Protokoll; in die feste Kopie je Mangel Kennung und Prüfsumme.
   Nach der Unterschrift des Auftraggebers keine neuen Mängel an diesem Protokoll. Vorher verworfene fehlen in der Kopie,
   danach verworfene bleiben drin und werden als verworfen angezeigt.
2. Zweck "abnahme" (nur Auftrag, nur Büro, nicht in /mobil), Systemfelder ohne Vorgabe, Startvorlage per Migration:
   - Befund: Teilnehmer, Umfang (gesamt/Teil mit Beschreibung), Dachflächen aus dem Objekt, Mängel, Einwendungen des
     Auftragnehmers
   - Erklärungen des Auftraggebers: Ergebnis, Vorbehalt Mängel, Vorbehalt Vertragsstrafe; Unterschrift Auftraggeber (laut
     Auftrag oder Beteiligter)
   - Schluss: Unterschrift Auftragnehmer (Konto)
   Bei der Unterschrift des Auftraggebers lehnt der Server ab: Mängel ohne Vorbehalt, Vorbehalt ohne Mangel, "verweigert" ohne
   Mangel.
3. Folge nach der Unterschrift des Auftraggebers: legt die Abnahme an (förmlich, Nachweis "Protokoll" mit Verweis aufs Siegel,
   Datum der Unterschrift in Berliner Zeit, Erklärender mit Vollmacht-Kopie) und hängt die Mängel daran; erst dann Aufgaben und
   Freigabe. Höchstens eine Abnahme je Protokoll, auch beim Nachholen. Ausstehende Folge sichtbar am Auftrag. Die Unterschrift
   des Auftraggebers lässt sich nicht verwerfen, solange die daraus entstandene Abnahme gilt.
4. Mängel und Erklärungen auf der Protokollseite und im PDF. Feste Fassung, Ablage und Versand kommen in 2c-2e.

Angriffstests mit Gegenprobe: Mangel nach der Unterschrift, die drei Widersprüche, doppelte Folge, Monteur öffnet das
Protokoll, falsche Unterzeichner-Art am Auftraggeber-Feld, Verwerfen der Unterschrift bei gültiger Abnahme. Wichtige Tests auch
gegen PostgreSQL. Eigene Festlegungen mit "Bitte bestätigen", Nebenbefunde nur melden. Wird der Umfang zu groß: nach Punkt 2
committen und den Rest auflisten.

Versionen: 1.8.59 Punkt 0, 1.8.60 Punkt 1, 1.8.61 Punkt 2, 1.8.62 Punkt 3, 1.8.63 Punkt 4 -- je ein Commit (Regel 13).


---

## Umsetzung 1.8.59 (05.10.2026) -- Runde 2c-2d, Punkt 0 (Vorweg)

### 0a: Person und Funktion beim Unterzeichner "Auftraggeber laut Auftrag"

- Neue Spalten `checklist_attachments.signer_person` (String 160) und `signer_function` (String 120), Migration
  `cd0d94c87f0c` (Downgrade verweigert, sobald eine Unterschrift eine Person trägt).
- `_signer()`: beim Auftraggeber laut Auftrag ist `signer_person` Pflicht (400 "Bitte den Namen der Person angeben, die für den
  Auftraggeber unterschreibt."), `signer_function` optional; Leerraum zusammengezogen, Längen 160/120. Bei jedem anderen
  Unterzeichner sind beide ein Fehler (400). `signer_name` bleibt der Auftraggeber laut Auftrag.
- Siegel: `signer_content()` nimmt `"person"`/`"function"` nur auf, wenn gesetzt -- Siegel von 1.8.57/1.8.58 rechnen unverändert
  nach, eine am ORM vorbei gesetzte, geänderte oder entfernte Person erscheint als "weicht ab: Unterzeichner".
- Seite: statt "Unterschreibt: …" jetzt "Für: <Auftraggeber> (Auftraggeber laut Auftrag)", darunter "Name der unterschreibenden
  Person" (Pflicht, ohne Vorbelegung) und "Funktion (optional)"; an der Unterschrift "– unterschrieben von <Person>
  (<Funktion>)", ebenso im PDF (`signer_text()`).

### 0b: Vollmacht immer mit Art, Warnung nur beim Zweck "abnahme"

- Unterschrift eines Beteiligten: "Vollmacht zur Abnahme: ja" (Büro mit Link "ansehen") bzw. "Vollmacht zur Abnahme: nein";
  nur beim Zweck "abnahme" als Warnung ("⚠ …", `signer_poa_warning`; im PDF "Achtung: Vollmacht zur Abnahme: nein").
- Auswahl der Beteiligten: "<Name> (<Rolle>) · Vollmacht zur Abnahme: ja/nein"; der Warnhinweis beim Wählen erscheint nur beim
  Zweck "abnahme".

### 0c: Veröffentlichen prüft Pflichtfelder, die der Unterzeichner nicht ausfüllen darf

- `signer_fill_findings()` (`app/checklist_templates.py`): je Unterschriftsfeld ohne "nur Büro" (also eines, das auch der
  Monteur leisten kann) die Pflichtfelder darüber (required oder Mindestanzahl, ohne Hinweise und Unterschriften), die nur das
  Büro ausfüllt. Ein solches Feld verlangt seine Unterschrift seit 1.8.56 -- der Monteur käme nie zur Unterschrift.
  `validate_version_for_publish()` lehnt ab (`signer_fill_problems()`), der Editor zeigt die Befunde am Entwurf und an der
  gültigen Fassung (Kasten "Unterschrift und Pflichtfelder").
- **Befund an den vorhandenen Vorlagen** (Startvorlagen über ihre Migrationen geprüft, `test_v361`): die 13 allgemeinen
  Startvorlagen und die Bedenkenanzeige -- nichts; die **Behinderungsanzeige** -- "Unterschrift" im Abschnitt Wegfall (Monteur
  oder Büro, 1.8.38) steht unter den Pflichtfeldern der Anzeige (Ursache, Beschreibung der Ursache, Betroffene Leistungen,
  Beginn), die nur das Büro ausfüllt. Gewöhnliche Felder sind nie "nur Büro" -- auf dem Server kann deshalb nur eine
  veröffentlichte Behinderungsanzeige betroffen sein; der Editor zeigt es dort an.
- Die Behinderungsanzeige steht als **bekannte Ausnahme** in `SIGNER_FILL_EXCEPTIONS` (darf nur kürzer werden, ein Test prüft,
  dass jede Ausnahme einem echten Befund entspricht) -- sonst ließe sich weder die Startvorlage noch eine neue Fassung einer
  Behinderungsanzeige veröffentlichen. Der Editor kennzeichnet sie "bekannte Ausnahme des Zwecks, Entscheidung offen".

### Festlegungen 1.8.59 (bestätigt am 06.10.2026, Vorgabe 2c-2d Teil 2; Nr. 5 entschieden: (b), siehe "Umsetzung 1.8.62")

1. **`signer_name` bleibt der Auftraggeber**, die Person kommt dazu (eigene Spalten) -- "Hallenbau GmbH, unterschrieben von
   Herbert Halle (Geschäftsführer)".
2. **Person und Funktion im Siegel nur, wenn gesetzt** -- keine neue Fassung des Siegelformats.
3. **Person und Funktion bei jedem anderen Unterzeichner abgelehnt** (400), keine stille Umdeutung.
4. **"Der Unterzeichner darf nicht ausfüllen"** heißt: eine Unterschrift ohne "nur Büro" unter einem Pflichtfeld "nur Büro".
   Pflicht wie beim Abschließen (required oder Mindestanzahl).
5. **Behinderungsanzeige als bekannte Ausnahme statt Ablehnung.** **Bitte entscheiden**, wie sie aufgelöst wird: (a) die
   Wegfall-Unterschrift nur fürs Büro (der Monteur trägt Beendigung und Wiederaufnahme ein, das Büro unterschreibt), oder (b)
   die Ausnahme behalten (der Monteur wartet mit der Wegfall-Unterschrift, bis das Büro die Anzeige ausgefüllt hat -- so ist der
   Ablauf seit 1.8.56).

### Verifikation 1.8.59

- `tests/test_v361_abnahmeprotokoll_vorweg.py` (16, einer nur unter SQLite): Person Pflicht und im Siegel, Funktion optional,
  Person/Funktion bei frei, Konto, Beteiligter abgelehnt, ältere Siegel gültig und Person gebunden (gesetzt, entfernt, Funktion
  geändert -> "Unterzeichner"), Seite ohne Vorbelegung; Vollmacht "ja/nein" mit Art, Warnung nur beim Zweck "abnahme" (Daten,
  PDF-Zeile, Seite); Veröffentlichen abgelehnt mit Test-Zweck, freiwilliges Büro-Feld und Büro-Unterschrift in Ordnung, alle
  Startvorlagen geprüft (nur die bekannte Ausnahme, sie hindert nicht), Editor; Migration mit verweigertem Downgrade.
- Angepasst: `test_v359` (Auftraggeber mit Person, Seitentext), `test_v358` (zwei neue Spalten eingeordnet -- vom Strukturtest
  gemeldet).
- Gegenproben (Marker GEGENPROBE, Dateien byte-genau zurück): 13 von 13 rot.
- Migration `cd0d94c87f0c`: SQLite hin/zurück/hin, `check`; PostgreSQL 17 im Wegwerf-Schema: Kette bis `5e562a4a172b`, head,
  Bestand über den App-Code (Auftraggeber mit Person, Beteiligter mit Vollmacht, Konto -- alle "unverändert"), Downgrade
  verweigert, `current`, `check`; leeres Schema hin/zurück/hin.
- PostgreSQL (pytest-Plugin): `test_v361` und `test_v359` -- 44 grün, einer übersprungen (Bestand mit rohem SQL nur unter SQLite).
- Klicktests: `klicktest_unterzeichner.py` 19/19 (neu: Person Pflicht ohne Vorbelegung, ohne Person abgelehnt, mit Person und
  Funktion; Vollmacht "ja/nein", kein Warnhinweis beim Zweck allgemein); unverändert grün: `behinderungsanzeige` 35, `_abschluss`
  43, `bedenkenanzeige` 22, `checkliste_zweck` 28, `checkliste_unterschrift` 26, `vertrag_unterschrift` 43.
- Volle Suite 2923 grün (mit den opt-in-Tests gegen PostgreSQL).

---

## Umsetzung 1.8.60 (05.10.2026) -- Runde 2c-2d, Punkt 1: Feldtyp "Mängel"

### Feld und Datensatz

- Neuer Feldtyp `maengel` (`FIELD_TYPES`), nur als Systemfeld eines Zwecks (`SYSTEM_ONLY_FIELD_TYPES`): im Editor nicht
  wählbar, Anlegen und Umstellen von Hand abgelehnt ("Den Feldtyp „Mängel“ gibt ein Zweck als Systemfeld vor …"); nie
  Pflicht, keine Antwort (`_NO_ANSWER_TYPES`). Bis 1.8.61 trägt ihn kein Zweck -- im Betrieb also noch nicht sichtbar.
- Ein Mangel aus dem Protokoll ist ein gewöhnlicher `Defect` mit `source = "protokoll"` und neuer Spalte
  `defects.checklist_id` (FK `fk_defects_checklist_id`, Index; Migration `82e4382b0c9f`, Downgrade verweigert, solange ein
  Mangel aus einem Protokoll existiert). `acceptance_id` bleibt leer, bis die Abnahme aus dem Protokoll entsteht (1.8.62).
- Gebundener Inhalt (`defect_content()`): bei Herkunft Protokoll `checklist_id` statt `acceptance_id`, sonst wie bisher --
  die Prüfsumme (`content_sha256`) steht ab dem Erfassen fest.
- `create_protocol_defect()` (`app/defects.py`), `POST /api/checklists/{id}/defects` (Büro, Modul `checklisten`; dazu `GET
  …/defects` und `GET …/protocol-options`): Beschreibung Pflicht, Dachfläche nur aus dem Objekt des Projekts und nicht
  archiviert, Ortsangabe, Frist nicht in der Vergangenheit, Fotos und Belege wie an der Abnahme. Unter der Zeilensperre der
  Checkliste (wie das Unterschreiben): nur im Entwurf, nur solange keine gültige Unterschrift das Feld versiegelt -- sonst 409
  "Das Protokoll ist unterschrieben – an diesem Protokoll entstehen keine neuen Mängel mehr." Keine Aufgabe.
- Bis zur Abnahme (`protocol_pending()`): Haltung, Freigabe, Status, Fotos und Belege ergänzen abgelehnt (409 "… aus dem noch
  keine Abnahme angelegt ist – Haltung, Freigabe, Status und Nachträge erst danach."); Verwerfen mit Begründung geht. Die Auftragsseite zeigt solche Mängel mit "Aus dem
  Abnahmeprotokoll – noch ohne Abnahme …", Link aufs Protokoll, nur "Verwerfen …", Aufgabe "entsteht mit der Abnahme aus dem
  Abnahmeprotokoll".

### Siegel

- Kopie jeder Unterschrift unterhalb des Felds und des Abschlusses: `{"field_key": …, "defects": [{"id", "sha256"}]}` -- je
  Mangel Kennung und Prüfsumme seines gebundenen Inhalts, nachgerechnet (nicht aus der Spalte gelesen): ein am ORM vorbei
  geänderter Mangel erscheint an der Unterschrift als "weicht ab: Mängel".
- Im Stand des Zeitpunkts (`defect_in_seal(defect, as_of)`): ein vor der Unterschrift verworfener Mangel fehlt, ein danach
  verworfener bleibt drin -- die Unterschrift bleibt "Inhalt unverändert", die Seite zeigt ihn "Verworfen (…) – bleibt im
  Protokoll (erst nach der Unterschrift verworfen)", einen vorher verworfenen "… – nicht im Protokoll". Der Abschluss nimmt
  den Stand seines Zeitpunkts (`completed_at` steht jetzt vor dem Versiegeln fest).
- Ältere Siegel sind unberührt: der Eintrag entsteht nur an einem Feld vom Typ `maengel`.
- **Eigener Fehler, im Test gefunden**: Unterschrift (`created_at`) und Verwerfen (`discarded_at`) wurden auf volle Sekunden
  gekürzt -- ein in derselben Sekunde vor der Unterschrift verworfener Mangel landete in ihrer Kopie. Beide Zeitpunkte jetzt
  mit voller Genauigkeit (das Siegel des Verwerfens kürzt intern wie bisher), Vergleich "verworfen nach der Unterschrift"
  strikt, und das Verwerfen eines Protokoll-Mangels sperrt zuerst die Checkliste -- Unterschrift und Verwerfen laufen
  nacheinander, nie verschränkt.

### Seite

- Ausfüllseite (Büro): Liste der Mängel (Nr., Dachfläche, Ort, Beschreibung, Frist, Dateien, Prüfstatus, verworfen mit
  Kennzeichnung) und darunter "Mangel erfassen" (Beschreibung, Dachfläche, Ortsangabe, Frist, Fotos, Belege), solange das
  Feld offen ist; "Verwerfen …" mit Begründung je Mangel. Monteur: "Mängel erfasst das Büro.", Liste und Erfassen 403.

### Festlegungen 1.8.60 (bestätigt am 06.10.2026, Vorgabe 2c-2d Teil 2; zu Nr. 7: ob ein Mangel im Protokoll bleibt, entscheidet seit 1.8.62 die Kopie, kein Zeitvergleich)

1. **Das Feld "Mängel" gibt nur ein Zweck vor** -- von Hand nicht anzulegen (ein Mangel braucht Auftrag, Objekt und später die
   Abnahme aus dem Protokoll).
2. **"Nach der Unterschrift des Auftraggebers keine neuen Mängel"** ist umgesetzt als: sobald eine gültige Unterschrift das
   Feld versiegelt (jede Unterschrift darunter, wie bei Antworten und Fotos). Wird sie verworfen, ist das Feld wieder offen;
   ab 1.8.62 lässt sich die Unterschrift des Auftraggebers nicht verwerfen, solange die Abnahme aus ihr gilt.
3. **Bis zur Abnahme nur Verwerfen** -- Haltung, Freigabe, Status und Nachträge erst danach; Fotos und Belege beim Erfassen.
4. **Der gebundene Inhalt bleibt beim Protokoll** (`checklist_id`): wenn die Abnahme in 1.8.62 entsteht, wird `acceptance_id`
   gesetzt, ohne den gebundenen Inhalt zu ändern -- sonst wichen die Siegel des Protokolls ab.
5. **Frist nicht in der Vergangenheit, Dachfläche nur aus dem Objekt und nicht archiviert** -- wie beim Erfassen an der
   Abnahme bzw. "zurück auf offen" (1.8.55).
6. **Mängel im Protokoll sieht nur das Büro** (der Zweck "abnahme" ist ab 1.8.61 ohnehin nur fürs Büro).
7. **Zeitpunkte von Unterschrift und Verwerfen mit voller Genauigkeit**, Verwerfen eines Protokoll-Mangels unter der Sperre
   der Checkliste (siehe "Eigener Fehler").

### Verifikation 1.8.60

- `tests/test_v362_maengel_im_protokoll.py` (18, davon 2 nur gegen PostgreSQL): Herkunft und gebundener Inhalt, Prüfung beim
  Erfassen (Beschreibung, fremde und archivierte Dachfläche, Frist), keine Einträge vor der Abnahme (Verwerfen geht),
  Systemfeld-Typ, Monteur 403, je Mangel Kennung und Prüfsumme in der Kopie, Angriff "Mangel nach der Unterschrift" (409, auch
  nach dem Verwerfen der Unterschrift wieder offen), vorher/danach verworfen in Kopie und Liste, Abschluss, am ORM vorbei
  geänderter Mangel -> "weicht ab: Mängel", Seiten, Migration mit verweigertem Downgrade; gegen PostgreSQL: Mangel während der
  Unterschrift wartet und wird abgelehnt, Unterschrift wartet auf den Mangel und versiegelt ihn mit.
- Gegenproben (Marker GEGENPROBE, Dateien byte-genau zurück): 13 von 13 rot, dazu 1 von 1 für die Liste (siehe unten).
- Migration `82e4382b0c9f`: SQLite hin/zurück/hin, `check`; PostgreSQL 17 im Wegwerf-Schema: Bestand über den App-Code
  (Protokoll-Mangel unter einer Unterschrift, "unverändert"), Downgrade verweigert, `current`, `check`, leeres Schema
  hin/zurück/hin.
- PostgreSQL (pytest-Plugin): `test_v362`, `test_v361`, `test_v359`, `test_v358`, `test_v351` -- 126 grün, 1 übersprungen, 1 rot:
  `test_v351::test_migration_down_refuses_while_defects_exist` sät mit rohem SQL und erfundenen Fremdschlüsseln (bekanntes
  Muster, unter PostgreSQL immer rot, kein Befund).
- Volle Suite (mit den opt-in-Tests gegen PostgreSQL): 2940 grün, 1 rot -- `test_v326`: die neue Route
  `/api/checklists/{id}/defects` fiel in den Filter "acceptance/warranty/defect", der für den Admin 200 mit Inhalt erwartet; die
  Checkliste des Durchlaufs hat kein Feld "Mängel". Die beiden Protokoll-Routen haben dort jetzt einen eigenen Test (Monteur
  403), Inhalt fürs Büro prüft `test_v362`. Danach `test_v326` 60 grün; nach der Korrektur unten die Dateien rund um Abnahme,
  Mängel und Checklisten (`test_v349`, `test_v35*`, `test_v36*`, `test_v326`) 379 grün.
- Klicktest neu: `klicktest_protokoll_maengel.py` 16/16 (Büro dunkel: leer, Dachflächen ohne archivierte, ohne Beschreibung
  abgelehnt, Mangel mit Foto und Beleg, vorher verworfen "nicht im Protokoll"; 412 px hell; Auftragsseite "noch ohne Abnahme",
  nur Verwerfen; Unterschrift -> kein Formular, API 409, danach verworfen "bleibt im Protokoll", Unterschrift unverändert;
  Monteurin "Mängel erfasst das Büro.", API 403). Das Feld "Mängel" setzt der Klicktest bis 1.8.61 direkt in der
  Wegwerf-Datenbank. Unverändert grün: `klicktest_maengel.py` 39, `klicktest_unterzeichner.py` 19,
  `klicktest_checkliste_unterschrift.py` 26.
- **Zweiter eigener Fehler, im Klicktest gefunden**: die Liste der Protokoll-Mängel meldete vor jeder Unterschrift jeden Mangel
  als "im Protokoll", auch einen schon verworfenen (`sealed_at is None or …`) -- die Seite zeigte "bleibt im Protokoll" statt
  "nicht im Protokoll". Ein vor der ersten Unterschrift verworfener Mangel kommt in keine Kopie mehr; jetzt
  `defect_in_seal(d, sealed_at)` auch ohne Unterschrift. `test_v362` prüfte die Liste nur nach der Unterschrift -- jetzt auch
  davor (Gegenprobe rot).

---

## Umsetzung 1.8.61 (05.10.2026) -- Runde 2c-2d, Punkt 2: Zweck "abnahme"

### Zweck und Systemfelder (`app/checklist_purposes.py`)

- `ChecklistPurpose("abnahme", …, ("auftrag",), ACCEPTANCE_SYSTEM_FIELDS, office_only=True, signature_checks=…)`, keine Folgen
  (die Folge "Abnahme anlegen" kommt mit 1.8.62). Systemfelder (Schlüssel `abnahme.<name>`, stehen in der Datenbank, werden nie
  umbenannt), ohne Vorgabe der Antworten:

  | Abschnitt | Feld | Typ | Pflicht |
  |---|---|---|---|
  | Befund | `teilnehmer` Teilnehmer | Text, mehrzeilig | ja |
  | | `umfang` Umfang | Auswahl `gesamt` Gesamtabnahme / `teil` Teilabnahme | ja |
  | | `umfang_beschreibung` Abgenommener Teil | Text, mehrzeilig | bei Teilabnahme (Prüfung bei der Unterschrift) |
  | | `dachflaechen` Dachflächen | neu: `dachflaechen` | nein |
  | | `maengel` Mängel | `maengel` (1.8.60) | nein |
  | | `einwendungen` Einwendungen des Auftragnehmers | Text, mehrzeilig | nein |
  | Erklärungen des Auftraggebers | `ergebnis` Ergebnis | Auswahl `abgenommen` Abnahme erklärt / `verweigert` Abnahme verweigert | ja |
  | | `vorbehalt_maengel` Vorbehalt wegen bekannter Mängel | Ja/Nein | bei "abgenommen" (Prüfung bei der Unterschrift) |
  | | `vorbehalt_vertragsstrafe` Vorbehalt der Vertragsstrafe | Ja/Nein | bei "abgenommen" (Prüfung bei der Unterschrift) |
  | | `unterschrift_auftraggeber` Unterschrift Auftraggeber | Unterschrift, Unterzeichner `ag_oder_beteiligter` | ja |
  | Schluss | `unterschrift_auftragnehmer` Unterschrift Auftragnehmer | Unterschrift, Unterzeichner `konto` | ja |

- Neu an `SystemField`: `signer_mode` -- der Unterzeichner eines Unterschrifts-Systemfelds ist fest wie der Typ:
  `_sync_system_fields()` setzt ihn, `system_field_problems()` meldet eine Abweichung ("weicht von der Vorgabe ab:
  Unterzeichner"), `update_field()` lehnt eine Änderung ab ("Den Unterzeichner dieses Systemfelds gibt der Zweck vor."), der
  Editor zeigt "(vom Zweck vorgegeben)" und sperrt die Auswahl (`signer_mode_locked`). Ohne Vorgabe (`None`, Behinderungs- und
  Bedenkenanzeige) bleibt er frei wählbar wie bisher.

### Nur Büro

- `ChecklistPurpose.office_only` (`purpose_office_only()`), im Router (`app/routers/checklists.py`): der Monteur sieht
  Vorlagen dieses Zwecks nicht in der Start-Auswahl, Checklisten nicht in der Liste am Auftrag und nicht unter "meine", Anlegen
  403 ("Diese Checkliste führt das Büro."), jeder Einzelzugriff 403 (Abruf, Antworten, Anhänge, PDF, Mängel) -- auch eine
  "eigene", die am Router vorbei angelegt wurde. `/mobil` nutzt dieselben Endpunkte. Der Editor nennt am Zweck "nur Büro".

### Unterzeichner "Auftraggeber laut Auftrag oder Beteiligter"

- Neuer Unterzeichner `ag_oder_beteiligter` (der Schlüssel ist kurz, weil `signer_mode` String(20) ist -- der zuerst geplante
  `auftraggeber_oder_beteiligter` hätte unter PostgreSQL die Spaltenlänge überschritten, SQLite hätte ihn still angenommen).
  Gewählt wird beim Unterschreiben: ohne Beteiligten der Auftraggeber laut Auftrag (Person Pflicht, Funktion optional, 1.8.59),
  mit Beteiligtem dessen Pfad (Rolle, Vollmacht zur Abnahme eingefroren, ohne mit Warnung). Gespeichert wird die gewählte Art
  (`signer_kind` "auftraggeber" bzw. "beteiligter") -- Siegel, Text und PDF wie bisher. Seite: "Wer unterschreibt?" mit dem
  Auftraggeber und den Beteiligten ("· Vollmacht zur Abnahme: ja/nein"), beim Auftraggeber die Personenfelder, beim
  Beteiligten ohne Vollmacht die Warnung (Zweck "abnahme").

### Prüfung bei der Unterschrift des Auftraggebers (`app/acceptance_protocol.py`)

- `ChecklistPurpose.signature_checks` (Feldschlüssel -> Prüfung), aufgerufen in `add_attachment()` nach der Prüfung der
  Pflichtangaben oberhalb und des Unterzeichners, unter der Zeilensperre der Checkliste -- dieselbe Sperre nehmen Erfassen und
  Verwerfen eines Mangels im Protokoll (1.8.60). Abgelehnt (400):
  - die drei Widersprüche: **Mängel ohne Vorbehalt** (abgenommen, mindestens ein nicht verworfener Mangel, Vorbehalt "nein"),
    **Vorbehalt ohne Mangel** (Vorbehalt "ja", kein nicht verworfener Mangel), **"verweigert" ohne Mangel**;
  - was die Abnahme aus dem Protokoll (1.8.62, `create_acceptance()`) ablehnen würde: Teilabnahme ohne Beschreibung,
    Beschreibung bei der Gesamtabnahme, fehlende Vorbehalte bei "abgenommen", Vorbehalte bei "verweigert", eine gewählte
    Dachfläche, die nicht mehr zum Objekt gehört oder inzwischen archiviert ist;
  - jeder andere Unterzeichner als Auftraggeber oder Beteiligter -- auch wenn die Fassung am ORM vorbei "frei" oder "Konto"
    trägt (Angriff "falsche Unterzeichner-Art").

### Feldtyp "Dachflächen"

- Neuer Feldtyp `dachflaechen`, nur als Systemfeld (`SYSTEM_ONLY_FIELD_TYPES`), nie Pflicht. Antwort: Liste von
  Dachflächen-Kennungen; gespeichert in `value_text` als `[{"id", "name"}]` nach Kennung, der Name als Schnappschuss
  (Umbenennen ändert Antwort und Siegel nicht). Nur aus dem Objekt des Projekts, nicht archiviert (400). Seite: Kacheln aus
  `GET /api/checklists/{id}/protocol-options`; eine gewählte, später archivierte bleibt sichtbar ("nicht mehr wählbar") und
  lässt sich abwählen. PDF: die Namen. Schemas: `ChecklistAnswerWrite.value` nimmt `list[int]`, `ChecklistAnswerOut.value`
  `list[ChecklistRoofAreaValueOut]`.

### Startvorlage (Migration `65c57e30d0f3`)

- "Abnahmeprotokoll" als Entwurf (Zweck abnahme, nur Auftrag, `field_readable` aus), mit Hinweis "Vor Veröffentlichung
  prüfen", Hilfetexten je Feld und den beiden festen Unterzeichnern; eine gleichnamige Vorlage bleibt unangetastet.
  `downgrade()` entfernt sie nur unveröffentlicht und unbenutzt. Kein Schema.
- **Auf dem Server**: eine schon vorhandene Vorlage mit Zweck "abnahme" (seit 1.8.16 wählbar, bisher ohne Systemfelder) wird
  mit 1.8.61 "nur Büro". Ihre veröffentlichten Fassungen bleiben nutzbar, ohne Prüfung des Zwecks (ihnen fehlt das Feld
  `abnahme.unterschrift_auftraggeber`); ein neuer Entwurf bekommt die Systemfelder, Veröffentlichen verlangt sie. Ob es eine
  solche Vorlage gibt, lässt sich von hier nicht prüfen.

### Festlegungen 1.8.61 (bestätigt am 06.10.2026, Vorgabe 2c-2d Teil 2)

1. **"Systemfelder ohne Vorgabe"** verstanden als: keine Vorbelegung und keine Vorauswahl der Antworten (wie der
   Abnahme-Dialog seit 1.8.46). Die Unterzeichner der beiden Unterschriften gibt der Zweck dagegen fest vor, wie die Vorgabe sie
   nennt.
2. **Ein Unterzeichner "Auftraggeber laut Auftrag oder Beteiligter"**, gewählt beim Unterschreiben, statt zweier Felder --
   gespeichert wird die gewählte Art.
3. **Pflicht**: Teilnehmer, Umfang, Ergebnis, beide Unterschriften. **Bedingt** (bei der Unterschrift des Auftraggebers
   geprüft): Beschreibung bei der Teilabnahme (bei der Gesamtabnahme leer), beide Vorbehalte bei "abgenommen" (bei
   "verweigert" leer). Dachflächen, Mängel, Einwendungen frei.
4. **Neben den drei Widersprüchen lehnt die Unterschrift ab, was die Abnahme aus dem Protokoll nicht annähme** -- sonst
   entstünde mit 1.8.62 eine Folge, die nicht ausführbar ist, nachdem die Unterschrift den Befund schon versiegelt hat.
5. **"Mangel" heißt ein nicht verworfener Mangel im Feld "Mängel"** -- ein verworfener zählt weder für den Vorbehalt noch
   für die Verweigerung.
6. **Dachflächen als eigener Feldtyp mit Namens-Schnappschuss**; eine später archivierte gewählte Fläche hält die
   Unterschrift auf, bis sie abgewählt ist.
7. **Nur Büro gilt für den ganzen Zweck**, auch für eine am Router vorbei angelegte "eigene" Checkliste des Monteurs und für
   schon vorhandene Vorlagen mit Zweck "abnahme".
8. **Startvorlage als Entwurf** mit Hinweis "Vor Veröffentlichung prüfen", wie Behinderungs- und Bedenkenanzeige.
9. **Ergebnis-Optionen "Abnahme erklärt"/"Abnahme verweigert"** (Schlüssel `abgenommen`/`verweigert` wie an der Abnahme).

### Verifikation 1.8.61

- `tests/test_v363_zweck_abnahme.py` (36, davon 2 nur gegen PostgreSQL): Registry (Abschnitte, Pflicht, feste Unterzeichner,
  Prüfung nur am Feld des Auftraggebers), Spaltenlängen, Startvorlage gegen die Registry über die echte
  Veröffentlichungsprüfung, Downgrade nur unbenutzt, Unterzeichner im Editor fest (ändern 400, am ORM vorbei -> "weicht ab",
  Angleichen setzt zurück), Zweckliste und Editor über HTTP, Monteur (Start-Auswahl, Anlegen, Liste, "meine", Abruf, Antwort,
  Anhang, PDF, Mängel, auch eine eigene), Auftraggeber mit Person, Beteiligter mit/ohne Vollmacht, unvollständig oder gemischt
  abgelehnt, Angriff falsche Unterzeichner-Art ("frei", "Konto"), die drei Widersprüche und ein nur verworfener Mangel, drei
  stimmige Protokolle, was die Abnahme nicht annähme (fünf Fälle), Teilabnahme mit Beschreibung, Dachflächen (Schnappschuss,
  fremd, archiviert, keine Liste, nach dem Archivieren), Seiten; gegen PostgreSQL: Unterschrift wartet auf das Verwerfen des
  einzigen Mangels und wird abgelehnt, Verwerfen wartet auf die Unterschrift und bleibt in der Kopie.
- Angepasst: `test_v320` (abnahme hat Systemfelder, "nur Büro" in der Zweckliste), `test_v361` (Testunterschrift über den neuen
  Pflicht-Systemfeldern). Beim Anpassen gefunden: die Antwortschemata (`ChecklistPurposeOut`, `ChecklistTemplateFieldOut`)
  filterten `office_only` und `signer_mode_locked` heraus -- ergänzt, `test_v363` prüft es jetzt über HTTP.
- Gegenproben (Marker GEGENPROBE, Dateien byte-genau zurück): 21 von 21 rot (Monteur fünfmal, Prüfung des Zwecks, jede der
  drei Widersprüche, verworfene zählen mit, Unterzeichner-Art, Teilabnahme, Vorbehalte bei "verweigert", archivierte und fremde
  Dachfläche, Namens-Schnappschuss, Unterzeichner im Editor und in der Veröffentlichungsprüfung, Startvorlage, Sperre beim
  Verwerfen gegen PostgreSQL, Spaltenlänge).
- Migration `65c57e30d0f3`: SQLite hin/zurück/hin (Startvorlage weg und wieder da), `current`, `check`; PostgreSQL 17 im
  Wegwerf-Schema: Kette bis `82e4382b0c9f`, eine alte, veröffentlichte Vorlage mit Zweck "abnahme" ohne Systemfelder, head,
  Startvorlage veröffentlicht und über den App-Code ausgefüllt (Teilabnahme, Dachfläche, Mangel mit Vorbehalt), freier Name am
  Auftraggeber-Feld abgelehnt, Beteiligter und Konto unterschrieben -- beide "unverändert"; die alte Vorlage weiter nutzbar;
  zurück/hin lässt die benutzte Startvorlage stehen und legt keine zweite an; `current`, `check`; leeres Schema hin/zurück/hin.
- PostgreSQL (pytest-Plugin): `test_v363`, `test_v320`, `test_v361` -- 67 grün, 1 übersprungen (Bestand mit rohem SQL nur
  unter SQLite).
- Volle Suite (mit den opt-in-Tests gegen PostgreSQL): 2977 grün; der danach ergänzte Spaltenlängen-Test grün.
- Klicktests: neu `klicktest_abnahmeprotokoll.py` 18/18; angepasst und grün `klicktest_checkliste_zweck.py` 28/28 (die
  Monteurin startet keine Abnahme mehr, Anlegen 403) und `klicktest_unterzeichner.py` 19/19 (fünf Unterzeichner); unverändert
  grün `klicktest_behinderungsanzeige.py` 35/35.

### Nebenbefunde 1.8.61 (nur gemeldet)

1. **Behinderungsanzeige, Wegfall-Unterschrift** (1.8.59, Festlegung 5): weiter als bekannte Ausnahme in
   `SIGNER_FILL_EXCEPTIONS`, Entscheidung offen.
2. **`create_checklist()` und jede Integritätsverletzung** (1.8.57, Nebenbefund 1): unverändert offen.
3. **`test_v326` kann die Protokoll-Routen nicht mit Inhalt füllen** (die Checkliste des Durchlaufs ist keine mit Feld
   "Mängel"); geprüft wird dort nur Monteur 403, der Inhalt fürs Büro in `test_v362`/`test_v363`.

### Offen aus 2c-2d: Punkt 3 und 4 (nach Punkt 2 committet, wie für einen zu großen Umfang vorgegeben)

Punkt 3 greift in die unveränderliche Abnahme ein (neue Nachweisart, neues Prüfsummenformat) und hängt an zwei offenen
Festlegungen (1.8.60 Nr. 4, 1.8.61 Nr. 4) -- deshalb erst nach deren Bestätigung. Geplant:

- **1.8.62 Punkt 3, Folge "Abnahme anlegen"** nach der Unterschrift des Auftraggebers (`FollowUp(after_signature=
  abnahme.unterschrift_auftraggeber)`): `order_acceptances.checklist_id` (FK, UNIQUE -- höchstens eine Abnahme je Protokoll,
  auch wenn ein Abbruch zwischen Handler und Vermerk das Nachholen wiederholt); Art förmlich, Nachweis "Protokoll" statt Beleg:
  Verweis auf die Unterschrift (Kennung, `content_sha256` ihrer Kopie) im gebundenen Inhalt der Abnahme (neues
  Prüfsummenformat, ältere Abnahmen rechnen in ihrem Format); Datum = Tag der Unterschrift in Europe/Berlin; Erklärender aus der
  Unterschrift (Auftraggeber mit Person bzw. Beteiligter mit der beim Unterschreiben eingefrorenen Vollmacht-Kopie, nicht der
  heutige Stand am Beteiligten); Umfang, Ergebnis, Vorbehalte, Einwendungen, Dachflächen aus der versiegelten Kopie. Danach
  `acceptance_id` an jedem nicht verworfenen Mangel des Protokolls (gebundener Inhalt unverändert, Festlegung 1.8.60 Nr. 4), erst
  dann Aufgaben je Mangel und Freigabe möglich (`protocol_pending()` wird falsch). Ausstehende oder fehlgeschlagene Folge als
  Hinweis am Auftrag mit "Nachholen". `discard_signatures()`: die Unterschrift des Auftraggebers lässt sich nicht verwerfen,
  solange die Abnahme daraus nicht verworfen ist (409). Angriffstests: doppelte Folge (gleichzeitig, auch gegen PostgreSQL),
  Verwerfen der Unterschrift bei gültiger Abnahme, Nachholen nach verworfener Abnahme (keine zweite).
- **1.8.63 Punkt 4**: Mängel (mit "verworfen"/"bleibt im Protokoll") und Erklärungen auf der Protokollseite gebündelt und im
  PDF -- heute zeigt das PDF am Feld "Mängel" nur "—", die Dachflächen schon mit Namen. Feste Fassung, Ablage und Versand: 2c-2e.

Offene Fragen dazu: (a) Soll eine verworfene Abnahme aus dem Protokoll eine neue aus demselben Protokoll erlauben (die Vorgabe
sagt "höchstens eine Abnahme je Protokoll, auch beim Nachholen" -- verstanden als nie, ein neues Protokoll ist der Weg)?
(b) Tag der Abnahme = Tag der Unterschrift des Auftraggebers, auch wenn die Folge erst Tage später nachgeholt wird?

Antworten (Vorgabe 2c-2d Teil 2, 06.10.2026): (a) Schlüssel der Folge ist die Unterschrift des Auftraggebers, nicht das
Protokoll -- höchstens eine Abnahme je Unterschrift; eine neue Abnahme aus demselben Protokoll nur über eine neue Unterschrift,
nachdem Abnahme und alte Unterschrift verworfen sind. (b) Ja: das Datum kommt aus der versiegelten Unterschrift (Berliner Zeit),
nie aus dem Zeitpunkt der Folge.

---

## Vorgabe 2c-2d Teil 2 (06.10.2026, übernommen wie gegeben)

Punkte 3 und 4 nach der Planung oben. Festlegungen 1.8.59–1.8.61 als bestätigt markieren. Antworten (a)/(b) siehe oben.
Behinderungsanzeige (Festlegung 1.8.59 Nr. 5): (b) behalten, wenn die Ausnahme genau die Büro-Felder der Anzeige über der
Wegfall-Unterschrift betrifft und das Datum des Wegfalls ein eigenes Feld ist, nicht die Unterschriftszeit -- sonst melden.

Vorweg:
- Ob ein Mangel vor oder nach der Unterschrift verworfen wurde, ergibt sich daraus, ob er in der versiegelten Kopie steht, nicht
  aus einem Zeitvergleich. Falls heute über Zeitstempel: umstellen.
- Längentest als Muster für alle Textspalten mit festen Werten, falls er das noch nicht ist.

Die Folge legt die Abnahme über dieselbe Prüf- und Anlegefunktion an wie das Erfassen von Hand, nichts nachgebaut.
Angriffstests mit Gegenprobe wie in der letzten Vorgabe (doppelte Folge, Verwerfen der Unterschrift bei gültiger Abnahme), dazu:
eine neue Unterschrift nach verworfener Abnahme ergibt genau eine neue Abnahme. Wichtige Tests auch gegen PostgreSQL. Eigene
Festlegungen mit "Bitte bestätigen", Nebenbefunde nur melden. Commit nach Regel 13.

Versionen: 1.8.62 Vorweg, 1.8.63 Punkt 3, 1.8.64 Punkt 4 (der Plan oben nannte 1.8.62/1.8.63 -- der Vorweg-Teil ist als eigene
Version davor gekommen).

---

## Umsetzung 1.8.62 (06.10.2026) -- Runde 2c-2d Teil 2, Vorweg

### Mängel im Protokoll: die Kopie entscheidet, nicht die Uhr

- Bis 1.8.61 rechnete die Prüfung einer Unterschrift (und des Abschlusses) die Mängel "im Stand ihres Zeitpunkts" nach:
  `defect_in_seal(defect, as_of)` verglich `discarded_at` mit `created_at` der Unterschrift; die Protokollseite ("bleibt im
  Protokoll" / "nicht im Protokoll") ebenso mit der ersten Unterschrift unter dem Feld. Das ist umgestellt:
  - `sealed_defect_ids(sealed_content)` (`app/checklists.py`): die Kennungen der Mängel in einer abgelegten Kopie.
  - `defect_in_seal(defect, sealed_ids)`: ein nicht verworfener Mangel immer; ein verworfener nur, wenn er in der Kopie steht.
    Beim Versiegeln selbst (keine Kopie) nur die nicht verworfenen -- unter der Zeilensperre der Checkliste, die auch das
    Verwerfen eines Protokoll-Mangels nimmt (1.8.60).
  - `check_signature()` und `check_completion()` rechnen mit den Kennungen ihrer eigenen Kopie nach, `list_protocol_defects()`
    mit der Kopie der ersten gültigen Unterschrift unter dem Feld (nach Zeitpunkt, dann Kennung).
- Was das nachgerechnete Siegel jetzt erkennt: ein am ORM vorbei geänderter, gelöschter oder neu eingefügter (nicht verworfener)
  Mangel weicht ab wie bisher. Was es nicht mehr meldet: ein nach der Unterschrift verworfener Mangel, dessen Zeitpunkt des
  Verwerfens am ORM vorbei vor die Unterschrift gelegt wurde -- er steht in der Kopie und bleibt im Protokoll; die Abweichung
  zeigt das Siegel des Verwerfens am Mangel selbst ("Verwerfen weicht von seiner Prüfsumme ab").
- Vorhandene Siegel (1.8.60/1.8.61): für unverändert gespeicherte Daten ergibt die Kopie dasselbe wie der Zeitvergleich -- sie
  rechnen unverändert nach. Kein neues Siegelformat, keine Migration. Die volle Genauigkeit von `created_at`/`discarded_at`
  (1.8.60, Festlegung 7) bleibt; sie trägt die Entscheidung nicht mehr.

### Längentest als Muster für alle Textspalten mit festen Werten

- Bis 1.8.61 prüfte `test_v363::test_signer_modes_and_field_types_fit_their_columns` nur Unterzeichner, Feldtypen und
  Systemfeld-Schlüssel. Neu `tests/test_v364_feste_werte_spaltenlaenge.py`:
  - `FESTE_WERTE` (108 Spalten): Spalte -> die Konstanten im Code (`(Modul, Ausdruck)` oder eine Funktion) -- ein neuer Wert in
    der Konstante wird automatisch mitgeprüft; `FESTE_LITERALE` (46): Werte, die nur als Literal an Schreibstellen stehen;
    `VORGABEN` (26): Spalten mit Nutzerwerten, deren Vorgaben beim Start aus dem Code kommen; `OHNE_FESTE_WERTE` (71) mit Grund.
  - Jede String(n)-Spalte, deren Name nach festen Werten klingt (`NAMENSMUSTER`, u. a. status, kind, type, mode, source, role,
    key), muss eingeordnet sein; veraltete Einträge fallen auf.
  - Per AST jedes Literal unter `app/`, das in einen Modellkonstruktor, `update(Modell).values(...)` oder einen Vergleich
    `Modell.spalte == "…"`/`!=`/`.in_([...])` geht (136), und jede String-Vorgabe der Modelle.
  - Ergebnis heute: kein fester Wert ist zu lang. Am Rand: `recurring_costs.overhead_classification` "auslastungsabhaengig"
    20/20, `ag_oder_beteiligter` 19/20, `behinderungsanzeige` in den `document_type`-Spalten 19/20.
- Die Bestandsaufnahme der Spalten hat ein Hilfsagent vorbereitet; Einordnung und Ausdrücke sind im Test ausgeführt
  (jeder Ausdruck liefert Werte, jede Spalte existiert).

### Behinderungsanzeige: (b) behalten, Ausnahme genau für die Büro-Felder der Anzeige

- Geprüft: die Ausnahme (`SIGNER_FILL_EXCEPTIONS`) betrifft die Wegfall-Unterschrift unter genau den vier Büro-Pflichtfeldern der
  Anzeige (Ursache, Beschreibung der Ursache, Betroffene Leistungen, Beginn) -- andere Felder "nur Büro" gibt es über ihr nicht.
  Beendigung ("Behinderung beendet am") und Wiederaufnahme ("Arbeit wieder aufgenommen am") sind eigene Datumsfelder (Pflicht,
  Abschnitt Wegfall); der Brief "Anzeige der Wiederaufnahme" nimmt sie aus der Kopie der Wegfall-Unterschrift, nirgends wird die
  Unterschriftszeit als Datum des Wegfalls verwendet. Bedingung erfüllt -- (b) bleibt.
- Neu: eine Ausnahme nennt die Felder, die sie abdeckt (`(Zweck, Unterschrift) -> (Feldschlüssel, Grund)`); steht ein weiteres
  Büro-Pflichtfeld über der Unterschrift, lehnt das Veröffentlichen wieder ab. Der Editor schreibt statt "Entscheidung offen"
  "der Monteur unterschreibt erst, wenn das Büro diese Felder ausgefüllt hat".

### Festlegungen 1.8.62 (bitte bestätigen)

1. **Maßgeblich ist die Kopie der ersten gültigen Unterschrift unter dem Feld** (nach Zeitpunkt) für "bleibt im Protokoll" auf
   der Seite; jede Unterschrift und der Abschluss prüfen gegen ihre eigene Kopie. Für die Abnahme aus dem Protokoll (1.8.63)
   zählt die Kopie der Unterschrift des Auftraggebers.
2. **Eine unlesbare Kopie gilt als ohne Mängel** -- sie weicht dann ohnehin von ihrer Prüfsumme ab.
3. **Feste Literale ohne Konstante stehen als Liste im Test** (`FESTE_LITERALE`); Zuweisungen `obj.spalte = "…"` findet die
   AST-Suche nicht -- ein neuer Wert dort muss von Hand in die Liste. Eine Konstante je Spalte wäre robuster, ist aber ein
   Umbau an 46 Stellen und nicht Teil dieser Runde.

### Verifikation 1.8.62

- `tests/test_v364_maengel_nach_kopie.py` (11): nach der Unterschrift verworfen und zurückdatiert -> bleibt im Protokoll, Siegel
  unverändert, Abweichung nur am Siegel des Verwerfens; vor der Unterschrift verworfen und vordatiert -> nicht im Protokoll,
  Siegel unverändert; dasselbe für den Abschluss; ein am ORM vorbei eingefügter Mangel -> "weicht ab: Mängel";
  `sealed_defect_ids()` (vier Fälle); Ausnahme der Behinderungsanzeige genau die vier Felder, Datumsfelder des Wegfalls, ein
  zusätzliches Büro-Pflichtfeld -> abgelehnt, die echte Vorlage veröffentlicht weiter.
- `tests/test_v364_feste_werte_spaltenlaenge.py` (4): Werte, Einordnung, Literale im Code, Modellvorgaben.
- Gegenproben (Marker GEGENPROBE, Dateien byte-genau zurück): 9 von 9 rot (verworfene nie in der Kopie, jeder verworfene bei
  vorhandener Kopie, Prüfung ohne die Kopie der Unterschrift, Abschluss ohne seine Kopie, Liste ohne die Kopie, Ausnahme ohne
  Feldprüfung, zu langer Unterzeichner in der Konstante, zu langes Literal im Konstruktor, zu langes Literal im Vergleich).
- Betroffene Dateien (`test_v361`–`test_v364`) unter SQLite 77 grün; die vier PostgreSQL-Tests aus `test_v362`/`test_v363`
  grün (die lokale Instanz war aus und musste gestartet werden). Volle Suite 2993 grün (mit den opt-in-Tests gegen
  PostgreSQL).

### Nebenbefunde 1.8.62 (nur gemeldet)

1. **Aufgaben- und Pipelinespalten: Schlüssel länger als die Spalte möglich.** Die Beschriftung darf 80 Zeichen haben, der
   daraus erzeugte Schlüssel (`app/task_columns.py::_slugify()`, ebenso `project_pipeline_columns.py`) wird nicht gekürzt --
   `task_columns.key`/`project_pipeline_columns.key` sind String(40), `tasks.status` (nimmt den Spaltenschlüssel) String(30).
   Unter PostgreSQL scheitert eine Spalte mit langer Beschriftung bzw. das Verschieben einer Aufgabe dorthin (500).
2. **`inspection_items.result` (String(20)) ungeprüft**: `update_inspection_item()` übernimmt jeden Text, das Schema begrenzt ihn
   nicht.
3. **Einheiten ohne Längengrenze im Schema** bei String(20)/(50)-Spalten: `RoofComponentCreate`/`Update.unit`,
   `InspectionTemplateItemCreate.unit`, `QuoteItemUpdate.unit` (nur Mindestlänge), `InvoiceItemUpdate.unit`.
4. **1.8.61 prüfte vor der Unterschrift des Auftraggebers keine Textlängen**: Beschreibung des Teils und Einwendungen nimmt das
   Protokoll bis 10.000 Zeichen, die Abnahme nur 2.000 bzw. 5.000 -- eine längere Angabe hätte die Unterschrift durchgelassen
   und die Abnahme aus dem Protokoll scheitern lassen. Behebung mit Punkt 3 (1.8.63) vorgesehen: die Prüfung ruft dann dieselbe Prüffunktion wie das
   Erfassen.
