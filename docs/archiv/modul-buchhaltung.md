# Buchhaltung (Eingangsrechnungen, Kontenstamm)

Ausgelagert aus CLAUDE.md am 2026-09-28 im Zuge der Aufteilung in eine schlanke
CLAUDE.md plus themensortiertes Archiv (siehe CLAUDE.md, Abschnitt "Modulübersicht",
und `docs/archiv/regel-abgleich.md` für die vollständige Zuordnung). Der Inhalt ist
wortgetreu (per Skript, zeilenweise) aus der vorherigen CLAUDE.md übernommen, keine
Umformulierung. Versionsangaben ("seit 1.x.y") beziehen sich auf den Stand zum
jeweiligen Zeitpunkt der ursprünglichen Aufzeichnung.

---

## Buchhaltung (seit 1.6.0, Modul "buchhaltung")

Stufe 1 -- Eingangsrechnungen erfassen und ablegen. Vorbereitende Buchhaltung, **kein Ersatz
für den Steuerberater**: sammelt und ordnet empfangene Lieferantenrechnungen mit Beleg, damit
sie später (Stufe 2) kontiert und für den Steuerberater exportiert werden können. KI-Belegauswertung
ist Stufe 3. Diese Version ist ausschließlich manuelle Erfassung -- erst ein vollständiger
Befund (Supplier/Invoice/RecurringCost/Dokumentenablage-Muster), dann zwei vom Betreiber
bestätigte Kernentscheidungen, dann in einer Runde gebaut.

### Befund, kurz zusammengefasst

- **`Supplier`** trägt bereits alles Nötige (Name, Adresse, Kontakt, `supplier_number`) und
  wird komplett über den bereits bestehenden `/api/suppliers`-Endpunkt verwaltet (liegt in
  `app/routers/resource_planning.py`, kein eigenes Business-Logic-Modul) -- Rollen-Schwelle dort
  `require_min_role(ROLE_OFFICE_AUFTRAG)`, buero_finanzen erfüllt diese Schwelle bereits über die
  Hierarchie (`ROLE_RANK`), kein Endpunkt-Umbau nötig, um einen Lieferanten aus dem
  Eingangsrechnungs-Formular heraus neu anzulegen.
- **`Invoice`** (Ausgangsrechnung) ist strukturell verwandt (Netto/Steuer/Brutto, Status,
  Skonto-Felder), aber fachlich eine andere Domäne (selbst erzeugtes, versendetes, GoBD-
  pflichtiges Dokument mit Einfrier-Snapshot-Mechanik) -- bewusst **keine gemeinsame Tabelle**,
  wie vom Betreiber vorgegeben. Übertragbar war das Prinzip fester Code-Werte für Felder mit
  Rechenregel (Steuersatz, Status) statt Optionsgruppen.
- **`RecurringCost.annual_amount`** ist bereits der gespeicherte, normierte Wert, der Schicht 3
  (`app/labor_rate.py::calculate_labor_rate()`) speist -- `RecurringCost.asset_id` (nullable FK,
  bewusst ohne Unique-Constraint) ist das bereits etablierte Muster "mehrere Fakten gegen einen
  geplanten Posten", direkt übertragbar auf Eingangsrechnung↔RecurringCost.
- **Dokumentenablage**: zwei etablierte Muster (mehrere unabhängige Dateien mit Dokumenttyp-
  Katalog wie `OperationalAssetDocument`/`RecurringCostDocument`, ODER eine einzelne, beim
  erneuten Hochladen ersetzte Datei wie `OperationalAssetInspection.document_filename`) --
  gewählt wurde das zweite, da eine Eingangsrechnung fachlich genau einen Beleg hat.

### Zwei Kernentscheidungen des Betreibers

1. **Positionen als optionale Aufschlüsselung, kein Zwang.** `IncomingInvoice.net_amount`/
   `tax_rate_pct` sind der immer vorhandene Gesamtbetrag -- eine einfache Rechnung bleibt ein
   Gesamtbetrag, eine mit gemischten Steuersätzen wird über `IncomingInvoiceItem`-Zeilen
   aufgeschlüsselt. **Existieren Positionen, muss ihre Netto-Summe zum Gesamtbetrag passen** --
   `app/incoming_invoices.py::_validate_item_sum()` meldet eine Abweichung (`ValueError` -> 422),
   statt sie still zuzulassen (Toleranz 0,01 € für Rundung). Beim Speichern werden alle
   Positionen einer Rechnung vollständig ersetzt (kein Teil-Update einzelner Zeilen) -- für die
   manuelle Erfassung in Stufe 1 ausreichend, keine eigene Positions-Historie.
   `invoice_gross_amount()` summiert bei vorhandenen Positionen deren je EIGENE Bruttobeträge
   (jede Position mit ihrem eigenen Steuersatz), nicht den Header-Satz -- eine Rechnung mit
   19%-Material und einer steuerfreien Position hat keinen gemeinsamen Satz.
