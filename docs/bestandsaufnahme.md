# Bestandsaufnahme DACHKONZEPTE ERP

Stand: 09.09.2026, Version 1.2.12. Reine Recherche gegen den tatsächlichen Code (kein
Produktivcode geändert, kein Schema geändert). Zweck: CLAUDE.md verlässlich auf den echten
Stand bringen, bevor das Wartungsmodul weiter ausgebaut wird.

## Inhalt

1. Alembic-Historie
2. Vollständiges Modell-Inventar (`app/models.py`)
3. Das Objekt-/Gebäudemodell (`Property`)
4. `MaintenanceContract` vollständig
5. `ServiceReport` vollständig + PDF
6. `TimeEntry`
7. Planungs-/Plantafel-Modul
8. `OPTIONAL_MODULES`
9. Datei-Upload-Pfade unter `data/`
10. Mobile-Tauglichkeit
11. Abweichungen zu CLAUDE.md
12. Empfehlungen

---

## 1. Alembic-Historie

Direkt per `alembic history --verbose` und `alembic heads` geprüft (nicht aus CLAUDE.md
übernommen). **Ein Head, `8adb7e406857`, DB ist aktuell** (`alembic current` bestätigt
`8adb7e406857 (head)`).

Vollständige Kette, älteste zuerst, 33 Migrationen insgesamt:

| # | Revision | Datum | Titel |
|---|---|---|---|
| 1 | `2befd7907eef` | 2026-09-02 08:15 | baseline: bestehendes Schema (`<base>` als Parent) |
| 2 | `6209c357b046` | 2026-09-02 19:01 | Kataloge und katalogbezogene Kalkulation |
| 3 | `806513205b5c` | 2026-09-03 15:33 | Materialkatalog |
| 4 | `d06425e23f3c` | 2026-09-03 17:36 | Materialkataloge |
| 5 | `e057d15af828` | 2026-09-04 08:15 | Rechnungswesen |
| 6 | `5581ab4df6d4` | 2026-09-04 09:16 | Zahlungsbedingungen |
| 7 | `369f94b5d5d3` | 2026-09-04 10:24 | Skonto |
| 8 | `8c0bddc8321c` | 2026-09-04 10:45 | Zahlungsbedingungen Textvorlage |
| 9 | `bb175f455b64` | 2026-09-04 11:39 | Steuerschluessel und Dokumentstruktur |
| 10 | `0946c1a4c4be` | 2026-09-04 15:37 | Mahnwesen: reminder_levels und reminders |
| 11 | `6285c0bb4e0d` | 2026-09-04 17:26 | Dokumentenmanagement: customer_documents und subfolder |
| 12 | `58e4e0719407` | 2026-09-04 18:09 | PDF-Layoutdesigner: DocumentLayoutBlock und Firmenlogo |
| 13 | `9e959412c279` | 2026-09-05 10:10 | Briefbogen-Hintergrund und Kundenadresse/Meta-Tabelle getrennt |
| 14 | `fff4d8ae8433` | 2026-09-05 10:57 | Konfigurierbare Tabellenfelder (Meta, Summen, Positionsliste) |
| 15 | `ef7b95affc19` | 2026-09-05 00:00 | Mehrseiten-Unterstuetzung: Hintergrund-Wiederholung |
| 16 | `4d6a0e28804a` | 2026-09-05 12:11 | Randabstaende je Seitentyp |
| 17 | `53778598ef1d` | 2026-09-07 07:01 | Mahnwesen-Automatisierung: automatische Entwuerfe |
| 18 | `e52a06d5ff38` | 2026-09-07 08:50 | E-Mail-Versand: SMTP-Einstellungen und Mahnstufen-Textbausteine |
| 19 | `15b775e5bd3f` | 2026-09-07 09:49 | Microsoft 365 OAuth2 Graph API als Versandweg |
| 20 | `3eb9f52b38ab` | 2026-09-07 11:38 | E-Mail-Versand fuer Rechnungen und Vorlagen-Infrastruktur |
| 21 | `b9b377efedd0` | 2026-09-07 12:09 | E-Mail-Versand fuer Angebote |
| 22 | `26c9609a8d41` | 2026-09-07 12:28 | E-Mail-Versand fuer Auftraege |
| 23 | `c208d96579ce` | 2026-09-07 13:04 | Mustervorgaenge is_template |
| 24 | `4d2f2e7b83f3` | 2026-09-07 13:42 | Projekte archivieren |
| 25 | `609b69008de8` | 2026-09-07 17:05 | accent_color zu general_settings |
| 26 | `ad3efb9bf522` | 2026-09-08 00:06 | user_dashboard_widgets Tabelle |
| 27 | `9609f7401158` | 2026-09-08 12:22 | enabled_modules und tasks Tabellen |
| 28 | `6ed174efcf4a` | 2026-09-08 14:28 | task_columns, checklist_items, task_settings |
| 29 | `f866cb9b23e7` | 2026-09-08 16:27 | maintenance_contracts Tabelle |
| 30 | `6d2ca9ae3761` | 2026-09-08 16:53 | service_reports Tabelle |
| 31 | `2ba59ab6f30a` | 2026-09-08 17:52 | Daten-Migration: Reparatur/Wartung Tätigkeiten |
| 32 | `5c8787a1145b` | 2026-09-08 18:11 | maintenance_settings Tabelle |
| 33 | `14ab5b62113d` | 2026-09-08 19:01 | Wartungsvertrag Objekt optional |
| 34 | `8adb7e406857` | 2026-09-08 19:17 | Archivieren für Wartungsverträge und Aufgaben **(head)** |

**Wichtig, siehe Abschnitt 11:** CLAUDE.md behauptet, `bb175f455b64` sei die älteste Migration.
Tatsächlich gibt es **8 weitere Migrationen davor**, angeführt von der Baseline `2befd7907eef`.

---

## 2. Vollständiges Modell-Inventar (`app/models.py`)

