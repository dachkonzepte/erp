# Anlage: Vollständiges Modell-Inventar `app/models.py`

Zugehörig zu [`bestandsaufnahme.md`](bestandsaufnahme.md), Abschnitt 2. Alle 104 Klassen aus
`app/models.py` (2361 Zeilen), in Dateireihenfolge, jeweils mit Tabellenname, allen Spalten
(Typ, nullable, default/server_default), Fremdschlüsseln, Relationships und `__table_args__`.
Reine Recherche, per Agent aus dem tatsächlichen Code gelesen (Datei:Zeile-Referenzen jeweils
der Klassenkopf).

## 1. `Catalog` — Zeile 8
`catalogs`. `id` PK; `name` String(255) NOT NULL; `description` Text nullable;
`is_import_catalog` Boolean default False, index; `archived` Boolean default False, index;
`created_at` DateTime default utcnow.
Relationships: `services` → `list[Service]` back_populates="catalog"; `calculation_settings` →
`CalculationSettings | None` back_populates="calculation_settings".

## 2. `ImportBatch` — Zeile 29
`import_batches`. `id` PK; `source_type` String(50) index; `source_name` String(255);
`source_version` String(50) nullable; `filename` String(255); `created_at` DateTime default
utcnow.
Relationships: `services` → `list[Service]` back_populates="import_batch".

## 3. `Service` — Zeile 42
`services`. `__table_args__`: UniqueConstraint(source_type, external_id).
`id` PK; `import_batch_id` FK→import_batches.id NOT NULL; `catalog_id` FK→catalogs.id
nullable, index; `service_type` String(20) nullable, index (lohnarbeit|fremdleistung|material);
`source_type` String(50) index; `external_id` String(100) index; `title_name` String(255)
nullable; `short_text` Text NOT NULL; `long_text` Text default ""; `rtf_text` Text nullable;
`image_reference` Text nullable; `quantity` Numeric(18,6) NOT NULL; `unit` String(50) NOT NULL;
`site_time_raw` Numeric(18,6) NOT NULL; `workshop_time_raw` Numeric(18,6) NOT NULL; `time_unit`
String(20) nullable; `sale_price` Numeric(18,6) NOT NULL; `activity_code` String(50) nullable.
Relationships: `import_batch` → ImportBatch; `catalog` → Catalog|None; `materials` →
list[ServiceMaterial] cascade delete-orphan; `calculation` → ServiceCalculation|None cascade
delete-orphan uselist=False; `material_overrides` → list[MaterialCalculationOverride] cascade
delete-orphan.

## 4. `MaterialGroup` — Zeile 82
`material_groups`. `id` PK; `name` String(255); `description` Text nullable;
`is_import_catalog` Boolean default False, index; `archived` Boolean default False, index;
`created_at` DateTime default utcnow.
Relationships: `materials` → list[Material] back_populates="catalog".

## 5. `Material` — Zeile 106
`materials`. `id` PK; `article_number` String(100) nullable, index; `name` Text NOT NULL; `unit`
String(50) NOT NULL; `purchase_price` Numeric(18,6) NOT NULL; `price_basis` Numeric(18,6)
default 1; `source` String(20) default "imported", index; `catalog_id` FK→material_groups.id
nullable, index; `created_at` DateTime default utcnow.
Relationships: `service_materials` → list[ServiceMaterial]; `catalog` → MaterialGroup|None.

## 6. `ServiceMaterial` — Zeile 132
`service_materials`. `id` PK; `service_id` FK→services.id NOT NULL, index; `material_id`
FK→materials.id nullable, index; `name` Text NOT NULL; `article_number` String(100) nullable,
index; `quantity` Numeric(18,6) NOT NULL; `unit` String(50) NOT NULL; `waste_raw` Numeric(18,6)
NOT NULL; `purchase_price` Numeric(18,6) NOT NULL; `price_basis` Numeric(18,6) NOT NULL.
Relationships: `material` → Material|None; `service` → Service back_populates="materials".

## 7. `CalculationSettings` — Zeile 151
`calculation_settings`. `__table_args__`: UniqueConstraint(catalog_id).
`id` PK (bewusst ohne Default); `catalog_id` FK→catalogs.id nullable; `labor_rate`
Numeric(18,6) default 82.00; `material_markup_pct` Numeric(9,4) default 0; `overhead_pct`
Numeric(9,4) default 0; `risk_profit_pct` Numeric(9,4) default 0; `use_source_time_as_minutes`
Boolean default True; `updated_at` DateTime default/onupdate utcnow.
Relationships: `catalog` → Catalog|None.

## 8. `ServiceCalculation` — Zeile 179
`service_calculations`. `__table_args__`: UniqueConstraint(service_id).
`id` PK; `service_id` FK→services.id NOT NULL, index; `site_time_minutes` Numeric(18,6)
nullable; `workshop_time_minutes` Numeric(18,6) nullable; `labor_rate_override` Numeric(18,6)
nullable; `material_markup_pct_override` Numeric(9,4) nullable; `equipment_cost` Numeric(18,6)
default 0; `subcontractor_cost` Numeric(18,6) default 0; `other_cost` Numeric(18,6) default 0;
`overhead_pct_override` Numeric(9,4) nullable; `risk_profit_pct_override` Numeric(9,4) nullable;
`manual_sale_price` Numeric(18,6) nullable; `notes` Text nullable; `updated_at` DateTime
default/onupdate utcnow.
Relationships: `service` → Service back_populates="calculation".

## 9. `MaterialCalculationOverride` — Zeile 204
`material_calculation_overrides`. `__table_args__`: UniqueConstraint(service_id,
article_number_key, material_name_key).
`id` PK; `service_id` FK→services.id NOT NULL, index; `article_number_key` String(100) default
""; `material_name_key` Text NOT NULL; `quantity_override` Numeric(18,6) nullable; `waste_pct`
Numeric(9,4) default 0; `purchase_price_override` Numeric(18,6) nullable;
`price_basis_override` Numeric(18,6) nullable; `updated_at` DateTime default/onupdate utcnow.
Relationships: `service` → Service back_populates="material_overrides".

## 10. `Customer` — Zeile 229
`customers`. `id` PK; `name` String(255) index; `contact_person` String(255) nullable; `street`
String(255) nullable; `postal_code` String(20) nullable; `city` String(120) nullable; `email`
String(255) nullable; `phone` String(80) nullable; `notes` Text nullable; `created_at` DateTime
default utcnow.
Relationships: `profile` → CustomerProfile|None cascade delete-orphan uselist=False;
`properties` → list[Property] cascade delete-orphan; `projects` → list[Project]; `inquiries` →
list[Inquiry]; `extra_infos` → list[CustomerExtraInfo] cascade delete-orphan order_by=id;
`documents` → list[CustomerDocument] cascade delete-orphan order_by=uploaded_at desc.
Python-`@property` (keine DB-Spalten): `customer_number`, `category`,
`default_payment_term_id` — alle aus `self.profile` abgeleitet.

