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
| **2c-2b** | 1.8.51, 1.8.52 | Vorweg: Sperre an eine gültige Fassung binden (nur gemeldet -- es gibt kein Zurückziehen einer Fassung), Belege am Mangel nachreichen, Aufgabentitel mit Kurzfassung, CLAUDE.md `update.sh`/`backup.sh` (1.8.51); Monteur-Sicht auf Mängel in `/mobil` mit Positivliste, "beseitigt" melden mit Foto, idempotent über `client_uuid` (1.8.52) | erledigt bis auf das Zurückziehen einer Fassung (Entscheidung offen) |

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

### Festlegungen 1.8.51 (bitte bestätigen)

1. **Belege als eigener Eintrag "belege"**, nicht im Eintrag "fotos" -- der Verlauf unterscheidet Fotos und Belege; je
   Speichern nur eine Art.
2. **Belege nachreichen auch nach der Erledigung** (wie Fotos), nicht nach dem Verwerfen; nur das Büro.
3. **Kurzfassung 60 Zeichen** an der Wortgrenze; Titel höchstens 255 Zeichen wie bisher.
4. **Pfad von `update.sh`** in CLAUDE.md ohne Verzeichnis -- bitte den Pfad nennen, wenn er dort stehen soll.

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

### Festlegungen 1.8.52 (bitte bestätigen)

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
   den Grenzen des Büros (10 je Meldung, je 15 MB, zusammen 30 MB).
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
   auf der Auftragsseite. Möglich wäre eine Folge "Beseitigung abnehmen" -- nicht gebaut.
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