Die Datei hat 2361 Zeilen und enthält **104 SQLAlchemy-Modellklassen** (die Zählung "104" ergibt
sich aus den unten gelisteten 1–104; einige sehr kleine Singleton-/Zusatztabellen wurden von der
Recherche in einer Sammelzeile zusammengefasst, sind aber alle einzeln aufgeführt). Es ist die
**einzige** Datei im Projekt mit SQLAlchemy-Modellen (per Grep über `app/` bestätigt).

Die vollständige, klassenweise Liste (Tabellenname, alle Spalten mit Typ/Nullable/Default,
Fremdschlüssel, Relationships, `__table_args__`) ist zu umfangreich für den Fließtext dieses
Berichts und liegt als eigene Anlage vor:

➡️ **Siehe [`docs/bestandsaufnahme_modelle.md`](bestandsaufnahme_modelle.md) für alle 104 Klassen
im Detail.**

Kurzüberblick nach Fachbereich (Klassenanzahl, ohne Anspruch auf eine einzig richtige Einteilung):

| Bereich | Klassen (Auszug) | Anzahl |
|---|---|---|
| Leistungskatalog/Kalkulation | `Catalog`, `Service`, `Material`, `ServiceMaterial`, `CalculationSettings`, `ServiceCalculation`, `MaterialCalculationOverride`, `MaterialGroup`, `ImportBatch` | 9 |
| Kunde/Objekt/Anfrage | `Customer`, `CustomerProfile`, `CustomerExtraInfo`, `CustomerDocument`, `Property`, `Inquiry` | 6 |
| Projekt/Angebot | `Project`, `ProjectProfile`, `ProjectDocument`, `Quote`, `QuoteItem`, `QuoteItemCalculation`, `QuoteItemMaterialCalculation`, `QuoteDocumentMeta`, `QuoteSection`, `QuoteItemLayout`, `QuoteEmployeeAssignment` | 11 |
| Auftrag/Rechnung/Mahnung | `Order`, `OrderRevision`, `OrderSection`, `OrderItem`, `OrderItemCalculationSnapshot`, `OrderItemMaterialSnapshot`, `Invoice`, `InvoiceItem`, `ReminderLevel`, `Reminder`, `TaxKey`, `PaymentTerm` | 12 |
| Arbeitsvorbereitung | `WorkPreparation`, `WorkPreparationEmployee`, `WorkPreparationTask`, `WorkPreparationMaterial`, `WorkPreparationTeamAssignment`, `WorkPreparationTeamEmployee`, `WorkPreparationTeamResource`, `WorkPreparationMaterialSupplier`, `WorkPreparationDeliveryNote`, `WorkPreparationMaterialDeliveryNote` | 10 |
| Ressourcen/Teams | `Supplier`, `OperationalResource`, `Team`, `TeamEmployee`, `TeamResource` | 5 |
| Plantafel | `PlanningSlot`, `PlanningSlotCapacity`, `PlanningSettings`, `PlanningRegionSettings`, `PlanningSchoolHoliday`, `PlanningSchoolHolidaySync`, `PlanningHoliday`, `EmployeeAbsence`, `EmployeeAbsenceRequest` | 9 |
| Zeiterfassung | `TimeEntry`, `TimeEntryGroup`, `TimeEntryGroupMember`, `TimeTrackingSettings`, `EmployeePayrollSettings`, `TimeBackofficeAdvancedSettings`, `WorkTimeModel`, `WorkTimeModelValidity`, `WorkTimeBreakRule`, `EmployeeWorkTimeModel` | 10 |
| Personal | `Employee`, `EmployeeProfile`, `EmployeeFunction`, `EmployeeCompensationSettings`, `EmployeeCostAllocationSettings`, `LaborRateSettings`, `LaborRateOverheadSettings`, `EmployeeRoleSettings`, `EmployeePlanningSettings` | 9 |
| System/Einstellungen | `GeneralSettings`, `NumberSequence`, `SettingOptionGroup`, `SettingOption`, `AppUser`, `UserDashboardWidget`, `EnabledModule`, `AuditLog`, `SmtpSettings`, `DocumentEmailTemplate` | 10 |
| PDF-Layout | `DocumentLayoutBlock`, `DocumentLayoutBackground`, `DocumentTableField`, `DocumentPageMargins` | 4 |
| Aufgabenmanagement | `Task`, `TaskColumn`, `TaskChecklistItem`, `TaskSettings` | 4 |
| Wartungen & Reparaturen | `MaintenanceContract`, `MaintenanceSettings`, `ServiceReport` | 3 |

Wiederkehrendes Muster, an vielen Stellen ("migrationsarme Zusatztabelle"): eine neue Spalte
wird nicht per `ALTER TABLE` auf eine Kerntabelle aufgebracht, sondern als eigene 1:1- oder
1:n-Tabelle mit reiner FK-Spalte angehängt (Beispiele über die in CLAUDE.md Regel 6 genannten
hinaus: `QuoteDocumentMeta`, `QuoteEmployeeAssignment`, `ProjectProfile`, `CustomerProfile`,
`EmployeeProfile`, `EmployeeCompensationSettings`, `EmployeeCostAllocationSettings`,
`EmployeeRoleSettings`, `EmployeePlanningSettings`, `OrderItemCalculationSnapshot`,
`PlanningSlotCapacity`). Manche dieser Zusatztabellen haben trotzdem eine `relationship()`
(z. B. `ProjectProfile.project` mit `back_populates`), andere bewusst nicht (z. B.
`QuoteDocumentMeta`, `QuoteEmployeeAssignment` — laut Docstring explizit "migrationsarm").