## 11. `CustomerProfile` — Zeile 270
`customer_profiles`. `__table_args__`: UniqueConstraint(customer_id); UniqueConstraint(
customer_number).
`id` PK; `customer_id` FK→customers.id NOT NULL, index; `customer_number` String(50) index;
`category` String(80) default "Privatkunde", index; `default_payment_term_id`
FK→payment_terms.id nullable; `created_at`/`updated_at` DateTime.
Relationships: `customer` → Customer back_populates="profile"; `default_payment_term` →
PaymentTerm|None (unidirektional).

## 12. `TaxKey` — Zeile 291
`tax_keys`. `id` PK; `label` String(120); `vat_rate` Numeric(9,4) default 19.00; `notice_text`
Text nullable; `is_default` Boolean default False, index; `archived` Boolean default False,
index; `sort_order` Integer default 10; `created_at` DateTime default utcnow.
Keine Relationships (Quote/Order/Invoice referenzieren per FK zurück, TaxKey selbst nicht).

## 13. `PaymentTerm` — Zeile 319
`payment_terms`. `id` PK; `label` String(120); `days` Integer default 14; `skonto_percent`
Numeric(5,2) nullable; `skonto_days` Integer nullable; `text_template` Text nullable;
`is_default` Boolean default False, index; `archived` Boolean default False, index;
`sort_order` Integer default 10; `created_at` DateTime default utcnow.
Keine Relationships (nur unidirektional von CustomerProfile referenziert).

## 14. `CustomerExtraInfo` — Zeile 356
`customer_extra_infos`. `id` PK; `customer_id` FK→customers.id NOT NULL, index; `info_type`
String(30) index; `label` String(120) nullable; `value` Text NOT NULL; `created_at` DateTime
default utcnow.
Relationships: `customer` → Customer back_populates="extra_infos".

## 15. `Property` — Zeile 371
`properties`. `id` PK; `customer_id` FK→customers.id NOT NULL, index; `name` String(255) NOT
NULL; `street` String(255) nullable; `postal_code` String(20) nullable; `city` String(120)
nullable; `notes` Text nullable; `created_at` DateTime default utcnow. Kein `__table_args__`.
Relationships: `customer` → Customer back_populates="properties"; `projects` → list[Project]
back_populates="property"; `inquiries` → list[Inquiry] back_populates="property".

## 16. `Inquiry` — Zeile 388
`inquiries`. `__table_args__`: UniqueConstraint(inquiry_number).
`id` PK; `inquiry_number` String(50) index; `customer_id` FK→customers.id NOT NULL, index;
`property_id` FK→properties.id nullable, index; `project_id` FK→projects.id nullable, index,
**unique=True**; `title` String(255); `description` Text nullable; `status` String(50) default
"neu", index; `priority` String(30) default "normal", index; `source` String(80) default
"sonstiges", index; `contact_person` String(255) nullable; `assigned_to` String(255) nullable;
`visit_at` DateTime nullable, index; `follow_up_at` DateTime nullable, index; `lost_reason`
Text nullable; `created_at`/`updated_at` DateTime.
Relationships: `customer` → Customer back_populates="inquiries"; `property` → Property|None
back_populates="inquiries"; `project` → Project|None back_populates="source_inquiry"
foreign_keys=[project_id].

## 17. `Project` — Zeile 418
`projects`. `__table_args__`: UniqueConstraint(project_number).
`id` PK; `project_number` String(50) index; `customer_id` FK→customers.id NOT NULL, index;
`property_id` FK→properties.id nullable, index; `name` String(255); `status` String(50) default
"anfrage", index; `description` Text nullable; `is_template` Boolean default False
server_default="0", index (seit 1.0.92); `archived` Boolean default False server_default="0",
index (seit 1.0.94); `created_at` DateTime default utcnow.
Relationships: `customer` → Customer back_populates="projects"; `property` → Property|None
back_populates="projects"; `quotes` → list[Quote] cascade delete-orphan; `orders` →
list[Order] cascade delete-orphan order_by=Order.id; `source_inquiry` → Inquiry|None
back_populates="source_inquiry" foreign_keys="Inquiry.project_id" uselist=False; `documents` →
list[ProjectDocument] cascade delete-orphan order_by=uploaded_at desc; `profile` →
ProjectProfile|None back_populates="profile" uselist=False cascade delete-orphan.

## 18. `ProjectProfile` — Zeile 454
`project_profiles`. `__table_args__`: UniqueConstraint(project_id).
`id` PK; `project_id` FK→projects.id NOT NULL, index; `category` String(100) nullable, index;
`created_at`/`updated_at` DateTime.
Relationships: `project` → Project back_populates="profile".

## 19. `ProjectDocument` — Zeile 469
`project_documents`. `id` PK; `project_id` FK→projects.id NOT NULL, index; `category`
String(100) default "Sonstiges", index; `subfolder` String(150) nullable, index;
`original_filename` String(255) NOT NULL; `stored_filename` String(255) unique=True;
`content_type` String(150) nullable; `file_size` Integer default 0; `description` Text
nullable; `document_date` Date nullable; `uploaded_at` DateTime default utcnow, index.
Relationships: `project` → Project back_populates="documents".

## 20. `CustomerDocument` — Zeile 499
`customer_documents`. Identisch strukturiert zu ProjectDocument, nur `customer_id`
FK→customers.id NOT NULL, index statt project_id.
Relationships: `customer` → Customer back_populates="documents".

## 21. `Quote` — Zeile 530
`quotes`. `__table_args__`: UniqueConstraint(quote_number).
`id` PK; `quote_number` String(50) index; `project_id` FK→projects.id NOT NULL, index; `title`
String(255); `status` String(50) default "entwurf", index; `vat_rate` Numeric(9,4) default
19.00; `tax_key_id` FK→tax_keys.id (Name `fk_quotes_tax_key_id`) nullable, index; `intro_text`/
`outro_text`/`outro_text_2` Text nullable; `source_format` String(50) default "manual";
`gaeb_exchange_phase` String(20) nullable; `email_sent_at` DateTime nullable; `email_sent_to`
String(255) nullable; `created_at`/`updated_at` DateTime.
Relationships: `project` → Project back_populates="quotes"; `items` → list[QuoteItem] cascade
delete-orphan order_by=sort_order.

## 22. `QuoteItem` — Zeile 565
`quote_items`. `id` PK; `quote_id` FK→quotes.id NOT NULL, index; `source_service_id`
FK→services.id nullable, index; `sort_order` Integer default 10; `position_number` String(50);
`gaeb_oz` String(100) nullable; `position_type` String(30) default "normal";
`source_external_id` String(100) nullable; `short_text` Text NOT NULL; `long_text` Text default
""; `quantity` Numeric(18,6) default 1; `unit` String(50); `unit_price` Numeric(18,6) default 0;
`source_unit_price` Numeric(18,6) nullable; `created_at` DateTime default utcnow.
Relationships: `quote` → Quote back_populates="items"; `source_service` → Service|None
(unidirektional); `project_calculation` → QuoteItemCalculation|None cascade delete-orphan
uselist=False.

