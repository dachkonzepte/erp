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
   `/home/tobias/backup.sh` den ganzen Datenordner sichert, steht nicht im Repo -- bitte prüfen.
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

### Festlegungen 1.8.47 (bitte bestätigen)

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