Weitere Fälle von FK-Spalten **ohne** `ForeignKey()`-Constraint (reine Integer-Referenz, keine
DB-seitige referenzielle Integrität): `OrderSection.source_quote_section_id`,
`OrderItem.source_quote_item_id`, `AuditLog.actor_user_id`, `AuditLog.project_id`. Und ein Fall
von FK-Spalte **mit** Constraint, aber bewusst **ohne** Relationship wegen Selbstreferenz:
`Invoice.storno_of_invoice_id` (Docstring: "vermeidet Komplexität durch die Selbstreferenz").

---

## 3. Das Objekt-/Gebäudemodell (`Property`)

**Klasse:** `Property` (`app/models.py:371`), `__tablename__ = "properties"`.

**Spalten:** `id` (PK), `customer_id` (FK → `customers.id`, NOT NULL), `name` (String(255), NOT
NULL), `street` (String(255), nullable), `postal_code` (String(20), nullable), `city`
(String(120), nullable), `notes` (Text, nullable), `created_at` (DateTime, default `utcnow`).
Kein `__table_args__`, keine weiteren Spalten.

**Wer verweist auf `properties.id`** — per Grep über den **gesamten** `app/`-Ordner (nicht nur
`models.py`) geprüft: genau drei Stellen, alle in `app/models.py`, alle als echte
`ForeignKey("properties.id")` mit `relationship()`:

| Klasse | Spalte | Nullable | Relationship |
|---|---|---|---|
| `Inquiry` (Zeile 397) | `property_id` | ja | `property` ↔ `Property.inquiries` (back_populates, bidirektional) |
| `Project` (Zeile 425) | `property_id` | ja | `property` ↔ `Property.projects` (back_populates, bidirektional) |
| `MaintenanceContract` (Zeile 2042) | `property_id` | ja (seit 1.2.9) | `property` (unidirektional, kein back_populates) |

`Property` selbst pflegt Rückwärts-Relationships zu `Inquiry` und `Project` (`inquiries`,
`projects`), aber **nicht** zu `MaintenanceContract` — von `Property` aus ist ein zugehöriger
Wartungsvertrag nicht direkt erreichbar, nur umgekehrt über `MaintenanceContract.property`.

### Order und Invoice: nur Text-Schnappschuss, bestätigt

Wörtliches Zitat `app/models.py:714-719` (Klasse `Order`):

```python
# Snapshot der Adress-/Kundendaten zum Zeitpunkt der Beauftragung.
customer_name: Mapped[str] = mapped_column(String(255))
customer_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
customer_address: Mapped[str | None] = mapped_column(Text, nullable=True)
property_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
property_address: Mapped[str | None] = mapped_column(Text, nullable=True)
```

**`Order` hat also tatsächlich keine `property_id`-Spalte und keine FK auf `properties.id`** —
nur `property_name` (String(255)) und `property_address` (Text) als zum Zeitpunkt der
Beauftragung eingefrorene Textkopie. Damit ist die entsprechende Aussage in CLAUDE.md
(mehrfach, u. a. bei "Wartungshistorie pro Gebäude") **korrekt** und durch den Code bestätigt.

Dieselbe Struktur (`property_name`/`property_address`, ebenfalls ohne `property_id`) hat auch
`Invoice` (Zeile 873-874) — dort bisher in CLAUDE.md nicht explizit erwähnt, aber exakt
analog.

**Praktische Konsequenz** (bereits von `list_property_history()` in `app/service_reports.py`
so gelöst): um von einem `Order` zum zugehörigen `Property` zu kommen, muss man über
`order.project.property_id` gehen — es gibt keinen direkten Weg.

---

## 4. `MaintenanceContract` vollständig

**Klasse:** `app/models.py:2026`, `__tablename__ = "maintenance_contracts"`.

**Spalten:**

| Spalte | Typ | Nullable | Default/server_default |
|---|---|---|---|
| `id` | Integer, PK | – | – |
| `customer_id` | FK → `customers.id`, index | nein | – |
| `property_id` | FK → `properties.id`, index | **ja** (seit 1.2.9) | – |
| `title` | String(255) | nein | – |
| `interval_months` | Integer | nein | `12` |
| `next_due_date` | Date | nein | – |
| `last_reminder_due_date` | Date | ja | – |
| `template_project_id` | FK → `projects.id` | ja | – |
| `responsible_employee_id` | FK → `employees.id` | ja | – |
| `status` | String(30) | nein | `"aktiv"` / `server_default="aktiv"` |
| `archived` | Boolean, index | nein | `False` / `server_default="0"` (seit 1.2.10) |
| `notes` | Text | ja | – |
| `created_at` | DateTime | nein | `utcnow` |
| `updated_at` | DateTime | nein | `utcnow`, `onupdate=utcnow` |

Relationships (alle unidirektional, kein `back_populates`): `customer` (`Customer`), `property`
(`Property | None`), `template_project` (`Project | None`), `responsible_employee`
(`Employee | None`). Kein `__table_args__`.

`STATUSES = ("aktiv", "pausiert", "beendet")` — fester Tupel in `app/maintenance_contracts.py`,
kein Enum in der DB.

**Alle Funktionen in `app/maintenance_contracts.py`** (aktueller Stand, Datei komplett neu
gelesen):