## 23. `QuoteItemCalculation` — Zeile 592
`quote_item_calculations`. `__table_args__`: UniqueConstraint(quote_item_id).
`id` PK; `quote_item_id` FK→quote_items.id NOT NULL, index; `site_time_minutes`/
`workshop_time_minutes` Numeric(18,6) default 0; `labor_rate` Numeric(18,6) default 0;
`material_markup_pct` Numeric(9,4) default 0; `equipment_cost`/`subcontractor_cost`/
`other_cost` Numeric(18,6) default 0; `overhead_pct`/`risk_profit_pct` Numeric(9,4) default 0;
`manual_sale_price` Numeric(18,6) nullable; `notes` Text nullable; `created_at`/`updated_at`
DateTime.
Relationships: `quote_item` → QuoteItem back_populates="project_calculation"; `materials` →
list[QuoteItemMaterialCalculation] cascade delete-orphan order_by=id.

## 24. `QuoteItemMaterialCalculation` — Zeile 624
`quote_item_material_calculations`. `id` PK; `calculation_id`
FK→quote_item_calculations.id NOT NULL, index; `source_material_id` FK→service_materials.id
nullable; `name` Text NOT NULL; `article_number` String(100) nullable, index; `unit`
String(50); `source_quantity`/`quantity` Numeric(18,6) default 0; `waste_pct` Numeric(9,4)
default 0; `source_purchase_price`/`purchase_price` Numeric(18,6) default 0; `price_basis`
Numeric(18,6) default 1.
Relationships: `calculation` → QuoteItemCalculation back_populates="materials".

## 25. `QuoteDocumentMeta` — Zeile 643
`quote_document_meta`. `__table_args__`: UniqueConstraint(quote_id).
`id` PK; `quote_id` FK→quotes.id NOT NULL, index; `quote_date` Date default today;
`valid_until` Date nullable; `contact_person` String(255) nullable; `payment_terms` Text
nullable; `execution_period` String(255) nullable; `internal_note` Text nullable;
`updated_at` DateTime.
Keine Relationships (migrationsarmes Muster, nur FK-Spalte).

## 26. `QuoteSection` — Zeile 660
`quote_sections`. `id` PK; `quote_id` FK→quotes.id NOT NULL, index; `parent_id`
FK→quote_sections.id (Selbstreferenz) nullable, index; `title` String(255); `description` Text
nullable; `sort_order` Integer default 10; `section_number` String(50) nullable;
`created_at`/`updated_at` DateTime.
Keine Relationships.

## 27. `QuoteItemLayout` — Zeile 676
`quote_item_layouts`. `__table_args__`: UniqueConstraint(quote_item_id).
`id` PK; `quote_item_id` FK→quote_items.id NOT NULL, index; `section_id`
FK→quote_sections.id nullable, index; `sort_order` Integer default 10; `include_in_total`
Boolean default True; `updated_at` DateTime.
Keine Relationships.

## 28. `Order` — Zeile 690
`orders`. `__table_args__`: UniqueConstraint(order_number); UniqueConstraint(source_quote_id).
`id` PK; `order_number` String(50) index; `project_id` FK→projects.id NOT NULL, index;
`source_quote_id` FK→quotes.id NOT NULL, index; `quote_number_snapshot` String(50); `title`
String(255); `status` String(50) default "beauftragt", index; `vat_rate` Numeric(9,4) default
19.00; `tax_key_id` FK→tax_keys.id (Name `fk_orders_tax_key_id`) nullable, index; `intro_text`/
`outro_text`/`outro_text_2` Text nullable.
**Kein `property_id`.** Statt dessen (Snapshot-Kommentar im Code): `customer_name`
String(255) NOT NULL; `customer_number` String(50) nullable; `customer_address` Text nullable;
`property_name` String(255) nullable; `property_address` Text nullable.
Weiter: `order_date` Date default today; `execution_start`/`execution_end` Date nullable;
`payment_terms` Text nullable; `remarks` Text nullable; `caseworker_employee_id`
FK→employees.id nullable, index; `project_manager_employee_id` FK→employees.id nullable,
index; `email_sent_at` DateTime nullable; `email_sent_to` String(255) nullable;
`created_at`/`updated_at` DateTime.
Relationships: `project` → Project back_populates="orders"; `source_quote` → Quote
(unidirektional); `sections` → list[OrderSection] cascade delete-orphan order_by=sort_order;
`items` → list[OrderItem] cascade delete-orphan order_by=sort_order; `revisions` →
list[OrderRevision] cascade delete-orphan order_by=revision_number; `invoices` →
list[Invoice] cascade delete-orphan; `caseworker` → Employee|None foreign_keys=[
caseworker_employee_id]; `project_manager` → Employee|None foreign_keys=[
project_manager_employee_id].

## 29. `OrderRevision` — Zeile 744
`order_revisions`. `__table_args__`: UniqueConstraint(order_id, revision_number).
`id` PK; `order_id` FK→orders.id NOT NULL, index; `revision_number` Integer default 1;
`reason` String(255) default "Auftragsstand gesichert"; `source` String(50) default "manual";
`snapshot_json` Text NOT NULL; `created_by_name` String(160) default "System"; `created_at`
DateTime default utcnow, index.
Relationships: `order` → Order back_populates="revisions".

## 30. `OrderSection` — Zeile 764
`order_sections`. `id` PK; `order_id` FK→orders.id NOT NULL, index; `parent_id`
FK→order_sections.id (Selbstreferenz) nullable, index; `source_quote_section_id`
**keine ForeignKey** (nur mapped_column nullable, index); `title` String(255); `description`
Text nullable; `sort_order` Integer default 10; `section_number` String(50) nullable.
Relationships: `order` → Order back_populates="sections".

## 31. `OrderItem` — Zeile 779
`order_items`. `id` PK; `order_id` FK→orders.id NOT NULL, index; `section_id`
FK→order_sections.id nullable, index; `source_quote_item_id` **keine ForeignKey** (nur
mapped_column nullable, index); `sort_order` Integer default 10; `position_number` String(50);
`gaeb_oz` String(100) nullable; `position_type` String(30) default "normal";
`source_external_id` String(100) nullable; `short_text` Text NOT NULL; `long_text` Text default
""; `quantity` Numeric(18,6) default 1; `unit` String(50); `unit_price` Numeric(18,6) default
0; `include_in_total` Boolean default True.
Relationships: `order` → Order back_populates="items"; `calculation_snapshot` →
OrderItemCalculationSnapshot|None cascade delete-orphan uselist=False.

## 32. `OrderItemCalculationSnapshot` — Zeile 802
`order_item_calculation_snapshots`. `__table_args__`: UniqueConstraint(order_item_id).
`id` PK; `order_item_id` FK→order_items.id NOT NULL, index; `site_time_minutes`/
`workshop_time_minutes` Numeric(18,6) default 0; `labor_rate` Numeric(18,6) default 0;
`material_markup_pct` Numeric(9,4) default 0; `equipment_cost`/`subcontractor_cost`/
`other_cost` Numeric(18,6) default 0; `overhead_pct`/`risk_profit_pct` Numeric(9,4) default 0;
`effective_sale_price` Numeric(18,6) default 0.
Relationships: `order_item` → OrderItem back_populates="calculation_snapshot"; `materials` →
list[OrderItemMaterialSnapshot] cascade delete-orphan order_by=id.