2. **Plan bleibt Grundlage für den Verrechnungssatz, Ist ist der Beleg -- bestätigt, als
   dauerhafte architektonische Grenze festgehalten.** `IncomingInvoice.recurring_cost_id`
   verbindet eine Eingangsrechnung mit dem geplanten Kostenposten, gegen den sie gebucht wird --
   **ausschließlich für Anzeige/Tracking**. Keine Funktion dieses Projekts darf darüber
   `RecurringCost.annual_amount`/den Verrechnungssatz verändern (siehe `IncomingInvoice`-
   Klassendocstring, `app/models.py` -- die Grenze steht dort ausdrücklich, damit eine künftige
   Session sie nicht versehentlich verdrahtet, weil es naheliegend erscheint). Ein Plan-Ist-
   Abgleich (Summe der verknüpften Eingangsrechnungen vs. `annual_amount`) wurde als Idee
   geprüft -- er würde über `recurring_cost_id` tatsächlich fast kostenlos herausfallen, ist aber
   **nicht Teil dieser Version** (nicht ausdrücklich beauftragt), die Verknüpfung selbst
   ermöglicht ihn später ohne jeden Umbau.

### Datenmodell

Neue, von `Invoice` getrennte Tabelle `IncomingInvoice` (`app/models.py`) plus
`IncomingInvoiceItem` (optionale Positionen, cascade `all, delete-orphan`) und
`IncomingInvoiceSettings` (Singleton, `skonto_reminder_lead_days`, Default 5 Tage).

- **`payment_status`** trägt nur `"offen"`/`"bezahlt"` -- **"überfällig" wird NIE gespeichert**,
  sondern bei jedem Lesezugriff berechnet (`app/incoming_invoices.py::is_overdue()`), exakt
  konsistent mit `Invoice` (`app/invoices.py`: `is_overdue = status=="versendet" and due_date is
  not None and due_date < date.today()`). Geprüft, wie in der Anfrage verlangt, ob das bei
  Ausgangsrechnungen gespeichert oder berechnet wird -- **berechnet**, kein dritter, gespeicherter
  Statuswert, der veralten könnte. `invoice_to_dict()["display_status"]` liefert den fertigen
  Wert (`"offen"`/`"bezahlt"`/`"ueberfaellig"`) für die Listenfilterung.
- **`skonto_percent`/`skonto_deadline`**: Skontofrist als echtes `Date`-Feld (nicht als
  Tageszahl relativ zum Rechnungsdatum wie bei `Invoice.skonto_days`) -- der Beleg des
  Lieferanten nennt die Frist meist direkt als Datum, keine Zahlungsbedingungen-Textmaschinerie
  nötig. `is_skonto_due()`/`is_skonto_overdue()` greifen nur, solange `payment_status=="offen"`
  ist -- eine bereits bezahlte Rechnung braucht keine Skonto-Warnung mehr.