| Funktion | Beschreibung |
|---|---|
| `_add_months(d, months)` | Reine Datumsarithmetik: addiert Monate, kappt den Tag korrekt auf das Monatsende (z. B. 31.1. + 1 Monat → 28./29.2.). |
| `_employee_name(e)` | `"Vorname Nachname"` oder `None`. |
| `_address(*parts)` | Verbindet nicht-leere Teile mit `", "`, sonst `None`. |
| `get_or_create_maintenance_settings(db)` | Liest/erstellt den Singleton `MaintenanceSettings` (id=1). |
| `maintenance_settings_to_dict(settings)` | Serialisiert die Einstellungen inkl. Name des Standard-Sachbearbeiters. |
| `update_maintenance_settings(db, reminder_lead_days, default_responsible_employee_id)` | Aktualisiert die Einstellungen; wirft `ValueError` bei negativer Vorlaufzeit. |
| `_is_due(contract, lead_days)` | `status=="aktiv" and next_due_date <= heute + lead_days`. |
| `contract_to_dict(contract, lead_days)` | Serialisiert einen Vertrag; bildet den Hauptadresse-Fallback nach, wenn kein `Property` gesetzt ist. |
| `_load(db, contract_id)` | Lädt einen Vertrag mit allen vier Relationships eager (`selectinload`). |
| `list_contracts(db, status=None, include_archived=False)` | Listet Verträge, filtert optional nach Status, blendet archivierte standardmäßig aus. |
| `create_contract(db, customer_id, property_id, title, interval_months, next_due_date, template_project_id=None, responsible_employee_id=None, notes=None)` | Legt einen neuen Vertrag an; wirft `ValueError` bei `interval_months < 1`. |
| `update_contract(db, contract_id, title, interval_months, next_due_date, template_project_id, responsible_employee_id, notes, property_id=None)` | Aktualisiert einen bestehenden Vertrag vollständig inkl. `property_id`. |
| `set_contract_status(db, contract_id, status)` | Setzt `aktiv`/`pausiert`/`beendet`; wirft `ValueError` bei unbekanntem Status. |
| `set_contract_archived(db, contract_id, archived)` | Archiviert/entarchiviert, unabhängig vom Status. |
| `delete_contract(db, contract_id)` | Löscht den Vertrag endgültig **und** löscht vorher alle zugehörigen Erinnerungs-Aufgaben (`Task` mit `source_module="wartungsvertrag"` und passender `source_url`). |
| `check_due_contracts_and_create_reminders(db)` | On-Demand-Lauf: erinnert per `create_task()` an jeden fälligen, aktiven, nicht archivierten Vertrag; `last_reminder_due_date` verhindert Doppel-Erinnerung; No-op, wenn Modul `aufgabenmanagement` deaktiviert ist. |
| `create_project_from_contract(db, contract_id)` | Erzeugt aus `template_project_id` per `duplicate_project()` einen neuen, normalen Vorgang; rückt `next_due_date` um `interval_months` weiter; setzt den Idempotenz-Stempel zurück. |
| `create_maintenance_contract_from_project(db, project_id, *, interval_months, next_due_date, responsible_employee_id=None)` | Rückweg (seit 1.2.12): erzeugt aus einem bestehenden Projekt per `duplicate_project(as_template=True)` einen neuen Mustervorgang und darauf einen neuen Wartungsvertrag; lehnt ab, wenn das Quellprojekt selbst schon `is_template` ist. |

---

## 5. `ServiceReport` vollständig + PDF

**Klasse:** `app/models.py:2083`, `__tablename__ = "service_reports"`.

**Spalten:** `id` (PK), `order_id` (FK → `orders.id`, NOT NULL, index), `report_type`
(String(30), NOT NULL, Kommentar `rapport|wartung`), `description` (Text, nullable),
`created_by_employee_id` (FK → `employees.id`, nullable), `performed_at` (Date, default
`date.today`), `signature_path` (String(255), nullable), `signature_name` (String(160),
nullable), `signed_at` (DateTime, nullable), `status` (String(30), default `"entwurf"` /
`server_default="entwurf"`), `created_at`, `updated_at`. Relationships (unidirektional):
`order` (`Order`), `created_by_employee` (`Employee | None`). Kein `__table_args__`.

**Statuswerte:** `REPORT_TYPES = ("rapport", "wartung")` für `report_type`;
`status` durchläuft genau zwei Werte: `"entwurf"` (Default, bearbeitbar/löschbar) →
`"unterschrieben"` (nach `sign_report()`, danach unveränderlich — gleiches Muster wie
`Invoice`/`Order`/`Reminder`).

**Alle Funktionen in `app/service_reports.py`** (Datei komplett neu gelesen):

| Funktion | Beschreibung |
|---|---|
| `_signature_directory()` | Legt `SIGNATURE_ROOT` an (`mkdir(parents=True, exist_ok=True)`) und gibt ihn zurück. |
| `signature_path(stored_filename)` | Baut den vollen Pfad `SIGNATURE_ROOT / stored_filename`. |
| `_employee_name(e)` | Wie bei MaintenanceContract. |
| `report_to_dict(report)` | Serialisiert einen Bericht inkl. Auftragsnummer, Mitarbeitername, Label. |
| `_load(db, report_id)` | Lädt einen Bericht mit `order`/`created_by_employee` eager. |
| `get_report_row(db, report_id)` | Wie `_load()`, gibt aber das ORM-Objekt zurück (für `build_service_report_pdf()`, das `report.order`/`report.signature_path` direkt braucht). |
| `list_reports(db, order_id)` | Alle Berichte zu einem Auftrag, neueste zuerst. |
| `list_property_history(db, order_id)` | Frühere, **unterschriebene** Berichte zu ANDEREN Aufträgen desselben Gebäudes; löst das Gebäude über `order.project.property_id` auf; leere Liste ohne verknüpftes Gebäude (kein Fehler). |
| `create_report(db, order_id, report_type, description=None, created_by_employee_id=None, performed_at=None)` | Legt einen neuen Entwurf an; prüft `report_type` und Auftrags-Existenz. |
| `update_report(db, report_id, report_type, description, performed_at)` | Nur solange `status != "unterschrieben"`, sonst `ValueError`. |
| `delete_report(db, report_id)` | Nur solange `status != "unterschrieben"`, sonst `ValueError`. |
| `sign_report(db, report_id, signature_png_bytes, signature_name)` | Schreibt die PNG-Bytes über `make_stored_filename()` nach `SIGNATURE_ROOT`, friert den Bericht ein (`status="unterschrieben"`), löst — nur bei aktivem Modul `aufgabenmanagement` — eine "Rechnung erstellen"-Aufgabe für `order.caseworker_employee_id` aus. |