## 33. `OrderItemMaterialSnapshot` — Zeile 824
`order_item_material_snapshots`. `id` PK; `calculation_id`
FK→order_item_calculation_snapshots.id NOT NULL, index; `article_number` String(100) nullable,
index; `name` Text NOT NULL; `unit` String(50); `quantity` Numeric(18,6) default 0;
`waste_pct` Numeric(9,4) default 0; `purchase_price` Numeric(18,6) default 0; `price_basis`
Numeric(18,6) default 1.
Relationships: `calculation` → OrderItemCalculationSnapshot back_populates="materials".

## 34. `Invoice` — Zeile 840
`invoices`. Kein `__table_args__`.
`id` PK; `invoice_number` String(50) nullable, index; `order_id` FK→orders.id NOT NULL, index;
`invoice_type` String(30) NOT NULL, index (abschlag_pauschal|abschlag_leistungsstand|schluss|
storno); `status` String(20) default "entwurf", index (entwurf|versendet|bezahlt|storniert);
`invoice_date` Date default today; `due_date`/`paid_date` Date nullable;
`storno_of_invoice_id` FK→invoices.id (Selbstreferenz) nullable, index — bewusst ohne
Relationship (Komplexität der Selbstreferenz); `customer_name` String(255) NOT NULL;
`customer_number` String(50) nullable; `customer_address` Text nullable; `property_name`
String(255) nullable; `property_address` Text nullable — **auch hier kein `property_id`**;
`vat_rate` Numeric(9,4) default 19.00; `tax_key_id` FK→tax_keys.id (Name
`fk_invoices_tax_key_id`) nullable, index; `tax_notice_text` Text nullable; `lump_sum_net`
Numeric(18,6) nullable; `progress_description` Text nullable; `intro_text`/`outro_text`/
`outro_text_2` Text nullable; `payment_terms` Text nullable; `skonto_percent` Numeric(5,2)
nullable; `skonto_days` Integer nullable; `payment_terms_text_template` Text nullable;
`caseworker_employee_id` FK→employees.id nullable, index; `email_sent_at` DateTime nullable;
`email_sent_to` String(255) nullable; `created_at`/`updated_at` DateTime.
Relationships: `order` → Order back_populates="invoices"; `items` → list[InvoiceItem] cascade
delete-orphan order_by=sort_order; `reminders` → list[Reminder] cascade delete-orphan
order_by=level.

## 35. `InvoiceItem` — Zeile 917
`invoice_items`. `id` PK; `invoice_id` FK→invoices.id NOT NULL, index; `source_order_item_id`
FK→order_items.id nullable, index; `sort_order` Integer default 10; `position_number`
String(50); `gaeb_oz` String(100) nullable; `short_text` Text NOT NULL; `long_text` Text
default ""; `unit` String(50); `unit_price` Numeric(18,6) default 0; `soll_quantity`
Numeric(18,6) nullable; `ist_quantity`/`billed_quantity`/`billed_total` Numeric(18,6) default 0.
Relationships: `invoice` → Invoice back_populates="items".

## 36. `ReminderLevel` — Zeile 958
`reminder_levels`. `id` PK; `level` Integer index (1/2/3); `label` String(120);
`days_after_previous_step` Integer default 7; `fee_amount` Numeric(18,6) default 0;
`text_template` Text nullable; `email_subject_template` String(255) nullable;
`email_body_template` Text nullable; `active` Boolean default True, index; `sort_order`
Integer default 10; `created_at` DateTime default utcnow.
Keine Relationships.

## 37. `Reminder` — Zeile 999
`reminders`. `id` PK; `reminder_number` String(50) nullable, index; `invoice_id`
FK→invoices.id NOT NULL, index; `level` Integer index; `status` String(20) default "entwurf",
index; `reminder_date` Date default today; `new_due_date` Date nullable;
`outstanding_amount`/`fee_amount` Numeric(18,6) default 0; `text` Text nullable;
`email_sent_at` DateTime nullable; `email_sent_to` String(255) nullable; `created_at`/
`updated_at` DateTime.
Relationships: `invoice` → Invoice back_populates="reminders".

## 38. `WorkPreparation` — Zeile 1043
`work_preparations`. `__table_args__`: UniqueConstraint(order_id).
`id` PK; `order_id` FK→orders.id NOT NULL, index; `status` String(50) default "offen", index;
`planned_start`/`planned_end` Date nullable; `site_notes`/`material_notes` Text nullable;
`created_at`/`updated_at` DateTime.
Relationships: `order` → Order (unidirektional); `employees` → list[WorkPreparationEmployee]
cascade delete-orphan order_by=id; `tasks` → list[WorkPreparationTask] cascade delete-orphan
order_by=sort_order; `materials` → list[WorkPreparationMaterial] cascade delete-orphan
order_by=id.

## 39. `WorkPreparationEmployee` — Zeile 1064
`work_preparation_employees`. `__table_args__`: UniqueConstraint(preparation_id, employee_id).
`id` PK; `preparation_id` FK→work_preparations.id NOT NULL, index; `employee_id`
FK→employees.id NOT NULL, index; `role` String(120) nullable; `planned_hours` Numeric(18,4)
nullable; `notes` Text nullable.
Relationships: `preparation` → WorkPreparation back_populates="employees"; `employee` →
Employee (unidirektional).

## 40. `WorkPreparationTask` — Zeile 1079
`work_preparation_tasks`. `id` PK; `preparation_id` FK→work_preparations.id NOT NULL, index;
`title` String(255); `status` String(40) default "offen", index; `priority` String(30) default
"normal"; `due_date` Date nullable; `assigned_employee_id` FK→employees.id nullable, index;
`notes` Text nullable; `sort_order` Integer default 100; `created_at`/`updated_at` DateTime.
Relationships: `preparation` → WorkPreparation back_populates="tasks"; `assigned_employee` →
Employee|None (unidirektional).

## 41. `WorkPreparationMaterial` — Zeile 1098
`work_preparation_materials`. `id` PK; `preparation_id` FK→work_preparations.id NOT NULL,
index; `source_material_snapshot_id` FK→order_item_material_snapshots.id nullable, index;
`source_order_item_id` FK→order_items.id nullable, index; `article_number` String(100)
nullable, index; `name` Text NOT NULL; `unit` String(50); `calculated_quantity`/
`planned_quantity` Numeric(18,6) default 0; `status` String(40) default "bedarf", index;
`supplier` String(255) nullable; `notes` Text nullable.
Relationships: `preparation` → WorkPreparation back_populates="materials".

## 42. `Supplier` — Zeile 1117
`suppliers`. `__table_args__`: UniqueConstraint(supplier_number).
`id` PK; `supplier_number` String(50) nullable, index; `name` String(255) index;
`contact_person` String(255) nullable; `street` String(255) nullable; `postal_code`
String(20) nullable; `city` String(120) nullable; `country` String(120) default
"Deutschland"; `phone` String(80) nullable; `email` String(255) nullable; `website`
String(255) nullable; `customer_number_at_supplier` String(100) nullable; `notes` Text
nullable; `active` Boolean default True, index; `created_at`/`updated_at` DateTime.
Keine Relationships (unidirektional referenziert).