- **Zuordnung**: `project_id`/`asset_id`/`recurring_cost_id` sind alle optional, aber
  **höchstens eine** darf gesetzt sein -- geprüft in `_validate_single_assignment()`, bewusst
  **kein CheckConstraint** (Muster `ServiceReportPhoto`: "gehört immer zu GENAU EINEM ... ODER
  ..., nie zu beidem/keinem", ausschließlich in der Business-Logik geprüft). Eine Rechnung kann
  auch unzugeordnet bleiben.
- **`document_filename`/`document_original_name`**: ein Beleg je Rechnung, 1:1-Muster
  (`app/incoming_invoice_documents.py::replace_document()`/`delete_document_file()`, Kopie des
  ursprünglichen `OperationalAssetInspection`-Musters) -- eigener Ordner
  `DACHKONZEPTE_INCOMING_INVOICE_FILE_ROOT` unter `ERP_DATA_DIR`.
- **`last_skonto_reminder_deadline`**: Idempotenz-Stempel für die On-Demand-Erinnerung, ohne
  expliziten Reset -- Muster `RecurringCost.last_reminder_due_date`.

### Andockpunkte für Stufe 2 (Kontierung) und Stufe 3 (KI-Belegauswertung) -- explizit

- **Stufe 2**: `account_code` (String(20), optional) existiert bereits **sowohl auf
  `IncomingInvoice` als auch auf `IncomingInvoiceItem`** -- bleibt in Stufe 1 durchgängig leer.
  Bewusst ein einfaches Freitextfeld statt einer FK auf einen Kontenrahmen, der noch nicht
  existiert (Stufe 2 entscheidet erst, wie ein Kontenrahmen modelliert wird) -- ein Konto lässt
  sich später je Rechnung (kein Split nötig, `IncomingInvoice.account_code` reicht) ODER je
  Position (Split nötig, `IncomingInvoiceItem.account_code`) eintragen. Beide Felder existieren
  bereits, keine Migration nötig, wenn Stufe 2 kommt -- höchstens eine spätere Ablösung des
  Freitexts durch eine echte FK, falls ein Kontenrahmen als eigene Tabelle entsteht.
- **Stufe 3**: `supplier_id`/`supplier_invoice_number`/`invoice_date`/`net_amount`/
  `tax_rate_pct`/`due_date`/`skonto_percent`/`skonto_deadline` sind exakt die Felder, die eine
  künftige automatische Belegauswertung füllen würde -- das Modell ist 1:1 darauf zugeschnitten,
  keine Umstrukturierung nötig, wenn Stufe 3 kommt.

### Lieferant inline anlegen

Kein neuer Endpunkt -- das Formular (`incoming_invoices.html`) zeigt neben dem
Lieferanten-Dropdown einen "+ Neuer Lieferant"-Umschalter mit einem kompakten Unterformular
(Name Pflicht, Adresse/Kontakt optional). Beim Anlegen wird direkt `POST /api/suppliers`
aufgerufen (bereits bestehender, unveränderter Endpunkt), der neue Lieferant erscheint sofort im
Dropdown und wird automatisch ausgewählt -- kein Seitenwechsel, kein `prompt()` (Regel 4). Die
volle Lieferantenpflege (Adresse im Detail, `supplier_number` u. Ä.) bleibt weiterhin
ausschließlich über `/master-data#suppliers` erreichbar, Regel 10 gilt dafür unverändert -- das
Inline-Formular ist ein Satellit, keine zweite Stammdatenpflege.

### Skonto-Warnung, überfällige Hervorhebung, Ansicht

`check_due_skonto_and_create_reminders()` (`app/incoming_invoices.py`) ist das On-Demand-Muster
von `check_due_cancellations_and_create_reminders()` (`app/recurring_costs.py`) -- läuft nur
beim Laden der Eingangsrechnungen-Liste, kein Scheduler. Erzeugt eine Aufgabe mit
`min_visible_role=ROLE_OFFICE_FINANZEN` (wie bei der Betriebskosten-Kündigungsfrist: eine
Skontofrist geht nur Finanzen/Admin etwas an). Die Liste (`GET /eingangsrechnungen`) zeigt
zusätzlich eine visuelle Hervorhebung (überfällige Zeilen, Skonto-läuft-ab-/verpasst-Badges) --
beides, wie beim Betriebskosten-Vorbild ("Hervorhebung UND Aufgabe"), nicht entweder-oder.

Filter (Status/Lieferant/Zeitraum) laufen über `GET /api/incoming-invoices` -- `supplier_id`/
`date_from`/`date_to` als echte SQL-`WHERE`-Bedingungen, `payment_status` dagegen in Python
gegen den berechneten `display_status` gefiltert (kann keine SQL-Spalte sein, siehe oben).
`GET /api/incoming-invoices/open-liabilities` liefert die Summe offener Verbindlichkeiten
(brutto) plus die Skonto-Warnliste, Muster `RecurringCost.overview_summary()`.

### Rollen und Modul

Modul-Schlüssel **`"buchhaltung"`** (`"betriebskosten"` war bereits belegt). Ausnahmslos
`require_min_role(ROLE_OFFICE_FINANZEN)` an jedem Endpunkt (`app/routers/incoming_invoices.py`)
-- dieselbe Finanzen-Achse wie Betriebskosten-Übersicht/Kalkulationsgrundlagen, kein
`_any_role_dep`. Sidebar-Link und Einstellungen-Abschnitt (Skonto-Vorlaufzeit) sind genauso
strenger gegated als "Finanzen"/"Mahnwesen" selbst (nur buero_finanzen/admin, kein
buero_auftrag) -- Muster `is_module_enabled('betriebskosten') and can(current_user, 'admin',
'buero_finanzen')`.

**Angriffstest bestätigt**: `buero_auftrag`/`field` kommen über keinen Weg an die
Eingangsrechnungen -- Liste, Einzelabruf (auch mit geratener ID -- 403, nicht 404, bevor
irgendeine Geschäftslogik läuft), Beleg-Upload/-Download/-Löschen (auch über eine geratene
Rechnungs-ID), Einstellungen, `check-due`, und die finanz-adressierte Skonto-Aufgabe (weder in
der Liste noch im gemeinsamen Eingang sichtbar, auch mit bekannter ID nicht übernehmbar). 31
neue Tests (`tests/test_v293_incoming_invoices.py`), volle Suite: 1719 Tests grün. Zusätzlich
end-to-end gegen eine isolierte Testinstanz (eigene, temporäre SQLite-Datenbank, niemals gegen
die echte `dachkonzepte_erp.db`) über echtes HTTP verifiziert: Bootstrap-Admin, Zwei-Faktor-
Ersteinrichtung, Lieferant + Eingangsrechnung mit gemischten Positionen anlegen (Brutto korrekt
je Position berechnet), Liste/Summen-Endpunkt liefern die erwarteten Werte, die gerenderte Seite
enthält alle erwarteten Elemente (Supplier-Auswahl, Editor, Positionstabelle, Sidebar-Link).

### Stufe 2, erster Teil: Kontenstamm mit manueller Pflege und Vorkontierung (seit 1.6.1)

Fortsetzung von Stufe 1 -- ausdrücklich **nicht** Teil dieser Runde: der Import der
Steuerberater-Kontendatei und der DATEV-Export (beide brauchen echte Beispieldateien vom
Steuerberater, die noch nicht vorliegen). Erst ein vollständiger Befund zu drei Punkten
(`account_code`-Feld, bestehende Konten/Kontenrahmen-Konzepte, Muster für pflegbare Stammdaten),
dann zwei vom Betreiber angefragte Entscheidungen (Startbestand ja/nein, wie `account_code`
umgestellt wird), dann in einer Runde gebaut. Alles ausschließlich `buero_finanzen`/`admin`, im
bestehenden Modul `"buchhaltung"`.

#### Befund

- **`account_code`** war in Stufe 1 ein einfaches, immer leeres `String(20)`-Freitextfeld auf
  `IncomingInvoice` UND `IncomingInvoiceItem` -- ausdrücklich als Andockpunkt für eine spätere
  Kontierung angelegt (siehe CLAUDE.md-Fassung vor dieser Version), aber nie befüllt: 0 echte
  Zeilen mit einem gesetzten Wert.
- **Kein bestehendes Konten-/Kontenrahmen-Konzept im Projekt.** `TaxKey` (Steuerschlüssel,
  `app/tax_keys.py`) ist eine pflegbare Stammdatentabelle für STEUERLICHE Kennzeichen (z. B.
  "19% Vorsteuer abziehbar"), keine Kontonummer -- geprüft und bewusst getrennt gehalten: ein
  Konto (WAS wurde gebucht) und ein Steuerschlüssel (WELCHE Steuerbehandlung) sind zwei
  unabhängige Dimensionen, die sich auch beim Steuerberater nie zu einem Feld verschmelzen. Die
  DATEV-Buchungscodes an den Zeitarten (`TimeTrackingSettings.datev_wage_type_*`,
  siehe "Schlechtwetter-Zeitarten") sind Lohnarten für die Personalabrechnung -- eine dritte,
  wiederum unabhängige Dimension, kein Sachkonto. Keine der drei bestehenden Konzepte war für den
  Kontenstamm wiederverwendbar, aber `TaxKey` war das direkte Struktur-Vorbild (siehe unten).
- **Pflegbare Stammdaten-Listen**: `SettingOptionGroup`/`SettingOption` (Optionsgruppen) für
  reine Label-Listen ohne Zusatzfelder; eine echte Tabelle (`TaxKey`, `PaymentTerm`,
  `RoofComponentType` u. v. a.), sobald mehr als ein Feld + eine Rechenregel/ein Zusatzattribut
  dazukommt. Der Kontenstamm braucht Kontonummer + Bezeichnung + optionalen Standard-Steuersatz
  -- eindeutig der zweite Fall, `Account` ist deshalb eine echte Tabelle nach dem `TaxKey`-Muster
  (Kontonummer statt `key`, `active`-Flag statt eines zusätzlichen "ist Standard"-Zustands).

#### Punkt 2: der Kontenstamm -- Startbestand: **nein**, bewusst leer

Neue Tabelle `Account` (`app/models.py`): `account_number` (String(20), indiziert),
`label`, `default_tax_rate_pct` (optional, `Numeric(5,2)`, gegen `ACCOUNT_TAX_RATES = (19.00,
7.00, 0.00)` geprüft -- fester Code-Wert wie bei `RecurringCost.overhead_classification`, keine
Optionsgruppe), `active` (Bool, Default an -- **nie Löschen**, nur Archivieren, auch für ein nie
verwendetes Konto: dasselbe Muster wie `TaxKey.archived`). `UniqueConstraint` auf
`account_number`.

**Entscheidung, wie vom Betreiber ausdrücklich zur eigenen Einschätzung gestellt**: **kein**
Startbestand mit vorbelegten SKR-04-Nummern, obwohl der Betreiber selbst zu einem kleinen,
sinnvollen Startbestand neigte. Begründung: das harte Kriterium der Anfrage lautete wörtlich
"echte SKR-04-Nummern, keine erfundenen". SKR 04 und SKR 03 sind zwei unterschiedliche
Kontenrahmen mit unterschiedlichen Nummernkreisen für dieselben fachlichen Konten (z. B. steht
eine Kontenklasse in SKR 03 an anderer Stelle als in SKR 04) -- eine Verwechslung der beiden
Systeme ist ein bekanntes, reales Fehlerrisiko. Für die GRUNDSTRUKTUR (Kontenklassen-Aufbau, das
Prozessgliederungsprinzip von SKR 04 allgemein) besteht ausreichende Sicherheit, aber für die
KONKRETEN, einzelnen Kontonummern der tatsächlich gebrauchten Aufwandskonten (Wareneinkauf,
Miete, Versicherung, Fremdleistungen) ließ sich diese Sicherheit nicht mit der vom Betreiber
verlangten Garantie ("echte Nummern, keine erfundenen") herstellen, ohne eine verifizierbare
Quelle (z. B. die tatsächliche SKR-04-Kontentabelle) einzusehen, die in dieser Sitzung nicht
vorlag. Ein seed mit teilweise falschen Nummern wäre schlimmer als gar keiner -- ein Betreiber,
der einem vorbelegten Konto vertraut, prüft es typischerweise nicht gegen den echten Kontenplan.
Die Tabelle bleibt deshalb leer, bis der Betreiber Konten manuell anlegt (idealerweise nach
Rücksprache mit dem Steuerberater) oder der spätere Datei-Import (Stufe 2, zweiter Teil, nicht
Teil dieser Version) sie befüllt -- exakt dieselbe Zurückhaltung, die `TaxKey` bereits für
denselben Risikotyp übt ("keine Rechtsberatung, bitte mit dem Steuerberater abgleichen").
`Account`-Klassendocstring (`app/models.py`) hält diese Begründung fest, damit eine künftige
Sitzung nicht versucht ist, "nachträglich doch ein paar Konten zu seeden".

**Manuelle Pflege**: `app/accounts.py` (Muster `app/tax_keys.py`, aber ohne
`ensure_default_*()`-Funktion) -- `create_account()`/`update_account()` validieren
`account_number`-Eindeutigkeit (bei Update: schließt die eigene Zeile aus) und
`default_tax_rate_pct` gegen `ACCOUNT_TAX_RATES`. `app/routers/accounts.py`
(`GET/POST /api/accounts`, `GET/PUT /api/accounts/{id}`) -- ausnahmslos
`require_min_role(ROLE_OFFICE_FINANZEN)` plus `is_module_enabled(db, "buchhaltung")`, Muster
`app/routers/tax_keys.py`. Neuer Abschnitt "Kontenstamm" in Einstellungen (`settings.html`,
gleiche strenge Gate wie das übrige Buchhaltungs-Menü) -- Liste, Anlegen/Bearbeiten-Panel,
Archivieren/Aktivieren, ein sichtbarer Hinweistext, warum keine Konten vorbelegt sind.

**Andockpunkt für den späteren Datei-Import (Stufe 2, zweiter Teil, NICHT Teil dieser
Version)**: ein künftiger Import liest die Kontendatei des Steuerberaters zeilenweise und legt
über `account_number` (der stabile, natürliche Schlüssel, `UniqueConstraint`) je Zeile ein Konto
an oder aktualisiert es (Upsert) -- `create_account()`/`update_account()` validieren dafür
bereits alles Nötige, **keine Änderung an der Tabelle oder an diesen Funktionen nötig**, wenn
der Import gebaut wird. Der Andockpunkt für den DATEV-Export (ebenfalls nicht Teil dieser
Version): ein künftiger Export liest `IncomingInvoice.account_id`/`IncomingInvoiceItem.
account_id` und löst sie über `Account.account_number` auf -- beide Felder existieren bereits
(siehe Punkt 3), keine weitere Vorbereitung nötig.

#### Punkt 3: die Vorkontierung -- `account_code` wird zu `account_id` (echte FK), nicht zu einem
Nummern-Verweis-String

**Entscheidung**: der freie `account_code`-String aus Stufe 1 wird durch eine echte
Fremdschlüssel-Spalte `account_id: int | None` (FK auf `accounts.id`) ersetzt, nicht durch einen
weiterhin freien String, der die Kontonummer referenziert. Begründung: jede andere Relation in
diesem Projekt (`project_id`, `asset_id`, `recurring_cost_id`, `supplier_id`, ...) ist eine
FK-auf-Surrogat-ID, niemals ein natürlicher-Schlüssel-String -- eine Ausnahme nur hier hätte eine
zweite, abweichende Konvention eingeführt, ohne einen Vorteil zu bieten (referentielle Integrität,
Umbenennungssicherheit und die bereits bestehende Eager-Load-Infrastruktur sprechen für die FK).
**Migration war sicher, weil 0 reale Zeilen betroffen waren**: direkt gegen die echte, lokale
Datenbank geprüft, bevor die Spalte gedroppt wurde -- 0 Zeilen in `incoming_invoices` und
`incoming_invoice_items` insgesamt (Stufe 1 war zu diesem Zeitpunkt noch nicht im echten Betrieb
genutzt), ein destruktiver Spaltentausch (`DROP account_code` + `ADD account_id`) war deshalb
verlustfrei, kein Backfill nötig.

Migration `329725277349`: legt `accounts` an, tauscht auf `incoming_invoices`/
`incoming_invoice_items` `account_code` gegen `account_id` (benannte FK-Constraints --
SQLite-Batch-Modus verlangt unter Alembic einen echten Namen, `None` scheitert mit
`ValueError: Constraint must have a name`, siehe unten). `Account.default_tax_rate_pct` wird
beim Wählen eines Kontos **client-seitig** als Vorschlag übernommen
(`incoming_invoices.html::applyAccountDefaultTaxRate()`), ist aber jederzeit übersteuerbar -- die
Rechnung entscheidet den tatsächlichen Steuersatz, nicht das Konto. **Kein serverseitiger Zwang**:
`create_invoice()`/`update_invoice()` übernehmen den Kontosatz nie automatisch beim Speichern,
belegt durch `test_account_default_tax_rate_is_never_applied_server_side` (Konto mit 0 %,
Rechnung explizit mit 19 % -- bleibt 19 %).

**Je Rechnung ein Konto ODER je Position** -- `is_invoice_accounted()` (`app/incoming_invoices.py`)
ist die eine Funktion, die "kontiert" definiert: **existieren Positionen, zählt ausschließlich
deren eigener Kontobezug** (jede Position braucht ein Konto, das Header-`account_id` wird dann
irrelevant, auch wenn es noch gesetzt ist); **existieren keine Positionen, zählt der
Header-Kontobezug**. `invoice_to_dict()`/`_item_to_dict()` lösen `account_id` zu
`account_number`/`account_label` auf (Eager-Load in `_invoice_query()`), plus das neue Feld
`is_accounted: bool`.

**Vorkontierung, keine Buchung -- Docstring-Warnung**: `IncomingInvoice.account_id`s Docstring
(`app/models.py`) hält ausdrücklich fest, dass das ERP an keiner Stelle eine steuerliche
Bewertung vornimmt und keinen finalen Buchungssatz erzeugt -- der Steuerberater prüft und bucht,
diese Zuordnung ist nur ein Vorschlag/eine Vorbereitung für den späteren DATEV-Export. Dieselbe
Warnung steht auf `Account` selbst (siehe oben) -- **zwei** Stellen, damit sie unabhängig vom
Einstiegspunkt einer künftigen Sitzung gefunden wird.

**Gefundener, projektrelevanter SQLite-Migrations-Fallstrick**: Alembics `batch_alter_table()`
verlangt unter SQLite einen **explizit benannten** `create_foreign_key()`-Aufruf --
Autogenerate erzeugt standardmäßig `create_foreign_key(None, ...)`, was beim internen
Tabellen-Kopieren-und-Ersetzen mit `ValueError: Constraint must have a name` scheitert. Fix: dem
Aufruf (und dem entsprechenden `drop_constraint()` in `downgrade()`) einen echten Namen geben
(`f"fk_{table}_account_id_accounts"`). Gilt für jede künftige FK-Migration auf SQLite in diesem
Projekt, nicht nur diese eine.

#### Punkt 4: Ansicht -- Kontiert/Nicht kontiert sichtbar

`incoming_invoices.html`: neue Tabellenspalte "Kontierung" mit einem Kontiert-/
Nicht-kontiert-Badge (aus `is_accounted`) -- die unkontierten Zeilen fallen dadurch optisch auf,
bevor ein späterer DATEV-Export eine übersieht. Header-Konto-Feld ist jetzt ein `<select>` aus
dem Kontenstamm (blendet sich aus, sobald Positionen existieren -- dann entscheidet ausschließlich
deren je eigener Kontobezug, `updateAccountFieldVisibility()`), jede Position hat ihr eigenes
Konto-`<select>`. Die "Kontenübersicht" in Einstellungen (siehe Punkt 2) ist dieselbe pflegbare
Liste, kein zweiter Anzeigeort.

#### Tests, Migration, Verifikation

`tests/test_v294_accounts_vorkontierung.py` (23 Tests) -- Kontenstamm (kein Startbestand,
CRUD, Eindeutigkeit, Steuersatz-Validierung, kein Löschen, Archivieren/Aktivieren-Filter),
Vorkontierung (`is_invoice_accounted()` für Header- und Positionsfall inkl. des
"Header-Konto wird bei vorhandenen Positionen irrelevant"-Falls, Validierung unbekannter
`account_id` auf Header UND Position, Steuersatz nie serverseitig übernommen, ein archiviertes
Konto bleibt an einer bereits kontierten Rechnung gültig), und der geforderte Angriffstest:
`buero_auftrag`/`field` bekommen 403 auf jeden `/api/accounts`-Endpunkt (Liste, Einzelabruf auch
mit geratener ID, Anlegen, Ändern) UND auf eine Eingangsrechnung mit gesetztem Konto (rekursiver
Schlüssel-Scan bestätigt: kein `account_number`/`label`/`default_tax_rate_pct` in einer
403-Antwort), sowie bei deaktiviertem Modul für jede Rolle inkl. Finanzen/Admin. Volle Suite:
1740 Tests grün. Migration erfolgreich gegen die echte, lokale `dachkonzepte_erp.db` angewendet
und per direkter `PRAGMA table_info`-Abfrage nachgemessen (0 Datenverlust, Schema exakt wie
erwartet).

### Beleg-Upload schon beim Anlegen (seit 1.6.3)

Bis dahin ließ sich ein Beleg erst im Bearbeiten-Modus hochladen -- `POST /api/incoming-invoices/
{invoice_id}/document` verlangt eine bereits existierende `invoice_id` (Muster
`app/routers/operational_assets.py`), im Anlegen-Formular gab es dafür kein Feld. Auftrag: dasselbe
Warteschlangen-Muster wie beim Betriebsmittel (1.5.6, `pendingAssetDocuments` in
`master_data_form.html::assetForm()`) anwenden -- **kein Backend-Code geändert**, exakt wie beim
Vorbild: kein neuer Endpunkt, kein neues Schema, keine neue Migration. Der bereits bestehende
Upload-Endpunkt wird lediglich zu einem anderen Zeitpunkt (nach dem Anlegen, statt nur im
Bearbeiten-Modus) aus demselben Formular heraus aufgerufen.

**Punkt 1 -- geprüft, ob sich die Warteschlangen-Logik jetzt (zweites Vorkommen) als gemeinsamer
JS-Baustein lohnt: nein, bewusst zwei eigenständige Umsetzungen.** Die beiden Fälle sind
strukturell verschieden, nicht nur zufällig ähnlich benannt:
- Ein Betriebsmittel kann **mehrere unabhängige** Dokumente tragen (`OperationalAssetDocument`,
  eigene Tabelle), jedes mit eigenem `document_type` + optionaler `notes` -- die 1.5.6-Warteschlange
  ist deshalb ein Array `{document_type, file, notes}[]`, mit einer eigenen "+ Vormerken"-Liste
  samt Entfernen-Button je Zeile (`renderAssetDocQueue()`).
- Eine Eingangsrechnung trägt fachlich **immer nur genau EINEN** Beleg (1:1-Ersetzungsmuster,
  `IncomingInvoice.document_filename`/`document_original_name`, siehe `app/incoming_invoice_
  documents.py`) -- kein `document_type`, keine `notes` je Datei, kein Mehrfach-Upload. Die
  Warteschlange ist hier bestenfalls ein einzelnes, optionales `File`-Objekt (`pendingInvoiceDocument`),
  keine Liste.

Ein "gemeinsamer Baustein" hätte entweder die einfachere Eingangsrechnung-Variante künstlich auf
das Array-mit-Metadaten-Schema des Betriebsmittels aufblasen müssen (ein Array mit immer nur einem
Element, ein `document_type`-Feld, das dort nie existiert), oder umgekehrt eine generische
Konfigurationsschicht (austauschbare `buildFormData()`/`renderItem()`-Callbacks je Aufrufer)
gebraucht, deren Indirektion mehr Code wäre als die eigentliche Logik selbst (bei beiden
Implementierungen zusammen keine 40 Zeilen). Das deckt sich mit der bereits im Projekt etablierten
Konvention (siehe CLAUDE.md "Stack & Struktur": kein gemeinsames JS-Modul für kleine Schnipsel,
`_debounce.html` ist die bewusste Ausnahme für eine tatsächlich nicht-triviale, mehrfach
IDENTISCHE Timer-Logik) -- ein Baustein lohnt sich erst, wenn die Form wirklich dieselbe ist, nicht
schon beim zweiten Vorkommen einer ähnlichen IDEE. Die zugrunde liegende Verhaltensregel (vorgemerkte
Datei erst nach erfolgreichem Anlegen hochladen, ein Fehlschlag darf das Anlegen nicht rückgängig
machen) ist als Kommentar an beiden Stellen im Code festgehalten, nicht nur hier.

Kleiner, durch die Verschiedenheit der beiden Seiten bedingter Unterschied bei der Fehleranzeige:
das Betriebsmittel-Formular navigiert nach dem Anlegen auf eine ANDERE Seite (`/betriebsmittel/
{id}`) und zeigt einen Upload-Fehlschlag deshalb per `alert()` (die Statuszeile ginge beim
Seitenwechsel sonst verloren). Der Eingangsrechnungen-Editor bleibt dagegen auf derselben Seite und
wechselt nur in den Bearbeiten-Modus (`openEditEditor(saved.id)`, das war schon vor dieser Änderung
so) -- ein Upload-Fehlschlag steht deshalb einfach als Text in der bereits sichtbaren
`#editorStatus`-Zeile, kein Popup nötig.

**Punkt 2 -- Fehlerfälle, per CDP-Browsertest gegen eine isolierte Testinstanz einzeln
nachgewiesen** (siehe Verifikation unten):
- **Anlegen scheitert** (fehlendes Pflichtfeld ODER, serverseitig, `_validate_item_sum()` lehnt
  einen Positions-Summenabgleich ab -> 422): `docToUpload` wurde vor dem `try`-Block aus dem
  globalen `pendingInvoiceDocument` gelesen, der eigentliche Upload-Aufruf steht aber ERST NACH
  dem erfolgreichen Anlegen im selben `try` -- schlägt das Anlegen fehl, springt die Ausführung
  direkt in den äußeren `catch`, der Upload-Code wird nie erreicht. `pendingInvoiceDocument`
  bleibt dabei unverändert gesetzt, die Dateiauswahl im `<input>` bleibt erhalten -- kein
  verwaister Datensatz (die Rechnung wurde ja nie angelegt), keine verlorene Datei (per Test
  bestätigt: Rechnungszähler unverändert, `pendingInvoiceDocument`/`#createDocFile.files` nach
  dem Fehlschlag weiterhin gesetzt).
- **Anlegen gelingt, der Upload scheitert** (z. B. Datei über 10 MB): die Rechnung bleibt
  bestehen (kein Rollback), `saveInvoice()` zeigt eine Statuszeile, die AUSDRÜCKLICH den
  Dateinamen und den Grund nennt und auf den Bereich "Beleg" weiter unten verweist -- exakt
  dorthin wechselt die Seite ohnehin schon (`openEditEditor(saved.id)`), wo derselbe, bereits
  bestehende Bearbeiten-Modus-Upload (`uploadDocument()`) den erneuten Versuch entgegennimmt.
  Kein stilles Verschlucken -- der Fehler steht so lange sichtbar, bis der Nutzer erneut speichert
  oder die Seite verlässt.

**Punkt 3 -- Upload-Feld bewusst OBEN im Anlegen-Formular, ANDOCKPUNKT für die künftige
KI-Belegauswertung (Stufe 3, noch nicht gebaut).** `IncomingInvoice`s Klassendocstring
(`app/models.py`) nennt bereits seit 1.6.0 die Felder, die eine künftige automatische
Belegauswertung füllen würde (`supplier_id`/`supplier_invoice_number`/`invoice_date`/
`net_amount`/`tax_rate_pct`/`due_date`/`skonto_percent`/`skonto_deadline`) -- in diesem
künftigen Ablauf kommt der Beleg IMMER zuerst (Upload/Foto), erst danach füllt die KI die
restlichen Felder. Das neue `#createDocumentSection` steht deshalb als ERSTES Element im
Anlegen-Formular, noch vor der Lieferantenauswahl (`.supplier-row`) -- nicht aus rein optischen
Gründen, sondern weil genau diese Stelle der Ort ist, an dem eine künftige Stufe-3-Funktion
ansetzen wird: Beleg hochladen -> (künftig) automatisch ausgewertet -> Formularfelder darunter
vorausgefüllt. Bis Stufe 3 gebaut ist, bleibt es bei reiner manueller Erfassung, das Feld tut
nichts anderes als vormerken und nach dem Speichern hochladen.

**Rechte unverändert** -- kein neuer Endpunkt, keine neue Rollenprüfung nötig: der bereits
bestehende `POST /api/incoming-invoices/{invoice_id}/document` bleibt unter
`require_min_role(ROLE_OFFICE_FINANZEN)` (`app/routers/incoming_invoices.py`), unverändert seit
1.6.0 -- `buero_auftrag`/`field` erreichen diesen Bereich weiterhin an keiner Stelle.

**Verifikation**: `node --check` gegen den extrahierten `<script>`-Block (keine JS-Syntaxfehler).
Zusätzlich ein echter, CDP-gesteuerter Headless-Chrome-Durchlauf gegen eine isolierte, temporäre
SQLite-Testinstanz (Bootstrap-Admin, Zwei-Faktor-Ersteinrichtung mit `pyotp`, ein Testlieferant --
niemals gegen `dachkonzepte_erp.db`): das Beleg-Feld steht nachweislich (DOM-Reihenfolge,
`compareDocumentPosition()`) vor der Lieferantenauswahl, per Screenshot zusätzlich visuell
bestätigt; Szenario "Anlegen scheitert" (Positions-Summenabgleich, `50,00 €` gegen `100,00 €`)
zeigt die erwartete Server-Fehlermeldung, lässt die vorgemerkte Datei unangetastet und legt
keine Rechnung an (Zähler unverändert); Szenario "Anlegen gelingt, Upload scheitert" (>10 MB)
legt die Rechnung nachweislich an (`has_document: false` direkt danach), zeigt Dateiname + Grund
in der Statuszeile, und der anschließende Retry über das bestehende Bearbeiten-Modus-Beleg-Feld
gelingt nachweislich (`has_document: true` danach); das Beleg-Feld blendet sich beim Wechsel in
den Bearbeiten-Modus einer bereits bestehenden Rechnung korrekt wieder aus. Keine neuen
`pytest`-Tests (reine Frontend-Änderung, Muster 1.5.6) -- volle Suite weiterhin 1764 Tests grün.