**`app/service_report_pdf.py`** (einzige Funktion `build_service_report_pdf(db, report)`):
lehnt nicht-unterschriebene Berichte ab; baut mit `SimpleDocTemplate`/`story` (Muster wie
`invoice_pdf.py`, nicht wie `quote_layout_pdf.py`) ein PDF mit Firmenkopf, Auftrags-/Kundendaten,
Beschreibung, einer Tabelle aller Zeitbuchungen des Auftrags (`list_entries(db,
order_id=order.id)` aus `app/time_tracking.py`) und der Unterschrift als eingebettetes
`platypus.Image` (nicht `drawImage` auf rohem Canvas). Importiert `report_to_dict`,
`signature_path` aus `service_reports.py` sowie `entry_to_dict`, `list_entries` aus
`time_tracking.py` — alle auf Modulebene (unproblematisch, da `service_report_pdf.py` nicht von
diesen Modulen zurückimportiert wird, also kein Zirkelbezug).

---

## 6. `TimeEntry`

**Klasse:** `app/models.py:1541`, `__tablename__ = "time_entries"`.

**Spalten:** `id` (PK), `employee_id` (FK → `employees.id`, **NOT NULL**), `project_id` (FK →
`projects.id`, **NOT NULL**, wird immer redundant aus `order.project_id` übernommen),
`order_id` (FK → `orders.id`, **NOT NULL**), `order_item_id` (FK → `order_items.id`,
**nullable**), `work_date` (Date, NOT NULL), `entry_type` (String(40), default `"site"`),
`counts_as_productive` (Boolean, default `True`), `activity` (String(180), nullable),
`started_at`/`ended_at` (DateTime, nullable), `break_minutes` (Integer, default `0`), `hours`
(Numeric(18,4), default `0`), `notes` (Text, nullable), `source` (String(30), default
`"manual"`), `status` (String(30), default `"booked"`), `created_by_user_id` (FK →
`app_users.id`, nullable), `created_at`, `updated_at`.

**Jede Zeitbuchung hängt zwingend an einem `Order`** (`order_id` NOT NULL); eine konkrete
LV-Position (`order_item_id`) ist optional. `project_id` ist ebenfalls Pflicht, aber nur eine
Denormalisierung des Auftrags-Projekts.

**Statuswerte** (nur zwei, kein Enum): `"running"` (Timer läuft) und `"booked"` (abgeschlossen/
gebucht). Nur `status=="booked"`-Zeilen zählen in Auswertungen (`order_actual_hours()`,
`order_item_actual_hours()`, "Rechnung aus Zeitbuchungen").

**Tätigkeiten (`activity`):** technisch freier String (`String(180)`), fachlich befüllt über
die konfigurierbare Optionsgruppe **`time_entry_activities`** ("Zeiterfassung · Tätigkeiten",
`app/option_settings.py:149`). Aktuelle Default-Werte: Allgemeine Baustellenarbeiten (Default),
Baustelleneinrichtung, Abbruch/Rückbau, Dämmung, Dachdeckung, Klempnerarbeiten, Dachfenster,
Aufräumen/Baustellenordnung, **Reparatur**, **Wartung** (die letzten beiden seit der
Daten-Migration `2ba59ab6f30a`, Version 1.2.3). Ob eine Tätigkeit zwingend ist, steuert die
separate, konfigurierbare Einstellung `require_activity`. Verwandt: `entry_type` (Zeitart)
läuft über eine zweite Optionsgruppe `time_entry_types` (`site`/`travel`/`workshop`/`other`).

**Auflösung zu einem Auftrag** (`app/time_tracking.py`):
- `list_entries(db, order_id=...)` (Zeile 199) — liefert alle Rohbuchungen zu genau einem
  Auftrag, eager geladen, sortiert nach Datum/Start/ID absteigend.
- `order_actual_hours(db, order_id)` (Zeile 216) — aggregiert nur `status=="booked"`-Zeilen
  nach `counts_as_productive`/`entry_type`, liefert produktive/Fahrt-/Gesamtstunden.
- `order_item_actual_hours(db, order_id)` (Zeile 231) — dieselbe Aggregation, aber je
  `order_item_id`, für die LV-Positions-genaue Nachkalkulation.

**Nicht in CLAUDE.md erwähnt, aber vorhanden:** `TimeEntryGroup`/`TimeEntryGroupMember` für
Gruppen-Zeitbuchungen (mehrere Mitarbeiter gleichzeitig, z. B. ein ganzes Team startet
gemeinsam einen Timer) — eigene Tabellen mit denselben Fachfeldern, `TimeEntryGroupMember`
verknüpft `group_id`/`employee_id`/`time_entry_id` 1:1 je Mitglied.

---

## 7. Planungs-/Plantafel-Modul

**Kein einzelner Auftrag und keine einzelne LV-Position wird direkt verplant.** Die planbare
Einheit ist ein **`PlanningSlot`**: ein Zeitabschnitt (Start-/Enddatum) für **einen Auftrag ×
ein Team**. Laut Docstring (`app/models.py:1244`): "kann ein Auftrag damit mehrere Kolonnen und
auch mehrere getrennte Zeitblöcke je Kolonne besitzen." Ein Slot hängt über `preparation_id` an
der `WorkPreparation` (1:1 zu `Order`) und über `team_assignment_id` an der konkreten
Team-Besetzung; die Sollstunden (`PlanningSlotCapacity.planned_hours`) werden nur als
Gesamtwert auf den Zeitabschnitt verteilt, nicht auf einzelne LV-Positionen heruntergebrochen.