## 43. `OperationalResource` — Zeile 1140
`operational_resources`. `__table_args__`: UniqueConstraint(resource_number).
`id` PK; `resource_number` String(50) nullable, index; `resource_type` String(50) default
"Maschine", index; `name` String(255) index; `manufacturer`/`model` String(120) nullable;
`identifier` String(120) nullable, index; `notes` Text nullable; `active` Boolean default
True, index; `created_at`/`updated_at` DateTime.
Keine Relationships.

## 44. `Team` — Zeile 1158
`teams`. `__table_args__`: UniqueConstraint(team_number).
`id` PK; `team_number` String(50) nullable, index; `name` String(160) index; `description`
Text nullable; `active` Boolean default True, index; `created_at`/`updated_at` DateTime.
Relationships: `employees` → list[TeamEmployee] cascade delete-orphan order_by=id; `resources`
→ list[TeamResource] cascade delete-orphan order_by=id.

## 45. `TeamEmployee` — Zeile 1175
`team_employees`. `__table_args__`: UniqueConstraint(team_id, employee_id).
`id` PK; `team_id` FK→teams.id NOT NULL, index; `employee_id` FK→employees.id NOT NULL, index;
`role` String(120) nullable.
Relationships: `team` → Team back_populates="employees"; `employee` → Employee
(unidirektional).

## 46. `TeamResource` — Zeile 1188
`team_resources`. `__table_args__`: UniqueConstraint(team_id, resource_id).
`id` PK; `team_id` FK→teams.id NOT NULL, index; `resource_id` FK→operational_resources.id NOT
NULL, index; `role` String(120) nullable.
Relationships: `team` → Team back_populates="resources"; `resource` → OperationalResource
(unidirektional).

## 47. `WorkPreparationTeamAssignment` — Zeile 1201
`work_preparation_team_assignments`. `__table_args__`: UniqueConstraint(preparation_id,
team_id).
`id` PK; `preparation_id` FK→work_preparations.id NOT NULL, index; `team_id` FK→teams.id NOT
NULL, index; `team_name_snapshot` String(160) NOT NULL; `notes` Text nullable; `created_at`
DateTime default utcnow.
Relationships: `team` → Team (unidirektional); `employees` → list[WorkPreparationTeamEmployee]
cascade delete-orphan order_by=id; `resources` → list[WorkPreparationTeamResource] cascade
delete-orphan order_by=id.

## 48. `WorkPreparationTeamEmployee` — Zeile 1218
`work_preparation_team_employees`. `__table_args__`: UniqueConstraint(assignment_id,
employee_id).
`id` PK; `assignment_id` FK→work_preparation_team_assignments.id NOT NULL, index;
`employee_id` FK→employees.id NOT NULL, index; `employee_name_snapshot` String(255) NOT NULL;
`role_snapshot` String(120) nullable.
Relationships: `employee` → Employee (unidirektional).

## 49. `WorkPreparationTeamResource` — Zeile 1230
`work_preparation_team_resources`. `__table_args__`: UniqueConstraint(assignment_id,
resource_id).
`id` PK; `assignment_id` FK→work_preparation_team_assignments.id NOT NULL, index;
`resource_id` FK→operational_resources.id NOT NULL, index; `resource_name_snapshot`
String(255) NOT NULL; `resource_type_snapshot` String(50) NOT NULL; `role_snapshot`
String(120) nullable.
Relationships: `resource` → OperationalResource (unidirektional).

## 50. `PlanningSlot` — Zeile 1243
`planning_slots`. `id` PK; `preparation_id` FK→work_preparations.id NOT NULL, index;
`team_assignment_id` FK→work_preparation_team_assignments.id NOT NULL, index; `start_date`/
`end_date` Date NOT NULL, index; `status` String(40) default "geplant", index; `notes` Text
nullable; `created_at`/`updated_at` DateTime.
Relationships: `preparation` → WorkPreparation (unidirektional); `team_assignment` →
WorkPreparationTeamAssignment (unidirektional); `capacity` → PlanningSlotCapacity|None cascade
delete-orphan uselist=False.

## 51. `PlanningSettings` — Zeile 1267 (Singleton, id default 1)
`planning_settings`. `daily_work_hours` Numeric(9,4) default 8.00;
`default_travel_hours_per_employee_day` Numeric(9,4) default 0.00; `monday`…`friday` Boolean
default True; `saturday`/`sunday` Boolean default False; `updated_at` DateTime.
Keine Relationships.

## 52. `PlanningRegionSettings` — Zeile 1286 (Singleton, id default 1)
`planning_region_settings`. `federal_state_code` String(2) default "NW";
`auto_public_holidays` Boolean default True; `show_school_holidays` Boolean default True;
`updated_at` DateTime.
Keine Relationships.

## 53. `PlanningSchoolHoliday` — Zeile 1297
`planning_school_holidays`. `__table_args__`: UniqueConstraint(state_code, calendar_year,
name, start_date, end_date).
`id` PK; `state_code` String(2) index; `calendar_year` Integer index; `name` String(120);
`start_date`/`end_date` Date index; `source` String(80) default "ferien-api.de"; `updated_at`
DateTime.
Keine Relationships.

## 54. `PlanningSchoolHolidaySync` — Zeile 1314
`planning_school_holiday_sync`. `__table_args__`: UniqueConstraint(state_code, calendar_year).
`id` PK; `state_code` String(2) index; `calendar_year` Integer index; `success` Boolean
default False; `error_message` Text nullable; `synced_at` DateTime default utcnow.
Keine Relationships.

## 55. `PlanningHoliday` — Zeile 1327
`planning_holidays`. `__table_args__`: UniqueConstraint(holiday_date).
`id` PK; `holiday_date` Date index; `name` String(180); `active` Boolean default True, index;
`created_at`/`updated_at` DateTime.
Keine Relationships.

## 56. `EmployeeAbsence` — Zeile 1340
`employee_absences`. `id` PK; `employee_id` FK→employees.id NOT NULL, index; `absence_type`
String(80) default "Urlaub", index; `start_date`/`end_date` Date NOT NULL, index; `notes` Text
nullable; `created_at`/`updated_at` DateTime.
Relationships: `employee` → Employee (unidirektional).

## 57. `EmployeeAbsenceRequest` — Zeile 1356
`employee_absence_requests`. `id` PK; `employee_id` FK→employees.id NOT NULL, index;
`absence_type` String(80) default "Urlaub", index; `start_date`/`end_date` Date NOT NULL,
index; `notes` Text nullable; `status` String(30) default "pending", index;
`requested_by_user_id`/`reviewed_by_user_id` FK→app_users.id nullable, index; `reviewed_at`
DateTime nullable; `review_notes` Text nullable; `approved_absence_id`
FK→employee_absences.id nullable, index; `created_at`/`updated_at` DateTime.
Relationships: `employee` → Employee foreign_keys=[employee_id]; `approved_absence` →
EmployeeAbsence|None foreign_keys=[approved_absence_id].

## 58. `PlanningSlotCapacity` — Zeile 1383
`planning_slot_capacity`. `__table_args__`: UniqueConstraint(slot_id).
`id` PK; `slot_id` FK→planning_slots.id NOT NULL, index; `planned_hours` Numeric(18,2) default
0.00; `travel_hours_per_employee_day` Numeric(9,4) nullable; `updated_at` DateTime.
Relationships: `slot` → PlanningSlot back_populates="capacity".

## 59. `WorkPreparationMaterialSupplier` — Zeile 1397
`work_preparation_material_suppliers`. `__table_args__`: UniqueConstraint(material_id).
`id` PK; `material_id` FK→work_preparation_materials.id NOT NULL, index; `supplier_id`
FK→suppliers.id NOT NULL, index.
Relationships: `supplier` → Supplier (unidirektional).

## 60. `WorkPreparationDeliveryNote` — Zeile 1408
`work_preparation_delivery_notes`. `__table_args__`: UniqueConstraint(project_document_id).
`id` PK; `preparation_id` FK→work_preparations.id NOT NULL, index; `project_document_id`
FK→project_documents.id NOT NULL, index; `supplier_id` FK→suppliers.id nullable, index;
`delivery_note_number` String(120) nullable, index; `document_date` Date nullable; `notes`
Text nullable; `created_at` DateTime default utcnow.
Relationships: `document` → ProjectDocument (unidirektional); `supplier` → Supplier|None
(unidirektional).

## 61. `WorkPreparationMaterialDeliveryNote` — Zeile 1426
`work_preparation_material_delivery_notes`. `__table_args__`: UniqueConstraint(material_id,
delivery_note_id).
`id` PK; `material_id` FK→work_preparation_materials.id NOT NULL, index; `delivery_note_id`
FK→work_preparation_delivery_notes.id NOT NULL, index.
Relationships: `delivery_note` → WorkPreparationDeliveryNote (unidirektional).

## 62. `TimeTrackingSettings` — Zeile 1439 (Singleton, id default 1)
`time_tracking_settings`. `rounding_minutes` Integer default 0; `default_break_minutes`
Integer default 0; `allow_manual_entries`/`allow_group_bookings` Boolean default True;
`require_order_item`/`require_activity` Boolean default False; `datev_target` String(30)
default "lohn_gehalt"; `datev_wage_type_site`/`_travel`/`_workshop`/`_other` String(30)
nullable; `updated_at` DateTime.
Keine Relationships.

## 63. `EmployeePayrollSettings` — Zeile 1458
`employee_payroll_settings`. `__table_args__`: UniqueConstraint(employee_id).
`id` PK; `employee_id` FK→employees.id NOT NULL, index; `datev_personnel_number` String(30)
nullable, index; `payroll_export_enabled` Boolean default True, index; `updated_at` DateTime.
Keine Relationships.

## 64. `TimeBackofficeAdvancedSettings` — Zeile 1470 (Singleton, id default 1)
`time_backoffice_advanced_settings`. `datev_personnel_equals_erp_number` Boolean default
False; `default_work_time_model_id` FK→work_time_models.id nullable; `updated_at` DateTime.
Keine Relationships.

## 65. `WorkTimeModel` — Zeile 1480
`work_time_models`. `__table_args__`: UniqueConstraint(name).
`id` PK; `name` String(120) index; `code` String(50) nullable, index; `daily_target_hours`
Numeric(9,4) default 8.00; `description` Text nullable; `active` Boolean default True, index;
`sort_order` Integer default 100; `created_at`/`updated_at` DateTime.
Relationships: `break_rules` → list[WorkTimeBreakRule] cascade delete-orphan
order_by=threshold_hours.

## 66. `WorkTimeModelValidity` — Zeile 1500
`work_time_model_validities`. `__table_args__`: UniqueConstraint(model_id).
`id` PK; `model_id` FK→work_time_models.id NOT NULL, index; `valid_from_week` Integer default
1; `valid_to_week` Integer default 53; `updated_at` DateTime.
Keine Relationships.

## 67. `WorkTimeBreakRule` — Zeile 1515
`work_time_break_rules`. `__table_args__`: UniqueConstraint(model_id, threshold_hours).
`id` PK; `model_id` FK→work_time_models.id NOT NULL, index; `threshold_hours` Numeric(9,4) NOT
NULL; `break_minutes` Integer default 0; `sort_order` Integer default 100.
Relationships: `model` → WorkTimeModel back_populates="break_rules".

## 68. `EmployeeWorkTimeModel` — Zeile 1528
`employee_work_time_models`. `__table_args__`: UniqueConstraint(employee_id).
`id` PK; `employee_id` FK→employees.id NOT NULL, index; `model_id` FK→work_time_models.id NOT
NULL, index; `updated_at` DateTime.
Relationships: `model` → WorkTimeModel (unidirektional).

## 69. `TimeEntry` — Zeile 1541
`time_entries`. Kein `__table_args__`. Siehe Hauptbericht Abschnitt 6 für volle Beschreibung.
`id` PK; `employee_id` FK→employees.id NOT NULL, index; `project_id` FK→projects.id NOT NULL,
index; `order_id` FK→orders.id NOT NULL, index; `order_item_id` FK→order_items.id nullable,
index; `work_date` Date NOT NULL, index; `entry_type` String(40) default "site", index;
`counts_as_productive` Boolean default True, index; `activity` String(180) nullable;
`started_at` DateTime nullable, index; `ended_at` DateTime nullable; `break_minutes` Integer
default 0; `hours` Numeric(18,4) default 0; `notes` Text nullable; `source` String(30) default
"manual", index; `status` String(30) default "booked", index; `created_by_user_id`
FK→app_users.id nullable, index; `created_at`/`updated_at` DateTime.
Relationships (alle unidirektional): `employee` → Employee; `project` → Project; `order` →
Order; `order_item` → OrderItem|None.

## 70. `TimeEntryGroup` — Zeile 1577
`time_entry_groups`. `id` PK; `initiated_by_employee_id` FK→employees.id nullable, index;
`team_id` FK→teams.id nullable, index; `order_id` FK→orders.id NOT NULL, index; `project_id`
FK→projects.id NOT NULL, index; `order_item_id` FK→order_items.id nullable, index; `mode`
String(20) default "manual", index; `entry_type` String(40) default "site", index;
`activity` String(180) nullable; `work_date` Date NOT NULL, index; `started_at`/`ended_at`
DateTime nullable; `break_minutes` Integer default 0; `hours` Numeric(18,4) default 0;
`notes` Text nullable; `status` String(30) default "booked", index; `created_by_user_id`
FK→app_users.id nullable, index; `created_at`/`updated_at` DateTime.
Keine Relationships (migrationsarmes Muster, Mitglieder liegen in TimeEntryGroupMember).

## 71. `TimeEntryGroupMember` — Zeile 1606
`time_entry_group_members`. `__table_args__`: UniqueConstraint(group_id, employee_id);
UniqueConstraint(time_entry_id).
`id` PK; `group_id` FK→time_entry_groups.id NOT NULL, index; `employee_id` FK→employees.id NOT
NULL, index; `time_entry_id` FK→time_entries.id NOT NULL, index; `created_at` DateTime default
utcnow.
Keine Relationships.