**Es werden primär Teams/Kolonnen geplant, nicht einzelne Mitarbeiter direkt am Slot.**
`Team` (`app/models.py:1158`) ist eine feste Stammdaten-Kolonne; `TeamEmployee` bildet eine
**viele-zu-viele-Mitgliedschaft** (`UNIQUE(team_id, employee_id)`) ohne Zeitbezug. Beim
erstmaligen Zuweisen eines Teams zu einer Arbeitsvorbereitung friert
`WorkPreparationTeamAssignment` (+ `WorkPreparationTeamEmployee`/`...TeamResource`) die
aktuelle Team-Besetzung als **Snapshot** ein — spätere Änderungen an der Team-Stammzusammen-
setzung wirken sich nicht rückwirkend auf bereits erstellte Planungen aus. Einzelmitarbeiter
sind zusätzlich direkt an einer AV zuweisbar (`WorkPreparationEmployee`, ohne Team) und haben
eine eigene Kapazitäts-/Sichtbarkeitsansicht (`EmployeePlanningSettings.show_on_planning_board`,
dritter UI-Tab "Mitarbeiter" neben "Kolonnen" und "Fahrzeuge/Maschinen").

**Business-Logik:** `app/planning.py` (Kernlogik: Kapazitätsberechnung, Feiertage/Schulferien,
Team-Snapshot, Slot-CRUD, Konflikterkennung `_conflicts()`, Planungsvorschlag
`planning_suggestion()`, Gesamtmodell `planning_board()`), `app/routers/planning.py` (dünne
API-Schicht darüber), `app/routers/resource_planning.py` (Stammdaten-CRUD für `Supplier`,
`OperationalResource`, `Team`).

**UI (`app/templates/planning.html`):** Gantt-artige Kalender-/Zeitachsen-Tabelle mit Drag &
Drop, kein Kanban-Board. Zeilen = Team/Mitarbeiter/Ressource, Spalten = Kalendertage,
`PlanningSlot`-Einsätze als farbige, absolut positionierte Balken. Backlog-Seitenleiste für
noch nicht verplante Aufträge. Details zur Touch-Tauglichkeit siehe Abschnitt 10.

---

## 8. `OPTIONAL_MODULES` (`app/modules.py`)

Vollständiger, aktueller Inhalt (`app/modules.py:16-19`):

```python
OPTIONAL_MODULES = {
    "aufgabenmanagement": "Aufgabenmanagement",
    "wartungen": "Wartungen & Reparaturen",
}
```

Genau zwei Einträge, reines `module_key → Anzeigename`-Dict, keine weiteren Metadaten (kein
Icon, keine Beschreibung, keine Abhängigkeiten, keine Sortierung).

`is_module_enabled(db, module_key)` (Zeile 22-27):
```python
def is_module_enabled(db: Session, module_key: str) -> bool:
    row = db.scalar(select(EnabledModule).where(EnabledModule.module_key == module_key))
    return row.enabled if row is not None else True
```
**Opt-out-Default, live aus der DB gelesen, kein Caching:** fehlt eine Zeile für einen
`module_key`, gilt das Modul als aktiv. Ein künftiger dritter Registry-Eintrag ist damit bei
allen Bestandsinstallationen sofort aktiv, bis ein Admin ihn bewusst abschaltet — genau wie in
CLAUDE.md beschrieben, hiermit bestätigt.

---

## 9. Datei-Upload-Pfade unter `data/`

Gemeinsamer Helper **`app/document_storage.py`**: `make_stored_filename(original_filename)` →
`f"{uuid.uuid4().hex}{suffix}"` (Original-Dateiname bleibt nur als DB-Spalte erhalten, nicht im
Dateisystem), plus `is_image_type()`/`can_preview_type()`.

| Ablage | Env-Var (Default relativ zum Projekt) | Schreiber | Ausgeliefert über |
|---|---|---|---|
| `data/project_files/<project_id>/` | `DACHKONZEPTE_PROJECT_FILE_ROOT` | `upload_project_document()` (`routers/projects.py`), zusätzlich `upload_work_preparation_delivery_note()` (Lieferscheine landen bewusst im selben Projektordner) | `GET /api/project-documents/{id}/view` (inline) und `/download` (Attachment) |
| `data/customer_files/<customer_id>/` | `DACHKONZEPTE_CUSTOMER_FILE_ROOT` | `upload_customer_document()` (`routers/customers.py`) | `GET /api/customer-documents/{id}/view` / `/download` |
| `data/company_logo/` | `DACHKONZEPTE_LOGO_FILE_ROOT` | `replace_logo()` (`app/company_logo.py`) — genau eine Datei, neuer Upload löscht die alte | `GET /api/settings/general/logo` |
| `data/document_layout_backgrounds/` | `DACHKONZEPTE_LAYOUT_BACKGROUND_ROOT` | `replace_background()` (`app/document_layout_background.py`) — eine Datei pro Dokumenttyp | `GET /api/document-layout/{type}/background/file` |
| `data/service_report_signatures/` | `DACHKONZEPTE_SIGNATURE_FILE_ROOT` | `sign_report()` (`app/service_reports.py`) — Quelle ist ein Base64-PNG aus dem Canvas, kein `UploadFile` | **Kein eigener Auslieferungs-Endpunkt** — nur indirekt als eingebettetes Bild in `build_service_report_pdf()` |

Alle Uploads außer der Signatur laufen über ein `UploadFile` mit eigenem `MAX_UPLOAD_BYTES`
(meist 50 MB, Logo 5 MB, Layout-Hintergrund 10 MB); die Signatur-Bytes selbst haben **kein**
Limit.

**Wichtiger Fund:** Es gibt **keinen zentralen** `data/`-Root. `ERP_DATA_DIR` wird nur von zwei
technischen, nicht upload-bezogenen Dateien genutzt (`app/logging_config.py`: `data/erp.log`;
`app/auth.py`: `data/.erp_secret` als JWT-Signierschlüssel-Fallback) — die fünf Upload-Ablagen
oben haben jeweils **eigene**, unabhängige Env-Vars. Siehe Empfehlungen.

Kein `StaticFiles`-Mount legt `data/` offen; jeder Zugriff läuft über einen authentifizierten
Endpunkt. Ein Datei-Import (`POST /api/imports/leistungen-dach`) landet nirgends auf Disk,
wird nur im Speicher geparst.