## 72. `GeneralSettings` — Zeile 1620 (Singleton, id default 1)
`general_settings`. `company_name` String(255) default "DACHKONZEPTE Rödchen GmbH";
`managing_director` String(255) nullable; `street`/`postal_code`/`city` nullable; `country`
String(120) default "Deutschland"; `phone`/`email`/`website` nullable; `tax_number`/`vat_id`
String(80) nullable; `register_court` String(160) nullable; `register_number` String(80)
nullable; `iban` String(80) nullable; `bic` String(40) nullable; `default_vat_rate`
Numeric(9,4) default 19.00; `default_quote_intro`/`default_quote_outro` Text nullable;
`logo_filename` String(255) nullable; `reminders_auto_create_drafts` Boolean default True
server_default="1"; `accent_color` String(20) default "#0d9488" server_default="#0d9488";
`updated_at` DateTime.
Keine Relationships.

## 73. `NumberSequence` — Zeile 1658
`number_sequences`. `__table_args__`: UniqueConstraint(sequence_key).
`id` PK; `sequence_key` String(50) index; `label` String(120); `format_pattern` String(120);
`start_value`/`next_value` Integer default 1; `reset_yearly` Boolean default False;
`last_year` Integer nullable; `updated_at` DateTime.
Keine Relationships.

## 74. `EmployeeFunction` — Zeile 1674
`employee_functions`. `__table_args__`: UniqueConstraint(name).
`id` PK; `name` String(160) index; `employee_group` String(30) default "gewerblich", index;
`description` Text nullable; `sort_order` Integer default 100; `active` Boolean default True,
index; `created_at`/`updated_at` DateTime.
Relationships: `employee_profiles` → list[EmployeeProfile] back_populates="function".

## 75. `Employee` — Zeile 1692
`employees`. Kein `__table_args__`.
`id` PK; `employee_number` String(50) nullable, unique=True, index; `first_name` String(120)
NOT NULL; `last_name` String(120) index; `job_title` String(160) nullable (Legacy);
`employee_group` String(30) default "gewerblich", index; `hourly_wage` Numeric(18,6) nullable;
`weekly_hours` Numeric(9,4) default 40.00; `active` Boolean default True, index; `created_at`/
`updated_at` DateTime.
Relationships: `profile` → EmployeeProfile|None cascade delete-orphan uselist=False;
`compensation` → EmployeeCompensationSettings|None cascade delete-orphan uselist=False.

## 76. `EmployeeCompensationSettings` — Zeile 1718
`employee_compensation_settings`. `__table_args__`: UniqueConstraint(employee_id).
`id` PK; `employee_id` FK→employees.id NOT NULL, index; `compensation_type` String(30) default
"hourly", index; `monthly_salary` Numeric(18,2) nullable; `created_at`/`updated_at` DateTime.
Relationships: `employee` → Employee back_populates="compensation".

## 77. `EmployeeCostAllocationSettings` — Zeile 1738
`employee_cost_allocation_settings`. `__table_args__`: UniqueConstraint(employee_id).
`id` PK; `employee_id` FK→employees.id NOT NULL, index; `allocation_type` String(40) default
"labor_rate", index; `updated_at` DateTime.
Keine Relationships.

## 78. `EmployeeProfile` — Zeile 1754
`employee_profiles`. `__table_args__`: UniqueConstraint(employee_id).
`id` PK; `employee_id` FK→employees.id NOT NULL, index; `function_id`
FK→employee_functions.id nullable, index; `street`/`postal_code`/`city` nullable; `country`
String(120) default "Deutschland"; `phone`/`mobile`/`email` nullable; `birthday` Date
nullable; `important_info` Text nullable; `created_at`/`updated_at` DateTime.
Relationships: `employee` → Employee back_populates="profile"; `function` →
EmployeeFunction|None back_populates="employee_profiles".

## 79. `LaborRateSettings` — Zeile 1779 (Singleton, id default 1)
`labor_rate_settings`. `employer_cost_pct` Numeric(9,4) default 25.00; `productive_time_pct`
Numeric(9,4) default 70.00; `annual_overhead` Numeric(18,2) default 0; `target_profit_pct`
Numeric(9,4) default 0; `weeks_per_year` Numeric(9,4) default 52.00; `updated_at` DateTime.
Keine Relationships.

## 80. `LaborRateOverheadSettings` — Zeile 1796 (Singleton, id default 1)
`labor_rate_overhead_settings`. `fixed_overhead_mode` String(10) default "eur";
`fixed_overhead_value` Numeric(18,4) default 0; `variable_overhead_mode` String(10) default
"eur"; `variable_overhead_value` Numeric(18,4) default 0; `updated_at` DateTime.
Keine Relationships.

## 81. `SettingOptionGroup` — Zeile 1813
`setting_option_groups`. `__table_args__`: UniqueConstraint(group_key).
`id` PK; `group_key` String(80) index; `label` String(160); `description` Text nullable;
`sort_order` Integer default 100; `created_at`/`updated_at` DateTime.
Relationships: `options` → list[SettingOption] cascade delete-orphan order_by=sort_order.

## 82. `SettingOption` — Zeile 1832
`setting_options`. `__table_args__`: UniqueConstraint(group_id, label).
`id` PK; `group_id` FK→setting_option_groups.id NOT NULL, index; `label` String(180); `value`
Text NOT NULL; `sort_order` Integer default 100; `active` Boolean default True, index;
`is_default` Boolean default False; `created_at`/`updated_at` DateTime.
Relationships: `group` → SettingOptionGroup back_populates="options".

## 83. `EmployeeRoleSettings` — Zeile 1853
`employee_role_settings`. `__table_args__`: UniqueConstraint(employee_id).
`id` PK; `employee_id` FK→employees.id NOT NULL, index; `available_as_caseworker` Boolean
default False, index; `updated_at` DateTime.
Keine Relationships.

## 84. `EmployeePlanningSettings` — Zeile 1867
`employee_planning_settings`. `__table_args__`: UniqueConstraint(employee_id).
`id` PK; `employee_id` FK→employees.id NOT NULL, index; `show_on_planning_board` Boolean
default True, index; `updated_at` DateTime.
Keine Relationships.

## 85. `QuoteEmployeeAssignment` — Zeile 1878
`quote_employee_assignments`. `__table_args__`: UniqueConstraint(quote_id).
`id` PK; `quote_id` FK→quotes.id NOT NULL, index; `caseworker_employee_id` FK→employees.id
nullable, index; `updated_at` DateTime.
Keine Relationships (bewusst migrationsarm laut Docstring).

## 86. `AppUser` — Zeile 1890
`app_users`. `__table_args__`: UniqueConstraint(username).
`id` PK; `username` String(80) index; `password_hash` Text NOT NULL; `display_name`
String(160) NOT NULL; `employee_id` FK→employees.id nullable, index; `role` String(30) default
"user", index; `active` Boolean default True, index; `created_at`/`updated_at` DateTime;
`last_login_at` DateTime nullable.
Keine Relationships.