---

## 10. Mobile-Tauglichkeit

Alle geprüften Templates (`settings.html`, `time_tracking.html`, `service_reports.html`,
`tasks.html`, `maintenance_contracts.html`, `planning.html`, `dashboard.html`) haben ein
korrektes Viewport-Meta-Tag; `time_tracking.html` zusätzlich `viewport-fit=cover` für
Notch/Safe-Area.

**Sidebar (`_sidebar.html`):** klappt ab `max-width:1000px` sinnvoll zusammen — wird
`position:fixed` und per `transform:translateX(-100%)` komplett aus dem Bildschirm geschoben,
öffnet sich nur per Hamburger-Toggle als Overlay mit Scrim. Keine dauerhaft feste Spalte auf
schmalen Bildschirmen.

**Breakpoints je Seite** (alle reduzieren Mehrspalten-Grids auf eine Spalte, siehe Detailbericht
für exakte Zeilen): `settings.html` bei 1000px/620px/480px (bei 480px auch Label-über-Feld
statt daneben), `time_tracking.html` bei 900px/620px, `service_reports.html` bei 700px,
`tasks.html` bei 900px (Kanban-Board wird gestapelt), `maintenance_contracts.html` bei 900px
(nur Schriftverkleinerung, keine Kartenliste), `planning.html` bei 950px, `dashboard.html` bei
760px.

**Fehlend in allen sieben Inhalts-Templates:** kein `overflow-x:auto`-Wrapper um `<table>`.
Breite Tabellen werden nur durch kleinere Schrift entschärft, nicht durch einen begrenzten
Scroll-Container — im ungünstigen Fall scrollt die ganze Seite horizontal.

**Touch-Tauglichkeit im Detail:**
- **`service_reports.html`** — vorbildlich für Touch gebaut: Unterschriften-Canvas nutzt
  einheitliche Pointer-Events (`onpointerdown/move/up/cancel`, `setPointerCapture`,
  `touch-action:none`), UI-Text weist Monteure explizit an, das Gerät zum Kunden zu
  reichen.
- **`planning.html`** — das Verschieben eines Planungs-Einsatzes nutzt ausschließlich die
  native HTML5-Drag-and-Drop-API (`draggable`, `dragstart`/`dragover`/`drop`). **Das
  funktioniert auf Touch-Geräten (iOS/Android) ohne Polyfill nicht.** Es gibt einen
  Fallback: Klick/Tap öffnet einen Bearbeiten-Dialog mit Team-/Datumsfeldern, über den sich
  derselbe Effekt erreichen lässt — aber die primäre, schnelle Interaktion (Ziehen auf der
  Zeitachse) ist auf einem Tablet/Smartphone funktionslos.
- **`tasks.html`** — kein Drag & Drop vorhanden (weder Maus noch Touch); Status wird über den
  Editor-Dialog geändert, funktioniert auf Touch ohne Einschränkung.
- **Klickflächen:** Buttons durchgängig ca. 34-40px Höhe (Padding 9-11px + Schrift 13.5-14px)
  — unterhalb der von Apple/Google empfohlenen 44pt/48dp, aber praktisch noch bedienbar; keine
  eigene, größere Mobile-Variante. `dashboard.html`s Icon-Buttons sind mit ~28-30px die
  kleinsten Klickziele. `time_tracking.html`s Schnellerfassungs-Buttons sind mit die größten
  und touch-freundlichsten.

**Fazit:** Die Oberfläche ist grundsätzlich mobiltauglich (Viewport, Sidebar-Kollaps,
Grid-Umbrüche), mit zwei konkreten Lücken für den Wartungen-&-Reparaturen-Kontext (Monteur vor
Ort): fehlendes Tabellen-Scrolling und die auf Touch nicht funktionierende Drag-Interaktion der
Plantafel (die Klick-Fallback-Route funktioniert aber).

---

## 11. Abweichungen zu CLAUDE.md

1. **Älteste Migration falsch benannt.** CLAUDE.md (Einleitung) behauptet, `bb175f455b64` sei
   die älteste Alembic-Migration und "schon vor dieser Sitzung Teil des Projekts" gewesen.
   Tatsächlich gibt es **8 Migrationen davor**, angeführt von der Baseline `2befd7907eef`
   (2026-09-02 08:15, zwei Tage vor `bb175f455b64`). Die Gesamtkette hat 34 Einträge, nicht
   implizit ~26 (34 minus die 8 fehlenden). **Korrigiert unten in CLAUDE.md.**

2. **`Roadmap_Zurueckgestellte_Vorhaben.md` existiert nicht lokal.** CLAUDE.md verweist darauf
   ("falls sie lokal abgelegt wurde, lohnt sich ein Blick hinein") — per `Glob` bestätigt: die
   Datei liegt nicht im Projektverzeichnis. Kein Fehler in CLAUDE.md (der Konjunktiv war schon
   vorsichtig formuliert), aber jetzt sicher verneint statt offen.

3. **`Order`/`Invoice` haben wirklich nur `property_name`/`property_address`, keine
   `property_id`.** Das war die zentrale, im Auftrag ausdrücklich zu prüfende Frage — CLAUDE.md
   war hier bereits **korrekt** (mehrfach erwähnt, u. a. bei "Wartungshistorie pro Gebäude").
   Keine Korrektur nötig, hiermit als bestätigt vermerkt.

4. **Regel 6 (migrationsarme Zusatztabellen) nennt nur 4 Beispiele**, tatsächlich zieht sich das
   Muster durch weit mehr Tabellen (`ProjectProfile`, `CustomerProfile`, `EmployeeProfile`,
   `EmployeeCompensationSettings`, `PlanningSlotCapacity`, `OrderItemCalculationSnapshot` u. a.)
   — keine falsche Aussage, nur eine unvollständige Beispielliste. Nicht geändert (Regel bleibt
   inhaltlich korrekt, nur die Beispiele sind exemplarisch, nicht erschöpfend).