## 87. `UserDashboardWidget` — Zeile 1908
`user_dashboard_widgets`. `__table_args__`: UniqueConstraint(user_id, widget_key).
`id` PK; `user_id` FK→app_users.id NOT NULL, index; `widget_key` String(60) NOT NULL;
`sort_order` Integer default 100; `visible` Boolean default True.
Keine Relationships.

## 88. `EnabledModule` — Zeile 1925
`enabled_modules`. `__table_args__`: UniqueConstraint(module_key).
`id` PK; `module_key` String(60) NOT NULL; `enabled` Boolean default True; `updated_at`
DateTime.
Keine Relationships.

## 89. `Task` — Zeile 1943
`tasks`. Kein `__table_args__`.
`id` PK; `title` String(255); `description` Text nullable; `status` String(30) default
"offen", index; `priority` String(30) default "normal"; `due_date` Date nullable;
`assigned_employee_id` FK→employees.id nullable, index; `project_id` FK→projects.id nullable,
index; `created_by_user_id` FK→app_users.id nullable (kein index); `created_at`/`updated_at`
DateTime; `completed_at` DateTime nullable; `archived` Boolean default False server_default=
"0", index (seit 1.2.10); `source_module` String(60) nullable, index; `source_label`
String(255) nullable; `source_url` String(500) nullable.
Relationships: `assigned_employee` → Employee|None (unidirektional); `project` → Project|None
(unidirektional); `checklist_items` → list[TaskChecklistItem] cascade delete-orphan
order_by=sort_order,id.

## 90. `TaskColumn` — Zeile 1985
`task_columns`. `__table_args__`: UniqueConstraint(key).
`id` PK; `key` String(40) NOT NULL; `label` String(80) NOT NULL; `sort_order` Integer default
0; `is_done` Boolean default False server_default="0"; `created_at` DateTime default utcnow.
Keine Relationships (Task.status referenziert `key` als String, kein FK).

## 91. `TaskChecklistItem` — Zeile 2002
`task_checklist_items`. `id` PK; `task_id` FK→tasks.id NOT NULL, index; `title` String(255)
NOT NULL; `done` Boolean default False server_default="0"; `sort_order` Integer default 0;
`created_at` DateTime default utcnow.
Keine Relationships.

## 92. `TaskSettings` — Zeile 2015 (Singleton, id default 1)
`task_settings`. `notify_on_assignment` Boolean default True server_default="1"; `updated_at`
DateTime.
Keine Relationships.

## 93. `MaintenanceContract` — Zeile 2026
Siehe Hauptbericht Abschnitt 4 für vollständige Beschreibung.

## 94. `MaintenanceSettings` — Zeile 2064 (Singleton, id default 1)
`maintenance_settings`. `reminder_lead_days` Integer default 30 server_default="30";
`default_responsible_employee_id` FK→employees.id nullable; `updated_at` DateTime.
Relationships: `default_responsible_employee` → Employee|None (unidirektional).

## 95. `ServiceReport` — Zeile 2083
Siehe Hauptbericht Abschnitt 5 für vollständige Beschreibung.

## 96. `AuditLog` — Zeile 2116
`audit_logs`. Kein `__table_args__`.
`id` PK; `occurred_at` DateTime default utcnow, index; `actor_user_id` **keine ForeignKey**
(nur mapped_column nullable, index); `actor_name` String(160) default "System", index;
`action` String(30) NOT NULL, index; `entity_type` String(80) NOT NULL, index; `entity_id`
String(80) nullable, index; `entity_label` String(255) nullable; `project_id` **keine
ForeignKey** (nur mapped_column nullable, index); `field_name` String(120) nullable, index;
`field_label` String(160) nullable; `old_value`/`new_value` Text nullable; `request_method`
String(12) nullable; `request_path` String(500) nullable; `details` Text nullable.
Keine Relationships — bewusst reines Append-only-Protokoll ohne referenzielle Integrität.

## 97. `DocumentLayoutBlock` — Zeile 2139
`document_layout_blocks`. Kein `__table_args__`.
`id` PK; `document_type` String(20) NOT NULL, index (quote|order|invoice|reminder);
`block_type` String(30) NOT NULL; `label` String(120) NOT NULL; `x_mm`/`y_mm`/`width_mm`/
`height_mm` Numeric(6,2) NOT NULL; `content` Text nullable; `font_size` Numeric(4,1) default
9.5; `font_weight` String(10) default "normal"; `text_align` String(10) default "left";
`visible` Boolean default True; `sort_order` Integer default 10; `created_at`/`updated_at`
DateTime.
Keine Relationships.

## 98. `DocumentLayoutBackground` — Zeile 2190
`document_layout_backgrounds`. Kein `__table_args__` (Unique liegt direkt auf der Spalte).
`id` PK; `document_type` String(20) unique=True, index; `stored_filename` String(255) NOT
NULL; `repeat_on_every_page` Boolean default True server_default="1"; `uploaded_at` DateTime
default utcnow.
Keine Relationships.

## 99. `DocumentTableField` — Zeile 2219
`document_table_fields`. Kein `__table_args__`.
`id` PK; `document_type` String(20) NOT NULL, index; `block_type` String(30) NOT NULL, index;
`field_key` String(50) NOT NULL; `label` String(120) NOT NULL; `is_custom` Boolean default
False; `custom_value` Text nullable; `visible` Boolean default True; `sort_order` Integer
default 10; `created_at` DateTime default utcnow.
Keine Relationships.

## 100. `DocumentPageMargins` — Zeile 2259
`document_page_margins`. `__table_args__`: UniqueConstraint(document_type, page_type).
`id` PK; `document_type` String(20) NOT NULL, index; `page_type` String(20) NOT NULL
(first|continuation); `top_mm`/`bottom_mm`/`left_mm`/`right_mm` Numeric(5,1) NOT NULL;
`updated_at` DateTime.
Keine Relationships.

## 101. `SmtpSettings` — Zeile 2292 (Singleton, id default 1)
`smtp_settings`. `send_method` String(20) default "smtp" server_default="smtp" (smtp|
graph_oauth2); `host` String(255) nullable; `port` Integer default 587; `username`
String(255) nullable; `password_encrypted` Text nullable; `encryption` String(20) default
"starttls" (starttls|ssl|none); `sender_email`/`sender_name` String(255) nullable;
`graph_tenant_id`/`graph_client_id` String(255) nullable; `graph_client_secret_encrypted`
Text nullable; `graph_sender_mailbox` String(255) nullable; `updated_at` DateTime.
Keine Relationships.

## 102. `DocumentEmailTemplate` — Zeile 2341
`document_email_templates`. `__table_args__`: UniqueConstraint(document_type).
`id` PK; `document_type` String(20) NOT NULL, index (quote|order|invoice); `subject_template`
String(255) nullable; `body_template` Text nullable; `updated_at` DateTime.
Keine Relationships.

---

Klassen 93 (`MaintenanceContract`) und 95 (`ServiceReport`) sind im Hauptbericht
([`bestandsaufnahme.md`](bestandsaufnahme.md), Abschnitte 4 und 5) vollständig inklusive aller
Business-Logik-Funktionen beschrieben, hier nicht doppelt ausgeführt.