5. **`TimeEntryGroup`/`TimeEntryGroupMember` (Gruppen-Zeitbuchungen) fehlen in CLAUDE.md
   komplett.** Relevant, falls das Wartungsmodul künftig auf gemeinsame Team-Zeitbuchungen
   zugreifen soll (z. B. ein ganzes Team bucht gemeinsam Zeit auf einen Wartungsauftrag).

6. **Datei-Upload-Pfade sind nicht zentral konfigurierbar.** CLAUDE.md erwähnt bei der
   Backup-Regel (9) nur pauschal "`data/` mit Firmenlogo, hochgeladenen Projektdateien und dem
   Verschlüsselungsschlüssel" — das ist für den Zweck der Regel (alles unter `data/` mitsichern)
   ausreichend, verschweigt aber, dass es fünf weitere, unabhängige `data/`-Unterordner mit
   jeweils eigener Env-Var gibt (Kundendokumente, PDF-Layout-Hintergründe, Signaturen). Für ein
   reines Backup irrelevant (der Ordner wird ohnehin komplett kopiert), aber relevant, falls der
   Datenordner einmal verschoben werden soll.

Alle anderen im Auftrag geprüften Aussagen (Modul-Registry-Verhalten, Aufgaben-Automatisierungs-
Anschlussstelle, GoBD-Unveränderlichkeit, `Order`-Snapshot-Konzept, Wartungsvertrag/
Einsatzbericht-Domänenmodell wie in dieser Sitzung zuletzt dokumentiert) stimmen mit dem Code
überein.

---

## 12. Empfehlungen

Vorschläge, wo vor einer Erweiterung des Wartungsmoduls Umbaubedarf oder zumindest eine bewusste
Entscheidung sinnvoll ist — keine davon wurde in diesem Auftrag umgesetzt (reine Recherche):

1. **`ServiceReport` fehlt eine Verbindung zu `MaintenanceContract`.** Aktuell hängt ein Bericht
   nur am `Order`; es gibt keine Möglichkeit, direkt "alle Berichte zu Wartungsvertrag X"
   abzufragen, ohne über `Order`/`Project` zu gehen. Falls künftig eine
   Wartungsvertrags-Historie (nicht nur die bestehende Gebäude-Historie) gebraucht wird, wäre
   das eine migrationsarme Zusatztabelle oder eine zusätzliche, nullable
   `maintenance_contract_id`-Spalte auf `ServiceReport` — mit Aufräum-Pflicht beim Löschen eines
   Vertrags (Regel 6/Regel aus diesem Auftrag), analog zum bereits bestehenden
   Task-Aufräum-Fix in `delete_contract()`.

2. **`Property` hat keine Rückwärts-Relationship zu `MaintenanceContract`.** Wer "alle
   Wartungsverträge zu diesem Objekt" braucht, muss selbst `select(MaintenanceContract).where(
   property_id==...)` schreiben. Unkritisch, aber beim nächsten Ausbau (z. B. eine
   Objekt-Detailseite mit Wartungshistorie) eine Stelle, an der man daran denken muss — es gibt
   keinen `Property.maintenance_contracts`-Bequemlichkeitszugriff.

3. **Plantafel-Drag&Drop ist auf Touch-Geräten funktionslos** (Abschnitt 10). Falls die
   Wartungen-Erweiterung Monteure vor Ort stärker in Planung/Disposition einbindet (z. B.
   eigene Einsätze auf dem Tablet verschieben), müsste das entweder auf Pointer-Events
   umgestellt oder bewusst auf den bestehenden Klick-Dialog-Fallback verwiesen werden.

4. **Kein `overflow-x:auto` um Tabellen** in den geprüften Templates, auch nicht in
   `maintenance_contracts.html`. Eine künftig breitere Wartungsverträge-/Reparaturen-Tabelle
   (z. B. mit mehr Spalten) sollte diesen Wrapper von Anfang an bekommen statt es nachträglich
   zu bemerken.

5. **Fünf unabhängige `data/`-Upload-Pfade statt eines zentralen Roots** (Abschnitt 9). Falls
   ein künftiges Wartungen-Feature einen weiteren Dateityp braucht (z. B. Fotos zu einem
   Einsatzbericht, über die bereits vorhandene Unterschrift hinaus), sollte überlegt werden, ob
   ein sechster unabhängiger Env-Var-Pfad wirklich gewollt ist oder ob die Gelegenheit genutzt
   wird, sich am bestehenden `PROJECT_ROOT`/`CUSTOMER_ROOT`-Muster zu orientieren (eigener
   Unterordner unter `data/`, aber wenigstens dokumentiert an einer Stelle gesammelt).

6. **`TimeEntryGroup` (Gruppen-Zeitbuchungen) ist für die Wartungen-Abrechnung noch nicht
   berücksichtigt.** `create_invoice_from_time_entries()` (invoice_type="aufwand") gruppiert
   nach `TimeEntry.employee_id`/`activity` — falls ein ganzes Team eine Wartung gemeinsam bucht
   (`TimeEntryGroup`), sollte geprüft werden, ob dessen Mitglieder (`TimeEntryGroupMember` →
   `TimeEntry`) in dieser Abrechnung schon korrekt einzeln auftauchen oder ob das noch eine
   Lücke ist (nicht in diesem Auftrag geprüft, da außerhalb der gestellten 10 Fragen).

7. **Kein `Property`-Feld für "wie viele/welche Wartungsverträge sind hier aktiv"** auf der
   Kundenseite (`customer.html`) — falls das Wartungsmodul wächst, könnte ein Admin von der
   Kundenseite aus direkt sehen wollen, welche Objekte einen laufenden Vertrag haben, ohne extra
   auf `/maintenance-contracts` zu wechseln und zu filtern.
